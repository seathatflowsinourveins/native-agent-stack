# Decision: RTK's Codex PreToolUse hook is qualified and becomes the upstream default for Codex hosts, installed with `rtk init -g --codex` and trusted through Codex's own config writer (2026-10-04)

**Decided by:** the owner's directive of 2026-10-04, relayed by the command center (session `wsl-architecture-design`) and
session native-agent-stack-5f. At about 21:30Z they asked for clean upstream native installation and fresh-session WSL E2E;
at about 22:05Z they approved frictionless rollout. The command center interpreted that reply as covering authorization settings and
the hash-scoped trust grant for a plan-installed, qualified upstream hook. This writer heard neither message directly: both are
relayed, the grant rests on that reading, and the owner may withdraw it. [RTK's pinned installer](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/init/codex.rs) supplies the native installation path.
Qualification evidence and the flip proposal came from native-agent-stack-99; the command center authorized the flip that evening.
The flip was scheduled for main after the install-plan rows (PR 684) land; source support and destination execution remain separate checks.

**Status:** this record lands with the trust tool, its tests and the evidence (the first of two pull requests, which touch no file
that PR 684 owns). The install plan's RTK row, the handbook and card text follow in a second pull request once PR 684 lands on
main, because the plan rows are its; until then no host installs or trusts the hook, and the awareness block of the Codex
`AGENTS.md` is reconciled with rtk 0.51.0 separately, by session native-agent-stack-5f, which owns the Codex roles that carry it. (This paragraph is the status of 2026-10-04.
Update of 2026-10-05: PR 684 landed as `ba1f6876c`, the first pull request as #701 (`287514581`) and the second as #705 (`0ce953696`), so the install plan's RTK row, the handbook and the card text are on
main and the plan's `command-output` row installs and trusts the hook; the residuals and the review history below state what that does and does not cover.)

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
"**Codex** | `rtk init -g --codex` | PreToolUse hook (`updatedInput`) + AGENTS.md"); the owner's directive calls for that upstream install.

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
   hooks file). This grants trust to the hook that sees every Bash command; its authority is the command center's reading of the owner's approval above, scoped to the reviewed hash.
   The upstream command is not hook-only: it also creates `RTK.md` and appends a pointer line `@<Codex home>/RTK.md` to `AGENTS.md`
   (`rtk-init-codex-probe.json`; `--hook-only`, `--no-patch` and `--auto-patch` are refused with `--codex`). Codex expands no `@` reference,
   so the pointer is inert text, and NativeStack's `AGENTS.md` already carries it; but it is an edit of the instruction file, which the
   owner's authorization-settings reply did not name; the second pull request sought their confirmation, given in the addendum below.
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

- **Keep the hold-out** (the 0.50.0 state, instructions only). Rejected: the owner's directive calls for upstream installation, qualification passed,
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
- The owner withdrawing the command center's reading of their rollout approval for this grant: the row then stops after `rtk init -g --codex` and leaves the hash review to Codex's native `/hooks` interface.

2026-10-05 update: the [published RTK fold Harbor phase-2 record](2026-10-05-rtk-fold-harbor-phase2.md) resolves the study trigger above with `remedy_triggered=false`; the default stays within the studied grep scope, with broader remedy coverage unresolved.

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

