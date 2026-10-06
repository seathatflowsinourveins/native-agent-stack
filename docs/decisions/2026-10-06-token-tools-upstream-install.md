# Record the command center's native token-tool install decisions (2026-10-06)

Decided by the command center (CC), under the user's dated directions of
2026-10-05 to proceed with converged upstream installation practice and
2026-10-06 to reduce routine safety friction. This record transcribes the
CC's STEP5 instruction and subsequent D6 amendment. It makes no new trust,
permission, installation, client configuration or exclusion decision and
applies nothing. The CC performs the approved client steps in its quiet window.

North-star action served: finish the foundation for complex engineering and
US-equities research while retaining native client behavior, source fidelity
and one owner for each information contract. Quality determines adoption;
recency gates eligibility. Popularity is not acceptance evidence.

The ordered plans are `wf_8703c159-c6d` (seven token tools) and
`wf_5e8f452c-484` (Serena). Their research/verifier outputs are source leads;
the original pinned sources and the CC's instructions govern this record.
The plans originally attributed D1 and D4 to the user; the CC's STEP5 direction
corrects that attribution. All six decisions below are the CC's application
of the named user directives. Host application and fresh-session acceptance
remain future evidence gates.

## D1 — CBM Codex hook trust approved

The CC approves trust for the `hook-augment` command installed by
[DeusData/codebase-memory-mcp v0.11.0](https://github.com/DeusData/codebase-memory-mcp/tree/8972ea69c6ad94b1ef1d4ffbf0a92d78d2db1798),
using the vendor's own installer. Its native Codex integration requires a
trusted hook; the installer supplies the registered command. Trust remains
reversible through the plan's step-7 backup and the maintained
[`codex_hook_trust.py`](../../tools/adoption/codex_hook_trust.py) workflow.

Alternatives are leaving the hook untrusted and inactive, or creating a local
replacement installer/hook. The latter duplicates maintained upstream behavior;
the former fails the approved context-supply role. Overturn or withdraw this
grant if the installed command/hash differs from the reviewed vendor command,
native trust/read-back fails, a conflicting control effect appears, or a
qualified upstream revision replaces the mechanism. No trust is granted by
publishing this document.

## D2 — CBM pointer approved, conditional on context measurements

The CC conditionally approves the vendor's 148-byte Codex pointer and the
four-byte rename of the existing AGENTS.md line-20 reference. Plan step 18
must measure actual start-of-session and subagent-start context against the
decision ceilings **24,031/19,585 bytes**. Keep the existing test constants
**24,458/20,103** distinct; this record edits neither instructions nor tests.
The later new-WSL comparison supersedes the earlier projected Codex 19,389
ceiling in [the context-budget record](2026-10-05-harness-context-budget.md).

The comparison must retain before/after inputs, actual rendered bytes and
independent review. If a ceiling is exceeded, move the pointer behind
on-demand loading; preserve the pointer rather than removing the approved
capability. Alternatives are startup preloading, the bounded native pointer
and on-demand loading. The measured footprint determines which permitted
placement holds the information contract. Overturn the startup placement if
actual measured context exceeds either applicable ceiling or a native
upstream surface supplies the same role with a smaller adequate footprint.

Sources: CBM v0.11.0's native installation/instruction surface and
[the pinned budget comparison at current main](https://github.com/seathatflowsinourveins/native-agent-stack/blob/0d5e6506434fab598dee861c749a22e628beb75a/docs/decisions/2026-10-05-harness-context-budget.md#L669).
The numerical approval is conditional; no measured post-install result is
claimed here.

## D3 — vendor skill and agents receive a lifecycle exception

The CC approves a bounded exception to the repository's manifest-driven
[skills lifecycle](../../adoption/skills/lifecycle.md) for CBM v0.11.0's vendor
skill and three vendor agents. Add `effort: max` to their frontmatter under
[the max-effort rule](2026-09-29-max-default-effort.md). Upstream's update
behavior preserves edited agents, so the local change and its ownership must
remain explicit during future vendor updates.

The vendor frontmatter is emitted by
[`src/cli/agent_profiles.c:608`](https://github.com/DeusData/codebase-memory-mcp/blob/8972ea69c6ad94b1ef1d4ffbf0a92d78d2db1798/src/cli/agent_profiles.c#L608).
The installer preserves modified profiles in
[`src/cli/cli.c:8710-8721`](https://github.com/DeusData/codebase-memory-mcp/blob/8972ea69c6ad94b1ef1d4ffbf0a92d78d2db1798/src/cli/cli.c#L8710).

Alternatives are the unchanged inherited-effort agents, the approved bounded
frontmatter edit, or duplicate locally authored skill/agent definitions.
The exception selects maintained vendor definitions with the required effort
and avoids duplicate routing surfaces. Overturn or revisit the exception if
upstream supplies the required effort natively, stops preserving edited files,
changes the agent/skill contract, or a measured lifecycle comparison finds
lost updates, duplicate exposure or context cost exceeding the accepted budget.
No skill or agent file is installed or edited by this record.

## D4 — Headroom stays MCP-only pending the quality comparison

The CC selects MCP-only Headroom for now. Proxy mode remains disabled until
a **promptfoo** A/B through the NativeStack2604 OmniRoute gateway on
lane-shaped work shows that quality holds. Overlap-token owns that A/B; it is
the same comparison as token-audit gap 2. Prepare fixed tasks, quality/token
measures and thresholds before running it. Under PARK, the long run waits
for the tools-wave relaunch or a specific CC exception.

The no-chained-compressors rule applies: evaluate each candidate mechanism
against its baseline without attributing overlapping reductions twice. The
approved clean-install plan targets
[Headroom v0.40.0](https://github.com/headroomlabs-ai/headroom/tree/v0.40.0);
the historical v0.37.0 native compression/recovery receipt remains historical.
Alternatives are MCP-only selected-artifact compression/recovery, proxy mode
qualified by the paired comparison, and the existing adequate context/output
owner. A quality regression blocks proxy adoption. A later superior upstream
comparison, chosen-owner regression or organic use overturns the disposition.

The CC sets a further disposition gate: if Headroom has zero organic calls
after **48 hours** and no A/B win, produce a dated exclusion. Record the
observation window, coverage and comparison in that later decision; this
document excludes nothing. The existing exclusion evidence rule, including
equivalent chosen coverage and the native routing-fix/rerun evidence, remains
visible in [the owner-contract record](2026-10-05-native-token-context-owner-contracts.md)
where available; it is not replaced by an unqualified zero count.

## D5 — keep qualified SocratiCode 1.15.0

The CC keeps the qualified **1.15.0** engine. Move to **1.16.0** only through a
verified prefix installation together with the mcporter builder. Sources are
the maintained [SocratiCode qualified 1.15.0 source](https://github.com/giancarloerra/SocratiCode/tree/f6191f076a42405f0d5508139f3a8b505cfef93a)
and the vendor's proposed [1.16.0 source](https://github.com/giancarloerra/SocratiCode/tree/3d3a4a4d427cb0f29de4f5dd1360da52896f62df) in the ordered plan,
as verified against their native installation/runtime interfaces in the plan.

Alternatives are retaining the passing prefix, silently floating to a newer
package, or a separately verified prefix plus builder. The approved path
preserves the existing qualification until the coupled upgrade passes.
Overturn the version hold when the new prefix/builder's native checks and
functional indexing/query evidence pass with retained outputs, source pins,
recovery and relevant before/after measurements. No package or registration
is changed here.

The coupled CLI-builder source is
[openclaw/mcporter v0.14.2](https://github.com/openclaw/mcporter/tree/aa0f55f9bffcde9d2070c86145f37d4dd3525f6c),
the accepted native bridge pin; builder verification remains an upgrade gate.

## D6 — retain the Serena dev pin; add only context hooks now

The CC keeps the recorded **c6fbd1c5932df2494ffa0020af5a9fbe80b82143**
(`2.0.0.dev0`) build, recorded in `adoption/new-wsl-profile.json`, rather than
downgrading to **v1.7.0**. The clean-release preference remains; this is the
documented exception needed for the native reset behavior. At v1.7.0,
`remind` denies one call per burst, and Codex Serena use does not reset it.
The installed dev build ships `serena-hooks reset`.

The latest D6 amendment restricts the quiet-window additions to these
**context-only** Codex hooks, both trusted at plan step 16:

- SessionStart, matcher `startup|resume`: `serena-hooks activate --client=codex`.
- SessionEnd: `serena-hooks cleanup --client=codex`.

This matches the ordered plan's context-only rule: added hooks produce no
deny, ask or updatedInput control effect. `remind` (PreToolUse Bash) and
`reset` (PostToolUse `^mcp__serena__.*$`) are **held** until step 19 proves
those events fire for nested code-mode calls. Reconsider them only in a dated
amendment after that evidence. Claude-side hooks wait for the CC's
role-enablement map `wf_1765cb57-995`.

Leave `statusMessage` and `timeout` out unless the exact
[Codex rust-v0.160.1 schema](https://github.com/openai/codex/tree/d27764b82f7118f674371e6d6e76271d9d606edb)
verifies the chosen fields: parser rejection can unload the shared hooks file,
including existing ai-memory hooks. Matching native hooks can run concurrently;
adding another input-control producer requires its own evidence.

Sources: [kept Serena source](https://github.com/oraios/serena/tree/c6fbd1c5932df2494ffa0020af5a9fbe80b82143),
[v1.7.0 hook implementation](https://github.com/oraios/serena/blob/v1.7.0/src/serena/hooks.py#L219),
and the vendor's
[client-hook documentation](https://github.com/oraios/serena/blob/2e1bdf524f634a66ab78c61f1a02deb57889c656/docs/02-usage/030_clients.md#L366)
and [changelog](https://github.com/oraios/serena/blob/2e1bdf524f634a66ab78c61f1a02deb57889c656/CHANGELOG.md#L114)
at **2e1bdf524f634a66ab78c61f1a02deb57889c656**. Alternatives are the older clean
release, the kept recorded dev revision, and a future clean release with
reset. Overturn the dev exception at the first clean release that ships
`reset`, then update accepted pins through `scripts/build_ecosystem.py` and
retain fresh functional/organic evidence. Neither the dev pin nor hooks change
in this documentation PR.

## Evidence and completion boundary

This is a dated CC decision record backed by pinned source review and
historical qualifications. It is not a new installation, measured context
comparison, trust grant, model run or whole-slot READY/exclusion. Step 7
supplies rollback backups; steps 18–19 supply application/read-back and
fresh-session/launcher evidence. The CC applies client changes after the
co-op's GPT read, CC ACK and the landing by the sole queued-PR writer.

Completeness review must preserve the D6 amendment, both context-budget
scopes and test constants, edited-agent update behavior, compound-hook/input
producer ordering, proxy quality and recovery, and the distinction between
zero observed calls and unknown coverage. These conditions feed the next
native token-tool sweep and cannot be closed by a version probe alone.
