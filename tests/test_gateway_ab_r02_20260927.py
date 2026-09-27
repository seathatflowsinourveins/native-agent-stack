"""Offline checks for the gateway-ab-r02-20260927 preregistration (R02: FW effort through the OmniRoute gateway).

Synthetic fixtures only: no gateway call, no promptfoo run and no private state. The one exception is the subset
rebuild, which runs only where li26's private acquisition exists and writes its tests files to a temporary
directory. The transform tests need Node, which promptfoo itself runs on. The statistics tests need numpy and scipy;
the project interpreter skips them, and the pinned run is
`uv run --with pytest --with scipy==1.18.1 --with statsmodels==0.15.0 --with numpy python -m pytest <this file> -q`.
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REL = "blueprints/convergence-practice/gateway-ab-r02-20260927"
HERE = ROOT / REL
LI26 = ROOT / "blueprints/convergence-practice/local-inference-latest-20260926"
TIERING_SCHEMA = ROOT / "blueprints/convergence-practice/gpt6-family-tiering-20260926/response.schema.json"
ACQUISITION = Path("~/.local/state/native-agent-stack/local-inference-latest-20260926/sec/acq-20260926").expanduser()
HAS_STATS = importlib.util.find_spec("numpy") is not None and importlib.util.find_spec("scipy") is not None
NODE = shutil.which("node")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD = load("r02_build_test", HERE / "build_r02.py")
PROMPT = load("r02_prompt_test", HERE / "prompt_r02.py")
ASSERTION = load("r02_assert_test", HERE / "assert_r02.py")
CALL_LOGS = load("r02_call_logs_test", HERE / "call_logs_by_correlation.py")
ANALYZE = load("r02_analyze_test", HERE / "analyze_r02.py")
LI26_EVAL_ARM = load("r02_li26_eval_arm_test", LI26 / "eval_arm.py")
LI26_ANALYZE = load("r02_li26_analyze_test", LI26 / "analyze.py")
PLAN = json.loads((HERE / "plan.json").read_text())
SAMPLING_FIELDS = {"temperature", "top_p", "top_k", "seed", "max_tokens", "max_completion_tokens",
                   "max_output_tokens", "reasoning_effort", "reasoning", "cache_prompt", "chat_template_kwargs"}


def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


# --- SSE fixtures -----------------------------------------------------------------------------------------------

def chunk(content=None, finish=None, usage=None, model="gpt-6-astra", choices=True, role=False):
    delta = {"role": "assistant"} if role else ({} if content is None else {"content": content})
    body = {"id": "chatcmpl-fixture", "object": "chat.completion.chunk", "created": 0, "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}] if choices else []}
    if usage is not None:
        body["usage"] = usage
    return "data: " + json.dumps(body) + "\n\n"


KEEPALIVE = ('data: {"id":"chatcmpl-keepalive","object":"chat.completion.chunk","created":0,"model":"keepalive",'
             '"choices":[{"index":0,"delta":{},"finish_reason":null}]}\n\n')
GATEWAY_ERROR = 'data: {"error":{"message":"Upstream stream failed before completion.","type":"stream_error"}}\n\n'
USAGE_B = {"prompt_tokens": 1493, "completion_tokens": 58, "total_tokens": 1551,
           "completion_tokens_details": {"reasoning_tokens": 37}, "prompt_tokens_details": {"cached_tokens": 1024}}
USAGE_A = {"prompt_tokens": 1493, "completion_tokens": 19, "total_tokens": 1512, "tokens_per_second": 39.5}
OK = {"status": 200, "statusText": "OK",
      "headers": {"X-Correlation-Id": "cid-fixture-1", "content-type": "text/event-stream"}}
DONE = "data: [DONE]\n\n"


def content_stream(usage=USAGE_B, usage_separate=False, finish="stop", done=True):
    parts = [chunk(role=True), chunk('{"items":'), chunk('["7.01"]}')]
    if usage_separate:
        parts += [chunk(finish=finish), chunk(usage=usage, choices=False)]
    else:
        parts.append(chunk(finish=finish, usage=usage))
    return "".join(parts) + (DONE if done else "")


@unittest.skipUnless(NODE, "the transform runs on Node, as promptfoo does")
class TransformTests(unittest.TestCase):
    """transform_r02.js as promptfoo calls it: (json, text, {response}) (src/providers/http.ts:2784-2786)."""

    RUNNER = """
