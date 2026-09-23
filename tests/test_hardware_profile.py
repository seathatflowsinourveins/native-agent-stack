"""Unit tests for scripts/hardware_profile.py.

All non-trivial inputs here are synthetic (labelled): fabricated /proc text,
fabricated .wslconfig text, fabricated `nvidia-smi`/`sysctl` output (via
mocking `hardware_profile._run`), and fabricated `profiles` dicts passed
directly to the pure `recommend`/`_pick_tier` functions. No test reads this
host's real /proc/meminfo or spawns the real `nvidia-smi`/`sysctl` binaries;
that native measurement is exercised manually and recorded as
evidence/artifacts/sota-refresh-20260923/hw-profiles/this-host.json, not
asserted on here since it is host-dependent.
"""

import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hardware_profile as hp  # noqa: E402


SYNTHETIC_PROFILES = {
    "$schema_id": "synthetic-test-profiles",
    "layers": {
        "workflow_concurrency": {"cap_default": 16, "reserved_cores": 2},
        "local_generation_model": {
            "macos_unified_gpu_working_set_fraction": 0.6,
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
        "ecosystem_bounded_run": {
            "default_high_gb": 4,
            "default_max_gb": 6,
            "max_fraction_of_ram": 0.25,
            "high_to_max_ratio": 0.667,
            "ceiling_max_gb": 32,
        },
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


class CpuinfoParsingTests(unittest.TestCase):
    def test_reads_model_name(self):
        text = "processor\t: 0\nmodel name\t: Intel(R) Core(TM) Ultra 9 275HX\nflags\t\t: fpu\n"
        self.assertEqual(hp._read_cpuinfo_model(text), "Intel(R) Core(TM) Ultra 9 275HX")

    def test_missing_field_returns_none(self):
        self.assertIsNone(hp._read_cpuinfo_model("processor\t: 0\n"))


class WslConfigAmbiguityTests(unittest.TestCase):
    def test_find_all_wslconfigs_returns_every_match_sorted(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            users_dir = Path(tmp) / "Users"
            for name in ("bob", "alice"):
                profile = users_dir / name
                profile.mkdir(parents=True)
                (profile / ".wslconfig").write_text("[wsl2]\nmemory=32GB\n")
            candidates = hp._find_all_wslconfigs(users_dirs=[users_dir])
        self.assertEqual(len(candidates), 2)
        # sorted() means alphabetically-first ("alice") comes first, even
        # though "bob"'s directory was created second.
        self.assertTrue(str(candidates[0]).endswith("alice/.wslconfig"))
        self.assertTrue(str(candidates[1]).endswith("bob/.wslconfig"))

    def test_find_all_wslconfigs_empty_when_no_users_dir(self):
        self.assertEqual(hp._find_all_wslconfigs(users_dirs=[Path("/nonexistent-path-xyz")]), [])

    def test_find_wslconfig_returns_first_of_several(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            users_dir = Path(tmp) / "Users"
            for name in ("zed", "amy"):
                profile = users_dir / name
                profile.mkdir(parents=True)
                (profile / ".wslconfig").write_text("[wsl2]\nmemory=16GB\n")
            with mock.patch.object(hp, "_find_all_wslconfigs", return_value=hp._find_all_wslconfigs(users_dirs=[users_dir])):
                result = hp._find_wslconfig()
        self.assertTrue(str(result).endswith("amy/.wslconfig"))


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
        # max(6, round(100*0.25,1)=25.0) = 25.0, min(25.0, 32) = 25.0
        self.assertEqual(result["ecosystem_job_memory_max_gb"], 25.0)
        self.assertEqual(result["ecosystem_job_memory_high_gb"], round(25.0 * 0.667, 1))
        self.assertIsNone(result["concurrent_use_warning"])

    def test_synthetic_low_core_low_ram_host_caps_below_16(self):
        measured = {"cores": 4, "effective_ram_gb": 8.0, "gpu": None}
        result = hp.recommend(measured, SYNTHETIC_PROFILES)
        self.assertEqual(result["workflow_concurrency_cap"], 2)
        self.assertEqual(result["local_generation_model_tier"], "cpu-only")
        self.assertEqual(result["embedding_semantic_rag_tier"], "unsupported")
        # Below the default floor: max(6, round(8*0.25,1)=2.0) = 6 (the wrapper's own default).
        self.assertEqual(result["ecosystem_job_memory_max_gb"], 6.0)
        self.assertEqual(result["ecosystem_job_memory_high_gb"], round(6.0 * 0.667, 1))

    def test_synthetic_macos_unified_memory_host_scales_vram_by_working_set_fraction(self):
        measured = {"cores": 12, "effective_ram_gb": 48.0, "unified_memory_gb": 48.0, "gpu": None}
        result = hp.recommend(measured, SYNTHETIC_PROFILES)
        # 48 * 0.6 = 28.8 >= 20 -> "large", not the full 48 which would also
        # qualify if unified memory were treated as 100% usable VRAM.
        self.assertEqual(result["local_generation_model_tier"], "large")
        self.assertEqual(result["embedding_semantic_rag_tier"], "full")

    def test_synthetic_macos_unified_memory_host_warns_on_concurrent_use(self):
        measured = {"cores": 12, "effective_ram_gb": 48.0, "unified_memory_gb": 48.0, "gpu": None}
        result = hp.recommend(measured, SYNTHETIC_PROFILES)
        self.assertIsNotNone(result["concurrent_use_warning"])

    def test_discrete_gpu_host_never_triggers_concurrent_use_warning(self):
        measured = {"cores": 12, "effective_ram_gb": 48.0, "gpu": {"name": "x", "vram_gb": 24.0}}
        result = hp.recommend(measured, SYNTHETIC_PROFILES)
        self.assertIsNone(result["concurrent_use_warning"])

    def test_bounded_run_memory_respects_ceiling(self):
        measured = {"cores": 8, "effective_ram_gb": 256.0, "gpu": None}
        result = hp.recommend(measured, SYNTHETIC_PROFILES)
        # round(256*0.25,1)=64.0, min(64.0, 32) = 32.0 (ceiling_max_gb)
        self.assertEqual(result["ecosystem_job_memory_max_gb"], 32.0)
        self.assertEqual(result["ecosystem_job_memory_high_gb"], round(32.0 * 0.667, 1))

    def test_single_core_host_never_reserves_below_one(self):
        measured = {"cores": 1, "effective_ram_gb": 4.0, "gpu": None}
        result = hp.recommend(measured, SYNTHETIC_PROFILES)
        self.assertGreaterEqual(result["workflow_concurrency_cap"], 1)


class EffectiveRamGbTests(unittest.TestCase):
    """Covers the WSL RAM-source finding: measured /proc/meminfo must win over
    the .wslconfig configured ceiling whenever both are available."""

    def test_prefers_measured_meminfo_over_wslconfig_ceiling(self):
        value, source = hp._effective_ram_gb(47.0, 48.0)
        self.assertEqual(value, 47.0)
        self.assertEqual(source, "proc_meminfo")

    def test_falls_back_to_wslconfig_when_meminfo_unavailable(self):
        value, source = hp._effective_ram_gb(None, 48.0)
        self.assertEqual(value, 48.0)
        self.assertEqual(source, "wslconfig")

    def test_none_when_neither_available(self):
        value, source = hp._effective_ram_gb(None, None)
        self.assertIsNone(value)
        self.assertEqual(source, "wslconfig")


class DetectNvidiaGpuTests(unittest.TestCase):
    def test_parses_csv_output_into_name_and_vram_gb(self):
        with mock.patch.object(hp, "_run", return_value="NVIDIA GeForce RTX 5090 Laptop GPU, 24576 MiB\n"):
            gpu = hp.detect_nvidia_gpu()
        self.assertEqual(gpu["name"], "NVIDIA GeForce RTX 5090 Laptop GPU")
        self.assertEqual(gpu["vram_gb"], round(24576 / 1024.0, 1))
        self.assertEqual(gpu["evidence_class"], "native_proven")

    def test_missing_nvidia_smi_returns_none(self):
        with mock.patch.object(hp, "_run", return_value=None):
            self.assertIsNone(hp.detect_nvidia_gpu())

    def test_malformed_csv_line_returns_none(self):
        with mock.patch.object(hp, "_run", return_value="not,enough,to,parse\nbut still 3 commas"):
            gpu = hp.detect_nvidia_gpu()
        # 4 comma-separated parts is fine (>=2); the second field ("enough")
        # has no digits, so the vram_gb float parse fails -> None.
        self.assertIsNone(gpu)

    def test_empty_output_returns_none(self):
        with mock.patch.object(hp, "_run", return_value=""):
            self.assertIsNone(hp.detect_nvidia_gpu())


class MeasureMacosTests(unittest.TestCase):
    def _run_side_effect(self, ncpu, memsize, brand):
        def _side_effect(cmd):
            if cmd[-1] == "hw.ncpu":
                return ncpu
            if cmd[-1] == "hw.memsize":
                return memsize
            if cmd[-1] == "machdep.cpu.brand_string":
                return brand
            return None
        return _side_effect

    def test_parses_sysctl_output_on_arm64(self):
        with mock.patch.object(hp, "_run", side_effect=self._run_side_effect(
            "12\n", str(48 * 1024 ** 3) + "\n", "Apple M3 Pro\n",
        )):
            with mock.patch.object(hp.platform, "machine", return_value="arm64"):
                measured = hp.measure_macos(SYNTHETIC_PROFILES)
        self.assertEqual(measured["cores"], 12)
        self.assertEqual(measured["effective_ram_gb"], 48.0)
        self.assertEqual(measured["cpu_brand"], "Apple M3 Pro")
        self.assertTrue(measured["arm64"])
        self.assertEqual(measured["unified_memory_gb"], 48.0)

    def test_intel_mac_has_no_unified_memory(self):
        with mock.patch.object(hp, "_run", side_effect=self._run_side_effect(
            "8\n", str(16 * 1024 ** 3) + "\n", "Intel(R) Core(TM) i7\n",
        )):
            with mock.patch.object(hp.platform, "machine", return_value="x86_64"):
                measured = hp.measure_macos(SYNTHETIC_PROFILES)
        self.assertFalse(measured["arm64"])
        self.assertIsNone(measured["unified_memory_gb"])

    def test_missing_sysctl_falls_back_to_os_cpu_count(self):
        with mock.patch.object(hp, "_run", return_value=None):
            with mock.patch.object(hp.os, "cpu_count", return_value=4):
                measured = hp.measure_macos(SYNTHETIC_PROFILES)
        self.assertEqual(measured["cores"], 4)
        self.assertIsNone(measured["effective_ram_gb"])
        self.assertIsNone(measured["cpu_brand"])


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
