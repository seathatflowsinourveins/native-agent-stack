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

## Addendum (2026-10-07): retained requirements, lessons and content folds

The current carrier also preserves the earlier convergence-practice review,
research-skill input pack, web-search observations and the cooperation,
credential-storage and lane lessons. Their original decision and evidence bytes
are retained; this publication supplies no new model run or runtime acceptance.
The seven discovery defects enter the anti-pattern log as additional rows, with
the existing log kept intact and related earlier corrections linked.

The twelve requirements in the retained October 2
[slot carrier](../../evidence/artifacts/new-wsl-final-architecture-20261002/added-slots/slots.json)
are now source-bound annotations on existing landscape parents. The projection
reuses `default_slot_inventory` and `read_manifest_sources` from
`native-agent-stack@8b844d37:scripts/build_new_wsl_handbook.py:443-490`.
Seven requirement IDs match native inventory IDs directly. Five new annotations
bridge requirement IDs to explicit job declarations in the retained
[native manifest](../../evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json),
at lines 1220-1234, 2539-2553, 2611-2625, 3210-3250 and 3433-3447.
The secret-scanning requirement keeps both distinct job references under the
same parent; no selected component, installation state or outcome chooses the
parent. Missing, ambiguous or contradictory identities refuse projection.

Each annotation retains the requirement text, source bytes' SHA-256, JSON pointer,
native parent provenance and any explicit job crosswalk. It creates no new layer
ID and changes no historical carrier or legacy ledger requirement hash. The
separate owner of versioned semantic binding controls that migration. A changed
source declaration or demonstrated parent mismatch overturns this mapping;
the offline controls check preservation and refusal, rather than merit or
candidate adoption. Future sweep seeds cover all twelve requirements.

Two completeness-critic claims are corrected alongside their originals. The
vendor pass's first hosting round had no survivor, while its completed follow-up
retained two hosting assessments. The claim that the V1 harness cannot represent
model-hub repositories is refuted by its existing URL schema, native Hub source
review path and two retained vendor-pass model proposals with their own returned
votes. These source corrections do not rewrite the original critic or outcomes;
model-slot and currency coverage remains a discovery requirement.

## Addendum (2026-10-07): host-bound gateway and upstream stdin transport

The existing harness now resolves its optional gateway against the host record
through the shared reviewed resolver block. Native-only staging reads no gateway
record. Primary and fallback gateway holders validate their staged endpoint and
lane-home configuration before spawning; the primary route also pins its endpoint
on the native command line. Deliberate alternatives retain an explicit reason.
The two copied resolver blocks bind to SHA-256
`e63090a57a5a58078fd019428fccdba75ffddbf5a1decc52d893e4848dbf4af3`.
Merge still requires the canonical resolver source and host-record predecessors,
plus the separately recorded real-client project-precedence controls.

Every future invocation explicitly disables apps, following installed Codex CLI
0.160.1's `--disable` flag and the official
[command reference](https://learn.chatgpt.com/docs/developer-commands).
Logical input identity records `apps: false`; primary gateway inputs additionally
bind the resolved endpoint, source and reason. Historical missing fields remain
unknown and unequal, with earlier attempts retained. A fresh native source-route
readback and smoke is still required before declaring shell/GitHub/context-mode
routes available inside an isolated job.

The real 32-layer input check found a complete discovery prompt of 169,926 bytes.
The old 120,000-byte refusal protected one argv string, rather than defining a
model context budget. The supported upstream alternative is `codex exec -`:
`openai/codex@rust-v0.160.1:codex-rs/exec/src/lib.rs:191-193,2252-2275,2288-2290`
reads stdin completely and returns its nonempty buffer without trimming.
The installed help and the exact tagged source were independently reread.

The runner therefore feeds the same previous UTF-8/universal-newline/LF-only
normalized bytes through stdin, using a private per-attempt file so deadline and
cancellation handling stays active. Raw prompt bytes and logical hashes stay
unchanged. Future transport receipts record delivered-byte count and SHA-256;
other subprocesses retain null stdin. The converter retains each receipt while
assigning failover limitations only to an actual native-to-gateway fallback.
No historical observation is edited, no input is clipped and no new content cap
is asserted without a source. A changed upstream stdin contract or a failed
byte-equivalence/control test overturns this transport choice.

The synthetic and source checks do not establish model or gateway acceptance.
Publication receives a delta read before the separate native full-input job;
project-precedence qualification and the later merged-code check remain distinct.

## Amendment (2026-10-07): owned detached gateway refusal accounting

The exact-head source review found that a gateway becoming invalid after
`start()` bound a fresh snapshot released the inherited lock without a terminal
receipt. The regression now reproduces that path, distinct from a valid endpoint
whose changed input identity was already handled. The original source and
verification record remain retained as the earlier observation.

An owned detached refusal now enters the existing configuration-error terminal
path: write its refusal cause, finish with exit 2 and `inputs_changed`, then release
the inherited lock. An initial or hand-run gateway refusal still raises before
creating a lock or receipt. Bound input bytes and earlier archived attempts are
unchanged, and neither a gateway probe nor a model process starts.

Source: `native-agent-stack@d466be191f2d6c4026530961a12360e8024843a9:tools/sota-convergence/landscape-sweep/codex_job.py:771-788,1055-1139,1380-1403`
and the existing race fixture in `tests/test_landscape_sweep_harness.py:2375`.
The new controlled race and filesystem-preservation checks verify local lifecycle
accounting, not upstream model or gateway acceptance. A future refusal path that
loses its terminal record or mutates retained inputs overturns this fix.

The current review direction schedules the separate native complete-input job
after this repair's push. Its returned output and native usage will be recorded
separately; source review, fixture passes and a missing hosted validation run do
not grant command-center acknowledgment or satisfy project-precedence proof.
