# Module 4 - Tested & Documented Grad Cafe Analytics

JHU Software Concepts in Python — Module 4

This module takes the Grad Cafe analytics app from Module 3 and makes it
test-driven and documented: a full Pytest suite with 100% coverage, a GitHub
Actions CI pipeline that spin up Postgres, and Sphinx documentation published
to Read the Docs.

## Documentation

The full Sphinx documentation (setup, architecture, API reference and the
testing guide) is published on Read the Docs:

**https://mfvpjhu-software-concepts.readthedocs.io/**

You can also build it locally — see [Building the docs](#building-the-docs).

## Project layout

```
module_4/
├── src/                 # application code (Flask, ETL, DB, queries)
│   ├── flask_app.py     # create_app() factory + routes
│   ├── db.py            # Database access layer (uses DATABASE_URL)
│   ├── query_data.py    # analysis / summary computations
│   ├── load_data.py     # read + map + load applicant data
│   ├── clean.py         # data cleaning / validation
│   ├── scrape.py        # Grad Cafe scraper (injectable fetcher)
│   └── templates/       # analysis.html
├── tests/               # ALL test code lives here
├── docs/                # Sphinx project
├── pytest.ini
├── requirements.txt
├── coverage_summary.txt
└── README.md
```

## Setup

### 1. Install dependencies

```bash
pip install -r module_4/requirements.txt
```

### 2. Configure PostgreSQL

The app reads a single environment variable, `DATABASE_URL`. Create a database
named `gradcafe` and point the variable at it:

```bash
# example - adjust user / password / host to match your machine
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/gradcafe
```

On Windows PowerShell:

```powershell
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/gradcafe"
```

There is also a `src/.env.example` you can copy to `src/.env`.

### 3. Load data and run the app

```bash
cd module_4/src
python load_data.py        # loads the enriched jsonl from module 2
python -c "from flask_app import create_app; create_app().run(debug=True)"
```

Then open http://localhost:5000/analysis in your browser. The page has two
buttons: **Pull Data** (scrape + load new entries) and **Update Analysis**
(refresh the numbers). Update is blocked while a pull is in progress.

## Running the tests

Run the whole suite (with coverage) from the **repository root** so the
`--cov=module_4/src` path resolves:

```bash
pytest module_4/tests
```

Run only certain marker groups:

```bash
pytest module_4/tests -m "web or buttons"
pytest module_4/tests -m "db"
```

The available markers are `web`, `buttons`, `analysis`, `db` and `integration`
(defined in `pytest.ini`). Every test carries at least one marker, and the suite
is configured to fail if coverage drops below 100%.

## Building the docs

```bash
cd module_4/docs
make html        # or:  sphinx-build -b html . _build/html
```

The generated site lands in `module_4/docs/_build/html/index.html`.

## Continuous integration

`.github/workflows/tests.yml` starts a Postgres service, installs the
requirements, and runs the pytest suite with coverage on every push and pull
request to `main`. See `actions_success.png` for a green run.
