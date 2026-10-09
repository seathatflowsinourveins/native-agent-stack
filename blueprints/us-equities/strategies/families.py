"""Nautilus rc5 Strategy classes for ten registered, untested T22 hypotheses.

Engine facilities are upstream; exits, calendar and callback guards are reused
from adaptive-paper. ``code-managed-limit-v1`` is an explicit simple-order
variant. ``native-target-v1`` refuses until T15 supplies the separately accepted
advanced-order path. Neither name claims acceptance of a broker order class.
"""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from types import MappingProxyType, SimpleNamespace

from nautilus_trader.model import (
    ClientOrderId,
    DataType,
    Equity,
    InstrumentId,
    OrderSide,
    Price,
    Quantity,
    StrategyId,
    TimeInForce,
)
from nautilus_trader.trading import Strategy, StrategyConfig

from .contracts import FactorSnapshot, StrategySpec, decimal, digest
from .presets import FAMILY_FACTORS, REQUIRED_QUALIFICATIONS, preset_for

_adapter = importlib.import_module(
    "blueprints.us-equities.adaptive-paper.native_adapter"
)
_exits = importlib.import_module("blueprints.us-equities.adaptive-paper.exits")
_sessions = importlib.import_module("blueprints.us-equities.adaptive-paper.sessions")
guarded_callback = _adapter.guarded_callback
D = Decimal
BPS = D("10000")


def snapshot_data_type(instrument_id: str):
    return DataType("FactorSnapshot", {"protocol": "t22-factors-v1"}, instrument_id)


