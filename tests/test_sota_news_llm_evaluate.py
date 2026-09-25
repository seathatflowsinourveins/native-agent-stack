"""SYN: evaluate.py guard, score checks, pricing, multiplicity, gates and a full guarded run.

No real data: every event, score, quote and price below is synthetic. The guard follows
the EAP standard: freeze record, frozen protocol, sha pins, clean tree, freeze commit an
ancestor of HEAD, and a guard token checked inside every loader.
"""

import copy
import gzip
import hashlib
import importlib.util
import io
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from tests import hermetic_git_environment

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/us-equities/sota-mover/news-llm"
STUDY_REL = "blueprints/us-equities/sota-mover/news-llm"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ev_mod = load("news_llm_evaluate_under_test", "evaluate.py")
sig = ev_mod.sig
FEES = json.loads((ROOT / "blueprints/us-equities/mover-v3/data/fees-v3.json").read_text())
PINS = json.loads((BLUEPRINT / "checkpoints.json").read_text())
DRAFT = json.loads((BLUEPRINT / "protocol.json").read_text())
COSTS = DRAFT["costs"]
SETTINGS = DRAFT["scoring"]["pinned_settings"]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def frozen_protocol(**overrides):
    p = copy.deepcopy(DRAFT)
    p.update(status="frozen_pre_outcome", frozen_before_outcomes=True, frozen_at="2026-09-26T00:00:00Z")
    p.update(overrides)
    return p


def write_protocol(directory, protocol):
    raw = json.dumps(protocol, indent=1).encode()
    path = Path(directory) / "protocol.json"
    path.write_bytes(raw)
    return path, sha(raw)


def make_event(eid, sym, session, window="overnight", lane="liquid", created=None, **extra):
    created = created or f"{session}T12:00:00Z"
    ev = {"event_id": f"{eid}:{sym}", "news_id": str(eid), "symbol": sym, "session": session, "window": window, "lane": lane,
          "exchange": "NYSE", "company": f"{sym} Corp.", "headline": f"{sym} headline {eid}", "created_at": created,
          "entry_utc": f"{session}T14:30:00Z" if window == "overnight" else f"{session}T16:00:00Z",
          "prior_close": 100.0, "ssr_carryover": False, "checkpoint_year": sig.checkpoint_year(created)}
    ev.update(extra)
    return ev


def make_row(ev, label):
    year = sig.checkpoint_year(ev["created_at"])
    entry = PINS["checkpoints"][str(year)]
    labels = sig.VARIANTS[SETTINGS["variant"]]["labels"]
    return {"event_id": ev["event_id"], "checkpoint_year": year, "revision": entry["revision"],
            "weights_sha256": entry["files"]["pytorch_model.bin"]["sha256"], "code_sha256": PINS["reviewed_code"]["sha256"],
            "variant": SETTINGS["variant"], "template_sha256": SETTINGS["template_sha256"], "dtype": SETTINGS["dtype"],
            "matmul": SETTINGS["matmul"], "decoder": SETTINGS["decoder"],
            "prompt_sha256": sig.sha256_text(sig.model_input(ev["company"], ev["headline"], SETTINGS["variant"])),
            "raw_output": label, "stop": "eos", "label": label, "score": labels.get(label, 0)}


class ProtocolConsistency(unittest.TestCase):
    def test_draft_matches_code_and_pins(self):
        p = DRAFT
        self.assertEqual(p["status"], "draft_pending_independent_pre_outcome_review")
        self.assertIs(p["frozen_before_outcomes"], False)
        self.assertEqual(p["frozen_status_value"], ev_mod.FROZEN_STATUS)
        self.assertEqual(p["scoring"]["operative_variant"], sig.OPERATIVE_VARIANT)
        self.assertEqual(SETTINGS["variant"], sig.OPERATIVE_VARIANT)
        self.assertEqual(SETTINGS["template_sha256"], sig.template_sha256(sig.OPERATIVE_VARIANT))
        self.assertEqual(p["scoring"]["template_sha256"], SETTINGS["template_sha256"])
        self.assertEqual(p["models"]["revisions"], {y: e["revision"] for y, e in PINS["checkpoints"].items()})
        self.assertEqual(p["models"]["code_sha256"], PINS["reviewed_code"]["sha256"])
        self.assertEqual(set(p["pins"]["code"]), set(ev_mod.CODE_PINS))
        self.assertEqual(set(p["pins"]["reference"]), set(ev_mod.REFERENCE_PINS))
        self.assertEqual(set(p["pins"]["private_inputs"]), set(ev_mod.PRIVATE_INPUTS))
        for name, rel in ev_mod.REFERENCE_PINS.items():
            self.assertEqual(p["pins"]["reference"][name], sha((ROOT / rel).read_bytes()), name)
        ids = {i["id"] for i in p["items"]}
        self.assertEqual(ids, {"NEWS-1", "NEWS-2", "NEWS-2B", "NEWS-3", "NEWS-4"})
        for item in p["items"]:
            self.assertIn(item["segment"], p["segments"])
            self.assertIn(item["series"], ("long", "long_short", "long_bench"))
        m = p["multiplicity"]
        self.assertEqual(m["primary"]["items"], ["NEWS-1", "NEWS-4"])
        self.assertEqual(m["secondary"]["items"], ["NEWS-1", "NEWS-2B", "NEWS-3"])
        self.assertAlmostEqual(m["gatekeeping"]["alpha"], 0.05 / 3)
        self.assertIn("2026-09-21 asset master", p["scope"])


