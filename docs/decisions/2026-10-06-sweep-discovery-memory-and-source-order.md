# Sweep discovery memory and source order — 2026-10-06

This decision improves foundation discovery for the north-star research and
historical simulation work. It changes inputs and instructions for future
sweeps. It does not change recorded sweep outcomes, select a runtime, install a
candidate or activate the pending version-2 runner.

## Evidence and alternatives

The existing input builder reads one last completed repository sweep, even when
that sweep did not cover the requested layer. Its novelty list uses the catalog
and baseline but omits that layer's earlier returned judgments. The ledger
already preserves those judgments and distinguishes a missing vote from a
returned refutation. Its policy sets K=3 for saturation counts; the owner now
also requires a K-derived discovery-memory window. These are different uses:
the discovery window has no clean-sweep or seven-day spacing requirement.

Sources: native-agent-stack@e28d0eec112527ac02659ac23753533b8ed39a73:
`tools/sota-convergence/landscape-sweep/build_inputs.py:151-171,618-658`;
`scripts/saturation_ledger.py:625-676,707-710`;
`catalogs/saturation/README.md:118-136`.

The maintained upstream client and APIs already supply repository redirects,
release lists and tag-prefix references. Replacing them with another transport,
discovery runtime or local comparison runner would not repair this missing
input projection. The selected approach extends the repository's existing
builder and frozen prompts; native transports and result schemas stay in use.

## DECIDED

| Topic | Selected practice | Alternative and condition that overturns this verdict |
| --- | --- | --- |
| Earlier judgments | Carry the last policy.K completed repository sweeps covering this exact layer, with original scope hashes and vote references. Keep the single-sweep compatibility field and baseline selection. A missing policy uses the ledger's existing default of three; an invalid supplied K is an error. | Retain one global sweep only if it can recover the same layer judgments across interleaved scopes. A demonstrated omission or an unbounded input expansion reopens the window design. |
| Official sources first | Inspect version-specific installed-client surfaces, then vendor and maintainer organization repositories and supported clean releases, before third-party proposals. Missing installed observations remain an explicit limit. | Start with third-party discovery only if current primary evidence establishes the official surface cannot meet this requirement. Popularity establishes no such gap. |
| Young repositories | Preserve the existing under-90-day warning and verify repository creation separately from maintenance and release dates. Age alone does not refute a candidate. | Change the warning only through an owner decision with evidence that another assessment interval better describes uncertainty. No new threshold is inferred from a release date. |
| Renames | Use official resolved identity for new proposals and preserve aliases and old observations. Reuse the native client rather than add redirect code. | A verified identity mismatch, including reuse of an old name, requires a fresh identity review; an unverified redirect remains unknown. |
| Release currency | Check the vendor-supported package train, using native release listings or declared tag-prefix references. A supported tag without a release is a tag-only observation with unknown publication date. | Use repository-wide latest only when primary documentation establishes one applicable train. Incomplete pagination or an unmatched package leaves currency unresolved. |
| Later dispositions | Carry exact layer-matching candidate and reconciliation observations from the supplied manifests, with document identity, date and pointers. Preserve conflicting observations. | Drop this projection only if another maintained input already carries the same current observations and provenance. Narrative kind/note values never authorize adoption or alter historical votes. |
| Model currency | Give model requirements an explicit review of current official model catalogs, release notes and cards, recording identity, revision, date and unresolved availability separately from runtime currency. | Omit this step only for requirements that use no models. A dated provider change or missing modality reopens the model-layer review. |

History is discovery context, not a permanent eligibility blacklist. A changed
requirement or platform hash makes an earlier vote a historical observation.
An absence-only outcome is not a merit refutation; the native absence helper's
false result also does not prove merit because unreadable references can return
false. Workers must reread a proposed candidate's own original vote and sources,
or state that they cannot verify them, before using a prior reason. Fresh primary
evidence and changed requirements remain valid reasons to reassess a candidate.

Version 2 keeps its neutral eligible field, identity hash and blind fit
projection. Neither this history nor an adoption observation changes admission,
ordering or burden. Its launch guard remains in force. An overturn condition
describes a future decision; catalog inclusion requires no local head-to-head,
trial matrix or A/B campaign and authorizes no such run.

