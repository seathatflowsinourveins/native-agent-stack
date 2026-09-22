#!/usr/bin/env python3
"""Replay the frozen ``one_zero`` SPY case twice on native NautilusTrader 2.0.0rc5.

Both runs use the same seed and the same venue/instrument configuration in fresh
engines. The receipt records the native intents and fills, the independent
``Decimal`` cash ledger, the externally derived distribution cash, the native end
cash, the buying-power and latch event lists, raw and normalized output hashes
for both runs, and the evidence class ``HIST``. This runner applies no numeric
tolerance of its own: its own checks are exact. It records ``tolerances.json``
and its hash in the receipt, and ``compare.py`` is the component that reads and
applies every limit the sheet declares, so a preregistered sheet replaces the
defaults without any code change.

The unsupported mapping list and the declared short sessions are read from
``mapping-manifest.json``; this file never restates them.

No network, no broker client and no credential store is used. Raw native reports
stay in the private output directory; the receipt publishes hashes and the
economic ledger only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import socket
import sys

SOURCE = Path(__file__).resolve().parent
REPO = SOURCE.parents[3]
HISTORICAL = SOURCE.parent.parent / "historical-simulation"
FROZEN_PLAN_SHA256 = "60959a050a3b004abf5346d376930b3b2f563096c725dc96e5427703ea203632"
EVIDENCE_CLASS = "HIST"
SEED = 20260922

WINDOW = {"symbol": "SPY", "start": "2019-12-02", "end": "2020-04-30"}
INSTRUMENT = {"instrument_id": "SPY.SIM", "symbol": "SPY", "venue": "SIM", "currency": "USD",
              "price_precision": 4, "price_increment": "0.0001", "size_precision": 0,
              "lot_size": 1, "bar_type": "SPY.SIM-1-HOUR-LAST-EXTERNAL"}
CASE = {"id": "one_zero", "initial_cash_usd": "100000", "target": "1", "sizing_buffer": "0.98",
        "entry_decision_date": "2019-12-31", "exit_decision_date": "2020-04-29",
        "fee_usd": "0", "slippage": "0", "currency": "USD"}
# Declared before execution as the authorized maximum. Only the fields that
# actually carry a freshly generated UUID4 are normalized; every other declared
# identity is retained raw and proved equal across the two runs.
DECLARED_ID_FIELDS = ("client_order_id", "venue_order_id", "init_id", "event_id", "last_trade_id",
                      "trade_id", "position_id", "account_id", "trader_id", "strategy_id",
                      "order_list_id", "exec_spawn_id")
APPLIED_ID_FIELDS = ("init_id", "event_id")
UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CONVERT = _load("spy_parity_convert", SOURCE / "convert.py")
FIXTURE = _load("spy_parity_fixture", SOURCE / "fixture_strategy.py")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n")


def number(value) -> Decimal:
    """Parse a native report value, including a currency suffix."""
    return Decimal(str(value).split()[0].replace(",", "").replace("_", ""))


def load_manifest(path: Path | None = None) -> dict:
    return json.loads(Path(path or SOURCE / "mapping-manifest.json").read_text())


def unsupported_mappings(manifest: dict) -> list:
    """The single source of truth: manifest rows whose status is unsupported."""
    return sorted(row["id"] for row in manifest["mappings"] if row["status"] == "unsupported")


def known_short_sessions(manifest: dict) -> dict:
    row = next(r for r in manifest["mappings"] if r["id"] == "sessions_and_time")
    return row["known_short_sessions"]


def check_frozen_plan() -> dict:
    """Bind this fixture to the frozen historical plan rather than restating it."""
    plan_path = HISTORICAL / "plan.json"
    if digest(plan_path) != FROZEN_PLAN_SHA256:
        raise ValueError("frozen_plan_hash_mismatch")
    plan = json.loads(plan_path.read_text())
    spec = next(c for c in plan["cases"] if c["id"] == CASE["id"])
    if (spec["target"] != CASE["target"] or spec["fee_usd"] != CASE["fee_usd"]
            or spec["slippage"] != CASE["slippage"] or spec["adaptive"] or spec["reject"]):
        raise ValueError("case_specification_drift")
    if (plan["start"] != WINDOW["start"] or plan["end"] != WINDOW["end"]
            or plan["initial_cash_usd"] != CASE["initial_cash_usd"]
            or plan["requested_target_sizing_multiplier"] != CASE["sizing_buffer"]):
        raise ValueError("plan_window_drift")
    if CASE["entry_decision_date"].replace("-", "") not in plan["entry_decision"].replace("-", ""):
        raise ValueError("entry_decision_drift")
    if CASE["exit_decision_date"].replace("-", "") not in plan["exit_decision"].replace("-", ""):
        raise ValueError("exit_decision_drift")
    return {"path": "blueprints/us-equities/historical-simulation/plan.json",
            "sha256": FROZEN_PLAN_SHA256, "case": spec}


def normalize(value, counters, key=None):
    """Replace generated UUID4 identities with their ordinal, recursively.

    The format is validated before substitution so a non-UUID value can never be
    normalized away. Timing, prices, quantities, fees, distributions, position
    transitions and decision order are never touched.
    """
    if isinstance(value, list):
        return [normalize(item, counters, key) for item in value]
    if isinstance(value, dict):
        return {k: normalize(v, counters, k) for k, v in value.items()}
    if key in APPLIED_ID_FIELDS and value is not None:
        text = str(value)
        if not UUID4_RE.match(text):
            raise ValueError("unexpected_generated_id_format:" + key)
        bucket = counters.setdefault(key, {})
        bucket.setdefault(text, len(bucket) + 1)
        return key + "#" + str(bucket[text])
    return value


def field_differences(left, right, path="") -> list:
    """Every field path whose value differs between the two runs."""
    if isinstance(left, dict) and isinstance(right, dict):
        keys = sorted(set(left) | set(right))
        found = []
        for key in keys:
            found += field_differences(left.get(key), right.get(key),
                                       path + ("." if path else "") + str(key))
        return found
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [path + "[len]"]
        found = []
        for index, (a, b) in enumerate(zip(left, right)):
            found += field_differences(a, b, path + "[" + str(index) + "]")
        return found
    return [] if left == right else [path]


def run_once(rows, distributions, out: Path, label: str) -> dict:
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig
    from nautilus_trader.model import (AccountType, Currency, Equity, InstrumentId, Money,
                                       OmsType, Price, Quantity, Symbol, Venue)

    random.seed(SEED)
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    usd = Currency.from_str(INSTRUMENT["currency"])
    venue = Venue(INSTRUMENT["venue"])
    equity = Equity(InstrumentId.from_str(INSTRUMENT["instrument_id"]), Symbol(INSTRUMENT["symbol"]),
                    usd, INSTRUMENT["price_precision"], Price.from_str(INSTRUMENT["price_increment"]),
                    0, 0, lot_size=Quantity.from_int(INSTRUMENT["lot_size"]))
    bars = CONVERT.to_bars(rows, INSTRUMENT["bar_type"], INSTRUMENT["price_precision"],
                           INSTRUMENT["size_precision"])
    strategy_class = FIXTURE.build_strategy(equity.id, INSTRUMENT["bar_type"], rows, CASE)
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    # Bound before the try so an engine failure surfaces as itself, never as a
    # NameError from the post-run block, and never masked by dispose().
    strategy = raw = reports = result = None
    open_positions = open_orders = None
    failure = None
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH,
                         [Money(Decimal(CASE["initial_cash_usd"]), usd)], base_currency=usd,
                         use_random_ids=False)
        engine.add_instrument(equity)
        engine.add_data(bars)
        strategy = strategy_class()
        engine.add_strategy(strategy)
        engine.run()
        result = engine.get_result()
        reports = {"account": engine.generate_account_report(venue=venue),
                   "positions": engine.generate_positions_report(),
                   "fills": engine.generate_order_fills_report()}
        for name, report in reports.items():
            report.to_csv(out / (name + ".csv"))
        raw = {name: json.loads(report.to_json(orient="records")) for name, report in reports.items()}
        save(out / "reports.private.json", raw)
        open_positions = len(engine.cache.positions_open())
        open_orders = len(engine.cache.orders_open())
    except BaseException as error:  # noqa: BLE001 - the original failure is re-raised
        failure = error
        raise
    finally:
        try:
            engine.dispose()
        except Exception as dispose_error:
            if failure is None:
                raise
            failure.add_note("engine.dispose() also failed: " + repr(dispose_error))

    if strategy is None or raw is None or result is None:
        raise ValueError("engine_run_incomplete:" + label)
    FIXTURE.check_run_integrity(strategy.errors, strategy.bars_seen, len(rows), result.iterations)
    FIXTURE.check_final_state(strategy.pending, open_orders, open_positions, strategy.position)
    FIXTURE.check_causality(strategy.intents, strategy.fills)
    ledger = FIXTURE.distribution_ledger(distributions, strategy.fills)
    cash = FIXTURE.cash_ledger(Decimal(CASE["initial_cash_usd"]), strategy.fills, ledger)
    native_balances = [str(number(row["total"])) for row in raw["account"]]
    counters = {}
    economic = {"intents": strategy.intents, "fills": strategy.fills,
                "order_events": normalize(strategy.order_events, counters),
                "native_account_totals": native_balances,
                "native_fills": normalize(raw["fills"], counters),
                "positions": normalize(raw["positions"], counters)}
    normalized_text = json.dumps(economic, sort_keys=True, default=str)
    record = {
        "label": label,
        "_raw_reports": raw,
        "processed_bars": result.iterations,
        "open_positions": open_positions,
        "open_orders": open_orders,
        "pending_intent": strategy.pending,
        "strategy_callback_errors": strategy.errors,
        "bars_seen": strategy.bars_seen,
        "run_integrity_checked": True,
        "final_state_checked": True,
        "final_quantity": str(strategy.position),
        "native_end_cash_usd": native_balances[-1] if native_balances else None,
        "native_account_events": len(native_balances),
        "fees_usd": str(sum((Decimal(f["fee"]) for f in strategy.fills), Decimal(0))),
        "intents": strategy.intents,
        "fills": strategy.fills,
        "distribution_ledger": ledger,
        "dividend_cash_usd": str(sum((Decimal(d["amount"]) for d in ledger), Decimal(0))),
        "cash_ledger": cash,
        "reconciled_end_cash_usd": cash[-1]["cash"] if cash else CASE["initial_cash_usd"],
        "buying_power_events": strategy.buying_power_events,
        "latch_events": strategy.latch_events,
        "raw_report_sha256": {name: digest(out / (name + ".csv")) for name in reports},
        "normalized_economic_sha256": digest_text(normalized_text),
    }
    save(out / "summary.json", {k: v for k, v in record.items() if k != "_raw_reports"})
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean-data", type=Path, required=True,
                        help="Retained LEAN Data root holding the frozen SPY inputs")
    parser.add_argument("--out", type=Path, required=True, help="Fresh private output directory")
    parser.add_argument("--tolerances", type=Path, default=SOURCE / "tolerances.json")
    args = parser.parse_args()

    installed = importlib.metadata.version("nautilus_trader")
    if installed != "2.0.0rc5":
        raise ValueError("native_version_mismatch:" + installed)
    os.umask(0o077)
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)

    frozen_plan = check_frozen_plan()
    manifest = load_manifest()
    conversion = CONVERT.convert(args.lean_data, WINDOW["symbol"], WINDOW["start"], WINDOW["end"],
                                 known_short_sessions(manifest))
    rows_path = args.out / "converted-rows.private.json"
    save(rows_path, conversion["rows"])
    tolerances = json.loads(args.tolerances.read_text())

    runs = [run_once(conversion["rows"], conversion["distributions"], args.out / label, label)
            for label in ("run-1", "run-2")]
    raw_differences = field_differences(runs[0]["_raw_reports"], runs[1]["_raw_reports"])
    undeclared = sorted({d for d in raw_differences
                         if d.rsplit(".", 1)[-1].split("[")[0] not in APPLIED_ID_FIELDS})
    determinism = {
        "normalized_economic_sha256_equal":
            runs[0]["normalized_economic_sha256"] == runs[1]["normalized_economic_sha256"],
        "raw_report_sha256_equal": runs[0]["raw_report_sha256"] == runs[1]["raw_report_sha256"],
        "raw_field_paths_differing": sorted(set(raw_differences)),
        "undeclared_differing_fields": undeclared,
        "declared_id_fields": list(DECLARED_ID_FIELDS),
        "applied_id_fields": list(APPLIED_ID_FIELDS),
        "normalization_rule": "Only freshly generated UUID4 identities are replaced by their ordinal, "
                              "after format validation. Timing, prices, quantities, fees, "
                              "distributions, transitions and decision order are never normalized.",
    }
    equal = determinism["normalized_economic_sha256_equal"] and not undeclared
    primary = runs[0]

    receipt = {
        "schema_version": 1,
        "id": "spy-parity-one-zero-20260922",
        "gate": "G-a",
        "case": CASE["id"],
        "evidence_class": EVIDENCE_CLASS,
        "classification": "local historical replay on retained bundled sample data; not an unchanged "
                          "upstream test, a point-in-time dataset or any broker execution",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "engine": {"package": "nautilus_trader", "version": installed,
                   "upstream_commit_pin": "1b0a49d2792a9432a3aca3fcb617ce7a630d905e",
                   "python": sys.version.split()[0]},
        "frozen_plan": frozen_plan,
        "case_configuration": {**CASE, "instrument": INSTRUMENT, "window": WINDOW, "seed": SEED,
                               "fill_model": None, "fee_model": None, "use_random_ids": False,
                               "account_type": "CASH",
                               "determinism_note": "one_zero configures no stochastic fill, fee or "
                                                   "latency model; the seed is recorded and applied "
                                                   "but no sampled component is exercised."},
        "mapping_manifest": {"path": "mapping-manifest.json",
                             "sha256": digest(SOURCE / "mapping-manifest.json")},
        "tolerances": {"path": str(args.tolerances.name), "sha256": digest(args.tolerances),
                       "limits": tolerances["limits"], "status": tolerances["status"]},
        "local_source_sha256": {name: digest(SOURCE / name) for name in
                                ("convert.py", "fixture_strategy.py", "run.py", "compare.py",
                                 "mapping-manifest.json", "tolerances.json")
                                if (SOURCE / name).is_file()},
        "inputs": {"data_root": str(args.lean_data), "sha256": conversion["input_hashes"],
                   "decoded": conversion["decoded_inputs"],
                   "price_encoding": conversion["price_encoding"],
                   "volume_encoding": conversion["volume_encoding"],
                   "session_source": conversion["session_source"],
                   "forward_filled_rows": conversion["forward_filled_rows"],
                   "map_rows": conversion["map_rows"]},
        "conversion": conversion["counts"],
        "attribution_evidence": {
            "file": rows_path.name,
            "converted_rows_sha256": digest(rows_path),
            "serialization": "json.dumps(rows, indent=2, sort_keys=True, default=str) + newline",
            "note": "compare.py refuses a --bars file whose digest differs, and re-hashes its own "
                    "re-derivation under --lean-data against this value.",
        },
        "derived_distributions": conversion["distributions"],
        "unsupported_mappings": unsupported_mappings(manifest),
        "runs": [{k: v for k, v in run.items() if k not in ("intents", "fills", "cash_ledger",
                                                            "distribution_ledger", "_raw_reports")}
                 for run in runs],
        "two_run_records_equal": equal,
        "two_run_determinism": determinism,
        "intents": primary["intents"],
        "fills": primary["fills"],
        "cash_ledger": primary["cash_ledger"],
        "distribution_ledger": primary["distribution_ledger"],
        "dividend_cash_usd": primary["dividend_cash_usd"],
        "fees_usd": primary["fees_usd"],
        "native_end_cash_usd": primary["native_end_cash_usd"],
        "reconciled_end_cash_usd": primary["reconciled_end_cash_usd"],
        "final_quantity": primary["final_quantity"],
        "buying_power_events": primary["buying_power_events"],
        "latch_events": primary["latch_events"],
        "buying_power_and_latch_note": "one_zero requests 1x with no leverage and no adaptive rule, so "
                                       "empty lists are the expected observation, not evidence of "
                                       "margin-model equivalence.",
        "isolation": {"network_interfaces": socket.if_nameindex(),
                      "environment_names": sorted(os.environ),
                      "argv": sys.argv, "cwd": os.getcwd()},
        "limitations": [
            "Distribution cash is an external Decimal ledger: the pinned engine posts none of it.",
            "Fill prices use the next session's first-bar close because market-on-open is unsupported.",
            "Bundled sample bytes are not an entitled, point-in-time or market-wide dataset.",
        ],
    }
    save(args.out / "receipt.json", receipt)
    print(json.dumps({"case": CASE["id"], "evidence_class": EVIDENCE_CLASS,
                      "two_run_records_equal": equal,
                      "processed_bars": primary["processed_bars"],
                      "fills": len(primary["fills"]),
                      "dividend_cash_usd": primary["dividend_cash_usd"],
                      "native_end_cash_usd": primary["native_end_cash_usd"],
                      "reconciled_end_cash_usd": primary["reconciled_end_cash_usd"],
                      "unsupported_mappings": receipt["unsupported_mappings"],
                      "receipt": str(args.out / "receipt.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
