"""Offline checks for the gateway-ab-r02-20260927 preregistration (R02: FW effort through the OmniRoute gateway).

Synthetic fixtures only: no gateway call, no promptfoo eval and no private state. The exceptions only read local
installations: the subset rebuild runs only where li26's private acquisition exists and writes its tests files to a
temporary directory; the promptfoo build check and the native checks run only where promptfoo is on PATH (they
import the installed package offline: its assertions API for the committed assertions, and its EvalResult for the
rows a results file holds). The transform tests need Node, which promptfoo itself runs on. The statistics tests
need numpy and scipy; the project interpreter skips them, and the pinned run is `uv run --no-project --python 3.14
--with numpy==2.5.3 --with scipy==1.18.1 --with statsmodels==0.15.0 python -m unittest
tests.test_gateway_ab_r02_20260927` (plan.json analysis_environment).
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import statistics
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
SCHEMA = BUILD.tiering_schema()
SAMPLING_FIELDS = {"temperature", "top_p", "top_k", "seed", "max_tokens", "max_completion_tokens",
                   "max_output_tokens", "reasoning_effort", "reasoning", "cache_prompt", "chat_template_kwargs"}


def installed_promptfoo():
    try:
        return BUILD.promptfoo_package()
    except SystemExit:
        return None


PROMPTFOO_PACKAGE = installed_promptfoo()
# This build's EvalResult module (export t), whose rows `-o results.json` holds; plan.json promptfoo_build pins the
# build and with it this chunk name.
EVAL_RESULT_MODULE = PROMPTFOO_PACKAGE / "dist/src/evalResult-yO_CeNru.js" if PROMPTFOO_PACKAGE else None


def promptfoo_environment(directory):
    """The environment of an offline promptfoo import: no inherited PROMPTFOO_ setting, telemetry off, and config
    and log directories inside `directory`."""
    environment = {name: value for name, value in os.environ.items() if not name.startswith("PROMPTFOO_")}
    environment.update({"PROMPTFOO_DISABLE_TELEMETRY": "1", "PROMPTFOO_CONFIG_DIR": str(Path(directory) / "config"),
                        "PROMPTFOO_LOG_DIR": str(Path(directory) / "logs")})
    return environment


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
            # li26's scorer, then promptfoo's is-json with the sent schema at its default weight: a weight of 0
            # would turn its pass into true (promptfoo@0.123.1 dist/src/evaluator-DlYW7Rgb.js:5790-5793).
            self.assertEqual(config["defaultTest"]["assert"],
                             [{"type": "python", "value": "file://assert_r02.py:get_assert"},
                              {"type": "is-json", "value": self.schema}])
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
                # The is-json assertion checks exactly the schema this provider sends.
                self.assertEqual(config["defaultTest"]["assert"][1]["value"],
                                 body["response_format"]["json_schema"]["schema"])

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
        self.assertEqual(ANALYZE.ORDERS, BUILD.ORDERS)

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


@unittest.skipUnless(NODE and PROMPTFOO_PACKAGE, "needs Node and the promptfoo installation on PATH")
class NativeSchemaTests(unittest.TestCase):
    """The committed config's is-json assertion run by the installed promptfoo's own assertions API
    (assertions.runAssertions, dist/src/index.js:22775-22800) with no provider call: our integration check of the
    upstream behaviour the analysis reads, not an upstream test."""

    SCRIPT = """
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
const [pkg, configPath, casesPath] = process.argv.slice(2);
const { assertions } = await import(pathToFileURL(pkg + '/dist/src/index.js').href);
const config = JSON.parse(readFileSync(configPath, 'utf8'));
const isJson = config.defaultTest.assert.find((item) => item.type === 'is-json');
const results = [];
for (const item of JSON.parse(readFileSync(casesPath, 'utf8'))) {
  const assertion = item.weight === undefined ? isJson : { ...isJson, weight: item.weight };
  const graded = await assertions.runAssertions({ test: { vars: {}, assert: [assertion] },
                                                  providerResponse: { output: item.output } });
  const component = graded.componentResults[0];
  results.push({ pass: component.pass, score: component.score, type: component.assertion.type,
                 value: component.assertion.value, components: graded.componentResults.length });
}
process.stdout.write('\\n' + JSON.stringify(results) + '\\n');
"""

    def test_is_json_rejects_what_li26_accepts(self):
        cases = [{"output": '{"items":["7.01"]}'}, {"output": '{"items":["9.99"]}'},
                 {"output": '```json\n{"items":["7.01"]}\n```'}, {"output": '{"items":["7.01"],"extra":1}'},
                 {"output": '{"items":["9.99"]}', "weight": 0}]
        with tempfile.TemporaryDirectory() as directory:
            script, cases_path = Path(directory) / "is_json.mjs", Path(directory) / "cases.json"
            script.write_text(self.SCRIPT)
            cases_path.write_text(json.dumps(cases))
            completed = subprocess.run([NODE, str(script), str(PROMPTFOO_PACKAGE), str(BUILD.config_path("ab")),
                                        str(cases_path)], capture_output=True, text=True, check=True, timeout=300,
                                       env=promptfoo_environment(directory))
        results = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual([result["type"] for result in results], ["is-json"] * 5)
        # The component result keeps the assertion with the schema, which the analysis hashes; one component each.
        self.assertEqual([result["value"] for result in results], [SCHEMA] * 5)
        self.assertEqual([result["components"] for result in results], [1] * 5)
        # The enum rejects 9.99; a fenced or extended object is not the schema's object either.
        self.assertEqual([result["pass"] for result in results[:4]], [True, False, False, False])
        # At weight 0 promptfoo reports pass true whatever the check found, which is why the config keeps the
        # default weight (dist/src/evaluator-DlYW7Rgb.js:5790-5793).
        self.assertEqual((results[4]["pass"], results[4]["score"]), (True, 0))
        # li26's parser accepts the same output as valid, which is why its status is not strict-schema validity.
        self.assertEqual(LI26_EVAL_ARM.parse_items('{"items":["9.99"]}'), (["9.99"], "valid"))

    GRADE = """
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
const [pkg, configPath, casesPath, assertPath] = process.argv.slice(2);
const { assertions } = await import(pathToFileURL(pkg + '/dist/src/index.js').href);
const config = JSON.parse(readFileSync(configPath, 'utf8'));
const asserts = config.defaultTest.assert.map((item) =>
  item.type === 'python' ? { ...item, value: 'file://' + assertPath + ':get_assert' } : item);
