# app/blueprints/contact/routes.py
# This file defines the URL route for the Contact page.

from flask import render_template

# Import the contact blueprint so we can attach the route to it.
from app.blueprints.contact import contact_bp


# When the user navigates to http://localhost:8080/contact, Flask calls index().
@contact_bp.route('/contact')
def index():
    """Return the rendered HTML for the contact page."""
    # Loads and returns app/templates/contact/index.html
    return render_template('contact/index.html')
