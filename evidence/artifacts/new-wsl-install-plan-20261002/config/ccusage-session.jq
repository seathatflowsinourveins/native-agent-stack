# Integration observation of native shell execution, not model prose.
# ccusage@v20.0.26:apps/ccusage/README.md:65-67 and docs/guide/installation.md:133-148.
# openai/codex@rust-v0.159.3:codex-rs/exec/src/exec_events.rs:148-165.
# https://code.claude.com/docs/en/headless documents the Claude stream envelope.
if $client == "claude" then
  [.[] | select(.type == "assistant") | .message.content[]? |
    select(.type == "tool_use" and .name == "Bash" and
           (.input.command | contains($meter) and contains("claude daily"))) | .id] as $calls |
  ([.[] | select(.type == "user") | .message.content[]? |
    select(.type == "tool_result" and .is_error != true) |
    select(.tool_use_id as $id | $calls | index($id))] | length) > 0 and
  any(.[]; .type == "result" and .is_error == false)
elif $client == "codex" then
  any(.[]; .type == "turn.completed") and
  any(.[]; .type == "item.completed" and
      .item.type == "command_execution" and .item.status == "completed" and
      .item.exit_code == 0 and
      (.item.command | contains($meter) and contains("codex daily")))
else false end