const results = [];
for (const item of JSON.parse(readFileSync(casesPath, 'utf8'))) {
  results.push(await assertions.runAssertions({ prompt: item.prompt, vars: item.vars,
    test: { vars: item.vars, assert: asserts }, providerResponse: { output: item.output } }));
}
process.stdout.write('\\n' + JSON.stringify(results) + '\\n');
"""

    def test_the_committed_assertions_grade_as_the_analysis_reads(self):
        # Both committed assertions, li26's Python scorer (run by promptfoo's own Python runner) and is-json, graded
        # by promptfoo; each grading result, placed on a row as the evaluator does (dist/src/
        # evaluator-DlYW7Rgb.js:7523-7534), must pass the analysis's rescoring and schema checks.
        accession, labels = FILINGS[0]
        cases = [('{"items": ["7.01"]}', "valid", True), ('{"items": ["9.99"]}', "valid", False),
                 ('```json\n{"items": ["7.01", "9.01"]}\n```', "fenced_valid", False),
                 ("items: 7.01", "invalid", False)]
        variables = {"accession": accession, "document": "Synthetic filing.", "labels_json": json.dumps(labels),
                     "prompt_sha256": PROMPT_SHA256}
        with tempfile.TemporaryDirectory() as directory:
            script, cases_path = Path(directory) / "grade.mjs", Path(directory) / "cases.json"
            script.write_text(self.GRADE)
            cases_path.write_text(json.dumps([{"output": output, "prompt": "p", "vars": variables}
                                              for output, _, _ in cases]))
            completed = subprocess.run([NODE, str(script), str(PROMPTFOO_PACKAGE), str(BUILD.config_path("ab")),
                                        str(cases_path), str(HERE / "assert_r02.py")], capture_output=True,
                                       text=True, check=True, timeout=600, env=promptfoo_environment(directory))
        graded = json.loads(completed.stdout.strip().splitlines()[-1])
        for (output, status, schema_valid), grading in zip(cases, graded):
            self.assertEqual([component["assertion"]["type"] for component in grading["componentResults"]],
                             ["python", "is-json"])
            row = result_row("A", 0, accession, labels, output=output, usage=usage(20),
                             cid=rendered_id("A", "eval-ab", 0, 0, 0))
            row.update({"gradingResult": grading, "namedScores": grading["namedScores"], "success": grading["pass"],
                        "score": grading["score"], "failureReason": 0 if grading["pass"] else 1})
            call = ANALYZE.call_record(row, "ab", "eval-ab", FROZEN)
            self.assertEqual((call["problems"], call["status"], call["schema_valid"]), ([], status, schema_valid),
                             output)
            self.assertEqual(grading["pass"], schema_valid)


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

    def test_frozen_inputs_cover_every_repository_file_the_harness_loads(self):
        # li26's eval_arm.py executes scripts/path_safety.py (eval_arm.py:54-56), so it is frozen too.
        closure = BUILD.module_closure()
        self.assertEqual(set(closure), {f"{REL}/{name}" for name, _ in BUILD.ENTRY_POINTS} | {
            "blueprints/convergence-practice/local-inference-latest-20260926/eval_arm.py",
            "blueprints/convergence-practice/local-inference-latest-20260926/analyze.py",
            "scripts/path_safety.py"})
        self.assertEqual(BUILD.closure_problems(closure, PLAN["frozen_inputs"]), [])
        self.assertEqual(BUILD.closure_problems(closure + ["scripts/unfrozen.py"], PLAN["frozen_inputs"]),
                         ["scripts/unfrozen.py"])

    def test_promptfoo_build_digest_covers_the_package_outside_node_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "lib/node_modules/promptfoo"
            (root / "dist/src").mkdir(parents=True)
            (root / "node_modules/dependency").mkdir(parents=True)
            (root / "package.json").write_text(json.dumps({"name": "promptfoo", "version": "0.123.1"}))
            (root / "dist/src/entrypoint.js").write_text("// entry\n")
            (root / "node_modules/dependency/index.js").write_text("// dependency\n")
            (Path(directory) / "bin").mkdir()
            (Path(directory) / "bin/promptfoo").symlink_to(root / "dist/src/entrypoint.js")
            self.assertEqual(BUILD.promptfoo_package(str(Path(directory) / "bin/promptfoo")), root.resolve())
            digest, files = BUILD.tree_digest(root)
            self.assertEqual(files, 2)
            (root / "node_modules/dependency/index.js").write_text("// another dependency build\n")
            self.assertEqual(BUILD.tree_digest(root), (digest, 2))
            (root / "dist/src/entrypoint.js").write_text("// another promptfoo build\n")
            self.assertNotEqual(BUILD.tree_digest(root)[0], digest)
            with self.assertRaises(SystemExit):
                BUILD.promptfoo_package(str(Path(directory) / "bin/not-promptfoo.js"))

    @unittest.skipUnless(NODE and PROMPTFOO_PACKAGE, "needs Node and the promptfoo installation on PATH")
    def test_plan_records_the_installed_promptfoo_build(self):
        self.assertEqual(BUILD.promptfoo_record(), PLAN["promptfoo_build"])

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
        is_json = BUILD.config("ab", schema)["defaultTest"]["assert"][1]
        self.assertEqual(sha256(BUILD.canonical(is_json["value"])), PLAN["request"]["schema_sha256"])
        self.assertTrue({"temperature", "top_p", "seed", "max_tokens", "top_k", "cache_prompt",
                         "chat_template_kwargs"} <= set(PLAN["request"]["not_sent"]))
        self.assertEqual(PLAN["repeats"], 3)
        self.assertEqual(PLAN["status"], "draft-not-frozen-not-run")

    def test_run_environment_bounds_the_whole_call(self):
        environment = PLAN["run"]["environment"]
        self.assertEqual(environment, {"PROMPTFOO_EVAL_TIMEOUT_MS": "1320000", "REQUEST_TIMEOUT_MS": "660000",
                                       "PROMPTFOO_DISABLE_TELEMETRY": "1"})
        # The gateway's stream cap and upstream fetch timeout, each plus the gateway's 60,000 ms margin
        # (OmniRoute@dd6e9607e:src/shared/utils/runtimeTimeouts.ts:9, 20-21).
        self.assertEqual(int(environment["PROMPTFOO_EVAL_TIMEOUT_MS"]), 1_260_000 + 60_000)
        self.assertEqual(int(environment["REQUEST_TIMEOUT_MS"]), 600_000 + 60_000)
        self.assertEqual(set(PLAN["run"]["environment_reasons"]), set(environment))
        self.assertTrue({"PROMPTFOO_STRIP_PROMPT_TEXT", "PROMPTFOO_STRIP_RESPONSE_OUTPUT", "PROMPTFOO_STRIP_TEST_VARS",
                         "PROMPTFOO_STRIP_GRADING_RESULT", "PROMPTFOO_STRIP_METADATA",
                         "PROMPTFOO_SHORT_CIRCUIT_TEST_FAILURES"} <= set(PLAN["run"]["must_not_set"]))
        frozen = ANALYZE.frozen_spec()
        self.assertEqual((frozen["call_deadline_ms"], frozen["request_timeout_ms"]), (1_320_000, 660_000))

    def test_analysis_environment_is_pinned(self):
        environment = PLAN["analysis_environment"]
        self.assertEqual(environment["versions"], {"python": "3.14", "numpy": "2.5.3", "scipy": "1.18.1",
                                                   "statsmodels": "0.15.0"})
        self.assertIn("--python 3.14 ", environment["command"])
        for name in ("numpy", "scipy", "statsmodels"):
            self.assertIn(f"--with {name}=={environment['versions'][name]}", environment["command"])
        self.assertEqual(ANALYZE.frozen_spec()["environment"], environment["versions"])

    def test_gateway_fingerprint_is_an_owner_precondition(self):
        fingerprint = PLAN["gateway_fingerprint"]
        self.assertTrue(fingerprint["status"].startswith("execution precondition performed by the gateway owner"))
        self.assertEqual(len(set(fingerprint["fields"])), len(fingerprint["fields"]))
        self.assertEqual(sorted(fingerprint["fields"]), sorted(fingerprint["field_sources"]))
        self.assertEqual(ANALYZE.frozen_spec()["gateway_fields"], sorted(fingerprint["fields"]))

    def test_time_to_headers_is_labelled_and_no_path_is_inferred_from_it(self):
        self.assertIn("time_to_response_headers", PLAN["metrics"])
        self.assertNotIn("latency", PLAN["metrics"])
        self.assertNotIn("latency_ms", PLAN["wire_recheck"])
        self.assertIn("time_to_response_headers_ms", PLAN["wire_recheck"])
        self.assertNotIn("most likely took the slow path", json.dumps(PLAN))
        self.assertIn("terminal_row_rule", PLAN["correlation"])
        self.assertNotIn("final_row_rule", PLAN["correlation"])

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
    INSERT = ("INSERT INTO call_logs (correlation_id, timestamp, status, model, reasoning_effort_requested, "
              "reasoning_effort_upstream, account_id, connection_id, request_body, artifact_path, tokens_in) "
              "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "storage.sqlite"
        connection = sqlite3.connect(self.db)
        connection.execute("CREATE TABLE call_logs (id INTEGER PRIMARY KEY, correlation_id TEXT, timestamp TEXT, "
                           "status INTEGER, model TEXT, reasoning_effort_requested TEXT, "
                           "reasoning_effort_upstream TEXT, account_id TEXT, connection_id TEXT, request_body TEXT, "
                           "artifact_path TEXT, tokens_in INTEGER)")
        # Rows in insertion order, which is not the gateway's attempt order: cid-b-3's rows share a timestamp and
        # cid-b-4's 200 row was inserted before its earlier-stamped 503 row.
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
            connection.execute(self.INSERT, row + self.SENSITIVE + (1000,))
        connection.commit()
        connection.close()

    def tearDown(self):
        self.tmp.cleanup()

    def insert(self, identifier, timestamp, status):
        connection = sqlite3.connect(self.db)
        connection.execute(self.INSERT, (identifier, timestamp, status, "gpt-6-astra", None, None) + self.SENSITIVE +
                           (1000,))
        connection.commit()
        connection.close()

    def test_selects_only_the_allowlisted_columns(self):
        self.assertEqual(CALL_LOGS.COLUMNS, ("correlation_id", "timestamp", "status", "model",
                                             "reasoning_effort_requested", "reasoning_effort_upstream"))
        self.assertTrue(CALL_LOGS.QUERY.startswith(f"SELECT {', '.join(CALL_LOGS.COLUMNS)} FROM call_logs WHERE "
                                                   "correlation_id IN ("))
        # The rows are ordered by the selected columns only, to make reads comparable; no insertion order.
        self.assertTrue(CALL_LOGS.QUERY.endswith(f") ORDER BY {', '.join(CALL_LOGS.COLUMNS)}"))
        self.assertNotIn("rowid", CALL_LOGS.QUERY)
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        rows = CALL_LOGS.lookup(self.db, ["cid-a-1", "cid-b-2", "cid-missing"])
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)
        self.assertEqual([set(row) for row in rows], [set(CALL_LOGS.COLUMNS)] * 3)
        text = json.dumps(rows)
        for value in self.SENSITIVE:
            self.assertNotIn(value, text)

    def test_summary_and_unmatched_without_attempt_order(self):
        arms = {"A": ["cid-a-1", "cid-a-missing"], "B": ["cid-b-1", "cid-b-2", "cid-b-3", "cid-b-4"]}
        rows = CALL_LOGS.lookup(self.db, [identifier for ids in arms.values() for identifier in ids])
        summary = CALL_LOGS.summarize(arms, rows, include_rows=True)
        self.assertEqual((summary["A"]["rows"], summary["A"]["ids_matched"], summary["A"]["unmatched"]),
                         (1, 1, ["cid-a-missing"]))
        self.assertEqual(summary["A"]["rows_per_id"], {0: 1, 1: 1})
        self.assertEqual((summary["B"]["rows"], summary["B"]["ids_matched"], summary["B"]["unmatched"]), (7, 4, []))
        self.assertEqual(summary["B"]["rows_per_id"], {1: 1, 2: 3})
        self.assertEqual(summary["B"]["ids_with_several_rows"], ["cid-b-2", "cid-b-3", "cid-b-4"])
        groups = {(group["status"], group["upstream"]): group["count"]
                  for group in summary["B"]["all_rows_by_status_model_requested_upstream"]}
        self.assertEqual(groups, {(200, "max"): 4, (429, None): 1, (503, None): 2})
        self.assertNotIn("final_rows_by_status_model_requested_upstream", summary["B"])
        # No attempt number and no final flag: neither the timestamp nor the insertion order is the attempt order.
        self.assertEqual([set(row) for row in summary["B"]["matched_rows"]], [set(CALL_LOGS.COLUMNS)] * 7)
        self.assertEqual([(row["correlation_id"], row["status"]) for row in summary["B"]["matched_rows"]],
                         [("cid-b-1", 200), ("cid-b-2", 429), ("cid-b-2", 200), ("cid-b-3", 200), ("cid-b-3", 503),
                          ("cid-b-4", 503), ("cid-b-4", 200)])
        self.assertEqual(CALL_LOGS.summarize({"B": ["cid-b-1", "cid-b-1"]}, rows)["B"]["duplicate_ids"], 1)

    def test_settled_lookup_rereads_until_two_reads_agree(self):
        clock = [0.0]

        def sleep(seconds):
            clock[0] += seconds
            if clock[0] == 30:  # a pending save lands during the first wait
                self.insert("cid-a-1", "2026-09-27T10:00:09.000Z", 503)

        rows, snapshot = CALL_LOGS.settled_lookup(self.db, ["cid-a-1"], interval=30, max_wait=600, sleep=sleep,
                                                  clock=lambda: clock[0])
        self.assertEqual(snapshot, {"reads": 3, "settled": True, "interval_seconds": 30, "max_wait_seconds": 600})
        self.assertEqual(sorted(row["status"] for row in rows), [200, 503])

    def test_settled_lookup_reports_a_snapshot_that_never_settles(self):
        clock = [0.0]

        def sleep(seconds):
            clock[0] += seconds
            self.insert("cid-a-1", f"2026-09-27T11:00:{int(clock[0]) % 60:02d}.000Z", 503)

        rows, snapshot = CALL_LOGS.settled_lookup(self.db, ["cid-a-1"], interval=30, max_wait=90, sleep=sleep,
                                                  clock=lambda: clock[0])
        self.assertEqual(snapshot, {"reads": 4, "settled": False, "interval_seconds": 30, "max_wait_seconds": 90})
        self.assertEqual(len(rows), 4)

    def test_batches_and_command_line(self):
        ids = [f"cid-missing-{index}" for index in range(1200)] + ["cid-b-1"]
        self.assertEqual(len(CALL_LOGS.lookup(self.db, ids)), 1)
        ids_file = Path(self.tmp.name) / "ids.json"
        ids_file.write_text(json.dumps({"A": ["cid-a-1"], "B": ["cid-b-1"]}))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = CALL_LOGS.main([str(self.db), str(ids_file), "--settle-seconds", "0", "--max-wait-seconds", "5"])
        report = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual((report["snapshot"]["settled"], report["snapshot"]["reads"]), (True, 2))
        self.assertEqual((report["arms"]["A"]["rows"], report["arms"]["B"]["rows"]), (1, 1))
        self.assertNotIn("matched_rows", report["arms"]["A"])
        # No second read fits in the bound, so the snapshot is not settled and the exit code says so.
        with contextlib.redirect_stdout(io.StringIO()):
            code = CALL_LOGS.main([str(self.db), str(ids_file), "--settle-seconds", "30", "--max-wait-seconds", "0"])
        self.assertEqual(code, CALL_LOGS.EXIT_UNSETTLED)
        ids_file.write_text(json.dumps(["cid-a-1"]))
        with self.assertRaises(SystemExit):
            CALL_LOGS.main([str(self.db), str(ids_file)])


# --- analysis fixtures --------------------------------------------------------------------------------------------

FILINGS = [(f"0000000000-26-{index:06d}", labels) for index, labels in
           enumerate([["7.01"], ["2.02", "9.01"], ["5.02"], ["8.01", "9.01"], ["1.01"], ["7.01", "8.01"]])]
RUN_FILINGS = {"ab": FILINGS[:3], "ba": FILINGS[3:]}
PROMPT_SHA256 = sha256("p")


def tests_raw(filings):
    """A private tests file as build_r02.tests_bytes writes it, for synthetic filings."""
    lines = [json.dumps({"description": accession, "vars": {"accession": accession, "document": "Synthetic filing.",
                                                            "labels_json": json.dumps(labels),
                                                            "prompt_sha256": PROMPT_SHA256}}, sort_keys=True)
             for accession, labels in filings]
    return ("\n".join(lines) + "\n").encode()


TESTS_RAW = {run: tests_raw(filings) for run, filings in RUN_FILINGS.items()}


def synthetic_frozen():
    """plan.json's frozen spec with the synthetic rosters and tests files."""
    frozen = ANALYZE.frozen_spec()
    frozen["rosters"] = {run: [accession for accession, _ in filings] for run, filings in RUN_FILINGS.items()}
    frozen["tests_files"] = {run: {"name": f"tests-{run}.jsonl", "sha256": hashlib.sha256(raw).hexdigest(),
                                   "tests": len(RUN_FILINGS[run])} for run, raw in TESTS_RAW.items()}
    return frozen


