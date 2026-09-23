#!/usr/bin/env python3
"""Gap-wave-2 stage driver for the identity-provenance DVC and project-local arms.

Each subcommand runs the project's own adapters (replay.py, temporal_snapshot.py and
security-identity probe/quality/ledger) through their CLIs or public functions and writes a
JSON result. The same file is used as DVC stage commands and as the project-local arm, so both
arms execute identical adapter code; only the executing implementation (dvc repro vs a plain
process) and the storage path (DVC cache restore vs fresh materialization) differ.
Synthetic data only; no network, broker or credential access.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import UUID

NS_CUTOFFS = {  # cutoff -> row_ids asserted by tests/test_nanosecond_replay.py
    "2025-02-01T21:00:00.000000099Z": [],
    "2025-02-01T21:00:00.000000100Z": ["original"],
    "2025-02-01T21:00:00.000000200Z": ["correction", "future-member"],
    "2025-02-01T21:00:00.000000201Z": ["sequence-correction", "future-member"],
}
PIT_QUERIES = [  # (name, cutoff, universe, feed, adjustment, expected symbol->value) from tests/test_point_in_time.py
    ("default-feb", "2025-02-10T00:00:00Z", "fixture-selected", "fixture-feed-a", "raw", {"AAPL": "100", "MSFT": "200"}),
    ("late-correction-mar", "2025-03-10T00:00:00Z", "fixture-selected", "fixture-feed-a", "raw", {"AAPL": "90"}),
    ("future-universe-apr", "2025-04-10T00:00:00Z", "fixture-selected", "fixture-feed-a", "raw", {"AAPL": "90", "SPY": "300"}),
    ("other-universe", "2025-02-10T00:00:00Z", "fixture-other", "fixture-feed-a", "raw", {"ZZZ": "777"}),
    ("feed-b", "2025-02-10T00:00:00Z", "fixture-selected", "fixture-feed-b", "raw", {"AAPL": "999"}),
    ("split-adjustment", "2025-02-10T00:00:00Z", "fixture-selected", "fixture-feed-a", "split", {"AAPL": "50"}),
    ("unavailable-feed", "2025-02-10T00:00:00Z", "fixture-selected", "unavailable-feed", "raw", {}),
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError:
        parsed = None
    return {"exit": proc.returncode, "stdout": parsed if parsed is not None else proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-600:]}


def write(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def writable_copy(src: Path, dst: Path):
    shutil.copytree(src, dst)
    for p in [dst, *dst.rglob("*")]:
        os.chmod(p, 0o700 if p.is_dir() else 0o600)


# ---------------- nanosecond replay (replay.py) ----------------

def ns_select(a):
    replay = str(Path(a.code) / "nanosecond-replay/replay.py")
    digest = json.loads(Path(a.manifest).read_text())["snapshot_sha256"]
    out = {}
    for cutoff, expected in NS_CUTOFFS.items():
        r = run([sys.executable, replay, "select", "--snapshot", a.materialized, "--snapshot-sha256", digest,
                 "--cutoff", cutoff, "--universe-id", "fixture-universe", "--feed", "fixture-feed"])
        body = r["stdout"] if isinstance(r["stdout"], dict) else {}
        ids = [x["row_id"] for x in body.get("records", [])]
        out[cutoff] = {"exit": r["exit"], "row_ids": ids, "expected_row_ids": expected,
                       "matches_test_assertion": r["exit"] == 0 and ids == expected,
                       "selection_sql_sha256": body.get("selection_sql_sha256"),
                       "records_sha256": sha(canon(body.get("records"))),
                       "snapshot_sha256": body.get("snapshot_sha256"),
                       "source_sha256": body.get("source_sha256"), "result": body}
    write(a.out, {"arm_code": a.code, "snapshot_sha256_used": digest, "cutoffs": out,
                  "all_match": all(v["matches_test_assertion"] for v in out.values())})
    return 0 if all(v["matches_test_assertion"] for v in out.values()) else 1


def ns_quarantine(a):
    replay = str(Path(a.code) / "nanosecond-replay/replay.py")
    digest = json.loads(Path(a.manifest).read_text())["snapshot_sha256"]
    restored_source = json.loads((Path(a.materialized) / "source.json").read_text())
    cases = {}
    mutations = {
        "control_unmutated": lambda d: None,
        "obs_available_at_removed": lambda d: d["observations"][0].pop("available_at"),
        "universe_available_at_removed": lambda d: d["universe"][0].pop("available_at"),
        "obs_available_at_null": lambda d: d["observations"][0].update(available_at=None),
        "obs_available_at_date_only": lambda d: d["observations"][0].update(available_at="2025-02-01"),
        "obs_backdated_event_after_availability": lambda d: d["observations"][0].update(event_at="2025-02-01T21:00:00.000000101Z"),
    }
    with tempfile.TemporaryDirectory(prefix="g2-ns-q-") as tmp:
        tmp = Path(tmp)
        for name, mutate in mutations.items():
            data = copy.deepcopy(restored_source)
            mutate(data)
            src = tmp / f"{name}.json"
            src.write_text(json.dumps(data))
            r = run([sys.executable, replay, "materialize", "--source", str(src), "--output", str(tmp / f"{name}-out")])
            want = 0 if name == "control_unmutated" else 2
            cases["materialize:" + name] = {"exit": r["exit"], "expected_exit": want, "ok": r["exit"] == want,
                                            "stdout": r["stdout"] if r["exit"] else "(materialized)"}
        sel = ["--cutoff", "2025-02-01T21:00:00.000000100Z", "--universe-id", "fixture-universe", "--feed", "fixture-feed"]
        r = run([sys.executable, replay, "select", "--snapshot", a.materialized, "--snapshot-sha256", digest, *sel])
        cases["select:control_restored_snapshot"] = {"exit": r["exit"], "expected_exit": 0, "ok": r["exit"] == 0}
        r = run([sys.executable, replay, "select", "--snapshot", a.materialized, "--snapshot-sha256", "0" * 64, *sel])
        cases["select:wrong_snapshot_sha256"] = {"exit": r["exit"], "expected_exit": 2, "ok": r["exit"] == 2, "stdout": r["stdout"]}
        tampered = tmp / "tampered"
        writable_copy(Path(a.materialized), tampered)
        p = tampered / "observations.parquet"
        p.write_bytes(p.read_bytes() + b"corruption")
        r = run([sys.executable, replay, "select", "--snapshot", str(tampered), "--snapshot-sha256", digest, *sel])
        cases["select:parquet_tamper"] = {"exit": r["exit"], "expected_exit": 2, "ok": r["exit"] == 2, "stdout": r["stdout"]}
    ok = all(c["ok"] for c in cases.values())
    write(a.out, {"arm_code": a.code, "cases": cases, "all_ok": ok,
                  "detection_method": "exit code of the project CLI compared with expected_exit; the unmutated control must exit 0, so a non-rejecting path would show exit 0 for a mutation and fail ok"})
    return 0 if ok else 1


# ---------------- point-in-time (temporal_snapshot.py) ----------------

def pit_select(a):
    tool = str(Path(a.code) / "point-in-time/temporal_snapshot.py")
    digest = json.loads(Path(a.manifest).read_text())["snapshot_sha256"]
    out = {}
    for name, cutoff, universe, feed, adjustment, expected in PIT_QUERIES:
        r = run([sys.executable, tool, "select", "--snapshot", a.materialized, "--snapshot-sha256", digest,
                 "--cutoff", cutoff, "--universe-id", universe, "--feed", feed, "--adjustment", adjustment,
                 "--field", "Assets", "--unit", "USD"])
        body = r["stdout"] if isinstance(r["stdout"], dict) else {}
        values = {x["symbol"]: x["value_text"] for x in body.get("records", [])}
        out[name] = {"exit": r["exit"], "values": values, "expected_values": expected,
                     "matches_test_assertion": r["exit"] == 0 and values == expected,
                     "selection_sql_sha256": body.get("selection_sql_sha256"),
                     "records_sha256": sha(canon(body.get("records"))), "result": body}
    ok = all(v["matches_test_assertion"] for v in out.values())
    write(a.out, {"arm_code": a.code, "snapshot_sha256_used": digest, "queries": out, "all_match": ok})
    return 0 if ok else 1


def pit_quarantine(a):
    tool = str(Path(a.code) / "point-in-time/temporal_snapshot.py")
    restored = json.loads((Path(a.materialized) / "source.json").read_text())
    mutations = {
        "control_unmutated": lambda r: None,
        "available_at_removed": lambda r: r.pop("available_at"),
        "available_at_date_only": lambda r: r.update(available_at="2025-02-01"),
        "available_at_null": lambda r: r.update(available_at=None),
        "availability_basis_unknown": lambda r: r.update(availability_basis="trust-me"),
        "availability_evidence_empty": lambda r: r.update(availability_evidence=""),
    }
    cases = {}
    with tempfile.TemporaryDirectory(prefix="g2-pit-q-") as tmp:
        tmp = Path(tmp)
        for name, mutate in mutations.items():
            data = copy.deepcopy(restored)
            mutate(data["observations"][0])
            src = tmp / f"{name}.json"
            src.write_text(json.dumps(data))
            r = run([sys.executable, tool, "snapshot", "--source", str(src), "--output", str(tmp / f"{name}-out")])
            want = 0 if name == "control_unmutated" else 2
            cases["snapshot:" + name] = {"exit": r["exit"], "expected_exit": want, "ok": r["exit"] == want,
                                        "stdout": r["stdout"] if r["exit"] else "(snapshotted)"}
    ok = all(c["ok"] for c in cases.values())
    write(a.out, {"arm_code": a.code, "cases": cases, "all_ok": ok})
    return 0 if ok else 1


# ---------------- identity-readiness adapters (security-identity) ----------------

def load(code, name):
    path = Path(code) / "security-identity" / (name + ".py")
    spec = importlib.util.spec_from_file_location("g2_identity_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bar(day, price):
    return {"t": day + "T04:00:00Z", "o": price, "h": price + 2, "l": price - 2, "c": price + 1,
            "v": 1000, "n": 50, "vw": price}


def synthetic_fetch(plan):
    """The zero-activity capture of tests/test_security_identity.py (zero_capture), deterministic clock."""
    clock = {"n": 0}

    def payloads(case_id):
        rows = [bar(day, 100 + i) for i, day in enumerate(plan["session_dates"])]
        if case_id == "meta_current":
            return [{"id": str(UUID(int=2)), "symbol": "META", "status": "active", "exchange": "NASDAQ",
                     "class": "us_equity", "tradable": True}]
        case = next(c for c in plan["cases"] if c["case_id"] == case_id)
        rows = rows[1:] if case_id == "meta_unmapped" else rows[:1] if case_id == "fb_unmapped" else rows
        return [{"bars": {case["symbol"]: rows[i:i + 2]}, "next_page_token": "second" if i + 2 < len(rows) else None}
                for i in range(0, len(rows), 2)]

    def fetch(case_id, query):
        pages = payloads(case_id)
        body = pages[1 if query.get("page_token") else 0]
        clock["n"] += 1
        c = clock["n"]
        endpoint = plan["asset"]["url"] if case_id == "meta_current" else plan["bars_url"]
        page = {"body": json.dumps(body).encode(), "body_complete": True, "status": 200,
                "started_at": f"2026-09-20T12:00:00.{c * 100:09d}Z",
                "observed_at": f"2026-09-20T12:00:00.{c * 100 + 1:09d}Z", "transport_error": None,
                "actual_request": {"method": "GET", "url": endpoint + ("?" + urlencode(query) if query else "")}}
        if case_id == "meta_unmapped":
            page["body"] = json.dumps({"bars": {"META": [dict(bar("2022-06-08", 100), v=0, n=0, vw=0), bar("2022-06-09", 101)]},
                                       "next_page_token": "retained-continuation"}).encode()
        return page
    return fetch


def id_capture(a):
    probe = load(a.code, "probe")
    plan = json.loads((Path(a.code) / "security-identity/plan.json").read_text())
    with patch.object(probe, "native_identity", return_value={"alpaca_py_version": "0.44.0", "sources": []}):
        summary = probe.collect(Path(a.out_dir), synthetic_fetch(plan))
    write(a.out, {"receipt_sha256": summary["receipt_sha256"], "summary": summary})
    return 0


def id_quality(a):
    quality = load(a.code, "quality")
    anchor = json.loads(Path(a.capture_json).read_text())["receipt_sha256"]
    summary = quality.derive(Path(a.capture), anchor, Path(a.out_dir))
    verified = quality.verify(Path(a.out_dir), summary["receipt_sha256"])
    write(a.out, {"source_anchor": anchor, "receipt_sha256": summary["receipt_sha256"],
                  "case_status": {k: v["status"] for k, v in verified["cases"].items()}})
    return 0


def id_ledger(a):
    ledger = load(a.code, "ledger")
    anchor = json.loads(Path(a.quality_json).read_text())["receipt_sha256"]
    built = ledger.materialize(Path(a.quality), anchor, Path(a.out_dir), derived=True)
    write(a.out, {"manifest_sha256": built["manifest_sha256"], "built": built})
    return 0


def id_select(a):
    ledger = load(a.code, "ledger")
    digest = json.loads(Path(a.ledger_json).read_text())["manifest_sha256"]
    results = {}
    for label, cutoff, case in [("after-observation-meta_unmapped", "2026-09-21T00:00:00Z", "meta_unmapped"),
                                ("after-observation-meta_mapped", "2026-09-21T00:00:00Z", "meta_mapped"),
                                ("historical-2022-meta_unmapped", "2022-06-30T00:00:00Z", "meta_unmapped"),
                                ("before-first-observation", "2026-09-20T12:00:00.000000100Z", "meta_unmapped")]:
        r = ledger.select(Path(a.ledger), digest, cutoff, case)
        results[label] = {"cutoff": cutoff, "case_id": case, "count": r["count"],
                          "qualified_count": r["qualified_count"], "quarantined_count": r["quarantined_count"],
                          "historical_universe_eligible": r["historical_universe_eligible"],
                          "selection_sql_sha256": r["selection_sql_sha256"], "result": r}
    # Fail-closed checks on the restored ledger: wrong manifest digest and a byte-tampered copy.
    refusals = {}
    for label, root_fn, dig in [("wrong_manifest_sha256", lambda t: Path(a.ledger), "0" * 64),
                                ("bars_parquet_tamper", None, digest)]:
        with tempfile.TemporaryDirectory(prefix="g2-id-q-") as tmp:
            root = Path(a.ledger)
            if root_fn is None:
                root = Path(tmp) / "tampered"
                writable_copy(Path(a.ledger), root)
                p = root / "bars.parquet"
                p.write_bytes(p.read_bytes() + b"x")
            try:
                ledger.select(root, dig, "2026-09-21T00:00:00Z", "meta_unmapped")
                refusals[label] = {"refused": False}
            except (ValueError, OSError) as error:
                refusals[label] = {"refused": True, "error": f"{type(error).__name__}: {error}"}
    quarantine_ok = results["after-observation-meta_unmapped"]["quarantined_count"] == 1 and \
        (results["after-observation-meta_unmapped"]["count"], results["after-observation-meta_unmapped"]["qualified_count"]) == (2, 1)
    ok = quarantine_ok and results["historical-2022-meta_unmapped"]["count"] == 0 and all(v["refused"] for v in refusals.values())
    write(a.out, {"manifest_sha256_used": digest, "selections": results, "refusals": refusals,
                  "quarantine_preserved": quarantine_ok, "all_ok": ok})
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("ns-select", "ns-quarantine", "pit-select", "pit-quarantine"):
        s = sub.add_parser(name)
        s.add_argument("--code", required=True); s.add_argument("--materialized", required=True)
        s.add_argument("--manifest", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("id-capture"); s.add_argument("--code", required=True); s.add_argument("--out-dir", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("id-quality"); s.add_argument("--code", required=True); s.add_argument("--capture", required=True)
    s.add_argument("--capture-json", required=True); s.add_argument("--out-dir", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("id-ledger"); s.add_argument("--code", required=True); s.add_argument("--quality", required=True)
    s.add_argument("--quality-json", required=True); s.add_argument("--out-dir", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("id-select"); s.add_argument("--code", required=True); s.add_argument("--ledger", required=True)
    s.add_argument("--ledger-json", required=True); s.add_argument("--out", required=True)
    a = p.parse_args()
    fn = {"ns-select": ns_select, "ns-quarantine": ns_quarantine, "pit-select": pit_select,
          "pit-quarantine": pit_quarantine, "id-capture": id_capture, "id-quality": id_quality,
          "id-ledger": id_ledger, "id-select": id_select}[a.cmd]
    return fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
