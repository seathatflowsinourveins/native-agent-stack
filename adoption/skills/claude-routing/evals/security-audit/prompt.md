---
runs: 3
max_turns: 8
allowed_tools: [Skill]
append_system_prompt: |-
  This is a synthetic skill selection evaluation. Load the applicable workflow
  instructions, then stop with a routing summary. Do not execute the workflow,
  delegate, contact services or modify files.
---

Audit this API for security vulnerabilities. Its download handler passes a filename from the request body directly to a system shell command. Identify exploitable paths and evidence needed to confirm them.

