# scrape.py
# This is my web scraper for Grad Cafe
# I'm still learning Python so bear with me on the comments :)
# I'm using urllib to check/build URLs and selenium to load the JS-rendered pages

import urllib.robotparser
import urllib.parse
import urllib.request
import logging
import time
import random

# selenium for rendering the javascript on the page
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# beautifulsoup for actually parsing the html content
from bs4 import BeautifulSoup
import re
import json
from pathlib import Path

# the base url and survey url for grad cafe
BASE_URL = "https://www.thegradcafe.com"
SURVEY_URL = "https://www.thegradcafe.com/survey/"
ROBOTS_URL = "https://www.thegradcafe.com/robots.txt"

# set up logging so I can see what is happening when the scraper runs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _check_robots_txt(url):
    """
    Check if we are allowed to scrape a url based on robots.txt.
    We HAVE to do this before scraping - it's the polite thing to do
    and it's also required for the assignment.
    Returns True if we can scrape, False if we cannot.
    """
    try:
        # use urllib's robotparser to read the robots.txt file
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(ROBOTS_URL)
        rp.read()

        # check if we (as a generic crawler) are allowed to fetch this url
        can_fetch = rp.can_fetch("*", url)

        if can_fetch:
            logger.info(f"robots.txt: scraping is ALLOWED for {url}")
        else:
            logger.warning(f"robots.txt: scraping is NOT allowed for {url}")

        return can_fetch

    except Exception as e:
        # if we can't read robots.txt for some reason, play it safe and don't scrape
        logger.error(f"Could not read robots.txt from {ROBOTS_URL}: {e}")
        return False


# how long to wait between requests in seconds - we want to be polite!
MIN_DELAY = 2.5
MAX_DELAY = 5.5


def _setup_driver():
    """
    Set up a headless Chrome browser for selenium.
    Headless means it runs in the background with no window - perfect for scraping.
    Selenium Manager (included in selenium 4+) handles downloading chromedriver automatically.
    """
    options = Options()

    # run in the background with no visible browser window
    options.add_argument("--headless=new")

    # these are needed to avoid some common errors
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    # set a user agent so we look like a normal browser and not a bot
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # selenium manager automatically downloads the correct chromedriver
    driver = webdriver.Chrome(options=options)
    logger.info("Chrome driver initialized (headless mode)")
    return driver


def _normalize_status(status_text):
    """
    Convert any status variation into a clean consistent value.
    Grad Cafe statuses can be like "Accepted on 15 Feb" or just "Accepted".
    We want to return: Accepted, Rejected, Waitlisted, Interview, or Other
    """
    if not status_text:
        return None, None  # return (status, decision_date)

    s = status_text.strip()
    s_lower = s.lower()

    # try to pull out a date if it's embedded in the status
    # format example: "Accepted on 15 Feb" or "Rejected on 3 Jan 2024"
    date_match = re.search(
        r'(?:on\s+)?(\d{1,2}\s+\w+(?:\s+\d{4})?|\w+\s+\d{1,2}(?:,\s*\d{4})?)',
        s, re.IGNORECASE
    )
    decision_date = date_match.group(1).strip() if date_match else None

    # figure out which status category it falls into
    if "accept" in s_lower:
        return "Accepted", decision_date
    elif "reject" in s_lower:
        return "Rejected", decision_date
    elif "waitlist" in s_lower or "wait list" in s_lower or "wait-list" in s_lower:
        return "Waitlisted", decision_date
    elif "interview" in s_lower:
        return "Interview", decision_date
    else:
        return s, decision_date


def _parse_season(term_text):
    """
    Parse a term string like "Fall 2024" into (semester, year).
    Returns a tuple of (semester_string, year_int) or (None, None).
    """
    if not term_text:
        return None, None

    text = term_text.strip()

    # find the 4-digit year
    year_match = re.search(r'\b(20\d{2})\b', text)
    year = int(year_match.group(1)) if year_match else None

    # figure out the semester from keywords
    t = text.lower()
    if "fall" in t or re.search(r'\bf\d{2}\b', t):
        semester = "Fall"
    elif "spring" in t or re.search(r'\bsp\d{2}\b', t):
        semester = "Spring"
    elif "summer" in t or re.search(r'\bsu\d{2}\b', t):
        semester = "Summer"
    elif "winter" in t:
        semester = "Winter"
    else:
        # just take the first word if we can't figure it out
        semester = text.split()[0].capitalize() if text.split() else None

    return semester, year


def _parse_gpa(gpa_text):
    """
    Parse GPA value from a string like "GPA 3.88" or just "3.88".
    Returns a float or None if it can't be parsed.
    """
    if not gpa_text:
        return None

    # find a decimal number in the string
    match = re.search(r'(\d+\.\d+|\d+)', str(gpa_text))
    if match:
        val = float(match.group(1))
        # GPA should be between 0.0 and 4.5 (some schools use 4.0 scale, some 4.3)
        if 0.0 <= val <= 4.5:
            return round(val, 2)
    return None


