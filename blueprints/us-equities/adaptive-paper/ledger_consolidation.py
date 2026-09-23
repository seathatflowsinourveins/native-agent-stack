"""Bounded, offline import of flat schema-1 paper histories into their original DB.

Call ``plan(original_db, sources, lock_path=...)`` then ``apply(plan, proof,
lock_path=..., now=...)`` in the SAME process holding the existing global flock.
This module never acquires trading credentials, contacts a broker, changes STOP,
starts a trial, edits source ledgers, or adopts a source's risk configuration.

The caller supplies a fresh, fully paginated paper-broker proof: account_fingerprint,
observed_at (Unix seconds), endpoint, absolute cash (private), positions, open_orders,
orders (normalized Alpaca fields, including limit_price), history_complete=True,
unmatched_activity=[], activities_complete=True and activities (raw Alpaca FILL
rows with id, activity_type, order_id, symbol, side, qty, price). All financial
activities in the bounded window must be covered; any non-FILL is unsupported.
Orders must cover every known broker ID exactly; an unexplained zero-fill order is
still a refusal. Obtaining and attesting that proof is the caller's responsibility.
Plan objects contain private source rows/balances: retain privately, never log them.

Only disjoint flat economic segments are supported. Zero-fill diagnostic histories
may overlap. A ledger outside the account fingerprint directory requires an explicit
Source(account_fingerprint=..., provenance_path=...) attestation, a paper receipt,
and broker-bound order identities. Historical configurations and table contents are
preserved as private provenance. This is local integration, not upstream acceptance.
Legacy native-fault provenance may use the exact broker="alpaca", endpoint="paper"
pair. That compatibility applies only to its retained receipt, never broker proof.
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time


class ConsolidationError(ValueError):
    pass


TABLES = ("meta", "intents", "positions", "marks", "requests", "events", "trials")
COLUMNS = {
    "meta": ("key", "value"),
    "intents": ("client_id", "symbol", "side", "qty", "limit_price", "status", "filled_qty",
                "average_price", "broker_id", "submit_attempted", "updated_at"),
    "positions": ("symbol", "qty", "cost_basis"), "marks": ("symbol", "bid", "ask", "at"),
    "requests": ("id", "at", "kind", "client_id"), "events": ("id", "kind", "client_id", "payload"),
    "trials": ("trial_id", "started_at"),
}
TERMINAL = {"filled", "canceled", "expired", "rejected", "not_sent", "broker_refused"}
PAPER = "https://paper-api.alpaca.markets"
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_ROWS = 20000
ZERO = Decimal(0)


def _fail(reason):
    raise ConsolidationError(reason)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        _fail("invalid_decimal")
    # Ledger accounting uses a 40-digit Decimal context; weighted cost basis can
    # legitimately produce many more fractional places than broker order inputs.
    if (not result.is_finite() or len(result.as_tuple().digits) > 60
            or result.as_tuple().exponent < -60 or result.copy_abs() > Decimal("1e18")):
        _fail("invalid_decimal")
    return result


def _time(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        _fail("invalid_timestamp")
    return float(value)


@dataclass(frozen=True)
class Source:
    db_path: Path = field(repr=False)
    account_fingerprint: str | None = field(default=None, repr=False)
    provenance_path: Path | None = field(default=None, repr=False)


@dataclass(frozen=True)
class _Snapshot:
    source: Source = field(repr=False)
    data_json: str = field(repr=False)
    fingerprints: tuple = field(repr=False)
    digest: str

    @property
    def data(self):
        return json.loads(self.data_json)


@dataclass(frozen=True)
class Plan:
    original: _Snapshot = field(repr=False)
    sources: tuple = field(repr=False)
    account_fingerprint: str = field(repr=False)
    summary_json: str = field(repr=False)
    digest: str

    @property
    def summary(self):
        return json.loads(self.summary_json)


def _require_lock(lock_path):
    """Verify the caller's existing Linux flock, without acquiring or releasing it."""
    path = Path(lock_path)
    if path.is_symlink() or not path.is_file() or not re.fullmatch(r"[a-f0-9]{64}\.lock", path.name):
        _fail("account_lock_required")
    st = path.stat()
    wanted = (os.major(st.st_dev), os.minor(st.st_dev), st.st_ino)
    for line in Path("/proc/locks").read_text().splitlines():
        parts = line.split()
        if len(parts) < 8 or parts[1:4] != ["FLOCK", "ADVISORY", "WRITE"] or parts[4] != str(os.getpid()):
            continue
        major, minor, inode = parts[5].split(":")
        if (int(major, 16), int(minor, 16), int(inode)) == wanted:
            return path.stem
    _fail("account_lock_not_held_by_current_process")


