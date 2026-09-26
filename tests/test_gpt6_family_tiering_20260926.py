"""Offline checks for the gpt6-family-tiering-20260926 preregistration.

Synthetic fixtures only: no provider call, no Codex sign-in and no private file. A fake `codex` in a temporary
directory stands in for the CLI: it reads its script from the fixture's fake.json beside its own directory, prints
scripted `--json` events, writes scripted replies and a session record into the CODEX_HOME it is given. It is found
through PATH, which holds only its directory, /usr/bin and /bin. The runner's native CODEX_HOME is a temporary
directory whose auth.json is a placeholder, so the real Codex and its sign-in are never reached.
"""
import contextlib
import copy
import fcntl
import hashlib
import importlib.util
import io
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
import threading
import time
import unittest
from unittest import mock

from scripts.validate_convergence import validate_record

ROOT = Path(__file__).resolve().parents[1]
REL = "blueprints/convergence-practice/gpt6-family-tiering-20260926"
HERE = ROOT / REL
LI26 = ROOT / "blueprints/convergence-practice/local-inference-latest-20260926"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN = load("gt26_run_arm_test", HERE / "run_arm.py")
ANALYZE = load("gt26_analyze_test", HERE / "analyze.py")
LI26_ANALYZE = load("gt26_li26_analyze_test", LI26 / "analyze.py")
PLAN = json.loads((HERE / "plan.json").read_text())
LIMIT_TEXT = "You’ve hit your usage limit. Visit https://chatgpt.com/codex/settings/usage or try again later."
# The frozen command, spelled out here independently of run_arm.py.
FROZEN_OPTIONS = ["-c", "agents.enabled=false", "-c", 'web_search="disabled"', "-c", "features.shell_tool=false",
                  "-c", "features.unified_exec=false", "-c", "features.view_image=false", "-c", "features.goals=false",
                  "-c", "features.sleep_tool=false", "-c", "features.hooks=false", "-c", "features.plugins=false",
                  "-c", "features.apps=false", "-c", "features.unbounded_connection_retries=false",
                  "-c", 'cli_auth_credentials_store="file"']
ONLY_TOOLS_LEFT = ["namespace:functions[exec,wait,request_user_input,request_user_input_async]"]

FAKE_CODEX = r'''#!{python}
import json, os, re, sys, time
SELF = os.path.abspath(__file__)
config = json.load(open(os.path.join(os.path.dirname(os.path.dirname(SELF)), "fake.json")))
args = sys.argv[1:]
if args == ["--version"]:
    print(config.get("version", "codex-cli 0.157.1"))
    if config.get("break_after_version"):
        os.chmod(SELF, 0o644)  # the version check passes, then every launch fails
    sys.exit(0)
prompt = args[-1]
model = args[args.index("-m") + 1]
effort = re.fullmatch(r'model_reasoning_effort="(.*)"', args[args.index("-c") + 1])[1]
reply_path = args[args.index("-o") + 1]
accessions = re.findall(r'^<<<FILING accession="([^"]+)">>>$', prompt, re.M)
key = model + "/" + effort
number = 1
while True:
    try:
        os.close(os.open(os.path.join(config["counter_dir"], "%s_%s_%s.%d" % (model, effort, accessions[0], number)),
                         os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        break
    except FileExistsError:
        number += 1
def log(kind):
    with open(config["log"], "a") as stream:
        stream.write(json.dumps({"kind": kind, "t": time.time(), "pid": os.getpid(), "key": key,
                                 "batch": accessions[0], "attempt": number}) + "\n")
log("start")
codex_home = os.environ["CODEX_HOME"]
auth = os.path.join(codex_home, "auth.json")
stdin, null = os.fstat(0), os.stat(os.devnull)
with open(os.path.join(config["record_dir"], "%s_%s_%s_%d.json" % (model, effort, accessions[0], number)), "w") as out:
    json.dump({"argv": args, "cwd": os.getcwd(), "env": sorted(os.environ), "codex_home": codex_home,
               "home": os.environ.get("HOME"), "tmpdir": os.environ.get("TMPDIR"),
               "auth_link": os.readlink(auth) if os.path.islink(auth) else None,
               "stdin_devnull": (stdin.st_ino, stdin.st_dev) == (null.st_ino, null.st_dev),
               "schema": json.load(open(args[args.index("--output-schema") + 1]))}, out)
action = "ok"
for rule in config.get("rules", []):
    if all(rule.get(field) in (None, value) for field, value in
           (("key", key), ("batch", accessions[0]), ("attempt", number))):
        action = rule["action"]
        break
if action == "ok" and config.get("outage"):
    action = "unavailable"
answers = config.get("answers", {}).get(key, config.get("answers", {}).get("default", {}))
usage = config.get("usage", {}).get(key, config.get("usage", {}).get("default"))
entries = [{"accession": a, "items": answers.get(a, [])} for a in accessions]
if action == "drop_last":
    entries = entries[:-1]
reply = json.dumps({"filings": entries})
if action == "fenced":
    reply = "```json\n" + reply + "\n```"
events = [{"type": "thread.started", "thread_id": "fixture"}, {"type": "turn.started"}]
def emit(items):
    for event in items:
        print(json.dumps(event), flush=True)
def session_record(extra):
    folder = os.path.join(codex_home, "sessions", "2026", "09", "26")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "rollout-2026-09-26T00-00-00-fixture.jsonl"), "w") as out:
        for item in [{"type": "session_meta", "payload": {"id": "fixture"}},
                     {"type": "response_item", "payload": {"type": "message", "role": "user"}}, *extra,
                     {"type": "response_item", "payload": {"type": "reasoning"}},
                     {"type": "response_item", "payload": {"type": "message", "role": "assistant"}}]:
            out.write(json.dumps(item) + "\n")
if action == "hang":
    emit(events)
    time.sleep(60)
if action in ("limit", "limit_slow"):
    emit(events + [{"type": "error", "message": config["limit_text"]},
                   {"type": "turn.failed", "error": {"message": config["limit_text"]}}])
    log("limit_emitted")
    if action == "limit_slow":
        time.sleep(config.get("limit_sleep", 1.5))
    log("end")
    sys.exit(1)
if action == "unavailable":
    emit(events + [{"type": "error", "message": "stream disconnected before completion"},
                   {"type": "turn.failed", "error": {"message": "stream disconnected before completion"}}])
    sys.stderr.write("ERROR: stream disconnected\n")
    log("end")
    sys.exit(1)
time.sleep(config.get("sleep", 0))
text = "not json" if action == "invalid_reply" else reply
with open(reply_path, "w") as out:
    out.write(text)
if action == "content_limit":
    events.append({"type": "item.completed", "item": {"id": "i1", "type": "agent_message",
                                                      "text": "a cited page says: " + config["limit_text"]}})
    sys.stderr.write("the model quoted: " + config["limit_text"] + "\n")
if action == "json_tool":
    events.append({"type": "item.completed", "item": {"id": "i0", "type": "command_execution", "command": "ls",
                                                      "exit_code": 0, "status": "completed"}})
if action == "write_home":
    open(os.path.join(os.environ["HOME"], "left-behind"), "w").write("x")
if action == "replace_link":
    os.unlink(auth)
    open(auth, "w").write("{}")
if action != "no_rollout":
    session_record([{"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec"}},
                    {"type": "response_item", "payload": {"type": "custom_tool_call_output"}}]
                   if action == "tool_call" else
                   [{"type": "response_item", "payload": {"type": "compaction"}}] if action == "odd_item" else [])
events.append({"type": "item.completed", "item": {"id": "i2", "type": "agent_message", "text": text}})
events.append({"type": "turn.completed", "usage": usage})
emit(events)
log("end")
sys.exit(1 if action == "exit_after_turn" else 0)
'''

DEFAULT_USAGE = {"input_tokens": 1000, "cached_input_tokens": 200, "cache_write_input_tokens": 0,
                 "output_tokens": 50, "reasoning_output_tokens": 30}
CODES = ["1.01", "2.02", "5.02", "7.01", "8.01", "9.01"]


