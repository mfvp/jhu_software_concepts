"""
test_analysis_format.py - analysis labels and percentage formatting.
Module 4 / JHU Software Concepts in Python

Two things matter here: every analysis item is labelled with "Answer:", and any
percentage shown on the page is formated with exactly two decimal places. A
regex is used to check the two-decimal rule. Also covers the pure analysis
helper functions directly so all of query_data is exercised.
"""

import re

import pytest

import query_data as qd

# matches a percentage with exactly two decimals, e.g. 39.28% or 0.00%
PERCENT_RE = re.compile(r"\d+\.\d{2}%")


@pytest.mark.analysis
def test_rendered_answers_are_labeled(client):
    """After a pull, the page should label analysis items with 'Answer:'."""
    client.post("/pull-data")
    html = client.get("/analysis").data.decode("utf-8")
    # there are several Q&A blocks, so we expect more than one Answer label
    assert html.count("Answer:") >= 2


@pytest.mark.analysis
def test_percentages_have_two_decimals(client):
    """Every percentage rendered on the page must have two decimal places."""
    client.post("/pull-data")
    html = client.get("/analysis").data.decode("utf-8")

    found = PERCENT_RE.findall(html)
    assert found, "expected at least one percentage on the page"
    # every percent-looking token must match the strict two-decimal pattern
    loose = re.findall(r"\d+\.\d+%", html)
    assert found == loose


@pytest.mark.analysis
def test_format_percent_two_decimals():
    """format_percent always gives two decimals."""
    assert qd.format_percent(39.2) == "39.20%"
    assert qd.format_percent(0) == "0.00%"
    assert PERCENT_RE.fullmatch(qd.format_percent(12.5))


@pytest.mark.analysis
def test_format_number_handles_none():
    """format_number gives N/A for None and two decimals otherwise."""
    assert qd.format_number(None) == "N/A"
    assert qd.format_number(3.5) == "3.50"


@pytest.mark.analysis
def test_percentage_handles_zero_whole():
    """Dividing by zero entries should give 0.0, not blow up."""
    assert qd.percentage(5, 0) == 0.0
    assert qd.percentage(1, 4) == 25.0


@pytest.mark.analysis
def test_average_helpers(sample_rows):
    """Spot-check the averaging and counting helpers on the sample data."""
    assert qd.count_fall_2026(sample_rows) == 3
    assert qd.percent_international(sample_rows) == pytest.approx(33.33)
    scores = qd.average_scores(sample_rows)
    assert scores["gpa"] == pytest.approx((3.9 + 3.6 + 3.8) / 3)
    assert qd.average_gpa_american_fall(sample_rows) == pytest.approx((3.9 + 3.8) / 2)
    assert qd.percent_acceptances_fall(sample_rows) == pytest.approx(66.67)
    assert qd.average_gpa_accept_fall(sample_rows) == pytest.approx((3.9 + 3.8) / 2)


@pytest.mark.analysis
def test_avg_empty_returns_none():
    """Averaging a list with no numbers returns None."""
    assert qd._avg([None, None]) is None


@pytest.mark.analysis
def test_contains_handles_none():
    """_contains is safe when the text is missing (e.g. a null program field)."""
    assert qd._contains(None, "stanford") is False
    assert qd._contains("Stanford University", "stanford") is True


@pytest.mark.analysis
def test_jhu_and_top_school_counts(sample_rows):
    """JHU masters CS count and the top-school PhD CS counts (raw + LLM)."""
    assert qd.count_jhu_masters_cs(sample_rows) == 1
    assert qd.count_top_school_phd_raw(sample_rows) == 1
    assert qd.count_top_school_phd_llm(sample_rows) == 1


@pytest.mark.analysis
def test_top_school_branches():
    """Exercise every early-exit branch of the top-school helper."""
    rows = [
        # wrong term -> skipped
        {"term": "Fall 2025", "status": "Accepted", "degree": "PhD",
         "program": "Computer Science, MIT"},
        # not an acceptance -> skipped
        {"term": "Fall 2026", "status": "Rejected", "degree": "PhD",
         "program": "Computer Science, MIT"},
        # program isn't CS -> skipped
        {"term": "Fall 2026", "status": "Accepted", "degree": "PhD",
         "program": "Biology, MIT"},
        # not a top school -> skipped
        {"term": "Fall 2026", "status": "Accepted", "degree": "PhD",
         "program": "Computer Science, Tiny College"},
        # the one that counts
        {"term": "Fall 2026", "status": "Accepted", "degree": "PhD",
         "program": "Computer Science, Stanford"},
    ]
    assert qd.count_top_school_phd_raw(rows) == 1


@pytest.mark.analysis
def test_top_universities_orders_and_limits():
    """top_universities counts, orders by frequency, ignores nulls, and limits."""
    rows = [
        {"llm_generated_university": "A"},
        {"llm_generated_university": "A"},
        {"llm_generated_university": "B"},
        {"llm_generated_university": None},  # ignored
    ]
    result = qd.top_universities(rows, limit=1)
    assert result == [("A", 2)]


@pytest.mark.analysis
def test_lowest_acceptance_rates():
    """lowest_acceptance_rates respects the min-entries threshold and sorts ascending."""
    rows = []
    # University A: 2 entries, 1 accepted -> 50%
    rows += [{"llm_generated_university": "A", "status": "Accepted"},
             {"llm_generated_university": "A", "status": "Rejected"}]
    # University B: 2 entries, 0 accepted -> 0%
    rows += [{"llm_generated_university": "B", "status": "Rejected"},
             {"llm_generated_university": "B", "status": "Rejected"}]
    # a null university is ignored
    rows += [{"llm_generated_university": None, "status": "Accepted"}]

    result = qd.lowest_acceptance_rates(rows, limit=10, min_entries=2)
    assert result[0] == ("B", 0.0, 2)   # lowest rate first
    assert ("A", 50.0, 2) in result


@pytest.mark.analysis
def test_get_analysis_and_query_keys(fake_db, sample_rows):
    """get_analysis returns the expected top-level keys, query returns row dicts."""
    fake_db.insert_applicants(sample_rows)
    analysis = qd.get_analysis(fake_db)
    assert set(analysis.keys()) == {"total", "items", "top_universities", "lowest_acceptance"}
    assert analysis["total"] == 3

    rows = qd.query_applicants(fake_db)
    assert isinstance(rows[0], dict)
