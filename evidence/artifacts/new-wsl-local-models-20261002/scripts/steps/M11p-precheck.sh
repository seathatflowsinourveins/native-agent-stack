#!/usr/bin/env bash
# Measurement distribution only. Precondition of a load under condition N (deviation 1 of the preregistration): the
# measurement Ollama server holds no resident model and no llama-server process exists here. Unloads nothing by
# itself: a resident model is a failed precondition and the window does not start. Exit 0 only when both hold.
set -u
export PATH="/usr/lib/wsl/lib:$PATH"
resident=$(curl -fsS -m 10 http://127.0.0.1:21434/api/ps 2>/dev/null | python3 -c 'import json,sys; print(" ".join(m["name"] for m in json.load(sys.stdin).get("models", [])))' 2>/dev/null)
ollama_up=$(curl -fsS -m 5 -o /dev/null http://127.0.0.1:21434/api/version 2>/dev/null && echo yes || echo no)
servers=$(pgrep -f 'llama-server' | tr '\n' ' ')
echo "precheck $(date -u +%Y-%m-%dT%H:%M:%SZ): measurement Ollama up=$ollama_up resident=[${resident}] llama-server pids=[${servers}] GPU used $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
[ -z "$resident" ] && [ -z "$servers" ]
