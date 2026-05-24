from flask import render_template

from app.blueprints.projects import projects_bp


@projects_bp.route('/projects')
def index():
    return render_template('projects/index.html')
