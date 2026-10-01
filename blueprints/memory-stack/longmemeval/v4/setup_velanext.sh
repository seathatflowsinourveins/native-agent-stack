#!/usr/bin/env bash
# Pinned, checksum-verified setup of the LongMemEval-S lane on VelaNext (WSL2 Ubuntu 24.04, RTX 4090).
#
# Everything installs under the lane's own prefix, $LME_BENCH_ROOT (default ~/.local/share/lme-bench), from
# official prebuilt releases, registries and lockfiles (pins.json). Nothing touches the workstation's production
# layout (~/.local/share/agent-ecosystem: its Ollama, models, links and tools; review pins P3, lane F8). The one
# self-build is ai-memory 19b6429: no official release, prerelease or image covers it (pins.json
# ai_memory.release_check). A16 adds MemPalace 3.10.0 and Hindsight 0.10.1 (hash-locked PyPI releases), chromadb's
# pinned MiniLM ONNX model, Hindsight's local models (revision-pinned) and Hindsight's agent-memory-benchmark at its
# own AMB_REF (uv.lock, on a pinned managed Python). Idempotent: every extracted tree carries a stamp with the archive
# digest or commit it came from, and a tree whose stamp differs from the pin is replaced (review pins P4). Never uses
# sudo; missing system packages are reported with the one command the user runs.
#
#   bash evals/longmemeval/setup_velanext.sh [--skip-models] [--only STEP]
#   STEPs: tools python venvs official data node agentmemory iii rust ai-memory ollama llama hf vendor a16
set -euo pipefail

LANE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LB="${LME_BENCH_ROOT:-$HOME/.local/share/lme-bench}"
LME_HOME="$LB/longmemeval"
TOOLS="$LB/tools"
SRC="$LB/src"
DL="$LB/downloads"
PINS="$LANE/pins.json"
ONLY=""
SKIP_MODELS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY="$2"; shift 2 ;;
    --skip-models) SKIP_MODELS=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

log() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { printf 'setup_velanext: %s\n' "$*" >&2; exit 1; }
want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }
pin() { python3 -c "import json,sys; v=json.load(open(sys.argv[1]))
for k in sys.argv[2].split('.'): v=v[int(k)] if k.isdigit() else v[k]
print(v)" "$PINS" "$1"; }

# fetch URL SHA256 DEST: download once, verify, keep. A file with the wrong checksum is replaced.
fetch() {
  local url="$1" sum="$2" dest="$3"
  mkdir -p "$(dirname "$dest")"
  if [ -f "$dest" ] && echo "$sum  $dest" | sha256sum -c --status; then return 0; fi
  log "download $(basename "$dest")"
  curl -fL --retry 3 --retry-delay 5 -o "$dest.part" "$url"
  echo "$sum  $dest.part" | sha256sum -c --status || { rm -f "$dest.part"; die "checksum mismatch for $url"; }
  mv "$dest.part" "$dest"
}
# stamped DIR VALUE: the tree at DIR was built from VALUE (an archive digest or a commit); a mismatch means rebuild.
stamped() { [ -f "$1/.archive-sha256" ] && [ "$(cat "$1/.archive-sha256")" = "$2" ]; }
stamp() { mkdir -p "$1"; printf '%s\n' "$2" > "$1/.archive-sha256"; }
fresh() { rm -rf "$1"; mkdir -p "$1"; }  # a tree whose stamp differs from the pin is replaced, never patched

# ---------------------------------------------------------------- preconditions
missing=()
for c in curl git tar zstd gcc make lsof pgrep ps sha256sum python3 nvidia-smi flock setsid; do
  command -v "$c" >/dev/null 2>&1 || missing+=("$c")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "missing commands: ${missing[*]}" >&2
  echo "ask the user to install the system packages once (the agent never runs sudo):" >&2
  echo "  sudo apt-get update && sudo apt-get install -y build-essential curl git zstd lsof procps util-linux" >&2
  echo "nvidia-smi comes from the Windows NVIDIA driver (/usr/lib/wsl/lib); see docs/qualification-cuda.md" >&2
  exit 1
fi
[ "$(uname -m)" = x86_64 ] || die "x86_64 only"
grep -q 'VERSION_ID="24.04"' /etc/os-release || log "warning: not Ubuntu 24.04; the lane was pinned for it"
mkdir -p "$LB" "$TOOLS" "$SRC" "$DL" "$LME_HOME"/{data,cache/proxy,logs,models}
free_gb=$(df -Pk "$LB" | awk 'NR==2 {print int($4 / 1048576)}')
[ "$free_gb" -ge 200 ] || log "warning: ${free_gb} GB free under $LB; the lane needs about 250 GB (models, caches, rows)"
mem_gb=$(awk '/MemTotal/ {print int($2 / 1048576)}' /proc/meminfo)
[ "$mem_gb" -ge 48 ] || log "warning: the WSL VM has ${mem_gb} GiB; H1, H2 and K1 keep MoE experts in host RAM (raise memory= in .wslconfig)"

# ---------------------------------------------------------------- uv and Python
UV_DIR="$TOOLS/uv-$(pin uv.version)"
if want tools && ! stamped "$UV_DIR" "$(pin uv.sha256)"; then
  fetch "$(pin uv.url)" "$(pin uv.sha256)" "$DL/uv-$(pin uv.version).tar.gz"
  fresh "$UV_DIR"
  tar -xzf "$DL/uv-$(pin uv.version).tar.gz" -C "$UV_DIR" --strip-components=1
  stamp "$UV_DIR" "$(pin uv.sha256)"
fi
UV="$UV_DIR/uv"
[ -x "$UV" ] || die "the pinned uv is missing (run without --only, or --only tools)"
export UV_PYTHON_INSTALL_DIR="$TOOLS/python" UV_PYTHON_PREFERENCE=only-managed UV_CACHE_DIR="$LB/uv-cache"
PY311="$(pin python.version)"
if want python; then
  "$UV" python install "$PY311" "$(pin python.amb_version)"
fi

# ---------------------------------------------------------------- venvs (hash-locked)
venv() {  # venv NAME LOCKFILE: the lock's hashes also cover the build dependencies of the one sdist-only package
  local dir="$LME_HOME/$1" lock="$LANE/requirements/$2" build="$LANE/requirements/build.lock.txt"
  local stamp_file="$dir/.lock-sha256" sum
  sum=$(cat "$lock" "$build" | sha256sum | cut -d' ' -f1)
  if [ -f "$stamp_file" ] && [ "$(cat "$stamp_file")" = "$sum" ]; then return 0; fi
  log "venv $1 from $2"
  [ -x "$dir/bin/python" ] || "$UV" venv --python "$PY311" "$dir"
  "$UV" pip sync --python "$dir/bin/python" --require-hashes --index-url https://pypi.org/simple \
    --build-constraints "$build" "$lock"
  echo "$sum" > "$stamp_file"
}
if want venvs; then
  venv .venv-official official.lock.txt
  venv .venv-embed embed.lock.txt
  venv .venv-mempalace mempalace.lock.txt   # A16 M2, M1
  venv .venv-hindsight hindsight.lock.txt   # A16 K1
fi

# ---------------------------------------------------------------- official LongMemEval checkout
clone_at() {  # clone_at URL DIR COMMIT
  local url="$1" dir="$2" commit="$3"
  [ -d "$dir/.git" ] || git clone --quiet "$url" "$dir"
  if [ "$(git -C "$dir" rev-parse HEAD)" != "$commit" ]; then
    git -C "$dir" fetch --quiet origin "$commit" 2>/dev/null || git -C "$dir" fetch --quiet origin
    git -C "$dir" -c advice.detachedHead=false checkout --quiet "$commit"
  fi
  [ "$(git -C "$dir" rev-parse HEAD)" = "$commit" ] || die "$dir is not at $commit"
  [ -z "$(git -C "$dir" status --porcelain --untracked-files=no)" ] || die "$dir has local changes"
}
if want official; then
  clone_at "$(pin official.repo)" "$SRC/LongMemEval" "$(pin official.commit)"
fi

# ---------------------------------------------------------------- dataset and manifest
if want data; then
  fetch "$(pin dataset.url)" "$(pin dataset.sha256)" "$LME_HOME/data/longmemeval_s_cleaned.json"
  echo "$(pin manifest.sha256)  $LANE/eligible-manifest.json" | sha256sum -c --status || die "eligible-manifest.json changed"
fi

# ---------------------------------------------------------------- node (for agentmemory)
NODE_DIR="$TOOLS/node-v$(pin node.version)"
if want node && ! stamped "$NODE_DIR" "$(pin node.sha256)"; then
  fetch "$(pin node.url)" "$(pin node.sha256)" "$DL/node-v$(pin node.version)-linux-x64.tar.gz"
  fresh "$NODE_DIR"
  tar -xzf "$DL/node-v$(pin node.version)-linux-x64.tar.gz" -C "$NODE_DIR" --strip-components=1
  stamp "$NODE_DIR" "$(pin node.sha256)"
fi
export PATH="$NODE_DIR/bin:$PATH"

# ---------------------------------------------------------------- agentmemory 0.9.29 (npm ci, lockfile) and iii 0.11.2
AM_ROOT="$LB/agentmemory"
npm_ci() {  # npm_ci DIR LOCKFILE: install exactly the lockfile; reinstall when the lockfile changes
  local dir="$1" lock="$2" sum
  sum=$(sha256sum "$lock" | cut -d' ' -f1)
  if [ -f "$dir/node_modules/.lock-sha256" ] && [ "$(cat "$dir/node_modules/.lock-sha256")" = "$sum" ]; then return 0; fi
  # --ignore-scripts: onnxruntime-node's postinstall would fetch CUDA provider binaries outside the lockfile;
  # the CPU provider ships in the package, which is what the Mac's D2 used.
  (cd "$dir" && npm ci --ignore-scripts --no-audit --no-fund)
  echo "$sum" > "$dir/node_modules/.lock-sha256"
}
if want agentmemory; then
  mkdir -p "$AM_ROOT/bin"
  cp "$LANE/agentmemory/package.json" "$LANE/agentmemory/package-lock.json" "$AM_ROOT/"
  npm_ci "$AM_ROOT" "$AM_ROOT/package-lock.json"
  lock_integrity=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['packages']['node_modules/@agentmemory/agentmemory']['integrity'])" \
    "$AM_ROOT/package-lock.json")
  [ "$lock_integrity" = "$(pin agentmemory.integrity)" ] || die "agentmemory lockfile integrity differs from pins.json"
