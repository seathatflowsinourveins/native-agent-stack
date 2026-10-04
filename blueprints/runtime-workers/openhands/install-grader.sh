#!/usr/bin/env bash
# OpenHands/benchmarks@405bae7 Makefile:33-42 native uv sync; locked adaptation.
# This is a coordinator host recipe; never invoked by offline contract tests.
set -euo pipefail
umask 077
grader_dir="$1"
cache_dir="$2"
benchmark_pin=405bae7140d7e961a75f4910a0b2e7069731db96
sdk_pin=43376f1868ffd702746080714a59c16d3f69ec12
export PYTHONDONTWRITEBYTECODE=1
export UV_PYTHON_DOWNLOADS=never
export UV_NO_CONFIG=1
recipe_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
[[ "$(uv --version | cut -d' ' -f2)" == 0.12.17 ]]
export UV_CACHE_DIR="$cache_dir/grader-uv"
export PRE_COMMIT_HOME="$cache_dir/grader-pre-commit"
export XDG_CACHE_HOME="$cache_dir/grader"
if [[ ! -d "$grader_dir" ]]; then
  git clone --no-checkout https://github.com/OpenHands/benchmarks.git "$grader_dir"
  git -C "$grader_dir" checkout --detach "$benchmark_pin"
fi
[[ "$(git -C "$grader_dir" rev-parse HEAD)" == "$benchmark_pin" ]]
[[ -z "$(git -C "$grader_dir" status --porcelain --untracked-files=no)" ]]
git -C "$grader_dir" submodule update --init --recursive
[[ "$(git -C "$grader_dir/vendor/software-agent-sdk" rev-parse HEAD)" == "$sdk_pin" ]]
# Hash of the unchanged upstream lock, read via GitHub contents at this commit.
printf '%s  %s\n' 287a42d2157d044ca0f5e723fe3a05c1e4bdf6413049370360226374db6d7e8c "$grader_dir/uv.lock" | sha256sum -c -
if [[ ! -x "$grader_dir/.venv/bin/python" ]]; then
  uv venv --python python3.13 "$grader_dir/.venv"
fi
# All four SDK workspace build systems at 43376f1 require setuptools>=61 + wheel.
# Hash-pinned build tools, no isolated downloads; --inexact retains those tools.
uv pip install --python "$grader_dir/.venv/bin/python" --require-hashes --no-deps \
  --only-binary :all: -r "$recipe_dir/build-requirements.lock"
# Override upstream .python-version:1 (3.12) with the hash-seeded environment;
# installed uv 0.12.17 sync --help documents --python for this selection.
uv sync --project "$grader_dir" --python "$grader_dir/.venv/bin/python" --locked --dev --no-build-isolation --inexact
git -C "$grader_dir" diff --exit-code -- uv.lock pyproject.toml
[[ "$(git -C "$grader_dir/vendor/software-agent-sdk" rev-parse HEAD)" == "$sdk_pin" ]]
"$grader_dir/.venv/bin/python" -c 'from importlib.metadata import version; assert version("swebench") == "4.1.0"; print("swebench==4.1.0 installed; grader not executed")'
