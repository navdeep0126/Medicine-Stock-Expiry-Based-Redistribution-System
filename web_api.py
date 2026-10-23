"""Flask API for the Medicine Stock & Expiry-Based Redistribution System.

This file reuses the project's existing DSA implementation in main.py.
For safety, it only runs against medicine_redistribution_test_db.
Run from the project root after setting MEDICINE_DB_PASSWORD.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import os
import re
import threading
from typing import Any

from flask import Flask, jsonify, request, send_from_directory, redirect, session, g
import mysql.connector
from functools import wraps
from werkzeug.security import check_password_hash

import main as core

PROJECT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_DIR / "frontend" if (PROJECT_DIR / "frontend").is_dir() else PROJECT_DIR / "Frontend"
TEST_DATABASE = "medicine_redistribution_test_db"

app = Flask(__name__, static_folder=None)
# Local development session: signed, HttpOnly cookies. Set MRS_SESSION_SECRET to a
# stable random value if you need sessions to survive a server restart.
app.secret_key = os.getenv("MRS_SESSION_SECRET") or os.urandom(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", PERMANENT_SESSION_LIFETIME=14400)
_process_lock = threading.Lock()


def _db_open():
    """Open a connection only when the explicitly selected DB is the test DB."""
    selected = os.getenv("MEDICINE_DB_NAME", "")
    if selected != TEST_DATABASE:
        raise RuntimeError(
            f"Safety stop: MEDICINE_DB_NAME must be {TEST_DATABASE!r}. "
            "Set the test database before starting the web API."
        )
    connection = core.get_database_connection()
    actual = getattr(connection, "database", None)
    if actual != TEST_DATABASE:
        connection.close()
        raise RuntimeError(
            f"Safety stop: connected to {actual!r}, not {TEST_DATABASE!r}."
        )
    return connection


def _rows(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    connection = _db_open()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def _one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    rows = _rows(sql, params)
    return rows[0] if rows else None


def _json_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _current_user():
    """Return the active approved account from the signed session, if any."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = _one(
        "SELECT user_id, username, email, role, status, facility_id, "
        "requested_facility_name, requested_location, contact "
        "FROM portal_users WHERE user_id=%s",
        (user_id,),
    )
    if not user or user["status"] != "approved":
        session.clear()
        return None
    user["facility_id"] = str(user["facility_id"]) if user["facility_id"] is not None else None
    if user["facility_id"]:
        facility = _one("SELECT facility_name FROM facilities WHERE facility_id=%s", (user["facility_id"],))
        user["facility_name"] = facility["facility_name"] if facility else user["facility_id"]
    else:
        user["facility_name"] = "System administrator"
    return user


def _auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            user = _current_user()
        except Exception as exc:
            return _json_error(f"Account service is not initialized. Run setup_hospital_accounts.py first. Details: {exc}", 503)
        if user is None:
            return _json_error("Please sign in to continue.", 401)
        g.current_user = user
        return view(*args, **kwargs)
    return wrapped


def _normalise_label(value: Any) -> str:
    """Normalize a label for duplicate checks in Python, avoiding collation-dependent SQL comparisons."""
    return " ".join(str(value or "").casefold().split())


def _next_facility_id(cursor) -> str:
    """Return the next F### ID using existing IDs; caller must hold registration lock."""
    cursor.execute("SELECT facility_id FROM facilities")
    rows = cursor.fetchall()
    ids = [str(row.get("facility_id") if isinstance(row, dict) else row[0]) for row in rows]
    numbers = [int(match.group(1)) for item in ids if (match := re.fullmatch(r"F(\d+)", item, re.IGNORECASE))]
    n = max(numbers, default=0) + 1
    used = {item.upper() for item in ids}
    candidate = f"F{n:03d}"
    while candidate.upper() in used:
        n += 1
        candidate = f"F{n:03d}"
    return candidate


_registration_lock = threading.Lock()