fi
if want iii && ! stamped "$AM_ROOT/bin" "$(pin iii.sha256)"; then
  fetch "$(pin iii.url)" "$(pin iii.sha256)" "$DL/iii-$(pin iii.version)-x86_64-unknown-linux-gnu.tar.gz"
  mkdir -p "$AM_ROOT/bin"
  tar -xzf "$DL/iii-$(pin iii.version)-x86_64-unknown-linux-gnu.tar.gz" -C "$AM_ROOT/bin" iii
  chmod +x "$AM_ROOT/bin/iii"
  stamp "$AM_ROOT/bin" "$(pin iii.sha256)"
fi

# ---------------------------------------------------------------- Rust and ai-memory 19b6429 (built: no release covers it)
export RUSTUP_HOME="$TOOLS/rust/rustup" CARGO_HOME="$TOOLS/rust/cargo"
AIMEM_DIR="$TOOLS/ai-memory-$(pin ai_memory.workspace_version)+$(pin ai_memory.commit | cut -c1-7)"
if want rust; then
  if ! stamped "$TOOLS/rust" "$(pin rustup.sha256)"; then
    fetch "$(pin rustup.url)" "$(pin rustup.sha256)" "$DL/rustup-init-$(pin rustup.version)"
    chmod +x "$DL/rustup-init-$(pin rustup.version)"
    "$DL/rustup-init-$(pin rustup.version)" -y --no-modify-path --profile minimal --default-toolchain "$(pin ai_memory.rust_toolchain)"
    stamp "$TOOLS/rust" "$(pin rustup.sha256)"
  fi
  "$CARGO_HOME/bin/rustup" toolchain install "$(pin ai_memory.rust_toolchain)" --profile minimal
