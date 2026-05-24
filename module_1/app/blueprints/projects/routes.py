# app/blueprints/projects/routes.py
# This file defines the URL route for the Projects page.

from flask import render_template

# Import the projects blueprint so we can attach the route to it.
from app.blueprints.projects import projects_bp


# When the user navigates to http://localhost:8080/projects, Flask calls index().
@projects_bp.route('/projects')
def index():
    """Return the rendered HTML for the projects page."""
    # Loads and returns app/templates/projects/index.html
    return render_template('projects/index.html')
