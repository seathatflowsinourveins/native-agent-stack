#!/usr/bin/env python3
"""Copy the token-report ledger readings behind the cards' native_snapshot figures into counter-readings.json.

Each native_snapshot entry in cards/*.json gives a tool, a scope, an observation time and a saved figure, and
its basis text quotes the reading's kind (and, for context-mode, its session estimate). This tool opens the
private token-report ledger read-only (sqlite3 URI mode=ro) and, for every entry, finds the one `snapshots` row
with the same tool, scope (home directory written as $HOME), observed_at to the second and metrics.saved. It
writes a sanitized copy of each row: its id, tool, scope, observed_at and success flag, plus the metrics the
entry cites (saved, kind and, where the basis quotes it, session_estimated_saved). The evidence column,
metrics.raw and every other metric are never read into the output. A missing or ambiguous match, a basis that
quotes other values than its row, or any private-content hit in the output stops the run before anything is
written. The values are the collector's historical readings; copying them measures nothing anew.

Usage: counter_readings.py [--state-dir DIR] [--out FILE]
  DIR defaults to ${XDG_STATE_HOME:-$HOME/.local/state}/native-token-report (tools/token-report/README.md),
  and the ledger is DIR/ledger.sqlite3.
"""

from __future__ import annotations

import argparse
import datetime
import getpass
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1]
ROOT = BUNDLE.parents[2]
EDITION = "2026-09-27"


def default_state_dir() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "native-token-report"


def home_relative(text: str) -> str:
    text = text.replace(str(Path.home()), "$HOME")
    return re.sub(r"/(?:home|Users)/[A-Za-z0-9_.-]+(?=/|\b)", "$HOME", text)


def snapshot_entries():
    for path in sorted((BUNDLE / "cards").glob("*.json")):
        if path.name == "index.json":
            continue
        card = json.loads(path.read_text(encoding="utf-8"))
        for index, entry in enumerate(card["adapted_performance"].get("native_snapshot") or []):
            yield f"cards/{path.name}#/adapted_performance/native_snapshot/{index}", entry


def basis_quotes(basis: str) -> dict:
    quoted = {}
    for part in basis.split(" | "):
        if part.startswith("kind: "):
            quoted["kind"] = part[len("kind: "):]
        elif part.startswith("session_estimated_saved="):
            quoted["session_estimated_saved"] = int(part.split("=", 1)[1])
    return quoted


def reading_for(rows, pointer: str, entry: dict) -> dict:
    found = []
    for row_id, tool, scope, observed_at, success, metrics_text in rows:
        if (tool == entry["tool"] and home_relative(scope or "") == entry["scope"]
                and (observed_at or "")[:19] == entry["observed_utc"][:19]):
            metrics = json.loads(metrics_text)
            if metrics.get("saved") == entry["saved"]:
                found.append((row_id, tool, home_relative(scope), observed_at, success, metrics))
    if len(found) != 1:
        raise SystemExit(f"{pointer}: expected one ledger row with its tool, scope, second and saved figure, "
                         f"found {len(found)}")
    row_id, tool, scope, observed_at, success, metrics = found[0]
    quoted = basis_quotes(entry["basis"])
    published = {"saved": metrics["saved"], "kind": metrics.get("kind")}
    if "session_estimated_saved" in quoted:
        published["session_estimated_saved"] = metrics.get("session_estimated_saved")
    if quoted != {key: published[key] for key in ("kind", "session_estimated_saved") if key in published}:
        raise SystemExit(f"{pointer}: the basis quotes values that ledger row {row_id} does not hold")
    return {"ledger_snapshot_id": row_id, "tool": tool, "scope": scope, "observed_at": observed_at,
            "success": success, "metrics": published, "card_entry": pointer}


def private_hits(text: str) -> list[str]:
    sys.path.insert(0, str(ROOT / "scripts"))
    import validate  # noqa: E402  (the repository's publication scanner)
    checks = [("e-mail address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
              ("session temp path", r"/tmp/claude-"), ("home-relative host path", r"(?<![\w$.~/-])~/"),
              ("home directory", re.escape(str(Path.home())))]
    user = getpass.getuser()
    if user and len(user) > 2:
        checks.append(("host user name", r"(?<![A-Za-z0-9])" + re.escape(user) + r"(?![A-Za-z0-9])"))
    return ([label for label, pattern in validate.PRIVATE_CONTENT if pattern.search(text)]
            + [label for label, pattern in checks if re.search(pattern, text)])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state-dir", type=Path, default=default_state_dir())
    parser.add_argument("--out", type=Path, default=BUNDLE / "counter-readings.json")
    args = parser.parse_args(argv)
    ledger = args.state_dir / "ledger.sqlite3"
    if not ledger.is_file():
        raise SystemExit("no token-report ledger.sqlite3 under --state-dir")
    connection = sqlite3.connect(ledger.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        rows = connection.execute("SELECT id, tool, scope, observed_at, success, metrics FROM snapshots").fetchall()
    finally:
        connection.close()
    copied_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    readings = sorted((reading_for(rows, pointer, entry) for pointer, entry in snapshot_entries()),
                      key=lambda reading: reading["ledger_snapshot_id"])
    document = {
        "schema_version": 1, "kind": "token_counter_readings", "edition": EDITION,
        "evidence_class": ("upstream estimate (tool-retained history snapshots that the token-report collector "
                           "recorded in its private ledger; copied read-only, not measured anew)"),
        "source": {"ledger": "the source host's native-token-report ledger, table snapshots (private, not published)",
                   "copied_at_utc": copied_at,
                   "method": ("tools/counter_readings.py: sqlite3 read-only (URI mode=ro); one row per "
                              "cards/*.json native_snapshot entry, matched on tool, scope with the home directory "
                              "written as $HOME, observed_at to the second and metrics.saved; the kind and session "
                              "estimate that each entry's basis quotes must equal the row's")},
        "published_fields": ["ledger_snapshot_id", "tool", "scope", "observed_at", "success", "metrics.saved",
                             "metrics.kind", "metrics.session_estimated_saved (only where the entry's basis quotes it)",
                             "card_entry"],
        "withheld": "the evidence column, metrics.raw and every other metric",
        "readings": readings}
    text = json.dumps(document, indent=1, ensure_ascii=False) + "\n"
    hits = private_hits(text)
    if hits:
        print("Private-content scan failed: " + ", ".join(sorted(set(hits))))
        return 1
    args.out.write_text(text, encoding="utf-8")
    print(json.dumps({"readings": len(readings), "ledger_ids": [reading["ledger_snapshot_id"] for reading in readings],
                      "copied_at_utc": copied_at, "bytes": len(text.encode("utf-8"))}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
