"""Build the gap-wave-2 receipts for us-equities/evaluation-experiments from the preregistrations
and the published (sanitized) raw outputs, then derive results.json from the receipts.
Usage (repo root): python3 build_receipts.py"""
import datetime
import glob
import hashlib
import json
from pathlib import Path

LAYER = "us-equities__evaluation-experiments"
EV = Path("evidence/artifacts/gap-wave2-20260923") / LAYER
BP = Path("blueprints/gap-wave2-20260923") / LAYER
RAW = EV / "raw"
NOW = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
H = "$HOME/.cache/gap-wave2-20260923/evaluation-experiments"
BR = "$HOME/codex-ecosystem/bin/ecosystem-bounded-run"


def j(rel):
    return json.loads((RAW / rel).read_text())


def t(rel):
    return (RAW / rel).read_text()


def one(pattern):
    found = sorted(glob.glob(str(RAW / pattern)))
    assert found, pattern
    return [str(Path(f).relative_to(RAW)) for f in found]


def raw_refs(*patterns):
    refs = []
    for p in patterns:
        for rel in one(p):
            refs.append({"path": str(RAW / rel), "sha256": hashlib.sha256((RAW / rel).read_bytes()).hexdigest()})
    return refs


def prereg(idx):
    path = next(p for p in sorted((EV / "prereg").glob(f"{idx}-*.json")) if not p.name.endswith("-fix1.json"))
    rec = json.loads(path.read_text())
    return rec, path


cmp0 = j("0/comparison.json")
timeline0 = t("0/run/timeline.txt").strip().splitlines()
contract = t("0/contract-test.txt")
control = j("0/control/results.json")
ctl_counts = {}
for r in control["results"]["results"]:
    key = f"{r['provider']['label']} failureReason={r.get('failureReason')}"
    ctl_counts[key] = ctl_counts.get(key, 0) + 1
ctl_err = next(r["error"] for r in control["results"]["results"] if r["provider"]["label"].startswith("typesafe")).split("\n")[0]
freeze3 = json.loads((BP / "inspect-arm/freeze.json").read_text())

