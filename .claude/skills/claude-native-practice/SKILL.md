---
name: claude-native-practice
description: Current Claude Code native practice, one evidenced default per role slot, newer than repository notes or memory. Use it first when deciding or answering how to configure Claude Code (settings, permissions, hooks, skills, MCP, subagents), harness or workflow choices (agent teams, Workflows, model and effort routing), or Claude GitHub Actions setup.
---

# Claude Code native practice

Start by reading [`reference/slots.md`](reference/slots.md) in this skill's directory: it answers for the slot your task
touches and is newer than repository notes or memory. It is the index, one row per role slot with its status, default
and `overturn_when`, and each row links to a layer page (for example `reference/native-clients.md`) holding the slot's
route, alternatives, rejections, evidence and notes. [`reference/slots.json`](reference/slots.json) is the same content
for scripts. Codex lanes follow the same practice through their own native mechanisms:
[`reference/cross-client.md`](reference/cross-client.md).

1. **Find the slot.** Match the task to one row of `reference/slots.md`, then read that slot's section on its layer page.
2. **Check currency.** Compare `claude --version` with the page's `client_version`. When the installed client is
   newer, read the CHANGELOG entries between the two versions for that slot's area
   (`gh api repos/anthropics/claude-code/contents/CHANGELOG.md -H "Accept: application/vnd.github.raw"`) and treat the
   row as current only if none changes the behaviour the default depends on. The newest page is
   <https://github.com/seathatflowsinourveins/native-agent-stack/blob/main/.claude/skills/claude-native-practice/reference/slots.md>.
3. **Follow the default.** Use the default and its route. A change to stored client configuration, hooks, hook trust or
   permissions is the command center's act: hand it a reviewed diff.
4. **Record a supersession.** When the CHANGELOG, the docs or a measured result overturns a row, name the row, the source
   at its pin and the date, and propose the dated update to the page by pull request. A token or cost saving changes a
   default only with quality parity measured on paired same-task runs.
