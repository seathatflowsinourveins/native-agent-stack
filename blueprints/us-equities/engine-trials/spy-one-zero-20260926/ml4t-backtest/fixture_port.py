#!/usr/bin/env python3
"""ml4t-backtest 0.1.12 port of the frozen SPY ``one_zero`` fixture (engine-trial arm).

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
ml4t-backtest 0.1.12 (MIT), PyPI wheel ``ml4t_backtest-0.1.12-py3-none-any.whl`` sha256
8f5dfe7c2ab96c497136934448bb3211d0d3bf8ec24e71b34229ca5cf53e393b, upstream
https://github.com/ml4t/backtest tag v0.1.12 = commit
672804b36915742fe18af9cd09b44e9839d39d6f; with ml4t-specs 0.1.5 (wheel sha256
4c8315f5da52674a1132dafa53568f4e1b02bbd6da400399d61b33d459315117, tag v0.1.5 =
07db811feac5541882201440eae4238c9dd9a39e). The engine is imported from the isolated
environment ``$ENV`` (see ``lockcheck/ml4t.lock``); no engine code is copied here.

Engine documentation this port follows, pinned at 672804b36915742fe18af9cd09b44e9839d39d6f
-------------------------------------------------------------------------------------
* docs/user-guide/profiles.md lines 37-40 (sha256 ee9aa112f6b44ec9267460b41721b3dfba73710675f3fdbbddf9503a209178ac):
  the ``lean`` profile is scoped to daily US equities; this trial runs it on hourly
  bars, outside that documented scope, and says so.
* docs/user-guide/execution-semantics.md lines 11-17 and 43-44 (sha256
  0abc331598e4f5fa8dba6003b165bb6e4fac50da3f5d760f3135cf05214c591f): under NEXT_BAR an
  ordinary order submitted from ``on_data()`` fills at the next bar's open.
* docs/user-guide/market-impact.md lines 229-269 (sha256
  74c18a25955936e6c66b89cd6384cb32cb3e4b46c45937c1e65c306a011afc41) and
  docs/tutorials/costs-and-funding.md (sha256
  5bed400f9fe5576e9e39c887319ea4c0aebbe90a443345dbdddf5e66898dad60):
  ``Engine(..., funding_df=...)`` with ``amount_per_unit`` posts
  ``-quantity * multiplier * amount_per_unit`` before the orders eligible at that feed
  timestamp and records a zero transfer for a flat asset.

Mechanisms (frozen by the preregistration and the arm manifest)
---------------------------------------------------------------
* Configuration: ``get_profile_config('lean')`` with the whole ``commission`` section
  replaced by ``{'model': 'none', 'rate': 0.0}`` (declared deviation D4) plus a
  ``calendar`` section (calendar None, data_frequency 1h, enforce_sessions False),
  built with ``BacktestConfig.from_dict(profile, preset_name='lean', strict=True)``.
* Feed: exactly the 725 rows ``convert.py`` derives, stamped at each bar's END
  instant as tz-aware UTC and declared ``timestamp_semantics=bar_close``.
* Market-on-open: an ordinary market order from ``on_data`` at the completed 16:00
  New York decision bar; NEXT_BAR with execution_price open fills it at the next
  session's first bar open, stamped at that bar's end. Faithful to LEAN only because
  the decision bar is session-final, which is checked at each decision.
* Distributions: one ``funding_df`` row per distribution ``convert.derive_distributions``
  derives from the frozen factor file, at the ex-date session's first bar end, with
  ``amount_per_unit = -per_share``. ``engine_posted`` is true exactly when the engine
  recorded a FundingPayment; the ledger carries that payment's own values.
* Sizing: ``fixture_strategy.target_quantity`` over the engine-reported equity and the
  decision bar's close; the exit sells the engine-reported position.
* Floats: every engine-reported price, fee, cash, equity and funding amount is
  projected with ``Decimal(repr(x)).quantize(Decimal('0.0001'), ROUND_HALF_EVEN)``;
  the raw ``repr`` travels beside it and the largest adjustment is reported.

This port never opens the oracle receipt, a Nautilus receipt or a verdict, never
writes an oracle value into the engine or the receipt, injects no bar, tick or cash,
re-prices no fill and constructs no broker client. Input-hash, plan, manifest-binding
and isolation checks stop it before any engine exists; every other guard is recorded
in the receipt's ``guards`` block so completed runs always yield a receipt to score.

Invocation (inside the run sandbox; see preregistration.json ``isolation``)::

    $ENV/bin/python -I fixture_port.py --lean-data /data --out /out/port

Each of the two runs executes in its own child process of this file, with a freshly
constructed engine. Converted rows, raw reports and logs stay under ``--out``,
outside every checkout; the receipt publishes hashes and the economic ledger only.
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
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
import socket
import subprocess
import sys
import time
import warnings

ARM = "ml4t-backtest"
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
    "package": "ml4t-backtest",
    "version": "0.1.12",
    "upstream_repository": "https://github.com/ml4t/backtest",
    "upstream_tag": "v0.1.12",
    "upstream_commit": "672804b36915742fe18af9cd09b44e9839d39d6f",
    "wheel_sha256": "8f5dfe7c2ab96c497136934448bb3211d0d3bf8ec24e71b34229ca5cf53e393b",
    "ml4t_specs_version": "0.1.5",
    "ml4t_specs_wheel_sha256": "4c8315f5da52674a1132dafa53568f4e1b02bbd6da400399d61b33d459315117",
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
# The documented bwrap run clears the environment and sets exactly these (PWD is
# added by the shell-less exec). This arm declares no addition.
ISOLATED_ENVIRONMENT = {"LANG": "C.UTF-8", "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
                        "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
UNDOCUMENTED_VALUE = "<differs from the documented value; not recorded>"
RUN_LABELS = ("run-1", "run-2")
CHILD_INPUT = "child-input.private.json"
ROWS_FILE = "converted-rows.private.json"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
FUNDING_SOURCE = "engine FundingPayment (Engine funding_df amount_per_unit)"
EXTERNAL_SOURCE = "external fixture_strategy.distribution_ledger; the engine recorded no FundingPayment"


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
        text = float.__repr__(value)
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
    if delta.microseconds:
        raise ValueError("engine_timestamp_not_whole_seconds")
    return delta.days * 86400 + delta.seconds


def bar_end(row) -> datetime:
    """The converted row's bar END instant (ts_event_ns) as a tz-aware UTC datetime."""
    ns = int(row["ts_event_ns"])
    if ns % 10 ** 9:
        raise ValueError("bar_end_not_whole_seconds:" + row["session_date"])
    return datetime.fromtimestamp(ns // 10 ** 9, tz=timezone.utc)


def plain(value):
    """JSON-safe copy of engine configuration values (enums by value, floats kept)."""
    if isinstance(value, enum.Enum):
        return plain(value.value)
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, "item"):
        return plain(value.item())
    return "<" + type(value).__name__ + ">"


