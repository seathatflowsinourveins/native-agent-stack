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
adaptation remain unproven. Framework-specific Vercel review and measurement
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
frontmatter and its own installed-skill enable state, never Claude Code settings
(see the README). Each new
test failed before its fix; [validation](validation.json) retains the returned
summaries. No independent model review was run for this round.

## Source pins

<!-- source-pins -->

| Repository | Commit resolved with gh api | Selected skills |
| --- | --- | --- |
| OpenHands/extensions | `bea7a20c59c44ec4dacddac3fc0efe58b9c73880` | 77 |
| affaan-m/ECC | `2b6e839771e53096d8451a213d40dc64ec8acac0` | 2 |
| anthropics/skills | `33375500bcea98d610eb30ce10ac4e59b89c390d` | 9 |
| assafelovic/gpt-researcher | `0957c301ed06c2a5857b834358c7227c739041d4` | 1 |
| mattpocock/skills | `c55ee46073ed923f86ce59a5eb3b6d895095d1b7` | 12 |
| obra/superpowers | `8ca22dba9a94f28898bbce59f2537ff4d87c747d` | 15 |
| openai/skills | `49f948faa9258a0c61caceaf225e179651397431` | 6 |
| trailofbits/skills | `0cc1c73a5e96749ab32d7ea5e14892fafa6972ae` | 9 |
| typesafe-ai/skills | `65a39f393687675ce170e6094757de20370365b9` | 1 |
| vercel-labs/agent-browser | `d01253d9db28d75080e36da3c1c31ef89454731e` | 1 |
| vercel-labs/agent-skills | `063bee94c3f4df8453406c830b0a7df0f2860278` | 4 |
| vercel-labs/skills | `7407f3893ad4dceab546ac002c3ef806e4000c73` | 1 |