@app.post("/api/auth/register")
def register_hospital():
    """Create a facility and activate its hospital account immediately; no approval step."""
    data = request.get_json(silent=True) or {}
    facility_name = str(data.get("facilityName", "")).strip()
    location = str(data.get("location", "")).strip()
    contact = str(data.get("contact", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")

    if not facility_name or not location or not contact or not email or not username or not isinstance(password, str):
        return _json_error("Please complete every required field.")
    if len(facility_name) > 180 or len(location) > 255 or len(contact) > 80:
        return _json_error("Hospital name, location, or contact details are too long.")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        return _json_error("Enter a valid email address.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,40}", username):
        return _json_error("Username must be 3–40 characters using letters, numbers, dot, underscore, or hyphen.")
    if len(password) < 8 or len(password) > 128:
        return _json_error("Password must contain between 8 and 128 characters.")

    # Serializes registrations within this local app so generated F### IDs do not collide.
    with _registration_lock:
        connection = None
        cursor = None
        try:
            connection = _db_open()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT user_id FROM portal_users WHERE username=%s OR email=%s LIMIT 1",
                (username, email),
            )
            if cursor.fetchone():
                return _json_error("That username or email is already registered.", 409)

            # Compare names and addresses in Python. This avoids MySQL column-collation
            # mismatches and does not attach a new account to an existing facility.
            cursor.execute("SELECT facility_id, facility_name, location FROM facilities")
            for existing in cursor.fetchall():
                same_name = _normalise_label(existing.get("facility_name")) == _normalise_label(facility_name)
                same_location = _normalise_label(existing.get("location")) == _normalise_label(location)
                if same_name and same_location:
                    return _json_error(
                        "This hospital name and location are already registered. Please use the existing hospital account.",
                        409,
                    )

            facility_id = _next_facility_id(cursor)
            from werkzeug.security import generate_password_hash
            password_hash = generate_password_hash(password, method="pbkdf2:sha256")
            cursor.execute(
                "INSERT INTO facilities (facility_id, facility_name, location) VALUES (%s, %s, %s)",
                (facility_id, facility_name, location),
            )
            cursor.execute(
                "INSERT INTO portal_users "
                "(username, email, password_hash, role, status, facility_id, "
                "requested_facility_name, requested_location, contact, approved_at) "
                "VALUES (%s, %s, %s, 'hospital', 'approved', %s, %s, %s, %s, NOW())",
                (username, email, password_hash, facility_id, facility_name, location, contact),
            )
            user_id = int(cursor.lastrowid)
            connection.commit()

            # Automatically sign in the newly created account.
            session.clear()
            session["user_id"] = user_id
            session.permanent = True
            safe_user = {
                "username": username,
                "email": email,
                "role": "hospital",
                "facilityId": facility_id,
                "facilityName": facility_name,
            }
            return jsonify({
                "ok": True,
                "status": "approved",
                "message": "Hospital registered successfully. Your account is active.",
                "user": safe_user,
            }), 201
        except mysql.connector.IntegrityError:
            if connection:
                connection.rollback()
            return _json_error("That username, email, or facility ID is already in use. Please try again.", 409)
        except Exception as exc:
            if connection:
                connection.rollback()
            app.logger.exception("Hospital registration failed")
            return _json_error(f"Hospital registration failed: {exc}", 500)
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")
    if not username or not isinstance(password, str):
        return _json_error("Enter your username and password.")
    try:
        user = _one(
            "SELECT user_id, username, email, password_hash, role, status, facility_id "
            "FROM portal_users WHERE username=%s",
            (username,),
        )
        if not user or not check_password_hash(user["password_hash"], password):
            return _json_error("Incorrect username or password.", 401)
        if user["status"] != "approved":
            return _json_error("This account is not active yet. Run setup_hospital_accounts.py to migrate older registrations.", 403)
        session.clear()
        session["user_id"] = int(user["user_id"])
        session.permanent = True
        safe_user = {
            "username": user["username"], "email": user["email"], "role": user["role"],
            "facilityId": str(user["facility_id"]) if user["facility_id"] is not None else None,
        }
        if safe_user["facilityId"]:
            facility = _one("SELECT facility_name FROM facilities WHERE facility_id=%s", (safe_user["facilityId"],))
            safe_user["facilityName"] = facility["facility_name"] if facility else safe_user["facilityId"]
        else:
            safe_user["facilityName"] = "System administrator"
        return jsonify({"ok": True, "user": safe_user})
    except Exception as exc:
        return _json_error(str(exc), 503)


@app.get("/api/auth/me")
@_auth_required
def auth_me():
    user = g.current_user
    return jsonify({
        "username": user["username"], "email": user["email"], "role": user["role"],
        "facilityId": user["facility_id"], "facilityName": user["facility_name"],
        "contact": user.get("contact") or "",
    })


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})




