# Decision: make macOS CI advisory (2026-10-05)

**Status:** approved by the user at approximately 01:50 UTC on 2026-10-05;
implemented by bounded builder job-064. The coordinator already removed
`validate-macos` from live ruleset 23739774. Evidence registry updates remain
with the coordinator.

Asked how macOS should be handled now that the Mac is portable or remote-control
only, the user answered: **"Advisory only (Recommended)"**. No pull request may
wait on macOS.

**North-star action served:** keep foundation changes available for US-equities
research and historical simulation while retaining macOS portability checks
after merge.

## Behavior

In `.github/workflows/adoption-bootstrap.yml`, `validate-macos`,
`bootstrap-macos` and `bootstrap-macos-brew` use the same job condition:

```yaml
if: ${{ !cancelled() && github.event_name != 'pull_request' }}
```

Every pull request skips all three jobs, including a PR whose `changes` job
fails or classifies a Mac-relevant path. Main pushes still use the existing
workflow paths filter. The weekly bootstrap schedule becomes daily at
**06:47 UTC** (`47 6 * * *`), away from :00 and :30. Manual dispatch remains
available. All eligible macOS runs execute the full validation and bootstrap
work they previously performed off pull requests.

The workflow still accepts pull requests for the `changes` job and path-gated
`bootstrap-linux`. Its bootstrap patterns and fail-safe output remain intact.
The historical macOS classifier and guarded changed-tests step are retained
for the earlier measurements and controls; they do not enable PR execution.
Linux's scheduled pinned-download smoke now runs daily too.

GitHub's [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idif)
defines job conditions. Keeping `!cancelled()` replaces the implicit
`success()` check on `needs: changes`, so a skipped detector does not prevent
push, schedule or dispatch runs. GitHub's [schedule event](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
runs the latest default-branch commit; the workflow must exist on that branch.
Scheduled runs can be delayed or dropped under load, especially at the start
of an hour. Registration of this schedule is structural evidence; hosted
execution of the new policy follows after merge.