class FamilyStrategy(Strategy):
    """One entry attempt, one in-flight order and exact owned-fill accounting.

    The caller injects snapshots through the native CustomData/on_data boundary;
    no data provider, universe selection or study outputs are queried here.
    LiveNode uses this same class. Its account governor remains the final order
    gate and every submit/cancel traverses native risk/execution and that governor.
    """

    FAMILY = "abstract"

    def __new__(cls, spec, *, ledger=None, fault_sink=None):
        # The rc5 PyO3 allocator accepts only its native config argument;
        # Python-only injected dependencies belong to this subclass's __init__.
        return super().__new__(cls)

    def __init__(self, spec: StrategySpec, *, ledger=None, fault_sink=None):
        self.spec = spec
        self.preset = preset_for(
            spec.preset, self.FAMILY, spec.catalyst_kind, exit_policy=spec.exit_policy
        )
        # rc5 checks the last StrategyId segment for uniqueness, not just
        # config.order_id_tag (crates/system/src/trader.rs:566-578 at 1b0a49d2).
        # A stable explicit instance name distinguishes otherwise identical
        # deployments; one identity must never run twice in the same trader.
        identity = [
            "t22-instance-v1",
            self.FAMILY,
            spec.preset,
            spec.instance_id,
            spec.instrument_id,
            spec.execution_profile,
            spec.cohort_sha256,
        ]
        if spec.exit_policy is not None:
            identity[0] = "t22-instance-v2"
            identity.extend([spec.exit_policy, spec.exit_evidence_sha256])
        self.instance_tag = digest(identity)[:24]
        self.client_id_prefix = "t22-" + self.instance_tag + "-"
        self.sequence = 0
        super().__init__(
            StrategyConfig(
                strategy_id=StrategyId("T22-" + self.instance_tag),
                order_id_tag=self.instance_tag,
                log_events=False,
                log_commands=False,
            )
        )
        self.instrument_id = InstrumentId.from_str(spec.instrument_id)
        self.snapshot = None
        self.last_quote = None
        self.trace = []
        self.flags = set()
        self.callback_faults = []
        self.faulted = False
        self.enabled = True
        self.fault_sink = fault_sink
        self._durable_ledger_supplied = ledger is not None
        self.ledger = (
            ledger
            if ledger is not None
            else SimpleNamespace(
                freeze=lambda reason: None,
                intents=lambda: (),
                unresolved=lambda: (),
                positions=dict,
                halted_reason=lambda: None,
            )
        )
        self.entry_attempted = False
        self.pending = None
        self.pending_role = None
        self.pending_remaining = D(0)
        self.pending_since_ns = 0
        self.cancel_requested = False
        self.cancel_requested_ns = 0
        self.quantity = D(0)
        self.entry_price = D(0)
        self.entry_atr = D(0)
        self.stop_distance = D(0)
        self.high_bid = D(0)
        self.entered_ns = None
        self.close_deadline_ns = None
        self.expiry_deadline_ns = None
        self.take_profit_done = False
        self.exit_reason = None
        self.exit_remaining = D(0)
        self.exit_orders = 0
        self.seen_fills = set()

    def _freeze(self, reason):
        self.faulted = True
        self.enabled = False
        self.flags.add(reason)
        # Match native_adapter.record_callback_fault's guarantee: attempt the
        # durable halt and session escalation independently, even if one fails.
        errors = {}
        try:
            self.ledger.freeze(reason.lower())
        except Exception as error:  # noqa: BLE001 -- still attempt the independent session stop
            errors["freeze_error"] = type(error).__name__
        if self.fault_sink is not None:
            try:
                self.fault_sink(reason)
            except Exception as error:  # noqa: BLE001 -- preserve both cleanup outcomes without raw errors
                errors["stop_error"] = type(error).__name__
        self._record("safety_freeze", reason=reason, **errors)
        if errors:
            self.callback_faults.append(
                {"callback": "safety_freeze", "freeze_reason": reason, **errors}
            )

    def _record(self, event, **fields):
        self.trace.append(
            {"event": event, "now_ns": self.clock.timestamp_ns(), **fields}
        )

    def _fault(self, name, error):
        _adapter.record_callback_fault(
            self, name, "strategy_callback_exception_" + name, error
        )

    def on_start(self):
        if self.spec.execution_profile == "native-target-v1":
            self._freeze("T15_native_order_capability_unqualified")
            self._record("capability_refused", profile=self.spec.execution_profile)
            return
        instrument = self.cache.instrument(self.instrument_id)
        if instrument is None:
            self._freeze("startup_instrument_not_registered")
            return
        if not isinstance(instrument, Equity):
            self._freeze("equity_instrument_required")
            self._record("capability_refused", reason="non_equity_instrument")
            return
        if (
            self.spec.evidence_class != "synthetic"
            and not self._durable_ledger_supplied
        ):
            self._freeze("startup_durable_ledger_required")
            return
        try:
            if not self._restore_ledger():
                return
        except Exception as error:
            # Never guess flatness or reset a sequence when journal reads fail.
            self._freeze("startup_ledger_read_failed_requires_reconciliation")
            self._record(
                "startup_refused",
                reason="ledger_read_failed",
                error_type=type(error).__name__,
            )
            self._fault("on_start", error)
            raise
        self.subscribe_quotes(self.instrument_id)
        self.subscribe_data(snapshot_data_type(self.spec.instrument_id))
        self.clock.set_timer(
            "t22-watchdog", timedelta(seconds=1), callback=self._on_watchdog
        )

    def _restore_ledger(self):
        """Restore identifiers; dirty startup requires the existing recovery path.

        Reuse adaptive-paper/native_strategy.py's ledger-intents max-sequence
        contract. No ambiguous order is retried here and no existing position is
        adopted as flat. The wire governor still journals each explicit ID
        before any broker request.
        """
        symbol = str(self.instrument_id.symbol)
        own = [
            i
            for i in self.ledger.intents()
            if i.client_id.startswith(self.client_id_prefix)
        ]
        sequences = [i.client_id[len(self.client_id_prefix) :] for i in own]
        if any(
            len(value) != 7
            or not value.isascii()
            or not value.isdigit()
            or int(value) < 1
            for value in sequences
        ):
            raise ValueError("malformed_owned_client_id")
        self.sequence = max((int(value) for value in sequences), default=0)
        if any(i.side == "buy" for i in own):
            # Each registered instance makes one entry attempt across restart,
            # including a terminal pre-wire refusal; a new trial needs its own
            # explicit instance identity, not an implicit reset.
            self.entry_attempted = True
            self.flags.add("prior_entry_attempt_restored")
        unresolved = self.ledger.unresolved()
        position = self.ledger.positions().get(symbol)
        reasons = []
        if self.ledger.halted_reason() is not None:
            reasons.append("startup_ledger_halted_requires_reconciliation")
        if any(
            i.symbol == symbol or i.client_id.startswith(self.client_id_prefix)
            for i in unresolved
        ):
            reasons.append("startup_unresolved_intent_requires_reconciliation")
        if position is not None and decimal(str(position.qty)) != 0:
            reasons.append("startup_position_requires_reconciliation")
        if self.cache.orders_open(instrument_id=self.instrument_id):
            reasons.append("startup_cached_order_requires_reconciliation")
        if self.cache.positions_open(instrument_id=self.instrument_id):
            reasons.append("startup_cached_position_requires_reconciliation")
        self._record(
            "ledger_restored", sequence=self.sequence, prior_entry=self.entry_attempted
        )
        for reason in reasons:
            self._freeze(reason)
        return not reasons

    def on_stop(self):
        if "t22-watchdog" in self.clock.timer_names():
            self.clock.cancel_timer("t22-watchdog")
        if self.quantity or self.pending is not None:
            self.flags.add("owned_residual_requires_operator_reconciliation")

    def on_data(self, data):
        try:
            value = getattr(data, "data", data)
            if (
                not isinstance(value, FactorSnapshot)
                or value.instrument_id != self.spec.instrument_id
            ):
                return
            now = self.clock.timestamp_ns()
            if value.ts_init > now or value.ts_event > now:
                self._record("snapshot_refused", reason="future_availability")
                return
            if (
                value.evidence_class != self.spec.evidence_class
                or value.cohort_sha256 != self.spec.cohort_sha256
            ):
                self._record("snapshot_refused", reason="cohort_or_evidence_mismatch")
                return
            if self.snapshot is not None:
                if value.ts_init < self.snapshot.ts_init:
                    self._record("snapshot_refused", reason="out_of_order")
                    return
                if value.ts_init == self.snapshot.ts_init:
                    if value != self.snapshot:
                        self._freeze("conflicting_snapshot_revision")
                    return
            self.snapshot = value
            self._record("snapshot", source_sha256=value.source_sha256)
        except Exception as error:
            self._fault("on_data", error)
            raise

    def on_quote(self, quote):
        try:
            if quote.instrument_id != self.instrument_id:
                return
            if (
                self.last_quote is not None
                and quote.ts_event < self.last_quote.ts_event
            ):
                self._record("quote_refused", reason="out_of_order")
                return
            self.last_quote = quote
            self._drive()
        except Exception as error:
            self._fault("on_quote", error)
            raise

    def _on_watchdog(self, event):
        try:
            self._drive()
        except Exception as error:
            self._fault("watchdog", error)
            raise

    def _fresh_quote(self, now):
        q = self.last_quote
        if q is None:
            return False
        bid, ask = decimal(str(q.bid_price)), decimal(str(q.ask_price))
        return (
            D(0) < bid <= ask
            and q.ts_event <= now + self.spec.future_tolerance_ns
            and q.ts_init <= now
            and now - q.ts_event <= self.spec.quote_max_age_ns
            and decimal(str(q.bid_size)) > 0
            and decimal(str(q.ask_size)) > 0
        )

    def _session(self, now):
        session = _sessions.session_at(datetime.fromtimestamp(now / 1e9, timezone.utc))
        return session

    def _drive(self):
        if self.faulted or not self.enabled:
            return
        now = self.clock.timestamp_ns()
        halted = self.snapshot is None or self.snapshot.halted
        if self.pending is not None:
            timeout = (
                self.spec.entry_timeout_ns
                if self.pending_role == "entry"
                else self.spec.exit_timeout_ns
            )
            if self.cancel_requested:
                if now - self.cancel_requested_ns >= timeout:
                    self._freeze("cancel_ack_timeout_requires_reconciliation")
                return  # Never assume an unacknowledged cancel freed the order.
            force = (
                self.spec.exit_deadline_ns is not None
                and now >= self.spec.exit_deadline_ns
                and (self.pending_role == "entry" or self.exit_reason != "time_exit")
            )
            if (
                not halted
                and not self.cancel_requested
                and (now - self.pending_since_ns >= timeout or force)
            ):
                self.cancel_requested = True
                self.cancel_requested_ns = now
                self._record("cancel_requested", role=self.pending_role)
                self.cancel_order(self.pending.client_order_id)
            return  # Never replace before terminal confirmation or overlap buys/sells.
        fresh = self._fresh_quote(now)
        if self.quantity and not fresh:
            self._freeze("held_quote_stale")
            return  # Includes forced/time exits: R9 never prices from a stale quote.
        if not fresh or self.snapshot is None:
            return
        self.flags.discard("held_quote_stale")
        if halted:
            if self.quantity:
                self._freeze("held_halted")
            return
        self.flags.discard("held_halted")
        session = self._session(now)
        if session.kind == _sessions.SessionKind.CLOSED:
            if self.quantity:
                self._freeze("closed_session_requires_handoff")
            return
        bid = decimal(str(self.last_quote.bid_price))
        if self.quantity:
            self.high_bid = max(self.high_bid, bid)
            self._exit(now, bid)
        elif not self.entry_attempted:
            self._enter(now, session)

    def _entry_allowed(self, now, session):
        snapshot = self.snapshot
        if not snapshot.cohort_member or now > snapshot.valid_until_ns:
            return False
        if (
            self.spec.entry_deadline_ns is not None
            and now >= self.spec.entry_deadline_ns
        ):
            return False
        if self.spec.exit_deadline_ns is not None and now >= self.spec.exit_deadline_ns:
            return False
        if self.spec.evidence_class == "development" and any(
            x not in self.spec.qualified_data
            for x in REQUIRED_QUALIFICATIONS.get(self.FAMILY, ())
        ):
            self.flags.add("owner_gated_family_data_unqualified")
            return False
        if self.preset.confirmation_seconds:
            elapsed = (
                0 if session.open is None else now / 1e9 - session.open.timestamp()
            )
            if session.kind != _sessions.SessionKind.RTH or elapsed < 300:
                return False
            if (
                now - snapshot.ts_init
                < self.preset.confirmation_seconds * 1_000_000_000
            ):
                return False
        elif (
            self.spec.preset == "standard-v1"
            and session.kind != _sessions.SessionKind.RTH
        ):
            return False
        if self.FAMILY == "options_flow_stock" and (
            snapshot.expiry_ns is None or now >= snapshot.expiry_ns - 300_000_000_000
        ):
            return False
        return self.entry_condition(snapshot)

    def _enter(self, now, session):
        if not self._entry_allowed(now, session):
            return
        atr = self.snapshot.value("atr_price")
        trigger = self.snapshot.value("entry_trigger")
        if atr is None or trigger is None or atr <= 0 or trigger <= 0:
            return
        bid, ask = (
            decimal(str(self.last_quote.bid_price)),
            decimal(str(self.last_quote.ask_price)),
        )
        # Standard's code-managed variant observes the trigger crossing; it does
        # not claim the target preset's pre-placed native stop-limit semantics.
        if ask < trigger:
            return
        price = self._limit_price(ask, OrderSide.BUY)
        stop = atr * self.preset.stop_atr
        structure = self.snapshot.value("structure_low")
        if (
            self.spec.preset in {"conservative-v1", "aggressive-v1"}
            and structure is not None
        ):
            if not D(0) < structure < ask:
                return
            stop = max(stop, price - structure)
        if stop >= ask or ask - bid > stop * self.preset.spread_stop_fraction:
            return
        fraction = self.preset.cap_fraction
        quantity = min(
            int(decimal(self.spec.position_cap_usd) * fraction / price),
            int(decimal(self.spec.cash_cap_usd) / price),
            int(decimal(self.spec.loss_cap_usd) * fraction / stop),
            self.spec.max_quantity,
        )
        if quantity <= 0:
            return
        self.entry_attempted = True
        self.entry_atr, self.stop_distance = atr, stop
        if self.FAMILY == "options_flow_stock":
            self.expiry_deadline_ns = self.snapshot.expiry_ns - 300_000_000_000
        self._submit(OrderSide.BUY, D(quantity), price, "entry", "family_signal")

    def _limit_price(self, reference, side):
        instrument = self.cache.instrument(self.instrument_id)
        collar = decimal(self.spec.limit_collar_bps) / BPS
        raw = reference * (1 + collar if side == OrderSide.BUY else 1 - collar)
        # The market-wide sub-penny grid changes below $1; respect the tighter instrument
        # grid as well. A buy rounds down into its collar; a sell rounds up.
        tick = max(
            decimal(str(instrument.price_increment)),
            D("0.01") if raw >= 1 else D("0.0001"),
        )
        rounding = ROUND_FLOOR if side == OrderSide.BUY else ROUND_CEILING
        return (raw / tick).to_integral_value(rounding=rounding) * tick

    def _holding_deadline(self, now):
        dt = datetime.fromtimestamp(now / 1e9, timezone.utc)
        policy = self.preset.exit_policy
        if policy is not None:
            info = _sessions.session_at(dt)
            day = info.session_date
            if policy.next_trading_day:
                day = _sessions.next_trading_day(day)
            # Reuse the shared calendar's PRE/RTH/POST boundaries, including
            # holidays, early closes and DST; do not rebuild session logic.
            pre = _sessions.session_at(
                datetime.combine(day, _sessions.PRE_OPEN, _sessions.NY)
            )
            if policy.boundary == "PRE_OPEN":
                boundary = pre.open
            elif policy.boundary == "RTH_OPEN":
                boundary = pre.close
            elif policy.boundary == "POST_CLOSE":
                boundary = _sessions.extended_session_close(pre.open)
            else:
                boundary = _sessions.session_at(pre.close).close
            return (
                int(boundary.timestamp() * 1e9) - policy.margin_seconds * 1_000_000_000
            )
        day = dt.astimezone(_sessions.NY).date()
        for _ in range(self.preset.max_sessions - 1):
            day = _sessions.next_trading_day(day)
        info = _sessions.session_at(
            datetime.combine(day, datetime.min.time(), _sessions.NY)
            + timedelta(hours=12)
        )
        return int(info.close.timestamp() * 1e9) - 120_000_000_000

    def _exit_config(self):
        stop_bps = float(self.stop_distance / self.entry_price * BPS)
        trail_bps = float(
            self.entry_atr * self.preset.trail_atr / self.entry_price * BPS
        )
        profit_r = self.preset.take_profit_r
        profit_bps = (
            float(self.stop_distance * profit_r / self.entry_price * BPS)
            if profit_r
            else float("inf")
        )
        gain_r = (self.high_bid - self.entry_price) / self.stop_distance
        if gain_r < self.preset.trail_from_r:
            trail_bps = float("inf")
        if self.take_profit_done:
            profit_bps = float("inf")
        return SimpleNamespace(
            stop_bps=stop_bps,
            stop_min_bps=stop_bps,
            stop_max_bps=stop_bps,
            trailing_bps=trail_bps,
            trailing_min_bps=trail_bps,
            trailing_max_bps=trail_bps,
            vol_stop_multiplier=1.0,
            vol_reference_bps=None,
            take_profit_bps=profit_bps,
            take_profit_fraction=float(self.preset.take_profit_fraction),
            time_decay_start_seconds=None,
            time_decay_min_multiplier=1.0,
            max_hold_seconds=self.preset.max_hold_seconds or float("inf"),
        )

    def _exit(self, now, bid):
        forced = (
            (
                self.spec.exit_deadline_ns is not None
                and now >= self.spec.exit_deadline_ns
            )
            or self.close_deadline_ns is not None
            and now >= self.close_deadline_ns
        )
        if self.expiry_deadline_ns is not None:
            forced = forced or now >= self.expiry_deadline_ns
        ctx = _exits.ExitContext(
            now=now / 1e9,
            entered_at=self.entered_ns / 1e9,
            pnl_bps=float((bid / self.entry_price - 1) * BPS),
            trail_bps=float((bid / self.high_bid - 1) * BPS),
            quote_fresh=True,
            risk_off=False,
            force_exit=forced,
            force_exit_reason="time_exit",
        )
        decision = _exits.DEFAULT_PLAN.evaluate(ctx, self._exit_config())
        if self.exit_reason is None:
            if decision is None:
                return
            quantity = int(self.quantity * decimal(str(decision.fraction)))
            if quantity <= 0:
                self._freeze("partial_take_profit_not_representable")
                return
            self.exit_reason, self.exit_remaining = decision.reason, D(quantity)
        elif decision is not None and decision.reason != "take_profit":
            self.exit_reason, self.exit_remaining = decision.reason, self.quantity
        if self.exit_orders >= self.spec.max_exit_orders:
            self._freeze("exit_budget_exhausted_requires_handoff")
            return
        price = self._limit_price(bid, OrderSide.SELL)
        if price <= 0:
            self._freeze("positive_exit_limit_unavailable")
            return
        self.exit_orders += 1
        self._submit(
            OrderSide.SELL,
            min(self.quantity, self.exit_remaining),
            price,
            "exit",
            self.exit_reason,
        )

    def _submit(self, side, quantity, price, role, reason):
        if self.faulted or not self.enabled:
            return
        if self.sequence >= 9_999_999:
            self._freeze("client_order_sequence_exhausted_requires_handoff")
            return
        self.sequence += 1
        client_id = self.client_id_prefix + f"{self.sequence:07d}"
        instrument = self.cache.instrument(self.instrument_id)
        order = self.order_factory.limit(
            self.instrument_id,
            side,
            Quantity.from_str(str(quantity)),
            Price.from_decimal_dp(price, instrument.price_precision),
            time_in_force=TimeInForce.DAY,
            reduce_only=side == OrderSide.SELL,
            client_order_id=ClientOrderId(client_id),
            tags=[
                "family=" + self.FAMILY,
                "preset=" + self.spec.preset,
                "profile=" + self.spec.execution_profile,
                "reason=" + reason,
            ],
        )
        self.pending, self.pending_role = order, role
        self.pending_remaining = quantity
        self.pending_since_ns = self.clock.timestamp_ns()
        self.cancel_requested = False
        self.cancel_requested_ns = 0
        self._record(
            "submit",
            side=str(side),
            quantity=str(quantity),
            limit_price=str(price),
            reason=reason,
            client_order_id=client_id,
        )
        self.submit_order(order)

    @guarded_callback
    def on_order_filled(self, event):
        if str(event.trade_id) in self.seen_fills:
            return
        if (
            self.pending is None
            or event.client_order_id != self.pending.client_order_id
        ):
            raise ValueError("unmatched_owned_fill")
        quantity, price = decimal(str(event.last_qty)), decimal(str(event.last_px))
        if not D(0) < quantity <= self.pending_remaining:
            raise ValueError("fill_quantity_outside_pending")
        self.seen_fills.add(str(event.trade_id))
        self.pending_remaining -= quantity
        if event.order_side == OrderSide.BUY:
            cost = self.quantity * self.entry_price + quantity * price
            self.quantity += quantity
            self.entry_price = cost / self.quantity
            if self.entered_ns is None:
                self.entered_ns = self.clock.timestamp_ns()
                self.close_deadline_ns = self._holding_deadline(self.entered_ns)
            self.high_bid = max(self.high_bid, price)
        else:
            if quantity > self.quantity:
                raise ValueError("exit_fill_exceeds_owned_quantity")
            self.quantity -= quantity
            self.exit_remaining -= quantity
            if self.exit_reason == "take_profit":
                self.take_profit_done = True
            if self.exit_remaining <= 0:
                self.exit_reason, self.exit_remaining = None, D(0)
        self._record(
            "fill", side=str(event.order_side), quantity=str(quantity), price=str(price)
        )
        if self.pending_remaining == 0:
            self._clear_pending()

    def _clear_pending(self):
        self.pending = None
        self.pending_role = None
        self.pending_remaining = D(0)
        self.cancel_requested = False
        self.cancel_requested_ns = 0

    def _terminal(self, event, refused=False):
        if (
            self.pending is not None
            and event.client_order_id == self.pending.client_order_id
        ):
            self._record("terminal", role=self.pending_role, refused=refused)
            if refused:
                self._freeze("native_order_refused_requires_handoff")
            self._clear_pending()

    @guarded_callback
    def on_order_cancel_rejected(self, event):
        if (
            self.pending is not None
            and event.client_order_id == self.pending.client_order_id
        ):
            # rc5's native cancel-reject callback is non-terminal: the original
            # order can still fill. Keep its ID/residual and require recovery.
            self._record("cancel_rejected", client_order_id=str(event.client_order_id))
            self._freeze("native_cancel_rejected_requires_reconciliation")

    @guarded_callback
    def on_order_canceled(self, event):
        self._terminal(event)

    @guarded_callback
    def on_order_expired(self, event):
        self._terminal(event)

    @guarded_callback
    def on_order_rejected(self, event):
        self._terminal(event, refused=True)

    @guarded_callback
    def on_order_denied(self, event):
        self._terminal(event, refused=True)

    def entry_condition(self, snapshot):
        raise NotImplementedError

    @staticmethod
    def _at_least(snapshot, key, threshold):
        value = snapshot.value(key)
        return value is not None and value >= D(threshold)

    @staticmethod
    def _positive(snapshot, key):
        value = snapshot.value(key)
        return value is not None and value > 0


