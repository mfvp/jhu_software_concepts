Overview & Setup
================

Requirements
------------

* Python 3.10+
* PostgreSQL 13+ (any recent version is fine)
* The packages in ``module_4/requirements.txt``

Install the the dependencies::

    pip install -r module_4/requirements.txt

Environment variables
---------------------

The whole application is configured through a single environment variable:

``DATABASE_URL``
    A standard Postgres connection string, for example
    ``postgresql://postgres:postgres@localhost:5432/gradcafe``.
    The database layer (:mod:`db`) reads this; if it isn't set a local
    default is used. Tests override it (or skip it entirely by injecting a
    fake connection).

There is a ``src/.env.example`` you can copy to ``src/.env``.

Running the app
---------------

From ``module_4/src``::

    python load_data.py                 # load the module 2 enriched data
    python -c "from flask_app import create_app; create_app().run(debug=True)"

Then browse to ``http://localhost:5000/analysis``.

The page exposes two buttons:

* **Pull Data** &mdash; scrapes the latest entries and loads them into Postgres.
* **Update Analysis** &mdash; recomputes the summary numbers. It is blocked
  (HTTP 409) while a pull is still running so the two never fight.

Running the tests
-----------------

From the repository root (so ``--cov=module_4/src`` resolves)::

    pytest module_4/tests

See :doc:`testing` for the markers and fixtures.
