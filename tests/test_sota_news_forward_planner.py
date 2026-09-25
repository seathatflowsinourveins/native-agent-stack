"""SYN: news-forward planner rules (sessions, screening, basket, filters, caps, exits).

Synthetic inputs only: no network, no credentials, no clock. The XNYS calendar is the
repository's session-calendar.json (DST and holidays come from it).
"""

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/us-equities/sota-mover/news-forward"
sys.path.insert(0, str(BLUEPRINT))

import common  # noqa: E402
import planner  # noqa: E402

NY = ZoneInfo("America/New_York")
UTC = timezone.utc
CAL = common.load_calendar()
sig = planner.sig


def ny(y, m, d, hh, mm=0, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=NY).astimezone(UTC)


def z(dt):
    return common.iso(dt)


class SessionWindows(unittest.TestCase):
    def test_edt_schedule(self):
        s = planner.day_schedule(CAL, date(2026, 9, 25))
        self.assertEqual(s.open_utc, datetime(2026, 9, 25, 13, 30, tzinfo=UTC))
        self.assertEqual(s.basket_at, datetime(2026, 9, 25, 13, 15, tzinfo=UTC))
        self.assertEqual(s.opg_submit_by, datetime(2026, 9, 25, 13, 27, tzinfo=UTC))
        self.assertEqual(s.opg_broker_cutoff, datetime(2026, 9, 25, 13, 28, tzinfo=UTC))
        self.assertEqual(s.cls_start, datetime(2026, 9, 25, 19, 40, tzinfo=UTC))
        self.assertEqual(s.cls_end, datetime(2026, 9, 25, 19, 45, tzinfo=UTC))
        self.assertEqual(s.market_flatten_at, datetime(2026, 9, 25, 19, 55, tzinfo=UTC))
        self.assertEqual(s.ext_end, ny(2026, 9, 25, 20))
        self.assertEqual(s.service_end, ny(2026, 9, 25, 20, 5))
        self.assertEqual(s.premarket_start, ny(2026, 9, 25, 4))

    def test_est_schedule_after_dst_ends(self):
        s = planner.day_schedule(CAL, date(2026, 11, 2))
        self.assertEqual(s.open_utc, datetime(2026, 11, 2, 14, 30, tzinfo=UTC))
        self.assertEqual(s.basket_at, datetime(2026, 11, 2, 14, 15, tzinfo=UTC))
        self.assertEqual(s.premarket_start, datetime(2026, 11, 2, 9, 0, tzinfo=UTC))

    def test_early_close_shifts_close_steps(self):
        s = planner.day_schedule(CAL, date(2026, 11, 27))
        self.assertTrue(s.early_close)
        self.assertEqual(s.close_utc, ny(2026, 11, 27, 13))
        self.assertEqual(s.cls_start, ny(2026, 11, 27, 12, 40))
        self.assertEqual(s.market_flatten_at, ny(2026, 11, 27, 12, 55))
        self.assertEqual(s.ext_end, ny(2026, 11, 27, 17))

    def test_holiday_is_not_a_session_and_maps_to_next_open(self):
        self.assertFalse(planner.is_session(CAL, date(2026, 11, 26)))
        w = CAL.classify(ny(2026, 11, 26, 11))
        self.assertEqual(planner.session_label(w), planner.OPEN_AUCTION)
        self.assertEqual(w.session, date(2026, 11, 27))
        self.assertEqual(planner.extended_segment(CAL, ny(2026, 11, 26, 5)), planner.CLOSED)

    def test_weekend_across_dst_change(self):
        w = CAL.classify(ny(2026, 10, 31, 12))
        self.assertEqual(w.session, date(2026, 11, 2))
        self.assertEqual(w.entry_utc, datetime(2026, 11, 2, 14, 30, tzinfo=UTC))

    def test_labels_by_time_of_day(self):
        cases = [
            (ny(2026, 9, 24, 17), planner.OPEN_AUCTION, date(2026, 9, 25), planner.EXT_POST),
            (ny(2026, 9, 25, 5), planner.OPEN_AUCTION, date(2026, 9, 25), planner.EXT_PRE),
            (ny(2026, 9, 25, 9, 10), sig.EXCLUDED_PREMARKET, date(2026, 9, 25), planner.EXT_PRE),
            (ny(2026, 9, 25, 10), planner.RTH, date(2026, 9, 25), planner.CLOSED),
            (ny(2026, 9, 25, 15, 45), sig.EXCLUDED_LATE, date(2026, 9, 25), planner.CLOSED),
            (ny(2026, 9, 25, 21), planner.OPEN_AUCTION, date(2026, 9, 28), planner.CLOSED),
        ]
        for t, label, session, ext in cases:
            w = CAL.classify(t)
            self.assertEqual(planner.session_label(w), label, t)
            self.assertEqual(w.session, session, t)
            self.assertEqual(planner.extended_segment(CAL, t), ext, t)

    def test_rth_entry_is_release_plus_15(self):
        w = CAL.classify(ny(2026, 9, 25, 10, 0, 20))
        self.assertEqual(w.entry_utc, ny(2026, 9, 25, 10, 15, 20))

    def test_opg_and_cls_cutoffs(self):
        s = planner.day_schedule(CAL, date(2026, 9, 25))
        self.assertFalse(planner.opg_submission_allowed(s, ny(2026, 9, 25, 9, 14, 59)))
        self.assertTrue(planner.opg_submission_allowed(s, ny(2026, 9, 25, 9, 15)))
        self.assertTrue(planner.opg_submission_allowed(s, ny(2026, 9, 25, 9, 27)))
        self.assertFalse(planner.opg_submission_allowed(s, ny(2026, 9, 25, 9, 27, 1)))
        self.assertFalse(planner.cls_submission_allowed(s, ny(2026, 9, 25, 15, 39, 59)))
        self.assertTrue(planner.cls_submission_allowed(s, ny(2026, 9, 25, 15, 40)))
        self.assertTrue(planner.cls_submission_allowed(s, ny(2026, 9, 25, 15, 45)))
        self.assertFalse(planner.cls_submission_allowed(s, ny(2026, 9, 25, 15, 45, 1)))