class GuardRefusals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def record(self, **fields):
        path = self.dir / "freeze-record.json"
        path.write_text(json.dumps(fields))
        return path

    def test_freeze_record_is_required_and_complete(self):
        with self.assertRaises(ev_mod.Refusal):
            ev_mod.read_freeze_record(self.dir / "missing.json")
        bad = self.dir / "bad.json"
        bad.write_text("{not json")
        with self.assertRaises(ev_mod.Refusal):
            ev_mod.read_freeze_record(bad)
        with self.assertRaises(ev_mod.Refusal):
            ev_mod.read_freeze_record(self.record(protocol_sha256=None, protocol_commit="a" * 40))
        with self.assertRaises(ev_mod.Refusal):
            ev_mod.read_freeze_record(self.record(protocol_sha256="a" * 64, protocol_commit="abc"))
        self.assertEqual(ev_mod.read_freeze_record(self.record(protocol_sha256="A" * 64, protocol_commit="b" * 40)),
                         ("a" * 64, "b" * 40))

    def test_template_is_not_a_valid_record(self):
        with self.assertRaises(ev_mod.Refusal):
            ev_mod.read_freeze_record(BLUEPRINT / "receipts" / "freeze-record.template.json")

    def test_committed_draft_is_refused_even_with_its_own_sha(self):
        raw = (BLUEPRINT / "protocol.json").read_bytes()
        with self.assertRaises(ev_mod.Refusal) as ctx:
            ev_mod.guard(BLUEPRINT / "protocol.json", sha(raw))
        self.assertIn("not frozen", ctx.exception.reason)

    def test_guard_needs_matching_sha_and_every_freeze_field(self):
        path, digest = write_protocol(self.dir, frozen_protocol())
        with self.assertRaises(ev_mod.Refusal):
            ev_mod.guard(path, "0" * 64)
        with self.assertRaises(ev_mod.Refusal):
            ev_mod.guard(path, None)
        self.assertIsInstance(ev_mod.guard(path, digest.upper()), ev_mod.FrozenProtocol)
        for field, value in (("frozen_before_outcomes", False), ("frozen_at", None), ("status", "frozen")):
            p = frozen_protocol(**{field: value})
            path, digest = write_protocol(self.dir, p)
            with self.assertRaises(ev_mod.Refusal, msg=field):
                ev_mod.guard(path, digest)

    def test_token_cannot_be_forged_and_every_loader_checks_it(self):
        with self.assertRaises(ev_mod.Refusal):
            ev_mod.FrozenProtocol({}, "a" * 64, "p", object())
        fake = SimpleNamespace(protocol={}, sha256="a" * 64, path=self.dir / "protocol.json", _token=object())
        loaders = [
            lambda f: ev_mod.load_events(f, self.dir),
            lambda f: ev_mod.load_score_rows(f, self.dir),
            lambda f: ev_mod.load_auction_prices(f, self.dir / "a.jsonl.gz", []),
            lambda f: ev_mod.load_rth_quotes(f, self.dir / "q.jsonl", []),
            lambda f: ev_mod.data_pass(SimpleNamespace(data_root=self.dir), f),
        ]
        for loader in loaders:
            for bad in (None, fake):
                with self.assertRaises(ev_mod.Refusal):
                    loader(bad)

    def test_loaders_refuse_after_the_protocol_changes(self):
        path, digest = write_protocol(self.dir, frozen_protocol())
        frozen = ev_mod.guard(path, digest)
        (self.dir / "q.jsonl").write_text("")
        self.assertEqual(ev_mod.load_rth_quotes(frozen, self.dir / "q.jsonl", []), {})
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(ev_mod.Refusal):
            ev_mod.load_rth_quotes(frozen, self.dir / "q.jsonl", [])

    def test_pins_missing_absent_or_changed_are_refused(self):
        data = self.dir / "data"
        (data / "scores").mkdir(parents=True)
        (data / "auctions").mkdir()
        (data / "spreads").mkdir()
        for rel in ev_mod.PRIVATE_INPUTS:
            (data / rel).write_bytes(rel.encode())
        pins = ev_mod.compute_pins(BLUEPRINT, data, ROOT)
        ev_mod.verify_pins({"pins": pins}, BLUEPRINT, data, ROOT)
        broken = copy.deepcopy(pins)
        broken["code"]["news_signal.py"] = None
        with self.assertRaises(ev_mod.Refusal):
            ev_mod.verify_pins({"pins": broken}, BLUEPRINT, data, ROOT)
        broken = copy.deepcopy(pins)
        broken["private_inputs"]["events.jsonl.gz"] = "0" * 64
        with self.assertRaises(ev_mod.Refusal):
            ev_mod.verify_pins({"pins": broken}, BLUEPRINT, data, ROOT)
        (data / "spreads" / "quotes.jsonl").unlink()
        with self.assertRaises(ev_mod.Refusal):
            ev_mod.verify_pins({"pins": pins}, BLUEPRINT, data, ROOT)


