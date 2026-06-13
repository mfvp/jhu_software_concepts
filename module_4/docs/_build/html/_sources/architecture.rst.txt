Architecture
============

The service is split into three layers. Keeping them apart is what makes the
app testable: the web layer never talks to psycopg2 directly, and the analysis
logic never touches the network.

Web layer (Flask)
-----------------

:mod:`flask_app` exposes a ``create_app(...)`` factory. The factory accepts
injected dependencies (a scraper, a loader, a database factory, and a busy-state
object) so tests can run the whole flow with fakes. Routes:

``GET /`` and ``GET /analysis``
    Render the analysis page (status 200).
``POST /pull-data``
    Scrape and load new rows. Returns ``{"ok": true}`` (200) when it works, or
    ``{"busy": true}`` (409) when a pull is already running.
``POST /update-analysis``
    Recompute the analysis. Returns ``{"ok": true}`` (200), or ``{"busy": true}``
    (409) while a pull is in progress.

Busy state lives in a small :class:`flask_app.BusyState` object instead of a
sleep-based flag, which keeps the gating tests deterministic.

ETL layer (scrape / clean / load)
---------------------------------

* :mod:`scrape` builds survey URLs, checks ``robots.txt``, and parses the
  results HTML. The actual page fetch (Selenium) is isolated behind a
  ``fetcher`` argument so the parser can be tested with sample HTML.
* :mod:`clean` strips HTML, normalises null-like values, and validates the
  numeric GPA/GRE fields.
* :mod:`load_data` maps raw scraped/enriched records into row dicts and hands
  them to the database layer.

Database layer (PostgreSQL)
---------------------------

:mod:`db` wraps a DB-API connection in a small :class:`db.Database` class with
high-level methods (``create_schema``, ``insert_applicants``, ``count``,
``fetch_all``). The schema is unchanged from Module 3 and the ``url`` column is
``UNIQUE``, which is the idempotency key &mdash; pulling the same row twice does
nothing thanks to ``ON CONFLICT (url) DO NOTHING``.

:mod:`query_data` reads the rows back as plain dicts and computes the analysis
answers in Python, so the summary logic can be unit tested without a database.

Data flow
---------

::

    Pull Data  ->  scrape()  ->  rows  ->  Database.insert_applicants()  ->  Postgres
    Analysis   ->  Database.fetch_all()  ->  query_data.get_analysis()  ->  template