ASSETS = {
    "ACME": {"symbol": "ACME", "name": "Acme Corp. Common Stock", "exchange": "NYSE"},
    "BETA": {"symbol": "BETA", "name": "Beta Inc. Common Stock", "exchange": "NASDAQ"},
    "FUND": {"symbol": "FUND", "name": "Some Index ETF", "exchange": "ARCA"},
}


def article(aid, created, symbols=("ACME",), headline="Acme wins large contract", source="benzinga", updated=None):
    return {"id": aid, "created_at": z(created), "updated_at": z(updated or created), "symbols": list(symbols),
            "headline": headline, "source": source}


class Screening(unittest.TestCase):
    def setUp(self):
        self.s = planner.Screener(CAL, ASSETS)

    def test_pass_and_labels(self):
        cand, reason = self.s.screen(article(100, ny(2026, 9, 24, 18)))
        self.assertEqual(reason, "ok")
        self.assertEqual(cand["session_label"], planner.OPEN_AUCTION)
        self.assertEqual(cand["session"], "2026-09-25")
        self.assertEqual(cand["company"], "Acme Corp.")
        self.assertEqual(cand["checkpoint_year"], 2024)
        self.assertEqual(cand["event_id"], "100:ACME")

    def test_guards(self):
        t = ny(2026, 9, 24, 18)
        self.assertEqual(self.s.screen(article(1, t, symbols=("ACME", "BETA")))[1], "drop_symbol_count_not_1")
        self.assertEqual(self.s.screen(article(2, t, source="globenewswire"))[1], "drop_source_not_benzinga")
        self.assertEqual(self.s.screen(article(3, t, symbols=("FUND",)))[1], "drop_not_primary_operating_company")
        self.assertEqual(self.s.screen(article(4, t, symbols=("ZZZZ",)))[1], "drop_symbol_not_in_asset_master")
        self.assertEqual(self.s.screen(article(5, t, headline="Acme shares are trading higher"))[1], "drop_movement_headline")
        self.assertEqual(self.s.screen(article(6, ny(2026, 9, 25, 9, 5)))[1], "drop_window_excluded_0900_0930")
        late = article(7, t, updated=ny(2026, 9, 25, 9, 1))
        self.assertEqual(self.s.screen(late)[1], "drop_guard_updated_after_cutoff")

    def test_novelty_24h(self):
        self.assertEqual(self.s.screen(article(10, ny(2026, 9, 24, 18), headline="Acme signs deal"))[1], "ok")
        self.assertEqual(self.s.screen(article(11, ny(2026, 9, 24, 19), headline="ACME signs deal!"))[1], "drop_duplicate_24h")

    def test_id_order_guard(self):
        for i in range(5):
            self.s.screen(article(200 + i, ny(2026, 9, 25, 6, i), symbols=("BETA", "ACME")))
        backdated = article(206, ny(2026, 9, 25, 4, 30), headline="Acme names new CFO")
        self.assertEqual(self.s.screen(backdated)[1], "drop_guard_id_order")


