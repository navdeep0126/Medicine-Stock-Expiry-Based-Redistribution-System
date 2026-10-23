"""
Medicine Stock & Expiry-Based Redistribution System
MCA Data Structures and Algorithmic Problem Solving Mini-Project

DSA components used: Linked List, FIFO Queue, Facility Graph, Linear Search,
Insertion Sort, and Greedy Allocation. MySQL stores persistent records.
Configure MEDICINE_DB_PASSWORD before running: python main.py
"""

from datetime import date
import os
import sys

import mysql.connector
from mysql.connector import Error as MySQLError

# Medicines expiring within this many days are flagged as near-expiry.
NEAR_EXPIRY_DAYS = 60

def get_expiry_label(expiry_date):
    """Return an expiry warning without changing the batch's stored status."""
    if isinstance(expiry_date, str):
        expiry_date = date.fromisoformat(expiry_date)

    days_remaining = (expiry_date - date.today()).days

    if days_remaining < 0:
        return f"EXPIRED ({abs(days_remaining)} days ago)"
    if days_remaining <= NEAR_EXPIRY_DAYS:
        return f"NEAR-EXPIRY ({days_remaining} days left)"
    return f"Normal ({days_remaining} days left)"

# Simple transaction history for every successful allocation.
TRANSACTION_RECORDS = []


# ============================================================
# 1. MEDICINE BATCH
# ============================================================

class MedicineBatch:
    def __init__(
        self,
        batch_id,
        medicine_id,
        medicine_name,
        facility_id,
        quantity,
        expiry_date,
        status="Available"
    ):
        # Validate quantity
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise ValueError("Quantity must be a whole number.")

        if quantity < 0:
            raise ValueError("Quantity cannot be negative.")

        # Validate required text fields
        fields = {
            "Batch ID": batch_id,
            "Medicine ID": medicine_id,
            "Medicine name": medicine_name,
            "Facility ID": facility_id,
            "Expiry date": expiry_date,
            "Status": status
        }

        for field_name, value in fields.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} cannot be empty.")

        # Validate expiry date
        try:
            parsed_expiry = date.fromisoformat(expiry_date)
            if parsed_expiry.isoformat() != expiry_date:
                raise ValueError
        except ValueError:
            raise ValueError(
                "Expiry date must use YYYY-MM-DD format."
            )

        self.batch_id = batch_id
        self.medicine_id = medicine_id
        self.medicine_name = medicine_name
        self.facility_id = facility_id
        self.quantity = quantity
        self.expiry_date = expiry_date
        self.status = status

    def display(self):
        print(
            f"{self.batch_id} | {self.medicine_name} | "
            f"Facility: {self.facility_id} | "
            f"Quantity: {self.quantity} | "
            f"Expiry: {self.expiry_date} | "
            f"Expiry alert: {get_expiry_label(self.expiry_date)} | "
            f"Status: {self.status}"
        )


# ============================================================
# 2. LINKED LIST - MEDICINE INVENTORY AND CRUD OPERATIONS
# ============================================================

class InventoryNode:
    def __init__(self, batch):
        self.batch = batch
        self.next = None