FROZEN = synthetic_frozen()
READBACKS = {point: {field: f"synthetic {field}" for field in PLAN["gateway_fingerprint"]["fields"]}
             for point in ANALYZE.READBACK_POINTS}
SETTLED = {"reads": 2, "settled": True, "interval_seconds": 30, "max_wait_seconds": 600}
DEADLINE_ERROR = "Evaluation timed out after 1320000ms: Error: Evaluation timed out after 1320000ms"
HEADERS_ERROR = "Error: Request failed after 0 retries: Error: Request timed out after 660000 ms"
RATE_LIMIT_ERROR = "HttpRateLimitError: Rate limit exceeded: HTTP 429 Too Many Requests"


def usage(completion, reasoning=0, prompt=1500, cached=0):
    value = {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion}
    if reasoning:
        value["completion_tokens_details"] = {"reasoning_tokens": reasoning}
    if cached:
        value["prompt_tokens_details"] = {"cached_tokens": cached}
    return value


DEFAULT_OUTPUTS = {"A": {"output": '{"items": ["7.01"]}', "usage": usage(20)},
                   "B": {"output": '{"items": ["7.01"]}', "usage": usage(60, reasoning=40)}}


def result_row(arm, test_idx, accession, labels, output=None, error=None, usage=None, cid=None, latency=1000,
               prompt_idx=0, rate_limit_headers=None, schema_valid=None, persisted=True):
    """One promptfoo 0.123.1 result row. Persisted, as `-o results.json` holds it: the vars went through promptfoo's
    sanitizer, which re-serializes labels_json compactly and redacts the 64-hex prompt_sha256
    (dist/src/logger-ChlKG5Wv.js:1049-1057, 718-730), and the x-correlation-id response header is redacted
    (dist/src/evalResult-yO_CeNru.js:626-681); NativePersistenceTests checks this against promptfoo itself. Not
    persisted, the evaluator's own row before that. A graded row carries both assertions' results in
    gradingResult.componentResults; the is-json result defaults to li26's status being valid."""
    in_memory = {"accession": accession, "document": "Synthetic filing.", "labels_json": json.dumps(labels),
                 "prompt_sha256": PROMPT_SHA256}
    variables = {**in_memory, "labels_json": json.dumps(labels, separators=(",", ":")),
                 "prompt_sha256": "[REDACTED]"} if persisted else in_memory
    row = {"provider": {"id": "http://127.0.0.1:20128/v1/chat/completions", "label": f"r02-{arm}"},
           "vars": variables, "testIdx": test_idx, "promptIdx": prompt_idx, "latencyMs": latency}
    metadata = {"http": {"status": 200, "headers": {"x-correlation-id": "[REDACTED]" if persisted else cid}},
                "r02": {"correlation_id": cid, "usage": usage, "rate_limit_headers": rate_limit_headers or {},
                        "dropped_upstream_headers": None}}
    if error is not None:
        row.update({"success": False, "failureReason": 2, "error": error, "score": 0, "namedScores": {},
                    "response": {"error": error, "metadata": metadata} if cid else None})
        return json.loads(json.dumps(row))
    grading = ASSERTION.get_assert(output, {"vars": in_memory, "prompt": "p"})
    valid = LI26_EVAL_ARM.parse_items(output)[1] == "valid" if schema_valid is None else schema_valid
    components = [{**grading, "assertion": {"type": "python", "value": "file://assert_r02.py:get_assert"}},
                  {"pass": valid, "score": 1 if valid else 0, "reason": "Assertion passed" if valid else "schema",
                   "assertion": {"type": "is-json", "value": SCHEMA}}]
    passed = grading["pass"] and valid
    row.update({"success": passed, "failureReason": 0 if passed else 1, "score": (grading["score"] + valid) / 2,
                "namedScores": grading["namedScores"], "response": {"output": output, "metadata": metadata},
                "gradingResult": {"pass": passed, "score": (grading["score"] + valid) / 2,
                                  "namedScores": grading["namedScores"], "componentResults": components}})
    if not passed:
        row["error"] = grading["reason"]
    return json.loads(json.dumps(row))