def bars(days, close=100.0, volume=1_000_000, low=None):
    return [{"t": z(datetime(d.year, d.month, d.day, tzinfo=NY)), "c": close, "v": volume, "l": low if low else close * 0.99}
            for d in days]


class LanesAndShortFilters(unittest.TestCase):
    def test_lane_from_prior_20_sessions(self):
        prior = CAL.prior_sessions(date(2026, 9, 25), 20)
        lane, close, med, complete = planner.lane_from_bars(CAL, date(2026, 9, 25), bars(prior, 50.0, 1_000_000))
        self.assertEqual((lane, close, med, complete), (sig.LIQUID, 50.0, 50_000_000.0, True))
        lane = planner.lane_from_bars(CAL, date(2026, 9, 25), bars(prior, 4.0, 1_000_000))[0]
        self.assertEqual(lane, sig.SMALL)
        lane = planner.lane_from_bars(CAL, date(2026, 9, 25), bars(prior[1:], 50.0, 1_000_000))[0]
        self.assertIsNone(lane)  # one session missing: incomplete

    def test_ssr(self):
        d = date(2026, 9, 25)
        d2, d1 = CAL.prior_sessions(d, 2)
        normal = bars([d2], 100.0) + bars([d1], 95.0, low=91.0)
        self.assertFalse(planner.ssr_active(CAL, d, normal))
        triggered = bars([d2], 100.0) + bars([d1], 95.0, low=90.0)
        self.assertTrue(planner.ssr_active(CAL, d, triggered))
        self.assertTrue(planner.ssr_active(CAL, d, bars([d1], 95.0)))  # missing data: restricted
        self.assertTrue(planner.ssr_active(CAL, d, normal, today_low=85.5))
        self.assertFalse(planner.ssr_active(CAL, d, normal, today_low=85.6))

    def test_short_allowed(self):
        ok = {"shortable": True, "easy_to_borrow": True}
        self.assertEqual(planner.short_allowed(ok, False), (True, "ok"))
        self.assertEqual(planner.short_allowed({**ok, "shortable": False}, False)[1], "not_shortable")
        self.assertEqual(planner.short_allowed({**ok, "easy_to_borrow": False}, False)[1], "not_easy_to_borrow")
        self.assertEqual(planner.short_allowed(ok, True)[1], "ssr_rule_201")
        self.assertEqual(planner.short_allowed(None, False)[1], "not_shortable")


ASSET_OK = {"tradable": True, "shortable": True, "easy_to_borrow": True}
E = Decimal("900000")
BIG = planner.Limits.for_arm(planner.CORE, E, 1)


def ev(i, symbol, label, lane=sig.LIQUID, price=100, asset=None, ssr=False, minute=0, target="20000"):
    return {"event_id": f"{i}:{symbol}", "news_id": str(i), "symbol": symbol, "label": label, "lane": lane,
            "created_at": z(ny(2026, 9, 24, 17, minute)), "ref_price": Decimal(str(price)),
            "asset": ASSET_OK if asset is None else asset, "ssr": ssr,
            "target_notional": None if target is None else Decimal(target)}


class Sizing(unittest.TestCase):
    def test_formula_and_caps(self):
        # risk term binds: 0.0015 * 900k / 0.03 = 45,000 = the 5% E cap; MDV term 0.5% * 20M = 100k
        self.assertEqual(planner.risk_notional(E, 0.03, 20_000_000), Decimal("45000.00"))
        # risk term below the others: 0.0015 * 900k / 0.05 = 27,000
        self.assertEqual(planner.risk_notional(E, 0.05, 20_000_000), Decimal("27000.00"))
        # liquidity term binds: 0.5% * 4M = 20,000
        self.assertEqual(planner.risk_notional(E, 0.02, 4_000_000), Decimal("20000.00"))
        # 5% E binds for a very quiet name
        self.assertEqual(planner.risk_notional(E, 0.001, 1e12), Decimal("45000.00"))
        # exploratory arms: 25% of the section-A size
        self.assertEqual(planner.risk_notional(E, 0.05, 20_000_000, planner.ARM_SIZE_FRACTION), Decimal("6750.00"))
        self.assertIsNone(planner.risk_notional(E, None, 1e7))
        self.assertIsNone(planner.risk_notional(E, 0.0, 1e7))

    def test_minimums(self):
        self.assertEqual(planner.sized_qty(Decimal("27000"), Decimal("100")), (270, Decimal("27000"), None))
        self.assertEqual(planner.sized_qty(Decimal("999"), Decimal("10"))[2], "below_min_notional")
        self.assertEqual(planner.sized_qty(Decimal("1500"), Decimal("2000"))[2], "below_one_share")
        self.assertEqual(planner.sized_qty(None, Decimal("10"))[2], "no_risk_size")

    def test_sigma_needs_21_closes(self):
        prior = CAL.prior_sessions(date(2026, 9, 25), 21)
        closes = [100.0 * (1.01 if i % 2 else 0.99) ** 0 * (1 + 0.01 * (-1) ** i) for i in range(21)]
        rows = [{"t": z(datetime(d.year, d.month, d.day, tzinfo=NY)), "c": c, "v": 1, "l": c} for d, c in zip(prior, closes)]
        sigma = planner.sigma_from_bars(CAL, date(2026, 9, 25), rows)
        self.assertAlmostEqual(sigma, 0.0205, places=3)
        self.assertIsNone(planner.sigma_from_bars(CAL, date(2026, 9, 25), rows[1:]))


