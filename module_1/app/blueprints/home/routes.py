# app/blueprints/home/routes.py
# This file defines the URL routes for the Home page.
#
# A "route" maps a URL (like "/" or "/contact") to a Python function.
# When a user visits that URL in their browser, Flask calls the matching
# function and returns whatever it produces as the web page.

# render_template() loads an HTML file from the templates/ folder and
# sends it to the user's browser.
from flask import render_template

# Import the home blueprint object so we can attach routes to it.
from app.blueprints.home import home_bp


# The @home_bp.route('/') decorator tells Flask:
# "When a user visits http://localhost:8080/, call the index() function."
# '/' is the root URL — it is the homepage of the site.
@home_bp.route('/')
def index():
    """Return the rendered HTML for the homepage."""
    # render_template() finds home/index.html inside the app/templates/ folder,
    # fills in any Jinja2 template tags, and returns the final HTML string.
    return render_template('home/index.html')
