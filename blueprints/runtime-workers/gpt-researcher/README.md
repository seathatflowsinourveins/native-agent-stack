# GPT Researcher runtime worker — round 3

This recipe retains **assafelovic/gpt-researcher v3.7.0**, source commit
`0957c301ed06c2a5857b834358c7227c739041d4`, package metadata `0.16.0`.
The source archive and three dependency locks remain unchanged. The CLI,
retry function and URL guard now also have individual hashes in [pins.json](pins.json).
The older PyPI wheel is not substituted for this source revision.

## Native qualification, 2026-09-30

An isolated native installation completed for the runtime, MCP proxy and
DRB-II grader. Native compatibility checks passed for 198, 68 and 8
distributions respectively. Six selected unchanged upstream test files returned
**24 passed, two warnings**, exit 0. The exact source/test hashes and returned
output are in the [qualification receipt](../../../evidence/artifacts/runtime-roster-20260930/gpt-researcher-native.json).
No model report, citation-quality score or whole-task usage was measured.
The older round-3 construction records below retain their historical scope.

The selected workflow entry point is the upstream CLI. [cli_runner.py](cli_runner.py)
loads its unchanged parser and calls its unchanged `main` inside the existing
HTTPX transport context. This small launcher preserves correlation capture,
request guards and per-generation headers; it does not replace the native research
pipeline. The CLI still uses DuckDuckGo and keyword context filtering without MCP
configuration. The separately selected E2E task uses the upstream Python SDK with
scoped MCP retrievers and the unchanged DRB-II grader.
Sources: [GPTR@0957c301 cli.py:306–362](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/cli.py#L306-L362),
[config/config.py:158–166](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/gpt_researcher/config/config.py#L158-L166).

## Installation

The coordinator runs `bash install.sh` on the host. The earlier round-3 repair
performed no host installs, model calls, gateway requests or container starts;
the later native qualification is recorded above. The native
prefix is `$HOME/.local/share/codex-ecosystem/tools/gpt-researcher-3.7.0`; the lock
target is Linux x86_64 and CPython 3.12. Worker/proxy/build requirements use hashed
locks, and source builds use the already locked build requirements with
`--no-build-isolation`. The installed source and installation-pins receipt must
match this recipe before dispatch.

The grader uses its own upstream lock and separate venv:

```sh
uv sync --locked --no-build --no-install-project --project "$grader_source" --python "$python_bin"
```

`--no-build` refuses source builds; `--no-install-project` avoids building the
benchmark package, whose scripts need only its locked dependencies. No upstream
grading source, container configuration or resource limit is changed. Sources:
[DRB-II@b38f360 pyproject.toml:1–12](https://github.com/imlrz/DeepResearch-Bench-II/blob/b38f360603db9531b102aef8c166cedb8509b6f6/pyproject.toml#L1-L12),
[its native installation](https://github.com/imlrz/DeepResearch-Bench-II/blob/b38f360603db9531b102aef8c166cedb8509b6f6/README.md#L287-L303),
[uv sync options](https://docs.astral.sh/uv/reference/cli/#uv-sync).
The repair checked installed `uv 0.12.17` and its `sync --help`; native install
acceptance on another host remains a separate check.

## Workflow dispatch

Run these from the checkout root through the workflow child's Bash tool. Choose a
unique, stable run ID (letters, digits, underscores and hyphens; maximum 64 characters).
`query_file` is an existing UTF-8 file containing the research question.

```sh
rtk bash blueprints/runtime-workers/gpt-researcher/dispatch.sh start \
  --run-id gptr-control-001 --arm control --query-file "$query_file"
rtk bash blueprints/runtime-workers/gpt-researcher/dispatch.sh wait \
  --run-id gptr-control-001 --timeout 30
rtk bash blueprints/runtime-workers/gpt-researcher/dispatch.sh result \
  --run-id gptr-control-001
```

`start` writes `status.json` before launch, detaches a bounded supervisor and
returns immediately. The child need not keep a foreground Bash tool call open
for research. `wait` accepts at most 60 seconds and returns 76 while pending;
repeat it until complete. `result` returns the current state or the final result.
All valid attempts use the same JSON envelope, including setup failure, busy,
native failure, timeout and pass. The deterministic paths printed relative to
`$HOME/.local/state/native-agent-stack/runtime-workers/gpt-researcher` are:

```text
runs/gptr-control-001/status.json
runs/gptr-control-001/dispatch-result.json
runs/gptr-control-001/receipt.json
```

Reusing a run ID is a setup error and never overwrites the existing attempt.
The same shared lock serializes CLI and E2E across both arms. A busy attempt has
its own result and receipt; retry with a new ID. The native timeout process also
inherits the lock descriptor, so a lost supervisor does not immediately admit
another worker. Host cancellation and orphan cleanup still need native observation.
The subprocess mechanism follows
[CPython@v3.12.12 subprocess.rst:565–568,595–599](https://github.com/python/cpython/blob/v3.12.12/Doc/library/subprocess.rst#L565-L599)
and [fcntl locking](https://github.com/python/cpython/blob/v3.12.12/Doc/library/fcntl.rst).

| Final code | Exit class | Meaning |
| --- | --- | --- |
| 0 | `pass` | Native execution/output and required accounting evidence completed; no research-quality claim |
| 10 | `negative_verdict` | Native process returned a failure; this is an execution verdict, not a threshold on DRB-II scores |
| 20 | `setup_failure` | Invalid inputs, missing/stale installation or unavailable setup |
| 30 | `incomplete_evidence` | Timeout, interrupted supervisor, malformed/missing output or incomplete accounting |
| 75 | `busy` | Another recipe attempt holds the shared lock |
| 76 | `running` | Wait/result is pending; start returns 0 only to acknowledge launch |

For benchmark dispatch, use the same sequence with `--mode e2e` and no query file:

```sh
rtk bash blueprints/runtime-workers/gpt-researcher/dispatch.sh start \
  --mode e2e --run-id gptr-e2e-control-001 --arm control
rtk bash blueprints/runtime-workers/gpt-researcher/dispatch.sh wait \
  --run-id gptr-e2e-control-001 --timeout 30
rtk bash blueprints/runtime-workers/gpt-researcher/dispatch.sh result \
  --run-id gptr-e2e-control-001
```

The foreground compatibility entry point is
`GPTR_RUN_ID=gptr-e2e-control-001 RUNTIME_WORKER_ARM=control bash blueprints/runtime-workers/gpt-researcher/run-e2e.sh`.
It uses the same supervisor and envelope. CLI research has a 1800-second deadline;
E2E research/grading each have 1800 seconds within a 3700-second outer deadline,
plus a 20-second kill grace. These are worker invocation deadlines, not changes
to an upstream grading container.

For invocation accounting, join the child's native `child-usage.mjs` record to
Claude `claude_code.tool_result` OTel events. Count Bash `start` or foreground
`run-e2e.sh` launches, deduplicated by `tool_use_id`; wait/result calls are polls.
`OTEL_LOG_TOOL_DETAILS=1` must expose the wrapper path in `full_command`.
Source: [Claude Code tool-result events](https://code.claude.com/docs/en/monitoring-usage).
On the worker side, retain `native.log`, `native-stdout.log` and `native-stderr.log`.
CLI completions require both the native `Report written to` log line and its
matching native front-matter report. The supervisor's `invocations.jsonl` records
one launch and one native exit, including failures; these are explicitly local
lifecycle records, not invented framework events. Reconcile launches against native
logs/completions, and retain failed/incomplete attempts. OTel rewrite behavior and
child-usage reconciliation remain host checks.

## Arms

`RUNTIME_WORKER_ARM=control|engines-on` defaults to control. `--arm` overrides it
for dispatch. Model/base overrides must match the selected arm; mismatches fail
before any model call. This host/stdio recipe accepts loopback URLs only; it does
not introduce container gateway addresses.

| Variable | Control | Engines on |
| --- | --- | --- |
| `RUNTIME_WORKER_ARM` | `control` | `engines-on` |
| `GPTR_BASE_URL` | `http://127.0.0.1:20128/v1` | `http://127.0.0.1:20129/v1` |
| `GPTR_MODEL` | `cx/gpt-6-astra-max` | `sharedgw/gpt-6-astra-max` |
| `GPTR_JUDGE_BASE_URL` | `http://127.0.0.1:20128/v1` | `http://127.0.0.1:20128/v1` |
| `GPTR_JUDGE_MODEL` | `cx/gpt-6-astra-max` | `cx/gpt-6-astra-max` |

Selecting the arm alone supplies these defaults. The sharedgw model has exactly
one slash; `sharedgw/cx/...` is rejected. Existing `cx/gpt-6-*` control variants
remain accepted, but a non-max alias must not be presented as max-effort A/B
acceptance. Both defaults explicitly request max effort. The worker sends
`x-omniroute-compression: allow-lossy` only on engines-on; the judge always uses
control and an independent random session. Receipts retain arm, both base URLs,
models and header **names**, with no session/correlation/header values.

Before engines-on accounting, the coordinator must verify that
`~/.local/share/omniroute-fw/storage.sqlite` belongs to the 20129 instance, then
set `GPTR_ENGINES_DB_VERIFIED=1`. Without that attestation its database is not read
and evidence remains incomplete. The flag changes observation readiness, not
model routing. Example after that host verification:

```sh
GPTR_ENGINES_DB_VERIFIED=1 rtk bash blueprints/runtime-workers/gpt-researcher/dispatch.sh start \
  --run-id gptr-engines-001 --arm engines-on --query-file "$query_file"
```

All native LLM roles receive the same selected route via JSON configuration.
Worker `max_tokens=12000`, timeout 180 seconds, keyword filtering and the frozen
research bounds are identical across arms. The transport rejects non-GPT-6
routes, unexpected model endpoints, temperature <=0.1, `json_object` and open
objects in strict schemas. Native free-text planning still uses upstream JSON
repair; no constrained planner is claimed.

SDK retries stay disabled. Passing `websocket=None` restores GPT Researcher's
native **ten-attempt** retry loop for streamed reports, with native logging and
a fresh key per outer attempt. One transient error no longer necessarily ends
the final report stage. Replay deduplication across outer attempts is not claimed.
Sources: [GPTR@0957c301 utils/llm.py:99–143](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/gpt_researcher/utils/llm.py#L99-L143),
[generic/base.py:146–158](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/gpt_researcher/llm_provider/generic/base.py#L146-L158),
[LangChain OpenAI@1.6.6 HTTP clients](https://github.com/langchain-ai/langchain/blob/langchain-openai%3D%3D1.6.6/libs/partners/openai/langchain_openai/chat_models/base.py#L1022-L1034),
[HTTPX@0.28.1 hooks](https://github.com/encode/httpx/blob/0.28.1/docs/advanced/event-hooks.md#L5-L7).

## Usage accounting

Worker and judge phases have separate persisted start/end timestamps and separate
private request/response correlation logs. HTTPX hooks capture response headers
before streaming bodies; the judge captures `requests.Response.headers` through
its module-local transport adapter. IDs never enter public receipts. Complete
capture selects matching correlation IDs; missing headers/transport responses
fall back to the phase's time window, model and path, with an explicit concurrent
caller limitation. Missing captured IDs in the database leave evidence incomplete.

The worker reads exactly its entry gateway: 20128 control or 20129 engines-on.
The judge reads 20128 in its separate phase. An engines-on worker's forwarded
20128 rows are never added. SQLite opens `?mode=ro` and selects only timestamp,
path, status, model, tokens_in, tokens_cache_read, tokens_reasoning and
correlation_id, plus the two effort fields explicitly required by round-3 section 3.
No prompt, response body, auth table, session tag or unrelated schema is read.
Unrelated paths/models are excluded, counters remain raw and unknown counters
remain unknown. Source: [CPython@v3.12.12 sqlite3.rst:2420–2425](https://github.com/python/cpython/blob/v3.12.12/Doc/library/sqlite3.rst#L2420-L2425).

Positive reasoning-token rows retain their logged requested/upstream effort;
non-max observations prevent evidence completion. Zero returned reasoning and
unknown usage have separate counts. Null effort does **not** mean effort was
missing: OmniRoute fills those columns only for encrypted reasoning.
Source: [OmniRoute@a58000c callLogs.ts:645–654](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/usage/callLogs.ts#L645-L654).
The installed gateway build and forwarding behavior still require host observation.

Engines-on compression is a separate before/after delta of 20129
`GET /api/analytics/compression?since=all`, using only cumulative `totalRequests`
and `totalTokensSaved`. Both snapshots and the delta are retained; counter resets
or refused observations are not zero savings. Aggregate savings may include other
callers. They are never added to provider usage.
Sources: [OmniRoute@a58000c API:13–25](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/app/api/analytics/compression/route.ts#L13-L25),
[compressionAnalytics.ts:52–55](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/src/lib/db/compressionAnalytics.ts#L52-L55).

## Native grading

E2E freezes DRB-II task idx 12 and checks the exact dataset row and prompt hashes.
The original report is exported unchanged. The grader remains
`imlrz/DeepResearch-Bench-II@b38f360603db9531b102aef8c166cedb8509b6f6`.
It runs unchanged `run_evaluation.py` and `aggregate_scores.py` with:

```text
OPENAI_REASONING_EFFORT=max
OPENAI_MAX_OUTPUT_TOKENS=32768
OPENAI_TIMEOUT=600
--max_workers 1 --max_retries 5 --chunk_size 50
```

32768, 50 and 5 follow the [pinned README:271–280](https://github.com/imlrz/DeepResearch-Bench-II/blob/b38f360603db9531b102aef8c166cedb8509b6f6/README.md#L271-L280).
Explicit deviations: GPT-6/max replaces GPT-5.5/medium per this arm contract;
one worker serializes grading; `--max_paper_chars` equals the report length to
preserve the full exported report; a closed JSON schema implements the unchanged
rubric-result schema. The upstream code's retry fallback is actually 10;
explicit 5 selects its documented configuration
([run_evaluation.py:26–29](https://github.com/imlrz/DeepResearch-Bench-II/blob/b38f360603db9531b102aef8c166cedb8509b6f6/run_evaluation.py#L26-L29)).
These settings are identical across both arms.

The adapter rechecks task identity, complete rubric rows, CSV layout/cells/hashes
and report hashes. All-zero/all-blocked scores stay native scores; no binary
quality threshold is invented. `execution_complete` means report delivery and
grading completed; `evidence_complete` separately requires gateway/accounting
observations. CLI dispatch is ungraded. Sources:
[DRB-II client:85–109](https://github.com/imlrz/DeepResearch-Bench-II/blob/b38f360603db9531b102aef8c166cedb8509b6f6/gpt_client.py#L85-L109),
[aggregation:249–289](https://github.com/imlrz/DeepResearch-Bench-II/blob/b38f360603db9531b102aef8c166cedb8509b6f6/aggregate_scores.py#L249-L289).

## Security posture

The model has no shell/Python execution tool. Context-mode exposes only
`ctx_search` and `ctx_index`; indexing accepts bounded literal `content` and
an optional source label. File/directory paths, execution tools and
`ctx_fetch_and_index` are denied at both discovery and call time. Disabling fetch
also removes its redirect/DNS bypass surface rather than adding an incomplete
URL filter to that second client. Each attempt has a separate scratch cwd,
context store and HOME; the checkout is not the MCP project directory.
Sources: [context-mode@v1.0.169 src/server.ts:2237–2309](https://github.com/mksglu/context-mode/blob/v1.0.169/src/server.ts#L2237-L2309),
[FastMCP@v4.0.10 middleware:751–768](https://github.com/PrefectHQ/fastmcp/blob/v4.0.10/docs/servers/middleware.mdx#L751-L768),
[proxy:260–275](https://github.com/PrefectHQ/fastmcp/blob/v4.0.10/docs/servers/providers/proxy.mdx#L260-L275).

Native GPTR scraping retains its public HTTP(S) URL checks and explicitly sets
`ALLOW_PRIVATE_URLS=false`. The pinned guard denies ordinary loopback/private
addresses and local-file URLs. **Residual risk:** its own source documents a DNS
rebinding window; the BeautifulSoup client follows redirects. This is not an OS
egress sandbox. No model-controlled container shell exists in this recipe, and
no container runtime is introduced in this repair, so container per-port controls,
capability dropping, no-new-privileges and non-root container settings are not
claimed. A future container migration must implement and independently qualify
those controls before enabling any model shell. Sources:
[GPTR@0957c301 url_security.py:8–25,63–122](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/gpt_researcher/utils/url_security.py#L8-L25),
[scraper.py:195–212](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/gpt_researcher/scraper/scraper.py#L195-L212),
[BeautifulSoup fetching:60–73](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/gpt_researcher/scraper/beautiful_soup/beautiful_soup.py#L60-L73).

QMD remains scoped to `foundation-docs`, `foundation-adoption`,
`us-equities-foundation` and `us-equities-catalog`, lexical-only with bounded
queries and explicit `qmd://collection/path` reads. Memory tools remain read-only
and get an explicit project/workspace. Resources and prompts are refused.
Socraticode and Headroom stay inactive. No MCP server installation is performed.
E2E requires a private 0600 host file outside the checkout using
[host.template.json](host.template.json); `WORKER_CWD` has been removed.
`GPTR_HOST_FILE` selects that file. `GPTR_PREFIX` and `GPTR_STATE_ROOT` optionally
select an operator-owned installation/state root; they are not model arguments.

Receipts are written by the outside supervisor, which rechecks native output,
grader rows and exported reports independently. The model has no tool for writing
those files. Raw reports, logs, correlation IDs and configuration remain private
under the attempt; only sanitized metadata and hashes enter receipts. Worker and
grader environments clear inherited provider/proxy configuration and disable dotenv.
No credential store is read or copied.

This SDK/stdio recipe creates no listener, container, volume or network. Any future
worker listener must use `127.0.0.1:3730-3799`; any future container resource must
use `rw-gpt-researcher-` and
`com.native-agent-stack.owner=gpt6-omniroute-framework-integration`. No Docker
cleanup commands are needed for this recipe.

## Skills and acceptance boundary

A native SKILL.md loader was not found in the reviewed v3.7.0 sources/release
record; no installed runtime capability absence claim is made. The official
outer-agent skill is a dispatch pointer. Startup/receipts retain empty skill
inventories and never fabricate activations. If a future qualified runtime adds
loading, the coordinator's intended installer remains **pending the skills-program PR**:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/adoption/install_skills.py \
  --manifest blueprints/runtime-workers/skills/manifest.json \
  --project-dir "$worker_workspace" --agent universal
```

The repair used the installed search-first, find-skills, tdd and
verification-before-completion guidance, with no delegation or installation.
[round3-verification.json](round3-verification.json) retains findings, actual
commands/outputs, source references and fail-first controls. These are local
integration checks and synthetic controls, not upstream E2E or provider acceptance.
Round-1/2 records remain historical.

Host work still required: native installation and `run-upstream-tests.sh`; actual
CLI and E2E in both arms; 20129 database identity; response correlations and delayed
call-log persistence; one injected transient report 5xx; grader empty/JSON-warning
inspection and per-batch reasoning/output budgets; native MCP isolation/discovery;
OTel and child-usage reconciliation; deadline/cancellation/orphan behavior. Inspect
worker report truncation under its 12000-token cap. The documented DNS/redirect
residual must be included in any host security acceptance. No measured savings or
quality improvement is claimed by this repair.
