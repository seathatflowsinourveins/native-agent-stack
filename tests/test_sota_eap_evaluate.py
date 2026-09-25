"""SYN: evaluate.py guard, pins, git and freeze-record refusals, and the evaluation core on synthetic data."""
import argparse
import contextlib
import hashlib
import io
import json
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from tests import hermetic_git_environment

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "blueprints/us-equities/sota-mover/eap"
sys.path.insert(0, str(BASE))
import evaluate as V  # noqa: E402

PROTOCOL = BASE / "protocol.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_copy(tmp, **changes):
    p = json.loads(PROTOCOL.read_text())
    p.update({"status": "frozen_pre_outcome", "frozen_before_outcomes": True, "frozen_at": "2026-09-30T00:00:00Z"})
    p.update(changes)
    path = Path(tmp) / "protocol.json"
    path.write_text(json.dumps(p))
    return path


class Guard(unittest.TestCase):
    def test_committed_draft_is_refused_even_with_its_own_sha(self):
        with self.assertRaises(V.Refusal) as cm:
            V.guard(PROTOCOL, sha(PROTOCOL))
        self.assertIn("not frozen", cm.exception.reason)
        self.assertEqual(cm.exception.code, 2)

    def test_sha_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = frozen_copy(tmp)
            for bad in ("0" * 64, "", None):
                with self.assertRaises(V.Refusal):
                    V.guard(path, bad)

    def test_frozen_flag_and_time_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            for changes in ({"frozen_before_outcomes": False}, {"frozen_at": None}, {"status": "frozen"}):
                path = frozen_copy(tmp, **changes)
                with self.assertRaises(V.Refusal):
                    V.guard(path, sha(path))

    def test_guard_token_cannot_be_forged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = frozen_copy(tmp)
            token = V.guard(path, sha(path).upper())
            self.assertIsInstance(token, V.FrozenProtocol)
        with self.assertRaises(V.Refusal):
            V.FrozenProtocol({"status": "frozen_pre_outcome"}, "0" * 64, object())
        with self.assertRaises(V.Refusal):
            V._data_pass(argparse.Namespace(), object())

    def test_freeze_record_required_and_well_formed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(V.Refusal):
                V.freeze_record_sha(Path(tmp) / "missing.json")
            template = BASE / "receipts" / "freeze-record.template.json"
            with self.assertRaises(V.Refusal):
                V.freeze_record_sha(template)
            rec = Path(tmp) / "rec.json"
            rec.write_text(json.dumps({"protocol_sha256": "A" * 64}))
            self.assertEqual(V.freeze_record_sha(rec), "a" * 64)


class RunRefuses(unittest.TestCase):
    """run() itself refuses the committed draft before any database or pin work."""

    def call(self, **kw):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(V.S, "duck", side_effect=AssertionError("database opened")), \
                mock.patch.object(V, "verify_pins", side_effect=AssertionError("pins reached")):
            rec = Path(tmp) / "freeze-record.json"
            rec.write_text(json.dumps({"protocol_sha256": kw.pop("record_sha", sha(PROTOCOL))}))
            a = argparse.Namespace(root=Path(tmp), daily=Path(tmp) / "none.parquet", freeze_record=rec, **kw)
            with self.assertRaises(V.Refusal) as cm:
                V.run(a)
            return cm.exception.reason

    def test_draft_refused_with_matching_record(self):
        self.assertIn("not frozen", self.call(protocol_sha256=None))

    def test_cli_sha_must_match_record(self):
        self.assertIn("differs from the freeze record", self.call(protocol_sha256="f" * 64))

    def test_record_for_other_bytes_refused(self):
        self.assertIn("sha256 mismatch", self.call(protocol_sha256=None, record_sha="e" * 64))

    def test_main_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()) as err, \
                mock.patch.object(V.S, "duck", side_effect=AssertionError("database opened")):
            code = V.main(["--root", tmp, "--daily", str(Path(tmp) / "x.parquet"), "--freeze-record", str(Path(tmp) / "none.json")])
        self.assertEqual(code, 2)
        self.assertIn("REFUSED: freeze record missing", err.getvalue())


