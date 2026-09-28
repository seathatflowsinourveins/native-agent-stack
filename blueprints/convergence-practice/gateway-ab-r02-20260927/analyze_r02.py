#!/usr/bin/env python3
"""Paired analysis of the R02 promptfoo results and the preregistered decision.

  analyze_r02.py ids --results-ab AB.json --results-ba BA.json --state-dir DIR
  analyze_r02.py readback READBACK.json
  uv run --no-project --python 3.14 --with numpy==2.5.3 --with scipy==1.18.1 --with statsmodels==0.15.0 \
      python analyze_r02.py analyze --results-ab AB.json --results-ba BA.json --state-dir DIR \
      --call-logs CALL_LOGS.json --gateway-readbacks AB_BEFORE AB_AFTER BA_BEFORE BA_AFTER [--out DECISION.json]

Inputs are promptfoo 0.123.1 `-o <file>.json` outputs (promptfoo@0.123.1:src/util/output.ts:465-494, rows in
results.results; installed dist/src/util-BE6VXITn.js:2162-2196 adds metadata.promptfooVersion and nodeVersion), the
private tests files build_r02.py wrote, `call_logs_by_correlation.py --rows` output and the gateway owner's four
sanitized read-backs. The integrity phase and the `ids` command need only the standard library.

- Integrity gate. Every check below that fails is an integrity problem. Any integrity problem voids the run: the
  report has status "invalid" and decision.result "invalid", no statistic is computed, and the command writes
  --out and exits 2. Counts such as unmatched error calls or filings left out of the effort tests are reported,
  never problems.
- Frozen schedule. Both arms of one filing and repeat share a testIdx, which promptfoo advances once per test and
  repeat, a test's repeats taking consecutive values, and the providers of one step take promptIdx 0 and 1 in
  config order (src/evaluator.ts:2674-2696; installed dist/src/evaluator-DlYW7Rgb.js:8612-8643). So in each run
  the filing is the frozen roster's entry testIdx // repeats (plan.json subset.runs), the repeat is testIdx % repeats
  and the arm of promptIdx p is the run's provider order. Each results file must hold every (testIdx, promptIdx)
  cell of that grid exactly once and nothing else, with the frozen promptfoo and Node versions, and each tests file
  must match its frozen sha256; each row's accession must equal the tests file's and its labels_json must parse to
  the same list. prompt_sha256 is not compared: results redact it (a string of 64 or more such characters looks
  like a secret, dist/src/logger-ChlKG5Wv.js:718-730, rule at :728). Rows of a step that hit the per-step
  deadline keep testIdx, promptIdx, the provider label and the test vars (dist/src/evaluator-DlYW7Rgb.js:
  8875-8898), and the timed-out step's own rows are skipped if they arrive later (:9137, 9216), so each cell still
  holds exactly one row.
- Redaction. A persisted row's vars are its test case's (dist/src/evalResult-yO_CeNru.js:1079), which promptfoo
  passes through its secret sanitizer (:609-615, 845). That sanitizer replaces the value of a key whose normalized
  name is in its secret set (token, session, sessionid, auth, cookie, signature, sig and others; exact names after
  lowercasing and dropping -, _ and spaces, dist/src/logger-ChlKG5Wv.js:563-642) and a secret-looking string
  (:718-730) with "[REDACTED]" (:494), and re-serializes a string that parses as a JSON array or object
  (:1049-1057). The response, output and metadata.r02 included, gets a JSON round trip (dist/src/
  evalResult-yO_CeNru.js:581-597) and header redaction under metadata.http only (:626-681, 713-721). No field this
  analysis reads has a secret name (accession, labels_json, correlation_id, the usage and rate-limit fields, the
  named scores); a read field that nonetheless holds the marker is an integrity problem, labels_json is compared
  as parsed JSON, and prompt_sha256, which is redacted, is never read from results.
- Correlation ids. Each call sends X-Correlation-Id r02-<arm key>-{{__evalId}}-{{__evalStepId}}, where
  __evalStepId is test-<testIdx>-prompt-<promptIdx>-repeat-<repeatIndex> (dist/src/evaluator-DlYW7Rgb.js:
  7599-7605). promptfoo drops these runtime vars from the persisted vars (:7606-7619), but every result row keeps
  testIdx and promptIdx (:8087-8100, 8133-8157) and the results file keeps evalId, so the sent id of every call is
  rebuilt from the frozen schedule. Where the transform ran, the gateway's X-Correlation-Id must equal it (the
  gateway keeps a caller id of 1-256 characters, OmniRoute@dd6e9607e:src/shared/utils/correlationPreserve.ts:6-12).
- Errors. transform_r02.js returns its own prefixed errors with metadata. promptfoo throws before the transform
  on a 429 when maxRetries is 0 ("Rate limit exceeded: HTTP 429" or "Quota exceeded: HTTP 429",
  src/util/fetch/index.ts:681-714, 768-770; src/util/fetch/errors.ts:164-211), on a 200 that carries a
  rate-limit-remaining 0 header ("Rate limited: ...", index.ts:375-388, 712-714) and when no response headers
  arrive within REQUEST_TIMEOUT_MS ("Request timed out after <ms> ms", dist/src/fetch-DpK1Rb6J.js:1177-1195). The
  per-step deadline PROMPTFOO_EVAL_TIMEOUT_MS ends the whole step, stream included, with "Evaluation timed out
  after <ms>ms" (dist/src/evaluator-DlYW7Rgb.js:8875-8898, 9191-9230). A timeout that names another value than the
  frozen one is an integrity problem. A failure after the gateway committed a slow-path 200 stream arrives in-band
  as a data-only error chunk (OmniRoute@dd6e9607e:open-sse/utils/earlyStreamKeepalive.ts:664-685), which the
  transform reports as sse_error_event.
- call_logs. Each call is joined on its sent id to the rows of an observed snapshot (call_logs_by_correlation.py
  re-reads until two consecutive reads at least 30 s apart agree). The snapshot is not a complete log, and
  settling is a heuristic: the gateway starts each attempt's save without awaiting it (OmniRoute@dd6e9607e:
  open-sse/handlers/chatCore/attemptLogging.ts:557-618), stamps the row after awaited lookups
  (src/lib/usage/callLogs.ts:538, 597, 602, 680) and inserts it only after an awaited artifact write (:759, 824), so
  a save can land after the last read; a save whose error is swallowed (attemptLogging.ts:618) or that is skipped
  (callLogs.ts:867) never lands. Its own drain, waitForCallLogSaves (:878-896), runs in-process and outside tests
  only from graceful shutdown (:898-910; src/lib/gracefulShutdown.ts:114, 129), so a reader of a shared, running
  gateway cannot call it. Every call_logs figure is therefore of observed rows (CALL_LOG_SCOPE, in the report):
  row counts are lower bounds, a call without a row may have rows saved late or never, and the terminal status is
  the observed one. Attempt order is not observable either, so a call's observed terminal row is taken from the
  client's own outcome, never from timestamps or insertion order. A call promptfoo graded received a complete
  stream and must have an observed success row; a call whose HTTP status the client saw (the transform's
  http_status_<code>, a thrown 429) narrows to observed rows with that status, and no such row is an integrity
  problem. For other failures the client's status says nothing about the log: a slow-path stream commits 200
  before the gateway's attempts end and then frames their error in-band (OmniRoute@dd6e9607e:
  open-sse/utils/earlyStreamKeepalive.ts:664-685), so all of the call's observed rows are candidates. The observed
  terminal row is taken only when the candidates agree on status, model and both effort columns; otherwise it is
  unknown, an integrity problem. A graded call with no observed row is an integrity problem, so a late or lost save
  can void a run but cannot change a verdict; an error call with no observed row is counted by client-side outcome.
- Scores. li26's own eval_arm.parse_items and analyze.filing_scores rescore every returned output; the python
  assertion's namedScores must agree. A call without output scores as filing_scores(gold, None), li26's rule for a
  call that returned nothing usable.
- Strict-schema validity is promptfoo's own is-json assertion with the exact schema sent in response_format
  (dist/src/evaluator-DlYW7Rgb.js:2509-2545, the whole output through JSON.parse and ajv; its result is kept per row
  in gradingResult.componentResults, :1335-1338, 1371-1392). It keeps the default weight because a weight of 0 turns
  its pass into true (:5790-5793); this analysis reads its pass. Its schema must hash to plan.json
  request.schema_sha256. li26's parse status (valid, fenced_valid, invalid) stays the scoring rule and is reported
  beside it.
- Quality. Per filing, TP/FP/FN are summed over repeats; micro-F1 comes from the summed counts (li26
  analyze.micro_f1), never from an average of filing F1. The difference is B - A, B being cx/gpt-6-astra-max.
- Cost. One paired per-filing estimand: per filing each arm's mean over its repeats, then the mean over the frozen
  filings. It is supported only when every call in both arms returned usage; otherwise the cost leg is
  unsupported, keep_medium cannot be reached, and the calls without usage are counted. Usage comes from the
  provider's own fields in metadata.r02.usage, not promptfoo's tokenUsage.cached, which counts promptfoo's cache
  hits (src/providers/openai/util.ts:998-1044). completion_tokens is reasoning plus output; the gateway writes
  completion_tokens_details and prompt_tokens_details only when their counts are above 0 (OmniRoute@dd6e9607e:
  open-sse/translator/response/openai-responses.ts:1403-1419), so on a call that returned usage an absent detail
  is 0.
- Time to response headers. promptfoo's latencyMs for this provider is the time until the response headers
  arrived: fetchWithCache stops its clock before reading the body (dist/src/cache-CwCWVUtJ.js:422-432, 535-545),
  the HTTP provider keeps it (dist/src/providers-BUaNtf-O.js:12932-12934, 13132-13136) and the row takes the
  provider's value (dist/src/evaluator-DlYW7Rgb.js:7836). It is reported only for calls that reached the
  transform: a thrown provider error keeps 0 (:8036, 8075, 8150) and a deadline row the deadline (:8893).
  Whole-call duration is not recorded.
- Statistics (scipy 1.18.1, scipy/stats/_resampling.py): bootstrap at :300 with paired=True, the filing as the
  resampling unit, method="percentile", alternative="greater" and confidence_level=0.95, so the lower end is
  the 5th percentile and the upper end is +inf (:651-683), n_resamples=10000 and a seeded numpy Generator as
  rng; permutation_test at :1679 with permutation_type="samples" as the secondary check. Each filing's two
  arms are rows of one count table and the samples carry those row indices, which stay integers (:202,
  :225-230, :1570-1604), so resampling or swapping a filing moves both arms' counts together. The analysis
  environment is pinned in plan.json analysis_environment and checked here; a mismatch is an integrity problem.
- Holm (statsmodels 0.15.0 statsmodels/stats/multitest.py:99, multipletests(method="holm")) applies only to a
  family of roles; R02 has one role, so it is recorded as not applied.
- Effective effort. The primary measure is the client-observed reasoning_tokens per call; completion_tokens
  is a second view. Both use the same paired filing bootstrap and permutation test, one-sided for B above A.
  A zero on one call is not a defect (about 14% of max-effort turns return 0 reasoning tokens as model
  behaviour, as relayed by the coordinator from token-save-practice-gpt6, 2026-09-27; not measured here).
  call_logs effort columns are a secondary check: they are filled only when the response carried encrypted
  reasoning (OmniRoute@dd6e9607e:src/lib/usage/callLogs.ts:646-653), so a NULL is no observation.
- Gateway fingerprint. Every gateway read that exposes the build or the effort-relevant settings needs a
  credential, so the gateway owner performs it before and after each run half and returns a sanitized read-back
  with exactly the top-level keys in plan.json gateway_fingerprint.fields. Every field's value must equal one of
  the values plan.json gateway_fingerprint.admissible lists for it, with JSON Schema enum semantics (JSON Schema
  Validation 2020-12, section 6.1.2; equality as python-jsonschema 4.26.0 implements it in jsonschema/_utils.py:
  106-153, used by jsonschema/_keywords.py:269-271): four identical read-backs that all show, for example, a rule
  forcing max effort or compression on are not admissible, so both arms cannot silently run the wrong treatment.
  The code holds no admissible value; another study declares its own in its plan. This command hashes each read-
  back (canonical JSON) and treats a missing read-back, another key set, a value outside the declaration, a
  declaration that does not give each field a non-empty list and, as a supplementary check, any difference between
  the four as an integrity problem. Problems name the read-back and field, never the value. `analyze_r02.py
  readback FILE` checks one read-back against the declaration, for the owner's dry read-back before freezing.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import platform
import re
import statistics
import sys

HERE = Path(__file__).resolve().parent
LI26 = HERE.parent / "local-inference-latest-20260926"
PLAN = HERE / "plan.json"
ARM_LABELS = {"r02-A": "A", "r02-B": "B"}
ARM_KEYS = {"A": "a", "B": "b"}  # build_r02.ARMS key prefixes
ORDERS = {"ab": ("A", "B"), "ba": ("B", "A")}  # build_r02.ORDERS: the provider order of each run
ERROR = 2
TRANSFORM_ERRORS = ("sse_error_event", "malformed_sse_chunks", "missing_terminal_chunk", "missing_usage",
                    "not_an_sse_stream")
DEADLINE_TEXT = re.compile(r"Evaluation timed out after (\d+)ms")  # dist/src/evaluator-DlYW7Rgb.js:8888, 9221
HEADERS_TIMEOUT_TEXT = re.compile(r"Request timed out after (\d+) ms")  # dist/src/fetch-DpK1Rb6J.js:1183
USAGE_KEYS = ("prompt", "completion", "reasoning", "cached", "visible_output", "uncached_input")
TERMINAL_KEYS = ("status", "model", "reasoning_effort_requested", "reasoning_effort_upstream")
READBACK_POINTS = ("ab_before", "ab_after", "ba_before", "ba_after")
REDACTED = "[REDACTED]"  # promptfoo's sanitizer marker, dist/src/logger-ChlKG5Wv.js:494
READ_VARS = ("accession", "labels_json")  # the test vars this analysis reads from a results file
MIN_SETTLE_SECONDS = 30  # the preregistered re-read interval; a heuristic, not a bound on save latency
CALL_LOG_SCOPE = ("observed snapshot: rows saved after the last read or never saved are not in it, so row counts "
                  "are lower bounds, a call without a row may have unsaved rows, and a terminal status is the one "
                  "the observed rows agree on (plan.json correlation.snapshot)")
SEED = 20260927
RESAMPLES = 10000
CONFIDENCE = 0.95
MARGIN = 0.02
ROLES = ("fw-chat-completions",)
EXIT_INVALID = 2
RULE = ("invalid if any integrity check fails; otherwise adopt_max if the one-sided 95% lower bound of "
        "micro-F1(B) - micro-F1(A) is above 0; otherwise keep_medium if the lower bound of micro-F1(A) - "
        "micro-F1(B) is at least -0.02 and the cost leg is supported and A's paired per-filing mean completion "
        "(reasoning plus output) tokens are below B's; otherwise inconclusive, and B is not adopted")

_ANALYZE = []


def li26():
    """li26's analyze.py, which loads its eval_arm.py (analyze.py:27-29)."""
    if not _ANALYZE:
        spec = importlib.util.spec_from_file_location("r02_analysis_li26_analyze", LI26 / "analyze.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _ANALYZE.append(module)
    return _ANALYZE[0]


def canonical(value):
    """build_r02.canonical: sorted keys, no spaces."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def frozen_spec(plan=None):
    """The frozen sample, versions and deadlines the analysis enforces, from plan.json."""
    plan = json.loads(PLAN.read_text()) if plan is None else plan
    subset, environment = plan["subset"], plan["run"]["environment"]
    return {"repeats": plan["repeats"],
            "rosters": {run: list(subset["runs"][run]) for run in ORDERS},
            "tests_files": {run: dict(subset["tests_files"][run]) for run in ORDERS},
            "schema_sha256": plan["request"]["schema_sha256"],
            "promptfoo_version": plan["promptfoo_build"]["version"],
            "node_version": plan["promptfoo_build"]["node"],
            "call_deadline_ms": int(environment["PROMPTFOO_EVAL_TIMEOUT_MS"]),
            "request_timeout_ms": int(environment["REQUEST_TIMEOUT_MS"]),
            "environment": dict(plan["analysis_environment"]["versions"]),
            "gateway_fields": sorted(plan["gateway_fingerprint"]["fields"]),
            "gateway_admissible": plan["gateway_fingerprint"].get("admissible")}


def result_rows(data):
    return data["results"]["results"]


def redacted_paths(value, path):
    """The paths under `value` whose value is promptfoo's redaction marker."""
    if value == REDACTED:
        return [path]
    if isinstance(value, dict):
        return [found for key, item in value.items() for found in redacted_paths(item, f"{path}.{key}")]
    if isinstance(value, list):
        return [found for index, item in enumerate(value) for found in redacted_paths(item, f"{path}[{index}]")]
    return []


def label_list(value):
    """A labels_json value as a list, or None when it is not JSON text of a list. The comparison is by value:
    promptfoo persists a var whose text parses as a JSON array or object re-serialized with JSON.stringify
    (dist/src/logger-ChlKG5Wv.js:1049-1057), so '["2.02", "9.01"]' comes back as '["2.02","9.01"]'."""
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, list) else None


