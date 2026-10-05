# Decide round 2: existing-owner configuration in the clean install plan

Date: 2026-10-04. Status: plan configuration implemented; destination execution
and model/provider acceptance remain UNRUN. This bounded unit serves the north
star's reproducible US-equities research and historical simulation by preserving
two independent research gatherers, native Sol/max workers, skill regression
verification and a separately qualified worker telemetry contract.

The owner rule and selected owners are
[the accepted round-2 decision](2026-10-04-final-architecture-round2.md) and
[its sanitized verdicts](../../evidence/artifacts/final-architecture-round2-20261004/verdicts.json).
This job changes only `promptfoo`, `research-harnesses`, `gpt-gateway` and
`harbor-containerized-agent-e2e-runner` and their configurations. The gateway
recipe pin remains proposed; stack and architecture pins are unchanged. It
installs no tool or launches a local trial. The
writing builder preserves its requested Sol/max lane; no child or cross-family
lane was launched. Repository research uses `search-first` quick mode and
OpenAI Docs; the owners are already selected, so discovery checks those owners'
release sources. The installed sandbox client reports Codex 0.159.3 and Claude
Code 2.1.289; that observation is separate from the clean host's pinned clients.
Scoped ai-memory retrieval was rejected by the tool's approval policy; the
current original decision, verdict and upstream sources were read directly.

## Promptfoo: Test Agent Skills on the pinned host clients

Retain Promptfoo 0.123.1, its existing SHA256-verified npm tarball and optional
SDK dependencies. Add the installed SDK dependency read-back to post-install
acceptance. The paired config now selects the host executables through
`path_to_claude_code_executable` and `codex_path_override`. Both SDK providers
reuse native sign-in; provider API-key variables are removed for this paired
acceptance. Codex uses `openai`, `gpt-6.1-sol` and `max`, with its existing native
HOME/CODEX_HOME. Scratch project workspaces isolate the named test skill without
copying authentication. Existing gateway A/B, echo controls, inverted skill
control and actual provider results remain recorded by Promptfoo.