two_arm_commands = [
    "cd blueprints/native-skill-practice && node --test test-contract.cjs",
    f"ECOSYSTEM_JOB_SECONDS=900 {BR} {BP}/run_two_arm.sh {H}/raw/0/run",
    "  arm 1 (per run): cd blueprints/native-skill-practice && PROMPTFOO_CONFIG_DIR=<run>/home unshare -rn promptfoo eval -c promptfooconfig.yaml --filter-providers exact-text-baseline-v1 --no-cache --no-share --no-table -j 1 -o <run>/results.json",
    "  arm 2 (per run): cd " + str(BP) + "/inspect-arm && HOME=<run>/home unshare -rn inspect eval catalog_task.py --max-samples 1 --max-connections 1 --retry-on-error 1 --log-format json --log-dir <run>/logs",
    "  fault diagnostic: arm 1 with derived config (C3 transform throws when INJECT_FAIL=1), then promptfoo eval --retry-errors; arm 2 with -T fail_once_case=C3 (retry-on-error 1) and again with --retry-on-error 0",
    "  interrupt/resume: arm 1 with --delay 1500, SIGINT after 5.5 s, then promptfoo eval --resume; arm 2 with -T delay=1.5, SIGINT after 7 s, then inspect eval-retry <cancelled log> --max-samples 1 --max-connections 1 --retry-on-error 1",
    f"python3 {BP}/compare_two_arm.py {H}/raw/0/run . > {H}/raw/0/comparison.json",
    "detection control: cd blueprints/native-skill-practice && env -u TYPESAFE_API_KEY PROMPTFOO_CONFIG_DIR=<ctl>/home REQUEST_TIMEOUT_MS=5000 timeout 120 unshare -rn promptfoo eval -c promptfooconfig.yaml --no-cache --no-share --no-table -j 1 -o <ctl>/results.json",
]
ATTEMPTS = [
    "attempt 1 (07:22:15Z): inspect rejected the absolute task path (NotImplementedError: Non-relative patterns are unsupported); no inspect sample was scored; runner fixed to cd into the task directory (frozen task files unchanged).",
    "attempt 2 (07:23:36Z): all clean and fault runs scored; the background inspect run ignored SIGINT (inherited SIG_IGN) and ran to completion, and eval-retry rejected --log-format; runner fixed.",
    "attempt 3 (07:24:56Z): all checks passed, but the promptfoo fault first-run and retry stdout shared one file; runner fixed to capture them separately and snapshot the DB before and after the retry.",
    "attempt 4 (07:26:37Z): retained run; all results in this receipt come from it.",
]
two_arm_results = {
    "contract_test": [l for l in contract.splitlines() if l.startswith(("ℹ tests", "ℹ pass", "ℹ fail", "exit="))],
    "timeline": timeline0,
    "label_matches": cmp0["label_matches"],
    "outcome_vector_promptfoo": {k: [v["verdict"], v["eligible"], v["disposition"], v["pass"], v["assertions"]] for k, v in cmp0["outcome_vector"]["promptfoo"].items()},
    "reproducibility": cmp0["reproducibility"],
    "gate_source_hash_summary": cmp0["gate_source_hash_summary"],
    "provider_calls": cmp0["provider_calls"],
    "detection_control_unfiltered_in_netns": {"counts": ctl_counts, "typesafe_error_first_line": ctl_err},
    "failure_log_fidelity": cmp0["failure_log_fidelity"],
    "interrupt_resume": cmp0["interrupt_resume"],
    "superseded_attempts": ATTEMPTS,
}
two_arm_raw = raw_refs("0/contract-test.txt", "0/comparison.json", "0/run/timeline.txt", "0/control/stdout.txt", "0/control/results.json",
                       "0/run/pf-clean-1/results.json", "0/run/pf-clean-2/results.json", "0/run/in-clean-1/logs/*.json", "0/run/in-clean-2/logs/*.json",
                       "0/run/pf-fault/*.json", "0/run/pf-fault/promptfooconfig.fault.yaml", "0/run/pf-fault/stdout.txt", "0/run/pf-fault/cfg-home/logs/*.log",
                       "0/run/pf-fault-retry/stdout.txt", "0/run/in-fault/logs/*.json", "0/run/in-fault-noretry/logs/*.json",
                       "0/run/pf-int/*", "0/run/in-int/logs/*.json", "0/run/in-int/stdout-*.txt")

receipts = {}
p, pp = prereg(0)
receipts[0] = dict(
    commands=two_arm_commands, results=two_arm_results, outcome="settled", evidence_class="local_integration",
    note="Every arm executed: contract check 6/6; both arms scored the frozen 8 cases with zero provider calls under unshare -rn; bounded concurrency 1 and bounded retries (inspect retry-on-error 1, promptfoo --retry-errors; HTTP maxRetries 0 untouched); retained failure logs; SIGINT interrupt then native resume to 8/8 in both arms. Scorer outcomes identical across repeats and arms (3/8 label matches, promptfoo exit 100). Differences: promptfoo compacts the JSON-valued C1/C2 source vars (gate source_sha256 differs from the frozen bytes for C1/C2; inspect matches all 8), and promptfoo's --retry-errors replaces the errored DB row and overwrites the original -o file, keeping the injected error only in its separate error log, whereas inspect keeps it in the final eval log's error_retries.",
    limits=["Deterministic exact-text baseline only: no model or TypeSafe inference, so nothing about semantic accuracy, latency or cost follows.",
            "Fault injection used a derived promptfoo config (transform throws for C3 when INJECT_FAIL=1) and task args for inspect; the unmodified config was used for all other arm-1 runs.",
            "One interrupt timing per arm (promptfoo after 2 of 8, inspect after 3 of 8 with C4 in flight); other interruption points untested.",
            "Arm 2's mock model evaluates the promptfoo transform expression via node and the scorer runs gate.cjs via node; it is a locally authored adapter, not an upstream inspect example.",
            "SIGINT for background runs required restoring the default SIGINT disposition (non-interactive bash ignores it in background jobs). Superseded attempts are listed in results.superseded_attempts; only attempt 4 is retained."],
    raw=two_arm_raw)

