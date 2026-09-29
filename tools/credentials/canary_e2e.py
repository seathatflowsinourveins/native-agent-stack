#!/usr/bin/env python3
"""Value-free canary proof of the key runner: a synthetic key handed to six consumers by inventory id.

    python3 tools/credentials/canary_e2e.py prepare [--keep-across-restart]
    python3 tools/credentials/canary_e2e.py controls --run <id>
    python3 tools/credentials/canary_e2e.py baseline --run <id>
    python3 tools/credentials/canary_e2e.py consume <consumer> --run <id> [--timeout S] [--model M] [--after-restart]
    python3 tools/credentials/canary_e2e.py decoy --run <id> --consumer <consumer>
    python3 tools/credentials/canary_e2e.py verify --run <id> [--consumer <consumer>]
    python3 tools/credentials/canary_e2e.py settle --run <id> [--max-wait S] [--interval S]
    python3 tools/credentials/canary_e2e.py scan --pass 1|2 --run <id> [--with-sudo]
    python3 tools/credentials/canary_e2e.py scan --sink omniroute --run <id>     # user-run, in your own terminal
    python3 tools/credentials/canary_e2e.py report --run <id> [--model <consumer>=<model id>]...
    python3 tools/credentials/canary_e2e.py cleanup --run <id>

The consumers are fresh-claude-session and its subagent (one `claude -p`), workflow-child (the coordinator runs
tools/credentials/canary_workflow.js with the Workflow tool), codex-exec, omniroute-lane (Codex through the keyless
OmniRoute profile) and systemd-user-unit (systemd-run, twice, the second time with the probe's --leak-check).

`prepare` makes one independent canary per consumer: 'CNRYE2E', 32 hex characters and one each of '+', '/' and '=' at
random positions, inside set_credential.py's bare-value grammar. It also makes a nonce per consumer and the decoys. A
canary exists in two places only: the canary-e2e store file, written with set_credential.py's store checks and
create-only writer (imported) while its consumer runs, and a 0600 pattern file in a 0700 run directory on the runtime
tmpfs. A canary's patterns are the forms credential_run.py masks (its encoded_forms: raw, base64 and base64url
interiors at three byte alignments, percent, JSON and hex). No canary, pattern or tag is printed, logged or put in an
argv: scanners read a pattern file (rg -f) or get patterns bound as SQL parameters, the one Loki query holds labels
and a time range only, and every output line is a sink id, a count and a path class.

`consume` runs one consumer at a time: write that consumer's canary to the store file, run the consumer, remove the
file. The probe prints only an HMAC tag bound to the run, the consumer and a fresh nonce, which `verify` checks, so a
stale or copied tag fails. Each Claude and Codex run carries its own decoy, echoed by a command that fails on purpose
(RTK keeps output only for failed commands), so each sink's positive control comes from the same run. While a consumer
runs, /proc/<pid>/cmdline of this user's processes and the transient unit files are sampled for the canaries (counts
only); /proc/<pid>/environ is never read. `settle` times the arrival of the decoys in the asynchronous sinks and sets
when scan passes 1 and 2 are due. A sink whose control decoy was planted and is not found is reported as "not a sink,
or scanned wrongly", never as clean, and the scan exits 1. Guard-denied stores (the OmniRoute data directories, Codex
shell_snapshots, ~/.docker/config.json) are scanned only by `scan --sink omniroute`, from the user's own terminal.

What a zero proves: no raw or listed-encoded copy of this run's canaries is in the scanned sinks whose positive control
passed, at the two scan times, for the cooperative, id-only path of the six consumers. Five consumers print only a
tag, so end-to-end masking is shown only by the systemd unit's --leak-check arm, whose output returns through a pipe to
this process and never to a client sink. Not covered: remote sinks (provider retention; GitHub beyond gh api reads),
Windows-side stores, transformed forms, process memory and swap, adversarial or careless agents, unscanned sinks,
OmniRoute unless the user ran its scan, and future client versions.

Exit status: 0 when the step passed; 1 for a failed check or a refusal; 2 for a usage error, a scan pass that is not
due yet, or a user-run scan without a terminal. Built from the research_sinks scan plan and verify_sinks of the D1
key-management design (2026-09-29; no upstream harness was found), set_credential.py's writer, credential_run.py's
encoded forms and scripts/credential_boot_receipt.py's receipt writer.
"""
from __future__ import annotations

import os
import sys

if __name__ == "__main__" and not sys.flags.isolated:
    # Re-run isolated (-I), as set_credential.py does: PYTHONPATH, PYTHONSTARTUP and the user site directory then cannot
    # shadow a module this tool imports.
    os.execv(sys.executable, [sys.executable, "-I", os.path.abspath(__file__), *sys.argv[1:]])

import argparse  # noqa: E402
import bz2  # noqa: E402
import functools  # noqa: E402
import glob  # noqa: E402
import hashlib  # noqa: E402
import hmac  # noqa: E402
import json  # noqa: E402
import lzma  # noqa: E402
import platform  # noqa: E402
import queue  # noqa: E402
import re  # noqa: E402
import resource  # noqa: E402
import secrets  # noqa: E402
import shutil  # noqa: E402
import signal  # noqa: E402
import sqlite3  # noqa: E402
import stat  # noqa: E402
import subprocess  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import urllib.parse  # noqa: E402
import urllib.request  # noqa: E402
import zlib  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
for _directory in (ROOT / "tools" / "credentials", ROOT / "scripts"):
    if str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))
import canary_probe as probe  # noqa: E402  (tag, run directories, leak forms)
import credential_boot_receipt as receipts  # noqa: E402  (private_directory, write_receipt: dot-file and os.link)
import credential_run as runner  # noqa: E402  (encoded_forms, child_environment, injectable)
import credential_status as cs  # noqa: E402  (inventory schema and store paths)
import set_credential as writer  # noqa: E402  (value grammar, store checks and the create-only writer)

ENTRY_ID = "canary-e2e"
VARIABLE = probe.VARIABLE
STATUS, CLASS = "test_only", "test_canary"
CANARY_PREFIX, DECOY_PREFIX = "CNRYE2E", "DCOYE2E"
CONSUMERS = probe.CONSUMERS
UNIT = "systemd-user-unit"
DECOY_OF = {"fresh-claude-session": "claude", "subagent": "subagent", "workflow-child": "wf", "codex-exec": "codex",
            "omniroute-lane": "omni"}
PLANTED = ("claude", "subagent", "wf", "codex", "omni", "journal", "loki")
DECOYS = PLANTED + ("text", "gz", "sqlite", "git")
# What finding a control decoy in a sink shows: a consumer's own decoy covers that consumer's path; the journal and Loki
# decoys are planted by the harness itself and show only that the sink is read correctly, for any consumer.
CONTROL_PROVES = {"claude": ("fresh-claude-session",), "subagent": ("subagent",), "wf": ("workflow-child",),
                  "codex": ("codex-exec",), "omni": ("omniroute-lane",), "journal": CONSUMERS, "loki": CONSUMERS}
CLASS_OF_KIND = {"files": ("text", "gz"), "sqlite": ("text", "gz", "sqlite"), "git": ("git",), "journal": ("journal",)}
KINDS = {"files", "sqlite", "git", "journal", "loki", "github", "manager_environment", "covered", "not_scanned",
         "during_consume"}
SCANNABLE = {"files", "sqlite", "git", "journal", "loki", "github", "manager_environment"}
ACCESS = {"agent", "sudo", "user_run", "not_scanned"}
USER_RUN_GROUP = "omniroute"
SET_NAME = re.compile(r"[cd]-[a-z-]+")
SINK_ID = re.compile(r"[A-Z][A-Za-z0-9-]{1,63}")
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/\[\]-]{0,99}")
VERSION = re.compile(r"[\w .()+~:/,-]{1,80}")
RUN_ID_SAMPLE = "canary-00000000t000000z-000000"
MARKER = f"[REDACTED:{VARIABLE}]".encode("ascii")
PARTIAL = f"[REDACTED-PARTIAL:{VARIABLE}]".encode("ascii")
SINKS_FILE = Path(__file__).resolve().with_name("canary_sinks.json")
HARNESS_REL, PROBE_REL, RUNNER_REL = ("tools/credentials/canary_e2e.py", "tools/credentials/canary_probe.py",
                                      "tools/credentials/credential_run.py")
WORKFLOW_REL = "tools/credentials/canary_workflow.js"
PROC_ROOT = Path("/proc")
CLAUDE_MODEL, SUBAGENT_TYPE = "sonnet", "source-scout"  # a pure probe: the command-wrapper role of the role table
CODEX_MODEL = "gpt-6-astra"  # pinned for codex-exec; the OmniRoute lane runs its own profile's model
OMNIROUTE_PROFILE = "omniroute"
# The keyless loopback gateway needs a non-empty key variable (adoption/templates/codex.omniroute.config.toml); this
# placeholder is not a key, and the profile's filter keeps it from every command the model runs.
OMNIROUTE_PLACEHOLDER = {"OMNIROUTE_API_KEY": "keyless-loopback-placeholder"}
CONSUME_TIMEOUT, WORKFLOW_TIMEOUT = 900.0, 1800.0
SAMPLE_SECONDS = 0.05
SETTLE_MAX_WAIT, SETTLE_INTERVAL = 1800.0, 30.0
MARGIN_MIN, MARGIN_MAX, PASS2_EXTRA, RETENTION_SAFETY = 30.0, 600.0, 600.0, 3600.0
WINDOW_SLACK = 3600  # a WSL clock can step back: time-bounded reads start an hour before the run
LOKI_QUERY, LOKI_LIMIT, LOKI_PAGES = '{service_name=~".+"}', 5000, 200
GH_READS = ("repos/{owner}/{repo}/pulls?state=all&sort=updated&direction=desc&per_page=50",
            "repos/{owner}/{repo}/issues/comments?since={since}&per_page=100",
            "repos/{owner}/{repo}/pulls/comments?since={since}&per_page=100",
            "repos/{owner}/{repo}/commits?since={since}&per_page=100")
DB_SUFFIXES = (".db", ".sqlite", ".sqlite3")
SQLITE_MAGIC = b"SQLite format 3\x00"
MAGIC = ((b"\x1f\x8b", "gzip"), (b"\x28\xb5\x2f\xfd", "zstd"), (b"\xfd7zXZ\x00", "xz"), (b"BZh", "bz2"),
         (b"\x78\x01", "zlib"), (b"\x78\x5e", "zlib"), (b"\x78\x9c", "zlib"), (b"\x78\xda", "zlib"))
MAX_DECOMPRESSED = 64 << 20
SQL_COPY_LIMIT = 256 << 20
SQL_TERMS = 400  # OR terms per query, under SQLite's 1000 expression depth and 999 host parameters of old builds
ZERO_CLAIM = ("A zero means that no raw or listed-encoded copy (the forms credential_run.py masks) of a canary of this "
              "run was found in the scanned sinks whose positive control passed, at the two scan times, for the "
              "cooperative, id-only path of the six consumers. Five consumers print only a tag, so it does not show "
              "masking; end-to-end masking is shown only by the systemd unit's --leak-check arm, whose output returns "
              "through a pipe to the harness and never to a client sink.")
NOT_COVERED = ("S47-forwarded-model-providers: Anthropic and OpenAI retention",
               "S48-forwarded-github beyond the gh api reads", "W01-windows-clipboard-history",
               "W02-windows-terminal-scrollback", "W03-wsl-swap-and-pagefile", "transformed forms",
               "process memory and swap", "adversarial or careless agents: the probe is cooperative",
               "sinks without a passed control or not scanned", "user-run sinks unless their scan ran",
               "future client versions")


class Refused(Exception):
    """A safety rule or a missing step stopped the command; the message holds no value and no host path."""

    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


class UsageError(Exception):
    """Bad arguments (exit 2)."""


# -- context ---------------------------------------------------------------------------------------------------------