class ScoreChecks(unittest.TestCase):
    def setUp(self):
        self.events = [make_event(1, "A", "2023-03-01"), make_event(2, "B", "2023-03-01", lane="small")]
        self.rows = {self.events[0]["event_id"]: [make_row(self.events[0], "FAVORABLE")],
                     self.events[1]["event_id"]: [make_row(self.events[1], "UNFAVORABLE")]}

    def check(self, rows=None, events=None):
        return ev_mod.check_scores(events or self.events, rows if rows is not None else self.rows, DRAFT, PINS)

    def test_valid_rows_pass_and_small_unscored_is_counted(self):
        chosen, notes = self.check()
        self.assertEqual(len(chosen), 2)
        rows = dict(self.rows)
        del rows[self.events[1]["event_id"]]
        chosen, notes = self.check(rows)
        self.assertEqual(notes, {"small_lane_unscored": 1})

    def test_refusals(self):
        e0 = self.events[0]["event_id"]
        cases = {
            "unscored liquid": {k: v for k, v in self.rows.items() if k != e0},
            "duplicate": {**self.rows, e0: self.rows[e0] * 2},
        }
        for field, value in (("checkpoint_year", 2021), ("revision", "0" * 40), ("dtype", "bfloat16"), ("matmul", "tf32"),
                             ("decoder", "full"), ("variant", "llt_alpaca"), ("prompt_sha256", "0" * 64), ("label", "UNFAVORABLE")):
            cases[field] = {**self.rows, e0: [dict(self.rows[e0][0], **{field: value})]}
        for name, rows in cases.items():
            with self.assertRaises(ev_mod.Refusal, msg=name):
                self.check(rows)


def overnight_world(n_days, start=date(2023, 3, 1), long_move=0.01, short_move=-0.01, other_move=0.0, noise=0.0):
    """3 FAVORABLE, 2 UNFAVORABLE and 1 UNCLEAR liquid overnight events per weekday."""
    events, scores, opens, closes = [], {}, {}, {}
    d, days = start, 0
    while days < n_days:
        if d.weekday() < 5:
            wiggle = noise * math.sin(days * 1.7)
            for k, (label, move) in enumerate((("FAVORABLE", long_move), ("FAVORABLE", long_move), ("FAVORABLE", long_move),
                                               ("UNFAVORABLE", short_move), ("UNFAVORABLE", short_move), ("UNCLEAR", other_move))):
                ev = make_event(f"{days}{k}", f"S{k}", d.isoformat())
                events.append(ev)
                scores[ev["event_id"]] = make_row(ev, label)
                opens[(ev["symbol"], ev["session"])] = 100.0
                closes[(ev["symbol"], ev["session"])] = 100.0 * (1 + move + wiggle)
            days += 1
        d += timedelta(days=1)
    return events, scores, opens, closes