def _date_text(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _facilities_map() -> dict[str, str]:
    rows = _rows("SELECT facility_id, facility_name FROM facilities")
    return {str(row["facility_id"]): str(row["facility_name"]) for row in rows}


def _medicine_map() -> dict[str, str]:
    """Build medicine master values from existing batch/request records without SQL UNION collation rules."""
    result: dict[str, str] = {}
    for table in ("medicine_batches", "redistribution_requests"):
        for row in _rows(f"SELECT medicine_id, medicine_name FROM {table}"):
            medicine_id = str(row["medicine_id"])
            medicine_name = str(row["medicine_name"] or medicine_id)
            result.setdefault(medicine_id, medicine_name)
    return dict(sorted(result.items(), key=lambda item: item[0]))


def _request_json(row: dict[str, Any], facilities: dict[str, str] | None = None):
    facilities = facilities if facilities is not None else _facilities_map()
    qty = int(row["requested_quantity"])
    allocated = int(row["allocated_quantity"])
    destination = str(row["destination_facility_id"])
    return {
        "id": str(row["request_id"]),
        "medicineId": str(row["medicine_id"]),
        "medicineName": str(row["medicine_name"]),
        "facilityId": destination,
        "facilityName": facilities.get(destination, destination),
        "qty": qty,
        "allocated": allocated,
        "remaining": max(0, qty - allocated),
        # The current MySQL table has no request-created date column.
        "date": None,
        "status": str(row["status"]),
    }


def _build_graph() -> core.FacilityConnectionGraph:
    """Use the same configured facility links as main.py."""
    graph = core.FacilityConnectionGraph()
    facility_ids = [str(row["facility_id"]) for row in _rows("SELECT facility_id FROM facilities")]
    for facility_id in facility_ids:
        graph.add_facility(facility_id)
    # Preserve the project's F004 hub configuration and connect newly registered
    # facilities to the same hub so they can participate in network redistribution.
    if "F004" in facility_ids:
        for facility_id in facility_ids:
            if facility_id != "F004":
                graph.add_connection("F004", facility_id)
    return graph


def _load_request_row(request_id: str):
    return _one(
        "SELECT request_id, destination_facility_id, medicine_id, medicine_name, "
        "requested_quantity, allocated_quantity, status "
        "FROM redistribution_requests WHERE request_id=%s",
        (request_id,),
    )


def _request_sort_key(request_id: Any):
    """Natural request order: R2 precedes R10. New request IDs are generated monotonically."""
    value = str(request_id)
    match = re.fullmatch(r"R(\d+)", value, re.IGNORECASE)
    return (0, int(match.group(1))) if match else (1, value.casefold())


def _load_inventory_and_request_queue(connection):
    """Load the original DSA inventory and rebuild the durable FIFO queue."""
    inventory, loaded_queue = core.load_database_data(connection)
    _normalize_inventory_status(inventory)
    existing = {str(item.request_id): item for item in getattr(loaded_queue, "requests", [])}

    cursor = connection.cursor(dictionary=True)
    try:
        # Load rows then filter in Python. This avoids collation-sensitive SQL string comparisons.
        cursor.execute(
            "SELECT request_id, destination_facility_id, medicine_id, medicine_name, "
            "requested_quantity, allocated_quantity, status, queue_order "
            "FROM redistribution_requests"
        )
        rows = [
            row for row in cursor.fetchall()
            if str(row["status"]) == "Pending"
            and int(row["allocated_quantity"]) < int(row["requested_quantity"])
        ]
    finally:
        cursor.close()

    rows.sort(key=lambda row: (
        row.get("queue_order") is None,
        int(row.get("queue_order") or 0),
        _request_sort_key(row["request_id"]),
    ))
    queue = core.RedistributionRequestQueue()
    for row in rows:
        request_id = str(row["request_id"])
        requested = int(row["requested_quantity"])
        allocated = int(row["allocated_quantity"])
        item = existing.get(request_id)
        if item is None:
            item = core.RedistributionRequest(
                request_id,
                str(row["destination_facility_id"]),
                str(row["medicine_id"]),
                str(row["medicine_name"]),
                requested,
            )
        item.total_allocated = allocated
        item.remaining_quantity = max(0, requested - allocated)
        item.status = str(row["status"])
        queue.add_request(item)

    return inventory, queue


def _batch_json(batch, medicine_names, facility_names):
    return {
        "batchId": batch.batch_id,
        "medicineId": batch.medicine_id,
        "medicineName": batch.medicine_name or medicine_names.get(batch.medicine_id, batch.medicine_id),
        "facilityId": batch.facility_id,
        "facilityName": facility_names.get(batch.facility_id, batch.facility_id),
        "qty": int(batch.quantity),
        "expiry": batch.expiry_date,
        "stock": batch.status,
    }


def _normalize_inventory_status(inventory):
    """Derive availability from quantity and expiry without changing DSA algorithms."""
    today = date.today()
    for batch in inventory.get_all_batches():
        expiry = date.fromisoformat(str(batch.expiry_date))
        quantity = int(batch.quantity)
        if expiry < today:
            batch.status = "Expired"
        elif quantity <= 0:
            batch.status = "Out of Stock"
        else:
            # Availability is not manually selected. Positive, unexpired stock is Available.
            batch.status = "Available"
    return inventory


@app.get("/api/health")
def health():
    try:
        connection = _db_open()
        try:
            try:
                cursor = connection.cursor()
                cursor.execute("SHOW TABLES LIKE 'portal_users'")
                auth_ready = cursor.fetchone() is not None
                cursor.close()
            except Exception:
                auth_ready = False
            return jsonify({"ok": True, "database": connection.database, "accountsConfigured": auth_ready})
        finally:
            connection.close()
    except Exception as exc:
        return _json_error(str(exc), 500)


@app.get("/api/batches")
@_auth_required
def get_batches():
    try:
        facilities = _facilities_map()
        medicines = _medicine_map()
        rows = _rows(
            "SELECT batch_id, medicine_id, medicine_name, facility_id, quantity, "
            "expiry_date, status FROM medicine_batches ORDER BY batch_id"
        )
        result = []
        today = date.today()
        for row in rows:
            expiry = row["expiry_date"]
            qty = int(row["quantity"])
            # Availability is calculated, not manually selected or inherited from a stale status.
            if expiry < today:
                status = "Expired"
            elif qty <= 0:
                status = "Out of Stock"
            else:
                status = "Available"
            result.append({
                "batchId": str(row["batch_id"]),
                "medicineId": str(row["medicine_id"]),
                "medicineName": str(row["medicine_name"] or medicines.get(str(row["medicine_id"]), row["medicine_id"])),
                "facilityId": str(row["facility_id"]),
                "facilityName": facilities.get(str(row["facility_id"]), str(row["facility_id"])),
                "qty": qty,
                "expiry": expiry.isoformat(),
                "stock": status,
            })
        return jsonify(result)
    except Exception as exc:
        return _json_error(str(exc), 500)


@app.get("/api/medicines")
@_auth_required
def get_medicines():
    try:
        return jsonify([
            {"id": medicine_id, "name": name}
            for medicine_id, name in _medicine_map().items()
        ])
    except Exception as exc:
        return _json_error(str(exc), 500)


def _batch_input(body: dict[str, Any], *, existing: dict[str, Any] | None = None):
    body = body or {}
    old = existing or {}
    batch_id = str(body.get("batchId", old.get("batch_id", ""))).strip()
    medicine_id = str(body.get("medicineId", old.get("medicine_id", ""))).strip()
    facility_id = str(body.get("facilityId", old.get("facility_id", ""))).strip()
    expiry = str(body.get("expiry", _date_text(old.get("expiry_date")) or "")).strip()
    raw_qty = body.get("qty", old.get("quantity"))
    try:
        if isinstance(raw_qty, bool):
            raise ValueError
        qty = int(raw_qty)
        if str(raw_qty).strip() != str(qty):
            # Allow normal JSON integers and integer strings only.
            if not isinstance(raw_qty, int):
                raise ValueError
    except (TypeError, ValueError):
        raise ValueError("Quantity must be a whole number.")
    medicine_name_input = str(body.get("medicineName") or "").strip()
    if not batch_id or not medicine_id or not facility_id or not expiry:
        raise ValueError("Batch ID, medicine, facility, quantity, and expiry date are required.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", medicine_id):
        raise ValueError("Medicine ID must use letters, numbers, hyphens or underscores only (maximum 32 characters).")
    if qty < 0:
        raise ValueError("Quantity cannot be negative.")
    try:
        parsed_expiry = date.fromisoformat(expiry)
    except ValueError:
        raise ValueError("Expiry date must use YYYY-MM-DD format.")
    if parsed_expiry.isoformat() != expiry:
        raise ValueError("Expiry date must use YYYY-MM-DD format.")

    facility = _one("SELECT facility_id FROM facilities WHERE facility_id=%s", (facility_id,))
    if facility is None:
        raise ValueError(f"Unknown facility ID: {facility_id}")

    medicine_map = _medicine_map()
    existing_id = next((key for key in medicine_map if key.casefold() == medicine_id.casefold()), None)
    if existing_id is not None:
        existing_name = medicine_map[existing_id]
        if medicine_name_input and _normalise_label(medicine_name_input) != _normalise_label(existing_name):
            raise ValueError(f"Medicine ID {existing_id} is already registered as {existing_name!r}.")
        medicine_name = existing_name
    else:
        medicine_name = medicine_name_input
        if not medicine_name:
            raise ValueError("For a new medicine, enter both a new Medicine ID and Medicine Name.")
        if len(medicine_name) > 180:
            raise ValueError("Medicine name must be 180 characters or fewer.")
        duplicate_name = next((
            (key, name) for key, name in medicine_map.items()
            if _normalise_label(name) == _normalise_label(medicine_name)
        ), None)
        if duplicate_name:
            raise ValueError(f"{medicine_name!r} already exists as medicine ID {duplicate_name[0]}. Select the existing medicine instead.")

    # Do not allow users to manually mark a positive, unexpired batch unavailable.
    # Its status is determined from expiry and quantity.
    if parsed_expiry < date.today():
        status = "Expired"
    elif qty <= 0:
        status = "Out of Stock"
    else:
        status = "Available"
    return {
        "batch_id": batch_id,
        "medicine_id": medicine_id,
        "medicine_name": medicine_name,
        "facility_id": facility_id,
        "quantity": qty,
        "expiry_date": expiry,
        "status": status,
    }


@app.post("/api/batches")
@_auth_required
def add_batch():
    try:
        data = request.get_json(silent=True) or {}
        if g.current_user["role"] == "hospital":
            if not g.current_user.get("facility_id"):
                return _json_error("This account is not linked to a facility.", 403)
            data["facilityId"] = g.current_user["facility_id"]
        values = _batch_input(data)
        if int(values["quantity"]) < 1:
            return _json_error("A new batch must start with at least one unit. To record stock reaching zero, edit an existing batch.")
        connection = _db_open()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT batch_id FROM medicine_batches WHERE LOWER(batch_id)=LOWER(%s)", (values["batch_id"],))
            if cursor.fetchone():
                connection.rollback()
                return _json_error(f"Batch ID {values['batch_id']} already exists. Use a different ID.", 409)
            cursor.execute(
                "INSERT INTO medicine_batches (batch_id, medicine_id, medicine_name, facility_id, quantity, expiry_date, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                tuple(values[k] for k in ("batch_id", "medicine_id", "medicine_name", "facility_id", "quantity", "expiry_date", "status")),
            )
            connection.commit()
            return jsonify({"ok": True, "batchId": values["batch_id"]}), 201
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except Exception as exc:
        return _json_error(str(exc), 500)


@app.put("/api/batches/<batch_id>")
@_auth_required
def update_batch(batch_id: str):
    try:
        connection = _db_open()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT batch_id, medicine_id, medicine_name, facility_id, quantity, expiry_date, status "
                "FROM medicine_batches WHERE batch_id=%s",
                (batch_id,),
            )
            old = cursor.fetchone()
            if old is None:
                return _json_error("Batch not found.", 404)
            if g.current_user["role"] == "hospital" and str(old["facility_id"]) != str(g.current_user.get("facility_id")):
                return _json_error("You can only edit batches belonging to your own facility.", 403)
            data = request.get_json(silent=True) or {}
            if g.current_user["role"] == "hospital":
                data["facilityId"] = g.current_user["facility_id"]
            values = _batch_input(data, existing=old)
            cursor.execute(
                "UPDATE medicine_batches SET medicine_id=%s, medicine_name=%s, facility_id=%s, "
                "quantity=%s, expiry_date=%s, status=%s WHERE batch_id=%s",
                (values["medicine_id"], values["medicine_name"], values["facility_id"], values["quantity"],
                 values["expiry_date"], values["status"], batch_id),
            )
            connection.commit()
            return jsonify({"ok": True, "batchId": batch_id})
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except Exception as exc:
        return _json_error(str(exc), 500)


