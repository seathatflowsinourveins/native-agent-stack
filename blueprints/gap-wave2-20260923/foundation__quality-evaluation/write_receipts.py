#!/usr/bin/env python3
"""Write the fix-round receipts for foundation/quality-evaluation (data only).

Usage: write_receipts.py G2_UNITS_JSON
"""
import hashlib
import json
import sys

UNITS = sys.argv[1]  # the wave's g2-units.json (session scratchpad path, not published)
E = "evidence/artifacts/gap-wave2-20260923/foundation__quality-evaluation/"
gaps = {g["index"]: g for u in json.load(open(UNITS)) if u["layer_id"] == "quality-evaluation" for g in u["gaps"]}
pre = json.load(open(E + "preregistrations-fixround.json"))["gaps"]
pre2 = json.load(open(E + "preregistrations-fixround2.json"))["gaps"]
BP = "blueprints/gap-wave2-20260923/foundation__quality-evaluation"
FX = "support/fixround"
ORIG = {0: "2026-09-23T01:40:00Z", 1: "2026-09-23T02:05:00Z", 2: "2026-09-23T02:15:00Z", 3: "2026-09-23T02:25:00Z", 4: "2026-09-23T02:00:00Z",
        5: "2026-09-23T02:45:00Z", 7: "2026-09-23T01:58:00Z", 9: "2026-09-23T02:35:00Z", 10: "2026-09-23T02:46:00Z"}
RUN123 = f"bash {BP}/run_g1_g2_g3.sh $HOME/.cache/gap-wave2-20260923/quality-evaluation/fixround/g123 $HOME/.cache/gap-wave2-20260923/quality-evaluation/fixround/g123-out"
RUN047 = (f"bash {BP}/run_g0_g4_g7.sh $HOME/.cache/gap-wave2-20260923/quality-evaluation/fixround/g047 $HOME/.cache/gap-wave2-20260923/quality-evaluation/fixround/g047-out "
          "$HOME/.cache/gap-wave2-20260923/quality-evaluation/promptfoo-heldout/cases.json $HOME/.cache/gap-wave2-20260923/quality-evaluation/fixround/upstream4 "
          "$HOME/.cache/gap-wave2-20260923/quality-evaluation/fixround/pinned-venv")
INSTALL = ("UV_CACHE_DIR=$HOME/.cache/gap-wave2-20260923/quality-evaluation/fixround/uv-cache ecosystem-bounded-run bash -c \"uv venv --python 3.12 .../fixround/pinned-venv && "
           "uv pip install --python .../fixround/pinned-venv/bin/python 'inspect-ai==0.3.268' 'mlflow==3.16.1' 'openai' 'jsonschema'\"")
REVIEW = f"bash {BP}/run_review_call.sh {{who}} $PWD/{E}support/typesafe-extension $HOME/.cache/gap-wave2-20260923/quality-evaluation/fixround/review-out"
SCORE = (f"pinned-venv/bin/python {BP}/score_reviews.py {E}support/typesafe-extension .../review-out/codex-last-message.json .../review-out/claude-result.json .../review-out/agreement.json")