class MedicineInventory:
    def __init__(self):
        self.head = None

    # CREATE: Add a new medicine batch
    def add_batch(self, batch):
        current = self.head

        # Reject duplicate batch IDs
        while current is not None:
            if current.batch.batch_id == batch.batch_id:
                raise ValueError(
                    f"Duplicate batch ID rejected: {batch.batch_id}"
                )
            current = current.next

        new_node = InventoryNode(batch)

        if self.head is None:
            self.head = new_node
        else:
            current = self.head

            while current.next is not None:
                current = current.next

            current.next = new_node

        # Set correct initial status from quantity and expiry
        self._refresh_batch_status(batch)

    # READ: Return all medicine batches
    def get_all_batches(self):
        batches = []
        current = self.head

        while current is not None:
            batches.append(current.batch)
            current = current.next

        return batches

    # READ: Find one batch by ID
    def find_batch(self, batch_id):
        current = self.head

        while current is not None:
            if current.batch.batch_id == batch_id:
                return current.batch

            current = current.next

        return None

    # UPDATE: Change selected batch details
    def update_batch(
        self,
        batch_id,
        quantity=None,
        expiry_date=None,
        status=None
    ):
        batch = self.find_batch(batch_id)

        if batch is None:
            return False

        # Validate quantity before updating
        if quantity is not None:
            if (
                isinstance(quantity, bool)
                or not isinstance(quantity, int)
            ):
                raise ValueError(
                    "Quantity must be a whole number."
                )

            if quantity < 0:
                raise ValueError(
                    "Quantity cannot be negative."
                )

        # Validate expiry date before updating
        if expiry_date is not None:
            if not isinstance(expiry_date, str):
                raise ValueError(
                    "Expiry date must use YYYY-MM-DD format."
                )

            try:
                parsed_expiry = date.fromisoformat(expiry_date)
                if parsed_expiry.isoformat() != expiry_date:
                    raise ValueError
            except ValueError:
                raise ValueError(
                    "Expiry date must use YYYY-MM-DD format."
                )

        # Validate status before updating
        allowed_statuses = {
            "Available",
            "Unavailable",
            "Expired",
            "Out of Stock"
        }

        if status is not None and status not in allowed_statuses:
            raise ValueError(
                "Status must be Available, Unavailable, "
                "Expired, or Out of Stock."
            )

        # Apply changes only after validation
        if quantity is not None:
            batch.quantity = quantity

        if expiry_date is not None:
            batch.expiry_date = expiry_date

        if status is not None:
            batch.status = status

        # Keep expiry and zero-stock status consistent
        self._refresh_batch_status(batch)

        return True

    # DELETE: Remove a batch from the Linked List
    def delete_batch(self, batch_id):
        current = self.head
        previous = None

        while current is not None:
            if current.batch.batch_id == batch_id:

                # If the first node is being deleted
                if previous is None:
                    self.head = current.next
                else:
                    previous.next = current.next

                return True

            previous = current
            current = current.next

        return False

    # Keep status consistent with expiry and quantity
    def _refresh_batch_status(self, batch):
        today = date.today()
        expiry = date.fromisoformat(batch.expiry_date)

        if expiry < today:
            batch.status = "Expired"
        elif batch.quantity == 0:
            batch.status = "Out of Stock"
        elif batch.status in {"Expired", "Out of Stock"}:
            batch.status = "Available"

    def update_expired_batches(self):
        for batch in self.get_all_batches():
            self._refresh_batch_status(batch)

    # Display all batches
    def display_inventory(self):
        print("\n========== MEDICINE INVENTORY ==========")

        batches = self.get_all_batches()

        if not batches:
            print("Inventory is empty.")
            return

        for batch in batches:
            batch.display()


# ============================================================
# 3. QUEUE - REDISTRIBUTION REQUESTS
# ============================================================

class RedistributionRequest:
    def __init__(
        self,
        request_id,
        destination_facility,
        medicine_id,
        medicine_name,
        requested_quantity
    ):
        if (
            isinstance(requested_quantity, bool)
            or not isinstance(requested_quantity, int)
        ):
            raise ValueError(
                "Requested quantity must be a whole number."
            )

        if requested_quantity <= 0:
            raise ValueError(
                "Requested quantity must be greater than zero."
            )

        self.request_id = request_id
        self.destination_facility = destination_facility
        self.medicine_id = medicine_id
        self.medicine_name = medicine_name
        self.requested_quantity = requested_quantity
        self.remaining_quantity = requested_quantity
        self.total_allocated = 0
        self.status = "Pending"


class RedistributionRequestQueue:
    def __init__(self):
        self.requests = []

    def add_request(self, request):
        self.requests.append(request)

    def peek_request(self):
        if self.is_empty():
            return None

        return self.requests[0]

    def remove_request(self):
        if not self.is_empty():
            return self.requests.pop(0)

        return None

    def is_empty(self):
        return len(self.requests) == 0

    def display_queue(self):
        print("\n========== REDISTRIBUTION QUEUE ==========")

        if self.is_empty():
            print("No pending requests.")
            return

        for request in self.requests:
            print(
                f"Request: {request.request_id} | "
                f"Medicine: {request.medicine_name} | "
                f"Remaining: {request.remaining_quantity} | "
                f"Status: {request.status}"
            )


# ============================================================
# 4. GRAPH - FACILITY CONNECTIONS
# ============================================================

