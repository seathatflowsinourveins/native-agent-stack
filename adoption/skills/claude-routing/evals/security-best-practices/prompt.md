---
runs: 3
max_turns: 8
allowed_tools: [Skill]
append_system_prompt: |-
  This is a synthetic skill selection evaluation. Load the applicable workflow
  instructions, then stop with a routing summary. Do not execute the workflow,
  delegate, contact services or modify files.
---

Review this Python FastAPI design for security best practices and secure defaults. It allows credentialed CORS from every origin and returns full exception text.

