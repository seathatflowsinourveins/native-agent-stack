# Decision: GPT-6.1 Sol at ultra is the GPT lane's workhorse, with Astra when the situation needs it (2026-10-03)

**Decided by:** a bounded worker of coordinator session `native-agent-stack-c5`, on the user's directions of
2026-10-03, in branch `c5/sol-ultra-workhorse` from `origin/main` `984bf4b27`. Lane: foundation.

**Amends:** [the Sol-primary routing record](2026-09-30-sol-primary-quality-defaults.md), whose worker clause
("GPT-6.1 Sol/Max for primary workers") this replaces, and clause (a) of
[the rule-text record](2026-09-30-rule-text-every-layer.md). Both carry a dated note.
[The Codex-lane effort record](2026-09-29-codex-lane-default-effort.md) is consistent and unchanged: its 2026-09-30
amendment already lets a lane stage ultra and keeps blind or isolated review lanes at max.

## Question

The user's words, verbatim:

- about 22:15Z: "the max quality it can get which is ultra, or your recommand. for highest quality and parrellel
  sdks,runtime workers, with fast speed and full stacks of token efficiency practice"
- about 22:27Z: "make sure the sol6.1 at ultra can be our main workhorse while astra USE when situation needed"

Which effort should GPT-6.1 Sol use by default for GPT-lane coordination and runtime workers, where does max remain,
and when does Astra take over?

## Evidence

Tags: **[doc]** primary source read at a pinned revision; **[obs]** local fixture observation with the real bundled
native runtime, not provider execution; **[measured]** recorded provider runs.

