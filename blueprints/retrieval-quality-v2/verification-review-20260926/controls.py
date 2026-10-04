"""Discriminating controls for blueprints/retrieval-quality-v2/run.py and its tests.

Each mutant reverts one repair in a copy of run.py; the named tests then run against that
copy and must fail. The same tests first run against an unmodified copy and must pass.
This is the controls tool behind repair-review-20260926.json (sha256 920ab4f0...) with the
mutants P1 to P5 added for the fixes made after the review of run.py 0792745e.
Usage: controls.py <worktree> <out-dir> <python> [mutant-name ...]
"""
import datetime
import difflib
import hashlib
import json
import pathlib
import platform
import shutil
import subprocess
import sys
import time

WT = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2])
PY = sys.argv[3]
ONLY = set(sys.argv[4:])
RUN = WT / "blueprints/retrieval-quality-v2/run.py"
TESTS = WT / "tests/test_retrieval_quality_v2.py"
SRC = RUN.read_text()
T = "tests.test_retrieval_quality_v2."

C_ENV = T + "EnvironmentIsolationTests."
C_PIN = T + "ModelPinTests."
C_VAL = T + "ResponseValidationTests."
C_TMO = T + "TimeoutTests."
C_OUT = T + "OutputTests."
C_NAT = T + "NativeRetentionTests."
C_BEN = T + "NativeBenchTests."
C_EVI = T + "CommittedRunEvidenceTests."
C_INT = T + "InterruptTests."
SIGINT_TEST = C_INT + "test_sigint_stops_an_arm_b_query_and_kills_its_process_group"
SIGTERM_TEST = C_INT + "test_sigterm_to_the_runner_and_then_its_group_like_gnu_timeout"