def rendered_id(arm, eval_id, test_idx, prompt_idx, repeat):
    """The config's X-Correlation-Id with promptfoo's runtime vars filled in: __evalStepId is
    test-<testIdx>-prompt-<promptIdx>-repeat-<repeatIndex> (dist/src/evaluator-DlYW7Rgb.js:7599-7605)."""
    return f"r02-{arm.lower()}-{eval_id}-test-{test_idx}-prompt-{prompt_idx}-repeat-{repeat}"


def results_file(eval_id, filings, orders, repeats=3, outputs=None, persisted=True):
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
                                       latency=spec.get("latency", 1000), persisted=persisted,
                                       **{key: value for key, value in spec.items() if key not in ("latency", "cid")}))
            test_idx += 1
    return {"evalId": eval_id, "results": {"version": 3, "results": rows},
            "metadata": {"promptfooVersion": PLAN["promptfoo_build"]["version"],
                         "nodeVersion": PLAN["promptfoo_build"]["node"]}}


def run_inputs(outputs_ab=None, outputs_ba=None):
    """Results and private tests files of both runs, matching FROZEN."""
    results = {"ab": results_file("eval-ab", RUN_FILINGS["ab"], ("A", "B"),
                                  outputs=DEFAULT_OUTPUTS if outputs_ab is None else outputs_ab),
               "ba": results_file("eval-ba", RUN_FILINGS["ba"], ("B", "A"),
                                  outputs=DEFAULT_OUTPUTS if outputs_ba is None else outputs_ba)}
    return results, dict(TESTS_RAW)


def log_row(identifier, second, status, model="gpt-6-astra", upstream=None):
    """A call_logs row as call_logs_by_correlation.lookup returns it (the six allowlisted columns)."""
    return {"correlation_id": identifier, "timestamp": f"2026-09-27T10:00:{second:02d}.000Z", "status": status,
            "model": model, "reasoning_effort_requested": None, "reasoning_effort_upstream": upstream}


def sent_ids(results):
    ids = {"A": [], "B": []}
    for data in results.values():
        for row in ANALYZE.result_rows(data):
            arm = ANALYZE.ARM_LABELS[row["provider"]["label"]]
            ids[arm].append(rendered_id(arm, data["evalId"], row["testIdx"], row["promptIdx"], row["testIdx"] % 3))
    return ids


def graded_rows(results):
    """One success row per call promptfoo graded: A as gpt-6-astra with no effort observation, B as
    gpt-6-astra-max at max, as the wire re-check recorded them."""
    rows = []
    for data in results.values():
        for row in ANALYZE.result_rows(data):
            if row.get("failureReason") == 2:
                continue
            arm = ANALYZE.ARM_LABELS[row["provider"]["label"]]
            identifier = rendered_id(arm, data["evalId"], row["testIdx"], row["promptIdx"], row["testIdx"] % 3)
            rows.append(log_row(identifier, 1, 200, *(("gpt-6-astra-max", "max") if arm == "B" else ("gpt-6-astra",
                                                                                                     None))))
    return rows


def call_logs(results, rows=None, snapshot=SETTLED, include_rows=True):
    """`call_logs_by_correlation.py --rows` output for the calls of `results`, as read back from its file."""
    rows = graded_rows(results) if rows is None else rows
    return json.loads(json.dumps({"snapshot": snapshot,
                                  "arms": CALL_LOGS.summarize(sent_ids(results), rows, include_rows)}))


def perfect(labels):
    return json.dumps({"items": labels})