def _parse_gre_score(score_text, is_aw=False):
    """
    Parse a GRE score from text.
    Regular GRE: total 260-340, verbal/quant 130-170
    Analytical Writing (AW): 0.0 to 6.0
    """
    if not score_text:
        return None

    match = re.search(r'(\d+\.?\d*)', str(score_text))
    if not match:
        return None

    val = float(match.group(1))

    if is_aw:
        # AW score range
        if 0.0 <= val <= 6.0:
            return round(val, 1)
    else:
        val = int(val)
        # valid GRE score ranges
        if 130 <= val <= 170:
            return val  # individual section score
        elif 260 <= val <= 340:
            return val  # combined score

    return None


def _split_program_university(raw_program):
    """
    Try to separate the program name from the university name.
    Grad Cafe often has both in one field like "Computer Science, MIT".
    This is tricky because there's no consistent separator.
    Returns (program_name, university_name).
    """
    if not raw_program:
        return None, None

    text = raw_program.strip().strip(",")

    # check for " at " pattern first (e.g., "Computer Science at MIT")
    at_split = re.split(r'\s+at\s+', text, maxsplit=1, flags=re.IGNORECASE)
    if len(at_split) == 2:
        return at_split[0].strip(), at_split[1].strip()

    # try splitting on the LAST comma
    # this handles "Computer Science, Machine Learning, MIT" -> program="Computer Science, Machine Learning", uni="MIT"
    last_comma = text.rfind(",")
    if last_comma > 0:
        prog_part = text[:last_comma].strip()
        uni_part = text[last_comma + 1:].strip()
        # if the university part looks like a university name (has uppercase), use it
        if uni_part and len(uni_part) > 2:
            return prog_part, uni_part

    # if we can't split it, return the whole thing as program and unknown university
    return text, None


def _parse_entry(row_elem, col_headers=None):
    """
    Parse one applicant row from BeautifulSoup into a dictionary.
    col_headers is an optional list of column names to help us identify fields.

    Returns a dict with all the fields we want to extract.
    """
    # start with all fields set to None so we always have consistent keys
    entry = {
        "program": None,           # raw original program text (keep for traceability!)
        "program_name": None,      # just the program part
        "university": None,        # just the university part
        "degree": None,            # Masters or PhD
        "status": None,            # Accepted/Rejected/Waitlisted/Interview/Other
        "decision_date": None,     # date of the decision
        "date_added": None,        # when the entry was added to grad cafe
        "semester": None,          # Fall/Spring/Summer/Winter
        "year": None,              # year (e.g., 2024)
        "applicant_type": None,    # International or American
        "gpa": None,
        "gre_total": None,
        "gre_v": None,
        "gre_aw": None,
        "comments": None,
        "url": None,
    }

    try:
        cells = row_elem.find_all(["td", "th"])

        # if we have column headers, use them to identify which cell is which
        if col_headers and len(col_headers) >= len(cells):
            cell_map = {col_headers[i].lower(): cells[i] for i in range(len(cells))}
        else:
            # no headers, we'll try to figure it out from content
            cell_map = {}

        # --- try to get the result url from any link in the row ---
        link = row_elem.find("a", href=re.compile(r'/result/\d+'))
        if link:
            href = link.get("href", "")
            if href.startswith("/"):
                entry["url"] = BASE_URL + href
            elif href.startswith("http"):
                entry["url"] = href

        # --- program field (usually in first cell or a cell with a link) ---
        # try named cells first, then fall back to the cell containing the result link
        prog_cell = (
            cell_map.get("program") or
            cell_map.get("institution") or
            cell_map.get("school") or
            None
        )
        # if we didn't find it by name, use the cell that contains the result link
        if prog_cell is None and link:
            prog_cell = link.find_parent("td") or link.find_parent("div")
        # also try the first non-empty td as last resort
        if prog_cell is None and cells:
            prog_cell = cells[0]

        if prog_cell:
            raw_prog = prog_cell.get_text(separator=" ", strip=True)
            # always keep the original raw text! important for traceability
            entry["program"] = raw_prog if raw_prog else None
            if raw_prog:
                entry["program_name"], entry["university"] = _split_program_university(raw_prog)

        # --- degree type ---
        degree_cell = cell_map.get("degree") or cell_map.get("type")
        if degree_cell:
            d_text = degree_cell.get_text(strip=True)
            if re.search(r'\bphd\b|doctorate|doctoral|d\.phil', d_text, re.I):
                entry["degree"] = "PhD"
            elif re.search(r'\bms\b|m\.s\.|meng|master|mba|mfa|mpa|mpp|m\.eng', d_text, re.I):
                entry["degree"] = "Masters"
            else:
                entry["degree"] = d_text or None

        # --- decision / status ---
        decision_cell = cell_map.get("decision") or cell_map.get("status") or cell_map.get("result")
        if decision_cell:
            raw_status = decision_cell.get_text(strip=True)
            entry["status"], entry["decision_date"] = _normalize_status(raw_status)

        # --- term / semester ---
        term_cell = cell_map.get("term") or cell_map.get("season") or cell_map.get("semester")
        if term_cell:
            term_text = term_cell.get_text(strip=True)
            entry["semester"], entry["year"] = _parse_season(term_text)

        # --- date added ---
        date_cell = cell_map.get("date added") or cell_map.get("added") or cell_map.get("date")
        if date_cell:
            entry["date_added"] = date_cell.get_text(strip=True) or None

        # --- applicant type ---
        type_cell = cell_map.get("us/international") or cell_map.get("type") or cell_map.get("status")
        if type_cell:
            type_text = type_cell.get_text(strip=True).lower()
            if "international" in type_text:
                entry["applicant_type"] = "International"
            elif "american" in type_text or "domestic" in type_text or "u.s" in type_text:
                entry["applicant_type"] = "American"

        # --- gpa ---
        gpa_cell = cell_map.get("gpa")
        if gpa_cell:
            entry["gpa"] = _parse_gpa(gpa_cell.get_text(strip=True))

        # --- gre scores ---
        gre_cell = cell_map.get("gre")
        if gre_cell:
            entry["gre_total"] = _parse_gre_score(gre_cell.get_text(strip=True))

        gre_v_cell = cell_map.get("gre v") or cell_map.get("grev")
        if gre_v_cell:
            entry["gre_v"] = _parse_gre_score(gre_v_cell.get_text(strip=True))

        gre_aw_cell = cell_map.get("gre aw") or cell_map.get("greaw") or cell_map.get("aw")
        if gre_aw_cell:
            entry["gre_aw"] = _parse_gre_score(gre_aw_cell.get_text(strip=True), is_aw=True)

        # --- comments ---
        comment_cell = cell_map.get("comments") or cell_map.get("notes") or cell_map.get("comment")
        if comment_cell:
            comment_text = comment_cell.get_text(separator=" ", strip=True)
            # clean up extra whitespace
            comment_text = re.sub(r'\s+', ' ', comment_text).strip()
            entry["comments"] = comment_text or None

    except Exception as e:
        logger.warning(f"Error parsing entry: {e}")

    return entry