def _source(value):
    source = value if isinstance(value, Source) else Source(Path(value))
    path = Path(source.db_path)
    if path.is_symlink() or not path.is_file() or path.name != "ledger.sqlite3":
        _fail("invalid_source_file")
    provenance = Path(source.provenance_path).resolve() if source.provenance_path else None
    return Source(path.resolve(), source.account_fingerprint, provenance)


def _fingerprints(source):
    paths = [source.db_path, Path(str(source.db_path) + "-wal"), source.db_path.parent / "trial.json"]
    if source.provenance_path:
        paths.append(source.provenance_path)
    result = []
    for p in paths:
        if p.is_symlink():
            _fail("source_symlink")
        if not p.exists():
            if p == source.db_path or p == source.provenance_path:
                _fail("source_missing")
            content = b""
        else:
            if not p.is_file() or p.stat().st_size > MAX_SOURCE_BYTES:
                _fail("source_size_or_type")
            content = p.read_bytes()
        result.append((str(p), len(content), _sha(content)))
    return tuple(result)


def _tables(db):
    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or db.execute("PRAGMA foreign_key_check").fetchone():
        _fail("source_integrity")
    result = {}
    for table in TABLES:
        if tuple(r[1] for r in db.execute("PRAGMA table_info(" + table + ")")) != COLUMNS[table]:
            _fail("unsupported_table_schema")
        rows = db.execute("SELECT * FROM " + table + " ORDER BY rowid LIMIT ?", (MAX_ROWS + 1,)).fetchall()
        if len(rows) > MAX_ROWS:
            _fail("source_row_cap")
        result[table] = [dict(r) for r in rows]
    return result


def _snapshot(source):
    before = _fingerprints(source)
    src = sqlite3.connect(source.db_path.as_uri() + "?mode=ro", uri=True, timeout=5)
    memory = sqlite3.connect(":memory:")
    memory.row_factory = sqlite3.Row
    deadline = time.monotonic() + 10
    def progress(*_):
        if time.monotonic() > deadline:
            _fail("snapshot_deadline")
    try:
        src.backup(memory, pages=128, progress=progress, sleep=.01)
        tables = _tables(memory)
    finally:
        memory.close()
        src.close()
    trial = source.db_path.parent / "trial.json"
    data = {"tables": tables, "trial": json.loads(trial.read_text()) if trial.exists() else None,
            "provenance": json.loads(source.provenance_path.read_text()) if source.provenance_path else None}
    if _fingerprints(source) != before:
        _fail("source_changed_during_snapshot")
    encoded = _json(data)
    return _Snapshot(source, encoded, before, _sha(encoded.encode()))


def _meta(data):
    return {r["key"]: r["value"] for r in data["tables"]["meta"]}