def synthetic_months(n_months, premium, seed=7, n_long=60, n_short=150, noise=0.03, common=0.02, spy_gap=0.0):
    rng = random.Random(seed)
    months = []
    for i in range(n_months):
        t = (2017 + i // 12, i % 12 + 1)
        mkt = rng.gauss(0.008, common)
        rows = {}
        for j in range(n_long + n_short):
            expected = j < n_long
            ret = mkt + (premium if expected else 0.0) + rng.gauss(0, noise)
            rows[f"S{i % 3}_{j}"] = {"lane": "main", "eligible": True, "expected": expected, "weight": 1e6 * (1 + j % 7),
                                     "ret": ret, "proxy": abs(rng.gauss(0, 0.05)) if expected else None,
                                     "price": 30.0, "dv": 1e7}
        months.append({"t": t, "d": date(t[0], t[1], 1), "rows": rows, "spy": mkt + spy_gap})
    return months


FEES = {"sec_section31": {"rows": [{"from": "2016-01-01", "to": None, "usd_per_million": 20.0}]},
        "finra_taf_covered_equity": {"rows": [{"from": "2016-01-01", "to": None, "usd_per_share": 0.0002}]}}


class Core(unittest.TestCase):
    def test_planted_premium_adopted(self):
        res = V.evaluate_core(synthetic_months(116, 0.02), FEES)
        it = res["items"]
        for k in ("EAP-1", "EAP-2", "EAP-4"):
            self.assertTrue(it[k]["rejected"], k)
            self.assertEqual(it[k]["n_valid_months"], 116)
        self.assertEqual((it["EAP-2"]["family"], it["EAP-1"]["family"]), ("primary", "secondary"))
        self.assertEqual(res["decision"], "adopt_for_pre_positioning_research")
        self.assertLess(it["EAP-4"]["mean_monthly"], it["EAP-2"]["mean_monthly"])
        self.assertEqual(set(it["EAP-2"]["sensitivity"]), {"nw3", "nw12"})
        self.assertEqual(it["EAP-2"]["nw_lags"], 4)
        self.assertGreater(it["EAP-2"]["upper_bound_95_one_sided"], it["EAP-2"]["mean_monthly"])
        self.assertIsNone(it["EAP-2"]["report"])
        d = res["descriptive"]
        self.assertGreater(d["break_even_cost_per_unit_turnover"], d["measured_cost_per_unit_turnover"])
        self.assertIn("eap4_mover_v1_sensitivity", d)

    def test_null_is_no_evidence_underpowered_with_wording(self):
        res = V.evaluate_core(synthetic_months(116, 0.0, seed=11), FEES)
        self.assertEqual(res["decision"], "no_evidence_underpowered")
        rep = res["items"]["EAP-2"]["report"]
        self.assertTrue(rep.startswith("not rejected at the preregistered level; the design had 80% power only above ≈"))
        self.assertTrue(rep.endswith("%/month, so an effect of the published size is not ruled out"))

    def test_benchmark_is_spy_not_sample_market(self):
        # Long leg beats non-announcers, but SPY beats the long leg: EAP-1 yes, EAP-2 no.
        res = V.evaluate_core(synthetic_months(116, 0.01, seed=5, spy_gap=0.03), FEES)
        self.assertTrue(res["items"]["EAP-1"]["rejected"])
        self.assertFalse(res["items"]["EAP-2"]["rejected"])
        self.assertFalse(res["items"]["EAP-4"]["rejected"])  # sequence stops after EAP-2
        self.assertEqual(res["decision"], "long_short_premium_only")
        self.assertGreater(res["descriptive"]["l_minus_m"]["mean_monthly"], 0)

    def test_sequence_stops_when_eap2_fails_even_if_eap4_p_small(self):
        items = {"EAP-2": 0.2, "EAP-4": 0.0001}
        self.assertEqual(V.S.fixed_sequence(list(items.items()), 0.05), {"EAP-2": False, "EAP-4": False})

    def test_small_premium_eaten_by_costs(self):
        months = synthetic_months(116, 0.004, seed=3, noise=0.01, common=0.005)
        table = {"main_lane": [{"price_min": 0, "price_max": 1e18, "dv_min": 0, "dv_max": 1e30, "half_spread": 0.004}],
                 "small_cap_lane_flat": 0.01}
        res = V.evaluate_core(months, FEES, {"measured": table})
        self.assertTrue(res["items"]["EAP-2"]["rejected"])
        self.assertFalse(res["items"]["EAP-4"]["rejected"])
        self.assertEqual(res["decision"], "premium_exists_not_tradable")

    def test_invalid_months_are_excluded_not_zero(self):
        months = synthetic_months(116, 0.02)
        for m in months[:20]:
            m["rows"] = {s: r for s, r in m["rows"].items() if not r["expected"]}  # no long leg
        for m in months[20:25]:
            m["spy"] = None
        res = V.evaluate_core(months, FEES)
        self.assertEqual(res["items"]["EAP-2"]["n_valid_months"], 91)
        self.assertEqual(res["items"]["EAP-2"]["status"], "inconclusive_below_minimum")
        self.assertEqual(res["items"]["EAP-1"]["n_valid_months"], 96)
        self.assertTrue(all(m["eap2"] is None for m in res["months"][:25]))

    def test_minimum_samples(self):
        res = V.evaluate_core(synthetic_months(116, 0.02, n_long=9), FEES)
        self.assertEqual(res["items"]["EAP-1"]["status"], "inconclusive_below_minimum")
        self.assertFalse(res["items"]["EAP-1"]["rejected"])
        self.assertEqual(res["items"]["EAP-3"]["n_valid_months"], 0)

    def test_capped_weights_in_series(self):
        months = synthetic_months(3, 0.0)
        first = next(s for s, r in months[0]["rows"].items() if r["expected"])
        months[0]["rows"][first]["weight"] = 1e12
        s = V.month_series(months[0]["rows"], months[0]["spy"])
        self.assertAlmostEqual(s["max_w_long"], 0.02)
        self.assertGreater(s["eff_n_long"], 40)

    def test_delisted_holding_sold(self):
        months = synthetic_months(2, 0.0)
        gone = next(s for s, r in months[0]["rows"].items() if r["expected"])
        months[1]["rows"] = {s: r for s, r in months[1]["rows"].items() if s != gone}
        self.assertGreater(V.cost_pass(months, FEES)[1]["turnover"], 0)


try:
    import duckdb  # noqa: F401
    HAVE_DUCKDB = True
except ImportError:  # the system python3 has no DuckDB; the tool Python runs these
    HAVE_DUCKDB = False

N_SYN = 40


def build_synthetic_inputs(root: Path, daily: Path) -> None:
    import datetime as dt
    import gzip
    con = duckdb.connect()
    con.execute(f"""COPY (
        SELECT sym AS symbol, s::DATE AS session_date,
               20 + 5 * sin(epoch(s) / 86400 / 30 + i) AS raw_c, 200000.0 AS raw_v,
               20 + 5 * sin(epoch(s) / 86400 / 30 + i) AS all_c
        FROM (SELECT i, CASE WHEN i = {N_SYN} THEN 'SPY' WHEN i < {N_SYN} THEN 'S' || lpad(i::VARCHAR, 2, '0')
                             ELSE 'FILL' || i::VARCHAR END AS sym
              FROM range(0, {N_SYN + 1 + 1000}) t(i)) syms,  -- 1,000 fillers meet the real calendar threshold
             generate_series(TIMESTAMP '2016-01-04', TIMESTAMP '2026-09-30', INTERVAL 1 DAY) g(s)
        WHERE isodow(s) < 6) TO '{daily}' (FORMAT parquet)""")
    rows = []
    for i in range(N_SYN):
        cik = f"{i + 1:010d}"
        for y in range(2015, 2027):
            for m in range(1, 13):
                if (m - 1) % 3 != i % 3 or (y, m) > (2026, 9):
                    continue
                ann = dt.date(y, m, 15)
                rows.append({"cik": cik, "accession": f"{cik}-{y}{m:02d}-8k", "form": "8-K", "items": "2.02,9.01",
                             "filing_date": ann.isoformat(), "report_date": ann.isoformat(),
                             "acceptance": f"{ann}T12:00:00.000Z"})
                period_end = dt.date(y, m, 1) - dt.timedelta(days=1)
                filed = ann + dt.timedelta(days=20)
                rows.append({"cik": cik, "accession": f"{cik}-{y}{m:02d}-10q", "form": "10-Q", "items": "",
                             "filing_date": filed.isoformat(), "report_date": period_end.isoformat(),
                             "acceptance": f"{filed}T21:00:00.000Z"})
    (root / "derived").mkdir(parents=True)
    (root / "receipts").mkdir()
    (root / "derived" / "filings.jsonl.gz").write_bytes(gzip.compress("\n".join(json.dumps(r) for r in rows).encode()))
    (root / "universe.json").write_text(json.dumps({"ciks": {f"{i + 1:010d}": [f"S{i:02d}"] for i in range(N_SYN)}}))


@unittest.skipUnless(HAVE_DUCKDB, "DuckDB not installed in this interpreter")
class AccuracyCli(unittest.TestCase):
    def test_accuracy_cli_on_regular_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_synthetic_inputs(root, root / "daily.parquet")
            out = root / "receipts" / "acc.json"
            with contextlib.redirect_stdout(io.StringIO()):
                V.E.cmd_accuracy(argparse.Namespace(root=root, daily=root / "daily.parquet", out=out))
            r = json.loads(out.read_text())
        self.assertFalse(r["outcomes_computed"])
        main = r["monthly_rule"]["main"]
        self.assertEqual((main["precision_expected_month_correct"], main["recall_actual_in_expected_month"]), (1.0, 1.0))
        self.assertEqual(main["firm_months"], N_SYN * 116)
        self.assertEqual(r["event_time_rule_main"]["share_abs_error_le_7d"], 1.0)


@unittest.skipUnless(HAVE_DUCKDB, "DuckDB not installed in this interpreter")
class FrozenEndToEnd(unittest.TestCase):
    """SYN: a frozen, pinned, committed copy of the study in a scratch git repository runs the real CLI."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        cls.repo = base / "repo"
        cls.study = cls.repo / "blueprints/us-equities/sota-mover/eap"
        (cls.study / "data").mkdir(parents=True)
        (cls.study / "receipts").mkdir()
        for f in ("eap_signal.py", "expected_dates.py", "evaluate.py", "collect_edgar.py", "spreads.py"):
            shutil.copy2(BASE / f, cls.study / f)
        shutil.copy2(BASE / "data" / "cost-table-eap-v1.json", cls.study / "data")
        fees = cls.repo / "blueprints/us-equities/mover-v3/data"
        fees.mkdir(parents=True)
        shutil.copy2(REPO / "blueprints/us-equities/mover-v3/data/fees-v3.json", fees)
        (cls.repo / ".gitignore").write_text("__pycache__/\n")
        cls.root, cls.daily = base / "private", base / "daily.parquet"
        build_synthetic_inputs(cls.root, cls.daily)
        # Pins are computed from the copy itself before the protocol is written (the protocol is not pinned).
        p = json.loads(PROTOCOL.read_text())
        p.update({"status": "frozen_pre_outcome", "frozen_before_outcomes": True, "frozen_at": "2026-09-30T00:00:00Z"})
        (cls.study / "protocol.json").write_text(json.dumps(p, indent=1))
        pins = json.loads(cls.cli("--print-pins").stdout)
        p["pins"] = {"note": "synthetic", **pins}
        (cls.study / "protocol.json").write_text(json.dumps(p, indent=1))
        cls.git("init", "-q")
        cls.git("add", "-A")
        cls.git("commit", "-qm", "frozen synthetic study")
        (cls.study / "receipts" / "freeze-record.json").write_text(json.dumps({"protocol_sha256": sha(cls.study / "protocol.json")}))
        cls.git("add", "-A")
        cls.git("commit", "-qm", "freeze record")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def git(cls, *args):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], cwd=cls.repo,
                              env=hermetic_git_environment(), check=True, capture_output=True, text=True)

    @classmethod
    def cli(cls, *extra):
        return subprocess.run([sys.executable, str(cls.study / "evaluate.py"), "--root", str(cls.root), "--daily", str(cls.daily), *extra],
                              capture_output=True, text=True, env=hermetic_git_environment())

    def test_1_runs_when_frozen_pinned_and_clean(self):
        out = Path(self.tmp.name) / "result.json"
        r = self.cli("--out", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        res = json.loads(out.read_text())
        self.assertEqual(res["git_head"], self.git("rev-parse", "HEAD").stdout.strip())
        self.assertEqual(res["protocol_sha256"], sha(self.study / "protocol.json"))
        self.assertEqual(len(res["months"]), 116)
        self.assertGreaterEqual(res["items"]["EAP-1"]["n_valid_months"], 100)
        self.assertGreater(res["descriptive"]["flags"]["spy_complete"], 100)
        self.assertGreater(res["descriptive"]["event_time"]["with_prices"], 0)
        self.assertIn(res["decision"], {"adopt_for_pre_positioning_research", "premium_exists_not_tradable",
                                        "long_short_premium_only", "no_evidence_underpowered"})

    def test_2_dirty_tree_refused(self):
        extra = self.study / "scratch.txt"
        extra.write_text("x")
        try:
            r = self.cli()
        finally:
            extra.unlink()
        self.assertEqual(r.returncode, 2)
        self.assertIn("uncommitted changes", r.stderr)

    def test_3_pin_mismatch_refused(self):
        uni = self.root / "universe.json"
        original = uni.read_bytes()
        uni.write_bytes(original + b" ")
        try:
            r = self.cli()
        finally:
            uni.write_bytes(original)
        self.assertEqual(r.returncode, 2)
        self.assertIn("pin mismatch: private_inputs/universe.json", r.stderr)


if __name__ == "__main__":
    unittest.main()
