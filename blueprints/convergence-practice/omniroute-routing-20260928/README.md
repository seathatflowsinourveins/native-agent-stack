# GPT-6 lane account routing through OmniRoute: convergence record, 2026-09-28

[`experiment.json`](experiment.json) records how the GPT-6 Codex lanes on `nativestack-5975wx-20260925` reach a pool of
six ChatGPT subscription accounts through OmniRoute, and what was decided about it. It was assembled after the work
ran, from the sanitized receipts in
[`evidence/artifacts/omniroute-routing-20260928/`](../../../evidence/artifacts/omniroute-routing-20260928/README.md).
The decision is `trial`. The adjudicated rules are this lane's routing standard, except 47 fields in 37 of the 51 items
that a later GPT-6 review of this record refuted (16) or amended (31); those await re-adjudication (`decisions.json`,
`gpt6-record-review`). None of the rules is accepted runtime behaviour yet.

This record covers the coordinator's log through its 03:50Z entry and the GPT-6 record review that ended at 04:13:48Z.
Later work, including the occupancy patch workflow's review rounds from about 04:0xZ, belongs to that workflow and a
later record.

- 20128 is the shared gateway, build `dd6e9607e` (release/v3.8.51 `a58000c7` with PRs #14904 and #13788).
- 20129 is the full-compression lane. It reaches 20128 through the `sharedgw` provider node.

## The failure

On 20128, OmniRoute's post-affinity OAuth occupancy override (`auth.ts:2159-2177`, always on from `chat.ts:1711`)
moves a turn off the session's pinned account when another OAuth account whose priority number is at most the pinned
account's plus one (any better, equal or next priority) has fewer foreign in-flight sessions. The pin itself is not
updated. Two measurements of how often a turn lands on another account:

- **Per-conversation pin-creation method, 24 h ending about 2026-09-28T00:13Z:** 460 of 4,461 matched GPT-6 turns
  (10.31%, in 64 of 201 conversations). Cache-read share was 73.76% on those turns and 92.14% on pinned turns
  (`route-mapper-final.json`). The adjudication used this figure.
- **Per-turn method, 06:58Z to 00:13Z, reported after the adjudication:** (the report does not state its start-time
  basis; route-mapper's frozen control, with the same pairing rule and the same 339 off-pin turns, uses start =
  timestamp - duration/1000, so the 8.0% does not repeat the withdrawn computation's error) 339 of 4,231 turns (8.0%),
  with 85.6% against 94.5% (`route-mapper-part1-final.md`). The rate depends on load, unevenly: mostly 0% in hours with
  peak in-flight 4-8, and 16.7% at 12Z (peak 13), 17.4% at 14Z (peak 14) and 21.7% at 16Z (peak 32). From the frozen
  control's table rows (`offpin-control-prepatch.md`), the eight hours with peak at least 10 give 284 of 2,756 (10.3%;
  2.8-21.7% per hour), and the other hours give 55 of 1,614 (3.4%).

Both are observational: off-pin selection rises with load, so the association with cache loss is not causally
isolated.

OmniRoute PR #8940, which introduced the occupancy signal, lists existing same-session affinity among the stronger
routing constraints, yet its own merge already has the override. In their checked strict-affinity paths, the four
reviewed gateways (CLIProxyAPI, sub2api, LiteLLM, llm-d-router) keep a live binding while the bound account is
eligible. There are opt-in or failure-driven exceptions. sub2api's weighted-sticky mode scores the sticky account
against load (`openai_account_scheduler.go:1023-1037, 1064-1085`), and its sticky escape leaves the bound account on
error rate, TTFT or full concurrency (565-601). LiteLLM skips affinity for an ordered fallback target
(`deployment_affinity_check.py:432-433`). These exceptions do not negate OmniRoute's always-on post-affinity override.

## How the practices were settled

1. route-landscape (Claude) catalogued practices P1-P22, risks R1-R8, exclusions E1-E9 and unknowns U1-U4 from
   pinned clones, then added P23, a P1/P7 clarification and the recomputed live finding.
2. Two GPT-6 jobs, `gpt-6-astra` at effort `max` through `codex-cli 0.157.1`, opened their own sources. JOB 1
   answered the question without seeing the catalog: 6 practices and 5 rejected practices. JOB 2 tried to refute the
   catalog: 10 confirmed, 3 refuted (P1, P14, R6), 27 amended, 6 not checked (E2-E4, E6-E8) and 3 missed practices.
3. route-mapper (Claude, read-only) mapped OmniRoute's routing mechanisms and 24 h metrics on both ports. It checked
   what expiry-first changes and which quota window binds, and found no upstream fix of the override on 547 branches
   or 354 open PRs as of about 01:30Z.
4. route-landscape reviewed OmniRoute PRs #8939, #8940, #5943 and #13102 and four reference gateways, and wrote down
   a cited minimal fix.
5. A `gh api` query at 02:01:49Z found 17 of the 18 cited upstreams maintained. Portkey-AI/gateway is stale (last
   commit 2026-05-25).
6. Three adjudication stages (model `opus`, effort `max`) settled all 51 items under
   [`adjudication-rule.json`](../../../evidence/artifacts/omniroute-routing-20260928/adjudication-rule.json). None
   ended in an unresolved disagreement. The stages ended at 02:32:12Z.
7. route-mapper's final part 1 report arrived at about 03:30Z, after the adjudication. It observed no quota cutoff in
   the retained snapshots and logs through 03:29Z and measured off-pin per turn and by load. It is recorded as its own
   run and was not adjudicated.
8. route-mapper's pre-patch off-pin control ran read-only at 03:31:57Z over 06:00Z to 04:00Z, and the coordinator froze
   it at about 03:4xZ (`offpin-control-prepatch.md`, with the script as `offpin-control.py.txt`). The coordinator's
   rerun to 03:00Z reproduced all 21 hourly rows (`offpin-rerun-team-lead.tsv`). Both are recorded as runs and were not
   adjudicated.
9. A GPT-6 review of this record (`gpt-6-astra` at effort `max`, 03:53:02Z to 04:13:48Z) read its `experiment.json` and
   this README as first committed. It returned 78 findings: 21 confirm, 17 refute and 40 amend. 65 of them judge
   adjudicated item fields (18 confirm, 16 refute, 31 amend), and 13 judge the record or add risks
   (`record-review-gpt6.last.json`). The synthesis re-opened the sources behind nine of the findings, and each held.

## Adjudicated items

| Action | Converged | Converged with amendment | Single family | Not checked by GPT-6 JOB 2 |
| --- | --- | --- | --- | --- |
| applied | | P17 | | |
| approved_pending | ADD-LIVE | P1, P7, P18, P19, ADD-P1P7 | | |
| deferred_to_ab | P12 | P4 | | |
| kept_as_is | P21, R1, R2, R5 | P2, P6, P9, P10, P11, P13, P14, P15, P16, P22, P23, R3, R4, R6, R7, R8 | | |
| not_applicable | U3 | P20 | | E4, E7, E8 |
| open_unknown | U1, U4, M1 | P3, P5, U2 | M2, M3, M4, M5 | |
| rejected | E1 | P8, E5, E9 | | E2, E3, E6 |

The later GPT-6 record review refuted E6's action, amended E3 and E5, confirmed E7's action, and confirmed that E2, E4
and E8 stay unchecked. It refuted fields of P1, P3, P5, P9, P14, P18, P19, ADD-P1P7, R3, R4, U2, M4, M5 and E6
(`decisions.json`).

[`adjudication.json`](../../../evidence/artifacts/omniroute-routing-20260928/adjudication.json) holds, for each item,
the adopted rule, the pinned upstream sources, OmniRoute's state with file and line, the action, a verify metric and
an overturn condition.

## Decisions (UTC, 2026-09-28)

- **01:22:13Z, applied (P17).** On 20129, `PATCH /api/resilience {"requestQueue":{"autoEnableApiKeyProviders":false}}`.
  The read-back shows the `sharedgw` limiter went from enabled to disabled, and no other resilience setting changed.
  Its effect has not been measured.
- **01:20Z, not applied: lever (d), expiry-first on 20128.** It changes only the target of the in-request Codex 429
  rotation, and no rotation happened in the window. It reopens as the D01 A/B only if Codex 429 rotations occur and the
  double move they can cause (a rotation, then a new pin) is observed.
- **01:29:29Z, freeze.** 20128 is frozen from the admissible R02 dry read-back through the R02 scored run (PR #445).
  As of the coordinator log's 03:3xZ entry that run had not started and had no active owner, so the freeze has no end
  date.
- **About 01:35Z, approved, acceptance pending: the 20128 affinity-over-occupancy patch** ("Full patch after R02").
  Part (i) skips the occupancy override when an eligible pin was reused (told apart from a fresh pin explicitly;
  `decisions.json`), in the guard form of OmniRoute PR #13102. Part (ii) binds a fresh pin to the connection that
  served it. A separate workflow builds it, and it is applied only after the R02 scored run.
- **About 03:3xZ, acceptance must use loaded hours.** After route-mapper's final part 1 report, the patch's acceptance
  compares hours with peak in-flight at least 10, stratified by peak.
- **About 03:4xZ, frozen: the pre-patch control.** route-mapper's script ran at 03:31:57Z, and the coordinator's rerun
  reproduced its hourly rows. Acceptance reruns the same script after the patch (`offpin-control-prepatch.md`).
- **Kept.** 20128's 4 h affinity TTL and Codex round-robin with `stickyRoundRobinLimit` 1 are unchanged. The kept TTL
  does not preserve continuation ownership past expiry. An expired pin is deleted, and the next turn gets a fresh LRU
  pin even when the original account is healthy (`sessionAccountAffinity.ts:63-83`; `sessionAffinityPin.ts:280-319`).

## Failed and withdrawn conditions

- **Withdrawn: 8.4% off-pin (84.1% against 93.9% cache-read share).** The first computation did not treat
  `call_logs.timestamp` as the request end. The per-conversation recomputation gave 10.31%, and route-mapper's later
  per-turn method gives 8.0% over a different window. The withdrawn text stays in the catalog's addendum and was left
  out of the JOB 2 prompt.
- **R02 dry read-back, attempt 1 (01:23:33Z, revision `00a94b52`): exit 2.** `/api/monitoring/health` needs
  management auth, so version and sha came back null. Attempt 2 (01:29:29Z, revision `bddb0072`) read the keyless
  `GET /api/system/version` and the `BUILD_SHA` sentinel instead and exited 0.
- [`decisions.json`](../../../evidence/artifacts/omniroute-routing-20260928/decisions.json) also records:
  - a quota-cutoff projection that did not hold;
  - a corrected quota-window source;
  - JOB 2's maintenance answers, all `unknown` until the `gh api` query closed them;
  - JOB 2's spent retrieval budget.
- **Interruptions (context, not runs).** The user paused work from 00:38Z to 01:20Z. From about 01:29Z to 01:35Z the
  Claude account's weekly limit paused the separate 20129 design workflow.

## Usage

| GPT-6 job | Uncached input | Cache read | Output | Reasoning, inside output | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| JOB 1, independent answer | 173,294 | 2,356,864 | 23,409 | 11,724 | 2,553,567 |
| JOB 2, refutation | 232,411 | 2,875,776 | 34,696 | 16,448 | 3,142,883 |
| Record review | 188,806 | 4,856,064 | 34,819 | 12,650 | 5,079,689 |

- All three counts are Codex's own `turn.completed` usage. Cache creation was 0 for all three jobs, and native retries
  are unknown.
- The usage of every Claude worker is unknown and is not estimated. That covers the three teammates (route-landscape,
  route-mapper and route-gpt6, which ran the GPT-6 jobs), the three adjudicators, the builder, the reviewers and the
  coordinator.
- There is no savings claim. The two uncached-token estimates in the adjudication measure overlapping things and must
  not be added: P1's about 5,370,000 per 24 h and P7's 7,520,091.

## Open unknowns

| Unknown | Next check |
| --- | --- |
| U1: the backend's cache scope and TTL, and whether cached tokens cost less quota | regress per-account quota burn on complete account traffic over identified quota windows, controlling output and reasoning, with uncertainty and stability criteria declared first; report an association, not a provider accounting rule |
| U3: cache isolation for Claude OAuth accounts | not applicable until a Claude OAuth lane exists |
| U4: per-account concurrency limits | 429s classified by type (concurrency, quota or rate) in each per-account in-flight bin, at matched model, quota headroom and load, with the rise that activates P18 admission declared first |
| The binding quota window's length (behaves as 7-day; inferred) | record each window's length from the upstream headers |
| Whether encrypted reasoning minted by another account is decrypted, rejected or ignored | the paired P5 probe with repeated state-sensitive tasks, a same-origin positive control, a visible-history-only negative control and a fidelity margin declared first; equal answers alone do not show that foreign encrypted reasoning was honored |
| Whether 20129 forwards `prompt_cache_key` to 20128 | a synthetic key through 20129, comparing the inbound and outbound `prompt_cache_key`, `session-id`/`session_id` and `thread-id` at both hops and accounting for OmniRoute's Codex identity rewrite (`codexIdentity.ts:453-480`), before the #431 cache comparison is read out; the 20128 affinity key kind is auxiliary |

## Next test and rollback

The loaded pre-patch control is frozen. After the R02 scored run, apply the occupancy patch once its upstream suite
passes. Declare the window, the minimum sample per peak stratum and the margins, then rerun the control script
stratified by peak, with the per-conversation method alongside. Require no unexplained move off an eligible pin and no
model or effort mismatch. Compare with the frozen control and, as context, with these whole-window baselines, which
mix loaded and quiet hours:

- served-not-pin rate, 10.31% per conversation and 8.0% per turn;
- key and thread groups served by more than one account, 27.27%;
- cache-read share on formerly overridden conversations, 73.76% against 92.14%;
- per-account peak in-flight: 2, 2, 8, 8, 10, 11;
- 429 and 499 rates: 0.0 and 0.028.

Then run the `prompt_cache_key` and P5 probes, and count `previous_response_id` and `configuration_update` items
(M1, M3). A failed criterion reopens its item under the overturn condition in `adjudication.json`.

To roll back the limiter lift, `PATCH /api/resilience {"requestQueue":{"autoEnableApiKeyProviders":true}}` on 20129.
The stored limiter values never changed; read back `GET /api/rate-limits`. This record changed nothing on 20128. The
patch has its own rollback: restore build `dd6e9607e`.

## Limits

- This is source review and decisions. The only runtime change this record made is the limiter lift, and it has a
  read-back but no measured effect. The 2 later 20129 turns do not measure it, and their `added_wait_ms` column may not record limiter
  waits.
- The metrics are one 24 h window on 20128 and route-mapper's later per-turn and hourly recheck. On 20129 they are the
  10 probe turns of that window and 2 turns after the limiter change.
- P1 and ADD-LIVE were adjudicated on the 10.31% figure, without the per-turn figure or the load dependence.
- The patch waits on the R02 scored run, which had no active owner as of the coordinator log's 03:3xZ entry.
- The route-mapper and route-landscape results are teammate reports that the coordinator wrote down.
- The adjudication rule and the post-patch criteria were written after the research runs, not before them.
- The GPT-6 record review names further untested risks. The 20129-to-20128 hop forwards `x-session-id` but not
  `session-id`, `thread-id` or `x-codex-turn-state` (harm:2). Threshold-triggered context compaction on `sharedgw` can
  rewrite earlier input (harm:3; recheck it against the 20129 settings after 03:49:59Z). Model, tier and
  effective-effort preservation across both hops is unproven (harm:4). OAuth refresh concurrency needs review before
  pinned traffic concentrates (missing:1). HTTP 200 is not completion without the terminal SSE event (missing:2). The
  all-200 counts in part1-final-recheck and limiter-lift-20129 are HTTP status only.

## Addendum (2026-10-03)

The R02 scored run never started. The 2026-09-30 rebuild restarted 20128 with `045aa81f3`, ending **in fact** both
the freeze under "Decisions" and the "after R02" order under "Next test and rollback". The rebuild record names
neither R02 nor #445. No explicit release by the user is on record; this addendum neither claims nor supplies one
and releases nothing. #445 is retired by the
[dated R02 retirement record](../../../docs/decisions/2026-10-03-retire-gateway-ab-r02.md), which preserves the
design, history and evidence limits. Sources: the original `decisions.json:29-41,65-74` and
`docs/decisions/2026-09-30-omniroute-rebuild.md:3-8,43-55`; class `source_review`. The historical instructions
above and every pinned artifact remain unchanged.