R = {}
FX2 = "support/fixround2"
C2 = "$HOME/.cache/gap-wave2-20260923/quality-evaluation/fixround2"
R[0] = dict(slug="promptfoo-heldout-30case", outcome="settled", evidence_class="local_integration", checked_at="2026-09-23T12:49:30Z",
    commands=[f"bash {BP}/run_codex_author.sh $PWD/{E}{FX2}/hardneg-author {C2}/author-out  (one codex exec: --ignore-user-config --disable hooks --sandbox read-only --ephemeral --skip-git-repo-check -C <empty dir> -m gpt-6-astra -c model_reasoning_effort=\"medium\" --output-schema schema.json --json - < prompt.txt)",
              f"freeze: the author's cases array written unchanged to {E}{FX2}/hardneg-cases.json (sha256 be64ae45...), committed in 2557b2f before any embedding call on it",
              f"UV_CACHE_DIR={C2}/uv-cache uv venv -p python3.12 {C2}/fe-venv && uv pip install -p {C2}/fe-venv/bin/python fastembed==0.8.1; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir={C2}/fe-models) (downloads Qdrant/bge-small-en-v1.5-onnx-Q, 65 MB)",
              f"bash {BP}/run_g0_fixround2.sh {C2}/g0 {C2}/g0-out {E}{FX}/g0-g4-g7/cases.json {E}{FX2}/hardneg-cases.json {C2}/fe-venv {C2}/fe-models",
              f"python3 {BP}/margins_fixround2.py {E}{FX}/g0-g4-g7/cases.json {E}{FX2}/hardneg-cases.json > {C2}/g0-out/margins-typed.jsonl  (post-hoc diagnostic, not preregistered)"],
    results={"call_form": "Nemotron now uses the pinned model card's call (upstream-example.py): the query in one /v2/embed request with input_type 'query', the four candidates in a second request with input_type 'document', embedding_types ['float'], truncate 'END' (heldout_common.predict_typed). The round-1/fix-round-1 predict() sent query and candidates in one request without input_type; it is kept unchanged for gap 4.",
             "easy_set": {"cases_sha256": "124e29b041af1ced01c2b8af4c5f15600cf86e78f13c19676079f2a792b0e9e6 (g0-out/easy-cases.sha256)",
                          "nemotron_typed": "✓ 30 passed (100%), exit 0 (easy-typed.stdout); tokenUsage total 2432 over 60 requests",
                          "bge_small": "✓ 30 passed (100%), exit 0 (easy-bge.stdout)",
                          "fix_round_1_untyped": "26/30 with failures case-07/09/13/24 (support/fixround/g0-g4-g7/pf-heldout.stdout): all four pass with the model-card call, so those failures came from the harness call, as the review said"},
             "hard_set": {"author": "one Codex call (gpt-6-astra, medium effort), exit 0, 241106 ms; usage input 17348, output 7664, reasoning 365 (author-out/codex-author-timing.txt, codex-author-events.jsonl: thread.started, turn.started, item.completed agent_message, turn.completed; no tool items)",
                          "cases_sha256": "be64ae45405313961624b102cba7b7a25cee97061ef3a251293d59c70a068576 (hardneg-freeze.txt; g0-out/hard-cases.sha256 identical)",
                          "shape": "30 cases, 30 distinct queries, each with one answer passage and three same-topic distractors (for example H22: jet lag after eastward travel; distractors on time-zone arithmetic, long-flight fatigue and jet-lag symptoms)",
                          "nemotron_typed": "✓ 30 passed (100%), exit 0 (hard-typed.stdout); tokenUsage total 6702 over 60 requests",
                          "bge_small": "✓ 28 passed (93.33%) ✗ 2 failed, exit 100 (hard-bge.stdout); failures case-21 (H22 jet lag, predicted the jet-lag-symptoms distractor) and case-23 (H24 tennis tiebreak serving order, predicted the tiebreak-scoring distractor)",
                          "nemotron_untyped_diagnostic": "✓ 13 passed (43.33%) ✗ 17 failed, exit 100 (hard-untyped.stdout); tokenUsage total 6299 over 30 requests",
                          "control": "constant pred=0: ✓ 6 passed (20.00%) ✗ 24 failed, exactly the 6 label-0 cases (hard-control.stdout, hard-generator.stdout 'label==0 count: 6')"},
             "per_case_scores": "every run's -o results JSON with 30 gradingResults is retained (g0-out/{easy,hard}-*-results.json)",
             "margin_diagnostic": "post-hoc, not preregistered: Nemotron typed cosine margin between the answer and the best distractor, median 0.5667 (min 0.3373) on the easy set vs 0.2272 (min 0.0674) on the hard set (g0-out/margins-typed.jsonl)",
             "preregistered_expectation_check": "arms (a), (b) and (c) all ran and every settled criterion holds. One stated expectation failed: Nemotron did not score lower on the hard set (30/30 on both); bge-small did (30 -> 28)."},
    limits=("The hard set was written by one Codex call, not by a human or a published benchmark. This agent checked only schema, counts and distinct queries, and read the two bge-failure cases (their labels are correct on inspection); the other labels were not re-reviewed. "
            "Nemotron reaches the ceiling on both sets, so the hard set cannot separate it from a stronger model; the 30 vs 28 difference against bge-small is two cases on one deterministic run, not a ranking with confidence. "
            "bge-small ran through fastembed 0.8.1, which serves Qdrant's quantised ONNX export (model_optimized.onnx sha256 51f1bd0a..., setup/bge-model-files.sha256), not the original FP32 weights. "
            "The fix-round-1 26/30 (and the gap-4 harness comparison built on it) used a call without input_type that drops Nemotron to 13/30 on the hard set; it measured the harness call, not model quality. "
            "Round-1 note: the round-1 assertion read the label from the provider's own output; that design was replaced in fix round 1 and is superseded (commit b37df23)."),
    artifacts=[f"{FX2}/hardneg-author/{{prompt.txt,schema.json}}", f"{FX2}/author-out/*", f"{FX2}/{{hardneg-cases.json,hardneg-freeze.txt}}", f"{FX2}/g0-out/*",
               f"{FX2}/setup/{{fe-install.log,bge-model-files.sha256,g0.started}}", f"{FX}/g0-g4-g7/{{cases.json,pf-heldout.stdout,pf-heldout-results.json}}",
               f"{BP}/{{run_codex_author.sh,run_g0_fixround2.sh,gen_fixround2_configs.py,heldout_common.py,pf_provider.py,pf_provider_typed.py,pf_provider_bge.py,pf_control_provider.py,margins_fixround2.py}}"])
