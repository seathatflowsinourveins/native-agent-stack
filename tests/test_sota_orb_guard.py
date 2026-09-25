"""SYN: freeze guard, cost-table helpers and statistics of the ORB replication (sota-mover/orb).

Synthetic inputs only; no private data is read (every refusal happens before any file other than the
protocol and the freeze record is opened; path attributes are patched to temporary files). Stdlib only (system python3).
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timezone
from pathlib import Path

ORB = Path(__file__).resolve().parents[1] / "blueprints/us-equities/sota-mover/orb"
if str(ORB) not in sys.path:
    sys.path.insert(0, str(ORB))


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ORB / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C = load("orb_common", "orb_common.py")
sys.modules["orb_common"] = C
E = load("orb_evaluate_under_test", "evaluate.py")
Q = load("orb_collect_quotes_under_test", "collect_quotes.py")
SIM = load("orb_simulate_under_test", "simulate.py")
QC = load("orb_quote_check_under_test", "quote_check.py")


def write_protocol(tmp, status, frozen, extra=None):
    p = Path(tmp) / "protocol.json"
    p.write_text(json.dumps(dict({"id": "x", "status": status, "frozen_before_outcomes": frozen}, **(extra or {}))))
    return p, hashlib.sha256(p.read_bytes()).hexdigest()


def write_record(tmp, sha):
    r = Path(tmp) / "freeze-record.json"
    r.write_text(json.dumps({"protocol_sha256": sha}))
    return r


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin", "HOME": cwd})


class RefusalGuard(unittest.TestCase):
    def test_repository_protocol_is_a_draft(self):
        proto = json.loads((ORB / "protocol.json").read_text())
        self.assertEqual(proto["status"], "draft_pending_independent_pre_outcome_review")
        self.assertIs(proto["frozen_before_outcomes"], False)
        self.assertFalse((ORB / "evidence/freeze-record.json").exists())

    def test_require_frozen_uses_the_freeze_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, sha = write_protocol(tmp, "frozen_before_outcomes", True)
            with mock.patch.object(C, "FREEZE_RECORD", Path(tmp) / "freeze-record.json"):
                with self.assertRaises(SystemExit) as cm:
                    C.require_frozen(p, None)
                self.assertIn("required", str(cm.exception.code))
                with self.assertRaises(SystemExit) as cm:          # no record yet
                    C.require_frozen(p, sha)
                self.assertIn("freeze record", str(cm.exception.code))
                write_record(tmp, sha)
                with self.assertRaises(SystemExit) as cm:          # argument differs from the record
                    C.require_frozen(p, "0" * 64)
                self.assertIn("freeze record", str(cm.exception.code))
                self.assertEqual(C.require_frozen(p, sha.upper())["id"], "x")
                p.write_text(p.read_text() + " ")                  # the working file changed after the freeze
                with self.assertRaises(SystemExit) as cm:
                    C.require_frozen(p, sha)
                self.assertIn("does not match the freeze record", str(cm.exception.code))
                for status, frozen in (("draft_pending_independent_pre_outcome_review", False),
                                       ("frozen_before_outcomes", False)):
                    p2, sha2 = write_protocol(tmp, status, frozen)
                    write_record(tmp, sha2)
                    with self.assertRaises(SystemExit) as cm:
                        C.require_frozen(p2, sha2)
                    self.assertIn("status", str(cm.exception.code))

    def test_entry_points_refuse_on_the_draft(self):
        sha = hashlib.sha256((ORB / "protocol.json").read_bytes()).hexdigest()
        for main, args in ((E.main, ["run"]), (E.main, ["run", "--protocol-sha256", sha]),
                           (SIM.main, ["run", "--protocol-sha256", sha]), (SIM.main, ["run", "--population", "base"]),
                           (QC.main, ["sample", "--protocol-sha256", sha]), (QC.main, ["apply"])):
            with self.assertRaises(SystemExit) as cm:
                main(args)
            self.assertTrue(str(cm.exception.code).startswith("refused"), args)


class PinsCountsAndGit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.priv = root / "private"
        self.priv.mkdir()
        (self.priv / "a.csv").write_text("x\n")
        self.inputs = {}
        for name in ("daily_parquet", "minute_plan", "fees", "calendar"):
            f = root / f"{name}.bin"
            f.write_text(name)
            self.inputs[name] = f
        self.patches = [mock.patch.object(C, "PRIVATE", self.priv),
                        mock.patch.object(C, "DAILY_PARQUET", self.inputs["daily_parquet"]),
                        mock.patch.object(C, "MINUTE_PLAN", self.inputs["minute_plan"]),
                        mock.patch.object(C, "FEES_PATH", self.inputs["fees"]),
                        mock.patch.object(C, "CALENDAR_PATH", self.inputs["calendar"])]
        for pt in self.patches:
            pt.start()

    def tearDown(self):
        for pt in self.patches:
            pt.stop()
        self.tmp.cleanup()

    def pins(self):
        return {"pinned_artifacts": {"private": {"a.csv": C.sha256_file(self.priv / "a.csv")},
                                     "inputs": {k: C.sha256_file(v) for k, v in self.inputs.items()}}}

    def test_verify_pins(self):
        C.verify_pins(self.pins())
        with self.assertRaises(SystemExit):
            C.verify_pins({"pinned_artifacts": {"private": {"a.csv": "0" * 64}}})       # inputs not pinned
        proto = self.pins()
        (self.priv / "a.csv").write_text("y\n")
        with self.assertRaises(SystemExit) as cm:
            C.verify_pins(proto)
        self.assertIn("a.csv", str(cm.exception.code))
        proto = self.pins()
        self.inputs["fees"].write_text("changed")
        with self.assertRaises(SystemExit) as cm:
            C.verify_pins(proto)
        self.assertIn("fees", str(cm.exception.code))
        proto = self.pins()
        self.inputs["daily_parquet"].unlink()
        with self.assertRaises(SystemExit):
            C.verify_pins(proto)

    def test_check_trades(self):
        sha = "ab" * 32
        with self.assertRaises(SystemExit):
            C.check_trades("selected", sha)                                      # missing
        t = self.priv / "trades-selected.csv.gz"
        t.write_bytes(b"trades")
        counts = self.priv / "trades-selected.counts.json"
        counts.write_text(json.dumps({"sha256": C.sha256_file(t), "protocol_sha256": sha}))
        self.assertEqual(C.check_trades("selected", sha.upper())["protocol_sha256"], sha)
        with self.assertRaises(SystemExit) as cm:
            C.check_trades("selected", "cd" * 32)
        self.assertIn("another protocol", str(cm.exception.code))
        t.write_bytes(b"tampered")
        with self.assertRaises(SystemExit) as cm:
            C.check_trades("selected", sha)
        self.assertIn("does not match its counts", str(cm.exception.code))

    def test_require_clean_tree(self):
        repo = Path(self.tmp.name) / "repo"
        study = repo / "study"
        study.mkdir(parents=True)
        with self.assertRaises(SystemExit):
            C.require_clean_tree(study)                                          # not a git tree
        git("init", "-q", cwd=repo)
        (study / "f.py").write_text("x = 1\n")
        (repo / "other.txt").write_text("outside the study directory\n")
        git("add", "study/f.py", cwd=repo)
        git("commit", "-q", "-m", "c", cwd=repo)
        head = C.require_clean_tree(study)                                       # other.txt is outside
        self.assertEqual(len(head), 40)
        (study / "f.py").write_text("x = 2\n")
        with self.assertRaises(SystemExit) as cm:
            C.require_clean_tree(study)
        self.assertIn("uncommitted", str(cm.exception.code))
        (study / "f.py").write_text("x = 1\n")
        (study / "new.json").write_text("{}")
        with self.assertRaises(SystemExit):
            C.require_clean_tree(study)                                          # untracked counts as dirty


class FreezeCommit(unittest.TestCase):
    """require_freeze_commit in a scratch git repository."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.study = self.repo / "study"
        (self.study / "evidence").mkdir(parents=True)
        git("init", "-q", cwd=self.repo)
        (self.study / "orb_signal.py").write_text("X = 1\n")
        (self.study / "protocol.json").write_text('{"status": "frozen_before_outcomes"}')
        git("add", ".", cwd=self.repo)
        git("commit", "-q", "-m", "freeze", cwd=self.repo)
        self.commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, capture_output=True, text=True,
                                     check=True).stdout.strip()
        self.sha = hashlib.sha256((self.study / "protocol.json").read_bytes()).hexdigest()
        self.record = self.study / "evidence/freeze-record.json"
        self.patch = mock.patch.object(C, "FREEZE_RECORD", self.record)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def write_record(self, **kw):
        rec = {"protocol_sha256": self.sha, "protocol_commit": self.commit, "frozen_at": "2026-09-25T00:00:00Z",
               "reviewer": "r", "review_verdict": "freeze_ready"}
        rec.update(kw)
        self.record.write_text(json.dumps(rec))
        git("add", ".", cwd=self.repo)
        git("commit", "-q", "-m", "record", cwd=self.repo)

    def test_accept_path(self):
        self.write_record()
        (self.study / "evidence/receipt.json").write_text("{}")  # later evidence commits are allowed
        git("add", ".", cwd=self.repo)
        git("commit", "-q", "-m", "evidence", cwd=self.repo)
        self.assertEqual(C.require_freeze_commit(self.study), self.commit)
        self.assertEqual(len(C.require_clean_tree(self.study)), 40)

    def test_code_change_after_freeze_refused(self):
        self.write_record()
        (self.study / "orb_signal.py").write_text("X = 2\n")
        git("add", ".", cwd=self.repo)
        git("commit", "-q", "-m", "change rules", cwd=self.repo)
        C.require_clean_tree(self.study)  # the tree is clean, yet the code moved
        with self.assertRaises(SystemExit) as cm:
            C.require_freeze_commit(self.study)
        self.assertIn("orb_signal.py", str(cm.exception.code))

    def test_missing_or_malformed_commit_refused(self):
        with self.assertRaises(SystemExit):
            C.require_freeze_commit(self.study)                 # no record at all
        self.write_record(protocol_commit=None)
        with self.assertRaises(SystemExit) as cm:
            C.require_freeze_commit(self.study)
        self.assertIn("40-hex", str(cm.exception.code))
        self.write_record(protocol_commit="1" * 40)             # well-formed but not in the history
        with self.assertRaises(SystemExit) as cm:
            C.require_freeze_commit(self.study)
        self.assertIn("ancestor", str(cm.exception.code))

    def test_wrong_commit_protocol_refused(self):
        (self.study / "protocol.json").write_text('{"status": "frozen_before_outcomes", "edited": true}')
        git("add", ".", cwd=self.repo)
        git("commit", "-q", "-m", "protocol edit", cwd=self.repo)
        self.write_record()   # records the sha of the edited file but points at the earlier commit
        rec = json.loads(self.record.read_text())
        rec["protocol_sha256"] = hashlib.sha256((self.study / "protocol.json").read_bytes()).hexdigest()
        self.record.write_text(json.dumps(rec))
        git("add", ".", cwd=self.repo)
        git("commit", "-q", "-m", "record", cwd=self.repo)
        with self.assertRaises(SystemExit) as cm:
            C.require_freeze_commit(self.study)
        self.assertIn("does not hash", str(cm.exception.code))

    def test_template_has_the_fields(self):
        t = json.loads((ORB / "evidence/freeze-record.template.json").read_text())
        self.assertTrue({"protocol_sha256", "protocol_commit", "frozen_at", "reviewer", "review_verdict"} <= set(t))


