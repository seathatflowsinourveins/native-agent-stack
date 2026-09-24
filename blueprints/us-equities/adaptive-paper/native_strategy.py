"""One native strategy owns the shared portfolio across policy families."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from decimal import Decimal
import time
from nautilus_trader.trading import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model import (ClientOrderId, InstrumentId, OrderSide, Price,
                                  Quantity, StrategyId, TimeInForce)
from exits import REASON_PRICE_RULE
from leverage import LeverageInputs
from safety import DEFAULT_STOP, SafetyError, evaluate_gap_risk
from sessions import SessionKind, next_trading_day, previous_trading_day, session_at
from strategies import AdaptivePolicy, OperationalStatus, QUOTE_FUTURE_TOLERANCE_SECONDS, limit_price


class AdaptiveStrategy(Strategy):
    def __new__(cls, policy, ledger, trial_id, **kwargs):
        return super().__new__(cls, StrategyConfig(strategy_id=StrategyId("ADAPTIVE-001"),
                                order_id_tag="A", log_events=False, log_commands=False, manage_stop=False))

    def __init__(self, policy: AdaptivePolicy, ledger, trial_id: str, *, event_sink=None,
                 transport=None, stop_file=None, clock=time.time, account_multiplier=None,
                 corporate_action_guard=None):
        self.policy = policy
        self.ledger = ledger
        self.trial_id = trial_id
        self.event_sink = event_sink or (lambda event: None)
        self.transport = transport
        self.stop_file = stop_file
        # Trading-lane audit gap #8: opt-in corporate-action guard (see
        # corporate_actions.py's module docstring for the full precedence
        # contract against gap_risk_stop/exits.py/force_exit). None
        # (default) leaves rebalance() byte-identical to before this
        # control existed -- _corporate_action_guard_symbols returns
        # immediately without a session lookup or event. runner.py's
        # `paper` command threads a real corporate_actions.CorporateActionMonitor
        # here; tests inject a fake with the same `.evaluate(...)` shape.
        self.corporate_action_guard = corporate_action_guard
        # NIT finding 11 (2026-09-24 fix round): the last corporate_action_
        # guard event actually emitted per symbol (a comparable tuple, or
        # absent for "no event emitted / symbol currently clear"), so
        # _corporate_action_guard_symbols only re-emits an event when a
        # symbol's decision actually CHANGES from the previous tick,
        # instead of re-emitting an identical event every tick for as long
        # as e.g. a confirmed must_flatten stays in range (the underlying
        # sell action itself is still deliberately re-applied every tick --
        # see corporate_actions.py's module docstring -- only the EVENT LOG
        # entry is now deduplicated).
        self._ca_last_emitted = {}
        # MEDIUM finding 8/finding 5 (2026-09-24 fix round): run-outcome
        # guard summary state. `_ca_ever_flagged` is every symbol this run
        # ever had a corporate_action_guard event emitted for (block/
        # flatten/attention at least once) -- runner.py surfaces it in the
        # run outcome. `_ca_last_must_flatten` is the CURRENT (this tick's)
        # must_flatten set -- runner.py's _honest_overnight_hold reads it
        # so a run cannot end "held_overnight" while a symbol is still
        # flagged for a forced flatten (finding 5).
        self._ca_ever_flagged = set()
        self._ca_last_must_flatten = set()
        # G-e: the broker-proven margin multiplier (runner.py's config
        # "_account_multiplier", only ever set after preflight has checked
        # multiplier >= requested leverage -- see runner._check_margin_
        # entitlement). None outside the leverage policy; consulted only by
        # _leverage_inputs below, and only when self.policy.leverage_policy
        # is not None (rebalance() only builds leverage_inputs then).
        self.account_multiplier = account_multiplier
        # D2 (round 6): a single clock, mirroring runner.Controller's own
        # `clock=time.time` constructor convention, so rebalance()'s
        # default `now` and on_order_canceled's ack-time `now` (which has
        # no caller-supplied `now` parameter to receive -- it is a real
        # nautilus event callback dispatched with only `event`) come from
        # the exact same source. Swappable for a synthetic clock in tests
        # (see ReplacementAckClockTests).
        self._clock = clock
        self.pending = {}
        prefix = f"adp-{trial_id}-"
        self.sequence = max((int(i.client_id[len(prefix):]) for i in ledger.intents()
                             if i.client_id.startswith(prefix) and i.client_id[len(prefix):].isdigit()), default=0)
        self.native_fills = 0
        self.native_rejections = 0
        self.received_quotes = 0
        self.started = False
        self.enabled = False
        # D5 gap-risk state: the prior session's captured RTH close price per
        # symbol, the session kind as of the previous rebalance() tick (to
        # detect the CLOSED/PRE -> RTH crossing), the stop price computed
        # once at this RTH session's open, and which symbols the gap stop
        # has already fired for (fire-once per RTH session).
        # S5: seed from the ledger's durably persisted prior-RTH-close
        # prices (see safety.Ledger.record_prior_rth_close/prior_rth_closes)
        # rather than starting empty every process, so the D5 gap-risk stop
        # can still fire against a close captured by an earlier invocation
        # (e.g. resuming a held overnight position after a restart).
        # D3 (round 4): prior_rth_closes() now returns {"price",
        # "session_date", "ts_ns"} per symbol, not a bare price -- keep
        # the price and session_date in separate parallel dicts so
        # _gap_risk_stop_symbols can validate a loaded close's session_date
        # before ever arming against it (see _gap_risk_stop_symbols'
        # docstring; D5 round 5 -- this comment used to misname it
        # "_arm_gap_stop", a method that never existed).
        loaded = ledger.prior_rth_closes()
        self._prior_rth_close = {symbol: record["price"] for symbol, record in loaded.items()}
        self._prior_rth_close_session_date = {symbol: record["session_date"] for symbol, record in loaded.items()}
        self._last_session_kind = None
        self._gap_risk_stop_price = {}
        self._gap_stop_applied = set()
        # D2 (round 4): symbols still waiting to be armed for the current
        # RTH session (set at the CLOSED/PRE -> RTH crossing, drained as
        # each symbol's quote becomes fresh enough to arm against -- a
        # symbol with only a stale quote at the crossing tick itself stays
        # pending and is retried on every subsequent RTH tick, rather than
        # being silently skipped for the rest of the session).
        self._gap_arm_pending = set()
        # D2 (round 5): the mirror-image retry set for the CAPTURE side (at
        # the RTH -> non-RTH crossing): symbols whose capture quote was
        # stale at the crossing tick, retried on every later non-RTH tick
        # until captured or abandoned at the next RTH open (see
        # _gap_risk_stop_symbols' docstring). _prior_close_capture_session_date
        # pins the capture to the RTH session date that actually just
        # ended, independent of how many (non-RTH) ticks the retry spans.
        self._prior_close_capture_pending = set()
        self._prior_close_capture_session_date = None
        # D4 (round 4): the most recently evaluated gap_bps per symbol,
        # surfaced in rebalance()'s decision event.
        self._gap_bps = {}
        # G-f deliverable 2: cancel-then-replace state for resting exit
        # orders whose price or price_rule has changed (e.g. a trailing
        # stop ratchet -- see exits.REASON_PRICE_RULE). All per-symbol,
        # reset only by a fresh AdaptiveStrategy instance (one per
        # trial/session), matching PolicyConfig.exit_replace_max_attempts'
        # "per symbol per session" cap. D5 (round 2): removed the
        # write-only `_exit_price_rule` dict that duplicated (and was never
        # read back from) `self.pending[client_id]["price_rule"]`, which is
        # already the single source replace_exit itself reads.
        self._exit_replace_busy = set()
        self._exit_attempts = {}
        self._last_replace_at = {}
        # D1 (round 8): a SEPARATE, never-rolled-back per-symbol counter
        # of cancel-rejects. _exit_attempts/_last_replace_at ARE rolled
        # back on a cancel-reject (see on_order_cancel_rejected -- no
        # replacement actually happened, so charging the attempts budget
        # or the min-interval clock for it would be wrong) -- but that
        # rollback alone leaves NO bound at all on retries against a
        # broker that keeps refusing to cancel the same resting order:
        # replace_exit would be re-tried and cancel-rejected forever with
        # every attempt fully refunded. This counter is bumped on every
        # cancel-reject and never refunded; replace_exit refuses once it
        # reaches exit_replace_max_attempts, independent of the (rolled
        # back) exit_attempts count.
        self._cancel_reject_counts = {}

    def on_start(self):
        for symbol in self.policy.config.symbols:
            self.subscribe_quotes(InstrumentId.from_str(symbol + ".ALPACA"))
        self.started = True

    def on_quote(self, quote):
        symbol = str(quote.instrument_id).rsplit(".", 1)[0]
        if self.policy.observe(symbol, float(str(quote.bid_price)), float(str(quote.ask_price)),
                               quote.ts_event / 1_000_000_000):
            self.received_quotes += 1

    def on_order_filled(self, event):
        self.native_fills += 1
        client_id = str(event.client_order_id)
        # D1 (round 3): a fill (full or partial) can race a staged
        # cancel-then-replace -- see _release_staged_replacement's
        # docstring. Residue protection for a partial fill still holds:
        # once busy is released here, the next rebalance() tick's
        # ordinary exit-action path re-derives the sell quantity from the
        # (now-reduced) live held-vs-target and submits a fresh resting
        # exit for whatever remains.
        #
        # D3 (round 8): terminal="fill" -- a genuine fill must NOT clear
        # gap-risk fire-once (see _release_staged_replacement's own
        # `terminal` docstring). A fill racing a staged cancel-then-replace
        # still had its protective stop fire; the position is simply gone
        # now (fully or partially), not "unprotected".
        self._release_staged_replacement(client_id, terminal="fill")
        self._finish_if_terminal(client_id)

    def on_order_canceled(self, event):
        """D1 (round 6): unlike on_order_rejected/denied/expired/
        cancel_rejected, an ordinary (non-replace) cancel of a
        gap_risk_stop order reaches here too -- e.g. cancel_expired's
        plain timeout cancel of a resting exit that was never replaced.
        Left marked, fire-once would stay "consumed" for a symbol whose
        protective order was just cancelled with nothing replacing it.
        Only clear it in that ordinary-cancel case: when this cancel IS
        the staged cancel-then-replace of that same gap exit (`replacement`
        is not None), do not clear it here -- the replacement itself
        carries the "gap_risk_stop" reason and (re-)marks fire-once
        itself, only once it is actually submitted (see
        _submit_replacement_exit's own D1/D6, round 4, guards)."""
        client_id = str(event.client_order_id)
        info = self.pending.pop(client_id, None)
        replacement = (info or {}).get("replace_with")
        if replacement is not None:
            # D2 (round 6): the clock AT ACKNOWLEDGEMENT time, never a
            # frozen request-time value -- see _submit_replacement_exit's
            # docstring (D4, round 8: the field that used to freeze the
            # request-time value was dead/write-only and was removed).
            self._submit_replacement_exit(replacement, self._clock())
        else:
            self._clear_gap_stop_applied_if_matches(info)

    def on_order_expired(self, event):
        client_id = str(event.client_order_id)
        self._release_staged_replacement(client_id)
        self._clear_gap_stop_applied_if_matches(self.pending.get(client_id))
        self.pending.pop(client_id, None)

    def on_order_rejected(self, event):
        self.native_rejections += 1
        client_id = str(event.client_order_id)
        self._release_staged_replacement(client_id)
        self._clear_gap_stop_applied_if_matches(self.pending.get(client_id))
        if str(event.reason).startswith("broker definitively rejected"):
            self.ledger.freeze("broker_refusal_needs_reconciliation")
        else:
            self._mark_definitive_refusal(client_id)
        self.pending.pop(client_id, None)

    def on_order_denied(self, event):
        self.native_rejections += 1
        client_id = str(event.client_order_id)
        self._release_staged_replacement(client_id)
        self._clear_gap_stop_applied_if_matches(self.pending.get(client_id))
        self._mark_definitive_refusal(client_id)
        self.pending.pop(client_id, None)

    def on_order_cancel_rejected(self, event):
        """D1 (round 3): the *cancel* itself failed -- the resting order
        is still live and unmodified (replace_exit's cancel never took
        effect). Release any staged replacement (it must not be submitted
        for an order that was never actually cancelled) and clear
        cancel_requested so this order is visible to _resting_exit_client_id
        and cancel_expired again, instead of being permanently treated as
        "cancelling forever".

        D1 (round 5): also clears fire-once (see
        _clear_gap_stop_applied_if_matches) for a gap_risk_stop order --
        this is conservative rather than strictly necessary (the order
        itself is still resting, unmodified, still protecting the
        position), but matches every other terminal-ish path here and
        costs nothing: the next tick's arm/trigger re-check simply finds
        the same still-resting order again (replace_exit on an unchanged
        order returns "noop").

        D3 (round 7): replace_exit already consumed one exit_attempts
        slot for this symbol BEFORE calling cancel_order -- stamped for a
        replacement that, since the cancel itself failed, never actually
        happened. Roll it back to its pre-attempt value (staged on the
        replacement by replace_exit for exactly this purpose) so a
        cancel-reject does not silently burn part of the attempts budget.

        D1 (round 8): `_last_replace_at` is deliberately NOT rolled back
        anymore (round 7 rolled it back too). A broker that keeps
        refusing to cancel the same resting order would otherwise let
        replace_exit retry it again immediately on the very next tick,
        forever -- the min-interval gate was the only thing standing
        between a repeatedly-cancel-rejected order and a tight retry
        loop, and rolling it back removed that bound entirely. Keeping
        `_last_replace_at` advanced preserves the min-interval spacing
        between retries. A SEPARATE, never-rolled-back
        `_cancel_reject_counts` counter (bumped just below) gives an
        outright cap on top of that spacing: once it reaches
        exit_replace_max_attempts, replace_exit refuses outright rather
        than retrying again after the interval -- see replace_exit's own
        docstring."""
        client_id = str(event.client_order_id)
        info = self.pending.get(client_id)
        replacement = (info or {}).get("replace_with")
        if replacement is not None:
            symbol = replacement["symbol"]
            if "previous_attempts" in replacement:
                self._exit_attempts[symbol] = replacement["previous_attempts"]
            self._cancel_reject_counts[symbol] = self._cancel_reject_counts.get(symbol, 0) + 1
        self._release_staged_replacement(client_id)
        self._clear_gap_stop_applied_if_matches(self.pending.get(client_id))
        info = self.pending.get(client_id)
        if info is not None:
            info["cancel_requested"] = False

    def _clear_gap_stop_applied_if_matches(self, info):
        """D1 (round 5): fire-once (self._gap_stop_applied) is consumed
        by a submitted order that later terminates WITHOUT filling --
        rejected, denied, expired, or (defensively) a cancel-reject on the
        symbol's own gap_risk_stop order. Left marked, the position would
        stay permanently unprotected for the rest of the RTH session (no
        order ever executed, but the stop is treated as "already fired").
        A genuine fill is deliberately NOT cleared here -- see
        on_order_filled, which does not call this."""
        if info is not None and info.get("reason") == "gap_risk_stop":
            self._gap_stop_applied.discard(info["symbol"])

    def _clear_gap_stop_for_dropped_replacement(self, replacement):
        """D2 (round 7): fire-once used to be left marked on the premise
        that a staged replacement carrying the "gap_risk_stop" reason
        would itself re-mark it once submitted. When that staged
        replacement is instead dropped or abandoned before ever being
        submitted -- a stale quote at ack time in _submit_replacement_exit,
        or the order it was meant to replace terminating some other way in
        _release_staged_replacement -- the OLD resting order is already
        gone (cancelled, or otherwise terminated) by the time this runs,
        so nothing is left resting to protect the position; fire-once
        must be cleared too, or the stop reads as "already fired" for the
        rest of the RTH session with no order actually resting."""
        if replacement is not None and replacement.get("reason") == "gap_risk_stop":
            self._gap_stop_applied.discard(replacement["symbol"])

    def _release_staged_replacement(self, client_id, terminal=None):
        """D1 (round 3): `_exit_replace_busy` used to be released only
        inside `_submit_replacement_exit` (reached from `on_order_canceled`
        when a cancel-then-replace's cancel is acknowledged). If the
        resting order this method's `client_id` refers to instead
        terminates some other way -- filled (in whole or part), rejected,
        expired, or its cancel was itself rejected -- while a replacement
        was staged on it (`replace_exit` was called on it), the busy flag
        would leak forever (the symbol could never be replaced or, in some
        of those cases, even resubmitted, again this session) and the
        stale staged replacement must never be submitted for an order that
        was never actually cancelled cleanly. Release the busy flag and
        drop the staged replacement; nothing here submits a new order --
        the next rebalance() tick's ordinary exit-action path re-derives
        sell quantity from live held-vs-target once the symbol is free
        again, which also covers a partial fill's residue.

        D3 (round 8): `terminal` names WHICH terminal event is releasing
        this staged replacement. Every caller except on_order_filled
        leaves it None, which still clears gap-risk fire-once for a
        dropped gap_risk_stop replacement (see
        _clear_gap_stop_for_dropped_replacement) -- the old resting order
        is gone and nothing was submitted to replace it, so the position
        really is unprotected. on_order_filled instead passes
        terminal="fill": a genuine fill means the protective stop DID do
        its job (or the position is otherwise gone/reduced); fire-once
        must stay marked, not be cleared, so this symbol is not treated
        as still needing a fresh gap-risk stop for the rest of the
        session."""
        info = self.pending.get(client_id)
        if info is not None and info.get("replace_with") is not None:
            self._exit_replace_busy.discard(info["symbol"])
            if terminal != "fill":
                self._clear_gap_stop_for_dropped_replacement(info["replace_with"])
            info["replace_with"] = None

    def _mark_definitive_refusal(self, client_id):
        intent = next((i for i in self.ledger.intents() if i.client_id == client_id), None)
        if intent and intent.broker_id is None and intent.filled_qty == 0:
            self.ledger.mark_not_sent(client_id, "native_definitive_refusal")

    def _finish_if_terminal(self, client_id):
        intent = next((i for i in self.ledger.intents() if i.client_id == client_id), None)
        if intent and intent.terminal:
            self.pending.pop(client_id, None)

    def positions(self):
        return {p.symbol: {"qty": str(p.qty), "avg_entry_price": str(p.average_cost)}
                for p in self.ledger.positions().values() if p.qty}

    def _corporate_action_guard_symbols(self, now, held, candidate_symbols):
        """Trading-lane audit gap #8: consult the injected corporate-action
        guard (`self.corporate_action_guard`, see corporate_actions.py) for
        (a) the set of held symbols that must be flattened before this
        session's close, and (b) the set of symbols -- held or candidate --
        whose entries (new or added-to) must be blocked this tick.

        Opt-in: `self.corporate_action_guard is None` (the default) returns
        immediately, with no session lookup and no event -- byte-identical
        to before this control existed, the same pattern
        `PolicyConfig.gap_stop_enabled` uses for `_gap_risk_stop_symbols`.

        Fail-closed on an unclassifiable session, block-and-flag only
        (finding 6, 2026-09-24 fix round): a `now` outside the frozen
        session calendar (`session_at`/`next_trading_day` raising
        `ValueError`) cannot even compute "today" or "the next session", so
        every held-or-candidate symbol this tick has its entry blocked and
        is flagged needs_attention -- but is NOT force-flattened purely
        because the calendar itself failed to classify this tick (a
        calendar gap is not evidence of an actual corporate action; forcing
        every held position closed on a transient calendar failure
        contradicts this guard's own must_flatten contract, which is
        reserved for a CONFIRMED in-range action). A held position instead
        stays open, blocked from growing further, with needs_attention set
        so an operator/the recovery path is warned.
        """
        if self.corporate_action_guard is None:
            return set(), set()
        held_symbols = {symbol for symbol, qty in held.items() if qty > 0}
        try:
            info = session_at(datetime.fromtimestamp(now, timezone.utc))
            next_session_date = next_trading_day(info.session_date)
        except ValueError:
            relevant = held_symbols | set(candidate_symbols)
            for symbol in relevant:
                self._emit_ca_event_on_change(symbol, "corporate_action_session_unknown",
                                              block_entry=True, must_flatten=False, needs_attention=True,
                                              action_type=None, action_date=None)
            self._ca_last_must_flatten = set()
            return relevant, set()
        decisions = self.corporate_action_guard.evaluate(
            today=info.session_date, next_session_date=next_session_date,
            held_symbols=held_symbols, candidate_symbols=set(candidate_symbols), now=now)
        block_entry, must_flatten = set(), set()
        for symbol, decision in decisions.items():
            if decision.block_entry:
                block_entry.add(symbol)
            if decision.must_flatten:
                must_flatten.add(symbol)
            if decision.block_entry or decision.must_flatten or decision.needs_attention:
                self._emit_ca_event_on_change(
                    symbol, decision.reason, block_entry=decision.block_entry,
                    must_flatten=decision.must_flatten, needs_attention=decision.needs_attention,
                    action_type=decision.action_type,
                    action_date=decision.action_date.isoformat() if decision.action_date else None)
            else:
                # Symbol has gone clear (no block/flatten/attention this
                # tick) -- drop any tracked prior state so a FUTURE
                # re-block is treated as a change and re-emitted, not
                # suppressed as "unchanged from a stale clear tick".
                self._ca_last_emitted.pop(symbol, None)
        self._ca_last_must_flatten = set(must_flatten)
        return block_entry, must_flatten

    def _emit_ca_event_on_change(self, symbol, reason, *, block_entry, must_flatten, needs_attention,
                                 action_type, action_date):
        """NIT finding 11: emit a `corporate_action_guard` event for
        `symbol` only when its decision differs from the last one actually
        emitted for that symbol (see `self._ca_last_emitted`'s docstring in
        `__init__`)."""
        state = (block_entry, must_flatten, needs_attention, reason, action_type, action_date)
        self._ca_ever_flagged.add(symbol)
        if self._ca_last_emitted.get(symbol) == state:
            return
        self._ca_last_emitted[symbol] = state
        self.event_sink({"type": "corporate_action_guard", "symbol": symbol,
                         "block_entry": block_entry, "must_flatten": must_flatten,
                         "needs_attention": needs_attention, "reason": reason,
                         "action_type": action_type, "action_date": action_date})

    def _gap_risk_stop_symbols(self, now, held):
        """D5: on the first RTH bar after an overnight hold, evaluate
        safety.evaluate_gap_risk between the prior session's captured RTH
        close and this session's actual open print, and return the set of
        held symbols whose live bid has since breached the resulting stop
        (to be forced through the existing sell-order path in rebalance()).

        The stop price is computed once, from the first fresh-quote RTH
        tick, then held fixed and checked against every later tick's live
        quote for the rest of that RTH session (fire once); it is
        deliberately not re-derived from each new tick's own quote, which
        would make the check compare a quote against a stop derived from
        itself and could never fire.

        This is an account-level trigger like D3's overnight cap widening:
        it fires for any currently-held symbol at the crossing, not only
        positions individually proven to have been opened before the prior
        close, because this engine does not track a per-position entry
        session boundary. A date outside the frozen session calendar (D7)
        -- including previous_trading_day walking into a year outside
        sessions.CALENDAR_YEARS at the very first trading day of the
        calendar (round 5) -- degrades to "validation-unknown, do not arm,
        record it" (the "stale_prior_close_ignored" event below), not a
        raised exception.

        D2/D3/D4 (round 4): arming is decoupled from the single crossing
        tick. `_gap_arm_pending` is seeded with every held symbol at the
        CLOSED/PRE -> RTH crossing (or the "already RTH on the first tick"
        case below) and drained one symbol at a time, on this or any later
        RTH tick, once each symbol's own quote is fresh (D2) and its
        persisted prior close's session_date is exactly the trading day
        immediately before today's RTH session (D3) -- a stale quote at
        the crossing instant no longer permanently skips arming for the
        rest of the session, and a prior close from the wrong date can
        never arm a stop at all. D4: a gap is only armed when its adverse
        (downward) magnitude is at least gap_stop_trigger_bps; gap_bps
        itself is recorded in self._gap_bps for rebalance()'s decision
        event regardless of whether it armed.

        D2 (round 5): the CAPTURE side (at the RTH -> non-RTH crossing)
        gets the same retry treatment as arming: `_prior_close_capture_pending`
        is seeded with every held symbol at that crossing and drained one
        symbol at a time on this or any later non-RTH tick, once each
        symbol's own quote is fresh -- a "prior_close_captured" event is
        emitted per symbol on success; any symbol still pending once the
        NEXT RTH session opens is abandoned (never captured for that
        session) and recorded via "prior_close_capture_abandoned".

        Round 5: this entire method is opt-in, gated on
        PolicyConfig.gap_stop_enabled (default False) -- when disabled it
        returns immediately without touching self._prior_rth_close,
        self.ledger, or any quote at all, including the capture/persist
        side above."""
        if not self.policy.config.gap_stop_enabled:
            return set()
        try:
            info = session_at(datetime.fromtimestamp(now, timezone.utc))
        except ValueError:
            return set()
        kind, today = info.kind, info.session_date
        # D4 (round 2): a fresh process whose *first* rebalance() tick lands
        # already inside RTH (e.g. a restart resuming an overnight hold)
        # never observes a CLOSED/PRE -> RTH transition -- _last_session_kind
        # starts None, so the ordinary crossing test below never becomes
        # true for it, and the gap stop would stay permanently disarmed for
        # that session even though S5 already seeded a real prior RTH close
        # from the ledger. Treat "first tick ever, already RTH, and a
        # persisted prior close exists for at least one symbol" as an
        # arming event too, using the same crossed_into_rth branch a real
        # crossing would take (it only ever reads self._prior_rth_close /
        # self.policy.latest, both already populated by then).
        first_tick_already_rth = (self._last_session_kind is None and kind == SessionKind.RTH
                                  and bool(self._prior_rth_close))
        crossed_into_rth = kind == SessionKind.RTH and (
            first_tick_already_rth
            or (self._last_session_kind is not None and self._last_session_kind != SessionKind.RTH))
        crossed_out_of_rth = self._last_session_kind == SessionKind.RTH and kind != SessionKind.RTH
        if crossed_into_rth:
            self._gap_stop_applied = set()
            self._gap_risk_stop_price = {}
            self._gap_bps = {}
            self._gap_arm_pending = {symbol for symbol, qty in held.items() if qty > 0}
        if kind == SessionKind.RTH and self._gap_arm_pending:
            try:
                expected_prior_date = previous_trading_day(today)
            except ValueError:
                expected_prior_date = None
            for symbol in list(self._gap_arm_pending):
                qty = held.get(symbol, 0)
                if qty <= 0:
                    self._gap_arm_pending.discard(symbol)
                    continue
                prior_close = self._prior_rth_close.get(symbol)
                if prior_close is None:
                    self._gap_arm_pending.discard(symbol)  # nothing to ever arm against this session
                    continue
                # D3 (round 4): only arm against a prior close whose
                # recorded session_date is exactly the trading day
                # immediately before today's RTH session -- a close from
                # any other date (stale persisted value, an idle ledger, a
                # malformed/unparseable pre-D3 record already dropped by
                # Ledger.prior_rth_closes()) is unusable.
                prior_date = self._prior_rth_close_session_date.get(symbol)
                if expected_prior_date is None or prior_date != expected_prior_date:
                    self._gap_arm_pending.discard(symbol)
                    self.event_sink({"type": "stale_prior_close_ignored", "symbol": symbol,
                                     "prior_close_session_date": str(prior_date) if prior_date else None,
                                     "expected_session_date": str(expected_prior_date) if expected_prior_date else None})
                    continue
                quote = self.policy.latest.get(symbol)
                # D2 (round 4): the quote used to DERIVE the armed stop
                # price was never age-checked at all. Apply the same
                # freshness window every other order path in this file
                # uses; a symbol with only a stale/future-stamped quote at
                # this tick simply stays pending and is retried on the
                # next RTH tick, not silently skipped for the rest of the
                # session.
                if (quote is None or now - quote.timestamp > self.policy.config.quote_age_seconds
                        or now < quote.timestamp - QUOTE_FUTURE_TOLERANCE_SECONDS):
                    continue
                # D3 (round 6): round the midpoint to the same tick
                # precision the capture side already uses (_round_to_tick)
                # -- a raw (bid+ask)/2 division can otherwise land on more
                # than the 9 decimal digits safety.decimal() accepts,
                # exactly the capture-side hazard D4 (round 5) fixed, just
                # on the arming side instead.
                session_open = self._round_to_tick((Decimal(str(quote.bid)) + Decimal(str(quote.ask))) / 2)
                try:
                    # D3 (round 5, decisive): PolicyConfig.stop_bps is a
                    # plain Python float (strategies_v1.PolicyConfig's real
                    # field type); safety.decimal() -- called internally by
                    # evaluate_gap_risk -- explicitly rejects float
                    # (`type(value) not in (str, int, Decimal)`), raising
                    # SafetyError immediately for every real (non-test-fake)
                    # PolicyConfig. str(...) at this boundary converts
                    # explicitly instead of relying on evaluate_gap_risk's
                    # own (float-rejecting) conversion.
                    gap = evaluate_gap_risk(prior_close, session_open, str(self.policy.config.stop_bps))
                except Exception as error:
                    # D3 (round 6): a failed evaluation used to permanently
                    # discard the symbol from _gap_arm_pending -- one bad
                    # tick (e.g. a transient precision/parse issue) meant
                    # no arming for the rest of the RTH session, with no
                    # trace of why. Keep it pending for retry on the next
                    # RTH tick instead, and record why this attempt failed.
                    self.event_sink({"type": "gap_arm_evaluation_failed", "symbol": symbol,
                                     "reason": str(error)})
                    continue
                self._gap_bps[symbol] = gap["gap_bps"]
                # D4 (round 4): evaluate_gap_risk's own gap_bps used to be
                # computed and discarded -- the stop armed for ANY gap
                # (including a gap up, or a negligible one). Only arm when
                # the adverse (downward) magnitude is at least the
                # configured trigger. D3 (round 5): gap_stop_trigger_bps is
                # also a plain float -- Decimal does not support direct
                # rich comparison with float (raises TypeError) -- convert
                # explicitly via str() here too.
                if -gap["gap_bps"] >= Decimal(str(self.policy.config.gap_stop_trigger_bps)):
                    self._gap_risk_stop_price[symbol] = gap["stop_price"]
                self._gap_arm_pending.discard(symbol)
        triggered = set()
        if kind == SessionKind.RTH:
            for symbol, qty in held.items():
                if qty <= 0 or symbol in self._gap_stop_applied:
                    continue
                stop_price = self._gap_risk_stop_price.get(symbol)
                quote = self.policy.latest.get(symbol)
                # D2 (round 3): the trigger used to read policy.latest with
                # no quote-age guard at all, unlike every other order path
                # in this file (rebalance()'s own action loop, replace_exit,
                # _submit_replacement_exit) -- a stale quote could still
                # trip the gap stop. Apply the identical freshness window
                # (same QUOTE_FUTURE_TOLERANCE_SECONDS/quote_age_seconds
                # those paths use) here too.
                if (stop_price is None or quote is None
                        or now - quote.timestamp > self.policy.config.quote_age_seconds
                        or now < quote.timestamp - QUOTE_FUTURE_TOLERANCE_SECONDS):
                    continue
                if Decimal(str(quote.bid)) <= stop_price:
                    # D2 (round 3)/D1 (round 4): fire-once is no longer
                    # marked here, or on a bare replace_exit "cancel
                    # requested" outcome -- rebalance()/_submit_replacement_exit
                    # mark self._gap_stop_applied only once the exit order
                    # for this symbol is actually submitted (D6, round 4:
                    # and only when the full held quantity was submitted,
                    # not truncated by max_shares).
                    triggered.add(symbol)
        if crossed_out_of_rth:
            self._gap_risk_stop_price = {}
            # D2 (round 5): seed the capture retry set for this crossing;
            # `today` here is the RTH session date that just ended (this
            # tick's own session_at().session_date, still the same
            # calendar day as the RTH session -- POST is the ordinary
            # case), pinned in _prior_close_capture_session_date so a
            # later retry tick (which may itself land on a different
            # calendar day, e.g. after midnight) still tags the eventual
            # capture with the correct originating session date.
            self._prior_close_capture_pending = {symbol for symbol, qty in held.items() if qty > 0}
            self._prior_close_capture_session_date = today
        if kind != SessionKind.RTH and self._prior_close_capture_pending:
            capture_date = self._prior_close_capture_session_date or today
            for symbol in list(self._prior_close_capture_pending):
                if held.get(symbol, 0) <= 0:
                    self._prior_close_capture_pending.discard(symbol)
                    continue
                quote = self.policy.latest.get(symbol)
                # D3 (round 4)/D2 (round 5): guard the capture itself with
                # the same freshness window -- an unguarded/stale/
                # future-stamped quote used to be captured (and persisted)
                # as "the" prior close unconditionally. A symbol whose
                # quote is still stale simply stays pending and is retried
                # on the next non-RTH tick, instead of never being
                # captured for this crossing at all.
                if (quote is None or now - quote.timestamp > self.policy.config.quote_age_seconds
                        or now < quote.timestamp - QUOTE_FUTURE_TOLERANCE_SECONDS):
                    continue
                # D4 (round 5): round the midpoint to the same tick
                # precision reserve_intent enforces (strategies_v1.
                # limit_price/safety.py's own price_increment check) --
                # (bid+ask)/2 can otherwise land on more than the 9
                # decimal digits safety.decimal() accepts (e.g. bid/ask
                # each already at max precision with differing last
                # digits), which used to raise out of
                # record_prior_rth_close uncaught.
                price = self._round_to_tick((Decimal(str(quote.bid)) + Decimal(str(quote.ask))) / 2)
                self._prior_rth_close[symbol] = price
                self._prior_rth_close_session_date[symbol] = capture_date
                self._prior_close_capture_pending.discard(symbol)
                # S5: persist alongside the in-memory copy so a fresh
                # process (resuming a held overnight position) still has
                # this close available at the next RTH crossing. D3 (round
                # 4): now also carries session_date and the capturing
                # quote's own market-clock ts_ns. D4 (round 5): never let
                # a persistence failure (e.g. the rounded price still out
                # of decimal()'s bounds for some other reason) raise into
                # rebalance() -- the in-memory copy above still lets this
                # process's own gap-risk arming work even if the durable
                # write failed; a fresh process simply would not see it.
                try:
                    self.ledger.record_prior_rth_close(symbol, price, capture_date.isoformat(),
                                                       int(quote.timestamp * 1_000_000_000))
                except SafetyError as error:
                    self.event_sink({"type": "prior_close_persist_failed", "symbol": symbol,
                                     "reason": str(error)})
                else:
                    self.event_sink({"type": "prior_close_captured", "symbol": symbol,
                                     "session_date": str(capture_date)})
        if crossed_into_rth and self._prior_close_capture_pending:
            # D2 (round 5): any symbol whose capture never resolved before
            # the NEXT RTH session opened is abandoned for that prior
            # crossing -- it simply has no usable prior close this session
            # (the ordinary "nothing to arm against" path above already
            # handles that), not retried indefinitely across sessions.
            for symbol in self._prior_close_capture_pending:
                self.event_sink({"type": "prior_close_capture_abandoned", "symbol": symbol})
            self._prior_close_capture_pending = set()
        self._last_session_kind = kind
        return triggered

    @staticmethod
    def _round_to_tick(price):
        """D4 (round 5): the same tick-precision convention safety.py's
        reserve_intent enforces on every order's own limit price
        (quantize to $0.01 at/above $1, $0.0001 below) -- the closest
        proxy this engine has to "the instrument's tick precision" for a
        captured midpoint, which is not itself an order and so never
        passes through reserve_intent's own check."""
        price = Decimal(str(price))
        tick = Decimal("0.01") if price >= 1 else Decimal("0.0001")
        return price.quantize(tick)

    def _operational_status(self, now) -> OperationalStatus:
        """Real, already-observed safety/transport/reconciliation state, fed
        to the selector (only consulted when policy.selector is set, i.e.
        rotation is enabled -- see runner.strategy_pool_and_selector).

        - kill_switch: the same STOP file safety.py's Ledger checks.
        - risk_halted / reconciled: Ledger.halted_reason() -- "recovery_only"
          means "needs reconciliation", not a risk halt (see safety.py's
          begin_recovery/begin_next_trial); any other non-None reason is a
          genuine risk halt.
        - transport_frozen: the transport's own health.frozen flag, when a
          transport was provided.
        - state_fresh: every currently held symbol has an observed quote no
          older than the policy's configured quote_age_seconds, allowing the
          same QUOTE_FUTURE_TOLERANCE_SECONDS clock-skew slack the engine's
          own _features()/order-freshness checks use (a quote timestamped
          slightly ahead of `now` is not "stale").
        """
        reason = self.ledger.halted_reason()
        if self.transport is not None:
            health = self.transport.health
            # Not every port's health dict carries "frozen" (e.g. simulation.
            # SimulatedPort only has ready/simulation/reason); read
            # defensively so rotation doesn't KeyError against those ports.
            transport_frozen = bool(health.get("frozen")) or (health.get("ready") is False) \
                or bool(health.get("reason"))
        else:
            transport_frozen = False
        held = self.positions()
        state_fresh = all(
            symbol in self.policy.latest
            and -QUOTE_FUTURE_TOLERANCE_SECONDS <= now - self.policy.latest[symbol].timestamp <= self.policy.config.quote_age_seconds
            for symbol in held)
        return OperationalStatus(
            kill_switch=Path(self.stop_file or DEFAULT_STOP).exists(),
            risk_halted=reason not in (None, "recovery_only"),
            transport_frozen=transport_frozen,
            reconciled=reason != "recovery_only",
            state_fresh=state_fresh)

    def _leverage_inputs(self, now) -> LeverageInputs:
        """G-e: only called from rebalance() when self.policy.leverage_policy
        is not None. `session` is None for a timestamp outside the frozen
        session calendar (LeverageInputs consumers fail closed to 0 on an
        unclassifiable session, the same contract as safety.Ledger's own
        independent envelope check). `kill_switch` is deliberately broader
        than OperationalStatus.kill_switch above: it also trips on ANY
        halted_reason (not just a non-recovery_only one) and on a frozen or
        not-ready transport, since a leverage entry must stop on strictly
        more conditions than the ordinary rotation kill switch.
        """
        try:
            session = session_at(datetime.fromtimestamp(now, timezone.utc)).kind.value
        except ValueError:
            session = None
        acct = self.ledger.accounting()
        reason = self.ledger.halted_reason()
        health = getattr(self.transport, "health", {}) if self.transport is not None else {}
        kill = (Path(self.stop_file or DEFAULT_STOP).exists() or reason is not None
                or bool(health.get("frozen")) or health.get("ready") is False)
        return LeverageInputs(session, acct.drawdown_usd / self.ledger.limits.max_drawdown_usd, kill,
                              self.account_multiplier, acct.pending_buy_notional_usd)

    def rebalance(self, now=None, *, force_exit=False):
        """Called on the native owner loop, never a socket thread."""
        now = self._clock() if now is None else now
        self.policy.sync_positions(self.positions(), now)
        for client_id in list(self.pending):
            self._finish_if_terminal(client_id)
        operational = self._operational_status(now) if self.policy.selector is not None else None
        decide_kwargs = {"operational": operational}
        # getattr, not a direct attribute access: self.policy is not always
        # a real strategies.AdaptivePolicy instance -- a duck-typed test
        # double (predating G-e) providing only the narrower pre-G-e
        # interface (config/latest/selector/decide/...) must still work
        # unchanged, with leverage treated as absent.
        if getattr(self.policy, "leverage_policy", None) is not None:
            decide_kwargs["leverage_inputs"] = self._leverage_inputs(now)
        decision = self.policy.decide(now, allow_entries=self.enabled, force_exit=force_exit,
                                       **decide_kwargs)
        if decision is None or not self.started:
            return None
        # If this tick's selector decision liquidates (FLATTEN_BEFORE_SWITCH),
        # policy.decide() already force-exited every holding above; propagate
        # that into this method's own force_exit so (a) no fresh entry is
        # proposed below despite self.enabled, and (b) any resting entry
        # order is cancelled now, not left pending past the flatten.
        liquidating = bool(self.policy.selector is not None and self.policy.last_selector_decision
                          and self.policy.last_selector_decision.liquidate)
        if liquidating:
            force_exit = True
            # cancel_expired's timeout clause fires for every resting order
            # once elapsed time is >= timeout; timeout=0 would therefore
            # cancel resting sells too. Use an unreachable timeout so only
            # the all_entries clause (buy-side entries) applies here.
            self.cancel_expired(now, float("inf"), all_entries=True)
        held = {s: Decimal(p["qty"]) for s, p in self.positions().items()}
        busy = {i.symbol for i in self.ledger.unresolved()}
        busy.update(item["symbol"] for item in self.pending.values())
        # D4 (round 4): _gap_risk_stop_symbols is now called before the
        # decision event is emitted (it used to run after) so gap_bps --
        # computed inside it whenever a symbol's gap is evaluated, armed
        # or not -- can be included in that same event below, instead of
        # needing a separate event type.
        gap_stop_symbols = self._gap_risk_stop_symbols(now, held)
        # Trading-lane audit gap #8: evaluated after gap risk (whose own
        # arming/capture state is independent of it) but consumed first,
        # below -- see corporate_actions.py's module docstring for the full
        # precedence contract. `candidate_symbols` is this tick's targets,
        # the only symbols a fresh/added entry could apply to.
        ca_block_entry, ca_must_flatten = self._corporate_action_guard_symbols(
            now, held, decision.targets.keys())
        # finding 10 (2026-09-24 fix round): a resting BUY order for a
        # symbol newly blocked this tick must not be left to fill after the
        # block was decided -- cancel it immediately, the same treatment
        # force_exit's all_entries=True already gives every resting buy.
        if ca_block_entry:
            self.cancel_expired(now, float("inf"), symbols=ca_block_entry)
        decision_event = {"type": "decision", "timestamp": now, "regime": decision.regime,
                          "targets": decision.targets, "exits": decision.exits,
                          "effective_leverage": decision.effective_leverage,
                          "signals": [{"symbol": s.symbol, "family": s.family,
                                       "edge_bps": s.edge_bps, "score": s.score} for s in decision.signals],
                          "gap_bps": {symbol: str(bps) for symbol, bps in self._gap_bps.items()}}
        # NIT finding 11 (2026-09-24 fix round): these two keys are only
        # ever added when a corporate-action guard is actually wired in --
        # `self.corporate_action_guard is None` (the default) now leaves
        # this decision event byte-identical to before this control
        # existed, as the module docstring above already claims (the claim
        # was previously false: both keys were always present, even with
        # the guard off).
        if self.corporate_action_guard is not None:
            decision_event["corporate_action_block_entry"] = sorted(ca_block_entry)
            decision_event["corporate_action_must_flatten"] = sorted(ca_must_flatten)
        if getattr(self.policy, "leverage_policy", None) is not None:
            decision_event["leverage_ceiling"] = self.policy.last_leverage_ceiling
        self.event_sink(decision_event)
        # Exits consume capacity before fresh entries; one outstanding order per
        # symbol also prevents sell-before-entry-terminal and oversell races.
        # A D5 gap-risk stop forces a full exit even if the ordinary decision
        # targets would otherwise have kept (or grown) the position.
        # D2 (round 2): a partial take-profit (exits.py's take_profit_fraction
        # < 1.0, surfaced via policy.last_exit_fractions) previously had no
        # engine reader here -- the full held-vs-target delta was always
        # sold, so a 0.5 fraction was inert. Only scale the sell quantity
        # for a symbol actually present in decision.exits this tick (a
        # generic held>target reduction with no recorded exit -- unreachable
        # today, see strategies_v1._decide_core's portfolio_rotation
        # fallback, but defended anyway -- always sells the full delta,
        # fraction=1.0); the unsold remainder simply stays held and is
        # re-evaluated (e.g. by the trailing rule) on the next tick once
        # sync_positions reflects the reduced broker quantity.
        actions = []
        for s, qty in held.items():
            target = decision.targets.get(s, 0)
            if qty <= target or s in gap_stop_symbols or s in ca_must_flatten:
                continue
            delta = qty - target
            reason = decision.exits.get(s, "rebalance")
            fraction = self.policy.last_exit_fractions.get(s, 1.0) if s in decision.exits else 1.0
            if fraction < 1 and delta > 0:
                sell_qty = (delta * Decimal(str(fraction))).to_integral_value(rounding="ROUND_FLOOR")
                if sell_qty < 1:
                    sell_qty = Decimal(1)
                sell_qty = min(sell_qty, delta)
            else:
                sell_qty = delta
            actions.append((s, "sell", sell_qty, reason))
        # Trading-lane audit gap #8: a confirmed-or-fail-closed corporate
        # action forces a full exit through this same engine-layer forced-
        # sell path, ranked ahead of gap_risk_stop (see corporate_actions.py's
        # module docstring for why); it is not mutually exclusive with
        # gap_stop_symbols in principle, but `ca_must_flatten` was already
        # excluded from the ordinary rebalance-delta loop above so a symbol
        # never gets two competing sell actions from this method.
        actions += [(s, "sell", held[s], "corporate_action_flatten") for s in ca_must_flatten if held.get(s, 0) > 0]
        # LOW finding 9 (2026-09-24 fix round): a symbol both gap-stopped
        # AND corporate-action-flattened this tick used to get a SECOND
        # competing sell action here (this loop did not exclude
        # ca_must_flatten), even though it was already fully sold above --
        # exclude it, the same way the held-vs-target loop above already
        # excludes both sets.
        actions += [(s, "sell", held[s], "gap_risk_stop")
                   for s in gap_stop_symbols - ca_must_flatten if held.get(s, 0) > 0]
        if self.enabled and not force_exit:
            actions += [(s, "buy", qty - held.get(s, 0),
                         next((x.family for x in decision.signals if x.symbol == s), "rebalance"))
                        for s, qty in decision.targets.items()
                        if qty > held.get(s, 0) and s not in ca_block_entry]
        for symbol, side, quantity, reason in actions:
            quote = self.policy.latest.get(symbol)
            if not quote or now - quote.timestamp > self.policy.config.quote_age_seconds \
                    or now < quote.timestamp - QUOTE_FUTURE_TOLERANCE_SECONDS:
                # D2 (round 3): a gap_risk_stop action that fails this same
                # freshness check must NOT be marked fire-once applied --
                # the stop stays armed and is re-evaluated (against a
                # hopefully-fresher quote) on the next tick.
                continue
            if symbol in busy:
                # G-f deliverable 2: a resting exit already covers this
                # symbol (the pre-existing one-outstanding-order-per-symbol
                # rule below never double-submits). If this tick's reason
                # implies a different price_rule than that resting order's
                # (e.g. exits.py's trailing rule ratcheted), replace it
                # instead of silently doing nothing until it happens to
                # fill/expire on its own.
                # Round 8: cancel-then-replace is opt-in on
                # PolicyConfig.exit_replace_enabled (default False, same
                # pattern as gap_stop_enabled). Disabled, this symbol is
                # simply skipped this tick -- the pre-G-f behavior: the
                # existing resting order is left exactly as-is until it
                # fills/expires/is cancelled on its own; replace_exit is
                # never called at all.
                if side == "sell" and self.policy.config.exit_replace_enabled:
                    # D1 (round 4): replace_exit's outcome is one of
                    # "cancel_requested"/"noop"/"refused" -- never
                    # "submitted" itself (the actual replacement order is
                    # only submitted later, asynchronously, from
                    # _submit_replacement_exit once the cancel is
                    # acknowledged, which is also where fire-once is now
                    # marked for this path -- see its own D6 truncation
                    # guard there too). Marking fire-once here on
                    # "cancel_requested" alone used to consume the gap
                    # stop before any replacement order had reached the
                    # broker, or even before it was known whether the
                    # eventual replacement would itself be refused (stale
                    # quote, cap, reject).
                    self.replace_exit(symbol, now, quantity, reason)
                continue
            self.sequence += 1
            client_id = f"adp-{self.trial_id}-{self.sequence:07d}"
            price_str = limit_price(quote.bid, quote.ask, side)
            order = self.order_factory.limit(
                InstrumentId.from_str(symbol + ".ALPACA"),
                OrderSide.BUY if side == "buy" else OrderSide.SELL,
                Quantity.from_str(str(min(quantity, self.policy.config.max_shares))),
                Price.from_str(price_str),
                time_in_force=TimeInForce.DAY, client_order_id=ClientOrderId(client_id),
                tags=[f"strategy={reason}", f"reason={reason}"])
            # D1 (round 5): "reason" is recorded on every pending entry (not
            # just sells) so on_order_{rejected,denied,expired,cancel_rejected}
            # can identify a gap_risk_stop order and clear fire-once for it.
            self.pending[client_id] = {"symbol": symbol, "side": side, "created": now, "reason": reason}
            if side == "sell":
                # D1 (round 2): record both the price_rule and the actual
                # computed limit price, so a later replace_exit call has a
                # real baseline to compare a ratcheted price against (not
                # just the price_rule label, which stays "trailing" for
                # every tick of a trailing-stop ratchet -- see
                # replace_exit's docstring).
                self.pending[client_id]["price_rule"] = REASON_PRICE_RULE.get(reason, "market")
                self.pending[client_id]["price"] = price_str
            busy.add(symbol)
            self.submit_order(order)
            # D2 (round 3): mark fire-once applied only now that the order
            # has actually been submitted, not preemptively when the stop
            # was first evaluated inside _gap_risk_stop_symbols. D6 (round
            # 4): only when the FULL held quantity was actually submitted
            # -- `Quantity.from_str(str(min(quantity, max_shares)))` above
            # silently truncates a gap_risk_stop sell larger than
            # max_shares, and marking fire-once regardless used to leave
            # the untruncated remainder permanently unprotected for the
            # rest of the RTH session.
            if reason == "gap_risk_stop" and quantity <= self.policy.config.max_shares:
                self._gap_stop_applied.add(symbol)
        return decision

    def _resting_exit_client_id(self, symbol):
        """The client_order_id of `symbol`'s resting, not-yet-cancel-
        requested sell order, or None. Two resting sells for the same
        symbol never coexist (the busy-set above), so at most one
        matches."""
        for client_id, info in self.pending.items():
            if info.get("symbol") == symbol and info.get("side") == "sell" and not info.get("cancel_requested"):
                return client_id
        return None

    def replace_exit(self, symbol, now, quantity, reason):
        """Cancel-then-replace `symbol`'s resting exit order (deliverable 2).

        native_adapter.py rejects order modify (see its `_modify_order`),
        so a changed exit price is expressed as cancel + a fresh submit,
        not an in-place amend. Guarded by:

        - busy-set (`_exit_replace_busy`): a symbol already mid
          cancel-then-replace is skipped here so it is never double
          cancelled or double resubmitted from a later tick before the
          broker has acknowledged the first cancel.
        - exit_attempts cap (PolicyConfig.exit_replace_max_attempts, default
          3): once a symbol has been replaced that many times this session,
          further replace_exit calls are refused; the caller (rebalance())
          then simply leaves the stale resting order in place, which is
          the existing pre-G-f behavior and itself eventually resolves via
          the ledger's ordinary fill/expire/recovery path -- not a new
          failure mode.
        - D1 (round 2) price-change gate: replacing used to be gated only
          on the reason's price_rule changing. A ratcheting trailing stop
          recomputes the *same* price_rule ("trailing") every single tick
          while its actual limit price keeps tightening, so gating on
          price_rule alone meant replace_exit could never fire for the
          exact case it exists for. Now a replace fires when EITHER the
          price_rule changed OR the freshly recomputed limit price has
          moved from the resting order's own recorded price by more than
          `PolicyConfig.exit_replace_tolerance_bps` (default 0 = any
          nonzero change at all).
        - D1 (round 2) min-interval gate: `PolicyConfig.
          exit_replace_min_interval_seconds` (default 0 = no minimum)
          bounds how often the same symbol can be replaced, so a
          fast-ratcheting trail cannot cancel/resubmit every tick; the very
          next tick past the interval still replaces at whatever price is
          then current, so a real ratchet is never permanently dropped,
          only rate-limited.
        - residue protection: this method only *initiates* the cancel; the
          replacement is always sized for the *current* full remaining
          quantity (`quantity`, computed by rebalance() from live
          held-vs-target each tick, not the old order's original quantity),
          and is submitted from `on_order_canceled` once the cancel is
          acknowledged. If no fresh quote is available at that moment the
          replacement is skipped for this cycle, not silently dropped
          forever: the symbol leaves `_exit_replace_busy` regardless, so
          the very next rebalance() tick's ordinary exit-action path (which
          always re-derives sell quantity from live held-vs-target,
          independent of this method) resubmits it exactly as it would for
          any other symbol with no resting exit order.
        - D3 (round 2): every mutation of the resting order's own pending
          record happens BEFORE `cancel_order` is called, not after. A
          synchronous cancel acknowledgement (e.g. SimulatedPort, or any
          fake/backtest port whose `cancel_order` invokes
          `on_order_canceled` inline) pops `self.pending[client_id]` during
          this very call; mutating the *same dict object* first means
          `on_order_canceled`'s `pop()` always returns the already-mutated
          record regardless of whether the ack is synchronous or
          asynchronous -- nothing here ever re-reads `self.pending
          [client_id]` after `cancel_order` is called.
        - D5 (round 4) single clock convention: `now` here is the exact
          same value rebalance()/_operational_status/cancel_expired all
          use -- the strategy owner loop's own clock (real wall-clock
          time.time() in live mode, a synthetic/backtest clock in a
          backtest or test). Quote timestamps are market-clock, which in
          live mode is the same clock; there is deliberately no separate
          wall-clock read anywhere in this method or
          _submit_replacement_exit (a round-3 version tried to split the
          freshness check onto raw time.time() while stamping "created"
          on the caller's `now`, which silently broke replacement under
          any non-wall-clock `now` -- e.g. a backtest -- since the
          freshness check would then compare a real wall-clock reading
          against a quote timestamped on the backtest's own clock and
          almost always see it as stale).

        Returns "cancel_requested" if the resting order's cancel was
        requested (the replacement order itself is submitted later,
        asynchronously, from _submit_replacement_exit once the cancel is
        acknowledged -- callers must not treat this as "submitted" for
        fire-once purposes, see D1, round 4), "noop" if nothing needed
        replacing (price and price_rule both unchanged), or "refused"
        (busy, capped, rate-limited, nothing resting, or a non-positive
        quantity).
        """
        if symbol in self._exit_replace_busy or quantity <= 0:
            return "refused"
        attempts = self._exit_attempts.get(symbol, 0)
        if attempts >= self.policy.config.exit_replace_max_attempts:
            return "refused"
        # D1 (round 8): a separate, never-rolled-back cap -- see
        # __init__'s _cancel_reject_counts docstring. Bounds retries
        # against a broker that keeps refusing to cancel this symbol's
        # resting order even though the (rolled-back) exit_attempts
        # budget alone would otherwise let it retry indefinitely.
        if self._cancel_reject_counts.get(symbol, 0) >= self.policy.config.exit_replace_max_attempts:
            return "refused"
        client_id = self._resting_exit_client_id(symbol)
        if client_id is None:
            return "refused"
        min_interval = self.policy.config.exit_replace_min_interval_seconds
        last_replace_at = self._last_replace_at.get(symbol)
        if min_interval > 0 and last_replace_at is not None and now - last_replace_at < min_interval:
            return "refused"
        resting = self.pending[client_id]
        price_rule = REASON_PRICE_RULE.get(reason, "market")
        old_price_rule = resting.get("price_rule", "market")
        quote = self.policy.latest.get(symbol)
        price_changed = False
        if quote is not None:
            new_price = Decimal(limit_price(quote.bid, quote.ask, "sell"))
            old_price = resting.get("price")
            if old_price is None:
                price_changed = True  # no recorded baseline -- treat as changed
            else:
                old_price = Decimal(str(old_price))
                if old_price == 0:
                    price_changed = new_price != old_price
                else:
                    tolerance = Decimal(str(self.policy.config.exit_replace_tolerance_bps))
                    diff_bps = abs(new_price - old_price) / old_price * 10000
                    price_changed = diff_bps > tolerance
        if not price_changed and old_price_rule == price_rule:
            return "noop"  # neither the price nor the price_rule moved
        resting["replace_with"] = {
            "symbol": symbol, "quantity": quantity, "reason": reason, "price_rule": price_rule,
            # D3 (round 7), D1 (round 8): the pre-attempt value of the
            # exit_attempts accounting this call is about to consume, so
            # on_order_cancel_rejected can roll it back if the cancel
            # itself never takes effect (see its own docstring) -- no
            # replacement happens in that case, so charging this attempt
            # would be double-counting a cancel-then-replace that never
            # actually replaced anything. D4 (round 8): the matching
            # `previous_last_replace_at` field (and the write-only
            # `requested_now` field, which _submit_replacement_exit never
            # read -- it always uses the ack-time clock instead, see its
            # own docstring) were both removed: round 8 (D1) stopped
            # rolling `_last_replace_at` back at all, so staging its
            # previous value here served no purpose.
            "previous_attempts": attempts}
        resting["cancel_requested"] = True
        self._exit_replace_busy.add(symbol)
        self._exit_attempts[symbol] = attempts + 1
        self._last_replace_at[symbol] = now
        self.cancel_order(ClientOrderId(client_id))
        return "cancel_requested"

    def _submit_replacement_exit(self, replacement, now):
        """D2 (round 6): `now` is the clock reading AT ACKNOWLEDGEMENT
        time (on_order_canceled's self._clock(), the same clock source
        rebalance() defaults its own `now` from -- see __init__), never a
        frozen request-time value. In live asynchronous operation the
        cancel ack can legitimately arrive well after the request (network
        / broker latency); using a stale request-time value for the
        freshness check would mean any quote arriving more than
        QUOTE_FUTURE_TOLERANCE_SECONDS (0.25s) after the *request* is
        rejected as "from the future" relative to that frozen clock,
        silently skipping every replacement whose ack took any real time
        at all. D4 (round 8): replace_exit used to stage a `requested_now`
        field on `replacement` for exactly that (wrong) purpose; it was
        never actually read here (this method always used the
        acknowledgement-time `now` parameter instead) and has been
        removed as dead/write-only."""
        symbol = replacement["symbol"]
        self._exit_replace_busy.discard(symbol)
        quote = self.policy.latest.get(symbol)
        if (not quote or now - quote.timestamp > self.policy.config.quote_age_seconds
                or now < quote.timestamp - QUOTE_FUTURE_TOLERANCE_SECONDS):
            # No fresh quote right now -- leave it to the next rebalance()
            # tick's ordinary exit-action path (see replace_exit's
            # docstring); this symbol is no longer busy or "resting", so
            # that path is free to act on it. D2 (round 7): the OLD
            # resting order was already successfully cancelled (that is
            # how we got here) -- clear fire-once too if the abandoned
            # replacement was itself a gap_risk_stop exit, see
            # _clear_gap_stop_for_dropped_replacement.
            self._clear_gap_stop_for_dropped_replacement(replacement)
            return
        self.sequence += 1
        client_id = f"adp-{self.trial_id}-{self.sequence:07d}"
        reason = replacement["reason"]
        quantity = replacement["quantity"]
        price_str = limit_price(quote.bid, quote.ask, "sell")
        order = self.order_factory.limit(
            InstrumentId.from_str(symbol + ".ALPACA"), OrderSide.SELL,
            Quantity.from_str(str(min(quantity, self.policy.config.max_shares))),
            Price.from_str(price_str),
            time_in_force=TimeInForce.DAY, client_order_id=ClientOrderId(client_id),
            tags=[f"strategy={reason}", f"reason={reason}", f"price_rule={replacement['price_rule']}"])
        self.pending[client_id] = {"symbol": symbol, "side": "sell", "created": now,
                                   "price_rule": replacement["price_rule"], "price": price_str, "reason": reason}
        self.submit_order(order)
        # D1 (round 4): fire-once is marked here -- once the replacement
        # order has actually been submitted -- not on replace_exit's
        # earlier "cancel_requested" outcome. D6 (round 4): only when the
        # FULL quantity was actually submitted, not truncated by
        # max_shares (see rebalance()'s identical guard on its own direct
        # submit path).
        if reason == "gap_risk_stop" and quantity <= self.policy.config.max_shares:
            self._gap_stop_applied.add(symbol)

    def cancel_expired(self, now, timeout, *, all_entries=False, symbols=None):
        """`symbols` (finding 10, 2026-09-24 fix round): an optional set of
        symbols whose resting BUY orders must be cancelled regardless of
        `timeout`/`all_entries`, the same immediate-cancel treatment
        `all_entries=True` already gives every resting buy -- used by
        rebalance() to cancel a resting entry the corporate-action guard
        has just newly blocked this tick, so a symbol found to carry an
        in-range action never gets a stale, already-submitted buy filled
        after the block was decided."""
        for client_id, info in list(self.pending.items()):
            if info.get("cancel_requested"):
                continue
            if (now - info["created"] >= timeout or (all_entries and info["side"] == "buy")
                    or (symbols and info["side"] == "buy" and info["symbol"] in symbols)):
                self.cancel_order(ClientOrderId(client_id))
                info["cancel_requested"] = True