def _validate(snapshot, fingerprint):
    data = snapshot.data
    tables, meta = data["tables"], _meta(data)
    source = snapshot.source
    if meta.get("schema_version") != "1":
        _fail("unsupported_schema")
    if fingerprint not in source.db_path.parts:
        provenance = data["provenance"]
        paper_receipt = isinstance(provenance, dict) and (
            (provenance.get("endpoint") == PAPER and provenance.get("broker") in (None, "alpaca"))
            or (provenance.get("broker") == "alpaca" and provenance.get("endpoint") == "paper"))
        broker_bound = any(isinstance(row["broker_id"], str) and row["broker_id"].strip()
                           for row in tables["intents"])
        if (source.account_fingerprint != fingerprint or not paper_receipt or not broker_bound):
            _fail("source_account_attestation_required")
    if source.account_fingerprint not in (None, fingerprint):
        _fail("source_account_mismatch")
    if any(_decimal(r["qty"]) != 0 or _decimal(r["cost_basis"]) != 0 for r in tables["positions"]):
        _fail("source_not_flat")
    if any(r["status"] not in TERMINAL for r in tables["intents"]):
        _fail("source_not_terminal")
    if meta.get("halted_reason") not in (None, "recovery_only"):
        _fail("source_risk_halt_requires_resolution")
    intents = {r["client_id"]: r for r in tables["intents"]}
    for row in intents.values():
        if (_decimal(row["qty"]) <= 0 or _decimal(row["limit_price"]) <= 0
                or row["side"] not in ("buy", "sell") or _decimal(row["filled_qty"]) < 0):
            _fail("invalid_intent")
        local = row["status"] in ("not_sent", "broker_refused")
        if local:
            if row["broker_id"] is not None or _decimal(row["filled_qty"]) or row["average_price"] is not None:
                _fail("local_terminal_has_broker_observation")
            matching = [e for e in tables["events"] if e["client_id"] == row["client_id"]]
            if any(e["kind"] == "order_observed" for e in matching):
                _fail("local_terminal_has_broker_observation")
            if row["status"] == "not_sent":
                if not any(e["kind"] == "intent_not_sent" and re.fullmatch(r"[a-z][a-z0-9_]{0,79}",
                           str(json.loads(e["payload"]).get("reason", ""))) for e in matching):
                    _fail("local_terminal_evidence_missing")
            elif (not row["submit_attempted"] or not any(e["kind"] == "broker_refused"
                    and json.loads(e["payload"]).get("http_status") in (401, 403, 404)
                    and json.loads(e["payload"]).get("evidence_required") == "submission_http_refusal_then_client_id_404"
                    for e in matching)):
                _fail("local_terminal_evidence_missing")
        elif (not isinstance(row["broker_id"], str) or not 1 <= len(row["broker_id"]) <= 128
              or row["submit_attempted"] != 1):
            _fail("broker_identity_or_attempt_missing")
    positions, seen, final_status, flows = {}, {}, {}, []
    cash = realized = loss = flat_peak_floor = ZERO
    previous_at = 0
    for event in tables["events"]:
        value = json.loads(event["payload"])
        if event["kind"] != "order_observed":
            continue
        if event["client_id"] not in intents:
            _fail("replay_unknown_intent")
        intent = intents[event["client_id"]]
        at = _time(value["at"])
        if at < previous_at:
            _fail("replay_order_timestamps_out_of_order")
        previous_at = at
        qty = _decimal(value["filled_qty"])
        average = _decimal(value["average_price"]) if qty else ZERO
        prior_qty, prior_notional = seen.get(event["client_id"], (ZERO, ZERO))
        delta, notional = qty - prior_qty, qty * average - prior_notional
        if (delta < 0 or delta != _decimal(value["delta_qty"]) or notional != _decimal(value["delta_notional"])
                or value["broker_id"] != intent["broker_id"] or qty > _decimal(intent["qty"])):
            _fail("replay_conflicting_fill")
        seen[event["client_id"]] = (qty, qty * average)
        final_status[event["client_id"]] = value["status"]
        if not delta:
            if notional:
                _fail("replay_same_qty_changed_notional")
            continue
        if notional <= 0 or (intent["side"] == "buy" and notional / delta > _decimal(intent["limit_price"])) or (
                intent["side"] == "sell" and notional / delta < _decimal(intent["limit_price"])):
            _fail("replay_limit_violation")
        symbol = intent["symbol"]
        held, cost = positions.get(symbol, (ZERO, ZERO))
        if intent["side"] == "buy":
            held, cost = held + delta, cost + notional
            flow = -notional
        elif intent["side"] == "sell" and held >= delta:
            basis = cost / held * delta
            pnl = notional - basis
            held, cost = held - delta, cost - basis
            realized += pnl
            loss += max(ZERO, -pnl)
            flow = notional
        else:
            _fail("replay_short_or_invalid_side")
        positions[symbol] = (held, cost if held else ZERO)
        cash += flow
        flows.append((at, flow))
        if all(qty == 0 for qty, _ in positions.values()):
            flat_peak_floor = max(flat_peak_floor, realized)
    if any(qty != 0 or cost != 0 for qty, cost in positions.values()):
        _fail("replay_not_flat")
    for row in tables["intents"]:
        qty, notional = seen.get(row["client_id"], (ZERO, ZERO))
        if (qty != _decimal(row["filled_qty"]) or (qty and notional != qty * _decimal(row["average_price"]))
                or (row["status"] == "filled" and qty != _decimal(row["qty"]))
                or (row["broker_id"] and final_status.get(row["client_id"]) != row["status"])):
            _fail("replay_terminal_intent_mismatch")
    for key, actual in (("cash_delta", cash), ("realized", realized), ("realized_loss", loss)):
        if _decimal(meta[key]) != actual:
            _fail("replay_accounting_mismatch")
    submits = {}
    for row in tables["requests"]:
        _time(row["at"])
        if row["kind"] not in ("read", "data_read", "submit", "cancel"):
            _fail("unknown_request_kind")
        if row["client_id"] is not None and row["client_id"] not in intents:
            _fail("request_unknown_intent")
        if row["kind"] == "submit":
            if row["client_id"] is None:
                _fail("submission_without_identity")
            submits[row["client_id"]] = submits.get(row["client_id"], 0) + 1
    if any(n != 1 for n in submits.values()) or any(bool(r["submit_attempted"]) != (submits.get(r["client_id"]) == 1) for r in intents.values()):
        _fail("submission_binding_mismatch")
    if not tables["requests"]:
        _fail("source_without_request_history")
    start = _time(float(meta["trial_start"]))
    if tables["trials"]:
        start = min(_time(r["started_at"]) for r in tables["trials"])
    # The original baseline belongs to its FIRST trial, not the latest resume.
    if data["trial"] is not None:
        start = min(start, _time(float(data["trial"]["started_at"])))
    elif flows:
        _fail("economic_source_baseline_missing")
    peak = _decimal(meta["peak_pnl"])
    if peak < max(ZERO, realized, flat_peak_floor):
        _fail("invalid_peak")
    return {"snapshot": snapshot, "start": start, "flows": flows, "cash": cash,
            "realized": realized, "loss": loss, "peak": peak}


