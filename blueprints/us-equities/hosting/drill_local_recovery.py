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
import threading
import time
import re

import journal_recovery as recovery


def scratch_directory(scratch_root: Path) -> tuple[Path, Path]:
    """Keep both lexical and canonical names; operate only on the resolved root."""
    lexical = Path(tempfile.mkdtemp(prefix="equity-recovery-", dir=scratch_root)).absolute()
    return lexical.resolve(), lexical


def assert_sanitized(value) -> None:
    """Refuse publication if any Unix/Windows absolute path remains in a string."""
    if isinstance(value, str):
        if re.search(r'(?<![A-Za-z0-9_<>.])/(?!/)[^\s,\"\']+|(?<![A-Za-z0-9_])[A-Za-z]:[\\/]', value):
            raise recovery.RecoveryError("sanitized output still contains an absolute path")
    elif isinstance(value, list):
        for item in value:
            assert_sanitized(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            assert_sanitized(key)
            assert_sanitized(item)


def sanitize(value, *, root: Path, lexical_root: Path, binary: Path):
    replacements = {str(root): "<scratch>", str(lexical_root): "<scratch>",
                    str(binary.absolute()): "<restic-0.19.1>", str(binary.resolve()): "<restic-0.19.1>"}

    def scrub(item):
        if isinstance(item, str):
            for path in sorted(replacements, key=len, reverse=True):
                item = item.replace(path, replacements[path])
            return item
        if isinstance(item, list):
            return [scrub(child) for child in item]
        if isinstance(item, dict):
            return {scrub(key): scrub(child) for key, child in item.items()}
        return item

    clean = scrub(value)
    assert_sanitized(clean)
    return clean


def drill(binary: Path, scratch_root: Path) -> dict:
    os.umask(0o077)
    root, lexical_root = scratch_directory(scratch_root)
    unlock_file = root / "throwaway-unlock-file"
    unlock_file.write_text(secrets.token_urlsafe(48) + "\n")
    unlock_file.chmod(0o600)
    writers = {}
    stops, threads, commits, writer_errors = {}, {}, {}, []
    journals = {}
    report = {"schema_version": 1, "evidence_class": "local_integration",
              "fixture_class": "synthetic SQLite WAL journals", "started_at_utc":
              datetime.now(timezone.utc).isoformat(), "restic_pin": "0.19.1"}

    try:
        for name, table in (("research", "events"), ("evidence", "runs")):
            path = root / f"{name}.sqlite3"
            db = sqlite3.connect(path, isolation_level=None)
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA wal_autocheckpoint=0")
            db.execute(f"CREATE TABLE {table}(id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
            # About 8 MiB each: long enough to observe overlapping commits during
            # a single native pages=-1 step, without delaying/reimplementing it.
            db.executemany(f"INSERT INTO {table}(payload) VALUES (?)", [("fixture" * 12000,)] * 96)
            writers[name] = db
            journals[name] = (path, [table])
        observed = []

        def write_continuously(name):
            # Independent WAL connection/thread; CPython releases the GIL during
            # sqlite3_backup_step (@v3.12.3:Modules/_sqlite/connection.c:2075-2078).
            db = sqlite3.connect(journals[name][0], isolation_level=None)
            try:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("PRAGMA wal_autocheckpoint=0")
                while not stops[name].is_set():
                    db.execute(f"INSERT INTO {journals[name][1][0]}(payload) VALUES (?)", ("concurrent WAL commit",))
                    commits[name].append(time.monotonic_ns())
                    stops[name].wait(0.001)
            except Exception as error:
                writer_errors.append(type(error).__name__)
            finally:
                db.close()

        def observe_copy(name, native):
            stops[name].set()
            threads[name].join(timeout=10)
            count = sum(native["backup_started_ns"] <= instant <= native["backup_finished_ns"]
                        for instant in commits[name])
            if threads[name].is_alive() or writer_errors or count < 1:
                raise recovery.RecoveryError("each journal needs an observed commit during its native Online Backup call")
            observed.append({"journal": name, "pages": native["pages"], "committed_writes_during_native_call": count,
                             "native_copy_duration_s": (native["backup_finished_ns"] - native["backup_started_ns"]) / 1e9})

        work = root / "accepted"
        work.mkdir(mode=0o700)
        runner = recovery.Restic(binary, root / "repository", unlock_file, work)
        runner.run("init", "--json")
        for name in journals:
            stops[name], commits[name] = threading.Event(), []
            threads[name] = threading.Thread(target=write_continuously, args=(name,))
            threads[name].start()
        # One partition (1/1) deliberately reads every pack in this small proof.
        # The operator procedure defaults to seven partitions; unittest covers its rotation.
        result = recovery.cycle(runner, journals, root / "rotation-one.json", parts=1,
                                observation=observe_copy)
        if {entry["journal"] for entry in observed} != set(journals):
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
            if counts != record["required_tables"] or min(counts.values()) < 96:
                raise recovery.RecoveryError("independent snapshot row-count comparison failed")
            independent.append({"path": record["path"], "sha256": record["sha256"],
                                "bytes": len(data), "integrity_check": "ok", "row_counts": counts})
        controls = {}
        for control in ("snapshot", "restore"):
            control_work = root / ("control-" + control)
            args = [sys.executable, str(Path(recovery.__file__)), "cycle", "--restic-bin", str(binary),
                    "--repository", str(root / "repository"), "--password-file", str(unlock_file),
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
            if control == "restore":
                controls[control]["mutation_observation"] = json.loads((control_work / "restore-control.json").read_text())
            if completed.returncode == 0:
                raise recovery.RecoveryError("a failing control incorrectly passed")
            if control == "snapshot" and not any(c["exit"] == 3 for c in native):
                raise recovery.RecoveryError("snapshot control must observe native restic exit 3")
            if control == "restore" and (not any(c["args"][0] == "restore" and c["exit"] == 0 for c in native)
                                         or "sha256/bytes mismatch" not in returned.get("reason", "")):
                raise recovery.RecoveryError("restore control must fail the comparison after native restore")
        report.update(result="passed", copy_observations=observed, frozen_inventory=inventory,
                      native_commands=runner.commands, comparison=result,
                      independent_observation=independent, controls=controls,
                      limitations=["Same-host disposable repository and key; no off-host recovery.",
                                   "No deployed scheduler, process restart, reboot, missed-run or independent alert drill.",
                                   "Two per-journal snapshots; no atomic transaction spanning both journals.",
                                   "Subset 1/1 only; seven-part rotation is tested separately with stdlib fixtures."])
    finally:
        for stop in stops.values():
            stop.set()
        for thread in threads.values():
            thread.join(timeout=10)
        for db in writers.values():
            db.close()
        unlock_file.unlink(missing_ok=True)
    report["throwaway_unlock_file_deleted"] = not unlock_file.exists()
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    return sanitize(report, root=root, lexical_root=lexical_root, binary=binary)


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
            assert_sanitized(report)
            recovery.write_new(args.output, recovery.json_bytes(report))
        print(json.dumps({"result": report["result"], "matched_journals": 2,
                          "checked_subset": report["comparison"]["checked_subset"],
                          "snapshot_control_exit": report["controls"]["snapshot"]["exit"],
                          "restore_control_exit": report["controls"]["restore"]["exit"],
                          "throwaway_unlock_file_deleted": report["throwaway_unlock_file_deleted"]}, sort_keys=True))
        return 0
    except (ValueError, OSError, sqlite3.Error, subprocess.TimeoutExpired) as error:
        print(json.dumps({"result": "failed", "reason": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
