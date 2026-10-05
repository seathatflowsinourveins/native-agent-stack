#!/usr/bin/env python3
"""Operator-run local backup/check/restore drill using disposable research fixtures.

This local integration fixture composes the pinned primitives cited in
journal_recovery.py. It is not an upstream restic test or off-host acceptance.
No scheduler, service, broker or network destination is used.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import tempfile

import journal_recovery as recovery


def drill(binary: Path, scratch_root: Path) -> dict:
    os.umask(0o077)
    root = Path(tempfile.mkdtemp(prefix="equity-recovery-", dir=scratch_root))
    password = root / "throwaway-password"
    password.write_text(secrets.token_urlsafe(48) + "\n")
    password.chmod(0o600)
    writers = {}
    journals = {}
    report = {"schema_version": 1, "evidence_class": "local_integration",
              "fixture_class": "synthetic SQLite WAL journals", "started_at_utc":
              datetime.now(timezone.utc).isoformat(), "restic_pin": "0.19.1"}

    def sanitize(value):
        if isinstance(value, str):
            return value.replace(str(binary.resolve()), "<restic-0.19.1>").replace(str(root), "<scratch>")
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, dict):
            return {key: sanitize(item) for key, item in value.items()}
        return value

    try:
        for name, table in (("research", "events"), ("evidence", "runs")):
            path = root / f"{name}.sqlite3"
            db = sqlite3.connect(path, isolation_level=None)
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute(f"CREATE TABLE {table}(id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
            db.executemany(f"INSERT INTO {table}(payload) VALUES (?)", [("fixture" * 300,)] * 96)
            writers[name] = db
            journals[name] = (path, [table])
        observed = []
        written = set()

        def write_during_copy(name, status, remaining, total):
            if name not in written and status == sqlite3.SQLITE_OK and remaining > 0:
                writers[name].execute(f"INSERT INTO {journals[name][1][0]}(payload) VALUES (?)",
                                      ("committed while Online Backup was active",))
                written.add(name)
                observed.append({"journal": name, "remaining_pages": remaining,
                                 "total_pages": total, "committed_writes": 1})

        work = root / "accepted"
        work.mkdir(mode=0o700)
        runner = recovery.Restic(binary, root / "repository", password, work)
        runner.run("init", "--json")
        # One partition (1/1) deliberately reads every pack in this small proof.
        # The operator procedure defaults to seven partitions; unittest covers its rotation.
        result = recovery.cycle(runner, journals, root / "rotation-one.json", parts=1,
                                progress=write_during_copy)
        if written != set(journals):
            raise recovery.RecoveryError("both journals must be written during their Online Backup")
        inventory = json.loads((work / "frozen-inventory.json").read_text())
        independent = []
        # Independent byte/state observation, separate from recovery.verify's result.
        expected_paths = {"inventory.json", *(record["path"] for record in inventory["files"])}
        if {p.relative_to(work / "restored").as_posix() for p in (work / "restored").rglob("*")
            if p.is_file()} != expected_paths:
            raise recovery.RecoveryError("independent restore file-set comparison failed")
        for record in inventory["files"]:
            staged = work / "stage" / record["path"]
            restored = work / "restored" / record["path"]
            data = restored.read_bytes()
            if data != staged.read_bytes() or hashlib.sha256(data).hexdigest() != record["sha256"]:
                raise recovery.RecoveryError("independent byte/hash comparison failed")
            db = sqlite3.connect(restored.as_uri() + "?mode=ro", uri=True)
            try:
                if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise recovery.RecoveryError("independent integrity observation failed")
                counts = {t: db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                          for t in record["required_tables"]}
            finally:
                db.close()
            if counts != record["required_tables"] or list(counts.values()) != [97]:
                raise recovery.RecoveryError("concurrent committed row missing from restore")
            independent.append({"path": record["path"], "sha256": record["sha256"],
                                "bytes": len(data), "integrity_check": "ok", "row_counts": counts})
        controls = {}
        for control in ("snapshot", "restore"):
            control_work = root / ("control-" + control)
            args = [sys.executable, str(Path(recovery.__file__)), "cycle", "--restic-bin", str(binary),
                    "--repository", str(root / "repository"), "--password-file", str(password),
                    "--work", str(control_work), "--rotation-state", str(root / "rotation-one.json"),
                    "--check-parts", "1", "--control", control]
            for name, (path, tables) in journals.items():
                args.extend(["--journal", f"{name}={path}"])
                for table in tables:
                    args.extend(["--required-table", f"{name}={table}"])
            completed = subprocess.run(args, env=runner.env, cwd=root, text=True,
                                       capture_output=True, timeout=900, check=False)
            returned = json.loads(completed.stdout)
            native = [json.loads(p.read_text()) for p in sorted(control_work.glob("restic-*.result.json"))]
            controls[control] = {"exit": completed.returncode, "returned": returned,
                                 "native_commands": native}
            if completed.returncode == 0:
                raise recovery.RecoveryError("a failing control incorrectly passed")
            if control == "snapshot" and not any(c["exit"] == 3 for c in native):
                raise recovery.RecoveryError("snapshot control must observe native restic exit 3")
            if control == "restore" and (not any(c["args"][0] == "restore" and c["exit"] == 0 for c in native)
                                         or "file inventory mismatch" not in returned.get("reason", "")):
                raise recovery.RecoveryError("restore control must fail the comparison after native restore")
        report.update(result="passed", copy_observations=observed, frozen_inventory=inventory,
                      native_commands=runner.commands, comparison=result,
                      independent_observation=independent, controls=controls,
                      limitations=["Same-host disposable repository and key; no off-host recovery.",
                                   "No deployed scheduler, process restart, reboot, missed-run or independent alert drill.",
                                   "Two per-journal snapshots; no atomic transaction spanning both journals.",
                                   "Subset 1/1 only; seven-part rotation is tested separately with stdlib fixtures."])
    finally:
        for db in writers.values():
            db.close()
        password.unlink(missing_ok=True)
    report["throwaway_password_deleted"] = not password.exists()
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    return sanitize(report)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restic-bin", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, default=os.environ.get("TMPDIR"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.scratch_root is None or not args.scratch_root.is_dir():
        parser.error("set TMPDIR or --scratch-root to an existing private scratch directory")
    try:
        report = drill(args.restic_bin, args.scratch_root)
        if args.output:
            recovery.write_new(args.output, recovery.json_bytes(report))
        print(json.dumps({"result": report["result"], "matched_journals": 2,
                          "checked_subset": report["comparison"]["checked_subset"],
                          "snapshot_control_exit": report["controls"]["snapshot"]["exit"],
                          "restore_control_exit": report["controls"]["restore"]["exit"],
                          "throwaway_password_deleted": report["throwaway_password_deleted"]}, sort_keys=True))
        return 0
    except (ValueError, OSError, sqlite3.Error, subprocess.TimeoutExpired) as error:
        print(json.dumps({"result": "failed", "reason": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
