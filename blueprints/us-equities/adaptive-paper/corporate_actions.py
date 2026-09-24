"""Interim corporate-action guard for the adaptive-paper engine (trading-lane
audit gap #8): positions were not adjusted for corporate actions even though
a `held_overnight` trial can hold a position across a session boundary. This
module adds that missing control: block new entries and force a pre-close
flatten for any symbol with a split, reverse split, cash/stock dividend,
spin-off, merger or name change whose governing date falls inside the
position's possible hold horizon (the next session, for an overnight hold).

Layering (mirrors transport.py's own network-boundary convention):
  - `ActionRecord`, `evaluate_guard`, `CorporateActionMonitor` are pure,
    offline, no-network logic -- independently unit-tested with a fake
    `source`, no credentials or alpaca-py import required.
  - `AlpacaCorporateActionsSource` is the only piece that imports alpaca-py,
    and only when actually constructed with real credentials. Its
    `_TYPE_FIELD_MAP` was verified field-for-field against the installed
    alpaca-py==0.44.0 package on this host (`alpaca/data/models/
    corporate_actions.py`, `alpaca/data/requests.py`,
    `alpaca/data/historical/corporate_actions.py`) -- a dated, reproducible
    local read of the pinned SDK revision, not a live network fetch; the
    endpoint itself (`GET /v1/corporate-actions` via
    `alpaca.data.historical.corporate_actions.CorporateActionsClient`) is
    never called by the offline test suite and carries no acceptance claim
    beyond "the request/response shapes this wrapper assumes match the
    installed SDK's own dataclasses".

Precedence (see native_strategy.AdaptiveStrategy.rebalance, where this
guard's result is consumed):
  1. safety.py's STOP file / risk halts and exits.py's own `force_exit`
     tier (trial/session end, threaded into rebalance() from outside) --
     both already stop or force-exit the *whole* trial regardless of any
     single symbol's corporate-action status, and are evaluated first.
  2. This guard's `must_flatten` -- evaluated and applied (as a forced full
     sell, through the same engine-layer forced-sell path D5's gap-risk
     stop already uses) ABOVE gap_risk_stop, because a scheduled
     corporate-action date is a known calendar fact fixed ahead of time,
     not a live threshold breach discovered this tick. Unlike gap_risk_stop
     it is deliberately NOT fire-once: it is re-evaluated and re-applied
     every tick for as long as the symbol is still held and still in
     range, exactly matching "must flatten before the regular close of the
     session before that date" (a partial fill or a cancelled/rejected
     attempt must not leave the position permanently unprotected for the
     rest of the session, the same reasoning exits.py's docstring gives
     for why gap-risk/overnight rules "stay exactly where they already
     lived" instead of joining the per-holding exits.py chain).
  3. D5 gap_risk_stop (native_strategy._gap_risk_stop_symbols), unchanged.
  4. exits.py's own per-holding chain (`exits.DEFAULT_PLAN`), unchanged.
  5. This guard's `block_entry` is checked independently, after
     strategies_v1.AdaptivePolicy.decide() has already picked this tick's
     targets: any symbol in `block_entry` has its target-increase (a new
     buy, or growing an existing position) dropped before order submission.
     This is a post-hoc filter, not a chain rule, because unlike
     gap_risk_stop (only ever a stop on an existing holding) this guard
     must also gate admission of a symbol never held before.

Fail-closed contract: a symbol whose lookup failed, was ambiguous, or was
simply never attempted (missing from the source's result, or the cached
result has gone stale past `CorporateActionMonitor.max_age_seconds`) is
always treated as `block_entry=True, needs_attention=True` -- never as "no
action". This module never guesses at a corporate action from partial data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import time as _time
from typing import Mapping

# Canonical action types this guard reasons about. Real alpaca-py corporate-
# action records collapse into these (see AlpacaCorporateActionsSource);
# unit_split/redemption/worthless_removal/rights_distribution -- corporate
# actions not explicitly named in the brief -- fall into "other" rather than
# being silently ignored, consistent with the fail-closed/no-guessing intent.
ACTION_TYPES = frozenset({
    "forward_split", "reverse_split", "cash_dividend", "stock_dividend",
    "spin_off", "merger", "name_change", "other",
})

# Sentinel lookup outcomes for a symbol, distinct from "resolved (possibly
# empty) list of ActionRecord".
LOOKUP_FAILED = "lookup_failed"
LOOKUP_AMBIGUOUS = "lookup_ambiguous"


class CorporateActionLookupError(Exception):
    """Raised by a source's fetch() on any network/parse/credential failure.
    Never carries a credential value; only a bounded reason string."""


@dataclass(frozen=True)
class ActionRecord:
    """One corporate action for one symbol, already normalized to the
    single governing date this guard checks against (`action_date`): the
    ex_date for a split/dividend/spin-off, the effective_date for a merger,
    the process_date for a name change or another type with no ex_date/
    effective_date of its own. Callers (a source's fetch()) resolve that
    choice before constructing this record -- this module does not itself
    pick between competing date fields at guard-evaluation time."""
    symbol: str
    action_type: str
    action_date: date
    source_id: str = ""

    def __post_init__(self):
        if self.action_type not in ACTION_TYPES:
            raise ValueError(f"unknown_corporate_action_type:{self.action_type}")


@dataclass(frozen=True)
class GuardDecision:
    symbol: str
    block_entry: bool
    must_flatten: bool
    needs_attention: bool
    reason: str | None
    action_type: str | None = None
    action_date: date | None = None


def evaluate_guard(*, today: date, next_session_date: date, held_symbols, candidate_symbols,
                   lookup_results: Mapping[str, object]) -> dict:
    """Pure decision function: no I/O, no clock read, no broker/session
    lookup of its own.

    `lookup_results` maps symbol -> either `LOOKUP_FAILED`/`LOOKUP_AMBIGUOUS`,
    or a (possibly empty) list/tuple of `ActionRecord`. A symbol absent from
    `lookup_results` entirely is treated exactly like `LOOKUP_FAILED` (fail
    closed on missing data, never silently "no action").

    `next_session_date` is the caller-supplied possible hold horizon for an
    overnight trial: a position opened (or already held) as of `today` can
    be carried to `next_session_date`'s open, so an action whose
    `action_date` falls on either `today` or `next_session_date` is in
    range and blocks/flattens. A qualifying action on `today` covers both
    "already holding into an action landing today" (should already have
    been flattened by a prior tick -- still enforced) and "an action was
    just discovered same-day, entries must stop immediately".
    """
    held = set(held_symbols)
    decisions = {}
    for symbol in held | set(candidate_symbols):
        result = lookup_results.get(symbol, LOOKUP_FAILED)
        if result in (LOOKUP_FAILED, LOOKUP_AMBIGUOUS):
            decisions[symbol] = GuardDecision(
                symbol=symbol, block_entry=True, must_flatten=False, needs_attention=True,
                reason=f"corporate_action_{result}")
            continue
        qualifying = [record for record in result if record.action_date in (today, next_session_date)]
        if not qualifying:
            decisions[symbol] = GuardDecision(symbol=symbol, block_entry=False, must_flatten=False,
                                              needs_attention=False, reason=None)
            continue
        chosen = min(qualifying, key=lambda record: record.action_date)
        decisions[symbol] = GuardDecision(
            symbol=symbol, block_entry=True, must_flatten=symbol in held, needs_attention=False,
            reason=f"corporate_action_{chosen.action_type}", action_type=chosen.action_type,
            action_date=chosen.action_date)
    return decisions


class CorporateActionMonitor:
    """Owns the periodic refresh and fail-closed staleness bound around one
    lookup `source` (an object exposing `.fetch(symbols, start, end) ->
    dict[symbol, list[ActionRecord]]`, raising `CorporateActionLookupError`
    on any failure). Never talks to a broker itself -- purely a cache with a
    fail-closed staleness policy, injectable for offline tests with a fake
    `source`. Every method is safe to call from the native owner loop; no
    method sleeps or blocks beyond the source's own `fetch` call.

    `refresh_seconds` bounds how often `refresh()` actually calls
    `source.fetch` (a corporate-actions calendar does not change tick to
    tick). `max_age_seconds` bounds how long a successful result is still
    trusted by `evaluate()`: past that age, or before any refresh has ever
    succeeded, every relevant symbol fails closed exactly like a lookup
    failure -- never silently reusing a result that might now be stale.
    """

    def __init__(self, source, *, refresh_seconds=900.0, max_age_seconds=3600.0, clock=None):
        self.source = source
        self.refresh_seconds = refresh_seconds
        self.max_age_seconds = max_age_seconds
        self._clock = clock or _time.time
        self._last_attempt = None
        self._last_success = None
        self._results: dict = {}

    def refresh(self, symbols, *, start: date, end: date, now=None):
        """Idempotent within `refresh_seconds` for a symbol set already
        covered by the last successful fetch; always safe to call every
        tick. Never raises -- a fetch failure marks every requested symbol
        `LOOKUP_FAILED` for this and every subsequent `evaluate()` until a
        later refresh succeeds."""
        now = self._clock() if now is None else now
        symbols = set(symbols)
        if (self._last_attempt is not None and now - self._last_attempt < self.refresh_seconds
                and symbols.issubset(self._results.keys())):
            return
        self._last_attempt = now
        try:
            fetched = self.source.fetch(sorted(symbols), start, end)
        except CorporateActionLookupError:
            for symbol in symbols:
                self._results[symbol] = LOOKUP_FAILED
            return
        except Exception:
            # Fail closed on any unexpected error too -- never guess.
            for symbol in symbols:
                self._results[symbol] = LOOKUP_FAILED
            return
        self._last_success = now
        for symbol in symbols:
            self._results[symbol] = fetched.get(symbol, [])

    def evaluate(self, *, today: date, next_session_date: date, held_symbols, candidate_symbols,
                now=None) -> dict:
        now = self._clock() if now is None else now
        relevant = set(held_symbols) | set(candidate_symbols)
        stale = self._last_success is None or now - self._last_success > self.max_age_seconds
        if stale:
            results = {symbol: LOOKUP_FAILED for symbol in relevant}
        else:
            results = {symbol: self._results.get(symbol, LOOKUP_FAILED) for symbol in relevant}
        return evaluate_guard(today=today, next_session_date=next_session_date,
                              held_symbols=held_symbols, candidate_symbols=candidate_symbols,
                              lookup_results=results)


# type_key (alpaca-py CorporateActionsSet.data key) -> (symbol attribute
# names that identify an affected tradable symbol, the attribute name that
# is this guard's governing date, the canonical ACTION_TYPES bucket).
# Verified against the installed alpaca-py==0.44.0
# alpaca/data/models/corporate_actions.py dataclass fields on this host.
_TYPE_FIELD_MAP = {
    "forward_splits": (("symbol",), "ex_date", "forward_split"),
    "reverse_splits": (("symbol",), "ex_date", "reverse_split"),
    "unit_splits": (("old_symbol", "new_symbol"), "effective_date", "other"),
    "stock_dividends": (("symbol",), "ex_date", "stock_dividend"),
    "cash_dividends": (("symbol",), "ex_date", "cash_dividend"),
    "spin_offs": (("source_symbol", "new_symbol"), "ex_date", "spin_off"),
    "cash_mergers": (("acquirer_symbol", "acquiree_symbol"), "effective_date", "merger"),
    "stock_mergers": (("acquirer_symbol", "acquiree_symbol"), "effective_date", "merger"),
    "stock_and_cash_mergers": (("acquirer_symbol", "acquiree_symbol"), "effective_date", "merger"),
    "redemptions": (("symbol",), "process_date", "other"),
    "name_changes": (("old_symbol", "new_symbol"), "process_date", "name_change"),
    "worthless_removals": (("symbol",), "process_date", "other"),
    "rights_distributions": (("source_symbol", "new_symbol"), "ex_date", "other"),
}


class AlpacaCorporateActionsSource:
    """Real alpaca-py 0.44.0 `alpaca.data.historical.corporate_actions.
    CorporateActionsClient` wrapper -- the only network-touching piece of
    this module, imported lazily (matching transport.py's own convention)
    so the rest of this module stays importable, and independently unit-
    testable, without alpaca-py installed. Constructed with the same
    key/secret runner.credentials() already returns; never logs, stores, or
    raises them in any exception message."""

    def __init__(self, api_key, secret_key):
        from alpaca.data.historical.corporate_actions import CorporateActionsClient
        self._client = CorporateActionsClient(api_key, secret_key)

    def fetch(self, symbols, start: date, end: date) -> dict:
        """Returns `{symbol: [ActionRecord, ...]}` for exactly the
        requested `symbols` (every requested symbol is present, possibly
        with an empty list); any symbol/type this wrapper cannot map is
        dropped from the per-symbol list, never silently invented.
        Raises `CorporateActionLookupError` -- never a raw alpaca-py/HTTP
        exception -- on any request or response-shape failure, so a caller
        never needs to know alpaca-py's own exception types."""
        from alpaca.data.requests import CorporateActionsRequest
        symbols = list(symbols)
        try:
            request = CorporateActionsRequest(symbols=symbols, start=start, end=end)
            response = self._client.get_corporate_actions(request)
        except CorporateActionLookupError:
            raise
        except Exception as error:
            raise CorporateActionLookupError(type(error).__name__) from error
        out = {symbol: [] for symbol in symbols}
        try:
            for type_key, items in dict(getattr(response, "data", {}) or {}).items():
                spec = _TYPE_FIELD_MAP.get(type_key)
                if spec is None:
                    continue
                symbol_fields, date_field, canonical_type = spec
                for item in items:
                    action_date = getattr(item, date_field, None)
                    if action_date is None:
                        continue
                    for field in symbol_fields:
                        symbol = getattr(item, field, None)
                        if symbol and symbol in out:
                            out[symbol].append(ActionRecord(
                                symbol=symbol, action_type=canonical_type, action_date=action_date,
                                source_id=str(getattr(item, "cusip", "") or type_key)))
        except CorporateActionLookupError:
            raise
        except Exception as error:
            raise CorporateActionLookupError("malformed_corporate_action_response") from error
        return out
