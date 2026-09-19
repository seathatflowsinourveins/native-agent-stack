# Paired native runtime acceptance — September 19, 2026

**The real native pair completed.** After interactive Codex sign-in, the new hash-locked SDK ran the existing manual Dagu pipeline: fresh LEAN simulation → DuckDB/Parquet packet → GPT-6 Astra report → Claude Opus 5 critique. Native Dagu history reports both preparation and model workflow **succeeded**. [Machine-readable receipt](receipt.json).

This supersedes the earlier account blocker for this host and task. It does not transfer the host's authentication to another machine or certify every optional service.

## Direct native results

| Native step | Observed result |
| --- | --- |
| uv compile/sync/check | 36 accepted distributions; required hashes; uncached reinstall and dependency check passed |
| LEAN launcher through native .NET | Exit 0; **3,943 data points**, **3 simulated orders**, zero stderr bytes |
| Dagu prepare-evidence | Native status succeeded; **5 cited facts**, **1,976-byte packet** |
| DuckDB data path | **6 events / 3 orders**, Parquet write/read; historical XNYS session |
| Official Codex SDK, native GPT-6 Astra | Completed in **14,953 ms**; 2 evidence entries and 2 findings |
| Native Claude Opus 5 | Completed in **10,538 ms**; 2 evidence entries and 3 findings; zero exposed tools, 16 hook events |
| Dagu research-pair history | Succeeded; **19:41:23–19:41:50 UTC** |
| Independent result review | Packet/prompt/report hashes and all three LEAN source hashes agree; exact accepted Astra report present in Claude prompt |

The formal report validator checks cited values, units and research-only scope. Independent review found no blocking handoff or numeric issue. Claude did flag Astra's incomplete date citation and irrelevant amendment-history wording; both original reports remain visible in [Astra's report](astra.report.json) and [Claude's critique](claude.report.json). Passing the structural checks is not a claim of flawless analysis.

## Native commands

Use the exact environment selection in [the existing native workflow](../../blueprints/us-equities/research-runtime/README.md), with a new private run directory and native sign-in. The same published commands were used here:

```sh
"$DOTNET" "$LEAN_LAUNCHER" --config "$LEAN_CONFIG" \
  --environment backtesting --algorithm-location "$LEAN_ALGORITHM" \
  --data-folder "$LEAN_DATA" --results-destination-folder "$LEAN_RESULTS"
"$DAGU" validate --dagu-home "$RESEARCH_HOME" \
  "$STACK_REPO/blueprints/us-equities/research-runtime/prepare-evidence.yaml"
"$DAGU" validate --dagu-home "$RESEARCH_HOME" \
  "$STACK_REPO/blueprints/us-equities/research-runtime/research-pair.yaml"
"$DAGU" start --context local --dagu-home "$RESEARCH_HOME" --run-id "$PREP_RUN_ID" \
  "$STACK_REPO/blueprints/us-equities/research-runtime/prepare-evidence.yaml"
"$DAGU" start --context local --dagu-home "$RESEARCH_HOME" --run-id "$MODEL_RUN_ID" \
  "$STACK_REPO/blueprints/us-equities/research-runtime/research-pair.yaml"
"$DAGU" history --context local --dagu-home "$RESEARCH_HOME" --format json research-pair
```

The full guide's stdout/stderr capture and explicit environment variables are required; the short commands above identify the native operations, not an unattended installer. The paired DAG has no automatic retry and will not silently substitute an independent Claude run after Astra fails.

## Exact usage and selected-text reduction

| Native usage category | Astra | Claude |
| --- | ---: | ---: |
| Input | 20,487 including cache reads | 2 ordinary input |
| Cache creation | 0 | 11,142 |
| Cache reads | 6,400, included in input | 3,156, separate |
| Output | 289 | 1,993 |
| Reasoning/thinking | 0 | 852, included in output |
| Total native tokens | **20,776** | **16,293** |

Combined native worker usage was **37,069 tokens**. These totals exclude the coordinator and separate research/review workers. Cache and thinking subsets must not be added twice.

Upstream `gpt-tokenizer 3.4.0`, `o200k_base`, measured the fresh three-file source selection at **4,823 tokens**, versus **640 tokens** for [the packet](packet.json): **4,183 fewer selected-text tokens, 86.73% less**.

```sh
TOKENIZER_PREFIX="$TOKENIZER_PREFIX" node \
  "$STACK_REPO/blueprints/us-equities/research-runtime/measure_packet.cjs" \
  "$LEAN_RESULTS" "$RESEARCH_OUTPUT/packet.json"
```

This is a lossy selection for the simulation-summary question. Native client instructions, hooks and context account for additional model input. It is **not measured net provider savings**, a billing reduction or a quality-matched experiment. The earlier 4,813 → 643 measurement belongs to a different dated source packet.

## Observability and remaining gates

[The paired observation receipt](observation.json) reconciles all six Astra metric categories and all four Claude categories with native usage. Astra's process joins 18 redacted native Loki records and one SDK result observation; Claude's process joins 51 redacted records, including one matching API event. Seven of seven monitoring targets were healthy. Claude correlation uses its unique process/time/model and exact usage categories because its native session identifier is not retained in Loki. The earlier [pre-login failure observation](../pre-login-observation.json) remains separate: one redacted failure record, unknown usage, no inference. Successful sign-in did not rewrite that history.

The adopted hosting mode is still manual local Dagu on WSL. All orders here were in the unchanged bundled historical LEAN simulation; no paper/live broker was connected. Current data entitlement, strategy/risk specification, retrieval-quality improvements, independent recovery, unattended hosting and causal provider-savings evaluation remain in [the canonical gate ledger](../../catalogs/us-equities/convergence-review.json).