class FacilityConnectionGraph:
    def __init__(self):
        self.connections = {}

    def add_facility(self, facility_id):
        if facility_id not in self.connections:
            self.connections[facility_id] = []

    def add_connection(self, facility_a, facility_b):
        if not isinstance(facility_a, str) or not facility_a.strip():
            raise ValueError("Facility ID cannot be empty.")
        if not isinstance(facility_b, str) or not facility_b.strip():
            raise ValueError("Facility ID cannot be empty.")
        if facility_a == facility_b:
            raise ValueError("A facility cannot connect to itself.")

        self.add_facility(facility_a)
        self.add_facility(facility_b)

        if facility_b not in self.connections[facility_a]:
            self.connections[facility_a].append(facility_b)

        if facility_a not in self.connections[facility_b]:
            self.connections[facility_b].append(facility_a)

    def get_connected_facilities(self, facility_id):
        return self.connections.get(facility_id, [])


# ============================================================
# 5. LINEAR SEARCH - FIND SUITABLE MEDICINE BATCHES
# ============================================================

class MedicineBatchLinearSearch:
    @staticmethod
    def search(inventory, request, graph):
        suitable_batches = []

        connected_facilities = graph.get_connected_facilities(
            request.destination_facility
        )

        today = date.today()

        for batch in inventory.get_all_batches():

            if batch.medicine_id != request.medicine_id:
                continue

            if batch.facility_id == request.destination_facility:
                continue

            if batch.facility_id not in connected_facilities:
                continue

            expiry = date.fromisoformat(batch.expiry_date)

            if expiry < today:
                batch.status = "Expired"
                continue

            if batch.quantity <= 0:
                if batch.status != "Expired":
                    batch.status = "Out of Stock"
                continue

            if batch.status != "Available":
                continue

            suitable_batches.append(batch)

        return suitable_batches


# ============================================================
# 6. INSERTION SORT - EARLIEST EXPIRY FIRST
# ============================================================

class MedicineBatchInsertionSort:
    @staticmethod
    def sort_by_expiry(batches):
        # Priority: earliest expiry first. If expiry dates are equal,
        # use batch ID alphabetically as the documented tie-breaker.
        sorted_batches = batches.copy()

        for i in range(1, len(sorted_batches)):
            current_batch = sorted_batches[i]
            current_priority = (
                date.fromisoformat(current_batch.expiry_date),
                current_batch.batch_id
            )

            j = i - 1

            while j >= 0:
                previous_batch = sorted_batches[j]
                previous_priority = (
                    date.fromisoformat(previous_batch.expiry_date),
                    previous_batch.batch_id
                )

                if previous_priority <= current_priority:
                    break

                sorted_batches[j + 1] = sorted_batches[j]
                j -= 1

            sorted_batches[j + 1] = current_batch

        return sorted_batches


# ============================================================
# 7. GREEDY ALGORITHM - ALLOCATE MEDICINE
# ============================================================

