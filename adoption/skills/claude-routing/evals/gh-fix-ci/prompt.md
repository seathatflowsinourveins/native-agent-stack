---
runs: 3
max_turns: 8
allowed_tools: [Skill]
append_system_prompt: |-
  This is a synthetic skill selection evaluation. Load the applicable workflow
  instructions, then stop with a routing summary. Do not execute the workflow,
  delegate, contact services or modify files.
---

Help fix the failing GitHub Actions check on my pull request. The test step reports ModuleNotFoundError for yaml and the workflow installs only requirements.txt. This is a synthetic PR example.