class Basket(unittest.TestCase):
    def build(self, events, limits=BIG, account=None, blocked=frozenset()):
        return planner.build_open_basket(events, date(2026, 9, 25), planner.Exposure(), limits, account, blocked)

    def test_legs_filters_and_orders(self):
        events = [ev(1, "AAA", "FAVORABLE", price=40), ev(2, "BBB", "FAVORABLE", minute=1),
                  ev(3, "CCC", "UNFAVORABLE", minute=2), ev(4, "DDD", "UNFAVORABLE", minute=3),
                  ev(5, "EEE", "UNFAVORABLE", asset={**ASSET_OK, "easy_to_borrow": False}, minute=4),
                  ev(6, "FFF", "UNFAVORABLE", ssr=True, minute=5),
                  ev(7, "GGG", "FAVORABLE", lane=sig.SMALL, minute=6),
                  ev(8, "HHH", "UNCLEAR", minute=7), ev(9, "AAA", "UNFAVORABLE", minute=8),
                  ev(10, "III", "UNFAVORABLE", minute=9, target=None), ev(11, "JJJ", "UNFAVORABLE", minute=10),
                  ev(12, "KKK", "UNFAVORABLE", asset={**ASSET_OK, "shortable": False}, minute=11)]
        decisions, intents = self.build(events, blocked={"JJJ"})
        by = {(d["symbol"], d["event_id"]): d for d in decisions}
        self.assertEqual(by[("EEE", "5:EEE")]["reason"], "not_easy_to_borrow")
        self.assertEqual(by[("FFF", "6:FFF")]["reason"], "ssr_rule_201")
        self.assertEqual(by[("KKK", "12:KKK")]["reason"], "not_shortable")
        self.assertEqual(by[("GGG", "7:GGG")]["action"], "shadow")
        self.assertEqual(by[("HHH", "8:HHH")]["reason"], "label_unclear")
        self.assertEqual(by[("AAA", "9:AAA")]["reason"], "not_first_in_window")
        self.assertEqual(by[("III", "10:III")]["reason"], "no_risk_size")
        self.assertEqual(by[("JJJ", "11:JJJ")]["reason"], "symbol_held_by_other_arm")
        got = {(i["symbol"], i["side"], i["qty"], i["time_in_force"], i["type"]) for i in intents}
        self.assertEqual(got, {("AAA", "buy", "500", "opg", "market"), ("BBB", "buy", "200", "opg", "market"),
                               ("CCC", "sell", "200", "opg", "market"), ("DDD", "sell", "200", "opg", "market")})
        self.assertIn("nf1-20260925-opg-CCC-short", {i["client_order_id"] for i in intents})

    def test_leg_needs_two_names(self):
        decisions, intents = self.build([ev(1, "AAA", "FAVORABLE"), ev(2, "BBB", "FAVORABLE"), ev(3, "CCC", "UNFAVORABLE")])
        self.assertEqual({i["symbol"] for i in intents}, {"AAA", "BBB"})
        self.assertIn("leg_below_min_names", {d["reason"] for d in decisions if d["symbol"] == "CCC"})

    def test_names_per_leg_and_gross_caps(self):
        longs = [ev(i, f"L{i:02d}", "FAVORABLE", minute=i) for i in range(14)]
        decisions, intents = self.build(longs)
        self.assertEqual(len(intents), 12)
        self.assertEqual(sum(d["reason"] == "names_per_leg_cap" for d in decisions), 2)
        both = [ev(i, f"L{i:02d}", "FAVORABLE", minute=2 * i) for i in range(12)] + \
               [ev(100 + i, f"S{i:02d}", "UNFAVORABLE", minute=2 * i + 1) for i in range(12)]
        small = planner.Limits(E, Decimal("400000"), Decimal("45000"))  # gross cap 400k: 20 names of 20k
        decisions, intents = self.build(both, limits=small)
        gross = sum(Decimal(i["qty"]) * 100 for i in intents)
        self.assertLessEqual(gross, Decimal("400000"))
        self.assertEqual(len(intents), 20)
        self.assertEqual(sum(d["reason"] == "gross_exposure_cap" for d in decisions), 4)

    def test_account_cap_across_arms(self):
        account = [Decimal("890000"), Decimal("900000")]  # other arms already use 890k of a 900k account cap
        decisions, intents = self.build([ev(1, "AAA", "FAVORABLE"), ev(2, "BBB", "FAVORABLE", minute=1)], account=account)
        self.assertEqual(intents, [])
        self.assertIn("account_gross_cap", {d["reason"] for d in decisions})
        account = [Decimal("0"), Decimal("900000")]
        decisions, intents = self.build([ev(1, "AAA", "FAVORABLE"), ev(2, "BBB", "FAVORABLE", minute=1)], account=account)
        self.assertEqual(account[0], Decimal("40000"))  # updated in place with the committed entries

    def test_per_order_cap_and_min_size(self):
        decisions, intents = self.build([ev(1, "AAA", "FAVORABLE", target="60000"), ev(2, "BBB", "FAVORABLE", target="900")])
        self.assertEqual(intents, [])
        self.assertEqual({d["reason"] for d in decisions}, {"per_order_notional_cap", "below_min_notional"})


