"""
test_flask_page.py - Flask app factory and page rendering tests.
Module 4 / JHU Software Concepts in Python

Checks the create_app factory builds a testable app, that every route exist,
and that GET /analysis renders all the required pieces (title, both buttons,
and Answer labels).
"""

import pytest
from bs4 import BeautifulSoup

from flask_app import create_app


@pytest.mark.web
def test_create_app_returns_testable_app(app_factory):
    """The factory should build a Flask app we can put into testing mode."""
    make_app, _ = app_factory
    app = make_app({"TESTING": True})
    assert app.testing is True


@pytest.mark.web
def test_create_app_with_defaults_has_routes():
    """create_app() with no injected deps still wires up all the routes."""
    # we don't call the routes here (that would need a real DB) - just check
    # the url map so the default wiring lines are exercised.
    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/" in rules
    assert "/analysis" in rules
    assert "/pull-data" in rules
    assert "/update-analysis" in rules


@pytest.mark.web
def test_analysis_route_status_200(client):
    """GET /analysis should load with status 200."""
    response = client.get("/analysis")
    assert response.status_code == 200


@pytest.mark.web
def test_index_route_also_renders(client):
    """The bare '/' route should render the same page."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Analysis" in response.data


@pytest.mark.web
def test_page_has_both_buttons(client):
    """The page must contain the Pull Data and Update Analysis buttons."""
    html = client.get("/analysis").data.decode("utf-8")
    soup = BeautifulSoup(html, "html.parser")

    pull_btn = soup.find(attrs={"data-testid": "pull-data-btn"})
    update_btn = soup.find(attrs={"data-testid": "update-analysis-btn"})

    assert pull_btn is not None
    assert update_btn is not None
    assert "Pull Data" in pull_btn.get_text()
    assert "Update Analysis" in update_btn.get_text()


@pytest.mark.web
def test_page_contains_analysis_and_answer(client):
    """Page text must include 'Analysis' and at least one 'Answer:' label."""
    html = client.get("/analysis").data.decode("utf-8")
    assert "Analysis" in html
    assert "Answer:" in html
