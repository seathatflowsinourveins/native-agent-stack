# Decision: RTK's Codex PreToolUse hook is qualified and becomes the upstream default for Codex hosts, installed with `rtk init -g --codex` and trusted through Codex's own config writer (2026-10-04)

**Decided by:** the user's directive of 2026-10-04, as the command center (session `wsl-architecture-design`) and session
native-agent-stack-5f relayed it. About 21:30Z, in 5f's session: "install cleanly with upstreamcommands, best sota practice natively, and e2e
with upstream commands with new session launched e2e for our wsls". About 22:05Z, to the command center: "yes frictionless", which the
command center reads as covering the authorization settings and the trust grant of a plan-installed, qualified upstream hook. The session
that wrote this record heard neither quotation itself; both are relayed, and the grant below rests on that reading, which the user may
withdraw. Evidence for the qualification and the proposal to flip came from session native-agent-stack-99; the command center said "go" on
the flip the same evening, to be written on main after the install plan's rows (PR 684) land.

**Status:** this record lands with the trust tool, its tests and the evidence (the first of two pull requests, which touch no file
that PR 684 owns). The install plan's RTK row, the handbook and card text follow in a second pull request once PR 684 lands on
main, because the plan rows are its; until then no host installs or trusts the hook, and the awareness block of the Codex
`AGENTS.md` is reconciled with rtk 0.51.0 separately, by session native-agent-stack-5f, which owns the Codex roles that carry it.

**Scope:**

