# Native Fable / Ultracode dispatch

This is a native Claude Code profile, not a separate orchestration framework.
The September 21, 2026 trial used installed Claude Code 2.1.278 and the existing
subscription. Fable 5.1 coordinated an actual Workflow with Sonnet 5 and Opus 5;
then the same coordinator resumed as a background session and completed a native
message round trip with a separate Sonnet session. See the
[dated results and gaps](../docs/native-ultracode-20260921.md).

## Start with the native profile

From the adopted project, using this repository's settings example at its real
location:

```sh
claude --settings /path/to/native-agent-stack/examples/claude-native/ultracode.settings.json
```

The portable [settings file](../examples/claude-native/ultracode.settings.json):

```json
{
  "enableWorkflows": true,
  "ultracode": true,
  "workflowSizeGuideline": "unrestricted",
  "env": {
    "CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS": "8",
    "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1"
  }
}
```

The example persists `enableWorkflows`, `ultracode`, the `unrestricted` advisory size
(each workflow sized to its task; it replaced `small` on 2026-09-21, see the
[routing guide](../docs/ultracode-token-routing-20260921.md)) and the per-workflow
concurrency setting of eight, which makes a large run queue rather than burst (the
bundled `/workflow-authoring` reference states the default cap as min(16, available
CPUs − 2) per workflow, and the official workflows doc says the setting overrides it
and accepts 1–256 from 2.1.269, so the formula is the default, not a limit. Eight
replaced three on 2026-09-21 on a 24-thread host after a 13-agent run, `wf_72e7aefc-8ad`
in agent-lab's `docs/native-token-workflow.md` cap table, completed at three without
provider or search-quota errors; no run has saturated eight. A new host starts at 8 and
raises only after `child-usage.mjs --latest` shows a full run with no rate-limit errors
or empty results), and `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`
so workflow and Agent children cannot fan out a second layer (the client default is
three layers; official sub-agents doc, fetched 2026-09-22). It does not select a model,
account or permission mode. To adopt it as a project default, merge only those
keys into the existing `.claude/settings.json`; preserve all unrelated settings.
Project environment settings require workspace trust, and organizational policy
or feature availability can still restrict the profile. The dated rules set behind
these values and the planned-workstation profile are in
[the convergence record](../docs/harness-rules-convergence-20260922.md) and
[the workstation profile](../docs/new-workstation-runtime-profile-20260922.md).

