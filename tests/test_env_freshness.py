"""Synthetic fixtures for scripts/env_freshness.py (no network, no real environments)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import env_freshness as E  # noqa: E402


def pypi(**versions):
    return {"releases": {v: [{"upload_time": f"{d}T00:00:00"}] for v, d in versions.items()}}


INDEX = {
    "nautilus-trader": pypi(**{"1.231.0": "2026-08-02", "2.0.0rc4": "2026-09-02", "2.0.0rc5": "2026-09-15"}),
    "alpaca-py": pypi(**{"0.43.0": "2026-07-01", "0.44.0": "2026-08-20"}),
    "deltalake": pypi(**{"1.6.4": "2026-09-01", "1.6.6": "2026-09-24"}),
    "duckdb": pypi(**{"1.4.0": "2026-09-01"}),
}


class Versions(unittest.TestCase):
    def test_ordering(self):
        vs = ["1.231.0", "2.0.0rc4", "2.0.0rc5", "2.0.0", "2.0.0a1", "2.0.0.dev1"]
        self.assertEqual(sorted(vs, key=E.version_key), ["1.231.0", "2.0.0.dev1", "2.0.0a1", "2.0.0rc4", "2.0.0rc5", "2.0.0"])

    def test_latest_stable_and_prerelease(self):
        idx = E.pypi_latest("nautilus-trader", lambda n: INDEX[n])
        self.assertEqual((idx["stable"], idx["prerelease"], idx["prerelease_released"]), ("1.231.0", "2.0.0rc5", "2026-09-15"))

    def test_statuses(self):
        get = lambda n: E.pypi_latest(n, lambda x: INDEX[x])
        self.assertEqual(E.status("2.0.0rc5", get("nautilus-trader")), "prerelease_current")
        self.assertEqual(E.status("2.0.0rc4", get("nautilus-trader")), "prerelease_behind")
        self.assertEqual(E.status("0.44.0", get("alpaca-py")), "current")
        self.assertEqual(E.status("1.6.4", get("deltalake")), "behind_stable")
        self.assertEqual(E.status("1.3.0", get("duckdb")), "behind_stable")
        old_pre = E.pypi_latest("x", lambda n: pypi(**{"0.1.0b3": "2025-01-01", "0.156.1": "2026-09-23"}))
        self.assertEqual((old_pre["stable"], old_pre["prerelease"]), ("0.156.1", None))
        self.assertEqual(E.status("9.9.9", get("duckdb")), "ahead_of_index")
        self.assertEqual(E.status("1.0", {"error": "HTTPError"}), "unknown")


class Report(unittest.TestCase):
    def test_build_from_fake_environments(self):
        dists = {"engine": {"nautilus-trader": "2.0.0rc5", "alpaca-py": "0.44.0", "requests": "2.32.0"},
                 "lake": {"deltalake": "1.6.4", "duckdb": "1.4.0"}}

        def runner(cmd, **kw):
            env = Path(cmd[0]).parents[1].name
            return subprocess.CompletedProcess(cmd, 0, json.dumps({"python": "3.12.3", "dists": dists[env]}), "")
        with tempfile.TemporaryDirectory() as tmp:
            tools = Path(tmp)
            for env in list(dists) + ["no-python"]:
                (tools / env / "bin").mkdir(parents=True)
            for env in dists:
                (tools / env / "bin" / "python").write_text("")
            report = E.build(tools, "test-host", runner=runner, fetch=lambda n: INDEX[n])
        self.assertEqual(report["environments"], 2)
        self.assertEqual(report["counts"], {"prerelease_current": 1, "current": 2, "behind_stable": 1})
        self.assertNotIn("requests", {r["package"] for r in report["rows"]})  # outside the watch list
        self.assertEqual(report["host_label"], "test-host")
        self.assertNotIn(tmp, json.dumps(report))  # no host paths in the published report


if __name__ == "__main__":
    unittest.main()
