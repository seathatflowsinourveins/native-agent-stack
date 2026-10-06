# Native RTK hook evidence and Claude launcher matching (2026-10-06)

This is a review proposal for P2-9 and P3-12, accompanying the P0-3 repairs in
drafts #779 and #775. It does not change a client configuration, trust hash,
permission rule or installed executable. The command center owns application
after the co-op's GPT read and its ACK. North-star action: let fresh native
sessions complete engineering and research work with countable token tools
and the client's intended permission semantics.

## P2-9: prove native firings before changing wiring

Installed Codex is **0.160.1**, upstream
[`d27764b82f7118f674371e6d6e76271d9d606edb`](https://github.com/openai/codex/releases/tag/rust-v0.160.1).
RTK is **0.51.0**, upstream
[`e001f773f80b22b7dc4c7a79521b30e35aaef026`](https://github.com/rtk-ai/rtk/releases/tag/v0.51.0).
Version/help, version-matched release notes, pinned source and official client
references were checked in that order. The Codex patch release's Windows MCP
environment backport is not a hook fix. Historical 0.160.0 census source and
the 10-04 qualification's **0.159.3 scratch-home run** remain distinct evidence.
The qualification's hard-coded legacy gateway port is not current organic
acceptance and must not be replayed as such.

The command-center census reports 82 all-time RTK decision-log sessions and
none attributable to its 511 Codex rollouts. Those different populations are
not a hook firing rate. RTK's
[`run_codex`, hook_cmd.rs:994-1029](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/hook_cmd.rs#L994)
does not invoke the SQLite
[`log_hook_decision`, :737-759](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/hook_cmd.rs#L737).
It optionally audits rewrite/skip outcomes and silently ignores other inputs.
The empty SQLite comparison therefore establishes a logging gap, not that the
Codex hook never fired.

Configuration-nonmutating native discovery finds the enabled PreToolUse/Bash RTK hook, with
hooks enabled and its current normalized configuration hash trusted. The
maintained `tools/adoption/codex_hook_trust.py --command 'rtk hook codex'
--check --cwd <owned-worktree>` returns **0** and reports every named hook
trusted. No trust or configuration repair is justified by that check alone.
The helper's normal app-server diagnostic lifecycle is not model inference.
Its documented dry-run starts app-server and can create normal Codex-home
state files (SQLite, installation identity and bundled skills); it is not a
filesystem-read-only check. It makes no trust/config edit or backup.

**Selected upstream lever for RTK decision countability:** reuse RTK's existing
SQLite logger in the native Codex handler, as it already does for Claude.
Codex 0.160.1's
[`pre_tool_use.rs:175-190`](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/hooks/src/events/pre_tool_use.rs#L175)
emits flat `session_id`, `tool_use_id` and `cwd` fields, exactly matching RTK's
[`hook_log_fields`, :723-727](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/hook_cmd.rs#L723).
The current Rewrite/Skip branches discard their classified decision through
`..`; an upstream change can bind it and invoke the existing best-effort
logger, preserving stdout, permission controls and the optional audit behavior.
No new client, runner, parallel observer or capture setting is needed for
that source-backed gap. Propose it in maintained `rtk-ai/rtk`, then adopt only
a reviewed pinned upstream revision through CC/F9.

Native upstream regression gates must exercise Codex-shaped Rewrite and Skip
inputs in an isolated tracker database; retained session/tool identity,
decision and rewrite data must match, while stdout/exit and existing Claude
behavior remain unchanged. Missing IDs, malformed/Ignore inputs and tracker
failure retain native best-effort behavior. Classified decision rows still
do **not** equal all hook firings: Ignore remains unlogged. Use count/status
queries without printing private stored command data. This change is a
proposal, not a current patch, installed fix or measured AFTER.

The native
[`tracking.rs:712-747 INSERT`](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/core/tracking.rs#L712)
does not deduplicate. Report raw decision rows, distinct native session/tool
identities and duplicate/conflicting outcomes separately. A Rewrite row is a
classifier/dispatch decision, not proof that the rewritten command executed;
join a qualified native terminal command observation by the same identity
before claiming confirmed execution. Missing identities or ambiguous joins
stay unknown. Existing upstream temporary `RTK_DB_PATH` fixtures and Cargo
tests provide the regression seam, avoiding a custom runner or redirected home:

```text
cargo test test_hook_log_fields
cargo test test_codex_
cargo test test_record_and_lookup_hook_decision_by_tool_use_id
cargo test --test hook_decision_protocol_test
```

These are proposed upstream checks, not tests executed by this lane.

Adoption also requires a native contention/timeout comparison: RTK's
[`tracker busy timeout`](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/core/tracking.rs#L1712)
is five seconds, and Codex
[`awaits hook-process completion`](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/hooks/src/engine/command_runner.rs#L269).
Writing stdout first does not alone preserve tool latency. Compare unchanged
output/permissions, native completion latency and cancellation under a locked
scratch tracker; a material delay or timeout blocks this adoption and reopens
the supported capture alternative. No such regression or passing contention
test is claimed here.

The fixed before census remains `[2026-10-05T06:05:00Z,
2026-10-06T06:05:00Z)`: 12 registered roots and their native descendants,
8,062 command items and 6,947 leading RTK prefixes. A separate read-only
request/result feasibility check of that same window discovers 539 rollout
files at its later snapshot, 10,822 code-mode `exec_command` spans and **zero
observable direct raw shell request/result pairs**. Consequently, confirmed
rewrites remain **unknown**, not zero. The command-center's 8,728/9,327
prefix observations have a different scope and are not added to this table.

For broader hook-run evidence, Codex's
[`rollout/src/policy.rs:193-194`](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/rollout/src/policy.rs#L193)
excludes HookStarted/HookCompleted persistence. Its public
[`HookStartedNotification` and `HookCompletedNotification`](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/app-server-protocol/src/protocol/v2/hook.rs#L145)
carry thread/turn attribution and a native run summary. Use that upstream
surface prospectively if the owning client integration can observe it without
replacing the maintained runner or competing for its notification stream.
`source_path` plus `display_order` can join an in-memory hooks/list definition
to the native run summary; publish only the verified processor class, native
lifecycle/status and counts, not paths, commands, entries or failure text.

The native
[`run_id()`](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/hooks/src/engine/mod.rs#L158)
is `event_name:display_order:source_path`, stable per configured hook. It is
**not a unique invocation ID**: deduplicating firings by that ID across calls
would lose legitimate executions. Native
[`running_summary`](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/hooks/src/engine/dispatcher.rs#L78)
preserves those fields. Count actual completion notifications once within a
single observer stream and retain failure/blocked/stopped outcomes separately.
Do not reconstruct completions from persisted rollout items or sum start and
completion notifications. An unobservable stream stays unknown.

P0-3 preserves native `codex.hooks.run` dimensions and Claude hook outcome
fields, but `hook_name` in that metric is a lifecycle label. Approval-decision
`source` names an approval origin. Neither identifies RTK or proves a rewrite.
The new dashboard explicitly keeps these units separate. Live read-back and
every-lane processor attribution remain acceptance gates after actual apply.

The existing first-party SDK integration
[`examples/omniroute-codex-sdk/worker.py`](../../examples/omniroute-codex-sdk/worker.py)
is concurrently owned by draft #773. Do not edit it here. Hand off a bounded
native notification-observer proposal to that owner through the co-op; use
only public supported SDK interfaces and preserve its returned native results,
timeouts, interrupts and shutdown. Its SDK dependency is 0.160.0; an explicitly
selected host CLI 0.160.1 is a separate revision. All later bounded GPT jobs
must use the current gateway's **21128** endpoint. No new runner, private SDK
collector call, additional dependency, capture setting or model job is added
by this proposal.

At SDK 0.160.0 (`a956835d020762cb2b570053af06f643a11c0ecc`), public
[`AsyncCodexClient.request`](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python/src/openai_codex/async_client.py#L132)
can issue typed `hooks/list`; native
[`HookMetadata1`](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python/src/openai_codex/generated/v2_all.py#L8277)
contains event/source-path/order, enabled/trust state and command metadata.
There is **no safe drop-in background observer around unchanged `turn.run()`**:
[`stream()` and `run()`](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python/src/openai_codex/api.py#L879)
consume the same per-turn stream, and
[`next_notification()`](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python/src/openai_codex/client.py#L394)
excludes active-turn events. A parallel global reader would miss them. The
owner can qualify an optional public low-level branch in the existing worker,
using one per-turn consumer and native `thread_read(include_turns=True)` for
terminal-item fidelity. Do not copy the private collector, reach into the
high-level client's private transport or consume the stream then call run.
This is an implementation lead, not an accepted adapter or a license to
replace native orchestration. This SDK alternative does not observe existing
interactive CLI lanes by itself. It is secondary to the RTK logger proposal
for every-lane RTK decisions and remains owned by #773.

Codex 0.160.1
[`should_emit_hook_notification`](https://github.com/openai/codex/blob/d27764b82f7118f674371e6d6e76271d9d606edb/codex-rs/core/src/hook_runtime.rs#L875)
restricts those notifications to non-builtin synchronous hooks. Record that
coverage, configuration identity, timeouts/cancellation and missing terminal
events explicitly. Observed native runs still do not prove rewrite decisions.
Before filling any AFTER row, record a coverage row for that exact lane and
launcher: client/source revision, observer epoch, reload boundary, gaps,
matched native identity and eligible event classes. Uncovered CLI periods,
asynchronous/builtin hooks, timeouts and missing terminal events stay unknown.

## P3-12: upstream exact-match parity

The affected native client is **Claude Code 2.1.291**, not Codex execpolicy.
The current RTK native dry-run gives:

| Native check input | Exit | Diagnostic verdict |
| --- | ---: | --- |
| `rtk hook check --agent claude 'env -u FOO python3 -V'` | 1 | Denied by a permission rule |
| `rtk hook check --agent claude 'env'` | 1 | Denied by a permission rule |
| `rtk hook check --agent claude 'FOO=1 python3 -V'` | 1 | No rewrite; not denied |

All three have empty stdout. The exit code alone does not distinguish a
denial from no rewrite. No command printed an environment value. The
command-center's 34 env-launcher cases among 60 Claude RTK denials are a
separate census population, not an added count in the Codex before table.

Pinned RTK
[`permissions.rs:434-435`](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/permissions.rs#L434)
matches a wildcard-free Bash specifier by equality **or a word-boundary
prefix**. Thus `Bash(env)` matches the benign unset launcher above. Claude's
[official permission reference](https://code.claude.com/docs/en/permissions#use-specifiers-for-fine-grained-control)
(checked 2026-10-06) documents wildcard-free Bash specifiers as exact command
matches. Its [precedence rule](https://code.claude.com/docs/en/permissions#manage-permissions)
also prevents a narrower allow from overriding a matching deny. This source
comparison establishes an RTK/client contract mismatch; the official current
documentation is not a source dump or black-box test of Claude's binary.

Proposed upstream change: route **Claude-origin** wildcard-free Bash rules
through its native exact-command contract. RTK's
[`shared permission entry point`](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/permissions.rs#L47)
also receives other hosts' rules; do not globally alter their matcher without
version-matched parity evidence for each affected host. Keep explicit wildcard/legacy
prefix forms and rule precedence, including bare `env` denial. This belongs
in maintained `rtk-ai/rtk`, with its native permission tests; do not vendor a
local fork or patch the installed binary. A pinned upstream release and
native regression evidence gate any later adoption. The command center still
reviews the original permission intent and owns any permission-rule change.

Acceptance must compare unchanged native cases before/after: bare `env`
remains denied; `env -u FOO python3 -V` is not denied by the exact-only rule;
an explicit broad `Bash(env *)` retains its documented scope; compound commands,
wrapper normalization and existing permission tests retain native behavior.
Permission parity is not authorization for a command. Assigning `FOO=1` or
an empty value does not reproduce unsetting a variable, so a guidance-only
assignment substitution does not repair the launcher contract.

Alternatives rejected: a blanket allow loses the existing rule intent and
cannot override a deny; deleting or broadening a host guard is not this lane's
authority; changing Codex execpolicy targets the wrong client; avoiding all
unset launchers leaves the demonstrated mismatch. Keep the live restriction
until the upstream fix or a reviewed source-backed CC alternative is applied.

## Evidence gates and overturn conditions

| Claim | Evidence class | Gate / limit |
| --- | --- | --- |
| Current RTK trust check returns 0 | local_integration | Maintained helper; no firing proof or model run |
| Codex handler omits SQLite decision writes | source_review | Exact RTK pin and handler/logger paths above |
| Existing before counts and observability gap | local_integration | Fixed native-item census; request/result coverage separately stated |
| Native notification identity and persistence | source_review | Codex 0.160.1 protocol/engine/policy above |
| Claude launcher rejected by current RTK matcher | native_proven | Installed RTK dry-run diagnostics above; no fresh model task |
| Exact-match repair is a candidate | source_review | Upstream native tests and release needed; no installed fix |
| Organic hook firings, rewrites and after improvement | pending | Actual live revision/reload plus fresh matched observation |

Overturn the P2 logger proposal if a maintained native release already logs
those Codex decisions, the payload identity contract differs at the adopted
pin, or upstream native regressions show output/permission behavior changed.
The SDK capture alternative is secondary. Overturn that alternative if a supported existing native facility
already supplies complete per-lane processor attribution, or if an unchanged
upstream harness shows the capture misses/duplicates native runs. A new native
trust/discovery failure would justify a bounded wiring fix; the present green
check does not. Overturn the P3 matcher proposal if version-matched native
Claude evidence establishes prefix semantics, or an upstream parity comparison
shows regression in intended denials. A later chosen tool, selected-owner
regression or superior upstream-harness A/B remains an overturn condition for
the original owner/exclusion study; none of these operational counts qualifies
an exclusion.

The before table is retained. Add after rows only for actually live reviewed
source/trust/configuration revisions, with a fresh window, unchanged registry
rules and qualified task opportunity. A native dry-run, synthetic Collector
fixture or newly rendered panel does not fill the organic-after column.
