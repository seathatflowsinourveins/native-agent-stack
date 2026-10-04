These recipes qualify separate native environments: OpenHands CLI 1.16.0 uses
SDK 1.21.0, while the standalone SDK recipe uses SDK/tools 1.50.1 and patched
LiteLLM 1.93.2. The current CLI's SDK 1.21.0 Jinja cache is hard-coded to
`~/.openhands/cache`; CLI persistence settings do not qualify whole-cache
isolation. The standalone SDK supports `OH_PERSISTENCE_DIR`, set before import.

`native-llm-trial.py` prepares metadata by default. Its explicit `generate` mode
makes one native `LLM.generate` call with a `Message` containing `TextContent`,
using Responses, Sol/Max, zero SDK and transport retries, a 180-second request
timeout and a 1,024-token output limit. Run it under an external 240-second
deadline. The exact-output check and local wrong-answer check are integration
oracles; they are separate from unchanged upstream tests. The trial uses the
public `local-loopback` placeholder key and observer URL `127.0.0.1:25371/v1`.
Provider execution requires the frozen trial plan and its observer window.
The recorded exact-output generation passed. Original executed source bytes
and publication-only cleanup are mapped in the
[source binding](../../evidence/artifacts/native-runtime-role-resolution-20260930/execution-source-bindings.json);
the cleaned recipe has an identical AST and was not a new provider run.

The native SDK API and normalized output are supported by
[LLM.generate](https://github.com/OpenHands/software-agent-sdk/blob/1e1390acc8788346ba4804c34323284009bf3f5e/openhands-sdk/openhands/sdk/llm/llm.py#L1673),
[Message/TextContent](https://github.com/OpenHands/software-agent-sdk/blob/1e1390acc8788346ba4804c34323284009bf3f5e/openhands-sdk/openhands/sdk/llm/message.py#L174),
[LLMResponse](https://github.com/OpenHands/software-agent-sdk/blob/1e1390acc8788346ba4804c34323284009bf3f5e/openhands-sdk/openhands/sdk/llm/llm_response.py#L28)
and the original
[Responses parsing test](https://github.com/OpenHands/software-agent-sdk/blob/1e1390acc8788346ba4804c34323284009bf3f5e/tests/sdk/llm/test_responses_parsing_and_kwargs.py#L173).

Correction: constructing the earlier configuration with bare
`cx/gpt-6.1-sol-max` did not prove provider resolution. The installed LiteLLM
1.93.2 resolver returned no provider for that alias; it resolves
`openai/cx/gpt-6.1-sol-max` to provider `openai` and wire model
`cx/gpt-6.1-sol-max`. This follows the SDK's
[native provider parser](https://github.com/OpenHands/software-agent-sdk/blob/1e1390acc8788346ba4804c34323284009bf3f5e/openhands-sdk/openhands/sdk/llm/utils/litellm_provider.py#L35)
and LiteLLM's
[provider-prefix resolver](https://github.com/BerriAI/litellm/blob/cd1bd0f4b8af865f8d05fbd938392fdd4703babc/litellm/litellm_core_utils/get_llm_provider_logic.py#L221).
`native-config.py` requires a supplied model, so this correction changes no
saved model default. Construction and source tests remain metadata and native
test evidence until an observed provider round-trip passes.
