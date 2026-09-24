Bounded two-step code-retrieval task over the project at PROJECT_PATH (already indexed).
Use only these MCP tools: socraticode codebase_search (always pass projectPath=PROJECT_PATH
and limit=10) and ai-memory handoff tools (always pass workspace="g2amw" and project="g9-composed").
If a tool is deferred, you may load it with the tool-discovery tool. Do not run shell commands.

Step 1: find which files compute a SHA-256 digest (hashlib.sha256). List the file paths.
Immediately after step 1, call ai-memory memory_handoff_begin recording: the step-1 file list,
"step 1 done", and "remaining: step 2 = find which files launch subprocesses (subprocess.run /
check_output / Popen) and return final JSON".
Step 2: find which files launch subprocesses.
Final answer: ONLY a JSON object {"sha256_files": [...], "subprocess_files": [...]}.