R[1] = dict(slug="playwright-upstream-todomvc", outcome="settled", evidence_class="native_proven", checked_at="2026-09-23T02:46:00Z",
    commands=["git clone --depth 1 --branch v1.63.0 https://github.com/microsoft/playwright.git repo (round 1; commit 1b025d7e20a026371cd5f98ba0cdce48892737c8)",
              "cd repo/examples/todomvc && npm install --no-save @playwright/test@1.63.0 dotenv (round 1)",
              RUN123 + "  (gap-1 step: npx playwright test --project=chromium --reporter=list in examples/todomvc)"],
    results={"exit": "0 (g1-full-suite.exit)", "summary": "Running 24 tests using 12 workers ... 24 passed (10.2s) (g1-full-suite.stdout)",
             "scope": "the whole upstream examples/todomvc suite: adding-todos, completing-todos, deleting-todos, editing-todos, filtering-todos, todo-creation and seed", "playwright_version": "Version 1.63.0 (versions.txt)"},
    limits=("examples/todomvc is Playwright's shipped example suite. The monorepo's internal tests/library and tests/page suites need private test-server fixtures and were not run. "
            "The target is the live demo.playwright.dev site. The Chromium build came from a browser cache that another unit created earlier this wave; its provenance was checked only by version match."),
    artifacts=[f"{FX}/g1-g2-g3/{{g1-full-suite.stdout,g1-full-suite.stderr,g1-full-suite.exit,versions.txt}}"])
RUN2 = (f"bash {BP}/run_g2_fixround2.sh $PWD {C2}/g2 {C2}/g2-out $HOME/.cache/gap-wave2-20260923/quality-evaluation/fixround/pinned-venv {C2}/app "
        "$HOME/.cache/gap-wave2-20260923/web-research/ms-playwright/chromium-1243/chrome-linux64/chrome")
R[2] = dict(slug="mutation-catch-three-winners", outcome="settled", evidence_class="local_integration", checked_at="2026-09-23T12:50:46Z",
    commands=[f"application prefix {C2}/app: copy of blueprints/convergence-practice/application-delivery at this branch plus wsl-application/playwright.config.ts; "
              "flex 2.6.4-8.2build1, m4 1.4.19-4build1 and bison 3.8.2+dfsg-1ubuntu0.24.04.1 .deb files downloaded from archive.ubuntu.com, sha256-checked against wsl-application/ubuntu-packages.json and extracted with dpkg-deb -x into a task sysroot; "
              "corepack enable --install-directory <prefix>/bin pnpm (COREPACK_HOME in the prefix; pnpm 12.4.2); make setup; ecosystem-bounded-run make postgres-install (attempt 1 failed: 'configure: error: bison not found'; attempt 2 exit 0); "
              "ecosystem-bounded-run taskset -c 0-3 pnpm build (attempt 1 failed: tokio 'OS can't spawn worker thread' under the default 256-task cap; attempt 2 with ECOSYSTEM_JOB_TASKS_MAX=1024 exit 0)",
              RUN2 + "  (inner namespace script: run_g2_app_inner.sh)"],
    results={"exit_codes": {"promptfoo (examples/promptfoo-nemotron-upstream)": "original 0 / mutant 100 / restored 0",
                            "shellcheck (shellcheck fixtures/example.sh)": "original 0 / mutant 1 / restored 0",
                            "playwright (application-delivery, frozen browser/ledger.spec.ts)": "original 0 / mutant 1 / restored 0"},
             "exit_code_files": "g2-out/{pf-upstream,sh,app}-{original,mutant,restored}.exit",
             "promptfoo_mutation": "upstream-example.py (the fixture's assertion target, executed copy sha256 c4b48632...) with DOCUMENTS[2] and DOCUMENTS[3] swapped (pf-upstream-mutation.diff; mutant sha256 28c29b96...); promptfooconfig.yaml sha256 07c64ff5... unchanged in all phases (pf-upstream-phase.sha256)",
             "promptfoo_mutant_failure": "'2/4 NVIDIA published queries ranked the paired document first; winners=[[0],[1],[3],[2]]' (pf-upstream-results-mutant.json); original and restored 'All assertions passed'",
             "shellcheck_mutation": "fixtures/example.sh line 3 'printf \"%s\\n\" \"native stack fixture\"' -> 'printf \"%s\\n\" $1' (sh-mutation.diff)",
             "shellcheck_mutant_failure": "In fixtures/example.sh line 3: printf \"%s\\n\" $1 ... SC2086 (info): Double quote to prevent globbing and word splitting. (sh-mutant.stdout)",
             "app_mutation": "backend/app.py update_run no longer inserts the run_events history row (app-mutation.diff); original sha256 0dbd2f60... equals the repository file",
             "app_mutant_failure": "Error: expect(locator).toContainText(expected) failed ... Expected substring: \"Revision 2 · 2 recorded changes\" Received string: \"...Revision 2 · 1 recorded changes...\" ... 1 failed (app-mutant.stdout)",
             "app_original_restored": "1 passed (4.5s) and 1 passed (2.4s) (app-original.stdout, app-restored.stdout)",
             "oracle_unchanged": "browser/ledger.spec.ts 1cd010ba..., playwright.config.ts d36c6391... and wsl-application/playwright.config.ts 24a34681... identical in all three phases and equal to the repository files (app-phase.sha256)",
             "isolation": "host 127.0.0.1:18080 was held by a running ntfy service (app-host-ports-before.txt), so PostgreSQL, the API, Next and Chromium ran in a new user+network namespace whose only interface was lo (app-ns-interfaces.txt), with the caller's uid mapped back to 1000 so PostgreSQL did not run as root. Namespace listeners after pg_ctl stop: none (app-ns-listeners-after.txt); host listeners on 15432/18081 after: 0 (app-host-ports-after.txt)",
             "fix_round_1_substitutes": "the fix-round-1 run on minimal Promptfoo/shell fixtures and on a loopback mirror of the TodoMVC demo app (support/fixround/g1-g2-g3/g2-*) is kept as supporting evidence; it is superseded as the gap-2 evidence"},
    limits=("One mutation per tool shows that each winner catches an injected regression in its project fixture; it does not measure mutation-detection rates. "
            "Chromium was the Playwright 1.63 chromium-1243 build from a browser cache another unit created this wave, not the Linux Chrome for Testing 153 build of the WSL qualification. "
            "The Ubuntu InRelease signature step of the WSL recipe was not repeated; each .deb was checked against the sha256 recorded in the committed ubuntu-packages.json. "
            "The application was copied from this branch rather than cloned fresh at cabbe2c; app/, backend/ and browser/ are unchanged between them, and the Makefile and serve.py differ only by the recorded portability fixes. "
            "The Promptfoo fixture directory holds only promptfooconfig.yaml; its assertion target is NVIDIA's model-card script, used here as the executed copy retained by gap 7. "
            "Detection: each mutant has a recorded diff (diff exit 1); the oracle hashes are identical in every phase; the original-phase pass needed the 'Run ledger' heading, which the host's ntfy on :18080 cannot serve, and the namespace had no route to host listeners."),
    artifacts=[f"{FX2}/g2-out/*", f"{FX2}/setup/{{app-setup.log,app-setup.started,debs-urls-sha256.txt,debs-verify.log,pg-install1-bison-missing.log,pg-install2.tail.log,app-build1-tasks-limit.log,app-build2.log,g2.started}}",
               f"{FX}/g1-g2-g3/g2-*", f"{BP}/{{run_g2_fixround2.sh,run_g2_app_inner.sh}}"])
