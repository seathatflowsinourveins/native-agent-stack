# Research convergence practice: current upstream review

Date: 2026-10-05. Lane: foundation. Evidence: source review and the explicitly
listed local integration checks. North-star action: keep the research and
acceptance practice useful for US-equities research and historical simulation.

## Decision and boundary

Retain the released research runtimes and the existing division of evaluation
work between Harbor, Inspect, promptfoo and Anthropic's paired skill benchmark.
Their jobs differ; neither release freshness nor agreement between reviewers
establishes a universal quality winner. Qualifying an update is separate from
identifying a newer release. The comparisons below name the evidence that would
change each disposition.

Repair one verified source-projection error: an Alpaca adapter-path requirement
does not pin `alpacahq/alpaca-py`. Preserve that implementation as a comparison
candidate, the named broker/adapter requirement, the NautilusTrader destination,
and the LEAN oracle. The [north star at the review base](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/AGENTS.md#L53)
and [existing review-queue item 11](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/tools/sota-convergence/landscape-sweep/README.md#L190)
settle this correction. Overturn it only if the user explicitly pins an
implementation and the canonical requirement records that choice.

Keep V2 launch blocked. The controlling proposed design is **U11 revision 5**;
the V2 source-preparation contract cites revision 4 as its historical source.
An executable workflow reference supports using native orchestration primitives,
but does not implement all of the selection, provenance and measurement policy.
Implementing the entire runner is a suggestion subject to the blocker matrix
below. The source-only converter already disclaims runtime copy/usage acceptance;
its omission of those checks is an activation gap, not a demonstrated regression.

The baseline is `native-agent-stack@4c897418fe35a030a1188ae447eaf31c893f8eff`.
The implementation branch was refreshed onto `f946c6d4ca988a17b6fa4392ecb488909f147883`
before publication; the original source-review references keep their exact pins.
The concurrent foundation sweep's frozen staging names that same commit and
repository modality. Its freshness manifest is input to this review; no second
foundation sweep was launched, and no completed result for the requested full
run is asserted here. The currency and fixwave lanes own their runtime updates
and acceptance repairs. No runtime was installed or upgraded by this review.

## Local practice inventory

These integration files are pinned together at the review base above, rather
than having independent package releases. The table covers both operating
pipelines and the pending V2 contract.

| Component and exact source | Current comparison and verdict | Overturn condition |
| --- | --- | --- |
| [AGENTS.md top rule](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/AGENTS.md#L3), [convergence architecture](../convergence-architecture.md), [acceptance policy](../acceptance-evidence-policy.md) | Retain task-scoped primary-source verification, owned workers, frozen inputs and separate evidence classes. Anthropic's [agent evaluation guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) supports isolated trials, outcome grading and deterministic graders where possible. | A matched experiment shows that the practice misses consequential errors or harms task completion relative to a maintained alternative. |
| [Convergence recipe](../../recipes/sota-convergence-practice.md), [saturation recipe](../../recipes/saturation-sweep.md) | Clarify source-survey versus merit evidence and the controlling V2 revision. The existing six-command manifest pipeline and independent layer-verdict pipeline remain distinct. | Retained execution and measurements qualify a replacement contract; update the recipes together with its implementation. |
| [extract_layers.py](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/tools/sota-convergence/extract_layers.py), [github_freshness.py](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/tools/sota-convergence/github_freshness.py), [build_manifest.py](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/tools/sota-convergence/build_manifest.py) | Retain deterministic extraction, primary metadata collection and conservative manifest assembly. Metadata establishes currency, not target-workload superiority. Use release notes and package advisories as separate inputs. | A supported upstream integration preserves scope, source identity, uncertainty and publication checks with a demonstrated advantage. |
| [build_inputs.py](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/tools/sota-convergence/landscape-sweep/build_inputs.py#L428), [V2 schemas/templates](../../tools/sota-convergence/landscape-sweep/README.md#version-2-source-contracts-u11-ab) | Correct the inferred Alpaca repository pin. Retain neutral full-field preparation, unknown facts and V1/V2 separation. Source preparation is implemented; execution qualification is pending. | An explicit requirement changes, or discriminating checks show that the projection still leaks incumbency or omits a material candidate. |
| [sweep.js](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/tools/sota-convergence/landscape-sweep/sweep.js#L177), [build_args.py](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/tools/sota-convergence/landscape-sweep/build_args.py#L539), [make_prompt.py](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/tools/sota-convergence/landscape-sweep/make_prompt.py) | Retain V1 compatibility and V2 refusal. V1's incumbent-relative discovery, capped proposals and asymmetric/missing refutations do not establish merit-neutral selection. | Revision 5's full-field runner prerequisites pass with retained native provenance and failures. |
| [convert.py](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/tools/sota-convergence/landscape-sweep/convert.py#L46), [source_reviews.py](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/tools/sota-convergence/landscape-sweep/source_reviews.py#L1242) | Retain source-only conversion, pending identities and exact-source reviews. A surviving proposal is a research lead, not a measured replacement or installation authorization. | Runtime support binds every counted return to its original files and observed role/route, with complete attempt accounting. |
| [saturation_ledger.py](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/scripts/saturation_ledger.py#L302), [validate_convergence.py](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/scripts/validate_convergence.py#L85) | Retain hash, failure, pending and declared-consistency checks. A clean source-search count is not a quality ranking; a valid experiment record does not certify its declarations as true. | A discriminating counterexample escapes a promised check, or a maintained validator provides stronger same-contract evidence. |
| Native workflow reference: [agent-lab@e070125dae03b4e44484ccb78d2d65057ad38f40:layer-verdict-lane.js](https://github.com/seathatflowsinourveins/agent-lab/blob/e070125dae03b4e44484ccb78d2d65057ad38f40/.claude/workflows/layer-verdict-lane.js#L66) | Retain supported native chains/schema returns; source bytes match the vendored reference, SHA256 `fd77b74945e9d2bd0b26b7822aabcde00e7e650c327da16d852fdbfd5984c0d6`. Requested model aliases remain distinct from observed backends. | A lifecycle or task-quality comparison demonstrates an improvement over these supported primitives. |

## Research and web inventory

Release metadata was read through authenticated `gh api`; installed runtime
capabilities were checked through help/imports before pinned source and official
documentation. Hosted candidates were reviewed through official documentation;
no host access or execution was inferred.
Source-checkout versions, distribution versions, catalog pins and host presence
are separate facts.

| Component | Recorded pin and upstream state on 2026-10-05 | Comparison, verdict and overturn condition |
| --- | --- | --- |
| GPT Researcher | `v3.7.0@0957c301ed06c2a5857b834358c7227c739041d4`; [source package metadata `0.16.0`](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/pyproject.toml#L25); [latest stable release](https://github.com/assafelovic/gpt-researcher/releases/tag/v3.7.0), 2026-09-26 | Retain released source and configured keyword filter. The [upstream fixed-page replay](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/evals/context_filter/README.md#L17) isolates filtering across 28 tasks with GPT-5.4; it is useful directional evidence, not our Sol/financial-workload result. Suggest Jev comparison using that replay. Switch for an applicable fix or matched citation/relevance improvement with complete usage and operational acceptance. |
| DeerFlow | `v2.1.0@345f08be00c8a9495079b732a39b46aa9af1584e`; [latest stable release](https://github.com/bytedance/deer-flow/releases/tag/v2.1.0), 2026-09-24 | Retain embedded gatherer. Installed `DeerFlowClient` import/signatures agree with the [pinned embedded example](https://github.com/bytedance/deer-flow/blob/v2.1.0/README.md#L1643). Unreleased-main security changes require applicability review and native tests, not an automatic HEAD upgrade. Switch for applicable fixes or matched research-quality improvement. |
| agent-browser | General stack `0.38.1`; [latest `0.38.2`](https://github.com/vercel-labs/agent-browser/releases/tag/v0.38.2), 2026-10-01 | Currency lead for the existing web-layer owner. Latest notes include auth-control selection and browser reliability fixes. Adopt only after the owner's matched browser/auth/isolation acceptance; this review does not operate an auth vault. |
| Playwright CLI | General stack `0.1.21`, with Playwright `1.64.0-alpha-1789764292000`; [latest CLI `0.1.22`](https://github.com/microsoft/playwright-cli/releases/tag/v0.1.22), 2026-09-28 | Currency lead; new file-output and dialog/runtime fixes do not qualify a browser installation. Reopen on the selected browser tasks, exact runtime compatibility and output-retention checks. Do not substitute the CLI's version for its Playwright dependency. |
| OpenResearch | General stack `0.2.7@24e404ecbe19cb9184ea8177e8e9f90d4f3205b0`; [latest `0.2.15`](https://github.com/alphaXiv/OpenResearch/releases/tag/v0.2.15), 2026-10-02 | Literature/desktop comparison lead for its layer owner. Its application modality is distinct from an embedded gatherer. Promote only when the current release improves frozen literature/citation tasks and passes its platform lifecycle. |
| Tavily CLI | General stack `0.1.8`; [repository](https://github.com/tavily-ai/tavily-cli); latest-release endpoint returned 404 | No release version established by that endpoint. Package publication/tag/changelog verification remains pending with the web-layer owner. Missing releases do not prove abandonment. Reopen on primary-source coverage and provider failure/usage evidence. |
| WSL web-search selection | The plan defers `web-search-provider` and `research-skill`; [current WSL decision](2026-10-01-new-wsl-definitive-defaults.md) names native web, deferred trafilatura `2.2.0`, browser comparison and a 30-query SearXNG challenger | Retain the selected scope pending that comparison. The general catalog's Tavily/browser/literature list does not establish installation on this host. Switch on matched primary-source coverage, citation correctness, temporal accuracy, latency and security. |

The research-runtime alternatives are suggestions, not installs:

| Alternative | Current primary comparison | Disposition and overturn condition |
| --- | --- | --- |
| LangChain Open Deep Research | [Repository API](https://api.github.com/repos/langchain-ai/open_deep_research) reports archived; HEAD `1b7d2e80db9faa586165c60e09096dbbfd483a64`, 2026-08-10. Its [historical RACE results](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/README.md#L108) use older models/configurations. | Historical comparator. Reconsider as a maintained candidate only if upstream maintenance and supported execution resume; published historical scores do not compare our current routes. |
| LangChain Deep Agents | Maintained adjacent harness, [core `deepagents==0.7.21@4394bcd00b8eb46e7c423939643a0dfcfb5d8773`](https://github.com/langchain-ai/deepagents/releases/tag/deepagents%3D%3D0.7.21), 2026-09-30 | Add to next lifecycle-keyed research sweep. Adopt only after a same-task research-quality and isolation comparison; monorepo CLI releases are not SDK pins. |
| Stanford STORM | [Latest `v1.1.0`](https://github.com/stanford-oval/storm/releases/tag/v1.1.0), 2025-01-23; [repository API](https://api.github.com/repos/stanford-oval/storm) reports non-archived, [reviewed default-branch HEAD](https://github.com/stanford-oval/storm/commit/fb951af7744dab086e34962e9bc6fe878e145f83) dated 2025-09-30. The [original study](https://arxiv.org/abs/2402.14207) examines multi-perspective article generation and source-bias failures. | Historical coverage comparator: its inactivity exceeds U11's proposed 90-day maintenance screen. Reconsider only after maintained activity resumes or a maintained fork passes the common maintenance, execution and factual/temporal quality checks. |
| OpenAI deep research | [Official Responses API guide](https://developers.openai.com/api/docs/guides/deep-research): web/file/search-fetch MCP research and background execution | Trial candidate. Establish availability, matched outputs, actual usage and public/private-data boundaries before adoption; product documentation is not comparative acceptance. |
| Anthropic research-system patterns | [Production account](https://www.anthropic.com/engineering/multi-agent-research-system), June 2025: bounded delegation, artifact handoff and outcome evaluation with older Opus/Sonnet configurations | Reuse those practices; do not transfer reported gains or costs to current models. Replace orchestration only after matched quality/reliability/usage evidence. |
| Gemini Deep Research | [Official guide](https://ai.google.dev/gemini-api/docs/deep-research), preview research agent, Interactions API and background execution | Missed commercial/document modality for the next sweep. Trial only with native access and the same output, citation, failure and usage contract. |

Two different gatherer implementations sharing DuckDuckGo and GPT-family routes
do not establish independent source or model corroboration. The next comparison
must include citation entailment, contradictions, as-of versus current facts,
failed retrieval, unsafe links, documents/tables and complete provider usage.

## Evaluation, SDK and orchestration inventory

| Component | Reviewed pin → current primary upstream | Verdict and comparison that would overturn it |
| --- | --- | --- |
| Harbor | `0.23.0@1e5c5c6db929a10a140d05e606882c671ae20729` → [same stable release](https://github.com/harbor-framework/harbor/releases/tag/v0.23.0) | Retain containerized agent-task runner. Inspect is an evaluation alternative, not a drop-in task/environment contract. Change for a frozen task/reward/trajectory comparison covering identical agents, isolation and complete usage. |
| Inspect AI | Installed `0.3.273@9e44f1b77ed7c912bf58baf30db8560937e7ce53` → [`0.3.276@93f7182cf2ce9be22724b05e499cd1358d7ed41d`](https://pypi.org/project/inspect-ai/0.3.276/) | Suggest qualification by currency owner; hold selected pin pending its recorded sample-selection gate. [Changelog](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.276/CHANGELOG.md#L1) includes sandbox-user, refresh and untrusted-viewer fixes. Promote after unchanged upstream tests and selected scored/control examples pass. |
| promptfoo | `0.123.1@34f74d34e140b5e17d23770dfb2340057b1936b8` → [same release](https://github.com/promptfoo/promptfoo/releases/tag/0.123.1) | Retain gateway/provider A/B and regression role. Replace for better discrimination/provider fidelity on a frozen paired corpus with complete usage. Its [optional Claude TypeScript SDK pin](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/package.json#L224) is `0.3.263`; do not override an upstream dependency just because the [standalone release](https://github.com/anthropics/claude-agent-sdk-typescript/releases/tag/v0.3.289) is newer. |
| Anthropic skill-creator | `8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4` → same upstream main | Retain [same-prompt skill/baseline pairing](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/SKILL.md#L169), native timing and [aggregate/analyst pass](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/SKILL.md#L225): `python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>`. Lifecycle-key the corpus. Replace only after a preregistered skill comparison demonstrates better quality/error detection; no skill benchmark ran here. |
| Claude Agent SDK Python | `0.2.163@1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7` → [same release](https://github.com/anthropics/claude-agent-sdk-python/releases/tag/v0.2.163) | Retain package. Default bundled CLI is `2.1.286`, whereas host CLI is `2.1.289`. Suggest the [supported `cli_path` override](https://github.com/anthropics/claude-agent-sdk-python/blob/v0.2.163/README.md#L15) only when newer fixes matter; qualify parsing, usage IDs, cancellation and resume. Host CLI currency does not update the SDK child automatically. |
| Claude Agent SDK TypeScript | promptfoo dependency `0.3.263`; standalone [latest `0.3.289`](https://github.com/anthropics/claude-agent-sdk-typescript/releases/tag/v0.3.289) | Standalone application candidate, not the selected Python install or permission to override promptfoo's pin. Adopt after a same-application lifecycle, parsing, cancellation/resume and usage comparison with the Python/native route. |
| Codex TypeScript SDK | Plan/installed `0.160.0` → [same release family](https://github.com/openai/codex/releases/tag/rust-v0.160.0) | Retain supported streaming/resume. The reviewed source contract `adoption/new-wsl-profile.json` still describes `0.159.3`; it also carries Inspect commit `0321960a92aa52390413ce011d67ffb5962a2b11`, differing from the plan/host pin above. Hand off source-profile reconciliation to its owner. Change runtime for a matched lifecycle comparison against native exec/app-server or Python SDK. |
| Codex Python SDK / CLI | `0.160.0`, CLI `a956835d020762cb2b570053af06f643a11c0ecc` → [same release](https://github.com/openai/codex/releases/tag/rust-v0.160.0) | Retain published pair and existing scoped compatibility evidence. [Release preparation](https://github.com/openai/codex/blob/rust-v0.160.0/sdk/python/scripts/update_sdk_artifacts.py#L94) rewrites development metadata, so tagged-source tests alone do not qualify published wheels/binaries. Replace after matched cancellation/recovery/usage/permission controls. |
| Codex app-server | Native CLI `0.160.0`; [official lifecycle contract](https://developers.openai.com/codex/app-server#experimental-api-opt-in) | Supported application-integration alternative. Official docs distinguish the stable API surface from opt-in experimental methods/fields. Qualify initialization, threads, turns, cancellation, recovery and permissions against SDK/exec before changing the selected application route; do not infer qualification of experimental methods from a stable-method canary. |
| OpenAI Agents SDK | Catalog `0.23.1` → [same release](https://github.com/openai/openai-agents-python/releases/tag/v0.23.1) | Unqualified application-orchestration alternative; no selected install-plan row found. Its [experimental Codex tool](https://github.com/openai/openai-agents-python/blob/v0.23.1/src/agents/extensions/experimental/codex/codex_tool.py#L584) has API-key/native-auth precedence. Adopt only after the recorded lifecycle, cancellation/recovery and usage comparison passes. |
| OpenHands SDK/tools | Installed `1.50.1@1e1390acc8788346ba4804c34323284009bf3f5e` → [`1.52.0@229b2b920d4541eab7a34b051a1f6f2bca5ebabf`](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.52.0), published today at 04:10:05Z | Suggest qualification through currency owner, preserving comparison/amendment hold. New tmux isolation, loopback port and create/fork dedupe fixes are relevant leads. Promote after frozen-lock install, unchanged upstream SDK/cross tests, relevant workspace/terminal controls and native dispatch acceptance. |
| Claude native workflows / teams | Host `2.1.289`; [tagged changelog](https://github.com/anthropics/claude-code/blob/v2.1.289/CHANGELOG.md#L21), [Workflow contract](https://code.claude.com/docs/en/workflows), [experimental teams](https://code.claude.com/docs/en/agent-teams) | Retain native workflow primitives. Trial teams for independent peers needing shared communication, with resume/coordination/shutdown controls; availability alone does not show higher task quality. |
| Codex native multi-agent | Installed `0.160.0`: `multi_agent=true`, `multi_agent_v2=false` | Capability observation only. [Pinned dispatch conditions](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/core/src/session/multi_agents.rs#L77) require V2 before Ultra selects proactive orchestration; effort labels alone do not prove activation. Change operating choice only with observed role/lifecycle and matched task evidence. |

Harbor, Inspect, promptfoo and skill-creator already supply their respective
evaluation harnesses. A new custom benchmark runner is not justified by this
review. The current comparison has not run one common benchmark across every
research runtime or SDK, so documented fit is not promoted to measured merit.

## Security and corrected claims

Both repository advisory listings and package/global advisory records matter.
The authenticated repository APIs returned no public records for most reviewed
repositories, but GPT Researcher's global package record exists despite its
empty repository listing. This is a bounded direct-source review, not a
transitive lockfile, native-binary or whole-host security audit.

- [GHSA-8j86-h8gg-797p](https://github.com/advisories/GHSA-8j86-h8gg-797p), updated
  2026-10-02, lists critical MCP STDIO command execution for PyPI
  `>=0.14.5, <=0.14.7`, with no patched version listed. Current source metadata
  `0.16.0` lies outside that declared range; that fact does not prove the code
  path is safe. Our [research configuration](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/tools/research/gpt-researcher.config.json)
  configures no MCP servers and the runner scrubs inherited provider configuration. Reassess
  applicability before enabling MCP or accepting untrusted runtime configuration.
- Claude Python SDK's [resume-injection advisory](https://github.com/anthropics/claude-agent-sdk-python/security/advisories/GHSA-h4mw-j7qp-8mwm)
  affects `<0.2.121`, patched at `0.2.121`; the reviewed `0.2.163` is outside that
  range. Codex's [sandbox-boundary advisory](https://github.com/advisories/GHSA-w5fx-fh39-j5rw)
  affects `0.2.0` through `0.38.0`, patched at `0.39.0`; reviewed `0.160.0` is
  outside that range. These are version-matched observations, not comprehensive
  absence claims.
- DeerFlow main's [non-global-address fix](https://github.com/bytedance/deer-flow/pull/6202),
  [DNS event-loop fix](https://github.com/bytedance/deer-flow/pull/6140) and
  [browser address-pinning fix](https://github.com/bytedance/deer-flow/pull/6201)
  do not establish a defect in the configured Jina gatherer. The
  [selected provider](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/evidence/artifacts/new-wsl-install-plan-20261002/config/deer-flow-config.yaml#L21)
  uses the [pinned Jina client](https://github.com/bytedance/deer-flow/blob/v2.1.0/backend/packages/harness/deerflow/community/jina_ai/jina_client.py#L12).
  Those fixes become relevant gates for direct-fetch/browser/personal-MCP routes.
- The fixwave lead that an Inspect upgrade might repair absolute example paths
  was not supported. `src/inspect_ai/_eval/list.py` at both
  [0.3.273](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.273/src/inspect_ai/_eval/list.py#L51)
  and [0.3.276](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.276/src/inspect_ai/_eval/list.py#L51)
  has blob `5392251c7d31a60ab76d0fb024c08e7f270db7fb` and uses
  `root_dir.glob(glob)`. The checkout-relative example path is the integration
  repair; the runtime update is a separate qualification decision.
- Initial memory calls without a verified static-client workspace/project pair
  returned unrelated sessions. They were discarded; a global U11 lookup found
  no relevant page. No retrieved session determined a verdict. Initial reviewer
  wording called the V2 converter limitation a defect; exact
  `convert.py:46-50` corrected it to a source-only activation gap.
- Initial wording said MCP was disabled, but `MCP_SERVERS=[]` means no configured
  servers; [upstream defaults](https://github.com/assafelovic/gpt-researcher/blob/v3.7.0/gpt_researcher/config/variables/default.py#L44)
  keep the fast strategy and automatic tool selection. It was corrected without
  changing runtime configuration. A review lead calling the whole Codex
  app-server experimental/non-production was also narrowed to the official
  stable-surface versus opt-in experimental-method distinction.

## V2 runner suggestion and activation conditions

The [revision 5 amendments](2026-10-01-u11-merit-neutral-selection.md#revision-5-2026-10-01)
control the future runner. The historical revision 4 preparation source and
sealed inputs remain unchanged. Resolve all applicable part-2 conditions before
removing `build_args.py`'s staging refusal:

| Condition | Existing source / unresolved comparison |
| --- | --- |
| Script-owned maintenance screen | Deterministically screen archived/stale candidates from equal API facts; revision 5 forbids launch before this exists. Unknown facts stay pending. |
| Paid-service scope | Owner-set `paid_service_allowed`, false by default, bound into frozen scope; missing credentials do not establish a fee. |
| Full-field replicated roles | Freeze the expanded identity field after discovery; two distinct judgments/order seeds per family per role, including GPT facts. V1's capped-proposal screen is insufficient. |
| Observed family/route provenance | Bind each counted judgment to its native role slot and retained actual route. A self-declared family or requested alias is insufficient. Preserve unknown provider sampling seeds. |
| Stable saturation semantics | Credible existing members must not reset novelty counts forever; unresolved material newcomers and failed conditions keep the layer open. |
| Source absence and exclusion controls | Reuse the maintained missing-release response policy; resolve role-specific host/paid/requirement exclusions with deciding facts and discriminating controls. |
| Runtime authenticity and accounting | Extend original-file copy reconciliation and retained attempt/effort/search-cap failures to every replicated role. Do not substitute source-only conversion for runtime acceptance. |
| Merit stage, separately | Native upstream evaluation harness, preregistration before trials, bound input/field hashes, per-arm results, complete usage and recomputed outcomes. A documented-fit install default is not a merit winner. |

The source-only tests cover neutral fields, unknowns, declared replication,
pending propagation and refusal before launch. They do not cover observed
independent model executions. Admission/screens/re-voting can be implemented
before the first measurement receipt; only the merit stage waits for it, as
[U11 already specifies](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4c897418fe35a030a1188ae447eaf31c893f8eff/docs/decisions/2026-10-01-u11-merit-neutral-selection.md#L203).
The written contract therefore supports preparatory work without claiming the
pending runner has converged. Overturn the deferral when these conditions pass
with retained native execution evidence; declaring a merit winner additionally
requires the registered comparison receipt.

## Execution, ownership and evidence

The installed GPT Researcher route was used for current-month research. The
first query, `October 2026 evidence-based agent research and evaluation practice`,
exited 0 and produced a report whose native frontmatter says `sources_count: 15`, SHA256
`7dd5836efe231c57380efbd65c55fe2e38e1c07bcb9d848184f32cca9311c610`.
The report contains nine unique Markdown citation URLs, also nine in its
References section; these are different counting scopes from the native
frontmatter statistic. Its raw log retains a PDF HTTP 404 retrieval failure.
It primarily gathered event announcements, cited no reviewed runtime's primary
source, and supplied no useful matched runtime benchmark. This is a completed gather with limited relevance, not a
successful comparative acceptance. A narrower second query, `October 2026 deep
research software benchmarks`, also exited 0, SHA256
`8d3d9383d3f7cdfcfe7cb42d1e1e84e74591f87672cffca24624fe14a252fd8e`.
Its frontmatter records 17 sources, while the final report contains 11 unique
URLs; its log retains a skipped HTTP 403 retrieval. Most benchmark rankings
come from secondary sources and do not establish a matched October comparison.
The relevant primary lead, [DeepResearch Bench](https://deepresearch-bench.github.io/),
separates research-report quality (RACE) from retrieval/citation accuracy (FACT)
across 100 bilingual tasks in 22 fields. Suggest its task and scoring methodology
for a frozen comparison through the selected native evaluation harness; its
historical leaderboard does not qualify current routes. Raw reports stay private. Claims used here were independently
read at the primary URLs above. Provider-native usage for this review is unknown;
the gatherer's estimated dollar counter is not substituted for it.

Local commands for the repaired projection used a private lane cache as
`TMPDIR`, outside the shared tmpfs:

| Command / observation | Result | Evidence class |
| --- | --- | --- |
| Existing input-builder CLI test strengthened to require Alpaca/IBKR repository null, true destination/oracle references, and Alpaca candidate retention | Failed before correction, exit 1; passed after correction, exit 0 | Synthetic local integration |
| `python3 -m unittest tests.test_landscape_sweep_harness.NeutralFieldTests tests.test_landscape_sweep_harness.NeutralSchemaTests tests.test_landscape_sweep_harness.NeutralStagingTests tests.test_saturation_ledger.V2PendingCliTests tests.test_convergence_contract -v` | 87 tests passed | Synthetic local integration; no model calls |
| `python3 -m unittest tests.test_landscape_sweep_harness tests.test_saturation_ledger tests.test_convergence_contract -v` | 358 tests run, four skipped; all executed tests passed | Synthetic local integration; no model calls |
| `python3 scripts/validate_convergence.py --all-recorded --root . --json` | Exit 0; recorded experiments valid | Existing record consistency, not new experiment execution |

No new convergence experiment or merit-selection claim was registered. Existing
record checks and repository validation are reported in the PR and lane handoff.
The local test result is not unchanged upstream acceptance or a new host's model
qualification. The co-op's earlier installation/E2E census was reused only for
its recorded stage/pin scope; no historical receipt was replayed as a fresh run.

Future runtime installation belongs to the owner of the qualifying PR and uses
only the existing plan rows: `research-harnesses`, `inspect-ai`,
`harbor-containerized-agent-e2e-runner`, `promptfoo`, `skill-authoring`,
`claude-agent-sdk`, `codex-sdk-and-codex-exec-app-server`, or
`agent-runtime-worker`. After that PR exists, use `install.sh --only <slot>` and
`accept.sh --only <slot> --stage <stage>`. `check_plan.py` checks synchronization;
it is not a generator. `build_new_wsl_handbook.py --write` and
`build_ecosystem.py --write` render their respective derived guides. These
commands do not independently update source pins or qualify a runtime.

The projection repair touches foundation-owned tooling and its synthetic test,
not trading selections or acceptance-plan summaries. Preserve U11's Gate A
script review and trading-owner acknowledgement as landing conditions; this
lane opens a review PR and does not merge it.

## Completeness critique and next sweep seeds

The read-only reviewers identified candidate and modality gaps: maintained
Deep Agents rather than archived Open Deep Research; Gemini and Claude's
[documented deep-research route](https://github.com/anthropics/claude-code/blob/v2.1.289/CHANGELOG.md#L870);
hosted OpenAI/Anthropic agent runtimes; documents,
tables, browser/audio/provider differences; published wheels versus source
environments; bundled versus host CLIs; retry deduplication; and complete
dependency locks. Include explicit OCR, formula/table and page/block provenance
comparisons with the native document-parsing route, and provider outages,
interrupted-run recovery, rollback and retirement. These are next-sweep leads,
not accepted replacements. Preserve Gemini's `deep-research-preview-04-2026`
identifier when freezing its trial and the separately held Linux/macOS Codex
pins when comparing platforms; this host's observed version changes neither hold.

The next lifecycle-keyed skills comparison should cover discovery, source
verification, install/activation, recovery and retirement separately. Use the
upstream paired skill benchmark and preserve nondiscriminating failures. A
runtime comparison should score report correctness, citation entailment,
coverage and temporal accuracy under matched data access and models, with
independent outcome checks and complete failures/usage. The ongoing foundation
sweep remains the owner of layer outcomes; this meta-layer record supplies
these seeds and must not convert its source survey into measured merit.

Match models where configurable in a controlled runtime comparison. Hosted
agents whose models cannot be matched require a separately identified complete
product comparison with exposed settings and data access retained. Include
search-grounded answer APIs as a distinct candidate class; DeepResearch Bench's
historical entries are discovery leads, not current qualification evidence.
