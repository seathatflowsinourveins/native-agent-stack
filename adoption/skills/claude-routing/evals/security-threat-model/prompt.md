---
runs: 3
max_turns: 8
allowed_tools: [Skill]
append_system_prompt: |-
  This is a synthetic skill selection evaluation. Load the applicable workflow
  instructions, then stop with a routing summary. Do not execute the workflow,
  delegate, contact services or modify files.
---

Create a threat model for a service accepting document uploads, queuing parsing and exposing stored results to authenticated customers. Identify assets, trust boundaries, attacker capabilities and abuse paths.