class MedicineRedistributionGreedy:
    @staticmethod
    def allocate_medicine(request, batches, inventory):
        allocation_records = []
        previously_remaining = request.remaining_quantity

        print("\n========== REDISTRIBUTION PROCESS ==========")
        print(f"Request ID: {request.request_id}")
        print(f"Destination: {request.destination_facility}")
        print(f"Requested quantity: {request.requested_quantity}")
        print(f"Previously remaining: {previously_remaining}")

        today = date.today()

        for batch in batches:
            if request.remaining_quantity == 0:
                break

            # Recheck eligibility so an invalid batch cannot be allocated
            # even if it is accidentally passed directly to this method.
            if batch.medicine_id != request.medicine_id:
                continue
            if batch.facility_id == request.destination_facility:
                continue
            if date.fromisoformat(batch.expiry_date) < today:
                batch.status = "Expired"
                continue
            if batch.quantity <= 0:
                batch.status = "Out of Stock"
                continue
            if batch.status != "Available":
                continue

            allocated_quantity = min(
                batch.quantity,
                request.remaining_quantity
            )

            batch.quantity -= allocated_quantity

            # Update batch status when stock reaches zero
            if batch.quantity == 0:
                batch.status = "Out of Stock"

            request.remaining_quantity -= allocated_quantity
            request.total_allocated += allocated_quantity

            allocation_records.append(
                (batch, allocated_quantity)
            )

            # Add the transferred quantity to destination inventory as a
            # separate batch, preserving the source batch's expiry date.
            # Create a destination batch ID that does not already exist.
            existing_ids = {item.batch_id for item in inventory.get_all_batches()}
            number = 1
            while f"TR{number:04d}" in existing_ids:
                number += 1
            transfer_batch_id = f"TR{number:04d}"
            destination_batch = MedicineBatch(
                transfer_batch_id,
                batch.medicine_id,
                batch.medicine_name,
                request.destination_facility,
                allocated_quantity,
                batch.expiry_date,
                "Available"
            )
            inventory.add_batch(destination_batch)

            TRANSACTION_RECORDS.append({
                "request_id": request.request_id,
                "medicine_id": request.medicine_id,
                "medicine_name": request.medicine_name,
                "batch_id": batch.batch_id,
                "source_batch_id": batch.batch_id,
                "destination_batch_id": transfer_batch_id,
                "source_facility": batch.facility_id,
                "destination_facility": request.destination_facility,
                "quantity_transferred": allocated_quantity,
                "transaction_date": date.today().isoformat(),
            })

        for batch, allocated_quantity in allocation_records:
            print(
                f"Source: {batch.facility_id} | "
                f"Batch: {batch.batch_id} | "
                f"Allocated: {allocated_quantity} | "
                f"Source stock left: {batch.quantity}"
            )

        allocated_this_run = (
            previously_remaining - request.remaining_quantity
        )

        if request.remaining_quantity == 0:
            request.status = "Fulfilled"
        elif request.total_allocated > 0:
            request.status = "Partially Fulfilled"
        else:
            request.status = "Pending"

        print(f"Allocated in this run: {allocated_this_run}")
        print(f"Total allocated: {request.total_allocated}")
        print(f"Remaining quantity: {request.remaining_quantity}")
        print(f"Request status: {request.status}")

        return request.status


# ============================================================
# 8. VALIDATION TESTS
# ============================================================

def run_validation_tests(inventory):
    print("\n========== VALIDATION TESTS ==========")

    # Test 1: Duplicate batch ID
    try:
        inventory.add_batch(
            MedicineBatch(
                "B001", "M002", "Ibuprofen",
                "F006", 10, "2027-06-15", "Available"
            )
        )
    except ValueError as error:
        print("Duplicate ID test:", error)

    # Test 2: Decimal quantity
    try:
        MedicineBatch(
            "B005", "M003", "Test Medicine",
            "F006", 2.5, "2027-06-15", "Available"
        )
    except ValueError as error:
        print("Decimal quantity test:", error)

    # Test 3: Invalid expiry date
    try:
        MedicineBatch(
            "B006", "M003", "Test Medicine",
            "F006", 10, "31-12-2027", "Available"
        )
    except ValueError as error:
        print("Invalid expiry date test:", error)

    # Test 4: Negative quantity
    try:
        MedicineBatch(
            "B007", "M003", "Test Medicine",
            "F006", -5, "2027-06-15", "Available"
        )
    except ValueError as error:
        print("Negative quantity test:", error)

    # Test 5: Zero request quantity
    try:
        RedistributionRequest(
            "R003", "F004", "M001", "Paracetamol", 0
        )
    except ValueError as error:
        print("Invalid request quantity test:", error)


# ============================================================
# 9. CRUD OPERATIONS DEMONSTRATION
# ============================================================

def demonstrate_crud_operations():
    print("\n========== CRUD OPERATIONS TEST ==========")

    # Use a separate inventory so the main demonstration
    # and its sample redistribution data remain unchanged.
    test_inventory = MedicineInventory()

    # CREATE
    new_batch = MedicineBatch(
        "TEST001",
        "M100",
        "Test Medicine",
        "F100",
        25,
        "2027-12-31",
        "Available"
    )

    test_inventory.add_batch(new_batch)
    print("CREATE: Test batch added successfully.")

    # READ
    found_batch = test_inventory.find_batch("TEST001")

    if found_batch is not None:
        print("READ: Batch found.")
        found_batch.display()
    else:
        print("READ: Batch not found.")

    # UPDATE
    updated = test_inventory.update_batch(
        "TEST001",
        quantity=15,
        expiry_date="2028-06-30"
    )

    if updated:
        print("UPDATE: Batch updated successfully.")
        test_inventory.find_batch("TEST001").display()
    else:
        print("UPDATE: Batch not found.")

    # DELETE
    deleted = test_inventory.delete_batch("TEST001")

    if deleted:
        print("DELETE: Batch deleted successfully.")
    else:
        print("DELETE: Batch not found.")

    # Confirm deletion
    if test_inventory.find_batch("TEST001") is None:
        print("DELETE TEST: Confirmed batch no longer exists.")

    print("CRUD operations test completed.")