R[3] = dict(slug="shellcheck-difft-content-assert", outcome="settled", evidence_class="local_integration", checked_at="2026-09-23T02:46:00Z",
    commands=[RUN123 + "  (gap-3 steps: shellcheck -f json bad.sh / clean.sh; difft --color never --exit-code a/file.sh b/file.sh and a/file.sh a/file.sh; grep -q 'there' on each difft stdout)"],
    results={"shellcheck_bad": "exit 1 (g3-shellcheck-bad.exit), codes [2086] (g3-shellcheck-bad.codes)", "shellcheck_clean": "exit 0, [] (g3-shellcheck-clean.exit/.json)",
             "difft_changed": "exit 1; stdout: '3 echo \"world\"               3 echo \"there\"' (g3-difft-changed.stdout)",
             "difft_identical": "exit 0; stdout: 'a/file.sh --- Bash / No changes.' (g3-difft-identical.stdout)",
             "content_assertions": "grep for the changed token 'there': exit 0 on the changed-file output, exit 1 on the identical-file output (g3-assert-*.exit)",
             "versions": "ShellCheck 0.11.0, Difftastic 0.71.0 (versions.txt)"},
    limits="The fixtures are minimal single-file synthetic cases written for this check. The content assertion is a token grep, not a structural parse of difft output.",
    artifacts=[f"{FX}/g1-g2-g3/g3-*", f"{FX}/g1-g2-g3/versions.txt"])
