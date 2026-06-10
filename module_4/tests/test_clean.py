"""
test_clean.py - cleaning/validation helpers in clean.py.
Module 4 / JHU Software Concepts in Python

These are plain data-cleaning functions so theyre easy to test with little
sample inputs. Marked 'db' because cleaning is part of the data (ETL) subsystem.
"""

import json
from pathlib import Path

import pytest

import clean


@pytest.mark.db
def test_strip_html():
    """HTML tags are removed, entities decoded, empty results become None."""
    assert clean.strip_html(None) is None
    assert clean.strip_html("<b>Hello</b> &amp; bye") == "Hello & bye"
    assert clean.strip_html("<p>   </p>") is None


@pytest.mark.db
def test_normalize_none():
    """Null-like strings collapse to None, real text is kept."""
    assert clean.normalize_none(None) is None
    assert clean.normalize_none("N/A") is None
    assert clean.normalize_none("Stanford") == "Stanford"


@pytest.mark.db
def test_clean_status_variants():
    """Every status keyword maps to its canonical word."""
    assert clean.clean_status(None) is None
    assert clean.clean_status("Accepted on 1 Mar") == "Accepted"
    assert clean.clean_status("Rejected") == "Rejected"
    assert clean.clean_status("Wait listed") == "Waitlisted"
    assert clean.clean_status("Interview scheduled") == "Interview"
    assert clean.clean_status("Other") == "Other"


@pytest.mark.db
def test_clean_degree_variants():
    """Degrees normalise to Masters / PhD, unknown text passes through."""
    assert clean.clean_degree(None) is None
    assert clean.clean_degree("PhD") == "PhD"
    assert clean.clean_degree("MS in CS") == "Masters"
    assert clean.clean_degree("Certificate") == "Certificate"


@pytest.mark.db
def test_validate_gpa():
    """GPA only kept when it parses and sits in a believable range."""
    assert clean.validate_gpa(None) is None
    assert clean.validate_gpa("not a number") is None
    assert clean.validate_gpa(5.0) is None       # too high
    assert clean.validate_gpa(3.456) == 3.46


@pytest.mark.db
def test_validate_gre():
    """GRE pulls the first number and range-checks it."""
    assert clean.validate_gre(None) is None
    assert clean.validate_gre("no digits") is None
    assert clean.validate_gre("315") == 315
    assert clean.validate_gre("999") is None     # out of range


@pytest.mark.db
def test_validate_gre_aw():
    """Analytical writing kept only in the 0-6 range."""
    assert clean.validate_gre_aw(None) is None
    assert clean.validate_gre_aw("bad") is None
    assert clean.validate_gre_aw(7.0) is None
    assert clean.validate_gre_aw(4.5) == 4.5


@pytest.mark.db
def test_clean_year():
    """Year parsed to int and sanity-checked."""
    assert clean.clean_year(None) is None
    assert clean.clean_year("abc") is None
    assert clean.clean_year(1999) is None
    assert clean.clean_year("2026") == 2026


@pytest.mark.db
def test_clean_applicant_type():
    """Applicant type normalises to International / American or passes through."""
    assert clean.clean_applicant_type(None) is None
    assert clean.clean_applicant_type("International") == "International"
    assert clean.clean_applicant_type("Domestic") == "American"
    assert clean.clean_applicant_type("Martian") == "Martian"


@pytest.mark.db
def test_clean_entry_fills_all_fields():
    """A cleaned entry has every expected field present."""
    raw = {"program": "<b>CS</b>", "status": "Accepted", "gpa": "3.7"}
    cleaned = clean.clean_entry(raw)
    for field in clean.EXPECTED_FIELDS:
        assert field in cleaned
    assert cleaned["program"] == "CS"
    assert cleaned["gpa"] == 3.7


@pytest.mark.db
def test_clean_data_drops_empty_entries():
    """Entries with no program and no url are dropped."""
    data = [
        {"program": "CS", "url": "http://x/1"},
        {"comments": "nothing useful"},   # no program, no url -> dropped
    ]
    cleaned = clean.clean_data(data)
    assert len(cleaned) == 1


@pytest.mark.db
def test_load_save_pipeline_round_trip():
    """load_data / save_data / run_cleaning_pipeline work on a real temp file."""
    src_dir = Path(clean.__file__).parent
    tmp = src_dir / "tmp_clean_test.json"
    raw = [{"program": "Physics", "url": "http://x/9", "status": "Accepted"}]
    tmp.write_text(json.dumps(raw), encoding="utf-8")
    try:
        loaded = clean.load_data("tmp_clean_test.json")
        assert loaded == raw

        result = clean.run_cleaning_pipeline("tmp_clean_test.json", "tmp_clean_test.json")
        assert len(result) == 1
        # the file was rewritten with the cleaned data
        written = json.loads(tmp.read_text(encoding="utf-8"))
        assert written[0]["program"] == "Physics"
    finally:
        tmp.unlink()


@pytest.mark.db
def test_load_data_missing_file_returns_empty():
    """Missing input file gives an empty list, not an error."""
    assert clean.load_data("definitely_not_here.json") == []


@pytest.mark.db
def test_pipeline_empty_when_no_data():
    """run_cleaning_pipeline returns [] when there's nothing to load."""
    assert clean.run_cleaning_pipeline("definitely_not_here.json") == []