class QuoteHelpers(unittest.TestCase):
    def test_stamps(self):
        day = "2024-03-05"
        st = Q.stamps_for(day, 576, 960)
        self.assertEqual([(m, k) for _, m, k in st],
                         [(577, "trigger"), (592, "trigger+15m"), (637, "trigger+60m"), (955, "close-5m")])
        self.assertEqual(st[0][0], datetime(2024, 3, 5, 14, 37, tzinfo=timezone.utc).timestamp())  # 09:37 EST
        late = Q.stamps_for(day, 930, 960)
        self.assertEqual([k for _, _, k in late], ["trigger", "trigger+15m", "close-5m"])
        self.assertEqual([k for _, _, k in Q.stamps_for(day, 950, 960)], ["trigger", "close-5m"])

    def test_buckets_and_tiers(self):
        self.assertEqual(Q.time_bucket(576, 960), 0)
        self.assertEqual(Q.time_bucket(600, 960), 1)
        self.assertEqual(Q.time_bucket(955, 960), 3)
        self.assertEqual(Q.time_bucket(960, 960), 3)
        self.assertIsNone(Q.time_bucket(570, 960))
        self.assertEqual([Q.tier(x, Q.PRICE_TIERS) for x in (5.5, 20.0, 49.99, 200.0)], [0, 1, 1, 3])
        self.assertEqual([Q.tier(x, Q.LIQ_TIERS) for x in (5e7, 1e8, 6e8)], [0, 1, 2])

    def test_sample_key_is_deterministic(self):
        a = [Q.sample_key(f"S{i}", "2024-01-02", 1, 5) for i in range(500)]
        self.assertEqual(a, [Q.sample_key(f"S{i}", "2024-01-02", 1, 5) for i in range(500)])
        self.assertTrue(60 < sum(a) < 140)

    def test_rate_cap_after_0330_et(self):
        self.assertEqual(Q.allowed_per_minute(datetime(2026, 9, 25, 7, 29, tzinfo=timezone.utc)), 2000)  # 03:29 EDT
        self.assertEqual(Q.allowed_per_minute(datetime(2026, 9, 25, 7, 30, tzinfo=timezone.utc)), 500)   # 03:30 EDT

    def test_valid_quote_and_cells(self):
        qs = [{"bp": 10.0, "ap": 10.0}, {"bp": 0, "ap": 10.0}, {"bp": 9.99, "ap": 10.01}]
        self.assertEqual(Q.valid_quote(qs), qs[2])
        obs = [(0, 1, 2, 0.001)] * 40 + [(0, 1, 0, 0.003)] * 10 + [(2, 3, 1, 0.01)] * 5
        cells, p90 = Q.build_cells(obs)
        self.assertEqual(cells["0|1|2"]["source"], "cell")
        self.assertAlmostEqual(cells["0|1|2"]["half_spread"], 0.001)
        self.assertEqual(cells["0|1|0"]["source"], "time_x_price")   # 10 in the cell, 50 in time x price
        self.assertEqual(cells["2|3|1"]["source"], "table_p90")
        self.assertEqual(cells["2|3|1"]["half_spread"], p90)

    def test_cost_function_lookup(self):
        cells = {f"{t}|{p}|{l}": {"half_spread": t * 100 + p * 10 + l} for t in range(4) for p in range(4) for l in range(3)}
        hs = SIM.cost_function({"groups": {"post_publication": {"cells": cells}}}, "post_publication", 2, 960)
        self.assertEqual(hs(575, 30.0), 12)     # 09:35 bar ends 09:36: bucket 0; $30: tier 1; liquidity 2
        self.assertEqual(hs(959, 250.0), 332)


