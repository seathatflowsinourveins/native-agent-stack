# Retirement of the unrun compaction-window A/B/C pilot

## a. Status

Lane: foundation. Status: retired 2026-10-03 by custodian session native-agent-stack-0c. No host or settings change.

This record preserves the draft and replaces its role as a living decider.
The native auto-compact default stays. The custodian closes PR #416 after this
record merges; the branch and pinned head remain for downstream citations.
The foundation action serves complex systems and north-star R&D by keeping the
native Claude companion's context behavior source-backed and preserving the
conditions for a future decision-changing experiment.

Evidence here distinguishes independently measured file bytes, live public
metadata, supplied historical observations, and the draft's reported structural
checks. No compaction experiment, model result or historical test replay was
performed for this retirement.

## b. Identity

| Field | Preserved value and provenance |
| --- | --- |
| PR | [#416, “Compaction-window A/B/C preregistration draft (not frozen, not run)”](https://github.com/seathatflowsinourveins/native-agent-stack/pull/416), a draft |
| Branch | `claude/compaction-window-ab-prereg-20260927`; kept |
| Head | `452f7b14715ae2a038c1d4a98e292b5de7812c87` (`452f7b14`), independently observed on both `refs/pull/416/head` and the branch on 2026-10-03 |
| Base of the rebased draft | `37739d3252c8c1aa2cd51b911ca88512e94f3dd3` |
| Opened | 2026-09-27T16:38:32Z, confirmed by the live PR API |
| Last update before custody | 2026-09-28T00:40:11Z, the custodian-supplied historical metadata |
| State at the retirement read | OPEN, draft, CONFLICTING; 0 reviews, 0 comments before the custody notice |
| Custody notice | [2026-10-03T08:21:56Z; two-hour objection window](https://github.com/seathatflowsinourveins/native-agent-stack/pull/416#issuecomment-5967134584) |

The 2026-10-03 live API's `updatedAt` is 08:21:57Z, after the notice, so it
does not replay the supplied pre-notice timestamp. The [public
timeline](https://api.github.com/repos/seathatflowsinourveins/native-agent-stack/issues/416/timeline)
separately records the final head force-push at 2026-09-28T00:39:18Z. These
timestamps describe different events.

The six commits between the base and head are preserved below. Times are
author times in UTC, from public commit metadata; the first five were rebased
with committer time 2026-09-28T00:36:09Z and the last with committer time
00:38:50Z. Historical hashes mentioned inside the artifacts, including
`f7cc409a`, `b6f36d8c`, `8cf950f3` and `52356fee`, retain their original
pre-rebase meaning. The pinned build record explicitly dates those earlier
rounds. [452f7b14:blueprints/compaction-window-ab/build-evidence.json:76](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L76)

| Commit | Author time (UTC) | Subject |
| --- | --- | --- |
| [dcb41ae91](https://github.com/seathatflowsinourveins/native-agent-stack/commit/dcb41ae91c158c43a0fe80081a87b2a059c9eba3) | 2026-09-27T16:37:55Z | Compaction-window A/B/C preregistration draft (not frozen, not run) |
| [788aa905a](https://github.com/seathatflowsinourveins/native-agent-stack/commit/788aa905abf3f6c793cb832cec1431c931bed7fc) | 2026-09-27T19:10:14Z | Compaction-window A/B/C preregistration: repair round (still draft, not frozen, not run) |
| [02b8731ad](https://github.com/seathatflowsinourveins/native-agent-stack/commit/02b8731adfb9791574bf4625b9fcc1fe35e4f0b6) | 2026-09-27T20:28:37Z | Compaction-window A/B/C preregistration: cross-family repair round F1-F9 (still draft, not frozen, not run) |
| [33afd2d91](https://github.com/seathatflowsinourveins/native-agent-stack/commit/33afd2d9179789cc9a37b9bc5a60761575a41c0f) | 2026-09-27T23:57:58Z | Compaction-window A/B/C preregistration: host-condition amendment, incumbent A and window-minus-buffer bands (still draft, not frozen, not run) |
| [5ce9104c9](https://github.com/seathatflowsinourveins/native-agent-stack/commit/5ce9104c928e2b4225be3695b3969be5981ed4e2) | 2026-09-28T00:02:10Z | Compaction-window A/B/C preregistration: classify the four pre-switch F4 events as settings-save transitions (still draft, not frozen, not run) |
| [452f7b147](https://github.com/seathatflowsinourveins/native-agent-stack/commit/452f7b14715ae2a038c1d4a98e292b5de7812c87) | 2026-09-28T00:34:04Z | Compaction-window A/B/C preregistration: review repair (stale-band wording test, computed selection examples, F4 record consistency) (still draft, not frozen, not run) |

Against the retirement build's main base `9b0b8d6d25f9e3fb8f71770500e774170423315e`,
`git rev-list --left-right --count origin/main...452f7b14` returned
`162 6`: 162 main-only commits and these six head-only commits. This is a
dated divergence observation, not a prediction about a later main tip.

## c. What it proposed

The user's choice and planned start are preserved verbatim from
[452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:3](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L3):

> **Status: DRAFT — not frozen, not run.** Written 2026-09-27, foundation lane.
> The user chose “A/B test first,” followed by the best quality per token. The
> planned start is immediately after the weekly reset on **2026-09-30 at 21:00
> America/New_York (2026-10-01 01:00 UTC)**, subject to sealing and readiness.

The amended arms, automatic trigger expectations and partition bands were:
[452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:80](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L80)

| Arm | Window treatment | Expected automatic trigger | Validity band for automatic preTokens |
| --- | --- | ---: | --- |
| A | unset; native 1,000,000 model window | about 967,000 | [870,300, 1,000,000] |
| B | 400000 | about 367,000 | [330,300, 870,300) |
| C | 200000 | about 167,000 | [150,300, 330,300) |

Each trigger was window minus the displayed 33,000-token buffer on 2.1.283.
Each lower edge was 0.9 × that arm's trigger; the next arm's lower edge
provided the exclusive upper edge, with A's 1,000,000 upper edge inclusive.
These were experiment-validity rules, not upstream guarantees. [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:88](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L88)
[452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:935](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L935)

The design had four proposed frozen (unsealed) real-task bundles (builder,
web research, verification and long review), three repetitions per task and three arms:
**4 × 3 × 3 = 36 attempts**. Each used a fresh coordinator process, owned
worktree and task index. All 12 A focal children had to exceed 400,000 prompt
tokens; an underlength, invalid, stopped or unmeasured run was incomplete.
[452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:221](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L221) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:342](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L342) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:527](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L527)

| Task | Repetition 1 | Repetition 2 | Repetition 3 |
| --- | --- | --- | --- |
| builder | ABC | BCA | CAB |
| web | ACB | CBA | BAC |
| verification | BCA | CAB | ABC |
| review | CBA | BAC | ACB |

Each arm occupied each position once per task; all six orderings appeared
twice. The proposed washout was 360 seconds after the last request and owned
process-group termination. Child cache TTL was to be five minutes;
coordinator one-hour effects stayed separate. A fresh process did not prove
a cache miss, and settings did not prove the TTL. The three repetitions
established position balance and a descriptive range only. Paired variance,
confirmatory sample size and statistical non-inferiority were unqualified.
Deleting each whole repetition block in turn was a sensitivity check; a
changed ranking or lost margin was unstable, and the check could not turn any
pilot ranking into adoption evidence. [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:348](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L348)
[452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:355](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L355) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:366](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L366) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:383](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L383)

Every arm was to use the same sealed settings packet and project-only
settings sources. A had to remove the window key from its launch environment,
because an older parent could still pass on 400000. Value-only readback had
to establish each arm's effective window and Workflow-child inheritance,
with the percentage override, output-token cap and 1M-disable modifiers absent.
No settings-source equivalence or inheritance was claimed from documentation
alone. [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:124](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L124) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:133](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L133) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:949](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L949)

The draft's coordinators were Opus 5.5/xhigh under Ultracode; every focal
Workflow child was Opus 5.5/max in its named role. Sonnet 5/max was allowed
only for pure command wrappers. Fast mode, model fallback, a global effort
override and a 200K context hold were excluded. Each child's resolved
model/effort and first-prompt carrier were to be observed, not inferred from
Agent-tool acceptance. These are preserved design controls, not new launches.
[452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:183](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L183)

The decision rule required all 36 valid attempts, independent checks and
complete accounting:

- For every task and check, any A pass required a pass in **every repetition**
  of the candidate. Candidate passed-check and successful-task totals could
  not fall below A's.
- All-attempt weighted child cost per successful task had to be at most
  **0.90 × A**, both pooled and for every task; every compared arm/task needed
  a success. Ordinary completed failures stayed in the cost numerator.
- Among eligible candidates, the unique lowest pooled cost won the
  **nomination**. There was no B/C priority or additional margin between them.
  Unrounded exact decimal/rational arithmetic decided it.
- An exact tie nominated nothing and left incumbent A unchanged. Rounded
  equality was not an exact tie. No best-of selection, imputation,
  arm-dependent repair or replacement attempts were allowed.

These are the pinned contract and selection rules, not an observed result.
[452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:533](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L533) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:539](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L539) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:561](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L561)

At equal quality, A=100/B=60/C=89 nominated B; A=100/B=89/C=60 nominated C;
B=C=60 nominated neither. B=91/C=95 missed the minimum effect. B=60 with a
quality regression could not beat eligible C=89. These were arithmetic
controls applying per task and pooled, not model observations. [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:550](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L550)

The proposed instrument was native OTel request events through the existing
collector into Loki, reconciled once with ccusage v20.0.26. It was explicitly
**log-only, unqualified**: intermediate retries had no qualified counters;
counter-less terminal API errors ended the pilot incomplete; ownership or
request-ID gaps prevented selection. Per-request cache-write TTL splits
were unqualified, so weighted cost and cost per success remained unknown.
The conditional five-minute price weights were Opus 5.5
1/1.25/0.05/5 and Sonnet 5 1/1.25/0.1/5, with dollar-equivalent totals needed
to combine models. These were dated conditional weights, not current pricing
or a saving. [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:393](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L393) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:424](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L424) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:471](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L471)

