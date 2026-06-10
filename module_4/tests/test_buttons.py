"""
test_buttons.py - Pull Data / Update Analysis button behaviour and busy gating.
Module 4 / JHU Software Concepts in Python

Uses Flask's test client (no real browser clicking) and the injected fake
scraper/loader so nothing touch the network or a real DB. Busy state is set
through the injected BusyState object instead of any sleep().
"""

import pytest

from flask_app import BusyState, create_app


@pytest.mark.buttons
def test_pull_data_returns_ok_when_not_busy(client):
    """POST /pull-data should return 200 with ok=true when nothing is running."""
    response = client.post("/pull-data")
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True


@pytest.mark.buttons
def test_pull_data_triggers_loader(app_factory, fake_conn):
    """The pull should actually run the loader and write the scraped rows."""
    make_app, _ = app_factory
    app = make_app()
    client = app.test_client()

    response = client.post("/pull-data")
    body = response.get_json()

    # the fake scraper returns 3 rows, so 3 rows should have been inserted
    assert body["inserted"] == 3
    assert len(fake_conn.store) == 3


@pytest.mark.buttons
def test_update_analysis_returns_200_when_not_busy(client):
    """POST /update-analysis should return 200 when no pull is running."""
    response = client.post("/update-analysis")
    assert response.status_code == 200
    assert response.get_json()["ok"] is True


@pytest.mark.buttons
def test_update_analysis_blocked_when_busy(app_factory):
    """When a pull is in progress, /update-analysis returns 409 with busy=true."""
    make_app, busy = app_factory
    busy.begin()  # pretend a pull is already running
    app = make_app(busy_state=busy)
    client = app.test_client()

    response = client.post("/update-analysis")
    assert response.status_code == 409
    assert response.get_json()["busy"] is True


@pytest.mark.buttons
def test_pull_data_blocked_when_busy(app_factory, fake_conn):
    """When busy, /pull-data is also gated (409) and performs no insert."""
    make_app, busy = app_factory
    busy.begin()
    app = make_app(busy_state=busy)
    client = app.test_client()

    response = client.post("/pull-data")
    assert response.status_code == 409
    assert response.get_json()["busy"] is True
    # nothing should have been written while busy
    assert len(fake_conn.store) == 0


@pytest.mark.buttons
def test_pull_data_error_path_returns_500_no_writes(fake_conn):
    """A scraper failure should yield a non-200 and leave no partial rows."""
    from db import Database

    def boom():
        raise RuntimeError("scraper exploded")

    busy = BusyState()
    app = create_app(
        test_config={"TESTING": True},
        scraper=boom,
        database_factory=lambda: Database(fake_conn),
        busy_state=busy,
    )
    client = app.test_client()

    response = client.post("/pull-data")
    assert response.status_code == 500
    assert response.get_json()["ok"] is False
    # no rows written, and the busy flag is released so the app isn't stuck
    assert len(fake_conn.store) == 0
    assert busy.is_busy() is False


@pytest.mark.buttons
def test_busy_state_helpers():
    """Small sanity check on the BusyState object the app uses for gating."""
    busy = BusyState()
    assert busy.is_busy() is False
    busy.begin()
    assert busy.is_busy() is True
    busy.end()
    assert busy.is_busy() is False
