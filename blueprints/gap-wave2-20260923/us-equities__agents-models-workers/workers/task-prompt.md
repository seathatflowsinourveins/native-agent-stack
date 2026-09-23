Read-only fact extraction. Two JSON files are in the current working directory:
worker-receipt.json and acp-research-receipt.json.

Read them with exactly one shell command and no other file-reading method:

    head -c 24000 -- worker-receipt.json acp-research-receipt.json

Do not use any MCP tool, do not write files, do not use the network. Then reply
with ONLY one JSON object (no code fence, no prose) with these keys and values
taken from the files:

- "sdk_run_duration_ms": worker-receipt.json run.duration_ms (integer)
- "sdk_run_total_tokens": worker-receipt.json run.usage.total.totalTokens (integer)
- "sdk_blocked_file_extraction_tasks": worker-receipt.json all_three_native_turns.blocked_file_extraction_tasks (integer)
- "acp_native_turn_duration_ms": acp-research-receipt.json result.native_turn_duration_ms (integer)
- "acp_cumulative_total_tokens": acp-research-receipt.json result.usage_cumulative.totalTokens (integer)
- "acp_sandbox_policy_type": acp-research-receipt.json result.sandbox_policy.type (string)
