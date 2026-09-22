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
    "CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS": "3"
  }
}
```

The example persists `enableWorkflows`, `ultracode`, the `unrestricted` advisory size
(each workflow sized to its task; it replaced `small` on 2026-09-21, see the
[routing guide](../docs/ultracode-token-routing-20260921.md)) and the per-workflow
concurrency setting of three, which makes a large run queue rather than burst. It does not select a model,
account or permission mode. To adopt it as a project default, merge only those
keys into the existing `.claude/settings.json`; preserve all unrelated settings.
Project environment settings require workspace trust, and organizational policy
or feature availability can still restrict the profile.

`ultracode: true` requests effective `xhigh` effort, subject to applicable caps,
and takes precedence over the stored `effortLevel` setting. Preserving that
stored value therefore does not mean effective effort is unchanged. An existing
`CLAUDE_CODE_EFFORT_LEVEL` value other than `xhigh` overrides Ultracode and leaves
its orchestration inactive. Ultracode is not a provider model name. The size
guideline is advisory; the environment
variable provides a per-workflow concurrency setting, not a total account or
cross-session budget. Size by the task: solo for conversational or mechanical
turns; a scout plus review for a bounded change; one agent per independent unit
plus verification for multi-unit work; tens of agents only for an enumerated
work-list run through `pipeline()` with lean `agentType` stages. Never drop a
verification stage to save tokens; save them with lean agents, deferred lanes and
focused reads. Keep existing sign-in, permissions, plugins and caching.

The dated trial explicitly used `--model fable --effort ultracode`; `fable`
resolved to `claude-fable-5-1` on that account. Verify the actually returned model
on another account/provider. The [subsequent native observations](../evidence/artifacts/native-claude-coop-20260921/persistent-profile.json)
retain fresh-session settings/role discovery and returned usage separately from
the interrupted cross-client attempt; they are not another PC's acceptance.

Use this profile for substantial parallel work. Routine work stays at ordinary
effort. Native Ultracode can increase tokens and elapsed time; it is not a general
token-saving switch. In a `-p` run, load this opted-in settings file or pass
`--effort ultracode`; the word in a prompt does not enable the feature.
[Persistent settings](https://code.claude.com/docs/en/settings-reference#ultracode),
[native model configuration](https://code.claude.com/docs/en/model-config),
[workflow behavior](https://code.claude.com/docs/en/workflows).

## Assign models by task and verify the assignment

| Role | Starting choice | Qualification |
| --- | --- | --- |
| Requirements, decomposition, integration and hard judgments | Fable, Ultracode for substantial graphs | Coordinator observed as Fable 5.1/xhigh |
| Exact extraction, inventories, running acceptance commands | `source-scout` (Sonnet, medium; four built-in tools, no project instructions) | First prompt 8,048 tokens versus 42,396 for the default child on one identical task; ran the inventory stage of eight native reviews and the readers of two readiness audits; the recheck stage exists since the eighth review and ran there and in the three scratch-adoption reviews |
| Implementation from a clear contract | `isolated-builder` (Sonnet, medium, own worktree, named MCP tools behind ToolSearch) | One real task: a manifest probe implemented, checked and committed from its own worktree (first prompt 17,864) |
| Independent review from source and recorded evidence | `evidence-reviewer` (Opus, high; read-only named MCP tools behind ToolSearch, no Bash/Edit/Write) | Eight native review runs; first prompt 12,164 for the deferred shape versus 42,220 with bare server grants |
| Cheap exact extraction | Haiku | Not routed: on one byte-identical packet the Opus verifier scored Sonnet 14/14 lane rows and Haiku 9/14 with a quote attributed to a file that does not contain it; overturn only after a repeat trial with no unanchored citation on two distinct packets |
| Independent cross-family review | Existing official Codex companion | Reuse its separately recorded native acceptance; this trial did not run Codex inside a Workflow graph |

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
three [native agent definitions](../examples/claude-native/agents/), the per-child
usage extractor `child-usage.mjs`, the Codex bridge and their local checks (a
static contract suite, a mutation harness and receipt bindings driven by a sibling
`contract.config.json`). `review-changes` re-runs every acceptance command with a
second worker and compares both runs in code. Record each run's children with
`node .claude/workflows/child-usage.mjs --latest`.
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

## Native sessions, result return and messaging

```sh
claude --bg --name scoped-worker --model sonnet --effort medium "Bounded task"
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