# ============================================================
# 10. MAIN PROGRAM
# ============================================================

def get_database_connection():
    """Connect to the existing MySQL database using environment settings."""
    password = os.getenv("MEDICINE_DB_PASSWORD")
    if not password:
        raise RuntimeError(
            "Database password is not set. In PowerShell, run:\n"
            '$env:MEDICINE_DB_PASSWORD = "YOUR_MYSQL_PASSWORD"\n'
            "Then run: python main.py"
        )

    return mysql.connector.connect(
        host=os.getenv("MEDICINE_DB_HOST", "localhost"),
        user=os.getenv("MEDICINE_DB_USER", "root"),
        password=password,
        database=os.getenv("MEDICINE_DB_NAME", "medicine_redistribution_db"),
    )


def load_database_data(connection):
    """Load database records into the project's Linked List and FIFO Queue."""
    inventory = MedicineInventory()
    request_queue = RedistributionRequestQueue()

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT batch_id, medicine_id, medicine_name, facility_id, "
            "quantity, expiry_date, status FROM medicine_batches ORDER BY batch_id"
        )
        for row in cursor.fetchall():
            expiry = row["expiry_date"].isoformat()
            batch = MedicineBatch(
                row["batch_id"], row["medicine_id"], row["medicine_name"],
                row["facility_id"], int(row["quantity"]), expiry, row["status"]
            )
            inventory.add_batch(batch)

        cursor.execute(
            "SELECT request_id, destination_facility_id, medicine_id, medicine_name, "
            "requested_quantity, allocated_quantity, status "
            "FROM redistribution_requests ORDER BY request_id"
        )
        for row in cursor.fetchall():
            requested = int(row["requested_quantity"])
            allocated = int(row["allocated_quantity"])
            status = row["status"]
            if status == "Fulfilled" or allocated >= requested:
                continue
            request = RedistributionRequest(
                row["request_id"], row["destination_facility_id"],
                row["medicine_id"], row["medicine_name"], requested
            )
            request.total_allocated = allocated
            request.remaining_quantity = max(0, requested - allocated)
            request.status = status
            request_queue.add_request(request)
    finally:
        cursor.close()

    inventory.update_expired_batches()
    return inventory, request_queue