@app.delete("/api/batches/<batch_id>")
@_auth_required
def delete_batch(batch_id: str):
    try:
        connection = _db_open()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT batch_id, facility_id FROM medicine_batches WHERE batch_id=%s", (batch_id,))
            batch_row = cursor.fetchone()
            if batch_row is None:
                return _json_error("Batch not found.", 404)
            if g.current_user["role"] == "hospital" and str(batch_row[1]) != str(g.current_user.get("facility_id")):
                return _json_error("You can only delete batches belonging to your own facility.", 403)
            cursor.execute("SELECT transaction_id FROM redistribution_transactions WHERE batch_id=%s LIMIT 1", (batch_id,))
            if cursor.fetchone():
                return _json_error("This batch is referenced by transaction history and cannot be deleted.", 409)
            cursor.execute("DELETE FROM medicine_batches WHERE batch_id=%s", (batch_id,))
            connection.commit()
            return jsonify({"ok": True})
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()
    except Exception as exc:
        return _json_error(str(exc), 500)


@app.get("/api/requests")
@_auth_required
def get_requests():
    try:
        rows = _rows(
            "SELECT request_id, destination_facility_id, medicine_id, medicine_name, "
            "requested_quantity, allocated_quantity, status, queue_order "
            "FROM redistribution_requests"
        )
        facilities = _facilities_map()
        status_rank = {"Partially Fulfilled": 1, "Fulfilled": 2, "Rejected": 3}
        rows.sort(key=lambda row: (
            0 if str(row["status"]) == "Pending" and int(row["allocated_quantity"]) < int(row["requested_quantity"]) else 1,
            int(row.get("queue_order") or 0) if str(row["status"]) == "Pending" and int(row["allocated_quantity"]) < int(row["requested_quantity"]) else status_rank.get(str(row["status"]), 4),
            _request_sort_key(row["request_id"]),
        ))
        return jsonify([_request_json(row, facilities) for row in rows])
    except Exception as exc:
        return _json_error(str(exc), 500)


