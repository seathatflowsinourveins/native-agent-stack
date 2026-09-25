"""SYN: end-to-end dry run of the ORB pipeline on a synthetic minute corpus (skipped without duckdb).

Builds made-up minute bars, daily bars and a membership plan in a temporary directory, points
orb_common's paths there, and runs prepare -> cost table -> simulate -> evaluate with a frozen copy of the
protocol. It checks the post-freeze commands run, are byte-reproducible and refuse the draft. No private
data is read. Run with the adaptive-paper tools Python (duckdb 1.5.5); the system python3 skips it.
"""
import hashlib
import importlib.util
import json
import random
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ORB = Path(__file__).resolve().parents[1] / "blueprints/us-equities/sota-mover/orb"
HAS_DUCKDB = importlib.util.find_spec("duckdb") is not None


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ORB / file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(HAS_DUCKDB, "duckdb not installed (run with the adaptive-paper tools Python)")
class SyntheticPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import duckdb
        if str(ORB) not in sys.path:
            sys.path.insert(0, str(ORB))
        cls.C = load("orb_common", "orb_common.py")
        cls.P = load("orb_prepare", "orb_prepare.py")
        cls.Q = load("collect_quotes", "collect_quotes.py")
        cls.SIM = load("orb_simulate_pipeline", "simulate.py")
        cls.E = load("orb_evaluate_pipeline", "evaluate.py")
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        C = cls.C
        C.PRIVATE = root / "private"
        C.MINUTE_ROOT = root / "minute"
        C.DAILY_PARQUET = root / "daily.parquet"
        C.MINUTE_PLAN = root / "plan.json"
        cls.P.BARS_GLOB = str(C.MINUTE_ROOT / "bars/symbol=*/year=*/full.parquet")
        daily_sessions = [s for s, _ in C.calendar() if "2023-06-01" <= s <= "2024-02-09"]
        sessions = [s for s in daily_sessions if s >= "2023-11-15"]  # minute bars only here
        syms = [f"S{i:02d}" for i in range(24)]
        rng = random.Random(7)
        con = duckdb.connect()
        drows, mrows = [], []
        for s in daily_sessions:  # the membership calendar symbol; not in the corpus (a counted 'missing' member)
            drows.append(("SPY", s, 400, 401, 399, 400, 5e7, 400, 401, 399, 400, 5e7))
        for sym in syms:
            px = rng.uniform(20, 150)
            for s in daily_sessions:
                if s < sessions[0]:
                    drows.append((sym, s, px, px * 1.02, px * 0.98, px, 3e6, px, px * 1.02, px * 0.98, px, 3e6))
                    continue
                o = px * (1 + rng.gauss(0, 0.01))
                path, hi, lo = [o], o, o
                for m in range(570, 960):
                    nxt = path[-1] * (1 + rng.gauss(0, 0.0015))
                    bo, bc = path[-1], nxt
                    bh, bl = max(bo, bc) * (1 + abs(rng.gauss(0, 0.0005))), min(bo, bc) * (1 - abs(rng.gauss(0, 0.0005)))
                    vol = rng.uniform(1e4, 5e4) * (5 if m < 575 else 1) * (rng.uniform(0.3, 4) if m == 570 else 1)
                    mrows.append((sym, s, m, bo, bh, bl, bc, vol, 2024 if s >= "2024-01-01" else 2023))
                    path.append(nxt)
                    hi, lo = max(hi, bh), min(lo, bl)
                c = path[-1]
                drows.append((sym, s, o, hi, lo, c, 3e6, o, hi, lo, c, 3e6))
                px = c
        mcsv = root / "m.csv"
        with open(mcsv, "w") as f:  # a CSV load is far faster than executemany
            f.writelines(",".join(map(str, r)) + "\n" for r in mrows)
        con.execute(f"""CREATE TABLE m AS SELECT * FROM read_csv('{mcsv}', header=false, columns={{'symbol': 'VARCHAR',
            'et_date': 'DATE', 'et_minute': 'SMALLINT', 'o': 'DOUBLE', 'h': 'DOUBLE', 'l': 'DOUBLE', 'c': 'DOUBLE',
            'v': 'DOUBLE', 'year': 'BIGINT'}})""")
        for sym in syms:
            for y in (2023, 2024):
                d = C.MINUTE_ROOT / f"bars/symbol={sym}/year={y}"
                d.mkdir(parents=True)
                con.execute(f"COPY (SELECT symbol, et_date, et_minute, o, h, l, c, v, year FROM m WHERE symbol=? AND year=? "
                            f"ORDER BY et_date, et_minute) TO '{d / 'full.parquet'}' (FORMAT parquet)", [sym, y])
        con.execute("CREATE TABLE d(symbol VARCHAR, session_date DATE, raw_o DOUBLE, raw_h DOUBLE, raw_l DOUBLE, "
                    "raw_c DOUBLE, raw_v DOUBLE, all_o DOUBLE, all_h DOUBLE, all_l DOUBLE, all_c DOUBLE, all_v DOUBLE)")
        con.executemany("INSERT INTO d VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", drows)
        con.execute(f"COPY (SELECT *, true AS in_raw, true AS in_all FROM d) TO '{C.DAILY_PARQUET}' (FORMAT parquet)")
        C.MINUTE_PLAN.write_text(json.dumps({"universe_a": {"per_year": {"2023": syms, "2024": syms}, "union": syms},
                                             "universe_inputs": {"daily_parquet_sha256": "synthetic"}}))
        proto = json.loads((ORB / "protocol.json").read_text())
        proto.update(status="frozen_before_outcomes", frozen_before_outcomes=True)
        C.PROTOCOL_PATH = root / "protocol.json"
        C.PROTOCOL_PATH.write_text(json.dumps(proto, indent=1))
        cls.sha = hashlib.sha256(C.PROTOCOL_PATH.read_bytes()).hexdigest()
        C.STUDY_DIR = root / "study"  # a git repository standing in for the study directory
        (C.STUDY_DIR / "evidence").mkdir(parents=True)
        C.FREEZE_RECORD = C.STUDY_DIR / "evidence/freeze-record.json"
        cls.git_env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                       "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin", "HOME": str(root)}
        cls.git("init", "-q")

    @classmethod
    def git(cls, *args):
        return subprocess.run(["git", *args], cwd=cls.C.STUDY_DIR, check=True, capture_output=True, text=True,
                              env=cls.git_env).stdout.strip()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_quiet(self, fn, argv):
        buf = StringIO()
        with redirect_stdout(buf):
            rc = fn(argv)
        return rc, buf.getvalue()

    def test_pipeline(self):
        C, P, Q, SIM, E = self.C, self.P, self.Q, self.SIM, self.E
        for cmd in ("or-table", "membership", "candidates", "select", "triggers"):
            self.assertEqual(self.run_quiet(P.main, [cmd])[0], 0, cmd)
        self.assertEqual(self.run_quiet(P.main, ["verify-or", "--n", "5"])[0], 0)
        sel = C.load_json(C.PRIVATE / "selected.counts.json")
        self.assertGreater(sel["post_publication"]["selected"], 0)
        trig = C.load_json(C.PRIVATE / "triggers.counts.json")
        self.assertGreater(trig["post_publication"]["fired"], 0)
        # a synthetic cost table in place of the fetched one
        rng = random.Random(3)
        obs = [(t, p, liq, rng.uniform(1e-4, 8e-4)) for t in range(4) for p in range(4) for liq in range(3) for _ in range(31)]
        cells, p90 = Q.build_cells(obs)
        (C.PRIVATE / "cost-table.json").write_text(json.dumps({"groups": {g: {"cells": cells} for g in
                                                                           ("reproduction", "post_publication")}}))
        # pin the private inputs in the frozen copy, as the real freeze does
        proto = json.loads(C.PROTOCOL_PATH.read_text())
        proto["pinned_artifacts"] = {
            "private": {n: C.sha256_file(C.PRIVATE / n) for n in
                        ("membership.parquet", "candidates.csv.gz", "selected.csv", "triggers.csv", "cost-table.json")},
            "inputs": {k: C.sha256_file(v) for k, v in C.input_paths().items()}}
        C.PROTOCOL_PATH = C.STUDY_DIR / "protocol.json"   # freeze it inside the study repository
        C.PROTOCOL_PATH.write_text(json.dumps(proto, indent=1))
        self.sha = hashlib.sha256(C.PROTOCOL_PATH.read_bytes()).hexdigest()
        self.git("add", ".")
        self.git("commit", "-q", "-m", "freeze")
        commit = self.git("rev-parse", "HEAD")
        # no freeze record yet, then a wrong hash: refused before anything is read
        with self.assertRaises(SystemExit) as cm:
            SIM.main(["run", "--protocol-sha256", self.sha])
        self.assertIn("freeze record", str(cm.exception.code))
        C.FREEZE_RECORD.write_text(json.dumps({"protocol_sha256": self.sha, "protocol_commit": commit,
                                               "frozen_at": "2026-09-25T00:00:00Z", "reviewer": "t",
                                               "review_verdict": "freeze_ready"}))
        self.git("add", ".")
        self.git("commit", "-q", "-m", "freeze record")
        with self.assertRaises(SystemExit):
            SIM.main(["run", "--protocol-sha256", "0" * 64])
        with self.assertRaises(SystemExit):
            E.main(["run"])
        rc, out = self.run_quiet(SIM.main, ["run", "--protocol-sha256", self.sha])
        self.assertEqual(rc, 0)
        first = json.loads(out)
        rc, out = self.run_quiet(SIM.main, ["run", "--protocol-sha256", self.sha])
        self.assertEqual(json.loads(out)["sha256"], first["sha256"])        # byte-reproducible
        self.assertEqual(first["trades:F0"], first["trades:F1"])
        self.assertEqual(first["trades:F1"], first["trades:F2"])
        self.assertEqual(first["trades:F0"], first["trades:F0fav"])
        self.assertEqual(first["protocol_sha256"], self.sha)
        self.assertEqual(len(first["git_head"]), 40)
        self.assertEqual(first["freeze_commit"], commit)
        self.assertEqual(first["trades:F1"], trig["post_publication"]["fired"] + trig.get("reproduction", {}).get("fired", 0))
        self.assertEqual(self.run_quiet(SIM.main, ["run", "--protocol-sha256", self.sha, "--population", "base"])[0], 0)
        rc, out = self.run_quiet(E.main, ["run", "--protocol-sha256", self.sha])
        self.assertEqual(rc, 0)
        # a tampered trades file is refused by evaluate
        tr = C.PRIVATE / "trades-selected.csv.gz"
        saved_tr = tr.read_bytes()
        tr.write_bytes(saved_tr + b"x")
        with self.assertRaises(SystemExit) as cm:
            E.main(["run", "--protocol-sha256", self.sha])
        self.assertIn("counts file", str(cm.exception.code))
        tr.write_bytes(saved_tr)
        # a dirty study directory is refused
        (C.STUDY_DIR / "stray.txt").write_text("x")
        with self.assertRaises(SystemExit) as cm:
            E.main(["run", "--protocol-sha256", self.sha])
        self.assertIn("uncommitted", str(cm.exception.code))
        (C.STUDY_DIR / "stray.txt").unlink()
        # a committed code change after the freeze is refused although the tree is clean
        (C.STUDY_DIR / "simulate.py").write_text("# changed after the freeze\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "post-freeze change")
        with self.assertRaises(SystemExit) as cm:
            E.main(["run", "--protocol-sha256", self.sha])
        self.assertIn("changed after the freeze commit", str(cm.exception.code))
        self.git("reset", "-q", "--hard", "HEAD~1")   # drop the change in this scratch repository only
        # a changed pinned input is refused
        saved = (C.PRIVATE / "cost-table.json").read_bytes()
        (C.PRIVATE / "cost-table.json").write_bytes(saved + b" ")
        with self.assertRaises(SystemExit) as cm:
            SIM.main(["run", "--protocol-sha256", self.sha])
        self.assertIn("pinned", str(cm.exception.code))
        (C.PRIVATE / "cost-table.json").write_bytes(saved)
        res = C.load_json(C.PRIVATE / "results.json")
        self.assertEqual(set(res["items"]), {"ORB-1", "ORB-2", "ORB-3"})
        for k, item in res["items"].items():
            self.assertIn(item["sequence_status"], ("rejected", "not_rejected", "not_tested"))
            self.assertTrue(res["verdicts"][k].startswith(("supported", "not supported", "pending", "inconclusive")))
        self.assertIsNone(res["verdicts"]["quote_adjusted_mean_R"])   # quote check not run in this dry run
        self.assertIn("week_block_bootstrap_ORB-1", res["descriptive"])
        self.assertIn("same_bar_count", res["per_trade"]["post_publication|F1|combined"])
        self.assertIn("fig4|post_publication|F0", res["descriptive"])
        # the F2 mean is below the F1 mean (2 bps extra per side)
        pt = res["per_trade"]
        self.assertLess(pt["post_publication|F2|combined"]["mean_net_R"], pt["post_publication|F1|combined"]["mean_net_R"])


if __name__ == "__main__":
    unittest.main()
