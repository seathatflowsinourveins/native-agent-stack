# Decision: harden the last three workflows, pin exact release comments, and give the token workflow discriminating fixtures (2026-09-26)

**Decided by:** work package WP10 of the 2026-09-26 native-workflow wiring plan, in an owned
worktree (branch `claude/gha-hardening-fixtures-20260926`, base `771f25f8`), for review by the
coordinator.

**Scope:**
- `.github/workflows/native-token-e2e.yml`, `.github/workflows/native-offhost-app-state.yml` and
  `.github/workflows/native-offhost-restore.yml`: a `step-security/harden-runner` first step in
  audit mode on each of their four jobs, and exact-release comments on six `uses:` pins.
- The two recovery plans' prospective bindings (`offhost-app-state/plan.json`,
  `offhost-restore/hosted-plan.json`) and one sentence in each plan README.
- `scripts/native_token_ci.py`, two new fixtures and their tests: discriminating inputs.
- `tests/test_workflow_hardening.py`: no exempt workflow remains; a version-comment guard; the
  tests `docs/github-automation.md` cites must exist.
- Pins, links and the vLLM compatibility sentence of `docs/foundation-stack.md`, with
  `tests/test_foundation_stack_pins.py` holding its release links and `gh release view` example to
  `manifests/stack.json`; a dated sentence and the rewritten `harden-runner` paragraph in
  `docs/github-automation.md`.

## Decision

### 1. `harden-runner` on every `ubuntu` job

All four remaining jobs now start with the same step as the other 31 harden-runner steps:
`step-security/harden-runner@e14015d583714f6e62063499dc959a02595150a1 # v2.21.1` with
`egress-policy: audit`. `gh api repos/step-security/harden-runner/releases/latest` returned
`v2.21.1` (2026-08-30), and its tag resolves to that commit. All 32 `ubuntu` jobs now start with it;
`HASH_FROZEN` in `tests/test_workflow_hardening.py` is empty, and a guard test keeps these four
jobs hardened.

- **`native-token-tools` (`native-token-e2e.yml`).** Its exemption was to end with "a re-run of
  that evidence which re-pins the workflow with the step in place"
  ([fix round](2026-09-22-actions-hardening-fix-round.md), "Integration follow-up"). Two local
  `--install` runs re-recorded the harness receipts against the new workflow bytes (`fb06cf92…`)
  ([evidence](../../evidence/artifacts/token-workflow-hardening-20260926/README.md)). Those runs
  call `scripts/native_token_ci.py` directly, so no workflow step, harden-runner included, ran in
  them. One of the four protected receipts is a hosted run
  (`full-stack-convergence-20260921/hosted-native-token-workflow.json`, run 35610682345). The pull
  request's own hosted `native-token-tools` run, which the workflow's `pull_request` paths start, is
  the step's first execution and that receipt's re-run; the overturn is complete only once that
  run's id and artifact are retained. Ten retained files keep recording the old bytes (`d98bbefd…`)
  as history: the four receipts the fix round counts (listed in `docs/github-automation-evidence.json`),
  the four receipts and the controls report of
  `native-token-ci-extension-20260926`, and `sota-refresh-20260925/rtk/out/native-token-ci-rtk-only.json`.
