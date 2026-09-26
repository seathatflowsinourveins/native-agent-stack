#!/usr/bin/env python3
"""Runner for the retrieval-quality-v2 preregistered comparison.

Executes the BM25 vs. hybrid comparison frozen in ``PREREGISTRATION.md``
against the 30 held-out queries in ``queries.json``, using the installed
upstream QMD 2.8.3 CLI via ``subprocess``. Standard library only -- no
third-party imports.

Evidence class: this script is this repository's own harness around upstream
QMD commands, so its metrics and decision are ``local_integration`` evidence.
The upstream-native corroboration is QMD's own benchmark command
(``qmd bench``, step 7), recorded separately with its returned output.

What this script does, in order:

0. Refuses to start if any output of this run already exists
   (``results-<run-id>.json``, ``native-<run-id>.json``,
   ``report-<run-id>.md``), then reserves ``results-<run-id>.json``
   exclusively. No historical result or failed attempt is ever overwritten.
   SIGINT, SIGTERM and SIGHUP stop a run cleanly (see "Interrupts" below);
   only a signal the runner cannot handle, such as SIGKILL, leaves the
   reserved receipt at status ``started``.
1. Re-hashes ``queries.json`` and compares it against the sha256 pinned in
   ``PREREGISTRATION.md``'s "Sealing" section. Stops immediately on a
   mismatch (per PREREGISTRATION.md: "A future runner must re-hash
   queries.json before use and treat a mismatch as grounds to stop").
2. Materializes the 33 pinned corpus files at the exact ``corpus_commit``
   recorded in ``queries.json``, via ``git show <commit>:<path>``, verifying
   each file's sha256 against the pin before writing it. Any mismatch aborts
   index construction entirely (fail closed; no arm runs against an
   unverified index).
3. Builds a fresh QMD index owned by this comparison, using the exact
   ``collection add`` / ``update`` commands from the preregistration. Every
   qmd call (``--version`` and ``pull`` included) passes ``--index``, runs
   with the scratch HOME as its working directory and gets a minimal
   environment that binds ``INDEX_PATH`` and ``QMD_CONFIG_DIR`` to the
   scratch tree. QMD reads ``INDEX_PATH`` before ``--index`` and
   ``QMD_CONFIG_DIR`` before ``XDG_CONFIG_HOME`` (``getDefaultDbPath`` in
   ``dist/store.js``, ``getConfigDir`` in ``dist/collections.js``), so
   inheriting either from the caller would route index and configuration
   writes to shared host state. Before any arm runs, the index's own
   ``documents`` table must hold exactly the 33 pinned content hashes.
4. Runs Arm A (``qmd search ... --format json``) for all 30 queries.
5. Pulls QMD's default embedding/generation/rerank models into the scratch
   HOME's model cache (``qmd pull``), resolves each model's HF repository
   revision and requires the Hugging Face LFS sha256 of the pulled file at
   that revision to equal the downloaded file's own sha256, then generates
   embeddings for the frozen index (``qmd embed``) -- all forced onto CPU.
   The ETag QMD itself cached for each file (``<model cache>/<URI file
   name>.etag``) is recorded as a cross-reference, not as a pin.
   An unresolved or mismatched pin, a failed or timed-out pull/embed, or an
   incomplete embedding records Arm B as ``not_run`` with the exact reason,
   and the 30-query loop for Arm B is skipped entirely (fails closed, per
   PREREGISTRATION.md). Substituting a different retrieval system is not an
   option this script implements.
6. Runs Arm B (``qmd query ... --format json``) for all 30 queries, only if
   step 5 succeeded.
7. Runs QMD's own benchmark command, ``qmd bench <fixture> --json``, against
   the same index, with a fixture derived mechanically from ``queries.json``
   (each query's grade-2 files are its expected files). The returned native
   summary is kept verbatim next to an exact-identity audit of the same
   returned rankings. Output that lacks a result for any fixture query on
   any of QMD's four backends, an empty output included, is recorded as
   ``incomplete``, never as completed. It is corroboration only and never
   enters the preregistered decision rule.
8. Computes nDCG@10, recall@5 (of grade-2 files) and MRR per query per arm,
   the paired bootstrap 95% CI of the per-query nDCG@10 difference, and the
   preregistered decision rule. A query whose output is not a JSON array of
   hits with string ``file`` and ``docid`` fields, or whose top ``-n`` hits
   include even one that cannot be verified against the pinned corpus (an
   unknown collection or path, a hit naming another index, or a docid other
   than the first six hex characters of that file's pinned sha256), is
   rejected whole: it scores 0 on every metric, keeps no ranked paths and is
   recorded as an error with its rejected hits; the arm continues with the
   next query, per the protocol's "What counts as failure". (The 2026-09-25
   runner instead kept the other hits, scored a hit outside the pinned corpus
   as grade 0 at its rank and credited a hit whose docid did not match.)
9. Writes ``results-<run-id>.json`` (the receipt), ``native-<run-id>.json``
   (every qmd call's sanitized argv, working directory, start/end time,
   exit code, stdout and stderr, each with its sha256) and
   ``report-<run-id>.md`` (rendered from the same in-memory receipt). Each
   per-query result names the native record and stdout sha256 it was scored
   from. A qmd call a stop request or an error cut short keeps its native
   record too.

Interrupts: SIGINT, SIGTERM and SIGHUP ask the run to stop. Each is handled
only when the caller left it at its default action, so ``nohup``'s ignored
SIGHUP stays ignored. The handler only records the signal (see
``StopRequests``); the runner acts on it at safe points. qmd runs in its own
session and never receives these signals, so within ``STOP_POLL_SECONDS``
the runner kills the process group of a qmd call that is still running,
keeps that call's partial output as a native record (``interrupted_by``
names the signal) and starts no further qmd call. The arm in progress
becomes ``interrupted`` (queries it already scored stay in ``per_query``; no
arm mean or decision is computed from a partial arm), the status becomes
``aborted_interrupted``, and all three outputs are written. ``interruption`` names the signal, the phase,
the qmd call that was running when the signal arrived (a call can finish
before the runner acts on the stop) and the call the stop cut short, if any.
A decision reached before the stop keeps its limitations, and a failure that
follows the stop is recorded as part of it. ``signals_received`` lists every
handled signal that arrived before the receipt was written; later ones only
reach stderr. Run as a script, the runner then ends by the signal that
stopped it, so a shell or supervisor sees the stop; ``main()`` itself
returns 128 + the signal number.

Every path written into these outputs is sanitized: the repository checkout
and scratch-home roots are replaced with symbolic placeholders, and any
remaining ``/home/<user>`` fragment is replaced with ``~``. That covers qmd's
stdout and stderr and every string the receipt takes from them: the reasons
recorded for rejected hits, which quote the hit, qmd's version banner,
``qmd pull``'s model URIs, sizes and notes, and ``qmd embed``'s duration.
``qmd bench``'s summary is kept verbatim; QMD fills it with backend names and
numbers.

Usage:
    python3 run.py --repo /path/to/native-agent-stack --scratch-home /path/to/scratch

With no ``--scratch-home``, a fresh temporary directory is created and used
(never the caller's real HOME), so this script is safe to run standalone.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import http.client
import json
import math
import os
import random
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple
from urllib import parse as urlparse
from urllib import request as urlrequest

SCRIPT_PATH = Path(__file__).resolve()
BLUEPRINT_DIR = SCRIPT_PATH.parent
DEFAULT_REPO = BLUEPRINT_DIR.parents[1]
QUERIES_REL = "blueprints/retrieval-quality-v2/queries.json"
PREREG_REL = "blueprints/retrieval-quality-v2/PREREGISTRATION.md"
HARNESS_REL = "blueprints/retrieval-quality-v2/run.py"

# QMD 2.8.3's `search`/`query` --format json emit `file` as
# `qmd://<collection>/<relative-path>?index=<indexName>` (confirmed by running
# both commands against a real built index; see the report's "Reviewed
# upstream implementation"). These three collection names and their
# repository-path prefixes are exactly the ones this script's own
# `collection add` commands create in step 3, mirroring PREREGISTRATION.md's
# "Index construction" block.
COLLECTION_PREFIX = {
    "rqv2-foundation": "blueprints/us-equities",
    "rqv2-catalog": "catalogs/us-equities",
    "rqv2-observability": "observability",
}
INDEX_NAME_DEFAULT = "retrieval-quality-v2"

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\r")
PULL_LINE_RE = re.compile(
    r"^-\s+(?P<uri>hf:\S+)\s+->\s+(?P<path>\S+)\s+\((?P<size>[^,]+),\s*(?P<note>[^)]+)\)\s*$"
)
SEAL_HASH_RE = re.compile(r"`queries\.json`\s+sha256:\s+`([0-9a-f]{64})`")
# QMD's docid is the first 6 hex characters of the content sha256, printed as
# `#abcdef` (getDocid in dist/store.js; searchResultsToJson in
# dist/cli/formatter.js).
DOCID_RE = re.compile(r"#?([0-9a-f]{6})")
RUN_ID_RE = re.compile(r"[0-9]{8}T[0-9]{6}Z")
HF_REVISION_RE = re.compile(r"[0-9a-f]{40}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")

# Caller variables handed to qmd unchanged: executable lookup, plus network
# plumbing that `qmd pull` may need on a proxied host. Everything else,
# including every QMD routing variable, comes from qmd_env() below.
QMD_ENV_PASSTHROUGH = (
    "PATH",
    "HTTPS_PROXY",
    "https_proxy",
    "HTTP_PROXY",
    "http_proxy",
    "NO_PROXY",
    "no_proxy",
    "NODE_EXTRA_CA_CERTS",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)
# Variables QMD 2.8.3 reads that change where it reads/writes, which models it
# loads or how it runs: the list `qmd doctor` reports
# (collectEnvironmentOverrides in dist/cli/qmd.js), PWD (getPwd in
# dist/store.js) and the local-config trust switches (dist/trust.js), plus
# every QMD_/node-llama-cpp/ggml-prefixed name. The receipt records which of
# them the caller had set (names only, never values); none is inherited.
QMD_ROUTING_ENV = frozenset(
    {
        "INDEX_PATH",
        "QMD_CONFIG_DIR",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "CI",
        "HF_ENDPOINT",
        "NO_COLOR",
        "PWD",
        "WSL_DISTRO_NAME",
        "WSL_INTEROP",
    }
)
QMD_ROUTING_PREFIXES = ("QMD_", "NODE_LLAMA_CPP_", "GGML_", "LLAMA_")
# Installed upstream modules whose sha256 identifies the exact QMD build.
QMD_MODULES = (
    "dist/cli/qmd.js",
    "dist/cli/formatter.js",
    "dist/store.js",
    "dist/index.js",
    "dist/llm.js",
    "dist/collections.js",
    "dist/bench/bench.js",
    "dist/bench/score.js",
)

BOOTSTRAP_ITERATIONS_DEFAULT = 10000
BOOTSTRAP_SEED_DEFAULT = 20260925  # fixed before Arm B's real results existed
GAIN_THRESHOLD = 0.05

# `qmd bench` fixture `type` labels (src/bench/types.ts). Labels only; QMD's
# README says they "label queries for grouping -- it does not change search
# behavior".
BENCH_TYPE_BY_STYLE = {
    "keyword": "exact",
    "natural_language": "semantic",
    "paraphrased_indirect": "alias",
}
BENCH_BACKENDS = ("bm25", "vector", "hybrid", "full")
BENCH_EXPECTED_IN_TOP_K = 5


class RunFailure(Exception):
    """A phase failed in a way that must be recorded, not hidden."""

    def __init__(self, slug: str, message: str):
        super().__init__(message)
        self.slug = slug


def signal_name(signum) -> str:
    try:
        return signal.Signals(signum).name
    except ValueError:
        return f"signal {signum}"


class RunInterrupted(BaseException):
    """Raised at a safe point once SIGINT, SIGTERM or SIGHUP asked the run to stop.

    A BaseException, like KeyboardInterrupt, so that no ``except Exception``
    in the runner can swallow it."""

    def __init__(self, signum: int):
        self.signum = int(signum)
        super().__init__(f"stopped by {signal_name(signum)}")


def interrupt_signal(exc: BaseException):
    """The signal number behind an interrupt exception; None for any other exception."""
    if isinstance(exc, RunInterrupted):
        return exc.signum
    if isinstance(exc, KeyboardInterrupt):
        return int(signal.SIGINT)
    return None


class StopRequests:
    """Turns SIGINT, SIGTERM and SIGHUP into a stop request for one ``main()`` call.

    The handler only records the signal; it never raises. An exception raised
    by a signal handler can land anywhere -- between ``fork`` and Popen
    recording the child's pid (leaving an untracked qmd running), half-way
    through writing a native record, or inside an ``except`` clause before the
    status is set. So the runner acts on a request at safe points instead:
    ``run_command`` polls ``requested()`` while qmd runs and kills its process
    group, ``QmdRunner.run`` records that call and then raises
    :class:`RunInterrupted`, and ``checkpoint()`` raises it before any qmd
    call starts.

    Only a disposition left at its default is replaced (Python's
    ``default_int_handler`` for SIGINT, ``SIG_DFL`` otherwise). One the caller
    chose -- ``nohup``'s ignored SIGHUP, the ignored SIGINT of a background
    job, or a handler of its own -- is left alone. The first signal is the
    stop request; later ones (GNU ``timeout`` signals the runner and then its
    whole process group) are only recorded. ``restore()`` puts every original
    disposition back.
    """

    HANDLED = ("SIGINT", "SIGTERM", "SIGHUP")

    def __init__(self):
        self._original = {}
        # (signal number, UTC time, phase, qmd call) in arrival order
        self.received = []
        self.phase = None  # the phase main() is in; its phase timer keeps this current
        # The native record id of the qmd call QmdRunner.run is running (or starting), else None.
        # A signal records it, because that call may still finish before the runner acts on the stop.
        self.current_call = None

    @classmethod
    def signals(cls) -> list:
        # SIGHUP does not exist on Windows.
        return [getattr(signal, name) for name in cls.HANDLED if hasattr(signal, name)]

    def _handle(self, signum, frame) -> None:
        self.received.append((int(signum), utc_now_iso_ms(), self.phase, self.current_call))

    def arm(self) -> None:
        for signum in self.signals():
            default = signal.default_int_handler if signum == signal.SIGINT else signal.SIG_DFL
            if signal.getsignal(signum) is not default:
                continue
            try:
                self._original[signum] = signal.signal(signum, self._handle)
            except (ValueError, OSError):  # not the main thread, or not settable here
                continue

    def restore(self) -> None:
        for signum, handler in self._original.items():
            with contextlib.suppress(ValueError, OSError, TypeError):
                signal.signal(signum, handler)
        self._original = {}

    def requested(self) -> bool:
        return bool(self.received)

    def first(self):
        """``(signal number, UTC time, phase, qmd call)`` of the stop request, or None."""
        return self.received[0] if self.received else None

    def checkpoint(self) -> None:
        if self.received:
            raise RunInterrupted(self.received[0][0])


# --------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now_iso_ms() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Sanitizer:
    """Replaces host-identifying absolute paths with symbolic placeholders.

    Applied to every free-text string (subprocess argv/stdout/stderr, resolved
    binary paths, model cache paths) before it is written into any output of
    this run. Never applied to repository-relative content paths (e.g.
    "blueprints/us-equities/data/README.md"), which are not host-specific and
    are the whole point of the receipt.
    """

    def __init__(self, repo: Path, scratch_home: Path):
        # Longest-first so a nested path (scratch_home under /tmp) is
        # replaced before any shorter prefix could partially match it.
        home = str(Path.home())
        pairs = [
            (str(scratch_home), "<SCRATCH_HOME>"),
            (str(repo), "<STACK_REPO>"),
        ]
        if home and home not in ("/", ""):
            pairs.append((home, "~"))
        pairs.sort(key=lambda p: len(p[0]), reverse=True)
        self._pairs = pairs

    def __call__(self, text: object) -> str:
        s = str(text)
        for literal, placeholder in self._pairs:
            if literal:
                s = s.replace(literal, placeholder)
        # Defense in depth: catch any remaining /home/<user>/... fragment
        # this process didn't already know about (e.g. from a nested tool).
        s = re.sub(r"/home/[^/\s\"']+", "~", s)
        return s


# --------------------------------------------------------------------------
# Step 1: seal verification
# --------------------------------------------------------------------------

def verify_seal(repo: Path) -> dict:
    queries_path = repo / QUERIES_REL
    prereg_path = repo / PREREG_REL
    if not queries_path.is_file():
        raise RunFailure("queries_missing", f"{QUERIES_REL} not found under repo")
    if not prereg_path.is_file():
        raise RunFailure("prereg_missing", f"{PREREG_REL} not found under repo")

    queries_bytes = queries_path.read_bytes()
    actual = sha256_bytes(queries_bytes)

    prereg_bytes = prereg_path.read_bytes()
    prereg_text = prereg_bytes.decode("utf-8")
    matches = sorted(set(SEAL_HASH_RE.findall(prereg_text)))
    if not matches:
        raise RunFailure(
            "seal_pin_not_found",
            "Could not find a `queries.json` sha256: `<hex>` line in PREREGISTRATION.md",
        )
    if len(matches) > 1:
        raise RunFailure(
            "seal_pin_ambiguous",
            f"PREREGISTRATION.md pins more than one distinct queries.json sha256: {matches!r}",
        )
    pinned = matches[0]
    if actual != pinned:
        raise RunFailure(
            "seal_mismatch",
            f"queries.json sha256 {actual} does not match PREREGISTRATION.md's pinned {pinned}. "
            "Stopping per PREREGISTRATION.md's own instruction; queries.json/PREREGISTRATION.md "
            "were not modified by this script.",
        )

    doc = json.loads(queries_bytes)
    if doc.get("query_count") != len(doc.get("queries", [])):
        raise RunFailure(
            "query_count_mismatch",
            f"queries.json query_count={doc.get('query_count')} != len(queries)={len(doc.get('queries', []))}",
        )
    return {
        "doc": doc,
        "queries_sha256": actual,
        "prereg_pinned_sha256": pinned,
        "preregistration_sha256": sha256_bytes(prereg_bytes),
    }


# --------------------------------------------------------------------------
# Step 2: corpus staging
# --------------------------------------------------------------------------

def stage_corpus(repo: Path, commit: str, corpus: list, stage_dir: Path) -> list:
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    staged = []
    for doc in corpus:
        rel_path = doc["path"]
        expected_sha = doc["sha256"]
        proc = subprocess.run(
            ["git", "-C", str(repo), "show", f"{commit}:{rel_path}"],
            capture_output=True,
            timeout=30,
        )
        if proc.returncode != 0:
            raise RunFailure(
                "corpus_git_show_failed",
                f"git show {commit}:{rel_path} failed (exit {proc.returncode}): "
                f"{proc.stderr.decode('utf-8', 'replace')[:500]}",
            )
        blob = proc.stdout
        actual_sha = sha256_bytes(blob)
        if actual_sha != expected_sha:
            raise RunFailure(
                "corpus_hash_mismatch",
                f"{rel_path} at {commit}: expected sha256 {expected_sha}, got {actual_sha}. "
                "Index construction stops here per PREREGISTRATION.md; no arm runs.",
            )
        dest = stage_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
        staged.append({"path": rel_path, "sha256": actual_sha, "utf8_bytes": len(blob)})
    return staged


# --------------------------------------------------------------------------
# QMD subprocess plumbing
# --------------------------------------------------------------------------

def qmd_env(scratch_home: Path, index_name: str, caller_env=None) -> tuple:
    """Returns ``(env, caller_variables_not_inherited)`` for every qmd call.

    The environment is built from scratch, not copied from the caller, and
    binds QMD's database and configuration explicitly to owned scratch
    storage instead of trusting routing variables to be absent.
    """
    caller = os.environ if caller_env is None else caller_env
    cache_home = scratch_home / ".cache"
    config_home = scratch_home / ".config"
    data_home = scratch_home / ".local" / "share"
    tmp_dir = scratch_home / "tmp"
    env = {key: caller[key] for key in QMD_ENV_PASSTHROUGH if key in caller}
    env.update(
        {
            "HOME": str(scratch_home),
            "XDG_CACHE_HOME": str(cache_home),
            "XDG_CONFIG_HOME": str(config_home),
            "XDG_DATA_HOME": str(data_home),
            "TMPDIR": str(tmp_dir),
            "INDEX_PATH": str(cache_home / "qmd" / f"{index_name}.sqlite"),
            "QMD_CONFIG_DIR": str(config_home / "qmd"),
            # Hard-rule CPU boundary: the GPU is shared and must not be
            # touched by this comparison. QMD's own switch plus the
            # node-llama-cpp convention, for redundancy.
            "QMD_FORCE_CPU": "1",
            "NODE_LLAMA_CPP_GPU": "false",
            "NO_COLOR": "1",
            # Never open a browser from a headless/agent context.
            "MCP_AUTO_OPEN_ENABLED": "false",
        }
    )
    for directory in (scratch_home, cache_home / "qmd", config_home / "qmd", data_home, tmp_dir):
        directory.mkdir(parents=True, exist_ok=True)
    not_inherited = sorted(
        key
        for key in caller
        if key != "PATH" and (key in QMD_ROUTING_ENV or key.startswith(QMD_ROUTING_PREFIXES))
    )
    return env, not_inherited


def index_db_path(env: dict) -> Path:
    return Path(env["INDEX_PATH"])


def index_config_path(env: dict, index_name: str) -> Path:
    return Path(env["QMD_CONFIG_DIR"]) / f"{index_name}.yml"


class CommandResult(NamedTuple):
    """How one qmd call ended, with the bytes it wrote."""

    stdout: bytes
    stderr: bytes
    exit_code: object  # the process's exit code; None when the runner killed it
    timed_out: bool
    process_group_killed: bool
    output_complete: bool  # False when reading a killed call's pipes had to give up
    stopped: bool = False  # killed because a stop was requested


# A killed process group closes its pipes at once; this only bounds the wait
# when a descendant that left the group still holds one open.
COLLECT_AFTER_KILL_SECONDS = 10.0
# How often run_command checks for a stop request while qmd runs.
STOP_POLL_SECONDS = 0.2


def _kill_process_group(proc: subprocess.Popen) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)


def _collect_after_kill(proc: subprocess.Popen) -> tuple:
    """Returns (stdout, stderr, complete) for a call whose process group was just killed."""
    try:
        stdout, stderr = proc.communicate(timeout=COLLECT_AFTER_KILL_SECONDS)
        return stdout or b"", stderr or b"", True
    except subprocess.TimeoutExpired as late:
        for stream in (proc.stdout, proc.stderr):
            with contextlib.suppress(OSError, ValueError):
                stream.close()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=1)
        return late.output or b"", late.stderr or b"", False


def run_command(argv: list, env: dict, cwd: Path, timeout: float, stop=None) -> CommandResult:
    """Runs ``argv`` in its own session and returns a :class:`CommandResult`.

    QMD's launcher (``bin/qmd``) spawns a child node process for
    ``dist/cli/qmd.js``. Killing only the launcher would orphan that child,
    which would keep running -- and keep writing to the scratch index -- after
    its phase was recorded as failed, so a timeout kills the whole process
    group. Because qmd runs in its own session, no signal sent to the runner
    or its terminal reaches it: while it runs, ``stop()`` (a
    ``StopRequests.requested``) is checked every STOP_POLL_SECONDS, and a stop
    request kills the group the same way. Any exception while waiting -- a
    caller's own SIGINT handler raising KeyboardInterrupt included -- also
    kills the group, attaches what the call had written as ``partial_result``
    and propagates.
    """
    proc = subprocess.Popen(
        argv,
        env=env,
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout
    try:
        while True:
            stopping = stop is not None and stop()
            remaining = deadline - time.monotonic()
            if stopping or remaining <= 0:
                _kill_process_group(proc)
                stdout, stderr, complete = _collect_after_kill(proc)
                return CommandResult(stdout, stderr, None, not stopping, True, complete, stopping)
            try:
                stdout, stderr = proc.communicate(
                    timeout=remaining if stop is None else min(remaining, STOP_POLL_SECONDS)
                )
            except subprocess.TimeoutExpired:
                continue  # communicate() keeps what it has read, and the next call resumes it
            return CommandResult(stdout or b"", stderr or b"", proc.returncode, False, False, True)
    except BaseException as exc:
        _kill_process_group(proc)
        try:
            stdout, stderr, complete = _collect_after_kill(proc)
        except BaseException:  # anything further while collecting: keep stopping
            stdout, stderr, complete = b"", b"", False
        with contextlib.suppress(AttributeError):
            exc.partial_result = CommandResult(stdout, stderr, None, False, True, complete)
        raise


def retained_stream(name: str, raw: bytes, san: Sanitizer) -> tuple:
    """Returns (decoded text for parsing, the fields retained for ``name``)."""
    text = raw.decode("utf-8", "replace")
    kept = san(text)
    kept_bytes = kept.encode("utf-8")
    return text, {
        name: kept,
        f"{name}_sha256": sha256_bytes(kept_bytes),
        f"{name}_raw_sha256": sha256_bytes(raw),
        f"{name}_raw_bytes": len(raw),
        f"{name}_identical_to_raw": kept_bytes == raw,
    }


class NativeCall:
    """One qmd invocation: its retained record plus the decoded streams."""

    def __init__(self, record: dict, stdout: str, stderr: str):
        self.record = record
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = record["exit_code"]
        self.timed_out = record["timed_out"]


class QmdRunner:
    """Runs every qmd call with the owned environment and retains its native output."""

    def __init__(self, qmd_bin: str, env: dict, cwd: Path, san: Sanitizer, stops=None):
        self.qmd_bin = qmd_bin
        self.env = env
        self.cwd = Path(cwd)
        self.san = san
        self.stops = stops if stops is not None else StopRequests()
        self.records = []

    def checkpoint(self) -> None:
        """Raises RunInterrupted once a stop was requested."""
        self.stops.checkpoint()

    def run(self, record_id: str, phase: str, args: list, timeout: float) -> NativeCall:
        """Runs one qmd call and appends its record before anything propagates.

        No call starts once a stop was requested. A call that a stop request
        cut short is recorded (``interrupted_by``, with its partial output) and
        RunInterrupted is then raised, so it is never scored; a call that
        finished first is returned as usual. A call that an exception cut short
        is recorded the same way before the exception propagates. While the
        call runs, ``stops.current_call`` names it, so a signal records which
        call was running even when that call finishes before the next poll.
        """
        self.checkpoint()
        argv = [self.qmd_bin, *(str(a) for a in args)]
        started_at = utc_now_iso_ms()
        start = time.monotonic()
        self.stops.current_call = record_id
        try:
            result = run_command(argv, self.env, self.cwd, timeout, stop=self.stops.requested)
        except BaseException as exc:
            partial = getattr(exc, "partial_result", None) or CommandResult(b"", b"", None, False, False, False)
            self._append(record_id, phase, argv, started_at, start, timeout, partial, exc)
            raise
        finally:
            self.stops.current_call = None
        record, stdout, stderr = self._append(record_id, phase, argv, started_at, start, timeout, result, None)
        if result.stopped:
            self.checkpoint()
        return NativeCall(record, stdout, stderr)

    def _append(self, record_id, phase, argv, started_at, start, timeout, result, exc) -> tuple:
        record = {
            "id": record_id,
            "phase": phase,
            "argv": [self.san(a) for a in argv],
            "cwd": self.san(str(self.cwd)),
            "started_at_utc": started_at,
            "ended_at_utc": utc_now_iso_ms(),
            "elapsed_ms": round((time.monotonic() - start) * 1000.0, 1),
            "timeout_seconds": timeout,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "interrupted_by": None,
            "process_group_killed": result.process_group_killed,
            "output_complete": result.output_complete,
        }
        if result.stopped:
            record["interrupted_by"] = signal_name(self.stops.first()[0])
        elif exc is not None:
            signum = interrupt_signal(exc)
            if signum is not None:
                record["interrupted_by"] = signal_name(signum)
            else:
                record["runner_error"] = self.san(f"{type(exc).__name__}: {exc}")
        stdout, stdout_fields = retained_stream("stdout", result.stdout, self.san)
        stderr, stderr_fields = retained_stream("stderr", result.stderr, self.san)
        record.update(stdout_fields)
        record.update(stderr_fields)
        self.records.append(record)
        return record, stdout, stderr

    def setup(self, record_id: str, phase: str, args: list, timeout: float, slug: str) -> NativeCall:
        """A setup step: a timeout or a non-zero exit is a recorded RunFailure."""
        call = self.run(record_id, phase, args, timeout)
        command = self.san(" ".join(["qmd", *(str(a) for a in args)]))
        if call.timed_out:
            raise RunFailure(
                f"{slug}_timeout",
                f"`{command}` timed out after {timeout}s; its process group was killed "
                f"(native record {record_id})",
            )
        if call.exit_code != 0:
            detail = self.san(strip_ansi(call.stderr))[-800:] or self.san(strip_ansi(call.stdout))[-800:]
            raise RunFailure(f"{slug}_failed", f"`{command}` failed (exit {call.exit_code}): {detail}")
        return call


def describe_qmd_install(qmd_bin: str, san: Sanitizer) -> dict:
    """Identifies the installed @tobilu/qmd package behind ``qmd_bin``."""
    resolved = Path(qmd_bin).resolve()
    package_dir = resolved.parent.parent
    info = {"bin": san(qmd_bin), "resolved_bin": san(str(resolved)), "package": None}
    try:
        manifest = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return info
    if not isinstance(manifest, dict) or manifest.get("name") != "@tobilu/qmd":
        return info
    build = {}
    with contextlib.suppress(OSError, ValueError):
        build = json.loads((package_dir / "dist" / "cli" / "build-info.json").read_text(encoding="utf-8"))
    info["package"] = {
        "name": manifest.get("name"),
        "version": manifest.get("version"),
        "build_commit": build.get("commit") if isinstance(build, dict) else None,
        "built_at": build.get("builtAt") if isinstance(build, dict) else None,
        "module_sha256": {
            rel: sha256_file(package_dir / rel) for rel in QMD_MODULES if (package_dir / rel).is_file()
        },
    }
    return info


def read_index_rows(db_path: Path, sql: str) -> list:
    """Reads QMD's SQLite index read-only (no qmd process is running here)."""
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    with contextlib.closing(sqlite3.connect(uri, uri=True)) as conn:
        return conn.execute(sql).fetchall()


