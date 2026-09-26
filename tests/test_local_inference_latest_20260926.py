"""Offline checks for the local-inference-latest-20260926 preregistration.

Synthetic fixtures only: no model, server, GPU, SEC request or private file.
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
import stat
import subprocess
import tempfile
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


def header_labels(raw):
    """Synthetic stand-in for the native FilingHeader ITEMS parse."""
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

    def test_changed_frozen_values_are_refused(self):
        for path, bad in [(("serving", "context"), 4096), (("serving", "port"), 18232),
                          (("sampling", "temperature"), 0.7), (("sampling", "max_tokens"), 1024),
                          (("window", "minimum_free_mib"), 1024), (("window", "admission_floor_mib"), 8192),
                          (("sampling", "chat_template_kwargs"), {"enable_thinking": True})]:
            with self.subTest(path=path):
                plan = copy.deepcopy(PLAN)
                plan[path[0]][path[1]] = bad
                with self.assertRaises(ValueError):
                    EVAL.check_plan(plan)
        plan = copy.deepcopy(PLAN)
        plan["arms"][4]["runtime"] = {"tag": "b99999", "commit": "0" * 40}
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
                            ("MEMORY_MAX", window["memory_max"])]:
            with self.subTest(name=name):
                self.assertIn(f"readonly {name}={value}\n", text)
        self.assertIn(f"readonly COORDINATION_LINE='{window['coordination_line']}'", text)
        self.assertIn(f"PRODUCTION_UNIT={window['production_unit']}\n", text)
        self.assertIn(f"PRODUCTION_HEALTH={window['production_health']}\n", text)
        self.assertRegex((HERE / "README.md").read_text(), r"(?m)^GPU trials: \S")
        for forbidden in ("wsl --terminate", "wsl --shutdown", "native-stack-embeddings"):
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
        c1 = EVAL.server_argv(PLAN, "C1", "/rt", "/models")
        self.assertEqual(dict(zip(c1[1::2], c1[2::2]))["--gpu-layers"], "99")
        c2 = EVAL.server_argv(PLAN, "C2", "/rt", "/models")
        tail = c2[c2.index("--spec-type"):]
        self.assertEqual(tail, ["--spec-type", "draft-mtp", "--spec-draft-model",
                                "/models/qwen3.8-27b-4ca7207/MTP/mtp-Qwen3.8-27B-Q4_0.gguf",
                                "--spec-draft-ngl", "99", "--spec-draft-n-max", "3"])
        m = EVAL.server_argv(PLAN, "M", "/rt", "/models")
        self.assertIn("/models/mimo-v2.6-distill-qwen-9b-81baddc/MiMo-V2.6-Distill-Qwen-9B-Q8_0.gguf", m)
        for arm in ("B", "X"):
            with self.assertRaises(ValueError):
                EVAL.server_argv(PLAN, arm, "/rt", "/models")
        self.assertEqual([EVAL.admission_mib(PLAN, arm) for arm in ("C0", "C1", "C2", "M")],
                         [16384, 19968, 22016, 16384])

    def test_every_arm_is_pinned_by_revision_hash_and_size(self):
        for arm in PLAN["arms"]:
            for model in filter(None, [arm["model"], arm["profile"].get("draft")]):
                with self.subTest(arm=arm["id"], file=model["filename"]):
                    self.assertRegex(model["revision"], r"^[0-9a-f]{40}$")
                    self.assertRegex(model["sha256"], r"^[0-9a-f]{64}$")
                    self.assertIsInstance(model["bytes"], int)
                    self.assertTrue(model["license"])
        self.assertEqual({arm["id"]: arm["support_status"] for arm in PLAN["arms"]},
                         {"C0": "runnable", "C1": "runnable_if_admitted", "C2": "runnable_if_admitted",
                          "B": "runtime_unsupported", "M": "runnable", "X": "runtime_unsupported"})
        self.assertEqual(PLAN["not_arms"][0]["status"], "resource_infeasible")


@unittest.skipUnless(shutil.which("bash"), "bash is required")
class WindowGate(unittest.TestCase):
    """window.sh refusals that happen before it queries the GPU or touches any unit.

    It runs from a temporary copy whose README keeps the PENDING line, so HERE,
    the plan and the coordination note all resolve inside the copy.
    """

    def run_window(self, *arms):
        with tempfile.TemporaryDirectory() as temp:
            shutil.copy(HERE / "window.sh", temp)
            Path(temp, "README.md").write_text("GPU trials: PENDING\n")
            args = ["--acquisition", temp, "--inputs-sha256", "a" * 64, "--runtime-dir", temp,
                    "--models-dir", temp, "--state-dir", str(Path(temp) / "state")]
            result = subprocess.run(["bash", str(Path(temp) / "window.sh"), *arms, *args],
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
                              (("--arms", "X"), "runtime_unsupported"), ((), "usage")]:
            with self.subTest(arms=arms):
                result = self.run_window(*arms)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(message, result.stderr)


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


def filings(gold, predicted, speed, statuses=None):
    rows = []
    for index, (labels, items) in enumerate(zip(gold, predicted)):
        rows.append({"accession": f"0000000001-20-{index:06d}", "gold": labels, "predicted": items,
                     "parse_status": (statuses or ["valid"] * len(gold))[index], "http_status": 200,
                     "error": None, "predicted_n": 12, "predicted_per_second": speed, "prompt_ms": 900.0})
    return rows


class EndToEndAnalysis(unittest.TestCase):
    def write_arm(self, root, arm, rows, status="completed", events=(), window_status="completed"):
        directory = Path(root) / arm
        (directory / "eval").mkdir(parents=True)
        metrics = {"arm": arm, "plan_sha256": hashlib.sha256((HERE / "plan.json").read_bytes()).hexdigest(),
                   "prompt_sha256": PLAN["prompt_sha256"], "inputs_sha256": "a" * 64, "status": status,
                   "events": list(events), "filings": rows}
        (directory / "eval" / "metrics.json").write_text(json.dumps(metrics))
        (directory / "window.json").write_text(json.dumps({"arm": arm, "status": window_status,
                                                           "guard_events": [], "cold_load_ms": 4200}))
        (directory / "memory.csv").write_text("1,9000,15000\n2,9800,14200\n")
        return directory

    def test_faster_noninferior_arm_replaces_and_control_failure_is_inconclusive(self):
        gold = [["2.02", "9.01"], ["8.01"], ["5.02", "9.01"], ["7.01"]] * 10
        plan_sha = hashlib.sha256((HERE / "plan.json").read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            c0 = self.write_arm(temp, "C0", filings(gold, gold, 5.0))
            m = self.write_arm(temp, "M", filings(gold, gold, 40.0))
            c1 = self.write_arm(temp, "C1", filings(gold, [["2.02"]] * 40, 30.0))
            decision = ANALYZE.analyze(PLAN, plan_sha, [c0, c1, m])
            self.assertEqual(decision["selected"], {"arm": "M", "outcome": "replace_model"})
            by_arm = {result["arm"]: result for result in decision["arms"]}
            self.assertFalse(by_arm["C1"]["criteria"]["noninferior_micro_f1"])
            self.assertEqual(by_arm["M"]["summary"]["peak_device_used_mib"], 9800)
            self.assertEqual(by_arm["M"]["summary"]["cold_load_seconds"], 4.2)
            self.assertEqual(decision["arms_not_run"], ["C2", "B", "X"])
            self.assertNotIn('"input"', json.dumps(decision))
        with tempfile.TemporaryDirectory() as temp:
            c0 = self.write_arm(temp, "C0", filings(gold, gold, 5.0), events=["request-deadline:x"])
            m = self.write_arm(temp, "M", filings(gold, gold, 40.0))
            self.assertEqual(ANALYZE.analyze(PLAN, plan_sha, [c0, m])["selected"]["outcome"],
                             "inconclusive_control_invalid")
        with tempfile.TemporaryDirectory() as temp:
            c0 = self.write_arm(temp, "C0", filings(gold, gold, 5.0))
            m = self.write_arm(temp, "M", filings(gold[:-1], gold[:-1], 40.0))
            with self.assertRaises(ValueError):
                ANALYZE.analyze(PLAN, plan_sha, [c0, m])


class FakeResponse(io.BytesIO):
    def __init__(self, payload, status=200):
        super().__init__(json.dumps(payload).encode())
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class FakeServer:
    """Loopback stand-in: replies in turn with strict, fenced, prose and an HTTP 400."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.bodies = []

    def open(self, request, timeout=None):
        url = request if isinstance(request, str) else request.full_url
        if url.endswith("/v1/models"):
            return FakeResponse({"data": [{"id": "li26-c0"}]})
        if url.endswith("/props"):
            return FakeResponse({"model_path": "/models/qwen3.8-27b-4ca7207/Qwen3.8-27B-UD-Q4_K_M.gguf",
                                 "build_info": "b11146-7fe450e19"})
        self.bodies.append(json.loads(request.data))
        reply = self.replies.pop(0)
        if reply is None:
            raise urllib.error.HTTPError(url, 400, "exceeds context", {}, io.BytesIO(b"{}"))
        return FakeResponse({"choices": [{"finish_reason": "stop", "message": {"content": reply}}],
                             "usage": {"prompt_tokens": 900, "completion_tokens": 12},
                             "timings": {"prompt_n": 900, "prompt_ms": 850.0, "predicted_n": 12,
                                         "predicted_ms": 2400.0, "predicted_per_second": 5.0}})


