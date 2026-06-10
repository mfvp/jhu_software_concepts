"""
flask_app.py - Flask web layer for the Grad Cafe analytics app.
Module 4 / JHU Software Concepts in Python

Module 3 used a single global Flask `app` object which is awful to test. Module 4
switches to a create_app(...) factory so each test can spin up its own app with
fake dependencies injected. The factory takes optional scraper / loader /
database_factory callables so tests never hit the network or a real database.

Routes:
  GET  /                 -> same as /analysis
  GET  /analysis         -> renders the analysis page
  POST /pull-data        -> scrape + load new rows (gated while busy)
  POST /update-analysis  -> refresh analysis (gated while busy)

Busy state is kept in a small injectable object instead of using sleeps, so the
busy-gating tests stay deterministic.
"""

from flask import Flask, jsonify, render_template

from db import Database, connect
from load_data import load_entries
from query_data import get_analysis
from scrape import scrape


class BusyState:
    """Tracks whether a data pull is currently running. Observable for the tests."""

    def __init__(self):
        self._busy = False

    def is_busy(self):
        return self._busy

    def begin(self):
        self._busy = True

    def end(self):
        self._busy = False


def default_scraper():  # pragma: no cover - real network scrape
    """Production scraper: pull one page of live results from Grad Cafe."""
    return scrape(max_pages=1)


def default_loader(database, rows):
    """Production loader: insert already-scraped rows straight into the database."""
    database.create_schema()
    return database.insert_applicants(rows)


def default_database_factory():  # pragma: no cover - needs a real postgres
    """Production database: connect to postgres using DATABASE_URL."""
    return Database(connect())


def create_app(test_config=None, scraper=None, loader=None,
               database_factory=None, busy_state=None):
    """
    Application factory. All of the moving parts can be injected so the tests can
    run fully offline:

    * ``scraper()``: returns a list of scraped row dicts
    * ``loader(database, rows)``: inserts rows, returns count inserted
    * ``database_factory()``: returns a Database
    * ``busy_state``: a BusyState (lets a test pretend a pull is already running)
    """
    app = Flask(__name__)
    app.config["TESTING"] = False
    if test_config:
        app.config.update(test_config)

    # fall back to the real production wiring when nothing was injected
    scraper = scraper or default_scraper
    loader = loader or default_loader
    database_factory = database_factory or default_database_factory
    busy = busy_state or BusyState()

    def render_analysis():
        """Build the analysis dict and render the page from it."""
        database = database_factory()
        try:
            analysis = get_analysis(database)
        except Exception as exc:  # keep the page alive even if the DB is down
            return render_template("analysis.html", analysis=None,
                                   error=str(exc), busy=busy.is_busy())
        return render_template("analysis.html", analysis=analysis,
                               error=None, busy=busy.is_busy())

    @app.route("/")
    @app.route("/analysis")
    def analysis():
        """Render the main analysis page (status 200)."""
        return render_analysis()

    @app.route("/pull-data", methods=["POST"])
    def pull_data():
        """Scrape + load new rows. Returns 409 if a pull is already running."""
        if busy.is_busy():
            return jsonify({"busy": True}), 409

        busy.begin()
        try:
            rows = scraper()
            database = database_factory()
            inserted = loader(database, rows)
        except Exception as exc:
            # error path: report failure, and because the loader commits per call
            # a failure before insert leaves no partial rows behind
            busy.end()
            return jsonify({"ok": False, "error": str(exc)}), 500
        busy.end()
        return jsonify({"ok": True, "inserted": inserted}), 200

    @app.route("/update-analysis", methods=["POST"])
    def update_analysis():
        """Refresh analysis. Does nothing and returns 409 while a pull is busy."""
        if busy.is_busy():
            return jsonify({"busy": True}), 409
        return jsonify({"ok": True}), 200

    return app


if __name__ == "__main__":  # pragma: no cover
    create_app().run(debug=True)