class SimulateHelpers(unittest.TestCase):
    def test_trade_record_gross_and_net(self):
        fees = json.loads((ORB.parents[1] / "mover-v3/data/fees-v3.json").read_text())
        bars = [(575, 12.0, 12.1, 11.95, 12.05, 1.0), (959, 12.6, 12.6, 12.6, 12.6, 1.0)]
        t = SIM.trade_record("F1", fees, "2024-06-03", 1, 12.0, 2.0, bars, 960, lambda m, p: 0.001)
        self.assertAlmostEqual(t["gross_R"], (12.6 - 12.0) / 0.2)            # base prices, before costs
        net = (12.6 * 0.999 - 12.0 * 1.001 - (27.8 * 12.6 * 0.999 / 1e6 + 0.000166)) / 0.2
        self.assertAlmostEqual(t["net_R"], net)
        self.assertIsNone(SIM.trade_record("F1", fees, "2024-06-03", 1, 13.0, 2.0, bars, 960, lambda m, p: 0.0))

    def test_ssr_flag(self):
        bars = [(570, 10, 10, 8.9, 9, 1), (576, 9, 9, 8.5, 8.6, 1)]
        self.assertEqual(SIM.ssr_flag(1, 5.0, 10.0, 10.0, 1.0, bars, 576), 0)        # longs never
        self.assertEqual(SIM.ssr_flag(-1, 8.9, 10.0, 10.0, 1.0, [], 576), 1)         # prior session -11%
        self.assertEqual(SIM.ssr_flag(-1, 9.5, 10.0, 10.0, 1.0, bars, 576), 1)       # 8.9 <= 9.0 before the trigger
        self.assertEqual(SIM.ssr_flag(-1, 9.5, 10.0, 10.0, 1.0, bars[1:], 576), 0)   # only at/after the trigger
        self.assertEqual(SIM.ssr_flag(-1, 9.5, 10.0, 20.0, 2.0, bars, 576), 1)       # prior close in post-split units


