"""Offline checks for the local-inference-latest-20260926 preregistration.

Synthetic fixtures only: no model, server, GPU, SEC request or private file. The
window runs use fake systemctl, systemd-run, nvidia-smi and llama-server stand-ins;
the co-filer label check runs EdgarTools only when the catalyst SDK is installed.
"""
import copy
import hashlib
import importlib.util
import io
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock
import urllib.error

from scripts.validate_convergence import validate_record

ROOT = Path(__file__).resolve().parents[1]
REL = "blueprints/convergence-practice/local-inference-latest-20260926"
HERE = ROOT / REL


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ACQUIRE = load("li26_acquire_test", "acquire.py")
EVAL = load("li26_eval_test", "eval_arm.py")
ANALYZE = load("li26_analyze_test", "analyze.py")
PLAN = json.loads((HERE / "plan.json").read_text())
PLAN_SHA = hashlib.sha256((HERE / "plan.json").read_bytes()).hexdigest()

SUBMISSION = """<SEC-DOCUMENT>0000000001-20-000001.txt : 20200302
<SEC-HEADER>0000000001-20-000001.hdr.sgml : 20200302
<ACCEPTANCE-DATETIME>20200302161500
ACCESSION NUMBER:\t\t0000000001-20-000001
CONFORMED SUBMISSION TYPE:\t8-K
PUBLIC DOCUMENT COUNT:\t\t2
ITEM INFORMATION:\t\tResults of Operations and Financial Condition
ITEM INFORMATION:\t\tFinancial Statements and Exhibits
FILED AS OF DATE:\t\t20200302
</SEC-HEADER>
<DOCUMENT>
<TYPE>8-K
<SEQUENCE>1
<FILENAME>form8k.htm
<DESCRIPTION>8-K
<TEXT>
<html><head><title>Header title leak</title></head><body>
<div style="display:none"><ix:header>hidden dei facts</ix:header></div>
<p>Item&#160;2.02&nbsp;Results of   Operations</p><table><tr><td>Revenue</td><td>$1</td></tr></table>
<script>var hidden = 1;</script>
<p>Item 9.01 Financial Statements and Exhibits.</p>​
</body></html>
</TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>EX-99.1
<SEQUENCE>2
<FILENAME>ex99.htm
<TEXT>
<html><body>Press release exhibit text</body></html>
</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>
"""

HEADER = """<SEC-HEADER>{accession}.hdr.sgml : 20200302
<ACCEPTANCE-DATETIME>20200302161500
<ACCESSION-NUMBER>{accession}
<TYPE>8-K
<PUBLIC-DOCUMENT-COUNT>2
{items}<FILING-DATE>20200302
</SEC-HEADER>
"""

FILER_BLOCK = ("<FILER>\n<COMPANY-DATA>\n<CONFORMED-NAME>CO{i}\n<CIK>000000000{i}\n<ASSIGNED-SIC>4911\n"
               "<STATE-OF-INCORPORATION>DE\n<FISCAL-YEAR-END>1231\n</COMPANY-DATA>\n<FILING-VALUES>\n"
               "<FORM-TYPE>8-K\n<ACT>34\n<FILE-NUMBER>001-0000{i}\n<FILM-NUMBER>2000000{i}\n</FILING-VALUES>\n"
               "<BUSINESS-ADDRESS>\n<STREET1>1 MAIN ST\n<CITY>TOWN\n<STATE>DE\n<ZIP>19801\n<PHONE>555-0100\n"
               "</BUSINESS-ADDRESS>\n</FILER>\n")


def cofiled_header(filers, items="<ITEMS>2.02\n<ITEMS>9.01\n", accession="0000000001-20-000002"):
    """A tag-format .hdr.sgml header with `filers` FILER blocks (co-filers when two or more)."""
    return ("<SEC-HEADER>{a}.hdr.sgml : 20200302\n<ACCEPTANCE-DATETIME>20200302161500\n<ACCESSION-NUMBER>{a}\n"
            "<TYPE>8-K\n<PUBLIC-DOCUMENT-COUNT>2\n<PERIOD>20200302\n{items}<FILING-DATE>20200302\n"
            "<DATE-OF-FILING-DATE-CHANGE>20200302\n").format(a=accession, items=items) + \
        "".join(FILER_BLOCK.format(i=i) for i in range(1, filers + 1)) + "</SEC-HEADER>\n"


def header_labels(raw):
    """Synthetic stand-in for the native FilingHeader ITEMS parse (the SDK test runs the real one)."""
    declared = re.findall(r"^<ITEMS>(.+)$", raw.decode(), re.MULTILINE)
    return ACQUIRE.item_codes(",".join(declared) if declared else None)