fi
aimem_current() {  # both binaries exist, SOURCE names the pinned commit, and its recorded sha256 matches the binary
  [ -x "$AIMEM_DIR/ai-memory" ] && [ -x "$SRC/ai-memory/target/release/ai-memory-eval" ] && [ -f "$AIMEM_DIR/SOURCE" ] \
    && head -1 "$AIMEM_DIR/SOURCE" | grep -q "^$(pin ai_memory.commit) " \
    && [ "$(sed -n 2p "$AIMEM_DIR/SOURCE" | cut -d' ' -f1)" = "$(sha256sum "$AIMEM_DIR/ai-memory" | cut -d' ' -f1)" ]
}
if want ai-memory; then
  clone_at "$(pin ai_memory.repo)" "$SRC/ai-memory" "$(pin ai_memory.commit)"
  if ! aimem_current; then
    log "cargo build ai-memory $(pin ai_memory.commit | cut -c1-7) (release, --locked)"
    (cd "$SRC/ai-memory" && RUSTUP_TOOLCHAIN="$(pin ai_memory.rust_toolchain)" "$CARGO_HOME/bin/cargo" build --locked --release \
      -p ai-memory-cli -p ai-memory-eval)
    fresh "$AIMEM_DIR"
    install -m 0755 "$SRC/ai-memory/target/release/ai-memory" "$AIMEM_DIR/ai-memory"
    printf '%s release/2.5, workspace version %s (built on VelaNext: cargo build --locked --release -p ai-memory-cli, rust %s)\n%s  ai-memory\n' \
      "$(pin ai_memory.commit)" "$(pin ai_memory.workspace_version)" "$(pin ai_memory.rust_toolchain)" \
      "$(sha256sum "$AIMEM_DIR/ai-memory" | cut -d' ' -f1)" > "$AIMEM_DIR/SOURCE"
  fi
fi

