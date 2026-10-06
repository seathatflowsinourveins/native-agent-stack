---
status: accepted
date: 2026-10-06
decision-makers: user, command center
---

# Worker defaults select the NativeStack2604 gateway

The command center reported that NativeStack and NativeStack2604 share WSL
networking and that NativeStack uses loopback ports 20128 and 20129. The
canonical install-plan topology assigns NativeStack2604's gateway to
`http://127.0.0.1:21128/v1`. A worker's implicit 20128 default could therefore
select the other distribution's service. This fix serves the north-star action
of routing bounded foundation/trading engineering jobs to their intended host.

Both standalone Python examples read the checked-out plan's nonsecret
`config/gpt-gateway-topology.json` field `gateway.endpoint`. This follows A46's
checked-out topology path and the existing native Promptfoo endpoint reader.
It avoids depending on a separate installed/client-configuration copy. Missing,
malformed or legacy-20128 topology defaults fall back to 21128. The candidate
uses the Codex worker's existing port-qualified HTTP loopback `/v1` contract.
Explicit `--base-url` overrides retain their existing behavior. DeepAgents'
configuration description reports the selected default as its underlying lane.

The alternative was replacing the two literals alone. Reading the canonical
field keeps future approved topology changes in one place while retaining a
portable fallback for copies of the examples without that asset. The skill's
bounded-job invocations pass 21128 explicitly as the command center requested;
the two example README default descriptions match the implemented selection.
Historical trial plans and receipts keep their original addresses.

Four fixture tests execute the actual Codex argument parser and DeepAgents
configuration-description branch with inert SDK/provider imports. They cover
canonical and missing topology, a configured alternate endpoint, explicit
overrides, legacy 20128 and malformed JSON/URL fields. Provider/runtime
constructors are forbidden in those tests. This is local/synthetic
configuration evidence, not native provider acceptance.

Two existing cases also passed with the real pinned SDK and bundled CLI:
runtime configuration and native metadata preflight/catalog cleanup. The
preflight asserts no model inference and no gateway HTTP requests. These are
repository integration tests with synthetic catalog/observer fixtures, not
unchanged upstream tests. Two unclosed-file ResourceWarnings occurred in that
passing native run and are retained. The initial default-loader review found
a missing malformed-URL case; it was corrected using the existing URL contract
and rechecked before publication.

Overturn the fallback when the command center adopts a different canonical
NativeStack2604 endpoint. Requalify default selection when the topology schema,
worker packaging path or URL contract changes. A different model route,
requested effort, gateway release, provider identity or live-provider success
requires its own acceptance; this change qualifies configuration selection.

Sources:

- `native-agent-stack@ecfa112764c664d35377dd66b8cfcb67e5a94d60:evidence/artifacts/new-wsl-install-plan-20261002/config/gpt-gateway-topology.json:2,9` defines the schema and endpoint.
- `native-agent-stack@84c79f7f92f61972a46aa470a4f299017bc82768:evidence/artifacts/new-wsl-install-plan-20261002/accept.sh:2596` reads the checked-out asset for SkillSpector; it selects a model, not an endpoint.
- [Existing native endpoint reader](https://github.com/seathatflowsinourveins/native-agent-stack/blob/84c79f7f92f61972a46aa470a4f299017bc82768/evidence/artifacts/new-wsl-install-plan-20261002/config/promptfoo-gateway.cjs#L8) selects `gateway.endpoint`.
- `native-agent-stack@ecfa112764c664d35377dd66b8cfcb67e5a94d60:examples/omniroute-codex-sdk/worker.py:90` provides the existing URL contract.
- [Pinned Codex SDK](https://github.com/openai/codex/tree/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python) and the existing `native-agent-stack@ecfa11276:examples/omniroute-codex-sdk/test_worker.py:502,774` support the bounded native configuration/preflight checks.
- [Pinned DeepAgents API](https://github.com/langchain-ai/deepagents/tree/4394bcd00b8eb46e7c423939643a0dfcfb5d8773) and [LangChain OpenAI base_url](https://github.com/langchain-ai/langchain/blob/026c3da2b615abe52f8446e37de460b844d07a43/libs/partners/openai/langchain_openai/chat_models/base.py) remain the example's supported runtime APIs.
