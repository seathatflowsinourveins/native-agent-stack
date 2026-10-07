# Integration observation of native client events, not an upstream test suite.
# promptfoo@0.123.1:src/commands/mcp/lib/utils.ts:11-38;
# src/commands/mcp/tools/runEvaluation.ts:103-115,433-478.
# openai/codex@rust-v0.159.3:codex-rs/exec/src/exec_events.rs:263-293.
# Claude Code's documented stream-json tool_use/tool_result envelope:
# https://code.claude.com/docs/en/headless
def decoded:
  if type == "string" then (fromjson? | decoded)
  elif type == "array" then .[] | decoded
  elif type == "object" then
    if .tool? == "run_evaluation" then .
    elif .type? == "text" then .text | decoded
    elif has("content") then .content | decoded
    else empty end
  else empty end;
def accepted:
  .tool == "run_evaluation" and .success == true and
  .data.eval.status == "completed" and
  .data.configuration.options.cache == false and
  .data.configuration.options.share == false and
  .data.results.totalEvals == 2 and
  .data.results.stats.successes == 2 and
  .data.results.stats.failures == 0 and .data.results.stats.errors == 0 and
  ([.data.results.results[].provider.id] | unique | length) == 2 and
  ([.data.results.results[].provider.id] | sort) == ($expected | sort) and
  all(.data.results.results[];
      .eval.success == true and (.provider.id | startswith("openai:chat:")));
if $client == "claude" then
  [.[] | select(.type == "assistant") | .message.content[]? |
    select(.type == "tool_use" and .name == "mcp__promptfoo__run_evaluation") | .id] as $calls |
  ([.[] | select(.type == "user") | .message.content[]? |
    select(.type == "tool_result" and .is_error != true) |
    select(.tool_use_id as $id | $calls | index($id)) |
    .content | decoded | select(accepted)] | length) > 0 and
  any(.[]; .type == "result" and .is_error == false)
elif $client == "codex" then
  any(.[]; .type == "turn.completed") and
  ([.[] | select(.type == "item.completed") | .item |
    select(.type == "mcp_tool_call" and .server == "promptfoo" and
           .tool == "run_evaluation" and .status == "completed" and .error == null) |
    .result.content | decoded | select(accepted)] | length) > 0
else false end
