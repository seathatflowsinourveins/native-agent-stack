# Preregistration: confirmatory run of the local model server's first gate

Written 2026-10-01T23:53:40Z, before any trial of this run, by the foundation lane's coordinator (the model family whose deciders
picked llama.cpp for this slot). The first gate's result favoured Ollama; this run can confirm or refute it.

## Why a second run

The first gate (`../local-model-server-gate-20261001/`, preregistered 2026-10-01T23:12:24Z) returned llama-server 0 of 3
and Ollama 2 of 3 under its frozen pass rule. The MCP tool call completed in 0 of 3 llama-server runs and in 3 of 3
Ollama runs; the third Ollama run then hit the wrapper's 300-second wall limit before its final answer, on CPU at
3.30 tokens per second. That verdict stands and is not re-scored. The wall limit, not the tool handling, decided it, so
the gate is repeated with a limit that the observed generation speed does not reach.

## Unchanged from the first gate

Pins (llama.cpp release v0.5.0, build b11146, commit 7fe450e1; Ollama v0.35.0; codex-cli 0.159.3; Qwen3-8B Q4_K_M with
the recorded sha256; mcp-server-time 2026.8.18), the Codex scratch configuration and model catalog, the prompt, the one
MCP server, CPU execution on both arms, the 32768-token context, the sampling settings, one fresh server process per
run, and the wrapper and scoring scripts apart from the wall limit.

## Changed

- Wall limit per run: 1,200 seconds. Basis: the slowest completed first model call of the first gate took 4 minutes
  35 seconds; a passing run needs two model calls; twice that is 550 seconds, and the limit doubles it.
- Nothing else. Three scored runs per arm again, in the order warm-up A, warm-up B, A1, B1, A2, B2, A3, B3.

## Pass rule (unchanged)

A run passes when the Codex event log shows the `get_current_time` MCP tool call completed with a result and the final
answer contains that result. An arm passes the gate when all three scored runs pass. A run that reaches the wall limit
fails. No run is repeated, excluded or re-scored.

## What the result is used for (not applied by the worker)

Under the order both lanes agreed for a split slot, gates come first and an arm that fails a gate cannot win.
If llama-server fails and Ollama passes, both critics' rules give Ollama and the slot is settled by the gate.
If both fail, nothing is selected and the slot stays "not installed". If both pass, the gate does not separate the arms
and the primary comparison is needed.

## Records

Per run: the Codex exit code, whether the target tool was called and completed, the final answer, the wall time, the
tokens per second of each model call, and the server log lines about tools. The receipt goes in this folder; the first
gate's folder is not edited.
