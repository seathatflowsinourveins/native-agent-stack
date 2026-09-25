"""SYN: evaluate.py refusal guard and synthetic end-to-end evaluation.

No real data: every price, score and event below is synthetic. The guard must refuse
before any data file is opened unless the protocol is frozen and its sha256 matches.
"""

import copy
import gzip
import hashlib
import importlib.util
import io
import json
import math
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/us-equities/sota-mover/news-llm"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ev_mod = load("news_llm_evaluate_under_test", "evaluate.py")
sig = ev_mod.sig
FEES = json.loads((ROOT / "blueprints/us-equities/mover-v3/data/fees-v3.json").read_text())
DRAFT = json.loads((BLUEPRINT / "protocol.json").read_text())
TEMPLATE = "t" * 64


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_protocol(directory, protocol):
    raw = json.dumps(protocol, indent=1).encode()
    path = Path(directory) / "protocol.json"
    path.write_bytes(raw)
    return path, sha(raw)


def frozen(protocol=None, **overrides):
    p = copy.deepcopy(protocol or DRAFT)
    p["status"] = "frozen"
    p["frozen_before_outcomes"] = True
    p["scoring"]["template_sha256"] = TEMPLATE
    p.update(overrides)
    return p


class ProtocolConsistency(unittest.TestCase):
    def test_draft_matches_code_and_pins(self):
        p = DRAFT
        self.assertEqual(p["status"], "draft_pending_independent_pre_outcome_review")
        self.assertIs(p["frozen_before_outcomes"], False)
        self.assertEqual(p["scoring"]["operative_variant"], sig.OPERATIVE_VARIANT)
        self.assertEqual(p["scoring"]["template_sha256"], sig.template_sha256(sig.OPERATIVE_VARIANT))
        pins = json.loads((BLUEPRINT / "checkpoints.json").read_text())
        self.assertEqual(p["models"]["revisions"], {y: e["revision"] for y, e in pins["checkpoints"].items()})
        self.assertEqual(p["models"]["code_sha256"], pins["reviewed_code"]["sha256"])
        self.assertEqual(p["models"]["pins_file_sha256"], sha((BLUEPRINT / "checkpoints.json").read_bytes()))
        self.assertEqual(p["costs"]["fees"]["sha256"], sha((ROOT / p["costs"]["fees"]["file"]).read_bytes()))
        cal = ROOT / "blueprints/us-equities/mover-v3/data/session-calendar.json"
        self.assertIn(sha(cal.read_bytes()), p["timing"]["calendar"])
        self.assertEqual(len(p["items"]), 4)
        for item in p["items"]:
            self.assertIn(item["segment"], p["segments"])
            self.assertIn(item["leg"], ("long", "short", "long_short"))
        self.assertTrue(all(v is None for v in p["frozen_inputs"].values()))


class RefusalGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_committed_draft_is_refused_even_with_its_own_sha(self):
        raw = (BLUEPRINT / "protocol.json").read_bytes()
        with self.assertRaises(SystemExit) as ctx:
            ev_mod.check_protocol(BLUEPRINT / "protocol.json", sha(raw))
        self.assertIn("refusing", str(ctx.exception))
        self.assertEqual(json.loads(raw)["status"], "draft_pending_independent_pre_outcome_review")
        self.assertIs(json.loads(raw)["frozen_before_outcomes"], False)

    def test_frozen_but_wrong_sha_is_refused(self):
        path, digest = write_protocol(self.dir, frozen())
        with self.assertRaises(SystemExit):
            ev_mod.check_protocol(path, "0" * 64)
        with self.assertRaises(SystemExit):
            ev_mod.check_protocol(path, "")
        with self.assertRaises(SystemExit):
            ev_mod.check_protocol(path, digest[:63])
        self.assertEqual(ev_mod.check_protocol(path, digest.upper())["status"], "frozen")

    def test_status_or_flag_alone_is_not_enough(self):
        p = frozen()
        p["frozen_before_outcomes"] = False
        path, digest = write_protocol(self.dir, p)
        with self.assertRaises(SystemExit):
            ev_mod.check_protocol(path, digest)
        p = frozen(status="draft")
        path, digest = write_protocol(self.dir, p)
        with self.assertRaises(SystemExit):
            ev_mod.check_protocol(path, digest)

    def test_main_refuses_before_reading_any_data(self):
        path, digest = write_protocol(self.dir, DRAFT)
        missing_root = self.dir / "does-not-exist"
        with self.assertRaises(SystemExit) as ctx:
            ev_mod.main(["--protocol", str(path), "--protocol-sha256", digest, "--data-root", str(missing_root)])
        self.assertIn("refusing", str(ctx.exception))

    def test_frozen_inputs_must_be_pinned_and_unchanged(self):
        root = self.dir / "data"
        root.mkdir()
        (root / "a.bin").write_bytes(b"abc")
        p = frozen(frozen_inputs={"a.bin": None})
        with self.assertRaises(SystemExit):
            ev_mod.check_inputs(p, root)
        p = frozen(frozen_inputs={"a.bin": sha(b"xyz")})
        with self.assertRaises(SystemExit):
            ev_mod.check_inputs(p, root)
        p = frozen(frozen_inputs={"missing.bin": sha(b"abc")})
        with self.assertRaises(SystemExit):
            ev_mod.check_inputs(p, root)
        ev_mod.check_inputs(frozen(frozen_inputs={"a.bin": sha(b"abc")}), root)


