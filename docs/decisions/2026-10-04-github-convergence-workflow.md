# GitHub convergence workflow: landing, check gates and description edits (2026-10-04)

Lane: foundation. North-star action served: every unit that moves the stack toward the north star lands on a
`main` whose required checks judged it together with the units landed before it, so research and paper-lane
evidence stays reproducible from `main`. Status: proposed. Cross-family consensus was reached on 2026-10-04 (Claude Opus synthesis, GPT-6.1 Sol review, Opus reconcile). The record becomes accepted when the command center ACKs this PR and it lands. Slot 1 awaits the owner's decision U1. The record was reconciled on 2026-10-04 after an
independent cross-family review (GPT-6.1 Sol), which disagreed on slot 2 and refined slots 3, 4, 5 and 9. Each
point was settled on the sources below. The other slots are bounded pull requests. This record changes no workflow, ruleset or setting by
itself.

## Decision

| Slot | Choice |
| --- | --- |
| 1. Landing and integration testing | Target: GitHub's native merge queue, started serial (squash, all-green groups, one build at a time). It needs an organization-owned public repository, and this one is User-owned, so it waits on U1. U1's recommended path qualifies the queue on a disposable fixture before the transfer. Until cutover, the coordinator's serial landing queue (kept outside the repository, unversioned) stays the owner, under slot 2's strict mode. No hosted queue, no bors, no Prow/Tide. |
| 2. Merge skew until slot 1 is settled | Strict up-to-date checks go on now, whatever U1 decides. First, every lander handles a `BEHIND` merge state: the landing queue sends it to its refresh step instead of handing the PR back, and any other session updates the branch and waits for the required checks, or hands the PR to the queue. Then the ruleset sets `strict_required_status_checks_policy: true`. The merge-queue cutover (G-10) decides the flag when the queue goes live. |
| 3. Description edits and `validate` | `sota-sources` and `verdict-review-gate` move, job IDs unchanged, into a PR-metadata workflow on `edited`, `push` to `main` and `workflow_dispatch`. It has a per-PR concurrency group with `queue: max` and no `cancel-in-progress`. `sota-sources` reads the current PR body through the REST API with the pinned `actions/github-script` and fails on a retrieval error. `verdict-review-gate` keeps its merge-parent and head checks, and fails closed when the current base differs from the event's. `validate.yml` drops `edited`. |
| 4. Coordinator ACK and cross-family verdict | Both stay in the landing queue as the merge gate (the enqueue gate after slot 1). They bind to the exact head through `expectedHeadOid`, which GitHub checks when the merge or enqueue request arrives. Before cutover, both enqueue paths are qualified: `gh pr merge --match-head-commit`, which sends `enablePullRequestAutoMerge` on a queue branch, and `enqueuePullRequest` with `expectedHeadOid`. No reviewer GitHub App and no new required status. |
| 5. Failing checks outside the required set | `native-token-tools` becomes required once its fix (#698) has merged and a run on `main` passes. Its path filter moves into a detector job with the fail-closed rules `validate-macos` uses. A test classifies every `pull_request` job as required or advisory. Socket Security and the betterleaks trial stay advisory. |
| 6. Squash message | The repository default becomes the PR title and description (`squash_merge_commit_title: PR_TITLE`, `squash_merge_commit_message: PR_BODY`), for every merge path including a queue. |
| 7. Auto-merge | Stays off, and the queue path does not turn it on. The current-practice line that calls it allowed is corrected. |
| 8. `github-practice` open work | "Require complete current-head coverage before landing the catalog metadata fix" closes as satisfied. The gh 2.102.0 item and the hosted-proposal item stay open. |
| 9. Actions quality | Hash-lock all five native replay wheels with `--require-hashes` (trading lane), with the requirements file inside the replay's trigger paths. Publish the Linux suite's ran and skipped counts in the job summary. The hardware-profile owner adds Harden-Runner to `macos-profile`. Not adopted: a wheel cache, the attestation wrapper, an XML test reporter, a quarantine or rerun plugin, a bypass-review workflow. |

User decision U1 (owner only): create a free organization, qualify the merge queue on a disposable public
fixture repository there, then transfer this repository into it (option b). Recommended. It costs no money,
because GitHub Free for organizations covers public repositories. The transfer is the one step that a ruleset
update does not undo.

## Evidence

Read on 2026-10-04 with read-only GraphQL and REST GETs, recorded runs and PR timelines, source at `main`
`3b8f9c8a` and current official documentation. Each item is labelled documented, observed or estimated.

- **Merge skew broke `main` (observed).** #651 (`75780ee5`) and #628 (`ecea2865`) merged 13 seconds apart on
  2026-10-03 (16:11:24Z and 16:11:37Z). The push run of `validate` on `ecea2865` (37135948481) failed after 71 s
  (16:11:43Z to 16:12:54Z), too soon for the test suite, and the run on `75780ee5` (37135935578) passed. `files[]`
  in `manifests/evidence.json` is unsorted at `ecea2865` and sorted at `75780ee5`, while both PR heads (`21497f9e`, `dce7bfb9`) are sorted. The cross-family review's read of job 111240392112 quotes `files[] must be sorted by path`, and the
  lander's condition 5 comment names the same cause. That meets the overturn the 2026-09-22 record set for strict mode
  ("a `main` failure traced to two PRs merging close together").
- **The interim control is structural and partial (observed).** The landing scripts kept outside the repository
  land a green PR "without a refresh" when its three-way merge onto current `main` is clean
  (`land_no_refresh.sh:122`). They refresh only when that check fails (`land_queue.sh:100-105`). Since 2026-10-03
  they also require the merged registry to stay sorted (condition 5, `land_no_refresh.sh:105-112`). The required
  suite never runs on the merged tree. A window separates the main-moved re-check (`:127-128`) from the merge
  (`:133`), and `--match-head-commit` binds the head, not the base (`docs/lanes.md:192-202`). Two session
  identities land through these scripts (`land_no_refresh.sh:120-122`), the command center owns merges that touch
  the hot registry, and `docs/lanes.md:193` states that concurrent sessions share `main`. Only strict mode or a
  merge queue tests every lander's PR against current `main`.
- **The other `main` failures were not skew (observed).** `main` took 100 commits from 2026-10-01T10:44:35Z to
  2026-10-04T22:08:01Z: 19, 21, 24 and 36 per UTC day, with the first and last days partial. Four push runs of
  `validate` failed. One was `ecea2865` (skew). The other three, on `0eb47187`, `1f5a791b` and `19249810` (runs
  37067723514, 37147299685 and 37168905683), failed only
  `tests.test_secret_path_guard.K4GuardTests.test_k4_timing`, a timing test that strict mode does not prevent.
- **Strict-mode cost (estimated, not measured under strict).** Each landing after the first in a burst needs one
  refresh and one CI cycle. Those three push runs of `validate` took 20m48s, 20m54s and 20m36s.
  `validate.yml:32-33` records 1727-1745 s for earlier runs, and the closure record gives `validate-macos` a
  10.9-minute median (line 1564). At 21-29 minutes a cycle, serial capacity is about 50-69 landings a day,
  against 19-36 observed. The 2026-09-22 record priced strict mode with auto-merge on and a manual branch update;
  auto-merge is now off, and the landing queue can refresh mechanically. Each refresh re-runs the flaky timing
  test, which raises the cost.
- **A description edit cancels `validate` (observed).** On #667, edits at 20:00:04Z and 20:00:12Z started
  `validate` runs 37230401501 and 37230410488 on the unchanged head `6c2fc2fa`. The runs they replaced
  (37230356948, then 37230401501) ended cancelled. `validate.yml` subscribes to `edited` and cancels in-progress
  `pull_request` runs in one group per PR. No other workflow subscribes to `edited`.
- **Queue order is not a freshness guarantee (documented).** In a concurrency group, runs are processed FIFO
  "according to the time each one started waiting on the concurrency group", and "ordering is not guaranteed".
  With `queue: max`, at most 100 runs wait before "any additional jobs or workflow runs are canceled". The gates
  read the event payload today (`validate.yml:280-282`, `:613`), so serialization alone cannot show that the
  checked description is current. Reading the PR at run time can.
- **`validate` gains nothing from edited runs (recorded 2026-09-23, not re-measured).** After a retarget, the
  edited run still checks out the merge commit built on the old base (`docs/github-automation.md:1355-1369`). Only
  `sota-sources` (the description) and `verdict-review-gate` (the base) need the event. Skipping `validate` on
  edited runs instead would hide a failure, because a job skipped by a condition reports success.
- **Live settings (observed).** Owner type `User`; `autoMergeAllowed` false; squash only; squash defaults
  `COMMIT_OR_PR_TITLE` and `COMMIT_MESSAGES`. Ruleset 23739774 equals `.github/main-ruleset.json`: eight checks
  from app 15368, strict off, no bypass actors. `docs/github-automation.md:31` still says auto-merge is allowed.
- **Enqueue path (documented).** At gh v2.101.0, `gh pr merge` sets auto on a queue branch (`merge.go:298-304`)
  and sends `enablePullRequestAutoMerge` with `expectedHeadOid` (`http.go:77-92`). The live GraphQL schema has
  `enqueuePullRequest(pullRequestId, jump, expectedHeadOid)`. GitHub lists four reasons for removal from a queue:
  CI failure, timeout, manual removal and an unresolved branch-protection failure. A head change is not among them.
- **A failing check landed (observed).** #693 landed as `14048b84` with `native-token-tools` failing on
  `rtk-exactness-controls-diff-and-grep-unchanged` (`scripts/native_token_ci.py:1540-1544`). The rtk 0.51.0 pin
  changed an exact output, and the check was not required. Its fix, #698, is open, with `native-token-tools`
  passing at `92512f05`. The latest push run of the check on `main` failed.
- **#611 had full coverage (observed).** It merged as `5803017` at 2026-10-02T20:15:13Z. At its head `05a2c67f`,
  22 check contexts passed and 3 were skipped. The open-work line asking for that coverage came in with #612
  (`21521f19`, 22:24:31Z), after the merge.
- **Availability, cost and transfer (documented).** GitHub documents merge queues for public repositories owned by
  an organization, and GitHub Free for organizations covers public repositories. A transfer redirects web and git
  access but not Pages. The redirects are deleted if anything is created at the old location. GitHub permanently
  retires the old owner/name when the repository had more than 100 clones or more than 100 uses of GitHub Actions
  in the week before the transfer.
- **Tests (observed).** `tests/test_sota_sources_gate.py:223` asserts the scaffold caller's `edited` trigger, not
  `validate.yml`'s. `validate.yml`'s is asserted at `tests/test_workflow_hardening.py:564-569`, and
  `TargetRulesetTests` asserts strict off at `:500`.

## Alternatives

- Slot 1: hosted queues (Mergify, Trunk, Aviator, Graphite) are separate hosted services that the self-hosted gate
  excludes; Mergify's setup starts by installing its GitHub App. rust-lang/bors and kubernetes-sigs/prow (Tide) have
  no releases or tags, and each is a service to deploy; bors-ng is archived. A reviewer GitHub App that issues the
  verdict as a required check answers a threat this single-account repository does not concretely face, and
  creating an App is the owner's call.
- Slot 2: keeping strict off until U1, with a second-failure tripwire, was this record's first draft. It leaves the
  general skew class to a structural check that only some landers run, after the recorded overturn has occurred.
  A self-built "tested against current main" check in the lander would copy strict mode without platform
  enforcement.
- Slot 3: a conditional `cancel-in-progress` still runs the full suite on every edit. Skipping `validate` on edited
  runs hides failures. Dropping `edited` everywhere loses the description check and the retarget fail-closed.
  Relying on queue order with payload reads is refuted by the ordering note above. A `gh api` step reading the body
  would pass the description through a shell, which the job avoids (`validate.yml:598-600`).
- Slot 4: `enqueuePullRequest` and `gh pr merge` are both qualified, not chosen in advance. If a head ever lands
  without the ACK, the remedy is a required commit status on the exact head, not an App.
- Slot 5: the landing queue's blanket rule alone covers one merge path and blocks on advisory checks. A required
  check behind a workflow path filter stays pending on other PRs. upsidr/merge-gatekeeper's last release is from
  2023-02-03, and re-actors/alls-green aggregates only within one workflow.
- Slot 9: actions/attest-build-provenance would duplicate the existing actions/attest step. No measured
  wheel-download bottleneck justifies a cache. github/safe-settings would need an App deployment.
- U1: (a) transfer first, then stage the queue; (c) stay personal, with strict mode as the permanent control; (d) a
  hosted queue, which the self-hosted gate excludes.

## Overturn

- Slot 1: GitHub opens merge queues to personal repositories (then enable in place). Or the serial trial fails an
  acceptance case: a push to a queued PR merges an unacknowledged head, a required context never reports on merge
  groups, the CodeQL rule blocks merge groups, or registry failures remove more PRs than the landing queue hands
  back. Then remove the `merge_queue` rule (one ruleset update) and land through the landing queue again.
- Slot 2: strict mode goes off only through the queue cutover, or if the landing-queue logs show more PRs queued
  than landed on each of 7 consecutive days with strict on (a growing backlog, counted by the queue owner). The
  user then chooses between U1 and loose mode with the landing check.
- Slot 3: a native trace in which a description edit still cancels `validate` or a required context, or in which
  the merge state does not follow the current description after rapid edits. If GitHub adds filters on what an
  `edited` event changed, fold the jobs back into one workflow.
- Slot 4: a head lands without the coordinator ACK or the cross-family verdict, through any merge path. The ACK
  then becomes a required commit status on the exact head.
- Slot 5: the converted check reports pending on a PR outside its paths, or fails without a defect in more than 10%
  of a rolling 20-run window (the closure record's `validate-macos` rule). It then returns to advisory.
- Slot 6: a merge path ignores the default.
- Slot 7: the merge queue is live and enqueuing before checks are green is wanted.
- Slot 8: a later read shows a context at #611's head that was neither success nor skipped.
- Slot 9: the wheel lock lets an installed wheel through without a predeclared hash, or a change to the
  requirements file does not trigger the replay. The other two items are overturned by the measurement named in
  their pull requests.

## Evidence class

Documented: GitHub documentation read on 2026-10-04 (the concurrency text at github/docs `336b7f546d94`), gh
v2.101.0 source, pip 26.2.1 documentation, and the Harden-Runner README at its pin. Observed: read-only GraphQL and
REST reads on 2026-10-04 (repository settings, `main` history and check rollups, PR metadata, schema
introspection) and the logs of runs 37067723514, 37147299685 and 37168905683. Estimated: strict-mode throughput. Not verified:

- which of several same-name runs the ruleset evaluates;
- how the strict flag interacts with a required merge queue;
- whether `enablePullRequestAutoMerge` enqueues with auto-merge off;
- what a push after enqueue does;
- how the CodeQL rule treats merge-group commits;
- whether this repository meets the retirement threshold, and whether a transfer back can reuse a retired name.

Nothing was installed or changed. Every proposed workflow change still needs native acceptance.

## SOTA sources

- Merge queue: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue
  and https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/merging-a-pull-request-with-a-merge-queue
- Strict and loose required checks: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
  and https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- Ruleset `merge_queue` rule: https://docs.github.com/en/rest/repos/rules
- Required checks, skipped jobs and path filters: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks
- Concurrency and `queue: max`: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
  and https://github.com/github/docs/blob/336b7f546d94/data/reusables/actions/actions-group-concurrency.md
- Events (`pull_request` activity types, `merge_group`): https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Current PR metadata: https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request, read through
  https://github.com/actions/github-script at `3a2844b7e9c422d3c10d287c895573f7108da1b3` (v9.0.0)
- Enqueue mutation: GitHub GraphQL schema (introspection of `EnqueuePullRequestInput`, 2026-10-04), reference at
  https://docs.github.com/en/graphql/reference/mutations#enqueuepullrequest
- gh `expectedHeadOid` and the queue path: https://github.com/cli/cli/blob/v2.101.0/pkg/cmd/pr/merge/merge.go
  and https://github.com/cli/cli/blob/v2.101.0/pkg/cmd/pr/merge/http.go
- Squash defaults: https://docs.github.com/en/rest/repos/repos#update-a-repository
- Transfer and plans: https://docs.github.com/en/repositories/creating-and-managing-repositories/transferring-a-repository
  and https://docs.github.com/en/get-started/learning-about-github/githubs-plans
- Dependency review in merge groups: https://github.com/actions/dependency-review-action/blob/a1d282b36b6f3519aa1f3fc636f609c47dddb294/action.yml
- pip hash-checking mode: https://github.com/pypa/pip/blob/26.2.1/docs/html/topics/secure-installs.md
- Harden-Runner macOS audit mode: https://github.com/step-security/harden-runner/blob/e14015d583714f6e62063499dc959a02595150a1/README.md
- In-repository records: `docs/decisions/2026-09-22-github-automation-closure.md`,
  `docs/decisions/2026-10-02-github-automation-practice.md`, `docs/github-automation.md`, `docs/lanes.md`.
