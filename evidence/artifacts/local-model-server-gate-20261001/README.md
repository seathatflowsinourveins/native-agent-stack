# Local model server gate, 2026-10-01

One preregistered pass-or-fail gate on one workstation (WSL2): the same fixed Codex task, which must call one tool from
one MCP server, against llama.cpp's `llama-server` (arm A) and against Ollama (arm B), both serving the same GGUF file.
The result, the per-run table and the cited log lines are in `receipt.json`. The rule that was fixed before the first
model call is in `PREREGISTRATION.md`; its sha256 is in the receipt.

Evidence class: local integration check. The wrappers, the scoring script and the prompt are local. The servers, the
Codex client and the MCP server are unchanged upstream releases. This is one workstation, not the new machine.

## Files

| File | What it is |
| --- | --- |
| `PREREGISTRATION.md` | Pins, serving settings, Codex configuration, prompt, run order and the frozen pass rule |
| `receipt.json` | Pins with sha256, commands, per-run results, per-arm verdict, gate outcome, deviations, limitations |
| `gate_env.sh`, `gate_setup.sh`, `gate_run.sh` | Local wrappers: common settings, one-time setup without a model call, one run |
| `gate_score.py` | Applies the frozen pass rule to one `codex exec --json` event log |
| `codex-config/` | The shared Codex config template, the two profiles and the model catalog (`<STATE>` stands for the state directory) |
| `Modelfile` | The Ollama import of the same GGUF with the library template and parameters |
| `setup/` | Setup output that makes no model call: `ollama show`, the launcher output, `codex mcp list`, model listing, package freeze |
| `runs/<label>/` | Per run: `events.jsonl` (Codex events), `score.json`, `run-meta.txt`, `last-message.txt`, `codex-stderr.txt`, `server-log-excerpt.txt` |
| `runs/pids.tsv` | Every process started by this work (label, role, PID, child PIDs seen at stop) |

Retained logs are trimmed to what the receipt cites. Host paths are replaced by `<STATE>`, `<HOME>` and `<SCRATCH>`,
the user name by `<user>`, and session identifiers by `<uuid>`.

## How to re-run

All steps run without `sudo`, without a systemd unit and on loopback ports 20231 and 20232.

1. Make a private state directory outside every checkout and export it:
   `mkdir -m 700 -p "$HOME/.local/state/model-server-gate" && export GATE_STATE="$HOME/.local/state/model-server-gate"`
2. Download the pinned artifacts and check each sha256 against `PREREGISTRATION.md`:
   - `https://github.com/ggml-org/llama.cpp/releases/download/b11146/llama-b11146-bin-ubuntu-cuda-12.8-x64.tar.gz`
   - `https://github.com/ggml-org/llama.cpp/releases/download/b11146/cudart-llama-b11146-bin-ubuntu-cuda-12.8-x64.tar.gz`
   - `https://github.com/ollama/ollama/releases/download/v0.35.0/ollama-linux-amd64.tar.zst`
   - `https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/7c41481f57cb95916b40956ab2f0b139b296d974/Qwen3-8B-Q4_K_M.gguf`
     into `$GATE_STATE/models/`
3. Unpack: both llama.cpp archives into `$GATE_STATE/llama/` and move the CUDA runtime libraries next to
   `llama-b11146/llama-server`; the Ollama archive into `$GATE_STATE/ollama/` (`tar --zstd -x`, or stream it through
   the Python `zstandard` package when `zstd` is not installed).
4. MCP server: `uv venv --python 3.13 "$GATE_STATE/mcp-venv"` then
   `uv pip install --python "$GATE_STATE/mcp-venv/bin/python" mcp-server-time==2026.8.18` (set `UV_CACHE_DIR` inside the
   state directory to keep the cache there).
5. Codex: `mkdir -p "$GATE_STATE/bin" && ln -s <path to the codex 0.159.3 binary> "$GATE_STATE/bin/codex"`.
6. Ollama library template: read the template layer digest from
   `https://registry.ollama.ai/v2/library/qwen3/manifests/8b` and save that blob as
   `$GATE_STATE/research/ollama-qwen3-8b-template.txt`.
7. Setup, no model call: `bash gate_setup.sh`. It imports the GGUF into Ollama, lets `ollama launch codex` write the
   Codex profile and model catalog into the scratch home, derives the llama-server profile and checks both servers.
8. Runs, one server at a time, in the preregistered order:
   `bash gate_run.sh llama warmup-A; bash gate_run.sh ollama warmup-B` and then
   `for n in 1 2 3; do bash gate_run.sh llama A$n; bash gate_run.sh ollama B$n; done`
9. Each run writes `$GATE_STATE/runs/<label>/score.json`. An arm passes when its three scored runs have
   `"run_pass": true`.

To serve from a GPU instead of the CPU, remove `CUDA_VISIBLE_DEVICES=-1` from `gate_env.sh` and replace
`--device none -ngl 0` with `-ngl 99`. The gate recorded here ran on the CPU; see the receipt for the reason.

## Acceptance checks for this folder

```
python3 -c "import json; json.load(open('evidence/artifacts/local-model-server-gate-20261001/receipt.json'))"
grep -rnE '/home/[a-z]|/mnt/[a-z]/Users' evidence/artifacts/local-model-server-gate-20261001/ ; test $? -eq 1
```
