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

## Addendum (2026-10-07): synthesis inputs and verification method

The following inputs are required for the adoption synthesis. A pending locator
is an open input, not a missing observation treated as a zero. Private artifacts
must acquire a sanitized, registered publication reference before a finalized
record can cite them; workflow identifiers alone do not establish their results.

| Input | Artifact locator or explicit pending publication reference | Scope |
| --- | --- | --- |
| First-pass landscape sweep 1 | Pending: the convergence owner supplies the first sweep's exact path, JSON pointer and stable commit from #804's retained inputs. | Candidate discovery and dated source observations; no installation claim. |
| First-pass landscape sweep 2 | Pending: the convergence owner supplies the second sweep's exact path, JSON pointer and stable commit from #804's retained inputs. | Separate first-pass evidence, with its own failures and limitations. |
| Vendor-official follow-up | `wf_62ccd24a-231`; pending sanitized registered artifact locator. | Recheck the vendor's repository, selected release and source identity rather than accepting discovery metadata. |
| AUDIT-SEEDS follow-up | Pending: the convergence owner supplies the AUDIT-SEEDS artifact and its pinned source references. | Follow missing candidates and modalities; retain gaps that are not resolved. |
| Owner audit | Pending: the dated audit's registered artifact locator. | A lead only, with origin and limitations; it supplies neither a family-role refutation nor native acceptance. |
| Install, wiring and client-smoke observations | `manifests/evidence.json`; pending exact receipt IDs and scoped original output references for each selected component and consuming client. | Verify the declared native integration and returned operation separately from source review or a synthetic fixture. |
| Organic counters | Pending: qualified per-client native/env protocol references and the dated invoke-rate dashboard report. | Retain trials, uses, selection rate, intervals, dates and unknown/deferred states; a directed smoke is not organic use. |
| Grand-manifest gather | `wf_4d706751-ca6`; pending sanitized registered artifact locator. | Reconcile repository ownership, slot boundaries, shared interfaces and the independently declared census. |

The command center performs adversarial verification against the selected
primary sources and original returned artifacts. It preserves four separate
refutation roles: Claude facts, Claude fit, GPT facts and GPT fit. It checks
release identity and evidence scope before joining a result to a recommendation.
Any disagreement, unavailable input, retained failure or missing client scope
remains visible; the synthesis does not manufacture a completed observation.

A completeness critic follows that verification. It checks missed vendor
repositories, candidate classes, modalities, language interfaces and consumers,
then feeds unresolved findings into the next scoped landscape sweep. The
command center records adjudication and the comparison that would overturn
each selection. Defaults and the complete census remain pending until that
work supplies their canonical references; this addendum selects none.

The declaration contract reuses the repository's exact-key validators and
canonical evidence carriers. Required fields, explicit dispositions and resolved
references constrain what a finalized declaration may claim; validation remains
a consistency check, not proof that an external observation is true.

## Addendum (2026-10-07): enforceable declaration fields

The projection document and every slot reject unknown or missing required
fields. Every repository declaration carries `repository`, `selection`,
`component_ids`, `adoption_status`, `source`, `evidence_classes`,
`install_smoke`, `organic`, `refutations`, `audit`, `exclusion`, `overturn`
and `supersedes`. Evidence carriers declare their disposition explicitly;
unknown or deferred evidence is not a completed result. Finalized publication
describes a recommendation; an adopted status needs its additional evidence.

A default's component references resolve to the canonical component source
and matching repository/pin. An alternative or exclusion can instead bind
the canonical research record and its specific source origin; this does not
promote it into the installed stack. A public-star discovery reference alone
cannot supply a release identity, native operation or audit outcome.

Release references join the selected repository, tag/version, commit,
publication date and clean-release metadata. A different latest release's
date cannot be used to date the selected pin. Evidence references resolve
registered bytes and the original payload's identity, class and scope. Native
host receipts remain usable when registered as files without an aggregate
receipt entry; when both exist their metadata must agree.

Facts and fit remain four separately bound Claude/GPT family-role judgments.
The owner audit is a dated lead with explicit limitations. Exclusions need a
dated reason and overturn conditions; comparisons and supersession retain
their scoped, stable references. A fabricated generic organic payload cannot
stand in for the canonical owner's missing carrier or qualify adoption.

Implementation sources at
`seathatflowsinourveins/native-agent-stack@6fc39660d458824b7aaf0827d1c6d3ea0ae73453`:

- `scripts/catalog_decisions.py:110-150,178-203,224-239`: canonical research identities and origin references.
- `manifests/landscape.json:5-14,355` and `scripts/landscape.py:1368-1381`: concrete release metadata and matching selected identity.
- `scripts/validate.py:397-424,454-490`, `adoption/host-receipt.schema.json:127-184` and `scripts/host_receipts.py:204-232,1240-1291,1420-1428,1696-1702`: registered source bytes, original receipt metadata, scoped native operations and pin agreement.
- `scripts/saturation_ledger.py:315-326,350-354,436-481,538-555,740-778,1250-1267`: retained family-role judgments, source identities and resolved registered pointers.
- `scripts/validate_foundation.py:313-328` and `docs/acceptance-evidence-policy.md:26-33,42-63`: dated scoped supersession and evidence-class boundaries.
- [RFC 6901, sections 3, 4 and 7](https://www.rfc-editor.org/rfc/rfc6901.txt) and [JSON Schema 2020-12 required fields](https://json-schema.org/draft/2020-12/json-schema-validation#section-6.5.3): pointer resolution and required declarations, reused through the existing native validators.

An optional slot `task_scope` maps an organic workload to the owner's canonical
record; each organic cell states that scope or an explicit unresolved value.
Native host envelopes are read through their existing component/version
adapter. An original operation without client or role coverage remains an
`observed` result and cannot establish adoption. Refuter observations likewise
remain useful without qualifying the current selection: recorded qualification
needs the original requirement's hash-bound repository, pin, commit and role.
Historical superseded references bind the prior decision's identity, pin and
scope; retained failures are not tested against today's selected pin.

## Amendment (2026-10-07): terminal management and deployed context

`terminal-management` is a fourth native-clients role. The two client roles
and model gateway do not cover terminal presentation or lane PTY/session
lifecycle. This adds one role to the original 78-role scaffold: 79 proposed
roles across 20 layers, with empty selections and a null census. This taxonomy
count is separate from any native qualification or readiness count.

The [new terminal-context receipt](../../evidence/receipts/ns2604-terminal-catalog-context-20261007.json)
keeps the reported deployment, installed-command observations and prospective
candidates separate. The current deployment report is the command center's
October 7 item, lines 12–18; September 28 measurements retain their original
NativeStack host scope. The reported deployed configuration is:

| Facet | Deployed context | Evidence boundary |
| --- | --- | --- |
| Terminal frontend | Windows Terminal 1.24, with program-controlled titles, escalation-only bells and Claude's 24-bit colour through the profile `environment` key. | CC-reported current configuration under the September 28 policy; no new visual or sound acceptance by this lane. |
| Lane PTYs and controls | hcom 0.7.27 with tmux 3.6; hcom's TUI dashboard, `hcom kill` and `hcom term`. | Installed help/version confirms the interfaces and versions; the retained orchestration record describes prior operations separately. |
| Claude session inventory | `claude agents --json`. | Installed Claude 2.1.292 documents the active interactive/background-session JSON inventory; this record performs no live inventory or session dispatch. |
| Tab lifecycle | The command center's owner-maintained relaunch scripts, including `lane-relaunch.sh` and its wave/window callers. | Source references only; this lane does not execute or publish host-specific launcher contents. |

These are facets of the deployed arrangement, not competing default repository
assignments. The synthesis must assign each repository one owner and use
non-owning dependency/interface references for the remaining facets.

Claude Code 2.1.292's background sessions and agent view remain a synthesis
candidate: the dated feature check records `ENABLED_UNUSED` and `ADOPT_LATER`,
not adoption. Its proposed bounded comparison is for worker sessions only,
excluding command-center and co-op sessions, against the existing terminal-tab
and owned-worktree route. Resolve `worktree.bgIsolation` before that comparison
and retain Worktrunk's ownership and hook behavior in both arms.
Background workflow runs do not wait out usage limits; retain that restriction
when assessing the worker comparison.
WezTerm and zellij retain the September 28 no-documented-gap disposition; reopen
their comparison only for a demonstrated gap. Windows Terminal's toast work
in #20010–#20012 is a watch item for release verification, not a feature claimed
in the deployed 1.24 pin.

The installed tmux 3.6 backend is retained as an observed deployment fact. Its
official release is dated 2025-11-26, while current upstream 3.7c is dated
2026-08-17. The old backend exceeds the 180-day current-release guideline;
currency and the owner must qualify any replacement through upstream tests
and the actual hcom/client route. This record makes no pin move or upgrade.

Sources: `native-agent-stack@fbb202239fb28d84078494216427e1a0722d2b86:docs/decisions/2026-09-28-terminal-experience.md:10,32-44,48-82,292`;
`docs/decisions/2026-10-06-hcom-relaxation.md:60,84` at that pin;
[Windows Terminal v1.24.11911.0](https://github.com/microsoft/terminal/releases/tag/v1.24.11911.0),
[hcom v0.7.27](https://github.com/aannoo/hcom/releases/tag/v0.7.27) and its
[pinned README](https://github.com/aannoo/hcom/blob/2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b/README.md#L282),
[tmux 3.6](https://github.com/tmux/tmux/releases/tag/3.6) and
[3.7c](https://github.com/tmux/tmux/releases/tag/3.7c).
The receipt retains sanitized locators and hashes for the CC deployment item,
the feature check, orchestration observations and owner launcher sources.

## Amendment (2026-10-07): vendor-native wiring before adoption

The catalog's `installed_and_smoked` concept maps to the existing per-client
`install_smoke` carrier. It now requires the whole integration chain: the
vendor's documented path at the selected pin; retained, value-free installed
readback for that path; any required gap correction through its owner; and one
fresh-session operation per client whose task prompt does not name the tool.
Vendor-provided routing instructions remain part of native integration;
additional task instructions cannot force the tested tool into use.

`organic_use` maps to the existing `organic` carrier and its canonical owner
qualification. It additionally needs the invoke-rate owner's completed daily
report after installation, wiring and both fresh smokes. The report must match
the selected component, pin, consumer, functional scope and actual integration
channel. A hook-based integration needs hook executions; MCP call totals cannot
supply that evidence. Directed requests, smoke-harness runs and other exclusions
must stay separate from counted organic invocations.

A version check, visible registration or instruction line alone cannot establish
adoption. A vendor-documented instruction path is valid when its installed
readback, implicit-use smoke and daily evidence resolve. A measured zero is an
adoption defect to investigate, not a default reason to exclude a tool. Missing
telemetry remains unknown, rather than a measured zero or a completed result.

The dashboard's owner must supply the working-day coverage policy and report.
The checker binds their measured interval and completion to those source records,
after both smoke completions; a later report-generation timestamp or an isolated
completion boolean is insufficient. This catalog adds no universal duration or
OIR threshold. Until that owner carrier exists, the daily qualification stays
unknown or deferred and cannot authorize an `adopted` declaration.

The current committed dashboard counts tool-result and MCP event families.
The future hook counters and daily Dagu report remain owner plans, not executed
qualification. The overnight 22:40Z–00:42Z snapshot is separate from the required
completed working-day evidence. Operational wiring, client restart-window
application, fresh client smokes and daily collection stay with their assigned
owners; this amendment changes the declaration contract only.

Sources at `native-agent-stack@96d0979fa1b7c92d98f0e6d791ae25a5bb047625`:
`scripts/validate_foundation.py:307-373,510-571`,
`scripts/validate_convergence.py:102-105,124-142`,
`tools/skill-usage/skill_usage.py:2163,2251-2254`,
`tools/skill-usage/README.md:163,623`, and
`observability/backends/templates/ecosystem-dashboard.json.example:613,657,701`.
The CC method is `coordination:command-center/ITEM-ns2604-coop-20261007T005140Z.md:16-21,33`,
SHA256 `bbf0ace2829ba9ffb051f53445a1ce8a1ff3eafe16339a0a82d9d2563a109d0e`.
The invoke-rate owner's prospective plan is
`coordination:ns2604-coop/notes/dispatch-20261006T1915Z/invoke-rates-overlap-token.md:12,21,29`,
SHA256 `d7d12d5604b5c3d372d6a782968ac342188f979d07f03fc73ba3ee9f46f1e8e4`.

Known integration records bind vendor-required registration identities to the
names-only readback and bind returned native-path events to the fresh smoke's
consumer, context and output. State readbacks keep their local integration
class; they do not become upstream acceptance. Daily qualification resolves
the owner's original working-day definition, its qualified origin and observed
coverage, plus the selected invocation map and native emitter. Raw counter
sources retain their original classes and report membership; synthetic counts
or a copied channel label cannot qualify adoption. Emitter documentation must
match a known canonical client source pin. An unresolved version/source mapping
remains unqualified until the owner supplies a supported pinned source identity;
the current carrier does not manufacture that mapping from a documentation URL.

## Amendment (2026-10-07): Original judgment provenance

The source review of #820 at `77d35e41911c0f8c28a5561790cd8d8a8cd68175`
found that recorded dispositions and credible vote screens alone allowed
synthetic original judgments to qualify a refutation. Qualification must also
resolve the inherited evidence class of every counted original judgment.
Synthetic or unresolved original provenance remains a non-qualifying observation,
including when one such original is mixed with otherwise qualifying originals.
A nested positive declaration cannot erase a synthetic ancestor's provenance.

Keep the frozen selection input's class separate from the original judgments'
classes. Registered, hash-resolved original-judgment provenance supplies the
declared source class; the canonical screen still checks identities, roles,
families, frozen inputs and retained votes. Structural acceptance of a positive
fixture verifies this declared contract, not actual adoption or the truth of a
review. Pending and observed carriers remain valid without becoming adopted.

The new
[`repair receipt`](../../evidence/receipts/ns2604-catalog-fix2-20261007.json)
links the prior controls and fold receipts without rewriting their recorded
observations. Selections remain pending synthesis.

Sources: `native-agent-stack@77d35e41911c0f8c28a5561790cd8d8a8cd68175:scripts/validate_foundation.py:123-144,702-753,877`
and `scripts/saturation_ledger.py:439-495`; the same pin's
`docs/acceptance-evidence-policy.md:26-33,42-69` defines the synthetic,
source-review and structural-validation claim boundaries.