def _analyze(original, sources, fingerprint):
    with localcontext() as ctx:
        ctx.prec = 40
        entries = [_validate(s, fingerprint) for s in (original,) + sources]
        entries.sort(key=lambda x: x["start"])
        if entries[0]["snapshot"] != original or original.data["trial"] is None:
            _fail("original_baseline_must_be_earliest")
        baseline = _decimal(original.data["trial"]["baseline_cash"])
        all_flows = sorted(flow for entry in entries for flow in entry["flows"])
        previous_end = 0
        prefix = peak = cash = loss = ZERO
        ids = {k: set() for k in ("client_id", "broker_id", "trial_id")}
        request_ids, event_ids = set(), set()
        counts = {k: 0 for k in TABLES if k != "meta"}
        for entry in entries:
            data = entry["snapshot"].data
            if entry["flows"]:
                if entry["flows"][0][0] <= previous_end:
                    _fail("overlapping_economic_segments")
                previous_end = entry["flows"][-1][0]
            if data["trial"] is not None:
                expected = baseline + sum((flow for at, flow in all_flows if at < entry["start"]), ZERO)
                if _decimal(data["trial"]["baseline_cash"]) != expected:
                    _fail("baseline_chain_gap")
            for table, key in (("intents", "client_id"), ("intents", "broker_id"), ("trials", "trial_id")):
                for row in data["tables"][table]:
                    if row[key] is None:
                        continue
                    if row[key] in ids[key]:
                        _fail("duplicate_identity")
                    ids[key].add(row[key])
            for table, keys, values in (("requests", ("at", "kind", "client_id"), request_ids),
                                         ("events", ("kind", "client_id", "payload"), event_ids)):
                source_identities = {tuple(row[k] for k in keys) for row in data["tables"][table]}
                if source_identities & values:
                    _fail("duplicate_history_row")
                # Repeated observations or read attempts within one source are
                # history, not duplicates to discard. Reject only cross-source
                # overlap; the original row lists are copied in full on apply.
                values.update(source_identities)
            for key in counts:
                counts[key] += len(data["tables"][key])
            # Translate each independent local high-water mark to the original
            # account baseline; never add or directly maximize local peaks.
            peak = max(peak, prefix + entry["peak"])
            prefix += entry["realized"]
            cash += entry["cash"]
            loss += entry["loss"]
        return {"counts": counts, "count_scope": "Source-history rows; flat positions and stale marks are archived only",
                "sources": len(sources), "cash_delta": str(cash),
                "realized": str(prefix), "realized_loss": str(loss), "peak_pnl": str(peak),
                "drawdown": str(max(ZERO, peak - prefix)), "flat": True}


def plan(original_db, source_dbs, *, lock_path):
    """Read consistent SQLite backups including WAL; do not mutate any ledger."""
    fingerprint = _require_lock(lock_path)
    source_dbs = tuple(source_dbs)
    if not 1 <= len(source_dbs) <= 31:
        _fail("source_count_out_of_bounds")
    specs = tuple(_source(x) for x in (original_db,) + source_dbs)
    if len({s.db_path for s in specs}) != len(specs):
        _fail("duplicate_source_path")
    snapshots = tuple(_snapshot(s) for s in specs)
    summary = _analyze(snapshots[0], snapshots[1:], fingerprint)
    digest = _sha(_json({"snapshots": [s.digest for s in snapshots], "files": [s.fingerprints for s in snapshots],
                         "account": fingerprint, "summary": summary}).encode())
    return Plan(snapshots[0], snapshots[1:], fingerprint, _json(summary), digest)