R[4] = dict(slug="promptfoo-vs-inspect-ai", outcome="settled", evidence_class="local_integration", checked_at="2026-09-23T02:48:49Z",
    commands=[INSTALL, RUN047],
    results={"pinned_install": "inspect-ai==0.3.268, mlflow==3.16.1 pinned in the install command; 'Resolved 141 packages ... Installed 141 packages' into a new venv (g4-g9-pinned-install.log)",
             "same_frozen_cases": "both harnesses read cases.json sha256 124e29b0... through the same heldout_common.load_cases (seed-42 shuffle)",
             "scores": "promptfoo 26/30 (86.67%); Inspect accuracy 0.867 (inspect-heldout.stdout)",
             "per_case_agreement": "30/30 identical predictions; the same 4 failures, case-07/09/13/24 (per-case-agreement.json)",
             "runtime": "wall clock: promptfoo 12728 ms, Inspect 4219 ms (*.wall_ms); promptfoo durationMs 1560; Inspect 'total time: 0:00:02'",
             "token_usage": {"promptfoo_harness": "stats.tokenUsage total 2040, numRequests 30 (from the provider's billed_units)",
                             "inspect_harness": "stats.model_usage {} (no Inspect model provider involved); per-sample billed_input_tokens in score metadata sums to 2040",
                             "endpoint_meter": "vllm:prompt_tokens_total +2040 during each harness window; +0 over both 15 s quiet control intervals (vllm-metrics.txt)"},
             "cost": "neither harness reports a monetary cost for the local endpoint (promptfoo cost 0 placeholder)"},
    limits=("Both harnesses ran the same custom embedding-retrieval scorer, not each tool's own LLM-graded workflow, so this compares harness mechanics on identical inputs, not grader quality. Inspect's native usage field is empty because no Inspect model provider was used; "
            "its token figure comes from task-recorded endpoint metadata. Wall-clock includes harness start-up. The round-1 comparison used an unpinned install and only aggregate scores; it is superseded. Fix-round-2 note: both harnesses used the single-request call without input_type; with the model card's call the same 30 cases score 30/30 (gap 0), so 26/30 reflects that call, not model quality. The harness comparison stands because both harnesses shared the call."),
    artifacts=[f"{FX}/g4-g9-pinned-install.log", f"{FX}/g0-g4-g7/{{per-case-agreement.json,inspect-logs/*,inspect-heldout.*,pf-heldout*,vllm-metrics.txt}}", f"{BP}/{{inspect_heldout_task.py,heldout_common.py}}"])
R[5] = dict(slug="typesafe-c4-expansion", outcome="advanced", evidence_class="native_proven", checked_at="2026-09-23T02:55:07Z",
    commands=[f"python3 {BP}/build_typesafe_extension.py {E}support/typesafe-extension (frozen and committed in 1b85ad8 at 2026-09-23T02:53:30Z, before either model call)",
              REVIEW.format(who="codex") + "  -> codex exec --ignore-user-config --disable hooks --sandbox read-only --ephemeral --skip-git-repo-check -C <empty dir> -m gpt-6-astra -c model_reasoning_effort=\"medium\" --output-schema schema.json -o codex-last-message.json --json - < prompt.txt (timeout 900)",
              REVIEW.format(who="claude") + "  -> claude -p --model sonnet --effort medium --setting-sources project --strict-mcp-config --tools \"\" --no-session-persistence --output-format json --json-schema <schema.json> < prompt.txt (timeout 900)",
              SCORE],
    results={"case_set": "20 cases: C1-C8 unchanged from catalog-cases.json (sha256 7cc28c50...), C9-C20 new, sourced from verbatim line ranges of docs/promptfoo-upstream-retrieval.md and docs/native-skill-practice-20260921.md (cases.json, freeze-hashes.txt)",
             "schema_validation": {"codex": "valid", "claude": "valid (structured_output)"},
             "agreement_with_frozen_labels": {"codex": "20/20 (C1-C8 8/8, C9-C20 12/12)", "claude": "17/20 (C1-C8 6/8, C9-C20 11/12)"},
             "codex_vs_claude": "17/20; Claude answered 'contradicted' where the source only fails to establish the claim, on C2, C4 and C20",
             "C4": "frozen insufficient; Codex insufficient; Claude contradicted; TypeSafe (2026-09-21) contradicted",
             "exit_and_timing": "codex exit 0, 24628 ms; claude exit 0, 9186 ms (*-timing.txt)",
             "usage": {"codex": "input 19896, cached 0, output 686, reasoning 44 (turn.completed)", "claude": "resolved claude-sonnet-5; input 2, cache_creation 16064, output 1151; total_cost_usd 0.0758 is the CLI's list-price estimate on the subscription account, not a charge"},
             "hooks": "Fix-round-2 correction: the per-session attribution claim ('0 ai-memory hook processes in either call\'s session') is withdrawn. Every hook invocation the poller sampled is its own session leader: 6/6 distinct hook session ids in the Claude window and 7/7 in the Codex window belong to a process with pid == sid ({claude,codex}-hook-poller.txt), so a hook spawned by the reviewed CLI would also have opened a new session and been counted as another session; the zero was true by construction, and the setsid sensitivity probe did not test that case. The no-hook conclusion rests instead on: (1) configuration: Codex ran with --ignore-user-config --disable hooks, Claude with --setting-sources project from an empty directory; (2) tool activity: Claude ran with --tools \"\" and codex-events.jsonl holds only thread.started, turn.started, item.completed(agent_message) and turn.completed, so neither call made a tool call; (3) event type: every sampled hook process was --event pre-tool-use or post-tool-use (Claude window 3 + 17, Codex window 5 + 10), which a call without tool calls cannot emit, and no session-start, user-prompt-submit or stop hook appears in either window. Two post-tool-use samples in the Codex window carry --agent codex; the reviewed Codex call made no tool call, so they came from another Codex session. Parent-pid ancestry was not captured, so no sampled hook is attributed to or excluded from a call by ancestry.",
             "blindness": "Not fully blind (reconciliation): prompt.txt lines 193-215 give, as the C15-C17 source excerpt, the sentence that the earlier native reviews 'corrected C4 to `insufficient`', and lines 217-239 (C18-C20) disclose TypeSafe's 7/8 aggregate. The same prompt asks for C4 at lines 86-96. Both reviewers' C4 verdicts are therefore contaminated, and the agreement counts on C4 are not independent agreement with the frozen label."},
    limits=("Deferred arm: TypeSafe was not run on C9-C20. Blocker: the TypeSafe API needs TYPESAFE_API_KEY, and this brief forbids credential reads and paid API use; owner: a session authorised to load that credential. "
            "The single Claude call is the brief's one allowed bounded call. It ran on Sonnet (resolved claude-sonnet-5), while the 2026-09-21 review ran on claude-fable-5-1, so the two Claude runs are different models. "
            "The C9-C20 labels were written by this agent before inference and were not independently reviewed. Twenty cases, one call per model and one run each still cannot support a ranking by quality, speed or cost. "
            "Label disclosure (reconciliation): the prompt was not blind on C4. The C15-C17 source excerpt states that the earlier native reviews corrected C4 to 'insufficient', and the C18-C20 excerpt gives TypeSafe's 7/8 aggregate. Codex's C4 'insufficient' (and so its 20/20) cannot count as independent agreement with the frozen label; Claude's C4 'contradicted' was given with the same disclosure in its input. The Claude arm cannot be rerun under the one-call limit and is recorded as contaminated on C4; the Codex arm could be rerun on a packet without C15-C20 or on C1-C8 alone, which this reconciliation (no new checks) did not do. "
            "Round-1 note: the round-1 Codex probe (codex exec --sandbox read-only --ephemeral with a positional prompt, without --ignore-user-config or --disable hooks) ran while $HOME/.codex/hooks.json registered ai-memory SessionStart, UserPromptSubmit and other hooks against the live store at 127.0.0.1:49374. Read-only determination: it did not reach session start. Its only stderr line is 'Reading additional input from stdin...', stdout is empty, and it was reaped by timeout 300. In the codex-cli 0.155.1 source (rust-v0.155.1 codex-rs/exec/src/lib.rs), that message is printed by read_prompt_from_stdin just before a blocking read_to_end on stdin, inside resolve_root_prompt (line 941), which runs before the in-process app-server client starts (line 973) and before thread/start. Hooks run inside that app server, so no ai-memory hook fired and nothing was written to the live store by this call (support/reconciliation/codex-round1-session-start.txt, codex-user-hooks-registration.txt). This rests on the installed version string matching the upstream tag; the live store itself was not queried, per the rules."),
    artifacts=[f"support/typesafe-extension/{{cases.json,labels-frozen.json,schema.json,prompt.txt,freeze-hashes.txt}}", f"{FX}/g5-g10-reviews/*", "support/reconciliation/{codex-round1-session-start.txt,codex-user-hooks-registration.txt}", f"{BP}/{{build_typesafe_extension.py,run_review_call.sh,score_reviews.py}}"])
