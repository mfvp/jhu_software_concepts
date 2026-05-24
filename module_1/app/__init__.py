# app/__init__.py
# This file turns the app/ folder into a Python package and defines
# the "application factory" function create_app().
#
# Why use a factory function instead of just creating the app at the top level?
# It keeps configuration and blueprint registration in one tidy place and
# avoids circular import problems that can happen in larger Flask projects.

# Flask is the web framework we are using. We import the Flask class to
# create our application object.
from flask import Flask


def create_app():
    """Create and configure the Flask application."""

    # Flask(__name__) creates the application.
    # __name__ tells Flask where to look for templates and static files —
    # it resolves to the current package (the app/ folder).
    app = Flask(__name__)

    # --- Register Blueprints ---
    # A Blueprint is like a mini-application that groups related pages together.
    # We import each blueprint object and register it with the main app so
    # Flask knows about the routes defined inside them.
    # The imports are placed here (inside the function) to avoid circular imports.
    from app.blueprints.home import home_bp
    from app.blueprints.contact import contact_bp
    from app.blueprints.projects import projects_bp

    # Registering a blueprint connects its routes to the main application.
    app.register_blueprint(home_bp)
    app.register_blueprint(contact_bp)
    app.register_blueprint(projects_bp)

    # Return the fully configured app to whoever called create_app() (i.e. run.py).
    return app