def count_llm_cache(db_path: Path):
    try:
        return int(read_index_rows(db_path, "SELECT COUNT(*) FROM llm_cache")[0][0])
    except (sqlite3.Error, OSError, IndexError):
        return None


# --------------------------------------------------------------------------
# Step 3: fresh index build
# --------------------------------------------------------------------------

def verify_index_content(db_path: Path, corpus: list) -> dict:
    """The index's own active documents must be exactly the pinned corpus."""
    if not db_path.is_file():
        raise RunFailure("index_db_missing", "no index database exists at the bound scratch INDEX_PATH")
    try:
        rows = read_index_rows(db_path, "SELECT collection, path, hash FROM documents WHERE active = 1")
    except sqlite3.Error as exc:
        raise RunFailure("index_db_unreadable", f"could not read the scratch index read-only: {exc}") from exc
    indexed = {}
    unexpected_collections = set()
    for collection, path, digest in rows:
        prefix = COLLECTION_PREFIX.get(collection)
        if prefix is None:
            unexpected_collections.add(collection)
            continue
        indexed[f"{prefix}/{path}"] = digest
    pinned = {d["path"]: d["sha256"] for d in corpus}
    missing = sorted(set(pinned) - set(indexed))
    extra = sorted(set(indexed) - set(pinned))
    changed = sorted(p for p in set(pinned) & set(indexed) if pinned[p] != indexed[p])
    if unexpected_collections or missing or extra or changed:
        raise RunFailure(
            "index_content_mismatch",
            f"the scratch index does not hold exactly the pinned corpus: unexpected collections "
            f"{sorted(unexpected_collections)}, missing {missing[:5]}, extra {extra[:5]}, "
            f"content hash differs {changed[:5]}. No arm runs against it.",
        )
    return {
        "documents_verified": len(indexed),
        "method": (
            "Read-only SELECT collection, path, hash FROM documents WHERE active = 1 on the "
            "scratch index after `update`; every row's content sha256 equals the queries.json "
            "pin and no pinned file is missing or extra."
        ),
    }


