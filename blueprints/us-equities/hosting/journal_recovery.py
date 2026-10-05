#!/usr/bin/env python3
"""Snapshot research SQLite journals, then run a local restic check/restore cycle.

Supported primitives (integration policy and inventory comparison are ours):
python/cpython@v3.12.3:Doc/library/sqlite3.rst:1107-1155 (Online Backup API);
restic/restic@v0.19.1:doc/040_backup.rst:787-806 (all nonzero exits fail);
doc/045_working_with_repos.rst:482-521 (deterministic subset rotation);
doc/050_restore.rst:55-73 (explicit snapshot/subfolder restore).
Only explicit local paths are accepted; this script has no broker/client integration.
"""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import time


CHECK_PARTS = 7
MAX_CHECK_GAP = timedelta(hours=24)
INVENTORY_FILE = "inventory.json"
SAFE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class RecoveryError(ValueError):
    """A snapshot, native command, rotation or restore could not be accepted."""


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def write_new(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o400)


def file_identity(path: Path) -> dict:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise RecoveryError("inventory requires regular files, without symlinks")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"sha256": digest, "bytes": path.stat().st_size}


def journal_state(path: Path, tables: list[str]) -> dict:
    if not tables or len(set(tables)) != len(tables) or any(
        not SAFE_NAME.fullmatch(table) for table in tables
    ):
        raise RecoveryError("each journal requires distinct, explicit table names")
    # mode=ro never creates a missing journal. Snapshot destinations use DELETE mode.
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        integrity = [row[0] for row in db.execute("PRAGMA integrity_check")]
        if integrity != ["ok"]:
            raise RecoveryError("journal integrity_check failed")
        counts = {table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                  for table in sorted(tables)}
    return {"integrity_check": "ok", "required_tables": counts}


def snapshot_journals(journals: dict, stage: Path, oracle: Path, *, progress=None) -> dict:
    """One Online Backup per journal; no cross-journal atomicity is promised.

    Optional progress observation is used by the offline concurrent-write fixture.
    Failed stages remain for diagnosis; they never receive an accepted inventory.
    """
    if not journals or oracle.exists():
        raise RecoveryError("use nonempty journal selection and a new external inventory")
    if stage.resolve() in oracle.resolve().parents:
        raise RecoveryError("the trusted inventory must be outside staging")
    for name, (source, tables) in journals.items():
        if not SAFE_NAME.fullmatch(name) or not tables:
            raise RecoveryError("a journal name and required tables are mandatory")
        if not source.is_file() or source.is_symlink():
            raise RecoveryError("journal source must be an existing regular file")
    stage.mkdir(mode=0o700)
    (stage / "journals").mkdir(mode=0o700)
    records = []
    for name, (source, tables) in sorted(journals.items()):
        target = stage / "journals" / f"{name}.sqlite3"
        deadline = time.monotonic() + 60

        def observe(status, remaining, total):
            if time.monotonic() > deadline:
                raise RecoveryError("Online Backup exceeded its 60 second bound")
            if progress:
                progress(name, status, remaining, total)

        # CPython's published src.backup(dst, pages=..., progress=...) pattern.
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(target)) as dst:
                src.backup(dst, pages=16, progress=observe, sleep=0.05)
                dst.execute("PRAGMA journal_mode=DELETE")
        state = journal_state(target, tables)
        target.chmod(0o400)
        records.append({"path": target.relative_to(stage).as_posix(),
                        **file_identity(target), **state})
    inventory = {"schema_version": 1, "files": records}
    frozen = json_bytes(inventory)
    write_new(stage / INVENTORY_FILE, frozen)
    write_new(oracle, frozen)
    verify(stage, oracle)
    return inventory


def verify(root: Path, oracle: Path) -> dict:
    """Trust the external frozen inventory, never the restore's own inventory."""
    frozen = oracle.read_bytes()
    inventory = json.loads(frozen)
    records = inventory.get("files", [])
    if inventory.get("schema_version") != 1 or not records:
        raise RecoveryError("empty or invalid frozen inventory")
    expected = {INVENTORY_FILE}
    for record in records:
        relative = Path(record["path"])
        if relative.is_absolute() or ".." in relative.parts or record["path"] in expected:
            raise RecoveryError("invalid or duplicate inventory path")
        expected.add(record["path"])
    actual = set()
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise RecoveryError("restore contains a symlink or special file")
        actual.add(path.relative_to(root).as_posix())
    if actual != expected:
        raise RecoveryError("file inventory mismatch (missing or extra files)")
    if (root / INVENTORY_FILE).read_bytes() != frozen:
        raise RecoveryError("restored inventory differs from the external frozen oracle")
    for record in records:
        path = root / record["path"]
        if file_identity(path) != {key: record[key] for key in ("sha256", "bytes")}:
            raise RecoveryError("file sha256/bytes mismatch")
        if journal_state(path, list(record["required_tables"])) != {
            key: record[key] for key in ("integrity_check", "required_tables")
        }:
            raise RecoveryError("required journal state mismatch")
    return {"matched_files": len(records), "matched_bytes": sum(r["bytes"] for r in records),
            "inventory_sha256": hashlib.sha256(frozen).hexdigest(), "required_state": "matched"}


