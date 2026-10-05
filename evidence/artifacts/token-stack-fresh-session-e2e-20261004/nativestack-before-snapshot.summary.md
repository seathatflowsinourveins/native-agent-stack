# Fresh-session E2E: nativestack, 20261004T214402Z (upstream commands only; local monitoring, not an A/B)

## Versions
- rtk 0.51.0; claude 2.1.289 (Claude Code); codex-cli 0.159.3
## rtk init --show
    rtk Configuration:
    
    [ok] Hook: rtk hook claude (native binary command)
    [ok] RTK.md: <home>/.claude/RTK.md (slim mode)
    [ok] Global (~/.claude/CLAUDE.md): @RTK.md reference
    [--] Local (./CLAUDE.md): not found
    [ok] settings.json: RTK hook configured
    [--] OpenCode: plugin not found
    [--] Cursor hook: not found
    
    Usage:
      rtk init              # Full injection into local CLAUDE.md
## MCP servers a fresh directory sees (claude mcp list / codex mcp list)
- claude, names: ai-memory codebase-memory headroom hindsight jcodemunch plugin:context-mode:context-mode qmd serena 
- claude, connected: 8 of 8
- claude, only in <home>/code/native-agent-stack (local or project scope, so a new project lacks it): socraticode 
- codex, names: ai-memory codebase-memory context-mode headroom hindsight qmd serena socraticode 
## Claude fresh session: claude-git
- init: claude_code_version 2.1.289, model claude-haiku-4-5-20251001, permissionMode bypassPermissions, tools 117, plugins 7
- MCP servers in the init event: plugin:context-mode:context-mode=connected, ai-memory=connected, serena=connected, jcodemunch=connected, codebase-memory=connected, qmd=connected, headroom=connected, hindsight=connected
- hook events (event, name, outcome, count):
    2 PostToolUse	PostToolUse:Bash	success
    4 PreToolUse	PreToolUse:Bash	success
    7 SessionStart	SessionStart:startup	success
    4 Stop	Stop	success
    2 UserPromptSubmit	UserPromptSubmit	success
- asked for / rewritten to:
    asked: git status
    RTK auto-rewrite: rtk git status
    result: * No commits yet on master
?? .serena/
?? a/
?? b/
?? c/
- result: success, turns 2, cost $0.040714, tokens in 18 out 185 cache-read 46150
## Claude fresh session: claude-grep
- init: claude_code_version 2.1.289, model claude-haiku-4-5-20251001, permissionMode bypassPermissions, tools 117, plugins 7
- MCP servers in the init event: plugin:context-mode:context-mode=connected, ai-memory=connected, serena=connected, jcodemunch=connected, codebase-memory=connected, qmd=connected, headroom=connected, hindsight=connected
- hook events (event, name, outcome, count):
    2 PostToolUse	PostToolUse:Bash	success
    4 PreToolUse	PreToolUse:Bash	success
    7 SessionStart	SessionStart:startup	success
    4 Stop	Stop	success
    2 UserPromptSubmit	UserPromptSubmit	success
- asked for / rewritten to:
    asked: grep -rl needle .
    RTK auto-rewrite: rtk grep -rl needle .
    result: ./b/x/util.py
./a/x/util.py
./c/util.py
- result: success, turns 2, cost $0.0340301, tokens in 20 out 262 cache-read 50141
## Codex fresh session: codex-git
- executed: /bin/bash -lc 'rtk git status' (exit 0): * No commits yet on master
?? .serena/
?? a/
?? b/
?? c/

- usage: input 39197, cached 19328, output 49
## rtk gain (upstream counter, whole host: the delta spans the E2E's interval and includes any other session's commands; the project-scoped block below is this E2E's own)
- commands 262568 -> 262601 (+33); saved tokens 124711599 -> 124711896 (+297); average saving 9.02291465765439%
- rtk gain -p (this fresh project only):
    RTK Token Savings (Project Scope)
    ════════════════════════════════════════════════════════════
    Scope: /.../.cache/e2e-fresh-project-OhobWt
    
    Total commands:    3
    Input tokens:      108
    Output tokens:     28
    Tokens saved:      80 (74.1%)
    Total exec time:   10ms (avg 3ms)
    Efficiency meter: ██████████████████░░░░░░ 74.1%
    
    By Command
    ───────────────────────────────────────────────────────────────────────
      #  Command                   Count  Saved  Total%    Time  Impact    