def build_index(
    runner: QmdRunner, env: dict, stage_dir: Path, index_name: str, timeout: float, corpus: list, san: Sanitizer
) -> dict:
    # Guarantee freshness even if scratch-home's model cache is being reused
    # across invocations: drop any pre-existing DB/config for this exact
    # index before (re)building it.
    db_path = index_db_path(env)
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()
    cfg = index_config_path(env, index_name)
    if cfg.exists():
        cfg.unlink()

    collections = [
        ("rqv2-foundation", stage_dir / "blueprints" / "us-equities"),
        ("rqv2-catalog", stage_dir / "catalogs" / "us-equities"),
        ("rqv2-observability", stage_dir / "observability"),
    ]
    add_results = []
    for name, path in collections:
        if not path.is_dir():
            raise RunFailure("index_missing_stage_dir", f"staged corpus missing expected directory {san(path)}")
        call = runner.setup(
            f"index:collection-add:{name}",
            "index_build",
            ["--index", index_name, "collection", "add", str(path), "--name", name, "--mask", "**/*.md"],
            timeout,
            "index_collection_add",
        )
        add_results.append({"collection": name, "native_record_id": call.record["id"]})
    if not db_path.is_file() or not cfg.is_file():
        raise RunFailure(
            "index_not_in_scratch",
            "qmd did not create the index database and configuration at the bound scratch "
            f"paths ({san(db_path)}, {san(cfg)})",
        )

    runner.setup("index:update", "index_build", ["--index", index_name, "update"], timeout, "index_update")

    call = runner.setup("index:status", "index_build", ["--index", index_name, "status"], timeout, "index_status")
    status_text = strip_ansi(call.stdout)
    counts = dict(re.findall(r"^\s*(rqv2-\w+)\s+\(qmd://[^)]*\)\s*\n\s*Pattern:.*\n\s*Files:\s+(\d+)", status_text, re.MULTILINE))
    total_match = re.search(r"Total:\s+(\d+)\s+files indexed", status_text)
    total_indexed = int(total_match.group(1)) if total_match else None
    expected_total = sum(len(list(path.rglob("*.md"))) for _, path in collections)
    if total_indexed != expected_total:
        raise RunFailure(
            "index_count_mismatch",
            f"qmd status reports {total_indexed} indexed files, expected {expected_total} "
            f"(status output: {san(status_text)[:1000]})",
        )
    content = verify_index_content(db_path, corpus)

    return {
        "index_name": index_name,
        "db_path_sanitized": san(str(db_path)),
        "config_path_sanitized": san(str(cfg)),
        "collections_added": add_results,
        "total_documents_indexed": total_indexed,
        "collection_file_counts": {k: int(v) for k, v in counts.items()},
        "status_native_record_id": call.record["id"],
        "content_verification": content,
    }


# --------------------------------------------------------------------------
# Path resolution and response validation for search/query hits
# --------------------------------------------------------------------------

def resolve_repository_path(file_field, docid_field, corpus_sha: dict, index_name: str) -> tuple:
    """Maps a returned `qmd://<collection>/<relpath>?index=...` hit back to
    this repository's path and verifies it against the pinned corpus. A hit
    is credited only when it names no other index (a hit without an
    ``?index=`` parameter is accepted), its path is one of the pinned files
    AND its docid is exactly the first 6 hex chars of that file's pinned
    sha256 (QMD's own docid derivation). Returns (repository_path, "ok") or
    (None, reason); a hit that fails any check is never scored, and run_arm
    then rejects the query's whole response."""
    if not isinstance(file_field, str) or not file_field.startswith("qmd://"):
        return None, f"unexpected file field (no qmd:// prefix): {file_field!r}"
    location, _, query = file_field[len("qmd://"):].partition("?")
    named_index = urlparse.parse_qs(query).get("index") if query else None
    if named_index is not None and named_index != [index_name]:
        return None, f"hit names another index {named_index!r}: {file_field!r}"
    if "/" not in location:
        return None, f"unexpected file field (no collection/path split): {file_field!r}"
    collection, relpath = location.split("/", 1)
    prefix = COLLECTION_PREFIX.get(collection)
    if prefix is None:
        return None, f"unknown collection {collection!r} in file field: {file_field!r}"
    repository_path = f"{prefix}/{relpath}"
    expected_sha = corpus_sha.get(repository_path)
    if expected_sha is None:
        return None, f"resolved path {repository_path!r} is not one of the pinned corpus files"
    match = DOCID_RE.fullmatch(docid_field) if isinstance(docid_field, str) else None
    if match is None:
        return None, f"docid {docid_field!r} for {repository_path!r} is not a six-hex-character QMD docid"
    if match.group(1) != expected_sha[:6]:
        return None, (
            f"docid #{match.group(1)} does not match {repository_path!r}'s pinned sha256 prefix "
            f"{expected_sha[:6]!r}"
        )
    return repository_path, "ok"


