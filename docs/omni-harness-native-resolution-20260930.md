# Native OmniRoute harness resolution

The selected GPT coding path is the native Claude coordinator, official Codex Python SDK, native Codex app-server and OmniRoute Responses endpoint. The accepted 0.159.2 integration remains the incumbent. Published SDK/CLI 0.159.3 and OmniRoute CLI 3.8.51 were installed in separate owned prefixes. New-version catalog discovery and three unchanged upstream API tests passed. The actual native Claude→SDK Sol/Max turn failed with HTTP429, so 0.159.3 is not promoted.

The complete dated [manifest](../evidence/artifacts/omni-harness-native-resolution-20260930/manifest.json) retains source pins, install commands, actual exits, original private-artifact digests, failures and next gates. Native metadata, upstream tests, local fixtures and actual provider execution have separate scopes. Complete provider usage and backend identity remain unknown.

## Candidate verdicts

| Candidate | Verdict | Reason |
| --- | --- | --- |
| [Official Codex Python SDK](https://github.com/openai/codex/tree/01fc69f4026735edfdf6789820549727a4867b11/sdk/python), 0.159.3 | Selected native GPT worker; new revision awaits acceptance | Retains native tools, MCP, skills, threads, model/effort and app-server lifecycle. No SDK files changed from the accepted 0.159.2 source, but new native execution still needs its own evidence. |
| [OpenAI Agents SDK](https://github.com/openai/openai-agents-python/tree/fdf21db62c303a3db54b0dfbee82de2141fa2799), 0.22.3 | Conditional application orchestration | Handoffs, guardrails and application sessions can justify adoption; native coding-state integration needs a separate gate. |
| [LangGraph](https://github.com/langchain-ai/langgraph/tree/49cce0ca852be4cfb567a1cbe0e511ff325a1682), 1.2.12 | Conditional durable graph | Adopt for a demonstrated checkpointed application graph requirement. Python package and CLI release numbers differ. |
| [OpenHands SDK](https://github.com/OpenHands/software-agent-sdk/tree/1e1390acc8788346ba4804c34323284009bf3f5e), 1.50.1 | Conditional isolated worker | Its separate runtime needs frozen isolation, lifecycle and task-quality comparisons before adoption. |
| [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview), 0.2.162 bridge | Unqualified existing OmniRoute translation trial | Retained bridge errors remain unresolved. Native Claude already has a supported route to a GPT worker through the official Codex SDK. |

These are capability-specific selections. No universal framework or complete-cost winner has been measured. Hindsight remains the fit-based shared-memory target described in the memory manifest; its measured backbone-winner field remains null.

## What ran natively

The native uv script installer and lock selected published `openai-codex==0.159.3` and its exact bundled CLI. A new worker home rendered from the existing template discovered Context Mode (9 tools), Serena (5 tools), 34 enabled skills and the project-installed `using-superpowers` skill. Discovery submitted no model inference.

The supported npm global-prefix install added 1153 packages. Published OmniRoute CLI version/help and its health command against the incumbent loopback gateway exited0. npm reported upstream peer-dependency warnings and seven unallowlisted lifecycle scripts. Fresh server startup from this published package was not qualified. Registry integrity identifies the installed package; its metadata lacks `gitHead`, so equivalence with the reviewed [v3.8.51 source tag](https://github.com/diegosouzapw/OmniRoute/releases/tag/v3.8.51) is not claimed.

Three selected, unchanged upstream public-API tests passed against the published wheel. Pytest conftest and project configuration were excluded because the upstream checkout otherwise prepends its development SDK. This was API acceptance, not a new model run. A cache-write warning did not affect the three assertions.

Native Claude2.1.286 Sonnet/Max read the project dispatcher and invoked the new SDK worker through native Bash. The worker preserved Sol/Max and initialized the native0.159.3 runtime. Its owned rollout records HTTP429 and `response_too_many_failed_attempts`; the worker exited2. Parent cumulative cost was $0.2888852, counted once. Worker and complete provider usage stay unknown. A healthy HTTP endpoint does not establish inference readiness.

## Lifecycle and next gate

Two unchanged local fixture runs failed during temporary-directory cleanup. Astra/Max then added strict fixture-owned process quiescence: same-UID processes inside the unique temporary directory are observed and awaited through pidfd/poll, with a 30-second deadline that fails and preserves residue. All 13 original test-method ASTs are unchanged; the repaired local integration run passed 13 tests in 18.679s. An owned Git process was independently observed after SDK shutdown, and all 11 observed Git/helper processes subsequently exited. Earlier failed residue and SDK ResourceWarnings are retained. The SDK's [close implementation](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/sdk/python/src/openai_codex/client.py#L268) terminates and waits for its immediate app-server child; production descendant cleanup remains unqualified.

Native peer messaging returned six successful queued acknowledgments, followed by two targeted 429 handoffs to the gateway and rollout owners. These establish enqueue, not completed recipient work. A native route dry run also exited1 without inference; its error category remains unestablished. Gateway/provider owners must supply native readiness or repair the429 condition before another bounded real GPT task, selected MCP execution and thread resume can qualify0.159.3. Matching0.159.2 acceptance is retained. No account credit was redeemed, active gateway replaced or new WSL distribution created.

## Sources and interpretation

The pinned SDK source, [Codex0.159.3 release](https://github.com/openai/codex/releases/tag/rust-v0.159.3), [OmniRoute package source](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/package.json), [native Claude skills](https://code.claude.com/docs/en/skills), and unchanged oracle are primary references. Source research and independent private-artifact verification informed the decision; neither substitutes for real-provider acceptance.
