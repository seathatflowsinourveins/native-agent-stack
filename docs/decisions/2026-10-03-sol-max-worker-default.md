# Decision: Sol max default for the packaged worker (quality first), ultra opt-in (2026-10-03)

**Decided by:** a bounded worker of coordinator session `native-agent-stack-c5`, on the user's directions of
2026-10-03, in branch `c5/sol-ultra-workhorse` (base `origin/main` `984bf4b27`, merged with `b29036f05`). The
coordinator re-scoped this branch after the user's clarification below. Lane: foundation.

**Relation to existing records.** This record amends none of them. The routing rule stays as
[the Sol-primary record](2026-09-30-sol-primary-quality-defaults.md) and `AGENTS.md:38` state it: GPT-6.1 Sol at
ultra coordinates and at max runs workers, and Astra keeps its triggers.
[The Codex-lane effort record](2026-09-29-codex-lane-default-effort.md) keeps blind or isolated lanes at max. This
record covers only the effort option of the packaged OmniRoute SDK worker.

## Question

The user's words, verbatim and in order:

1. about 22:15Z: "the max quality it can get which is ultra, or your recommand. for highest quality and parrellel
   sdks,runtime workers, with fast speed and full stacks of token efficiency practice"
2. about 22:27Z: "make sure the sol6.1 at ultra can be our main workhorse while astra USE when situation needed"
3. about 23:05Z: "max means for thehighest quality and effort"

Which effort should the packaged worker use by default, and how should ultra be offered?

## Evidence

Tags: **[doc]** primary source read at a pinned revision; **[obs]** local fixture observation with the real bundled
native runtime, not provider execution; **[measured]** recorded provider runs; **[nv]** a claim read in source but not
verified on the installed build.