class CatalystStrategy(FamilyStrategy):
    FAMILY = "catalyst"

    def entry_condition(self, s):
        return (
            any(self._positive(s, k) for k in FAMILY_FACTORS[self.FAMILY][:-1])
            and self._positive(s, "catalyst_confirmation")
            and self._positive(s, "price_confirmation")
            and self._at_least(s, "relative_volume", "2")
        )


class GapPremarketStrategy(FamilyStrategy):
    FAMILY = "gap_premarket"

    def entry_condition(self, s):
        return (
            self._at_least(s, "overnight_gap", "0.02")
            and self._positive(s, "premarket_return")
            and self._at_least(s, "premarket_activity", "1")
        )


class VolumeFloatStrategy(FamilyStrategy):
    FAMILY = "volume_float"

    def entry_condition(self, s):
        return (
            self._at_least(s, "relative_volume", "2")
            and self._at_least(s, "float_turnover", "1")
            and self._positive(s, "float_flip_clock")
        )


class SqueezeBorrowStrategy(FamilyStrategy):
    FAMILY = "squeeze_borrow"

    def entry_condition(self, s):
        return (
            self._at_least(s, "short_interest", "0.2")
            and self._at_least(s, "days_to_cover", "2")
            and self._positive(s, "fails_to_deliver")
            and self._positive(s, "borrow_fee")
            and self._positive(s, "price_confirmation")
        )


