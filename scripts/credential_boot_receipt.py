#!/usr/bin/env python3
"""Record a value-free receipt of the credential store at each start of the user's service manager; compare two.

    python3 -I scripts/credential_boot_receipt.py record    # credential-boot-receipt.service, at every start
    python3 -I scripts/credential_boot_receipt.py compare   # the latest two receipts: did every key file survive?

`record` writes <XDG_STATE_HOME>/native-agent-stack/credential-boot/<UTC stamp>-<boot id prefix>.json, a 0600 file
in a 0700 directory, linked into place so that no receipt is ever replaced, and prints one line of counts. A
receipt holds the boot id, uptime, systemd version, whether the user lingers and the checkout revision; the rows of
scripts/credential_status.py reduced to ids, statuses, store kinds, path templates, states, findings and warnings;
each file row's fingerprint (mode, size and mtime_ns from lstat); the checker's coverage names; the names of this
uid's live native-agent-stack:* kernel keys; and whether the installed user-scope guard matches its pin. No store
file is opened, read, followed or hashed, and no value, content hash or expanded host path is recorded.

`compare` prints the states of the latest two receipts and the names of changed fingerprint fields, never their
values: the size a local receipt keeps gives a one-variable file's value length, so no printed or published form
carries it. It exits 1 when a required or optional file row that was ok is no longer ok or is gone, 2 when there is
no receipt or one cannot be read, and 0 otherwise; with a single receipt it reports that baseline.
"""

from __future__ import annotations

import os
import sys

if __name__ == "__main__" and not sys.flags.isolated:
    # Re-run isolated (-I), as tools/credentials/set_credential.py does: PYTHONPATH, PYTHONSTARTUP and the user site
    # directory then cannot shadow a module this tool imports.
    os.execv(sys.executable, [sys.executable, "-I", os.path.abspath(__file__), *sys.argv[1:]])

import argparse  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import stat  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import credential_status as cs  # noqa: E402  (stdlib-only checker: lstat and names only)

SCHEMA_VERSION = 1
KIND = "credential_boot_receipt"
RECEIPT_DIRECTORY = ("native-agent-stack", "credential-boot")
RECEIPT_NAME = re.compile(r"\d{8}T\d{6}\.\d{6}Z-(?:[0-9a-f]{8}|unknown)\.json")
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")  # a random UUID the kernel makes at each boot (random(4))
UPTIME = Path("/proc/uptime")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
SYSTEMD_VERSION = re.compile(r"systemd \d+(?: \([\w.~+-]+\))?")  # `systemctl --version`, first line
REVISION = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
STATES = ("ok", "missing", "unsafe", "unchecked", "not_local")  # credential_status.py's row states
GATED_STATUSES = {"required", "optional"}  # compare exits 1 when such a file row leaves ok
FINGERPRINT_FIELDS = ("mode", "size", "mtime_ns")


class Refused(Exception):
    """No receipt can be written or read safely; the message holds no value and no host path."""


