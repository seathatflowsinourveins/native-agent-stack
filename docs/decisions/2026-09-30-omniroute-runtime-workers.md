# OmniRoute runtime workers called from native Claude

Use the retained official Codex SDK for the primary foundation coding worker:
`cx/gpt-6.1-sol-max` through the selected OmniRoute Responses lane, with native
Max effort. Native interactive Claude and Codex keep their existing accounts and
routes. The [project Claude skill](../../.claude/skills/omniroute-runtime-worker/SKILL.md)
dispatches the [bounded worker](../../examples/omniroute-codex-sdk/README.md)
through Claude's native Bash tool, with a separate worktree and private worker
home. Configuration remains scoped to the child process. The existing frozen
three-arm SDK comparison remains unresolved; this is functional qualification of
the retained implementation for one application role.

## Sources and selection

The maintained [Codex SDK at rust-v0.159.2](https://github.com/openai/codex/tree/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python)
supplies the native start/resume/turn/interrupt/close lifecycle. Published SDK and
bundled CLI versions are 0.159.2, pinned by native uv script locks. Sol model
metadata survives the single gateway namespace through
[native model matching](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/models-manager/src/manager.rs#L763).
The [Claude project Skills format](https://code.claude.com/docs/en/skills) supplies
the coordinator's on-demand entry point; it adds no outer orchestration runtime.

The alternative [Claude Agent SDK v0.2.162](https://github.com/anthropics/claude-agent-sdk-python/tree/f2204bb956bab02907aaf3cb88eb9dead28eaa35)
is implemented in [a separate trial](../../examples/claude-runtime-sdk/README.md),
with explicit native prompt preset, tools, settings, skills and lifecycle. Its
advertised `dva/claude-opus-5-max` route uses OmniRoute's translated Devin bridge.
The [running-base serializer](https://github.com/diegosouzapw/OmniRoute/blob/2f42a9ac19d1a247ec9ce5473b790843724b3061/open-sse/executors/devin-agentic/serializer.ts),
[tool parser](https://github.com/diegosouzapw/OmniRoute/blob/2f42a9ac19d1a247ec9ce5473b790843724b3061/open-sse/executors/devin-agentic/toolParser.ts)
and [usage estimator](https://github.com/diegosouzapw/OmniRoute/blob/2f42a9ac19d1a247ec9ce5473b790843724b3061/open-sse/executors/devin-agentic/types.ts)
establish translation, finite tool-result truncation, restricted envelopes and
estimated usage. Advertised model labels do not attest backend identity. The
[official Claude gateway contract](https://code.claude.com/docs/en/llm-gateway)
requires Claude models; it does not qualify this translation or non-Claude model
substitution inside the Claude harness.

The running OmniRoute 3.8.51 base and its owned patches differ from the published
3.8.51 tag. Port 20128's existing compression-off lane was preserved. No gateway
engine, global authentication setting or interactive model route was changed.

## Actual acceptance and limits

The [sanitized receipt](../../evidence/receipts/omniroute-runtime-workers-20260930.json)
retains selected actual native returns, failed attempts and independent
observations. A Sol/Max worker read two task-relevant skill bodies, repaired only
`math.js` in the upstream OmniRoute arithmetic fixture, and passed its unchanged
test. Independent execution observed the defect before the task and success
after it. Native resume retained the same thread and passed. An invalid resume
failed before inference; a three-second deadline requested native interruption;
a fresh thread then passed. The cancellation result is in its private log, not
an original-result JSON file. Remote termination remains unverified.

The byte-exact executed sources are also retained in this branch's public
[Sol source commit](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9edd76e9f9f817e818b59b7b5cfd16e329317ad0/examples/omniroute-codex-sdk/worker.py)
and [Claude source commit](https://github.com/seathatflowsinourveins/native-agent-stack/blob/38e4ec6f69d23c663f60c44c311217f7239e448d/examples/claude-runtime-sdk/worker.py).
Later formatting commits preserve the same AST; the receipt names original
worker commits and full executed/final SHA-256 values.

The gateway observer confirms Max effort and native ResponsesLite tool carriage
under `input[].type=additional_tools`. The first authored oracle incorrectly
expected top-level `tools`; original tagged source corrected that failed oracle.
Resume preserved the native cache key and stable tool prefix. Six authored
SDK/native-CLI transport tests and five observer tests passed. Their local
synthetic evidence remains distinct from actual provider execution. The prior
unchanged Codex source suite retains one formatter-driver failure; no complete
Codex upstream-suite passing claim is made. Repeated calls in one Python process
also expose native SDK pipe ResourceWarnings. Standalone child exit is checked;
a long-running in-process pool is unqualified.

The supported pinned skill installer installed 136 catalog skills in the owned
project, and its independent check reported 136 OK. Native task execution read
`using-superpowers` plus the additional upstream `bridge-proof` fixture skill.
The latter was an explicit Claude-path read, not Codex implicit discovery. Keep
metadata discovery, actual body loading and task outcomes separate. Fifteen role
gaps, three capability gaps, the remaining skills and optional MCP integrations
retain their existing qualification limits. Follow the existing native skill
lifecycle; do not preload every body or start optional services by default.

Both Claude gateway attempts timed out with zero tool calls. The observed
Messages requests returned HTTP 500. One bounded Sol repair adopted the
[native launcher child environment](https://github.com/diegosouzapw/OmniRoute/blob/2f42a9ac19d1a247ec9ce5473b790843724b3061/bin/cli/commands/launch.mjs),
including keyless gateway authentication and discovery. The repaired attempt
still failed, so the bridge remains unqualified. This does not establish the
cause of the first timeout. Separately, the unchanged Claude SDK suite passed
1,587 tests with six skips; 24 authored local checks passed. Neither result
overrides failed provider acceptance.

## Judgment, cooperation and token accounting

Consequential bridge architecture and failure after one bounded Sol repair
triggered an Astra/Max original-source and owned-artifact audit. Its acceptance
was limited to the demonstrated Codex SDK lifecycle; it rejected promotion of
the failed Claude bridge. Explicit task models remain explicit. Astra is an
explicit judgment stage, rather than a silent retry or default for every worker.

Native Opus 5.5/Max contacted the live Claude/default owners through supported
ListAgents/SendMessage. The runtime owner received the
[scope handoff](https://github.com/seathatflowsinourveins/native-agent-stack/pull/535#issuecomment-5913868401).
The [Claude Pi peer's trial](https://github.com/seathatflowsinourveins/native-agent-stack/pull/524)
remains conditional: its small fixtures showed substantial token-stack overhead,
so extra tools are selected by task rather than enabled indiscriminately. The
owned native cooperation session produced no final packet and was stopped. A
subsequent analytical review timed out at 240 seconds without approval; usage is
unknown. Its earlier bare-mode authentication failure does not establish a
missing native account. No peer approval is claimed from these attempts.

Count the primary thread's latest resumed snapshot once: 197,817 native tokens.
The separate successful recovery thread reports 30,927. Their combined 228,744
matches independently captured completed-response usage. Cached input and
reasoning output are subsets. Interrupted, failed and preparation usage,
complete provider billing and overall cost remain unknown. No token-savings or
universal quality claim follows from cache reuse. The scoped
[convergence record](../../blueprints/convergence-practice/omniroute-runtime-workers/experiment.json)
checks declared consistency, not truth or comparative superiority.

Actual provider acceptance invoked the SDK directly from the implementing
coordinator. The supplied Claude dispatch skill is structurally validated; a
native Claude coordinator invoking it remains a distinct unmeasured acceptance
step. Preserve the native sessions, existing SDK comparison gate and live
owner's shared files. Future bridge promotion requires successful native tools,
skills, resume, cancellation/recovery and truthful usage on the selected route;
an advertised model list or unchanged SDK test suite is insufficient.
