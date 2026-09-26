# rtk exclude_commands widen: retained hook check (2026-09-26)

`hook-check.txt` is a retained raw capture -- exit code, stdout and stderr for each
command, in the order run -- of `rtk hook check` / `rtk hook claude` against the pinned
rtk 0.50.0 binary at `~/.local/share/codex-ecosystem/tools/rtk-0.50.0-r20260925/rtk`
(binary sha256 `23433a2a50bdeb12199cadd4b94b639238d6c38529fcba1c30c9295db5fa9517`, the
binary extracted from the upstream `rtk-ai/rtk` v0.50.0 release asset tarball
`rtk-x86_64-unknown-linux-musl.tar.gz`, asset sha256
`bc2b8902b0d9c796c82ef45f16ae2307e17757afeca5ee156235a3dc7bda5f89`, per
`evidence/receipts/rtk-050-qualification-20260925.json`), produced directly for this
branch (`claude/rtk-exclude-widen-20260926`) rather than credited to any other host's run.

## How it was produced

A scratch `XDG_CONFIG_HOME` held only `$XDG_CONFIG_HOME/rtk/config.toml`, set to exactly
the `[hooks]` block [recipes/README.md](../../../recipes/README.md#native-context-mode-and-hooks)
recommends (config sha256 `1f6126b4fd0e63d089f2869440d2c80533e6af5b121d655353c5af182cfcccef`)
-- no other keys, so none of this host's other production exclusions could interfere. A
scratch `RTK_DB_PATH` kept the run off the production `history.db`. `rtk hook check
<command>` was run once per listed command (exit 1, "No rewrite for: ..." on stderr = the
native command runs; exit 0, the rewritten form on stdout = rewritten to `rtk ...`), then
one `rtk hook claude` PreToolUse-JSON probe for an excluded command (empty stdout) and one
for an included command (`updatedInput`), then `rtk verify`.

## Scope

This reproduces the effect of anchoring both added patterns to the git subcommand
position: `git show REV:path` and `git branch` are excluded (native) in a bare form, a
`-C`/`-c <dir>` form, a `--git-dir`/`--work-tree <dir>` form (the same global options
rtk's own discovery strips before dispatch, `GIT_GLOBAL_OPT`,
`src/discover/registry.rs:78`) and another `--flag` form, while `git log`, `git status`,
`git push`, `git commit` (even one whose message argument contains the word "branch") and
`git show --stat`/`git show <rev>` (no colon-blob) still get rewritten to `rtk ...`. The
`show` pattern can still match a `git show` call whose *later* argument contains `:` (for
example `--pretty=format:%h`); that stays harmless, since the command then runs natively
and the only cost is the lost `rtk` output compression. This file verifies only that the
new command-pattern matching excludes `git show REV:path` and `git branch` in these
forms; it does not reproduce rtk's separate `git branch -a` branch-name-compaction bug
that these exclusions route around, which always keeps git's local `+ ` prefix
(`git_cmd.rs` lines 3209-3211) but only misreports a branch as remote-only when a
remote-tracking branch of the same name also exists (`git_cmd.rs` lines 3224-3227)
(recipes/README.md).

This file does not repeat the 2026-09-25 qualification's broader acceptance-script
pass/fail counts (`evidence/receipts/rtk-050-qualification-20260925.json`), and it is not
the laptop's separate 2026-09-26 ultracode E2E that first found the two gaps this widen
fixes -- that receipt is sibling PR #316's artifact
(`evidence/artifacts/token-e2e-ultracode-laptop-20260926/receipt.json`), cited here only
for the discovery, not as verification of this change.
