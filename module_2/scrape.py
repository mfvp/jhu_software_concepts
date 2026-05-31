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


# quick test to make sure the robots check works
if __name__ == "__main__":
    print("Checking if Grad Cafe survey is allowed by robots.txt...")
    allowed = _check_robots_txt(SURVEY_URL)
    print(f"Result: {'ALLOWED' if allowed else 'NOT ALLOWED'}")
