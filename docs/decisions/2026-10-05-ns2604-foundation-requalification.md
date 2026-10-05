# NativeStack2604 foundation re-qualification, 2026-10-05

## Decision and north-star action

Publish the retained 2026-10-05 evidence as a documentary re-qualification,
with the last fully adjudicated baseline and the new provisional scenarios
shown separately. This serves complex engineering, US-equities research and
historical simulation before independently qualified paper operation.

The earlier co-op **40/80** and conditional **44/80** scenarios are superseded.
The cited roadmap proposes **37/80**; the command center reports **32/80,
provisional, pending the coordinator's final verified E2E**. Both figures are
recorded source-review proposals, not an aggregate derived or qualified by
this publication. The command center's correction excludes ccusage,
command-output, native-clients/codex, session-analytics and alerting from READY.
Its source and the exact review objections are retained in
`evidence/artifacts/ns2604-requalification-20261005/review-715-corrections.json`.

The last fully adjudicated aggregate remains the historical **30/80 (37.5%)**
from 2026-10-04, reported as 38% after half-up rounding in PR #700. That record
has 18 READY and 12 BY_DESIGN slots. Its labels stay intact in the new slot
artifact, beside today's observations. It is not a new 2026-10-05 acceptance
run. Official readiness stays **30/80** until the command center's own dated,
final verified E2E of the same 80 slots, followed by independent review and
adjudication. A review of this PR or its public projection does not lift
provisional status. The generated correction sets current/conditional values to
null with this decision as its pointer. Its earlier #713 ownership hold ended
when #713 landed as1796303f. The publication is reconciled with current main
9e955327; older coupled projections supply no current readiness authority.

## Sources and reuse

The repository's maintained evidence procedure and generators are the selected
reference implementations. No new acceptance runner, dependency, installation
or model trial is introduced. Sources are:

- [PR #700](https://github.com/seathatflowsinourveins/native-agent-stack/pull/700),
  merged as `76647ef0bfd5a52dce97234a93a0b8bc802fd92b`,
  `evidence/artifacts/ns2604-e2e-20261004/method.md` and `slots.json`: the frozen
  slot inventory, aggregation formula, executor/reviewer/adjudication boundaries
  and original status chains.
- [PR #704](https://github.com/seathatflowsinourveins/native-agent-stack/pull/704),
  merged as `4c897418fe35a030a1188ae447eaf31c893f8eff`,
  `evidence/artifacts/new-wsl-fix-wave-20261004/README.md` and
  `evidence/artifacts/new-wsl-install-plan-20261002/SOURCES.md`: source-backed
  plan repairs and per-component upstream commands. Plan repair is not host
  execution; `docs/decisions/2026-10-04-2604-e2e-fix-wave.md:15` explicitly
  records every revised destination command as UNRUN at that pin.
- `seathatflowsinourveins/native-agent-stack@4c897418fe35a030a1188ae447eaf31c893f8eff:docs/acceptance-evidence-policy.md`,
  sections "Identify what each check proves" and "Preserve the returned result":
  native operations, local integrations, structural validation and independent
  observation remain distinct.
- `seathatflowsinourveins/native-agent-stack@4c897418fe35a030a1188ae447eaf31c893f8eff:scripts/build_new_wsl_handbook.py:676`
  and `:1033`: reuse the existing input hashing, source projection and rendering
  interface for a separate host-observation section. The builder's reference
  implementation is `scripts/build_ecosystem.py` at
  `20ea4ae23a18565676823b9e3a23541c2100bb39`, as its module header states.
- `seathatflowsinourveins/native-agent-stack@4c897418fe35a030a1188ae447eaf31c893f8eff:scripts/build_ecosystem.py:695`
  and `scripts/host_receipts.py:710`: use supported architecture fields, source
  citations, native builders and evidence registration.

Search-first selected the existing repository generators and evidence policy
as the exact match for this publication. Package registries and a new harness
are unnecessary because the task adds no executable capability. The installed
builder help, source and relevant tests define the supported interface.
Scoped ai-memory queries with `pin_first=true, limit=2`, then without pin
priority, returned unrelated observability sessions rather than a maintained
re-qualification decision; the exact current repository sources govern here.

## Method and evidence classes

Use the PR #700 denominator of 80 foundation slots. Readiness is
`(READY + BY_DESIGN) / 80`. PARTIAL, FAIL, INTERIM and UNJUDGED contribute zero.
BY_DESIGN records an intentional disposition, not evidence that its tool ran.
Keep failed attempts, repeated attempts and omitted stages. A census row is
an attempt; it is not a unique slot or a whole-slot readiness judgment.

Each of the 80 entries in
[`slots.json`](../../evidence/artifacts/ns2604-requalification-20261005/slots.json)
retains its historical label and separates native stage observations from
model review and missing proof. Original source hashes are in
[`sources.json`](../../evidence/artifacts/ns2604-requalification-20261005/sources.json).
The public projection and its source mapping are reviewable without publishing
raw conversations or host paths.

| Claim | Evidence class | Boundary |
| --- | --- | --- |
| Retained native client command outputs | `native_proven` | The client command, host, revision and result actually retained; not whole-slot acceptance |
| Plan-wrapper census/stage checks and locally authored probes | `local_integration` | Our integration only; not unchanged upstream tests |
| Opus/GPT judgments and drift review | `source_review` | Review of retained evidence; not independent execution |
| Earlier 40/80 and 44/80 projections | superseded reported scenarios | Historical proposals retained; not current readiness |
| Roadmap 37/80 and CC 32/80 proposals | `source_review`, provisional | Reported figures only; coordinator's final verified E2E remains pending |
| Early invocation snapshot | `historical_inventory` | Install exposure window and native counter scope only |
| Skipped stages or missing raw proof | `none_recorded` | No successful operation inferred |
| Generators, hashes, tests and validator | `structural_validation` | Publication consistency; not host or provider acceptance |

No new unchanged upstream test is claimed. Publication does not run host
acceptance, sign-in, provider inference, GPU or paper-trading operations.
Retained evidence is reused rather than replayed and relabelled as a new run.

## Observations, disagreements and corrections

At `3e343ba6c7fc391a54f8780c87df65231f24c276`, the post-install census retained
80 attempts: 50 exit-zero, 28 skipped, session-analytics exit 127 and Collector
exit 1. Six after-sign-in attempts returned zero; local-model-server was not
run. Eight service-health attempts included seven zero exits and a
local-model-server failure. These censuses demonstrate their stages only.
Later raw observations at `4c897418f` include a repeated skill-authoring attempt;
81 raw rows must not be reported as 81 distinct slots. At the publication
boundary no persistent `fixwave-4c897418f` census exists in the co-op evidence
directory; recovery uses the selected original-source hashes.

Fresh Opus and GPT reviews disagree on exactly these four slots:

- `token-efficiency/code-index`
- `token-efficiency/command-output`
- `token-efficiency/output-compression`
- `token-efficiency/repo-packing`

Opus's READY and GPT's PARTIAL labels are source-review results. The missing
upstream/native acceptance and the local-fixture boundary remain visible.
These are different from the four token slots held for PR #684 in the
historical PR #700 record; `context-supply` is not one of today's four disputes.
Some fresh GPT-lane READY labels cover only the Codex leg. Those labels do not
prove the complete native-client or whole-slot contract.

Publication correction: the first handbook adapter mistakenly used PR #700's
historical four-token hold list, substituting `context-supply` for today's
`repo-packing`. Its synthetic fixture shared that mistake. Running the native
builder against the real receipt failed with exit 1 and "needs the four disputed
token slots". The adapter and fixture now use the original 2026-10-05 Opus/GPT
disagreements; the negative control explicitly rejects the historical four.
Verification path: the hashed fresh review records in `sources.json`, the
four slot entries in `slots.json`, and the native handbook projection tests.

The independently checked drift record refuted D20's missing-skills claim:
the native initial listing contained 55 skills, and the later two-skill listing
was incremental. Verification path: `client-drift-3e343ba6.json:correction.D20`
and `clients-native-3e343ba6.json`, identified by hash in the source inventory.
The drift record's 21 original items include 20 Dxx verdict rows and C01,
whose drift disposition overlaps D02/D03. The 11 real-drift, eight by-design
and one refuted verifier categories cover those 20 Dxx rows. Six missed
candidates are another view; these are not summed into a new defect count.

The invocation baseline at 2026-10-05T01:37:41Z has 220 items and 107 never
invoked. Most token and interim MCP entries had about 38 minutes of exposure.
Their zero counters describe that install window, not a quality verdict.

The fixwave-defects and currency status files were read before publication.
Both lanes were in progress. Their repair and update plans are leads; this
record claims no accepted slot closure from them. A later currency move also
requires checking that an earlier receipt's inputs and pins still match.

## Alternatives and overturn condition

Retaining only the historical baseline would omit today's real native
observations. Promoting zero-exit census rows or selected model READY labels
would overstate the evidence. Publishing the provisional scenarios alongside
the unchanged baseline preserves useful progress and its actual limitations.

Only the command center's own new dated, final verified E2E of the same 80
slots, followed by independent review and adjudication, can replace the
official historical result. A PR/source-projection review alone cannot lift
provisional. The earlier 40/44 scenarios and current-plus-four calculation are
superseded; the reported roadmap37 and CC32 proposals are not derived here.
New failures, pin changes or client-leg limitations may lower a later qualified
result, so publication validation must not require monotonic readiness.

## Publication, rollback and remaining work

Register the sanitized receipt and artifacts, plus every changed registered
input, in the final shared-registry commit using `host_receipts.register_file`.
Regenerate the handbook, component matrix and grand list through their native
builders, and build the ignored ecosystem HTML to exercise the architecture
rendering. Keep historical architecture winner pins, evidence classes and
closure judgments intact; append dated host observations with source links.
No main checkout or host configuration is changed.

At the initial capture, two retained-source conflicts were open: session-analytics' later summary
claims success while its complete rerun exit files report failure, and later
output-only attempts lack exit/time siblings. Alerting's zero exit accompanies
an explicit `needs_user` sink disposition. The slot artifact preserves both
the reported claims and the stronger raw-attempt boundaries without inventing
a successful whole-slot acceptance. Later attempts and source corrections are
recorded separately in the documentary supplement below.

Independent source comparison checked all 513 originals: 512 matched and none
were missing. The research-harnesses after-sign-in stderr file had changed
after its capture hash was taken. That attempt lacks complete exit/end
records. Its original hash is preserved; the source manifest records the
changed snapshot explicitly and does not imply a recoverable immutable copy
or successful acceptance. This is another incomplete observation, not a
reason to regenerate a green receipt.

Local checks are reported in the PR and private lane status. Required validation
is `python3 scripts/validate.py`, the touched generator/registry tests and
native `--check` commands. They remain structural evidence. No new convergence
or merit winner is claimed, so this documentary publication does not replace
an experiment record or invent a completed convergence trial.

Rollback is reverting this publication PR. Host state and source selection
remain unaffected. The command center owns landing; this lane opens a
`lane:foundation` PR and never merges.

## Completeness critic and next sweep

Covered modalities: all 80 historical slots, today's native attempts,
duplicates, failures, skips, selected fresh client-leg reviews, four model
disagreements, drift refutation, early invocation exposure and generated
publication surfaces. Hash identity is not proof of successful execution.

An independent bounded completeness reader checked the PR #700 original
method, dated architecture notes, PR #704's destination-unrun declaration,
peer status files and the original private client/drift/invocation metadata.
It caught undated latest-release phrasing, now explicitly historical, and
clarified the overlapping C01 drift row. This source review verifies only
those documentary properties; it does not supply the missing whole-slot
qualification or lift the current scenarios' provisional status.

The same reader checked all 80 identifiers/labels and 1,088 normalized source
references, identified the mutable stderr capture, and clarified that wrapper
stage checks are local integration. Those findings were incorporated without
changing historical READY labels or claiming upstream acceptance.

Missing modalities: complete fresh whole-slot derivation; independent host
replication of unresolved operations; unchanged upstream token acceptance;
GPU/local-model acceptance after its authorized window; peer repair and
currency receipts with matching pins. None is filled by a local check.

The next foundation landscape sweep should target those specific evidence
gaps rather than reopen unrelated candidates. The skills sweep is keyed by
install, activate, recover and use lifecycle tasks: verify both clients'
carriers and actual skill invocation against native histories and published
upstream contracts. New source or candidate leads remain suggestions until
their evidence converges.

The completeness review also feeds two concrete next-sweep requirements:
freeze or recover incomplete mutable command outputs, and retain resolved
reviewer/provider model and effort metadata when a claim depends on that
identity. Requested gateway routes alone do not identify the resolved backend.

## Roadmap evidence supplement, 2026-10-05

The separately registered [documentary receipt](../../evidence/receipts/ns2604-roadmap-evidence-20261005.json)
refreshes retained per-slot proof for review. It preserves the original receipt
as an initial-capture record and leaves its generated projection intact while
PR #713 owns the overlapping catalog/generated paths. This is source evidence,
not a new qualification. Every roadmap status remains provisional pending the
command center's final verified E2E; an independent public-projection read alone
cannot qualify a new status or readiness figure.

The only authority for a new readiness number is the command center's final,
dated qualification of the same 80 slots with independent review and
adjudication: native-agent-stack@4c897418fe35a030a1188ae447eaf31c893f8eff:docs/decisions/2026-10-04-ns2604-verified-e2e.md:114–121.
The wf_cfa1d860-ebd roadmap's blind Claude/GPT analyses and Opus adjudication
are recorded as `source_review`. They do not establish upstream acceptance or
authorize adoption of the roadmap's projected readiness figures.

The earlier list of ten reported host-plan passes did not substantiate the
40/80 scenario. The same cited roadmap holds base-distribution, syft,
betterleaks and otel-collector-contrib at PARTIAL. It also demotes four
baseline-READY slots: claude-code to PARTIAL for incomplete wiring,
skill-discovery to FAIL after rc 5 at 08:05:08Z, and dagu and mise to PARTIAL
for version mismatches. These are roadmap source-review labels, not replacements
for the unchanged historical baseline or evidence of new upstream acceptance.

The command center's subsequent objections cover ccusage, command-output,
native-clients/codex, session-analytics and alerting. Its ruling says these do
not count READY; it does not assign new PARTIAL labels to all five. The earlier
token disputes and client-leg reviews stay intact, including the roadmap's
reported command-output READY and the earlier GPT PARTIAL. The old conditional
current-plus-four calculation is superseded rather than carried forward.

Ccusage remains open: its condition-absent controls at 07:28:59Z and 07:29:05Z
are reported only in analyst transcript T, not retained beside the passing runs
in this receipt. The dated criterion-(2) reading accepts retained pinned native
operations and upstream examples; the unrun suite is not an additional blanket
requirement. The missing condition-absent controls remain open. See
native-agent-stack@4c897418fe35a030a1188ae447eaf31c893f8eff:docs/acceptance-evidence-policy.md:42–53.

Session-analytics remains open despite retained successful metadata. Rerun2 has
stdout reporting 0 without process rc or start/end siblings. The 07:27
service.8yU0G1 timestamps come from the roadmap; its argv and process rc are not
retained. The idle-exit event and subsequent failed sweep remain. Required
follow-up is an owner-native idle-period rerun retaining argv, stdout/stderr,
process rc, start/end times, exact pin and original-output hashes. Reconciliation
of dated daemon states does not close that lifecycle qualification gate.

Alerting retains its initial exit-zero skip, later modified-network delivery,
and later cached unmodified pass as distinct attempts. The command center
confirms that the attestation is the user's own; the original receipt's
not_verified field remains historical. User authorship is no longer an open
authenticity question. Fresh unmodified delivery remains blocked by defect 14,
and the plan check's printed result line remains unconfirmed. The currency
owner's status still defers Codex profile work pending #713; it supplies no
owner acceptance closing D04. Neither defect is declared fixed here.

These corrections follow the original Claude review of #715 head ec7dbc2d0,
SHA-256 cf54816c12d77a705b1d278f332d18166bfc8e926e65c3ecaac7eb2921bde5c8,
and the command-center ruling at coordination-root:command-center/ITEM-ns2604-coop-20261005T114416Z.md:15–26,
SHA-256 a4b778fcc133cb3b4b479688815b6dc34a287dccbfe05a5c00c057ae0af2e375.
The correction artifact records their portable locators and original hashes;
no new aggregate, native run or review-lift trigger is created.

Job1's observation and tool records retain native operations, wrapper results,
fixtures and model judgments separately. Job2 carries documented BY_DESIGN
dispositions with their decision citations. Job3 retains memory's INTERIM
hold and corrects the skill-validator chronology without claiming fresh skill
creation/evaluation. Their exact proofs and limitations are in the receipt's
linked artifacts. No fresh alert, provider call, native test or session was
run for this supplement.

The builder correction uses the definitive code-navigation slots: Serena
provides symbols/references for both clients, and the official Claude LSP
plugins are not installed. Source:
native-agent-stack@4c897418fe35a030a1188ae447eaf31c893f8eff:docs/decisions/2026-10-01-new-wsl-definitive-defaults.md:68–69, :528.
The source patch and its local integration checks remain isolated until the
generated paths are released. Job4 waits for each slot's stages2–5, independent
review and adjudication; cite the #723 receipt only by its merged commit and
JSON path when available. Job5 waits for #713 to land.

## Dated reading of criterion 2 and custody/base rulings

The command center's 2026-10-05 reading of the frozen criterion 2 accepts an
unchanged pinned upstream test or a supported pinned upstream example/native
operation with its actual output retained. A plan check supplies that evidence
only when its body runs the applicable upstream operation. A version string or
wrapper's passing footer alone does not establish this condition. Require a
particular suite when the frozen slot explicitly names it. Preserve controls,
failed attempts, wiring and fresh-session use as separate requirements.

The [dated ruling record](../../evidence/artifacts/ns2604-requalification-20261005/dated-readiness-rulings.json)
applies this interpretation to all 17 affected slots together, names each
changed blocker and status, and keeps the original source-review labels beside
the reading. No previously READY slot is demoted solely because an upstream
suite was not run; removing a suite-only objection does not prove the other
three READY conditions. Worktrunk, skill-discovery and Git lose the interpretive
blocker. Git's retained version-only OPTIONS-line check still fails criterion 2.
Trace-viewer is the named-suite exception in this 17-slot pass: the frozen PR
#700 record names upstream `make test`, whose returned result is missing. Its
version-only plan smoke supplies no result or superseding adjudication. Source:
native-agent-stack@76647ef0bfd5a52dce97234a93a0b8bc802fd92b:evidence/artifacts/ns2604-e2e-20261004/slots.json:687,
and ymtdzzz/otel-tui@3b25779a083469b732e3c628b4a412ee05cf9948:Makefile:10–12.
Ccusage, Serena and MinerU need their retained condition-absent controls beside
the applicable passing operations. Their gaps remain open rather than being
filled by this documentary reading.

Credential custody's dated disposition is **BY_DESIGN**, replacing its prior
INTERIM policy hold. The drafted alternative retains one private 0600 file per
provider outside worktrees, pointer variables, value-free status checks, the
id-based runner and scoped client guards. It adds no dedicated custody product.
Native sign-ins remain in the clients' supported stores.
This is a documented scope choice, not inspection or acceptance of any credential
file. The systemd-creds comparison and custody changes 1–3 are superseded;
they no longer constitute planned work or a gate. The source for the existing
practice is native-agent-stack@c148e049efee75f8ea8a9a009e7b96b1e97f5c28:docs/secret-storage.md:3–10,
with the adopted ruling recorded at `coord:readiness-20261005/coordinator-rulings-20261005.md:17`.

Base distribution is **PARTIAL**, with the proposed INTERIM disposition rejected.
It is deployed and waits on G8's external upstream condition. Canonical's
unchanged systemd-assertions returned **exit 1**; an exception-bearing local plan
check that returned zero does not erase that upstream failure. Retain both
results. No protectBinfmt setting is changed or proposed by this publication.
Correction: the initial slot commentary called F1 an exception for an
intentionally stopped distribution. G8 instead permits exactly one binfmt failed
unit and its identifier-selected read-only flush diagnostic. Verification:
the G8 lines below and ubuntu/wsl-setup@73418e32bb48d514c2c2853fa7e5cacdcaf3dfe8:test/systemd-assertions.sh:6–8.
The unchanged upstream script returns exit 1 when `systemctl is-system-running`
reports any state other than the literal `running`, including a degraded state.
The gate's source is native-agent-stack@c148e049efee75f8ea8a9a009e7b96b1e97f5c28:docs/decisions/2026-10-04-2604-e2e-fix-wave-g8-base-gateway.md:28–35,
and the adopted ruling is `coord:readiness-20261005/coordinator-rulings-20261005.md:25`.

These are source-review dispositions pending the final verified qualification.
All 80 historical baseline labels, original attempts and review chains remain
unchanged. Official readiness remains 30/80; no aggregate is derived. Ruling 10
also keeps shared-host plan application with the co-op's readiness-runner lane.
This publication neither runs install.sh nor changes host configuration.

## Publication reconciliation after #713 landed

The 16:11Z co-op direction releases the previously recorded generated-path hold.
This publication now follows main9e955327702e6b7a8dd1909b2884196726a15ba5,
which contains #713 at1796303f, #705 at0ce95369 and #735 at095d4fad.
Earlier hold/unpublished-candidate descriptions in this dated record describe
the preceding preparation phase; they are not current publication gates.

Preserve main's owner/profile binding, browser replacement controls, wave-5
104-row catalog inventory and owner fields. The frozen readiness denominator
remains 80; the larger recommendation catalog does not change it. Main's winner
pins, destination-unaccepted qualifications and original generation history
remain intact. Append scoped historical observations and regenerate through the
existing builders. Restore main's evidence registry and re-register only this
lane's two receipts and changed files; registry is the final commit.

Main's plan/profile Dagu and Mise moves are #740 at
cb339488e3e004b04e8a4e5b4fd246442a275e3c, separately from #735's calendar
changes. The installed-host observations at4c897418 are historical and do not
qualify a changed plan/profile pin by replay. In particular, the plan's Dagu
v2.18.2 and Mise v2026.10.1 remain distinct from the deliberately held stack pin
and earlier host attempts. No fresh installation or acceptance is claimed.

Sources: native-agent-stack@9e955327702e6b7a8dd1909b2884196726a15ba5:scripts/build_new_wsl_handbook.py:811–831,
tests/test_new_wsl_handbook.py:243–263, :1046, :1158, :1233;
catalogs/foundation/new-wsl-architecture-20261001.json;
evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json#/owners/57
and #/owners/71; docs/lanes.md:94–128. The exact-head command-center Claude read
remains pending and cannot replace the final verified E2E. Official30/80 and
null current/conditional values remain; the reported32 proposal stays provisional.
