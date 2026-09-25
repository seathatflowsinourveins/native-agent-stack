"""SYN: evaluate.py refusal guard and the pure evaluation core on synthetic months."""
import contextlib
import hashlib
import io
import importlib.util
import json
import random
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

BASE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/sota-mover/eap"


def load(name):
    key = f"eap_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, BASE / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        spec.loader.exec_module(mod)
    return sys.modules[key]


V = load("evaluate")
PROTOCOL = BASE / "protocol.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class RefusalGuard(unittest.TestCase):
    def frozen_copy(self, tmp, **changes):
        p = json.loads(PROTOCOL.read_text())
        p.update({"status": "frozen_pre_outcome", "frozen_before_outcomes": True, "frozen_at": "2026-09-30T00:00:00Z"})
        p.update(changes)
        path = Path(tmp) / "protocol.json"
        path.write_text(json.dumps(p))
        return path

    def test_committed_draft_is_refused_even_with_its_own_sha(self):
        with self.assertRaises(V.Refusal) as cm:
            V.guard(PROTOCOL, sha(PROTOCOL))
        self.assertIn("not frozen", cm.exception.reason)
        self.assertEqual(cm.exception.code, 2)

    def test_sha_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.frozen_copy(tmp)
            with self.assertRaises(V.Refusal) as cm:
                V.guard(path, "0" * 64)
            self.assertIn("sha256 mismatch", cm.exception.reason)
            with self.assertRaises(V.Refusal):
                V.guard(path, "")

    def test_frozen_flag_and_time_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            for changes in ({"frozen_before_outcomes": False}, {"frozen_at": None}, {"status": "frozen"}):
                path = self.frozen_copy(tmp, **changes)
                with self.assertRaises(V.Refusal):
                    V.guard(path, sha(path))

    def test_frozen_matching_protocol_passes_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.frozen_copy(tmp)
            self.assertEqual(V.guard(path, sha(path).upper())["status"], "frozen_pre_outcome")

    def test_main_refuses_before_reading_any_price(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(V, "run", side_effect=AssertionError("run reached")), \
                mock.patch.object(V.S, "duck", side_effect=AssertionError("database opened")), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code = V.main(["--protocol-sha256", sha(PROTOCOL), "--root", tmp, "--daily", str(Path(tmp) / "none.parquet")])
            self.assertEqual(code, 2)
            frozen = self.frozen_copy(tmp)
            code = V.main(["--protocol-sha256", sha(frozen), "--protocol", str(frozen), "--root", tmp,
                           "--daily", str(Path(tmp) / "none.parquet")])
            self.assertEqual(code, 2)  # a frozen copy elsewhere is not this directory's protocol
            self.assertEqual(err.getvalue().count("REFUSED"), 2)


def synthetic_months(n_months, premium, seed=7, n_long=40, n_short=110, noise=0.03, common=0.02):
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
        months.append({"t": t, "d": date(t[0], t[1], 1), "rows": rows})
    return months


FEES = {"sec_section31": {"rows": [{"from": "2016-01-01", "to": None, "usd_per_million": 20.0}]},
        "finra_taf_covered_equity": {"rows": [{"from": "2016-01-01", "to": None, "usd_per_share": 0.0002}]}}


class Core(unittest.TestCase):
    def test_planted_premium_is_detected_and_net_of_costs(self):
        res = V.evaluate_core(synthetic_months(116, 0.02), FEES)
        items = res["items"]
        for k in ("EAP-1", "EAP-2", "EAP-4"):
            self.assertTrue(items[k]["holm_reject"], k)
            self.assertEqual(items[k]["n_valid_months"], 116)
        self.assertEqual(res["decision"], "adopt_for_pre_positioning_research")
        self.assertLess(items["EAP-4"]["mean_monthly"], items["EAP-2"]["mean_monthly"])
        d = res["descriptive"]
        self.assertGreater(d["break_even_cost_per_unit_turnover"], d["measured_cost_per_unit_turnover"])
        self.assertGreater(d["mean_monthly_turnover"], 0.5)

    def test_null_is_not_rejected(self):
        res = V.evaluate_core(synthetic_months(116, 0.0, seed=11), FEES)
        self.assertEqual(res["decision"], "no_premium")
        self.assertFalse(any(v["holm_reject"] for v in res["items"].values()))

    def test_small_premium_eaten_by_costs(self):
        res = V.evaluate_core(synthetic_months(116, 0.004, seed=3, noise=0.01, common=0.005), FEES)
        self.assertTrue(res["items"]["EAP-2"]["holm_reject"])
        self.assertFalse(res["items"]["EAP-4"]["holm_reject"])
        self.assertEqual(res["decision"], "premium_exists_not_tradable")

    def test_minimum_samples(self):
        months = synthetic_months(116, 0.02, n_long=9)
        res = V.evaluate_core(months, FEES)
        self.assertEqual(res["items"]["EAP-1"]["status"], "inconclusive_below_minimum")
        self.assertFalse(res["items"]["EAP-1"]["holm_reject"])
        few = V.evaluate_core(synthetic_months(60, 0.02), FEES)
        self.assertEqual(few["items"]["EAP-2"]["status"], "inconclusive_below_minimum")

    def test_eap3_needs_thirty_with_proxy(self):
        months = synthetic_months(116, 0.02, n_long=29)
        self.assertEqual(V.evaluate_core(months, FEES)["items"]["EAP-3"]["n_valid_months"], 0)

    def test_delisted_holding_sold_at_last_known_price(self):
        months = synthetic_months(2, 0.0)
        gone = next(s for s, r in months[0]["rows"].items() if r["expected"])
        months[1]["rows"] = {s: r for s, r in months[1]["rows"].items() if s != gone}
        costs = V.cost_pass(months, FEES)
        self.assertGreater(costs[1]["turnover"], 0)


try:
    import duckdb  # noqa: F401
    HAVE_DUCKDB = True
except ImportError:  # the system python3 has no DuckDB; the tool Python runs this class
    HAVE_DUCKDB = False


@unittest.skipUnless(HAVE_DUCKDB, "DuckDB not installed in this interpreter")
class SyntheticEndToEnd(unittest.TestCase):
    """SYN: accuracy CLI and evaluate.run on a synthetic parquet and filing store (never real data)."""

    N = 40

    @classmethod
    def setUpClass(cls):
        import datetime as dt
        import gzip
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.root, cls.daily = root, root / "daily.parquet"
        con = duckdb.connect()
        con.execute(f"""COPY (
            SELECT sym AS symbol, s::DATE AS session_date,
                   20 + 5 * sin(epoch(s) / 86400 / 30 + i) AS raw_c, 200000.0 AS raw_v,
                   20 + 5 * sin(epoch(s) / 86400 / 30 + i) AS all_c
            FROM (SELECT i, CASE WHEN i = {cls.N} THEN 'SPY' ELSE 'S' || lpad(i::VARCHAR, 2, '0') END AS sym
                  FROM range(0, {cls.N + 1}) t(i)) syms,
                 generate_series(TIMESTAMP '2016-01-04', TIMESTAMP '2026-09-30', INTERVAL 1 DAY) g(s)
            WHERE isodow(s) < 6) TO '{cls.daily}' (FORMAT parquet)""")
        rows = []
        for i in range(cls.N):
            cik = f"{i + 1:010d}"
            for y in range(2015, 2027):
                for m in range(1, 13):
                    if (m - 1) % 3 != i % 3 or (y, m) > (2026, 9):
                        continue
                    ann = dt.date(y, m, 15)
                    rows.append({"cik": cik, "accession": f"{cik}-{y}{m:02d}-8k", "form": "8-K", "items": "2.02,9.01",
                                 "filing_date": ann.isoformat(), "report_date": ann.isoformat(),
                                 "acceptance": f"{ann}T07:00:00.000Z"})
                    period_end = dt.date(y, m, 1) - dt.timedelta(days=1)
                    filed = ann + dt.timedelta(days=20)
                    rows.append({"cik": cik, "accession": f"{cik}-{y}{m:02d}-10q", "form": "10-Q", "items": "",
                                 "filing_date": filed.isoformat(), "report_date": period_end.isoformat(),
                                 "acceptance": f"{filed}T17:00:00.000Z"})
        (root / "derived").mkdir()
        (root / "receipts").mkdir()
        body = "\n".join(json.dumps(r) for r in rows).encode()
        (root / "derived" / "filings.jsonl.gz").write_bytes(gzip.compress(body))
        (root / "universe.json").write_text(json.dumps({"ciks": {f"{i + 1:010d}": [f"S{i:02d}"] for i in range(cls.N)}}))
        cls.patch = mock.patch.object(V.E, "CALENDAR_MIN_SYMBOLS", 1)
        cls.patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.patch.stop()
        cls.tmp.cleanup()

    def test_accuracy_cli_on_regular_calendar(self):
        import argparse
        out = self.root / "receipts" / "acc.json"
        with contextlib.redirect_stdout(io.StringIO()):
            V.E.cmd_accuracy(argparse.Namespace(root=self.root, daily=self.daily, out=out))
        r = json.loads(out.read_text())
        self.assertFalse(r["outcomes_computed"])
        main = r["monthly_rule"]["main"]
        self.assertEqual(main["precision_expected_month_correct"], 1.0)
        self.assertEqual(main["recall_actual_in_expected_month"], 1.0)
        self.assertEqual(main["firm_months"], self.N * 116)
        et = r["event_time_rule_main"]
        self.assertGreater(et["matched"], 0)
        self.assertEqual(et["share_abs_error_le_7d"], 1.0)

    def test_evaluate_run(self):
        import argparse
        protocol = json.loads(PROTOCOL.read_text())
        res = V.run(argparse.Namespace(root=self.root, daily=self.daily), protocol)
        self.assertEqual(len(res["months"]), 116)
        self.assertGreaterEqual(res["items"]["EAP-1"]["n_valid_months"], 100)
        self.assertEqual(res["items"]["EAP-3"]["n_valid_months"], 0)  # fewer than 30 expected announcers
        self.assertGreater(res["descriptive"]["flags"]["complete"], 0)
        self.assertGreater(res["descriptive"]["event_time"]["with_prices"], 0)
        for m in res["months"]:
            if m["eap1"] is not None:
                self.assertTrue(10 <= m["n_long"] <= 14 and m["n_short"] >= 26)


if __name__ == "__main__":
    unittest.main()
