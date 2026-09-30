# Decision: a skills discovery modality in the packaged landscape sweep (2026-09-30)

## Context

The packaged landscape sweep ([`tools/sota-convergence/landscape-sweep/`](../../tools/sota-convergence/landscape-sweep/README.md))
discovers repositories per foundation or trading layer. Its templates are discover, facts, fit, critic and followup,
and its discovery schema is keyed by `repository`. The installed skills are pinned in `adoption/skills/manifest.json`,
under [the skills trial](2026-09-25-skills-trial-and-usage.md). No sweep searches the skills landscape per lifecycle
task, so a skill candidate appears only when a repository sweep happens to name its repository. Unit A1 of the
2026-09-30 SOTA-defaults wave asked for a second discovery modality, keyed by lifecycle task. It runs the same
Discover, Refute, Critic and Follow-up pipeline.

The modality encodes these upstream facts, read on 2026-09-30:

- **Claude Code.** In the skills frontmatter, `disable-model-invocation: true` stops Claude from loading a skill
  automatically and from preloading it into subagents ([code.claude.com/docs/en/skills](https://code.claude.com/docs/en/skills),
  frontmatter reference).
- **Codex.** `agents/openai.yaml` `policy.allow_implicit_invocation` defaults to true. When it is false, Codex never
  invokes the skill implicitly, and explicit `$skill` invocation still works
  ([developers.openai.com/codex/skills](https://developers.openai.com/codex/skills), Optional metadata).
- **Agent Skills specification.** A skill's `name` has 1-64 lowercase letters, digits and hyphens and matches its
  folder. Its `description` has 1-1024 characters
  ([agentskills.io/specification](https://agentskills.io/specification)).
- **Structured outputs.** OpenAI Structured Outputs support `pattern` on strings in strict mode
  ([Structured Outputs, Supported properties](https://developers.openai.com/api/docs/guides/structured-outputs)).
  The skills schema's patterns therefore stay within what the Codex lane's `--output-schema` accepts.
- **Skills trial.** The trial's selection rules are a named gap, no duplicate of a native capability, no conflict
  with the canonical instructions, and one winner per capability
  ([trial record, lines 88-116](2026-09-25-skills-trial-and-usage.md#selection-rule)). Its bake-off names
  skill-creator's paired with-skill/without-skill benchmark as the comparison harness (lines 670-673).

## Alternatives

1. **A separate skills sweep script beside the packaged sweep.** Rejected: it would fork the evidence contract the
   harness already enforces, which the README's Evidence contract lists:
   - two-family survival with refute-by-default votes;
   - retained failures and their reopen entries;
   - the effort and WebSearch-cap checks, and the GPT-6 copy check;
   - source reviews.

   It would also duplicate the runner, the conversion and the result tools, each of which carries review repairs.
2. **A modality inside the packaged sweep.** Chosen. Three variants were rejected along the way:
   - **Runtime template selection** (`sweep.js` and `make_prompt.py` choose per layer). It was the first
     implementation and was rejected on measurement. Every run's args carried every template: a repository run's
     `args.json` grew from under 16 KB to 20.8 KB, and
     `tests.test_landscape_sweep_harness.BuildArgsTests.test_args_are_compact_and_the_run_is_staged` failed. Every
     repository run's `prompts_sha256` also changed.
   - **A separate identity field through `convert.py` and the ledger.** Rejected as unnecessary. The ledger compares
     `repo` strings with `norm_repo`, and the harness with `slug` and `canon`. All three keep `owner/repo@name` whole
     (checked on 2026-09-30), so the skill ref can travel as the row's `repository`.
   - **Mixed runs** of repository and skills layers. Rejected: one completeness critic covers a run, and
     `make_result.py` counts it in every layer of the record.

## Decision

The packaged sweep gains `modality: "skills"`.

- **Catalog.** [`catalogs/landscape/skills-lifecycle.json`](../../catalogs/landscape/skills-lifecycle.json) keys 13
  lifecycle tasks as `skills-<task>` layers. It covers every pinned skill once and pins 23 sources at the commits
  `gh api` read on 2026-09-30. The skills.sh registry is searched with the manifest's pinned
  `npx skills@1.7.0 find`.
- **Inputs and scope.** `build_inputs.py --modality skills` builds the layer inputs, and `--skills-scope` prints
  their frozen scope in `saturation_ledger.py --scope`'s format, computed with the ledger's own functions.
- **Templates.** `build_args.py` resolves the modality at build time. A skills run's `discover` and `critic` are
  `discover_skills` and `critic_skills`, and `facts` and `fit` end in `modality_skills`. A repository run's frozen
  templates and `prompts_sha256` (`9c34fa72…f14b`) are unchanged. The tests pin both runs' values.
- **Schema.** `schemas/discover-skills.json` is strict. Its `comparison_that_would_overturn` must name skill-creator
  or promptfoo.
- **Identity.** `sweep.js` merges skill proposals by `skill_ref` and carries it as the row's `repository`. A run
  covers one modality.
- **Records.** `source_reviews.py` reviews a skill survivor at its SKILL.md, and `make_result.py --decision-record`
  writes a skills sweep's decision record. The sweep edits no manifest.

**Residuals.**

- **Not bound to the ledger.** `scripts/saturation_ledger.py` refuses a layer outside the foundation and us-equities
  catalogs (`check_layer`, lines 608-610 at the base e45328d3), and refuses a layer that is not in
  `research-state.json` (`complete_result`, lines 1107-1109). Its `--report` and `--scope` list only research-state
  layers (lines 966-1050). So a skills `RESULT.json` cannot be appended, `--due-report` selects no skills layer, and
  the saturation count does not cover skills. How the ledger learns the skills catalog belongs to the owner of that
  script: a `skills` catalog with its own requirement rows and manifest section, or research-state rows.
- **Not run.** No model was called. The evidence is this repository's synthetic-fixture suite, not a measured sweep.
- **Not exercised.** The GPT-6 lane has not run `discover-skills.json`'s `pattern` keywords, which the upstream
  documentation supports. `build_manifest.py` has no skills section, and a skills lane layer lands in
  `lane_groupings` (its docstring, lines 1301-1303).

## Overturn condition

Reconsider a separate skills sweep (Alternative 1) if a measured skills run shows that the modality cannot express a
skills verdict. For example:

- the refuters or the conversion lose or merge distinct skills;
- the returns cannot carry a verdict that a task's requirement needs, such as an invocation flag or a paired-benchmark
  comparison;
- the ledger cannot bind a skills record even after it learns the skills catalog.

## Sources

- [code.claude.com/docs/en/skills.md](https://code.claude.com/docs/en/skills.md), fetched 2026-09-30: the frontmatter
  table (lines 354-370) and the default model invocation (line 766).
- [developers.openai.com/codex/skills.md](https://developers.openai.com/codex/skills.md), fetched 2026-09-30:
  `agents/openai.yaml` and `allow_implicit_invocation` (lines 192-215).
- [agentskills.io/specification.md](https://agentskills.io/specification.md), fetched 2026-09-30: the frontmatter
  fields (lines 28-35), `name` (lines 61-69) and `description` (lines 101-105).
- [developers.openai.com/api/docs/guides/structured-outputs.md](https://developers.openai.com/api/docs/guides/structured-outputs.md),
  fetched 2026-09-30: Supported properties, `pattern`.
- [vercel-labs/skills README.md at v1.7.0](https://github.com/vercel-labs/skills/blob/v1.7.0/README.md) (tag commit
  `7407f3893ad4dceab546ac002c3ef806e4000c73`): `npx skills find [query]` (lines 150 and 170-182).
- `tools/sota-convergence/landscape-sweep/README.md` (Evidence contract, Skills modality), and
  [the skills trial record](2026-09-25-skills-trial-and-usage.md) (lines 88-116 and 670-673).
- The source pins: `gh api repos/<owner>/<repo>/commits/<default branch>` on 2026-09-30, recorded in the catalog.
- The checks: `tests/test_landscape_sweep_skills.py` and `tests/test_landscape_sweep_harness.py`.