MUTANTS = {
    "F1-inherit-caller-env": (
        [("    env = {key: caller[key] for key in QMD_ENV_PASSTHROUGH if key in caller}\n", "    env = dict(caller)\n"),
         ('            "INDEX_PATH": str(cache_home / "qmd" / f"{index_name}.sqlite"),\n'
          '            "QMD_CONFIG_DIR": str(config_home / "qmd"),\n', "")],
        [C_ENV + "test_no_qmd_call_follows_the_callers_routing_variables",
         C_ENV + "test_env_binds_owned_storage_and_drops_caller_routing"]),
    "F2-revision-fail-open": (
        [("    if not isinstance(revision, str) or not HF_REVISION_RE.fullmatch(revision):\n        raise RunFailure(",
          "    if not isinstance(revision, str) or not HF_REVISION_RE.fullmatch(revision):\n"
          "        return {\"revision\": None, \"lfs_sha256\": None, \"lfs_size\": None}\n        raise RunFailure(")],
        [C_PIN + "test_unresolved_revision_fails_arm_b_closed"]),
    "F3-docid-unchecked": (
        [("    match = DOCID_RE.fullmatch(docid_field) if isinstance(docid_field, str) else None\n",
          "    return repository_path, \"ok\"\n    match = None\n")],
        [C_VAL + "test_docid_must_match_the_pinned_content_hash",
         C_VAL + "test_malformed_and_unverifiable_responses_score_zero_and_the_arm_continues"]),
    "F3c-unverifiable-hit-scored-as-grade-0": (
        [("                if rejected_hits:\n                    error = (", "                if False:\n                    error = (")],
        [C_VAL + "test_one_unverifiable_hit_rejects_the_whole_query"]),
    "F3b-index-content-unverified": (
        [("    pinned = {d[\"path\"]: d[\"sha256\"] for d in corpus}\n    missing =", "    pinned = dict(indexed)\n    missing =")],
        [C_ENV + "test_index_content_mismatch_aborts_before_any_arm"]),
    "F4-json-shape-unchecked": (
        [("    if not isinstance(doc, list):\n        return None,", "    if doc is None:\n        return [],\n    if False:\n        return None,"),
         ("        if not isinstance(hit, dict):\n            return None,", "        if False:\n            return None,")],
        [C_VAL + "test_malformed_and_unverifiable_responses_score_zero_and_the_arm_continues"]),
    "F5a-timeout-propagates": (
        [("            if stopping or remaining <= 0:\n",
          "            if remaining <= 0 and not stopping:\n                raise subprocess.TimeoutExpired(argv, timeout)\n"
          "            if stopping:\n")],
        [C_TMO + "test_embed_timeout_marks_arm_b_not_evaluated"]),
    "F5b-kill-launcher-only": (
        [("        os.killpg(proc.pid, signal.SIGKILL)\n", "        proc.kill()\n")],
        [C_TMO + "test_pull_timeout_marks_arm_b_not_evaluated_and_kills_the_process_group", SIGINT_TEST]),
    "F6-overwrite-outputs": (
        [("    existing = [p.name for p in outputs.values() if p.exists()]\n", "    existing = []\n"),
         ('    with open(path, "x", encoding="utf-8") as fh:\n', '    with open(path, "w", encoding="utf-8") as fh:\n')],
        [C_OUT + "test_existing_output_is_never_overwritten"]),
    "F7-no-native-retention": (
        [("        self.records.append(record)\n", "")],
        [C_NAT + "test_every_scored_query_links_to_its_retained_native_output"]),
    "evidence-receipt-hand-edited": (
        [], [C_EVI + "test_committed_receipts_rederive_from_their_native_output"]),
    "bench-audit-trusts-native": (
        [("            exact_recall5 = (sum(1 for g in gold if g in top[:5]) / len(gold)) if gold else 0.0\n",
          "            exact_recall5 = backend_result.get(\"recall_at_5\")\n")],
        [C_BEN + "test_bench_runs_on_the_same_index_with_a_derived_fixture_and_an_exact_audit"]),
    "I1-no-stop-handlers": (
        [("    def arm(self) -> None:\n        for signum in self.signals():\n",
          "    def arm(self) -> None:\n        for signum in ():\n")],
        [SIGTERM_TEST, C_INT + "test_stop_requests_record_every_signal_and_raise_only_at_a_checkpoint"]),
    "I2-stop-not-polled": (
        [("            stopping = stop is not None and stop()\n", "            stopping = False\n")],
        [SIGINT_TEST]),
    "I3-stopped-call-not-recorded": (
        [("        record, stdout, stderr = self._append(record_id, phase, argv, started_at, start, timeout, result, None)\n"
          "        if result.stopped:\n            self.checkpoint()\n",
          "        if result.stopped:\n            self.checkpoint()\n"
          "        record, stdout, stderr = self._append(record_id, phase, argv, started_at, start, timeout, result, None)\n")],
        [SIGINT_TEST]),
    "I4-group-not-killed-on-stop": (
        [("            if stopping or remaining <= 0:\n                _kill_process_group(proc)\n",
          "            if stopping or remaining <= 0:\n                if not stopping:\n                    _kill_process_group(proc)\n")],
        [SIGINT_TEST]),
    "I5-no-interrupted-status": (
        [('        receipt["status"] = "aborted_interrupted"\n', '        receipt["status"] = "started"\n')],
        [SIGINT_TEST]),
    "I6-statuses-not-settled": (
        [("            settle_statuses(receipt)\n", "")],
        [SIGINT_TEST]),
    "I7-script-exits-with-a-code": (
        [("    exit_process(main())\n", "    sys.exit(main())\n")],
        [SIGTERM_TEST]),
    "I8-caller-dispositions-replaced": (
        [("            if signal.getsignal(signum) is not default:\n                continue\n", "")],
        [C_INT + "test_an_ignored_sighup_is_left_alone",
         C_INT + "test_a_callers_own_sigint_handler_still_leaves_an_interrupted_receipt"]),
    "I9-exception-leaves-group-running": (
        [("    except BaseException as exc:\n        _kill_process_group(proc)\n        try:\n"
          "            stdout, stderr, complete = _collect_after_kill(proc)\n",
          "    except BaseException as exc:\n        try:\n            stdout, stderr, complete = b\"\", b\"\", False\n")],
        [C_INT + "test_a_callers_own_sigint_handler_still_leaves_an_interrupted_receipt"]),
    "E1-etag-at-downloaded-file-name": (
        [("        etag_path = qmd_etag_path(model_cache_dir, uri)\n",
          "        etag_path = local_path.with_name(local_path.name + \".etag\")\n")],
        [C_PIN + "test_qmd_cached_etag_is_read_from_its_uri_file_name"]),
    # The final fixes after the review of run.py 0792745e: each mutant restores 0792745e's behaviour.
    "P1-bench-accepts-incomplete-output": (
        [("    problems = bench_output_problems(doc, fixture)\n    if problems:\n",
          "    problems = bench_output_problems(doc, fixture)\n    if False:\n")],
        [C_BEN + "test_empty_or_incomplete_bench_output_is_not_completed"]),
    "P2-rejection-reason-unsanitized": (
        [('                                "reason": runner.san(note),\n', '                                "reason": note,\n')],
        [C_NAT + "test_every_scored_query_links_to_its_retained_native_output"]),
    "P2b-version-banner-unsanitized": (
        [('            receipt["qmd_version_raw"] = san(ver.stdout.strip() or ver.stderr.strip())\n',
          '            receipt["qmd_version_raw"] = ver.stdout.strip() or ver.stderr.strip()\n')],
        [C_NAT + "test_every_scored_query_links_to_its_retained_native_output"]),
    "P2c-pull-note-unsanitized": (
        [('                "pull_note": san(entry["note"]),\n', '                "pull_note": entry["note"],\n')],
        [C_NAT + "test_every_scored_query_links_to_its_retained_native_output"]),
    "P3-limitations-set-after-the-benchmark": (
        [('        if args.skip_native_bench:\n            receipt["native_bench"] = {"status": "not_run",',
          '        pending_limitations, receipt["limitations"] = receipt["limitations"], []\n'
          '        if args.skip_native_bench:\n            receipt["native_bench"] = {"status": "not_run",'),
         ('        if receipt["native_bench"].get("status") != "not_run":\n',
          '        receipt["limitations"] = pending_limitations\n'
          '        if receipt["native_bench"].get("status") != "not_run":\n')],
        [C_INT + "test_a_stop_during_the_benchmark_keeps_the_decisions_limitations"]),
    "P4-running-call-not-recorded": (
        [("        self.received.append((int(signum), utc_now_iso_ms(), self.phase, self.current_call))\n",
          "        self.received.append((int(signum), utc_now_iso_ms(), self.phase, None))\n")],
        [C_INT + "test_a_call_that_ends_after_the_signal_is_named_but_not_cut_short"]),
    "P5-setup-failure-after-a-stop-dropped": (
        [("                if stops.requested():\n"
          "                    # A failure that follows a stop request is part of stopping, not a\n"
          "                    # finding about Arm B: the handler below records it with the stop.\n"
          "                    raise\n",
          "                stops.checkpoint()\n")],
        [C_INT + "test_a_setup_failure_after_a_stop_is_recorded_with_the_stop"]),
}


