#!/usr/bin/env python3
"""Lumibot 4.6.1 port of the frozen SPY ``one_zero`` fixture (engine-trial arm).

GPL-3.0 notice
--------------
Lumibot 4.6.1 is licensed GPL-3.0 (license file and package metadata at the tag). This
file imports ``lumibot`` from the isolated evaluation environment ``$ENV`` at run time,
for evaluation only. It contains no Lumibot code, docstring, example strategy, test or
data; where it relies on engine behaviour it cites pinned upstream locations instead of
quoting them. The environment, the Lumibot wheel and the locally built ibapi wheel stay
outside every checkout and are never redistributed.

Trial and scoring
-----------------
Preregistered in ``../preregistration.json`` (sha256
73ea82e9007d92e1b00feb86ba190d5fb8842b7d14962c651b0caf74b8522b38, committed at
a74ed16d7084a4d84cd31ce3116a95457baa913c). The receipt this port writes is scored,
unchanged, by ``blueprints/us-equities/engine-nautilus/spy-parity/compare.py``
(sha256 c70386f8...) with the unchanged ``tolerances.json`` (c8bc7231...) against
this arm's ``mapping-manifest.json``: the v1 29-check contract of the Nautilus arm's
``verdict.json``. This port applies no tolerance of its own.

Engine and pins
---------------
lumibot 4.6.1, PyPI wheel ``lumibot-4.6.1-py3-none-any.whl`` sha256
d06b8feb32c8a23026628e9030b9f166a25f4ab3af510d241aaa915516554159, upstream
https://github.com/Lumiwealth/lumibot tag v4.6.1 = commit
2dfdda100cdc34e5acb46a7f13e8208a35aede72. Its pinned dependency ibapi 9.81.1.post1 has
no wheel on PyPI; it was built once, offline, from the hash-checked sdist (built wheel
sha256 664a4d01e9b47da023fde90630aa312d42b88f2f5f31c1adfd5d32f17debdcaf). The
environment is installed from ``lockcheck/lumibot.lock`` with ``--require-hashes``.

Engine documentation this port follows, pinned at 2dfdda100cdc34e5acb46a7f13e8208a35aede72
-------------------------------------------------------------------------------------
* docsrc/backtesting.pandas.rst (sha256
  edb110b53f9437257c31a1b2e44e1b7a494e530332a2a28db71cb469d44f3a2b): a pandas backtest
  wraps a DataFrame in ``Data(asset, df, timestep=...)`` and passes it as
  ``pandas_data`` to the strategy's backtest entry point with ``PandasDataBacktesting``.
  The page documents the minute and day raw timesteps only; this port uses ``hour``,
  a declared, preregistered use of an undocumented PandasData timestep.
* tests/test_hour_timestep_support.py (sha256
  820cd040c146faed010daacb08301b9c787aa7f269721391271b6af6b06bd6ac): ``Data`` accepts
  ``timestep="hour"``, and a native hour request with ``timeshift=-1`` includes the bar
  indexed at the requested instant.

Mechanisms (frozen by the preregistration and the arm manifest)
---------------------------------------------------------------
* Data: exactly the 725 rows ``convert.py`` derives, indexed at each bar's END instant
  (tz-aware), columns open, high, low, close and volume only, ``timestep="hour"``. No
  dividend column, padding, forward fill or resampling.
* Backtest: ``PandasDataBacktesting`` through ``Strategy.run_backtest`` with budget
  100000, empty fee lists, no slippage, ``benchmark_asset=None`` and
  ``risk_free_rate=0.0``; analysis, plots, tearsheets, indicators, progress bar, stats
  and log files are off. The risk-free rate feeds statistics only; left unset, the
  strategy asks Yahoo for ^IRX when it dumps its statistics (observed, and refused by
  the sandbox, in probe-01).
* Decision hook ``after_market_closes`` (the preregistration's example): at the
  session-final bar's end (16:00 New York) the port reads that bar with
  ``get_historical_prices(asset, 1, "hour", timeshift=-1)``, checks its end instant and
  close against the converted row, sizes with ``fixture_strategy.target_quantity`` over
  the engine-reported portfolio value, and submits one market order with
  ``time_in_force="gtc"``. The exit sells the engine-reported position.
* Pre-run finding (probes/hook-probe.json, synthetic bars): the backtesting broker
  processes pending orders at the current clock whenever the strategy next awaits the
  market open, before the clock advances, and prices a market order at the OPEN of the
  bar indexed at that clock. With END-indexed bars a GTC market order submitted at
  16:00 therefore fills at 16:00 at the decision bar's own open, not at the next
  session's first bar. This contradicts the preregistered market_on_open_proxy
  mechanism; the row stays ``resolved`` (binding) and the primary attempt runs this,
  the closest implementation the port contract allows. The port records the outcome
  through its guards and never adjusts a fill.
* Distributions: ``distributions_and_cash`` is unsupported (arm manifest). The ledger is
  ``fixture_strategy.distribution_ledger`` over the engine's own fills at LEAN's
  ex-date instants, ``engine_posted`` false, per-share values from
  ``convert.derive_distributions``. If the engine's trade-event log carries a dividend
  cash event for an ex-date, that posting replaces the external entry, with the
  engine's own amount and instant.
* Fill instants are the broker clock the engine logged with each fill event. The
  ``on_filled_order`` callback is delivered later, when the strategy's event queue
  drains, and is recorded only as a cross-check.
* Floats: every engine-reported price, fee, cash and equity is projected with
  ``Decimal(repr(x)).quantize(Decimal('0.0001'), ROUND_HALF_EVEN)``; the raw ``repr``
  travels beside it and the largest adjustment is reported.
* Identifiers: the preregistration expected uuid4 order identifiers (the Order
  default). In backtests the pinned Strategy.create_order assigns sequential
  ``bt_<n>`` identifiers instead (a pre-run finding); those are deterministic and stay
  raw in the private determinism record, any uuid4 identifier would be replaced by its
  ordinal, and published files carry order ordinals only.

This port never opens the oracle receipt, a Nautilus receipt or a verdict, never
writes an oracle value into the engine or the receipt, injects no bar, tick or cash,
re-prices no fill and constructs no broker client. Input-hash, plan, manifest-binding
and isolation checks stop it before any engine exists; every other guard is recorded
in the receipt's ``guards`` block so completed runs always yield a receipt to score.

Invocation (inside the run sandbox; see preregistration.json ``isolation``)::

    $ENV/bin/python -I fixture_port.py --lean-data /data --out /out/port

``--decision-hook before_market_opens`` or ``before_starting_trading`` selects another
hook for post-hoc variants only (preregistration ``failure_policy`` F5). Each of the two
runs executes in its own child process of this file, with a freshly constructed
engine, its own ``LUMIBOT_CACHE_FOLDER`` under /tmp and its own working directory
under ``--out``. Converted rows, raw reports and logs stay under ``--out``, outside
every checkout; the receipt publishes hashes and the economic ledger only.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
import enum
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import warnings
from zoneinfo import ZoneInfo

ARM = "lumibot"
PORT_PATH = Path(__file__).resolve()
ARM_DIR = PORT_PATH.parent
TRIAL_DIR = ARM_DIR.parent
REPO = ARM_DIR.parents[4]
SPY_PARITY = REPO / "blueprints" / "us-equities" / "engine-nautilus" / "spy-parity"
HISTORICAL = REPO / "blueprints" / "us-equities" / "historical-simulation"
PREREGISTRATION = TRIAL_DIR / "preregistration.json"
PREREGISTRATION_COMMIT = "a74ed16d7084a4d84cd31ce3116a95457baa913c"
MANIFEST = ARM_DIR / "mapping-manifest.json"

ENGINE = {
    "package": "lumibot",
    "version": "4.6.1",
    "license": "GPL-3.0 (evaluation only; imported from the isolated environment, never vendored)",
    "upstream_repository": "https://github.com/Lumiwealth/lumibot",
    "upstream_tag": "v4.6.1",
    "upstream_commit": "2dfdda100cdc34e5acb46a7f13e8208a35aede72",
    "wheel_sha256": "d06b8feb32c8a23026628e9030b9f166a25f4ab3af510d241aaa915516554159",
}
# The pinned dependency with no wheel on PyPI, built once offline from its hash-checked sdist.
BUILT_FROM_SOURCE = {
    "package": "ibapi",
    "version": "9.81.1.post1",
    "sdist_sha256": "49f6678bf4cced996920f32ad4b48e6897749ac30ba14a661082285f4ec09cd6",
    "built_wheel_sha256": "664a4d01e9b47da023fde90630aa312d42b88f2f5f31c1adfd5d32f17debdcaf",
}
# The spy-parity files this port and compare.py share, pinned by the preregistration.
PINNED_SPY_PARITY = {
    "compare.py": "c70386f869e45bcdc54602100991235a450d2a5854445d98ffe45b849454a5ec",
    "convert.py": "08cba0a2aac938e9306935f91c2889b181dfc880b532b5943e0ccda395592c65",
    "fixture_strategy.py": "59649ac50f26c8b6090dc976e4ec0b3b7e2121cc214674f6c122fbbca9b143f1",
    "tolerances.json": "c8bc72317fb4de83f2b0b7e71888828c7dd15a5a7eb2f60b68f87d54e751c15a",
}
PLAN_PATH = HISTORICAL / "plan.json"
PLAN_SHA256 = "60959a050a3b004abf5346d376930b3b2f563096c725dc96e5427703ea203632"
ROWS_SHA256 = "6c6fcf4ae2b6d26521d0e0218501d94f7fcfa7571e902309f0f83ac2a68845cc"
ROWS_SERIALIZATION = "json.dumps(rows, indent=2, sort_keys=True, default=str) + newline"
ROW_COUNT = 725
SESSION_COUNT = 104
EVIDENCE_CLASS = "HIST"
CASE_ID = "one_zero"
ASSET = "SPY"
CURRENCY = "USD"
WINDOW = {"symbol": "SPY", "start": "2019-12-02", "end": "2020-04-30"}
ENTRY_DECISION_DATE = "2019-12-31"
EXIT_DECISION_DATE = "2020-04-29"
DECISION_LOCAL_START = "15:00"  # the hourly row that completes at 16:00 New York
NEW_YORK = ZoneInfo("America/New_York")
TICK = Decimal("0.0001")
PROJECTION_NOISE_LIMIT = Decimal("0.000001")
PROJECTION_RULE = ("d = Decimal(repr(x)); value = d.quantize(Decimal('0.0001'), rounding=ROUND_HALF_EVEN); "
                   "the compared field carries str(value) and a sibling field suffixed _engine_repr "
                   "carries repr(x). Quantities must equal an integer exactly.")
ROW_ORDER = ("instrument_identity", "raw_data_decoding", "sessions_and_time", "decision_visibility",
             "market_on_open_proxy", "distributions_and_cash", "costs_and_rounding",
             "margin_and_adaptive_state")
BINDING_CONFIGURATION_FIELDS = ("case", "seed", "account_type", "use_random_ids", "fill_model",
                                "fee_model", "window")
# The documented bwrap run clears the environment and sets exactly these (PWD is added
# by the shell-less exec). The last two are this arm's declared additions (deviation D3).
ISOLATED_ENVIRONMENT = {"LANG": "C.UTF-8", "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
                        "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
                        "LUMIBOT_DISABLE_DOTENV": "1", "LUMIBOT_CACHE_FOLDER": "/tmp/lumibot-cache"}
DECLARED_ADDITIONS = ("LUMIBOT_CACHE_FOLDER", "LUMIBOT_DISABLE_DOTENV")
UNDOCUMENTED_VALUE = "<differs from the documented value; not recorded>"
RUN_LABELS = ("run-1", "run-2")
CHILD_INPUT = "child-input.private.json"
ROWS_FILE = "converted-rows.private.json"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
STRATEGY_NAME = "one_zero_port"
PRIMARY_HOOK = "after_market_closes"
DECISION_HOOKS = ("after_market_closes", "before_market_opens", "before_starting_trading")
# The timeshift that returns the decision bar at each hook (probes/hook-probe.json): at 16:00
# and before the next open, -1 includes the bar indexed at or before the clock; at the next
# session's 10:00 the bar indexed 10:00 exists and 0 excludes it.
READ_TIMESHIFT = {"after_market_closes": -1, "before_market_opens": -1, "before_starting_trading": 0}
HOOK_CALLS = ("before_market_opens", "before_starting_trading", "on_trading_iteration",
              "before_market_closes", "after_market_closes")
# Naive datetimes; Lumibot localizes them to its default zone, America/New_York.
BACKTEST_START = datetime(2019, 12, 2, 0, 0)
BACKTEST_END = datetime(2020, 4, 30, 23, 59)
BACKTEST_ARGUMENTS = {
    "budget": 100000.0, "sleeptime": "60M", "minutes_before_opening": 60, "minutes_before_closing": 5,
    "buy_trading_fees": [], "sell_trading_fees": [], "benchmark_asset": None, "risk_free_rate": 0.0,
    "analyze_backtest": False, "show_plot": False, "show_tearsheet": False, "save_tearsheet": False,
    "show_indicators": False, "show_progress_bar": False, "save_stats_file": False, "save_logfile": False,
    "quiet_logs": True, "name": STRATEGY_NAME,
}
UUID_HEX = re.compile(r"^[0-9a-f]{32}$")
SEQUENTIAL_BACKTEST_ID = re.compile(r"^bt_[1-9][0-9]*$")
IDENTIFIER_FIELDS = ("identifier", "parent_identifier", "event_id", "_identifier")
EXTERNAL_SOURCE = "external fixture_strategy.distribution_ledger; the engine recorded no dividend cash event"
POSTED_SOURCE = "engine trade-event log dividend cash event"
BLOCKED_LOOKUP_MARKER = b"Could not resolve host"


class Refused(SystemExit):
    """A precondition failed before any engine was constructed."""

    def __init__(self, reason: str):
        super().__init__("refused: " + reason)


def digest(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n")


def repo_relative(path) -> str:
    return Path(path).resolve().relative_to(REPO).as_posix()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_module(name: str, path: Path, expected_sha256: str):
    """Load a pinned spy-parity helper by path (python -I drops the script directory)."""
    if digest(path) != expected_sha256:
        raise Refused("pinned_source_sha256_mismatch:" + path.name)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_helpers():
    """convert.py and the pure helpers of fixture_strategy.py, unchanged and hash-checked.

    fixture_strategy.build_strategy (which imports nautilus_trader) is never called.
    """
    convert = load_module("spy_parity_convert", SPY_PARITY / "convert.py", PINNED_SPY_PARITY["convert.py"])
    fixture = load_module("spy_parity_fixture", SPY_PARITY / "fixture_strategy.py",
                          PINNED_SPY_PARITY["fixture_strategy.py"])
    return convert, fixture


class Projection:
    """The preregistered float projection (preregistration.json ``float_projection``)."""

    def __init__(self):
        self.values = 0
        self.max_abs_adjustment = Decimal(0)

    def money(self, value) -> tuple[str, str]:
        if isinstance(value, bool) or value is None:
            raise TypeError("unexpected_engine_value:" + repr(value))
        if isinstance(value, Decimal):
            return str(value), repr(value)
        if isinstance(value, int):
            return str(value), repr(value)
        if not isinstance(value, float):
            raise TypeError("unexpected_engine_value_type:" + type(value).__name__)
        if not math.isfinite(value):
            raise ValueError("nonfinite_engine_value")
        text = float.__repr__(float(value))
        exact = Decimal(text)
        projected = exact.quantize(TICK, rounding=ROUND_HALF_EVEN)
        self.values += 1
        adjustment = abs(projected - exact)
        if adjustment > self.max_abs_adjustment:
            self.max_abs_adjustment = adjustment
        return str(projected), text

    @staticmethod
    def quantity(value) -> int:
        if isinstance(value, bool) or value is None:
            raise TypeError("unexpected_engine_quantity:" + repr(value))
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("nonfinite_engine_quantity")
        if value != int(value):
            raise ValueError("non_integral_engine_quantity:" + repr(value))
        return int(value)

    def summary(self) -> dict:
        return {"rule": PROJECTION_RULE, "values_projected": self.values,
                "max_abs_adjustment": format(self.max_abs_adjustment, "f"),
                "noise_limit": format(PROJECTION_NOISE_LIMIT, "f")}


def utc_seconds(stamp) -> int:
    """Exact UTC epoch seconds of an engine timestamp; naive or fractional stamps refuse."""
    if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("engine_timestamp_not_timezone_aware:" + type(stamp).__name__)
    delta = stamp - EPOCH
    if delta.microseconds or getattr(delta, "nanoseconds", 0):
        raise ValueError("engine_timestamp_not_whole_seconds")
    return delta.days * 86400 + delta.seconds


def bar_end(row) -> datetime:
    """The converted row's bar END instant (ts_event_ns) as a tz-aware UTC datetime."""
    ns = int(row["ts_event_ns"])
    if ns % 10 ** 9:
        raise ValueError("bar_end_not_whole_seconds:" + row["session_date"])
    return datetime.fromtimestamp(ns // 10 ** 9, tz=timezone.utc)


def end_seconds(row) -> int:
    return int(row["ts_event_ns"]) // 10 ** 9


def new_york_date(second: int) -> str:
    return datetime.fromtimestamp(second, tz=timezone.utc).astimezone(NEW_YORK).date().isoformat()


def is_missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def raw(value):
    """Lossless, deterministic serialization of engine records for the private raw report.

    Floats keep their exact repr as strings so two runs compare field by field (NaN
    included); objects without a data model are named by type, never by repr.
    """
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, enum.Enum):
        return raw(value.value)
    if isinstance(value, float):
        return "float:" + float.__repr__(float(value))
    if isinstance(value, (str, int)):
        return value
    if isinstance(value, Decimal):
        return "decimal:" + str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): raw(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [raw(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((raw(v) for v in value), key=lambda item: json.dumps(item, sort_keys=True))
    if hasattr(value, "item") and callable(value.item):
        try:
            return raw(value.item())
        except (TypeError, ValueError):
            pass
    symbol = getattr(value, "symbol", None)
    asset_type = getattr(value, "asset_type", None)
    if isinstance(symbol, str):
        return {"asset": symbol, "asset_type": raw(asset_type)}
    return "<" + type(value).__name__ + ">"


class IdentifierMap:
    """Engine identifiers for the determinism record, per the preregistered rule.

    Random identifiers (uuid4 hex, the Order default) are replaced by their ordinal of
    first appearance. The sequential ``bt_<n>`` identifiers the pinned Strategy.create_order
    assigns in backtests (lumibot/strategies/strategy.py lines 884-890 in the wheel) are
    deterministic and stay raw, as ml4t's sequential ids do. Any other shape is recorded
    as unrecognized. No identifier of either kind reaches a published file.
    """

    def __init__(self):
        self.ordinals = {}
        self.sequential = set()
        self.rejected = []

    def token(self, value, kind="order"):
        if value is None:
            return None
        text = str(value)
        if SEQUENTIAL_BACKTEST_ID.match(text):
            self.sequential.add(text)
            return text
        if not UUID_HEX.match(text):
            self.rejected.append(type(value).__name__)
            return "<unrecognized-identifier>"
        if text not in self.ordinals:
            self.ordinals[text] = len(self.ordinals) + 1
        return kind + "-" + str(self.ordinals[text])

    def scrub(self, value):
        """A deep copy with every identifier field replaced by its ordinal token."""
        if isinstance(value, dict):
            return {k: (self.token(v) if k in IDENTIFIER_FIELDS and isinstance(v, str) else self.scrub(v))
                    for k, v in value.items()}
        if isinstance(value, list):
            return [self.scrub(v) for v in value]
        return value


def field_differences(left, right, path="") -> list:
    """Every field path whose value differs between the two runs' raw reports."""
    if isinstance(left, dict) and isinstance(right, dict):
        found = []
        for key in sorted(set(left) | set(right)):
            found += field_differences(left.get(key), right.get(key), path + ("." if path else "") + str(key))
        return found
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [path + "[len]"]
        found = []
        for index, (a, b) in enumerate(zip(left, right)):
            found += field_differences(a, b, path + "[" + str(index) + "]")
        return found
    return [] if left == right else [path]


def guard(name: str, passed: bool, detail) -> dict:
    return {"name": name, "outcome": "pass" if passed else "fail", "detail": detail}


def prices_frame(pd, rows):
    """Exactly the converted rows, indexed at each bar's end instant (tz-aware UTC)."""
    index = pd.DatetimeIndex([bar_end(row) for row in rows], name="datetime")
    return pd.DataFrame({
        "open": [float(Decimal(row["o"])) for row in rows],
        "high": [float(Decimal(row["h"])) for row in rows],
        "low": [float(Decimal(row["l"])) for row in rows],
        "close": [float(Decimal(row["c"])) for row in rows],
        "volume": [int(row["v"]) for row in rows],
    }, index=index)


def session_layout(rows) -> dict:
    sessions, first, last = [], {}, {}
    for row in rows:
        day = row["session_date"]
        if day not in first:
            sessions.append(day)
            first[day] = end_seconds(row)
        last[day] = end_seconds(row)
    following = {sessions[i]: sessions[i + 1] for i in range(len(sessions) - 1)}
    return {"sessions": sessions, "first_end": first, "last_end": last, "following": following}


def make_strategy(Strategy, fixture, projection: Projection, rows, case: dict, asset, hook: str, state: dict):
    """The one_zero decision rule as a Lumibot Strategy (lifecycle hooks only)."""
    layout = session_layout(rows)
    index_by_end = {end_seconds(row): index for index, row in enumerate(rows)}
    decision_rows = fixture.decision_rows(rows, [case["entry_decision_date"], case["exit_decision_date"]])
    if hook == "after_market_closes":
        trigger = {day: day for day in decision_rows}
    else:
        trigger = {layout["following"][day]: day for day in decision_rows}

    class OneZeroPort(Strategy):
        def initialize(self):
            state["initialized"] = state.get("initialized", 0) + 1

        def _call(self, name):
            now = self.get_datetime()
            second = utc_seconds(now)
            state["calls"].append({"hook": name, "utc_seconds": second})
            if name != hook:
                return
            day = new_york_date(second)
            decision_date = trigger.get(day)
            if decision_date is None or decision_date in state["decided"]:
                return
            if hook == "after_market_closes" and second != layout["last_end"][day]:
                return
            state["decided"].add(decision_date)
            self._decide(decision_date, second)

        def _decide(self, decision_date, second):
            row = decision_rows[decision_date]
            index = index_by_end[end_seconds(row)]
            try:
                fixture.check_decision_bar_is_session_final(rows, index)
                session_final = guard("decision_bar_is_session_final", True,
                                      decision_date + ": next row opens " + rows[index + 1]["session_date"])
            except ValueError as error:
                session_final = guard("decision_bar_is_session_final", False, str(error))
            close = Decimal(row["c"])
            shift = READ_TIMESHIFT[hook]
            bars = self.get_historical_prices(asset, 1, "hour", timeshift=shift)
            frame = getattr(bars, "df", None)
            if frame is None or len(frame.index) == 0:
                seen_end, engine_close, engine_close_repr = None, None, None
            else:
                seen_end = utc_seconds(frame.index[-1].to_pydatetime())
                engine_close, engine_close_repr = projection.money(float(frame["close"].iloc[-1]))
            visible = guard("decision_bar_visible_and_matches",
                            seen_end == end_seconds(row) and engine_close is not None
                            and Decimal(engine_close) == close,
                            {"decision_date": decision_date, "timeshift": shift, "engine_bar_end": seen_end,
                             "decision_bar_end": end_seconds(row), "engine_close": engine_close,
                             "converted_close": str(close)})
            equity, equity_repr = projection.money(float(self.get_portfolio_value()))
            position = self.get_position(asset)
            held = projection.quantity(position.quantity) if position is not None else 0
            if decision_date == case["entry_decision_date"]:
                wanted = fixture.target_quantity(Decimal(equity), Decimal(case["target"]),
                                                 Decimal(case["sizing_buffer"]), close)
                reason = "entry"
            else:
                wanted, reason = 0, "exit"
            delta = wanted - held
            decision = {"session_date": decision_date, "utc_seconds": end_seconds(row),
                        "decided_engine_clock_utc_seconds": second, "hook": hook,
                        "decision_price": str(close), "engine_close": engine_close,
                        "engine_close_repr": engine_close_repr, "decision_equity": equity,
                        "decision_equity_engine_repr": equity_repr, "held_before": held,
                        "wanted": wanted, "delta": delta, "guards": [session_final, visible]}
            if delta == 0:
                decision["order_ref"] = None
                state["decisions"].append(decision)
                return
            side = "buy" if delta > 0 else "sell"
            order = self.create_order(asset, abs(delta), side, order_type="market", time_in_force="gtc")
            submitted = self.submit_order(order)
            ref = len(state["intents"]) + 1
            identifier = getattr(submitted, "identifier", None) if submitted is not None else None
            if identifier is not None:
                state["order_refs"][str(identifier)] = ref
            state["intents"].append({
                "kind": "intent", "order_ref": ref, "reason": reason, "utc_seconds": end_seconds(row),
                "ts_event_ns": int(row["ts_event_ns"]), "session_date": decision_date,
                "quantity": delta, "target": str(Decimal(case["target"])) if wanted else "0",
                "decision_price": str(close), "decision_equity": equity,
                "decision_equity_engine_repr": equity_repr, "decision_hook": hook,
                "submitted_engine_clock_utc_seconds": second,
                "submission_status": str(getattr(submitted, "status", None)) if submitted is not None
                else "not_submitted",
                "order_type": str(getattr(submitted, "order_type", None)),
                "time_in_force": str(getattr(submitted, "time_in_force", None))})
            decision["order_ref"] = ref
            state["decisions"].append(decision)

        def before_market_opens(self):
            self._call("before_market_opens")

        def before_starting_trading(self):
            self._call("before_starting_trading")

        def on_trading_iteration(self):
            self._call("on_trading_iteration")

        def before_market_closes(self):
            self._call("before_market_closes")

        def after_market_closes(self):
            self._call("after_market_closes")

        def on_filled_order(self, position, order, price, quantity, multiplier):
            state["fill_callbacks"].append({
                "delivered_engine_clock_utc_seconds": utc_seconds(self.get_datetime()),
                "identifier": str(getattr(order, "identifier", None)), "price": raw(price),
                "quantity": raw(quantity), "multiplier": raw(multiplier), "side": str(getattr(order, "side", None))})

        def on_canceled_order(self, order):
            state["canceled"].append({"engine_clock_utc_seconds": utc_seconds(self.get_datetime()),
                                      "identifier": str(getattr(order, "identifier", None))})

    return OneZeroPort


def trade_event_rows(broker) -> list:
    """The broker's trade-event log, in order, as plain dicts."""
    frame = broker._trade_event_log_df
    if frame is None or len(frame.index) == 0:
        return []
    return [dict(record) for record in frame.to_dict("records")]


def engine_cash_path(stats_rows, initial: Decimal, deltas) -> dict:
    """Engine cash may change only by the logged economic events, in their order."""
    observed = []
    for row in stats_rows:
        value = row.get("cash")
        if is_missing(value):
            continue
        cash = Decimal(float.__repr__(float(value)))
        if not observed or cash != observed[-1]:
            observed.append(cash)
    expected = [initial]
    for delta in deltas:
        expected.append(expected[-1] + delta)
    expected_changes = [value for i, value in enumerate(expected) if i == 0 or value != expected[i - 1]]
    matches = len(observed) == len(expected_changes) and all(
        abs(a - b) <= PROJECTION_NOISE_LIMIT for a, b in zip(observed, expected_changes))
    return {"matches": matches, "observed_distinct_cash": [format(v, "f") for v in observed],
            "expected_distinct_cash": [format(v, "f") for v in expected_changes], "snapshots": len(stats_rows)}


def run_engine(rows, distributions, case: dict, fixture, *, label: str, hook: str) -> dict:
    """One fresh engine over ``rows``: returns the economic record, guards and raw report."""
    import numpy
    import pandas as pd
    import lumibot
    from lumibot.backtesting import PandasDataBacktesting
    from lumibot.entities import Asset, Data
    from lumibot.strategies import Strategy

    versions = {"lumibot": importlib.metadata.version("lumibot"), "lumibot_module": lumibot.__version__,
                "ibapi": importlib.metadata.version("ibapi"), "pandas": pd.__version__,
                "numpy": numpy.__version__, "python": sys.version.split()[0]}
    projection = Projection()
    ids = IdentifierMap()
    guards = [guard("engine_version", versions["lumibot"] == ENGINE["version"]
                    and versions["lumibot_module"] == ENGINE["version"]
                    and versions["ibapi"] == BUILT_FROM_SOURCE["version"],
                    {k: versions[k] for k in ("lumibot", "lumibot_module", "ibapi")})]
    layout = session_layout(rows)
    asset = Asset(symbol=ASSET, asset_type="stock")
    quote = Asset(symbol=CURRENCY, asset_type="forex")
    frame = prices_frame(pd, rows)
    data = Data(asset, frame, timestep="hour", quote=quote)
    state = {"calls": [], "decisions": [], "intents": [], "order_refs": {}, "decided": set(),
             "fill_callbacks": [], "canceled": []}
    strategy_class = make_strategy(Strategy, fixture, projection, rows, case, asset, hook, state)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _, strategy = strategy_class.run_backtest(PandasDataBacktesting, BACKTEST_START, BACKTEST_END,
                                                  pandas_data=[data], **BACKTEST_ARGUMENTS)
    broker = strategy.broker
    source = broker.data_source

    # --- configuration actually in force ---------------------------------------------
    facts = {
        "data_source_class": type(source).__name__, "data_source_timestep": getattr(source, "_timestep", None),
        "data_source_kind": getattr(source, "SOURCE", None),
        "datetime_start": raw(getattr(source, "datetime_start", None)),
        "datetime_end": raw(getattr(source, "datetime_end", None)),
        "data_store_entries": len(getattr(source, "_data_store", {}) or {}),
        "data_timestep": getattr(data, "timestep", None),
        "sleeptime": raw(getattr(strategy, "sleeptime", None)),
        "minutes_before_opening": raw(getattr(strategy, "minutes_before_opening", None)),
        "minutes_before_closing": raw(getattr(strategy, "minutes_before_closing", None)),
        "buy_trading_fees": len(getattr(strategy, "buy_trading_fees", None) or []),
        "sell_trading_fees": len(getattr(strategy, "sell_trading_fees", None) or []),
        "risk_free_rate": raw(getattr(strategy, "_risk_free_rate", "<absent>")),
        "cash_financing_enabled": raw(getattr(strategy, "_cash_financing_enabled", "<absent>")),
        "quote_asset": raw(getattr(strategy, "quote_asset", None)),
        "market": raw(getattr(broker, "market", None)),
        "is_backtesting": raw(getattr(strategy, "is_backtesting", None)),
        "initialize_calls": state.get("initialized", 0),
    }
    guards.append(guard("backtest_configuration", (
        facts["data_source_class"] == "PandasDataBacktesting" and facts["data_source_timestep"] == "hour"
        and facts["data_source_kind"] == "PANDAS" and facts["data_store_entries"] == 1
        and facts["data_timestep"] == "hour" and facts["sleeptime"] == "60M"
        and facts["minutes_before_opening"] == 60 and facts["minutes_before_closing"] == 5
        and facts["buy_trading_fees"] == 0 and facts["sell_trading_fees"] == 0
        and facts["risk_free_rate"] == "float:0.0" and facts["cash_financing_enabled"] is False
        and facts["is_backtesting"] is True and facts["initialize_calls"] == 1), facts))

    # --- the engine held exactly the supplied rows (no padding or forward fill) ---------
    held_frame = data.df
    held_ends = [utc_seconds(stamp.to_pydatetime()) for stamp in held_frame.index]
    same_values = len(held_frame.index) == len(rows) and all(
        float(held_frame["open"].iloc[i]) == float(Decimal(r["o"])) and float(held_frame["high"].iloc[i]) == float(Decimal(r["h"]))
        and float(held_frame["low"].iloc[i]) == float(Decimal(r["l"])) and float(held_frame["close"].iloc[i]) == float(Decimal(r["c"]))
        and int(held_frame["volume"].iloc[i]) == int(r["v"]) for i, r in enumerate(rows))
    guards.append(guard("engine_rows_equal_converted_rows",
                        held_ends == [end_seconds(r) for r in rows] and same_values,
                        {"rows_supplied": len(rows), "rows_held_after_run": len(held_frame.index),
                         "index_timezone": str(getattr(held_frame.index, "tz", None)),
                         "columns": [str(c) for c in held_frame.columns]}))

    # --- trading calendar the engine derived from the rows ------------------------------
    days = getattr(broker, "_trading_days", None)
    calendar = []
    if days is not None:
        for close_stamp, opens in zip(days.index, days["market_open"]):
            calendar.append((utc_seconds(opens.to_pydatetime()), utc_seconds(close_stamp.to_pydatetime())))
    expected_calendar = [(layout["first_end"][d], layout["last_end"][d]) for d in layout["sessions"]]
    guards.append(guard("sessions_from_rows", calendar == expected_calendar,
                        {"engine_sessions": len(calendar), "converted_sessions": len(expected_calendar)}))

    # --- lifecycle clocks ---------------------------------------------------------------
    by_hook = {name: [c["utc_seconds"] for c in state["calls"] if c["hook"] == name] for name in HOOK_CALLS}
    all_ends = [end_seconds(r) for r in rows]
    last_ends = set(layout["last_end"].values())
    want_clock = {
        "before_market_opens": sorted(v - 3600 for v in layout["first_end"].values()),
        "before_starting_trading": sorted(layout["first_end"].values()),
        "on_trading_iteration": sorted(e for e in all_ends if e not in last_ends),
        "after_market_closes": sorted(last_ends),
    }
    guards.append(guard("lifecycle_clock", all(sorted(by_hook[k]) == v for k, v in want_clock.items()),
                        {name: len(calls) for name, calls in by_hook.items()}))

    for decision in state["decisions"]:
        guards.extend(decision["guards"])
    guards.append(guard("decisions_reached", sorted(d["session_date"] for d in state["decisions"])
                        == sorted({case["entry_decision_date"], case["exit_decision_date"]}),
                        [d["session_date"] for d in state["decisions"]]))

    # --- fills and cash events from the engine's trade-event log --------------------------
    events = trade_event_rows(broker)
    for event in events:
        ids.token(event.get("identifier"))
    intents = state["intents"]
    fills, fill_deltas = [], []
    for event in events:
        if str(event.get("event_kind")) != "trade" or str(event.get("status")) != "fill":
            continue
        quantity = projection.quantity(event["filled_quantity"])
        side = str(event.get("side"))
        signed = quantity if side in ("buy", "buy_to_open", "buy_to_cover", "buy_to_close") else -quantity
        price, price_repr = projection.money(event["price"])
        fee, fee_repr = projection.money(event["trade_cost"] if not is_missing(event["trade_cost"]) else 0.0)
        fills.append({"kind": "fill", "order_ref": state["order_refs"].get(str(event.get("identifier"))),
                      "utc_seconds": utc_seconds(event["time"]), "quantity": signed,
                      "side": "BUY" if signed > 0 else "SELL", "price": price, "price_engine_repr": price_repr,
                      "fee": fee, "fee_engine_repr": fee_repr, "order_type": str(event.get("type")),
                      "time_in_force": str(event.get("time_in_force")),
                      "price_source": None if is_missing(event.get("price_source")) else str(event.get("price_source")),
                      "currency": CURRENCY})
        fill_deltas.append((utc_seconds(event["time"]),
                            -Decimal(signed) * Decimal(price_repr) - Decimal(fee_repr)))
    cash_events = [e for e in events if str(e.get("event_kind")) != "trade"]
    dividend_events = [e for e in cash_events if str(e.get("cash_event_type")) == "dividend"]

    ledger, posted_detail, posted_deltas = [], [], []
    for distribution in distributions:
        posted = [e for e in dividend_events if new_york_date(utc_seconds(e["time"])) == distribution["ex_date"]]
        if len(posted) == 1:
            amount, amount_repr = projection.money(float(posted[0]["cash_event_amount"]))
            second = utc_seconds(posted[0]["time"])
            per_share = Decimal(distribution["per_share"])
            ledger.append({"ex_date": distribution["ex_date"], "utc_seconds": second,
                           "per_share": str(per_share),
                           "quantity": str(Decimal(amount) / per_share) if per_share else "0",
                           "amount": amount, "amount_engine_repr": amount_repr, "engine_posted": True,
                           "source": POSTED_SOURCE,
                           "lean_ex_date_instant_utc_seconds": int(distribution["utc_seconds"])})
            posted_deltas.append((second, Decimal(amount_repr)))
            posted_detail.append(distribution["ex_date"] + ": engine dividend cash event " + amount_repr)
        else:
            external = fixture.distribution_ledger([distribution], fills)[0]
            ledger.append({**external, "source": EXTERNAL_SOURCE,
                           "lean_ex_date_instant_utc_seconds": int(distribution["utc_seconds"])})
            posted_detail.append(distribution["ex_date"] + ": " + str(len(posted)) + " engine dividend cash events")
    guards.append(guard("engine_cash_events", not cash_events,
                        {"cash_events": len(cash_events), "dividend_cash_events": len(dividend_events),
                         "distributions": posted_detail}))

    initial_cash = Decimal(case["initial_cash_usd"])
    cash_ledger = fixture.cash_ledger(initial_cash, fills, ledger)
    fees_usd = str(sum((Decimal(f["fee"]) for f in fills), Decimal(0)))
    dividend_cash_usd = str(sum((Decimal(d["amount"]) for d in ledger), Decimal(0)))
    reconciled = cash_ledger[-1]["cash"] if cash_ledger else str(initial_cash)
    native_cash, native_cash_repr = projection.money(float(strategy.cash))
    position = strategy.get_position(asset)
    final_quantity = projection.quantity(position.quantity) if position is not None else 0
    open_orders = len(broker.get_active_tracked_orders(strategy=STRATEGY_NAME))
    open_positions = sum(1 for p in strategy.get_positions()
                         if getattr(p, "asset", None) != quote and getattr(getattr(p, "asset", None), "asset_type",
                                                                               None) != "forex"
                         and Decimal(str(p.quantity)) != 0)

    try:
        fixture.check_causality(intents, [f for f in fills if f["order_ref"] is not None])
        causality = guard("causality", all(f["order_ref"] is not None for f in fills),
                          "every fill strictly after its own decision instant; unattributed fills: "
                          + str(sum(1 for f in fills if f["order_ref"] is None)))
    except ValueError as error:
        causality = guard("causality", False, str(error))
    guards.append(causality)
    try:
        fixture.check_final_state(None, open_orders, open_positions, final_quantity)
        guards.append(guard("final_state", True, "flat; no open order; no pending intent"))
    except ValueError as error:
        guards.append(guard("final_state", False, str(error)))

    orders = broker.get_tracked_orders(strategy=STRATEGY_NAME)
    statuses = sorted(str(o.status) for o in orders)
    guards.append(guard("orders_filled_none_canceled", (
        len(orders) == len(intents) and all(o.is_filled() for o in orders) and not state["canceled"]
        and all(i["submission_status"] in ("new", "open", "submitted", "unprocessed") for i in intents)
        and all(i["time_in_force"] == "gtc" and i["order_type"] == "market" for i in intents)),
        {"orders": len(orders), "intents": len(intents), "statuses": statuses,
         "canceled": len(state["canceled"]),
         "submission_statuses": [i["submission_status"] for i in intents]}))

    rows_by_end = {end_seconds(r): r for r in rows}
    fills_by_ref = {}
    for fill in fills:
        fills_by_ref.setdefault(fill["order_ref"], []).append(fill)
    clock_detail, placement_detail, open_detail = [], [], []
    clock_ok = placement_ok = open_ok = bool(intents)
    for intent in intents:
        own = fills_by_ref.get(intent["order_ref"], [])
        submitted = intent["submitted_engine_clock_utc_seconds"]
        following = layout["following"].get(intent["session_date"])
        next_first = layout["first_end"].get(following) if following else None
        clock_ok = clock_ok and bool(own) and all(intent["utc_seconds"] <= submitted < f["utc_seconds"] for f in own)
        clock_detail.append({"order_ref": intent["order_ref"], "decision": intent["utc_seconds"],
                             "submitted_engine_clock": submitted, "fills": [f["utc_seconds"] for f in own]})
        placement_ok = placement_ok and bool(own) and all(f["utc_seconds"] == next_first for f in own)
        placement_detail.append({"order_ref": intent["order_ref"], "next_session_first_bar_end": next_first,
                                 "fills": [f["utc_seconds"] for f in own]})
        for fill in own:
            bar = rows_by_end.get(fill["utc_seconds"])
            matches = bar is not None and Decimal(fill["price"]) == Decimal(bar["o"])
            open_ok = open_ok and matches
            open_detail.append({"order_ref": intent["order_ref"], "fill_price": fill["price"],
                                "bar_indexed_at_fill_instant": None if bar is None else
                                {"session_date": bar["session_date"], "local_start": bar["local_start"],
                                 "o": bar["o"], "c": bar["c"]}})
    guards.append(guard("submission_clock", clock_ok, clock_detail))
    guards.append(guard("fill_at_next_session_first_bar", placement_ok, placement_detail))
    guards.append(guard("fill_price_is_open_of_bar_indexed_at_fill_instant", open_ok, open_detail))
    guards.append(guard("costs_zero", all(Decimal(f["fee"]) == 0 for f in fills),
                        [{"order_ref": f["order_ref"], "fee_engine_repr": f["fee_engine_repr"]} for f in fills]))

    callbacks = state["fill_callbacks"]
    callback_ok = len(callbacks) == len(fills) and all(
        Decimal(str(c["price"]).split(":")[-1]) == Decimal(f["price_engine_repr"])
        and abs(Decimal(str(c["quantity"]).split(":")[-1])) == abs(Decimal(f["quantity"]))
        and state["order_refs"].get(c["identifier"]) == f["order_ref"] for c, f in zip(callbacks, fills))
    guards.append(guard("fill_callbacks_match_trade_events", callback_ok,
                        [{"order_ref": state["order_refs"].get(c["identifier"]),
                          "delivered_engine_clock_utc_seconds": c["delivered_engine_clock_utc_seconds"]}
                         for c in callbacks]))

    stats_rows = list(getattr(strategy, "_stats_list", []) or [])
    path = engine_cash_path(stats_rows, initial_cash,
                            [d for _, d in sorted(fill_deltas + posted_deltas, key=lambda item: item[0])])
    guards.append(guard("engine_cash_changes_only_at_fills", path["matches"], path))
    fill_path_end = initial_cash + sum((d for _, d in fill_deltas + posted_deltas), Decimal(0))
    last_stats_cash = None
    for row in reversed(stats_rows):
        if not is_missing(row.get("cash")):
            last_stats_cash = Decimal(float.__repr__(float(row["cash"])))
            break
    guards.append(guard("native_end_cash_equals_engine_event_path",
                        abs(Decimal(native_cash_repr) - fill_path_end) <= PROJECTION_NOISE_LIMIT
                        and last_stats_cash is not None
                        and abs(last_stats_cash - Decimal(native_cash_repr)) <= PROJECTION_NOISE_LIMIT,
                        {"engine_cash": native_cash_repr, "initial_plus_engine_events": format(fill_path_end, "f"),
                         "last_snapshot_cash": format(last_stats_cash, "f") if last_stats_cash is not None else None}))
    guards.append(guard("identifiers_recognized", not ids.rejected,
                        {"sequential_backtest_identifiers_kept": len(ids.sequential),
                         "uuid4_hex_identifiers_normalized": len(ids.ordinals), "rejected_types": ids.rejected}))
    guards.append(guard("float_projection_noise_only", projection.max_abs_adjustment <= PROJECTION_NOISE_LIMIT,
                        projection.summary()))

    order_views = [ids.scrub({
        "identifier": str(o.identifier), "side": str(o.side), "quantity": raw(o.quantity),
        "order_type": str(o.order_type), "time_in_force": str(o.time_in_force), "status": str(o.status),
        "avg_fill_price": raw(o.avg_fill_price), "trade_cost": raw(o.trade_cost),
        "transactions": [[raw(t.price), raw(t.quantity)] for t in o.transactions],
        "date_created": raw(getattr(o, "_date_created", None)),
        "broker_create_date": raw(o.broker_create_date), "broker_update_date": raw(o.broker_update_date)})
        for o in orders]
    event_views = [ids.scrub({k: raw(v) for k, v in event.items()}) for event in events]
    record = {
        "intents": intents, "fills": fills, "distribution_ledger": ledger, "cash_ledger": cash_ledger,
        "native_end_cash_usd": native_cash, "native_end_cash_usd_engine_repr": native_cash_repr,
        "final_quantity": final_quantity,
        "order_sequence": [{k: v[k] for k in ("identifier", "side", "quantity", "order_type", "time_in_force",
                                               "status", "avg_fill_price", "transactions", "date_created")}
                           for v in order_views],
        "fill_sequence": [{k: e.get(k) for k in ("time", "identifier", "side", "status", "price",
                                                   "filled_quantity", "trade_cost", "type")}
                          for e in event_views],
    }
    warning_list = sorted({(w.category.__name__, str(w.message)) for w in caught})
    raw_report = {
        "engine": versions, "backtest_arguments": raw(BACKTEST_ARGUMENTS),
        "backtest_window": [BACKTEST_START.isoformat(), BACKTEST_END.isoformat()],
        "decision_hook": hook, "configuration_facts": facts,
        "trade_event_log": event_views, "orders": order_views,
        "stats_rows": [raw(row) for row in stats_rows],
        "calendar": calendar, "calls": state["calls"],
        "decisions": state["decisions"], "intents": intents,
        "fill_callbacks": [ids.scrub(c) for c in callbacks], "canceled": [ids.scrub(c) for c in state["canceled"]],
        "end_state": {"cash": raw(strategy.cash), "portfolio_value": raw(strategy.get_portfolio_value()),
                      "final_quantity": final_quantity, "open_orders": open_orders,
                      "open_positions": open_positions},
        "warnings": [list(w) for w in warning_list],
    }
    return {
        "label": label, "engine": versions, "decision_hook": hook, "record": record,
        "normalized_economic_sha256": digest_text(json.dumps(record, sort_keys=True, default=str)),
        "guards": guards, "projection": projection.summary(), "configuration_facts": facts,
        "identifier_normalization": {"sequential_kept": len(ids.sequential), "uuid4_hex_normalized": len(ids.ordinals),
                                     "rejected": len(ids.rejected), "fields": list(IDENTIFIER_FIELDS)},
        "totals": {"fees_usd": fees_usd, "dividend_cash_usd": dividend_cash_usd,
                   "reconciled_end_cash_usd": reconciled, "native_end_cash_usd": native_cash,
                   "native_end_cash_usd_engine_repr": native_cash_repr, "final_quantity": final_quantity,
                   "engine_portfolio_value_repr": float.__repr__(float(strategy.get_portfolio_value()))},
        "lifecycle_calls": {name: len(calls) for name, calls in by_hook.items()},
        "trade_events": len(events), "cash_events": len(cash_events), "stats_snapshots": len(stats_rows),
        "warnings": {"count": len(caught), "distinct": len(warning_list),
                     "categories": sorted({w[0] for w in warning_list}),
                     "messages_sha256": digest_text(json.dumps(warning_list))},
        "raw_report": raw_report,
    }


def isolation_evidence(data_root: Path) -> dict:
    """What the process observes of its own sandbox; no interpreter or host path is recorded."""
    def read_only(path) -> bool:
        return bool(os.statvfs(path).f_flag & os.ST_RDONLY)

    try:
        uid_map = Path("/proc/self/uid_map").read_text()
    except OSError:
        uid_map = None
    return {"network_interfaces": [list(item) for item in socket.if_nameindex()],
            "environment_names": sorted(os.environ),
            "environment_values": {k: (v if os.environ[k] == v else UNDOCUMENTED_VALUE)
                                   for k, v in ISOLATED_ENVIRONMENT.items() if k in os.environ},
            "environment_additions": sorted(set(os.environ) - set(ISOLATED_ENVIRONMENT) - {"PWD"}),
            "declared_additions": list(DECLARED_ADDITIONS),
            "argv": list(sys.argv), "cwd": os.getcwd(), "python_flags_isolated": sys.flags.isolated,
            "read_only": {"port_source": read_only(ARM_DIR), "spy_parity_sources": read_only(SPY_PARITY),
                          "data_root": read_only(data_root), "python_prefix": read_only(sys.prefix)},
            "uid_map": uid_map}


def refuse_unless_isolated() -> None:
    names = [name for _, name in socket.if_nameindex()]
    if names != ["lo"]:
        raise Refused("network_not_isolated:" + ",".join(names))


def check_pinned_sources() -> dict:
    observed = {name: digest(SPY_PARITY / name) for name in PINNED_SPY_PARITY}
    for name, expected in PINNED_SPY_PARITY.items():
        if observed[name] != expected:
            raise Refused("pinned_source_sha256_mismatch:" + name)
    return observed


def check_plan() -> tuple[dict, dict]:
    """Bind to the frozen historical plan rather than restating it."""
    if digest(PLAN_PATH) != PLAN_SHA256:
        raise Refused("frozen_plan_sha256_mismatch")
    plan = json.loads(PLAN_PATH.read_text())
    specs = [c for c in plan["cases"] if c["id"] == CASE_ID]
    if len(specs) != 1:
        raise Refused("plan_case_not_found")
    spec = specs[0]
    if (plan["start"], plan["end"]) != (WINDOW["start"], WINDOW["end"]) or spec["adaptive"] or spec["reject"]:
        raise Refused("plan_window_or_case_drift")
    if ENTRY_DECISION_DATE not in plan["entry_decision"] or EXIT_DECISION_DATE not in plan["exit_decision"]:
        raise Refused("plan_decision_date_drift")
    case = {"id": CASE_ID, "initial_cash_usd": plan["initial_cash_usd"],
            "sizing_buffer": plan["requested_target_sizing_multiplier"], "target": spec["target"],
            "fee_usd": spec["fee_usd"], "slippage": spec["slippage"],
            "entry_decision_date": ENTRY_DECISION_DATE, "exit_decision_date": EXIT_DECISION_DATE,
            "currency": CURRENCY}
    if Decimal(case["fee_usd"]) != 0 or Decimal(case["slippage"]) != 0:
        raise Refused("one_zero_costs_not_zero")
    if Decimal(case["initial_cash_usd"]) != Decimal(str(BACKTEST_ARGUMENTS["budget"])):
        raise Refused("budget_differs_from_plan")
    frozen = {"path": repo_relative(PLAN_PATH), "sha256": PLAN_SHA256, "case": spec}
    return frozen, case


def binding_projection(manifest: dict) -> dict:
    """preregistration.json arm_manifests.rules.projection, applied to one manifest."""
    rows = manifest["mappings"]
    return {"schema_version": manifest["schema_version"], "evidence_class": manifest["evidence_class"],
            "engine": {"version": manifest["engine"]["version"]},
            "oracle": {"receipt_sha256": manifest["oracle"]["receipt_sha256"],
                       "plan_sha256": manifest["oracle"]["plan_sha256"]},
            "case_configuration": {k: manifest["case_configuration"][k] for k in BINDING_CONFIGURATION_FIELDS},
            "mapping_status": {row["id"]: row["status"] for row in rows},
            "known_short_sessions": next(r for r in rows if r["id"] == "sessions_and_time")["known_short_sessions"],
            "unsupported_mappings": sorted(r["id"] for r in rows if r["status"] == "unsupported")}


def check_manifest_binding() -> tuple[dict, dict]:
    manifest = json.loads(MANIFEST.read_text())
    preregistration = json.loads(PREREGISTRATION.read_text())
    binding = preregistration["arm_manifests"][ARM]["binding"]
    if tuple(row["id"] for row in manifest["mappings"]) != ROW_ORDER:
        raise Refused("manifest_row_order")
    if binding_projection(manifest) != binding:
        raise Refused("manifest_projection_differs_from_preregistered_binding")
    if manifest["engine"]["version"] != ENGINE["version"]:
        raise Refused("manifest_engine_version")
    return manifest, {"projection_equals_binding": True, "rows": len(manifest["mappings"])}


def child_command(out: Path, label: str, hook: str) -> list:
    return [sys.executable, "-I", str(PORT_PATH), "--out", str(out), "--child-run", label, "--decision-hook", hook]


def spawn_run(out: Path, label: str, hook: str) -> dict:
    """One run in a fresh child process of this file (a freshly constructed engine)."""
    run_dir = out / label
    run_dir.mkdir(mode=0o700)
    engine_cwd = run_dir / "engine-cwd"
    engine_cwd.mkdir(mode=0o700)
    env = dict(os.environ, LUMIBOT_CACHE_FOLDER=ISOLATED_ENVIRONMENT["LUMIBOT_CACHE_FOLDER"] + "/" + label)
    command = child_command(out, label, hook)
    started = time.monotonic()
    completed = subprocess.run(command, capture_output=True, check=False, cwd=engine_cwd, env=env)
    wall = round(time.monotonic() - started, 3)
    (run_dir / (label + ".stdout.log")).write_bytes(completed.stdout)
    (run_dir / (label + ".stderr.log")).write_bytes(completed.stderr)
    return {"label": label, "exit_code": completed.returncode, "wall_seconds": wall,
            "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
            "stderr_bytes": len(completed.stderr),
            "blocked_host_lookups": (completed.stdout + completed.stderr).count(BLOCKED_LOOKUP_MARKER),
            "engine_cwd_entries": sorted(p.relative_to(engine_cwd).as_posix() for p in engine_cwd.rglob("*")),
            "cache_folder": env["LUMIBOT_CACHE_FOLDER"]}


def child_main(out: Path, label: str, hook: str) -> int:
    os.umask(0o077)
    refuse_unless_isolated()
    run_dir = out / label
    child_input = json.loads((out / CHILD_INPUT).read_text())
    blob = (out / child_input["rows_file"]).read_bytes()
    if hashlib.sha256(blob).hexdigest() != ROWS_SHA256 or child_input["rows_sha256"] != ROWS_SHA256:
        raise Refused("child_rows_sha256_mismatch")
    if hook != child_input["decision_hook"] or hook not in DECISION_HOOKS:
        raise Refused("child_decision_hook_mismatch")
    rows = json.loads(blob.decode("utf-8"))
    _, fixture = load_helpers()
    outcome = run_engine(rows, child_input["distributions"], child_input["case"], fixture, label=label, hook=hook)
    raw_text = json.dumps(outcome.pop("raw_report"), indent=1, sort_keys=True, default=str) + "\n"
    (run_dir / "raw-report.private.json").write_text(raw_text)
    outcome["raw_report_sha256"] = digest_text(raw_text)
    save(run_dir / "summary.private.json", outcome)
    return 0


def parent_main(lean_data: Path, out: Path, hook: str) -> int:
    started_utc = utc_now()
    refuse_unless_isolated()
    out = Path(out).absolute()
    if out == REPO or REPO in out.parents:
        raise Refused("output_directory_inside_the_checkout")
    if hook not in DECISION_HOOKS:
        raise Refused("unknown_decision_hook:" + hook)
    os.umask(0o077)
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    port_guards = [guard("network_isolation", True, "only lo is visible")]

    local_sources = check_pinned_sources()
    port_guards.append(guard("pinned_spy_parity_sources", True, sorted(local_sources)))
    convert, fixture = load_helpers()
    frozen_plan, case = check_plan()
    port_guards.append(guard("frozen_plan", True, frozen_plan["sha256"]))
    manifest, binding_check = check_manifest_binding()
    port_guards.append(guard("manifest_binding", True, binding_check))

    observed_inputs = convert.verify_inputs(lean_data)
    if observed_inputs != convert.FROZEN_INPUT_SHA256:
        raise Refused("frozen_input_sha256_mismatch")
    short = next(r for r in manifest["mappings"] if r["id"] == "sessions_and_time")["known_short_sessions"]
    conversion = convert.convert(lean_data, WINDOW["symbol"], WINDOW["start"], WINDOW["end"], short)
    rows = conversion["rows"]
    rows_text = json.dumps(rows, indent=2, sort_keys=True, default=str) + "\n"
    rows_sha256 = digest_text(rows_text)
    if len(rows) != ROW_COUNT or conversion["counts"]["sessions"] != SESSION_COUNT or rows_sha256 != ROWS_SHA256:
        raise Refused("converted_rows_mismatch")
    (out / ROWS_FILE).write_text(rows_text)
    port_guards.append(guard("frozen_inputs_and_rows", True,
                             {"inputs": len(observed_inputs), "rows": len(rows), "rows_sha256": rows_sha256}))
    decisions = fixture.decision_rows(rows, [ENTRY_DECISION_DATE, EXIT_DECISION_DATE])
    port_guards.append(guard("decision_rows_present", True,
                             {day: end_seconds(row) for day, row in sorted(decisions.items())}))
    distributions = [{"ex_date": d["ex_date"], "utc_seconds": int(d["utc_seconds"]), "per_share": str(d["per_share"])}
                     for d in conversion["distributions"]]
    save(out / CHILD_INPUT, {"rows_file": ROWS_FILE, "rows_sha256": rows_sha256, "distributions": distributions,
                             "case": case, "asset": ASSET, "decision_hook": hook})

    runs = []
    for label in RUN_LABELS:
        run = spawn_run(out, label, hook)
        runs.append(run)
        if run["exit_code"] != 0:
            raise SystemExit("engine_run_failed:" + label + " exit " + str(run["exit_code"])
                             + " (stderr kept privately beside the run)")
    summaries = [json.loads((out / label / "summary.private.json").read_text()) for label in RUN_LABELS]
    raw_reports = [json.loads((out / label / "raw-report.private.json").read_text()) for label in RUN_LABELS]
    raw_differences = sorted(set(field_differences(raw_reports[0], raw_reports[1])))
    hashes_equal = summaries[0]["normalized_economic_sha256"] == summaries[1]["normalized_economic_sha256"]
    two_run_records_equal = hashes_equal and not raw_differences
    port_guards.append(guard("no_blocked_network_lookups", all(r["blocked_host_lookups"] == 0 for r in runs),
                             {r["label"]: r["blocked_host_lookups"] for r in runs}))
    port_guards.append(guard("no_relative_home_directory", all("~" not in r["engine_cwd_entries"] for r in runs),
                             {r["label"]: r["engine_cwd_entries"] for r in runs}))
    primary = summaries[0]
    record = primary["record"]
    guards = [dict(g, scope="port") for g in port_guards]
    for summary in summaries:
        guards += [dict(g, scope=summary["label"]) for g in summary["guards"]]
    failed = sorted({g["scope"] + ":" + g["name"] for g in guards if g["outcome"] != "pass"})
    tolerances = json.loads((SPY_PARITY / "tolerances.json").read_text())
    primary_hook = hook == PRIMARY_HOOK

    receipt = {
        "schema_version": 1,
        "id": "engine-trial-lumibot-spy-one-zero-20260926" + ("" if primary_hook else "-hook-" + hook),
        "trial": "spy-one-zero-engine-trials-20260926",
        "arm": ARM,
        "gate_context": "Comparison arm beside gate G-a; changes no gate status.",
        "case": CASE_ID,
        "evidence_class": EVIDENCE_CLASS,
        "classification": ("local historical replay on retained bundled sample data through Lumibot 4.6.1 "
                           "(GPL-3.0, evaluation only); not an unchanged upstream test, a point-in-time dataset "
                           "or any broker execution"),
        "started_utc": started_utc,
        "observed_utc": utc_now(),
        "engine": {"package": ENGINE["package"], "version": primary["engine"]["lumibot"],
                   "license": ENGINE["license"], "upstream_repository": ENGINE["upstream_repository"],
                   "upstream_tag": ENGINE["upstream_tag"], "upstream_commit": ENGINE["upstream_commit"],
                   "wheel_sha256": ENGINE["wheel_sha256"],
                   "built_from_source": {**BUILT_FROM_SOURCE, "installed_version": primary["engine"]["ibapi"]},
                   "pandas": primary["engine"]["pandas"], "numpy": primary["engine"]["numpy"],
                   "python": primary["engine"]["python"]},
        "frozen_plan": frozen_plan,
        "case_configuration": {
            "initial_cash_usd": case["initial_cash_usd"], "sizing_buffer": case["sizing_buffer"],
            "target": case["target"], "fee_usd": case["fee_usd"], "slippage": case["slippage"],
            **{k: manifest["case_configuration"][k] for k in BINDING_CONFIGURATION_FIELDS if k != "case"},
            "entry_decision_date": ENTRY_DECISION_DATE, "exit_decision_date": EXIT_DECISION_DATE,
            "currency": CURRENCY, "asset": ASSET,
            "determinism_note": "seed is null: the configuration has no stochastic fill, fee or latency "
                                "component. use_random_ids is true as preregistered (the Order default is a "
                                "uuid4 identifier); in backtests the pinned Strategy.create_order assigns "
                                "sequential bt_<n> identifiers instead, which stay raw in the private "
                                "determinism record, and any uuid4 identifier would be replaced by its "
                                "ordinal."},
        "decision_hook": {"hook": hook, "primary": primary_hook, "read_timeshift": READ_TIMESHIFT[hook],
                          "preregistered_example": PRIMARY_HOOK},
        "engine_configuration": {"backtest_arguments": raw(BACKTEST_ARGUMENTS),
                                 "backtest_window_local": [BACKTEST_START.isoformat(), BACKTEST_END.isoformat()],
                                 "data_source": "PandasDataBacktesting", "data_timestep": "hour",
                                 "bar_index": "bar end instant (ts_event_ns), tz-aware",
                                 "facts": primary["configuration_facts"]},
        "mapping_manifest": {"path": repo_relative(MANIFEST), "sha256": digest(MANIFEST),
                             "schema_version": manifest["schema_version"]},
        "tolerances": {"path": repo_relative(SPY_PARITY / "tolerances.json"),
                       "sha256": digest(SPY_PARITY / "tolerances.json"),
                       "limits": tolerances["limits"], "status": tolerances["status"]},
        "local_source_sha256": local_sources,
        "port_source_sha256": {"path": repo_relative(PORT_PATH), "sha256": digest(PORT_PATH),
                               "verified_by_compare_py": False,
                               "note": "compare.py verifies only spy-parity files; the port's hash is bound "
                                       "by run.json and the trial README."},
        "preregistration": {"path": repo_relative(PREREGISTRATION), "sha256": digest(PREREGISTRATION),
                            "commit": PREREGISTRATION_COMMIT},
        "unsupported_mappings": sorted(r["id"] for r in manifest["mappings"] if r["status"] == "unsupported"),
        "inputs": {"data_root": "/data (read-only sandbox mount)" if str(lean_data) == "/data" else "<LEAN_DATA>",
                   "sha256": observed_inputs, "decoded": conversion["decoded_inputs"],
                   "price_encoding": conversion["price_encoding"],
                   "volume_encoding": conversion["volume_encoding"],
                   "session_source": conversion["session_source"],
                   "forward_filled_rows": conversion["forward_filled_rows"], "map_rows": conversion["map_rows"]},
        "conversion": conversion["counts"],
        "attribution_evidence": {
            "converted_rows_sha256": rows_sha256, "file": ROWS_FILE, "serialization": ROWS_SERIALIZATION,
            "note": "compare.py refuses a --bars file whose digest differs, and re-hashes its own "
                    "re-derivation under --lean-data against this value."},
        "derived_distributions": conversion["distributions"],
        "intents": record["intents"],
        "fills": record["fills"],
        "fees_usd": primary["totals"]["fees_usd"],
        "dividend_cash_usd": primary["totals"]["dividend_cash_usd"],
        "reconciled_end_cash_usd": primary["totals"]["reconciled_end_cash_usd"],
        "native_end_cash_usd": primary["totals"]["native_end_cash_usd"],
        "native_end_cash_usd_engine_repr": primary["totals"]["native_end_cash_usd_engine_repr"],
        "final_quantity": primary["totals"]["final_quantity"],
        "engine_totals": {"engine_portfolio_value_repr": primary["totals"]["engine_portfolio_value_repr"]},
        "distribution_ledger": record["distribution_ledger"],
        "cash_ledger": record["cash_ledger"],
        "runs": [{"label": s["label"], "exit_code": r["exit_code"], "wall_seconds": r["wall_seconds"],
                  "normalized_economic_sha256": s["normalized_economic_sha256"],
                  "raw_report_sha256": s["raw_report_sha256"], "stdout_sha256": r["stdout_sha256"],
                  "stderr_sha256": r["stderr_sha256"], "stderr_bytes": r["stderr_bytes"],
                  "blocked_host_lookups": r["blocked_host_lookups"],
                  "engine_cwd_entries": r["engine_cwd_entries"], "cache_folder": r["cache_folder"],
                  "lifecycle_calls": s["lifecycle_calls"], "trade_events": s["trade_events"],
                  "cash_events": s["cash_events"], "stats_snapshots": s["stats_snapshots"],
                  "native_end_cash_usd": s["totals"]["native_end_cash_usd"],
                  "reconciled_end_cash_usd": s["totals"]["reconciled_end_cash_usd"],
                  "final_quantity": s["totals"]["final_quantity"], "projection": s["projection"],
                  "warnings": s["warnings"], "identifier_normalization": s["identifier_normalization"],
                  "guards_failed": sorted(g["name"] for g in s["guards"] if g["outcome"] != "pass")}
                 for s, r in zip(summaries, runs)],
        "two_run_records_equal": two_run_records_equal,
        "two_run_determinism": {
            "normalized_economic_sha256_equal": hashes_equal,
            "raw_report_sha256_equal": summaries[0]["raw_report_sha256"] == summaries[1]["raw_report_sha256"],
            "raw_field_paths_differing": raw_differences,
            "normalization_rule": "Only random uuid4 hex identifiers (fields " + ", ".join(IDENTIFIER_FIELDS)
                                  + ") are replaced by ordinals in order of first appearance, after format "
                                    "validation; the sequential bt_<n> identifiers Lumibot assigns in backtests "
                                    "stay raw. Timing, prices, quantities, fees, distributions, position "
                                    "transitions and decision order are never normalized, and the raw reports "
                                    "carry no run label or wall-clock value.",
            "runs": "two child processes of the port, each constructing a fresh engine with its own "
                    "LUMIBOT_CACHE_FOLDER and working directory"},
        "guards": guards,
        "guards_failed": failed,
        "isolation": isolation_evidence(lean_data),
        "float_projection": {**primary["projection"],
                             "per_run": {s["label"]: s["projection"] for s in summaries}},
        "pre_run_findings": [
            "probes/hook-probe.json (synthetic bars): a GTC market order submitted in after_market_closes at "
            "a session's final bar end fills at that same instant at that bar's open, because the backtesting "
            "broker processes pending orders at the current clock when the strategy next awaits the open and "
            "prices a market order at the open of the bar indexed at that clock. This contradicts the "
            "preregistered market_on_open_proxy mechanism (predicted fill at the next session's first bar "
            "open, stamped 10:00 New York). The row stays resolved; the primary attempt runs the "
            "preregistered example hook.",
            "probe-01 (without risk_free_rate) showed the strategy asking Yahoo for ^IRX when it dumps its "
            "statistics; the sandbox refused each lookup. The port passes risk_free_rate=0.0, which feeds "
            "statistics only (cash financing is off).",
            "probe-03: in backtests the pinned Strategy.create_order assigns sequential bt_<n> order "
            "identifiers, not the uuid4 identifiers the preregistration expected; they stay raw in the "
            "private determinism record under the preregistered normalization rule."],
        "declared_deviations": ["D1_per_arm_mapping_manifest", "D2_v1_contract_only",
                                "D3_lumibot_environment_and_working_directory"],
        "limitations": [
            "PandasData's pinned documentation names the minute and day raw timesteps only; this arm uses the "
            "hour timestep the Data entity accepts.",
            "Bars are indexed at their END instant; the engine's market-order fill model prices at the open of "
            "the bar indexed at the current clock, which for END-indexed bars is the bar that has just "
            "completed.",
            "Distributions are not posted by the engine in this configuration (row distributions_and_cash is "
            "unsupported); the receipt carries an external Decimal ledger with engine_posted false.",
            "No margin model is configured or claimed (row margin_and_adaptive_state is blocked).",
            "Bundled sample bytes are not an entitled, point-in-time or market-wide dataset.",
        ],
    }
    save(out / "receipt.json", receipt)
    print(json.dumps({"arm": ARM, "case": CASE_ID, "decision_hook": hook,
                      "two_run_records_equal": two_run_records_equal,
                      "fills": [(f["utc_seconds"], f["quantity"], f["price"]) for f in record["fills"]],
                      "dividend_cash_usd": receipt["dividend_cash_usd"],
                      "native_end_cash_usd": receipt["native_end_cash_usd"],
                      "reconciled_end_cash_usd": receipt["reconciled_end_cash_usd"],
                      "guards_failed": failed, "receipt": "receipt.json"}, sort_keys=True))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Lumibot 4.6.1 port of the frozen SPY one_zero fixture")
    parser.add_argument("--lean-data", type=Path, help="Retained LEAN Data root (the read-only /data mount)")
    parser.add_argument("--out", type=Path, required=True, help="Fresh private output directory")
    parser.add_argument("--decision-hook", choices=DECISION_HOOKS, default=PRIMARY_HOOK,
                        help="Lifecycle hook that forms the decision (post-hoc variants only; default is the "
                             "preregistered example)")
    parser.add_argument("--child-run", choices=RUN_LABELS, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child_run:
        return child_main(args.out, args.child_run, args.decision_hook)
    if args.lean_data is None:
        parser.error("--lean-data is required")
    return parent_main(args.lean_data, args.out, args.decision_hook)


if __name__ == "__main__":
    sys.exit(main())