def parse_hits(stdout: str) -> tuple:
    """Validates `search`/`query --format json` output. Returns (hits, None) or (None, error)."""
    try:
        doc = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON output: {exc}"
    if not isinstance(doc, list):
        return None, f"malformed JSON response: expected an array of hits, got {type(doc).__name__}"
    for rank, hit in enumerate(doc, start=1):
        if not isinstance(hit, dict):
            return None, f"malformed hit at rank {rank}: expected an object, got {type(hit).__name__}"
        if not isinstance(hit.get("file"), str) or not isinstance(hit.get("docid"), str):
            return None, f"malformed hit at rank {rank}: 'file' and 'docid' must both be strings"
    return doc, None


# --------------------------------------------------------------------------
# Metrics (exact formulas from PREREGISTRATION.md's "Metrics" section)
# --------------------------------------------------------------------------

def dcg(grades_in_rank_order: list) -> float:
    return sum((2 ** g - 1) / math.log2(idx + 2) for idx, g in enumerate(grades_in_rank_order))


def compute_query_metrics(ranked_paths: list, relevance: list) -> dict:
    rel_map = {r["path"]: r["grade"] for r in relevance}
    ranked_grades = [rel_map.get(p, 0) if p is not None else 0 for p in ranked_paths][:10]

    ideal_grades = sorted((r["grade"] for r in relevance), reverse=True)[:10]
    idcg = dcg(ideal_grades)
    if idcg <= 0:
        # PREREGISTRATION.md: "Every query has at least one grade-2 file, so
        # IDCG@10 > 0 always". Fail loudly rather than silently divide.
        raise RunFailure("zero_idcg", "a query's ideal DCG@10 was <= 0; preregistration invariant violated")
    ndcg10 = dcg(ranked_grades) / idcg

    grade2_paths = {r["path"] for r in relevance if r["grade"] == 2}
    top5 = set(p for p in ranked_paths[:5] if p is not None)
    recall5 = (len(grade2_paths & top5) / len(grade2_paths)) if grade2_paths else 0.0

    mrr = 0.0
    for rank, p in enumerate(ranked_paths[:10], start=1):
        if p is not None and rel_map.get(p, 0) >= 1:
            mrr = 1.0 / rank
            break

    return {"ndcg_at_10": ndcg10, "recall_at_5": recall5, "mrr": mrr}


ZERO_METRICS = {"ndcg_at_10": 0.0, "recall_at_5": 0.0, "mrr": 0.0}


# --------------------------------------------------------------------------
# Arm execution (search/query share an identical JSON schema)
# --------------------------------------------------------------------------

def run_arm(
    runner: QmdRunner,
    index_name: str,
    subcommand: str,
    arm_label: str,
    queries: list,
    corpus: list,
    per_query_timeout: float,
    top_k: int,
    results=None,
) -> list:
    """Runs one arm; each scored query is appended to ``results`` (default: a
    new list) as soon as it is scored, so an interrupted arm keeps the queries
    it finished."""
    corpus_sha = {d["path"]: d["sha256"] for d in corpus}
    results = [] if results is None else results
    for q in queries:
        call = runner.run(
            f"{arm_label}:{q['id']}",
            arm_label,
            ["--index", index_name, subcommand, q["query"], "-n", str(top_k), "--format", "json"],
            per_query_timeout,
        )
        error = None
        ranked_paths = []
        raw_hit_count = None
        rejected_hits = []
        if call.timed_out:
            error = f"timed out after {per_query_timeout}s"
        elif call.exit_code != 0:
            error = f"exit {call.exit_code}: {runner.san(strip_ansi(call.stderr))[-500:]}"
        else:
            hits, error = parse_hits(call.stdout)
            if error is None:
                raw_hit_count = len(hits)
                for rank, hit in enumerate(hits[:top_k], start=1):
                    path, note = resolve_repository_path(hit["file"], hit["docid"], corpus_sha, index_name)
                    if path is None:
                        # The reason quotes the hit's own fields, so it is sanitized like them.
                        rejected_hits.append(
                            {
                                "rank": rank,
                                "file": runner.san(hit["file"]),
                                "docid": runner.san(hit["docid"]),
                                "reason": runner.san(note),
                            }
                        )
                    ranked_paths.append(path)
                if rejected_hits:
                    error = (
                        "response rejected: hit(s) at rank "
                        f"{', '.join(str(r['rank']) for r in rejected_hits)} cannot be verified against "
                        "the pinned corpus"
                    )
                    ranked_paths = []

        metrics = dict(ZERO_METRICS) if error is not None else compute_query_metrics(ranked_paths, q["relevance"])
        results.append(
            {
                "id": q["id"],
                "style": q["style"],
                "query": q["query"],
                "latency_ms": call.record["elapsed_ms"],
                "raw_hit_count": raw_hit_count,
                "ranked_paths": ranked_paths,
                "error": error,
                "rejected_hits": rejected_hits,
                "native_record_id": call.record["id"],
                "exit_code": call.exit_code,
                "stdout_sha256": call.record["stdout_sha256"],
                **metrics,
            }
        )
    return results


def summarize_arm(per_query: list) -> dict:
    n = len(per_query)
    return {
        "query_count": n,
        "mean_ndcg_at_10": sum(r["ndcg_at_10"] for r in per_query) / n,
        "mean_recall_at_5": sum(r["recall_at_5"] for r in per_query) / n,
        "mean_mrr": sum(r["mrr"] for r in per_query) / n,
        "errored_queries": [r["id"] for r in per_query if r["error"] is not None],
        "empty_result_queries": [r["id"] for r in per_query if r["error"] is None and r["raw_hit_count"] == 0],
    }


# --------------------------------------------------------------------------
# Arm B setup: model pull + provenance + embed
# --------------------------------------------------------------------------

def hf_api_get(path: str, timeout: float = 15.0, attempts: int = 3) -> tuple:
    """GET https://huggingface.co/api/<path>; returns (decoded JSON, None) or (None, error)."""
    url = f"https://huggingface.co/api/{path}"
    last_error = None
    for attempt in range(attempts):
        req = urlrequest.Request(url, headers={"Accept": "application/json"})
        try:
            with urlrequest.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8")), None
        except (OSError, ValueError, http.client.HTTPException) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt + 1 < attempts:
            time.sleep(2.0 * (attempt + 1))
    return None, last_error


def resolve_hf_pin(repo_id: str, filename: str, file_sha256: str, file_size: int) -> dict:
    """Pins a pulled model file to an exact HF revision, failing closed.

    The revision is the repository HEAD commit reported by the HF API. The pin
    holds only if that revision's tree lists ``filename`` with an LFS sha256
    (and size) equal to the downloaded file's own; anything else raises.
    """
    info, err = hf_api_get(f"models/{repo_id}")
    revision = info.get("sha") if isinstance(info, dict) else None
    if not isinstance(revision, str) or not HF_REVISION_RE.fullmatch(revision):
        raise RunFailure(
            "arm_b_model_revision_unresolved",
            f"could not resolve the HF revision of {repo_id}: {err or 'the API response had no commit sha'}",
        )
    directory = filename.rsplit("/", 1)[0] if "/" in filename else ""
    tree_path = f"models/{repo_id}/tree/{revision}" + (f"/{urlparse.quote(directory)}" if directory else "")
    tree, err = hf_api_get(tree_path)
    entry = None
    if isinstance(tree, list):
        entry = next((e for e in tree if isinstance(e, dict) and e.get("path") == filename), None)
    lfs = entry.get("lfs") if isinstance(entry, dict) else None
    lfs_sha256 = lfs.get("oid") if isinstance(lfs, dict) else None
    lfs_size = lfs.get("size") if isinstance(lfs, dict) else None
    if not isinstance(lfs_sha256, str) or not SHA256_RE.fullmatch(lfs_sha256):
        raise RunFailure(
            "arm_b_model_revision_unverified",
            f"{repo_id}@{revision} does not list an LFS sha256 for {filename}: {err or 'file not in that tree'}",
        )
    if lfs_sha256 != file_sha256 or lfs_size != file_size:
        raise RunFailure(
            "arm_b_model_revision_mismatch",
            f"{filename}: downloaded sha256 {file_sha256} ({file_size} bytes) is not the file "
            f"{repo_id}@{revision} pins (LFS sha256 {lfs_sha256}, {lfs_size} bytes)",
        )
    return {"revision": revision, "lfs_sha256": lfs_sha256, "lfs_size": lfs_size}


def qmd_model_cache_dir(env: dict) -> Path:
    """QMD's DEFAULT_MODEL_CACHE_DIR (dist/llm.js) under the environment qmd_env() builds."""
    return Path(env["XDG_CACHE_HOME"]) / "qmd" / "models"


def qmd_etag_path(model_cache_dir: Path, hf_uri: str) -> Path:
    """Where QMD 2.8.3 caches the ETag of a pulled model.

    ``pullModels`` in dist/llm.js writes ``join(cacheDir, `${filename}.etag`)``
    with ``filename = model.split("/").pop()``: the URI's last path segment,
    not the name node-llama-cpp gives the downloaded file (``hf_<org>_<file>``).
    """
    return Path(model_cache_dir) / f"{hf_uri.rsplit('/', 1)[-1]}.etag"


def pull_and_pin_models(runner: QmdRunner, index_name: str, scratch_home: Path, pull_timeout: float, san: Sanitizer) -> dict:
    call = runner.setup("arm_b:pull", "arm_b_setup", ["--index", index_name, "pull"], pull_timeout, "arm_b_pull")
    stdout = strip_ansi(call.stdout)

    roles = ["embed", "generate", "rerank"]  # fixed order qmd's own `pull` case uses (dist/cli/qmd.js)
    parsed = []
    for line in stdout.splitlines():
        m = PULL_LINE_RE.match(line.strip())
        if m:
            parsed.append(m.groupdict())

    if len(parsed) != 3:
        raise RunFailure(
            "arm_b_pull_unparseable",
            f"expected 3 model lines from `qmd pull`, parsed {len(parsed)}. "
            f"stdout tail: {san(stdout)[-800:]}",
        )

    owned_root = scratch_home.resolve()
    model_cache_dir = qmd_model_cache_dir(runner.env)
    models = []
    for role, entry in zip(roles, parsed, strict=True):
        runner.checkpoint()  # hashing a model and two HF lookups take seconds; stop between models
        uri = entry["uri"]
        local_path = Path(entry["path"])
        parts = uri[len("hf:"):].split("/")
        if len(parts) < 3:
            raise RunFailure("arm_b_model_uri_unexpected", f"could not split org/repo/filename from {uri!r}")
        org, repo_name = parts[0], parts[1]
        filename = "/".join(parts[2:])
        hf_repo_id = f"{org}/{repo_name}"
        if not local_path.is_file():
            raise RunFailure(
                "arm_b_model_file_missing",
                f"qmd pull reported {uri} at {san(str(local_path))} but that file does not exist",
            )
        if not local_path.resolve().is_relative_to(owned_root):
            raise RunFailure(
                "arm_b_model_outside_scratch",
                f"qmd pull placed {uri} at {san(str(local_path))}, outside the scratch HOME's model cache",
            )
        file_sha256 = sha256_file(local_path)
        size_bytes = local_path.stat().st_size
        pin = resolve_hf_pin(hf_repo_id, filename, file_sha256, size_bytes)
        etag_path = qmd_etag_path(model_cache_dir, uri)
        hf_content_etag = etag_path.read_text(encoding="utf-8").strip() if etag_path.is_file() else None
        models.append(
            {
                "role": role,
                # The URI and its parts come from qmd's output: sanitized where kept, raw for the lookup.
                "hf_uri": san(uri),
                "hf_repo_id": san(hf_repo_id),
                "filename": san(filename),
                "size_bytes": size_bytes,
                "sha256": file_sha256,
                "hf_repo_revision": pin["revision"],
                "hf_revision_lfs_sha256": pin["lfs_sha256"],
                "hf_revision_lfs_size": pin["lfs_size"],
                "hf_repo_revision_note": (
                    "The repository HEAD commit reported by huggingface.co/api/models/<repo> after the "
                    "pull. The pin is accepted only because that revision's tree lists this filename "
                    "with an LFS sha256 and size equal to the downloaded file's own, so the recorded "
                    "revision contains exactly these bytes."
                ),
                "hf_content_store_etag": hf_content_etag,
                "hf_content_store_etag_path": san(str(etag_path)),
                "hf_content_store_etag_note": (
                    "The ETag Hugging Face served for this file's resolve/main URL, as QMD cached it "
                    "to decide whether `qmd pull` must download again (pullModels in dist/llm.js "
                    "writes <model cache>/<URI file name>.etag). For a Xet-backed file it is the "
                    "file's Xet hash, not its sha256, so it is only a cross-reference to QMD's own "
                    "cache bookkeeping; the sha256 and LFS fields above are the pin. null when QMD "
                    "cached no ETag."
                ),
                # Free text from qmd's own output, sanitized like the rest of it.
                "pull_note": san(entry["note"]),
                "pull_size_reported": san(entry["size"]),
            }
        )
    return {"models": models, "pull_native_record_id": call.record["id"]}