def _broker_proof(plan, proof, now):
    with localcontext() as ctx:
        ctx.prec = 40
        return _check_broker_proof(plan, proof, now)


def _check_broker_proof(plan, proof, now):
    now, observed = _time(now), _time(proof.get("observed_at"))
    if not 0 <= now - observed <= 30 or proof.get("endpoint") != PAPER:
        _fail("broker_proof_stale_or_not_paper")
    if proof.get("account_fingerprint") != plan.account_fingerprint:
        _fail("broker_account_mismatch")
    if proof.get("history_complete") is not True or proof.get("unmatched_activity") != []:
        _fail("broker_history_incomplete")
    if proof.get("open_orders") != [] or not isinstance(proof.get("positions"), list):
        _fail("broker_not_flat_idle")
    if any(_decimal(p["qty"]) != 0 for p in proof["positions"]):
        _fail("broker_not_flat_idle")
    baseline = _decimal(plan.original.data["trial"]["baseline_cash"])
    if _decimal(proof.get("cash")) != baseline + _decimal(plan.summary["cash_delta"]):
        _fail("broker_cash_mismatch")
    expected = {r["client_id"]: r for snap in (plan.original,) + plan.sources for r in snap.data["tables"]["intents"] if r["broker_id"]}
    rows = proof.get("orders")
    if not isinstance(rows, list) or len(rows) != len(expected):
        _fail("broker_order_coverage_mismatch")
    seen = set()
    for row in rows:
        cid = row.get("client_order_id")
        if cid in seen or cid not in expected:
            _fail("broker_unknown_or_duplicate_order")
        seen.add(cid)
        old = expected[cid]
        if any(row.get(k) != old[v] for k, v in (("id", "broker_id"), ("symbol", "symbol"), ("side", "side"), ("status", "status"))):
            _fail("broker_order_identity_or_status_mismatch")
        if any(_decimal(row.get(k)) != _decimal(old[v]) for k, v in (("qty", "qty"), ("filled_qty", "filled_qty"))):
            _fail("broker_order_quantity_mismatch")
        if _decimal(row.get("limit_price")) != _decimal(old["limit_price"]):
            _fail("broker_limit_price_mismatch")
        if _decimal(old["filled_qty"]) and _decimal(row.get("filled_avg_price")) != _decimal(old["average_price"]):
            _fail("broker_order_price_mismatch")
    activities = proof.get("activities")
    if proof.get("activities_complete") is not True or not isinstance(activities, list) or len(activities) > 1000:
        _fail("broker_activities_incomplete")
    by_broker = {r["broker_id"]: r for r in expected.values()}
    totals, activity_ids = {}, set()
    for row in activities:
        identifier = row.get("id")
        if not isinstance(identifier, str) or not 1 <= len(identifier) <= 256 or identifier in activity_ids:
            _fail("broker_activity_identity_invalid_or_duplicate")
        activity_ids.add(identifier)
        if row.get("activity_type") != "FILL":
            _fail("broker_non_fill_activity_unsupported")
        order = by_broker.get(row.get("order_id"))
        if order is None or row.get("symbol") != order["symbol"] or row.get("side") != order["side"]:
            _fail("broker_activity_order_mismatch")
        qty, price = _decimal(row.get("qty")), _decimal(row.get("price"))
        if qty <= 0 or price <= 0:
            _fail("broker_activity_nonpositive_fill")
        old_qty, old_notional = totals.get(row["order_id"], (ZERO, ZERO))
        totals[row["order_id"]] = old_qty + qty, old_notional + qty * price
    for broker_id, order in by_broker.items():
        qty = _decimal(order["filled_qty"])
        expected_notional = qty * _decimal(order["average_price"]) if qty else ZERO
        if totals.get(broker_id, (ZERO, ZERO)) != (qty, expected_notional):
            _fail("broker_activity_quantity_or_notional_mismatch")


