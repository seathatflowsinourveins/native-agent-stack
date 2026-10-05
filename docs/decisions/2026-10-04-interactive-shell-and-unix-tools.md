# Decision: bash with no framework on the 26.04 hosts, a small opt-in interactive layer below Ubuntu's guard, and no new agent tools (2026-10-04)

**Status:** proposed. Cross-family consensus was reached on 2026-10-04. The record becomes accepted when the command center ACKs this PR and it lands.

**Decided by:** research unit B of the decide-quality round, which is session 5f's unit for the interactive shell and Unix tooling. It started from the GPT-6.1 Sol discovery lanes B1-B3 and applied the frozen round-2 criteria (the coordinator's quality criteria of 2026-10-04). The record then passed two more stages:
- cross-family reader: GPT-6.1 Sol;
- finalize stage: Claude Opus 5.5 (2026-10-04, 23:30-23:40Z).

The integration base is main `3b8f9c8a`. The repository files cited here are unchanged since `38ac9aca`, which remains history only.

**Adoption status:** This PR records the decision and catalog selections only; it installs nothing. The interactive block is opt-in and person-run. Implementation belongs to the subsequent unit B PRs; every Ubuntu 26.04 runtime guarantee remains pending PR-3. Dotfile names below denote the person's shell startup files without publishing a home path.

**Landing dependency:** Hold this PR's merge until unit A's planned record, `docs/decisions/2026-10-04-credential-guard-launcher-union.md` (PR-1), is on main. Once it exists, add that path to the isolation row's `source_paths` before final file registration. Unit A's PR-2 owns `CLAUDE_CODE_SHELL=/bin/bash` and agent-shell policy.

**Scope:**
- **In scope:** the login shell, framework, prompt, history, directory jump and environment loader, and the modern-Unix tool set, both agent-facing and human-facing.
- **Agent isolation:** how agent shells stay isolated from interactive rc content.
- **Hosts:** NativeStack2604 and StackMeasure2604 (Ubuntu 26.04.1). NativeStack (24.04) is unchanged.
- **Out of scope:** agent-harness frameworks belong to the command center.

**Requirement basis:** criteria A(3). A coordinator record of 2026-10-04 quoting the user carries it:
- :8 quotes the user's 2026-10-04 request verbatim, which names "termnial profiles";
- :10 lists ohmyzsh/ohmyzsh as an example to research beyond;
- :12 assigns the class to session 5f.

This is private coordination state, not a repository record. No agent ever writes the interactive block; only the person's own run of the named-only slot does. Without that run, every other slot stands unchanged.

## Problem

Claude Code's Bash tool replays the user's shell startup state (tools-reference.md L150). If a framework's aliases reach agent commands, the PreToolUse guard sees only the alias text. That decides whether a framework is safe in the login shell. Each of the other slots needs one default, and "none" is allowed. Tools this stack already runs are configured in preference to new installs, and upstream defaults win over local adaptation.

## Alternatives

| Slot | Chosen | Not chosen (reason) |
| :- | :- | :- |
| Login shell | bash 5.3 (image default) | zsh: not in the image, and Claude would source `.zshrc`. fish, nushell: Claude does not support them, and Codex does not recognize them. |
| Framework | none | Oh My Zsh, Oh My Bash: no release or tag. Bash-it: release 351 d. ble.sh: release 1280 d. Prezto, Sheldon: stale. Zinit, Antidote, Zim: zsh-only. |
| Prompt | skel PS1 plus git's `__git_ps1` (PS1 mode) | git-prompt's PROMPT_COMMAND mode: documented as slightly faster (git-prompt.sh:18-24 at v2.53.0) and held as the first performance step. Starship and Oh My Posh pass the gates but are not clearly stronger than git's helper (D2). Powerlevel10k fails the gate. |
| History | native bash history, searched with fzf's Ctrl-R | Atuin: needs bash-preexec and local overrides of its AI, sync and update defaults. McFly, hstr: fail the gate. |
| Directory jump | zoxide 0.10.0 | z.lua needs Lua. autojump, rupa/z, fasd: fail the gate. |
| Env loader | mise (existing owner, pinned at v2026.10.0); `mise exec --` for agent commands | direnv: fails the gate, and mise marks its direnv integration deprecated. A Claude CwdChanged hook: only after a recorded need for persistent session state. |
| Agent tools | no new install | fd (no gap), sd and hyperfine (fail the gate), mikefarah/yq (no recorded job), bat, eza, lsd (decorated output) |
| Human tools | fzf and zoxide, opt-in, NativeStack2604 only | eza, fd, dust, btop, tealdeer, lazygit (existing owners cover them). bat, duf (fail the gate). delta (overlaps difftastic). tmux, zellij (not adopted on 2026-09-28). |
| Isolation | Ubuntu skel guard plus one managed block; `CLAUDE_CODE_SHELL=/bin/bash` from unit A | a CLAUDE_CODE_SHELL_PREFIX wrapper, a BASH_ENV sanitizer, `.bash_aliases` (sourced before bash-completion) |

