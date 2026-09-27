<!-- native-agent-stack:codex-user-instructions:begin (adoption/templates/codex.AGENTS.template.md) -->
<!-- native-agent-stack:top-rule -->
Top rule: never self-write without a SOTA source; upstream and the installed client are the source of truth.
Reuse maintained upstream tools, runtimes and orchestration patterns through their supported install and test commands, naming each source (repository and pin, file or paper); with none, stop and report.
Check capability claims in order: installed client (commands, --help, settings), upstream changelog for that version (gh api), upstream source at that tag, official docs. Absence claims need the first two, else say "not found in X, Y".
Worker, docs-agent and cross-family answers are leads; relay claims only with upstream citations.
Process large output outside the model.
When a claim proves wrong, record the correction and its verification path that turn.

<!-- native-agent-stack:rtk-upstream rtk-ai/rtk v0.50.0 hooks/rtk-awareness-full.md, verbatim -->
# RTK

Prefix every shell command with `rtk`: `rtk git status`, `rtk cargo test`,
`rtk npm run build`, `rtk ls src/`. Keep the prefix inside chains:
`rtk git add . && rtk git commit -m "msg"`. Commands RTK has no filter for
run as-is, so the prefix is always safe.

# Command output

Command output here is condensed to save tokens, keeping every signal and
dropping costly noise. Treat it as the complete result: run commands
normally, and batch related commands into one call to avoid extra turns.
Truncated results state their recovery path in their own output. Re-run a
command as `rtk proxy <cmd>` only when its result is unusable: empty when
output was clearly expected, contradicting its exit code, or garbled.

## About RTK

RTK (Rust Token Killer) is a CLI proxy that filters command output to save
tokens; behavior and exit code are unchanged.

- `rtk gain` / `rtk gain --history` — token savings, overall and per command.
- `rtk proxy <cmd>` — run a command unfiltered, still tracked.
- `RTK_DISABLED=1 <cmd>` — skip RTK for one command.
- `rtk discover` — find past commands RTK could have condensed.

<!-- native-agent-stack:rtk-exceptions -->
## Exceptions to the RTK prefix rule (rtk 0.50.0)

An explicit `rtk` prefix bypasses rtk's own exclusion list, so "the prefix is always safe" does not hold for these commands: rtk changes their output or exit status. Run them natively, or as `rtk proxy <command>` to keep the call tracked:
- `git show REV:path` in any form, including `git -C DIR show REV:path`: rtk keeps about 8 KiB of the blob.
- `diff`: on a missing file rtk exits 1, where diff exits 2.
- `git branch`: rtk can list a branch checked out in another worktree as remote-only.
- `git log` when the complete history matters: rtk stops at 10 commits without a notice and drops merge commits.
- `jq`: rtk keeps 40 lines of at most 120 characters.
- `find` on a path that may not exist: rtk exits 0 with no output.

Never put `rtk` in front of a shell builtin such as `cd`, `export` or `source`: rtk exits 127 and the rest of a `&&` chain does not run.
<!-- native-agent-stack:codex-user-instructions:end -->
