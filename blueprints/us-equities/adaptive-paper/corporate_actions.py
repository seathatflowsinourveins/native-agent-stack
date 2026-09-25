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
        # `complete_attempt`/`fail_attempt` reject a write from any earlier,
        # superseded generation even if it happens to complete later.
        # `refresh_timed_out()`/`invalidate_attempt()` (called by the async
        # scheduler when its own wait_for gives up, or cancels, a still-
        # running attempt) also bump the generation, so that attempt's
        # eventual write -- success or failure, whenever the thread actually
        # finishes -- is dropped too. HIGH finding (fix round 5): the
        # generation for THAT attempt is now allocated by `begin_attempt`
        # BEFORE the worker thread is even launched, not lazily inside
        # `refresh()`/`run_attempt()` once the thread happens to start
        # running -- closing a window where a launched-but-not-yet-running
        # thread was invisible to a concurrent shutdown-time invalidation.
        self._lock = threading.Lock()
        self._generation = 0
        # NIT finding 9 (fix round 4): the generation that most recently
        # actually WROTE a result (success or failure) -- distinct from
        # `_generation` itself. Lets `refresh_timed_out()` tell "the
        # attempt I'm invalidating never actually committed" (a real
        # timeout on a still-in-flight attempt -- must invalidate) apart
        # from "the attempt already committed before this timeout handler
        # even ran" (a race between the worker thread finishing and
        # wait_for's own timeout firing just after -- must NOT re-degrade
        # an already-fresh result; reproduced by the review's own Q5
        # probe: a timeout processed immediately after a successful fetch
        # used to mark the fresh result degraded for up to `retry_seconds`
        # for no reason).
        self._committed_generation = 0

    def refresh(self, symbols, *, start: date, end: date, now=None):
        """The ordinary, synchronous convenience path (used directly by
        every offline test and by any caller that does not need its own
        worker thread) -- built on the two-phase begin_attempt/
        complete_attempt/fail_attempt primitives below, so it shares
        exactly their generation-safety guarantees. Never raises, and
        never overwrites a previously successful result with
        `LOOKUP_FAILED` (finding 3) -- a fetch failure only marks every
        requested symbol DEGRADED (see `_mark_degraded`); `evaluate()`
        preserves the last known good result for a degraded symbol while
        still surfacing `needs_attention`."""
        now = self._clock() if now is None else now
        generation = self.begin_attempt(symbols, start=start, end=end, now=now)
        if generation is None:
            return  # throttled -- an equivalent fresh result is already cached
        symbols = set(symbols)
        try:
            result = self.source.fetch(sorted(symbols), start, end)
        except CorporateActionLookupError:
            self.fail_attempt(symbols, generation)
            return
        except Exception:
            # Fail closed (degraded, not overwritten) on any unexpected
            # error too -- never guess.
            self.fail_attempt(symbols, generation)
            return
        fetched, ambiguous = self._normalize_fetch_result(result)
        self.complete_attempt(symbols, generation, now, fetched, ambiguous)

    def run_attempt(self, symbols, generation, *, start: date, end: date, now):
        """The two-phase counterpart of `refresh()`'s own fetch-and-apply
        body, for a caller (runner.py's `_schedule_corporate_action_refresh`
        worker thread) that already called `begin_attempt` itself -- on the
        CALLING thread/coroutine, before launching the worker -- and is now
        running the actual blocking `source.fetch()` call, and applying its
        result, on a SEPARATE worker thread under the pre-allocated
        `generation`. Never raises."""
        symbols = set(symbols)
        try:
            result = self.source.fetch(sorted(symbols), start, end)
        except CorporateActionLookupError:
            self.fail_attempt(symbols, generation)
            return
        except Exception:
            self.fail_attempt(symbols, generation)
            return
        fetched, ambiguous = self._normalize_fetch_result(result)
        self.complete_attempt(symbols, generation, now, fetched, ambiguous)

    def begin_attempt(self, symbols, *, start: date, end: date, now=None):
        """HIGH finding (fix round 5): allocate THIS attempt's generation
        and run the throttle check SYNCHRONOUSLY, before any blocking I/O
        -- a caller that will run the actual fetch on a separate worker
        thread (runner.py's `_schedule_corporate_action_refresh`) MUST call
        this first, on the CALLING thread/coroutine, before launching that
        worker, and use the returned generation for `complete_attempt`/
        `fail_attempt`/`invalidate_attempt`/`refresh_timed_out`.

        Reproduced by an independent review: the OLD design bumped the
        generation lazily, inside `refresh()` itself -- which only ran once
        the worker thread actually started executing. A worker thread that
        had been launched (`Thread.start()` called) but was still merely
        QUEUED by the OS -- not yet running `refresh()`, so `_generation`
        was still unchanged -- could be invisible to a shutdown-time
        cancellation check: `_committed_generation == _generation` looked
        "already committed / nothing in flight" (neither had moved yet),
        so cancellation did nothing, and the delayed worker went on to
        commit a stale result AFTER shutdown had already decided the run
        was done. Allocating the generation here, before the thread is
        even created, closes that window entirely.

        Returns None if throttled (an equivalent fresh result, for this
        exact symbol set and window, is already cached) -- the caller must
        not launch a worker in that case."""
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
                return None
            self._last_attempt = now
            self._last_window = window
            self._generation += 1
            return self._generation

    @staticmethod
    def _normalize_fetch_result(result):
        """A source's `fetch()` may return either the original plain
        `dict[symbol, list[ActionRecord] | LOOKUP_FAILED | LOOKUP_AMBIGUOUS]`
        (every existing offline-test fake, and any simple source that never
        needs to report "confirmed records AND residual uncertainty" for
        the same symbol at once), or HIGH finding (fix round 5)'s richer
        `(dict[symbol, list[ActionRecord]], ambiguous_symbols: set[str])`
        2-tuple -- AlpacaCorporateActionsSource.fetch() now always returns
        the latter, so a symbol's confirmed records are never discarded
        just because SOME OTHER row for that same symbol was also
        ambiguous (records and uncertainty are tracked separately, not
        collapsed into one sentinel-or-list value per symbol)."""
        if isinstance(result, tuple) and len(result) == 2:
            fetched, ambiguous = result
            return fetched, set(ambiguous)
        return result, set()

    def refresh_timed_out(self, generation, symbols):
        """HIGH finding (fix round 5): called by the async scheduler on a
        GENUINE `wait_for` timeout (not a cancellation -- see
        `invalidate_attempt` for that) for the SPECIFIC pre-allocated
        `generation` (from `begin_attempt`) that timed out. The thread
        keeps running (Python cannot forcibly kill it), so this both (a)
        invalidates exactly that attempt -- bumping `_generation` past it
        only if it is STILL the current one (a newer attempt may already
        have superseded it, in which case there is nothing to invalidate)
        -- so its eventual late write, whenever the thread finishes, is
        dropped, and (b) treats the timeout itself as an ordinary failure
        right now (degraded, short `retry_seconds` retry interval), exactly
        as if `fetch()` had raised, rather than silently leaving the cache
        in its last (possibly clear) state until the abandoned attempt
        happens to resolve on its own.

        NIT finding 9 (fix round 4, preserved through round 5's generation
        pre-allocation): a no-op if THIS SAME generation has ALREADY
        committed (see `_committed_generation`) -- this timeout handler
        firing just after this exact attempt's own success/failure already
        landed must never re-degrade an already-fresh result."""
        with self._lock:
            if generation != self._generation or generation == self._committed_generation:
                return  # already superseded, or already committed -- nothing to invalidate
            self._generation += 1
            self._last_attempt_failed = True
            self._mark_degraded(symbols)

    def invalidate_attempt(self, generation):
        """HIGH finding (fix round 5)/LOW (Claude): called on an ordinary
        CANCELLATION (not a timeout -- shutdown cancelling a still-routine
        in-flight refresh) for the SPECIFIC pre-allocated `generation`.
        Cancellation alone is not evidence the data is wrong -- only
        invalidates that attempt (its eventual late write, if any, is
        dropped as superseded, exactly like `refresh_timed_out`) WITHOUT
        degrading anything. The monitor's last committed result stands,
        subject only to the ordinary `max_age_seconds` staleness rule.
        Reproduced by an independent review's own probe: the previous
        design routed cancellation through the SAME handler as a timeout,
        so a perfectly routine periodic refresh still in flight at
        shutdown (nothing wrong with the cached data at all) forced the
        cached result to needs_attention -- which could force a liquidation
        of an otherwise clean, reconciled overnight hold."""
        with self._lock:
            if generation != self._generation:
                return  # already superseded -- nothing to invalidate
            self._generation += 1

    def fail_attempt(self, symbols, generation):
        """The two-phase counterpart of the old `_apply_failure` -- applies
        an ordinary fetch FAILURE (the source's own `fetch()` raised) for a
        pre-allocated `generation`."""
        with self._lock:
            if generation != self._generation:
                return  # superseded by a later attempt (or a timeout/cancellation) -- drop
            self._committed_generation = generation
            self._last_attempt_failed = True
            self._mark_degraded(symbols)

    def complete_attempt(self, symbols, generation, now, fetched, ambiguous=frozenset()):
        """The two-phase counterpart of the old `_apply_success` -- applies
        a successful fetch result for a pre-allocated `generation`.

        HIGH finding (fix round 5): `fetched` and `ambiguous` are tracked
        SEPARATELY -- a symbol's valid records (possibly empty) are always
        written to `_results` (never discarded), and `ambiguous` only ever
        ADDS that symbol to `_degraded` (never overwrites `_results`) when
        there is residual uncertainty about it (an undated/unmapped/
        symbol-less row) -- even when that same symbol ALSO has confirmed,
        in-range records. The pre-fix design collapsed a symbol's whole
        answer into either "a list of records" OR "LOOKUP_AMBIGUOUS",
        picking the ambiguous sentinel (discarding any records already
        collected) whenever ANY row was uncertain -- which meant a
        confirmed split ALONGSIDE an unrelated undated dividend for the
        same symbol, or a benchmark symbol with its routine quarterly
        dividend already dated (SPY/QQQ/IWM/DIA in the shipped universe
        virtually always have one somewhere in the 97-day window) alongside
        an unmapped/symbol-less row, silently read as fully clear."""
        with self._lock:
            if generation != self._generation:
                return  # superseded -- an older result must never overwrite a newer one
            self._committed_generation = generation
            self._last_attempt_failed = False
            self._last_success = now
            for symbol in symbols:
                if symbol not in fetched:
                    # LOW finding 7 (fix round 3): a symbol omitted from an
                    # OTHERWISE successful fetch (most other symbols
                    # resolved fine) must not erase its own previously
                    # confirmed record -- treat exactly like a per-symbol
                    # failure (degraded, last good record preserved), never
                    # overwrite with LOOKUP_FAILED.
                    self._mark_degraded((symbol,))
                    continue
                new_value = fetched[symbol]
                if new_value in (LOOKUP_FAILED, LOOKUP_AMBIGUOUS):
                    # Backward-compat path for a source using the OLD
                    # single-value-per-symbol contract (see
                    # _normalize_fetch_result): the sentinel must never
                    # overwrite a previously confirmed (already non-empty)
                    # result -- degrade instead, preserving the confirmed
                    # action.
                    self._mark_degraded((symbol,))
                    continue
                if symbol in ambiguous and not new_value:
                    # LOW finding (fix round 6): an ambiguous symbol with NO
                    # valid records of its OWN in this response must not
                    # overwrite a previously confirmed (non-empty) result
                    # with an empty list -- exactly like the sentinel branch
                    # above, this degrades instead, preserving the last
                    # known good records. Reproduced by an independent
                    # review's own probe: an in-range NVDA split confirmed
                    # on one fetch, then a LATER fetch reporting the SAME
                    # split again but now missing its ex_date (so it
                    # resolves to zero valid records for NVDA, plus
                    # ambiguity) used to silently write `_results["NVDA"]
                    # = []`, turning an already-confirmed must_flatten back
                    # into block-and-flag -- losing a still-live intraday
                    # exit signal the guard had already raised.
                    self._mark_degraded((symbol,))
                    continue
                self._results[symbol] = new_value
                if symbol in ambiguous:
                    # HIGH finding (fix round 5): keep the (possibly
                    # confirmed, possibly empty) records, but flag this
                    # symbol degraded anyway -- there is residual
                    # uncertainty about it this fetch even though it also
                    # has a valid answer.
                    self._degraded.add(symbol)
                else:
                    self._degraded.discard(symbol)

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
    # CorporateActionsRequest defaults `limit` to 1000. This wrapper does
    # its OWN pagination now (LOW finding 4, fix round 4 -- see fetch()),
    # accumulating items across pages up to this cap; a result at or past
    # it means more matching rows may exist beyond what was requested.
    _REQUEST_LIMIT = 1000
    # LOW finding 4 (fix round 4): a hard ceiling on how many pages fetch()
    # will follow `next_page_token` for, so a still-present continuation
    # token can never silently loop forever -- exhausting this many pages
    # while a token remains is itself treated as an ambiguous/at-cap
    # result (see fetch()), never a silent truncation.
    _MAX_PAGES = 5

    def __init__(self, api_key, secret_key):
        # alpaca-py's data client is imported and built on first use (the
        # `_client` property below), not here: runner.main constructs this
        # source for every overnight-holds run before its gate checks, and a
        # process that never fetches (a refused run, or a test environment
        # without alpaca-py) must not need alpaca-py installed.
        self._api_key = api_key
        self._secret_key = secret_key
        self._client_instance = None

    @property
    def _client(self):
        if self._client_instance is not None:
            return self._client_instance
        from alpaca.data.historical.corporate_actions import CorporateActionsClient
        # raw_data=True: this wrapper's own inherited `RESTClient.get()`
        # (which fetch() below calls directly) already returns the plain
        # parsed-JSON response regardless of this flag (verified via
        # inspect.getsource against the installed alpaca-py==0.44.0
        # RESTClient.get/_request/_one_request: `_one_request` always
        # returns `response.json()`) -- raw_data=True is kept here only so
        # the client's OWN `get_corporate_actions()` convenience method
        # (not used by this wrapper's fetch() below; LOW finding 4, fix
        # round 4, moved fetch() to the public `get()` with this wrapper's
        # own pagination) would behave consistently if ever called
        # elsewhere. The original reason this flag mattered here --
        # CorporateActionsSet.__init__'s 13-branch, no-else parser
        # (verified via inspect.getsource) silently dropping any bucket key
        # it does not model, e.g. Alpaca's documented `reorganizations`,
        # `partial_calls`, `capital_gains_distributions` -- is now moot for
        # fetch() specifically, since it never goes through
        # CorporateActionsSet at all.
        client = CorporateActionsClient(self._api_key, self._secret_key, raw_data=True)
        # HIGH finding 2: alpaca-py's RESTClient (verified against the
        # installed alpaca-py==0.44.0 RESTClient.__init__/_request) sets no
        # per-request HTTP timeout at all, and sleeps `_retry_wait` (default
        # 3s) between up to `_retry` (default 3) retries on a 429/504 --
        # unbounded and slow by default. Pin a bounded connect/read timeout
        # directly onto the underlying requests.Session (mirroring
        # transport.py's own HTTP-boundary `timeout=(5, 5)` convention) and
        # cut retries to the bare minimum. LOW finding 5 (fix round 3/4):
        # this `requests` timeout bounds each individual connect/read, NOT
        # this fetch() call's total wall-clock duration -- a multi-page
        # fetch issues one HTTP request per page, so a slow-but-not-hung
        # server could still make the overall call run for roughly
        # `pages * timeout`. `wait_for()` in runner.py's
        # `_schedule_corporate_action_refresh` only bounds how long THAT
        # COROUTINE waits for this call to finish; it does not stop this
        # call, or the worker thread it runs in, from continuing to run
        # past that point (see that function's own docstring and
        # CorporateActionMonitor's generation check, which is what makes a
        # late write from such a call harmless rather than "bounded").
        session = client._session
        original_request = session.request

        def _bounded_request(method, url, **kwargs):
            kwargs.setdefault("timeout", (5, 15))
            return original_request(method, url, **kwargs)

        session.request = _bounded_request
        client._retry = 1
        client._retry_wait = 1
        self._client_instance = client
        return client

    @staticmethod
    def _parse_date(value):
        """A raw response field is an ISO date string (or absent/null) once
        parsed from JSON -- never already a `datetime.date` (that only
        happens through the SDK's own pydantic models, which this wrapper
        no longer uses). Returns None for anything that is not a valid ISO
        date, rather than raising -- callers treat a missing/unparseable
        governing date as ambiguous for that record's symbol(s), not as a
        whole-fetch failure."""
        if not isinstance(value, str) or not value:
            return None
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None

    @staticmethod
    def _unmapped_row_symbols(item):
        """LOW finding 5 (fix round 4): a best-effort symbol extraction for
        a bucket type this wrapper's `_TYPE_FIELD_MAP` does not (yet)
        model -- every field Alpaca's documented corporate-action schemas
        use for a tradable symbol is named `*symbol*` (symbol, old_symbol,
        new_symbol, acquirer_symbol, acquiree_symbol, source_symbol,
        alternate_symbol -- see `_TYPE_FIELD_MAP`'s own key tuples above),
        so any key ending in "symbol" with a truthy value is treated as a
        possible symbol for this row, without knowing the type's exact
        schema."""
        return [value for key, value in item.items() if key.endswith("symbol") and value]

    def fetch(self, symbols, start: date, end: date) -> dict:
        """Returns `(out, ambiguous_symbols)` -- HIGH finding (fix round 5):
        `out` is `{symbol: [ActionRecord, ...]}` for exactly the requested
        `symbols` (every requested symbol present, its own resolved list of
        valid records, possibly empty) and `ambiguous_symbols` is the
        INDEPENDENT `set[str]` of requested symbols with at least one
        unresolved row this response (undated, unmapped-bucket, or
        symbol-less) -- a symbol can be in both `out` (with real records)
        and `ambiguous_symbols` (uncertainty about some OTHER row) at once;
        neither ever silently overwrites the other. Raises
        `CorporateActionLookupError` -- never a raw
        alpaca-py/HTTP exception -- on any request/transport failure or a
        result at the page/limit cap, so a caller never needs to know
        alpaca-py's own exception types and never silently treats an
        incomplete or unparseable response as "no action" for every
        requested symbol.

        HIGH finding 3 (fix round 3): requests `data_quality=all` --
        Alpaca's documented default (`data_quality=complete`) excludes
        records the provider itself considers incomplete (e.g. missing a
        CUSIP/ISIN), which could otherwise make a real, known-symbol,
        known-date upcoming action invisible to this guard with no signal
        at all. `all` is not exposed as a typed field on the installed
        alpaca-py==0.44.0 CorporateActionsRequest model (verified: the
        field is silently dropped by its own to_request_fields(), a
        pydantic extra="ignore" default), so this calls the client's own
        PUBLIC `get()` directly with a hand-built params dict, including
        `region: "us"` (also absent from the typed request model) -- the
        same pattern blueprints/us-equities/alpaca-historical/README.md
        and its collect.py document and use for this same endpoint: "The
        installed action request model lacks region and data_quality, so
        the bridge sends those documented REST parameters directly."

        LOW finding 4 (fix round 4): pagination is this wrapper's OWN
        explicit loop over `next_page_token`, matching that same bridge's
        approach ("Installed source inspection confirms that their limit
        acts as a total retrieval cap and that merged results discard
        continuation tokens. This bridge therefore uses the inherited
        native single-page get, adds its own bounded pagination...") --
        the response envelope (`{"corporate_actions": {...buckets...},
        "next_page_token": ...}`) was independently confirmed via a native
        read-only call to `client.get(path="/corporate-actions", ...)` on
        2026-09-24 (see corporate-actions-native-check-20260924.json).

        Types (fix round 4): the Alpaca API reference
        (https://docs.alpaca.markets/us/reference/corporateactions-1,
        fetched by the coordinator 2026-09-24) documents `partial_call`,
        `reorganization` and `capital_gains_distribution` as additional
        action types beyond the 13 `_TYPE_FIELD_MAP` maps, and documents
        `data_quality` as accepting `complete` (default) or `all`. An
        unmapped bucket (any of those three, or a future one) no longer
        fails the WHOLE fetch (LOW finding 5, fix round 4): only the
        symbol(s) its own rows actually name become ambiguous -- an
        unrelated requested symbol with no row in that bucket is
        unaffected. A row with no identifiable symbol at all (every symbol
        field blank/missing, mapped or unmapped bucket alike) cannot be
        safely ignored -- any requested symbol could be the intended one --
        and marks EVERY requested symbol ambiguous (MEDIUM finding 2, fix
        round 4)."""
        symbols = list(symbols)
        params = {"symbols": ",".join(symbols), "start": start.isoformat(), "end": end.isoformat(),
                  "limit": self._REQUEST_LIMIT, "sort": "asc", "data_quality": "all", "region": "us"}
        out = {symbol: [] for symbol in symbols}
        ambiguous_symbols = set()
        try:
            raw: dict = {}
            total_items = 0
            page_token = None
            for _ in range(self._MAX_PAGES):
                page_params = dict(params)
                if page_token is not None:
                    page_params["page_token"] = page_token
                response = self._client.get(path="/corporate-actions", data=page_params)
                if not isinstance(response, dict):
                    raise CorporateActionLookupError("malformed_corporate_action_response")
                body = response.get("corporate_actions")
                if not isinstance(body, dict):
                    raise CorporateActionLookupError("malformed_corporate_action_response")
                for type_key, items in body.items():
                    if not isinstance(items, list):
                        raise CorporateActionLookupError("malformed_corporate_action_response")
                    raw.setdefault(type_key, []).extend(items)
                    total_items += len(items)
                # finding 1 (result-count-at-cap is ambiguous): a response
                # whose total RAW item count (every bucket, mapped or not)
                # reaches the request's own `limit` may have been
                # truncated server-side with no signal to this wrapper
                # about which symbol's records were cut off -- fail closed
                # for this whole fetch rather than trust a possibly-partial
                # result.
                if total_items >= self._REQUEST_LIMIT:
                    raise CorporateActionLookupError("result_at_page_or_limit_cap")
                page_token = response.get("next_page_token")
                # LOW finding (fix round 5): an empty-string token is not a
                # continuation -- Alpaca's own envelope uses an ABSENT or
                # null `next_page_token` to mean "no more pages", but
                # nothing guarantees it never sends `""` for the same
                # meaning; treating any falsy token (None or "") as "stop"
                # avoids sending a bogus `page_token=""` on a request that
                # should have been the last one.
                if not page_token:
                    break
            else:
                # LOW finding 4: exhausted _MAX_PAGES while a continuation
                # token was STILL present -- never silently truncate.
                raise CorporateActionLookupError("result_at_page_or_limit_cap")
            for type_key, items in raw.items():
                spec = _TYPE_FIELD_MAP.get(type_key)
                for item in items:
                    if not isinstance(item, dict):
                        raise CorporateActionLookupError("malformed_corporate_action_item")
                    if spec is None:
                        # LOW finding 5: an unmapped bucket type -- degrade
                        # only the symbol(s) THIS row actually names (or
                        # every requested symbol, if it names none at all;
                        # MEDIUM finding 2 below covers that same rule for
                        # mapped buckets too).
                        row_symbols = self._unmapped_row_symbols(item)
                        ambiguous_symbols.update(symbols if not row_symbols
                                                 else (s for s in row_symbols if s in out))
                        continue
                    symbol_fields, date_field, canonical_type = spec
                    raw_symbols = [item.get(field) for field in symbol_fields if item.get(field)]
                    if not raw_symbols:
                        # MEDIUM finding 2 (fix round 4): a row with NO
                        # identifiable symbol at all (every symbol field on
                        # this row blank/missing) cannot be safely ignored
                        # -- any requested symbol could be the intended
                        # one -- ambiguous for every requested symbol in
                        # this fetch, not silently "no action" for all of
                        # them.
                        ambiguous_symbols.update(symbols)
                        continue
                    matched_symbols = [s for s in raw_symbols if s in out]
                    if not matched_symbols:
                        continue  # a real symbol, just not one we asked about -- ignore
                    action_date = self._parse_date(item.get(date_field))
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
        except CorporateActionLookupError:
            raise
        except Exception as error:
            raise CorporateActionLookupError(type(error).__name__) from error
        # HIGH finding (fix round 5): records and uncertainty are returned
        # SEPARATELY -- `out[symbol]` is always that symbol's own valid,
        # in-window records (possibly empty), NEVER replaced or collapsed
        # into a sentinel, and `ambiguous_symbols` independently lists every
        # symbol with at least one unresolved row (undated, unmapped-bucket,
        # or symbol-less) THIS fetch. The pre-fix design overwrote `out
        # [symbol]` with the single sentinel `LOOKUP_AMBIGUOUS` whenever the
        # symbol had zero valid records of its own -- which read as fully
        # clear the moment a symbol ALSO had any unrelated valid record,
        # e.g. a benchmark symbol's routine quarterly dividend already dated
        # somewhere in the window (SPY/QQQ/IWM/DIA virtually always have
        # one) sitting alongside an unmapped/undated/symbol-less row for
        # that same symbol. `CorporateActionMonitor.complete_attempt` (via
        # `_normalize_fetch_result`) now keeps `out[symbol]`'s records AND
        # separately marks the symbol degraded when it is also in
        # `ambiguous_symbols` -- a confirmed action still flattens the
        # guard, and residual uncertainty still raises needs_attention,
        # simultaneously, rather than one silently hiding the other.
        return out, ambiguous_symbols
