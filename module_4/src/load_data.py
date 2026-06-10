"""
load_data.py - Load Grad Cafe applicant data into the database.
Module 4 / JHU Software Concepts in Python

Reads eiter the LLM enriched JSONL file (from module 2) or the freshly scraped
applicant_data.json, turns each record into a normalized row dict, and hands the
rows to the Database layer to insert.

The mapping/normalizing functions are kept separate from the database so they can
be tested on their own with no postgres connection.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from db import Database, connect


MODULE_DIR = Path(__file__).parent
JSONL_FILE = MODULE_DIR / "llm_extend_applicant_data_run.jsonl"
JSON_FILE = MODULE_DIR / "applicant_data.json"


def normalize_status(status_text):
    """
    Grad Cafe stores statuses like 'Accepted on May 31'. We just want the clean
    status word: Accepted, Rejected, Waitlisted or Interview.
    """
    if not status_text:
        return None
    s = status_text.lower().strip()
    if "accept" in s:
        return "Accepted"
    if "reject" in s:
        return "Rejected"
    if "waitlist" in s or "wait list" in s or "wait listed" in s:
        return "Waitlisted"
    if "interview" in s:
        return "Interview"
    return status_text.strip()


def parse_date(date_str):
    """
    Parse the various date formats grad cafe uses into a python date.
    Returns None if none of the formats match so we don't crash on bad data.
    """
    if not date_str:
        return None

    cleaned = str(date_str).strip()
    formats = [
        "%B %d, %Y",   # May 31, 2026
        "%b %d, %Y",   # abbreviated month
        "%B %d",       # no year
        "%b %d",
        "%Y-%m-%d",    # iso, just in case
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            # strptime uses 1900 when no year was given - swap in the current year
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
            return dt.date()
        except ValueError:
            continue
    return None


def parse_float(val):
    """Convert a value to float, or None when it can't be parsed."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def map_jsonl_entry(entry):
    """Map one record from the LLM enriched JSONL format into a row dict."""
    comments = entry.get("comments") or None
    if comments == "":
        comments = None
    return {
        "program": entry.get("program"),
        "comments": comments,
        "date_added": parse_date(entry.get("date_added")),
        "url": entry.get("url"),
        "status": normalize_status(entry.get("status")),
        "term": entry.get("term"),
        "us_or_international": entry.get("US/International"),
        "gpa": parse_float(entry.get("GPA")),
        "gre": parse_float(entry.get("GRE")),
        "gre_v": parse_float(entry.get("GRE V")),
        "gre_aw": parse_float(entry.get("GRE AW")),
        "degree": entry.get("Degree"),
        "llm_generated_program": entry.get("llm-generated-program"),
        "llm_generated_university": entry.get("llm-generated-university"),
    }


def map_json_entry(entry):
    """
    Map one record from the scraper/cleaner JSON format into a row dict.
    These rows have no LLM fields yet so those stay None.
    """
    semester = entry.get("semester")
    year = entry.get("year")
    term = "{} {}".format(semester, year) if semester and year else None
    return {
        "program": entry.get("program"),
        "comments": entry.get("comments") or None,
        "date_added": parse_date(entry.get("date_added")),
        "url": entry.get("url"),
        "status": normalize_status(entry.get("status")),
        "term": term,
        "us_or_international": entry.get("applicant_type"),
        "gpa": parse_float(entry.get("gpa")),
        "gre": parse_float(entry.get("gre_total")),
        "gre_v": parse_float(entry.get("gre_v")),
        "gre_aw": parse_float(entry.get("gre_aw")),
        "degree": entry.get("degree"),
        "llm_generated_program": None,
        "llm_generated_university": None,
    }


def read_jsonl(filepath):
    """Read a JSONL file (one json object per line) into a list of dicts."""
    entries = []
    path = Path(filepath)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                # skip the occasional malformed line rather than crashing
                continue
    return entries


def read_json(filepath):
    """Read a regular JSON array file into a list of dicts."""
    path = Path(filepath)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def load_entries(database, entries, source="jsonl"):
    """
    Map raw entries with the right mapper and insert them into the database.
    source picks which format the entries are in. Returns the number inserted.
    """
    if source == "json":
        rows = [map_json_entry(e) for e in entries]
    else:
        rows = [map_jsonl_entry(e) for e in entries]
    database.create_schema()
    return database.insert_applicants(rows)


def main(load_new=False):  # pragma: no cover - real DB load, exercised manually
    """Connect to postgres and load either the scraped json or the enriched jsonl."""
    database = Database(connect())
    if load_new:
        entries = read_json(JSON_FILE)
        inserted = load_entries(database, entries, source="json")
    else:
        entries = read_jsonl(JSONL_FILE)
        inserted = load_entries(database, entries, source="jsonl")
    print("Inserted {} new rows".format(inserted))
    database.close()


if __name__ == "__main__":  # pragma: no cover
    main(load_new="--new" in sys.argv)
