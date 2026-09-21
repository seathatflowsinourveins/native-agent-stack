"""Explicit bounded broker recovery; no strategy restart and no new buys."""
from __future__ import annotations

import asyncio
from decimal import Decimal, ROUND_DOWN
import re
import time

from safety import SafetyError


def _payload(intent):
    return {"client_order_id": intent.client_id, "symbol": intent.symbol,
            "side": intent.side, "qty": format(intent.qty, "f"),
            "limit_price": format(intent.limit_price, "f"), "type": "limit",
            "time_in_force": "day", "extended_hours": False}


def _code(exc):
    text = str(exc)
    return text if isinstance(exc, SafetyError) and re.fullmatch(r"[a-z_]{1,100}", text) else type(exc).__name__


async def recover(controller, metadata, config, *, reconcile_fn=None):
    """Reconcile/cancel/exit owned residuals using a fresh, unstarted port.

    The caller holds the account writer lock and validates account/config identity.
    ``metadata`` supplies the original ``trial_id`` and ``baseline_cash``. The
    normal reconciler is runner.reconcile; injection supports isolated local tests.
    All broker requests still cross controller/transport durable budget gates.
    """
    if reconcile_fn is None:
        from runner import reconcile as reconcile_fn
    ledger, port = controller.ledger, controller.port
    controller.stop = True
    changed = asyncio.Event()
    cleanup = min(float(config["cleanup_seconds"]), float(ledger.limits.cleanup_seconds), 120.0)
    if not 0 < cleanup <= 120:
        raise SafetyError("invalid_recovery_deadline")
    deadline = time.monotonic() + cleanup
    trial = metadata["trial_id"]
    if not isinstance(trial, str) or not re.fullmatch(r"[a-z0-9-]{1,24}", trial):
        raise SafetyError("invalid_trial_id")
    prefix = "rec-" + trial + "-"
    sequence = max((int(i.client_id[len(prefix):]) for i in ledger.intents()
                    if i.client_id.startswith(prefix) and i.client_id[len(prefix):].isdigit()), default=0)
    errors, cancelled, submitted = [], [], []
    last_snapshot = None
    proof = None

    def quote(row):
        controller.quote(row)
        changed.set()

    def order(row):
        controller.observe(row)
        changed.set()

    async def bounded(operation):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            operation.close()  # Do not start a broker operation after the deadline.
            raise SafetyError("recovery_deadline_reached")
        timeout = asyncio.timeout(remaining)
        try:
            async with timeout:
                return await operation
        except asyncio.TimeoutError:
            if timeout.expired():
                raise SafetyError("recovery_deadline_reached") from None
            raise  # A broker TimeoutError is an ambiguous operation, not our timer.

    async def observe_snapshot():
        nonlocal last_snapshot, proof
        last_snapshot = await bounded(port.snapshot())
        proof = reconcile_fn(ledger, last_snapshot, metadata["baseline_cash"])
        return proof

    async def wait_for(predicate, seconds):
        until = min(deadline, time.monotonic() + seconds)
        while not predicate():
            changed.clear()
            if predicate():
                return True
            remaining = until - time.monotonic()
            if remaining <= 0:
                return False
            try:
                await asyncio.wait_for(changed.wait(), remaining)
            except asyncio.TimeoutError:
                return bool(predicate())
        return True

    async def cancel(client_id):
        guard_observation_integrity()
        confirmation = await bounded(port.cancel(client_id))
        cancelled.append(client_id)
        if confirmation is not None:
            order(confirmation)

    def terminal(client_ids):
        return not any(i.client_id in client_ids for i in ledger.unresolved())

    def fresh(symbol):
        value = controller.quotes.get(symbol)
        return value is not None and -0.25 <= controller.clock() - value.timestamp <= min(
            float(config["quote_max_age_seconds"]), ledger.limits.quote_max_age_seconds)

    def guard_observation_integrity():
        # Reconnect/stale-quote admission freezes can coexist with an owned exit
        # using a fresh quote. Event loss/identity conflicts cannot: a stream sink
        # may detect these before invoking our order callback.
        reasons = set(getattr(port, "health", {}).get("reasons", []))
        if reasons & {"callback_failure", "queue_overflow", "client_id_collision",
                      "snapshot_incomplete", "replay_unresolved"}:
            raise SafetyError("recovery_observation_integrity_lost")

    try:
        ledger.begin_recovery(controller.clock())
        for intent in ledger.intents():
            if (intent.status == "reserved" and not intent.submit_attempted
                    and intent.broker_id is None and not intent.filled_qty):
                # The durable HTTP budget marks attempted *before* any POST. No
                # attempted request is ever retired based on a missing lookup.
                ledger.mark_not_sent(intent.client_id, "recovery_proven_never_attempted")
        port.adopt_intents([_payload(i) for i in ledger.intents() if i.status != "not_sent"])
        await bounded(port.start(quote, order))
        await observe_snapshot()  # Unknown exposure/absent attempted IDs stop here.
        outstanding = {i.client_id for i in ledger.unresolved()}
        for client_id in sorted(outstanding):
            await cancel(client_id)
        if outstanding:
            if not await wait_for(lambda: terminal(outstanding), float(config["order_timeout_seconds"])):
                raise SafetyError("cancellation_not_confirmed")
            await observe_snapshot()
        if ledger.unresolved():
            raise SafetyError("unresolved_orders_block_exit")
        # Sequential closes prevent overselling and leave capacity for cancels and
        # reconciliation. A terminal partial cancel must be snapshotted again.
        while ledger.positions():
            guard_observation_integrity()
            if len(submitted) >= 100:
                raise SafetyError("recovery_order_bound_reached")
            symbol, position = sorted(ledger.positions().items())[0]
            if not controller.market_open or controller.close - controller.clock() <= 1:
                raise SafetyError("outside_allowed_session")
            if not await wait_for(lambda: fresh(symbol), float(config["quote_max_age_seconds"])):
                raise SafetyError("recovery_quote_not_fresh")
            bid = controller.quotes[symbol].bid
            price = (bid - Decimal("0.02")).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            if price <= 0:
                raise SafetyError("recovery_price_not_positive")
            capacity = (ledger.limits.max_order_notional_usd / price).quantize(
                Decimal("0.000000001"), rounding=ROUND_DOWN)
            quantity = min(position.qty, ledger.limits.max_order_qty, capacity)
            if quantity <= 0 or quantity.as_tuple().exponent < -9:
                raise SafetyError("recovery_quantity_not_representable")
            sequence += 1
            client_id = prefix + f"{sequence:07d}"
            payload = {"client_order_id": client_id, "symbol": symbol, "side": "sell",
                       "qty": format(quantity, "f"), "limit_price": format(price, "f"),
                       "type": "limit", "time_in_force": "day", "extended_hours": False,
                       "strategy": "recovery", "reason": "owned_residual_exit"}
            submitted.append(client_id)
            try:
                guard_observation_integrity()
                confirmation = await bounded(port.submit(payload))
                order(confirmation)
            except Exception as exc:
                if getattr(exc, "definitive_rejection", False) is True:
                    intent = next((i for i in ledger.intents() if i.client_id == client_id), None)
                    if intent and intent.status == "reserved" and not intent.filled_qty and intent.broker_id is None:
                        ledger.mark_not_sent(client_id, "recovery_definitive_refusal")
                raise
            if not await wait_for(lambda: terminal({client_id}), float(config["order_timeout_seconds"])):
                await cancel(client_id)
                if not await wait_for(lambda: terminal({client_id}), float(config["order_timeout_seconds"])):
                    raise SafetyError("exit_cancellation_not_confirmed")
            intent = next(i for i in ledger.intents() if i.client_id == client_id)
            if intent.status != "filled":
                await observe_snapshot()
                if not intent.filled_qty:
                    raise SafetyError("exit_unfilled_no_blind_retry")
        await observe_snapshot()  # A fresh broker proof is required even if already flat.
    except asyncio.CancelledError:
        errors.append("recovery_cancelled")
    except Exception as exc:
        errors.append(_code(exc))
    finally:
        controller.stop = True
        try:
            # Teardown can outlive the order deadline, but cannot authorize orders.
            await asyncio.wait_for(port.stop(), 10)
        except Exception as exc:
            errors.append("stop_" + _code(exc))
    positions = [{"symbol": p.symbol, "qty": format(p.qty, "f")} for p in ledger.positions().values()]
    unresolved = [{"client_id": i.client_id, "symbol": i.symbol, "side": i.side,
                   "status": i.status, "qty": format(i.qty, "f"), "filled_qty": format(i.filled_qty, "f"),
                   "submit_attempted": i.submit_attempted} for i in ledger.unresolved()]
    flat = (not positions and not unresolved and proof is not None and not errors
            and proof["positions"] == 0 and proof["open_orders"] == 0)
    return {"mode": "official_sdk_recovery", "native_engine_resumed": False,
            "status": "passed" if flat else "needs_attention", "flat": flat,
            "errors": errors, "positions": positions, "unresolved_orders": unresolved,
            "broker_positions_last_observed": None if last_snapshot is None else
                [{"symbol": p["symbol"], "qty": str(p["qty"])} for p in last_snapshot["positions"]],
            "reconciliation": proof, "cancel_attempt_client_ids": cancelled,
            "exit_attempt_client_ids": submitted, "buy_submissions": 0,
            "order_deadline_seconds": cleanup}
