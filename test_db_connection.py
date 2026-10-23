"""Safe connection check for the isolated MRD development database."""
import os
from getpass import getpass
import mysql.connector

TEST_DATABASE = "medicine_redistribution_test_db"
password = os.getenv("MEDICINE_DB_PASSWORD") or getpass("MySQL password (hidden): ")
try:
    connection = mysql.connector.connect(
        host=os.getenv("MEDICINE_DB_HOST", "localhost"),
        user=os.getenv("MEDICINE_DB_USER", "root"),
        password=password,
        database=TEST_DATABASE,
    )
    print("MySQL connection successful!")
    print("Database:", connection.database)
    connection.close()
except mysql.connector.Error as error:
    print("Connection failed:", error)
