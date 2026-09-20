# Research-task acceptance for native Codex and Claude

The acceptance unit is a useful answer with correct sources and retained limits.
Hosted checks of schemas, hashes and constructed fixtures qualify those checks;
they do not establish native client activation, research quality or broker readiness.
Use the [evidence policy](acceptance-evidence-policy.md) and preserve failed attempts.

## Declared baseline and reusable measurements

Reuse the September 20 [frozen plan](../blueprints/us-equities/research-efficiency/plan.json),
[native receipt](../blueprints/us-equities/research-efficiency/native-receipt.json)
and [execution/usage instructions](../blueprints/us-equities/research-efficiency/README.md).
No model invocation was repeated for the GitHub automation change.

The baseline is all eight selected public documents from
`cb79080cf5d9510818c67ac51c521b1d2a1b80fe` (71,223 source bytes). The comparison
uses unchanged source IDs/text selected by QMD 2.8.3 BM25, at most two documents.
Questions, rubric and order were frozen before the eight native submissions.
Task A reconciles FB/META observations and historical eligibility. Task B
reconciles worker usage, cache subsets and selected-text reductions. These test
evidence reading relevant to both catalogs; neither is a trading strategy test.

Content acceptance requires at least 8/10, at least 3/4 required facts, and no
fabricated citation/value or false historical eligibility/net-savings claim.
Protocol acceptance additionally requires the frozen structure and at most 250
prose words. Independent blinded reviewers scored answers against the full corpus;
source availability was checked separately against each supplied packet.

| Native client / task | Full → focused elapsed seconds | Full → focused reported tokens | Full → focused content score | Both protocol passes |
| --- | ---: | ---: | ---: | --- |
| Codex / A | 19.780 → 18.854 | 38,102 → 22,691 | 10 → 10 | Yes |
| Codex / B | 20.950 → 17.751 | 38,130 → 25,069 | 10 → 9.5 | Yes |
| Claude / A | 10.578 → 14.893 | 44,595 → 20,136 | 9.5 → 10 | No: full answer 327 words |
| Claude / B | 12.846 → 16.558 | 45,652 → 24,562 | 9.5 → 9.5 | No: full answer 260 words |

Reliability in this small retained sample: 8/8 completed, 8/8 met the content
rubric, 6/8 met the whole answer contract; no invocation timed out. Report all
denominators and failures. Focused Claude answers took longer even though their
reported tokens were lower. Codex B lost half a content point. Two tasks per
provider do not establish population reliability, provider rankings or causality.

Six local QMD index/search/get operations took 607 ms, separate from model time.
Native totals include only the narrow answer runs, excluding coordinator,
preparation and review. Codex cached input and reasoning are already subsets of
input/output. Claude ordinary input, cache creation, cache reads and output are
distinct; exposed thinking is within output. Missing retry/usage fields stay null.
Client context, hooks and caches were not controlled; fresh sessions were not cold
caches. The two Claude baselines failed protocol, so those pairs cannot be called
accepted efficiency gains. No session, lifetime, dollar or general savings follow.

## Use on a future research task

1. Freeze a bounded question, source revisions, baseline packet, output contract,
   rubric, run order, existing native client/model settings, timeout and maximum
   submissions before execution. Include an answerable source-reconciliation task
   and a task that must preserve an unknown or rejected claim.
2. Check the native account is ready without reading/copying credential stores.
   Keep each provider separate. Preserve quota/authentication refusals; stop that
   provider's submissions instead of silently changing accounts or models.
3. Retain source bytes/hashes, actual command results, failures, durations and the
   single terminal usage aggregate. Keep private raw outputs outside publication.
4. Have an independent reader check cited claims against the pinned originals,
   then score completion, limits and format. A passing JSON schema alone does not
   establish any of these semantic properties.
5. Compare elapsed time and available usage only for matched tasks, while reporting
   every failed condition. Repeat only when changed inputs or a concrete hypothesis
   justify another authorized native run. Do not sum overlapping snapshots.

The existing experiment's `prepare`, `run`, `export-blind` and `review` procedure
is project-owned integration around supported QMD/native client interfaces, not an
upstream benchmarking feature. Use its [documented commands](../blueprints/us-equities/research-efficiency/README.md)
when that exact protocol fits; do not build a competing model harness in Actions.

## Automation acceptance and ownership

The existing daily Codex maintenance task owns upstream-change research. A bounded
pilot must identify a material change, cite pinned primary sources, distinguish
accepted from proposed revisions, explain affected tasks, and name matching
acceptance commands and rollback. A report is useful only when a reviewer can act
on it without guessing the source or qualification boundary. Record false positives,
missed scope, elapsed time and available usage; absent accounting remains unknown.

GitHub validates the proposal's artifacts and runs relevant hosted fixtures. The
native task owner qualifies actual local runtime behavior. NautilusTrader/IBKR
historical simulation and the separate Alpaca adapter retain independent data and
paper-operation gates. No model report, attestation or CI pass authorizes orders.

Maintenance owner: native foundation coordinator. Rollback: restore the previous
protocol/packet and retain the failed newer result; leave accepted runtime pins
unchanged. This guide adopts existing measurements, not new model execution.
