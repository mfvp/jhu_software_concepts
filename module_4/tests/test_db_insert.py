"""
test_db_insert.py - database schema, inserts, idempotency and queries.
Module 4 / JHU Software Concepts in Python

Runs against the in-memory FakeConnection from conftest, which enforces url
uniqueness just like the real Postgres UNIQUE(url) constraint. That lets us check
inserts and the duplicate-pull idempotency policy without a live database.
"""

import os

import pytest

from db import APPLICANT_COLUMNS, REQUIRED_FIELDS, Database, get_database_url


@pytest.mark.db
def test_table_starts_empty(fake_db):
    """Before any insert the applicants table is empty."""
    assert fake_db.count() == 0


@pytest.mark.db
def test_insert_adds_rows_with_required_fields(fake_db, sample_rows):
    """After inserting, new rows exist and the required fields are non-null."""
    inserted = fake_db.insert_applicants(sample_rows)
    assert inserted == 3
    assert fake_db.count() == 3

    rows = fake_db.fetch_all()
    for row in rows:
        for field in REQUIRED_FIELDS:
            assert row[field] is not None


@pytest.mark.db
def test_duplicate_pull_is_idempotent(fake_db, sample_rows):
    """Inserting the same rows twice must not create duplicates."""
    first = fake_db.insert_applicants(sample_rows)
    second = fake_db.insert_applicants(sample_rows)

    assert first == 3
    assert second == 0          # ON CONFLICT skipped every row the second time
    assert fake_db.count() == 3


@pytest.mark.db
def test_partial_overlap_only_inserts_new(fake_db, sample_rows):
    """A second pull that overlaps only inserts the genuinely new rows."""
    fake_db.insert_applicants(sample_rows[:2])
    # now pull all three - only the third one is new
    inserted = fake_db.insert_applicants(sample_rows)
    assert inserted == 1
    assert fake_db.count() == 3


@pytest.mark.db
def test_query_returns_dict_with_expected_keys(fake_db, sample_rows):
    """fetch_all returns dicts containing every Module-3 required field key."""
    fake_db.insert_applicants(sample_rows)
    row = fake_db.fetch_all()[0]
    assert set(row.keys()) == set(APPLICANT_COLUMNS)


@pytest.mark.db
def test_get_database_url_uses_env(monkeypatch):
    """get_database_url should prefer the DATABASE_URL env var when set."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/test")
    assert get_database_url() == "postgresql://u:p@host:5432/test"


@pytest.mark.db
def test_get_database_url_falls_back(monkeypatch):
    """Without DATABASE_URL we fall back to the local default."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert get_database_url().startswith("postgresql://")


@pytest.mark.db
def test_database_close(fake_conn):
    """Database.close should close the underlying connection without error."""
    database = Database(fake_conn)
    database.close()  # FakeConnection.close is a no-op, just make sure it runs
