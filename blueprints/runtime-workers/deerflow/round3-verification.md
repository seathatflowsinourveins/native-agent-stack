# DeerFlow round-3 repair verification — 2026-09-27

Draft PR #427; supplied base b98a1cd5; branch claude/runtime-worker-deerflow-20260927.
This is the single offline repair round. The coordinator owns commits, hash
registration, installation and native E2E. No Git metadata, shared evidence
manifest, host install, container or model gateway was mutated/invoked here.

The four supplied inputs were read first: rw3-deerflow-review.json,
rw3-security.json, rw3-deerflow-integrate.json and rw3-common.md. IDs below index
the review arrays (D = DeerFlow; S = security). Other recipes' findings are out of
scope. S9 is split to make the declined UID portion explicit.

## Findings

| ID | Severity | Disposition | Change / evidence |
| --- | --- | --- | --- |
| D1 | blocker | fixed | Engines-on model rejected: recipe.arm_settings; arm regression red exit 1 -> green 0; one-slash common requirement overrides review's two-slash proposal. Sources: user common requirements §1; DF config/app_config.py:432,565. |
| D2 | blocker | fixed | Base URL fixed to control: $DEERFLOW_BASE_URL; derived per-arm environment; attempt window and receipts identify arm/model/base_url/header names. Sources: DF config/app_config.py:432,565; LC base.py:668-670,1220-1242. |
| D3 | blocker | fixed | Inspect OpenAI provider unnecessarily required: e2e/evaluate.py uses --model none; removes key/base URL; supplies --metadata. Grader optional OpenAI import probe no longer gates this provider path. Sources: IA providers.py:361-365,379-391. |
| D4 | major | fixed | Unconditional no-cache disables engines-on cache: No no-cache header. Compression header only engines-on; max effort and temperature omission tested. Sources: LC base.py:1683-1712,3327-3345; user common requirements §1. |
| D5 | major | fixed | No stable machine-readable result: Stable caller run ID; start status/result paths; official Inspect JSON path; native HTTP start/wait/result/cancel; four exit classes. Sources: DF thread_runs.py:923-939,1143-1168,1528-1560; IA _cli/eval.py:1681-1682; log/_log.py:798-820,848-895. |
| D6 | minor | fixed | Skill activation trusts omitted tool status: Corrected serialization comment; bounded frontmatter name required; errors without failure prefix including a stray name line fail activation. Sources: DF client.py:527-564; sandbox/local/local_sandbox.py:813-842. |
| S2 | major | fixed | Model shell reaches other host loopback services: Internal network plus separate fixed per-port nginx forwarder; no raw ai-memory/Qdrant endpoints enabled. Native network enforcement and host bridge paths unmeasured. Sources: CS 06-networks.md:215-218; NG proxy module:305-358,417-457. |
| S3 | major | fixed | E2E inherits persistent tokens/state/network: Fresh two-service Compose graph/project/networks; isolated writable state/work; host-retained QMD seed; no env_file/internal token/Redis connection. Persistent Redis requirepass added. Sources: CS 06-networks.md:215-218; RD redis.conf:1041-1050. |
| S4 | major | fixed | Grader transitive installation unlocked: 96-package hash lock, hash in pins.json, CPython 3.13 Linux x86_64; --require-hashes --only-binary=:all: --no-deps; pip check/version validation. Resolution is not installation acceptance. Sources: UV docs/pip/compile.md:24-28 and installed CLI help; IE GAIA README. |
| S6 | minor | fixed | Credential/ancestor/symlink mounts accepted: Resolved dependency-root allowlist and protected-store ancestor/descendant denial; regression covers .config/native-agent-stack, home ancestor and symlink escape. Sources: CS 05-services.md volume bind contract; repository docs/secret-storage.md. |
| S9a | minor | fixed | Container capability/privilege/root-filesystem hardening missing: All services cap_drop ALL, no-new-privileges, read-only roots/tmpfs. nginx and egress run UID 101. Sources: CS 05-services.md:171-175,1839-1841,1955-1963,2029-2046,2080-2082. |
| S9b | common baseline | declined | Blanket non-root UID for Gateway/frontend/Redis: Current rootless binds and generated private configuration use host-owned 0700/0600 permissions; an arbitrary container UID would break access. Published backend source defaults to root. Keep rootless default UID with all caps dropped until coordinator qualifies mapped-UID/owned-bind lifecycle. Residual is documented, not an upstream non-root absence claim. Sources: DF backend/Dockerfile:94-127; CS 05-services.md:2080-2082; recipe.py owned file permissions. |
| S11 | minor | fixed | Serena dashboard enabled: --enable-web-dashboard false; GUI/off and native command otherwise retained. Sources: SR src/serena/cli.py:291-305,398-400. |
| C2-C3 | common requirements | fixed | Per-arm usage, correlation and effort evidence: Entry store only; private IDs joined/omitted; exact model/path/window fallback without attributed total; positive-reasoning max/nonmax/unknown categories; zero-reasoning count; separate compression delta. Sources: OR callLogs.ts:628-653; compression route:13-24; compressionAnalytics.ts:52-82; LC base.py:934-935,1404-1411,1462-1469. |
| C4-C5 | common requirements | fixed | Native dispatch, invocation accounting and receipt boundary: PAT native background run API; stable artifacts/private ledger; native RunEvent envelopes and lead-agent result; independent SQL checks, host-captured forwarder log, all receipt paths outside model mounts. Actual OTel/native run reconciliation remains a host gate. Sources: DF chat.sh:24-90,140-164; thread_runs.py:223-242,923-939,1143-1168,1528-1560; runtime/journal.py:512-522. |

