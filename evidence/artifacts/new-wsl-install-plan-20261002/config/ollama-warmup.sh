#!/usr/bin/env bash
# Preload both measured models after the server starts (ruling change 5): KEEP_ALIVE=-1 keeps loaded models resident
# but does not preload them (docs/faq.mdx). Logs /api/ps; a failure is recorded, never fatal (ExecStartPost=-).
set -u
H=http://127.0.0.1:21434
for i in $(seq 1 60); do curl -fsS -m 2 -o /dev/null "$H/api/version" && break; sleep 1; done
curl -fsS -m 300 "$H/api/generate" -d '{"model":"swift-iq3s-s2o-64k","keep_alive":-1}' > /dev/null && echo "warm-up generate model loaded"
curl -fsS -m 120 "$H/api/embed" -d '{"model":"qwen3-embedding-8k","input":"warm","keep_alive":-1}' > /dev/null && echo "warm-up embed model loaded"
curl -fsS -m 5 "$H/api/ps" | python3 -c 'import json,sys; [print("resident", m["name"], m.get("size"), m.get("size_vram"), m.get("context_length")) for m in json.load(sys.stdin).get("models", [])]'