The upstream command `rtk init -g --codex` appends an inert `@<Codex home>/RTK.md` pointer to the Codex `AGENTS.md` and creates `RTK.md`.
The [pinned installer](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/init/codex.rs) and the retained `rtk-init-codex-probe.json` establish those side effects; there is no hook-only mode with `--codex`.
Because the earlier authorization-settings reply did not name instruction-file edits, the command center put this to the owner and relayed their approval.
By its transcript, they approved the RTK pointer at 2026-10-05T00:49:16Z; their queued 00:50:08Z message set a standing rule to
always proceed with highest-quality SOTA-converged practice using upstream repositories for RTK-like work, including shipped installer effects.
The command center corrected its earlier about-00:55Z estimate; this writer heard neither message directly and relies on those relays.
The approval and standing rule rest on that reading, which the owner may withdraw; each installer effect still retains its measurement and rollback checks.

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
5. **What changes, for whom.** Execution rules are evaluated before the approval-policy fallback (`exec_policy.rs` L327-L420), whatever the approval policy: a
   `forbidden` match stays forbidden, an `allow` match is allowed, and under `approval_policy = "never"` a `prompt` match is rejected by policy and becomes
   `forbidden` (`prompt_is_rejected_by_policy`, L216-L236; the match at L394-L415). So approvals off do not switch rules off; a first draft of this record
   said that no rule is consulted on NativeStack2604, and the job-071 read (P3) corrected it. On a host with no applicable rule the class of a rewritten
   command does not change: an unmatched command's decision depends on the approval policy and the sandbox, not on its words, except for the forced-`rm`
   heuristic, which rtk leaves alone; under `untrusted` every unmatched command prompts anyway, and rtk notes that known-safe commands may gain prompts. On a
   host whose rules name commands rtk rewrites, the rule no longer matches the rewritten form, so a `forbidden` or `prompt` rule on `git push` is bypassed for
   `rtk git push`, with approvals on or off. What NativeStack2604's state means: its user layer has no `rules` directory (a read-only `ls` of
   `<codex home>/rules` on 2026-10-05: no such directory; NativeStack has none either), so no user-layer rule exists for the rewrite to bypass. That is a
   statement about the user layer; the tool does not see a project's `.codex/rules` or a managed layer.

