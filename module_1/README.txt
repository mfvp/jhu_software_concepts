======================================================
  Module 1 — Personal Portfolio Website
  JHU Modern Software Concepts in Python
  Author: Mateus Pereira
======================================================

DESCRIPTION
-----------
A multi-page personal portfolio website built with Flask (Python).
Three pages are provided: Home, Contact, and Projects.
The site uses Flask Blueprints, Jinja2 templates, and custom CSS.


PREREQUISITES
-------------
- Python 3.10 or higher
- pip (Python package manager)


SETUP INSTRUCTIONS
------------------
1. Clone or download the repository.

2. Navigate to the module_1 folder:
       cd jhu_software_concepts/module_1

3. (Recommended) Create and activate a virtual environment:
       python -m venv venv

       Windows:   venv\Scripts\activate
       macOS/Linux: source venv/bin/activate

4. Install all dependencies:
       pip install -r requirements.txt

5. Add your profile photo:
       Place a headshot image named  profile.jpg
       inside:  app/static/images/


RUNNING THE APPLICATION
-----------------------
From inside the module_1 folder, run:

    python run.py

The site will be available at:
    http://localhost:8080

Press  Ctrl+C  to stop the server.


PROJECT STRUCTURE
-----------------
module_1/
├── run.py                         Entry point — starts Flask on port 8080
├── requirements.txt               Dependency list for pip
├── README.txt                     This file
└── app/
    ├── __init__.py                Application factory (create_app)
    ├── blueprints/
    │   ├── home/                  Blueprint for the homepage (/)
    │   │   ├── __init__.py
    │   │   └── routes.py
    │   ├── contact/               Blueprint for the contact page (/contact)
    │   │   ├── __init__.py
    │   │   └── routes.py
    │   └── projects/              Blueprint for the projects page (/projects)
    │       ├── __init__.py
    │       └── routes.py
    ├── static/
    │   ├── css/style.css          Global stylesheet
    │   └── images/profile.jpg     Your headshot (add this file manually)
    └── templates/
        ├── base.html              Shared layout with navigation bar
        ├── home/index.html        Homepage template
        ├── contact/index.html     Contact page template
        └── projects/index.html    Projects page template


PAGES
-----
  /             Home page     — name, position, bio, profile photo
  /contact      Contact page  — email, LinkedIn, GitHub
  /projects     Projects page — Module 1 project details and GitHub link