class MomentumBreakoutStrategy(FamilyStrategy):
    FAMILY = "momentum_breakout"

    def entry_condition(self, s):
        width = s.value("tight_range_state")
        return (
            self._positive(s, "momentum_20")
            and self._at_least(s, "range_breakout", "1")
            and width is not None
            and D(0) < width <= D("0.05")
        )


class OptionsFlowStockStrategy(FamilyStrategy):
    FAMILY = "options_flow_stock"

    def entry_condition(self, s):
        return (
            self._at_least(s, "option_volume_surge", "2")
            and self._positive(s, "gamma_exposure_proxy")
            and self._at_least(s, "expiry_concentration", "0.5")
        )


class HaltReopenStrategy(FamilyStrategy):
    FAMILY = "halt_reopen"

    def entry_condition(self, s):
        return (
            self._positive(s, "halt_event")
            and self._positive(s, "halt_reopen_liquidity")
            and self._at_least(s, "reopen_bid_print", "1")
            and self._at_least(s, "reopen_ask_print", "1")
            and s.value("halt_pause_density") is not None
        )


class PostEarningsDriftStrategy(FamilyStrategy):
    FAMILY = "post_earnings_drift"

    def entry_condition(self, s):
        return (
            self._positive(s, "earnings")
            and self._positive(s, "overnight_gap")
            and self._at_least(s, "relative_volume", "1.5")
        )