The **1,000,000,000 native-token ceiling** covered input + cache creation +
cache read + output over every deduplicated owned request, including
readiness, coordinators, children, compaction/background work, wrappers,
retries, failures, refusals and fallbacks. It was a proposed resource ceiling;
complete metering and a proven hard cap were not established. The ledger poll
was one second. Reporting lag was null with zero samples; reserve, delivery,
admission, cancellation and drain bounds remained unqualified. The proposed
reserve was
`R_max * (N_active_max + ceil(lambda_max * (L_bound + P + K_bound)))`.
Each attempt's wall cap was 7,200 seconds; the complete cap had to be at least
`271800 + 36*D + H` seconds for 36 attempts, 35 washouts, 36 drains and
readiness/overhead. D, H and the numeric cap remained null; the action was
**do not launch**. [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:566](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L566) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:590](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L590) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:603](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L603) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:632](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L632)

The exact sealing rules are retained at [452f7b14:blueprints/compaction-window-ab/preregistration.json:1078](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/preregistration.json#L1078)–1080:

| Key | Preserved rule |
| --- | --- |
| `amendment_rule` | “Preserve every prior amendment and seal table. Append date, reason, superseded rules/artifacts, whether results were observed, replacement hashes and merge/execution chronology. After any model observation, a changed workload, threshold, eligibility rule, instrument or budget requires a new cohort; retain the old incomplete/failed cohort. Never silently rewrite or retroactively recode eligibility.” |
| `adoption_rule` | “This pilot can nominate a candidate for an independently preregistered confirmatory cohort only. It supplies no authority for persistent host changes; the host incumbent A (key absent, native default) stays unchanged. Setting B or C on the host requires that confirmatory cohort to show non-inferior quality and the preregistered cost reduction, recorded. This DRAFT neither schedules, launches, freezes nor adopts an arm.” |
| `pilot_allows_persistent_adoption` | `false` |

The open launch questions at [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:713](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L713) and [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:763](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L763) are preserved as
five groups; the [PR's “Open gates” section](https://github.com/seathatflowsinourveins/native-agent-stack/pull/416) states the same
groups:

1. Native isolated per-arm readback and Workflow-child treatment inheritance,
   automatic B/C compactions in an arm, and >400K A-child eligibility.
2. Complete required collector attributes and child/request joins, retry/error
   accounting and per-request one-hour versus five-minute cache-write TTL
   evidence. The collector template alone could not prove active preservation.
3. Reporting lag, enforceable outstanding-token reserve, owned cancellation,
   drain/readiness bounds, budget feasibility and the whole-run wall cap.
4. Executable independent Inspect adapters and control outputs, the frozen
   real-task bundles and the fixed 97-module offline suite's readiness.
5. Final input inventories, primary-source captures, tool/agent/MCP/carrier
   fingerprints, sealed oracle artifacts and independently observed
   seal/merge/launch chronology.

Eight adapter contracts and 32 hashed known-pass, known-fail, malformed and
missing-output controls were specified for Inspect 0.3.271. They were not
executed scorer outputs. Historical installed metadata 0.3.266 was not
substituted; the later builder's interpreter found no Inspect metadata.
No package installation closed that gap. [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:730](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L730) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:788](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L788)

The SIZE-07 outcome was descriptive: each task/arm's check outcomes beside
each focal child's peak prompt tokens and utilization of the model's 1M
window. It was not powered for SIZE-07's overturn condition and did not enter
selection or add a quality-superiority route. [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:501](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L501) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:974](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L974)