def first_line(command: list[str]) -> str | None:
    """The first stdout line of a short read-only command, or None when it is missing or fails."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = result.stdout.splitlines()
    return lines[0].strip() if result.returncode == 0 and lines else None


def small_text(path: Path) -> str:
    try:
        with open(path, encoding="ascii") as handle:
            return handle.read(4096).strip()
    except (OSError, ValueError):
        return ""


def boot_facts() -> dict:
    """This boot as the kernel, systemd and logind report it; None for a fact the host lacks (macOS has no /proc)."""
    boot_id = small_text(BOOT_ID)
    uptime = small_text(UPTIME).split()
    try:
        uptime_seconds = round(float(uptime[0]), 2) if uptime else None
    except ValueError:
        uptime_seconds = None
    version = first_line(["systemctl", "--version"])
    # loginctl(1) show-user: Linger=yes keeps the user's manager, and so this unit, running from boot without a login.
    linger = first_line(["loginctl", "show-user", str(os.getuid()), "--property=Linger", "--value"])
    return {"boot_id": boot_id if UUID.fullmatch(boot_id) else None,
            "uptime_seconds": uptime_seconds,
            "systemd_version": version if version and SYSTEMD_VERSION.fullmatch(version) else None,
            "linger": {"yes": True, "no": False}.get(linger or "")}


def checkout_revision(root: Path) -> str | None:
    revision = first_line(["git", "-C", str(root), "rev-parse", "--verify", "HEAD"])
    return revision if revision and REVISION.fullmatch(revision) else None


def fingerprint(path: Path) -> dict | None:
    """mode, size and mtime_ns from lstat: the file is not opened, read, followed or hashed. None when absent."""
    try:
        info = os.lstat(path)
    except OSError:
        return None
    return {"mode": format(stat.S_IMODE(info.st_mode), "04o"), "size": info.st_size, "mtime_ns": info.st_mtime_ns}


def load_inventory(root: Path) -> dict:
    try:
        inventory = json.loads((root / cs.INVENTORY).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Refused(f"invalid inventory: {type(error).__name__}") from None
    errors = cs.inventory_errors(inventory, root)
    if errors:
        raise Refused(f"invalid inventory: {len(errors)} errors; run scripts/credential_status.py")
    return inventory


def build_receipt(root: Path, inventory: dict, env, *, proc_keys: Path | None, facts: dict, now: datetime) -> dict:
    report = cs.inspect(root, inventory, env, proc_keys=proc_keys)
    rows = []
    for entry in report["entries"]:
        row = {"id": entry["id"], "status": entry["status"], "store_kind": entry["store_kind"],
               "template": entry["path"], "state": entry["state"],
               "findings": list(entry["findings"]), "warnings": list(entry["warnings"])}
        if entry["store_kind"] in cs.LOCAL_KINDS:
            row["fingerprint"] = fingerprint(cs.expand_template(entry["path"], env))
        rows.append(row)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "recorded_at": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "boot": {key: facts[key] for key in ("boot_id", "uptime_seconds", "systemd_version", "linger")},
        "checkout": {"revision": checkout_revision(root)},
        "rows": rows,
        "coverage": {key: report["coverage"][key] for key in ("undeclared_store_files", "undeclared_keyring_keys")},
        "warnings": list(report["warnings"]),
        # Every live native-agent-stack:<name> key of this uid, claimed by a row or not: no entry is passed as a claim.
        "keyring_names": cs.undeclared_keyring_keys([], os.getuid(), proc_keys),
        "claude_user_guard_matches_pin": cs.guard_matches_pin(cs.claude_config_dir(env), root),
        "result": report["result"],
    }


def receipt_directory(env) -> Path:
    """<XDG_STATE_HOME>/native-agent-stack/credential-boot. An unset, empty or relative XDG_STATE_HOME means
    $HOME/.local/state (XDG Base Directory Specification)."""
    state = env.get("XDG_STATE_HOME") or ""
    if not os.path.isabs(state):
        state = os.path.join(env.get("HOME") or str(Path.home()), ".local", "state")
    return Path(state, *RECEIPT_DIRECTORY)


def private_directory(path: Path) -> Path:
    """Create the receipt directory 0700 (its parents too), refuse anything but a real directory of this user, and
    tighten its mode through a handle that does not follow a symbolic link."""
    os.makedirs(path.parent, mode=0o700, exist_ok=True)
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    try:
        handle = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise Refused("refused: the receipt directory is not a real directory") from None
    try:
        info = os.fstat(handle)
        if info.st_uid != os.getuid():
            raise Refused("refused: the receipt directory belongs to another user")
        if stat.S_IMODE(info.st_mode) != 0o700:
            os.fchmod(handle, 0o700)
    finally:
        os.close(handle)
    return path


def receipt_name(now: datetime, boot_id: str | None) -> str:
    prefix = boot_id.replace("-", "")[:8] if boot_id else "unknown"
    return f"{now.strftime('%Y%m%dT%H%M%S.%f')}Z-{prefix}.json"


def write_receipt(directory: Path, name: str, receipt: dict) -> Path:
    """Write a 0600 temporary dot-file (mkstemp), then link it to its name: a receipt is never replaced, and a killed
    writer leaves only the dot-file, which compare does not read."""
    handle, temporary = tempfile.mkstemp(prefix=f".{name}.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, directory / name)
    finally:
        os.unlink(temporary)
    return directory / name


def count(names) -> str:
    return "unknown" if names is None else str(len(names))


def summary_line(receipt: dict, name: str) -> str:
    rows = receipt["rows"]
    states = " ".join(f"{state}={sum(row['state'] == state for row in rows)}" for state in STATES)
    fingerprints = sum(row.get("fingerprint") is not None for row in rows)
    return (f"credential boot receipt: rows={len(rows)} {states} fingerprints={fingerprints} "
            f"undeclared_store_files={count(receipt['coverage']['undeclared_store_files'])} "
            f"keyring_names={count(receipt['keyring_names'])} "
            f"guard_matches_pin={json.dumps(receipt['claude_user_guard_matches_pin'])} "
            f"result={receipt['result']} receipt={name}")


def record(root: Path = ROOT, env=None, *, proc_keys: Path | None = cs.PROC_KEYS, facts: dict | None = None,
           now: datetime | None = None) -> tuple[Path, dict, str]:
    """Write one receipt; returns its path, the receipt and the line of counts."""
    env = os.environ if env is None else env
    inventory = load_inventory(root)
    facts = boot_facts() if facts is None else facts
    now = datetime.now(timezone.utc) if now is None else now
    receipt = build_receipt(root, inventory, env, proc_keys=proc_keys, facts=facts, now=now)
    directory = private_directory(receipt_directory(env))
    path = write_receipt(directory, receipt_name(now, facts["boot_id"]), receipt)
    return path, receipt, summary_line(receipt, path.name)


def receipt_names(directory: Path) -> list[str]:
    """Receipt names in time order; dot-files (a killed writer's) and anything else in the directory are skipped."""
    try:
        with os.scandir(directory) as listing:
            return sorted(item.name for item in listing
                          if RECEIPT_NAME.fullmatch(item.name) and item.is_file(follow_symlinks=False))
    except FileNotFoundError:
        return []


def load_receipt(directory: Path, name: str) -> dict:
    try:
        receipt = json.loads((directory / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Refused(f"cannot read receipt {name}") from None
    if not isinstance(receipt, dict) or receipt.get("kind") != KIND or receipt.get("schema_version") != SCHEMA_VERSION:
        raise Refused(f"receipt {name} is not a schema {SCHEMA_VERSION} {KIND}")
    return receipt


def names(values) -> str:
    return "not checked" if values is None else (",".join(values) or "none")


def seconds(value) -> str:
    return "unknown" if value is None else f"{value} s"


def fingerprint_change(before, after) -> str:
    """Which fingerprint fields changed, by name only; a value (a size is a length) is never printed."""
    if before is None and after is None:
        return "no file"
    if before is None:
        return "fingerprint new"
    if after is None:
        return "fingerprint gone"
    changed = [field for field in FINGERPRINT_FIELDS if before.get(field) != after.get(field)]
    return "fingerprint changed: " + ", ".join(changed) if changed else "fingerprint same"


def regressed(before: dict, after: dict | None) -> bool:
    """A required or optional file row that was ok and is not ok now, or has no row now."""
    return (before["status"] in GATED_STATUSES and before["store_kind"] in cs.LOCAL_KINDS
            and before["state"] == "ok" and (after is None or after["state"] != "ok"))


def compare_receipts(older: dict, newer: dict) -> tuple[list[str], list[str]]:
    """Value-free lines and the ids of the regressed rows."""
    boots = older["boot"].get("boot_id"), newer["boot"].get("boot_id")
    boot = "unknown" if None in boots else ("changed" if boots[0] != boots[1] else "unchanged")
    revisions = older["checkout"].get("revision"), newer["checkout"].get("revision")
    revision = "unknown" if None in revisions else ("same" if revisions[0] == revisions[1] else "changed")
    lines = [f"boot_id: {boot} (uptime at record {seconds(older['boot'].get('uptime_seconds'))} -> "
             f"{seconds(newer['boot'].get('uptime_seconds'))})",
             f"checkout revision: {revision}",
             f"systemd: {older['boot'].get('systemd_version')} -> {newer['boot'].get('systemd_version')}; "
             f"linger: {json.dumps(older['boot'].get('linger'))} -> {json.dumps(newer['boot'].get('linger'))}",
             "rows:"]
    before_rows = {row["id"]: row for row in older["rows"]}
    after_rows = {row["id"]: row for row in newer["rows"]}
    order = [row["id"] for row in older["rows"]] + [row["id"] for row in newer["rows"] if row["id"] not in before_rows]
    regressions = []
    for identifier in order:
        before, after = before_rows.get(identifier), after_rows.get(identifier)
        row = before or after
        line = (f"  {identifier} ({row['status']}, {row['store_kind']}): "
                f"{before['state'] if before else '(no row)'} -> {after['state'] if after else '(no row)'}")
        if before and after and "fingerprint" in before and "fingerprint" in after:
            line += ", " + fingerprint_change(before["fingerprint"], after["fingerprint"])
        if before and regressed(before, after):
            regressions.append(identifier)
            line += "  <- regression"
        lines.append(line)
    stored = older["coverage"]["undeclared_store_files"], newer["coverage"]["undeclared_store_files"]
    lines.append(f"undeclared store files: {names(stored[0])} -> {names(stored[1])}")
    keys = older["keyring_names"], newer["keyring_names"]
    lost = bool(keys[0]) and keys[1] is not None and bool(set(keys[0]) - set(keys[1]))
    lines.append(f"kernel keyring names: {names(keys[0])} -> {names(keys[1])}"
                 + (" (memory only: a kernel restart erases them)" if lost else ""))
    lines.append(f"claude_user_guard_matches_pin: {json.dumps(older['claude_user_guard_matches_pin'])} -> "
                 f"{json.dumps(newer['claude_user_guard_matches_pin'])}")
    lines.append(f"result: regression: {', '.join(regressions)} (a required or optional file row was ok and is not)"
                 if regressions else "result: ok (no required or optional file row left ok)")
    return lines, regressions


def compare(env=None) -> tuple[list[str], int]:
    env = os.environ if env is None else env
    directory = receipt_directory(env)
    found = receipt_names(directory)
    if not found:
        raise Refused("no receipt yet; run: python3 -I scripts/credential_boot_receipt.py record")
    if len(found) == 1:
        baseline = load_receipt(directory, found[0])
        return [f"baseline: {found[0]} (one receipt; nothing to compare yet)", summary_line(baseline, found[0])], 0
    older_name, newer_name = found[-2:]
    older, newer = load_receipt(directory, older_name), load_receipt(directory, newer_name)
    try:
        lines, regressions = compare_receipts(older, newer)
    except (KeyError, TypeError, AttributeError):
        raise Refused(f"cannot read receipt {older_name} or {newer_name}: a field is missing") from None
    return [f"compare: {older_name} -> {newer_name}", *lines], 1 if regressions else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("record", "compare"))
    parser.add_argument("--proc-keys", type=Path, default=cs.PROC_KEYS,
                        help="the kernel's key list, read for the names of live native-agent-stack keys "
                             f"(default {cs.PROC_KEYS}; the tests pass a fixture)")
    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            print(record(proc_keys=args.proc_keys)[2])
            return 0
        lines, code = compare()
        print("\n".join(lines))
        return code
    except Refused as error:
        print(f"credential_boot_receipt: {error}", file=sys.stderr)
    except OSError as error:  # the class only: an OSError's text would carry a host path
        print(f"credential_boot_receipt: {args.command} failed: {type(error).__name__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
