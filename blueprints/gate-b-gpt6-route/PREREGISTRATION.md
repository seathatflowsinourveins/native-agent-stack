# Gate B criterion: the settled GPT-6 route for the landscape-sweep lane, with a gated OpenHands smoke check (2026-09-28)

**Status: DRAFT.** Not frozen, not run, and execution is not authorized. It decides nothing until it is confirmed, reviewed and sealed as described under "Freeze and amendment procedure". The machine-readable contract is [preregistration.json](preregistration.json). The two files carry the same values, and `tests/test_gate_b_gpt6_route_preregistration.py` checks that. No result, seal, sizing choice or admission is recorded.

This revision is the single bounded repair round after two independent refuters reviewed the first draft (one on method, one on citations). "Repair-round dispositions" gives each finding its disposition, and "Decisions taken in the repair" records each design choice. Writing it used no model call, no gateway setting change and no credential. The two gateways received GET requests only.

**Requested by:** roadmap move F-WK-2, "a dated Gate B draft (below), frozen before any measured acceptance run" (`docs/decisions/2026-09-28-ecosystem-roadmap.md:176`). The draft needs three arms, a pass rule and an owner, "for the user to confirm" (`docs/decisions/2026-09-28-ecosystem-roadmap.md:180-183`).

**Who confirms it.** The roadmap holds two readings:
- as written on 2026-09-28, confirming the criterion is a user-only action (`docs/decisions/2026-09-28-ecosystem-roadmap.md:252`);
- its 2026-09-29 update lists the Gate B criterion among the "owner decisions made with evidence under the user's delegation" (`docs/decisions/2026-09-28-ecosystem-roadmap.md:311`), citing the delegation record (`docs/decisions/2026-09-28-delegated-decisions.md:3`).

The roadmap also says that it "changes no authority" (`docs/decisions/2026-09-28-ecosystem-roadmap.md:3`), and the delegation record applied the delegation to named items (`docs/decisions/2026-09-28-delegated-decisions.md:5-8`). This draft therefore treats the update as a recorded reading, not a verified grant. Decision 1 lets the accountable owner confirm under it, after one objection round with the live peers (`docs/decisions/2026-09-28-delegated-decisions.md:13`). The user can take any item back, every decision that changes a user-decided record stays with the user, and the owner itself is a user decision (decision 2).