def _take_robots_screenshot(driver):
    """
    Navigate to the robots.txt page and take a screenshot as evidence
    that we checked it before scraping. Saves to screenshot.jpg.
    """
    try:
        # go to the robots.txt url
        driver.get(ROBOTS_URL)
        # wait a moment for the page to fully load
        time.sleep(2)

        # save the screenshot in the same folder as this script
        screenshot_path = Path(__file__).parent / "screenshot.jpg"
        driver.save_screenshot(str(screenshot_path))
        logger.info(f"robots.txt screenshot saved: {screenshot_path}")
    except Exception as e:
        logger.error(f"Could not take robots.txt screenshot: {e}")


def _build_page_url(page_num, query=""):
    """
    Build the URL for a specific page of grad cafe survey results.
    Using urllib.parse to properly encode the query parameters.
    Example: page 5 becomes https://www.thegradcafe.com/survey/?page=5
    """
    # put the page number into a dict so urllib can encode it properly
    params = {"page": page_num}

    # if we have a search query (like filtering by program) add it too
    if query:
        params["q"] = query

    # encode the params dict into a url query string
    query_string = urllib.parse.urlencode(params)

    # combine the base survey url with the query string
    full_url = f"{SURVEY_URL}?{query_string}"
    return full_url


def _parse_result_id_from_url(url):
    """
    Extract the numeric result id from a grad cafe result url.
    Example: https://www.thegradcafe.com/result/935454 -> 935454
    """
    if not url:
        return None
    # look for /result/ followed by digits
    match = urllib.parse.urlparse(url)
    parts = match.path.strip("/").split("/")
    # the last part should be the id number
    for part in reversed(parts):
        if part.isdigit():
            return int(part)
    return None


# quick test to make sure the robots check works
if __name__ == "__main__":
    print("Checking if Grad Cafe survey is allowed by robots.txt...")
    allowed = _check_robots_txt(SURVEY_URL)
    print(f"Result: {'ALLOWED' if allowed else 'NOT ALLOWED'}")

    # test url building
    print("\nTest URL building:")
    for page in [1, 2, 100]:
        print(f"  Page {page}: {_build_page_url(page)}")