class CapsAndKill(unittest.TestCase):
    def test_limits_per_arm(self):
        core = planner.Limits.for_arm(planner.CORE, E, Decimal("1"))
        self.assertEqual((core.gross_cap, core.per_order_cap), (E, Decimal("45000.00")))
        self.assertEqual(planner.Limits.for_arm(planner.CORE, E, Decimal("2.5")).gross_cap, Decimal("2250000.0"))
        pm = planner.Limits.for_arm(planner.PM, E, Decimal("3"), extra_cap=E)
        self.assertEqual(pm.gross_cap, Decimal("225000.00"))
        ah = planner.Limits.for_arm(planner.AH, E, Decimal("3"), extra_cap=Decimal("100000"))
        self.assertEqual(ah.gross_cap, Decimal("100000"))

    def test_entry_caps(self):
        lim = planner.Limits(E, Decimal("50000"), Decimal("45000"))
        e = planner.Exposure()
        self.assertEqual(planner.entry_cap_violation(Decimal("45000.01"), "rth", "long", "A", e, lim), "per_order_notional_cap")
        self.assertIsNone(planner.entry_cap_violation(Decimal("45000"), "rth", "long", "A", e, lim))
        e.gross = Decimal("10000")
        self.assertEqual(planner.entry_cap_violation(Decimal("40001"), "rth", "long", "A", e, lim), "gross_exposure_cap")
        e.gross = Decimal("0")
        e.names[("rth", "long")] = 12
        self.assertEqual(planner.entry_cap_violation(Decimal("100"), "rth", "long", "A", e, lim), "names_per_leg_cap")
        self.assertIsNone(planner.entry_cap_violation(Decimal("100"), "rth", "short", "A", e, lim))
        e.symbols.add("A")
        self.assertEqual(planner.entry_cap_violation(Decimal("100"), "rth", "short", "A", e, lim), "symbol_already_traded_today")
        self.assertEqual(planner.entry_cap_violation(Decimal("100"), "rth", "short", "B", planner.Exposure(), lim,
                                                     (Decimal("99950"), Decimal("100000"))), "account_gross_cap")

    def test_kill_switch_at_two_percent(self):
        self.assertTrue(planner.kill_switch_triggered("100000", "98000"))
        self.assertFalse(planner.kill_switch_triggered("100000", "98000.01"))
        self.assertFalse(planner.kill_switch_triggered("100000", "98500"))  # the old 1.5% level no longer trips
        self.assertFalse(planner.kill_switch_triggered(None, "1"))


