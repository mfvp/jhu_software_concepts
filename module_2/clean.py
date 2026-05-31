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


# TODO: add cleaning functions
if __name__ == "__main__":
    print("clean.py placeholder - cleaning functions coming soon")
