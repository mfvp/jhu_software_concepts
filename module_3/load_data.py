"""
load_data.py - Load Grad Cafe Data into PostgreSQL
Module 3 / JHU Software Concepts in Python

Takes the cleaned applicant data from module 2 and loads it into a local
PostgreSQL database using psycopg2.

Run:
    python load_data.py
"""

# psycopg2 is the library we use to connect to PostgreSQL from Python
import psycopg2
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# update these settings to match your local PostgreSQL setup
# I set mine up following the lecture slide instructions for Windows
# (install from postgresql.org, set postgres user password, create gradcafe db)
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "gradcafe",
    "user": "postgres",
    "password": "password"   # change this to your actual postgres password
}


def get_connection():
    """Connect to the PostgreSQL database and return the connection."""
    conn = psycopg2.connect(**DB_CONFIG)
    return conn


if __name__ == "__main__":
    print("Testing database connection...")
    try:
        conn = get_connection()
        print("Connected to PostgreSQL!")
        conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Make sure PostgreSQL is running and check DB_CONFIG settings")
