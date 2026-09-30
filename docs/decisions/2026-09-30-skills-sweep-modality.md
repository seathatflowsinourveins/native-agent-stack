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

- **Claude Code.** A true-valued `disable-model-invocation` in the skills frontmatter stops Claude from loading a
  skill automatically and from preloading it into subagents. Boolean fields accept `true`, `yes`, `on` and `1` (and
  `false`, `no`, `off`, `0`) in any letter case; before v2.1.218 only `true` and `false`
  ([skills, Frontmatter reference](https://code.claude.com/docs/en/skills#frontmatter-reference)).
- **Codex.** `agents/openai.yaml` `policy.allow_implicit_invocation` defaults to true. When it is false, Codex never
  invokes the skill implicitly, and explicit `$skill` invocation still works
  ([Codex skills, Optional metadata](https://developers.openai.com/codex/skills#optional-metadata)). Codex
  rust-v0.157.1 reads the file with serde_yaml 0.9.34, which takes only a plain `true` or `false` as a boolean. When it
  cannot deserialize the file, Codex ignores all of it, so a quoted `"false"` or a `no` leaves implicit invocation on.
- **Agent Skills specification.** A skill's `name` has 1-64 lowercase letters, digits and hyphens and matches its
  folder. Its `description` has 1-1024 characters
  ([agentskills.io/specification, Frontmatter](https://agentskills.io/specification#frontmatter)).
- **The skills CLI.** The manifest pins vercel-labs/skills v1.7.0. Its `discoverSkills` decides which SKILL.md
  `npx skills@1.7.0 add owner/repo --skill <name>` installs:
  - a root `SKILL.md` with a name and description is the repository's only skill;
  - otherwise the CLI searches the root's child folders, then `skills/` (with `.curated`, `.experimental` and
    `.system`) and 30 agent folders, each three levels deep, where a shallower `SKILL.md` shadows the folders below
    it, then the skill folders a `.claude-plugin` manifest declares;
  - a name found in one location is skipped in the later ones;
  - only when none of these holds a skill does it search every folder up to five levels deep.

  The README documents the rule ("Skill Discovery" and "Plugin Manifest Discovery"), but its folder list differs
  from the code: it names 31 folders, such as `data/skills/`, that the code never searches, and omits 7 that it
  does, such as `.github/skills`. The code decides.
- **Structured outputs.** OpenAI Structured Outputs support `pattern` on strings in strict mode
  ([Structured Outputs, Supported properties](https://developers.openai.com/api/docs/guides/structured-outputs)).
  The skills schema's patterns therefore stay within what the Codex lane's `--output-schema` accepts.
- **Skills trial.** The trial's selection rules are a named gap, no duplicate of a native capability, no conflict
  with the canonical instructions, and one winner per capability
  ([trial record, Selection rule](2026-09-25-skills-trial-and-usage.md#selection-rule)). Its security-audit bake-off
  names skill-creator's paired with-skill/without-skill benchmark as the comparison harness
  ([trial record, Addendum 2026-09-27](2026-09-25-skills-trial-and-usage.md#addendum-2026-09-27-security-audit-trial-row-stale-upstream-flags-sandbox-gate)).

## Alternatives

1. **A separate skills sweep script beside the packaged sweep.** Rejected: it would fork the evidence contract the
   harness already enforces, which the README's Evidence contract lists:
   - two-family survival with refute-by-default votes;
   - retained failures and their reopen entries;
   - the effort and WebSearch-cap checks, and the GPT-6 copy check;
   - source reviews.

   It would also duplicate the runner, the conversion and the result tools, each of which carries review repairs.
2. **A modality inside the packaged sweep.** Chosen. Four variants were rejected along the way:
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
   - **A self-written source-review rule** (the folder named `<name>` must be unique in the tree). Rejected by the
     independent review. At the catalog pins it refused 254 of affaan-m/ECC's 296 skill names, whose translations sit
     under `docs/<lang>/skills` and agent copies under `.kiro/skills`. It also refused 2 of microsoft/skills' names and
     1 of openai/skills'. The CLI's own order resolves 294 of ECC's names. Across the 22 GitHub sources it finds only
     one same-location ambiguity: `openai/skills@openai-docs`, in both `skills/.curated` and `skills/.system`.

## Decision

The packaged sweep gains `modality: "skills"`.

- **Catalog.** [`catalogs/landscape/skills-lifecycle.json`](../../catalogs/landscape/skills-lifecycle.json) keys 13
  lifecycle tasks as `skills-<task>` layers. It covers every pinned skill once and pins 23 sources at the commits
  `gh api` read on 2026-09-30. The skills.sh registry is searched with the manifest's pinned
  `npx skills@1.7.0 find`.
- **Stale source.** Maintenance was checked for all 22 GitHub sources under the common block's rule: stale when
  archived or with "no commit on its default branch in the last 90 days", established with
  `commits?since=<date 90 days ago>`, not from `pushed_at`. Only `openai-skills` failed: its last `main` commit,
  `49f948fa`, is dated 2026-06-24, 98 days before the check. It carries a `maintenance` record with that API fact.
  - It stays listed for its four installed skills. `skills-ci-pr` and `skills-security` name it as an open gap
    ("Stale source: replacement via this sweep").
  - `discover_skills` labels its skills `not_adopted` unless a maintained fork or replacement is found.
- **Inputs and scope.** `build_inputs.py --modality skills` builds the layer inputs.
  - `known_skills` keeps each comma-separated name of the manifest's excluded entries whole, as the committed
    manifest states them.
  - Task texts, open gaps and the installed skills' `gap` fields pass whole.
  - `--skills-scope` prints the frozen scope in `saturation_ledger.py --scope`'s format, with the ledger's own
    `skills_requirement_sha256`.
- **Templates.** `build_args.py` resolves the modality at build time. A skills run's `discover` and `critic` are
  `discover_skills` and `critic_skills`, and `facts` and `fit` end in `modality_skills`.
  - The invocation flags follow the clients: a true-valued `disable-model-invocation` (true/yes/on/1 in any letter
    case) and a plain `allow_implicit_invocation: false`.
  - A skill conflicts with the canonical instructions when it writes `CLAUDE.md` or `AGENTS.md` on its own
    initiative. Editing them when asked is the `skills-agent-docs` task's requirement.
  - A repository run's frozen templates and `prompts_sha256` (`9c34fa72…f14b`) are unchanged. The tests pin both
    runs' values.
- **Schema.** `schemas/discover-skills.json` is strict. Its `comparison_that_would_overturn` must name skill-creator
  or promptfoo.
- **Identity.** `sweep.js` merges skill proposals by `skill_ref` and carries it as the row's `repository`. A run
  covers one modality.
- **Source reviews.** `source_reviews.py` reviews a skill survivor at its adjudicated pin, which `convert.py` copies
  into `survivors.json` with the proposal's `skill_md_sha256`. It finds the SKILL.md in the CLI's discovery order.
  - It falls back to the default branch only for an unreadable pin, and says so.
  - It refuses a SKILL.md whose hash differs from the judged one, and a true same-location ambiguity.
  - `make_result.py` refuses a `RESULT.json` while any survivor lacks its review. The README says so.
- **Decision record.** `make_result.py --decision-record` writes a skills sweep's decision record. A layer that lost
  workers reads as incomplete, not refuted. The sweep edits no manifest.
- **Ledger.** `scripts/saturation_ledger.py` learns the skills catalog.
  - `--report` lists every task as a `skills/skills-<task>` layer, so `build_args.py --due-report` selects due
    skills layers.
  - `--append` and `--check` record a skills `RESULT.json`.
  - A skills survivor binds to its retained votes and source review, since a SOTA-convergence manifest has no skills
    section.

**Residuals.**

- **Ledger schema.** `catalogs/saturation/ledger.schema.json` lists only `foundation` and `us-equities` in its layer
  `catalog` enum, and that file is outside this change. The first skills record needs `"skills"` added there.
  `--check` is the enforced check; the schema test runs only when jsonschema is installed.
- **Resolver limits.** A folder's name stands for the skill's name field, which the specification requires to match.
  The CLI's `skills-lock.json` rule is not emulated: it skips installed copies under agent folders. In
  `agents/openai.yaml`, type errors outside `policy`, which also make Codex ignore the file, are not checked.
- **Not run.** No model was called, and no sweep was measured. The evidence is this repository's synthetic-fixture
  suite, plus two read-only checks of the resolver on 2026-09-30:
  - it matched `npx skills@1.7.0 add <repo> --list` exactly on six sources (ECC 294 skills, microsoft/skills 13,
    trailofbits/skills 83, openai/skills 43, mattpocock/skills 37, vercel-labs/agent-browser 1);
  - all 28 installed skills resolve to their manifest `path`.
- **Not exercised.** The GPT-6 lane has not run `discover-skills.json`'s `pattern` keywords, which the upstream
  documentation supports. `build_manifest.py` has no skills section, and a skills lane layer lands in
  `lane_groupings` (its docstring, lines 1301-1303).

## Overturn condition

Reconsider a separate skills sweep (Alternative 1) if a measured skills run shows that the modality cannot express a
skills verdict. For example:

- the refuters or the conversion lose or merge distinct skills;
- the returns cannot carry a verdict that a task's requirement needs, such as an invocation flag or a paired-benchmark
  comparison;
- the ledger cannot bind a skills record.

Revise the source-review resolver when the manifest pins another skills CLI release whose `discoverSkills` differs,
or when `npx skills add <repo> --list` disagrees with it on a source.

## Sources

- [code.claude.com/docs/en/skills](https://code.claude.com/docs/en/skills), fetched as `skills.md` on 2026-09-30
  (99,199 bytes, sha256 `8d22bd7ed1d0fcf62c879a406b84f052cbc9658fb62bed8cac2dd0067e1c811d`; an earlier fetch that
  day differed, so no line numbers are cited). Sections: Frontmatter reference (the field table and "Boolean fields
  accept ..."), and Restrict Claude's skill access (the default model invocation).
- [developers.openai.com/codex/skills](https://developers.openai.com/codex/skills), fetched as `skills.md` on
  2026-09-30 (sha256 `d15791562748e64a53dfec534b8558aa522e732cec0fdedcf7257fa4ef486a20`): Optional metadata.
- [agentskills.io/specification](https://agentskills.io/specification), fetched as `specification.md` on 2026-09-30
  (sha256 `4c649bdf0e0a51c9e215d9f91009ecdca05ee9d073edb6f37c20265bbd829e11`): Frontmatter, `name` and `description`.
- [developers.openai.com/api/docs/guides/structured-outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
  fetched 2026-09-30: Supported properties, `pattern`.
- [vercel-labs/skills at v1.7.0](https://github.com/vercel-labs/skills/tree/v1.7.0), tag commit
  `7407f3893ad4dceab546ac002c3ef806e4000c73`:
  - `README.md` (sha256 `f1835e9d5cc091a82b3ea75ec93bdd96e3c8f86187358ca046a3ac3acdb3983b`): "Skill Discovery"
    (lines 412-483), "Plugin Manifest Discovery" (lines 485-505) and `npx skills find` (lines 150 and 170-182);
  - `src/skills.ts`: `SKIP_DIRS`, `AGENT_PROJECT_SKILL_DIRS` (lines 12-43) and `discoverSkills` (lines 180-329);
  - `src/plugin-manifest.ts` `getPluginSkillPaths`, and `src/constants.ts` `DEFAULT_SKILL_CONTAINER_DEPTH`;
  - `src/add.ts`: `--skill` includes internal skills, and a GitHub source is cloned before discovery;
  - `src/blob.ts` `PRIORITY_PREFIXES` (lines 306-342), which lists the code's locations.
- [openai/codex at rust-v0.157.1](https://github.com/openai/codex/tree/rust-v0.157.1), tag commit
  `36650394c5b38c2990ccf2a3457165ca3e9d9726`:
  - `codex-rs/ext/skills/src/loader/metadata.rs` (lines 27-56 and 130-139) and `codex-rs/skills/src/model.rs`;
  - `codex-rs/Cargo.lock` pins serde_yaml 0.9.34, whose `src/de.rs` (tag commit
    `2009506d33767dfc88e979d6bc0d53d09f941c94`) holds `parse_bool` (lines 932-938), `parse_null` (lines 925-930) and
    `deserialize_option` (lines 1517-1558).
- `tools/sota-convergence/landscape-sweep/README.md` (Evidence contract, Skills modality), and
  [the skills trial record](2026-09-25-skills-trial-and-usage.md) (Selection rule; Addendum 2026-09-27).
- The source pins: `gh api repos/<owner>/<repo>/commits/<default branch>` on 2026-09-30, recorded in the catalog.
  The maintenance check was `gh api 'repos/<owner>/<repo>/commits?sha=<default branch>&since=2026-07-02T00:00:00Z&per_page=1'`
  on 2026-09-30, and its result is recorded in the catalog's notes and in `openai-skills`' maintenance record.
- The checks: `tests/test_landscape_sweep_skills.py`, `tests/test_landscape_sweep_harness.py` and
  `tests/test_saturation_ledger.py`.
