Testing Guide
=============

The suite lives under ``module_4/tests`` and runs fully offline &mdash; no live
internet and no real database are required, because the network and DB are
faked. Run everything from the repo root::

    pytest module_4/tests

Markers
-------

Every test is tagged with at least one marker (an unmarked test is a policy
violation). The markers are declared in ``pytest.ini``:

``web``
    Flask route / page-rendering tests.
``buttons``
    *Pull Data* / *Update Analysis* endpoints and busy-state behaviour.
``analysis``
    Label and percentage-formatting checks.
``db``
    Database schema, inserts, idempotency, queries, and the ETL helpers.
``integration``
    End-to-end pull → update → render flows.

Run a subset by marker::

    pytest module_4/tests -m "web or buttons"
    pytest module_4/tests -m "integration"

This single command runs the entire suite::

    pytest module_4/tests -m "web or buttons or analysis or db or integration"

Selectors
---------

The UI tests find the buttons by their stable ``data-testid`` attributes rather
than by their visible text:

* ``data-testid="pull-data-btn"``
* ``data-testid="update-analysis-btn"``

Percentage assertions use the regex ``\d+\.\d{2}%`` to confirm every percentage
is rendered with exactly two decimals.

Test doubles & fixtures
-----------------------

All of the shared fixtures live in ``tests/conftest.py``:

``FakeConnection`` / ``FakeCursor``
    An in-memory stand-in for a psycopg2 connection. It stores applicants in a
    dict keyed by ``url``, which gives the same uniqueness/idempotency behaviour
    as the real ``UNIQUE(url)`` constraint &mdash; without a server.
``fake_db``
    A :class:`db.Database` wrapping the fake connection, schema already created.
``sample_rows``
    A few applicant rows reused by the db / analysis / integration tests.
``fake_scraper``
    Returns the sample rows instead of scraping the network.
``app_factory`` / ``client``
    Build a ``create_app(...)`` with the scraper, database, and busy-state all
    injected, then hand back a Flask test client.

Because the busy state is an injectable object, the busy-gating tests just call
``busy.begin()`` before the request &mdash; there are no ``sleep()`` calls
anywhere in the suite.

Coverage
--------

``pytest.ini`` runs ``pytest-cov`` against ``module_4/src`` and fails the build
if coverage drops below 100%. The latest summary is committed to
``module_4/coverage_summary.txt``.
