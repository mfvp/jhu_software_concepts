# clean.py
# This module handles cleaning the raw scraped data from Grad Cafe.
# The data comes out pretty messy from the scraper so this fixes it up.

import json
import re
import html
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# all the fields we expect in a clean entry
EXPECTED_FIELDS = [
    "program", "program_name", "university", "degree", "status",
    "decision_date", "date_added", "semester", "year", "applicant_type",
    "gpa", "gre_total", "gre_v", "gre_aw", "comments", "url"
]


def load_data(filename="applicant_data.json"):
    """Load raw scraped data from a JSON file."""
    path = Path(__file__).parent / filename
    if not path.exists():
        logger.warning(f"File not found: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"Loaded {len(data)} entries from {path}")
    return data


def save_data(data, filename="applicant_data.json"):
    """Save cleaned data to a JSON file."""
    path = Path(__file__).parent / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(data)} entries to {path}")


def _strip_html(text):
    """
    Remove any leftover HTML tags and decode HTML entities.
    For example: "&amp;" becomes "&", "&lt;" becomes "<", etc.
    Sometimes comments on Grad Cafe have HTML in them.
    """
    if text is None:
        return None
    # remove html tags with regex
    cleaned = re.sub(r'<[^>]+>', '', str(text))
    # decode html entities like &amp; &lt; etc.
    cleaned = html.unescape(cleaned)
    # collapse multiple spaces/newlines into a single space
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else None


def _normalize_none(value):
    """
    Turn "null-like" strings into actual Python None.
    Grad Cafe sometimes has "N/A", "--", or empty strings where data is missing.
    """
    if value is None:
        return None
    text = str(value).strip()
    # list of strings that all mean "no data"
    null_like = {"", "n/a", "na", "none", "--", "-", "null", "undefined", "?", "unknown"}
    if text.lower() in null_like:
        return None
    return text


def _clean_text(text):
    """Strip HTML and handle null values for a generic text field."""
    return _normalize_none(_strip_html(text))


def _clean_status(status):
    """Normalize status strings to consistent values."""
    if not status:
        return None
    s = status.lower().strip()
    if "accept" in s:
        return "Accepted"
    elif "reject" in s:
        return "Rejected"
    elif "waitlist" in s or "wait list" in s:
        return "Waitlisted"
    elif "interview" in s:
        return "Interview"
    return _normalize_none(status)


def _clean_degree(degree):
    """Normalize degree to 'Masters' or 'PhD'."""
    if not degree:
        return None
    d = degree.lower().strip()
    if re.search(r'\bphd\b|ph\.d|doctorate|doctoral', d):
        return "PhD"
    elif re.search(r'\bms\b|m\.s\.|master|meng|mba|mfa|mpa|mpp', d):
        return "Masters"
    return _normalize_none(degree)


def _validate_gpa(gpa):
    """
    Make sure GPA is a valid float in a realistic range (0.0 - 4.5).
    Some schools use a 4.3 scale so we give a bit of slack.
    """
    if gpa is None:
        return None
    try:
        val = float(gpa)
        if 0.0 <= val <= 4.5:
            return round(val, 2)
    except (ValueError, TypeError):
        pass
    return None


def _validate_gre(score, min_val=130, max_val=340):
    """
    Validate a GRE score is within expected range.
    Total score: 260-340. Individual section: 130-170.
    Also handles strings like "GRE 315" or "315/340".
    """
    if score is None:
        return None
    # if it's a string, extract the first number from it
    score_str = str(score)
    num_match = re.search(r'(\d+)', score_str)
    if not num_match:
        return None
    try:
        val = int(num_match.group(1))
        if min_val <= val <= max_val:
            return val
    except (ValueError, TypeError):
        pass
    return None


def _validate_gre_aw(score):
    """
    GRE Analytical Writing scores go 0.0 to 6.0 in 0.5 steps.
    """
    if score is None:
        return None
    try:
        val = float(score)
        if 0.0 <= val <= 6.0:
            return round(val, 1)
    except (ValueError, TypeError):
        pass
    return None


def _ensure_fields(entry):
    """Make sure every entry has all expected fields (set to None if missing)."""
    for field in EXPECTED_FIELDS:
        if field not in entry:
            entry[field] = None
    return entry


def _clean_entry(entry):
    """
    Clean a single applicant entry dictionary.
    Returns a new dict with cleaned values.
    """
    c = {}

    # always keep the original program text! needed for reproducibility
    c["program"] = _clean_text(entry.get("program"))

    # clean all the text fields
    c["program_name"] = _clean_text(entry.get("program_name"))
    c["university"] = _clean_text(entry.get("university"))
    c["comments"] = _clean_text(entry.get("comments"))
    c["url"] = _normalize_none(entry.get("url"))
    c["date_added"] = _normalize_none(entry.get("date_added"))
    c["decision_date"] = _normalize_none(entry.get("decision_date"))

    # normalized fields
    c["status"] = _clean_status(entry.get("status"))
    c["degree"] = _clean_degree(entry.get("degree"))
    c["semester"] = _normalize_none(entry.get("semester"))

    # year should be an integer
    year = entry.get("year")
    if year is not None:
        try:
            y = int(year)
            c["year"] = y if 2000 <= y <= 2035 else None
        except (ValueError, TypeError):
            c["year"] = None
    else:
        c["year"] = None

    # applicant type
    at = _normalize_none(entry.get("applicant_type"))
    if at:
        at_l = at.lower()
        if "international" in at_l:
            c["applicant_type"] = "International"
        elif "american" in at_l or "domestic" in at_l or "u.s" in at_l:
            c["applicant_type"] = "American"
        else:
            c["applicant_type"] = at
    else:
        c["applicant_type"] = None

    # numeric scores - validated with range checks
    c["gpa"] = _validate_gpa(entry.get("gpa"))
    c["gre_total"] = _validate_gre(entry.get("gre_total"), min_val=260, max_val=340)
    c["gre_v"] = _validate_gre(entry.get("gre_v"), min_val=130, max_val=170)
    c["gre_aw"] = _validate_gre_aw(entry.get("gre_aw"))

    return _ensure_fields(c)


def clean_data(data):
    """
    Clean all entries in the dataset.
    Returns a new list with cleaned data, skipping completely empty entries.
    """
    logger.info(f"Cleaning {len(data)} entries...")
    cleaned = []
    skipped = 0
    for i, entry in enumerate(data):
        try:
            c = _clean_entry(entry)
            # skip entries with absolutely no useful data
            if not c.get("program") and not c.get("url"):
                skipped += 1
                continue
            cleaned.append(c)
        except Exception as e:
            logger.warning(f"Error cleaning entry {i}: {e}")
            skipped += 1
    logger.info(f"Done. Kept {len(cleaned)} entries, skipped {skipped}.")
    return cleaned


def run_cleaning_pipeline(input_file="applicant_data.json", output_file="applicant_data.json"):
    """
    Run the full cleaning pipeline on a JSON file.
    Loads raw scraped data, cleans it, and saves the result.
    """
    raw = load_data(input_file)
    if not raw:
        logger.error("No data loaded - is the input file correct?")
        return []
    cleaned = clean_data(raw)
    save_data(cleaned, output_file)
    return cleaned


if __name__ == "__main__":
    print("Running cleaning pipeline...")
    result = run_cleaning_pipeline()
    print(f"Done! Cleaned {len(result)} entries.")
