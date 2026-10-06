"""The GPT Researcher entry point of the new WSL distribution (tools/research/gpt_researcher.sh), run against stand-ins.

A stand-in checkout replaces the upstream source: its gpt_researcher.config.Config reads the JSON file and the environment
the way upstream's does at 0957c301 (config.py: load_config, _set_attributes, parse_llm), and its cli.py records its
arguments and environment instead of researching. Nothing is installed and no network is used. These are this project's
checks of its own wrapper, not upstream acceptance: the wave-2 research ruling (changes 2-5) and the synthesis X18.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/research/gpt_researcher.sh"
CONFIG = ROOT / "tools/research/gpt-researcher.config.json"
MEASURED_RECORD = ROOT / "evidence/artifacts/new-wsl-layer-consensus-20261002/wave2-records.json"
AMENDMENT_RECORD = ROOT / "evidence/artifacts/final-architecture-round2-20261004/integration-resolutions.json"
GATEWAY = "http://127.0.0.1:21128/v1"
# The host timer, found as the wrapper finds its own: GNU coreutils' timeout on PATH, else gtimeout, Homebrew coreutils'
# name for it on macOS. macOS has no timeout in /usr/bin or /bin (run 37141171758: exit 127, "env: timeout: No such file or
# directory"), and the GitHub runner image of the CI's macos-15 label lists neither coreutils, timeout nor gtimeout
# (actions/runner-images: README.md L34 at a99056ad maps macos-15 to macOS 15 Arm64; images/macos/macos-15-arm64-Readme.md
# at f95c0c79 and images/macos/macos-15-Readme.md at 07cc2190, section Utilities).
TIMER = shutil.which("timeout") or shutil.which("gtimeout")
NO_TIMER = ("no supported timer on PATH (timeout from GNU coreutils, or gtimeout from Homebrew coreutils), so the research "
            "run fails closed here; test_the_run_fails_closed_without_a_supported_timer covers that")

STAND_IN_CONFIG = textwrap.dedent('''
    import json
    import os


    class Config:
        """Stand-in: upstream merges the file over its defaults and lets an environment variable override a key."""

        def __init__(self, config_path=None):
            path = config_path or os.environ.get("CONFIG_PATH")
            values = {"RETRIEVER": "tavily", "FAST_LLM": "openai:gpt-4o-mini", "SMART_LLM": "openai:gpt-4.1",
                      "STRATEGIC_LLM": "openai:o4-mini", "LLM_KWARGS": {}, "CONTEXT_FILTER": "embeddings"}
            if path and os.path.exists(path):
                with open(path, encoding="utf-8") as handle:
                    values.update(json.load(handle))
            for key, value in values.items():
                setattr(self, key.lower(), os.environ.get(key, value))
            self.retrievers = [name.strip() for name in os.environ.get("RETRIEVER", values["RETRIEVER"]).split(",")]
            for role in ("fast", "smart", "strategic"):
                provider, model = getattr(self, role + "_llm").split(":", 1)
                setattr(self, role + "_llm_provider", provider)
                setattr(self, role + "_llm_model", model)
''')
STAND_IN_CLI = textwrap.dedent('''
    import json
    import os
    import sys

    os.makedirs("outputs", exist_ok=True)
    with open("cli-call.json", "w", encoding="utf-8") as handle:
        json.dump({"argv": sys.argv[1:], "env": dict(os.environ), "cwd": os.getcwd()}, handle)
    with open("outputs/report.md", "w", encoding="utf-8") as handle:
        handle.write("# Report\\n\\n## References\\n" + "".join(f"- https://example.org/{n}\\n" for n in range(6)))
    print("Report written to 'outputs/report.md'")
''')


class ResearchEntry(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="gptr-entry-"))
        self.addCleanup(shutil.rmtree, self.temp)
        checkout = self.temp / "data/new-wsl-native-stack/tools/gpt-researcher"
        (checkout / "gpt_researcher/config").mkdir(parents=True)
        (checkout / "gpt_researcher/__init__.py").write_text("")
        (checkout / "gpt_researcher/config/__init__.py").write_text(STAND_IN_CONFIG)
        (checkout / "cli.py").write_text(STAND_IN_CLI)
        (checkout / ".venv/bin").mkdir(parents=True)
        os.symlink(sys.executable, checkout / ".venv/bin/python")
        self.checkout = checkout
        self.env = {"HOME": str(self.temp / "home"), "PATH": os.environ["PATH"], "XDG_DATA_HOME": str(self.temp / "data"),
                    "XDG_STATE_HOME": str(self.temp / "state"), "RETRIEVER": "tavily", "LEAKED_PARENT_VARIABLE": "x"}

    def run_script(self, *args, config=None):
        env = dict(self.env)
        if config is not None:
            path = self.temp / "config.json"
            path.write_text(json.dumps(config))
            env["GPTR_CONFIG_SOURCE"] = str(path)
        return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=120)

    @staticmethod
    def run_dir(result):
        return Path(next(line for line in result.stdout.splitlines() if line.startswith("run directory: "))[15:])

    def provide_timer(self):
        """(path, record) of the timer this fixture puts first on the wrapper's PATH: a `timeout` that writes how it was run
        to `record` (the run's environment is scrubbed, so the path is written into the program) and then runs TIMER."""
        if TIMER is None:
            self.skipTest(NO_TIMER)
        timer_bin = self.temp / "timer-bin"
        timer_bin.mkdir()
        record = self.temp / "timer-call"
        (timer_bin / "timeout").write_text(f"#!/bin/sh\nprintf '%s\\n' \"$0\" \"$@\" > '{record}'\nexec '{TIMER}' \"$@\"\n",
                                           encoding="utf-8")
        (timer_bin / "timeout").chmod(0o755)
        self.env["PATH"] = f"{timer_bin}{os.pathsep}{self.env['PATH']}"
        return timer_bin / "timeout", record

    def test_the_committed_configuration_matches_the_measured_profile_and_dated_amendment_without_a_key(self):
        # The retained ruling binds the baseline to session 80. The 2026-10-05
        # amendment binds these exact config bytes to #637's source compatibility
        # corrections; it makes no new model-run or delivered-effort claim.
        amendment = json.loads(AMENDMENT_RECORD.read_text())["repair_round_4"]["research_configuration_amendment"]
        self.assertEqual(amendment["date_utc"], "2026-10-05")
        self.assertFalse(amendment["measurement_performed"])
        self.assertEqual(amendment["configuration_sha256"], hashlib.sha256(CONFIG.read_bytes()).hexdigest())
        self.assertEqual(amendment["measured_record"]["path"], str(MEASURED_RECORD.relative_to(ROOT)))
        self.assertEqual(amendment["measured_record"]["sha256"], hashlib.sha256(MEASURED_RECORD.read_bytes()).hexdigest())
        ruling = json.loads(MEASURED_RECORD.read_text())["layers"]["gpt-runtimes"]["ruling"]
        self.assertIn("session 80's config.json", ruling["changes"]["2"])
        self.assertIn("cx/gpt-6.1-sol-high and cx/gpt-6.1-sol-max", ruling["decided_default"])
        config = json.loads(CONFIG.read_text())
        for field, value in amendment["preserved_measured_values"].items():
            found = config
            for part in field.split("."):
                found = found[part]
            self.assertEqual(found, value, field)
        for field, change in amendment["compatibility_amendments"].items():
            found = config
            for part in field.split("."):
                found = found[part]
            self.assertEqual(found, change["value"], field)
        self.assertNotIn("api_key", config["LLM_KWARGS"])
        self.assertEqual(config["LLM_KWARGS"]["base_url"], GATEWAY)
        self.assertEqual(config["LLM_KWARGS"]["max_tokens"], 12000)
        self.assertEqual((config["RETRIEVER"], config["CONTEXT_FILTER"]), ("duckduckgo", "keyword"))
        self.assertEqual((config["FAST_LLM"], config["SMART_LLM"], config["STRATEGIC_LLM"]),
                         ("openai:cx/gpt-6.1-sol-high", "openai:cx/gpt-6.1-sol", "openai:cx/gpt-6.1-sol"))
        self.assertEqual(config["LLM_KWARGS"]["reasoning_effort"], "xhigh")
        self.assertEqual((config["MAX_SCRAPER_WORKERS"], config["SCRAPER_RATE_LIMIT_DELAY"], config["BROWSE_CHUNK_MAX_LENGTH"],
                          config["TOTAL_WORDS"]), (4, 0.5, 4096, 1500))

    def test_the_preflight_passes_and_writes_one_copy_per_run(self):
        result = self.run_script("--preflight-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("preflight passed", result.stdout)
        copy = json.loads((self.run_dir(result) / "config.json").read_text())
        self.assertEqual(copy["LLM_KWARGS"]["base_url"], GATEWAY)
        self.assertNotIn("api_key", copy["LLM_KWARGS"])
        self.assertEqual(copy["LLM_KWARGS"]["default_headers"]["x-omniroute-session-id"], "gptr-" + self.run_dir(result).name)
        self.assertNotIn("x-omniroute-session", copy["LLM_KWARGS"]["default_headers"])
        self.assertFalse((self.run_dir(result) / "cli-call.json").exists())

    def test_the_preflight_fails_closed_and_the_research_never_starts(self):
        base = json.loads(CONFIG.read_text())
        cases = {
            "retrievers": dict(base, RETRIEVER="tavily"),
            "context filter": dict(base, CONTEXT_FILTER="embeddings"),
            "fast model": dict(base, FAST_LLM="openai:gpt-4o-mini"),
        }
        for problem, config in cases.items():
            with self.subTest(problem=problem):
                result = self.run_script("a query", config=config)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("preflight failed", result.stderr)
                self.assertIn(problem, result.stderr)
                self.assertNotIn("Report written", result.stdout)

    def test_the_run_is_research_report_only_in_a_scrubbed_environment(self):
        timer, record = self.provide_timer()
        result = self.run_script("Ubuntu 26.04 WSL news this month")
        self.assertEqual(result.returncode, 0, result.stderr)
        # The watchdog: the CLI runs under the timer found before the scrub, run by its absolute path, with 1500 seconds.
        self.assertEqual(record.read_text().splitlines(),
                         [str(timer), "1500", str(self.checkout / ".venv/bin/python"), str(self.checkout / "cli.py"),
                          "Ubuntu 26.04 WSL news this month", "--report_type", "research_report", "--tone", "objective",
                          "--no-pdf", "--no-docx"])
        self.assertIn("Report written to 'outputs/report.md'", result.stdout)
        call = json.loads((self.run_dir(result) / "cli-call.json").read_text())
        self.assertEqual(call["argv"], ["Ubuntu 26.04 WSL news this month", "--report_type", "research_report", "--tone",
                                        "objective", "--no-pdf", "--no-docx"])
        env = call["env"]
        self.assertNotIn("LEAKED_PARENT_VARIABLE", env)
        self.assertNotIn("RETRIEVER", env)  # the parent's RETRIEVER=tavily would have overridden the file
        self.assertEqual(env["OPENAI_BASE_URL"], GATEWAY)
        self.assertEqual(env["OPENAI_API_KEY"], "local-loopback")
        self.assertEqual(env["HOME"], str(self.run_dir(result) / "home"))
        self.assertEqual(env["CONFIG_PATH"], str(self.run_dir(result) / "config.json"))
        self.assertEqual(Path(call["cwd"]), self.run_dir(result))

    def test_the_run_fails_closed_without_a_supported_timer(self):
        """Negative control: with neither timeout nor gtimeout on the caller's PATH, as on macOS without Homebrew's coreutils,
        the research run stops with exit 1 and names the missing timer. It does not drop the watchdog, and it does not reach
        a bare lookup in the scrubbed run (macOS run 37141171758: exit 127, "env: timeout: No such file or directory")."""
        bare = self.temp / "bin-without-a-timer"
        bare.mkdir()
        for name in ("bash", "env", "dirname", "date", "install"):  # what the wrapper runs from PATH before the research
            found = shutil.which(name)
            if found is None:
                self.skipTest(f"needs {name} to run the wrapper")
            (bare / name).symlink_to(found)
        self.env["PATH"] = str(bare)
        result = self.run_script("Ubuntu 26.04 WSL news this month")
        self.assertNotEqual(result.returncode, 127, result.stderr)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("No supported timer for the 1500-second watchdog", result.stderr)
        self.assertIn("neither timeout (GNU coreutils) nor gtimeout (Homebrew coreutils) is on PATH", result.stderr)
        self.assertNotIn("Report written", result.stdout)
        self.assertEqual(list((self.temp / "state").rglob("cli-call.json")), [])  # the CLI never started

    def test_the_script_names_no_other_report_type(self):
        code = "\n".join(line for line in SCRIPT.read_text().splitlines() if not line.lstrip().startswith("#"))
        self.assertNotIn("detailed_report", code)
        self.assertEqual(code.count("--report_type"), 1)
        self.assertIn("--report_type research_report", code)


if __name__ == "__main__":
    unittest.main()
