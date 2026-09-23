import os
import anyio
from claude_agent_sdk import query, ClaudeAgentOptions

# cwd is the worktree this check ran in; pass it via CTX_SDK_CWD or default to
# the current working directory so no host-specific path is hardcoded here.
async def main():
    options = ClaudeAgentOptions(
        cwd=os.environ.get("CTX_SDK_CWD", os.getcwd()),
        allowed_tools=["Bash"],
        max_turns=2,
    )
    result_text = []
    async for message in query(
        prompt="Use the Bash tool to run `echo sdk-tool-ok` and then reply with just the word DONE.",
        options=options,
    ):
        result_text.append(repr(message))
    for line in result_text:
        print(line)

anyio.run(main)
