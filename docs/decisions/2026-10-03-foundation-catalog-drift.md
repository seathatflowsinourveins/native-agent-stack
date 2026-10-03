# Reconcile the foundation Agents SDK and gateway descriptions

Date: 2026-10-03. Scope: build contract C2, foundation catalog metadata at
base dcae68bd08a191f37ba564eceda9fc4a9d6d4a6e. North-star action: give
complex engineering and US-equities research/historical-simulation workers
accurate account, SDK and gateway prerequisites without promoting an
unmeasured runtime or transferring historical acceptance to another host.

## Decision and alternatives

Keep every current OpenAI Agents SDK row unqualified, add the missing
agent-sdks candidate and foundation-layer description, and correct the
native-client overturn arms. Retain the AD-5 hold on experimental
codex_tool adoption. The alternatives were preserving the contradictory
conditional/unqualified labels or promoting the extension on source
compatibility alone. Neither supplies the missing application requirement
and measured qualification.

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
when one is passed. Therefore the wrapper can use the existing local
Codex login; an explicit environment or key override can change that
behavior. The SDK's
[endpoint configuration](https://github.com/openai/openai-agents-python/blob/v0.23.1/docs/config.md#L84-L88)
supports OPENAI_BASE_URL for an OpenAI-compatible endpoint. These source
capabilities do not measure whether OmniRoute accepts the SDK's actual
requests, nor do they transfer Codex entitlement to an orchestrating model.

The tagged [tool documentation](https://github.com/openai/openai-agents-python/blob/v0.23.1/docs/tools.md#L890-L894)
still classifies codex_tool as experimental. AD-5 remains a hold. Adoption
requires a needed orchestration capability, graduation from experimental,
and an accepted frozen comparison of the Codex thread API, Agents SDK
codex_tool and codex exec --json plus resume. The comparison must account
for complete usage, events, external effects, cancellation and recovery.
No installation or comparison is authorized by this documentation repair.

The audit's assertion that the foundation manifest still cites table
lines 78-84 no longer holds: its agent-sdks description already cites the
October 2 two-host decision. The stale citation does remain in the
landscape's agent-sdks rationale and is corrected to rows 82-86 of
docs/foundation-closure-20260921.md (header at line 80). That table has
five other SDK/runtime candidates and no OpenAI Agents SDK row.

The September 26 return at
evidence/artifacts/landscape-sweep-20260926/returns.json#/votes/native-clients/1/fit
contains a Claude refutation and a missing GPT-6 fit vote, explicitly
counted as refuted under its either-family rule. It is a single-family
substantive fit judgment with missing-vote provenance, not a completed
two-family vote. The returns, saturation-ledger reference and dated
sota-convergence manifest remain unchanged. No new vote is claimed, and
their historical comparison baseline is not repinned by this task.

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

Both bases are 2f42a9ac19d1a247ec9ce5473b790843724b3061, with the same
tree as released v3.8.51 commit c1e30b7676975feb298b49eff6ff58923c04b89e.
Both deployments carry
[#13788](https://github.com/diegosouzapw/OmniRoute/pull/13788), whose
head is 6c7990058c4ce9677de79452c8cefb10b4bf1b3d; 20128 additionally
carries the local affinity patch and
[#15167](https://github.com/diegosouzapw/OmniRoute/pull/15167), whose
head is 0585aba5589d5a1f49243a13a8db249558e7c9e3. Fresh gh api reads
on 2026-10-03 returned both PRs open with those heads. A PR head is not
the deployed cherry-pick's BUILD_SHA.

In the clean package's
[effort sets](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex/reasoningSuffix.ts#L11-L31),
gpt-6.1-sol is unlisted, so
[clampEffort](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex.ts#L315-L340)
caps it at xhigh. PR #15167's
[pinned sets](https://github.com/diegosouzapw/OmniRoute/blob/0585aba5589d5a1f49243a13a8db249558e7c9e3/open-sse/executors/codex/reasoningSuffix.ts#L11-L33)
include gpt-6.1-sol, preserving requested max;
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
scripts/catalog_decisions.py --write regenerated its single changed
conditional-to-unqualified reference in the foundation-owned union.
Landscape and explorer checks rejected a changed current_choice that
differed from the quality catalog's incumbent choice. That choice remains
unchanged, with the held SDK added as a candidate and described in the
foundation manifest instead. Original logs retain those failures before
the corrected reruns. All 26 registered convergence records were checked
for changed-file artifact pins; none requires rebinding. The component
matrix and new-host grand list remained current without regeneration.

The bounded completeness critic checked managed API versus open-source
SDK, orchestrator versus Codex authentication, explicit environment/key
overrides, experimental status, missing sweep votes, clean package versus
each carried deployment, PR head versus build identity, and Mac versus
workstation scope. The next native-clients/agent-sdks landscape sweep
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