class FrozenPlan(unittest.TestCase):
    def test_every_frozen_input_and_the_prompt_match_their_hashes(self):
        EVAL.verify_frozen(EVAL.load_plan(HERE / "plan.json"))
        ACQUIRE.verify_frozen(PLAN)
        self.assertEqual(hashlib.sha256((HERE / "prompt.txt").read_bytes()).hexdigest(), PLAN["prompt_sha256"])
        self.assertEqual(sorted(PLAN["frozen_inputs"]), sorted([
            f"{REL}/acquire.py", f"{REL}/analyze.py", f"{REL}/eval_arm.py", f"{REL}/prompt.txt",
            f"{REL}/window.sh", "blueprints/us-equities/catalyst-provenance/catalyst.py",
            "scripts/path_safety.py"]))

    def test_planned_record_validates_without_observations(self):
        result = validate_record(ROOT, f"{REL}/experiment.json")
        self.assertTrue(result["valid"], result["errors"])
        record = json.loads((HERE / "experiment.json").read_text())
        self.assertEqual((record["status"], record["lane"], record["observations"]), ("planned", "local-inference", []))
        self.assertEqual(PLAN["status"], "preregistered")
        plan_input = [entry for entry in record["frozen_inputs"]["inputs"] if entry["path"].endswith("plan.json")]
        self.assertEqual(plan_input[0]["sha256"], PLAN_SHA)

    def test_changed_frozen_values_are_refused(self):
        for path, bad in [(("serving", "context"), 4096), (("serving", "port"), 18232),
                          (("sampling", "temperature"), 0.7), (("sampling", "max_tokens"), 1024),
                          (("window", "minimum_free_mib"), 1024), (("window", "admission_floor_mib"), 8192),
                          (("window", "request_seconds"), 180), (("window", "max_segments"), 9),
                          (("window", "production_estimated_device_mib"), 8000),
                          (("sampling", "chat_template_kwargs"), {"enable_thinking": True})]:
            with self.subTest(path=path):
                plan = copy.deepcopy(PLAN)
                plan[path[0]][path[1]] = bad
                with self.assertRaises(ValueError):
                    EVAL.check_plan(plan)
        for arm_index, change in [(4, {"runtime": {"tag": "b99999", "commit": "0" * 40}}),
                                  (2, {"profile": {**PLAN["arms"][2]["profile"],
                                                   "draft": {"type": "draft-mtp", "filename": "MTP/x.gguf"}}}),
                                  (1, {"profile": {**PLAN["arms"][1]["profile"], "n_cpu_ffn": "20"}})]:
            with self.subTest(arm=arm_index):
                plan = copy.deepcopy(PLAN)
                plan["arms"][arm_index].update(change)
                with self.assertRaises(ValueError):
                    EVAL.check_plan(plan)
        plan = copy.deepcopy(PLAN)
        plan["task"]["input"]["head_chars"] = 20000
        with self.assertRaises(ValueError):
            ACQUIRE.check_plan(plan)
        ACQUIRE.check_plan(PLAN)

    def test_window_script_constants_match_the_plan(self):
        text = (HERE / "window.sh").read_text()
        window = PLAN["window"]
        for name, value in [("PORT", PLAN["serving"]["port"]), ("ADMISSION_FLOOR_MIB", window["admission_floor_mib"]),
                            ("MINIMUM_FREE_MIB", window["minimum_free_mib"]), ("WINDOW_SECONDS", window["window_seconds"]),
                            ("ARM_SECONDS", window["arm_seconds"]), ("STARTUP_SECONDS", window["startup_seconds"]),
                            ("RESTORE_RESERVE_SECONDS", window["restore_reserve_seconds"]),
                            ("MINIMUM_SEGMENT_SECONDS", window["minimum_segment_seconds"]),
                            ("QUERY_TIMEOUT_SECONDS", window["query_timeout_seconds"]),
                            ("STOP_TIMEOUT_SECONDS", window["stop_timeout_seconds"]),
                            ("MEMORY_MAX", window["memory_max"]),
                            ("PRODUCTION_UNIT_NAME", window["production_unit"]),
                            ("PRODUCTION_HEALTH", window["production_health"])]:
            with self.subTest(name=name):
                self.assertIn(f"readonly {name}={value}\n", text)
        self.assertIn(f"readonly COORDINATION_LINE='{window['coordination_line']}'", text)
        self.assertRegex((HERE / "README.md").read_text(), r"(?m)^GPU trials: \S")
        for forbidden in ("wsl --terminate", "wsl --shutdown", "native-stack-embeddings", "--production-health"):
            self.assertFalse(any(forbidden in line and not line.lstrip().startswith("#")
                                 for line in text.splitlines()), forbidden)

    def test_arm_argv_follows_the_frozen_profiles(self):
        c0 = EVAL.server_argv(PLAN, "C0", "/rt", "/models")
        self.assertEqual(c0[0], "/rt/llama-server")
        pairs = dict(zip(c0[1::2], c0[2::2]))
        for flag, value in [("--gpu-layers", "36"), ("--ctx-size", "8192"), ("--parallel", "1"), ("--fit", "off"),
                            ("--threads", "16"), ("--threads-batch", "24"), ("--batch-size", "512"),
                            ("--ubatch-size", "128"), ("--port", "18299"), ("--host", "127.0.0.1"),
                            ("--model", "/models/qwen3.8-27b-4ca7207/Qwen3.8-27B-UD-Q4_K_M.gguf")]:
            self.assertEqual(pairs[flag], value)
        self.assertNotIn("--spec-type", c0)
        self.assertNotIn("--n-cpu-ffn", c0)
        c1 = EVAL.server_argv(PLAN, "C1", "/rt", "/models")
        c1_pairs = dict(zip(c1[1::2], c1[2::2]))
        self.assertEqual((c1_pairs["--gpu-layers"], c1_pairs["--n-cpu-ffn"]), ("99", "20"))
        self.assertEqual(c1_pairs["--model"], pairs["--model"])
        self.assertNotIn("--spec-type", c1)
        c2 = EVAL.server_argv(PLAN, "C2", "/rt", "/models")
        self.assertEqual(c2[:c2.index("--spec-type")], [part.replace("li26-c1", "li26-c2") for part in c1])
        self.assertEqual(c2[c2.index("--spec-type"):], ["--spec-type", "draft-mtp", "--spec-draft-n-max", "3"])
        self.assertFalse(any(part.startswith("--spec-draft-model") or part.endswith("mtp-Qwen3.8-27B-Q4_0.gguf")
                             for part in c2))
        m = EVAL.server_argv(PLAN, "M", "/rt", "/models")
        self.assertIn("/models/mimo-v2.6-distill-qwen-9b-81baddc/MiMo-V2.6-Distill-Qwen-9B-Q8_0.gguf", m)
        for arm in ("B", "X"):
            with self.assertRaises(ValueError):
                EVAL.server_argv(PLAN, arm, "/rt", "/models")
        self.assertEqual([EVAL.admission_mib(PLAN, arm) for arm in ("C0", "C1", "C2", "M")],
                         [16384, 17151, 17535, 16384])

    def test_host_admission_arithmetic_is_consistent(self):
        gpu = PLAN["host"]["gpu_memory_at_planning"]
        self.assertEqual(gpu["used_mib"] + gpu["free_mib"], gpu["reportable_mib"])
        most_free = gpu["reportable_mib"] - round(0.16 * gpu["total_mib"])  # the embeddings unit's configured share
        self.assertEqual(most_free, 20213)
        allowed = PLAN["window"]["host_admission_arithmetic"]["windows_side_mib_allowed"]
        self.assertEqual(sorted(allowed), ["C0", "C1", "C2", "M"])
        for arm_id, windows_side in allowed.items():
            with self.subTest(arm=arm_id):
                self.assertEqual(windows_side, most_free - EVAL.admission_mib(PLAN, arm_id))
        c1_tasked = next(entry for entry in PLAN["not_arms"] if entry["name"].startswith("C1 as tasked"))
        self.assertEqual(c1_tasked["admission_free_mib"], c1_tasked["estimated_device_mib"] + 3072)
        self.assertEqual(most_free - c1_tasked["admission_free_mib"], 414)  # Windows side at most 414 MiB

    def test_every_arm_is_pinned_by_revision_hash_and_size(self):
        for arm in PLAN["arms"]:
            with self.subTest(arm=arm["id"]):
                model = arm["model"]
                self.assertRegex(model["revision"], r"^[0-9a-f]{40}$")
                self.assertRegex(model["sha256"], r"^[0-9a-f]{64}$")
                self.assertIsInstance(model["bytes"], int)
                self.assertTrue(model["license"])
        self.assertEqual({arm["id"]: arm["support_status"] for arm in PLAN["arms"]},
                         {"C0": "runnable", "C1": "runnable_if_admitted", "C2": "runnable_if_admitted",
                          "B": "runtime_unsupported", "M": "runnable", "X": "runtime_unsupported"})
        self.assertEqual([entry["status"] for entry in PLAN["not_arms"]],
                         ["resource_infeasible", "resource_infeasible_on_host", "resource_infeasible_on_host"])
        draft = PLAN["not_arms"][2]["draft_file"]
        self.assertEqual((draft["filename"], draft["bytes"]), ("MTP/mtp-Qwen3.8-27B-Q4_0.gguf", 1369590656))
        self.assertRegex(draft["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual([download["arm"] for download in PLAN["downloads"]], ["M"])


@unittest.skipUnless(shutil.which("bash"), "bash is required")
class WindowGate(unittest.TestCase):
    """window.sh refusals that happen before it queries the GPU or touches any unit.

    It runs from a temporary copy whose README keeps the PENDING line, so HERE,
    the plan and the coordination note all resolve inside the copy.
    """

    def run_window(self, *arguments, trailing=()):
        with tempfile.TemporaryDirectory() as temp:
            shutil.copy(HERE / "window.sh", temp)
            Path(temp, "README.md").write_text("GPU trials: PENDING\n")
            args = ["--acquisition", temp, "--inputs-sha256", "a" * 64, "--runtime-dir", temp,
                    "--models-dir", temp, "--state-dir", str(Path(temp) / "state")]
            result = subprocess.run(["bash", str(Path(temp) / "window.sh"), *arguments, *args, *trailing],
                                    capture_output=True, text=True, timeout=30,
                                    env={"PATH": "/usr/bin:/bin"})
            self.assertFalse(Path(temp, "state").exists())
        return result

    def test_pending_coordination_line_refuses_the_window(self):
        result = self.run_window("--arms", "C0,C1")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("another session owns GPU trials", result.stderr)

    def test_unsupported_duplicate_and_missing_arguments_are_refused(self):
        for arms, message in [(("--arms", "C0,B"), "runtime_unsupported"), (("--arms", "C0,C0"), "listed twice"),
                              (("--arms", "X"), "runtime_unsupported"), ((), "usage"),
                              (("--arms", "C0", "--production-health", "http://127.0.0.1:1/"), "unknown argument")]:
            with self.subTest(arms=arms):
                result = self.run_window(*arms)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(message, result.stderr)
        result = self.run_window("--arms", "C0", trailing=("--production-unit",))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("--production-unit needs a value", result.stderr)

    def test_only_the_production_generation_unit_can_be_stopped(self):
        for unit in ("native-stack-embeddings.service", "nativestack-generation", "default.target", ""):
            with self.subTest(unit=unit):
                result = self.run_window("--arms", "C0", "--production-unit", unit)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("--production-unit must be nativestack-generation.service or none", result.stderr)
                self.assertNotIn("another session", result.stderr)  # refused before the preflight


STUB_EVAL = textwrap.dedent("""\
    import os, sys, time
    args = sys.argv[1:]
    with open(os.environ["LI26_FAKE_LOG"], "a") as log:
        log.write("eval " + " ".join(args) + "\\n")
    command = args[0]
    if command == "next-segment":
        if os.environ.get("LI26_FAKE_NEXT") == "refuse":
            print("next-segment: arm C0 is already complete", file=sys.stderr)
            sys.exit(1)
        print("1 -")
    elif command == "predict":
        sys.exit(1 if os.environ.get("LI26_FAKE_PREDICT") == "short" else 0)
    elif command == "admission":
        print(16384)
    elif command == "argv":
        sys.stdout.write(os.environ["LI26_FAKE_SERVER"] + "\\0" + os.environ["LI26_FAKE_MARK"] + "\\0")
    elif command == "run":
        mode, deadline = os.environ.get("LI26_FAKE_RUN", "wait-server"), time.time() + 60
        while time.time() < deadline:
            if mode == "wait-server" and os.path.exists(os.environ["LI26_FAKE_MARK"]):
                sys.exit(3)
            time.sleep(0.1)
        sys.exit(3)
    """)

FAKES = {
    "systemctl": textwrap.dedent("""\
        #!/bin/bash
        printf 'systemctl %s\\n' "$*" >>"$LI26_FAKE_LOG"
        case " $* " in
          *" is-active "*) echo active ;;
          *" show "*) echo 21474836480 ;;
        esac
        exit 0
        """),
    "systemd-run": textwrap.dedent("""\
        #!/bin/bash
        printf 'systemd-run %s\\n' "$*" >>"$LI26_FAKE_LOG"
        scope=0
        while (($#)); do
          case $1 in
            --scope) scope=1 ;;
            --) shift; break ;;
          esac
          shift
        done
        if ((scope)); then exec "$@"; fi
        exit 0
        """),
    "nvidia-smi": textwrap.dedent("""\
        #!/bin/bash
        exec 8>>"$LI26_FAKE_DIR/nvsmi.lock"
        flock 8
        n=$(( $(cat "$LI26_FAKE_DIR/nvsmi.count" 2>/dev/null || echo 0) + 1 ))
        echo "$n" >"$LI26_FAKE_DIR/nvsmi.count"
        flock -u 8
        printf 'nvidia-smi call %s\\n' "$n" >>"$LI26_FAKE_LOG"
        if [[ ${LI26_FAKE_HANG_AT:-0} == "$n" ]]; then exec -a "li26-hang $LI26_FAKE_DIR" sleep 3600; fi
        echo "9000, ${LI26_FAKE_FREE:-17000}"
        """),
    "fake-server": textwrap.dedent("""\
        #!/bin/bash
        trap 'echo stopped >"$1"; exit 143' TERM
        while :; do sleep 0.1; done
        """),
}


@unittest.skipUnless(sys.platform.startswith("linux") and all(shutil.which(tool) for tool in
                                                              ("bash", "timeout", "flock", "pkill", "date")),
                     "Linux bash, coreutils, util-linux and procps are required")
class WindowRun(unittest.TestCase):
    """Whole windows against stand-ins: a hung GPU query, SIGTERM and refusals before any stop."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bin, self.here, self.state = self.root / "bin", self.root / "blueprint", self.root / "state"
        self.bin.mkdir()
        self.here.mkdir()
        shutil.copy(HERE / "window.sh", self.here)
        (self.here / "README.md").write_text("GPU trials: TRIALS DONE\n")
        (self.here / "eval_arm.py").write_text(STUB_EVAL)
        (self.here / "plan.json").write_text("{}\n")
        for name, body in FAKES.items():
            (self.bin / name).write_text(body)
            (self.bin / name).chmod(0o755)
        self.log = self.root / "calls.log"
        self.log.touch()
        self.env = {"PATH": f"{self.bin}:/usr/bin:/bin", "LI26_FAKE_LOG": str(self.log),
                    "LI26_FAKE_DIR": str(self.root), "LI26_FAKE_SERVER": str(self.bin / "fake-server"),
                    "LI26_FAKE_MARK": str(self.root / "server.stopped")}
        self.process = None

    def tearDown(self):
        # A failed run must not leave stand-ins behind: every one carries this unique temp root in its command line.
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.communicate()
        subprocess.run(["pkill", "-KILL", "-f", str(self.root)], capture_output=True)
        self.temp.cleanup()

    def start(self, **extra):
        args = ["bash", str(self.here / "window.sh"), "--arms", "C0", "--acquisition", str(self.root),
                "--inputs-sha256", "a" * 64, "--runtime-dir", str(self.root), "--models-dir", str(self.root),
                "--state-dir", str(self.state)]
        self.process = subprocess.Popen(args, env={**self.env, **extra}, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True)
        return self.process

    def calls(self):
        return self.log.read_text().splitlines()

    def index(self, prefix):
        """First logged call that starts with `prefix` (the timer's own command line merely contains it)."""
        return next(i for i, line in enumerate(self.calls()) if line.startswith(prefix))

    def window_records(self):
        (window_dir,) = (self.state / "runs").iterdir()
        return (json.loads((window_dir / "window-summary.json").read_text()),
                json.loads((window_dir / "C0" / "window.json").read_text()))

    def assert_production_restored(self, summary):
        self.assertEqual(summary["production_health"], "ok")
        self.assertEqual(summary["restore_timer"], "cancelled")
        timer = self.index("systemd-run --user --quiet --collect --unit=li26-restore-")
        self.assertIn("--on-active=10800s", self.calls()[timer])
        self.assertIn("systemctl --user stop li26-c0-", self.calls()[timer])
        stop = self.calls().index("systemctl --user stop nativestack-generation.service")
        start = self.calls().index("systemctl --user start nativestack-generation.service")
        self.assertLess(timer, stop)  # the independent restore timer is armed before production stops
        self.assertLess(stop, start)
        self.assertLess(start, self.index("systemctl --user stop li26-restore-"))
        self.assertFalse(any("native-stack-embeddings" in line for line in self.calls()))

    def test_hung_memory_query_stops_the_arm_and_restores_production(self):
        # Calls 1-3: preflight, after the production stop, admission; call 4 is the guard's first query.
        started = time.monotonic()
        process = self.start(LI26_FAKE_HANG_AT="4")
        stdout, stderr = process.communicate(timeout=120)
        elapsed = time.monotonic() - started
        self.assertEqual(process.returncode, 0, stderr)
        self.assertLess(elapsed, 60)
        summary, arm = self.window_records()
        self.assertIn("memory-monitor-failed", arm["guard_events"])
        self.assertIn(arm["status"], ("server-exited", "eval-stopped"))
        self.assertTrue(arm["memory_max_verified"])
        self.assertEqual(summary["exit_code"], 0)
        self.assert_production_restored(summary)
        self.assertTrue(any("kill --signal=SIGTERM li26-c0-" in line for line in self.calls()))

    def test_sigterm_during_an_arm_records_interrupted_and_restores_production(self):
        process = self.start(LI26_FAKE_RUN="sleep")
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not any(line.startswith("eval run") for line in self.calls()):
            time.sleep(0.1)
        self.assertTrue(any(line.startswith("eval run") for line in self.calls()), self.calls())
        signalled = time.monotonic()
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=120)
        self.assertLess(time.monotonic() - signalled, 60)
        self.assertEqual(process.returncode, 143, stderr)
        summary, arm = self.window_records()
        self.assertEqual((arm["status"], summary["exit_code"]), ("interrupted", 143))
        self.assertIn("interrupted", arm["guard_events"])
        self.assertTrue((self.root / "server.stopped").exists())
        self.assert_production_restored(summary)

    def test_admission_refusal_launches_nothing_and_restores_production(self):
        process = self.start(LI26_FAKE_FREE="1000")
        stdout, stderr = process.communicate(timeout=120)
        self.assertEqual(process.returncode, 0, stderr)
        summary, arm = self.window_records()
        self.assertEqual((arm["status"], arm["free_mib_at_admission"], arm["admission_required_mib"]),
                         ("admission-refused", 1000, 16384))
        self.assertEqual((arm["segment"], arm["previous_window"], arm["guard_events"]), (1, None, []))
        self.assertFalse(any(line.startswith("systemd-run") and "--scope" in line for line in self.calls()))
        self.assert_production_restored(summary)

    def test_refusals_before_any_stop(self):
        for extra, message in [({"LI26_FAKE_PREDICT": "short"}, "predicted free device memory"),
                               ({"LI26_FAKE_NEXT": "refuse"}, "cannot run in this window")]:
            with self.subTest(extra=extra):
                self.log.write_text("")
                process = self.start(**extra)
                stdout, stderr = process.communicate(timeout=60)
                self.assertEqual(process.returncode, 2, stderr)
                self.assertIn(message, stderr)
                self.assertFalse(any(line.startswith("systemd-run") or "stop nativestack" in line
                                     for line in self.calls()), self.calls())
                self.assertEqual(list((self.state / "runs").iterdir()), [])


class SubmissionToInput(unittest.TestCase):
    def test_header_is_stripped_and_only_the_primary_document_remains(self):
        source = ACQUIRE.model_input(SUBMISSION, "8-K")
        text = source["text"]
        self.assertIn("Item 2.02 Results of Operations", text)
        self.assertIn("Item 9.01 Financial Statements and Exhibits.", text)
        self.assertIn("Revenue $1", text)
        for leaked in ("ITEM INFORMATION", "ACCEPTANCE", "Financial Condition", "SEC-HEADER", "Press release",
                       "Header title leak", "hidden dei facts", "var hidden", "​", "\xa0", "  "):
            self.assertNotIn(leaked, text)
        self.assertEqual((source["primary_filename"], source["primary_sequence"], source["truncated"]),
                         ("form8k.htm", "1", False))
        header, documents = ACQUIRE.split_submission(SUBMISSION)
        self.assertEqual(ACQUIRE.submission_identity(header), ("0000000001-20-000001", "8-K"))
        self.assertEqual([document["type"] for document in documents], ["8-K", "EX-99.1"])

    def test_amendment_plain_text_and_missing_or_empty_documents(self):
        amended = SUBMISSION.replace("<TYPE>8-K\n", "<TYPE>8-K/A\n")
        self.assertIn("Item 2.02", ACQUIRE.model_input(amended, "8-K/A")["text"])
        with self.assertRaises(ACQUIRE.EmptyPrimary):
            ACQUIRE.model_input(amended, "8-K")
        blank = SUBMISSION.replace(SUBMISSION[SUBMISSION.index("<html><head>"):SUBMISSION.index("</TEXT>")],
                                   "<html><body> \n&#160;</body></html>\n")
        with self.assertRaises(ACQUIRE.EmptyPrimary):
            ACQUIRE.model_input(blank, "8-K")
        plain = SUBMISSION.replace(SUBMISSION[SUBMISSION.index("<html><head>"):SUBMISSION.index("</TEXT>")],
                                   "ITEM 8.01   OTHER EVENTS\n<PAGE>\n\n  Plain body.\n")
        self.assertEqual(ACQUIRE.model_input(plain, "8-K")["text"], "ITEM 8.01 OTHER EVENTS\nPlain body.")
        with self.assertRaises(ValueError):
            ACQUIRE.split_submission("<DOCUMENT><TYPE>8-K\n<TEXT>no header</TEXT></DOCUMENT>")

    def test_cap_keeps_head_and_tail_with_a_marker(self):
        short = "a" * 16000
        self.assertEqual(ACQUIRE.cap_text(short), (short, False))
        long = "".join(chr(65 + index % 26) for index in range(20000))
        capped, truncated = ACQUIRE.cap_text(long)
        self.assertTrue(truncated)
        self.assertEqual(capped, long[:12000] + "\n[...]\n" + long[-4000:])

    def test_declared_items_are_validated(self):
        self.assertEqual(ACQUIRE.item_codes("9.01, 2.02"), ["2.02", "9.01"])
        self.assertEqual(ACQUIRE.item_codes(None), [])
        self.assertEqual(ACQUIRE.item_codes(["8.01"]), ["8.01"])
        for bad in ("2.02,2.02", "Item 2.02", "2.2", "10.01"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ACQUIRE.item_codes(bad)

    def test_cofiled_header_keeps_items_before_the_filer_blocks(self):
        for filers in (1, 2, 3):
            with self.subTest(filers=filers):
                text = cofiled_header(filers)
                top = ACQUIRE.header_before_entities(text)
                self.assertNotIn("<FILER>", top)
                self.assertIn("<ITEMS>2.02\n<ITEMS>9.01\n", top)
                self.assertEqual(text.count("<FILER>"), filers)
                member = {"cik": 1, "accession": "0000000001-20-000002", "form": "8-K", "filed_date": "2020-03-02"}
                self.assertEqual(ACQUIRE.catalyst.parse_header(text.encode(), member, "2026-09-26T00:00:00Z")["status"],
                                 "qualified")
        self.assertEqual(ACQUIRE.header_before_entities("<SEC-HEADER>x\n<ITEMS>8.01\n"), "<SEC-HEADER>x\n<ITEMS>8.01\n")

    def test_exclusions_apply_in_the_predeclared_order(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            (run / "headers").mkdir()
            (run / "filings").mkdir()
            exhibit_only = SUBMISSION.replace("<TYPE>8-K\n<SEQUENCE>1", "<TYPE>EX-10.1\n<SEQUENCE>1")
            cases = [
                ("0000000001-20-000001", "<ITEMS>2.02\n<ITEMS>9.01\n", SUBMISSION, "fetched", None),
                ("0000000001-20-000002", "<ITEMS>8.01\n", SUBMISSION, "failed", "acquisition_failure"),
                ("0000000001-20-000003", "<ITEMS>8.01\n", exhibit_only, "fetched", "empty_primary_document"),
                ("0000000001-20-000004", "", SUBMISSION, "fetched", "zero_declared_items"),
                ("0000000001-20-000005", "", exhibit_only, "fetched", "empty_primary_document"),
                ("0000000001-20-000006", "<ITEMS>8.01\n", SUBMISSION, "fetched", "acquisition_failure"),
            ]
            entries = []
            for accession, items, submission, status, _ in cases:
                if accession != "0000000001-20-000006":
                    submission = submission.replace("0000000001-20-000001", accession)
                (run / "headers" / f"{accession}.hdr.sgml").write_text(HEADER.format(accession=accession, items=items))
                (run / "filings" / f"{accession}.txt").write_text(submission)
                entries.append({"accession": accession, "form": "8-K", "ciks": [1], "status": status,
                                "member": {"cik": 1, "accession": accession, "form": "8-K", "filed_date": "2020-03-02"},
                                "header": {"path": f"headers/{accession}.hdr.sgml",
                                           "first_observed_at": "2026-09-26T00:00:00Z"},
                                "submission": {"path": f"filings/{accession}.txt"}, "error": None})
            rows, exclusions, agreement = ACQUIRE.build_inputs(run, entries, header_labels, lambda text: "form8k.htm")
        self.assertEqual([row["accession"] for row in rows], ["0000000001-20-000001"])
        self.assertEqual(rows[0]["labels"], ["2.02", "9.01"])
        self.assertEqual(dict(exclusions), {"acquisition_failure": 2, "empty_primary_document": 2,
                                            "zero_declared_items": 1})
        self.assertEqual([entry["exclusion"] for entry in entries], [case[4] for case in cases])
        self.assertEqual(entries[-1]["error"], "submission_identity_mismatch")
        self.assertEqual(dict(agreement), {"agree": 1})
        self.assertEqual(ACQUIRE.inputs_bytes(rows), ACQUIRE.inputs_bytes(copy.deepcopy(rows)))

    def test_pacer_starts_at_most_five_requests_per_second(self):
        now = [100.0]
        pacer = ACQUIRE.Pacer(5, clock=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0] + seconds))
        starts = []
        for _ in range(11):
            pacer.wait()
            starts.append(now[0])
        self.assertAlmostEqual(starts[-1] - starts[0], 2.0)
        self.assertTrue(all(b - a >= 0.2 - 1e-9 for a, b in zip(starts, starts[1:])))


SDK_PYTHON = Path(os.environ.get("CATALYST_SDK_PY") or
                  Path.home() / ".local/share/codex-ecosystem/catalyst-provenance/sdk/bin/python")


@unittest.skipUnless(SDK_PYTHON.is_file() and os.access(SDK_PYTHON, os.X_OK),
                     "catalyst-provenance SDK Python (EdgarTools) is not installed")
class NativeLabels(unittest.TestCase):
    """The real EdgarTools label path on co-filed headers; offline, parse only."""

    def test_cofiled_headers_parse_with_the_native_reader(self):
        script = textwrap.dedent("""\
            import importlib.metadata, importlib.util, json, sys
            spec = importlib.util.spec_from_file_location("li26_acquire_sdk", sys.argv[1])
            acquire = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(acquire)
            results = []
            for path in sys.argv[2:]:
                try:
                    results.append(acquire.native_labels(open(path, "rb").read()))
                except ValueError as error:
                    results.append(str(error))
            print(json.dumps({"edgartools": importlib.metadata.version("edgartools"), "results": results}))
            """)
        cases = [(cofiled_header(1), ["2.02", "9.01"]), (cofiled_header(2), ["2.02", "9.01"]),
                 (cofiled_header(3), ["2.02", "9.01"]), (cofiled_header(2, items=""), []),
                 (cofiled_header(2, items="<ITEMS>2.02\n") + "<ITEMS>5.02\n", "native_items_disagree")]
        with tempfile.TemporaryDirectory() as temp:
            paths = []
            for index, (text, _) in enumerate(cases):
                path = Path(temp) / f"h{index}.hdr.sgml"
                path.write_text(text)
                paths.append(str(path))
            (Path(temp) / "script.py").write_text(script)
            result = subprocess.run([str(SDK_PYTHON), str(Path(temp) / "script.py"), str(HERE / "acquire.py"), *paths],
                                    capture_output=True, text=True, timeout=300,
                                    env={"PATH": "/usr/bin:/bin", "HOME": temp,
                                         "EDGAR_LOCAL_DATA_DIR": str(Path(temp) / "edgar")})
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        output = json.loads(result.stdout.strip().splitlines()[-1])
        if output["edgartools"] != ACQUIRE.EDGAR_VERSION:
            self.skipTest(f"EdgarTools {output['edgartools']} is not the pinned {ACQUIRE.EDGAR_VERSION}")
        self.assertEqual(output["results"], [expected for _, expected in cases])


INDEX = """Description:           Master Index of EDGAR Dissemination Feed
Last Data Received:    March 2, 2020

CIK|Company Name|Form Type|Date Filed|File Name
--------------------------------------------------------------------------------
1|Alpha Corp|8-K|20200302|edgar/data/1/0000000001-20-000001.txt
2|Beta Corp|8-K|20200302|edgar/data/2/0000000001-20-000001.txt
3|Gamma Corp|8-K/A|20200302|edgar/data/3/0000000003-20-000003.txt
4|Delta Corp|10-K|20200302|edgar/data/4/0000000004-20-000004.txt
""".encode()


class FakeHttp:
    """Stand-in for EdgarTools get_with_retry: the synthetic index, one filing, one 404 or 403."""

    def __init__(self, missing_status=404, first_header_status=200):
        self.urls = []
        self.missing_status, self.first_header_status = missing_status, first_header_status
        base = "https://www.sec.gov/Archives/edgar/data/"
        self.bodies = {
            ACQUIRE.INDEX_URL: INDEX,
            f"{base}1/000000000120000001/0000000001-20-000001.hdr.sgml":
                HEADER.format(accession="0000000001-20-000001", items="<ITEMS>2.02\n<ITEMS>9.01\n").encode(),
            f"{base}1/000000000120000001/0000000001-20-000001.txt": SUBMISSION.encode(),
        }

    def __call__(self, url):
        self.urls.append(url)
        status = 200 if url in self.bodies else self.missing_status
        if url.endswith("0000000001-20-000001.hdr.sgml"):
            status = self.first_header_status
        body = self.bodies.get(url, b"") if status == 200 else b""
        return type("Response", (), {"status_code": status, "url": url, "content": body,
                                     "headers": {"content-length": str(len(body))}})()


class Acquisition(unittest.TestCase):
    CONTACT = "Example Research research@example.com"

    def run_acquire(self, temp, http):
        anchors = {"INDEX_SHA256": hashlib.sha256(INDEX).hexdigest(), "INDEX_BYTES": len(INDEX),
                   "EXPECTED_COHORT": {"rows": 3, "accessions": 2, "8-K": 2, "8-K/A": 1}}
        pacer = ACQUIRE.Pacer(5, clock=lambda: 0.0, sleep=lambda seconds: None)
        with mock.patch.multiple(ACQUIRE, **anchors), mock.patch.dict(os.environ, {}, clear=False):
            summary = ACQUIRE.acquire(Path(temp) / "state", "acq-test", self.CONTACT, get=http, pacer=pacer,
                                      parse_labels=header_labels, native_primary=lambda text: None)
            self.assertEqual(os.environ["EDGAR_IDENTITY"], self.CONTACT)
        return summary, Path(temp) / "state" / "sec" / "acq-test"

    def test_offline_acquisition_retains_private_bytes_and_a_public_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            http = FakeHttp()
            summary, run = self.run_acquire(temp, http)
            manifest = json.loads((run / "manifest.json").read_text())
            rows = [json.loads(line) for line in (run / "inputs.jsonl").read_text().splitlines()]
            for path in run.rglob("*"):
                if path.is_file():
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600, path.name)
                    self.assertNotIn(self.CONTACT.encode(), path.read_bytes(), path.name)
                elif path.is_dir():
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700, path.name)
        self.assertEqual(http.urls[0], ACQUIRE.INDEX_URL)
        self.assertEqual(len(http.urls), 1 + 2 + 1)  # index, one filing's two files, one 404 header
        self.assertEqual((summary["status"], summary["eligible"], summary["request_count"]), ("complete", 1, 4))
        self.assertEqual(summary["exclusions"], {"acquisition_failure": 1, "empty_primary_document": 0,
                                                 "zero_declared_items": 0})
        self.assertEqual(summary["label_counts"], {"2.02": 1, "9.01": 1})
        self.assertEqual(summary["inputs_sha256"], manifest["inputs"]["sha256"])
        self.assertEqual(summary["input_chars_total"], len(rows[0]["input"]))
        self.assertEqual([row["ciks"] for row in rows], [[1, 2]])
        public = json.dumps(summary)
        self.assertNotIn("Item 2.02", public)
        self.assertNotIn(self.CONTACT, public)
        self.assertEqual([entry["error"] for entry in manifest["filings"]], [None, "http_404"])

    def test_refusal_stops_every_later_request(self):
        with tempfile.TemporaryDirectory() as temp:
            http = FakeHttp(first_header_status=403)
            summary, run = self.run_acquire(temp, http)
            manifest = json.loads((run / "manifest.json").read_text())
        self.assertEqual(len(http.urls), 2)
        self.assertEqual((summary["status"], summary["stopped"], summary["eligible"]), ("incomplete", "http_403", 0))
        self.assertEqual([entry["status"] for entry in manifest["filings"]], ["failed", "not_attempted"])

    def test_changed_index_fails_closed_before_any_filing_request(self):
        with tempfile.TemporaryDirectory() as temp:
            http = FakeHttp()
            pacer = ACQUIRE.Pacer(5, clock=lambda: 0.0, sleep=lambda seconds: None)
            with mock.patch.dict(os.environ, {}, clear=False):
                summary = ACQUIRE.acquire(Path(temp) / "state", "acq-test", self.CONTACT, get=http, pacer=pacer,
                                          parse_labels=header_labels, native_primary=lambda text: None)
        self.assertEqual((summary["status"], summary["error"], len(http.urls)), ("failed", "frozen_index_changed", 1))