const transform = require(process.argv[2]);
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(cases.map((item) => {
  try { return { result: transform(item.json, item.text, { response: item.response }) }; }
  catch (error) { return { thrown: String(error) }; }
})));
"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.runner = Path(cls.tmp.name) / "runner.js"
        cls.runner.write_text(cls.RUNNER)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_cases(self, cases):
        payload = [{"json": case.get("json"), "text": case["text"], "response": case.get("response", OK)}
                   for case in cases]
        completed = subprocess.run([NODE, str(self.runner), str(HERE / "transform_r02.js")],
                                   input=json.dumps(payload), capture_output=True, text=True, check=True,
                                   timeout=120)
        outcomes = json.loads(completed.stdout)
        for outcome in outcomes:
            self.assertNotIn("thrown", outcome)
        return [outcome["result"] for outcome in outcomes]

    def test_stream_output_usage_and_metadata(self):
        (result,) = self.run_cases([{"text": KEEPALIVE + ": comment\n\n" + content_stream()}])
        self.assertEqual(result["output"], '{"items":["7.01"]}')
        self.assertEqual(result["tokenUsage"], {"prompt": 1493, "completion": 58, "total": 1551, "numRequests": 1,
                                                "completionDetails": {"reasoning": 37,
                                                                      "cacheReadInputTokens": 1024}})
        self.assertNotIn("cached", result["tokenUsage"])
        self.assertEqual(result["metadata"]["http"], {"status": 200, "statusText": "OK",
                                                      "headers": {"x-correlation-id": "cid-fixture-1"}})
        r02 = result["metadata"]["r02"]
        self.assertEqual(r02["correlation_id"], "cid-fixture-1")
        self.assertEqual(r02["model"], "gpt-6-astra")
        self.assertEqual(r02["finish_reason"], "stop")
        self.assertTrue(r02["done_sentinel"])
        self.assertTrue(r02["usage_chunk_has_choices"])
        self.assertEqual(r02["usage"], USAGE_B)
        self.assertEqual(r02["data_after_done"], 0)

    def test_usage_from_the_last_usage_chunk_whatever_its_choices(self):
        separate, crlf, no_details = self.run_cases([
            {"text": content_stream(usage_separate=True)},
            {"text": content_stream().replace("\n", "\r\n")},
            {"text": content_stream(usage=USAGE_A)},
        ])
        self.assertEqual(separate["output"], '{"items":["7.01"]}')
        self.assertFalse(separate["metadata"]["r02"]["usage_chunk_has_choices"])
        self.assertEqual(separate["tokenUsage"]["completion"], 58)
        self.assertEqual(crlf["output"], '{"items":["7.01"]}')
        self.assertEqual(no_details["tokenUsage"], {"prompt": 1493, "completion": 19, "total": 1512,
                                                    "numRequests": 1})
        self.assertEqual(no_details["metadata"]["r02"]["usage"], USAGE_A)

    def test_failures_return_errors_with_the_correlation_id(self):
        results = self.run_cases([
            {"text": content_stream(usage=None)},
            {"text": content_stream(finish=None)},
            {"text": KEEPALIVE + GATEWAY_ERROR},
            {"text": "event: error\ndata: {\"message\": \"named error event\"}\n\n"},
            {"text": content_stream().replace(chunk('["7.01"]}'), 'data: {"broken": \n\n')},
            {"text": '{"error": {"message": "upstream failed"}}', "json": {"error": {"message": "upstream failed"}},
             "response": {**OK, "status": 500, "statusText": "Internal Server Error"}},
            {"text": '{"choices": []}', "json": {"choices": []}},
        ])
        prefixes = ["missing_usage", "missing_terminal_chunk", "sse_error_event", "sse_error_event",
                    "malformed_sse_chunks: 1", "http_status_500: ", "not_an_sse_stream"]
        for result, prefix in zip(results, prefixes):
            self.assertNotIn("output", result)
            self.assertTrue(result["error"].startswith(prefix), (prefix, result["error"]))
            self.assertEqual(result["metadata"]["r02"]["correlation_id"], "cid-fixture-1")
            self.assertEqual(result["metadata"]["http"]["headers"], {"x-correlation-id": "cid-fixture-1"})
        self.assertIn("Upstream stream failed", results[2]["error"])
        self.assertEqual(results[5]["metadata"]["http"]["status"], 500)

    def test_missing_correlation_header_is_null(self):
        (result,) = self.run_cases([{"text": content_stream(), "response": {**OK, "headers": {}}}])
        self.assertIsNone(result["metadata"]["r02"]["correlation_id"])
        self.assertEqual(result["output"], '{"items":["7.01"]}')

    def test_rate_limit_headers_and_dropped_count_go_to_r02_metadata(self):
        # Open question 3: the gateway's rate-limit forwarding class is any name containing "ratelimit" or
        # "rate-limit" (OmniRoute@dd6e9607e:open-sse/handlers/chatCore/responseHeaders.ts:145).
        headers = {**OK["headers"], "x-ratelimit-remaining-requests": "12", "X-RateLimit-Limit": "100",
                   "ratelimit-reset": "30", "x-codex-primary-used-percent": "4", "retry-after": "1",
                   "X-OmniRoute-Dropped-Upstream-Headers": "2"}
        expected = {"x-ratelimit-remaining-requests": "12", "x-ratelimit-limit": "100", "ratelimit-reset": "30"}
        success, failure, plain = self.run_cases([
            {"text": content_stream(), "response": {**OK, "headers": headers}},
            {"text": '{"error": {}}', "json": {"error": {}},
             "response": {**OK, "status": 503, "statusText": "Service Unavailable", "headers": headers}},
            {"text": content_stream()},
        ])
        for result in (success, failure):
            self.assertEqual(result["metadata"]["r02"]["rate_limit_headers"], expected)
            self.assertEqual(result["metadata"]["r02"]["dropped_upstream_headers"], "2")
            # promptfoo redacts x-ratelimit-* in metadata.http.headers; none are copied there.
            self.assertEqual(result["metadata"]["http"]["headers"], {"x-correlation-id": "cid-fixture-1"})
        self.assertEqual(success["output"], '{"items":["7.01"]}')
        self.assertTrue(failure["error"].startswith("http_status_503: "))
        self.assertEqual(plain["metadata"]["r02"]["rate_limit_headers"], {})
        self.assertIsNone(plain["metadata"]["r02"]["dropped_upstream_headers"])


class AssertionTests(unittest.TestCase):
    """assert_r02.get_assert: li26's parse_items and filing_scores as a promptfoo Python assertion."""

    def context(self, labels, prompt="rendered prompt", recorded=None):
        return {"vars": {"labels_json": json.dumps(labels), "prompt_sha256": recorded or sha256("rendered prompt")},
                "prompt": prompt}

    def test_valid_fenced_and_invalid(self):
        valid = ASSERTION.get_assert('{"items": ["7.01"]}', self.context(["7.01"]))
        self.assertEqual((valid["pass"], valid["score"]), (True, 1.0))
        self.assertEqual(valid["namedScores"], {"tp": 1, "fp": 0, "fn": 0, "prompt_ok": 1, "status_valid": 1,
                                                "status_fenced_valid": 0, "status_invalid": 0})
        fenced = ASSERTION.get_assert('```json\n{"items": ["7.01", "9.01"]}\n```', self.context(["7.01"]))
        self.assertTrue(fenced["pass"])
        self.assertEqual((fenced["namedScores"]["status_fenced_valid"], fenced["namedScores"]["fp"]), (1, 1))
        invalid = ASSERTION.get_assert("items: 7.01", self.context(["7.01", "2.02"]))
        self.assertFalse(invalid["pass"])
        self.assertEqual(invalid["score"], 0.0)
        self.assertEqual((invalid["namedScores"]["fn"], invalid["namedScores"]["status_invalid"]), (2, 1))
        duplicated = ASSERTION.get_assert('{"items": ["7.01", "7.01"]}', self.context(["7.01"]))
        self.assertEqual(duplicated["namedScores"]["status_invalid"], 1)

    def test_scores_match_li26(self):
        for output, gold in (('{"items": ["8.01"]}', ["7.01"]), ('{"items": []}', []), ('{"items": []}', ["5.02"])):
            predicted, _ = LI26_EVAL_ARM.parse_items(output)
            expected = LI26_ANALYZE.filing_scores(gold, predicted)
            result = ASSERTION.get_assert(output, self.context(gold))
            self.assertEqual(result["score"], expected["f1"])
            self.assertEqual([result["namedScores"][key] for key in ("tp", "fp", "fn")],
                             [expected[key] for key in ("tp", "fp", "fn")])

    def test_prompt_mismatch_fails(self):
        result = ASSERTION.get_assert('{"items": ["7.01"]}', self.context(["7.01"], prompt="another prompt"))
        self.assertFalse(result["pass"])
        self.assertEqual(result["namedScores"]["prompt_ok"], 0)
        self.assertIn("prompt=mismatch", result["reason"])


