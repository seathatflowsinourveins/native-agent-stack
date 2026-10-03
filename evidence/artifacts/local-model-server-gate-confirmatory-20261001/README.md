# Confirmatory run of the local model server gate, 2026-10-01

A second run of the gate in `../local-model-server-gate-20261001/`, with one change: the wall limit per run is
1,200 seconds instead of 300. The rule was fixed by the coordinator in `PREREGISTRATION.md` before any trial; its
sha256 was checked before the first trial and is in `receipt.json`, together with the per-run results, the wall
times, the tokens per second of each model call and the server log lines about tools. The first gate's folder and
verdict are not touched.

Evidence class: local integration check on one workstation (WSL2, CPU inference), not the new machine. The wrappers,
the scoring script and the prompt are local. The servers, the Codex client and the MCP server are unchanged upstream
releases.

## Files

| File | What it is |
| --- | --- |
| `PREREGISTRATION.md` | The coordinator's preregistration of this run (not edited by the worker) |
| `receipt.json` | Pins, commands, per-run results with wall time and tokens per second, per-arm verdict, deviations, limitations |
| `gate_env.sh` | Common settings. Differs from the first gate's copy in one line: `RUN_TIMEOUT_SEC=1200` |
| `gate_run.sh`, `gate_score.py` | One run, and the frozen pass rule. Byte-identical to the first gate's copies |
| `gate_setup.sh`, `codex-config/`, `Modelfile` | Setup without a model call, the Codex config template, the two profiles, the model catalog and the Ollama import. Byte-identical to the first gate's copies. Setup was not run again here: the state directory of the first gate was reused and every pinned file and config was re-verified by sha256 |
| `gate_collect.py` | Reporting only: copies the runs out of the state directory (sanitized event logs, scores, server log excerpts) and adds wall time, tokens per second per model call and the load average at each run's start |
| `runs/<label>/` | Per run: `events.jsonl`, `score.json`, `run-meta.txt`, `last-message.txt` (absent when the run ended without a final answer), `codex-stderr.txt`, `server-log-excerpt.txt` |
| `runs/pids.tsv`, `runs/load.tsv` | Every process started by this run, and the load average at each run's start |

Retained logs are trimmed to what the receipt cites. Host paths are replaced by `<STATE>`, `<HOME>` and `<SCRATCH>`,
the user name by `<user>`, and session identifiers by `<uuid>`.

## How to re-run

No `sudo`, no systemd unit, loopback ports 20231 and 20232, CPU only.

1. Make a private state directory outside every checkout and export it as `GATE_STATE`.
2. Download the pinned artifacts and check each sha256 against `receipt.json`:
   - `https://github.com/ggml-org/llama.cpp/releases/download/b11146/llama-b11146-bin-ubuntu-cuda-12.8-x64.tar.gz`
   - `https://github.com/ggml-org/llama.cpp/releases/download/b11146/cudart-llama-b11146-bin-ubuntu-cuda-12.8-x64.tar.gz`
   - `https://github.com/ollama/ollama/releases/download/v0.35.0/ollama-linux-amd64.tar.zst`
   - `https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/7c41481f57cb95916b40956ab2f0b139b296d974/Qwen3-8B-Q4_K_M.gguf`
     into `$GATE_STATE/models/`
3. Unpack both llama.cpp archives into `$GATE_STATE/llama/` with the CUDA runtime libraries next to
   `llama-b11146/llama-server`, and the Ollama archive into `$GATE_STATE/ollama/`.
4. `uv venv --python 3.13 "$GATE_STATE/mcp-venv"` and
   `uv pip install --python "$GATE_STATE/mcp-venv/bin/python" mcp-server-time==2026.8.18`.
5. `mkdir -p "$GATE_STATE/bin" && ln -s <path to the codex 0.159.3 binary> "$GATE_STATE/bin/codex"`.
6. Save the template layer of `https://registry.ollama.ai/v2/library/qwen3/manifests/8b` as
   `$GATE_STATE/research/ollama-qwen3-8b-template.txt`.
7. `bash gate_setup.sh` (no model call).
8. `bash gate_run.sh llama warmup-A; bash gate_run.sh ollama warmup-B`, then
   `for n in 1 2 3; do bash gate_run.sh llama A$n; bash gate_run.sh ollama B$n; done`.
   A run may take up to 1,200 seconds. `gate_run.sh` refuses to overwrite an existing run in `$GATE_STATE/runs/`.
9. `python3 gate_collect.py` copies the runs into `runs/` here and prints the per-run summary. An arm passes when its
   three scored runs have `"run_pass": true`.

## Acceptance checks for this folder

```
python3 -c "import json; json.load(open('evidence/artifacts/local-model-server-gate-confirmatory-20261001/receipt.json'))"
grep -rnE '/home/[a-z]|/mnt/[a-z]/Users' evidence/artifacts/local-model-server-gate-confirmatory-20261001/ ; test $? -eq 1
```

The folder is also scanned for the user name, the host name, scratch paths and identifiers shaped like session ids
(eight, four, four, four and twelve hexadecimal digits joined by hyphens); none may match.