class ContactFile(unittest.TestCase):
    CONTACT = "Example Research research@example.com"

    def write(self, directory, text, mode=0o600):
        path = Path(directory) / "sec-contact.env"
        path.write_text(text)
        path.chmod(mode)
        return path

    def test_contact_is_read_from_an_owner_only_file_and_never_echoed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.write(temp, f'# private\nexport SEC_USER_AGENT="{self.CONTACT}"\n')
            self.assertEqual(ACQUIRE.load_contact(path), self.CONTACT)
            path.chmod(0o644)
            with self.assertRaises(ValueError) as caught:
                ACQUIRE.load_contact(path)
            self.assertNotIn(self.CONTACT, str(caught.exception))
            link = Path(temp) / "link.env"
            path.chmod(0o600)
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                ACQUIRE.load_contact(link)
            preferred = self.write(temp, f"export SEC_USER_AGENT='{self.CONTACT}'\nEDGAR_IDENTITY=Other Name other@example.com\n")
            self.assertEqual(ACQUIRE.load_contact(preferred), "Other Name other@example.com")
            for text in ("export SEC_USER_AGENT=\n", "export SEC_USER_AGENT=\"no contact here\"\n", "OTHER=x\n"):
                with self.subTest(text=text), self.assertRaises(ValueError) as caught:
                    ACQUIRE.load_contact(self.write(temp, text))
                self.assertNotIn("contact here", str(caught.exception))


