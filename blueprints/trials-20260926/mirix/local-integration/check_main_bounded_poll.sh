#!/bin/sh
# Positive control for receipt_check_v016_use.sh: the same add()+poll
# sequence, same local llama.cpp endpoint, against the main-branch pin
# (commit 8cb06a62, where the audio_tokens schema bug is fixed) -- shows a
# clean pass is achievable with this host's local model, so a stall on the
# v0.1.6 pin is not merely "the model is slow".
set -e
W="<scratch>/trial-mirix"
"$W/venv-main/bin/python" - <<'PYEOF'
import time, json, sys, asyncio
sys.path.insert(0, "<scratch>/trial-mirix/mirix-main-src")
from mirix import MirixClient

async def main():
    c = MirixClient(api_key="<redacted>", base_url="http://127.0.0.1:18533")
    r = await c.add(user_id="receipt-check-user", messages=[
        {"role": "user", "content": "The receipt check fact: the sky is teal today."},
    ])
    print("ADD:", json.dumps(r))
    deadline = time.time() + 280
    counts = {}
    while time.time() < deadline:
        m = await c.retrieve_with_conversation(user_id="receipt-check-user", messages=[
            {"role": "user", "content": "What is the receipt check fact?"},
        ], limit=5)
        counts = {k: v.get("total_count", 0) for k, v in m.get("memories", {}).items()}
        print("POLL:", json.dumps(counts))
        if sum(counts.values()) > 0:
            print("MEMORY_APPEARED")
            return 0
        await asyncio.sleep(15)
    print("MEMORY_NEVER_APPEARED after 280s:", json.dumps(counts))
    return 1

sys.exit(asyncio.run(main()))
PYEOF
