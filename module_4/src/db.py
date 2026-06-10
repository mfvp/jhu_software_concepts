"""
db.py - Database access layer for the Grad Cafe analytics app.
Module 4 / JHU Software Concepts in Python

In module 3 the SQL was spread out across load_data.py and app.py which made it
really hard to test. So for module 4 I pulled all the Postgres stuff into one
small "Database" class. The class just wraps a DB-API connection (psycopg2 in
real life) so the rest of the app never talk to psycopg2 directly. This also
lets the tests pass in a fake connection instead of needing a live database.

Connection settings come from the DATABASE_URL environment variable (the grader
asked for this) so nothing is hard coded.
"""

import os

import psycopg2


# default points at a local postgres - tests/CI override this with DATABASE_URL
DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/gradcafe"

# the column order used everywhere when we insert / read rows.
# keeping it in one list means insert and fetch can never get out of sync.
APPLICANT_COLUMNS = [
    "program",
    "comments",
    "date_added",
    "url",
    "status",
    "term",
    "us_or_international",
    "gpa",
    "gre",
    "gre_v",
    "gre_aw",
    "degree",
    "llm_generated_program",
    "llm_generated_university",
]

# the fields that must never be null for a row to count as a real applicant.
# url is also the uniqueness key so a duplicate pull doesn't create dupes.
REQUIRED_FIELDS = ["program", "url", "status", "term"]

# schema is exactly the module 3 schema - the assignment says not to change it
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS applicants (
    p_id                     SERIAL PRIMARY KEY,
    program                  TEXT,
    comments                 TEXT,
    date_added               DATE,
    url                      TEXT UNIQUE,
    status                   TEXT,
    term                     TEXT,
    us_or_international       TEXT,
    gpa                      FLOAT,
    gre                      FLOAT,
    gre_v                    FLOAT,
    gre_aw                   FLOAT,
    degree                   TEXT,
    llm_generated_program    TEXT,
    llm_generated_university TEXT
);
"""

# %s placeholders are psycopg2 style. ON CONFLICT(url) is our idempotency policy:
# pulling the same row twice just does nothing instead of duplicating it.
INSERT_SQL = """
INSERT INTO applicants
    (program, comments, date_added, url, status, term, us_or_international,
     gpa, gre, gre_v, gre_aw, degree, llm_generated_program, llm_generated_university)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (url) DO NOTHING;
"""


def get_database_url():
    """Return the configured DATABASE_URL, falling back to a local default."""
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def connect(database_url=None):  # pragma: no cover - needs a real postgres server
    """Open a real psycopg2 connection. Tests inject a fake instead of calling this."""
    url = database_url or get_database_url()
    return psycopg2.connect(url)


class Database:
    """Thin wrapper around a DB-API connection so the app never touches psycopg2 directly."""

    def __init__(self, conn):
        # conn is anything that quacks like a psycopg2 connection (or our fake)
        self.conn = conn

    def create_schema(self):
        """Create the applicants table if it isn't there yet."""
        with self.conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
        self.conn.commit()

    def insert_applicants(self, rows):
        """
        Insert a list of row dicts. Returns how many rows were actually inserted
        (duplicates are skipped thanks to ON CONFLICT, so they don't get counted).
        """
        inserted = 0
        with self.conn.cursor() as cur:
            for row in rows:
                values = tuple(row.get(col) for col in APPLICANT_COLUMNS)
                cur.execute(INSERT_SQL, values)
                # rowcount is 1 when a row went in, 0 when ON CONFLICT skipped it
                if cur.rowcount and cur.rowcount > 0:
                    inserted += 1
        self.conn.commit()
        return inserted

    def count(self):
        """Return the total number of rows in the applicants table."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM applicants;")
            return cur.fetchone()[0]

    def fetch_all(self):
        """Read every applicant back as a list of dicts keyed by APPLICANT_COLUMNS."""
        columns = ", ".join(APPLICANT_COLUMNS)
        with self.conn.cursor() as cur:
            cur.execute("SELECT " + columns + " FROM applicants;")
            rows = cur.fetchall()
        return [dict(zip(APPLICANT_COLUMNS, row)) for row in rows]

    def close(self):
        """Close the underlying connection."""
        self.conn.close()