class IdsAndEnvelopes(unittest.TestCase):
    def test_client_order_ids_per_arm(self):
        cid = planner.client_order_id(date(2026, 9, 25), "opg", "BRK.B", "long")
        self.assertEqual(cid, "nf1-20260925-opg-BRK.B-long")
        self.assertEqual(cid, planner.client_order_id(date(2026, 9, 25), "opg", "BRK.B", "long"))
        self.assertEqual(planner.client_order_id(date(2026, 9, 25), "ent", "ACME", "short", planner.PM), "nf1x-pm-20260925-ent-ACME-short")
        self.assertEqual(planner.client_order_id(date(2026, 9, 25), "opg", "ACME", "long", planner.AH), "nf1x-ah-20260925-opg-ACME-long")
        for c in (cid, "nf1x-pm-20260925-ent-ACME-short", "nf1x-ah-20260925-opg-ACME-long"):
            self.assertTrue(planner.is_nf1(c))
        self.assertFalse(planner.is_nf1("adaptive-1"))
        self.assertFalse(planner.is_nf1("nf1x-zz-20260925-ent-ACME-long"))
        self.assertEqual(planner.parse_cid("nf1x-ah-20260925-opg-BRK.B-long"),
                         {"arm": "ah", "date": date(2026, 9, 25), "stage": "opg", "symbol": "BRK.B", "leg": "long"})
        self.assertIsNone(planner.parse_cid("nf1-2026092-opg-A-long"))
        self.assertEqual(planner.exit_intent(date(2026, 9, 25), "cls", "ACME", "-7")["client_order_id"],
                         "nf1-20260925-cls-ACME-short")

    def test_auction_envelopes(self):
        oc = common.order_contract()
        env = planner.contract_envelope(planner.entry_intent(date(2026, 9, 25), "opg", "ACME", "long", 20, "opg"))
        self.assertEqual(env["intent"]["time_in_force"], "opg")
        self.assertEqual(env["local_extension"]["time_in_force"], "opg")
        self.assertFalse(env["submission_enabled"])
        env = planner.contract_envelope(planner.exit_intent(date(2026, 9, 25), "cls", "ACME", "-20"))
        self.assertEqual((env["intent"]["side"], env["intent"]["time_in_force"], env["intent"]["qty"]), ("buy", "cls", "20"))
        env = planner.contract_envelope(planner.exit_intent(date(2026, 9, 24), "opg", "ACME", "20", arm=planner.AH))
        self.assertEqual((env["intent"]["time_in_force"], env["intent"]["client_order_id"]), ("opg", "nf1x-ah-20260924-opg-ACME-long"))
        with self.assertRaises(oc.ContractError):
            planner.contract_envelope({**planner.entry_intent(date(2026, 9, 25), "opg", "ACME", "long", 20, "opg"),
                                       "type": "limit", "limit_price": "10.00"})
        with self.assertRaises(oc.ContractError):
            planner.contract_envelope(planner.entry_intent(date(2026, 9, 25), "opg", "ACME", "long", 20, "gtc"))

    def test_limit_and_extended_envelopes(self):
        oc = common.order_contract()
        env = planner.contract_envelope(planner.entry_intent(date(2026, 9, 25), "rth", "ACME", "short", 10, "day", Decimal("99.80")))
        self.assertEqual(env["intent"]["limit_price"], "99.8")
        self.assertFalse(env["intent"]["extended_hours"])
        ext = planner.exit_intent(date(2026, 9, 25), "ext1", "ACME", "10", limit_price=Decimal("99.50"), extended=True)
        self.assertTrue(planner.contract_envelope(ext)["intent"]["extended_hours"])
        arm_entry = planner.entry_intent(date(2026, 9, 25), "ent", "ACME", "long", 5, "day", "10.03", arm=planner.PM, extended=True)
        env = planner.contract_envelope(arm_entry)
        self.assertEqual((env["intent"]["extended_hours"], env["intent"]["time_in_force"], env["intent"]["type"]), (True, "day", "limit"))
        with self.assertRaises(oc.ContractError):
            planner.contract_envelope({k: v for k, v in ext.items() if k != "limit_price"} | {"type": "market"})
        with self.assertRaises(oc.ContractError):
            planner.contract_envelope({**planner.entry_intent(date(2026, 9, 25), "rth", "ACME", "long", 1, "day", "10.00"),
                                       "qty": "1.5"})