def r02_metadata(row):
    response = row.get("response") or {}
    return (response.get("metadata") or {}).get("r02") or (row.get("metadata") or {}).get("r02") or {}


def sent_id(arm, eval_id, test_idx, prompt_idx, repeat):
    """The X-Correlation-Id (and Idempotency-Key) promptfoo rendered for one call."""
    return f"r02-{ARM_KEYS[arm]}-{eval_id}-test-{test_idx}-prompt-{prompt_idx}-repeat-{repeat}"


# --- integrity: frozen inputs and schedule --------------------------------------------------------------------

def tests_file_problems(raw, run, frozen):
    """The run's private tests file as parsed tests, and its problems: missing, another sha256 than the frozen one,
    or a roster other than the frozen one."""
    record = frozen["tests_files"][run]
    if raw is None:
        return None, [f"{run}: the private tests file {record['name']} is missing"]
    if hashlib.sha256(raw).hexdigest() != record["sha256"]:
        return None, [f"{run}: {record['name']} differs from its frozen sha256"]
    tests = [json.loads(line) for line in raw.decode().splitlines()]
    if [test["vars"]["accession"] for test in tests] != frozen["rosters"][run]:
        return None, [f"{run}: {record['name']} does not hold the frozen roster in order"]
    return tests, []


def expected_cells(run, frozen):
    """Every (testIdx, promptIdx) the frozen schedule sends in one run, with its filing index and arm."""
    repeats = frozen["repeats"]
    return {(test * repeats + repeat, column): (test, arm)
            for test in range(len(frozen["rosters"][run])) for repeat in range(repeats)
            for column, arm in enumerate(ORDERS[run])}