- **`source`, `destination` (`native-offhost-app-state.yml`) and `synthetic-restore`
  (`native-offhost-restore.yml`).** These are manual recovery trials. Their accepted hosted runs
  (35541091430 and 35537533416, 2026-09-20) predate the current workflow bytes. The plans'
  `frozen_sources` are prospective bindings for the next dispatch, which `run.py` and `verify.py`
  check. On 2026-09-20 the maintainer refreshed them after reviewed logging and Action-pin changes
  (`37a3b436`, "repair active recovery plan bindings"), noting that the accepted runs keep their
  execution revisions and plan digests and that no new run is claimed. This change refreshes them
  the same way, with a `corrections` line in `hosted-plan.json` and a sentence in each README.

  This lifts their exemption on a different ground from the one the fix round names. Its operative
  overturn is the "Integration follow-up", which superseded the earlier gap paragraph and that
  paragraph's "coordinator instruction to extend the bounded objective" clause: "a re-run of that
  evidence which re-pins the workflow with the step in place". No off-host run with the step has
  happened, so that condition is not met for `source`, `destination` or `synthetic-restore`. The
  latest dispatches, 35964963227 and 35964966279 (2026-09-24, both successful, cited by no record in
  the repository), ran the bytes before this change. The ground here is
  that the pinned hashes are prospective dispatch bindings rather than the accepted runs' evidence,
  following the `37a3b436` precedent, and it stands only if the coordinator accepts it at review.
  The alternative that meets the operative condition is to dispatch both workflows on the pull
  request's branch before merge and cite their run ids. Three reasons support adding the step now:
  - The step is already qualified beside the same sandbox. `nautilus-offline-replay`
    (`native-foundation-e2e.yml`) starts with it and runs `sudo bwrap --unshare-all --unshare-net`.
    Its five latest hosted runs (2026-09-25) succeeded; `synthetic-restore` uses the same `bwrap`
    network unsharing, and `source` uses `unshare --net`.
  - These are the jobs that receive the fixture-only Actions secret, so an egress audit log matters
    most there.
  - Audit mode only records egress; it cannot fail a step or block a call.

  What is not claimed: no recovery trial ran with the step. The next dispatch of each workflow is
  the first run with it, and that dispatch's own receipt is the evidence.

### 2. Exact-release comments on every SHA pin

Six pins carried a moving major tag as their comment (`# v7` on five `upload-artifact` pins,
`# v8` on one `download-artifact` pin). They now name the release of the same SHA, `# v7.0.1` and
`# v8.0.1`; no SHA changed. `validate.yml` runs zizmor with the job token, so its online
`ref-version-mismatch` audit runs, and a finding fails that required check. zizmor 1.30.1 reads any
single-word comment as a version (`VERSION_COMMENT_PATTERN`, `crates/zizmor/src/models/version.rs`)
and reports a Medium finding at the regular persona when that ref's commit differs from the pin
(`crates/zizmor/src/audit/ref_version_mismatch.rs`). The next upload-artifact or download-artifact
release that moves `v7` or `v8` would therefore have failed `validate` on every pull request. The
failure would have lasted until a Dependabot bump, which the 7-day cooldown and weekly schedule
delay by one to two weeks. The 2026-09-21 review judged these comments cosmetic: "Normalize those
comments with the next functional change" (`docs/github-automation-evidence.json`,
`frozen_sources`). The harden-runner step is that change. `PinningTests.test_pin_comments_name_an_exact_release_outside_hash_frozen_workflows`
now guards it offline.

### 3. Discriminating fixtures in `native-token-e2e`

The harness now gives five tools an input on which native behaviour differs measurably from a
passthrough or a plain-text tool. Each check is held against that baseline:

- RTK: a 12-commit history with long bodies and trailers. The check requires the compact form
  (2,880 bytes against git's 6,599), an exact `rtk proxy` passthrough, a ledger saving for the
  filter and none for the proxy, and the default 10-commit window.
- MarkItDown: a multi-element HTML page whose ten element checks all hold on the conversion and all
  fail on the raw HTML and on its tag-stripped text.
- ast-grep: `subprocess.run($$$, shell=True, $$$)`, which matches a call spread over five lines.
  The closest single-line regex matches a comment and a string instead.
- Repomix: compression must drop the bodies. The existing check also passed on an uncompressed
  pack.
- TOON: the tabular block, smaller than the JSON. Other valid encodings pass the round trip too.

Real-tool controls (13 arms) fail exactly the targeted check. They also found one defect before
merge: markdownify escaped `_`, so a leaked marker went unseen. The 25 added commands took 0.510
and 0.539 seconds in the two final runs, and the job keeps its 20-minute limit (the hosted job took
about 1 minute 45 seconds before this change). Details and every run:
[`evidence/artifacts/token-workflow-hardening-20260926/`](../../evidence/artifacts/token-workflow-hardening-20260926/README.md).

### 4. Action pins against their latest releases (inventory of the base commit, 2026-09-26T16:02Z)

| Action | Pinned SHA | Comment tag | Uses | Latest release | Status |
| --- | --- | --- | --- | --- | --- |
| `actions/attest` | `1e69f48acb82` | v4.2.2 | 3 | v4.2.2 (2026-08-04) | latest |
| `actions/cache` | `55cc8345863c` | v6.1.0 | 1 | v6.1.0 (2026-06-26) | latest |
| `actions/checkout` | `3d3c42e5aac5` | v7.0.1 | 30 | v7.0.1 (2026-07-20) | latest |
| `actions/dependency-review-action` | `a1d282b36b6f` | v5.0.0 | 1 | v5.0.0 (2026-05-08) | latest |
| `actions/download-artifact` | `3e5f45b2cfb9` | v8.0.1, v8 | 6 | v8.0.1 (2026-03-11) | latest |
| `actions/github-script` | `3a2844b7e9c4` | v9.0.0 | 1 | v9.0.0 (2026-04-09) | latest |
| `actions/setup-go` | `b7ad1dad31e0` | v7.0.0 | 3 | v7.0.0 (2026-07-16) | latest |
| `actions/setup-node` | `820762786026` | v7.0.0 | 1 | v7.0.0 (2026-07-14) | latest |
| `actions/setup-python` | `5fda3b95a4ea` | v7.0.0 | 13 | v7.0.0 (2026-07-20) | latest |
| `actions/upload-artifact` | `043fb46d1a93` | v7.0.1, v7 | 27 | v7.0.1 (2026-04-10) | latest |
| `github/codeql-action/upload-sarif` | `1c5b675653bb` | v4.38.1 | 3 | v4.38.2 (2026-09-24) | behind; in Dependabot's 7-day cooldown |
| `ossf/scorecard-action` | `2d1146689b8c` | v2.4.4 | 1 | v2.4.4 (2026-07-23) | latest |
| `step-security/harden-runner` | `e14015d58371` | v2.21.1 | 31 | v2.21.1 (2026-08-30) | latest |

Every comment's tag resolved to its pinned SHA, and the advisory database lists no advisory for any
pinned version. After this change harden-runner has 35 uses and no major-only comment remains.

`github/codeql-action` publishes CodeQL bundles and action versions in one release list, and its
`releases/latest` answered `codeql-bundle-v2.27.1`. The action release v4.38.2
(`2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2`, 2026-09-24T10:27Z) only moves the default bundle to
2.27.1. Dependabot does not consider a version until the cooldown after its release has passed
(GitHub's options reference, `cooldown`). So the weekly run of Monday 2026-09-28 09:00 UTC skips it,
and 2026-10-05 is the first eligible run. `.github/dependabot.yml` is unchanged.

### 5. Living documents

`docs/foundation-stack.md` (not a new-machine file) had drifted from `manifests/stack.json`:
ai-memory 2.3.2, vLLM 0.25.0, the RTK `v0.49.0` release link and the pre-redirect
`chopratejas/headroom` repository. Its table now names the manifest pins: ai-memory 2.4.1 (macOS
pin 2.3.2), vLLM 0.30.0, the RTK `v0.50.0` link and `headroomlabs-ai/headroom`. A dated note keeps
the 2026-09-20 acceptance receipt's versions as history. The review of this change found three
sentences the first sweep left behind: the ai-memory `gh release view` example named 2.3.2, the vLLM
paragraph still called 0.25.0 the compatibility pin, and the dated note credited every newer pin's
`freshness` note with a winner-pin statement only ai-memory's and RTK's make. They now follow the
manifest, and `tests/test_foundation_stack_pins.py` fails on a release link or `gh release view`
command that names a version other than the manifest pin. Items owned elsewhere are listed in the
work package's report, not changed here: the handbook's claude-code and codex pins (u4/u5), the
socraticode pin (#345), the hosted-model catalog, and new-machine files during the release window.

## Alternatives considered

- **Keep the off-host exemptions until a hosted dispatch.** This was the first draft of this
  record. It rested on the belief that the plans' hashes were the accepted runs' own evidence. They
  are not: the app-state receipt pins plan digest `ba247c28…` while the file had become
  `d8afd7d5…`, and both runs predate `37a3b436`. It would also have left the major-only comments
  in place, and so the latent `validate` failure.
- **Exact comments without the step, for the off-host workflows.** This needs the same binding
  refresh and leaves the jobs that hold a secret without an egress audit.
- **`exclude-paths` for the off-host workflows in Dependabot.** Not taken: the package was told to
  leave Dependabot's configuration alone, and it would also stop security bumps there.
- **A zizmor ignore comment.** The gate runs with `--no-ignores` by design.
- **Pin exact byte-for-byte outputs in the new fixture checks.** Rejected for MarkItDown and
  Repomix, whose markdownify, beautifulsoup4 and tree-sitter dependencies resolve at installation.
  The checks accept each tool's formatting variants and still reject the baselines. TOON's encoder is
  bundled in its CLI, so its exact text is pinned.

## Comparison that would overturn it

- The first dispatch of an off-host workflow fails in or because of the harden-runner step. Remove
  the step from that workflow, refresh its binding again, record the failed run, and restore a named
  exemption: put the workflow back in `HASH_FROZEN` with the file that pins it, and drop it from
  `FORMERLY_HASH_FROZEN`, whose guard test otherwise fails.
- The pull request's hosted `native-token-tools` run fails or slows past its budget because of the
  step. Revert the step there, citing that run, with the same `HASH_FROZEN` and
  `FORMERLY_HASH_FROZEN` changes.
- The coordinator does not accept the prospective-binding ground for the off-host jobs (section 1).
  Dispatch both workflows on the pull request's branch and cite their run ids before merge, or take
  the step out of both, restore their earlier bindings and restore their exemptions as above.
- A pin bump that changes a native behaviour a new check freezes (for example RTK's default window
  or TOON's tabular text). Update the oracle from the new release's source or documentation, with a
  control run; do not loosen the check.

## Evidence class

`local_integration` for the harness runs, the controls, the unit tests and the mutation check;
`local_static_analysis` for zizmor 1.30.1 (`--offline --no-config --no-ignores --persona regular
--strict-collection .`: no findings) and actionlint 1.7.12 (exit 0); `documented_api_check` for the
`gh api` lookups (releases, tags, advisories, hosted run conclusions). zizmor's online audits were
not run locally, because they need a token this package does not read; their inputs were checked
through `gh api`, and the pull request's `validate` job runs them. No hosted run of the changed
workflows is part of this record.

## Primary sources

- step-security/harden-runner v2.21.1: `gh api repos/step-security/harden-runner/releases/latest`
  and `git/ref/tags/v2.21.1`.
- zizmor v1.30.1 source: `crates/zizmor/src/audit/ref_version_mismatch.rs`,
  `crates/zizmor/src/models/version.rs`; audit documentation <https://docs.zizmor.sh/audits/>
  (`ref-version-mismatch`, `concurrency-limits`).
- Dependabot options reference, `cooldown`:
  <https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference>.
- RTK v0.50.0 source: `src/cmds/git/git_cmd.rs` (`run_log`, `filter_log_output`,
  `DEFAULT_LOG_LIMIT`), `src/core/guard.rs` (`never_worse`).
- markdownify 1.2.3 escaping options (`escape_underscores`, default true):
  <https://pypi.org/project/markdownify/>; MarkItDown 0.1.8 wheel metadata (unpinned `markdownify`,
  `beautifulsoup4`).
- ast-grep pattern syntax (`$$$`, syntax-tree matching): <https://ast-grep.github.io/guide/pattern-syntax.html>.
- Repomix code compression (tree-sitter; signatures kept, implementations removed):
  <https://repomix.com/guide/code-compress>.
- `@toon-format/cli` 4.1.1 package (no runtime dependencies; encoder bundled in `dist/index.mjs`).
- GitHub REST API: releases, git refs and tags, global security advisories
  (`/advisories?ecosystem=actions&affects=`), workflow runs.