@app.post("/api/requests")
@_auth_required
def create_request():
    try:
        data = request.get_json(silent=True) or {}
        medicine_id = str(data.get("medicineId", "")).strip()
        facility_id = str(data.get("facilityId", "")).strip()
        if g.current_user["role"] == "hospital":
            facility_id = str(g.current_user.get("facility_id") or "")
            if not facility_id:
                return _json_error("This account is not linked to a facility.", 403)
        raw_qty = data.get("qty")
        if isinstance(raw_qty, bool):
            raise ValueError("Requested quantity must be a whole number greater than zero.")
        try:
            qty = int(raw_qty)
        except (TypeError, ValueError):
            raise ValueError("Requested quantity must be a whole number greater than zero.")
        if qty <= 0 or (not isinstance(raw_qty, int) and str(raw_qty).strip() != str(qty)):
            raise ValueError("Requested quantity must be a whole number greater than zero.")
        medicine_map = _medicine_map()
        if medicine_id not in medicine_map:
            raise ValueError(f"Unknown medicine ID: {medicine_id}")
        if _one("SELECT facility_id FROM facilities WHERE facility_id=%s", (facility_id,)) is None:
            raise ValueError(f"Unknown facility ID: {facility_id}")

        connection = _db_open()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT request_id FROM redistribution_requests")
            ids = [str(row[0]) for row in cursor.fetchall()]
            numbers = [int(match.group(1)) for item in ids if (match := re.fullmatch(r"R(\d+)", item, re.IGNORECASE))]
            next_number = max(numbers, default=0) + 1
            request_id = f"R{next_number:03d}"
            while request_id in ids:
                next_number += 1
                request_id = f"R{next_number:03d}"
            cursor.execute("SELECT COALESCE(MAX(queue_order), 0) + 1 FROM redistribution_requests")
            queue_order = int(cursor.fetchone()[0])
            cursor.execute(
                "INSERT INTO redistribution_requests "
                "(request_id, destination_facility_id, medicine_id, medicine_name, requested_quantity, allocated_quantity, status, queue_order) "
                "VALUES (%s, %s, %s, %s, %s, 0, 'Pending', %s)",
                (request_id, facility_id, medicine_id, medicine_map[medicine_id], qty, queue_order),
            )
            connection.commit()
            return jsonify({"ok": True, "id": request_id, "requestId": request_id}), 201
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except Exception as exc:
        return _json_error(str(exc), 500)