def _append_source(db, snapshot):
    for table in ("intents", "trials", "requests", "events"):
        for row in snapshot.data["tables"][table]:
            keys = [k for k in row if not (table in ("requests", "events") and k == "id")]
            db.execute("INSERT INTO " + table + "(" + ",".join(keys) + ") VALUES (" + ",".join("?" for _ in keys) + ")", [row[k] for k in keys])
    # Flat positions and stale marks are evidence, not executable current state.
    # Their original rows, risk limits and trial outcomes remain in this payload.
    db.execute("INSERT INTO consolidation_sources VALUES (?,?,?)", (str(snapshot.source.db_path), snapshot.digest, snapshot.data_json))


def apply(prepared, broker_proof, *, lock_path, now):
    """Explicit atomic mutation. Requires an unchanged plan and fresh broker proof.

    Reapplying the exact committed plan returns already_applied without mutations.
    This does not clear STOP, recovery-only state, risk halts, or expired deadlines.
    """
    began = time.monotonic()
    if not isinstance(prepared, Plan) or _require_lock(lock_path) != prepared.account_fingerprint:
        _fail("account_lock_or_plan_mismatch")
    snapshots = (prepared.original,) + prepared.sources
    if any(_sha(s.data_json.encode()) != s.digest for s in snapshots):
        _fail("plan_snapshot_digest_mismatch")
    digest = _sha(_json({"snapshots": [s.digest for s in snapshots], "files": [s.fingerprints for s in snapshots],
                         "account": prepared.account_fingerprint, "summary": prepared.summary}).encode())
    if digest != prepared.digest:
        _fail("plan_digest_mismatch")
    for snapshot in prepared.sources:
        if _fingerprints(snapshot.source) != snapshot.fingerprints:
            _fail("source_changed_after_plan")
    db = sqlite3.connect(prepared.original.source.db_path, timeout=5, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='consolidation_runs'").fetchone():
            row = db.execute("SELECT receipt FROM consolidation_runs WHERE digest=?", (prepared.digest,)).fetchone()
            if row:
                result = json.loads(row[0])
                db.execute("ROLLBACK")
                return dict(result, status="already_applied")
            if db.execute("SELECT 1 FROM consolidation_sources LIMIT 1").fetchone():
                _fail("destination_already_consolidated_replan_unsupported")
        if _fingerprints(prepared.original.source) != prepared.original.fingerprints:
            _fail("source_changed_after_plan")
        current = prepared.original.data
        if _tables(db) != current["tables"]:
            _fail("destination_changed_after_plan")
        if _analyze(prepared.original, prepared.sources, prepared.account_fingerprint) != prepared.summary:
            _fail("plan_accounting_changed")
        _broker_proof(prepared, broker_proof, now)
        db.execute("CREATE TABLE IF NOT EXISTS consolidation_sources(path TEXT PRIMARY KEY,digest TEXT NOT NULL,payload TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS consolidation_runs(digest TEXT PRIMARY KEY,receipt TEXT NOT NULL)")
        db.execute("INSERT INTO consolidation_sources VALUES (?,?,?)", (str(prepared.original.source.db_path),
                   prepared.original.digest, prepared.original.data_json))
        for snapshot in prepared.sources:
            _append_source(db, snapshot)
        for key in ("cash_delta", "realized", "realized_loss", "peak_pnl"):
            db.execute("UPDATE meta SET value=? WHERE key=?", (prepared.summary[key], key))
        for snapshot in prepared.sources:
            if _fingerprints(snapshot.source) != snapshot.fingerprints:
                _fail("source_changed_during_apply")
        if _fingerprints(prepared.original.source)[2:] != prepared.original.fingerprints[2:]:
            _fail("original_baseline_changed_during_apply")
        if _require_lock(lock_path) != prepared.account_fingerprint:
            _fail("account_lock_lost")
        _broker_proof(prepared, broker_proof, now + time.monotonic() - began)
        receipt = dict(prepared.summary, status="applied", plan_digest=prepared.digest,
                       proof_observed_at=broker_proof["observed_at"], applied_at=now,
                       limits_unchanged=True, baseline_unchanged=True, halt_unchanged=True)
        receipt["destination_counts"] = {t: db.execute("SELECT count(*) FROM " + t).fetchone()[0]
                                         for t in TABLES if t != "meta"}
        receipt["destination_counts"]["events"] += 1  # The import marker below.
        db.execute("INSERT INTO consolidation_runs VALUES (?,?)", (prepared.digest, _json(receipt)))
        db.execute("INSERT INTO events(kind,payload) VALUES (?,?)", ("history_consolidated", _json(receipt)))
        if db.execute("PRAGMA foreign_key_check").fetchone():
            _fail("import_foreign_key_error")
        db.execute("COMMIT")
        return receipt
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()