Full source identities/file lines, exact commands, exit codes and returned
stdout/stderr are in [round3-verification.json](round3-verification.json).
The [README](README.md) links the upstream files and gives exact dispatch,
arm-switch, installation and E2E commands.

## Source and skill discovery

The installed search-first and find-skills guidance was used inline; no worker
was spawned and no skill was installed. The best-matching reference is DeerFlow's
own pinned claude-to-deerflow skill and maintained Gateway API. A new MCP server
was not built. Installed checks found uv 0.12.17 and inspect 0.3.266 on PATH;
Docker and DeerFlow were not found on PATH. This does not claim they are absent
from the host. The builder Python cannot import the pinned grader packages, so
the real upstream scorer control is explicitly skipped.

Direct shell gh could not connect; the allowed read-only Context Mode gh channel
returned the v2.1.0 release and pinned source. The web open operation was unsupported.
Those channel failures are not absence evidence. The LangChain 1.2.1 sdist was
fetched in memory and its SHA256 matched pins.json. No code from that archive was
installed or run. Compose, nginx, Redis, Serena, uv, Inspect and OmniRoute source
references are pinned in the JSON record.

The 96-package grader lock was resolved with installed uv 0.12.17 and
re-resolved with a wheel-only constraint at CPython 3.13 / Linux x86_64. Both
produced SHA256 388083f96839d48ab92b99ea7a3a8fe01f978e5d73374fd8d4ed4dc00adaa341.
Two exploratory install **dry-runs** failed before installation (no venv, then
the Context Mode host's externally-managed Python 3.12). No override or install
followed; the target-specific wheel-only compile supplied the artifact check.

## Test-first evidence

Tests use the seams authorized by the user: recipe rendering, gateway payloads,
isolated transport, private receipt accounting, native API dispatch and official
grader result transport. External clients/containers are doubled. These are local
integration contracts and synthetic fixtures, not unchanged upstream acceptance.

The JSON log preserves each red/green command pair, intermediate failures and the
final acceptance output. Red cases cover arm selection/endpoint, max effort,
skill/frontmatter failure, correlated usage, lock/install flags, internal-network
hardening, fresh attempt state, NoModel grading/result paths, native dispatch and
compression, lifecycle and installed entry points, duplicate IDs, ambiguous
create retries, non-root nginx, setup status and native RunEvent envelopes.
Exit 1 is the expected failing unittest run; the corresponding repaired run is
exit 0. The first Inspect-green attempt failed a stale source-string assertion
and is retained alongside its corrected pass.

## Correction and anti-pattern log

| Mistake or incomplete assumption | Correction and verification path |
| --- | --- |
| Review proposed sharedgw/cx/... | The explicit common contract requires sharedgw/gpt-6-astra-max. The arm regression accepts this slug and rejects the two-slash variant; no gateway probe was repeated. |
| Skill ToolMessage values were said to carry status | DeerFlow@345f08be client.py:527–564 omits that field in both serializations. A returned SKILL.md needs actual bounded frontmatter with the right name. Both missing-prefix error and stray-name controls failed before repair. |
| Initial HTTP result fixture reused the SSE message shape | The /messages API returns RunEvent envelopes, with AIMessage.model_dump() in content (runtime/events/store/base.py:32–43,54–55; runtime/journal.py:512–522 at the DeerFlow pin). Updating the fixture to that pinned shape failed (exit 1); unwrapping it passed (exit 0). Lead-only result selection follows journal.py:327–344. |
| Duplicate correlation rows could choose the first row and silently claim a total | A conflicting duplicate control failed; duplicates now produce incomplete/unavailable attribution, not a sum or an arbitrary retained row. |
| Lost create response classified as setup failure | A native run may already exist. The failed control now retains a pending slot and repeats the same native idempotency key, with one ledger entry on acknowledgment. |
| A dry-run used the Context Mode interpreter rather than the lock target | The retained externally-managed refusal is preserved; the earlier no-venv refusal is recorded as a session observation without raw output. No package was installed. Explicit target/wheel-only uv compilation reproduced the lock byte-for-byte. |
| Assuming read-only nginx could keep root startup semantics after dropping caps | nginx and the forwarder use UID 101; nginx config/PID/temp files have writable locations, while the image's /etc/nginx remains intact. Native execution is still a host gate. |

This recipe-local log carries the corrections for the coordinator; the shared
harness-defaults anti-pattern log is not edited from this owned repair lane.

## Host verification still required

1. Install the coordinator's skills manifest/CLI extension and the hash-locked
   CPython 3.13 grader. Run the unchanged GAIA known-pass/known-fail controls.
2. Verify all pinned image metadata, Compose config, read-only/tmpfs startup,
   Redis AUTH, nginx UID 101 and the actual mapped-UID lifecycle. Gateway,
   frontend and Redis still use the release/default UID (S9b).
3. Test both allowed gateway ports through their selected forwarder and denial
   of the other gateway port, direct host-loopback/bridge listeners, ai-memory,
   Qdrant, metadata services and CONNECT. Validate rootless internal-network
   behavior before claiming confinement. Public web egress and the two remote
   MCP services remain disabled under this policy.
4. Establish in-container MCP dependency/interpreter visibility, QMD snapshot
   behavior and real skill reads. Confirm the released clients' payload/stream
   hook sends session/idempotency, compression only on engines-on, and max effort
   for lead, child and summarization calls.
5. Initialize/login to DeerFlow, mint the scoped PAT, exercise native
   start/wait/result/cancel and ambiguous-start/restart recovery. Reconcile
   ledger/native run/console rows and Claude child-usage/OTel tool events.
6. Verify the 20129 store path and actual correlation/effort rows, response
   headers for all call roles, final-row flush timing, and management access to
   compression analytics. Missing data remains incomplete, never zero savings.
7. Acquire permitted frozen GAIA no-attachment validation inputs, run both arms,
   retain native logs and failures, and qualify timeout/network cleanup.
   General web-research coverage is not claimed with restricted egress.
8. Re-register changed hashes in manifests/evidence.json and rerun the
   repository validator. The only allowed current failure is changed-file
   SHA256/byte-count mismatch; it is retained as a failure.

## Final acceptance


The unittest command exited 0: 39 tests, with 38 executed and one explicitly
skipped because the pinned upstream grader is unavailable in this builder.
The validator exited 1 only for SHA-256/byte-count mismatches in the 16 changed
tracked files. This is a retained failure; the coordinator must re-register
hashes. The diff whitespace check exited 0 with no output.

Paths in returned output use the substitutions declared in the JSON record.
The complete output below retains the synthetic fixtures' negative/setup JSON;
those lines are expected test observations, not failed unittest outcomes.

### final-suite

Command (exit 0):

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_deerflow -v
```

Returned output:

```text
test_adapter_preserves_known_pass_and_fail_without_a_local_verdict (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_adapter_preserves_known_pass_and_fail_without_a_local_verdict) ... ok
test_adapter_rejects_missing_malformed_and_unfinished_output (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_adapter_rejects_missing_malformed_and_unfinished_output) ... ok
test_gateway_headers_preserve_affinity_and_new_call_identity (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_gateway_headers_preserve_affinity_and_new_call_identity) ... ok
test_gateway_reader_is_read_only_and_uses_only_approved_columns (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_gateway_reader_is_read_only_and_uses_only_approved_columns) ... ok
test_gateway_rejects_non_gpt6_model_routes (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_gateway_rejects_non_gpt6_model_routes) ... ok
test_gateway_structured_output_uses_upstream_tool_calling (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_gateway_structured_output_uses_upstream_tool_calling) ... ok
test_grader_install_and_launch_use_exact_upstream_pins (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_grader_install_and_launch_use_exact_upstream_pins) ... ok
test_inspect_solver_transports_only_input_and_preserves_upstream_task (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_inspect_solver_transports_only_input_and_preserves_upstream_task) ... ok
test_literal_cleanup_continues_after_already_absent_resource (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_literal_cleanup_continues_after_already_absent_resource) ... ok
test_mcp_launches_preserve_the_adoption_commands (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_mcp_launches_preserve_the_adoption_commands) ... ok
test_model_context_and_container_contract (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_model_context_and_container_contract) ... ok
test_native_trace_distinguishes_skill_inventory_metadata_and_loads (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_native_trace_distinguishes_skill_inventory_metadata_and_loads) ... ok
test_native_trace_does_not_count_failed_children_as_completed (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_native_trace_does_not_count_failed_children_as_completed) ... ok
test_owned_compose_resources_and_loopback_ports (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_owned_compose_resources_and_loopback_ports) ... ok
test_pins_and_script_boundaries (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_pins_and_script_boundaries) ... ok
test_real_upstream_gaia_known_pass_and_fail_controls (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_real_upstream_gaia_known_pass_and_fail_controls) ... skipped 'pinned upstream grader unavailable; installation prohibited in builder'
test_renderer_and_qmd_snapshot_keep_state_owned_and_index_scoped (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_renderer_and_qmd_snapshot_keep_state_owned_and_index_scoped) ... ok
test_reviewable_recipe_and_empty_result_rejection (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_reviewable_recipe_and_empty_result_rejection) ... ok
test_round3_arms_render_endpoint_model_and_only_selected_header (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_arms_render_endpoint_model_and_only_selected_header) ... ok
test_round3_attempt_has_fresh_state_and_network_and_no_stack_secrets (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_attempt_has_fresh_state_and_network_and_no_stack_secrets) ... ok
test_round3_compression_deltas_are_separate_and_reject_counter_resets (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_compression_deltas_are_separate_and_reject_counter_resets) ... ok
test_round3_container_network_hardening_and_resolved_mount_guards (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_container_network_hardening_and_resolved_mount_guards) ... ok
test_round3_dispatch_ambiguous_start_is_incomplete_and_retries_same_native_key (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_dispatch_ambiguous_start_is_incomplete_and_retries_same_native_key) ... ok
test_round3_dispatch_cli_accepts_prompt_after_options (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_dispatch_cli_accepts_prompt_after_options) ... ok
test_round3_dispatch_pat_uses_header_and_refuses_redirects_and_unsafe_token_files (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_dispatch_pat_uses_header_and_refuses_redirects_and_unsafe_token_files) ... ok
test_round3_dispatch_reports_negative_setup_and_missing_evidence (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_dispatch_reports_negative_setup_and_missing_evidence) ... ok
test_round3_dispatch_start_wait_result_uses_pat_native_runs_and_stable_paths (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_dispatch_start_wait_result_uses_pat_native_runs_and_stable_paths) ... ok
test_round3_duplicate_correlation_is_incomplete_and_dispatch_counts_are_sanitized (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_duplicate_correlation_is_incomplete_and_dispatch_counts_are_sanitized) ... ok
test_round3_grader_install_is_hash_locked_and_wheel_only (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_grader_install_is_hash_locked_and_wheel_only) ... ok
test_round3_inspect_launch_has_no_model_and_publishes_stable_result (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_inspect_launch_has_no_model_and_publishes_stable_result) ... {"result_path": "fixture"}
{"status_path": "<WORKTREE>/.round3-tmp/tmpcqyj5hqf/state/runs/frozen-run/status.json", "result_path": "<WORKTREE>/.round3-tmp/tmpcqyj5hqf/state/runs/frozen-run/result.json"}
{"result_path": "<WORKTREE>/.round3-tmp/tmpcqyj5hqf/state/runs/frozen-run/result.json", "exit_code": 1}
ok
test_round3_inspect_verdict_rejects_incomplete_evidence (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_inspect_verdict_rejects_incomplete_evidence) ... ok
test_round3_installed_entrypoints_have_their_local_dependencies (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_installed_entrypoints_have_their_local_dependencies) ... ok
test_round3_lifecycle_rejects_active_dispatch_and_recreates_selected_arm (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_lifecycle_rejects_active_dispatch_and_recreates_selected_arm) ... ok
test_round3_missing_host_setup_still_writes_status_and_result (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_missing_host_setup_still_writes_status_and_result) ... {"status_path": "<WORKTREE>/.round3-tmp/tmpsseosh8_/runs/missing/status.json", "result_path": "<WORKTREE>/.round3-tmp/tmpsseosh8_/runs/missing/result.json"}
{"result_path": "<WORKTREE>/.round3-tmp/tmpsseosh8_/runs/missing/result.json", "exit_code": 2}
ok
test_round3_nginx_and_preflight_match_hardened_configuration (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_nginx_and_preflight_match_hardened_configuration) ... ok
test_round3_usage_correlates_entry_gateway_once_and_separates_effort (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_round3_usage_correlates_entry_gateway_once_and_separates_effort) ... ok
test_skills_use_coordinator_project_installer (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_skills_use_coordinator_project_installer) ... ok
test_tool_limits_are_enforced_not_only_described (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_tool_limits_are_enforced_not_only_described) ... ok
test_transport_runs_owned_container_and_retains_failed_attempts (tests.test_runtime_worker_deerflow.DeerFlowRecipeTests.test_transport_runs_owned_container_and_retains_failed_attempts) ... ok

----------------------------------------------------------------------
Ran 39 tests in 0.406s

OK (skipped=1)
```

### final-validator-completion

Command (exit 1):

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate.py
```

Returned output:

```text
Publication validation failed:
blueprints/runtime-workers/deerflow/README.md: SHA-256 mismatch
blueprints/runtime-workers/deerflow/README.md: byte count mismatch
blueprints/runtime-workers/deerflow/compose.json.template: SHA-256 mismatch
blueprints/runtime-workers/deerflow/compose.json.template: byte count mismatch
blueprints/runtime-workers/deerflow/config.yaml.template: SHA-256 mismatch
blueprints/runtime-workers/deerflow/config.yaml.template: byte count mismatch
blueprints/runtime-workers/deerflow/e2e/receipt.py: SHA-256 mismatch
blueprints/runtime-workers/deerflow/e2e/receipt.py: byte count mismatch
blueprints/runtime-workers/deerflow/e2e/run.py: SHA-256 mismatch
blueprints/runtime-workers/deerflow/e2e/run.py: byte count mismatch
blueprints/runtime-workers/deerflow/extensions_config.json.template: SHA-256 mismatch
blueprints/runtime-workers/deerflow/extensions_config.json.template: byte count mismatch
blueprints/runtime-workers/deerflow/pins.json: SHA-256 mismatch
blueprints/runtime-workers/deerflow/pins.json: byte count mismatch
blueprints/runtime-workers/deerflow/recipe.py: SHA-256 mismatch
blueprints/runtime-workers/deerflow/recipe.py: byte count mismatch
blueprints/runtime-workers/deerflow/run-e2e.sh: SHA-256 mismatch
blueprints/runtime-workers/deerflow/run-e2e.sh: byte count mismatch
blueprints/runtime-workers/deerflow/runtime/gateway-start.sh: SHA-256 mismatch
blueprints/runtime-workers/deerflow/runtime/gateway-start.sh: byte count mismatch
blueprints/runtime-workers/deerflow/runtime/gateway_headers.py: SHA-256 mismatch
blueprints/runtime-workers/deerflow/runtime/gateway_headers.py: byte count mismatch
blueprints/runtime-workers/deerflow/runtime/gateway_model.py: SHA-256 mismatch
blueprints/runtime-workers/deerflow/runtime/gateway_model.py: byte count mismatch
blueprints/runtime-workers/deerflow/runtime/nginx-start.sh: SHA-256 mismatch
blueprints/runtime-workers/deerflow/runtime/nginx-start.sh: byte count mismatch
blueprints/runtime-workers/deerflow/runtime/preflight.py: SHA-256 mismatch
blueprints/runtime-workers/deerflow/runtime/preflight.py: byte count mismatch
blueprints/runtime-workers/deerflow/runtime/redis-start.sh: SHA-256 mismatch
blueprints/runtime-workers/deerflow/runtime/redis-start.sh: byte count mismatch
tests/test_runtime_worker_deerflow.py: SHA-256 mismatch
tests/test_runtime_worker_deerflow.py: byte count mismatch
```

### final-diff-check

Command (exit 0):

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0 git diff --check
```

Returned output: empty:

```text
```

Scratch cleanup exited 0; its returned output was:

```text
Removed .round3-tmp/rechecked.lock and empty .round3-tmp
Cache files/directories: []
```