`ultracode: true` requests effective `xhigh` effort, subject to applicable caps,
and takes precedence over the stored `effortLevel` setting. Preserving that
stored value therefore does not mean effective effort is unchanged. Never set
`CLAUDE_CODE_EFFORT_LEVEL`: any value overrides every child's frontmatter and
workflow-stage effort, and any value other than `xhigh` also overrides Ultracode
and leaves its orchestration inactive
([below](#child-effort-max-under-an-ultracode-coordinator)). Ultracode is not a
provider model name. The size
guideline is advisory; the environment
variable provides a per-workflow concurrency setting, not a total account or
cross-session budget. Size by the task: solo for conversational or mechanical
turns; a scout plus review for a bounded change; one agent per independent unit
plus verification for multi-unit work; tens of agents only for an enumerated
work-list run through `pipeline()` with lean `agentType` stages. Never drop a
verification stage to save tokens; save them with lean agents, deferred lanes and
focused reads. Keep existing sign-in, permissions, plugins and caching.

For another host, inspect its CPU count and the available account/API
allowance first. Start at eight when the allowance supports it; otherwise use a
lower cap. The setting overrides the client's per-workflow default of
`min(16, CPUs - 2)` and accepts 1–256 (from 2.1.269), so that formula is the
default, not a ceiling; on a small host still write a positive setting that the
runtime can honour rather than a zero/negative one. Raise toward 12–16 only
after a complete run has no rate-limit errors, missing results or unintended
model substitutions. Preserve verification stages and
inspect `child-usage.mjs` results. This cap is per workflow: other workflows,
direct agents and native clients can share the same account quotas. Changing
concurrency does not request a different model/effort, but quality, wall time and
total cost still need observation. Do not infer improvement from the setting.

The dated trial explicitly used `--model fable --effort ultracode`; `fable`
resolved to `claude-fable-5-1` on that account. Verify the actually returned model
on another account/provider. The [subsequent native observations](../evidence/artifacts/native-claude-coop-20260921/persistent-profile.json)
retain fresh-session settings/role discovery and returned usage separately from
the interrupted cross-client attempt; they are not another PC's acceptance.

Since 2026-09-23 this profile is the default main loop for every session, not
only for substantial parallel work
([decision record](../docs/decisions/2026-09-23-max-effort-default.md)).
Ultracode orchestrates workflows only for substantive tasks, and the sizing rule
above keeps conversational and mechanical turns solo; a lower effort remains a
per-session `/effort` choice. Native Ultracode can increase tokens and elapsed
time; it is not a general token-saving switch. In a `-p` run, load this
opted-in settings file or pass `--effort ultracode`; the word in a prompt does
not enable the feature.
[Persistent settings](https://code.claude.com/docs/en/settings-reference#ultracode),
[native model configuration](https://code.claude.com/docs/en/model-config),
[workflow behavior](https://code.claude.com/docs/en/workflows).

## Assign models by task and verify the assignment

**2026-09-23: Opus 5.5 now leads this table.** The live host's coordinator
model is `claude-opus-5-5` (via `modelSettings.claude-opus-5-5.effortLevel:
xhigh`, since a USER-scope top-level `effortLevel` no longer covers Opus 5.5
and later; see `recipes/claude-native-profile.md`'s 2026-09-23 correction).
Fable 5.1 is the escalation path when a task specifically needs the prior
coordinator's demonstrated multi-agent-graph behavior (below) rather than the
new default.

**2026-09-23, later: every child role runs at `max` effort.** The coordinator
stays Opus 5.5 at Ultracode (`xhigh` plus dynamic workflow orchestration).
Every child keeps its task-matched model and requests `max`: Sonnet for scouts
and builders, Opus for reviewers and judges. Each child row's Qualification
below predates this change and was recorded at the earlier task-matched
efforts (Sonnet/medium, Opus/high). No run has compared `max` with those
efforts on the same tasks yet, so the effort choice stays keep-but-compare
until the sweep named in the
[decision record](../docs/decisions/2026-09-23-max-effort-default.md) runs.
The [section below](#child-effort-max-under-an-ultracode-coordinator) has
the measured constraints and the per-stage rule.

| Role | Starting choice | Qualification |
| --- | --- | --- |
| Requirements, decomposition, integration and hard judgments | Opus 5.5 at Ultracode (`xhigh` plus dynamic workflow orchestration), the default for every session; escalate to Fable 5.1 for a task needing its previously demonstrated graph-coordination behavior | Coordinator observed as Opus 5.5/xhigh on this host as of 2026-09-23; Fable 5.1/xhigh's own multi-agent-graph coordination (Sonnet 5 and Opus 5 workers) remains the escalation's own qualification below |
| Exact extraction, inventories, running acceptance commands | `source-scout` (Sonnet, max; four built-in tools, no project instructions) | First prompt 8,048 tokens versus 42,396 for the default child on one identical task; ran the inventory stage of eight native reviews and the readers of two readiness audits (one deployed, one in the scratch adoption); the recheck stage exists since the eighth review and ran there and in the three scratch-adoption reviews |
| Implementation from a clear contract | `isolated-builder` (Sonnet, max, own worktree, named MCP tools behind ToolSearch) | One real task: a manifest probe implemented, checked and committed from its own worktree (first prompt 17,864) |
| Independent review from source and recorded evidence | `evidence-reviewer` (Opus, max; read-only named MCP tools behind ToolSearch, no Bash/Edit/Write) | Eight native review runs; first prompt 12,164 for the deferred shape versus 42,220 with bare server grants |
| Review of supplied semantic (TypeSafe) judgments against original source | `semantic-evidence-reviewer` (Opus, max; Read, Glob and Grep, `typesafe-ai` skill preloaded) | One probe, `wf_20a5e69a-84d`, measured the skill preload (first prompt 15,059 tokens; [convergence record](../docs/harness-rules-convergence-20260922.md)); no quality comparison with another reviewer is recorded. The vendored layer-verdict lane no longer uses it (next row) |
| Proposing, refuting and re-checking one stripped layer-verdict packet | `blind-lane-reviewer` (Opus, max; Read, Glob and Grep, no preloaded skill, no project instructions) | Every stage of the vendored [layer-verdict lane](../examples/claude-native/workflows/layer-verdict-lane.js) names it (agent-lab `e070125`, vendored with the lane). A skill it preloaded could be one of the candidates a packet judges, and project instructions can name incumbent selections, so it carries neither; this catalog records no dated run of the lane with it |
| Judging or refuting one sealed comparison packet | `blind-judge` (Opus, max; Read only, no project instructions) | Its frontmatter was checked against the agent contract in the [convergence record](../docs/harness-rules-convergence-20260922.md); its body was not reviewed there, and this catalog records no dated run of the role |
| Cheap exact extraction | Haiku | Not routed: on one byte-identical packet the Opus verifier scored Sonnet 14/14 lane rows and Haiku 9/14 with a quote attributed to a file that does not contain it; overturn only after a repeat trial with no unanchored citation on two distinct packets. Haiku 4.5 takes no effort level, so `max` does not apply to it |
| Independent cross-family review | Existing official Codex companion | Reuse its separately recorded native acceptance; this trial did not run Codex inside a Workflow graph. Its reasoning effort follows the Codex configuration, not this table |

These are starting choices, not a universal quality ranking. Set worker model
and effort explicitly. Inspect native child metadata and returned model identity;
do not infer success from a role name. More expensive escalation requires an
uncertainty the task actually needs resolved.

Give each worker a concise task, relevant original sources, allowed effects and
return contract. Writers get owned worktrees; read-only task instructions do not
create an OS sandbox. Keep raw intermediate results in workflow variables and
return source-linked findings. Prefer small schemas with bounded fields over
word-count instructions that trigger repeated shell calls. Verify substantive
claims independently; preserve schema retries, nulls, failures and model
substitutions as incomplete results rather than filtering them into a pass.

Use the bundled `/workflow-authoring` skill when writing reusable workflow code.
For an interactive authoring session, start with the positional prompt
`claude --model fable --effort ultracode /workflow-authoring` and verify the native
skill reference was injected. Merely mentioning the skill in a prose task did
not invoke it in the later writing trial. Define permitted native workflow
metadata reads separately from owned source writes. Run acceptance commands
without output pipelines that mask their exit status.

The portable [saved workflow examples](../examples/claude-native/workflows/README.md)
are byte-identical copies of the deployed review and readiness scripts, the
[native agent definitions](../examples/claude-native/agents/), the per-child
usage extractor `child-usage.mjs`, the Codex bridge and their local checks (a
static contract suite, a mutation harness and receipt bindings driven by a sibling
`contract.config.json`). `review-changes` re-runs every acceptance command with a
second worker and compares both runs in code. Record each run's children with
`node .claude/workflows/child-usage.mjs --latest`.
Since 2026-09-23 the examples' agents and stages bind effort `max` with their
task-matched models unchanged (the review, readiness and layer-verdict scripts
are byte-identical to agent-lab `b31f640`; the max change is agent-lab #43), as do the shipped
[`adoption/agents/claude/`](../adoption/agents/claude/) definitions. Their
contract suite now fails a stage or agent at any other effort, a `MODEL` record
that differs from the stages it describes, a routing table that restates an
agent's effort differently, and a settings file that sets
`CLAUDE_CODE_EFFORT_LEVEL` or caps effort below `max`. The qualifications above
were recorded at the earlier efforts (Sonnet/medium, Opus/high).
Adopt selected files into a project's existing `.claude/` directories without
overwriting its instructions, accounts or permissions. A saved script is a
supported native extension, not an upstream-authored acceptance policy.
Review acceptance requires exact evidenced claim coverage and all requested
checks; readiness completion additionally accounts for every requested source.
An evidenced negative readiness audit can complete while the project remains
unready. Model agreement alone cannot establish correctness.

The [writing and recovery qualification](../docs/native-workflow-writing-recovery-20260921.md)
records a Sonnet implementation, Opus review, selected-worker failure, graceful
coordinator exit and same-session resume. Both writing arms produced accepted
code, but the comparison retained process-contract failures and the worker arm
used more tokens for the small repair. Recovery preserved edits made while
stopped; its native and persisted usage totals did not fully reconcile. Keep
these boundaries when selecting this profile.

The native `/workflows` view shows stages, agents, tokens and returned results.
Save a useful script from that view into the selected project's `.claude/workflows/`
or the user's workflow directory, then `/reload-skills` when needed. Do not
publish live host paths or save a one-off audit as a universal project workflow.

### Child effort: `max` under an Ultracode coordinator

Measured on 2026-09-23 with Claude Code 2.1.281 in headless probes, each started
in a fresh directory; the probes left the user settings file unchanged. The
[decision record](../docs/decisions/2026-09-23-max-effort-default.md) lists each
probe and its result.

- **`max` disables Ultracode orchestration.** Ultracode sends `xhigh` to the
  model and additionally has Claude orchestrate dynamic workflows; any other
  resolved effort, `max` included, leaves orchestration inactive. Sessions
  started with `--effort max` or `CLAUDE_CODE_EFFORT_LEVEL=max` ran at `max`
  and had no Ultracode system reminder (P1, P2), so one session cannot have
  both.
- **`max` cannot be persisted.** With `--settings
  '{"ultracode":false,"effortLevel":"max"}'` the session ran at `xhigh`, the
  level of the user's per-model `modelSettings` entry, with no warning: the
  `max` was dropped and the next source decided (Q1). The control with
  `"effortLevel":"high"` ran at `high`, so the key applies a valid value (Q2).
  The earlier probes that put `max` in `effortLevel` or
  `modelSettings.<model>.effortLevel` (`--settings` or a project
  `.claude/settings.json`: P3, P4, P7, P8) also stayed at `xhigh`, but they ran
  with `ultracode: true`, which takes precedence over both keys, so on their
  own they cannot show the drop. For the per-model key and a project file the
  evidence is the installed schema, which accepts only `low`, `medium`, `high`
  and `xhigh` in both keys, and the official docs: `max` "isn't accepted as a
  level in either key" and otherwise applies to the current session only.
- **`CLAUDE_CODE_EFFORT_LEVEL` overrides every child's effort.** With it set
  to `max`, a default Agent child, a `source-scout` whose frontmatter then said
  `sonnet`/`medium` and a workflow stage that passed `effort: 'high'` all ran
  at `max` (P5, P6, P9), and the docs say frontmatter effort overrides the
  session level "but not the environment variable". Never set it: any value
  erases every per-agent and per-stage effort, and any value other than
  `xhigh` also turns Ultracode off.

Under the default Ultracode coordinator (`xhigh`, orchestration active), a
workflow stage that passed `effort: 'max'` ran at `max` on Opus 5.5 (H1) and on
Sonnet 5 (Q3); a stage naming an agent whose frontmatter says `effort: max`
ran at `max` with or without its own `effort: 'max'` (Q3; H1 saw the same for
an Agent-tool child); a stage that
passed `effort: 'max'` to an agent whose frontmatter says `effort: medium` ran
at `max`, so the stage's effort wins over the frontmatter (Q3); and a stage
with neither inherited `xhigh` (H1). The installed binary has no
default-effort key for subagents or workflow stages
(`CLAUDE_CODE_SUBAGENT_MODEL` sets only the model), so name the effort
wherever a child is defined:

- every project agent declares `effort: max` in its frontmatter beside its
  task-matched `model` (the shipped [agent definitions](../adoption/agents/claude/)
  and the [examples](../examples/claude-native/agents/) do);
- every saved workflow stage and every ad-hoc `agent()` call in a workflow
  script passes `effort: 'max'` together with an explicit `model`: a stage
  without its own `effort` inherits the coordinator's `xhigh` unless its agent's
  frontmatter sets one, and the stage's effort also overrides a lower
  frontmatter;
- a single non-orchestrated session at `max` stays available on request:
  `claude --effort max` ran at `max` with orchestration off (P2). `/effort max`
  was not probed; the docs say Claude Code applies `max` "to the current
  session only" and list `ultracode` as a separate entry of the `/effort` menu
  ([model configuration](https://code.claude.com/docs/en/model-config), fetched
  2026-09-23).

The docs list `max` for Opus 5.5, Fable 5.1 and Sonnet 5 (the probes observed
it on Opus 5.5 and Sonnet 5); a model without it falls back to its highest
supported level, and Haiku 4.5 takes no effort level. The
official docs warn that `max` "may show diminishing returns and is prone to
overthinking" and advise testing before adopting it broadly. Children are
expected to spend more output tokens, and no sweep has measured that cost or a
quality gain yet. `autoContinueAtUsageLimit` (on in the settings template) is
not a cost control and does not reduce usage: it lets an interactive session
signed in with a claude.ai subscription, and a workflow run inside it, wait for
a usage limit to reset (a reset within 24 hours, at most twice in a row) instead
of failing. `claude -p`, Agent SDK and GitHub Actions runs and background
sessions get no wait and fail at the limit
([interactive mode](https://code.claude.com/docs/en/interactive-mode#wait-for-a-usage-limit-to-reset),
[workflows](https://code.claude.com/docs/en/workflows#when-a-run-hits-your-usage-limit),
both fetched 2026-09-23).

## GitHub and cloud sessions

No GitHub Actions workflow in this catalog invokes Claude. For a future one
built on `anthropics/claude-code-action` (its `action.yml` and `base-action`
source read on 2026-09-23 at commit `8cf3482550831fb35a4fc3fbf7ca139cf8028b4c`):
the action has no `effort`, `ultracode` or `model` input, and `base-action`
runs Claude through the Agent SDK's `query()`, so a job is a non-interactive
Agent SDK run. Request Ultracode through `claude_args: '--effort ultracode'` or
the `settings` input `'{"ultracode": true}'`, and never put `--effort max` in
`claude_args` beside Ultracode: an explicit `max` wins and turns orchestration
off. In `claude -p` and Agent SDK runs Claude Code shows no workflow approval
prompt; a Workflow launch goes through the session's normal permission
evaluation, so it starts only under a `Workflow` or `Workflow(<name>)` allow
rule, auto or bypass permission mode, or a hook that allows the call
([workflows](https://code.claude.com/docs/en/workflows#approve-the-plan-before-it-runs),
fetched 2026-09-23). Such a job fails at a usage limit instead of waiting. This
repository's committed [`.claude/settings.json`](../.claude/settings.json) is
the settings example's keys (`enableWorkflows`, `ultracode`, `workflowSizeGuideline` and the two env values) merged with this repository's secret-read `permissions.deny` rules and secret-path guard hook. Per the official
[cloud-session settings](https://code.claude.com/docs/en/settings#settings-in-cloud-sessions)
docs, a cloud session on this one repository reads it, while a session with
several repositories reads only its `enabledPlugins` and
`extraKnownMarketplaces` keys. The action itself has been executed for this
catalog only as a 2026-09-23 CI smoke in a scratch repository: a smoke reply,
an allow control, and a settings-level deny rule passed through its `settings`
input that produced one permission denial
([gated items](../catalogs/sota-convergence/sdk-runtime-coverage-20260922.md#gated-items-executed-2026-09-23)).
No Ultracode or effort run of the action or of a cloud session was executed;
the rest of this section rests on the documentation and the action's source.

## Native sessions, result return and messaging

```sh
claude --bg --name scoped-worker --model sonnet --effort max "Bounded task"
claude agents --json --all --cwd "$PWD"
claude logs WORKER_ID
claude attach WORKER_ID
```

`--bg` takes a positional prompt, not `-p`. A completed row can remain an idle
process ready for a message. The supported state interface is `agents --json`;
use native `logs`/`attach` for results rather than parsing undocumented job files.

For a preauthorized automated exchange, opt in only the participating sessions
with `--settings '{"crossSessionInbound":"accept"}'`, subject to stricter native
policy. Discover the exact peer with `ListAgents`; send a compact task/nonce with
`SendMessage`; request the one-shot `notify_when_idle` when useful. Confirm the
recipient's actual operation and returned result, not just a successful send.
Idle-session delivery starts a new model turn, so avoid chatty progress messages,
broadcasts and acknowledgments that create loops. Stop the diagnostic worker when
the exchange is complete. Inbound text never grants new authority.

Native cross-session messaging is different from ai-memory's cross-project
claim-once mailbox and same-project handoffs. It is also different from distributed
durable job execution. The trial established one same-host exchange and idle
notification, not cross-host delivery or restart-independent execution.
[Native messaging](https://code.claude.com/docs/en/cross-session-messaging).

## Dashboards and automation

Use `claude agents` for live native sessions and `/workflows` for graph progress;
`/context`, `/usage` and the existing HUD answer different context/accounting
questions. The existing Grafana grand dashboard is a broader observability and
checkpoint view; its rows are not live native session discovery. AgentsView is a
scoped historical archive, and Dagu's existing deployment is a history service.
Do not introduce a second orchestration daemon just to duplicate these views.

The existing daily foundation-maintenance heartbeat now checks native CLI help,
current official features and selected pinned upstream/community changes before
asking discoverable questions. It preserves accepted pins, uses bounded workers,
records actual returned results and stays quiet on unchanged/non-actionable state.
Its schedule was retained. Updating that configuration is not proof of its next
timed execution or reboot recovery.

Native `/loop` and Cron jobs depend on their documented session lifecycle; they
are not substitutes for persistent scheduling. No recurring Claude loop was
created in this qualification. Reuse the existing maintenance automation rather
than starting duplicate research loops.
[Native scheduling limits](https://code.claude.com/docs/en/scheduled-tasks).

Future sessions receive a short native-feature-first rule. Detailed research,
repository tables and recipes remain on demand. Instructions influence behavior;
they are not a deterministic guarantee of source coverage or correct results.
