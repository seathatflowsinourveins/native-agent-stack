# Decision: `max` effort for every Claude child, Ultracode for the main loop (2026-09-23)

**Decided by:** unit `max-effort-default`, its own dedicated worktree, branch
`claude/max-effort-default-20260923` (base `origin/main@40828dfe`), from the user's
requirement of 2026-09-23: "effort max and ultracode default for all future workflow
and github, max quality". The user expected one session to run `max` and Ultracode at
the same time; the probes below show that the native client does not allow that, so
the requirement is met per layer instead.

**Scope:** the five shipped agent definitions (`adoption/agents/claude/*.md`, kept
byte-identical to agent-lab's `.claude/agents/` copies, which receive the same
one-line change), a new committed project settings file for this repository
(`.claude/settings.json`), the model/effort guidance in
[`recipes/claude-native-ultracode.md`](../../recipes/claude-native-ultracode.md) and
[`recipes/claude-native-profile.md`](../../recipes/claude-native-profile.md). The
user-scope settings template (`adoption/templates/claude.settings.template.json`)
already carries `ultracode: true`, the `xhigh` effort defaults and
`autoContinueAtUsageLimit: true`, and no `CLAUDE_CODE_EFFORT_LEVEL`; it needs no change.
This record extends the [Claude user profile decision](2026-09-23-claude-user-profile.md);
its coordinator choice (Opus 5.5 at `xhigh`) is unchanged.

## Evidence

**Probe method.** Research workflow `wf_3f4689fe-c86` ran headless probes P0 to P9
with Claude Code 2.1.281, each in a fresh scratch directory, on the host whose user
settings carry `ultracode: true` and `modelSettings.claude-opus-5-5.effortLevel:
"xhigh"`. The user settings file's hash was the same before and after the probes.
Each probe's resolved effort, for the session and for each child, was read from its
native transcript. Ultracode was counted as active when the transcript carried the
Ultracode system reminder, whose text begins "Ultracode is on: optimize"; the
unrelated `/workflow-authoring` reference sentence "Ultracode is on for the
session" was excluded. The transcripts stay on the probing
host (they hold local session identifiers and paths) and are not published here.

| Probe | Configuration | Result |
| --- | --- | --- |
| P0 | Baseline: user `ultracode: true` plus the per-model `xhigh` | Session at `xhigh`; reminder present (1 line) |
| P1 | Environment `CLAUDE_CODE_EFFORT_LEVEL=max` | Session at `max`; reminder absent (0 lines) |
| P2 | `--effort max` | Session at `max`; reminder absent (0 lines) |
| P3 | `--settings` with `effortLevel: "max"` | Session at `xhigh`, no warning; reminder present |
| P4 | `--settings` with `modelSettings.claude-opus-5-5.effortLevel: "max"` | Session at `xhigh`, no warning; reminder present |
| P5 | Environment `max`; one default Agent child | Child `claude-opus-5-5` at `max` |
| P6 | Environment `max`; one `source-scout` child, frontmatter then `sonnet`/`medium` | Child `claude-sonnet-5` at `max`: the variable overrides frontmatter effort |
| P7 | Project `.claude/settings.json` with `effortLevel: "max"` | Session at `xhigh`, no warning; reminder present |
| P8 | Project `effortLevel: "max"` plus `ultracode: true` | Session at `xhigh`, no warning; reminder present |
| P9 | Environment `max`; one Workflow stage passing `effort: 'high'` | Stage at `max`: the variable overrides stage effort; reminder absent |

A further probe, H1, ran with the default Ultracode parent at `xhigh` (reminder
present): a Workflow stage that passed `effort: 'max'` ran at `max` (agent
`a659fbb94398ea280`, label `stage-max`); a stage with no `effort` inherited `xhigh`
(agent `abd2b64f159add7c2`, label `stage-inherit`); an Agent whose frontmatter says
`effort: max` ran at `max`.

**Installed client.** The 2.1.281 binary's settings schema declares `effortLevel` and
`modelSettings.<model>.effortLevel` as
`z(["low","medium","high","xhigh"]).optional().catch(void 0)`, so any other value,
`"max"` included, is dropped without a warning (P3, P4, P7, P8). The binary has no
default-effort key for subagents or workflow stages; `CLAUDE_CODE_SUBAGENT_MODEL`
sets only a child's model.

