# GitHub automation continuation

Scope: continue PR #26 in its existing isolated checkout; own routine workflows,
dependency maintenance, publication automation and their documentation. The
foundation coordinator owns recovery experiments and `native-offhost-app-state.yml`.
Do not mutate native runtimes, account/model configuration or trading state.

## Initial implementation reviewed before expansion

Base: `4a4382736804bffab6754d92492af282dcb2f165`.
Original PR head: `aeaf4773d25ef36dbc7f67d4c3e1569250647277`.
Independent review found no actionable defects in the complete original diff.
Reused recorded actionlint 1.7.12, zizmor, 49 security/registry tests, integrity
validation and exact HTML rebuild; unchanged qualification was not rerun.

Separate GitHub observation confirmed four successful PR runs and no duplicate
push runs for that revision:

- [validate 35539623928](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/35539623928)
- [token-report 35539623855](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/35539623855)
- [native-token 35539623917](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/35539623917)
- [native-foundation 35539623932](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/35539623932)

Native artifacts 10614510695 and 10614272134 existed and were unexpired at review.
Actual cancellation, first Dependabot event and post-merge events remain separate
unobserved behaviors.

## Inspected gaps and selected work

GitHub initially returned `[]` for rulesets, HTTP 404 `Branch not protected` for
main protection, Actions enabled with all actions allowed, default token read,
and workflow approval capability false. Public repository; no paid feature needed.

1. Require the two unconditional GitHub Actions jobs, with no strict freshness or
   human approval gate. Preserve native path filters and manual trial ownership.
2. Add the already qualified upstream actionlint release to routine CI, retaining
   its archive checksum and existing zizmor/integrity checks.
3. Prepare a manual trusted-main catalog/evidence artifact with native provenance.
   Its hosted attestation requires integration and explicit dispatch; static checks
   cannot establish issuance or verification.
4. Keep the existing active daily catalog maintenance task as sole agentic owner;
   evaluate a single source-cited upstream-change proposal without another schedule.
5. Publish a compact acceptance guide using the existing frozen native research
   comparison. No new model submissions or session/lifetime savings claims.

Integration is coordinated with the foundation task. It confirmed the two required
checks do not conflict with recovery publication; shared evidence-registry updates
must be reconciled with any intervening main commits.

Verification and source details are linked from [the handbook](../github-automation.md).

## Retained outcomes

The [compact command/platform record](../github-automation-evidence.json) retains
the before/after settings, original hosted IDs, actual analyzer output, initial
failure and unchanged native-research source hashes. GitHub independently returned
the two app-bound required contexts from `rules/branches/main`; the reviewed JSON
matched the separately retrieved ruleset configuration. No blocked merge was
attempted solely to test the settings.

Expanding actionlint from the original four changed workflows to all six exposed
two SC2024 warnings in the existing off-host restore apt-log redirections. The
foundation coordinator approved ownership of this narrow logging fix. Using
`2>&1 | tee` retains exact native apt argv, the same files and Bash pipefail.
Actionlint then returned exit 0 with empty output; zizmor returned exit 0 and `[]`.
The old recovery receipt remains scoped to its frozen workflow revision.

The native research acceptance guide reuses eight frozen answer results rather
than resubmitting models: 8/8 content passes, 6/8 complete protocol passes, with
both word failures and complete available usage preserved. The upstream pilot
identified a source-backed Nautilus catalog migration/interval safety concern;
its proposed native tests remain unrun and accepted runtime pins are unchanged.

Integration of main `9767e9ca1915378d539cd63dd0b56f652545dc9c` conflicted only
in the shared evidence registry, explorer manifest and generated HTML. Preserved
the incoming recovery records, restored this PR's handbook entry, and refreshed
only reviewed automation/document hashes. The first HTML rebuild correctly left
the old generated-file hash failing (`SHA-256 mismatch`, `byte count mismatch`);
refreshing that reviewed generated output is part of regeneration, with integrity
checks retained. This is structural reconciliation, not new recovery execution.

The isolated publication worker contributed only the workflow and provenance
guide from commit `e1473e03a0b46e9dafad21afd45c962799773eb8`. Its local static
checks passed, the exact archive steps succeeded on the clean historical source,
a dirty checkout was rejected, and a real upstream attestation consumer sequence
returned 0/1/0 for original/modified/original bytes. The guide retains its initial
lint and scratch-directory failures. These are local packaging and upstream
consumer checks, not this repository's hosted issuance.

## Integrated local verification

After reconciliation and the publication contribution, all commands returned 0:

- `python3 scripts/validate.py`: 68 components, 1,012 hashed files, 4 profiles,
  100 receipts; integrity/scope only.
- `python3 scripts/validate_catalogs.py`: catalog structure/evidence classes passed.
- `python3 scripts/validate_foundation.py --root . --json`: `ok: true`, no errors.
- `python3 scripts/validate_convergence.py --all-recorded --root . --json`:
  all 13 declared records valid; no native executions repeated.
- `python3 scripts/build_ecosystem.py --check`: exact generated output matched.
- `python3 -m unittest tests.test_validate tests.test_workflow_security tests.test_ecosystem_manifest`:
  `Ran 77 tests in 1.877s`, `OK`; local integration/negative/structural tests.
- Actionlint 1.7.12 across all seven workflows: empty stdout/stderr.
- Strict offline zizmor 1.30.1 across all seven workflows: `[]`.
- `git diff --check origin/main`: empty output. An earlier comparison to the old
  branch parent exposed whitespace in incoming raw recovery logs; those historical
  returned bytes were preserved, and the automation diff itself is clean.

Final source links and hosted results are recorded in the existing
[PR #26](https://github.com/seathatflowsinourveins/native-agent-stack/pull/26).
Future hosted results must identify their tested SHA and event. They do not turn
these local checks into upstream whole-stack or native runtime qualification.