def save_request_result(connection, inventory, request, new_transactions, original_batch_ids):
    """Save one request's changes in a single MySQL transaction."""
    cursor = connection.cursor()
    try:
        # Update quantities/status for original batches, including source stock.
        for batch in inventory.get_all_batches():
            if batch.batch_id in original_batch_ids:
                cursor.execute(
                    "UPDATE medicine_batches SET quantity=%s, status=%s, expiry_date=%s "
                    "WHERE batch_id=%s",
                    (batch.quantity, batch.status, batch.expiry_date, batch.batch_id)
                )

        # Add each newly created destination batch and its transaction record.
        for transaction in new_transactions:
            destination_batch = inventory.find_batch(transaction["destination_batch_id"])
            if destination_batch is None:
                raise RuntimeError(
                    f"Destination batch {transaction['destination_batch_id']} was not found."
                )
            cursor.execute(
                "INSERT INTO medicine_batches "
                "(batch_id, medicine_id, medicine_name, facility_id, quantity, expiry_date, status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (destination_batch.batch_id, destination_batch.medicine_id,
                 destination_batch.medicine_name, destination_batch.facility_id,
                 destination_batch.quantity, destination_batch.expiry_date,
                 destination_batch.status)
            )
            cursor.execute(
                "INSERT INTO redistribution_transactions "
                "(request_id, batch_id, source_facility_id, destination_facility_id, "
                "transferred_quantity, transaction_date) VALUES (%s, %s, %s, %s, %s, %s)",
                (transaction["request_id"], transaction["source_batch_id"],
                 transaction["source_facility"], transaction["destination_facility"],
                 transaction["quantity_transferred"], transaction["transaction_date"])
            )

        cursor.execute(
            "UPDATE redistribution_requests SET allocated_quantity=%s, status=%s "
            "WHERE request_id=%s",
            (request.total_allocated, request.status, request.request_id)
        )
        connection.commit()
        print("Database saved: stock, request status, and transactions updated.")
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def main():
    print("MEDICINE STOCK & EXPIRY REDISTRIBUTION SYSTEM")
    print("Loading records from MySQL...\n")

    connection = None
    try:
        connection = get_database_connection()
        print("Connected to medicine_redistribution_db successfully.")
        inventory, request_queue = load_database_data(connection)

        if not inventory.get_all_batches():
            print("\nNo medicine batches found in medicine_batches.")
            print("Add facility and batch records to MySQL, then run the program again.")
            return
        if request_queue.is_empty():
            print("\nNo pending redistribution requests were found.")
            inventory.display_inventory()
            return

        # Existing project graph. The current four-table schema has no table
        # for connections, so these are the project's configured demo links.
        graph = FacilityConnectionGraph()
        graph.add_connection("F004", "F001")
        graph.add_connection("F004", "F002")
        graph.add_connection("F004", "F003")
        graph.add_connection("F004", "F005")

        original_batch_ids = {batch.batch_id for batch in inventory.get_all_batches()}
        inventory.display_inventory()
        request_queue.display_queue()

        while not request_queue.is_empty():
            request = request_queue.peek_request()
            print(f"\nProcessing request: {request.request_id}")
            suitable_batches = MedicineBatchLinearSearch.search(inventory, request, graph)
            sorted_batches = MedicineBatchInsertionSort.sort_by_expiry(suitable_batches)

            print("\nSuitable batches in expiry order:")
            if not sorted_batches:
                print("No suitable medicine batches found.")
            for batch in sorted_batches:
                print(
                    f"{batch.batch_id} | Facility: {batch.facility_id} | "
                    f"Expiry: {batch.expiry_date} | "
                    f"Expiry alert: {get_expiry_label(batch.expiry_date)} | "
                    f"Quantity: {batch.quantity}"
                )

            transaction_count_before = len(TRANSACTION_RECORDS)
            status = MedicineRedistributionGreedy.allocate_medicine(
                request, sorted_batches, inventory
            )
            new_transactions = TRANSACTION_RECORDS[transaction_count_before:]
            save_request_result(
                connection, inventory, request, new_transactions, original_batch_ids
            )
            # Newly created destination batches now exist in MySQL and must not
            # be re-inserted as original batches on a later request.
            original_batch_ids.update(
                transaction["destination_batch_id"] for transaction in new_transactions
            )

            if status == "Fulfilled":
                request_queue.remove_request()
                print("Request fulfilled and removed from the processing queue.")
            else:
                print("Request remains pending/partially fulfilled.")
                print("Stopping to preserve FIFO order.")
                break

        print("\n========== REDISTRIBUTION TRANSACTION HISTORY (THIS RUN) ==========")
        if not TRANSACTION_RECORDS:
            print("No medicine transfers were completed.")
        else:
            for transaction in TRANSACTION_RECORDS:
                print(
                    f"Request: {transaction['request_id']} | "
                    f"Source batch: {transaction['source_batch_id']} | "
                    f"Destination batch: {transaction['destination_batch_id']} | "
                    f"Source: {transaction['source_facility']} | "
                    f"Destination: {transaction['destination_facility']} | "
                    f"Quantity: {transaction['quantity_transferred']} | "
                    f"Date: {transaction['transaction_date']}"
                )

        print("\n========== FINAL INVENTORY ==========")
        inventory.update_expired_batches()
        inventory.display_inventory()
        print("\nRedistribution workflow completed.")

    except (RuntimeError, MySQLError, ValueError) as error:
        if connection is not None:
            try:
                connection.rollback()
            except MySQLError:
                pass
        print(f"\nERROR: {error}")
        sys.exit(1)
    finally:
        if connection is not None and connection.is_connected():
            connection.close()
            print("\nMySQL connection closed.")


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()