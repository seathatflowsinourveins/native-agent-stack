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
import threading
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
                   lookup_results: Mapping[str, object], degraded_symbols=frozenset()) -> dict:
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

    `degraded_symbols` (finding 3, 2026-09-24 fix round): symbols whose most
    recent refresh attempt failed or has gone stale, but whose
    `lookup_results` entry is still the LAST KNOWN GOOD (possibly empty)
    `ActionRecord` list rather than `LOOKUP_FAILED`/`LOOKUP_AMBIGUOUS` (the
    caller -- CorporateActionMonitor.evaluate -- never overwrites a
    previously successful result on a later failure; see its own
    docstring). A degraded symbol with no qualifying action still blocks
    entry and raises needs_attention (its "no action" answer can no longer
    be trusted); a degraded symbol WITH a qualifying action keeps
    must_flatten exactly as it would non-degraded -- a confirmed in-range
    corporate action already discovered must never be silently cancelled
    just because a subsequent refresh failed -- while also raising
    needs_attention so an operator is warned the underlying data is stale.
    """
    held = set(held_symbols)
    decisions = {}
    for symbol in held | set(candidate_symbols):
        result = lookup_results.get(symbol, LOOKUP_FAILED)
        degraded = symbol in degraded_symbols
        if result in (LOOKUP_FAILED, LOOKUP_AMBIGUOUS):
            decisions[symbol] = GuardDecision(
                symbol=symbol, block_entry=True, must_flatten=False, needs_attention=True,
                reason=f"corporate_action_{result}")
            continue
        # finding 4 (2026-09-24 fix round): a weekend/holiday action date
        # (e.g. a dividend whose ex_date lands on a Saturday) falls between
        # `today` and `next_session_date` but matched neither exactly, so it
        # was never in range. An inclusive range check catches every date in
        # between, not just the two session-boundary dates themselves.
        qualifying = [record for record in result if today <= record.action_date <= next_session_date]
        if not qualifying:
            decisions[symbol] = GuardDecision(
                symbol=symbol, block_entry=degraded, must_flatten=False, needs_attention=degraded,
                reason="corporate_action_stale_refresh" if degraded else None)
            continue
        chosen = min(qualifying, key=lambda record: record.action_date)
        decisions[symbol] = GuardDecision(
            symbol=symbol, block_entry=True, must_flatten=symbol in held, needs_attention=degraded,
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
    tick). `retry_seconds` (finding 8, 2026-09-24 fix round) is a SHORTER
    throttle used instead of `refresh_seconds` immediately after a failed
    attempt, so a transient failure is retried again in about a minute
    rather than waiting out the full (much longer) `refresh_seconds`
    interval before trying again. `max_age_seconds` bounds how long a
    successful result is still trusted by `evaluate()`: past that age, or
    before any refresh has ever succeeded, every relevant symbol fails
    closed exactly like a lookup failure -- never silently reusing a
    result that might now be stale.
    """

    def __init__(self, source, *, refresh_seconds=900.0, retry_seconds=60.0, max_age_seconds=3600.0, clock=None):
        self.source = source
        self.refresh_seconds = refresh_seconds
        self.retry_seconds = retry_seconds
        self.max_age_seconds = max_age_seconds
        self._clock = clock or _time.time
        self._last_attempt = None
        self._last_success = None
        self._last_attempt_failed = False
        self._results: dict = {}
        # finding 7b (2026-09-24 fix round): the window this cached
        # `_results` was actually fetched for, so a caller that asks for a
        # DIFFERENT (start, end) window than the last cached fetch is never
        # served a stale result computed against the old window purely
        # because it arrived within `refresh_seconds` -- the throttle used
        # to key only on symbol coverage, ignoring the window entirely.
        self._last_window = None
        # finding 3 (2026-09-24 fix round): symbols whose most recent
        # refresh attempt failed, or whose entire cache has gone stale past
        # `max_age_seconds` -- tracked SEPARATELY from `_results`, which is
        # now only ever written on a SUCCESSFUL fetch (see refresh()/
        # _mark_degraded below), so a failed or stale refresh never
        # overwrites (and thereby silently cancels) a previously confirmed
        # in-range corporate action.
        self._degraded: set = set()
        # HIGH finding 1 (2026-09-24 fix round 3): `refresh()` runs in a
        # caller-owned worker thread (runner.py's asyncio.to_thread) bounded
        # by a wait_for timeout on the CALLER side -- the timeout only stops
        # the caller from waiting, it cannot stop the thread itself
        # (reproduced: an older, slower attempt finishing after a newer one
        # already wrote a confirmed must_flatten silently turned it back
        # off, because both attempts wrote into `_results` unconditionally
        # with no ordering guard). `_generation` is bumped, under `_lock`,
        # at the START of every `refresh()` attempt; only the write from
        # the CURRENT (latest-started) generation is ever applied --
        # `_apply_success`/`_apply_failure` drop a write from any earlier,
        # superseded generation even if it happens to complete later.
        # `refresh_timed_out()` (called by the async scheduler when its own
        # wait_for gives up on a still-running attempt) also bumps the
        # generation, so that attempt's eventual write -- success or
        # failure, whenever the thread actually finishes -- is dropped too.
        self._lock = threading.Lock()
        self._generation = 0

    def refresh(self, symbols, *, start: date, end: date, now=None):
        """Idempotent within `refresh_seconds` for a symbol set already
        covered by the last successful fetch AND fetched for this same
        (start, end) window; always safe to call every tick, including
        concurrently from multiple threads (finding 1) -- every state
        mutation is generation-checked under `self._lock`. Never raises,
        and never overwrites a previously successful result with
        `LOOKUP_FAILED` (finding 3) -- a fetch failure only marks every
        requested symbol DEGRADED (see `_mark_degraded`); `evaluate()`
        preserves the last known good result for a degraded symbol while
        still surfacing `needs_attention`."""
        now = self._clock() if now is None else now
        symbols = set(symbols)
        window = (start, end)
        with self._lock:
            # finding 8: a throttle interval of `retry_seconds` (short)
            # rather than `refresh_seconds` (long) whenever the LAST
            # attempt failed -- a transient failure gets retried again in
            # about a minute instead of waiting out the full ordinary
            # interval.
            interval = self.retry_seconds if self._last_attempt_failed else self.refresh_seconds
            if (self._last_attempt is not None and now - self._last_attempt < interval
                    and symbols.issubset(self._results.keys()) and self._last_window == window):
                return
            self._last_attempt = now
            self._last_window = window
            self._generation += 1
            my_generation = self._generation
        try:
            fetched = self.source.fetch(sorted(symbols), start, end)
        except CorporateActionLookupError:
            self._apply_failure(symbols, my_generation)
            return
        except Exception:
            # Fail closed (degraded, not overwritten) on any unexpected
            # error too -- never guess.
            self._apply_failure(symbols, my_generation)
            return
        self._apply_success(symbols, fetched, now, my_generation)

    def refresh_timed_out(self, symbols):
        """HIGH finding 1: called by the async scheduler (runner.py's
        `_schedule_corporate_action_refresh`) when ITS OWN wait_for gives up
        on a `refresh()` call still running in a worker thread. The thread
        keeps running (Python cannot forcibly kill it), so this both (a)
        bumps the generation counter, invalidating that in-flight attempt --
        whenever it does eventually finish, `_apply_success`/`_apply_failure`
        will see a stale generation and drop the write -- and (b) treats the
        timeout itself as an ordinary failure right now (degraded, short
        `retry_seconds` retry interval), exactly as if `fetch()` had raised,
        rather than silently leaving the cache in its last (possibly clear)
        state until the abandoned attempt happens to resolve on its own."""
        with self._lock:
            self._generation += 1
            self._last_attempt_failed = True
            self._mark_degraded(symbols)

    def _apply_failure(self, symbols, generation):
        with self._lock:
            if generation != self._generation:
                return  # superseded by a later attempt (or a timeout) -- drop
            self._last_attempt_failed = True
            self._mark_degraded(symbols)

    def _apply_success(self, symbols, fetched, now, generation):
        with self._lock:
            if generation != self._generation:
                return  # superseded -- an older result must never overwrite a newer one
            self._last_attempt_failed = False
            self._last_success = now
            for symbol in symbols:
                if symbol in fetched:
                    self._results[symbol] = fetched[symbol]
                    self._degraded.discard(symbol)
                else:
                    # LOW finding 7 (fix round 3): a symbol omitted from an
                    # OTHERWISE successful fetch (most other symbols
                    # resolved fine) must not erase its own previously
                    # confirmed record -- treat exactly like a per-symbol
                    # failure (degraded, last good record preserved), never
                    # overwrite with LOOKUP_FAILED.
                    self._mark_degraded((symbol,))

    def _mark_degraded(self, symbols):
        """finding 3: only ever ADD to `_degraded` and, for a symbol never
        previously fetched at all, seed a `LOOKUP_FAILED` baseline via
        `setdefault` -- never touch an existing `_results` entry, so a
        previously confirmed corporate action survives a later failed
        refresh untouched. Callers hold `self._lock`."""
        for symbol in symbols:
            self._degraded.add(symbol)
            self._results.setdefault(symbol, LOOKUP_FAILED)

    def evaluate(self, *, today: date, next_session_date: date, held_symbols, candidate_symbols,
                now=None) -> dict:
        now = self._clock() if now is None else now
        relevant = set(held_symbols) | set(candidate_symbols)
        # finding 3: a globally stale cache (no successful refresh within
        # max_age_seconds) is treated as degraded for every relevant
        # symbol, exactly like a per-symbol refresh failure -- but, unlike
        # the pre-fix behaviour, this no longer discards `_results`: the
        # last known good ActionRecord list (if any) is still read below,
        # so a confirmed in-range action is preserved (with needs_attention
        # added) rather than silently cancelled by staleness alone.
        with self._lock:
            stale = self._last_success is None or now - self._last_success > self.max_age_seconds
            results = {symbol: self._results.get(symbol, LOOKUP_FAILED) for symbol in relevant}
            degraded = (relevant if stale else set()) | (self._degraded & relevant)
        return evaluate_guard(today=today, next_session_date=next_session_date,
                              held_symbols=held_symbols, candidate_symbols=candidate_symbols,
                              lookup_results=results, degraded_symbols=degraded)


