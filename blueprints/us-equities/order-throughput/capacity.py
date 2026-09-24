"""Paper-only execution-capacity qualification for Alpaca order actions.

This harness measures how many order actions (REST submits and cancels) one
paper account sustains per 60 seconds under the broker's rate limit, with
every order's state observed on the ``trade_updates`` websocket. It is an
execution-capacity measurement, never strategy performance: its orders are
non-marketable 1-share limit BUY probes priced well below the bid and
cancelled individually, and they must never be counted as strategy trades.

The adaptive-paper engine is reused read-only: paper endpoint pins, the
guarded HTTP session (no retries, no redirects, no cancel-all path), the
``trade_updates`` stream class, credential loading, atomic receipt writes,
the host STOP kill switch and the account-writer lock. See README.md.
"""
from __future__ import annotations

import argparse
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal, InvalidOperation
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import queue
import re
import secrets
import shlex
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ADAPTIVE = HERE.parent / "adaptive-paper"
for _path in (str(HERE), str(ADAPTIVE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from rate_governor import GovernorError, RateGovernor  # noqa: E402
from safety import DEFAULT_STOP  # noqa: E402
from sessions import SessionKind, session_at  # noqa: E402
from transport import PAPER_URL, TERMINAL  # noqa: E402

HARNESS_VERSION = "order-throughput/1"
POLICY_STATEMENT = (
    "Execution-capacity qualification only. Harness orders are non-marketable probes that are "
    "cancelled individually; they are not strategy trades and must never be counted as strategy "
    "trades, fills, signals or performance.")
ACK_EVENTS = frozenset({"pending_new", "new", "accepted"})
ACK_STATUSES = frozenset({"pending_new", "new", "accepted", "accepted_for_bidding", "held"})
FILL_EVENTS = frozenset({"fill", "partial_fill"})
TERMINAL_EVENTS = frozenset({"fill", "canceled", "expired", "rejected", "replaced"})
LIVE_STATES = frozenset({"submitting", "accepted", "accepted_by_stream", "ambiguous"})
PREFIX = re.compile(r"cap-[0-9]{8}t[0-9]{6}-[0-9a-f]{6}-\Z")
SYMBOL = re.compile(r"[A-Z][A-Z0-9.\-]{0,14}\Z")
CENT = Decimal("0.01")
MAX_CANCEL_ATTEMPTS = 3
# Cleanup may outlast cleanup_timeout_seconds by this many governor max_backoff
# periods, so a 429 near or during cleanup cannot consume the whole window.
CLEANUP_BACKOFF_PERIODS = 3
CLEANUP_VERIFY_ROUNDS = 3
RECONCILE_SECONDS = 30.0
SESSION_MARGIN_SECONDS = 30.0
# Frozen qualification criteria (README "Acceptance criteria"). Configurable
# values below these stay exploratory: acceptance.passed is then false.
FROZEN_REQUIRED_WINDOWS = 5
FROZEN_TARGET_ACTIONS_RATIO = 0.85
PATH_OPTIONS = frozenset({"--env-file", "--output", "--journal", "--adaptive-state-root", "--stop-file"})
SOURCE_FILES = ("capacity.py", "rate_governor.py", "alpaca_capacity_port.py", "capacity_fixture.py")
ADAPTIVE_SOURCE_FILES = ("transport.py", "safety.py", "sessions.py", "runner.py")


class HarnessRefusal(RuntimeError):
    """Refused before any order could be sent; bounded reason code."""


def _positive_decimal(value, name):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise HarnessRefusal("invalid_" + name) from None
    if not number.is_finite() or number <= 0:
        raise HarnessRefusal("invalid_" + name)
    return number


@dataclass
class CapacityConfig:
    symbol: str = "SPY"
    qty: int = 1
    band_bps: int = 500
    configured_cap_per_minute: int = 200
    headroom: float = 0.9
    burst: int | None = None
    max_orders: int = 600
    max_duration_seconds: float = 330.0
    max_open_orders: int = 10
    max_order_notional_usd: str = "1000"
    max_open_notional_usd: str = "10000"
    max_http_429: int = 5
    max_consecutive_rejections: int = 10
    inflight: int = 4
    stream_timeout_seconds: float = 10.0
    stream_start_timeout_seconds: float = 15.0
    cleanup_timeout_seconds: float = 60.0
    requote_seconds: float = 60.0
    allow_extended_hours: bool = True
    allow_cancel_all: bool = False
    acknowledged_positions: int = 0
    acknowledged_open_orders: int = 0
    target_actions_ratio: float = 0.85
    required_windows: int = 5
    base_url: str = PAPER_URL

    def validate(self):
        if self.base_url != PAPER_URL:
            raise HarnessRefusal("non_paper_base_url")
        if not isinstance(self.symbol, str) or not SYMBOL.fullmatch(self.symbol):
            raise HarnessRefusal("invalid_symbol")
        bounds = {"qty": (1, 10), "band_bps": (100, 5000), "configured_cap_per_minute": (1, 2000),
                  "max_orders": (1, 20000), "max_open_orders": (1, 100), "max_http_429": (0, 100),
                  "max_consecutive_rejections": (1, 1000), "inflight": (1, 16),
                  "acknowledged_positions": (0, 1000), "acknowledged_open_orders": (0, 1000),
                  "required_windows": (1, 60)}
        for name, (low, high) in bounds.items():
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise HarnessRefusal(name + "_out_of_bounds")
        floats = {"headroom": (0.1, 1.0), "max_duration_seconds": (1.0, 3600.0),
                  "stream_timeout_seconds": (0.5, 120.0), "stream_start_timeout_seconds": (1.0, 120.0),
                  "cleanup_timeout_seconds": (5.0, 900.0), "requote_seconds": (5.0, 3600.0),
                  "target_actions_ratio": (0.1, 1.0)}
        for name, (low, high) in floats.items():
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise HarnessRefusal(name + "_out_of_bounds")
        if self.burst is not None and (type(self.burst) is not int or not 1 <= self.burst <= 200):
            raise HarnessRefusal("burst_out_of_bounds")
        for name in ("allow_extended_hours", "allow_cancel_all"):
            if type(getattr(self, name)) is not bool:
                raise HarnessRefusal(name + "_must_be_boolean")
        order_cap = _positive_decimal(self.max_order_notional_usd, "max_order_notional_usd")
        open_cap = _positive_decimal(self.max_open_notional_usd, "max_open_notional_usd")
        if order_cap > Decimal("10000") or open_cap > Decimal("100000") or order_cap > open_cap:
            raise HarnessRefusal("notional_cap_out_of_bounds")

    def public(self):
        return asdict(self)


@dataclass
class Response:
    """One REST outcome. Ports return this for HTTP outcomes and never raise for them."""
    status: int | None
    headers: dict = field(default_factory=dict)
    order: dict | None = None
    error: str | None = None
    not_sent: bool = False
    origin: str = "trading"


@dataclass
class Probe:
    client_order_id: str
    seq: int
    limit_price: str
    qty: int
    extended_hours: bool
    state: str = "submitting"
    order_id: str | None = None
    sent_at: float | None = None
    rest_at: float | None = None
    rest_status: int | None = None
    stream_ack_at: float | None = None
    terminal_at: float | None = None
    terminal_status: str | None = None
    events: list = field(default_factory=list)
    cancel_state: str | None = None
    cancel_attempts: int = 0
    cancel_done_at: float | None = None
    cancel_statuses: list = field(default_factory=list)
    filled_qty: str = "0"

    @property
    def terminal(self):
        return self.terminal_status is not None

    @property
    def notional(self):
        return Decimal(self.limit_price) * self.qty


class SystemClock:
    monotonic = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)
    time = staticmethod(time.time)


class InlineExecutor:
    """Runs each call immediately; used with offline ports and a fake clock."""

    def submit(self, fn, *args):
        future = Future()
        try:
            future.set_result(fn(*args))
        except Exception as exc:  # surfaced by the coordinator
            future.set_exception(exc)
        return future

    def shutdown(self, wait=True):
        return None


def percentile(values, pct):
    """Nearest-rank percentile; None for an empty sample."""
    ordered = sorted(values)
    if not ordered:
        return None
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[rank - 1]


def _latency_summary(seconds):
    millis = [value * 1000.0 for value in seconds]
    result = {"count": len(millis)}
    for pct in (50, 95, 99):
        value = percentile(millis, pct)
        result["p%d_ms" % pct] = None if value is None else round(value, 3)
    result["max_ms"] = round(max(millis), 3) if millis else None
    return result


def limit_price_below_bid(bid, band_bps):
    try:
        bid = Decimal(str(bid))
    except (InvalidOperation, ValueError):
        raise HarnessRefusal("quote_unavailable") from None
    if not bid.is_finite() or bid <= 0:
        raise HarnessRefusal("quote_unavailable")
    price = (bid * (Decimal(10000) - Decimal(band_bps)) / Decimal(10000)).quantize(CENT, rounding=ROUND_DOWN)
    if price < Decimal("1.00") or price >= bid:
        raise HarnessRefusal("probe_price_unusable")
    return price


def cancel_all_guard(open_orders, complete, prefix, *, preflight_open_orders):
    """DELETE /v2/orders cancels every open order on the shared account. It is
    permitted only when the preflight saw no open order at all (so none can
    predate this run) and a fresh, complete listing shows that every open order
    carries this run's client_order_id prefix."""
    if preflight_open_orders:
        return False, "preflight_found_open_orders_not_created_by_this_run"
    if not complete:
        return False, "open_order_listing_incomplete"
    if any(not str(order.get("client_order_id") or "").startswith(prefix) for order in open_orders):
        return False, "foreign_open_orders_present"
    return True, "only_this_runs_orders_open"


def new_prefix(now_wall):
    stamp = datetime.fromtimestamp(now_wall, timezone.utc).strftime("%Y%m%dt%H%M%S")
    return "cap-%s-%s-" % (stamp, secrets.token_hex(3))


def env_base_url(path):
    """Return APCA_API_BASE_URL from the env file if present (else None).

    Call only after adaptive-paper ``runner.credentials`` accepted the file's
    ownership, mode and location. Only this one key is read here."""
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.removeprefix("export ").split("=", 1)
        if name.strip() == "APCA_API_BASE_URL":
            values = shlex.split(value, comments=True)
            return values[0] if len(values) == 1 else ""
    return None


class Journal:
    """Append-only JSONL run journal (0600, created exclusively, no secrets).

    The start record, which carries the ``client_order_id`` prefix, is fsynced
    before the stream starts and before any order is sent, so a run killed by
    SIGKILL, OOM or power loss can still be found and cancelled with
    ``capacity.py recover``. Each probe intent is written and flushed before
    its POST (it survives process death; the prefix alone suffices for
    recovery). The end record is fsynced."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            raise HarnessRefusal("journal_exists") from None
        except OSError:
            raise HarnessRefusal("journal_unavailable") from None
        self._stream = os.fdopen(fd, "a")

    def write(self, record, sync=False):
        self._stream.write(json.dumps(record, sort_keys=True) + "\n")
        self._stream.flush()
        if sync:
            os.fsync(self._stream.fileno())

    def close(self):
        try:
            self._stream.flush()
            os.fsync(self._stream.fileno())
        finally:
            self._stream.close()


def read_journal(path):
    """Parse a run journal; a torn final line (crash mid-write) is ignored."""
    try:
        lines = Path(path).read_text().splitlines()
    except OSError:
        raise HarnessRefusal("journal_unreadable") from None
    start, intents, end = None, [], None
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        if record.get("type") == "start" and start is None:
            start = record
        elif record.get("type") == "intent":
            intents.append(record)
        elif record.get("type") == "end":
            end = record
    if start is None or not PREFIX.fullmatch(str(start.get("prefix") or "")):
        raise HarnessRefusal("journal_has_no_start_record")
    return {"start": start, "intents": intents, "end": end}


def sanitize_argv(argv):
    """Keep the argument vector but replace private path values."""
    result, redact_next = [], False
    for item in argv or []:
        item = str(item)
        if redact_next:
            result.append("<path>")
            redact_next = False
        elif item in PATH_OPTIONS:
            result.append(item)
            redact_next = True
        elif "=" in item and item.split("=", 1)[0] in PATH_OPTIONS:
            result.append(item.split("=", 1)[0] + "=<path>")
        else:
            result.append(item)
    return result


def _sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def source_provenance():
    """Harness source identity for the receipt: file hashes, git revision, SDK version."""
    try:
        done = subprocess.run(["git", "-C", str(HERE), "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=5, check=False)
        revision = done.stdout.strip() if done.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        revision = None
    try:
        sdk = importlib.metadata.version("alpaca-py")
    except importlib.metadata.PackageNotFoundError:
        sdk = None
    files = {"order-throughput/" + name: _sha256(HERE / name) for name in SOURCE_FILES}
    files.update({"adaptive-paper/" + name: _sha256(ADAPTIVE / name) for name in ADAPTIVE_SOURCE_FILES})
    return {"git_revision": revision, "source_sha256": files, "alpaca_py_version": sdk,
            "python_version": platform.python_version()}


class CapacityRun:
    """One bounded capacity run against a broker port.

    Port contract (capacity_fixture.FakeBroker and alpaca_capacity_port):
    ``evidence_class``; ``supports_cancel_all``; ``preflight()`` -> dict;
    ``submit(client_order_id, symbol, qty, limit_price, extended_hours)``,
    ``cancel(order_id)`` and ``cancel_all()`` -> Response;
    ``list_orders(status, after_wall, admit)`` -> (orders, complete, [Response]),
    where ``admit()`` must return True before each page after the first;
    ``positions()`` -> (positions, [Response]); ``latest_quote()`` -> dict;
    ``start_stream(callback, timeout)``, ``stream_health()`` and ``stop_stream()``.
    """

    def __init__(self, port, config, *, clock=None, executor=None, stop_file=None,
                 account_scope=None, prefix=None, journal_path=None, argv=None):
        self.port = port
        self.config = config
        self.clock = clock or SystemClock()
        self.executor = executor
        self.stop_file = Path(stop_file) if stop_file is not None else DEFAULT_STOP
        self.account_scope = account_scope or (lambda fingerprint: nullcontext())
        self.prefix = prefix
        self.journal_path = None if journal_path is None else Path(journal_path)
        self.journal = None
        self.argv = sanitize_argv(argv)
        self.exit_code = None
        self.mode = "run"
        self.governor = None
        self.probes = {}
        self._live = {}
        self._events = queue.Queue()
        self._inflight = {}
        self._quote_future = None
        self._cancel_queue = []
        self._stop_reason = None
        self._health = set()
        self._stream_started = False
        self._broker_seen = set()
        self.port_errors = 0
        self.actions = []
        self.responses = []
        self.stream_stats = {"events_total": 0, "events_this_run": 0, "foreign_events_ignored": 0,
                             "unknown_harness_events": 0, "malformed_events": 0}
        self.rejections = {}
        self.consecutive_rejections = 0
        self.unexpected_fill_qty = Decimal(0)
        self.preflight_summary = {}
        self.t0 = None
        self.submit_phase_end = None
        self.started_wall = None
        self.limit_price = None
        self.extended_hours = False
        self.session_kind = None
        self.quote_at = None
        self.cleanup = {}
        self.reconciliation = {}
        self.error_type = None
        self.status = None
        self.stage = None
        self.refusal = None
        self._preflight_open_orders = 0
        self._preflight_positions = {}
        self.receipt = {}

    # -- external control ------------------------------------------------------
    def request_stop(self, reason="signal"):
        if self._stop_reason is None:
            self._stop_reason = str(reason)

    def _freeze(self, reason):
        self._health.add(str(reason))

    def _stop_present(self):
        return self.stop_file.exists()

    # -- probe bookkeeping ------------------------------------------------------
    def _settle(self, probe):
        if probe.terminal or probe.state not in LIVE_STATES:
            self._live.pop(probe.client_order_id, None)

    def _open_probes(self):
        return list(self._live.values())

    def _open_notional(self):
        return sum((p.notional for p in self._live.values()), Decimal(0))

    # -- stream -----------------------------------------------------------------
    def _on_stream(self, raw):
        """Called on the stream thread (or inline by a fake); stamps receipt time and enqueues."""
        self._events.put((self.clock.monotonic(), raw))

    def _drain_events(self):
        while True:
            try:
                at, raw = self._events.get_nowait()
            except queue.Empty:
                return
            self._handle_event(raw, at)

    def _handle_event(self, raw, at=None):
        self.stream_stats["events_total"] += 1
        try:
            payload = raw.get("data", raw)
            order = payload["order"]
            cid = str(order.get("client_order_id") or "")
            event = str(payload.get("event") or "")
            status = str(order.get("status") or "")
            order_id = str(order.get("id") or "")
            filled = Decimal(str(order.get("filled_qty") or "0"))
            if not filled.is_finite() or filled < 0:
                raise ValueError
        except (AttributeError, KeyError, TypeError, ValueError, InvalidOperation):
            self.stream_stats["malformed_events"] += 1
            return
        if not self.prefix or not cid.startswith(self.prefix):
            self.stream_stats["foreign_events_ignored"] += 1
            return
        self.stream_stats["events_this_run"] += 1
        probe = self.probes.get(cid)
        if probe is None:
            self.stream_stats["unknown_harness_events"] += 1
            self._freeze("unknown_harness_order")
            return
        now = self.clock.monotonic() if at is None else at
        probe.events.append(event or status)
        if order_id:
            if probe.order_id and probe.order_id != order_id:
                self._freeze("client_id_collision")
            probe.order_id = probe.order_id or order_id
        if probe.state == "ambiguous":
            probe.state = "accepted_by_stream"
            self._live[cid] = probe
        if probe.stream_ack_at is None and (event in ACK_EVENTS or (not event and status in ACK_STATUSES)):
            probe.stream_ack_at = now
        if event in FILL_EVENTS or filled > 0:
            if filled > Decimal(probe.filled_qty):
                self.unexpected_fill_qty += filled - Decimal(probe.filled_qty)
                probe.filled_qty = str(filled)
            self._freeze("unexpected_fill")
        if status in TERMINAL or event in TERMINAL_EVENTS:
            if probe.terminal_status is None:
                probe.terminal_status = status if status in TERMINAL else ("filled" if event == "fill" else event)
                probe.terminal_at = now
            self._settle(probe)
            return
        if probe.stream_ack_at is not None:
            self._schedule_cancel(probe)

    def _schedule_cancel(self, probe):
        if (probe.terminal or probe.order_id is None or probe.cancel_attempts >= MAX_CANCEL_ATTEMPTS
                or probe.cancel_state in ("queued", "sent", "acknowledged")):
            return
        probe.cancel_state = "queued"
        self._cancel_queue.append(probe.client_order_id)

    # -- REST -------------------------------------------------------------------
    def _record(self, kind, response, phase):
        self.responses.append({"kind": kind, "status": response.status, "origin": response.origin,
                               "headers": dict(response.headers or {}), "phase": phase})
        if response.origin == "trading" and not response.not_sent:
            self.governor.on_response(kind, response.status, response.headers, inflight=len(self._inflight))

    def _timed(self, fn, *args):
        """Runs on a REST worker: the completion time is stamped there, not at collection."""
        result = fn(*args)
        return result, self.clock.monotonic()

    def _port_error(self, exc):
        """A port defect (an exception rather than a Response). The first one fails
        the run and freezes submissions; cleanup and reconciliation still run."""
        self.port_errors += 1
        self.error_type = self.error_type or type(exc).__name__
        self._freeze("port_exception")

    @staticmethod
    def _ok(response):
        status = getattr(response, "status", None)
        return not getattr(response, "not_sent", True) and status is not None and 200 <= status < 300

    def _dispatch(self, kind, fn, *args, key):
        action = {"t": self.clock.monotonic(), "kind": kind, "ok": None}
        self.actions.append(action)
        future = self.executor.submit(self._timed, fn, *args)
        self._inflight[future] = (kind, key, action)

    def _collect(self):
        """Handle every finished REST call. Never raises: a failed future is recorded."""
        for future in [future for future in self._inflight if future.done()]:
            kind, key, action = self._inflight.pop(future)
            probe = self.probes[key]
            try:
                response, done_at = future.result()
            except Exception as exc:
                action["ok"] = False
                self._port_error(exc)
                if kind == "submit":
                    # The order may exist; the prefix sweep and reconciliation resolve it.
                    probe.rest_status = None
                    probe.state = "accepted_by_stream" if probe.events else "ambiguous"
                    self.rejections["port_exception"] = self.rejections.get("port_exception", 0) + 1
                    self._settle(probe)
                else:
                    probe.cancel_statuses.append(None)
                    probe.cancel_state = None
                    if not probe.terminal:
                        self._schedule_cancel(probe)
                continue
            action["ok"] = self._ok(response)
            self._record(kind, response, "run")
            if kind == "submit":
                self._on_submit(probe, response, done_at)
            else:
                self._on_cancel(probe, response, done_at)

    def _on_submit(self, probe, response, done_at=None):
        probe.rest_status = response.status
        if response.not_sent:
            probe.state = "not_sent"
            self.rejections["not_sent"] = self.rejections.get("not_sent", 0) + 1
        elif response.status is not None and 200 <= response.status < 300 and response.order:
            probe.state = "accepted"
            probe.rest_at = self.clock.monotonic() if done_at is None else done_at
            order_id = str(response.order.get("id") or "")
            if order_id:
                if probe.order_id and probe.order_id != order_id:
                    self._freeze("client_id_collision")
                probe.order_id = probe.order_id or order_id
            self.consecutive_rejections = 0
            if probe.stream_ack_at is not None and not probe.terminal:
                self._schedule_cancel(probe)
        elif response.status == 429 or response.status is None or response.status >= 500:
            # The order may exist. Never resubmit: the stream or the final
            # reconciliation resolves it, and cleanup cancels it if it exists.
            probe.state = "accepted_by_stream" if probe.events else "ambiguous"
            label = "http_429" if response.status == 429 else "ambiguous_%s" % (response.status or "no_response")
            self.rejections[label] = self.rejections.get(label, 0) + 1
        else:
            probe.state = "rejected"
            label = "http_%d" % response.status
            self.rejections[label] = self.rejections.get(label, 0) + 1
            self.consecutive_rejections += 1
        self._settle(probe)

    def _on_cancel(self, probe, response, done_at=None):
        done_at = self.clock.monotonic() if done_at is None else done_at
        probe.cancel_statuses.append(response.status)
        if response.status is not None and 200 <= response.status < 300:
            probe.cancel_state = "acknowledged"
            probe.cancel_done_at = done_at
        elif response.status == 429 or response.status is None or response.status >= 500:
            probe.cancel_state = None  # retried once the governor's backoff ends
            if not probe.terminal:
                self._schedule_cancel(probe)
        else:
            # 404/422: typically already terminal; the stream and reconciliation decide.
            probe.cancel_state = "refused_%d" % response.status
            probe.cancel_done_at = done_at

    @staticmethod
    def _due(deadline):
        return deadline() if callable(deadline) else deadline

    def _governed(self, kind, deadline):
        """Wait for one admission until ``deadline`` (a value or a callable re-read each pass)."""
        while self.clock.monotonic() < self._due(deadline):
            if self.governor.try_acquire(kind):
                return True
            self.clock.sleep(max(0.001, min(0.25, self.governor.wait_hint())))
        return False

    def _sync(self, kind, deadline, fn, *args, phase):
        """One governed synchronous call (cleanup/reconciliation). None if no budget or a port defect."""
        if not self._governed("cancel" if kind in ("cancel", "cancel_all") else kind, deadline):
            return None
        action = {"t": self.clock.monotonic(), "kind": kind, "ok": None}
        self.actions.append(action)
        try:
            result = fn(*args)
        except Exception as exc:
            action["ok"] = False
            self._port_error(exc)
            return None
        # Listings and positions return tuples ending in their responses; cancels return one.
        responses = list(result[-1]) if isinstance(result, tuple) else [result]
        action["ok"] = bool(responses) and self._ok(responses[0])
        for response in responses:
            self._record("read" if kind == "read" else "cancel", response, phase)
        return result

    def _list(self, status, after_wall, deadline, phase):
        """A governed, paged order listing: every page is admitted by the governor."""
        pages = {"admitted": 0}

        def admit():
            if not self._governed("read", deadline):
                return False
            pages["admitted"] += 1
            self.actions.append({"t": self.clock.monotonic(), "kind": "read", "ok": True})
            return True

        result = self._sync("read", deadline, self.port.list_orders, status, after_wall, admit, phase=phase)
        if result is None:
            return None
        # A port that ignored ``admit`` sent unadmitted pages; count them in the window.
        extra = len(result[-1]) - 1 - pages["admitted"]
        if extra > 0:
            self.governor.note_external_calls(extra)
        return result

    # -- phases -----------------------------------------------------------------
    def _preflight(self):
        pre = self.port.preflight()
        limits = self._governor_from(pre)
        observations = pre.get("observations", [])
        positions = [p for p in pre.get("positions", []) if Decimal(str(p.get("qty", "0"))) != 0]
        open_orders = list(pre.get("open_orders", []))
        self._preflight_open_orders = len(open_orders)
        self._preflight_positions = {p["symbol"]: str(p["qty"]) for p in positions}
        self.preflight_summary = {
            "trading_limit_header": limits[-1],
            "trading_limit_headers_seen": sorted(set(limits)),
            "data_limit_headers_seen": sorted({str((o.get("headers") or {}).get("x-ratelimit-limit"))
                                               for o in observations if o.get("origin") == "data"
                                               and (o.get("headers") or {}).get("x-ratelimit-limit")}),
            "positions": len(positions), "open_orders": len(open_orders),
            "open_orders_complete": bool(pre.get("open_orders_complete")),
            "acknowledged_positions": self.config.acknowledged_positions,
            "acknowledged_open_orders": self.config.acknowledged_open_orders,
            "asset_tradable": pre.get("asset_tradable")}
        if not pre.get("open_orders_complete"):
            raise HarnessRefusal("open_order_listing_incomplete")
        if len(positions) != self.config.acknowledged_positions:
            raise HarnessRefusal("unacknowledged_positions")
        if len(open_orders) != self.config.acknowledged_open_orders:
            raise HarnessRefusal("unacknowledged_open_orders")
        if pre.get("asset_tradable") is not True:
            raise HarnessRefusal("asset_not_tradable")
        return pre

    def _governor_from(self, pre):
        """Size the RateGovernor from the preflight's trading-origin headers."""
        observations = pre.get("observations", [])
        trading = [o for o in observations if o.get("origin") == "trading"]
        limits = [int(str(o["headers"]["x-ratelimit-limit"])) for o in trading
                  if str((o.get("headers") or {}).get("x-ratelimit-limit", "")).isdigit()]
        self.responses.extend({"kind": o.get("kind", "read"), "status": o.get("status"),
                               "origin": o.get("origin"), "headers": dict(o.get("headers") or {}),
                               "phase": "preflight"} for o in observations)
        if not limits:
            raise HarnessRefusal("trading_rate_limit_header_unobserved")
        self.governor = RateGovernor(self.config.configured_cap_per_minute, headroom=self.config.headroom,
                                     burst=self.config.burst, clock=self.clock.monotonic, wall=self.clock.time)
        # The market-data origin reports its own, unrelated limit; only trading headers count.
        self.governor.observe_limit(limits[-1])
        self.governor.note_external_calls(len(trading))
        last = trading[-1].get("headers") or {}
        self.governor.on_response("read", trading[-1].get("status"), last)
        return limits

    def cleanup_ceiling_seconds(self):
        """Hard bound on cleanup: the timeout plus room for a few governor backoffs."""
        max_backoff = self.governor.max_backoff if self.governor else 60.0
        return self.config.cleanup_timeout_seconds + CLEANUP_BACKOFF_PERIODS * max_backoff

    def post_loop_reserve_seconds(self):
        """Everything that can run after the submission deadline, plus stream start before t0."""
        return (self.config.stream_start_timeout_seconds + self.cleanup_ceiling_seconds()
                + RECONCILE_SECONDS + SESSION_MARGIN_SECONDS)

    def _session(self):
        now = datetime.fromtimestamp(self.clock.time(), timezone.utc)
        try:
            info = session_at(now)
        except ValueError:
            raise HarnessRefusal("session_calendar_unsupported") from None
        self.session_kind = info.kind.value
        if info.kind == SessionKind.CLOSED:
            raise HarnessRefusal("market_session_closed")
        if info.kind in (SessionKind.PRE, SessionKind.POST):
            if not self.config.allow_extended_hours:
                raise HarnessRefusal("extended_hours_not_allowed")
            self.extended_hours = True
        # Finish, including stream start, cleanup (with its backoff allowance) and
        # reconciliation, inside the current session segment.
        remaining = (info.seconds_to_close or 0) - self.post_loop_reserve_seconds()
        if remaining < 60.0:
            raise HarnessRefusal("session_ends_too_soon")
        return min(self.config.max_duration_seconds, remaining)

    def _price(self, quote):
        if not quote or "bid" not in quote:
            raise HarnessRefusal("quote_unavailable")
        price = limit_price_below_bid(quote["bid"], self.config.band_bps)
        if price * self.config.qty > Decimal(self.config.max_order_notional_usd):
            raise HarnessRefusal("order_notional_cap_exceeded")
        self.limit_price = price
        self.quote_at = self.clock.monotonic()

    def _requote(self):
        """Refresh the probe price on a worker so the data call never blocks the main loop."""
        future = self._quote_future
        if future is not None:
            if not future.done():
                return
            self._quote_future = None
            try:
                quote, _ = future.result()
                self._price(quote)
            except HarnessRefusal as exc:
                self._freeze("requote_" + str(exc))
            except Exception:
                self._freeze("requote_failed")
            finally:
                self.quote_at = self.clock.monotonic()
            return
        if self.clock.monotonic() - self.quote_at >= self.config.requote_seconds:
            self._quote_future = self.executor.submit(self._timed, self.port.latest_quote)

    def _stop_condition(self, deadline):
        if self._stop_reason:
            return self._stop_reason
        if self._stop_present():
            return "stop_file_present"
        if self._health:
            return "frozen:" + ",".join(sorted(self._health))
        if self.clock.monotonic() >= deadline:
            return "duration_reached"
        if self.governor.stats["http_429"] > self.config.max_http_429:
            return "http_429_cap_exceeded"
        if self.consecutive_rejections >= self.config.max_consecutive_rejections:
            return "consecutive_rejections"
        if len(self.probes) >= self.config.max_orders and not self._live and not self._inflight:
            return "max_orders_reached"
        if not self.port.stream_health().get("ready", False):
            self._freeze("stream_not_ready")
            return "frozen:stream_not_ready"
        now = self.clock.monotonic()
        timeout = self.config.stream_timeout_seconds
        for probe in self._live.values():
            if probe.stream_ack_at is None and probe.rest_at is not None and now - probe.rest_at > timeout:
                self._freeze("stream_ack_missing")
                return "frozen:stream_ack_missing"
            if probe.cancel_done_at is not None and now - probe.cancel_done_at > timeout:
                self._freeze("stream_terminal_missing")
                return "frozen:stream_terminal_missing"
        return None

    def _may_submit(self):
        if len(self.probes) >= self.config.max_orders or len(self._inflight) >= self.config.inflight:
            return False
        if len(self._live) >= self.config.max_open_orders:
            return False
        return (self._open_notional() + self.limit_price * self.config.qty
                <= Decimal(self.config.max_open_notional_usd))

    def _submit_one(self):
        seq = len(self.probes) + 1
        cid = "%s%06d" % (self.prefix, seq)
        probe = Probe(cid, seq, str(self.limit_price), self.config.qty, self.extended_hours)
        if self.journal is not None:
            # Written (and flushed) before the POST, so a crash leaves a record of the intent.
            self.journal.write({"type": "intent", "seq": seq, "client_order_id": cid,
                                "limit_price": probe.limit_price, "qty": probe.qty,
                                "extended_hours": probe.extended_hours})
        probe.sent_at = self.clock.monotonic()
        self.probes[cid] = self._live[cid] = probe
        self._dispatch("submit", self.port.submit, cid, self.config.symbol, self.config.qty,
                       str(self.limit_price), self.extended_hours, key=cid)

    def _cancel_one(self):
        cid = self._cancel_queue.pop(0)
        probe = self.probes[cid]
        if probe.terminal or probe.order_id is None:
            probe.cancel_state = None
            return False
        probe.cancel_state = "sent"
        probe.cancel_attempts += 1
        self._dispatch("cancel", self.port.cancel, probe.order_id, key=cid)
        return True

    def _loop(self, duration):
        deadline = self.t0 + duration
        while True:
            self._drain_events()
            self._collect()
            self._drain_events()
            reason = self._stop_condition(deadline)
            if reason:
                self._stop_reason = self._stop_reason or reason
                return reason
            self._requote()
            progressed = False
            if self._cancel_queue:
                # Cancels always take priority over new submits.
                if len(self._inflight) < self.config.inflight and self.governor.try_acquire("cancel"):
                    progressed = self._cancel_one()
            elif not self._health and self._may_submit() and self.governor.try_acquire("submit"):
                self._submit_one()
                progressed = True
            if not progressed:
                hint = 0.001 if self._inflight else self.governor.wait_hint()
                self.clock.sleep(max(0.001, min(0.05, hint)))

    def _wait_inflight(self, deadline):
        while self._inflight and self.clock.monotonic() < self._due(deadline):
            self._collect()
            self._drain_events()
            if self._inflight:
                self.clock.sleep(0.005)

    def _list_open(self, deadline, phase):
        result = self._list("open", None, deadline, phase)
        if result is None:
            return None, False
        orders, complete, _ = result
        return orders, complete

    def _cancel_live(self, deadline, result):
        """Cancel every live order with a known broker id, individually, through the governor."""
        last_activity = self.clock.monotonic()
        while self.clock.monotonic() < self._due(deadline):
            self._drain_events()
            self._collect()
            for probe in self._open_probes():
                self._schedule_cancel(probe)
            if (self._cancel_queue and len(self._inflight) < self.config.inflight
                    and self.governor.try_acquire("cancel")):
                if self._cancel_one():
                    result["individual_cancels"] += 1
                    last_activity = self.clock.monotonic()
                continue
            pending = [p for p in self._open_probes() if p.order_id]
            if not pending and not self._inflight and not self._cancel_queue:
                break
            if (not self._cancel_queue and not self._inflight
                    and self.clock.monotonic() - last_activity > self.config.stream_timeout_seconds):
                break
            self.clock.sleep(max(0.001, min(0.05, self.governor.wait_hint())))
        self._wait_inflight(deadline)
        self._drain_events()

    def _adopt(self, cid):
        """Recovery only: a prefix order the journal did not list (intent line lost)."""
        suffix = cid[len(self.prefix):]
        seq = int(suffix) if suffix.isdigit() else 0
        probe = Probe(cid, seq, "0", self.config.qty, False, state="ambiguous")
        self.probes[cid] = self._live[cid] = probe
        return probe

    def _sweep(self, deadline, result):
        """REST sweep: cancel anything with this prefix still open (e.g. ambiguous submits)."""
        orders, _ = self._list_open(deadline, "cleanup_sweep")
        for raw in orders or []:
            cid = str(raw.get("client_order_id") or "")
            if not cid.startswith(self.prefix):
                continue
            probe = self.probes.get(cid)
            if probe is None:
                if self.mode != "recover":
                    self._freeze("unknown_harness_order")
                    continue
                probe = self._adopt(cid)
            probe.order_id = probe.order_id or (str(raw.get("id") or "") or None)
            if probe.order_id is None or probe.terminal:
                continue
            response = self._sync("cancel", deadline, self.port.cancel, probe.order_id, phase="cleanup")
            if response is not None:
                probe.cancel_attempts += 1
                self._on_cancel(probe, response)
                result["rest_sweep_cancels"] += 1

    def _settle_stream(self, deadline):
        settle = min(self._due(deadline), self.clock.monotonic() + min(self.config.stream_timeout_seconds, 5.0))
        while self.clock.monotonic() < settle and [p for p in self._open_probes() if p.order_id]:
            self.clock.sleep(0.05)
            self._drain_events()
        self._drain_events()

    def _cleanup(self):
        """Cancel every order this run created and verify that none remains open.

        The working deadline is ``cleanup_timeout_seconds`` of time outside any
        governor freeze: a 429 backoff extends it, up to the hard ceiling
        ``cleanup_ceiling_seconds()``. An incomplete or non-zero verification
        repeats the sweep and verification, within the same ceiling. A failing
        step is recorded and the next step still runs."""
        start = self.clock.monotonic()
        ceiling = start + self.cleanup_ceiling_seconds()

        def deadline():
            base = start + self.config.cleanup_timeout_seconds
            frozen = self.governor.frozen_until
            if frozen is not None:
                base = max(base, frozen + self.config.cleanup_timeout_seconds)
            return min(ceiling, base)

        result = {"cancel_all_used": False, "cancel_all_decision": "not_enabled",
                  "individual_cancels": 0, "rest_sweep_cancels": 0, "verification_rounds": 0,
                  "ceiling_seconds": round(ceiling - start, 3), "step_errors": []}

        def step(fn, *args):
            try:
                return fn(*args)
            except Exception as exc:  # never abandon the remaining cleanup steps
                result["step_errors"].append(type(exc).__name__)
                self.error_type = self.error_type or type(exc).__name__
                return None

        step(self._wait_inflight, deadline)
        step(self._drain_events)
        # 0) Cancel-all only when enabled AND the guard proves no foreign open order exists.
        if self.config.allow_cancel_all and self._live and self.mode != "recover":
            step(self._cancel_all_guarded, deadline, result)
        # 1) Individual cancels by broker id.
        step(self._cancel_live, deadline, result)
        verified = False
        for _ in range(CLEANUP_VERIFY_ROUNDS):
            result["verification_rounds"] += 1
            round_start = self.clock.monotonic()

            def until(round_start=round_start):
                return min(ceiling, max(deadline(), round_start + RECONCILE_SECONDS))

            # 2) Sweep by prefix, then retry any cancel a 429 deferred.
            step(self._sweep, until, result)
            step(self._cancel_live, until, result)
            # 3) Bounded wait for stream terminal events, then REST verification.
            step(self._settle_stream, until)
            listing = step(self._list_open, until, "cleanup_verification")
            orders, complete = listing if listing is not None else (None, False)
            remaining = [o for o in (orders or []) if str(o.get("client_order_id", "")).startswith(self.prefix)]
            verified = orders is not None and bool(complete) and not remaining
            result.update(open_listing_complete=orders is not None and bool(complete),
                          open_harness_orders_after=None if orders is None else len(remaining))
            if verified or self.clock.monotonic() >= ceiling:
                break
        result.update(verified_zero_open=verified, seconds=round(self.clock.monotonic() - start, 3))
        self.cleanup = result

    def _cancel_all_guarded(self, deadline, result):
        orders, complete = self._list_open(deadline, "cleanup_cancel_all_guard")
        permitted, reason = cancel_all_guard(orders or [], orders is not None and complete, self.prefix,
                                             preflight_open_orders=self._preflight_open_orders)
        if permitted and not getattr(self.port, "supports_cancel_all", False):
            permitted, reason = False, "port_does_not_expose_cancel_all"
        result["cancel_all_decision"] = reason
        if permitted:
            response = self._sync("cancel_all", deadline, self.port.cancel_all, phase="cleanup")
            result["cancel_all_used"] = response is not None
            self._drain_events()

    def _reconcile(self):
        deadline = self.clock.monotonic() + RECONCILE_SECONDS
        listing = self._list("all", self.started_wall - 5.0, deadline, "reconciliation")
        if listing is None:
            self.reconciliation = {"performed": False, "reason": "no_read_budget", "clean": False}
            return
        orders, complete, _ = listing
        ours = {str(o.get("client_order_id") or ""): o for o in orders
                if str(o.get("client_order_id") or "").startswith(self.prefix)}
        # Every probe the broker proves existed must also be covered by the stream.
        self._broker_seen = set(ours) & set(self.probes)
        unknown = sorted(set(ours) - set(self.probes))
        missing, mismatched, non_terminal, filled = [], [], [], []
        ambiguous = {"existed": 0, "not_created": 0, "unresolved": 0}
        for cid, probe in self.probes.items():
            broker = ours.get(cid)
            if probe.state in ("ambiguous", "submitting"):
                ambiguous["existed" if broker is not None else "not_created" if complete else "unresolved"] += 1
            elif probe.state in ("accepted", "accepted_by_stream") and broker is None:
                missing.append(probe.seq)
            if broker is None:
                continue
            status = str(broker.get("status") or "")
            if status not in TERMINAL:
                non_terminal.append(probe.seq)
            elif probe.terminal_status is not None and probe.terminal_status != status:
                mismatched.append({"seq": probe.seq, "stream": probe.terminal_status, "rest": status})
            if Decimal(str(broker.get("filled_qty") or "0")) > 0:
                filled.append(probe.seq)
        positions_after = None
        result = self._sync("read", deadline, self.port.positions, phase="reconciliation")
        if result is not None:
            positions_after = {p["symbol"]: str(p["qty"]) for p in result[0]
                               if Decimal(str(p.get("qty", "0"))) != 0}
        symbol = self.config.symbol
        position_unchanged = (positions_after is not None and Decimal(positions_after.get(symbol, "0"))
                              == Decimal(self._preflight_positions.get(symbol, "0")))
        clean = (bool(complete) and not unknown and not missing and not mismatched and not non_terminal
                 and not filled and ambiguous["unresolved"] == 0 and position_unchanged)
        self.reconciliation = {"performed": True, "listing_complete": bool(complete),
                               "broker_orders_with_prefix": len(ours), "local_probes": len(self.probes),
                               "unknown_prefix_orders": len(unknown), "missing_from_broker": missing,
                               "status_mismatches": mismatched, "non_terminal_at_end": non_terminal,
                               "filled_probes": filled, "ambiguous_submits": ambiguous,
                               "position_unchanged": position_unchanged, "clean": clean}

    # -- entry point ------------------------------------------------------------
    def run(self):
        self.started_wall = self.clock.time()
        self.stage = "config"
        try:
            self.config.validate()
            if self._stop_present():
                raise HarnessRefusal("stop_file_present")
            self.stage = "preflight"
            pre = self._preflight()
            with self.account_scope(pre.get("account_identity_sha256")):
                if self._stop_present():
                    raise HarnessRefusal("stop_file_present")
                duration = self._session()
                self._price(pre.get("quote"))
                self.prefix = self.prefix or new_prefix(self.started_wall)
                if not PREFIX.fullmatch(self.prefix):
                    raise HarnessRefusal("invalid_client_order_id_prefix")
                self._journal_start()
                self.stage = "stream"
                self._stream_started = True
                self.port.start_stream(self._on_stream, self.config.stream_start_timeout_seconds)
                if not self.port.stream_health().get("ready"):
                    raise HarnessRefusal("trade_updates_stream_not_ready")
                if self.executor is None:
                    # One extra worker for the off-loop quote refresh.
                    self.executor = ThreadPoolExecutor(max_workers=self.config.inflight + 1,
                                                       thread_name_prefix="capacity-rest")
                self.stage = "running"
                self.t0 = self.clock.monotonic()
                self.started_wall = self.clock.time()
                try:
                    self._loop(duration)
                finally:
                    # Runs on normal exit, STOP, signal, freeze and exception alike.
                    self.submit_phase_end = self.clock.monotonic()
                    self.stage = "cleanup"
                    try:
                        self._cleanup()
                    except Exception as exc:
                        self.cleanup = dict(self.cleanup, error_type=type(exc).__name__,
                                            verified_zero_open=False)
                    self.stage = "reconciliation"
                    try:
                        self._reconcile()
                    except Exception as exc:
                        self.reconciliation = {"performed": False, "clean": False,
                                               "error_type": type(exc).__name__}
            self.status = "completed"
        except (HarnessRefusal, GovernorError) as exc:
            self.refusal = str(exc)
            self.status = "refused" if not self.probes else "needs_attention"
        except Exception as exc:
            self.error_type = type(exc).__name__
            self.status = "failed"
        finally:
            if self._stream_started:
                try:
                    self.port.stop_stream()
                except Exception:
                    self._freeze("stream_stop_failed")
            if isinstance(self.executor, ThreadPoolExecutor):
                self.executor.shutdown(wait=True)
        if self.status == "completed" and self.error_type is not None:
            self.status = "failed"  # a port defect was recorded while cleanup still ran
        if self.status == "completed" and (not self.cleanup.get("verified_zero_open")
                                           or not self.reconciliation.get("clean")
                                           or self.unexpected_fill_qty > 0):
            self.status = "needs_attention"
        self.receipt = self._build_receipt()
        self._journal_end()
        return self.receipt

    # -- journal and crash recovery ----------------------------------------------
    def _journal_start(self):
        if self.journal_path is None:
            return
        self.journal = Journal(self.journal_path)
        self.journal.write({"type": "start", "harness": HARNESS_VERSION, "prefix": self.prefix,
                            "started_wall": self.started_wall, "symbol": self.config.symbol,
                            "evidence_class": getattr(self.port, "evidence_class", "unknown"),
                            "config": self.config.public()}, sync=True)

    def _journal_end(self):
        if self.journal is None:
            return
        try:
            self.journal.write({"type": "end", "status": self.status,
                                "verified_zero_open": bool(self.cleanup.get("verified_zero_open")),
                                "probes": len(self.probes)}, sync=True)
            self.journal.close()
        except OSError:
            pass
        self.journal = None

    def recover(self, journal_path, *, cancel=True):
        """After a crash: cancel (or, with cancel=False, only list) every order that
        carries the journal's prefix, individually and through the governor, then
        verify zero open. Cancels only; the STOP file does not block it, exactly
        as adaptive-paper keeps cancels allowed under STOP."""
        self.mode = "recover" if cancel else "audit"
        self.stage = "journal"
        record = listing = None
        try:
            record = read_journal(journal_path)
            self.prefix = record["start"]["prefix"]
            self.started_wall = float(record["start"]["started_wall"])
            self.config.validate()
            self.stage = "preflight"
            pre = self.port.preflight()
            self._governor_from(pre)
            with self.account_scope(pre.get("account_identity_sha256")):
                for intent in record["intents"]:
                    cid = str(intent.get("client_order_id") or "")
                    if cid.startswith(self.prefix) and cid not in self.probes:
                        probe = Probe(cid, int(intent.get("seq") or 0), str(intent.get("limit_price") or "0"),
                                      self.config.qty, bool(intent.get("extended_hours")), state="ambiguous")
                        self.probes[cid] = self._live[cid] = probe
                if self.executor is None:
                    self.executor = ThreadPoolExecutor(max_workers=self.config.inflight,
                                                       thread_name_prefix="capacity-recover")
                if cancel:
                    self.stage = "cleanup"
                    self._cleanup()
                self.stage = "listing"
                listing = self._list("all", self.started_wall - 5.0,
                                     self.clock.monotonic() + RECONCILE_SECONDS, "recovery_listing")
            self.status = "completed"
        except (HarnessRefusal, GovernorError) as exc:
            self.refusal, self.status, listing = str(exc), "refused", None
        except Exception as exc:
            self.error_type, self.status, listing = type(exc).__name__, "failed", None
        finally:
            if isinstance(self.executor, ThreadPoolExecutor):
                self.executor.shutdown(wait=True)
        by_status, complete = {}, False
        if listing is not None:
            orders, complete, _ = listing
            for order in orders:
                if str(order.get("client_order_id") or "").startswith(self.prefix or "\0"):
                    status = str(order.get("status") or "unknown")
                    by_status[status] = by_status.get(status, 0) + 1
        if self.status == "completed" and (self.error_type or (cancel and not self.cleanup.get("verified_zero_open"))
                                           or not complete):
            self.status = "needs_attention"
        self.receipt = {
            "schema_version": 1, "harness": HARNESS_VERSION, "mode": self.mode,
            "evidence_class": getattr(self.port, "evidence_class", "unknown"),
            "policy": POLICY_STATEMENT, "counts_as_strategy_trades": False, "strategy_trades": 0,
            "status": self.status, "stage": self.stage, "refusal_reason": self.refusal,
            "error_type": self.error_type, "client_order_id_prefix": self.prefix,
            "journal": {"intents": len(record["intents"]) if record else None,
                        "end_record_present": bool(record and record["end"])},
            "cleanup": self.cleanup if cancel else None,
            "broker_orders_with_prefix": {"listing_complete": bool(complete), "by_status": dict(sorted(by_status.items()))},
            "rate": self.governor.summary() if self.governor else None,
            "provenance": dict(source_provenance(), argv=self.argv,
                               ended_at=datetime.fromtimestamp(self.clock.time(), timezone.utc).isoformat(),
                               exit_code=self.exit_code),
        }
        return self.receipt

    # -- metrics & receipt ------------------------------------------------------
    def _windows(self):
        if self.t0 is None:
            return [], []
        end = self.submit_phase_end if self.submit_phase_end is not None else self.clock.monotonic()
        full = int((end - self.t0) // 60)

        def blank(index):
            return {"index": index, "submits": 0, "cancels": 0, "submits_attempted": 0,
                    "cancels_attempted": 0, "reads": 0}

        windows = {index: blank(index) for index in range(full)}
        for action in self.actions:
            if action["t"] < self.t0:
                continue
            index = int((action["t"] - self.t0) // 60)
            row = windows.setdefault(index, blank(index))
            kind = action["kind"]
            if kind == "read":
                row["reads"] += 1
                continue
            name = "submits" if kind == "submit" else "cancels"
            row[name + "_attempted"] += 1
            # Only broker-accepted submits and acknowledged cancels (2xx) are completed
            # order actions; rejections, 429s, unsent and failed calls are not.
            if action.get("ok"):
                row[name] += 1
        rows = []
        for index in sorted(windows):
            row = windows[index]
            row["order_actions"] = row["submits"] + row["cancels"]
            row["order_actions_attempted"] = row["submits_attempted"] + row["cancels_attempted"]
            row["full"] = index < full
            rows.append(row)
        return rows, [row for row in rows if row["full"]]

    def _http_429_accounting(self):
        """A 429 is handled when admissions froze for its backoff (always, by
        construction) and the affected operation's outcome was later resolved."""
        total = self.governor.stats["http_429"] if self.governor else 0
        rec = self.reconciliation
        resolved_listing = bool(rec.get("performed") and rec.get("listing_complete"))
        attributed = unresolved = 0
        for probe in self.probes.values():
            if probe.rest_status == 429:
                attributed += 1
                unresolved += 0 if resolved_listing else 1
            cancels = sum(1 for status in probe.cancel_statuses if status == 429)
            attributed += cancels
            if cancels and not (probe.terminal or (resolved_listing and probe.seq not in rec.get("non_terminal_at_end", []))):
                unresolved += cancels
        other = max(0, total - attributed)
        if other and not (self.cleanup.get("verified_zero_open") and resolved_listing):
            unresolved += other
        return total, total - unresolved

    def _build_receipt(self):
        rows, full_rows = self._windows()
        effective = self.governor.effective_limit if self.governor else None
        target = math.ceil(self.config.target_actions_ratio * effective) if effective else None
        streak = best = 0
        for row in full_rows:
            streak = streak + 1 if target is not None and row["order_actions"] >= target else 0
            best = max(best, streak)
        sent = [p for p in self.probes.values() if p.state != "not_sent"]
        rest_latency = [p.rest_at - p.sent_at for p in sent if p.rest_at is not None]
        ack_latency = [p.stream_ack_at - p.sent_at for p in sent if p.stream_ack_at is not None]
        terminal_latency = [p.terminal_at - p.sent_at for p in sent if p.terminal_at is not None]
        # Orders known to exist: accepted by REST, seen on the stream, or proven by
        # the final broker listing (e.g. an ambiguous submit whose order was created).
        existing = [p for p in self.probes.values() if p.state in ("accepted", "accepted_by_stream") or p.events
                    or p.client_order_id in self._broker_seen]
        acked = [p for p in existing if p.stream_ack_at is not None or p.terminal_status == "rejected"]
        terminal = [p for p in existing if p.terminal]
        complete = [p for p in acked if p.terminal]
        completeness = len(complete) / len(existing) if existing else None
        total_429, handled_429 = self._http_429_accounting()
        observed, remaining_min, statuses = {}, {}, {}
        for response in self.responses:
            origin = response.get("origin") or "trading"
            label = "%s:%s:%s" % (origin, response.get("kind"), response.get("status"))
            statuses[label] = statuses.get(label, 0) + 1
            headers = response.get("headers") or {}
            limit = headers.get("x-ratelimit-limit")
            if limit is not None:
                key = "%s:%s" % (origin, limit)
                observed[key] = observed.get(key, 0) + 1
            remaining = headers.get("x-ratelimit-remaining")
            if remaining is not None and str(remaining).isdigit():
                remaining_min[origin] = min(remaining_min.get(origin, 10 ** 9), int(remaining))
        end = self.submit_phase_end if self.submit_phase_end is not None else self.t0
        duration = (end - self.t0) if self.t0 is not None else 0.0
        phase_actions = [a for a in self.actions if a["kind"] in ("submit", "cancel", "cancel_all")
                         and self.t0 is not None and self.t0 <= a["t"] <= end]
        in_phase = sum(1 for a in phase_actions if a.get("ok"))
        frozen_met = (self.config.required_windows >= FROZEN_REQUIRED_WINDOWS
                      and self.config.target_actions_ratio >= FROZEN_TARGET_ACTIONS_RATIO)
        acceptance = {
            "target_order_actions_per_window": target,
            "target_rule": ("ceil(target_actions_ratio * effective_limit); each broker-accepted submit and "
                            "each acknowledged (2xx) cancel is one completed order action"),
            "required_consecutive_full_windows": self.config.required_windows,
            "best_consecutive_full_windows_at_target": best,
            "sustained": best >= self.config.required_windows,
            "unhandled_http_429": total_429 - handled_429,
            "websocket_completeness_is_1": completeness == 1.0,
            "reconciliation_clean": bool(self.reconciliation.get("clean")),
            "cleanup_verified_zero_open": bool(self.cleanup.get("verified_zero_open")),
            "no_unexpected_fills": self.unexpected_fill_qty == 0,
            "no_health_freezes": not self._health,
            "evidence_class_qualifies": getattr(self.port, "evidence_class", None) == "native_paper",
            "frozen_criteria": {"required_windows_min": FROZEN_REQUIRED_WINDOWS,
                                "target_actions_ratio_min": FROZEN_TARGET_ACTIONS_RATIO,
                                "configured_at_or_above": frozen_met}}
        acceptance["capacity_criteria_met"] = (self.status == "completed" and acceptance["unhandled_http_429"] == 0
                                               and all(acceptance[key] for key in (
                                                   "sustained", "websocket_completeness_is_1",
                                                   "reconciliation_clean", "cleanup_verified_zero_open",
                                                   "no_unexpected_fills", "no_health_freezes")))
        blockers = []
        if not acceptance["capacity_criteria_met"]:
            blockers.append("capacity_criteria_not_met")
        if not frozen_met:
            blockers.append("criteria_below_frozen_minimum")
        if not acceptance["evidence_class_qualifies"]:
            blockers.append("evidence_class_not_native_paper")
        acceptance["passed"] = not blockers
        acceptance["passed_blockers"] = blockers
        acceptance["passed_is_self_reported"] = True
        acceptance["independent_observation_required"] = (
            "Native acceptance also needs an observation by a separate method, e.g. the Alpaca dashboard or "
            "account-activity export for this prefix, checked against the receipt counts.")
        governor = self.governor.summary() if self.governor else None
        return {
            "schema_version": 1,
            "harness": HARNESS_VERSION,
            "evidence_class": getattr(self.port, "evidence_class", "unknown"),
            "policy": POLICY_STATEMENT,
            "counts_as_strategy_trades": False,
            "strategy_trades": 0,
            "status": self.status,
            "stage": self.stage,
            "refusal_reason": self.refusal,
            "error_type": self.error_type,
            "stop_reason": self._stop_reason,
            "health_freezes": sorted(self._health),
            "started_at": datetime.fromtimestamp(self.started_wall, timezone.utc).isoformat(),
            "provenance": dict(source_provenance(), argv=self.argv,
                               ended_at=datetime.fromtimestamp(self.clock.time(), timezone.utc).isoformat(),
                               exit_code=self.exit_code,
                               journal_used=self.journal_path is not None),
            "session_kind": self.session_kind,
            "port_errors": self.port_errors,
            "extended_hours_orders": self.extended_hours,
            "config": self.config.public(),
            "probe_plan": {"side": "buy", "type": "limit", "time_in_force": "day", "marketable": False,
                           "band_bps_below_bid": self.config.band_bps,
                           "limit_price": None if self.limit_price is None else str(self.limit_price),
                           "cancel": "individual DELETE /v2/orders/{order_id}",
                           "client_order_id_prefix": self.prefix},
            "preflight": self.preflight_summary,
            "rate": governor,
            "rate_limit_changes": [{"seconds_from_start": None if self.t0 is None else round(item["at_monotonic"] - self.t0, 3),
                                    "limit": item["limit"], "effective_limit": item["effective_limit"],
                                    "budget": item["budget"]}
                                   for item in (self.governor.limit_history if self.governor else [])],
            "observed_rate_limit_headers": {"counts_by_origin_and_limit": dict(sorted(observed.items())),
                                            "min_remaining_by_origin": remaining_min},
            "http_status_counts": dict(sorted(statuses.items())),
            "http_429": {"total": total_429, "handled": handled_429, "unhandled": total_429 - handled_429},
            "orders": {"submit_attempts": len(self.probes),
                       "rest_accepted": sum(1 for p in self.probes.values()
                                            if p.rest_status is not None and 200 <= p.rest_status < 300),
                       "rest_rejections": dict(sorted(self.rejections.items())),
                       "cancel_requests": sum(p.cancel_attempts for p in self.probes.values()),
                       "unexpected_fill_qty": str(self.unexpected_fill_qty)},
            "latency": {"submit_rest_ack": _latency_summary(rest_latency),
                        "submit_to_stream_ack": _latency_summary(ack_latency),
                        "submit_to_stream_terminal": _latency_summary(terminal_latency)},
            "throughput": {"submission_phase_seconds": round(duration, 3),
                           "order_actions_in_phase": in_phase,
                           "order_actions_attempted_in_phase": len(phase_actions),
                           "order_actions_not_completed_in_phase": len(phase_actions) - in_phase,
                           "order_actions_per_minute_mean": round(in_phase * 60.0 / duration, 3) if duration > 0 else None,
                           "full_windows": len(full_rows),
                           "min_order_actions_full_window": min((r["order_actions"] for r in full_rows), default=None),
                           "min_submits_full_window": min((r["submits"] for r in full_rows), default=None),
                           "max_order_actions_full_window": max((r["order_actions"] for r in full_rows), default=None),
                           "windows": rows},
            "websocket": dict(self.stream_stats, orders_expected=len(existing), ack_observed=len(acked),
                              terminal_observed=len(terminal), complete=len(complete),
                              completeness=None if completeness is None else round(completeness, 6)),
            "cleanup": self.cleanup,
            "reconciliation": self.reconciliation,
            "acceptance": acceptance,
        }


# -- CLI --------------------------------------------------------------------------

def _paper_scope(state_root, accept_conflict):
    """The adaptive-paper account-writer lock plus a lane-conflict guard."""
    from contextlib import ExitStack
    from safety import SafetyError, account_lock_fingerprint

    @contextmanager
    def scope(fingerprint):
        if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
            raise HarnessRefusal("account_identity_unavailable")
        # adaptive-paper reconciles every order since its first trial started and
        # freezes on any client_order_id it does not own (external_order_detected).
        if (Path(state_root) / fingerprint / "adaptive" / "trial.json").exists() and not accept_conflict:
            raise HarnessRefusal("account_has_adaptive_paper_state")
        with ExitStack() as stack:
            try:
                stack.enter_context(account_lock_fingerprint(fingerprint))
            except SafetyError as exc:  # e.g. account_writer_already_running
                raise HarnessRefusal(str(exc)) from None
            yield
    return scope


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["offline", "paper", "recover", "audit"],
                        help="recover: cancel every open order with a crashed run's journal prefix; "
                             "audit: list that prefix's orders read-only")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--journal", type=Path, default=None,
                        help="run journal (paper default: <output>.journal.jsonl); required by recover/audit")
    parser.add_argument("--env-file", type=Path, help="0600 paper credential file outside any Git worktree")
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--band-bps", type=int, default=500)
    parser.add_argument("--cap", type=int, default=200, help="configured calls/min cap")
    parser.add_argument("--headroom", type=float, default=0.9)
    parser.add_argument("--max-orders", type=int, default=600)
    parser.add_argument("--duration", type=float, default=330.0)
    parser.add_argument("--max-open-orders", type=int, default=10)
    parser.add_argument("--max-order-notional", default="1000")
    parser.add_argument("--max-open-notional", default="10000")
    parser.add_argument("--inflight", type=int, default=4)
    parser.add_argument("--required-windows", type=int, default=5)
    parser.add_argument("--no-extended-hours", action="store_true")
    parser.add_argument("--allow-cancel-all", action="store_true",
                        help="permit DELETE /v2/orders only when cancel_all_guard proves no foreign open orders")
    parser.add_argument("--acknowledge-positions", type=int, default=0,
                        help="exact count of existing nonzero positions the operator accepts")
    parser.add_argument("--acknowledge-open-orders", type=int, default=0,
                        help="exact count of existing open orders the operator accepts")
    parser.add_argument("--feed", default="iex")
    parser.add_argument("--adaptive-state-root", type=Path, default=DEFAULT_STOP.parent)
    parser.add_argument("--accept-adaptive-lane-conflict", action="store_true")
    parser.add_argument("--limit-header", type=int, default=200, help="offline: simulated x-ratelimit-limit")
    parser.add_argument("--stop-file", type=Path, default=None, help="offline only; paper uses the host STOP")
    return parser


def config_from_args(args):
    return CapacityConfig(symbol=args.symbol, band_bps=args.band_bps, configured_cap_per_minute=args.cap,
                          headroom=args.headroom, max_orders=args.max_orders,
                          max_duration_seconds=args.duration, max_open_orders=args.max_open_orders,
                          max_order_notional_usd=args.max_order_notional,
                          max_open_notional_usd=args.max_open_notional, inflight=args.inflight,
                          allow_extended_hours=not args.no_extended_hours,
                          allow_cancel_all=args.allow_cancel_all,
                          acknowledged_positions=args.acknowledge_positions,
                          acknowledged_open_orders=args.acknowledge_open_orders,
                          required_windows=args.required_windows)


def exit_code_for(receipt):
    if receipt["status"] == "refused":
        return 2
    if receipt["status"] != "completed":
        return 3
    if "acceptance" not in receipt:
        return 0
    return 0 if receipt["acceptance"]["capacity_criteria_met"] else 1


def main(argv=None):
    parser = build_parser()
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(raw_argv)
    config = config_from_args(args)
    from runner import save  # adaptive-paper: atomic 0600 JSON write
    if args.command == "offline":
        if args.journal is not None:
            parser.error("--journal is for paper, recover and audit")
        from capacity_fixture import FakeBroker, FakeClock
        clock = FakeClock()
        port = FakeBroker(clock, limit=args.limit_header, symbol=args.symbol)
        run = CapacityRun(port, config, clock=clock, executor=InlineExecutor(),
                          stop_file=args.stop_file or (HERE / "offline-stop-file-not-used"), argv=raw_argv)
    else:
        if args.stop_file is not None:
            parser.error("--stop-file is offline only; paper honours the host STOP file")
        if args.env_file is None:
            parser.error("%s requires --env-file" % args.command)
        if args.command in ("recover", "audit") and args.journal is None:
            parser.error("%s requires --journal" % args.command)
        from runner import credentials  # adaptive-paper: 0600, owner, outside-Git checks
        key, secret = credentials(args.env_file)
        base = env_base_url(args.env_file)
        if base is not None and base.rstrip("/") != PAPER_URL:
            config.base_url = base  # CapacityConfig.validate refuses it before any request
        from alpaca_capacity_port import AlpacaCapacityPort
        port = AlpacaCapacityPort(key, secret, config.symbol, feed=args.feed, workers=config.inflight)
        journal = args.journal
        if args.command == "paper" and journal is None:
            journal = args.output.with_suffix(".journal.jsonl")
        run = CapacityRun(port, config, account_scope=_paper_scope(args.adaptive_state_root,
                                                                   args.accept_adaptive_lane_conflict),
                          journal_path=journal if args.command == "paper" else None, argv=raw_argv)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: run.request_stop("signal"))
    if args.command in ("recover", "audit"):
        receipt = run.recover(args.journal, cancel=args.command == "recover")
    else:
        receipt = run.run()
    code = exit_code_for(receipt)
    receipt["provenance"]["exit_code"] = run.exit_code = code
    save(args.output, receipt)
    summary = {"status": receipt["status"], "evidence_class": receipt["evidence_class"],
               "refusal_reason": receipt["refusal_reason"]}
    if "acceptance" in receipt:
        summary.update(stop_reason=receipt["stop_reason"],
                       capacity_criteria_met=receipt["acceptance"]["capacity_criteria_met"],
                       passed=receipt["acceptance"]["passed"])
    else:
        summary.update(mode=receipt["mode"], by_status=receipt["broker_orders_with_prefix"]["by_status"])
    print(json.dumps(summary))
    return code


if __name__ == "__main__":
    # Run through the importable module so the ports' ``from capacity import
    # Response`` and this engine share one module (not ``__main__`` plus a copy).
    import capacity
    raise SystemExit(capacity.main())