p, pp = prereg(2)
receipts[2] = dict(
    commands=["Same run as gap 0 (see receipt 0-promptfoo-inspect-two-arm.json)."] + two_arm_commands[-2:-1],
    results={"matched_on": "same frozen 8 cases (sha256 7cc28c50...), same exact-text transform, same gate.cjs and three assertions, zero provider calls, concurrency 1",
             "scorer_reproducibility": cmp0["reproducibility"], "label_matches": cmp0["label_matches"],
             "failure_log_fidelity_per_assertion": {a: len(cmp0["failure_log_fidelity"][a]["failed_with_per_assertion_detail"]) for a in ("promptfoo", "inspect")},
             "injected_error_in_final_tool_state": {"promptfoo": cmp0["failure_log_fidelity"]["promptfoo"]["injected_error"]["final_output_has_error_row"],
                                                   "promptfoo_error_log_file": cmp0["failure_log_fidelity"]["promptfoo"]["injected_error"]["retained_error_log_files_with_text"],
                                                   "inspect_error_retries": cmp0["failure_log_fidelity"]["inspect"]["injected_error"]["C3_error_retries_in_final_log"]},
             "resume": {a: {k: v for k, v in cmp0["interrupt_resume"][a].items()} for a in ("promptfoo", "inspect")},
             "input_fidelity_gate_source_hash_equal_frozen": {a: len(cmp0["gate_source_hash_summary"][f"{a}_equal_frozen"]) for a in ("promptfoo", "inspect")},
             "verdict": "Tie on scorer reproducibility (identical 8-case vectors, repeat-stable) and on resume success (both 8/8, pre-interrupt results reused). inspect-ai is ahead on two measured properties: it keeps the retried error inside the final eval log, and it passes the JSON-valued sources byte-exact (8/8 vs 6/8 gate source hashes). This supports keeping inspect-ai selected for the harness properties measured here; it is not a model-quality win."},
    outcome="settled", evidence_class="local_integration",
    note="The matched two-arm comparison now exists on the same task and is retained; it measures harness properties, not model quality.",
    limits=["Harness comparison on a deterministic baseline; the TypeSafe/model arm and any semantic-quality comparison were not run (no provider calls by design).",
            "Eight cases and one interrupt point per arm; timing is not compared."],
    raw=two_arm_raw[:3])

p, pp = prereg(3)
receipts[3] = dict(
    commands=["git commit 11d1e6c (inspect-arm/catalog_task.py, bridge.cjs, freeze.json) at 2026-09-23T07:21:37Z, before the first scored run",
              "cd " + str(BP) + "/inspect-arm && HOME=<run>/home unshare -rn " + H + "/venv-inspect/bin/inspect eval catalog_task.py --max-samples 1 --max-connections 1 --retry-on-error 1 --log-format json --log-dir <run>/logs"],
    results={"freeze": freeze3, "retained_run_timeline_attempt4": [l for l in timeline0 if "in-clean-1" in l],
             "in_clean_1": {"status": "success", "samples": 8, "accuracy_label_matches": cmp0["label_matches"]["inspect"],
                            "model_usage": cmp0["provider_calls"]["inspect_model_usage"]},
             "first_scored_run": "The first scored inspect run was attempt 2 at 07:23:39Z, after the 07:21:37Z freeze commit.",
             "superseded_attempts": ATTEMPTS},
    outcome="settled", evidence_class="local_integration",
    note="The inspect-ai mock-model task over catalog-cases.json was authored, hash-frozen and committed before its first scored run, and inspect eval ran it to 8 scored samples with exit 0.",
    limits=["The fixture is under blueprints/gap-wave2-20260923/, not under blueprints/native-skill-practice/; integration into that folder is left to the coordinator.",
            "Raw outputs of superseded attempts 1-3 were deleted when run_two_arm.sh was rerun into the same directory; they are described from the observed output, not retained."],
    raw=raw_refs("0/run/in-clean-1/logs/*.json", "0/run/in-clean-1/stdout.txt", "0/run/timeline.txt"))