def synthetic_world(n_days=30, start=date(2023, 3, 1)):
    """Overnight liquid events on n_days sessions: 3 positives up 1%, 2 negatives down 1%."""
    events, scores, opens, closes = [], {}, {}, {}
    d = start
    days = 0
    while days < n_days:
        if d.weekday() < 5:
            days += 1
            for k, (label, move) in enumerate((("YES", 0.01), ("YES", 0.01), ("YES", 0.01), ("NO", -0.01), ("NO", -0.01), ("UNKNOWN", 0.05))):
                sym = f"S{k}"
                eid = f"{d.isoformat()}{k}:{sym}"
                events.append({"event_id": eid, "symbol": sym, "session": d.isoformat(), "window": "overnight",
                               "lane": "liquid", "exchange": "NYSE", "entry_utc": f"{d.isoformat()}T14:30:00Z"})
                scores[eid] = {"event_id": eid, "label": label, "score": sig.YES_NO_LABELS[label],
                               "template_sha256": TEMPLATE}
                opens[(sym, d.isoformat())] = 100.0
                closes[(sym, d.isoformat())] = 100.0 * (1 + move)
        d += timedelta(days=1)
    return events, scores, opens, closes


COSTS = DRAFT["costs"]


class PureEvaluation(unittest.TestCase):
    def test_build_positions_signs_costs_and_exclusions(self):
        events, scores, opens, closes = synthetic_world(n_days=2)
        del closes[("S0", events[0]["session"])]  # missing exit
        scores[events[1]["event_id"]]["template_sha256"] = "x" * 64  # foreign template
        del scores[events[2]["event_id"]]  # never scored
        positions, excluded = ev_mod.build_positions(events, scores, opens, closes, {}, lambda ev: 0.0, FEES, COSTS,
                                                     expected_template=TEMPLATE)
        self.assertEqual(excluded["missing_exit_overnight"], 1)
        self.assertEqual(excluded["template_mismatch"], 1)
        self.assertEqual(excluded["no_score"], 1)
        self.assertEqual(excluded["no_position_UNKNOWN"], 2)
        longs = [p for p in positions if p["side"] == 1]
        shorts = [p for p in positions if p["side"] == -1]
        self.assertTrue(all(abs(p["gross"] - 0.01) < 1e-12 for p in longs + shorts))
        for p in longs + shorts:
            self.assertLess(p["net"], p["gross"])
            self.assertGreater(p["cost"], 2 * COSTS["auction_slippage_bps_per_side"]["liquid"] / 1e4 * 0.99)

    def test_rth_uses_minute_entry_and_half_spread(self):
        ev = {"event_id": "1:A", "symbol": "A", "session": "2023-03-01", "window": "rth", "lane": "liquid",
              "exchange": "NASDAQ", "entry_utc": "2023-03-01T15:00:00Z"}
        scores = {"1:A": {"label": "YES", "score": 1, "template_sha256": TEMPLATE}}
        closes = {("A", "2023-03-01"): 101.0}
        positions, excluded = ev_mod.build_positions([ev], scores, {}, closes, {}, lambda e: 0.001, FEES, COSTS)
        self.assertEqual(excluded["missing_entry_rth"], 1)
        positions, _ = ev_mod.build_positions([ev], scores, {}, closes, {"1:A": 100.0}, lambda e: 0.001, FEES, COSTS)
        p = positions[0]
        expected_entry_cost = 0.001 + COSTS["rth_entry_allowance_bps"] / 1e4
        net = sig.position_net_return(1, 100.0, 101.0, date(2023, 3, 1), FEES, COSTS["notional_usd"], expected_entry_cost,
                                      COSTS["auction_slippage_bps_per_side"]["liquid"] / 1e4)
        self.assertAlmostEqual(p["net"], net)

    def test_items_holm_and_gates(self):
        events, scores, opens, closes = synthetic_world(n_days=30)
        positions, _ = ev_mod.build_positions(events, scores, opens, closes, {}, lambda ev: 0.0, FEES, COSTS)
        protocol = frozen()
        for item in protocol["items"]:
            item["min_days"] = 10
        protocol["segments"]["overnight_full"] = {"first_session": "2023-01-01", "last_session": "2023-12-31"}
        protocol["segments"]["recent_24m"] = {"first_session": "2023-03-10", "last_session": "2023-12-31"}
        results = ev_mod.evaluate_items(protocol, positions)
        # constant positive daily returns: zero variance gives no t statistic, so no pass
        self.assertEqual(results["NEWS-3"]["verdict"], "insufficient_sample")
        for key in ("NEWS-1", "NEWS-2", "NEWS-4"):
            self.assertIn(results[key]["verdict"], ("fail", "pass"))
            self.assertGreater(results[key]["mean"], 0)

    def test_items_pass_with_noisy_positive_series_and_fail_when_negative(self):
        protocol = frozen()
        for item in protocol["items"]:
            item["min_days"] = 50
        protocol["segments"]["overnight_full"] = {"first_session": "2000-01-01", "last_session": "2099-12-31"}
        protocol["segments"]["recent_24m"] = protocol["segments"]["overnight_full"]

        def world(mean):
            positions = []
            for i in range(200):
                day = (date(2020, 1, 1) + timedelta(days=i)).isoformat()
                noise = 0.004 * math.sin(i * 1.7)
                for side in (1, 1, -1, -1):
                    positions.append({"session": day, "side": side, "window": "overnight", "lane": "liquid",
                                      "net": mean + noise, "gross": mean + noise, "cost": 0.0})
            return positions

        good = ev_mod.evaluate_items(protocol, world(0.002))
        self.assertEqual(good["NEWS-1"]["verdict"], "pass")
        self.assertEqual(good["NEWS-2"]["verdict"], "pass")
        self.assertLessEqual(good["NEWS-1"]["p_one_sided"], good["NEWS-1"]["p_holm"])
        bad = ev_mod.evaluate_items(protocol, world(-0.002))
        self.assertEqual(bad["NEWS-1"]["verdict"], "fail")

    def test_break_even_round_trip(self):
        daily = {"2023-01-02": {"long": 0.002, "short": 0.001, "long_short": 0.003},
                 "2023-01-03": {"long": 0.001, "short": None, "long_short": 0.001}}
        seg = {"first_session": "2023-01-01", "last_session": "2023-12-31"}
        self.assertAlmostEqual(ev_mod.break_even_round_trip(daily, seg), 0.002 / 1.5)

    def test_spread_lookup_fallbacks(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "quotes.jsonl"
        rows = [
            {"event_id": "e1", "quotes": [{"bp": 0, "ap": 10}, {"bp": 9.9, "ap": 10.1}]},
            {"event_id": "e2", "quotes": [{"bp": 19.8, "ap": 20.2}]},
            {"event_id": "e3", "quotes": []},
        ]
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        events = [
            {"event_id": "e1", "symbol": "A", "session": "2023-05-01"},
            {"event_id": "e2", "symbol": "B", "session": "2023-05-01"},
            {"event_id": "e3", "symbol": "A", "session": "2023-06-01"},
            {"event_id": "e4", "symbol": "C", "session": "2024-06-01"},
        ]
        lookup = ev_mod.spread_lookup_factory(str(path), events, 5.0)
        self.assertAlmostEqual(lookup(events[0]), 0.01)
        self.assertAlmostEqual(lookup(events[1]), 0.01)
        self.assertAlmostEqual(lookup(events[2]), 0.01)  # symbol-year median
        self.assertAlmostEqual(lookup(events[3]), 0.01)  # all-events median
        empty = ev_mod.spread_lookup_factory(str(Path(tmp.name) / "none.jsonl"), events, 5.0)
        self.assertAlmostEqual(empty(events[3]), 0.0005)


@unittest.skipUnless(importlib.util.find_spec("duckdb"), "duckdb not installed (run under the data runtime)")
class RthMinuteLoader(unittest.TestCase):
    def test_first_bar_at_or_after_entry_within_five_minutes(self):
        import duckdb

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name) / "symbol=AAA" / "year=2023"
        d.mkdir(parents=True)
        con = duckdb.connect()
        con.execute("""CREATE TABLE b AS SELECT * FROM (VALUES
            ('AAA', DATE '2023-03-01', 614::SMALLINT, 49.0),
            ('AAA', DATE '2023-03-01', 616::SMALLINT, 50.0),
            ('AAA', DATE '2023-03-02', 600::SMALLINT, 60.0)) t(symbol, et_date, et_minute, o)""")
        con.execute(f"COPY b TO '{d / 'full.parquet'}' (FORMAT parquet)")
        events = [
            {"event_id": "1:AAA", "symbol": "AAA", "window": "rth", "entry_utc": "2023-03-01T15:15:00Z"},  # 615 missing -> 616
            {"event_id": "2:AAA", "symbol": "AAA", "window": "rth", "entry_utc": "2023-03-02T15:00:00Z"},
            {"event_id": "3:AAA", "symbol": "AAA", "window": "rth", "entry_utc": "2023-03-02T16:00:00Z"},  # no bar in 5 min
            {"event_id": "4:BBB", "symbol": "BBB", "window": "rth", "entry_utc": "2023-03-02T16:00:00Z"},  # no file
            {"event_id": "5:AAA", "symbol": "AAA", "window": "overnight", "entry_utc": "2023-03-02T14:30:00Z"},
        ]
        self.assertEqual(ev_mod.load_rth_entries(events, tmp.name), {"1:AAA": 50.0, "2:AAA": 60.0})


