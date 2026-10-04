# Reconcile the foundation Agents SDK and gateway descriptions

Date: 2026-10-03. Scope: build contract C2, foundation catalog metadata at
base dcae68bd08a191f37ba564eceda9fc4a9d6d4a6e. North-star action: give
complex engineering and US-equities research/historical-simulation workers
accurate account, SDK and gateway prerequisites without promoting an
unmeasured runtime or transferring historical acceptance to another host.

## Decision and alternatives

Keep every current OpenAI Agents SDK candidate row unqualified, and add the
missing agent-sdks candidate and foundation-layer description. Retain
the 2026-10-02 Codex-practice audit item AD-5, hold on Agents SDK codex_tool
adoption. AD-5 is the audit's bounded decision to leave the experimental
extension unadopted until a needed orchestration capability and its measured
candidate comparison qualify it; the resolvable comparison source is
catalogs/sota-convergence/manifest-20260926.json:451. The alternatives were
preserving the contradictory conditional/unqualified labels or promoting
the extension on source compatibility alone. Neither supplies the missing
application requirement and measured qualification.

Correction, 2026-10-03 (coordinator, before merge): the native-clients
layer's `alternatives[2]` text (the API-backed premise), its
`overturn_protocol.arms` and its `verdict_overturn_when` are fields of the
frozen layer-verdict row of wave 20260922
(`catalogs/sota-convergence/layer-verdicts-20260922.json`). Hosted
`validate` ("Check layer-verdict generator output is current") and
`verdict-review-gate` ("1 changed row(s), 1 violation(s)") refused the
first head `226f0794` because a frozen row may change only when it is
re-recorded under a new run id with a sealed cross-family review
(`tools/sota-convergence/build_verdicts.py`, `scripts/verdict_review_gate.py`).
This PR therefore leaves those three fields byte-identical to main. Their
premise correction and the codex_tool overturn arm are carried forward as
an open item for that re-record: the next native-clients/agent-sdks verdict
wave, which also covers the 28 fit refutations in
evidence/artifacts/landscape-sweep-20260926/returns.json#/votes where the
Claude vote did not refute but the GPT-6 vote was missing and counted as
refuted. Until then the frozen row's wording stands as recorded,
and this record and the corrected candidate rows state the accurate
premise.

The earlier repair registered the six-candidate agent-sdks collection with
`python3 scripts/catalog_decisions.py --write --supplement
catalogs/landscape/foundation.json#/layers/16/candidates`, so the new layer
entry participates in the validated repository decision union. This added
six layer-16 references, changing `counts.references` from 2045 to 2051 in
catalogs/us-equities/decision-index.json. Registration supplies no SDK
adoption or execution evidence.

Replace the foundation gateway's September 27 build description with the
two dated workstation build observations below. Retaining the replaced
build or describing the clean npm package as either patched deployment
would obscure their source and effort differences. This changes catalog
wording only; it supplies no new host, gateway, SDK or model acceptance.

## DD-1 verification and correction

Both conflicting dispositions and the blanket API-backed/native-account
premise still exist at the assigned base. The closure assessment's
native-clients entry in
evidence/artifacts/layer-closure-assessment-20261001/foundation.json
already flags the discrepancy. The missing OpenAI Agents SDK entry also
still holds in both catalogs' agent-sdks layer.

