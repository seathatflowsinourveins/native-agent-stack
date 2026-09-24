"""Synthetic (SYN) tests for the trading-lane audit gap #8 interim control:
corporate_actions.py's pure guard/monitor logic, and its wiring into
native_strategy.AdaptiveStrategy.rebalance(). No credentials, sockets, or
broker execution; every source is a fake, matching every other
tests/test_adaptive_paper_*.py file in this directory. The real
alpaca-py-backed `corporate_actions.AlpacaCorporateActionsSource` is not
exercised here (see corporate_actions.py's module docstring for how its
field mapping was verified against the installed alpaca-py==0.44.0
package instead).
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal as D
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))

import corporate_actions as CA  # noqa: E402 (path inserted above)
import sessions  # noqa: E402

NATIVE = importlib.util.find_spec("nautilus_trader") is not None
if NATIVE:
    from nautilus_trader.model import OrderSide  # noqa: E402

TODAY = date(2026, 9, 24)
NEXT_SESSION = date(2026, 9, 25)
FAR_FUTURE = date(2026, 12, 1)


def action(symbol, action_type, action_date, source_id=""):
    return CA.ActionRecord(symbol=symbol, action_type=action_type, action_date=action_date,
                           source_id=source_id)


class ActionRecordTests(unittest.TestCase):
    def test_unknown_action_type_rejected(self):
        with self.assertRaises(ValueError):
            CA.ActionRecord(symbol="AAPL", action_type="bogus", action_date=TODAY)

    def test_every_documented_action_type_accepted(self):
        for action_type in ("forward_split", "reverse_split", "cash_dividend", "stock_dividend",
                            "spin_off", "merger", "name_change", "other"):
            action("AAPL", action_type, TODAY)  # must not raise


class EvaluateGuardTests(unittest.TestCase):
    """Covers each action type, entry blocking, pre-close flattening, the
    fail-closed path, and the absence of any effect on symbols without
    actions -- run against corporate_actions.evaluate_guard directly."""

    def evaluate(self, held, candidates, results):
        return CA.evaluate_guard(today=TODAY, next_session_date=NEXT_SESSION,
                                 held_symbols=held, candidate_symbols=candidates,
                                 lookup_results=results)

    def test_each_action_type_on_a_held_symbol_blocks_and_flattens(self):
        for action_type in ("forward_split", "reverse_split", "cash_dividend", "stock_dividend",
                            "spin_off", "merger", "name_change", "other"):
            with self.subTest(action_type=action_type):
                decisions = self.evaluate({"AAPL"}, set(), {"AAPL": [action("AAPL", action_type, TODAY)]})
                d = decisions["AAPL"]
                self.assertTrue(d.block_entry)
                self.assertTrue(d.must_flatten)
                self.assertFalse(d.needs_attention)
                self.assertEqual(d.reason, f"corporate_action_{action_type}")
                self.assertEqual(d.action_type, action_type)
                self.assertEqual(d.action_date, TODAY)

    def test_action_on_next_session_date_also_qualifies(self):
        decisions = self.evaluate({"AAPL"}, set(), {"AAPL": [action("AAPL", "reverse_split", NEXT_SESSION)]})
        self.assertTrue(decisions["AAPL"].block_entry)
        self.assertTrue(decisions["AAPL"].must_flatten)

    def test_action_outside_the_hold_horizon_has_no_effect(self):
        decisions = self.evaluate({"AAPL"}, set(), {"AAPL": [action("AAPL", "cash_dividend", FAR_FUTURE)]})
        d = decisions["AAPL"]
        self.assertFalse(d.block_entry)
        self.assertFalse(d.must_flatten)
        self.assertFalse(d.needs_attention)
        self.assertIsNone(d.reason)

    def test_symbol_with_no_recorded_actions_at_all_has_no_effect(self):
        decisions = self.evaluate({"AAPL"}, {"MSFT"}, {"AAPL": [], "MSFT": []})
        self.assertFalse(decisions["AAPL"].block_entry)
        self.assertFalse(decisions["AAPL"].must_flatten)
        self.assertFalse(decisions["MSFT"].block_entry)

    def test_candidate_not_currently_held_is_blocked_but_never_flattened(self):
        decisions = self.evaluate(set(), {"MSFT"}, {"MSFT": [action("MSFT", "spin_off", TODAY)]})
        d = decisions["MSFT"]
        self.assertTrue(d.block_entry)
        self.assertFalse(d.must_flatten)

    def test_lookup_failed_fails_closed_blocking_entry_without_forcing_flatten(self):
        decisions = self.evaluate({"AAPL"}, {"MSFT"}, {"AAPL": CA.LOOKUP_FAILED, "MSFT": CA.LOOKUP_FAILED})
        for symbol in ("AAPL", "MSFT"):
            d = decisions[symbol]
            self.assertTrue(d.block_entry)
            self.assertTrue(d.needs_attention)
            self.assertFalse(d.must_flatten)
            self.assertEqual(d.reason, "corporate_action_lookup_failed")

    def test_lookup_ambiguous_fails_closed_the_same_way(self):
        decisions = self.evaluate({"AAPL"}, set(), {"AAPL": CA.LOOKUP_AMBIGUOUS})
        d = decisions["AAPL"]
        self.assertTrue(d.block_entry)
        self.assertTrue(d.needs_attention)
        self.assertEqual(d.reason, "corporate_action_lookup_ambiguous")

    def test_symbol_missing_from_results_entirely_fails_closed(self):
        decisions = self.evaluate({"AAPL"}, set(), {})
        d = decisions["AAPL"]
        self.assertTrue(d.block_entry)
        self.assertTrue(d.needs_attention)
        self.assertEqual(d.reason, "corporate_action_lookup_failed")

    def test_earliest_qualifying_action_governs_when_several_are_recorded(self):
        decisions = self.evaluate({"AAPL"}, set(), {"AAPL": [
            action("AAPL", "cash_dividend", NEXT_SESSION), action("AAPL", "reverse_split", TODAY)]})
        d = decisions["AAPL"]
        self.assertEqual(d.action_type, "reverse_split")
        self.assertEqual(d.action_date, TODAY)

    def test_only_relevant_symbols_are_decided(self):
        decisions = self.evaluate({"AAPL"}, {"MSFT"}, {"AAPL": [], "MSFT": [], "IGNORED": []})
        self.assertEqual(set(decisions), {"AAPL", "MSFT"})

    # -- finding 4: a governing date strictly BETWEEN today and
    # next_session_date (e.g. a weekend/holiday the ex_date happens to
    # land on) must still be in range -- not just the two boundary dates
    # themselves.
    def test_action_date_strictly_between_today_and_next_session_is_in_range(self):
        friday, saturday, monday = date(2026, 10, 2), date(2026, 10, 3), date(2026, 10, 5)
        decisions = CA.evaluate_guard(today=friday, next_session_date=monday, held_symbols={"X"},
                                      candidate_symbols=set(),
                                      lookup_results={"X": [action("X", "merger", saturday)]})
        d = decisions["X"]
        self.assertTrue(d.block_entry)
        self.assertTrue(d.must_flatten)
        self.assertEqual(d.action_date, saturday)

    # -- finding 3: a degraded (stale/failed-refresh) symbol with a
    # confirmed in-range action keeps must_flatten, but gains
    # needs_attention; a degraded symbol with NO qualifying action still
    # blocks entry (cannot trust "no action" from stale data) and gains
    # needs_attention, but is never force-flattened on staleness alone.
    def test_degraded_symbol_preserves_confirmed_flatten_and_adds_attention(self):
        decisions = self.evaluate({"AAPL"}, set(), {"AAPL": [action("AAPL", "cash_dividend", TODAY)]})
        # Not degraded: baseline.
        self.assertFalse(decisions["AAPL"].needs_attention)
        degraded = CA.evaluate_guard(today=TODAY, next_session_date=NEXT_SESSION, held_symbols={"AAPL"},
                                     candidate_symbols=set(),
                                     lookup_results={"AAPL": [action("AAPL", "cash_dividend", TODAY)]},
                                     degraded_symbols={"AAPL"})["AAPL"]
        self.assertTrue(degraded.must_flatten, "a confirmed flatten must survive degraded staleness")
        self.assertTrue(degraded.needs_attention)

    def test_degraded_symbol_with_no_qualifying_action_still_blocks_entry(self):
        decisions = CA.evaluate_guard(today=TODAY, next_session_date=NEXT_SESSION, held_symbols=set(),
                                      candidate_symbols={"MSFT"}, lookup_results={"MSFT": []},
                                      degraded_symbols={"MSFT"})["MSFT"]
        self.assertTrue(decisions.block_entry)
        self.assertTrue(decisions.needs_attention)
        self.assertFalse(decisions.must_flatten)


class CorporateActionMonitorTests(unittest.TestCase):
    class FakeSource:
        def __init__(self, result=None, error=None):
            self.result = result or {}
            self.error = error
            self.calls = []

        def fetch(self, symbols, start, end):
            self.calls.append((tuple(symbols), start, end))
            if self.error is not None:
                raise self.error
            return {s: self.result.get(s, []) for s in symbols}

    def test_evaluate_before_any_refresh_fails_closed(self):
        monitor = CA.CorporateActionMonitor(self.FakeSource(), clock=lambda: 1000.0)
        decisions = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION,
                                     held_symbols={"AAPL"}, candidate_symbols=set(), now=1000.0)
        self.assertTrue(decisions["AAPL"].needs_attention)
        self.assertTrue(decisions["AAPL"].block_entry)

    def test_successful_refresh_feeds_evaluate(self):
        source = self.FakeSource(result={"AAPL": [action("AAPL", "forward_split", TODAY)]})
        monitor = CA.CorporateActionMonitor(source, clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        decisions = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION,
                                     held_symbols={"AAPL"}, candidate_symbols=set(), now=1000.0)
        self.assertEqual(decisions["AAPL"].reason, "corporate_action_forward_split")
        self.assertFalse(decisions["AAPL"].needs_attention)

    def test_lookup_error_fails_closed_for_every_requested_symbol(self):
        source = self.FakeSource(error=CA.CorporateActionLookupError("boom"))
        monitor = CA.CorporateActionMonitor(source, clock=lambda: 1000.0)
        monitor.refresh({"AAPL", "MSFT"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        decisions = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION,
                                     held_symbols={"AAPL"}, candidate_symbols={"MSFT"}, now=1000.0)
        self.assertTrue(decisions["AAPL"].needs_attention)
        self.assertTrue(decisions["MSFT"].needs_attention)

    def test_unexpected_exception_from_source_also_fails_closed(self):
        source = self.FakeSource(error=RuntimeError("unexpected"))
        monitor = CA.CorporateActionMonitor(source, clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        decisions = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION,
                                     held_symbols={"AAPL"}, candidate_symbols=set(), now=1000.0)
        self.assertTrue(decisions["AAPL"].needs_attention)

    def test_stale_result_past_max_age_fails_closed_even_after_a_success(self):
        source = self.FakeSource(result={"AAPL": []})
        monitor = CA.CorporateActionMonitor(source, refresh_seconds=1, max_age_seconds=100, clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        fresh = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION,
                                 held_symbols={"AAPL"}, candidate_symbols=set(), now=1050.0)
        self.assertFalse(fresh["AAPL"].needs_attention)
        stale = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION,
                                 held_symbols={"AAPL"}, candidate_symbols=set(), now=1200.0)
        self.assertTrue(stale["AAPL"].needs_attention)

    def test_refresh_is_throttled_within_refresh_seconds_for_the_same_symbols(self):
        source = self.FakeSource(result={"AAPL": []})
        monitor = CA.CorporateActionMonitor(source, refresh_seconds=900, clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1001.0)
        self.assertEqual(len(source.calls), 1)

    def test_refresh_widens_the_fetch_when_a_new_symbol_appears(self):
        source = self.FakeSource(result={"AAPL": [], "MSFT": []})
        monitor = CA.CorporateActionMonitor(source, refresh_seconds=900, clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        monitor.refresh({"AAPL", "MSFT"}, start=TODAY, end=NEXT_SESSION, now=1001.0)
        self.assertEqual(len(source.calls), 2)

    # -- finding 7b: the throttle must also be keyed on the (start, end)
    # window, not just symbol coverage -- a caller asking for a DIFFERENT
    # window than the last cached fetch must never be served a stale
    # result computed against the OLD window merely because it arrived
    # within refresh_seconds.
    def test_refresh_not_throttled_when_the_window_changes_for_the_same_symbols(self):
        source = self.FakeSource(result={"AAPL": []})
        monitor = CA.CorporateActionMonitor(source, refresh_seconds=900, clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        monitor.refresh({"AAPL"}, start=NEXT_SESSION, end=FAR_FUTURE, now=1001.0)
        self.assertEqual(len(source.calls), 2)
        self.assertEqual(source.calls[1], (("AAPL",), NEXT_SESSION, FAR_FUTURE))

    # -- finding 7a: a source that silently omits a requested symbol from
    # its returned dict (an injected fake/test source; never true of
    # AlpacaCorporateActionsSource) must fail closed for that symbol, not
    # be read as "no action".
    def test_symbol_omitted_by_the_source_fails_closed_not_no_action(self):
        class OmittingSource:
            def fetch(self, symbols, start, end):
                return {}  # never includes any requested symbol
        monitor = CA.CorporateActionMonitor(OmittingSource(), clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        decisions = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION,
                                     held_symbols=set(), candidate_symbols={"AAPL"}, now=1000.0)
        self.assertTrue(decisions["AAPL"].block_entry)
        self.assertTrue(decisions["AAPL"].needs_attention)
        self.assertEqual(decisions["AAPL"].reason, "corporate_action_lookup_failed")

    # -- finding 3: a failed refresh must PRESERVE a previously confirmed
    # in-range action (must_flatten stays True) instead of silently
    # cancelling it, while still raising needs_attention so the staleness
    # is visible.
    def test_failed_refresh_preserves_a_previously_confirmed_flatten(self):
        class FlakySource:
            def __init__(self):
                self.fail = False
            def fetch(self, symbols, start, end):
                if self.fail:
                    raise CA.CorporateActionLookupError("boom")
                return {s: [action(s, "forward_split", TODAY)] for s in symbols}
        source = FlakySource()
        monitor = CA.CorporateActionMonitor(source, refresh_seconds=900, max_age_seconds=3600, clock=lambda: 1000.0)
        monitor.refresh({"NVDA"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        before = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION, held_symbols={"NVDA"},
                                  candidate_symbols=set(), now=1000.0)["NVDA"]
        self.assertTrue(before.must_flatten)
        self.assertFalse(before.needs_attention)
        source.fail = True
        monitor.refresh({"NVDA"}, start=TODAY, end=NEXT_SESSION, now=2000.0)
        after = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION, held_symbols={"NVDA"},
                                 candidate_symbols=set(), now=2000.0)["NVDA"]
        self.assertTrue(after.must_flatten, "a confirmed in-range action must survive a later failed refresh")
        self.assertTrue(after.needs_attention, "the failure must still be surfaced")
        self.assertEqual(after.reason, "corporate_action_forward_split")

    # -- finding 3 (staleness path): the same preservation must hold when
    # the whole cache goes stale past max_age_seconds, not just on an
    # explicit fetch failure.
    def test_staleness_preserves_a_previously_confirmed_flatten(self):
        source = self.FakeSource(result={"NVDA": [action("NVDA", "reverse_split", TODAY)]})
        monitor = CA.CorporateActionMonitor(source, refresh_seconds=1, max_age_seconds=100, clock=lambda: 1000.0)
        monitor.refresh({"NVDA"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        stale = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION, held_symbols={"NVDA"},
                                 candidate_symbols=set(), now=1200.0)["NVDA"]
        self.assertTrue(stale.must_flatten)
        self.assertTrue(stale.needs_attention)

    # -- finding 8: a failed attempt is retried on the shorter
    # `retry_seconds` interval, not the full (much longer) refresh_seconds.
    def test_failed_attempt_retries_on_the_short_retry_interval(self):
        source = self.FakeSource(error=CA.CorporateActionLookupError("boom"))
        monitor = CA.CorporateActionMonitor(source, refresh_seconds=900, retry_seconds=60, clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        self.assertEqual(len(source.calls), 1)
        # 70s later: past retry_seconds (60) but nowhere near refresh_seconds (900).
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1070.0)
        self.assertEqual(len(source.calls), 2, "a failed attempt must retry within retry_seconds, not refresh_seconds")

    def test_successful_attempt_reverts_to_the_ordinary_refresh_interval(self):
        source = self.FakeSource(error=CA.CorporateActionLookupError("boom"))
        monitor = CA.CorporateActionMonitor(source, refresh_seconds=900, retry_seconds=60, clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        source.error = None
        source.result = {"AAPL": []}
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1070.0)
        self.assertEqual(len(source.calls), 2)
        # Now successful; the NEXT call within 900s (but past 60s) must be throttled again.
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1200.0)
        self.assertEqual(len(source.calls), 2, "a successful attempt must revert to the ordinary refresh_seconds throttle")

    def test_successful_refresh_clears_degraded_state(self):
        # fix round 3 (mutation F3b): a symbol degraded by a prior failure
        # must go back to non-degraded (needs_attention False) once a
        # SUBSEQUENT refresh actually succeeds for it -- degraded must not
        # be sticky forever.
        source = self.FakeSource(error=CA.CorporateActionLookupError("boom"))
        monitor = CA.CorporateActionMonitor(source, refresh_seconds=900, retry_seconds=60, clock=lambda: 1000.0)
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        degraded = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION, held_symbols={"AAPL"},
                                    candidate_symbols=set(), now=1000.0)["AAPL"]
        self.assertTrue(degraded.needs_attention)
        source.error = None
        source.result = {"AAPL": []}
        monitor.refresh({"AAPL"}, start=TODAY, end=NEXT_SESSION, now=1070.0)
        recovered = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION, held_symbols={"AAPL"},
                                     candidate_symbols=set(), now=1070.0)["AAPL"]
        self.assertFalse(recovered.needs_attention, "a successful refresh must clear the degraded state")
        self.assertFalse(recovered.block_entry)

    def test_superseded_failure_does_not_re_degrade_a_newer_confirmed_action(self):
        """HIGH finding 1 (fix round 3): a FAILURE from a superseded
        (older-generation) attempt must be dropped exactly like a
        superseded SUCCESS -- an older attempt that eventually raises must
        not re-degrade a symbol a newer attempt already confirmed."""
        monitor = CA.CorporateActionMonitor(self.FakeSource(), clock=lambda: 1000.0)
        # Simulate: generation 1 was an old attempt (now superseded);
        # generation 2 is the newer attempt that already succeeded and
        # confirmed an action.
        old_generation = 1
        monitor._generation = 2
        monitor._apply_success({"AAPL"}, {"AAPL": [action("AAPL", "forward_split", TODAY)]}, 1030.0, 2)
        confirmed = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION, held_symbols={"AAPL"},
                                     candidate_symbols=set(), now=1030.0)["AAPL"]
        self.assertTrue(confirmed.must_flatten)
        # The OLD (generation 1) attempt now finally fails -- must be dropped.
        monitor._apply_failure({"AAPL"}, old_generation)
        after = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION, held_symbols={"AAPL"},
                                 candidate_symbols=set(), now=1030.0)["AAPL"]
        self.assertTrue(after.must_flatten, "a superseded (older-generation) failure must not re-degrade "
                                            "a newer confirmed action")
        self.assertFalse(after.needs_attention)

    def test_refresh_timed_out_invalidates_the_in_flight_generation(self):
        """HIGH finding 1 (fix round 3): refresh_timed_out() must bump the
        generation counter so a subsequent LATE write from the abandoned
        attempt (identified by the generation it captured before the
        timeout) is dropped as superseded, exactly like an ordinary
        superseded success/failure."""
        monitor = CA.CorporateActionMonitor(self.FakeSource(), clock=lambda: 1000.0)
        monitor._last_attempt = 1000.0
        monitor._generation = 1
        abandoned_generation = monitor._generation
        monitor.refresh_timed_out({"AAPL"})
        self.assertTrue(monitor._last_attempt_failed)
        self.assertIn("AAPL", monitor._degraded)
        # The abandoned attempt's thread finally finishes and tries to
        # write a stale success under its OLD (now-superseded) generation.
        monitor._apply_success({"AAPL"}, {"AAPL": [action("AAPL", "forward_split", TODAY)]},
                               1000.0, abandoned_generation)
        after = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION, held_symbols={"AAPL"},
                                 candidate_symbols=set(), now=1000.0)["AAPL"]
        self.assertTrue(after.needs_attention, "the abandoned attempt's late write must be dropped, "
                                               "leaving the symbol degraded from the timeout")
        self.assertFalse(after.must_flatten)

    def test_omission_after_a_prior_success_preserves_the_confirmed_action(self):
        """LOW finding 7 (fix round 3): a symbol omitted from an OTHERWISE
        successful fetch (most requested symbols resolved fine, this one
        did not come back at all) must not erase its own previously
        confirmed action -- treated exactly like a per-symbol failure."""
        class OmitsOneSymbol:
            def __init__(self):
                self.omit_aapl = False

            def fetch(self, symbols, start, end):
                out = {s: [action(s, "forward_split", TODAY)] for s in symbols}
                if self.omit_aapl:
                    out.pop("AAPL", None)
                return out

        source = OmitsOneSymbol()
        monitor = CA.CorporateActionMonitor(source, refresh_seconds=900, clock=lambda: 1000.0)
        monitor.refresh({"AAPL", "MSFT"}, start=TODAY, end=NEXT_SESSION, now=1000.0)
        before = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION, held_symbols={"AAPL"},
                                  candidate_symbols=set(), now=1000.0)["AAPL"]
        self.assertTrue(before.must_flatten)
        source.omit_aapl = True
        monitor.refresh({"AAPL", "MSFT"}, start=TODAY, end=NEXT_SESSION, now=1901.0)
        after = monitor.evaluate(today=TODAY, next_session_date=NEXT_SESSION, held_symbols={"AAPL"},
                                 candidate_symbols=set(), now=1901.0)["AAPL"]
        self.assertTrue(after.must_flatten, "an omission after a prior success must preserve the "
                                            "confirmed action, not erase it")
        self.assertTrue(after.needs_attention)


ALPACA = importlib.util.find_spec("alpaca") is not None


@unittest.skipUnless(ALPACA, "requires the pinned alpaca-py package")
class AlpacaCorporateActionsSourceTests(unittest.TestCase):
    """Exercises AlpacaCorporateActionsSource.fetch() through the REAL
    alpaca-py 0.44.0 request/response pipeline (raw_data=True,
    RESTClient._get_marketdata, its pagination) with only the underlying
    HTTP transport faked (requests.Session.request patched to return a
    canned JSON body) -- no network, no real credentials, but the actual
    installed SDK code this wrapper depends on DOES run, so a change to
    that SDK's own parsing/pagination/type-branch behaviour would be
    caught here (fix round 3, finding 2: earlier tests injected an
    already-parsed `.data`-style response, bypassing exactly the SDK
    behaviour that turned out to be broken)."""

    def source(self):
        return CA.AlpacaCorporateActionsSource("fake-key", "fake-secret")

    @staticmethod
    def _fake_http_response(body, status_code=200):
        import requests
        resp = requests.Response()
        resp.status_code = status_code
        resp._content = json.dumps(body).encode()
        resp.headers["Content-Type"] = "application/json"
        return resp

    def _mock_http(self, body):
        """A context manager patching requests.Session.request (BEFORE
        AlpacaCorporateActionsSource construction, so its `_bounded_request`
        wrapper's captured `original_request` is this mock) to return a
        fake HTTP 200 response carrying `body` as JSON, wrapped in the
        top-level "corporate_actions" key alpaca-py's own
        `_get_marketdata_entries` (verified via inspect.getsource against
        the installed package) requires -- exercising the real
        RESTClient._request/_one_request/_get_marketdata call chain,
        including its own page-loop. Returns (patcher, captured) where
        `captured` collects the actual outgoing request's method/url/kwargs
        for assertion."""
        import unittest.mock as mock
        import requests
        captured = {}
        envelope = {"corporate_actions": body, "next_page_token": None}

        def fake_request(self_session, method, url, **kwargs):
            captured["method"], captured["url"], captured["kwargs"] = method, url, kwargs
            return self._fake_http_response(envelope)

        return mock.patch.object(requests.Session, "request", fake_request), captured

    def test_construction_cuts_retries(self):
        # finding 2: alpaca-py's RESTClient retries up to 3 times, sleeping
        # 3s between attempts, by default -- construction must cut this to
        # the bare minimum.
        src = self.source()
        self.assertEqual(src._client._retry, 1)
        self.assertEqual(src._client._retry_wait, 1)

    def test_construction_requests_raw_data(self):
        # HIGH finding 2 (fix round 3): raw_data=True is required so an
        # unmapped bucket type reaches this wrapper's own fail-closed path
        # instead of being silently dropped by the SDK's CorporateActionsSet
        # parser first.
        src = self.source()
        self.assertTrue(src._client._use_raw_data)

    def test_construction_bounds_the_underlying_session_request_timeout(self):
        # finding 2: alpaca-py's RESTClient sets NO per-request timeout at
        # all by default -- the constructor must wrap the underlying
        # requests.Session so every call carries a bounded timeout, proven
        # here by patching requests.Session.request BEFORE construction (so
        # the wrapper's captured `original_request` is the mock) and
        # inspecting what it was actually called with.
        import unittest.mock as mock
        import requests
        captured = {}

        def fake_request(self_session, method, url, **kwargs):
            captured.update(kwargs)
            raise RuntimeError("no real network call in this test")

        with mock.patch.object(requests.Session, "request", fake_request):
            src = self.source()
            with self.assertRaises(RuntimeError):
                src._client._session.request("GET", "https://example.invalid")
        self.assertEqual(captured.get("timeout"), (5, 15))

    def test_fetch_requests_data_quality_all(self):
        """HIGH finding 3 (fix round 3): the request must ask for
        data_quality=all -- the documented Alpaca default (`complete`)
        excludes records the provider considers incomplete."""
        patcher, captured = self._mock_http({"cash_dividends": []})
        with patcher:
            src = self.source()
            src.fetch(["AAPL"], TODAY, NEXT_SESSION)
        self.assertEqual(captured["kwargs"].get("params", {}).get("data_quality"), "all")

    def test_result_at_the_page_limit_cap_is_ambiguous_fails_closed(self):
        items = [{"symbol": "AAPL", "ex_date": TODAY.isoformat()} for _ in range(1000)]
        patcher, _ = self._mock_http({"cash_dividends": items})
        with patcher:
            src = self.source()
            with self.assertRaises(CA.CorporateActionLookupError):
                src.fetch(["AAPL"], TODAY, NEXT_SESSION)

    def test_cap_counts_the_total_across_all_buckets_not_the_largest_bucket(self):
        # fix round 3 (mutation F1c): 600 + 600 = 1200 >= 1000 across TWO
        # buckets, each individually under the cap. Summing across buckets
        # must still fail closed; a max()-of-one-bucket implementation
        # would wrongly trust this as "under the cap".
        items_a = [{"symbol": "AAPL", "ex_date": TODAY.isoformat()} for _ in range(600)]
        items_b = [{"old_symbol": "OLD", "new_symbol": "NEW", "alternate_symbol": "ALT",
                   "effective_date": TODAY.isoformat()} for _ in range(600)]
        patcher, _ = self._mock_http({"cash_dividends": items_a, "unit_splits": items_b})
        with patcher:
            src = self.source()
            with self.assertRaises(CA.CorporateActionLookupError):
                src.fetch(["AAPL"], TODAY, NEXT_SESSION)

    def test_result_under_the_cap_is_trusted(self):
        patcher, _ = self._mock_http({"cash_dividends": [{"symbol": "AAPL", "ex_date": TODAY.isoformat()}]})
        with patcher:
            src = self.source()
            out = src.fetch(["AAPL"], TODAY, NEXT_SESSION)
        self.assertEqual(len(out["AAPL"]), 1)
        self.assertEqual(out["AAPL"][0].action_type, "cash_dividend")
        self.assertEqual(out["AAPL"][0].action_date, TODAY)

    def test_unmapped_type_key_fails_closed_instead_of_being_silently_dropped(self):
        # HIGH finding 2 (fix round 3): `reorganizations` is a real,
        # Alpaca-documented bucket type this guard's _TYPE_FIELD_MAP does
        # not (yet) model. With raw_data=True this reaches this wrapper's
        # own fail-closed path directly -- the pre-fix code went through
        # the SDK's CorporateActionsSet, whose 13-branch parser (verified
        # via inspect.getsource against the installed package) has no
        # else/default clause and silently drops any bucket it does not
        # recognize, turning this exact case into an apparently-clear
        # {'AAPL': []} instead of raising.
        patcher, _ = self._mock_http({"reorganizations": [{"symbol": "AAPL", "ex_date": TODAY.isoformat()}]})
        with patcher:
            src = self.source()
            with self.assertRaises(CA.CorporateActionLookupError):
                src.fetch(["AAPL"], TODAY, NEXT_SESSION)

    def test_unmapped_type_with_a_thousand_records_still_fails_closed(self):
        # finding 2: 1000 records of an unmapped type used to become a
        # silently-clear result AND evade the cap check (the SDK dropped
        # the bucket before either check ever saw it). Both this wrapper's
        # cap check and its unmapped-type check now see the raw bucket;
        # either failing closed is acceptable, but a clear/successful
        # result is not.
        items = [{"symbol": "AAPL", "ex_date": TODAY.isoformat()} for _ in range(1000)]
        patcher, _ = self._mock_http({"reorganizations": items})
        with patcher:
            src = self.source()
            with self.assertRaises(CA.CorporateActionLookupError):
                src.fetch(["AAPL"], TODAY, NEXT_SESSION)

    def test_unit_split_alternate_symbol_is_mapped(self):
        body = {"unit_splits": [{"old_symbol": "OLD", "new_symbol": "NEW", "alternate_symbol": "ALT",
                                 "effective_date": TODAY.isoformat()}]}
        patcher, _ = self._mock_http(body)
        with patcher:
            src = self.source()
            out = src.fetch(["OLD", "NEW", "ALT"], TODAY, NEXT_SESSION)
        for symbol in ("OLD", "NEW", "ALT"):
            self.assertEqual(len(out[symbol]), 1, f"{symbol} must be mapped from a unit_split")

    def test_record_missing_governing_date_is_ambiguous_for_its_own_symbol_only(self):
        """HIGH finding 3 (fix round 3): a record missing (or carrying an
        unparseable) governing date -- e.g. an incomplete record surfaced
        by data_quality=all -- must mark ONLY the symbol(s) that record
        names as LOOKUP_AMBIGUOUS, never fail the whole fetch, and never
        affect an unrelated symbol's own clean result."""
        body = {"cash_dividends": [{"symbol": "AAPL"},  # no ex_date at all
                                   {"symbol": "MSFT", "ex_date": TODAY.isoformat()}]}
        patcher, _ = self._mock_http(body)
        with patcher:
            src = self.source()
            out = src.fetch(["AAPL", "MSFT"], TODAY, NEXT_SESSION)
        self.assertEqual(out["AAPL"], CA.LOOKUP_AMBIGUOUS)
        self.assertEqual(len(out["MSFT"]), 1)


@unittest.skipUnless(NATIVE, "requires pinned Nautilus 2.0.0rc5 runtime")
class RebalanceCorporateActionGuardTests(unittest.TestCase):
    """Deliverable: native_strategy.AdaptiveStrategy.rebalance() consults
    the injected corporate-action guard -- entry blocking, pre-close
    flattening, precedence over gap_risk_stop, and no effect when the guard
    is absent or reports nothing relevant. Same FakeStrategy construction
    pattern as tests/test_adaptive_paper_exits.py's ReplaceExitTests and
    tests/test_adaptive_paper_runner.py's FakeStrategy."""

    class _FakeQuote:
        def __init__(self, bid, ask, timestamp):
            self.bid, self.ask, self.timestamp = bid, ask, timestamp

    class _FakePolicyConfig:
        def __init__(self, symbols=("AAPL", "MSFT"), quote_age_seconds=3, max_shares=5,
                    gap_stop_enabled=False, exit_replace_enabled=False):
            self.symbols = symbols
            self.quote_age_seconds = quote_age_seconds
            self.max_shares = max_shares
            self.gap_stop_enabled = gap_stop_enabled
            self.exit_replace_enabled = exit_replace_enabled

    @dataclass
    class _FakePosition:
        symbol: str
        qty: D
        average_cost: float = 100.0

    class _FakeDecision:
        def __init__(self, targets, exits=None, regime="trend", effective_leverage=1.0, signals=()):
            self.targets, self.exits = targets, exits or {}
            self.regime, self.effective_leverage, self.signals = regime, effective_leverage, signals

    class _FakePolicy:
        def __init__(self, config, decision):
            self.latest = {}
            self.config = config
            self.selector = None
            self.last_exit_fractions = {}
            self._decision = decision

        def sync_positions(self, positions, now):
            pass

        def decide(self, now, *, allow_entries, force_exit, operational=None):
            return self._decision

    class _FakeLedger:
        def __init__(self, positions=None):
            self._positions = positions or {}

        def intents(self):
            return []

        def prior_rth_closes(self):
            return {}

        def unresolved(self):
            return []

        def positions(self):
            return self._positions

    class _FakeGuard:
        """Scripted guard: returns the decisions it was constructed with
        (keyed by symbol), FILTERED to exactly the symbols actually
        requested (held_symbols | candidate_symbols) -- fix round 3: a
        prior version returned every scripted decision unconditionally,
        which masked the production bug where a symbol whose signal
        disappeared (and whose resting buy order therefore never made it
        into candidate_symbols) was silently never evaluated at all; this
        fake would still have reported its scripted decision anyway. The
        real corporate_actions.evaluate_guard performs exactly this same
        held|candidate filter."""

        def __init__(self, decisions):
            self.decisions = decisions
            self.calls = []

        def evaluate(self, *, today, next_session_date, held_symbols, candidate_symbols, now):
            self.calls.append({"today": today, "next_session_date": next_session_date,
                               "held_symbols": set(held_symbols), "candidate_symbols": set(candidate_symbols)})
            relevant = set(held_symbols) | set(candidate_symbols)
            return {symbol: decision for symbol, decision in self.decisions.items() if symbol in relevant}

    def strategy(self, *, held=None, targets=None, guard_decisions=None, clock=lambda: 1790256600.0):
        # 2026-09-24 09:30:00 America/New_York in epoch seconds (RTH open) --
        # picked so session_at()/next_trading_day() both resolve without a
        # ValueError under the frozen 2026 calendar (verified: session_date
        # 2026-09-24, next_trading_day 2026-09-25 -- this file's module-level
        # TODAY/NEXT_SESSION constants).
        from native_strategy import AdaptiveStrategy

        class FakeOrderFactory:
            def __init__(self):
                self.calls = []

            def limit(self, instrument_id, side, quantity, price, *, time_in_force, client_order_id, tags):
                self.calls.append({"instrument_id": str(instrument_id), "side": side,
                                   "quantity": str(quantity), "price": str(price), "tags": list(tags)})
                return self.calls[-1]

        class FakeStrategy(AdaptiveStrategy):
            @property
            def order_factory(self):
                return self._fake_order_factory

        held = held or {}
        positions = {s: self._FakePosition(symbol=s, qty=D(str(q))) for s, q in held.items()}
        config = self._FakePolicyConfig()
        decision = self._FakeDecision(targets=targets or {})
        policy = self._FakePolicy(config, decision)
        guard = self._FakeGuard(guard_decisions) if guard_decisions is not None else None
        strat = FakeStrategy(policy, self._FakeLedger(positions), "fixture", clock=clock,
                             corporate_action_guard=guard)
        strat._fake_order_factory = FakeOrderFactory()
        strat.submitted, strat.events = [], []
        strat.submit_order = strat.submitted.append
        strat.event_sink = strat.events.append
        strat.started = True
        strat.enabled = True
        for symbol in set(held) | set(targets or {}):
            policy.latest[symbol] = self._FakeQuote(100.0, 100.02, clock())
        return strat

    def decision_for(self, symbol, *, block_entry=False, must_flatten=False, needs_attention=False,
                     reason=None, action_type=None, action_date=None):
        return CA.GuardDecision(symbol=symbol, block_entry=block_entry, must_flatten=must_flatten,
                                needs_attention=needs_attention, reason=reason,
                                action_type=action_type, action_date=action_date)

    def test_no_guard_configured_is_inert(self):
        strategy = self.strategy(held={}, targets={"AAPL": 1})
        strategy.rebalance()
        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(strategy._fake_order_factory.calls[0]["side"], OrderSide.BUY)

    def test_blocked_entry_symbol_never_gets_a_buy_order(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, needs_attention=True,
                                                      reason="corporate_action_lookup_failed"),
                           "MSFT": self.decision_for("MSFT")}
        strategy = self.strategy(held={}, targets={"AAPL": 1, "MSFT": 1}, guard_decisions=guard_decisions)
        strategy.rebalance()
        self.assertEqual(len(strategy.submitted), 1)
        instrument_ids = [c["instrument_id"] for c in strategy._fake_order_factory.calls]
        self.assertNotIn("AAPL.ALPACA", instrument_ids)
        self.assertIn("MSFT.ALPACA", instrument_ids)

    def test_held_symbol_with_qualifying_action_is_flattened_before_close(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, must_flatten=True,
                                                      reason="corporate_action_reverse_split",
                                                      action_type="reverse_split", action_date=TODAY)}
        strategy = self.strategy(held={"AAPL": 3}, targets={"AAPL": 3}, guard_decisions=guard_decisions)
        strategy.rebalance()
        self.assertEqual(len(strategy.submitted), 1)
        call = strategy._fake_order_factory.calls[0]
        self.assertEqual(call["side"], OrderSide.SELL)
        self.assertEqual(call["quantity"], "3")
        self.assertIn("reason=corporate_action_flatten", call["tags"])
        # fix round 3 (mutation F5b): the strategy must actually RECORD
        # this tick's must_flatten set on itself -- runner.py's outcome
        # construction reads this attribute directly.
        self.assertEqual(strategy._ca_last_must_flatten, {"AAPL"})

    def test_flatten_still_forced_even_when_decide_would_have_kept_the_position(self):
        """Unlike an ordinary rebalance-delta sell, the forced flatten fires
        even though this tick's own decision.targets kept the full
        quantity (mirrors gap_risk_stop's own override of the ordinary
        held<=target skip)."""
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, must_flatten=True,
                                                      reason="corporate_action_merger",
                                                      action_type="merger", action_date=TODAY)}
        strategy = self.strategy(held={"AAPL": 2}, targets={"AAPL": 2}, guard_decisions=guard_decisions)
        strategy.rebalance()
        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(strategy._fake_order_factory.calls[0]["side"], OrderSide.SELL)

    def test_symbol_without_any_action_is_unaffected(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL")}
        strategy = self.strategy(held={}, targets={"AAPL": 2}, guard_decisions=guard_decisions)
        strategy.rebalance()
        self.assertEqual(len(strategy.submitted), 1)
        self.assertEqual(strategy._fake_order_factory.calls[0]["side"], OrderSide.BUY)
        self.assertEqual(strategy._fake_order_factory.calls[0]["quantity"], "2")

    def test_needs_attention_events_are_recorded_without_forcing_a_flatten(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, needs_attention=True,
                                                      reason="corporate_action_lookup_ambiguous")}
        strategy = self.strategy(held={"AAPL": 1}, targets={"AAPL": 1}, guard_decisions=guard_decisions)
        strategy.rebalance()
        self.assertEqual(strategy.submitted, [])  # not blocked from holding, not forced to flatten
        events = [e for e in strategy.events if e.get("type") == "corporate_action_guard"]
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["needs_attention"])
        self.assertFalse(events[0]["must_flatten"])
        # MEDIUM finding 4 (fix round 3): the strategy must record this
        # held symbol into its own attention-tracking attribute --
        # runner.py's outcome construction reads this directly so
        # _honest_overnight_hold can refuse a false "held_overnight".
        self.assertEqual(strategy._ca_last_needs_attention_held, {"AAPL"})

    def test_flatten_event_carries_no_credential_value_only_bounded_fields(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, must_flatten=True,
                                                      reason="corporate_action_cash_dividend",
                                                      action_type="cash_dividend", action_date=TODAY)}
        strategy = self.strategy(held={"AAPL": 1}, targets={"AAPL": 1}, guard_decisions=guard_decisions)
        strategy.rebalance()
        events = [e for e in strategy.events if e.get("type") == "corporate_action_guard"]
        self.assertEqual(len(events), 1)
        self.assertEqual(set(events[0]), {"type", "symbol", "block_entry", "must_flatten",
                                          "needs_attention", "reason", "action_type", "action_date"})

    def test_decision_event_carries_the_guard_summary_lists(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, must_flatten=True,
                                                      reason="corporate_action_spin_off",
                                                      action_type="spin_off", action_date=TODAY),
                           "MSFT": self.decision_for("MSFT", block_entry=True,
                                                      reason="corporate_action_lookup_failed",
                                                      needs_attention=True)}
        strategy = self.strategy(held={"AAPL": 1}, targets={"AAPL": 1, "MSFT": 1}, guard_decisions=guard_decisions)
        strategy.rebalance()
        events = [e for e in strategy.events if e.get("type") == "decision"]
        self.assertEqual(len(events), 1)
        self.assertEqual(sorted(events[0]["corporate_action_must_flatten"]), ["AAPL"])
        self.assertEqual(sorted(events[0]["corporate_action_block_entry"]), ["AAPL", "MSFT"])

    # -- finding 6: a session-calendar failure (a clock outside the frozen
    # calendar's covered years) must block entry and flag needs_attention,
    # but must NOT force-flatten a held position -- a calendar gap is not
    # evidence of an actual corporate action.
    def test_calendar_failure_blocks_entry_but_never_force_flattens(self):
        # 2028-01-04 10:00 ET -- outside sessions.CALENDAR_YEARS (2026, 2027).
        out_of_range_clock = lambda: 1830610800.0
        guard_decisions = {}  # never consulted: the ValueError branch short-circuits first
        strategy = self.strategy(held={"AAPL": 3}, targets={"AAPL": 3}, guard_decisions=guard_decisions,
                                 clock=out_of_range_clock)
        strategy.rebalance()
        self.assertEqual(strategy.submitted, [], "a calendar failure alone must never force a flatten sell")
        events = [e for e in strategy.events if e.get("type") == "corporate_action_guard"]
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["block_entry"])
        self.assertFalse(events[0]["must_flatten"])
        self.assertTrue(events[0]["needs_attention"])
        self.assertEqual(events[0]["reason"], "corporate_action_session_unknown")

    # -- fix round 3 (mutation F4a): the guard's own hold horizon must be
    # the NEXT TRADING DAY (skipping weekends/holidays), not a raw
    # calendar-day-plus-one -- proven with a Friday tick, whose "next
    # session" is the following Monday, not Saturday.
    def test_friday_horizon_is_the_following_monday_not_saturday(self):
        # 2026-09-25 10:00 ET is a Friday (RTH open) under the frozen 2026
        # calendar.
        friday_clock = lambda: 1790344800.0
        strategy = self.strategy(held={"AAPL": 1}, targets={"AAPL": 1}, guard_decisions={}, clock=friday_clock)
        strategy.rebalance()
        self.assertEqual(len(strategy.corporate_action_guard.calls), 1)
        call = strategy.corporate_action_guard.calls[0]
        self.assertEqual(call["today"], date(2026, 9, 25))
        self.assertEqual(call["next_session_date"], date(2026, 9, 28),
                         "the horizon must skip the weekend to the following Monday, not land on Saturday")

    # -- finding 9: a symbol flagged by BOTH the corporate-action guard
    # (must_flatten) and the gap-risk stop must get exactly ONE sell
    # action, not two competing ones.
    def test_symbol_flagged_by_both_guards_gets_exactly_one_sell(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, must_flatten=True,
                                                      reason="corporate_action_reverse_split",
                                                      action_type="reverse_split", action_date=TODAY)}
        strategy = self.strategy(held={"AAPL": 4}, targets={"AAPL": 4}, guard_decisions=guard_decisions)
        strategy._gap_risk_stop_symbols = lambda now, held: {"AAPL"}
        strategy.rebalance()
        aapl_sells = [c for c in strategy._fake_order_factory.calls
                     if c["instrument_id"] == "AAPL.ALPACA" and c["side"] == OrderSide.SELL]
        self.assertEqual(len(aapl_sells), 1, "AAPL must get exactly one sell, not one per guard")
        self.assertEqual(aapl_sells[0]["quantity"], "4")

    # -- finding 10: a resting BUY order for a symbol newly blocked this
    # tick must be cancelled, not left to potentially fill afterwards.
    def test_resting_buy_is_cancelled_for_a_newly_blocked_symbol(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, needs_attention=True,
                                                      reason="corporate_action_lookup_failed")}
        strategy = self.strategy(held={}, targets={"AAPL": 1}, guard_decisions=guard_decisions)
        strategy.cancelled = []
        strategy.cancel_order = lambda cid: strategy.cancelled.append(str(cid))
        strategy.pending["resting-buy-1"] = {"symbol": "AAPL", "side": "buy", "created": 0.0}
        strategy.rebalance()
        self.assertIn("resting-buy-1", strategy.cancelled)
        self.assertTrue(strategy.pending["resting-buy-1"]["cancel_requested"])

    # -- MEDIUM finding 5 (fix round 3): a symbol whose signal disappeared
    # (no longer in decision.targets) but whose buy from a PRIOR tick is
    # still resting must still be evaluated by the guard -- a corporate
    # action discovered on this now-untargeted symbol must still cancel
    # that resting buy, not leave it silently eligible to fill.
    def test_resting_buy_is_cancelled_when_its_signal_disappears_while_it_rests(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, needs_attention=True,
                                                      reason="corporate_action_lookup_failed")}
        # targets={} -- AAPL's signal is gone this tick, unlike the test
        # above where it is still targeted.
        strategy = self.strategy(held={}, targets={}, guard_decisions=guard_decisions)
        strategy.cancelled = []
        strategy.cancel_order = lambda cid: strategy.cancelled.append(str(cid))
        strategy.pending["resting-buy-1"] = {"symbol": "AAPL", "side": "buy", "created": 0.0}
        strategy.rebalance()
        self.assertIn("resting-buy-1", strategy.cancelled,
                      "a resting buy must be cancelled even after its own signal disappeared")
        self.assertTrue(strategy.pending["resting-buy-1"]["cancel_requested"])
        # The guard's own evaluate() call must have actually been asked
        # about AAPL as a candidate (via the pending-buy symbol union),
        # not silently skipped.
        self.assertIn("AAPL", strategy.corporate_action_guard.calls[-1]["candidate_symbols"])

    # -- finding 11 (byte-identical claim): with the guard off (None,
    # default), the decision event must carry neither
    # corporate_action_block_entry nor corporate_action_must_flatten.
    def test_decision_event_has_no_corporate_action_keys_when_guard_is_off(self):
        strategy = self.strategy(held={}, targets={"AAPL": 1}, guard_decisions=None)
        strategy.rebalance()
        events = [e for e in strategy.events if e.get("type") == "decision"]
        self.assertEqual(len(events), 1)
        self.assertNotIn("corporate_action_block_entry", events[0])
        self.assertNotIn("corporate_action_must_flatten", events[0])

    # -- finding 11 (emit-on-change): an unchanged guard decision for the
    # same symbol across consecutive ticks must not re-emit a duplicate
    # corporate_action_guard event.
    def test_guard_event_not_re_emitted_when_the_decision_is_unchanged(self):
        guard_decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, must_flatten=True,
                                                      reason="corporate_action_cash_dividend",
                                                      action_type="cash_dividend", action_date=TODAY)}
        strategy = self.strategy(held={"AAPL": 1}, targets={"AAPL": 1}, guard_decisions=guard_decisions)
        strategy.rebalance()
        strategy.rebalance()
        events = [e for e in strategy.events if e.get("type") == "corporate_action_guard"]
        self.assertEqual(len(events), 1, "an unchanged decision must be emitted only once")

    def test_guard_event_re_emitted_when_the_decision_changes(self):
        guard = self._FakeGuard({"AAPL": self.decision_for("AAPL", block_entry=True, needs_attention=True,
                                                            reason="corporate_action_lookup_failed")})
        strategy = self.strategy(held={"AAPL": 1}, targets={"AAPL": 1})
        strategy.corporate_action_guard = guard
        strategy.rebalance()
        guard.decisions = {"AAPL": self.decision_for("AAPL", block_entry=True, must_flatten=True,
                                                      reason="corporate_action_cash_dividend",
                                                      action_type="cash_dividend", action_date=TODAY)}
        strategy.rebalance()
        events = [e for e in strategy.events if e.get("type") == "corporate_action_guard"]
        self.assertEqual(len(events), 2, "a changed decision must be re-emitted")

    # -- NIT finding 9 (fix round 3): a symbol that was previously flagged
    # and then goes fully clear must emit one explicit "cleared" event.
    def test_guard_emits_a_cleared_event_when_a_flagged_symbol_resolves(self):
        guard = self._FakeGuard({"AAPL": self.decision_for("AAPL", block_entry=True, needs_attention=True,
                                                            reason="corporate_action_lookup_failed")})
        strategy = self.strategy(held={"AAPL": 1}, targets={"AAPL": 1})
        strategy.corporate_action_guard = guard
        strategy.rebalance()
        guard.decisions = {"AAPL": self.decision_for("AAPL")}  # fully clear now
        strategy.rebalance()
        events = [e for e in strategy.events if e.get("type") == "corporate_action_guard"]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1]["reason"], "corporate_action_cleared")
        self.assertFalse(events[1]["block_entry"])
        self.assertFalse(events[1]["must_flatten"])
        self.assertFalse(events[1]["needs_attention"])
        # A symbol never flagged in the first place gets no clear event.
        guard2 = self._FakeGuard({"MSFT": self.decision_for("MSFT")})
        strategy2 = self.strategy(held={"MSFT": 1}, targets={"MSFT": 1})
        strategy2.corporate_action_guard = guard2
        strategy2.rebalance()
        self.assertEqual([e for e in strategy2.events if e.get("type") == "corporate_action_guard"], [])


if __name__ == "__main__":
    unittest.main()
