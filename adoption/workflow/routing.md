# Native workflow routing

Generated from manifest.json; pins remain in the referenced stores.
Hook channels stay held until the upstream A/B and the command-center ACK.

| Task | Status | References | Native lanes |
| --- | --- | --- | --- |
| skills-research | kept | skills:search-first, skills:iterative-retrieval, agents:stack-researcher | cc: description; coop: description; codex_lane: description; agent_team: description; scheduled_headless: description; ultracode_stage: stack-researcher |
| skills-skill-lifecycle | kept | skills:find-skills, skills:skill-creator, agents:stack-verifier, stack:promptfoo | cc: description; coop: description; agent_team: description; scheduled_headless: description; ultracode_stage: stack-verifier |
| skills-design-intake | kept | agents:evidence-reviewer | cc: description; coop: description; codex_lane: description; agent_team: description; scheduled_headless: description; ultracode_stage: inert |
| skills-architecture | kept | skills:codebase-design, agents:isolated-builder | cc: description; coop: description; codex_lane: description; agent_team: description; scheduled_headless: description; ultracode_stage: inert |
| skills-implement | kept | skills:modern-python, skills:frontend-design, agents:isolated-builder | cc: description; coop: description; codex_lane: description; agent_team: description; scheduled_headless: description; ultracode_stage: inert |
| skills-test | kept | skills:tdd, skills:property-based-testing, agents:isolated-builder | cc: description; coop: description; codex_lane: description; agent_team: description; scheduled_headless: description; ultracode_stage: inert |
| skills-debug | kept | skills:diagnosing-bugs, agents:isolated-builder | cc: description; coop: description; codex_lane: description; agent_team: description; scheduled_headless: description; ultracode_stage: inert |
| skills-review | kept | skills:typesafe-ai, skills:variant-analysis, agents:evidence-reviewer | cc: description; coop: description; codex_lane: description; agent_team: description; scheduled_headless: description; ultracode_stage: evidence-reviewer |
| skills-security | kept | skills:security-best-practices, skills:security-threat-model, skills:codeql, skills:supply-chain-risk-auditor, skills:agentic-actions-auditor, skills:sarif-parsing, skills:fp-check, skills:security-audit, agents:security-reviewer-skills, skills:variant-analysis | cc: description; coop: description; codex_lane: description; agent_team: description; scheduled_headless: description; ultracode_stage: security-reviewer-skills |
| skills-ci-pr | kept | skills:gh-fix-ci, skills:gh-address-comments, agents:isolated-builder-ci-pr | cc: description; coop: description; codex_lane: description; agent_team: description; scheduled_headless: description; ultracode_stage: isolated-builder-ci-pr |
| skills-agent-docs | kept | skills:writing-for-agents, agents:isolated-builder-agent-docs | cc: description, path_rule; coop: description, path_rule; codex_lane: description; agent_team: description; scheduled_headless: description; ultracode_stage: isolated-builder-agent-docs |
| skills-browser | held | skills:agent-browser | ultracode_stage: inert |
| skills-mcp-build | kept | skills:mcp-builder, agents:isolated-builder | cc: description; coop: description; codex_lane: description; agent_team: description; scheduled_headless: description; ultracode_stage: inert |
| skills-data-quant | held | stack:edgartools, agents:stack-researcher | ultracode_stage: inert |
| skills-broker-adapter | held | stack:alpaca-py, agents:isolated-builder | ultracode_stage: inert |
| skills-hosting | held | stack:dagu, agents:isolated-builder | ultracode_stage: inert |
| skills-model-hub | held | stack:huggingface-hub-native | ultracode_stage: inert |