## Primary sources

- [GitHub redirect guidance](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#follow-redirects) and [rename caveat](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository): resolved requests and possible reuse of the former name.
- [GitHub releases](https://docs.github.com/en/rest/releases/releases#get-the-latest-release): the latest endpoint is repository-wide and excludes drafts/prereleases; release publication and associated commit dates differ.
- [GitHub matching references](https://docs.github.com/en/rest/git/refs#list-matching-references): native prefix-scoped tag discovery, rather than a new release-discovery wrapper.
- native-agent-stack@e28d0eec112527ac02659ac23753533b8ed39a73:`tools/sota-convergence/github_freshness.py:420-478`: existing rename metadata, release/tag fallback, creation timestamp and matching tags.
- native-agent-stack@e28d0eec112527ac02659ac23753533b8ed39a73:`tools/sota-convergence/build_manifest.py:252-285,1953-1958`: publication uncertainty, flagging an unversioned tag and copying reconciliation observations.
- native-agent-stack@e28d0eec112527ac02659ac23753533b8ed39a73:`tools/sota-convergence/landscape-sweep/templates.json:2,11`: existing young-repository warning, primary model-card sources and neutral V2 policy.
- [ECC search-first at 2b6e839771e53096d8451a213d40dc64ec8acac0](https://github.com/affaan-m/ECC/blob/2b6e839771e53096d8451a213d40dc64ec8acac0/skills/search-first/SKILL.md): research and reuse before implementation.

## Evidence boundaries

The installed GPT Researcher gathered current-month leads for this unit. Its
report is not authority, and its broad provenance recommendations do not prove
these harness policies. The deciding API facts were reread in the primary docs
above; implementation facts were checked against exact repository source.
Source inspection is source_review. Upcoming fixture regressions and structural
validation will remain synthetic/local_integration evidence, not upstream
runtime acceptance or a new model-quality measurement. Unknown provider usage
remains unknown, and the gather's failed retrieval is retained privately.

## Verification addendum (2026-10-06)

The same focused regression failed against unchanged source at e28d0eec:
the layer's known list was empty instead of its two retained judgments. All
nine new synthetic regressions pass with the input projection. The existing
harness, ledger and contract suites pass: 423 tests run, four skipped.

The initial broader check exposed four failures. Expanded instructions exceeded
the existing 16,000-byte staging limit and moved three current template change
detectors. The instructions were shortened without raising the limit; native
prompt filling/hash functions regenerated current detectors, with their prior
values retained. Skills-specific templates remain unchanged, but shared facts
and fit text changes the skills run's frozen hash. The failed log and expanded
templates remain retained; no historical run hash or observation was rewritten.
The four focused repair checks and the broader rerun pass.

A source-review completeness critic accepted the bounded repair with limits:
the disposition join covers only the supplied manifests, history references
remain unverified context, and no future discovery-quality gain was measured.
Its next-sweep leads cover later decision/receipt carriers, non-GitHub official
distribution surfaces, observed source ordering and the size of retained input
context. Fixture omissions concerning source immutability and older lens-vote
history remain explicit follow-ups, not passed coverage.

The [verification carrier](../../evidence/artifacts/sweep-harness-discovery-20261006/verification.json)
keeps the failing control, failed conditions, passing checks and source hashes.
These results remain synthetic/local_integration evidence.

## Unknown-reference clarification addendum (2026-10-06)

The final source read found that a compressed instruction could require an
unavailable old vote before fresh adjudication. The instruction now explicitly
requires fresh adjudication when the old reference cannot be read. It also says
absence=false does not establish a merit judgment, rather than implying a
negative merit verdict. Native current detectors were regenerated with prior
values retained. The final 423-test regression run passes with four skips;
the unchanged nine history regressions retain their earlier passing evidence.
The [final verification carrier](../../evidence/artifacts/sweep-harness-discovery-20261006/verification-final.json)
extends the earlier observed phase without rewriting its source hashes or
results. The same source-review and synthetic-evidence limits apply.
