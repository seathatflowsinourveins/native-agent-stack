# NativeStack2604 foundation re-qualification, 2026-10-05

## Decision and north-star action

Publish the retained 2026-10-05 evidence as a documentary re-qualification,
with the last fully adjudicated baseline and the new provisional scenarios
shown separately. This serves complex engineering, US-equities research and
historical simulation before independently qualified paper operation.

The current scenario is **40/80 (50%), provisional**. The conditional scenario
is **44/80 (55%), provisional**, only if four disputed token slots adjudicate
READY. These are the co-op projections supplied in this lane's brief. The
available fresh records do not identify a complete 80-slot status chain or
the ten promotions deriving 40. Consequently this publication does not assert
that 40 independently qualified slots have been demonstrated.

The last fully adjudicated aggregate remains the historical **30/80 (37.5%)**
from 2026-10-04, reported as 38% after half-up rounding in PR #700. That record
has 18 READY and 12 BY_DESIGN slots. Its labels stay intact in the new slot
artifact, beside today's observations. It is not a new 2026-10-05 acceptance
run. The gap in the current projection must be closed before it becomes the
verified aggregate.

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
| 40/80 and 44/80 projections | supplied provisional scenarios | No complete fresh derivation or independent aggregate review retained |
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

Replace the provisional scenario with a verified aggregate only after an
independent reviewer retains the full 80-slot status chain, identifies every
baseline-to-current promotion and checks each slot against the frozen method.
Raise 40 to 44 only if the four disputed slots have source-backed native
acceptance and recorded adjudications under that same contract. New failures,
pin changes or client-leg limitations may instead lower the numerator.

## Publication, rollback and remaining work

Register the sanitized receipt and artifacts, plus every changed registered
input, in the final shared-registry commit using `host_receipts.register_file`.
Regenerate the handbook, component matrix and grand list through their native
builders, and build the ignored ecosystem HTML to exercise the architecture
rendering. Keep historical architecture winner pins, evidence classes and
closure judgments intact; append dated host observations with source links.
No main checkout or host configuration is changed.

Two retained-source conflicts remain open: session-analytics' later summary
claims success while its complete rerun exit files report failure, and later
output-only attempts lack exit/time siblings. Alerting's zero exit accompanies
an explicit `needs_user` sink disposition. The slot artifact preserves both
the reported claims and the stronger raw-attempt boundaries without inventing
a successful whole-slot acceptance.

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