R[7] = dict(slug="independent-queries-tokenusage", outcome="advanced", evidence_class="local_integration", checked_at="2026-09-23T02:48:49Z",
    commands=["curl https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16/resolve/c0c9fea93ea424587517f2c59e20db9f1d6bf615/README.md; extract the first python block under 'Recommended Retrieval Endpoint'; substitute only the endpoint URL",
              RUN047 + "  (gap-7 step: promptfoo eval -c examples/promptfoo-nemotron-upstream/promptfooconfig.yaml --no-cache -j 1 -o results.json, python = pinned venv with numpy 2.5.3 / requests 2.34.2)"],
    results={"upstream_example_hashes": "original 09df5e6a..., executed c4b48632..., both equal to the 2026-09-21 qualification.json values",
             "upstream_four_query_rerun": "exit 0; ✓ 1 passed (100%), 'All assertions passed' (upstream4.stdout, g7-upstream4/results.json)",
             "upstream_tokenUsage_cost": "promptfoo tokenUsage total 0, numRequests 1; cost 0 (zero placeholders: the exec provider reports no usage)",
             "upstream_measured_tokens": "vllm:prompt_tokens_total +336 and request_success_total{stop} +8 over the run window (vllm-metrics.txt), consistent with 8 texts; quiet control windows +0",
             "independent_queries": "the 30 held-out queries (gap 0) were written independently of NVIDIA's four rows; with the Python provider returning the endpoint's billed_units, promptfoo itself reports tokenUsage total 2040 over 30 requests, equal to the +2040 metric delta",
             "cost": "cost 0 in both results.json files: a placeholder, because no price exists for the local endpoint"},
    limits=("Token usage is now recorded both by promptfoo (independent queries) and by the endpoint meter (upstream four-query run). The four-query assertion's own promptfoo counters remain zero placeholders, because the upstream script prints only a matrix and was not modified. "
            "Cost remains unreported: promptfoo's cost field is a 0 placeholder, and no per-token price or energy measurement exists for the local vLLM endpoint. This is the remaining arm, so the outcome is advanced. The metric deltas are model-scoped counters; quiet control windows showed no background traffic, but they are not exclusive per-evaluation billing."),
    artifacts=[f"{FX}/g7-upstream4/*", f"{FX}/g0-g4-g7/{{upstream4.stdout,upstream4.exit,upstream4.wall_ms,vllm-metrics.txt,pf-heldout-results.json}}"])