# type_key (alpaca-py CorporateActionsSet.data key) -> (symbol attribute
# names that identify an affected tradable symbol, the attribute name that
# is this guard's governing date, the canonical ACTION_TYPES bucket).
# Verified against the installed alpaca-py==0.44.0
# alpaca/data/models/corporate_actions.py dataclass fields on this host.
_TYPE_FIELD_MAP = {
    "forward_splits": (("symbol",), "ex_date", "forward_split"),
    "reverse_splits": (("symbol",), "ex_date", "reverse_split"),
    # finding 7d: alpaca-py's UnitSplit model also carries an
    # `alternate_symbol` (the symbol representing fractional/alternate
    # shares from the split) distinct from old_symbol/new_symbol -- a held
    # or candidate position in that alternate symbol must also be guarded.
    "unit_splits": (("old_symbol", "new_symbol", "alternate_symbol"), "effective_date", "other"),
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

    # HIGH finding 2 (fix round 3): request cap -- alpaca-py==0.44.0's
    # CorporateActionsRequest defaults `limit` to 1000, and its
    # `RESTClient._get_marketdata` (verified via `inspect.getsource` against
    # the installed package) DOES auto-paginate across `next_page_token`,
    # accumulating items from every page up to this `limit` -- so a result
    # at or past this cap means more matching rows may exist beyond what was
    # requested, not that pagination silently stopped after one page (an
    # earlier round of this comment was wrong about that).
    _REQUEST_LIMIT = 1000

    def __init__(self, api_key, secret_key):
        from alpaca.data.historical.corporate_actions import CorporateActionsClient
        # HIGH finding 2 (fix round 3): raw_data=True makes get_corporate_
        # actions() (and the private _get_marketdata() this wrapper calls
        # directly below) return the plain parsed-JSON dict instead of a
        # CorporateActionsSet. This is required, not cosmetic:
        # CorporateActionsSet.__init__ (verified via inspect.getsource
        # against the installed alpaca-py==0.44.0 package) is a chain of 13
        # `elif corporate_action_type == "..."` branches with NO else/
        # default clause -- any bucket key it does not recognize (the
        # Alpaca API reference documents `reorganizations`, `partial_calls`
        # and `capital_gains_distributions` in addition to the 13 this
        # wrapper's own _TYPE_FIELD_MAP models) is silently dropped by the
        # SDK before this wrapper ever sees it, turning a real corporate
        # action into an apparently-clear "no action" result, and its rows
        # also never reach the cap check below. Parsing the raw dict
        # ourselves (see fetch()) means an unmapped bucket key is visible to
        # this wrapper's own _TYPE_FIELD_MAP.get(...) is None fail-closed
        # path instead of vanishing inside the SDK first.
        self._client = CorporateActionsClient(api_key, secret_key, raw_data=True)
        # HIGH finding 2: alpaca-py's RESTClient (verified against the
        # installed alpaca-py==0.44.0 RESTClient.__init__/_request) sets no
        # per-request HTTP timeout at all, and sleeps `_retry_wait` (default
        # 3s) between up to `_retry` (default 3) retries on a 429/504 --
        # unbounded and slow by default. Pin a bounded connect/read timeout
        # directly onto the underlying requests.Session (mirroring
        # transport.py's own HTTP-boundary `timeout=(5, 5)` convention) and
        # cut retries to the bare minimum. NIT finding 9 (fix round 3): a
        # `requests` timeout bounds each individual connect/read, not the
        # call's total wall-clock duration -- a paginated multi-page fetch
        # (`_get_marketdata` above) issues one HTTP request per page, and a
        # slow-but-not-hung server could still make the overall fetch() call
        # run for `pages * timeout`. The actual outer bound on one fetch()
        # call is runner.py's own asyncio wait_for()
        # (CORPORATE_ACTION_REFRESH_TIMEOUT_SECONDS) around the whole
        # refresh() call this fetch() runs inside, not this per-request
        # timeout alone; this timeout only prevents a single HTTP request
        # from hanging indefinitely with no data ever arriving.
        session = self._client._session
        original_request = session.request

        def _bounded_request(method, url, **kwargs):
            kwargs.setdefault("timeout", (5, 15))
            return original_request(method, url, **kwargs)

        session.request = _bounded_request
        self._client._retry = 1
        self._client._retry_wait = 1

    @staticmethod
    def _parse_date(value):
        """A raw response field is an ISO date string (or absent/null) once
        parsed from JSON -- never already a `datetime.date` (that only
        happens through the SDK's own pydantic models, which this wrapper
        no longer uses; see raw_data=True above). Returns None for
        anything that is not a valid ISO date, rather than raising --
        callers treat a missing/unparseable governing date as ambiguous for
        that record's symbol(s), not as a whole-fetch failure."""
        if not isinstance(value, str) or not value:
            return None
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None

    def fetch(self, symbols, start: date, end: date) -> dict:
        """Returns `{symbol: [ActionRecord, ...] | LOOKUP_AMBIGUOUS}` for
        exactly the requested `symbols` (every requested symbol is present:
        either its resolved list, possibly empty, or LOOKUP_AMBIGUOUS for a
        symbol whose own record(s) could not be fully parsed -- MEDIUM
        finding 3, fix round 3). Raises `CorporateActionLookupError` --
        never a raw alpaca-py/HTTP exception -- on any request/transport
        failure, a result at the page/limit cap, or an unmapped action-type
        bucket, so a caller never needs to know alpaca-py's own exception
        types and never silently treats an incomplete or unparseable
        response as "no action" for every requested symbol.

        HIGH finding 3 (fix round 3): requests `data_quality=all` --
        Alpaca's documented default (`data_quality=complete`) excludes
        records the provider itself considers incomplete (e.g. missing a
        CUSIP/ISIN), which could otherwise make a real, known-symbol,
        known-date upcoming action invisible to this guard with no
        signal at all. `all` is not exposed as a typed field on the
        installed alpaca-py==0.44.0 CorporateActionsRequest model (verified:
        the field is silently dropped by its own to_request_fields(), a
        pydantic extra="ignore" default), so this calls the client's own
        private `_get_marketdata` directly with a hand-built params dict --
        the same private method `get_corporate_actions()` itself calls --
        instead of going through the typed request object for this one
        parameter."""
        symbols = list(symbols)
        params = {"symbols": ",".join(symbols), "start": start.isoformat(), "end": end.isoformat(),
                  "limit": self._REQUEST_LIMIT, "sort": "asc", "data_quality": "all"}
        try:
            raw = self._client._get_marketdata(path="/corporate-actions", params=params,
                                               page_limit=1000, page_size=1000)
        except CorporateActionLookupError:
            raise
        except Exception as error:
            raise CorporateActionLookupError(type(error).__name__) from error
        out = {symbol: [] for symbol in symbols}
        ambiguous_symbols = set()
        try:
            raw = dict(raw or {})
            # finding 1 (result-count-at-cap is ambiguous): a response whose
            # total RAW item count (every bucket, including one this
            # wrapper does not model -- see raw_data=True above) reaches the
            # request's own `limit` may have been truncated server-side
            # with no signal to this wrapper about which symbol's records
            # were cut off -- fail closed for this whole fetch rather than
            # trust a possibly-partial result.
            total_items = sum(len(items) for items in raw.values())
            if total_items >= self._REQUEST_LIMIT:
                raise CorporateActionLookupError("result_at_page_or_limit_cap")
            for type_key, items in raw.items():
                spec = _TYPE_FIELD_MAP.get(type_key)
                if spec is None:
                    # finding 7c/finding 2 (fix round 3): an unmapped bucket
                    # key (e.g. Alpaca's documented `reorganizations`,
                    # `partial_calls`, `capital_gains_distributions`, or any
                    # future type this guard's _TYPE_FIELD_MAP does not yet
                    # know) has no known governing-date or symbol field this
                    # wrapper can trust to parse -- fail closed (ambiguous)
                    # for the whole fetch rather than silently skip an
                    # action type this guard does not yet recognize. Now
                    # actually reachable (raw_data=True, fix round 3): the
                    # SDK's own CorporateActionsSet used to drop these
                    # bucket keys before this wrapper ever saw them.
                    raise CorporateActionLookupError(f"unmapped_corporate_action_type:{type_key}")
                symbol_fields, date_field, canonical_type = spec
                for item in items:
                    if not isinstance(item, dict):
                        raise CorporateActionLookupError("malformed_corporate_action_item")
                    action_date = self._parse_date(item.get(date_field))
                    matched_symbols = [item.get(field) for field in symbol_fields
                                      if item.get(field) and item.get(field) in out]
                    if action_date is None:
                        # HIGH finding 3 (fix round 3): a record missing (or
                        # carrying an unparseable) governing date -- e.g.
                        # excluded-by-default incomplete data now included
                        # via data_quality=all -- becomes ambiguous for
                        # EVERY requested symbol it names, rather than being
                        # silently skipped as if it never existed.
                        ambiguous_symbols.update(matched_symbols)
                        continue
                    for symbol in matched_symbols:
                        out[symbol].append(ActionRecord(
                            symbol=symbol, action_type=canonical_type, action_date=action_date,
                            source_id=str(item.get("cusip") or type_key)))
            for symbol in ambiguous_symbols:
                out[symbol] = LOOKUP_AMBIGUOUS
        except CorporateActionLookupError:
            raise
        except Exception as error:
            raise CorporateActionLookupError("malformed_corporate_action_response") from error
        return out
