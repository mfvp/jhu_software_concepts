"""
load_data.py - Load Grad Cafe Data into PostgreSQL
Module 3 / JHU Software Concepts in Python

Takes the cleaned applicant data from module 2 and loads it into a local
PostgreSQL database using psycopg2.

Run:
    python load_data.py
"""

import psycopg2
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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


def normalize_status(status_text):
    """
    Grad Cafe stores statuses like 'Accepted on May 31' or 'Wait Listed on Mar 3'.
    We just want the clean status word: Accepted, Rejected, Waitlisted, or Interview.
    """
    if not status_text:
        return None
    s = status_text.lower().strip()
    if "accept" in s:
        return "Accepted"
    elif "reject" in s:
        return "Rejected"
    elif "waitlist" in s or "wait list" in s or "wait listed" in s:
        return "Waitlisted"
    elif "interview" in s:
        return "Interview"
    return status_text.strip()


def parse_date(date_str):
    """
    Parse date strings like 'May 31, 2026' into Python date objects.
    I needed this because PostgreSQL can't accept strings like 'May 31, 2026' directly.
    Returns None if the string can't be parsed.
    """
    if not date_str:
        return None

    cleaned = str(date_str).strip()

    formats = [
        "%B %d, %Y",   # May 31, 2026
        "%b %d, %Y",   # abbreviated month
        "%B %d",       # no year (will use current year)
        "%b %d",
        "%Y-%m-%d",    # ISO format just in case
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
            return dt.date()
        except ValueError:
            continue

    logger.debug(f"Could not parse date: '{date_str}'")
    return None


def parse_float(val):
    """Try to convert a value to float. Returns None if it can't."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    print("Setting up database table...")
    try:
        conn = get_connection()
        create_table(conn)
        print("Table is ready!")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