class PromptTests(unittest.TestCase):
    def test_li26_prompt_with_the_filing(self):
        template = LI26_EVAL_ARM.prompt_template(LI26_EVAL_ARM.load_plan())
        document = "ITEM 7.01 Regulation FD Disclosure. Synthetic filing text."
        expected = template.replace(LI26_EVAL_ARM.MARKER, document, 1)
        text = PROMPT.build_prompt({"vars": {"document": document, "prompt_sha256": sha256(expected),
                                             "accession": "0000000000-26-000001"}})
        self.assertEqual(text, expected)
        self.assertEqual(template.count(LI26_EVAL_ARM.MARKER), 1)
        # promptfoo renders a function prompt's text as Nunjucks (src/evaluatorHelpers.ts:396-419).
        self.assertFalse(any(opener in template for opener in BUILD.NUNJUCKS_OPENERS))

    def test_hash_mismatch_is_refused(self):
        with self.assertRaises(ValueError):
            PROMPT.build_prompt({"vars": {"document": "text", "prompt_sha256": "0" * 64, "accession": "x"}})


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tiering = json.loads(TIERING_SCHEMA.read_text())
        self.schema = BUILD.derive_schema(self.tiering)

    def test_schema_is_the_tiering_filing_object_without_accession(self):
        expected = copy.deepcopy(self.tiering["properties"]["filings"]["items"])
        del expected["properties"]["accession"]
        expected["required"] = ["items"]
        self.assertEqual(self.schema, expected)
        self.assertIs(self.schema["additionalProperties"], False)
        self.assertEqual(self.schema["properties"]["items"]["items"]["enum"],
                         self.tiering["properties"]["filings"]["items"]["properties"]["items"]["items"]["enum"])
        broken = copy.deepcopy(self.tiering)
        broken["properties"]["filings"]["items"]["additionalProperties"] = True
        with self.assertRaises(ValueError):
            BUILD.derive_schema(broken)

    def test_committed_configs_are_generated(self):
        for order in BUILD.ORDERS:
            self.assertEqual(BUILD.config_path(order).read_text(), BUILD.config_text(order, self.schema))

    def test_request_shape(self):
        for order, arms in (("ab", ["r02-A", "r02-B"]), ("ba", ["r02-B", "r02-A"])):
            text = BUILD.config_path(order).read_text()
            self.assertNotIn("json_object", text)
            config = json.loads(text)
            self.assertEqual([provider["label"] for provider in config["providers"]], arms)
            self.assertEqual(config["prompts"], ["file://prompt_r02.py:build_prompt"])
            self.assertEqual(config["defaultTest"]["assert"],
                             [{"type": "python", "value": "file://assert_r02.py:get_assert"}])
            for provider in config["providers"]:
                arm = provider["label"][-1]
                key = BUILD.ARMS[arm]["key"]
                settings = provider["config"]
                self.assertEqual(provider["id"], "http")
                self.assertEqual(settings["url"], "http://127.0.0.1:20128/v1/chat/completions")
                self.assertEqual(settings["maxRetries"], 0)
                self.assertEqual(settings["transformResponse"], "file://transform_r02.js")
                headers = settings["headers"]
                self.assertEqual(set(headers), {"Content-Type", "x-omniroute-session", "Idempotency-Key",
                                                "X-Correlation-Id", "X-OmniRoute-No-Cache"})
                self.assertFalse({name.lower() for name in headers} & {"authorization", "x-api-key"})
                self.assertEqual(headers["x-omniroute-session"],
                                 f"r02-{key}-{{{{accession}}}}-r{{{{__repeatIndex}}}}-{{{{__evalId}}}}")
                self.assertEqual(headers["Idempotency-Key"], f"r02-{key}-{{{{__evalId}}}}-{{{{__evalStepId}}}}")
                self.assertEqual(headers["X-Correlation-Id"], headers["Idempotency-Key"])
                self.assertEqual(headers["X-OmniRoute-No-Cache"], "true")
                body = settings["body"]
                self.assertEqual(set(body), {"model", "messages", "stream", "stream_options", "response_format"})
                self.assertFalse(SAMPLING_FIELDS & set(body))
                self.assertEqual(body["model"], BUILD.ARMS[arm]["model"])
                self.assertEqual(body["messages"], [{"role": "user", "content": "{{prompt}}"}])
                self.assertIs(body["stream"], True)
                self.assertEqual(body["response_format"], {"type": "json_schema", "json_schema": {
                    "name": "li26_filing_items", "strict": True, "schema": self.schema}})

    def test_arms_differ_only_in_model_and_key_prefix(self):
        config = BUILD.config("ab", self.schema)
        first, second = (copy.deepcopy(provider["config"]) for provider in config["providers"])
        for settings in (first, second):
            settings["body"].pop("model")
            for name in ("x-omniroute-session", "Idempotency-Key", "X-Correlation-Id"):
                settings["headers"][name] = settings["headers"][name][len("r02-a-"):]
        self.assertEqual(first, second)
        self.assertEqual(BUILD.ARMS, {"A": {"model": "cx/gpt-6-astra", "key": "a"},
                                      "B": {"model": "cx/gpt-6-astra-max", "key": "b"}})
        self.assertEqual(ANALYZE.ARM_KEYS, {arm: entry["key"] for arm, entry in BUILD.ARMS.items()})

    def test_analysis_rebuilds_the_rendered_correlation_id(self):
        # promptfoo renders __evalStepId as test-<testIdx>-prompt-<promptIdx>-repeat-<repeatIndex>
        # (promptfoo@0.123.1:dist/src/evaluator-DlYW7Rgb.js:7599-7605); the echo check observed it on the wire.
        eval_id = "eval-Ab3-2026-09-27T20:00:00"
        for arm in ("A", "B"):
            template = BUILD.provider(arm, self.schema)["config"]["headers"]["X-Correlation-Id"]
            rendered = template.replace("{{__evalId}}", eval_id).replace("{{__evalStepId}}",
                                                                          "test-5-prompt-1-repeat-2")
            self.assertEqual(rendered, ANALYZE.sent_id(arm, eval_id, 5, 1, 2))
            self.assertNotIn("{{", rendered)
            # The gateway keeps a caller id of 1-256 characters (correlationPreserve.ts:6-12).
            self.assertLessEqual(len(rendered), 256)


def synthetic_rows(count=360, seed=7):
    """Rows shaped like li26's inputs, with a skewed label-count distribution."""
    rows = []
    for index in range(count):
        digest = int(sha256(f"{seed}:{index}"), 16)
        size = [0, 1, 1, 1, 1, 2, 2, 3, 4, 6][digest % 10]
        labels = sorted({f"{1 + (digest >> shift) % 9}.0{(digest >> (shift + 4)) % 3 + 1}" for shift in
                         range(8, 8 + 8 * size, 8)})
        rows.append({"accession": f"0000000000-26-{index:06d}", "input": f"Synthetic filing {index}.",
                     "labels": labels})
    return rows


