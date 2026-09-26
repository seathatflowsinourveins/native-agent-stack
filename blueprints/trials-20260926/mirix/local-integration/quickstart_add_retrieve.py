#!/usr/bin/env python3
"""Thin glue: runs upstream MIRIX's own documented quickstart code path
(README.md "Option B: Local (backend + dashboard, no Docker)") against a
locally-started server, with only the model_endpoint / embedding_endpoint
values substituted for this host's local OpenAI-compatible servers.

Every call below (MirixClient(...), initialize_meta_agent, add,
retrieve_with_conversation) is upstream's unmodified mirix.client.remote_client
code, invoked exactly as mirix-src/README.md's own quickstart shows. No memory
scoring/evaluation logic is implemented here.
"""
import json
import os
import sys
import yaml

from mirix import MirixClient

CONFIG_PATH = sys.argv[1] if len(sys.argv) > 1 else "config/mirix_local.yaml"
API_KEY = os.environ["MIRIX_API_KEY"]
BASE_URL = os.environ.get("MIRIX_API_URL", "http://127.0.0.1:18531")

client = MirixClient(api_key=API_KEY, base_url=BASE_URL)

config = yaml.safe_load(open(CONFIG_PATH))

init_result = client.initialize_meta_agent(config=config, update_agents=True)
print("INIT_RESULT:", json.dumps(init_result, default=str)[:2000])

add_result = client.add(
    user_id="demo-user",
    messages=[
        {"role": "user", "content": [{"type": "text", "text": "The moon now has a president."}]},
        {"role": "assistant", "content": [{"type": "text", "text": "Noted."}]},
    ],
)
print("ADD_RESULT:", json.dumps(add_result, default=str)[:2000])

memories = client.retrieve_with_conversation(
    user_id="demo-user",
    messages=[
        {"role": "user", "content": [{"type": "text", "text": "What did we discuss about the moon?"}]},
    ],
    limit=5,
)
print("RETRIEVE_RESULT:", json.dumps(memories, default=str)[:4000])
