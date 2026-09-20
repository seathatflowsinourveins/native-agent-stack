"""Meaningful integration tests: requires the dedicated migrated PostgreSQL DB."""
from uuid import uuid4
from fastapi.testclient import TestClient
import pytest
from .app import app, connection

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="session", autouse=True)
def dedicated_test_database():
    with connection() as conn:
        assert conn.info.dbname == "ledger_test", "Refusing to mutate a non-test database"


def create(title="API acceptance"):
    response = client.post("/runs", json={"title": title})
    assert response.status_code == 201
    return response.json()


@pytest.mark.parametrize("body", [{"title": " "}, {"title": "x" * 121}, {"title": 3},
                                 {"title": "valid", "status": "passed"}, {}])
def test_invalid_create_does_not_write(body):
    with connection() as conn:
        before = conn.execute("SELECT count(*) n FROM runs").fetchone()["n"]
    assert client.post("/runs", json=body).status_code == 422
    with connection() as conn:
        assert conn.execute("SELECT count(*) n FROM runs").fetchone()["n"] == before


def test_create_update_and_stale_conflict():
    item = create()
    assert (item["status"], item["revision"], item["event_count"]) == ("planned", 1, 1)
    result = client.patch("/runs/" + item["id"], json={"status": "passed", "expected_revision": 1})
    assert result.status_code == 200
    assert (result.json()["status"], result.json()["revision"], result.json()["event_count"]) == ("passed", 2, 2)
    assert client.patch("/runs/" + item["id"], json={"status": "failed", "expected_revision": 1}).status_code == 409
    with connection() as conn:
        assert conn.execute("SELECT count(*) n FROM run_events WHERE run_id=%s", (item["id"],)).fetchone()["n"] == 2


@pytest.mark.parametrize("body", [{"status": "invented", "expected_revision": 1},
                                 {"status": "passed", "expected_revision": True},
                                 {"status": "passed", "expected_revision": 0},
                                 {"status": "passed", "expected_revision": 1, "admin": True}])
def test_invalid_update(body):
    item = create()
    assert client.patch("/runs/" + item["id"], json=body).status_code == 422


def test_missing_run():
    assert client.patch(f"/runs/{uuid4()}", json={"status": "passed", "expected_revision": 1}).status_code == 404


def test_history_failure_rolls_back_run_update():
    item = create("Rollback injection fixture")
    # Test-only PostgreSQL constraint forces the second statement to fail.
    with connection() as conn:
        conn.execute("ALTER TABLE run_events ADD CONSTRAINT reject_test_event CHECK (status <> 'failed')")
    try:
        response = client.patch("/runs/" + item["id"], json={"status": "failed", "expected_revision": 1})
        assert response.status_code == 500
        with connection() as conn:
            row = conn.execute("SELECT status,revision FROM runs WHERE id=%s", (item["id"],)).fetchone()
            assert row == {"status": "planned", "revision": 1}
            assert conn.execute("SELECT count(*) n FROM run_events WHERE run_id=%s", (item["id"],)).fetchone()["n"] == 1
    finally:
        with connection() as conn:
            conn.execute("ALTER TABLE run_events DROP CONSTRAINT reject_test_event")
