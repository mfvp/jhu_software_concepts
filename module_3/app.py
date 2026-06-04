"""
app.py - Flask Web Application for Grad Cafe Analysis
Module 3 / JHU Software Concepts in Python

Displays the SQL query results on a styled webpage.

Run:
    python app.py
Then open http://localhost:5000
"""

from flask import Flask, render_template
import psycopg2
import logging

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# same database settings as query_data.py
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "gradcafe",
    "user": "postgres",
    "password": "password"
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def run_analysis():
    """
    Execute all the SQL queries and return results as a dictionary.
    """
    conn = get_connection()
    results = {}

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM applicants WHERE term = 'Fall 2026';")
            results["q1"] = cur.fetchone()[0]

            cur.execute("""
                SELECT ROUND(
                    100.0
                    * COUNT(CASE WHEN us_or_international = 'International' THEN 1 END)
                    / NULLIF(COUNT(CASE WHEN us_or_international IN ('International', 'American') THEN 1 END), 0),
                    2
                )
                FROM applicants;
            """)
            results["q2"] = cur.fetchone()[0]

            cur.execute("""
                SELECT
                    ROUND(AVG(gpa)::numeric, 2),
                    ROUND(AVG(gre)::numeric, 2),
                    ROUND(AVG(gre_v)::numeric, 2),
                    ROUND(AVG(gre_aw)::numeric, 2)
                FROM applicants;
            """)
            row = cur.fetchone()
            results["q3_gpa"] = row[0]
            results["q3_gre"] = row[1]
            results["q3_gre_v"] = row[2]
            results["q3_gre_aw"] = row[3]

            cur.execute("""
                SELECT ROUND(AVG(gpa)::numeric, 2)
                FROM applicants
                WHERE us_or_international = 'American'
                  AND term = 'Fall 2026' AND gpa IS NOT NULL;
            """)
            results["q4"] = cur.fetchone()[0]

            cur.execute("""
                SELECT ROUND(
                    100.0 * COUNT(CASE WHEN status = 'Accepted' THEN 1 END) / NULLIF(COUNT(*), 0), 2
                )
                FROM applicants WHERE term = 'Fall 2026';
            """)
            results["q5"] = cur.fetchone()[0]

            cur.execute("""
                SELECT ROUND(AVG(gpa)::numeric, 2)
                FROM applicants
                WHERE term = 'Fall 2026' AND status = 'Accepted' AND gpa IS NOT NULL;
            """)
            results["q6"] = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*) FROM applicants
                WHERE (program ILIKE '%Johns Hopkins%' OR program ILIKE '%JHU%')
                  AND program ILIKE '%Computer Science%' AND degree = 'Masters';
            """)
            results["q7"] = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*) FROM applicants
                WHERE term ILIKE '%2026%' AND status = 'Accepted' AND degree = 'PhD'
                  AND program ILIKE '%Computer Science%'
                  AND (
                      program ILIKE '%Georgetown%' OR program ILIKE '%MIT%'
                      OR program ILIKE '%Stanford%' OR program ILIKE '%Carnegie Mellon%'
                  );
            """)
            results["q8"] = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*) FROM applicants
                WHERE term ILIKE '%2026%' AND status = 'Accepted' AND degree = 'PhD'
                  AND llm_generated_program ILIKE '%Computer Science%'
                  AND (
                      llm_generated_university ILIKE '%Georgetown%'
                      OR llm_generated_university ILIKE '%MIT%'
                      OR llm_generated_university ILIKE '%Stanford%'
                      OR llm_generated_university ILIKE '%Carnegie Mellon%'
                  );
            """)
            results["q9"] = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM applicants;")
            results["total"] = cur.fetchone()[0]

    finally:
        conn.close()

    return results


@app.route("/")
def index():
    """Render the main analysis page."""
    error = None
    results = {}

    try:
        results = run_analysis()
    except Exception as e:
        logger.error(f"Error running analysis: {e}")
        error = str(e)

    return render_template("index.html", results=results, error=error, scraping=False)


if __name__ == "__main__":
    app.run(debug=True)
