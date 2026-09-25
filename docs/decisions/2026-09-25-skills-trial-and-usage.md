# Decision: skills trial and usage monitoring (2026-09-25)

**Decided by:** the user's 2026-09-25 request to install all SOTA skills and monitor their
invoke rate, portable to all hosts. `adoption/skills/manifest.json` (the first commit of this change: "Skills trial manifest: 26
pinned skills (5 kept winners, 21 trial) with audits, gaps and listing states") pins the
selected, trial and excluded skills and names this file as its `decision_record`. This record adds the measured baseline, writes up the
listing/measurement policy the manifest's `trial` and `budget` fields already declare, and
records the trial-scope supersession of two 2026-09-24 dispositions below.

**Scope:** this record, `blueprints/native-skill-practice/README.md`'s install section,
`recipes/claude-native-profile.md`'s ECC skills-install section, and one added step in
`adoption/update.md`, alongside the manifest, installer, status check, usage report, tests and
this host's evidence artifact in the same change; that change's last commit registers every
added or changed file in `manifests/evidence.json` under the `docs/lanes.md` hot-file protocol.
`catalogs/landscape/foundation.json`'s `instructions-skills` row is deliberately unchanged.

**Not covered:** whether any trial skill is promoted to a verdict winner (see
[Verdict boundary](#verdict-boundary)); the actual per-host pinned install run, which is a
pending coordinator receipt, not something this record executes or claims.

## Decision

Install all 26 skills named in `adoption/skills/manifest.json` for a 30-day trial
(`2026-09-25` to `2026-10-25`), each at the `claude_listing` and `codex_enabled` state the
manifest already assigns, and monitor invocation with the native `/skill-doctor` command
(Claude) and `tools/skill-usage` (Codex). Trial status is not a verdict: the five already-`kept`
skills are unchanged winners from before this trial; the 21 `trial` skills are candidates whose
listing decays automatically if unused, and none of them changes
`catalogs/landscape/foundation.json`'s `instructions-skills` row on its own.

## Mechanics (source review, skills CLI v1.7.0)

Read directly from the installed CLI's source, not its `--help` text: the global lock is at
`$XDG_STATE_HOME/skills/.skill-lock.json` when that variable is set, else
`~/.agents/.skill-lock.json` (lock version 3, `skills{name: {source, sourceType, sourceUrl,
skillPath, skillFolderHash, installedAt, updatedAt}}`). `skillFolderHash` is the upstream git
tree SHA of the skill's folder, which is exactly the manifest's `tree_sha` field per skill. The
canonical copy lives once, at `~/.agents/skills/<name>/`; `claude-code` gets a **relative**
symlink `~/.claude/skills/<name> -> ../../.agents/skills/<name>`, and Codex reads
`~/.agents/skills` directly with no link. `skills add <github tree URL at a 40-hex ref> --skill
<name> -g -y -a claude-code codex` installs at that exact commit for both clients in one command;
`add` runs `cleanAndCreateDirectory` on the target, so it replaces an existing folder rather than
merging into it. `skills remove <name> -g -y` (no `-a`) removes the canonical copy, both links
and the lock entry. `check` is the same code path as `update` and can write, so both need `-g`
for global scope. `DISABLE_TELEMETRY=1` disables both the telemetry event and the add-time audit
call, which is why the manifest's `cli.env` sets it and why the measurement commands below set it
explicitly rather than relying on a default.

Codex 0.155.1 disables a skill without touching the lock or the symlink, through
`[[skills.config]]` tables in `~/.codex/config.toml`: `name = "<skill>"` and `enabled = false`,
no path needed. Claude Code 2.1.282 does the equivalent with a settings key, `skillOverrides`,
mapping a skill name to `"on" | "name-only" | "user-invocable-only" | "off"` — exactly the four
values the manifest's `claude_listing` field uses, propagated to a host by
`adoption/templates/claude.settings.template.json`'s `skillOverrides` block through
`tools/adoption/apply_claude_settings.py`'s deep merge (a key removed from the template is never
removed from an already-applied host, so a demotion must write an explicit state rather than
delete a key). Native `claude -p "/skill-doctor" --output-format json` costs 0 API tokens
(`num_turns` 0, model `<synthetic>`) and prints a table headed `skill  source  context  7d
tokens  uses  last used`, with `context` a listing-cost estimate in tokens (`-` when a skill does
not appear in the listing at all, as `off` skills do not), `uses` a count like `3×`, and `last
used` either `never` or a relative/absolute time. This is a native operation with actual output,
not a wrapper's self-report.

## Baseline measurement — 2026-09-25, host `nativestack-5975wx-20260925`

| Check | Command | Result |
| --- | --- | --- |
| Claude skill listing and use | `claude -p "/skill-doctor" --output-format json` | Lists the 5 installed user skills, all at 0 uses / `never`: `gh-fix-ci` (~110 context tokens), `iterative-retrieval` (~70), `search-first` (~50), `security-best-practices` (~140), `typesafe-ai` (~230). Also lists 8 synced (claude.ai sync) and 15 plugin skills, none ever invoked. |
| Lock currency | `DISABLE_TELEMETRY=1 skills update -g` | `All global skills are up to date.` Lock unchanged: no `skillFolderHash` moved. |
| Scout transcript count (read-only, not a receipt) | grep-style scan of 1,189 local Claude transcripts for a `Skill` tool call naming one of the 5 installed skills | Zero matches for the five; the only `Skill` calls found were `loop`, twice, for an unrelated recurring task. |
| Scout rollout count (read-only, not a receipt) | scan of 76 local Codex rollouts for a `$skill` invocation | Zero matches. |

The transcript and rollout counts are a **scout measurement**, per
[the acceptance-evidence policy](../acceptance-evidence-policy.md#identify-what-each-check-proves):
a read-only inspection with no frozen oracle and no independent corroboration beyond the
count itself, not a receipt. It bounds today's baseline; it is not a claim about every session on
every host, and a transcript missing from this host's local store would silently not count. The
`/skill-doctor` run and the `skills update -g` run are each a native operation with actual
returned output, which is a stronger evidence class than the scout count (see
[Evidence class](#evidence-class)) — but `/skill-doctor`'s own zero-use figures are exactly what
the scout count independently corroborates for the five installed user skills, using a different
method (direct transcript inspection instead of the client's own counter).

All 5 kept skills and all synced/plugin skills sit at 0 uses on day zero of the trial; that is
expected on the day skills are installed or a trial starts, not evidence against them. The
`review_after` date, 2026-10-25, is when 30 days of real usage exists to judge.

## Selection rule

Per [the acceptance-evidence policy](../acceptance-evidence-policy.md#select-and-reuse-before-building),
"repository popularity, local test totals and a well-formed receipt are discovery or validation
signals; none establishes native end-to-end behavior by itself." Install counts, stars and
skills.sh badges are exactly that kind of signal here and never by themselves qualify a skill.
The manifest applies one rule per candidate, in order:

1. **A named, concrete gap** in this repository (a missing procedure, an ad hoc workaround, an
   unwritten checklist) — every `kept` and `trial` row's `gap` field states it; a candidate with
   no such gap (`jupyter-notebook`: no `.ipynb` file exists) is excluded instead.
2. **A license** the skill actually carries at its pinned revision (`doc-coauthoring`,
   `web-design-guidelines`, `writing-guidelines` and `vercel-react-best-practices` are excluded
   for lacking one).
3. **No audit Fail** from the skills.sh listing (Gen Agent Trust Hub, Socket, Snyk), read
   2026-09-25 (`code-review` and `insecure-defaults` are excluded on a Snyk Fail; a Warn is not a
   Fail and does not exclude by itself).
4. **No duplicate** of a capability this host already has natively or through an existing sync:
   native `/code-review`, `/security-review` and the bundled `claude-api` skill; the claude.ai
   skill sync (`anthropic-skills:*`); Codex's own `.system` skills. `differential-review`,
   `gh-cli`, `playwright`/`playwright-cli`/`webapp-testing`, `pdf`/`docx`/`xlsx`/`pptx`/`claude-api`
   and both `skill-creator` copies are excluded on this rule.
5. **No conflict** with `CLAUDE.md`/`AGENTS.md`. The eleven `obra/superpowers` process skills
   (`using-superpowers` through `writing-skills`) are excluded because they contradict the
   no-intake, no-brainstorming, native-worktree and bounded-review-loop rules those files set.
6. **One winner per capability.** Where two candidates cover the same gap, only one is installed:
   `mattpocock/skills`' `diagnosing-bugs` and `tdd` are the installed winners over
   `obra/superpowers`' `systematic-debugging` and `test-driven-development`.

## The 26 pinned skills

| Name | Source @ ref | Status | Listing | Codex | Gap |
| --- | --- | --- | --- | --- | --- |
| typesafe-ai | typesafe-ai/skills@65a39f3 | kept | name-only | yes | Verdict winner (`instructions-skills`): typed semantic judgments for evidence review, used by the semantic-evidence-reviewer role. |
| gh-fix-ci | openai/skills@49f948f | kept | on | yes | Verdict winner: triage failing GitHub Actions checks on this repo's 18 workflows and 7 required checks. |
| security-best-practices | openai/skills@49f948f | kept | on | yes | Verdict winner: language-specific secure-coding review for `scripts/` and `tools/`. |
| iterative-retrieval | affaan-m/ECC@2b6e839 | kept | name-only | yes | Verdict winner (ECC): staged retrieval for subagent context under the small-context rule. |
| search-first | affaan-m/ECC@2b6e839 | kept | name-only | yes | Verdict winner (ECC): research existing upstream tools before writing code (AGENTS.md research-first rule). |
| diagnosing-bugs | mattpocock/skills@c55ee46 | trial | on | yes | No debugging procedure is installed; failing tests, CI and paper-engine faults are diagnosed ad hoc. |
| tdd | mattpocock/skills@c55ee46 | trial | on | yes | New scripts land with unittest suites but no test-first procedure is loaded. |
| codebase-design | mattpocock/skills@c55ee46 | trial | on | no | Large single-file validators (`scripts/validate.py`, `scripts/landscape.py`) lack a shared module vocabulary for refactors. |
| resolving-merge-conflicts | mattpocock/skills@c55ee46 | trial | on | no | Concurrent sessions rebase onto hot files (`manifests/evidence.json`, `docs/lanes.md`) and hit conflicts. |
| grill-me | mattpocock/skills@c55ee46 | trial | user-invocable-only | no | User-invoked stress test of a plan before approval; upstream disables model-invocation, so no listing cost. |
| improve-codebase-architecture | mattpocock/skills@c55ee46 | trial | user-invocable-only | no | User-invoked architecture review of a grown module; upstream disables model-invocation. |
| verification-before-completion | obra/superpowers@8ca22db | trial | on | yes | CLAUDE.md requires resolved findings and verified behavior before completion; no checklist skill enforces it. |
| security-threat-model | openai/skills@49f948f | trial | on | yes | Paper-lane broker adapters, credential stores and host-request lanes have no written threat model. |
| gh-address-comments | openai/skills@49f948f | trial | on | yes | The main ruleset requires review-thread resolution; PR comments are addressed by hand. |
| semgrep | trailofbits/skills@0cc1c73 | trial | on | no | No custom static rules beyond CodeQL default setup; ad hoc pattern audits are grep-based. |
| codeql | trailofbits/skills@0cc1c73 | trial | on | no | CodeQL default setup gates main, but alert triage and custom queries have no procedure. |
| supply-chain-risk-auditor | trailofbits/skills@0cc1c73 | trial | on | no | Catalog winners and pinned tools are adopted without a dependency risk checklist. |
| agentic-actions-auditor | trailofbits/skills@0cc1c73 | trial | on | no | Agent-adjacent workflow automation has no audit procedure for agentic Actions risk. |
| property-based-testing | trailofbits/skills@0cc1c73 | trial | on | no | Parsers and sanitizers (`host_receipts.sanitize`) have example tests only; Scorecard Fuzzing scores 0. |
| modern-python | trailofbits/skills@0cc1c73 | trial | on | yes | `scripts/` and `tools/` use uv-run Python without a shared modern-tooling guide. |
| sarif-parsing | trailofbits/skills@0cc1c73 | trial | on | no | zizmor, OSV-Scanner, Scorecard and CodeQL all upload SARIF; reading and diffing results is manual. |
| fp-check | trailofbits/skills@0cc1c73 | trial | on | no | Open Scorecard/zizmor/CodeQL alerts need false-positive triage with retained reasoning. |
| mcp-builder | anthropics/skills@3337550 | trial | on | no | 22 files wire MCP servers; building or fixing one has no procedure. |
| frontend-design | anthropics/skills@3337550 | trial | on | no | The generated ecosystem guide and grand dashboard (19 HTML files) are hand-styled. |
| agent-browser | vercel-labs/agent-browser@d01253d | trial | name-only | no | Browser acceptance uses the pinned `agent-browser` CLI; the skill documents its commands (925-char description). |
| find-skills | vercel-labs/skills@7407f38 | trial | user-invocable-only | no | User-invoked registry search; anything it finds still needs pinning in this manifest before install. |

## Excluded groups

| Skills | Source | Reason | Overturn |
| --- | --- | --- | --- |
| using-superpowers, brainstorming, writing-plans, executing-plans, using-git-worktrees, subagent-driven-development, dispatching-parallel-agents, finishing-a-development-branch, requesting-code-review, receiving-code-review, writing-skills | obra/superpowers | Process skills conflict with CLAUDE.md/AGENTS.md: no intake or brainstorming for bounded work, manually created worktrees, Ultracode workflow orchestration, bounded review loops. | The canonical instructions drop the conflicting rule, or a frozen A/B shows a process skill improves accepted outcomes without adding intake steps. |
| systematic-debugging, test-driven-development | obra/superpowers | Duplicate capability: mattpocock `diagnosing-bugs` and `tdd` are the single winners per capability. | The trial shows the winner unused while a duplicate would have triggered on the same prompts. |
| setup-matt-pocock-skills, wayfinder, triage, to-tickets | mattpocock/skills | `setup-matt-pocock-skills` edits CLAUDE.md/AGENTS.md and writes `docs/agents/*`; the others depend on that setup and on issue-tracker conventions this repo does not use. | The user adopts the upstream issue-tracker conventions and approves the canonical-instruction edit. |
| code-review | mattpocock/skills | skills.sh audit Snyk Fail (2026-09-25); also duplicates the bundled `/code-review`. | A later audit passes and native `/code-review` shows a gap on the same diffs. |
| research | mattpocock/skills | Writes findings `.md` into the repo; duplicates `search-first` and `iterative-retrieval`. | Kept research skills show a gap on a frozen research task. |
| insecure-defaults | trailofbits/skills | skills.sh audit Snyk Fail (2026-09-25). | A later audit passes. |
| differential-review, gh-cli, sharp-edges, mutation-testing | trailofbits/skills | `differential-review` duplicates bundled `/security-review`; `gh-cli` duplicates `gh-fix-ci` and native `gh` use (Snyk Warn); `sharp-edges` and `mutation-testing` have no concrete gap yet. | A concrete gap appears (e.g. a mutation-testing requirement) and the skill passes its audits. |
| skill-creator | openai/skills, anthropics/skills | The openai copy has a Gen Agent Trust Hub Fail; both duplicate the synced `anthropic-skills:skill-creator` and Codex `.system/skill-creator`. | Never while a native copy exists. |
| jupyter-notebook | openai/skills | No notebook exists in the repository (0 `.ipynb` files on 2026-09-25). | The first notebook research artifact lands. |
| playwright, playwright-cli, webapp-testing | openai/skills, microsoft/playwright-cli, anthropics/skills | Duplicate browser capability; `agent-browser` is the pinned browser CLI. | `agent-browser` fails a browser acceptance that one of these passes. |
| pdf, docx, xlsx, pptx, claude-api | anthropics/skills | Duplicates of the synced anthropic-skills and the bundled `claude-api` skill. | Never while the native copies exist. |
| doc-coauthoring, web-design-guidelines, writing-guidelines, vercel-react-best-practices | anthropics/skills, vercel-labs/agent-skills | No license file or field at the pinned revisions; the React guidance has no React code here. | A license is published and a concrete UI/React gap appears. |
| Lark/Feishu, Azure, genmedia, hyperframes, remotion, reddit-automation and vendor-specific packs | various | Off-domain for this repository's layers. | The repository adds that domain. |

## Listing policy

- **Cap.** `on`-listed Claude descriptions are capped at 8,000 characters combined
  (`trial.on_description_char_cap`). The current sum is 6,746 characters
  (`budget.claude_on_description_chars`), leaving 1,254 of headroom before a new `on` skill would
  push another out.
- **Codex budget.** Codex's own default description budget is 8,000 characters
  (`budget.codex_default_budget_chars`); enabled skills currently sum to 2,951
  (`budget.codex_enabled_description_chars`).
- **Name-only confound.** "name-only and user-invocable-only listings depress proactive
  invocation; compare only within a listing state" (`trial.confound`, verbatim). A `name-only`
  skill's 0-use count is not comparable to an `on` skill's 0-use count: the model cannot see a
  `name-only` skill's description to decide whether to invoke it, so a low count there says less
  about the skill's usefulness and more about its listing state. This is why `typesafe-ai`,
  `iterative-retrieval` and `search-first` sit at `name-only` already, ahead of any measured
  under-use: each is a deliberate-invocation skill (consulted for a specific task, not a
  proactive trigger), matching M10's rule below.
- **Prune rule** (`trial.prune_rule`, verbatim): "A skill installed for at least window_days with
  zero invocations in the last window_days is demoted one step (on -> name-only -> off) or
  removed; kept verdict winners change only through a verdict re-record." A `kept` skill's
  five-winner status cannot be silently pruned; only a fresh verdict record changes it. A
  `trial` skill's `claude_listing` can be demoted automatically at the 30-day mark.
- **Window.** Trial started 2026-09-25; `review_after` is 2026-10-25 (`trial.window_days`: 30).

This settles part of `docs/decisions/2026-09-24-community-sweep.md`'s
[M10](2026-09-24-community-sweep.md#keep-but-compare) ("Run `/skill-doctor` once to settle the
open `skillOverrides` name-only decision... set name-only only for never-invoked skills.
Overturned if a name-only skill then fails to trigger on a task that needs it."): today's
`/skill-doctor` baseline confirms all three already-`name-only` kept skills are never-invoked, so
M10's rule is satisfied for them. M10 itself is `docs/decisions/2026-09-24-community-sweep.md`'s
row to close, not this record's; that document is read-only reference here, and its own owner
(the community-sweep coordinator) updates it if it treats this baseline as sufficient.

## Monitoring

- **Claude:** native `/skill-doctor`, run headless with `claude -p "/skill-doctor"
  --output-format json` — 0 API tokens, `num_turns` 0, model `<synthetic>`. Zero incremental
  provider cost per check.
- **Codex:** `tools/skill-usage/skill_usage.py`, over explicitly passed rollout roots (Codex has
  no native equivalent of `/skill-doctor`; the manifest's `trial.measurement.codex` field pins
  this path).

### Alternatives considered

- **OpenTelemetry with `OTEL_LOG_TOOL_DETAILS=1`.** Rejected: it requires standing up and
  operating an OTel collector for a 30-day trial of 26 skills, when the native command already
  gives the same per-skill use count and last-used time at zero incremental cost.
- **A custom `Skill`/`UserPromptExpansion` hook.** Rejected: it would duplicate what
  `/skill-doctor` already reports natively, and a hook that fires on every prompt adds latency
  and a new failure surface for a measurement the client already computes.
- **The project's own `skills-lock.json` plus `experimental_install`.** Rejected: that path
  restores a skill at `HEAD` or a given ref without comparing `computedHash` against what is
  actually installed, so a host could silently drift from the pinned revision with no signal.
  The upstream global lock's `skillFolderHash` (the git tree SHA) is the check that catches that
  drift, and the manifest's per-skill `tree_sha` is compared against it.
- **systemd/launchd timers** to poll `/skill-doctor` or re-run `skills update` on a schedule.
  Rejected: this project's `automatic_model_calls` policy is `false`, and a timer invoking a
  model command (even a 0-token one, since the boundary is the policy, not the price) is exactly
  what that policy excludes. `tests/test_adoption_launchd.py` fixes the template set of services
  this host runs under launchd/systemd, and a new recurring model-invoking unit is not one of
  them.

## Supersedes, trial scope only

This manifest supersedes two 2026-09-24 dispositions, **only for the one named skill each, and
only for the 30-day trial** — every other skill in each source repository stays excluded under
its original reason (see [Excluded groups](#excluded-groups) above, which still lists
`obra/superpowers`'s eleven process skills and two debugging duplicates as excluded).

- **anthropics/skills.** `docs/community-native-practice.md`'s 2026-09-24 review row reads,
  quoted exactly: "Not installed or vendored; its useful parts reach this host through the
  claude.ai skill sync and the bundled claude-api skill." This manifest now trial-installs two
  named skills from that repository, `mcp-builder` and `frontend-design` (both `on`, ref
  `3337550`), each against a concrete gap this repository has and the claude.ai sync and
  `claude-api` skill do not cover (MCP-server authoring; the hand-styled ecosystem/dashboard
  HTML). The "not installed or vendored" disposition otherwise still holds: every other
  `anthropics/skills` candidate (`pdf`, `docx`, `xlsx`, `pptx`, `claude-api`,
  `doc-coauthoring`, `web-design-guidelines`, `writing-guidelines`, the `skill-creator` copy) is
  excluded above for the same reasons that review gave.
- **obra/superpowers.** `docs/decisions/2026-09-24-community-sweep.md`'s follow-up-sweep row
  reads, quoted exactly: "Keep the catalog's `alternative` disposition: no plugin, SessionStart
  bootstrap or skill copy." This manifest now trial-installs one named skill from that
  repository, `verification-before-completion` (`on`, ref `8ca22db`), against the CLAUDE.md
  requirement that findings be resolved and behavior verified before completion, which the
  follow-up sweep itself flagged as a real gap ("tests that cannot fail, and untested empty,
  zero or non-finite inputs... caught only at independent review"). No plugin, SessionStart
  bootstrap or any other `obra/superpowers` skill is installed: the eleven process skills and the
  two debugging duplicates stay excluded, and the follow-up sweep's own proposed remedy (a
  required test-break entry in the isolated-builder return) is unaffected by this manifest and
  remains that record's own keep-but-compare item, not this one's.

## Verdict boundary

Trial skills are not verdict winners (`trial.verdict_boundary`, verbatim): "Trial skills are not
verdict winners; catalogs/landscape/foundation.json instructions-skills is unchanged until a
sealed re-record." This record does not edit that row. A sealed cross-family re-record after
2026-09-30 (when the current Codex usage limit clears and cross-family review resumes) decides
promotion for any trial skill; until then, a trial skill's presence in the manifest is a bounded
experiment, not an adoption.

## Evidence class

Per [the acceptance-evidence policy](../acceptance-evidence-policy.md#identify-what-each-check-proves):

| Item | Evidence class | Basis |
| --- | --- | --- |
| Per-skill `tree_sha`/`skill_md_sha256`/license/`upstream_disable_model_invocation` fields | Structural validation | Hashes and fields checked against the pinned upstream revision; proves artifact identity, not execution. |
| skills.sh audit (Gen Agent Trust Hub, Socket, Snyk), read 2026-09-25 | Independent observation | A separate platform's own scan of the package/dependency surface; it checks what that platform inspects, not this skill's behavior in this repository. |
| Native `/skill-doctor` baseline and `skills update -g` result | Upstream example / native operation | Supported commands, actual returned output, on this host, today. |
| Scout transcript/rollout count (1,189 Claude transcripts, 76 Codex rollouts) | Explicitly a scout measurement, not a receipt | Read-only inspection with no frozen oracle; corroborates the `/skill-doctor` zero-use figures by a second, independent method. |
| Pinned install of these 26 skills on any given host | Pending coordinator receipt | Not yet run or recorded by this branch; this record documents the manifest and policy, not a completed installation. |

## Overturn conditions

- Codex gains a native skill-invocation event of its own → drop the `tools/skill-usage` rollout
  parser in favor of it.
- `/skill-doctor` gains a stable JSON schema beyond the current table → parse that JSON instead
  of the printed table.
- A trial skill shows measurable harm, or gives instructions that conflict with
  CLAUDE.md/AGENTS.md once actually read in full → remove it immediately, not at the trial
  window's end.
- Trial window end (2026-10-25) → apply the prune rule to every `trial` skill still at zero
  invocations in the preceding 30 days, and record the result as a manifest update plus a
  follow-up decision record.