def embed_index(runner: QmdRunner, index_name: str, embed_timeout: float, expected_documents: int, san: Sanitizer) -> dict:
    call = runner.setup("arm_b:embed", "arm_b_setup", ["--index", index_name, "embed"], embed_timeout, "arm_b_embed")
    stdout = strip_ansi(call.stdout)
    m = re.search(r"Embedded (\d+) chunks from (\d+) documents in (\S+)", stdout)
    if m is None or int(m.group(2)) != expected_documents:
        raise RunFailure(
            "arm_b_embed_incomplete",
            f"qmd embed did not report embedding all {expected_documents} documents: {san(stdout)[-500:]}",
        )
    return {
        "chunks_embedded": int(m.group(1)),
        "documents_embedded": int(m.group(2)),
        "upstream_reported_duration": san(m.group(3)),
        "native_record_id": call.record["id"],
    }


# --------------------------------------------------------------------------
# Step 7: QMD's own benchmark command on the same index
# --------------------------------------------------------------------------

def virtual_path(repository_path: str) -> str:
    for collection, prefix in COLLECTION_PREFIX.items():
        if repository_path.startswith(prefix + "/"):
            return f"qmd://{collection}/{repository_path[len(prefix) + 1:]}"
    raise ValueError(f"{repository_path!r} is under none of this index's collections")


def repository_path_from_virtual(value):
    """`qmd://<collection>/<relpath>[?...]` -> repository path, or None."""
    if not isinstance(value, str) or not value.startswith("qmd://"):
        return None
    location = value[len("qmd://"):].split("?", 1)[0]
    if "/" not in location:
        return None
    collection, relpath = location.split("/", 1)
    prefix = COLLECTION_PREFIX.get(collection)
    return f"{prefix}/{relpath}" if prefix else None


def build_bench_fixture(queries: list) -> dict:
    """A `qmd bench` fixture (src/bench/types.ts) derived mechanically from queries.json."""
    return {
        "description": (
            "retrieval-quality-v2: the sealed queries.json queries, derived mechanically by run.py. "
            "expected_files are each query's grade-2 paths as qmd:// virtual paths; "
            f"expected_in_top_k={BENCH_EXPECTED_IN_TOP_K} matches the preregistered recall@5."
        ),
        "version": 1,
        "queries": [
            {
                "id": q["id"],
                "query": q["query"],
                "type": BENCH_TYPE_BY_STYLE[q["style"]],
                "description": f"queries.json {q['id']} ({q['style']})",
                "expected_files": [virtual_path(r["path"]) for r in q["relevance"] if r["grade"] == 2],
                "expected_in_top_k": BENCH_EXPECTED_IN_TOP_K,
            }
            for q in queries
        ],
    }


def audit_native_bench(doc: dict, fixture: dict, arm_results: dict) -> dict:
    """Re-scores the bench's own returned rankings with exact path identity.

    QMD's scorer (src/bench/score.ts) lowercases paths, drops the collection
    and accepts a suffix match in either direction, so a collection-root
    README.md matches every nested README.md. This audit recomputes recall@5
    and MRR from the same returned ``top_files`` with exact repository-path
    identity, lists every query where the two disagree, and compares each
    backend's rankings with the CLI arm that runs the same pipeline.
    """
    expected = {
        q["id"]: [repository_path_from_virtual(p) for p in q["expected_files"]] for q in fixture["queries"]
    }
    arm_by_backend = {"bm25": "arm_a", "full": "arm_b"}
    audit = {}
    for backend in BENCH_BACKENDS:
        rows = []
        for result in doc.get("results", []):
            if not isinstance(result, dict):
                continue
            backends = result.get("backends")
            backend_result = backends.get(backend) if isinstance(backends, dict) else None
            if not isinstance(backend_result, dict):
                continue
            top = [repository_path_from_virtual(f) for f in backend_result.get("top_files") or []]
            gold = expected.get(result.get("id"), [])
            exact_recall5 = (sum(1 for g in gold if g in top[:5]) / len(gold)) if gold else 0.0
            first = next((i for i, p in enumerate(top) if p is not None and p in gold), None)
            exact_mrr = 0.0 if first is None else 1.0 / (first + 1)
            rows.append(
                {
                    "id": result.get("id"),
                    "top": top,
                    "exact_recall_at_5": exact_recall5,
                    "exact_mrr": exact_mrr,
                    "native_recall_at_5": backend_result.get("recall_at_5"),
                    "native_mrr": backend_result.get("mrr"),
                }
            )
        if not rows:
            continue
        n = len(rows)
        entry = {
            "queries": n,
            "exact_mean_recall_at_5": sum(r["exact_recall_at_5"] for r in rows) / n,
            "exact_mean_mrr": sum(r["exact_mrr"] for r in rows) / n,
            "native_vs_exact_recall_at_5_disagreements": [
                r["id"] for r in rows if r["native_recall_at_5"] != r["exact_recall_at_5"]
            ],
            "native_vs_exact_mrr_disagreements": [r["id"] for r in rows if r["native_mrr"] != r["exact_mrr"]],
            "unmapped_top_files": sum(1 for r in rows for p in r["top"] if p is None),
        }
        arm = arm_by_backend.get(backend)
        arm_rows = {r["id"]: r for r in (arm_results.get(arm) or [])} if arm else {}
        if arm_rows:
            compared = [r for r in rows if r["id"] in arm_rows and arm_rows[r["id"]]["error"] is None]
            entry["cli_arm"] = arm
            entry["cli_rankings_compared"] = len(compared)
            entry["cli_rankings_identical"] = sum(
                1 for r in compared if r["top"][:10] == arm_rows[r["id"]]["ranked_paths"][:10]
            )
            entry["cli_rankings_differing"] = [
                r["id"] for r in compared if r["top"][:10] != arm_rows[r["id"]]["ranked_paths"][:10]
            ]
        audit[backend] = entry
    return audit


def _some(ids: list) -> str:
    """At most five ids, then how many more."""
    shown = ", ".join(str(i) for i in ids[:5])
    return shown + (f" and {len(ids) - 5} more" if len(ids) > 5 else "")


def bench_output_problems(doc: dict, fixture: dict) -> list:
    """What keeps a parsed ``qmd bench --json`` output from covering the fixture.

    ``runBenchmark`` (src/bench/bench.ts) runs every fixture query on each of
    its four backends, so a complete output holds exactly one result per
    fixture query id, each with a result holding a ``top_files`` list for
    every backend, and a summary entry for every backend. Anything less, an
    empty output included, is not a completed benchmark. Returns the
    problems found, or an empty list.
    """
    problems = []
    expected = [q["id"] for q in fixture["queries"]]
    results = [r for r in doc["results"] if isinstance(r, dict)]
    if len(results) != len(doc["results"]):
        problems.append(f"{len(doc['results']) - len(results)} results are not objects")
    returned = [r.get("id") for r in results]
    missing = [qid for qid in expected if qid not in returned]
    if missing:
        problems.append(f"no result for fixture queries {_some(missing)}")
    unexpected = [qid for qid in returned if qid not in expected]
    if unexpected:
        problems.append(f"results for queries not in the fixture: {_some([repr(q) for q in unexpected])}")
    repeated = [qid for qid in expected if returned.count(qid) > 1]
    if repeated:
        problems.append(f"more than one result for {_some(repeated)}")
    for backend in BENCH_BACKENDS:
        lacking = []
        for result in results:
            backends = result.get("backends")
            entry = backends.get(backend) if isinstance(backends, dict) else None
            if not isinstance(entry, dict) or not isinstance(entry.get("top_files"), list):
                lacking.append(result.get("id"))
        if lacking:
            problems.append(f"no {backend} result with a top_files list for {_some(lacking)}")
    no_summary = [b for b in BENCH_BACKENDS if not isinstance(doc["summary"].get(b), dict)]
    if no_summary:
        problems.append(f"no summary for backends {', '.join(no_summary)}")
    return problems