tl1 = t("1/timeline.txt").strip().splitlines()
mteb = j("1/mteb-results/summary.json")
ph = j("1/phoenix-roundtrip.json")
ph1 = j("1/phoenix-attempt1-roundtrip.json")
mlf = t("1/mlflow-snippet.txt").strip().splitlines()[-1]
receipts[1] = dict(
    commands=[f"ECOSYSTEM_JOB_SECONDS=1800 ECOSYSTEM_JOB_MEMORY_MAX=8G ECOSYSTEM_JOB_MEMORY_HIGH=6G {BR} {H}/install.sh  (copy: {BP}/install_venvs.sh)",
              f"ECOSYSTEM_JOB_SECONDS=1800 ECOSYSTEM_JOB_MEMORY_MAX=8G ECOSYSTEM_JOB_MEMORY_HIGH=6G {BR} {H}/install-mteb.sh  (copy: {BP}/install_mteb.sh)",
              f"{BP}/run_package_checks.sh {H}/raw/1 inspect river mlflow",
              f"ECOSYSTEM_JOB_SECONDS=1200 ECOSYSTEM_JOB_MEMORY_MAX=8G ECOSYSTEM_JOB_MEMORY_HIGH=6G {BR} {BP}/run_package_checks.sh {H}/raw/1 mteb",
              f"{BP}/run_package_checks.sh {H}/raw/1 phoenix  (twice; attempt 1 had a launcher bug)"],
    results={"timeline": tl1,
             "inspect": {"version": "0.3.266", "help_exit": 0, "eval": "gap-3 task run exit 0, 8 samples (receipt 3)"},
             "river": {"version": "0.26.1", "catalog_snippet_output": t("1/river-snippet.txt").strip()},
             "mlflow": {"version": "3.16.1", "catalog_snippet_tracking_uri_printed": mlf,
                        "server_health": t("1/mlflow-health.txt").strip(), "experiments_search": [e["name"] for e in j("1/mlflow-experiments.json")["experiments"]]},
             "mteb": mteb,
             "phoenix": {"version": "20.14.0", "healthz": t("1/phoenix-health.txt").strip(), "span_roundtrip": ph,
                         "attempt_1": {"result": ph1["last_body_if_missing"], "cause": "runner used `env ... exec` (env: 'exec': No such file or directory), so no server started; fixed to `exec env ...` and rerun"}},
             "install_attempts": {"first_mteb_attempt": "uv rejected the requirement `torch==*+cpu` (Failed to parse); retried as `mteb==2.21.0 torch` with the PyTorch CPU extra index (installed torch 2.14.0+cpu)."},
             "network_downloads": "uv wheel downloads into an isolated UV_CACHE_DIR (2.3 GB on disk after unpacking across all venvs; largest wheel torch 2.14.0+cpu 187.2 MiB); sentence-transformers/all-MiniLM-L6-v2 at revision 8b3219a9 and mteb/stsbenchmark-sts (90 MB HF_HOME); CPython 3.14.7 via uv (112 MB, used by gap 4)."},
    outcome="settled", evidence_class="native_proven",
    note="All five pinned packages were installed into separate new uv venvs and executed: inspect --help and a scored eval; river and mlflow catalog snippets; an mlflow loopback server health/search check; an mteb STSBenchmark evaluation (main_score 0.8203 for all-MiniLM-L6-v2 on CPU); and a loopback phoenix serve that accepted and returned one OTLP span.",
    limits=["Minimal runs only: no inspect model provider, no mlflow model registry, no production phoenix instrumentation, one mteb task.",
            "The catalog cards in catalogs/us-equities/*.json still label these workflows prospective; this receipt is the executed evidence, and updating the card text is left to the coordinator.",
            "The mteb score is a public benchmark reproduction for one model and task, not financial-document retrieval evidence."],
    raw=raw_refs("1/*.txt", "1/*.json", "1/*.log", "1/mteb-results/summary.json", "1/mteb-results/cache/results/*/*/STSBenchmark.json"))