## Decision

1. **Login shell: bash.** It is the Ubuntu 26.04 default and the passwd shell the recipe creates. No chsh.
2. **Framework: none.**
3. **Prompt.** Keep Ubuntu's skel PS1 and insert `$(__git_ps1 " (%s)")` before its trailing `\$ `, with git's upstream defaults. The block sources `/usr/lib/git-core/git-sh-prompt` only if bash-completion has not already defined `__git_ps1`.
4. **History.** Native bash history with Ubuntu's defaults, searched through fzf's Ctrl-R (`eval "$(fzf --bash)"`).
5. **Directory jump.** zoxide 0.10.0 (`z` and `zi`; `cd` is unchanged), with `eval "$(zoxide init bash)"` as the last line of the block. Integrity is checked against GitHub's published digest for the fetched release asset, because zoxide publishes no checksum file.
6. **Env loader: mise, pinned at v2026.10.0.**
   - **Pin.** v2026.10.0 is the version main's install plan installs (`install.sh:541-544`, `install-plan.json:2535`). The files this record cites are byte-identical at v2026.10.2. Moving the pin is a separate pin-move PR.
   - **Shims.** Shims stay on PATH through the existing `.profile` managed block, for login shells.
   - **Activation.** `eval "$(mise activate bash)"` goes in the interactive block.
   - **Per-directory variables.** They live in `mise.toml` `[env]`.
   - **Agent commands.** An agent command that needs project `[env]` runs as `mise exec -- <cmd>`. That loads tools and environment explicitly, the same way for both clients (shims.md:44-45; direnv.md:43-46).
   - **CwdChanged.** A Claude CwdChanged hook writing to `CLAUDE_ENV_FILE` follows only a recorded need for persistent session state. It must also set the session's initial project environment.
7. **Agent-facing tools: nothing new.**
   - **Claude Code.** Its embedded `bfs` (find) and `ugrep` (grep) shell functions and its bundled `rg` are the native search route.
   - **Codex.** It uses `rg` and `rg --files`, as its own base instructions say. These come from apt ripgrep, which the plan prescribes for sandbox-runtime (`install.sh:704`); PR-3 records whether it is installed.
   - **jq.** It comes from F4.
   - **RTK hook rewrites.** The hook rewrites rg, grep, find, ls, cat, git, diff, du, df and ps (rules.rs:128-179). A rewritten search runs as an external process and bypasses Claude's embedded functions.
   - **RTK exclusions.** The stack's `[hooks] exclude_commands` (`jq`, `diff`, `git show REV:path`) stops the hook rewriting those commands. A command written with an explicit `rtk` prefix still needs the documented exact-output exceptions.
   - **RTK coverage.** "No fd, bat or eza rule" holds for the static rules read. RTK's TOML filter registry (registry.rs:1743-1762) is a separate inventory.
8. **Human-facing tools.** fzf 0.74.4 and zoxide 0.10.0 are global mise pins inside a named-only `interactive-shell` slot of the install plan.
   - **Selection.** A default run skips the slot (`install.sh:37-38`, `:727-728`), and StackMeasure2604 never names it.
   - **Checks before writing.** The writer first checks that bash is 4 or newer, `fzf --version` is 0.74.4, `zoxide --version` is 0.10.0, `git-sh-prompt` is present and mise is on PATH. It refuses if any check fails.
   - **Other jobs.** Every other job keeps its existing owner.
