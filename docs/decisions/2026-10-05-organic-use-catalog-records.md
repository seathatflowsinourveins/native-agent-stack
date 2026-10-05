---
status: proposed
date: 2026-10-05
decision-makers: [command center]
consulted: [grand-catalog, convergence-practice]
informed: [ns2604-coop]
review_by: 2027-01-03
---

# Preserve organic-use observations in the existing catalog evidence chain

## Context and Problem Statement

The catalogs preserve selections, source reviews, host lifecycle acceptance and
convergence sweeps. Those records do not establish whether a client selects a
component during ordinary work. The current organic pilot also cannot establish
that from a successful process exit: exposure, provenance, completed use and
native telemetry joins still need reconciliation by the run owner.

The requested durable record serves future foundation qualification and the
US-equities research and historical-simulation north star. It lets a later
session revisit the observation when a client, component or landscape changes,
without changing readiness or treating observation as upstream acceptance.

## Decision Drivers

- Preserve protocol `organic-e2e-v1-20261005` and amendment U1, with exact source
  hashes and bounded proof locators.
- Keep client runtime cells, versions, models, effective effort, configuration,
  native/env arms and P1/P2 phases separate.
- Reuse registered receipts, the existing schema helper, matrix generator,
  freshness reporter and append-only saturation ledger.
- Keep incomplete telemetry unknown and all conclusions reviewable.

## Considered Options

1. An optional `data.organic_use` block in an immutable registered
   `historical_inventory` receipt, joined informationally into the matrix and
   existing recheck reports.
2. Put observations into host lifecycle `use` receipts or convergence
   `in_use`/`invoke` values.
3. A separate catalog, runner, statistics calculator or validator executable.

## Decision Outcome

Propose option 1. Existing receipt metadata, integrity registration and component
IDs remain authoritative for the join. The optional schema is
[`organic-use.schema.json`](../../catalogs/landscape/organic-use.schema.json).
`scripts/validate.py` calls the existing schema-validation helper for the optional
block and checks its declared protocol boundaries. The draft creates no native
execution, statistics implementation or acceptance stage.

Each record retains its canonical stack component ID, layer scope, observed tool
pin, client cell, platform, arm, observation-window end, process run IDs/dates,
proof refs/hashes, evidence class and review/adjudication state. An unverified
tool pin, effective effort or configuration identity stays null. Pending P1,
P2 and pooled metrics and the verdict stay null. A terminal process rc is
process metadata; it is not an exposure, selection, use or successful native
test. Client version statements in this initial inventory come from U1's launch
record, and still require the run owner's exact telemetry join. `protocol_status`
preserves the protocol's intermediate screening, observed, wiring, unavailable,
unknown and deferred vocabulary separately from the final organic-protocol
verdict. The initial source inventory reports U1's Codex Serena availability gap;
that intermediate statement is not a pilot verdict.

Completed metric cells retain the denominator breakdown and explicitly identify
the valid exposed `should_use` denominator (`eligible_exposed`). Selection counts
include denied or failed model requests; completed successful task-organic uses
are a separate count. Discovery, instructed canaries, prompted requests and hook
rewrites cannot become organic uses. R1 provenance and negative-control proof
must be retained. OIR and selection rate use this cell's denominator; Wilson 95%
bounds are stored from the owner's native analysis with their provenance, never
recomputed here. Breakdown categories are not assumed to partition all trials.
`context_proof` links the complete owner manifest of task/instance identity,
frozen label vectors, suite, detectors, grader, provenance strata,
negative/task-outcome and telemetry controls, and usage/cost (unknown stays
unknown). Completed qualification must cite T6; storing an interval does not
substitute the out-of-v1 T8 rate policy.

Final verdicts are `READY`, `NOT-READY` or `EXCLUDED`. Pilot inventories issue no
verdicts. U1 makes native-arm evidence the organic gate for model-chosen slots;
env is comparison evidence. `READY` needs completed qualification, independent
review and adjudication under the dated method. This optional record cannot
change catalog acceptance, convergence scores or aggregate readiness. Official
readiness remains the command center's separate dated verified-E2E result.

`EXCLUDED` additionally needs the command center's rule (c) record for this
client: never selected unprompted in the full run, a selected covering component
for the same task class, and one upstream-native routing fix with an unchanged
rerun. Its overturn conditions are later organic selection, regression of the
covering tool, or an upstream-harness comparison favoring the excluded tool.
An uncovered task-class gap supports `NOT-READY` after the fix round; it does not
support exclusion. A schema-valid reference is a declaration to review, not
proof that the referenced judgment is true.

