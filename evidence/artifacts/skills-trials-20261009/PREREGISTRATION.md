# Instructions and skills trial preregistration (2026-10-09)

Status: frozen before any candidate check or comparison outcome. This is a new
blinded comparison of native validation reports on the same skill fixtures. It
does not repeat the earlier unblinded skill-task scoring or establish general
task superiority.

The routed sweep was re-read at
`77e17817d8ecc8e53329ac32303ece8dc4e86eaf67cba1e3ae36196aa328a109`.
The source changed after the handoff snapshot; its instructions-skills rows still
name these trials. The repository base is
`b7dfe638fc825a52ff4e7d1a9ccf2fde7de889fd`.

## Sources and native arms

- agent-sh/agnix v0.57.0, commit
  `2c0e4efede3181599eca37619e8067ae2d941c00`: native `agnix --target codex
  --format json <corpus>`. Use the vendor GNU Linux x86_64 release archive,
  sha256 `c72bf5ff1f45900055c353cc1bd6bbea6389506a3ba3197db000340066c78098`.
- NVIDIA/SkillEvaluator v0.5.0, commit
  `7304d76cde371287b67ea99653409d014b6b9c85`: native `validate <skill>
  --tiers 1 --checks schema,quality --no-llm --min-score 70 -r json`.
  Install the vendor base package with uv into a lane-owned tool prefix.
- openai/skills commit `49f948faa9258a0c61caceaf225e179651397431`:
  unmodified `skills/.system/skill-creator/scripts/quick_validate.py`.
- anthropics/skills commit `683bc88e56f3e09ba94f7055977f3d3aa499f202`:
  unmodified `skills/skill-creator/scripts/quick_validate.py`.

The last two arms are reference validator controls. Running their scripts does
not install their skills or rerun their previous live-task comparison. All four
receive identical frozen cases. Native unsupported scope and missing checks are
reported as such, never turned into successful checks.

## Frozen tasks and reference labels

The format labels follow the current [Agent Skills specification](https://agentskills.io/specification):
required name/description, lowercase name of at most 64 characters, description
of at most 1024 characters, valid YAML frontmatter, and references to available
local resources. Valid controls have actionable instructions and existing files.
The body/reference case measures a resource-checking gap separately from syntax.

| Case | Task | Reference result |
| --- | --- | --- |
| C01 | Minimal valid skill | clean |
| C02 | Required name absent | name missing |
| C03 | Required description absent | description missing |
| C04 | YAML mapping malformed | invalid YAML |
| C05 | Name contains uppercase and underscore | invalid name |
| C06 | Name has 65 characters | name too long |
| C07 | Description has 1025 characters | description too long |
| C08 | Markdown links to a missing local reference | missing local resource |
| C09 | Markdown links to an existing reference | clean |
| C10 | Valid license, compatibility, and metadata fields | clean |
| C11 | Description is empty | description empty |
| C12 | Frontmatter absent | frontmatter missing |
| I01 | AGENTS.md links to an existing local file | clean |
| I02 | AGENTS.md links to a missing local file | missing local resource |

The shared primary comparison covers C01–C12 only. I01–I02 are the separate
Codex instruction coverage gate: unsupported scope in a skill-only validator is
not a false positive or a fabricated pass. These are deliberately small
synthetic cases, rather than a representative workload or independent published
benchmark. No corpus extension, replacement or threshold change after results.

## Judge and blinding

One fresh independent standard-tier judge receives only this reference rubric,
neutral task identifiers, and normalized native findings for four opaque arms.
It uses the inherited `cx/gpt-6.1-sol` model and effort; it has no parent-turn
history and is instructed to make no tool calls. The executor does not judge.
The arm mapping is generated before execution and retained privately; only its
hash is registered before judging. The judge packet omits source names, rule
IDs, source paths, release pins, dependency inventories and prior verdicts.
Anonymization changes presentation only: preserve all finding text and severity
after substituting source identifiers. Retain the native reports and their
hashes for subsequent review. Reveal the mapping only after the judge seals its
return. Any origin leak, execution error or incomplete return invalidates the
affected comparison rather than being scored as an empty report.

For each case/arm the judge reports whether the seeded defect was correctly
identified and whether it asserted additional unsupported defects. A clean
case is a true negative only when there is no unsupported defect. Missing a
seeded defect is a false negative. Unsupported additional defect assertions
are false positives. Style suggestions explicitly marked optional are not
defect assertions. The executor computes precision, recall and F1 from the
sealed per-case labels; ties are inconclusive. Record the case table so that
the metrics can be recomputed without another model call.

## Frozen thresholds and adoption gates

- A static-check pass requires F1 at least 0.90 and zero false positives on the
  three clean shared cases. agnix must also identify I02 and accept I01 to
  demonstrate the separately named instruction-file gap.
- Replacement requires an F1 gain of at least 0.10 over the stronger reference
  validator control. Passing syntax checks alone cannot establish live-task
  superiority, semantic overlap quality or security coverage.
- A stale source cannot be a new maintenance-qualified winner. Recheck
  openai/skills with REST on its explicit default branch, using the exact
  90-day cutoff and archived flag; do not use `pushed_at`. A clean static result
  cannot override this gate. Do not select anthropics/skills as a general
  replacement from this diagnostic alone. The proposed re-rule and any
  still-open task comparison must be explicit.
- Every candidate retains quality evidence at its pin, its vendor install,
  one native check and its executed, verified inverse. A fresh native session
  receives a natural validation request without either candidate name. Count
  reach only from the native tool-command record. A missing vendor routing
  resource or a policy-blocked skill install leaves this stage failed or
  unproved; do not invent a routing skill.
- ADOPT-NOW additionally requires a measured per-session PSS from
  `/proc/<pid>/smaps_rollup`, complete required stages, and the owner gate.
  No user-level configuration, hook or skill registration is changed. A
  proposal remains a proposal until the CC's own apply and fresh-session
  gates. Both designated PR reads, CI, the pre-cue tool and the CC's cue remain
  required for landing; publishing this trial PR does not satisfy those gates.

## Retention and stopping

Keep preregistration/corpus/mapping hashes, native commands and return codes,
all failures, anonymized packet, sealed judge output, mapping reveal, metric
table, source reviews and gate results. Record usage as unknown unless a native
meter supplies it. Perform no rerun to obtain a preferred outcome. Publish one
draft foundation PR after validation, then post the required acceptance and
CHECKPOINT headings. Run nothing between 13:15 and 13:45Z.