cmp4 = j("4/comparison.json")
receipts[4] = dict(
    commands=[f"git clone https://github.com/eyuansu62/agent-retrieval-bench.git {H}/arb/upstream && git -C {H}/arb/upstream checkout --detach b487f3866cc13dd971819cb902517a6a50282404",
              f"curl -sS --fail --location --max-time 300 -o {H}/arb/agent_retrieval_bench_v2_trace2code.tar.zst https://huggingface.co/datasets/eyuansu71/agent_retrieval_bench/resolve/5901e1ee3aff048290db72edf9c63bc498b79ea3/releases/v2_trace2code/agent_retrieval_bench_v2_trace2code.tar.zst",
              f"ECOSYSTEM_JOB_SECONDS=1200 {BR} {BP}/arb_rerun.sh {H}/arb {H}/raw/4",
              f"python3 {BP}/arb_compare.py . {H}/arb > {H}/raw/4/comparison.json"],
    results={"runtime": t("4/runtime.txt").strip(), "archive": t("4/extract.txt").strip().splitlines(),
             "validation": j("4/validate.json"), "exit_codes": t("4/exit-codes.txt").strip().splitlines(),
             "upstream_tests": t("4/upstream-tests.txt").strip().splitlines()[-1],
             "comparison_with_darwin_arm64_receipt": cmp4,
             "download": "37.5 MiB (39,295,446 bytes) archive from Hugging Face; upstream git clone."},
    outcome="advanced", evidence_class="native_proven",
    note="The host clause is closed: on Linux x86_64 with CPython 3.14.7, the unmodified ARB v0.2.1 lexical and BM25 per-sample details are byte-identical to the Darwin arm64 receipt (sha256 2eb08ad2... and 3c5e5399...), all 101 per-sample gold ranks match paired-samples.json, only runtime.wall_time_seconds differs in the summaries, and 15/15 upstream tests pass. What remains: the gap's scope clauses (file-level code retrieval with gin+click at 82/101 samples, not financial-document retrieval, answer quality or net trading performance) cannot be closed by a rerun; they need a financial-document retrieval benchmark with answer-quality judgments.",
    limits=["Same released subset and algorithms; no new domain, answer quality or trading evidence.", "Wall times (about 15-16 s per ranker) are single observations, not a latency benchmark."],
    raw=raw_refs("4/*"))

r5 = j("5/result.json")
ext = json.loads((BP / "fixture-v2/fixture-v2-extension.json").read_text())
receipts[5] = dict(
    commands=["git commit 2dbd582: freeze fixture-v2/fixture-v2-extension.json (8 added unanswerable queries, sha256 6e3aef38...) before any ranking",
              f"cd {H}/arb && PYTHONPATH=upstream/src runtime/bin/python {BP}/fixture_abstention_bootstrap.py <repo> > {H}/raw/5/result.json"],
    results={"added_unanswerable_queries": [q["query"] for q in ext["queries"]],
             "replay_ranking_mismatches_vs_2026_09_20": r5["replay_ranking_mismatches_vs_2026_09_20"],
             "replay_positive_metrics": r5["replay_positive_metrics"], "summary": r5["summary"], "bootstrap": r5["bootstrap"],
             "default_promotion_rule": r5["default_promotion_rule"], "default_promotion_claim_follows": r5["default_promotion_claim_follows"]},
    outcome="advanced", evidence_class="local_integration",
    note="Executed every arm of the next_check: 8 unanswerable queries added (v2: 20 answerable, 12 unanswerable), abstention rate/recall/false-abstention/decision accuracy under a preregistered leave-one-out threshold policy, paired bootstrap CIs (BM25 minus lexical MRR +0.067 [-0.008, 0.150]; Recall@1 +0.15 [0.00, 0.30]; top-1 decision accuracy -0.0625 [-0.1875, 0.0625]), and the preregistered promotion rule, which does not fire: no default-promotion claim follows. The original 24-query rankings replay exactly. What remains: the fixture is still source-authored over 15 public documents by the same author class; an external held-out or real-user query set is needed to close that clause.",
    limits=["n=20 answerable and 12 unanswerable; CIs are wide.", "The added unanswerables are authored with rg term scans as support; paraphrased answers could exist.",
            "The abstention threshold is chosen by leave-one-out on the same 32 queries; it is not a transferable operating point."],
    raw=raw_refs("5/result.json"))