**Pins.**
- Every repository citation `path:line` is at origin/main `11648f9a` (#463). Each one was verified by substring match against `git show 11648f9a:<path>`. The JSON's `citation_checks` holds the needle for every cited range, and the test re-checks all of them. origin/main moved on after this pin: `git ls-remote` read `b0fb65b4` at 2026-09-29T03:04:26Z. No cited line was re-read there.
- `<sha>:path:line` is an open PR head: #416 `452f7b14`, #431 `73fc873e`, #445 `bddb0072`, #390 `d161f691`.
- `owner/repo@pin:path:line` is upstream, read through `gh api` on 2026-09-29.
- `package@version:path:line` is an installed package file on this host [src].

**Labels:** [doc] documented at the cited source; [obs] observed by this repair's author at the stated UTC time, GET requests and local reads only; [src] source review at the stated pin, never executed; [hist] a retained historical receipt, reference evidence only (`AGENTS.md:42`); [nv] not verified; [inf] inference; [prop] proposed here.

## Scope and the decision gated

**What main records.** The skills-trial record defines Gate B as the settled GPT-6 route (`docs/decisions/2026-09-25-skills-trial-and-usage.md:513-520`). Two consumers wait on it:
- **The 32-layer verdict wave.** It runs "on the Gate B route, after both gates pass" (`docs/decisions/2026-09-28-ecosystem-roadmap.md:210`), and it now waits only on Gate A and Gate B (`docs/decisions/2026-09-28-ecosystem-roadmap.md:312`).
- **The security-audit trial.** M5b's gate 3 is "The user sets a per-run budget" (`docs/decisions/2026-09-25-skills-trial-and-usage.md:660`), and M5c is "Queued behind Gate A and Gate B" (`docs/decisions/2026-09-25-skills-trial-and-usage.md:664`). Their owner lists both as dependents of F-WK-2 in the #469 comment [5880981981](https://github.com/seathatflowsinourveins/native-agent-stack/pull/469#issuecomment-5880981981), which the roadmap cites (`docs/decisions/2026-09-28-ecosystem-roadmap.md:315`).

**D1 (blocking): which GPT-6 lane the landscape-sweep consumer runs on this workstation.** The answer takes the form that `build_args.py` accepts:
- **`native`.** The incumbent and the code default (`tools/sota-convergence/landscape-sweep/build_args.py:554-557`). Its job command is `codex exec --ignore-user-config --skip-git-repo-check -s read-only -m gpt-6-astra ...` (`tools/sota-convergence/landscape-sweep/codex_job.py:15-16`).
- **`omniroute`.** `--gpt6-provider omniroute --codex-host <HOST>` with the defaults: base URL `http://127.0.0.1:20128/v1`, model `cx/gpt-6-astra`, effort `max`, no `--omniroute-header` and the keyless placeholder key (`tools/sota-convergence/landscape-sweep/build_args.py:94-101,593-626`; `tools/sota-convergence/landscape-sweep/codex_job.py:18-25`). This lane refuses `--quota-stop-percent` (`tools/sota-convergence/landscape-sweep/build_args.py:606-608`; `tools/sota-convergence/landscape-sweep/codex_job.py:193-195`).

D1 is the comparison that the gateway's own records wait for. The account-pool record keeps native Codex as the max-quality default "until a preregistered comparison says otherwise" (`docs/decisions/2026-09-27-omniroute-account-pool.md:318`), and the gateway profile keeps it "until a preregistered same-task comparison with native Codex passes" (`adoption/templates/codex.omniroute.config.toml:21-22`).

**D1v (optional, off by default): whether the verdict lane may follow D1.** `tools/sota-convergence/codex_lane.py` has no provider switch and runs with web search disabled (`tools/sota-convergence/codex_lane.py:9-13`). Only family F2 below can support a change, and only a separately reviewed code change can make it.

**D2 (non-blocking, and not decidable in this cohort): whether OpenHands via OmniRoute is admitted for bounded GPT-6 coding-worker trials,** using the #425 recipe's control arm (merged `f6e5a038`). The merged recipe cannot produce an admission today:
- its receipt hard-codes `"evidence_complete": False` (`blueprints/runtime-workers/openhands/receipt.py:282`);
- a run exits 0 only when `task_passed` and `evidence_complete` are both true, otherwise 2 (`blueprints/runtime-workers/openhands/host.py:1328-1330`), and the recipe keeps `evidence_complete` false until an independent observer is qualified (`blueprints/runtime-workers/openhands/README.md:29-31`);
- its P3 control call raises `NotImplementedError` (`blueprints/runtime-workers/openhands/README.md:917-921`).

So arm C is a gated smoke check. Stage C is not scheduled, and consumes no frozen row and no GPT-6 conversation, until its preconditions hold (see "Stage C"). D2 stays `pending` in every outcome of this cohort and never holds up D1. The arm covers the roadmap's third arm (`docs/decisions/2026-09-28-ecosystem-roadmap.md:183`). Because the gate needs no runtime-worker run, #425-#428 leave Gate B's critical path (`docs/decisions/2026-09-28-ecosystem-roadmap.md:284`).

**"Gate B passed"** means that D1 has a recorded value under a row of the decision table (see "Pass rule") whose Gate B column reads `passed`. Those rows are: Stage 0 native, Stage 1 non-inferior, Stage 1 inferior, Stage 1 inconclusive, and two untested-native rows, Stage 1 unpowered within the budget and the time box. The two untested rows count as passed only as decision 15 allows. VOID and INCOMPLETE are never passed. No timer sets a result, except that the time-box row settles native as a label, never as a test result. A person starts the wave (`docs/decisions/2026-09-28-ecosystem-roadmap.md:210`).

**Not decided here:**
- **The agent-sdks layer default.** It changes only through a re-preregistered rerun of the sealed three-arm workers comparison (`docs/grand-catalog-handbook.md:602`; `catalogs/landscape/foundation.json:4739`; `docs/decisions/2026-09-27-omniroute-account-pool.md:309-312`).
- **The 20129 engines-on route and its `sharedgw/` aliases.** Control stays the default "until the #431 A/B selects the engines arm" (`blueprints/runtime-workers/openhands/README.md:147-148`), and harness acceptance on that route "remains open" (`tools/sota-convergence/landscape-sweep/README.md:211`).
- **R02 effort** (#445).
- **S3's LLM route** (`docs/decisions/2026-09-28-ecosystem-roadmap.md:202`).
- **Claude lanes** [prop: a scope choice of this draft], and **the Mac or any other host** (the account-pool record's one-host limit, `docs/decisions/2026-09-27-omniroute-account-pool.md:515-517`).
- **#426-#428.** They are parked "behind the Gate B criterion and #425" (`docs/decisions/2026-09-28-ecosystem-roadmap.md:239`). Their PR bodies define only `control` and `engines-on` arms, with no native arm [doc: `gh pr view 426`, `427` and `428`, all open drafts, at 2026-09-29T02:38Z].

**What a result cannot show:**
- **It is a lane result, not a route result.** Arm B's lane differs from arm A's in more than the provider (`tools/sota-convergence/landscape-sweep/README.md:105-117,122-130`; `tools/sota-convergence/landscape-sweep/build_args.py:311-355,367-370`). The differences are listed under "Arm B". B also uses the gateway's search backend (`tools/sota-convergence/landscape-sweep/README.md:121`; `docs/decisions/2026-09-27-omniroute-account-pool.md:512`), and it goes through two gateway request rewrites known from source at `a58000c7`: `reasoning.context: "all_turns"` is dropped, and placeholder instructions and summary `auto` are injected (`docs/decisions/2026-09-27-omniroute-account-pool.md:434-439`). Two further divergences come from Codex itself for any non-OpenAI provider: cleared encrypted function arguments and local compaction (`docs/decisions/2026-09-27-omniroute-account-pool.md:440-443`). Those two depend on the Codex binary, not the gateway build.
- B's MCP servers run outside Codex's read-only sandbox [doc]: "`ctx_execute` ... runs code with the user's own file access, outside Codex's read-only sandbox" (`tools/sota-convergence/landscape-sweep/README.md:129`). So B can fetch sources that A reaches only through web search. A pass is therefore labelled "lane", never "route fidelity".
- **Short packets may not exercise the rewrites or compaction.** Stage 1 packets are short multi-step lookups. Long multi-turn discover jobs are not tested.
- **The scope is fixed.** A result holds only for this workstation, the sealed gateway fingerprint, the sealed Codex binary and the sealed inputs of both arms.

## Arms, each with its harness, pins and what it can run today

| Arm | Harness | Model | Provider | Base URL | Effort | CODEX_HOME | Working directory | skip_git_repo_check |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `A` | promptfoo 0.123.1 openai:codex-sdk with the Gate B launcher | gpt-6-astra | openai (native ChatGPT login) | Codex default | max | unset (~/.codex) | native-staged work/empty | true |
| `B` | promptfoo 0.123.1 openai:codex-sdk with the Gate B launcher | cx/gpt-6-astra | omniroute (lane home) | http://127.0.0.1:20128/v1 | max | work/codex-home | omniroute-staged work/empty | true |
| `C` | #425 recipe host.py and dispatch.py (control arm) | cx/gpt-6-astra-max | omniroute control arm | http://gw:8081/v1 to 20128 | max | n/a | n/a | n/a |

### Harness shared by arms A and B

**Runner (upstream).** promptfoo 0.123.1 `openai:codex-sdk`. Its bundled `@openai/codex-sdk` 0.153.4 starts `<codex_path_override> exec --experimental-json ...` (`tools/capability-gate/codex-profile-exec:2-5`; `@openai/codex-sdk@0.153.4:dist/index.js:176-243`). The #381 capability gate already runs this provider with a launcher on this host (`docs/decisions/2026-09-27-capability-gate-harness.md:6-11`; `tools/capability-gate/m13.yaml:22-44`).

**Provider settings for both arms.** Each maps to one SDK flag (`@openai/codex-sdk@0.153.4:dist/index.js:194-235`):
- `working_dir`: the arm's staged work directory `<work>/empty`, and `skip_git_repo_check: true`. promptfoo's default working directory is the current directory, and its Git check is on by default (`promptfoo/promptfoo@0.123.1:site/docs/providers/openai-codex-sdk.md:219,231`). The installed provider refuses a directory outside a Git repository unless `skip_git_repo_check` is true (`promptfoo@0.123.1:dist/src/codex-sdk-CHgLS7xg.js`, `validateWorkingDirectory`) [src]. The consumer runs in `<work-dir>/empty` with `--skip-git-repo-check` (`tools/sota-convergence/landscape-sweep/codex_job.py:13,434`).
- `model`: `gpt-6-astra` for A and `cx/gpt-6-astra` for B. Also `sandbox_mode: read-only`, `model_reasoning_effort: max`, and `web_search_mode: live` (F1) or `disabled` (F2).
- `output_schema`: the frozen schema object.
- No `approval_policy` and no `model_provider`. The SDK then adds neither `--config approval_policy=...` (`@openai/codex-sdk@0.153.4:dist/index.js:233-235`) nor `--config model_provider=...`, since the installed provider builds a CLI config only when one of these is set (`getResolvedCliConfig`) [src]. The consumer passes neither (`tools/sota-convergence/landscape-sweep/codex_job.py:425-436`). B's provider comes from its lane home, as in the consumer.
- `maxRetries: 0`. The default is 3, and a throttle with no reset hint waits 60 s, which would hide route failures (`promptfoo/promptfoo@0.123.1:site/docs/providers/openai-codex-sdk.md:218,242`).
- `inherit_process_env: true`, as in the #381 precedent (`tools/capability-gate/m13.yaml:27`). promptfoo's default is a minimal environment (`promptfoo/promptfoo@0.123.1:site/docs/providers/openai-codex-sdk.md:238`). The inherited environment is the curated one below.

**evaluateOptions.** `maxConcurrency: 1` for Stage 0 and 2 for Stage 1; `cache: false`; `timeoutMs: 3000000`, the consumer's 3,000 s bound (`tools/sota-convergence/landscape-sweep/codex_job.py:13`). promptfoo documents `timeoutMs` as the "Timeout in milliseconds for each individual test case/provider API call" (`promptfoo/promptfoo@0.123.1:site/docs/configuration/reference.md:50`). On timeout the installed evaluator aborts the step [src], and the SDK hands the abort signal to the process it spawns (`@openai/codex-sdk@0.153.4:dist/index.js:263-266`). Because the launcher `exec`s Codex, that process is Codex itself. With `maxConcurrency: 2` at most two attempts are in flight, of either arm: promptfoo keeps at most `maxConcurrency` steps in flight (`tools/capability-gate/m13.yaml:5-6`), which bounds the total and not one run per arm.

**Curated environment (a VOID gate).** The A/B operator starts promptfoo under `env -i` with a frozen list of variable names, fixed at the seal: at least `HOME`, `PATH`, `LANG`, `TERM`, `TMPDIR` and `USER`. Values come from the operator's session. The list holds no name containing `KEY`, `SECRET`, `TOKEN`, `PASSWORD`, `CREDENTIAL` or `AUTH`, and no `RUST_LOG*`. The reasons:
- the SDK reuses the ChatGPT login only when `apiKey`, `OPENAI_API_KEY` and `CODEX_API_KEY` are all unset (`promptfoo/promptfoo@0.123.1:site/docs/providers/openai-codex-sdk.md:70`);
- Codex 0.157.1 hands the commands the model runs its whole environment, because the default `*KEY*`/`*SECRET*`/`*TOKEN*` excludes are off (`tools/sota-convergence/landscape-sweep/build_args.py:325-327`; `tools/sota-convergence/landscape-sweep/README.md:114`), and B's lane home filters only `OMNIROUTE_API_KEY` (`tools/sota-convergence/landscape-sweep/build_args.py:336-337`). Any other credential in the operator's environment would reach the model-run commands of both arms;
- the consumer's runner drops every `RUST_LOG*` variable (`tools/sota-convergence/landscape-sweep/codex_job.py:375-379`).

The earlier draft cited `adoption/templates/codex.omniroute.config.toml:9-13` for this. Those lines are stale: they say the lane home has no filter, which `build_args.py` has since added. The consumer itself passes the operator's full environment, minus `RUST_LOG*`, so the curated list is a declared difference, recorded in the scope of any result. Arm B adds `CODEX_HOME=<work>/codex-home` and `OMNIROUTE_API_KEY=local-loopback` through `cli_env` (`tools/sota-convergence/landscape-sweep/codex_job.py:18-25`; `tools/sota-convergence/landscape-sweep/README.md:143`).

**Launcher.** It follows `tools/capability-gate/codex-profile-exec`, which only inserts a flag and `exec`s (`tools/capability-gate/codex-profile-exec:6-9`), with added recording. Per attempt it:
1. reads the prompt from stdin into a private attempt file (mode 0600), and records its sha256 and the attempt nonce on its last line;
2. reads the schema file named after `--output-schema` and records the sha256 of its canonical JSON (sorted keys, compact separators). This happens before `exec` because the SDK writes `JSON.stringify(schema)` to a temporary directory and deletes it after the run (`@openai/codex-sdk@0.153.4:dist/index.js:5-27`);
3. records the argv it received, the argv it executes, and the names, never the values, of the environment variables Codex receives;
4. removes `CODEX_INTERNAL_ORIGINATOR_OVERRIDE`, which the SDK sets to `codex_sdk_ts` (`@openai/codex-sdk@0.153.4:dist/index.js:145-146,254-256`), so Codex runs with the same originator as the consumer's runner;
5. inserts `--ignore-user-config` (arm A) or `--profile stack-worker` (arm B) after `exec`;
6. changes its working directory to the `--cd` value. The consumer's runner starts Codex there (`tools/sota-convergence/landscape-sweep/codex_job.py:685-689`), and context-mode takes its project directory from it (`tools/sota-convergence/landscape-sweep/README.md:123`) [inf: needed for B's skill reads];
7. `exec`s the sealed Codex binary with stdin from the saved prompt file.

It never forks or tees, so the process that promptfoo's timeout signals is Codex itself. The event stream is taken from promptfoo's stored response, not copied by the launcher. The SDK keeps every completed item whole, and the usage (`@openai/codex-sdk@0.153.4:dist/index.js:79-92,98-121`), and promptfoo returns them as `raw` with the thread id as `sessionId` [src]. The Codex rollout named by that `sessionId` is the second record.

**Argv read-back (a VOID gate).** The observer compares the executed argv with `codex_job.codex_argv()` for the same arm (`tools/sota-convergence/landscape-sweep/codex_job.py:425-436`), after normalizing option spellings (`-s`/`--sandbox`, `-m`/`--model`, `-c`/`--config`) and order. The allowed differences are fixed now from the SDK's source (`@openai/codex-sdk@0.153.4:dist/index.js:176-274`), not taken from a pilot:
1. `--experimental-json` in place of `--json`;
2. `--cd <the arm's work directory>` in place of the runner's working directory;
3. the prompt on stdin in place of the last argument with stdin `/dev/null`;
4. the SDK's temporary `--output-schema` path in place of `<job>/schema.json`, with equal canonical bytes;
5. no `-o <job>/last.json`, because the final message comes from the event stream.

Each Stage 0 control changes exactly one setting, listed with the control: `--config web_search="disabled"`, `--config mcp_servers.context-mode.enabled=false`, or effort `medium` in place of `max`. Any other difference voids the block. The pilot only confirms this list. A difference it finds is not allowed by default: it needs a dated pre-seal amendment with its reason, or the fallback in alternative 4.

**Environment read-back (a VOID gate).** The recorded names must equal the curated list plus arm B's two `cli_env` names, with `CODEX_INTERNAL_ORIGINATOR_OVERRIDE` absent after the launcher.

**Pins shared by A and B.**
- **Codex:** codex-cli 0.157.1 [obs 2026-09-29T02:27:37Z, `codex --version`], pinned by path and sha256 at the seal. Upstream published `rust-v0.158.0` at 2026-09-28T05:07:23Z [doc: `gh api repos/openai/codex/releases/latest`]. Moving to it changes both arms and needs a new cohort.
- **promptfoo:** 0.123.1 [obs 2026-09-29T02:27:37Z], with `@openai/codex-sdk` 0.153.4 in its `node_modules` [obs, `package.json`].
- **Analysis environment:** python 3.14, numpy 2.5.3, scipy 1.18.1 and statsmodels 0.15.0 through `uv run --no-project` (`bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json`, key `analysis_environment`). On this host uv resolved python 3.14.7 with those versions [obs 2026-09-29T02:2xZ].

### Local integration code (ours; sealed; tested)

These five components decide outcomes. All five are our integration code: the policy's "Local integration check" class (`docs/acceptance-evidence-policy.md:30`) and the PR table's `local_integration` (`.github/pull_request_template.md:17-20`). Each is sealed by hash, carries unit tests that fail first, and is never described as an upstream runner. The #381 precedent limited local code to the launcher, the assertions and hook, and a wrapper (`docs/decisions/2026-09-27-capability-gate-harness.md:6-11`). The upstream parts are Codex, promptfoo's runner and its `is-json` assertion, and scipy/statsmodels.

| Component | Reads | Emits | Its own tests |
| --- | --- | --- | --- |
| launcher (shell) | argv, environment names, the prompt on stdin, the schema file | `launch.json` per attempt and the private prompt file, then `exec` of Codex | a fake Codex binary: flag insertion per arm, originator removal, record fields, stdin hand-off, the same pid after `exec` (a SIGTERM to the launcher's pid reaches the fake), canonical schema hash |
| hook (promptfoo `beforeEach`, pattern `tools/capability-gate/m13.yaml:18-19`) | nothing | a fresh random Stage 0 token file with its sha256; the attempt nonce as a test variable | freshness, uniqueness, no reuse |
| observer (Python) | promptfoo's JSON output (per-assertion results, `raw` items and usage, `sessionId`, errors); the launcher records; only the rollouts named by those `sessionId`s; nonce matches and aggregates handed over by the gateway operator, with no IDs or bodies | attempt classes, Stage 0 item results per run, identity verdicts, per-packet scores, the usage table, VOID and INCOMPLETE causes | planted fixtures for every class and item, both planted relabels, usage removed, web-search items without results, argv and environment read-back cases |
| analysis (Python, pinned environment) | the observer's per-packet table | Δ̂, the bootstrap bound and p, the exact-branch p when it governs, the branch used, the informative-set check and the decision-table row; exit 2 on VOID | appendix A's boundary fixtures: all concordant, 19 against 20 nonzero differences, a zero-width interval |
| scorer-control generator (Python) | the frozen packets and expected values | the synthetic outputs that promptfoo's `echo` provider replays through the frozen assertions | each control's predicted verdict |

### Arm A: native Codex (incumbent)

- **Lane.** The consumer's native job: `codex exec --ignore-user-config --skip-git-repo-check -s read-only -m gpt-6-astra -c model_reasoning_effort="max" -c web_search="live" --output-schema <job>/schema.json -o <job>/last.json --json <prompt>`, run in `<work>/empty` (`tools/sota-convergence/landscape-sweep/codex_job.py:15-16,433-436`). The harness reproduces it with the five listed differences.
- **Sign-in.** `CODEX_HOME` stays unset, so Codex uses the host's existing ChatGPT login in `~/.codex`. Nothing is copied, read or printed (`AGENTS.md:43`).
- **Working directory.** `<work>/empty` as `build_args.py` stages it for the native provider. It is empty, because a native restage removes `.claude/settings.json` (`tools/sota-convergence/landscape-sweep/README.md:130`), and it lies outside any Git checkout.
- **Sealed inputs.** `~/.codex/AGENTS.md`, since the native lane's workers get the top rule and RTK's instructions from it (`tools/sota-convergence/landscape-sweep/README.md:110`). The skill trees under `~/.codex/skills` and `~/.agents/skills`, since Codex lists user skills from `$CODEX_HOME/skills` and `$HOME/.agents/skills` (`tools/sota-convergence/landscape-sweep/README.md:122`). The working directory's listing and the Codex binary. `~/.codex/config.toml` is ignored under `--ignore-user-config`. The auth store is never read or hashed.
- **Model and effort evidence.** Client side only: the launcher's argv and the rollout's `turn_context` for the attempt's `sessionId`, under `~/.codex/sessions` (`promptfoo/promptfoo@0.123.1:site/docs/providers/openai-codex-sdk.md:301`). The observer reads only the rollouts its own attempts named. The event stream carries no model field (`docs/decisions/2026-09-28-delegated-decisions.md:127`), and the native route has no provider-side echo, so the analysis states this asymmetry with arm B.
- **What it can run today.** Partly:
  - codex-cli 0.157.1 and promptfoo 0.123.1 are on PATH [obs 2026-09-29T02:27:37Z].
  - The login state and live quota were not read. The last retained quota read was 43% used at 2026-09-28T00:30:32Z (`evidence/artifacts/omniroute-routing-20260928/route-gpt6-runs.json:142`) [hist].
  - The last retained native lane jobs exited 0 on 2026-09-28: route-job1 (`evidence/artifacts/omniroute-routing-20260928/route-gpt6-runs.json:7-26`) and route-job2 (`evidence/artifacts/omniroute-routing-20260928/route-gpt6-runs.json:69-90`) [hist].
  - Not yet built: the local code above, the packets, schemas and controls.

### Arm B: OmniRoute GPT-6 on 20128, no headers (candidate)

- **Lane.** `CODEX_HOME` is the lane home that `build_args.py --gpt6-provider omniroute --codex-host <HOST>` stages, and the command is `codex exec -p stack-worker --skip-git-repo-check -s read-only -m cx/gpt-6-astra ...` (`tools/sota-convergence/landscape-sweep/codex_job.py:18-25`; `tools/sota-convergence/landscape-sweep/README.md:142`).
- **The lane home, sealed as a whole** (`tools/sota-convergence/landscape-sweep/README.md:105-117`; `tools/sota-convergence/landscape-sweep/build_args.py:311-355`):
  - `config.toml`: model `cx/gpt-6-astra`, provider `omniroute`, effort `max`; `[features] shell_snapshot = false` and `standalone_web_search = true`; `[shell_environment_policy.filters] OMNIROUTE_API_KEY = "exclude"`; `[model_providers.omniroute]` with a loopback `base_url`, `env_key = "OMNIROUTE_API_KEY"`, `requires_openai_auth = false`, `wire_api = "responses"` and `supports_standalone_web_search = true`; and the `[mcp_servers.*]` tables for serena, ai-memory, socraticode, headroom, codebase-memory, qmd and context-mode;
  - `stack-worker.config.toml`, the worker profile copied verbatim;
  - `AGENTS.md`, the managed block with the top rule and RTK's instructions (`tools/sota-convergence/landscape-sweep/README.md:110`).
- **Working directory.** `<work>/empty` with `.claude/settings.json`, which holds one exact `Read(...)` rule per file under `$HOME/.agents/skills`. context-mode needs it to load the skills (`tools/sota-convergence/landscape-sweep/build_args.py:203-219,367-370`; `tools/sota-convergence/landscape-sweep/README.md:122-126`). It lies outside any Git checkout.
- **Sealed inputs.** The lane-home files, the working directory's settings file, the skill trees under `<lane home>/skills` and `~/.agents/skills`, the MCP server entry points named in the lane config (path and sha256), and the Codex binary. ai-memory is reached by URL, so the seal records the version it reports [nv: the read path is fixed in the pilot].
- **promptfoo settings.** `cli_env` sets `CODEX_HOME` and `OMNIROUTE_API_KEY=local-loopback` (`tools/sota-convergence/landscape-sweep/codex_job.py:22-25`). Whether the provider runs with an overridden `CODEX_HOME` and the keyless placeholder is [nv] until the pilot. promptfoo documents only the ChatGPT-login case of an overridden `CODEX_HOME` (`promptfoo/promptfoo@0.123.1:site/docs/providers/openai-codex-sdk.md:72`).
- **Gateway now** [obs 2026-09-29T02:27:37Z, GET requests and unit reads only]:
  - `omniroute.service` (20128) has been active since 2026-09-29T00:42:44Z on install `omniroute-3.8.51-81c9b6da-pr13788-affinity2`, whose `dist/BUILD_SHA` reads `5fc47d970`: `81c9b6da` with #13788 and the affinity2 change.
  - `GET /v1/models` on 20128 lists 600 IDs, 60 of them GPT-6, including `cx/gpt-6-astra` and `cx/gpt-6-astra-max`.
  - `GET /api/logs/detail?limit=0` returns `enabled: false` on both ports, so detailed pipeline logging is off.
  - 20129 (out of scope) has been active since 00:41:49Z on `omniroute-3.8.51-81c9b6da-pr13788`, `BUILD_SHA` `c3fa5a15e`: `81c9b6da` with #13788.
- **Build record.** The rebuild's receipt is not on main, and no open PR carries it [obs, `gh pr list --state open` at 2026-09-29T02:38:20Z]. That receipt is F-WK-3: per-unit `BUILD_SHA` and #445's admissible values re-derived on the new build (`docs/decisions/2026-09-28-ecosystem-roadmap.md:185-189`).
- **Facts established on earlier builds.** Each is a seal prerequisite to re-derive on the running build:
  - Before the 2026-09-29 rebuild, 20128 ran `045aa81f3` and 20129 ran `dd6e9607e` (`blueprints/runtime-workers/openhands/evidence/repair-round-commands.json:254`). On 2026-09-27, 20128 ran `dd6e9607e` (`docs/decisions/2026-09-27-omniroute-account-pool.md:137`).
  - Correlation IDs. At `045aa81f3` and `dd6e9607e`, `/v1/responses` logs a fresh gateway-generated ID, and only `/v1/chat/completions` keeps a caller's (`blueprints/runtime-workers/openhands/README.md:459-467`). Codex uses `/v1/responses`, so a caller-set ID cannot join its rows; identity uses the attempt nonce instead (Stage 0 item 7).
  - Effort columns. `reasoning_effort_requested` and `reasoning_effort_upstream` are filled only when the response carries encrypted reasoning, as read on the installed OmniRoute 3.8.51 (`tools/sota-convergence/landscape-sweep/README.md:208`). A null proves nothing.
  - What the gateway sent upstream is `pipelinePayloads.providerRequest`, recorded only while detailed logging is on (`tools/sota-convergence/landscape-sweep/README.md:209`).
  - The two gateway request rewrites above, read at `a58000c7` (`docs/decisions/2026-09-27-omniroute-account-pool.md:434-439`).
  - The no-auth and anonymous-fallback provider lists used by G5, copied from `045aa81f3` and `dd6e9607e`: "A gateway upgrade must re-read them" (`blueprints/runtime-workers/openhands/README.md:788-790`).
  - PR #14904 reported HTTP 500 for every `/v1/responses` request on `release/v3.8.51` (`adoption/templates/codex.omniroute.config.toml:18-20`). Upstream closed it unmerged on 2026-09-28 [doc, `gh pr view 14904 -R diegosouzapw/OmniRoute`, as the citation refuter read it], and the running install name carries only `pr13788` [obs]. Whether `81c9b6da` contains an equivalent fix is [nv]; the pilot answers it directly.
- **Effort evidence.** 20128's `pipelinePayloads.providerRequest` for the attempt's nonce row, which needs detailed logging (decision 6), or a non-null `reasoning_effort_upstream`. Never `requestBody` (`tools/sota-convergence/landscape-sweep/README.md:208-209`).
- **Excluded.** 20129 engines-on and `sharedgw/` aliases.
- **What it can run today.** The routes are listed [obs], but the arm cannot be measured yet. It still needs the build receipt, a fingerprint read-back with logging on (decision 6), the re-derived facts, the local code and the packets.

### Arm C: OpenHands via OmniRoute (D2 only; a gated smoke check)

- **Recipe.** The #425 recipe's control arm (merged `f6e5a038`):
  - OpenHands SDK and agent-server 1.49.6 at `fcc102a` (`blueprints/runtime-workers/openhands/pins.json:3-6`); upstream tag `v1.49.6` resolves to `fcc102a6` [doc: `gh api`];
  - agent-server image `sha256:02ef66fd…` (`blueprints/runtime-workers/openhands/pins.json:17`) and nginx proxy image `sha256:ed04ec1f…` (`blueprints/runtime-workers/openhands/pins.json:25`);
  - a per-attempt internal network, with the agent's base URL `http://gw:8081/v1` leading to 20128, model `cx/gpt-6-astra-max` (`blueprints/runtime-workers/openhands/README.md:155-162`);
  - Responses, `reasoning_effort=max`, a 40-iteration limit and a 1,200-second deadline (`blueprints/runtime-workers/openhands/README.md:177-178`).
- **Harness.** The recipe's own `host.py` and `dispatch.py`: a local integration by the recipe's author, merged and tested offline (`blueprints/runtime-workers/openhands/README.md:3-7`). It is labelled so, never as an upstream runner.
- **Grading.** The official SWE-bench 4.1.0 harness, through the converter pinned at `OpenHands/benchmarks@405bae71` (`blueprints/runtime-workers/openhands/pins.json:48-50`; `blueprints/runtime-workers/openhands/README.md:1019-1024`).
- **Why it cannot decide D2 now.** The reasons under "Scope" (`evidence_complete`, exit 2, P3), plus:
  - the P0-P2 isolation probe has not run (`blueprints/runtime-workers/openhands/README.md:20-22`);
  - G2 and P3 are stage gates that the coordinator records after observing them live (`blueprints/runtime-workers/openhands/README.md:895-912`), and none is recorded;
  - G5 refuses on any unblocked no-auth provider outside the arm allowlist (`blueprints/runtime-workers/openhands/README.md:772-778`). Both gateways list IDs owned by `codex-app-server` (46), `devin-cli-agentic` (127), `auggie` (28) and `zcode` (14) [obs 2026-09-29T02:27:37Z], so G5 would refuse today [inf].
- **What it can run today.** Nothing. There is no openhands directory under the tools prefix, and `harbor` is not on PATH [obs 2026-09-29T03:04:26Z].

## Task set

### Stage 0: lane parity with discriminating controls (arms A and B, serialized)

Each check counts only after a run with its condition absent has failed (`docs/acceptance-evidence-policy.md:42-53`). The seven items are the lane parity check (`tools/sota-convergence/landscape-sweep/README.md:147-153`) plus identity. Stage 0 runs as one block with `maxConcurrency: 1`, inside the sealed window with detailed logging on (decision 6).

| # | Item | Arms | Passes when | Failing control (must fail as predicted) |
| --- | --- | --- | --- | --- |
| 1 | effort | B | 20128's `providerRequest` for the attempt's nonce row shows effort `max`, or a non-null `reasoning_effort_upstream` equals `max` | one B run at effort `medium` reads `medium` |
| 2 | shell | A, B | a `command_execution` item's output carries the fresh token that the hook wrote just before the run | one run per arm whose hook writes no token file |
| 3 | MCP | B | an `mcp_tool_call` item of server `context-mode`, tool `ctx_execute`, carries the token. A's lane has no MCP servers by design: `--ignore-user-config` keeps the host's config out (`tools/sota-convergence/landscape-sweep/codex_job.py:33`), and "the native lane has no context-mode" (`tools/sota-convergence/landscape-sweep/README.md:130`) | one B run with context-mode disabled through `cli_config.mcp_servers` (`tools/capability-gate/m13.yaml:56-59`) |
| 4 | schema | A, B | the output passes `is-json` with the frozen schema | a planted wrong-shape output fails and a planted correct one passes (no model call) |
| 5 | usage | A, B | `turn.completed` usage is present on every attempt | a copy of a real attempt with its usage removed is reported missing (no model call) |
| 6 | search | A, B | for every frozen query where A's matched run got at least one result, B's run also got one | one B run with `web_search` disabled gets none |
| 7 | identity | A, B | client side: argv, `CODEX_HOME` and sealed inputs match the arm, and so does the rollout when one is written. Gateway side: every B attempt's nonce appears in at least one 20128 `/v1/responses` row, and no A attempt's nonce appears in any | the observer flags two planted relabels: a real A attempt filed as B, and the reverse (no model call) |

**Where each item reads.**
- Items 2, 3 and 6 read the attempt's completed items in promptfoo's stored `raw`.
- Item 6 reads the `results` field of each `web_search` item. The SDK's TypeScript type lists only `id`, `type` and `query` (`@openai/codex-sdk@0.153.4:dist/index.d.ts:78-82`), but the SDK passes each parsed item through whole (`@openai/codex-sdk@0.153.4:dist/index.js:79-92,104-110`). A retained fixture shows codex-cli 0.157.1 emitting `results` on `web_search` items against a fake search server (`evidence/artifacts/sota-refresh-20260926/codex/accept_codex_ws.py:82-95`; `evidence/artifacts/sota-refresh-20260926/codex/results/websearch-0.157.1.json`) [hist, fixture, not live].
- If a live pilot attempt's items carry no `results`, item 6 reads the Codex rollout named by the attempt's `sessionId`. If neither carries results, item 6 is untested, which is INCOMPLETE. The pilot settles this before the seal, so the owner can amend while no Stage 0 data exists.
- Only `web.run` counts for item 6. B's MCP fetches in P2 are flagged and reported.
- Item 7's gateway side reads 20128's detailed call logs for the sealed window. The gateway operator searches the logged request bodies for the attempts' nonces and hands the observer only the matches, never bodies or IDs. If decision 6 is "no", this leg falls back to time windows, which then requires Stage 0 to run in an exclusive window (decision 7). Without either, the gateway leg is untested and Stage 0 is INCOMPLETE.

**Probes.**
- P1 covers items 2-5 and 7. One prompt asks for the file token through the shell, and for B also through `ctx_execute`, answered in the frozen schema.
- P2 covers items 4-7. It holds 6 frozen web queries, each answered with the URLs retrieved. The queries are sampled from the sweep's retained search calls where these exist, and are recorded at the freeze.
- Every prompt ends with a line `attempt: <nonce>`, a fresh random value from the hook, in the same form in both arms.

**Repeats.** K = 3 runs of P1 and of P2 per arm, interleaved A, B, A, B and matched by index (A1 with B1, and so on).

**Frozen failure rule:**
- B fails an item when it fails in at least 2 of the 3 runs whose matched A run passed that item. For the B-only items 1 and 3, the rule is at least 2 of the 3 B runs.
- If A fails an item in at least 2 of its 3 runs, Stage 0 is INCOMPLETE. An A-side failure never decides D1 and never triggers the account-pool overturn.
- For items 1 and 7, a missing gateway record is an observability gap, not a B failure. When the client-side evidence shows the omniroute route and 20128 holds no row for a B nonce, or holds no `providerRequest`, the item is untested and Stage 0 is INCOMPLETE until the gateway operator restores logging. B fails item 7 only when client-side evidence contradicts the arm, or when an A nonce appears at 20128.
- An infrastructure failure (HTTP 5xx, a timeout) gets one frozen retry and then counts as INCOMPLETE.

**Standing checks outside D1:**
- **E1a, shell containment (one run per arm).** A shell step runs `curl -s -X GET 'http://127.0.0.1:20128/api/logs/detail?limit=0'` inside the read-only sandbox and reports the output. "Reached" means the `command_execution` output carries the endpoint's JSON. The control is the observer's same GET outside the sandbox, which must succeed.
- **E1b, MCP containment (arm B).** B is asked to run the same GET through `ctx_execute`. "Reached" means the `mcp_tool_call` result, which the MCP server returns and the model cannot write, carries the endpoint's JSON. The expected result is "reached" (`tools/sota-convergence/landscape-sweep/README.md:129`). Two controls: the observer's GET outside Codex must succeed, and the same probe with context-mode disabled must not reach. The keyless management API lets any local process register hooks that read and rewrite prompts (`docs/decisions/2026-09-27-omniroute-account-pool.md:290-296`), so E1b measures the known path that E1a cannot.
- **Q1, quota-gate control (no model call).** `scripts/codex_quota.py --json --gate P`, with `P` set below the live `used_percent`, must exit 3 (`scripts/codex_quota.py:28-30`).

**Stage 0 total: 21 model runs.** That is 12 for P1 and P2, plus 9 controls: effort `medium` (1), no token (2), context-mode disabled (1), search disabled (1), E1a (2), E1b (1) and the E1b context-mode-disabled control (1). The planted-output, usage-absent and planted-relabel controls replay retained records and need no model call.

### Exploratory pilot (never acceptance)

- **Size.** 12 packets built like F1 and kept apart from it, with one run per arm (24 runs), all before the freeze. The pilot also runs the read-back checks with logging on.
- **What it measures:** the per-packet differences h (defined under "Statistics"), arm A's mean score, usage and wall time per run, and the pre-seal facts: the argv and environment read-backs, rollout presence and fields, whether `web_search` items carry `results`, the `CODEX_HOME` placeholder, `providerRequest` effort, and correlation-ID behaviour on the running build.
- **Calibration gate.** Arm A's pilot mean must lie within [0.20, 0.80]. Otherwise the packet construction is revised and the pilot repeats on new packets. Pilot packets never enter Stage 1.
- **Status of its outputs.** They never count, the rule the roadmap applies to an exploratory #425 run (`docs/decisions/2026-09-28-ecosystem-roadmap.md:43,176`). The pilot law feeds the sizing amendment.

### Stage 1: arm A against arm B (runs only after Stage 0 passes)

**F1, required: landscape-sweep packets.**
- **Size and schedule.**
  - n packets come from the dated pre-seal sizing amendment (see "Statistics"), and the reserve holds ceil(0.2 n) packets.
  - Each arm runs each packet once, with order alternating AB and BA by packet index.
  - Blocks of 20 packets, with `maxConcurrency: 2` and `timeoutMs: 3000000`.
- **Source.** Refute or fit questions about candidates in `catalogs/sota-convergence/manifest-20260926.json` (`docs/decisions/2026-09-28-ecosystem-roadmap.md:25`). Each question is chosen so its verdict depends on facts that need at least two dependent tool steps. For example: find the latest release, read its changelog or merged PR, then check a named file at that tag.
- **Shape.**
  - Each packet has 3 fact fields and 1 verdict field, which a frozen rule derives from the facts.
  - At least 15% of packets have a negative expected answer, written in a frozen negative representation: a tag or repository that does not exist, or a claim that its own source contradicts.
  - Every prompt ends with the attempt-nonce line. That line is the only difference between the two arms' prompts for one packet.
- **Expected values.** The freeze author records them from primary sources through `gh api` GET requests, with as-of UTC times. A second session re-checks them before the seal and again after the run.
- **Drift.** A fact that changed during the window drops that packet from both arms, and the next reserve packet takes its place in frozen order. A pair stopped by a capacity limit reruns in both arms once the condition changes, and the first attempts are kept.
- **Scoring.** Only promptfoo's built-in `is-json` assertion is used (`promptfoo/promptfoo@0.123.1:site/docs/configuration/expected-outputs/deterministic.md:340-389`):
  - one assertion checks the frozen output schema;
  - one assertion per scored field checks a frozen JSON Schema whose `const` or `pattern` encodes the frozen normalization: case, surrounding whitespace, a leading `v` on tags, and the negative representation.

  There are no JavaScript or model-graded assertions. The analysis reads promptfoo's per-assertion results, and a packet's score is the number of matched field assertions divided by 4.
- **Scorer controls** (synthetic, no model call). The scorer-control generator writes these outputs, and promptfoo's `echo` provider replays them through the same frozen assertions, once before the seal and again before the analysis:
  - for each packet, the exact expected values score 4 of 4;
  - one planted wrong value per field fails that field only;
  - for each field type, the normalization edge cases (a case change, surrounding whitespace, a leading `v`) pass as frozen, and a near miss (`1.2.30` for `1.2.3`) fails;
  - for each negative packet, the frozen negative representation passes and a fabricated value fails.

  A control that does not behave as predicted fails the scorer's qualification before the seal, or voids the analysis after the run.
- **Field provenance.** From the attempt's items, the observer records which tool produced each scored fact: `web_search`, an MCP tool or the shell. It is reported, never a decision leg.

**F2, optional (decision 5): verdict-lane packets.**
- **Shape.** n2 packets built like `codex_lane.py` runs: read-only sandbox in a frozen checkout, web search disabled and an output schema (`tools/sota-convergence/codex_lane.py:9-13`).
- **Questions.** Each is fixed by repository files at a frozen revision (a pin, a line's content, a count). At least 15% have negative expected answers.
- **Arms.** Arm A runs codex_lane's argv. Arm B runs the same argv with only the provider changed to 20128's omniroute provider. The pre-seal amendment fixes the exact argv, and any later code change must implement that argv.
- **The rest.** Scoring, scorer controls, drift and provenance follow F1.

### Stage C: OpenHands admission smoke check (arm C, D2), gated

- **Dispatch preconditions.** All must hold before a row is frozen or a conversation spent:
  - an independent observer qualified for #425, and a merged recipe change under which `evidence_complete` can become true on that observer's evidence;
  - P3 implemented and run, with G2, P3 and G5 recorded as passed (`blueprints/runtime-workers/openhands/README.md:895-912`);
  - a P0-P2 receipt at most 900 s old at dispatch (`blueprints/runtime-workers/openhands/README.md:873-893`);
  - decision 8's G5 blocking applied, with its own fingerprint.
- **Then** a dated seal amendment, before any Stage C data, freezes one SWE-bench row never used in an exploratory #425 run, and one conversation runs through the recipe's control arm.
- **Grader controls.** Run under the frozen image with network `none`: the gold patch resolves; the empty patch does not; two planted exploit patches do not (a `conftest.py` that prints PASSED lines, and an edit to the task's test files).
- **Why the exploit patches.** The SWE-bench changelog dates 4.1.0 to 9/11/2025, before v5.0.0, whose "Fixed grading" entry says "A patch can no longer pass by printing its own `PASSED` lines" (#620) (`SWE-bench/SWE-bench@v5.0.1:CHANGELOG.md:12,34-35,41`). When the grader resolves an exploit patch, no resolved verdict from it may be cited as quality evidence until it is requalified on swebench 5.x.
- **Until then** D2 is `pending` in every outcome, and Stage C consumes nothing.

## Metrics and usage accounting (counted once)

### Stage 1 metric

- **Per-packet score.** In [0, 1], as defined under "Task set".
- **Attempt classes.** The independent observer assigns them from the stored items, errors and exit data, never from a wrapper's own `passed` field (`docs/acceptance-evidence-policy.md:65-69`):

  | Class | Meaning | Scoring |
  | --- | --- | --- |
  | S | completed, with schema-valid output | scored |
  | F | completed, with schema-invalid or empty output | 0 |
  | X | failed after Codex started: promptfoo's `timeoutMs` abort, a transport error or HTTP 5xx, or a Codex error | 0. The consumer would see a missing vote, like the 71 of the 287 candidates of the 2026-09-26 sweep whose `gpt-6-astra` fit vote reads only "missing" (`docs/decisions/2026-09-28-ecosystem-roadmap.md:34`) |
  | L | capacity refusal: Codex's usage-limit message, a quota stop, a gateway limit or HTTP 429 | not scored. The pair reruns in both arms after the condition changes, never in an automatic loop (`docs/convergence-architecture.md:164-168`) |

  A harness failure before Codex starts is an invalid attempt: it is kept and rerun, and never scored.
- **Estimand.** Δ = the mean over scored packets of score(B) − score(A). The test works with the harm h = score(A) − score(B), so Δ = −E[h].
- **Reported but never decision legs:**
  - completion rate per arm, (S+F)/(S+F+X);
  - the L count per arm and per source;
  - Δ split by field provenance;
  - per-arm means;
  - the number of packets with h ≠ 0, and how many of them differ by more than one field;
  - the correlation between the arms. Miller's "Adding Error Bars to Evals" treats paired differences between two models and experiment planning ([arXiv 2411.00640](https://arxiv.org/abs/2411.00640), abstract).

### Stage 0 and Stage C records

- **Stage 0.** Items pass or fail under the frozen failure rule. E1a, E1b and Q1 are recorded with their controls.
- **Stage C** (only if it becomes schedulable): the receipt's exit code, `evidence_complete` and `failure_stage`; the official grader verdict and the four grader controls; the effort sent upstream; and usage from the entry gateway.

### Usage accounting

- **One authority per Codex attempt.** That authority is the `turn.completed` usage stored in promptfoo's `raw`. The keys are `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens` and `reasoning_output_tokens`. Cached and cache-write input sit inside input, reasoning sits inside output, and total = input + output (`evidence/artifacts/omniroute-routing-20260928/route-gpt6-runs.json:4`). The SDK sets a missing `cache_write_input_tokens` to 0 (`@openai/codex-sdk@0.153.4:dist/index.js:88-90`), so a zero there is not evidence of zero cache writes.
- **Cross-checks, never added.** promptfoo's `tokenUsage` (`promptfoo/promptfoo@0.123.1:site/docs/providers/openai-codex-sdk.md:33`) and B's gateway rows, joined by nonce.
- **Every attempt counts once.** This covers the pilot; Stage 0 runs and controls; Stage 1 attempts, whether scored, failed, timed out, limit-stopped or rerun; invalid attempts; and Stage C. Pilot and control usage are reported apart from scored runs (`docs/convergence-architecture.md:149-158`).
- **Unknown usage stays unknown.** A quota percentage is a whole-account figure and never a token count (`docs/token-practice.md:319-322`).
- **Codex transport retries.** Codex's own retries inside a turn are not visible as separate attempts [nv]. This is declared, not estimated.
- **Local model work behind B's MCP servers.** socraticode embeds through a local LM Studio endpoint (`adoption/templates/codex.config.template.toml:60-67`). That work is outside Codex's usage: it is declared unknown and never added.
- **Claude-side usage.** The coordinator's, observer's and reviewers' usage comes from their own native counters and is never summed with GPT-6 counters (`AGENTS.md:28`).
- **Arm C usage.** It comes from the entry gateway's rows, matched by time window, model and path (`blueprints/runtime-workers/openhands/README.md:440-457`). Reads there are limited to input, cache-read and reasoning tokens, so there is no output-token total, and it is not comparable with A and B.
- **Wall time.** Taken from the launcher's start time and promptfoo's latency per attempt. It is reported per arm and is never a decision leg.
- **Money.** No dollar figures are computed.

### Evidence classes

The class names follow `docs/acceptance-evidence-policy.md:26-33`, and the PR-table names follow `.github/pull_request_template.md:17-20`. The table lists the classes that future receipts will carry. This draft itself is structural validation (`source_review`) and claims nothing stronger.

| Output | Policy class | PR-table class |
| --- | --- | --- |
| This draft, its JSON, the draft-contract test, the hash rows, appendix A's planning simulation | structural validation | source_review |
| Packets, expected values, schemas, planted and scorer controls | synthetic fixture (constructor named, frozen data, stated limits) | synthetic |
| Stage 0 and Stage 1 runs: our packets, local code and assertions in upstream promptfoo, with native Codex executing on this host | local integration check | local_integration |
| The #425 dispatch for arm C, whose verdict comes from the unchanged SWE-bench 4.1.0 grader | local integration check | local_integration |
| The grader's gold and empty-patch controls | upstream example or native operation | native_proven |
| The observer's re-derivation from stored items, rollouts, launcher records and gateway nonce matches; the second-session fact re-check | independent observation | native_proven |
| Merged commit `b9abcc5f`'s probe, route-job1 and route-job2, receipt 8 and this repair's host observations | reference only | not claimed |

## Pass rule

Outcomes are evaluated in this order: VOID, then INCOMPLETE, then a decided row. The order follows Gate A's `outcome_rule`, which puts incomplete before pass and fail (`evidence/artifacts/token-adoption-e2e-20260926/preregistration.json:3153-3169`), and #445's invalid-first rule (`bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json`, key `decision_rule.invalid`).

### Blocks

A block is one promptfoo invocation over a frozen, contiguous slice of the schedule. Stage 0 is one block, and Stage 1 runs in blocks of 20 packets (40 attempts) in frozen order. Before and after each block the runner and the gateway operator:
- read back the gateway fingerprint;
- re-hash the sealing table and the sealed inputs of both arms;
- check the curated environment;
- read the native quota live, with Q1 as its control.

VOID discards a whole block from scoring, and its attempts stay retained with their usage. If the fix changes no sealed artifact, the same slice reruns as a new block in the same cohort. If the fix changes a sealed artifact, the cohort ends. A new cohort needs a new seal, and it does not reuse packets whose Stage 1 outcome was observed. An outcome counts as observed once the observer has classified or scored an attempt, or anyone has read its output.

### VOID: zero tolerance, no statistic, analysis exits 2

A block is VOID when any of the following holds:
- **Seal.** A frozen artifact's sha256 differs from the sealing table.
- **Codex binary.** Its hash or version differs between the arms, or from the seal.
- **Gateway fingerprint.** It differs from the seal, or between blocks. It is read back before and after every block and covers `BUILD_SHA`; the Thinking Budget mode; blocked providers; combos and model-combo mappings; reasoning-routing rules; compression settings; the detailed-logging state, which is sealed as on for the whole window; and the hooks and middleware registry. Sources: `docs/decisions/2026-09-27-omniroute-account-pool.md:290-296`, and the precedent `bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json`, key `gateway_fingerprint`.
- **Sealed inputs.** Any sealed input of either arm differs from the sealing table: A's `~/.codex/AGENTS.md` and skill trees; B's lane-home files, working-directory settings file, skill trees and MCP entry points; either working directory's listing; or a Git repository above a working directory.
- **Argv.** The executed argv falls outside the five source-derived differences, or a control's single change.
- **Environment.** The recorded names differ from the curated list plus B's two `cli_env` names.
- **Schema.** The canonical sha256 of the schema that Codex received differs from the frozen schema.
- **Identity.** On a scored attempt, client-side evidence contradicts the arm, or an A nonce appears in a 20128 row.
- **Controls.** A D1 control does not behave as predicted: a Stage 0 control, a scorer control, or a grader control once Stage C runs.
- **Analysis environment.** It differs from the frozen one.
- **Usage.** Usage is counted twice.

On VOID the attempts are kept, the cause is fixed, and the rule under "Blocks" decides between a rerun in the same cohort and a new cohort.

**Not VOID: B's wire diff.** The comparison of `requestBody` with `providerRequest` is a reported diagnostic. Its known entries are listed in advance: `reasoning.context` `all_turns` dropped, effort mapped, placeholder instructions injected only when the field is empty, and summary `auto` (`docs/decisions/2026-09-27-omniroute-account-pool.md:434-439`; `tools/sota-convergence/landscape-sweep/README.md:209`). An entry outside that list is reported with the verdict and named in the adopt scope.

### Standing rules

- **Shell containment.** If a shell step in either arm reaches 20128's management API in E1a, dispatch stops, the gateway owner receives a containment finding (`docs/decisions/2026-09-27-omniroute-account-pool.md:290-296,300`), and Gate B stays INCOMPLETE until the owner rules.
- **MCP containment.** E1b's expected "reached" is recorded in D1's scope and reported to the gateway owner and the user, who rule on the posture under decision 16. It does not stop dispatch, because each block's fingerprint read-back, hooks and middleware registry included, voids any block during which the gateway configuration changed. E1b "not reached" while its positive control succeeded is recorded as unexpected.
- **Dispatch hold.** If Q1 does not exit 3, no Stage 1 block is dispatched until it is fixed.

E1a, E1b and Q1 never decide D1.

### INCOMPLETE: never a pass

While a run is INCOMPLETE, native stays in force and Gate B stays open. Once the condition changes, the same frozen checks top up the run (Gate A's `on_incomplete`, `evidence/artifacts/token-adoption-e2e-20260926/preregistration.json:3167`). A run is INCOMPLETE when:
- a Stage 0 item is untested, including item 6 without a results record and items 1 and 7 without gateway records;
- A fails a Stage 0 item in at least 2 of its 3 runs;
- a Stage 0 infrastructure failure persists after its one frozen retry;
- an arm cannot run: sign-in, quota refusal, the native reserve reached, a gateway restart or rebuild, a 401, or detailed logging unavailable;
- the shell-containment rule is open;
- fewer than n packets are scored after the reserve is used;
- arm A's Stage 1 mean falls outside [0.10, 0.90]. The packet set was uninformative, so the cohort ends, and a new packet set needs a new seal.

### Stage 0 decides native

When B fails an item under the frozen rule and every control behaved, the result is D1 = `native`. Stage 1 does not run, and B is not max-quality-qualified (`tools/sota-convergence/landscape-sweep/README.md:147`).

### Stage 1 decides (complete, valid run)

The rules apply in this order:
1. **Informative set.** Arm A's mean score lies within [0.10, 0.90]; otherwise the run is INCOMPLETE (above).
2. **Non-inferior.** The test under "Statistics" returns NI.
3. **Inferior.** At least 20 packets have h ≠ 0, and the one-sided 95% lower bound of E[h] from the same bootstrap exceeds δ.
4. **Otherwise** the result is inconclusive.

### Decision table

Every outcome maps to exactly one row, and every row to exactly one consumer column under "What each consumer does with each outcome".

| Row | Outcome | When | D1 | Gate B | Convergence record |
| --- | --- | --- | --- | --- | --- |
| `void` | VOID | a VOID condition holds in a block | unchanged (native in force) | open | stays planned (trial) |
| `incomplete` | INCOMPLETE | an INCOMPLETE condition holds | unchanged (native in force) | open | stays planned (trial) |
| `stage0_native` | Stage 0 native | B fails a Stage 0 item under the frozen rule, and every control behaved | native | passed | reject |
| `ni` | Stage 1 non-inferior | the NI test passes on a complete, valid run | omniroute | passed | adopt_within_scope |
| `inferior` | Stage 1 inferior | rule 3 holds on a complete, valid run | native | passed | reject |
| `inconclusive` | Stage 1 inconclusive | neither NI nor inferior on a complete, valid run | native | passed | retain |
| `unpowered` | Stage 1 unpowered | before the seal, the sizing rule finds no n up to n_max (decision 12), or no calibrated α' | native (untested) | passed (decision 15) | retain, no qualification run |
| `time_box` | Time box | 14 days after the seal, no decided row has been reached | native (untested) | passed (decision 15) | retain, no qualification run |

The `ni` row carries the label "gateway lane non-inferior within δ; max-quality-qualified for the landscape-sweep lane within scope" when δ ≤ 0.05, and "non-inferior within 0.10; not max-quality-qualified" when δ = 0.10. Its scope names this host, the sealed fingerprint, the Codex binary, the sealed inputs of both arms, the curated environment, the landscape-sweep lane and the E1b result. The other rows carry no label.

**The improvement that a D1 = `omniroute` rests on** (`docs/acceptance-evidence-policy.md:81-85`) is pooled weekly capacity across the gateway's accounts (`docs/decisions/2026-09-27-omniroute-account-pool.md:3-6`; `tools/sota-convergence/landscape-sweep/README.md:103`). It is a documented property, not a measured quality or efficiency gain. The seal records one live aggregate read of the pool and one of the native login, as context.

### D2 admission (pending in this cohort)

When Stage C becomes schedulable under its own seal amendment, OpenHands is admitted for bounded trials in the tested form only when all of these hold: the receipt has `evidence_complete` true and no `failure_stage`; an official 4.1.0 verdict is present, whether resolved or unresolved (reported, not used); the gold patch resolves and the empty patch does not, with the exploit results recorded; the P0-P2 receipt is at most 900 s old at dispatch; G2, P3 and G5 passed; and upstream effort `max` is evidenced. Anything else leaves D2 pending, never refuted (`tools/sota-convergence/landscape-sweep/templates.json:2`; `d161f691:blueprints/memory-layer-s3/PREREGISTRATION.md:33`).

### Time box

A sealed run that has reached no decided row 14 days after the seal takes the `time_box` row: D1 = native, labelled "native by time box, not a test result". The owner may move the date only by a dated amendment recorded before it expires. Moving the date changes no analysis, since n is fixed at the seal. Before the seal there is no time box. If the seal has not merged 21 days after confirmation, the owner reports the blocking prerequisite to the user, and nothing is settled by default.

## Statistics

- **Unit.** The packet, with one run per arm in Stage 1. If K is ever raised, attempts are averaged per packet first.
- **Harm.** h_i = score_A,i − score_B,i lies in [−1, 1] in steps of 1/4, because a packet has 4 scored fields. B is non-inferior (NI) when the one-sided upper 95% bound of E[h] is below δ.
- **Test: #431's paired net-difference procedure** (`73fc873e:blueprints/gpt6-lane-compression-ab/preregistration.json:2985-2994`), applied to h:

```python
import numpy as np
from scipy import stats

res = stats.bootstrap(
    (score_a, score_b),
    lambda a, b, axis=-1: np.mean(a - b, axis=axis),   # mean harm of B
    paired=True, vectorized=True, method="percentile",
    n_resamples=99_999, confidence_level=0.95,
    alternative="less",                                  # the upper bound
    rng=np.random.default_rng(20260928),
)
p_ni = (1 + np.sum(res.bootstrap_distribution >= delta)) / (99_999 + 1)
```

  - This is #431's `p_rule`: invert the one-sided percentile bound at the margin, with 99,999 resamples (`73fc873e:blueprints/gpt6-lane-compression-ab/preregistration.json:2993`). NI when p_NI < α′, where α′ is the calibrated level of the bootstrap branch (below).
  - These parameters override SciPy 1.18.1's defaults, which are `method="BCa"`, `n_resamples=9999`, `paired=False` and `alternative="two-sided"` [obs 2026-09-29, `inspect.signature(scipy.stats.bootstrap)` in the pinned environment; the function starts at `scipy@1.18.1:scipy/stats/_resampling.py:297`].
- **Exact fallback.** When fewer than 20 packets have h ≠ 0, or the bootstrap interval is zero-width or nonfinite (`73fc873e:blueprints/gpt6-lane-compression-ab/preregistration.json:2965`), count h⁺ = #{h_i > 0} and h⁻ = #{h_i < 0} and use #431's harmful-minus-beneficial bound (`73fc873e:blueprints/gpt6-lane-compression-ab/preregistration.json:2994`), with the beneficial side scaled by the step 1/4:
  - U(a) = `binomtest(h⁺, n, alternative="less").proportion_ci(1 − a/2, method="exact").high` − ¼ · `binomtest(h⁻, n, alternative="greater").proportion_ci(1 − a/2, method="exact").low`;
  - it is valid: 0 < h ≤ 1 whenever h > 0, and h ≤ −¼ whenever h < 0, so E[h] ≤ P(h > 0) − ¼ · P(h < 0), and a Bonferroni split covers both bounds without assuming they are independent. With binary scores the step is 1, and this is #431's rule exactly;
  - p = inf{a ∈ (0, 1) : U(a) < δ}, found by bisection because U falls as a grows, and p = 1 when no a qualifies. NI when p < α = 0.05;
  - all-concordant data still get a nonzero exact bound. At n = 400, h⁺ = 0 gives an upper bound of 0.0092.
- **Why not the earlier guard.** The earlier draft's harmful-only exact test had very low power and could invert the evidence at the 20-packet switch (finding F-GUARD). #431 dropped that form in its own repair: "Harmful discordance alone is no longer the primary test" (`73fc873e:blueprints/gpt6-lane-compression-ab/preregistration.json:2951`), because "a harmful-discordance-only bound has near-zero power for equal arms" (`73fc873e:blueprints/gpt6-lane-compression-ab/preregistration.json:3176`).
- **A step remains at the switch.** The exact branch is more conservative than the bootstrap branch. One more discordant packet can therefore move a data set from the exact branch (not NI) to the bootstrap branch (NI). This step is inherited from #431's switch, and appendix A's power and false-NI rates include it.
- **Calibrated α′.** The percentile bootstrap is anti-conservative near the margin at these sample sizes. In appendix A, at α′ = 0.05 and n = 400, the worst simulated false-NI rate at E[h] = δ has an upper 95% Clopper-Pearson bound of 0.0678, above #431's bar of 0.055 (`73fc873e:blueprints/gpt6-lane-compression-ab/preregistration.json:3034`). The bootstrap branch therefore uses the first α′ in {0.05, 0.045, 0.04, 0.035, 0.03} that meets the bar at the selected n. #431 leaves its gate open when calibration fails. This criterion instead fixes α′ in the pre-seal sizing amendment, before any data, so that it stays decidable. If no α′ in the grid passes, the `unpowered` row applies. Bowyer et al. show CLT-based error bars running too narrow below a few hundred data points ([arXiv 2503.01747](https://arxiv.org/abs/2503.01747), abstract), the same small-sample risk.
- **Multiplicity.** With F1 alone there is one hypothesis and no correction. With F2 on, `statsmodels.stats.multitest.multipletests([p1, p2], alpha=0.05, method="holm")`, where a missing hypothesis gets p = 1 (`73fc873e:blueprints/gpt6-lane-compression-ab/preregistration.json`, key `analysis.multiplicity`).
- **Diagnostic only.** `scipy.stats.permutation_test`. "Nonsignificant equality is not non-inferiority" (`73fc873e:blueprints/gpt6-lane-compression-ab/preregistration.json`, key `analysis.permutation`).
- **Margin.** δ = 0.05 by default (decision 3), with α = 0.05.

**Sizing rule (frozen; applied in the dated pre-seal sizing amendment).** Simulate the full rule, both branches, the switch and α′ included:
- n is the smallest value in {100, 155, 200, 250, 300, 400, 500} at which P(NI | identical arms) ≥ 0.80 under every required law and under the pilot law. The required laws are field-level differences (M1: |h| = ¼, ½, ¾, 1 with weights 0.6, 0.2, 0.1, 0.1) at 5, 10, 20 and 30% discordance. The pilot law resamples the pilot's 12 observed differences.
- α′ is then calibrated at that n with 10,000 replicates per null law. If the calibrated α′ lowers power below 0.80, the next n is taken.
- If the selected n exceeds n_max (decision 12), or no α′ passes, the `unpowered` row applies.
- n never shrinks because the pilot shows few differences. At low discordance the exact branch governs, and it needs a large n to return NI.

**Planning values (appendix A; a planning simulation, not a result).**
- **At δ = 0.05, n = 400 and α′ = 0.035.** Under the required laws, P(NI) is 0.96, 1.00, 0.99 and 0.96. If B is truly worse by 0.02 (M1, 20% discordance), it is 0.81.
- **The earlier draft's n = 155** (at α′ = 0.05) gives 0.26 at 5% discordance and 0.15 at 10%: the low-discordance regime, where the exact branch requires h⁺ ≤ 2 (≤ 3 when h⁻ ≥ 8). It gives 0.85 at 20% and 0.71 at 30%. If B is truly worse by 0.02, 0.52. So the 80% power the earlier draft stated held only near 20% discordance.
- **The earlier formula's floor, n = 40,** can never return NI at δ = 0.05. Its exact branch fails even at h⁺ = 0, and its bootstrap branch needs at least 20 of 40 packets to differ.
- **If differences are mostly all-or-nothing** (M2: |h| = 1), n = 400 gives 0.97, 0.92, 0.73 and 0.56 at 5-30% discordance. A pilot that shows this pattern raises n through the pilot law, possibly above n_max, which is the `unpowered` row.
- **At δ = 0.10, n = 200 and α′ = 0.04.** P(NI) is 1.00, 0.98, 1.00 and 1.00.

| Key | Value | Meaning |
| --- | --- | --- |
| `alpha` | `0.05` | one-sided level of the NI test |
| `delta_default` | `0.05` | the NI margin (decision 3) |
| `delta_alternative` | `0.1` | allowed only with the narrowed label |
| `step` | `0.25` | smallest nonzero per-packet difference |
| `switch_nonzero` | `20` | fewer packets with h ≠ 0 than this: exact fallback |
| `bootstrap_resamples` | `99999` | paired percentile bootstrap resamples |
| `bootstrap_seed` | `20260928` | analysis rng seed |
| `alpha_boot_grid` | `[0.05, 0.045, 0.04, 0.035, 0.03]` | candidate levels for the bootstrap branch |
| `calibration_bound` | `0.055` | largest allowed upper 95% bound of the false-NI rate |
| `calibration_reps` | `10000` | replicates per null law in the sizing amendment |
| `target_power` | `0.8` | required P(NI) with identical arms |
| `n_grid` | `[100, 155, 200, 250, 300, 400, 500]` | packet counts the sizing rule may choose |
| `required_laws` | `["M1 r=0.05", "M1 r=0.10", "M1 r=0.20", "M1 r=0.30"]` | planning laws every n must satisfy |
| `sim_seed` | `20260929` | appendix A's seed |
| `planning_n_delta_005` | `400` | appendix A's n at δ = 0.05 |
| `planning_alpha_boot_delta_005` | `0.035` | appendix A's α′ at δ = 0.05 |
| `planning_n_delta_010` | `200` | appendix A's n at δ = 0.10 |
| `planning_alpha_boot_delta_010` | `0.04` | appendix A's α′ at δ = 0.10 |
| `n_max_default` | `400` | default budget cap on n (decision 12) |
| `informative_band` | `[0.1, 0.9]` | arm A's Stage 1 mean must lie here |
| `pilot_band` | `[0.2, 0.8]` | arm A's pilot mean must lie here |
| `pilot_packets` | `12` | exploratory pilot size |
| `stage0_repeats` | `3` | K runs of P1 and P2 per arm |
| `stage0_model_runs` | `21` | Stage 0 model runs, controls included |
| `reserve_fraction` | `0.2` | reserve packets, ceil(0.2 n) |
| `block_packets` | `20` | Stage 1 packets per block |
| `time_box_days` | `14` | days after the seal |
| `timeout_ms` | `3000000` | promptfoo `timeoutMs`, the consumer's 3,000 s |
| `max_concurrency_stage0` | `1` | Stage 0 runs serialized |
| `max_concurrency_stage1` | `2` | at most two attempts in flight in Stage 1 |

**Environment.** Python, numpy, scipy and statsmodels are pinned at the seal, and a mismatch is VOID. No statistic is computed on a VOID or INCOMPLETE run.

## Owner and roles

- **Accountable owner.** F-WK-2 is "unassigned; the gateway owner offers to draft it after the resolver's live Stage B" (`docs/decisions/2026-09-28-ecosystem-roadmap.md:176`). The owner must be a session that operates no arm. Decision 2 (the user's) proposes `native-agent-stack-2d`, with `ecosystem-roadmap-2026` as the alternative.
  - `native-agent-stack-2d` took Gate A from 2026-09-29, "on the user's direct instruction", as the peer stated and not independently verified (`docs/decisions/2026-09-28-ecosystem-roadmap.md:304`). It stages the wave (`docs/decisions/2026-09-28-ecosystem-roadmap.md:306`), so it can order Gate A's window W and Gate B's seal.
  - `ecosystem-roadmap-2026` claimed F-2W-3 (`docs/decisions/2026-09-28-ecosystem-roadmap.md:203`).
- **Gateway operator: `token-save-practice-e2e-status`,** the gateway owner (`docs/decisions/2026-09-28-ecosystem-roadmap.md:134`). The roadmap records only its offer to draft the Gate B criterion (`docs/decisions/2026-09-28-ecosystem-roadmap.md:295`). The role below is [prop]: it runs only the gateway side. Its tasks:
  - the F-WK-3 receipt;
  - the fingerprint read-back, including the hooks registry, before and after each block. Gateway reads are an owner precondition, following #445's precedent (`bddb0072:blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json`, key `gateway_fingerprint`);
  - detailed logging (decision 6), any exclusive window (decision 7) and G5 (decision 8), each only where decided;
  - the nonce search in 20128's logged bodies, returning matches only;
  - the #425 steps (F-2W-1, which it accepted, `docs/decisions/2026-09-28-ecosystem-roadmap.md:201`).
- **A/B operator (runner).** A session on this host with the native Codex login. It runs promptfoo from the curated environment and never reads auth state.
- **Seal author.** A session other than the runner. It records the sha256 table and the as-of fact checks.
- **Independent observer and analyst.** It is not the owner, a runner or the gateway operator. It classifies attempts, re-derives the Stage 0 and Stage 1 verdicts, route identity and effort from the stored items, the named rollouts, the launcher records and the gateway nonce matches, and runs the frozen analysis. It may be qualified separately as #425's trace observer (`blueprints/runtime-workers/openhands/README.md:29-31`).
- **Fact re-checker.** A second session re-checks the expected packet values before the seal and after the run.
- **Reviewers.** GPT-6 through a read-only `codex exec` at effort `max` on the PR head, and a Claude `evidence-reviewer`. Each gets one review and one repair round, with residuals recorded.
- **Decider for confirmation.** The accountable owner, under the reading at `docs/decisions/2026-09-28-ecosystem-roadmap.md:311`, after one objection round with the live peers (decision 1). The user decides the items marked "user".

## Freeze and amendment procedure

1. **Draft PR (this change).** It carries `lane:foundation` and a non-empty `## SOTA sources` section (`AGENTS.md:37`), and `python3 scripts/validate.py` runs before the commit (`AGENTS.md:17`). It contains exactly:
   - `blueprints/gate-b-gpt6-route/PREREGISTRATION.md` and `preregistration.json`, with status DRAFT; `frozen`, `run_started` and `execution_authorized` false; and `results` null;
   - `tests/test_gate_b_gpt6_route_preregistration.py`, run once before the files existed and once against the unrepaired draft (both exit 1), then against these files (exit 0). The pattern follows `73fc873e:tests/test_gpt6_lane_compression_ab_preregistration.py` and `452f7b14:tests/test_compaction_window_ab_preregistration.py`. Their fail-first records live in the PR bodies: #416's body reads "Fail-first: 10 failures of 21 for the amendment, then 2 of 23 for the repair", and #431's is its line 35;
   - `{path, sha256, bytes}` rows in `manifests/evidence.json` for the three files, written with `scripts/host_receipts.py`'s `register_file`. It is a shared hot file: take main's copy and re-register (`docs/lanes.md:96-110`).
2. **Exploratory work, never acceptance.** The pilot, the argv and environment read-backs, rollout presence, the `results` field, the overridden `CODEX_HOME` with the placeholder key, schema and effort pass-through, the nonce search, where identity and upstream effort can be read, and the scorer and grader controls. Any exploratory #425 run uses a different SWE-bench row.
3. **Prerequisites.** All of these must hold before the seal:
   - **Order with Gate A** as decision 4 sets it (default: Gate A's recorded pass first).
   - **The F-WK-3 receipt** for the build that will run (`docs/decisions/2026-09-28-ecosystem-roadmap.md:185-189`).
   - **Re-derived values** on that build: the admissible model IDs and the earlier-build facts listed under "Arm B".
   - **A fingerprint read-back with detailed logging on**, since logging is part of the sealed fingerprint.
   - **Decisions 1-16** recorded.
   - **A clear schedule.** Gate A's window W is not active (`docs/decisions/2026-09-28-delegated-decisions.md:99-103`). No #431 or #445 run overlaps. No `apply_codex_lane` or `install_skills` run is planned inside the sealed window, which is announced to the live peers.
   - **The local code** merged, with its tests shown failing first and then passing, and the scorer controls qualified.
   - **One planned convergence record,** `blueprints/convergence-practice/gate-b-route-20260928/experiment.json`: `kind: convergence_experiment`, status `planned` with no observations, lane `native-agent-engineering`, baseline A, candidate B and decision `trial`, declared in `convergence_records` (`scripts/validate_convergence.py:102-105,212,233-238`). One record may carry several candidate arms: the validator requires scoped qualification runs, not one record per candidate (`scripts/validate_convergence.py:136-146`). D2 stays in #425's receipts.
4. **Pre-seal sizing amendment, dated.** It records n, n2, the reserve, δ, α′, the power and false-NI tables at the selected n, the pilot law, the budget and the native reserve.
5. **Reviews.** GPT-6 cross-family and Claude reviews of the complete bundle, with one repair round.
6. **Confirmation.** The owner's dated decision, after the peer objection round, plus the user's decisions for the items marked "user".
7. **Seal.** A separate seal commit, merged to main before any Stage 0 run. It sets status `frozen` and `execution_authorized` true, and carries a sealing amendment by the independent seal author, with a sha256 table covering:
   - packets, reserve and expected values with their as-of times;
   - schemas (canonical JSON), the promptfoo config, the hook, the launcher, the observer, the analysis code and the scorer controls;
   - the Codex binary and the sealed inputs of both arms;
   - the curated environment's name list;
   - the fingerprint read-back;
   - the analysis environment;
   - the schedule and its blocks.

   The runner re-hashes the table before launch and before each block. The order of events comes from the merge time and native records (promptfoo timestamps, gateway row times), because "A matching sha256 shows that the sealed bytes did not change. It does not show when they were sealed" (`blueprints/retrieval-quality-v2/PREREGISTRATION.md:234-235`).
8. **After the seal.**
   - The files are never edited again.
   - Amendments are append-only and dated, with old and new hashes and whether they came before or after the data (`73fc873e:blueprints/gpt6-lane-compression-ab/preregistration.json:3139`).
   - Any change made after an observed result starts a new cohort (`452f7b14:blueprints/compaction-window-ab/preregistration.json:1078`; `73fc873e:blueprints/gpt6-lane-compression-ab/preregistration.json:3137`).
   - Failed attempts are kept with their usage. Argv, working directory, start and end times, exit codes, stdout, stderr and hashes are retained (`docs/acceptance-evidence-policy.md:57-63`).
   - A missed bar is a documented FAIL, never a reason to loosen the bar or rerun silently (`d161f691:blueprints/memory-layer-s3/PREREGISTRATION.md:25`).

## Budget and capacity

**Model runs if every stage proceeds** [inf]:

| Stage | Model runs |
| --- | --- |
| Pilot | 24 (reported apart) |
| Stage 0 | 21 |
| Stage 1 | 2n, plus reserve packets and limit reruns: 800 at the planning n = 400 (δ = 0.05), 400 at n = 200 (δ = 0.10); F2 adds 2·n2 |
| Stage C | none in this cohort |

**Tokens.** Unknown until the pilot. For scale, the two retained native sweep jobs [hist] were:

| Job | Input (cached) | Output | Wall time | Source |
| --- | --- | --- | --- | --- |
| route-job1 | 2,530,158 (2,356,864) | 23,409 | 13.5 min | `evidence/artifacts/omniroute-routing-20260928/route-gpt6-runs.json:7-26` |
| route-job2 | 3,108,187 (2,875,776) | 34,696 | 18.6 min | `evidence/artifacts/omniroute-routing-20260928/route-gpt6-runs.json:69-90` |

Gate B packets should be smaller than these jobs. No estimate is claimed.

**Wall time** [inf]. At 10 to 20 minutes per attempt with two in flight, 800 attempts take about 67 to 133 hours and 400 take about 33 to 67 hours. That fits the 14-day time box only if capacity holds.

**Capacity.**
- **Pool** [obs 2026-09-29T02:28:20Z, `GET /api/usage/provider-limits` on 20128, aggregates only; cache fetched 01:18:44Z-01:18:53Z]: 6 accounts (5 prolite, 1 pro); weekly windows of 604,800 s, used 45-96%; 126 of 600 points remain; resets from 2026-10-03T17:14Z to 2026-10-04T07:02Z.
- **Native login.** Not read. The last read was 43% at 2026-09-28T00:30:32Z [hist].
- **Overlap.** Whether the native login is one of the pooled accounts is [nv]. If it is, arms A and B share quota.
- Whether the pool can carry 800 max-effort attempts within the time box is unknown. The pilot measures the cost per attempt, and decision 12's n_max caps the exposure.

**Controls on spending:**
- Read `scripts/codex_quota.py` and the pool aggregate live before each block. Never gate on a recorded reset.
- Stop dispatching A at the native reserve that decision 12 sets. That makes the run INCOMPLETE, not failed.
- The verdict wave keeps quota priority (`docs/token-practice.md:330`). Gate B's spend lies on the wave's own critical path, so the owner sets its cap.
- Claude-side usage is counted separately.

## What each consumer does with each outcome

The columns are the decision table's consumer columns: `omniroute` is the `ni` row; `native (decided)` the `stage0_native` and `inferior` rows; `native (inconclusive)` the `inconclusive` row; `native (untested)` the `unpowered` and `time_box` rows; and `open` the `void` and `incomplete` rows.

| Consumer | omniroute | native (decided) | native (inconclusive) | native (untested) | open |
| --- | --- | --- | --- | --- | --- |
| `sweep-lane` Landscape-sweep GPT-6 lane, the wave's discovery and refute jobs (`docs/decisions/2026-09-28-ecosystem-roadmap.md:210`) | the operator passes `--gpt6-provider omniroute` with the sealed settings; the code default stays `native` | native | native; gateway use only under decision 11 | native | the wave stays held (`docs/decisions/2026-09-28-ecosystem-roadmap.md:312`) |
| `wave-start` The 32-layer wave start | a person may start it on the gateway lane | a person may start it on the native lane | a person may start it on the native lane | a person may start it on the native lane if decision 15 allows; otherwise held | held |
| `verdict-lane` Verdict lane `codex_lane.py` | native; if F2 was on and its hypothesis passed, a reviewed code change may add the switch implementing exactly the tested argv | native | native | native | native |
| `m5` M5b gate 3 and M5c (`docs/decisions/2026-09-25-skills-trial-and-usage.md:660,664`) | released. M5c lists Harbor among its harnesses (`docs/decisions/2026-09-25-skills-trial-and-usage.md:670-672`), and Harbor strips provider prefixes (`harbor-framework/harbor@1e5c5c6d:src/harbor/agents/installed/codex.py:1339`), so M5c uses the gateway only after its own invocation is checked against the qualified lane | released; native | released; native | released on native if decision 15 allows; otherwise held | held |
| `gateway-profile` Gateway profile note (`adoption/templates/codex.omniroute.config.toml:21-22`) | a reviewed PR may name the qualified scope | unchanged | unchanged | unchanged | unchanged |
| `pool-overturn` Account-pool overturn (`docs/decisions/2026-09-27-omniroute-account-pool.md:476-477`) | not triggered | triggered only if decision 9 counts Gate B as the gateway-parity run | not triggered | not triggered | not triggered |
| `sweep-direction` The user's direction that the sweep runs through the gateway lane (`docs/decisions/2026-09-27-omniroute-account-pool.md:304-305`) | consistent | the wave's sweep runs native, a reversal that decision 10 confirms | native unless decision 11 allows capacity use; the reversal needs decision 10 | native, the reversal under decision 10, labelled untested | unchanged; the wave is held |
| `openhands` OpenHands, #425 (D2, independent of D1) | pending: Stage C is not schedulable in this cohort | pending | pending | pending | pending |
| `runtime-recipes` #426-#428 | parked behind #425 (`docs/decisions/2026-09-28-ecosystem-roadmap.md:239`); they may cite B's Stage 0 effort and usage items as reference for their 20128 control arm, never as their own acceptance | parked | parked | parked | parked |
| `agent-sdks` agent-sdks layer default | unchanged | unchanged | unchanged | unchanged | unchanged |
| `engines-on` #431 engines-on (20129) | unaffected; that route needs its own non-inferiority test | unaffected | unaffected | unaffected | unaffected |
| `convergence-record` The planned record `gate-b-route-20260928` | `adopt_within_scope` | `reject` | `retain` | `retain`, with no qualification run | stays planned, decision `trial` |

## Alternatives considered, and the comparison that would overturn this

### Alternatives considered

1. **Quality-first design: SWE-bench Pro V2 in Harbor, all three arms, K attempts.** Rejected for this gate:
   - arm A would need Harbor to inject the host's `auth.json` into the agent's container (`harbor-framework/harbor@1e5c5c6d:src/harbor/agents/installed/codex.py:1299-1327`), which `AGENTS.md:43` forbids;
   - Harbor strips the model prefix (`harbor-framework/harbor@1e5c5c6d:src/harbor/agents/installed/codex.py:1339`);
   - `1e5c5c6d` is the tag `v0.23.0` (`gh api` compare: identical), and the #381 record found Harbor v0.23.0 unable to "run the unchanged profile in existing worktrees" (`docs/decisions/2026-09-27-capability-gate-harness.md:21`), so it would not test the consumer lane;
   - its sessions are far longer than lookup packets, against 126 of 600 pool points [obs].

   Kept from it: VOID-first precedence, the informative set, the exact fallback, pilot-based sizing, the wire diff as a diagnostic and the grader exploit controls.
2. **Operability-first design.** Rejected: it ran A and B from the interactive `CODEX_HOME`, not the consumer lanes; it combined intersection-union tests with Holm without a computable rule; and it named a default coding worker, which the agent-sdks gate reserves (`docs/grand-catalog-handbook.md:602`). Kept from it: attempt classes, `maxRetries: 0`, the hooks-registry read-back, planted controls, an owner who operates no arm, and an improvement leg.
3. **A comparative OpenHands contrast.** It needs a Codex arm that produces patches under the same grader, which means either new glue or the auth-store copy. It is left to a later cohort. One convergence record can carry it.
4. **The consumer's own runner (`codex_call.sh`) under promptfoo's custom-script provider.** It gives the byte-identical argv and the consumer's own `events.jsonl` (`tools/sota-convergence/landscape-sweep/codex_job.py:686-689`), but adds a local wrapper around a local runner. It is the fallback if the argv or environment read-back cannot be reconciled.
5. **inspect_swe.** Its Codex agent routes model calls through Inspect's `sandbox_agent_bridge` (`meridianlabs-ai/inspect_swe@7eb8dd64:src/inspect_swe/_codex_cli/codex_cli.py:369-388`), so the call goes through an Inspect model provider rather than Codex's own ChatGPT login [inf].
6. **The recorded mechanical parity probe** (merged commit `b9abcc5f`, build `dd6e9607e`, `docs/decisions/2026-09-27-omniroute-account-pool.md:304-308`). It is historical, has no failing controls and ran on an older build, so it is reference only.
7. **Waiting for `omniroute-codex-max-parity`.** It is not frozen and has not run (`docs/decisions/2026-09-27-omniroute-account-pool.md:315-316`).
8. **The earlier harmful-only exact guard.** Rejected (F-GUARD): low power and the evidence inversion at the switch.
9. **Gateway identity by time window under concurrent A and B runs.** Rejected (F-IDENT): overlapping windows make it undecidable, and `/v1/responses` rows carry a gateway-generated ID. The attempt nonce replaces it.

### Comparison that would overturn it

- **A contradicting cohort.** A later, independently preregistered cohort in the same scope, with a tighter δ or a larger n, contradicts D1. It replaces D1.
- **Changed inputs.** D1 = `omniroute` lapses when any of these change: the route-relevant gateway fingerprint (every field above except the detailed-logging switch), the Codex binary, the sealed inputs of either arm, the curated environment list, or the search backend. Stage 0 must then pass again on the new inputs. A new Stage 1 cohort is also needed if the change touches request rewriting or the rendered prompt, checked by `codex debug prompt-input` parity (`tools/sota-convergence/landscape-sweep/README.md:171-186`).
- **The logging switch is excluded from the lapse set.** It controls what the gateway records (`tools/sota-convergence/landscape-sweep/README.md:209`), not the request it sends upstream [src, not measured]. Turning logging off after the run therefore does not lapse D1. If any evidence shows the switch changes the upstream request, D1 lapses.
- **G5 applied later.** When G5 blocking is applied to 20128 for Stage C (decision 8), a D1 = `omniroute` lapses until Stage 0 passes again on the new fingerprint. This is stated in advance.
- **A cause that goes away.** A D1 = `native` from a Stage 0 failure reopens when the failed item's cause changes, for example with a search-backend bake-off result (`docs/decisions/2026-09-27-omniroute-account-pool.md:478`).
- **Gate A fails.** If Gate A fails a required row, token fixes and a Gate A rerun come before Gate B (`docs/decisions/2026-09-28-ecosystem-roadmap.md:283`). A carrier change after the seal reopens D1.
- **Wave evidence.** If the chosen lane's schema-valid completion rate over the first 100 wave jobs falls more than δ below its Stage 1 rate, D1 reopens through a new cohort.
- **Arm C changes.** A qualified independent observer and the matching recipe change make Stage C schedulable. If #431 selects engines-on, arm C changes only through a new cohort.
- **Better tooling.** A promptfoo release or profile setting that removes the need for the launcher (`docs/decisions/2026-09-27-capability-gate-harness.md:33-37`), or an upstream harness that runs both consumer lanes unchanged with less local code. It is adopted by a dated amendment before the seal, or in a new cohort after it.
- **Other hosts.** Any other host needs its own run (`AGENTS.md:42`).

## User decisions required (numbered, each with a recommended default)

Per the reading at `docs/decisions/2026-09-28-ecosystem-roadmap.md:311`, items marked "owner" are decided by the accountable owner under the user's delegation, and the user can take any of them back. Items marked "user" change a user-decided record, or the gate's own meaning, and stay with the user. All sixteen are recorded before the seal, so the decision table is fully determined when the run starts. One point is fixed and not offered: no auth store is ever copied (`AGENTS.md:43`).

| # | Decision | Decider | Recommended default |
| --- | --- | --- | --- |
| 1 | Confirm this criterion | owner | confirm after the GPT-6 and Claude reviews, one repair round and one objection round with live peers |
| 2 | Accountable owner for F-WK-2 | user | native-agent-stack-2d; alternative ecosystem-roadmap-2026 |
| 3 | Margin δ and the sizing rule | owner | δ = 0.05, n by the frozen sizing rule (planning n = 400, α′ = 0.035) |
| 4 | Seal order with Gate A | owner | the seal waits for Gate A's recorded pass |
| 5 | Family F2 (verdict lane) | owner | off |
| 6 | Detailed pipeline logging on 20128 for the whole sealed window | user | yes, bodies private under the gateway owner's retention rule |
| 7 | An exclusive 20128 window for Stage 0 | user | not required while decision 6 is yes |
| 8 | G5 no-auth provider blocking on 20128 | user | not applied in this cohort |
| 9 | Gate B as the account-pool's preregistered gateway-parity run | user | yes for Stage 0 native or Stage 1 inferior on a complete, valid run; no otherwise |
| 10 | A native D1 reverses the sweep's gateway direction | user | accept the reversal for the wave |
| 11 | Gateway capacity use after a native D1 | user | no |
| 12 | Budget, native reserve and n_max | owner | pilot, Stage 0 and Stage 1 at the sized n, with n_max = 400; stop A at the reserve the owner sets |
| 13 | Exploratory #425 runs | owner | allowed on a different SWE-bench row, never acceptance |
| 14 | Hosts | owner | this workstation only |
| 15 | Whether an untested native settlement releases the gate | user | yes: the wave may start on the native lane, labelled untested |
| 16 | E1b's management-API reach and the account-pool posture | user | record and report; D1 is still decided |

1. **Confirm this criterion.** Decider: owner, under the reading at `docs/decisions/2026-09-28-ecosystem-roadmap.md:311`. Alternative: the user confirms, as the roadmap first recorded (`docs/decisions/2026-09-28-ecosystem-roadmap.md:252`).
2. **Accountable owner for F-WK-2.** Default `native-agent-stack-2d`: it operates no arm, holds Gate A as the peer stated (`docs/decisions/2026-09-28-ecosystem-roadmap.md:304`) and stages the wave (`docs/decisions/2026-09-28-ecosystem-roadmap.md:306`). Alternative `ecosystem-roadmap-2026` (`docs/decisions/2026-09-28-ecosystem-roadmap.md:203`). The named session accepts in writing on the PR.
3. **Margin and sizing.** Default δ = 0.05 with n from the sizing rule. δ = 0.10 (planning n = 200) is allowed only with the narrowed label "non-inferior within 0.10, not max-quality-qualified".
4. **Seal order with Gate A.** Default: the seal waits for Gate A's recorded pass. The basis is an inference, and the cited lines do not say it outright. The roadmap relays the user's order to prove the token stack end to end first and then run the full waves (`docs/decisions/2026-09-28-ecosystem-roadmap.md:306`). If Gate A fails a required row, token fixes and a rerun come before Gate B (`docs/decisions/2026-09-28-ecosystem-roadmap.md:283`). Arm B's lane carries the token stack (its MCP servers and instruction block), so Gate A's fixes can change B's sealed inputs. Alternative: seal Gate B outside window W, accepting that a later token-stack change lapses a D1 = `omniroute`.
5. **Family F2.** Default off: `codex_lane.py` stays native, and the wave records the lane used for each stage. Turning F2 on adds 2·n2 runs and the Holm family.
6. **Detailed pipeline logging on 20128 for the whole sealed window.** Default yes. It is sealed as on and read back at each block boundary, and it is excluded from D1's lapse set. Captured bodies stay private; the gateway operator returns only nonce matches and effort values. This effectively blocks the gate: without it, items 1 and 7 are untested unless decision 7 provides an exclusive window and responses carry encrypted reasoning. Decider: user, because it changes the user-chosen keyless shared gateway for every caller (`docs/decisions/2026-09-27-omniroute-account-pool.md:285-302`).
7. **Exclusive 20128 window for Stage 0.** Default: not required while decision 6 is yes, since nonce attribution works under concurrency. If decision 6 is no, Stage 0 needs this window, with other GPT-6 callers paused and told in advance.
8. **G5 no-auth provider blocking.** Default: not applied in this cohort, since Stage C is not schedulable. Applying it later changes the fingerprint and lapses a D1 = `omniroute` until Stage 0 passes again.
9. **Gate B as the account-pool's gateway-parity run** (`docs/decisions/2026-09-27-omniroute-account-pool.md:476-477`). Default yes for the `stage0_native` and `inferior` rows, no for every other row. Decider: user, because that record is a user decision (`docs/decisions/2026-09-27-omniroute-account-pool.md:3-6`).
10. **A native D1 reverses the user's direction that the sweep runs through the gateway lane** (`docs/decisions/2026-09-27-omniroute-account-pool.md:304-305`). Default: accept the reversal for the wave.
11. **After a native D1, may the wave use the gateway lane for capacity, labelled "gateway, not max-quality-qualified"?** Default no: the wave runs native under the quota plan (`docs/token-practice.md:324-333`).
12. **Budget, native reserve and n_max.** Default: pilot, Stage 0 and Stage 1 at the sized n with n_max = 400. Stop dispatching A when a live native read reaches the reserve the owner sets. The verdict wave keeps priority. Decider: owner, within the user's 2026-09-26 quota policy (`docs/token-practice.md:324-333`).
13. **Exploratory #425 runs.** Default: allowed on a different SWE-bench row, labelled exploratory, never acceptance (`docs/decisions/2026-09-28-ecosystem-roadmap.md:43`). The gateway owner operates them.
14. **Hosts.** Default: this workstation only. The Mac needs its own run (`AGENTS.md:42`).
15. **Untested native settlement.** Whether the `unpowered` and `time_box` rows count as "Gate B passed" and release the wave on the native lane. Default yes, labelled "native, untested", with no account-pool overturn and with the gateway lane unqualified. Decider: user, because it sets what the user's gate means.
16. **E1b's reach of the keyless management API.** The account-pool record's posture overturn names "any untrusted local process" (`docs/decisions/2026-09-27-omniroute-account-pool.md:300`), and a model-driven `ctx_execute` may be one. Default: record the reach in D1's scope and report it; D1 is still decided, and the per-block fingerprint read-back guards the run. Alternative: treat the reach as that overturn, which turns login and key requirements back on.

## Sources (pins, URLs, file:line)

### This repository at origin/main `11648f9a`

Every `path:line` in this file is listed with its needle in the JSON's `citation_checks`, and the test re-checks each one at the pin. The main files are:
- **Roadmap and delegation:** `docs/decisions/2026-09-28-ecosystem-roadmap.md`; `docs/decisions/2026-09-28-delegated-decisions.md`; `docs/decisions/2026-09-25-skills-trial-and-usage.md`.
- **Gateway:** `docs/decisions/2026-09-27-omniroute-account-pool.md`; `adoption/templates/codex.omniroute.config.toml`; `adoption/templates/codex.config.template.toml`.
- **Consumer lane:** `tools/sota-convergence/landscape-sweep/build_args.py`, `codex_job.py`, `README.md` and `templates.json`; `tools/sota-convergence/codex_lane.py`.
- **Harness precedent (#381):** `docs/decisions/2026-09-27-capability-gate-harness.md`; `tools/capability-gate/m13.yaml`; `tools/capability-gate/codex-profile-exec`.
- **OpenHands recipe:** `blueprints/runtime-workers/openhands/README.md`, `pins.json`, `receipt.py`, `host.py` and `evidence/repair-round-commands.json`.
- **Evidence and convergence rules:** `docs/acceptance-evidence-policy.md`; `docs/convergence-architecture.md`; `scripts/validate_convergence.py`; `scripts/codex_quota.py`; `docs/token-practice.md`; `AGENTS.md`; `docs/lanes.md`; `.github/pull_request_template.md`; `docs/grand-catalog-handbook.md`; `catalogs/landscape/foundation.json`.
- **Receipts and precedents:** `evidence/artifacts/omniroute-routing-20260928/route-gpt6-runs.json`; `evidence/artifacts/token-adoption-e2e-20260926/preregistration.json`; `blueprints/retrieval-quality-v2/PREREGISTRATION.md`; `evidence/artifacts/sota-refresh-20260926/codex/accept_codex_ws.py` and its `results/websearch-0.157.1.json`.

### Open PR heads

- **#445 at `bddb0072`:** `blueprints/convergence-practice/gateway-ab-r02-20260927/plan.json`, keys `decision_rule.invalid`, `statistics`, `analysis_environment` and `gateway_fingerprint`.
- **#431 at `73fc873e`:** `blueprints/gpt6-lane-compression-ab/preregistration.json` lines 2951 (`noninferiority`), 2965 (`degenerate_interval_guard`), 2985-2994 (`paired_net_test`: `p_rule` at 2993, `exact_fallback` at 2994), 3034 (`calibration`), 3137 and 3139 (`sealing`) and 3176 (the anti-pattern entry); keys `analysis.multiplicity` and `analysis.permutation`; `tests/test_gpt6_lane_compression_ab_preregistration.py`.
- **#416 at `452f7b14`:** `blueprints/compaction-window-ab/preregistration.json` line 1078 (`amendment_rule`); `tests/test_compaction_window_ab_preregistration.py`.
- **#390 at `d161f691`:** `blueprints/memory-layer-s3/PREREGISTRATION.md` lines 25 and 33.
- **PR bodies** read with `gh pr view` at 2026-09-29T02:38Z: #416 (fail-first record), #431 (line 35), #426, #427 and #428 (their arms).
- **The #469 comment:** https://github.com/seathatflowsinourveins/native-agent-stack/pull/469#issuecomment-5880981981.

### Upstream and installed packages

- **promptfoo** at tag `0.123.1`, read through `gh api` on 2026-09-29: `site/docs/providers/openai-codex-sdk.md` lines 33, 70, 72, 218, 219, 231, 238, 242 and 301; `site/docs/configuration/expected-outputs/deterministic.md` lines 340-389; `site/docs/configuration/reference.md` line 50.
- **Installed promptfoo 0.123.1** [src]: `dist/src/codex-sdk-CHgLS7xg.js` (`validateWorkingDirectory`, `buildThreadOptions`, `getResolvedCliConfig`, `prepareEnvironment`, `buildCodexProviderResponse`) and `dist/src/evaluator-DlYW7Rgb.js` (the per-step `timeoutMs` abort).
- **Installed `@openai/codex-sdk` 0.153.4** [src]: `dist/index.js` lines 5-27, 79-92, 88-90, 98-121, 145-146, 176-274; `dist/index.d.ts` lines 78-82.
- **Codex:** `rust-v0.158.0`, published 2026-09-28T05:07:23Z, https://github.com/openai/codex/releases/tag/rust-v0.158.0.
- **Harbor:** `harbor-framework/harbor@1e5c5c6d` (identical to tag `v0.23.0`): `src/harbor/agents/installed/codex.py` lines 1299-1327 and 1339.
- **inspect_swe:** `meridianlabs-ai/inspect_swe@7eb8dd64:src/inspect_swe/_codex_cli/codex_cli.py` lines 369-388.
- **SWE-bench:** `SWE-bench/SWE-bench@v5.0.1:CHANGELOG.md` lines 12, 34-35 and 41.
- **OpenHands:** `OpenHands/software-agent-sdk@fcc102a` (tag `v1.49.6`) and `OpenHands/benchmarks@405bae71`, as pinned in `pins.json`.
- **SciPy 1.18.1** [obs, pinned uv environment]: the `scipy.stats.bootstrap` signature defaults; `scipy/stats/_resampling.py` line 297.
- **Papers:** Miller, "Adding Error Bars to Evals", https://arxiv.org/abs/2411.00640; Bowyer et al., "Position: Don't Use the CLT in LLM Evals With Fewer Than a Few Hundred Datapoints", https://arxiv.org/abs/2503.01747. Both were read at the abstract level only.

### Live observations (GET requests and local reads only, aggregates only, no credentials)

- **2026-09-29T02:27:37Z:** `codex --version` returned 0.157.1 and `promptfoo --version` 0.123.1. `systemctl --user show` returned both units active, with their start times and install names, and each unit's `dist/BUILD_SHA` was read (`5fc47d970`, `c3fa5a15e`). `GET /v1/models` (ID and owner counts) and `GET /api/logs/detail?limit=0` (the `enabled` flag) ran on both ports.
- **2026-09-29T02:28:20Z:** `GET /api/usage/provider-limits` on 20128, reduced to plan counts, used and remaining points, window lengths and reset times.
- **2026-09-29T02:38:20Z:** `gh pr list --state open` found no Gate B or rebuild-receipt PR among 30 open PRs; `gh pr view` read #416, #426, #427, #428 and #431.
- **2026-09-29T03:04:26Z:** no openhands tool directory; `harbor` not on PATH; `git ls-remote origin refs/heads/main` returned `b0fb65b4`.

## Decisions taken in the repair

**DT-1.** The decision table is total. It has eight rows, each mapped to exactly one consumer column. "Gate B passed" is defined by those rows, and two untested-native rows (`unpowered`, `time_box`) close the gate as native, never as a test result, subject to decision 15. This is the most conservative total rule that still terminates: native is the incumbent and the code default, and a person still starts the wave. (CLAIM-1, F-TIMEBOX)

**DT-2.** The test is #431's procedure: a paired percentile bootstrap with p-inversion at the margin, and the harmful-minus-beneficial exact fallback below 20 discordant packets. The beneficial side is scaled by the 1/4 step, which is the only change needed for bounded, non-binary differences. n comes from simulating the whole rule. The one declared deviation is that α′ is calibrated before any data instead of leaving the gate open, which keeps it decidable with the simulated false-NI rate held to #431's bar. (CLAIM-4, F-GUARD, R-CALIB)

**DT-3.** Identity uses an attempt nonce found in 20128's logged request bodies, which works under concurrency. Stage 0 is also serialized. An exclusive window is not needed while logging is on. (F-IDENT)

**DT-4.** Detailed logging is sealed as on for the whole sealed window and read back at each block boundary. It is excluded from D1's lapse set, with the reason stated. G5 is not applied in this cohort, and applying it later is a stated lapse. (F-FPRINT)

**DT-5.** Stage C is gated on its preconditions and consumes nothing until they hold. D2 is pending in every outcome of this cohort. (F-D2, CLAIM-2)

**DT-6.** The runner inherits a curated environment with no credential-bearing names. This is recorded as a declared difference from the consumer, which inherits everything. (F-CITE-ENV, F23)

**DT-7.** The argv differences are fixed from the SDK's source. `approval_policy` and `model_provider` are not set, and the launcher removes the SDK's originator variable. The pilot confirms the list and never widens it. (F-ARGV-LIST, CLAIM-6)

**DT-8.** The launcher `exec`s Codex and never tees or forks. The records come from promptfoo's stored `raw` and from the rollout named by `sessionId`, and `timeoutMs` enforces the consumer's 3,000 s. (F-TIMEOUT, F-LOCALCODE)

**DT-9.** An informative-set failure is INCOMPLETE and needs a new packet set in a new cohort, never a settled native. The pilot gates packet calibration with the band [0.20, 0.80]. (F-INFORM)

**DT-10.** The Gate A order is an owner decision with a stated inference, not a fixed point. (F-GATEA)

**DT-11.** E1b probes the MCP path with two controls. Its expected reach is recorded and reported, and the posture ruling goes to the user as decision 16. (F-E1)

**DT-12.** δ = 0.05 stays the default, with planning n = 400. δ = 0.10 with n = 200 is the cheaper alternative with the narrowed label, and n_max defaults to 400. (CLAIM-4)

**DT-13.** The planned convergence record is added at confirmation, not in this draft PR, which carries only the three new files and their registrations. (R-CONV-RECORD)

**DT-14.** The owner stays a proposal: decision 2, the user's. The roadmap's lines on who confirms are quoted both ways. (brief item 5)

## Repair-round dispositions

Findings of the method refuter (refute:method) and the citation refuter (refute:citations), and four gaps this repair found (R-*). Actions: fixed, reworded, declined or user-decision.

| ID | Action | Where | Note |
| --- | --- | --- | --- |
| `CLAIM-1` | fixed | Scope ("Gate B passed"); Pass rule (decision table) | eight total rows; each cause the refuter listed is fixed under its own ID |
| `CLAIM-2` | fixed | Arms; Task set | working directory and Git check set, item 6's record named, Stage C gated |
| `CLAIM-3` | fixed | Metrics (usage accounting) | the claim held; the one gap, MCP-side local model work, is now declared unknown |
| `CLAIM-4` | fixed | Statistics; appendix A | power recomputed for the full rule; 80% held only near 20% discordance at n = 155 |
| `CLAIM-5` | fixed | Arms (local integration code) | five local components specified with reads, emits and tests; the D2 runner labelled |
| `CLAIM-6` | fixed | JSON arms and user decisions | the arm argv is compared with the consumer's for both arms; deciders unified; the test enforces agreement |
| `F-IDENT` | fixed | Task set (item 7); Pass rule | nonce attribution; Stage 0 serialized; a missing gateway row is INCOMPLETE |
| `F-FPRINT` | fixed | Pass rule (VOID); overturn | logging sealed on for the window, excluded from the lapse set; G5 not in this cohort |
| `F-GUARD` | fixed | Statistics | #431 harmful-minus-beneficial fallback; power simulated with the guard |
| `F-CWD` | fixed | Arms (harness, A, B) | `working_dir` = staged `<work>/empty`, `skip_git_repo_check` true, settings Read rules sealed |
| `F-SEARCH` | fixed | Task set (item 6) | reads `results` in stored items, else the rollout, else INCOMPLETE, settled in the pilot |
| `F-D2` | fixed | Scope; Arm C; Stage C | a smoke check that cannot decide D2; dispatch gated on observer qualification |
| `F-UNSEALED` | fixed | Arms A and B; Pass rule (VOID) | `~/.codex/AGENTS.md` and the skill trees sealed; lane-home rule replaced by sealed-input hashes |
| `F-E1` | fixed | Task set (E1b); Standing rules | a `ctx_execute` probe with two controls; decision 16 |
| `F-SCORER` | fixed | Task set (scorer controls) | planted wrong values, normalization edge cases and negative answers |
| `F-LOCALCODE` | fixed | Arms (local integration code) | launcher, hook, observer, analysis and scorer controls specified and labelled |
| `F-TIMEBOX` | fixed | Pass rule (decision table, time box) | the time box maps to one row and one action |
| `F-INFORM` | fixed | Task set (pilot); Pass rule (INCOMPLETE) | pilot calibration band; an uninformative set is INCOMPLETE |
| `F-CITE-ENV` | fixed | Arms (curated environment) | citation moved to build_args.py and README; curated environment |
| `F-SCHEMA-BYTES` | fixed | Arms (launcher, argv read-back) | canonical JSON hash, captured before `exec` |
| `F-ARGV-LIST` | fixed | Arms (argv read-back) | differences fixed from SDK source; originator removed; no pilot-derived allowances |
| `F-TIMEOUT` | fixed | Arms (evaluateOptions, launcher) | `timeoutMs: 3000000`; the launcher `exec`s, so no orphaned Codex |
| `F-BLOCK` | fixed | Pass rule (Blocks) | block defined; VOID scope and cohort rule stated |
| `F-GATEA` | reworded | User decisions (4) | now an owner decision with its inference stated |
| `GAP` | fixed | Arms; Sources | host facts re-observed; promptfoo lines verified; the statistics re-run in the pinned environment |
| `F01` | fixed | Arm B; Pass rule (VOID) | `[features]` and the filter listed; the diff rule replaced by sealed-input hashes |
| `F02` | fixed | Arm B (earlier-build facts) | each fact pinned to its source build: `045aa81f3`/`dd6e9607e`, `a58000c7`, installed 3.8.51 |
| `F03` | fixed | Pins | re-pinned to `11648f9a`; later main heads noted |
| `F04` | fixed | Scope | two gateway rewrites against two Codex-side behaviours |
| `F05` | fixed | Arms (evaluateOptions) | at most two attempts of either arm in flight |
| `F06` | fixed | Scope (D1) | refusal cited at build_args.py:606-608 |
| `F07` | fixed | Arm A; Budget | route-job1 at 7-26, route-job2 at 69-90 |
| `F08` | fixed | Arm C | G2 cited at README:895-912, G5 at 772-778 |
| `F09` | fixed | Metrics (arm C usage) | cited at README:440-457 |
| `F10` | fixed | Statistics; Sources | p_rule at 2993, exact_fallback at 2994, range extended |
| `F11` | fixed | Freeze (seal) | cited at PREREGISTRATION.md:234-235 |
| `F12` | fixed | Freeze (draft PR) | fail-first records cited from the PR bodies |
| `F13` | fixed | Scope | labelled [doc] with README:129 |
| `F14` | fixed | Freeze (prerequisites) | one record may carry several candidates |
| `F15` | fixed | Scope (not decided) | roadmap:239 quoted; PR bodies cited for the missing native arm |
| `F16` | fixed | Scope (not decided) | the #431 link cited at openhands README:147-148 |
| `F17` | fixed | Scope (not decided) | the Claude-lane exclusion labelled [prop] |
| `F18` | fixed | Owner and roles | the gateway operator's role labelled [prop]; roadmap:295 quoted |
| `F19` | fixed | Metrics (class X) | 71 of the 287 candidates |
| `F20` | fixed | Alternatives (1) | `1e5c5c6d` shown identical to tag `v0.23.0` |
| `F21` | fixed | Statistics | SciPy defaults read from the pinned environment |
| `F22` | fixed | Alternatives (1) | the uncited session count removed |
| `F23` | fixed | Arms (curated environment) | stale citation replaced by build_args.py:325-327 and 336-337 |
| `U01` | fixed | Arms; Sources | promptfoo 0.123.1 doc lines read through `gh api` |
| `U02` | fixed | Arms (pins) | `rust-v0.158.0` publication read through `gh api` |
| `U03` | fixed | Alternatives (1) | Harbor lines read at `1e5c5c6d` |
| `U04` | reworded | Alternatives (5) | lines 369-388 read; the login consequence labelled [inf] |
| `U05` | fixed | Stage C | changelog lines 12, 34-35 and 41 read |
| `U06` | fixed | Arm C | tag `v1.49.6` = `fcc102a6`; `405bae71` exists |
| `U07` | reworded | Metrics | abstract only; section attributions and the sizing formula removed |
| `U08` | reworded | Statistics | the CLT claim stated as the abstract gives it |
| `U09` | fixed | Arm B; Budget; Sources | pool, models and PR list re-observed; the call-log row claim dropped |
| `R-CALIB` | fixed | Statistics | the percentile bootstrap exceeds the size bar at α′ = 0.05; α′ calibrated pre-data |
| `R-CACHEWRITE` | fixed | Metrics (usage accounting) | the SDK zero-fills a missing cache-write count |
| `R-ROLLOUT-SCOPE` | fixed | Arm A; Owner and roles | the observer reads only the rollouts its attempts named |
| `R-CONV-RECORD` | fixed | Freeze (prerequisites) | the planned record moves to confirmation |

## Appendix A: sizing and power script

Run with `UV_NO_CONFIG=1 uv run --no-project --python 3.14 --with numpy==2.5.3 --with scipy==1.18.1 python gate_b_sizing.py`. On this host it took 321 s and exited 0 at 2026-09-29T03:01:07Z. The output below is its complete stdout. The simulation resamples multinomial value counts, which draws from exactly the bootstrap distribution, and it checks this against `scipy.stats.bootstrap` on two fixtures first. The pre-seal sizing amendment reruns it with the pilot law and 10,000 calibration replicates.

```python
"""Gate B sizing and power: the full non-inferiority rule, exact fallback included (appendix A).

Run: UV_NO_CONFIG=1 uv run --no-project --python 3.14 --with numpy==2.5.3 --with scipy==1.18.1 python gate_b_sizing.py
h = score_A - score_B on one packet (the harm of B), in steps of 1/4 because a packet has 4 scored fields.
B is non-inferior (NI) when the one-sided upper 95% bound of E[h] is below delta.
"""
import math

import numpy as np
from scipy import stats

ALPHA = 0.05
STEP = 0.25                     # smallest nonzero |h|: one field of four
SWITCH = 20                     # fewer packets with h != 0 than this: exact fallback (#431 degenerate_interval_guard)
VALUES = np.arange(-4, 5) / 4   # the nine possible values of h
REPS, CALIBRATION_REPS, RESAMPLES, SEED = 1000, 4000, 2000, 20260929
MAGNITUDES = {"M1": (0.6, 0.2, 0.1, 0.1), "M2": (0.0, 0.0, 0.0, 1.0)}  # weights of |h| = 1/4, 2/4, 3/4, 1
REQUIRED = [("M1", r) for r in (0.05, 0.10, 0.20, 0.30)]
REPORTED = [("M1", 0.02)] + [("M2", r) for r in (0.05, 0.10, 0.20, 0.30)]
GRID = (100, 155, 200, 250, 300, 400, 500)
ALPHA_BOOT_GRID = (0.05, 0.045, 0.04, 0.035, 0.03)
NULL_LAWS = [(m, r) for m in ("M1", "M2") for r in (0.15, 0.20, 0.30, 0.40, 0.60)]


def upper_harm(hp, hm, n, a):
    """#431 exact_fallback with the beneficial side scaled by STEP: an upper bound on E[h] at level 1 - a.
    E[h] <= P(h > 0) - STEP * P(h < 0), because 0 < h <= 1 and h < 0 implies h <= -STEP; Bonferroni over the two."""
    up = stats.binomtest(hp, n, alternative="less").proportion_ci(confidence_level=1 - a / 2, method="exact").high
    low = stats.binomtest(hm, n, alternative="greater").proportion_ci(confidence_level=1 - a / 2, method="exact").low
    return up - STEP * low


def exact_p(hp, hm, n, delta):
    """p = inf{a in (0, 1): upper_harm(a) < delta}. The bound falls as a grows, so bisect; p = 1 when none."""
    lo, hi = 1e-12, 1 - 1e-12
    if upper_harm(hp, hm, n, hi) >= delta:
        return 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if upper_harm(hp, hm, n, mid) < delta else (mid, hi)
    return hi


def law(r, magnitude, harm_share=0.5):
    """P(h = v) for v in VALUES: discordance r, |h| weights, P(h > 0 | h != 0) = harm_share."""
    w = np.array(MAGNITUDES[magnitude]) / sum(MAGNITUDES[magnitude])
    p = np.zeros(9)
    p[4] = 1 - r
    p[5:] = r * harm_share * w
    p[:4] = (r * (1 - harm_share) * w)[::-1]
    return p


def mean_abs(magnitude):
    return float(np.array(MAGNITUDES[magnitude]) / sum(MAGNITUDES[magnitude]) @ np.arange(1, 5) / 4)


def shifted_law(r, magnitude, harm):
    """E[h] = harm at discordance r; None when r is too small to carry that harm."""
    return None if r * mean_abs(magnitude) <= harm else law(r, magnitude, (1 + harm / (r * mean_abs(magnitude))) / 2)


def decision_table(n, delta):
    """Exact-branch NI for every (h+, h-) with h+ + h- < SWITCH: p < ALPHA iff upper_harm(ALPHA) < delta."""
    return {(hp, hm): upper_harm(hp, hm, n, ALPHA) < delta
            for hp in range(SWITCH) for hm in range(SWITCH - hp) if hp + hm <= n}


def p_ni(n, p, delta, table, rng, reps, alpha_boot=ALPHA):
    wins = 0
    for _ in range(reps):
        counts = rng.multinomial(n, p)
        hp, hm = int(counts[5:].sum()), int(counts[:4].sum())
        if hp + hm < SWITCH:
            wins += table[(hp, hm)]
        elif np.count_nonzero(counts) == 1:            # zero-width bootstrap interval: exact fallback
            wins += upper_harm(hp, hm, n, ALPHA) < delta
        else:  # percentile bootstrap of mean(h): resampling packets = multinomial resampling of the value counts
            means = rng.multinomial(n, counts / n, size=RESAMPLES) @ VALUES / n
            wins += (1 + np.sum(means >= delta)) / (RESAMPLES + 1) < alpha_boot
    return wins / reps


def calibrate(n, delta, table, rng):
    """First alpha' in ALPHA_BOOT_GRID whose worst false-NI rate at the margin (E[h] = delta) has the upper end of
    its two-sided 95% Clopper-Pearson interval at or below 0.055 (#431 power_simulation.calibration)."""
    for alpha_boot in ALPHA_BOOT_GRID:
        worst = 0.0
        for magnitude, r in NULL_LAWS:
            p = shifted_law(r, magnitude, delta)
            if p is not None:
                k = round(p_ni(n, p, delta, table, rng, CALIBRATION_REPS, alpha_boot) * CALIBRATION_REPS)
                worst = max(worst, stats.binomtest(k, CALIBRATION_REPS).proportion_ci(method="exact").high)
        print(f"    alpha'={alpha_boot}: worst false NI at the margin, CP95 upper {worst:.4f}")
        if worst <= 0.055:
            return alpha_boot
    return None


def main():
    rng = np.random.default_rng(SEED)
    print("check: multinomial shortcut vs scipy.stats.bootstrap (upper 95% bound of mean h)")
    for name, h in (("fixture-a", np.r_[np.full(30, 0.25), np.full(20, -0.25), np.zeros(105)]),
                    ("fixture-b", np.r_[np.full(12, 1.0), np.full(10, -0.5), np.zeros(133)])):
        res = stats.bootstrap((h,), np.mean, method="percentile", n_resamples=99_999, alternative="less",
                              rng=np.random.default_rng(SEED))
        values, counts = np.unique(h, return_counts=True)
        means = rng.multinomial(len(h), counts / len(h), size=99_999) @ values / len(h)
        print(f"  {name}: scipy {res.confidence_interval.high:.4f}  shortcut {np.quantile(means, 0.95):.4f}")
    print("normal-approximation n of the earlier draft (sigma 0.25), for comparison only")
    for m, delta in ((1, 0.05), (1, 0.10), (2, 0.05), (2, 0.10)):
        z = stats.norm.ppf(1 - ALPHA / m) + stats.norm.ppf(0.80)
        print(f"  m={m} delta={delta}: {math.ceil((z * 0.25 / delta) ** 2)}")
    for delta in (0.05, 0.10):
        print(f"delta={delta}: exact-branch NI needs h+ <= value, by h- = 0..10 (-1: never)")
        for n in (40, 155, 400) if delta == 0.05 else (40, 100, 200):
            table = decision_table(n, delta)
            print(f"  n={n}:", [max([hp for hp in range(SWITCH) if table.get((hp, hm))], default=-1)
                                for hm in range(11)])
        print(f"delta={delta}: P(NI) with identical arms, alpha'=0.05 (rows: law; columns: n = {GRID})")
        tables = {n: decision_table(n, delta) for n in GRID}
        passing = [True] * len(GRID)
        for magnitude, r in REQUIRED + REPORTED:
            row = [p_ni(n, law(r, magnitude), delta, tables[n], rng, REPS) for n in GRID]
            tag = "required" if (magnitude, r) in REQUIRED else "reported"
            print(f"  {magnitude} r={r:.2f} {tag}: " + " ".join(f"{x:.2f}" for x in row))
            if tag == "required":
                passing = [a and x >= 0.80 for a, x in zip(passing, row)]
        n_sel = next((n for n, ok in zip(GRID, passing) if ok), None)
        print(f"  smallest n in the grid with P(NI) >= 0.80 under every required law: {n_sel}")
        print(f"  calibration at n={n_sel}:")
        alpha_boot = calibrate(n_sel, delta, tables[n_sel], rng)
        print(f"  calibrated alpha' = {alpha_boot}")
        if alpha_boot is not None:
            row = [p_ni(n_sel, law(r, m), delta, tables[n_sel], rng, REPS, alpha_boot) for m, r in REQUIRED]
            print(f"  n={n_sel}, alpha'={alpha_boot}: P(NI) under the required laws " + " ".join(f"{x:.2f}" for x in row))
            worse = shifted_law(0.20, "M1", 0.02)
            print(f"  n={n_sel}, alpha'={alpha_boot}: P(NI) when B is truly worse by 0.02 (M1, r=0.20): "
                  f"{p_ni(n_sel, worse, delta, tables[n_sel], rng, REPS, alpha_boot):.2f}")
        worse = shifted_law(0.20, "M1", 0.02)
        print(f"  n=155, alpha'=0.05: P(NI) when B is truly worse by 0.02 (M1, r=0.20): "
              f"{p_ni(155, worse, delta, tables[155], rng, REPS):.2f}")


if __name__ == "__main__":
    main()
```

Output:

```text
check: multinomial shortcut vs scipy.stats.bootstrap (upper 95% bound of mean h)
  fixture-a: scipy 0.0355  shortcut 0.0355
  fixture-b: scipy 0.0871  shortcut 0.0871
normal-approximation n of the earlier draft (sigma 0.25), for comparison only
  m=1 delta=0.05: 155
  m=1 delta=0.1: 39
  m=2 delta=0.05: 197
  m=2 delta=0.1: 50
delta=0.05: exact-branch NI needs h+ <= value, by h- = 0..10 (-1: never)
  n=40: [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1]
  n=155: [2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3]
  n=400: [11, 11, 11, 11, 11, 11, 11, 11, 11, 10, 9]
delta=0.05: P(NI) with identical arms, alpha'=0.05 (rows: law; columns: n = (100, 155, 200, 250, 300, 400, 500))
  M1 r=0.05 required: 0.09 0.26 0.43 0.52 0.69 0.96 1.00
  M1 r=0.10 required: 0.03 0.15 0.56 0.88 0.99 1.00 1.00
  M1 r=0.20 required: 0.37 0.85 0.92 0.96 0.99 1.00 1.00
  M1 r=0.30 required: 0.59 0.71 0.83 0.90 0.93 0.98 0.99
  M1 r=0.02 reported: 0.36 0.80 0.89 0.96 0.98 1.00 1.00
  M2 r=0.05 reported: 0.09 0.25 0.40 0.53 0.70 0.97 1.00
  M2 r=0.10 reported: 0.02 0.10 0.36 0.73 0.84 0.92 0.96
  M2 r=0.20 reported: 0.15 0.41 0.49 0.55 0.57 0.73 0.79
  M2 r=0.30 reported: 0.22 0.29 0.34 0.44 0.47 0.56 0.62
  smallest n in the grid with P(NI) >= 0.80 under every required law: 400
  calibration at n=400:
    alpha'=0.05: worst false NI at the margin, CP95 upper 0.0678
    alpha'=0.045: worst false NI at the margin, CP95 upper 0.0559
    alpha'=0.04: worst false NI at the margin, CP95 upper 0.0551
    alpha'=0.035: worst false NI at the margin, CP95 upper 0.0548
  calibrated alpha' = 0.035
  n=400, alpha'=0.035: P(NI) under the required laws 0.96 1.00 0.99 0.96
  n=400, alpha'=0.035: P(NI) when B is truly worse by 0.02 (M1, r=0.20): 0.81
  n=155, alpha'=0.05: P(NI) when B is truly worse by 0.02 (M1, r=0.20): 0.52
delta=0.1: exact-branch NI needs h+ <= value, by h- = 0..10 (-1: never)
  n=40: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]
  n=100: [4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4]
  n=200: [11, 11, 11, 11, 11, 11, 12, 12, 11, 10, 9]
delta=0.1: P(NI) with identical arms, alpha'=0.05 (rows: law; columns: n = (100, 155, 200, 250, 300, 400, 500))
  M1 r=0.05 required: 0.89 0.99 0.99 1.00 1.00 1.00 1.00
  M1 r=0.10 required: 0.43 0.76 0.98 1.00 1.00 1.00 1.00
  M1 r=0.20 required: 0.60 0.99 1.00 1.00 1.00 1.00 1.00
  M1 r=0.30 required: 0.96 1.00 1.00 1.00 1.00 1.00 1.00
  M1 r=0.02 reported: 0.99 1.00 1.00 1.00 1.00 1.00 1.00
  M2 r=0.05 reported: 0.89 0.98 0.99 1.00 1.00 1.00 1.00
  M2 r=0.10 reported: 0.44 0.75 0.97 1.00 1.00 1.00 1.00
  M2 r=0.20 reported: 0.39 0.85 0.93 0.96 0.98 1.00 1.00
  M2 r=0.30 reported: 0.52 0.72 0.81 0.88 0.94 0.98 0.99
  smallest n in the grid with P(NI) >= 0.80 under every required law: 200
  calibration at n=200:
    alpha'=0.05: worst false NI at the margin, CP95 upper 0.0668
    alpha'=0.045: worst false NI at the margin, CP95 upper 0.0562
    alpha'=0.04: worst false NI at the margin, CP95 upper 0.0495
  calibrated alpha' = 0.04
  n=200, alpha'=0.04: P(NI) under the required laws 1.00 0.98 1.00 1.00
  n=200, alpha'=0.04: P(NI) when B is truly worse by 0.02 (M1, r=0.20): 1.00
  n=155, alpha'=0.05: P(NI) when B is truly worse by 0.02 (M1, r=0.20): 0.99
```
