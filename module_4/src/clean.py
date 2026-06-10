"""
clean.py - Data cleaning for the scraped Grad Cafe data.
Module 4 / JHU Software Concepts in Python

Takes the messy records that come out of scrape.py and tidies every field:
strips HTML, normalizes "N/A" style values to None, and validates the numeric
scores. In module 3 this ran on a process pool, but that was hard to test and
overkill for the data sizes hear, so module 4 cleans the entries sequentially.
"""

import html
import json
import re
from pathlib import Path


# every field we expect a clean entry to have
EXPECTED_FIELDS = [
    "program", "program_name", "university", "comments", "date_added",
    "url", "status", "decision_date", "semester", "year",
    "applicant_type", "gre_total", "gre_v", "degree", "gpa", "gre_aw",
]

# strings that really mean "no data was provided"
NULL_LIKE = {"", "n/a", "na", "none", "--", "-", "null", "undefined", "?", "unknown"}


def load_data(filename="applicant_data.json"):
    """Load raw scraped data from a JSON file in this folder."""
    path = Path(__file__).parent / filename
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data, filename="applicant_data.json"):
    """Save cleaned data back out to a JSON file."""
    path = Path(__file__).parent / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def strip_html(text):
    """Remove leftover HTML tags, decode entities, and collapse whitespace."""
    if text is None:
        return None
    cleaned = re.sub(r"<[^>]+>", "", str(text))
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else None


def normalize_none(value):
    """Turn 'null-like' strings ('N/A', '--', etc.) into a real None."""
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in NULL_LIKE:
        return None
    return text


def clean_text(text):
    """Strip HTML and normalize null-ish values for a plain text field."""
    return normalize_none(strip_html(text))


def clean_status(status):
    """Normalize a status string to one of our known status words."""
    if not status:
        return None
    s = status.lower().strip()
    if "accept" in s:
        return "Accepted"
    if "reject" in s:
        return "Rejected"
    if "waitlist" in s or "wait list" in s:
        return "Waitlisted"
    if "interview" in s:
        return "Interview"
    return normalize_none(status)


def clean_degree(degree):
    """Normalize a degree string to 'Masters' or 'PhD' when we can tell."""
    if not degree:
        return None
    d = degree.lower().strip()
    if re.search(r"\bphd\b|ph\.d|doctorate|doctoral", d):
        return "PhD"
    if re.search(r"\bms\b|m\.s\.|master|meng|mba|mfa|mpa|mpp", d):
        return "Masters"
    return normalize_none(degree)


def validate_gpa(gpa):
    """Keep GPA only if it's a real number in a believable 0.0-4.5 range."""
    if gpa is None:
        return None
    try:
        val = float(gpa)
    except (ValueError, TypeError):
        return None
    if 0.0 <= val <= 4.5:
        return round(val, 2)
    return None


def validate_gre(score, min_val=130, max_val=340):
    """Pull the first number out of a GRE value and keep it if it's in range."""
    if score is None:
        return None
    match = re.search(r"(\d+)", str(score))
    if not match:
        return None
    try:
        val = int(match.group(1))
    except (ValueError, TypeError):  # pragma: no cover - regex already guarantees digits
        return None
    if min_val <= val <= max_val:
        return val
    return None


def validate_gre_aw(score):
    """GRE Analytical Writing is 0.0-6.0 in half point steps."""
    if score is None:
        return None
    try:
        val = float(score)
    except (ValueError, TypeError):
        return None
    if 0.0 <= val <= 6.0:
        return round(val, 1)
    return None


def ensure_fields(entry):
    """Make sure every expected field exists, defaulting missing ones to None."""
    for field in EXPECTED_FIELDS:
        entry.setdefault(field, None)
    return entry


def clean_year(year):
    """Parse the year into an int and sanity-check it's a realistic application year."""
    if year is None:
        return None
    try:
        y = int(year)
    except (ValueError, TypeError):
        return None
    return y if 2000 <= y <= 2035 else None


def clean_applicant_type(value):
    """Normalize the applicant type to 'International' or 'American' when possible."""
    at = normalize_none(value)
    if not at:
        return None
    at_l = at.lower()
    if "international" in at_l:
        return "International"
    if "american" in at_l or "domestic" in at_l or "u.s" in at_l:
        return "American"
    return at


def clean_entry(entry):
    """Clean a single applicant dict and return a brand new cleaned dict."""
    c = {
        "program": clean_text(entry.get("program")),
        "program_name": clean_text(entry.get("program_name")),
        "university": clean_text(entry.get("university")),
        "comments": clean_text(entry.get("comments")),
        "date_added": normalize_none(entry.get("date_added")),
        "url": normalize_none(entry.get("url")),
        "status": clean_status(entry.get("status")),
        "decision_date": normalize_none(entry.get("decision_date")),
        "semester": normalize_none(entry.get("semester")),
        "year": clean_year(entry.get("year")),
        "applicant_type": clean_applicant_type(entry.get("applicant_type")),
        "gre_total": validate_gre(entry.get("gre_total"), min_val=260, max_val=340),
        "gre_v": validate_gre(entry.get("gre_v"), min_val=130, max_val=170),
        "degree": clean_degree(entry.get("degree")),
        "gpa": validate_gpa(entry.get("gpa")),
        "gre_aw": validate_gre_aw(entry.get("gre_aw")),
    }
    return ensure_fields(c)


def clean_data(data):
    """
    Clean every entry in the dataset. Entries that end up with no program AND no
    url are dropped because there's nothing useful to keep.
    """
    cleaned = []
    for entry in data:
        result = clean_entry(entry)
        if not result.get("program") and not result.get("url"):
            continue
        cleaned.append(result)
    return cleaned


def run_cleaning_pipeline(input_file="applicant_data.json", output_file="applicant_data.json"):
    """Load raw data, clean it, save it back, and return the cleaned list."""
    raw = load_data(input_file)
    if not raw:
        return []
    cleaned = clean_data(raw)
    save_data(cleaned, output_file)
    return cleaned


if __name__ == "__main__":  # pragma: no cover
    result = run_cleaning_pipeline()
    print("Cleaned {} entries".format(len(result)))