The generated matrix retains records under their declared layer scope, including
alternatives; each keeps its canonical stack ID and never binds acceptance to a winner. Source
receipt hashes and review states remain visible. Existing convergence `in_use`
means adoption decisions and `invoke` remains under its existing evidence gate.

Rechecks bind the observed tool pin, client version and scoped landscape/sweep.
The existing freshness reporter surfaces changed tool/client versions, a later
recorded landscape reopen and age beyond the record's explicit limit. Use its
existing 30-day default as an observational recheck limit, not a protocol
qualification threshold. Age starts at the observation-window end, not the
receipt publication date. Missing inputs mean not checked. Catalog client
versions are labelled as declared targets; an owner can supply current versions
with `--client-version ID=VERSION` without changing host configuration. The
report's `assess_organic` API also accepts owner-supplied model, mode, effective
effort/tier, route and configuration identities keyed by exact observation block
reference, so a client's arms and runtime cells are not pooled. Missing current context cannot
be treated as a matching binding.

The saturation report maps these signals to existing `pin_moved`,
`comparison_changed` and `stale_receipt` reopen categories. A real subsequent
sweep retains them in its `reopen[]`; the draft appends no fictitious sweep and
does not rewrite earlier hash chains. Clock-dependent freshness stays outside
deterministic matrix generation.

A re-observation is a new immutable registered record with a `supersedes`
reference to the exact earlier block and its receipt hash. Only a single scoped,
reviewed/adjudicated qualified successor with a known current binding can
discharge its predecessor's current trigger; pending successors, forks and
missing context cannot. Older flags and verdicts stay visible in the report.
Ordinary host receipts cannot clear an organic recheck. A fresh record cannot
erase a durable reset already retained in the ledger. Only baseline selected
component/layer placements raise current saturation triggers; unmapped organic
signals remain informational.

### Consequences

The record format can evolve with measured organic evidence while preserving
earlier failures and cells. The initial pilot inventory remains incomplete:
run-owner telemetry reconciliation, provenance classification, metrics, full
qualification, independent review and adjudication are pending. The
convergence-practice Q9 review confirms option 1's carrier and requests six
semantic boundaries; this draft incorporates them and requests an implementation
re-read. The owner has not approved these implementation changes yet.

### Confirmation

Run the existing publication validator and the touched schema, matrix, freshness
and saturation tests, then the matrix generator's check. These are local
structural/integration checks, not upstream acceptance or organic qualification.
Keep the registry commit last and the PR a draft for command-center review.

## Pros and Cons of the Options

### Optional registered observation

Reuses integrity and discovery paths, preserves unknowns and avoids changing
acceptance semantics. It needs a small typed block and informational joins.

### Host lifecycle or convergence metric

Reuses existing names but changes their meanings and could overstate adoption or
upstream acceptance. Reject this option unless an independently reviewed change
to those meanings and a measured qualification supports it.

### Separate system

Could collect more telemetry, but duplicates current registry, schema and report
capabilities. A demonstrated missing capability with a maintained upstream
solution would overturn this rejection; no such gap is established here.

## More Information

Extension sources, verified unchanged at the integration base `9e955327`:
`native-agent-stack@1796303f:catalogs/README.md:8,25`;
`scripts/validate.py:432–461`; `scripts/host_receipts.py:308–318,359`;
`scripts/component_matrix.py:79–102,356–393,866`;
`scripts/receipt_staleness.py:7,29–39,60`;
`scripts/saturation_ledger.py:1453–1494`;
`catalogs/saturation/README.md:136–146`.

JSON shape follows the existing Draft 2020-12 dialect and its
[type semantics](https://json-schema.org/draft/2020-12/json-schema-validation#section-6.1.1).
This record uses [MADR 4.0.0's template](https://github.com/adr/madr/blob/4.0.0/template/adr-template.md).
Its review deadline is within 90 days.

The sanitized [pilot source inventory](../../evidence/receipts/ns2604-organic-use-pilot-20261005.json)
retains source hashes and exact protocol pointers: protocol `1154e174` at
`/metrics/0–1,9`, `/decisions/1`, `/pilot`; suite `cd26427a`; U1 `db3ca7e1`
lines 15–20 and 61; command-center rule (c) `668362fe` lines 27–36.
Private originals remain with the run owner. This digest preserves declared
method and process metadata without publishing raw prompts, conversations,
credential files or host configuration. Independent verification of those
originals remains an explicit review step.
