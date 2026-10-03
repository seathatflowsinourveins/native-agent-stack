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
  - Each modality keeps its own history. `previous_sweep`, and a repository run's default baseline manifest, come
    from the last completed sweep of the run's own modality, which the ledger names by its layers' catalogs. A skills
    sweep never empties a repository run's history or becomes its baseline, and a modality with no completed sweep
    gets an empty history.
- **Templates.** `build_args.py` resolves the modality at build time. A skills run's `discover` and `critic` are
  `discover_skills` and `critic_skills`, and `facts` and `fit` end in `modality_skills`.
  - The invocation flags follow the clients: a true-valued `disable-model-invocation` (true/yes/on/1 in any letter
    case) and a plain `allow_implicit_invocation: false`.
  - A skill conflicts with the canonical instructions when it writes `CLAUDE.md` or `AGENTS.md` on its own
    initiative. Editing them when asked is the `skills-agent-docs` task's requirement.
  - The modality leaves a repository run's frozen templates and `prompts_sha256` (`9c34fa72…f14b`) unchanged.
    After unit F3 (#553) pinned skill-creator, which the skills templates name for its paired benchmark, common's
    Skills paragraph names it as well, so both values moved: the repository run's to `b61956f3…726d` and the
    skills run's to `a76ee858…b460`. The tests pin both runs' values.
- **Schema.** `schemas/discover-skills.json` is strict. Its `comparison_that_would_overturn` must name skill-creator
  or promptfoo.
- **Identity.** `sweep.js` merges skill proposals by `skill_ref` and carries it as the row's `repository`. A run
  covers one modality.
- **Source reviews.** `source_reviews.py` reviews a skill survivor at its adjudicated pin, which `convert.py` copies
  into `survivors.json` with the proposal's `skill_md_sha256`, and at no other commit. It finds the SKILL.md in the
  CLI's discovery order.
  - Each candidate is validated before the order applies, by the CLI's own code: `skill_md.mjs` runs the CLI's
    `parseSkillMd`, `parseFrontmatter`, `sanitizeMetadata` and `getSkillDisplayName`, ported line by line, with the
    `yaml` package `skills-yaml.pin.json` pins (2.9.0 and its npm integrity, the CLI lockfile's). It installs
    nothing, runs only the installed files the pin hashes, and refuses an install whose bytes or lockfile integrity
    differ. A copy the CLI skips (no `name` or `description`, one that is not a string, a YAML parse error) is
    recorded with the CLI's own warning, so a valid later copy wins and a skill whose every copy is invalid is
    refused.
  - A copy gets no verdict, and stops the survivor when its verdict decides the CLI's pick, when node or a verified
    install is missing, when its frontmatter holds a line break other than LF or CRLF, and when its bytes are not the
    regular-file blob the tree lists (a symlink, content gh does not return, or other bytes). So does a `SKILL.md` gh
    cannot read.
  - The CLI walks a search location through a symlink at or above it (`readdir` follows it) and skips a symlinked
    skill folder inside one, while the git tree lists a symlink as one blob. A search location at or below a
    symlink, a folder whose `SKILL.md` is a symlink with skill folders below it, and `.claude-plugin` manifests behind
    a symlink or without verified bytes are unknown locations: one reached before the pick is decided stops the
    survivor, since the CLI may take a copy there first or skip its recursive search because of what it finds.
  - CI's `validate` job installs the yaml pin before the suite, as it does the tree-sitter-bash pin, so the reader
    tests run there; `tests/test_landscape_sweep_skills.py` fails an Actions job without the verified install, and
    fails the suite when the provisioning step is missing, late, retyped, unexported or skippable.
  - A copy's name is compared as the CLI matches `--skill` against it: the name `sanitizeMetadata` records, or the
    folder's name when that is empty (`getSkillDisplayName`).
  - It records the reader (`skill_md_reader`: package, integrity, the pin file's sha256) and the skill folder's git
    tree id at the pin (`skill_folder_tree_sha`, the CLI lock's `skillFolderHash`), verified to cover the SKILL.md and
    `agents/openai.yaml` bytes it read.
  - It reads `agents/openai.yaml` as Codex's serde_yaml does. A file that is not UTF-8, or holds a character libyaml
    refuses or a line break other than LF and CRLF, is unverified first. Then PyYAML's composer (libyaml's
    `CSafeLoader` when present) reads it when PyYAML is installed; without it only the plain block-mapping subset is
    read, and other syntax gives `codex_implicit: null` with the reason. That includes a double-quoted scalar anywhere
    in the file whose escape libyaml does not define, such as `"C:\skills"`.
  - A survivor with no pin, an unreadable or moved pin, a null hash, no valid copy, other bytes than the judged ones,
    or a tree that does not cover them gets no review. Its stopped entry (`status: stopped`, `pin_lookup`, `reason`)
    stops its layer.
  - `make_result.py` refuses a `RESULT.json` while any survivor lacks its review or its layer is stopped. For a
    skills layer, each review's `reviewed_commit` must be the adjudicated pin in the returns, over the judged
    `skill_md_sha256`, with the folder hash recorded. The README says so.
- **Decision record.** `make_result.py --decision-record` writes a skills sweep's decision record. A layer that lost
  workers reads as incomplete, not refuted. The sweep edits no manifest.
- **Ledger.** `scripts/saturation_ledger.py` learns the skills catalog.
  - `--report` lists every task as a `skills/skills-<task>` layer, so `build_args.py --due-report` selects due
    skills layers.
  - `--append` and `--check` record a skills `RESULT.json`.
  - A skills survivor binds to its retained votes and source review, since a SOTA-convergence manifest has no skills
    section.
  - `catalogs/saturation/ledger.schema.json` lists `skills` in its layer `catalog` enum beside `foundation` and
    `us-equities`, so a skills record validates against the schema as well as `--check`.

**Residuals.**

- **Resolver limits.** A folder's name stands for the skill's name field, which the specification requires to match.
  `add` keeps the first skill of each name and drops a later one (`dist/cli.mjs` line 1352; the two call sites that
  pass `includeDuplicateNames: true`, lines 7382 and 7588, are both in the update paths), so when an earlier folder
  named otherwise declares `<name>` the CLI installs that folder, and the review can name a later copy the CLI throws
  away. The CLI's `skills-lock.json` rule is not
  emulated: it skips installed copies under agent folders. In `agents/openai.yaml`, type errors outside
  `policy.allow_implicit_invocation` (in `interface`, `dependencies` or `products`), which also make Codex ignore
  the file, are not checked.
- **Reader limits.** The round-3 PyYAML and subset frontmatter readers are gone: an independent review found both
  giving a verdict on frontmatter the CLI's `yaml` package reads otherwise (under-indented quoted and flow
  continuations, bad nested indentation, an empty flow item, mismatched brackets, a lone CR or U+2028 read as a line
  break). What remains unverified:
  - **The yaml release.** The pin holds the CLI lockfile's yaml 2.9.0, but `skills@1.7.0` declares `"yaml":
    "^2.8.3"` as a runtime dependency its bundle imports, so npm resolves it when the CLI is installed: 2.9.1 on
    2026-09-30 (released 2026-09-11), the version of this host's install from the manifest's `cli.install`. The two
    gave identical results on the receipt's 2,455 corpus files, 139 edge cases and 200,000 random multi-line scalars
    (2.9.1 changed line unfolding in plain and single-quoted scalars and alias counting). A later 2.x is not checked
    until the pin moves.
  - **Line breaks other than LF and CRLF** in a frontmatter leave the copy without a verdict, even where the CLI's
    own verdict is definite, because libyaml-based readers such as Codex's serde_yaml break lines there. When the
    CLI's frontmatter pattern does not match a file that starts with `---`, the whole file counts as frontmatter, so
    such a break in its body also leaves it without a verdict.
  - **Symlinks and other bytes.** A symlinked `SKILL.md` has no verdict. The CLI walks a search location through a
    symlink at or above it (`readdir` follows it, `dist/cli.mjs` lines 1339-1370) and skips a symlinked skill folder
    inside one (`entry.isDirectory()` is false, `src/skills.ts` lines 284-298 and 141-149); the git trees API lists
    a symlink as one blob and nothing below it. The review does not resolve link targets: a location at or below a
    symlink, a `SKILL.md` symlink with skill folders below it and manifests behind a symlink or without verified
    bytes are unknown, and one reached before the pick is decided stops the survivor. That includes a layout where
    resolving the link would show it changes nothing: an agent folder linked to `skills/`, such as
    `.agents/skills -> ../skills`, is searched after `skills/` and holds only names already found, yet it stops a
    pick that would come from a later location. A symlinked location searched after the pick never stops it. At the
    catalog pins, 3 of the 22 GitHub sources hold a symlinked search location (`.agents/skills` in getsentry/skills,
    `.opencode/skills` in addyosmani/agent-skills and microsoft/skills) and none a symlinked `SKILL.md`; every pick
    the resolver makes in the 22 sources is decided before any symlinked location, so the rule stops none of them
    ([receipt](../../evidence/artifacts/skills-md-reader-20260930/README.md), `symlinks` step).
  - **`.gitattributes`.** The review reads each file's blob. The CLI reads its clone's checkout, where
    `.gitattributes` can change the bytes (`filter=lfs` leaves a pointer or fetches the object, eol and text
    normalization, `working-tree-encoding`); the review does not read `.gitattributes`.
  - **Claude Code's parser.** `disable_model_invocation` applies Claude Code's documented boolean rule to the value as
    the `yaml` package types it; Claude Code's own frontmatter parser was not run.
  - **CI.** `validate.yml`'s `validate` job installs the pin, so the reader tests run there. The two other jobs that
    run the whole suite, `adoption-bootstrap.yml` `validate-macos` and `catalog-freshness.yml` `freshness`, do not
    yet (the tree-sitter pin records the same two gaps): their reader tests skip, and the tripwire stands down there
    by name.
- **Stricter reviews.** A survivor whose discovery worker could not compute `skill_md_sha256` (the schema allows null
  for a worker that cannot run commands) can no longer be reviewed, so its layer stops until a rerun supplies it.
- **Not run.** No model was called, and no sweep was measured. The evidence is this repository's synthetic-fixture
  suite, plus three read-only checks on 2026-09-30:
  - the resolver matched `npx skills@1.7.0 add <repo> --list` exactly on six sources (ECC 294 skills,
    microsoft/skills 13, trailofbits/skills 83, openai/skills 43, mattpocock/skills 37, vercel-labs/agent-browser 1);
  - all 28 skills the manifest pinned before unit F3 (#553) resolve to their manifest `path` (F3's six re-pins and
    its skill-creator were not rechecked);
  - `skill_md.mjs` gave the CLI's verdict, recorded name, description and warning for all 2,455 `SKILL.md` files of
    the catalog's 22 GitHub sources at their pins (2,452 taken, 3 skipped), against two oracles: `parseSkillMd` and
    its helpers sliced byte for byte from the published `skills@1.7.0` `dist/cli.mjs` with yaml 2.9.0 and with the
    2.9.1 a fresh install resolves, and the installed CLI's `skills add <fixture> --list` run end to end (same skipped
    copies and warnings, same 1,693 names, and a planted invalid and a planted valid copy behaving as expected). On
    139 edge cases the reader agreed wherever it gave a verdict and gave none on the 9 with a line break other than
    LF or CRLF ([receipt](../../evidence/artifacts/skills-md-reader-20260930/README.md)).

  The first two checks measured the location order before candidate validation was added; validation changes a
  choice only where a copy is invalid, and no source was re-measured since.
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
or when `npx skills add <repo> --list` disagrees with it on a source. Re-port `skill_md.mjs` when that release's
`parseSkillMd`, `parseFrontmatter` or `sanitize.ts` differs. Re-pin `skills-yaml.pin.json` when the `yaml` release a
fresh install of the CLI resolves gives another verdict, name or warning than the pinned one on the receipt's corpus
and edge cases (rerun its comparison), or when the manifest starts pinning the CLI's dependencies.

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
  - `src/skills.ts`: `SKIP_DIRS`, `AGENT_PROJECT_SKILL_DIRS` (lines 12-43), `parseSkillMd` (lines 80-133: a
    SKILL.md without a name or description, or with non-string ones, is skipped), `discoverSkills` (lines 180-329:
    `tryAddSkillAt` adds no invalid skill, and the recursive fallback runs only when no skill was added) and
    `filterSkills` (lines 339-348: `--skill` matches the name field, or `getSkillDisplayName`'s folder name, lines
    331-333);
  - `src/frontmatter.ts` `parseFrontmatter` (lines 8-16), and `package.json`, `"yaml": "^2.8.3"` among the runtime
    `dependencies` (2.9.0 in the lockfile, whose integrity `sha512-2AvhNX3m…L4cA==` is the registry's for
    `yaml@2.9.0`); the published tarball's `dist/cli.mjs` (sha256 `fde68534…6701c`) imports `parse` from `"yaml"`;
  - `src/sanitize.ts`: `stripTerminalEscapes` (lines 18-52) and `sanitizeMetadata` (lines 61-65), the name recorded;
  - `src/plugin-manifest.ts` `getPluginSkillPaths`, and `src/constants.ts` `DEFAULT_SKILL_CONTAINER_DEPTH`;
  - `src/add.ts`: `--skill` includes internal skills; a GitHub source named with a ref (`owner/repo#<ref>`, as the
    adjudicated pin would be installed) is cloned before discovery, because the blob-install fast path returns null for
    a ref (published `dist/cli.mjs` lines 4101-4102). Without a ref, sources of the vercel, vercel-labs, heygen-com and
    remotion-dev owners and the listed repositories try that path first (lines 5190-5212): it reads the tree from the
    API, and when it succeeds it installs a downloaded snapshot without running `discoverSkills` (lines 4101-4174);
    when it returns null the source is cloned as well;
  - `src/blob.ts` `PRIORITY_PREFIXES` (lines 306-342), which lists the code's locations, and
    `getSkillFolderHashFromTree` (lines 277-301): a skill's `skillFolderHash` is its folder's GitHub tree id (the
    root tree's for a root SKILL.md);
  - the files above were compared byte for byte with the tag commit's on 2026-09-30.
- [eemeli/yaml at v2.9.0](https://github.com/eemeli/yaml/tree/v2.9.0), tag commit
  `ddb21b04cb889722cec8f89dc1b67f19d62d7f7d`, the npm package `yaml@2.9.0` (dist.integrity `sha512-2AvhNX3m…L4cA==`,
  gitHead that commit): the parser `skill_md.mjs` runs, pinned file by file in `skills-yaml.pin.json`.
  [v2.9.1](https://github.com/eemeli/yaml/releases/tag/v2.9.1) (commit `1440ecd3d1bff41e4ac399f8f6839e810328bd16`,
  2026-09-11; npm dist.integrity `sha512-3NxN8+78…Eb2yFw==`): "Limit recursive merge aliases" and "Simplify line
  unfolding during quoted string parsing"; its `dist/` differs from 2.9.0's only in
  `compose/resolve-flow-scalar.js` and `nodes/Alias.js`. `npm view yaml dist-tags` on 2026-09-30: latest 2.9.1.
- [dtolnay/unsafe-libyaml at 0.2.11](https://github.com/dtolnay/unsafe-libyaml/tree/0.2.11), the version Codex's
  `Cargo.lock` pins beside serde_yaml, tag commit `a7b8d1fbd93aefbca3003dcb5fcc6a9c2297e968`: `src/scanner.rs`
  lines 2195-2361 (the double-quoted escapes; "found unknown escape character"; the hex digits; surrogates and code
  points beyond U+10FFFF refused), `src/reader.rs` lines 381-395 (the characters its reader accepts; any other is
  "control characters are not allowed") and `src/macros.rs` lines 253-265 (`IS_BREAK_AT`: CR, LF, U+0085, U+2028 and
  U+2029 break a line).
- [openai/codex at rust-v0.157.1](https://github.com/openai/codex/tree/rust-v0.157.1), tag commit
  `36650394c5b38c2990ccf2a3457165ca3e9d9726`:
  - `codex-rs/ext/skills/src/loader/metadata.rs` (lines 27-56 and 130-139) and `codex-rs/skills/src/model.rs`;
  - `codex-rs/Cargo.lock` pins serde_yaml 0.9.34, whose `src/de.rs` (tag commit
    `2009506d33767dfc88e979d6bc0d53d09f941c94`) holds `parse_bool` (lines 932-938), `parse_null` (lines 925-930),
    `deserialize_option` (lines 1517-1558), `deserialize_bool` (lines 1266-1290) with
    `is_plain_or_tagged_literal_scalar` (lines 1149-1158), `deserialize_map` (lines 1660-1688) and the
    `MoreThanOneDocument` refusal (lines 105 and 142).
- PyYAML 6.0.1 (`yaml.compose_all` with `CSafeLoader`, the libyaml binding, or `SafeLoader`), used only for
  `agents/openai.yaml` and only when installed: the repository does not require it, and the tests run the subset
  reader either way.
- The tree-sitter-bash pin (`examples/claude-native/workflows/shell-parser.pin.json` and `child-usage.mjs`
  `loadShellParser`), whose pattern `skills-yaml.pin.json` and `skill_md.mjs` follow: a pinned npm install, verified
  file by file and by lockfile integrity, never vendored, and nothing parsed without it. Its CI provisioning step in
  `.github/workflows/validate.yml` and its fail-closed tests (`tests/test_shell_parser_ci.py`: runtime tripwire,
  structure checks, ratchet over whole-suite jobs, mutation controls) are the pattern of the yaml pin's step and of
  the CI tests in `tests/test_landscape_sweep_skills.py`. The step was run with npm 10.9.8 and the reader under
  Node.js 22.23.2, the versions of the ubuntu-24.04 runner image, and the install verified; the pin's 75 file hashes
  are the bytes of the registry tarball whose sha512 is the pinned integrity.
- Git's object ids ([Pro Git, Git Objects](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects)): the tests
  compare `git_blob_id` and `git_tree_id` with `git write-tree` and `git ls-tree` output.
- `tools/sota-convergence/landscape-sweep/README.md` (Evidence contract, Skills modality), and
  [the skills trial record](2026-09-25-skills-trial-and-usage.md) (Selection rule; Addendum 2026-09-27).
- The source pins: `gh api repos/<owner>/<repo>/commits/<default branch>` on 2026-09-30, recorded in the catalog.
  The maintenance check was `gh api 'repos/<owner>/<repo>/commits?sha=<default branch>&since=2026-07-02T00:00:00Z&per_page=1'`
  on 2026-09-30, and its result is recorded in the catalog's notes and in `openai-skills`' maintenance record.
- The checks: `tests/test_landscape_sweep_skills.py`, `tests/test_landscape_sweep_harness.py` and
  `tests/test_saturation_ledger.py`.
