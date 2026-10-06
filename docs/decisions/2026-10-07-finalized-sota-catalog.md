---
status: proposed
date: 2026-10-07
decision-makers: [command-center]
review_by: 2027-01-05
---

# Finalized foundation catalog: publication structure

This is the decision-record skeleton for the command center's forthcoming
adoption synthesis. It selects no repository, changes no installed tool or
broker gate, and derives no readiness count. Its dated October 7 title names
the planned publication record; preparation occurred on October 6.

The catalog supports US-equities research and historical simulation through
the native foundation. Its [north-star boundary](../../blueprints/us-equities/AGENTS.md)
keeps research, simulation, paper and live acceptance separate.

## Context and decision drivers

The existing foundation catalog describes broad capabilities. Its research
decisions deliberately allow one repository to appear in multiple layers.
That remains useful discovery and historical evidence, but does not establish
one current default per narrowly defined role or exclusive repository ownership.

The publication needs one default per finalized slot, one owning slot per
included canonical repository, explicit official release identities, and
separate evidence classes. Shared dependencies and multi-language interfaces
must not create competing repository assignments. Historical outcomes and
dated exclusions remain visible.

## Proposed structure

The existing [foundation manifest](../../catalogs/foundation/manifest.json)
links a [current projection](../../catalogs/foundation/finalized-sota-catalog.json)
through the optional `finalized_selection_file` field. The projection starts
at `pending_synthesis`, with an unknown repository census (`null`) and empty
repository selections. Its 78 proposed roles span the existing 20 layers;
these are taxonomy counts, not installed tools or READY slots.

The command center's synthesis may coalesce roles before finalization. In
particular, a monorepo providing several SDK languages has one owning slot
with `supported_languages` facets. Another slot's `references` are dependency
or interface links, not ownership declarations. A practice without a repository
requires an explicit source/owner decision; no repository identity is invented.

After synthesis, `included_repositories` is an independent canonical census.
Each `slots[].repositories[]` record names a repository and selects exactly
one of `default`, `alternative` or `excluded`. Every finalized slot has one
default, and every included repository has one owner across all three kinds.
References may repeat, but must resolve into that census. A missing owner is
an error even when all declared owners are unique.

The scoped check extends the existing foundation and publication validators.
It does not change the research catalog's intentional cross-layer overlap and
does not add a validator executable, installation step or acceptance runner.
It verifies declared consistency; it does not prove external evidence true.

## Default record fields to populate from synthesis

| Field | Canonical carrier and publication requirement |
| --- | --- |
| Functional slot and languages | Current projection's `id`, `layer_id`, `role`, `purpose` and language facets; define the consumer and boundary before selecting a default. |
| Official source and release | Link `manifests/stack.json` component/source identities and registered primary provenance. Verify the vendor's own repository, clean release pin, commit and publication date together. Latest-release metadata cannot date a different selected pin. |
| Evidence classes | Link original registered receipts and their scoped classes. Installed/smoked, organic observations, source review, synthetic checks and independent observations remain distinct. |
| Installed and smoked | Actual returned per-consuming-client operation, version/source binding, exit or native completion status, output and retained failure conditions. |
| Organic counters | Link the canonical owner's protocol record per client and native/env arm, with trials, uses, OIR/interval, selection rate, run IDs and dates. Preserve unknown/deferred states. A named smoke supplies none of these counters. |
| Facts and fit refuters | Four explicit role/family scopes: facts and fit from Claude, and facts and fit from GPT. Retain source pin, artifact locator and original returned result for each. A dual-lane label alone does not establish these scopes. |
| Owner audit grade | A dated source-review lead with its origin and limitations; it is neither independent refutation nor native acceptance. |
| Alternates and exclusions | One owning slot per canonical repository, original evidence/decision references, dated reason and conditions that would overturn the exclusion. |
| Overturn comparison | Link the existing landscape comparison's fixture, metric, arms and decision-changing trigger. |
| Supersession | Link the prior decision/receipt at a stable pin; retain its original scope and failed outcomes. Never sum overlapping usage. |

The current-main snapshot does not contain #750's organic carrier. Until its
canonical implementation and the owner's qualified records are available, the
projection records that evidence as missing rather than replacing it with a
host smoke or a zero. The existing saturation ledger's facts/fit references
also need explicit family-role declarations from the new synthesis.

## Alternatives considered

- Replace legacy research overlap with global uniqueness: rejected because it
  erases valid capability references and changes historical discovery semantics.
- Put structured evidence into current layer strings: rejected because it hides
  joins and bypasses the exact-field schema rather than extending it explicitly.
- Add a separate runner or dependency: unnecessary; the existing canonical
  repository identities, duplicate-key reader, validators and unit framework
  already cover the declaration check.

## First-pass draft #804

[#804](https://github.com/seathatflowsinourveins/native-agent-stack/pull/804)
remains the convergence owner's first-pass publication. Its observed draft
head was `8b844d37ac7f89b116d69f86681d06f5d4dc7791` on October 6. Its dated
manifests, source-review receipts, votes, failed attempts, usage and exclusions
retain their original scope. Vendor-official follow-up and synthesis remain
with their owner.

The finalized catalog folds qualified references from the three sweep inputs
after the command center's adoption synthesis. It supersedes first-pass
recommendation status only through a new dated record; it does not rewrite
the old outcomes, close #804 or claim that a draft vote establishes acceptance.
Before final publication, use #804's eventual merged commit and exact source
path/JSON pointer for retained inputs.

## Pending acceptance and consequences

The current PR prepares only structure and a deterministic declaration check.
It remains a draft. The command center supplies the synthesis; exact-head
cross-family review, CI and the command center's ACK precede the sole lander's
queue. Publication and installation are separate actions.

Open items: actual defaults and complete repository census; official selected
release proof; four family-role refutations; canonical organic records;
language/monorepo coalescing; non-repository practice dispositions; #804's
stable publication pin. No open item is silently marked complete.

## Comparison that would overturn this structure

Reopen if a qualified synthesis cannot represent one repository's necessary
interfaces without losing language or workload coverage, if an independently
declared census exposes an unowned repository, or if an existing upstream
catalog format supplies these joins and consistency checks more clearly.
Compare complete source/evidence recovery and deterministic counterexamples,
while preserving historical and organic evidence classes.

## SOTA sources

- `seathatflowsinourveins/native-agent-stack@e28d0eec112527ac02659ac23753533b8ed39a73:scripts/validate_foundation.py:50-53,74-93,135-147`: existing exact-field foundation schema and canonical joins.
- At the same pin, `scripts/validate_catalogs.py:110-127,156-186,253-272,362-368`: canonical repository identity, alias normalization and duplicate-key rejection.
- At the same pin, `tests/test_catalogs.py:199-207`: intentional research overlap retained.
- At the same pin, `scripts/validate.py:405-461,484-485`: publication references/hashes and the existing entrypoint extended by this draft.
- At the same pin, `catalogs/landscape/README.md:75-102`, `catalogs/saturation/ledger.schema.json:27-59` and `docs/acceptance-evidence-policy.md:26-33`: alternatives, overturn comparisons, scoped votes and evidence boundaries.
- [Python JSON duplicate-key hooks](https://docs.python.org/3.13/library/json.html#json.load), [sets](https://docs.python.org/3.13/library/stdtypes.html#set-types-set-frozenset), and [JSON Schema uniqueItems](https://json-schema.org/draft/2020-12/json-schema-validation#section-6.4.3): reuse existing identity/key checks; whole-object uniqueness alone cannot establish exclusive ownership.