**Decision.** Keep the upstream install, and gate the activation of the hook on the user layer's rule files with a review that parses nothing
(`tools/adoption/codex_hook_trust.py`, fourth version of 2026-10-05). The history is three analysing versions and three sets of bypasses. The first version
refused whenever a rules file existed (head 4739ea829); 705d and job-071 read it. The command center then asked for a refusal only where a rule could really be
bypassed, so that #713's `hcom-deny.rules` (rtk rewrites none of its commands) would not block the row. The second version (e6321c0b8) compared the decisions that
`codex execpolicy check` gives on the commands the rules name and on a sample of rtk-rewritten commands; 705e found that it cannot be completed: P1 an entry-level
`FileNotFoundError` failed open, P1 a `prefix_rule` nested in an argument of `host_executable` is accepted by the real codex-cli 0.159.3 evaluator and was never
counted, P1 a prefix that rtk leaves alone has extensions that it rewrites (`["git", "-C", "."]`: `rtk hook check` exits 1 for `git -C .` and rewrites
`git -C . push origin main`; broad `["uv"]` and `["npx"]` forbids passed). The third version (a9a07d815, c771da9eb) derived the command heads that rtk can rewrite
from its source and checked each rule's first token against them, reading the rules with Python's `ast`; 705f found five P1s and a P2 in it: a raw CR inside a
triple-quoted token, which Codex's Starlark lexer drops (the pattern is `git push`) and Python's reader turns into a newline; a rule on the whole shell argv
(`["bash", "-lc", "FOO=1 git push origin main"]`), which Codex evaluates when it cannot split an assignment-prefixed script, and rtk rewrites the script; the PHP
tool spellings that rtk normalizes (`phpunit.exe`); a user-global TOML filter whose pattern has a second branch (`^reviewalpha\b|^hcom\b`) that rtk rewrites after
`rtk trust`; rtk's Unicode word boundary (`g++` plus a combining mark); and P2 `DirEntry.is_file()` suppresses a missing-entry error that Codex's `file_type()`
propagates. Every analysing version modelled two things that must agree with the real ones, Codex's Starlark evaluator on one side and rtk's rewrite on the other,
and every read found a place where they differ; each repair widened the analysed surface (heads, parser, matcher). The fourth version is the design that 5f
recommended after 705f and the command center accepted: the tool no longer decides what a rule means.
  - **The rule.** For each regular file with the extension `.rules` in `<codex home>/rules`, read as bytes:
    (1) its sha256 is on the reviewed list, `tools/adoption/exec_rules_reviewed.json`, and the host conditions of the entry hold: it is accepted;
    (2) it holds nothing but allow rules in Codex's own format, byte for byte (lines `prefix_rule(pattern=["a", "b"], decision="allow")` whose tokens are
    printable ASCII without a quote or a backslash, as `codex-rs/execpolicy/src/amend.rs` writes `default.rules`; comment lines of printable ASCII without a
    backslash, which hcom's own `hcom.rules` begins with (`aannoo/hcom` 7151660a3, `src/hooks/codex.rs` `build_codex_rules`); empty lines; hcom's file as its installer builds it, from `SAFE_HCOM_COMMANDS` and `HCOM_TOOL_NAMES`, has no character outside the grammar): it is accepted,
    because an allow rule that a rewrite stops matching only loses its approval and restricts nothing, and a language this small reads the same in every
    parser (705g checked all 93 admitted token characters against Codex's Starlark); one that contains the letters `rtk` anywhere is refused, because the hook's
    rewrite inserts that word, so the rule matches the rewritten command and not the original and widens an approval (codex-cli 0.159.3 `execpolicy check`: under
    `["rtk"]` allow, `rtk git push origin main` is `allow` and `git push origin main` has no decision, `allow_rtk_check`; and 705g P1-1: Codex cannot split an
    assignment-prefixed script, evaluates it as one token of the shell argv, and the hook inserts rtk inside that token, so `["/bin/bash", "-lc", "FOO=1 rtk git
    push origin main"]` allows the rewritten script and not the original, `allow_rtk_script_check`; the whole-token version of the check missed it);
    (3) otherwise it is an exposure. `--apply` refuses with exit 2 before the app-server starts, so before any write, even for an already trusted hook;
    `--check` exits 6 for a trusted hook beside an exposure (5 stays for an untrusted one), and the post_install acceptance runs it, so a rule file added or
    edited after the grant is caught on the next acceptance run; `--allow-exec-rules` accepts the exposure, after the `rtk` form of each restricting rule is written
    beside the plain one and both are checked with `codex execpolicy check`. Any step that cannot be done (a listing or read error, a broken list, an rtk that does not
    answer) is an exposure as well. With no rule file nothing is read and rtk is not run.
  - **The reviewed list.** An entry is the review of one exact file for one rtk version: the sha256, the first tokens of its rules, the rtk version and commit it was
    reviewed for, and its evidence. Today it has one entry, #713's `config/hcom-deny.rules` at head 7fbe586f3 (a copy is kept as
    `fixtures/hcom-deny.rules`; #713's repair round 2 narrowed the comments and justification strings of the 5f295f254 file, and the 25 other lines, the patterns, decisions and
    match lists, are identical, so the first review of 2026-10-05 carries over; the entry follows the shipped bytes and a later edit of the file needs a new entry): every rule is a prefix rule on `hcom ...` or `uvx hcom ...`, neither word is a command rtk 0.51.0 can route, so no
    command that a rule matches is rewritten, and a command behind a wrapper (`time hcom ...`) is outside a prefix rule's reach with or without the rewrite. The review rests on `rtk-rewrite-heads.json` (the heads derived from
    rtk's 94 `RULES` patterns and 62 builtin TOML filters, the wrappers and the env prefix, with line provenance) and on `check_rtk_rewrite_heads.py`, whose section 6
    ran the entry's first tokens in 22 spellings and 8 shapes, alone and behind each wrapper (352 commands) against the real binary: none is rewritten. Both are review
    evidence, not a gate: the tool reads neither. The conditions of an entry are the ones the review was made under: `rtk --version` must report the entry's version,
    `rtk config` must show `transparent_prefixes = []` (a configured prefix makes rtk rewrite the command after it), `rtk trust --list` must print exactly
    `No trusted filters.` (rtk applies a project or global TOML filter only while it is trusted, and the store is global; measured with rtk 0.51.0: a trusted project
    filter makes the hook rewrite `hcom kill luna` from that project's directory, and `rtk trust --list` shows it from any directory), `RTK_TRUST_PROJECT_FILTERS`
    must be unset in the tool's environment (with a CI variable rtk trusts every project filters file without a store entry, which the list does not show: measured
    too), and the user-global TOML filters file beside rtk's config must hold nothing but comments and `schema_version` (a filter's `match_command` can make rtk
    rewrite any command). One changed byte of the file, another rtk, a prefix, a trusted filter or the override variable ends the review. **A pin move of rtk re-reviews the list**: `tests/test_codex_hook_trust.py` compares each entry with the rtk entry of
    `adoption/pins-linux-x86_64.json` (version and commit), so the PR that moves the pin carries the new review (re-derive the heads with
    `derive_rtk_rewrite_heads.py`, run `check_rtk_rewrite_heads.py` and the scratch run, update the entry), and the RTK row of `docs/token-efficiency-stack.json` names
    the step in the currency process. A file that ships with an install plan row must be on the list or allow-only, which a test checks.
  - **The listing, fail closed.** The rules directory is listed as Codex's `collect_policy_files` does (`exec_policy.rs` L1121-L1170): only opening it may report a
    missing directory, every other error (the open, the iteration, an entry) is a failure, and the type of every entry is asked before its extension, from its own
    `lstat` (`os.scandir` entry `stat(follow_symlinks=False)`, which raises for an entry that vanished), so a symlink, a directory or a named pipe is not loaded and
    never opened. The cost is false refusals: any hand-written restricting rule that is not on the list, and a `default.rules` that Codex wrote with an escape (an
    approved command with a quote or a backslash), is an exposure until it is reviewed into the list or accepted with `--allow-exec-rules`.

