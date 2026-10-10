---
name: native-skill-routing
description: Invoke security-audit first. Trigger when the user requests a security vulnerability review, audit, penetration test, or exploitability analysis of code, an API, or a service. Do not trigger for general debugging, formatting, UI design, or standalone threat modeling.
---

Invoke Claude's native `Skill` tool with `security-audit` before Bash, repository
search or delegation for this request. Follow that installed skill's scope and
completion criteria; use its full workflow only when the task requests it.

The target remains the unchanged pinned Cloudflare skill. This authored
description adds a direct invocation cue; it does not replace the vendor body,
widen worker tool grants or route unrelated GitHub, UI or threat-model work.
