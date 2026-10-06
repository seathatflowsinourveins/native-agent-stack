# Token stack fresh-session E2E and the Codex rtk hook qualification (2026-10-04)

Local monitoring and qualification with upstream commands only. It is not an A/B and not an upstream test: one run per arm, one
host (NativeStack, WSL2), deterministic commands. It answers two questions the clean-install directive of 2026-10-04 asks of
each WSL: does a brand-new session pick up the token stack with nothing registered per project, and may RTK's Codex hook, held
out at the 0.50.0 pin because it was not qualified, be installed with `rtk init -g --codex`.

| Part | Script | Reads |
| --- | --- | --- |
| Fresh-session E2E | `fresh_session_e2e.sh <label>` | `rtk --version`, `rtk init --show`, `rtk gain -f json` before and after, `claude mcp list`, `codex mcp list`, two fresh `claude -p --output-format stream-json --verbose --include-hook-events` sessions (git status, grep -rl), one fresh `codex exec --json --ephemeral` session, all in a new empty project directory, summarised with jq |
| Codex hook qualification | `codex_hook_qual.py [outdir [arm ...]]` | `rtk init -g --codex`, `rtk init --show --codex`, Codex's own `hooks/list`, `tools/adoption/codex_hook_trust.py`, `codex exec --json --ephemeral` through the loopback OmniRoute gateway (no credential needed or copied), `rtk gain` |
| Plan row scratch run | `plan_row_scratch_run.py [outfile]` | the install plan's `command-output` Codex steps in a scratch HOME, their text read from `install-plan.json`: the exclusions config, `rtk init -g --codex`, the trust, the post_install program, the after_sign_in jq filter on synthetic streams, and the trust tool's execution-rule review in more scratch homes with the real rtk and codex (`fixtures/hcom-deny.rules` from #713 by its exact bytes and with one added comment line, the allow-only files of Codex and hcom, a configured transparent prefix, a user TOML filter, a `git push` forbid rule with and without its `rtk` twin, the counterexamples of the 705e and 705f reads, an unreadable rules directory), plus `rtk hook check` and `codex execpolicy check` on them: `plan-row-scratch-run.json` |
| Rewrite heads | `derive_rtk_rewrite_heads.py --source <rtk clone> --write FILE` (`--check`, `--list`) | the command heads rtk 0.51.0 can rewrite, derived from its source at the pin (the leading tokens of the 94 RULES patterns and 62 builtin TOML filters, found by walking the parsed regexes, plus the process and shell wrappers and the env prefix): `rtk-rewrite-heads.json`, review evidence for the reviewed list that the tool does not read |
| Rewrite heads check | `check_rtk_rewrite_heads.py [outfile]` | that file and the reviewed entries of `tools/adoption/exec_rules_reviewed.json` against the real rtk (upstream defaults, a scratch HOME): a positive control per RULES pattern (94 of 94 rewritten), a scan of 1,449 command names with 9 argument shapes (13,041 commands, 623 rewritten, none outside the heads), 8,884 spellings of the 101 literal heads (paths, other case, quotes, escapes, .exe/.bat/.cmd/.ps1, suffixes, trailing slash, backslash paths: 480 rewritten, none outside the heads) and 67 wrapper prefixes in front of `git status` (24 rewritten, all led by a head), the 705e counterexamples and the 352 commands of the reviewed entry's first tokens (`hcom`, `uvx`) in 22 spellings and 8 shapes (none rewritten): `rtk-rewrite-heads-check.json` |
| Rule review mutation check | `rule_review_mutation_check.py` | 63 mutants of the execution-rule review in `tools/adoption/codex_hook_trust.py`, each of which must fail at least one test of `tests/test_codex_hook_trust.py`; works on a temporary copy: `rule-review-mutation-check.txt` |
| rtk init probe | `rtk_init_codex_probe.py [outfile]` | what `rtk init -g --codex` writes, shows and undoes in scratch homes (no host file): `rtk-init-codex-probe.json` |
| rtk behaviour probe | `rtk_behaviour_probe.py [outfile]` | `rtk rewrite` and rtk's compact forms against the shell, in a scratch repository and scratch homes (no host configuration, no host counter): `rtk-behaviour-probe.json` |
| Read-back race | `trust_readback_race.py [tool file]` | `tools/adoption/codex_hook_trust.py` against the real `codex app-server` when the hook's definition changes right after the write |

Run the first inside a distribution (about 30 s, about 8 cents of Haiku for two probes plus one low-effort Codex probe). Run the
second from the repository (about 5 min for seven arms of one or two sessions each): it builds scratch Codex homes and a fixture
repository under `~/.cache/native-agent-stack-e2e`, never writes the live `~/.codex` (it hashes the live hooks.json before and
after), and deletes its work directory. Files here: `receipt.json` (the sanitized results below),
`nativestack-before-snapshot.summary.md` (the E2E's own summary, home paths replaced), `rtk-behaviour-probe.json` and
`rtk-init-codex-probe.json` and `plan-row-scratch-run.json` (the probes' and the scratch run's output).

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
- `rtk gain -f json` moved by 33 commands and 297 saved tokens over the interval of the probes; the counter is host-wide and other
  sessions ran, so that delta is not the probes' alone (the project-scoped `rtk gain -p` block of the summary is).

## Codex rtk hook qualification (rtk 0.51.0, codex-cli 0.159.3)

Static, on a scratch HOME and CODEX_HOME holding a copy of the host's hooks.json: `rtk init -g --codex` appends one PreToolUse
group, `{"matcher":"Bash","hooks":[{"type":"command","command":"rtk hook codex"}]}`, after the existing group and changes no
other byte, so the existing hooks keep their keys (`hooks.json:pre_tool_use:0:0`: a key carries the group index) and their
trust; a second run is "already present"; `--uninstall` removes the entry (the JSON equals the original after normalising; rtk
reserialises the file and leaves a `.bak`); Codex's own `hooks/list` loads it with no error or warning.

The same command is not hook-only (`rtk-init-codex-probe.json`: scratch homes, rtk 0.51.0). It also creates `RTK.md` in the Codex
home, appends the line `@<absolute Codex home>/RTK.md` to its `AGENTS.md` (creating the file when it is missing) and creates rtk's
history database under its data directory; it prints the optional `writable_roots` grant for that database and applies none ("No
Codex permission settings have been changed"), and it honours `CODEX_HOME`. A second run reports "already present".
`--uninstall` removes the hook entry, `RTK.md` and the pointer line and leaves an emptied `AGENTS.md`. `--hook-only`, `--no-patch` and
`--auto-patch` are refused with `--codex` (exit 1, "rtk: --codex cannot be combined with ..."), so there is no hook-only Codex
install. `rtk init --show --codex` reports the Global lines (RTK.md, hook, AGENTS.md pointer) `[ok]` after the install and `[--]`
after the uninstall; its Local lines concern the current directory's `.codex/`, so an acceptance reads the Global lines only. Codex
expands no `@` reference in `AGENTS.md` (`docs/token-efficiency-stack.md`, citing `codex-rs/codex-home/src/instructions/mod.rs` at
rust-v0.157.1), so the pointer is inert text; NativeStack's `~/.codex/AGENTS.md` already carries it from an earlier `rtk init`, and
the stack's AGENTS block keeps it. Installing the hook is therefore also an edit of the Codex instruction file.

Dynamic, seven arms over six commands (and five more in arm B2), a probe hook at group 0 standing for ai-memory. The arms ran with
the host's HOME, so rtk read the host's own configuration, a `[hooks] exclude_commands` of the five entries of
`fixtures/rtk-hook-exclusions.toml` (`git show REV:path`, `diff`, `git branch`, `jq`); the Codex hook honours it:

| Arm | Hook | Trusted | Executed with `rtk` | Exit codes equal to the shell's |
| --- | --- | --- | --- | --- |
| R0 | none | n/a | 0 of 6 | yes |
| R1 | rtk | yes (`codex_hook_trust.py`) | 6 of 6 (a compound only in its first segment) | yes |
| R1u | rtk | no | 0 of 6; the probe, also untrusted, never ran | yes |
| R2 | rtk, awareness text present, prompt forbids a prefix | yes | 6 of 6 | yes |
| R2b | rtk, awareness text present, prompt silent | yes | 6 of 6, all prefixed by the model; no `rtk rtk` | yes |
| B2 | rtk | yes | 4 of 5: `diff` is excluded by that configuration, `cat` becomes `rtk read` | yes |
| R1p | rtk, `rtk` not on the launcher's PATH | yes | 0 of 6: the hook fails open, silently | yes |

The six commands and their shell exit codes: `git status --short` 0, `ls /nonexistent` 2, `grep -rl nomatch .` 1, `grep -rl needle .`
0, `git diff --exit-code` 1, `git status --short && echo done` 0; battery 2: `git log --oneline -3 | cat` 0, `grep -rn "needle two" a` 0,
`find /nonexistent -name x` 1, `diff /nonexistent a/x/util.py` 2, `cat a/x/util.py` 0.

Findings: the hook fires, preserves exit status, blocks nothing and coexists with another PreToolUse hook. Codex skips a hook until
its current hash equals `[hooks.state."<key>"].trusted_hash` (upstream, rust-v0.159.3:
codex-rs/hooks/src/engine/discovery.rs hook_hash L775 and hook_trust_status L794-L815), so `rtk init -g --codex` alone changes
nothing; the TUI's `/hooks` review persists the grant with `config/batchWrite` of `hooks.state` (upsert) and
`tools/adoption/codex_hook_trust.py` sends the same edit for the hooks named with `--command` only (codex-rs/tui/src/hooks_rpc.rs
write_hook_trusts L58-L91). `codex exec --help` of 0.159.3 does list `--dangerously-bypass-hook-trust` ("Run enabled hooks without
requiring persisted hook trust for this invocation. DANGEROUS."; openai/codex rust-v0.159.3, commit 01fc69f4,
codex-rs/utils/cli/src/shared_options.rs L61-L64 and codex-rs/exec/src/cli.rs L145; this repository's capture
`evidence/artifacts/runtime-sdk-20261003/exec-help-0.159.3.txt` L65). It persists nothing and skips trust for every enabled hook, so
it is not the hash-bound grant this tool writes. (An earlier draft of this README said the flag was absent: it had filtered the help
text through `head -8`; see the anti-pattern log in docs/harness-defaults.md.)

What rtk does is in `rtk-behaviour-probe.json` (rtk 0.51.0, git 2.43.0; a scratch repository of 66 commits with one merge and
scratch homes, so no host configuration applies). `rtk rewrite "<cmd>"` with upstream defaults rewrites `git status`, `git log`,
`git diff`, `ls`, `cat` (to `rtk read`), `grep`, `find`, `git show REV:path`, `diff`, `jq`, `git branch` and the first segment of a
pipe or `&&` chain, and leaves `echo` and `bash -c ...` alone (exit 1, no output); with the five `exclude_commands` of
`fixtures/rtk-hook-exclusions.toml` as rtk's config file it also leaves `git show REV:path`, `diff`, `jq` and `git branch` alone.
The compact forms differ from the shell's: `rtk git status --short` drops the trailing newline and `rtk ls /nonexistent` names
`/usr/bin/ls` in its error. Exit codes are the shell's, `find` on a missing path included (1: the awareness text's "exits 0" does
not hold at 0.51.0). Bare `rtk git log` prints at most 10 commits, one `<hash> <subject> (<age>) <author>` line each, drops the
merge commit and prints no notice; `rtk git log --stat` caps at 10 commits, keeps the merge and prints `[rtk] capped at 10 commits;
pass -n <count> for more` on stderr; with `--oneline`, `--format=%s` or `--graph --oneline` and no count it defaults to 50 commits,
without merges, and prints no notice (50 lines against git's 66, 66 and 68; `src/cmds/git/git_cmd.rs` L1819-L1825 at e001f773:
`--oneline`, `--format` and `--pretty` without a count add `-50`); an explicit count is respected and keeps merges (`-n 16`: 16
lines; `--oneline -n 66`: 66). A fixture shorter than 50 commits cannot show that default, and an earlier draft of this README, run
on 16 commits, called those forms uncapped.

Mutating commands and execution rules (`rtk-behaviour-probe.json`, `codex_hook_check`; `plan-row-scratch-run.json`, `execpolicy_check`). `rtk hook check
--agent codex` rewrites 36 of 55 commands, among them mutating ones (`git push`, `git commit`, `git add`, `git checkout`, `git pull`, `gh pr merge`,
`docker run`, `kubectl apply`, `pip install`, `curl -X POST`, `aws s3 rm`), and leaves `rm -rf`, `mv`, `chmod`, `sed -i`, `git reset --hard`,
`terraform apply` and 13 others alone; the five `exclude_commands` change none of them. Codex replaces the call with the hook's `updatedInput` before its
handler's approval path (`registry.rs` L603-L660 at rust-v0.159.3 and rust-v0.160.0) and matches execution rules against the rewritten command's words:
`codex execpolicy check` on 0.159.3 returns `forbidden` for `git push` and no decision for `rtk git push` under the same rule. The trust tool therefore
reviews the user layer's rule files first and parses nothing (three reads each found a bypass in an analysing version): a file passes by its sha256 on
`tools/adoption/exec_rules_reviewed.json` (an exact-bytes review for rtk 0.51.0 and its default hook configuration; `rtk-rewrite-heads.json` and
`rtk-rewrite-heads-check.json` are its evidence) or as Codex's own allow-only format, and any other file refuses `--apply` (exit 2, before the app-server starts).
A sample of commands cannot do this (the 705e read: `git -C .` is not rewritten but `git -C . push origin main` is, and the native evaluator forbids the original
and not the rewrite) and neither can an `rtk` twin (rtk's rewrites also change words after `rtk`: `cat f` becomes `rtk read f`, `python3 -m pytest` becomes
`rtk pytest`). `--check` exits 6 for a trusted hook beside such a file, so the post_install acceptance catches a rule file added or edited later;
`--allow-exec-rules` accepts. The scratch run (79 steps, rtk 0.51.0 and codex-cli 0.159.3): #713's `hcom-deny.rules` by its exact bytes lets the trust proceed,
and the same bytes with one added comment line, a configured rtk transparent prefix, a user TOML filter beside the reviewed file, a trusted project filter
(the real rtk then rewrites `hcom kill luna` from that project's directory) or `RTK_TRUST_PROJECT_FILTERS` with a CI variable are refused; the allow-only files
of Codex and hcom let it proceed and an allow rule that holds `rtk` (the real evaluator allows `rtk git push origin main` under `["rtk"]` and not `git push origin main`; and, 705g, allows the
rewritten shell-script token `FOO=1 rtk git push origin main` and not the original) is refused; a `git push` forbid rule (with or without its twin), `git -C .`, broad `uv` and `npx` rules, a
`host_executable(name = prefix_rule(...) or "git", ...)` file that the real codex evaluator accepts and that forbids `git push origin main`, a raw CR in a token,
a `bash -lc` script rule, `phpunit.exe`, `g++` plus a combining mark and an unreadable rules directory are refused; a rule added after the grant makes `--check`
exit 6. The decision record's 2026-10-05 addenda on #705 carry the sources, the alternatives, the correction that approvals off do not switch execution rules
off, the pin-move rule for the reviewed list and the untested boundary (no live session with a forbidding rule and the hook active).

## What this does not show

One run per arm: no variance, no cost comparison, no claim about tokens saved (the A/B of the folding of `grep -l` output is a separate
measurement). The dynamic arms ran through the loopback gateway route `cx/gpt-6.1-sol-max`, not the host's own ChatGPT sign-in, and in scratch
Codex homes (CODEX_HOME), with the host's HOME for rtk's configuration; the live `~/.codex` was neither written nor read for
credentials. The probe's `grep -rl needle .` returns one file, so it does not exercise rtk 0.51.0's file-list fold (a shared path prefix folded into
`<prefix> (N files)` with the tails listed; `src/cmds/system/search.rs` L612 at e001f773), which the control of
`docs/decisions/2026-10-04-rtk-file-list-control.md` covers. The native probes ran on codex-cli 0.159.3 only: no 0.160.0 binary was run here, so 0.160.0 is checked from source
only. The trust tool's dry run makes no trust or config edit but is not read-only: starting the app-server creates its own state
files in the Codex home. The 2604 after snapshot, the PATH of each real launcher and a hook trust grant on a real host are
separate, later steps.
