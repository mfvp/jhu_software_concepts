"""
test_integration_end_to_end.py - full pull -> update -> render flows.
Module 4 / JHU Software Concepts in Python

Wires the whole app together with a fake scraper (multiple records) and the
shared in-memory database, then walks through the real user flow: pull the data,
update the analysis, and render the page. Also checks the uniqueness policy holds
across multiple overlapping pulls.
"""

import re

import pytest

from db import Database
from flask_app import BusyState, create_app

PERCENT_RE = re.compile(r"\d+\.\d{2}%")


@pytest.mark.integration
def test_pull_update_render(app_factory, fake_conn):
    """End to end: pull inserts rows, update succeeds, render shows formatted data."""
    make_app, _ = app_factory
    client = make_app().test_client()

    # 1) pull -> rows land in the database
    pull = client.post("/pull-data")
    assert pull.status_code == 200
    assert pull.get_json()["inserted"] == 3
    assert len(fake_conn.store) == 3

    # 2) update analysis works when not busy
    update = client.post("/update-analysis")
    assert update.status_code == 200

    # 3) the rendered page reflects the data with two-decimal percentages
    html = client.get("/analysis").data.decode("utf-8")
    assert "Total entries in database: 3" in html
    assert "Answer:" in html
    assert PERCENT_RE.search(html)


@pytest.mark.integration
def test_multiple_pulls_stay_consistent(app_factory, fake_conn):
    """Running pull-data twice with overlapping data keeps the DB de-duplicated."""
    make_app, _ = app_factory
    client = make_app().test_client()

    client.post("/pull-data")
    client.post("/pull-data")   # same fake rows again

    # still only the 3 unique rows - uniqueness policy respected
    assert len(fake_conn.store) == 3


@pytest.mark.integration
def test_render_handles_database_error():
    """If the analysis query blows up, the page still renders with an error banner."""
    class BrokenDatabase:
        def fetch_all(self):
            raise RuntimeError("db is down")

    app = create_app(
        test_config={"TESTING": True},
        scraper=lambda: [],
        database_factory=lambda: BrokenDatabase(),
        busy_state=BusyState(),
    )
    client = app.test_client()

    response = client.get("/analysis")
    assert response.status_code == 200
    assert b"Database error" in response.data


@pytest.mark.integration
def test_pull_then_loader_inserts_into_real_database_layer(sample_rows, fake_conn):
    """The default loader path (create schema + insert) works through the app."""
    # uses the real default_loader (loader=None) so that production code path runs
    app = create_app(
        test_config={"TESTING": True},
        scraper=lambda: sample_rows,
        loader=None,
        database_factory=lambda: Database(fake_conn),
        busy_state=BusyState(),
    )
    client = app.test_client()

    response = client.post("/pull-data")
    assert response.get_json()["inserted"] == 3
    assert len(fake_conn.store) == 3
