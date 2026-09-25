"""SYN: synthetic checks of the pure rules in blueprints/us-equities/sota-mover/news-llm/news_signal.py.

Standard library only; no GPU, model file, network or private data. The real XNYS
session calendar committed at blueprints/us-equities/mover-v3/data/session-calendar.json
supplies DST transitions, holidays and early closes.
"""

import importlib.util
import json
import math
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/us-equities/sota-mover/news-llm"


def load_signal():
    spec = importlib.util.spec_from_file_location("news_signal", BLUEPRINT / "news_signal.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["news_signal"] = module
    spec.loader.exec_module(module)
    return module


sig = load_signal()
CALENDAR = sig.Calendar.from_calendar_json(json.loads((ROOT / "blueprints/us-equities/mover-v3/data/session-calendar.json").read_text()))


def ny(y, mo, d, h, mi, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=sig.NY)


def utc(text):
    return sig.as_utc(text)


class TimingWindows(unittest.TestCase):
    def test_pre_open_overnight_uses_same_session_open_and_close(self):
        w = CALENDAR.classify(ny(2021, 3, 15, 8, 59, 59))
        self.assertEqual((w.kind, w.session, w.sub), (sig.OVERNIGHT, date(2021, 3, 15), "pre_open"))
        self.assertEqual(w.entry_utc, utc("2021-03-15T13:30:00Z"))  # EDT open
        self.assertEqual(w.exit_utc, utc("2021-03-15T20:00:00Z"))
        self.assertEqual(w.decision_cutoff_utc, utc("2021-03-15T13:00:00Z"))

    def test_0900_to_0930_is_excluded(self):
        self.assertEqual(CALENDAR.classify(ny(2021, 3, 15, 9, 0)).kind, sig.EXCLUDED_PREMARKET)
        self.assertEqual(CALENDAR.classify(ny(2021, 3, 15, 9, 29, 59)).kind, sig.EXCLUDED_PREMARKET)

    def test_rth_entry_is_release_plus_15_minutes_and_exit_at_close(self):
        w = CALENDAR.classify(ny(2021, 3, 15, 9, 30))
        self.assertEqual(w.kind, sig.RTH)
        self.assertEqual(w.entry_utc, utc("2021-03-15T13:45:00Z"))
        self.assertEqual(w.exit_utc, utc("2021-03-15T20:00:00Z"))
        self.assertEqual(CALENDAR.classify(ny(2021, 3, 15, 15, 29, 59)).kind, sig.RTH)
        self.assertEqual(CALENDAR.classify(ny(2021, 3, 15, 15, 30)).kind, sig.EXCLUDED_LATE)
        self.assertEqual(CALENDAR.classify(ny(2021, 3, 15, 15, 59, 59)).kind, sig.EXCLUDED_LATE)

    def test_release_at_the_close_rolls_to_next_session_over_the_weekend(self):
        w = CALENDAR.classify(ny(2021, 3, 12, 16, 0))  # Friday 16:00 EST
        self.assertEqual((w.kind, w.session, w.sub), (sig.OVERNIGHT, date(2021, 3, 15), "post_close"))

    def test_dst_spring_forward_cutoff_and_open_move_in_utc(self):
        friday = CALENDAR.get(date(2021, 3, 12))
        monday = CALENDAR.get(date(2021, 3, 15))
        self.assertEqual(friday.cutoff_utc, utc("2021-03-12T14:00:00Z"))
        self.assertEqual(monday.cutoff_utc, utc("2021-03-15T13:00:00Z"))
        # Sunday evening after the 2021-03-14 switch belongs to Monday's overnight window.
        w = CALENDAR.classify(ny(2021, 3, 14, 20, 0))
        self.assertEqual((w.kind, w.session), (sig.OVERNIGHT, date(2021, 3, 15)))
        # 08:30 EDT on Monday is 12:30Z: before the 13:00Z cutoff, so still overnight.
        self.assertEqual(CALENDAR.classify(utc("2021-03-15T12:30:00Z")).kind, sig.OVERNIGHT)
        # 13:15Z on Monday is 09:15 EDT: excluded, although it would be 08:15 in EST.
        self.assertEqual(CALENDAR.classify(utc("2021-03-15T13:15:00Z")).kind, sig.EXCLUDED_PREMARKET)

    def test_dst_fall_back(self):
        w = CALENDAR.classify(ny(2021, 11, 8, 8, 30))  # Monday after the 2021-11-07 switch, EST
        self.assertEqual((w.kind, w.entry_utc), (sig.OVERNIGHT, utc("2021-11-08T14:30:00Z")))
        self.assertEqual(CALENDAR.classify(utc("2021-11-08T13:30:00Z")).kind, sig.OVERNIGHT)  # 08:30 EST

    def test_holiday_rolls_to_next_session(self):
        w = CALENDAR.classify(ny(2021, 4, 2, 10, 0))  # Good Friday, market closed
        self.assertEqual((w.kind, w.session, w.sub), (sig.OVERNIGHT, date(2021, 4, 5), "post_close"))
        w = CALENDAR.classify(ny(2021, 7, 5, 8, 0))  # Independence Day observed (Monday)
        self.assertEqual(w.session, date(2021, 7, 6))

    def test_early_close_session(self):
        s = CALENDAR.get(date(2020, 11, 27))
        self.assertTrue(s.early_close)
        self.assertEqual(CALENDAR.classify(ny(2020, 11, 27, 12, 29)).kind, sig.RTH)
        self.assertEqual(CALENDAR.classify(ny(2020, 11, 27, 12, 30)).kind, sig.EXCLUDED_LATE)
        w = CALENDAR.classify(ny(2020, 11, 27, 13, 5))  # after the 13:00 early close
        self.assertEqual((w.kind, w.session), (sig.OVERNIGHT, date(2020, 11, 30)))
        w = CALENDAR.classify(ny(2020, 12, 24, 14, 0))  # early close, then Christmas, then weekend
        self.assertEqual((w.kind, w.session), (sig.OVERNIGHT, date(2020, 12, 28)))

    def test_estimated_ingestion_uses_p90_of_predecessors(self):
        self.assertEqual(sig.estimated_ingestion([], 500), 500)
        preds = sorted(range(1_000, 1_100))  # 100 predecessors, p90 = element 89 -> 1,089
        self.assertEqual(sig.quantile_sorted(preds, 0.9), 1_089)
        self.assertEqual(sig.estimated_ingestion(preds, 500), 1_089)  # stamped earlier than neighbours
        self.assertEqual(sig.estimated_ingestion(preds, 2_000), 2_000)  # quiet period: own stamp
        # a handful of late-stamped predecessors cannot move the p90
        noisy = sorted([1_000] * 95 + [10**9] * 5)
        self.assertEqual(sig.estimated_ingestion(noisy, 900), 1_000)

    def test_ingestion_guard_against_the_window_cutoff(self):
        w = CALENDAR.classify(ny(2021, 3, 15, 7, 0))  # overnight, cutoff 09:00 EDT = 13:00Z
        cutoff = utc("2021-03-15T13:00:00Z").timestamp()
        self.assertEqual(sig.ingestion_guard(w, cutoff - 1), (True, "ok"))
        self.assertEqual(sig.ingestion_guard(w, cutoff), (False, "ingested_after_cutoff"))
        r = CALENDAR.classify(ny(2021, 3, 15, 10, 0))  # RTH, cutoff = entry 10:15
        entry = utc("2021-03-15T14:15:00Z").timestamp()
        self.assertEqual(sig.ingestion_guard(r, entry), (True, "ok"))
        self.assertEqual(sig.ingestion_guard(r, entry + 1), (False, "ingested_after_cutoff"))
        # an old stamp ingested after the cutoff is dropped although created_at is early
        self.assertFalse(sig.ingestion_guard(w, utc("2021-03-15T15:00:00Z").timestamp())[0])

    def test_rth_entry_quote_and_price(self):
        entry = "2021-03-15T14:15:00Z"
        quotes = [
            {"bp": 10.0, "ap": 10.02, "t": "2021-03-15T14:14:59Z"},   # before entry
            {"bp": 0, "ap": 10.02, "t": "2021-03-15T14:15:01Z"},      # one-sided
            {"bp": 10.05, "ap": 10.0, "t": "2021-03-15T14:15:02Z"},   # crossed
            {"bp": 10.01, "ap": 10.03, "t": "2021-03-15T14:15:03Z"},
        ]
        q = sig.rth_entry_quote(quotes, entry)
        self.assertEqual((q["bid"], q["ask"]), (10.01, 10.03))
        self.assertEqual(sig.rth_entry_price(q, 1), 10.03)
        self.assertEqual(sig.rth_entry_price(q, -1), 10.01)
        self.assertIsNone(sig.rth_entry_quote([{"bp": 1, "ap": 1.1, "t": "2021-03-15T14:16:01Z"}], entry))
        self.assertIsNone(sig.rth_entry_price(None, 1))

    def test_rule_201_flags_use_pre_decision_information(self):
        self.assertTrue(sig.ssr_carryover(89.9, 100.0))
        self.assertTrue(sig.ssr_carryover(90.0, 100.0))
        self.assertFalse(sig.ssr_carryover(90.1, 100.0))
        self.assertFalse(sig.ssr_carryover(None, 100.0))
        over = {"window": "overnight", "ssr_carryover": False, "prior_close": 100.0}
        self.assertFalse(sig.ssr_flag(over))
        self.assertTrue(sig.ssr_flag(dict(over, ssr_carryover=True)))
        rth = {"window": "rth", "ssr_carryover": False, "prior_close": 100.0}
        self.assertTrue(sig.ssr_flag(rth, {"bid": 89.99, "ask": 90.1}))
        self.assertFalse(sig.ssr_flag(rth, {"bid": 90.01, "ask": 90.1}))
        self.assertFalse(sig.ssr_flag(rth, None))

    def test_timestamp_guard(self):
        w = CALENDAR.classify(ny(2021, 3, 15, 7, 0))
        self.assertEqual(sig.timestamp_guard(w, ny(2021, 3, 15, 8, 59, 59)), (True, "ok"))
        self.assertEqual(sig.timestamp_guard(w, ny(2021, 3, 15, 9, 0)), (False, "updated_after_cutoff"))
        self.assertEqual(sig.timestamp_guard(w, None), (False, "missing_updated_at"))
        r = CALENDAR.classify(ny(2021, 3, 15, 10, 0))
        self.assertEqual(sig.timestamp_guard(r, ny(2021, 3, 15, 10, 15)), (True, "ok"))
        self.assertEqual(sig.timestamp_guard(r, ny(2021, 3, 15, 10, 15, 1)), (False, "updated_after_cutoff"))
        x = CALENDAR.classify(ny(2021, 3, 15, 9, 10))
        self.assertEqual(sig.timestamp_guard(x, ny(2021, 3, 15, 9, 10)), (False, "not_tradable_window"))


class Scoring(unittest.TestCase):
    def test_parse_label(self):
        cases = {
            "YES\nThe deal adds revenue.": ("YES", 1, True),
            "  yes.": ("YES", 1, True),
            "**NO** because": ("NO", -1, True),
            "\n\nUNKNOWN": ("UNKNOWN", 0, True),
            "Answer: NO": ("NO", -1, True),
            '"YES"': ("YES", 1, True),
            "“NO”": ("NO", -1, True),
            "NOT sure": ("PARSE_FAIL", 0, False),
            "Nope": ("PARSE_FAIL", 0, False),
            "Maybe YES": ("PARSE_FAIL", 0, False),
            "": ("PARSE_FAIL", 0, False),
            "   \n  ": ("PARSE_FAIL", 0, False),
            "123": ("PARSE_FAIL", 0, False),
            None: ("PARSE_FAIL", 0, False),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(sig.parse_label(raw, "llt_alpaca"), expected)

    def test_checkpoint_year_mapping(self):
        self.assertEqual(sig.checkpoint_year(utc("2016-06-01T12:00:00Z")), 2015)
        self.assertEqual(sig.checkpoint_year(utc("2020-01-01T01:00:00Z")), 2018)  # 2019-12-31 in New York
        self.assertEqual(sig.checkpoint_year(utc("2020-01-01T05:00:00Z")), 2019)
        self.assertEqual(sig.checkpoint_year(utc("2024-12-31T23:00:00Z")), 2023)
        self.assertEqual(sig.checkpoint_year(utc("2025-03-01T12:00:00Z")), 2024)
        self.assertEqual(sig.checkpoint_year(utc("2026-09-18T12:00:00Z")), 2024)
        with self.assertRaises(ValueError):
            sig.checkpoint_year(utc("2015-12-31T20:00:00Z"))
        self.assertEqual(sig.checkpoint_repo(2024), "manelalab/chrono-gpt-instruct-v1-20241231")

    def test_checkpoint_pins_cover_every_mapped_year(self):
        pins = json.loads((BLUEPRINT / "checkpoints.json").read_text())
        years = {int(y) for y in pins["checkpoints"]}
        self.assertEqual(years, set(range(sig.FIRST_CHECKPOINT_YEAR, sig.LAST_CHECKPOINT_YEAR + 1)))
        for y, entry in pins["checkpoints"].items():
            self.assertEqual(entry["repo"], sig.checkpoint_repo(int(y)))
            self.assertRegex(entry["revision"], r"^[0-9a-f]{40}$")
            self.assertEqual(entry["files"]["ChronoGPT_instruct.py"]["sha256"], pins["reviewed_code"]["sha256"])
            self.assertTrue(entry["files"]["pytorch_model.bin"]["lfs"])

    def test_prompt_matches_paper_text_up_to_quotes_and_placeholders(self):
        paper = sig.PAPER_PROMPT_VERBATIM.replace("“", '"').replace("”", '"')
        paper = paper.replace("company name", "{company}").replace("Headline: headline", "Headline: {headline}")
        self.assertEqual(paper, sig.PROMPT_TEMPLATE)
        p = sig.build_prompt("Humana Inc.", "Cigna Calls Off Humana Pursuit, Plans Big Stock Buyback")
        self.assertTrue(p.endswith("stock price of Humana Inc. in the short term?\nHeadline: Cigna Calls Off Humana Pursuit, Plans Big Stock Buyback"))

    def test_variants_build_their_documented_formats(self):
        llt = sig.model_input("Acme Inc.", "Acme Wins Contract", "llt_alpaca")
        self.assertTrue(llt.startswith(sig.ALPACA_PREAMBLE + "\n\n### Instruction:\nForget all your previous instructions."))
        self.assertIn("stock price of Acme Inc. in the short term?\n\n### Input:\nAcme Wins Contract\n\n### Response:\n", llt)
        self.assertNotIn("Headline:", llt)
        hl = sig.model_input("Acme Inc.", "Acme Wins Contract", "hlmw_alpaca")
        self.assertEqual(
            hl,
            "Below is an instruction that describes a task. Write a response that appropriately completes the request."
            "\n\n### Instruction:\nClassify this news headline as either FAVORABLE, or UNFAVORABLE, or UNCLEAR for the "
            "stock price of Acme Inc.\n\n### Input:\nAcme Wins Contract\n\n### Response:\n",
        )
        up = sig.model_input("Acme Inc.", "Acme Wins Contract", "llt_upstream_wrapper")
        self.assertEqual(up, sig.chrono_format(sig.build_prompt("Acme Inc.", "Acme Wins Contract")))
        shas = {sig.template_sha256(v) for v in sig.VARIANTS}
        self.assertEqual(len(shas), len(sig.VARIANTS))
        self.assertEqual(sig.TEMPLATE_SHA256, sig.template_sha256(sig.OPERATIVE_VARIANT))
        self.assertEqual(set(sig.VARIANT_PREFERENCE), set(sig.VARIANTS))

    def test_parse_label_per_variant(self):
        self.assertEqual(sig.parse_label("FAVORABLE.", "hlmw_alpaca"), ("FAVORABLE", 1, True))
        self.assertEqual(sig.parse_label("Unfavorable news", "hlmw_alpaca"), ("UNFAVORABLE", -1, True))
        self.assertEqual(sig.parse_label("UNCLEAR", "hlmw_alpaca"), ("UNCLEAR", 0, True))
        self.assertEqual(sig.parse_label("YES", "hlmw_alpaca"), ("PARSE_FAIL", 0, False))
        self.assertEqual(sig.parse_label("FAVORABLE", "llt_alpaca"), ("PARSE_FAIL", 0, False))

    def test_operative_score_unique_prefix_rule(self):
        cases = {
            "UNFAVORABLE": ("UNFAVORABLE", -1, "exact"),
            "UNFLEXIBLE": ("UNFAVORABLE", -1, "prefix"),
            "UNFRIENDLY,": ("UNFAVORABLE", -1, "prefix"),
            "UNF FA": ("UNFAVORABLE", -1, "prefix"),
            "Unfavorable news": ("UNFAVORABLE", -1, "exact"),
            "FAVORABLE.": ("FAVORABLE", 1, "exact"),
            "FAVOR": ("FAVORABLE", 1, "prefix"),
            "**Favorable**": ("FAVORABLE", 1, "exact"),
            "UNCLEAR": ("UNCLEAR", 0, "exact"),
            "UNCERTAINTY": ("UNCLEAR", 0, "prefix"),
            "Answer: UNFLEASIBLE": ("UNFAVORABLE", -1, "prefix"),
            "UN": ("PARSE_FAIL", 0, "none"),
            "FA": ("PARSE_FAIL", 0, "none"),
            "THE": ("PARSE_FAIL", 0, "none"),
            "": ("PARSE_FAIL", 0, "none"),
            None: ("PARSE_FAIL", 0, "none"),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(sig.operative_score(raw), expected)
        self.assertEqual(sig.operative_score("UNFAVORABLE", stop="context_overflow"), ("PARSE_FAIL", 0, "none"))
        # the strict rule (stored labels) is unchanged: UNFLEXIBLE stays a parse failure there
        self.assertEqual(sig.parse_label("UNFLEXIBLE", "hlmw_alpaca"), ("PARSE_FAIL", 0, False))
        # every exact label maps to the same score under both rules
        for word, score in sig.FAVORABLE_LABELS.items():
            self.assertEqual(sig.operative_score(word)[1], score)
            self.assertEqual(sig.parse_label(word, "hlmw_alpaca")[1], score)

    def test_label_decided_stop_rule(self):
        self.assertFalse(sig.label_decided(""))
        self.assertFalse(sig.label_decided("YES"))
        self.assertFalse(sig.label_decided("UN"))
        self.assertFalse(sig.label_decided("Answer"))
        self.assertFalse(sig.label_decided("\n"))
        self.assertTrue(sig.label_decided("YES."))
        self.assertTrue(sig.label_decided("YES\n"))
        self.assertTrue(sig.label_decided("UNFAVORABLE "))
        self.assertTrue(sig.label_decided("Answer: NO,"))
        self.assertTrue(sig.label_decided("Headline: x"))
        self.assertTrue(sig.label_decided("- (MS)"))
        # stopping never changes the parsed label of the full text
        for full in ("YES. Because", "Headline: Acme wins", "UNFAVORABLE for", "**NO** it is", "Answer: YES\nx"):
            for k in range(1, len(full) + 1):
                if sig.label_decided(full[:k]):
                    self.assertEqual(sig.parse_label(full[:k], "llt_alpaca"), sig.parse_label(full, "llt_alpaca"))
                    self.assertEqual(sig.parse_label(full[:k], "hlmw_alpaca"), sig.parse_label(full, "hlmw_alpaca"))
                    break

    def test_select_variant_rule(self):
        good_llt = {"n": 100, "labels": {"YES": 40, "NO": 10, "UNKNOWN": 35, "PARSE_FAIL": 15}}
        good_hl = {"n": 100, "labels": {"FAVORABLE": 30, "UNFAVORABLE": 30, "PARSE_FAIL": 40}}
        self.assertEqual(sig.select_variant({"llt_alpaca": good_llt, "hlmw_alpaca": good_hl}), "llt_alpaca")
        few_directional = {"n": 100, "labels": {"YES": 30, "NO": 10, "UNKNOWN": 30, "PARSE_FAIL": 30}}
        self.assertEqual(sig.select_variant({"llt_alpaca": few_directional, "hlmw_alpaca": good_hl}), "hlmw_alpaca")
        one_sided = {"n": 100, "labels": {"YES": 96, "NO": 1, "UNKNOWN": 3}}
        self.assertEqual(sig.select_variant({"llt_alpaca": one_sided, "hlmw_alpaca": good_hl}), "hlmw_alpaca")
        self.assertIsNone(sig.select_variant({"llt_alpaca": few_directional, "hlmw_alpaca": {"n": 0, "labels": {}}}))

    def test_chrono_wrapper_matches_upstream_extract_response_format(self):
        wrapped = sig.chrono_format("X")
        self.assertEqual(
            wrapped,
            "\n\n### Instruction:\nYou are ChronoGPT, a large language model trained by ManelaLab at WashU.\n"
            "    Below is an instruction that describes a task.\n"
            "    Write a response that appropriately completes the request.\nX\n\n### Input:\n### Response:\n",
        )
        self.assertEqual(sig.template_sha256("llt_upstream_wrapper"), sig.sha256_text(sig.chrono_format(sig.PROMPT_TEMPLATE)))
        self.assertEqual(sig.OPERATIVE_VARIANT, "hlmw_alpaca")
        self.assertEqual(sig.parse_label("UNFAVORABLE"), ("UNFAVORABLE", -1, True))


class TextAndRelevance(unittest.TestCase):
    def test_parse_symbols_accepts_json_and_python_literals_only(self):
        self.assertEqual(sig.parse_symbols("['TSLA']"), ["TSLA"])
        self.assertEqual(sig.parse_symbols('["aapl", "AAPL", "MSFT"]'), ["AAPL", "MSFT"])
        self.assertEqual(sig.parse_symbols("[]"), [])
        self.assertIsNone(sig.parse_symbols("__import__('os')"))
        self.assertIsNone(sig.parse_symbols("[1, 2]"))
        self.assertIsNone(sig.parse_symbols(None))

    def test_normalize_and_clean_headline(self):
        self.assertEqual(sig.normalize_headline("Apple &amp; Co. <b>Beats</b>!"), "apple co b beats b")
        self.assertEqual(sig.normalize_headline("APPLE  co  B beats b"), "apple co b beats b")
        self.assertEqual(sig.clean_headline("  Apple &amp;\n Co  "), "Apple & Co")

    def test_movement_headlines(self):
        moving = [
            "Why Wayfair Stock Is Tumbling After The Close",
            "Splunk shares are trading higher after the company reported results",
            "Enveric Bio Stock Spikes 115% After Notice Of Allowance",
            "PacWest Bancorp Shares Halted On Circuit Breaker, Stock Now Down -34.5%",
            "Datadog Unusual Options Activity For May 23",
            "What Is Going On With Meta Stock Wednesday",
            "If You Invested $1000 In This Stock 20 Years Ago, You Would Have $14,000 Today",
            "Here's How Much $100 Invested In DexCom 15 Years Ago Would Be Worth This Much Today",
            "12 Biggest Movers From Friday",
        ]
        not_moving = [
            "Bernstein Upgrades Roper Techs to Outperform, Raises Price Target to $525",
            "InterDigital Q1 EPS $4.21 Beats $0.62 Estimate, Sales $202.37M Beat $100.58M Estimate",
            "Gogoro Reiterate 2023 Outlook; Revenue Of $400M-$450M, Up 4.5%-17.6% Y/Y",
            "Advanced Drainage Systems Board Approves A 17% Increase In Annual Dividend",
            "FDA Approves Merck's Keytruda For New Indication",
            # D5 audit narrowing: offerings by selling holders and "up to" sizes are news
            "Paycor HCM Reports Commencement Of Public Offering Of 8M Shares Of Common Stock By Selling Stockholders",
            "Nauticus Robotics May Now Offer & Sell Shares Of Common Stock Offering Price Of Up To $8.4M",
        ]
        for h in moving:
            with self.subTest(h=h):
                self.assertTrue(sig.is_movement_headline(h))
        for h in not_moving:
            with self.subTest(h=h):
                self.assertFalse(sig.is_movement_headline(h))

    def test_instrument_filter_and_company_names(self):
        self.assertTrue(sig.is_primary_operating_company("AAPL", "Apple Inc. Common Stock", "NASDAQ"))
        self.assertFalse(sig.is_primary_operating_company("SPY", "SPDR S&P 500 ETF Trust", "ARCA"))
        self.assertFalse(sig.is_primary_operating_company("BRK.WS", "Something Corp", "NYSE"))
        self.assertFalse(sig.is_primary_operating_company("XYZW", "Xyz Acquisition Corp. Warrant", "NASDAQ"))
        self.assertFalse(sig.is_primary_operating_company("ABC", "ABC Holdings Units", "NASDAQ"))
        self.assertFalse(sig.is_primary_operating_company("BABA", "Alibaba Group Holding Limited American Depositary Shares", "NYSE"))
        self.assertFalse(sig.is_primary_operating_company("OTCX", "Otc Company Inc", "OTC"))
        cases = {
            "Apple Inc. Common Stock": "Apple Inc.",
            "Alphabet Inc. Class A Common Stock": "Alphabet Inc.",
            "Tesla, Inc. Common Stock": "Tesla, Inc.",
            "Descartes Systems Group Inc. (The) Common Stock": "Descartes Systems Group Inc.",
            "XYZ Inc. Common Stock (DE)": "XYZ Inc.",
            "Fox Corporation Class A Common Stock": "Fox Corporation",
            "DTE Energy Company": "DTE Energy Company",
            "Stock Yards Bancorp, Inc. Common Stock": "Stock Yards Bancorp, Inc.",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(sig.clean_company_name(raw), expected)


class Novelty(unittest.TestCase):
    def test_duplicate_within_24h_for_the_same_symbol_only(self):
        tr = sig.DuplicateTracker()
        t0 = utc("2022-05-02T12:00:00Z")
        n = sig.normalize_headline("Acme Wins Contract")
        self.assertFalse(tr.seen_recently("ACME", t0, n))
        tr.record(["ACME", "OTHR"], t0, n)
        self.assertTrue(tr.seen_recently("ACME", t0 + timedelta(hours=23, minutes=59), n))
        self.assertTrue(tr.seen_recently("OTHR", t0 + timedelta(hours=1), n))  # multi-symbol articles count
        self.assertFalse(tr.seen_recently("ZZZ", t0 + timedelta(hours=1), n))
        self.assertFalse(tr.seen_recently("ACME", t0 + timedelta(hours=1), sig.normalize_headline("Acme Loses Contract")))
        self.assertFalse(tr.seen_recently("ACME", t0 + timedelta(hours=24, seconds=1), n))
        tr.record(["ACME"], t0, n)
        tr.prune_all(t0 + timedelta(days=2))
        self.assertEqual(tr._by_symbol, {})

    def test_first_per_window_keeps_earliest_release_then_lowest_id(self):
        evs = [
            {"symbol": "A", "session": "2022-05-02", "window": "overnight", "created_at": "2022-05-02T11:00:00Z", "news_id": "20"},
            {"symbol": "A", "session": "2022-05-02", "window": "overnight", "created_at": "2022-05-01T22:00:00Z", "news_id": "30"},
            {"symbol": "A", "session": "2022-05-02", "window": "overnight", "created_at": "2022-05-01T22:00:00Z", "news_id": "9"},
            {"symbol": "A", "session": "2022-05-02", "window": "rth", "created_at": "2022-05-02T15:00:00Z", "news_id": "40"},
            {"symbol": "B", "session": "2022-05-02", "window": "overnight", "created_at": "2022-05-02T12:00:00Z", "news_id": "50"},
        ]
        kept = sig.first_per_window(evs)
        self.assertEqual(sorted(e["news_id"] for e in kept), ["40", "50", "9"])


class LanesPricesCosts(unittest.TestCase):
    def test_lane_rules(self):
        self.assertEqual(sig.lane_for(5.0, 20e6, True), sig.LIQUID)
        self.assertEqual(sig.lane_for(4.99, 50e6, True), sig.SMALL)
        self.assertEqual(sig.lane_for(20.0, 19.9e6, True), sig.SMALL)
        self.assertEqual(sig.lane_for(1.0, 2e6, True), sig.SMALL)
        self.assertIsNone(sig.lane_for(0.99, 50e6, True))
        self.assertIsNone(sig.lane_for(10.0, 1.9e6, True))
        self.assertIsNone(sig.lane_for(10.0, 50e6, False))
        self.assertIsNone(sig.lane_for(None, 50e6, True))

    def test_auction_price_selection(self):
        opens = [
            {"c": "Q", "p": 139.12, "t": "2022-10-12T13:30:00.18Z", "x": "P"},
            {"c": "O", "p": 138.99, "t": "2022-10-12T13:30:01.47Z", "x": "Q"},
            {"c": "Q", "p": 138.99, "t": "2022-10-12T13:30:01.48Z", "x": "Q"},
        ]
        self.assertEqual(sig.select_auction_price(opens, "open", "NASDAQ"), (138.99, "O", "Q"))
        # older SIP data tags Nasdaq auction prints "T"
        self.assertEqual(sig.select_auction_price([{"c": "O", "p": 20.0, "x": "T"}], "open", "NASDAQ"), (20.0, "O", "T"))
        # listing changed since the event: the only non-Arca print wins over Arca's own auction
        mixed = [{"c": "O", "p": 30.0, "x": "N"}, {"c": "O", "p": 30.2, "x": "P"}, {"c": "Q", "p": 30.1, "x": "Q"}]
        self.assertEqual(sig.select_auction_price(mixed, "open", "NASDAQ"), (30.0, "O", "N"))
        # two non-Arca prints and none at the listing venue: fall back to the official price there
        two = [{"c": "6", "p": 10.0, "x": "N"}, {"c": "6", "p": 10.1, "x": "A"}, {"c": "M", "p": 10.05, "x": "Q"}]
        self.assertEqual(sig.select_auction_price(two, "close", "NASDAQ"), (10.05, "M", "Q"))
        self.assertIsNone(sig.select_auction_price(two[:2], "close", "NASDAQ"))
        # only Arca printed: accepted as the single print
        self.assertEqual(sig.select_auction_price([{"c": "6", "p": 5.0, "x": "P"}], "close", "NYSE"), (5.0, "6", "P"))
        closes = [{"c": "M", "p": 142.94, "t": "2022-10-13T20:00:00.17Z", "x": "P"}]
        self.assertIsNone(sig.select_auction_price(closes, "close", "NASDAQ"))
        self.assertIsNone(sig.select_auction_price([{"c": "O", "p": 0, "x": "Q"}], "open", "NASDAQ"))
        self.assertIsNone(sig.select_auction_price([], "open", "NASDAQ"))

    def test_half_spread(self):
        self.assertAlmostEqual(sig.half_spread_fraction({"bp": 99.0, "ap": 101.0}), 0.01)
        self.assertIsNone(sig.half_spread_fraction({"bp": 0, "ap": 101.0}))
        self.assertIsNone(sig.half_spread_fraction({"bp": 101.0, "ap": 100.0}))
        self.assertIsNone(sig.half_spread_fraction({"bp": None, "ap": 100.0}))

    def fees(self):
        return json.loads((ROOT / "blueprints/us-equities/mover-v3/data/fees-v3.json").read_text())

    def test_fees_on_the_sale_leg(self):
        fees = self.fees()
        # 2024-06-03: SEC 27.8 $/M; TAF 0.000166 $/sh capped at 8.30
        usd = sig.sale_fees_usd(fees, date(2024, 6, 3), 100, 50.0)
        self.assertAlmostEqual(usd, 5000 * 27.8 / 1e6 + 100 * 0.000166)
        # TAF cap binds for a large share count
        usd = sig.sale_fees_usd(fees, date(2024, 6, 3), 1_000_000, 1.0)
        self.assertAlmostEqual(usd, 1_000_000 * 27.8 / 1e6 + 8.30)
        # before the first SEC row the earliest row applies (protocol costs.fees.before_first_row)
        self.assertAlmostEqual(sig.sale_fees_usd(fees, date(2016, 2, 2), 0, 10.0), 0.0)

    def test_position_net_return(self):
        fees = self.fees()
        day = date(2024, 6, 3)
        gross_long = sig.gross_return(1, 100.0, 101.0)
        self.assertAlmostEqual(gross_long, 0.01)
        net = sig.position_net_return(1, 100.0, 101.0, day, fees, 10_000, 0.0002, 0.0002)
        entry, exit_ = 100.0 * 1.0002, 101.0 * 0.9998
        shares = 10_000 / entry
        expected = (shares * (exit_ - entry) - sig.sale_fees_usd(fees, day, shares, exit_)) / 10_000
        self.assertAlmostEqual(net, expected)
        self.assertLess(net, gross_long)
        net_short = sig.position_net_return(-1, 100.0, 99.0, day, fees, 10_000, 0.0002, 0.0002)
        entry_s, exit_s = 100.0 * 0.9998, 99.0 * 1.0002
        shares_s = 10_000 / entry_s
        expected_s = (shares_s * (entry_s - exit_s) - sig.sale_fees_usd(fees, day, shares_s, entry_s)) / 10_000
        self.assertAlmostEqual(net_short, expected_s)
        with self.assertRaises(ValueError):
            sig.position_net_return(0, 1, 1, day, fees, 1, 0, 0)


class PortfoliosAndStats(unittest.TestCase):
    def test_min_two_names_per_leg(self):
        pos = [
            {"session": "d1", "side": 1, "ret": 0.01}, {"session": "d1", "side": 1, "ret": 0.03},
            {"session": "d1", "side": -1, "ret": 0.02}, {"session": "d1", "side": -1, "ret": 0.00},
            {"session": "d2", "side": 1, "ret": 0.05}, {"session": "d2", "side": -1, "ret": 0.01},
            {"session": "d2", "side": -1, "ret": 0.03},
            {"session": "d3", "side": 1, "ret": 0.05},
        ]
        out = sig.daily_portfolios(pos)
        self.assertAlmostEqual(out["d1"]["long"], 0.02)
        self.assertAlmostEqual(out["d1"]["short"], 0.01)
        self.assertAlmostEqual(out["d1"]["long_short"], 0.03)
        self.assertAlmostEqual(out["d1"]["long_short_paper"], 0.03)
        self.assertFalse(out["d1"]["single_leg"])
        # confirmatory long-short needs both legs; the paper's single-leg version is kept
        self.assertIsNone(out["d2"]["long"])
        self.assertIsNone(out["d2"]["long_short"])
        self.assertAlmostEqual(out["d2"]["long_short_paper"], 0.02)
        self.assertTrue(out["d2"]["single_leg"])
        self.assertIsNone(out["d3"]["long_short"])
        self.assertIsNone(out["d3"]["long_short_paper"])
        self.assertFalse(out["d3"]["single_leg"])

    def test_fixed_sequence_and_holm_reject(self):
        self.assertEqual(sig.fixed_sequence([("A", 0.01), ("B", 0.04)], 0.05), {"A": True, "B": True})
        self.assertEqual(sig.fixed_sequence([("A", 0.06), ("B", 0.001)], 0.05), {"A": False, "B": False})
        self.assertEqual(sig.fixed_sequence([("A", None), ("B", 0.001)], 0.05), {"A": False, "B": False})
        self.assertEqual(sig.holm_reject({"a": 0.01, "b": 0.02, "c": 0.04}, 0.05), {"a": True, "b": True, "c": True})
        self.assertEqual(sig.holm_reject({"a": 0.01, "b": 0.03, "c": 0.04}, 0.05), {"a": True, "b": False, "c": False})

    def test_newey_west_zero_lag_equals_plain_t(self):
        x = [0.01, -0.02, 0.03, 0.0, 0.02, -0.01]
        t, se = sig.newey_west_t(x, 0)
        mu = sum(x) / len(x)
        var = sum((v - mu) ** 2 for v in x) / len(x)
        self.assertAlmostEqual(se, math.sqrt(var / len(x)))
        self.assertAlmostEqual(t, mu / se)
        self.assertTrue(math.isnan(sig.newey_west_t([1.0], 5)[0]))
        self.assertAlmostEqual(sig.normal_sf(0.0), 0.5)
        self.assertAlmostEqual(sig.normal_sf(1.6448536), 0.05, places=6)

    def test_holm(self):
        adj = sig.holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": None})
        self.assertAlmostEqual(adj["a"], 0.04)
        self.assertAlmostEqual(adj["c"], 0.09)
        self.assertAlmostEqual(adj["b"], 0.09)
        self.assertEqual(adj["d"], 1.0)


if __name__ == "__main__":
    unittest.main()
