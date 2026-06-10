"""
test_load_data.py - parsing/mapping helpers and the load_entries flow.
Module 4 / JHU Software Concepts in Python

Marked 'db' because loading data is part of the data (ETL + DB) subsystem.
Uses temp files and the fake database so nothing real is touched.
"""

from datetime import date, datetime

import pytest

import load_data as ld


@pytest.mark.db
def test_normalize_status():
    """Status strings normalise to canonical words, unknown passes through."""
    assert ld.normalize_status(None) is None
    assert ld.normalize_status("Accepted on Mar 1") == "Accepted"
    assert ld.normalize_status("Rejected") == "Rejected"
    assert ld.normalize_status("Wait Listed") == "Waitlisted"
    assert ld.normalize_status("Interview") == "Interview"
    assert ld.normalize_status("Deferred") == "Deferred"


@pytest.mark.db
def test_parse_date_formats():
    """Several date formats parse, missing-year uses the current year, junk -> None."""
    assert ld.parse_date(None) is None
    assert ld.parse_date("May 31, 2026") == date(2026, 5, 31)
    assert ld.parse_date("2026-05-31") == date(2026, 5, 31)
    # no year given -> should fill in the current year
    no_year = ld.parse_date("May 31")
    assert no_year.year == datetime.now().year
    assert ld.parse_date("garbage") is None


@pytest.mark.db
def test_parse_float():
    """parse_float converts numbers and returns None on bad input."""
    assert ld.parse_float(None) is None
    assert ld.parse_float("3.5") == 3.5
    assert ld.parse_float("oops") is None


@pytest.mark.db
def test_map_jsonl_entry():
    """JSONL records map onto the row dict, blank comments become None."""
    entry = {
        "program": "CS, MIT", "comments": "", "date_added": "May 1, 2026",
        "url": "http://x/1", "status": "Accepted on May 1", "term": "Fall 2026",
        "US/International": "American", "GPA": "3.9", "GRE": "330",
        "GRE V": "165", "GRE AW": "4.5", "Degree": "PhD",
        "llm-generated-program": "Computer Science",
        "llm-generated-university": "MIT",
    }
    row = ld.map_jsonl_entry(entry)
    assert row["comments"] is None       # "" collapses to None
    assert row["status"] == "Accepted"
    assert row["gpa"] == 3.9
    assert row["llm_generated_university"] == "MIT"


@pytest.mark.db
def test_map_json_entry_term_building():
    """JSON records build the term from semester + year (or None)."""
    with_term = ld.map_json_entry({"semester": "Fall", "year": 2026, "url": "u"})
    assert with_term["term"] == "Fall 2026"

    without = ld.map_json_entry({"url": "u"})
    assert without["term"] is None
    assert without["llm_generated_program"] is None


@pytest.mark.db
def test_read_jsonl(tmp_path):
    """read_jsonl skips blank and malformed lines and parses the good ones."""
    f = tmp_path / "data.jsonl"
    f.write_text('{"a": 1}\n\nnot json\n{"b": 2}\n', encoding="utf-8")
    entries = ld.read_jsonl(f)
    assert entries == [{"a": 1}, {"b": 2}]


@pytest.mark.db
def test_read_jsonl_missing(tmp_path):
    """A missing jsonl file gives an empty list."""
    assert ld.read_jsonl(tmp_path / "nope.jsonl") == []


@pytest.mark.db
def test_read_json(tmp_path):
    """read_json reads a list; a non-list file yields an empty list."""
    good = tmp_path / "good.json"
    good.write_text('[{"x": 1}]', encoding="utf-8")
    assert ld.read_json(good) == [{"x": 1}]

    obj = tmp_path / "obj.json"
    obj.write_text('{"x": 1}', encoding="utf-8")   # not a list
    assert ld.read_json(obj) == []

    assert ld.read_json(tmp_path / "missing.json") == []


@pytest.mark.db
def test_load_entries_jsonl_source(fake_db):
    """load_entries with the jsonl source maps + inserts rows."""
    entries = [{
        "program": "CS", "url": "http://x/1", "status": "Accepted",
        "term": "Fall 2026", "US/International": "American",
    }]
    inserted = ld.load_entries(fake_db, entries, source="jsonl")
    assert inserted == 1
    assert fake_db.count() == 1


@pytest.mark.db
def test_load_entries_json_source(fake_db):
    """load_entries with the json source builds the term and inserts."""
    entries = [{
        "program": "CS", "url": "http://x/2", "status": "Rejected",
        "semester": "Fall", "year": 2026, "applicant_type": "International",
    }]
    inserted = ld.load_entries(fake_db, entries, source="json")
    assert inserted == 1
    row = fake_db.fetch_all()[0]
    assert row["term"] == "Fall 2026"
