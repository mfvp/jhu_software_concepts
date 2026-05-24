# app/blueprints/home/__init__.py
# This file sets up the "home" Blueprint.
#
# A Blueprint lets us organize our web application into smaller, self-contained
# sections. Each page (Home, Contact, Projects) has its own Blueprint so the
# code stays clean and easy to navigate.

# We import Blueprint from Flask to create our blueprint object.
from flask import Blueprint

# Blueprint('home', __name__) creates a new blueprint named 'home'.
# The name 'home' is used internally by Flask to identify this blueprint,
# for example when we call url_for('home.index') in our HTML templates.
home_bp = Blueprint('home', __name__)

# We import the routes module so Flask registers the URL routes defined there.
# This import must come AFTER home_bp is created to avoid a circular import.
# noqa comments suppress linter warnings about the import order.
from app.blueprints.home import routes  # noqa: E402, F401