class RthAndArmEntries(unittest.TestCase):
    def rth_event(self, label="FAVORABLE", target="2000"):
        return {"event_id": "1:ACME", "symbol": "ACME", "label": label, "lane": sig.LIQUID,
                "entry_utc": z(ny(2026, 9, 25, 10, 15)), "asset": ASSET_OK, "ssr": False, "target_notional": Decimal(target)}

    def plan(self, event, quote, now):
        return planner.plan_rth_entry(event, quote, now, date(2026, 9, 25), planner.Exposure(), BIG)

    def test_rth_entry_prices_and_spread(self):
        now = ny(2026, 9, 25, 10, 15, 5)
        d, intent = self.plan(self.rth_event(), {"bp": 99.95, "ap": 100.05}, now)
        self.assertEqual((d["action"], intent["limit_price"], intent["qty"], intent["side"]), ("enter", "100.26", "19", "buy"))
        self.assertEqual(intent["client_order_id"], "nf1-20260925-rth-ACME-long")
        self.assertNotIn("extended_hours", intent)
        d, intent = self.plan(self.rth_event("UNFAVORABLE"), {"bp": 99.95, "ap": 100.05}, now)
        self.assertEqual((intent["limit_price"], intent["side"]), ("99.75", "sell"))
        d, intent = self.plan(self.rth_event(), {"bp": 99.7, "ap": 100.3}, now)
        self.assertEqual((d["reason"], intent), ("spread_above_50bps", None))
        d, _ = self.plan(self.rth_event(), {"bp": 99.95, "ap": 100.05}, ny(2026, 9, 25, 10, 20, 1))
        self.assertEqual(d["reason"], "entry_late")
        d, _ = self.plan(self.rth_event(), {"bp": 99.95, "ap": 100.05}, ny(2026, 9, 25, 10, 14))
        self.assertEqual(d["action"], "wait")

    def test_extended_hours_arm_entry_flags(self):
        ev = {**self.rth_event(target="5000"), "entry_utc": z(ny(2026, 9, 25, 16, 20))}
        now = ny(2026, 9, 25, 16, 20, 10)
        d, intent = planner.plan_ext_entry(ev, {"bp": 49.9, "ap": 50.1}, now, date(2026, 9, 25), planner.Exposure(),
                                           planner.Limits.for_arm(planner.AH, E, 1), planner.AH)
        self.assertEqual((intent["extended_hours"], intent["time_in_force"], intent["type"], intent["limit_price"], intent["qty"]),
                         (True, "day", "limit", "50.26", "99"))
        self.assertEqual(intent["client_order_id"], "nf1x-ah-20260925-ent-ACME-long")
        self.assertEqual((d["arm"], d["session_label"]), ("ah", planner.EXT_POST))
        d, intent = planner.plan_ext_entry({**ev, "label": "UNFAVORABLE"}, {"bp": 49.9, "ap": 50.1}, now, date(2026, 9, 25),
                                           planner.Exposure(), planner.Limits.for_arm(planner.PM, E, 1), planner.PM)
        self.assertEqual((intent["limit_price"], intent["side"], intent["client_order_id"]), ("49.75", "sell", "nf1x-pm-20260925-ent-ACME-short"))
        d, intent = planner.plan_ext_entry(ev, {"bp": 49.0, "ap": 50.0}, now, date(2026, 9, 25), planner.Exposure(),
                                           planner.Limits.for_arm(planner.AH, E, 1), planner.AH)
        self.assertEqual((d["reason"], intent), ("spread_above_100bps", None))
        d, intent = planner.plan_ext_entry(ev, None, now, date(2026, 9, 25), planner.Exposure(),
                                           planner.Limits.for_arm(planner.AH, E, 1), planner.AH)
        self.assertEqual(d["reason"], "no_two_sided_quote")

    def test_arm_for_release(self):
        self.assertEqual(planner.arm_for_release(CAL, ny(2026, 9, 25, 4, 30)), planner.PM)
        self.assertIsNone(planner.arm_for_release(CAL, ny(2026, 9, 25, 9, 0)))
        self.assertIsNone(planner.arm_for_release(CAL, ny(2026, 9, 25, 3, 59)))
        self.assertEqual(planner.arm_for_release(CAL, ny(2026, 9, 25, 16, 0)), planner.AH)
        self.assertEqual(planner.arm_for_release(CAL, ny(2026, 9, 25, 19, 29)), planner.AH)
        self.assertIsNone(planner.arm_for_release(CAL, ny(2026, 9, 25, 19, 30)))
        self.assertIsNone(planner.arm_for_release(CAL, ny(2026, 11, 27, 16, 0)))  # early close day: no ah arm
        self.assertIsNone(planner.arm_for_release(CAL, ny(2026, 9, 26, 5, 0)))    # Saturday