class Pricing(unittest.TestCase):
    def test_rth_uses_ask_for_longs_bid_for_shorts_and_ssr_excludes_shorts(self):
        long_ev = make_event(1, "A", "2023-03-01", window="rth")
        short_ev = make_event(2, "B", "2023-03-01", window="rth")
        ssr_ev = make_event(3, "C", "2023-03-01", window="rth")
        carry_ev = make_event(4, "D", "2023-03-01", ssr_carryover=True)
        scores = {long_ev["event_id"]: make_row(long_ev, "FAVORABLE"), short_ev["event_id"]: make_row(short_ev, "UNFAVORABLE"),
                  ssr_ev["event_id"]: make_row(ssr_ev, "UNFAVORABLE"), carry_ev["event_id"]: make_row(carry_ev, "UNFAVORABLE")}
        quotes = {long_ev["event_id"]: {"bid": 99.9, "ask": 100.1, "t": "x"},
                  short_ev["event_id"]: {"bid": 99.9, "ask": 100.1, "t": "x"},
                  ssr_ev["event_id"]: {"bid": 89.0, "ask": 89.2, "t": "x"}}
        closes = {(e["symbol"], "2023-03-01"): 101.0 for e in (long_ev, short_ev, ssr_ev, carry_ev)}
        opens = {("D", "2023-03-01"): 100.0}
        positions, bench, excluded = ev_mod.build_positions([long_ev, short_ev, ssr_ev, carry_ev], scores, opens, closes,
                                                            quotes, FEES, COSTS)
        by = {p["symbol"]: p for p in positions}
        self.assertAlmostEqual(by["A"]["gross"], 101.0 / 100.1 - 1)
        self.assertAlmostEqual(by["B"]["gross"], -(101.0 / 99.9 - 1))
        self.assertTrue(by["C"]["ssr"] and by["D"]["ssr"])
        self.assertFalse(by["A"]["ssr"] or by["B"]["ssr"])
        self.assertEqual((excluded["ssr_short_rth"], excluded["ssr_short_overnight"]), (1, 1))
        expected = sig.position_net_return(1, 100.1, 101.0, date(2023, 3, 1), FEES, COSTS["notional_usd"],
                                           COSTS["rth_entry_allowance_bps"] / 1e4, COSTS["auction_slippage_bps_per_side"]["liquid"] / 1e4)
        self.assertAlmostEqual(by["A"]["net"], expected)
        self.assertEqual(len(bench), 1)  # only the liquid overnight event with both auction prices
        daily = ev_mod.daily_series(positions, "rth", "liquid", "net")
        self.assertEqual((daily["2023-03-01"]["n_long"], daily["2023-03-01"]["n_short"]), (1, 1))  # C excluded

    def test_missing_prices_and_neutral_labels_are_counted(self):
        events, scores, opens, closes = overnight_world(1)
        del closes[(events[0]["symbol"], events[0]["session"])]
        positions, bench, excluded = ev_mod.build_positions(events, scores, opens, closes, {}, FEES, COSTS)
        self.assertEqual(excluded["missing_exit_overnight"], 1)
        self.assertEqual(excluded["no_position_UNCLEAR"], 1)
        self.assertEqual(len(bench), 5)  # the UNCLEAR event is in the benchmark, the unpriced one is not


def test_protocol(min_days=10):
    p = frozen_protocol()
    for item in p["items"]:
        item["min_days"] = min_days
    p["segments"]["overnight_full"] = {"first_session": "2000-01-01", "last_session": "2099-12-31"}
    p["segments"]["recent_24m"] = {"first_session": "2000-01-01", "last_session": "2099-12-31"}
    p["segments"]["rth_full"] = {"first_session": "2000-01-01", "last_session": "2099-12-31"}
    return p


