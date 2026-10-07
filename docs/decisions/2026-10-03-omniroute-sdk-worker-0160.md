# OmniRoute SDK worker publication at Codex 0.160.0

This unit serves reliable native workers for complex systems and the stack's
north-star R&D. It supersedes the stale PR #551 implementation on current main,
without moving the separately owned stack/adoption/SDK-pair pins. The selected
source is `openai/codex` rust-v0.160.0,
`a956835d020762cb2b570053af06f643a11c0ecc`, installed from its published Python
package through maintained uv PEP 723 script locks. No alternative orchestration
runtime or benchmark runner is added.

## Sources and research convergence

Installed uv 0.12.17 supports `uv lock --script` and `uv run --locked --script`;
the [maintained scripts guide](https://docs.astral.sh/uv/guides/scripts/#locking-dependencies)
documents the adjacent lock format. The earlier standalone Codex observation
reported 0.159.3; this unit uses the separately bundled 0.160.0 SDK runtime and leaves that
standalone installation unchanged. The [0.160.0 release](https://github.com/openai/codex/releases/tag/rust-v0.160.0),
read with `gh api`, names a956835d. [Published SDK metadata](https://pypi.org/pypi/openai-codex/0.160.0/json)
couples it to `openai-codex-cli-bin==0.160.0`; the Git SDK pyproject has development
placeholders and is not an installation source.

The builder used the maintained search-first workflow and scoped ai-memory
retrieval as historical leads, then verified exact originals. The read-only
same-session builder self-review compared native feature configuration,
remote catalog authentication,
requirements policy, published-package installation and uv locking. Existing
OpenAI SDK/native configuration already covers the mechanisms, so another SDK,
MCP installer or skill loader is unwarranted. The frozen broader SDK comparison
remains independent of this publication.

## Plugin-sync choice

Set `features.plugins=false` in the standard fixture homes and in the worker's
process overrides/starter template. A dedicated fixture home omits `[features]`
to prove that the production override alone supplies the gate. The worker needs native skills
and MCP, and has no plugin dependency. [Config mapping](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/config/mod.rs#L1715-L1725)
maps the boolean feature to `plugins_enabled`; the [schema](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/config.schema.json#L7038-L7040)
defines the exact key. The [startup gate](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core-plugins/src/manager.rs#L743-L763)
requires plugins enabled, remote catalog inactive and requirements admission of
the curated Git source.

| Alternative | Source-grounded behavior | Choice |
| --- | --- | --- |
| `features.plugins=false` | Stops this startup path and plugin loading directly. | Select the one native feature switch for this worker. |
| Active remote catalog | Needs `remote_plugin_enabled` and Codex-backend authentication. Disabling the remote feature leaves local fallback eligible. | Avoid an authentication/remote-catalog dependency for isolation. |
| Requirements marketplace restriction | A restricted allowed-source policy can reject the curated Git URL while keeping plugins enabled. | Retain as a supported alternative if plugin capability becomes necessary. |
| Pinned marketplace | A requirements allowed Git ref rejects curated `ref=None` unless another rule matches. An ordinary configured marketplace pin is a different mechanism. | Do not substitute it for the explicit gate. |
| Proxy/managed-network settings | These are not conditions in the cited startup gate. | No claim that they disable startup sync. |

[Marketplace policy](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core-plugins/src/marketplace_policy.rs#L52-L103)
activates only with requirements `restrict_to_allowed_sources`; [Git/ref matching](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core-plugins/src/marketplace_policy.rs#L157-L199)
establishes the alternative. No unneeded enterprise policy fixture was installed.
The gate also avoids [HTTP/export-archive fallback](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core-plugins/src/startup_sync.rs#L103-L159).
Plugin skill roots are excluded, while [native skills loading](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/app-server/src/request_processors/catalog_processor.rs#L561-L570)
still receives the configuration layers.

Acceptance scopes fixture temporary roots to the unit's owned private directory
through `TMPDIR`, with 0700 roots/homes. Tests observe direct app-server PID exit
and absence of clone directories, not all descendants or all network traffic.
This choice would be overturned by a required plugin-backed task and evidence
that the native requirements restriction preserves that capability while passing
the same lifecycle/cleanup checks. An upstream fix could also warrant removing
the feature override after those checks pass.

## Recovery and API boundary

The 0.160.0 content-filter fixture observes terminal failure and persisted
guidance with retries disabled and with the native five-retry budget. Guidance
is [recorded before retry checks](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/responses_retry.rs#L66-L171).
Preserve the stopped thread for an explicit permitted alternative or unrelated
authorized continuation; do not discard guidance in a fresh thread or replay the
blocked task. [Bundled guidance](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/prompts/src/model_messages.rs#L57)
defines this boundary. Ordinary cache/prefix preservation claims apply absent a
content-filter stop. Keep gateway providers free of `model_catalog_url`, whose
explicit catalog has different authoritative matching semantics.

Preflight uses exactly pinned SDK internals excluded from the [public root exports](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python/tests/test_public_api_signatures.py#L252-L268).
The private PID chain was reverified against `api.py:317`, `async_client.py:62`
and `client.py:224,268`. The [shutdown implementation](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python/src/openai_codex/client.py#L283-L302)
waits on its direct process. The added [public AsyncThread.read call](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python/src/openai_codex/api.py#L775-L778)
records actual terminal thread status. Recheck private internals on every pin
move. OpenAI calls the [Python SDK stable](https://learn.chatgpt.com/docs/codex-sdk.md)
while [app-server remains experimental and unsupported for production workloads](https://learn.chatgpt.com/docs/mcp-server.md).
This is bounded research/integration acceptance within that boundary.

The role split is explicit: the Codex SDK runs the local Codex harness; the
[Agents API](https://developers.openai.com/api/docs/guides/agents-api/overview)
runs that harness as an OpenAI-managed service, owning sessions, orchestration,
compaction and recovery. The
[Agents SDK](https://developers.openai.com/api/docs/guides/agents/sdk)
is an agent loop inside the caller's application. These are separate deployment
choices, and no managed Agents API or Agents SDK acceptance is claimed here.

The B2 startup repair retains and shields the native startup task across the
overall deadline, then waits for it to settle before closing the SDK. The
[pinned async wrapper](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python/src/openai_codex/async_client.py#L73-L103)
offloads native start/initialize/close to threads; caller cancellation does not
establish that those operations have settled. Python 3.13's
[shield contract](https://docs.python.org/3.13/library/asyncio-task.html#shielding-from-cancellation)
supplies the cancellation pattern and requires strong task references. Cleanup
has one bound and reports `unresolved` if it expires, with nonzero CLI exit;
owned cleanup can continue while an embedding event loop remains running.
Delayed real native startup tests reproduce the original premature `closed`
result for both worker and preflight and now observe direct PID exit or truthful
unresolved status. Native items are saved before the post-turn status read;
a read error is recorded without changing the completed turn status.

## Observed scope and preserved history

The [new receipt](../../evidence/receipts/omniroute-sdk-worker-0160-20261003.json)
retains commands, exits, exact decisive returns, native usage, controls and limits.
All twelve B2 final fixture invocations passed nineteen tests each. The earlier
twelve fifteen-test invocations remain separate pre-B2 attempts. Metadata
preflight discovered the required Context Mode catalog without inference. No
skill was installed in the new private home, so no skill requirement was added;
discovered inherited/project skills are a separate observation.

One live read-only task through port 20128 returned the exact twelve-file set
and 0.160.0 pin, with a completed turn, idle native thread and closed SDK. The
retained native artifact also contains two shell startup failures and one MCP
transport failure; the successful Context Mode call supplied the requested data.
Native shell startup was not qualified by that nested completed task.
The retained error is `app-server socket directory must be a user-owned directory
with mode 0700`. The pinned [socket-directory helper](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/uds/src/daemon_directory.rs#L1-L35)
fixes its shared location independently of HOME, TMPDIR or CODEX_HOME, and
[bubblewrap validates it before restricted execution](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/linux-sandbox/src/bwrap.rs#L425-L430).
The coordinator subsequently ran a separate non-nested read-only shell task:
worker exit 0, turn completed, one `commandExecution` with exit 0 and output
`13`, idle thread and closed cleanup. The copied
[coordinator observation](../../evidence/artifacts/omniroute-sdk-worker-0160-20261003/coordinator-shell-observation.json)
records native-result SHA-256
`244f6e30f795cbbcb51ba50a96adb2b25adb8f27bde7b7fb931bcebba6725698`.
This is coordinator-supplied evidence at the pre-B2 candidate, not a builder
rerun. The [socket helper's header](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/uds/src/daemon_directory.rs#L1-L4)
states that sandboxes hide the socket root by design, supporting the
coordinator's explanation of the builder's nested-run failures. The separate
MCP `Transport closed` failure remains retained. Writing (`workspace-write`)
dispatch is not yet qualified at 0.160.0. Requested Max
effort, forwarded effort and backend identity remain distinct. The default route
requires an OmniRoute build carrying PR #15167; its live catalog entry was checked.

September 30 receipts remain byte-identical. Both historical convergence records
retain #551's base revisions, tasks, roles, tools, commands, observations and
qualification IDs. Only frozen references to changed files point to
byte-identical historical copies, with dated provenance notes. The separate
[October 3 sibling record](../../blueprints/convergence-practice/omniroute-runtime-workers/experiment-sdk-0160-20261003.json)
uses current-main base `56473e4b840f0e6940c031801d866e7e9bf29baf`, 0.160.0
tools and its own source closure. It holds the two moved pre-B2 observations,
the B2 fixture acceptance and the separately attributed coordinator shell
observation. The builder's live run occurs once in convergence observations;
each native thread's latest cumulative usage is counted once. Current checks
describe current files. This does not rerun the
historical Claude callsite, Astra judge, Dagu graph or upstream SDK suite.

## Completeness critic and remaining audit ownership

The same-session builder self-review checked the feature gate, all other gate conditions,
SDK API/PID internals, content-filter continuation policy and current skill
readiness wording. Its HTTP/archive and descendant-versus-direct-PID findings
are carried above and feed the next worker lifecycle sweep. That sweep must also
qualify writing dispatch and the retained MCP transport failure at the repaired
candidate. The audit's separate critic supplied only the HP-2 gate alternatives
(`claude-audit-synth.json#/critic/gaps/9`) and the NA-2 correction from four keys
to six property paths (`claude-audit-synth.json#/critic/challenged_actions/9`).
The broader checks in this paragraph are builder self-review, not independent
review. Optional approval modes, scheduled Dagu runs,
long-lived SDK pools, full skill coverage and the broader SDK comparison retain
their own gates.

AD-1 shared-home state-DB acceptance belongs to the separate pin-move owner; this
unit uses private homes. AD-2 session tagging remains deferred until the gateway
owner confirms its documented memory side effect and by-run reconciliation.
HP-4 forwarded effort/backend attestation is unmeasured; no model substitution
or forwarded-Max claim is made. PL-2's harness guard is added, while the separate
main worker-lane test belongs to its owner. The coordinator-owned historical
temporary-directory cleanup is not performed by this worker. No-action NA-1
through NA-4 require no SDK redesign; the changed runtime and namespace/skill
surfaces are exercised within this unit's stated scope.

## Corrections and rollback

The contract's “39 added files” count was corrected by the unfiltered native Git
diff at source head `0e86cb7e7798b497a43672dc67328a12d2793964`: its named families
contain forty added files. All forty were imported. Shared Git metadata is
read-only in this worker, so the source ref was fetched into owned private Git
metadata and its exact head was compared with the worktree's source ref. The
local exclude hides `.claude/`; the proposed review index explicitly includes
the dispatcher skill. The coordinator must preserve that file when staging.

Discard this uncommitted candidate to retain current main. Restore historical
0.159.2 sources only from their immutable copies when replaying historical
observations; do not change the independently owned host/pin installation.

The first receipt assembly rejected its own file-set comparison because a raw
recursive file walk included an ignored Python bytecode cache. Rechecking with
the same native `rtk proxy rg --files --hidden examples/omniroute-codex-sdk`
command used by the retained live tool returned the exact twelve source/config
paths. The same-session builder observation now uses that command; the failed assembly
and correction remain in the new receipt. No worker source or test result changed.

The same-session builder readback corrected a receipt description of the version
negative control: `test_explicit_wrong_runtime_version_is_not_replaced_by_user_agent`
supplies an invalid explicit `serverInfo.version` alongside a correctly pinned
userAgent. The worker's `native_runtime`
rejects the explicit version instead of replacing it with that matching fallback.
The refreshed receipt and local checks describe this tested condition. The worker
is an uncommitted review candidate using OpenAI's published SDK; its publication
is not an official upstream worker release.

Earlier publication validation at the owned checkout reported the host-excluded,
untracked dispatcher. A retry with the private index reports the same failure:
`scripts/validate.py:240-259` intentionally removes inherited `GIT_*` variables.
The earlier assumption that the private review index could satisfy that exact
root enumeration was wrong; `tests/test_validate.py:361-369` covers the guard.
Both returned failures remain recorded. The coordinator has since force-added
the skill to the real index; B2 checks use that actual checkout index.

The additional artifact check exports the native proposed tree with installed
Git 2.43.0 [write-tree](https://git-scm.com/docs/git-write-tree) and
[archive](https://git-scm.com/docs/git-archive/2.43.0), whose installed help and
official manuals were read. That private source archive includes the
force-staged dispatcher, preserves the proposed bytes, and uses the validator's
supported archive-root behavior (`scripts/validate.py:277-303`). Archive acceptance
did not replace the then-failing checkout enumeration. The coordinator's
force-add resolves that earlier enumeration gate; B2 reruns the checkout
validator and all three registry tests on the real index. No shared index,
ignore file, validator or permission rule is changed by this workaround.

The exported native proposal passed the unchanged publication validator with
9,369 hashed files and 190 receipts. Its native tree/inventory identity and all
55 owned file comparisons are retained privately and summarized in the new
receipt. This is an artifact integrity/scope check, alongside the retained
checkout failure; it adds no provider execution or acceptance for native shell.

The B2 correction rejects the earlier claim of an independent completeness
critic: the claimed wider coverage was same-session builder self-review. Exact
audit critic locators above are the only attributed audit contributions. The
delayed-start regression command first returned `FAILED (failures=5)` across
three tests; the same command after repair returned `Ran 3 tests ... OK`.
Final lint and metadata preflight are rerun on the repaired Python source;
earlier “final” attempt IDs are labeled pre-B2. Keep the project skill through
the dated exception in `adoption/skills/lifecycle.md`; the reusable graph has
task-configured skill requirements rather than a fixed `using-superpowers`
dependency. None of these repairs launches a new live model task.

## B3 review-bot repairs (2026-10-03)

This bounded repair serves reliable native workers for complex systems and
north-star R&D, and addresses all five Codex bot threads on PR #628 from base
`7c9d7214d`. It keeps the same SDK/native runtime and dependency pins. The
diagnosing-bugs workflow supplied failing regression commands before production
changes; the five reported causes were already specified, so a separate
hypothesis/instrumentation round was unnecessary. Official OpenAI documentation,
the exact pinned upstream sources and the existing OmniRoute profile establish
the configuration choices; no replacement runtime or test runner is introduced.

`--api-key-env` now excludes its validated name through the canonical keyed
`shell_environment_policy.filters` override alongside the provider's `env_key`.
The starter home excludes `OMNIROUTE_API_KEY`; keyed worker launches also disable
shell snapshots, matching the template and OmniRoute profile. At a956835d,
[the policy struct and keyed conversion](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/config/src/shell_environment_policy.rs#L28-L35)
and [exclude mapping](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/config/src/shell_environment_policy.rs#L137-L162)
define this supported form; [mixing keyed and legacy filters is rejected](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/config/src/shell_environment_policy.rs#L106-L110).

The custom provider now sets `supports_standalone_web_search=true`, and its
process overrides and starter home enable `features.standalone_web_search`.
[The custom-provider field defaults to false](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/model-provider-info/src/lib.rs#L194-L196)
and [the native feature is separately off by default](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/features/src/lib.rs#L1128-L1132).
The [official configuration reference](https://developers.openai.com/codex/config-reference)
confirms the two gates. Configuration checks establish the switches, not a
successful live gateway search or keyed-shell confidentiality trial.

Claude SDK connection now shares the query's operation deadline. A `finally`
block calls the native exit/disconnect path even if entry times out or throws;
only interrupt/drain and shielded disconnect receive cleanup grace. The pinned
[client entry/exit methods](https://github.com/anthropics/claude-agent-sdk-python/blob/f2204bb956bab02907aaf3cb88eb9dead28eaa35/src/claude_agent_sdk/client.py#L623-L631)
and [AnyIO finalization guidance](https://anyio.readthedocs.io/en/stable/cancellation.html#finalization)
are the reference. Native [query cleanup](https://github.com/anthropics/claude-agent-sdk-python/blob/f2204bb956bab02907aaf3cb88eb9dead28eaa35/src/claude_agent_sdk/_internal/query.py#L1149-L1182)
has its own shields and transport bounds; the wrapper does not override those
native termination guarantees. Slow and failing connection fixtures both reach
disconnect without starting a query.

The observer now splits complete SSE lines once before bounding the remaining
incomplete frame. Its test returns a chunk over 2 MiB byte-identically and
captures its terminal usage, while the fragmented overflow control still fails
capture. The supported callback remains mitmproxy v12.2.3's
[streaming addon](https://github.com/mitmproxy/mitmproxy/blob/6c09d56e4c29a92f5ad01b03199977584b8ea14f/examples/addons/http-stream-modify.py#L17-L29).
`--native-result` now reserves its 0600 `O_EXCL` file before SDK initialization or
thread creation. It saves completed items before the post-turn read and writes a
sanitized failure record on earlier failure. The existing retention mechanism
uses the supported [Python `os.open`](https://docs.python.org/3.13/library/os.html#os.open)
flags; no destination is overwritten.

The red Codex command returned `Ran 6 tests` and
`FAILED (failures=4, errors=3)`; the red Claude connection command returned
`Ran 2 tests` and `FAILED (failures=2)`; the red observer command returned
`Ran 1 test` and `FAILED (failures=1)`. The same commands passed after repair.
Final Codex acceptance passed **12 of 12 invocations, 25 tests each**; the final
Claude suite passed 26 tests and the observer suite passed six. The documented
disarmed route oracle returned exit 1, and the armed oracle returned exit 0.
Ruff check and format check passed on all six changed Python files. Commands,
actual excerpts and private-log hashes are retained in the updated receipt;
B2 and September 30 results remain historical. No B3 live model task ran.

The same-session builder completeness self-review checked the starter template,
arbitrary validated key names, both independent search gates, failed entry and
shielded cleanup, fragmented and batched SSE, and early result reservation.
It identified the remaining live keyed-shell/search path, native connection
faults and MCP/workspace-write qualification as work for the next worker
lifecycle sweep. These are limitations of local fixture evidence, not an
independent review or a new provider acceptance claim. The narrower alternatives
(exclude arrays, only one search gate, connection grace, chunk-size bounding and
post-turn destination checks) are rejected by the cited native configuration or
the failing controls. Revisit these choices if upstream changes the APIs or a
matched native lifecycle run disproves the fixture behavior.

The first B3 publication check caught an incomplete evidence seal: the registry's
receipt claim/limitations still described B2, and unittest's shortened failure
repr retained a personal path prefix that escaped full-path substitution. The
first convergence check also rejected qualification IDs whose scope differed
from the new decision scope. Those actual failed outputs remain in the receipt.
The correction synchronizes this receipt's registry metadata, sanitizes the
shortened prefix, and assigns the three current candidate suites one explicit
qualification scope; historical B2 observations remain recorded separately.
These were record consistency repairs and did not change the passing Python
implementation or require another model run.

Corrected publication acceptance returned 9,392 hashed files and 190 receipts;
all 29 recorded convergence experiments validated. Component matrix and new-host
reports passed without regeneration, and the real checkout index passed all
38 OSV tests and the three required pre-push registry tests. Those returned
outputs are sealed in the receipt before the final read-only publication and
convergence rerun. `host_receipts.register_file` re-registers the owned files
after their last change, with the receipt claim/limitations synchronized in the
registry; the coordinator retains commit, push and final merge ownership.

## Amendment (2026-10-07): exact SDK 0.160.1 qualification

The maintained example moves its exact published SDK/runtime pair to 0.160.1
at `openai/codex@d27764b82f7118f674371e6d6e76271d9d606edb`. The original
decided text and every earlier observation remain unchanged. The new
[qualification receipt](../../evidence/artifacts/skills-sdk-01601-20261007/receipt.json)
records a clean isolated wheel install, the unchanged upstream installed-SDK
protocol smoke, 31 authored integration fixtures and model-free discovery
against the installed native CLI 0.160.1, explicitly routed through 21128.

Keeping 0.160.0 would leave the installed client's catalog unqualified under
the existing exact-version guard. A range or weakened guard is rejected: the
new pin remains an exact equality, and its mismatched-version control still
rejects. Upstream initialization fields and the user-agent fallback retain
their tagged source blobs. This comparison would be overturned by a changed
native interface or a failing unchanged upstream/local integration check at
the new pair; retain that failure and qualify another exact pair.

The source is the [published release](https://github.com/openai/codex/releases/tag/rust-v0.160.1),
[version-pair publication policy](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/sdk/python/RELEASING.md#L3)
and [upstream installed-SDK check](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/sdk/python/tests/installed_sdk_smoke.py).
Catalog discovery does not establish prompt visibility, actual skill/MCP use,
organic counters or live writing dispatch. Shared/global adoption pins and
client configuration remain outside this example update.