Sources: `promptfoo/promptfoo@34f74d34e140b5e17d23770dfb2340057b1936b8:package.json:1`,
`:site/docs/guides/test-agent-skills.md:204`,
`:site/docs/providers/claude-agent-sdk.md:45`, `:site/docs/providers/claude-agent-sdk.md:890`,
`:site/docs/providers/openai-codex-sdk.md:62` and `:232`;
[Codex SDK](https://developers.openai.com/codex/sdk/) and
[native Codex config](https://developers.openai.com/codex/config-reference/).

Skill-creator retains authoring and authoring-time evaluation. Harbor retains
containerized task-level A/B. The removal comparison is Promptfoo against
Harbor 0.23.0 (`--skill` plus Rewardkit) on the same frozen, oracle-labelled
skill regressions in both clients: transfer ownership only if Harbor detects
strictly more true regressions with no more false flags and complete records.
Verification correctness is scored separately from task success. Native client
sign-in when absent and the existing gateway template's provider model IDs
remain `needs_user`.

Correction to the verdict's open item: the pinned Claude provider documentation
at lines 45-56 explicitly documents `apiKeyRequired: false` with an existing
native Claude Code session. That source supports the configuration, while
native execution on the destination remains owed. Codex `skill-used` remains
inferred from successful `SKILL.md` reads, as the pinned guide states at line 249.

## Research consumers: preserve the fix-wave binding

The repair configures DeerFlow's `langchain_openai:ChatOpenAI` model
`cx/gpt-6.1-sol` at `http://127.0.0.1:21128/v1`, with
`supports_reasoning_effort: true` and `reasoning_effort: xhigh`, keyless DuckDuckGo and Jina
tools, `DEER_FLOW_CONFIG_PATH`, and the embedded client. GPT Researcher already
uses the same endpoint, `duckduckgo`, `CONTEXT_FILTER=keyword` and `env -i`,
preventing inherited environment overrides. Its smart and strategic models use
the plain Sol route at xhigh; its fast model retains the high suffix. Keep both
installs. Add the installed runner's preflight and an
effective DeerFlow endpoint/model/tool read-back. The fresh native Codex caller
uses its native Sol/max route.

Sources: `assafelovic/gpt-researcher@0957c301ed06c2a5857b834358c7227c739041d4:gpt_researcher/config/config.py:63`
and `:158`; `bytedance/deer-flow@345f08be00c8a9495079b732a39b46aa9af1584e:backend/packages/harness/deerflow/config/app_config.py:681`
and `:backend/packages/harness/deerflow/client.py:1229`;
`bytedance/deer-flow@v2.1.0:config.example.yaml:250`, `:802`,
`:backend/tests/test_client.py:1`, `:README.md:1658`;
[this PR's installed GPT Researcher runner](https://github.com/seathatflowsinourveins/native-agent-stack/pull/684/files)
(`this PR: tools/research/gpt_researcher.sh:27`).

The conflicting research and topology verdicts are reconciled through #637's
published 3.8.51 record. That gateway caps Sol at xhigh. Per-run session headers
join both gatherers to native call logs; acceptance requires successful calls,
zero `/v1/embeddings` requests, and the delivered provider request's model and
reasoning effort, rather than the requested alias. DeerFlow's pinned
`config/model_config.py:36` defaults `supports_reasoning_effort` to false, and
`models/factory.py:283-285` drops the configured effort unless that flag is true;
the read-back asserts the flag as well. These source-verified repairs supersede
the earlier Sol/max consumer spelling. Effective-configuration read-back and those runs overturn the binding
only if an endpoint/model/effort/retriever mismatch cannot be expressed by the
consumers' documented settings and a gate-passing alternative fixes it without
adding a service. The comparison belongs to this binding, not a gateway swap.

## OmniRoute: published pool and fallback, native Sol/max

The completed recipe proposes replacing the clean install's carried canary composition with published
`omniroute@3.8.51` at `c1e30b7676975feb298b49eff6ff58923c04b89e`. Its native npm
install compares the published SHA512 SRI before install; npm enforces package
integrity. The registry publishes SLSA provenance, which was not verified by
this job. Native upstream doctor, readiness and fresh-client checks remain
acceptance, with no carried patch or historical canary receipt used as their
gate. The stack already records the qualified 3.8.51 release selected in #637; it
has no new_wsl_pin field and this repair does not change it. The destination
architecture uses the same published release. The historical #704 canary is
superseded by the round-2 topology, not carried as fresh acceptance.
The adoption profile has no OmniRoute entry to re-pin.

The new topology artifact and client-config map render the destination's
opt-in pool/fallback profile as `cx/gpt-6.1-sol` at `xhigh`. The profile disables
standalone search settings which depended on the previous PR #13788 carry.
Native `openai` Codex is the only Sol/max route until a published OmniRoute
release contains PR #15167. Upstream was queried on 2026-10-04: that PR is open
and unmerged. Re-pin only when the released source adds Sol to both alias sets,
then accept one gateway request whose observed wire `reasoning.effort` is `max`.
Keep the existing agentgateway-versus-OmniRoute Promptfoo comparison for the pool.

Sources: `diegosouzapw/OmniRoute@c1e30b7676975feb298b49eff6ff58923c04b89e:docs/guides/SETUP_GUIDE.md:28`,
`:open-sse/executors/codex/reasoningSuffix.ts:11`,
`:open-sse/executors/codex.ts:331`, `:bin/cli/commands/doctor.mjs:632`;
[published registry metadata](https://registry.npmjs.org/omniroute/3.8.51),
[release](https://github.com/diegosouzapw/OmniRoute/releases/tag/v3.8.51),
[Sol effort correction PR](https://github.com/diegosouzapw/OmniRoute/pull/15167).
Installed Codex `exec --help`, its [0.160.0 release](https://github.com/openai/codex/releases/tag/rust-v0.160.0)
and [noninteractive docs](https://developers.openai.com/codex/noninteractive/)
support the native invocation. Config map wiring is the existing destination
writer; no live client settings or service are changed in this builder.

Correction: the fix-wave's exact-Sol/max canary gate and clean-default carry
conflict with the round-2 ruling. Historical canary artifacts remain historical
and the clean functions no longer invoke them. A differing existing service
unit is retained and reported `needs_user`; installation reloads the manager,
and startup precedes service-health acceptance.

## Harbor: qualify native worker telemetry with its own runner

Retain Harbor 0.23.0 at `1e5c5c6db929a10a140d05e606882c671ae20729`. Install its
wheel only after verifying the published PyPI SHA256. Post-install runs the
unchanged ATIF validator unit tests; the existing upstream hello-user
oracle/nop integration remains the container runner READY gate. Add the native
telemetry-contract qualification as an `after_sign_in` acceptance recipe.

The recipe needs the user's maintained, commit-pinned task corpus and public
Harbor JSON job config. It uses Harbor's own runner, documented agent kwargs,
native verifiers and ATIF validator. Codex is pinned to 0.160.0 and DeerFlow to
v2.1.0; Codex uses native Sol/max. The OpenHands adapter and returned trial
version must match the producer's actually installed openhands-sdk metadata.
The worker pin stays 1.50.1. A move to 1.51.0 needs its owner's qualification;
an adapter mismatch exits 78 as needs_user before Harbor launches.
Native verifiers must separately assert the SDK/app-server and OpenHands
events, unique concurrent writer identity, MCP/skill, tool error/recovery,
nested workers, cancellation and restart, using valid and seeded-violation
cases and independently observed Collector outputs. ATIF alone does not
establish those properties. Collection/routing stays with the Collector's own
slot, and no exporter or trace setting is changed.

Sources: `harbor-framework/harbor@1e5c5c6db929a10a140d05e606882c671ae20729:tests/unit/test_trajectory_validator.py:1`,
`:tests/integration/test_hello_user_e2e.py:25`,
`:docs-mintlify/core-concepts/jobs/configs.mdx:6`,
`:docs-mintlify/core-concepts/agents/atif.mdx:121`,
`:src/harbor/agents/installed/base.py:560`,
`:src/harbor/agents/installed/codex.py:328`,
`:src/harbor/agents/installed/openhands_sdk.py:150`,
`:src/harbor/agents/installed/deerflow.py:181`;
[published wheel hashes](https://pypi.org/pypi/harbor/0.23.0/json) and
[uv tool install](https://docs.astral.sh/uv/reference/cli/#uv-tool-install).

The recipe explicitly leaves the task corpus, native/container provider
sign-in and endpoint/Collector reachability as `needs_user`. No corpus or new
local trial is invented. The removal comparison is the verdict's identical,
versioned native corpus in Inspect and Harbor; change ownership only if
Inspect reproducibly detects every seeded violation while Harbor misses at
least one without losing required runtime integration.

## Completeness review and alternatives

The four configuration jobs have their existing owners, source pins,
installation integrity, native acceptance paths and execution boundaries.
Sources include both SDK provider pages and the skills guide, both consumers'
config implementations, the gateway's alias parser and effort clamp, and
Harbor's native adapters, verifier/result model and validator. The live call,
gateway wire effort and raw SDK/app-server/Collector modalities remain explicit
acceptance items; version checks and ATIF validity do not substitute for them.
The next sweep must revisit a released PR #15167, the supplied native telemetry
corpus and the paired Promptfoo/Harbor verification comparison. No new
candidate class or service is adopted by this unit.

Alternatives retained for the named comparisons: gateway carried canary versus
the released pool route (the clean ruling selects the release); disposable
unauthenticated Codex homes versus native sign-in (native sign-in reaches the
selected Sol/max route without credential copying); native skill-creator
versus Promptfoo (the verdict selects Promptfoo and names Harbor as its
executable removal comparator); Collector or Inspect as telemetry qualifier
versus Harbor (Collector keeps routing; the verdict selects Harbor).

Shared row order, dispatch lists, installation counts and headers remain
unchanged. The base `check_plan.py` reports seven other-group problems; none
names these four slots. Evidence registry updates belong to the coordinator.

## Builder corrections and verification

The proposed gateway pin and its dependent architecture, generated handbook
and receipt changes were restored to HEAD under the deadline instruction.
The remaining recipe and topology record explicitly describe a proposed
3.8.51 destination, not an accepted host-pin move. The evidence registry
remains coordinator-owned. Shared headers are preserved; the README's shared
version-only inventory needs a coordinator update because Harbor now runs
upstream ATIF unit tests at post-install. The deadline skips the long unittest
rerun and permits only the requested short acceptance checks.

## Integrator correction, 2026-10-05

The builder's stack-not-yet-moved premise is superseded by main PR #637:
OmniRoute 3.8.51 has its qualification receipt and is the host selection. The
2604 gateway install, topology and architecture cell therefore follow 3.8.51;
the architecture's pin_source names this PR:manifests/stack.json:1887. Source:
this PR:docs/decisions/2026-10-03-omniroute-3851-pin.md:108. No host stack or
upstream-snapshot bytes change. The requested host new_wsl_pin change remains
currency-PR work with its own saturation row and qualification evidence.

The #704 composition calls retain their tool_root argument for aliases under
an owned canary prefix. Each acceptance stage then requires the published
3.8.51 prefix and package identity, so the selected release succeeds without
being compared to a historical canary receipt, and a carried canary cannot
qualify this destination. Source: this PR:docs/decisions/2026-10-04-2604-e2e-fix-wave-g8-base-gateway.md
(the destination composition binding); diegosouzapw/OmniRoute@c1e30b7676975feb298b49eff6ff58923c04b89e:
bin/cli/commands/doctor.mjs:632. The gateway effort comment in
adoption/templates/codex.omniroute.config.toml stays outside this job and is
handed back to its configuration owner.

Harbor's README inventory now names its unchanged upstream ATIF unit tests.
Its worker telemetry contract, Promptfoo's paired skill configuration and the
gatherers' published gateway bindings are integrated without changing their
owners. The existing OpenHands worker row remains 1.50.1; telemetry now checks
that installed version. Qualification of 1.51.0 is handed to its owner.
Native telemetry corpus, provider sign-ins and destination runs remain
external acceptance. Source: this PR:docs/decisions/2026-10-04-final-architecture-round2.md:37.