## d. Host facts

The host-condition amendment starts at [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:908](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L908). Its inputs were
“coordinator-supplied observations or coordinator-relayed peer observations”,
dated 2026-09-27; the amendment builder did not replay them. It added one
value-only readback and official-document reads. It reported no Claude
session or model call; its version inspection returned 2.1.283.
[452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:910](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L910) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:922](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L922)

| Input | Preserved observation, label and implication | Pinned source |
| --- | --- | --- |
| F1 host condition | At the user's request, peer a9 removed the window environment key after finding no primary recommendation for 400K or 40%; a backup existed. The coordinator's value-only read around 23:28Z returned `absent`; the settings-file mtime 23:21:57Z was not the unknown removal instant. Its shell still read 400000. Builder corroboration at 23:36:46Z was settings `absent`, shell 400000. Incumbent A replaced the superseded 18:59Z B condition; A's explicit environment removal and all-arm settings isolation stayed necessary. | [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:929](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L929) |
| F2 autocompact buffer | Native display observation on installed 2.1.283: `/context` displayed **33k** at unset (1m), 400000, 200000 and 100000. It was not an automatic compaction event or measured threshold. The official default about 967K corroborated 1,000,000 − 33,000; B/C expected triggers were 367000/167000. | [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:930](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L930) |
| F3 consequence | Old C band 180000–220000 excluded its nominal ~167000 trigger; a child near the trigger would be invalid, while an overshoot to 190000 would meet the old band. Old B 360000–440000 held 367000 by only 7000. The final wording corrected the overclaim that every C child would be invalid. | [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:931](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L931) |
| F4 native events | “Peer a9, value-level, coordinator-relayed”: automatic `compact_boundary` entries, `compactMetadata.preTokens`, all main/subagent transcripts including Workflow children, 18:59:21Z–23:23:33Z. Of 35 events, the 31 from sessions running 400000 spanned 366,209–432,724 (median 368,563; 18 main, 13 subagent). Four pre-switch-launched sessions' events spanned 618,371–922,073. Before the switch, every event was 966,908–971,662. The proposed symmetric B band 330300–403700 would exclude 432,724 (+17.9%); partition bands retained overshoot. | [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:932](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L932) |
| F5 implementation reading | Peer a9 reported from the installed 2.1.283 binary: threshold = (window − min(model max output, 20000)) − 13000. This was **“peer-supplied, undocumented implementation reading”**; binary offsets were omitted. No rule relied on it. It disagreed with the docs about capping the output reserve; the protocol instead relied on F2, the documented default and F4. | [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:933](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L933) |

