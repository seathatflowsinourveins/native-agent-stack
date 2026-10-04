#!/bin/sh
# Receipt "use" dry-run for mirix at the pinned v0.1.6 release tag
# (commit 0f3fbdb5e085ccceb6254e2a4a128a8957dac55a), against this host's
# local llama.cpp OpenAI-compatible endpoint (qwen3.8-27b-local). Positive
# control: the same call sequence against the fixed main-branch pin
# (8cb06a62) in receipt_check_main_use.sh proves a clean add()+poll pass is
# possible with the same local model/config, so a stall here is not "the
# model is just slow" -- it isolates to the v0.1.6 pin.
set -e
W="<scratch>/trial-mirix"
"$W/venv/bin/python" - <<'PYEOF'
import time, json, sys
sys.path.insert(0, "<scratch>/trial-mirix/mirix-src")
import yaml
from mirix import MirixClient
c = MirixClient(api_key="<redacted>", base_url="http://127.0.0.1:18531")
config = yaml.safe_load(open("<scratch>/trial-mirix/config/mirix_local_bm25.yaml"))
c.initialize_meta_agent(config=config, update_agents=False)
r = c.add(user_id="receipt-check-user", messages=[
    {"role": "user", "content": [{"type": "text", "text": "The receipt check fact: the sky is teal today."}]},
])
print("ADD:", json.dumps(r))
deadline = time.time() + 280
counts = {}
while time.time() < deadline:
    m = c.retrieve_with_conversation(user_id="receipt-check-user", messages=[
        {"role": "user", "content": [{"type": "text", "text": "What is the receipt check fact?"}]},
    ], limit=5)
    counts = {k: v.get("total_count", 0) for k, v in m.get("memories", {}).items()}
    print("POLL:", json.dumps(counts))
    if sum(counts.values()) > 0:
        print("MEMORY_APPEARED")
        sys.exit(0)
    time.sleep(15)
print("MEMORY_NEVER_APPEARED after 280s:", json.dumps(counts))
sys.exit(1)
PYEOF
