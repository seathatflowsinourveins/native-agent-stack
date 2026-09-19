# Native research runtime acceptance — September 19, 2026

**Later paired acceptance:** native sign-in restored Codex readiness and the
existing workflow completed fresh LEAN → Dagu → DuckDB → Astra → Claude with
the recreated SDK. See [the paired receipt and native results](../../../adoption/paired/README.md).
The standalone run and quota boundary below remain dated historical evidence.

The local path now runs **LEAN → Dagu → DuckDB/Parquet → a cited packet → native
Claude Opus 5**, with native hooks and recorded usage. The separate **GPT-6 Astra
→ Claude critique** workflow is implemented and validated, but its new paired
model execution is pending Linux Codex allowance/sign-in. An earlier successful
Astra SDK run remains [separate historical evidence](../workers/README.md).

This is research infrastructure. The LEAN sample is the upstream historical SPY
example, not a selected strategy or broker execution. The [SEC path](../financial-data/README.md)
stopped on its first HTTP 403; no newly downloaded SEC dataset or financial report
is claimed. [Encrypted backup acceptance](../hosting/backup/README.md) covers
22 selected public files on this host, not live database or off-host recovery.

## Actual results

| Native operation | Result |
|---|---|
| LEAN launcher, fresh result directory | Completed; 3,943 data points; 3 simulated orders; 6 order events |
| `dagu validate` on both final recipes | Exit 0; unsupported entrypoint `name` fields removed after the initial validation failure |
| `dagu start` then `dagu history` | Final `prepare-evidence` run `succeeded`; both packet and order-table steps completed |
| DuckDB/Parquet | 6 events, 3 distinct order IDs; 3 submitted and 3 filled **simulation** events |
| Cited packet | 5 facts, 1,976 bytes; source hashes retained, date window derived from native summary |
| Native Claude Opus 5 independent report | Terminal `success`; 0 exposed model tools; 16 hook events; 2 exact facts and 3 cited findings accepted |
| Native Claude usage | 2 ordinary input + 13,018 cache creation + 531 cache read + 1,032 output = **14,583 tokens** |
| Selected-text measurement | **4,813 → 643 tokens**, 4,170 fewer / 86.64% less selected text |
| New native Astra readiness | Exact model available, ordinary allowance false, primary window 100%; inference not submitted |
| SEC acquisition | First request HTTP 403; 0 source snapshots, 0 ready datasets; no automatic retry |

The tokenizer is upstream `gpt-tokenizer@3.4.0`, `o200k_base`. This is lossy
selection for one summary question, not equal-information compression or a
quality-matched provider comparison. Claude's 423 thinking tokens are already
inside its 1,032 output tokens. Its 531 cache-read tokens are reuse, not a measured
net saving. Native client instructions/hooks explain why a 643-token packet does
not equal the full model input. Parent/coordinator usage remains separate.

The [receipt](receipt.json) retains hashes, normalized native results and the
uncompleted boundaries. Private native logs remain private; the public receipt
does not claim replaying it repeats inference.

## Native workflow

Use the existing [pinned SDK environment](../workers/README.md), [LEAN build](../engine/resolution.md),
and [Dagu installation/configuration](../hosting/README.md). Set paths for your
host; none below is an account credential. `RESEARCH_WORKSPACE` must be a project
already explicitly adopted by the native clients. Keep `RESEARCH_OUTPUT` outside
Git and choose a fresh directory/run ID for each attempt.

```sh
mkdir -m 700 "$RESEARCH_OUTPUT"
mkdir -m 700 "$LEAN_RESULTS"
"$DOTNET" "$LEAN_LAUNCHER" --config "$LEAN_CONFIG" \
  --environment backtesting --algorithm-location "$LEAN_ALGORITHM" \
  --data-folder "$LEAN_DATA" --results-destination-folder "$LEAN_RESULTS" \
  > "$LEAN_RESULTS/stdout.txt" 2> "$LEAN_RESULTS/stderr.txt"

"$DAGU" validate --dagu-home "$RESEARCH_HOME" \
  "$STACK_REPO/blueprints/us-equities/research-runtime/prepare-evidence.yaml"
"$DAGU" validate --dagu-home "$RESEARCH_HOME" \
  "$STACK_REPO/blueprints/us-equities/research-runtime/research-pair.yaml"

env -i HOME="$HOME" PATH="$NATIVE_RUNTIME_PATH" \
  STACK_REPO="$STACK_REPO" SDK_ENV="$SDK_ENV" LEAN_RESULTS="$LEAN_RESULTS" \
  RESEARCH_OUTPUT="$RESEARCH_OUTPUT" \
  "$DAGU" start --context local --dagu-home "$RESEARCH_HOME" --run-id "$PREP_RUN_ID" \
  "$STACK_REPO/blueprints/us-equities/research-runtime/prepare-evidence.yaml"
"$DAGU" history --context local --dagu-home "$RESEARCH_HOME" --format json prepare-evidence
```

The LEAN preparation requires the selected sample's summary/order-event filenames
and a captured `stdout.txt` in `LEAN_RESULTS`. Capture the launcher's stdout and
stderr there. Engine commit identity is recorded separately from packet facts;
the helper does not infer a source build from arbitrary result files.

