
"""
TEST 18: Verify complete database rollback when saving a redistribution fails.

This test uses medicine_redistribution_test_db only.
It does not modify the actual project database.
"""

import os
from datetime import date, timedelta

from mysql.connector import Error as MySQLError

# Force this test to use the separate test database.
os.environ["MEDICINE_DB_NAME"] = "medicine_redistribution_test_db"

from main import (
    MedicineBatch,
    MedicineInventory,
    RedistributionRequest,
    save_request_result,
    get_database_connection,
)


def test_save_failure_rollback():
    connection = None
    cursor = None

    source_id = "TEST18_SOURCE"
    destination_id = "TEST18_DEST"
    request_id = "TEST18_REQ"
    constraint_name = "chk_test18_force_failure"

    constraint_created = False

    try:
        # 1. Connect to the separate test database.
        connection = get_database_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT DATABASE()")
        database_name = cursor.fetchone()[0]

        if database_name != "medicine_redistribution_test_db":
            raise RuntimeError(
                f"Unsafe database selected: {database_name}"
            )

        print(f"PASS: Connected to {database_name}.")

        # 2. Remove leftover test data from a previous failed run.
        # Delete child transaction records before related test records.
        cursor.execute(
            "DELETE FROM redistribution_transactions WHERE request_id = %s",
            (request_id,),
        )
        cursor.execute(
            "DELETE FROM medicine_batches WHERE batch_id IN (%s, %s)",
            (source_id, destination_id),
        )
        cursor.execute(
            "DELETE FROM redistribution_requests WHERE request_id = %s",
            (request_id,),
        )
        connection.commit()

        # Remove our test constraint if an earlier run left it behind.
        try:
            cursor.execute(
                f"ALTER TABLE redistribution_requests "
                f"DROP CHECK {constraint_name}"
            )
            connection.commit()
        except MySQLError:
            connection.rollback()

        # 3. Add a test-only constraint.
        # Pending is allowed, but Fulfilled is rejected.
        # The save function updates the request to Fulfilled LAST.
        cursor.execute(
            f"ALTER TABLE redistribution_requests "
            f"ADD CONSTRAINT {constraint_name} "
            f"CHECK (status <> 'Fulfilled')"
        )
        connection.commit()
        constraint_created = True

        print("PASS: Test-only failure condition configured.")

        # 4. Insert a source batch and a pending request.
        future_expiry = (
            date.today() + timedelta(days=120)
        ).isoformat()

        cursor.execute(
            """
            INSERT INTO medicine_batches
                (batch_id, medicine_id, medicine_name, facility_id,
                 quantity, expiry_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                source_id,
                "TEST18_MED",
                "Rollback Test Medicine",
                "F001",
                10,
                future_expiry,
                "Available",
            ),
        )

        cursor.execute(
            """
            INSERT INTO redistribution_requests
                (request_id, destination_facility_id, medicine_id,
                 medicine_name, requested_quantity,
                 allocated_quantity, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request_id,
                "F004",
                "TEST18_MED",
                "Rollback Test Medicine",
                5,
                0,
                "Pending",
            ),
        )

        connection.commit()
        print("PASS: Test records inserted.")

        # 5. Capture the original database state.
        cursor.execute(
            "SELECT quantity, status FROM medicine_batches "
            "WHERE batch_id = %s",
            (source_id,),
        )
        original_source = cursor.fetchone()

        cursor.execute(
            "SELECT COUNT(*) FROM medicine_batches "
            "WHERE batch_id = %s",
            (destination_id,),
        )
        original_destination_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT allocated_quantity, status "
            "FROM redistribution_requests WHERE request_id = %s",
            (request_id,),
        )
        original_request = cursor.fetchone()

        cursor.execute(
            "SELECT COUNT(*) FROM redistribution_transactions "
            "WHERE request_id = %s",
            (request_id,),
        )
        original_transaction_count = cursor.fetchone()[0]

        print("PASS: Original database state captured.")

        # 6. Prepare the in-memory inventory.
        inventory = MedicineInventory()

        source_batch = MedicineBatch(
            source_id,
            "TEST18_MED",
            "Rollback Test Medicine",
            "F001",
            10,
            future_expiry,
            "Available",
        )
        inventory.add_batch(source_batch)

        # Simulate allocating 5 units from the source.
        source_batch.quantity = 5

        destination_batch = MedicineBatch(
            destination_id,
            "TEST18_MED",
            "Rollback Test Medicine",
            "F004",
            5,
            future_expiry,
            "Available",
        )
        inventory.add_batch(destination_batch)

        request = RedistributionRequest(
            request_id,
            "F004",
            "TEST18_MED",
            "Rollback Test Medicine",
            5,
        )
        request.total_allocated = 5
        request.remaining_quantity = 0
        request.status = "Fulfilled"

        transaction = {
            "request_id": request_id,
            "medicine_id": "TEST18_MED",
            "medicine_name": "Rollback Test Medicine",
            "batch_id": source_id,
            "source_batch_id": source_id,
            "destination_batch_id": destination_id,
            "source_facility": "F001",
            "destination_facility": "F004",
            "quantity_transferred": 5,
            "transaction_date": date.today().isoformat(),
        }

        # 7. Attempt the save. The final request update should fail
        # because the test-only CHECK constraint rejects Fulfilled.
        failure_observed = False

        try:
            save_request_result(
                connection,
                inventory,
                request,
                [transaction],
                {source_id},
            )
        except MySQLError as error:
            failure_observed = True
            print(
                "PASS: Expected database failure triggered: "
                f"{error.__class__.__name__}"
            )

        if not failure_observed:
            raise AssertionError(
                "Expected the request update to fail, but it succeeded."
            )

        # save_request_result() should already have rolled back.
        # Explicit rollback here is also safe.
        connection.rollback()

        # 8. Verify that the source stock was restored.
        cursor.execute(
            "SELECT quantity, status FROM medicine_batches "
            "WHERE batch_id = %s",
            (source_id,),
        )
        restored_source = cursor.fetchone()

        assert restored_source == original_source, (
            f"Source stock was not restored: {restored_source}"
        )
        print("PASS: Source stock update was rolled back.")

        # 9. Verify that the destination batch was not inserted.
        cursor.execute(
            "SELECT COUNT(*) FROM medicine_batches "
            "WHERE batch_id = %s",
            (destination_id,),
        )
        destination_count = cursor.fetchone()[0]

        assert destination_count == original_destination_count, (
            "Destination batch insertion was not rolled back."
        )
        print("PASS: Destination batch insertion was rolled back.")

        # 10. Verify that the transaction record was not saved.
        cursor.execute(
            "SELECT COUNT(*) FROM redistribution_transactions "
            "WHERE request_id = %s",
            (request_id,),
        )
        transaction_count = cursor.fetchone()[0]

        assert transaction_count == original_transaction_count, (
            "Transaction record was not rolled back."
        )
        print("PASS: Transaction record insertion was rolled back.")

        # 11. Verify that the request stayed unchanged.
        cursor.execute(
            "SELECT allocated_quantity, status "
            "FROM redistribution_requests WHERE request_id = %s",
            (request_id,),
        )
        restored_request = cursor.fetchone()

        assert restored_request == original_request, (
            f"Request state changed unexpectedly: {restored_request}"
        )
        print("PASS: Request record remains unchanged.")

        print("\nTEST 18 PASSED SUCCESSFULLY!")
        print("All database changes from the failed save were rolled back.")

    except Exception as error:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass

        print(f"\nTEST 18 FAILED: {error}")
        raise

    finally:
        if cursor is not None and connection is not None:
            # Remove the test-only constraint before cleaning up.
            if constraint_created:
                try:
                    cursor.execute(
                        "ALTER TABLE redistribution_requests "
                        f"DROP CHECK {constraint_name}"
                    )
                    connection.commit()
                except MySQLError as cleanup_error:
                    connection.rollback()
                    print(
                        "WARNING: Could not remove test constraint: "
                        f"{cleanup_error}"
                    )

            # Clean up only the test records.
            try:
                cursor.execute(
                    "DELETE FROM redistribution_transactions "
                    "WHERE request_id = %s",
                    (request_id,),
                )
                cursor.execute(
                    "DELETE FROM medicine_batches "
                    "WHERE batch_id IN (%s, %s)",
                    (source_id, destination_id),
                )
                cursor.execute(
                    "DELETE FROM redistribution_requests "
                    "WHERE request_id = %s",
                    (request_id,),
                )
                connection.commit()
                print("Test records cleaned up.")
            except MySQLError as cleanup_error:
                connection.rollback()
                print(
                    "WARNING: Test data cleanup needs attention: "
                    f"{cleanup_error}"
                )

            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()
            print("Test database connection closed.")


if __name__ == "__main__":
    test_save_failure_rollback()
