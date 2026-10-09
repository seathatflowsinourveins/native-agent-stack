# Worker telemetry contract qualification through Harbor 0.24.0

This is an acceptance recipe, UNRUN. Harbor qualifies the contract. Codex
rust-v0.160.0 and OpenHands software-agent-sdk v1.50.1 produce the events; OTel
Collector Contrib v0.162.0 collects and routes them in its own slot. The existing
Harbor oracle/nop hello-user acceptance remains the runner READY gate.

The current Harbor owner and Scout ATIF companion use 0.24.0 at
`b53b8134e1241686dca7759af188f987ecc48e8b`. The pinned source still ships
the hello-user task, its oracle/nop integration test and the trajectory
validator unit test. The source-method references below retain the recipe's
original provenance; current executable checkout paths use v0.24.0.

The qualification needs a maintained, versioned Harbor task corpus with native
verifiers, its full source commit, and a public Harbor JSON job recipe with all
three agents: `codex`, `openhands-sdk`, and `deerflow`. Set
`HARBOR_TELEMETRY_TASKS`, `HARBOR_TELEMETRY_TASKS_REV`, and
`HARBOR_TELEMETRY_JOB_CONFIG` to those inputs, then run:

```bash
bash accept.sh --only harbor-containerized-agent-e2e-runner --stage after_sign_in
```

Use Harbor's documented job config format. The agents' `kwargs` must pin Codex
with `version: "0.160.0"`, OpenHands with the installed agent-runtime-worker version (currently `version: "1.50.1"`), and DeerFlow with
`repo_ref: "v2.1.0"`. The Codex `model_name` is `gpt-6.1-sol`; its native
`kwargs.config` must set `model_provider: "openai"` and
`model_reasoning_effort: "max"`. The clean OmniRoute 3.8.51 pin cannot supply
Sol/max. Supply the other agents' model names and container-reachable endpoints
through their own documented Harbor settings. Container access to the existing Collector is an operator input. The Codex leg authenticates only through OPENAI_API_KEY from the per-provider 0600 file outside worktrees in docs/secret-storage.md, injected by tools/credentials/credential_run.py and never placed in the public job config. A ChatGPT native sign-in alone leaves this leg needs_user. CODEX_AUTH_JSON_PATH and CODEX_FORCE_AUTH_JSON are refused when set, before Harbor can upload an auth store. Do not put secrets in
the public job recipe or copy native authentication stores.

The versioned tasks' verifiers must check these native events, including a valid
case and seeded violations for every condition:

- Unique concurrent worker/writer identity and parent/child correlation.
- Tool errors and their recovery; MCP calls and skill use.
- Nested workers, cancellation, restart and completion across native streams.
- Codex rollout JSONL, SDK JSONL and app-server notifications, alongside
  OpenHands SDK exports and the independently observed Collector output.

For seeded violations, reward `1` means the verifier detected the expected
violation; it does not mean the worker succeeded at its task. Keep verification
correctness separate from task success. The corpus must retain the native
exports and Collector observation as Harbor task artifacts, and its verifiers
must fail on absent evidence. No such corpus is supplied in this bounded job:
that input is `needs_user`, and the recipe makes no telemetry qualification
claim before it is supplied and executed.

Harbor's native runner retains job/trial configs, task checksums, verifier
results and adapter artifacts under a fresh private state directory. The
recipe requires every task's three-agent matrix, pinned observed runtime
versions, reward `1` and no trial exception, then validates every adapter's
`agent/trajectory.json` with the upstream ATIF validator. Those result checks
are integration checks parameterized from the upstream hello-user test; the
unchanged ATIF unit tests and validator are upstream acceptance.

ATIF validation alone cannot establish this contract. ATIF-v1.7 can embed
subagent trajectories, but Harbor's Codex converter reads rollout events; the
SDK stream and app-server notifications need explicit native verifier checks.
No collection owner or producer is replaced, and the recipe enables no trace
export by itself. Unknown usage remains unknown.

Sources:

- `harbor-framework/harbor@1e5c5c6db929a10a140d05e606882c671ae20729:docs-mintlify/core-concepts/jobs/configs.mdx:6`.
- `harbor-framework/harbor@1e5c5c6db929a10a140d05e606882c671ae20729:src/harbor/agents/installed/base.py:560`.
- `harbor-framework/harbor@1e5c5c6db929a10a140d05e606882c671ae20729:src/harbor/agents/installed/codex.py:328`.
- `harbor-framework/harbor@1e5c5c6db929a10a140d05e606882c671ae20729:src/harbor/agents/installed/openhands_sdk.py:150`.
- `harbor-framework/harbor@1e5c5c6db929a10a140d05e606882c671ae20729:src/harbor/agents/installed/deerflow.py:181`.
- `harbor-framework/harbor@1e5c5c6db929a10a140d05e606882c671ae20729:docs-mintlify/core-concepts/agents/atif.mdx:47` and `:121`.
- `harbor-framework/harbor@1e5c5c6db929a10a140d05e606882c671ae20729:tests/integration/test_hello_user_e2e.py:25`.
- `harbor-framework/harbor@1e5c5c6db929a10a140d05e606882c671ae20729:docs-mintlify/core-concepts/tasks/verifier.mdx:1`.

The OpenHands adapter and every retained result must equal the version read from the installed producer package metadata. A mismatch exits 78 with needs_user. The agent-runtime-worker owner retains its v1.50.1 pin and owns any separately qualified move to v1.51.0; this repair changes no producer pin.
