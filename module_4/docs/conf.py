"""
Sphinx configuration for the Grad Cafe analytics docs.
Module 4 / JHU Software Concepts in Python
"""

import os
import sys

# autodoc needs to be able to import the application modules, which live in src/
sys.path.insert(0, os.path.abspath("../src"))

# -- Project information -----------------------------------------------------
project = "Grad Cafe Analytics"
author = "Mateus Pereira"
copyright = "2026, Mateus Pereira"
release = "1.0"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",       # pull docstrings out of our modules
    "sphinx.ext.napoleon",      # understand Google / NumPy style docstrings
    "sphinx.ext.viewcode",      # add links to the highlighted source
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# don't choke the build if an optional dependency (selenium etc.) isn't installed
autodoc_mock_imports = ["selenium", "psycopg2", "dotenv"]

# -- HTML output -------------------------------------------------------------
# use the Read the Docs theme. fall back to the default if it's not installed.
try:
    import sphinx_rtd_theme  # noqa: F401
    html_theme = "sphinx_rtd_theme"
except ImportError:  # pragma: no cover
    html_theme = "alabaster"

html_static_path = ["_static"]