class EvaluationRun(unittest.TestCase):
    def test_public_metrics_hold_codes_and_timings_but_no_document_text(self):
        secret = "UNIQUE-SYNTHETIC-FILING-TEXT"
        rows = [{"accession": f"0000000001-20-00000{index}", "labels": ["2.02", "9.01"],
                 "input": f"{secret} {index} Item 2.02", "truncated": False} for index in range(4)]
        payload = b"".join(json.dumps(row, sort_keys=True).encode() + b"\n" for row in rows)
        digest = hashlib.sha256(payload).hexdigest()
        server = FakeServer(['{"items": ["2.02", "9.01"]}', '```json\n{"items": ["2.02"]}\n```',
                             'The items are 2.02 and 9.01.', None])
        with tempfile.TemporaryDirectory() as temp:
            acquisition = Path(temp) / "acq"
            acquisition.mkdir()
            (acquisition / "inputs.jsonl").write_bytes(payload)
            (acquisition / "manifest.json").write_text(json.dumps({"status": "complete", "inputs": {"sha256": digest}}))
            out = Path(temp) / "eval"
            metrics = EVAL.run(HERE / "plan.json", "C0", acquisition, digest, "http://127.0.0.1:18299", out,
                               time.time() + 600, http=server)
            public = (out / "metrics.json").read_text()
            self.assertEqual(stat.S_IMODE(os.stat(out / "raw.private.jsonl").st_mode), 0o600)
            self.assertIn("The items are", (out / "raw.private.jsonl").read_text())
        self.assertEqual(metrics["status"], "completed")
        self.assertNotIn(secret, public)
        self.assertNotIn("The items are", public)
        self.assertEqual([f["parse_status"] for f in metrics["filings"]], ["valid", "fenced_valid", "invalid", "invalid"])
        self.assertEqual(metrics["filings"][3]["error"], "http_400")
        self.assertEqual(metrics["server"]["build_info"], "b11146-7fe450e19")
        body = server.bodies[0]
        self.assertEqual({key: body[key] for key in ("seed", "temperature", "top_k", "top_p", "max_tokens",
                                                     "chat_template_kwargs", "cache_prompt", "stream")},
                         {"seed": 0, "temperature": 0.0, "top_k": 1, "top_p": 1.0, "max_tokens": 256,
                          "chat_template_kwargs": {"enable_thinking": False}, "cache_prompt": False, "stream": False})
        content = body["messages"][0]["content"]
        self.assertIn(f"{secret} 0 Item 2.02", content)
        self.assertNotIn(EVAL.MARKER, content)
        self.assertTrue(content.startswith("You label a U.S. SEC current report"))

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
