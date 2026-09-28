# GPT-6 lane account routing through OmniRoute: convergence record, 2026-09-28

[`experiment.json`](experiment.json) records how the GPT-6 Codex lanes on `nativestack-5975wx-20260925` reach a pool of
six ChatGPT subscription accounts through OmniRoute, and what was decided about it. It was assembled after the work
ran, from the sanitized receipts in
[`evidence/artifacts/omniroute-routing-20260928/`](../../../evidence/artifacts/omniroute-routing-20260928/README.md).
The decision is `trial`. The adjudicated rules are this lane's routing standard; none of them is accepted runtime
behaviour yet.

- 20128 is the shared gateway, build `dd6e9607e` (release/v3.8.51 `a58000c7` with PRs #14904 and #13788).
- 20129 is the full-compression lane. It reaches 20128 through the `sharedgw` provider node.

## The failure

On 20128, OmniRoute's post-affinity OAuth occupancy override (`auth.ts:2159-2177`, always on from `chat.ts:1711`)
moves a turn off the session's pinned account when an account of equal or next priority has fewer foreign in-flight
sessions. The pin itself is not updated. Two measurements of how often a turn lands on another account:

- **Per-conversation pin-creation method, 24 h ending about 2026-09-28T00:13Z:** 460 of 4,461 matched GPT-6 turns
  (10.31%, in 64 of 201 conversations). Cache-read share was 73.76% on those turns and 92.14% on pinned turns
  (`route-mapper-final.json`). The adjudication used this figure.
- **Per-turn method, 06:58Z to 00:13Z, reported after the adjudication:** 339 of 4,231 turns (8.0%), with 85.6% against
  94.5% (`route-mapper-part1-final.md`). The rate depends on load: mostly 0% in hours with peak in-flight 4-8, and
  16.7-21.7% in hours with peak 13-32.

Both are observational: off-pin selection rises with load, so the association with cache loss is not causally
isolated.

OmniRoute PR #8940, which introduced the occupancy signal, lists existing same-session affinity among the stronger
routing constraints, yet its own merge already has the override. The four reviewed gateways (CLIProxyAPI, sub2api,
LiteLLM, llm-d-router) keep a live binding while the bound account is eligible, and none moves a bound session because
a peer is less occupied.

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
7. route-mapper's final part 1 report arrived at about 03:30Z, after the adjudication. It found no quota cutoff
   through 03:29Z and measured off-pin per turn and by load. It is recorded as its own run and was not adjudicated.

## Adjudicated items

| Action | Converged | Converged with amendment | Single family | Not checked by GPT-6 |
| --- | --- | --- | --- | --- |
| applied | | P17 | | |
| approved_pending | ADD-LIVE | P1, P7, P18, P19, ADD-P1P7 | | |
| deferred_to_ab | P12 | P4 | | |
| kept_as_is | P21, R1, R2, R5 | P2, P6, P9, P10, P11, P13, P14, P15, P16, P22, P23, R3, R4, R6, R7, R8 | | |
| not_applicable | U3 | P20 | | E4, E7, E8 |
| open_unknown | U1, U4, M1 | P3, P5, U2 | M2, M3, M4, M5 | |
| rejected | E1 | P8, E5, E9 | | E2, E3, E6 |

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
  Part (i) skips the occupancy override when an eligible pin was reused, in the guard form of OmniRoute PR #13102.
  Part (ii) binds a fresh pin to the connection that served it. A separate workflow builds it, and it is applied only
  after the R02 scored run.
- **About 03:3xZ, acceptance must be load-matched.** After route-mapper's final part 1 report, the patch's acceptance
  compares loaded windows (peak in-flight at least 10, or more than about 300 turns/h), and a loaded pre-patch window
  is recorded before the patch is applied.
- **Kept.** 20128's 4 h affinity TTL and Codex round-robin with `stickyRoundRobinLimit` 1 are unchanged.

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

- Both counts are Codex's own `turn.completed` usage. Cache creation was 0 for both jobs, and native retries are
  unknown.
- The usage of every Claude worker is unknown and is not estimated. That covers the three teammates (route-landscape,
  route-mapper and route-gpt6, which ran the GPT-6 jobs), the three adjudicators, the builder, the reviewers and the
  coordinator.
- There is no savings claim. The two uncached-token estimates in the adjudication measure overlapping things and must
  not be added: P1's about 5,370,000 per 24 h and P7's 7,520,091.

## Open unknowns

| Unknown | Next check |
| --- | --- |
| U1: the backend's cache scope and TTL, and whether cached tokens cost less quota | regress per-account quota burn on uncached and cached input |
| U3: cache isolation for Claude OAuth accounts | not applicable until a Claude OAuth lane exists |
| U4: per-account concurrency limits | 429 rate by per-account in-flight bin after the patch |
| The binding quota window's length (behaves as 7-day; inferred) | record each window's length from the upstream headers |
| Whether encrypted reasoning minted by another account is decrypted, rejected or ignored | the paired P5 continuation-fidelity probe |
| Whether 20129 forwards `prompt_cache_key` to 20128 | a synthetic key through 20129, before the #431 cache comparison is read out |

## Next test and rollback

Before the patch, record a loaded pre-patch window on 20128 (peak in-flight at least 10, or more than about 300
turns/h). After the R02 scored run, apply the occupancy patch once its upstream suite passes, and measure a
load-matched window with both methods. Compare it with the loaded pre-patch window and with these whole-window
baselines, which mix loaded and quiet hours:

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

- This is source review and decisions. The only runtime change is the limiter lift, and it has a read-back but no
  measured effect. The 2 later 20129 turns do not measure it, and their `added_wait_ms` column may not record limiter
  waits.
- The metrics are one 24 h window on 20128 and route-mapper's later per-turn and hourly recheck. On 20129 they are the
  10 probe turns of that window and 2 turns after the limiter change.
- P1 and ADD-LIVE were adjudicated on the 10.31% figure, without the per-turn figure or the load dependence.
- The patch waits on the R02 scored run, which had no active owner as of the coordinator log's 03:3xZ entry.
- The route-mapper and route-landscape results are teammate reports that the coordinator wrote down.
- The adjudication rule and the post-patch criteria were written after the research runs, not before them.
