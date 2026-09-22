"""Bounded paper lane: preflight, native strategy execution, durable reconciliation.

CLI credentials are loaded only from the explicitly selected private env file.
Default behavior never submits an order; `paper` is an explicit bounded trial.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import time

from safety import Ledger, Quote, RiskLimits, SafetyError, account_lock_fingerprint, DEFAULT_STOP
from strategies import AdaptivePolicy, PolicyConfig, limit_price
from transport import AlpacaPaperTransport, TransportError, RejectedSubmission, preflight

SOURCE = Path(__file__).resolve().parent
LAST_OUTPUT = None


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(data, stream, indent=2, sort_keys=True, default=str)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def credentials(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.removeprefix("export ").split("=", 1)
        if name.strip() in {"APCA_API_KEY_ID", "APCA_API_SECRET_KEY"}:
            values = shlex.split(value, comments=True)
            if len(values) != 1:
                raise ValueError("invalid_scoped_credential")
            result[name.strip()] = values[0]
    if len(result) != 2 or not all(result.values()):
        raise ValueError("missing_paper_credentials")
    return result["APCA_API_KEY_ID"], result["APCA_API_SECRET_KEY"]


def load_config(path):
    c = json.loads(Path(path).read_text())
    if (c["endpoint"] != "https://paper-api.alpaca.markets" or c["feed"] != "iex"
            or c["regular_session_only"] is not True or c["extended_hours_enabled"] is not False
            or c["catalyst_orders_enabled"] is not False or Decimal(c["max_leverage"]) > 1):
        raise ValueError("unqualified_lane_configuration")
    risk = RiskLimits(capital_usd=c["capital_usd"], max_gross_exposure_usd=c["max_gross_exposure_usd"],
                      max_order_notional_usd=c["max_order_notional_usd"], max_order_qty=str(c["max_order_quantity"]),
                      max_gross_loss_usd=c["max_gross_loss_usd"], max_drawdown_usd=c["max_drawdown_usd"],
                      max_spread_bps=c["max_spread_bps"], max_held_symbols=c["max_held_symbols"],
                      max_outstanding_orders=c["max_outstanding_orders"], max_rest_per_minute=c["max_api_requests_per_minute"],
                      max_submits_per_minute=c["max_submit_requests_per_minute"],
                      quote_max_age_seconds=c["quote_max_age_seconds"], trial_seconds=c["duration_seconds"],
                      cleanup_seconds=c["cleanup_seconds"], min_entry_close_seconds=c["min_entry_close_seconds"])
    policy = PolicyConfig(symbols=tuple(c["symbols"]), benchmarks=tuple(c["benchmarks"]),
                          max_positions=c["max_held_symbols"], capital=float(c["capital_usd"]),
                          gross_cap=float(c["max_gross_exposure_usd"]), max_leverage=float(c["max_leverage"]),
                          max_shares=c["max_order_quantity"], max_spread_bps=float(c["max_spread_bps"]),
                          warmup_samples=c["warmup_samples"], warmup_seconds=c["warmup_seconds"],
                          minimum_edge_bps=c["minimum_edge_bps"], quote_age_seconds=c["quote_max_age_seconds"],
                          min_hold_seconds=c["min_hold_seconds"], max_hold_seconds=c["max_hold_seconds"],
                          stop_bps=c["stop_bps"], take_profit_bps=c["take_profit_bps"], trailing_bps=c["trailing_bps"])
    if set(c["strategy_scope"]) != set(AdaptivePolicy.families):
        raise ValueError("unsupported_strategy_scope")
    return c, risk, policy


def public_preflight(observation):
    account = observation["account"]
    return {"observed_at": datetime.now(timezone.utc).isoformat(),
            "endpoint": "https://paper-api.alpaca.markets", "account_status": account.get("status"),
            "capital_available": Decimal(account["cash"]) >= 10000,
            "clock": observation["clock"], "asset_count": len(observation["assets"]),
            "position_count": len(observation["positions"]), "open_order_count": len(observation["orders"]),
            "orders_submitted": 0, "quote_count": len(observation["quotes"]),
            "quote_errors": observation.get("quote_errors", {})}


def validate_preflight(observation, config, *, require_open, allow_existing=False):
    account, clock = observation["account"], observation["clock"]
    if (account.get("status") != "ACTIVE" or account.get("currency") != "USD" or any(account.get(k) is not False for k in
            ("trading_blocked", "account_blocked", "trade_suspended_by_user"))
            or (not allow_existing and (Decimal(account["cash"]) < Decimal(config["capital_usd"])
            or Decimal(account["equity"]) < 25000))):
        raise SafetyError("account_not_ready")
    server = clock["timestamp_ns"] / 1e9
    close = clock["next_close_ns"] / 1e9
    if abs(clock["received_at_ns"] / 1e9 - server) > .25:
        raise SafetyError("clock_drift")
    required_window = 1 if allow_existing else config["duration_seconds"] + config["cleanup_seconds"] + 60
    if require_open and (clock["is_open"] is not True or close - server < required_window):
        raise SafetyError("regular_session_window_unavailable")
    if not allow_existing and (observation["positions"] or observation["orders"]):
        raise SafetyError("clean_native_start_requires_flat_account")
    assets = {a["symbol"]: a for a in observation["assets"]}
    required_assets = {p["symbol"] for p in observation["positions"]} if allow_existing else set(config["symbols"])
    if not required_assets.issubset(assets) or any(assets[s].get("status") != "active" or assets[s].get("tradable") is not True
                                                   for s in required_assets):
        raise SafetyError("universe_not_tradable")
    if require_open and not allow_existing:
        quotes = {q["symbol"]: q for q in observation["quotes"]}
        if any(s not in quotes or not -.25 <= time.time() - quotes[s]["ts_ns"] / 1e9 <= config["quote_max_age_seconds"]
               for s in config["benchmarks"]):
            raise SafetyError("benchmark_quotes_not_ready")
    return close


def reconcile(ledger, snapshot, baseline_cash):
    """Only invoke with admissions stopped and no in-flight submit tasks."""
    if snapshot.get("complete") is not True:
        raise SafetyError("incomplete_snapshot")
    intents = {i.client_id: i for i in ledger.intents()}
    seen = set()
    for order in snapshot["orders"]:
        cid = order["client_order_id"]
        if cid not in intents:
            raise SafetyError("external_order_detected")
        intent = intents[cid]
        if (order["symbol"] != intent.symbol or order["side"] != intent.side
                or Decimal(order["qty"]) != intent.qty):
            raise SafetyError("broker_intent_mismatch")
        ledger.record_order(cid, order["id"], order["status"], order["filled_qty"], order.get("filled_avg_price"),
                            timestamp=order["updated_at_ns"] / 1e9)
        seen.add(cid)
    if any(i.submit_attempted and i.status not in ("not_sent", "broker_refused")
           and i.client_id not in seen for i in ledger.intents()):
        raise SafetyError("submitted_intent_absent")
    actual = {p["symbol"]: Decimal(p["qty"]) for p in snapshot["positions"] if Decimal(p["qty"])}
    expected = {p.symbol: p.qty for p in ledger.positions().values() if p.qty}
    if actual != expected:
        raise SafetyError("position_mismatch")
    cash_delta = Decimal(snapshot["account"]["cash"]) - Decimal(baseline_cash)
    if abs(cash_delta - ledger.accounting().cash_delta_usd) > Decimal("0.01"):
        raise SafetyError("cash_mismatch_or_unmodeled_fees")
    return {"positions_match": True, "cash_match": True, "cash_delta_usd": str(cash_delta),
            "open_orders": len(ledger.unresolved()), "positions": len(expected)}


class Controller:
    def __init__(self, ledger, close, *, market_open, clock=time.time):
        self.ledger, self.close, self.market_open, self.clock = ledger, close, market_open, clock
        self.port = None
        self.quotes = {}
        self.requests = []
        self.events = []
        self.stop = False
        self.defer_until = 0

    async def before_request(self, kind, client_id=None):
        if kind == "data_read":
            return
        deadline = self.clock() + 65
        while self.clock() < deadline:
            if kind == "submit":
                intent = next((i for i in self.ledger.intents() if i.client_id == client_id), None)
                if intent is None:
                    raise SafetyError("submit_without_intent")
                self.ledger.validate_pending(client_id, quote=self.quotes[intent.symbol], now=self.clock(),
                                             market_open=self.market_open, session_close=self.close)
                if intent.side == "buy" and (self.stop or not self.port.ready):
                    raise SafetyError("admissions_not_ready")
            wait = self.ledger.request_budget(self.clock(), kind, client_id=client_id)
            if not wait:
                self.requests.append({"timestamp": self.clock(), "kind": kind})
                return
            if kind == "submit":
                self.defer_until = max(self.defer_until, self.clock() + wait)
                raise SafetyError("submission_rate_deferred")
            await asyncio.sleep(min(wait + .002, 1))
        raise SafetyError("request_budget_wait_exceeded")

    def before_submit(self, order):
        from native_adapter import NativeOrderRejected
        try:
            if order["side"] == "buy" and (self.stop or not self.port.ready):
                raise SafetyError("admissions_not_ready")
            quote = self.quotes.get(order["symbol"])
            if quote is None:
                raise SafetyError("no_current_quote")
            intent = self.ledger.reserve_intent(order["client_order_id"], order["symbol"], order["side"],
                                                order["qty"], order["limit_price"], quote=quote,
                                                now=self.clock(), market_open=self.market_open,
                                                session_close=self.close)
            if not intent.newly_reserved:
                raise SafetyError("duplicate_intent_not_resubmitted")
        except SafetyError as exc:
            raise NativeOrderRejected(str(exc)) from None
        self.events.append({"type": "intent", "client_id": intent.client_id, "symbol": intent.symbol,
                            "side": intent.side, "strategy": order.get("strategy"), "reason": order.get("reason")})

    def observe(self, order):
        known = {i.client_id for i in self.ledger.intents()}
        if order["client_order_id"] not in known:
            self.stop = True
            self.ledger.freeze("external_order_detected")
            raise SafetyError("external_order_detected")
        self.ledger.record_order(order["client_order_id"], order["id"], order["status"], order["filled_qty"],
                                 order.get("filled_avg_price"), timestamp=order["updated_at_ns"] / 1e9)

    def quote(self, quote):
        q = Quote(quote["symbol"], quote["bid"], quote["ask"], quote["ts_ns"] / 1e9)
        old = self.quotes.get(q.symbol)
        if old is None or q.timestamp > old.timestamp:
            self.quotes[q.symbol] = q

    def bind(self, port):
        """Retain proven negative outcomes before native/recovery callbacks."""
        submit = port.submit
        async def observed_submit(order):
            try:
                return await submit(order)
            except Exception as exc:
                intent = next((i for i in self.ledger.intents() if i.client_id == order["client_order_id"]), None)
                if intent and intent.status == "reserved" and intent.broker_id is None and not intent.filled_qty:
                    if getattr(exc, "not_sent", False) is True:
                        self.ledger.mark_not_sent(intent.client_id, "transport_proven_not_sent")
                    elif isinstance(exc, RejectedSubmission):
                        self.ledger.mark_broker_refused(intent.client_id, exc.status_code)
                        self.stop = True
                raise
        port.submit = observed_submit
        return port


async def run_native(controller, policy_config, assets, trial_id, config, baseline_cash, *, account_fingerprint="simulation"):
    from native_adapter import build_node
    from native_strategy import AdaptiveStrategy
    strategy = AdaptiveStrategy(AdaptivePolicy(policy_config), controller.ledger, trial_id,
                                event_sink=controller.events.append)
    # Capture actual streaming quotes before native conversion. Every native
    # strategy event still arrives through the data engine's ordinary path.
    port = controller.port
    start = port.start
    async def start_with_quotes(on_quote, on_order):
        async def quote_sink(q):
            controller.quote(q)
            result = on_quote(q)
            if hasattr(result, "__await__"):
                await result
        return await start(quote_sink, on_order)
    port.start = start_with_quotes
    metadata = [{"symbol": a["symbol"], "price_precision": 2, "price_increment": "0.01", "lot_size": "1"}
                for a in assets]
    session = build_node(port, metadata, [strategy], account_id="ALPACA-PAPER-" + account_fingerprint[:16],
                         max_order_submit_rate="180/00:01:00")
    task = asyncio.create_task(session.run_async())
    started = time.monotonic()
    last_reconciliation = started
    cleanup_started = None
    reconciliation = None
    try:
        while time.monotonic() - started < config["duration_seconds"] + config["cleanup_seconds"]:
            now = time.time()
            if task.done():
                break
            elapsed = time.monotonic() - started
            state = controller.ledger.accounting()
            force_exit = (controller.stop or DEFAULT_STOP.exists() or bool(session.errors)
                          or bool(state.halted_reason) or elapsed >= config["duration_seconds"]
                          or controller.close - now <= config["cleanup_seconds"])
            if force_exit and cleanup_started is None:
                cleanup_started = time.monotonic()
            # A connection or integrity gap ends this bounded run. Quote silence
            # pauses admissions; it requires a fresh reconciled snapshot to thaw.
            health = getattr(port, "health", {})
            serious_gap = any("stale" not in str(reason) for reason in health.get("reasons", []))
            if strategy.started and serious_gap:
                controller.stop = True
                force_exit = True
            strategy.enabled = (strategy.started and port.ready and not force_exit
                                and now >= controller.defer_until)
            fresh_quotes = [q for q in controller.quotes.values()
                            if -.25 <= now - q.timestamp <= config["quote_max_age_seconds"]]
            try:
                controller.ledger.mark_to_market(fresh_quotes, now)
            except SafetyError as exc:
                strategy.enabled = False
                if str(exc) != "held_position_mark_stale":
                    controller.stop = True
                    force_exit = True
            if (strategy.started and not force_exit and time.monotonic() - last_reconciliation >= 30
                    and not controller.ledger.unresolved() and not strategy.pending):
                strategy.enabled = False
                snapshot = await port.snapshot()
                reconcile(controller.ledger, snapshot, baseline_cash)
                if health.get("fresh_quotes") and hasattr(port, "mark_reconciled"):
                    port.mark_reconciled()
                last_reconciliation = time.monotonic()
            if strategy.started:
                strategy.cancel_expired(now, config["order_timeout_seconds"], all_entries=force_exit)
                strategy.rebalance(now, force_exit=force_exit)
            if force_exit and not controller.ledger.unresolved() and not controller.ledger.positions() and not strategy.pending:
                break
            await asyncio.sleep(.1)
        strategy.enabled = False
        controller.stop = True
        # Native lifecycle has to settle before a read-only final comparison.
        if not controller.ledger.unresolved() and not strategy.pending:
            snap = await port.snapshot()
            reconciliation = reconcile(controller.ledger, snap, baseline_cash)
    finally:
        strategy.enabled = False
        controller.stop = True
        session.stop()
        try:
            await asyncio.wait_for(task, 20)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await port.stop()
    state = asdict(controller.ledger.accounting())
    return {"engine": "NautilusTrader LiveNode 2.0.0rc5", "native_quotes": strategy.received_quotes,
            "native_fill_events": strategy.native_fills, "native_rejections": strategy.native_rejections,
            "policy_selections": strategy.policy.counts, "accounting": state,
            "reconciliation": reconciliation, "adapter_errors": list(session.errors),
            "flat": not controller.ledger.positions() and not controller.ledger.unresolved(),
            "requests": controller.requests, "events": controller.events,
            "elapsed_seconds": time.monotonic() - started,
            "status": ("passed" if strategy.native_fills else "completed_no_signals")
                      if reconciliation and reconciliation["positions"] == 0
                      and reconciliation["open_orders"] == 0 and not session.errors else "needs_attention"}


def main():
    global LAST_OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "paper", "recover"])
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=SOURCE / "config.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trial", default="adaptive-20260921")
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STOP.parent)
    args = parser.parse_args()
    LAST_OUTPUT = args.output
    if not re.fullmatch(r"[a-z0-9-]{1,24}", args.trial):
        raise ValueError("invalid_trial_id")
    config, limits, policy_config = load_config(args.config)
    key, secret = credentials(args.env_file)
    attempts, responses = [], []
    def observe_request(kind, **kwargs):
        attempts.append({"timestamp": time.time(), "kind": kind})
        if len(attempts) > 50:
            raise SafetyError("preflight_request_bound")
    try:
        observation = preflight(key, secret, config["symbols"], before_request=observe_request,
                                request_observer=responses.append)
    except TransportError as exc:
        result = {"status": "not_started", "stage": "preflight", "reason": str(exc),
                  "orders_submitted": 0, "http": responses, "attempts": attempts}
        save(args.output, result)
        print(json.dumps({k: result[k] for k in ("status", "stage", "reason", "orders_submitted")}))
        return 2
    summary = public_preflight(observation)
    summary["http"] = responses
    summary["config_sha256"] = hashlib.sha256(args.config.read_bytes()).hexdigest()
    if args.command == "preflight":
        try:
            validate_preflight(observation, config, require_open=True)
            summary["status"] = "ready"
        except SafetyError as exc:
            summary.update(status="not_ready", reason=str(exc))
        save(args.output, summary)
        print(json.dumps({k: summary[k] for k in ("status", "orders_submitted")}, default=str))
        return 0 if summary["status"] == "ready" else 2
    try:
        close = validate_preflight(observation, config, require_open=True, allow_existing=args.command == "recover")
    except SafetyError as exc:
        summary.update(status="not_started", reason=str(exc))
        save(args.output, summary)
        print(json.dumps({"status": "not_started", "reason": str(exc), "orders_submitted": 0}))
        return 2
    fingerprint = observation["account_identity_sha256"]
    with account_lock_fingerprint(fingerprint):
        state_dir = args.state_root / fingerprint / "adaptive"
        metadata_path = state_dir / "trial.json"
        previous_metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else None
        if previous_metadata and args.command != "recover" and previous_metadata.get("phase") != "finished":
            raise SafetyError("existing_trial_requires_explicit_recovery")
        if args.command == "recover" and not metadata_path.exists():
            raise SafetyError("no_owned_trial_to_recover")
        ledger = Ledger(state_dir / "ledger.sqlite3", limits)
        try:
            now = time.time()
            for attempt in attempts:
                if attempt["kind"] != "data_read":
                    if ledger.request_budget(attempt["timestamp"], "read"):
                        raise SafetyError("preflight_budget_inconsistent")
            controller = Controller(ledger, close, market_open=True)
            if args.command == "recover":
                metadata = previous_metadata
                if metadata["config_sha256"] != summary["config_sha256"]:
                    raise SafetyError("recovery_config_differs_from_frozen_trial")
            else:
                if previous_metadata:
                    if previous_metadata["config_sha256"] != summary["config_sha256"]:
                        raise SafetyError("next_trial_config_differs_from_frozen_limits")
                    if ledger.positions() or ledger.unresolved():
                        raise SafetyError("next_trial_requires_recovery")
                    expected_cash = Decimal(previous_metadata["baseline_cash"]) + ledger.accounting().cash_delta_usd
                    if abs(Decimal(observation["account"]["cash"]) - expected_cash) > Decimal("0.01"):
                        raise SafetyError("next_trial_cash_mismatch")
                ledger.begin_next_trial(now, args.trial)
                metadata = {"trial_id": args.trial,
                            "started_at": previous_metadata["started_at"] if previous_metadata else now,
                            "current_trial_started_at": now, "config_sha256": summary["config_sha256"],
                            "baseline_cash": previous_metadata["baseline_cash"] if previous_metadata else observation["account"]["cash"],
                            "phase": "starting"}
                save(metadata_path, metadata)
            def fresh_port(recovering=False):
                needed = sorted(set(ledger.positions()) | {i.symbol for i in ledger.unresolved()})
                return controller.bind(AlpacaPaperTransport(key, secret, config["symbols"],
                    before_request=controller.before_request, before_submit=controller.before_submit,
                    sink_observation=controller.observe, request_observer=responses.append,
                    quote_timeout=config["quote_max_age_seconds"],
                    required_quote_symbols=needed if recovering and needed else config["benchmarks"],
                    history_start=datetime.fromtimestamp(metadata["started_at"], timezone.utc)))
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, lambda *_: setattr(controller, "stop", True))
            async def execute():
                from recovery import recover
                if args.command == "recover":
                    controller.port = fresh_port(True)
                    return await recover(controller, metadata, config)
                controller.port = fresh_port()
                try:
                    outcome = await run_native(controller, policy_config, observation["assets"], args.trial,
                                               config, metadata["baseline_cash"], account_fingerprint=fingerprint)
                except Exception as exc:
                    outcome = {"status": "needs_attention", "flat": False, "native_fill_events": 0,
                               "error_type": type(exc).__name__}
                if ledger.positions() or ledger.unresolved():
                    controller.stop = True
                    controller.port = fresh_port(True)
                    recovery = await recover(controller, metadata, config)
                    outcome["recovery"] = recovery
                    outcome["flat"] = recovery["flat"]
                return outcome
            result = asyncio.run(execute())
            result.update(preflight=summary, mode="adaptive_paper", config_sha256=summary["config_sha256"])
            metadata["phase"] = "finished" if result.get("flat") else "needs_attention"
            metadata["status"] = result["status"]
            save(metadata_path, metadata)
            save(args.output, result)
            print(json.dumps({k: result.get(k) for k in ("status", "flat", "native_fill_events")}, default=str))
            return 0 if result["status"] in ("passed", "completed_no_signals") else 3
        finally:
            ledger.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Never serialize arbitrary provider exception text or request headers.
        failure = {"status": "failed", "error_type": type(exc).__name__,
                   "reconciliation": "not_established"}
        if LAST_OUTPUT is not None:
            save(LAST_OUTPUT, failure)
        print(json.dumps(failure))
        raise SystemExit(3)