def rows_for(count, text_bytes=80, start=1):
    rows = []
    for offset in range(count):
        number = start + offset
        labels = sorted({CODES[number % len(CODES)], "9.01"} if number % 3 else {CODES[number % len(CODES)]})
        body = f"Synthetic filing {number}. Item text placeholder. "
        rows.append({"accession": f"0000000001-20-{number:06d}", "labels": labels,
                     "input": (body * (1 + text_bytes // len(body)))[:text_bytes]})
    return rows


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2))


def max_concurrency(log_path):
    events = []
    for line in Path(log_path).read_text().splitlines():
        entry = json.loads(line)
        if entry["kind"] in ("start", "end"):
            events.append((entry["t"], 1 if entry["kind"] == "start" else -1))
    level = peak = 0
    for _, step in sorted(events, key=lambda item: (item[0], item[1])):
        level += step
        peak = max(peak, level)
    return peak


class Fixture:
    """A synthetic acquisition, a plan frozen for it, a lock directory, a state directory, a native Codex home with a
    placeholder sign-in file, and the fake codex."""

    def __init__(self, case, rows, plan_changes=None):
        self.root = Path(tempfile.mkdtemp(prefix="gt26-"))
        case.addCleanup(lambda: subprocess.run(["rm", "-rf", str(self.root)], check=False))
        self.rows = rows
        self.acquisition = self.root / "acq"
        self.acquisition.mkdir()
        raw = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()
        (self.acquisition / "inputs.jsonl").write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        write_json(self.acquisition / "manifest.json", {"status": "complete", "inputs": {"sha256": digest}})
        template = (HERE / "prompt.txt").read_text()
        self.batches = RUN.plan_batches(template, rows, 15, 110000)
        plan = copy.deepcopy(PLAN)
        plan["task"]["inputs_sha256"], plan["task"]["eligible_filings"] = digest, len(rows)
        plan["batching"]["batches"] = len(self.batches)
        plan["batching"]["layout_sha256"] = RUN.layout_sha256(self.batches)
        for path, value in (plan_changes or {}).items():
            target = plan
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = value
        self.plan = self.root / "plan.json"
        self.plan.write_text(json.dumps(plan, indent=2))
        self.locks = self.root / "locks"
        self.locks.mkdir()
        self.state = self.root / "state"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.codex = self.bin / "codex"
        self.codex.write_text(FAKE_CODEX.replace("{python}", sys.executable))
        self.codex.chmod(0o755)
        self.counters = self.root / "counters"
        self.counters.mkdir()
        self.records_dir = self.root / "records"
        self.records_dir.mkdir()
        self.log = self.root / "calls.log"
        self.config = self.root / "fake.json"
        self.native = self.root / "native-codex-home"
        self.native.mkdir()
        (self.native / "auth.json").write_text("{}")  # a placeholder, not a credential
        self.configure()
        # Only the fake is reachable: the real codex lives in neither directory, and the native home is a placeholder.
        self.path = f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin"
        case.assertEqual(shutil.which("codex", path=self.path), str(self.codex))
        patcher = mock.patch.dict(os.environ, {"CODEX_HOME": str(self.native), "RUST_LOG": "trace",
                                               "OPENAI_API_KEY": "fixture-placeholder", "PATH": self.path})
        patcher.start()
        case.addCleanup(patcher.stop)

    def configure(self, **config):
        base = {"counter_dir": str(self.counters), "log": str(self.log), "record_dir": str(self.records_dir),
                "limit_text": LIMIT_TEXT, "usage": {"default": DEFAULT_USAGE},
                "answers": {"default": {row["accession"]: row["labels"] for row in self.rows}}}
        write_json(self.config, {**base, **config})

    def run(self, arm="A0", **options):
        options = {"poll_seconds": 0.02, "timeout_seconds": 30, "grace_seconds": 0.5, "out": io.StringIO(),
                   **options}  # codex resolves through PATH, where only the fake is
        return RUN.run_arm(self.plan, arm, self.acquisition, self.state, self.locks, **options)

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines() if '"start"' in line]

    def log_entries(self, kind):
        return [entry for entry in map(json.loads, self.log.read_text().splitlines()) if entry["kind"] == kind]

    def records(self, arm="A0"):
        found = {}
        for path in sorted((self.state / "arms" / arm / "batches").glob("b*/attempt-*/call.json")):
            record = json.loads(path.read_text())
            found[(record["batch"], record["attempt"])] = record
        return found

    def first(self, index):
        return self.batches[index][0]["accession"]

    def seen(self, model, effort, index, attempt=1):
        return json.loads((self.records_dir / f"{model}_{effort}_{self.first(index)}_{attempt}.json").read_text())

    def attempt(self, arm, batch, number):
        return self.state / "arms" / arm / "batches" / batch / f"attempt-{number}"

    def cli(self, *args, env=None):
        environment = {"PATH": self.path, "CODEX_HOME": str(self.native), "HOME": str(self.root), **(env or {})}
        return subprocess.Popen([sys.executable, str(HERE / "run_arm.py"), *args], env=environment,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


class FrozenPlanTests(unittest.TestCase):
    def test_frozen_inputs_prompt_and_schema_match_their_hashes(self):
        plan, _ = RUN.load_plan(HERE / "plan.json")
        RUN.verify_frozen(plan)
        self.assertEqual(sorted(plan["frozen_inputs"]), sorted([
            f"{REL}/run_arm.py", f"{REL}/analyze.py", f"{REL}/prompt.txt", f"{REL}/response.schema.json",
            "blueprints/convergence-practice/local-inference-latest-20260926/eval_arm.py",
            "blueprints/convergence-practice/local-inference-latest-20260926/analyze.py", "scripts/path_safety.py"]))
        li26_plan = json.loads((LI26 / "plan.json").read_text())
        for name in ("eval_arm.py", "analyze.py"):  # the reused li26 code is li26's own frozen code
            relative = f"blueprints/convergence-practice/local-inference-latest-20260926/{name}"
            self.assertEqual(plan["frozen_inputs"][relative], li26_plan["frozen_inputs"][relative])
        done = subprocess.run([sys.executable, str(HERE / "run_arm.py"), "verify-frozen"], capture_output=True,
                              text=True)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "frozen inputs verified"))

    def test_changed_frozen_values_are_refused(self):
        changes = [(("arms", 1, "effort"), "ultra"), (("arms", 2, "model"), "gpt-5.6-sol"),
                   (("arms", 0, "role"), "candidate"), (("batching", "max_filings"), 16),
                   (("batching", "max_prompt_bytes"), 120000), (("calls", "max_concurrent"), 4),
                   (("calls", "retries_per_batch"), 2), (("decision_rule", "noninferiority_margin"), -0.05),
                   (("decision_rule", "json_valid_min"), 0.9), (("decision_rule", "bootstrap", "alpha"), 0.1),
                   (("decision_rule", "bootstrap", "resamples"), 1000), (("codex", "version"), "codex-cli 0.158.0"),
                   (("status",), "planned")]
        for path, value in changes:
            plan = copy.deepcopy(PLAN)
            target = plan
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                RUN.check_plan(plan)
        argv = PLAN["codex"]["argv_after_binary"]
        for changed in (["--search", *argv], [part for part in argv if part != "agents.enabled=false"]):
            plan = copy.deepcopy(PLAN)
            plan["codex"]["argv_after_binary"] = changed
            with self.subTest(argv=changed[:2]), self.assertRaises(ValueError):
                RUN.check_plan(plan)

    def test_planned_record_validates_and_pins_the_plan(self):
        result = validate_record(ROOT, f"{REL}/experiment.json")
        self.assertTrue(result["valid"], result["errors"])
        record = json.loads((HERE / "experiment.json").read_text())
        self.assertEqual((record["status"], record["observations"], record["decision_and_scope"]["decision"]),
                         ("planned", [], "trial"))
        pinned = {entry["path"]: entry["sha256"] for group in ("inputs", "evaluation")
                  for entry in record["frozen_inputs"][group]}
        self.assertEqual(pinned[f"{REL}/plan.json"], hashlib.sha256((HERE / "plan.json").read_bytes()).hexdigest())
        self.assertEqual(pinned[f"{REL}/run_arm.py"], PLAN["frozen_inputs"][f"{REL}/run_arm.py"])
        self.assertEqual(pinned[f"{REL}/analyze.py"], PLAN["frozen_inputs"][f"{REL}/analyze.py"])

    def test_schema_is_strict_and_lists_exactly_the_prompt_codes(self):
        schema = json.loads((HERE / "response.schema.json").read_text())

        def objects(node):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    yield node
                for value in node.values():
                    yield from objects(value)
            elif isinstance(node, list):
                for value in node:
                    yield from objects(value)

        for node in objects(schema):
            self.assertIs(node["additionalProperties"], False)
            self.assertEqual(sorted(node["required"]), sorted(node["properties"]))
        prompt = (HERE / "prompt.txt").read_text()
        li26_prompt = (LI26 / "prompt.txt").read_text()
        codes = re.findall(r"^([1-9]\.[0-9]{2}) ", prompt, re.M)
        self.assertEqual(codes, re.findall(r"^([1-9]\.[0-9]{2}) ", li26_prompt, re.M))
        self.assertEqual(len(codes), 34)
        enum = schema["properties"]["filings"]["items"]["properties"]["items"]["items"]["enum"]
        self.assertEqual(enum, codes)
        item_list = li26_prompt[li26_prompt.index("Form 8-K items"):li26_prompt.index("\n\nRules:")]
        self.assertIn(item_list, prompt)  # li26's item list, verbatim
        self.assertEqual((prompt.count("@@FILING_COUNT@@"), prompt.count("@@FILINGS@@")), (1, 1))

    def test_committed_layout_is_frozen_and_within_the_bounds(self):
        batching = PLAN["batching"]
        observed = batching["observed_on_frozen_inputs"]
        self.assertEqual(batching["batches"], 25)
        self.assertEqual(sum(int(size) * count for size, count in observed["batches_by_size"].items()), 360)
        self.assertLessEqual(max(int(size) for size in observed["batches_by_size"]), 15)
        self.assertLess(observed["prompt_bytes"]["max"], 110000)
        self.assertEqual(PLAN["task"]["inputs_sha256"],
                         "2a5c8c9bd1650bc20a3e7364defef2d725904f6eb1ef509a511a49526a32bfe0")

    def test_the_frozen_overrides_are_the_ones_the_isolation_probe_measured(self):
        isolation = PLAN["codex"]["isolation"]
        self.assertEqual(isolation["overrides"], FROZEN_OPTIONS)
        self.assertEqual(list(RUN.ISOLATION), FROZEN_OPTIONS)
        argv = PLAN["codex"]["argv_after_binary"]
        start = argv.index('model_reasoning_effort="<effort>"') + 1
        self.assertEqual(argv[start:start + len(FROZEN_OPTIONS)], FROZEN_OPTIONS)
        probe = HERE / "isolation-probe"
        for name, digest in isolation["probe_files"].items():
            self.assertEqual(hashlib.sha256((probe / name).read_bytes()).hexdigest(), digest, name)
        results = json.loads((probe / "results.json").read_text())
        self.assertEqual((results["codex"], results["isolation_overrides"]), ("codex-cli 0.157.1", FROZEN_OPTIONS))
        cases = {case["case"]: case for case in results["cases"]}
        self.assertTrue(any("collaboration" in tool for tool in cases["committed-web"]["offered_tools_first_request"]))
        # features.multi_agent=false alone leaves the sub-agent tools; agents.enabled=false removes them.
        self.assertEqual(cases["multi-agent-feature-off"]["overrides"], "multi_agent_feature_off")
        self.assertTrue(any("spawn_agent" in tool
                            for tool in cases["multi-agent-feature-off"]["offered_tools_first_request"]))
        self.assertEqual(cases["committed-web"]["search_requests"], 1)
        self.assertIn("command_execution", cases["committed-code-mode"]["json_item_types"])
        for name in ("isolated-web", "isolated-code-mode", "isolated-collaboration", "isolated-plain-astra",
                     "isolated-plain-sol", "isolated-plain-luna"):
            case = cases[name]
            self.assertEqual(case["overrides"], "isolation", name)
            self.assertEqual(case["offered_tools_first_request"], ONLY_TOOLS_LEFT, name)
            self.assertEqual((case["search_requests"], case["exit"]), (0, 0), name)
            self.assertEqual(case["json_item_types"], ["agent_message"], name)
        self.assertIn("apply_patch", cases["isolated-plain-sol"]["tool_outputs_returned_to_model"][0])
        self.assertNotIn("exec_command", cases["isolated-plain-luna"]["tool_outputs_returned_to_model"][0])
        self.assertEqual(cases["isolated-code-mode"]["rollout_response_items"]["custom_tool_call"], 2)
        self.assertEqual(cases["committed-provider-unreachable"]["exit"], "timeout")
        self.assertEqual(cases["isolated-provider-unreachable"]["exit"], 1)
        self.assertNotRegex(json.dumps(results), r"/home/|/tmp/|/Users/")  # no host path


