"""Mover trial mode, pure logic: config, scan, sizing, pricing, exits and the order state
machine. Synthetic fixtures only (evidence class SYN); no broker, network or credentials."""
from datetime import datetime, time as dtime, timezone
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

SOURCE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper"
sys.path.insert(0, str(SOURCE))
import mover  # noqa: E402
import mover_runner  # noqa: E402
from safety import Ledger, Position, Quote, SafetyError  # noqa: E402
from sessions import order_extended_hours_flag  # noqa: E402
from transport import TransportError, normalize_intent  # noqa: E402

try:  # package mode (python -m unittest tests.x) or discover -s tests (top-level modules)
    from .adaptive_paper_hermetic import patch_default_stop, restore_default_stop
except ImportError:
    from adaptive_paper_hermetic import patch_default_stop, restore_default_stop  # noqa: E402

_HERMETIC_TOKEN = None


def setUpModule():
    global _HERMETIC_TOKEN
    _HERMETIC_TOKEN = patch_default_stop()


def tearDownModule():
    restore_default_stop(_HERMETIC_TOKEN)


CONFIG = SOURCE / "config-mover.json"
# 2026-09-24 08:00:05 EDT (UTC-4): five seconds after the example rule's 08:00.
SCAN_TIME = datetime(2026, 9, 24, 12, 0, 5, tzinfo=timezone.utc).timestamp()
PRE_TS = datetime(2026, 9, 24, 12, 30, tzinfo=timezone.utc)    # 08:30 ET, PRE
RTH_TS = datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc)     # 11:00 ET, RTH
POST_TS = datetime(2026, 9, 24, 21, 0, tzinfo=timezone.utc)    # 17:00 ET, POST
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)


def config_data():
    return json.loads(CONFIG.read_text())


def load(data):
    with tempfile.TemporaryDirectory() as root:
        path = Path(root) / "config.json"
        path.write_text(json.dumps(data))
        return mover.load_mover_config(path)


def scan_dict(**changes):
    data = {"schema_version": 1, "kind": "mover_scan", "protocol": mover.PROTOCOL_ID,
            "rule": "08:00|G20|V1000000|any", "scan_time": "2026-09-24T12:00:05Z",
            "symbols": [
                {"symbol": "ABCD", "rank": 1, "price_at_t": "3.21", "dollar_volume_at_t": "12500000",
                 "entry_bar_dollar_volume": "450000", "gain_pct_at_t": "45.2"},
                {"symbol": "WXYZ", "rank": 2, "price_at_t": "45.50", "dollar_volume_at_t": "8000000",
                 "entry_bar_dollar_volume": None}]}
    data.update(changes)
    return data


def scan_bytes(**changes):
    return json.dumps(scan_dict(**changes)).encode()


class RuleAndConfig(unittest.TestCase):
    def test_example_config_is_pre_market_x2_rung_one_with_conservative_caps(self):
        config, limits, settings = mover.load_mover_config(CONFIG)
        self.assertEqual(settings.session_scope, "pre_market_only")
        self.assertEqual(settings.trial_end_et, dtime(9, 25))
        self.assertEqual(settings.exit_rule, "X2")
        self.assertEqual(settings.rung_schedule, ((1, 20, D(1)),))
        self.assertEqual((settings.entry_cap_bps, settings.entry_timeout_seconds), (D(50), 60))
        self.assertEqual(settings.max_scan_age_seconds, 300)
        self.assertEqual((limits.max_order_notional_usd, limits.max_gross_exposure_usd), (D(200), D(2000)))
        self.assertEqual(limits.max_order_qty_mode, "notional")
        self.assertIsNone(limits.leverage)
        self.assertTrue(config["sessions"]["extended_hours"])
        self.assertNotIn("symbols", config)
        self.assertEqual(mover.engine_config(config, ["WXYZ", "ABCD"])["symbols"], ["ABCD", "SPY", "WXYZ"])

    def test_rule_grammar(self):
        rule = mover.parse_rule("09:15|G12.5|V5M|news_before_t")
        self.assertEqual((rule.at_et, rule.min_gain_pct, rule.min_dollar_volume, rule.news),
                         (dtime(9, 15), D("12.5"), D(5000000), "news_before_t"))
        self.assertEqual(mover.parse_rule("08:00|G20|V1000000|any").min_dollar_volume, D(1000000))
        for bad in ("8:00|G20|V1000000|any", "08:00|G20|V1e6|any", "08:00|G20|V1000000|maybe", "03:59|G20|V1|any",
                    "20:00|G20|V1|any", "24:00|G20|V1|any", "08:00|G-1|V1|any", "", None, 800):
            with self.subTest(rule=bad), self.assertRaisesRegex(ValueError, "invalid_mover_rule"):
                mover.parse_rule(bad)

    def test_config_refusals(self):
        cases = []

        def case(reason, mutate):
            data = config_data()
            mutate(data)
            cases.append((reason, data))

        case("mover_universe_comes_from_scan", lambda d: d.update(symbols=["ABCD"]))
        case("mover_x1_requires_regular_session", lambda d: d["mover"].update(exit="X1"))
        case("mover_pre_market_window_invalid", lambda d: d["mover"].update(trial_end_et="09:31"))
        case("mover_pre_market_window_invalid", lambda d: d["mover"].update(rule="09:30|G20|V1000000|any"))
        case("mover_requires_flat_end", lambda d: d["sessions"].update(overnight_holds=True))
        case("mover_pre_market_requires_extended_hours", lambda d: (
            d.update(regular_session_only=True, extended_hours_enabled=False),
            d["sessions"].update(extended_hours=False)))
        case("mover_rung_requires_leverage_policy", lambda d: d["mover"].update(
            rung_schedule=[{"from_session": 1, "to_session": 20, "rung": "2"}]))
        case("invalid_mover_rung_schedule", lambda d: d["mover"].update(
            rung_schedule=[{"from_session": 1, "to_session": 10, "rung": "1"},
                           {"from_session": 12, "to_session": 20, "rung": "1"}]))
        case("invalid_mover_rung_schedule", lambda d: d["mover"].update(
            rung_schedule=[{"from_session": 1, "to_session": 20, "rung": "5"}]))
        case("unqualified_lane_configuration", lambda d: d.update(endpoint="https://api.alpaca.markets"))
        case("unqualified_lane_configuration", lambda d: d.update(max_leverage="2"))
        case("unqualified_lane_configuration", lambda d: d.update(catalyst_orders_enabled=True))
        case("mover_symbol_or_order_caps_below_scan_size", lambda d: d.update(max_held_symbols=4))
        case("invalid_mover_setting:limit_cap_bps", lambda d: d["mover"]["entry"].update(limit_cap_bps="0"))
        case("invalid_mover_setting:max_scan_age_seconds", lambda d: d["mover"].update(max_scan_age_seconds=301))
        case("invalid_mover_setting:stream_quote_timeout_seconds",
             lambda d: d["mover"].update(stream_quote_timeout_seconds=2))
        case("invalid_mover_setting:exit", lambda d: d["mover"].update(exit="X5"))
        case("invalid_mover_block", lambda d: d["mover"].update(extra=True))
        case("unqualified_data_feed", lambda d: d.update(feed="IEX"))
        case("unqualified_mover_configuration", lambda d: d.update(protocol="other"))
        for reason, data in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, "^" + re.escape(reason) + "$"):
                load(data)

    def test_engine_risk_bounds_still_apply(self):
        data = config_data()
        data["max_gross_loss_usd"] = "2000"  # above capital / 10
        with self.assertRaisesRegex(SafetyError, "risk_limit_out_of_bounds"):
            load(data)

    def test_rung_above_one_requires_and_accepts_the_canonical_leverage_policy(self):
        import leverage
        data = config_data()
        data.update(max_leverage="2", max_gross_exposure_usd="4000", leverage_policy=leverage.CANONICAL_V1_BLOCK)
        data["mover"]["session_scope"] = "any_session"
        data["mover"]["trial_end_et"] = "15:59"
        data["mover"]["rung_schedule"] = [{"from_session": 1, "to_session": 20, "rung": "1"},
                                          {"from_session": 21, "to_session": 40, "rung": "2"}]
        config, limits, settings = load(data)
        self.assertEqual(limits.leverage.max_leverage, D(2))
        self.assertIs(config["_leverage_policy"], limits.leverage)
        # The pre-registered schedule caps PRE/POST at 1x, whatever the mover rung says.
        self.assertEqual(limits.leverage.envelope(session="PRE", drawdown_fraction=D(0)), D(1))
        self.assertEqual(limits.leverage.envelope(session="RTH", drawdown_fraction=D(0)), D(2))