9. **Isolation.**
   - **Boundary.** Ubuntu's skel guard (`case $- in *i*) ;; *) return;; esac`) isolates the managed interactive content on the qualified non-interactive startup paths:
     - Claude's snapshot capture, which runs as a non-interactive login shell (observed on 24.04);
     - Codex's default `bash -lc`, where `.profile` sources `.bashrc` and the guard returns before the block.
   - **Not an authorization control.** The guard does not authorize agent commands; unit A's guard and threat model cover that.
   - **The block.** All interactive content lives in one managed block at the end of `.bashrc`, below the guard and bash-completion. Only the person's run of the named slot writes it, through `tools/adoption/managed_block.py`, which refuses when no guard precedes it.
   - **Login files.** `.profile` stays environment-only, and `BASH_ENV` stays unset.
   - **Claude.** `CLAUDE_CODE_SHELL=/bin/bash` comes from unit A's PR-2, and there is no `CLAUDE_CODE_SHELL_PREFIX`.
   - **Codex.** It keeps `shell_snapshot = false` and `inherit = "none"`. `inherit = "none"` builds an empty baseline, then adds the rendered set table, then Codex's own variables such as `CODEX_THREAD_ID`. Login startup files still run under the default login shell. If unit A adopts `allow_login_shell = false`, they stop, and the agent PATH comes only from the rendered set table.
   - **StackMeasure2604.** It gets no block.
   - **Status.** Behaviour on 26.04 is pending PR-3.

On Oh My Zsh, since the user named it:

- **Maintenance gate.** It fails the frozen gate because it publishes no release and no tag. That is an artifact of the criteria for a rolling-release project: it had 152 commits from 24 authors in 90 days.
- **Release discipline.** Its updates track `master`, and the default update mode is `prompt` (`tools/check_for_upgrade.sh:14-19`).
- **Agent exposure.** With zsh as `$SHELL`, Claude sources `.zshrc`, and the Oh My Zsh template has no interactive guard. Its aliases would therefore reach agent commands. They include the git plugin's 203 aliases (for example `grhh='git reset --hard'`), the global `...` aliases and `_='sudo '`.
- **Safe opt-in.** zsh as the login shell plus `CLAUDE_CODE_SHELL=/bin/bash`, gated by the session-attributed snapshot check below.

## Evidence

**Agent shells read startup files**

- **Claude Code.**
  - It sources `.zshrc`, `.bashrc` or `.profile` at session start and replays the aliases, functions and options it captured (tools-reference.md L150).
  - It skips `-l` when a snapshot exists (CHANGELOG 2.1.51, L6334).
  - Native Linux builds run `find` and `grep` as embedded `bfs` and `ugrep` (2.1.117, L5026; tools-reference L292).
  - PreToolUse fires before the tool call is processed (hooks.md L1578-1580).
- **Observed on NativeStack with Claude Code 2.1.289 (unit B).**
  - All 8 snapshots hold 0 alias lines, although `.bashrc` defines 8 aliases below Ubuntu's guard.
  - The capture runs as a login shell (`shopt -s login_shell`).
  - The snapshot unaliases and shadows `find`, `grep` and `pkill`.
- **Observed now (finalize stage).** A Bash tool process names the snapshot it sourced in its own argv: `/proc/$$/cmdline` contains `shell-snapshots/snapshot-bash-<ms>-<suffix>.sh`. The snapshot directory is shared (8 files). This behaviour is undocumented.
- **Codex** (pin rust-v0.160.0, installed 0.159.3).
  - It takes its shell from passwd (`shell_detect.rs:62-100, 346-369`).
  - It runs login shells by default: `allow_login_shell` defaults to true (`config/mod.rs:3833`; `unified_exec.rs:105-113`).
  - Its snapshot would source `.bashrc` (`startup.rs:9-27`), but this stack turns the snapshot off (`codex.config.template.toml:241-246`).
  - `inherit = "none"` starts from an empty environment before the set table (`shell_environment.rs:99-101`; `codex.config.additions.toml:34-50`).
- **Ubuntu `.profile`.** It sources `.bashrc` under bash (`/etc/skel/.profile:12-15` on 24.04, observed now; the 26.04 skel profile was not re-read).
- **GNU bash 5.3.** A non-interactive shell sources `$BASH_ENV`, and aliases do not expand without `expand_aliases`.

**Image, archive and host state**

