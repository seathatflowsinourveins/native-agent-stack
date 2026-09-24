# Decision: `max` effort for every Claude child, Ultracode for the main loop (2026-09-23)

**Decided by:** unit `max-effort-default`, its own dedicated worktree, branch
`claude/max-effort-default-20260923` (first based on `origin/main@40828dfe`, later
rebased onto the current `main`), from the user's requirement of 2026-09-23: "effort max
and ultracode default for all future workflow and github, max quality". The user
expected one session to run `max` and Ultracode at the same time; the probes below
show that the native client does not allow that, so the requirement is met per layer
instead.

**Scope:**

- the shipped agent definitions (`adoption/agents/claude/*.md`; the five installer agents
  change here, and the two blind lane roles arrived at `max` with #145), all byte-identical
  to agent-lab's `.claude/agents/` copies at agent-lab `b31f640` (the `max` change is agent-lab
  #43; `source-scout`'s `maxTurns: 100` is agent-lab #46);
- a new committed project settings file for this repository (`.claude/settings.json`) and
  the coordinator rule in [`AGENTS.md`](../../AGENTS.md);
- the portable examples: [`examples/claude-native/CLAUDE.md`](../../examples/claude-native/CLAUDE.md),
  the agents in `examples/claude-native/agents/`, the saved workflows (`review-changes.js`,
  `readiness-audit.js`; the vendored `layer-verdict-lane.js` and its two blind roles are
  vendored at `max` by #145, not by this change), and their contract suites;
- the model/effort guidance in
  [`recipes/claude-native-ultracode.md`](../../recipes/claude-native-ultracode.md) and
  [`recipes/claude-native-profile.md`](../../recipes/claude-native-profile.md), and the
  `lean-workflow-child-routing` activation in `catalogs/foundation/decisions.json`.

The user-scope settings template (`adoption/templates/claude.settings.template.json`)
already carries `ultracode: true`, the `xhigh` effort defaults and no
`CLAUDE_CODE_EFFORT_LEVEL`; it needs no change. This record extends the
[Claude user profile decision](2026-09-23-claude-user-profile.md); its coordinator
choice (Opus 5.5 at `xhigh`) is unchanged.

## Evidence

**Probe method.** Research workflow `wf_3f4689fe-c86` ran headless probes P0 to P9, a
further probe H1 followed, and three more headless sessions ran Q1 to Q3 later the same
day, all with Claude Code 2.1.281, each in a fresh scratch directory, on the host whose user settings
carry `ultracode: true` and `modelSettings.claude-opus-5-5.effortLevel: "xhigh"`. The
user settings file's hash was the same before and after the probes. Each probe's
resolved effort, for the session and for each child, was read from its native
transcript. Ultracode was counted as active when the transcript carried the Ultracode
system reminder, whose text begins "Ultracode is on: optimize"; the unrelated
`/workflow-authoring` reference sentence "Ultracode is on for the session" was
excluded. The transcripts stay on the probing host (they hold local session
identifiers and paths) and are not published here.

| Probe | Configuration | Result |
| --- | --- | --- |
| P0 | Baseline: user `ultracode: true` plus the per-model `xhigh` | Session at `xhigh`; reminder present (1 line) |
| P1 | Environment `CLAUDE_CODE_EFFORT_LEVEL=max` | Session at `max`; reminder absent (0 lines) |
| P2 | `--effort max` | Session at `max`; reminder absent (0 lines) |
| P3 | `--settings` with `effortLevel: "max"` | Session at `xhigh`, no warning; reminder present. Confounded: see below |
| P4 | `--settings` with `modelSettings.claude-opus-5-5.effortLevel: "max"` | Session at `xhigh`, no warning; reminder present. Confounded: see below |
| P5 | Environment `max`; one default Agent child | Child `claude-opus-5-5` at `max` |
| P6 | Environment `max`; one `source-scout` child, frontmatter then `sonnet`/`medium` | Child `claude-sonnet-5` at `max`: the variable overrides frontmatter effort |
| P7 | Project `.claude/settings.json` with `effortLevel: "max"` | Session at `xhigh`, no warning; reminder present. Confounded: see below |
| P8 | Project `effortLevel: "max"` plus `ultracode: true` | Session at `xhigh`, no warning; reminder present. Confounded: see below |
| P9 | Environment `max`; one Workflow stage passing `effort: 'high'` | Stage at `max`: the variable overrides stage effort; reminder absent |
| Q1 | `--settings '{"ultracode":false,"effortLevel":"max"}'` | Session at `xhigh`, the user's per-model level, no warning; reminder absent: the `max` was dropped |
| Q2 | Control: `--settings '{"ultracode":false,"effortLevel":"high"}'` | Session at `high`; reminder absent: the key applies a valid value |
| Q3 | Default Ultracode parent at `xhigh` (reminder present); Workflow run `wf_45d3a3bd-6e6` with four stages | `{model: 'sonnet', effort: 'max'}`: `claude-sonnet-5` at `max`. `{agentType: 'source-scout', effort: 'max'}`, frontmatter `max`: Sonnet 5 at `max`. `{agentType: 'source-scout'}` with no stage effort, frontmatter `max`: Sonnet 5 at `max`. `{agentType: 'scout-medium', effort: 'max'}`, a copy whose frontmatter says `effort: medium`: Sonnet 5 at `max`, so the stage effort wins over the frontmatter |

H1 ran with the default Ultracode parent at `xhigh` (reminder present): a Workflow
stage that passed `effort: 'max'` ran at `max` (agent `a659fbb94398ea280`, label
`stage-max`); a stage with no `effort` and no agent type inherited `xhigh` (agent
`abd2b64f159add7c2`, label `stage-inherit`); an Agent whose frontmatter says
`effort: max` ran at `max`. In Q3 the four children were agents `adb4fe075ae1bd61d`,
`a3655d8bbcc4c8426`, `a21fd778630b97247` and `aee5ec9e1ff3c829e`, in the order of the
table row; the Q3 directory's project copy of `source-scout` (`effort: max`) won by name
over the user-level copy, which still said `medium`.

**What shows that a persisted `max` is dropped.** P3, P4, P7 and P8 ran under the
user's `ultracode: true` (P8 also set it in the project file), and Ultracode "takes
precedence over `effortLevel` and `modelSettings` entries"
([settings reference](https://code.claude.com/docs/en/settings-reference#ultracode),
fetched 2026-09-23). Those sessions would have run at `xhigh` whatever level was
persisted, so they are
consistent with a dropped `max` but cannot show it on their own. Q1 and Q2 are the
unconfounded evidence: with `ultracode: false` in the same `--settings` source,
`effortLevel: "high"` ran at `high` (Q2), and `effortLevel: "max"` ran at `xhigh`, the
level of the user's `modelSettings.claude-opus-5-5.effortLevel` (Q1), so `max` was
dropped and the next source decided. Q1 and Q2 cover the top-level key in the
`--settings` source; for the per-model key and a project settings file the evidence is
the installed schema and the docs below.

**Installed client.** The 2.1.281 binary's settings schema declares `effortLevel` and
`modelSettings.<model>.effortLevel` as
`z(["low","medium","high","xhigh"]).optional().catch(void 0)`, so any other value,
`"max"` included, is dropped without a warning (measured for the top-level key by Q1,
with Q2 as its control). The binary has no default-effort key for subagents or
workflow stages; `CLAUDE_CODE_SUBAGENT_MODEL` sets only a child's model.

**Official documentation** (fetched by the research workflow and again for this record
on 2026-09-23):

- [Model configuration](https://code.claude.com/docs/en/model-config): "Ultracode is a
  Claude Code setting rather than a model effort level: it sends `xhigh` to the model
  and additionally has Claude orchestrate dynamic workflows for substantive tasks."
  When `CLAUDE_CODE_EFFORT_LEVEL` "is set to a level other than `xhigh`, requests run at
  that level and ultracode's workflow orchestration stays inactive." On the settings
  keys: "`max` isn't accepted as a level in either key". On sessions: "Unless you set
  it through the `CLAUDE_CODE_EFFORT_LEVEL` environment variable, Claude Code applies
  `max` to the current session only." Frontmatter effort "applies when that skill or
  subagent is active, overriding the session level but not the environment variable."
  The `/effort` menu "also offers `ultracode`", beside the effort levels.
- The same page: `max` "may show diminishing returns and is prone to overthinking.
  Test before adopting broadly". The effort table lists `max` for Opus 5.5, Fable 5.1
  and Sonnet 5; a level the model lacks falls back to the highest supported level at
  or below it; models the table does not list, Haiku 4.5 among them, take no effort
  level.
- [Workflows](https://code.claude.com/docs/en/workflows): "In `claude -p` and the Agent
  SDK, Claude Code never shows this prompt. It runs the Workflow tool call through the
  same permission evaluation as the rest of the session"; a launch there needs a
  `Workflow` or `Workflow(<name>)` allow rule, auto or bypass permission mode, a
  `PreToolUse` hook that allows it, or the host's own approval. A run pauses at a
  claude.ai usage limit only when "The session is interactive and signed in with a
  claude.ai subscription"; "A run doesn't pause in non-interactive mode with `claude -p`
  or the Agent SDK, in a background session, or in a Remote Control or agent team
  teammate session."
- [Interactive mode](https://code.claude.com/docs/en/interactive-mode#wait-for-a-usage-limit-to-reset):
  "Automatic continue is on by default in interactive sessions signed in with a
  claude.ai subscription"; the session "re-arms the wait on its own at most twice in a
  row" and does not start a wait for a reset more than 24 hours away.

The platform effort documentation, as fetched by the research workflow, recommends an
effort sweep on your own evaluations for Opus 5.5; that page was not re-read for this
record.

**GitHub and cloud sessions.** No GitHub Actions workflow in agent-lab or in this
catalog invokes Claude (searched 2026-09-23). The `action.yml` of
`anthropics/claude-code-action`, read on 2026-09-23 at commit
`8cf3482550831fb35a4fc3fbf7ca139cf8028b4c`, has `settings` ("Claude Code settings as
JSON string or path to settings JSON file") and `claude_args` ("Additional arguments to
pass directly to Claude CLI") inputs and no `effort`, `ultracode` or `model` input; its
`base-action` runs Claude through the Agent SDK's `query()`
(`base-action/src/run-claude.ts` calls `runClaudeWithSdk`), so an action job is a
non-interactive Agent SDK run. The action itself was executed for this catalog only as
a 2026-09-23 CI smoke in a scratch repository (a smoke reply, an allow control, and a
settings-level deny rule passed through its `settings` input that produced one
permission denial; [gated items](../../catalogs/sota-convergence/sdk-runtime-coverage-20260922.md#gated-items-executed-2026-09-23)).
The [cloud-session settings documentation](https://code.claude.com/docs/en/settings#settings-in-cloud-sessions)
says a session with one repository reads that repository's committed
`.claude/settings.json`, while a session with several repositories reads only its
`enabledPlugins` and `extraKnownMarketplaces` keys. No Ultracode or effort run of the
action or of a cloud session was executed for this record.

## Decision

1. **The main loop stays at Ultracode everywhere** (`xhigh` plus dynamic workflow
   orchestration): the user-scope settings template as it is, and a new committed
   [`.claude/settings.json`](../../.claude/settings.json) in this repository: the
   [portable example](../../examples/claude-native/ultracode.settings.json)'s keys, as in
   agent-lab's committed project settings (`enableWorkflows`, `ultracode`, the
   `unrestricted` size guideline, the concurrency cap of eight and spawn depth one),
   merged with this repository's existing secret-read `permissions.deny` rules and
   secret-path guard hook,
   so single-repository cloud sessions on this repository start with it. It adds
   neither `effortLevel` (a `max` there is dropped: Q1, and the schema and docs for a
   project file) nor `CLAUDE_CODE_EFFORT_LEVEL`, which is never set at any value: any
   value overrides every child's own effort (the docs for frontmatter effort at any
   value; at `max`, P6 for frontmatter and P9 for a stage's effort), and any value
   other than `xhigh` also disables Ultracode (P1, docs). [`AGENTS.md`](../../AGENTS.md)
   tells the coordinator so.
2. **Every project agent and every saved workflow stage runs at `max`, with
   task-matched models kept:** Sonnet for `source-scout` and `isolated-builder`;
   Opus for `evidence-reviewer`, `semantic-evidence-reviewer`, `blind-judge` and the
   vendored lane's `blind-lane-reviewer`. The shipped definitions change only their
   frontmatter line to `effort: max` (H1 and Q3: frontmatter `max` runs at `max` under
   an Ultracode parent). Workflow scripts, saved and ad-hoc, pass `effort: 'max'` on
   every `agent()` call: a stage without its own effort inherits `xhigh` unless its
   agent's frontmatter sets one (H1, Q3), and a stage's effort overrides the
   frontmatter (Q3), so the stage literal decides.
3. **One non-orchestrated session at `max` stays available on request.**
   `claude --effort max` ran at `max` with orchestration off (P2). `/effort max` was
   not probed: the docs say Claude Code applies `max` to the current session only and
   list `ultracode` as a separate entry of the same menu. Neither persists.
4. **GitHub:** a future Actions workflow built on `claude-code-action` requests
   Ultracode with `claude_args: '--effort ultracode'` or the `settings` input
   `'{"ultracode": true}'`, and never puts `--effort max` in `claude_args` beside
   Ultracode, because an explicit `max` wins and turns orchestration off (P2). A job
   that should start workflows also needs a `Workflow` or `Workflow(<name>)` allow
   rule, auto or bypass permission mode, or a hook that allows the call, because its
   Workflow launches go through normal permission evaluation (workflows docs).

**Cost.** Children are expected to spend more output tokens than at `medium` or
`high`; neither that cost nor a quality gain has been measured yet. Nothing here caps
that cost: `autoContinueAtUsageLimit`, on in the settings template, only lets an
interactive session signed in with a claude.ai subscription, and a workflow run inside
it, wait for a usage limit to reset instead of failing (a reset within 24 hours, at
most twice in a row); `claude -p`, Agent SDK and so GitHub Actions runs and background
sessions fail at the limit (interactive-mode and workflows docs above). The setting
does not reduce usage. Record each run's per-child model, effort and usage with
`child-usage.mjs --latest` so the overturn comparison below has data.

## Alternatives considered

- **`CLAUDE_CODE_EFFORT_LEVEL=max` everywhere.** Rejected: it disables Ultracode
  orchestration for the main loop (P1) and forces every child to `max` regardless of
  its definition (P5, P6, P9), so no stage could ever be set lower on evidence.
- **Keep the task-matched efforts (Sonnet/medium, Opus/high).** Rejected: contrary
  to the user's requirement of `max` for all workflows.
- **`max` for reviewers and judges only.** Rejected: the user asked for all
  workflows, scouts and builders included.
- **Persist `max` through `effortLevel` or `modelSettings`.** Not available: the
  client drops the value without a warning (Q1, with Q2 as its control; the schema and
  docs for the per-model key).

## Overturn conditions

Revisit this record when any of these happens:

- a measured effort sweep on the comparison harness (agent-lab `tools/compare`)
  shows that `max` gives no quality gain over `xhigh` or `high` for a role at higher
  cost; that role returns to the cheaper effort;
- usage limits block work;
- a Claude Code release accepts `max` together with Ultracode orchestration; the main
  loop then moves to `max`;
- `max` overthinking is observed to regress a gated result.

## Limitations

- **Keep-but-compare.** The per-role qualifications in the Ultracode recipe and the
  examples were recorded at the earlier efforts; no run has compared `max` with them
  on the same tasks, and no saved workflow has run with the `max` literals yet.
- **One host, one release.** The probes ran once each, on one account, with Claude
  Code 2.1.281; a later release can change the schema or the interaction with
  Ultracode. Repeat the probe method above after an upgrade before relying on it.
- **Probe coverage.** Q1 and Q2 cover the top-level `effortLevel` key in the
  `--settings` source only; no unconfounded probe covered the per-model key or a
  project settings file. `/effort max` was not probed.
- **Not executed:** an Ultracode or effort run of `claude-code-action`, and cloud
  sessions (documentation and source only; the action's CI smoke above tested
  replies and a settings-level permission rule, not Ultracode or effort).
- **Released tags predate this change.** `v2026.09.23.1`, pinned since #148 and this
  record's first base, ships the five agent definitions at `medium`/`high`, so
  `adoption/bootstrap.md` marks them "changed after `v2026.09.23.1`". A host installing
  from that tag gets the `max` definitions after the next release and re-pin, or by
  running `tools/adoption/install_claude_profile.py --only agents` from a default-branch
  clone; the installer replaces any differing catalog-owned agent file.
- **Vendored lane.** The lane and its two blind roles are vendored at `max` by catalog #145
  (pinned at agent-lab `e070125`), not by this change; the pre-merge `915e73e` pin on an
  earlier revision of this branch never reached main. The review and readiness scripts and
  the `child-usage.mjs` mirror here are byte-identical to agent-lab `b31f640`.