class AnalysisTests(unittest.TestCase):
    """analyze_r02.py integrity checks, extraction, pairing and decision rule; standard library only."""

    def integrity(self, results, tests=None, logs=None, readbacks=None, frozen=None):
        return ANALYZE.integrity(results, TESTS_RAW if tests is None else tests,
                                 call_logs(results) if logs is None else logs,
                                 READBACKS if readbacks is None else readbacks, FROZEN if frozen is None else frozen)

    # P1-2: the frozen sample and schedule.

    def test_the_complete_frozen_schedule_passes(self):
        results, tests = run_inputs()
        report, problems, runs = self.integrity(results, tests)
        self.assertEqual(problems, [])
        self.assertEqual({run: len(calls) for run, calls in runs.items()}, {"ab": 18, "ba": 18})
        self.assertEqual(report["correlation"]["A"], {"calls": 18, "sent_ids": 18, "echoed": 18, "echo_mismatch": 0})

    def test_a_dropped_filing_or_a_smaller_run_is_invalid(self):
        results, tests = run_inputs()
        dropped = RUN_FILINGS["ab"][1][0]
        results["ab"]["results"]["results"] = [row for row in ANALYZE.result_rows(results["ab"])
                                               if row["vars"]["accession"] != dropped]
        self.assertEqual(self.integrity(results, tests)[1], ["ab: 6 of 18 scheduled calls are missing"])
        results, tests = run_inputs()
        results["ba"] = results_file("eval-ba", RUN_FILINGS["ba"][:2], ("B", "A"), outputs=DEFAULT_OUTPUTS)
        self.assertEqual(self.integrity(results, tests)[1], ["ba: 6 of 18 scheduled calls are missing"])

    def test_missing_first_repeat_rows_are_invalid_and_do_not_shift_the_repeat(self):
        results, tests = run_inputs()
        rows = ANALYZE.result_rows(results["ab"])
        # testIdx 3 is the second filing's first repeat; both of its rows go missing.
        results["ab"]["results"]["results"] = [row for row in rows if row["testIdx"] != 3]
        self.assertEqual(self.integrity(results, tests)[1], ["ab: 2 of 18 scheduled calls are missing"])
        # The repeat comes from the frozen schedule (testIdx % repeats), not from the smallest present testIdx.
        (row,) = [row for row in rows if (row["testIdx"], row["promptIdx"]) == (4, 0)]
        call = ANALYZE.call_record(row, "ab", "eval-ab", FROZEN)
        self.assertEqual((call["repeat"], call["sent_id"]), (1, rendered_id("A", "eval-ab", 4, 0, 1)))

    def test_duplicate_extra_and_reordered_rows_are_invalid(self):
        results, tests = run_inputs()
        rows = ANALYZE.result_rows(results["ab"])
        rows.append(copy.deepcopy(rows[0]))
        self.assertEqual(self.integrity(results, tests)[1], ["ab: 1 scheduled calls appear more than once"])
        results, tests = run_inputs()
        extra = copy.deepcopy(ANALYZE.result_rows(results["ab"])[0])
        extra["testIdx"] = 9
        ANALYZE.result_rows(results["ab"]).append(extra)
        self.assertEqual(self.integrity(results, tests)[1], ["ab: a row outside the frozen step schedule"])
        results, tests = run_inputs()
        for row in ANALYZE.result_rows(results["ab"]):
            row["provider"]["label"] = "r02-B" if row["promptIdx"] == 0 else "r02-A"
        problems = self.integrity(results, tests)[1]
        self.assertIn("ab: testIdx 0 promptIdx 0 is not arm A", problems)
        self.assertEqual(len(problems), 18)

    def test_the_frozen_roster_labels_and_tests_files_are_enforced(self):
        results, tests = run_inputs()
        first, second = (row for row in ANALYZE.result_rows(results["ab"]) if row["testIdx"] == 0)
        first["vars"]["accession"] = RUN_FILINGS["ab"][1][0]
        second["vars"]["labels_json"] = json.dumps(["1.01"])
        self.assertEqual(self.integrity(results, tests)[1],
                         ["ab: testIdx 0 is not frozen filing 1 of the roster",
                          "ab: testIdx 0 labels differ from the frozen tests file"])
        results, _ = run_inputs()
        tests = {"ab": TESTS_RAW["ab"] + b"\n", "ba": None}
        self.assertEqual(self.integrity(results, tests)[1],
                         ["ab: tests-ab.jsonl differs from its frozen sha256",
                          "ba: the private tests file tests-ba.jsonl is missing"])
        reordered = b"".join(reversed(TESTS_RAW["ab"].splitlines(keepends=True)))
        frozen = copy.deepcopy(FROZEN)
        frozen["tests_files"]["ab"]["sha256"] = hashlib.sha256(reordered).hexdigest()
        self.assertEqual(self.integrity(results, {**TESTS_RAW, "ab": reordered}, frozen=frozen)[1],
                         ["ab: tests-ab.jsonl does not hold the frozen roster in order"])

    def test_the_promptfoo_and_node_versions_are_enforced(self):
        results, tests = run_inputs()
        results["ab"]["metadata"]["promptfooVersion"] = "0.122.0"
        del results["ba"]["metadata"]
        self.assertEqual(self.integrity(results, tests)[1],
                         ["ab: results were not written by promptfoo 0.123.1",
                          "ba: results were not written by promptfoo 0.123.1",
                          "ba: results were not written under Node v24.21.0"])

    def test_a_redacted_field_the_analysis_reads_is_an_integrity_problem(self):
        # promptfoo's results sanitizer replaces values of secret-named keys with "[REDACTED]"
        # (dist/src/logger-ChlKG5Wv.js:494, 563-642); none of the fields read here has such a name.
        results, tests = run_inputs()
        ANALYZE.result_rows(results["ab"])[0]["vars"]["labels_json"] = "[REDACTED]"
        self.assertIn("ab: promptfoo redacted a test var this analysis reads (accession or labels_json)",
                      self.integrity(results, tests)[1])
        results, _ = run_inputs()
        row = ANALYZE.result_rows(results["ab"])[0]
        row["response"]["metadata"]["r02"]["usage"]["completion_tokens"] = "[REDACTED]"
        self.assertEqual(ANALYZE.call_record(row, "ab", "eval-ab", FROZEN)["problems"],
                         ["promptfoo redacted row.r02.usage.completion_tokens, which this analysis reads"])
        # prompt_sha256 is redacted in real results and is never read from them.
        self.assertEqual(self.integrity(*run_inputs())[1], [])

    def test_ids_are_rebuilt_only_from_inputs_that_match_the_frozen_schedule(self):
        results, tests = run_inputs()
        ids = ANALYZE.correlation_ids(results, tests, FROZEN)
        self.assertEqual({arm: len(values) for arm, values in ids.items()}, {"A": 18, "B": 18})
        self.assertEqual(ids["A"][:2], [rendered_id("A", "eval-ab", 0, 0, 0), rendered_id("A", "eval-ab", 1, 0, 1)])
        # In the BA run B is the first provider, so A's prompt column index is 1.
        self.assertEqual(ids["A"][9], rendered_id("A", "eval-ba", 0, 1, 0))
        self.assertEqual(ids, sent_ids(results))
        del ANALYZE.result_rows(results["ab"])[0]
        with self.assertRaises(SystemExit):
            ANALYZE.correlation_ids(results, tests, FROZEN)

    # P1-1: no verdict from an invalid run.

    def test_an_integrity_problem_voids_the_verdict(self):
        results, tests = run_inputs()
        ANALYZE.result_rows(results["ab"])[0]["namedScores"]["tp"] = 5
        report = ANALYZE.analyze(results, tests, call_logs(results), READBACKS, FROZEN)
        self.assertEqual((report["status"], report["decision"]["result"]), ("invalid", "invalid"))
        self.assertEqual(len(report["problems"]), 1)
        self.assertIn("assertion scores differ from li26 rescoring", report["problems"][0])
        self.assertFalse({"tests", "micro_f1", "arms", "effort", "cost_per_filing"} & set(report))

    def test_the_command_line_writes_the_invalid_report_and_exits_2(self):
        results, _ = run_inputs()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for run, data in results.items():
                (root / f"results-{run}.json").write_text(json.dumps(data))
            (root / "state").mkdir()
            (root / "call-logs.json").write_text(json.dumps(call_logs(results)))
            readbacks = []
            for point in ANALYZE.READBACK_POINTS:
                (root / f"{point}.json").write_text(json.dumps(READBACKS[point]))
                readbacks.append(str(root / f"{point}.json"))
            inputs = ["--results-ab", str(root / "results-ab.json"), "--results-ba", str(root / "results-ba.json"),
                      "--state-dir", str(root / "state")]
            # plan.json's frozen rosters and tests files are not these synthetic ones, so the run is invalid.
            with contextlib.redirect_stdout(io.StringIO()):
                code = ANALYZE.main(["analyze", *inputs, "--call-logs", str(root / "call-logs.json"),
                                     "--gateway-readbacks", *readbacks, "--out", str(root / "decision.json")])
            report = json.loads((root / "decision.json").read_text())
            with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()):
                ANALYZE.main(["ids", *inputs])
        self.assertEqual(code, ANALYZE.EXIT_INVALID)
        self.assertEqual((report["status"], report["decision"]["result"]), ("invalid", "invalid"))
        self.assertIn("ab: the private tests file tests-ab.jsonl is missing", report["problems"])

    # P1-3: the cost leg.

    def test_the_cost_leg_is_paired_per_filing_and_needs_every_call(self):
        # The reviewer's example: 59 filings cost 10 completion tokens in both arms, one costs A 1,000 and B 900.
        def pair(filing, repeat):
            a, b = (1000, 900) if filing == 0 else (10, 10)
            return {"accession": f"f{filing:02d}", "repeat": repeat, "A": {"usage": {"completion": a}},
                    "B": {"usage": {"completion": b}}}

        pairs = [pair(filing, repeat) for filing in range(60) for repeat in range(3)]
        complete = ANALYZE.cost_leg(pairs)
        self.assertTrue(complete["supported"])
        self.assertAlmostEqual(complete["A"], 26.5)
        self.assertAlmostEqual(complete["B"], 1490 / 60)
        self.assertEqual(ANALYZE.decide(-0.1, 0.0, complete), "inconclusive")
        # One of A's 1,000-token calls returns no usage. Averaging the calls that did would compare 21.06 with
        # 24.83 and let keep_medium through; the per-filing leg is unsupported instead.
        pairs[0]["A"]["usage"]["completion"] = None
        available = [pair["A"]["usage"]["completion"] for pair in pairs if pair["A"]["usage"]["completion"]]
        self.assertEqual((round(statistics.fmean(available), 2),
                          round(statistics.fmean(pair["B"]["usage"]["completion"] for pair in pairs), 2)),
                         (21.06, 24.83))
        partial = ANALYZE.cost_leg(pairs)
        self.assertEqual((partial["supported"], partial["A"], partial["B"], partial["calls_without_usage"]),
                         (False, None, None, {"A": 1, "B": 0}))
        self.assertEqual(ANALYZE.decide(-0.1, 0.0, partial), "inconclusive")
        # Quality superiority does not depend on cost.
        self.assertEqual(ANALYZE.decide(0.01, -0.5, partial), "adopt_max")

    def test_decision_rule(self):
        cheaper = {"supported": True, "A": 10.0, "B": 20.0}
        dearer = {"supported": True, "A": 30.0, "B": 20.0}
        unsupported = {"supported": False, "A": None, "B": None}
        self.assertEqual(ANALYZE.decide(0.001, -0.5, unsupported), "adopt_max")
        self.assertEqual(ANALYZE.decide(0.0, -0.02, cheaper), "keep_medium")
        self.assertEqual(ANALYZE.decide(0.0, -0.02, unsupported), "inconclusive")
        self.assertEqual(ANALYZE.decide(0.0, -0.021, cheaper), "inconclusive")
        self.assertEqual(ANALYZE.decide(-0.1, 0.0, dearer), "inconclusive")

    # P2-4: analysis environment and gateway read-backs.

    def test_environment_problems(self):
        required = PLAN["analysis_environment"]["versions"]
        good = {"python": "3.14.7", "numpy": "2.5.3", "scipy": "1.18.1", "statsmodels": "0.15.0"}
        self.assertEqual(ANALYZE.environment_problems(required, good), [])
        for key, value in (("python", "3.13.15"), ("python", "3.140.1"), ("numpy", None), ("scipy", "1.18.0"),
                           ("statsmodels", "0.15.1")):
            self.assertEqual(len(ANALYZE.environment_problems(required, {**good, key: value})), 1, (key, value))
        results, tests = run_inputs()
        _, problems, _ = ANALYZE.integrity(results, tests, call_logs(results), READBACKS, FROZEN,
                                           {**good, "numpy": "2.4.0"})
        self.assertEqual(problems, ["numpy 2.4.0 is not the frozen 2.5.3"])

    def test_gateway_read_backs(self):
        fields = FROZEN["gateway_fields"]
        fingerprint, problems = ANALYZE.gateway_fingerprint(READBACKS, fields)
        self.assertEqual((problems, fingerprint["identical"]), ([], True))
        self.assertEqual(sorted(fingerprint["sha256"]), sorted(ANALYZE.READBACK_POINTS))
        changed = copy.deepcopy(READBACKS)
        changed["ba_after"]["model_aliases"] = "another alias"
        self.assertEqual(ANALYZE.gateway_fingerprint(changed, fields)[1],
                         ["the gateway read-backs differ between the points of the run"])
        extra = copy.deepcopy(READBACKS)
        extra["ab_after"]["connection_id"] = "conn-secret-9"
        missing = copy.deepcopy(READBACKS)
        del missing["ab_before"]["compression"]
        absent = copy.deepcopy(READBACKS)
        del absent["ba_before"]
        for readbacks in (extra, missing, absent, {**READBACKS, "ab_before": ["not", "an", "object"]}):
            fingerprint, problems = ANALYZE.gateway_fingerprint(readbacks, fields)
            self.assertEqual((len(problems), fingerprint["identical"]), (1, False))
        # Neither an unexpected key nor its value reaches the report.
        self.assertNotIn("conn", json.dumps(ANALYZE.gateway_fingerprint(extra, fields)))
        results, tests = run_inputs()
        self.assertEqual(self.integrity(results, tests, readbacks={})[1],
                         [f"gateway read-back {point} is missing or not a JSON object"
                          for point in ANALYZE.READBACK_POINTS])

    # P2-5: split timeouts with the frozen values.

    def test_error_kinds(self):
        cases = {"http_status_500: {}": "http_500", "sse_error_event: {}": "sse_error_event",
                 "missing_usage": "missing_usage",
                 f"{RATE_LIMIT_ERROR}\n\n    at stack": "http_429",
                 "HttpRateLimitError: Quota exceeded: HTTP 429 Too Many Requests (code: quota)": "http_429",
                 "Error: Rate limited: 200 OK after 1 attempts": "rate_limit_header",
                 HEADERS_ERROR: "headers_timeout",
                 DEADLINE_ERROR: "call_deadline",
                 "TypeError: unexpected": "other"}
        for message, kind in cases.items():
            self.assertEqual(ANALYZE.error_kind({"failureReason": 2, "error": message}), kind, message)
        self.assertIsNone(ANALYZE.error_kind({"failureReason": 1, "error": "parse=invalid; prompt=ok"}))

    def test_timeouts_must_name_the_frozen_values(self):
        name = RUN_FILINGS["ab"][0][0]
        results, _ = run_inputs({**DEFAULT_OUTPUTS,
                                 (name, 0, "A"): {"error": DEADLINE_ERROR, "cid": None, "latency": 1320000},
                                 (name, 1, "A"): {"error": DEADLINE_ERROR.replace("1320000", "300000"), "cid": None},
                                 (name, 2, "A"): {"error": HEADERS_ERROR.replace("660000", "300000"), "cid": None},
                                 (name, 0, "B"): {"error": HEADERS_ERROR, "cid": None, "latency": 0}})
        calls = {(call["test_idx"], call["arm"]): call for call in ANALYZE.run_calls(results["ab"], "ab", FROZEN)}
        self.assertEqual([calls[(0, "A")]["error_kind"], calls[(0, "B")]["error_kind"]],
                         ["call_deadline", "headers_timeout"])
        self.assertEqual([calls[(0, "A")]["problems"], calls[(0, "B")]["problems"]], [[], []])
        self.assertEqual(calls[(1, "A")]["problems"],
                         ["a timeout other than the frozen PROMPTFOO_EVAL_TIMEOUT_MS=1320000"])
        self.assertEqual(calls[(2, "A")]["problems"], ["a timeout other than the frozen REQUEST_TIMEOUT_MS=660000"])

    # P2-6: settled call_logs and the client's outcome as terminal truth.

    def test_the_terminal_row_follows_the_client_outcome_not_row_order(self):
        def rows(*statuses, **columns):
            return [log_row("cid", second, status, **columns) for second, status in enumerate(statuses)]

        graded = {"error_kind": None}
        resolved = [(graded, rows(503, 200), 200), (graded, rows(200, 503), 200),
                    ({"error_kind": "http_503"}, rows(429, 503), 503),
                    ({"error_kind": "http_429"}, rows(429, 429), 429),
                    ({"error_kind": "sse_error_event"}, rows(503), 503),
                    ({"error_kind": "call_deadline"}, rows(200), 200)]
        for call, candidates, status in resolved:
            row, reason = ANALYZE.terminal_row(call, candidates)
            self.assertEqual((row["status"], reason), (status, None), (call, status))
        unknown = [(graded, rows(503)), ({"error_kind": "http_503"}, rows(429)),
                   ({"error_kind": "call_deadline"}, rows(503, 499)),
                   ({"error_kind": "sse_error_event"}, rows(429, 502)),
                   (graded, rows(200) + [log_row("cid", 5, 200, upstream="max")])]
        for call, candidates in unknown:
            row, reason = ANALYZE.terminal_row(call, candidates)
            self.assertIsNone(row)
            self.assertIsInstance(reason, str)

    def test_call_log_join_and_unmatched_calls(self):
        name = RUN_FILINGS["ab"][0][0]
        results, tests = run_inputs({**DEFAULT_OUTPUTS,
                                     (name, 1, "A"): {"error": RATE_LIMIT_ERROR, "cid": None, "latency": 0},
                                     (name, 1, "B"): {"error": DEADLINE_ERROR, "cid": None, "latency": 1320000}})
        # B's first call was graded after a 503 attempt; A's thrown 429 has its gateway row; B's deadline has none.
        rows = graded_rows(results) + [log_row(rendered_id("B", "eval-ab", 0, 1, 0), 0, 503, "gpt-6-astra-max"),
                                       log_row(rendered_id("A", "eval-ab", 1, 0, 1), 5, 429)]
        report, problems, _ = self.integrity(results, tests, call_logs(results, rows))
        self.assertEqual(problems, [])
        summary = report["call_logs"]
        self.assertEqual(summary["snapshot"], SETTLED)
        self.assertEqual(summary["A"]["terminal_status"], {"200": 17, "429": 1})
        self.assertEqual((summary["A"]["http_429_rows"], summary["A"]["http_429_terminal"]), (1, 1))
        self.assertEqual(summary["A"]["effort_not_observed_calls"], {"requested": 18, "upstream": 18})
        self.assertEqual((summary["B"]["calls_matched"], summary["B"]["calls_unmatched"]), (17, 1))
        self.assertEqual(summary["B"]["unmatched_by_client_outcome"], {"call_deadline": 1})
        self.assertEqual((summary["B"]["calls_with_several_rows"], summary["B"]["rows_per_call"]), (1, {1: 16, 2: 1}))
        self.assertEqual(summary["B"]["terminal_status"], {"200": 17})
        self.assertEqual(summary["B"]["row_status"], {"200": 17, "503": 1})
        self.assertEqual(summary["B"]["effort_observed"]["upstream"], {"max": 17})
        self.assertIn({"client": "call_deadline", "terminal_status": "no_row", "count": 1},
                      summary["B"]["client_outcome_by_terminal_status"])
        self.assertIn({"client": "http_429", "terminal_status": "429", "count": 1},
                      summary["A"]["client_outcome_by_terminal_status"])

    def test_call_log_integrity_problems(self):
        results, tests = run_inputs()
        rows = graded_rows(results)
        problems = self.integrity(results, tests, call_logs(results, rows[1:]))[1]
        self.assertEqual(len(problems), 1)
        self.assertIn("promptfoo graded this call but call_logs has no row", problems[0])
        extra = rows + [log_row(rows[0]["correlation_id"], 9, 200, upstream="max")]
        problems = self.integrity(results, tests, call_logs(results, extra))[1]
        self.assertEqual(len(problems), 1)
        self.assertIn("terminal call_logs status unknown", problems[0])
        for snapshot, text in (({**SETTLED, "settled": False}, "the call_logs snapshot did not settle"),
                               ({**SETTLED, "interval_seconds": 5}, "settled over less than 30 s"),
                               (None, "the call_logs snapshot did not settle")):
            self.assertIn(text if "30" not in text else f"the call_logs snapshot {text}",
                          self.integrity(results, tests, call_logs(results, rows, snapshot))[1])
        problems = self.integrity(results, tests, call_logs(results, rows, include_rows=False))[1]
        self.assertIn("the call_logs output has no matched rows (use call_logs_by_correlation.py --rows)", problems)

    # P2-7: time to response headers.

    def test_time_to_headers_only_where_the_transform_ran(self):
        name = RUN_FILINGS["ab"][0][0]
        results, _ = run_inputs({**DEFAULT_OUTPUTS,
                                 (name, 0, "A"): {"error": RATE_LIMIT_ERROR, "cid": None, "latency": 0},
                                 (name, 1, "A"): {"error": DEADLINE_ERROR, "cid": None, "latency": 1320000},
                                 (name, 2, "A"): {"error": "http_status_503: {}", "latency": 800},
                                 (name, 0, "B"): {**DEFAULT_OUTPUTS["B"], "latency": 4639}})
        calls = {(call["test_idx"], call["arm"]): call for call in ANALYZE.run_calls(results["ab"], "ab", FROZEN)}
        self.assertEqual([calls[(step, "A")]["time_to_headers_ms"] for step in range(3)], [None, None, 800])
        self.assertEqual((calls[(0, "B")]["time_to_headers_ms"], calls[(1, "B")]["time_to_headers_ms"]), (4639, 1000))

    # P2-8: strict-schema validity from promptfoo's is-json.

    def test_schema_validity_is_the_is_json_result(self):
        name = RUN_FILINGS["ab"][0][0]
        results, _ = run_inputs({**DEFAULT_OUTPUTS, (name, 0, "A"): {"output": '{"items": ["9.99"]}',
                                                                     "usage": usage(20), "schema_valid": False}})
        calls = ANALYZE.run_calls(results["ab"], "ab", FROZEN)
        self.assertEqual((calls[0]["status"], calls[0]["schema_valid"], calls[0]["problems"]), ("valid", False, []))
        self.assertEqual((calls[1]["status"], calls[1]["schema_valid"]), ("valid", True))

    def test_the_is_json_result_must_exist_and_check_the_sent_schema(self):
        results, _ = run_inputs()
        rows = ANALYZE.result_rows(results["ab"])
        rows[0]["gradingResult"]["componentResults"].pop()
        other = copy.deepcopy(SCHEMA)
        other["properties"]["items"]["items"]["enum"].append("9.99")
        rows[1]["gradingResult"]["componentResults"][1]["assertion"]["value"] = other
        calls = ANALYZE.run_calls(results["ab"], "ab", FROZEN)
        self.assertEqual(calls[0]["problems"], ["the is-json schema assertion result is missing"])
        self.assertEqual(calls[1]["problems"], ["the is-json assertion's schema differs from the schema sent"])

    # Extraction and pairing.

    def test_usage_fields_read_absent_details_as_zero(self):
        fields = ANALYZE.usage_fields(usage(19))
        self.assertEqual((fields["reasoning"], fields["cached"], fields["visible_output"]), (0, 0, 19))
        self.assertEqual((fields["reasoning_reported"], fields["cached_reported"]), (False, False))
        fields = ANALYZE.usage_fields(usage(58, reasoning=37, cached=1024))
        self.assertEqual((fields["reasoning"], fields["visible_output"], fields["uncached_input"]), (37, 21, 476))
        self.assertTrue(fields["reasoning_reported"] and fields["cached_reported"])
        self.assertTrue(all(ANALYZE.usage_fields(None)[key] is None for key in ANALYZE.USAGE_KEYS))

    def test_pairing_and_filing_sums(self):
        results, _ = run_inputs({"A": {"output": '{"items": ["7.01"]}', "usage": usage(20)},
                                 "B": {"output": '{"items": ["7.01", "9.01"]}', "usage": usage(60, reasoning=40)}})
        runs = {run: ANALYZE.run_calls(results[run], run, FROZEN) for run in ANALYZE.ORDERS}
        pairs = ANALYZE.pair_calls(runs)
        self.assertEqual(len(pairs), 18)
        self.assertEqual([pair["repeat"] for pair in pairs[:6]], [0, 1, 2, 0, 1, 2])
        filings, table_a, table_b = ANALYZE.filing_table(pairs)
        self.assertEqual(filings, [accession for accession, _ in FILINGS])
        self.assertEqual(table_a[:2], [[3, 0, 0], [0, 3, 6]])
        self.assertEqual(table_b[:2], [[3, 3, 0], [3, 3, 3]])
        self.assertEqual(ANALYZE.micro_f1(table_a[:2]), LI26_ANALYZE.micro_f1([(3, 3, 6)]))

    def test_errors_score_as_not_returned(self):
        name = RUN_FILINGS["ab"][1][0]
        results, _ = run_inputs({**DEFAULT_OUTPUTS,
                                 (name, 0, "A"): {"error": RATE_LIMIT_ERROR, "cid": None, "latency": 0},
                                 (name, 0, "B"): {"error": 'sse_error_event: {"message": "x"}'}})
        a_row, b_row = (row for row in ANALYZE.result_rows(results["ab"]) if row["testIdx"] == 3)
        self.assertIsNone(a_row["response"])
        calls = [ANALYZE.call_record(row, "ab", "eval-ab", FROZEN) for row in (a_row, b_row)]
        self.assertEqual([(call["tp"], call["fp"], call["fn"]) for call in calls], [(0, 0, 2), (0, 0, 2)])
        self.assertEqual([call["error_kind"] for call in calls], ["http_429", "sse_error_event"])
        self.assertEqual([call["schema_valid"] for call in calls], [False, False])
        # A call thrown before the transform has no echoed id, but its sent id is rebuilt.
        self.assertIsNone(calls[0]["correlation_id"])
        self.assertEqual(calls[0]["sent_id"], rendered_id("A", "eval-ab", 3, 0, 0))
        self.assertEqual(calls[1]["correlation_id"], calls[1]["sent_id"])
        self.assertEqual([call["problems"] for call in calls], [[], []])

    def test_an_echo_mismatch_and_a_missing_eval_id_are_refused(self):
        results, tests = run_inputs({**DEFAULT_OUTPUTS, (RUN_FILINGS["ab"][0][0], 0, "A"): {
            **DEFAULT_OUTPUTS["A"], "cid": "gateway-generated-id"}})
        calls = ANALYZE.run_calls(results["ab"], "ab", FROZEN)
        self.assertEqual(calls[0]["problems"], ["the gateway's X-Correlation-Id differs from the sent id"])
        self.assertEqual(ANALYZE.correlation_summary(calls)[0]["A"],
                         {"calls": 9, "sent_ids": 9, "echoed": 9, "echo_mismatch": 1})
        with self.assertRaises(SystemExit):
            ANALYZE.correlation_ids(results, tests, FROZEN)
        results, tests = run_inputs()
        del results["ab"]["evalId"]
        with self.assertRaises(SystemExit):
            ANALYZE.correlation_ids(results, tests, FROZEN)

    def test_filing_means_leave_out_filings_without_usage(self):
        name = RUN_FILINGS["ab"][1][0]
        results, _ = run_inputs({**DEFAULT_OUTPUTS, **{(name, repeat, "A"): {"error": HEADERS_ERROR, "cid": None}
                                                       for repeat in range(3)}})
        runs = {run: ANALYZE.run_calls(results[run], run, FROZEN) for run in ANALYZE.ORDERS}
        pairs = ANALYZE.pair_calls(runs)
        sample_a, sample_b, left_out = ANALYZE.filing_means(pairs, "reasoning")
        self.assertEqual((sample_a, sample_b, left_out), ([0.0] * 5, [40.0] * 5, 1))
        self.assertEqual(ANALYZE.cost_leg(pairs, "reasoning")["calls_without_usage"], {"A": 3, "B": 0})


