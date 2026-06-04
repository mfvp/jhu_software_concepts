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
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "gradcafe",
    "user": "postgres",
    "password": "password"
}


def get_connection():
    """Connect to the PostgreSQL database and return the connection."""
    conn = psycopg2.connect(**DB_CONFIG)
    return conn


def create_table(conn):
    """
    Create the applicants table if it doesn't already exist.
    The schema follows the assignment specification exactly.
    Using SERIAL for p_id so PostgreSQL auto-assigns an ID to each row.
    """
    create_sql = """
    CREATE TABLE IF NOT EXISTS applicants (
        p_id                    SERIAL PRIMARY KEY,
        program                 TEXT,
        comments                TEXT,
        date_added              DATE,
        url                     TEXT UNIQUE,
        status                  TEXT,
        term                    TEXT,
        us_or_international     TEXT,
        gpa                     FLOAT,
        gre                     FLOAT,
        gre_v                   FLOAT,
        gre_aw                  FLOAT,
        degree                  TEXT,
        llm_generated_program   TEXT,
        llm_generated_university TEXT
    );
    """
    with conn.cursor() as cur:
        cur.execute(create_sql)
    conn.commit()
    logger.info("Table 'applicants' is ready")


if __name__ == "__main__":
    print("Setting up database table...")
    try:
        conn = get_connection()
        print("Connected to PostgreSQL!")
        create_table(conn)
        print("Table created (or already exists)")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure PostgreSQL is running and check DB_CONFIG settings")