r7 = j("7/validation-report.json")
receipts[7] = dict(
    commands=[f"{H}/venv-river/bin/python {BP}/river_delayed_validation.py <repo> $HOME/.local/share/codex-ecosystem/tools/lean-985ef30 > {H}/raw/7/validation-report.json"],
    results={"input": r7["input"], "stream": r7["stream"],
             "runs": [{k: v for k, v in run.items() if k != "checkpoints"} | {"checkpoints": len(run["checkpoints"])} for run in r7["runs"]],
             "probe_detection": r7["probe_detection"],
             "report_artifact": str(RAW / "7/validation-report.json"),
             "superseded_attempts": "Two script errors before any report was written (moment without delay raised TypeError; the probe lacked river's Classifier base so the metric rejected it); fixed and rerun."},
    outcome="settled", evidence_class="local_integration",
    note="river 0.26.1 in a new uv venv ran iter_progressive_val_score over the hash-verified bundled LEAN SPY daily stream (1,798 samples) with each label revealed at its t+6 open (delay = label_at - date), and emitted a validation report with 8 checkpoints per run. The causality probe counted 0 early labels in the delayed run and 1,797 in the immediate positive control. Delayed logistic accuracy 0.592 versus immediate 0.610; a prior-class baseline reached 0.612, so no predictive-skill claim follows.",
    limits=["One ETF and three trailing-return features; a mechanics check of delayed progressive validation, not a strategy evaluation.",
            "Nominal session dates stand in for label availability times; late corrections and restarts were not modelled.",
            "Input read from the pinned LEAN checkout at $HOME/.local/share/codex-ecosystem/tools/lean-985ef30 (hash-verified, read-only)."],
    raw=raw_refs("7/*"))

rb0 = j("8/readback.json")
rb = j("8/readback-fix1.json")
rec8 = json.loads(Path("blueprints/us-equities/research-evaluation/receipt.json").read_text())
res8 = j("8/work-fix1/run-1/results.json")
res8_round0 = j("8/work/run-1/results.json")
selection_match = {f"run-1/{f['id']}.selection.json": f["selection_sha256"] == rec8["private_artifacts"][f"run-1/{f['id']}.selection.json"]["sha256"]
                   for f in res8["development_folds"] + [res8["reserved"]]}
