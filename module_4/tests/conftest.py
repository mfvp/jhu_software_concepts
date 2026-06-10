"""
conftest.py - shared pytest fixtures and the fake database.
Module 4 / JHU Software Concepts in Python

The most important thing in here is the FakeConnection. It pretends to be a
psycopg2 connection but stores the the applicants in an in-memory dict keyed by url.
That dict gives us the url-uniqueness behaviour (idempotency) for free, so we can
test inserts/idempotency/queries without ever talking to a real Postgres server.

Because we inject this fake everywhere, the whole suite runs offline and fast,
which is exactly what the assignment asks for (no live internet, no real DB).
"""

import sys
from pathlib import Path

import pytest

# make the application modules in src/ importable (db, query_data, flask_app, ...)
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from db import APPLICANT_COLUMNS, Database  # noqa: E402  (import after sys.path tweak)
from flask_app import BusyState, create_app  # noqa: E402

URL_INDEX = APPLICANT_COLUMNS.index("url")


class FakeCursor:
    """A minimal stand-in for a psycopg2 cursor backed by an in-memory dict."""

    def __init__(self, store):
        self.store = store          # shared dict: url -> row tuple
        self._result = []
        self.rowcount = -1

    # cursors are used as context managers in the db layer
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        text = " ".join(sql.split()).upper()
        if text.startswith("CREATE TABLE"):
            self.rowcount = -1
        elif text.startswith("INSERT INTO"):
            url = params[URL_INDEX]
            if url in self.store:
                # duplicate url - mimic ON CONFLICT DO NOTHING
                self.rowcount = 0
            else:
                self.store[url] = tuple(params)
                self.rowcount = 1
        elif "COUNT(*)" in text:
            self._result = [(len(self.store),)]
        elif text.startswith("SELECT"):
            self._result = [tuple(row) for row in self.store.values()]
        else:  # pragma: no cover - we don't issue any other statements
            self._result = []

    def fetchone(self):
        return self._result[0]

    def fetchall(self):
        return list(self._result)

    def close(self):
        pass


class FakeConnection:
    """A stand-in psycopg2 connection. One shared store survives across cursors."""

    def __init__(self):
        self.store = {}
        self.commits = 0

    def cursor(self):
        return FakeCursor(self.store)

    def commit(self):
        self.commits += 1

    def rollback(self):  # pragma: no cover - not needed by the happy paths
        pass

    def close(self):
        pass


@pytest.fixture
def fake_conn():
    """A fresh in-memory fake connection (empty applicants 'table')."""
    return FakeConnection()


@pytest.fixture
def fake_db(fake_conn):
    """A Database wrapping the fake connection, schema already created."""
    database = Database(fake_conn)
    database.create_schema()
    return database


@pytest.fixture
def sample_rows():
    """A small set of applicant rows used across the db / integration tests."""
    return [
        {
            "program": "Computer Science, Stanford University",
            "comments": "fingers crossed",
            "date_added": "2026-03-01",
            "url": "https://www.thegradcafe.com/result/1",
            "status": "Accepted",
            "term": "Fall 2026",
            "us_or_international": "American",
            "gpa": 3.9, "gre": 330.0, "gre_v": 165.0, "gre_aw": 4.5,
            "degree": "PhD",
            "llm_generated_program": "Computer Science",
            "llm_generated_university": "Stanford University",
        },
        {
            "program": "Computer Science, MIT",
            "comments": None,
            "date_added": "2026-03-02",
            "url": "https://www.thegradcafe.com/result/2",
            "status": "Rejected",
            "term": "Fall 2026",
            "us_or_international": "International",
            "gpa": 3.6, "gre": 320.0, "gre_v": 160.0, "gre_aw": 4.0,
            "degree": "Masters",
            "llm_generated_program": "Computer Science",
            "llm_generated_university": "Massachusetts Institute of Technology",
        },
        {
            "program": "Computer Science, Johns Hopkins University",
            "comments": "waiting...",
            "date_added": "2026-03-03",
            "url": "https://www.thegradcafe.com/result/3",
            "status": "Accepted",
            "term": "Fall 2026",
            "us_or_international": "American",
            "gpa": 3.8, "gre": 325.0, "gre_v": 162.0, "gre_aw": 5.0,
            "degree": "Masters",
            "llm_generated_program": "Computer Science",
            "llm_generated_university": "Johns Hopkins University",
        },
    ]


@pytest.fixture
def fake_scraper(sample_rows):
    """A scraper that just returns the sample rows instead of hitting the network."""
    def _scraper():
        return list(sample_rows)
    return _scraper


@pytest.fixture
def app_factory(fake_conn, fake_scraper):
    """
    Build a create_app() with everything faked. The same fake_conn is shared
    between pull-data and analysis so rows written by a pull are visible when the
    page renders. Returns (factory, busy_state) so tests can tweak busy state.
    """
    busy = BusyState()

    def database_factory():
        return Database(fake_conn)

    def make_app(extra_config=None, scraper=None, busy_state=None):
        config = {"TESTING": True}
        if extra_config:
            config.update(extra_config)
        return create_app(
            test_config=config,
            scraper=scraper or fake_scraper,
            loader=None,  # use the real default_loader so we cover that code path
            database_factory=database_factory,
            busy_state=busy_state or busy,
        )

    return make_app, busy


@pytest.fixture
def client(app_factory):
    """A Flask test client wired to the fully-faked app."""
    make_app, _ = app_factory
    app = make_app()
    return app.test_client()