class BatchingTests(unittest.TestCase):
    template = (HERE / "prompt.txt").read_text()

    def test_greedy_batches_keep_input_order_and_at_most_15_filings(self):
        rows = rows_for(40)
        batches = RUN.plan_batches(self.template, rows, 15, 110000)
        self.assertEqual([len(batch) for batch in batches], [15, 15, 10])
        self.assertEqual([row["accession"] for batch in batches for row in batch], [row["accession"] for row in rows])
        prompt = RUN.build_prompt(self.template, batches[2])
        self.assertIn("Below are 10 filings.", prompt)
        self.assertEqual(re.findall(r'^<<<FILING accession="([^"]+)">>>$', prompt, re.M),
                         [row["accession"] for row in batches[2]])
        self.assertTrue(prompt.endswith(f'<<<END FILING accession="{batches[2][-1]["accession"]}">>>\n'))

    def test_prompt_byte_bound_splits_batches_and_refuses_an_oversized_filing(self):
        rows = rows_for(10, text_bytes=30000)
        batches = RUN.plan_batches(self.template, rows, 15, 110000)
        self.assertEqual([len(batch) for batch in batches], [3, 3, 3, 1])
        for batch in batches:
            self.assertLess(RUN.prompt_bytes(self.template, batch), 110000)
        for batch, following in zip(batches, batches[1:]):  # each cut happened because the next filing did not fit
            self.assertGreaterEqual(RUN.prompt_bytes(self.template, batch + following[:1]), 110000)
        multibyte = rows_for(4, text_bytes=100)
        for row in multibyte:
            row["input"] = "é" * 20000  # 40,000 UTF-8 bytes: the bound is in bytes, not characters
        self.assertEqual([len(batch) for batch in RUN.plan_batches(self.template, multibyte, 15, 110000)], [2, 2])
        single = RUN.prompt_bytes(self.template, rows[:1])
        with self.assertRaisesRegex(ValueError, "alone reaches the prompt bound"):
            RUN.plan_batches(self.template, rows[:2], 15, single)  # exactly at the bound is refused
        self.assertEqual(len(RUN.plan_batches(self.template, rows[:1], 15, single + 1)), 1)

    def test_a_delimiter_inside_a_filing_is_refused(self):
        rows = rows_for(3)
        rows[1]["input"] += '\n<<<END FILING accession="x">>>'
        with self.assertRaisesRegex(ValueError, "delimiter"):
            RUN.plan_batches(self.template, rows, 15, 110000)

    def test_reply_parsing_reuses_the_li26_per_filing_rule(self):
        accessions = ["a1", "a2", "a3"]
        status, per, extra = RUN.parse_reply(json.dumps({"filings": [
            {"accession": "a1", "items": ["9.01", "2.02"]}, {"accession": "a2", "items": ["2.02", "2.02"]},
            {"accession": "zz", "items": []}]}), accessions)
        self.assertEqual((status, extra), ("valid", 1))
        self.assertEqual(per, {"a1": (["2.02", "9.01"], "valid"), "a2": (None, "invalid"), "a3": (None, "invalid")})
        status, per, _ = RUN.parse_reply("```json\n" + json.dumps({"filings": [{"accession": "a1", "items": []}]})
                                         + "\n```", accessions)
        self.assertEqual((status, per["a1"]), ("fenced_valid", ([], "fenced_valid")))
        for bad in ('{"filings": [], "filings": []}', '{"filings": [{"accession": "a1"}]}', "[]", "not json",
                    '{"filings": [{"accession": "a1", "items": [], "note": 1}]}'):
            self.assertEqual(RUN.parse_reply(bad, accessions)[0], "invalid", bad)
        duplicate = json.dumps({"filings": [{"accession": "a1", "items": []}, {"accession": "a1", "items": []}]})
        self.assertEqual(RUN.parse_reply(duplicate, accessions)[1]["a1"], (None, "invalid"))