def run_native_bench(
    runner: QmdRunner,
    index_name: str,
    queries: list,
    scratch_home: Path,
    timeout: float,
    db_path: Path,
    arm_results: dict,
    section=None,
) -> dict:
    """Runs ``qmd bench``; ``section`` (default: a new dict) is filled in place,
    so an interrupted benchmark still shows its fixture and state."""
    section = {} if section is None else section
    fixture = build_bench_fixture(queries)
    fixture_bytes = (json.dumps(fixture, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    bench_dir = scratch_home / "bench"
    bench_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = bench_dir / "fixture.json"
    fixture_path.write_bytes(fixture_bytes)
    section.update({
        "evidence_class": "upstream_native_operation",
        "evidence_note": (
            "QMD's own `qmd bench` command and scorer (README 'Benchmarking'; src/bench/bench.ts and "
            "src/bench/score.ts at the pinned commit), run on this run's index with a fixture this "
            "script derived from queries.json. Non-gating corroboration; the preregistered decision "
            "uses only the nDCG@10 rule above."
        ),
        "status": "started",
        "fixture": {
            "sha256": sha256_bytes(fixture_bytes),
            "expected_in_top_k": BENCH_EXPECTED_IN_TOP_K,
            "derivation": (
                "One fixture query per queries.json query, same id and text; expected_files = the "
                "query's grade-2 paths as qmd:// virtual paths; type = keyword->exact, "
                "natural_language->semantic, paraphrased_indirect->alias (labels only)."
            ),
            "content": fixture,
        },
        "llm_cache_rows_before": count_llm_cache(db_path),
    })
    call = runner.run(
        "native_bench", "native_bench", ["--index", index_name, "bench", str(fixture_path), "--json"], timeout
    )
    section.update(
        {
            "command": call.record["argv"],
            "native_record_id": call.record["id"],
            "exit_code": call.exit_code,
            "stdout_sha256": call.record["stdout_sha256"],
            "llm_cache_rows_after": count_llm_cache(db_path),
        }
    )
    if call.timed_out:
        section["status"] = "timed_out"
        return section
    if call.exit_code != 0:
        section["status"] = "failed"
        section["error"] = runner.san(strip_ansi(call.stderr))[-800:]
        return section
    try:
        doc = json.loads(call.stdout)
    except json.JSONDecodeError as exc:
        section["status"] = "unparseable"
        section["error"] = f"bench --json output is not JSON: {exc}"
        return section
    if not isinstance(doc, dict) or not isinstance(doc.get("summary"), dict) or not isinstance(doc.get("results"), list):
        section["status"] = "unexpected_shape"
        section["error"] = "bench --json output lacks a summary object or results array"
        return section
    problems = bench_output_problems(doc, fixture)
    if problems:
        section["status"] = "incomplete"
        section["error"] = runner.san("bench --json output does not cover the fixture: " + "; ".join(problems))
        section["native_query_count"] = len(doc["results"])
        return section
    section["native_summary"] = doc["summary"]
    section["native_query_count"] = len(doc["results"])
    section["exact_identity_audit"] = audit_native_bench(doc, fixture, arm_results)
    section["status"] = "completed"
    return section


# --------------------------------------------------------------------------
# Bootstrap CI + decision rule
# --------------------------------------------------------------------------

def paired_bootstrap_ci(diffs: list, iterations: int, seed: int) -> dict:
    # Resampling the 30 per-query (B_i - A_i) nDCG@10 differences with
    # replacement is algebraically identical to resampling the 30 (A_i, B_i)
    # pairs and recomputing mean(B) - mean(A) on each resample, since
    # mean(B_resample) - mean(A_resample) == mean(B_i - A_i over the same
    # resampled indices) by linearity of the mean. PREREGISTRATION.md
    # specifies the pair-resampling form; this is that computation.
    rng = random.Random(seed)
    n = len(diffs)
    resample_means = []
    for _ in range(iterations):
        resample_means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    resample_means.sort()
    lo_idx = int(iterations * 0.025)
    hi_idx = min(int(iterations * 0.975), iterations - 1)
    return {
        "iterations": iterations,
        "seed": seed,
        "lower_95": resample_means[lo_idx],
        "upper_95": resample_means[hi_idx],
        "method": (
            "Nearest-rank percentile on ascending-sorted resample means of mean(B)-mean(A) "
            f"over N={iterations} resamples of the 30 paired per-query nDCG@10 differences, "
            f"each drawn with replacement (Python random.Random(seed={seed})). "
            f"lower=sorted[floor(0.025*N)], upper=sorted[min(floor(0.975*N), N-1)], both 0-indexed."
        ),
    }


def decide(arm_a_summary: dict, arm_b_status: str, arm_b_summary: dict, bootstrap: dict) -> dict:
    if arm_b_status != "evaluated":
        return {
            "gain_ndcg_at_10": None,
            "bootstrap_ci": None,
            "condition_1_gain_ge_0_05": None,
            "condition_2_ci_excludes_zero": None,
            "decision": "BM25 (Arm A) stays the default",
            "reason": "Arm B was not evaluated (not_run), which is distinct from Arm B being tried and losing.",
        }
    gain = arm_b_summary["mean_ndcg_at_10"] - arm_a_summary["mean_ndcg_at_10"]
    cond1 = gain >= GAIN_THRESHOLD
    cond2 = bootstrap["lower_95"] > 0
    selected = cond1 and cond2
    return {
        "gain_ndcg_at_10": gain,
        "bootstrap_ci": bootstrap,
        "condition_1_gain_ge_0_05": cond1,
        "condition_2_ci_excludes_zero": cond2,
        "decision": "Hybrid (Arm B) selected over BM25" if selected else "BM25 (Arm A) stays the default",
        "reason": (
            "Both preregistered conditions held."
            if selected
            else "At least one preregistered condition failed; an inconclusive or negative result "
            "does not disturb QMD's current BM25-only profile."
        ),
    }


# --------------------------------------------------------------------------
# Report rendering (tolerates aborted and partial receipts)
# --------------------------------------------------------------------------

def fmt(x, digits=4):
    return "n/a" if not isinstance(x, (int, float)) else f"{x:.{digits}f}"


# How the report names an arm that has no summary. "not_run" is the
# protocol's "not evaluated" (Arm B failed closed, or --skip-arm-b).
ARM_STATUS_LABELS = {
    "not_run": "not evaluated",
    "not_reached": "not reached",
    "interrupted": "interrupted",
    "aborted": "aborted",
}


def render_report(receipt: dict) -> str:
    arm_a = receipt.get("arm_a") or {}
    arm_b = receipt.get("arm_b") or {}
    a = arm_a.get("summary")
    b = arm_b.get("summary")
    b_status = arm_b.get("status")
    decision = receipt.get("decision")
    ci = (decision or {}).get("bootstrap_ci") or {}
    run_id = receipt.get("run_id", "unknown")
    status = receipt.get("status", "unknown")
    outputs = receipt.get("outputs") or {}
    qmd_version = receipt.get("qmd_version") or "unknown"
    index_name = (receipt.get("index") or {}).get("index_name") or INDEX_NAME_DEFAULT
    n_queries = receipt.get("query_count") or (a or b or {}).get("query_count", 30)

    lines = [f"# Retrieval quality v2 run {run_id}: BM25 vs. hybrid", ""]
    lines.append(
        f"Status: `{status}`. Evidence class: `{receipt.get('evidence_class', 'local_integration')}` "
        f"(this repository's harness around upstream QMD commands). Receipt: "
        f"[{outputs.get('results', f'results-{run_id}.json')}]({outputs.get('results', f'results-{run_id}.json')}); "
        f"native qmd output: [{outputs.get('native', f'native-{run_id}.json')}]({outputs.get('native', f'native-{run_id}.json')})."
    )
    lines.append("")
    if receipt.get("abort_reason"):
        label = "Stopped after the decision" if decision else "Aborted before a decision"
        lines.append(f"**{label}:** {receipt['abort_reason']}")
        lines.append("")
    for label, arm in (("Arm A", arm_a), ("Arm B", arm_b)):
        if arm.get("status") in ("interrupted", "aborted"):
            lines.append(
                f"{label} was {arm['status']} after {len(arm.get('per_query') or [])} of {n_queries} queries. "
                "The receipt keeps those queries' scores, but no arm mean or decision is computed "
                "from a partial arm."
            )
            lines.append("")
    if a is not None and b_status == "evaluated" and b is not None and decision:
        lines.append(
            f"QMD **{qmd_version}** evaluated all {n_queries} preregistered held-out queries against both "
            f"arms over the same frozen index. Arm A (BM25) scored nDCG@10={fmt(a['mean_ndcg_at_10'])}; "
            f"Arm B (hybrid, CPU) scored nDCG@10={fmt(b['mean_ndcg_at_10'])}. **{decision['decision']}** "
            f"(gain={fmt(decision['gain_ndcg_at_10'])}, threshold={GAIN_THRESHOLD}, 95% bootstrap "
            f"CI=[{fmt(ci.get('lower_95'))}, {fmt(ci.get('upper_95'))}])."
        )
    elif a is not None and decision:
        lines.append(
            f"QMD **{qmd_version}** evaluated Arm A (BM25) against all {n_queries} preregistered held-out "
            f"queries: nDCG@10={fmt(a['mean_ndcg_at_10'])}. **Arm B (hybrid) was not evaluated** -- "
            f"{arm_b.get('not_run_reason') or 'reason not recorded'}. Per PREREGISTRATION.md, a "
            f"not-evaluated Arm B cannot satisfy the decision rule, so **{decision['decision']}**, "
            "distinct from Arm B having been tried and lost."
        )
    lines.append("")

    lines.append("| Metric (mean over all queries) | Arm A -- BM25 (`search`) | Arm B -- hybrid (`query`, CPU) |")
    lines.append("| --- | ---: | ---: |")

    def state(arm):
        return ARM_STATUS_LABELS.get(arm.get("status"), arm.get("status") or "not run")

    def cell(arm, summary, key):
        return fmt(summary.get(key)) if summary else state(arm)

    b_eval = b if b_status == "evaluated" else None
    for label, key in (
        ("nDCG@10", "mean_ndcg_at_10"),
        ("recall@5 (grade-2 files)", "mean_recall_at_5"),
        ("MRR", "mean_mrr"),
    ):
        lines.append(f"| {label} | {cell(arm_a, a, key)} | {cell(arm_b, b_eval, key)} |")

    def count(arm, summary, key):
        return f"{len(summary.get(key) or [])}/{summary.get('query_count', n_queries)}" if summary else state(arm)

    lines.append(
        f"| Queries erroring/timing out/rejected | {count(arm_a, a, 'errored_queries')} | "
        f"{count(arm_b, b_eval, 'errored_queries')} |"
    )
    lines.append(
        f"| Queries with no results | {count(arm_a, a, 'empty_result_queries')} | "
        f"{count(arm_b, b_eval, 'empty_result_queries')} |"
    )
    lines.append("")
    lines.append(
        "recall@5 and MRR are secondary, non-gating evidence per PREREGISTRATION.md's Decision rule; "
        "only nDCG@10's mean gain and bootstrap CI decide between arms."
    )
    lines.append("")

    lines.append("## Decision")
    lines.append("")
    if decision:
        lines.append(f"**{decision['decision']}.** {decision['reason']}")
        if b_status == "evaluated":
            lines.append("")
            lines.append(
                f"- Condition 1 (gain &ge; {GAIN_THRESHOLD}): {decision['condition_1_gain_ge_0_05']} "
                f"(gain={fmt(decision['gain_ndcg_at_10'])})"
            )
            lines.append(
                f"- Condition 2 (paired bootstrap 95% CI excludes 0): {decision['condition_2_ci_excludes_zero']} "
                f"(CI=[{fmt(ci.get('lower_95'))}, {fmt(ci.get('upper_95'))}], {ci.get('iterations')} resamples, "
                f"seed={ci.get('seed')})"
            )
    else:
        lines.append("No decision: the run stopped before the decision rule could be applied.")
    lines.append("")

    lines.append("## Model provenance (Arm B)")
    lines.append("")
    models = (arm_b.get("model_provenance") or {}).get("models") or []
    if models:
        lines.append(
            "QMD's default hybrid-mode models, pulled into the scratch HOME's own model cache. Each "
            "revision is accepted only because Hugging Face lists the pulled file at that revision with "
            "the same LFS sha256 and size as the downloaded bytes:"
        )
        lines.append("")
        lines.append("| Role | HF repository | Revision | File | sha256 | Size |")
        lines.append("| --- | --- | --- | --- | --- | ---: |")
        for m in models:
            lines.append(
                f"| {m['role']} | [{m['hf_repo_id']}](https://huggingface.co/{m['hf_repo_id']}) | "
                f"`{m['hf_repo_revision']}` | `{m['filename']}` | `{m['sha256']}` | {m['pull_size_reported']} |"
            )
        skipped = arm_b.get("expansion_skipped_queries")
        if skipped is not None:
            lines.append("")
            lines.append(
                f"QMD skipped its query-expansion (generate) model for {len(skipped)} of "
                f"{len(arm_b.get('per_query') or [])} Arm B queries, counted from the retained native "
                "stderr of each query (its \"Strong BM25 signal\" line)."
            )
    else:
        lines.append(f"Not applicable -- {arm_b.get('not_run_reason') or 'Arm B did not reach model pinning.'}")
    lines.append("")

    bench = receipt.get("native_bench") or {}
    lines.append("## QMD's own benchmark (`qmd bench`, upstream native operation)")
    lines.append("")
    if bench.get("status") == "completed":
        summary = bench.get("native_summary") or {}
        audit = bench.get("exact_identity_audit") or {}
        lines.append(
            f"`qmd --index {index_name} bench <fixture> --json` ran all four upstream backends on the same "
            f"index (fixture sha256 `{(bench.get('fixture') or {}).get('sha256')}`: each query's grade-2 "
            "files, expected in the top 5). The native columns are QMD's own returned averages; the exact "
            "columns re-score the same returned `top_files` with exact path identity."
        )
        lines.append("")
        lines.append(
            "| Backend | Native P@k | Native recall@5 | Native MRR | Exact recall@5 | Exact MRR | "
            "Native/exact recall@5 disagreements | Avg latency (ms) |"
        )
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        for backend in BENCH_BACKENDS:
            s = summary.get(backend)
            if not isinstance(s, dict):
                continue
            e = audit.get(backend) or {}
            lines.append(
                f"| {backend} | {fmt(s.get('avg_precision'))} | {fmt(s.get('avg_recall_at_5'))} | "
                f"{fmt(s.get('avg_mrr'))} | {fmt(e.get('exact_mean_recall_at_5'))} | {fmt(e.get('exact_mean_mrr'))} | "
                f"{len(e.get('native_vs_exact_recall_at_5_disagreements') or [])} | {fmt(s.get('avg_latency_ms'), 0)} |"
            )
        for backend in ("bm25", "full"):
            e = audit.get(backend) or {}
            if "cli_rankings_compared" in e:
                lines.append("")
                lines.append(
                    f"- `{backend}` top-10 rankings identical to {e['cli_arm']}'s CLI rankings for "
                    f"{e['cli_rankings_identical']} of {e['cli_rankings_compared']} queries."
                )
        lines.append(
            f"- QMD's LLM cache held {bench.get('llm_cache_rows_before')} rows before the bench and "
            f"{bench.get('llm_cache_rows_after')} after it."
        )
    else:
        lines.append(
            f"Status `{bench.get('status', 'not_run')}`"
            + (f": {bench.get('error') or bench.get('reason')}" if (bench.get("error") or bench.get("reason")) else ".")
        )
    lines.append("")

    lines.append("## Known limitations")
    lines.append("")
    for item in receipt.get("limitations") or []:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Durations")
    lines.append("")
    lines.append("| Phase | Duration |")
    lines.append("| --- | ---: |")
    for phase, seconds in (receipt.get("durations_seconds") or {}).items():
        if seconds is not None:
            lines.append(f"| {phase} | {seconds:.1f}s |")
    lines.append("")

    lines.append("## Exact commands")
    lines.append("")
    lines.append(
        "Every qmd call runs with the scratch HOME as its working directory and a minimal environment: "
        "`PATH` and proxy/CA variables from the caller, `HOME`/`XDG_*`/`TMPDIR` under `$SCRATCH_HOME`, "
        "`INDEX_PATH=$SCRATCH_HOME/.cache/qmd/<index>.sqlite`, `QMD_CONFIG_DIR=$SCRATCH_HOME/.config/qmd`, "
        "`QMD_FORCE_CPU=1`, `NODE_LLAMA_CPP_GPU=false`, `NO_COLOR=1` and `MCP_AUTO_OPEN_ENABLED=false`. "
        "No other caller variable reaches qmd."
    )
    lines.append("")
    lines.append("```sh")
    lines.append("python3 blueprints/retrieval-quality-v2/run.py \\")
    lines.append('  --repo "$STACK_REPO" --scratch-home "$SCRATCH_HOME"')
    lines.append("")
    lines.append("# what run.py runs under the hood:")
    lines.append(f"qmd --index {index_name} --version")
    lines.append(f'qmd --index {index_name} collection add "$STAGE/blueprints/us-equities" \\')
    lines.append("  --name rqv2-foundation --mask '**/*.md'")
    lines.append(f'qmd --index {index_name} collection add "$STAGE/catalogs/us-equities" \\')
    lines.append("  --name rqv2-catalog --mask '**/*.md'")
    lines.append(f'qmd --index {index_name} collection add "$STAGE/observability" \\')
    lines.append("  --name rqv2-observability --mask '**/*.md'")
    lines.append(f"qmd --index {index_name} update")
    lines.append(f"qmd --index {index_name} status")
    lines.append(f'qmd --index {index_name} search "<query>" -n 10 --format json   # Arm A')
    lines.append(f"qmd --index {index_name} pull    # Arm B only: default embed/generate/rerank models")
    lines.append(f"qmd --index {index_name} embed   # Arm B only")
    lines.append(f'qmd --index {index_name} query "<query>" -n 10 --format json    # Arm B')
    lines.append(f'qmd --index {index_name} bench "$SCRATCH_HOME/bench/fixture.json" --json   # upstream benchmark')
    lines.append("```")
    lines.append("")

    qmd = receipt.get("qmd") or {}
    package = qmd.get("package") or {}
    lines.append("## Reviewed upstream implementation")
    lines.append("")
    lines.append(
        f"QMD `{receipt.get('qmd_version_raw') or 'unknown'}`, installed package "
        f"`{package.get('name', 'unknown')}` {package.get('version', 'unknown')} (build commit "
        f"`{package.get('build_commit', 'unknown')}`; module sha256 values in the receipt). The `file` "
        "field's `qmd://<collection>/<relative-path>?index=<name>` shape and `docid` = first 6 hex chars "
        "of the content sha256 come from `dist/cli/formatter.js` (`searchResultsToJson`) and "
        "`dist/store.js` (`getDocid`); the default model URIs from `dist/llm.js`; the environment "
        "precedence from `dist/store.js` (`getDefaultDbPath`) and `dist/collections.js` (`getConfigDir`); "
        "the benchmark from `dist/bench/bench.js` and `dist/bench/score.js`."
    )
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Outputs: unique per run, never overwritten
# --------------------------------------------------------------------------

def run_outputs(output_dir: Path, run_id: str) -> dict:
    return {
        "results": output_dir / f"results-{run_id}.json",
        "native": output_dir / f"native-{run_id}.json",
        "report": output_dir / f"report-{run_id}.md",
    }


def write_new(path: Path, text: str) -> None:
    """Creates ``path``; raises FileExistsError rather than replacing anything."""
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(text)


def replace_reserved(path: Path, text: str) -> None:
    """Atomically rewrites the results file this run reserved for itself."""
    tmp = path.with_name(path.name + ".partial")
    write_new(tmp, text)
    os.replace(tmp, path)


def to_json(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def settle_statuses(receipt: dict) -> None:
    """Gives both arms and the benchmark a final status once a run has ended.

    Whatever was still running when the run stopped becomes ``interrupted``
    (a signal) or ``aborted`` (a failure), with the run's abort reason; what it
    never started becomes ``not_reached``. A completed run changes nothing.
    """
    outcome = "interrupted" if receipt.get("status") == "aborted_interrupted" else "aborted"
    reason = receipt.get("abort_reason")
    for key in ("arm_a", "arm_b"):
        arm = receipt[key]
        if arm.get("status") == "running":
            arm["status"] = outcome
            arm["stop_reason"] = reason
        elif arm.get("status") == "pending":
            arm["status"] = "not_reached"
    bench = receipt["native_bench"]
    if bench.get("status") in (None, "started"):
        bench["status"] = outcome
        bench["reason"] = reason
    elif bench.get("status") == "pending":
        bench["status"] = "not_reached"


# --------------------------------------------------------------------------
# CLI / main
# --------------------------------------------------------------------------

def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", default=str(DEFAULT_REPO), help="path to the native-agent-stack checkout")
    p.add_argument(
        "--scratch-home",
        default=None,
        help="scratch HOME/XDG root for QMD's index+model cache (default: a fresh temp dir; "
        "never the host's real HOME, and never committed)",
    )
    p.add_argument("--index-name", default=INDEX_NAME_DEFAULT)
    p.add_argument("--qmd-bin", default=None, help="default: resolved via shutil.which('qmd')")
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--skip-arm-b", action="store_true", help="BM25-only run; skips model pull/embed/query entirely")
    p.add_argument("--skip-native-bench", action="store_true", help="do not run `qmd bench` after the arms")
    p.add_argument("--bootstrap-iterations", type=int, default=BOOTSTRAP_ITERATIONS_DEFAULT)
    p.add_argument("--bootstrap-seed", type=int, default=BOOTSTRAP_SEED_DEFAULT)
    p.add_argument("--index-timeout", type=float, default=300.0)
    p.add_argument("--arm-a-query-timeout", type=float, default=60.0)
    p.add_argument("--arm-b-query-timeout", type=float, default=240.0)
    p.add_argument("--pull-timeout", type=float, default=1800.0)
    p.add_argument("--embed-timeout", type=float, default=900.0)
    p.add_argument("--bench-timeout", type=float, default=10800.0)
    p.add_argument(
        "--run-id",
        default=None,
        help="YYYYMMDDTHHMMSSZ naming this run's outputs (default: the UTC start time)",
    )
    p.add_argument(
        "--output-dir",
        default=None,
        help="directory for results-/native-/report-<run-id> (default: next to this script)",
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not RUN_ID_RE.fullmatch(run_id):
        print(f"error: --run-id must look like YYYYMMDDTHHMMSSZ, got {run_id!r}", file=sys.stderr)
        return 2
    output_dir = Path(args.output_dir).resolve() if args.output_dir else BLUEPRINT_DIR
    outputs = run_outputs(output_dir, run_id)
    existing = [p.name for p in outputs.values() if p.exists()]
    if existing:
        print(
            f"error: refusing to overwrite existing run output(s) {existing}; every run writes new "
            "files, so choose another --run-id or --output-dir",
            file=sys.stderr,
        )
        return 2

    if args.scratch_home:
        scratch_home = Path(args.scratch_home).resolve()
        scratch_home.mkdir(parents=True, exist_ok=True)
        owns_scratch = False
    else:
        scratch_home = Path(tempfile.mkdtemp(prefix="qmd-retrieval-quality-v2-"))
        owns_scratch = True

    san = Sanitizer(repo, scratch_home)
    started_monotonic = time.monotonic()
    durations = {
        "setup": None,
        "seal_verify": None,
        "corpus_staging": None,
        "index_build": None,
        "arm_a": None,
        "arm_b_pull": None,
        "arm_b_embed": None,
        "arm_b": None,
        "decision": None,
        "native_bench": None,
        "total_wall_clock": None,
    }
    outputs_rel = {key: path.name for key, path in outputs.items()}

    receipt = {
        # Schema 4 names the qmd call that was running when a signal arrived
        # (interruption.qmd_call_running_when_received, signals_received[].qmd_call)
        # apart from the call the stop cut short (cut_short_native_record_id,
        # schema 3's in_flight_native_record_id), and adds the benchmark status
        # incomplete. Schema 3 receipts come from run.py 0792745e. Schema 3 added
        # the arm and benchmark statuses pending, running, interrupted, aborted
        # and not_reached, plus query_count, interruption and signals_received.
        # Schema 2 receipts come from run.py efba31d5, which had no signal handling.
        "schema_version": 4,
        "run_id": run_id,
        "run_date": run_id[:8],
        "generated_at_utc": utc_now_iso(),
        "generated_at_human": datetime.now(timezone.utc).strftime("%B %d, %Y"),
        "status": "started",
        "status_note": (
            "Reserved when the run started. The runner rewrites this receipt when the run ends, "
            "a stop by SIGINT, SIGTERM or SIGHUP included; a receipt still at status 'started' means "
            "the runner was killed by a signal it cannot handle, such as SIGKILL, before it could "
            "record an outcome."
        ),
        "evidence_class": "local_integration",
        "evidence_class_note": (
            "run.py is this repository's harness around upstream QMD CLI commands; its metrics and "
            "decision are local integration evidence. The native_bench section is QMD's own benchmark "
            "command and scorer (upstream native operation), reported separately and non-gating."
        ),
        "preregistration": "PREREGISTRATION.md",
        "queries_file": "queries.json",
        "harness": {"path": HARNESS_REL, "sha256": sha256_file(SCRIPT_PATH)},
        "outputs": outputs_rel,
        "qmd_version": None,
        "qmd_version_raw": None,
        "qmd": None,
        "index": {"index_name": args.index_name},
        "seal": {},
        "query_count": None,
        "corpus_commit": None,
        "corpus_staging": [],
        "arm_a": {"status": "pending", "per_query": [], "summary": None},
        "arm_b": {"status": "pending", "per_query": [], "summary": None, "model_provenance": None, "not_run_reason": None},
        "decision": None,
        "native_bench": {"status": "pending"},
        "interruption": None,
        "signals_received": [],
        "durations_seconds": durations,
        "environment": {
            "python_version": sys.version.split()[0],
            "cpu_forced": True,
            "gpu_used": False,
            "cpu_count": os.cpu_count(),
            "scratch_home_owned_by_this_run": owns_scratch,
        },
        "limitations": [],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        write_new(outputs["results"], to_json(receipt))
    except FileExistsError:
        print(f"error: {outputs['results'].name} appeared concurrently; refusing to overwrite it", file=sys.stderr)
        return 2

    exit_code = 0
    runner = None
    stops = StopRequests()

    def t(key):
        class _Timer:
            def __enter__(self_inner):
                self_inner.start = time.monotonic()
                stops.phase = key
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):
                durations[key] = time.monotonic() - self_inner.start
                stops.phase = None
                if exc is not None and not hasattr(exc, "run_phase"):
                    with contextlib.suppress(AttributeError):
                        exc.run_phase = key  # the phase the exception left

        return _Timer()

    def record_interruption(signum: int, received_at, phase, running, cause=None) -> int:
        """Sets status aborted_interrupted with its details; returns the exit code.

        ``running`` is the qmd call that was running when the signal arrived, which may have
        finished before the runner acted on the stop; the call the stop cut short, if any, is
        the last native record, marked ``interrupted_by``.
        """
        last = runner.records[-1] if runner is not None and runner.records else None
        cut_short = last["id"] if last is not None and last.get("interrupted_by") else None
        if received_at is None and running is None:
            # A caller's own SIGINT handler raised KeyboardInterrupt where the runner was
            # waiting, so the call that exception cut short is the one that was running.
            running = cut_short
        name = signal_name(signum)
        receipt["status"] = "aborted_interrupted"
        receipt["interruption"] = {
            "signal": name,
            "received_at_utc": received_at,
            "phase_when_received": phase,
            "qmd_call_running_when_received": running,
            "acted_on_at_utc": utc_now_iso_ms(),
            "cut_short_native_record_id": cut_short,
        }
        reason = f"stopped by {name} during {phase or 'the runner work between phases'}"
        if cut_short:
            reason += (
                f"; the qmd call it cut short ({cut_short}) was killed with its process group and is kept in "
                f"{outputs_rel['native']} with its partial output"
            )
        elif running:
            reason += (
                f"; the qmd call that was running when the signal arrived ({running}) finished before the "
                f"runner acted on the stop, so no qmd call was cut short; that call is kept in "
                f"{outputs_rel['native']}"
            )
        else:
            reason += "; no qmd call was running"
        if cause is not None:
            reason += f"; the run was already stopping when this failure followed: {cause}"
        receipt["abort_reason"] = san(reason)
        return 128 + signum

    try:
        stops.arm()
        with t("setup"):
            qmd_bin = args.qmd_bin or shutil.which("qmd")
            if not qmd_bin:
                raise RunFailure("qmd_not_found", "qmd not found on PATH (command -v qmd)")
            env, not_inherited = qmd_env(scratch_home, args.index_name)
            receipt["environment"]["qmd_env"] = {
                "keys": sorted(env),
                "bound": {
                    key: san(env[key])
                    for key in (
                        "HOME",
                        "XDG_CACHE_HOME",
                        "XDG_CONFIG_HOME",
                        "XDG_DATA_HOME",
                        "TMPDIR",
                        "INDEX_PATH",
                        "QMD_CONFIG_DIR",
                        "QMD_FORCE_CPU",
                        "NODE_LLAMA_CPP_GPU",
                        "NO_COLOR",
                        "MCP_AUTO_OPEN_ENABLED",
                    )
                },
                "passed_through_from_caller": sorted(k for k in QMD_ENV_PASSTHROUGH if k in env),
                "caller_qmd_variables_not_inherited": not_inherited,
                "cwd": "<SCRATCH_HOME>",
            }
            runner = QmdRunner(qmd_bin, env, scratch_home, san, stops)
            receipt["qmd"] = describe_qmd_install(qmd_bin, san)
            ver = runner.setup("qmd:version", "setup", ["--index", args.index_name, "--version"], 30, "qmd_version")
            receipt["qmd_version_raw"] = san(ver.stdout.strip() or ver.stderr.strip())
            # "qmd --version" prints "qmd 2.8.3 (facd35e)"; keep just the semver for
            # qmd_version and the full banner in qmd_version_raw.
            version_match = re.search(r"(\d+\.\d+\.\d+)", receipt["qmd_version_raw"] or "")
            receipt["qmd_version"] = version_match.group(1) if version_match else receipt["qmd_version_raw"]

        with t("seal_verify"):
            seal = verify_seal(repo)
        receipt["seal"] = {
            "queries_sha256": seal["queries_sha256"],
            "prereg_pinned_sha256": seal["prereg_pinned_sha256"],
            "match": True,
            # The whole PREREGISTRATION.md as read before any qmd query, so a
            # dated amendment can be shown to predate this run's results.
            "preregistration_sha256": seal["preregistration_sha256"],
        }
        doc = seal["doc"]
        queries = doc["queries"]
        corpus = doc["corpus"]
        commit = doc["corpus_commit"]
        receipt["query_count"] = len(queries)
        receipt["corpus_commit"] = commit

        stage_dir = scratch_home / "corpus-stage"
        with t("corpus_staging"):
            staged = stage_corpus(repo, commit, corpus, stage_dir)
        receipt["corpus_staging"] = staged
        stops.checkpoint()

        with t("index_build"):
            index_summary = build_index(runner, env, stage_dir, args.index_name, args.index_timeout, corpus, san)
        receipt["index"].update(index_summary)

        arm_a = receipt["arm_a"]
        arm_a["status"] = "running"
        with t("arm_a"):
            run_arm(
                runner, args.index_name, "search", "arm_a", queries, corpus, args.arm_a_query_timeout, args.top_k,
                results=arm_a["per_query"],
            )
        arm_a["status"] = "evaluated"
        arm_a["summary"] = summarize_arm(arm_a["per_query"])

        arm_b = receipt["arm_b"]
        if args.skip_arm_b:
            arm_b["status"] = "not_run"
            arm_b["not_run_reason"] = "--skip-arm-b was passed"
        else:
            arm_b["status"] = "running"
            try:
                with t("arm_b_pull"):
                    provenance = pull_and_pin_models(runner, args.index_name, scratch_home, args.pull_timeout, san)
                # Recorded as soon as it exists, so a subsequent embed failure
                # still leaves the resolved model provenance in the receipt.
                arm_b["model_provenance"] = provenance

                with t("arm_b_embed"):
                    embed_summary = embed_index(runner, args.index_name, args.embed_timeout, len(corpus), san)
                arm_b["embed_summary"] = embed_summary
            except RunFailure as exc:
                if stops.requested():
                    # A failure that follows a stop request is part of stopping, not a
                    # finding about Arm B: the handler below records it with the stop.
                    raise
                # PREREGISTRATION.md: Arm B fails closed and is reported as not evaluated.
                arm_b["status"] = "not_run"
                arm_b["not_run_reason"] = san(f"[{exc.slug}] {exc}")
            else:
                with t("arm_b"):
                    run_arm(
                        runner, args.index_name, "query", "arm_b", queries, corpus, args.arm_b_query_timeout,
                        args.top_k, results=arm_b["per_query"],
                    )
                arm_b["status"] = "evaluated"
                arm_b["summary"] = summarize_arm(arm_b["per_query"])
                stderr_by_record = {r["id"]: r["stderr"] for r in runner.records}
                arm_b["expansion_skipped_queries"] = [
                    r["id"]
                    for r in arm_b["per_query"]
                    if "Strong BM25 signal" in stderr_by_record.get(r["native_record_id"], "")
                ]

        stops.checkpoint()
        with t("decision"):
            if arm_b["status"] == "evaluated":
                pairs = zip(arm_a["per_query"], arm_b["per_query"], strict=True)
                diffs = [b["ndcg_at_10"] - a["ndcg_at_10"] for a, b in pairs]
                bootstrap = paired_bootstrap_ci(diffs, args.bootstrap_iterations, args.bootstrap_seed)
                receipt["decision"] = decide(arm_a["summary"], "evaluated", arm_b["summary"], bootstrap)
            else:
                receipt["decision"] = decide(arm_a["summary"], "not_run", None, None)

        # The decision's limitations are recorded before the benchmark starts, so a run
        # stopped during the benchmark still carries them with its decision.
        a_summary = arm_a["summary"]
        receipt["limitations"] = [
            "Arm A is QMD's lexical `search` command as research workers call it, not BM25 in general: it "
            f"returned no candidates for {len(a_summary['empty_result_queries'])} of {a_summary['query_count']} "
            "queries in this run. The decision measures QMD hybrid `query` against QMD lexical `search`; a "
            "relaxed or disjunctive BM25 baseline over the same index is a separate, unrun comparison.",
            "30 queries against 33 short documents is a small-sample comparison; the paired bootstrap "
            "CI is the safeguard against reading noise as a real gain, not a substitute for a larger corpus.",
            "This protocol measures retrieval quality only (nDCG@10, recall@5, MRR); it does not measure "
            "end-to-end answer quality, latency at scale, or provider-token cost.",
            "The query author's relevance judgments reflect one reader's understanding of "
            "\"directly answers\" vs. \"partially relevant\", not adjudicated multi-rater agreement.",
            "run.py is this repository's harness around upstream QMD commands, so its metrics and "
            "decision are local_integration evidence, not an upstream test.",
        ]
        if arm_b["status"] == "evaluated":
            receipt["limitations"] += [
                "Arm B's models ran forced onto CPU on a shared host; a GPU run or a different host's CPU "
                "could show different absolute latency.",
                "QMD adaptively skips its query-expansion model per-query when its BM25 signal is already "
                "strong; not every Arm B query exercised all three pulled models.",
            ]
        else:
            receipt["limitations"].append(f"Arm B was not evaluated: {arm_b['not_run_reason']}")

        if args.skip_native_bench:
            receipt["native_bench"] = {"status": "not_run", "reason": "--skip-native-bench was passed"}
        elif arm_b["status"] != "evaluated":
            receipt["native_bench"] = {
                "status": "not_run",
                "reason": "qmd bench's vector/hybrid/full backends need Arm B's models and embeddings, which were not prepared",
            }
        else:
            bench = receipt["native_bench"] = {}
            with t("native_bench"):
                run_native_bench(
                    runner,
                    args.index_name,
                    queries,
                    scratch_home,
                    args.bench_timeout,
                    index_db_path(env),
                    {"arm_a": arm_a["per_query"], "arm_b": arm_b["per_query"]},
                    section=bench,
                )
        if receipt["native_bench"].get("status") != "not_run":
            receipt["limitations"].append(
                "`qmd bench` is QMD's own command and scorer, but its fixture is derived here from "
                "queries.json, its scorer lowercases paths and accepts suffix matches in either direction "
                "(the exact-identity audit re-scores the same returned rankings), and its precision@k divides "
                "by min(k, expected files). It ran after Arm B on the same index, so QMD's LLM cache may serve "
                "its expansion/rerank results: its latencies may be warm, and its `full` backend is not an "
                "independent replication of Arm B's model calls. The LLM cache's row counts before and after "
                "it do not show which results were served from the cache."
            )

        receipt["status"] = (
            "completed_both_arms_evaluated" if arm_b["status"] == "evaluated" else "completed_arm_b_not_run"
        )

    except RunInterrupted as exc:
        first = stops.first()
        if first is not None:
            exit_code = record_interruption(*first)
        else:  # raised without a recorded signal, so not by this runner's StopRequests
            exit_code = record_interruption(exc.signum, None, getattr(exc, "run_phase", None), None)
    except KeyboardInterrupt as exc:
        # Raised by a SIGINT handler the caller installed; the runner leaves those in place.
        exit_code = record_interruption(int(signal.SIGINT), None, getattr(exc, "run_phase", None), None)
    except RunFailure as exc:
        first = stops.first()
        if first is not None:
            # For example, a terminal's SIGINT also reaches a `git show` that the
            # runner started in its own process group.
            exit_code = record_interruption(*first, cause=san(f"[{exc.slug}] {exc}"))
        else:
            receipt["status"] = f"aborted_{exc.slug}"
            receipt["abort_reason"] = san(str(exc))
            exit_code = 1
    except Exception as exc:  # top-level safety net: still write an honest partial receipt
        receipt["status"] = "aborted_unexpected_exception"
        receipt["abort_reason"] = san(f"{type(exc).__name__}: {exc}")
        exit_code = 1
    finally:
        try:
            settle_statuses(receipt)
            receipt.pop("status_note", None)
            receipt["signals_received"] = [
                {"signal": signal_name(signum), "received_at_utc": at, "phase": phase, "qmd_call": call}
                for signum, at, phase, call in stops.received
            ]
            durations["total_wall_clock"] = time.monotonic() - started_monotonic
            native_doc = {
                "schema_version": 1,
                "run_id": run_id,
                "results_file": outputs_rel["results"],
                "evidence_class": "native_cli_output",
                "sanitization": (
                    "stdout/stderr are decoded as UTF-8 (invalid bytes replaced); the repository checkout "
                    "becomes <STACK_REPO>, the scratch HOME <SCRATCH_HOME>, and any /home/<user> prefix ~. "
                    "*_raw_sha256/*_raw_bytes describe the bytes qmd returned; *_sha256 hashes the retained "
                    "text; *_identical_to_raw says whether they are the same bytes."
                ),
                "records": runner.records if runner is not None else [],
            }
            write_errors = []
            try:
                write_new(outputs["native"], to_json(native_doc))
            except OSError as exc:
                write_errors.append(f"native: {exc}")
            try:
                replace_reserved(outputs["results"], to_json(receipt))
            except OSError as exc:
                write_errors.append(f"results: {exc}")
            try:
                write_new(outputs["report"], render_report(receipt))
            except Exception as exc:  # the receipt is already on disk; say so rather than crash
                write_errors.append(f"report: {type(exc).__name__}: {exc}")

            print(f"status: {receipt['status']}")
            for key in ("results", "native", "report"):
                print(f"{key}: {outputs[key]}")
            if receipt.get("decision"):
                print(f"decision: {receipt['decision']['decision']}")
            for problem in write_errors:
                print(f"error writing output {problem}", file=sys.stderr)
            if write_errors:
                exit_code = 1
        finally:
            stops.restore()

    unrecorded = stops.received[len(receipt["signals_received"]):]
    if unrecorded:
        names = ", ".join(signal_name(signum) for signum, _at, _phase, _call in unrecorded)
        print(f"note: {names} arrived while the outputs were being written and is not in the receipt", file=sys.stderr)
    if exit_code == 0 and stops.received:
        # The run finished its work before it reached a point where it could stop;
        # it still reports that it was asked to stop.
        print(
            f"note: {signal_name(stops.received[0][0])} arrived after the last qmd call; the run completed first",
            file=sys.stderr,
        )
        exit_code = 128 + stops.received[0][0]
    return exit_code


def exit_process(code: int) -> None:
    """Ends the script with ``code``, or by the signal that stopped the run.

    A process that handled SIGINT, SIGTERM or SIGHUP and then exits normally
    looks to its caller like one that failed, and a shell running it in a loop
    carries on. Ending by the same signal, once the outputs are written, lets
    a shell, GNU timeout or a supervisor see the stop for what it was.
    """
    signum = code - 128 if code > 128 else None
    if signum is not None and signum in {int(s) for s in StopRequests.signals()}:
        sys.stdout.flush()
        sys.stderr.flush()
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)
    sys.exit(code)


if __name__ == "__main__":
    exit_process(main())
