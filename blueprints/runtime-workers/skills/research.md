# Runtime-worker skills source review — 2026-09-27

This is source-review evidence for a broad trial, not worker acceptance or a
claim of measured superiority. Discovery used the installed `search-first` and
`find-skills` guidance, the skills.sh directory, and the named primary repositories.
Popularity was not a selection criterion. Pages were fetched/indexed with
context-mode; repository commits, recursive trees and file bytes were retrieved
with `gh api`. No skill files were copied into a worker and no host installation
or configuration was changed by this build.

## Installer and freshness design, before implementation

Extend `tools/adoption/install_skills.py` and its existing subprocess tests.
The already-requested public seam is its command line: project placement,
explicit agent selection, idempotence, refusal and rollback, with unchanged
default global invocations. These are local integration fixtures, not upstream
CLI tests.

The installed `skills` executable was unavailable on PATH. GitHub's latest
release endpoint returned `v1.7.0` (published 2026-09-17); `gh api
repos/vercel-labs/skills/commits/v1.7.0` resolved
`7407f3893ad4dceab546ac002c3ef806e4000c73`. The existing adoption manifest pins
that same release and registry integrity. Source at this revision settles:

- [`src/agents.ts`](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/agents.ts):
  universal project directory is `.agents/skills`; its global configuration is
  distinct and must not be substituted for a project target.
