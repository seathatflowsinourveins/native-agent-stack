# Token stack fresh-session E2E and the Codex rtk hook qualification (2026-10-04)

Local monitoring and qualification with upstream commands only. It is not an A/B and not an upstream test: one run per arm, one
host (NativeStack, WSL2), deterministic commands. It answers two questions the clean-install directive of 2026-10-04 asks of
each WSL: does a brand-new session pick up the token stack with nothing registered per project, and may RTK's Codex hook, held
out at the 0.50.0 pin because it was not qualified, be installed with `rtk init -g --codex`.

| Part | Script | Reads |
| --- | --- | --- |
| Fresh-session E2E | `fresh_session_e2e.sh <label>` | `rtk --version`, `rtk init --show`, `rtk gain -f json` before and after, `claude mcp list`, `codex mcp list`, two fresh `claude -p --output-format stream-json --verbose --include-hook-events` sessions (git status, grep -rl), one fresh `codex exec --json --ephemeral` session, all in a new empty project directory, summarised with jq |
| Codex hook qualification | `codex_hook_qual.py [outdir [arm ...]]` | `rtk init -g --codex`, `rtk init --show --codex`, Codex's own `hooks/list`, `tools/adoption/codex_hook_trust.py`, `codex exec --json --ephemeral` through the loopback OmniRoute gateway (no credential needed or copied), `rtk gain` |

Run the first inside a distribution (about 30 s, about 8 cents of Haiku for two probes plus one low-effort Codex probe). Run the
second from the repository (about 5 min for seven arms of one or two sessions each): it builds scratch Codex homes and a fixture
repository under `~/.cache/native-agent-stack-e2e`, never writes the live `~/.codex` (it hashes the live hooks.json before and
after), and deletes its work directory. Files here: `receipt.json` (the sanitized results below) and
`nativestack-before-snapshot.summary.md` (the E2E's own summary, home paths replaced).

## NativeStack before snapshot (2026-10-04 21:44Z, before the NativeStack host steps of docs/decisions/2026-10-04-claude-template-holds-out-token-lane-carriers.md)

- rtk 0.51.0 at the pin; `rtk init --show` reports the Claude hook, RTK.md (slim) and the settings.json hook `[ok]`.
- A fresh Claude Code 2.1.289 session in an empty project connected 8 of 8 user-scope MCP servers (context-mode plugin, ai-memory,
  serena, jcodemunch, codebase-memory, qmd, headroom, hindsight) and loaded 117 tools. Its PreToolUse:Bash hook rewrote `git status`
  to `rtk git status` and `grep -rl needle .` to `rtk grep -rl needle .` ("RTK auto-rewrite", `updatedInput` in the hook response);
  SessionStart ran 7 hook commands, UserPromptSubmit 2, PostToolUse 2, Stop 4, all with outcome success.
- A fresh Codex 0.159.3 session ran `rtk git status` because the model followed the awareness text: Codex's hooks.json held no rtk
  hook (ai-memory and hindsight only), so for Codex rtk was instruction-driven (`rtk init --show --codex`: hook `[--]`).
- Gap found: SocratiCode is registered for Claude Code at local scope for one checkout (`claude mcp get socraticode`: "Local config"),
  so a fresh project does not get it although `adoption/mcp/claude-user.json` carries it at user scope; Codex lacks jcodemunch until the
  host step registers it.
- `rtk gain -f json` moved by 33 commands and 297 saved tokens across the probes; the counter is host-wide and other sessions ran.

## Codex rtk hook qualification (rtk 0.51.0, codex-cli 0.159.3)

Static, on a scratch HOME and CODEX_HOME holding a copy of the host's hooks.json: `rtk init -g --codex` appends one PreToolUse
group, `{"matcher":"Bash","hooks":[{"type":"command","command":"rtk hook codex"}]}`, after the existing group and changes no
other byte, so the existing hooks keep their keys (`hooks.json:pre_tool_use:0:0`: a key carries the group index) and their
trust; a second run is "already present"; `--uninstall` removes the entry (the JSON equals the original after normalising; rtk
reserialises the file and leaves a `.bak`); Codex's own `hooks/list` loads it with no error or warning.

Dynamic, seven arms over six commands (and five more in arm B2), a probe hook at group 0 standing for ai-memory:

| Arm | Hook | Trusted | Executed with `rtk` | Exit codes equal to the shell's |
| --- | --- | --- | --- | --- |
| R0 | none | n/a | 0 of 6 | yes |
| R1 | rtk | yes (`codex_hook_trust.py`) | 6 of 6 (a compound only in its first segment) | yes |
| R1u | rtk | no | 0 of 6; the probe, also untrusted, never ran | yes |
| R2 | rtk, awareness text present, prompt forbids a prefix | yes | 6 of 6 | yes |
| R2b | rtk, awareness text present, prompt silent | yes | 6 of 6, all prefixed by the model; no `rtk rtk` | yes |
| B2 | rtk | yes | 4 of 5: `diff` is not rewritten, `cat` becomes `rtk read` | yes |
| R1p | rtk, `rtk` not on the launcher's PATH | yes | 0 of 6: the hook fails open, silently | yes |

The six commands and their shell exit codes: `git status --short` 0, `ls /nonexistent` 2, `grep -rl nomatch .` 1, `grep -rl needle .`
0, `git diff --exit-code` 1, `git status --short && echo done` 0; battery 2: `git log --oneline -3 | cat` 0, `grep -rn "needle two" a` 0,
`find /nonexistent -name x` 1, `diff /nonexistent a/x/util.py` 2, `cat a/x/util.py` 0.

Findings: the hook fires, preserves exit status, blocks nothing and coexists with another PreToolUse hook; it differs only in
output form (`rtk git status --short` drops the trailing newline, so a compound prints `...util.pydone`; `rtk ls` names `/usr/bin/ls` in
its error). Codex skips a hook until its current hash equals `[hooks.state."<key>"].trusted_hash` (upstream, rust-v0.159.3:
codex-rs/hooks/src/engine/discovery.rs hook_hash L775 and hook_trust_status L794-L815), so `rtk init -g --codex` alone changes
nothing; the TUI's `/hooks` review persists the grant with `config/batchWrite` of `hooks.state` (upsert) and
`tools/adoption/codex_hook_trust.py` sends the same edit for the hooks named with `--command` only (codex-rs/tui/src/hooks_rpc.rs
write_hook_trusts L58-L91). `codex exec` of 0.159.3 has no `--dangerously-bypass-hook-trust`, which the Codex docs describe.
`rtk rewrite "<cmd>"` shows what the hook rewrites: git status and log, ls, cat, grep, find and the first segment of a pipe or `&&` chain; not
`git show REV:path`, `diff`, `jq`, `git branch`, `echo` or `bash -c ...`. Two exceptions of the awareness text do not hold at 0.51.0 (shell
against `rtk`, measured here): `find` on a missing path exits 1 like find, and default `git log` and `git log --stat` cap at 10 commits but
print `[rtk] capped at 10 commits; pass -n <count> for more`.

## What this does not show

One run per arm: no variance, no cost comparison, no claim about tokens saved (the A/B of the folding of `grep -l` output is a separate
measurement). The dynamic arms ran through the loopback gateway route `cx/gpt-6.1-sol-max`, not the host's own ChatGPT sign-in, and in scratch
homes; the live `~/.codex` was neither written nor read for credentials. The 2604 after snapshot, the PATH of each real launcher and a
hook trust grant on a real host are separate, later steps.