class TrendNewHighsStrategy(FamilyStrategy):
    FAMILY = "trend_new_highs"

    def entry_condition(self, s):
        return (
            self._positive(s, "trend_state")
            and self._positive(s, "relative_strength")
            and self._at_least(s, "at_all_time_closing_high", "1")
        )


class ShortTermReversalStrategy(FamilyStrategy):
    FAMILY = "short_term_reversal"

    def entry_condition(self, s):
        ret = s.value("momentum_5")
        return (
            ret is not None
            and ret <= D("-0.03")
            and self._positive(s, "price_confirmation")
        )


class NoTradeStrategy(FamilyStrategy):
    FAMILY = "control_no_trade"

    def entry_condition(self, s):
        return False


class HashRandomControl(FamilyStrategy):
    FAMILY = "control_hash_random"

    def entry_condition(self, s):
        return (
            int(digest([s.cohort_sha256, s.instrument_id, "t22-control-v1"]), 16) % 4
            == 0
        )


class MomentumControl(FamilyStrategy):
    FAMILY = "control_momentum_20"

    def entry_condition(self, s):
        return self._positive(s, "momentum_20")


class RelativeVolumeControl(FamilyStrategy):
    FAMILY = "control_relative_volume"

    def entry_condition(self, s):
        return self._at_least(s, "relative_volume", "2")


FAMILIES = MappingProxyType(
    {
        cls.FAMILY: cls
        for cls in (
            CatalystStrategy,
            GapPremarketStrategy,
            VolumeFloatStrategy,
            SqueezeBorrowStrategy,
            MomentumBreakoutStrategy,
            OptionsFlowStockStrategy,
            HaltReopenStrategy,
            PostEarningsDriftStrategy,
            TrendNewHighsStrategy,
            ShortTermReversalStrategy,
        )
    }
)
CONTROLS = MappingProxyType(
    {
        cls.FAMILY: cls
        for cls in (
            NoTradeStrategy,
            HashRandomControl,
            MomentumControl,
            RelativeVolumeControl,
        )
    }
)