class ScanValidation(unittest.TestCase):
    def setUp(self):
        _, self.limits, self.settings = mover.load_mover_config(CONFIG)

    def scan(self, raw=None, now=SCAN_TIME + 20):
        return mover.load_scan(raw if raw is not None else scan_bytes(), self.settings, now=now)

    def refused(self, reason, raw, now=SCAN_TIME + 20):
        with self.assertRaises(mover.MoverRefusal) as caught:
            self.scan(raw, now)
        self.assertEqual(str(caught.exception), reason)

    def test_valid_scan_is_hashed_ranked_and_regime_defaults_conservative(self):
        rows = scan_dict()["symbols"][::-1]  # out of rank order in the file
        raw = scan_bytes(symbols=rows)
        scan = self.scan(raw)
        self.assertEqual(scan.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual([s.symbol for s in scan.symbols], ["ABCD", "WXYZ"])
        self.assertEqual(scan.session_date.isoformat(), "2026-09-24")
        self.assertEqual((scan.regime_factor, scan.regime_source), (D("0.5"), "absent_conservative_default"))
        self.assertIsNone(scan.symbols[1].entry_bar_dollar_volume)
        self.assertAlmostEqual(scan.age_seconds, 20)

    def test_scan_older_than_five_minutes_is_refused(self):
        self.scan(now=SCAN_TIME + 300)
        self.refused("scan_stale", scan_bytes(), now=SCAN_TIME + 300.001)

    def test_future_or_pre_rule_scans_and_rule_mismatch_are_refused(self):
        self.refused("scan_from_future", scan_bytes(), now=SCAN_TIME - 1)
        self.refused("scan_precedes_rule_time", scan_bytes(scan_time="2026-09-24T11:59:59Z"), now=SCAN_TIME)
        self.refused("scan_rule_differs_from_config", scan_bytes(rule="08:00|G10|V1000000|any"))
        self.refused("scan_time_invalid", scan_bytes(scan_time="2026-09-24 12:00:05"))
        self.refused("scan_session_date_mismatch", scan_bytes(session_date="2026-09-25"))
        self.refused("scan_schema_invalid", scan_bytes(kind="other"))

    def test_symbol_rows_are_bounded_unique_and_follow_their_rule(self):
        row = scan_dict()["symbols"][0]
        six = [dict(row, symbol=s, rank=i + 1) for i, s in enumerate(["AA", "BB", "CC", "DD", "EE", "FF"])]
        self.refused("scan_symbols_invalid", scan_bytes(symbols=six))
        self.refused("scan_rank_or_symbol_duplicate", scan_bytes(symbols=[row, dict(row, rank=2)]))
        self.refused("scan_rank_or_symbol_duplicate", scan_bytes(symbols=[row, dict(row, symbol="EFGH")]))
        self.refused("scan_ranks_not_contiguous", scan_bytes(symbols=[dict(row, rank=2)]))
        self.refused("scan_symbol_fields_invalid", scan_bytes(symbols=[{k: v for k, v in row.items()
                                                                       if k != "entry_bar_dollar_volume"}]))
        self.refused("scan_symbol_invalid", scan_bytes(symbols=[dict(row, symbol="abcd")]))
        self.refused("scan_price_invalid", scan_bytes(symbols=[dict(row, price_at_t="0")]))
        self.refused("scan_price_invalid", scan_bytes(symbols=[dict(row, price_at_t=True)]))
        self.refused("scan_symbol_below_rule_dollar_volume",
                     scan_bytes(symbols=[dict(row, dollar_volume_at_t="999999.99")]))
        self.refused("scan_symbol_below_rule_gain", scan_bytes(symbols=[dict(row, gain_pct_at_t="19.9")]))
        self.assertEqual(self.scan(scan_bytes(symbols=[dict(row, price_at_t=3.21)])).symbols[0].price_at_t, D("3.21"))

    def test_news_rule_requires_the_news_flag(self):
        data = config_data()
        data["mover"]["rule"] = "08:00|G20|V1000000|news_before_t"
        _, _, settings = load(data)
        row = scan_dict()["symbols"][0]
        raw = scan_bytes(rule="08:00|G20|V1000000|news_before_t", symbols=[row])
        with self.assertRaisesRegex(mover.MoverRefusal, "scan_symbol_without_required_news"):
            mover.load_scan(raw, settings, now=SCAN_TIME)
        raw = scan_bytes(rule="08:00|G20|V1000000|news_before_t", symbols=[dict(row, news_before_t=True)])
        self.assertTrue(mover.load_scan(raw, settings, now=SCAN_TIME).symbols[0].news_before_t)

    def test_regime_factor_from_inputs_or_precomputed(self):
        inputs = {"spy_prev_close": "661.2", "spy_sma20": "650.1", "spy_rv20": "0.11", "spy_rv20_median252": "0.14"}
        self.assertEqual(self.scan(scan_bytes(regime={"inputs": inputs})).regime_factor, D(1))
        below = dict(inputs, spy_prev_close="640")
        self.assertEqual(self.scan(scan_bytes(regime={"inputs": below})).regime_factor, D("0.5"))
        high_vol = dict(inputs, spy_rv20="0.20")
        self.assertEqual(self.scan(scan_bytes(regime={"inputs": high_vol})).regime_factor, D("0.5"))
        scan = self.scan(scan_bytes(regime={"factor": "1"}))
        self.assertEqual((scan.regime_factor, scan.regime_source), (D(1), "scan_precomputed"))
        self.refused("scan_regime_factor_inconsistent", scan_bytes(regime={"factor": "1", "inputs": below}))
        self.refused("scan_regime_invalid", scan_bytes(regime={"factor": "0.7"}))
        self.refused("scan_regime_invalid", scan_bytes(regime={"inputs": {"spy_prev_close": "1"}}))

    def test_empty_scan_is_valid_and_empty(self):
        self.assertEqual(self.scan(scan_bytes(symbols=[])).symbols, ())


class SessionsSizingAndTiming(unittest.TestCase):
    def setUp(self):
        self.config, self.limits, self.settings = mover.load_mover_config(CONFIG)
        self.schedule = self.settings.rung_schedule

    def test_drawdown_ladder_from_the_equity_peak(self):
        first = mover.plan_session(None, equity=D(10000), rung_schedule=self.schedule)
        self.assertEqual((first.number, first.rung, first.drawdown_factor, first.paused), (1, D(1), D(1), False))
        state = {"sessions_started": 3, "equity_peak_usd": "10000", "pause_sessions_remaining": 0}
        for equity, factor in (("9000", D(1)), ("8999", D("0.5")), ("8000", D("0.5"))):
            with self.subTest(equity=equity):
                plan = mover.plan_session(state, equity=D(equity), rung_schedule=self.schedule)
                self.assertEqual((plan.number, plan.drawdown_factor, plan.paused), (4, factor, False))
        paused = mover.plan_session(state, equity=D("7999"), rung_schedule=self.schedule)
        self.assertEqual((paused.paused, paused.drawdown_factor, paused.pause_sessions_remaining_after),
                         (True, D(0), 9))
        # The pause holds for ten sessions in total, then the ladder is re-evaluated.
        state = mover.session_state_after(paused, equity_end=D("7999"))
        for remaining in range(8, -1, -1):
            plan = mover.plan_session(state, equity=D("9500"), rung_schedule=self.schedule)
            self.assertTrue(plan.paused)
            self.assertEqual(plan.pause_sessions_remaining_after, remaining)
            state = mover.session_state_after(plan, equity_end=D("9500"))
        resumed = mover.plan_session(state, equity=D("9500"), rung_schedule=self.schedule)
        self.assertEqual((resumed.paused, resumed.drawdown_factor, resumed.number), (False, D(1), 14))

    def test_equity_peak_rises_and_sessions_beyond_the_schedule_are_refused(self):
        plan = mover.plan_session(None, equity=D(10000), rung_schedule=self.schedule)
        self.assertEqual(mover.session_state_after(plan, equity_end=D(10250))["equity_peak_usd"], "10250")
        with self.assertRaisesRegex(mover.MoverRefusal, "mover_session_beyond_rung_schedule"):
            mover.plan_session({"sessions_started": 20, "equity_peak_usd": "10000", "pause_sessions_remaining": 0},
                               equity=D(10000), rung_schedule=self.schedule)
        with self.assertRaisesRegex(mover.MoverRefusal, "mover_state_invalid"):
            mover.plan_session({"sessions_started": -1}, equity=D(10000), rung_schedule=self.schedule)

    def test_leverage_multiple(self):
        self.assertEqual(mover.leverage_multiple(D(1), D("0.5"), D(1)), D("0.5"))
        self.assertEqual(mover.leverage_multiple(D(4), D(1), D(1)), D(4))
        self.assertEqual(mover.leverage_multiple(D(4), D(1), D("0.5")), D(2))

    def row(self, symbol, rank, price, volume, bar=None):
        return mover.ScanSymbol(symbol, rank, D(price), D(volume), None if bar is None else D(bar))

    def test_sizing_formula_and_every_cap(self):
        symbols = (self.row("AAA", 1, "10", "50000000"), self.row("BBB", 2, "3", "50000000"),
                   self.row("CCC", 3, "10", "100000"), self.row("DDD", 4, "10", "50000000", "5000"))
        sized = mover.size_symbols(symbols, equity=D(10000), leverage=D(2), gross_budget=D(100000),
                                   per_order_cap=D(10000), allowance=D(1))
        a, b, c, d = sized
        self.assertEqual((a.leverage_i, a.raw_notional_usd, a.notional_usd, a.binding), (D(2), D(4000), D(4000), "formula"))
        self.assertEqual((b.leverage_i, b.notional_usd), (D(1), D(2000)))  # below 5 USD: L_i = min(L, 1)
        self.assertEqual((c.notional_usd, c.binding), (D(1000), "dollar_volume_1pct"))
        self.assertEqual((d.notional_usd, d.binding), (D(500), "entry_bar_10pct"))
        per_order = mover.size_symbols(symbols[:1], equity=D(10000), leverage=D(1), gross_budget=D(100000),
                                       per_order_cap=D(200), allowance=D(2))[0]
        self.assertEqual((per_order.notional_usd, per_order.binding), (D(200), "per_order"))

    def test_gross_budget_allocates_in_rank_order_and_skips(self):
        symbols = (self.row("AAA", 1, "10", "50000000"), self.row("BBB", 2, "10", "50000000"),
                   self.row("CCC", 3, "10", "50000000"), self.row("EXP", 4, "1500", "50000000"))
        a, b, c, e = mover.size_symbols(symbols, equity=D(10000), leverage=D(1), gross_budget=D(2500),
                                        per_order_cap=D(2000), allowance=D(2))
        self.assertEqual((a.notional_usd, b.notional_usd, b.binding), (D(2000), D(500), "gross_remaining"))
        self.assertEqual((c.notional_usd, c.skip_reason), (D(0), "notional_below_one_share"))
        self.assertEqual(e.skip_reason, "price_exceeds_per_order_headroom")  # 1500 x 2 > 2000 per order
        paused = mover.size_symbols(symbols[:1], equity=D(10000), leverage=D(0), gross_budget=D(2500),
                                    per_order_cap=D(2000), allowance=D(2))[0]
        self.assertEqual(paused.skip_reason, "leverage_zero")

    def test_plan_uses_the_appreciation_allowance_and_guard(self):
        scan = mover.load_scan(scan_bytes(), self.settings, now=SCAN_TIME + 20)
        session = mover.plan_session(None, equity=D(10000), rung_schedule=self.schedule)
        plan = mover.build_plan(self.settings, self.limits, scan, session, trial_id="t1", evidence_class="PAPER",
                                t0=SCAN_TIME + 25, equity=D(10000))
        self.assertEqual(plan.leverage, D("0.5"))            # rung 1 x regime 0.5 (absent) x drawdown 1
        self.assertEqual(plan.gross_budget_usd, D(1000))     # min(2000 / 2, 10000 x 1)
        self.assertEqual(plan.gross_guard_usd, D(1800))      # 0.9 x ledger gross cap
        self.assertEqual([s.notional_usd for s in plan.symbols], [D(200), D(200)])
        self.assertEqual([s.price_decimals for s in plan.symbols], [2, 2])
        with self.assertRaisesRegex(mover.MoverRefusal, "invalid_evidence_class"):
            mover.build_plan(self.settings, self.limits, scan, session, trial_id="t1", evidence_class="LIVE",
                             t0=SCAN_TIME + 25, equity=D(10000))

    def test_hard_flatten_is_the_trial_end_or_the_ledger_sell_window(self):
        date = datetime(2026, 9, 24).date()
        t0 = mover.et_epoch(date, dtime(8, 0, 30))
        timing = mover.plan_timing(self.settings, self.limits, t0=t0, session_date=date)
        self.assertEqual(timing.sell_window_end, t0 + 3600 + 600)
        self.assertEqual(timing.hard_flatten_at, t0 + 4200 - 120)          # 09:08:30, before 09:25
        self.assertEqual((timing.entry_deadline, timing.x2_hold_seconds, timing.x1_at), (t0 + 30, 3600.0, None))
        late = mover.et_epoch(date, dtime(8, 30))
        self.assertEqual(mover.plan_timing(self.settings, self.limits, t0=late, session_date=date).hard_flatten_at,
                         mover.et_epoch(date, dtime(9, 25)))               # the configured trial end binds
        with self.assertRaisesRegex(mover.MoverRefusal, "mover_window_too_short"):
            mover.plan_timing(self.settings, self.limits, t0=mover.et_epoch(date, dtime(9, 24)), session_date=date)
        data = config_data()
        data["mover"].update(session_scope="any_session", exit="X1", trial_end_et="16:00", rule="14:50|G20|V1000000|any")
        _, limits, settings = load(data)
        timing = mover.plan_timing(settings, limits, t0=mover.et_epoch(date, dtime(14, 51)), session_date=date)
        self.assertEqual(timing.x1_at, mover.et_epoch(date, dtime(15, 58)))


class Pricing(unittest.TestCase):
    def test_buy_limit_is_ask_plus_cap_rounded_down_to_the_tick(self):
        self.assertEqual(mover.buy_limit_price(D("3.22"), D(50)), D("3.23"))
        self.assertEqual(mover.buy_limit_price(D("10.00"), D(50)), D("10.05"))
        self.assertEqual(mover.buy_limit_price(D("0.8160"), D(50)), D("0.8200"))
        self.assertEqual(mover.buy_limit_price(D("0.9990"), D(50)), D("1.00"))
        self.assertEqual(mover.buy_limit_price(D("0.50"), D(50), decimals=2), D("0.50"))
        self.assertIsNone(mover.buy_limit_price(D("0.5123"), D(50), decimals=2))  # 0.51 would sit below the ask

    def test_sell_limit_is_bid_less_cap_rounded_up_to_the_tick(self):
        self.assertEqual(mover.sell_limit_price(D("3.20"), D(50)), D("3.19"))
        self.assertEqual(mover.sell_limit_price(D("0.9999"), D(50)), D("0.9950"))
        self.assertEqual(mover.sell_limit_price(D("1.0049"), D(50)), D("0.9999"))
        self.assertEqual(mover.sell_limit_price(D("0.97"), D(50), decimals=2), D("0.97"))
        self.assertEqual(mover.sell_limit_price(D("100.00"), D(50)), D("99.50"))

    def test_limits_satisfy_the_ledger_price_increment_and_cap(self):
        for text in ("0.1234", "0.5", "0.9999", "1.00", "1.01", "3.21", "45.50", "199.99"):
            price = D(text)
            for limit in (mover.buy_limit_price(price, D(50)), mover.sell_limit_price(price, D(50))):
                self.assertEqual(limit, limit.quantize(D("0.01") if limit >= 1 else D("0.0001")))
            self.assertLessEqual(mover.buy_limit_price(price, D(50)), price * D("1.005"))
            self.assertGreaterEqual(mover.sell_limit_price(price, D(50)), price * D("0.995"))

    def test_extended_hours_exit_is_a_marketable_limit_the_transport_accepts(self):
        """Stops cannot rest at the broker outside 09:30-16:00; the exit is a marketable limit
        sell at bid x (1 - cap) carrying Alpaca's extended_hours flag, limit + TIF day."""
        policy = {"extended_hours": True}
        self.assertTrue(order_extended_hours_flag(PRE_TS, policy))
        self.assertTrue(order_extended_hours_flag(POST_TS, policy))
        self.assertFalse(order_extended_hours_flag(RTH_TS, policy))
        self.assertFalse(order_extended_hours_flag(PRE_TS, {"extended_hours": False}))
        limit = mover.sell_limit_price(D("3.20"), D(50))
        payload = {"client_order_id": "mvr-t1-0000002", "symbol": "ABCD", "side": "sell", "qty": "61",
                   "limit_price": mover.price_text(limit), "type": "limit", "time_in_force": "day",
                   "extended_hours": order_extended_hours_flag(PRE_TS, policy), "reason": "x2_time"}
        accepted = normalize_intent(payload, ("ABCD", "SPY"), allow_extended_hours=True)
        self.assertEqual((accepted["limit_price"], accepted["extended_hours"]), ("3.19", True))
        with self.assertRaises(TransportError):
            normalize_intent(payload, ("ABCD", "SPY"), allow_extended_hours=False)
        with self.assertRaises(TransportError):
            normalize_intent(dict(payload, type="market"), ("ABCD", "SPY"), allow_extended_hours=True)


class ExitRules(unittest.TestCase):
    def timing(self, x1_at=None):
        return mover.Timing(1000.0, 1030.0, 60.0, 10.0, 99999.0, 99999.0, x1_at, 3600.0)

    def reason(self, rule, **kw):
        base = dict(now=5000.0, bid=D(10), entry_price=D(10), running_high=D(10), first_fill_at=1000.0,
                    timing=self.timing(4000.0))
        base.update(kw)
        return mover.rule_exit_reason(rule, **base)

    def test_x1_flattens_at_the_close_time(self):
        self.assertIsNone(self.reason("X1", now=3999.9))
        self.assertEqual(self.reason("X1", now=4000.0), "x1_close")

    def test_x2_sells_sixty_minutes_after_the_first_fill(self):
        self.assertIsNone(self.reason("X2", now=4599.9))
        self.assertEqual(self.reason("X2", now=4600.0), "x2_time")
        self.assertIsNone(self.reason("X2", first_fill_at=None))

    def test_x3_trails_at_085_of_the_running_high(self):
        self.assertIsNone(self.reason("X3", bid=D("8.51"), running_high=D(10)))
        self.assertEqual(self.reason("X3", bid=D("8.50"), running_high=D(10)), "x3_trail")

    def test_x4_brackets_at_085_and_150_of_entry(self):
        self.assertEqual(self.reason("X4", bid=D("8.50")), "x4_stop")
        self.assertIsNone(self.reason("X4", bid=D("8.51")))
        self.assertIsNone(self.reason("X4", bid=D("14.99")))
        self.assertEqual(self.reason("X4", bid=D("15.00")), "x4_target")


class BookHarness:
    """A MoverBook over mutable fake positions and quotes, with the example config's caps."""

    def __init__(self, test, *, exit_rule="X2", symbols=None, timing=None, regime=None):
        data = config_data()
        data["mover"]["exit"] = exit_rule
        if exit_rule == "X1":
            data["mover"].update(session_scope="any_session", trial_end_et="16:00")
        _, self.limits, self.settings = load(data)
        raw = scan_bytes(symbols=symbols or scan_dict()["symbols"], **({"regime": regime} if regime else {}))
        self.scan = mover.load_scan(raw, self.settings, now=SCAN_TIME + 20)
        self.t0 = SCAN_TIME + 25
        self.timing = timing or mover.Timing(self.t0, self.t0 + 30, 60.0, 10.0, self.t0 + 4000, self.t0 + 4200,
                                             self.t0 + 2000 if exit_rule == "X1" else None, 3600.0)
        session = mover.plan_session(None, equity=D(10000), rung_schedule=self.settings.rung_schedule)
        self.plan = mover.build_plan(self.settings, self.limits, self.scan, session, trial_id="t1",
                                     evidence_class="SYN", t0=self.t0, equity=D(10000), timing=self.timing)
        self.positions, self.quotes, self.events = {}, {}, []
        self.book = mover.MoverBook(self.plan, positions=lambda: dict(self.positions), quote=self.quotes.get,
                                    limits=self.limits, trial_id="t1", event_sink=self.events.append)

    def quote(self, symbol, bid, ask, at, halted=False):
        self.quotes[symbol] = Quote(symbol, str(bid), str(ask), at, halted=halted)

    def hold(self, symbol, qty, cost):
        self.positions[symbol] = Position(symbol, D(qty), D(qty) * D(cost))

    def fill(self, record, qty, price, at):
        self.book.on_fill(record.client_id, at, D(qty), D(price))
        held = self.positions.get(record.symbol)
        qty, price = D(qty), D(price)
        if record.side == "buy":
            base = held or Position(record.symbol, D(0), D(0))
            self.positions[record.symbol] = Position(record.symbol, base.qty + qty, base.cost_basis_usd + qty * price)
        else:
            remaining = held.qty - qty
            if remaining:
                self.positions[record.symbol] = Position(record.symbol, remaining, held.average_cost * remaining)
            else:
                del self.positions[record.symbol]

    def evaluate(self, now, enabled=True, symbols=None):
        return self.book.evaluate(now, entries_enabled=enabled, symbols=symbols)


def submits(actions, side=None):
    return [a.record for a in actions if a.kind == "submit" and (side is None or a.record.side == side)]


def cancels(actions):
    return [a.client_id for a in actions if a.kind == "cancel"]


class BookStateMachine(unittest.TestCase):
    def test_one_marketable_limit_buy_per_symbol_never_resent(self):
        h = BookHarness(self)
        now = h.t0 + 1
        h.quote("ABCD", "3.21", "3.22", now)
        h.quote("WXYZ", "45.40", "45.50", now)
        buys = submits(h.evaluate(now), "buy")
        self.assertEqual([(b.symbol, b.qty, b.limit_price) for b in buys],
                         [("ABCD", D(61), D("3.23")), ("WXYZ", D(4), D("45.72"))])
        self.assertEqual(buys[0].client_id, "mvr-t1-0000001")
        self.assertEqual(h.book.legs["ABCD"].entry_qty_binding, "notional")
        self.assertEqual(submits(h.evaluate(now + 1)), [])          # entry open: no second buy
        h.book.on_terminal(buys[0].client_id, "rejected", "quote_spread_exceeds_cap")
        self.assertEqual(h.book.legs["ABCD"].state, "no_fill")
        self.assertEqual(submits(h.evaluate(now + 2), "buy"), [])   # a refusal is never re-sent

    def test_stale_wide_or_halted_quotes_block_entries_until_the_window_ends(self):
        h = BookHarness(self, symbols=scan_dict()["symbols"][:1])
        now = h.t0 + 1
        h.quote("ABCD", "3.21", "3.22", now - 3.5)                   # older than the 3 s quote age
        self.assertEqual(submits(h.evaluate(now)), [])
        self.assertEqual(h.book.legs["ABCD"].wait_reason, "no_fresh_quote")
        h.quote("ABCD", "3.00", "3.22", now)                         # 707 bps spread > 100 bps cap
        self.assertEqual(submits(h.evaluate(now)), [])
        self.assertEqual(h.book.legs["ABCD"].wait_reason, "spread_exceeds_cap")
        h.quote("ABCD", "3.21", "3.22", now, halted=True)
        self.assertEqual(submits(h.evaluate(now)), [])
        self.assertEqual(h.book.legs["ABCD"].wait_reason, "quote_halted")
        self.assertEqual(submits(h.evaluate(now, enabled=False)), [])
        self.assertEqual(h.book.legs["ABCD"].wait_reason, "entries_not_enabled")
        h.quote("ABCD", "3.21", "3.22", h.timing.entry_deadline)
        self.assertEqual(submits(h.evaluate(h.timing.entry_deadline)), [])
        self.assertEqual((h.book.legs["ABCD"].state, h.book.legs["ABCD"].skip_reason),
                         ("skipped", "entries_not_enabled"))
        self.assertTrue(h.book.complete())

    def test_entry_timeout_cancels_the_unfilled_remainder_and_never_chases(self):
        h = BookHarness(self, symbols=scan_dict()["symbols"][:1])
        now = h.t0 + 1
        h.quote("ABCD", "3.21", "3.22", now)
        buy = submits(h.evaluate(now), "buy")[0]
        h.fill(buy, 30, "3.22", now + 0.5)
        h.quote("ABCD", "3.25", "3.26", now + 59)
        self.assertEqual(cancels(h.evaluate(now + 59)), [])
        h.quote("ABCD", "3.25", "3.26", now + 60)
        self.assertEqual(cancels(h.evaluate(now + 60)), [buy.client_id])
        self.assertEqual(buy.cancel_reason, "entry_timeout")
        self.assertEqual(submits(h.evaluate(now + 60.5)), [])      # nothing while the cancel is pending
        h.book.on_terminal(buy.client_id, "canceled")
        self.assertEqual(h.book.legs["ABCD"].state, "holding")
        self.assertEqual(submits(h.evaluate(now + 61), "buy"), [])
        h.quote("ABCD", "3.30", "3.31", now + 0.5 + 3600)
        sell = submits(h.evaluate(now + 0.5 + 3600), "sell")[0]    # X2 from the first fill
        self.assertEqual((sell.qty, sell.reason, sell.limit_price), (D(30), "x2_time", D("3.29")))

    def test_x3_trail_uses_the_running_high_since_entry(self):
        h = BookHarness(self, exit_rule="X3", symbols=scan_dict()["symbols"][:1])
        now = h.t0 + 1
        h.quote("ABCD", "3.21", "3.22", now)
        buy = submits(h.evaluate(now), "buy")[0]
        h.fill(buy, 61, "3.22", now + 0.2)
        for i, bid in enumerate(("3.50", "4.00", "3.60", "3.41")):
            h.quote("ABCD", bid, str(D(bid) + D("0.01")), now + 1 + i)
            self.assertEqual(submits(h.evaluate(now + 1 + i), "sell"), [])
        h.quote("ABCD", "3.40", "3.41", now + 6)                    # 3.40 = 0.85 x 4.00
        sell = submits(h.evaluate(now + 6), "sell")[0]
        self.assertEqual((sell.reason, h.book.legs["ABCD"].running_high), ("x3_trail", D("4.00")))

    def test_x4_bracket_stop_and_target(self):
        rows = scan_dict()["symbols"]
        h = BookHarness(self, exit_rule="X4", symbols=rows)
        now = h.t0 + 1
        h.quote("ABCD", "3.21", "3.22", now)
        h.quote("WXYZ", "45.40", "45.50", now)
        a, w = submits(h.evaluate(now), "buy")
        h.fill(a, a.qty, "3.22", now + 0.1)
        h.fill(w, w.qty, "45.50", now + 0.1)
        h.quote("ABCD", "4.83", "4.84", now + 2)                    # 4.83 >= 1.50 x 3.22
        h.quote("WXYZ", "38.67", "38.70", now + 2)                  # 38.67 <= 0.85 x 45.50
        sells = {s.symbol: s.reason for s in submits(h.evaluate(now + 2), "sell")}
        self.assertEqual(sells, {"ABCD": "x4_target", "WXYZ": "x4_stop"})

    def test_exit_reprices_after_its_timeout_and_chunks_to_the_per_order_cap(self):
        h = BookHarness(self, symbols=scan_dict()["symbols"][:1])
        now = h.t0 + 1
        h.quote("ABCD", "3.21", "3.22", now)
        buy = submits(h.evaluate(now), "buy")[0]
        h.fill(buy, 61, "3.22", now)
        at = now + 3600
        h.quote("ABCD", "6.40", "6.41", at)                         # the position doubled: 61 x 6.37 > 200
        first = submits(h.evaluate(at), "sell")[0]
        self.assertEqual((first.qty, first.limit_price), (D(31), D("6.37")))   # floor(200 / 6.37) = 31
        h.quote("ABCD", "6.30", "6.31", at + 10)
        self.assertEqual(cancels(h.evaluate(at + 10)), [first.client_id])
        self.assertEqual(first.cancel_reason, "exit_reprice")
        h.book.on_terminal(first.client_id, "canceled")
        second = submits(h.evaluate(at + 10.1), "sell")[0]
        self.assertEqual((second.qty, second.limit_price, second.reason), (D(31), D("6.27"), "x2_time"))
        h.fill(second, 31, "6.30", at + 10.2)
        third = submits(h.evaluate(at + 10.3), "sell")[0]
        self.assertEqual(third.qty, D(30))
        h.fill(third, 30, "6.30", at + 10.4)
        h.evaluate(at + 10.5)
        self.assertEqual(h.book.legs["ABCD"].state, "closed")
        self.assertTrue(h.book.complete())

    def test_never_sends_a_sell_while_the_symbols_buy_is_open(self):
        h = BookHarness(self, exit_rule="X4", symbols=scan_dict()["symbols"][:1])
        now = h.t0 + 1
        h.quote("ABCD", "3.21", "3.22", now)
        buy = submits(h.evaluate(now), "buy")[0]
        h.fill(buy, 20, "3.22", now + 0.1)
        h.quote("ABCD", "2.70", "2.72", now + 1)                    # X4 stop while the entry still rests
        actions = h.evaluate(now + 1)
        self.assertEqual((cancels(actions), submits(actions)), ([buy.client_id], []))
        self.assertEqual(buy.cancel_reason, "exit_triggered")
        self.assertEqual(submits(h.evaluate(now + 1.1)), [])
        h.book.on_terminal(buy.client_id, "canceled")
        sell = submits(h.evaluate(now + 1.2), "sell")[0]
        self.assertEqual((sell.qty, sell.reason), (D(20), "x4_stop"))

    def test_kill_switch_cancels_entries_and_flattens(self):
        h = BookHarness(self)
        now = h.t0 + 1
        h.quote("ABCD", "3.21", "3.22", now)
        buy = submits(h.evaluate(now, symbols=("ABCD",)), "buy")[0]
        h.fill(buy, 10, "3.22", now + 0.1)
        h.book.set_force("kill_switch", now + 1)
        h.quote("ABCD", "3.30", "3.31", now + 1)
        h.quote("WXYZ", "45.40", "45.50", now + 1)
        actions = h.evaluate(now + 1)
        self.assertEqual(cancels(actions), [buy.client_id])
        self.assertEqual(buy.cancel_reason, "force:kill_switch")
        self.assertEqual(submits(actions, "buy"), [])
        self.assertEqual(h.book.legs["WXYZ"].skip_reason, "force:kill_switch")
        h.book.on_terminal(buy.client_id, "canceled")
        sell = submits(h.evaluate(now + 1.1), "sell")[0]
        self.assertEqual((sell.qty, sell.reason), (D(10), "kill_switch"))
        self.assertEqual(h.book.force_reason, "kill_switch")

    def test_hard_flatten_at_the_configured_trial_end(self):
        t0 = SCAN_TIME + 25
        h = BookHarness(self, symbols=scan_dict()["symbols"][:1],
                        timing=mover.Timing(t0, t0 + 30, 60.0, 10.0, t0 + 100, t0 + 4200, None, 3600.0))
        now = h.t0 + 1
        h.quote("ABCD", "3.21", "3.22", now)
        buy = submits(h.evaluate(now), "buy")[0]
        h.fill(buy, 61, "3.22", now)
        h.quote("ABCD", "3.30", "3.31", h.timing.hard_flatten_at - 0.1)
        self.assertEqual(submits(h.evaluate(h.timing.hard_flatten_at - 0.1)), [])
        h.quote("ABCD", "3.30", "3.31", h.timing.hard_flatten_at)
        sell = submits(h.evaluate(h.timing.hard_flatten_at), "sell")[0]
        # 61 x 3.29 would exceed the 200 USD per-order cap the ledger applies to sells too.
        self.assertEqual((sell.reason, sell.qty, sell.limit_price), ("hard_flatten", D(60), D("3.29")))
        self.assertEqual(h.book.force_reason, "hard_flatten")
        h.fill(sell, 60, "3.30", h.timing.hard_flatten_at + 0.1)
        rest = submits(h.evaluate(h.timing.hard_flatten_at + 0.2), "sell")[0]
        self.assertEqual((rest.reason, rest.qty), ("hard_flatten", D(1)))

    def test_gross_guard_exits_the_largest_position_before_the_ledger_cap(self):
        h = BookHarness(self)
        now = h.t0 + 1
        h.hold("ABCD", 100, "3.00")
        h.hold("WXYZ", 4, "45.00")
        h.book.legs["ABCD"].state = h.book.legs["WXYZ"].state = "holding"
        h.book.legs["ABCD"].first_fill_at = h.book.legs["WXYZ"].first_fill_at = now
        h.quote("ABCD", "13.00", "13.01", now)                      # 1301 + 180 = 1481 < 1800 guard
        h.quote("WXYZ", "45.00", "45.01", now)
        self.assertEqual(submits(h.evaluate(now)), [])
        h.quote("ABCD", "16.20", "16.21", now + 1)                  # 1621 + 180 = 1801 >= 1800
        sells = submits(h.evaluate(now + 1), "sell")
        self.assertEqual([(s.symbol, s.reason) for s in sells], [("ABCD", "gross_cap_guard")])

    def test_client_ids_continue_after_the_ledgers_existing_ids(self):
        h = BookHarness(self)
        book = mover.MoverBook(h.plan, positions=dict, quote=h.quotes.get, limits=h.limits, trial_id="t1",
                               existing_client_ids=["mvr-t1-0000007", "rec-t1-0000009", "mvr-t0-0000099"])
        now = h.t0 + 1
        h.quote("ABCD", "3.21", "3.22", now)
        self.assertEqual(submits(book.evaluate(now, entries_enabled=True, symbols=("ABCD",)))[0].client_id,
                         "mvr-t1-0000008")


class ForeignOrdersOnASharedAccount(unittest.TestCase):
    """The account's order history can hold another lane's finished orders; only those
    are tolerated. A foreign open order still freezes, and a foreign fill still shows
    up as a cash or position mismatch."""

    def setUp(self):
        _, self.limits, _ = mover.load_mover_config(CONFIG)
        self.root = tempfile.TemporaryDirectory()
        self.ledger = Ledger(Path(self.root.name) / "ledger.sqlite3", self.limits)
        self.now = SCAN_TIME + 30
        self.ledger.begin_next_trial(self.now, "t1")
        self.controller = mover_runner.MoverController(self.ledger, self.now + 36000, market_open=True,
                                                       clock=lambda: self.now)

    def tearDown(self):
        self.ledger.close()
        self.root.cleanup()

    def order(self, cid, status, filled="0"):
        return {"client_order_id": cid, "id": "b-" + cid, "symbol": "ABCD", "side": "buy", "qty": "5",
                "limit_price": "3.23", "status": status, "filled_qty": filled,
                "filled_avg_price": "3.22" if filled != "0" else None, "updated_at_ns": int(self.now * 1e9)}

    def test_foreign_terminal_orders_are_ignored_and_open_ones_still_freeze(self):
        self.controller.observe(self.order("adp-other-0000001", "filled", "5"))
        self.controller.observe(self.order("adp-other-0000002", "canceled"))
        self.assertEqual((self.controller.foreign_terminal_orders, self.ledger.halted_reason()), (2, None))
        with self.assertRaisesRegex(SafetyError, "external_order_detected"):
            self.controller.observe(self.order("adp-other-0000003", "new"))
        self.assertEqual(self.ledger.halted_reason(), "external_order_detected")

    def test_reconcile_drops_foreign_terminal_orders_but_not_their_effects(self):
        snapshot = {"complete": True, "positions": [], "account": {"cash": "100000"},
                    "orders": [self.order("adp-other-0000001", "filled", "5"), self.order("rec-other-0000001", "canceled")]}
        proof = mover_runner.mover_reconcile(self.ledger, snapshot, "100000")
        self.assertEqual((proof["positions"], proof["open_orders"], proof["cash_match"]), (0, 0, True))
        with self.assertRaisesRegex(SafetyError, "external_order_detected"):
            mover_runner.mover_reconcile(self.ledger, dict(snapshot, orders=[self.order("adp-other-0000009", "new")]),
                                         "100000")
        with self.assertRaisesRegex(SafetyError, "cash_mismatch"):
            mover_runner.mover_reconcile(self.ledger, dict(snapshot, account={"cash": "99983.90"}), "100000")
        with self.assertRaisesRegex(SafetyError, "position_mismatch"):
            mover_runner.mover_reconcile(self.ledger, dict(snapshot, positions=[{"symbol": "ABCD", "qty": "5"}]),
                                         "100000")


class ReceiptAndCommands(unittest.TestCase):
    def test_receipt_carries_orders_pnl_and_reconciliation_without_account_data(self):
        h = BookHarness(self, symbols=scan_dict()["symbols"][:1])
        broker_ids = [str(uuid.uuid4()), str(uuid.uuid4())]  # Alpaca-shaped ids, generated so none is committed
        with tempfile.TemporaryDirectory() as root:
            ledger = Ledger(Path(root) / "ledger.sqlite3", h.limits)
            try:
                now = h.t0
                ledger.begin_next_trial(now, "t1")
                before = ledger.accounting()
                quote = Quote("ABCD", "3.21", "3.22", now)
                ledger.reserve_intent("mvr-t1-0000001", "ABCD", "buy", "61", "3.23", quote=quote, now=now,
                                      market_open=True, session_close=now + 36000)
                ledger.record_order("mvr-t1-0000001", broker_ids[0], "filled", "61", "3.22", timestamp=now)
                exit_quote = Quote("ABCD", "3.26", "3.27", now + 1)
                ledger.reserve_intent("mvr-t1-0000002", "ABCD", "sell", "61", "3.25", quote=exit_quote, now=now + 1,
                                      market_open=True, session_close=now + 36000)
                ledger.record_order("mvr-t1-0000002", broker_ids[1], "filled", "61", "3.26", timestamp=now + 1)
                outcome = {"status": "passed", "flat": True, "native_fill_events": 2, "legs": h.book.leg_receipts(),
                           "reconciliation": {"positions_match": True, "cash_match": True,
                                              "cash_delta_usd": "2.44", "open_orders": 0, "positions": 0}}
                receipt = mover_runner.build_receipt(plan=h.plan, outcome=outcome, config_sha256="c" * 64,
                                                     scan=h.scan, ledger=ledger, ledger_before=before,
                                                     prefixes=("mvr-t1-", "rec-t1-"))
            finally:
                ledger.close()
        self.assertEqual(receipt["evidence_class"], "SYN")
        self.assertEqual(receipt["symbols"][0]["realized_pnl_usd"], "2.4400")   # 61 x (3.26 - 3.22)
        self.assertEqual(receipt["totals"]["realized_pnl_usd"], "2.4400")
        self.assertTrue(receipt["totals"]["pnl_consistent"])
        self.assertEqual(receipt["scan_sha256"], h.scan.sha256)
        self.assertEqual(receipt["reconciliation"]["end"]["cash_match"], True)
        body = json.dumps(receipt)
        self.assertIsNone(UUID.search(body))
        for forbidden in ("account_identity", "baseline_cash", '"cash":', '"equity":', "buying_power",
                          "APCA_", "secret"):
            self.assertNotIn(forbidden, body)
        self.assertEqual(mover.broker_ref(broker_ids[0]), hashlib.sha256(broker_ids[0].encode()).hexdigest()[:16])
        for broker_id in broker_ids:
            self.assertNotIn(broker_id, body)

    def run_main(self, root, scan_raw, *extra):
        scan_path, out = Path(root) / "scan.json", Path(root) / "out.json"
        scan_path.write_bytes(scan_raw)
        with patch.object(mover_runner, "credentials", side_effect=AssertionError("credentials read")):
            code = mover_runner.main(["paper", "--env-file", str(Path(root) / "absent.env"), "--config", str(CONFIG),
                                      "--scan", str(scan_path), "--output", str(out), "--trial", "t1",
                                      "--state-root", str(Path(root) / "state"), *extra])
        return code, json.loads(out.read_text())

    def test_paper_refuses_a_stale_or_empty_scan_before_any_credential_or_broker_access(self):
        with tempfile.TemporaryDirectory() as root:
            stale = scan_bytes(scan_time="2026-09-22T12:00:05Z")
            code, result = self.run_main(root, stale)
            self.assertEqual((code, result["status"], result["reason"], result["orders_submitted"]),
                             (2, "not_started", "scan_stale", 0))
            self.assertEqual(result["scan_sha256"], hashlib.sha256(stale).hexdigest())
            with patch.object(mover_runner.time, "time", return_value=SCAN_TIME + 20):
                code, result = self.run_main(root, scan_bytes(symbols=[]))
            self.assertEqual((code, result["reason"]), (2, "scan_empty"))
            with patch.object(mover_runner.time, "time", return_value=SCAN_TIME - 5):
                code, result = self.run_main(root, scan_bytes())
            self.assertEqual((code, result["reason"]), (2, "scan_from_future"))
            self.assertFalse((Path(root) / "state").exists())

    def test_a_failing_read_only_preflight_is_not_started_with_its_error_type_only(self):
        import transport
        with tempfile.TemporaryDirectory() as root:
            scan_path, out = Path(root) / "scan.json", Path(root) / "out.json"
            scan_path.write_bytes(scan_bytes())
            with patch.object(mover_runner.time, "time", return_value=SCAN_TIME + 20), \
                 patch.object(mover_runner, "credentials", return_value=("key", "secret")), \
                 patch.object(transport, "preflight", side_effect=RuntimeError("provider text never kept")), \
                 patch("builtins.print"):
                code = mover_runner.main(["paper", "--env-file", str(Path(root) / "unused.env"), "--scan",
                                          str(scan_path), "--output", str(out), "--trial", "t1",
                                          "--state-root", str(Path(root) / "state")])
            result = json.loads(out.read_text())
        self.assertEqual((code, result["stage"], result["reason"]), (2, "preflight", "preflight_error:RuntimeError"))
        self.assertNotIn("provider text", json.dumps(result))

    def test_check_prints_the_entry_plan_without_broker_access(self):
        with tempfile.TemporaryDirectory() as root:
            scan_path, out = Path(root) / "scan.json", Path(root) / "plan.json"
            scan_path.write_bytes(scan_bytes())
            with patch("builtins.print"):
                code = mover_runner.main(["check", "--scan", str(scan_path), "--output", str(out), "--assume-fresh"])
            result = json.loads(out.read_text())
        self.assertEqual((code, result["status"], result["freshness_checked"]), (0, "valid", False))
        self.assertEqual([(s["symbol"], s["intended_notional_usd"], s["binding"]) for s in result["symbols"]],
                         [("ABCD", "200.00", "per_order"), ("WXYZ", "200.00", "per_order")])
        self.assertEqual(result["sizing"]["gross_budget_usd"], "1000.00")


if __name__ == "__main__":
    unittest.main()
