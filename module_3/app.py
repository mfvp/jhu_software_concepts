"""
app.py - Flask Web Application for Grad Cafe Analysis
Module 3 / JHU Software Concepts in Python

Displays the SQL query results on a styled webpage.
Has two buttons:
  - "Pull Data": scrapes new entries from Grad Cafe and loads them into PostgreSQL
  - "Update Analysis": refreshes the page with the latest query results
                       (blocked if a pull is currently running)

Run:
    python app.py
Then open http://localhost:5000 in your browser.
"""

from flask import Flask, render_template, jsonify, redirect, url_for
import psycopg2
import subprocess
import threading
import sys
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# credentials come from .env - see .env.example for the required variables
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "gradcafe"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "")
}

# this flag tracks whether a data pull is currently running
# using threading.Event so it works safely across threads
scraping_in_progress = threading.Event()


def get_connection():
    """Get a database connection."""
    return psycopg2.connect(**DB_CONFIG)


def run_analysis():
    """
    Execute all the SQL queries and return results as a dictionary.
    Returns an empty dict if the connection fails so the page still loads.
    """
    conn = get_connection()
    results = {}

    try:
        with conn.cursor() as cur:

            # Q1: total Fall 2026 entries
            cur.execute("SELECT COUNT(*) FROM applicants WHERE term = 'Fall 2026';")
            results["q1"] = cur.fetchone()[0]

            # Q2: % international
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

            # Q3: average scores
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

            # Q4: avg GPA American Fall 2026
            cur.execute("""
                SELECT ROUND(AVG(gpa)::numeric, 2)
                FROM applicants
                WHERE us_or_international = 'American'
                  AND term = 'Fall 2026'
                  AND gpa IS NOT NULL;
            """)
            results["q4"] = cur.fetchone()[0]

            # Q5: % Fall 2026 acceptances
            cur.execute("""
                SELECT ROUND(
                    100.0 * COUNT(CASE WHEN status = 'Accepted' THEN 1 END) / NULLIF(COUNT(*), 0),
                    2
                )
                FROM applicants
                WHERE term = 'Fall 2026';
            """)
            results["q5"] = cur.fetchone()[0]

            # Q6: avg GPA of Fall 2026 acceptances
            cur.execute("""
                SELECT ROUND(AVG(gpa)::numeric, 2)
                FROM applicants
                WHERE term = 'Fall 2026' AND status = 'Accepted' AND gpa IS NOT NULL;
            """)
            results["q6"] = cur.fetchone()[0]

            # Q7: JHU Masters CS entries
            cur.execute("""
                SELECT COUNT(*) FROM applicants
                WHERE (program ILIKE '%Johns Hopkins%' OR program ILIKE '%JHU%')
                  AND program ILIKE '%Computer Science%'
                  AND degree = 'Masters';
            """)
            results["q7"] = cur.fetchone()[0]

            # Q8: 2026 PhD CS acceptances at top schools (raw fields)
            cur.execute("""
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
            """)
            results["q8"] = cur.fetchone()[0]

            # Q9: same as Q8 using LLM fields
            cur.execute("""
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
            """)
            results["q9"] = cur.fetchone()[0]

            # Q10: top 10 most applied-to universities
            cur.execute("""
                SELECT llm_generated_university, COUNT(*) AS entry_count
                FROM applicants
                WHERE llm_generated_university IS NOT NULL
                GROUP BY llm_generated_university
                ORDER BY entry_count DESC
                LIMIT 10;
            """)
            results["q10"] = cur.fetchall()

            # Q11: 10 universities with the lowest acceptance rate (min 15 entries)
            cur.execute("""
                SELECT
                    llm_generated_university,
                    ROUND(
                        100.0 * COUNT(CASE WHEN status = 'Accepted' THEN 1 END) / COUNT(*),
                        2
                    ) AS acceptance_rate,
                    COUNT(*) AS total_entries
                FROM applicants
                WHERE llm_generated_university IS NOT NULL
                GROUP BY llm_generated_university
                HAVING COUNT(*) >= 15
                ORDER BY acceptance_rate ASC
                LIMIT 10;
            """)
            results["q11"] = cur.fetchall()

            # total entries (shown at top of page)
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

    return render_template(
        "index.html",
        results=results,
        error=error,
        scraping=scraping_in_progress.is_set()
    )


@app.route("/scraping_status")
def scraping_status():
    """Returns JSON with whether a scrape is currently running. Used by the frontend."""
    return jsonify({"running": scraping_in_progress.is_set()})


@app.route("/pull_data")
def pull_data():
    """
    Start a background scrape + load pipeline.
    Returns immediately with a status message so the user isn't waiting.
    """
    if scraping_in_progress.is_set():
        return jsonify({
            "status": "already_running",
            "message": "A data pull is already in progress — please wait for it to finish."
        })

    def run_pipeline():
        """Runs in a background thread: scrape -> clean -> load."""
        scraping_in_progress.set()
        module_dir = Path(__file__).parent
        try:
            logger.info("Pull Data: starting scraper...")
            subprocess.run(
                [sys.executable, str(module_dir / "scrape.py")],
                cwd=str(module_dir),
                check=True
            )

            logger.info("Pull Data: cleaning data...")
            subprocess.run(
                [sys.executable, str(module_dir / "clean.py")],
                cwd=str(module_dir),
                check=True
            )

            logger.info("Pull Data: loading new entries into database...")
            subprocess.run(
                [sys.executable, str(module_dir / "load_data.py"), "--new"],
                cwd=str(module_dir),
                check=True
            )

            logger.info("Pull Data: pipeline complete!")
        except subprocess.CalledProcessError as e:
            logger.error(f"Pull Data pipeline failed: {e}")
        finally:
            scraping_in_progress.clear()

    # use daemon=True so the thread doesn't block Flask from shutting down
    t = threading.Thread(target=run_pipeline, daemon=True)
    t.start()

    return jsonify({
        "status": "started",
        "message": "Data pull has started! This may take several minutes. "
                   "The scraper is fetching the latest entries from Grad Cafe."
    })


@app.route("/update_analysis")
def update_analysis():
    """
    Refresh the analysis page — but only if no data pull is running.
    If a pull is running, tell the user to wait.
    """
    if scraping_in_progress.is_set():
        return jsonify({
            "status": "blocked",
            "message": "Cannot update right now — a data pull is in progress. "
                       "Please wait for it to finish, then try again."
        })

    # no pull running, just redirect back to the main page to reload results
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