Evidence (`local_integration` unless noted): `plan-row-scratch-run.json`, 79 steps with the real rtk 0.51.0 and codex-cli 0.159.3 in scratch homes, the plan's own
command strings: #713's `hcom-deny.rules` by its exact bytes lets the trust proceed (and a `git push` forbid rule added after the grant makes `--check` exit 6 and the
trust refuse); the same bytes plus one comment line, a configured transparent prefix, a user TOML filter beside the reviewed file, a trusted project filter (under which the real rtk
rewrites `hcom kill luna` from the project's directory) and `RTK_TRUST_PROJECT_FILTERS` with a CI variable (the same rewrite, with no store entry) are each refused; Codex's and
hcom's allow-only files let the trust proceed, and an allow rule that holds `rtk` (as a token, or inside a shell-script token) is refused; a `git push` forbid rule is refused before anything is written (accepted with `--allow-exec-rules`, after which
`--check` exits 6), and so is the same rule with its `rtk git push` twin; the counterexamples of 705e (`git -C .`, broad `uv` and `npx` rules, the nested
`host_executable` file, under which the real evaluator forbids `git push origin main`) and of 705f (raw CR, `bash -lc` script, `phpunit.exe`, `g++` plus a combining
mark) and an unreadable rules directory are refused; each `execpolicy_check` answer needs exit 0 and a valid response, and `rtk_hook_check` records which of the
commands the real hook rewrites (`git -C . push origin main`, `uv run harmless.py`, `npx prisma migrate deploy`, `phpunit.exe tests/` and the combining-mark `g++`
are rewritten; `git -C .`, `uv`, `npx`, `uvx hcom kill luna` and `hcom kill luna` are not). `rtk-rewrite-heads-check.json`: 94 of 94 RULES patterns have a command
that the binary rewrites, 13,041 scanned commands (1,449 names, 9 shapes) gave 623 rewrites and none outside the heads, 67 wrapper prefixes in front of `git status`
gave 24 rewrites, all led by a head, 8,884 spellings of the 101 literal heads gave 480 rewrites and none outside the heads, and the 352 commands of the reviewed
entry gave none (the derivation's gaps were 101, then 63, then 0, and 28, then 40, then 0 in the spelling scan: the `r#"..."#` sbt rule, the TOML filters as a
second rewrite source, `^gcc\b` accepting `gcc-13`, a trailing slash, PHP `.exe`/`.bat` words, backslash readings). 81 unit tests (`synthetic`: `FakeRtk` stands in for
`rtk --version` and `rtk config`; the evidence tests read the retained records) were written after the code and checked by mutation: 63 mutants each fail at
least one test (`rule_review_mutation_check.py`, `rule-review-mutation-check.txt`; the ASCII decode of the grammar is the one equivalent mutant and is not listed).
The operating rule for rule authors stays: write the `rtk` form beside the plain one and check both with `codex execpolicy check`, then accept with `--allow-exec-rules`.