manifest = {f["path"]: f for f in j("MANIFEST.json")["files"]}
stdout_sha = manifest["8/work-fix1/evaluate.stdout.txt"]["original_sha256"]
fix8 = json.loads((EV / "prereg/8-research-evaluation-mlflow-binding-fix1.json").read_text())
receipts[8] = dict(
    commands=["python3 -m unittest tests/test_research_evaluation.py -v",
              f"round 0: MLFLOW_DISABLE_TELEMETRY=true DO_NOT_TRACK=true MLFLOW_DISABLE_AGENT_HINT=1 ECOSYSTEM_JOB_SECONDS=1200 {BR} {H}/venv-mlflow/bin/python {BP}/mlflow_bind.py <repo> $HOME/.local/share/codex-ecosystem/tools/lean-985ef30 {H}/venv-skfolio/bin/python {H}/raw/8/work",
              f"fix round 1 (after review; exit-code metric added to the comparison): same command with {H}/raw/8/work-fix1 > {H}/raw/8/readback-fix1.json"],
    results={"unit_tests": [l for l in t("8/unit-tests.txt").splitlines() if l.startswith(("Ran ", "OK", "exit="))],
             "readback_fix1": {k: rb[k] for k in ("runs_found", "status", "evaluate_exit_code", "params_logged", "metrics_logged", "metric_columns_read_back",
                                                  "all_read_back_metrics_compared", "readback_mismatches",
                                                  "negative_probe_changed_ledger_records_detected", "negative_probe_exit_code_999_detected",
                                                  "dataset_inputs", "dataset_digests_equal_plan_prefix36",
                                                  "dataset_digest_lengths", "tags", "artifacts", "first_attempt_note")},
             "round0_readback_superseded": {"readback_mismatches": rb0["readback_mismatches"], "defect": "compare() omitted the logged evaluate_exit_code metric (round-1 review finding); fixed in fix round 1"},
             "replay_vs_2026_09_19_receipt": {
                 "ledger_sha256_equal": rb["tags"]["ledger_sha256"] == rec8["private_artifacts"]["run-1/candidate-ledger.json"]["sha256"],
                 "evaluate_stdout_sha256_equal": stdout_sha == rec8["private_artifacts"]["run-1.stdout.txt"]["sha256"],
                 "selection_hashes_equal": f"{sum(selection_match.values())}/{len(selection_match)}",
                 "reserved_all_candidates_equal": res8["reserved"]["all_candidates"] == rec8["results"]["reserved"]["all_candidates"],
                 "round0_and_fix1_results_equal_except_freeze_time": {k: v for k, v in res8.items() if k != "freeze_sha256"} == {k: v for k, v in res8_round0.items() if k != "freeze_sha256"},
                 "folds": len(res8["development_folds"]), "ledger_records": res8["ledger_records"], "reserved_chosen": res8["reserved"]["chosen"]}},
    outcome="advanced", evidence_class="local_integration",
    fix_round_preregistration=fix8,
    note="The tracker link is established. The unchanged evaluate.py ran from its hash-locked skfolio 1.2.9 venv inside an MLflow 3.16.1 run with a temporary sqlite store. It logged 16 params, 19 metrics (including evaluate_exit_code), 9 dataset inputs and sha256 tags. mlflow.search_runs read every logged param and metric back with 0 mismatches. Two negative probes were each detected as a single mismatch: ledger_records+1 and exit code 999. The replay reproduced the 2026-09-19 receipt: the candidate-ledger sha256, the stdout sha256 and all 21 selection hashes are equal. One clause remains: the chronological evaluation is still project-local code. The tracker is now upstream, but the evaluation logic is not. Closing that clause needs the same protocol to run through an upstream-maintained evaluation component, for example skfolio's model_selection cross-validation producing the same selections.",
    limits=["MLflow caps dataset digests at 36 characters, so each dataset input carries only the first 36 hex digits of its sha256; the full sha256 is in the input_sha256:* tags. The first attempt with full digests failed; its output is retained.",
            "Metrics are logged as floats; the exact Decimal strings remain in the logged results.json artifact.",
            "Local sqlite tracking store only; no tracking server, registry or remote artifact store.",
            "Round 0's readback omitted the exit-code metric; fix round 1 is the cited result and round 0 is retained as superseded."],
    raw=raw_refs("8/*.txt", "8/readback.json", "8/readback-fix1.json", "8/work/*.txt", "8/work/run-1/*.json", "8/work-fix1/*.txt", "8/work-fix1/run-1/*.json", "review-codex-round1.md"))

results = {}
for idx, r in sorted(receipts.items()):
    pre, prepath = prereg(idx)
    slug = pre["slug"]
    rec = {"id": f"gap-wave2-20260923/{LAYER}/{idx}-{slug}", "gap_index": idx, "gap_text_sha256": pre["gap_text_sha256"],
           "next_check": pre["next_check"],
           "preregistration": dict(pre["preregistration"], file=str(prepath), committed_in="20fbeb6 (2026-09-23T07:18:35Z), before any check ran"),
           "commands": r["commands"], "results": r["results"], "outcome": r["outcome"], "outcome_note": r["note"],
           "evidence_class": r["evidence_class"], "limits": r["limits"], "raw_outputs": r["raw"], "checked_at": NOW}
    if "fix_round_preregistration" in r:
        rec["fix_round_preregistration"] = dict(r["fix_round_preregistration"], file=f"{EV}/prereg/{idx}-{slug}-fix1.json", committed_in="b874a51 (2026-09-23T07:50:35Z), before the fix-1 run")
    path = EV / f"{idx}-{slug}.json"
    path.write_text(json.dumps(rec, indent=1, default=str) + "\n")
# results.json is derived from the receipts on disk, never written by hand.
for path in sorted(EV.glob("[0-9]*-*.json")):
    rec = json.loads(path.read_text())
    results[str(rec["gap_index"])] = {"outcome": rec["outcome"], "receipt": str(path)}
(EV / "results.json").write_text(json.dumps({"layer": LAYER, "generated_from_receipts": True, "generated_at": NOW, "gaps": results}, indent=1) + "\n")
print(json.dumps(results, indent=1))
