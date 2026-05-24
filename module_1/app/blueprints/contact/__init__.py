# app/blueprints/contact/__init__.py
# This file sets up the "contact" Blueprint.
# It follows the same pattern as the home blueprint — create the blueprint
# object first, then import routes so they get registered on it.

from flask import Blueprint

# Create the blueprint named 'contact'.
# Flask uses this name when generating URLs, e.g. url_for('contact.index').
contact_bp = Blueprint('contact', __name__)

# Import routes after creating the blueprint to avoid circular imports.
from app.blueprints.contact import routes  # noqa: E402, F401
