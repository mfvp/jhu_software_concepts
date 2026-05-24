# app/blueprints/projects/__init__.py
# This file sets up the "projects" Blueprint.
# Same pattern as home and contact — create the blueprint, then import routes.

from flask import Blueprint

# Create the blueprint named 'projects'.
# Flask uses this name when generating URLs, e.g. url_for('projects.index').
projects_bp = Blueprint('projects', __name__)

# Import routes after creating the blueprint to avoid circular imports.
from app.blueprints.projects import routes  # noqa: E402, F401