class ReplyParsing(unittest.TestCase):
    def test_strict_fenced_and_malformed_replies(self):
        cases = [
            ('{"items": ["9.01", "2.02"]}', (["2.02", "9.01"], "valid")),
            ('  {"items": []}\n', ([], "valid")),
            ('```json\n{"items": ["8.01"]}\n```', (["8.01"], "fenced_valid")),
            ('```\n{"items": ["8.01"]}\n```', (["8.01"], "fenced_valid")),
            ('Here it is: {"items": ["8.01"]}', (None, "invalid")),
            ('{"items": ["8.01"]} Done.', (None, "invalid")),
            ('{"items": ["8.01", "8.01"]}', (None, "invalid")),
            ('{"items": ["Item 8.01"]}', (None, "invalid")),
            ('{"items": ["8.1"]}', (None, "invalid")),
            ('{"items": [801]}', (None, "invalid")),
            ('{"items": "8.01"}', (None, "invalid")),
            ('{"items": ["8.01"], "note": "x"}', (None, "invalid")),
            ('{"item": ["8.01"]}', (None, "invalid")),
            ('{"items": ["8.01"], "items": ["9.01"]}', (None, "invalid")),
            ('{"items": ["8.01"', (None, "invalid")),
            ('["8.01"]', (None, "invalid")),
            ("<think>\n</think>", (None, "invalid")),
            ("", (None, "invalid")),
            (None, (None, "invalid")),
        ]
        for content, expected in cases:
            with self.subTest(content=content):
                self.assertEqual(EVAL.parse_items(content), expected)


