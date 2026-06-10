"""
test_scrape.py - url building, robots check, and HTML parsing in scrape.py.
Module 4 / JHU Software Concepts in Python

The real scraping uses Selenium and the network, so here we test only the pure
parts and inject a fake page fetcher / robots parser. Marked 'db' because the
scraper feed the data (ETL) subsystem.
"""

import json

import pytest

import scrape


@pytest.mark.db
def test_build_survey_url():
    """Page 1 is the bare survey url, later pages add the page query param."""
    assert scrape.build_survey_url(1) == scrape.SURVEY_URL
    assert "page=3" in scrape.build_survey_url(3)


@pytest.mark.db
def test_check_robots_with_injected_parser():
    """check_robots delegates to the parser's can_fetch (injected here)."""
    class AllowParser:
        def can_fetch(self, agent, url):
            return True

    class DenyParser:
        def can_fetch(self, agent, url):
            return False

    assert scrape.check_robots("http://x/page", parser=AllowParser()) is True
    assert scrape.check_robots("http://x/page", parser=DenyParser()) is False


# a tiny sample results page in the structure the parser expects
SAMPLE_HTML = """
<table>
  <tr class="entry-row">
    <td data-field="program">Computer Science, MIT</td>
    <td data-field="status">Accepted</td>
    <a href="/result/5">view</a>
  </tr>
  <tr class="entry-row">
    <td data-field="program">Physics, Stanford</td>
    <a href="http://example.com/result/6">view</a>
  </tr>
  <tr class="entry-row">
    <td data-field="status">Rejected</td>
  </tr>
</table>
"""


@pytest.mark.db
def test_parse_results_extracts_entries():
    """Two real rows are parsed; the row with no program/url is skipped."""
    entries = scrape.parse_results(SAMPLE_HTML)
    assert len(entries) == 2

    first = entries[0]
    assert first["program"] == "Computer Science, MIT"
    assert first["status"] == "Accepted"
    # relative href gets the base url prepended
    assert first["url"] == scrape.BASE_URL + "/result/5"

    # absolute href is left as-is
    assert entries[1]["url"] == "http://example.com/result/6"


@pytest.mark.db
def test_parse_entry_without_link():
    """A row with no anchor tag just has no url key."""
    from bs4 import BeautifulSoup
    row = BeautifulSoup(
        '<tr class="entry-row"><td data-field="program">CS</td></tr>',
        "html.parser",
    ).find("tr")
    entry = scrape.parse_entry(row)
    assert entry["program"] == "CS"
    assert "url" not in entry


@pytest.mark.db
def test_text_or_none_missing_element():
    """The text helper returns None when given no element."""
    assert scrape._text_or_none(None) is None


@pytest.mark.db
def test_save_data(tmp_path):
    """save_data writes the entries to JSON and returns the path."""
    out = tmp_path / "out.json"
    path = scrape.save_data([{"program": "CS"}], out)
    assert path == out
    assert json.loads(out.read_text(encoding="utf-8"))[0]["program"] == "CS"


@pytest.mark.db
def test_scrape_with_fake_fetcher():
    """scrape() across two pages using a fake fetcher returns combined entries."""
    pages = {
        scrape.build_survey_url(1): SAMPLE_HTML,
        scrape.build_survey_url(2): SAMPLE_HTML,
    }

    def fake_fetcher(url):
        return pages[url]

    results = scrape.scrape(max_pages=2, fetcher=fake_fetcher)
    # 2 valid entries per page across 2 pages
    assert len(results) == 4
