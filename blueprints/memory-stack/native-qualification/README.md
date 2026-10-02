# Native memory qualification

This package implements the bounded evaluation workflow for `native_files`,
`ai_memory` and `hindsight`. It uses **Inspect AI 0.3.275** for task execution,
scoring and logs. Native Codex and Claude keep their own executor and login.
No API bridge, replacement agent runner, global hook installer or production
promotion runs automatically.

The current production memory selection remains ai-memory. Hindsight is fully
eligible to replace it after the measured gates; a Markdown source of truth is
not an automatic quality preference. This package has not established a winner.
The [preregistration](PREREGISTRATION.md) defines the comparison, held-out data,
operational gates and 20-session canary. The [runtime recipe](runtime/README.md)
contains pinned upstream commands, rollback and the isolated restore result.

## Run the checked integration

Use a unique private task directory for logs and responses. Run these commands
from this package; `TASK_SCRATCH` is that absolute directory, not a shared temp
filename. The locked environment uses official wheels; no source builds.

```sh
: "${TASK_SCRATCH:?Set an absolute unique private task directory first}"
uv sync --frozen --no-build --group dev
uv run --frozen python -m pytest
uv run --frozen inspect eval qualification.py@synthetic_pipeline \
  --model mockllm/model \
  -T cases="$PWD/corpus/dev/cases.jsonl" \
  -T sources="$PWD/corpus/dev/sources.json" \
  --log-dir "$TASK_SCRATCH/inspect-synthetic" --log-format json --display plain
```

The synthetic task checks the scorer and Inspect integration using authored
development answers. It performs no generation and cannot qualify a backend.
Inspect exit zero means the task ran; inspect its scores and errors separately.
The meaningful negative controls deliberately use wrong claims, missing evidence
and invalid citations and must be rejected by the same checks.

## Import actual native results

Collect native responses only after scope, effective hooks, startup context and
MCP endpoints are attested by the native configuration owner. The result schema
is in `qualification.py`; it binds each case to its arm, mode, split, frozen
configuration, output, evidence file/hash, runtime identity and accounting.
Unknown token/cost fields remain null. Adapter-supplied source hashes come from
the actual retrieved bytes; do not ask a model to calculate checksums or expose
the gold answer registry to the model.

```sh
: "${CASE_FILE:?}" "${SOURCE_REGISTRY:?}" "${RESULT_FILE:?}" "${TASK_SCRATCH:?}"
uv run --frozen inspect eval qualification.py@native_qualification \
  --model mockllm/model \
  -T cases="$CASE_FILE" -T sources="$SOURCE_REGISTRY" -T results="$RESULT_FILE" \
  -T arm=hindsight -T mode=tuned_pipeline -T split=holdout \
  -T corpus_freeze_id=synthetic-native-qualification-20261002-v1 \
  -T corpus_manifest="$PWD/corpus-manifest.json" \
  -T corpus_manifest_sha256=44d9b260e4240986b4295af2555659c40d92e1263d621c9da58b599922762b12 \
  --log-dir "$TASK_SCRATCH/inspect-native" --log-format json --display plain
```

Repeat for each arm/mode with its own native result file. The offline solver
imports recorded responses; it never calls `generate`. Run the common-retrieval
measurement with the same answer model and evidence budget. Evaluate each
supported tuned pipeline separately. Tune only the 12 development cases, then
freeze the configuration before releasing the 60-case holdout to the evaluator.
Base64 packaging and hashes protect integrity and accidental exposure; they are
not encryption, access control or proof of an unseen production workload.

The primary comparison uses tuned-pipeline logs:

```sh
: "${NATIVE_FILES_LOG:?}" "${AI_MEMORY_LOG:?}" "${HINDSIGHT_LOG:?}" "${GATE_RECEIPTS:?}" "${TASK_SCRATCH:?}"
uv run --frozen python qualification.py \
  "$NATIVE_FILES_LOG" "$AI_MEMORY_LOG" "$HINDSIGHT_LOG" \
  --gates "$GATE_RECEIPTS" \
  --corpus-freeze-id synthetic-native-qualification-20261002-v1 \
  --corpus-manifest-sha256 44d9b260e4240986b4295af2555659c40d92e1263d621c9da58b599922762b12 \
  --output "$TASK_SCRATCH/decision.json"
```

For the single preregistered extension, provide the original logs plus logs for
60 new cases, keep the same frozen settings, and add `--look extension
--previous "$TASK_SCRATCH/initial-decision.json"`. Freeze a separate extension
manifest under the same corpus ID with `parent_manifest_sha256` pointing to the
initial manifest. Pass the extension manifest's hash to
`--corpus-manifest-sha256`; the prior decision binds the original 60. The comparison reports paired
95% descriptive intervals and more conservative simultaneous decision intervals
for the planned comparisons/looks. Common-retrieval results are diagnostic.

Receipt validation checks structure, identities, hashes and consistency. It
cannot authenticate a producer's assertions or turn a self-reported `passed`
field into observed native behavior. Independent source-grounded receipt review
and blind cross-family convergence remain required. A decision file does not
install a backend or change production settings.

## Evidence and present boundaries

- [Implementation validation](VALIDATION.md): 20 regression tests, 12 synthetic
  Inspect samples, one scoped unchanged upstream test and bounded source review.
- [Pinned artifacts](runtime/artifacts.json): ai-memory 2.5.2, Hindsight 0.10.2,
  coding-agents 0.8.0 and Inspect 0.3.275. Repository license observations do not
  substitute for dependency/model license qualification.
- [Actual isolated restore](runtime/observed-20261002.json): wiki page and
  DB-only pending message restored and read after restart; external config
  restored separately. Initial failures and publication redactions are retained.
- Synthetic cases and scorer checks establish fixture behavior, not production
  quality. Historical failed native compaction, rerank latency and synthesis
  checks remain open; this package does not relabel them.
- [Native prerequisites](runtime/native-gates-20261002.json): native hooks have
  not been rewired by this package. The local gateway's models
  endpoint returned 401, and `secret has OMNIROUTE_API_KEY` returned nonzero on
  this host. No authenticated cross-family vote was obtained. The maintained
  repository requires the coordinator to start those votes through its gateway;
  native credentials are not imported into it.
- Representative native lifecycle, real comparative runs, blind convergence and
  the 20 genuine-session/two-restart canary still gate a selection change. Other
  hosts require their own acceptance. Whole-task usage and net savings are unknown.

## Upstream basis

The local adaptation exists because native Codex/Claude results must be scored
without redirecting their authentication or generation through an API bridge.
Inspect already provides the runner, typed samples, solvers, scorers and logs;
the project-specific code adds only its evidence and decision contracts.

- [Inspect source at c05398d](https://github.com/UKGovernmentBEIS/inspect_ai/tree/c05398d897affcb85bd4cb9d10a7c03e1779a18e),
  [official 0.3.275 distribution](https://pypi.org/project/inspect-ai/0.3.275/),
  [upstream recorded-output solver test](https://github.com/UKGovernmentBEIS/inspect_ai/blob/c05398d897affcb85bd4cb9d10a7c03e1779a18e/tests/solver/test_solver.py#L47).
- [LongMemEval-V2](https://arxiv.org/abs/2605.12493) informs the workload categories;
  this authored fixture is not that benchmark and its scores are not comparable.
- [Agent memory systems characterization](https://arxiv.org/abs/2606.06448)
  motivates separating construction, retrieval and generation costs.
- The [repository evidence policy](../../../docs/acceptance-evidence-policy.md)
  separates unchanged upstream tests, native operations, local integrations,
  synthetic fixtures and structural validation.
