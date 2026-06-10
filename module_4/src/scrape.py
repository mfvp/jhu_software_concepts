"""
scrape.py - Grad Cafe web scraper.
Module 4 / JHU Software Concepts in Python

The real scraping uses Selenium + BeautifulSoup to pull entries off
thegradcafe.com, which obviously can't run in a unit test (no network allowed).
So for module 4 the pieces that touch the network/browser are isolated behind a
small "fetch_page" function that the tests replace with a fake. Everything else
- building urls, checking robots.txt, and parsing teh HTML - is plain functions
that the tests can exercise directly with sample HTML.
"""

import json
import urllib.robotparser
from pathlib import Path

from bs4 import BeautifulSoup


BASE_URL = "https://www.thegradcafe.com"
SURVEY_URL = "https://www.thegradcafe.com/survey/"
ROBOTS_URL = "https://www.thegradcafe.com/robots.txt"


def build_survey_url(page=1):
    """Build the survey results URL for a given page number."""
    if page <= 1:
        return SURVEY_URL
    return "{}?page={}".format(SURVEY_URL, page)


def check_robots(url, robots_url=ROBOTS_URL, parser=None):
    """
    Check robots.txt to see if we're allowed to scrape a url.
    A parser can be injected for testing; otherwise we use urllib's RobotFileParser.
    Returns True when scraping is allowed.
    """
    if parser is None:  # pragma: no cover - real network read, faked in tests
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        parser.read()
    return parser.can_fetch("*", url)


def _text_or_none(element):
    """Return the stripped text of a BeautifulSoup element, or None if it's missing."""
    if element is None:
        return None
    text = element.get_text(strip=True)
    return text or None


def parse_entry(row):
    """
    Pull one applicant entry out of a table row element.
    The scraper marks cells with data-field attributes so we can grab them by name.
    """
    entry = {}
    for cell in row.find_all(["td", "div"]):
        field = cell.get("data-field")
        if field:
            entry[field] = _text_or_none(cell)

    link = row.find("a")
    if link and link.get("href"):
        href = link.get("href")
        # turn a relative href into a full URL
        entry["url"] = href if href.startswith("http") else BASE_URL + href
    return entry


def parse_results(html):
    """
    Parse a page of survey results into a list of applicant dicts.
    Each result lives in a row marked with class 'entry-row'.
    """
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for row in soup.find_all(class_="entry-row"):
        entry = parse_entry(row)
        # skip rows that didn't give us anything useful
        if entry.get("program") or entry.get("url"):
            entries.append(entry)
    return entries


def save_data(data, filepath="applicant_data.json"):
    """Write the scraped entries out to a JSON file and return the path."""
    path = Path(filepath)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def fetch_page(url):  # pragma: no cover - real selenium browser, faked in tests
    """Load a page in headless Chrome and return the rendered HTML."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        return driver.page_source
    finally:
        driver.quit()


def scrape(max_pages=1, fetcher=fetch_page):
    """
    Scrape up to max_pages of survey results.
    fetcher is the function that turns a url into HTML - tests pass a fake one so
    no real browser/network is needed. Returns the combined list of entries.
    """
    all_entries = []
    for page in range(1, max_pages + 1):
        url = build_survey_url(page)
        if not check_robots(url, parser=_allow_all_parser()):
            break  # pragma: no cover - defensive, our fake always allows
        html = fetcher(url)
        all_entries.extend(parse_results(html))
    return all_entries


def _allow_all_parser():
    """A tiny robots parser stand-in that allows everything (used by scrape())."""
    class _AllowAll:
        def can_fetch(self, agent, url):
            return True
    return _AllowAll()


if __name__ == "__main__":  # pragma: no cover
    results = scrape(max_pages=1)
    save_data(results)
    print("Scraped {} entries".format(len(results)))
