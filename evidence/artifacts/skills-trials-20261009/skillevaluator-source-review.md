# NVIDIA SkillEvaluator source review

Reviewed 2026-10-09. This record contains primary-source research and proposed native commands. No installation, local native check, inverse, comparison, fresh-session run, or memory measurement was executed by this reviewer. Trial outcomes and adoption decisions belong to the preregistered parent experiment.

## Exact source and maintenance

- Repository: [NVIDIA/SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator), Apache-2.0, not archived. REST repository metadata reported `pushed_at=2026-10-08T20:04:08Z`.
- Current stable release: [v0.5.0](https://github.com/NVIDIA/SkillEvaluator/releases/tag/v0.5.0), published `2026-10-06T18:10:49Z`.
- Tag object: the REST `git/ref/tags/v0.5.0` endpoint resolves directly to commit **7304d76cde371287b67ea99653409d014b6b9c85**. All source citations below use this immutable commit.
- Latest default-branch REST commit was **f32c88455b6007b7afca9d1d3909283226d52efa**, `2026-10-07T06:38:53Z`, a documentation refresh for v0.5.0. This is maintenance evidence, not the tested release pin.
- Earlier published releases: v0.4.0 on 2026-09-30, v0.3.0 on 2026-09-17, v0.1.0 on 2026-08-05. The v0.5.0 release lists changes and a v0.4.0-to-v0.5.0 changelog. Its GitHub release assets list was empty; this review therefore does not assert an official binary or wheel checksum.
- The owner sweep's `FINAL.md:73` and `sweep/out/survivors.json` identify this repository as `keep_but_compare` but do not supply a commit/version pin. The stable pin above was resolved independently through upstream REST.

Primary endpoints were queried with `gh api --cache 120s`: `repos/NVIDIA/SkillEvaluator`, `/releases?per_page=5`, `/releases/tags/v0.5.0`, `/git/ref/tags/v0.5.0`, and `/commits?per_page=1`.

## Quality evidence at the release pin

The REST check-runs endpoint at the release commit reported 17 checks: 14 successful and three skipped. Successful checks included Tests (Python 3.12), Tests (Python 3.13), HTML parser compatibility on 3.12.11 and 3.13.5, Package, Tier 2 on macOS and Windows, Tier 3 macOS contract/progress, native Windows fail-closed behavior, RHEL 8 security install, CodeQL, and Gitleaks. Dependency review and two classification checks were skipped.

Release-commit workflow runs:

- [CI: success](https://github.com/NVIDIA/SkillEvaluator/actions/runs/37505174678).
- [Security: success](https://github.com/NVIDIA/SkillEvaluator/actions/runs/37505174655).
- [Publish Docs: success](https://github.com/NVIDIA/SkillEvaluator/actions/runs/37505174557).

The [CI workflow:65](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/.github/workflows/ci.yml#L65) uses `uv sync --all-extras --locked --python 3.12`; [CI:75](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/.github/workflows/ci.yml#L75) runs `uv run pytest -q --cov=skillevaluator --cov-report=term-missing --cov-report=xml:coverage.xml`. [CI:117](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/.github/workflows/ci.yml#L117) also tests Python 3.13. The [pytest configuration:196](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/pyproject.toml#L196) excludes `live` and `integration` from the default test selection. Successful default CI is not evidence that this host ran a credentialed live experiment.

Supported source-checkout setup is documented in [installation:61](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/installation.mdx#L61) and [developer guide:20](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/developer-guide.mdx#L20). These targeted paths exist at the pin and use upstream pytest directly; they have not been run by this reviewer:

```sh
# From an exact release checkout, with UV_CACHE_DIR and UV_PYTHON_INSTALL_DIR
# confined to the lane prefix:
nice -n 10 ionice -c2 -n7 timeout 600 uv sync --all-extras --locked --python 3.13
nice -n 10 ionice -c2 -n7 timeout 600 uv run pytest -q tests/validators/test_schema.py
nice -n 10 ionice -c2 -n7 timeout 600 uv run pytest -q tests/validators/test_quality_score.py
nice -n 10 ionice -c2 -n7 timeout 600 uv run pytest -q tests/cli/test_validate_defaults.py
```

These are targeted selections of the documented upstream pytest harness, rather than a claim that upstream prescribes these three exact module selections. Full-extras setup is broader than the base trial install and should be treated as a separate quality-check environment.

## Supported scoped install, native checks, and inverse

[Installation:30](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/installation.mdx#L30) recommends `uv tool install --python 3.13` from the upstream Git repository. [Installation:37](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/installation.mdx#L37) supports a base install. [pyproject:37](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/pyproject.toml#L37) deliberately keeps Harbor and LLM clients out of the base dependency set. Python must be at least 3.12 and below 3.14.

The installed uv CLI was `uv 0.12.22`; its native `uv help tool uninstall` confirms `uv tool uninstall <NAME>`. Official uv documentation supports the [managed-tool directory](https://docs.astral.sh/uv/reference/environment/#uv_tool_dir), [tool executable directory](https://docs.astral.sh/uv/reference/environment/#uv_tool_bin_dir), [cache directory](https://docs.astral.sh/uv/reference/environment/#uv_cache_dir), and [managed-Python directory](https://docs.astral.sh/uv/reference/environment/#uv_python_install_dir) overrides used here. These variables isolate an install without changing client registrations or shell configuration.

```sh
SKILLEVAL_TRIAL_PREFIX=<host-home>/.local/state/native-agent-stack/research/api-surfaces-trials/skillevaluator
export UV_TOOL_DIR="$SKILLEVAL_TRIAL_PREFIX/uv-tools"
export UV_TOOL_BIN_DIR="$SKILLEVAL_TRIAL_PREFIX/bin"
export UV_CACHE_DIR="$SKILLEVAL_TRIAL_PREFIX/uv-cache"
export UV_PYTHON_INSTALL_DIR="$SKILLEVAL_TRIAL_PREFIX/uv-python"
export UV_PYTHON_CACHE_DIR="$SKILLEVAL_TRIAL_PREFIX/uv-python-cache"

nice -n 10 ionice -c2 -n7 timeout 600 uv tool install --python 3.13 \
  'skillevaluator @ git+https://github.com/NVIDIA/SkillEvaluator.git@7304d76cde371287b67ea99653409d014b6b9c85'

# Frozen fixture paths and report directories must be supplied by the
# preregistration. Neither command requires a provider or credential.
"$UV_TOOL_BIN_DIR/skillevaluator" validate <frozen-skill-directory> \
  --tiers 1 --checks schema,quality --no-llm --min-score 70 \
  -r json -o <lane-owned-report-directory>

# The standalone quality command is also documented and entirely offline.
"$UV_TOOL_BIN_DIR/skillevaluator" quality-check <frozen-skill-directory> \
  --min-score 70 -r json -o <lane-owned-quality-report-directory>

# Recorded inverse, using the same scoped UV_* variables:
uv tool uninstall skillevaluator
test ! -e "$UV_TOOL_BIN_DIR/skillevaluator"
test ! -e "$UV_TOOL_DIR/skillevaluator"
uv tool list
```

The threshold of 70 is upstream's documented default, not an observed trial outcome. Parent preregistration controls whether that default is retained. Record the checksum of the actual downloaded source/install artifact during execution; the Git pin alone does not satisfy the requested artifact-sha256 receipt. Uninstall removes the managed tool environment and executable; caches/interpreter material may remain within the lane prefix.

Check selection is documented at [Tier 1:68](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/tier1-validation.mdx#L68). The [CLI reference:203](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/cli-reference.mdx#L203) names `schema` and `quality`; [CLI reference:261](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/cli-reference.mdx#L261) documents the offline `quality-check` and its 70-point default. [Reports:21](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/reports.mdx#L21) documents explicit JSON output and scoped output directories.

## Blinding and substantive-test boundaries

- Tier 1 schema plus deterministic quality checks can operate on the same preregistered clean/defective skill fixtures without provider credentials. A comparison of these reports measures static fixture detection/scoring only. It does not establish semantic task quality, agent-task improvement, security coverage, overlap detection, or skill-repository superiority.
- Full required-scanner coverage requires additional tools. [Installation:18](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/installation.mdx#L18) names the security extra plus Semgrep, SkillSpector, and Gitleaks. Missing required scanners report INCOMPLETE. Selecting only schema/quality deliberately excludes those claims.
- The [content-type contract:94](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/tier1-validation.mdx#L94) supports explicit `--type rules`, with automatic rule detection documented for `.mdc` files under `team-rules/`. It does not document automatic Codex `AGENTS.md` support. Quality/lint/version are skipped for rules and workflows. AGENTS coverage therefore requires an explicit separate claim and measured check, or an untested-boundary entry.
- [Tier 2:7](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/tier2-deduplication.mdx#L7) requires a configured embeddings provider, plus a chat LLM for intra-skill verification. [Tier 2:24](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/tier2-deduplication.mdx#L24) requires a local catalog for inter-skill comparison. Neither route was run.
- [Tier 3:16](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/tier3-live-evaluation.mdx#L16) runs matched cases with and without a skill through Harbor. [Tier 3:263](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/tier3-live-evaluation.mdx#L263) documents `skillevaluator tier3 evaluate ./my-skill --agents codex --env-mode docker`; an agent override uses `--agent-model codex=<model>`, and Codex requires an OpenAI-compatible Responses model. Full-extras/tier3 install, provider access, and a running sandbox are prerequisites. This route was not run.
- The evaluated installation, Tier 3, dataset, report, and agent guides contain no documented blind-judge option. Reports expose `with-skill` and `without-skill` arm directories ([Tier 3:281](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/tier3-live-evaluation.mdx#L281)). The dimension-report source explicitly formats `with_skill`, `baseline`, and `lift` ([dimension_judge.py:114](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/src/skillevaluator/evaluation/dimension_judge.py#L114)). This does not prove that every internal trajectory grader sees repository identity; it establishes that native output alone is not an anonymous independent comparison. Parent must preregister and anonymize the external judge's exact inputs, exclude this source review/arm mapping, and retain native raw reports separately.

## Fresh-session reach without naming the tool

The pinned Git tree endpoint returned `truncated=false`. Its complete `SKILL.md` inventory is five reference workloads under `src/skillevaluator/tier3/reference_skills/` (`api-caller`, `calculator`, `create-custom-grader`, `task-list`, `text-analyzer`) plus `tests/fixtures/skills/simple/SKILL.md`. No `plugin.json`, `agent_plugin.yaml`/`.yml`, or tool-use routing skill was found in that pinned tree.

The reference workloads are evaluation targets, not a client install that automatically invokes SkillEvaluator. The documented native install puts the CLI on a tool executable path. Therefore this review found **no vendor-supplied client autoselection skill/plugin/install resource for an unnamed SkillEvaluator validation request at v0.5.0**. A custom routing skill was not created. The parent should record this missing adoption-stage resource and leave the fresh-session reach stage unproved.

The native Tier 3 workflow does offer isolated target-skill discovery for measuring another skill: [agent workspace options:374](https://github.com/NVIDIA/SkillEvaluator/blob/7304d76cde371287b67ea99653409d014b6b9c85/docs/agents-and-sandboxes.mdx#L374) default to staging only the evaluated target. That is a separate claim from automatically reaching SkillEvaluator itself. It was not exercised here.

## Evidence limits

Upstream API/doc/source observations above are measured research. Proposed install/test/inverse commands are unexecuted. The scoped static trial can justify a comparison-limited disposition; it cannot satisfy unrun Tier 2, Tier 3, automatic tool reach, or per-session PSS stages. No ADOPT-NOW conclusion is supplied by this source review.
