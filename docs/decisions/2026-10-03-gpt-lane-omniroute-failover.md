# Opt-in native-to-OmniRoute failover for packaged GPT sweep jobs

Date: 2026-10-03. Scope: the foundation landscape-sweep runner, its staging,
conversion, documentation and synthetic tests. The build contract's base is
`e88d59e4b4670ca19211a9ab2adb45e1a28901c7`.

North-star action: preserve GPT research and refutation votes across a native
usage limit during ecosystem sweeps serving complex-system delivery and the
US-equities research and historical-simulation program.

## Decision and alternatives

Extend the existing packaged runner with an explicitly staged `codex.fallback`
block. Native remains the primary route. A native limit or staged native quota
gate archives the native attempt, records `LIMIT-native`, and continues through
the keyless loopback OmniRoute gateway within the held slot and existing total
deadline. The new CLI flags are `--gpt6-fallback omniroute` and
`--fallback-codex-host 127.0.0.1:20128`; the latter defaults to that address.

The alternatives were the existing native-only stop, staging a gateway primary,
manually restaging after a limit, and an upstream provider-failover mechanism.
The native-only stop loses the remaining GPT work. A gateway primary loads its
lane-local configuration; the selected fallback preserves the native instruction
surface. Switching the primary provider changes job inputs and reruns successful
GPT jobs. No provider-failover option was found in the installed Codex 0.159.3
`exec --help` or its
[matching release notes](https://github.com/openai/codex/releases/tag/rust-v0.159.3).
This is repository integration over supported upstream configuration and account
interfaces, rather than a claim that Codex supplies transport failover.

Reset-credit consumption (the research plan's G5) is outside this build contract.
The integration reads native rate limits and never calls a consume/reset endpoint.
It changes no shared gateway setting, combo, account or key.

## SOTA sources and verification order

Installed `codex --version` returned `codex-cli 0.159.3`. Its `exec --help`
confirmed `--ignore-user-config`, inline `-c` overrides and JSONL output. The
matching release was read with `gh api` before the tagged source. The source pin
is `openai/codex@01fc69f4026735edfdf6789820549727a4867b11` (`rust-v0.159.3`).

- [Exec configuration](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/exec/src/lib.rs#L334)
  and the [configuration loader](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/config/src/loader/mod.rs#L249)
  retain session overrides while excluding the user configuration layer. Auth
  still uses `CODEX_HOME`; project and managed layers remain separate.
- [Provider fields and retry configuration](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/model-provider-info/src/lib.rs#L193)
  support Responses providers and standalone search. `retry_429` is hardcoded
  false at line 450; a terminal retry-limit report therefore cannot distinguish
  exhausted accounts from a transient HTTP 429. The
  [exec event schema](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/exec/src/exec_events.rs#L22)
  supplies `error.message` and `turn.failed.error.message`.
- [Canonical shell environment filters](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/config/src/shell_environment_policy.rs#L106)
  support exclusion of `OMNIROUTE_API_KEY`. The fallback also disables shell
  snapshots, following the existing lane's provider-key handling.
- The [account method](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/app-server-protocol/src/protocol/common.rs#L1309)
  and [nullable ordinaryUsageAllowed contract](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/app-server-protocol/src/protocol/v2/account.rs#L331)
  are implemented through the existing [quota probe](../../scripts/codex_quota.py).
  Backend recovery must not be inferred from percentages or reset times.
- [Codex's search endpoint](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/codex-api/src/endpoint/search.rs#L14)
  is provider-relative `alpha/search`. Its standalone feature and provider
  capability require explicit activation; see the
  [official configuration reference](https://developers.openai.com/codex/config-reference/).
- The installed gateway reports OmniRoute 3.8.51 with `dist/BUILD_SHA`
  `cf6748d04`. Its named build carries PR #13788's
  [search adapter at 6c7990058c4ce9677de79452c8cefb10b4bf1b3d](https://github.com/amsjavan/OmniRoute/blob/6c7990058c4ce9677de79452c8cefb10b4bf1b3d/src/app/api/v1/alpha/search/route.ts#L132)
  and PR #15167's
  [reasoning suffix parser at 0585aba5589d5a1f49243a13a8db249558e7c9e3](https://github.com/HouMinXi/OmniRoute/blob/0585aba5589d5a1f49243a13a8db249558e7c9e3/open-sse/executors/codex/reasoningSuffix.ts#L35).
  The installed suffix source matches that PR. This is the existing carried
  build, not a new installation or gateway configuration change.
- [OmniRoute's terminal pool helper at its 2f42a9ac base](https://github.com/diegosouzapw/OmniRoute/blob/2f42a9ac19d1a247ec9ce5473b790843724b3061/src/sse/handlers/chatHelpers.ts#L765)
  preserves the last status/error after account exhaustion. The inspected
  installed helper retains that behavior.

The search-first and OpenAI Docs skills guided this bounded source check.
Scoped ai-memory CLI searches with `--project native-agent-stack --limit 2`
and automatic project selection both returned HTTP 404 for that project in the
default workspace. CLI search help supplies no `pin_first` option. No prior
memory claim was used as authority; canonical source and the original current
files supplied the implementation evidence.

## Runtime contract and provenance

The fallback keeps `--ignore-user-config`, the caller's `CODEX_HOME` and global
instructions, the read-only sandbox, original prompt/schema and staged effort.
Its inline provider sets `wire_api = "responses"`, `requires_openai_auth = false`,
`env_key = "OMNIROUTE_API_KEY"` and `supports_standalone_web_search = true`.
Standalone search is enabled, shell snapshots are disabled, and the key is
excluded from model-run shells. A missing key receives the keyless loopback
placeholder. The requested gateway model is `cx/<native model>-<request_effort>`:
`high` stays `high`, and native `ultra` on Astra/6.1 Sol resolves to `xhigh`.
The pinned suffix parser accepts low through xhigh for bare models and max only
for its seven exact max-alias models. Both the stager and runner refuse a fallback
without the matching alias. The suffix takes precedence over explicit request
effort in the [pinned executor](https://github.com/HouMinXi/OmniRoute/blob/0585aba5589d5a1f49243a13a8db249558e7c9e3/open-sse/executors/codex.ts#L1403).
`gateway_effort` records this requested wire effort; delivered effort and stronger
server force rules remain unobserved.

`inputs.json` stays byte-identical. `route.json` records the requested provider,
fallback origin/reason, native and gateway models, the archived native attempt
number, the sanitized loopback `base_url`, `gateway_effort` and
`omniroute:/alpha/search`. The receipt is written after process launch; a hold,
insufficient reserve or failed launch carries no actual gateway route. A direct gateway job has a null native
attempt number. `result` and archived attempt summaries expose the route.
Conversion reads the original receipt because `sweep.js` copies fixed fields;
raw returns and GPT fit votes retain it. Later capacity/idle retries archive and
write the same route receipt after launch, and every failed attempt remains accounted for.
A successful fallback result is reused only while its bound inputs and current
fallback provider, endpoint, model and effort match the route receipt. Disabling
fallback or changing the endpoint archives that result and runs the job again.

`LIMIT-native` contains JSON `reason` and `reset_time`; an unreported reset stays
null. Before each new held job with that marker, the native probe runs without a
quota threshold or model turn. Only a successful report with explicit
`ordinary_usage_allowed: true` removes the marker. Otherwise the job goes directly
to the gateway. A native quota threshold can fail over before any native model
call. This threshold is not applied to the gateway pool. Recovery and quota
probes receive the job's absolute deadline; helper and parent timeouts are capped
by the remaining budget, and expired budgets prevent probe launch. Failed probes
remain recorded. Failover needs the existing 300-second retry reserve. Without
it, exit 3 and the latest native limit remain terminal, including after an earlier
capacity or idle failure.

A gateway HTTP-429 retry-limit report counts only in `error` or `turn.failed`
events. Item content and stderr quotes do not count. It writes global `LIMIT`
with `gateway pool 429`, retaining stop-and-notify when the enabled routes are
exhausted. Native-only LIMIT/quota behavior remains covered by the existing suite.

Workflow resume caches a GPT wrapper that completed with `failed_exit_3`.
Clearing the marker cannot invalidate that completed agent return. Recovery uses
a new Workflow run with the primary provider and frozen templates unchanged.
Successful GPT jobs return `already done` only while their bound inputs remain
byte-identical and their fallback route still matches. Pre-written first-round
discovery prompts can meet that condition. Rerun Claude stages rebuild fit and
follow-up prompts from new proposals and critic output; changed prompt bytes
rerun those GPT jobs, moving earlier successes to `attempts/<n>/` at new GPT
cost. Failed jobs also rerun with their attempt history. Automatic failover keeps the intermediate
native failure within a single held job.

## Acceptance evidence and boundaries

The regression checks use synthetic fake Codex executables on PATH, including
fake `account/rateLimits/read` responses. They establish this repository's
integration behavior, not upstream acceptance or a live model/pool run. New
cases cover native failure then gateway success, both routes exhausted, direct
gateway routing, explicit/nullable/failed native recovery, a native quota gate,
primary gateway error events and stderr controls, gateway capacity/idle recovery,
shared-deadline exhaustion, conversion provenance and restaging byte invariance.

The first full-suite run returned exit 1: 205 tests, one failure and one error,
with three optional skips. The decisive diagnostics were
`KeyError: 'route'` in the new conversion test and `(6, False, False) !=
(3, True, True)` in the new primary-gateway fixture. Conversion's intermediate
metadata projection omitted the route; it now retains it. The primary fixture
omitted its keyless placeholder; it now stages one. The two focused tests then
returned exit 0 (`Ran 2 tests`, `OK`). Subsequent focused routing/conversion
checks returned exit 0 (`Ran 37 tests`, `OK`). These failed conditions are retained
here rather than described as an initially passing build.

The installed debug command rejects literal exec isolation argv:
`codex --ignore-user-config -m gpt-6.1-sol debug prompt-input` returned exit 2,
`unexpected argument '--ignore-user-config' found`. The
[debug builder](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/cli/src/main.rs#L1970)
uses ordinary config loading. The supported
[CODEX_HOME override](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/core/src/config/mod.rs#L4911)
therefore supplied a disposable home without `config.toml`, linking the same
global `AGENTS.md` and skills for both commands. Authentication stores were not
copied. Both commands ran in `<W>/empty`, projecting the runner's native/fallback
model, sandbox, effort, search and inline-provider overrides onto the supported
debug interface. Both returned exit 0. After dropping item `id`/`create_time` and
masking the model names, `cmp` returned exit 0; both normalized SHA-256 values
were `9808c97f250ee7780c03770ee61ad838cb7d4c6c9e44edc4b245824031930bdd`.
Private raw prompts and command vectors remain in the disposable work directory.
`codex debug models --bundled` also returned exit 0: both requested model names
resolve to the bundled `gpt-6.1-sol` entry and its same nonempty base instructions
(SHA-256 `e1bdd4f8f0df4b20f4a0ffc8a861ce819df45325d8cecdfb92e80379cf8d142e`).
This is a bundled-catalog/source comparison, distinct from prompt-input equality.

This is controlled configuration reconstruction with the installed native debug
command. The [debug output](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/core/src/prompt_debug.rs#L84)
is the rendered input array, not the separate base instructions, tool schema or
structured-output request. Schema-byte equality is checked by the synthetic
runner test; search operation and outgoing effort parity remain separate gaps.
No model inference was made for this build's acceptance.

Original FO repository command results (retained failed publication condition):

| Command | Exit | Decisive returned output |
| --- | --- | --- |
| `python3 -B -m unittest tests.test_landscape_sweep_harness` | 0 | `Ran 209 tests in 50.036s`; `OK (skipped=3)` |
| `python3 scripts/validate.py` | 1 | `Publication validation failed:`; SHA-256 and byte-count mismatches for the five edited tracked files |
| `python3 scripts/validate_convergence.py --all-recorded --root . --json` | 0 | `records` has 26 entries; `valid: true` |
| The three pre-push registry tests, exact command below | 0 | `Ran 3 tests in 0.199s`; `OK` |
| `git diff --check` | 0 | No whitespace errors |

```sh
python3 -B -m unittest \
  tests.test_osv_lockfile_coverage.LockfileInventoryTests.test_every_tracked_lockfile_and_manifest_is_listed \
  tests.test_blind_checkout.RepositoryClassificationTests.test_every_blueprint_value_under_a_label_key_is_classified \
  tests.test_workflow_security_coverage.NewWorkflowSecurityCoverageTests.test_all_published_workflows_are_listed_and_covered
```

The full-suite optional skips are the installed context-mode security fixture
(`CONTEXT_MODE_SECURITY_JS`), shellcheck and a real Bash 3.2 binary. `which ruff`
returned exit 1, and the Python module availability check returned false;
conditional `ruff check` and `ruff format --check` were therefore not run.

At that first run, publication validation failed because `manifests/evidence.json`
held old hashes/byte counts for `tests/test_landscape_sweep_harness.py` and the edited
`README.md`, `build_args.py`, `codex_job.py` and `convert.py` in the harness.
That shared hot file was outside contract FO's allowed write scope. The first
unit handed registration to the integrating coordinator through
[the hot-file protocol](../lanes.md#hot-file-protocol). It supplied proposed
entries through `scripts/host_receipts.py` in a disposable snapshot, preserving
the failed command as a failed condition.
The later registration at `ef4c764d252ad66b754824222e2d700d4e62c89b`
updated all six owned entries. R649 rechecks publication after its repairs and
registration; its addendum below retains the current returned result.

## Limitations and overturn condition

The installed `/alpha/search` adapter supports `search_query`; it rejects
`open`, `click`, `find` and `screenshot`. It selects the web-search registry with
a DuckDuckGo fallback. Prompt equality does not establish native search recall,
operation parity, outgoing effort or delivered-model equality. Gateway upstream
[emergency fallback](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/services/emergencyFallback.ts#L37)
can select another provider for quota/budget conditions; its effective deployed
setting was not qualified in this unit. Route provenance records the requested
transport/models and must not be promoted into provider-side model acceptance.

Replace this integration when native Codex exposes supported provider failover,
or disable/reassess this route after a measured parity failure against the native
lane. A future quality comparison must use the repository's upstream promptfoo
protocol and gateway-owner evidence, preserving failed attempts and unknown
usage. This opt-in change does not assert a max-quality gateway acceptance.

## Corrections and completeness critic

- The research plan's G4 described a missing 429 detector. At this contract's
  actual base, `codex_job.py` already recognized the phrase and archived attempts.
  The change adds gateway-specific event-only treatment and the pool reason.
  Verification: original `limit_kind`, `run_attempts` and the existing LIMIT tests.
- A source-only look at the installed gateway missed its carried search route.
  Verification proceeded through `dist/.build/next/server/app-paths-manifest.json`,
  the compiled `/api/v1/alpha/search/route.js`, its referenced chunk and the exact
  PR #13788 source. This corrected the route-absence lead; its narrower operation
  support remains recorded. The current v3.8.51 tag's
  `c1e30b7676975feb298b49eff6ff58923c04b89e` is distinct from this installed carry.
- The research proposed literal exec argv for prompt debug. Installed help, the
  rejected command and tagged debug builder show the interface difference. The
  accepted comparison uses the supported disposable-home reconstruction above.
- The bounded read-only completeness review found no concrete routing defect.
  It identified missing combined fallback/retry, shared-deadline and primary
  stderr controls; those cases were added. The consequential missed source class
  was the installed compiled carry, now verified. The next native-client/gateway
  sweep should check upstream provider failover, nullable recovery behavior,
  deployed pool exhaustion/effort and full web-operation parity. Live settings
  and inference acceptance remain unqualified, as required by this build contract.

## R649 repair and post-registration addendum (2026-10-03)

The bounded PR #649 repair corrects the effort, probe deadline, gateway stderr,
route launch/provenance, route reuse, retry reserve and resume-cost findings.
Its north-star action remains preserving research/refutation votes without
misstating their requested route, effort or attempt cost. The existing runner
and unittest fixtures were extended against the supported pinned Codex provider
interface and OmniRoute suffix parser/executor; no new runtime or dependency
was selected. Keeping the hardcoded max suffix and accepting a route receipt
before process launch were rejected by the reproduced failures. Unsupported
aliases are refused; native provider failover or measured gateway parity failure
still overturns this integration.

The initial R649 regression command returned exit 1: `Ran 8 tests in 1.676s`,
`FAILED (failures=11, errors=1)`. Decisive failures included a high request
selecting `cx/gpt-6.1-sol-max`, probe timeouts `(600.0, 630.0)` instead of
`(1.0, 1.0)`, a gateway stderr quote returning `(3, True, True)` instead of
`(7, False, False)`, a false route on an operator hold, stale `already done`
reuse after changing the endpoint, and timeout 124 instead of terminal native
limit 3. The missing deadline argument was the error. These are synthetic
integration observations, with no provider/model execution. One failed high
subcase left its marker for the following ultra subcase; the fixture now clears
the marker before each independent subcase.

After repair, the focused command returned exit 0: `Ran 32 tests in 7.834s`,
`OK`. An expanded focused run returned exit 1 (`Ran 24 tests in 6.424s`, one
failure): its capacity-then-limit clock selected the second time based on an
exact zero comparison that subprocess waiting had already advanced. The fixture
now uses the attempt ordinal. Its focused rerun returned exit 0 (`Ran 1 test in
0.078s`, `OK`). The final full suite below includes that corrected fixture.

All 17 originally linked external sources were re-fetched, including the release,
15 pinned source files and official configuration reference; the pinned
OmniRoute executor was fetched separately. None was unavailable. The source
check confirms suffix precedence, the seven exact max aliases, nullable recovery,
event fields, inline provider/config behavior, search-operation restrictions,
debug input scope and emergency fallback. Correction: `retry_429: false` is at
line 450 in the pinned provider file; line 447 begins the enclosing retry block.
Installed `codex --version` and `exec --help` still report 0.159.3 and the
supported overrides; the matching release was read with `gh api` before source
verification. The web tool's `open` request failed with HTTP 400 for the carried
search adapter; direct official-page retrieval succeeded. Scoped and automatic
ai-memory searches each returned the existing default-workspace project 404;
its installed help still exposes no `pin_first`. Those unavailable memory
results supplied no authority.

Post-registration `python3 scripts/validate.py` returned exit **0**, with the
actual decisive output:

```text
{"components": 69, "hashed_files": 9421, "profiles": 4, "receipts": 187, "status": "passed"}
Integrity and scope checks only; no live provider or GPU execution.
```

Each changed tracked file was registered with `host_receipts.register_file`,
with `manifests/evidence.json` written last. This passing observation follows
registration; it does not replace or relabel the original FO exit-1 condition.

| R649 check | Exit | Decisive output |
| --- | --- | --- |
| `python3 -B -m unittest tests.test_landscape_sweep_harness` | 0 | `Ran 224 tests in 56.627s`; `OK (skipped=3)` |
| `python3 scripts/validate.py` after registration | 0 | `status: passed`; exact output above |
| `python3 scripts/validate_convergence.py --all-recorded --root . --json` | 0 | `valid: true`, 26 recorded entries |
| The three pre-push registry tests listed above | 0 | `Ran 3 tests in 0.297s`; `OK` |
| `git diff --check` | 0 | No whitespace errors |

The three optional skips retain their original scope. `which ruff` returned
exit 1 and Python module discovery returned false, so conditional Ruff checks
were unavailable. The required worktree-parent scratch directory was absent,
and its creation returned exit 1 (`Read-only file system`). The commands above
used this worker's dedicated writable builds scratch as `TMPDIR`, outside the
checkout and outside `/tmp`. That is an environment exception to R649's exact
parent-scratch requirement, pending a writable parent path; these results do
not attest that required location. No reset credit or consume/reset endpoint
was used, and no live inference/parity qualification was attempted.

R649 completeness critic: the missed source class was alias support independent
of the native catalog, and the missed failure/timing cases were recovery probe
exhaustion, capacity followed by a native limit, quota failover without reserve,
gateway launch failure, operator holds and stderr/item quotations. The suite
now exercises those cases, route reuse after endpoint/enablement changes, and
conversion with and without a launched receipt. `convert.py` needs no repair:
without a route file it reports no gateway provenance or added gateway search
limitation. The next client/gateway sweep should revisit upstream provider
failover, deployed force/clamp behavior and full search-operation parity through
the existing upstream comparison harness. Delivered effort, served model,
provider usage and live pool exhaustion remain unqualified.
