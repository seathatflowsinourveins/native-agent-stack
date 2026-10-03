#!/usr/bin/env bash
# Measurement distribution only. Prepare gate G0 of amendment 3a for one second-server arm: copy the confirmatory
# model-server gate from the repository clone, check the originals against the frozen hashes, apply the declared
# differences to gate_env.sh by exact replacements (each must change exactly one line), derive the Codex profile and
# model description as the gate derives its llama profile, and hash everything before the warm-up. Loads no model.
# usage: bash -s <S1|S1b|S2>
set -euo pipefail
ARM="${1:?arm}"
export PATH="$HOME/.local/share/mise/shims:$HOME/.local/bin:/usr/lib/wsl/lib:$PATH"
M="$HOME/measure"; PRISM="$M/prism-llama/llama-prism-b10743-adfffbe-bin-linux-cuda-12.8-x64"
CUDALIBS=$(find "$M/prism-llama/cuda12-runtime/site/nvidia" -type d -name lib | sort | tr '\n' ':')
case "$ARM" in
  S1)  FILE=Ternary-Bonsai-2-27B-PTQ1_0.gguf; WANT=53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3
       ALIAS=g0-bonsai-ptq1; SAMPLING='--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.05' ;;
  S1b) FILE=Ternary-Bonsai-2-27B-PQ2_0.gguf; WANT=3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1
       ALIAS=g0-bonsai-pq2; SAMPLING='--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.05' ;;
  S2)  FILE=Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf; WANT=1333c6ea70ef348d4ac6d62732772e8ad6571ac5b3754c14ed54f1a0d904a786
       ALIAS=g0-swift-iq3s; SAMPLING='--temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --presence-penalty 0.0 --repeat-penalty 1.0' ;;
  *) echo "unknown arm $ARM"; exit 2 ;;
esac
S="$M/g0/$ARM"; G="$S/gate"; OUT="$S/setup"; HOME_S="$S/scratch-home"
[ ! -e "$S/runs" ] || { echo "state for $ARM already exists; not prepared twice"; exit 2; }
mkdir -p "$G" "$S/bin" "$S/work" "$S/runs" "$OUT" "$HOME_S/.codex"; chmod 700 "$S"
SRC="$HOME/code/native-agent-stack/evidence/artifacts/local-model-server-gate-confirmatory-20261001"
echo "setup $ARM start $(date -u +%Y-%m-%dT%H:%M:%SZ); clone at $(git -C "$HOME/code/native-agent-stack" rev-parse --short=9 HEAD)"
got=$(sha256sum "$M/models/$FILE" | cut -c1-64); [ "$got" = "$WANT" ] || { echo "model file hash differs: $got"; exit 1; }
echo "model file $FILE hash matches"
cp "$SRC"/gate_env.sh "$SRC"/gate_run.sh "$SRC"/gate_score.py "$SRC"/gate_collect.py "$G/"; cp -r "$SRC/codex-config" "$G/"
check() { [ "$(sha256sum "$1" | cut -c1-64)" = "$2" ] || { echo "original differs from the frozen hash: $1"; exit 1; }; }
check "$G/gate_score.py" 44f19bcc4c43c5e40c2b737423adac6b1b0cd008dcfb4f06753049ca14672da8
check "$G/gate_run.sh" 18b12909589529f9426a6674f7168bf005860b05715e9563495011603de102da
check "$G/gate_env.sh" 2fc970549afd6daa324706699290084d017323b38a6983c49f7728d1a5291ecc
echo "gate originals match the frozen hashes"
cp "$G/gate_env.sh" "$OUT/gate_env.orig.sh"
one() { # description, sed expression: must change exactly one line
  cp "$G/gate_env.sh" "$OUT/.before"; sed -i -e "$2" "$G/gate_env.sh"
  n=$(diff "$OUT/.before" "$G/gate_env.sh" | grep -c '^<' || true)
  [ "$n" -eq 1 ] || { echo "replacement '$1' changed $n lines, expected 1"; exit 1; }
  echo "replaced: $1"
}
one "model alias"   "s#^MODEL_ALIAS=gate-qwen3-8b\$#MODEL_ALIAS=$ALIAS#"
one "model file"    "s#^GGUF=\"\\\$S/models/Qwen3-8B-Q4_K_M.gguf\"\$#GGUF=\"$M/models/$FILE\"#"
one "context"       's#^CTX=32768$#CTX=64000#'
one "server binary" "s#^LLAMA_BIN=\"\\\$S/llama/llama-b11146/llama-server\"\$#LLAMA_BIN=\"$PRISM/llama-server\"#"
one "library path"  "s#^HERMETIC=(env -i PATH=\"\\\$S/bin:/usr/bin:/bin\" #HERMETIC=(env -i PATH=\"\$S/bin:/usr/bin:/bin\" LD_LIBRARY_PATH=\"$PRISM:${CUDALIBS}/usr/lib/wsl/lib\" #"
one "GPU visible"   's#"\${HERMETIC\[@\]}" CUDA_VISIBLE_DEVICES=-1 "\$LLAMA_BIN"#"${HERMETIC[@]}" "$LLAMA_BIN"#'
one "server flags"  "s#-c \"\\\$CTX\" -np 1 --device none -ngl 0 --jinja --temp 0.6 --top-k 20 --top-p 0.95 --repeat-penalty 1.0 --verbose#-c \"\$CTX\" -np 1 -ngl 99 -fa on -ctk f16 -ctv f16 --jinja $SAMPLING --verbose#"
rm -f "$OUT/.before"
diff "$OUT/gate_env.orig.sh" "$G/gate_env.sh" > "$OUT/gate_env.diff" || true
echo "gate_env.sh: $(grep -c '^<' "$OUT/gate_env.diff") lines differ from the original"
bash -n "$G/gate_env.sh" && echo "adapted gate_env.sh parses"
# client binary and the time server, as the gate's README prepares them
ln -sf "$(readlink -f "$(command -v codex)")" "$S/bin/codex"; "$S/bin/codex" --version | head -n 1
uv venv --quiet --python 3.13 "$S/mcp-venv" && uv pip install --quiet --python "$S/mcp-venv/bin/python" mcp-server-time==2026.8.18
echo "mcp-server-time: $("$S/mcp-venv/bin/python" -c 'import importlib.metadata as m; print(m.version("mcp-server-time"))')"
sed "s#<STATE>#$S#g" "$G/codex-config/config.toml.tmpl" > "$HOME_S/.codex/config.toml"
# profile and model description: written by Ollama's launcher for the control model, then renamed as the gate does
OLLAMA_REAL=$(mise which ollama 2>/dev/null || command -v ollama)
set +e
env -i PATH="$S/bin:$(dirname "$OLLAMA_REAL"):/usr/bin:/bin" HOME="$HOME_S" CODEX_HOME="$HOME_S/.codex" LANG=C.UTF-8 TZ=UTC \
  OLLAMA_HOST=127.0.0.1:21434 timeout 90 "$OLLAMA_REAL" launch codex --model gpt-oss:20b --yes -- --version \
  > "$OUT/ollama-launch-version.txt" 2>&1 < /dev/null
