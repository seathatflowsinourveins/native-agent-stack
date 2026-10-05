# 2604 E2E G2: MCP inspection and runtime-worker plan repair

Date: 2026-10-04. Scope: the three assigned install-plan slots, built on
PR #684's head without committing or operating a WSL
distribution. The launch pins Sol at max; no additional agents were launched.
The north-star action is to make native inspection, bounded coding delegation
and two public research gatherers usable on the clean foundation before the
US-equities research and historical-simulation work begins.

This is a source-backed plan repair. Its repository checks are structural and
local integration checks; it records no new provider, native-client, container,
GPU or destination-host acceptance. Historical executor receipts and the supplied
Opus adjudications explain the gaps; current upstream source establishes the
replacement commands. The supplied `fixes.json` was absent. The available
adjudication, executor and independent-review records covered all three slots.
Scoped ai-memory retrieval was unavailable under this job's tool approval policy;
exact repository files and tagged upstream source were read directly.

## MCP Inspector

Keep the plan's existing 2.9.0 on-demand pin, with an explicit Web command, Node
`>=22.19.0`, and an acceptance function that runs only when named. Inspector
2.9.0 resolves to `ae865a19178ddf6f375780a02e9c77c4cf4da184`; the npm latest
metadata and tagged release were checked on this date.
[Launch and prerequisite](https://github.com/modelcontextprotocol/inspector/blob/2.9.0/README.md#L9),
[launcher routing](https://github.com/modelcontextprotocol/inspector/blob/2.9.0/clients/launcher/README.md#L15).

Use upstream `npm install` and `npm run pack:verify` in a disposable acceptance
checkout. That harness verifies the actual tarball in a clean consumer, CLI,
production Web and a Chromium-rendered MCP App. Retain `smoke:web:tabs` separately
for the build-tree Tools-tab interaction. A real QMD `tools/list` is an additional
local integration check.
[Published-package smoke](https://github.com/modelcontextprotocol/inspector/blob/2.9.0/docs/publishing.md#L16),
[native scripts](https://github.com/modelcontextprotocol/inspector/blob/2.9.0/package.json#L84).

The plan checker now admits only this narrowly defined on-demand route; ordinary
excluded rows remain prohibited from carrying commands or executable acceptance.
The original checker rejected the proposed Inspector command/acceptance before
the repair. The repaired checker requires the pinned launch and Node prerequisite
and retains the existing rejection of commands on ordinary excluded rows.

The executor's claim that native wiring did not apply was incorrect: the existing
client map declares `MCP_AUTO_OPEN_ENABLED` for both native clients. Keep that
wiring and require fresh headless sessions to observe the inherited `false`,
launch the pinned package against QMD, serve the Web page and stop its process.
Use the upstream memory-only secret-store option for these keyless checks.
`native-agent-stack@PR #684's head:adoption/new-wsl/client-config-map.json:27`;
[secret-store option](https://github.com/modelcontextprotocol/inspector/blob/2.9.0/docs/secret-storage.md#L148).

Alternative rejected: `smoke:web:tabs` alone proves the source build, not the
published package. Global installation adds no capability needed by this route.
The global stack's historically accepted Inspector 2.8.0 recipe remains distinct
from the already-pinned clean-host 2.9.0 profile/plan; this job does not relabel
that earlier host qualification. Reopen the on-demand choice if the pinned
published-package smoke fails or the installed client ceases to inherit the
mapped environment setting.

## OpenHands worker

Repair in this PR (job 058): restore the definitive manifest's selected SDK/tools/source baseline v1.50.1 at
`1e1390acc8788346ba4804c34323284009bf3f5e`. The prior 1.51.0 currency move had no declared amendment. It remains a follow-up for the pending comparison; current latest metadata does not override the selected baseline. Export constraints from its frozen workspace lock with
`uv export --frozen --no-dev --no-hashes --no-emit-workspace --package openhands-tools`,
then install both 1.50.1 wheels with those constraints into the owned interpreter.
[Release](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.50.1),
[package dependency](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/openhands-tools/pyproject.toml),
[uv export](https://docs.astral.sh/uv/reference/cli/#uv-export).

Post-install acceptance runs unchanged `tests/sdk` and `tests/cross` with the
frozen development environment. This focused selection omits tools, workspace,
agent-server, browser and live-provider suites. After sign-in, run the unchanged
hello-world example under srt from an owned scratch cwd using its native LLM environment
variables; its `os.getcwd()` workspace must not dirty the source checkout.
[CI test installation and command](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/.github/workflows/tests.yml#L94),
[unchanged example](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/examples/01_standalone_sdk/01_hello_world.py#L9).

Port the supplied phase-1 dispatcher as repository integration glue around the
tagged Agent, Conversation, preset tools, hooks, skills, subagents and persistence
APIs. Install the per-job `openhands-job@.service` and render each job's srt policy
with only its named workspace/private state writable. Keep `proxy_loopback` and
the gateway's `127.0.0.1:21128` allowance. Register the template with the user
manager; install starts and enables no job. The unit expects the default user
XDG directories and the plan's mise shims; the `sandbox-runtime-srt` slot is its
prerequisite. The worker and research skill placement honors CLAUDE_CONFIG_DIR. Existing failed units are a host-executor cleanup task, with their
journals preserved.
[Preset composition](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/openhands-tools/openhands/tools/preset/default.py#L37),
[MCP integration](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/examples/01_standalone_sdk/07_mcp_integration.py),
[sandbox settings](https://github.com/anthropic-experimental/sandbox-runtime/blob/v0.0.78/README.md).

Within the bounded file ownership, the dispatch instructions are installed as
`native-stack-worker` in both native skill directories. Fresh Claude and Codex
sessions dispatch different positive jobs. The enclosing acceptance reads the
native completion records, unit Result, `run-report.json` and the computed file
independently. A successful-response counter comes from the SDK's response-latency
records, rather than a preflight/version or an agent's statement. A closed-port
negative must fail with zero model requests; only that exact failed instance is
reset after its evidence is retained.
[SDK metrics](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/openhands-sdk/openhands/sdk/llm/utils/metrics.py#L113),
[Codex user skill root](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/ext/skills/src/host_roots.rs#L103),
[Claude native skills](https://code.claude.com/docs/en/skills#where-skills-live),
[native Codex command events](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/exec_events.rs#L159).

Comparison at v1.50.1 found every API the dispatcher uses: preset default tools
and built-in agents, AgentContext flags, HookConfig.load, register_file_agents,
persistence, NeverConfirm and the response-latency counter. No 1.51.0-only API
is essential. Reverting source, wheels, worker, unit and catalog together avoids
another undeclared selection. A 1.51.0 comparison result and amendment, or a
verified API missing at 1.50.1, would overturn this choice.

The frozen 1.49.6 container/SWE-bench recipe keeps its original
pin and acceptance boundary. The architecture winner records the 1.50.1 clean-host SDK plan pin in its
existing fields and retains the separate frozen-container version in notes. The general stack/profile contain no OpenHands component row;
inventing a new inventory entry would change the coordinator's shared counts.
Reopen this version if its unchanged focused tests fail, the dispatcher cannot
complete both native-client jobs, or the per-job isolation qualification fails.

## Independent research gatherers

Keep GPT Researcher v3.7.0 at `0957c301ed06c2a5857b834358c7227c739041d4` and
DeerFlow v2.1.0 at `345f08be00c8a9495079b732a39b46aa9af1584e`. GPT Researcher's
0.16.0 distribution metadata is legitimate for that source tag. Its existing
requirements installation, fail-closed preflight, scrubbed keyless gateway route
and five-reference report check remain. Install byte-identical copies of the
repository runner and public configuration together for invocation from any cwd.
`native-agent-stack@PR #684's head:tools/research/gpt_researcher.sh:27`;
[GPT Researcher source version](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/pyproject.toml#L23),
[upstream research CLI](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/cli.py#L336).

Configure an active embedded DeerFlow model using the documented ChatOpenAI
Responses route, the selected loopback model and the placeholder `local-loopback`.
Keep upstream DuckDuckGo and web-fetch tools. The dedicated config is preserved
on rerun, with a private per-run home/state; no operator .env edit, account secret
or new service is required. Run unchanged `backend/tests/test_client.py`, including
mocked Gateway conformance, and verify the configured model. Execute the documented
`DeerFlowClient.chat()` example and require an actual nonempty cited answer.
[Model configuration](https://github.com/bytedance/deer-flow/blob/v2.1.0/config.example.yaml#L250),
[DuckDuckGo](https://github.com/bytedance/deer-flow/blob/v2.1.0/config.example.yaml#L802),
[embedded example](https://github.com/bytedance/deer-flow/blob/v2.1.0/README.md#L1658),
[unchanged client tests](https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/tests/test_client.py).

Install `native-stack-research` for both native clients. Each fresh headless client
must complete both gatherers; the enclosing acceptance requires completed native
tool records and new report/answer artifacts. Source-reference thresholds, client
output observation and the absence of DeerFlow HTTP listeners remain local
integration assertions. Gateway-side successful requests and zero embeddings
calls still require the host's independent observation.

Alternative rejected: provision DeerFlow's HTTP/Compose stack or activate the
gated research skill to use its documented embedded API. The supplied review
correctly distinguishes an import from research; it also confirms that absence
of an HTTP service is consistent with this selected route. Reopen the embedded
choice if the upstream chat fails with this configuration, either native client
cannot invoke both gatherers, or their source-grounding comparison fails.

## Completeness and handoff

The bounded completeness review covers the previously missed modalities:
published package versus source build, interactive Web versus CLI, positive
model execution versus zero-request preflight, both native client families, and
both independent gatherers. Original upstream commands, repository glue and
independent state observations have separate evidence classes. TUI, OAuth,
browser-enabled OpenHands, the frozen container grader and a DeerFlow server are
outside these selected jobs, not implied accepted features. Host execution,
sign-in and live output review remain with the coordinator's E2E executors.

Shared inventory counts and headers were deliberately left unchanged. This plan
now has 129 command entries and 80 acceptance entries, compared with 118 and 78
at the supplied head. The coordinator must refresh the shared summaries and the
hash/byte registry in `manifests/evidence.json`, including generated handbook
bindings; this builder does not edit that file.

Final offline acceptance used the job-local `.bounded-fix-wave-g2-mcp-workers/tmp`
as TMPDIR. `check_plan.py` passed with 80 rows, 129 commands and 80 acceptance
entries. `bash -n` passed for `install.sh` and `accept.sh`; the generated handbook
check passed. `validate.py` returned 1 with registry drift only: 24 hash/byte or
unlisted-artifact findings, with no other publication-validation finding.

The four required unittest modules ran 324 tests and returned 1 with 85 failures
and 12 errors. The same command on a clean Git checkout of PR #684's supplied
head ran 324 tests and returned 1 with 84 failures and 12 errors; that checkout
remained clean. Every baseline failure/error section reproduces in the repaired
tree. Those inherited failures include the stale `codex-user-instructions` block
and the RTK 0.50.0 owner/default row versus the stack's 0.51.0 pin. The only added
failure is the generated handbook's coordinator-owned receipt binding; handbook
generation itself passes. These unrelated inherited repairs and the evidence
registry update are handed back to the coordinator. No destination-host or
fresh-native-session acceptance was run by this builder.