**Official documentation** ([model configuration](https://code.claude.com/docs/en/model-config),
fetched by the research workflow and again for this record on 2026-09-23):

- "Ultracode is a Claude Code setting rather than a model effort level: it sends
  `xhigh` to the model and additionally has Claude orchestrate dynamic workflows for
  substantive tasks." When `CLAUDE_CODE_EFFORT_LEVEL` "is set to a level other than
  `xhigh`, requests run at that level and ultracode's workflow orchestration stays
  inactive."
- On the settings keys: "`max` isn't accepted as a level in either key". On
  sessions: "Unless you set it through the `CLAUDE_CODE_EFFORT_LEVEL` environment
  variable, Claude Code applies `max` to the current session only."
- `max` "may show diminishing returns and is prone to overthinking. Test before
  adopting broadly".
- The effort table lists `max` for Opus 5.5, Fable 5.1 and Sonnet 5; a level the
  model lacks falls back to the highest supported level at or below it; models the
  table does not list, Haiku 4.5 among them, take no effort level.

The platform effort documentation, as fetched by the research workflow, recommends
an effort sweep on your own evaluations for Opus 5.5; that page was not re-read for
this record.

**GitHub and cloud sessions.** No GitHub Actions workflow in agent-lab or in this
catalog invokes Claude (searched 2026-09-23). The `action.yml` of
`anthropics/claude-code-action` at `8cf3482550831fb35a4fc3fbf7ca139cf8028b4c`
(committed 2026-09-23) declares 39 inputs, among them `settings` ("Claude Code
settings as JSON string or path to settings JSON file") and `claude_args`
("Additional arguments to pass directly to Claude CLI"), and no `effort`,
`ultracode` or `model` input. The
[cloud-session settings documentation](https://code.claude.com/docs/en/settings#settings-in-cloud-sessions)
says a session with one repository reads that repository's committed
`.claude/settings.json`, while a session with several repositories reads only its
`enabledPlugins` and `extraKnownMarketplaces` keys. Neither the action nor a cloud
session was run for this record.

## Decision

1. **The main loop stays at Ultracode everywhere** (`xhigh` plus dynamic workflow
   orchestration): the user-scope settings template as it is, and a new committed
   [`.claude/settings.json`](../../.claude/settings.json) in this repository, byte
   for byte the [portable example](../../examples/claude-native/ultracode.settings.json)
   and agent-lab's committed project settings (`enableWorkflows`, `ultracode`, the
   `unrestricted` size guideline, the concurrency cap of eight and spawn depth one),
   so single-repository cloud sessions on this repository start with it. It adds
   neither `effortLevel` (a `max` there is dropped, P7 and P8) nor
   `CLAUDE_CODE_EFFORT_LEVEL` (any value other than `xhigh` disables Ultracode, and
   `max` there overrode every child's effort: P1, P5, P6 and P9).
2. **Every project agent and every saved workflow stage runs at `max`, with
   task-matched models kept:** Sonnet for `source-scout` and `isolated-builder`;
   Opus for `evidence-reviewer`, `semantic-evidence-reviewer` and `blind-judge`.
   The five shipped definitions change only their frontmatter line to
   `effort: max` (H1: frontmatter `max` runs at `max` under an Ultracode parent).
   Ad-hoc workflow scripts pass `effort: 'max'` on every `agent()` call, because a
   stage without it inherits `xhigh` (H1).
3. **One non-orchestrated session at `max` stays available on request:**
   `claude --effort max` or `/effort max`. Either turns Ultracode off for that
   session (P2 measured the flag; `/effort max` picks `max` in place of the
   `ultracode` entry of the same menu), and neither persists.
4. **GitHub:** a future Actions workflow built on `claude-code-action` requests
   Ultracode with `claude_args: '--effort ultracode'` or the `settings` input
   `'{"ultracode": true}'`, and never puts `--effort max` in `claude_args` beside
   Ultracode, because an explicit `max` wins and turns orchestration off (P2).

**Cost.** Children are expected to spend more output tokens than at `medium` or
`high`; neither that cost nor a quality gain has been measured yet.
`autoContinueAtUsageLimit` stays on in the settings template. Record each run's
per-child model, effort and usage with `child-usage.mjs --latest` so the overturn
comparison below has data.

## Alternatives considered

- **`CLAUDE_CODE_EFFORT_LEVEL=max` everywhere.** Rejected: it disables Ultracode
  orchestration for the main loop (P1) and forces every child to `max` regardless of
  its definition (P5, P6, P9), so no stage could ever be set lower on evidence.
- **Keep the task-matched efforts (Sonnet/medium, Opus/high).** Rejected: contrary
  to the user's requirement of `max` for all workflows.
- **`max` for reviewers and judges only.** Rejected: the user asked for all
  workflows, scouts and builders included.
- **Persist `max` through `effortLevel` or `modelSettings`.** Not available: the
  client drops the value without a warning (P3, P4, P7, P8).

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

- **Keep-but-compare.** The per-role qualifications in the Ultracode recipe were
  recorded at the earlier efforts; no run has compared `max` with them on the same
  tasks.
- **One host, one release.** The probes ran once each, on one account, with Claude
  Code 2.1.281; a later release can change the schema or the interaction with
  Ultracode. Repeat the probe method above after an upgrade before relying on it.
- **Not executed:** `claude-code-action` and cloud sessions (documentation and
  source only).
- **Dated examples unchanged.** `examples/claude-native/agents/` and the saved
  workflow examples keep the efforts they were qualified at, and their contract
  suite pins those values; the Ultracode recipe says how to raise them when
  adopting.
- **Released tags predate this change.** `v2026.09.23` has no
  `adoption/agents/claude/`, and `v2026.09.23.1` (this record's base commit) ships the
  five definitions at the earlier `medium`/`high` efforts. A host installing from
  either tag gets the `max` definitions only after the next release and re-pin, or by
  running `tools/adoption/install_claude_profile.py` from a checkout that has this
  change. The installer refreshes any differing catalog-owned agent file, so a host
  that already installed the earlier copies gets the `max` versions on a re-run.