echo "ollama launch codex -- --version exit=$?"; tail -n 2 "$OUT/ollama-launch-version.txt" | cut -c1-160
set -e
[ -f "$HOME_S/.codex/ollama-launch.config.toml" ] || { echo "the launcher wrote no profile"; ls -la "$HOME_S/.codex" | cut -c1-120; exit 1; }
cp "$HOME_S/.codex/ollama-launch.config.toml" "$OUT/ollama-launch.config.orig.toml"; cp "$HOME_S/.codex/model.json" "$OUT/model.orig.json"
sed -e 's#ollama-launch#llamacpp-gate#g' -e 's#name = "Ollama"#name = "llama.cpp"#' -e 's#127.0.0.1:21434#127.0.0.1:20231#' \
    -e "s#^model = .*#model = \"$ALIAS\"\nmodel_reasoning_effort = \"medium\"#" \
    "$HOME_S/.codex/ollama-launch.config.toml" > "$HOME_S/.codex/llamacpp-gate.config.toml"
python3 - "$HOME_S/.codex/model.json" "$ALIAS" <<'PY'
import json, sys
path, alias = sys.argv[1], sys.argv[2]
data = json.load(open(path))
for model in data["models"]:
    print("launcher's description:", {k: model.get(k) for k in ("slug", "context_window", "default_reasoning_level")},
          "levels:", [level.get("effort") for level in model.get("supported_reasoning_levels", [])])
    model["slug"] = model["display_name"] = alias
    model["context_window"] = 64000
json.dump(data, open(path, "w"), indent=2)
print("model description now:", [(m["slug"], m["context_window"], m.get("default_reasoning_level")) for m in data["models"]])
PY
sed "s#$HOME#<HOME>#g" "$HOME_S/.codex/llamacpp-gate.config.toml"
set +e
env -i PATH="$S/bin:/usr/bin:/bin" HOME="$HOME_S" CODEX_HOME="$HOME_S/.codex" LANG=C.UTF-8 TZ=UTC \
  "$S/bin/codex" --profile llamacpp-gate mcp list > "$OUT/codex-mcp-list.txt" 2>&1 < /dev/null
echo "codex mcp list (llamacpp-gate) exit=$?"; grep -c 'time' "$OUT/codex-mcp-list.txt" | sed 's/^/lines naming the time server: /'
set -e
( cd "$S" && sha256sum gate/gate_env.sh gate/gate_run.sh gate/gate_score.py scratch-home/.codex/llamacpp-gate.config.toml \
    scratch-home/.codex/model.json scratch-home/.codex/config.toml > setup/hashes.txt ); cat "$OUT/hashes.txt" | cut -c1-110
echo "setup $ARM end $(date -u +%Y-%m-%dT%H:%M:%SZ)"
