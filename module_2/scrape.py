# scrape.py
# This is my web scraper for Grad Cafe
# I'm still learning Python so bear with me on the comments :)
# I'm using urllib to check/build URLs and selenium to load the JS-rendered pages

import urllib.robotparser
import urllib.parse
import urllib.request
import logging

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