- the install plan's RTK row (`evidence/artifacts/new-wsl-install-plan-20261002/`): `rtk init -g --codex`, the trust grant and their acceptance (second pull request);
- `tools/adoption/codex_hook_trust.py` (new) and its tests (first pull request);
- the awareness block of `adoption/templates/codex.AGENTS.template.md` and its generated and scaffold copies (session native-agent-stack-5f's change, not this pair of pull requests);
- the hold-out lines of `docs/token-session-handbook.md` and the `docs/token-efficiency-stack.json` card, and what is generated from them (second pull request);
- the evidence in `evidence/artifacts/token-stack-fresh-session-e2e-20261004/` (first pull request).

## Context

At the RTK 0.50.0 pin this catalog ran no Codex hook: `rtk init --global --codex` had started to install a Codex PreToolUse hook that "this
catalog has not qualified" (`docs/token-session-handbook.md`), where 0.49.0 had written instructions only, as an `@RTK.md` line that Codex
does not expand. Codex homes got RTK's text from the stack's `AGENTS.md` block instead, and the model prefixed `rtk` itself. At 0.51.0 upstream
documents the hook as the Codex integration (rtk-ai/rtk v0.51.0, commit e001f773f80b22b7dc4c7a79521b30e35aaef026, `README.md` L133 and L460:
"**Codex** | `rtk init -g --codex` | PreToolUse hook (`updatedInput`) + AGENTS.md"), and the user's directive asks for the upstream install.

## Decision

1. A Codex host installs the hook with the upstream command `rtk init -g --codex` and trusts it with
   `python3 tools/adoption/codex_hook_trust.py --command "rtk hook codex" --apply`. Codex skips a non-managed hook until its hash equals
   `[hooks.state."<key>"].trusted_hash` (openai/codex rust-v0.159.3, commit 01fc69f4026735edfdf6789820549727a4867b11:
   `codex-rs/hooks/src/engine/discovery.rs` hook_hash L775, hook_trust_status L794-L815), so the registration alone changes nothing. The
   tool sends the edit the TUI's `/hooks` review sends, `config/batchWrite` of `hooks.state`, mergeStrategy upsert,
   `{"<key>": {"trusted_hash": <currentHash>}}` (`codex-rs/tui/src/hooks_rpc.rs` write_hook_trusts L58-L91), for the user-layer hooks whose command
   equals one named with `--command` and for no other hook; a dry run is the default, `--apply` backs up `config.toml` (mode 0600), refuses
   while a codex process runs and reads every named hook back through `hooks/list` by key and hash (a hook that vanished, moved or
   changed during the write, or a discovery error that was not there before it, is exit 3: `expectedVersion` guards `config.toml`, not the
   hooks file). This grant is the trust decision for the hook that sees every Bash command; the user's "yes frictionless" above is its authority.
   The upstream command is not hook-only: it also creates `RTK.md` and appends a pointer line `@<Codex home>/RTK.md` to `AGENTS.md`
   (`rtk-init-codex-probe.json`; `--hook-only`, `--no-patch` and `--auto-patch` are refused with `--codex`). Codex expands no `@` reference,
   so the pointer is inert text, and NativeStack's `AGENTS.md` already carries it; but it is an edit of the instruction file, which the
   user's reply about authorization settings does not name, so the second pull request lists it among the points for the user to confirm.
   `rtk init -g --codex --uninstall` removes the hook, `RTK.md` and the pointer together.
2. The row's acceptance is `rtk init --show --codex` with every line `[ok]`, `codex_hook_trust.py --command "rtk hook codex"` reporting the
   hook trusted, a fresh `codex exec --json --ephemeral` probe whose executed command carries the `rtk` prefix from each real launcher (the
   hook is the bare command `rtk hook codex` and fails open and silent when `rtk` is not on the launcher's PATH), the fresh-session E2E
   (`fresh_session_e2e.sh`) and the Codex arm of `codex_hook_qual.py`, with the five `exclude_commands` of
   `fixtures/rtk-hook-exclusions.toml` in rtk's config file (`rtk rewrite "diff a b"` printing nothing shows them in place).
3. The awareness block of the Codex `AGENTS.md` template stays (with the hook the model's own prefix is left alone: no `rtk rtk`) and its
   exceptions are reconciled with rtk 0.51.0 as measured (`rtk_behaviour_probe.py`): the hook leaves `git show REV:path`, `diff`, `jq` and
   `git branch` alone only under the five `exclude_commands` of `fixtures/rtk-hook-exclusions.toml`, which the bootstrap installs for the
   Claude hook and the Codex hook reads from the same rtk config (with upstream defaults rtk rewrites all four); `find` on a missing path
   exits 1 like find; bare `git log` caps at 10 commits without a notice and drops merge commits, `git log --stat` caps at 10 with the
   notice, and `--oneline` or `--format` without a count default to 50 commits, again without merges or a notice
   (`git_cmd.rs` L1819-L1825 at e001f773; measured on a 66-commit fixture).
4. The hold-out in the handbook and in the token-efficiency card becomes this decision and its evidence.

## Evidence (`evidence/artifacts/token-stack-fresh-session-e2e-20261004/`)

| Claim | Evidence class | Source |
| --- | --- | --- |
| `rtk init -g --codex` appends one PreToolUse group after the existing ones, changes no other byte, is idempotent, reversible with `--uninstall`, and Codex's `hooks/list` loads it without error | `local_integration`: the upstream commands on a scratch copy of the host's hooks.json; the live file was hashed before and after | README, "Codex rtk hook qualification" |
| With the hook trusted, 22 of the 23 commands of the four arms that exercise it (R1, R2, B2, R2b) ran with the `rtk` prefix (the 23rd, `diff`, is excluded by the host's `exclude_commands`, which the arms ran with), exit codes equal to the shell's in all seven arms (0 2 1 0 1 0 and 0 0 1 2 0), nothing blocked, a second PreToolUse hook ran in every trusted arm | `local_integration`: real codex-cli 0.159.3 and rtk 0.51.0 through the loopback gateway, one run per arm | `receipt.json`, `codex_hook_qual.py` |
| An untrusted hook is skipped, in that arm together with the other hook; a hook with `rtk` off the PATH fails open; a model-prefixed command gets no second prefix | same | same |
| The trust edit works through `codex_hook_trust.py` on the real binary: dry run, apply with backup, idempotent second run, exit 4 when no hook has the command | `local_integration`: a scratch home | the arms above ran with it; its fake-server tests are `synthetic` (22 tests) |
| The trust tool's read-back, when the hook's definition changes right after the write, on the real binary: the tool at `c8613fe16` reported success (exit 0), the fixed tool exits 3 and names the hook | `local_integration`: real `codex app-server` 0.159.3, a scratch home, one run each | `trust_readback_race.py`; `receipt.json`, `trust_readback_race` |
| rtk 0.51.0's rewrite table with upstream defaults and with the five `exclude_commands`, and its compact forms against the shell's (the log cap and its notice, dropped merges, the trailing newline, `/usr/bin/ls`, `find` exit 1) | `local_integration`: one run, one host, a scratch repository and scratch homes | `rtk_behaviour_probe.py`; `rtk-behaviour-probe.json` |
| `rtk init -g --codex` also creates `RTK.md`, appends the `@<Codex home>/RTK.md` pointer to `AGENTS.md` (creating it when missing) and rtk's history database, honours `CODEX_HOME`, is idempotent, is undone whole by `--uninstall`, and refuses `--hook-only`, `--no-patch` and `--auto-patch` | `local_integration`: one run, one host, scratch homes | `rtk_init_codex_probe.py`; `rtk-init-codex-probe.json` |
| `rtk-ai/rtk` v0.51.0 and `openai/codex` rust-v0.159.3 behave as the citations above say | `source_review` | the pinned README and source lines |
| A fresh Claude and Codex session on NativeStack picks the token stack up with nothing per project, and rtk rewrites show in the hook events | `local_integration` | `nativestack-before-snapshot.summary.md` |

## Alternatives considered

- **Keep the hold-out** (the 0.50.0 state, instructions only). Rejected: the user's directive is the upstream install, the qualification passed,
  and the hook handles four of the six exceptions of the awareness text itself.
- **Copy the hook entry from a template** instead of running `rtk init -g --codex`. Rejected: it is not upstream's command, and the entry
  would drift from what rtk writes (rtk owns the hooks.json patch, its idempotence and its `--uninstall`).
- **Trust through the interactive `/hooks` review.** Not automatable on a fresh distribution; kept as the way a user reviews or revokes.
- **`--dangerously-bypass-hook-trust`.** Present in 0.159.3 (`codex exec --help`; `codex-rs/utils/cli/src/shared_options.rs` L61-L64 and
  `codex-rs/exec/src/cli.rs` L145 at `01fc69f4`): "Run enabled hooks without requiring persisted hook trust for this invocation.
  DANGEROUS." Rejected as the install path: it persists nothing, so every launcher (the TUI, each `codex exec`, a wrapper) would have to
  carry it, and it skips trust for every enabled hook, where the persisted grant is bound to one hook's hash and `/hooks` shows and revokes it.
  An earlier draft of this record said the flag was absent; that came from a `head`-truncated filter of the help text (anti-pattern log).
- **Trust every hook of the home.** Rejected: the tool names the command it trusts and ignores every other hook, a managed one and a project's.
- **An absolute path in the hook command** to survive a launcher without `rtk` on its PATH. Rejected: it departs from upstream's command; the acceptance
  probes each real launcher instead.

## What would overturn it

- The fold A/B of session native-agent-stack-5f (harbor-rtk-fold-20261004) measuring wrong-path actions that the Codex hook's folding of
  `grep -l` output causes beyond the upstream-native `exclude_commands` remedy: the row then adds that exclusion, or holds the hook out again.
- A Codex release that changes the trust model or the hook schema (`hooks.state`, `trusted_hash`, the hash), or an rtk release whose
  `rtk hook codex` or `rtk init -g --codex` changes the hook's definition (its hash changes and the grant must be repeated).
- The user withdrawing the reading of "yes frictionless" for this grant: the row then stops after `rtk init -g --codex` and leaves the review to `/hooks`.

## Residuals

The install edits the Codex instruction file (the inert pointer line) and creates `RTK.md`; the user approved that edit on 2026-10-05
(the addendum below). One run per arm, one host, the loopback gateway route and not the host's ChatGPT sign-in; no claim about tokens saved. Native probes ran on
codex-cli 0.159.3 only: no 0.160.0 binary was run, so 0.160.0 is checked from source only. The hook is skipped
again whenever its definition or its group index changes (the key carries the index), so the acceptance probe is the check, not the grant. The
2604 after snapshot, the PATH of each real launcher and the grant on a real host are later steps that this decision schedules and does not
run. Cosmetic differences remain (a dropped trailing newline in `rtk git status --short`, `/usr/bin/ls` in an `rtk ls` error), and so do
content differences in rtk's compact `git log` (merge commits dropped, a 10-commit cap, a 50-commit default for `--oneline` and `--format`), which the awareness reconcile carries. A dry run of
the trust tool makes no trust or config edit but is not read-only: starting the app-server creates its own state files in the Codex home.
The NativeStack counter delta of the snapshot (+33 commands, +297 saved tokens) spans other sessions' commands; the project-scoped block of
its summary is the E2E's own.

## Addendum (2026-10-05): the pointer line is approved

The upstream command `rtk init -g --codex` appends an inert `@<Codex home>/RTK.md` pointer to the Codex `AGENTS.md` and creates `RTK.md`
(`rtk-init-codex-probe.json`; there is no hook-only mode with `--codex`). That is an instruction-file edit, which the earlier reply about
authorization settings does not name, so the command center put it to the user as one yes/no question and relayed the answer. By the command center's transcript the user wrote,
on 2026-10-05, "yes for rtk pointer" at 00:49:16Z (part of a longer message) and, as a queued message at 00:50:08Z, a standing rule: "for the
practice like rtk, always proceed with sota convergence highest quality practice with upstream repos". (The command center first relayed
them as "about 00:55Z", an estimate, and corrected the times afterwards.) The session that wrote this record heard neither quotation itself;
both are the user's words as the command center relayed them, and the row's behaviour rests on that reading, which the user may withdraw.

Effect: the install plan's `command-output` row runs `rtk init -g --codex` as upstream implements it, pointer line and `RTK.md` included, and
the same rule covers future upstream installer side effects of this kind (each still recorded with its measurement). `rtk init -g --codex
--uninstall` removes the hook, `RTK.md` and the pointer together.

## Addendum (2026-10-05, review of #705): approval and execution rules

The Codex review of #705 asked whether the rewrite happens before or after Codex's approval and policy evaluation, and whether a mutating command such as
`git push` can pass as `rtk git push` with a different approval class. The answer, from the upstream sources at both Codex pins (rust-v0.159.3 `01fc69f40267`
and rust-v0.160.0 `a956835d0207`, identical lines) and rtk v0.51.0 (`e001f773f80b`):

1. **The rewrite comes first.** `codex-rs/core/src/tools/registry.rs` L603-L660 runs the PreToolUse hook (`run_pre_tool_use_hooks`, L604) and, when the hook
   returns `updatedInput`, replaces the call (`invocation = updated_invocation`, L632); only then does the handler, with its approval and sandbox path, run
   (`handle_any_tool`, L689). A hook's `permissionDecision: "allow"` is the protocol shape that lets `updatedInput` through, not an approval
   (`codex-rs/hooks/src/events/pre_tool_use.rs` L388-L405; `deny` blocks, L357). rtk says the same (`hooks/codex/README.md` L14-L24: Codex "applies the
   replacement before its normal command approval and sandbox checks ... classification is based on the rewritten command ... This can add prompts for
   known-safe commands or obscure signals for wrapped mutating commands such as `git push`"; `src/hooks/hook_cmd.rs` L975-L989).
2. **Approval sees the rewritten command's words.** `codex-rs/core/src/exec_policy.rs` L327-L420 builds the approval requirement from the command words:
   execution rules are matched by prefix (`check_multiple_with_options`, L375) and an unmatched command falls to the approval-policy fallback
   (`render_decision_for_unmatched_command_for_platform`, L770-L850: `never` allows and relies on the sandbox, `untrusted` prompts for every unmatched command,
   L816). On codex-cli 0.159.3, `codex execpolicy check` with a rule forbidding `git push` and one prompting `git commit` returns `forbidden` and `prompt` for
   those commands and no decision for `rtk git push` and `rtk git commit` (`plan-row-scratch-run.json`, `execpolicy_check`).
3. **The one built-in dangerous-command heuristic is not touched.** `codex-rs/shell-command/src/command_safety/is_dangerous_command.rs` L133 flags only a forced
   `rm` (and unwraps `sudo`, L138, and `env`, L143, not `rtk`), and rtk 0.51.0 does not rewrite `rm`, `mv`, `chmod`, `sed -i`, `tee` or `dd`
   (`rtk-behaviour-probe.json`, `codex_hook_check`: `rtk hook check --agent codex` over 55 commands).
4. **rtk does rewrite mutating commands.** Of the 55, 36 are rewritten, among them `git push` (also `--force`), `git commit`, `git add`, `git checkout`,
   `git pull`, `git stash`, `git worktree add`, `gh pr merge`, `gh pr create`, `gh api -X DELETE`, `docker run`, `docker exec`, `docker build`, `kubectl apply`,
   `helm install`, `pulumi up`, `pip install`, `cargo install`, `make install`, `curl -X POST`, `wget`, `rsync --delete`, `aws s3 rm` and `iptables -F`; 19 are
   not (`git reset --hard`, `git clean -fd`, `git rebase`, `git merge`, `git rm`, `docker rm`, `kubectl delete`, `terraform apply`, `npm install`, `npm publish`,
   `cargo publish`, `systemctl stop`, `rm -rf` and the others above). The five `exclude_commands` change none of these decisions. "RTK never rewrites mutating
   commands" is false, so it cannot be the proof; rtk itself reads no Codex rules (`src/hooks/permissions.rs` L64-L72: Codex "enforces its native execution
   rules after updatedInput").
5. **What changes, for whom.** On a host with no execution rules the class of a rewritten mutating command does not change: an unmatched command's decision
   depends on the approval policy and the sandbox, not on its words, except for the forced-`rm` heuristic, which rtk leaves alone; under `untrusted` every
   unmatched command prompts anyway, and rtk notes that known-safe commands may gain prompts. On a host whose rules name commands rtk rewrites, the rule no
   longer matches the rewritten form, so a `forbidden` or `prompt` rule on `git push` is bypassed for `rtk git push`. NativeStack2604 runs the authorization
   settings (approvals off), where no rule is consulted.

**Decision.** Keep the upstream install, and make activation conditional on the one host state that changes the class. `codex_hook_trust.py --apply`
refuses (exit 2) while the user layer's `rules/` directory holds a rules file with content, names the files, and proceeds only with `--allow-exec-rules`,
the explicit acceptance after the rtk forms of the rules are written or the commands are excluded in rtk's `exclude_commands`; `--check` and the dry run only
name the rules. Six tests were written first (five red); the scratch run shows the refusal (exit 2), `--check` still 5, the accepted trust 0, and the
evaluator's decisions (`plan-row-scratch-run.json`). The operating rule for rule authors: write both forms (`prefix_rule(pattern = ["rtk", "git", "push"],
decision = "forbidden")` beside the plain one) and verify with `codex execpolicy check`. Limits: rules in a project's `.codex/rules` or a managed layer are not
visible to the tool, and rules written after the grant are not re-checked. No live Codex session was run with a forbidding rule and the hook active; the
session behaviour is derived from the dispatch order above and the same evaluator that `codex execpolicy check` runs (untested boundary).

**Alternatives.** (a) *Limit the hook to a read-only rewrite set with `exclude_commands`*: rtk's option is exclusion-only (`src/core/config.rs` L119-L123;
`src/discover/registry.rs` L1548-L1582: a pattern starting with `^` is a regex without look-around, any other is a literal prefix, and a trivial pattern is
ignored), so an allow-list cannot be written, and a deny-list of every state-changing prefix among the registry's 96 patterns (`src/discover/rules.rs`) would
track upstream's registry, change the shared config that the Claude hook and the recipe's five-entry table also read, and cost compression only on short
mutating-command output; not done here, and it is the first thing to do if a rule bypass is ever observed. (b) *Prove rtk never rewrites mutating commands*:
false (item 4). (c) *Hold the Codex hook out again*: against the user's directive of 2026-10-04. (d) *Ship `rtk ...` rules with the plan*: under
`approval_policy = "never"` a `prompt` rule is rejected by policy and becomes `forbidden` (`exec_policy.rs` L216-L236 and the match at L407-L415), which would block the
authorization-settings hosts.
