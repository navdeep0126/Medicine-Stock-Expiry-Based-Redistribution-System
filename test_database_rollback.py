
import os
os.environ["MEDICINE_DB_NAME"] = "medicine_redistribution_test_db"

from main import get_database_connection


def test_database_rollback():
    connection = None
    cursor = None
    table_created = False
    table_name = "rollback_test_temp"

    try:
        connection = get_database_connection()
        cursor = connection.cursor()

        # Remove a leftover temporary test table if present.
        cursor.execute(
            f"DROP TEMPORARY TABLE IF EXISTS {table_name}"
        )

        # Create a temporary InnoDB table.
        cursor.execute(
            f"""
            CREATE TEMPORARY TABLE {table_name} (
                test_id INT PRIMARY KEY,
                test_value VARCHAR(50)
            ) ENGINE=InnoDB
            """
        )
        table_created = True

        print("PASS: Temporary InnoDB test table created.")

        # Do not call start_transaction().
        # The connector starts a transaction for the insert.
        cursor.execute(
            f"""
            INSERT INTO {table_name} (test_id, test_value)
            VALUES (%s, %s)
            """,
            (1, "rollback-check"),
        )

        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        before_rollback = cursor.fetchone()[0]

        assert before_rollback == 1
        print("PASS: Test row exists before rollback.")

        # Undo the uncommitted insert.
        connection.rollback()

        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        after_rollback = cursor.fetchone()[0]

        assert after_rollback == 0, (
            "Test row still exists after rollback."
        )

        print("PASS: Inserted row was removed by rollback.")
        print("PASS: Database rollback works for the test transaction.")
        print("\nTEST 17 PASSED SUCCESSFULLY!")

    except Exception as error:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass

        print(f"\nTEST 17 FAILED: {error}")
        raise

    finally:
        if cursor is not None:
            if table_created:
                try:
                    cursor.execute(
                        f"DROP TEMPORARY TABLE IF EXISTS {table_name}"
                    )
                except Exception:
                    pass

            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    test_database_rollback()