- [`src/local-lock.ts:15`](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/local-lock.ts#L15):
  project lock entries contain source, ref, skillPath and computedHash;
  `computedHash` is SHA-256, **not** the global lock's Git tree SHA.
  Lines 65–66 place the lock at `<cwd>/skills-lock.json`.
- [`src/add.ts:2066`](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/add.ts#L2066):
  local hashes come from the source folder or blob snapshot; lines 2130–2160
  write the local lock. Lines 2086–2125 write the different global lock.
  Project verification must bind the lock to the exact source/ref/path and
  independently compare that pinned directory's GitHub tree SHA, alongside the
  existing installed SKILL.md SHA-256 check. This retains the global verifier's
  evidence boundary: source-tree identity, not installed support-file integrity.
- [`src/cli.ts:398`](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/cli.ts#L398):
  `check` and `update` both call `runUpdate`. A scheduled read-only job must not
  run `skills check` against an adopted project.
- [`src/update.ts:549`](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/update.ts#L549):
  updates group by source **and ref**. Lines 868 and 925–950 clone the recorded
  project ref and reinstall; a commit pin does not advance to HEAD. Report
  HEAD drift separately from pin integrity, and repin explicitly after review.

The scheduled job follows `.github/workflows/catalog-freshness.yml`'s read-only
freshness job, pinned actions, bounded runtime and retained report artifact;
its optional proposal job is outside this skill program.

## Observed research limitations

The shell execution tool could not connect to api.github.com; `gh api` through
context-mode succeeded. A Python YAML import in the research subprocess failed
because PyYAML was unavailable on that interpreter; Node YAML parsers were also
unavailable. Metadata review used the existing `/usr/bin/python3` with PyYAML
6.0.1 instead; nothing was installed. Guessed GitHub helper filenames returned unavailable and were
discarded; citations use only paths confirmed by the recursive tree and file
reads. These failures are not evidence of an upstream capability's absence.

## Merit decisions and source bytes

The manifest carries the exact directory Git tree SHA from each pinned
`gh api repos/OWNER/REPO/git/trees/COMMIT?recursive=1` response and SHA-256 of the
returned raw SKILL.md bytes from the contents endpoint at that commit. All trees
were untruncated. Description length counts the trimmed parsed YAML string;
byte count and SHA-256 use unmodified bytes. Rechecking all 28 adoption entries
matched their existing pins and hashes; `reuse_ref` preserves their provenance.
No registry summary was substituted for these source observations.

The OpenHands registry was enumerated, including plugin skill entrypoints, not
estimated from a search result. Every one of its 84 skill paths has a selected or
excluded decision. Its release API returned v0.25.0, published
2026-09-27T12:30:14Z (the release-note heading says 2026-09-26).
The full inventory and collision decisions are in `manifest.json`.

Anthropic's skill-creator closes output-evaluation needs through the explicit
with/without baseline and repeated evaluation loop at
[anthropics/skills@33375500 skills/skill-creator/SKILL.md:163](https://github.com/anthropics/skills/blob/33375500bcea98d610eb30ce10ac4e59b89c390d/skills/skill-creator/SKILL.md#L163).
Superpowers' individual lifecycle skills merit testing for coherent planning,
red/green implementation and evidence-based completion; native hook and namespace
adaptation remain unproven. Its completion skill, `verification-before-completion`,
was later excluded with main (see repair round 4 below). Framework-specific Vercel review and measurement
skills complement general code review. Matt Pocock supplies primary-source
research, spec/ticket synthesis and handoffs in addition to the seven existing
pins. Trail of Bits' nine existing selections already cover scanning, dependency
risk, finding verification, property tests and Python tooling. The six OpenAI
selections combine the four existing GitHub/security skills with Playwright and
notebook workflows. These are capability-fit judgments, not claims of measured
head-to-head superiority. No runtime invocations were used as evidence here.

The [live freshness report](freshness-20260927.json) independently re-read pinned
trees and HEAD with `gh api`: all 138 manifest tree identities matched, no fetch
failed, and two ECC skills had repository movement with unchanged skill trees.
ECC HEAD was `e482e579415fde18357cafce70f177ae19fd7f03`; their retained adoption
pin is `2b6e839771e53096d8451a213d40dc64ec8acac0`. The CLI latest release was
still 1.7.0. No pin was advanced by the check.

## Test-first and independent review

The first added subprocess test ran before implementation and failed because
argparse rejected `--project-dir` and `--agent`; the test command exited 1.
The initial change then passed that test and all 19 original tests.
Further lifecycle tests first exposed absent check-only support and pruned-skill
reinstallation. A read-only independent source review found three project-mode
issues: a new Claude target could be skipped after universal installation,
targeted removal could retain a shared canonical folder, and a relative CLI path
could break after the cwd switch. Each received a failing regression run before
its fix. The fake CLI now models native target placement and shared removal.
Returned summaries and the exact commands are retained in [validation](validation.json).
These are local integration fixtures; unchanged upstream CLI tests and worker
E2E runs were not executed.

## 2026-09-28 rebase: main's gated skill and the reused gates

The branch was rebased onto main `3058b237`, and after the repair onto `8d8f79cd`
(#460), where only `manifests/evidence.json` conflicted. Main's #448 (`8315274f`) had added
a 29th adoption skill, `security-audit` from `cloudflare/security-audit-skill`,
with Codex disabled and a name-only Claude listing pending the M5c bake-off
against `/security-review`. The coordinator chose to exclude it rather than reuse
it, because runtime workers must not bypass a gate set on main. The manifest
records that exclusion with an overturn condition. The contract test re-verified
the 28 `reuse_ref` pins against main (all equal). The selected count stays 138
and the source count 12.

The same review found that reused entries copied only pin keys, so
`--print-codex-config` on this manifest disabled none of the 16 reused skills
main keeps off for Codex. The installer now takes both gates from the adoption
entry when it resolves a `reuse_ref`, and refuses an entry that restates a gate
or whose pin drifted. The Claude listing mode is a Claude Code `skillOverrides`
setting. The OpenHands SDK's skill loader at
`fcc102a697874d54a357e36004e02c95040dbdc0` reads skill directories, SKILL.md
frontmatter and its own installed-skill enable state, never Claude Code settings.
With `load_project_skills` on (it is `False` by default), it also loads
`AGENTS.md`, `CLAUDE.md` and the other third-party instruction files from the work
directory and its Git root as permanent context, and `AgentContext.disabled_skills`
is its deny-list by name across every source (see the README; repair round 3
added the last two points). Each new
test failed before its fix; [validation](validation.json) retains the returned
summaries. No independent model review was run for this round.

## 2026-09-28 repair round 3: two independent reviews

Two independent reviews of `8efdc35d` returned changes-needed with no blocker or
high finding: a GPT-6 cross-family review (codex_call.sh, gpt-6-astra max) and a
headless Claude session review. The coordinator relayed eleven findings; each
received a failing test or a source check before its fix, and
[validation](validation.json) records every finding's disposition under
`repair_r3`.

- **Project containment (GPT6-C1).** skills 1.7.0 recreates
  `<project>/.agents/skills/<name>` with `rm` and `mkdir`. Through a symlinked
  target directory or lock, or with `--project-dir` at `--home`, an add and its
  rollback could replace and then delete a global skill. The installer now
  refuses those layouts before any CLI or `gh` call.
- **Pin identity before add (CL-D1).** A pinned-tree mismatch used to be found
  only after `add` and rolled back. The native in-use guard keeps the canonical
  folder and lock whenever a detected agent that is not a target reads that
  folder (Codex whenever `$CODEX_HOME`, or `~/.codex` when it is unset, or
  `/etc/codex` exists). The comparison
  therefore moved into the preflight, and a mismatch refuses the run with no add.
- **Scope and pruning (CL-D3).** The manifest carries `"scope": "project"`, and
  the installer refuses it without `--project-dir`. A pruned entry is never
  installed in either mode.
- **Reference key (CL-D6).** `reuse_ref` and `adoption_ref` now name the
  adoption manifest and match by skill name, so main can reorder or insert skills.
- **Freshness pin (CL-D7).** `runtime_skill_freshness.py` reads the expected CLI
  version and source ref from the manifest's `cli` pin.
- **Workflow analysis (GPT6-C5).** `tests.test_workflow_security_coverage` now
  analyzes the freshness workflow with zizmor. It also shows that a floating tag,
  a dropped `persist-credentials: false` or a dropped permissions block each
  become a finding. zizmor 1.30.1's regular persona reports nothing for a
  workflow-level `contents: write`, so the read-only grant is asserted on the text.
- **Documentation (GPT6-C6a, GPT6-C6b, CL-D2, CL-D4).** The README now says four
  things. The rendered skill list omits `<location>`. `disabled_skills` and the
  source flags are OpenHands' controls. Third-party instruction files load from
  the work directory and Git root, so the example worker projects moved outside
  this repository. A rollback is retained whenever Codex or another
  `.agents/skills` agent is detected and not targeted, and the retained copy
  stays loadable.
- **Review record (CL-D5).** The earlier `skills-review-r1.json` was never
  published. It is now labelled as unpublished, and its seven findings remain
  transcribed in [validation](validation.json).

The branch was rebased onto main `c1581fa2` (#462) before the repairs, where only
`manifests/evidence.json` conflicted and main's side was taken, and onto
`c61e6657` (#461) after them without conflicts; main had moved past the
`b9eb62d2` named in the repair brief. The coordinator attaches the raw review
verdicts to the pull request as comments; they are not part of this tree.

## 2026-09-28 repair round 4: main's M4 removal

Main `c0966da2` (#464) removed `verification-before-completion` from its skills
trial under the conflict rule M4 and moved it to its own `excluded` list
([decision](../../../docs/decisions/2026-09-28-delegated-decisions.md), #462).
The pinned SKILL.md (`8ca22db`, SHA-256 prefix `2befe7fc`, re-read with `gh api`
for this round) requires fresh verification evidence before any completion claim
(L17-20) and rates a previous run as not sufficient (L42), while `AGENTS.md:16`
says to reuse passing evidence when its inputs still match. A worker whose work
directory is a checkout of this repository loads both texts.

The branch was rebased onto `c0966da2` without conflicts (git exit 0). The
previous re-registration commit applied cleanly; it was then uncommitted, main's
`manifests/evidence.json` restored, and the re-registration redone as the last
commit. On the rebased tree the unchanged tests failed as the contract intends
(67 tests, 6 failures, 2 errors):
`test_every_adoption_skill_is_reused_or_explicitly_excluded` reported
`verification-before-completion: reuse_ref 'adoption/skills/manifest.json' names
no single main adoption skill`, and the installer refused the manifest for the
same reason.

The runtime manifest now excludes the skill with its reviewed pin, a reason and
an overturn condition: main re-admits it. The exclusion carries no `adoption_ref`,
because main lists the skill under `excluded` rather than `skills`. The new test
`test_verification_before_completion_stays_excluded_until_main_readmits_it` and
the revised superpowers lifecycle test failed before the exclusion. The current
counts are 137 skills from 12 sources (obra/superpowers 14 of its 15), 27 reused
adoption skills (16 of them Codex-disabled on main) and nine exclusions. There are
15 empty role/scenario cells, since the extraction caller's CI-fix cell lost its
only selection. Catalog sums are 1,020,955 SKILL.md bytes and 36,739 description
characters. A new source-count test ties `sources` and the table below to the
selected skills.

The round-3 record's `not_relayed` line was wrong. The GPT-6 review's
GPT6-C1-manifest-pins, C2-adoption-coverage, C3-reuse-gates, C4-pruned-selection
and C7-validation-evidence were CONFIRM verdicts without a defect, so nothing
needed relaying; [validation](validation.json) now lists them under
`repair_r3.confirmed`.

## 2026-09-30: main's LLM-native listing

Main's [LLM-native listing decision](../../../docs/decisions/2026-09-30-skills-llm-native-listing.md)
lists every model-invocable adoption skill `on` and enables every adoption skill for
Codex except its new `skill-creator` pin. Two runtime entries follow it.

- **`security-audit`.** Main's promotion (listing `on`, Codex enabled) met the
  exclusion's overturn condition. The exclusion became a `reuse_ref` entry for the
  `security` scenario and the `coding` and `orchestration` roles: the pinned SKILL.md
  has a parent delegate hunters and verifiers into a coverage ledger with `confirmed`,
  `needs_validation` or `rejected` records (L172-175 at `c1c8a8c`, re-read with
  `gh api`, SHA-256 `5e3e96a1…`), and loading it is guidance only until a prompt asks
  for the full audit (L12). No research role is claimed, so that `security` cell stays
  a gap. `cloudflare/security-audit-skill` joins the source table below.
- **`skill-creator`.** Main pins it at `anthropics/skills@8a1541c4`, that repository's
  HEAD on 2026-09-29. `gh api` shows the same folder tree (`3cf9a8db…`) and SKILL.md
  (SHA-256 `dcd4803e…`) as the `33375500` pin this manifest selected. The contract
  compares `ref` and `url`, so the entry became a `reuse_ref` at main's ref and the
  collision record follows it. The source table keeps `33375500`, the commit the
  other eight `anthropics/skills` skills were selected at.

The counts are now 138 skills from 13 sources, 29 reused adoption skills (only
`skill-creator` Codex-disabled on main) and eight exclusions, with 1,042,981
SKILL.md bytes and 37,098 description characters. The empty role/scenario cells are
unchanged. `test_security_audit_is_reused_since_main_promoted_it` replaced the
exclusion test and failed against the unchanged manifests before the change. The
bare-exclusion negative control now builds its own fixture, since no `adoption_ref`
exclusion remains here.

## 2026-09-30: upstream re-pins and one retirement

The adoption manifest's 2026-09-30 source review
([native skill lifecycle record](../../../docs/decisions/2026-09-30-native-skill-lifecycle.md))
re-pinned six reused skills and retired one; every pin was re-verified from a blobless
clone of its source repository (tree SHA, SKILL.md SHA-256, bytes and description length).

- **`resolving-merge-conflicts` is retired.** Upstream removed it in `daa01d8`
  (2026-09-24), so it is absent at `mattpocock/skills@d81f3a18`, whose changeset says
  nothing replaces it. Its entry and its four coverage selections are gone; the
  `github-issue-to-pr` and `github-pr-review` cells keep their other selections.
- **Re-pins through `reuse_ref`.** `diagnosing-bugs`, `tdd`, `codebase-design` and
  `improve-codebase-architecture` follow the adoption manifest to `d81f3a18`,
  `search-first` to `affaan-m/ECC@c70874fa` (description 141 to 328 characters) and
  `semgrep` to `trailofbits/skills@82fe8226`.

The counts are now 137 skills from 13 sources, 28 reused adoption skills and eight
exclusions, with 1,042,408 SKILL.md bytes and 37,215 description characters. These are
catalog sums. The source table below keeps each repository's original discovery
revision (`mattpocock/skills` now has 11 selections); each entry's own `ref`, including
a newer one reached through `reuse_ref`, is authoritative. This update neither installs
the runtime catalog nor qualifies its other candidates.

Sources: [removal changeset](https://github.com/mattpocock/skills/blob/d81f3a183412e71a5b1e84ca21bc1a35eea03a60/.changeset/remove-resolving-merge-conflicts.md),
[search-first](https://github.com/affaan-m/ECC/blob/c70874fae9eb0e5ad0365beb7e2955899fd1d30f/skills/search-first/SKILL.md),
[Semgrep](https://github.com/trailofbits/skills/tree/82fe8226252622fa807643bdca1710901198553a/plugins/static-analysis/skills/semgrep).

## Source pins

<!-- source-pins -->

| Repository | Commit resolved with gh api | Selected skills |
| --- | --- | --- |
| OpenHands/extensions | `bea7a20c59c44ec4dacddac3fc0efe58b9c73880` | 77 |
| affaan-m/ECC | `2b6e839771e53096d8451a213d40dc64ec8acac0` | 2 |
| anthropics/skills | `33375500bcea98d610eb30ce10ac4e59b89c390d` | 9 |
| assafelovic/gpt-researcher | `0957c301ed06c2a5857b834358c7227c739041d4` | 1 |
| cloudflare/security-audit-skill | `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8` | 1 |
| mattpocock/skills | `c55ee46073ed923f86ce59a5eb3b6d895095d1b7` | 9 |
| obra/superpowers | `8ca22dba9a94f28898bbce59f2537ff4d87c747d` | 14 |
| openai/skills | `49f948faa9258a0c61caceaf225e179651397431` | 6 |
| trailofbits/skills | `0cc1c73a5e96749ab32d7ea5e14892fafa6972ae` | 8 |
| typesafe-ai/skills | `65a39f393687675ce170e6094757de20370365b9` | 1 |
| vercel-labs/agent-browser | `d01253d9db28d75080e36da3c1c31ef89454731e` | 1 |
| vercel-labs/agent-skills | `063bee94c3f4df8453406c830b0a7df0f2860278` | 4 |
| vercel-labs/skills | `7407f3893ad4dceab546ac002c3ef806e4000c73` | 1 |
