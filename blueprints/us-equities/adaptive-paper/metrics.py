"""Read-only Prometheus exporter for the adaptive-paper durable ledger.

Runs as a separate process, bound to 127.0.0.1:18890 by default. It only ever
opens two files of the trial, strictly read-only:

  * ``--ledger`` (the ``ledger.sqlite3`` SQLite file `safety.Ledger` writes,
    opened with ``file:...?mode=ro`` so a write attempt would raise instead of
    silently succeeding), and
  * ``<ledger dir>/trial.json`` (the durable run-metadata file `runner.py`
    writes next to the ledger; override with ``--trial-json``).

The one file it writes is the Prometheus ``file_sd`` target list named by
``--file-sd`` (the backend profile renders it as
``<config-root>/adaptive-paper-targets.json``), plus that list's sibling
``.lock`` file. Prometheus scrapes job ``adaptive-paper`` only at registered
targets, so the ``EquitiesPaperMetricsMissing`` alert fires only while an
exporter is registered but not answering:

  * the exporter adds its own ``127.0.0.1:<port>`` target after its listener
    binds, and refuses to start (exit 2) when the list is unreadable or is not
    a ``file_sd`` target list, rather than serving unmonitored;
  * it removes that target only on a clean stop (SIGTERM or SIGINT) of a trial
    that finished (``trial.json`` phase ``finished``, or no ``trial.json``). A
    crashed or killed exporter, or a trial left at ``starting``,
    ``needs_attention`` or ``held_overnight``, stays registered, so the alert
    fires until an operator recovers the trial and runs ``--deregister``.

It never imports ``safety.Ledger`` (whose constructor opens the database for
writes and mutates schema/pragmas), never reads an env file or any credentials
path, and never talks to the broker or any network endpoint other than the
loopback HTTP listener it serves. No strategy, transport or account module is
imported.

## Metric derivation and documented gaps

Every exported metric is computed straight from the ledger's own tables
(``meta``, ``events``, ``requests``) or the sibling ``trial.json`` written by
``runner.py``; nothing here invents a field that is not already durably
recorded by ``safety.py``/``runner.py``:

* ``paper_trial_active`` -- 1 iff ``trial.json["phase"] == "starting"``
  (`runner.main` only sets ``phase`` to ``"starting"`` while a bounded trial
  is in flight, and to ``"finished"``/``"needs_attention"`` once it returns).
  Always exported (0 when trial.json is absent or phase is unknown) so the
  ``EquitiesPaperMetricsMissing`` alert only fires when the exporter itself,
  or its ledger path, is unreachable -- not merely because no trial is active.
* ``paper_needs_attention`` -- 1 iff ``trial.json["phase"] == "needs_attention"``.
  Always exported for the same reason.
* ``paper_reconciliation_status{result="..."}`` -- one series per known result
  label, 1 for the current ``trial.json["status"]`` value and 0 for the other
  known labels. ``status`` is the exact string `runner.main` copies from the
  run result (``passed``, ``completed_no_signals``, ``needs_attention``,
  ``not_started``, ``not_ready``, ``ready``, ``failed``). Exported only when
  ``trial.json`` has a ``status`` field (absent before a trial's first
  completed run).
* ``paper_order_state_divergence_total`` -- count of ``events`` rows with
  ``kind='risk_halt'`` whose JSON payload has ``reason == "external_order_detected"``.
  That is the one order-state divergence `safety.Ledger.freeze` durably
  records as an event (`runner.Controller.observe` calls
  ``ledger.freeze("external_order_detected")`` the instant it sees a broker
  order whose ``client_order_id`` the ledger never reserved). **Gap:**
  ``runner.reconcile``'s other mismatch types -- ``position_mismatch``,
  ``cash_mismatch_or_unmodeled_fees``, ``broker_intent_mismatch``,
  ``external_order_detected`` raised directly from `reconcile` before any
  order observation -- raise `SafetyError` and abort without writing any
  ledger event, so they are not counted here. Exported only when the ledger
  file is present and openable.
* ``paper_ledger_frozen{reason="..."}`` -- 1 for the ledger's current
  ``meta['halted_reason']`` (any reason `safety.Ledger.freeze`/`_refresh_risk`
  persisted); no series at all while the ledger is not frozen (this is the
  usual Prometheus idiom for a label-keyed state gauge -- see the
  ``max by (reason) (...) == 1`` alert expression).
* ``paper_request_budget_remaining`` / ``paper_request_budget_limit``
  ``{kind="rest"|"submit"}`` -- read-only recomputation of
  `safety.Ledger.request_budget`'s rolling one-minute window: count rows in
  ``requests`` with ``at`` in the last 60s (all kinds for ``rest``, only
  ``kind='submit'`` for ``submit``), and compare against
  ``meta['limits']['max_rest_per_minute']`` /
  ``['max_submits_per_minute']``. Exported only when the ledger file is
  present and openable.
* ``paper_ledger_readable`` -- 1 iff this scrape's read-only open of
  ``--ledger`` succeeded, 0 if the file is missing or the open/read failed.
  This is the exporter's own operational status, not a value read from the
  ledger's schema, and is the only signal for the four metrics above being
  silently absent (they are conditionally emitted, unlike
  ``paper_trial_active``/``paper_needs_attention``, so no ``absent()`` rule
  can target them directly). Always exported. Guarded by the
  ``EquitiesLedgerUnreadable`` alert.

Two requested metrics are **not derivable from the current ledger/trial.json
schema and are intentionally not exported** (see the trailing comment lines
in every response body):

* ``paper_reconciliation_last_success_timestamp_seconds`` -- `runner.reconcile`
  returns a result dict but never writes a durable, timestamped "reconciled"
  event into the ledger; the only place a reconciliation result is saved is
  the ephemeral, caller-chosen ``--output`` file passed to ``runner.py``,
  which this read-only exporter has no fixed, discoverable path to.
* ``paper_request_budget_wait_exceeded_total`` -- raised as
  ``SafetyError("request_budget_wait_exceeded")`` inside
  `runner.Controller.before_request`, entirely in the runner process; a
  delayed/denied budget wait leaves no row in the ledger's ``requests`` table
  and no ``events`` entry, so it cannot be recovered by reading the ledger
  after the fact.

Do not add these fields to ``safety.py`` merely to satisfy this exporter; if
a future ledger schema change records them durably, extend the derivation
above and drop the corresponding gap comment.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import sqlite3
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
DEFAULT_PORT = 18890
WINDOW_SECONDS = 60

KNOWN_RECONCILIATION_LABELS = {
    "passed", "completed_no_signals", "needs_attention",
    "not_started", "not_ready", "ready", "failed",
}

GAP_COMMENT = """\
# adaptive-paper-metrics gap: paper_reconciliation_last_success_timestamp_seconds is not exported.
# No per-reconciliation success timestamp is durably recorded in ledger.sqlite3 or trial.json;
# runner.reconcile() returns a result dict but does not persist a timestamped ledger event, and
# the per-run --output file has no fixed, exporter-discoverable path. See metrics.py module docstring.
# adaptive-paper-metrics gap: paper_request_budget_wait_exceeded_total is not exported.
# request_budget_wait_exceeded is raised by runner.Controller.before_request() in the runner
# process only; ledger.sqlite3's requests table records granted reservations, never denied waits.
# See metrics.py module docstring.
"""


def _escape_label(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _ledger_dir(ledger_path: Path) -> Path | None:
    """The resolved directory every readable path (`--ledger`, `--trial-json`,
    and any other path argument this exporter accepts) must live inside.
    Returns None if the ledger's parent directory does not exist/cannot be
    resolved -- callers must then treat every path as unreadable."""
    try:
        return Path(ledger_path).parent.resolve(strict=True)
    except OSError:
        return None


def _resolve_confined(path: Path, boundary: Path | None) -> Path | None:
    """Resolve `path` strictly (following symlinks) and require the result to
    live inside `boundary`. Returns the resolved path, or None if `boundary`
    is None, `path` does not exist/cannot be resolved, or the resolved path
    is outside `boundary` (including a symlink whose target escapes it).
    Callers must treat None as "refuse; never read" -- `resolve(strict=True)`
    only stats/reads the symlink chain, it never opens file contents, so a
    refusal here happens before any read is attempted."""
    if boundary is None:
        return None
    try:
        resolved = Path(path).resolve(strict=True)
    except OSError:
        return None
    try:
        resolved.relative_to(boundary)
    except ValueError:
        return None
    if resolved == boundary:
        return None
    return resolved


def _read_trial_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, NotADirectoryError, OSError, json.JSONDecodeError):
        return None


def _sqlite_ro_uri(path: Path) -> str:
    """Build a `file:` URI that SQLite opens strictly read-only. Built from
    `urllib.parse.quote` of the path, never by naive string concatenation: a
    raw `?`/`#` in the path would otherwise be interpreted as the start of
    the URI's query string, letting a filename like
    `.../probe?mode=memory&ignored=` silently override `mode=ro` (or escape
    the target file entirely) and yield a writable connection. As a second,
    independent guard, a resolved path containing `?` or `#` is refused
    outright rather than relying solely on percent-encoding.

    Deliberately does **not** add `immutable=1`: the ledger this exporter
    reads is a live WAL database that `safety.Ledger` holds open and keeps
    writing to for the whole duration of a trial (see the module docstring).
    SQLite's `immutable` hint asserts the file's content and schema never
    change for the life of the connection; against an actively-written WAL
    file that assertion is false, and the observed failure mode is not mere
    staleness but an outright `sqlite3.OperationalError: no such table: meta`
    on every scrape taken while a trial is running (the immutable connection
    does not read the WAL, and this database has no non-WAL schema image to
    fall back to). A plain `mode=ro` connection ignores `PRAGMA
    journal_mode`/state changes it doesn't need to and correctly reads
    committed WAL frames on each scrape, still strictly read-only: any write
    attempt raises `sqlite3.OperationalError` (see
    `test_open_ledger_readonly_connection_rejects_a_write_attempt`)."""
    text = str(path)
    if "?" in text or "#" in text:
        raise ValueError(f"ledger_path_rejected: reserved URI character in {text!r}")
    return "file:" + urllib.parse.quote(text) + "?mode=ro"


def _open_ledger_readonly(path: Path) -> sqlite3.Connection:
    """Open strictly read-only; raises rather than silently allowing a write."""
    uri = _sqlite_ro_uri(path)
    conn = sqlite3.connect(uri, uri=True, timeout=2)
    conn.row_factory = sqlite3.Row
    return conn


def _gauge(lines, name, help_text, samples):
    lines.append(f"# HELP {name} {help_text}")
    lines.append(f"# TYPE {name} gauge")
    for labels, value in samples:
        lines.append(f"{name}{labels} {value}")


def _counter(lines, name, help_text, value):
    lines.append(f"# HELP {name} {help_text}")
    lines.append(f"# TYPE {name} counter")
    lines.append(f"{name} {value}")


def render_metrics(ledger_path: Path, trial_path: Path, *, now: float | None = None) -> str:
    """Read the ledger/trial.json read-only and return Prometheus text-format output.

    Never writes to either file. ``now`` is injectable for deterministic tests;
    it never comes from the ledger and is only used for the rolling-window
    request-budget computation.
    """
    now = time.time() if now is None else now
    lines: list[str] = []
    # Every path this function reads is confined to the ledger's own
    # directory (see _ledger_dir/_resolve_confined): a `--trial-json` (or
    # `--ledger`) argument pointing outside it -- directly, or via a symlink
    # that escapes it -- is refused before any attempt to read its contents.
    boundary = _ledger_dir(ledger_path)
    trial_resolved = _resolve_confined(trial_path, boundary)
    metadata = _read_trial_json(trial_resolved) if trial_resolved is not None else None

    phase = metadata.get("phase") if isinstance(metadata, dict) else None
    active = 1 if phase == "starting" else 0
    needs_attention = 1 if phase == "needs_attention" else 0
    _gauge(lines, "paper_trial_active",
           '1 if trial.json phase is "starting" (an in-progress bounded trial); '
           "0 otherwise, including when trial.json is absent.", [("", active)])
    _gauge(lines, "paper_needs_attention",
           '1 if trial.json phase is "needs_attention"; 0 otherwise, including when '
           "trial.json is absent.", [("", needs_attention)])

    status = metadata.get("status") if isinstance(metadata, dict) else None
    if isinstance(status, str) and status:
        labels = sorted(KNOWN_RECONCILIATION_LABELS | {status})
        samples = [(f'{{result="{_escape_label(label)}"}}', 1 if label == status else 0) for label in labels]
        _gauge(lines, "paper_reconciliation_status",
               "1 for the current trial.json status result label, 0 for other known labels.", samples)

    ledger_resolved = _resolve_confined(ledger_path, boundary)
    if ledger_resolved is not None:
        try:
            conn = _open_ledger_readonly(ledger_resolved)
        except (sqlite3.OperationalError, ValueError) as exc:
            lines.append(f"# adaptive-paper-metrics gap: ledger open failed ({_escape_label(str(exc))}); "
                         "ledger-derived metrics omitted for this scrape.")
            conn = None
    else:
        lines.append("# adaptive-paper-metrics gap: ledger file not found or outside the configured "
                      "ledger directory; ledger-derived metrics omitted for this scrape.")
        conn = None

    # Always exported (not gated on the ledger being present/openable), independent of any
    # ledger-derived series above: this is the exporter's own read attempt outcome, not a value
    # read from the ledger's schema. A wrong --ledger path, a permissions problem, or a failed
    # read-only sqlite open would otherwise leave paper_order_state_divergence_total,
    # paper_ledger_frozen and the paper_request_budget_* series silently absent with no series
    # any absent()-based alert could target (they are conditionally emitted, unlike
    # paper_trial_active/paper_needs_attention above). EquitiesLedgerUnreadable guards this case.
    _gauge(lines, "paper_ledger_readable",
           "1 if this scrape's read-only open of --ledger succeeded; 0 if the ledger file is "
           "missing or the open/read failed. Always exported regardless of ledger state.",
           [("", 1 if conn is not None else 0)])

    if conn is not None:
        try:
            meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta")}
            limits = {}
            if "limits" in meta:
                try:
                    limits = json.loads(meta["limits"])
                except json.JSONDecodeError:
                    limits = {}

            halted = meta.get("halted_reason")
            if halted:
                _gauge(lines, "paper_ledger_frozen",
                       "1 for the ledger's current persisted halted_reason; no series while not frozen.",
                       [(f'{{reason="{_escape_label(halted)}"}}', 1)])

            divergence = 0
            for row in conn.execute("SELECT payload FROM events WHERE kind='risk_halt'"):
                try:
                    payload = json.loads(row["payload"])
                except json.JSONDecodeError:
                    continue
                if payload.get("reason") == "external_order_detected":
                    divergence += 1
            _counter(lines, "paper_order_state_divergence_total",
                     "Count of ledger risk_halt events recorded with reason=external_order_detected "
                     "(a broker order absent from the ledger). Other reconcile mismatch types are not "
                     "durably recorded in the ledger; see the module docstring gap note.", divergence)

            window_start = now - WINDOW_SECONDS
            rows = conn.execute("SELECT at, kind FROM requests WHERE at > ?", (window_start,)).fetchall()
            rest_limit = limits.get("max_rest_per_minute")
            submit_limit = limits.get("max_submits_per_minute")
            limit_samples, remaining_samples = [], []
            if isinstance(rest_limit, int):
                limit_samples.append(('{kind="rest"}', rest_limit))
                remaining_samples.append(('{kind="rest"}', max(0, rest_limit - len(rows))))
            if isinstance(submit_limit, int):
                submit_count = sum(1 for r in rows if r["kind"] == "submit")
                limit_samples.append(('{kind="submit"}', submit_limit))
                remaining_samples.append(('{kind="submit"}', max(0, submit_limit - submit_count)))
            if limit_samples:
                _gauge(lines, "paper_request_budget_limit",
                       "Rolling one-minute request budget limit from persisted RiskLimits, by kind.",
                       limit_samples)
                _gauge(lines, "paper_request_budget_remaining",
                       "Rolling one-minute request budget remaining, recomputed read-only from the "
                       "requests table, by kind.", remaining_samples)
        finally:
            conn.close()

    lines.append(GAP_COMMENT.rstrip("\n"))
    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    ledger_path: Path
    trial_path: Path

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass  # A local read-only exporter does not need per-request access logs.

    def do_GET(self):
        if self.path.split("?", 1)[0] not in ("/metrics", "/metrics/"):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        try:
            body = render_metrics(self.ledger_path, self.trial_path).encode("utf-8")
            status = 200
        except Exception as exc:  # never crash the process on an unreadable ledger
            body = f"# adaptive-paper-metrics error: {_escape_label(str(exc))}\n".encode("utf-8")
            status = 500
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_server(ledger_path: Path, trial_path: Path, *, host: str = HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    handler = type("BoundMetricsHandler", (MetricsHandler,), {"ledger_path": ledger_path, "trial_path": trial_path})
    return ThreadingHTTPServer((host, port), handler)


def _file_sd_groups(path: Path) -> list:
    """The target groups in the file_sd list at ``path`` ([] when it does not exist yet). Anything that is not a
    JSON list of ``{"targets": [str, ...], "labels": {...}}`` groups raises ValueError instead of being replaced."""
    try:
        groups = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} is not JSON: {exc}") from None
    if not isinstance(groups, list) or not all(
            isinstance(group, dict) and set(group) <= {"targets", "labels"} and isinstance(group.get("targets"), list)
            and all(isinstance(target, str) for target in group["targets"])
            and isinstance(group.get("labels", {}), dict) for group in groups):
        raise ValueError(f"{path.name} is not a file_sd target list")
    return groups


def update_file_sd(path: Path, target: str, *, registered: bool) -> None:
    """Add (``registered``) or remove this exporter's own single-target group in the file_sd list at ``path``.

    Groups written by anyone else are kept as they are. A sibling lock file serialises concurrent exporters, and
    the new list is written to a temporary file in the same directory, flushed to disk and ``os.replace``-d over
    the old one, so Prometheus, which re-reads the file on every change, never reads a partial list.
    """
    with open(path.with_name(path.name + ".lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        groups = [group for group in _file_sd_groups(path) if group["targets"] != [target]]
        if registered:
            groups.append({"targets": [target], "labels": {}})
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            with open(temporary, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(groups, indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise


def trial_finished(trial_path: Path) -> bool:
    """True when nothing is left to watch: no trial.json (no trial ran on this ledger) or phase ``finished``
    without a failed status. `runner.trial_phase_and_exit_code` records ``finished`` only for a passing status
    that ended flat; a ``finished`` phase carrying ``needs_attention`` or ``failed`` (the recovered-flat case
    ``EquitiesReconciliationFailed`` also covers) is still not clean. ``starting``, ``needs_attention``,
    ``held_overnight`` and an unreadable file keep the exporter registered."""
    try:
        metadata = json.loads(trial_path.read_text())
    except FileNotFoundError:
        return True
    except (OSError, json.JSONDecodeError):
        return False
    return (isinstance(metadata, dict) and metadata.get("phase") == "finished"
            and metadata.get("status") not in ("needs_attention", "failed"))


class _CleanStop(Exception):
    """Raised by the SIGTERM handler so serve_forever() returns through the clean-stop path, as SIGINT does."""


def _raise_clean_stop(signum, frame):
    raise _CleanStop()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Loopback-only listen port (default {DEFAULT_PORT}; 0 picks a free one); host is "
                             "always 127.0.0.1.")
    parser.add_argument("--ledger", type=Path,
                        help="Path to the adaptive-paper ledger.sqlite3 file, opened strictly read-only. Required "
                             "unless --deregister.")
    parser.add_argument("--trial-json", type=Path, default=None,
                        help="Path to the sibling trial.json metadata file; defaults to <ledger dir>/trial.json.")
    parser.add_argument("--file-sd", type=Path, default=None,
                        help="Prometheus file_sd target list to register this exporter in (the rendered "
                             "<config-root>/adaptive-paper-targets.json). Without it the exporter is not scraped.")
    parser.add_argument("--deregister", action="store_true",
                        help="Remove 127.0.0.1:--port from --file-sd and exit: after an operator has recovered a "
                             "trial whose exporter stopped while registered.")
    args = parser.parse_args(argv)
    if args.deregister:
        if args.file_sd is None:
            parser.error("--deregister needs --file-sd")
        update_file_sd(args.file_sd, f"{HOST}:{args.port}", registered=False)
        print(f"adaptive-paper metrics exporter {HOST}:{args.port} deregistered from {args.file_sd}", file=sys.stderr)
        return 0
    if args.ledger is None:
        parser.error("--ledger is required")
    trial_path = args.trial_json or (args.ledger.parent / "trial.json")
    server = make_server(args.ledger, trial_path, port=args.port)
    target = f"{HOST}:{server.server_address[1]}"
    # Installed before registering, so a SIGTERM at any point after the target is written takes the clean-stop path.
    signal.signal(signal.SIGTERM, _raise_clean_stop)
    clean_stop = False
    try:
        if args.file_sd is not None:
            try:
                update_file_sd(args.file_sd, target, registered=True)
            except (OSError, ValueError) as exc:
                print(f"adaptive-paper metrics exporter refused: cannot register {target} in {args.file_sd}: {exc}",
                      file=sys.stderr)
                return 2
        print(f"adaptive-paper metrics exporter listening on http://{target}/metrics "
              f"(read-only; ledger={args.ledger}; file_sd={args.file_sd})", file=sys.stderr)
        server.serve_forever()
    except (KeyboardInterrupt, _CleanStop):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)  # a repeated SIGTERM must not cut the clean stop short
        clean_stop = True
    finally:
        server.server_close()
    # Only a clean stop of a finished trial deregisters; a crash propagates above and skips this entirely.
    if clean_stop and args.file_sd is not None:
        if trial_finished(trial_path):
            update_file_sd(args.file_sd, target, registered=False)
            print(f"adaptive-paper metrics exporter {target} deregistered", file=sys.stderr)
        else:
            print(f"adaptive-paper metrics exporter {target} stays registered: the trial has not finished",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