class Scoring(unittest.TestCase):
    def test_per_filing_micro_and_macro_scores(self):
        partial = ANALYZE.filing_scores(["2.02", "9.01"], ["2.02"])
        self.assertEqual((partial["precision"], partial["recall"], partial["exact"]), (1.0, 0.5, False))
        self.assertAlmostEqual(partial["f1"], 2 / 3)
        nothing = ANALYZE.filing_scores(["8.01"], None)
        self.assertEqual((nothing["precision"], nothing["recall"], nothing["f1"], nothing["exact"]), (0.0, 0.0, 0.0, False))
        extra = ANALYZE.filing_scores(["8.01"], ["8.01", "9.01"])
        self.assertEqual((extra["precision"], extra["recall"], extra["exact"]), (0.5, 1.0, False))
        self.assertTrue(ANALYZE.filing_scores(["8.01", "9.01"], ["9.01", "8.01"])["exact"])
        self.assertAlmostEqual(ANALYZE.micro_f1([(1, 0, 1), (0, 1, 1)]), 0.4)
        golds = [["9.01"]] * 5 + [["2.02"]] * 4
        predictions = [["9.01"]] * 4 + [[]] + [["2.02"]] * 4
        macro, per_code = ANALYZE.macro_f1(golds, predictions)
        self.assertEqual(list(per_code), ["9.01"])  # 2.02 has only four filings
        self.assertAlmostEqual(macro, 8 / 9)

    def test_paired_bootstrap_is_deterministic_for_its_seed(self):
        # Varied per-filing counts, so the percentile does not sit on a discrete atom for every seed.
        control = [(i % 3 + 1, (i * 7) % 3, (i * 5) % 4) for i in range(60)]
        arm = [(i % 4 + 1, (i * 11) % 2, (i * 3) % 3) for i in range(60)]
        first = ANALYZE.paired_bootstrap(control, arm)
        self.assertEqual(first, ANALYZE.paired_bootstrap(control, arm))
        self.assertEqual((first["resamples"], first["seed"]), (10000, 20260926))
        self.assertLessEqual(first["lower"], first["point"])
        self.assertLessEqual(first["point"], first["upper"])
        self.assertNotEqual(first["lower"], ANALYZE.paired_bootstrap(control, arm, seed=7)["lower"])
        same = ANALYZE.paired_bootstrap(control, control, resamples=500)
        self.assertEqual((same["lower"], same["point"], same["upper"]), (0.0, 0.0, 0.0))
        better = ANALYZE.paired_bootstrap([(0, 0, 1)] * 30, [(1, 0, 0)] * 30, resamples=500)
        self.assertEqual(better["lower"], 1.0)
        self.assertEqual(ANALYZE.nearest_rank(list(range(10000)), 0.025), 249)

    def test_decision_rule_truth_table(self):
        rule = PLAN["decision_rule"]
        control = {"median_decode_tokens_per_second": 5.0}
        for quality, faster, valid, clean in itertools.product([True, False], repeat=4):
            bootstrap = {"lower": -0.02 if quality else -0.0201}
            arm = {"median_decode_tokens_per_second": 5.01 if faster else 5.0,
                   "json_valid_rate": 0.98 if valid else 0.9799, "failure_free": clean}
            passed = ANALYZE.criteria(bootstrap, arm, control, rule)
            self.assertEqual(list(passed.values()), [quality, faster, valid, clean])
            with self.subTest(quality=quality, faster=faster, valid=valid, clean=clean):
                expected_all = quality and faster and valid and clean
                self.assertEqual(ANALYZE.outcome("model_candidate", passed),
                                 "replace_model" if expected_all else "retain_control")
                self.assertEqual(ANALYZE.outcome("serving_profile_candidate", passed),
                                 "change_serving_profile" if expected_all else "retain_control")
        missing = ANALYZE.criteria({"lower": 0.1}, {"median_decode_tokens_per_second": None, "json_valid_rate": 1.0,
                                                    "failure_free": True}, control, rule)
        self.assertFalse(missing["faster_median_decode"])