def schedule_problems(data, run, frozen, tests=None):
    """Problems of one results file against the frozen schedule: evalId, promptfoo and Node versions, and every
    cell of the step grid exactly once with the frozen arm, filing and (given the tests file) labels."""
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, dict) or not isinstance(results.get("results"), list):
        return [f"{run}: not a promptfoo results file with results.results"]
    problems = []
    eval_id = data.get("evalId")
    if not isinstance(eval_id, str) or not eval_id:
        problems.append(f"{run}: no evalId, so the sent correlation ids cannot be rebuilt")
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    if metadata.get("promptfooVersion") != frozen["promptfoo_version"]:
        problems.append(f"{run}: results were not written by promptfoo {frozen['promptfoo_version']}")
    if metadata.get("nodeVersion") != frozen["node_version"]:
        problems.append(f"{run}: results were not written under Node {frozen['node_version']}")
    roster, expected = frozen["rosters"][run], expected_cells(run, frozen)
    usable_tests = tests if tests is not None and len(tests) == len(roster) else None
    seen = Counter()
    for row in result_rows(data):
        cell = (row.get("testIdx"), row.get("promptIdx")) if isinstance(row, dict) else (None, None)
        seen[cell] += 1
        if cell not in expected:
            problems.append(f"{run}: a row outside the frozen step schedule")
            continue
        test, arm = expected[cell]
        if (row.get("provider") or {}).get("label") != f"r02-{arm}":
            problems.append(f"{run}: testIdx {cell[0]} promptIdx {cell[1]} is not arm {arm}")
        variables = row.get("vars") or {}
        if redacted_paths({name: variables.get(name) for name in READ_VARS}, "vars"):
            problems.append(f"{run}: promptfoo redacted a test var this analysis reads (accession or labels_json)")
        if variables.get("accession") != roster[test]:
            problems.append(f"{run}: testIdx {cell[0]} is not frozen filing {test + 1} of the roster")
        elif usable_tests is not None and \
                label_list(variables.get("labels_json")) != label_list(usable_tests[test]["vars"]["labels_json"]):
            problems.append(f"{run}: testIdx {cell[0]} labels differ from the frozen tests file")
    missing = sum(seen[cell] == 0 for cell in expected)
    duplicated = sum(count > 1 for cell, count in seen.items() if cell in expected)
    if missing:
        problems.append(f"{run}: {missing} of {len(expected)} scheduled calls are missing")
    if duplicated:
        problems.append(f"{run}: {duplicated} scheduled calls appear more than once")
    return sorted(set(problems))


