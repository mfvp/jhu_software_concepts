"""
load_data.py - Load Grad Cafe Data into PostgreSQL
Module 3 / JHU Software Concepts in Python

Reads the LLM-enriched applicant data (JSONL file produced in module 2)
and loads it into a local PostgreSQL database using psycopg2.

Run:
    python load_data.py          # initial load from llm_extend_applicant_data_run.jsonl
    python load_data.py --new    # load newly scraped data from applicant_data.json
"""

# psycopg2 is the standard Python library for PostgreSQL
import psycopg2
import json
import re
import sys
import logging
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# load credentials from the .env file in this folder
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# credentials come from .env - see .env.example for the required variables
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "gradcafe"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "")
}

# paths to data files in this module's directory
MODULE_DIR = Path(__file__).parent
JSONL_FILE = MODULE_DIR / "llm_extend_applicant_data_run.jsonl"   # initial LLM-enriched data
JSON_FILE = MODULE_DIR / "applicant_data.json"                     # newly scraped data


def get_connection():
    """Connect to the PostgreSQL database and return the connection."""
    conn = psycopg2.connect(**DB_CONFIG)
    return conn


def create_table(conn):
    """
    Create the applicants table if it doesn't already exist.
    The schema matches the assignment specification exactly.
    ON CONFLICT on url lets us safely re-run this script without duplicating data.
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
    Parse date strings from grad cafe into Python date objects.
    The dates come in formats like 'May 31, 2026' or 'May 31'.
    Returns None if parsing fails so we don't crash on bad data.
    """
    if not date_str:
        return None

    cleaned = str(date_str).strip()

    formats = [
        "%B %d, %Y",   # May 31, 2026
        "%b %d, %Y",   # May 31, 2026 (abbreviated)
        "%B %d",       # May 31 (no year)
        "%b %d",       # May 31 (abbreviated, no year)
        "%Y-%m-%d",    # 2026-05-31 (ISO format, just in case)
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            # if the format had no year, strptime gives us 1900 - replace with current year
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
            return dt.date()
        except ValueError:
            continue

    logger.debug(f"Could not parse date: '{date_str}'")
    return None


def parse_float(val):
    """Try to convert a value to float. Returns None if it can't be done."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def load_jsonl(filepath):
    """
    Load data from a JSONL file (one JSON object per line).
    This is the format produced by the LLM enrichment step in module 2.
    """
    entries = []
    path = Path(filepath)
    if not path.exists():
        logger.error(f"File not found: {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError as e:
                logger.warning(f"Skipping bad JSON on line {line_num}: {e}")

    logger.info(f"Loaded {len(entries)} entries from {path.name}")
    return entries


def load_json(filepath):
    """
    Load data from a regular JSON file (array of objects).
    This is the format produced by scrape.py and clean.py from module 2.
    """
    path = Path(filepath)
    if not path.exists():
        logger.error(f"File not found: {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info(f"Loaded {len(data)} entries from {path.name}")
    return data if isinstance(data, list) else []


def insert_entries_from_jsonl(conn, entries):
    """
    Insert entries from the LLM-enriched JSONL format into the database.
    Fields: program, comments, date_added, url, status, term, US/International,
            Degree, GPA, GRE, GRE V, GRE AW, llm-generated-program, llm-generated-university
    """
    insert_sql = """
    INSERT INTO applicants
        (program, comments, date_added, url, status, term, us_or_international,
         gpa, gre, gre_v, gre_aw, degree, llm_generated_program, llm_generated_university)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (url) DO NOTHING;
    """

    inserted = 0
    skipped = 0
    errors = 0

    with conn.cursor() as cur:
        for entry in entries:
            program = entry.get("program")
            comments = entry.get("comments") or None
            if comments == "":
                comments = None
            date_added = parse_date(entry.get("date_added"))
            url = entry.get("url")
            status = normalize_status(entry.get("status"))
            term = entry.get("term")
            us_or_intl = entry.get("US/International")
            gpa = parse_float(entry.get("GPA"))
            gre = parse_float(entry.get("GRE"))
            gre_v = parse_float(entry.get("GRE V"))
            gre_aw = parse_float(entry.get("GRE AW"))
            degree = entry.get("Degree")
            llm_program = entry.get("llm-generated-program")
            llm_university = entry.get("llm-generated-university")

            try:
                cur.execute(insert_sql, (
                    program, comments, date_added, url, status, term,
                    us_or_intl, gpa, gre, gre_v, gre_aw,
                    degree, llm_program, llm_university
                ))
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.warning(f"Error inserting {url}: {e}")
                conn.rollback()
                errors += 1
                continue

    conn.commit()
    logger.info(f"JSONL load: {inserted} inserted, {skipped} skipped (duplicates), {errors} errors")
    return inserted


def insert_entries_from_json(conn, entries):
    """
    Insert entries from the scraper/cleaner JSON format.
    No LLM fields available so those will be NULL in the database.
    """
    insert_sql = """
    INSERT INTO applicants
        (program, comments, date_added, url, status, term, us_or_international,
         gpa, gre, gre_v, gre_aw, degree, llm_generated_program, llm_generated_university)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (url) DO NOTHING;
    """

    inserted = 0
    skipped = 0
    errors = 0

    with conn.cursor() as cur:
        for entry in entries:
            semester = entry.get("semester")
            year = entry.get("year")
            if semester and year:
                term = f"{semester} {year}"
            else:
                term = None

            program = entry.get("program")
            comments = entry.get("comments") or None
            date_added = parse_date(entry.get("date_added"))
            url = entry.get("url")
            status = normalize_status(entry.get("status"))
            us_or_intl = entry.get("applicant_type")
            gpa = parse_float(entry.get("gpa"))
            gre = parse_float(entry.get("gre_total"))
            gre_v = parse_float(entry.get("gre_v"))
            gre_aw = parse_float(entry.get("gre_aw"))
            degree = entry.get("degree")

            try:
                cur.execute(insert_sql, (
                    program, comments, date_added, url, status, term,
                    us_or_intl, gpa, gre, gre_v, gre_aw,
                    degree, None, None
                ))
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.warning(f"Error inserting {url}: {e}")
                conn.rollback()
                errors += 1
                continue

    conn.commit()
    logger.info(f"JSON load: {inserted} inserted, {skipped} skipped (duplicates), {errors} errors")
    return inserted


def print_summary(conn):
    """Print a quick summary of what's in the database."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applicants;")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM applicants WHERE term = 'Fall 2026';")
        fall2026 = cur.fetchone()[0]
    print(f"\nDatabase summary: {total} total entries, {fall2026} for Fall 2026")


def main(load_new=False):
    """
    Main function - connects to PostgreSQL, creates the table, and loads data.
    load_new=True loads from applicant_data.json (scraped), False loads the JSONL file.
    """
    logger.info("Connecting to PostgreSQL...")

    try:
        conn = get_connection()
        logger.info("Connected!")
    except Exception as e:
        logger.error(f"Could not connect to the database: {e}")
        logger.error("Check your DB_CONFIG settings and make sure PostgreSQL is running")
        return

    try:
        create_table(conn)

        if load_new:
            if not JSON_FILE.exists():
                logger.error(f"No scraped data file found at {JSON_FILE}")
                return
            entries = load_json(JSON_FILE)
            if entries:
                insert_entries_from_json(conn, entries)
        else:
            if not JSONL_FILE.exists():
                logger.error(f"Data file not found: {JSONL_FILE}")
                return
            entries = load_jsonl(JSONL_FILE)
            if entries:
                insert_entries_from_jsonl(conn, entries)

        print_summary(conn)

    finally:
        conn.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    load_new_data = "--new" in sys.argv
    if load_new_data:
        print("Loading newly scraped data from applicant_data.json...")
    else:
        print("Loading initial data from llm_extend_applicant_data_run.jsonl...")

    main(load_new=load_new_data)