class Restic:
    """Run the pinned executable with explicit local inputs and bounded commands."""

    def __init__(self, binary: Path, repository: Path, password_file: Path, work: Path,
                 timeout: int = 600):
        self.binary = binary.resolve()
        self.repository = repository.resolve()
        self.password_file = password_file.resolve()
        self.work = work.resolve()
        self.timeout = timeout
        self.commands = []
        # Empty inherited environment: no remote repository, password or cloud settings.
        self.env = {"HOME": str(work), "PATH": "/usr/bin:/bin", "LC_ALL": "C",
                    "TMPDIR": os.environ.get("TMPDIR", str(work)), "RESTIC_PROGRESS_FPS": "0"}

    def run(self, *args: str) -> str:
        command = [str(self.binary), "--repo", str(self.repository), "--password-file",
                   str(self.password_file), "--cache-dir", str(self.work / "cache"), *args]
        started = time.monotonic()
        result = subprocess.run(command, cwd=self.work, env=self.env, text=True,
                                capture_output=True, timeout=self.timeout, check=False)
        output = result.stdout + result.stderr
        # Private raw returned output stays outside the checkout. Public proof scrubs paths.
        (self.work / f"restic-{len(self.commands):02d}.log").write_text(output)
        self.commands.append({"args": list(args), "exit": result.returncode,
                              "duration_s": round(time.monotonic() - started, 6), "output": output})
        (self.work / f"restic-{len(self.commands) - 1:02d}.result.json").write_bytes(
            json_bytes(self.commands[-1]))
        # restic@v0.19.1:doc/040_backup.rst:792-806: exit 3 is an INCOMPLETE snapshot.
        if result.returncode != 0:
            raise RecoveryError(f"restic {args[0]} refused (exit {result.returncode})")
        return result.stdout


def check_rotation(restic, state_path: Path, *, parts=CHECK_PARTS, now=None,
                   full_check=False) -> str:
    """All n/t subsets in at most seven days; advance only after native success.

    Run at least once every 24 hours, including weekends and holidays. A missed
    interval requires a successful full --read-data check before starting again.
    A separate state file belongs to this repository; concurrent checks fail closed.
    """
    if not 1 <= parts <= CHECK_PARTS:
        raise RecoveryError("rotation requires 1..7 parts (default 7)")
    now = now or datetime.now(timezone.utc)
    lock = state_path.with_suffix(state_path.suffix + ".lock")
    with lock.open("x"):
        try:
            key = hashlib.sha256(str(restic.repository).encode()).hexdigest()
            state = json.loads(state_path.read_text()) if state_path.exists() else {
                "parts": parts, "next": 1, "repository_key": key}
            if state.get("parts") != parts or state.get("repository_key") != key:
                raise RecoveryError("rotation state belongs to another repository or partition count")
            previous = datetime.fromisoformat(state["last_success"]) if "last_success" in state else None
            if previous and (now < previous or now - previous > MAX_CHECK_GAP):
                if not full_check:
                    raise RecoveryError("rotation overdue or clock reversed; require --full-check")
            if full_check:
                restic.run("check", "--read-data")
                state["next"] = 1
            part = state["next"]
            if type(part) is not int or not 1 <= part <= parts:
                raise RecoveryError("invalid rotation cursor")
            subset = f"{part}/{parts}"
            restic.run("check", f"--read-data-subset={subset}")
            state.update(next=part % parts + 1, last_success=now.isoformat())
            temporary = state_path.with_suffix(state_path.suffix + ".new")
            write_new(temporary, json_bytes(state))
            os.replace(temporary, state_path)
            return subset
        finally:
            lock.unlink()