@app.get("/api/requests/<request_id>/eligible")
@_auth_required
def get_eligible(request_id: str):
    connection = None
    try:
        # Load the actual rows into the project's Linked List and use the same
        # Linear Search + Insertion Sort classes as main.py. This route is read-only.
        connection = _db_open()
        row = _load_request_row(request_id)
        if row is None:
            return _json_error("Request not found.", 404)
        inventory, _queue = core.load_database_data(connection)
        _normalize_inventory_status(inventory)
        graph = _build_graph()
        request_obj = core.RedistributionRequest(
            str(row["request_id"]), str(row["destination_facility_id"]),
            str(row["medicine_id"]), str(row["medicine_name"]), int(row["requested_quantity"]),
        )
        request_obj.total_allocated = int(row["allocated_quantity"])
        request_obj.remaining_quantity = max(0, request_obj.requested_quantity - request_obj.total_allocated)
        request_obj.status = str(row["status"])

        eligible_sorted = core.MedicineBatchInsertionSort.sort_by_expiry(
            core.MedicineBatchLinearSearch.search(inventory, request_obj, graph)
        )
        eligible_ids = {batch.batch_id for batch in eligible_sorted}
        connected = set(graph.get_connected_facilities(request_obj.destination_facility))
        all_batches = inventory.get_all_batches()
        candidates = [
            batch for batch in all_batches
            if batch.medicine_id == request_obj.medicine_id
            and batch.facility_id != request_obj.destination_facility
            and batch.facility_id in connected
        ]
        eligible_rows = []
        excluded_rows = []
        remaining = request_obj.remaining_quantity
        supply = 0
        for batch in eligible_sorted:
            suggested = min(int(batch.quantity), remaining)
            remaining -= suggested
            supply += suggested
            eligible_rows.append({
                **_batch_json(batch, {}, {}),
                "eligible": True,
                "suggested": suggested,
                "reason": "Near expiry; prioritize transfer promptly." if core.get_expiry_label(batch.expiry_date).startswith("NEAR-EXPIRY") else None,
            })
        for batch in candidates:
            if batch.batch_id in eligible_ids:
                continue
            expiry = date.fromisoformat(batch.expiry_date)
            if expiry < date.today():
                reason = "Expired medicine is never redistributed."
            elif batch.quantity <= 0:
                reason = "Zero quantity in stock."
            elif batch.status != "Available":
                reason = f"Batch is marked {batch.status}."
            else:
                reason = "Batch is not eligible under the facility connection rules."
            excluded_rows.append({
                **_batch_json(batch, {}, {}),
                "eligible": False,
                "suggested": 0,
                "reason": reason,
            })

        facilities = _facilities_map()
        medicine_names = _medicine_map()
        for item in eligible_rows + excluded_rows:
            item["facilityName"] = facilities.get(item["facilityId"], item["facilityId"])
            item["medicineName"] = medicine_names.get(item["medicineId"], item["medicineId"])
        remaining_required = request_obj.remaining_quantity
        outcome = "none" if not eligible_sorted else ("full" if supply >= remaining_required else "partial")
        serialized_request = _request_json(row, facilities)
        serialized_request["medicineName"] = medicine_names.get(request_obj.medicine_id, request_obj.medicine_name)
        return jsonify({
            "request": serialized_request,
            "rows": eligible_rows + excluded_rows,
            "hasResult": True,
            "eligibleTotal": sum(int(batch.quantity) for batch in eligible_sorted),
            "supply": supply,
            "remaining": request_obj.remaining_quantity,
            "outcome": outcome,
        })
    except Exception as exc:
        return _json_error(str(exc), 500)
    finally:
        if connection is not None:
            connection.close()


