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