Limits and residuals: rules in a project's `.codex/rules` or a managed layer are not visible to the tool; the override variable is checked in the tool's own
environment, not in the environment Codex runs the hook in, and a filter trusted after the review shows only at the next `--check` (705g P1-2: a point-in-time
check cannot establish what a global hook does in every working directory; the review classifies the filter state it can see, so a trusted filter or the override
needs `--allow-exec-rules`, and the exclusions of alternative (j) are the enforced hardening); the reviewed list covers rtk's default hook configuration of the one version it names; the review covers the user layer's rule files as bytes and does not
say whether a restricting rule is good; no live Codex session was run with a forbidding rule and the hook active (untested boundary: the session behaviour is
derived from the dispatch order above and the evaluator that `codex execpolicy check` runs); `--allow-exec-rules` is an explicit acceptance of an exposure; there is no atomic snapshot across listing, loading and the grant of the trust, and no enforcement after a later
change of the rules, the filters, the HOME or XDG paths or the hook's environment (705h's boundary: another `--check` is needed after such a change); the probes ran codex-cli
0.159.3 and rtk 0.51.0, and rust-v0.160.0 was read from source, with no fresh model session.
What would overturn the design: a Codex that matches execution rules before the PreToolUse rewrite or against both forms, an rtk that reads Codex's rules or has a
Codex-aware rewrite exclusion, or a maintained upstream gate that supplies the review (the live landscape is re-read at each pin move).

**Review rounds (2026-10-05).** The first version of the guard (4739ea829) was read twice. 705d (Sol, through 5f): P1 `rule_files` failed open when the listing
raised (`Path.glob` swallows the error); P2 the refusal came after the app-server started; P2 the scratch run accepted a failed evaluator as "no decision".
Job-071 (through the command center): P2 the same listing hole; P2 rules were reported only for a hook still to be trusted; P3 the claim that approvals-off
hosts consult no rules. The second version (e6321c0b8) fixed those and was read by 705e: the three P1s above. The third version (c771da9eb) fixed them with the head
set and the `ast` reader and was read by 705f: five P1s and a P2 (above). The fourth version replaces the analysis with the hash list on 5f's recommendation and
keeps the mechanical repairs (the listing, fail closed). 705g (Sol, through 5f, at 3a2bb97ba) found two P1s and no P2 in it: an allow rule for a shell script that holds
`rtk` inside the script token (the check had refused only a whole token `rtk`), and project filters, which rtk loads from the hook's working directory before the
global and built-in ones and which `rtk trust --yes` or `RTK_TRUST_PROJECT_FILTERS=1` with a CI variable activate, so that the reviewed hash still passed while the real
hook rewrote `hcom kill luna` out of the forbid rule. The repair round refuses `rtk` anywhere in an allow rule and adds the trust list and the override variable to the
entry's host conditions (the reviewer's second option: classify the project-filter exposure so that it needs `--allow-exec-rules`). Bounded review loop: one more read
of this version, and the residuals above recorded. 705h (Sol, through 5f, at 14a8b119f) accepted it: no P1 and no P2, both 705g P1s verified fixed against the real binaries (the
whole-token mutant dies with 36 test failures; both project-filter activation routes give `--apply` exit 2 and `--check` exit 6, with the default and the XDG layouts; `rtk trust
--list` detects the filter from any directory), no additional bypass in the pinned rewrite paths and inputs, and two boundaries not verified (the residuals above). The branch was then refreshed by hand onto main `cb339488e` (the head that landed is `118f579ff`): 28 of its 31 owned
files are patch-id-equal (`git diff -U0`) to the accepted head, the other three are the regenerated new-WSL handbook outputs and their receipt, and 5f re-queued it after its own
micro-read of that regeneration. The exclusions default that job-071 recommended is alternative (a).