def raw(value):
    """Lossless, deterministic serialization of engine records for the private raw report.

    Floats keep their exact repr as strings so two runs compare field by field
    (NaN included); objects without a data model are named by type, never by repr.
    """
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, enum.Enum):
        return raw(value.value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: raw(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, float):
        return "float:" + float.__repr__(value)
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
    if hasattr(value, "item"):
        return raw(value.item())
    return "<" + type(value).__name__ + ">"


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


def preregistered_profile(get_profile_config) -> tuple[dict, dict, list]:
    """The lean profile with the one declared override and the declared additions."""
    preset = get_profile_config("lean")
    profile = copy.deepcopy(preset)
    profile["commission"] = {"model": "none", "rate": 0.0}
    profile["calendar"] = {"calendar": None, "data_frequency": "1h", "enforce_sessions": False}
    changed = sorted(key for key in set(preset) | set(profile) if preset.get(key) != profile.get(key))
    return preset, profile, changed


def prices_frame(pl, rows, asset: str):
    """Exactly the converted rows, stamped at each bar's end instant (UTC)."""
    return pl.DataFrame({
        "timestamp": pl.Series("timestamp", [bar_end(row) for row in rows], dtype=pl.Datetime("us", "UTC")),
        "asset": pl.Series("asset", [asset] * len(rows), dtype=pl.String),
        "open": pl.Series("open", [float(Decimal(row["o"])) for row in rows], dtype=pl.Float64),
        "high": pl.Series("high", [float(Decimal(row["h"])) for row in rows], dtype=pl.Float64),
        "low": pl.Series("low", [float(Decimal(row["l"])) for row in rows], dtype=pl.Float64),
        "close": pl.Series("close", [float(Decimal(row["c"])) for row in rows], dtype=pl.Float64),
        "volume": pl.Series("volume", [int(row["v"]) for row in rows], dtype=pl.Int64),
    })


def funding_frame(pl, events, asset: str):
    """One funding row per derived distribution (the documented funding_df input)."""
    return pl.DataFrame({
        "timestamp": pl.Series("timestamp", [datetime.fromtimestamp(e["utc_seconds"], tz=timezone.utc)
                                             for e in events], dtype=pl.Datetime("us", "UTC")),
        "asset": pl.Series("asset", [asset] * len(events), dtype=pl.String),
        "amount_per_unit": pl.Series("amount_per_unit", [float(e["amount_per_unit"]) for e in events],
                                     dtype=pl.Float64),
    })


def funding_events(rows, distributions) -> list:
    """Place each derived distribution on its ex-date session's first converted bar."""
    first = {}
    for row in rows:
        first.setdefault(row["session_date"], row)
    events = []
    for distribution in distributions:
        row = first.get(distribution["ex_date"])
        if row is None:
            raise Refused("ex_date_has_no_converted_row:" + distribution["ex_date"])
        per_share = Decimal(distribution["per_share"])
        amount = -float(per_share)
        events.append({"ex_date": distribution["ex_date"], "per_share": str(per_share),
                       "utc_seconds": utc_seconds(bar_end(row)),
                       "session_date": row["session_date"], "local_start": row["local_start"],
                       "amount_per_unit": amount, "amount_per_unit_repr": repr(amount),
                       "lean_ex_date_instant_utc_seconds": int(distribution["utc_seconds"])})
    return events


def make_strategy(Strategy, fixture, projection: Projection, rows, case: dict, asset: str):
    """The one_zero decision rule as an ml4t Strategy (on_data per accepted market event)."""
    index_by_end = {int(row["ts_event_ns"]) // 10 ** 9: index for index, row in enumerate(rows)}
    decision_dates = {case["entry_decision_date"], case["exit_decision_date"]}

    class OneZeroPort(Strategy):
        def __init__(self):
            self.intents = []
            self.decisions = []
            self.order_refs = {}
            self.seen = []
            self.unknown_bars = []
            self.callbacks = {"on_start": 0, "on_end": 0, "on_data": 0}

        def on_start(self, broker):
            self.callbacks["on_start"] += 1

        def on_end(self, broker):
            self.callbacks["on_end"] += 1

        def on_data(self, timestamp, data, context, broker):
            self.callbacks["on_data"] += 1
            second = utc_seconds(timestamp)
            self.seen.append(second)
            index = index_by_end.get(second)
            if index is None:
                self.unknown_bars.append(second)
                return
            row = rows[index]
            if row["local_start"] == DECISION_LOCAL_START and row["session_date"] in decision_dates:
                self._decide(index, row, second, data, broker)

        def _decide(self, index, row, second, data, broker):
            try:
                fixture.check_decision_bar_is_session_final(rows, index)
                session_final = guard("decision_bar_is_session_final", True,
                                      row["session_date"] + ": next row opens " + rows[index + 1]["session_date"])
            except ValueError as error:
                session_final = guard("decision_bar_is_session_final", False, str(error))
            close = Decimal(row["c"])
            bar = data.get(asset) or {}
            if bar.get("close") is None:
                engine_close, engine_close_repr = None, None
            else:
                engine_close, engine_close_repr = projection.money(bar["close"])
            close_check = guard("decision_close_matches_converted_row",
                                engine_close is not None and Decimal(engine_close) == close,
                                row["session_date"] + ": engine " + str(engine_close) + ", converted " + str(close))
            equity, equity_repr = projection.money(broker.get_account_value())
            position = broker.get_position(asset)
            held = projection.quantity(position.quantity) if position is not None else 0
            if row["session_date"] == case["entry_decision_date"]:
                wanted = fixture.target_quantity(Decimal(equity), Decimal(case["target"]),
                                                 Decimal(case["sizing_buffer"]), close)
                reason = "entry"
            else:
                wanted, reason = 0, "exit"
            delta = wanted - held
            decision = {"session_date": row["session_date"], "utc_seconds": second,
                        "decision_price": str(close), "engine_close": engine_close,
                        "engine_close_repr": engine_close_repr, "decision_equity": equity,
                        "decision_equity_engine_repr": equity_repr, "held_before": held,
                        "wanted": wanted, "delta": delta, "guards": [session_final, close_check]}
            if delta == 0:
                decision["order_ref"] = None
                self.decisions.append(decision)
                return
            order = broker.submit_order(asset, delta)
            ref = len(self.intents) + 1
            created = getattr(order, "created_at", None) if order is not None else None
            self.intents.append({
                "kind": "intent", "order_ref": ref, "reason": reason, "utc_seconds": second,
                "ts_event_ns": int(row["ts_event_ns"]), "session_date": row["session_date"],
                "quantity": delta, "target": str(Decimal(case["target"])) if wanted else "0",
                "decision_price": str(close), "decision_equity": equity,
                "decision_equity_engine_repr": equity_repr,
                "submitted_engine_clock_utc_seconds": utc_seconds(created) if created is not None else None,
                "submission_status": order.status.value if order is not None else "not_created",
                "order_type": order.order_type.value if order is not None else None})
            if order is not None:
                self.order_refs[order.order_id] = ref
            decision["order_ref"] = ref
            self.decisions.append(decision)

    return OneZeroPort


def cash_path_check(portfolio_state, initial_cash: float, fill_deltas: dict, funding_deltas: dict) -> tuple:
    """Engine cash may change only at fills and funding payments, by exactly their amounts."""
    previous = Decimal(float.__repr__(float(initial_cash)))
    mismatches, changed_bars = [], 0
    for state in portfolio_state:
        second = utc_seconds(state[0])
        cash = Decimal(float.__repr__(float(state[2])))
        change = cash - previous
        expected = fill_deltas.get(second, Decimal(0)) + funding_deltas.get(second, Decimal(0))
        if change != 0:
            changed_bars += 1
        if abs(change - expected) > PROJECTION_NOISE_LIMIT:
            mismatches.append({"utc_seconds": second, "change": format(change, "f"),
                               "expected": format(expected, "f")})
        previous = cash
    return mismatches, changed_bars


def run_engine(rows, events, case: dict, asset: str, fixture, *, label: str) -> dict:
    """One fresh engine over ``rows``: returns the economic record, guards and raw report."""
    import numpy
    import polars as pl
    from ml4t.backtest import BacktestConfig, DataFeed, Engine, OrderSide, Strategy
    from ml4t.backtest.profiles import get_profile_config
    from ml4t.specs.market_data import FeedSpec, TimestampSemantics

    versions = {"ml4t_backtest": importlib.metadata.version("ml4t-backtest"),
                "ml4t_specs": importlib.metadata.version("ml4t-specs"),
                "polars": importlib.metadata.version("polars"),
                "numpy": numpy.__version__, "python": sys.version.split()[0]}
    projection = Projection()
    guards = [guard("engine_version", versions["ml4t_backtest"] == ENGINE["version"]
                    and versions["ml4t_specs"] == ENGINE["ml4t_specs_version"],
                    {"ml4t_backtest": versions["ml4t_backtest"], "ml4t_specs": versions["ml4t_specs"]})]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        preset, profile, changed = preregistered_profile(get_profile_config)
        config = BacktestConfig.from_dict(profile, preset_name="lean", strict=True)
        feed = DataFeed(prices_df=prices_frame(pl, rows, asset),
                        feed_spec=FeedSpec(timestamp_semantics=TimestampSemantics.BAR_CLOSE))
        strategy = make_strategy(Strategy, fixture, projection, rows, case, asset)()
        engine = Engine(feed, strategy, config, funding_df=funding_frame(pl, events, asset))
        result = engine.run()
    broker = engine.broker
    resolved = engine.config

    guards.append(guard("profile_override_only_commission",
                        changed == ["calendar", "commission"] and "calendar" not in preset,
                        {"changed_sections": changed, "preset_commission": plain(preset.get("commission"))}))
    configuration_facts = {
        "execution_mode": resolved.execution_mode.value, "execution_price": resolved.execution_price.value,
        "commission_type": resolved.commission_type.value,
        "commission_nonzero_fields": [name for name in ("commission_rate", "commission_per_share",
                                                        "commission_per_trade", "commission_minimum")
                                      if getattr(resolved, name) != 0],
        "slippage_type": resolved.slippage_type.value,
        "slippage_nonzero_fields": [name for name in ("slippage_rate", "slippage_fixed", "slippage_spread",
                                                      "stop_slippage_rate") if getattr(resolved, name) != 0],
        "commission_model": type(broker.commission_model).__name__,
        "slippage_model": type(broker.slippage_model).__name__,
        "allow_leverage": resolved.allow_leverage, "allow_short_selling": resolved.allow_short_selling,
        "share_type": resolved.share_type.value, "immediate_fill": resolved.immediate_fill,
        "calendar": resolved.resolved_calendar, "enforce_sessions": resolved.enforce_sessions,
        "data_frequency": resolved.resolved_data_frequency.value,
        "timestamp_semantics": plain(resolved.resolved_timestamp_semantics),
        "initial_cash": resolved.initial_cash, "preset_name": resolved.preset_name,
        "session_col": getattr(feed, "session_col", None)}
    guards.append(guard("resolved_configuration", (
        configuration_facts["execution_mode"] == "next_bar" and configuration_facts["execution_price"] == "open"
        and configuration_facts["commission_type"] == "none" and not configuration_facts["commission_nonzero_fields"]
        and configuration_facts["slippage_type"] == "none" and not configuration_facts["slippage_nonzero_fields"]
        and configuration_facts["commission_model"] == "NoCommission"
        and configuration_facts["slippage_model"] == "NoSlippage"
        and configuration_facts["allow_leverage"] is True and configuration_facts["share_type"] == "integer"
        and configuration_facts["immediate_fill"] is False and configuration_facts["calendar"] is None
        and configuration_facts["enforce_sessions"] is False and configuration_facts["data_frequency"] == "1h"
        and configuration_facts["timestamp_semantics"] == "bar_close"
        and configuration_facts["session_col"] is None
        and Decimal(float.__repr__(float(resolved.initial_cash))) == Decimal(case["initial_cash_usd"])),
        configuration_facts))

    expected_ends = [int(row["ts_event_ns"]) // 10 ** 9 for row in rows]
    counts = {str(plain(k)): v for k, v in result.metrics.get("lifecycle_callback_counts", {}).items()}
    guards.append(guard("bars_processed", (
        strategy.seen == expected_ends and not strategy.unknown_bars
        and len(result.portfolio_state) == len(rows) and result.metrics.get("skipped_bars") == 0
        and counts.get("market_event") == len(rows) and counts.get("run_start") == 1
        and counts.get("run_end") == 1 and strategy.callbacks["on_start"] == 1
        and strategy.callbacks["on_end"] == 1),
        {"rows": len(rows), "on_data_calls": strategy.callbacks["on_data"],
         "portfolio_states": len(result.portfolio_state), "skipped_bars": result.metrics.get("skipped_bars"),
         "unknown_bars": len(strategy.unknown_bars), "lifecycle_callback_counts": counts}))
    for decision in strategy.decisions:
        guards.extend(decision["guards"])
    guards.append(guard("decisions_reached", sorted(d["session_date"] for d in strategy.decisions)
                        == sorted({case["entry_decision_date"], case["exit_decision_date"]}),
                        [d["session_date"] for d in strategy.decisions]))

    rows_by_end = {int(row["ts_event_ns"]) // 10 ** 9: row for row in rows}
    sessions = []
    first_end_by_session = {}
    for row in rows:
        if row["session_date"] not in first_end_by_session:
            sessions.append(row["session_date"])
            first_end_by_session[row["session_date"]] = int(row["ts_event_ns"]) // 10 ** 9

    fills, fill_deltas = [], {}
    for fill in result.fills:
        quantity = projection.quantity(fill.quantity)
        signed = quantity if fill.side is OrderSide.BUY else -quantity
        price, price_repr = projection.money(fill.price)
        fee, fee_repr = projection.money(fill.commission)
        second = utc_seconds(fill.timestamp)
        fills.append({"kind": "fill", "order_ref": strategy.order_refs.get(fill.order_id),
                      "utc_seconds": second, "quantity": signed, "side": "BUY" if signed > 0 else "SELL",
                      "price": price, "price_engine_repr": price_repr, "fee": fee, "fee_engine_repr": fee_repr,
                      "slippage_engine_repr": float.__repr__(float(fill.slippage)),
                      "price_source": fill.price_source, "order_type": fill.order_type,
                      "currency": CURRENCY})
        multiplier = Decimal(float.__repr__(float(broker.get_multiplier(fill.asset))))
        fill_deltas[second] = fill_deltas.get(second, Decimal(0)) + (
            -Decimal(signed) * Decimal(price_repr) * multiplier - Decimal(fee_repr))

    payments = {}
    for payment in result.funding_payments:
        payments.setdefault((utc_seconds(payment.timestamp), payment.asset), []).append(payment)
    ledger, funding_deltas, posted_detail = [], {}, []
    for event in events:
        found = payments.get((event["utc_seconds"], asset), [])
        if len(found) == 1:
            payment = found[0]
            amount, amount_repr = projection.money(payment.cash_delta)
            second = utc_seconds(payment.timestamp)
            ledger.append({"ex_date": event["ex_date"], "utc_seconds": second, "per_share": event["per_share"],
                           "quantity": str(projection.quantity(payment.quantity)), "amount": amount,
                           "amount_engine_repr": amount_repr,
                           "amount_per_unit_engine_repr": float.__repr__(float(payment.amount_per_unit)),
                           "engine_posted": True, "source": FUNDING_SOURCE,
                           "lean_ex_date_instant_utc_seconds": event["lean_ex_date_instant_utc_seconds"]})
            funding_deltas[second] = funding_deltas.get(second, Decimal(0)) + Decimal(amount_repr)
            posted_detail.append(event["ex_date"] + ": FundingPayment quantity " + ledger[-1]["quantity"]
                                 + ", cash_delta " + amount_repr + " at " + str(second))
        else:
            external = fixture.distribution_ledger(
                [{"ex_date": event["ex_date"], "utc_seconds": event["lean_ex_date_instant_utc_seconds"],
                  "per_share": event["per_share"]}], fills)[0]
            ledger.append({**external, "source": EXTERNAL_SOURCE,
                           "lean_ex_date_instant_utc_seconds": event["lean_ex_date_instant_utc_seconds"]})
            posted_detail.append(event["ex_date"] + ": " + str(len(found)) + " FundingPayment records")
    expected_keys = {(event["utc_seconds"], asset) for event in events}
    stray = sorted(str(key) for key in payments if key not in expected_keys)
    guards.append(guard("funding_payment_per_event",
                        all(entry["engine_posted"] is True for entry in ledger) and not stray
                        and len(result.funding_payments) == len(events),
                        {"events": posted_detail, "stray_payments": stray,
                         "payments_recorded": len(result.funding_payments)}))

    initial_cash = Decimal(case["initial_cash_usd"])
    cash_ledger = fixture.cash_ledger(initial_cash, fills, ledger)
    fees_usd = str(sum((Decimal(f["fee"]) for f in fills), Decimal(0)))
    dividend_cash_usd = str(sum((Decimal(d["amount"]) for d in ledger), Decimal(0)))
    reconciled = cash_ledger[-1]["cash"] if cash_ledger else str(initial_cash)
    native_cash, native_cash_repr = projection.money(broker.cash)
    position = broker.get_position(asset)
    final_quantity = projection.quantity(position.quantity) if position is not None else 0
    open_orders = len(broker.get_pending_orders())
    open_positions = sum(1 for p in broker.positions.values() if p.quantity != 0)

    intents = strategy.intents
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

    orders = list(broker.orders)
    rejected = [order for order in orders if order.status.value == "rejected"]
    guards.append(guard("orders_filled_none_rejected", (
        len(orders) == len(intents) and not rejected and not result.rejected_orders
        and all(order.status.value == "filled" for order in orders)
        and all(i["submission_status"] == "pending" for i in intents)),
        {"orders": len(orders), "intents": len(intents),
         "statuses": sorted(order.status.value for order in orders), "rejected": len(rejected)}))
    fills_by_ref = {}
    for fill in fills:
        fills_by_ref.setdefault(fill["order_ref"], []).append(fill)
    clock_detail, placement_detail, open_detail = [], [], []
    clock_ok = placement_ok = open_ok = bool(intents)
    for intent in intents:
        own = fills_by_ref.get(intent["order_ref"], [])
        submitted = intent["submitted_engine_clock_utc_seconds"]
        index = sessions.index(intent["session_date"]) if intent["session_date"] in sessions else None
        next_first = (first_end_by_session[sessions[index + 1]]
                      if index is not None and index + 1 < len(sessions) else None)
        clock_ok = clock_ok and submitted is not None and bool(own) and all(
            intent["utc_seconds"] <= submitted < f["utc_seconds"] for f in own)
        clock_detail.append({"order_ref": intent["order_ref"], "decision": intent["utc_seconds"],
                             "submitted_engine_clock": submitted, "fills": [f["utc_seconds"] for f in own]})
        placement_ok = placement_ok and bool(own) and all(f["utc_seconds"] == next_first for f in own)
        placement_detail.append({"order_ref": intent["order_ref"], "next_session_first_bar_end": next_first,
                                 "fills": [f["utc_seconds"] for f in own]})
        for fill in own:
            bar = rows_by_end.get(fill["utc_seconds"])
            matches = bar is not None and Decimal(fill["price"]) == Decimal(bar["o"])
            open_ok = open_ok and matches and fill["price_source"] == "open"
            open_detail.append({"order_ref": intent["order_ref"], "fill_price": fill["price"],
                                "fill_bar_open": bar["o"] if bar is not None else None,
                                "price_source": fill["price_source"]})
    guards.append(guard("submission_clock", clock_ok, clock_detail))
    guards.append(guard("fill_at_next_session_first_bar", placement_ok, placement_detail))
    guards.append(guard("fill_price_is_fill_bar_open", open_ok, open_detail))
    guards.append(guard("costs_zero", all(Decimal(f["fee"]) == 0 and float(f["slippage_engine_repr"]) == 0.0
                                          for f in fills),
                        [{"order_ref": f["order_ref"], "fee_engine_repr": f["fee_engine_repr"],
                          "slippage_engine_repr": f["slippage_engine_repr"]} for f in fills]))
    mismatches, changed_bars = cash_path_check(result.portfolio_state, resolved.initial_cash, fill_deltas,
                                               funding_deltas)
    guards.append(guard("engine_cash_path", not mismatches,
                        {"bars_with_cash_change": changed_bars, "mismatches": mismatches,
                         "fill_bars": len(fill_deltas),
                         "nonzero_funding_bars": sum(1 for v in funding_deltas.values() if v != 0)}))
    end_cash_state = Decimal(float.__repr__(float(result.portfolio_state[-1][2]))) if result.portfolio_state else None
    guards.append(guard("native_end_cash_is_last_portfolio_state",
                        end_cash_state is not None and end_cash_state == Decimal(native_cash_repr),
                        {"broker_cash": native_cash_repr,
                         "last_portfolio_state_cash": format(end_cash_state, "f") if end_cash_state is not None else None}))
    guards.append(guard("float_projection_noise_only", projection.max_abs_adjustment <= PROJECTION_NOISE_LIMIT,
                        projection.summary()))

    record = {
        "intents": intents, "fills": fills, "distribution_ledger": ledger, "cash_ledger": cash_ledger,
        "native_end_cash_usd": native_cash, "native_end_cash_usd_engine_repr": native_cash_repr,
        "final_quantity": final_quantity,
        "order_sequence": [{"order_id": o.order_id, "side": o.side.value, "quantity": raw(o.quantity),
                            "order_type": o.order_type.value, "status": o.status.value,
                            "created_at": raw(o.created_at), "filled_at": raw(o.filled_at),
                            "filled_price": raw(o.filled_price), "filled_quantity": raw(o.filled_quantity)}
                           for o in orders],
        "fill_sequence": [{"order_id": f.order_id, "timestamp": raw(f.timestamp), "side": f.side.value,
                           "quantity": raw(f.quantity), "price": raw(f.price), "commission": raw(f.commission)}
                          for f in result.fills],
        "funding_sequence": [{"timestamp": raw(p.timestamp), "asset": p.asset, "quantity": raw(p.quantity),
                              "amount_per_unit": raw(p.amount_per_unit), "cash_delta": raw(p.cash_delta)}
                             for p in result.funding_payments],
    }
    raw_report = {
        "engine": versions, "configuration": raw(resolved.to_dict()),
        "profile_changed_sections": changed,
        "fills": [raw(f) for f in result.fills], "orders": [raw(o) for o in orders],
        "funding_payments": [raw(p) for p in result.funding_payments],
        "rejected_orders": [raw(o) for o in result.rejected_orders],
        "trades": [raw(t) for t in result.trades],
        "portfolio_state": [raw(s) for s in result.portfolio_state],
        "equity_curve": [raw(e) for e in result.equity_curve],
        "metrics": raw(result.metrics),
        "strategy": {"decisions": strategy.decisions, "intents": intents, "callbacks": strategy.callbacks,
                     "seen": strategy.seen, "unknown_bars": strategy.unknown_bars},
        "end_state": {"cash": raw(broker.cash), "positions": raw(dict(broker.positions)),
                      "pending_orders": [raw(o) for o in broker.get_pending_orders()]},
        "warnings": [{"category": w.category.__name__, "message": str(w.message)} for w in caught],
    }
    warning_messages = sorted(w.category.__name__ + ": " + str(w.message) for w in caught)
    return {
        "label": label, "engine": versions, "record": record,
        "normalized_economic_sha256": digest_text(json.dumps(record, sort_keys=True)),
        "guards": guards, "projection": projection.summary(),
        "configuration": plain(resolved.to_dict()), "configuration_facts": configuration_facts,
        "profile_changed_sections": changed,
        "totals": {"fees_usd": fees_usd, "dividend_cash_usd": dividend_cash_usd,
                   "reconciled_end_cash_usd": reconciled, "native_end_cash_usd": native_cash,
                   "native_end_cash_usd_engine_repr": native_cash_repr, "final_quantity": final_quantity,
                   "engine_final_value_repr": float.__repr__(float(result.metrics.get("final_value", float("nan")))),
                   "engine_total_funding_repr": float.__repr__(float(result.metrics.get("total_funding", 0.0))),
                   "engine_total_commission_repr": float.__repr__(float(result.metrics.get("total_commission", 0.0)))},
        "metrics": {"num_orders": result.metrics.get("num_orders"), "num_fills": result.metrics.get("num_fills"),
                    "num_rejected_orders": result.metrics.get("num_rejected_orders"),
                    "num_funding_events": result.metrics.get("num_funding_events"),
                    "skipped_bars": result.metrics.get("skipped_bars"), "lifecycle_callback_counts": counts},
        "strategy_callbacks": strategy.callbacks,
        "warnings": {"count": len(caught), "categories": sorted({w.category.__name__ for w in caught}),
                     "messages_sha256": digest_text(json.dumps(warning_messages))},
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


def spawn_run(out: Path, label: str) -> dict:
    """One run in a fresh child process of this file (a freshly constructed engine)."""
    command = [sys.executable, "-I", str(PORT_PATH), "--out", str(out), "--child-run", label]
    started = time.monotonic()
    completed = subprocess.run(command, capture_output=True, check=False)
    wall = round(time.monotonic() - started, 3)
    logs = out / label if (out / label).is_dir() else out
    (logs / (label + ".stdout.log")).write_bytes(completed.stdout)
    (logs / (label + ".stderr.log")).write_bytes(completed.stderr)
    return {"label": label, "exit_code": completed.returncode, "wall_seconds": wall,
            "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
            "stderr_bytes": len(completed.stderr)}


def child_main(out: Path, label: str) -> int:
    os.umask(0o077)
    refuse_unless_isolated()
    run_dir = out / label
    run_dir.mkdir(mode=0o700, exist_ok=False)
    child_input = json.loads((out / CHILD_INPUT).read_text())
    blob = (out / child_input["rows_file"]).read_bytes()
    if hashlib.sha256(blob).hexdigest() != ROWS_SHA256 or child_input["rows_sha256"] != ROWS_SHA256:
        raise Refused("child_rows_sha256_mismatch")
    rows = json.loads(blob.decode("utf-8"))
    _, fixture = load_helpers()
    outcome = run_engine(rows, child_input["funding_events"], child_input["case"], child_input["asset"],
                         fixture, label=label)
    raw_text = json.dumps(outcome.pop("raw_report"), indent=1, sort_keys=True) + "\n"
    (run_dir / "raw-report.private.json").write_text(raw_text)
    outcome["raw_report_sha256"] = digest_text(raw_text)
    save(run_dir / "summary.private.json", outcome)
    return 0


def parent_main(lean_data: Path, out: Path) -> int:
    started_utc = utc_now()
    refuse_unless_isolated()
    out = Path(out).absolute()
    if out == REPO or REPO in out.parents:
        raise Refused("output_directory_inside_the_checkout")
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
                             {day: int(row["ts_event_ns"]) // 10 ** 9 for day, row in sorted(decisions.items())}))
    events = funding_events(rows, conversion["distributions"])
    port_guards.append(guard("funding_rows_on_ex_date_first_bars", True,
                             [{"ex_date": e["ex_date"], "utc_seconds": e["utc_seconds"],
                               "local_start": e["local_start"]} for e in events]))
    save(out / CHILD_INPUT, {"rows_file": ROWS_FILE, "rows_sha256": rows_sha256, "funding_events": events,
                             "case": case, "asset": ASSET})

    runs = []
    for label in RUN_LABELS:
        run = spawn_run(out, label)
        runs.append(run)
        if run["exit_code"] != 0:
            raise SystemExit("engine_run_failed:" + label + " exit " + str(run["exit_code"])
                             + " (stderr kept privately beside the run)")
    summaries = [json.loads((out / label / "summary.private.json").read_text()) for label in RUN_LABELS]
    raw_reports = [json.loads((out / label / "raw-report.private.json").read_text()) for label in RUN_LABELS]
    raw_differences = sorted(set(field_differences(raw_reports[0], raw_reports[1])))
    hashes_equal = summaries[0]["normalized_economic_sha256"] == summaries[1]["normalized_economic_sha256"]
    two_run_records_equal = hashes_equal and not raw_differences
    primary = summaries[0]
    record = primary["record"]
    guards = [dict(g, scope="port") for g in port_guards]
    for summary in summaries:
        guards += [dict(g, scope=summary["label"]) for g in summary["guards"]]
    failed = sorted({g["scope"] + ":" + g["name"] for g in guards if g["outcome"] != "pass"})
    tolerances = json.loads((SPY_PARITY / "tolerances.json").read_text())

    receipt = {
        "schema_version": 1,
        "id": "engine-trial-ml4t-backtest-spy-one-zero-20260926",
        "trial": "spy-one-zero-engine-trials-20260926",
        "arm": ARM,
        "gate_context": "Comparison arm beside gate G-a; changes no gate status.",
        "case": CASE_ID,
        "evidence_class": EVIDENCE_CLASS,
        "classification": ("local historical replay on retained bundled sample data through ml4t-backtest "
                           "0.1.12; not an unchanged upstream test, a point-in-time dataset or any broker "
                           "execution"),
        "started_utc": started_utc,
        "observed_utc": utc_now(),
        "engine": {"package": ENGINE["package"], "version": primary["engine"]["ml4t_backtest"],
                   "upstream_repository": ENGINE["upstream_repository"], "upstream_tag": ENGINE["upstream_tag"],
                   "upstream_commit": ENGINE["upstream_commit"], "wheel_sha256": ENGINE["wheel_sha256"],
                   "ml4t_specs": {"version": primary["engine"]["ml4t_specs"],
                                  "wheel_sha256": ENGINE["ml4t_specs_wheel_sha256"]},
                   "polars": primary["engine"]["polars"], "numpy": primary["engine"]["numpy"],
                   "python": primary["engine"]["python"]},
        "frozen_plan": frozen_plan,
        "case_configuration": {
            "initial_cash_usd": case["initial_cash_usd"], "sizing_buffer": case["sizing_buffer"],
            "target": case["target"], "fee_usd": case["fee_usd"], "slippage": case["slippage"],
            **{k: manifest["case_configuration"][k] for k in BINDING_CONFIGURATION_FIELDS if k != "case"},
            "entry_decision_date": ENTRY_DECISION_DATE, "exit_decision_date": EXIT_DECISION_DATE,
            "currency": CURRENCY, "asset": ASSET,
            "determinism_note": "seed is null: the configuration has no stochastic fill, fee, latency or id "
                                "component."},
        "engine_configuration": primary["configuration"],
        "engine_configuration_facts": primary["configuration_facts"],
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
        "funding_input": events,
        "intents": record["intents"],
        "fills": record["fills"],
        "fees_usd": primary["totals"]["fees_usd"],
        "dividend_cash_usd": primary["totals"]["dividend_cash_usd"],
        "reconciled_end_cash_usd": primary["totals"]["reconciled_end_cash_usd"],
        "native_end_cash_usd": primary["totals"]["native_end_cash_usd"],
        "native_end_cash_usd_engine_repr": primary["totals"]["native_end_cash_usd_engine_repr"],
        "final_quantity": primary["totals"]["final_quantity"],
        "engine_totals": {k: primary["totals"][k] for k in ("engine_final_value_repr", "engine_total_funding_repr",
                                                             "engine_total_commission_repr")},
        "distribution_ledger": record["distribution_ledger"],
        "cash_ledger": record["cash_ledger"],
        "runs": [{"label": s["label"], "exit_code": r["exit_code"], "wall_seconds": r["wall_seconds"],
                  "normalized_economic_sha256": s["normalized_economic_sha256"],
                  "raw_report_sha256": s["raw_report_sha256"], "stdout_sha256": r["stdout_sha256"],
                  "stderr_sha256": r["stderr_sha256"], "stderr_bytes": r["stderr_bytes"],
                  "metrics": s["metrics"], "strategy_callbacks": s["strategy_callbacks"],
                  "native_end_cash_usd": s["totals"]["native_end_cash_usd"],
                  "reconciled_end_cash_usd": s["totals"]["reconciled_end_cash_usd"],
                  "final_quantity": s["totals"]["final_quantity"], "projection": s["projection"],
                  "warnings": s["warnings"],
                  "guards_failed": sorted(g["name"] for g in s["guards"] if g["outcome"] != "pass")}
                 for s, r in zip(summaries, runs)],
        "two_run_records_equal": two_run_records_equal,
        "two_run_determinism": {
            "normalized_economic_sha256_equal": hashes_equal,
            "raw_report_sha256_equal": summaries[0]["raw_report_sha256"] == summaries[1]["raw_report_sha256"],
            "raw_field_paths_differing": raw_differences,
            "normalization_rule": "Nothing is normalized: ml4t order ids are sequential per engine and stay "
                                  "raw, and the raw reports carry no run label or wall-clock value.",
            "runs": "two child processes of the port, each constructing a fresh engine"},
        "guards": guards,
        "guards_failed": failed,
        "isolation": isolation_evidence(lean_data),
        "float_projection": {**primary["projection"],
                             "per_run": {s["label"]: s["projection"] for s in summaries}},
        "declared_deviations": ["D1_per_arm_mapping_manifest", "D2_v1_contract_only",
                                "D4_ml4t_lean_preset_commission"],
        "limitations": [
            "The lean profile is documented for daily US equities; this trial runs it on hourly bars, outside "
            "that documented scope.",
            "Distribution cash is posted through the funding input documented for perpetual futures, at each "
            "ex-date's first bar end (10:00 New York) rather than LEAN's 00:00 ex-date instant.",
            "The market-on-open proxy equals LEAN's MarketOnOpenFill only because each decision bar is its "
            "session's final bar.",
            "The account is the lean profile's margin account; margin and adaptive-state equivalence is not "
            "claimed (row margin_and_adaptive_state is blocked).",
            "Bundled sample bytes are not an entitled, point-in-time or market-wide dataset.",
        ],
    }
    save(out / "receipt.json", receipt)
    print(json.dumps({"arm": ARM, "case": CASE_ID, "two_run_records_equal": two_run_records_equal,
                      "fills": len(record["fills"]), "dividend_cash_usd": receipt["dividend_cash_usd"],
                      "native_end_cash_usd": receipt["native_end_cash_usd"],
                      "reconciled_end_cash_usd": receipt["reconciled_end_cash_usd"],
                      "guards_failed": failed, "receipt": "receipt.json"}, sort_keys=True))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ml4t-backtest 0.1.12 port of the frozen SPY one_zero fixture")
    parser.add_argument("--lean-data", type=Path, help="Retained LEAN Data root (the read-only /data mount)")
    parser.add_argument("--out", type=Path, required=True, help="Fresh private output directory")
    parser.add_argument("--child-run", choices=RUN_LABELS, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.child_run:
        return child_main(args.out, args.child_run)
    if args.lean_data is None:
        parser.error("--lean-data is required")
    return parent_main(args.lean_data, args.out)


if __name__ == "__main__":
    sys.exit(main())
