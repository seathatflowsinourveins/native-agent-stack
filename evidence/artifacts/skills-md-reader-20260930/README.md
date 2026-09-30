# SKILL.md reader agreement with the pinned skills CLI (2026-09-30)

One workstation, 2026-09-30 23:56:37Z to 23:57:35Z UTC (33 steps). This receipt checks
`tools/sota-convergence/landscape-sweep/skill_md.mjs`, the reader the landscape sweep's skills modality runs for every
`SKILL.md` copy of a skill survivor (`source_reviews.py`), against the pinned skills CLI itself. It also records what
`source_reviews.py`'s symlink rule changes on the catalog's sources, and checks the CI step that installs the reader's
yaml pin. The code under test, by sha256 (`counts.json` `code_under_test`; the files, not the commit, are the
identity, since the branch is rebuilt onto main before merge):

| File | sha256 |
| --- | --- |
| `skill_md.mjs` | `4fbd76f219192d629ee962d5aeeb8580cea2a903c3b03fa90c51da8cc69e5791` |
| `skills-yaml.pin.json` | `0e4755bfd05d130603b2991af4fb834bcb4e05d08d67af216596a9fbb320399b` |
| `source_reviews.py` | `5ccae0e2b5f0e9c5b640727837705fae46121d20b8909780934daf9898a5191d` |

No model was called and no skill was installed into any client. The only network use was npm (the public registry),
`git fetch` of public GitHub repositories and the Node.js 22.23.2 tarball from nodejs.org (checked against its
`SHASUMS256.txt`); no token was read or sent.

## Evidence classes

Per [`docs/acceptance-evidence-policy.md`](../../../docs/acceptance-evidence-policy.md):

| Check | Class | What it establishes |
| --- | --- | --- |
| Reader against `parseSkillMd` and its helpers sliced byte for byte from the published `skills@1.7.0` `dist/cli.mjs` (`cli_oracle.mjs`), run with the yaml its install resolved (2.9.1) and with 2.9.0 | Local integration check | The port reproduces the CLI's own functions on these inputs: verdict, recorded name and description, display name, and the warning printed for a skipped copy |
| Reader against the installed CLI run end to end, `skills add <fixture> --list` (`e2e_compare.py`) | Independent observation | The CLI's own output (its skipped-copy warnings and the names it lists) agrees with the reader's verdicts |
| The edge-case comparisons (`edge_cases.py`, 139 inputs) | Synthetic fixture | The review's inputs, line breaks, the name rules and the 2.9.0 to 2.9.1 changes; constructed here, not production text |
| The symlink rule on the sources' trees (`symlink_impact.py`) | Local integration check | Which picks `source_reviews.py`'s symlink rule stops or changes at the catalog pins |
| The CI provisioning step (`ci_step.py`) | Local integration check | validate.yml's step, run with the runner image's npm, installs what the reader verifies under the image's Node.js |
| Negative controls (below) | Discriminating controls | Each comparison fails when its condition is removed |

The corpus is the real input set: all 2,455 `SKILL.md` files of the skills catalog's 22 GitHub sources, fetched at
their catalog pins by commit id (`corpus.py`), each checked against its git blob id; its index digest (the sorted
"key mode blob-id" lines) is in `counts.json`.

## Results

| Comparison | Corpus (2,455 files) | Edge cases (139) |
| --- | --- | --- |
| Reader against the CLI's `parseSkillMd`, yaml 2.9.1 (the CLI install's) | take/take 2,452, skip/skip 3; 0 contradictions, 0 field differences | take/take 62, skip/skip 68; 9 line-break refusals (7 the CLI skips, 2 it takes); 0 contradictions, 0 field differences |
| Reader against the CLI's `parseSkillMd`, yaml 2.9.0 (the pin's) | identical to the row above | identical to the row above |
| Reader against `skills add <fixture> --list` | the CLI found 1,694 skills (1,693 corpus names plus the planted valid one) and warned 4 times (the 3 skips with the same warnings, plus the planted invalid one): agreement | the CLI found 7 skills and warned 76 times: 68 on the reader's skips with the same warnings, 7 on copies the reader gives no verdict, 1 planted: agreement |

