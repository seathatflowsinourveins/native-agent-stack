# GitHub CI final-state observation — 2026-10-05

## Outcome and scope

The captured main commit `4c897418fe35a030a1188ae447eaf31c893f8eff` has successful latest push workflows. Its effective rules require seven status contexts and a separate CodeQL code-scanning rule. Several owner PRs remain blocked or pending; this record does not certify them for merge.

The pre-publication follow-up records #714 merged at 04:32:03Z as `f946c6d4ca988a17b6fa4392ecb488909f147883`. This worktree includes that release-prep commit; its four changed paths contain no workflow or ruleset change. Its 23 checks were 16 successful, two skipped and five in progress at the later GET, so the earlier green state is not a claim that the newer head has finished. Both native observations remain in `current-state.json`.

North-star action: give foundation and US-equities research sessions a recoverable CI gate, failure and ownership record before continuing research and historical simulation. This lane changes evidence and documentation only. Settings, workflow code and owner PRs remain with their owners.

The [receipt](../../evidence/receipts/github-ci-finalize-20261005.json) and [returned-output archive](../../evidence/artifacts/github-ci-finalize-20261005/README.md) supersede summary-only measurement for this window. Existing October 3 measurements retain their original scope and limitations. The co-op's host/client/acceptance records and ten task-filtered defects supplied no replacement GitHub census; no host/model acceptance was repeated.

## Current gate and pending shape

The effective ruleset GET records these contexts, each bound to GitHub Actions integration **15368**:

- `validate`, `token-report`, `secret-scan`, `dependency-review`, `osv-scanner`, `verdict-review-gate`, `sota-sources`.

