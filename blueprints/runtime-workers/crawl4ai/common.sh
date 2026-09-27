#!/usr/bin/env bash
# This file sets task-specific variables; it never replaces HOME or CODEX_HOME.
set -euo pipefail
umask 077
export NAS_CRAWL4AI_PREFIX="$HOME/.local/share/codex-ecosystem/tools/crawl4ai-0.9.4"
export NAS_CRAWL4AI_STATE="$HOME/.local/state/native-agent-stack/runtime-workers/crawl4ai"
export NAS_CRAWL4AI_GRADER="$NAS_CRAWL4AI_PREFIX/grader/bin/promptfoo"
export PYTHONDONTWRITEBYTECODE=1
export XDG_CACHE_HOME="$NAS_CRAWL4AI_STATE/cache"
export CRAWL4_AI_BASE_DIRECTORY="$NAS_CRAWL4AI_STATE/crawl"
export PLAYWRIGHT_BROWSERS_PATH="$NAS_CRAWL4AI_PREFIX/venv/.cache/ms-playwright"
export NLTK_DATA="$NAS_CRAWL4AI_STATE/cache/nltk"
export HF_HOME="$NAS_CRAWL4AI_STATE/cache/huggingface"
export TIKTOKEN_CACHE_DIR="$NAS_CRAWL4AI_STATE/cache/tiktoken"
export LITELLM_LOCAL_MODEL_COST_MAP=true
export DO_NOT_TRACK=1
export UV_PYTHON_DOWNLOADS=never
