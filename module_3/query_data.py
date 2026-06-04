"""
query_data.py - SQL Query Analysis for Grad Cafe Data
Module 3 / JHU Software Concepts in Python

Runs SQL queries against the PostgreSQL applicants database to answer
the analysis questions from the assignment. Run load_data.py first!

Run:
    python query_data.py
"""

import psycopg2
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# same db settings as load_data.py
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "gradcafe",
    "user": "postgres",
    "password": "password"
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def run_query(conn, query, params=None):
    """Run a SELECT query and return all rows."""
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def main():
    print("\n=== Grad Cafe Data Analysis ===\n")

    try:
        conn = get_connection()
    except Exception as e:
        print(f"Could not connect to database: {e}")
        return

    try:
        # Q1: How many entries for Fall 2026?
        q1_sql = "SELECT COUNT(*) FROM applicants WHERE term = 'Fall 2026';"
        q1_result = run_query(conn, q1_sql)
        print(f"Q1) Entries for Fall 2026: {q1_result[0][0]}")

        # Q2: % international students
        # TODO: figure out the right denominator here
        q2_sql = """
            SELECT ROUND(
                100.0 * COUNT(CASE WHEN us_or_international = 'International' THEN 1 END)
                / NULLIF(COUNT(*), 0),
                2
            ) AS pct_international
            FROM applicants;
        """
        q2_result = run_query(conn, q2_sql)
        print(f"Q2) % International students: {q2_result[0][0]}%")

        # Q3: Average GPA, GRE, GRE V, GRE AW
        q3_sql = """
            SELECT
                ROUND(AVG(gpa)::numeric, 2)    AS avg_gpa,
                ROUND(AVG(gre)::numeric, 2)    AS avg_gre,
                ROUND(AVG(gre_v)::numeric, 2)  AS avg_gre_v,
                ROUND(AVG(gre_aw)::numeric, 2) AS avg_gre_aw
            FROM applicants;
        """
        q3_result = run_query(conn, q3_sql)
        r = q3_result[0]
        print(f"Q3) Average scores — GPA: {r[0]}, GRE: {r[1]}, GRE V: {r[2]}, GRE AW: {r[3]}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