1. **[doc] What ultra sends on each root request.** At Codex `rust-v0.160.0` (`a956835d020762cb2b570053af06f643a11c0ecc`),
   `ModelInfo::resolve_reasoning_effort`
   ([protocol/src/openai_models/reasoning_effort.rs:10-40](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/protocol/src/openai_models/reasoning_effort.rs#L10-L40))
   sends ultra as the catalog's `multi_agent_reasoning_effort` when that value is listed and is not ultra, else max
   when listed, else the highest listed non-ultra level, else medium. The bundled catalog sets that value to `xhigh` for
   `gpt-6-astra` and `gpt-6.1-sol`
   ([models-manager/models.json:22,196](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/models-manager/models.json)).
   `core/src/client_tests.rs:1168-1184` tests that override; `:1186-1241` test the fallbacks, where max applies only
   without a valid override. Natively, Sol at ultra therefore sends `xhigh`, not max. This corrects the coordinator
   brief's reading of `client_tests.rs:1180-1238` ("ultra reasons as deep as max per request"). It agrees with
   both records named above, which found the same at 0.159.2.
2. **[doc] What ultra adds.** An effective ultra selects `MultiAgentMode::Proactive`, and any other effort selects
   `ExplicitRequestOnly`
   ([core/src/session/multi_agents.rs:96-104](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/session/multi_agents.rs#L96-L104)),
   under multi-agent V2 only (`:80-82`). The Sol and Astra catalog rows set `multi_agent_version: "v2"`
   (`models.json:21,195`), which
   [core/src/config/mod.rs:1606-1613](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/config/mod.rs#L1606-L1613)
   applies when no feature override is set. The `multi_agent_v2` feature itself is stable and off by default
   (`features/src/lib.rs:1336-1341`).
3. **[doc] What the default gateway route forwards.** The worker's id `cx/gpt-6.1-sol-max` takes the `gpt-6.1-sol`
   catalog row through the namespaced-suffix lookup (`models-manager/src/manager.rs:873-901`), so points 1 and 2 hold
   for it. OmniRoute's Codex executor gives a model-suffix effort precedence over the body's `reasoning.effort`
   ([diegosouzapw/OmniRoute `2f42a9ac1`, open-sse/executors/codex.ts:1419-1441](https://github.com/diegosouzapw/OmniRoute/blob/2f42a9ac19d1a247ec9ce5473b790843724b3061/open-sse/executors/codex.ts#L1419-L1441)),
   the release/v3.8.51 commit the port-20128 build is based on. That build carries PR #15167, which adds `gpt-6.1-sol` to
   the `-max` alias set (`manifests/stack.json`, `omniroute` row). Through the default route, each root request should
   therefore reach the backend at max. This was not observed live (residual 3).
4. **[obs] Fixture with the real bundled runtime.** `examples/omniroute-codex-sdk/test_worker.py` drives the bundled
   0.160.0 runtime against a loopback fixture provider. With this change, the default ultra sets the launch override
   `model_reasoning_effort="ultra"`, the turn effort ultra and a preflight readback of `ultra`. The request carries
   `reasoning.effort` `xhigh` and a `<multi_agent_mode>` fragment that begins "Proactive multi-agent delegation is
   active." With `--effort max`, every site and the request carry max, and the fragment begins "Any earlier
   instruction enabling proactive multi-agent delegation no longer applies." The fixture does not exercise OmniRoute.
5. **[doc] How far delegation fans out.** Without spawn overrides, children inherit the parent's model and effort
   (`core/src/agent/child_config.rs:196-209`). Under V2, a child of a V2-catalog model keeps the collaboration tools
   (`core/src/tools/spec_plan.rs:672-683`), so depth does not bound it. A tree-wide limit on concurrently spawned
   agents does: `core/src/agent/registry.rs:89-98` and `core/src/config/mod.rs:1615-1622,2760-2771`. That limit is
   three in the worker's private home (`agents.max_concurrent_threads_per_session = 3`), and three under the V2
   default of four threads otherwise.
6. **[doc] SDK support.** `openai-codex==0.160.0` defines `ReasoningEffort.ultra`
   (`openai_codex/generated/v2_all.py:3694-3702`, re-exported by `openai_codex/types.py`).
7. **[measured] Fast tier.** [The tier probe receipt](../../evidence/receipts/omniroute-sdk-worker-fast-tier-20261003.json)
   records four runs at requested max through port 20128, two per tier, with an identical prompt. The fast tier gave
   61.05 and 61.26 output tokens per turn second against 32.63 and 32.79 standard (about 1.87 times); the probe's own
   wall times were 102.8-118.5 s against 194.2-211.3 s. **[doc]** Codex sends `fast` as the request id `priority`
   (`protocol/src/config_types.rs:528-551`; `core/config.schema.json:7632-7635`), and the Sol catalog row describes
   the tier as "2x speed, increased usage" (`models.json:340-349`).

## Alternatives

- **Max everywhere**, the previous worker default. Each root request runs at max and the worker delegates only when a
  task asks. Rejected as the default: the user asked for ultra and parallel runtime workers, and through the `-max`
  route ultra keeps max on root requests (point 3) while adding proactive delegation (point 2).
- **Ultra everywhere, including one-model lanes.** Rejected. A blind or one-model convergence lane must stay one
  isolated judgment, and proactive delegation spawns further threads. The landscape-sweep harness keeps those lanes at
  max (`tools/sota-convergence/landscape-sweep/README.md`, "The harness default stays max"; the `codex_job.py`
  docstring); this change leaves it untouched. On a suffix-less route, ultra also lowers each root request to `xhigh`
  (point 1).

## Decision

- GPT-6.1 Sol at ultra coordinates and runs workers, the OmniRoute SDK runtime worker included: `worker.py` takes
  `--effort {ultra,max}`, default `ultra`, on the `cx/gpt-6.1-sol-max` route.
- Max stays for a single judgment, a blind or one-model convergence lane and the bounded `stack-worker` exec profile
  (`adoption/templates/codex.stack-worker.config.toml`, unchanged).
- Astra's triggers are unchanged. Astra at ultra coordinates a complex workflow that needs Astra; Astra at max takes a
  single consequential judgment (conflicting primary evidence, consequential architecture, complex changes across
  systems, or a failure unresolved after one bounded Sol repair). With the worker, that is
  `--model cx/gpt-6-astra-max --effort max` for the judgment and the same model at the default ultra to coordinate.
- `service_tier = "fast"` is an optional, measured speed setting for a private worker home. It is not added to the
  starter template.

## Exact changes

- `examples/omniroute-codex-sdk/worker.py`: `EFFORTS` and `DEFAULT_EFFORT`, the launch override and the turn effort
  from `--effort`, `requested_effort` from the request, and the `--effort` option with its two choices. Dependencies
  and both PEP 723 locks are unchanged.
- `examples/omniroute-codex-sdk/test_worker.py`: ultra's request effort `xhigh` and the preflight readback `ultra` in
  the existing tests, plus six tests: the default reaching every site, `--effort max` reaching every site, the two
  native multi-agent modes, refusal of other values, a negative control restoring the previous revision's hard-coded
  max (`worker.py:125,437` at `984bf4b27`), and the preflight readback for both values.
- `examples/omniroute-codex-sdk/README.md`, `enhancements.md` and `.claude/skills/omniroute-runtime-worker/SKILL.md`.
- The shared Codex routing sentence on all four rule surfaces: `AGENTS.md:38` (which also cites this record),
  `examples/claude-native/CLAUDE.md:48`, `adoption/templates/codex.AGENTS.template.md:14` and
  `adoption/scaffold/AGENTS.md:15`. `adoption/new-wsl/{claude,codex}-user-instructions.md` were regenerated with
  `tools/adoption/new_wsl_client_config.py --write-blocks`. In the tests, the shared sentence in
  `tests/test_install_claude_profile.py` and the Codex top-rule hash and word count (827 to 846) in
  `tests/test_codex_worker_lane.py` are re-pinned. Its local byte budget for the Codex template goes from 8,192 to
  8,320: the template stood at 8,180 bytes and needs 8,307 with this sentence.
- [The tier probe receipt](../../evidence/receipts/omniroute-sdk-worker-fast-tier-20261003.json), with this record and
  the two dated notes.
- Unchanged: the `stack-worker` profile, every convergence-lane tool, the worker locks, and the source closure of
  `examples/omniroute-codex-sdk/checks.json` and the
  [0.160.0 refresh receipt](../../evidence/receipts/omniroute-sdk-worker-0160-20261003.json). Both are historical and
  name the previous worker and test bytes.

## Rollback

Pass `--effort max` per call for the previous behaviour without a code change. Reverting the commit restores the
hard-coded max, the previous routing sentence on every surface, the test pins and the 8,192-byte budget. Then
regenerate the new-WSL blocks with `--write-blocks`.

## Overturn conditions

- A measured quality regression of ultra against max on a fixed task set, with the same prompts and acceptance oracle.
- Pool exhaustion caused by sub-agent fan-out, such as provider-limit failures attributable to delegated threads.
- A Codex release that changes the ultra mapping (`reasoning_effort.rs`), the proactive selection
  (`multi_agents.rs`), or Sol's catalog `multi_agent_reasoning_effort` or `multi_agent_version`.
- An OmniRoute change to suffix-over-body effort precedence, or a build without `gpt-6.1-sol` in its `-max` alias
  set.

## Residuals

1. No quality comparison of ultra against max was run.
2. Sub-agent fan-out cost is unmeasured. The worker's native usage snapshot covers its own thread; delegated threads
   are separate native threads, so at ultra the snapshot does not establish complete usage.
3. The gateway-forwarded effort under ultra was not observed live. This change made no live model call.
4. The fast tier was measured at max only, in two rounds on one prompt, and its pool cost was not measured.
5. The worker's 300 s default deadline and the Dagu graph's 600 s (`runtime-worker.yaml`) were sized at max. A
   delegated ultra turn lasts as long as its sub-agents; one native wait call defaults to 30 s and may ask for up to
   3,600 s (`core/src/config/mod.rs:256-258`), and a deadline interrupts the turn. No ultra run has tested whether
   those deadlines are long enough.
6. `docs/decisions/2026-10-02-two-host-north-star-architecture.md:240` still describes Sol at max running primary
   workers. That dated architecture record is left to its owner.