R[9] = dict(slug="inspect-mlflow-local-vllm", outcome="advanced", evidence_class="native_proven", checked_at="2026-09-23T02:52:39Z",
    commands=[INSTALL,
              "git clone --depth 1 --branch 0.3.268 --filter=blob:none --sparse https://github.com/UKGovernmentBEIS/inspect_ai.git inspect-src && git sparse-checkout set examples (HEAD f9837f6c577da1bf89223f0575d4cb218940a79f)",
              "VLLM_USE_FLASHINFER_SAMPLER=0 VLLM_USE_V2_MODEL_RUNNER=0 HF_HUB_OFFLINE=1 VLLM_CACHE_ROOT=.../fixround/vllm-cache XDG_CACHE_HOME=.../fixround/xdg-cache ecosystem-bounded-run <existing vllm-0.25.0 python> vllm serve $HOME/.local/share/codex-ecosystem/models/qwen2.5-7b-instruct-awq-b250375 --served-model-name qwen2.5-7b-instruct-awq --host 127.0.0.1 --port 18431 --max-model-len 4096 --max-num-seqs 4 --gpu-memory-utilization 0.40 --enforce-eager --no-enable-log-requests (attempt 3; attempts 1-2 failed: 'UVA is not available', then FlashInfer JIT 'Could not find nvcc')",
              f"bash {BP}/run_g9.sh .../fixround/g9 .../fixround/g9-out .../fixround/pinned-venv .../fixround/inspect-src/examples <gap-4 heldout inspect log>  (inspect eval hello_world.py / security_guide.py --model vllm/qwen2.5-7b-instruct-awq with VLLM_BASE_URL=http://127.0.0.1:18431/v1; mlflow server --host 127.0.0.1 --port 15005 with a temp sqlite store; log_inspect_to_mlflow.py; REST runs/get; kill)",
              "kill <vllm pid on 18431>; ss -ltn | grep -c ':18431 '"],
    results={"chat_probe": "resident 8231 models ['nvidia/Nemotron-3-Embed-1B-BF16'], POST /v1/chat/completions status 404; temporary 18431 models ['qwen2.5-7b-instruct-awq'], status 200 (chat-endpoint-probe.txt)",
             "upstream_examples_unmodified": "hello_world.py and security_guide.py sha256 in upstream-example.sha256 (sparse checkout, no edits)",
             "inspect_exit_codes": "hello_world 0, security_guide 0 (inspect-*.exit)",
             "inspect_results": "hello_world exact mean 1.000, 37 tokens [I: 34, O: 3]; security_guide model_graded_fact accuracy 0.688 (stderr 0.120), 9,510 tokens [I: 5,590, O: 3,920]",
             "mlflow_runs": {"2d1037033bff45b5ba8970b90ebd9d10": "hello_world FINISHED", "4b176a82717c4de79d631d2aeae7efca": "security_guide FINISHED", "c2c725db27ef4b488101f86e759e47c4": "heldout_retrieval (gap 4 log) FINISHED"},
             "mlflow_retrieval": "status and metrics from /api/2.0/mlflow/runs/get (mlflow-run-*.json); mlflow-log exit 0",
             "servers_stopped": "MLflow: 0 listeners on :15005 and no mlflow server process. vLLM chat: 0 listeners on :18431; GPU memory back to 5540 MiB (mlflow-stop-verification.txt). Connect probes (reconciliation restatement): at 02:52Z a curl http connect to 127.0.0.1:15005 timed out (curl exit 28, mlflow-after-stop.txt) and Python socket connects to 15005 and to the unused control port 15999 raised TimeoutError, whereas the earlier gap-2 curl https check of the stopped mirror on closed port 18443 was refused (curl exit 7, g2-mirror-after-stop.txt). The note inside mlflow-stop-verification.txt that any closed loopback port times out on this host is contradicted by that refusal and is withdrawn; the cause of the timeouts (port, timing or other host state) was not determined. Shutdown rests on the listener counts and the process recheck, not on the connect probes."},
    limits=("The next_check arms are all executed: fresh pinned prefix, one upstream Inspect example (two were run) against local vLLM, MLflow logging, run IDs and exit codes. The gap text also names CI failure repair and security finding quality, which this check does not exercise. They remain unestablished, so the outcome is advanced. "
            "The local chat model is the pre-existing Qwen2.5-7B-Instruct-AWQ copy under the ecosystem models directory (read only). security_guide grades with the same model it evaluates. A temporary second vLLM ran on loopback beside the resident embedding service and was stopped. "
            "The resident service was not touched apart from a read-only /v1/models, 404 chat probe and /metrics reads."),
    artifacts=[f"{FX}/g9/*", f"{FX}/g4-g9-pinned-install.log", f"{BP}/{{run_g9.sh,log_inspect_to_mlflow.py}}"])
