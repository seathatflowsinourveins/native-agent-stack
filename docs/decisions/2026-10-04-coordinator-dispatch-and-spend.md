# Decision: Claude spend after the WSL update follows coordinator run volume; builders move to the GPT lane under a concurrency cap (2026-10-04)

**Decided by:** the command-center session `wsl-architecture-design`, with the amendments of session `native-agent-stack-5f`, which both coordinators accepted on 2026-10-04 at about 14:20Z.

**Requested by the owner on 2026-10-04 (paraphrased in the command-center record):**
- They asked to fully optimize token spending after its sharp rise since the WSL update. [RTK's native initializer](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/init/codex.rs) supplies hook integration; savings require observation.
- They asked for high invocation and live upstream hooks through native end-to-end commands, with observed savings and multiple converging checks. [Harbor's pinned harness](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/README.md) is an evaluation reference; retain each counter's scope, failures and limits.

**Builds on:** [2026-09-29 token spend attribution](2026-09-29-token-spend-attribution.md). Run shape is where spend concentrates, and savings are sought in architecture. Effort stays `max` and the advisor stays on, as the user chose. The later Advisor model decision below changes the advisor model at the user's request. Effort, compaction, hooks and the main-model pin remain unchanged.

**Measurement:** receipt [`claude-spend-window-20261004`](../../evidence/receipts/claude-spend-window-20261004.json), from three instruments that agree on direction within their different scopes:
- ccusage 20.0.26, `daily` and `session`;
- Claude Code's OpenTelemetry counters in the local Prometheus;
- the 2026-09-29 transcript scanner, re-run with a window comparison.

## What the measurement says

**Daily Claude cost** (ccusage, API-equivalent; the subscription meter weights tokens differently):
- 10-01 and 10-02: $2.8K and $2.4K.
- 10-03: $5.9K. 10-04 is on a similar pace.
- 09-26/27 priced totals were $5.4K to $6.0K. Sonnet 5.5 is unpriced in ccusage from 09-28, so later dollar totals omit its cost. Prometheus supports the short dip: its UTC days 10-01/02 are $3,794.72/$2,056.14, against $6,600.64 on 10-03 (receipt data.prometheus_daily). The instruments support direction, not an exact reconciliation or a complete ccusage trough claim.

**Per 24 h, 10-01/02 against 10-03 to 10-04 14Z** (the scanner's relative cost index, IET):

| Measure | 10-01/02 | 10-03/04 | Change |
|---|---|---|---|
| Executor IET | 744.4M | 1,579.0M | ×2.1 |
| Executor IET plus advisor-cohort estimate | 830.3M | 1,778.0M | ×2.141 |
| Call rows | | | ×2.4 |
| Subagents started | 301 | 850 | ×2.8 |
| Calls per subagent | 44 | 44 | unchanged |
| Mean context per call | 272K | 216K | fell |
| Workflow-stage IET | 372M | 1,080M | ×2.9 |

**Advisor accounting:** calls.tsv contains executor rows only. The file-start cohorts in files.jsonl retain 689 Fable iterations in A (141,966,410 input; 5,973,717 output) and 1,209 in B (231,924,586 input; 9,979,005 output). Adding their relative index gives 830.3M versus 1,778.0M per 24 h: ×2.141, still ×2.1 at one decimal. Advisor aggregates span whole files and lack iteration timestamps, so this is a cohort estimate alongside the executor call-window index.

**IET weights:** every model uses the same coefficients: input 1, cache read 0.1, five-minute cache write 1.25, one-hour cache write 2, and output 5. Unclassified cache writes receive 1.25; thinking is already included in output. Advisor aggregates do not split cache-write durations, so all their cache writes receive 1.25. These coefficients come from `report.py` and the retained comparison artifact (receipt data.window_comparison.iet_weight_scope), without model-specific base prices. IET shares and ratios describe this relative index; they do not establish dollar shares, actual spend ratios or savings from changing the advisor.

**Who** (retained ccusage session-selection views, not spend since 10-03):
- The raw Claude export totals $12,404.88. It includes 17 rows worth $1,252.96 whose last activity precedes 10-03 04Z.
- Selecting last activity from 10-03 04Z leaves $11,151.92: `wsl-architecture-design`'s tree 63.3%, with 50 workflow rows, and `native-agent-stack-5f`'s tree 33.8%, with 36 workflow rows (receipt data.ccusage_session_view.activity_selected_view.coordinator_trees). Re-reading the pinned session export and mapping workflow folder names to scanner parents confirms 38 raw rows for the latter tree, with two excluded by this cutoff; receipt data.ccusage_session_view.workflow_row_count_observation retains the check.
- Workflow rows are 57.1% of this activity-selected denominator; the unfiltered export's workflow share is 61.4%. Session totals can contain earlier entries even after the activity filter.
- Opus 5.5 is 85% of the executor-only index, and effort is `max` on nearly every executor row. Advisor effort is not recorded in the retained aggregates.

**What did not cause it:**
- **Hook text:** the SubagentStart token-lanes carrier is about 870 tokens per subagent, and context-mode's PreToolUse tips are a few hundred bytes.
- **Injected start context:** it grew about 0.8K tokens per subagent.
- **Token-tool use:** subagents already route 31% of their tool calls through context-mode.

## Decisions

1. **Builders go to the GPT lane** through the packaged Codex SDK worker (`examples/omniroute-codex-sdk/worker.py`, Sol at max).
   - Cross-family stays cross-family: a Claude-built change gets a GPT review, and a GPT-built change gets one bounded, read-only Claude Opus review (about 30 reads, one agent, a shared packet). A GPT review of a GPT build is not the independent review.
   - A build that needs Claude-only tools, or judgment without a written contract, stays on Opus. For a contract build eligible for either decision 1 or 2, decision 1 wins: use the GPT builder; decision 2's Sonnet allowance applies to judgment/synthesis fan-out, not those builds.
   - Guard and credential-path builds go to the GPT lane only with conformance framing. A flagged job retries once with an edited brief, then returns to the coordinator.
2. **Claude workflows are for judgment and synthesis.** Sonnet 5.5 takes fan-out units that an executable oracle or a later Opus stage checks, and deterministic scripts do extraction (`examples/claude-native/workflows/README.md`, dispatch by role).
3. **Every workflow states its agent count and per-agent tool-call budget,** and gives its stages a shared packet instead of having each one re-read the same sources.
4. **At most four concurrent Claude background units per coordinator,** counting Workflow runs and Agent-tool background subagents alike. A read-only judgment stage that gates a landing may take a fifth slot.
5. **Preregistered protocol roles are exempt.** The exemption applies to the family/model and reviewer-family routing in decisions 1 and 2 only. Where a bound text fixes a role's family or model (for example, the code-search blind roles, or the memory head-to-head judge and audit roles), the text governs. Decisions 3, 4, 6 and 7 retain their resource, pool and observation requirements.
6. **Before any GPT fan-out of three or more jobs, check the pool.** Do a read-only `GET /api/usage/provider-limits` on the gateway, never a POST, and size the launch to the accounts with headroom. A job that hits a 429 is reported, not retried.
7. **"Quality unchanged" is a tested claim.** Observe at least 10 eligible GPT-built PRs and at least five complete Claude-built baseline PRs from 10-03/04. Record P1 findings per independent cross-family read and substantive repair rounds per PR using the observation contract below. The quality gate is pending until baseline builder attribution, heads and all counters are complete. Record exact one-day Claude spend and accepted throughput per coordinator against a qualified 10-03 baseline; the mixed session export above does not supply it.

The token layer's own effect is judged by the with-vs-without comparison of the clean-session evaluation harness (arm F against arm F-token), together with each tool's upstream counter (`ctx_stats`, `rtk gain`, headroom stats). It is not judged by invoke rates alone. High invoke rates and live upstream hooks remain the adoption target the user set. They are measured per agent type from transcripts and the OpenTelemetry logs.


## Advisor model

On 2026-10-04 at about 15:10Z, the user chose Opus 5.5 as the advisor. The template now carries `advisorModel: "opus"`, using the [supported native setting](https://code.claude.com/docs/en/advisor#set-advisormodel-in-settings). The receipt records Fable at $2,092.87 of $5,940.56 priced Claude dollars on 10-03 (35.23%). The coordinator supplied the workstation read-back `claude -p "/advisor"` → `Advisor: Opus 5.5`; this repair does not replay that model call. This supersedes the dated Fable-template selection in the 09-27 model-currency record and 09-30 routing table. Historical Fable measurements remain historical; savings and quality after the change are unmeasured.

## Observation contract

Use the receipt's data.dispatch_observation_protocol. A P1 count sums newly confirmed P1 findings across independent cross-family reads; divide by the number of those reads. Count substantive review-requested repairs per eligible PR; rebases, hash refreshes and unchanged re-reads do not add a round. Publish explicit zeroes only from complete records. Preregistered role exemptions and Claude-only builds are outside this contract-build comparison.

The selection rule is the fixed, enumerated inventory of ten candidate foundation changes below, merged on 10-03/04 by the 14:20Z decision at main b629b5b4. It is a purposive inventory, not every merge in that interval or a claim to be the ten most recent merges; receipt data.dispatch_observation_protocol.baseline_inventory_selection fixes its membership. Retain every candidate regardless of review outcome or missing data. Claude coauthor trailers identify the coordinating client, not necessarily the builder. Score only rows with confirmed Claude builder family, exact review heads and complete counters, after the contract-build exclusions above, and qualify at least five before comparison. Public comments were inspected, but a subsequent counter sweep was rate-limited; unknown cells are retained. The quality gate remains pending, and no quality-unchanged result is claimed.

| Candidate PR | P1 findings across reads | Substantive repair rounds | Evidence limit |
|---|---|---|---|
| [#683](https://github.com/seathatflowsinourveins/native-agent-stack/pull/683) | unknown | unknown | Builder attribution and complete read counters pending. |
| [#688](https://github.com/seathatflowsinourveins/native-agent-stack/pull/688) | unknown | unknown | Builder attribution and complete read counters pending. |
| [#681](https://github.com/seathatflowsinourveins/native-agent-stack/pull/681) | unknown | 1 | PR body records repair round 1; complete P1 reads pending. |
| [#626](https://github.com/seathatflowsinourveins/native-agent-stack/pull/626) | unknown | unknown | Builder attribution and complete read counters pending. |
| [#672](https://github.com/seathatflowsinourveins/native-agent-stack/pull/672) | unknown | unknown | Builder attribution and complete read counters pending. |
| [#673](https://github.com/seathatflowsinourveins/native-agent-stack/pull/673) | unknown | unknown | Builder attribution and complete read counters pending. |
| [#665](https://github.com/seathatflowsinourveins/native-agent-stack/pull/665) | unknown | unknown | Last reported read had 0 P1; complete history pending. |
| [#680](https://github.com/seathatflowsinourveins/native-agent-stack/pull/680) | unknown | unknown | Builder attribution and complete read counters pending. |
| [#676](https://github.com/seathatflowsinourveins/native-agent-stack/pull/676) | unknown | unknown | Builder attribution and complete read counters pending. |
| [#635](https://github.com/seathatflowsinourveins/native-agent-stack/pull/635) | unknown | unknown | Builder attribution and complete read counters pending. |

For each coordinator and local EDT day d, retain `ccusage claude session --since <d> --until <d> --json --offline`, the version, aligned export time and a folder-name-only tree mapping. Qualify its entry-date filter before summing priced totalCost per tree, and retain per-model dollars and unpriced-model gaps. The exact one-day 10-03 tree export is absent here, so per-coordinator cost baselines remain unknown until qualified. Last-activity selection is not a substitute for daily entry membership.

Throughput is distinct accepted PRs merged and distinct completed bounded units per coordinator per local day. A repair/re-read remains the same unit. Compare three-day means against the 10-03 per-day counts; require both to be within 10%, with zero/inactive baselines unscorable. Retain those baseline counts before opening the cost gate. Advisor model and dollars by model must accompany each day because advisor and dispatch changes coincide.

The arms differ: Claude-built work received GPT review with historical budgets not fully recovered; GPT-built work gets one Opus 5.5/max review at about 30 reads. Record model, effort and actual read budget for every read. These are operational overturn signals, not a controlled quality A/B or proof of non-inferiority.

## Alternatives considered

- **Lower effort for mechanical stages.** Out of scope: the user's standing answer is to keep `max` (2026-09-29 record, decision 1). The upstream guidance on effort and thinking (`https://code.claude.com/docs/en/costs`, "Adjust extended thinking", read 2026-10-04) remains the overturn path through the max-default record's arms.
- **A smaller compaction window.** Native defaults stay. #416 is retired; the successor is a separately reviewed and frozen confirmatory cohort through Harbor or Inspect, with quality non-inferiority and a preregistered cost criterion, as specified in the [retirement reopen conditions](2026-10-03-compaction-window-ab-retirement.md#i-reopen-conditions). No such result is claimed here. It would also miss the cause, because main sessions were flat.
- **Fewer token hooks or carriers.** Rejected: the owner asked for live hooks in the October 4 direction above, and their recorded size is small. No matched removal result establishes a saving.
- **Trimming always-loaded files.** The auto-memory index (about 22 KB) and the instruction files are carried by every call. Upstream advises keeping CLAUDE.md small and moving workflow-specific text into skills ("Move instructions from CLAUDE.md to skills", same page). The estimated effect is under 1% of daily cost. It is kept as a follow-up, not a decision here.

## Overturn conditions

- **Revisit decision 1** after at least 10 eligible GPT-built PRs and five complete Claude-built baseline PRs, if either defined quality mean exceeds its baseline. Missing counters or builder attribution keep the gate pending; they do not count as zero.
- **Revisit decisions 3 and 4** if the mean exact daily Claude spend for three consecutive qualifying full days does not fall below the same coordinator's qualified 10-03 baseline, while both throughput means are within 10% of baseline. Inactive or unqualified baselines are unscorable. Report the advisor-model change alongside this comparison.
- **Revisit the token-layer default, not this record,** if the F against F-token comparison shows no token reduction at equal accuracy.