@unittest.skipUnless(NODE and EVAL_RESULT_MODULE and EVAL_RESULT_MODULE.is_file(),
                     "needs Node and the pinned promptfoo build on PATH")
class NativePersistenceTests(unittest.TestCase):
    """Synthetic in-memory rows through the installed promptfoo's own EvalResult: createFromEvaluateResult, which
    sanitizes the test case and with it the vars (dist/src/evalResult-yO_CeNru.js:829-879, 609-615), then
    toEvaluateResult (:1041-1082), which `-o results.json` writes (dist/src/util-BE6VXITn.js:2087-2088, 2180-2196;
    dist/src/eval-CUIvWaK2.js:1576-1597). persist is false, so no database is written and the response keeps its
    x-correlation-id header, which the persisted path alone redacts (evalResult-yO_CeNru.js:862-871) and nothing
    here reads. Our integration check that the analysis accepts what promptfoo writes, not an upstream test."""

    SCRIPT = """
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
const [module, rowsPath, evalId] = process.argv.slice(2);
const { t: EvalResult } = await import(pathToFileURL(module).href);
const rows = [];
for (const row of JSON.parse(readFileSync(rowsPath, 'utf8'))) {
  const result = { ...row, testCase: { vars: row.vars }, prompt: { raw: 'p', label: 'p' } };
  const record = await EvalResult.createFromEvaluateResult(evalId, result, { persist: false });
  rows.push(record.toEvaluateResult());
}
process.stdout.write('\\n' + JSON.stringify(rows) + '\\n');
"""

    def persist(self, data):
        with tempfile.TemporaryDirectory() as directory:
            script, rows_path = Path(directory) / "persist.mjs", Path(directory) / "rows.json"
            script.write_text(self.SCRIPT)
            rows_path.write_text(json.dumps(ANALYZE.result_rows(data)))
            completed = subprocess.run([NODE, str(script), str(EVAL_RESULT_MODULE), str(rows_path), data["evalId"]],
                                       capture_output=True, text=True, check=True, timeout=300,
                                       env=promptfoo_environment(directory))
        rows = json.loads(completed.stdout.strip().splitlines()[-1])
        return {**data, "results": {**data["results"], "results": rows}}

    def test_the_analysis_accepts_the_rows_promptfoo_writes(self):
        name = RUN_FILINGS["ab"][1][0]
        outputs = {**DEFAULT_OUTPUTS, (name, 0, "A"): {"error": RATE_LIMIT_ERROR, "cid": None, "latency": 0},
                   (name, 0, "B"): {**DEFAULT_OUTPUTS["B"], "rate_limit_headers": {
                       "x-ratelimit-remaining-requests": "12"}}}
        memory = {"ab": results_file("eval-ab", RUN_FILINGS["ab"], ("A", "B"), outputs=outputs, persisted=False),
                  "ba": results_file("eval-ba", RUN_FILINGS["ba"], ("B", "A"), outputs=DEFAULT_OUTPUTS,
                                     persisted=False)}
        written = {run: self.persist(data) for run, data in memory.items()}
        before, after = ANALYZE.result_rows(memory["ab"]), ANALYZE.result_rows(written["ab"])
        self.assertEqual(len(after), len(before))
        for old, new in zip(before, after):
            self.assertEqual((new["testIdx"], new["promptIdx"], new["provider"]["label"]),
                             (old["testIdx"], old["promptIdx"], old["provider"]["label"]))
            self.assertEqual(new["vars"]["accession"], old["vars"]["accession"])
            self.assertEqual(new["vars"]["prompt_sha256"], "[REDACTED]")
            self.assertEqual(json.loads(new["vars"]["labels_json"]), json.loads(old["vars"]["labels_json"]))
            # Everything the analysis reads from the response and the grading is kept as the evaluator had it.
            self.assertEqual(new.get("response"), old.get("response"))
            self.assertEqual(new["namedScores"], old["namedScores"])
            self.assertEqual(new.get("gradingResult"), old.get("gradingResult"))
            self.assertEqual((new.get("error"), new["latencyMs"], new["failureReason"]),
                             (old.get("error"), old["latencyMs"], old["failureReason"]))
        # A two-label filing's labels_json comes back re-serialized, so its text differs from the tests file's.
        (tests_line,) = [json.loads(line) for line in TESTS_RAW["ab"].decode().splitlines()
                         if json.loads(line)["vars"]["accession"] == name]
        stored = {row["vars"]["labels_json"] for row in after if row["vars"]["accession"] == name}
        self.assertEqual(stored, {'["2.02","9.01"]'})
        self.assertEqual(tests_line["vars"]["labels_json"], '["2.02", "9.01"]')
        # The fixture's persisted rows hold the same vars as promptfoo's.
        fixture = ANALYZE.result_rows(results_file("eval-ab", RUN_FILINGS["ab"], ("A", "B"), outputs=outputs))
        self.assertEqual([row["vars"] for row in after], [row["vars"] for row in fixture])
        report, problems, runs = ANALYZE.integrity(written, TESTS_RAW, call_logs(written), READBACKS, FROZEN)
        self.assertEqual(problems, [])
        calls = {(call["test_idx"], call["arm"]): call for call in runs["ab"]}
        self.assertEqual((calls[(3, "A")]["error_kind"], calls[(3, "B")]["rate_limit_headers"]),
                         ("http_429", ["x-ratelimit-remaining-requests"]))
        self.assertEqual((report["correlation"]["A"]["echoed"], report["correlation"]["B"]["echoed"]), (17, 18))