def input_problems(results_by_run, tests_raw_by_run, frozen):
    """Tests files and schedules of both runs; returns the parsed tests by run and the problems."""
    problems, tests_by_run = [], {}
    rosters = [frozen["rosters"][run] for run in ORDERS]
    if len(set(rosters[0]) | set(rosters[1])) != len(rosters[0]) + len(rosters[1]):
        problems.append("the frozen rosters overlap")
    for run in ORDERS:
        tests, found = tests_file_problems(tests_raw_by_run.get(run), run, frozen)
        tests_by_run[run] = tests
        problems += found
        problems += schedule_problems(results_by_run.get(run), run, frozen, tests)
    return tests_by_run, problems


def environment_problems(required, versions):
    """The analysis environment against plan.json analysis_environment: Python by major.minor, the packages
    exactly."""
    problems = []
    python = versions.get("python") or ""
    if python != required["python"] and not python.startswith(required["python"] + "."):
        problems.append(f"Python {python or 'unknown'} is not the frozen {required['python']}")
    for name in ("numpy", "scipy", "statsmodels"):
        if versions.get(name) != required[name]:
            problems.append(f"{name} {versions.get(name) or 'missing'} is not the frozen {required[name]}")
    return problems


def json_equal(one, two):
    """JSON Schema instance equality (JSON Schema Core 2020-12, section 4.2.2), ported from python-jsonschema
    4.26.0's equal, _sequence_equal, _mapping_equal and unbool (jsonschema/_utils.py:106-153), which its enum
    keyword uses (jsonschema/_keywords.py:269-271): a boolean equals only the same boolean, never 1 or 0; other
    numbers compare by value, so 600000 equals 600000.0; arrays compare item by item in order, objects by their keys
    and values."""
    if isinstance(one, str) or isinstance(two, str):
        return one == two
    if isinstance(one, list) and isinstance(two, list):
        return len(one) == len(two) and all(json_equal(first, second) for first, second in zip(one, two))
    if isinstance(one, dict) and isinstance(two, dict):
        return len(one) == len(two) and all(key in two and json_equal(value, two[key]) for key, value in one.items())
    if isinstance(one, bool) or isinstance(two, bool):
        return one is two
    return one == two


def admissible_problems(fields, admissible):
    """The declaration's own problems: plan.json gateway_fingerprint.admissible must list, for exactly the declared
    fields, a non-empty list of admissible values each."""
    if isinstance(admissible, dict) and sorted(admissible) == sorted(fields) and \
            all(isinstance(values, list) and values for values in admissible.values()):
        return []
    return ["plan.json gateway_fingerprint.admissible does not give each gateway field a non-empty list of "
            "admissible values"]


def readback_problems(point, value, fields, admissible=None):
    """One sanitized read-back: a JSON object with exactly the declared fields and, given the declaration, every
    field's value equal (json_equal) to one of its admissible values, as a JSON Schema enum. Problems name the
    read-back and the field, never the value."""
    if not isinstance(value, dict):
        return [f"gateway read-back {point} is missing or not a JSON object"]
    if sorted(value) != sorted(fields):
        return [f"gateway read-back {point} does not have exactly the allowlisted top-level keys"]
    if admissible is None:
        return []
    return [f"gateway read-back {point}: {field} is not an admissible value" for field in sorted(fields)
            if not any(json_equal(value[field], allowed) for allowed in admissible[field])]


def gateway_fingerprint(readbacks, fields, admissible):
    """The gateway owner's four sanitized read-backs against plan.json gateway_fingerprint: the sha256 (canonical
    JSON) of each, whether all are admissible and identical, and the problems. A missing read-back, other top-level
    keys, a value outside the declaration (readback_problems) and a broken declaration (admissible_problems) are
    problems; so is, as a supplementary check, any difference between the four. The admissible values are data from
    the plan, so identical read-backs of the wrong treatment fail here."""
    problems = admissible_problems(fields, admissible)
    declared = None if problems else admissible
    digests, value_problems = {}, []
    readbacks = readbacks if isinstance(readbacks, dict) else {}
    for point in READBACK_POINTS:
        value = readbacks.get(point)
        found = readback_problems(point, value, fields, declared)
        if isinstance(value, dict) and sorted(value) == sorted(fields):
            digests[point] = sha256_text(canonical(value))
            value_problems += found
        else:
            problems += found
    problems += value_problems
    if len(set(digests.values())) > 1:
        problems.append("the gateway read-backs differ between the points of the run")
    complete = len(digests) == len(READBACK_POINTS)
    return {"sha256": digests, "admissible": complete and declared is not None and not value_problems,
            "identical": complete and len(set(digests.values())) == 1}, problems


# --- calls ----------------------------------------------------------------------------------------------------

def error_kind(row):
    """None for a graded call; otherwise the class of the provider error."""
    if row.get("failureReason") != ERROR:
        return None
    message = row.get("error") or ""
    if message.startswith("http_status_"):
        return "http_" + message[len("http_status_"):].split(":", 1)[0]
    for prefix in TRANSFORM_ERRORS:
        if message.startswith(prefix):
            return prefix
    if message.startswith("Evaluation timed out after"):
        return "call_deadline"
    if "HTTP 429" in message:
        return "http_429"
    if "Rate limited: " in message:
        return "rate_limit_header"
    if "Request timed out after" in message:
        return "headers_timeout"
    return "other"


def timeout_problems(row, kind, frozen):
    """A deadline error that names another value than the frozen one."""
    checks = {"call_deadline": (DEADLINE_TEXT, frozen["call_deadline_ms"], "PROMPTFOO_EVAL_TIMEOUT_MS"),
              "headers_timeout": (HEADERS_TIMEOUT_TEXT, frozen["request_timeout_ms"], "REQUEST_TIMEOUT_MS")}
    if kind not in checks:
        return []
    pattern, value, name = checks[kind]
    match = pattern.search(row.get("error") or "")
    return [] if match and int(match[1]) == value else [f"a timeout other than the frozen {name}={value}"]


def schema_assertion(row, schema_sha256):
    """(passed, problem) of the row's is-json assertion, which checks the output against the schema sent."""
    components = [component for component in ((row.get("gradingResult") or {}).get("componentResults") or [])
                  if isinstance(component, dict) and (component.get("assertion") or {}).get("type") == "is-json"]
    if len(components) != 1:
        return False, "the is-json schema assertion result is missing"
    if sha256_text(canonical(components[0]["assertion"].get("value"))) != schema_sha256:
        return False, "the is-json assertion's schema differs from the schema sent"
    return components[0].get("pass") is True, None


