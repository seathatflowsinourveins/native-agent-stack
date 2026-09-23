You are resuming a task another worker started and could not finish. Use only these MCP tools:
ai-memory handoff tools (always pass workspace="g2amw" and project="g9-composed") and
socraticode codebase_search (always pass projectPath=PROJECT_PATH and limit=10). If a tool is
deferred, you may load it with the tool-discovery tool. Do not run shell commands.

First call memory_handoff_list, then memory_handoff_accept for the open handoff, and read what was
done and what remains. Do not redo completed steps; reuse the recorded step-1 result. Complete the
remaining step with SocratiCode. Final answer: ONLY a JSON object
{"sha256_files": [...], "subprocess_files": [...], "recovered_from_handoff": ["..."], "redone_steps": [...]}.