**Alternatives.** (a) *Limit the hook to a read-only rewrite set with `exclude_commands`* (job-071 recommended exclusions for state-changing families as a
default beside the guard): rtk's option is exclusion-only (`src/core/config.rs` L119-L123; `src/discover/registry.rs` L1548-L1582: a pattern starting with `^` is
a regex without look-around, any other is a literal prefix, and a trivial pattern is ignored), so an allow-list cannot be written, and a deny-list of every
state-changing prefix would track upstream's registry, change the shared config that the Claude hook and the recipe's five-entry table also read, and cost
compression only on short mutating-command output. That read's own probe shows the limit: `exclude_commands = ["git push"]` excludes `git push` but still rewrites
`git -C /tmp push`, so exclusions reduce the risk without preserving a rule or constraining a command the model prefixes with `rtk` itself; not done here, and
the first thing to add if a bypass is ever observed. (b) *Prove rtk never rewrites mutating commands*: false (item 4). (c) *Hold the Codex hook out again*:
against the owner's directive of 2026-10-04 unless they withdraw its scoped grant. (d) *Ship `rtk ...` rules with the plan*: under `approval_policy = "never"` a `prompt` rule is rejected by policy and
becomes `forbidden` (`exec_policy.rs` L216-L236 and the match at L407-L415), which would block the authorization-settings hosts, and a twin cannot be shown to
cover every rewrite. (e) *Refuse whenever a rules file exists* (the first version): it blocks the row for nothing once #713 installs `hcom-deny.rules`; the hash list
refuses only what is not reviewed or allow-only. (f) *Compare decisions on probed and sampled commands* (the second version): abandoned, the 705e counterexamples.
(g) *A wrapper hook that evaluates the rules before delegating to `rtk hook codex`*: it would be complete for the user layer, but it replaces upstream's hook command
with a self-built component, against the directive to install with upstream commands; not done. (h) *Derive rtk's heads and read the rules with a parser* (the third
version): abandoned, the 705f counterexamples; the derivation and the real-binary check remain as the review evidence for a list entry. (i) *Accept any rule file
whose first tokens are not heads, by a parser written for the purpose*: the same analysis with the same failure surface; the list reviews exact bytes instead. (j) *Enforce `exclude_commands` entries for `hcom` and `uvx hcom` as the reviewed entry's host condition* (705g's first option for P1-2): rtk applies exclusions before the TOML-filter rewrite (`src/discover/registry.rs` L1743-L1763), and measured with the real binary in a scratch HOME (`project_filter_check`), `['^hcom(\s|$)', '^uvx\s+hcom(\s|$)']` keeps `hcom kill luna` and `uvx hcom kill luna` unrewritten while a trusted project filter that matches both is active, and under the CI override, and leaves `git status` rewritten. It is the better hardening and is not enforced by the tool: the entries would join the recipe's shared five-entry table that Claude's hook reads too (its text, fixture and tests count five, and other lanes own them), and an exclusion matches rtk's raw command text, so it cannot cover every shell spelling that Codex reads as `hcom` (quotes, escapes) against an unanchored trusted filter, where the observed-state conditions leave rtk with no filter at all. A host that opens untrusted repositories with Codex can add the two entries to rtk's config now; whether the plan's default table should carry them is a decision for the recipe's owners.