The [managed Agents API overview](https://developers.openai.com/api/docs/guides/agents-api/overview),
fetched as Markdown on 2026-10-03, specifies API-rate billing at line 15
and Bearer OPENAI_API_KEY authentication at lines 297-298. That is a
different surface from the open-source Python SDK.

At openai/openai-agents-python v0.23.1,
[CodexExec](https://github.com/openai/openai-agents-python/blob/v0.23.1/src/agents/extensions/experimental/codex/exec.py#L48-L63)
resolves a local executable and builds a Codex exec invocation.
[_build_env](https://github.com/openai/openai-agents-python/blob/v0.23.1/src/agents/extensions/experimental/codex/exec.py#L226-L240)
copies the inherited environment by default and sets CODEX_API_KEY only
when one is passed. R641 correction, 2026-10-03: that function alone does
not establish the tool's authentication. At
[tool key resolution](https://github.com/openai/openai-agents-python/blob/v0.23.1/src/agents/extensions/experimental/codex/codex_tool.py#L584-L628),
an explicit `codex_options.api_key` wins. Otherwise the tool resolves
`CODEX_API_KEY` or `OPENAI_API_KEY` from `options.env`, then the process
environment, then the SDK default set by `set_default_openai_key`.
[Thread forwarding](https://github.com/openai/openai-agents-python/blob/v0.23.1/src/agents/extensions/experimental/codex/thread.py#L108-L111)
passes that key to CodexExec, which exports it as `CODEX_API_KEY`.
The native Codex login applies only when no key resolves, or when the
caller [supplies a Codex instance](https://github.com/openai/openai-agents-python/blob/v0.23.1/src/agents/extensions/experimental/codex/codex_tool.py#L631-L639)
without `api_key` and preserves the instance's native authentication
environment/configuration. A key on the orchestrator can therefore select
API-key authentication for its Codex tool even without an explicit tool
key override. The SDK's
[endpoint configuration](https://github.com/openai/openai-agents-python/blob/v0.23.1/docs/config.md#L84-L88)
supports OPENAI_BASE_URL for an OpenAI-compatible endpoint. These source
capabilities do not measure whether OmniRoute accepts the SDK's actual
requests, nor do they transfer Codex entitlement to an orchestrating model.

The tagged [tool documentation](https://github.com/openai/openai-agents-python/blob/v0.23.1/docs/tools.md#L890-L894)
still classifies codex_tool as experimental. The defined audit hold remains.
Adoption
requires a needed orchestration capability, graduation from experimental,
and an accepted newly preregistered comparison of Agents SDK codex_tool,
the Codex thread API and codex exec --json plus resume, following the
comparison design in catalogs/sota-convergence/manifest-20260926.json:451.
The comparison must account
for complete usage, events, external effects, cancellation and recovery.
It stays separate from the sealed workers comparison of native Claude
CLI, the Codex SDK via native_worker.py and the Claude Agent SDK. That
layer-default verdict changes only through a re-preregistered rerun, as
recorded in docs/grand-catalog-handbook.md's agent-sdks narrative. Neither
this candidate comparison design nor these metadata edits change the
frozen wave-20260922 layer-verdict rows.
No installation or comparison is authorized by this documentation repair.

The audit's assertion that the foundation manifest still cites table
lines 78-84 no longer holds: its agent-sdks description already cites the
October 2 two-host decision. The closure assessment identifies four copies:
catalogs/landscape/foundation.json's agent-sdks rationale,
catalogs/foundation/decisions.json's agent-sdk-runtime-selection next_gap,
catalogs/foundation/manifest.json's agent-sdks next_gap, and
catalogs/landscape/research-state.json's agent-sdks next_action. The
landscape rationale was corrected in C2; R641 corrects the two remaining
stale copies in decisions.json and research-state.json. All three now
cite the header at line 80 and candidate rows 82-86 of
docs/foundation-closure-20260921.md and record the 2026-10-03 source revisit.
The manifest copy was already clean at the assigned base. The historical
table still has five other SDK/runtime candidates and no OpenAI Agents SDK
row; the source revisit supplies no new execution.

The September 26 return at
evidence/artifacts/landscape-sweep-20260926/returns.json#/votes/native-clients/1/fit
contains a Claude refutation and a missing GPT-6 fit vote, explicitly
counted as refuted under its either-family rule. It is a single-family
substantive fit judgment with missing-vote provenance, not a completed
two-family vote. The returns, saturation-ledger reference and dated
sota-convergence manifest remain unchanged. No new vote is claimed, and
their historical comparison baseline is not repinned by this task.

The new agent-sdks candidate also cites the completed two-family fit return
at evidence/artifacts/landscape-sweep-20260926/returns.json#/votes/agent-sdks/6/fit.
Claude refuted at confidence 0.72 using the managed API's key/billing
premise, which this correction no longer generalizes to the local SDK.
GPT-6 refuted at 0.99 and explicitly rejected that generalization while
challenging the proposed isolation outcome. Correcting the authentication
premise does not qualify the candidate or remove the orchestration,
experimental-status and measured-comparison hold. Both historical returns
retain their original votes and provenance.

## DD-2 verification and correction

The catalog's September 27 #14904 build description still holds as a
drift. The
[September 30 rebuild decision](2026-09-30-omniroute-rebuild.md)
records its replacements and the later #15167 carry. PR #637's
[October 3 pin decision](https://github.com/seathatflowsinourveins/native-agent-stack/blob/269f9516883b/docs/decisions/2026-10-03-omniroute-3851-pin.md)
was read with gh api at the contract's exact revision and records:

| Port | Build | BUILD_SHA |
| --- | --- | --- |
| 20128 | omniroute-3.8.51-2f42a9ac-pr13788-affinity2-pr15167 | cf6748d04 |
| 20129 | omniroute-3.8.51-2f42a9ac-pr13788 | 87c4c488d |

Both bases are
[2f42a9ac19d1a247ec9ce5473b790843724b3061](https://github.com/diegosouzapw/OmniRoute/commit/2f42a9ac19d1a247ec9ce5473b790843724b3061),
with the same tree as released v3.8.51 commit
[c1e30b7676975feb298b49eff6ff58923c04b89e](https://github.com/diegosouzapw/OmniRoute/commit/c1e30b7676975feb298b49eff6ff58923c04b89e).
Fresh GitHub git-commit reads at both pins returned tree
`0f58d8df20c0c2ae4336b432b3f39837119b6eed`.
Both deployments carry
[#13788](https://github.com/diegosouzapw/OmniRoute/pull/13788), whose
head is [6c7990058c4ce9677de79452c8cefb10b4bf1b3d](https://github.com/diegosouzapw/OmniRoute/commit/6c7990058c4ce9677de79452c8cefb10b4bf1b3d).
R641 correction, 2026-10-03: 20128 additionally carries the local affinity
patch and [#15167](https://github.com/diegosouzapw/OmniRoute/pull/15167)
cherry-picked from upstream head `f5d8e150b79e0901fa18241c7f29bff889b87c14`
into build `cf6748d04`, as retained in
[qualification-pipeline-times.txt](../../evidence/artifacts/omniroute-sol-max-20260930/checks/qualification-pipeline-times.txt)
lines 1-2 and
[omniroute.service.after-switch.txt](../../evidence/artifacts/omniroute-sol-max-20260930/checks/omniroute.service.after-switch.txt)
line 2. The PR's later force-pushed head
`0585aba5589d5a1f49243a13a8db249558e7c9e3` describes current upstream
state only. Fresh gh api reads on 2026-10-03 returned both PRs open;
the [pinned comparison](https://github.com/diegosouzapw/OmniRoute/compare/f5d8e150b79e0901fa18241c7f29bff889b87c14...0585aba5589d5a1f49243a13a8db249558e7c9e3)
returned `diverged`, with the later commit dated 2026-09-30T10:20:42Z.
A PR's current head does not identify the deployed cherry-pick.

In the clean package's
[effort sets](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex/reasoningSuffix.ts#L11-L31),
gpt-6.1-sol is unlisted, so
[clampEffort](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex.ts#L315-L340)
caps it at xhigh. PR #15167's
[carried sets](https://github.com/diegosouzapw/OmniRoute/blob/f5d8e150b79e0901fa18241c7f29bff889b87c14/open-sse/executors/codex/reasoningSuffix.ts#L11-L33)
include gpt-6.1-sol, preserving requested max. The fetched
reasoningSuffix.ts at that pin and the
[current upstream state](https://github.com/diegosouzapw/OmniRoute/blob/0585aba5589d5a1f49243a13a8db249558e7c9e3/open-sse/executors/codex/reasoningSuffix.ts#L11-L33)
are byte-identical (SHA256
`e6709380c42b76fe115861df83afc9a00be64bba3e5fdf615ec910094d5901c9`). The
[wire mapping](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex.ts#L1401-L1442)
maps ultra to max. The audit's separate October 2 Mac 3.8.52 observation
in docs/decisions/2026-10-02-omniroute-mac-rebuild.md does not replace
either named workstation observation or identify the clean release pin.
These are retained deployment observations plus source inspection, not
new acceptance or a fresh read of the running units.

## Retrieval corrections and completeness critic

The installed ai-memory 2.4.2 search help supports limit and project scope
but exposes no pin-first flag. Initial default-workspace searches returned
404 for this project. The verified recipe at recipes/README.md names
workspace local and project native-agent-stack; that scoped limit-2 query
and the exact read of decisions/omni-native-harness-resolution-20261001.md
succeeded. The page is historical evidence, and its conditional SDK label
does not supersede this correction. No memory page or client configuration
was changed.

Two patch attempts were refused by mismatched context: a trailing comma
was assumed on the native-clients object's final field, and a later
documentation patch assumed a different line break. Exact-source reads
resolved the contexts. The refused patches changed no bytes.

Initial acceptance retained three exit-1 results. Catalog validation
reported a stale decision-index disposition; the supported
scripts/catalog_decisions.py --write corrected the conditional-to-unqualified
reference. The supplement registration described above also added six
layer-16 references to the foundation-owned union (2045 to 2051).
Landscape and explorer checks rejected a changed current_choice that
differed from the quality catalog's incumbent choice. That choice remains
unchanged, with the held SDK added as a candidate and described in the
foundation manifest instead. These initial failures are historical worker
reports, not fresh R641 check results. The 26 convergence records listed
in manifests/evidence.json#/convergence_records were checked for this
repair's changed-file artifact pins; none requires rebinding. The component
matrix and new-host grand list remained current without regeneration.

R641 retained one refused patch before any bytes changed: its manifest
context assumed a trailing comma on the final field. The first candidate
edit then made verdict_review_gate.py exit 1 because landscape.py requires
canonical repository file paths in evidence_refs, rejecting a JSON pointer
fragment. The corrected candidate registers returns.json as the file and
locates /votes/agent-sdks/6/fit in its rationale. Both frozen-verdict checks
then passed with zero changed rows and zero violations. The failed attempt
and the contract's final command outputs are retained in the repair handoff.

The bounded completeness critic checked managed API versus open-source
SDK, explicit keys and the tool's full default key-resolution chain,
provided Codex instances, orchestrator versus Codex authentication,
experimental status, both layer-specific fit returns and missing sweep
votes, all four table citations, the newly preregistered candidate
comparison versus the sealed workers comparison, clean package versus
each carried deployment, carried PR head versus its later force-push and
build identity, and Mac versus workstation scope. Pinned upstream SDK and
gateway reads succeeded in R641; the other reviewer's network failures
were verification gaps and did not require a content change. The next
native-clients/agent-sdks landscape sweep
should verify experimental graduation and endpoint request compatibility;
the next gateway sweep should check whether a clean release incorporates
#13788/#15167 and supports the exact gpt-6.1-sol effort. Neither task is
started here. The anti-pattern log records both corrected premises.

Overturn the SDK hold only with the capability and measured comparison
above. Revise the gateway observations only against a newer owned
deployment record and its canonical source. Rollback is limited to these
catalog/documentation edits and their hash registrations. The contract's
offline checks and three pre-push registry tests establish repository
consistency only; their command results are reported in the worker handoff.
