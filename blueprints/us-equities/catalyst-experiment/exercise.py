#!/usr/bin/env python3
"""Run a tiny synthetic contract using installed native DuckDB; never fetch data."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import contract
import duckdb

ROOT = Path(__file__).resolve().parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Never overwrite a prior freeze, failed run, output, or attempted adoption.
    args.output.mkdir(parents=True, exist_ok=False)
    files = ["protocol.json", "contract.py", "exercise.py", "availability.sql"]
    freeze = {
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": {name: digest(ROOT / name) for name in files},
        "synthetic_only": True,
    }
    write(args.output / "command.private.json", {"executable": sys.executable, "argv": sys.argv})
    protocol = json.loads((ROOT / "protocol.json").read_text())
    inputs = [
        ["known", 100, 110, True],
        ["late_revision", 100, 121, True],
        ["incomplete_at_120", 125, 130, True],
        ["unknown_availability", 100, None, True],
        ["quarantined", 90, 100, False],
    ]
    write(args.output / "synthetic-inputs.json", inputs)
    freeze["synthetic_inputs_sha256"] = digest(args.output / "synthetic-inputs.json")
    write(args.output / "freeze.json", freeze)
    sql = (ROOT / "availability.sql").read_text()
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE TABLE observations(observation_id VARCHAR, feature_end_ns BIGINT, available_at_ns BIGINT, quality_qualified BOOLEAN)")
    connection.executemany("INSERT INTO observations VALUES (?, ?, ?, ?)", inputs)
    expected = {100: [], 110: ["known"], 120: ["known"],
                130: ["incomplete_at_120", "known", "late_revision"]}
    actual = {}
    for cutoff, ids in expected.items():
        selected = [r[0] for r in connection.execute(sql, {"cutoff": cutoff}).fetchall()]
        actual[str(cutoff)] = selected
        if selected != ids:
            raise ValueError("native synthetic eligibility mismatch")
    # One nanosecond must remain distinct at present-day epoch magnitudes.
    base = contract.utc_ns("2026-09-21T13:35:00Z")
    exact = connection.execute(
        "SELECT CAST(? AS BIGINT)-CAST(? AS BIGINT)", [base + 1, base]
    ).fetchone()[0]
    if exact != 1: raise ValueError("native nanosecond precision lost")
    feature = {
        "security_id": "SYNTH-A", "source_hash": "a" * 64,
        "feature_end_ns": 100, "feature_available_ns": 110,
        "universe_available_ns": 90, "catalyst_available_ns": 80,
        "is_listed": True, "is_common_share": True, "identity_proven": True,
        "catalyst_original_8k_item101": True, "catalyst_age_sessions": 0,
        "full_session_minutes": 390, "complete_prior_sessions": 20,
        "basis_ids": ["S0", "S0", "S0"], "prior_close": "10",
        "median_dollar_volume": "5000000", "price_return": "0.05",
        "relative_volume": "3", "quote_age_ms": 100, "spread_bps": "30",
    }
    decisions = {lane: contract.candidate(feature, 120, lane, protocol)
                 for lane in ("daily", "intraday")}
    if any(decisions.values()): raise ValueError("synthetic boundary candidate rejected")
    # Future source mutation changes only later eligibility, never cutoff120.
    connection.execute("UPDATE observations SET available_at_ns=999 WHERE observation_id='late_revision'")
    future_perturbation = [r[0] for r in connection.execute(sql, {"cutoff": 120}).fetchall()]
    if future_perturbation != actual["120"]:
        raise ValueError("future observation changed earlier selection")
    outcomes = contract.labels("10", "12", "36", "15", "45", "13", "14", basis_consistent=True)
    connection.close()
    if any(digest(ROOT / name) != value for name, value in freeze["files"].items()):
        raise ValueError("source changed after freeze")
    result = {
        "kind": "synthetic_contract_exercise",
        "protocol_id": protocol["id"],
        "protocol_sha256": freeze["files"]["protocol.json"],
        "duckdb_version": importlib.metadata.version("duckdb"),
        "python_version": sys.version.split()[0],
        "observation_count": len(inputs),
        "native_query": "duckdb.connect(':memory:').execute(availability_sql, {'cutoff': integer_ns}).fetchall()",
        "selections": actual,
        "future_perturbation_preserves_earlier_selection": True,
        "native_bigint_one_nanosecond_difference": exact,
        "candidate_rejection_reasons": decisions,
        "named_synthetic_labels": outcomes,
        "source_hashes_unchanged": True,
        "empirical_results": None,
        "provider_calls": 0,
        "broker_orders": 0,
        "limitations": "Supplied synthetic inputs only. No real source availability, feature construction, execution accounting, matching, bootstrap or empirical promotion accepted.",
    }
    write(args.output / "result.json", result)
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