class Prediction(unittest.TestCase):
    def test_admission_is_predicted_before_production_stops(self):
        short = EVAL.predict_admission(PLAN, ["C0", "M"], 4969, True)
        self.assertEqual((short["predicted_free_mib"], short["required_mib"], short["shortfall_mib"]),
                         (4969 + 9478, 16384, 16384 - 4969 - 9478))
        enough = EVAL.predict_admission(PLAN, ["C2"], 8100, True)
        self.assertEqual((enough["required_mib"], enough["shortfall_mib"]), (17535, 0))
        stopped = EVAL.predict_admission(PLAN, ["C1"], 17000, False)
        self.assertEqual((stopped["predicted_free_mib"], stopped["shortfall_mib"]), (17000, 151))
        with self.assertRaises(ValueError):
            EVAL.predict_admission(PLAN, ["B"], 24000, False)


def filing_rows(gold, predicted, speed, segment=1, statuses=None, count=None):
    """Public per-filing records; filings from index `count` on are left not attempted."""
    rows = []
    for index, (labels, items) in enumerate(zip(gold, predicted)):
        attempted = count is None or index < count
        rows.append({"accession": f"0000000001-20-{index:06d}", "gold": labels,
                     "predicted": items if attempted else None,
                     "parse_status": (statuses or ["valid"] * len(gold))[index] if attempted else "invalid",
                     "http_status": 200 if attempted else None, "error": None if attempted else "not_attempted",
                     "predicted_n": 12 if attempted else None, "predicted_per_second": speed if attempted else None,
                     "prompt_ms": 900.0 if attempted else None, "segment": segment if attempted else None})
    return rows


class StateDir:
    """A synthetic window.sh state directory: runs/<window>/<arm>/{window.json, memory.csv, eval/metrics.json}."""

    STATUS = {"completed": "completed", "segment-boundary": "segment_boundary"}

    def __init__(self, root):
        self.root, self.count = Path(root), 0

    def add(self, arm, filings, status="completed", segment=1, previous=None, events=(), guard_events=(),
            memory="default", verified=True):
        self.count += 1
        window = f"w-20260927T{self.count:06d}Z"
        directory = self.root / "runs" / window / arm
        (directory / "eval").mkdir(parents=True)
        started = 1_000_000 + self.count * 100_000
        record = {"arm": arm, "segment": segment, "status": status, "memory_max_verified": verified,
                  "guard_events": list(guard_events), "cold_load_ms": 4200, "server_started_ms": started,
                  "monitor_stopped_ms": started + 10_000}
        (directory / "window.json").write_text(json.dumps(record))
        if memory == "default":
            memory = "".join(f"{started + i * 1000},9000,15000\n" for i in range(11))
        elif callable(memory):
            memory = memory(started)
        if memory is not None:
            (directory / "memory.csv").write_text(memory)
        if filings is None:
            return window, None
        metrics = {"arm": arm, "segment": segment, "previous_metrics_sha256": previous, "plan_sha256": PLAN_SHA,
                   "prompt_sha256": PLAN["prompt_sha256"], "inputs_sha256": "a" * 64,
                   "status": self.STATUS.get(status, "stopped"), "events": list(events), "filings": filings}
        raw = json.dumps(metrics).encode()
        (directory / "eval" / "metrics.json").write_bytes(raw)
        return window, hashlib.sha256(raw).hexdigest()


GOLD = [["2.02", "9.01"], ["8.01"], ["5.02", "9.01"], ["7.01"]] * 10


class Segments(unittest.TestCase):
    def test_next_segment_follows_the_chain(self):
        with tempfile.TemporaryDirectory() as temp:
            state = StateDir(temp)
            self.assertEqual(EVAL.next_segment(PLAN, temp, "C0"), (1, None))
            state.add("C0", None, status="admission-refused", memory=None)
            self.assertEqual(EVAL.next_segment(PLAN, temp, "C0"), (1, None))
            window, sha = state.add("C0", filing_rows(GOLD, GOLD, 5.0, count=10), status="segment-boundary")
            self.assertEqual(EVAL.next_segment(PLAN, temp, "C0"), (2, window))
            state.add("C0", filing_rows(GOLD, GOLD, 5.0, count=20), status="segment-boundary", segment=2, previous=sha)
            self.assertEqual(EVAL.next_segment(PLAN, temp, "C0")[0], 3)
            with self.assertRaises(ValueError):
                EVAL.next_segment(PLAN, temp, "B")

    def test_completed_failed_exhausted_and_broken_chains_refuse(self):
        cases = {
            "complete": [("completed", None)],
            "ended as eval-stopped": [("eval-stopped", None)],
            "ended as unrecorded": [(None, None)],
            "used all 4 segments": [("segment-boundary", None)] * 4,
            "inconsistent record": [("segment-boundary", None), ("segment-boundary", "0" * 64)],
        }
        for message, attempts in cases.items():
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temp:
                state, previous = StateDir(temp), None
                for position, (status, forced) in enumerate(attempts, 1):
                    window, previous = state.add("C0", filing_rows(GOLD, GOLD, 5.0, count=position * 5),
                                                 status=status or "completed", segment=position,
                                                 previous=forced or previous)
                    if status is None:
                        (Path(temp) / "runs" / window / "C0" / "window.json").unlink()
                with self.assertRaises(ValueError) as caught:
                    EVAL.next_segment(PLAN, temp, "C0")
                self.assertIn(message, str(caught.exception))