- **26.04.1 WSL image manifest.** It lists bash 5.3-2ubuntu1, bash-completion 1:2.16.0-8build1, git 1:2.53.0-1ubuntu1, coreutils-from-uutils and rust-coreutils 0.8.0-0ubuntu3. It lists no zsh, fzf, ripgrep or jq.
- **Coreutils upgrade.** Coordination records of 2026-10-04 and unit A PR-0's read-only host baseline artifacts, captured 2026-10-05 01:02-01:03Z, record rust-coreutils 0.10.0-1ubuntu2~26.04.1 and sudo-rs on both 2604 hosts:
  - NativeStack2604: held in private coordination state, not a repository record; unit A's PR-0 is to commit a sanitized host receipt (the 2026-10-04 upgrade record covers 08:04:47Z-08:05:03Z);
  - StackMeasure2604: held in private coordination state, not a repository record; unit A's PR-0 is to commit a sanitized host receipt.

  The B2 lead's 0.10.0 therefore matches the recorded host state, not the image. These artifacts and receipts are pending in unit A's PR-0; the records become repository evidence when that PR commits them. Every Ubuntu 26.04 runtime guarantee remains pending PR-3.
- **Ubuntu skel `.bashrc`.** It holds the guard (L5-9), the history defaults (L13-20), the `.bash_aliases` hook (L100-105) and bash-completion (L112-115).
- **git.** It ships `git-sh-prompt` and its bash-completion loader. The PS1 mode is at git-prompt.sh:13-17 and the PROMPT_COMMAND mode at :18-24, at v2.53.0 (the 26.04 image's git) and identically at v2.43.0 (24.04).

**Maintenance gate** (GraphQL, 2026-10-04T22:07Z; days since the last commit / days since the last release or tag)

- **Fail:** Oh My Zsh 5/none, Oh My Bash 32/none, Prezto 163/none, Bash-it 21/351, ble.sh 26/1280, Sheldon 95/439, Powerlevel10k 28/982, direnv 187/441, bat 3/306, duf 369/391, sd 221/221, hyperfine 2/320, gojq 7/186, McFly 33/284, hstr 18/240, peco 15/222.
- **Pass:** zoxide 1/92, fzf 20/22, Starship 1/98, Atuin 1/12, mise 0/0, ripgrep 61/81, z.lua 56/55, skim 0/0.

**Tools, integrity and RTK**

- **zoxide v0.10.0** (latest, published 2026-07-04T12:41:16Z).
  - All 17 assets carry a GitHub-published `sha256` digest (GraphQL `ReleaseAsset.digest`, read 2026-10-04T23:35Z), and none of the assets is a checksum file.
  - `zoxide-0.10.0-x86_64-unknown-linux-musl.tar.gz` is `sha256:2d93385b99f3e82cf2701609a1bffcad863fbeb75aa3fe7eb6be4d29be68b1ae`.
  - GitHub computes the digest; the publisher does not sign it.
- **fzf.**
  - It provides `--bash` since 0.48.0 and documents installation through mise (README:127-132).
  - It ships a checksums file per release.
  - Its bash integration binds Ctrl-R with `bind -m emacs-standard -x` to `__fzf_history__` (shell/key-bindings.bash:181; bash 4 or newer, from :151), and `bind -X` lists such bindings (bash `help bind`).
- **mise.** It documents shims in the login profile and activation in `.bashrc` (shims.md:126-152), and `mise exec --` for scripts (:44-45). It marks its direnv integration deprecated (direnv.md:5, 12).
- **zoxide setup.** zoxide asks for its init at the end of `.bashrc` (README:218-222) and needs fzf 0.51 or newer for `zi` (README:340-346).
- **Atuin.** On bash it needs bash-preexec (README:108-110). Its AI feature is on by default (`init.rs:86`), as are auto_sync and update_check (`config.toml:27, 30`).
- **RTK v0.51.0.**
  - It rewrites rg, grep, find, ls and cat (`rules.rs:128-179`).
  - Its hook would rewrite a standalone `jq` through the TOML registry, capped at 40 lines (`registry.rs:1743-1762`, `jq.toml`).
  - This stack's bootstrap requires `jq` in `exclude_commands` (`bootstrap-linux.sh:1051, 1055`).
- **GNU grep 3.11** (observed now). `grep -c` with no match prints `0` and exits 1; exit 2 means an error (`grep --help`).

## What would overturn it

- **Login shell.** Both of these:
  - a user-named need bash cannot meet;
  - a NativeStack2604 run with zsh as the passwd shell and `CLAUDE_CODE_SHELL=/bin/bash` that shows all of: 0 alias lines in that session's own snapshot (attributed as in PR-3), Codex `type gst` not found, and `adoption_status.py --login-shell --launcher-resolution` passing.
- **Framework.** A gate-passing framework that adds 0 aliases or functions to the Claude snapshot and to Codex commands, for a job no standalone tool covers.
- **Prompt.** Time the complete prompt over 30 warm runs in the largest worktree, with mise's and zoxide's hooks active.
  - If the PS1 mode's median exceeds 50 ms, first move to git-prompt's PROMPT_COMMAND mode, composed with the other hooks (zoxide last).
  - Move to Starship v1.26.0 only if that mode's median also exceeds 50 ms and `starship prompt` runs in under half of it.
  - A user-named prompt field that git-prompt lacks also moves the prompt to Starship.
- **History.** A recorded loss of history across concurrent shells, or a user-named need for per-command context, moves it to Atuin v18.23.0 with `--disable-up-arrow`, `--disable-ai`, `auto_sync=false`, `update_check=false` and bash-preexec 0.7.0.
- **Directory jump.**
  - zoxide's hook adds more than 10 ms to the median prompt, or zoxide leaves a gate: move to z.lua, or to none.
  - GitHub stops publishing an asset digest and no checksum file appears: the profile row records the computed hash as unverified until the next release.
- **Env loader.**
  - A project needs `.envrc` logic that mise cannot express, and direnv is back inside the gates: adopt direnv.
  - `mise exec --` cannot serve a recorded agent workflow that needs persistent per-directory state: add a CwdChanged hook, with initial-environment handling.
  - The pin moves only through a pin-move PR.
- **Agent tools.**
  - An agent task record shows a failure caused by a missing gate-passing tool: add the tool.
  - RTK's filters misparse uutils 0.10.0 output compared with `coreutils-from-gnu` on a 26.04 host, using unit A PR-0's versions: switch the coreutils provider.
- **Isolation.**
  - A fresh, session-attributed Claude snapshot shows `^alias`, `__zoxide`, `_mise_hook`, `__fzf_` or `__git_ps1`, or a Codex command finds `z`: add an early return on `CLAUDECODE` or `CODEX_THREAD_ID`.
  - Claude Code or Codex documents a native switch that turns off rc capture: use it.

## Limitations

- **Host observation.** Neither this unit nor the finalize stage observed a 26.04 host directly; the coreutils versions come from coordination records. The snapshot evidence is NativeStack 24.04 with Claude Code 2.1.289. No Codex path was executed.
- **Published evaluations.** No candidate in these slots has one (criteria item 5). Authors-in-90-days counts are approximate.
- **RTK over uutils.** RTK filters over uutils 0.10.0 output have not been tested.
- **zoxide integrity.** It rests on GitHub's platform digest plus HTTPS, not on a publisher signature.
- **Snapshot attribution.** The method relies on observed, undocumented client behaviour. The fallback is a before/after listing with no concurrent session.
- **fzf bindings.** fzf binds Ctrl-T and Alt-C as well as Ctrl-R. `FZF_CTRL_T_COMMAND=` and `FZF_ALT_C_COMMAND=` can drop them (README:232-236).
- **Requirement basis.** It is a coordinator record that quotes the user, held in private coordination state.

## Changes from the cross-family reading

**Applied** (each verified at the source named in the rulings):
- the PROMPT_COMMAND arm;
- zoxide's GitHub digest;
- `mise exec --` as the first remedy;
- named-only selection;
- the uutils correction, with host values from coordination records;
- per-session snapshot attribution;
- `grep -c` exit handling;
- full-evidence receipts;
- the fzf Readline check;
- the RTK, ripgrep and isolation wording;
- base `3b8f9c8a`;
- mise and git citations at the installed pins (v2026.10.0 and v2.53.0).

**Kept:** every slot choice, which the reader agreed with; the 50 ms and 10 ms thresholds; and the person-run, requirement-gated block.

**Finalize-stage alignment:** the isolation slot now takes `CLAUDE_CODE_SHELL=/bin/bash` from unit A instead of "no pin":
- unit A owns agent-shell policy;
- the setting is used as documented (env-vars.md L370);
- this record's own zsh opt-in already needs it.

## SOTA sources

- Claude Code docs, read 2026-10-04:
  - https://code.claude.com/docs/en/tools-reference.md L150, L292
  - https://code.claude.com/docs/en/env-vars.md L190, L370-371, L422
  - https://code.claude.com/docs/en/hooks.md L60, L202, L470, L1578-1580, L2813-2817
- anthropics/claude-code@v2.1.289: CHANGELOG.md:2367, 4309, 5026, 6334.
- openai/codex, stack pin `rust-v0.160.0` (`manifests/stack.json:296-298`):
  - codex-rs/shell-command/src/shell_detect.rs:39-45, 62-100, 346-369
  - codex-rs/shell-command/src/startup.rs:9-27
  - codex-rs/features/src/lib.rs:1015-1018, 1027-1030
  - codex-rs/config/src/config_toml.rs:216-219
  - codex-rs/core/src/config/mod.rs:3833
  - codex-rs/core/src/tools/handlers/unified_exec.rs:105-113
  - codex-rs/core/src/shell.rs:22-30
  - codex-rs/protocol/src/shell_environment.rs:99-101, 152
  - codex-rs/protocol/src/prompts/base_instructions/default.md:264
- openai/codex, installed `rust-v0.159.3`: codex-rs/config/src/config_toml.rs:215-218.
- Ubuntu:
  - git.launchpad.net/ubuntu/+source/bash (applied/ubuntu/resolute) debian/skel.bashrc:5-9, 13-20, 100-105, 112-115
  - https://releases.ubuntu.com/resolute/ubuntu-26.04.1-wsl-amd64.manifest
  - https://packages.ubuntu.com/resolute/{zsh,fzf,zoxide,starship,atuin,rust-coreutils,coreutils-from-gnu,yq}
- GNU Bash Reference Manual, Edition 5.3 (18 May 2025): 'Invoked non-interactively' and 'Aliases'.
- ohmyzsh/ohmyzsh@4d4cfc287e9d: templates/zshrc.zsh-template:5-78; tools/check_for_upgrade.sh:14-19; plugins/git/git.plugin.zsh:378; lib/directories.zsh:8-11, 24-25; lib/misc.zsh:31.
- git/git@v2.53.0: contrib/completion/git-prompt.sh:13-24, with identical lines at v2.43.0. The t/t9903-bash-prompt.sh declarations were inspected at v2.51.0 by the reader and not executed.
- ajeetdsouza/zoxide@v0.10.0:
  - README.md:218-222, 340-346, 373-375, 458-460
  - GitHub GraphQL `ReleaseAsset.digest` for release v0.10.0, read 2026-10-04T23:35Z (field documented at https://docs.github.com/en/rest/releases/assets)
- junegunn/fzf@v0.74.4: README.md:127-132, 202, 232-236; shell/key-bindings.bash:151, 171, 181; CHANGELOG.md:1525-1531.
- atuinsh/atuin@v18.23.0: README.md:108-110; crates/atuin/src/command/client/init.rs:86; crates/atuin-client/config.toml:27, 30, 37.
- jdx/mise@v2026.10.0, byte-identical at v2026.10.2: docs/dev-tools/shims.md:44-45, 126-152; docs/direnv.md:5, 12, 43-46; registry/zoxide.toml; registry/fzf.toml.
- rtk-ai/rtk@v0.51.0: src/discover/rules.rs:128-179; src/discover/registry.rs:1743-1762, 3317-3322; src/filters/jq.toml; README.md:482-484.
- anthropics/sandbox-runtime@6fa731368807: README.md:553-554.
- This repository at `3b8f9c8a`:
  - adoption/templates/codex.config.template.toml:241-246, 274-278
  - adoption/new-wsl/templates/codex.config.additions.toml:34-50
  - adoption/templates/claude.settings.template.json:89-91
  - adoption/bootstrap-linux.sh:1051, 1055
  - adoption/platforms/linux-wsl2-new-distro.md:776, 930-945
  - examples/claude-native/windows-terminal.fragment.example.json:5, 16, 38
  - evidence/artifacts/new-wsl-install-plan-20261002/install.sh:37-38, 541-544, 704, 727-728, and mise.toml
  - tools/adoption/managed_block.py:21-25, 249-266
  - docs/acceptance-evidence-policy.md:42-53
  - docs/decisions/2026-09-28-terminal-experience.md:135
- Coordination records, cited as leads only:
  - A coordinator record of 2026-10-04 quoting the user (requirement basis, lines 8, 10, 12).
  - Coordination records of 2026-10-04 and unit A PR-0's pending read-only host baseline artifacts, captured 2026-10-05 01:02-01:03Z (NativeStack2604 coreutils and sudo-rs); held in private coordination state, not a repository record; unit A's PR-0 is to commit a sanitized host receipt.
  - Coordination records of 2026-10-04 and unit A PR-0's pending read-only host baseline artifacts, captured 2026-10-05 01:02-01:03Z (StackMeasure2604 coreutils and sudo-rs); held in private coordination state, not a repository record; unit A's PR-0 is to commit a sanitized host receipt.
