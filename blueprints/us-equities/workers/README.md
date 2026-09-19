# Native Astra research workers

The official Python Codex SDK was installed and used with the existing native
Codex 0.155.1 binary. Native sign-in completed; the first allowance check was
blocked, and the post-login check allowed the research task. The actual task
completed in **58,410 ms** with configured model `gpt-6-astra`, provider `openai`,
and Context Mode tool calls. See [the sanitized receipt](receipt.json).

## Reproduce with native SDK commands

Set `SDK_ENV`, `STACK_REPO`, `NATIVE_CODEX_HOME`, `NATIVE_CODEX_BIN`,
`RESEARCH_WORKSPACE`, `PROMPT_FILE` and `PRIVATE_RUN_DIR` to explicit paths.
Use a private run directory outside any published repository. Existing files
are not overwritten. This requirements file pins the top-level versions;
it does not claim a hash-locked transitive environment.

```sh
uv venv --python 3.13 "$SDK_ENV"
uv pip install --python "$SDK_ENV/bin/python" \
  -r "$STACK_REPO/blueprints/us-equities/workers/requirements.txt"

# Native browser sign-in only when needed; the client owns its credentials.
CODEX_HOME="$NATIVE_CODEX_HOME" "$NATIVE_CODEX_BIN" login

timeout --signal=TERM --kill-after=10s 60s "$SDK_ENV/bin/python" \
  "$STACK_REPO/blueprints/us-equities/workers/native_worker.py" inspect \
  --codex-bin "$NATIVE_CODEX_BIN" --codex-home "$NATIVE_CODEX_HOME" \
  --workspace "$RESEARCH_WORKSPACE" --receipt "$PRIVATE_RUN_DIR/discovery.json"

timeout --signal=TERM --kill-after=10s 240s "$SDK_ENV/bin/python" \
  "$STACK_REPO/blueprints/us-equities/workers/native_worker.py" run \
  --codex-bin "$NATIVE_CODEX_BIN" --codex-home "$NATIVE_CODEX_HOME" \
  --workspace "$RESEARCH_WORKSPACE" --prompt "$PROMPT_FILE" \
  --receipt "$PRIVATE_RUN_DIR/research.json" --turn-deadline-seconds 180
```

`native_worker.py` is a small integration example around upstream
`CodexClient.initialize`, `model_list`, `account/rateLimits/read`,
`AsyncCodex.thread_start`, `thread.read`, `thread.turn` and `turn.run`.
It preserves native authentication, explicitly selects Astra, requires reported
ordinary allowance, checks the configured model/provider before submission,
uses a read-only sandbox, denies escalation and adds [the shared policy](policy.md)
as developer instructions. It does not build another agent framework.

The turn deadline starts after the upstream turn is accepted. Startup and
readiness RPCs can block independently; the outer native process timeout limits
local lifetime. Neither deadline is a provider spending cap or proof of remote
cancellation. Native interrupt is requested on a turn deadline. This example is
not a persistent queue, retry service or unattended order executor.

The SDK overlays `env` onto the parent environment. **Launch from a dedicated
research environment with no broker/service secrets**, and separately restrict
its tools and filesystem identity. Read-only shell/filesystem permissions do
not make inherited MCP servers or lifecycle hooks read-only. Review those native
registrations before dispatch. A policy prompt is not an authorization boundary.
The recorded task had no broker keys or broker tools supplied.

## Token practice and exact observations

The policy applies to each worker created by this example. Existing native
plugins/hooks remain configured in the selected native home. Other SDKs, other
accounts, unrelated projects and already-running Desktop sessions do not gain
these tools merely because the packages are installed.

The observed worker used `ctx_execute` three times, `ctx_stats` once and attempted
`ctx_execute_file` once. The file operation was rejected by the server's scoped
project root; extraction then completed through `ctx_execute`. Review the scope
when deliberately adopting a new project; do not disable the restriction globally.
No memory or code-RAG query was made against the unadopted publication checkout.

Two bounded follow-ups investigated that file-scope failure. A parent environment
override still failed because the plugin transport did not inherit it. The
optional `--context-mode-start /absolute/path/to/installed/start.mjs` uses native
Codex `mcp_servers.context-mode` process overrides to set the workspace directly
on the MCP server. Native registration/discovery accepted that configuration,
but the file call then required approval as a new MCP registration and the
worker's `deny_all` policy correctly blocked it. **The override is not a completed
file-tool acceptance.** It needs normal native MCP approval before use. No trust
rule, path containment or approval requirement was bypassed, and no further
model trial was launched. Default trusted `ctx_execute` remains the demonstrated
working path; do not treat it as permission to read an unrequested file.

