# OpenHands round-3 repair verification — 2026-09-27

This is the single repair round for draft PR #425, baseline 17460572, branch
claude/runtime-worker-openhands-20260927. The coordinator owns commits and
manifests/evidence.json. This builder changed only this recipe and its unit test;
no Git metadata operations, installations, containers, model calls or gateway
requests were performed. All Python commands set PYTHONDONTWRITEBYTECODE=1.

The review inputs were rw3-openhands-review.json, rw3-security.json,
rw3-openhands-integrate.json and rw3-common.md. These are coordinator inputs,
not upstream acceptance evidence. The common requirements override the older
two-slash engines-on route and downstream-20128 accounting suggestion.

**Evidence class:** offline adapter contracts, synthetic fixtures, source review
and publication checks. No unchanged upstream suite, native server execution,
official grading, host network acceptance, A/B result or token saving is claimed.
The independent trace gate remains deliberately incomplete: evidence_complete
is false, so a resolved task currently exits 2.

[Source index and correction log](../research.md#source-index-used-by-the-repair)
names every pinned upstream implementation used below. R1–R18 refer to that
index. [README](../README.md) contains the full operational contract and the
required Workflow dispatch, Arms, Usage accounting and Security posture sections.

## Findings and disposition

IDs C1–C8 and S1–S12 are one-based positions in the Claude and security arrays.
A disposition of fixed means the local defect is repaired with offline evidence;
it does not imply that a native host run has passed.

| ID | Severity | Disposition | Evidence and reason |
| --- | --- | --- | --- |
| C1 | major | Fixed | recipe.py arm_config accepts sharedgw/gpt-6-astra-max, rejects two slashes/other families, and retains control variants. Round 01. Common arm contract; R5 provider config. |
| C2 | major | Fixed | OPENHANDS_BASE_URL is validated per arm and propagated to native request/window/receipt with model and header names. R2/R5; rounds 01,03,08. |
| C3 | major | Fixed | receipt.py selects exactly one entry database, matches expected model/path, sums each returned row once and preserves unknown totals. Separate reasoning/no-reasoning counts and compression delta. R13/R14; rounds 02,07. The common contract overrides the review's 20128 engines-on advice. Entry model/database matching remains a host check. |
| C4 | major | Fixed | Native start/wait/result adapter, stable run/arm directory, early status, deterministic JSON receipt path, deadlines and distinct exits. R1–R3; rounds 05,07,08,10,11. |
| C5 | major | Declined: coordinator-owned | The user expressly forbids editing manifests/evidence.json. Run and retain validate.py; coordinator re-registers changed hashes/new evidence and obtains a clean publication pass. No hashes were bypassed. |
| C6 | minor | Fixed | Setup/preflight failures write status/receipt and return 3; official negatives return 1; incomplete evidence returns 2. R10 report contract; rounds 05,09,11. |
| C7 | minor | Fixed | clone_command queries pinned SWE-bench REPO_BASE_COMMIT_BRANCH before clone/reset. R10 python.py:271-277; round 05. |
| C8 | minor | Fixed | Official grader transport adds names/labels and identity gates, without local CPU/memory/PID limits. R10 docker_build.py:516-524; rounds 04,09. |
| S2 | major | Declined: host enforcement unverified | Remote MCPs disabled; resolved mount allowlist, scoped per-arm networks and a fresh host policy/probe receipt now fail closed. R12 supports DOCKER-USER filtering, but its rootless namespace placement/effects were not observed; no Docker or host mutation is authorized here. The operator assertion is not an implemented firewall. Grader host-service isolation also needs separate qualification while retaining official grading options. Round 04 and round 12 prove gates only. |
| S4/S5 | major, cross-cutting | Fixed for this recipe | Upstream lock hash, uv 0.12.17, hashed build tools, --locked --no-build-isolation --inexact and the explicitly seeded interpreter; automatic Python downloads disabled. R8/R9 and installed uv help; rounds 06,15. Other recipes are outside owned scope. |
| S6 | minor | Fixed | Resolve symlinks before exact tool/document allowlisting; reject home ancestors and auth-store intersections. R17 selected adoption layout; round 04. |
| S7 | minor | Declined: host build isolation | Lock/build inputs and image digests are secured, mutable pulls denied, pre-pulled identity rechecked (R8–R11; rounds 06,09,15). The grader build still executes pinned upstream code on the host. A container-built host venv/interpreter and Docker transport have not been qualified; installation/container experiments are prohibited this round. This residual is documented, not claimed eliminated. |
| S9 | minor, cross-cutting | Fixed for model containers | UID/GID 10001, capability drop, no-new-privileges, read-only root and scoped temporary home. Installer remains root only for owned offline writes. R4; rounds 04,13. Official grading options stay upstream per the common contract. |
| S10 | minor | Fixed trust vulnerability; observer deferred | Bounded descriptor-relative no-follow regular-file reads reject symlink/FIFO/oversize input. Worker trace/versions/skills are explicitly untrusted and cannot make evidence_complete true. R16/R18; round 02. An independent trace observer is not implemented or qualified; canonical REST dispatch does not export legacy standalone callback events. |
| S12 | minor | Fixed | Installer sees only worker venv/cache writable; no writable parent alias reaches the recipe snapshot. Round 06; existing hashed wheel install retained. |
| Local correction | minor | Fixed | Fixture identifiers are constructed at runtime; publication policy is reused unchanged. R17 and round 14. |

S1/S3/S8/S11 identify other recipes and were not changed. The required
cross-cutting network, installation and hardening requirements are accounted
for above.

## Test-first record

For each implementation slice the test was extended before running red, then
the source was changed and green run. The test seam is the user-requested
tests.test_runtime_worker_openhands public recipe/host/dispatch boundary.
No test installs packages, starts Docker, sends a model request or uses Git to
create/stage/commit a repository. External operations are mocked. Static
installer command checks are explicitly source-contract checks.

[round3-commands.json](round3-commands.json) retains full returned outputs and
exit codes. Only private worktree/interpreter prefixes, the obsolete container
home prefix and the synthetic conversation identifier are replaced by labelled
placeholders. Timings, failures and intermediate failed runs are preserved.
The first host implementation still failed with an import error (exit 1);
the corrected host implementation passed (exit 0). This failed condition is
retained rather than replaced by the later pass.

| Slice | Fail first | Final pass |
| --- | --- | --- |
| 01 Arms | 1: Ran 1 test in 0.005s; FAILED (failures=1, errors=8) | 0: Ran 1 test in 0.003s; OK |
| 02 Entry-gateway accounting and untrusted inputs | 1: Ran 8 tests in 0.103s; FAILED (errors=2) | 0: Ran 8 tests in 0.166s; OK |
| 03 Native request and response headers | 1: Ran 2 tests in 0.011s; FAILED (errors=2) | 0: Ran 15 tests in 0.036s; OK |
| 04 Mounts, non-root model container, official limits | 1: Ran 4 tests in 0.043s; FAILED (failures=2, errors=2) | 0: Ran 4 tests in 0.035s; OK |
| 05 Host failure paths, clone mapping and exits | 1: Ran 13 tests in 0.354s; FAILED (errors=4) | 0: Ran 13 tests in 0.377s; OK |
| 06 Installer mounts, locks and image identity | 1: Ran 2 tests in 0.042s; FAILED (failures=1, errors=1) | 0: Ran 2 tests in 0.040s; OK |
| 07 REST dispatch | 1: Ran 4 tests in 0.009s; FAILED (errors=4) | 0: Ran 4 tests in 0.049s; OK |
| 08 Native launch and module preload | 1: Ran 7 tests in 0.062s; FAILED (errors=3) | 0: Ran 7 tests in 0.072s; OK |
| 09 Grader boundary | 1: Ran 18 tests in 0.399s; FAILED (failures=3, errors=2) | 0: Ran 18 tests in 0.431s; OK |
| 10 Lifecycle and removal | 1: Ran 11 tests in 0.093s; FAILED (failures=3) | 0: Ran 11 tests in 0.088s; OK |
| 11 Host patch export | 1: Ran 2 tests in 0.045s; FAILED (failures=1, errors=1) | 0: Ran 2 tests in 0.042s; OK |
| 12 Host network template | 1: Ran 1 test in 0.001s; FAILED (errors=1) | 0: Ran 1 test in 0.000s; OK |
| 13 Container home | 1: Ran 1 test in 0.022s; FAILED (failures=1) | 0: Ran 1 test in 0.021s; OK |
| 14 Publication-safe synthetic fixture | 1: Ran 1 test in 0.009s; FAILED (failures=1) | 0: Ran 12 tests in 0.119s; OK |
| 15 Grader interpreter selection | 1: Ran 1 test in 0.002s; FAILED (failures=1) | 0: Ran 2 tests in 0.047s; OK |
| 16 Collected result retry | 1: Ran 1 test in 0.032s; FAILED (failures=1) | 0: Ran 12 tests in 0.101s; OK |

The initial required unit run passed 56 tests, and the initial publication run
failed with changed-file hashes plus the literal-fixture identifier. Round 14
corrected that publication issue. Round 15 explicitly keeps uv sync on the
hash-seeded interpreter. A subsequent full run passed 58 tests; final inspection
then reproduced and repaired the collected-result retry bug in round 16.
Final acceptance results follow at the end of this
record.

## Exact red and green commands

All commands ran from the owned worktree. The temporary test directory is
inside the worktree and removed after verification.

### 01: Arms

**01-arms-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_explicit_arms_keep_one_slash_routes_and_compression_separate -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 1 test in 0.005s

FAILED (failures=1, errors=8)
```

**01-arms-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_explicit_arms_keep_one_slash_routes_and_compression_separate -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 1 test in 0.003s

OK
```

### 02: Entry-gateway accounting and untrusted inputs

**02-receipts-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsReceiptTests -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 8 tests in 0.103s

FAILED (errors=2)
```

**02-receipts-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsReceiptTests -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 8 tests in 0.166s

OK
```

### 03: Native request and response headers

**03-worker-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_worker_arm_headers_and_response_correlation_capture tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_native_start_request_uses_sdk_serialization_and_shared_agent -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 2 tests in 0.011s

FAILED (errors=2)
```

**03-worker-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsRecipeTests -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 15 tests in 0.036s

OK
```

### 04: Mounts, non-root model container, official limits

**04-security-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_model_container_is_nonroot_and_network_is_explicit tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_mount_allowlist_checks_resolved_targets_and_secret_ancestors tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_remote_mcp_services_are_not_registered_in_model_network tests.test_runtime_worker_openhands.OpenHandsUpstreamAdapterTests.test_official_grader_container_transport_preserves_upstream_settings -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 4 tests in 0.043s

FAILED (failures=2, errors=2)
```

**04-security-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_model_container_is_nonroot_and_network_is_explicit tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_mount_allowlist_checks_resolved_targets_and_secret_ancestors tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_remote_mcp_services_are_not_registered_in_model_network tests.test_runtime_worker_openhands.OpenHandsUpstreamAdapterTests.test_official_grader_container_transport_preserves_upstream_settings -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 4 tests in 0.035s

OK
```

### 05: Host failure paths, clone mapping and exits

**05-host-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsUpstreamAdapterTests -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 13 tests in 0.354s

FAILED (errors=4)
```

**05-host-green**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsUpstreamAdapterTests -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 13 tests in 0.374s

FAILED (errors=1)
```

**05-host-green-final**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsUpstreamAdapterTests -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 13 tests in 0.377s

OK
```

### 06: Installer mounts, locks and image identity

**06-install-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsUpstreamAdapterTests.test_install_actually_uses_narrow_mounts_and_grader_lock tests.test_runtime_worker_openhands.OpenHandsUpstreamAdapterTests.test_grader_refuses_unpinned_images_and_does_not_pull_mutable_tags -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 2 tests in 0.042s

FAILED (failures=1, errors=1)
```

**06-install-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsUpstreamAdapterTests.test_install_actually_uses_narrow_mounts_and_grader_lock tests.test_runtime_worker_openhands.OpenHandsUpstreamAdapterTests.test_grader_refuses_unpinned_images_and_does_not_pull_mutable_tags -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 2 tests in 0.040s

OK
```

### 07: REST dispatch

**07-dispatch-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsDispatchTests -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 4 tests in 0.009s

FAILED (errors=4)
```

**07-dispatch-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsDispatchTests -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 4 tests in 0.049s

OK
```

### 08: Native launch and module preload

**08-native-launch-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsDispatchTests -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 7 tests in 0.062s

FAILED (errors=3)
```

**08-native-launch-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsDispatchTests -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 7 tests in 0.072s

OK
```

### 09: Grader boundary

**09-grader-boundary-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsUpstreamAdapterTests -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 18 tests in 0.399s

FAILED (failures=3, errors=2)
```

**09-grader-boundary-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsUpstreamAdapterTests -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 18 tests in 0.431s

OK
```

### 10: Lifecycle and removal

**10-lifecycle-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsDispatchTests tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_gateway_model_and_container_topology -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 11 tests in 0.093s

FAILED (failures=3)
```

**10-lifecycle-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsDispatchTests tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_gateway_model_and_container_topology -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 11 tests in 0.088s

OK
```

### 11: Host patch export

**11-export-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsUpstreamAdapterTests.test_preflight_failure_still_has_status_receipt_and_setup_exit tests.test_runtime_worker_openhands.OpenHandsDispatchTests.test_patch_export_cannot_use_host_git_filters_or_external_diff -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 2 tests in 0.045s

FAILED (failures=1, errors=1)
```

**11-export-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsUpstreamAdapterTests.test_preflight_failure_still_has_status_receipt_and_setup_exit tests.test_runtime_worker_openhands.OpenHandsDispatchTests.test_patch_export_cannot_use_host_git_filters_or_external_diff -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 2 tests in 0.042s

OK
```

### 12: Host network template

**12-host-template-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_host_template_names_the_two_required_network_policy_receipts -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 1 test in 0.001s

FAILED (errors=1)
```

**12-host-template-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_host_template_names_the_two_required_network_policy_receipts -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 1 test in 0.000s

OK
```

### 13: Container home

**13-container-home-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_model_container_is_nonroot_and_network_is_explicit -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 1 test in 0.022s

FAILED (failures=1)
```

**13-container-home-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_model_container_is_nonroot_and_network_is_explicit -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 1 test in 0.021s

OK
```

### 14: Publication-safe synthetic fixture

**14-publication-fixture-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_dispatch_fixtures_pass_publication_identifier_policy -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 1 test in 0.009s

FAILED (failures=1)
```

**14-publication-fixture-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_dispatch_fixtures_pass_publication_identifier_policy tests.test_runtime_worker_openhands.OpenHandsDispatchTests -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 12 tests in 0.119s

OK
```

### 15: Grader interpreter selection

**15-grader-interpreter-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_grader_sync_keeps_the_hash_seeded_interpreter -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 1 test in 0.002s

FAILED (failures=1)
```

**15-grader-interpreter-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsRecipeTests.test_grader_sync_keeps_the_hash_seeded_interpreter tests.test_runtime_worker_openhands.OpenHandsUpstreamAdapterTests.test_install_actually_uses_narrow_mounts_and_grader_lock -v
```

Returned summary (complete output retained in the JSON command record):

```text
----------------------------------------------------------------------
Ran 2 tests in 0.047s

OK
```

### 16: Preserve collected results on retry

**16-result-retry-red**, exit 1:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsDispatchTests.test_result_retry_preserves_collected_official_receipt -v
```

Returned summary (full failure retained in round3-commands.json):

```text
----------------------------------------------------------------------
Ran 1 test in 0.032s

FAILED (failures=1)
```

**16-result-retry-green**, exit 0:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands.OpenHandsDispatchTests -v
```

Returned summary:

```text
----------------------------------------------------------------------
Ran 12 tests in 0.101s

OK
```


## Host verification still required

- Coordinator re-registers changed hashes/new files; no local evidence claim
  overrides the failed publication exit.
- Perform native hash-locked worker/grader installation, image entrypoint and
  preload import checks, authenticated health/docs/OpenAPI and native request
  acceptance. Confirm non-root access to all selected tool mounts.
- Supply the shared skills PR, frozen task/hash and per-instance image digest;
  run gold-patch and known-negative official grader controls unchanged.
- Provision and probe rootless per-port filtering, including other host
  services, the opposite arm and post-restart policy behavior. Qualify
  candidate execution in the official grader without hiding environment
  deviations. Keep rule dumps/probe output; do not synthesize a proof receipt.
- Verify each entry database/model/path and max effort, raw response header
  capture including condenser/streaming behavior, missing counters, compression
  snapshot auth/deltas and serial attribution. No request was sent here.
- Qualify an observer outside the model's trust boundary before enabling a
  complete-evidence verdict. The present code intentionally cannot return a
  final pass for a resolved task.
- Confirm invocation counts in Claude child-usage/OTel and native server logs,
  actual tool/skill behavior, background wait/result, cancellation/removal and
  stale-reservation recovery.

## Final acceptance outputs

The final required commands returned:

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3-tmp" python3 -m unittest tests.test_runtime_worker_openhands -v
```

Exit 0; returned summary (all 59 verbose test results are retained in
round3-commands.json):

```text
----------------------------------------------------------------------
Ran 59 tests in 0.647s

OK
```

```sh
rtk env PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate.py
```

Exit 1; complete returned output:

```text
Publication validation failed:
blueprints/runtime-workers/openhands/README.md: SHA-256 mismatch
blueprints/runtime-workers/openhands/README.md: byte count mismatch
blueprints/runtime-workers/openhands/config/host.example.json: SHA-256 mismatch
blueprints/runtime-workers/openhands/config/host.example.json: byte count mismatch
blueprints/runtime-workers/openhands/config/mcp.template.json: SHA-256 mismatch
blueprints/runtime-workers/openhands/config/mcp.template.json: byte count mismatch
blueprints/runtime-workers/openhands/config/worker.json: SHA-256 mismatch
blueprints/runtime-workers/openhands/config/worker.json: byte count mismatch
blueprints/runtime-workers/openhands/e2e/check.py: SHA-256 mismatch
blueprints/runtime-workers/openhands/e2e/check.py: byte count mismatch
blueprints/runtime-workers/openhands/e2e/docker_grader.py: SHA-256 mismatch
blueprints/runtime-workers/openhands/e2e/docker_grader.py: byte count mismatch
blueprints/runtime-workers/openhands/host.py: SHA-256 mismatch
blueprints/runtime-workers/openhands/host.py: byte count mismatch
blueprints/runtime-workers/openhands/install-grader.sh: SHA-256 mismatch
blueprints/runtime-workers/openhands/install-grader.sh: byte count mismatch
blueprints/runtime-workers/openhands/install.sh: SHA-256 mismatch
blueprints/runtime-workers/openhands/install.sh: byte count mismatch
blueprints/runtime-workers/openhands/pins.json: SHA-256 mismatch
blueprints/runtime-workers/openhands/pins.json: byte count mismatch
blueprints/runtime-workers/openhands/receipt.py: SHA-256 mismatch
blueprints/runtime-workers/openhands/receipt.py: byte count mismatch
blueprints/runtime-workers/openhands/recipe.py: SHA-256 mismatch
blueprints/runtime-workers/openhands/recipe.py: byte count mismatch
blueprints/runtime-workers/openhands/research.md: SHA-256 mismatch
blueprints/runtime-workers/openhands/research.md: byte count mismatch
blueprints/runtime-workers/openhands/run-e2e.sh: SHA-256 mismatch
blueprints/runtime-workers/openhands/run-e2e.sh: byte count mismatch
blueprints/runtime-workers/openhands/worker.py: SHA-256 mismatch
blueprints/runtime-workers/openhands/worker.py: byte count mismatch
tests/test_runtime_worker_openhands.py: SHA-256 mismatch
tests/test_runtime_worker_openhands.py: byte count mismatch
```

These are SHA256/byte-count mismatches for the 16 tracked files changed in this
repair. There are no remaining identifier, schema, reference or other
publication errors in this returned output. This is not a publication pass;
the coordinator must register hashes and new evidence, then rerun the check.

```sh
rtk env GIT_OPTIONAL_LOCKS=0 git diff --check
```

Exit 0; returned output was empty.

Additional verification returned exit 0:

```text
Parsed Python sources: 14; shell syntax checks: 4
Publication text scan: no private-content matches
```

The whole worktree cache scan found no bytecode/cache directories; the empty
owned test temporary directory was removed. No commit, staging, Git metadata
write or manifests/evidence.json edit was performed.