@unittest.skipUnless(HAS_STATS, "numpy and scipy are not installed for this interpreter")
class StatisticsTests(unittest.TestCase):
    """analyze_r02.analyze with scipy's bootstrap and permutation test on synthetic valid runs."""

    def run_analysis(self, outputs_ab, outputs_ba):
        results, tests = run_inputs(outputs_ab, outputs_ba)
        return ANALYZE.analyze(results, tests, call_logs(results), READBACKS, FROZEN)

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
        self.assertEqual((arm_a["time_to_response_headers_ms"]["p50"], arm_b["time_to_response_headers_ms"]["p95"]),
                         (1000.0, 4000.0))
        self.assertEqual(arm_a["time_to_response_headers_ms"]["n"], 18)
        self.assertEqual(arm_a["calls_with_details"], {"reasoning_tokens": 0, "cached_tokens": 18})
        self.assertAlmostEqual(arm_a["cached_input_share"], 512 / 1500)
        self.assertEqual(arm_a["reasoning_tokens"]["zero_share"], 1.0)
        self.assertEqual(arm_b["tokens_per_call_with_usage"]["visible_output"], 20.0)
        self.assertEqual(arm_a["strict_schema_validity"], 1.0)
        self.assertEqual(arm_a["timeouts"], {"headers": 0, "call_deadline": 0})
        self.assertEqual(arm_a["rate_limit_headers"],
                         {"calls_with_any": 18, "names": {"x-ratelimit-remaining-requests": 18}})
        self.assertEqual(arm_b["rate_limit_headers"], {"calls_with_any": 0, "names": {}})
        self.assertEqual(report["cost_per_filing"]["completion"]["supported"], True)
        self.assertEqual((report["cost_per_filing"]["completion"]["A"], report["cost_per_filing"]["completion"]["B"]),
                         (20.0, 60.0))
        self.assertEqual(report["gateway_fingerprint"]["identical"], True)

    def test_identical_quality_and_cheaper_medium_keeps_medium(self):
        per_filing = {}
        for accession, labels in FILINGS:
            for repeat in range(3):
                per_filing[(accession, repeat, "A")] = {"output": perfect(labels[:1]), "usage": usage(20)}
                per_filing[(accession, repeat, "B")] = {"output": perfect(labels[:1]), "usage": usage(50, 30)}
        report = self.run_analysis(per_filing, per_filing)
        self.assertEqual(report["tests"]["b_minus_a"]["lower_one_sided_95"], 0.0)
        self.assertEqual(report["tests"]["a_minus_b"]["lower_one_sided_95"], 0.0)
        cost = report["decision"]["cost_leg"]
        self.assertEqual((cost["supported"], cost["A"], cost["B"], cost["filings"]), (True, 20.0, 50.0, 6))
        self.assertEqual(report["decision"]["result"], "keep_medium")

    def test_one_call_without_usage_makes_keep_medium_unreachable(self):
        # A graded call without usage cannot happen through the transform (transform_r02.js:178); it isolates the
        # cost leg here, since a failed call would also lower A's quality.
        per_filing = {}
        for accession, labels in FILINGS:
            for repeat in range(3):
                per_filing[(accession, repeat, "A")] = {"output": perfect(labels[:1]), "usage": usage(20)}
                per_filing[(accession, repeat, "B")] = {"output": perfect(labels[:1]), "usage": usage(50, 30)}
        per_filing[(FILINGS[0][0], 0, "A")] = {"output": perfect(FILINGS[0][1][:1]), "usage": None}
        report = self.run_analysis(per_filing, per_filing)
        self.assertEqual(report["tests"]["a_minus_b"]["lower_one_sided_95"], 0.0)
        cost = report["decision"]["cost_leg"]
        self.assertEqual((cost["supported"], cost["calls_without_usage"]), (False, {"A": 1, "B": 0}))
        self.assertEqual(report["decision"]["result"], "inconclusive")

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
        results, _ = run_inputs(per_filing, per_filing)
        runs = {run: ANALYZE.run_calls(results[run], run, FROZEN) for run in ANALYZE.ORDERS}
        _, table_a, table_b = ANALYZE.filing_table(ANALYZE.pair_calls(runs))
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