@app.post("/api/redistribution/process-next")
@_auth_required
def process_next():
    """Process one FIFO request through the existing DSA classes and SQL saver."""
    if not _process_lock.acquire(blocking=False):
        return _json_error("Another redistribution request is currently being processed. Please wait.", 409)
    connection = None
    try:
        connection = _db_open()
        inventory, queue = _load_inventory_and_request_queue(connection)
        if queue.is_empty():
            return jsonify({"processed": False, "message": "No pending redistribution requests."})

        request_obj = queue.peek_request()
        graph = _build_graph()
        original_batch_ids = {batch.batch_id for batch in inventory.get_all_batches()}
        suitable = core.MedicineBatchLinearSearch.search(inventory, request_obj, graph)
        sorted_batches = core.MedicineBatchInsertionSort.sort_by_expiry(suitable)
        transaction_count_before = len(core.TRANSACTION_RECORDS)
        status = core.MedicineRedistributionGreedy.allocate_medicine(
            request_obj, sorted_batches, inventory
        )
        new_transactions = list(core.TRANSACTION_RECORDS[transaction_count_before:])
        # If a request remains completely Pending because no eligible quantity could
        # be allocated, move it to the back of the queue so other pending requests
        # can be processed. This change is committed atomically by the existing saver.
        if request_obj.status == "Pending":
            queue_cursor = connection.cursor()
            try:
                queue_cursor.execute("SELECT COALESCE(MAX(queue_order), 0) + 1 FROM redistribution_requests")
                next_queue_order = int(queue_cursor.fetchone()[0])
                queue_cursor.execute(
                    "UPDATE redistribution_requests SET queue_order=%s WHERE request_id=%s",
                    (next_queue_order, request_obj.request_id),
                )
            finally:
                queue_cursor.close()
        core.save_request_result(connection, inventory, request_obj, new_transactions, original_batch_ids)
        del core.TRANSACTION_RECORDS[transaction_count_before:]

        return jsonify({
            "processed": True,
            "requestId": request_obj.request_id,
            "status": status,
            "requested": request_obj.requested_quantity,
            "allocated": request_obj.total_allocated,
            "remaining": request_obj.remaining_quantity,
            "transferred": sum(int(t["quantity_transferred"]) for t in new_transactions),
            "transactions": [
                {"batchId": t["source_batch_id"], "destinationBatchId": t["destination_batch_id"],
                 "sourceId": t["source_facility"], "destId": t["destination_facility"],
                 "qty": int(t["quantity_transferred"]), "date": t["transaction_date"]}
                for t in new_transactions
            ],
            "message": f"{request_obj.request_id}: {status}. Remaining quantity: {request_obj.remaining_quantity}.",
        })
    except Exception as exc:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        return _json_error(str(exc), 500)
    finally:
        if connection is not None:
            connection.close()
        _process_lock.release()


@app.get("/api/transactions")
@_auth_required
def get_transactions():
    try:
        rows = _rows(
            "SELECT transaction_id, request_id, batch_id, source_facility_id, "
            "destination_facility_id, transferred_quantity, transaction_date "
            "FROM redistribution_transactions ORDER BY transaction_id DESC"
        )
        # Join request metadata in Python rather than comparing differently collated
        # request_id columns in MySQL.
        request_rows = _rows(
            "SELECT request_id, medicine_id, medicine_name FROM redistribution_requests"
        )
        request_info = {
            str(row["request_id"]): {
                "medicine_id": str(row["medicine_id"] or ""),
                "medicine_name": str(row["medicine_name"] or row["medicine_id"] or "Unknown medicine"),
            }
            for row in request_rows
        }
        facilities = _facilities_map()
        result = []
        for row in rows:
            request_id = str(row["request_id"])
            meta = request_info.get(request_id, {"medicine_id": "", "medicine_name": "Unknown medicine"})
            source = str(row["source_facility_id"])
            dest = str(row["destination_facility_id"])
            result.append({
                "id": f"T{int(row['transaction_id']):03d}",
                "requestId": request_id,
                "medicineId": meta["medicine_id"],
                "medicineName": meta["medicine_name"],
                "batchId": str(row["batch_id"]),
                "sourceId": source,
                "sourceName": facilities.get(source, source),
                "destId": dest,
                "destName": facilities.get(dest, dest),
                "qty": int(row["transferred_quantity"]),
                "date": _date_text(row["transaction_date"]),
            })
        return jsonify(result)
    except Exception as exc:
        app.logger.exception("Unable to load transactions")
        return _json_error(str(exc), 500)

