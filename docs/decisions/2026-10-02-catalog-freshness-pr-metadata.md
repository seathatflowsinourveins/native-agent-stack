# Catalog-freshness PR metadata — 2026-10-02

Lane: foundation. North-star action served: keep the source-refresh evidence PRs usable by the same review and acceptance gates as the foundation work that prepares research runtime workers.

At `18eea2c1de992b46c266d79ef0cc40f93c9fb943`, the catalog-freshness workflow creates and updates a report-only PR without a lane label or a SOTA-sources section. Native GitHub reads confirmed both omissions on [PR527](https://github.com/seathatflowsinourveins/native-agent-stack/pull/527). The required `sota-sources` check needs a nonempty, case-sensitive section, and `docs/lanes.md` requires a lane label.

The workflow now adds `lane:foundation` on creation and update and puts the matching lane and `### SOTA sources` in its generated description. The source section points to the current PR's source-review artifacts and the pinned native GitHub CLI metadata interfaces. The description remains independent of any particular workflow run, preserving the existing concurrent-proposal behavior. Evidence registration alone does not make this report-only foundation-tool change a shared-lane decision.

The existing workflow permission scope, opt-in conditions, branch lease, report-only semantics, approval-required behavior and manual review remain unchanged. No job is dispatched by this change, and no upstream candidate or runtime pin is selected.

## SOTA sources

- [cli/cli v2.102.0](https://github.com/cli/cli/tree/fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd): `pkg/cmd/pr/create/create.go` and `pkg/cmd/pr/edit/edit.go`; staged native `gh pr create --help` exposes `--label`, `gh pr edit --help` exposes `--add-label`, and both expose `--body-file`, each returning exit 0.
- [Native gh create reference](https://cli.github.com/manual/gh_pr_create) and [edit reference](https://cli.github.com/manual/gh_pr_edit).
- Existing [repository PR template](../../.github/pull_request_template.md), [lane policy](../lanes.md) and [bot-dispatch decision](2026-09-23-bot-pr-dispatch.md).

## Acceptance

Local observations:

- `python3 -m unittest tests.test_catalog_freshness_propose` exited 1: 80 tests ran, 79 passed and the publication-validator test detected the edited workflow's stale registered hash and byte count. The supported `host_receipts.register_file` registrar updated only that file's registration. The targeted retry, `python3 -m unittest tests.test_catalog_freshness_propose.RebuildExplorerSubprocessTests.test_general_publication_validator_passes_after_the_run`, exited 0 (one test). The other 79 passing tests were not rerun.
- `python3 scripts/validate.py` then exited 0: 69 components, 9,315 hashed files, four profiles and 186 receipts passed integrity and scope checks.
- The actual shell description block rendered locally with exit 0 (1,085 bytes, lane present). The existing `tests.test_sota_sources_gate.run_check` helper evaluated the unchanged reusable gate against that rendered body and returned `SOTA sources section present (496 characters).` This is a local gate observation, not GitHub execution.
- Native `kjanat/actionlint` v1.17.0, the revision selected by this repository's CI, exited 0 on `.github/workflows/catalog-freshness.yml`. Its release archive and checksum-file digests matched both the published checksum and release API. The initial PATH lookup exited 127; the staged upstream release supplied the missing executable without changing the shared installation. Source: [v1.17.0 release](https://github.com/kjanat/actionlint/releases/tag/v1.17.0) and [CI selection](../../.github/workflows/validate.yml).

These establish local integration and native workflow syntax. A future authorized bot proposal establishes hosted create/update behavior. Inspect the actual generated body and label on that proposal. Hosted acceptance and independent review remain open; no workflow was dispatched solely to manufacture them. Manual PR metadata repair is an alternative, but leaves future proposals with the same omission. A supported upstream change to PR metadata flags or a repository change to lane/source requirements would require revisiting this implementation.