class LedgerAndExits(unittest.TestCase):
    def orders(self):
        return [
            {"client_order_id": "nf1-20260925-opg-AAA-long", "side": "buy", "filled_qty": "20"},
            {"client_order_id": "nf1-20260925-opg-BBB-short", "side": "sell", "filled_qty": "15"},
            {"client_order_id": "nf1x-pm-20260925-ent-AAA-long", "side": "buy", "filled_qty": "5"},
            {"client_order_id": "nf1x-ah-20260924-ent-CCC-long", "side": "buy", "filled_qty": "8"},
            {"client_order_id": "nf1x-ah-20260925-ent-DDD-short", "side": "sell", "filled_qty": "4"},
            {"client_order_id": "nf1-20260925-rth-EEE-long", "side": "buy", "filled_qty": "0"},
            {"client_order_id": "other-1", "side": "buy", "filled_qty": "100"},
        ]

    def test_ledger(self):
        book = planner.ledger(self.orders())
        self.assertEqual(book, {("core", date(2026, 9, 25), "AAA"): Decimal("20"), ("core", date(2026, 9, 25), "BBB"): Decimal("-15"),
                                ("pm", date(2026, 9, 25), "AAA"): Decimal("5"), ("ah", date(2026, 9, 24), "CCC"): Decimal("8"),
                                ("ah", date(2026, 9, 25), "DDD"): Decimal("-4")})
        closed = planner.ledger(self.orders() + [{"client_order_id": "nf1-20260925-cls-AAA-long", "side": "sell", "filled_qty": "20"}])
        self.assertNotIn(("core", date(2026, 9, 25), "AAA"), closed)

    def test_close_out_plans_per_arm(self):
        book = planner.ledger(self.orders())
        cls = planner.plan_cls_exits(book, date(2026, 9, 25), covered=set())
        self.assertEqual([(i["client_order_id"], i["side"], i["qty"], i["time_in_force"]) for i in cls],
                         [("nf1-20260925-cls-AAA-long", "sell", "20", "cls"), ("nf1-20260925-cls-BBB-short", "buy", "15", "cls"),
                          ("nf1x-pm-20260925-cls-AAA-long", "sell", "5", "cls")])
        mkt = planner.plan_market_flatten(book, date(2026, 9, 25), covered={("core", "AAA"), ("pm", "AAA")})
        self.assertEqual([(i["symbol"], i["time_in_force"], i["type"]) for i in mkt], [("BBB", "day", "market")])
        ext, missing = planner.plan_ext_flatten(book, {"AAA": {"bp": 50.0, "ap": 50.1}, "BBB": {"bp": 20.0, "ap": 20.02}},
                                                date(2026, 9, 25), stage="ext1")
        self.assertEqual([(i["client_order_id"], i["side"], i["limit_price"], i["extended_hours"]) for i in ext],
                         [("nf1-20260925-ext1-AAA-long", "sell", "49.75", True), ("nf1-20260925-ext1-BBB-short", "buy", "20.13", True),
                          ("nf1x-pm-20260925-ext1-AAA-long", "sell", "49.75", True)])
        self.assertEqual(missing, [])
        opg = planner.plan_ah_opg_exits(book, date(2026, 9, 25), CAL)
        self.assertEqual([(i["client_order_id"], i["side"], i["time_in_force"]) for i in opg],
                         [("nf1x-ah-20260924-opg-CCC-long", "sell", "opg")])
        opg_monday = planner.plan_ah_opg_exits(book, date(2026, 9, 28), CAL)
        self.assertEqual([i["client_order_id"] for i in opg_monday], ["nf1x-ah-20260925-opg-DDD-short"])


class Reconciliation(unittest.TestCase):
    def test_reconcile_flat_day(self):
        fills = [{"side": "buy", "filled_qty": "10", "filled_avg_price": "100"},
                 {"side": "sell", "filled_qty": "10", "filled_avg_price": "101"}]
        ok = planner.reconcile("100000", "100009.98", fills, [], [])
        self.assertTrue(ok["ok"], ok)
        self.assertEqual(ok["realized_pnl"], "10")
        bad = planner.reconcile("100000", "100005", fills, [{"symbol": "A", "qty": "3"}],
                                [{"client_order_id": "nf1-20260925-cls-A-long"}])
        self.assertEqual(bad["problems"], ["positions_open", "orders_open", "cash_mismatch"])

    def test_reconcile_with_overnight_arm(self):
        fills = [{"side": "buy", "filled_qty": "10", "filled_avg_price": "100"},
                 {"side": "sell", "filled_qty": "10", "filled_avg_price": "101"},
                 {"side": "buy", "filled_qty": "5", "filled_avg_price": "20"}]
        ok = planner.reconcile("100000", "99910", fills, [{"symbol": "AHX", "qty": "5"}], [], expected={"AHX": "5"})
        self.assertTrue(ok["ok"], ok)
        self.assertIsNone(ok["realized_pnl"])
        bad = planner.reconcile("100000", "99910", fills, [{"symbol": "AHX", "qty": "5"}, {"symbol": "B", "qty": "-1"}], [],
                                expected={"AHX": "5"})
        self.assertEqual((bad["problems"], bad["unexpected_positions"]), (["positions_open"], ["B"]))


if __name__ == "__main__":
    unittest.main()