1. **[doc] What ultra sends on each root request.** At Codex `rust-v0.160.0` (`a956835d020762cb2b570053af06f643a11c0ecc`),
   `ModelInfo::resolve_reasoning_effort`
   ([protocol/src/openai_models/reasoning_effort.rs:10-40](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/protocol/src/openai_models/reasoning_effort.rs#L10-L40))
   sends ultra as the catalog's `multi_agent_reasoning_effort` when that value is listed and is not ultra, else max
   when listed, else the highest listed non-ultra level, else medium. The bundled catalog sets that value to `xhigh` for
   `gpt-6-astra` and `gpt-6.1-sol`
   ([models-manager/models.json:22,196](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/models-manager/models.json)).
   `core/src/client_tests.rs:1168-1184` tests that override; `:1186-1241` test the fallbacks, where max applies only
   without a valid override. Natively, Sol 6.1 at ultra therefore sends `xhigh` per request, while max sends max.
   This corrects the first brief's reading of `client_tests.rs:1180-1238` ("ultra reasons as deep as max per
   request") and agrees with both 2026-09-30 records, which found the same at 0.159.2.
2. **[doc] What ultra adds.** An effective ultra selects `MultiAgentMode::Proactive`, and any other effort selects
   `ExplicitRequestOnly`
   ([core/src/session/multi_agents.rs:96-104](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/core/src/session/multi_agents.rs#L96-L104)),
   under multi-agent V2 only (`:80-82`). The Sol and Astra catalog rows set `multi_agent_version: "v2"`
   (`models.json:21,195`), which `core/src/config/mod.rs:1606-1613` applies when no feature override is set. The
   `multi_agent_v2` feature itself is stable and off by default (`features/src/lib.rs:1336-1341`).
3. **[obs] Fixture with the real bundled runtime.** `examples/omniroute-codex-sdk/test_worker.py` drives the bundled
   0.160.0 runtime against a loopback fixture provider.
   - With the default max, the launch override, the turn effort, the preflight readback and the request all carry
     max. The `<multi_agent_mode>` fragment begins "Any earlier instruction enabling proactive multi-agent delegation
     no longer applies."
   - With `--effort ultra`, those sites carry ultra and the request carries `xhigh`. The fragment begins "Proactive
     multi-agent delegation is active."

   The fixture does not exercise OmniRoute.
4. **[doc] [nv] The gateway route.** The worker's id `cx/gpt-6.1-sol-max` takes the `gpt-6.1-sol` catalog row through
   the namespaced-suffix lookup (`models-manager/src/manager.rs:873-901`). OmniRoute's Codex executor gives a
   model-suffix effort precedence over the body's `reasoning.effort`
   ([diegosouzapw/OmniRoute `2f42a9ac1`, open-sse/executors/codex.ts:1419-1441](https://github.com/diegosouzapw/OmniRoute/blob/2f42a9ac19d1a247ec9ce5473b790843724b3061/open-sse/executors/codex.ts#L1419-L1441)).
   That is the release/v3.8.51 commit the port-20128 build is based on, and the build carries PR #15167
   (`manifests/stack.json`, `omniroute` row). For an ultra run, the `-max` route may therefore force max per request at
   the gateway. This is read in source only and not measured on the installed build.
5. **[doc] How far opt-in delegation fans out.** Without spawn overrides, children inherit the parent's model and
   effort (`core/src/agent/child_config.rs:196-209`). Under V2, a child of a V2-catalog model keeps the collaboration
   tools (`core/src/tools/spec_plan.rs:672-683`). A tree-wide limit on concurrently spawned agents bounds the fan-out,
   not depth (`core/src/agent/registry.rs:89-98`; `core/src/config/mod.rs:1615-1622,2760-2771`): three in the
   worker's private home. One native wait call defaults to 30 s and may ask for up to 3,600 s
   (`core/src/config/mod.rs:256-258`).
6. **[doc] SDK support.** `openai-codex==0.160.0` defines `ReasoningEffort.ultra`
   (`openai_codex/generated/v2_all.py:3694-3702`, re-exported by `openai_codex/types.py`).
7. **[measured] Fast tier.** [The tier probe receipt](../../evidence/receipts/omniroute-sdk-worker-fast-tier-20261003.json)
   records four runs at max through port 20128, two per tier, with an identical prompt. The fast tier gave 61.05 and
   61.26 output tokens per turn second against 32.63 and 32.79 standard (about 1.87 times); the probe's own wall times
   were 102.8-118.5 s against 194.2-211.3 s. Codex sends `fast` as the request id `priority`
   (`protocol/src/config_types.rs:528-551`; `core/config.schema.json:7632-7635`), and the Sol catalog row describes the
   tier as "2x speed, increased usage" (`models.json:340-349`).
8. **[doc] Independent convergence.** The runtime lane's open
   [PR #678](https://github.com/seathatflowsinourveins/native-agent-stack/pull/678) ("Expose native Ultra effort on
   the packaged SDK worker", head `c48347a4cdb72a24c7a0e2981c0b50222832e088`) independently makes the same three
   edits at launch, per turn and in `requested_effort`, and adds `--effort` with the choices max and ultra and a max
   default. It also records that the bundled Sol 6.1 metadata maps ultra to `xhigh`. This branch's `worker.py` is
   byte-identical to #678's head, so the two pull requests agree on that file.

## Alternatives

- **Ultra default**, this branch's first version (`5e01eebc7`). Rejected after the user's clarification. Natively, ultra
  on Sol 6.1 sends `xhigh` per request (points 1 and 3); only an unmeasured gateway rule [nv] could restore max.
  Quality comes first, and max is the deepest effort per request.
- **Max only, without an ultra option.** Rejected. A decomposable job can opt into native delegation explicitly, and
  the same option is what #678 exposes.
- **Ultra everywhere, including one-model lanes.** Rejected. Blind and one-model convergence lanes stay single
  isolated judgments at max; the landscape-sweep harness keeps that default and is unchanged.

## Decision

- The packaged worker defaults to `--effort max`, the deepest effort per request: quality first.
- Parallelism comes from fanning out several max workers, each with its own worktree and bounded task, rather than
  from ultra's delegation.
- `--effort ultra` is an explicit opt-in for a decomposable job. On Sol 6.1 it means `xhigh` per request plus
  automatic delegation to native sub-agents.
- Astra keeps its triggers through `--model cx/gpt-6-astra-max --effort max`: consequential architecture,
  conflicting primary evidence, or a failure unresolved after one bounded Sol repair.
- `service_tier = "fast"` is an optional, measured speed setting for a private worker home. It is not added to the
  starter template.
- `AGENTS.md` and its synced rule surfaces do not change.

## Exact changes

- `examples/omniroute-codex-sdk/worker.py`: `--effort {max,ultra}`, default max, applied to the launch override, the
  turn effort and `requested_effort`. The bytes equal #678's head. Dependencies and both PEP 723 locks are unchanged.
- `examples/omniroute-codex-sdk/test_worker.py`: six effort tests.
  - The default max reaches both call sites.
  - `--effort ultra` reaches both call sites with `xhigh` on the wire.
  - The two efforts select different native multi-agent modes.
  - Other values are refused.
  - A negative control restores the previous revision's hard-coded max (`worker.py:125,437` at `984bf4b27`) and fails
    the ultra acceptance.
  - The preflight readback holds for both values.

  The suite contains 31 tests.
- `examples/omniroute-codex-sdk/README.md`, `enhancements.md` and `.claude/skills/omniroute-runtime-worker/SKILL.md`.
- [The tier probe receipt](../../evidence/receipts/omniroute-sdk-worker-fast-tier-20261003.json), this record and their
  `manifests/evidence.json` entries.
- Unchanged: `AGENTS.md` and its synced copies, the `stack-worker` profile, every convergence-lane tool, the worker
  locks, and the source closure of `examples/omniroute-codex-sdk/checks.json` and the
  [0.160.0 refresh receipt](../../evidence/receipts/omniroute-sdk-worker-0160-20261003.json). Both are historical and
  name the previous worker and test bytes.

## Rollback

Ultra applies only when a caller passes `--effort ultra`, so no call changes behaviour unless it asks. Reverting the
branch restores the hard-coded max and the previous 25-test suite.

## Overturn condition

A measured quality comparison of ultra against max on a fixed task set, with the same prompts and acceptance oracle,
that shows ultra better at the same acceptance bar. A Codex change to `reasoning_effort.rs` or to Sol's catalog values,
or an OmniRoute change to suffix precedence, calls for re-reading the evidence; it does not by itself change the
default.

## Residuals

1. No quality comparison of ultra against max was run.
2. [nv] The gateway's effect on an ultra run through the `-max` route is unmeasured on the installed build. This
   change made no live model call.
3. The fan-out cost of the ultra opt-in is unmeasured. The worker's usage snapshot covers its own thread, not delegated
   threads.
4. The worker's 300 s default deadline and the Dagu graph's 600 s (`runtime-worker.yaml`) fit max. An opt-in ultra
   turn waits for its sub-agents, and one wait call may ask for up to 3,600 s.
5. The fast tier was measured in two rounds on one prompt, and its pool cost was not measured.
6. #678 overlaps this branch. `worker.py` is identical, but `test_worker.py` and `README.md` differ, so whichever pull
   request merges second must reconcile those two files, and `manifests/evidence.json` under the hot-file protocol.
