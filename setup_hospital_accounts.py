"""Initialize hospital self-registration for the isolated MRD test database.

This script never connects to medicine_redistribution_db and never deletes records.
It creates the account table when missing and safely activates older pending accounts
from the previous approval-based prototype by assigning each a new facility ID.
"""
from getpass import getpass
import os
import re
import mysql.connector

TEST_DATABASE = "medicine_redistribution_test_db"


def next_facility_id(cursor):
    cursor.execute("SELECT facility_id FROM facilities")
    rows = cursor.fetchall()
    ids = [str(row.get("facility_id") if isinstance(row, dict) else row[0]) for row in rows]
    numbers = [int(match.group(1)) for value in ids if (match := re.fullmatch(r"F(\d+)", value, re.IGNORECASE))]
    used = {value.upper() for value in ids}
    n = max(numbers, default=0) + 1
    candidate = f"F{n:03d}"
    while candidate.upper() in used:
        n += 1
        candidate = f"F{n:03d}"
    return candidate


def main():
    host = os.getenv("MEDICINE_DB_HOST", "localhost")
    user = os.getenv("MEDICINE_DB_USER", "root")
    password = os.getenv("MEDICINE_DB_PASSWORD") or getpass("MySQL password (hidden): ")
    if not password:
        print("No MySQL password supplied. Nothing was changed.")
        return 1

    print(f"Target database (fixed for safety): {TEST_DATABASE}")
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(
            host=host, user=user, password=password, database=TEST_DATABASE
        )
        if connection.database != TEST_DATABASE:
            raise RuntimeError(f"Safety stop: connected to {connection.database!r}.")
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portal_users (
                user_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(40) NOT NULL UNIQUE,
                email VARCHAR(254) NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('admin','hospital') NOT NULL DEFAULT 'hospital',
                status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'approved',
                facility_id VARCHAR(32) NULL,
                requested_facility_name VARCHAR(180) NULL,
                requested_location VARCHAR(255) NULL,
                contact VARCHAR(80) NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                approved_at DATETIME NULL,
                reviewed_by BIGINT NULL,
                reviewed_at DATETIME NULL,
                INDEX idx_portal_users_status_role (status, role),
                INDEX idx_portal_users_facility (facility_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        connection.commit()

        # Add a durable FIFO order to existing requests without deleting or resetting data.
        # Legacy rows receive an order based on their natural request ID (R2 before R10).
        cursor.execute("SHOW COLUMNS FROM redistribution_requests LIKE 'queue_order'")
        if cursor.fetchone() is None:
            cursor.execute(
                "ALTER TABLE redistribution_requests "
                "ADD COLUMN queue_order BIGINT UNSIGNED NULL"
            )

        cursor.execute("SELECT request_id, queue_order FROM redistribution_requests")
        request_rows = cursor.fetchall()
        def request_sort_key(value):
            value = str(value or "")
            match = re.fullmatch(r"R(\d+)", value, re.IGNORECASE)
            return (0, int(match.group(1))) if match else (1, value.casefold())

        next_queue_order = max(
            (int(row[1]) for row in request_rows if row[1] is not None), default=0
        )
        unsequenced = sorted(
            (row for row in request_rows if row[1] is None),
            key=lambda row: request_sort_key(row[0]),
        )
        for row in unsequenced:
            next_queue_order += 1
            cursor.execute(
                "UPDATE redistribution_requests SET queue_order=%s WHERE request_id=%s",
                (next_queue_order, row[0]),
            )
        connection.commit()
        print("Persistent FIFO request ordering is ready.")

        # The previous version used pending approvals. Under the selected policy,
        # pending hospital registrations are activated with their own facility row.
        cursor.close()
        cursor = connection.cursor(dictionary=True)
        # Fetch accounts and filter enum/text fields in Python to avoid collation conflicts.
        cursor.execute(
            "SELECT user_id, role, status, requested_facility_name, requested_location, created_at "
            "FROM portal_users ORDER BY created_at, user_id"
        )
        pending = [
            row for row in cursor.fetchall()
            if str(row.get("role") if isinstance(row, dict) else row[1]) == "hospital"
            and str(row.get("status") if isinstance(row, dict) else row[2]) == "pending"
        ]
        activated = 0
        for account in pending:
            facility_name = str(account.get("requested_facility_name") or "").strip()
            location = str(account.get("requested_location") or "").strip()
            if not facility_name or not location:
                # Keep malformed legacy records untouched so their missing details
                # can be repaired rather than creating a bad facility record.
                continue
            facility_id = next_facility_id(cursor)
            cursor.execute(
                "INSERT INTO facilities (facility_id, facility_name, location) VALUES (%s, %s, %s)",
                (facility_id, facility_name, location),
            )
            cursor.execute(
                "UPDATE portal_users SET facility_id=%s, status='approved', approved_at=NOW(), "
                "reviewed_by=NULL, reviewed_at=NULL WHERE user_id=%s AND role='hospital' AND status='pending'",
                (facility_id, int(account["user_id"])),
            )
            activated += cursor.rowcount
        connection.commit()
        print("Account table is ready.")
        print("Hospital registration now activates accounts automatically; no administrator approval is used.")
        print(f"Legacy pending registrations activated: {activated}")
        print("No existing inventory, request, or transaction records were deleted.")
        return 0
    except Exception as exc:
        if connection:
            connection.rollback()
        print(f"Setup failed: {exc}")
        return 1
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
