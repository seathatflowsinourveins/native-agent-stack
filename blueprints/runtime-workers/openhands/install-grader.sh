#!/usr/bin/env bash
# OpenHands/benchmarks 405bae7 README + Makefile: supported make build path.
# This is a coordinator host recipe; never invoked by offline contract tests.
set -euo pipefail
umask 077
grader_dir="$1"
cache_dir="$2"
benchmark_pin=405bae7140d7e961a75f4910a0b2e7069731db96
sdk_pin=43376f1868ffd702746080714a59c16d3f69ec12
export PYTHONDONTWRITEBYTECODE=1
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
# Makefile runs uv sync --dev against its workspace/submodule and installs its
# own development hooks in this isolated checkout, never in native-agent-stack.
make -C "$grader_dir" build
git -C "$grader_dir" diff --exit-code -- uv.lock pyproject.toml
[[ "$(git -C "$grader_dir/vendor/software-agent-sdk" rev-parse HEAD)" == "$sdk_pin" ]]
"$grader_dir/.venv/bin/python" -c 'from importlib.metadata import version; assert version("swebench") == "4.1.0"; print("swebench==4.1.0 installed; grader not executed")'