# ---------------------------------------------------------------- Ollama 0.34.4 and the GGUF models, lane-owned
# The lane's Ollama, its model store and its runtime home live under $LB/ollama; no shared `current` link is made
# and no production store is written (review pins P3, lane F8). The tag v0.34.4 was re-spun: pins.json records the
# re-uploaded asset's sha256 and the tag's commit.
OLL_DIR="$LB/ollama/v$(pin ollama.version)"
export OLLAMA_MODELS="$LB/ollama/models"
if want ollama; then
  if ! stamped "$OLL_DIR" "$(pin ollama.sha256)"; then
    fetch "$(pin ollama.url)" "$(pin ollama.sha256)" "$DL/ollama-$(pin ollama.version)-linux-amd64.tar.zst"
    fresh "$OLL_DIR"
    tar --zstd -xf "$DL/ollama-$(pin ollama.version)-linux-amd64.tar.zst" -C "$OLL_DIR"
    stamp "$OLL_DIR" "$(pin ollama.sha256)"
  fi
  if [ "$SKIP_MODELS" = 0 ]; then
    mkdir -p "$OLLAMA_MODELS" "$LB/ollama/runtime-home"
    env -i HOME="$LB/ollama/runtime-home" PATH=/usr/bin:/bin OLLAMA_HOST=127.0.0.1:11438 OLLAMA_MODELS="$OLLAMA_MODELS" \
      OLLAMA_NO_CLOUD=1 "$OLL_DIR/bin/ollama" serve > "$LME_HOME/logs/ollama-setup.log" 2>&1 &
    oll_pid=$!
    trap 'kill $oll_pid 2>/dev/null || true' EXIT
    for _ in $(seq 60); do curl -sf http://127.0.0.1:11438/api/version >/dev/null && break; sleep 1; done
    for m in $(python3 -c "import json,sys; print(' '.join(json.load(open(sys.argv[1]))['ollama_models']))" "$PINS"); do
      if ! python3 "$LANE/lane_tools.py" verify-ollama "$OLLAMA_MODELS" "$m" >/dev/null; then
        log "ollama pull $m"
        OLLAMA_HOST=127.0.0.1:11438 "$OLL_DIR/bin/ollama" pull "$m"
      fi
    done
    python3 "$LANE/lane_tools.py" verify-ollama "$OLLAMA_MODELS" || die "an Ollama model does not match its pinned digests"
    for f in "$LANE"/ollama/*.Modelfile; do
      OLLAMA_HOST=127.0.0.1:11438 "$OLL_DIR/bin/ollama" create "$(basename "$f" .Modelfile)" -f "$f"
    done
    kill "$oll_pid" 2>/dev/null || true
    trap - EXIT
  fi
fi

# ---------------------------------------------------------------- llama.cpp v0.5.0 (b11146) CUDA 12.8 build
LLAMA_DIR="$TOOLS/llama.cpp-$(pin llama_cpp.build)"
LLAMA_STAMP="$(pin llama_cpp.assets.0.sha256) $(pin llama_cpp.assets.1.sha256)"
if want llama; then
  if ! stamped "$LLAMA_DIR" "$LLAMA_STAMP"; then
    fresh "$LLAMA_DIR"
    mkdir -p "$LLAMA_DIR/dist"
    for i in 0 1; do
      name=$(pin "llama_cpp.assets.$i.name")
      fetch "$(pin "llama_cpp.assets.$i.url")" "$(pin "llama_cpp.assets.$i.sha256")" "$DL/$name"
      tar -xzf "$DL/$name" -C "$LLAMA_DIR/dist"
    done
    server=$(find "$LLAMA_DIR/dist" -type f -name llama-server | head -1)
    [ -n "$server" ] || die "llama-server not found in the llama.cpp release"
    ln -sfn "$server" "$LLAMA_DIR/llama-server"
    find "$LLAMA_DIR/dist" -name '*.so*' -printf '%h\n' | sort -u | paste -sd: > "$LLAMA_DIR/LD_LIBRARY_PATH"
    stamp "$LLAMA_DIR" "$LLAMA_STAMP"
  fi
  LD_LIBRARY_PATH="$(cat "$LLAMA_DIR/LD_LIBRARY_PATH")" "$LLAMA_DIR/llama-server" --version 2>&1 | head -3
fi

# ---------------------------------------------------------------- Hugging Face models and data (revision-pinned, hashed)
export HF_HOME="$LME_HOME/hf-home"
if want hf && [ "$SKIP_MODELS" = 0 ]; then
  "$LME_HOME/.venv-embed/bin/python" "$LANE/lane_tools.py" fetch-hf --select serve,mteb,rerank,minilm,data
  "$LME_HOME/.venv-embed/bin/python" "$LANE/lane_tools.py" install-minilm --lme-home "$LME_HOME" --node-modules "$AM_ROOT/node_modules"
  # mteb's task loads its dataset through `datasets`, which needs its own cache to work offline: load it once here,
  # online, right after the files were verified; the gates then load it offline (review pins P7).
  "$LME_HOME/.venv-embed/bin/python" "$LANE/mteb_lmeb.py" --dry-load > "$LME_HOME/logs/mteb-warm.json" \
    || die "mteb could not load its LongMemEval task (logs/mteb-warm.json)"
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "$LME_HOME/.venv-embed/bin/python" "$LANE/mteb_lmeb.py" \
    --dry-load > /dev/null || die "mteb's LongMemEval task does not load offline after warming"
fi

# ---------------------------------------------------------------- vendor harnesses (run unmodified)
AMREPO="$SRC/agentmemory-v$(pin agentmemory.version)"
if want vendor; then
  # The vendor bench writes into its tracked benchmark/data files; the run keeps lane copies and restores these, and an
  # interrupted run must not block setup (review pins P2).
  if [ -d "$AMREPO/.git" ]; then git -C "$AMREPO" checkout -- benchmark/data 2>/dev/null || true; fi
  clone_at "$(pin agentmemory.repo)" "$AMREPO" "$(pin agentmemory.commit)"
  # The repository ships no lockfile; the lane's (vendor/agentmemory-repo-package-lock.json) pins every package.
  cp "$LANE/vendor/agentmemory-repo-package-lock.json" "$AMREPO/package-lock.json"
  npm_ci "$AMREPO" "$AMREPO/package-lock.json"
  ln -sfn "$LME_HOME/data/longmemeval_s_cleaned.json" "$AMREPO/benchmark/data/longmemeval_s_cleaned.json"
  if [ "$SKIP_MODELS" = 0 ]; then
    "$LME_HOME/.venv-embed/bin/python" "$LANE/lane_tools.py" install-minilm --lme-home "$LME_HOME" --node-modules "$AMREPO/node_modules"
  fi
fi

# ---------------------------------------------------------------- A16: MemPalace, Hindsight and AMB
MP_ONNX="$LME_HOME/models/chroma-onnx/all-MiniLM-L6-v2"
if want a16; then
  for pkg in mempalace:.venv-mempalace:mempalace.version hindsight-api:.venv-hindsight:hindsight.version; do
    IFS=: read -r name dir key <<< "$pkg"
    have=$("$LME_HOME/$dir/bin/python" -c "import importlib.metadata as m; print(m.version('$name'))" 2>/dev/null || true)
    [ "$have" = "$(pin "$key")" ] || die "$name $have in $dir is not $(pin "$key") (run --only venvs)"
  done
  # chromadb's own MiniLM ONNX archive (MemPalace's default embedder), checked against chromadb 1.5.9's sha256; each
  # MemPalace store links it into its HOME's ~/.cache/chroma, so chromadb never downloads at run time.
  if ! stamped "$MP_ONNX" "$(pin mempalace.embedding.sha256)"; then
    fetch "$(pin mempalace.embedding.url)" "$(pin mempalace.embedding.sha256)" "$DL/chroma-all-MiniLM-L6-v2-onnx.tar.gz"
    fresh "$MP_ONNX"
    cp "$DL/chroma-all-MiniLM-L6-v2-onnx.tar.gz" "$MP_ONNX/onnx.tar.gz"
    tar -xzf "$MP_ONNX/onnx.tar.gz" -C "$MP_ONNX"
    [ -f "$MP_ONNX/onnx/model.onnx" ] || die "the ONNX archive did not contain onnx/model.onnx"
    stamp "$MP_ONNX" "$(pin mempalace.embedding.sha256)"
  fi
  # M1 runs MemPalace's own benchmarks/longmemeval_bench.py from the release tag, unmodified.
  clone_at "$(pin mempalace.repo)" "$SRC/mempalace-v$(pin mempalace.version)" "$(pin mempalace.commit)"
  # Hindsight's agent-memory-benchmark at the commit Hindsight 0.10.1 names (hindsight-system-evals/AMB_REF), on the
  # pinned managed Python 3.12, with its locked dependencies only; the project itself runs from its source tree
  # (no hatchling build). Its one sdist-only dependency, langdetect 1.0.9 (hash-locked in AMB's uv.lock), is built
  # without isolation against AMB's own hash-locked setuptools, installed first, so no build backend comes from
  # outside the lock (review pins P6).
  clone_at "$(pin hindsight.amb.repo)" "$SRC/agent-memory-benchmark" "$(pin hindsight.amb.commit)"
  (cd "$SRC/agent-memory-benchmark" \
    && "$UV" sync --frozen --no-install-project --no-install-package langdetect --python "$(pin python.amb_version)" \
    && "$UV" sync --frozen --no-install-project --no-build-isolation-package langdetect --python "$(pin python.amb_version)")
  "$SRC/agent-memory-benchmark/.venv/bin/python" -c "import importlib.metadata as m, sys
v = {p: m.version(p) for p in ('langdetect', 'setuptools')}
sys.exit(0 if v == {'langdetect': '$(pin hindsight.amb.langdetect.version)', 'setuptools': '$(pin hindsight.amb.langdetect.built_with_setuptools)'} else f'AMB build tools: {v}')"
  if [ "$SKIP_MODELS" = 0 ]; then
    # Hindsight loads its embedder and reranker by name: its own HF home, refs/main pinned to the verified revision.
    HF_HOME="$LME_HOME/hf-home-hindsight" "$LME_HOME/.venv-embed/bin/python" "$LANE/lane_tools.py" fetch-hf \
      --select hindsight --pin-main
  fi
  python3 "$LANE/lane_tools.py" k1-subset --data "$LME_HOME/data/longmemeval_s_cleaned.json" --check "$LANE/k1-subset.json" \
    || die "k1-subset.json does not reproduce from the pinned dataset"
fi

log "setup complete under $LB; next: bash evals/longmemeval/run_velanext.sh gates"