class SubsetTests(unittest.TestCase):
    def test_selection_is_deterministic_and_order_free(self):
        rows = synthetic_rows()
        first = BUILD.select(rows)
        self.assertEqual(first, BUILD.select(list(reversed(rows))))
        self.assertNotEqual([item["accession"] for item in first[0]],
                            [item["accession"] for item in BUILD.select(rows, seed=1)[0]])

    def test_stratified_proportional_allocation(self):
        rows = synthetic_rows()
        selection, population, counts = BUILD.select(rows)
        self.assertEqual(len(selection), 60)
        self.assertEqual(sum(counts.values()), 60)
        self.assertEqual(sum(population.values()), len(rows))
        for key, size in population.items():
            quota = 60 * size / len(rows)
            self.assertIn(counts[key], {int(quota), int(quota) + 1})
            members = sorted((BUILD.rank(row["accession"]), row["accession"]) for row in rows
                             if BUILD.stratum(row) == key)
            chosen = {item["accession"] for item in selection if item["stratum"] == key}
            self.assertEqual(chosen, {accession for _, accession in members[:counts[key]]})
        self.assertEqual(BUILD.allocate({0: 1, 1: 1}, 1), {0: 1, 1: 0})
        self.assertEqual(BUILD.allocate({0: 5, 1: 3, 2: 2}, 4), {0: 2, 1: 1, 2: 1})

    def test_runs_alternate_and_split_evenly(self):
        selection, _, _ = BUILD.select(synthetic_rows())
        self.assertEqual([item["run"] for item in selection], ["ab", "ba"] * 30)
        runs = {run: {item["accession"] for item in selection if item["run"] == run} for run in BUILD.ORDERS}
        self.assertEqual((len(runs["ab"]), len(runs["ba"])), (30, 30))
        self.assertFalse(runs["ab"] & runs["ba"])

    def test_tests_files(self):
        rows = synthetic_rows()
        selection, _, _ = BUILD.select(rows)
        template = "Classify.\n@@MARK@@\nEnd."
        raw = BUILD.tests_bytes(selection, "ab", template, "@@MARK@@")
        self.assertEqual(raw, BUILD.tests_bytes(selection, "ab", template, "@@MARK@@"))
        lines = [json.loads(line) for line in raw.decode().splitlines()]
        self.assertEqual(len(lines), 30)
        by_accession = {row["accession"]: row for row in rows}
        for line in lines:
            row = by_accession[line["vars"]["accession"]]
            self.assertEqual(json.loads(line["vars"]["labels_json"]), row["labels"])
            self.assertEqual(line["vars"]["prompt_sha256"],
                             sha256(template.replace("@@MARK@@", row["input"], 1)))
        with self.assertRaises(ValueError):
            BUILD.test_case({"accession": "x", "input": "a {{ tag }}", "labels": []}, template, "@@MARK@@")

    def test_private_files_are_owner_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tests-ab.jsonl"
            BUILD.write_private(path, b"{}\n")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class PlanTests(unittest.TestCase):
    def test_frozen_inputs_match_the_files(self):
        self.assertEqual(PLAN["frozen_inputs"], BUILD.frozen_record())
        self.assertEqual(set(PLAN["frozen_inputs"]),
                         {f"{REL}/{name}" for name in BUILD.HARNESS} | set(BUILD.UPSTREAM_INPUTS))

    def test_subset_record(self):
        subset = PLAN["subset"]
        self.assertEqual((subset["size"], subset["seed"]), (60, BUILD.SUBSET_SEED))
        self.assertEqual(subset["source"]["inputs_sha256"], BUILD.INPUTS_SHA256)
        ab, ba = subset["runs"]["ab"], subset["runs"]["ba"]
        self.assertEqual((len(ab), len(ba), len(set(ab) | set(ba))), (30, 30, 60))
        self.assertEqual(sum(entry["selected"] for entry in subset["strata"].values()), 60)
        for run in BUILD.ORDERS:
            self.assertRegex(subset["tests_files"][run]["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(subset["tests_files"][run]["tests"], 30)

    def test_plan_matches_the_configs(self):
        schema = BUILD.tiering_schema()
        self.assertEqual({arm: entry["model"] for arm, entry in PLAN["arms"].items()},
                         {arm: entry["model"] for arm, entry in BUILD.ARMS.items()})
        provider = BUILD.provider("A", schema)["config"]
        self.assertEqual(PLAN["request"]["url"], provider["url"])
        self.assertEqual(PLAN["request"]["body_fields"], sorted(provider["body"]))
        self.assertEqual(PLAN["request"]["headers"]["x-omniroute-session"],
                         "r02-<arm key>-{{accession}}-r{{__repeatIndex}}-{{__evalId}}")
        self.assertEqual(PLAN["request"]["headers"]["X-Correlation-Id"],
                         PLAN["request"]["headers"]["Idempotency-Key"])
        self.assertEqual(set(PLAN["request"]["headers"]) - {"Authorization"}, set(provider["headers"]))
        self.assertEqual(PLAN["request"]["schema_sha256"], sha256(BUILD.canonical(schema)))
        self.assertTrue({"temperature", "top_p", "seed", "max_tokens", "top_k", "cache_prompt",
                         "chat_template_kwargs"} <= set(PLAN["request"]["not_sent"]))
        self.assertEqual(PLAN["repeats"], 3)
        self.assertEqual(PLAN["status"], "draft-not-frozen-not-run")

    @unittest.skipUnless(ACQUISITION.is_dir(), "li26's private acquisition is not on this host")
    def test_subset_rebuilds_from_the_acquisition(self):
        with tempfile.TemporaryDirectory() as directory:
            record = BUILD.build_subset(ACQUISITION, directory)
            self.assertEqual(record, PLAN["subset"])
            for entry in record["tests_files"].values():
                path = Path(directory) / entry["name"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(Path(directory).stat().st_mode & 0o777, 0o700)


class CallLogsTests(unittest.TestCase):
    SENSITIVE = ("acct-secret-7", "conn-secret-9", "request body secret", "/private/path")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "storage.sqlite"
        connection = sqlite3.connect(self.db)
        connection.execute("CREATE TABLE call_logs (id INTEGER PRIMARY KEY, correlation_id TEXT, timestamp TEXT, "
                           "status INTEGER, model TEXT, reasoning_effort_requested TEXT, "
                           "reasoning_effort_upstream TEXT, account_id TEXT, connection_id TEXT, request_body TEXT, "
                           "artifact_path TEXT, tokens_in INTEGER)")
        # Rows in insertion (rowid) order. cid-b-3's two attempts share a timestamp, so insertion order decides;
        # cid-b-4's later attempt was inserted first, so the timestamp decides.
        rows = [("cid-a-1", "2026-09-27T10:00:01.000Z", 200, "gpt-6-astra", None, None),
                ("cid-b-1", "2026-09-27T10:00:02.000Z", 200, "gpt-6-astra-max", None, "max"),
                ("cid-b-2", "2026-09-27T10:00:03.000Z", 429, "gpt-6-astra-max", None, None),
                ("cid-b-2", "2026-09-27T10:00:04.000Z", 200, "gpt-6-astra-max", None, "max"),
                ("cid-other", "2026-09-27T10:00:05.000Z", 200, "gpt-6-astra-max", None, "max"),
                ("cid-b-3", "2026-09-27T10:00:06.000Z", 503, "gpt-6-astra-max", None, None),
                ("cid-b-3", "2026-09-27T10:00:06.000Z", 200, "gpt-6-astra-max", None, "max"),
                ("cid-b-4", "2026-09-27T10:00:08.000Z", 200, "gpt-6-astra-max", None, "max"),
                ("cid-b-4", "2026-09-27T10:00:07.000Z", 503, "gpt-6-astra-max", None, None)]
        for row in rows:
            connection.execute("INSERT INTO call_logs (correlation_id, timestamp, status, model, "
                               "reasoning_effort_requested, reasoning_effort_upstream, account_id, connection_id, "
                               "request_body, artifact_path, tokens_in) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               row + self.SENSITIVE + (1000,))
        connection.commit()
        connection.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_selects_only_the_allowlisted_columns(self):
        self.assertEqual(CALL_LOGS.COLUMNS, ("correlation_id", "timestamp", "status", "model",
                                             "reasoning_effort_requested", "reasoning_effort_upstream"))
        self.assertTrue(CALL_LOGS.QUERY.startswith(f"SELECT {', '.join(CALL_LOGS.COLUMNS)} FROM call_logs WHERE "
                                                   "correlation_id IN ("))
        # rowid only orders an id's rows; it is never selected.
        self.assertTrue(CALL_LOGS.QUERY.endswith(") ORDER BY correlation_id, timestamp, rowid"))
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        rows = CALL_LOGS.lookup(self.db, ["cid-a-1", "cid-b-2", "cid-missing"])
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)
        self.assertEqual([set(row) for row in rows], [set(CALL_LOGS.COLUMNS)] * 3)
        text = json.dumps(rows)
        for value in self.SENSITIVE:
            self.assertNotIn(value, text)

    def test_summary_and_unmatched(self):
        arms = {"A": ["cid-a-1", "cid-a-missing"], "B": ["cid-b-1", "cid-b-2", "cid-b-3", "cid-b-4"]}
        rows = CALL_LOGS.lookup(self.db, [identifier for ids in arms.values() for identifier in ids])
        summary = CALL_LOGS.summarize(arms, rows, include_rows=True)
        self.assertEqual((summary["A"]["rows"], summary["A"]["ids_matched"], summary["A"]["unmatched"]),
                         (1, 1, ["cid-a-missing"]))
        self.assertEqual(summary["A"]["rows_per_id"], {0: 1, 1: 1})
        self.assertEqual((summary["B"]["rows"], summary["B"]["ids_matched"], summary["B"]["unmatched"]), (7, 4, []))
        self.assertEqual(summary["B"]["rows_per_id"], {1: 1, 2: 3})
        self.assertEqual(summary["B"]["retried_ids"], ["cid-b-2", "cid-b-3", "cid-b-4"])

        def groups(key):
            return {(group["status"], group["upstream"]): group["count"] for group in summary["B"][key]}

        self.assertEqual(groups("all_rows_by_status_model_requested_upstream"),
                         {(200, "max"): 4, (429, None): 1, (503, None): 2})
        self.assertEqual(groups("final_rows_by_status_model_requested_upstream"), {(200, "max"): 4})
        attempts = [(row["correlation_id"], row["status"], row["attempt"], row["attempts"], row["final"])
                    for row in summary["B"]["matched_rows"]]
        self.assertEqual(attempts, [("cid-b-1", 200, 1, 1, True),
                                    ("cid-b-2", 429, 1, 2, False), ("cid-b-2", 200, 2, 2, True),
                                    ("cid-b-3", 503, 1, 2, False), ("cid-b-3", 200, 2, 2, True),
                                    ("cid-b-4", 503, 1, 2, False), ("cid-b-4", 200, 2, 2, True)])
        self.assertEqual(CALL_LOGS.summarize({"B": ["cid-b-1", "cid-b-1"]}, rows)["B"]["duplicate_ids"], 1)

    def test_batches_and_command_line(self):
        ids = [f"cid-missing-{index}" for index in range(1200)] + ["cid-b-1"]
        self.assertEqual(len(CALL_LOGS.lookup(self.db, ids)), 1)
        ids_file = Path(self.tmp.name) / "ids.json"
        ids_file.write_text(json.dumps({"A": ["cid-a-1"], "B": ["cid-b-1"]}))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            CALL_LOGS.main([str(self.db), str(ids_file)])
        report = json.loads(output.getvalue())
        self.assertEqual((report["A"]["rows"], report["B"]["rows"]), (1, 1))
        self.assertNotIn("matched_rows", report["A"])
        ids_file.write_text(json.dumps(["cid-a-1"]))
        with self.assertRaises(SystemExit):
            CALL_LOGS.main([str(self.db), str(ids_file)])


def result_row(arm, test_idx, accession, labels, output=None, error=None, usage=None, cid=None, latency=1000,
               prompt_idx=0, rate_limit_headers=None):
    """One promptfoo 0.123.1 result row as `-o results.json` persists it."""
    variables = {"accession": accession, "document": "Synthetic filing.", "labels_json": json.dumps(labels),
                 "prompt_sha256": "[REDACTED]"}
    row = {"provider": {"id": "http://127.0.0.1:20128/v1/chat/completions", "label": f"r02-{arm}"},
           "vars": variables, "testIdx": test_idx, "promptIdx": prompt_idx, "latencyMs": latency}
    metadata = {"http": {"status": 200, "headers": {"x-correlation-id": "[REDACTED]"}},
                "r02": {"correlation_id": cid, "usage": usage, "rate_limit_headers": rate_limit_headers or {},
                        "dropped_upstream_headers": None}}
    if error is not None:
        row.update({"success": False, "failureReason": 2, "error": error, "score": 0, "namedScores": {},
                    "response": {"error": error, "metadata": metadata} if cid else None})
        return row
    grading = ASSERTION.get_assert(output, {"vars": {**variables, "prompt_sha256": sha256("p")}, "prompt": "p"})
    row.update({"success": grading["pass"], "failureReason": 0 if grading["pass"] else 1,
                "score": grading["score"], "namedScores": grading["namedScores"],
                "response": {"output": output, "metadata": metadata}})
    if not grading["pass"]:
        row["error"] = grading["reason"]
    return row


def usage(completion, reasoning=0, prompt=1500, cached=0):
    value = {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion}
    if reasoning:
        value["completion_tokens_details"] = {"reasoning_tokens": reasoning}
    if cached:
        value["prompt_tokens_details"] = {"cached_tokens": cached}
    return value


def rendered_id(arm, eval_id, test_idx, prompt_idx, repeat):
    """The config's X-Correlation-Id with promptfoo's runtime vars filled in: __evalStepId is
    test-<testIdx>-prompt-<promptIdx>-repeat-<repeatIndex> (dist/src/evaluator-DlYW7Rgb.js:7599-7605)."""
    return f"r02-{arm.lower()}-{eval_id}-test-{test_idx}-prompt-{prompt_idx}-repeat-{repeat}"


def results_file(eval_id, filings, orders, repeats=3, outputs=None):
    """A promptfoo results file: tests in order, each repeat a new testIdx, the providers in `orders` (the prompt
    column index follows the provider order). Each row carries the gateway's echo of its sent id unless its
    spec sets `cid`."""
    outputs = outputs or {}
    rows, test_idx = [], 0
    for accession, labels in filings:
        for repeat in range(repeats):
            for prompt_idx, arm in enumerate(orders):
                spec = outputs.get((accession, repeat, arm)) or outputs.get(arm) or {}
                rows.append(result_row(arm, test_idx, accession, labels, prompt_idx=prompt_idx,
                                       cid=spec.get("cid", rendered_id(arm, eval_id, test_idx, prompt_idx, repeat)),
                                       latency=spec.get("latency", 1000),
                                       **{key: value for key, value in spec.items() if key not in ("latency", "cid")}))
            test_idx += 1
    return {"evalId": eval_id, "results": {"version": 3, "results": rows}}


FILINGS = [(f"0000000000-26-{index:06d}", labels) for index, labels in
           enumerate([["7.01"], ["2.02", "9.01"], ["5.02"], ["8.01", "9.01"], ["1.01"], ["7.01", "8.01"]])]


def perfect(labels):
    return json.dumps({"items": labels})


class AnalysisTests(unittest.TestCase):
    """analyze_r02.py extraction, pairing and decision rule; standard library only."""

    def test_error_kinds(self):
        cases = {"http_status_500: {}": "http_500", "sse_error_event: {}": "sse_error_event",
                 "missing_usage": "missing_usage",
                 "HttpRateLimitError: Rate limit exceeded: HTTP 429 Too Many Requests\n\n    at stack": "http_429",
                 "HttpRateLimitError: Quota exceeded: HTTP 429 Too Many Requests (code: quota)": "http_429",
                 "Error: Rate limited: 200 OK after 1 attempts": "rate_limit_header",
                 "Error: Request failed after 0 retries: Error: Request timed out after 300000 ms": "timeout",
                 "TypeError: unexpected": "other"}
        for message, kind in cases.items():
            self.assertEqual(ANALYZE.error_kind({"failureReason": 2, "error": message}), kind, message)
        self.assertIsNone(ANALYZE.error_kind({"failureReason": 1, "error": "parse=invalid; prompt=ok"}))

    def test_usage_fields_read_absent_details_as_zero(self):
        fields = ANALYZE.usage_fields(usage(19))
        self.assertEqual((fields["reasoning"], fields["cached"], fields["visible_output"]), (0, 0, 19))
        self.assertEqual((fields["reasoning_reported"], fields["cached_reported"]), (False, False))
        fields = ANALYZE.usage_fields(usage(58, reasoning=37, cached=1024))
        self.assertEqual((fields["reasoning"], fields["visible_output"], fields["uncached_input"]), (37, 21, 476))
        self.assertTrue(fields["reasoning_reported"] and fields["cached_reported"])
        self.assertTrue(all(ANALYZE.usage_fields(None)[key] is None for key in ANALYZE.USAGE_KEYS))

    def test_pairing_and_filing_sums(self):
        data = results_file("eval-ab", FILINGS[:2], ("A", "B"), outputs={
            "A": {"output": '{"items": ["7.01"]}', "usage": usage(20)},
            "B": {"output": '{"items": ["7.01", "9.01"]}', "usage": usage(60, reasoning=40)}})
        runs = {"ab": ANALYZE.run_calls(data, "ab")}
        pairs, problems = ANALYZE.pair_calls(runs, 3)
        self.assertEqual(problems, [])
        self.assertEqual(len(pairs), 6)
        self.assertEqual([pair["repeat"] for pair in pairs], [0, 1, 2, 0, 1, 2])
        filings, table_a, table_b = ANALYZE.filing_table(pairs)
        self.assertEqual(filings, [FILINGS[0][0], FILINGS[1][0]])
        self.assertEqual(table_a, [[3, 0, 0], [0, 3, 6]])
        self.assertEqual(table_b, [[3, 3, 0], [3, 3, 3]])
        self.assertEqual(ANALYZE.micro_f1(table_a), LI26_ANALYZE.micro_f1([(3, 3, 6)]))

    def test_pairing_problems(self):
        data = results_file("eval-ab", FILINGS[:1], ("A", "B"), repeats=2,
                            outputs={"A": {"output": "{}"}, "B": {"output": "{}"}})
        rows = ANALYZE.result_rows(data)
        del rows[-1]
        rows[0]["namedScores"]["tp"] = 5
        runs = {"ab": ANALYZE.run_calls(data, "ab")}
        pairs, problems = ANALYZE.pair_calls(runs, 2)
        self.assertEqual(len(pairs), 1)
        self.assertIn("ab: testIdx 1 lacks an arm", problems)
        self.assertIn(f"ab: {FILINGS[0][0]} has 1 complete repeats, expected 2", problems)
        self.assertEqual(runs["ab"][0]["problems"], ["assertion scores differ from li26 rescoring"])
        both = {"ab": runs["ab"], "ba": [dict(call, run="ba") for call in runs["ab"]]}
        self.assertIn("a filing appears in both runs", ANALYZE.pair_calls(both, 2)[1])

    def test_errors_score_as_not_returned(self):
        data = results_file("eval-ab", FILINGS[1:2], ("A", "B"), repeats=1, outputs={
            "A": {"error": "HttpRateLimitError: Rate limit exceeded: HTTP 429 Too Many Requests", "cid": None},
            "B": {"error": "sse_error_event: {\"message\": \"x\"}", "usage": None}})
        self.assertIsNone(ANALYZE.result_rows(data)[0]["response"])
        calls = ANALYZE.run_calls(data, "ab")
        self.assertEqual([(call["tp"], call["fp"], call["fn"]) for call in calls], [(0, 0, 2), (0, 0, 2)])
        self.assertEqual([call["error_kind"] for call in calls], ["http_429", "sse_error_event"])
        # A call thrown before the transform has no echoed id, but its sent id is rebuilt.
        self.assertIsNone(calls[0]["correlation_id"])
        self.assertEqual(calls[0]["sent_id"], rendered_id("A", "eval-ab", 0, 0, 0))
        self.assertEqual(calls[1]["correlation_id"], calls[1]["sent_id"])
        self.assertEqual([call["problems"] for call in calls], [[], []])

    def test_sent_ids_are_rebuilt_for_every_call(self):
        # BA order: B is the first provider, so its prompt column index is 0.
        data = results_file("eval-ba", FILINGS[:2], ("B", "A"), repeats=2, outputs={
            "A": {"output": "{}"}, "B": {"output": "{}"},
            (FILINGS[1][0], 1, "A"): {"error": "Error: Request timed out after 300000 ms", "cid": None}})
        rows = ANALYZE.result_rows(data)
        self.assertEqual(ANALYZE.repeat_by_step(rows), {0: 0, 1: 1, 2: 0, 3: 1})
        expected = {"A": [rendered_id("A", "eval-ba", step, 1, step % 2) for step in range(4)],
                    "B": [rendered_id("B", "eval-ba", step, 0, step % 2) for step in range(4)]}
        self.assertEqual({arm: [identifier for row_arm, identifier, _ in ANALYZE.sent_calls(data)
                                if row_arm == arm] for arm in ("A", "B")}, expected)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.json"
            path.write_text(json.dumps(data))
            self.assertEqual(ANALYZE.correlation_ids([path]), expected)
            # The repeat is testIdx minus the filing's smallest testIdx, whatever the row order.
            data["results"]["results"].reverse()
            path.write_text(json.dumps(data))
            self.assertEqual({arm: sorted(ids) for arm, ids in ANALYZE.correlation_ids([path]).items()},
                             {arm: sorted(ids) for arm, ids in expected.items()})

    def test_echo_mismatch_and_missing_eval_id_are_refused(self):
        data = results_file("eval-ab", FILINGS[:1], ("A", "B"), repeats=1,
                            outputs={"A": {"output": "{}", "cid": "gateway-generated-id"}, "B": {"output": "{}"}})
        calls = ANALYZE.run_calls(data, "ab")
        self.assertEqual(calls[0]["problems"], ["the gateway's X-Correlation-Id differs from the sent id"])
        self.assertEqual(ANALYZE.correlation_summary(calls)[0]["A"],
                         {"calls": 1, "sent_ids": 1, "echoed": 1, "echo_mismatch": 1})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.json"
            path.write_text(json.dumps(data))
            with self.assertRaises(SystemExit):
                ANALYZE.correlation_ids([path])
            del data["evalId"]
            path.write_text(json.dumps(data))
            with self.assertRaises(SystemExit):
                ANALYZE.correlation_ids([path])

    def test_decision_rule(self):
        self.assertEqual(ANALYZE.decide(0.001, -0.5, 10, 20), "adopt_max")
        self.assertEqual(ANALYZE.decide(0.0, -0.02, 10, 20), "keep_medium")
        self.assertEqual(ANALYZE.decide(0.0, -0.021, 10, 20), "inconclusive")
        self.assertEqual(ANALYZE.decide(-0.1, 0.0, 30, 20), "inconclusive")
        self.assertEqual(ANALYZE.decide(-0.1, 0.0, None, 20), "inconclusive")

    @staticmethod
    def log_row(identifier, second, status, upstream=None):
        """A call_logs row as call_logs_by_correlation.lookup returns it (the six allowlisted columns)."""
        return {"correlation_id": identifier, "timestamp": f"2026-09-27T10:00:{second:02d}.000Z", "status": status,
                "model": "gpt-6-astra", "reasoning_effort_requested": None, "reasoning_effort_upstream": upstream}

    def test_correlation_ids_and_call_log_join(self):
        data = results_file("eval-ab", FILINGS[:1], ("A", "B"), repeats=1,
                            outputs={"A": {"output": "{}", "usage": usage(20)},
                                     "B": {"output": "{}", "usage": usage(60, reasoning=40)}})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.json"
            path.write_text(json.dumps(data))
            ids = ANALYZE.correlation_ids([path])
        self.assertEqual(ids, {"A": ["r02-a-eval-ab-test-0-prompt-0-repeat-0"],
                               "B": ["r02-b-eval-ab-test-0-prompt-1-repeat-0"]})
        calls = ANALYZE.run_calls(data, "ab")
        # B: a 429 attempt, then the 200 attempt the client received.
        rows = [self.log_row(ids["A"][0], 1, 200), self.log_row(ids["B"][0], 2, 429),
                self.log_row(ids["B"][0], 3, 200, "max")]
        call_logs = CALL_LOGS.summarize(ids, rows, include_rows=True)
        summary, problems = ANALYZE.call_log_summary(json.loads(json.dumps(call_logs)), calls)
        self.assertEqual(problems, [])
        self.assertEqual(summary["A"]["effort_observed"], {"requested": {}, "upstream": {}})
        self.assertEqual(summary["A"]["effort_not_observed_calls"], {"requested": 1, "upstream": 1})
        self.assertEqual(summary["B"]["effort_observed"]["upstream"], {"max": 1})
        self.assertEqual((summary["B"]["attempt_rows"], summary["B"]["http_429_attempt_rows"],
                          summary["B"]["http_429_final"], summary["B"]["retried_calls"]), (2, 1, 0, 1))
        self.assertEqual(summary["B"]["attempts_per_call"], {2: 1})
        self.assertEqual(summary["B"]["final_status"], {"200": 1})
        self.assertEqual(summary["B"]["attempt_status"], {"200": 1, "429": 1})

    def test_final_rows_and_unmatched_calls_by_client_outcome(self):
        # Two repeats per arm. A: repeat 0 graded; repeat 1 a client-side 429 thrown before the transform, whose
        # gateway row is joined through its rebuilt id. B: repeat 0 graded after a 503 attempt; repeat 1 a
        # timeout with no call_logs row.
        data = results_file("eval-ab", FILINGS[:1], ("A", "B"), repeats=2, outputs={
            "A": {"output": "{}"}, "B": {"output": "{}"},
            (FILINGS[0][0], 1, "A"): {"error": "HttpRateLimitError: Rate limit exceeded: HTTP 429", "cid": None},
            (FILINGS[0][0], 1, "B"): {"error": "Error: Request timed out after 300000 ms", "cid": None}})
        calls = ANALYZE.run_calls(data, "ab")
        a0, b0, a1, b1 = (call["sent_id"] for call in calls)
        rows = [self.log_row(a0, 1, 200), self.log_row(b0, 2, 503), self.log_row(b0, 4, 200, "max"),
                self.log_row(a1, 5, 429)]
        call_logs = CALL_LOGS.summarize({"A": [a0, a1], "B": [b0, b1]}, rows, include_rows=True)
        self.assertEqual((call_logs["B"]["retried_ids"], call_logs["B"]["unmatched"]), ([b0], [b1]))
        summary, problems = ANALYZE.call_log_summary(call_logs, calls)
        self.assertEqual(problems, [])
        self.assertEqual((summary["A"]["calls_matched"], summary["A"]["calls_unmatched"]), (2, 0))
        self.assertEqual(summary["A"]["final_status"], {"200": 1, "429": 1})
        self.assertEqual((summary["A"]["http_429_final"], summary["A"]["http_429_attempt_rows"]), (1, 1))
        self.assertEqual(summary["A"]["client_outcome_by_final_status"],
                         [{"client": "http_429", "final_status": "429", "count": 1},
                          {"client": "no_provider_error", "final_status": "200", "count": 1}])
        self.assertEqual((summary["B"]["calls_matched"], summary["B"]["calls_unmatched"]), (1, 1))
        self.assertEqual(summary["B"]["unmatched_by_client_outcome"], {"timeout": 1})
        self.assertEqual((summary["B"]["retried_calls"], summary["B"]["final_status"]), (1, {"200": 1}))
        self.assertEqual(summary["B"]["attempt_status"], {"200": 1, "503": 1})
        self.assertEqual(summary["B"]["effort_observed"]["upstream"], {"max": 1})
        self.assertEqual(summary["B"]["client_outcome_by_final_status"],
                         [{"client": "no_provider_error", "final_status": "200", "count": 1},
                          {"client": "timeout", "final_status": "no_row", "count": 1}])

    def test_call_log_rows_without_attempt_numbers_are_a_problem(self):
        data = results_file("eval-ab", FILINGS[:1], ("A", "B"), repeats=1,
                            outputs={"A": {"output": "{}"}, "B": {"output": "{}"}})
        calls = ANALYZE.run_calls(data, "ab")
        unnumbered = {"A": {"matched_rows": [self.log_row(calls[0]["sent_id"], 1, 503),
                                             self.log_row(calls[0]["sent_id"], 2, 200)]}}
        summary, problems = ANALYZE.call_log_summary(unnumbered, calls)
        self.assertEqual(len(problems), 1)
        self.assertIn("one final row", problems[0])
        self.assertEqual(summary["A"]["final_status"], {})

    def test_filing_means_leave_out_filings_without_usage(self):
        data = results_file("eval-ab", FILINGS[:2], ("A", "B"), repeats=2, outputs={
            "A": {"output": "{}", "usage": usage(20)}, "B": {"output": "{}", "usage": usage(60, reasoning=40)},
            (FILINGS[1][0], 0, "A"): {"error": "Error: Request timed out after 300000 ms"},
            (FILINGS[1][0], 1, "A"): {"error": "Error: Request timed out after 300000 ms"}})
        runs = {"ab": ANALYZE.run_calls(data, "ab")}
        pairs, _ = ANALYZE.pair_calls(runs, 2)
        sample_a, sample_b, left_out = ANALYZE.filing_means(pairs, "reasoning")
        self.assertEqual((sample_a, sample_b, left_out), ([0.0], [40.0], 1))


@unittest.skipUnless(HAS_STATS, "numpy and scipy are not installed for this interpreter")
class StatisticsTests(unittest.TestCase):
    """analyze_r02.analyze with scipy's bootstrap and permutation test on synthetic results."""

    def run_analysis(self, outputs_ab, outputs_ba):
        return ANALYZE.analyze({"ab": results_file("eval-ab", FILINGS[:3], ("A", "B"), outputs=outputs_ab),
                                "ba": results_file("eval-ba", FILINGS[3:], ("B", "A"), outputs=outputs_ba)}, 3)

    def test_max_better_on_every_filing_is_adopted(self):
        outputs = {"A": {"output": '{"items": []}', "usage": usage(20, cached=512), "latency": 1000,
                         "rate_limit_headers": {"x-ratelimit-remaining-requests": "12"}},
                   "B": {"usage": usage(60, reasoning=40), "latency": 4000}}
        per_filing = {}
        for accession, labels in FILINGS:
            for repeat in range(3):
                per_filing[(accession, repeat, "B")] = {"output": perfect(labels), **outputs["B"]}
        report = self.run_analysis({**outputs, **per_filing}, {**outputs, **per_filing})
        self.assertEqual((report["status"], report["problems"]), ("analysis", []))
        self.assertEqual((report["pairs"], report["filings"]), (18, 6))
        self.assertEqual(report["micro_f1"], {"A": 0.0, "B": 1.0})
        self.assertEqual(report["tests"]["b_minus_a"]["point"], 1.0)
        self.assertEqual(report["tests"]["b_minus_a"]["lower_one_sided_95"], 1.0)
        self.assertLessEqual(report["tests"]["permutation_b_minus_a"]["p_value_greater"], 1 / 64 + 1e-12)
        self.assertEqual(report["decision"]["result"], "adopt_max")
        self.assertEqual(report["holm"]["applied"], False)
        effort = report["effort"]
        self.assertEqual(effort["primary"], "reasoning_tokens")
        self.assertEqual(effort["reasoning_tokens"]["b_minus_a"]["point"], 40.0)
        self.assertGreater(effort["reasoning_tokens"]["b_minus_a"]["lower_one_sided_95"], 0)
        arm_a, arm_b = report["arms"]["A"], report["arms"]["B"]
        self.assertEqual((arm_a["latency_ms"]["p50"], arm_b["latency_ms"]["p95"]), (1000.0, 4000.0))
        self.assertEqual(arm_a["calls_with_details"], {"reasoning_tokens": 0, "cached_tokens": 18})
        self.assertAlmostEqual(arm_a["cached_input_share"], 512 / 1500)
        self.assertEqual(arm_a["reasoning_tokens"]["zero_share"], 1.0)
        self.assertEqual(arm_b["tokens_per_filing"]["visible_output"], 20.0)
        self.assertEqual(arm_a["strict_schema_validity"], 1.0)
        self.assertEqual(arm_a["rate_limit_headers"],
                         {"calls_with_any": 18, "names": {"x-ratelimit-remaining-requests": 18}})
        self.assertEqual(arm_b["rate_limit_headers"], {"calls_with_any": 0, "names": {}})
        self.assertEqual(report["correlation"]["A"], {"calls": 18, "sent_ids": 18, "echoed": 18, "echo_mismatch": 0})

    def test_identical_quality_and_cheaper_medium_keeps_medium(self):
        per_filing = {}
        for accession, labels in FILINGS:
            for repeat in range(3):
                per_filing[(accession, repeat, "A")] = {"output": perfect(labels[:1]), "usage": usage(20)}
                per_filing[(accession, repeat, "B")] = {"output": perfect(labels[:1]), "usage": usage(50, 30)}
        report = self.run_analysis(per_filing, per_filing)
        self.assertEqual(report["tests"]["b_minus_a"]["lower_one_sided_95"], 0.0)
        self.assertEqual(report["tests"]["a_minus_b"]["lower_one_sided_95"], 0.0)
        self.assertEqual(report["decision"]["result"], "keep_medium")

    def test_bootstrap_matches_a_direct_resampling(self):
        import numpy as np

        per_filing = {}
        for index, (accession, labels) in enumerate(FILINGS):
            for repeat in range(3):
                good = (index + repeat) % 3 != 0
                per_filing[(accession, repeat, "A")] = {"output": perfect(labels if good else labels[:1]),
                                                        "usage": usage(20)}
                per_filing[(accession, repeat, "B")] = {"output": perfect(labels if index % 2 else ["9.01"]),
                                                        "usage": usage(50, 30)}
        report = self.run_analysis(per_filing, per_filing)
        runs = {"ab": results_file("eval-ab", FILINGS[:3], ("A", "B"), outputs=per_filing),
                "ba": results_file("eval-ba", FILINGS[3:], ("B", "A"), outputs=per_filing)}
        calls = {run: ANALYZE.run_calls(data, run) for run, data in runs.items()}
        _, table_a, table_b = ANALYZE.filing_table(ANALYZE.pair_calls(calls, 3)[0])
        # scipy 1.18.1 draws one (n_resamples, n) index matrix (_resampling.py _bootstrap_resample, rng_integers)
        # and takes the linear 5th percentile (stats.quantile) for a one-sided "greater" bound.
        draws = np.random.default_rng(ANALYZE.SEED).integers(0, 6, size=(ANALYZE.RESAMPLES, 6), dtype="int64")
        differences = [LI26_ANALYZE.micro_f1([table_b[i] for i in row]) -
                       LI26_ANALYZE.micro_f1([table_a[i] for i in row]) for row in draws]
        self.assertAlmostEqual(report["tests"]["b_minus_a"]["lower_one_sided_95"],
                               float(np.quantile(differences, 0.05)), places=12)
        self.assertAlmostEqual(report["tests"]["b_minus_a"]["point"],
                               LI26_ANALYZE.micro_f1(table_b) - LI26_ANALYZE.micro_f1(table_a), places=12)


if __name__ == "__main__":
    unittest.main()
