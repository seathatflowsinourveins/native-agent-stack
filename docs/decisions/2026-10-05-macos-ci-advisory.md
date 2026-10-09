# Decision: make macOS CI advisory (2026-10-05)

**Status:** the user chose the advisory option at **2026-10-05T01:41:33Z**.
The coordinator then changed live ruleset 23739774 at **2026-10-05T01:42:03Z**,
30 seconds later. [PR #711](https://github.com/seathatflowsinourveins/native-agent-stack/pull/711)
followed with the workflow implementation by bounded builder job-064 and the
coordinator's registry update.

At 01:41:33Z, the user answered the AskUserQuestion
**"How should macOS be handled, now that the Mac is portable or remote-control only?"**
by choosing the option labelled **"Advisory only (Recommended)"**.
"(Recommended)" is the asking agent's label for the option, not the user's
words. No pull request may wait on macOS.

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
nightly and main-push coverage follows after merge.

The committed `.github/main-ruleset.json` matches the coordinator's seven
required contexts: `validate`, `token-report`, `secret-scan`,
`dependency-review`, `osv-scanner`, `verdict-review-gate` and `sota-sources`.
A coordinator read-back of [ruleset 23739774](https://github.com/seathatflowsinourveins/native-agent-stack/rules/23739774)
at **02:52Z** confirmed those seven contexts, **strict false** and
**enforcement active**, following the 01:42:03Z change. The automation
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
That record gains a dated forward pointer; its measurements and
`evidence/artifacts/macos-ci-scope-20261003/` are retained. Their queue times,
suite durations, classifications, replay results and stated
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

[PR #711](https://github.com/seathatflowsinourveins/native-agent-stack/pull/711)
reports **builder-run results**: the original workflow produced **133 failing
subtests** in the PR-event control (exit 1), and the new workflow passed that
control (exit 0). The 133 count was measured with the first round's helper
(b4f76da95 in this PR), which ran each event combination as its own subtest.
The repaired helper stops at a job's first failing combination, so the same
control now shows at most one failing subtest per job. The repair round's
builder re-ran the strengthened control from red to green. The builder's selected modules reported **388 tests OK,
36 skipped**. These are local integration and synthetic checks using the
existing unittest tests and expression oracle.

PR #711's adoption-bootstrap CI on its final head reports `validate-macos`,
`bootstrap-macos` and `bootstrap-macos-brew` as skipped on the PR, and its
`validate` run is the hosted execution record. The 133 and 388 counts above
are the builder-run results reported in the PR.

The builder-run acceptance results for the submitted change were:

| Command | Exit | Result |
| --- | --- | --- |
| Original workflow PR-event control | 1 | 133 failing subtests |
| `python3 -m unittest tests.test_workflow_hardening` | 0 | 118 tests, 2 skipped |
| `python3 -m unittest tests.test_adoption_bootstrap_macos` | 0 | 162 tests, 33 skipped |
| `python3 -m unittest tests.test_github_automation_practice tests.test_codex_broker_reaper tests.test_shell_parser_ci` | 0 | 105 tests, 1 skipped |
| `python3 -m unittest tests.test_merge_guard_doc` with the stale count (control) | 1 | 3 tests, 1 failure |
| `python3 -m unittest tests.test_merge_guard_doc` with the corrected count (final) | 0 | 3 tests |
| `git diff --check` | 0 | No whitespace errors |

`command -v actionlint` returned exit 1, so the optional actionlint run is
unavailable on this job's PATH. Optional PyYAML parser checks were skipped
because that dependency is unavailable; the event-policy controls use the
existing dependency-free workflow parser. The selected unittest modules total
388 tests with 36 skips. `python3 scripts/validate.py` returned exit 1 with
only registry drift: SHA-256 and byte-count mismatches for changed registered
files. The coordinator registers the changes; job-064
does not edit `manifests/evidence.json`.

The completeness check covers all three adoption macOS jobs, PR exclusion, reachable
main-push/nightly/dispatch runs, cancellation, the Linux detector, required
contexts, the dated catalog snapshot and both maintained macOS guides. It
also caught the merge guard's stale eight-context count and old required-check
comments in the broker-reaper and shell-parser tests; these now describe
advisory coverage. `hardware-profile-smoke.yml:macos-profile` already sits
outside the required contexts, and the merge guard reads only
`gh pr checks --required`, so its existing PR smoke is advisory. That workflow
has a separate owner and is unchanged. The
remaining observation is the first hosted nightly or main-push run after merge. Future reviews
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

## Addendum: daily-only macOS CI (2026-10-09)

The owner selected daily-only macOS CI on 2026-10-09, relayed by the command
center at approximately 04:51 UTC. This supersedes the after-merge macOS
execution described above. `validate-macos`, `bootstrap-macos` and
`bootstrap-macos-brew` now run only on the existing daily **06:47 UTC**
schedule or manual dispatch, using:

```yaml
if: ${{ !cancelled() && (github.event_name == 'schedule' || github.event_name == 'workflow_dispatch') }}
```

`hardware-profile-smoke.yml:macos-profile` runs only on manual dispatch.
Pull requests continue without macOS jobs; the Linux jobs and required-check
policy retain their behavior. A daily macOS failure is still fixed forward
under the existing seven-day overturn condition, then checked by the next
scheduled or manually dispatched macOS run.

The reason is the October 2026 metered-usage screenshot supplied by the owner
and relayed with this decision (evidence class: `source_review`):

| October day | Metered minutes |
| --- | ---: |
| 1 | 5,377 |
| 2 | 3,599 |
| 3 | 6,699 |
| 4 | 4,712 |
| 5 | 4,640 |
| 6 | 684 |
| 7 | 1,204 |
| 8 | 2,182 |

The screenshot reports **$0 billed**. Removing repeated merge and PR macOS
runs is expected to reduce macOS minutes by about **80–90%**; this estimate
has no measured post-change result yet. The reported daily totals motivate
the cadence change and do not establish that estimate.

The implementation follows the documented GitHub Actions job conditions,
status functions and schedule at
[`github/docs@9f651797567230e844373870fce8b14427ad47ad`](https://github.com/github/docs/tree/9f651797567230e844373870fce8b14427ad47ad),
read on 2026-10-09: the job-condition reusable, `expressions.md` status-check
functions, and the schedule-event references named in **SOTA sources** above.
The existing expression oracle checks the four event types and cancellation
locally; scheduled execution on the default branch remains hosted evidence
to observe after landing.

### MLX lock coverage retained on Linux PRs (2026-10-09 fix)

At the implementation base
[`b7dfe638`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/b7dfe638fc825a52ff4e7d1a9ccf2fde7de889fd/.github/workflows/hardware-profile-smoke.yml#L94-L102),
the macOS job checked lock consistency by compiling `tools/mlx-smoke/requirements.in`
with **uv 0.12.17**, targeting `aarch64-apple-darwin` and Python 3.12 with
hashes, a 2026-09-23 cutoff and `MACOSX_DEPLOYMENT_TARGET=14.0`, then comparing
the result with the committed `requirements.lock.txt`. The separate
[lines 103–118](https://github.com/seathatflowsinourveins/native-agent-stack/blob/b7dfe638fc825a52ff4e7d1a9ccf2fde7de889fd/.github/workflows/hardware-profile-smoke.yml#L103-L118)
create a venv, install the wheels and run MLX generation.

The resolve-and-diff check is retained in `linux-profile` on pull requests and
manual dispatch, using the vendor's same cross-platform command and pinned
Linux distribution. The existing Linux profile and script tests remain; the
job also runs `MlxLockLinuxTests` against its native uv executable. That test
executes the workflow's actual resolve-and-diff script against both the
committed lock and a deliberately stale dependency pin. Other unit-test jobs
without the supplied uv binary skip this integration case; the Linux MLX job
supplies it explicitly and runs the regression. Native MLX wheel installation
and inference remain manual macOS checks, so PRs lose that runtime coverage.

The primary reference is [uv's `--python-platform` CLI
documentation](https://docs.astral.sh/uv/reference/cli/#uv-pip-compile--python-platform)
and [`--python-version`](https://docs.astral.sh/uv/reference/cli/#uv-pip-compile--python-version),
verified against **astral-sh/uv 0.12.17 at
[`635500036e1705961315e86447f0fab0a8ddb309`](https://github.com/astral-sh/uv/tree/635500036e1705961315e86447f0fab0a8ddb309)**,
`crates/uv-cli/src/lib.rs` and `crates/uv/src/commands/pip/compile.rs`.
On Linux, that vendor binary reproduced the committed lock exactly
(SHA-256 `71b920ceab903cf59e6387651f79dd9c9ac70880065508689eac664a8d27e6a4`;
resolve 0, diff 0). Replacing a dependency pin in a scratch lock left the
generated lock unchanged and made the same diff return 1. An explicit Linux
Python 3.13 interpreter with Python 3.12 resolution also returned resolve 0,
diff 0 without Python downloads. These are `local_integration` results for
this requirements set. Hosted Linux PR execution at the fix head remains to
be observed; the daily **06:47 UTC** adoption jobs retain general macOS
portability coverage and manual hardware dispatch retains the MLX runtime check.