@app.post("/api/facilities")
@_auth_required
def create_facility():
    """Admin helper: create a facility together with an immediately active hospital account."""
    if g.current_user.get("role") != "admin":
        return _json_error("Only the system administrator can create a facility from this page. Hospitals should self-register.", 403)

    data = request.get_json(silent=True) or {}
    facility_name = str(data.get("facilityName", "")).strip()
    location = str(data.get("location", "")).strip()
    contact = str(data.get("contact", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")

    if not facility_name or not location or not contact or not email or not username or not isinstance(password, str):
        return _json_error("Please complete every required facility and account field.")
    if len(facility_name) > 180 or len(location) > 255 or len(contact) > 80:
        return _json_error("Facility name, location, or contact details are too long.")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
        return _json_error("Enter a valid email address.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,40}", username):
        return _json_error("Username must be 3–40 characters using letters, numbers, dot, underscore, or hyphen.")
    if len(password) < 8 or len(password) > 128:
        return _json_error("Password must contain between 8 and 128 characters.")

    with _registration_lock:
        connection = None
        cursor = None
        try:
            connection = _db_open()
            cursor = connection.cursor(dictionary=True)

            # Compare account strings in Python to avoid mixed-collation comparisons.
            cursor.execute("SELECT username, email FROM portal_users")
            for account in cursor.fetchall():
                if _normalise_label(account.get("username")) == _normalise_label(username):
                    return _json_error("That username is already registered.", 409)
                if account.get("email") and _normalise_label(account.get("email")) == _normalise_label(email):
                    return _json_error("That email is already registered.", 409)

            cursor.execute("SELECT facility_id, facility_name, location FROM facilities")
            for existing in cursor.fetchall():
                if (_normalise_label(existing.get("facility_name")) == _normalise_label(facility_name)
                        and _normalise_label(existing.get("location")) == _normalise_label(location)):
                    return _json_error("This facility name and location are already registered.", 409)

            facility_id = _next_facility_id(cursor)
            from werkzeug.security import generate_password_hash
            password_hash = generate_password_hash(password, method="pbkdf2:sha256")
            cursor.execute(
                "INSERT INTO facilities (facility_id, facility_name, location) VALUES (%s, %s, %s)",
                (facility_id, facility_name, location),
            )
            cursor.execute(
                "INSERT INTO portal_users "
                "(username, email, password_hash, role, status, facility_id, requested_facility_name, "
                "requested_location, contact, approved_at) "
                "VALUES (%s, %s, %s, 'hospital', 'approved', %s, %s, %s, %s, NOW())",
                (username, email, password_hash, facility_id, facility_name, location, contact),
            )
            connection.commit()
            return jsonify({
                "ok": True,
                "facilityId": facility_id,
                "facilityName": facility_name,
                "username": username,
                "message": "Facility and active hospital account created successfully. No approval is pending.",
            }), 201
        except mysql.connector.IntegrityError:
            if connection:
                connection.rollback()
            return _json_error("The username, email, or facility details are already in use.", 409)
        except Exception as exc:
            if connection:
                connection.rollback()
            app.logger.exception("Facility creation failed")
            return _json_error(f"Facility creation failed: {exc}", 500)
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()


@app.get("/api/facilities")
@_auth_required
def get_facilities():
    try:
        facilities = _rows(
            "SELECT facility_id, facility_name, location FROM facilities ORDER BY facility_id"
        )
        # Filter account role/status in Python to avoid mixed-collation string comparisons.
        account_rows = _rows(
            "SELECT facility_id, contact, role, status FROM portal_users WHERE facility_id IS NOT NULL"
        )
        contacts = {}
        for account in account_rows:
            if str(account.get("role")) == "hospital" and str(account.get("status")) == "approved":
                contacts.setdefault(str(account["facility_id"]), str(account.get("contact") or ""))

        batches = _rows("SELECT facility_id, quantity FROM medicine_batches")
        requests_rows = _rows(
            "SELECT destination_facility_id, status FROM redistribution_requests"
        )
        stats: dict[str, dict[str, int]] = {}
        for row in facilities:
            stats[str(row["facility_id"])] = {"batches": 0, "units": 0, "active": 0}
        for row in batches:
            key = str(row["facility_id"])
            if key in stats:
                stats[key]["batches"] += 1
                stats[key]["units"] += int(row["quantity"])
        for row in requests_rows:
            key = str(row["destination_facility_id"])
            if key in stats and row["status"] in ("Pending", "Partially Fulfilled"):
                stats[key]["active"] += 1
        return jsonify([
            {"id": str(row["facility_id"]), "name": str(row["facility_name"]),
             "address": str(row["location"] or ""), "contact": contacts.get(str(row["facility_id"]), ""),
             **stats[str(row["facility_id"])]}
            for row in facilities
        ])
    except Exception as exc:
        app.logger.exception("Unable to load facilities")
        return _json_error(str(exc), 500)

@app.get("/")
def frontend_home():
    if not FRONTEND_DIR.is_dir():
        return _json_error("Frontend folder was not found. Put web_api.py beside main.py and the Frontend folder.", 500)
    try:
        user = _current_user()
    except Exception:
        user = None
    if user is None:
        return redirect("/login.html")
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:filename>")
def frontend_assets(filename: str):
    # Flask's send_from_directory prevents paths escaping the Frontend folder.
    if filename.startswith("api/"):
        return _json_error("API route not found.", 404)
    if not FRONTEND_DIR.is_dir():
        return _json_error("Frontend folder was not found next to web_api.py.", 500)
    public_pages = {"login.html", "register.html"}
    protected_pages = {"index.html", "inventory.html", "requests.html", "candidates.html", "transactions.html", "facilities.html"}
    if filename in protected_pages:
        try:
            user = _current_user()
        except Exception:
            user = None
        if user is None:
            return redirect("/login.html")
    elif filename in public_pages:
        try:
            user = _current_user()
        except Exception:
            user = None
        if user is not None:
            return redirect("/index.html")
    return send_from_directory(FRONTEND_DIR, filename)


if __name__ == "__main__":
    print("Medicine Redistribution Web API")
    print(f"Safety mode: database must be {TEST_DATABASE}")
    print("Automatic hospital registration is enabled; no approval page is used.")
    print("Open http://127.0.0.1:5000 in your browser.")
    app.run(host="127.0.0.1", port=5000, debug=False)