class FamiliesAndGates(unittest.TestCase):
    def run_world(self, protocol=None, **kw):
        events, scores, opens, closes = overnight_world(60, noise=0.003, **kw)
        positions, bench, _ = ev_mod.build_positions(events, scores, opens, closes, {}, FEES, COSTS)
        return ev_mod.evaluate_items(protocol or test_protocol(), positions, bench)

    def test_strong_selection_passes_long_only_and_long_short(self):
        items, gates = self.run_world(long_move=0.01, short_move=-0.01, other_move=0.0)
        self.assertEqual(items["NEWS-1"]["verdict"], "rejected")
        self.assertTrue(items["NEWS-4"]["rejected_primary_sequence"])
        self.assertTrue(items["NEWS-2B"]["rejected_secondary_holm"])
        self.assertTrue(items["NEWS-2"]["rejected_gatekeeping"])
        self.assertTrue(gates["long_short_candidate"])
        self.assertTrue(gates["long_only_paper_candidate"])
        self.assertFalse(gates["rth_candidate"])
        self.assertEqual(items["NEWS-3"]["verdict"], "insufficient_sample")
        self.assertGreater(gates["recent_long_leg_mean_net"], 0)

    def test_long_leg_that_only_rides_the_news_day_fails_the_benchmark(self):
        # every event rises 1%: the long leg is positive but no better than holding all events
        items, gates = self.run_world(long_move=0.01, short_move=0.01, other_move=0.01)
        self.assertTrue(items["NEWS-2"]["net"]["mean"] > 0)
        self.assertFalse(items["NEWS-2B"]["rejected_secondary_holm"])
        self.assertFalse(items["NEWS-2"]["rejected_gatekeeping"])
        self.assertFalse(gates["long_only_paper_candidate"])
        self.assertFalse(gates["long_short_candidate"])

    def test_fixed_sequence_stops_after_news1(self):
        p = test_protocol()
        p["segments"]["overnight_full"] = {"first_session": "2000-01-01", "last_session": "2000-12-31"}  # NEWS-1 empty
        items, gates = self.run_world(protocol=p)
        self.assertEqual(items["NEWS-1"]["verdict"], "insufficient_sample")
        self.assertFalse(items["NEWS-4"]["rejected_primary_sequence"])
        self.assertFalse(gates["long_short_candidate"])

    def test_recent_long_leg_must_be_positive(self):
        p = test_protocol()
        p["segments"]["recent_24m"] = {"first_session": "2000-01-01", "last_session": "2000-12-31"}
        p["items"][[i["id"] for i in p["items"]].index("NEWS-4")]["min_days"] = 0
        items, gates = self.run_world(protocol=p)
        self.assertIsNone(gates["recent_long_leg_mean_net"])
        self.assertFalse(gates["long_only_paper_candidate"])

    def test_upper_bound_reading(self):
        items, _ = self.run_world(long_move=0.0, short_move=0.0)
        net = items["NEWS-1"]["net"]
        self.assertAlmostEqual(net["upper_bound_95_one_sided"], net["mean"] + ev_mod.Z95 * net["se_nw"])
        reading = items["NEWS-1"]["reading"]["net"]
        self.assertEqual(set(reading), {"model_authors_3bps", "paper_34bps"})
        self.assertEqual(reading["paper_34bps"]["excluded_by_upper_bound"], net["upper_bound_95_one_sided"] < 0.0034)
        self.assertIn("gross", items["NEWS-1"]["reading"])

    def test_break_even(self):
        daily = {"2023-01-02": {"long": 0.002, "short": 0.001, "long_short": 0.003},
                 "2023-01-03": {"long": 0.001, "short": None, "long_short": None}}
        seg = {"first_session": "2023-01-01", "last_session": "2023-12-31"}
        self.assertAlmostEqual(ev_mod.break_even(daily, "long_short", seg), 0.0015)
        self.assertAlmostEqual(ev_mod.break_even(daily, "long", seg), 0.0015)


def git(cwd, *args):
    out = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], cwd=cwd,
                         capture_output=True, text=True, env=hermetic_git_environment())
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return out.stdout.strip()


