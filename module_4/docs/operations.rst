Operational Notes
=================

Busy-state policy
-----------------

Only one data pull should run at a time. While a pull is in progress:

* ``POST /pull-data`` returns ``409`` with ``{"busy": true}`` and does **not**
  start a second pull.
* ``POST /update-analysis`` returns ``409`` with ``{"busy": true}`` and does
  **not** recompute.

The busy flag is held in a :class:`flask_app.BusyState` object. It is set before
the scrape/load starts and cleared in every exit path (including errors), so a
failed pull can't leave the app stuck "busy".

Idempotency & uniqueness
------------------------

The ``url`` column is the uniqueness key. Inserts use
``ON CONFLICT (url) DO NOTHING``, so:

* re-running a pull over data you already have inserts nothing new, and
* a pull that overlaps a previous one only adds the genuinely new rows.

``Database.insert_applicants`` returns the count of rows that were *actually*
inserted (duplicates are not counted).

Troubleshooting
---------------

**``could not connect to server`` / connection refused**
    Postgres isn't running or ``DATABASE_URL`` is wrong. Check the host, port,
    user, password, and that the ``gradcafe`` database exists.

**Tests can't import ``db`` / ``flask_app``**
    Run pytest from the repository root. ``tests/conftest.py`` adds
    ``module_4/src`` to ``sys.path`` automatically, but the working directory
    still matters for the ``--cov=module_4/src`` path.

**Coverage is below 100%**
    The build is configured to fail under 100%. Run
    ``pytest module_4/tests`` and read the ``term-missing`` column to see which
    lines aren't covered.

**GitHub Actions: db tests fail in CI**
    Confirm the ``postgres`` service is healthy and that the ``DATABASE_URL``
    env var in ``tests.yml`` matches the service credentials.
