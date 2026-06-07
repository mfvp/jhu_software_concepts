"""
query_data.py - SQL Query Analysis for Grad Cafe Data
Module 3 / JHU Software Concepts in Python

Runs SQL queries against the PostgreSQL applicants database to answer
the analysis questions from the assignment. Run load_data.py first!

Run:
    python query_data.py
"""

# psycopg2 for talking to postgres, same as load_data.py
import psycopg2
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

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


def get_connection():
    """Connect to PostgreSQL and return the connection."""
    return psycopg2.connect(**DB_CONFIG)


def run_query(conn, query, params=None):
    """
    Execute a SQL query and return all rows as a list.
    Using parameterized queries to avoid SQL injection (good practice even for class work).
    """
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def main():
    print("\n=== Grad Cafe Data Analysis ===\n")

    try:
        conn = get_connection()
    except Exception as e:
        print(f"Could not connect to database: {e}")
        print("Make sure PostgreSQL is running and load_data.py has been run first")
        return

    try:
        # --- Q1: How many entries for Fall 2026? ---
        q1_sql = """
            SELECT COUNT(*)
            FROM applicants
            WHERE term = 'Fall 2026';
        """
        q1_result = run_query(conn, q1_sql)
        print(f"Q1) Entries for Fall 2026: {q1_result[0][0]}")

        # --- Q2: % of entries that are international students (not American or Other) ---
        # fixed: denominator should only count entries where us_or_international is
        # 'International' or 'American', excluding nulls and 'Other'
        q2_sql = """
            SELECT ROUND(
                100.0
                * COUNT(CASE WHEN us_or_international = 'International' THEN 1 END)
                / NULLIF(
                    COUNT(CASE WHEN us_or_international IN ('International', 'American') THEN 1 END),
                    0
                ),
                2
            ) AS pct_international
            FROM applicants;
        """
        q2_result = run_query(conn, q2_sql)
        print(f"Q2) % International students: {q2_result[0][0]}%")

        # --- Q3: Average GPA, GRE, GRE V, GRE AW across all applicants ---
        # using separate AVGs so we only average over rows that have a value for each metric
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

        # --- Q4: Average GPA of American students applying for Fall 2026 ---
        q4_sql = """
            SELECT ROUND(AVG(gpa)::numeric, 2) AS avg_gpa
            FROM applicants
            WHERE us_or_international = 'American'
              AND term = 'Fall 2026'
              AND gpa IS NOT NULL;
        """
        q4_result = run_query(conn, q4_sql)
        print(f"Q4) Avg GPA (American, Fall 2026): {q4_result[0][0]}")

        # --- Q5: % of Fall 2026 entries that are Acceptances ---
        q5_sql = """
            SELECT ROUND(
                100.0
                * COUNT(CASE WHEN status = 'Accepted' THEN 1 END)
                / NULLIF(COUNT(*), 0),
                2
            ) AS pct_accepted
            FROM applicants
            WHERE term = 'Fall 2026';
        """
        q5_result = run_query(conn, q5_sql)
        print(f"Q5) % Acceptances for Fall 2026: {q5_result[0][0]}%")

        # --- Q6: Average GPA of Fall 2026 acceptances ---
        q6_sql = """
            SELECT ROUND(AVG(gpa)::numeric, 2) AS avg_gpa
            FROM applicants
            WHERE term = 'Fall 2026'
              AND status = 'Accepted'
              AND gpa IS NOT NULL;
        """
        q6_result = run_query(conn, q6_sql)
        print(f"Q6) Avg GPA of Fall 2026 Acceptances: {q6_result[0][0]}")

        # --- Q7: Entries from JHU for a Masters in Computer Science ---
        # searching the raw program field for JHU / Johns Hopkins + Computer Science + Masters
        q7_sql = """
            SELECT COUNT(*) FROM applicants
            WHERE (
                program ILIKE '%Johns Hopkins%'
                OR program ILIKE '%JHU%'
            )
              AND program ILIKE '%Computer Science%'
              AND degree = 'Masters';
        """
        q7_result = run_query(conn, q7_sql)
        print(f"Q7) JHU Masters CS entries: {q7_result[0][0]}")

        # --- Q8: 2026 PhD CS Acceptances at Georgetown, MIT, Stanford, CMU (raw fields) ---
        # using the original 'program' column which stores the full "Program, University" string
        q8_sql = """
            SELECT COUNT(*) FROM applicants
            WHERE term ILIKE '%2026%'
              AND status = 'Accepted'
              AND degree = 'PhD'
              AND program ILIKE '%Computer Science%'
              AND (
                  program ILIKE '%Georgetown%'
                  OR program ILIKE '%Massachusetts Institute of Technology%'
                  OR program ILIKE '%MIT%'
                  OR program ILIKE '%Stanford%'
                  OR program ILIKE '%Carnegie Mellon%'
              );
        """
        q8_result = run_query(conn, q8_sql)
        print(f"Q8) 2026 PhD CS Acceptances (Georgetown/MIT/Stanford/CMU) — raw fields: {q8_result[0][0]}")

        # --- Q9: Same as Q8 but using LLM-generated university/program fields ---
        # LLM-generated fields should be cleaner and more consistent
        q9_sql = """
            SELECT COUNT(*) FROM applicants
            WHERE term ILIKE '%2026%'
              AND status = 'Accepted'
              AND degree = 'PhD'
              AND llm_generated_program ILIKE '%Computer Science%'
              AND (
                  llm_generated_university ILIKE '%Georgetown%'
                  OR llm_generated_university ILIKE '%Massachusetts Institute of Technology%'
                  OR llm_generated_university ILIKE '%MIT%'
                  OR llm_generated_university ILIKE '%Stanford%'
                  OR llm_generated_university ILIKE '%Carnegie Mellon%'
              );
        """
        q9_result = run_query(conn, q9_sql)
        print(f"Q9) 2026 PhD CS Acceptances (Georgetown/MIT/Stanford/CMU) — LLM fields: {q9_result[0][0]}")

        print()

        # --- Q10 (custom): [PLACEHOLDER - add your own question here] ---
        # TODO: formulate and answer a custom question about the data
        # Example: What is the distribution of degree types (PhD vs Masters)?
        # q10_sql = "..."

        # --- Q11 (custom): [PLACEHOLDER - add your own question here] ---
        # TODO: formulate and answer a second custom question
        # Example: Which universities have the most Fall 2026 accepted applicants?
        # q11_sql = "..."

        print("Q10) [Custom question — placeholder]")
        print("Q11) [Custom question — placeholder]")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
