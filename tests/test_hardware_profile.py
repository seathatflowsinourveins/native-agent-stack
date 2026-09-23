"""Unit tests for scripts/hardware_profile.py.

All non-trivial inputs here are synthetic (labelled): fabricated /proc text,
fabricated .wslconfig text, and fabricated `profiles` dicts passed directly to
the pure `recommend`/`_pick_tier` functions. No test spawns nvidia-smi/sysctl
or reads this host's real /proc/meminfo; that native measurement is exercised
manually and recorded as evidence/artifacts/sota-refresh-20260923/hw-profiles/this-host.json,
not asserted on here since it is host-dependent.
"""

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hardware_profile as hp  # noqa: E402


SYNTHETIC_PROFILES = {
    "$schema_id": "synthetic-test-profiles",
    "layers": {
        "workflow_concurrency": {"cap_default": 16, "reserved_cores": 2},
        "local_generation_model": {
            "tiers": [
                {"name": "cpu-only", "min_vram_gb": 0},
                {"name": "small", "min_vram_gb": 8},
                {"name": "large", "min_vram_gb": 20},
            ]
        },
        "embedding_semantic_rag": {
            "tiers": [
                {"name": "unsupported", "min_ram_gb": 0},
                {"name": "standard", "min_ram_gb": 32},
                {"name": "full", "min_ram_gb": 48},
            ]
        },
        "ecosystem_bounded_run": {"fraction": 0.5, "floor_gb": 2, "ceiling_gb": 64},
    },
}


class MeminfoParsingTests(unittest.TestCase):
    def test_reads_mem_total_kib(self):
        text = "MemTotal:       49327740 kB\nMemFree:  100 kB\n"
        self.assertEqual(hp._read_meminfo_total_kib(text), 49327740)

    def test_missing_field_returns_none(self):
        self.assertIsNone(hp._read_meminfo_total_kib("Nonsense: 1\n"))


class WslDetectionTests(unittest.TestCase):
    def test_detects_microsoft_kernel_string(self):
        self.assertTrue(hp.detect_wsl(
            "Linux version 6.6.87.2-microsoft-standard-WSL2 (root@buildkitsandbox)"
        ))

    def test_plain_linux_kernel_is_not_wsl(self):
        self.assertFalse(hp.detect_wsl("Linux version 6.8.0-generic (buildd@host)"))


class WslConfigParsingTests(unittest.TestCase):
    def test_parses_gb_memory_value(self):
        text = "[wsl2]\nmemory=48GB\nswap=8GB\n"
        self.assertEqual(hp._parse_wslconfig_memory_gb(text), 48.0)

    def test_parses_mb_memory_value(self):
        text = "[wsl2]\nmemory=2048MB\n"
        self.assertEqual(hp._parse_wslconfig_memory_gb(text), 2.0)

    def test_missing_memory_key_returns_none(self):
        self.assertIsNone(hp._parse_wslconfig_memory_gb("[wsl2]\nswap=8GB\n"))


class PickTierTests(unittest.TestCase):
    def test_picks_highest_eligible_tier(self):
        tiers = SYNTHETIC_PROFILES["layers"]["local_generation_model"]["tiers"]
        tier = hp._pick_tier(tiers, 24.0, "vram_gb")
        self.assertEqual(tier["name"], "large")

    def test_falls_back_to_lowest_tier_when_at_floor(self):
        tiers = SYNTHETIC_PROFILES["layers"]["local_generation_model"]["tiers"]
        tier = hp._pick_tier(tiers, 0.0, "vram_gb")
        self.assertEqual(tier["name"], "cpu-only")

    def test_none_value_returns_none(self):
        tiers = SYNTHETIC_PROFILES["layers"]["local_generation_model"]["tiers"]
        self.assertIsNone(hp._pick_tier(tiers, None, "vram_gb"))


class RecommendTests(unittest.TestCase):
    def test_synthetic_128gb_workstation_style_host(self):
        measured = {
            "cores": 32,
            "effective_ram_gb": 100.0,
            "gpu": {"name": "synthetic-gpu", "vram_gb": 24.0},
        }
        result = hp.recommend(measured, SYNTHETIC_PROFILES)
        self.assertEqual(result["workflow_concurrency_cap"], 16)
        self.assertEqual(result["local_generation_model_tier"], "large")
        self.assertEqual(result["embedding_semantic_rag_tier"], "full")
        self.assertEqual(result["ecosystem_bounded_run_memory_gb"], 50.0)

    def test_synthetic_low_core_low_ram_host_caps_below_16(self):
        measured = {"cores": 4, "effective_ram_gb": 8.0, "gpu": None}
        result = hp.recommend(measured, SYNTHETIC_PROFILES)
        self.assertEqual(result["workflow_concurrency_cap"], 2)
        self.assertEqual(result["local_generation_model_tier"], "cpu-only")
        self.assertEqual(result["embedding_semantic_rag_tier"], "unsupported")
        self.assertEqual(result["ecosystem_bounded_run_memory_gb"], 4.0)

    def test_synthetic_macos_unified_memory_host_uses_unified_memory_as_vram(self):
        measured = {"cores": 12, "effective_ram_gb": 48.0, "unified_memory_gb": 48.0, "gpu": None}
        result = hp.recommend(measured, SYNTHETIC_PROFILES)
        self.assertEqual(result["local_generation_model_tier"], "large")
        self.assertEqual(result["embedding_semantic_rag_tier"], "full")

    def test_bounded_run_memory_respects_ceiling(self):
        measured = {"cores": 8, "effective_ram_gb": 256.0, "gpu": None}
        result = hp.recommend(measured, SYNTHETIC_PROFILES)
        self.assertEqual(result["ecosystem_bounded_run_memory_gb"], 64.0)

    def test_single_core_host_never_reserves_below_one(self):
        measured = {"cores": 1, "effective_ram_gb": 4.0, "gpu": None}
        result = hp.recommend(measured, SYNTHETIC_PROFILES)
        self.assertGreaterEqual(result["workflow_concurrency_cap"], 1)


class BuildReportOnRealPlatformSmokeTest(unittest.TestCase):
    """A light smoke test that the real declarative profiles file loads and the
    report builds without raising on whatever platform runs the test suite.
    This is native_proven for the host it runs on, not a fixed-value assertion.
    """

    def test_report_builds_with_shipped_profiles_file(self):
        profiles_path = ROOT / "adoption" / "hardware-profiles.json"
        with profiles_path.open("r", encoding="utf-8") as handle:
            profiles = json.load(handle)
        report = hp.build_report(profiles)
        self.assertEqual(report["schema"], "hardware-profile-report-v1")
        self.assertIn("workflow_concurrency_cap", report["recommended"])
        self.assertGreaterEqual(report["recommended"]["workflow_concurrency_cap"], 1)


if __name__ == "__main__":
    unittest.main()