The three corpus files the CLI skips are microsoft/skills@3495f50ae0d7
`.github/plugins/azure-skills/skills/azure-app-onboard/{deploy,prepare,scaffold}/SKILL.md`, each with "missing required
frontmatter field(s): name, description". The nine edge cases without a verdict are exactly those with a lone CR,
U+0085, U+2028 or U+2029 in the frontmatter: the reader's one designed refusal, since libyaml (Codex's serde_yaml)
breaks lines there and the yaml package does not. `counts.json` lists every edge case with both verdicts.

The edge cases include the inputs of the round-3 review of PR #541: under-indented double- and single-quoted
continuations and flow collections continued at column 0 (finding 2), the line breaks (finding 3), a nested mapping key
under-indented, an empty flow item and mismatched brackets (finding 4), and names that sanitize to nothing or carry
terminal escapes (finding 6). The CLI skips every input of findings 2 and 4 with a YAML parse error, and the reader
gives the same warning.

## Symlinks on the catalog's sources

The CLI walks a search location through a symlink at or above it, which the git tree does not show, and
`source_reviews.py` stops a survivor whose pick could depend on such a location (the round-4 review's D1). At the
catalog pins, 8 of the 22 GitHub sources hold symlinks (69 in all); 3 of them hold a symlinked search location
(`.opencode/skills` in addyosmani/agent-skills and microsoft/skills, `.agents/skills` in getsentry/skills), none a
symlinked `SKILL.md`, and none a plugin manifest behind a symlink. For each of the 679 folder names the resolver finds
in a search location, the pick with the rule equals the pick without it (678 picks, and 1 name with no pick either
way): every pick is decided
before any symlinked location, so the rule stops none of them. microsoft/skills' other 59 symlinks are skill folders
inside search locations (48 in `.github/skills`, 11 in plugin `skills/` folders), which the CLI skips (their directory
entries are not directories), as the tree shows.

## The CI provisioning of the yaml pin

`validate.yml` installs `skills-yaml.pin.json` before the suite with the pin's own command. `ci_step.py` checked it
without CI: the sha512 of the registry tarball `yaml-2.9.0.tgz` is the pinned integrity and all 75 pinned file hashes
are that tarball's bytes; the step's script, run as the runner runs it (bash -e) with npm 10.9.8 (the ubuntu-24.04
image's) in a scratch workspace, exited 0 and exported `LANDSCAPE_SWEEP_SKILLS_YAML=<runner-temp>/skills-yaml-2.9.0`;
and `skill_md.mjs` under Node.js 22.23.2 (the image's) reported the pinned package, integrity and pin sha256 for that
install. npm checks the tarball against the registry's integrity; the reader then checks the lockfile's integrity and
every file, so a different tarball fails closed.

## The yaml release the CLI runs

`skills@1.7.0` declares `"yaml": "^2.8.3"` among its runtime `dependencies`, and its bundle (`dist/cli.mjs`, sha256
`fde68534019765fb69510a0038ca7df2810a6ffed4c26fef9beabdcf6cc6701c`) imports `parse` from `"yaml"` without bundling it.
Its lockfile (`pnpm-lock.yaml`, not published) resolves 2.9.0, but npm resolves the range when the CLI is installed: this
run's `npm install --global --prefix <scratch>/skills-1.7.0 skills@1.7.0` (the manifest's `cli.install` form) got
yaml 2.9.1, the registry's `latest` (released 2026-09-11). `skills-yaml.pin.json` pins 2.9.0, as briefed. On this day the
two releases gave identical `parseSkillMd` results for all 2,455 corpus files and all 139 edge cases, and identical
`yaml.parse` results for 200,000 random multi-line plain and single-quoted scalars (`yaml_versions.mjs`, seed
20260930), the code path 2.9.1 changed ("Simplify line unfolding during quoted string parsing"). A later 2.x is not
covered: rerun this receipt before trusting the pin against it.

## Negative controls

| Step | Condition removed | Expected | Observed |
| --- | --- | --- | --- |
| `control-sanitize` | `sanitizeMetadata` without `stripTerminalEscapes` (a mutant of the reader) | exit 1 | exit 1: field differences on the edge cases with terminal escapes and control characters |
| `control-typeof` | `parseSkillMd` without its string check | exit 1 | exit 1: the mutant fails on non-string names and descriptions ("str.replace is not a function"), counted as errors |
| `control-flip` | one corpus verdict flipped from skip to take before the end-to-end comparison | exit 1 | exit 1: "skipped folders differ" and "listed names differ" |
| `control-tampered` | one byte appended to the installed `composer.js` | exit 3, `hash_mismatch` | exit 3, `{"reader": {"ok": false, "reason": "hash_mismatch"}, "results": []}` |
| `control-mutants` | (check that both mutants differ from the reader) | prints only "mutants written" | "mutants written" |

The end-to-end comparisons also carry their own controls: a planted copy without a description must be warned about,
a planted valid copy must be listed, and the CLI's "Found N skills" must equal the names listed. All three held in both
runs. The symlink rule's own discriminating tests (the same five layouts reviewed at the wrong copy by the round-4
code) are in `tests/test_landscape_sweep_skills.py`, not here.

## Files

| File | What it is |
| --- | --- |
| `run.sh` | The whole run: `bash run.sh <checkout> <scratch>`; every step's command, UTC start and end and exit status go to `log.txt` with the checkout, scratch and receipt directories written as placeholders |
| `corpus.py` | Fetches the catalog's GitHub sources at their pins (depth 1, partial) and writes every `SKILL.md`, checked against its git blob id |
| `edge_cases.py` | Writes the 139 edge cases |
| `symlink_impact.py` | The symlink rule on the sources' trees at their pins: symlinks, symlinked locations, and every pick with and without the rule |
| `ci_step.py` | The CI provisioning check: the pin's hashes against the registry tarball, validate.yml's step run with a given npm, and the reader under a given node |
| `cli_oracle.mjs` | Slices `parseSkillMd`, `parseFrontmatter`, `stripTerminalEscapes`, `sanitizeMetadata`, `isRecord$1`, `shouldInstallInternalSkills`, `warnSkippedSkill` and `getSkillDisplayName` from the installed CLI's `dist/cli.mjs` (checked against the sha256 above; the extract's sha256 is in `counts.json`) and runs them with a chosen yaml install |
| `compare.py` | Runs the reader in one batch and compares it with the oracle outputs |
| `e2e_compare.py` | Compares the reader with `skills add <fixture> --list` |
| `yaml_versions.mjs` | The random differential of yaml 2.9.0 and 2.9.1 |
| `summarize.py` | Writes `counts.json` from the retained outputs |
| `log.txt` | The 33 steps of this run with their exit statuses |
| `counts.json` | The code under test, tool and package versions and integrity values, the corpus by source with its index digest, every comparison recomputed, the edge cases one by one, the yaml version delta, the symlink rule's effect, the CI provisioning check, the controls, and the sha256 and size of each raw output kept outside the repository |