class QuoteCheck(unittest.TestCase):
    def test_executions_and_delta(self):
        t = {"gap_entry": 1, "entry_minute": 576, "entry_base": 12.5, "dirn": 1, "exit_reason": "stop",
             "exit_minute": 600, "exit_base": 11.0, "stop": 12.3}
        ex = QC.executions(t)
        self.assertEqual(ex, [("entry_gap", 576, 12.5, 1, True), ("stop_exit", 600, 11.0, -1, True)])
        eod = dict(t, gap_entry=0, exit_reason="eod")
        self.assertEqual(QC.executions(eod), [])
        inside = dict(t, gap_entry=0, exit_base=12.3)
        self.assertEqual(QC.executions(inside), [("stop_exit", 600, 12.3, -1, False)])
        # measured spreads wider than the bucket lower R: -(0.002-0.001)*12.5/0.2 - (0.001-0.001)*11/0.2
        self.assertAlmostEqual(QC.trade_delta_r(ex, [0.002, 0.001], [0.001, 0.001], 0.2), -0.0625)
        self.assertAlmostEqual(QC.segment_shift([-0.1, -0.3], 50, 100), -0.1)
        self.assertEqual(QC.segment_shift([], 0, 100), 0.0)

    def test_quote_coverage(self):
        self.assertTrue(QC.coverage_ok(5, 100))
        self.assertFalse(QC.coverage_ok(6, 100))
        self.assertTrue(QC.coverage_ok(0, 0))
        self.assertEqual(E.item_verdict("rejected", True, "coverage", 0.2, True, True), "inconclusive (quote coverage)")

    def test_sample_key_depends_on_protocol(self):
        a = [QC.in_check("2024-01-02", f"S{i}", 1, "aa" * 32) for i in range(1000)]
        b = [QC.in_check("2024-01-02", f"S{i}", 1, "bb" * 32) for i in range(1000)]
        self.assertTrue(60 < sum(a) < 140)
        self.assertNotEqual(a, b)


