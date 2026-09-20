"""Typed local run ledger; PostgreSQL owns state and transactional history."""

from datetime import datetime
from enum import StrEnum
import os
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@127.0.0.1:15432/ledger")
app = FastAPI(title="Run ledger", version="0.1.0")


class RunStatus(StrEnum):
    planned = "planned"
    running = "running"
    passed = "passed"
    failed = "failed"


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class RunUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: RunStatus
    expected_revision: int = Field(strict=True, ge=1)


class RunRead(BaseModel):
    id: UUID
    title: str
    status: RunStatus
    revision: int
    created_at: datetime
    updated_at: datetime
    event_count: int


def connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=5)


READ = """SELECT r.*, count(e.id) AS event_count FROM runs r
          JOIN run_events e ON e.run_id=r.id"""


def one(conn, run_id):
    return conn.execute(READ + " WHERE r.id=%s GROUP BY r.id", (run_id,)).fetchone()


@app.get("/health")
def health():
    with connection() as conn:
        return {"status": "ready", "postgres_version": conn.execute("SHOW server_version").fetchone()["server_version"]}


@app.get("/runs", response_model=list[RunRead])
def list_runs():
    with connection() as conn:
        return conn.execute(READ + " GROUP BY r.id ORDER BY r.created_at DESC, r.id LIMIT 100").fetchall()


@app.post("/runs", response_model=RunRead, status_code=201)
def create_run(body: RunCreate):
    run_id = uuid4()
    with connection() as conn:
        conn.execute("INSERT INTO runs(id,title) VALUES (%s,%s)", (run_id, body.title))
        conn.execute("INSERT INTO run_events(run_id,revision,status) VALUES (%s,1,'planned')", (run_id,))
        return one(conn, run_id)


@app.patch("/runs/{run_id}", response_model=RunRead)
def update_run(run_id: UUID, body: RunUpdate):
    with connection() as conn:
        row = conn.execute("""UPDATE runs SET status=%s, revision=revision+1, updated_at=clock_timestamp()
                              WHERE id=%s AND revision=%s RETURNING revision""",
                           (body.status.value, run_id, body.expected_revision)).fetchone()
        if row is None:
            exists = conn.execute("SELECT 1 FROM runs WHERE id=%s", (run_id,)).fetchone()
            raise HTTPException(409 if exists else 404, "Run changed; refresh before updating." if exists else "Run not found.")
        conn.execute("INSERT INTO run_events(run_id,revision,status) VALUES (%s,%s,%s)",
                     (run_id, row["revision"], body.status.value))
        return one(conn, run_id)