class Context:
    """Where this run lives and what it may touch: the environment (XDG and store paths come from it), the checkout,
    the sink table, the /proc to sample, the output streams, the clock and the terminal test. Tests pass their own."""

    def __init__(self, env=None, *, root=ROOT, sinks_path=SINKS_FILE, proc_root=PROC_ROOT, out=None, err=None,
                 clock=None, tty=None, uid=None):
        self.env = dict(os.environ if env is None else env)
        self.root = Path(root)
        self.sinks_path = Path(sinks_path)
        self.proc_root = Path(proc_root)
        self.out = sys.stdout if out is None else out
        self.err = sys.stderr if err is None else err
        self.clock = time.time if clock is None else clock
        self.tty = (lambda: sys.stdin.isatty() and sys.stdout.isatty()) if tty is None else tty
        self.uid = os.getuid() if uid is None else uid
        self.secrets: list = []  # canary material loaded in this process: no printed line may hold any of it
        self._entry = None
        self._table = None

    def which(self, name: str):
        return shutil.which(name, path=self.env.get("PATH") or os.defpath)

    def hold(self, values) -> None:
        self.secrets.extend(v if isinstance(v, bytes) else v.encode("ascii") for v in values)

    def say(self, text: str) -> None:
        self._write(self.out, text)

    def warn(self, text: str) -> None:
        self._write(self.err, text)

    def _write(self, stream, text: str) -> None:
        data = text.encode("utf-8", "replace")
        if any(secret in data for secret in self.secrets):
            text = "[line withheld: it held canary material]"
        stream.write(text + "\n")
        stream.flush()

    @property
    def entry(self):
        if self._entry is None:
            self._entry = canary_entry(self.root)
        return self._entry

    @property
    def table(self) -> dict:
        if self._table is None:
            try:
                table = json.loads(self.sinks_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise Refused("the sink table is unreadable") from None
            errors = table_errors(table)
            if errors:
                raise Refused(f"the sink table is invalid ({len(errors)} errors): {errors[0]}")
            self._table = table
        return self._table


def iso(epoch) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_or_none(epoch):
    return iso(epoch) if isinstance(epoch, (int, float)) else None


# -- inventory, store and run directory ------------------------------------------------------------------------------

def canary_entry(root: Path = ROOT) -> tuple:
    """(entry, inventory): the canary-e2e row, validated by scripts/credential_status.py's schema."""
    try:
        inventory = json.loads((root / cs.INVENTORY).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Refused("the inventory is unreadable; check with python3 scripts/credential_status.py") from None
    errors = cs.inventory_errors(inventory, root)
    if errors:
        raise Refused(f"invalid inventory ({len(errors)} errors); check with python3 scripts/credential_status.py")
    entry = next((e for e in inventory["entries"] if e["id"] == ENTRY_ID), None)
    if (entry is None or entry["status"] != STATUS or entry["class"] != CLASS or entry["variables"] != [VARIABLE]
            or entry["optional_variables"] or not runner.injectable(entry)):
        raise Refused(f"the inventory has no {ENTRY_ID} row of class {CLASS} and status {STATUS} with the one "
                      f"variable {VARIABLE}")
    return entry, inventory


def store_file(ctx: Context) -> Path:
    root = cs.expand_template(cs.STORE_ROOT, ctx.env)
    path = cs.expand_template(ctx.entry[0]["store"]["path_template"], ctx.env)
    if path.parent != root:
        raise Refused("the canary file is not directly under the store root")
    return path


STORE_EXISTS = ("a canary store file exists already: an earlier consumer or run was not cleaned up "
                "(run cleanup for that run)")


def arm(ctx: Context, run_dir: Path, consumer: str) -> None:
    """Write the consumer's canary to the store file through set_credential.py's checked, create-only writer."""
    path = store_file(ctx)
    line = writer.encode(VARIABLE, set_value(read_set(run_dir, f"c-{consumer}")))
    try:
        dfd = writer.open_store(path.parent, ctx.uid)
    except writer.Refused as refusal:
        raise Refused(str(refusal)) from None
    try:
        if writer.existing(dfd, path.name, ctx.uid):
            raise Refused(STORE_EXISTS)
        try:
            writer.create_exclusively(dfd, path.name, line)
        except writer.Refused:
            raise Refused(STORE_EXISTS) from None
    except writer.Refused as refusal:
        raise Refused(str(refusal)) from None
    finally:
        os.close(dfd)


def disarm(ctx: Context) -> bool:
    """Unlink the canary file, and only it, through a no-follow handle on the store directory. True when removed."""
    path = store_file(ctx)
    try:
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return False
    except OSError:
        raise Refused("the store is not a real directory; nothing removed") from None
    try:
        if os.fstat(dfd).st_uid != ctx.uid:
            raise Refused("the store directory is not yours; nothing removed")
        try:
            info = os.stat(path.name, dir_fd=dfd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        if not stat.S_ISREG(info.st_mode) or info.st_uid != ctx.uid:
            raise Refused("the canary store path is not a regular file of yours; left in place")
        os.unlink(path.name, dir_fd=dfd)
        os.fsync(dfd)
        return True
    finally:
        os.close(dfd)


def store_present(ctx: Context) -> bool:
    return os.path.lexists(store_file(ctx))


def run_directory(ctx: Context, run: str) -> Path:
    if not probe.RUN_ID.fullmatch(run or ""):
        raise UsageError("--run is not a canary run id (prepare prints one)")
    for directory in probe.run_directories(run, ctx.env):
        try:
            info = os.lstat(directory)
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != ctx.uid or stat.S_IMODE(info.st_mode) & 0o077:
            raise Refused("the run directory is not a private directory of yours")
        return directory
    raise Refused("no such run on this host (prepare makes one; a runtime run does not survive a restart)")


def private_tree(path: Path) -> None:
    """Create path and its missing parents as 0700 directories; path itself must be new."""
    missing, current = [], path
    while not os.path.lexists(current):
        missing.append(current)
        current = current.parent
    if path not in missing:
        raise Refused("the run directory exists already")
    for directory in reversed(missing):
        os.mkdir(directory, 0o700)
        os.chmod(directory, 0o700)


def check_runtime_base(ctx: Context, run_dir: Path) -> None:
    """The runtime directory (XDG_RUNTIME_DIR) must be a real 0700 directory of this user: the tmpfs of the XDG spec."""
    base = run_dir.parents[2]
    try:
        info = os.lstat(base)
    except OSError:
        raise Refused("the runtime directory does not exist (XDG_RUNTIME_DIR); use --keep-across-restart") from None
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != ctx.uid or stat.S_IMODE(info.st_mode) & 0o077:
        raise Refused("the runtime directory (XDG_RUNTIME_DIR) is not a private directory of yours")


def write_private(path: Path, data: bytes) -> None:
    """Write data to path atomically, 0600, never through a link."""
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)


def write_json(path: Path, value) -> None:
    write_private(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        raise Refused(f"a result file of this run is unreadable: {path.name}") from None


def result_path(run_dir: Path, name: str) -> Path:
    return run_dir / "results" / f"{name}.json"


def load_state(run_dir: Path) -> dict:
    state = read_json(run_dir / "state.json")
    if not isinstance(state, dict):
        raise Refused("the run directory has no state file")
    return state


def rotate_nonce(run_dir: Path, consumer: str) -> None:
    """A fresh nonce for the consumer's next arming; an older tag file is removed, and would no longer verify."""
    write_private(run_dir / "nonce" / consumer, (secrets.token_hex(16) + "\n").encode("ascii"))
    try:
        os.unlink(run_dir / "tags" / f"{consumer}.tag")
    except FileNotFoundError:
        pass


# -- canaries, decoys and patterns -----------------------------------------------------------------------------------

def new_canary() -> str:
    body = list(secrets.token_hex(16))
    for symbol in "+/=":
        body.insert(secrets.randbelow(len(body) + 1), symbol)
    value = CANARY_PREFIX + "".join(body)
    if writer.BARE_VALUE.match(value) is None:  # a guard on the construction above, never expected to fire
        raise Refused("a canary left the store writer's grammar")
    return value


def new_decoy() -> str:
    return DECOY_PREFIX + secrets.token_hex(16)


def forms(value: str) -> list:
    """The listed forms of value: credential_run.py's encoded_forms, deduplicated, raw first. The masked forms are the
    scanned forms."""
    found = []
    for form in runner.encoded_forms(value.encode("ascii")):
        if len(form) >= runner.LENGTH_MIN and form not in found and b"\n" not in form:
            found.append(form)
    return found


def write_set(run_dir: Path, name: str, value: str) -> None:
    write_private(run_dir / "patterns" / f"{name}.pat", b"\n".join(forms(value)) + b"\n")


def read_set(run_dir: Path, name: str) -> list:
    if not SET_NAME.fullmatch(name):
        raise Refused("not a pattern set of this run")
    try:
        data = (run_dir / "patterns" / f"{name}.pat").read_bytes()
    except OSError:
        raise Refused("a pattern file of this run is missing") from None
    return [line for line in data.split(b"\n") if line]


def set_value(patterns: list) -> str:
    """A set's raw value: its first pattern."""
    return patterns[0].decode("ascii")


def load_sets(run_dir: Path) -> dict:
    sets = {}
    for path in sorted((run_dir / "patterns").iterdir()):
        if path.suffix == ".pat" and SET_NAME.fullmatch(path.stem):
            sets[path.stem] = read_set(run_dir, path.stem)
    return sets


def canary_sets(sets: dict) -> dict:
    return {name: patterns for name, patterns in sets.items() if name.startswith("c-")}


def pattern_file(run_dir: Path, names) -> Path:
    """One pattern file for the union of the named sets (a set alone is its own file)."""
    names = sorted(set(names))
    if len(names) == 1:
        return run_dir / "patterns" / f"{names[0]}.pat"
    key = hashlib.sha256("\n".join(names).encode("ascii")).hexdigest()[:12]
    path = run_dir / "patterns" / f".u-{key}.pat"
    if not path.exists():
        lines = dict.fromkeys(line for name in names for line in read_set(run_dir, name))
        write_private(path, b"\n".join(lines) + b"\n")
    return path


@functools.lru_cache(maxsize=None)
def family_anchors(prefix: str) -> tuple:
    """For each listed form, the head that every value starting with prefix shares: the longest common prefix of that
    form over bodies that differ in their first character. () when a head would be shorter than 4 bytes."""
    tail = secrets.token_hex(16)[1:]
    samples = [runner.encoded_forms((prefix + first + tail).encode("ascii")) for first in "+/=09af"]
    anchors = []
    for column in zip(*samples):
        common = os.path.commonprefix(list(column))
        if len(common) < 4:
            return ()
        anchors.append(common)
    return tuple(dict.fromkeys(anchors))


class Matcher:
    """Which pattern sets a record holds. A record is tested in full only when it holds an anchor, the prefix-derived
    head of a form; the anchors are used only when every pattern of every set holds one, so the prefilter can never
    hide a pattern."""

    def __init__(self, sets: dict):
        self.sets = {name: list(patterns) for name, patterns in sets.items() if patterns}
        anchors = []
        if any(name.startswith("c-") for name in self.sets):
            anchors += family_anchors(CANARY_PREFIX)
        if any(name.startswith("d-") for name in self.sets):
            anchors += family_anchors(DECOY_PREFIX)
        everything = [pattern for patterns in self.sets.values() for pattern in patterns]
        self.anchors = list(dict.fromkeys(anchors)) if anchors and all(
            any(anchor in pattern for anchor in anchors) for pattern in everything) else []

    def hits(self, data: bytes) -> set:
        if self.anchors and not any(anchor in data for anchor in self.anchors):
            return set()
        return {name for name, patterns in self.sets.items() if any(pattern in data for pattern in patterns)}


# -- sink table and paths --------------------------------------------------------------------------------------------

def table_errors(table) -> list:
    if not isinstance(table, dict) or table.get("schema_version") != 1 or not isinstance(table.get("sinks"), list):
        return ["table: expected schema_version 1 and a sinks array"]
    errors, seen = [], set()
    for index, sink in enumerate(table["sinks"]):
        label = f"sinks[{index}]"
        if not isinstance(sink, dict):
            errors.append(f"{label}: expected an object")
            continue
        identifier = sink.get("id")
        if not isinstance(identifier, str) or not SINK_ID.fullmatch(identifier) or identifier in seen:
            errors.append(f"{label}: missing, malformed or repeated id")
        seen.add(identifier)
        if sink.get("kind") not in KINDS:
            errors.append(f"{label}: unknown kind")
        elif sink["kind"] == "loki" and not isinstance(sink.get("url"), str):
            errors.append(f"{label}: a loki sink needs a url")
        elif sink["kind"] == "journal" and sink.get("scope") not in ("user", "system"):
            errors.append(f"{label}: a journal sink needs scope user or system")
        if sink.get("access") not in ACCESS:
            errors.append(f"{label}: unknown access")
        if not (isinstance(sink.get("paths"), list) and all(isinstance(p, str) for p in sink["paths"])):
            errors.append(f"{label}: paths must be strings")
        controls = sink.get("controls")
        if not (isinstance(controls, list) and all(c in PLANTED for c in controls)):
            errors.append(f"{label}: controls must name planted decoys ({', '.join(PLANTED)})")
        if not isinstance(sink.get("async"), bool) or not isinstance(sink.get("persisted"), bool):
            errors.append(f"{label}: async and persisted must be booleans")
    for key in ("exclude", "exclude_names"):
        if not (isinstance(table.get(key, []), list) and all(isinstance(p, str) for p in table.get(key, []))):
            errors.append(f"{key}: expected strings")
    return errors


def expand(ctx: Context, template: str) -> list:
    """Paths of a table template: credential_status.py's ${NAME:-default} and $HOME, $CHECKOUT, $UID and globs."""
    text = template.replace("$CHECKOUT", str(ctx.root)).replace("$UID", str(ctx.uid))
    path = str(cs.expand_template(text, ctx.env))
    if any(character in path for character in "*?["):
        return [Path(match) for match in sorted(glob.glob(path, recursive=True))]
    return [Path(path)]


def real(path) -> Path:
    return Path(os.path.realpath(path))


def split_roots(path: Path, excluded: list) -> list:
    """path, or the parts of it that hold no excluded path, so that a scanner is never handed an excluded file.

    A path inside an excluded one gives nothing; a directory that contains one is replaced by its children, the
    excluded ones left out. Symbolic links among those children are skipped, as rg skips them while it walks."""
    resolved = real(path)
    if any(resolved == item or item in resolved.parents for item in excluded):
        return []
    if not any(resolved in item.parents for item in excluded):
        return [resolved]
    try:
        children = sorted(os.scandir(resolved), key=lambda child: child.name)
    except OSError:
        return []  # a directory holding an excluded path is never handed over whole
    parts = []
    for child in children:
        if not child.is_symlink():
            parts += split_roots(Path(child.path), excluded)
    return parts


def exclusions(ctx: Context, agent_pass: bool) -> list:
    """The table's excluded paths, the store, this harness's run and receipt directories and, for an agent-run pass,
    every user-run sink's paths."""
    table = ctx.table
    paths = [p for template in table.get("exclude", []) for p in expand(ctx, template)]
    paths.append(cs.expand_template(cs.STORE_ROOT, ctx.env))
    runtime_dir, keep_dir = probe.run_directories(RUN_ID_SAMPLE, ctx.env)
    paths += [runtime_dir.parent, keep_dir.parent.parent]
    if agent_pass:
        for sink in table["sinks"]:
            if sink.get("access") == "user_run":
                paths += [p for template in sink.get("paths", []) if "**" not in template
                          for p in expand(ctx, template)]
    return [real(p) for p in paths]


def launch_environment(ctx: Context, extra=None) -> dict:
    """The caller's environment minus every inventory variable and must_not_be_set name (credential_run.py's own
    rule), plus extra. No client sandbox or scrub setting is added."""
    environment = runner.child_environment(ctx.entry[1], {}, ctx.env)
    environment.update(extra or {})
    return environment


def scanner_environment(ctx: Context) -> dict:
    environment = {k: v for k, v in launch_environment(ctx).items() if not k.startswith("GIT_")}
    environment["LC_ALL"] = "C"
    return environment


# -- scanners --------------------------------------------------------------------------------------------------------

def rg_command(ctx: Context, globs=(), sudo: bool = False) -> list:
    rg = ctx.which("rg")
    if rg is None:
        raise Refused("rg (ripgrep) is not on PATH; the scanners need it")
    argv = []
    if sudo:
        elevate = ctx.which("sudo")
        if elevate is None:
            raise Refused("sudo is not on PATH")
        argv += [elevate, "-n"]
    for tool, options in (("nice", ["-n", "19"]), ("ionice", ["-c3"])):
        found = ctx.which(tool)
        if found:
            argv += [found, *options]
    argv += [rg, "--no-config", "-uuu", "-a", "-z"]
    for name in globs:
        argv += ["-g", f"!{name}"]
    return argv


def files_holding(ctx: Context, patterns: Path, paths: list, globs=(), sudo: bool = False) -> tuple:
    """(files under paths that hold a pattern of the file, unreadable paths). The paths are for this process only."""
    found, errors = [], 0
    for start in range(0, len(paths), 256):
        chunk = [str(p) for p in paths[start:start + 256]]
        result = subprocess.run(rg_command(ctx, globs, sudo) + ["-l", "-F", "-f", str(patterns), "--", *chunk],
                                stdin=subprocess.DEVNULL, capture_output=True, env=scanner_environment(ctx))
        found += [line for line in result.stdout.decode("utf-8", "surrogateescape").split("\n") if line]
        errors += sum(1 for line in result.stderr.splitlines() if line.strip())
    return found, errors


def filescan(ctx: Context, run_dir: Path, names, paths: list, globs=(), sudo: bool = False) -> tuple:
    """({set: [files]}, unreadable): one rg pass with the union of the sets, then one per set over the files it found."""
    hits = {name: [] for name in names}
    if not paths:
        return hits, 0
    candidates, errors = files_holding(ctx, pattern_file(run_dir, names), paths, globs, sudo)
    if candidates:
        for name in names:
            hits[name] = files_holding(ctx, pattern_file(run_dir, [name]), candidates, (), sudo)[0]
    return hits, errors


def stream_count(ctx: Context, producer: list, patterns: Path, cwd=None) -> tuple:
    """(lines of the producer's output that hold a pattern, 1 when the producer or rg failed)."""
    rg = ctx.which("rg")
    if rg is None:
        raise Refused("rg (ripgrep) is not on PATH; the scanners need it")
    environment = scanner_environment(ctx)
    with subprocess.Popen(producer, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          env=environment, cwd=cwd) as source:
        result = subprocess.run([rg, "--no-config", "-a", "-c", "-F", "-f", str(patterns), "-"], stdin=source.stdout,
                                capture_output=True, env=environment)
        source.stdout.close()
        source.wait()
    text = result.stdout.strip()
    return (int(text) if text.isdigit() else 0), int(source.returncode != 0 or result.returncode not in (0, 1))


def count_lines(ctx: Context, run_dir: Path, names, producer: list, cwd=None) -> tuple:
    """({set: lines}, error): one pass with the union, then one pass per set only when the union found a line."""
    total, error = stream_count(ctx, producer, pattern_file(run_dir, names), cwd)
    counts = {name: 0 for name in names}
    if total:
        for name in names:
            counts[name] = stream_count(ctx, producer, pattern_file(run_dir, [name]), cwd)[0]
    return counts, error


def decompressed(data: bytes) -> tuple:
    """(plain bytes or None, undecodable) for a value that starts with a compression format's magic bytes."""
    for magic, codec in MAGIC:
        if not data.startswith(magic):
            continue
        try:
            if codec == "gzip":
                return zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(data, MAX_DECOMPRESSED), False
            if codec == "zlib":
                return zlib.decompressobj().decompress(data, MAX_DECOMPRESSED), False
            if codec == "xz":
                return lzma.LZMADecompressor().decompress(data, MAX_DECOMPRESSED), False
            if codec == "bz2":
                return bz2.BZ2Decompressor().decompress(data, MAX_DECOMPRESSED), False
            return zstd_decompressed(data)
        except (zlib.error, lzma.LZMAError, OSError, EOFError, ValueError):
            return None, codec == "zstd"
    return None, False


def zstd_decompressed(data: bytes) -> tuple:
    try:
        from compression import zstd  # Python 3.14
        return zstd.ZstdDecompressor().decompress(data, MAX_DECOMPRESSED), False
    except ImportError:
        pass
    try:
        import zstandard  # an optional third-party module
        return zstandard.ZstdDecompressor().decompressobj().decompress(data)[:MAX_DECOMPRESSED], False
    except ImportError:
        return None, True  # counted as undecodable, never as clean


def as_bytes(cell):
    if cell is None:
        return None
    if isinstance(cell, (bytes, bytearray, memoryview)):
        return bytes(cell)
    return str(cell).encode("utf-8", "surrogatepass")


def quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def is_sqlite(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            return handle.read(16) == SQLITE_MAGIC
    except OSError:
        return False


def sql_scan_file(ctx: Context, path: Path, matcher: Matcher, run_dir: Path) -> dict:
    """Cells of one database that hold a pattern, per set. Opened read-only (not immutable, so committed WAL frames
    are read); the anchors and compression magics are bound parameters of a prefilter, and a candidate cell is matched
    here, decompressed first when it starts with gzip, zlib, xz, bz2 or zstd magic. A database that cannot be opened
    read-only and is small enough is read from a copy in the run directory, which is then deleted."""
    info = {"counts": {name: 0 for name in matcher.sets}, "errors": 0, "undecodable": 0}
    try:
        connection = sqlite3.connect(f"file:{urllib.parse.quote(str(path))}?mode=ro", uri=True, timeout=5)
        connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
        copy = None
    except sqlite3.Error:
        copy = copied_database(path, run_dir)
        if copy is None:
            info["errors"] += 1
            return info
        connection = sqlite3.connect(str(copy / path.name), timeout=5)
    try:
        connection.execute("PRAGMA query_only = 1")
        tables = connection.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table'").fetchall()
        virtual = [name for name, sql in tables if (sql or "").upper().startswith("CREATE VIRTUAL TABLE")]
        tests = [("instr", anchor) for anchor in matcher.anchors] + [("magic", magic) for magic, _ in MAGIC]
        for name, _sql in tables:
            if name.startswith("sqlite_") or any(name.startswith(v + "_") for v in virtual):
                continue  # internal and shadow tables: a virtual table is read through itself
            try:
                columns = [row[1] for row in connection.execute(f"PRAGMA table_info({quoted(name)})")]
                per_query = max(1, SQL_TERMS // max(1, len(tests))) if matcher.anchors else len(columns) or 1
                for start in range(0, len(columns), per_query):
                    group = columns[start:start + per_query]
                    clauses, parameters = [], []
                    for column in group:
                        cast = f"CAST({quoted(column)} AS BLOB)"
                        for how, needle in tests:
                            clauses.append(f"instr({cast}, ?) > 0" if how == "instr"
                                           else f"substr({cast}, 1, {len(needle)}) = ?")
                            parameters.append(needle)
                    where = " OR ".join(clauses) if matcher.anchors else "1"
                    select = ", ".join(quoted(column) for column in group)
                    for row in connection.execute(f"SELECT {select} FROM {quoted(name)} WHERE {where}", parameters):
                        for cell in row:
                            data = as_bytes(cell)
                            if data is None:
                                continue
                            found = matcher.hits(data)
                            plain, undecodable = decompressed(data)
                            if plain is not None:
                                found |= matcher.hits(plain)
                            info["undecodable"] += int(undecodable)
                            for set_name in found:
                                info["counts"][set_name] += 1
            except sqlite3.Error:
                info["errors"] += 1
    except sqlite3.Error:
        info["errors"] += 1
    finally:
        connection.close()
        if copy is not None:
            shutil.rmtree(copy, ignore_errors=True)
    return info


def copied_database(path: Path, run_dir: Path):
    """A private copy of a database and its WAL in the run directory, or None when it is too large or unreadable."""
    try:
        size = sum(os.path.getsize(p) for p in (path, Path(f"{path}-wal")) if p.exists())
        if size > SQL_COPY_LIMIT:
            return None
        directory = run_dir / "scratch" / f"sqlcopy-{secrets.token_hex(4)}"
        os.mkdir(directory, 0o700)
        shutil.copyfile(path, directory / path.name)
        if Path(f"{path}-wal").exists():
            shutil.copyfile(f"{path}-wal", directory / f"{path.name}-wal")
        return directory
    except OSError:
        return None


def database_files(parts: list, globs=()) -> list:
    found = []
    for part in parts:
        if part.is_file():
            if part.name.endswith(DB_SUFFIXES) and is_sqlite(part):
                found.append(part)
            continue
        for directory, directories, files in os.walk(part):
            directories[:] = [d for d in directories if d not in globs]
            for name in files:
                path = Path(directory, name)
                if name.endswith(DB_SUFFIXES) and not path.is_symlink() and is_sqlite(path):
                    found.append(path)
    return found


def sqlite_sink(ctx: Context, run_dir: Path, names, sets: dict, parts: list, globs, sudo: bool) -> dict:
    """SQL cells, plus a raw pass over every file of the sink (databases and their WAL included) as a second net; a
    raw hit in a database file whose SQL scan already counted that set is not counted twice."""
    matcher = Matcher({name: sets[name] for name in names})
    cells = {name: 0 for name in names}
    counted = {name: set() for name in names}
    errors = undecodable = 0
    for database in database_files(parts, globs):
        result = sql_scan_file(ctx, database, matcher, run_dir)
        errors += result["errors"]
        undecodable += result["undecodable"]
        for name, count in result["counts"].items():
            cells[name] += count
            if count:
                counted[name].update(f"{database}{suffix}" for suffix in ("", "-wal", "-shm", "-journal"))
    raw, raw_errors = filescan(ctx, run_dir, names, parts, globs, sudo)
    counts = {name: cells[name] + sum(1 for f in raw[name] if f not in counted[name]) for name in names}
    return {"status": "scanned", "counts": counts, "unreadable": errors + raw_errors + undecodable}


def git_common_dir(ctx: Context, part: Path):
    git = ctx.which("git")
    if git is None or not part.is_dir():
        return None
    result = subprocess.run([git, "-C", str(part), "rev-parse", "--git-common-dir"], stdin=subprocess.DEVNULL,
                            capture_output=True, env=scanner_environment(ctx), timeout=60)
    if result.returncode != 0:
        return None
    common = Path(result.stdout.decode("utf-8", "surrogateescape").strip())
    return real(common if common.is_absolute() else part / common)


def git_sink(ctx: Context, run_dir: Path, names, parts: list, seen_git: set) -> dict:
    """Every object of each repository (cat-file --batch-all-objects: loose, packed, unreachable), and its reflogs."""
    counts = {name: 0 for name in names}
    errors, repositories = 0, 0
    git = ctx.which("git")
    for part in parts:
        common = git_common_dir(ctx, part)
        if common is None:
            continue
        repositories += 1
        if common in seen_git:
            continue
        seen_git.add(common)
        objects, error = count_lines(ctx, run_dir, names,
                                     [git, "--git-dir", str(common), "cat-file", "--batch-all-objects", "--batch"])
        errors += error
        logs = [p for p in [common / "logs", common / "COMMIT_EDITMSG", common / "packed-refs",
                            *common.glob("worktrees/*/logs"), *common.glob("worktrees/*/COMMIT_EDITMSG")] if p.exists()]
        hits, unreadable = filescan(ctx, run_dir, names, logs)
        errors += unreadable
        for name in names:
            counts[name] += objects[name] + len(hits[name])
    return {"status": "scanned" if repositories else "absent", "counts": counts, "unreadable": errors}


def journal_sink(ctx: Context, run_dir: Path, names, system: bool, since_epoch: float) -> dict:
    journalctl = ctx.which("journalctl")
    zero = {name: 0 for name in names}
    if journalctl is None:
        return {"status": "error", "counts": zero, "unreadable": 0}
    since = f"@{int(since_epoch) - WINDOW_SLACK}"
    if system:
        elevate = ctx.which("sudo")
        if elevate is None:
            return {"status": "error", "counts": zero, "unreadable": 0}
        producer = [elevate, "-n", journalctl, "-o", "export", "--no-pager", "--since", since]
    else:
        producer = [journalctl, "--user", "-o", "export", "--no-pager", "--since", since]
    counts, error = count_lines(ctx, run_dir, names, producer)
    return {"status": "error" if error else "scanned", "counts": counts, "unreadable": 0}


def loopback(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise Refused("the Loki URL must be a loopback http URL: decoys and queries never leave this host")
    return url.rstrip("/")


def loki_push(ctx: Context, sink: dict, decoy: str) -> bool:
    """Push one decoy line to Loki (labels service_name=canary-e2e-decoy); the body holds the decoy and nothing else."""
    base = loopback(sink["url"])
    body = json.dumps({"streams": [{"stream": {"service_name": "canary-e2e-decoy"},
                                    "values": [[str(time.time_ns()), f"canary decoy {decoy}"]]}]}).encode("ascii")
    request = urllib.request.Request(f"{base}/loki/api/v1/push", data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return 200 <= response.status < 300
    except (OSError, ValueError):
        return False


def loki_sink(ctx: Context, sink: dict, sets: dict, since_epoch: float) -> dict:
    """Dump by labels and time range only (the query holds no value), match here, write nothing."""
    base = loopback(sink["url"])
    matcher = Matcher(sets)
    counts = {name: 0 for name in sets}
    start, end = (int(since_epoch) - WINDOW_SLACK) * 10 ** 9, int(ctx.clock() + 60) * 10 ** 9
    try:
        for _ in range(LOKI_PAGES):
            query = urllib.parse.urlencode({"query": LOKI_QUERY, "start": str(start), "end": str(end),
                                            "limit": str(LOKI_LIMIT), "direction": "forward"})
            request = urllib.request.Request(f"{base}/loki/api/v1/query_range?{query}",
                                             headers={"X-Loki-Response-Encoding-Flags": "categorize-labels"})
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read())
            entries, last = 0, start
            for stream in body.get("data", {}).get("result", []):
                labels = json.dumps(stream.get("stream", {}), sort_keys=True).encode("utf-8")
                for value in stream.get("values", []):
                    entries += 1
                    last = max(last, int(value[0]))
                    parts = [v if isinstance(v, str) else json.dumps(v, sort_keys=True) for v in value[1:]]
                    for name in matcher.hits("\n".join(parts).encode("utf-8") + b"\n" + labels):
                        counts[name] += 1
            if entries < LOKI_LIMIT:
                break
            start = last + 1
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "error", "counts": counts, "unreadable": 0}
    return {"status": "scanned", "counts": counts, "unreadable": 0}


def github_sink(ctx: Context, run_dir: Path, names, since_epoch: float) -> dict:
    gh = ctx.which("gh")
    counts = {name: 0 for name in names}
    if gh is None:
        return {"status": "error", "counts": counts, "unreadable": 0}
    since, failed = iso(since_epoch - WINDOW_SLACK), 0
    for read in GH_READS:
        found, error = count_lines(ctx, run_dir, names, [gh, "api", read.replace("{since}", since)], cwd=str(ctx.root))
        failed += error
        for name in names:
            counts[name] += found[name]
    return {"status": "error" if failed == len(GH_READS) else "scanned", "counts": counts, "unreadable": failed}


def manager_sink(ctx: Context) -> dict:
    """Names only: whether CANARY_E2E_KEY or another inventory name is set in the user manager's environment. Each
    line is cut at its first '=' here, and no value goes further than this function."""
    systemctl = ctx.which("systemctl")
    if systemctl is None:
        return {"status": "error", "counts": {}, "unreadable": 0}
    result = subprocess.run([systemctl, "--user", "show-environment"], stdin=subprocess.DEVNULL, capture_output=True,
                            env=scanner_environment(ctx), timeout=30)
    names = {line.split(b"=", 1)[0].decode("ascii", "replace") for line in result.stdout.splitlines() if b"=" in line}
    failed = result.returncode != 0
    del result
    inventory = ctx.entry[1]
    declared = {n for e in inventory["entries"] for n in e["variables"] + e["optional_variables"]}
    declared |= set(inventory["must_not_be_set"])
    return {"status": "error" if failed else "scanned", "counts": {}, "unreadable": 0, "names_only": True,
            "canary_name_present": VARIABLE in names, "inventory_names_present": len(names & declared)}


def scan_sink(ctx: Context, run_dir: Path, sink: dict, sets: dict, *, agent_pass: bool, seen_git: set,
              since_epoch: float) -> dict:
    """One sink: {"status": scanned|absent|error|not_scanned, "counts": {set: n}, "unreadable": n, ...}."""
    names = sorted(sets)
    zero = {name: 0 for name in names}
    kind = sink["kind"]
    try:
        if kind in ("files", "sqlite", "git"):
            roots = [p for template in sink.get("paths", []) for p in expand(ctx, template) if os.path.lexists(p)]
            if not roots:
                return {"status": "absent", "counts": zero, "unreadable": 0}
            excluded = exclusions(ctx, agent_pass)
            excluded += [real(p) for template in sink.get("exclude", []) for p in expand(ctx, template)]
            globs = list(ctx.table.get("exclude_names", [])) if agent_pass else []
            parts = [part for root in roots for part in split_roots(root, excluded)]
            sudo = sink.get("access") == "sudo"
            if kind == "files":
                hits, unreadable = filescan(ctx, run_dir, names, parts, globs, sudo)
                return {"status": "scanned", "counts": {n: len(h) for n, h in hits.items()}, "unreadable": unreadable}
            if kind == "sqlite":
                return sqlite_sink(ctx, run_dir, names, sets, parts, globs, sudo)
            return git_sink(ctx, run_dir, names, parts, seen_git)
        if kind == "journal":
            return journal_sink(ctx, run_dir, names, sink.get("scope") == "system", since_epoch)
        if kind == "loki":
            return loki_sink(ctx, sink, sets, since_epoch)
        if kind == "github":
            return github_sink(ctx, run_dir, names, since_epoch)
        if kind == "manager_environment":
            return manager_sink(ctx)
    except (OSError, subprocess.SubprocessError, sqlite3.Error, ValueError):
        return {"status": "error", "counts": zero, "unreadable": 0}
    return {"status": "not_scanned", "counts": zero, "unreadable": 0}


def judge(sink: dict, result: dict, planted, class_ok: dict) -> dict:
    """The verdict of one scanned sink. A planted control decoy that is not found makes it "not a sink, or scanned
    wrongly", never clean; any canary hit is a LEAK; both fail the scan."""
    counts = result.get("counts", {})
    canary = {consumer: int(counts.get(f"c-{consumer}", 0)) for consumer in CONSUMERS}
    controls = {decoy: ("not_planted" if decoy not in planted else
                        "found" if counts.get(f"d-{decoy}", 0) > 0 else "missing")
                for decoy in sink.get("controls", [])}
    proven = sorted({c for d, s in controls.items() if s == "found" for c in CONTROL_PROVES.get(d, ())},
                    key=CONSUMERS.index)
    status = result.get("status")
    if result.get("canary_name_present") or any(canary.values()):
        verdict, fails = "LEAK", True
    elif not class_ok.get(sink.get("kind"), True):
        verdict, fails = "scanned wrongly: its scanner class control failed", True
    elif status == "error":
        verdict, fails = "not scanned: scanner error", bool(controls)
    elif "missing" in controls.values():
        verdict, fails = "not a sink, or scanned wrongly", True
    elif status == "absent":
        verdict, fails = "absent (no such path on this host)", False
    elif "found" in controls.values():
        verdict, fails = "clean (control passed)", False
    elif controls:
        verdict, fails = "uncontrolled: no control decoy was planted in this run", False
    else:
        verdict, fails = "uncontrolled: a zero here proves nothing", False
    return {"canary": canary, "controls": controls, "verdict": verdict, "fails": fails, "proven_for": proven}


def sink_line(sink: dict, judged: dict, result: dict) -> str:
    total = sum(judged["canary"].values()) + int(bool(result.get("canary_name_present")))
    line = f"{sink['id']} [{sink.get('path_class', '')}]: {judged['verdict']}; canary {total}"
    by = [f"{consumer}={count}" for consumer, count in judged["canary"].items() if count]
    if by:
        line += f" ({', '.join(by)})"
    if result.get("canary_name_present"):
        line += f" ({VARIABLE} is a name in the user manager's environment)"
    if judged["controls"]:
        line += "; controls " + " ".join(f"{decoy}={state}" for decoy, state in judged["controls"].items())
    if result.get("names_only"):
        line += f"; inventory names in the manager environment {result['inventory_names_present']} (names only)"
    if result.get("unreadable"):
        line += f"; unreadable {result['unreadable']}"
    return line


def planted_decoys(run_dir: Path) -> set:
    planted = set()
    for consumer, decoy in DECOY_OF.items():
        consumed = read_json(result_path(run_dir, f"consume-{consumer}"))
        if consumed and consumed.get("ran"):
            planted.add(decoy)
    controls = read_json(result_path(run_dir, "controls")) or {}
    if (controls.get("journal") or {}).get("found"):
        planted.add("journal")
    if (read_json(result_path(run_dir, "settle")) or {}).get("loki_pushed"):
        planted.add("loki")
    return planted


def class_status(run_dir: Path) -> dict:
    controls = read_json(result_path(run_dir, "controls"))
    if controls is None:
        raise Refused("run controls first: a sink's zero means nothing until its scanner has found a planted decoy")
    return {kind: all((controls.get(name) or {}).get("ok") for name in classes)
            for kind, classes in CLASS_OF_KIND.items()}


# -- the /proc sampler -----------------------------------------------------------------------------------------------

class ProcSampler:
    """Counts the canaries in /proc/<pid>/cmdline of this user's processes and in the transient unit files, sampled
    every 50 ms while a consumer runs. /proc/<pid>/environ is never read. Counts only: distinct (process, canary)."""

    def __init__(self, ctx: Context, sets: dict):
        self.ctx = ctx
        self.matcher = Matcher(canary_sets(sets))
        self.samples = 0
        self.hits, self.transient = set(), set()
        self.stop = threading.Event()
        self.thread = None
        runtime = ctx.env.get("XDG_RUNTIME_DIR") or f"/run/user/{ctx.uid}"
        self.transient_dir = Path(runtime) / "systemd" / "transient"

    def sample_once(self) -> None:
        try:
            entries = list(os.scandir(self.ctx.proc_root))
        except OSError:
            entries = []
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                if entry.stat(follow_symlinks=False).st_uid != self.ctx.uid:
                    continue
                with open(os.path.join(entry.path, "cmdline"), "rb") as handle:
                    data = handle.read(1 << 20)
            except OSError:
                continue
            self.hits.update((entry.name, name) for name in self.matcher.hits(data))
        try:
            units = list(os.scandir(self.transient_dir))
        except OSError:
            units = []
        for unit in units:
            try:
                with open(unit.path, "rb") as handle:
                    data = handle.read(1 << 20)
            except OSError:
                continue
            self.transient.update((unit.name, name) for name in self.matcher.hits(data))
        self.samples += 1

    def _loop(self) -> None:
        while not self.stop.wait(SAMPLE_SECONDS):
            self.sample_once()

    def __enter__(self):
        self.sample_once()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc) -> bool:
        self.stop.set()
        self.thread.join()
        self.sample_once()
        return False

    def summary(self) -> dict:
        def by_consumer(pairs) -> dict:
            counted = {}
            for _where, name in pairs:
                counted[name[2:]] = counted.get(name[2:], 0) + 1
            return counted
        return {"samples": self.samples, "cmdline_hits": by_consumer(self.hits),
                "transient_unit_hits": by_consumer(self.transient)}


# -- documented commands and prompts ---------------------------------------------------------------------------------

def probe_command(run: str, consumer: str, leak: bool = False) -> str:
    return (f"python3 -I {RUNNER_REL} {ENTRY_ID} -- python3 -I {PROBE_REL} --run {run} --consumer {consumer}"
            + (" --leak-check" if leak else ""))


def decoy_command(run: str, consumer: str) -> str:
    return f"python3 {HARNESS_REL} decoy --run {run} --consumer {consumer}"


def user_run_command(run: str) -> str:
    return f"python3 {HARNESS_REL} scan --sink {USER_RUN_GROUP} --run {run}"


def workflow_invocation(run: str) -> str:
    return f"script {WORKFLOW_REL} and args {{\"run\": \"{run}\"}}"


CLAUDE_ALLOWED = (f"Bash(python3 -I {RUNNER_REL} {ENTRY_ID} -- python3 -I {PROBE_REL}:*)",
                  f"Bash(python3 {HARNESS_REL} decoy:*)", "Bash(echo:*)", "Bash(false)", "Agent")


def claude_prompt(run: str, decoy: str) -> str:
    return ("This is an automated canary probe of the key-management proof (run " + run + "). It checks that a "
            "synthetic key reaches a command by inventory id without being printed. Do exactly these steps, in "
            "order, and nothing else.\n"
            f"1. Run this Bash command exactly. It prints a decoy value and fails on purpose: echo {decoy} && false\n"
            f"2. Run this Bash command exactly: {probe_command(run, 'fresh-claude-session')}\n"
            f"3. After step 2 has printed its canary-probe line, use the Agent tool once, with subagent_type "
            f"\"{SUBAGENT_TYPE}\", model \"{CLAUDE_MODEL}\", description \"canary probe\" and this prompt, copied "
            "exactly: \"Run these Bash commands exactly, one at a time, and then reply with only the line that "
            f"starts with canary-probe. First: {decoy_command(run, 'subagent')} (it prints a decoy line and fails on "
            "purpose). Second: echo, then the decoy value that the first command printed after the colon, then "
            f"&& false (this fails on purpose too). Third: {probe_command(run, 'subagent')}\"\n"
            "4. Reply with only the two canary-probe lines.\n")


def codex_prompt(run: str, consumer: str, decoy: str) -> str:
    return (f"This is an automated canary probe of the key-management proof (run {run}). Run these two shell "
            "commands exactly, one after the other, and then reply with only the line that starts with "
            "canary-probe.\n"
            f"1. echo {decoy} && false   (it prints a decoy value and fails on purpose)\n"
            f"2. {probe_command(run, consumer)}\n")


# -- consumers -------------------------------------------------------------------------------------------------------

def open_append(path: Path):
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600), "ab")


def stop_group(process) -> None:
    for signum, grace in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        try:
            os.killpg(process.pid, signum)
        except (ProcessLookupError, PermissionError):
            return
        try:
            process.wait(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            continue


def run_streaming(ctx: Context, argv: list, environment: dict, stdin_data, capture: Path, on_line, timeout: float):
    """Run a client, feed it stdin_data, keep its stdout lines in capture (run directory, 0600) as they come and hand
    each to on_line; stderr goes to capture's .stderr file. Returns the exit status, or None after a timeout."""
    process = subprocess.Popen(argv, stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(ctx.root), env=environment,
                               start_new_session=True)
    lines: queue.Queue = queue.Queue()

    def pump_out() -> None:
        for line in iter(process.stdout.readline, b""):
            lines.put(line)
        lines.put(None)

    def pump_err() -> None:
        with open_append(capture.with_suffix(".stderr")) as sink:
            for chunk in iter(lambda: process.stderr.read(65536), b""):
                sink.write(chunk)

    def feed() -> None:
        try:
            process.stdin.write(stdin_data)
        except OSError:
            pass
        finally:
            try:
                process.stdin.close()
            except OSError:
                pass

    workers = [threading.Thread(target=pump_out, daemon=True), threading.Thread(target=pump_err, daemon=True)]
    if stdin_data is not None:
        workers.append(threading.Thread(target=feed, daemon=True))
    for worker in workers:
        worker.start()
    deadline, timed_out = time.monotonic() + timeout, False
    with open_append(capture) as sink:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                stop_group(process)
                break
            try:
                line = lines.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue
            if line is None:
                break
            sink.write(line)
            sink.flush()
            on_line(line)
    try:
        code = process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        stop_group(process)
        code = None
    for worker in workers:
        worker.join(timeout=10)
    return None if timed_out else code


def model_id(value):
    return value if isinstance(value, str) and MODEL_ID.fullmatch(value) else None


def stream_hits(data: bytes, sets: dict) -> dict:
    return {name[2:]: 1 for name in Matcher(canary_sets(sets)).hits(data)}


def consume_record(ctx, started: float, code, summary: dict, consumer: str, **extra) -> dict:
    record = {"ran": True, "started_epoch": started, "ended_epoch": ctx.clock(), "exit_code": code,
              "cmdline_hits": summary["cmdline_hits"].get(consumer, 0),
              "transient_unit_hits": summary["transient_unit_hits"].get(consumer, 0)}
    record.update(extra)
    return record


def consume_claude(ctx: Context, run_dir: Path, run: str, sets: dict, timeout: float) -> int:
    claude = ctx.which("claude")
    if claude is None:
        raise Refused("claude is not on PATH")
    decoys = {"fresh-claude-session": set_value(sets["d-claude"]), "subagent": set_value(sets["d-subagent"])}
    argv = [claude, "-p", "--model", CLAUDE_MODEL, "--output-format", "stream-json", "--verbose", "--allowedTools",
            *CLAUDE_ALLOWED]
    capture = run_dir / "captured" / "fresh-claude-session.jsonl"
    observed, models, swapped = {}, {}, []
    for consumer in decoys:
        rotate_nonce(run_dir, consumer)

    def on_line(line: bytes) -> None:
        text = line.decode("utf-8", "replace")
        for match in probe.TAG_LINE.finditer(text):
            observed.setdefault(match["consumer"], match["prefix"])
        if not swapped and "fresh-claude-session" in observed:
            disarm(ctx)  # the subagent gets its own canary: swap before its probe can run
            arm(ctx, run_dir, "subagent")
            swapped.append(ctx.clock())
        try:
            event = json.loads(text)
        except ValueError:
            return
        if not isinstance(event, dict):
            return
        if event.get("type") == "system" and event.get("subtype") == "init":
            models.setdefault("fresh-claude-session", model_id(event.get("model")))
        message = event.get("message")
        if event.get("parent_tool_use_id") and isinstance(message, dict) and model_id(message.get("model")):
            models.setdefault("subagent", model_id(message.get("model")))

    started = ctx.clock()
    arm(ctx, run_dir, "fresh-claude-session")
    try:
        with ProcSampler(ctx, sets) as sampler:
            code = run_streaming(ctx, argv, launch_environment(ctx), claude_prompt(run, decoys["fresh-claude-session"])
                                 .encode("utf-8"), capture, on_line, timeout)
    finally:
        disarm(ctx)
    stream = capture.read_bytes()
    hits, summary = stream_hits(stream, sets), sampler.summary()
    status = 0 if code == 0 else 1
    for consumer, source in (("fresh-claude-session", "init_record"), ("subagent", "stream_message")):
        record = consume_record(ctx, started, code, summary, consumer,
                                stream_tag_prefix=observed.get(consumer), model_id=models.get(consumer),
                                model_id_source=source if models.get(consumer) else "none",
                                stream_canary_hits=hits.get(consumer, 0),
                                decoy_echoed=decoys[consumer].encode("ascii") in stream)
        record["ran"] = consumer == "fresh-claude-session" or bool(swapped)
        write_json(result_path(run_dir, f"consume-{consumer}"), record)
        seen = "tag line seen" if observed.get(consumer) else "no tag line"
        ctx.say(f"consume {consumer}: exit {code}; {seen}; model {models.get(consumer) or 'unknown'}; "
                f"canary in the stream {record['stream_canary_hits']}; canary in process arguments "
                f"{record['cmdline_hits']}")
        if not observed.get(consumer) or record["stream_canary_hits"] or record["cmdline_hits"]:
            status = 1
    return status


def codex_shell_snapshot_off(codex_home: Path, profile=None):
    """True when features.shell_snapshot is false in the effective configuration of this CODEX_HOME (and profile),
    False when it is on or unset (Codex 0.157.1 enables it by default), None when a file cannot be read. A profile
    file, $CODEX_HOME/<profile>.config.toml (profile-v2), is layered over config.toml; without one, a legacy
    [profiles.<name>] table is read."""
    try:
        import tomllib
    except ImportError:
        return None

    def feature(table):
        features = table.get("features") if isinstance(table, dict) else None
        value = features.get("shell_snapshot") if isinstance(features, dict) else None
        return value if isinstance(value, bool) else None

    try:
        base = tomllib.loads((codex_home / "config.toml").read_text(encoding="utf-8"))
    except FileNotFoundError:
        base = {}
    except (OSError, ValueError):
        return None
    effective = feature(base)
    if profile:
        try:
            layer = tomllib.loads((codex_home / f"{profile}.config.toml").read_text(encoding="utf-8"))
        except FileNotFoundError:
            profiles = base.get("profiles") if isinstance(base.get("profiles"), dict) else {}
            layer = profiles.get(profile) if isinstance(profiles.get(profile), dict) else {}
        except (OSError, ValueError):
            return None
        if feature(layer) is not None:
            effective = feature(layer)
    return effective is False


def codex_home(ctx: Context) -> Path:
    return Path(ctx.env.get("CODEX_HOME") or Path(ctx.env.get("HOME") or str(Path.home())) / ".codex")


def consume_codex(ctx: Context, run_dir: Path, run: str, sets: dict, consumer: str, timeout: float, model: str) -> int:
    codex = ctx.which("codex")
    if codex is None:
        raise Refused("codex is not on PATH")
    profile = OMNIROUTE_PROFILE if consumer == "omniroute-lane" else None
    decoy = set_value(sets[f"d-{DECOY_OF[consumer]}"])
    argv = [codex, "exec", "--json", "-s", "read-only", "-C", str(ctx.root)]
    argv += ["-p", profile] if profile else ["-m", model]
    argv.append("-")  # the prompt comes on stdin, which is then closed: no decoy in argv, no stdin hang
    capture = run_dir / "captured" / f"{consumer}.jsonl"
    observed, models = {}, []

    def on_line(line: bytes) -> None:
        text = line.decode("utf-8", "replace")
        for match in probe.TAG_LINE.finditer(text):
            observed.setdefault(match["consumer"], match["prefix"])
        try:
            event = json.loads(text)
        except ValueError:
            return
        if isinstance(event, dict) and model_id(event.get("model")):
            models.append(model_id(event.get("model")))

    rotate_nonce(run_dir, consumer)
    started = ctx.clock()
    arm(ctx, run_dir, consumer)
    try:
        with ProcSampler(ctx, sets) as sampler:
            code = run_streaming(ctx, argv, launch_environment(ctx, OMNIROUTE_PLACEHOLDER if profile else None),
                                 codex_prompt(run, consumer, decoy).encode("utf-8"), capture, on_line, timeout)
    finally:
        disarm(ctx)
    stream = capture.read_bytes()
    reported = models[0] if models else None
    source = "event_stream" if reported else ("profile" if profile else "requested")
    record = consume_record(ctx, started, code, sampler.summary(), consumer,
                            stream_tag_prefix=observed.get(consumer),
                            model_id=reported or (None if profile else model_id(model)), model_id_source=source,
                            stream_canary_hits=stream_hits(stream, sets).get(consumer, 0),
                            decoy_echoed=decoy.encode("ascii") in stream)
    write_json(result_path(run_dir, f"consume-{consumer}"), record)
    ctx.say(f"consume {consumer}: exit {code}; {'tag line seen' if observed.get(consumer) else 'no tag line'}; "
            f"model {record['model_id'] or 'from the profile'}; canary in the stream {record['stream_canary_hits']}; "
            f"canary in process arguments {record['cmdline_hits']}")
    ok = code == 0 and observed.get(consumer) and not record["stream_canary_hits"] and not record["cmdline_hits"]
    return 0 if ok else 1


def leak_counts(output: bytes, canary: str, patterns: list) -> dict:
    """Counts of what the --leak-check run returned: listed forms and printed lines left whole, and markers."""
    printed = probe.leak_forms(canary)
    return {"pattern_hits": sum(output.count(p) for p in patterns),
            "printed_form_hits": sum(output.count(form.encode("ascii")) for form in printed),
            "markers": output.count(MARKER), "partial_markers": output.count(PARTIAL),
            "forms_printed": len(printed) + 3}  # plus the raw form on stderr, the split write and the last line


def consume_unit(ctx: Context, run_dir: Path, run: str, sets: dict, state: dict, timeout: float,
                 after_restart: bool) -> int:
    systemd_run = ctx.which("systemd-run")
    if systemd_run is None:
        raise Refused("systemd-run is not on PATH")
    keep = bool(state.get("keep_across_restart"))
    name = "consume-systemd-user-unit-after-restart" if after_restart else "consume-systemd-user-unit"
    python = sys.executable
    unit = [systemd_run, "--user", "--wait", "--collect", "--pipe", "--quiet", "-p", "Type=oneshot",
            python, "-I", str(ctx.root / RUNNER_REL), ENTRY_ID, "--",
            python, "-I", str(ctx.root / PROBE_REL), "--run", run, "--consumer", UNIT]
    if after_restart:
        if not keep:
            raise UsageError("--after-restart is for a run prepared with --keep-across-restart")
        if not store_present(ctx):
            raise Refused("the kept canary file is not in the store; it did not survive the restart")
    else:
        rotate_nonce(run_dir, UNIT)
        arm(ctx, run_dir, UNIT)
    started = ctx.clock()
    environment = launch_environment(ctx)
    try:
        with ProcSampler(ctx, sets) as sampler:
            plain = subprocess.run(unit, stdin=subprocess.DEVNULL, capture_output=True, env=environment,
                                   timeout=timeout)
            leak = subprocess.run(unit + ["--leak-check"], stdin=subprocess.DEVNULL, capture_output=True,
                                  env=environment, timeout=timeout)
    finally:
        if not keep or after_restart:
            disarm(ctx)
    patterns = sets[f"c-{UNIT}"]
    prefixes = [m["prefix"] for m in probe.TAG_LINE.finditer(plain.stdout.decode("utf-8", "replace"))
                if m["consumer"] == UNIT]
    plain_hits = sum((plain.stdout + plain.stderr).count(p) for p in patterns)
    counts = leak_counts(leak.stdout + b"\n" + leak.stderr, set_value(patterns), patterns)
    counts["masked"] = (leak.returncode == 0 and counts["pattern_hits"] == 0 and counts["printed_form_hits"] == 0
                        and counts["markers"] + counts["partial_markers"] >= counts["forms_printed"])
    boot = receipts.small_text(receipts.BOOT_ID)
    record = consume_record(ctx, started, plain.returncode, sampler.summary(), UNIT,
                            stream_tag_prefix=prefixes[0] if prefixes else None, model_id=None,
                            model_id_source="none", stream_canary_hits=plain_hits, leak_exit_code=leak.returncode,
                            leak_check=counts, decoy_echoed=None,
                            boot_changed=(boot != state.get("boot_id")) if after_restart else None)
    write_json(result_path(run_dir, name), record)
    ctx.say(f"consume {UNIT}{' after the restart' if after_restart else ''}: exit {plain.returncode}; "
            f"{'tag line seen' if prefixes else 'no tag line'}; canary in the output {plain_hits}; canary in process "
            f"arguments {record['cmdline_hits']}; canary in transient unit files {record['transient_unit_hits']}")
    ctx.say(f"consume {UNIT} --leak-check: listed forms returned {counts['pattern_hits']}, printed lines returned "
            f"whole {counts['printed_form_hits']}, markers {counts['markers']} and partial markers "
            f"{counts['partial_markers']} for {counts['forms_printed']} forms printed; masked {counts['masked']}")
    if keep and not after_restart:
        ctx.say(f"consume {UNIT}: the canary file stays in the store for the restart check; after the restart run: "
                f"python3 {HARNESS_REL} consume {UNIT} --after-restart --run {run}")
    ok = (plain.returncode == 0 and prefixes and plain_hits == 0 and counts["masked"]
          and not record["cmdline_hits"] and not record["transient_unit_hits"])
    return 0 if ok else 1


def consume_workflow(ctx: Context, run_dir: Path, run: str, sets: dict, timeout: float) -> int:
    """Arm, let the coordinator run the Workflow tool, wait for the probe's tag file, disarm."""
    consumer = "workflow-child"
    rotate_nonce(run_dir, consumer)
    tag_file = run_dir / "tags" / f"{consumer}.tag"
    started = ctx.clock()
    arm(ctx, run_dir, consumer)
    ctx.say(f"consume {consumer}: armed; now run the Workflow tool with {workflow_invocation(run)}. This command "
            f"waits up to {int(timeout)} s for the probe's tag file and then removes the store file.")
    seen = False
    try:
        with ProcSampler(ctx, sets) as sampler:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if tag_file.exists():
                    seen = True
                    break
                time.sleep(0.2)
    finally:
        disarm(ctx)
    record = consume_record(ctx, started, 0 if seen else None, sampler.summary(), consumer, stream_tag_prefix=None,
                            model_id=None, model_id_source="none", stream_canary_hits=0, decoy_echoed=None)
    record["ran"] = seen
    write_json(result_path(run_dir, f"consume-{consumer}"), record)
    ctx.say(f"consume {consumer}: {'probe tag file seen' if seen else 'no probe tag file before the timeout'}; "
            f"store file removed; canary in process arguments {record['cmdline_hits']}")
    return 0 if seen and not record["cmdline_hits"] else 1


# -- subcommands -----------------------------------------------------------------------------------------------------

def cmd_prepare(ctx: Context, args) -> int:
    ctx.entry  # the inventory row, validated
    if store_present(ctx):
        raise Refused(STORE_EXISTS)
    stamp = datetime.fromtimestamp(ctx.clock(), timezone.utc).strftime("%Y%m%dt%H%M%Sz")
    run = f"canary-{stamp}-{secrets.token_hex(3)}"
    runtime_dir, keep_dir = probe.run_directories(run, ctx.env)
    run_dir = keep_dir if args.keep_across_restart else runtime_dir
    if not args.keep_across_restart:
        check_runtime_base(ctx, run_dir)
    private_tree(run_dir)
    for part in ("patterns", "nonce", "tags", "results", "captured", "scratch"):
        os.mkdir(run_dir / part, 0o700)
    for consumer in CONSUMERS:
        write_set(run_dir, f"c-{consumer}", new_canary())
        rotate_nonce(run_dir, consumer)
    for decoy in DECOYS:
        write_set(run_dir, f"d-{decoy}", new_decoy())
    boot = receipts.small_text(receipts.BOOT_ID)
    write_json(run_dir / "state.json", {"schema_version": 1, "run": run, "created_epoch": ctx.clock(),
                                        "keep_across_restart": bool(args.keep_across_restart),
                                        "boot_id": boot if receipts.UUID.fullmatch(boot) else None})
    ctx.say(run)
    return 0


def cmd_controls(ctx: Context, args) -> int:
    """Plant a decoy for each scanner class in scratch, require a count of at least 1, delete it, require 0. The
    journal line cannot be deleted, so its decoy is decoy-only and stays counted."""
    run_dir = run_directory(ctx, args.run)
    sets = load_sets(run_dir)
    ctx.hold(p for name, patterns in canary_sets(sets).items() for p in patterns)
    scratch = run_dir / "scratch" / "controls"
    shutil.rmtree(scratch, ignore_errors=True)
    os.mkdir(scratch, 0o700)
    results = {}

    def files_count(name: str, directory: Path) -> int:
        return len(filescan(ctx, run_dir, [f"d-{name}"], [directory])[0][f"d-{name}"])

    for name in ("text", "gz"):
        directory = scratch / name
        os.mkdir(directory, 0o700)
        line = f"control {set_value(sets[f'd-{name}'])}\n".encode("ascii")
        target = directory / ("decoy.txt" if name == "text" else "decoy.txt.gz")
        write_private(target, line if name == "text" else zlib_gzip(line))
        found = files_count(name, directory)
        os.unlink(target)
        after = files_count(name, directory)
        results[name] = {"found": found, "after_removal": after, "ok": found >= 1 and after == 0}
    results["sqlite"] = sqlite_control(ctx, run_dir, sets, scratch / "sqlite")
    results["git"] = git_control(ctx, run_dir, sets, scratch / "git")
    results["journal"] = journal_control(ctx, run_dir, sets)
    write_json(result_path(run_dir, "controls"), results)
    for name, result in results.items():
        after = ("a journal line cannot be removed" if result["after_removal"] is None
                 else f"{result['after_removal']} after removal")
        ctx.say(f"control {name}: {'ok' if result['ok'] else 'FAILED'} (found {result['found']}; {after})")
    return 0 if all(result["ok"] for result in results.values()) else 1


def zlib_gzip(data: bytes) -> bytes:
    compressor = zlib.compressobj(9, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
    return compressor.compress(data) + compressor.flush()


def sqlite_control(ctx: Context, run_dir: Path, sets: dict, directory: Path) -> dict:
    """A WAL database with an open connection that never checkpoints: the decoy is only in the -wal file, one cell
    holds it as text and one gzip-compressed. The SQL scan must count both cells, then 0 once the files are gone."""
    os.mkdir(directory, 0o700)
    decoy = set_value(sets["d-sqlite"])
    database = directory / "control.db"
    connection = sqlite3.connect(str(database))
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA wal_autocheckpoint = 0")
        connection.execute("CREATE TABLE control (body TEXT, packed BLOB)")
        connection.commit()
        text = f"control {decoy}"
        connection.execute("INSERT INTO control VALUES (?, ?)", (text, zlib_gzip(text.encode("ascii"))))
        connection.commit()
        in_main = decoy.encode("ascii") in database.read_bytes()
        wal = Path(f"{database}-wal")
        in_wal = wal.exists() and decoy.encode("ascii") in wal.read_bytes()
        found = sql_scan_file(ctx, database, Matcher({"d-sqlite": sets["d-sqlite"]}), run_dir)["counts"]["d-sqlite"]
    finally:
        connection.close()
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(f"{database}{suffix}")
        except FileNotFoundError:
            pass
    after = sqlite_sink(ctx, run_dir, ["d-sqlite"], sets, [directory], (), False)["counts"]["d-sqlite"]
    return {"found": found, "after_removal": after, "in_main_file": in_main, "in_wal": in_wal,
            "ok": found >= 2 and after == 0 and in_wal and not in_main}


def git_control(ctx: Context, run_dir: Path, sets: dict, directory: Path) -> dict:
    """An object written from stdin to a scratch repository, found by the object scan, then pruned."""
    git = ctx.which("git")
    if git is None:
        return {"found": 0, "after_removal": None, "ok": False}
    environment = scanner_environment(ctx)
    subprocess.run([git, "init", "-q", str(directory)], stdin=subprocess.DEVNULL, capture_output=True,
                   env=environment, check=True, timeout=60)
    subprocess.run([git, "-C", str(directory), "hash-object", "-w", "--stdin"], capture_output=True,
                   input=f"control {set_value(sets['d-git'])}\n".encode("ascii"), env=environment, check=True,
                   timeout=60)
    found = git_sink(ctx, run_dir, ["d-git"], [real(directory)], set())["counts"]["d-git"]
    subprocess.run([git, "-C", str(directory), "prune", "--expire=now"], stdin=subprocess.DEVNULL,
                   capture_output=True, env=environment, check=True, timeout=60)
    after = git_sink(ctx, run_dir, ["d-git"], [real(directory)], set())["counts"]["d-git"]
    return {"found": found, "after_removal": after, "ok": found >= 1 and after == 0}


def journal_control(ctx: Context, run_dir: Path, sets: dict) -> dict:
    """A journal line written through systemd-cat from stdin, found by the export scan within 10 s."""
    cat = ctx.which("systemd-cat")
    if cat is None:
        return {"found": 0, "after_removal": None, "ok": False}
    subprocess.run([cat, "-t", "canary-e2e-decoy"], input=f"canary decoy {set_value(sets['d-journal'])}\n"
                   .encode("ascii"), capture_output=True, env=scanner_environment(ctx), timeout=60)
    found, deadline = 0, time.monotonic() + 10
    while True:
        found = journal_sink(ctx, run_dir, ["d-journal"], False, ctx.clock())["counts"]["d-journal"]
        if found or time.monotonic() > deadline:
            break
        time.sleep(0.5)
    return {"found": found, "after_removal": None, "ok": found >= 1}


def scannable_sinks(ctx: Context, with_sudo: bool) -> list:
    return [s for s in ctx.table["sinks"] if s["kind"] in SCANNABLE
            and (s["access"] == "agent" or (with_sudo and s["access"] == "sudo"))]


def cmd_baseline(ctx: Context, args) -> int:
    """The full scan before any consumer: every canary count must be 0."""
    run_dir = run_directory(ctx, args.run)
    state, sets = load_state(run_dir), load_sets(run_dir)
    ctx.hold(p for patterns in canary_sets(sets).values() for p in patterns)
    class_ok = class_status(run_dir)
    if not all(class_ok.values()):
        raise Refused("a scanner class control failed: fix it before the baseline")
    if any(read_json(result_path(run_dir, f"consume-{c}")) for c in CONSUMERS):
        raise Refused("the baseline runs before any consumer; this run has consumed already")
    sinks, total, seen_git = scannable_sinks(ctx, False), 0, set()
    for sink in sinks:
        result = scan_sink(ctx, run_dir, sink, sets, agent_pass=True, seen_git=seen_git,
                           since_epoch=state["created_epoch"])
        hits = sum(result["counts"].get(f"c-{c}", 0) for c in CONSUMERS) + int(bool(result.get("canary_name_present")))
        total += hits
        if hits or result["status"] == "error":
            ctx.say(sink_line(sink, judge(sink, result, set(), class_ok), result))
    record = {"ok": total == 0, "canary_hits": total, "sinks": len(sinks), "ran_epoch": ctx.clock()}
    write_json(result_path(run_dir, "baseline"), record)
    ctx.say(f"baseline: {len(sinks)} sinks scanned before any consumer, canary hits {total}; "
            f"result {'ok' if total == 0 else 'FAILED'}")
    return 0 if total == 0 else 1


def cmd_consume(ctx: Context, args) -> int:
    consumer = args.consumer
    if consumer == "subagent":
        raise UsageError("the subagent runs inside the fresh-claude-session consumer: consume fresh-claude-session")
    if args.after_restart and consumer != UNIT:
        raise UsageError(f"--after-restart is for {UNIT} only")
    run_dir = run_directory(ctx, args.run)
    state, sets = load_state(run_dir), load_sets(run_dir)
    ctx.hold(p for patterns in canary_sets(sets).values() for p in patterns)
    if consumer in ("codex-exec", "omniroute-lane"):
        profile = OMNIROUTE_PROFILE if consumer == "omniroute-lane" else None
        if codex_shell_snapshot_off(codex_home(ctx), profile) is not True:
            raise Refused(f"{consumer}: features.shell_snapshot is not false in the effective Codex configuration of "
                          f"this CODEX_HOME{' and profile ' + profile if profile else ''}; set it first (Codex 0.157.1 "
                          "enables shell snapshots by default, and they record the launcher's environment)")
    if read_json(result_path(run_dir, "baseline")) is None:
        raise Refused("run controls and baseline first")
    timeout = args.timeout or (WORKFLOW_TIMEOUT if consumer == "workflow-child" else CONSUME_TIMEOUT)
    if consumer == "fresh-claude-session":
        return consume_claude(ctx, run_dir, args.run, sets, timeout)
    if consumer == "workflow-child":
        return consume_workflow(ctx, run_dir, args.run, sets, timeout)
    if consumer == UNIT:
        return consume_unit(ctx, run_dir, args.run, sets, state, timeout, args.after_restart)
    return consume_codex(ctx, run_dir, args.run, sets, consumer, timeout, args.model)


def cmd_decoy(ctx: Context, args) -> int:
    """Print the consumer's decoy and exit 1 on purpose (a failed command, for sinks that keep only those)."""
    run_dir = run_directory(ctx, args.run)
    ctx.say(f"decoy {args.consumer}: {set_value(read_set(run_dir, 'd-' + DECOY_OF[args.consumer]))}")
    return 1


def verify_one(ctx: Context, run_dir: Path, run: str, sets: dict, consumer: str) -> tuple:
    try:
        nonce = (run_dir / "nonce" / consumer).read_text(encoding="ascii").strip()
    except (OSError, ValueError):
        return "invalid", ""
    if not probe.NONCE.fullmatch(nonce):
        return "invalid", ""
    expected = probe.tag(set_value(sets[f"c-{consumer}"]), run, consumer, nonce)
    ctx.hold([expected, expected[:probe.PREFIX_HEX]])
    checks = []
    try:
        file_tag = (run_dir / "tags" / f"{consumer}.tag").read_text(encoding="ascii").strip()
    except (OSError, ValueError):
        file_tag = None
    if file_tag:
        checks.append(("tag file", hmac.compare_digest(file_tag.encode("ascii", "replace"), expected.encode())))
    prefix = (read_json(result_path(run_dir, f"consume-{consumer}")) or {}).get("stream_tag_prefix")
    if isinstance(prefix, str) and prefix:
        checks.append(("stream", hmac.compare_digest(prefix.encode("ascii", "replace"),
                                                     expected[:probe.PREFIX_HEX].encode())))
    if not checks:
        return "absent", ""
    return ("valid" if all(ok for _name, ok in checks) else "invalid"), "+".join(name for name, _ok in checks)


def cmd_verify(ctx: Context, args) -> int:
    """Recompute HMAC-SHA256(canary, run|consumer|nonce) and compare it with the tag file and the captured prefix."""
    run_dir = run_directory(ctx, args.run)
    sets = load_sets(run_dir)
    ctx.hold(p for patterns in canary_sets(sets).values() for p in patterns)
    results = read_json(result_path(run_dir, "verify")) or {}
    valid = True
    for consumer in ([args.consumer] if args.consumer else list(CONSUMERS)):
        state, channel = verify_one(ctx, run_dir, args.run, sets, consumer)
        results[consumer] = {"tag": state, "channel": channel}
        valid = valid and state == "valid"
        ctx.say(f"verify {consumer}: tag {state}" + (f" ({channel})" if channel else ""))
    write_json(result_path(run_dir, "verify"), results)
    return 0 if valid else 1


def cmd_settle(ctx: Context, args) -> int:
    """Time the decoys' arrival in each asynchronous sink, then set when scan passes 1 and 2 are due."""
    run_dir = run_directory(ctx, args.run)
    state, sets = load_state(run_dir), load_sets(run_dir)
    ctx.hold(p for patterns in canary_sets(sets).values() for p in patterns)
    ended = {}
    for consumer in CONSUMERS:
        consumed = read_json(result_path(run_dir, f"consume-{consumer}"))
        if consumed and consumed.get("ran"):
            ended[consumer] = consumed["ended_epoch"]
    if not ended:
        raise Refused("no consumer has run yet: settle times the arrival of their decoys")
    last_end = max(ended.values())
    planted_at = {DECOY_OF[c]: t for c, t in ended.items() if c in DECOY_OF}
    async_sinks = [s for s in ctx.table["sinks"] if s.get("async") and s["access"] == "agent"
                   and s["kind"] in SCANNABLE]
    record = read_json(result_path(run_dir, "settle")) or {}
    for sink in async_sinks:
        if sink["kind"] == "loki" and "loki" in sink.get("controls", []):
            if loki_push(ctx, sink, set_value(sets["d-loki"])):
                record["loki_pushed"] = True
                planted_at["loki"] = ctx.clock()
    write_json(result_path(run_dir, "settle"), record)
    arrivals, pending = {}, {}
    for sink in async_sinks:
        decoys = [d for d in sink.get("controls", []) if d in planted_at]
        if decoys:
            pending[sink["id"]] = (sink, decoys)
        else:
            arrivals[sink["id"]] = None
    started = time.monotonic()
    while pending:
        for identifier, (sink, decoys) in list(pending.items()):
            result = scan_sink(ctx, run_dir, sink, {f"d-{d}": sets[f"d-{d}"] for d in decoys}, agent_pass=True,
                               seen_git=set(), since_epoch=state["created_epoch"])
            if all(result["counts"].get(f"d-{d}", 0) > 0 for d in decoys):
                now = ctx.clock()
                arrivals[identifier] = round(max(now - planted_at[d] for d in decoys), 1)
                del pending[identifier]
        if not pending or time.monotonic() - started >= args.max_wait:
            break
        time.sleep(args.interval)
    for identifier in pending:
        arrivals[identifier] = None
    observed = [a for a in arrivals.values() if a is not None]
    longest = max(observed) if observed else float(args.max_wait)
    pass1 = longest + min(max(MARGIN_MIN, longest / 2), MARGIN_MAX)
    pass2 = max(3 * pass1, pass1 + PASS2_EXTRA)
    retention = [s["retention_seconds"] for s in ctx.table["sinks"] if s.get("controls")
                 and s["access"] in ("agent", "sudo") and isinstance(s.get("retention_seconds"), (int, float))]
    if retention:  # never later than the shortest retention of a controlled sink
        pass1, pass2 = min(pass1, min(retention) - RETENTION_SAFETY), min(pass2, min(retention) - RETENTION_SAFETY)
    record.update({"arrival_seconds": arrivals, "pass1_delay_seconds": round(pass1, 1),
                   "pass2_delay_seconds": round(pass2, 1), "max_wait_seconds": args.max_wait,
                   "last_consumer_end_epoch": last_end, "pass1_due_epoch": last_end + pass1,
                   "pass2_due_epoch": last_end + pass2})
    write_json(result_path(run_dir, "settle"), record)
    for identifier, arrival in arrivals.items():
        ctx.say(f"settle {identifier}: " + (f"decoy arrived by {arrival} s" if arrival is not None else
                                           f"decoy not seen within {int(args.max_wait)} s"))
    ctx.say(f"settle: scan pass 1 is due at {iso(last_end + pass1)} (+{pass1:.0f} s after the last consumer), "
            f"pass 2 at {iso(last_end + pass2)} (+{pass2:.0f} s)")
    return 0


def cmd_scan(ctx: Context, args) -> int:
    run_dir = run_directory(ctx, args.run)
    state = load_state(run_dir)
    if args.sink:
        wanted = [s for s in ctx.table["sinks"] if s["access"] == "user_run"] if args.sink == USER_RUN_GROUP else \
            [s for s in ctx.table["sinks"] if s["id"] == args.sink]
        if not wanted:
            raise UsageError(f"no sink {args.sink} in the table")
        user_run = any(s["access"] == "user_run" for s in wanted)
        if user_run and not ctx.tty():
            raise Refused("user-run only: these sinks hold upstream account tokens or exported values and are "
                          "Read-denied to agents. Run it in your own terminal: " + user_run_command(args.run), code=2)
        label = "user-run" if args.sink == USER_RUN_GROUP else f"sink-{args.sink}"
        agent_pass = not user_run
    else:
        settle = read_json(result_path(run_dir, "settle"))
        if not settle or "pass1_due_epoch" not in settle:
            raise Refused("run settle first: it measures when each scan pass is due")
        due, now = settle[f"pass{args.pass_}_due_epoch"], ctx.clock()
        if now < due:
            raise Refused(f"scan pass {args.pass_} is due at {iso(due)}, in {int(due - now) + 1} s; run it then", code=2)
        if read_json(result_path(run_dir, "baseline")) is None:
            raise Refused("run baseline first")
        wanted, label, agent_pass = scannable_sinks(ctx, args.with_sudo), f"pass-{args.pass_}", True
    sets = load_sets(run_dir)
    ctx.hold(p for patterns in canary_sets(sets).values() for p in patterns)
    class_ok, planted = class_status(run_dir), planted_decoys(run_dir)
    sinks = [s for s in wanted if s["kind"] in SCANNABLE]
    results, seen_git, tally = {}, set(), {"LEAK": 0, "failing": 0, "clean": 0, "uncontrolled": 0, "absent": 0}
    for sink in sinks:
        result = scan_sink(ctx, run_dir, sink, sets, agent_pass=agent_pass, seen_git=seen_git,
                           since_epoch=state["created_epoch"])
        judged = judge(sink, result, planted, class_ok)
        results[sink["id"]] = {"canary": sum(judged["canary"].values()) + int(bool(result.get("canary_name_present"))),
                               "canary_by_consumer": {c: n for c, n in judged["canary"].items() if n},
                               "controls": judged["controls"], "verdict": judged["verdict"],
                               "proven_for": judged["proven_for"], "unreadable": int(result.get("unreadable", 0)),
                               "fails": judged["fails"]}
        if result.get("names_only"):
            results[sink["id"]].update({"canary_name_present": result["canary_name_present"],
                                        "inventory_names_present": result["inventory_names_present"]})
        tally["LEAK"] += judged["verdict"] == "LEAK"
        tally["failing"] += judged["fails"]
        tally["clean"] += judged["verdict"].startswith("clean")
        tally["uncontrolled"] += judged["verdict"].startswith("uncontrolled")
        tally["absent"] += judged["verdict"].startswith("absent")
        ctx.say(sink_line(sink, judged, result))
    ok = tally["failing"] == 0
    write_json(result_path(run_dir, f"scan-{label}"), {"ran_epoch": ctx.clock(), "ok": ok, "sinks": results})
    ctx.say(f"scan {label}: {len(sinks)} sinks, {tally['LEAK']} with canary hits, {tally['failing']} failing, "
            f"{tally['clean']} clean with a passed control, {tally['uncontrolled']} uncontrolled, {tally['absent']} "
            f"absent; result {'ok' if ok else 'FAILED'}")
    if not args.sink:
        user_sinks = [s["id"] for s in ctx.table["sinks"] if s["access"] == "user_run"]
        if user_sinks and read_json(result_path(run_dir, "scan-user-run")) is None:
            ctx.say(f"user-run sinks not scanned yet ({len(user_sinks)}); in your own terminal run: "
                    f"{user_run_command(args.run)}")
    return 0 if ok else 1


PASS_SINK_KEYS = ("canary", "canary_by_consumer", "controls", "verdict", "proven_for", "unreadable")


def versions(ctx: Context) -> dict:
    found = {"python": platform.python_version()}
    for name, command in (("claude", "claude"), ("codex", "codex"), ("systemd", "systemctl"), ("rg", "rg"),
                          ("git", "git")):
        executable, line = ctx.which(command), None
        if executable:
            try:
                result = subprocess.run([executable, "--version"], stdin=subprocess.DEVNULL, capture_output=True,
                                        timeout=30, env=scanner_environment(ctx))
                lines = result.stdout.decode("utf-8", "replace").splitlines()
                line = lines[0].strip() if result.returncode == 0 and lines else None
            except (OSError, subprocess.SubprocessError):
                line = None
        found[name] = line if line and VERSION.fullmatch(line) else None
    return found


def classify(consumers: dict, leak, controls: dict, baseline, passes: dict) -> tuple:
    reasons, leaked = [], False
    for consumer, row in consumers.items():
        if row["stream_canary_hits"] or row["cmdline_hits"] or row["transient_unit_hits"]:
            leaked = True
            reasons.append(f"canary_outside_the_probe:{consumer}")
        if not row["ran"]:
            reasons.append(f"consumer_not_run:{consumer}")
        elif row["tag"] != "valid":
            reasons.append(f"tag_not_valid:{consumer}")
    if leak is None:
        reasons.append("leak_check_missing")
    elif leak["pattern_hits"] or leak["printed_form_hits"]:
        leaked = True
        reasons.append("leak_check_returned_canary_forms")
    elif not leak["masked"]:
        reasons.append("leak_check_not_masked")
    if not controls or not all(row.get("ok") for row in controls.values()):
        reasons.append("scanner_controls_failed_or_missing")
    if baseline is None:
        reasons.append("baseline_missing")
    elif baseline["canary_hits"]:
        leaked = True
        reasons.append("baseline_canary_hits")
    for number in ("1", "2"):
        scanned = passes.get(number)
        if scanned is None:
            reasons.append(f"pass{number}_missing")
            continue
        if any(row["verdict"] == "LEAK" for row in scanned["sinks"].values()):
            leaked = True
            reasons.append(f"pass{number}_leak")
        if not scanned["ok"]:
            reasons.append(f"pass{number}_failed")
    return ("leak" if leaked else "zero" if not reasons else "incomplete"), reasons


def build_receipt(ctx: Context, run_dir: Path, state: dict, models: dict) -> dict:
    """Counts, ids, versions, model ids and times only (tests/test_canary_e2e.py holds the key allowlist)."""
    def read(name):
        return read_json(result_path(run_dir, name))

    verified = read("verify") or {}
    consumers = {}
    for consumer in CONSUMERS:
        row = read(f"consume-{consumer}") or {}
        tag = verified.get(consumer) or {}
        consumers[consumer] = {
            "ran": bool(row.get("ran")), "started_at": iso_or_none(row.get("started_epoch")),
            "ended_at": iso_or_none(row.get("ended_epoch")), "exit_code": row.get("exit_code"),
            "tag": tag.get("tag", "not_verified"), "tag_channel": tag.get("channel", ""),
            "model_id": models.get(consumer) or model_id(row.get("model_id")),
            "model_id_source": "coordinator" if consumer in models else row.get("model_id_source", "none"),
            "stream_canary_hits": int(row.get("stream_canary_hits") or 0),
            "cmdline_hits": int(row.get("cmdline_hits") or 0),
            "transient_unit_hits": int(row.get("transient_unit_hits") or 0), "decoy_echoed": row.get("decoy_echoed")}
    unit = read("consume-systemd-user-unit") or {}
    leak = unit.get("leak_check")
    leak_out = None if leak is None else {k: leak[k] for k in ("pattern_hits", "printed_form_hits", "markers",
                                                               "partial_markers", "forms_printed", "masked")}
    after = read("consume-systemd-user-unit-after-restart")
    after_out = None if after is None else {
        "ran": bool(after.get("ran")), "exit_code": after.get("exit_code"), "boot_changed": after.get("boot_changed"),
        "masked": (after.get("leak_check") or {}).get("masked"),
        "pattern_hits": (after.get("leak_check") or {}).get("pattern_hits")}
    controls = {name: {k: row[k] for k in ("found", "after_removal", "ok", "in_main_file", "in_wal") if k in row}
                for name, row in (read("controls") or {}).items()}
    baseline = read("baseline")
    baseline_out = None if baseline is None else {k: baseline[k] for k in ("canary_hits", "sinks", "ok")}
    settle = read("settle")
    settle_out = None if not settle or "arrival_seconds" not in settle else {
        k: settle[k] for k in ("arrival_seconds", "pass1_delay_seconds", "pass2_delay_seconds", "max_wait_seconds")}
    passes, manager = {}, None
    for number in ("1", "2"):
        scanned = read(f"scan-pass-{number}")
        if scanned is None:
            continue
        passes[number] = {"ran_at": iso(scanned["ran_epoch"]), "ok": scanned["ok"],
                          "sinks": {i: {k: row[k] for k in PASS_SINK_KEYS} for i, row in scanned["sinks"].items()}}
        for row in scanned["sinks"].values():
            if "canary_name_present" in row:
                manager = {"canary_name_present": row["canary_name_present"],
                           "inventory_names_present": row["inventory_names_present"]}
    user = read("scan-user-run")
    user_out = {"ran": False} if user is None else {
        "ran": True, "ran_at": iso(user["ran_epoch"]), "ok": user["ok"],
        "sinks": {i: {k: row[k] for k in PASS_SINK_KEYS} for i, row in user["sinks"].items()}}
    result, reasons = classify(consumers, leak_out, controls, baseline_out, passes)
    receipt = {"schema_version": 1, "kind": "canary_e2e_receipt", "run": state["run"],
               "recorded_at": iso(ctx.clock()), "keep_across_restart": bool(state.get("keep_across_restart")),
               "checkout_revision": receipts.checkout_revision(ctx.root), "versions": versions(ctx),
               "consumers": consumers, "after_restart": after_out, "leak_check": leak_out, "controls": controls,
               "baseline": baseline_out, "settle": settle_out, "passes": passes, "user_run": user_out,
               "result": result, "reasons": reasons, "claim": ZERO_CLAIM, "not_covered": list(NOT_COVERED)}
    if manager is not None:
        receipt["manager_environment"] = manager
    return receipt


def cmd_report(ctx: Context, args) -> int:
    run_dir = run_directory(ctx, args.run)
    state, sets = load_state(run_dir), load_sets(run_dir)
    ctx.hold(p for patterns in canary_sets(sets).values() for p in patterns)
    models = {}
    for item in args.model:
        consumer, _, value = item.partition("=")
        if consumer not in CONSUMERS or model_id(value) is None:
            raise UsageError("--model takes <consumer>=<model id>, for example workflow-child=claude-sonnet-5-5")
        models[consumer] = value
    receipt = build_receipt(ctx, run_dir, state, models)
    directory = receipts.private_directory(probe.run_directories(RUN_ID_SAMPLE, ctx.env)[1].parent.parent)
    boot = receipts.small_text(receipts.BOOT_ID)
    label = receipts.receipt_label(datetime.fromtimestamp(ctx.clock(), timezone.utc),
                                   boot if receipts.UUID.fullmatch(boot) else None)
    path = receipts.write_receipt(directory, receipt, label)
    valid = sum(row["tag"] == "valid" for row in receipt["consumers"].values())
    ctx.say(f"canary receipt: result {receipt['result']}; tags valid {valid}/{len(CONSUMERS)}; passes "
            f"{len(receipt['passes'])}/2; user-run scan {'ran' if receipt['user_run']['ran'] else 'not run'}; "
            f"reasons {','.join(receipt['reasons']) or 'none'}; receipt {path.name}")
    return 0 if receipt["result"] == "zero" else 1


def cmd_cleanup(ctx: Context, args) -> int:
    """Unlink only canary-e2e.env and remove this run's directory; the receipts stay."""
    try:
        run_dir = run_directory(ctx, args.run)
    except Refused:
        run_dir = None  # already removed: the store file may still need removing
    removed = disarm(ctx)
    if run_dir is not None:
        shutil.rmtree(run_dir)
    ctx.say(f"cleanup: canary store file {'removed' if removed else 'absent'}; run directory "
            f"{'removed' if run_dir is not None else 'absent'}; receipts kept")
    return 0


# -- entry point -----------------------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="canary_e2e.py", description=__doc__.splitlines()[0], allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--keep-across-restart", action="store_true")
    for name in ("controls", "baseline", "cleanup"):
        commands.add_parser(name).add_argument("--run", required=True)
    consume = commands.add_parser("consume")
    consume.add_argument("consumer", choices=CONSUMERS)
    consume.add_argument("--run", required=True)
    consume.add_argument("--timeout", type=float)
    consume.add_argument("--model", default=CODEX_MODEL, help="codex-exec's pinned model")
    consume.add_argument("--after-restart", action="store_true")
    decoy = commands.add_parser("decoy")
    decoy.add_argument("--run", required=True)
    decoy.add_argument("--consumer", required=True, choices=tuple(DECOY_OF))
    verify = commands.add_parser("verify")
    verify.add_argument("--run", required=True)
    verify.add_argument("--consumer", choices=CONSUMERS)
    settle = commands.add_parser("settle")
    settle.add_argument("--run", required=True)
    settle.add_argument("--max-wait", type=float, default=SETTLE_MAX_WAIT)
    settle.add_argument("--interval", type=float, default=SETTLE_INTERVAL)
    scan = commands.add_parser("scan")
    scan.add_argument("--run", required=True)
    target = scan.add_mutually_exclusive_group(required=True)
    target.add_argument("--pass", dest="pass_", choices=("1", "2"))
    target.add_argument("--sink", help=f"one sink id, or {USER_RUN_GROUP} for the user-run sinks")
    scan.add_argument("--with-sudo", action="store_true")
    report = commands.add_parser("report")
    report.add_argument("--run", required=True)
    report.add_argument("--model", action="append", default=[], metavar="CONSUMER=MODEL")
    return parser


COMMANDS = {"prepare": cmd_prepare, "controls": cmd_controls, "baseline": cmd_baseline, "consume": cmd_consume,
            "decoy": cmd_decoy, "verify": cmd_verify, "settle": cmd_settle, "scan": cmd_scan, "report": cmd_report,
            "cleanup": cmd_cleanup}


def main(argv=None, ctx=None) -> int:
    ctx = Context() if ctx is None else ctx
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as stop:
        return stop.code if isinstance(stop.code, int) else 2
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ValueError, OSError):
        ctx.warn("canary_e2e: refused: could not set RLIMIT_CORE to 0")
        return 1
    try:
        return COMMANDS[args.command](ctx, args)
    except UsageError as error:
        ctx.warn(f"canary_e2e: usage error: {error}")
        return 2
    except Refused as refusal:
        ctx.warn(f"canary_e2e: refused: {refusal}")
        return refusal.code
    except KeyboardInterrupt:
        ctx.warn("canary_e2e: cancelled")
        return 130
    except Exception as error:  # no traceback: it could quote whatever was being handled
        ctx.warn(f"canary_e2e: unexpected {type(error).__name__}; no value was printed")
        return 1


if __name__ == "__main__":
    os.umask(0o077)
    raise SystemExit(main())