class Statistics(unittest.TestCase):
    def test_fixed_sequence(self):
        seq = ("ORB-1", "ORB-2", "ORB-3")
        self.assertEqual(E.fixed_sequence({"ORB-1": 0.01, "ORB-2": 0.049, "ORB-3": 0.04}, seq, 0.05),
                         {"ORB-1": "rejected", "ORB-2": "rejected", "ORB-3": "rejected"})
        self.assertEqual(E.fixed_sequence({"ORB-1": 0.01, "ORB-2": 0.2, "ORB-3": 0.001}, seq, 0.05),
                         {"ORB-1": "rejected", "ORB-2": "not_rejected", "ORB-3": "not_tested"})
        self.assertEqual(E.fixed_sequence({"ORB-1": 0.06, "ORB-2": 0.001, "ORB-3": None}, seq, 0.05),
                         {"ORB-1": "not_rejected", "ORB-2": "not_tested", "ORB-3": "not_tested"})

    def test_verdict_wording(self):
        v = E.item_verdict
        self.assertEqual(v("rejected", True, True, 0.2, True, True), "supported on the 500 most liquid names")
        self.assertTrue(v("rejected", True, None, 0.2, True, True).startswith("pending"))
        self.assertTrue(v("rejected", True, False, 0.2, True, True).startswith("not supported, inconclusive"))
        self.assertTrue(v("rejected", False, True, 0.2, True, True).startswith("not supported"))
        self.assertEqual(v("not_rejected", True, True, 0.05, True, True),
                         "not supported; an effect >= 0.08R is excluded on the 500 most liquid names")
        self.assertEqual(v("not_rejected", True, True, 0.08, True, True),
                         "not supported, inconclusive at 0.08R on the 500 most liquid names")
        self.assertEqual(v("not_tested", True, True, 0.1, True, False), "not supported on the 500 most liquid names")
        self.assertTrue(v("rejected", True, True, 0.2, False, True).startswith("inconclusive"))

    def test_bootstrap_mean(self):
        mean, p, lo, hi, up = E.bootstrap_mean([10.0] * 50, [10] * 50, 200, 1)
        self.assertEqual((mean, lo, hi, up), (1.0, 1.0, 1.0, 1.0))
        self.assertLess(p, 0.01)
        mean, p, lo, hi, up = E.bootstrap_mean([1.0, -1.0] * 50, [1] * 100, 500, 1)
        self.assertEqual(mean, 0.0)
        self.assertGreater(p, 0.3)
        self.assertLess(lo, 0.0)
        self.assertGreater(hi, up)
        self.assertGreater(up, 0.0)

    def test_week_clusters(self):
        self.assertEqual(E.iso_week("2024-01-01"), E.iso_week("2024-01-05"))
        self.assertNotEqual(E.iso_week("2024-01-05"), E.iso_week("2024-01-08"))
        sums, counts = E.cluster_sums([{"d": "2024-01-02", "x": 1.0}, {"d": "2024-01-03", "x": 2.0},
                                       {"d": "2024-01-08", "x": 4.0}], lambda t: E.iso_week(t["d"]), lambda t: t["x"])
        self.assertEqual((sums, counts), ([3.0, 4.0], [2, 1]))

    def test_power(self):
        self.assertGreater(E.n_required(0.08, 3.0, 1.0, 0.05), E.n_required(0.08, 2.0, 1.0, 0.05))
        self.assertAlmostEqual(E.mde(E.n_required(0.08, 2.0, 1.3, 0.05), 2.0, 1.3, 0.05), 0.08, places=3)
        # the protocol's recorded minimum sample matches the formula at its stated basis
        proto = json.loads((ORB / "protocol.json").read_text())
        t = proto["sample_size"]["table"]
        deff = 1 + (t["m_bar_combined"] - 1) * 0.02
        self.assertEqual(proto["sample_size"]["n_min_trades"], E.n_required(0.08, 2.0, deff, 0.05))
        self.assertEqual(proto["multiplicity"]["alpha_per_step"], 0.05)

    def test_portfolio_paper_sizing(self):
        fees = json.loads((ORB.parents[1] / "mover-v3/data/fees-v3.json").read_text())
        t = {"d": "2024-06-03", "entry_fill": 10.0, "exit_fill": 10.4, "atr14": 2.0, "dirn": 1, "slots": 20}
        stats, rets = E.portfolio([t], ["2024-06-03", "2024-06-04"], fees, "F0", "paper")
        # 62.5 shares x $0.40 - 2 x 0.0035 x 62.5 commission
        self.assertAlmostEqual(rets[0], (62.5 * 0.4 - 0.4375) / 25000)
        self.assertEqual(rets[1], 0.0)
        self.assertEqual(stats["trades"], 1)
        stats1, rets1 = E.portfolio([t], ["2024-06-03"], fees, "F1", "1x")
        self.assertAlmostEqual(rets1[0], (125 * 0.4 - (27.8 * 1300 / 1e6 + 125 * 0.000166)) / 25000)


if __name__ == "__main__":
    unittest.main()