def finite(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def usage_fields(usage):
    """Token fields of one call; every field is None when the call returned no usage."""
    if not isinstance(usage, dict):
        return {**dict.fromkeys(USAGE_KEYS), "reasoning_reported": False, "cached_reported": False}
    prompt = finite(usage.get("prompt_tokens"))
    completion = finite(usage.get("completion_tokens"))
    reported_reasoning = finite((usage.get("completion_tokens_details") or {}).get("reasoning_tokens"))
    reported_cached = finite((usage.get("prompt_tokens_details") or {}).get("cached_tokens"))
    reasoning = 0 if reported_reasoning is None else reported_reasoning
    cached = 0 if reported_cached is None else reported_cached
    return {"prompt": prompt, "completion": completion, "reasoning": reasoning, "cached": cached,
            "visible_output": None if completion is None else completion - reasoning,
            "uncached_input": None if prompt is None else prompt - cached,
            "reasoning_reported": reported_reasoning is not None, "cached_reported": reported_cached is not None}


def call_record(row, run, eval_id, frozen):
    """One call of a validated results file: arm, filing, repeat, counts from li26's rescoring, the is-json result,
    status, tokens, time to response headers, the sent correlation id, the gateway's echo of it, the rate-limit
    headers the transform saw, and the call's integrity problems."""
    analyze = li26()
    arm = ARM_LABELS[row["provider"]["label"]]
    variables = row["vars"]
    gold = json.loads(variables["labels_json"])
    kind = error_kind(row)
    response = row.get("response") or {}
    meta = r02_metadata(row)
    problems, schema_valid = [], False
    problems += [f"promptfoo redacted {path}, which this analysis reads" for path in redacted_paths(
        {"r02": meta, "namedScores": row.get("namedScores") or {}}, "row")]
    if kind is None:
        predicted, status = analyze.eval_arm.parse_items(response.get("output"))
        scores = analyze.filing_scores(gold, predicted)
        named = row.get("namedScores") or {}
        if (named.get("tp"), named.get("fp"), named.get("fn")) != (scores["tp"], scores["fp"], scores["fn"]) or \
                named.get(f"status_{status}") != 1:
            problems.append("assertion scores differ from li26 rescoring")
        if named.get("prompt_ok") != 1:
            problems.append("prompt differs from the recorded li26 prompt")
        schema_valid, problem = schema_assertion(row, frozen["schema_sha256"])
        if problem:
            problems.append(problem)
    else:
        status = "error"
        scores = analyze.filing_scores(gold, None)
        problems += timeout_problems(row, kind, frozen)
    identifier = sent_id(arm, eval_id, row["testIdx"], row["promptIdx"], row["testIdx"] % frozen["repeats"])
    echoed = meta.get("correlation_id")
    if echoed and echoed != identifier:
        problems.append("the gateway's X-Correlation-Id differs from the sent id")
    return {"run": run, "arm": arm, "test_idx": row["testIdx"], "repeat": row["testIdx"] % frozen["repeats"],
            "accession": variables["accession"], "tp": scores["tp"], "fp": scores["fp"], "fn": scores["fn"],
            "status": status, "schema_valid": schema_valid, "error_kind": kind,
            "time_to_headers_ms": finite(row.get("latencyMs")) if meta else None,
            "usage": usage_fields(meta.get("usage")), "sent_id": identifier, "correlation_id": echoed,
            "rate_limit_headers": sorted(meta.get("rate_limit_headers") or {}),
            "dropped_upstream_headers": meta.get("dropped_upstream_headers"), "problems": problems}


def run_calls(data, run, frozen):
    """call_record for every row of one validated results file."""
    return [call_record(row, run, data["evalId"], frozen) for row in result_rows(data)]


def pair_calls(runs):
    """Pair A and B on (run, testIdx) of validated results, in schedule order."""
    pairs = []
    for run, calls in runs.items():
        by_step = {}
        for call in calls:
            by_step.setdefault(call["test_idx"], {})[call["arm"]] = call
        for step in sorted(by_step):
            slot = by_step[step]
            pairs.append({"run": run, "accession": slot["A"]["accession"], "repeat": slot["A"]["repeat"],
                          "A": slot["A"], "B": slot["B"]})
    return pairs


def correlation_summary(calls):
    """Sent ids per arm, the gateway's echoes of them, and the problems: echoes that differ, repeated ids."""
    report = {arm: {"calls": sum(call["arm"] == arm for call in calls),
                    "sent_ids": sum(call["arm"] == arm and call["sent_id"] is not None for call in calls),
                    "echoed": sum(call["arm"] == arm and call["correlation_id"] is not None for call in calls),
                    "echo_mismatch": sum(call["arm"] == arm and call["correlation_id"] is not None and
                                         call["correlation_id"] != call["sent_id"] for call in calls)}
              for arm in ("A", "B")}
    counts = Counter(call["sent_id"] for call in calls if call["sent_id"])
    problems = [f"sent correlation id used by {count} calls" for count in sorted(
        count for count in counts.values() if count > 1)]
    return report, problems


# --- call_logs ------------------------------------------------------------------------------------------------

def client_outcome(call):
    return call["error_kind"] or "no_provider_error"


def client_status(call):
    """What the client's own outcome fixes about the terminal status: "success" for a graded call, the code of a
    transform http_status_<code> error (a non-200 response, transform_r02.js:158-160) or of a thrown 429, and
    None otherwise. A transform stream error, a rate_limit_header failure, a timeout or another thrown error fix
    nothing: a slow-path stream commits 200 before the gateway's attempts end."""
    kind = call["error_kind"]
    if kind is None:
        return "success"
    if kind.startswith("http_") and kind[len("http_"):].isdigit():
        return int(kind[len("http_"):])
    return None


def terminal_row(call, rows):
    """(row, None) with the call's observed terminal call_logs row, or (None, reason) when it is not determined.
    `rows` are the call's rows in the observed snapshot; a row saved late or never is not among them. Attempt order
    is never inferred from timestamps or insertion order."""
    status = client_status(call)
    if status == "success":
        candidates = [row for row in rows if isinstance(row.get("status"), int) and 200 <= row["status"] < 300]
        if not candidates:
            return None, "promptfoo graded this call but none of its observed call_logs rows is a success"
    elif status is not None:
        candidates = [row for row in rows if row.get("status") == status]
        if not candidates:
            return None, f"the client received HTTP {status} but none of the call's observed call_logs rows has it"
    else:
        candidates = list(rows)
    if len({tuple(row.get(key) for key in TERMINAL_KEYS) for row in candidates}) != 1:
        return None, ("terminal call_logs status unknown: the observed candidate rows disagree and attempt order is "
                      "not known")
    return candidates[0], None


def call_log_rows(call_logs):
    """Rows per correlation id from `call_logs_by_correlation.py --rows` output, the snapshot record and the
    problems: a snapshot that did not settle or settled on too short an interval, or output without rows."""
    problems = []
    snapshot = call_logs.get("snapshot") if isinstance(call_logs, dict) else None
    if not isinstance(snapshot, dict) or snapshot.get("settled") is not True:
        problems.append("the call_logs snapshot did not settle")
    elif finite(snapshot.get("interval_seconds")) is None or snapshot["interval_seconds"] < MIN_SETTLE_SECONDS:
        problems.append(f"the call_logs snapshot settled over less than {MIN_SETTLE_SECONDS} s")
    arms = call_logs.get("arms") if isinstance(call_logs, dict) else None
    if not isinstance(arms, dict) or not all(isinstance(entry, dict) and isinstance(entry.get("matched_rows"), list)
                                             for entry in arms.values()):
        problems.append("the call_logs output has no matched rows (use call_logs_by_correlation.py --rows)")
        arms = {}
    rows = {}
    for entry in arms.values():
        for row in entry["matched_rows"]:
            rows.setdefault(row.get("correlation_id"), []).append(row)
    return rows, snapshot, problems


def call_log_summary(call_logs, calls):
    """Per arm, each call joined on its sent correlation id to the rows of the observed snapshot, its observed
    terminal row taken from the client's outcome (terminal_row). Every figure is of observed rows (CALL_LOG_SCOPE):
    rows per call and 429 rows count all observed rows and are lower bounds. A NULL effort column is no
    observation, never "no effort". Returns the report and its problems."""
    rows, snapshot, problems = call_log_rows(call_logs)
    report = {"scope": CALL_LOG_SCOPE, "snapshot": snapshot}
    for arm in ("A", "B"):
        arm_calls = [call for call in calls if call["arm"] == arm]
        terminals, unmatched, all_rows, row_counts = [], [], [], []
        for call in arm_calls:
            matched = rows.get(call["sent_id"], [])
            if not matched:
                if call["error_kind"] is None:
                    problems.append(f"{arm} {call['sent_id']}: promptfoo graded this call but the call_logs "
                                    "snapshot has no row for it (none written, or saved late or never)")
                unmatched.append(call)
                continue
            all_rows += matched
            row_counts.append(len(matched))
            terminal, reason = terminal_row(call, matched)
            if terminal is None:
                problems.append(f"{arm} {call['sent_id']}: {reason}")
                continue
            terminals.append((call, terminal))
        report[arm] = {
            "calls": len(arm_calls),
            "calls_matched": len(arm_calls) - len(unmatched),
            "calls_unmatched": len(unmatched),
            "unmatched_by_client_outcome": dict(sorted(Counter(client_outcome(call) for call in unmatched).items())),
            "rows": len(all_rows),
            "rows_per_call": dict(sorted(Counter(row_counts).items())),
            "calls_with_several_rows": sum(count > 1 for count in row_counts),
            "observed_terminal_status": dict(sorted(Counter(str(row["status"]) for _, row in terminals).items())),
            "row_status": dict(sorted(Counter(str(row.get("status")) for row in all_rows).items())),
            "http_429_rows": sum(row.get("status") == 429 for row in all_rows),
            "http_429_observed_terminal": sum(row["status"] == 429 for _, row in terminals),
            "client_outcome_by_observed_terminal_status": [
                {"client": client, "observed_terminal_status": status, "count": count}
                for (client, status), count in sorted(Counter(
                    [(client_outcome(call), str(row["status"])) for call, row in terminals] +
                    [(client_outcome(call), "no_row") for call in unmatched]).items())],
            "model": dict(sorted(Counter(str(row["model"]) for _, row in terminals).items())),
            "effort_observed": {
                column: dict(sorted(Counter(row[f"reasoning_effort_{column}"] for _, row in terminals
                                            if row[f"reasoning_effort_{column}"] is not None).items()))
                for column in ("requested", "upstream")},
            "effort_not_observed_calls": {
                column: sum(row[f"reasoning_effort_{column}"] is None for _, row in terminals)
                for column in ("requested", "upstream")},
        }
    return report, problems


# --- decision -------------------------------------------------------------------------------------------------

def cost_leg(pairs, key="completion"):
    """The paired per-filing cost of one usage field: per filing, each arm's mean over its repeats, then the mean
    over filings. Supported only when every call in both arms returned the field; otherwise no mean is given."""
    missing = {"A": 0, "B": 0}
    values = {}
    for pair in pairs:
        for arm in ("A", "B"):
            value = pair[arm]["usage"][key]
            if value is None:
                missing[arm] += 1
            else:
                values.setdefault(pair["accession"], {"A": [], "B": []})[arm].append(value)
    record = {"estimand": "mean over filings of each arm's per-filing mean over repeats", "field": key,
              "calls": {arm: len(pairs) for arm in ("A", "B")}, "calls_without_usage": missing,
              "filings": len({pair["accession"] for pair in pairs})}
    if not pairs or missing["A"] or missing["B"]:
        return {**record, "supported": False, "A": None, "B": None}
    filings = sorted(values)
    return {**record, "supported": True,
            **{arm: statistics.fmean(statistics.fmean(values[filing][arm]) for filing in filings)
               for arm in ("A", "B")}}


def decide(lower_b_minus_a, lower_a_minus_b, cost, margin=MARGIN):
    """The preregistered rule (RULE) for a valid run; cost is cost_leg(pairs, "completion")."""
    if lower_b_minus_a > 0:
        return "adopt_max"
    if lower_a_minus_b >= -margin and cost["supported"] and cost["A"] < cost["B"]:
        return "keep_medium"
    return "inconclusive"


def filing_table(pairs):
    """Per filing, TP/FP/FN summed over repeats, for each arm, in accession order."""
    filings = sorted({pair["accession"] for pair in pairs})
    sums = {accession: {"A": [0, 0, 0], "B": [0, 0, 0]} for accession in filings}
    for pair in pairs:
        for arm in ("A", "B"):
            for index, key in enumerate(("tp", "fp", "fn")):
                sums[pair["accession"]][arm][index] += pair[arm][key]
    return filings, [sums[accession]["A"] for accession in filings], [sums[accession]["B"] for accession in filings]


def filing_means(pairs, key):
    """Per filing, each arm's mean of a usage field over the repeats that returned usage; filings where an arm
    has no such repeat are left out and counted."""
    values = {}
    for pair in pairs:
        for arm in ("A", "B"):
            value = pair[arm]["usage"][key]
            if value is not None:
                values.setdefault(pair["accession"], {"A": [], "B": []})[arm].append(value)
    filings = sorted(accession for accession, arms in values.items() if arms["A"] and arms["B"])
    left_out = len({pair["accession"] for pair in pairs}) - len(filings)
    return ([statistics.fmean(values[accession]["A"]) for accession in filings],
            [statistics.fmean(values[accession]["B"]) for accession in filings], left_out)


def micro_f1(counts):
    """li26's micro-F1 from summed counts (analyze.micro_f1)."""
    return li26().micro_f1([tuple(row) for row in counts])


def mean(values):
    values = [value for value in values if value is not None]
    return statistics.fmean(values) if values else None


def distribution(values, np):
    values = [value for value in values if value is not None]
    if not values:
        return {"n": 0}
    return {"n": len(values), "mean": statistics.fmean(values), "median": float(np.median(values)),
            "p95": float(np.percentile(values, 95, method="linear")),
            "zero_share": sum(value == 0 for value in values) / len(values)}


def arm_summary(calls, np):
    headers = [call["time_to_headers_ms"] for call in calls if call["time_to_headers_ms"] is not None]
    usage = [call["usage"] for call in calls]
    returned = [entry for entry in usage if entry["prompt"] is not None]
    prompt_total = sum(entry["prompt"] for entry in returned)
    errors = Counter(call["error_kind"] for call in calls if call["error_kind"])
    return {
        "calls": len(calls),
        "li26_status": dict(sorted(Counter(call["status"] for call in calls).items())),
        "strict_schema_validity": sum(call["schema_valid"] for call in calls) / len(calls) if calls else None,
        "errors": dict(sorted(errors.items())),
        "timeouts": {"headers": errors.get("headers_timeout", 0), "call_deadline": errors.get("call_deadline", 0)},
        "http_429_client": errors.get("http_429", 0),
        "time_to_response_headers_ms": {
            "p50": float(np.percentile(headers, 50, method="linear")) if headers else None,
            "p95": float(np.percentile(headers, 95, method="linear")) if headers else None,
            "n": len(headers), "scope": "calls that reached the transform"},
        "tokens_per_call_with_usage": {key: mean(entry[key] for entry in usage) for key in USAGE_KEYS},
        "calls_with_usage": len(returned),
        "calls_with_details": {"reasoning_tokens": sum(entry["reasoning_reported"] for entry in usage),
                               "cached_tokens": sum(entry["cached_reported"] for entry in usage)},
        "cached_input_share": sum(entry["cached"] for entry in returned) / prompt_total if prompt_total else None,
        "reasoning_tokens": distribution([entry["reasoning"] for entry in usage], np),
        "completion_tokens": distribution([entry["completion"] for entry in usage], np),
        # Open question 3: rate-limit-class response headers on calls that reached the transform.
        "rate_limit_headers": {"calls_with_any": sum(bool(call["rate_limit_headers"]) for call in calls),
                               "names": dict(sorted(Counter(name for call in calls
                                                            for name in call["rate_limit_headers"]).items()))},
        "calls_with_dropped_upstream_headers": sum(call["dropped_upstream_headers"] is not None for call in calls),
    }


def paired_tests(sample_a, sample_b, statistic, np, stats):
    """The preregistered paired bootstrap (both one-sided bounds) and the samples permutation test."""
    settings = {"paired": True, "vectorized": True, "n_resamples": RESAMPLES, "method": "percentile",
                "confidence_level": CONFIDENCE, "alternative": "greater"}

    def reverse(first, second, axis=-1):
        return -statistic(first, second, axis=axis)

    def number(value):
        return float(value) + 0.0  # reports 0.0 rather than -0.0

    b_minus_a = stats.bootstrap((sample_a, sample_b), statistic, rng=np.random.default_rng(SEED), **settings)
    a_minus_b = stats.bootstrap((sample_a, sample_b), reverse, rng=np.random.default_rng(SEED), **settings)
    permutation = stats.permutation_test((sample_a, sample_b), statistic, permutation_type="samples",
                                         vectorized=True, n_resamples=RESAMPLES, alternative="greater",
                                         rng=np.random.default_rng(SEED))
    return {
        "b_minus_a": {"point": number(statistic(sample_a, sample_b)),
                      "lower_one_sided_95": number(b_minus_a.confidence_interval.low),
                      "standard_error": number(b_minus_a.standard_error)},
        "a_minus_b": {"point": number(reverse(sample_a, sample_b)),
                      "lower_one_sided_95": number(a_minus_b.confidence_interval.low)},
        "permutation_b_minus_a": {"statistic": number(permutation.statistic),
                                  "p_value_greater": number(permutation.pvalue)},
    }


def settings_record():
    return {"bootstrap": {"paired": True, "vectorized": True, "n_resamples": RESAMPLES, "method": "percentile",
                          "confidence_level": CONFIDENCE, "alternative": "greater",
                          "rng": f"numpy.random.default_rng({SEED})", "resampling_unit": "filing (both arms together)"},
            "permutation_test": {"permutation_type": "samples", "n_resamples": RESAMPLES, "alternative": "greater",
                                 "rng": f"numpy.random.default_rng({SEED})"}}


def quality_tests(table_a, table_b):
    import numpy as np
    from scipy import stats

    table = np.asarray(table_a + table_b, dtype=float)
    n = len(table_a)

    def f1(counts):
        tp, fp, fn = counts[..., 0], counts[..., 1], counts[..., 2]
        denominator = 2 * tp + fp + fn
        return np.where(denominator > 0, 2 * tp / np.where(denominator > 0, denominator, 1), 1.0)

    def micro_f1_difference(first, second, axis=-1):
        first = np.moveaxis(np.asarray(first), axis, -1)
        second = np.moveaxis(np.asarray(second), axis, -1)
        return f1(table[second].sum(axis=-2)) - f1(table[first].sum(axis=-2))

    return {"filings": n, **paired_tests(np.arange(n), np.arange(n, 2 * n), micro_f1_difference, np, stats),
            "settings": settings_record()}


def effort_tests(pairs):
    """Effective effort: per-filing mean tokens over repeats, B - A, for reasoning and completion tokens."""
    import numpy as np
    from scipy import stats

    def mean_difference(first, second, axis=-1):
        return np.mean(second, axis=axis) - np.mean(first, axis=axis)

    report = {"primary": "reasoning_tokens", "statistic": "mean over filings of the per-filing mean, B - A",
              "settings": settings_record()}
    for key in ("reasoning", "completion"):
        sample_a, sample_b, left_out = filing_means(pairs, key)
        entry = {"filings": len(sample_a), "filings_left_out": left_out}
        if len(sample_a) < 2:
            entry["computed"] = False
        else:
            entry.update(paired_tests(np.asarray(sample_a, dtype=float), np.asarray(sample_b, dtype=float),
                                      mean_difference, np, stats))
        report[f"{key}_tokens"] = entry
    return report


def installed(distribution_name):
    try:
        return importlib.metadata.version(distribution_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def installed_versions():
    return {"python": platform.python_version(), "numpy": installed("numpy"), "scipy": installed("scipy"),
            "statsmodels": installed("statsmodels")}


def holm(p_values):
    if len(p_values) < 2:
        return {"applied": False, "roles": len(p_values),
                "reason": "one role; Holm applies only to a family of roles"}
    from statsmodels.stats.multitest import multipletests
    reject, corrected, _, _ = multipletests(list(p_values.values()), alpha=1 - CONFIDENCE, method="holm")
    return {"applied": True, "roles": {role: {"p_holm": float(p), "reject": bool(r)}
                                       for role, p, r in zip(p_values, corrected, reject)}}


def integrity(results_by_run, tests_raw_by_run, call_logs, gateway_readbacks, frozen, versions=None):
    """The integrity phase, standard library only: the report so far, the integrity problems and the calls of each
    run (None when the inputs do not match the frozen schedule). `versions` is the analysis environment to check
    (installed_versions()); None skips that check, for synthetic tests outside the pinned environment."""
    _, problems = input_problems(results_by_run, tests_raw_by_run, frozen)
    report = {"rule": RULE, "repeats": frozen["repeats"]}
    fingerprint, fingerprint_problems = gateway_fingerprint(gateway_readbacks, frozen["gateway_fields"],
                                                            frozen["gateway_admissible"])
    report["gateway_fingerprint"] = fingerprint
    if versions is not None:
        report["versions"] = versions
        problems += environment_problems(frozen["environment"], versions)
    problems += fingerprint_problems
    runs = None
    if not any(problem.startswith(tuple(f"{run}:" for run in ORDERS)) for problem in problems):
        runs = {run: run_calls(results_by_run[run], run, frozen) for run in ORDERS}
        calls = [call for members in runs.values() for call in members]
        problems += sorted({f"{call['run']} {call['arm']} {call['accession']}: {problem}"
                            for call in calls for problem in call["problems"]})
        correlation, correlation_problems = correlation_summary(calls)
        problems += correlation_problems
        call_log_report, call_log_problems = call_log_summary(call_logs, calls)
        problems += call_log_problems
        report.update({"correlation": correlation, "call_logs": call_log_report})
    return report, problems, runs


def analyze(results_by_run, tests_raw_by_run, call_logs, gateway_readbacks, frozen=None, versions=None):
    """integrity(), then, for a valid run only, the statistics and the decision. Any integrity problem makes the
    report invalid: no statistic is computed and decision.result is "invalid"."""
    frozen = frozen_spec() if frozen is None else frozen
    report, problems, runs = integrity(results_by_run, tests_raw_by_run, call_logs, gateway_readbacks, frozen,
                                       versions)
    if problems:
        report.update({"status": "invalid", "problems": problems,
                       "decision": {"rule": RULE, "result": "invalid",
                                    "reason": "integrity checks failed; no statistic and no verdict"}})
        return report

    import numpy as np

    pairs = pair_calls(runs)
    filings, table_a, table_b = filing_table(pairs)
    tests = quality_tests(table_a, table_b)
    cost = cost_leg(pairs, "completion")
    report.update({
        "status": "analysis",
        "problems": [],
        "pairs": len(pairs), "filings": len(filings),
        "runs": {run: {"calls": len(members), "eval_id": results_by_run[run]["evalId"]}
                 for run, members in runs.items()},
        "micro_f1": {"A": micro_f1(table_a), "B": micro_f1(table_b)},
        "tests": tests,
        "holm": holm({ROLES[0]: tests["permutation_b_minus_a"]["p_value_greater"]}),
        "effort": effort_tests(pairs),
        "arms": {arm: arm_summary([pair[arm] for pair in pairs], np) for arm in ("A", "B")},
        "cost_per_filing": {key: cost_leg(pairs, key) for key in USAGE_KEYS},
        "decision": {"rule": RULE, "margin": MARGIN, "cost_leg": cost,
                     "result": decide(tests["b_minus_a"]["lower_one_sided_95"],
                                      tests["a_minus_b"]["lower_one_sided_95"], cost)},
    })
    return report


# --- command line ---------------------------------------------------------------------------------------------

def read_json(path):
    """Parsed JSON, or None when the file is missing or not JSON."""
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def read_tests(state_dir, frozen):
    raws = {}
    for run in ORDERS:
        path = Path(state_dir).expanduser() / frozen["tests_files"][run]["name"]
        raws[run] = path.read_bytes() if path.is_file() else None
    return raws


def correlation_ids(results_by_run, tests_raw_by_run, frozen=None):
    """The sent correlation id of every call per arm, rebuilt from validated results files. Refuses when the
    results or tests files do not match the frozen schedule, or when an id the gateway echoed differs from the
    rebuilt one, since call_logs would then be joined on wrong ids."""
    frozen = frozen_spec() if frozen is None else frozen
    _, problems = input_problems(results_by_run, tests_raw_by_run, frozen)
    if problems:
        raise SystemExit("refused, the inputs do not match the frozen schedule: " + "; ".join(problems))
    ids, mismatched = {"A": [], "B": []}, 0
    for run in ORDERS:
        data = results_by_run[run]
        for row in result_rows(data):
            arm = ARM_LABELS[row["provider"]["label"]]
            identifier = sent_id(arm, data["evalId"], row["testIdx"], row["promptIdx"],
                                 row["testIdx"] % frozen["repeats"])
            ids[arm].append(identifier)
            echoed = r02_metadata(row).get("correlation_id")
            mismatched += echoed is not None and echoed != identifier
    if mismatched:
        raise SystemExit(f"the gateway's X-Correlation-Id differs from the rebuilt sent id for {mismatched} calls")
    return ids


def dry_readback(value, frozen):
    """The owner's dry read-back before freezing, against the plan's declaration: (admissible, problems)."""
    problems = admissible_problems(frozen["gateway_fields"], frozen["gateway_admissible"]) or \
        readback_problems("dry-run", value, frozen["gateway_fields"], frozen["gateway_admissible"])
    return not problems, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("readback", help="one gateway read-back against plan.json gateway_fingerprint."
                                                 "admissible, for the owner's dry read-back before freezing")
    check.add_argument("readback")
    ids = commands.add_parser("ids", help="the sent correlation id of every call per arm, for "
                                          "call_logs_by_correlation.py")
    run = commands.add_parser("analyze", help="integrity checks, then paired statistics and the decision")
    for command in (ids, run):
        command.add_argument("--results-ab", required=True)
        command.add_argument("--results-ba", required=True)
        command.add_argument("--state-dir", required=True, help="directory holding the private tests files")
    run.add_argument("--call-logs", required=True)
    run.add_argument("--gateway-readbacks", nargs=4, required=True, metavar=tuple(point.upper() for point in
                                                                                READBACK_POINTS))
    run.add_argument("--out")
    args = parser.parse_args(argv)
    frozen = frozen_spec()
    if args.command == "readback":
        admissible, problems = dry_readback(read_json(args.readback), frozen)
        print(json.dumps({"admissible": admissible, "problems": problems}, indent=2))
        return 0 if admissible else EXIT_INVALID
    results = {"ab": read_json(args.results_ab), "ba": read_json(args.results_ba)}
    tests = read_tests(args.state_dir, frozen)
    if args.command == "ids":
        print(json.dumps(correlation_ids(results, tests, frozen), indent=2))
        return 0
    readbacks = {point: read_json(path) for point, path in zip(READBACK_POINTS, args.gateway_readbacks)}
    report = analyze(results, tests, read_json(args.call_logs), readbacks, frozen, installed_versions())
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text)
    print(text, end="")
    return EXIT_INVALID if report["status"] == "invalid" else 0


if __name__ == "__main__":
    sys.exit(main())
