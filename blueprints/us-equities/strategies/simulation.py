"""Synthetic T22 engineering acceptance through the unchanged native rc5 engine.

No provider, broker or historical acquisition surface. Fixtures are declarative
CustomData plus QuoteTick. Source: native BacktestEngine custom-data and surface
tests at nautilus_trader@1b0a49d2792a9432a3aca3fcb617ce7a630d905e.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from nautilus_trader.backtest import BacktestEngine, BacktestEngineConfig
from nautilus_trader.execution import OneTickSlippageFillModel, StaticLatencyModel
from nautilus_trader.model import (
    AccountType,
    Currency,
    CustomData,
    Equity,
    InstrumentId,
    Money,
    OmsType,
    Price,
    Quantity,
    QuoteTick,
    Symbol,
    Venue,
)

from .contracts import FactorSnapshot, StrategySpec, digest
from .families import CONTROLS, FAMILIES, snapshot_data_type
from .presets import EXIT_POLICIES, PRESETS

BASE_NS = int(datetime(2026, 10, 8, 13, 35, tzinfo=timezone.utc).timestamp() * 1e9)
INSTRUMENT_ID = "TST.ALPACA"
COHORT_SHA256 = digest({"protocol": "t22-synthetic-v1", "members": [INSTRUMENT_ID]})
D = Decimal

POSITIVE_FACTORS = {
    "atr_price": "0.2",
    "entry_trigger": "10",
    "structure_low": "9.7",
    "fda_decision": "1",
    "catalyst_confirmation": "1",
    "price_confirmation": "1",
    "relative_volume": "3",
    "overnight_gap": "0.05",
    "premarket_return": "0.05",
    "premarket_activity": "2",
    "float_turnover": "1.2",
    "float_flip_clock": "30",
    "short_interest": "0.3",
    "days_to_cover": "3",
    "fails_to_deliver": "100",
    "borrow_fee": "0.2",
    "momentum_20": "0.1",
    "range_breakout": "1.02",
    "tight_range_state": "0.02",
    "option_volume_surge": "3",
    "gamma_exposure_proxy": "1",
    "expiry_concentration": "0.7",
    "halt_event": "1",
    "halt_reopen_liquidity": "1",
    "halt_pause_density": "1",
    "reopen_bid_print": "1",
    "reopen_ask_print": "1",
    "earnings": "1",
    "trend_state": "0.1",
    "relative_strength": "0.05",
    "at_all_time_closing_high": "1",
    "momentum_5": "-0.05",
}


def fixture_snapshot(*, values=None, member=True, halted=False, ts_init=None):
    values = POSITIVE_FACTORS if values is None else values
    available = BASE_NS - 600_000_000_000 if ts_init is None else ts_init
    source = digest(
        {
            "fixture": "t22-synthetic-v1",
            "values": values,
            "available_ns": available,
            "member": member,
            "halted": halted,
        }
    )
    return FactorSnapshot(
        INSTRUMENT_ID,
        COHORT_SHA256,
        source,
        available,
        available,
        BASE_NS + 7200_000_000_000,
        tuple(sorted(values.items())),
        cohort_member=member,
        halted=halted,
        expiry_ns=BASE_NS + 86400_000_000_000,
    )


def fixture_quotes(
    instrument,
    *,
    start_ns=BASE_NS,
    bids=(
        "10",
        "10",
        "10.1",
        "10.15",
        "10.15",
        "10.1",
        "10",
        "9.9",
        "9.8",
        "9.7",
        "9.6",
        "9.6",
        "9.6",
        "9.6",
        "9.6",
        "9.6",
    ),
):
    result = []
    for i, raw in enumerate(bids):
        bid = D(raw)
        ts = start_ns + i * 1_000_000_000
        result.append(
            QuoteTick(
                instrument.id,
                Price.from_decimal_dp(bid, 4),
                Price.from_decimal_dp(bid + D("0.01"), 4),
                Quantity.from_int(100),
                Quantity.from_int(100),
                ts,
                ts,
            )
        )
    return result


def fixture_engine(instrument=None):
    """Shared native synthetic venue/instrument for acceptance regressions."""
    currency = Currency.from_str("USD")
    if instrument is None:
        instrument = Equity(
            InstrumentId.from_str(INSTRUMENT_ID),
            Symbol("TST"),
            currency,
            price_precision=4,
            price_increment=Price.from_str("0.0001"),
            lot_size=Quantity.from_int(1),
            ts_event=0,
            ts_init=0,
        )
    engine = BacktestEngine(
        BacktestEngineConfig(bypass_logging=True, run_analysis=False)
    )
    engine.add_venue(
        Venue("ALPACA"),
        OmsType.NETTING,
        AccountType.CASH,
        starting_balances=[Money.from_str("10000 USD")],
        base_currency=currency if isinstance(instrument, Equity) else None,
        fill_model=OneTickSlippageFillModel(
            prob_fill_on_limit=1.0, prob_slippage=1.0, random_seed=22
        ),
        latency_model=StaticLatencyModel(base_latency_nanos=1_000_000),
    )
    engine.add_instrument(instrument)
    return engine, instrument


def run_case(
    family,
    preset="conservative-v1",
    *,
    snapshot=None,
    start_ns=BASE_NS,
    bids=None,
    spec_overrides=None,
    advance_to_ns=None,
    ledger=None,
):
    """Small native backtest, returning engineering fields without P&L statistics."""
    if importlib.metadata.version("nautilus-trader") != "2.0.0rc5":
        raise ValueError("unqualified_native_version")
    engine, instrument = fixture_engine()
    overrides = {
        "entry_deadline_ns": start_ns + 5_000_000_000,
        "exit_deadline_ns": start_ns + 8_000_000_000,
        "entry_timeout_ns": 2_000_000_000,
        "exit_timeout_ns": 2_000_000_000,
    }
    overrides.update(spec_overrides or {})
    spec = replace(
        StrategySpec(INSTRUMENT_ID, COHORT_SHA256, preset=preset), **overrides
    )
    cls = (FAMILIES | CONTROLS)[family]
    strategy = cls(spec, ledger=ledger)
    snapshot = fixture_snapshot() if snapshot is None else snapshot
    quotes = fixture_quotes(
        instrument, start_ns=start_ns, **({"bids": bids} if bids is not None else {})
    )
    engine.add_strategy(strategy)
    data = [CustomData(snapshot_data_type(INSTRUMENT_ID), snapshot), *quotes]
    if advance_to_ns is not None:
        heartbeat = replace(
            snapshot,
            ts_event=advance_to_ns,
            ts_init=advance_to_ns,
            valid_until_ns=max(snapshot.valid_until_ns, advance_to_ns),
        )
        data.append(CustomData(snapshot_data_type(INSTRUMENT_ID), heartbeat))
    engine.add_data(data, sort=True)
    fixture_hash = digest(
        {
            "snapshot": snapshot.as_dict(),
            "quotes": [
                {
                    "ts_event": q.ts_event,
                    "bid": str(q.bid_price),
                    "ask": str(q.ask_price),
                }
                for q in quotes
            ],
            "spec": {k: str(v) for k, v in spec.__dict__.items()},
            "advance_to_ns": advance_to_ns,
        }
    )
    try:
        engine.run()
        result = engine.get_result()
        orders = engine.generate_orders_report()
        record = {
            "family": family,
            "class": cls.__name__,
            "preset": preset,
            "exit_policy": spec.exit_policy,
            "execution_profile": spec.execution_profile,
            "evidence_class": "synthetic",
            "fixture_sha256": fixture_hash,
            "trace_sha256": digest(strategy.trace),
            "iterations": result.iterations,
            "orders": result.total_orders,
            "fill_callbacks": sum(row["event"] == "fill" for row in strategy.trace),
            "owned_quantity": str(strategy.quantity),
            "pending": strategy.pending is not None,
            "sequence": strategy.sequence,
            "strategy_id": str(strategy.strategy_id),
            "order_id_tag": strategy.config.order_id_tag,
            "callback_faults": strategy.callback_faults,
            "flags": sorted(strategy.flags),
            "trace": strategy.trace,
            "native_order_types": sorted(set(orders["type"].astype(str)))
            if len(orders)
            else [],
        }
        record["passed"] = (
            not strategy.callback_faults
            and not strategy.faulted
            and strategy.quantity == 0
            and strategy.pending is None
        )
        return record
    finally:
        engine.dispose()


def run_matrix():
    records = [run_case(family, preset) for family in FAMILIES for preset in PRESETS]
    # Accelerated deadlines exercise native mechanics only; real multi-session
    # timing and qualification are covered separately by regression/evidence.
    measured = [
        run_case(family, preset, spec_overrides={"exit_policy": policy})
        for family in FAMILIES
        for preset in PRESETS
        for policy in EXIT_POLICIES
    ]
    controls = [run_case(control) for control in CONTROLS]
    inverse = [
        run_case(family, snapshot=fixture_snapshot(member=False)) for family in FAMILIES
    ]
    for row in records + measured:
        row["passed"] = row["passed"] and row["fill_callbacks"] >= 2
    for row in inverse:
        row["passed"] = row["passed"] and row["orders"] == 0
    for row in controls:
        if row["family"] == "control_no_trade":
            row["passed"] = row["passed"] and row["orders"] == 0
    return {
        "schema_version": 1,
        "kind": "t22_strategy_synthetic_receipt",
        "status": "passed"
        if all(r["passed"] for r in records + measured + controls + inverse)
        else "failed",
        "evidence_class": "synthetic",
        "historical_layer15_e2e": "NOT_RUN",
        "historical_exit_timing": "NOT_RUN",
        "strategy_performance": "NOT_CITED",
        "paper_adoption": "NOT_RUN",
        "engine": {
            "repository": "nautechsystems/nautilus_trader",
            "version": "2.0.0rc5",
            "sha": "1b0a49d2792a9432a3aca3fcb617ce7a630d905e",
            "fill_model": "OneTickSlippageFillModel",
            "random_seed": 22,
            "prob_fill_on_limit": "1.0",
            "prob_slippage": "1.0",
            "latency_model": "StaticLatencyModel",
            "base_latency_nanos": 1_000_000,
        },
        "families": records,
        "measured_exit_candidates": measured,
        "controls": controls,
        "inverse_noncohort": inverse,
        "source_sha256": {
            f.name: hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(
                [
                    *Path(__file__).parent.glob("*.py"),
                    Path(__file__).parent / "registry.json",
                ]
            )
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_matrix()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "path": str(args.output),
                "evidence_class": "synthetic",
                "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
            }
        )
    )
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
