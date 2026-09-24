#!/usr/bin/env python3
"""Store one operator-supplied credential entry from adoption/credential-inventory.json.

Run it in your own terminal, directly or through open_credential_terminal.sh. Each value
is read with hidden input (getpass; the tool refuses if the terminal cannot hide input).
Values are never printed, logged or passed on a command line. They are written as
`export NAME=value` lines to the entry's file (mode 0600) in the per-host store (mode 0700,
owned by you, outside every Git worktree). Every write is made through a directory handle
opened without following symlinks. The output names variables only.

Live broker keys are deliberately not a stored entry (docs/secret-storage.md).

    python3 tools/credentials/set_credential.py alpaca-paper
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import stat
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import credential_status as cs  # noqa: E402  (stdlib-only checker; shares template and worktree rules)

OPERATOR_STATUSES = {"required", "optional", "user_only_paid"}
BARE_VALUE = re.compile(r"^[A-Za-z0-9._+/=:@-]+$")          # no ~ (a sourcing shell would expand it)
QUOTED_VALUE = re.compile(r'^[\x20-\x7e]+$')                 # printable ASCII only
QUOTED_FORBIDDEN = set('"$`\\')
KEY_PREFIX_HINT = {"alpaca-paper": "PK"}


class Refused(Exception):
    """A safety rule refused the operation; the message never contains a value."""


def load_entry(entry_id: str, root: Path = ROOT, env=None) -> dict:
    env = os.environ if env is None else env
    inventory = json.loads((root / cs.INVENTORY).read_text(encoding="utf-8"))
    errors = cs.inventory_errors(inventory, root)
    if errors:
        raise Refused("invalid inventory: " + "; ".join(errors))
    entry = next((e for e in inventory["entries"] if e["id"] == entry_id), None)
    if entry is None:
        raise Refused(f"unknown entry id {entry_id!r}; see {cs.INVENTORY}")
    if entry["store"]["kind"] != "private_env_file" or entry["status"] not in OPERATOR_STATUSES:
        raise Refused(f"{entry_id}: not an operator-supplied stored entry (status {entry['status']})")
    store_root = cs.expand_template(cs.STORE_ROOT, env)
    path = cs.expand_template(entry["store"]["path_template"], env)
    if path.parent != store_root:
        raise Refused(f"{entry_id}: file is not directly under the store root")
    return entry


def encode(name: str, value: str) -> str:
    if not value or value != value.strip():
        raise Refused(f"{name}: empty value or leading/trailing whitespace")
    # `export NAME=value` is the documented store format; every repository parser accepts it
    # and pit-availability/measure.py accepts only it (docs/secret-storage.md, Storage rules).
    if BARE_VALUE.match(value):
        return f"export {name}={value}\n"
    if QUOTED_VALUE.match(value) and not QUOTED_FORBIDDEN & set(value):
        return f'export {name}="{value}"\n'
    raise Refused(f"{name}: value has a character this store format does not allow")


def open_store(store: Path, uid: int) -> int:
    """Create the store if needed and return a checked O_DIRECTORY|O_NOFOLLOW handle."""
    store.mkdir(mode=0o700, parents=True, exist_ok=True)
    if cs.git_worktree_of(store) is not None:
        raise Refused("store directory is inside a Git worktree")
    try:
        dfd = os.open(store, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        raise Refused("store is not a real directory (symlink or other file)") from None
    info = os.fstat(dfd)
    if info.st_uid != uid:
        os.close(dfd)
        raise Refused("store directory is not owned by you")
    if stat.S_IMODE(info.st_mode) != 0o700:
        os.fchmod(dfd, 0o700)
    return dfd


def existing(dfd: int, name: str, uid: int) -> bool:
    try:
        info = os.stat(name, dir_fd=dfd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode):
        raise Refused("existing credential path is not a regular file")
    if info.st_uid != uid:
        raise Refused("existing credential file is not owned by you")
    return True


def write_atomically(dfd: int, name: str, text: str) -> None:
    tmp = f".{name}.{os.urandom(8).hex()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dfd)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd)
        os.fsync(dfd)
    except BaseException:
        try:
            os.unlink(tmp, dir_fd=dfd)
        except FileNotFoundError:
            pass
        raise


def run(entry_id: str, *, env=None, uid=None, prompt=getpass.getpass, out=sys.stdout,
        root: Path = ROOT) -> int:
    env = os.environ if env is None else env
    uid = os.getuid() if uid is None else uid
    entry = load_entry(entry_id, root, env)
    path = cs.expand_template(entry["store"]["path_template"], env)
    dfd = open_store(path.parent, uid)
    try:
        if existing(dfd, path.name, uid):
            answer = prompt(f"{entry_id}: a stored value exists. Type 'replace' to rotate it (hidden): ")
            if answer.strip() != "replace":
                print(f"{entry_id}: unchanged", file=out)
                return 1
        print(f"{entry['label']}: values are hidden while you type; paste and press Enter.", file=out)
        lines, stored = [], []
        for name in entry["variables"]:
            lines.append(encode(name, prompt(f"  {name}: ")))
            stored.append(name)
        for name in entry["optional_variables"]:
            value = prompt(f"  {name} (optional, Enter to skip): ")
            if value:
                lines.append(encode(name, value))
                stored.append(name)
        hint = KEY_PREFIX_HINT.get(entry_id)
        key_line = next((line for line in lines if line.startswith("export APCA_API_KEY_ID=")), "")
        if hint and key_line and not key_line.split("=", 1)[1].strip().strip('"').startswith(hint):
            print(f"  warning: APCA_API_KEY_ID does not start with {hint}, the usual prefix for this "
                  "account type. Check you pasted the right key.", file=out)
        write_atomically(dfd, path.name, "".join(lines))
    finally:
        os.close(dfd)
    print(f"stored {entry_id}: {', '.join(stored)} -> {entry['store']['path_template']} (0600)", file=out)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("entry_id", help="an operator-supplied id from adoption/credential-inventory.json")
    args = parser.parse_args(argv)
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("refused: run this in an interactive terminal (values are typed, never piped)", file=sys.stderr)
        return 2
    warnings.simplefilter("error", getpass.GetPassWarning)  # never fall back to echoed input
    try:
        return run(args.entry_id)
    except Refused as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    except getpass.GetPassWarning:
        print("refused: this terminal cannot hide input; nothing written", file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        print("\ncancelled; nothing written", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