R[10] = dict(slug="typesafe-c4-agreement", outcome="advanced", evidence_class="native_proven", checked_at="2026-09-23T02:55:07Z",
    commands=[REVIEW.format(who="codex"), REVIEW.format(who="claude"), SCORE + "  (shared with gap 5; C1-C8 are the identical TypeSafe case set)"],
    results={"schema_validated": "Codex and Claude outputs both validate against schema.json (agreement.json schema_validation)",
             "agreement_C1_C8": {"codex": "8/8 vs frozen source-review labels, 7/8 vs TypeSafe", "claude": "6/8 vs frozen labels, 7/8 vs TypeSafe", "typesafe": "7/8 vs frozen labels"},
             "C4": {"frozen_label": "insufficient", "codex": "insufficient (contaminated: label disclosed in the same prompt)", "claude": "contradicted (contaminated: label disclosed in the same prompt)", "typesafe_2026_09_21": "contradicted", "prior_codex_review": "insufficient", "prior_claude_review": "insufficient"},
             "baseline_match": "Identical case set (C1-C8) and schema-validated output, but not blind on C4: the same prompt's C15-C17 source excerpt (prompt.txt lines 193-215) says the earlier native reviews 'corrected C4 to `insufficient`', and C18-C20 (lines 217-239) disclose TypeSafe's 7/8 aggregate. No per-case TypeSafe verdicts or label file were in the prompt."},
    limits=("The matched-blind-baseline clause is only partly closed (reconciliation): the native reviews use the identical case set with schema-validated output, but the prompt disclosed the reference C4 label (C15-C17 excerpt) and TypeSafe's 7/8 aggregate (C18-C20). Codex's C4 'insufficient' and its 8/8 therefore cannot count as independent agreement with the frozen label, and the Claude arm, which cannot be rerun under the one-call limit, is recorded as contaminated on C4. A Codex rerun on C1-C8 alone (or a packet without C15-C20) remains open. The C4 disagreement is not resolved: Claude (Sonnet) answered 'contradicted' like TypeSafe despite the disclosure, while Codex, the frozen label and both earlier reviews say 'insufficient'. "
            "The split turns on whether 'not established here' contradicts a universal efficiency claim. Settling it needs an explicit labelling rule or an independent adjudicator, so the outcome is advanced. One call per model; no repeat runs, so run-to-run variance is unknown. This differs from the preregistered expectation ('settled if both arms return schema-valid verdicts'): both arms did return valid verdicts, but the reproduced C4 split leaves one clause of the gap text open."),
    artifacts=[f"{FX}/g5-g10-reviews/agreement.json", f"{FX}/g5-g10-reviews/*", "support/typesafe-extension/*"])

for i, r in R.items():
    p = pre[str(i)]
    receipt = {
        "id": f"foundation__quality-evaluation__gap{i}", "gap_index": i,
        "gap_text_sha256": hashlib.sha256(gaps[i]["text"].encode()).hexdigest(),
        "preregistration": {"written_at": p["written_at"], "label": p["label"], "expectation": p["expectation"], "criteria": p["criteria"],
                            "committed_in": "ebf6ac1 (preregistrations-fixround.json), before any fix-round command"},
        "original_round_preregistration": {"written_at": None, "note": f"Round 1 recorded written_at {ORIG[i]}, a value reconstructed after its runs (raw-output mtimes and eval ids precede it). It is labelled late and superseded; the round-1 artifacts are at commit b37df23."},
        "commands": r["commands"], "results": r["results"], "outcome": r["outcome"], "evidence_class": r["evidence_class"],
        "limits": r["limits"], "checked_at": r["checked_at"], "artifacts": r["artifacts"],
    }
    if str(i) in pre2:
        q = pre2[str(i)]
        receipt["fixround2_preregistration"] = {"written_at": q["written_at"], "label": q["label"], "expectation": q["expectation"], "criteria": q["criteria"],
                                                "committed_in": "1fcd1fe (preregistrations-fixround2.json), before any fix-round-2 command"}
        receipt = {k: receipt[k] for k in ["id", "gap_index", "gap_text_sha256", "preregistration", "fixround2_preregistration"] + [k for k in receipt if k not in ("id", "gap_index", "gap_text_sha256", "preregistration", "fixround2_preregistration")]}
    open(f"{E}{i}-{r['slug']}.json", "w").write(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n")
print("wrote", sorted(R))