class EndToEnd(unittest.TestCase):
    def test_main_on_a_synthetic_frozen_study(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "data"
        (root / "scores").mkdir(parents=True)
        (root / "auctions").mkdir()
        (root / "spreads").mkdir()
        events, scores, opens, closes = synthetic_world(n_days=12)
        with gzip.open(root / "events.jsonl.gz", "wt") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")
        (root / "scores/scores-20221231.jsonl").write_text("\n".join(json.dumps(r) for r in scores.values()) + "\n")
        with gzip.open(root / "auctions/auctions.jsonl.gz", "wt") as fh:
            for (sym, day), price in opens.items():
                fh.write(json.dumps({"symbol": sym, "session": day, "o": [{"c": "O", "p": price, "x": "N"}],
                                     "c": [{"c": "6", "p": closes[(sym, day)], "x": "N"}]}) + "\n")
        (root / "spreads/quotes.jsonl").write_text("")
        pins = {rel: sha((root / rel).read_bytes()) for rel in
                ("events.jsonl.gz", "scores/scores-20221231.jsonl", "auctions/auctions.jsonl.gz", "spreads/quotes.jsonl")}
        protocol = frozen(frozen_inputs=pins)
        for item in protocol["items"]:
            item["min_days"] = 5
        path, digest = write_protocol(Path(tmp.name), protocol)
        out = Path(tmp.name) / "results.json"
        with redirect_stdout(io.StringIO()):
            ev_mod.main(["--protocol", str(path), "--protocol-sha256", digest, "--data-root", str(root),
                         "--minute-root", str(Path(tmp.name) / "no-minutes"), "--out", str(out)])
        results = json.loads(out.read_text())
        self.assertEqual(results["positions"], 12 * 5)
        self.assertEqual(results["excluded"], {"no_position_UNKNOWN": 12})
        block = results["descriptive"]["overnight:liquid"]["overnight_full"]
        self.assertAlmostEqual(block["gross_long_short"]["mean"], 0.02)
        self.assertLess(block["net_long_short"]["mean"], 0.02)
        self.assertAlmostEqual(block["break_even_round_trip"], 0.01)
        self.assertIn("NEWS-1", results["items"])


if __name__ == "__main__":
    unittest.main()