def cycle(restic: Restic, journals: dict, state_path: Path, *, parts=CHECK_PARTS,
          full_check=False, control=None, progress=None) -> dict:
    stage, oracle, restored = (restic.work / name for name in ("stage", "frozen-inventory.json", "restored"))
    if restored.exists() or not restic.repository.is_dir() or not restic.password_file.is_file():
        raise RecoveryError("use a fresh restore/work directory and an initialized local repository")
    if restic.password_file.is_relative_to(stage) or restic.repository.is_relative_to(stage):
        raise RecoveryError("repository and password file must be outside staging")
    version_output = restic.run("version")
    if not version_output.startswith("restic 0.19.1 "):
        raise RecoveryError("restic must stay pinned to 0.19.1")
    inventory = snapshot_journals(journals, stage, oracle, progress=progress)
    verify(stage, oracle)  # Refuse a staging change before attempting backup.
    unreadable = stage / inventory["files"][0]["path"]
    if control == "snapshot":
        unreadable.chmod(0)  # Keep another readable file, so restic can create an incomplete snapshot.
    try:
        output = restic.run("backup", str(stage), "--host", "equity-research-recovery",
                            "--tag", "journal-recovery", "--json")
    finally:
        unreadable.chmod(0o400)
    if control == "snapshot":
        raise RecoveryError("snapshot control did not provoke native refusal; control is not accepted")
    verify(stage, oracle)  # Detect changes during backup before accepting its snapshot ID.
    summaries = [row for line in output.splitlines() if line.startswith("{")
                 for row in [json.loads(line)] if row.get("message_type") == "summary"]
    if len(summaries) != 1 or not re.fullmatch(r"[a-f0-9]{64}", summaries[0].get("snapshot_id", "")):
        raise RecoveryError("backup did not return exactly one complete snapshot ID")
    snapshot_id = summaries[0]["snapshot_id"]
    subset = check_rotation(restic, state_path, parts=parts, full_check=full_check)
    # Restore the selected snapshot's staging subtree to a new directory; never use latest.
    restic.run("restore", f"{snapshot_id}:{stage}", "--target", str(restored),
               "--verify", "--overwrite", "never", "--json")
    if control == "restore":
        (restored / inventory["files"][0]["path"]).unlink()
    compared = verify(restored, oracle)
    if control:
        raise RecoveryError("unknown or non-discriminating control")
    return {"snapshot_id": snapshot_id, "checked_subset": subset, **compared}


def selections(journal_args, table_args) -> dict:
    journals, tables = {}, {}
    for argument in journal_args:
        name, separator, path = argument.partition("=")
        if not separator or not path or name in journals or not SAFE_NAME.fullmatch(name):
            raise RecoveryError("use distinct --journal NAME=PATH arguments")
        journals[name] = Path(path)
    for argument in table_args:
        name, separator, table = argument.partition("=")
        if not separator or name not in journals or not SAFE_NAME.fullmatch(table):
            raise RecoveryError("use --required-table NAME=TABLE for each selected journal")
        tables.setdefault(name, []).append(table)
    if not journals or set(tables) != set(journals):
        raise RecoveryError("every selected journal needs explicit required tables")
    return {name: (path, tables[name]) for name, path in journals.items()}


def main(argv=None) -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("snapshot", "cycle"):
        p = commands.add_parser(name)
        p.add_argument("--journal", action="append", required=True)
        p.add_argument("--required-table", action="append", required=True)
        if name == "snapshot":
            p.add_argument("--stage", type=Path, required=True)
            p.add_argument("--inventory", type=Path, required=True)
        else:
            p.add_argument("--restic-bin", type=Path, required=True)
            p.add_argument("--repository", type=Path, required=True)
            p.add_argument("--password-file", type=Path, required=True)
            p.add_argument("--work", type=Path, required=True)
            p.add_argument("--rotation-state", type=Path, required=True)
            p.add_argument("--check-parts", type=int, default=CHECK_PARTS)
            p.add_argument("--full-check", action="store_true")
            p.add_argument("--control", choices=("snapshot", "restore"))
    p = commands.add_parser("verify")
    p.add_argument("--restored", type=Path, required=True)
    p.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            result = verify(args.restored, args.inventory)
        else:
            journals = selections(args.journal, args.required_table)
            if args.command == "snapshot":
                result = snapshot_journals(journals, args.stage, args.inventory)
            else:
                args.work.mkdir(mode=0o700)
                runner = Restic(args.restic_bin, args.repository, args.password_file, args.work)
                result = cycle(runner, journals, args.rotation_state, parts=args.check_parts,
                               full_check=args.full_check, control=args.control)
        print(json.dumps({"result": "passed", **result}, sort_keys=True))
        return 0
    except (RecoveryError, OSError, sqlite3.Error, KeyError, TypeError,
            subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        # No source path, repository path or password is emitted in the public result.
        detail = str(error) if isinstance(error, RecoveryError) else type(error).__name__
        print(json.dumps({"result": "refused", "reason": detail}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
