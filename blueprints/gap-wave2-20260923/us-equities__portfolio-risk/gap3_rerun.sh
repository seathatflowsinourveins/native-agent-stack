#!/usr/bin/env bash
# Regenerate the research-evaluation private artifacts in a fresh WAVE_DIR (run from the repository root).
set -u
WAVE_DIR=${1:?fresh wave dir}
SDK_PYTHON=$HOME/.local/share/codex-ecosystem/python/cpython-3.13.15-linux-x86_64-gnu/bin/python3.13
LEAN_SOURCE=$HOME/.local/share/codex-ecosystem/tools/lean-985ef30
[ -e "$WAVE_DIR" ] && { echo "wave dir exists" >&2; exit 2; }
mkdir -p "$WAVE_DIR/setup"
R=blueprints/us-equities/research-evaluation
run() { local id=$1; shift; "$@" > "$WAVE_DIR/setup/$id.stdout.txt" 2> "$WAVE_DIR/setup/$id.stderr.txt"; echo "$id exit=$?"; }
# Initial compile guess: the receipt says it also included unused DuckDB 1.5.5 (exact input unknown).
printf 'skfolio==1.2.9\npandas==3.0.6\nduckdb==1.5.5\n' > "$WAVE_DIR/requirements.initial-guess.in"
run compile uv pip compile "$WAVE_DIR/requirements.initial-guess.in" --python "$SDK_PYTHON" --generate-hashes --no-header --output-file "$WAVE_DIR/requirements.initial-guess.lock"
run compile-final uv pip compile $R/requirements.in --python "$SDK_PYTHON" --generate-hashes --no-header --output-file "$WAVE_DIR/requirements.lock.regenerated"
run venv uv venv --python "$SDK_PYTHON" "$WAVE_DIR/venv"
run sync-final uv pip sync --python "$WAVE_DIR/venv/bin/python" --require-hashes $R/requirements.lock
run check uv pip check --python "$WAVE_DIR/venv/bin/python"
run freeze uv pip freeze --python "$WAVE_DIR/venv/bin/python"
"$WAVE_DIR/venv/bin/python" $R/evaluate.py --lean-source "$LEAN_SOURCE" --out "$WAVE_DIR/run-1" > "$WAVE_DIR/run-1.stdout.txt" 2> "$WAVE_DIR/run-1.stderr.txt"
echo "run-1 exit=$?"