The committed `.github/main-ruleset.json` matches the coordinator's seven
required contexts: `validate`, `token-report`, `secret-scan`,
`dependency-review`, `osv-scanner`, `verdict-review-gate` and `sota-sources`.
A read-only GET of [ruleset 23739774](https://github.com/seathatflowsinourveins/native-agent-stack/rules/23739774)
confirmed those contexts, strict up-to-date checks off and squash-only merges;
its returned update timestamp was 2026-10-05T01:42:03.690Z. The automation
catalog gains `current_practice_20261005` and keeps its earlier dated snapshot.
The merge guard's documented required-context count in `docs/lanes.md` changes
from eight to seven; its existing count check fails before this correction and
passes afterward. This count-only edit follows that file's `lane:shared`
integration policy.

## Supersession and evidence

This decision supersedes the **required** macOS check and its PR execution
policy, including the two bootstrap jobs' PR gating, in
[`2026-10-03-macos-ci-scope.md`](2026-10-03-macos-ci-scope.md), implemented by
[#677](https://github.com/seathatflowsinourveins/native-agent-stack/pull/677).
That record and `evidence/artifacts/macos-ci-scope-20261003/` remain unchanged.
Their queue times, suite durations, classifications, replay results and stated
measurement limits remain historical evidence. This also replaces the older
required-check policy cited from the 2026-09-25 automation closure.

[#699](https://github.com/seathatflowsinourveins/native-agent-stack/pull/699)
provided a real portability catch, at the cost of a full PR round:
`test_a_settings_file_names_its_own_home` in
`tests/test_apply_claude_settings.py` hard-coded `/home/example`, while macOS
resolves `/home` to `/System/Volumes/Data/home`. The
repair in #699 (landed on main as [5df0e0ede](https://github.com/seathatflowsinourveins/native-agent-stack/commit/5df0e0ede); `tests/test_apply_claude_settings.py:439`)
compares the expected home with the resolved settings path; the runtime code
stayed unchanged. The catch supports retaining macOS runs. The Mac's current
portable or remote-control role removes the reason to delay every PR for them.

## Fix forward and overturn

A failing nightly or main-push macOS run is diagnosed and fixed in a
**follow-up PR**. The failing run retains its failure status and logs. The
follow-up PR uses the seven required checks and can merge without a macOS run;
its next eligible main-push or nightly run verifies the Mac repair.

Revisit this decision if either condition occurs:

- The Mac becomes a host again.
- A nightly macOS failure remains unfixed for **more than 7 days**.

Alternatives considered are keeping #677's required, scoped PR check or
retiring macOS CI. Advisory coverage follows the user's answer and preserves
the demonstrated portability benefit. The two overturn conditions define
when to compare those alternatives again.

## Acceptance and completeness

The new PR-event test failed against the original workflow with one failure
for each macOS job (exit 1), then passed after the job conditions changed
(exit 0). With the final test's complete input matrix, restoring the original
workflow from base `2875145812ebea1bb299ac15d1106261c679cca0` produced
133 failing subtests (one test, exit 1). Restoring the new workflow byte for
byte made that same final test pass (exit 0). The resumed job repeated this
comparison with the original workflow supplied to the existing unittest test
through a fixture override, preserving the working-tree workflow throughout;
it again produced 133 failing subtests (exit 1), followed by a pass of the
new workflow (exit 0). Separate controls rejected the original weekly cron and committed
`validate-macos` requirement, then passed with the daily cron and seven
contexts. A retained control evaluates the previous workflow's actual job
condition against the advisory policy. These are local integration and
synthetic checks using the existing unittest tests and expression oracle.

The final local commands passed:

| Command | Exit | Result |
| --- | --- | --- |
| `python3 -m unittest tests.test_workflow_hardening` | 0 | 118 tests, 2 skipped |
| `python3 -m unittest tests.test_adoption_bootstrap_macos` | 0 | 162 tests, 33 skipped |
| `python3 -m unittest tests.test_github_automation_practice tests.test_codex_broker_reaper tests.test_shell_parser_ci` | 0 | 105 tests, 1 skipped |
| `python3 -m unittest tests.test_merge_guard_doc` | 0 | 3 tests; stale count control failed with 1 failure, exit 1 |
| `git diff --check` | 0 | No whitespace errors |

`command -v actionlint` returned exit 1, so the optional actionlint run is
unavailable on this job's PATH. Optional PyYAML parser checks were skipped
because that dependency is unavailable; the event-policy controls use the
existing dependency-free workflow parser. The selected unittest modules total
388 tests with 36 skips. `python3 scripts/validate.py` returned exit 1 with
only registry drift: SHA-256 and byte-count mismatches for changed registered
files. The coordinator registers the changes; job-064
does not edit `manifests/evidence.json`.

Intermediate full-module failures are retained with the final result: an
initial 16 failures came from applying the new execution-policy oracle to
the historical selector; keeping its classification oracle fixed those.
Two remaining assertions described the old summaries and were updated to
assert advisory PR skips. The final 118-test run passed. Handoff reports in
`.bounded-job-064/` retain the returned outputs with the worktree path
sanitized as `<job-worktree>`.
The first publication check flagged unsanitized worktree paths in five of
those reports. Sanitizing the reports removed those findings; the subsequent
check contained only the 14 expected registry mismatches.

The completeness check covers all three adoption macOS jobs, PR exclusion, reachable
main-push/nightly/dispatch runs, cancellation, the Linux detector, required
contexts, the dated catalog snapshot and both maintained macOS guides. It
also caught the merge guard's stale eight-context count and old required-check
comments in the broker-reaper and shell-parser tests; these now describe
advisory coverage. `hardware-profile-smoke.yml:macos-profile` already sits
outside the required contexts, and the merge guard reads only
`gh pr checks --required`, so its existing PR smoke is advisory. That workflow
has a separate owner and is unchanged. The
remaining observation is the first hosted run after merge. Future reviews
track the age of nightly failures against the seven-day overturn condition.

## SOTA sources

The selected upstream implementation is GitHub Actions' documented job
condition and schedule, read from **github/docs at
2bd66de8cea336061c9ea060c9b37385136e6ab3**, the main revision returned by
`gh api repos/github/docs/commits/main` for this job:

- `content/actions/reference/workflows-and-actions/workflow-syntax.md` and
  `data/reusables/actions/jobs/section-using-conditions-to-control-job-execution.md`.
- `content/actions/reference/workflows-and-actions/events-that-trigger-workflows.md`,
  `data/reusables/actions/schedule-delay.md`,
  `data/reusables/actions/branch-requirement.md` and
  `data/reusables/repositories/actions-scheduled-workflow-example.md`.
- `content/actions/reference/workflows-and-actions/expressions.md`, status
  check functions and the default `success()` behavior.

Repository evidence: the original job-064 base
`2875145812ebea1bb299ac15d1106261c679cca0`, #677's retained decision and
measurements, #699's original repair diff, and the read-only ruleset GET.
The existing expression oracle retains its citations to the GitHub runner
operator sources. The search-first and tdd skills guided source selection
and the red-then-green controls; they are process guidance, not hosted
execution evidence.
