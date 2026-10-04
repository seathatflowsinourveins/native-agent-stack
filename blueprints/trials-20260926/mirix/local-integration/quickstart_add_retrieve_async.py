#!/usr/bin/env python3
"""Same upstream MIRIX quickstart calls as quickstart_add_retrieve.py, awaited.

On the main-branch pin (8cb06a62) MirixClient.initialize_meta_agent/add/
retrieve_with_conversation are `async def` (unlike the synchronous v0.1.6
release tag). Upstream's own README.md quickstart code block and
samples/run_client.py still show these as plain synchronous calls with no
await/asyncio -- copy-pasting either as documented only produces
"coroutine ... was never awaited" RuntimeWarnings and does no actual work
(reproduced in quickstart_main_run1.log). This wrapper calls the exact same
unmodified MirixClient methods, just awaited, so the underlying upstream
add/retrieve behaviour can actually be observed on this pin.
"""
import json
import os
import sys
import asyncio
import yaml

from mirix import MirixClient

CONFIG_PATH = sys.argv[1] if len(sys.argv) > 1 else "config/mirix_main_local_bm25.yaml"
API_KEY = os.environ["MIRIX_API_KEY"]
BASE_URL = os.environ.get("MIRIX_API_URL", "http://127.0.0.1:18533")


async def main():
    client = MirixClient(api_key=API_KEY, base_url=BASE_URL)
    config = yaml.safe_load(open(CONFIG_PATH))

    init_result = await client.initialize_meta_agent(config=config, update_agents=True)
    print("INIT_RESULT:", json.dumps(init_result, default=str)[:2000])

    # NOTE: upstream's own README.md quickstart shows content as a list of
    # {"type": "text", "text": ...} parts; mirix/server/rest_api.py add_memory
    # (line ~2413) crashes on that exact shape with
    # "TypeError: can only concatenate str (not 'dict') to str" (confirmed,
    # see quickstart_main_run2.log + server-main.log). Using the same
    # endpoint's other documented shape -- content as a plain string, per its
    # own comment "OR the simpler format: [{'role': 'user', 'content': 'Hello
    # world'}]" -- to observe the rest of the add/retrieve pipeline.
    add_result = await client.add(
        user_id="demo-user",
        messages=[
            {"role": "user", "content": "The moon now has a president."},
            {"role": "assistant", "content": "Noted."},
        ],
    )
    print("ADD_RESULT:", json.dumps(add_result, default=str)[:2000])

    memories = await client.retrieve_with_conversation(
        user_id="demo-user",
        messages=[
            {"role": "user", "content": "What did we discuss about the moon?"},
        ],
        limit=5,
    )
    print("RETRIEVE_RESULT:", json.dumps(memories, default=str)[:4000])


if __name__ == "__main__":
    asyncio.run(main())