`strict_required_status_checks_policy` is **false**. The same active rules require linear history, resolved review threads, squash pull requests, and CodeQL at high-or-higher security severity/errors. Classic branch-protection GET returned 404; effective branch rules returned active protection. The latter endpoint includes active inherited rules. [GitHub rules API](https://docs.github.com/en/rest/repos/rules?apiVersion=2022-11-28#get-rules-for-a-branch).

Latest main has 23 check runs: 21 success and two skipped. Its six latest workflows' job records have no failed job. `dependency-review` is PR-only; this main observation cannot establish all PR gates. Required checks on a test-merge commit can govern instead of checks on the head. [GitHub required-check semantics](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks).

| Shape or plan unit | Observed disposition | Owner |
| --- | --- | --- |
| Linux full-suite validation, 60-minute limit | On main; timeout stopgap #653 merged at `59f8a1e36e1f2870d9de18a16c42f1e72cdae1c6` | Validation maintainer |
| unittest-parallel trial | #646 closed unmerged; failed-trial records #652 merged | Retain rejection; no new trial |
| Scoped macOS suite | #677 merged at `e0c329ae98efb6ac5e11a49220b69ec6eddbb658` | Adoption maintainer |
| macOS required context | Already absent from live rules; committed rules, advisory push/nightly behavior and docs still being reconciled | [#711](https://github.com/seathatflowsinourveins/native-agent-stack/pull/711) |
| Strict up-to-date checks | Proposed, not active | [#708](https://github.com/seathatflowsinourveins/native-agent-stack/pull/708) |
| Separate PR metadata gates/current-body reads | Proposed; later snapshot has validate in progress | [#706](https://github.com/seathatflowsinourveins/native-agent-stack/pull/706) |
| SARIF action bump | Pending evidence registration and PR-description repairs | [#690](https://github.com/seathatflowsinourveins/native-agent-stack/pull/690) |

The approved-plan memory predates these changes. #632 coverage records also merged. Newer live rules and merged sources take precedence over its older macOS-full-suite and held-record statements. No private-repository billing or settings conclusion is made.

## Workflow census

Creation window: **2026-09-28 00:00:00Z through 2026-10-05 03:59:59Z**, seven days plus four hours. Conclusions were read during 04:09–04:26Z rather than at one atomic instant. Eleven contiguous second-resolution partitions retain **8,022 unique runs**; the largest contains 992. Native projected page totals reconcile with collected records. GitHub caps filtered run searches at 1,000; partitioning precedes pagination. [Workflow-runs API](https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28#list-workflow-runs-for-a-repository).

“Main” means `head_branch == main`: **1,430** records, comprising 1,174 push, 240 dynamic, ten schedule and six dispatch events. All 21 main failures and five main cancellations are push events. The remaining census includes 5,519 PR events; events are retained, rather than inferred from associated PR arrays.

| Workflow | All pass | All fail | All cancelled | Main pass | Main fail | Main cancelled |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Adoption bootstrap smoke | 787 | 79 | 371 | 218 | 9 | 0 |
| Catalog freshness (report-only) | 6 | 0 | 0 | 6 | 0 | 0 |
| CodeQL | 1299 | 0 | 0 | 233 | 0 | 0 |
| Dependabot Updates | 3 | 0 | 0 | 3 | 0 | 0 |
| Dependency and workflow security scan | 1102 | 98 | 44 | 228 | 5 | 0 |
| Dependency Graph | 4 | 0 | 0 | 4 | 0 | 0 |
| Dependency review | 963 | 3 | 45 | 0 | 0 | 0 |
| Hardware profile smoke | 3 | 0 | 0 | 0 | 0 | 0 |
| Native foundation offline engine E2E | 21 | 0 | 0 | 3 | 0 | 0 |
| Native owned guest service reboot | 0 | 0 | 0 | 0 | 0 | 0 |
| Native synthetic independent-host restore | 0 | 0 | 0 | 0 | 0 | 0 |
| Native synthetic off-host application-state recovery | 0 | 0 | 0 | 0 | 0 | 0 |
| Native token tools E2E | 96 | 7 | 5 | 14 | 1 | 0 |
| OpenSSF Scorecard (report-only) | 229 | 0 | 4 | 229 | 0 | 4 |
| PR metadata gates | 2 | 0 | 0 | 0 | 0 | 0 |
| Practice references freshness (report-only) | 2 | 0 | 0 | 2 | 0 | 0 |
| Publish attested catalog archive | 0 | 0 | 0 | 0 | 0 | 0 |
| Qualify selected Action toolchains | 4 | 0 | 0 | 1 | 0 | 0 |
| Receipt staleness report | 5 | 0 | 0 | 2 | 0 | 0 |
| Runtime-worker skills freshness (report-only) | 1 | 0 | 0 | 1 | 0 | 0 |
| Saturation tracking | 1 | 0 | 0 | 1 | 0 | 0 |
| SOTA sources gate | 0 | 0 | 0 | 0 | 0 | 0 |
| Suite parallelism trial (draft pull request only) | 0 | 0 | 1 | 0 | 0 | 0 |
| Supply-chain SBOM and vulnerability scan | 11 | 0 | 0 | 2 | 0 | 0 |
| Validate portable token report | 1200 | 0 | 43 | 232 | 0 | 0 |
| Validate published evidence | 951 | 104 | 517 | 225 | 6 | 1 |

Five additional outcomes are `action_required`: one each in Adoption, Security scan, Dependency review, Token report and Validate. Six runs were unfinished: four Adoption and two Validate. None is counted as success, failure or cancellation. No `timed_out` run conclusion appears in this census.

Names are canonical workflow-registry names; the original first run names remain in `counts.json` for the three dynamic workflows. The registry contains 26 entries, including three dynamic workflows and two branch-only workflow files absent from main: the parallelism trial and PR metadata workflow. Registration and zero window executions prove neither adoption nor acceptance.

Counts are latest run-level outcomes. **28 runs have `run_attempt > 1`**; prior attempts were not reconstructed, so these data do not establish first-attempt success or a complete flake rate.

## Durations

The metric is **completed-run elapsed seconds**, `updated_at - (run_started_at or created_at)`, following [cli/cli v2.102.0 source](https://github.com/cli/cli/blob/v2.102.0/pkg/cmd/run/shared/shared.go#L114). It includes scheduling/dependency intervals and is not CPU or billable time. All 8,016 completed records are retained in 58 separate workflow/cohort/conclusion groups, including five zero-second `action_required` intervals. The following sample describes successful runs only; the full [duration data](../../evidence/artifacts/github-ci-finalize-20261005/durations.json) also separates failures and cancellations.

| Workflow / cohort | N | Median seconds | P90 seconds | Maximum seconds |
| --- | ---: | ---: | ---: | ---: |
| Validate / PR | 726 | 1490.5 | 1876 | 2313 |
| Validate / main | 225 | 1373 | 1832 | 2068 |
| Adoption / PR | 569 | 2064 | 6716 | 22513 |
| Adoption / main | 218 | 2324.5 | 7821 | 21961 |
| Security scan / PR | 874 | 25 | 40 | 310 |
| Token report / PR | 968 | 29 | 43 | 496 |
| Dependency review / PR | 963 | 23 | 37 | 600 |

P90 uses nearest rank. The mixed window spans macOS scope changes; this is not a matched performance experiment or an adoption verdict.

## Historical main failures and cancellation causes

Native job records cover every non-success main run. Numbered log excerpts and four macOS artifact traces preserve the failure evidence. The table groups identical findings while keeping advisory failures apart from required-check failures. “Mitigated” names a later change, not proof that every intermittent cause disappeared.

| Runs | Job/cause observed | Owner and disposition |
| --- | --- | --- |
| 36523555202 | Required validate: adaptive-paper exporter registration assertion failed | Trading adaptive-paper metrics owner; underlying registration cause unproved, no dedicated repair identified |
| 36645830933, 36646406088, 36647290868 | Required OSV: OpenHands frozen lock, PyJWT 2.13.0 advisories | OpenHands dependency owner; #525/#546 relocks merged; current lock 2.15.0 |
| 36783972732, 36784221993 | Required OSV: LiteLLM 1.93.0 / GHSA-3cv6-jpf6-8222 | OpenHands dependency owner; #562 merged at `74cc5468691ada09674f325ebb2cddbdfe4ad68c`; current lock 1.93.2 |
| 37067723514, 37147299685, 37168905683 | Required validate: `test_k4_timing`, shell-words/f-header controls | Guard owner; GC-isolation mitigation #665 merged at `e7c297e255c98337b54ff3d514191d5d1fa36354` |
| 37135948481, 37135948579 | Linux and macOS manifest ordering validation failed on the same SHA | Shared manifest integration owner; current main passes; #708 is a preventive proposal |
| 37249462697 | Required validate: gateway-idle retry fixture returned 125 (`EXIT_IDLE`) instead of zero | [#696](https://github.com/seathatflowsinourveins/native-agent-stack/pull/696); intermittent watchdog outcome, underlying trigger unproved |
| 36825377925 | macOS: credential-run SIGHUP assertion `1 != 8` | Credential-run owner / #711 workflow scope; unresolved here |
| 36867111096 | macOS: OpenHands netprobe positive-control assertion `True != False` | OpenHands probe owner; port race is a hypothesis |
| 37151325855 | macOS: credential-run child `communicate(timeout=60)` expired | Credential-run owner; child timeout, not GitHub job timeout |
| 37174409325 | macOS: incentive-monitor second-sweep assertion `(0,1) != (0,2)` | Incentive-monitor owner; underlying trigger unproved |
| 37067723566, 37100416149 | Linux bootstrap curl HTTP 500/exit 22; missing status artifact follows | Bootstrap maintainer; endpoint not established |
| 37157767436 | macOS Homebrew bootstrap download error/exit 56 | Bootstrap maintainer / #711; endpoint not established |
| 37238141977 | macOS bootstrap curl HTTP/2 stream error/exit 92 | Bootstrap maintainer / #711 |
| 37229129131 | Advisory native-token tool exactness control failed | Token maintainer; #698 repair merged at `5e659eb8361facfbe046c0477ac108f568dd7384` |

For 37249462697, the runner file and failing test body are unchanged between its SHA and main. The [runner constant](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/tools/sota-convergence/landscape-sweep/codex_job.py#L226) identifies exit 125; the [test](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/tests/test_landscape_sweep_harness.py#L2440) sets 0.2-second idle and 0.1-second kill grace. The latest main log explicitly records that test as OK. Suggest that #696 investigate fixture readiness/timing; evidence does not yet select a repair.

Four cancelled Scorecard runs (37149396638, 37149418947, 37149426843, 37247963368) have zero jobs and a shared workflow/event/ref concurrency group. Default pending-run replacement is consistent with those observations; cancellation actor is not established. [GitHub concurrency contract](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency). Validate cancellation 36802271844 has a cancelled suite step but a null job conclusion; its unique run-ID group and PR-only cancellation do not support main supersession. Its exact trigger remains unknown.

## Current required-check handoffs

These are states of captured heads; checks can change without a new head. Retained check IDs, SHAs and times make that boundary explicit. No duplicate repair PR is opened for owned paths.

| Owner PR | Required blocker / next owner action |
| --- | --- |
| #711 | Add the unreleased-path disclaimer in macOS adoption docs; remove the now-unused bootstrap-macos cache exemption in `tests/test_workflow_policy.py` |
| #690 | Register both `scorecard.yml` and `security-scan.yml` changed bytes; supply a non-empty SOTA sources section |
| #712 | Reconcile changed retrieval-test bytes with the WSL retrieval experiment's frozen evaluation hash; preserve historical qualification semantics |
| #709 | Update stale `otel.environment` source citation/disposition line after README movement |
| #692 | Rebuild the generated component evidence matrix outputs |
| #581 | Reconcile sandbox-runtime lifecycle identity 0.0.77 versus 0.0.78 |
| #629 | Reconcile stale branch's braces 3.0.3 scan result with current main's frozen-lock policy |
| #535 | Resolve its node-forge 1.4.0 advisory in both dependency-review and OSV under the owning runtime qualification |
| #708, draft #703 | Conflicted; all seven required contexts absent. Owner must resolve the branch; absence is not a green result |
| #706, #696 | Validate still in progress in the captured observation |
| #714 | Validate was in progress in the initial observation; the pre-publication GET confirms it merged as `f946c6d4ca988a17b6fa4392ecb488909f147883` |
| #705 | Secret scan in progress; validate cancelled in captured observation. Owner checks current completion before considering readiness |

Workflow-path ownership additionally includes #707/#642 (catalog freshness), #642 (publish and supply chain), #633 (worker freshness), #706/#595/#596 (validation), and #690 (Scorecard/security scan). File-list pagination for #633 and #535 is retained through terminal pages: #633 has 107 files; #535 has 434 files, with its final 34-file page captured during the final review. Both are below the [REST file-list cap](https://docs.github.com/en/rest/pulls/pulls?apiVersion=2026-03-10#list-pull-requests-files). This lane found no unowned converged workflow repair. Unproved timing/network causes remain recommendations to their owners.

## Sources, alternatives and overturn conditions

Use the installed **gh 2.102.0** native REST command, verified against [its release](https://github.com/cli/cli/releases/tag/v2.102.0) and [API source at tag](https://github.com/cli/cli/blob/v2.102.0/pkg/cmd/api/api.go#L103); tag commit is `fc4b137cdef0a6bd28fd461b7cf9c84a5812a8cd`. Explicit GET prevents field flags from changing a read into POST. `gh run list` is a convenient view but lacks server-total evidence; `gh pr checks --required` uses GraphQL. A new SDK or runner adds no evidence advantage here. Native metrics remain an optional independent observation, not a replacement for retained run/job records.

The receipt follows the [existing CI measurement convention](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/evidence/receipts/github-ci-measurements-20261003.json). Evidence hashing follows [register_file at the base pin](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/scripts/host_receipts.py#L710). No new runtime, component acceptance or efficiency comparison is adopted, so no new convergence experiment is asserted.

Reopen the record when an owner PR lands or settings change; capture effective rules and final-head/test-merge checks afresh. Investigate a new latest-main required failure through its job/log records, without rerun loops. Revisit timing hypotheses only after a bounded reproduction or more diagnostic native evidence identifies the cause. A new supported API cap, pagination or queue contract also reopens the collection method.

The completeness critic independently verified the census, partition boundaries, counts and existing duration statistics. It found five omitted zero-second action-required duration records; all are now included. Its final review caught the written table placeholder and #535's nonterminal file page; the table and terminal page are now retained. Its other findings produced canonical dynamic names, zero-run/branch-only distinctions, paginated ownership, CodeQL-rule coverage and explicit retry/PR-readiness limits. The next CI sweep should inspect earlier attempts for intermittent failures, final test-merge checks after conflict resolution, pending queue behavior, and artifact/check retention. Skills discovery is keyed to lifecycle: search-first for measurement choices, gh-fix-ci and diagnosing-bugs for failure inspection, context-mode for large-output processing.

## Evidence and recovery limits

Class: independent observation of native GitHub records, source review for causes, structural validation for hashes/recounts. Local validation is not upstream acceptance. No model/provider, GPU, paper operation or new hosted test was run for this record.

Every accepted native projected output has command arguments, start/end time, exit code and decoded-output hash. Archive/log excerpt sanitization is declared; full raw bytes are withheld and cannot be reconstructed from hashes. Native argument vectors redact only the installed executable path. The private lane status retains the working-directory locator. Repository retention reads 90 days, while individual artifacts have shorter limits.

Failed reads and transfer/parser mistakes remain recorded in the receipt. Prior summary-only numbers are not silently promoted into retained native payload evidence. Resume from this record, its receipt and the owner head snapshots; verify current state before using an old observation as a current gate.
