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
| security-best-practices | openai/skills@49f948f | kept | on | yes | Verdict winner: language-specific secure-coding review for `scripts/` and `tools/`, used by the security-reviewer role. |
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

## Addendum 2026-09-26: two trial additions, one deferral, corrected counts, on-disk tree check

Evidence: [`evidence/artifacts/skills-agents-layer-20260926/`](../../evidence/artifacts/skills-agents-layer-20260926/README.md)
(`delta.json` holds every source, commit, audit reading and count cited here).

**Pins unchanged.** On 2026-09-26 every one of the 26 pinned skill folders has the same git tree
SHA at its source repository's default-branch HEAD as at its pin (8 of 9 source repositories have
not moved at all; `affaan-m/ECC` moved to `e482e57` without touching `iterative-retrieval` or
`search-first`). No pin follows `adoption/update.md` today. The skills.sh page labels of all 26
read the same as on 2026-09-25.

**Added for trial**, each under the [selection rule](#selection-rule) (gap, license, no audit
Fail, no duplicate, no conflict, one winner per capability):

| Name | Source @ ref | Status | Listing | Codex | Gap |
| --- | --- | --- | --- | --- | --- |
| variant-analysis | trailofbits/skills@0cc1c73 | trial | on | no | Post-merge review keeps finding siblings of fixed defects (#314 widened #291's rtk blob exclusion and closed a blind-packet leak the #269 filter missed); `fp-check` verifies one finding and says it is not for hunting. |
| writing-for-agents | mattpocock/skills@c55ee46 | trial | on | yes | `AGENTS.md` (160 lines, 11,708 bytes) loads into every session and each worker that keeps project instructions, and changed in 28 commits from 2026-09-12 to 2026-09-26; no procedure covers context load, a single source of truth or pruning in `AGENTS.md` or `CLAUDE.md`. |

`writing-for-agents` also triggers on creating or editing skills, which the synced
`anthropic-skills:skill-creator` and Codex's `.system/skill-creator` own (rules 4 and 6). It is
admitted only for `AGENTS.md` and `CLAUDE.md`, which no skill-creator file mentions; the upstream
description cannot be split by pin, so the shared trigger is a trial confound, and at the review
only its uses on `AGENTS.md` or `CLAUDE.md` count toward its gap. Codex stays enabled because
`AGENTS.md` is Codex's own instruction file. Each addition's prune window starts at its own install
on each host (the lock's `installedAt`), so neither is a prune candidate at the 2026-10-25 review.

**Deferred: a local content scan before a pin.** `superagent-ai/skills` `skill-security` (0da315b)
was added in this branch's first round for the gap that rule 3 reads only third-party audits (the
audit API rated `agentic-actions-auditor`'s Socket result `critical`, 1 alert, while its page shows
Warn). Review removed it before any install. Its file discovery follows symlinks with no containment
check: on a synthetic fixture whose `references/example.md` links to a file outside the skill, an
`open()` trace showed it read that file, listed it as the skill's own and printed a line of it, with
no symlink finding. A scanner for untrusted skills that can print a readable credential file into
the transcript fails the credential rule. `getsentry/skills` `skill-scanner`, the alternative,
reports the outside symlink as critical but reads and prints through it too. On seven synthetic
malicious fixtures `skill-security` returned at least one high or critical finding on 6 and
`skill-scanner` on 4; the first round's "5 of 5 at high or critical" counted per-finding severities,
while `skill-security`'s own default verdict was DO NOT INSTALL only for the fixture combining an
instruction override, credential reads and a piped remote script, and REVIEW MANUALLY for the others
it flagged. Neither deterministic scanner flags instruction-only memory poisoning: the first round's
memory-poisoning fixture was caught through its `settings.json` permission-grant clause, and without
that clause both return nothing. The fixtures are authored for this check and are a small
diagnostic, not a universal ranking. The gap stays open until an upstream pin, or an enforced
wrapper, rejects symlinks that resolve outside the target (proposal P9 in `delta.json`).

**Corrected counts.** `budget.description_chars_method` now states the one method (Unicode code
points of the PyYAML-parsed description, whitespace stripped): 23 of the 26 recorded values already
followed it, and `semgrep`, `codeql` and `sarif-parsing` move from 709, 753 and 375 to 707, 751 and
373. With the additions, `on` listings sum to 7,409 of the 8,000-character cap (591 left) and
Codex-enabled descriptions to 3,054.

**Mechanics correction.** The lock's `skillFolderHash` is written at install time and never
recomputed, so it does not catch a file changed after install, which the [Alternatives
considered](#alternatives-considered) entry implied. On this host `supply-chain-risk-auditor`'s own
`uv run {baseDir}/scripts/collect.py` created `scripts/.venv` and `__pycache__` inside the installed
folder and rewrote the pinned `scripts/uv.lock` (dropping upstream's `exclude-newer-span = "P1W"`
option; the project declares no dependencies), while `scripts/skills_status.py` still passed.
The status script now recomputes each canonical folder's git tree from disk and reports `ok`,
`runtime_artifacts` or `drift` per skill, informationally: normal use recreates the files and
`tools/adoption/install_skills.py` does not reinstall a folder whose SKILL.md and lock entry match.

**Left for the verdict wave** (proposals in `delta.json`, not adopted): pin
`semgrep-rule-creator` or re-scope the `semgrep` gap (the pinned `semgrep` skill routes custom rules
to it, and neither the `semgrep` nor the `codeql` CLI is installed on this host); record raw audit
API risks beside page labels in rule 3; a version-matched EdgarTools skill pin; `backtest-expert`
on a frozen research task; a local scanner that passes the symlink fixture (P9); attribute each
`writing-for-agents` use to the file it served (P10).

## Addendum 2026-09-26: claude.ai skill sync and MCP servers off

**Decided by:** the user on 2026-09-26, quoted exactly: "disable the unused claude.ai skills and
the docs connector". A same-day request to also turn off the never-used user and plugin skills
was replaced before this change by "don't just mindlessly delete, but improve their usage", so
this addendum changes no `skillOverrides` state, no manifest entry and no Codex skill setting.

**Change.** `adoption/templates/claude.settings.template.json` sets `"syncClaudeAiSkills": false`
and, in `env`, `"ENABLE_CLAUDEAI_MCP_SERVERS": "false"`; `tools/adoption/apply_claude_settings.py`
carries both into an applied host's user settings. Upstream sources, read 2026-09-26:

- Claude Code docs, [Extend Claude with skills](https://code.claude.com/docs/en/skills): "To stop
  syncing on a machine, set `syncClaudeAiSkills` to `false` in your user settings. Claude Code
  stops downloading, and the next time it starts it moves the skills it already synced to
  `~/.claude/skills/.trash/` and no longer loads them."
- `anthropics/claude-code` `CHANGELOG.md` at `7779afb12e36` (2026-09-25), 2.1.275: "Added syncing of the skills and plugins enabled on
  your claude.ai account to terminal sessions signed in with it; opt out with
  `syncClaudeAiSkills: false` or `syncClaudeAiPlugins: false`"; 2.1.63: "Added
  `ENABLE_CLAUDEAI_MCP_SERVERS=false` env var to opt out from making claude.ai MCP servers
  available".

`syncClaudeAiPlugins` stays unset: the user did not ask for it, and the init event below lists no
claude.ai plugin (only the three marketplace plugins and two built-ins).

**Use before the change**, host `nativestack-5975wx-20260925`:

| Check | Evidence class | Result |
| --- | --- | --- |
| `/skill-doctor` baseline, 2026-09-25 ([above](#baseline-measurement--2026-09-25-host-nativestack-5975wx-20260925)) | Native operation | 8 synced (claude.ai sync) skills listed, none ever invoked. |
| Local Claude transcripts, scanned 2026-09-26T20:15Z | Scout measurement, not a receipt | 2,234 transcript files dated 2026-09-24 to 2026-09-26: 0 `mcp__claude_ai_*` tool calls, and none of the 384 `Skill` calls names an `anthropic-skills:*` skill or a synced skill folder. |

The scan covers under three days, the whole span of this host's local transcript store; it bounds
this host's use, not any other host's.

**Host read-back** (Claude Code 2.1.283, after both settings were applied on this host): a fresh
headless `/skill-doctor` run (0 turns, $0) opens with an init event that lists 8 MCP servers, none
from claude.ai, no `claude_ai` tool and no `anthropic-skills:*` skill or command, and its table has
no `claude.ai sync` row. A session started on the same host before the change lists the connector
as 8 tools, `mcp__claude_ai_Claude_Docs__` `batch`, `create`, `delete`, `export`, `guide`, `query`,
`read` and `update`.

**Effect on the selection rule.** [Rule 4](#selection-rule) counts the claude.ai skill sync as an
existing capability, and two [excluded groups](#excluded-groups) cite it: `pdf`, `docx`, `xlsx`
and `pptx` as duplicates of the synced copies, and `skill-creator` as a duplicate of the synced
copy and Codex's `.system/skill-creator`. Where this template applies, the synced copies no longer
load: the four document skills stay excluded on the user's finding that the synced skills went
unused, not because a loaded duplicate exists, and `skill-creator`'s remaining duplicate is the
Codex copy. The manifest's `excluded[]` text still names the synced copies; this addendum leaves
it for the 2026-10-25 review. On Claude, `writing-for-agents` no longer shares its skill-editing
trigger with a loaded `skill-creator`; that confound remains for Codex.

**Overturn.** A task that needs a claude.ai skill or the Claude Docs connector: change the value
in this template, not only on the host. `apply_claude_settings.py` lets template scalars win, so
a host-only change is overwritten at the next apply, and a key deleted from the template stays on
every host that already has it. `tests/test_render_config.py` pins both values in the rendered
template.

## Addendum 2026-09-26: listing state and agent preload

**Question.** Does a skill's `skillOverrides` state change whether an agent's frontmatter
`skills:` field can preload it? This matters because the listing policy above keeps on-demand
skills out of the listing to save context, while role agents preload their core skills.

**Upstream source.** Claude Code docs, [Create custom subagents, "Preload skills into
subagents"](https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents), read
2026-09-26: "You can't preload skills that set `disable-model-invocation: true`, since preloading
draws from the same set of skills Claude can invoke." The same section: "If a listed skill is
missing or disabled, for example by your organization's policy, Claude Code skips it and logs a
warning to the debug log."

**Probe.** Native operation on host `nativestack-5975wx-20260925` with Claude Code 2.1.283. Each
run was a headless `claude -p --model claude-sonnet-5 --settings <overlay> --agents <json>`
(prompt on stdin, since `--disallowedTools` is variadic) with two `haiku` probe agents. Each agent
preloaded one skill through `skills:`, had no tools, and was asked to quote the first Markdown
heading of any skill content in its context, or answer NONE. The overlay set only that skill's
`skillOverrides` state. The returned lines:

| Run | Skill | Overlay state | Agent's answer |
| --- | --- | --- | --- |
| 1 | `tdd` | `name-only` | `# Test-Driven Development` |
| 1 | `semgrep` | `off` | `NONE` |
| 2 | `semgrep` | `user-invocable-only` | `NONE` |
| 2 | `tdd` | `name-only` | `# Test-Driven Development` |

**Decision.** A skill that an agent preloads stays `on` or `name-only`. `name-only` keeps its
content out of the listing and still preloads. `user-invocable-only` and `off` both block the
preload, so `user-invocable-only` is kept for skills that no agent preloads: on this host,
`grill-me`, `improve-codebase-architecture` and `find-skills`. A grep of the user agents
directory, `.claude/agents/` and `adoption/agents/` found no agent that preloads any of the three,
so the host needs no change.

**Evidence class.** A native client operation on one host. The observation is the model's quoted
heading, not a receipt. Another host or client version re-runs the probe.

**Overturn.** Any Claude Code release note or docs change to preload eligibility, or a re-run of
the probe on a newer client that preloads a `user-invocable-only` skill.

## Addendum 2026-09-26: targeted role preloads (security-reviewer, isolated-builder)

The [stack-agent decision](2026-09-26-stack-agents-role-dispatch.md) adds a read-only
`security-reviewer` that preloads `security-best-practices` (openai/skills@49f948f,
`kept`, `Listing: on`), and gives `isolated-builder` a targeted preload of
`context-mode:context-mode` and `verification-before-completion` (obra/superpowers@8ca22db,
`trial`, `Listing: on`). `security-reviewer`'s named read tools match `evidence-reviewer`;
neither new configuration grants a Bash, Edit, Write, WebFetch or Skill tool beyond what
each role already carried. The skills add guidance, not tool permissions. No `semgrep` or
`codeql` preload is added: the first addendum above records that neither CLI is installed,
and neither reviewer runs acceptance commands.

All six dispatch roles now have an explicit preload decision:

| Agent | Preloaded skills | Basis |
| --- | --- | --- |
| `source-scout` | none | bounded extraction and named command results |
| `stack-researcher` | none | task-specific source research; read a named skill explicitly |
| `stack-verifier` | none | named checks and per-claim verdicts |
| `evidence-reviewer` | none | general source review with the existing named read tools |
| `isolated-builder` | `context-mode:context-mode`, `verification-before-completion` | context-mode plugin 1.0.169 is available and its `SKILL.md` sets no invocation-disabling frontmatter; `verification-before-completion` is `trial`, `Listing: on` above |
| `security-reviewer` | `security-best-practices` | pinned, `kept`, `Listing: on` above |

Per the ["listing state and agent preload" addendum](#addendum-2026-09-26-listing-state-and-agent-preload)
above, a skill preloads through `skills:` only at `Listing: on` or `name-only`;
`user-invocable-only` and `off` block it. All three preloaded skills here meet that bar. That
addendum's probe covers a pinned, table-listed skill; `context-mode:context-mode` is a
plugin-scoped skill outside the pinned table, so its eligibility rests on the same upstream
mechanism (no `disable-model-invocation` field in its installed `SKILL.md`) rather than a
repeat of the probe on a plugin skill specifically. The local integration test
(`tests/test_install_claude_profile.py`) checks every shipped agent's preload against this
table's `Listing` column, and checks a plugin-scoped name only for its `plugin:skill` shape,
not installation or native preload success.

Native viability for `context-mode:context-mode` and `verification-before-completion`
therefore rests on the probe above and the absent-disabling-field check, not a repeat native
run of these two skills specifically; first-prompt size for all three preloaded
configurations is unmeasured. They join the researcher/verifier preregistration in the
stack-agent decision; no default preload is added to every role child (that decision's own
D3 constraint, narrowed rather than reversed).

## Addendum 2026-09-27: security-audit trial row, stale-upstream flags, sandbox gate

Evidence: [`evidence/artifacts/cloudflare-audit-skill-trial-20260927/`](../../evidence/artifacts/cloudflare-audit-skill-trial-20260927/README.md).
`delta.json` records the pin and its file hashes, each fetched page's size and sha256, and every
passage quoted here with its file or URL and line (`quoted_passages` holds the skill, schema and
repository quotes). Repository mechanics cited without a quote are read at the base commit. The
upstream reads ran on 2026-09-28 between 02:03Z and 02:18Z (UTC), which is the evening of
2026-09-27 on the host (EDT). A review repair round read again, between about 03:05Z and 03:17Z,
the pinned `SKILL.md` (same sha256), `report-schema.json` (same size as the tree listing), the
settings reference, the sandboxing page and the Trust Hub audit page (each the same bytes and
sha256), and read the local `claude plugin eval --help` (Claude Code 2.1.283). A second repair
round, at 07:07Z on 2026-09-28 (03:07 EDT, so 2026-09-28 on the host), fetched the skills page, the
settings reference and the commands reference again with curl (each the same bytes and sha256) and
corrected the invocation claims (`checks.repair_round_2`). Dates below are host dates.

**Decided by** the user on 2026-09-27: no user invocation; the skill runs through LLM-native
automation (workflow stages), with the full trial, and the bake-off only if it proves suitable,
under the token-saving stack for every run. The bake-off budget is high but waits until the
token-saving practice passes end to end with real evidence (Gate A) and, per the plan of record,
the GPT-6 route is settled (Gate B). Settings enforce neither restriction (no user invocation,
workflow stages only). The wiring below carries both as a usage policy, and the `name-only` listing
leaves the skill invocable by the user and by the model (see **LLM-native wiring** and its
enforcement residual).

**Added for trial**, under the [selection rule](#selection-rule):

| Name | Source @ ref | Status | Listing | Codex | Gap |
| --- | --- | --- | --- | --- | --- |
| security-audit | cloudflare/security-audit-skill@c1c8a8c | trial | name-only | no | No installed procedure audits the whole repository with a coverage ledger and a `confirmed`/`needs_validation`/`rejected` verdict contract (restated below). |

Pin facts, read with `gh api` at the pin:

- `c1c8a8c` is still `main`'s HEAD, committed 2026-09-14.
- `skills/security-audit` is git tree `ccbc33e` at the pin and at HEAD: 20 files, 314,670 bytes,
  including two Node validators and their tests.
- `SKILL.md` is 22,026 bytes (blob `92178da`, re-hashed locally). Its frontmatter holds only `name`
  and `description`, so upstream does not disable model invocation. The description is 359
  characters (PyYAML 6.0.3, the manifest's method).
- License: MIT, from the repository `LICENSE` at the pin. The installed folder carries no license
  file.
- `official` is true by the manifest's owner-scoped convention: https://skills.sh/official lists the
  `cloudflare` owner, as it lists `vercel-labs` for both `vercel-labs` rows.

**Rule 3: audits re-observed.** The skills.sh page and its three audit pages:

| Audit | Page label | Audit page | Audit API (`add-skill.vercel.sh/audit`) |
| --- | --- | --- | --- |
| Gen Agent Trust Hub | Pass | "Risk Level: SAFE"; lists COMMAND_EXECUTION, DYNAMIC_EXECUTION and INDIRECT_PROMPT_INJECTION (the Node validators, untrusted target code) | `ath` risk `safe` |
| Socket | Pass | Pass, analyzed 2026-09-15 | `socket` risk `safe`, 0 alerts, score 90 |
| Snyk | Warn | "W011: Third-party content exposure detected (indirect prompt injection risk)", MEDIUM, "medium risk: 0.30" | `snyk` risk `medium` |

All three were analyzed on 2026-09-15, after the pin became HEAD on 2026-09-14; no page names the
revision it scanned. A Warn is not a Fail and does not exclude ([rule 3](#selection-rule)). W011
describes the skill's purpose, reading untrusted code. The wiring below keeps its listing name-only
and starts it from workflow stages by usage policy. It does not stop a user or the model from
invoking the skill by name.

**The 2026-09-23 `not_adopted` proposal and its refutation.** The 2026-09-23 landscape sweep
proposed `not_adopted` with "No demonstrated gap. The native /security-review and
security-best-practices skills already cover security review." Both refuters voted it refuted, so it
did not survive. The citation critic asked the next pass to restate the gap with the qualification
from `docs/native-skill-practice-20260921.md:13` ("security findings and false-positive control
remain unqualified") and to "state whether the candidate closes the qualification gap"
(`catalogs/sota-convergence/manifest-20260923.json`, lines 6035-6060 and 17195-17201; that dated
file is not edited). The restated gap, from the Claude Code
[commands reference](https://code.claude.com/docs/en/commands), read 2026-09-27:

- `/security-review` "Reviews the diff between your branch and origin's default branch". It is
  diff-scoped.
- `/code-review` reviews "the current diff, or a PR number, branch, or path you pass, for correctness
  bugs". It can take a path, but its subject is correctness, not security.
- `security-best-practices` is framework guidance. Its catalog record says "The skill is not a full
  security audit" (`catalogs/landscape/native-practice.json`).
- None of the three documents a whole-repository coverage ledger or a per-finding
  `confirmed`/`needs_validation`/`rejected` contract. The pinned skill defines both and checks them
  with `validate-coverage-ledger.cjs` and `validate-findings.cjs`.

Whether the skill closes the qualification gap (useful findings with controlled false positives) is
unknown: nothing has been measured here. The M5c bake-off below is the 2026-09-23 overturn condition
itself.

**Third-party evidence, weak.** [Issue #20](https://github.com/cloudflare/security-audit-skill/issues/20)
is open, filed 2026-09-16 by an account with no association to the repository, and reports one
blind comparison. Quoted, emphasis removed:

- "n = 3 per arm, one target".
- For the skill, "precision held at a median of 90% across rounds, zero hits on either deliberate
  look-alike decoy in any round".
- "median cost per run ...: the skill's quick profile $29.95, a plain single-agent review $2.06, a
  multi-lens review pipeline of ours $7.66", with quick's median recall equal to the single-agent
  review's ("0.467 vs 0.467, on 15 seeds").
- "Disclosure: the multi-lens pipeline is our own tool, so we have an interest here".

The issue says only "pinned to a recent commit", never which. One seeded target, three rounds and an
interested author make this a discovery signal for the M5c design, not evidence of merit.

**LLM-native wiring.**

- **Listing `name-only`.** "Claude sees the skill by name without its description" (settings
  reference, `skillOverrides`). Workflow stages and the model can invoke it by name. Its broad
  description, which says "Use for security questions", stays out of the listing. That narrows what
  Claude sees, not who can invoke the skill:
  - The model can still pick the skill by name on any prompt, an ordinary security question
    included: "By default, Claude can invoke any skill that doesn't have
    `disable-model-invocation: true` set." How often it would without the description is
    unmeasured.
  - The skills page's [visibility table](https://code.claude.com/docs/en/skills#override-skill-visibility-from-settings)
    gives `name-only` as "Name only" to Claude and "Yes" in the column "In `/` menu", so a user can
    still type `/security-audit`.
  - Running it only from workflow stages is therefore a usage policy that the stage prompts carry,
    not a guarantee.
  - No `skillOverrides` state hides the `/` entry and keeps the skill listed to Claude. Only `off`
    hides the `/` entry, and then "Claude doesn't see the skill and `/name` is hidden from
    autocomplete". Invoking such a skill "by its full name still returns the `skillOverrides` error
    instead of running it", so `off` would stop the workflow stages too.
  - `user-invocable-only` is not used: the user rejected user invocation, "Claude doesn't see the
    skill" in that state, and it blocks agent preloads ([listing state and agent
    preload](#addendum-2026-09-26-listing-state-and-agent-preload)).
- **Enforcement residual (the user trigger only).** The native control for the user trigger is
  frontmatter: with `user-invocable: false`, "Claude Code hides it from the `/` menu and doesn't
  run it when you type `/name`". The field leaves Claude's own invocation on: "With
  `user-invocable: false`, you can't invoke the skill, but Claude still can." Keeping Claude from
  invoking it takes `disable-model-invocation: true`, which "removes the skill from Claude's
  context entirely", so the session that drives the stages could not load it either. Stage-only use
  therefore stays a usage policy with or without either field. The pinned `SKILL.md` has neither
  field, and the install is as-is: `tools/adoption/install_skills.py` counts an installed
  `SKILL.md` as current only when its sha256 matches the pin (`classify_skill`) and rolls back an
  add that does not match, so a local frontmatter edit would break the pin. Removing the user
  trigger therefore needs a new upstream pin. Even then, the docs do not say how the field combines
  with a `name-only` override; their invocation table gives `user-invocable: false` a "Description
  always in context". A native probe of the combination comes before any claim that the user
  trigger is gone.
- **No agent preload.** `SKILL.md` alone is 22,026 bytes and the folder 314,670. Stages paste the
  companion blocks they need, as the skill intends: `HUNTING.md` and `VALIDATION-AND-REPORTING.md`
  "carry this procedure as one identical fenced block for hunter and verifier prompts". The six-role
  preload table above is unchanged.
- **Guidance by default.** Upstream says: "This skill is guidance by default. Loading it does not
  authorize the complete audit workflow or file creation." A stage runs full audit mode only when its
  prompt asks for it explicitly, with a profile, scope, budget and an output directory outside the
  target.
- **Parent and children.** The skill is "agent-neutral": its "Task tool" is "the platform's
  delegation or sub-agent mechanism". A headless coordinator session is the parent and maps that to
  the Agent tool. Hunters are its direct children, because spawn depth is 1.
- **Sandbox.** Upstream says: "If every control cannot be enforced, do not execute target code:
  report the missing sandbox capability as a needs-validation blocker". Without a measured sandbox
  profile, execution-dependent leads stay `needs_validation`. Those dated blockers are the pressure
  evidence for the foundation open gate `claude-code-sandbox-profile` in
  `catalogs/foundation/manifest.json`.
- **Codex off.** Codex's `[[skills.config]]` has only `enabled`, with no name-only state. Enabled,
  Codex would list the 359-character description and could fire it on any security question. No M5
  arm uses Codex as the skill's parent; the GPT-6 lane is the cross-family verifier. The manifest
  schema requires only a boolean, so `false` needs no schema change. `tools/adoption/install_skills.py`
  still installs the folder for both agents, so the table from `--print-codex-config` goes into
  `~/.codex/config.toml` before the install.

**M5b: suitability gate.** The bake-off runs only if all three hold:

1. The unchanged upstream `node --test validate-findings.test.cjs validate-coverage-ledger.test.cjs`
   passes at the pin.
2. A labelled fixture exists. An upstream labelled set comes first. Otherwise, use a pre-registered
   seeded copy of `scripts/`, `.github/workflows` and the installers, with known-pass, known-fail,
   malformed and decoy controls, labelled as a local integration.
3. The user sets a per-run budget.

If any fails, record the reason and move the row to watch.

**M5c: bake-off.** Queued behind Gate A and Gate B, with a high budget (user, 2026-09-27).

- Arms, 3 runs each:
  1. the unchanged skill, `quick` profile, source-only;
  2. bundled `/security-review` on a branch that introduces the seeds;
  3. a plain single-agent control.
- Harnesses, all upstream: skill-creator's paired with-skill/without-skill benchmark, Harbor for
  native transcripts, and scipy `bootstrap`/`permutation_test` for the statistics. No self-written
  scorer.
- A native paired candidate runs beside skill-creator's benchmark. It comes from a 2026-09-27 peer
  practice sweep and from [M9 of the 2026-09-24 community sweep](2026-09-24-community-sweep.md#keep-but-compare):
  `claude plugin eval --ablation with-without --model claude-opus-5-5 --judge-model <model> --no-publish --json <path>`.
  - The judge must not be Haiku. The help (Claude Code 2.1.283) says "Override LLM-grader model
    (default: haiku)", so `--judge-model` must name another model.
  - Record the resolved model from the `--json` result. If the result does not name it, record that
    gap.
  - The help ties the baseline arm to a plugin: "default: with-without whenever a plugin resolves —
    by name, or from the target path — and none when nothing does". This skill installs through the
    skills CLI, not as a plugin, so the `--json` result must show that the no-plugin baseline arm
    ran, or the arm does not count. The 2026-09-24 sweep lists `claude plugin eval` as "named in M9
    but not qualified".
- Scores: recall at equal false positives; precision and decoy hits; complete provider usage,
  including failed attempts; wall time.
- Promote only if the skill beats `/security-review` on recall at equal false positives. Otherwise,
  exclude it with the numbers and keep the method as a cited reference.

**M6: sandbox open gate.** The foundation open gate `claude-code-sandbox-profile` in
`catalogs/foundation/manifest.json` carries the whole measurement list:

- the deferral's three controls ([2026-09-24 secret storage](2026-09-24-secret-storage.md), lines
  91-95): `sandbox.enabled`, `allowUnsandboxedCommands: false`, and the `credentials.files` deny.
  In current settings that deny is a `sandbox.credentials.files` entry with mode `deny` for the
  store;
- `failIfUnavailable`, the host check, and the refusals of writes outside the worktree and of
  `/mnt/c` launches;
- a credentials arm: with filesystem isolation on, a sandboxed read of a store file fails through a
  `~/` path and through its absolute path. The sandboxing page says "The file protection is part of
  the filesystem layer", so the deny does not apply when filesystem isolation is off;
- a separate `strictAllowlist` arm. With it false, the settings reference leaves a host outside the
  allowlist to the permission mode, and "in `bypassPermissions` mode and in interactive terminal
  plan-mode sessions where bypass is available it allows" it. The ungated permission profile stays
  by user decision (PS-1 in `docs/harness-rules-convergence-20260922.md`);
- the deferral's gh, git push, codex, paper-runner and systemd-bus items.

The two extra arms come from a 2026-09-27 peer practice sweep. `adoption/manifest.json` now lists
the gate in `continuation.next_action_refs`, as it listed each open foundation gate before
(`d17b3cff` and `49c094d9` kept the two lists together), so a resumed task or a new host meets it at
the entry point. `tests/test_adoption_contract.py` checks only that the list is a subset of the open
gates, so this listing rests on that precedent, not on a failing test.

**Trial exit and overturn.**

- An M5b failure moves the row to watch. An M5c loss moves it to `excluded[]` with the numbers. An
  M5c win goes to a sealed verdict re-record ([verdict boundary](#verdict-boundary)).
- Its prune window starts at its own install on each host, so it is not a prune candidate at the
  2026-10-25 review.
- Remove it at once if any audit turns to Fail.
- Re-decide the listing if a new pin changes the description or adds `disable-model-invocation`,
  or if a native probe shows that a workflow stage cannot invoke a `name-only` skill by name.
- Close the user-trigger residual only when a native probe on one host shows both halves: a typed
  `/security-audit` does not run, and a workflow stage still invokes the skill by name. The
  candidates are a new pin that adds `user-invocable: false`, probed together with the `name-only`
  override, or a future `skillOverrides` state with that effect. Closing it does not make
  stage-only use enforced: Claude can still invoke the skill unprompted, so that stays a usage
  policy.
- Re-decide Codex if Codex gains a name-only state.

**Stale upstreams, flagged for the next verdict wave** and re-observed with `gh api` on 2026-09-27.

`openai/skills`:

- `main`'s HEAD is still `49f948f` (2026-06-24), the pin of `gh-fix-ci`, `security-best-practices`,
  `security-threat-model` and `gh-address-comments`.
- `main` has had 0 commits since 2026-06-29. The repository's `pushed_at` of 2026-09-08 is not on
  `main`.
- The manifest's skill rows have no notes field, so the note lives here: the next verdict wave
  fields a challenger for the kept `security-best-practices` and the trial `security-threat-model`.

`praetorian-inc/noseyparker`:

- Archived on 2026-04-24. Last push 2026-02-21; last release v0.24.0 (2025-05-08).
- Its README opens: "Nosey Parker is now Replaced by Titus. Nosey Parker is Officially Retired".
- No current catalog presents it as a survivor or candidate. It appears only in dated records:
  - `evidence/artifacts/landscape-sweep-20260926/`;
  - `catalogs/sota-convergence/manifest-20260926.json`;
  - the 2026-09-26 sweep in `catalogs/saturation/ledger.json`. That ledger is append-only and
    hash-chained ("Editing, reordering or deleting a record breaks the chain",
    `scripts/saturation_ledger.py`).
- The correction is therefore recorded here:
  - the 2026-09-26 sweep's facts vote passed a repository archived five months earlier;
  - `manifest-20260926` carries it into the verdict wave as a `secrets-credentials` survivor;
  - the ledger learns of it only through the next sweep's record.
- The verdict wave should refute it on facts.

**Evidence class.**

| Item | Class | Basis |
| --- | --- | --- |
| Pin identity, tree, `SKILL.md` hash, license, quoted upstream and docs text | upstream-unchanged | `gh api` and page reads at the pin; proves identity and wording, not behavior |
| skills.sh labels, audit pages, audit API | upstream-unchanged (independent observation) | Another platform's 2026-09-15 scan; not this repository's behavior |
| Issue #20 numbers | upstream-unchanged (third-party report, weak) | One seeded target, n = 3, an interested author |
| `claude plugin eval --help` lines | upstream-unchanged (local native client help, Claude Code 2.1.283) | Wording only; the arm itself is not qualified |
| Manifest row, template key, foundation gate, tests, `scripts/validate.py` | our-integration | Structural checks, each with a failing control run first |
| Gate listed in `adoption/manifest.json` `next_action_refs` | our-integration | Precedent check (`d17b3cff`, `49c094d9`); no test fails without it |
| Install, settings apply, Codex disable, host read-back | our-integration, with Claude Code's own `/skill-doctor` as the native read-back (one host, 2026-09-28) | [security-audit-host-install-20260928](../../evidence/artifacts/security-audit-host-install-20260928/README.md): `installed`, every `skills_status` check `ok`, listing `name-only` at 20 context tokens. The Codex disable went in 10 s after the install, not before |
| M5b gate 1: the unchanged upstream `node --test` at the pin | upstream-unchanged (one host, 2026-09-28) | Same receipt: 65 of 65 pass on Node v24.21.0. The four test and validator files match the pin byte for byte |
| `name-only` invocation reach (a typed `/security-audit`, unprompted model invocation), M5b gates 2 and 3, M5c, sandbox measurement | live-run-pending | M5c waits for Gate A and Gate B; no labelled fixture exists yet |

## Addendum 2026-09-28: carrier conditions and the verification review rule

**Why the trial needs this.** The TOKEN LANES carrier
([decision](2026-09-27-token-lanes-subagent-start.md)) adds text to a subagent's start context
through `SubagentStart`. From its first revision, that text told children to follow
`verification-before-completion` and to research with `search-first`. An instruction that names a
skill can raise its use count with no change in the skill's listing or usefulness, so the
[name-only confound](#listing-policy) ("compare only within a listing state") gains another
dimension: the instructions a child receives. The carrier is one source; the landscape-sweep
templates and two role changes are others (other sources and role changes, below). This
addendum logs these conditions and adds a comparison to the review of
`verification-before-completion`'s Claude listing. It changes no `skillOverrides` state, no
manifest entry (the prune rule included) and no agent preload.

**Condition log.**

| Condition | Carrier revision (merge, UTC) | What children's start context says about the two skills |
| --- | --- | --- |
| C0 | none | nothing from the carrier |
| C1 | [#378](https://github.com/seathatflowsinourveins/native-agent-stack/pull/378), `0c33b37a` (2026-09-27T06:11:54Z) | every non-blind child: "follow the installed verification-before-completion skill: real command output before any success claim", then the `search-first` sentence; #412 and #421 left both instructions unchanged |
| C2 | [#447](https://github.com/seathatflowsinourveins/native-agent-stack/pull/447), `f508ffba` (2026-09-28T03:39:00Z) | default-block types: both sentences; `isolated-builder`: the verification sentence only; `stack-researcher`, `stack-verifier`, `evidence-reviewer`, `security-reviewer` and `source-scout`: neither; `semantic-evidence-reviewer` and `blind-*` types: nothing ([role-matched addendum](2026-09-27-token-lanes-subagent-start.md#addendum-2026-09-27-role-matched-blocks)) |
| C3 | the [verification-line addendum](2026-09-27-token-lanes-subagent-start.md#addendum-2026-09-28-verification-line), dated 2026-09-28 and merged with this addendum | default-block types: an evidence sentence that names no skill, then the `search-first` sentence; no role block names either skill |

**Boundaries.** A host changes condition when `tools/adoption/install_claude_profile.py`
installs a revision, not at its merge: the hook reads the block files installed beside it. The
installer writes no install record, and its `shutil.copy2` (L113 for hooks, L143 for agents)
keeps the source file's modification time; #381's frozen procedure records hashes, not install
times. The one install time this repository records is the C1 install that the coordinator
reported for its local measurement: 08:26:32Z on 2026-09-27, from `main` at `5f3a7c21`
([measured-gap addendum](2026-09-27-token-lanes-subagent-start.md#addendum-2026-09-27-measured-fetch-and-containment-gaps)).
The review therefore assigns a window to a condition only from a host's own record of its
installs, and it reports a window that crosses an unrecorded boundary as mixed. A separate
boundary lies inside C0: `isolated-builder` has preloaded the skill, and its body has named it,
since [#376](https://github.com/seathatflowsinourveins/native-agent-stack/pull/376) (`623d34fa`,
merged 2026-09-27T03:38:47Z; the
[targeted role preloads](#addendum-2026-09-26-targeted-role-preloads-security-reviewer-isolated-builder)
addendum). On a host, that boundary is when `install_claude_profile.py` installed the agent
definition. This record does not establish whether `/skill-doctor` counts a preload as a use.

**Other sources and role changes.**
- The landscape-sweep templates name both skills in every sweep worker's prompt from `1b0e4598`
  (2026-09-26T05:08:52Z) onward: "Discovery: search-first ... Refutation:
  verification-before-completion (evidence before any verdict)"
  ([`templates.json`](../../tools/sota-convergence/landscape-sweep/templates.json), `common`;
  `TEMPLATE_SKILLS` in [`build_args.py`](../../tools/sota-convergence/landscape-sweep/build_args.py)
  L59). The Claude workers and the GPT-6 lane, which composes its prompts from the same templates,
  both receive them, and no carrier revision changes them. In the C0 baseline window, when no child
  received `SubagentStart` context, 120 workflow-subagent children in one session made 108
  `verification-before-completion` and 46 `search-first` Skill calls
  ([child-lane baseline](../../evidence/artifacts/child-lane-baseline-20260926/README.md#results-claude-children-639-in-7-sessions)).
  That set matches the templates' Discovery and Refutation list, which is consistent with
  template-driven use but does not prove it.
- [#398](https://github.com/seathatflowsinourveins/native-agent-stack/pull/398) (`54834120`,
  merged 2026-09-27T14:27:46Z) moved the sweep's Claude judgment stages to the
  `landscape-sweep-worker` type on Opus, `refute-facts` from Sonnet. Earlier sweep children carry no
  such type, so the sweep's own run records identify them.
- [#402](https://github.com/seathatflowsinourveins/native-agent-stack/pull/402) (`d022295a`,
  merged 2026-09-27T14:04:25Z), inside C1, moved `isolated-builder` from `model: sonnet` with
  `isolation: worktree` to `model: opus` without frontmatter isolation.

**Review rule, 2026-10-25.** The review splits each skill's uses by host and condition, within
its listing state. On each client it reports sweep workers apart from other children, and it
reports builder uses before and after each host's #402 install apart. For
`verification-before-completion`'s Claude listing (`trial`, `on`, preloaded by
`isolated-builder`), a Claude use count does not show usefulness: under C1 and C2 the carrier
prompted its use, the sweep templates prompt it, and the builder's preload delivers its content
without a `Skill` call. The review therefore adds a with/without comparison that varies that
preload on frozen builder tasks, run through an upstream evaluation harness that the review record
names with its pin before the run, comparing tokens, elapsed time and review-found defects. The
count rule still applies as written: this addendum changes no manifest entry, and
`tools/skill-usage/skill_usage.py` (L516-538) lists a trial skill as a prune candidate when every
evaluated client shows zero uses and the skill is at least `window_days` old. Codex enablement
stays under that rule, read with the sweep split. If the comparison and the count rule disagree
for the Claude listing, the review writes the resulting exception or demotion into the manifest
update and follow-up decision record that the [trial window end](#overturn-conditions) already
requires. `search-first` is a `kept` verdict winner: its split usage is reported, and it changes
only through a verdict re-record, as the prune rule already states.

**Evidence class.** The condition log and the other sources are structural: merge commits, block
files, templates and agent definitions at each revision. The C0 counts are the baseline's
retained measurement, quoted as such. This addendum makes no new measurement of use and claims no
review result.

## Addendum 2026-09-28: host listing drift restored

Evidence: the receipt
[`skills-listing-restore-20260928`](../../evidence/receipts/skills-listing-restore-20260928.json)
holds the failing pre-edit run, the edit, the passing post-edit run and the settings-backup states.
[`evidence/artifacts/skills-listing-restore-20260928/`](../../evidence/artifacts/skills-listing-restore-20260928/README.md)
holds the `supply-chain-risk-auditor` tree check and its five controls.

**Decided by** the coordinator, on the user's 2026-09-28 delegation, quoted exactly:
"the decision should make with evidances andrsearch covnvergence, they should done in your end as you have have full access to them".
A coordinator decision workflow (three lens proposals, a synthesis and an adversarial refute)
produced the per-skill verdicts. The refute upheld all 15 and listed defects in the drafted
record, which this addendum resolves. The coordinator reads the delegation as also covering the
host edit; this record holds no separate approval of that edit. The earlier host edit of
2026-09-28 was different: `2026-09-28-community-sweep.md` (line 117) records it as applied "with
the user's approval".

**What drifted.** Fourteen skills that the manifest, the settings template and the
[trial table](#the-26-pinned-skills) list `on` read `name-only` in this host's user settings:
`agentic-actions-auditor`, `codeql`, `diagnosing-bugs`, `frontend-design`, `gh-address-comments`,
`gh-fix-ci`, `modern-python`, `resolving-merge-conflicts`, `sarif-parsing`,
`security-best-practices`, `security-threat-model`, `semgrep`, `tdd` and `variant-analysis`. No
version of the manifest (6 versions), the template (32) or `.claude/settings.json` (11) in any
ref's history (`git log --all`, read 2026-09-28) sets any of them to a state other than `on`. No
decision record authorizes the change; the
[2026-09-28 community sweep](2026-09-28-community-sweep.md) notes it as drift (lines 174-175). The
settings backups, read value-free with `scripts/skills_status.py`'s own reader, split this host's
history into segments:

| Segment | Bounds (UTC) | Backup reading |
| --- | --- | --- |
| `on` | Read at 2026-09-26T20:00:20Z, the earliest backup read. The installs were earlier: 2026-09-25T04:15Z for the two kept skills, 22:50Z-22:51Z for eleven trial skills and 2026-09-26T09:33Z for `variant-analysis` | `settings.json.20260926T200020Z.pre-skills-off`: 13 of the 14 set `on`, `variant-analysis` absent (so `on`), `writing-for-agents` absent |
| `off` | Began after 20:00:20Z and held at 20:12:39Z | `settings.json.20260926T201239Z.pre-skills-nameonly`: the 14 `off`, with `agent-browser`, `grill-me` and `improve-codebase-architecture` (17); `codebase-design`, `verification-before-completion`, `supply-chain-risk-auditor`, `property-based-testing`, `fp-check` and `mcp-builder` `on` |
| `name-only` | From about 20:12:39Z to 2026-09-28T15:09:02Z, at most 42.94 hours | `settings.json.bak.20260927T053110Z.agent-teams` and the pre-restore backup: the 14 `name-only` |
| `on` | From 2026-09-28T15:09:02Z | The restore below |

- Each backup is named for the edit that followed it, so the `off` segment lasted about 12
  minutes. The stamps are bounds; the edit times are inferred from the labels.
- Two Codex backups from the same minutes exist, `codex-config.toml.20260926T200118Z.pre-skills-off`
  and `.20260926T201239Z.pre-skills-reenable`. Their content was not opened. Both status runs below
  find the Codex disable entries matching the manifest.
- `variant-analysis` was installed about 10.45 hours before the first backup read, which holds it
  absent (`on`). Its own first window, which starts at its install on each host
  ([first 2026-09-26 addendum](#addendum-2026-09-26-two-trial-additions-one-deferral-corrected-counts-on-disk-tree-check)),
  also crosses the `off` and `name-only` segments.
- None of the 14 had a lifetime use at the restore, so every earlier segment holds zero uses.
- The [claude.ai sync addendum](#addendum-2026-09-26-claudeai-skill-sync-and-mcp-servers-off)
  records that, before its change, a same-day request to turn off the never-used user and plugin
  skills was replaced by "don't just mindlessly delete, but improve their usage", and that it
  changed no `skillOverrides` state. The host edits themselves, who made them and the user's fuller
  words are recorded only in a coordinator memory note: untrusted history, not evidence.

**What the drift changed.**

- `tools/skill-usage/skill_usage.py` takes each skill's listing label from the manifest (L469) and
  its age from the lock's `installedAt` (L473-479), so it kept labelling the 14's counts `on`. With
  zero lifetime uses (L537-558), it would list the eleven 2026-09-25 trial skills under
  `prune_candidates` from 2026-10-25T22:50:51Z to 22:51:17Z (per install), `gh-fix-ci` and `security-best-practices` under
  `verdict_recheck` ("verdict re-record required") from 2026-10-25T04:15:04Z, and
  `variant-analysis` from 2026-10-26T09:33:36Z.
- Two kept verdict winners changed listing without the verdict re-record that the prune rule
  requires.
- Zeros counted at `name-only` or `off` entered a comparison that the
  [name-only confound](#listing-policy) limits to one listing state.

**Change, this host only.** At 2026-09-28T15:09:02Z, after a backup labelled
`settings.json.20260928T150902Z.pre-listing-restore`, a script that touches only `skillOverrides`
set the 14 to `on`. It also added an explicit `"writing-for-agents": "on"`, the key the template
already writes (`adoption/templates/claude.settings.template.json` L341). An absent key already
means `on`, so that key changes no behavior; the key count went from 28 to 29. The script's
assertions held: the top-level key list, every other override, and all 15 at `on`. The manifest,
the template and `budget.claude_on_description_chars` (7,409 of the 8,000-character cap) are
unchanged, because they already say `on`.

**Read-back** ([receipt](../../evidence/receipts/skills-listing-restore-20260928.json)). Context
figures are `/skill-doctor`'s listing-cost estimates
([Mechanics](#mechanics-source-review-skills-cli-v170)), not provider counts.

| Skill | Status | Before: listing, context | After: listing, context | Lifetime uses |
| --- | --- | --- | --- | --- |
| agentic-actions-auditor | trial | name-only, 20 | on, 200 | 0 |
| codeql | trial | name-only, 20 | on, 250 | 0 |
| diagnosing-bugs | trial | name-only, 20 | on, 60 | 0 |
| frontend-design | trial | name-only, 20 | on, 70 | 0 |
| gh-address-comments | trial | name-only, 20 | on, 60 | 0 |
| gh-fix-ci | kept | name-only, 20 | on, 110 | 0 |
| modern-python | trial | name-only, 20 | on, 60 | 0 |
| resolving-merge-conflicts | trial | name-only, 20 | on, 30 | 0 |
| sarif-parsing | trial | name-only, 20 | on, 130 | 0 |
| security-best-practices | kept | name-only, 20 | on, 140 | 0 |
| security-threat-model | trial | name-only, 20 | on, 150 | 0 |
| semgrep | trial | name-only, 20 | on, 240 | 0 |
| tdd | trial | name-only, 20 | on, 50 | 0 |
| variant-analysis | trial | name-only, 20 | on, 200 | 0 |
| writing-for-agents | trial | on (key absent), 40 | on (explicit key), 40 | 2 |

- Before (captured 15:08:39Z), `python3 scripts/skills_status.py --json` exited 1 with result
  `fail`: 14 `claude_listing` mismatches, and every other required check `ok`. This failing run is
  the discriminating control for the passing one.
- After (captured 15:09:12Z), the same command exited 0 with result `ok` and 0 mismatches.
- `python3 tools/skill-usage/skill_usage.py --run-skill-doctor --json` exited 0 both times. Both
  `/skill-doctor` runs made 0 model turns at $0, so neither could add a use. The 15 read 320
  context tokens before and 1,790 after; the 14 went from 280 to 1,750 (+1,470).
- `skills_status.py` reads only the user settings file. `/skill-doctor` reports on the skills in
  the session (the skills page's "Find unused skills"), and its report shows the same change.

**Per-skill result.** All 15 are `on`, on this host only. The manifest sets the listing states,
which the template's `skillOverrides` must equal, and no authorized path moved these 14.
`gh-fix-ci` and `security-best-practices` are kept verdict winners, which change only through a
sealed verdict re-record. `on`, like `name-only`, stays preload-eligible
([listing state and agent preload](#addendum-2026-09-26-listing-state-and-agent-preload)).

**Upstream guidance and the tiebreak.** Claude Code's
[skills page](https://code.claude.com/docs/en/skills) (read 2026-09-28) makes two
recommendations:

1. `/skill-doctor` "flags skills in the listing that have never been invoked and says where to
   turn them off. Of the skills it tells you where to turn off, start with the ones that have the
   highest context cost."
2. "To free budget for other skills, set low-priority entries to `"name-only"` in
   `skillOverrides` so they list without a description."

The same page says a dropped description "removes the keywords Claude needs to match your
request". The trial's own rules decide the timing. The 30-day window, the one-step prune rule and
the confound rule (`adoption/skills/manifest.json` L26-31) apply the first recommendation at the
window's end. P2 defers its own demotion because "a listing change mid-trial would confound the
within-state comparison, so it waits for the review"
(`evidence/artifacts/skills-agents-layer-20260926/delta.json` L4227, cited below as `delta.json`).
The second recommendation applies when the listing overflows its budget, which scales at 1% of the
model's context window. Whether it overflows in a smaller-window child is unmeasured (overturn
condition 1). How often Claude picks a `name-only` skill on its own is not found in the skills page
or the settings reference. The nearest statement is about descriptions dropped for budget, which
leave Claude "less likely to choose one on its own"
([settings reference](https://code.claude.com/docs/en/settings-reference),
`skillListingBudgetFraction`, read 2026-09-28). That is an analogue for `name-only`, not a
statement about it.

**Name-only use.** `iterative-retrieval` and `search-first` are `name-only` and still used (58 and
66 lifetime uses). That is consistent with instruction-driven use but does not prove it. The
landscape-sweep templates name both (`TEMPLATE_SKILLS`,
`tools/sota-convergence/landscape-sweep/build_args.py` L59). For `search-first` and
`verification-before-completion` only, the
[carrier addendum](#addendum-2026-09-28-carrier-conditions-and-the-verification-review-rule) finds
the C0 Skill calls "consistent with template-driven use but does not prove it". `delta.json` L4372
draws the contrary reading: "a name-only listing does not by itself prevent invocation when the
name is descriptive".

**Observational counts.** Lifetime `/skill-doctor` uses after the restore:

- Skills listed `on` with uses: `verification-before-completion` 153, `supply-chain-risk-auditor`
  135, `fp-check` 89, `codebase-design` 5, `property-based-testing` 3, `writing-for-agents` 2 and
  `mcp-builder` 1.
- `name-only` skills with uses: `search-first` 66 and `iterative-retrieval` 58.
- The 14 restored skills: 0.

These counts are observational, not causal: preloads, templates and instructions also drive uses.

**`semgrep` and `codeql`.** Both go back to `on` with the other twelve. P2 ("Unless pinned semgrep
and codeql CLIs are adopted, demote the semgrep and codeql trial skills to name-only", `delta.json`
L4225) names both without ranking them, and it names its own paths: the "2026-10-25 review or a
verdict re-record" (L4224). In one shell on this host at 2026-09-28T15:42:00Z,
`command -v semgrep` and `command -v codeql` each exited 1 (the receipt's `local_checks`), so
neither was on that shell's `PATH`. P2's condition therefore stands for the review.

- **Dissent, recorded.** Move both to `name-only` now, through the manifest, template and budget,
  because upstream says to start with the highest context cost (240 and 250 tokens). It lost. An
  addendum is neither of P2's paths, and P2 waits to avoid the confound. The docs set no evaluation
  window, while the trial sets 30 days. A template or manifest change would also move every host's
  declared state, not only this host's.
- **Correction to the dissent's early path.** Measured harm before the review removes the skill at
  once under this record's [overturn conditions](#overturn-conditions), which prescribe removal,
  not demotion. This addendum counts as harm a misfire, or an invocation that fails on the missing
  CLI and costs a turn. P2 stays on its own paths.

**Window exception, this host only.** The carrier addendum states: "The count rule still applies
as written". The per-host window precedent (the first 2026-09-26 addendum and the security-audit
trial exit) starts a window at each skill's own install. This addendum departs from both, for these
14 skills on host `nativestack-5975wx-20260925` only.

- Their clean `on` window starts at the receipted restore, 2026-09-28T15:09:02Z, and ends at
  2026-10-28T15:09:02Z. The receipted restore time is the guard: `skills_status.py`'s
  `claude_listing` check compares only the current value (`check_claude_listing`, L325-334), so it
  now reads `ok` and cannot show the earlier segments.
- The 2026-10-25 review sets aside `skill_usage.py`'s `prune_candidates` and `verdict_recheck`
  entries for these 14 on this host until 2026-10-28T15:09:02Z, and evaluates them then. Their
  lifetime uses were 0 at the restore, so a lifetime count read later belongs to the restored
  period while the listing stays `on`.
- The review reports this host's segments split as above, not as one mixed window.
- `writing-for-agents` is outside the exception: its listing never left `on`, and its window
  already starts at its own install.
- The review record carries this exception into the manifest update and follow-up decision record
  that the [trial window end](#overturn-conditions) requires.
- **Overturn.** The exception ends for a skill in either of two cases. The trigger comparison
  (overturn condition 2) shows its description gives no trigger gain, so its `name-only` zeros are
  comparable. Or its manifest listing changes.
- **Another change on this host.** If `skills_status.py` finds one of the 14 in a state other than
  `on` again, or `/skill-doctor` reads it at the 20 tokens it showed at `name-only` while
  `skills_status.py` reads `on`, the review reports its window as mixed from that recorded
  boundary, as the carrier addendum does for an unrecorded one, until a new receipted restore.

**The `supply-chain-risk-auditor` tree drift.** The
[tree check](../../evidence/artifacts/skills-listing-restore-20260928/README.md) of 2026-09-28
lists the pinned tree (`truncated: false`). It finds the same 13 file paths in the installed
folder once `scripts/.venv/` and `scripts/__pycache__/` are left out, and only `scripts/uv.lock`
differs. With the fetched upstream blob substituted in memory, the folder's rows hash to
`954cc68e…`, the manifest `tree_sha` and the upstream folder row. This matches the
[2026-09-26 mechanics correction](#addendum-2026-09-26-two-trial-additions-one-deferral-corrected-counts-on-disk-tree-check):
the skill's own `uv run` rewrote the pinned `scripts/uv.lock`. There is no reinstall. `SKILL.md`
and the lock entry match, so `tools/adoption/install_skills.py` classifies the skill `ok`. The
`folder_tree` check in `skills_status.py` stays informational.

- **Per-blob re-check.** `tree_drift_check.py` in that directory, run with
  `--allow scripts/uv.lock` as its README shows, writes nothing. It fails (exit 1) on any other
  differing, missing or extra blob. It refuses (exit 2) an installed entry other than a regular
  file or directory, a `.git` entry, and an upstream row other than a `100644` or `100755` blob or
  a tree. None of its five controls passed. No allowance, and a planted one-byte change to
  `scripts/model.py` in a copy, each exited 1. A copy whose `scripts` is a symlink to an outside
  directory, a copy holding a FIFO and a `.git` file, and a listing rewritten to hold a gitlink
  each exited 2. It runs at the 2026-10-25 review on each trial host, and before any reinstall or
  re-pin of this skill.
- **Escalation.** The `SKILL.md` sha256 and lock checks are required `skills_status.py` checks. A
  `SKILL.md` sha256 mismatch, or a lock entry whose `skillFolderHash` differs from the pin, makes
  `classify_skill` return `install` (`install_skills.py` L117-135). The supported path is then
  `python3 tools/adoption/install_skills.py --only supply-chain-risk-auditor --skills-bin <tools-root>/skills-1.7.0/bin/skills`,
  after installing the pinned CLI per the manifest's `cli.install`. That path checks the pinned
  version (L148-162), runs with `DISABLE_TELEMETRY=1` (L143), adds with `--skill` (L181), and
  verifies or rolls back (L195-204). With no lock entry and a changed `SKILL.md`,
  `classify_skill` returns `local-modified`, and the installer refuses unless `--force` is passed.
- **Per-blob-only failure.** When `SKILL.md` and the lock still match, the installer has no path:
  `classify_skill` returns `ok` and the add is skipped (L172-175). Until P4's installer half is
  decided, that case is re-added by hand with the installer's own argument vector and environment,
  `DISABLE_TELEMETRY=1 <skills-bin> add <manifest url> --skill supply-chain-risk-auditor -g -y -a claude-code codex`,
  followed by `skills_status.py` and the re-check.
- **P4** (`delta.json` L4237-4241, "for": "upstream issue plus installer follow-up") has two
  halves. Its upstream-issue half ("Ask trailofbits to run supply-chain-risk-auditor's stdlib-only
  scripts with 'uv run --no-project'") is dropped under the rule to "never file upstream issues,
  comments or pull requests"
  ([harness defaults](../harness-defaults.md#build-on-upstream-as-foundation-platform-and-runtime-workers)).
  Its installer half ("an opt-in install_skills.py flag that reinstalls a folder whose on-disk tree
  drifted") stays open for the verdict wave or the 2026-10-25 review. This addendum neither adopts
  nor rejects it.
- **This addendum's own watch**, which is not P4's text: when an upstream revision runs these
  stdlib scripts with `uv run --no-project`, re-pin to it through a manifest update with its own
  record, applied as in
  [Apply the skills manifest](../../adoption/update.md#apply-the-skills-manifest).

**Other hosts.** Before 2026-10-25, the Mac coordinator and every other trial host run
`python3 scripts/skills_status.py --json` and record the result. A `claude_listing` mismatch there
gets its own receipt and addendum before the review counts that host's windows. This exception
does not extend to another host.

**Handed to the sweep record's owner.** This addendum answers pending decision (g) of the
[2026-09-28 community sweep](2026-09-28-community-sweep.md) (line 532). It also answers that
record's notes on the same drift, at lines 174-175, 556 and 558 ("gh-fix-ci stays name-only
(skills lane)"). That record's owner updates them. This change does not edit that record,
following the M10 hand-off precedent in the [listing policy](#listing-policy).

**Dated narrowing, 2026-09-28.** The 2026-09-26 anti-pattern row "Disabling capabilities to save
context instead of routing them" (`docs/harness-defaults.md`) says "Keep on-demand skills
`name-only`". Its source question, in the
[preload addendum](#addendum-2026-09-26-listing-state-and-agent-preload), describes the listing
policy as keeping "on-demand skills out of the listing to save context".

- From 2026-09-28, that rule applies to a skill's manifest listing, changed through the manifest,
  template and budget together. It does not license a host-only edit of a skill that the manifest
  lists `on`.
- This narrowing is dated today. It is not a claim about what the row meant when it was written:
  the only record of its author's intent, a coordinator memory note (untrusted history), shows a
  global `name-only` rule.
- The listing policy does not reserve `name-only` for a class of skill. It gives the three kept
  `name-only` skills' reason as deliberate invocation, matching M10's rule, and the prune rule
  (`adoption/skills/manifest.json` L30) demotes unused trial skills to `name-only`.

**Overturn conditions.**

1. **Listing budget.** A `--debug` run shows the warning that Claude Code writes when the listing
   exceeds its budget, in the main session or in any child model in use (`/context`'s Skills row
   reports the listing after the budget). Claude Code then drops descriptions starting with the
   skills invoked least, including the 14, along with other zero-use user and plugin skills.
   Action: apply a documented remedy by addendum: `name-only` for low-priority entries, through the
   manifest, template and budget together, or a lower `skillListingMaxDescChars` or higher
   `skillListingBudgetFraction` in the template.
2. **Trigger comparison.** There is no fixed date: it runs once an upstream harness is named with
   its pin before the run, as the carrier addendum requires for its own comparison. The trigger is
   a preregistered `on`-versus-`name-only` comparison that shows no trigger gain for a skill. It
   runs in fresh sessions, with frozen should-trigger prompts and adjacent should-not-trigger
   prompts, graded on Skill tool calls. Action: demote that skill through the manifest, template
   and budget, with an addendum.
3. **Count rule at the window end.** The review is held on 2026-10-25, but each skill's
   eligibility date is its own, per host. On a host whose listing never drifted, a skill becomes
   eligible 30 days after its own install on that host (the lock's `installedAt`), as
   `skill_usage.py` computes it (L473-479, L537-541). The
   [first 2026-09-26 addendum](#addendum-2026-09-26-two-trial-additions-one-deferral-corrected-counts-on-disk-tree-check)
   says so for its two additions: "Each addition's prune window starts at its own install on each
   host (the lock's `installedAt`), so neither is a prune candidate at the 2026-10-25 review." For
   these 14 on this host, eligibility starts at 2026-10-28T15:09:02Z; their install-based dates,
   which the exception replaces, are in the receipt's `data.skill_usage_30_day_age_reached`. A
   trial skill past its eligibility date with zero uses across its clean `on` window is demoted
   one step or removed under the prune rule. A skill not yet eligible at the review is not a
   prune candidate there. The kept pair is excepted.
4. **`semgrep` and `codeql`.** P2 decides at the 2026-10-25 review or a verdict re-record. Measured
   harm before then means removal, as above.
5. **Kept pair.** Only a sealed verdict re-record changes `gh-fix-ci` or
   `security-best-practices`. For `security-best-practices`, the next verdict wave fields a
   challenger ([security-audit addendum](#addendum-2026-09-27-security-audit-trial-row-stale-upstream-flags-sandbox-gate)).
6. **User choice.** The user may choose a listing directly, including a global `name-only` rule.
   It is carried through the manifest, template and budget together, never host-only.
   `tests/test_skills_manifest.py` L187-189 holds the template's `skillOverrides` equal to the
   manifest listings, and L149-151 holds the budget to the manifest's `on` descriptions; both read
   repository files only, so they pass on host drift. A host-only change is also overwritten at
   the next apply (the Overturn in the
   [claude.ai sync addendum](#addendum-2026-09-26-claudeai-skill-sync-and-mcp-servers-off)).
7. **Cost.** A provider-counted first-request measurement, not yet run, shows the 14 descriptions
   add more than 2,940 tokens per request. The measurement is
   `examples/claude-native/workflows/child-usage.mjs` on one workflow child of a type that
   receives the skill listing, with the 14 `on` and at `name-only`, on one host. The threshold,
   twice the `/skill-doctor` estimate of +1,470, was set on 2026-09-28, before any measurement.
   Action: re-decide the 14's listing, starting with the highest context cost, as the skills page
   advises. A budget diagnostic uses prompts that match none of the 14 and records any Skill call
   it makes.
8. **Client or pin change.** These are this addendum's own conditions: the
   [preload addendum](#addendum-2026-09-26-listing-state-and-agent-preload)'s overturn covers
   preload eligibility only, and the
   [security-audit addendum](#addendum-2026-09-27-security-audit-trial-row-stale-upstream-flags-sandbox-gate)'s
   pin condition covers that skill only. A Claude Code release after 2.1.283 changes the absent-key
   default, `name-only` semantics or the listing budget, or a new pin changes one of the 14's
   description. Action: re-decide that listing.
9. **Tree drift.** The per-blob re-check exits 1, or exits 2 refusing an entry of the installed
   folder, which lies outside the pinned tree: follow the escalation above. Any other exit 2 is
   resolved and the check re-run; no exit 2 counts as a pass. An upstream revision runs the
   scripts with `uv run --no-project`: re-pin as in this addendum's watch above.

**Evidence class.**

| Item | Class | Policy class | Basis |
| --- | --- | --- | --- |
| `/skill-doctor` before and after, through `skill_usage.py --run-skill-doctor`, with lifetime use counts | native-measurement | Upstream example or native operation | [Receipt](../../evidence/receipts/skills-listing-restore-20260928.json); 0 turns, $0; context figures are estimates, and use counts are observational, not causal |
| `skills_status.py` before (exit 1) and after (exit 0), and the edit script's assertions | our-integration | Local integration check | Same receipt; the failing run is the control for the passing one |
| Settings-backup states | our-integration | Independent observation | Same receipt; read value-free with `skills_status.py`'s own reader |
| `command -v semgrep` and `command -v codeql` | native-measurement | Upstream example or native operation | Same receipt, `local_checks`; one shell's `PATH` at one time |
| `gh api` tree and blob reads | native-measurement | Upstream example or native operation | [Tree check](../../evidence/artifacts/skills-listing-restore-20260928/README.md), with stdout digests |
| Scan, per-blob comparison and in-memory substitution | our-integration | Local integration check | Same directory; both self-checks in each run that passes the entry scan |
| Tree-check controls | synthetic-fixture | Synthetic fixture | Same directory: five controls built by `run_checks.sh`, two exiting 1 and three exiting 2, none a pass |
| Skills page and settings reference wording | upstream wording | None; cited, not executed | URL and read date (2026-09-28) only; no copy retained |
| Who made the 2026-09-26 edits, and why | untrusted-history | None; not evidence | A coordinator memory note |