class EndToEndAnalysis(unittest.TestCase):
    def two_segment_control(self, state, speed=5.0):
        _, first = state.add("C0", filing_rows(GOLD, GOLD, speed, count=20), status="segment-boundary")
        second_rows = filing_rows(GOLD, GOLD, speed, segment=2)
        second_rows[:20] = filing_rows(GOLD, GOLD, speed, count=20)[:20]
        state.add("C0", second_rows, status="completed", segment=2, previous=first)

    def test_faster_noninferior_arm_replaces_across_segments(self):
        with tempfile.TemporaryDirectory() as temp:
            state = StateDir(temp)
            self.two_segment_control(state)
            state.add("M", filing_rows(GOLD, GOLD, 40.0))
            state.add("C1", filing_rows(GOLD, [["2.02"]] * 40, 30.0))
            state.add("C2", None, status="admission-refused", memory=None)
            decision = ANALYZE.analyze(PLAN, PLAN_SHA, temp)
        self.assertEqual(decision["selected"], {"arm": "M", "outcome": "replace_model"})
        self.assertTrue(decision["final"])
        self.assertEqual(decision["control"]["summary"]["segments"], 2)
        self.assertTrue(decision["control"]["summary"]["failure_free"])
        by_arm = {result["arm"]: result for result in decision["arms"]}
        self.assertFalse(by_arm["C1"]["criteria"]["noninferior_micro_f1"])
        self.assertEqual(by_arm["M"]["summary"]["peak_device_used_mib"], 9000)
        self.assertEqual(by_arm["M"]["summary"]["cold_load_seconds"], 4.2)
        self.assertEqual([entry["arm"] for entry in decision["arms_not_run"]], ["C2", "B", "X"])
        self.assertEqual(decision["arms_not_run"][0]["not_started"][0]["status"], "admission-refused")
        self.assertNotIn('"input"', json.dumps(decision))

    def test_missing_or_contradictory_memory_evidence_blocks_a_winning_arm(self):
        variants = {
            "memory-samples-missing": {"memory": None},
            "memory-samples-malformed": {"memory": lambda t: f"{t},9000,15000\nnot,a,sample\n"},
            "device-memory-reserve-breached-in-samples": {
                "memory": lambda t: "".join(f"{t + i * 5000},21000,2000\n" for i in range(3))},
            "memory-monitor-gap": {"memory": lambda t: f"{t},9000,15000\n{t + 40_000},9000,15000\n"},
            "memory-monitor-coverage": {"memory": lambda t: f"{t + 40_000},9000,15000\n"},
            "memory-limit-unverified": {"verified": False},
        }
        for failure, options in variants.items():
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                state = StateDir(temp)
                state.add("C0", filing_rows(GOLD, GOLD, 5.0))
                state.add("M", filing_rows(GOLD, GOLD, 40.0), **options)
                decision = ANALYZE.analyze(PLAN, PLAN_SHA, temp)
                (result,) = decision["arms"]
                self.assertIn(failure, result["summary"]["failures"])
                self.assertTrue(result["criteria"]["noninferior_micro_f1"])
                self.assertTrue(result["criteria"]["faster_median_decode"])
                self.assertFalse(result["criteria"]["no_memory_or_deadline_failure"])
                self.assertEqual((result["outcome"], decision["selected"]["outcome"]),
                                 ("retain_control", "retain_control"))

    def test_a_recoverable_server_error_cannot_win(self):
        # 200 filings: one HTTP 500 leaves JSON validity at 0.995 and quality non-inferior; only (4) fails.
        gold = GOLD * 5
        for window_status in ("eval-stopped", "completed"):
            with self.subTest(window_status=window_status), tempfile.TemporaryDirectory() as temp:
                state = StateDir(temp)
                state.add("C0", filing_rows(gold, gold, 5.0))
                rows = filing_rows(gold, gold, 40.0)
                rows[3].update(predicted=None, parse_status="invalid", http_status=500, error="http_500")
                state.add("M", rows, status=window_status, events=["server-error:500:0000000001-20-000003"])
                decision = ANALYZE.analyze(PLAN, PLAN_SHA, temp)
                (result,) = decision["arms"]
                self.assertTrue(result["criteria"]["noninferior_micro_f1"], result["bootstrap"])
                self.assertTrue(result["criteria"]["faster_median_decode"])
                self.assertTrue(result["criteria"]["json_valid_rate"])
                self.assertFalse(result["criteria"]["no_memory_or_deadline_failure"])
                self.assertIn("server-error:500:0000000001-20-000003", result["summary"]["failures"])
                self.assertEqual(decision["selected"], {"arm": None, "outcome": "retain_control"})

    def test_control_problems_make_the_result_inconclusive(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(ANALYZE.analyze(PLAN, PLAN_SHA, temp)["selected"]["outcome"],
                             "inconclusive_control_not_evaluated")
        with tempfile.TemporaryDirectory() as temp:
            state = StateDir(temp)
            state.add("C0", filing_rows(GOLD, GOLD, 5.0, count=20), status="segment-boundary")
            state.add("M", filing_rows(GOLD, GOLD, 40.0))
            decision = ANALYZE.analyze(PLAN, PLAN_SHA, temp)
            self.assertEqual((decision["selected"]["outcome"], decision["final"]),
                             ("inconclusive_control_incomplete", False))
        for options in ({"events": ["request-deadline:0000000001-20-000007"]},
                        {"status": "startup-failed", "memory": None}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as temp:
                state = StateDir(temp)
                filings = None if options.get("status") == "startup-failed" else filing_rows(GOLD, GOLD, 5.0)
                state.add("C0", filings, **options)
                state.add("M", filing_rows(GOLD, GOLD, 40.0))
                self.assertEqual(ANALYZE.analyze(PLAN, PLAN_SHA, temp)["selected"]["outcome"],
                                 "inconclusive_control_invalid")

    def test_reruns_and_tampered_chains_fail_the_arm(self):
        with tempfile.TemporaryDirectory() as temp:
            state = StateDir(temp)
            state.add("C0", filing_rows(GOLD, GOLD, 5.0))
            state.add("C0", filing_rows(GOLD, GOLD, 5.0))
            decision = ANALYZE.analyze(PLAN, PLAN_SHA, temp)
            self.assertEqual(decision["selected"]["outcome"], "inconclusive_control_invalid")
            self.assertTrue(any(f.startswith("rerun-after-terminal-attempt")
                                for f in decision["control"]["summary"]["failures"]))
        with tempfile.TemporaryDirectory() as temp:
            state = StateDir(temp)
            _, first = state.add("C0", filing_rows(GOLD, GOLD, 5.0, count=20), status="segment-boundary")
            tampered = filing_rows(GOLD, GOLD, 5.0, segment=2)
            tampered[:20] = filing_rows(GOLD, GOLD, 5.0, count=20)[:20]
            tampered[0]["predicted"] = ["9.01"]
            state.add("C0", tampered, status="completed", segment=2, previous=first)
            failures = ANALYZE.analyze(PLAN, PLAN_SHA, temp)["control"]["summary"]["failures"]
            self.assertTrue(any(f.startswith("segment-carry-mismatch") for f in failures), failures)

    def test_unpaired_or_foreign_plan_metrics_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            state = StateDir(temp)
            state.add("C0", filing_rows(GOLD, GOLD, 5.0))
            state.add("M", filing_rows(GOLD[:-1], GOLD[:-1], 40.0))
            with self.assertRaises(ValueError):
                ANALYZE.analyze(PLAN, PLAN_SHA, temp)
        with tempfile.TemporaryDirectory() as temp:
            StateDir(temp).add("C0", filing_rows(GOLD, GOLD, 5.0))
            with self.assertRaises(ValueError):
                ANALYZE.analyze(PLAN, "0" * 64, temp)


class FakeResponse(io.BytesIO):
    def __init__(self, payload, status=200):
        super().__init__(json.dumps(payload).encode())
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def completion(content):
    return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {"prompt_tokens": 900, "completion_tokens": 12},
            "timings": {"prompt_n": 900, "prompt_ms": 850.0, "predicted_n": 12,
                        "predicted_ms": 2400.0, "predicted_per_second": 5.0}}


class FakeServer:
    """Loopback stand-in: each chat request takes the next scripted reply.

    A reply is the content string of a completion, ("http", code, body) for an
    HTTP error with a JSON body, ("payload", value) for a raw 200 body, or
    ("raise", exception).
    """

    def __init__(self, replies, alias="li26-c0"):
        self.replies, self.alias = list(replies), alias
        self.bodies = []

    def open(self, request, timeout=None):
        url = request if isinstance(request, str) else request.full_url
        if url.endswith("/v1/models"):
            return FakeResponse({"data": [{"id": self.alias}]})
        if url.endswith("/props"):
            return FakeResponse({"model_path": "/models/qwen3.8-27b-4ca7207/Qwen3.8-27B-UD-Q4_K_M.gguf",
                                 "build_info": "b11146-7fe450e19"})
        self.bodies.append(json.loads(request.data))
        reply = self.replies.pop(0)
        if isinstance(reply, str):
            return FakeResponse(completion(reply))
        if reply[0] == "http":
            raise urllib.error.HTTPError(url, reply[1], "error", {}, io.BytesIO(json.dumps(reply[2]).encode()))
        if reply[0] == "payload":
            return FakeResponse(reply[1])
        raise reply[1]


class EvaluationRun(unittest.TestCase):
    SECRET = "UNIQUE-SYNTHETIC-FILING-TEXT"

    def acquisition(self, temp, count=4):
        rows = [{"accession": f"0000000001-20-00000{index}", "labels": ["2.02", "9.01"],
                 "input": f"{self.SECRET} {index} Item 2.02", "truncated": False} for index in range(count)]
        payload = b"".join(json.dumps(row, sort_keys=True).encode() + b"\n" for row in rows)
        digest = hashlib.sha256(payload).hexdigest()
        acquisition = Path(temp) / "acq"
        acquisition.mkdir()
        (acquisition / "inputs.jsonl").write_bytes(payload)
        (acquisition / "manifest.json").write_text(json.dumps({"status": "complete", "inputs": {"sha256": digest}}))
        return acquisition, digest

    def run_segment(self, temp, replies, name="eval", clock=None, **kwargs):
        acquisition, digest = self.acquisition(temp)
        server = FakeServer(replies)
        metrics = EVAL.run(HERE / "plan.json", "C0", acquisition, digest, "http://127.0.0.1:18299", Path(temp) / name,
                           10_000.0, http=server, clock=clock or (lambda: 0.0), **kwargs)
        return metrics, server, Path(temp) / name

    def test_public_metrics_hold_codes_and_timings_but_no_document_text(self):
        overflow = {"error": {"code": 400, "message": "request (9000 tokens) exceeds the available context size",
                              "type": "exceed_context_size_error", "n_prompt_tokens": 9000, "n_ctx": 8192}}
        with tempfile.TemporaryDirectory() as temp:
            metrics, server, out = self.run_segment(temp, [
                '{"items": ["2.02", "9.01"]}', '```json\n{"items": ["2.02"]}\n```', 'The items are 2.02 and 9.01.',
                ("http", 400, overflow)])
            public = (out / "metrics.json").read_text()
            private = (out / "raw.private.jsonl").read_text()
            self.assertEqual(stat.S_IMODE(os.stat(out / "raw.private.jsonl").st_mode), 0o600)
        self.assertIn("The items are", private)
        self.assertIn("exceeds the available context size", private)
        self.assertEqual((metrics["status"], metrics["events"], metrics["segment"]), ("completed", [], 1))
        self.assertNotIn(self.SECRET, public)
        self.assertNotIn("The items are", public)
        self.assertNotIn("exceeds the available", public)
        self.assertEqual([f["parse_status"] for f in metrics["filings"]], ["valid", "fenced_valid", "invalid", "invalid"])
        self.assertEqual((metrics["filings"][3]["error"], metrics["filings"][3]["error_type"],
                          metrics["filings"][3]["n_prompt_tokens"]),
                         ("context_overflow", "exceed_context_size_error", 9000))
        self.assertEqual([f["segment"] for f in metrics["filings"]], [1, 1, 1, 1])
        self.assertEqual(metrics["server"]["build_info"], "b11146-7fe450e19")
        body = server.bodies[0]
        self.assertEqual({key: body[key] for key in ("seed", "temperature", "top_k", "top_p", "max_tokens",
                                                     "chat_template_kwargs", "cache_prompt", "stream")},
                         {"seed": 0, "temperature": 0.0, "top_k": 1, "top_p": 1.0, "max_tokens": 256,
                          "chat_template_kwargs": {"enable_thinking": False}, "cache_prompt": False, "stream": False})
        content = body["messages"][0]["content"]
        self.assertIn(f"{self.SECRET} 0 Item 2.02", content)
        self.assertNotIn(EVAL.MARKER, content)
        self.assertTrue(content.startswith("You label a U.S. SEC current report"))

    def test_server_errors_stop_the_arm(self):
        compute_error = {"error": {"code": 500, "message": "Compute error.", "type": "server_error"}}
        for reply, event in [(("http", 500, compute_error), "server-error:500:0000000001-20-000001"),
                             (("http", 400, {"error": {"type": "invalid_request_error"}}),
                              "server-error:400:0000000001-20-000001"),
                             (("payload", {"unexpected": True}), "server-error:200:0000000001-20-000001"),
                             (("raise", ConnectionRefusedError()), "server-unavailable:0000000001-20-000001")]:
            with self.subTest(event=event), tempfile.TemporaryDirectory() as temp:
                metrics, server, out = self.run_segment(temp, ['{"items": ["2.02", "9.01"]}', reply,
                                                               '{"items": ["2.02", "9.01"]}'])
                self.assertEqual((metrics["status"], metrics["events"]), ("stopped", [event]))
                self.assertEqual(EVAL.exit_code(metrics["status"]), EVAL.EXIT_STOPPED)
                self.assertEqual([f["error"] for f in metrics["filings"]][2:], ["not_attempted", "not_attempted"])
                self.assertEqual(len(server.bodies), 2)
                if reply[0] == "http":
                    self.assertIn(reply[2]["error"]["type"], (out / "raw.private.jsonl").read_text())

    def test_segment_boundary_and_continuation_carry_results_verbatim(self):
        with tempfile.TemporaryDirectory() as temp:
            times = iter([0.0, 0.0, 9_500.0])
            first, _, first_out = self.run_segment(temp, ['{"items": ["2.02", "9.01"]}', '{"items": ["2.02"]}'],
                                                   name="s1", clock=lambda: next(times))
            self.assertEqual((first["status"], first["events"]), ("segment_boundary", []))
            self.assertEqual(EVAL.exit_code(first["status"]), EVAL.EXIT_SEGMENT_BOUNDARY)
            self.assertEqual([f["segment"] for f in first["filings"]], [1, 1, None, None])
            acquisition, digest = Path(temp) / "acq", hashlib.sha256((Path(temp) / "acq/inputs.jsonl").read_bytes()).hexdigest()
            server = FakeServer(['{"items": ["9.01"]}', '{"items": ["2.02", "9.01"]}'])
            second = EVAL.run(HERE / "plan.json", "C0", acquisition, digest, "http://127.0.0.1:18299",
                              Path(temp) / "s2", 10_000.0, segment=2, previous=first_out, http=server,
                              clock=lambda: 0.0)
            self.assertEqual(second["status"], "completed")
            self.assertEqual(second["filings"][:2], first["filings"][:2])
            self.assertEqual([f["segment"] for f in second["filings"]], [1, 1, 2, 2])
            self.assertEqual(second["previous_metrics_sha256"],
                             hashlib.sha256((first_out / "metrics.json").read_bytes()).hexdigest())
            self.assertEqual(len(server.bodies), 2)
            for segment, previous in [(3, first_out), (1, first_out), (2, None)]:
                with self.subTest(segment=segment), self.assertRaises(ValueError):
                    EVAL.run(HERE / "plan.json", "C0", acquisition, digest, "http://127.0.0.1:18299",
                             Path(temp) / f"bad{segment}", 10_000.0, segment=segment, previous=previous,
                             http=FakeServer([]), clock=lambda: 0.0)
            with self.assertRaises(ValueError):  # a completed segment is never continued
                EVAL.run(HERE / "plan.json", "C0", acquisition, digest, "http://127.0.0.1:18299",
                         Path(temp) / "s3", 10_000.0, segment=3, previous=Path(temp) / "s2",
                         http=FakeServer([]), clock=lambda: 0.0)

    def test_interruption_is_recorded_and_terminal(self):
        with tempfile.TemporaryDirectory() as temp:
            metrics, _, out = self.run_segment(temp, ['{"items": ["2.02", "9.01"]}', ("raise", EVAL.Interrupted())])
            written = json.loads((out / "metrics.json").read_text())
        self.assertEqual((metrics["status"], metrics["events"]), ("interrupted", ["interrupted"]))
        self.assertEqual(written["status"], "interrupted")
        self.assertEqual(EVAL.exit_code("interrupted"), EVAL.EXIT_INTERRUPTED)
        self.assertEqual([f["segment"] for f in metrics["filings"]], [1, None, None, None])

    def test_wrong_inputs_hash_or_incomplete_acquisition_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            acquisition = Path(temp)
            (acquisition / "inputs.jsonl").write_bytes(b'{"accession": "a"}\n')
            digest = hashlib.sha256(b'{"accession": "a"}\n').hexdigest()
            (acquisition / "manifest.json").write_text(json.dumps({"status": "incomplete", "inputs": {"sha256": digest}}))
            with self.assertRaises(ValueError):
                EVAL.load_inputs(acquisition, digest)
            with self.assertRaises(ValueError):
                EVAL.load_inputs(acquisition, "0" * 64)


if __name__ == "__main__":
    unittest.main()