The raw outputs (the 24 MB corpus text, the CLI's stdout and stderr, which name scratch paths, and the per-file oracle and
reader answers) are not published; `counts.json` records the sha256 and size of each.

## Reproduce

```
bash evidence/artifacts/skills-md-reader-20260930/run.sh . <scratch directory>
```

It needs node (24.21.0 here), npm (11.19.0), git, curl, xz and python3, and installs into `<scratch>` only. It fetches
each source again by its pinned commit id, so the corpus is the same bytes (compare the index digest) or the corpus
step fails. The CLI's own yaml is whatever npm resolves on the day of the run.

## Limits

- One host and one day. The CLI's yaml resolution depends on the day it is installed.
- The oracle `cli_oracle.mjs` runs functions sliced from the CLI's bundle, not the CLI's own module graph; the end-to-end
  run covers that gap for what `skills add --list` prints (warnings and listed names), not for descriptions or for
  every copy of a name the CLI de-duplicates.
- The corpus is what the catalog's sources hold at their pins: it exercises few invalid copies (3 of 2,455), which is
  why the edge cases exist.
- `symlink_impact.py` treats every `SKILL.md` as valid and named after its folder (the resolver without a reader); it
  measures the symlink rule, not the reader.
- The CI check ran the step and the reader locally with the image's npm and Node.js versions, not on a GitHub runner;
  the first CI run of the branch is that observation.
- Nothing here checks Claude Code's or Codex's own reading of a `SKILL.md`, or `agents/openai.yaml`.