| Native SDK aggregate counter | Observed tokens |
| --- | ---: |
| Input | 133,839 |
| Cached input, included in input | 119,424 |
| Input minus cached input | 14,415 |
| Cache-write input | 0 |
| Output | 1,472 |
| Reasoning output, included in output | 117 |
| Total input + output | 135,311 |

Cached-input share is **89.23%**. These are aggregate native turn counters across
the agent's requests, not the size of one prompt, a subscription bill or measured
net savings. At its early checkpoint Context Mode reported **0 estimated tokens
saved** and 9.5 KB entered context; later extraction calls were not in that
checkpoint. No successful compressor percentage is invented for this run.
The task's answer could not see provider usage, but the owning SDK returned it
after completion. Configured-model checks are not independent per-request
provider attestation; this example does not collect model-reroute notifications.

Both unsuccessful file checks also consumed native usage. The parent-env check
reported **34,228 input / 28,288 cached / 240 output**; the scoped-MCP check
reported **34,097 input / 28,288 cached / 215 output**. Across all three SDK turns:
**202,164 input, 176,000 cached input, 1,927 output, 204,091 total tokens**.
Cached-input share across all three is **87.06%**; no paired net-savings claim is
made. A completed assistant turn that reports a tool rejection is still a failed
extraction task. [The receipt](receipt.json) distinguishes those outcomes.
These totals cover those three SDK turns only, excluding the coordinator and
separate catalog-research agents; they are not a whole-task cost measurement.

## Local observation and native usage

The later [observability acceptance](../../../observability/README.md) ran two
additional native SDK tasks. They completed with **40,187 and 40,583 total
input-plus-output tokens**, or **80,770 combined**. These are separate from the
three earlier research/file-scope turns above. Their native receipts and
correlated logs remain the evidence anchors: the SDK's native turn histogram
was **not observed**, including after a bounded flush attempt. Missing telemetry
is not zero usage, and a completed task does not establish delivery of every
metric family. [Exact monitoring receipt](../../../observability/receipt.json).

The helper now assigns a fresh opaque telemetry instance identity for each
readiness/execution process, preserving the inherited native exporter settings.
It can also publish a small local observation after a turn through
`--observation-dir "$PRIVATE_OBSERVATION_DIR"` or the equivalent environment
variable. The directory must already exist and be private; choose it explicitly
and configure the native Collector file receiver to watch that directory:

```bash
install -d -m 700 "$PRIVATE_OBSERVATION_DIR"
export ECOSYSTEM_SDK_OBSERVATION_DIR="$PRIVATE_OBSERVATION_DIR"
# Subsequent native_worker.py run invocations use this optional observation sink.
```

The optional file is published atomically, mode `0600`, with a unique
`observation_id`, task status, configured model, duration, usage availability and
aggregate usage. It contains no prompt, response/items, raw errors, account
identity or native thread identifier. Unavailable usage remains JSON `null`.
Its identifier is a local ingestion/deduplication key, not a public session ID.
The detailed `--receipt` remains private and is a different artifact.

The helper change has offline validation. The monitoring acceptance imported
bounded summaries from the already-completed SDK receipts to exercise the
separate file-ingestion route; **it did not run new inference through the changed
helper**. Consult the monitoring receipt for that route's final delivery status.
Do not add imported observations, OTLP counters and native receipts together as
independent usage. The file route does not repair or prove the missing native
histogram, and there is no automatic model retry to obtain a metric.

These exporter/identity settings apply to fresh native children. They do not
hot-reload the current Desktop process, instrument every third-party SDK, or
change model/account/sandbox policy. No broker connection, external notification
or paid cloud service was introduced.

Receipts contain private native item records. Review and select fields before
publishing. Failed SDK turns can raise before returning previously observed
usage, so failure/timeout receipts say `usage: null` with an explicit status.
Do not sum successful-only receipts and call that total spend or treat unknown
usage as zero. Keep artifact reduction, Context Mode/RTK estimates, native cache
reuse and provider totals separate.

The [baseline text measurement](../../../docs/direct-results.md) remains a
separate reproducible 2,730 → 491 token artifact comparison. Stable instructions,
bounded retrieval, scoped memory, SQL aggregates and one useful worker per
independent task are the default practices; more MCP catalogs and frameworks
can increase startup and context cost.

Upstream: [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk),
[App Server](https://learn.chatgpt.com/docs/app-server),
[native source](https://github.com/openai/codex),
[prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching).
