from flask import Blueprint

home_bp = Blueprint('home', __name__)

from app.blueprints.home import routes  # noqa: E402, F401
