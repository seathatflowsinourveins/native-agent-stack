# Decision: Claude Code native practice, 2026-10 (client 2.1.295)

Date: 2026-10-09. Lane: foundation. Status: decided by evidence under the command center's rulings of 2026-10-09;
repository record awaiting review. Producer: session cc-native-practice.

## Context

The last practice review ([2026-09-28 community sweep](2026-09-28-community-sweep.md)) was made at Claude Code 2.1.283.
Since then 1,031 CHANGELOG entries landed (2.1.284 to 2.1.295), and the owner asked (2026-10-09, paraphrased) for the
Claude-native layer to end as one evidenced default per role slot that every future session starts from. During the
review the owner added three directions (each paraphrased, 2026-10-09): cover every starred repository and the
research-converged SOTA repositories, not only the listed ones (about 03:41Z); quality comes first and budget is not
the limit, with token efficiency practised through architecture and measured routing only (about 03:44Z, restated
about 05:2xZ); and judge GitHub automation on its own SOTA quality, not on security alone (about 05:0xZ). This record
paraphrases those directions and quotes no message.

## Decision

1. **One default per role slot.** The 33 role slots, their defaults, ranked alternatives, rejections and overturn
   conditions live with the [`claude-native-practice` skill](../../.claude/skills/claude-native-practice/SKILL.md)
   ([index](../../.claude/skills/claude-native-practice/reference/slots.md)); the table under
   [Decided defaults](#decided-defaults) is this record's dated copy. A native Claude Code 2.1.295 feature is the
   default wherever it covers the slot; no third-party framework is adopted over native features.
2. **The quality bar.** A token or cost saving becomes a default only with quality parity measured on our own tasks:
   paired same-task runs scored by an upstream harness (promptfoo 0.124.0 or the skill-creator benchmark) with a blind
   judge and exact checks. Token counts alone never decide. Every token-efficiency row below is either a native
   default with no quality loss claimed, or pending that measurement.
3. **GitHub automation** follows the official requirements in [GitHub automation](#github-automation-against-official-practice);
   the open workflow pull requests carry the deltas.
4. **The practice stays current** through the weekly pass in [Refresh loop](#refresh-loop), owned by the currency lane.
5. **Sessions reach the practice on demand** through the skill, which carries the defaults with it; no always-loaded
   text changes.

## Method and evidence

| Stage | What ran | Result |
| --- | --- | --- |
| Pins | Installed client `claude --version` 2.1.295 and its `--help`; `anthropics/claude-code` tag v2.1.295 = `602df92bf481ed904533e95c09f740f40aab5aed`, CHANGELOG.md sha256 `c0b1f9aa313a8021d863ec0053c047b0acc792d74e04af9c7741d3ecd23c3d1a`; 7 anthropics and 15 listed community repositories at full SHAs (2026-10-09T03:18:36Z); claude-code-action v1.0.247 = `2dca132ff0e0c4094ce6048b422c6915a071210b` | [research manifest](../../evidence/artifacts/claude-native-practice-20261009/research-manifest.json) |
| Inventory | 5 read-only Sonnet 5.5 scouts over origin/main, the named PR heads and the host's configuration (names only) | 19 areas of our state with locators |
| GPT family | Codex research lanes through the co-op: L1 official behaviour, L2 community convergence and framework ranking, L3 claude-code-action, L4a and L4b landscape (every G5 row in the Claude-native layers and all 368 starred repositories), L5 GitHub automation | 236 official claims (153 current, 82 changed since 2.1.283, 1 unverified), 61 community practices, 42 repositories graded, 8 action requirements, 2,583 entries screened, 59 deep reads, 9 automation slots |
| Claude family | A blind Opus 5.5 selection per slot group that did not open the GPT returns; Opus judges verifying every default under the version, scope and integrity lenses; blind adjudication of each disagreement with a second adjudicator refuting each judgment | 83 lens verdicts: 19 stand, 64 stand with corrections, none refuted (417 decision claims, 39 corrected); 11 disagreements adjudicated; 10 judgments upheld by their refuter, and one refuted for a misstated citation with the default unchanged ([verification.json](../../evidence/artifacts/claude-native-practice-20261009/verification.json)) |
| Third selection | The owner's session's landscape sweep, `research/api-surfaces-20261008/FINAL.md` on the producing host (corrected bytes, sha256 `17b1489725f0cb403b8f8d838fe20b0cc79375c926288c20daa3320b7a00ed12`) | Converged per slot where it overlaps |
| Audit | A third, independent audit of the five Claude workflow heads with the trailofbits agentic-actions-auditor skill, plus a measured symlink probe on 2.1.295 | 0 P0, 0 P1, 1 P2 mitigated by measurement, 5 P3 to the owning lane |
| Handoff proof | skill-creator `run_eval.py` trigger evaluation, 10 queries times 3 runs, on both descriptions; six fresh `claude -p` sessions in a checkout of this branch, none told to use the skill | 30 of 30 correct on each description; the skill was the first tool call in 5 of 6 sessions, 4 of 6 then read its slots page whole and a fifth grepped it (per-run excerpts: launch command, request, Skill arguments, every read from the skill directory) |

Claude-family spend, priced at API list price from each run's own usage record (`usage_record.py`): inventory $2.57,
blind selection $30.66, verification $62.46, adjudication at least $38.44, the actions audit $5.34, fresh-session
proofs $3.61 and the symlink probe $0.05; about $143 in all. The GPT lanes ran on the Codex pool. The owner's
direction made quality, not budget, the limit; every run above $5 was announced to the command center first.

Every claim the page cites resolves, with its locators, in
[claims.json](../../evidence/artifacts/claude-native-practice-20261009/claims.json): a repository file at a full SHA
with lines, a CHANGELOG line at the v2.1.295 tag, a documentation URL with its fetch time and the sha256 of the bytes
read, or a read-only installed-client command.

## Capability matrix

Official claim ids (`<area>-O<n>`) and community ids (`<area>-C<n>`) resolve in claims.json. "Changed" names entries of
2.1.284 to 2.1.295 that change practice.

| Area | Official behaviour at 2.1.295 | Community convergence | Our state | Gap | Decision (slot) |
| --- | --- | --- | --- | --- | --- |
| Memory | CLAUDE.md imports, `.claude/rules` `paths:`, auto memory (memory-O1 to O13). Changed: rules also load on Write, Edit and single-file Bash views (O7, 2.1.293); MEMORY.md markup neutralized (O9, 2.1.284) | Under 200 lines; file-specific text in scoped rules (memory-C1, 3 families) | Root CLAUDE.md imports AGENTS.md (8 lines); one scoped trading rule; auto-memory index 24 lines | No recorded auto-memory policy; AN-12 exclusion unapplied | instruction-files, auto-memory |
| Settings and permissions | Precedence managed > --settings > local > project > user; deny-first in every mode (settings-permissions-O1 to O19). Changed: auto start mode for unconfigured interactive sessions (O7, 2.1.285); dangerous rm under bypass prompts (O16) | Scoped rules or auto mode; bypass only when isolated (C1) | Host bypass by owner choice; template 134 denies, host 138 | Guard files uncovered by deny rules under bypass | settings-permissions, config-managers |
| Sandbox | Bash-only sandbox; strictAllowlist user or managed only (sandbox-O1 to O8). Changed: project settings cannot loosen an admin-required sandbox (O7) | Start restricted and widen by observed need (sandbox-C1) | No sandbox configured | Bypass on bare WSL2 | sandbox (trial) |
| Hooks | Events, matchers, handler types (hooks-O1 to O14). Changed: `onFailure: "block"` (O9, 2.1.295) | Narrow deterministic hooks tested against fixtures (hooks-C1, 3 families) | Guard with onFailure; template wrapper exits 0 when the script is missing | Floor 2.1.284 ignores onFailure | hooks |
| Skills | Nested discovery and lazy load; `<dir>:<name>` on clash (skills-I1; CHANGELOG L7339, L4303); Codex reads `.agents/skills` from the project root to its working directory only (skills-I2). Changed: allowed-tools grants last the turn (skills-O3, 2.1.295); `verify` skill guidance (O9, 2.1.286) | Precise descriptions and on-demand references (skills-C1, 7 sources) | 28 pinned vendor skills; 32 skillOverrides in the template | Content default awaits a blinded comparison | skills-library, commands |
| Subagents and teams | Frontmatter fields, priority, nesting (subagents-teams-O1 to O17). Changed: skills preload up to 32 (O2); per-call effort (O3, 2.1.292) | Explicit ownership and isolation (subagents-teams-C1, 4 sources) | 11 checked-in definitions; 4 host copies drift | Host drift (G6b) | subagent-definitions, agent-teams |
| Background and Workflows | Workflows resume from the journal; background supervisor (background-workflows-O1 to O10) | One loop authority; Workflow for ordered handoffs (C1, C2) | Saved workflows only as repository examples | Not at a native discovery location | background-workflows |
| Plugins | Plugin-level `sha` pins; marketplace sources take `ref` (plugins-marketplaces-O1 to O15) | Native marketplaces, individual plugins (C1) | Tags or no ref on our marketplaces | No catalog-owned marketplace.json | plugin-marketplaces |
| Output styles | Built-in and custom styles (output-styles-O1 to O9) | Choose a style for the behaviour wanted (C1) | Templates Default; owner's checkout Concise | No measurement for Concise | output-styles |
| Commands | Custom commands merged into skills (slash-commands-O1 to O13) | Skills or commands for repeated procedures (C1) | Skills only | None | commands |
| MCP | Tool search defers tools; 25,000-token output cap; alwaysLoad (mcp-O1 to O11). Changed: 2026-07-28 protocol by default for stdio (O7); 16,384-character tool descriptions (O6) | Selective servers, native deferral (mcp-C1); no measured shared-process default (C4) | User-scope registrations; drift host versus template | Shared servers unmeasured on the Claude side | mcp-config-tool-search, mcp-shared-servers |
| Status line | JSON on stdin; refreshInterval; subagentStatusLine (statusline-O1 to O9) | Local JSON-stdin command (C1) | Host node launcher; template glob wrapper | Two forms; renderer runs with full access | statusline |
| Checkpoints | 100 most recent checkpoints; cleanupPeriodDays default 30 (checkpoints-rewind-O1 to O8) | Rewind plus Git for risky edits (C1) | cleanupPeriodDays 3650 | Long plaintext retention | checkpoints-rewind |
| Headless and SDK | `-p` skips trust; `--bare` never reads OAuth; `--restricted` (headless-sdk-O1 to O18). Changed: bare sessions connect only command-line MCP (O3, 2.1.286); `-p` start mode can be auto (O12, 2.1.285) | Print mode with explicit output contract (C1); bare only after its auth route is qualified (C3) | Two call sites without fences | HOST-07 `--bare` unusable on OAuth | headless-sdk |
| Model and effort | Aliases, per-model effort, advisor (model-effort-O1 to O18). Changed: Sonnet 5.5 and Haiku 5.5 defaults (O2); Ultracode is a separate toggle (O6, 2.1.284); Agent `effort` (O7, 2.1.292) | Task-class routing asserted, not measured (model-effort-C1 to C9) | Explicit model and effort per role | M7 sweep owed | model-effort-routing |
| Context and tokens | Auto-compaction, TTL buckets, output bounds (context-token-O1 to O19). Changed: window saved per model (O3, 2.1.288); compaction retraction fixed (O16, 2.1.293) | Stable prefixes (C2); compression tools report token reductions without quality parity (C3 to C5) | No overrides; context-mode, rtk, headroom installed | No quality-parity record for compression | context-compaction, prompt-caching, output-compression |
| Cost and usage | OTel metrics and events; /usage (cost-usage-O1 to O12) | Separate token buckets from priced cost (C1, C2) | OTel flows to Prometheus, Loki, Grafana | Cost coverage depends on provider | usage-cost-monitoring |
| Scheduling | Session tasks expire after 7 days, no catch-up (scheduling-O1 to O11) | Session loops for temporary work, durable schedulers otherwise (C1) | systemd user timers for durable jobs | No Claude run under systemd tested | scheduled-tasks |
| GitHub Actions | See [GitHub automation](#github-automation-against-official-practice) (github-actions-A1 to A10) | Separate review and triage; findings-only by default (github-actions-C1, C2) | Harness audit on main; five workflow PRs open | R4 hardening folded | github-action, pr-review-pre-cue |

## Supersession

Each row names the earlier practice, what replaced it and what changes here. The full set of baseline rows the GPT
family reconciled (257, of which 102 changed) is in [supersession.json](../../evidence/artifacts/claude-native-practice-20261009/supersession.json).

| Practice | Source and date | Superseded by | Source and date | What changes for us |
| --- | --- | --- | --- | --- |
| Eight required checks including validate-macos | [2026-10-02 automation record](2026-10-02-github-automation-practice.md) | Seven required checks | [macOS CI advisory](2026-10-05-macos-ci-advisory.md), 2026-10-05; live ruleset 23739774 read 2026-10-09 | Dated addendum added to the 2026-10-02 record |
| HOST-07: `--bare` outside trusted checkouts | harness-rules convergence, 2026-09-22 | `--restricted` with `--permission-prompts none` and `--strict-mcp-config` on OAuth hosts | headless.md and `claude --help` at 2.1.295; measured: `--bare` drops Glob and Grep and never reads OAuth | headless-sdk route |
| `ultracode: true` runs at xhigh; any other effort level turns Ultracode off (R52) | 2026-09-28 sweep | Ultracode is an independent `/effort` toggle | CHANGELOG 2.1.284 (model-effort-O6) | model-effort-routing |
| `sonnet` resolves to Sonnet 5 | 2026-09-28 sweep (AN-05) | `sonnet` is Sonnet 5.5, `haiku` is Haiku 5.5 | CHANGELOG 2.1.284 and 2.1.293 (model-effort-O2) | Role table aliases resolve to 5.5 models |
| Compact earlier with a percentage override (M3, consensus topic) | 2026-09-28 sweep | Native window, saved per model; no override | CHANGELOG 2.1.288 (context-token-O3) | context-compaction |
| Global 1-hour cache TTL (R59, consensus topic) | 2026-09-28 sweep | Native TTL buckets by request type | prompt-caching.md, 2026-10-09 | prompt-caching |
| Raise `MAX_MCP_OUTPUT_TOKENS` (consensus topic) | 2026-09-28 sweep | Oversized results saved to a file and replaced by its path | mcp.md (mcp-O3) | mcp-config-tool-search |
| Recurring session tasks last 3 days | shanraisshan guide (R5) | 7 days, no catch-up | scheduled-tasks docs; scheduling-C2 marked superseded | scheduled-tasks |
| `claude -p --timeout` | community examples (R73) | Not a flag at 2.1.295 | `claude --help` (headless-sdk-O16) | Bound jobs with `--max-turns` and `--max-budget-usd` |
| Guard hooks fail open on errors | 2026-10-08 guard record before 2.1.295 | `onFailure: "block"` | CHANGELOG 2.1.295 (hooks-O9) | Floor and wrapper proposal (below) |
| Marketplace commit pins (M8 question) | 2026-09-24 and 2026-09-28 sweeps | `sha` only on plugin sources; marketplaces take `ref` | marketplace reference and `marketplace add --help` at 2.1.295 | plugin-marketplaces |
| Status-line git cost premise (M14) | claude-hud 0.8.0 | claude-hud 0.10.0 runs different git calls | claude-hud source at its pin | statusline |
| Auto-memory index about 22 KB per call | [2026-10-04 dispatch record](2026-10-04-coordinator-dispatch-and-spend.md) | About 3 KB (24 lines) | inventory 2026-10-09 | auto-memory |
| Output style Concise "declined" | upstream-surface-dispositions.json | Not measured; pending M19 | this review | Disposition text to correct (catalog owner) |
| claude-code-action v1.0.245 on main | harness-audit.yml at origin/main | v1.0.247 | action release 2026-10-08; all five open heads | Lands with #892 |

## Decided defaults

Status values: default, default (scoped), recommendation (owner's choice), trial, pending.

| Slot | Layer | Status | Default |
| --- | --- | --- | --- |
| `client-core` | native-clients | default | Native installer build on the latest auto-update channel (`autoUpdatesChannel` unset or `latest`) |
| `instruction-files` | native-clients | default (scoped) | `CLAUDE.md` that imports `@AGENTS.md`, Claude-only lines below the import, and `paths:`-scoped `.claude/rules` |
| `auto-memory` | native-clients | default (scoped) | Native auto memory on, in the default directory, with `MEMORY.md` kept as a short index |
| `settings-permissions` | native-clients | default (scoped) | Native layered settings (managed > `--settings` > local > project > user) with deny-first rules |
| `config-managers` | native-clients | default | Native settings layering as the profile and provider switch |
| `hooks` | native-clients | default (scoped) | Settings command hooks, with `onFailure: "block"` on each guard hook entry |
| `statusline` | native-clients | default (scoped) | Native `statusLine` (command and `refreshInterval`), fed the session JSON |
| `checkpoints-rewind` | native-clients | default (scoped) | Native checkpointing (`/rewind`, Esc Esc) with Git as the permanent history |
| `sandbox` | isolation | trial | Hardened native Bash sandbox, delivered through `claude --settings` or managed settings |
| `worktrees` | isolation | default (scoped) | Coordinator-created worktree at the exact base (`git worktree add --no-track <path> -b <branch> <base>`), with the session started in it |
| `model-effort-routing` | native-clients | recommendation (owner's choice) | Native per-role model and effort: subagent and skill frontmatter, the Agent tool's `model` and `effort` (2.1.292+), per-model `modelSettings`, and `--model`/`--effort` on headless jobs |
| `context-compaction` | token-efficiency | default | Native auto-compaction at the model's default window, with `/compact <focus>` at natural breaks, `/clear` between unrelated tasks and a Compact Instructions section in CLAUDE.md |
| `prompt-caching` | token-efficiency | default | Native automatic prompt caching with the default TTL buckets and no TTL overrides |
| `output-compression` | token-efficiency | default (scoped) | Native output bounds and delegation: `BASH_MAX_OUTPUT_LENGTH`/`bashOutputMaxChars` (30,000 characters by default), MCP results over 25,000 tokens saved to a file, filtering hooks, and subagents for large reads |
| `skills-library` | instructions-skills | default | Native Agent Skills at personal scope, filled from the pinned vendor manifest (adoption/skills/manifest.json) and governed by `skillOverrides`, `skillListingBudgetFraction` and `/skill-doctor` |
| `plugin-marketplaces` | instructions-skills | default (scoped) | Native marketplaces with commit-pinned plugin sources (plugin-level `sha`), the official marketplace first |
| `output-styles` | instructions-skills | default (scoped) | Built-in Default output style in the repository templates |
| `commands` | instructions-skills | default | Skills (`SKILL.md`) as the only surface for custom slash commands |
| `practice-references` | instructions-skills | default | Pinned, read-only practice-reference catalog with a weekly freshness check; primary sources first, community guides as leads |
| `subagent-definitions` | workers | default (scoped) | File-based subagent definitions at project scope (`.claude/agents`), installed to `~/.claude/agents` by the profile installer |
| `agent-teams` | workers | default (scoped) | Native agent teams, used only where workers must message each other |
| `background-workflows` | workers | default (scoped) | Dynamic Workflows (Workflow tool; saved workflows in `.claude/workflows` or `~/.claude/workflows`) |
| `orchestration-frameworks` | workers | default | Native composition without a framework layer: subagent definitions, Workflows, agent teams, background sessions and cross-session messaging |
| `planning-persistence` | workers | default | Repository-resident task state per Anthropic's multi-context-window guidance (a JSON status file, free-text progress notes and git commits, read at session start), with native plan mode for the plan |
| `loops-completion` | workers | default | Native Stop hook as the completion gate, with `/goal` and the self-paced `/loop` for fitting conditions |
| `scheduled-tasks` | scheduling-supervision | default | systemd --user timers with oneshot services for durable host-local runs (a bounded headless command, `claude -p` with explicit settings when a model is needed) |
| `mcp-config-tool-search` | mcp-surfaces | default | Native MCP configuration with tool search at its default (tools deferred), default output caps and `alwaysLoad` unset |
| `mcp-shared-servers` | mcp-surfaces | trial | One vendor-native Streamable HTTP service per heavy MCP server, admitted one server at a time after a PSS before/after and tool-surface parity check |
| `headless-sdk` | agent-sdks | default (scoped) | `claude -p` with every fence on the command line |
| `github-action` | git-github-automation | default | anthropics/claude-code-action at commit 2dca132ff0e0c4094ce6048b422c6915a071210b (v1.0.247) |
| `pr-review-pre-cue` | git-github-automation | default | pr-review-toolkit pre-cue (pr-test-analyzer and silent-failure-hunter): locally in J8 and in Actions through #909 |
| `release-tracking` | ci-supply-chain | default | Scheduled trackers: catalog-freshness.yml (daily read-only report plus a Monday proposal PR), practice-references-freshness.yml (weekly, report-only), the host's upstream surface watch (six sources: npm dist-tags, the Agent SDK settings types, the settings reference, env vars and mods, the Codex release, the CHANGELOG delta), plus Dependabot for action versions |
| `usage-cost-monitoring` | observation-inference | default | Native OpenTelemetry export (claude_code.* metrics and events) into the local collector, Prometheus, Loki and Grafana |

Routes, ranked alternatives, rejections, evidence, notes and overturn conditions per slot are in the skill's layer pages; this table is the dated copy of the decision.

## GitHub automation against official practice

Lane ccnp-l3-action read `anthropics/claude-code-action` v1.0.247 (commit `2dca132ff0e0c4094ce6048b422c6915a071210b`,
which bundles Claude Code 2.1.295) and GitHub's own documentation against `main` and the five open workflow pull
requests (#892, #894, #895, #896, #909), requirement by requirement. Its return holds 409 retained captures.

| Requirement | Official source at the pin | State | Delta |
| --- | --- | --- | --- |
| R1 Full-SHA action references | GitHub's security hardening guide; the action pins its own setup actions by SHA | All 155 `uses:` in 23 main workflows are full SHAs. `harness-audit` on main pins v1.0.245 (`6fed3ca1`); every open head pins v1.0.247 (`2dca132f`) | None; main moves to v1.0.247 when #892 lands |
| R2 Workload identity federation only | `anthropic_federation_rule_id`, `anthropic_organization_id` and `id-token: write`; a static `anthropic_api_key` or `claude_code_oauth_token` takes precedence and disables federation | Main and every head supply federation inputs and no static Anthropic credential | None |
| R3 No secrets on fork pull requests | GitHub withholds secrets from fork `pull_request` runs, while `pull_request_target` and `workflow_run` run in the base context; the action's write-permission gate; `allowed_bots` bypasses that gate | Main's audit has schedule and dispatch triggers only; the heads are dispatch-only or variable-gated, keep the default gate and leave `allowed_bots` empty | None |
| R4 No debug output on this public repository | `ACTIONS_STEP_DEBUG=true` forces full SDK output whatever `show_full_output` says (`base-action/src/parse-sdk-options.ts:195-196`); `runner.debug` reflects step debugging only; the retained `execution_file` holds unredacted messages | Every head pins `ACTIONS_STEP_DEBUG: 'false'` on the action step, sets `show_full_output: false` and keeps `execution_file` private; the pre-auth guard did not see debug settings made as repository secrets or variables | Folded on 2026-10-09 at #892 `0be47ac7`, #894 `a1bc3bc7`, #895 `f5f1fd22`, #896 `e1ba3bb3`, #909 `b80a6eb8`: the guard binds `(secrets.X \|\| vars.X) == 'true'` for both flags and refuses before any token (hardening; the full-output path was already closed) |
| R5 Least privilege | Job-scoped `GITHUB_TOKEN`; an explicit `github_token` skips the independently exchanged App token; `persist-credentials: false` | Empty workflow permissions; per-job grants; explicit token; checkout without persisted credentials | None |
| R6 Review and triage flows | The action ships PR review, security review and triage examples; `--model` and `--effort` are CLI arguments; prompt caching is on unless disabled | Main's audit leaves effort implicit; the heads pass `--model` and `--effort` explicitly | None beyond #892 |
| R7 Release tracking | Scheduled workflows run from the default branch; Dependabot updates declared action dependencies | 147 of 148 adopted repositories have a declared scheduled tracker (`catalog-freshness.yml` daily, `practice-references-freshness.yml` weekly, `runtime-worker-skills-freshness.yml`, Dependabot); `pandas-dev/pandas` has none | Recorded; execution success of the trackers was not checked |
| R8 Rulesets | Rulesets can require checks from one integration, resolved threads, linear history and code scanning, with bypass actors per ruleset | Ruleset 23739774: seven required checks, strict off, resolved threads, CodeQL (errors, high or higher), linear history, no bypass actors | None |

Main's required checks are seven. The eight-check list of
[the 2026-10-02 GitHub automation record](2026-10-02-github-automation-practice.md) was superseded on 2026-10-05 by
[the macOS CI advisory record](2026-10-05-macos-ci-advisory.md); this change adds a dated addendum there.

### Automation slots beyond the action

Lane ccnp-l5-automation ranked each slot's candidates on their own repository quality and preregistered a paired
output-quality run on our real pull-request deltas for every slot we run (the runs themselves are model-backed and
come later). Prior decisions stand unless a preregistered run beats them.

| Slot | Default | Ranked alternatives | Measurement | Status |
| --- | --- | --- | --- | --- |
| PR review | pr-review-toolkit pre-cue (row `pr-review-pre-cue`) | native `/code-review max`; qodo-ai/pr-agent; gh-aw review agent | Four arms scored on J8's confirmed findings and J7 class D | default, measured |
| Security review | claude-code-action with a security prompt on read-only tools (#895), beside the required static gates (CodeQL, secret-scan, dependency-review, osv-scanner) | sisaku-security/sisakulint for AI-agent action audits zizmor lacks; gh-aw security review | Three arms preregistered | default (in review) |
| Triage | The model-proposes, model-free-applies design (#896) | actions/labeler for deterministic path labels; gh-aw triage | Mislabel rate on the first real runs, before any author gate | default (in review) |
| Release and changelog | The existing tag-only publication with attested assets (`gh release`) | googleapis/release-please; release-drafter | Same-delta comparison preregistered | default |
| Dependency updates | The stdlib release trackers plus Dependabot (2026-10-02 trial) | renovatebot/renovate | Renovate custom manager against the trackers | default, measured |
| Landing | Lander 5f with `gh` on the command center's cue | chdsbd/kodiak | None; a merge queue needs an organisation-owned repository | default |
| CI analytics | None today | dorny/test-reporter; trunk-io analytics uploader | Not preregistered | trial candidate |
| Docs automation | Current validation | DavidAnson/markdownlint-cli2-action; lycheeverse/lychee | Not preregistered | trial candidate |
| Maintenance agents | Existing owners (the currency lane and the report-only scheduled workflows) | claude-code-action scheduled agents; gh-aw | A new scheduled writer needs a measured advantage | default |

anthropics/claude-code-security-review stays rejected (R68 of 2026-09-28 reconfirmed): no default-branch commit
since 2026-02-11 and no releases, which fails the 90-day maintenance rule.

## Actions from verification

1. **The secret-path guard fails closed when its script is missing, and the client floor rises to 2.1.295.** The
   template wrapper exits 0 when the guard script is missing, so `onFailure` never fires
   (`adoption/templates/claude.settings.template.json:195`), and the pinned floor 2.1.284 ignores `onFailure`
   ([guard record](2026-10-08-guard-hook-fails-closed.md)). A reviewed diff went to the command center: the wrapper
   exits 2 with a refusal when the script is missing (template plus one declared test contract change; 110 tests pass
   locally), and the verified 2.1.295 manifest (gpg-verified, linux-x64 sha256 `4503bfe1…f358`) for the floor raise,
   which the currency lane applies to the pin files.
2. **Retention is a secret-exposure window.** `cleanupPeriodDays: 3650` keeps plaintext transcripts and pre-edit file
   snapshots for about ten years (claude-directory.md; the client default is 30 days). Retention is the owner's
   choice. Trade-off: 3650 keeps the full local history that session archives and audits read; 30 matches the vendor
   default and the shortest exposure but removes transcripts after a month. Recommended: **180**, after one probe that
   the session archive (agentsview) keeps a session once its transcript file is gone, so that no record depends on a
   transcript older than that.
3. **The native sandbox bounds shell commands only.** For bypass sessions the docs call for a container, a VM or the
   sandbox runtime (sandbox-environments.md). That is recorded as a candidate under the sandbox slot; nothing is
   adopted without measurement, and bypass is not reopened.

## Measurements owed

| Measurement | Decides | Owner |
| --- | --- | --- |
| Paired quality-parity run for context-mode, rtk and headroom on our tasks (a J7 class) | output-compression default | api-actions (requested by the command center) |
| Paired same-delta run: pr-review-toolkit against native `/code-review max` on confirmed findings (J7 class D) | pr-review-pre-cue | api-actions |
| M7 effort sweep (high, xhigh, max) on frozen packets | model-effort-routing | command center (model choices are the owner's) |
| Three-arm PSS run on serena with pyright: per-session stdio, one native HTTP instance, behind mcpproxy-go | mcp-shared-servers | overlap-token |
| M1 sandbox arms on this host | sandbox | owner opt-in, then the command center |
| M19 Concise against Default output style | output-styles | command center |
| Blinded skills-content comparison | skills-library | skills-lifecycle |
| Mislabel rate on the first real triage runs before any author gate | GitHub triage | api-actions |
| agentsview retention probe | cleanupPeriodDays recommendation | command center |

## Refresh loop

The practice stays current through a weekly pass owned by the **currency lane**, ruled by the command center on
2026-10-09. The currency lane already owns the resolver loop of the [upstream surface watch](../upstream-surface-watch.md).

| Part | Value |
| --- | --- |
| Cadence | Weekly, Thursday, after the 06:41Z run of [`practice-references-freshness.yml`](../../.github/workflows/practice-references-freshness.yml) |
| Inputs | That run's report (archived, stale, renamed or drifted references); the surface watch's unreviewed list; the Claude Code CHANGELOG entries since `client_version` in [`reference/slots.json`](../../.claude/skills/claude-native-practice/reference/slots.json) |
| Work | One combined pass: each new or superseded source, and each CHANGELOG entry that changes a slot's default behaviour, becomes a candidate G5 row or a dated update to the living page |
| Output | Candidate G5 rows handed to grand-catalog under the G5 refresh procedure; page updates by pull request |
| Fallback | If the currency lane is parked on a Thursday, the co-op wakes it for the pass and records the trigger |

The practice-reference re-pins and the seven new references from this review go to grand-catalog as a candidate file
in the existing catalog's schema, validated with `practice_references.py --catalog`; grand-catalog folds it into
`catalogs/foundation/practice-references.json` after #878. The workflow itself does not change.

## Handoff

The [`claude-native-practice` skill](../../.claude/skills/claude-native-practice/SKILL.md) is the entry point. Its
description triggers on Claude Code configuration, harness and workflow decisions and Claude GitHub Actions setup; its
reference pages carry the defaults, so they travel with the skill (supporting files load on demand, per the skills
documentation). Measured on 2026-10-09:

- skill-creator `run_eval.py` trigger evaluation, 10 queries times 3 runs: 30 of 30 correct for the first description
  and 30 of 30 for the shipped one; no unrelated query fired in either run
  ([trigger-eval.json](../../evidence/artifacts/claude-native-practice-20261009/trigger-eval.json));
- fresh `claude -p` sessions in a checkout of this branch, three practice questions on each of Sonnet 5.5 and Opus 5.5,
  none of which names the skill: the skill was the session's first tool call in 5 of 6; 4 of 6 then read
  `reference/slots.md` whole, two by Read and two by `cat` in a shell command (Sonnet 2 of 3, Opus 2 of 3), and a fifth
  (Opus) grepped it before reading the MCP page. For example, asked which model, effort and permission flags a
  headless reviewer should use, Sonnet 5.5 called `Skill` with `claude-native-practice` first and then read
  `.claude/skills/claude-native-practice/reference/slots.md`. Each run's launch command, exact request, first Skill
  invocation with its arguments and every tool call that read from the skill directory (position, tool, exact path or
  command) are in `activation_excerpts`, so the rates recompute; the transcripts stay private. The
  misses cluster on the hooks question, where this host's auto memory and the 2026-10-08 guard record already hold
  the answer. The first description fired in 0 of 1 Sonnet runs; stating that the page is newer than repository notes
  or memory, and telling the session to start by reading it, produced the measured rate
  ([fresh-session.json](../../evidence/artifacts/claude-native-practice-20261009/fresh-session.json)).

After landing, the command center installs the skill at user scope for both clients through the pinned skills
manifest. Fresh-session proofs then run in us-equities-trading (Claude) and a Codex lane, and each must show the
skill firing and its reference page being read.

## Overturn conditions

Revisit this record when any of these happens: a Claude Code release changes a slot's default behaviour (the weekly
pass checks the CHANGELOG since `client_version`); a measurement listed above returns; a vendor repository supersedes a
default; or a slot's overturn condition on the page fires.

## Evidence class and limits

Official behaviour is source review of the installed client, the CHANGELOG at its tag, the documentation with fetch
times and vendor repositories at pins. Community practice is source review at pins. Measured here: the symlink probe
on 2.1.295, the trigger evaluation, the verified 2.1.295 manifest, the J8 review counts and the host's own counters
quoted in the rows. Untested: every pending measurement above, and every third-party candidate's runtime on this host.
No setting, hook, permission, catalog or installed component changed in this pull request.

## SOTA sources

- Claude Code 2.1.295: installed client; `anthropics/claude-code@602df92bf481ed904533e95c09f740f40aab5aed` CHANGELOG.md;
  documentation at https://code.claude.com/docs/en/ (skills, memory, settings, permissions, sandboxing, hooks,
  sub-agents, agent-teams, workflows, plugins, output-styles, mcp, statusline, checkpointing, headless, model-config,
  costs, monitoring-usage, context-window, prompt-caching), fetched 2026-10-09.
- `anthropics/claude-code-action@2dca132ff0e0c4094ce6048b422c6915a071210b` (v1.0.247) and its docs.
- `anthropics/skills@683bc88e56f3e09ba94f7055977f3d3aa499f202` (skill-creator `run_eval.py`),
  `anthropics/claude-plugins-official@315c4e48967d9541c29c3c656441dded353ca7aa`,
  `anthropics/claude-agent-sdk-python@a8e7ce3cf2d7b18f815f55d5ef3b770d8bfe9cd9`,
  `anthropics/claude-agent-sdk-typescript@da321bbe62ed45d10a1ff0e77a948253d9eee3e0`,
  `anthropics/claude-cookbooks@d7265d6ae994ccd8429db0594b000073b2f9ad43`.
- `openai/codex@979011409de0a60b52f179721948e65531d26144` (rust-v0.161.0) `codex-rs/ext/skills/src/host_roots.rs`.
- Community repositories at the pins in the practice-references candidate file
  ([practice-references-candidate.json](../../evidence/artifacts/claude-native-practice-20261009/practice-references-candidate.json)).
- Anthropic pricing, https://platform.claude.com/docs/en/about-claude/pricing, read 2026-10-09.

## Addendum (2026-10-09): primary sources, one practice for both clients, and measured probes

**Primary-source reading.** After the owner directed this lane to the quality of code and workflows, run
`wf_bee0b670-035` read 31 primary sources: 22 Anthropic engineering and Claude blog posts on code and workflow quality,
and 9 cross-client sources (the Agent Skills specification and its skill-evaluation guide; the Codex skills, subagents,
hooks, AGENTS.md, non-interactive and plugins documentation; OpenAI's harness-engineering post). For each source an Opus
5.5 reader at xhigh extracted the practices it states and mapped each to a role slot and a client, and an Opus 5.5
refuter at max re-read the page and refuted each practice by default. All 31 sources were readable. Of 248 practices
the refuters kept 195 and refuted 53; of the 195, 56 agree with a default, 127 extend one, 3 contradict one and 9 are
not covered by any default; 186 map to one of 24 role slots and 9 to none; 19 rest on a measurement the source
reports, and 124 apply to both clients. Each source carries its fetch time and the sha256 of the bytes read
([primary-source-reading.json](../../evidence/artifacts/claude-native-practice-20261009/primary-source-reading.json));
the layer pages list each slot's sources. Before this run one post backed a default (planning-persistence); the
others were only links inside community sources. Spend: $63.87 at API list price (usage record).

**One practice, native execution per client** (command center, 2026-10-09): procedure in a short AGENTS.md map and
Agent Skills, which both clients load; execution in each client's own mechanism, with nothing ported; and, as the
landing rule for every author, a deep multi-agent review of every PR by the other model family, each finding given a
landing-time disposition and precision tracked per family. The mapping and its sources are in
[`reference/cross-client.md`](../../.claude/skills/claude-native-practice/reference/cross-client.md). The gate rests
on measurements: Anthropic's code-review post reports substantive review comments on 54% of PRs, up from 16%, and
its multiagent-systems post finds that agents sharing a model, scaffold and context act almost identically, so their
agreement is weak evidence.

**Default extensions accepted by the command center:** orchestration keeps a single session for ordinary coding and
fans out only when parallelism or specialization earns its cost, with harness components ablated at each model
release; completion evaluators exercise the running system against explicit thresholds; long builds start with a
spec step and keep execution plans with progress and decision logs in the repository; each skill is evaluated with
and without it in clean contexts. **Contradictions held as candidates:** classifier routing to Sonnet (until the M7
A/B), a one-hour cache TTL for long API-key sessions (api-actions' scope), and Ralph-style headless loops (until the
planning-persistence paired run).

**What the exports describe.** The reader and refuter settings above are those the run's children were measured at
(`usage.by_phase` in the reading, from `child-usage.mjs` over the retained transcripts; the tool exits 1 under
`--require-effort max` because the 31 readers run at xhigh by design). `claude-native-slot-manifest.json` is the data file
built on 2026-10-09 from `reference/slots.json` as merged in #923 (`a30c2188e`, sha256 `a7d87f9a…`): a baseline snapshot,
labeled so in its `snapshot` block, whose citation relations are relative to those rows. The current decision source is
`reference/slots.json`, which adds the four route extensions and the two held alternatives above and moves
loops-completion's Ralph-style entry from its rejections to a held candidate; the block lists each differing field. The
reading's page:line locators (for example `slots.md:35`) resolve at that same revision, not at this change's head, and
its `local_references` says so. `tests/test_native_practice_snapshot_provenance.py` checks the label, the listed
differences and, where the history holds the revision, the baseline rows and six quoted-phrase locators.

**Model and effort routing** (ruled about 12:40Z; the owner delegated it to the command center): Opus 5.5 is the
floor; xhigh is the session default; max is for verify, judge and adjudication roles and the coordinators; a cheaper
model needs a frozen paired A/B at parity; `CLAUDE_CODE_EFFORT_LEVEL` and `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` stay unset.
The keys, as `settings-reference.md` documents them for 2.1.295 (`model` line 1090, `effortLevel` line 942,
`modelSettings` line 1230; the two environment variables in `env-vars.md`), already carry these values in the
template (`model: "opus[1m]"`, `effortLevel: "xhigh"`, `modelSettings` at xhigh, `CLAUDE_CODE_SUBAGENT_MODEL=opus`), and
the judge, verifier and reviewer agents declare `model: opus`, `effort: max`. No key changes: builder and research
agents stay at max until the M7 sweep shows parity at xhigh, and `source-scout` stays on Sonnet 5.5 under the
2026-09-29 split decision (benchmark evidence and an Opus review of its output), an open item against the A/B rule.

**Retention and the session archive.** The command center set `cleanupPeriodDays` to 180 on the host; the template now
carries 180. The archive probe passed: agentsview 0.44.0 keeps a session, its messages and its export row after the
transcript is deleted, through incremental and full resyncs. All 2,501 sessions of the pre-move archive were found in
the live one, no process held it, and its database and usage-cache files (1,784,512,512 bytes) were deleted at
13:50:06Z under the owner's superseded-items rule; its small leftovers stay until 2026-10-23
([probes-20261009.json](../../evidence/artifacts/claude-native-practice-20261009/probes-20261009.json)).

**Sandbox measurements, kept as facts.** M1 on this host: the native sandbox runs the RTK hook, `gh`, `codex` and
explicit-path commits; it blocks direct connections to host loopback services (they answer through the sandbox
proxy), `git add -A` (protected-path placeholders in the working tree) and writes outside the working directory; it
refuses `dangerouslyDisableSandbox`, denies unlisted hosts under `strictAllowlist` and blocks the docker socket. With no
deny list the sandbox exposes credential files and secret variables; the template's `Read(...)` denies alone cover
all 24 credential stores it names, and secret variables need `sandbox.credentials.envVars` entries. After the owner's
direction against further security work, the sandbox profile was dropped and these results stand as measurements.

**Paired runs (W5 of the finalization program).** Preregistered before any arm runs, in this lane's research
directory: orchestration on six validated north-star fixtures (single session, a verify Workflow, an agent team; AO's
bounded role in a separate PR-cycle run); planning persistence under forced compaction; and the review gate (vendor
paths against the current reads, with the co-op). Their results follow in a later addendum.
