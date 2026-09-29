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

`--from-env` is the one form without a terminal. It stores an entry that declares exactly one
variable from this process's environment, where `scripts/kernel_keyring.py exec` puts a key that
lives only in the kernel keyring, so the value never passes through an agent, a prompt or a command
line. It is create-only (it never replaces a file), refuses unless the interpreter was started with
-I, and prints only `<id>: stored`:

    python3 scripts/kernel_keyring.py exec tavily_api_key TAVILY_API_KEY -- python3 -I tools/credentials/set_credential.py tavily --from-env
"""
from __future__ import annotations

import os
import sys

if __name__ == "__main__" and not sys.flags.isolated:
    if "--from-env" in sys.argv[1:]:
        # The value is already in this interpreter's environment, and a start without -I has already honoured
        # PYTHONPATH and the user site directory: a sitecustomize or usercustomize module or a .pth file there
        # ran beside the value. Re-running isolated cannot undo that, so this mode refuses and never re-executes.
        sys.stderr.write("refused: --from-env needs an interpreter started isolated: "
                         "python3 -I tools/credentials/set_credential.py <id> --from-env\n")
        raise SystemExit(2)
    # Re-run isolated (-I): ignore PYTHONPATH, PYTHONSTARTUP and user site-packages, so a
    # poisoned environment cannot shadow getpass or any other module this tool imports.
    os.execv(sys.executable, [sys.executable, "-I", os.path.abspath(__file__), *sys.argv[1:]])

import argparse  # noqa: E402
import getpass  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import stat  # noqa: E402
import warnings  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import credential_status as cs  # noqa: E402  (stdlib-only checker; shares template and worktree rules)

OPERATOR_STATUSES = {"required", "optional", "user_only_paid"}
BARE_VALUE = re.compile(r"^[A-Za-z0-9._+/=:@-]+$")          # no ~ (a sourcing shell would expand it)
QUOTED_VALUE = re.compile(r'^[\x20-\x7e]+$')                 # printable ASCII only
QUOTED_FORBIDDEN = set('"$`\\')
KEY_PREFIX_HINT = {"alpaca-paper": "PK", "alpaca-paper-2": "PK"}


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


def create_exclusively(dfd: int, name: str, text: str) -> None:
    """Write text to a new file `name` in the directory dfd; never replace one that exists.

    The complete, fsynced temporary file gets its final name with os.link, which fails with EEXIST when the
    name exists (os.replace would overwrite it), so the existence check and the creation are one step in the
    kernel. The temporary name is then removed, leaving one link."""
    tmp = f".{name}.{os.urandom(8).hex()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dfd)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd, follow_symlinks=False)
        except FileExistsError:
            raise Refused(f"{name} already exists; --from-env never replaces a stored file") from None
    finally:
        try:
            os.unlink(tmp, dir_fd=dfd)
        except FileNotFoundError:
            pass
    os.fsync(dfd)


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


def run_from_env(entry_id: str, *, env=None, uid=None, out=sys.stdout, root: Path = ROOT,
                 isolated: bool | None = None) -> int:
    """Store the entry's one variable from env (os.environ by default) in a new file; create-only.

    Refused unless the interpreter was started isolated, for an entry that does not declare exactly one
    variable (a pair's provenance cannot be proven from an inherited environment), and for an absent, empty
    or out-of-grammar value. The value is popped from env first, so no child of this process inherits it
    (Linux still shows the start-up environment in /proc/<pid>/environ while this short process runs).
    The only output is `<id>: stored`; no message holds the value or any part of it."""
    env = os.environ if env is None else env
    isolated = bool(sys.flags.isolated) if isolated is None else isolated
    if not isolated:
        raise Refused("--from-env needs an interpreter started isolated: "
                      "python3 -I tools/credentials/set_credential.py <id> --from-env")
    uid = os.getuid() if uid is None else uid
    entry = load_entry(entry_id, root, env)
    declared = entry["variables"] + entry["optional_variables"]
    if len(declared) != 1:
        raise Refused(f"{entry_id}: --from-env stores only an entry with exactly one variable; this one "
                      f"declares {len(declared)}, and a pair's provenance cannot be proven from an inherited "
                      "environment")
    name = declared[0]
    value = env.pop(name, None)
    if value is None:
        raise Refused(f"{name}: not set in this process's environment; nothing written")
    line = encode(name, value)  # refuses an empty, padded or out-of-grammar value without quoting it
    path = cs.expand_template(entry["store"]["path_template"], env)
    dfd = open_store(path.parent, uid)
    try:
        try:
            os.stat(path.name, dir_fd=dfd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:  # checked before the temporary file is written; create_exclusively's link settles a race
            raise Refused(f"{path.name} already exists; --from-env never replaces a stored file "
                          f"(rotate with tools/credentials/open_credential_terminal.sh {entry_id})")
        create_exclusively(dfd, path.name, line)
    finally:
        os.close(dfd)
    print(f"{entry_id}: stored", file=out)
    return 0


def main(argv=None) -> int:
    # No abbreviations: --from would otherwise select --from-env, which the start-up check above does not see.
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0], allow_abbrev=False)
    parser.add_argument("entry_id", help="an operator-supplied id from adoption/credential-inventory.json")
    parser.add_argument("--from-env", action="store_true",
                        help="store the entry's one variable from this process's environment in a new file "
                             "(create-only, no terminal; needs python3 -I)")
    args = parser.parse_args(argv)
    if args.from_env:
        try:
            return run_from_env(args.entry_id)
        except Refused as error:
            print(f"refused: {error}", file=sys.stderr)
            return 2
        except KeyboardInterrupt:
            print("cancelled; check with python3 scripts/credential_status.py", file=sys.stderr)
            return 130
        except Exception as error:  # no traceback: it could quote whatever was being handled
            print(f"failed: unexpected {type(error).__name__}; no value was printed; "
                  "check with python3 scripts/credential_status.py", file=sys.stderr)
            return 1
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
