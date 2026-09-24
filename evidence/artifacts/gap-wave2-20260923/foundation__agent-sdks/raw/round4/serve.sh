#!/usr/bin/env bash
# Round 4 loopback provider: vLLM in its own network namespace; only 127.0.0.1:28431 is forwarded from the host.
exec pasta --config-net -t 127.0.0.1/28431 -u none -T none -U none --quiet -- \
  env -u HF_TOKEN HF_HOME=$HOME/.cache/gap-wave2-20260923/agent-sdks/hf HF_HUB_OFFLINE=1 VLLM_CACHE_ROOT=$HOME/.cache/gap-wave2-20260923/agent-sdks/round4/vllm-cache XDG_CACHE_HOME=$HOME/.cache/gap-wave2-20260923/agent-sdks/round4/xdg \
  VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1 VLLM_USE_V2_MODEL_RUNNER=0 VLLM_USE_FLASHINFER_SAMPLER=0 \
  $HOME/.local/share/codex-ecosystem/bin/vllm serve $HOME/.cache/gap-wave2-20260923/agent-sdks/hf/hub/models--Qwen--Qwen3-4B-Instruct-2507-FP8/snapshots/8591804019c8b22094c3b5b4454e0edc05dffc98 --host 0.0.0.0 --port 28431 \
  --served-model-name qwen3-4b local-sonnet local-haiku --gpu-memory-utilization 0.5 --max-model-len 32768 \
  --max-num-seqs 4 --enforce-eager --enable-auto-tool-choice --tool-call-parser hermes