The four F4 events were classified by the coordinator as **transition
events**, not default-window triggers. Saved settings environment changes
applied to running sessions; removal did not unset the value until relaunch.
A request already above ~367,000 could therefore compact at its current size.
The superseded coordinator event at 902,612 was the recorded instance.
Per-event timing (each first request after the save) was **not re-checked**.
The old “unattributed” residual and two relayed texts saying “ran the default
window” remain historical input, with the residual marked superseded.
A's band was unchanged. [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:990](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L990) [452f7b14:blueprints/compaction-window-ab/build-evidence.json:573](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L573) [452f7b14:blueprints/compaction-window-ab/build-evidence.json:586](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L586)

The community sweep separately recorded that sessions started before the
2026-09-27 revert retained 400000 and had **five auto compactions at 365–373K
after removal**. This is that dated record's observation, not a new count
or B-arm trial.
[docs/decisions/2026-09-28-community-sweep.md:525](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-28-community-sweep.md#L525)

## e. Motivation, supplied and not re-measured

The motivation file describes supplied historical diagnosis, copied
2026-09-27, with native run/session labels replaced by local ordinals.
These measurements were not independently remeasured by the draft or this
retirement. Transcript bytes are separate from provider tokens, and the
combined input/cache-write category cannot be retrospectively split or priced.
[452f7b14:blueprints/compaction-window-ab/motivation-20260927.md:3](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/motivation-20260927.md#L3) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:19](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L19)

| Supplied measurement | Preserved value | Pinned source |
| --- | --- | --- |
| Population | 52 Workflow children over 7 runs | [452f7b14:blueprints/compaction-window-ab/motivation-20260927.md:7](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/motivation-20260927.md#L7) |
| Provider usage | cache_read 398,038,533; input+cache_write 11,639,727; output 3,672,138 | [452f7b14:blueprints/compaction-window-ab/motivation-20260927.md:8](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/motivation-20260927.md#L8) |
| Requests | 4,781; average context/request approximately 83K | [452f7b14:blueprints/compaction-window-ab/motivation-20260927.md:8](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/motivation-20260927.md#L8) |
| Largest child | build: 258 requests, maximum context 936,520, cache_read 93.2M | [452f7b14:blueprints/compaction-window-ab/motivation-20260927.md:9](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/motivation-20260927.md#L9) |
| Other large children | agent-memory research: 283 requests, 69.6M cache reads; Hindsight research: 247 requests, 65.3M. Three Hindsight lanes across three workflows were 65.3M + 44.0M + 33.8M | [452f7b14:blueprints/compaction-window-ab/motivation-20260927.md:9](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/motivation-20260927.md#L9) |
| Large results | 588 tool results over 5,120 B, 69% of 9.45 MB of result bytes; target ≤20%. Large-result tools included Read, Bash and Context Mode printing | [452f7b14:blueprints/compaction-window-ab/motivation-20260927.md:10](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/motivation-20260927.md#L10) |
| Transcript composition | thinking 12.65 MB, 2,083 blocks, max effort; tool_result 10.12 MB; tool_use 2.93 MB; hook_success attachments ~4.0 MB; token reminders 1.40 MB; first-prompt snapshots/instructions/skill listing ~5.8 MB | [452f7b14:blueprints/compaction-window-ab/motivation-20260927.md:11](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/motivation-20260927.md#L11) |
| Dated native-lever finding | Opus 4.7+ and Sonnet 5 on the Anthropic API had native 1M, approximately 967K default; the disable-1M lever held sessions at 200K; the weekly limit was seat-based and shared across models | [452f7b14:blueprints/compaction-window-ab/motivation-20260927.md:12](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/motivation-20260927.md#L12) |
| Reported waste/failure | stopped-and-relaunched S3 arms in run-04: 36.4M cache reads. GPT-6 wrapper stages dispatched as source-scout never ran because of a role conflict | [452f7b14:blueprints/compaction-window-ab/motivation-20260927.md:13](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/motivation-20260927.md#L13) |

## f. Review and test history, as claimed by the PR

The [PR body at pinned head 452f7b14](https://github.com/seathatflowsinourveins/native-agent-stack/pull/416) reports the first
draft as GPT-6, `gpt-6-astra`, max effort, through the Codex stack-worker
lane. The [first commit](https://github.com/seathatflowsinourveins/native-agent-stack/commit/dcb41ae91c158c43a0fe80081a87b2a059c9eba3)
records that authorship and the sandboxed builder's inability to write Git
metadata; the coordinator committed the files. The pinned original build
record preserves its failed `git add` (exit 128) and structural checks.
[452f7b14:blueprints/compaction-window-ab/build-evidence.json:11](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L11) [452f7b14:blueprints/compaction-window-ab/build-evidence.json:64](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L64)

The body reports one independent Claude review with nine findings
(one blocker, four majors, four minors), repaired by GPT-6 in one round.
The pinned cross-family F1–F9 round records nine findings, all repaired in
the draft: host readback, untracked/ignored paths, deterministic B1/R1
predicates, attribute-complete collector qualification, narrower retry/error
claims, sealed provider constant, unknown TTL-weighted cost, complete wall
cap, and dated registration history. Its native runtime gates stayed open.
[452f7b14:blueprints/compaction-window-ab/build-evidence.json:77](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L77) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:862](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L862) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:884](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L884)

The host-condition amendment was built by Claude Opus 5.5, followed by the
coordinator's F4 transition ruling. The body reports an independent GPT-6
Astra/max read-only review with **one major and three minor findings**, all
fixed in one repair round:

1. The active “unattributed” residual contradicted the F4 ruling; it was
   preserved verbatim and marked superseded.
2. “Every C focal child” overclaimed; the repair distinguished a nominal
   trigger from an overshoot into the old band.
3. Tests missed obsolete bands in operative prose; current Markdown, current
   JSON and all treatment-proof values gained a scan with explicit historical
   exclusions.
4. The pre-existing selection test compared labels only; the repair computed
   every worked nomination using `fractions.Fraction`, with per-task,
   inclusive 0.90-boundary and exact-tie controls.

The pinned amendment builder, repair findings and tests preserve that sequence.
[452f7b14:blueprints/compaction-window-ab/build-evidence.json:377](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L377) [452f7b14:blueprints/compaction-window-ab/build-evidence.json:609](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L609) [452f7b14:blueprints/compaction-window-ab/build-evidence.json:637](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L637)

| Reported historical check | Returned result and boundary | Pinned source |
| --- | --- | --- |
| Original draft fail-first / green | 1 missing-artifact failure, then 1 test OK; structural checks only | [452f7b14:blueprints/compaction-window-ab/build-evidence.json:11](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L11) |
| Earlier GPT-6 repair fail-first / green | 6 failures / 6 tests, then 6 tests OK; earlier stale registrations failed validation before coordinator refresh | [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:799](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L799) |
| Cross-family F1–F9 fail-first | 14 tests, 11 failures, exit 1 before repairing protocol artifacts | [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:898](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L898) |
| Host amendment fail-first | 21 tests, 10 failures, 0 errors, 11 unaffected passes; exit 1 | [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:1002](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L1002) |
| Review repair fail-first | 23 tests, 2 failures, 0 errors, 21 passes; RR1/RR2 failed, while RR3/RR4 gaps were demonstrated by mutations | [452f7b14:blueprints/compaction-window-ab/build-evidence.json:691](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L691) |
| Review repair green | 23 tests OK, exit 0, after all four repairs | [452f7b14:blueprints/compaction-window-ab/build-evidence.json:743](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L743) |
| Mutation controls | 13 retained first-round mutations plus 21 new mutations = 34/34 caught; unmutated control passed. Of the 21 new mutations, 20 passed the old 21-test module, reproducing gaps; one failed both | [452f7b14:blueprints/compaction-window-ab/build-evidence.json:529](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L529) [452f7b14:blueprints/compaction-window-ab/build-evidence.json:711](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L711) |
| Integration reported in the PR body | Registry tests: 57 OK after rebase. Four `disposition` prose values moved to the closed-vocabulary `fixed` label with prose under `repair`; final six-file registration/validate passed, and the #438 pre-push gate passed | [Pinned PR body](https://github.com/seathatflowsinourveins/native-agent-stack/pull/416), [452f7b14:blueprints/compaction-window-ab/build-evidence.json:743](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L743), [452f7b14:manifests/evidence.json:3824](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/manifests/evidence.json#L3824) |

Historical builder validator failures are retained as such. The final repair's
build record still shows pending registration and validator exit 1; the later
integration success is the PR body's claim, corroborated here only for the
six registered byte identities. These are locally authored structural tests
and mutation checks, not upstream acceptance or compaction results.
The 23-test blueprint suite was **not rerun** for retirement and is kept only
on the PR head.

The PR body's four residuals are preserved:

- The 33k buffer was a `/context` display observation on 2.1.283 and could
  change with the client.
- F4 was **relayed, not replayed**, and transition-event timing was not
  re-checked.
- The obsolete-band scan missed bounds written in words or decimal multiples
  such as 0.36M.
- Two relayed texts still quoted “ran the default window” as input.

The pinned records also retain the unknown removal instant, absent automatic
B/C treatment events, F5's undocumented/capped-reserve disagreement, and the
fact that the Markdown residual bullet agreed but was not itself tested.
[452f7b14:blueprints/compaction-window-ab/build-evidence.json:573](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L573) [452f7b14:blueprints/compaction-window-ab/build-evidence.json:762](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L762) [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:981](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L981)

**Independently measured byte identities, 2026-10-03.** Each row below comes
from complete `git show 452f7b14:<path>` bytes, separately SHA-256 hashed and
counted. All seven hash/count pipelines exited 0. The four blueprint files,
test and blind-checkout entries match the head-versus-base evidence-manifest
diff; the manifest's own blob is measured separately.

| File at 452f7b14 | SHA-256 | Bytes |
| --- | --- | ---: |
| `blueprints/compaction-window-ab/PREREGISTRATION.md` | `c76270ec0804a6e971d6b77cd3a104b584d234607ad848f0a428cf4b4b631970` | 75054 |
| `blueprints/compaction-window-ab/build-evidence.json` | `2126fd4c6cde5ebb480a9272c23c96eeeb8f13e075ed6473932ffd59c19b4f43` | 83309 |
| `blueprints/compaction-window-ab/motivation-20260927.md` | `7e9b224ddb2874cf4836a7ff1d113c7c6c8abb001a1c64d4b4686e9ac907a365` | 1815 |
| `blueprints/compaction-window-ab/preregistration.json` | `c2525d8277a5c00b2dcf63d6929b9c1fe22db247db84914a7ba2f4dbdf132e23` | 153785 |
| `manifests/evidence.json` | `3e987b556bf8306d27ece5811788abd108a6cd276afe70d399a19c799edcd95d` | 1922720 |
| `tests/test_compaction_window_ab_preregistration.py` | `b0546ccb18a59ff8c2062a435760898475ef47e9e55e0b812e1f5612bdce4d28` | 55852 |
| `tools/sota-convergence/blind_checkout.py` | `780312b8d48db5875672cf1baabb307c3a1c50413e2d9072e89ad5250b6109b3` | 55711 |

The registry locators are [452f7b14:manifests/evidence.json:3824](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/manifests/evidence.json#L3824),
[452f7b14:manifests/evidence.json:3829](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/manifests/evidence.json#L3829), [452f7b14:manifests/evidence.json:3834](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/manifests/evidence.json#L3834),
[452f7b14:manifests/evidence.json:3839](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/manifests/evidence.json#L3839), [452f7b14:manifests/evidence.json:39330](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/manifests/evidence.json#L39330)
and [452f7b14:manifests/evidence.json:40065](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/manifests/evidence.json#L40065).
The blind-checkout file is preserved by digest and head reference only;
its head-only classification is not ported. Main already has the `fixed`
classification from #429.

## g. Why retired

The selected alternative is to retire the unrun draft, preserve its evidence
and keep native A. Keeping it as a standing decider or merely re-freezing its
old pilot would leave the actual decision and launch gaps unresolved.
Adopting B/C now would contradict its own confirmation rule.
Each reason has a public source:

1. **The planned start passed without a run.** The draft scheduled no execution;
   its intended 2026-10-01 01:00 UTC start was conditional, and the
   [custody notice](https://github.com/seathatflowsinourveins/native-agent-stack/pull/416#issuecomment-5967134584) states that it
   passed without a run. The pinned status remains DRAFT/not run.
   [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:3](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L3) [452f7b14:blueprints/compaction-window-ab/build-evidence.json:5](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/build-evidence.json#L5)
2. **The client pin is stale for the destination.** A fresh
   `grep -cF 2.1.283` over the pinned Markdown returned **13 matching lines**.
   This counts lines, not every repeated occurrence. The destination's
   [read-only native-command observation](https://github.com/seathatflowsinourveins/native-agent-stack/pull/608#issuecomment-5964814555)
   reports Claude Code **2.1.288**; it is not full host acceptance.
   The draft's installed pin is documented at [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:30](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L30).
3. **Its sequencing target moved.** The
   [roadmap's “after Gate A” entry](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-28-ecosystem-roadmap.md#L227)
   sequenced #416 after Gate A. The user's
   [Gate A re-aim](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-01-definitive-sota-wsl-program.md#L352)
   superseded the old-distribution plan and moved Gate A to the new
   distribution after its clean install.
4. **The amendment addresses the old distribution's leftover 400000
   environment value.** It describes removal from settings while old
   sessions/launchers retained the value; it is a dated host condition,
   not the new destination's baseline. [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:96](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L96)
   [docs/decisions/2026-09-28-community-sweep.md:525](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-28-community-sweep.md#L525)
5. **The five launch-gate groups were never resolved.** They remain in the
   pinned unresolved-gates section, and the
   [custody notice](https://github.com/seathatflowsinourveins/native-agent-stack/pull/416#issuecomment-5967134584)
   states that the five launch gates are unresolved; structural passes do not
   qualify inheritance, metering, bounds, adapters or sealing. [452f7b14:blueprints/compaction-window-ab/PREREGISTRATION.md:763](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/PREREGISTRATION.md#L763) [452f7b14:blueprints/compaction-window-ab/preregistration.json:1064](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/preregistration.json#L1064)
6. **Re-freezing this pilot would not produce a decision-changing protocol.**
   Its own adoption rule permits only nomination for a separate confirmatory
   cohort, and `pilot_allows_persistent_adoption` is false.
   [452f7b14:blueprints/compaction-window-ab/preregistration.json:1079](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/preregistration.json#L1079)
7. **Current A/B/E2E work must use an upstream harness.** The
   [standing harness rule](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-30-rule-text-every-layer.md#L34)
   names Harbor or Inspect for containerized agent tasks and prohibits a
   self-written runner. The Gate A owner's
   [recommended path R](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-01-definitive-sota-wsl-program.md#L371)
   and [Amendment 4 plan](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-01-definitive-sota-wsl-program.md#L400)
   follow that rule (the harness choice was
   [still open at the base](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-01-definitive-sota-wsl-program.md#L366));
   none launches this retired pilot.
8. **Claude Code remains the native companion.**
   [docs/decisions/2026-10-02-two-host-north-star-architecture.md:56](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-10-02-two-host-north-star-architecture.md#L56)
   assigns that role and preserves its native model/effort, authentication
   and orchestration.
9. **The active token/context study preserves native compaction.**
   [#627's protocol at its read head](https://github.com/seathatflowsinourveins/native-agent-stack/blob/385b2d1703f2b7618693b216728d49eff41eb95a/evidence/artifacts/token-context-20261003/protocol.md#L23)
   explicitly says “no custom compaction threshold”; it also refuses to
   call a lowered threshold a natural baseline.

These reasons concern the stale protocol and its decision scope. They do not
establish that an earlier window can never win.

## h. Standing state

The native auto-compact default stays, as recorded by
[docs/decisions/2026-09-29-max-default-effort.md:161](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-29-max-default-effort.md#L161).
No host or settings change follows from this retirement. The user's “test
before changing” choice therefore still holds. No trial is required or
implied. The preserved pilot's absence of persistent-adoption authority
remains explicit. [452f7b14:blueprints/compaction-window-ab/preregistration.json:1079](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/preregistration.json#L1079)

## i. Reopen conditions

Either condition reopens the question:

1. **A new preregistration shows a window or threshold rule beating native A.**
   It must be written for the then-current Claude Code client on the
   destination, run through Harbor or Inspect, and be confirmatory with
   quality non-inferiority and a preregistered cost criterion. Independent
   review and freeze must precede launch. It must cite this retirement
   record and `452f7b14`, retain failed/incomplete attempts and keep unknown
   usage unknown. The source for the confirmation boundary is
   [452f7b14:blueprints/compaction-window-ab/preregistration.json:1079](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/preregistration.json#L1079); the upstream-harness boundary is the
   [standing rule](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-30-rule-text-every-layer.md#L34).
2. **A primary Anthropic source changes the default or recommends an earlier
   window.** Verify the installed client, its version's changelog and pinned
   source, then the official documentation for the destination's model and
   route. A changed lever or save scope alone does not prove a new
   recommendation.

A qualifying comparison overturns the standing choice through its recorded
confirmatory result; this retirement supplies no automatic trial or
installation.

## j. Superseded pointers

The following references now resolve to this record and its
[reopen conditions](#i-reopen-conditions). The dated documents and existing
PR bodies remain historical text; this section supplies their resolution.
Only the three living community-practice rows are edited.

| Source at retirement base | References covered | Resolution |
| --- | --- | --- |
| [token-spend-attribution](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-29-token-spend-attribution.md#L15) | lines 15, 70, 81 | Its #416 ownership/“decides” wording now points to this retirement and section i |
| [ecosystem-roadmap](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-28-ecosystem-roadmap.md#L227) | line 227 | The “after Gate A” item is retired; reopening follows section i |
| [community-sweep](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-28-community-sweep.md#L192) | lines 192, 269, 326, 327, 513, 522, 544, 550 | Covers M3/KC-01, SIZE-07, source/ownership history and the compaction-count handoff. No historical count becomes a new sanitized receipt |
| [community-native-practice](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/community-native-practice.md#L191) | lines 191, 192, 201 (four #416 phrases across three rows) | Their living window-question and overturn pointers link directly to section i; source pins and other cells stay unchanged |
| [PR #453](https://github.com/seathatflowsinourveins/native-agent-stack/pull/453) | body line 16 | Its claim that #416 decides M3/KC-01 is superseded by this record |
| [PR #500](https://github.com/seathatflowsinourveins/native-agent-stack/pull/500) | body line 48 | Its native compaction-window entry resolves to this record |

The remaining two hits from
`git grep -n -E '#416\b' origin/main -- docs scripts` are historical
and remain as written:

- [docs/harness-defaults.md:122](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/harness-defaults.md#L122): the registry-CI anti-pattern row
  (line 121 in the earlier contract snapshot, now line 122).
- [scripts/git-hooks/pre-push:6](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/scripts/git-hooks/pre-push#L6): the historical reason for the
  pre-push registry gate.

This covers every hit in that read of main, including historical-only hits;
the search does not edit or authorize another custodian's PR body.

## k. Kept citations

PR [#488](https://github.com/seathatflowsinourveins/native-agent-stack/pull/488) at
`caea04f28d7dcd5d428155cf1a24b28423cba1ce` (`caea04f2`)
cites #416 and `452f7b14` at all of these retained locations:

| Artifact at caea04f2 | Lines |
| --- | --- |
| [blueprints/gate-b-gpt6-route/PREREGISTRATION.md](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/PREREGISTRATION.md#L17) | 17, 532, 560, 707, 709, 729 |
| [blueprints/gate-b-gpt6-route/preregistration.json](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/blueprints/gate-b-gpt6-route/preregistration.json#L1736) | 1736, 1803, 4105, 4110, 4137 |
| [tests/test_gate_b_gpt6_route_preregistration.py](https://github.com/seathatflowsinourveins/native-agent-stack/blob/caea04f28d7dcd5d428155cf1a24b28423cba1ce/tests/test_gate_b_gpt6_route_preregistration.py#L4) | 4 |

Their fail-first, amendment-rule and test reference-seam citations remain resolvable through
`refs/pull/416/head` and the preserved branch, including
[452f7b14:blueprints/compaction-window-ab/preregistration.json:1078](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/blueprints/compaction-window-ab/preregistration.json#L1078) and
[452f7b14:tests/test_compaction_window_ab_preregistration.py:1](https://github.com/seathatflowsinourveins/native-agent-stack/blob/452f7b14715ae2a038c1d4a98e292b5de7812c87/tests/test_compaction_window_ab_preregistration.py#L1).
The “open PR head” wording at #488's line 17 belongs to #488's custodian to
change after closure. This record changes no #488 file, branch, comment or
PR state.

## SOTA sources

All retirement source reads below are dated **2026-10-03**. The installed
client returned **Claude Code 2.1.288**; native help exposes the auto-compaction
launch flag and settings-source controls. These are installation/help
observations, not a model run.

- [Anthropic model configuration, “Set the auto-compact window”](https://code.claude.com/docs/en/model-config#set-the-auto-compact-window)
  and [“Default auto-compact thresholds”](https://code.claude.com/docs/en/model-config#default-auto-compact-thresholds):
  the native 1M Anthropic-API default remains about 967K. Version 2.1.288
  changes per-model saving; it does not supply an earlier-window recommendation
  for this route.
- [Anthropic environment-variable reference](https://code.claude.com/docs/en/env-vars):
  documents window precedence, modifiers and live settings-environment
  application. Removing a saved variable does not unset it in an already
  running session.
- [anthropics/claude-code v2.1.288 CHANGELOG](https://github.com/anthropics/claude-code/blob/1c229fcd1e1e4e452e29a8f116b45fe4cfe2c528/CHANGELOG.md),
  fetched with `gh api`, commit
  `1c229fcd1e1e4e452e29a8f116b45fe4cfe2c528`: entries
  **2.1.284, 2.1.285, 2.1.286, 2.1.287 and 2.1.288**, read in full.
  The per-model save change, compaction/resume repairs, and expanded
  provider/gateway 1M defaults do not change the documented native
  Anthropic-API default above.
- [docs/decisions/2026-09-28-community-sweep.md:522](https://github.com/seathatflowsinourveins/native-agent-stack/blob/9b0b8d6d25f9e3fb8f71770500e774170423315e/docs/decisions/2026-09-28-community-sweep.md#L522):
  the dated source synthesis says the draft was not frozen/run and that it
  found no primary Opus 5.5 quality-versus-context-length measurement.
  This is that sweep's bounded finding, not a new universal absence claim.
- The seven pinned #416 artifacts and the #488 citation sites above:
  independently read complete original bytes, with all seven SHA-256/byte
  identities measured for this record.

No new runtime, installation or test runner is adopted. The alternatives and
the comparison that would overturn retirement are in sections g and i.

Completeness critic: the unit checked the native client/help, versioned
changelog, official lever/default documentation, unchanged PR refs, historical
observed/relayed distinctions, launch/accounting gates, all main pointers and
the downstream citation class. The next current-client sweep must include
per-model saved-window precedence, route-dependent defaults, Workflow
inheritance, retry/TTL/lag accounting and confirmatory quality/cost evidence.
Those are future comparison requirements, not grounds for a trial here.