class RunnerTests(unittest.TestCase):
    def test_codex_command_line_homes_environment_and_private_files(self):
        fixture = Fixture(self, rows_for(20))
        fixture.configure(rules=[{"batch": fixture.first(1), "action": "write_home"}])
        self.assertEqual(fixture.run("S1"), RUN.EXIT_DONE)
        seen = fixture.seen("gpt-6-sol", "medium", 1)
        arm_dir = fixture.state / "arms" / "S1"
        attempt = arm_dir / "batches/b002/attempt-1"
        argv = seen["argv"]
        self.assertEqual(argv[:-4], ["exec", "--ignore-user-config", "--skip-git-repo-check", "-s", "read-only",
                                     "-m", "gpt-6-sol", "-c", 'model_reasoning_effort="medium"', *FROZEN_OPTIONS,
                                     "--output-schema", str(arm_dir / "schema.json")])
        self.assertEqual(argv[-4:-1], ["-o", str(attempt / "reply.json"), "--json"])
        self.assertNotIn("--search", argv)
        self.assertEqual(argv[-1], RUN.build_prompt((HERE / "prompt.txt").read_text(), fixture.batches[1]))
        # Its own Codex home in the attempt directory, linked to the native sign-in only while it ran.
        self.assertEqual(seen["codex_home"], str(attempt / "codex-home"))
        self.assertEqual(seen["auth_link"], str(fixture.native / "auth.json"))
        self.assertFalse(os.path.lexists(attempt / "codex-home/auth.json"))
        self.assertTrue((attempt / "codex-home/sessions").is_dir())  # the session record stays private
        # HOME, TMPDIR and the working directory: one empty scratch directory outside the state tree, now removed.
        scratch = Path(seen["cwd"]).parent
        self.assertEqual((seen["cwd"], seen["home"], seen["tmpdir"]),
                         (str(scratch / "cwd"), str(scratch / "home"), str(scratch / "tmp")))
        self.assertTrue(scratch.name.startswith("gt26-call-"))
        self.assertNotIn(fixture.state.resolve(), scratch.resolve().parents)
        self.assertFalse(scratch.exists())
        self.assertEqual(set(seen["env"]) - set(RUN.CHILD_ENV_ALLOWLIST), {"CODEX_HOME", "HOME", "TMPDIR"})
        self.assertNotIn("RUST_LOG", seen["env"])
        self.assertNotIn("OPENAI_API_KEY", seen["env"])
        self.assertTrue(seen["stdin_devnull"])
        self.assertEqual(seen["schema"], json.loads((HERE / "response.schema.json").read_text()))
        for path in fixture.state.rglob("*"):
            if "codex-home" in path.relative_to(fixture.state).parts[:-1]:
                continue  # Codex's own files; their directory is 0700
            mode = stat.S_IMODE(path.lstat().st_mode)
            self.assertEqual(mode, 0o700 if path.is_dir() else 0o600, path)
        self.assertEqual(stat.S_IMODE(fixture.state.stat().st_mode), 0o700)
        records = fixture.records("S1")
        self.assertEqual(sorted(records), [("b001", 1), ("b002", 1)])
        first = records[("b001", 1)]
        self.assertEqual((first["outcome"], first["usage"], first["reply_status"], first["model"], first["effort"]),
                         ("ok", DEFAULT_USAGE, "valid", "gpt-6-sol", "medium"))
        self.assertEqual((first["credential_link"], first["scratch_entries"], first["tool_items"],
                          first["session_record_found"]), ("removed", 0, 0, True))
        self.assertEqual(records[("b002", 1)]["scratch_entries"], 1)  # counted, then removed with the scratch
        self.assertEqual(first["accessions"], [row["accession"] for row in fixture.batches[0]])
        self.assertIn(first["slot"], (1, 2, 3))
        runs = [json.loads(line) for line in (arm_dir / "runs.jsonl").read_text().splitlines()]
        self.assertEqual((runs[-1]["status"], runs[-1]["codex_version"]), ("complete", "codex-cli 0.157.1"))
        self.assertEqual(fixture.run("S1"), RUN.EXIT_DONE)  # complete: nothing runs again
        self.assertEqual(len(fixture.calls()), 2)

    def test_the_same_batches_go_to_every_arm(self):
        fixture = Fixture(self, rows_for(40))
        for arm in ("A0", "L1"):
            self.assertEqual(fixture.run(arm), RUN.EXIT_DONE)
        layouts = [[record["accessions"] for _, record in sorted(fixture.records(arm).items())] for arm in ("A0", "L1")]
        self.assertEqual(layouts[0], layouts[1])
        self.assertEqual(layouts[0], RUN.layout(fixture.batches))

    def test_calls_never_exceed_the_host_slots(self):
        fixture = Fixture(self, rows_for(75))
        fixture.configure(sleep=0.3)
        held = []
        for number in (1, 2):  # another job holds two of the host's three slots
            fd = os.open(fixture.locks / f"slot-{number}", os.O_RDWR | os.O_CREAT, 0o644)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            held.append(fd)
        try:
            self.assertEqual(fixture.run("A0"), RUN.EXIT_DONE)
        finally:
            for fd in held:
                os.close(fd)
        self.assertEqual(max_concurrency(fixture.log), 1)
        self.assertEqual({record["slot"] for record in fixture.records("A0").values()}, {3})
        self.assertGreater(max(record["slot_wait_seconds"] for record in fixture.records("A0").values()), 0.1)

    def test_two_arms_at_once_share_the_three_slot_pool(self):
        fixture = Fixture(self, rows_for(75))
        fixture.configure(sleep=0.25)
        codes = {}
        threads = [threading.Thread(target=lambda arm=arm: codes.__setitem__(arm, fixture.run(arm)))
                   for arm in ("A0", "S0")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(60)
        self.assertEqual(codes, {"A0": RUN.EXIT_DONE, "S0": RUN.EXIT_DONE})
        self.assertEqual(len(fixture.calls()), 10)
        self.assertLessEqual(max_concurrency(fixture.log), 3)
        self.assertGreaterEqual(max_concurrency(fixture.log), 2)

    def test_usage_limit_stops_the_arm_and_the_batch_resumes_after_the_reset(self):
        fixture = Fixture(self, rows_for(75))
        second = fixture.first(1)
        fixture.configure(sleep=0.4, rules=[{"batch": second, "attempt": 1, "action": "limit"},
                                            {"batch": second, "attempt": 2, "action": "exit_after_turn"}])
        out = io.StringIO()
        self.assertEqual(fixture.run("A0", out=out), RUN.EXIT_LIMIT)
        self.assertEqual(json.loads(out.getvalue())["status"], "limit_stopped")
        note = json.loads((fixture.state / "LIMIT").read_text())
        self.assertEqual((note["arm"], note["batch"], note["attempt"], note["recovered"]), ("A0", "b002", 1, False))
        self.assertIn("hit your usage limit", note["codex_message"])
        self.assertEqual(stat.S_IMODE((fixture.state / "LIMIT").stat().st_mode), 0o600)
        started = {(call["batch"], call["attempt"]) for call in fixture.calls()}
        self.assertIn((second, 1), started)
        self.assertLessEqual(started, {(fixture.first(0), 1), (second, 1), (fixture.first(2), 1)})
        records = fixture.records("A0")
        self.assertEqual((records[("b002", 1)]["outcome"], records[("b002", 1)]["limit"],
                          records[("b002", 1)]["limit_noted"], records[("b002", 1)]["usage_known"]),
                         ("limit", True, True, True))
        self.assertEqual(records[("b001", 1)]["outcome"], "ok")  # running calls finish and are kept
        self.assertFalse((fixture.state / "arms/A0/batches/b004").exists())
        self.assertEqual(fixture.run("A0"), RUN.EXIT_LIMIT)  # the note blocks every run until it is removed
        self.assertEqual(len(fixture.calls()), len(started))
        (fixture.state / "LIMIT").unlink()
        self.assertEqual(fixture.run("A0"), RUN.EXIT_DONE)
        records = fixture.records("A0")
        self.assertEqual([records[("b002", n)]["outcome"] for n in (1, 2, 3)], ["limit", "failed", "ok"])
        self.assertEqual(records[("b002", 2)]["reason"], "exit")
        self.assertEqual(len(fixture.calls()), 7)  # five batches once, b002 twice more

    def test_the_limit_note_is_published_while_the_call_runs_and_no_call_starts_after_it(self):
        fixture = Fixture(self, rows_for(90))
        fixture.configure(sleep=0.8, limit_sleep=2.0,
                          rules=[{"batch": fixture.first(2), "attempt": 1, "action": "limit_slow"}])
        self.assertEqual(fixture.run("A0"), RUN.EXIT_LIMIT)
        published = (fixture.state / "LIMIT").stat().st_mtime_ns
        limit_end = [entry["t"] for entry in fixture.log_entries("end") if entry["batch"] == fixture.first(2)]
        self.assertLess(published / 1e9, limit_end[0] - 1.0)  # while the limited call ran, before its slot freed
        records = fixture.records("A0")
        self.assertEqual(sorted(records), [("b001", 1), ("b002", 1), ("b003", 1)])  # the first wave only
        self.assertEqual([records[key]["outcome"] for key in sorted(records)], ["ok", "ok", "limit"])
        # b001 and b002 ended after the note; their workers found it at the gate and started nothing more.
        self.assertTrue(all(record["launched_unix_ns"] < published for record in records.values()))
        others_end = [entry["t"] for entry in fixture.log_entries("end") if entry["batch"] != fixture.first(2)]
        self.assertTrue(all(end > published / 1e9 for end in others_end))

    def test_a_limit_note_from_another_arm_stops_a_running_arm(self):
        fixture = Fixture(self, rows_for(75))
        fixture.configure(sleep=0.5)
        codes = {}
        thread = threading.Thread(target=lambda: codes.__setitem__("A1", fixture.run("A1")))
        thread.start()
        deadline = time.monotonic() + 30
        while not fixture.calls() and time.monotonic() < deadline:
            time.sleep(0.02)
        (fixture.state / "LIMIT").write_text(json.dumps({"arm": "S0"}))
        thread.join(60)
        self.assertEqual(codes, {"A1": RUN.EXIT_LIMIT})
        self.assertLessEqual(len(fixture.calls()), 3)  # the first wave finishes; nothing starts after the note
        self.assertEqual({record["outcome"] for record in fixture.records("A1").values()}, {"ok"})
        self.assertEqual(json.loads((fixture.state / "LIMIT").read_text()), {"arm": "S0"})  # never overwritten

    def test_only_codex_error_events_count_as_the_usage_limit(self):
        fixture = Fixture(self, rows_for(20))
        fixture.configure(rules=[{"action": "content_limit"}])
        self.assertEqual(fixture.run("A1"), RUN.EXIT_DONE)
        self.assertFalse((fixture.state / "LIMIT").exists())
        self.assertEqual({record["outcome"] for record in fixture.records("A1").values()}, {"ok"})
        events = RUN.read_events(fixture.state / "arms/A1/batches/b001/attempt-1/events.jsonl")
        self.assertIsNone(RUN.limit_message(events))
        self.assertIsNotNone(RUN.limit_message([{"type": "turn.failed", "error": {"message": LIMIT_TEXT}}]))
        self.assertIsNotNone(RUN.limit_message([{"type": "error", "message": LIMIT_TEXT}]))

    def test_an_abandoned_limit_is_published_before_any_call(self):
        fixture = Fixture(self, rows_for(20))
        attempt = fixture.attempt("A0", "b001", 1)
        attempt.mkdir(mode=0o700, parents=True)
        for path in (fixture.state, *attempt.relative_to(fixture.state).parents):
            os.chmod(fixture.state / path, 0o700)
        (attempt / "codex-home").mkdir(mode=0o700)
        (attempt / "codex-home/auth.json").symlink_to(fixture.native / "auth.json")  # left by the dead runner
        (attempt / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in (
            {"type": "turn.started"}, {"type": "error", "message": LIMIT_TEXT},
            {"type": "turn.failed", "error": {"message": LIMIT_TEXT}})))
        out = io.StringIO()
        self.assertEqual(fixture.run("A0", out=out), RUN.EXIT_LIMIT)  # the runner died before publishing it
        self.assertEqual(json.loads(out.getvalue())["calls"], 0)
        self.assertEqual(fixture.calls(), [])
        note = json.loads((fixture.state / "LIMIT").read_text())
        self.assertEqual((note["batch"], note["attempt"], note["recovered"]), ("b001", 1, True))
        record = fixture.records()[("b001", 1)]
        self.assertEqual((record["outcome"], record["limit_noted"]), ("limit", True))
        self.assertFalse(os.path.lexists(attempt / "codex-home/auth.json"))
        (fixture.state / "LIMIT").unlink()  # after the reset
        self.assertEqual(fixture.run("A0"), RUN.EXIT_DONE)
        self.assertEqual(fixture.records()[("b001", 2)]["outcome"], "ok")
        self.assertEqual(len(fixture.calls()), 2)

    def test_an_outage_stops_the_arm_without_using_retries_and_recovers(self):
        fixture = Fixture(self, rows_for(75))
        fixture.configure(outage=True)
        out = io.StringIO()
        self.assertEqual(fixture.run("A0", out=out), RUN.EXIT_UNAVAILABLE)
        self.assertEqual(json.loads(out.getvalue())["status"], "unavailable_stopped")
        note = json.loads((fixture.state / "UNAVAILABLE").read_text())
        self.assertEqual((note["reason"], note["codex_message"]),
                         ("no_turn_completed", "stream disconnected before completion"))
        first_wave = len(fixture.calls())
        self.assertLessEqual(first_wave, 3)
        records = fixture.records()
        self.assertEqual({(record["outcome"], record["reason"], record["usage_known"]) for record in records.values()},
                         {("unavailable", "no_turn_completed", False)})
        self.assertEqual(fixture.run("A0"), RUN.EXIT_UNAVAILABLE)  # the note blocks every arm
        self.assertEqual(fixture.run("S1"), RUN.EXIT_UNAVAILABLE)
        self.assertEqual(len(fixture.calls()), first_wave)
        fixture.configure()  # the service is back
        (fixture.state / "UNAVAILABLE").unlink()
        self.assertEqual(fixture.run("A0"), RUN.EXIT_DONE)
        outcomes = {}
        for (batch, _), record in sorted(fixture.records().items()):
            outcomes.setdefault(batch, []).append(record["outcome"])
        self.assertEqual(len(outcomes), 5)
        self.assertEqual(sum(value == ["unavailable", "ok"] for value in outcomes.values()), first_wave)
        self.assertTrue(all(value in (["ok"], ["unavailable", "ok"]) for value in outcomes.values()))
        self.assertEqual(len(fixture.calls()), first_wave + 5)  # every batch completed; no retry was used

    def test_a_launch_failure_stops_the_arm_without_using_a_retry(self):
        fixture = Fixture(self, rows_for(20))
        fixture.configure(break_after_version=True)
        self.assertEqual(fixture.run("A0"), RUN.EXIT_UNAVAILABLE)
        failed_launches = list(fixture.records().values())
        self.assertTrue(failed_launches)
        self.assertEqual({(record["outcome"], record["reason"], record["usage_known"]) for record in failed_launches},
                         {("unavailable", "launch_error", True)})
        self.assertEqual(fixture.calls(), [])  # nothing ran
        self.assertEqual(json.loads((fixture.state / "UNAVAILABLE").read_text())["reason"], "launch_error")
        fixture.codex.chmod(0o755)
        fixture.configure()
        (fixture.state / "UNAVAILABLE").unlink()
        self.assertEqual(fixture.run("A0"), RUN.EXIT_DONE)
        self.assertEqual(len(fixture.calls()), 2)

    def test_tool_use_fails_the_call_and_uses_the_retry(self):
        fixture = Fixture(self, rows_for(45))
        fixture.configure(rules=[{"batch": fixture.first(0), "attempt": 1, "action": "tool_call"},
                                 {"batch": fixture.first(1), "action": "json_tool"}])
        self.assertEqual(fixture.run("L1"), RUN.EXIT_FAILED_BATCHES)
        records = fixture.records("L1")
        first = records[("b001", 1)]
        self.assertEqual((first["outcome"], first["reason"], first["tool_items"]), ("failed", "tool_use", 2))
        self.assertEqual(first["session_items"]["custom_tool_call"], 1)
        self.assertEqual(records[("b001", 2)]["outcome"], "ok")
        self.assertEqual([records[("b002", n)]["reason"] for n in (1, 2)], ["tool_use", "tool_use"])
        self.assertEqual(records[("b002", 1)]["json_items"]["command_execution"], 1)
        self.assertEqual(records[("b003", 1)]["outcome"], "ok")

    def test_a_missing_or_unknown_session_record_stops_the_arm_without_using_the_retry(self):
        for action, reason in (("no_rollout", "rollout_missing"), ("odd_item", "unexpected_item")):
            with self.subTest(action=action):
                fixture = Fixture(self, rows_for(10))
                fixture.configure(rules=[{"attempt": 1, "action": action}])
                self.assertEqual(fixture.run("S0"), RUN.EXIT_UNAVAILABLE)
                record = fixture.records("S0")[("b001", 1)]
                self.assertEqual((record["outcome"], record["reason"], record["usage_known"]),
                                 ("unavailable", reason, True))
                self.assertEqual(json.loads((fixture.state / "UNAVAILABLE").read_text())["reason"], reason)
                (fixture.state / "UNAVAILABLE").unlink()
                self.assertEqual(fixture.run("S0"), RUN.EXIT_DONE)
                self.assertEqual(fixture.records("S0")[("b001", 2)]["outcome"], "ok")

    def test_a_replaced_credential_link_stops_the_run_and_is_left_untouched(self):
        fixture = Fixture(self, rows_for(10))
        fixture.configure(rules=[{"action": "replace_link"}])
        self.assertEqual(fixture.run("A0"), RUN.EXIT_ERROR)
        left = fixture.attempt("A0", "b001", 1) / "codex-home/auth.json"
        self.assertTrue(left.exists() and not left.is_symlink())
        self.assertEqual(fixture.records()[("b001", 1)]["credential_link"], "replaced")
        self.assertEqual((fixture.native / "auth.json").read_text(), "{}")

    def test_a_failed_batch_runs_once_more_and_then_never_again(self):
        fixture = Fixture(self, rows_for(45))
        fixture.configure(rules=[{"batch": fixture.first(0), "attempt": 1, "action": "exit_after_turn"},
                                 {"batch": fixture.first(1), "action": "invalid_reply"}])
        out = io.StringIO()
        self.assertEqual(fixture.run("L0", out=out), RUN.EXIT_FAILED_BATCHES)
        self.assertEqual(json.loads(out.getvalue())["status"], "complete_with_failed_batches")
        records = fixture.records("L0")
        self.assertEqual([(key, records[key]["outcome"], records[key]["reason"]) for key in sorted(records)], [
            (("b001", 1), "failed", "exit"), (("b001", 2), "ok", None),
            (("b002", 1), "failed", "reply_invalid"), (("b002", 2), "failed", "reply_invalid"),
            (("b003", 1), "ok", None)])
        self.assertEqual(fixture.run("L0"), RUN.EXIT_FAILED_BATCHES)
        self.assertEqual(len(fixture.calls()), 5)  # the failed batch never runs a third time

    def test_timeout_kills_the_call_and_counts_as_a_failure(self):
        fixture = Fixture(self, rows_for(10))
        fixture.configure(rules=[{"attempt": 1, "action": "hang"}])
        self.assertEqual(fixture.run("A0", timeout_seconds=0.5), RUN.EXIT_DONE)
        records = fixture.records("A0")
        self.assertEqual((records[("b001", 1)]["reason"], records[("b001", 1)]["timed_out"],
                          records[("b001", 1)]["usage_known"]), ("timeout", True, False))
        self.assertEqual(records[("b001", 2)]["outcome"], "ok")
        pid = fixture.calls()[0]["pid"]
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_an_abandoned_attempt_is_recorded_without_using_the_retry(self):
        fixture = Fixture(self, rows_for(10))
        attempt = fixture.attempt("A0", "b001", 1)
        attempt.mkdir(mode=0o700, parents=True)
        for path in (fixture.state, *attempt.relative_to(fixture.state).parents):
            os.chmod(fixture.state / path, 0o700)
        (attempt / "events.jsonl").write_text(json.dumps({"type": "turn.started"}) + "\n")
        self.assertEqual(fixture.run("A0"), RUN.EXIT_DONE)
        records = fixture.records("A0")
        self.assertEqual((records[("b001", 1)]["outcome"], records[("b001", 1)]["reason"],
                          records[("b001", 1)]["usage_known"]), ("abandoned", "abandoned", False))
        self.assertEqual(records[("b001", 2)]["outcome"], "ok")
        self.assertEqual(RUN.batch_state([records[("b001", 1)]], 0), "pending")  # never counted

    def test_sigterm_records_the_running_call_as_interrupted_without_counting_it(self):
        fixture = Fixture(self, rows_for(10))
        fixture.configure(rules=[{"attempt": 1, "action": "hang"}])
        args = ["run", "--plan", str(fixture.plan), "--arm", "A0", "--acquisition", str(fixture.acquisition),
                "--lock-dir", str(fixture.locks), "--state-dir", str(fixture.state)]
        process = fixture.cli(*args)
        deadline = time.monotonic() + 30
        while not fixture.calls() and time.monotonic() < deadline:
            time.sleep(0.05)
        process.send_signal(signal.SIGTERM)
        _, stderr = process.communicate(timeout=60)
        self.assertEqual(process.returncode, RUN.EXIT_INTERRUPTED, stderr)
        record = fixture.records()[("b001", 1)]
        self.assertEqual((record["outcome"], record["interrupted"], record["usage_known"]),
                         ("interrupted", True, False))
        process = fixture.cli(*args)
        process.communicate(timeout=60)
        self.assertEqual(process.returncode, RUN.EXIT_DONE)
        self.assertEqual(fixture.records()[("b001", 2)]["outcome"], "ok")
        self.assertEqual(RUN.batch_state(list(fixture.records().values()), 1), "completed")

    def test_refusals_before_any_call(self):
        fixture = Fixture(self, rows_for(10))
        with self.assertRaisesRegex(ValueError, "lock directory"):
            RUN.run_arm(fixture.plan, "A0", fixture.acquisition, fixture.state, fixture.root / "missing")
        fixture.configure(version="codex-cli 0.158.0")
        with self.assertRaisesRegex(ValueError, "0.158.0"):
            fixture.run("A0")
        fixture.configure()
        wrong = json.loads(fixture.plan.read_text())
        wrong["batching"]["layout_sha256"] = "0" * 64
        wrong_plan = fixture.root / "wrong-plan.json"
        wrong_plan.write_text(json.dumps(wrong, indent=2))
        with self.assertRaisesRegex(ValueError, "frozen layout"):
            RUN.run_arm(wrong_plan, "A0", fixture.acquisition, fixture.state, fixture.locks)
        system = fixture.root / "system-config.toml"
        system.write_text("")
        with mock.patch.object(RUN, "SYSTEM_CONFIG_FILES", (str(system),)):
            with self.assertRaisesRegex(ValueError, "system Codex configuration"):
                fixture.run("A0")
        (fixture.native / "auth.json").rename(fixture.native / "moved.json")
        with self.assertRaisesRegex(ValueError, "no native Codex sign-in"):
            fixture.run("A0")
        (fixture.native / "moved.json").rename(fixture.native / "auth.json")
        fixture.state.mkdir(mode=0o755, exist_ok=True)
        os.chmod(fixture.state, 0o755)
        with self.assertRaisesRegex(ValueError, "mode 0700"):
            fixture.run("A0")
        os.chmod(fixture.state, 0o700)
        for name, code in (("LIMIT", RUN.EXIT_LIMIT), ("UNAVAILABLE", RUN.EXIT_UNAVAILABLE)):
            (fixture.state / name).write_text("{}")
            self.assertEqual(fixture.run("A0"), code)
            (fixture.state / name).unlink()
        self.assertEqual(fixture.calls(), [])
        self.assertFalse((fixture.state / "arms").exists())
        done = fixture.cli("run", "--plan", str(fixture.plan), "--arm", "A0", "--acquisition",
                           str(fixture.acquisition), "--lock-dir", str(fixture.root / "missing"),
                           "--state-dir", str(fixture.state))
        _, stderr = done.communicate(timeout=60)
        self.assertEqual(done.returncode, RUN.EXIT_REFUSED, stderr)
        self.assertIn("lock directory", stderr)
        self.assertEqual(fixture.run("A0"), RUN.EXIT_DONE)
        fd = os.open(fixture.state / "arms/A0/run.lock", os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with self.assertRaisesRegex(ValueError, "already running"):
                fixture.run("A0")
        finally:
            os.close(fd)
        changed = json.loads(fixture.plan.read_text())
        changed["question"] += " (edited)"
        fixture.plan.write_text(json.dumps(changed, indent=2))
        with self.assertRaisesRegex(ValueError, "different plan"):
            fixture.run("A0")


def summary(billed, wall=1.0, json_valid=1.0, complete=True, usage_complete=True, violations=0):
    return {"every_batch_completed": complete, "json_valid_rate": json_valid,
            "tokens": {"subset_violations": violations, "usage_complete": usage_complete,
                       "per_filing": {"billed": billed}},
            "wall": {"median_ok_call_wall_seconds": wall}}


class DecisionRuleTests(unittest.TestCase):
    def decide(self, summaries, lowers=None, states=None):
        results = {arm["id"]: {"state": (states or {}).get(arm["id"], "complete")} for arm in PLAN["arms"]}
        bootstraps = {arm_id: {"lower": (lowers or {}).get(arm_id, 0.0)} for arm_id in summaries if arm_id != "A0"}
        return ANALYZE.decide(PLAN, results, summaries, bootstraps)

    def test_the_cheapest_candidate_below_the_control_wins_ties_to_wall_time_then_plan_order(self):
        base = {"A0": summary(900), "A1": summary(500), "S0": summary(300), "S1": summary(200),
                "L0": summary(100, complete=False), "L1": summary(50, json_valid=0.975)}
        selected, criteria = self.decide(base, lowers={"S1": -0.021})
        self.assertEqual((selected["arm"], selected["outcome"], selected["effort"]),
                         ("S0", "route_mechanical_extraction", "max"))
        self.assertEqual(selected["routable"], ["A0", "A1", "S0"])
        self.assertEqual(selected["ranked"], ["S0", "A1"])
        self.assertFalse(criteria["S1"]["noninferior_micro_f1"])
        self.assertEqual(self.decide(base, lowers={"S1": -0.02})[0]["arm"], "S1")  # the margin is inclusive
        tie = {**base, "A1": summary(300, wall=0.5)}
        self.assertEqual(self.decide(tie, lowers={"S1": -0.5})[0]["arm"], "A1")
        tie = {**base, "A1": summary(300, wall=1.0)}
        self.assertEqual(self.decide(tie, lowers={"S1": -0.5})[0]["arm"], "A1")  # plan order

    def test_a_candidate_must_cost_strictly_less_than_the_control(self):
        selected, _ = self.decide({"A0": summary(300), "S0": summary(300, wall=0.1), "A1": summary(900)})
        self.assertEqual((selected["arm"], selected["outcome"], selected["reason"]),
                         ("A0", "keep_default", "no_candidate_below_control"))
        self.assertEqual(selected["ranked"], ["S0", "A1"])
        cheap_default = {arm: summary(1000) for arm in ("A1", "S0", "S1", "L0", "L1")}
        self.assertEqual(self.decide({**cheap_default, "A0": summary(10)})[0]["outcome"], "keep_default")

    def test_a_candidate_with_unknown_usage_is_routable_but_never_ranked(self):
        selected, _ = self.decide({"A0": summary(900), "S0": summary(100, usage_complete=False)})
        self.assertEqual((selected["arm"], selected["outcome"], selected["reason"], selected["routable"]),
                         ("A0", "keep_default", "no_candidate_with_known_usage", ["A0", "S0"]))

    def test_unknown_control_usage_is_a_lower_bound_never_a_reason_to_drop_the_control(self):
        # The reviewers' probe: A0 at 1,000 with unknown usage, S0 routable at 9,000 with known usage.
        selected, _ = self.decide({"A0": summary(1000, usage_complete=False), "S0": summary(9000)})
        self.assertEqual((selected["arm"], selected["outcome"], selected["control_usage_complete"]),
                         (None, "inconclusive_control_usage_incomplete", False))
        selected, _ = self.decide({"A0": summary(1000, usage_complete=False), "S0": summary(500)})
        self.assertEqual((selected["arm"], selected["outcome"]), ("S0", "route_mechanical_extraction"))
        selected, _ = self.decide({"A0": summary(1000, usage_complete=False), "S0": summary(10, json_valid=0.5)})
        self.assertEqual((selected["outcome"], selected["reason"]), ("keep_default", "no_routable_candidate"))

    def test_control_problems_and_subset_violations_are_inconclusive(self):
        ok = {"A0": summary(900), "S0": summary(100)}
        self.assertEqual(self.decide({"S0": summary(1)}, states={"A0": "not_run"})[0]["outcome"],
                         "inconclusive_control_not_evaluated")
        self.assertEqual(self.decide(ok, states={"A0": "incomplete"})[0]["outcome"], "inconclusive_control_incomplete")
        for bad in (summary(900, complete=False), summary(900, json_valid=0.97)):
            self.assertEqual(self.decide({**ok, "A0": bad})[0]["outcome"], "inconclusive_control_invalid")
        self.assertEqual(self.decide({**ok, "S0": summary(100, violations=1)})[0]["outcome"],
                         "inconclusive_usage_subset_rule_violated")

    def test_billed_tokens_count_reasoning_once_and_unknown_usage_is_named(self):
        records = [{"outcome": "ok", "usage": {"input_tokens": 1000, "cached_input_tokens": 400,
                                               "cache_write_input_tokens": 0, "output_tokens": 120,
                                               "reasoning_output_tokens": 100}},
                   {"outcome": "failed", "reason": "reply_invalid",
                    "usage": {"input_tokens": 500, "cached_input_tokens": 0, "output_tokens": 30,
                              "reasoning_output_tokens": 30}},
                   {"outcome": "limit", "reason": "usage_limit", "usage": None},
                   {"outcome": "unavailable", "reason": "launch_error", "usage": None}]
        usage = ANALYZE.usage_summary(records, 10)
        self.assertEqual(usage["totals"]["billed"], (1000 - 400 + 120) + (500 + 30))
        self.assertEqual((usage["totals"]["reasoning"], usage["totals"]["visible_output"]), (130, 20))
        self.assertEqual((usage["per_filing"]["cached_input"], usage["usage_complete"]), (40.0, True))
        unknown = [{"outcome": "failed", "reason": "timeout", "usage": None},
                   {"outcome": "unavailable", "reason": "no_turn_completed", "usage": None},
                   {"outcome": "interrupted", "reason": "interrupted", "usage": None},
                   {"outcome": "abandoned", "reason": "abandoned", "usage": None}]
        usage = ANALYZE.usage_summary(records + unknown, 10)
        self.assertEqual((usage["calls_without_usage"], usage["usage_complete"]), (4, False))
        self.assertEqual(usage["calls_without_usage_by_outcome"],
                         {"failed": 1, "unavailable": 1, "interrupted": 1, "abandoned": 1})
        bad = [{"outcome": "ok", "usage": {"input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 5,
                                           "reasoning_output_tokens": 6}}]
        self.assertEqual(ANALYZE.usage_summary(bad, 1)["subset_violations"], 1)


class AnalysisTests(unittest.TestCase):
    def test_analysis_on_synthetic_labels(self):
        rows = rows_for(45)
        fixture = Fixture(self, rows)
        gold = {row["accession"]: row["labels"] for row in rows}
        noisy = {accession: (labels[1:] if index % 3 == 0 else labels) for index, (accession, labels)
                 in enumerate(gold.items())}

        def usage(output, reasoning):
            return {"input_tokens": 3000, "cached_input_tokens": 1000, "cache_write_input_tokens": 0,
                    "output_tokens": output, "reasoning_output_tokens": reasoning}

        fixture.configure(
            answers={"default": gold, "gpt-6-sol/medium": noisy},
            usage={"gpt-6-astra/max": usage(3000, 2800), "gpt-6-astra/medium": usage(900, 700),
                   "gpt-6-sol/max": usage(600, 500), "gpt-6-sol/medium": usage(300, 200),
                   "gpt-6-luna/max": usage(100, 50), "gpt-6-luna/medium": usage(200, 100)},
            rules=[{"key": "gpt-6-luna/max", "batch": fixture.first(1), "action": "invalid_reply"},
                   {"key": "gpt-6-luna/medium", "batch": fixture.first(0), "action": "drop_last"}])
        for arm in ("A0", "A1", "S0", "S1", "L0", "L1"):
            self.assertEqual(fixture.run(arm), RUN.EXIT_FAILED_BATCHES if arm == "L0" else RUN.EXIT_DONE, arm)
        quota = fixture.root / "quota.json"
        write_json(quota, {"source": "coordinator reading", "readings": [
            {"arm": "A0", "window": "weekly", "before_percent": 10, "after_percent": 14.5}]})
        out = fixture.root / "decision.json"
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            ANALYZE.main(["--plan", str(fixture.plan), "--acquisition", str(fixture.acquisition),
                          "--state-dir", str(fixture.state), "--quota-context", str(quota), "--out", str(out)])
        self.assertEqual(json.loads(printed.getvalue())["selected"]["arm"], "S0")
        text = out.read_text()
        decision = json.loads(text)
        arms = {entry["arm"]: entry for entry in decision["arms"]}
        self.assertEqual((decision["final"], decision["n_filings"], decision["n_batches"]), (True, 45, 3))
        self.assertEqual((decision["frozen_inputs_verified"], decision["frozen_inputs"]),
                         (True, PLAN["frozen_inputs"]))
        self.assertEqual(decision["selected"]["arm"], "S0")
        self.assertEqual(decision["selected"]["outcome"], "route_mechanical_extraction")
        self.assertEqual(decision["selected"]["routable"], ["A0", "A1", "S0"])
        self.assertEqual(decision["selected"]["ranked"], ["S0", "A1"])
        self.assertAlmostEqual(decision["selected"]["control_billed_per_filing"], 3 * (2000 + 3000) / 45)
        triples = [LI26_ANALYZE.counts(gold[accession], noisy[accession]) for accession in gold]
        self.assertAlmostEqual(arms["S1"]["summary"]["micro_f1"], LI26_ANALYZE.micro_f1(triples))
        self.assertFalse(arms["S1"]["criteria"]["noninferior_micro_f1"])
        self.assertEqual(arms["A1"]["summary"]["micro_f1"], 1.0)
        self.assertEqual(arms["L0"]["summary"]["batches"], {"total": 3, "completed": 2, "failed": 1, "pending": 0})
        self.assertEqual(arms["L0"]["summary"]["failed_batch_ids"], ["b002"])
        self.assertEqual(arms["L0"]["summary"]["invalid_filings"], 15)  # never dropped: scored as invalid
        self.assertEqual(arms["L0"]["summary"]["calls"]["by_reason"], {"reply_invalid": 2})
        self.assertFalse(arms["L0"]["routable"])
        self.assertAlmostEqual(arms["L1"]["summary"]["json_valid_rate"], 44 / 45)
        self.assertFalse(arms["L1"]["criteria"]["json_valid_rate"])
        s0 = arms["S0"]["summary"]["tokens"]
        self.assertEqual(s0["totals"]["billed"], 3 * (3000 - 1000 + 600))
        self.assertAlmostEqual(s0["per_filing"]["billed"], 3 * 2600 / 45)
        self.assertEqual(s0["totals"]["cached_input"], 3000)
        self.assertEqual(arms["L0"]["summary"]["calls"]["failed"], 2)
        self.assertEqual(arms["L0"]["summary"]["tokens"]["totals"]["output_including_reasoning"], 4 * 100)
        self.assertEqual(decision["quota_context"]["readings"][0]["delta_percent"], 4.5)
        self.assertFalse(decision["quota_context"]["used_by_rule"])
        self.assertIsNone(arms["A0"]["bootstrap_vs_control"])
        self.assertEqual(arms["A1"]["bootstrap_vs_control"]["resamples"], 10000)
        for row in rows:  # aggregates only: no filing text and no accession number
            self.assertNotIn(row["accession"], text)
            self.assertNotIn(row["input"][:40], text)
        with self.assertRaises(FileExistsError):  # the decision file is never overwritten
            ANALYZE.main(["--plan", str(fixture.plan), "--acquisition", str(fixture.acquisition),
                          "--state-dir", str(fixture.state), "--out", str(out)])

    def test_incomplete_or_missing_arms_keep_the_decision_provisional(self):
        fixture = Fixture(self, rows_for(75))
        fixture.configure(rules=[{"key": "gpt-6-sol/max", "batch": fixture.first(3), "action": "limit"}])
        self.assertEqual(fixture.run("A0"), RUN.EXIT_DONE)
        self.assertEqual(fixture.run("S0"), RUN.EXIT_LIMIT)
        decision = ANALYZE.analyze(json.loads(fixture.plan.read_text()),
                                   hashlib.sha256(fixture.plan.read_bytes()).hexdigest(), fixture.acquisition,
                                   fixture.state)
        arms = {entry["arm"]: entry for entry in decision["arms"]}
        self.assertFalse(decision["final"])
        self.assertEqual(decision["arms_incomplete"], ["S0"])
        self.assertEqual(decision["arms_not_run"], ["A1", "S1", "L0", "L1"])
        self.assertIn("b004", arms["S0"]["summary"]["pending_batch_ids"])
        self.assertEqual(arms["S0"]["summary"]["calls"]["limit"], 1)
        self.assertFalse(arms["S0"]["routable"])
        self.assertEqual((decision["selected"]["arm"], decision["selected"]["reason"]), ("A0", "no_routable_candidate"))

    def test_analysis_refuses_changed_frozen_code(self):
        fixture = Fixture(self, rows_for(10))
        self.assertEqual(fixture.run("A0"), RUN.EXIT_DONE)
        plan = json.loads(fixture.plan.read_text())
        digest = hashlib.sha256(fixture.plan.read_bytes()).hexdigest()
        scorer = LI26 / "analyze.py"
        real = ANALYZE.run_arm.li26.digest

        def edited(path):  # li26's scorer as if edited after the arms ran, with the plan unchanged
            return "0" * 64 if Path(path).resolve() == scorer.resolve() else real(path)

        with mock.patch.object(ANALYZE.run_arm.li26, "digest", side_effect=edited):
            with self.assertRaisesRegex(ValueError, "frozen input changed: .*local-inference-latest-20260926/analyze"):
                ANALYZE.analyze(plan, digest, fixture.acquisition, fixture.state)
        self.assertEqual(ANALYZE.analyze(plan, digest, fixture.acquisition, fixture.state)["frozen_inputs_verified"],
                         True)

    def test_analysis_refuses_a_running_arm_or_another_plan(self):
        fixture = Fixture(self, rows_for(10))
        self.assertEqual(fixture.run("A0"), RUN.EXIT_DONE)
        plan = json.loads(fixture.plan.read_text())
        digest = hashlib.sha256(fixture.plan.read_bytes()).hexdigest()
        fd = os.open(fixture.state / "arms/A0/run.lock", os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with self.assertRaisesRegex(ValueError, "running"):
                ANALYZE.analyze(plan, digest, fixture.acquisition, fixture.state)
        finally:
            os.close(fd)
        with self.assertRaisesRegex(ValueError, "different plan"):
            ANALYZE.analyze(plan, "0" * 64, fixture.acquisition, fixture.state)
        bad = fixture.root / "quota-bad.json"
        write_json(bad, {"readings": [{"arm": "A0", "before_percent": 10, "after_percent": 140}]})
        with self.assertRaisesRegex(ValueError, "percentages"):
            ANALYZE.analyze(plan, digest, fixture.acquisition, fixture.state, bad)


if __name__ == "__main__":
    unittest.main()
