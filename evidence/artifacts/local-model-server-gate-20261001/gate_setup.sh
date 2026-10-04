#!/usr/bin/env bash
# One-time setup for the gate, run before PREREGISTRATION.md is written. Makes no model call:
# it imports the GGUF into the scratch Ollama store, lets `ollama launch codex` write the
# Codex profile and model catalog into the scratch home, derives the llama-server profile from that
# profile, and checks that both servers start and answer their health endpoints.
# Local wrapper, not an upstream component.
source "$(dirname "${BASH_SOURCE[0]}")/gate_env.sh"

OUT="$S/setup"; mkdir -p "$OUT" "$SCRATCH_HOME/.codex" "$S/work" "$S/runs"; chmod 700 "$OUT"
PIDFILE="$S/runs/pids.tsv"
RES="$S/research"

echo "setup start $(utc)"

# 1. Base Codex config (MCP server, approval mode, no web search, no analytics).
sed "s#<STATE>#$S#g" "$HERE/codex-config/config.toml.tmpl" >"$SCRATCH_HOME/.codex/config.toml"

# 2. Modelfile: the same GGUF, the library qwen3:8b template and parameters (registry blobs), 32k context.
{
  printf 'FROM %s\n' "$GGUF"
  printf 'TEMPLATE """'; cat "$RES/ollama-qwen3-8b-template.txt"; printf '"""\n'
  printf 'PARAMETER repeat_penalty 1\nPARAMETER stop <|im_start|>\nPARAMETER stop <|im_end|>\n'
  printf 'PARAMETER temperature 0.6\nPARAMETER top_k 20\nPARAMETER top_p 0.95\nPARAMETER num_ctx %s\n' "$CTX"
} >"$OUT/Modelfile"

# 3. Ollama: start, import, show, write the Codex profile, stop.
start_ollama "$OUT/ollama-setup-server.log"; OPID=$SERVER_PID
wait_ready "http://127.0.0.1:$PORT_OLLAMA/api/version" "$OPID"
curl -fsS -m 5 "http://127.0.0.1:$PORT_OLLAMA/api/version" >"$OUT/ollama-api-version.json"
if ollama_env "$OLLAMA_BIN" list 2>/dev/null </dev/null | grep -q "^$MODEL_ALIAS"; then
  echo "ollama model $MODEL_ALIAS already imported"
else
  ollama_env "$OLLAMA_BIN" create "$MODEL_ALIAS" -f "$OUT/Modelfile" >"$OUT/ollama-create.txt" 2>&1 </dev/null \
    && echo "ollama create exit=0" || echo "ollama create exit=$?"
fi
ollama_env "$OLLAMA_BIN" show "$MODEL_ALIAS" >"$OUT/ollama-show.txt" 2>&1 </dev/null || true
ollama_env "$OLLAMA_BIN" show --modelfile "$MODEL_ALIAS" >"$OUT/ollama-show-modelfile.txt" 2>&1 </dev/null || true
ollama_env "$OLLAMA_BIN" list >"$OUT/ollama-list.txt" 2>&1 </dev/null || true
# The launcher writes the Codex profile and the model catalog into the scratch home, then runs
# `codex --profile ollama-launch ... --version`, which prints the version and exits (no model call).
set +e
ollama_env timeout 90 "$OLLAMA_BIN" launch codex --model "$MODEL_ALIAS" --yes -- --version \
  >"$OUT/ollama-launch-version.txt" 2>&1 </dev/null
echo "ollama launch codex -- --version exit=$?" | tee -a "$OUT/ollama-launch-version.txt"
set -e
stop_server "$OPID" "$PIDFILE" setup ollama-serve
echo "ollama stopped; alive=$(kill -0 "$OPID" 2>/dev/null && echo yes || echo no)"

# 4. llama-server profile: the launcher's profile with only the provider id, name and base URL changed.
sed -e 's#ollama-launch#llamacpp-gate#g' -e 's#name = "Ollama"#name = "llama.cpp"#' \
    -e "s#127.0.0.1:$PORT_OLLAMA#127.0.0.1:$PORT_LLAMA#" \
    "$SCRATCH_HOME/.codex/ollama-launch.config.toml" >"$SCRATCH_HOME/.codex/llamacpp-gate.config.toml"

# 5. Codex reads the scratch config and lists the one MCP server (no model call).
set +e
hermetic "$CODEX_BIN" --profile ollama-launch mcp list >"$OUT/codex-mcp-list-ollama.txt" 2>&1 </dev/null
echo "codex mcp list (ollama-launch) exit=$?"
hermetic "$CODEX_BIN" --profile llamacpp-gate mcp list >"$OUT/codex-mcp-list-llamacpp.txt" 2>&1 </dev/null
echo "codex mcp list (llamacpp-gate) exit=$?"
set -e

# 6. llama-server: start, health, model list, stop (no inference request).
echo "gpu_used_mib_before_llama=$(gpu_used_mib)"
start_llama "$OUT/llama-setup-server.log"; LPID=$SERVER_PID
wait_ready "http://127.0.0.1:$PORT_LLAMA/health" "$LPID"
curl -fsS -m 5 "http://127.0.0.1:$PORT_LLAMA/v1/models" >"$OUT/llama-v1-models.json"
curl -fsS -m 5 "http://127.0.0.1:$PORT_LLAMA/props" >"$OUT/llama-props.json" || true
echo "gpu_used_mib_with_llama_loaded=$(gpu_used_mib)"
stop_server "$LPID" "$PIDFILE" setup llama-server
echo "llama-server stopped; alive=$(kill -0 "$LPID" 2>/dev/null && echo yes || echo no)"
echo "gpu_used_mib_after_stop=$(gpu_used_mib)"
echo "setup end $(utc)"