class GuardedRunInGit(unittest.TestCase):
    """A full run() in a temporary git repository with synthetic private inputs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.study = self.repo / STUDY_REL
        (self.study / "receipts").mkdir(parents=True)
        for name in ev_mod.CODE_PINS + ("checkpoints.json",):
            shutil.copy(BLUEPRINT / name, self.study / name)
        for rel in ev_mod.REFERENCE_PINS.values():
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, self.repo / rel)
        self.data = Path(self.tmp.name) / "data"
        (self.data / "scores").mkdir(parents=True)
        (self.data / "auctions").mkdir()
        (self.data / "spreads").mkdir()
        events, scores, opens, closes = overnight_world(12, noise=0.002)
        rth = make_event(999, "R", "2023-03-01", window="rth")
        events.append(rth)
        scores[rth["event_id"]] = make_row(rth, "FAVORABLE")
        closes[("R", "2023-03-01")] = 101.0
        with gzip.open(self.data / "events.jsonl.gz", "wt") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")
        by_year = {}
        for row in scores.values():
            by_year.setdefault(row["checkpoint_year"], []).append(row)
        for y in range(2015, 2025):
            (self.data / f"scores/scores-{y}1231.jsonl").write_text("".join(json.dumps(r) + "\n" for r in by_year.get(y, [])))
        with gzip.open(self.data / "auctions/auctions.jsonl.gz", "wt") as fh:
            for (sym, day), price in closes.items():
                o = [{"c": "O", "p": opens[(sym, day)], "x": "N"}] if (sym, day) in opens else []
                fh.write(json.dumps({"symbol": sym, "session": day, "o": o, "c": [{"c": "6", "p": price, "x": "N"}]}) + "\n")
        (self.data / "spreads/quotes.jsonl").write_text(json.dumps(
            {"event_id": rth["event_id"], "entry_utc": rth["entry_utc"],
             "quotes": [{"bp": 99.9, "ap": 100.1, "t": "2023-03-01T16:00:01Z"}]}) + "\n")
        git(self.repo, "init", "-q")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "code")
        protocol = test_protocol(min_days=5)
        protocol["pins"] = ev_mod.compute_pins(self.study, self.data, self.repo)
        _, self.sha = write_protocol(self.study, protocol)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "freeze")
        self.commit = git(self.repo, "rev-parse", "HEAD")
        (self.study / "receipts" / "freeze-record.json").write_text(json.dumps(
            {"protocol_sha256": self.sha, "protocol_commit": self.commit}))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "record")

    def tearDown(self):
        self.tmp.cleanup()

    def run_eval(self, **kw):
        a = SimpleNamespace(data_root=self.data, freeze_record=None, protocol_sha256=kw.get("protocol_sha256"))
        return ev_mod.run(a, study_dir=self.study, repo_root=self.repo)

    def test_success_records_head_scope_and_gates(self):
        result = self.run_eval()
        self.assertEqual(result["git_head"], git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(result["protocol_sha256"], self.sha)
        self.assertIn("2026-09-21 asset master", result["scope"])
        self.assertEqual(result["positions"], 12 * 5 + 1)
        self.assertEqual(set(result["gates"]), {"long_only_paper_candidate", "long_short_candidate", "rth_candidate",
                                                "recent_long_leg_mean_net", "recent_long_leg_days"})
        block = result["descriptive"]["overnight:liquid"]["overnight_full"]
        self.assertEqual(block["single_leg_days"], 0)

    def test_wrong_cli_sha_is_refused(self):
        with self.assertRaises(ev_mod.Refusal):
            self.run_eval(protocol_sha256="0" * 64)

    def test_dirty_tree_is_refused(self):
        (self.study / "scratch.txt").write_text("x")
        with self.assertRaises(ev_mod.Refusal) as ctx:
            self.run_eval()
        self.assertIn("uncommitted", ctx.exception.reason)

    def test_changed_private_input_is_refused(self):
        (self.data / "spreads/quotes.jsonl").write_text("")
        with self.assertRaises(ev_mod.Refusal) as ctx:
            self.run_eval()
        self.assertIn("pin mismatch", ctx.exception.reason)

    def test_freeze_commit_must_be_an_ancestor(self):
        git(self.repo, "checkout", "-q", "--orphan", "other")
        git(self.repo, "commit", "-q", "-m", "unrelated")
        with self.assertRaises(ev_mod.Refusal) as ctx:
            self.run_eval()
        self.assertIn("not an ancestor", ctx.exception.reason)

    def test_protocol_at_freeze_commit_must_match(self):
        rec = self.study / "receipts" / "freeze-record.json"
        first = git(self.repo, "rev-list", "--max-parents=0", "HEAD")
        rec.write_text(json.dumps({"protocol_sha256": self.sha, "protocol_commit": first}))
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "point the record at the code commit")
        with self.assertRaises(ev_mod.Refusal) as ctx:
            self.run_eval()
        self.assertIn("freeze commit", ctx.exception.reason)

    def test_main_prints_refusal_and_exits_2_on_the_repository_draft(self):
        err = io.StringIO()
        with redirect_stdout(io.StringIO()):
            import contextlib
            with contextlib.redirect_stderr(err):
                code = ev_mod.main(["--data-root", str(self.data)])
        self.assertEqual(code, 2)
        self.assertIn("REFUSED", err.getvalue())


if __name__ == "__main__":
    unittest.main()
