# Claude runtime workers: September 30 landscape resolution

Retain native Claude coordination and the official Codex SDK worker through the
child-scoped OmniRoute Responses lane. The
[dispatch guide](../blueprints/runtime-workers/README.md) gives the complete
invocation, ownership and result contract. Current primary-source research
supports several useful alternate interfaces and extensions; it does not
establish a universal quality winner. The
[catalog](../catalogs/foundation/runtime-worker-landscape-20260930.json) records
17 components, immutable source revisions, disposition, evidence level and gaps.

## What is runnable and what remains a trial

The retained worker is `openai-codex==0.159.2`, model
`cx/gpt-6.1-sol-max`, native Max effort. Its recorded direct provider trial covers
repair, unchanged test results, native resume, invalid-resume rejection,
deadline interruption request and fresh recovery. A later native Claude
Opus 5.5/Max call discovered/read the dispatcher and invoked the worker through
Bash; the original result retains one unchanged test command with exit 0.
These dated receipts qualify their demonstrated scope. They were reused rather
than replayed as new model runs. Sources:
[SDK source](https://github.com/openai/codex/tree/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python),
[direct lifecycle receipt](../evidence/receipts/omniroute-runtime-workers-20260930.json),
[native Claude caller receipt](../evidence/receipts/omniroute-claude-callsite-20260930.json).

The separate enhanced-worker experiment now qualifies a bounded Sol/Max SDK
workflow with an actual `using-superpowers` body read, three selected MCP calls,
a recovered Dagu graph, one native Astra/Max judge and an unchanged arithmetic
oracle with exit 0. All eight receipt source hashes match the reviewed worker
files. This manifest reuses the recorded native execution; it adds no provider
trial. The native Claude caller above remains a historical separate source
scope. Sources: [enhancement receipt](../evidence/receipts/omniroute-runtime-enhancements-20260930.json),
[scoped convergence experiment](../blueprints/convergence-practice/omniroute-runtime-enhancements/experiment.json).

Use Astra/Max explicitly for consequential architecture, conflicting primary
evidence or a failure remaining after one bounded Sol repair. This review
triggered that architecture stage. Astra accepted the minimal dispatch
integration and required explicit workspace, private worker home and original
native result. Those arguments are optional in the executable, so the guide
requires the caller to supply them. This review does not resolve the separate
three-arm SDK comparison. The Claude Agent SDK gateway bridge retains two
failed HTTP 500/timeout attempts with zero tool calls and remains an unqualified
trial; its passing upstream SDK suite does not override provider failure.
Sources: [current decision](decisions/2026-09-30-omniroute-runtime-workers.md),
[original bridge receipt](../evidence/receipts/omniroute-runtime-workers-20260930.json).

Gateway source identity is also scoped. Current public OmniRoute 3.8.51 resolves
to `c1e30b76`; the retained decision records a running base `2f42a9ac` with
owned patches, while the component catalog still carries 3.8.50. This review
changes neither source nor lane. A matching version label cannot establish
byte identity or transfer execution acceptance. Sources:
[current release](https://github.com/diegosouzapw/OmniRoute/releases/tag/v3.8.51),
[public release commit](https://github.com/diegosouzapw/OmniRoute/commit/c1e30b7676975feb298b49eff6ff58923c04b89e),
[retained source decision](decisions/2026-09-30-omniroute-runtime-workers.md).

## Current upstream choices

Release and source checks used public GitHub API responses and exact source
revisions on September 30. Discovery covered 352 public starred repositories,
the [CLI coding agents list](https://github.com/bradagi/awesome-cli-coding-agents),
the [AI agents list](https://github.com/e2b-dev/awesome-ai-agents), package
registries, available research skills and the existing selected manifests.
Stars and lists supplied leads. The following primary sources support the
capability and selection statements.

| Component and current pin | Useful native surface | Resolution for this stack |
| --- | --- | --- |
| [Codex 0.159.2 / ff6aec96](https://github.com/openai/codex/tree/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python) | Official Python SDK and native App Server lifecycle | Retain the scoped, demonstrated worker role. |
| [Claude Agent SDK 0.2.162 / f2204bb9](https://github.com/anthropics/claude-agent-sdk-python/tree/f2204bb956bab02907aaf3cb88eb9dead28eaa35) | Native Claude harness lifecycle | Preserve the separate failed-provider trial and its evidence. |
| [OpenHands SDK 1.50.0 / dcf401af](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.50.0) | LiteLLM Responses, native tools, delegation, skills/plugins/MCP, sandbox metrics | Review the upgrade with the owner; retain the frozen 1.49.6 O1 trial until its gates pass. |
| [OpenHands CLI 1.16.0 / 2963442d](https://github.com/OpenHands/OpenHands-CLI/blob/2963442dacc7cea44e39b7c4e73724295c853465/pyproject.toml) | Terminal, headless events, resume and ACP | Separate candidate: Python 3.12, SDK/tools 1.21.0, workspace 1.11.1. |
| [OpenHands extensions 0.25.0 / bea7a20c](https://github.com/OpenHands/extensions/tree/bea7a20c59c44ec4dacddac3fc0efe58b9c73880) | Pinned task skills and native plugin sources | Reuse relevant entries in the existing trial; qualify actual invocation. |
| [OpenHands application 1.24.0 / 7dc68054](https://github.com/OpenHands/OpenHands/releases/tag/v1.24.0) | Separate application/deployment surface | No additional local worker gap demonstrated. |
| [Pi 0.99.1 / d86654ab](https://github.com/earendil-works/pi/blob/d86654abb8862e201933517d6f1fce9f88dd117f/packages/coding-agent/docs/sdk.md) | SDK, print/JSON/RPC, executable extensions | Source-review candidate; coordinate the current canonical repository/package with the Pi owner. |
| [OpenCode 1.18.33 / 51ef4be1](https://github.com/anomalyco/opencode/blob/51ef4be1d3c122f18fefb510dca8d778571f4f18/packages/web/src/content/docs/sdk.mdx) | SDK/server sessions and ACP | Source-review candidate requiring gateway and lifecycle acceptance. |
| [Goose 1.52.0 / 302b6080](https://github.com/aaif-goose/goose/blob/302b60806639ea9f0ae8f053f49f8bf0e88b26f4/documentation/docs/gdk/acp/index.md) | Agent tools/extensions through its runtime/ACP surface | Source-review candidate; its GDK SDK is a provider library, a distinct scope. |
| [oh-my-pi 18.4.4 / 8ac1309b](https://github.com/can1357/oh-my-pi/tree/8ac1309bd8adaddc891eeb389c545345073875be) | A separate extended Pi-derived runtime | Compare only for a demonstrated role gap. |
| [Official Codex for Claude 1.0.6 / db52e28f](https://github.com/openai/codex-plugin-cc/blob/db52e28f4d9ded852ab3942cea316258ae4ef346/README.md) | Claude commands, reviews and App Server integration | Compare the already optional interface; source support is not new OmniRoute acceptance. |
| [Codex ACP 2.0.1 / 7a8e00fe](https://github.com/agentclientprotocol/codex-acp/blob/7a8e00fe46b299264f5ebe9f250288636f1485cc/README.md) | Maintained stdio adapter for Codex App Server | Optional standardized transport with its own acceptance. |
| [acpx 0.19.3 / 6b4714c7](https://github.com/openclaw/acpx/blob/6b4714c7aaac8c38b1fe38354848d2546f65d87d/docs/CLI.md) | Persistent headless ACP sessions, JSON, status and cancellation | Optional Claude Bash interface; retain native session semantics. |
| [oh-my-codex 0.21.6 / cdc24a71](https://github.com/Yeachan-Heo/oh-my-codex/blob/cdc24a71408ebd6bd0362f52170f0d7998f77007/README.md) | Additional Codex orchestration | Defer pending measured benefit and compatible ownership. |
| [Agent Skills / 69ef37e9](https://github.com/agentskills/agentskills/tree/69ef37e9424c0a7ea9dd2293b559e43ec8176379) | Portable task instruction format | Retain task-selected instructions; executable plugins remain separate. |
| [Vercel Skills 1.7.0 / 7407f389](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/README.md) | Supported skill discovery/installation | Use the selected native skill lifecycle. |
| [OpenAI managed Agents API](https://developers.openai.com/api/docs/guides/agents-api/overview) | Managed sessions, tools, skills and recovery | Separate hosted/API scope; no local OmniRoute qualification. |

The current Pi source is `earendil-works/pi`, package
`@earendil-works/pi-coding-agent`. Its
[model configuration](https://github.com/earendil-works/pi/blob/d86654abb8862e201933517d6f1fce9f88dd117f/packages/coding-agent/docs/models.md)
is a possible gateway entry point. Its current
[built-in MCP extension](https://github.com/earendil-works/pi/tree/d86654abb8862e201933517d6f1fce9f88dd117f/packages/coding-agent/src/extensions/mcp)
also means older blanket descriptions of Pi's MCP surface need rechecking.
Existing PR 524's conditional trial remains separate from this new source pin.

OpenCode's [provider contract](https://github.com/anomalyco/opencode/blob/51ef4be1d3c122f18fefb510dca8d778571f4f18/packages/web/src/content/docs/providers.mdx)
distinguishes `@ai-sdk/openai` for Responses from
`@ai-sdk/openai-compatible` for Chat Completions. The official Claude plugin's
[provider check](https://github.com/openai/codex-plugin-cc/blob/db52e28f4d9ded852ab3942cea316258ae4ef346/plugins/codex/scripts/lib/codex.mjs#L817)
accepts `requiresOpenaiAuth=false` and respects `CODEX_HOME`. These source
contracts justify scoped qualification candidates; neither demonstrates a
successful new gateway call.

## OpenHands and enhancements

SDK 1.50.0 supports explicit `api_mode="responses"` for proxy aliases,
`base_url`, provider-neutral effort, native tools, canonical model names,
capability overrides and forwarded headers. Its LiteLLM full Responses path
needs its own wire/model/tool acceptance; the retained Codex worker's
ResponsesLite behavior does not transfer. Source:
[LLM fields and transport](https://github.com/OpenHands/software-agent-sdk/blob/dcf401af7a9a302ef92cb7d092e1df9bb659daa5/openhands-sdk/openhands/sdk/llm/llm.py).

Native OpenHands extension APIs already exist. Use
[`load_skills_from_dir` and `AgentContext`](https://github.com/OpenHands/software-agent-sdk/blob/dcf401af7a9a302ef92cb7d092e1df9bb659daa5/examples/05_skills_and_plugins/01_loading_agentskills/main.py),
[`PluginSource` and conversation plugins](https://github.com/OpenHands/software-agent-sdk/blob/dcf401af7a9a302ef92cb7d092e1df9bb659daa5/examples/05_skills_and_plugins/02_loading_plugins/main.py),
or [explicit MCP definitions](https://github.com/OpenHands/software-agent-sdk/blob/dcf401af7a9a302ef92cb7d092e1df9bb659daa5/examples/01_standalone_sdk/07_mcp_integration.py)
according to the task. Preserve the existing
[O1 installation, isolation, dispatch and official grading gates](../blueprints/runtime-workers/openhands/README.md).
The declared OpenHands installation prefix and executable were absent here;
this review performed no installation or model trial for it.

The existing skill trial contains 136 selections from 12 pinned sources.
It is an inventory awaiting native acceptance. Pi and OpenCode share several
Agent Skills directory conventions, but executable plugins, MCP definitions
and hooks have their own contracts. Sources:
[trial manifest](../blueprints/runtime-workers/skills/manifest.json),
[Pi skills](https://github.com/earendil-works/pi/blob/d86654abb8862e201933517d6f1fce9f88dd117f/packages/coding-agent/docs/skills.md),
[OpenCode skills](https://github.com/anomalyco/opencode/blob/51ef4be1d3c122f18fefb510dca8d778571f4f18/packages/web/src/content/docs/skills.mdx).

The next useful enhancement gate is one relevant pinned skill through the
retained worker: freeze a realistic positive, adjacent negative, unchanged
task oracle, response contract and invocation evidence. Compare the same
worker with and without the extension. Preserve the actual instruction read,
failed attempts, original native result and scoped usage. Existing context,
cache, compaction, isolation, memory and observation recipes remain selected
by the capability a task needs. Sources:
[native skill lifecycle](../adoption/skills/lifecycle.md),
[official skill evaluation](https://developers.openai.com/blog/eval-skills),
[convergence architecture](convergence-architecture.md).

## Supported commands and evidence boundaries

These upstream commands were researched, not executed for the candidates in
this review. Run them only in an owned isolated target or exact upstream
checkout with that project's documented prerequisites. The existing
[adoption lifecycle](../adoption/lifecycle.md) owns installation and rollback.

| Component | Native installation or interface | Unchanged upstream check |
| --- | --- | --- |
| [OpenHands CLI](https://github.com/OpenHands/OpenHands-CLI/blob/2963442dacc7cea44e39b7c4e73724295c853465/README.md) | `rtk uv tool install openhands==1.16.0 --python 3.12`; then `rtk openhands --help` | [Makefile](https://github.com/OpenHands/OpenHands-CLI/blob/2963442dacc7cea44e39b7c4e73724295c853465/Makefile): `rtk make test` |
| [OpenHands SDK development](https://github.com/OpenHands/software-agent-sdk/blob/dcf401af7a9a302ef92cb7d092e1df9bb659daa5/DEVELOPMENT.md) | Pinned checkout: `rtk make build` | `rtk uv run pytest tests/sdk/`; `rtk uv run pytest tests/tools/` |
| [Pi](https://github.com/earendil-works/pi/blob/d86654abb8862e201933517d6f1fce9f88dd117f/packages/coding-agent/README.md#L24) | `rtk npm install -g --ignore-scripts @earendil-works/pi-coding-agent@0.99.1` | `rtk ./test.sh` |
| [OpenCode](https://github.com/anomalyco/opencode/tree/51ef4be1d3c122f18fefb510dca8d778571f4f18) | `rtk npm install -g opencode-ai@1.18.33` | `rtk bun run --cwd packages/opencode test` |
| [Goose](https://github.com/aaif-goose/goose/blob/302b60806639ea9f0ae8f053f49f8bf0e88b26f4/documentation/docs/getting-started/installation.md) | Select the documented v1.52.0 release asset for a pinned install | After documented Hermit setup: `rtk cargo test` |
| [oh-my-pi](https://github.com/can1357/oh-my-pi/tree/8ac1309bd8adaddc891eeb389c545345073875be) | `rtk npm install -g @oh-my-pi/pi-coding-agent@18.4.4` | `rtk bun run test` |
| [Official Claude plugin](https://github.com/openai/codex-plugin-cc/blob/db52e28f4d9ded852ab3942cea316258ae4ef346/README.md) | Claude `/plugin marketplace add openai/codex-plugin-cc`, then `/plugin install codex@openai-codex` | `rtk npm test` |
| [Codex ACP](https://github.com/agentclientprotocol/codex-acp/tree/7a8e00fe46b299264f5ebe9f250288636f1485cc) | `rtk npm install -g @agentclientprotocol/codex-acp@2.0.1` | `rtk npm test`; provider `test:e2e` remains separate |
| [acpx](https://github.com/openclaw/acpx/tree/6b4714c7aaac8c38b1fe38354848d2546f65d87d) | `rtk npm install -g acpx@0.19.3` | `rtk pnpm test` |

Version/help proves readiness only. Unchanged upstream suites, authored
integration fixtures and live provider execution remain separate. This review
added a dispatch map, source catalog and guide links; it made no new worker
installation, gateway-engine change or comparative provider trial.

## Cooperation and anti-pattern log

Installed native Claude listed active runtime-enhancement, OmniRoute/Pi and
default-harness sessions. Exact file ownership was not inferred from their
names. The new work is bounded to the landscape artifacts and links; existing
SDK, gateway, skill and shared-pin implementations remain with their owners.
A fresh Opus/Max read-only contact attempt timed out at 90 seconds without a
final result or complete usage. No contact or peer approval is inferred from
that attempt.

The [Claude 2.1.285 release notes](https://github.com/anthropics/claude-code/releases/tag/v2.1.285)
describe resuming a running background session and forwarding a prompt. Both
installed headless and interactive `--resume` attempts instead returned exit 1,
instructing the caller to use native `attach`, stop, or fork. The correction is
to check the installed invocation rather than extrapolate from the release
description. A handoff was submitted through the supported native `attach` UI;
Ctrl+Z detached the owned frontend with exit 0. Recipient acknowledgement and
completed peer review remain unconfirmed. The owner was not stopped or forked,
and no private IPC workaround was introduced. The catalog retains the
sanitized diagnostic and unknown usage.

Older discovery lists name `zed-industries/codex-acp`. Its
[GitHub metadata](https://api.github.com/repos/zed-industries/codex-acp) now
reports it archived. The corrected maintained source is
[agentclientprotocol/codex-acp 2.0.1](https://github.com/agentclientprotocol/codex-acp/releases/tag/v2.0.1),
verified through current release metadata and its pinned README. Likewise,
installing the separately versioned OpenHands CLI would not qualify the
current SDK/O1 worker; the pinned dependency source above is the verification
path for that distinction.

Repository validation results are retained in the catalog. Source review,
Astra architecture acceptance, a submitted handoff and historical runtime
receipts each retain their own scope. Unknown usage remains unknown.

Independent original-source verification caught an omitted `--ignore-scripts`
flag in this report's initial Pi install command. The corrected command above
preserves the exact pinned
[upstream README](https://github.com/earendil-works/pi/blob/d86654abb8862e201933517d6f1fce9f88dd117f/packages/coding-agent/README.md#L24).
No installation had been performed. Preserve supported command flags when
turning research leads into executable recipes.

## Evidence manifest and offline HTML

The catalog now contains four evidence records: direct SDK lifecycle, native
Claude caller, enhanced SDK/MCP/skill/judge workflow and the failed Claude SDK
bridge. Each names its scope, original receipt, sources and limitations. Its
separate enhancement registry identifies the upstream Codex, context-mode,
Serena, Dagu, mitmproxy, using-superpowers, OmniRoute fixture and RTK pins. The
existing RTK v0.50.0 awareness source resolves to commit
[`1d87b8e`](https://github.com/rtk-ai/rtk/blob/1d87b8e719ce0a50c223cd93ca64dd16921f9aec/hooks/rtk-awareness-full.md)
through the native GitHub tag-ref and hook-file API checks, both exit 0.
This registry records demonstrated roles; it does not install alternatives.

The enhanced workflow discovered 169 enabled skills and exercised one body and
three MCP calls. Its first readiness graph failed; its second parent exceeded
300 seconds; the repaired graph and judge completed. Completed streams retain
unclassified `flow_error` events. Hooks, live web search, schedules and all
other tools remain unmeasured. These failed conditions and unknown backend
identity, billing, complete failed-attempt usage and savings remain visible in
the [original receipt](../evidence/receipts/omniroute-runtime-enhancements-20260930.json).

| Native thread scope | Terminal event | Input | Cached input subset | Output | Reasoning output subset | Total |
|---|---|---:|---:|---:|---:|---:|
| repaired-parent, Sol/Max | task_complete | 151525 | 131712 | 2288 | 1122 | 153813 |
| repaired-judge, Astra/Max | task_complete | 64556 | 61952 | 1488 | 878 | 66044 |
| deadline300-parent, Sol/Max | turn_aborted | 209699 | 178816 | 3365 | 1625 | 213064 |
| deadline300-judge, Astra/Max | task_complete | 105465 | 76160 | 1908 | 1050 | 107373 |

Each row is the latest native cumulative snapshot for one distinct thread.
Count each once. Cached input and reasoning output are subsets, and the
independent observer corroborates the same scopes. Do not add observer counters
as further consumption or combine successful and failed attempts into a
savings claim. Source: [native_threads in the receipt](../evidence/receipts/omniroute-runtime-enhancements-20260930.json).

Build the generated offline guide with
`rtk python3 scripts/build_ecosystem.py --write`, then open its **Runtime
workers** tab. It renders all 17 source-reviewed candidates, evidence records,
native usage scopes, enhancement sources and reset policy, with an original
JSON download and embedded linked guides. The generator extends the existing
optional memory review ingestion and catalog panel patterns; it adds no UI
framework. Sources: [generator](../scripts/build_ecosystem.py),
[template](ecosystem/template.html), [view manifest](ecosystem/manifest.json).

## Native Codex usage-limit recovery

The user clarified that “reset” means the Codex usage allowance, and subsequently
reported that the allowance had reset. That report is the provenance of the
session notice. It is not a backend quota attestation or a reset performed by
this review. Local research workers resumed after the notice.

Installed Codex 0.159.2 and its upstream source support earned-reset redemption
through native `/usage` and the App Server. Installed `--help` and the release
notes expose no standalone reset command; the exact protocol and official
documentation establish the supported interface. Reset-credit operations
require native Codex-backend authentication. A generic OmniRoute custom-provider
child has a separate eligibility scope. Sources:
[native commands](https://learn.chatgpt.com/docs/developer-commands),
[App Server contract](https://learn.chatgpt.com/docs/app-server),
[release](https://github.com/openai/codex/releases/tag/rust-v0.159.2),
[authentication checks](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/request_processors/account_processor/rate_limit_resets.rs#L100).

On an actual included-usage denial, preserve the worker thread, worktree and
explicit model/effort. Read `account/rateLimits/read` through the official
native client. `ordinary_usage_allowed` is backend-validated; an unavailable
value remains unknown and must not be inferred from a timestamp or percentage.
If usage is denied and an eligible earned reset exists, redeem one through
`/usage` or `account/rateLimitResetCredit/consume`, using an idempotency key
reused only for retries of that same redemption. Refresh native limits after
`reset` or `alreadyRedeemed` before resuming once. With `noCredit` or
`nothingToReset`, retain the checkpoint and await a confirmed state change.
Sources: [native account protocol](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server-protocol/src/protocol/v2/account.rs#L330),
[generated SDK contract](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/generated/v2_all.py#L1084).

No earned reset was consumed by this review. Paid credits, purchases and
account/provider changes remain separate scopes. Source:
[official pricing](https://learn.chatgpt.com/docs/pricing).

One read-only native `account/rateLimits/read` attempt with the installed
0.159.2 SDK returned `InvalidRequestError`, exit 1. Both ordinary usage
permission and the available earned-reset count remain unknown. No thread or
model turn was created, and no retry or reset consumption followed. The
sanitized observation is recorded in the catalog's `usage_limit_policy`;
successful resumed research tasks do not prove global account quota status.
Source: [typed native request API](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/async_client.py#L132).

The native broadcast attempt with variadic `--tools` initially consumed its
prompt as another tool name and exited 1 with “Input must be provided”. Supplying
`--` before the prompt corrected argument parsing. Native peer discovery then
succeeded, but its bounded run timed out before a confirmed `SendMessage`.
The later scoped `SendMessage`-only Opus/Max call completed with exit 0 and
reported six notices queued, one per discovered native peer. The active owner
also received the HTML ownership note in its single notice. The manifest
retains the failed attempts, unknown timeout usage and successful native
communication counters separately. Queued delivery does not establish reading,
continuation or peer approval. The public record omits raw conversations,
session identifiers and machine paths.

All 69 renderer integration tests passed. Foundation/catalog validation,
scoped convergence validation and the generated HTML public-artifact scan
passed. Complete repository evidence validation passed before a concurrent
native CLI audit added a new unregistered artifact; the latest global check
requires that artifact's owner to register its hash. All eleven runtime-owned
file hashes match. Earlier failures and both global observations remain in
the catalog. An independent Astra
verifier confirmed the eight source hashes, selected native actions, all four
usage scopes, pinned skill digest and native reset policy; it retained the
23 unclassified `flow_error` events and found no consequential error within
that scope. These checks validate rendering, declared consistency and original
evidence; they add no model trial or alternative-runtime acceptance.

The public dashboard checkpoint now includes the runtime landscape gate and
the scoped enhanced SDK worker. Native full-snapshot validation found an existing
paper-lane reference to a missing trial README. The runtime references exist;
the paper record belongs to another workstream. Four owner notifications have
native successful tool returns and remain queued, with reading and resolution
unconfirmed. No paper status changed and no missing evidence was invented.
The catalog keeps this dashboard condition distinct from the passing HTML and
repository integrity checks. Sources: [checkpoint](../observability/grand-dashboard/state.json),
[native snapshot validation](../observability/grand-dashboard/progress.py),
[checkpoint contract](../observability/grand-dashboard/README.md).

The next all-layer wave recovered all sixteen original paper-trial files from
immutable Git revision `40375e1ecf432749e0f04b521d754866a41ee9d9` and repaired
display labels to the existing public metadata contract. An independent native
snapshot passed with 112 records at 02:43 UTC on October 1. The initial missing
reference and later concurrent oversized-label failure remain recorded.
This restores historical evidence and a timestamped local checkpoint; it adds
no paper run or strategy acceptance. The HTML now maps all twenty foundation
and twelve trading layers to their remaining gates. Source:
[all-layer execution record](../evidence/artifacts/all-layer-next-gap-resolution-20261001/README.md).

A final upstream refresh found Codex CLI 0.159.3, published at 22:57 UTC on
September 30, after the initial source review. Its annotated tag resolves to
[`01fc69f4`](https://github.com/openai/codex/tree/01fc69f4026735edfdf6789820549727a4867b11);
the release notes introduce optional account-security setup reminders for
eligible local ChatGPT sessions. The receipt-qualified SDK and bundled CLI
worker remain at 0.159.2. The newer CLI release is recorded separately from
native worker acceptance; no installation or new provider run followed this
metadata check. Source: [official 0.159.3 release](https://github.com/openai/codex/releases/tag/rust-v0.159.3).