Inspect native allowance before inference. Never copy an authentication store or
silently replace a subscription route with a paid API route:

```sh
"$SDK_ENV/bin/python" "$STACK_REPO/blueprints/us-equities/workers/native_worker.py" inspect \
  --codex-bin "$NATIVE_CODEX_BIN" --codex-home "$NATIVE_CODEX_HOME" \
  --workspace "$RESEARCH_WORKSPACE" --receipt "$NEW_PRIVATE_READINESS_RECEIPT"
# Only when native sign-in is needed:
env CODEX_HOME="$NATIVE_CODEX_HOME" "$NATIVE_CODEX_BIN" login --device-auth
```

After readiness is true, the paired workflow uses the official Codex SDK and
the native Claude CLI. All variable names below are explicitly allowed by the
updated [Dagu configuration example](../hosting/config.yaml.example). The active
local configuration preserved its private authentication and disabled UI run/edit
permissions while adding these environment names.

```sh
env -i HOME="$HOME" PATH="$NATIVE_RUNTIME_PATH" \
  STACK_REPO="$STACK_REPO" SDK_ENV="$SDK_ENV" RESEARCH_OUTPUT="$RESEARCH_OUTPUT" \
  RESEARCH_WORKSPACE="$RESEARCH_WORKSPACE" NATIVE_CODEX_HOME="$NATIVE_CODEX_HOME" \
  NATIVE_CODEX_BIN="$NATIVE_CODEX_BIN" NATIVE_CLAUDE_BIN="$NATIVE_CLAUDE_BIN" \
  NATIVE_RUNTIME_PATH="$NATIVE_RUNTIME_PATH" SDK_OBSERVATION_DIR="$SDK_OBSERVATION_DIR" \
  "$DAGU" start --context local --dagu-home "$RESEARCH_HOME" --run-id "$MODEL_RUN_ID" \
  "$STACK_REPO/blueprints/us-equities/research-runtime/research-pair.yaml"
"$DAGU" history --context local --dagu-home "$RESEARCH_HOME" --format json research-pair
```

For an explicitly independent Claude report, the exercised supervisor command is:

```sh
"$SDK_ENV/bin/python" "$STACK_REPO/blueprints/us-equities/research-runtime/run_worker.py" claude \
  --independent --packet "$RESEARCH_OUTPUT/packet.json" --run-dir "$RESEARCH_OUTPUT" \
  --workspace "$RESEARCH_WORKSPACE" --codex-home "$NATIVE_CODEX_HOME" \
  --codex-bin "$NATIVE_CODEX_BIN" --claude-bin "$NATIVE_CLAUDE_BIN" \
  --sdk-python "$SDK_ENV/bin/python" --runtime-path "$NATIVE_RUNTIME_PATH" \
  --observation-dir "$SDK_OBSERVATION_DIR"
```

It invokes the upstream command directly, with the bounded prompt on stdin:

```sh
claude -p --model claude-opus-5 --output-format stream-json --verbose \
  --include-hook-events --max-turns 2 --tools '' --disallowedTools '*' \
  --permission-mode dontAsk --permission-prompts none
```

Independent mode is never a silent fallback. The paired DAG omits it and requires
the preceding Astra receipt/report to match the packet and report hashes.
Do not reuse a directory already reserved for a standalone Claude run for the
paired workflow: each role is accepted only once per directory, including failure.

Reproduce the text count with the installed upstream tokenizer:

```sh
TOKENIZER_PREFIX="$ISOLATED_TOKENIZER_PREFIX" node \
  "$STACK_REPO/blueprints/us-equities/research-runtime/measure_packet.cjs" \
  "$LEAN_RESULTS" "$RESEARCH_OUTPUT/packet.json"
```

## Boundaries and persistence

The native client registrations, lifecycle hooks, local retrieval services,
observability and Dagu service persist for future sessions on this adopted host.
These new recipes are explicit manual research runs; they do not inject a whole
catalog into every model prompt, run a scheduler or change unrelated projects.
No further Desktop restart is needed for the already verified direct Context
Mode path. A restart cannot restore exhausted account allowance or SEC access.

Workers keep the native account home and hooks. A minimal child environment
omits inherited API/broker/service secrets, but it is not an operating-system
security boundary. Claude exposes no model tools; registered lifecycle hooks
still execute. Astra uses SDK read-only/deny-all and rejects unexpected tool/action
result items; that final audit does not prevent already-authorized MCP calls.

Prompts, packets and accepted reports have size limits; subprocess groups have
deadlines and cancellation cleanup, including TERM-ignoring descendants. Raw
stdout/stderr are private but not byte-capped. Detached processes outside the
owned process group and remote work are not a general containment guarantee.
No automatic retry, paid fallback, model-change fallback or broker order exists.

The report checker validates exact numerical values, units, citation IDs, cutoff
and scope. It does not establish that every prose claim follows from its citations,
prove profitability, perform investment diligence or authorize trading. Local
hosting still needs a separately chosen destination and operational acceptance
for always-on/off-host service. The [gap ledger](../gap-resolution.md) retains
data rights, strategy/risk specification, broker reconciliation and paper execution.
