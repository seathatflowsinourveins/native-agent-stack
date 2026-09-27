#!/usr/bin/env bash
# Sources: v0.9.4 release pip path; uv 0.12.17 pip sync hash checking;
# Docker's digest pull; Playwright 1.63.0 install --only-shell + download mirror.
set -euo pipefail
NAS_CRAWL4AI_RECIPE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$NAS_CRAWL4AI_RECIPE/common.sh"
[[ "$(uname -m)" == x86_64 && "$(uname -s)" == Linux ]] || { echo 'Linux x86_64 required' >&2; exit 1; }
[[ "$(uv --version)" == 'uv 0.12.17'* ]] || { echo 'uv 0.12.17 required' >&2; exit 1; }
# Promptfoo 0.123.1 site/docs/installation.md; no global/default npm prefix.
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 22)) process.exit(1)'
command -v npm >/dev/null
python3 - "$NAS_CRAWL4AI_RECIPE" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
pins = json.loads((root / 'pins.json').read_text())
assert hashlib.sha256((root / 'requirements.lock').read_bytes()).hexdigest() == pins['requirements_lock_sha256'], 'reviewed lock hash mismatch'
PY
python3 "$NAS_CRAWL4AI_RECIPE/host.py" init
NAS_CRAWL4AI_PYTHON="$(python3 "$NAS_CRAWL4AI_RECIPE/host.py" get python)"
NAS_CRAWL4AI_DOCKER="$(python3 "$NAS_CRAWL4AI_RECIPE/host.py" get docker)"
NAS_CRAWL4AI_DOCKER_CONTEXT="$(python3 "$NAS_CRAWL4AI_RECIPE/host.py" get docker_context)"
"$NAS_CRAWL4AI_PYTHON" -c 'import sys; assert sys.version_info[:2] == (3, 12)'
"$NAS_CRAWL4AI_DOCKER" --context "$NAS_CRAWL4AI_DOCKER_CONTEXT" info --format '{{json .SecurityOptions}}' |
  python3 -c 'import json,sys; assert any("rootless" in x for x in json.load(sys.stdin)), "rootless Docker required"'
uv venv --python "$NAS_CRAWL4AI_PYTHON" --allow-existing "$NAS_CRAWL4AI_PREFIX/venv"
# The release's upstream lock is stale; requirements.lock is a derived, hash-pinned wheel closure.
uv pip sync --python "$NAS_CRAWL4AI_PREFIX/venv/bin/python" --require-hashes --only-binary :all: \
  --cache-dir "$NAS_CRAWL4AI_STATE/cache/uv" "$NAS_CRAWL4AI_RECIPE/requirements.lock"
mkdir -p "$NAS_CRAWL4AI_PREFIX/venv/.cache" "$NAS_CRAWL4AI_PREFIX/recipe"
if [[ ! -e "$PLAYWRIGHT_BROWSERS_PATH" && ! -L "$PLAYWRIGHT_BROWSERS_PATH" ]]; then
  ln -s "$NAS_CRAWL4AI_STATE/browser-cache" "$PLAYWRIGHT_BROWSERS_PATH"
fi
[[ "$(readlink -- "$PLAYWRIGHT_BROWSERS_PATH")" == "$NAS_CRAWL4AI_STATE/browser-cache" ]] || {
  echo 'Browser cache belongs to another installation; refusing replacement' >&2; exit 1;
}
# Retain a standalone reviewed recipe. Never copy research scratch space or a credential.
python3 - "$NAS_CRAWL4AI_RECIPE" "$NAS_CRAWL4AI_PREFIX/recipe" <<'PY'
import pathlib, shutil, sys
source, destination = map(pathlib.Path, sys.argv[1:])
if source.resolve() != destination.resolve():
    shutil.copytree(source, destination, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('.research', '__pycache__', '.gitignore'))
PY
export TMPDIR="$NAS_CRAWL4AI_STATE/tmp"
npm install --global --prefix "$NAS_CRAWL4AI_PREFIX/grader" --cache "$NAS_CRAWL4AI_STATE/cache/npm" \
  --no-audit --no-fund promptfoo@0.123.1
PROMPTFOO_CONFIG_DIR="$NAS_CRAWL4AI_STATE/grader" PROMPTFOO_DISABLE_TELEMETRY=1 \
  PROMPTFOO_DISABLE_UPDATE=1 "$NAS_CRAWL4AI_GRADER" --version
"$NAS_CRAWL4AI_PYTHON" "$NAS_CRAWL4AI_PREFIX/recipe/install-browser.py"
NAS_CRAWL4AI_IMAGE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image"])' "$NAS_CRAWL4AI_RECIPE/pins.json")"
"$NAS_CRAWL4AI_DOCKER" --context "$NAS_CRAWL4AI_DOCKER_CONTEXT" pull --platform linux/amd64 "$NAS_CRAWL4AI_IMAGE"
"$NAS_CRAWL4AI_PREFIX/venv/bin/python" -c 'import importlib.metadata as m; assert m.version("crawl4ai") == "0.9.4"; assert m.version("playwright") == "1.63.0"'
echo 'Pinned native environment and Docker image installed. Service and E2E have separate commands.'