def build(name, source):
    root = OUT / name
    shutil.rmtree(root, ignore_errors=True)
    blueprint = root / "blueprints/retrieval-quality-v2"
    blueprint.mkdir(parents=True)
    (root / "tests").mkdir()
    for helper in ("__init__.py", "test_retrieval_quality_v2.py"):
        shutil.copy(WT / "tests" / helper, root / "tests" / helper)
    (blueprint / "run.py").write_text(source)
    for evidence in (WT / "blueprints/retrieval-quality-v2").glob("*.json"):
        shutil.copy(evidence, blueprint / evidence.name)
    return root


def run_tests(root, tests):
    outcomes = []
    for test in tests:
        start = time.monotonic()
        proc = subprocess.run([PY, "-m", "unittest", test], cwd=root, capture_output=True, text=True, timeout=900)
        lines = proc.stderr.strip().splitlines()
        ran = next((line for line in lines if line.startswith("Ran ")), "")
        outcomes.append({"test": test.rsplit(".", 1)[1], "exit_code": proc.returncode, "ran": ran,
                         "unittest_summary": lines[-1] if lines else "", "seconds": round(time.monotonic() - start, 1)})
    return outcomes


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
all_tests = sorted({t for _edits, tests in MUTANTS.values() for t in tests})
baseline = run_tests(build("baseline", SRC), all_tests)
results = []
for name, (edits, tests) in MUTANTS.items():
    if ONLY and name not in ONLY:
        continue
    source = SRC
    for old, new in edits:
        assert source.count(old) == 1, (name, old[:70], source.count(old))
        source = source.replace(old, new, 1)
    root = build(name, source)
    if name == "evidence-receipt-hand-edited":
        target = root / "blueprints/retrieval-quality-v2/results-20260926T024558Z.json"
        receipt = json.loads(target.read_text())
        row = receipt["arm_b"]["per_query"][0]
        row["ranked_paths"] = row["ranked_paths"][1:] + row["ranked_paths"][:1]
        target.write_text(json.dumps(receipt, indent=2) + "\n")
        patch = ("results-20260926T024558Z.json: arm_b.per_query[0].ranked_paths rotated by one position "
                 "(first path moved to the end); run.py unchanged")
    else:
        patch = "".join(difflib.unified_diff(SRC.splitlines(True), source.splitlines(True), "run.py", "run.py (mutant)", n=1))
    outcomes = run_tests(root, tests)
    for outcome in outcomes:
        outcome["result"] = "failed_as_required" if outcome["exit_code"] != 0 else "passed_mutant_not_caught"
    results.append({"mutant": name, "patch": patch, "tests": outcomes})
    print(name, [(o["test"], o["result"], o["unittest_summary"]) for o in outcomes], flush=True)

summary = {
    "recorded_at_utc": started,
    "python": platform.python_version(),
    "harness_sha256": sha(RUN),
    "tests_sha256": sha(TESTS),
    "method": ("Each mutant changes one repair in a copy of the committed run.py (the patch below); the named "
               "tests from tests/test_retrieval_quality_v2.py then run against that copy, one `python -m unittest "
               "<test>` each, and must fail. The same tests first run against an unmodified copy and must pass."),
    "baseline": baseline,
    "baseline_all_passed": all(o["exit_code"] == 0 for o in baseline),
    "mutants": results,
    "all_mutants_caught": all(o["exit_code"] != 0 for r in results for o in r["tests"]),
}
(OUT / "controls.json").write_text(json.dumps(summary, indent=2) + "\n")
print("baseline_all_passed", summary["baseline_all_passed"], "all_mutants_caught", summary["all_mutants_caught"])
