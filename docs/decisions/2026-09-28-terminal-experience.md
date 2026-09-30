# Decision: Windows Terminal tab titles, needed-only alerts and colour depth for the native clients (2026-09-28)

**Decided by:** the user's direction of 2026-09-28 in this session, verbatim: "make sure each one shown their title,each tab
with sota convergenced practice,bell should NOT ring all the time, only with real speacial reasons when esclated and the
sound should not too large"; "optimize with the best practice you deem the best" (asked whether to keep testing by hand);
"with current best sota practice" (persistence and dashboard); "also with latest sota practice,only show notification for
real needed choose action etc per user waiting,otherwise there are too much noise" (toasts); "Not now" (phone push); and
the approval of the plan that preceded this record.

**Scope:** one workstation (WSL2 distro `NativeStack`, Windows Terminal 1.24.11911.0, Claude Code 2.1.284, Codex 0.157.1).
Runtime settings changed on the host only; the settings template and `AGENTS.md` are unchanged. The change also registers
this record, its receipt and its artifacts in `manifests/evidence.json`, a shared hot file under
[`docs/lanes.md`](../lanes.md) (label `lane:foundation`). The two anti-pattern rows for this record follow in
a separate change, because `docs/harness-defaults.md` is edited by most changes and a shared edit there keeps a pull
request from merging cleanly. It closes the "how Windows Terminal's bellStyle responds to BEL"
bullet under "Not covered" in [`2026-09-28-community-sweep.md`](2026-09-28-community-sweep.md) and supersedes that
record's A09 decision (`preferredNotifChannel: terminal_bell` with a Notification hook as the fallback); both places now
point here.

## What was measured before the change

| Observation | Value | How |
| --- | --- | --- |
| Tab titles in the one Windows Terminal window | 7 tabs, 1 distinct title (all the static profile title) | UI Automation tab-name read-back; counts and a hash prefix only, no screenshot |
| Alerts | `terminal_bell` rang on every notification type, including the "Claude is waiting for your input" ping 60 s after each turn | client source and the 2026-09-28 A09 setting |
| Colour depth Claude Code emitted (`TERM=xterm-256color`, `COLORTERM` unset) | 37 foreground and 4 background 256-colour sequences, 0 truecolor | `claude --bare` first frame in a pty with an empty config directory and a dummy key |

## What upstream sources establish

| Claim | Source (read 2026-09-28) |
| --- | --- |
| `suppressApplicationTitle: true` discards every program-sent title (OSC 0/1/2) at the terminal core; the flag is re-read on settings reload | `microsoft/terminal@v1.24.11911.0` `src/cascadia/TerminalCore/TerminalApi.cpp` L87; `AppLogic.cpp` L207-L213, L304-L338, L376-L439; `Tab.cpp` L358-L367; `ControlCore.cpp` L918-L937; `Terminal.cpp` L100 |
| Fragments are re-merged on every settings load (`LoadAll` builds the `SettingsLoader` and calls `FindFragmentsAndMergeIntoUserSettings`); the watcher covers only `settings.json` | `CascadiaSettingsSerialization.cpp` L1203, L1246, L1271; `AppLogic.cpp` L304-L337 |
| Plain OSC 9 text is ignored; only `9;4` (taskbar and tab progress state), `9;9` (cwd) and `9;12` (marks) are handled, so no escape sequence can raise a toast in 1.24 stable or the 1.25 preview | `src/terminal/adapter/adaptDispatch.cpp` `DoConEmuAction` L3523-L3614 at `v1.24.11911.0` (`9;4` L3546, `9;9` L3580, `9;12` L3609); L3533-L3628 at `v1.25.1912.0` (a non-numeric first field returns at L3550-L3553; `9;4` L3556, `9;9` L3590, `9;12` L3619) |
| OSC 777 and OSC 99 are not handled; OSC 9001 handles only `CmdNotFound` | `src/terminal/parser/OutputStateMachineEngine.hpp` L202-L225, `.cpp` L749-L892; `adaptDispatch.cpp` L3797-L3819 |
| BEL is the only bell or notification signal Windows Terminal acts on (`DECPS`, `AdaptDispatch::PlaySounds`, plays notes but raises no bell indicator, and the `terminalSequence` allowlist cannot send it): default `bellStyle` is `audible`; any non-zero style shows a tab bell icon that clears on focus; `taskbar` flashes only when the window is unfocused; `bellSound` accepts a list | `TerminalPaneContent.cpp` L268-L303; `Tab.cpp` L440-L461, L1131-L1156; `IslandWindow.cpp` L919-L924; `adaptDispatch.cpp` L4799-L4818; `doc/cascadia/profiles.schema.json` |
| Toasts exist only on Terminal `main`: #20010 (infrastructure, 2026-04-30), #20011 `bellStyle "notification"` (2026-05-04), #20012 OSC 777 behind `compatibility.allowOSC777`, default false (2026-06-04). Neither release tag contains them | `gh api repos/microsoft/terminal/compare/93bdbfaa3d62304f4b50b4ca4484da4dd08e4a1f...v1.24.11911.0` and `...v1.25.1912.0` both report `diverged`; the `BellStyle` enum in `doc/cascadia/profiles.schema.json` carries `notification` on `main` and on neither tag (probe under Overturn conditions) |
| Claude Code's hooks reference lists Windows Terminal under OSC 9 notifications; that holds only for `9;4`. Codex's unit test asserts Windows Terminal is not OSC 9 capable | code.claude.com hooks reference, "Emit terminal notifications" (OSC 9: iTerm2, ConEmu, Windows Terminal, WezTerm; OSC 99: Kitty; OSC 777: urxvt, Ghostty, Warp); `openai/codex@rust-v0.157.1` `codex-rs/tui/src/notifications/mod.rs` L53-L61, L116-L131 |
| Claude Code's `terminalSequence` hook field accepts OSC 0/1/2/9/99/777 and BEL and is ignored under `-p` | code.claude.com hooks reference ("Emit terminal notifications") |
| Six of the eight matcher types are documented (the eighth, `push_notification`, was added on 2026-09-29): `permission_prompt` (held until the prompt has waited about 6 s), `elicitation_dialog` and `elicitation_url_dialog` (about 6 s without typing), `agent_needs_input` (a background session waiting while agent view is open, or a teammate setup question after about 6 s), `quota_auto_resume_stale` and `quota_auto_resume_disabled` (fire on the quota event). `worker_permission_prompt` is not documented: it rests on the installed binary, whose notification type list contains it and whose team inbox poller emits it with "needs permission for" and "needs network access to" messages. `push_notification` is not documented either; see the last update | code.claude.com hooks reference, Notification type table and timing notes; installed `2.1.284` binary (type list and inbox poller) |
| Settings edits, hooks included, hot-reload into running sessions; the sender reads `preferredNotifChannel` on every notification | code.claude.com settings, "When edits take effect"; installed `2.1.284` binary (the notification sender calls the settings getter for `preferredNotifChannel` before each dispatch); observed here: the host `ConfigChange` audit log gained 7 lines per edit, with seven sessions live |
| Claude Code's own tip list says "Try setting environment variable COLORTERM=truecolor for richer colors"; the effect is measured below | installed `2.1.284` binary, tip list |
| Codex promotes truecolor itself when `WT_SESSION` is set | `openai/codex@rust-v0.157.1` `codex-rs/tui/src/terminal_palette.rs` L43-L75 (`effective_stdout_color_level`, `stdout_color_level_for_terminal`); the diff renderer maps it at `diff_render.rs` L1132-L1156 |
| A profile's `environment` key sets each entry on the launched process and appends its name to `WSLENV`, so it reaches a WSL process started with `--exec` | `microsoft/terminal@v1.24.11911.0` `src/cascadia/TerminalConnection/ConptyConnection.cpp` L104-L127 (`WSLENV.4` at L118); `doc/cascadia/profiles.schema.json` `Profile.environment` |
| Codex `[tui] notifications` accepts `true`/`false` or a list of kinds (`agent-turn-complete`, `approval-requested`, `plan-mode-prompt`, `async-question`); the list is plain strings, so a misspelled kind loads cleanly and never notifies | `codex-rs/config/src/types.rs` L652-L657; `codex-rs/tui/src/chatwidget/notifications.rs` `type_name()` L72-L81, `allowed_for` L94-L98 |
| Codex's `terminal_title` defaults to `activity` (spins while working, shows an action-required message when blocked), `thread-name` and `project-name` | `codex-rs/config/src/types.rs` L826-L833 |

## Decision, as applied on this host

1. **Titles.** In the host practice repository's Windows Terminal fragment, the Claude and Codex profiles no longer set
   `suppressApplicationTitle`; `tabTitle` stays as the initial title and `tabColor` as the static identity. Shell,
   Operations and Local Chat keep static titles. Result: after the settings reload the distinct-title count rose from 1 to
   5 of 7 within minutes; the two sessions that were idle wrote their title only after a one-line message woke them, and
   the window then showed 7 distinct titles and 0 static profile titles (20:12 local time, unchanged at 20:26; 8 tabs, 8
   distinct, 0 static at 21:25). All of those tabs were Claude tabs: no Codex tab was open, so Codex's title behaviour
   rests on the source row above.
2. **Bell.** The Claude and Codex profiles use `bellStyle: ["audible", "taskbar"]` and `bellSound` `Windows Ding.wav`
   from the Windows media folder. An explicit array, never `"all"`: on Terminal `main` `"all"` also raises a toast. The
   Shell, Operations and Local Chat profiles use `["taskbar"]`: no sound, so a readline completion bell cannot ring in a
   static tab, and a taskbar flash still marks an unfocused window. Levels measured with 16-bit PCM RMS in dBFS: the
   first choice, Windows Notify System Generic, was -24.7 (peak -9.8) and was replaced after the user asked for a quieter
   sound; Windows Ding is -40.9 (peak -22.7), 16 dB quieter; ding.wav is -50.0 (0.4 s) if that is still too loud. A check
   in the host repository refuses, on the Claude and Codex profiles, any `bellSound` that is not exactly a measured quiet file directly in `C:\Windows\Media` (a subdirectory or a `..` path is refused; since 2026-09-30, after a cross-family review, and where that folder is readable from WSL the file must exist) and refuses
   `audible` on the static ones.
3. **Alerts only when a decision is pending.** `~/.claude/settings.json`: `preferredNotifChannel` is
   `notifications_disabled` (hooks still run) and one `Notification` hook, matcher `permission_prompt|elicitation_dialog|elicitation_url_dialog|agent_needs_input|quota_auto_resume_stale|quota_auto_resume_disabled|worker_permission_prompt|push_notification`, command `jq -nc --arg s "$(printf '\a')" '{terminalSequence:$s}'` (the hooks reference's construction, so no control
   byte sits in the settings string). The dialog types wait about 6 s for the user first; `agent_needs_input` fires when a background
   session starts waiting while agent view is open (its documented 6 s applies to an agent-team setup question); the
   quota types fire when the quota event occurs; `worker_permission_prompt` fires from the team inbox poller; `push_notification` was added on 2026-09-29 (see the last update). `idle_prompt` (the finished-and-waiting
   ping) is excluded on purpose, which also silences a question asked in prose and then left waiting; add it to the
   matcher to get it back. Codex `[tui] notifications = ["approval-requested", "plan-mode-prompt", "async-question"]`.
   An immediate `PreToolUse` chime on `AskUserQuestion|ExitPlanMode` was applied first and removed at the user's request:
   it rang every time Claude asked a question, and the away-gated route was measured to cover both dialogs (Evidence).
4. **24-bit colour, Claude profile only.** The profile sets Windows Terminal's native `environment` key,
   `"environment": { "COLORTERM": "truecolor" }`, and the command stays `exec claude`. The plan chose `~/.profile`, but
   this stack's settings template denies `Edit(~/.profile)` (`adoption/templates/claude.settings.template.json` L84, [`docs/secret-storage.md`](../secret-storage.md)) and the host applies it. An intermediate draft exported the variable in the profile
   command; the key replaces that shell wrapper, needs no change to the command line, leaves other login shells
   unchanged, and the host check now refuses the wrapper. Codex needs nothing (see the table). Only sessions started
   after the change see it.
5. **Watch, not build.** No Windows-side toast bridge is installed: no shipped Terminal can raise a toast from an escape
   sequence, and Terminal `main` will. The watch lives in the host practice repository's `upstreams.json`
   (`microsoft/terminal`, `recheck`) and is restated under Overturn conditions.

## Evidence

| Claim | Class | Result |
| --- | --- | --- |
| A program title flows once the flag is off; it does not with the flag on | native Windows Terminal, negative control | trial profile A (flag absent) read `title-trial-ok`; trial profile B (`suppressApplicationTitle: true`) kept its static title; the tab set returned to the baseline hash after both tabs closed themselves |
| The bell rings and marks the tab with the chosen bell settings, including an absolute local `bellSound` | user observation | the user heard the chime and saw the bell icon on the trial tab; the user did not report a taskbar flash, so the `taskbar` flag is kept because upstream documents it, but its effect on this host is not confirmed |
| An unanswered `AskUserQuestion` raises one Notification and one BEL, about 6 s after it opens, and nothing at open | native Claude Code, pty probe, in this host's own default permission mode (bypassPermissions, read from the on-screen footer) and again with an explicit `default` mode | `permission_prompt` at +6.1 s (bypassPermissions) and +6.0 s (default) ("Claude needs your permission"); one bare BEL byte at +6.1 s and +6.0 s. Earlier probe versions measured +6.0 s to +6.1 s |
| An unanswered plan approval behaves the same | native Claude Code, pty probe in plan mode (the only mode in which the dialog exists) | `permission_prompt` at +6.0 s ("Claude Code needs your approval for the plan"), one bare BEL byte at +6.0 s |
| The BEL comes from the user's hook, not from the client's own channel | native Claude Code, control | separate runs with the same session setup but every hook disabled (the observer hook included, so Notification events cannot be observed) opened the dialog (detected from its on-screen text) and produced 0 bare BEL bytes in the 16 s that followed, for the plan dialog and for `AskUserQuestion` in the host's default mode |
| The BEL counter counts bytes, follows the pinned terminal's parser transitions and ignores an OSC terminator | probe self-test | `alert_probe.py --selftest`: 24 of 24 checks pass. 22 counter cases, each derived by hand from `stateMachine.cpp` at `v1.24.11911.0` (`ProcessCharacter` L1838-L1924, `_EventEscape` L1084-L1161, `_EventOscString` L1487-L1508, `_EventOscTermination` L1519-L1532): plain and doubled BELs; an OSC title ended by BEL, also split across reads; a bare BEL after ST; a BEL executed in the escape state (`ESC BEL`, and after an interrupted OSC); a BEL after a DCS interrupted by `ESC ESC`; no bell for a BEL inside a DCS or APC string; a BEL inside a CSI sequence; CAN or SUB returning to ground. Two more checks: the private payload directory is removed after an interruption and after a failure. The counter models those transitions; it is not Windows Terminal's own parser |
| The saved hook command yields exactly one BEL | fixture (synthetic class only) | the exact string extracted from the saved settings ran under `bash -c` and its stdout decoded to one U+0007 |
| Claude Code draws in 24-bit colour with `COLORTERM=truecolor` | native Claude Code, pty capture | 0 truecolor and 41 256-colour sequences (37 foreground, 4 background) with `COLORTERM` unset; 45 truecolor (39 foreground, 6 background) and 0 256-colour with it set |
| The profile `environment` key reaches a process started with `wsl.exe --exec` | native Windows Terminal, negative control | trial profile D (`environment` set) printed `$COLORTERM` into its tab title and UI Automation read `env=truecolor`; control E (no key) read `env=`; the trial fragment and its two stubs were removed and Windows Terminal's `settings.json` was byte-identical to its pre-trial backup |
| The Codex configuration loads fail-closed and its kinds are real | native Codex, source | `codex --strict-config exec` returned `ok`, exit 0, and the `[tui]` table validates against the `rust-v0.157.1` schema. Strict config does not check the kind strings, so the three kinds were compared with `type_name()` (L72-L81) and the host check asserts the exact list |
| The check catches the original mistake and each single defect | negative control | on the previous fragment it fails ("AI-client profiles must let program titles through"); nine single-defect mutants (title suppression on Claude, a loud sound on both AI profiles, a relative `bellSound`, an AI `bellStyle` without `taskbar`, `"all"` and a `notification` list on static profiles, `audible` on a static profile, no `COLORTERM` key, `COLORTERM` in the command line) each fail exactly one rule, and it is the expected one (eight distinct rules; `all` and `notification` are two shapes of the same rule); on the new fragment it passes, and the deployed copy equals the repository source |

The probes ran a short real session from the repository root (already trusted) with an observer hook, sending no keys while
the dialog was open. Raw hook payloads go to a private temporary directory that the probe deletes; only counts and timings
are kept. Probe scripts, hashes and counts are in the
[receipt](../../evidence/receipts/terminal-experience-20260928.json).

**Not established.**
- Taskbar flash on this host. Click-to-focus. Toast display (none exists yet).
- A live, user-heard chime from either dialog through the Notification route (measured by the probe only; the chimes the
  user did hear were the trial tab's bell and the since-removed immediate `PreToolUse` chime).
- Codex tab titles: no Codex tab was open during any measurement.
- An audible bell in Windows Terminal for the alert path itself: the probe counts the BEL bytes the client writes to its pty,
  and ConPTY sits between that stream and Windows Terminal. The only bell the user observed was the trial tab's.
- Colour in a Claude tab launched from the updated profile: the two halves were measured separately (emitted
  sequences with `COLORTERM` set; the `environment` key reaching a `--exec` process), and sessions started before the change keep 256
  colours.
- `preferredNotifChannel` reaching sessions that started before the edit. The sender reads it on every notification,
  which supports hot reload, but no live peer was observed. A peer that still rings twice for one dialog or still sends
  the idle ping can be restarted, or its "Local notifications" value checked in `/config`.

## Alternatives, with pins read on 2026-09-28

| Alternative | Verdict | Why |
| --- | --- | --- |
| `DevinoSolutions/anotifier-for-claude-codex-cursor@92c080a7` (v1.2.6, AGPL-3.0) | compare | WSL absolute-path toast and BEL through `terminalSequence`, but synchronous Node hooks that wait for the toast, a daily npm check inside the hook, two contributors |
| `777genius/agent-notifications@0376f9c9` (v1.45.18) | compare (cross-platform) | strong project; README lists macOS, Linux and Windows and says notifications work from WSL after a Windows install (`README.md` L241-L256); its installer refuses to run inside WSL, where it would install Linux binaries, unless `CLAUDE_NOTIFICATIONS_ALLOW_WSL=1` (`bin/install.sh` L228-L260); wires `PreToolUse(ExitPlanMode\|AskUserQuestion)`; not tried on this workstation |
| `congmnguyen/claude-code-wsl2-setup@69620ec4` (v1.0.0) | compare (reference) | async tray balloon by absolute `powershell.exe`; author no longer tests WSL2 daily |
| `shanselman/toasty@973eeb8d` (v0.8.1, MIT) | compare (interim only if asked) | maintained, tested with `--dry-run`, Windows-only; writes a Start shortcut and a `toasty:` protocol handler on first run |
| `PeonPing/peon-ping@8ef37660`, `mylee04/code-notify@dcfd4ae6` | reject | bare `powershell.exe`, `/dev/tty` writes (hooks have no controlling terminal), `wsl-notify-send` |
| `Windos/BurntToast` | reject | archived 2026-09-25 |
| `stuartleeks/wsl-notify-send` | reject | last commit 2021 |
| Immediate `PreToolUse` chime on `AskUserQuestion\|ExitPlanMode` | reject | rings every time; the away-gated route already covers both |
| `bash -lc "export COLORTERM=truecolor; exec claude"` in the profile command | replaced | worked, but the native `environment` key does the same with no shell wrapper |
| `OSC 9;4` state hook (ring in tab and taskbar) | not built | capability verified, but no maintained upstream implements it |
| SessionStart `sessionTitle` from cwd or branch | not used | seven sessions share one checkout, names collide, and they replace better AI titles |
| Tab colour by escape sequence | not used | colour-table index 264 exists, but Claude's `terminalSequence` allowlist rejects palette OSC |
| tmux, zellij, tmux-resurrect and continuum, claude-squad, crystal, vibe-kanban | not adopted | dormant, deprecated, overlapping agent view, or no gain on Windows Terminal (below) |
| WezTerm, Windows Terminal Preview | not adopted | no documented gap that configuration here cannot close |
| `~/.profile` for `COLORTERM` | not possible | the settings template denies `Edit(~/.profile)` (`adoption/templates/claude.settings.template.json` L84) and the host applies it |

Persistence and dashboard: first-party agent view (`claude agents`, `--bg`) is the current best practice for many
sessions, but its background sessions move into `.claude/worktrees/` and commit and push, and this repository has a
recorded `core.hooksPath` rewrite hazard. The decision is probe-then-adopt, and the probe is pending (not run in this
change). It uses a throwaway repository with a relative `core.hooksPath`, a marker hook and a local bare remote, after the
user accepts the workspace-trust dialog there, and dispatches two `claude --bg` sessions that each edit a file: one with no
git instruction and one with a `CLAUDE.md` line saying the user handles commits and pushes. All of these must hold:
`core.hooksPath` unchanged after each; edits only under `.claude/worktrees/<name>`; the marker hook fires inside the
background session; nothing committed or pushed under the second dispatch; any push under the first reaches only the local
remote (recorded as a default to neutralise with a private user-level instruction before real use). Passing adds a
`NativeStack - Agents` profile (`claude agents`) beside the per-tab profiles; failing keeps one tab per session. **Superseded 2026-09-29:** agent view is not adopted and the probe is not run (see the update below); this procedure remains the check to run if detached background dispatch is ever wanted.

Validated but not adopted, tmux 3.4 (each line checked against the 3.4 tag's `options-table.c` and `tmux.1`):
`default-terminal tmux-256color`; `terminal-features xterm*:RGB`; `terminal-features xterm*:extkeys` with `extended-keys on`
(no effect on Windows Terminal: no modifyOtherKeys); `allow-passthrough all`; `focus-events on`; `escape-time 10`;
`mouse on`; `history-limit 50000`; `set-titles on`; `set-titles-string '#S: #T'`; `detach-on-destroy off`. Anthropic's
three-line block does less here than its page implies: `auto` emits nothing on Windows Terminal, so passthrough carries
nothing. (An earlier version of this sentence added that tmux through 3.6 lacks synchronized output. That is wrong: tmux 3.4 and 3.6 define the `sync` terminal feature in `tty-features.c`, and a private 3.4 server wrote 3 pairs of `ESC[?2026h`/`ESC[?2026l` to its outer terminal with `terminal-features 'xterm*:sync'` and none without it, `tmux_sync_probe.py`, corrected 2026-09-30 after the cross-family review. Whether Windows Terminal 1.24 honours mode 2026, and what tmux does with an application's own request for it, was not measured.)

## Overturn conditions

- **A Terminal release contains the toast work.** Two signals, either is enough to act on:
  1. Direct schema probe, which prints `true` when a tag's `BellStyle` enum carries `notification`, that is, when #20011
     (with #20010's infrastructure) is in the tag (measured 2026-09-28: `false` for `v1.24.11911.0` and `v1.25.1912.0`, `true`
     for `main`). #20012 adds the `compatibility.allowOSC777` setting, which is also in the `main` schema and in neither
     tag's; grep the tag's schema for `allowOSC777` before relying on OSC 777:
     `gh api "repos/microsoft/terminal/contents/doc/cascadia/profiles.schema.json?ref=<latest tag>" -H "Accept: application/vnd.github.raw" | jq '[.. | objects | select(has("enum")) | select(.enum | index("taskbar")) | .enum | index("notification")] | any'`
  2. Ancestry: `gh api repos/microsoft/terminal/compare/93bdbfaa3d62304f4b50b4ca4484da4dd08e4a1f...<latest tag> --jq .status`
     reports `ahead` instead of `diverged` for the first release that contains #20012 (#20011's merge commit is
     `a834313fb7`). Ancestry alone can miss a backport, because release tags sit on servicing branches: `v1.25.1912.0`
     is 55 commits ahead of and 87 behind `93bdbfaa`.
  Then update `checks/check-terminal-profiles.py` in the host repository in the same change (it forbids `notification`
  and `all` in `bellStyle` and requires exactly `["audible", "taskbar"]` on the AI-client profiles), add `"notification"`
  to the two `bellStyle` arrays (BEL becomes a toast; the needed-only hook keeps it rare), and consider
  `compatibility.allowOSC777` with the hooks reference's OSC 777 example so the toast carries the message.
- **A maintained upstream implements a state indicator or a WSL-aware notifier** that clears the bar in this record's table.
- **Idle-ping wanted.** Add `idle_prompt` to the Notification matcher.
- **Mac hosts** keep `auto` (native desktop notifications in Ghostty, iTerm2 and Kitty). To make one needed-only, emit the
  sequence its terminal implements, per the hooks reference's list (OSC 9 for iTerm2, OSC 99 for Kitty, OSC 777 for
  Ghostty), and set `notifications_disabled` there only after a delivered notification is observed on that host. An OSC
  777 hook in iTerm2 would notify nothing: its parser maps OSC 9 to a user notification and returns not-supported for
  numbers it does not list, and 777 is not listed
  (`gnachman/iTerm2@52fdf260e0822ffb655fe3cd44d041dc876aadae` `sources/VT100/VT100XtermParser.m` L276-L320).

## Rollback

Restore the backed-up fragment (or `git revert` in the host practice repository) and touch `settings.json` to reload;
restore `~/.claude/settings.json` and `~/.codex/config.toml` from the backups taken before the change. Backups are private
and outside every repository.

## Update 2026-09-29: login shell contract, launch practice and landscape refresh

The user asked for the open items of this record to be decided by research convergence and carried through. This update also adds the two anti-pattern rows
of the earlier update, which that change left out so that its pull request could merge cleanly, and one for this incident. The evidence is in the
[receipt](../../evidence/receipts/login-shell-contract-20260929.json) and its
[scripts](../../evidence/artifacts/login-shell-contract-20260929/README.md). The Windows Terminal profiles of the second distro (Polaris; two per-project Claude profiles) were outside this update and were not measured; the same-day section "Repository-carried defaults" below brings them to this policy.

### What broke, and why

New `NativeStack - Claude` tabs printed `/bin/bash: line 1: exec: claude: not found` (exit 127). Every profile starts `/bin/bash -lc`, and
bash reads only the first of `~/.bash_profile`, `~/.bash_login` and `~/.profile` (`bash(1)` INVOCATION; the header of `/etc/skel/.profile`
says the same). An empty `~/.bash_profile` had appeared, so `~/.profile`, which carries PATH on this host, was never read: a login probe
through `wsl.exe --exec` found no `claude`, `codex` or `rtk`. Open sessions were unaffected, no user unit failed and the user journal
held no exit-127 line. Claude Code's hooks, Bash tool and MCP servers take PATH from the `env` block of the user settings (the settings
template sets it), so they did not depend on the login shell.

The cause is a known upstream behaviour, not a local fault: it is reported upstream and acknowledged as intended by a maintainer, but not
yet described in the environment-variable documentation. With `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` on Linux with bubblewrap, Claude Code pre-creates an
empty regular file for each missing protected path (shell startup files, package-manager and git configuration, `.env*`) and does not remove
it; the installed 2.1.284 startup code opens a fixed list of such paths in append mode, which creates a missing file and never truncates an existing one (11 names in the home, among them `~/.bash_profile` and `~/.profile` but not `~/.bash_login`, and in the working directory 9 fixed names plus a list held in a variable, the `.env*` files; `startup_placeholder_names.py` reads the list from the binary), and also touches `/tmp/inline-comments-buffer.jsonl`. anthropics/claude-code [#76236](https://github.com/anthropics/claude-code/issues/76236) reports exactly this empty `~/.bash_profile`
(closed `not_planned` by the stale bot on 2026-09-01). [#78072](https://github.com/anthropics/claude-code/issues/78072) is open and
labelled `reproduced`; a maintainer comment of 2026-08-17 calls the persistent files intended ("pre-created as an empty regular file so
protected tools ... keep working") and says cleaning them up at exit is being considered. The 2.1.284 changelog has no such fix. The variable arrived in 2.1.83 (credential stripping), and 2.1.98 added subprocess sandboxing with PID namespace isolation on Linux when it is set. The changelog's sandbox-cleanup entries are 2.1.69 (ghost dotfiles in the working directory's `git status` after sandboxed Bash commands), 2.1.78 (stubs in the working directory's `git status`), 2.1.247 (an after-command cleanup deleting a symlinked settings file), 2.1.257 (a `/doctor` warning for stale sandbox mask files left by a killed session) and 2.1.271 (a stale `.git/config.lock`); none removes the scrub-mode startup placeholders. The documented per-command placeholders are removed after each sandboxed command, and a killed session can leave them
([sandboxing troubleshooting](https://code.claude.com/docs/en/sandboxing)); the scrub-mode startup placeholders persist by design, and the
installed `claude doctor` did not flag the scrub-created `~/.bash_profile` (measured below). A headless `claude -p` probe of a peer session ran with
the variable against the real home and created 14 empty entries there within about a second (and the empty `/tmp/inline-comments-buffer.jsonl`); its scratch working directory held empty `.env*`,
`.gitmodules`, `.npmrc` and `.claude` from the same run, and its no-variable arm none. These reports were only read; nothing was filed or
commented.

### Evidence, 2026-09-29

| Claim | Class | Result |
| --- | --- | --- |
| A login shell started as the profiles start it finds no `claude`, `codex` or `rtk` while the empty file exists, and finds them once that one file is removed | native, before and after | the probe printed nothing for the three names with the distro default PATH; after removing only `~/.bash_profile` (asserted regular, empty, that creation time, no `bwrap` or `srt` process) `claude`, `codex`, `nativestack`, `rtk` and `uv` resolved |
| The variable creates the empty file and takes `~/.local/bin` out of the login PATH; without it no empty placeholder file is created; a real hand-off file is left alone | native Claude Code, isolated home, control arm | no variable: 0 empty files, PATH kept. Variable, stock home: 27 empty files and 12 empty directories (19 directories in all) including `~/.bash_profile`, `~/.local/bin` gone from the login PATH. Variable, real hand-off file: byte-identical, PATH kept (26 other empty files still created) |
| The doctor's `login-shell-path` check fails the incident and passes a healthy home | fixtures and the real host | five temporary homes as expected (`~/.profile` only passes; an empty `~/.bash_profile`, an empty `~/.bash_login` and no startup file fail with all four names missing; a hand-off file passes); the real host passes |
| The installed `claude doctor` does not flag the scrub-created empty `~/.bash_profile`, and by its documented scope it cannot | native Claude Code, isolated home; the planted file shows the warning is live | in the stock-home arm's home `claude doctor` printed 3 warnings with the sandbox off and 4 with the sandbox enabled and a planted 0-byte, read-only `proj/.claude/settings.local.json`; the planted file was named and `~/.bash_profile` in neither run. The documented warning covers 0-byte read-only placeholders that a killed sandboxed command left where a settings file belongs ([errors page](https://code.claude.com/docs/en/errors#stale-sandbox-mask-files-left-by-a-killed-session)); the scrub-created file is a 0-byte file with mode 0644 in the home, so the silence follows from that scope and the planted file is not a control for it. The native warning does not replace the doctor check |
| The reproduction wrote only inside its throwaway directories, apart from one shared temp file it removed | native, the script measures it | each arm ran with `TMPDIR` and `CLAUDE_CODE_TMPDIR` pointing at a short private directory beside its throwaway home (the client caps the path of its messaging socket, `<dir>/cc-socks/<pid>.sock`, at 103 bytes (its own constant; Linux allows 107) and falls back to a fixed `/tmp/cc-socks-<uid>` directory in the real `/tmp` when the path is longer, so with a 7-digit pid a private path over about 81 bytes falls back (the control used 99); `XDG_RUNTIME_DIR` is preferred over the temp directory and must stay unset; `socket_path_fallback_probe.py` shows both cases with a control), which held the client's temporary state (a per-directory state folder, a file-watch probe folder and, in the two scrub arms, one sandbox multiplexer socket in the recorded run; the counts vary a little between runs) and went with it; in the recorded run of 2026-09-29 the real `/tmp` and `/tmp/claude-<uid>` gained no top-level entry (a concurrent session can add one inside that window) and the 14 named files of the real home that script listed still existed (that first version did not list `~/.bash_profile` and compared only whether names existed); the rerun with the revised script on 2026-09-30 (native client 2.1.285, `recorded/scrub_placeholder_probe.txt` in the 2026-09-30 receipt) compared 19 names of the real home (the client's startup placeholder list and a few more) by lstat mode, size, mtime and inode and found none changed, while the real `/tmp` gained two top-level entries of no kind the script counts (a concurrent session's, as the warning above says) and `/tmp/claude-<uid>` none, and its arms reproduced the recorded counts (27 and 26 empty files in the two scrub arms, 12 empty directories in the stock-home arm, no empty file in the control); writes inside entries that already existed under `/tmp` are not measured; the shared `/tmp/inline-comments-buffer.jsonl`, a path the client hard-codes, was absent before, appeared during the run and was removed by the script, which cannot tell its own arms' creation of it from a concurrent session's |
| Creating the hand-off file changes nothing about the login PATH | native, digest | 13 entries and the same digest before and after (`login_path_digest.py`); the revised script gives 13 entries again on 2026-09-30 (`recorded/login_path_digest.txt`; the digest value of 2026-09-29 was not recorded, so it is not compared) |

### Decisions

| Decision | Chosen | Alternatives rejected | Overturned when |
| --- | --- | --- | --- |
| Login shell | Keep `bash -lc` in every profile. Keep a real `~/.bash_profile` that hands off to `~/.profile` (`if [ -r "$HOME/.profile" ]; then . "$HOME/.profile"; fi`), never an empty one. Keep the doctor check, because the doctor has no scheduler | Remove the stray file and rely on the doctor: any creator of missing files undoes it. An absolute `--exec` launcher with no login shell: it starts Claude, but the host's `codex` launcher (a local integration that sets the telemetry identity) execs the npm shim (`#!/usr/bin/env node`), which exits 127 under the default PATH (`/usr/bin/env: 'node': No such file or directory`); the package also bundles a native executable that starts under a clean PATH, but the launcher does not use it, its path is specific to the installed version, and starting it directly would bypass the shim and the telemetry-identity launcher. The Shell, Operations and Local Chat tabs need the login files either way. `--shell-type login` starts `-bash` and reads the same files in the same order. PATH through the profile `environment` key or `WSLENV`: no documented support for the Linux PATH. `. ~/.profile` spelled in the command line, or `env PATH=...` in the fragment: no upstream reference, and a third copy of PATH | A creator truncates or replaces an existing file (pin the launcher and supply PATH explicitly). The `codex` launcher execs the bundled native executable, or puts `node` on PATH itself (an absolute `--exec` then becomes viable for the Codex tab; the Shell, Operations and Local Chat tabs still need the login files). Upstream stops creating the placeholders or removes them at exit (the file stays harmless, the check stays) |
| Session names | No `-n` or `--name` in the shared profiles; use `/rename` in a tab | A fixed name: a name set with `--name` replaces the generated tab title, and a second live session with the same name is renamed to a variant, so the tabs of a profile would carry the fixed name or a variant of it instead of their own titles | Separate per-lane profiles with unique names are wanted |
| Resume | No resume profile; `/resume` in any tab, `claude --resume`, `codex resume` | Extra profiles for the picker: no measured gain for added fragment and check surface, and the practice repository resumes deliberately with the native picker | Repeated resume steps after restarts become a measured cost |
| Agent view | Not adopted; the probe is not run. The scripted `claude agents --json` needs no adoption: it prints the active interactive and background sessions (`name`, `cwd`, `pid`, `sessionId`, `startedAt`, `status`; no token or cost field), and `--cwd` narrows it | The agent view screen lists only background sessions ("Interactive sessions you have open in other terminals don't appear until you background them"), documents no token or cost column, shows the workspace-trust dialog first when the directory is not yet trusted, and a background session "commits without asking, and pushes the branch when the repository has a remote" unless your git instructions say otherwise; adopting it would move the per-tab workflow to background sessions, which distinguishable interactive tabs with alerts do not call for | Detached background dispatch is wanted (then run the probe described above) |
| Telemetry gaps | Unchanged here. The collector and the launcher belong to the owners of the token-efficiency measurement: no tab identity beyond `session_id`; per-skill, per-agent and per-MCP labels are dropped from the metrics (Loki keeps them); project agent names collapse to `custom`; traces are off; the dashboards have no per-session variable; Loki keeps 3 days and Prometheus 1 week | Changing the collector or the launcher while a measurement window is sealed. The design-supported route to a tab identity is a `service.instance.id` in `OTEL_RESOURCE_ATTRIBUTES` from the profile's `environment` key: the collector keeps a launcher-set id and appends `/<session.id>`, and the Codex launcher keeps an inherited id as a prefix ([collector README](../../observability/collector/README.md)); it changes the `session_id` values of those tabs, so their owners decide | The window closes and the owners accept the changed `session_id` values |

Sources for these decisions: the GNU Bash Reference Manual, "Bash Startup Files", in the maintainer's copy
([bashref](https://tiswww.case.edu/php/chet/bash/bashref.html#Bash-Startup-Files); `~/.bash_profile` conventionally hands off to another
startup file) and `bash(1)` 5.2.21 INVOCATION for the read order; the Arch
([`dot.bash_profile`](https://gitlab.archlinux.org/archlinux/packaging/packages/bash/-/raw/main/dot.bash_profile)) and Fedora
([`dot-bash_profile`](https://src.fedoraproject.org/rpms/bash/raw/rawhide/f/dot-bash_profile)) bash package skeletons, which ship a
`~/.bash_profile` that sources `~/.bashrc`; Ubuntu 24.04's `/etc/skel/.profile` (not read if `~/.bash_profile` or `~/.bash_login` exists;
it sources `~/.bashrc`); `wsl.exe --help` (WSL 2.7.13.0: `--exec`, `--cd`, `--shell-type`); and the Claude Code documentation pages for agent
view, cross-session messaging, the settings reference and the CLI reference.

Visibility, as documented and observed: Claude tabs of one user in one distro see each other with `ListAgents` and `SendMessage`
([cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging), Claude Code 2.1.224 or later); with
`crossSessionInbound: accept` and bypass mode no approval dialog holds a message. Codex tabs are not in that registry (observed), and tabs
in another distro or on the Windows side are expected to be invisible (inferred). `claude agents --json` prints the active interactive and background sessions with their `status` (the cooperation recipe's sentence that it finds same-host Claude peers was checked against the installed CLI and stands); no tab or command shows another tab's token usage.

### Landscape refresh, 2026-09-29

- **Windows Terminal:** no release since 2026-07-16 (stable `v1.24.11911.0`, preview `v1.25.1912.0`). Both toast signals are unchanged: the `BellStyle` enum of neither tag carries `notification`, and both tags report `diverged`. No overturn condition of this record is met.
- **Claude Code:** `2.1.284` is still the newest release (2026-09-28); the changelog has no cleanup of the scrub-mode startup placeholders (the entries are listed above).
- **Codex:** `rust-v0.159.0` (2026-09-29) is the newest stable at the re-run (the first refresh of the day saw `rust-v0.158.0`; host: `rust-v0.157.1`). `chatwidget/notifications.rs`, `notifications/mod.rs` and `terminal_palette.rs` are identical between the two tags, the four notification kinds are unchanged, and the `Notifications` type and the `terminal_title`, `notification_method` and `notification_condition` settings are identical (the 70 changed lines of `config/src/types.rs` add copy-on-select and right-click paste settings, the `log_agent_responses` and `log_guardian_assessments` logging opt-ins (for the owners of the telemetry row) and an MCP startup re-export). The host check and `[tui] notifications` need no change when Codex is next upgraded; this record does not upgrade it.
- **Candidates:** every pin in the table above is unchanged (repository heads equal the recorded pins; no archived repository). agent-deck, ccmanager and zellij carry no pin in the table: the refresh script recorded their heads on 2026-09-29 as baselines, so there is nothing earlier to compare them with.

### Corrections after the bounded re-check (2026-09-29)

A headless Opus reviewer at effort max re-checked the merged change and found six defects, all repaired here: (1) the row that said the reproduction touched nothing outside
its homes was false, because the client also leaves a sandbox multiplexer socket in `/tmp` and a file-watch probe folder under `/tmp/claude-<uid>` (the script now redirects the client's temporary state to a short private directory and measures the real temp directories instead of assuming; a first repair still leaked when the caller's TMPDIR made the private path too long for the client's messaging socket, which the review round after it found); (2) the native `claude doctor` negative was taken with the
sandbox off, where the stale-mask warning cannot fire, so it now has a second run with the sandbox enabled and a planted positive control; (3) the changelog list missed 2.1.69
and did not name where the variable and its sandbox came from (2.1.83 and 2.1.98); (4) the startup-code fact had no producing command, so
`startup_placeholder_names.py` reads it from the binary; (5) three candidate pins in the refresh script had never been recorded before it ran and are now marked as baselines;
(6) the practice repository's README still described a fixed name as giving every tab one name and stated the invisibility of other distros as fact. The receipt carries the re-run values.

## Repository-carried defaults and the second distro's profiles (2026-09-29)

The user asked for the terminal profiles to default to the current best practice, cleanly, so that every later session and host picks it up, and for a usage limit not to
shorten any planned review. Until now this record's settings lived in host files: the deployed fragment and the hand-edited live settings. This change moves them into the
repository and brings the second distro's per-project Claude profiles to the same policy. The evidence is in the
[receipt](../../evidence/receipts/wsl-terminal-defaults-20260929.json) and its [scripts](../../evidence/artifacts/wsl-terminal-defaults-20260929/README.md).

### What the repository carries now

| Default | Where | Checked by |
| --- | --- | --- |
| Claude Code: `preferredNotifChannel` `notifications_disabled` and the one `Notification` hook that rings for a needed action only | `adoption/templates/claude.settings.linux-wsl2.overlay.json`, merged with `tools/adoption/apply_claude_settings.py` | merging it into this host's live settings changed nothing, and the live bell group's matcher equals the overlay's (the merge alone cannot see that: it de-duplicates hooks by command, so a catch-all group or an older matcher merges to itself; the acceptance script checks the group count and the matcher, and a test proves it refuses both wrong hosts); tests pin the keys, the matcher (each needed type matches, four other types do not), one BEL from the hook command, an idempotent merge and composition with the base template in either order |
| Codex: `[tui] notifications` naming the three needed-action kinds | `adoption/templates/codex.config.template.toml` | the rendered template loads under `codex --strict-config` (wrong type and unknown top-level key refused; an unknown key inside `[tui]` is not, so a test pins that table's setting names); the kinds are pinned to the four literals at `rust-v0.157.1` |
| Windows Terminal profiles: own titles, an explicit quiet bell, truecolor, a login shell | `examples/claude-native/windows-terminal.fragment.example.json` and the recipe's Claude entry | policy tests with negative controls (title suppression, `"all"`, an implicit bell, a loud sound and a launch without a login shell are each refused); the profiles declare no GUID, so Windows Terminal derives a stable one from the folder and profile names (`Profile.cpp` `_GenerateGuidForProfile` at `v1.24.11911.0`). The fragment page calls a GUID "optional, but strongly encouraged"; the example declares none because the publication scan treats any UUID as a session identifier, and renaming the folder or a profile changes the derived value, so the platform page says to keep both fixed |
| The login-shell precondition | `scripts/adoption_status.py --login-shell` (file metadata only) | 512 combinations of three startup files over eight states against the real bash login search, 0 mismatches, a FIFO made bash block (the model calls it unusable and unread), and a wrong model disagrees in 26; unit tests |
| Steps and placement | `adoption/platforms/linux-wsl2.md`, "Windows Terminal profiles and the login shell" | the docs-consistency tests |

### Decisions

| Decision | Chosen | Alternatives rejected | Overturned when |
| --- | --- | --- | --- |
| Where the Claude settings live | A separate Linux/WSL2 overlay, merged after the base template | Folding them into `claude.settings.template.json`, which the macOS host also renders: the default `auto` channel sends a desktop notification in Ghostty, iTerm2 and Kitty and does nothing in Windows Terminal ([settings reference](https://code.claude.com/docs/en/settings-reference#preferrednotifchannel)), so the bell hook is the Windows Terminal answer and not every host's; a test keeps the base template free of both keys | Windows Terminal acts on a notification sequence (the toast condition above) or the macOS host wants the bell too |
| Login files | The bootstrap writes no shell startup file; `--login-shell` reports and the operator keeps a real hand-off `~/.bash_profile` where `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` is set | Having the bootstrap create the hand-off file: startup files are the operator's, and the failure needs that variable | An empty startup file appears on a host without the variable, or upstream stops creating the placeholders |
| Codex notifications on other hosts | The needed-action list lives in the shared template, so a macOS host that renders it gets the same list; Codex keeps its own per-terminal channel (`notification_method` stays `auto`), so the needed kinds still notify natively and only the turn-complete notification stops; at the macOS pin (0.155.1) a `request_user_input` question already notifies as `plan-mode-prompt` (`tool_requests.rs` L449-458 at both tags), and `async-question` (asynchronous questions, `questions.rs` at `rust-v0.157.1`) is inert there, so no notification that release emits is lost | Scoping the list to the Linux/WSL2 render with a Codex overlay: it adds a manual merge step and splits the render, and unlike the Claude channel change there is no observe-first risk, because the delivery path is unchanged and no needed alert can be lost | A Mac host wants the turn-complete ping (add `agent-turn-complete` to its rendered list), or `async-question` changes meaning |
| The second distro's Claude profiles | The same policy: no `suppressApplicationTitle`, `bellStyle` `["audible", "taskbar"]` with the quiet sound, `COLORTERM` through `environment`, the overlay in that distro's Claude settings; `tabTitle` and `tabColor` stay as the initial title and identity | Leaving them: two sessions of one project would read the same fixed title, the failure this record fixed for the first distro | Fixed per-project titles are wanted again: set the flag back and change the check's rule |
| Fullscreen repaint variable | Not set on any profile; that distro already runs `tui: fullscreen` by its own setting | `CLAUDE_CODE_ALT_SCREEN_FULL_REPAINT=1` everywhere: the upstream documentation makes it a reactive fix for stale fragments and none was observed | Stale fragments appear in a Windows Terminal tab |

### Evidence, 2026-09-29 (second part)

| Claim | Class | Result |
| --- | --- | --- |
| The overlay reproduces the live settings | native, the repository's merge tool | `--dry-run` exit 0 and the merged result equals the live file; exactly one Notification group holds the bell command and its matcher equals the overlay's |
| The Codex template is accepted by the installed Codex | native Codex 0.157.1 | the rendered template loads (the run stops at authentication); the two negative controls are refused, the unknown key inside `[tui]` is not |
| The static login-shell model equals bash | native bash 5.2.21, control arm | 512 combinations over eight states (absent, empty, content, directory, dangling symlink, symlink to a file, `/dev/null`, unreadable), 0 mismatches; a FIFO blocked bash; the empty-file-as-absent control disagrees in 26 |
| The second distro's profiles and settings follow the policy | native, before and after | both profiles lost the title suppression and gained the quiet bell and `COLORTERM`; every other profile, the defaults and the other settings are equal; the overlay changed only `$schema`, `hooks` and `preferredNotifChannel` there, and the installed hook command printed one BEL |
| The host check catches a regression | fixtures and the real host | the check scans the live settings file and passes; the pre-change file (kept privately) fails it with 8 findings on exactly those two profiles and 4 distinct rules; 22 single-defect controls (9 fragment, 10 settings, 3 overrides under the derived GUID of a fragment profile that declares none) each fail for exactly their rule. Review round 2 found that the first version of the check crashed on a fragment without GUIDs (`KeyError`, exit 1) and that the fix left an override under the derived GUID unchecked (exit 0); the check now derives that GUID the way Windows Terminal does, and the controls compute the recipe independently and assert the documentation's own example |

Limits: one workstation; Claude Code applies edits to `hooks` to a running session without a restart (settings reference, "When edits take effect"), so open sessions of the second distro should pick the overlay up, which was not observed there; no tab was
opened and no bell was heard in this work; the profile example was not loaded into Windows Terminal; nothing here is in the pinned release until a release carries it
and the manifest is re-pinned.

## Update 2026-09-29 (late): the model's own push signal, every notification type and agent teams in Windows Terminal

The user asked for the finalized setup to be ready for complex workflows and for the projects and north star that follow. A long workflow ends, or blocks, while the user is
away, and the model's own way to say so is the PushNotification tool. The [receipt](../../evidence/receipts/notification-types-20260929.json) and its
[scripts](../../evidence/artifacts/notification-types-20260929/README.md) hold the evidence.

### What was found

- **The overlay's bell missed the model's push.** The installed Claude Code (2.1.285) knows 17 distinct notification types, all valid matcher values (a 15-item base array plus `elicitation_complete` and `elicitation_response`). The hooks reference documents 12; the bell hook rang for seven. In a native pty probe with no user-scope settings, a model-initiated PushNotification (after a focus-out report) raised a `Notification` event of type
  `push_notification` and nothing rang; with one more hook that matches that type, exactly one BEL reached the terminal; and with this host's own settings after the change, the same one BEL. A headless `-p` run of a few seconds (the elapsed time was not recorded) raised no event: the tool's result began "Not sent" (the client's text for a present user reads "Not sent because you're active in this terminal."). The same presence rule applies to `-p`, so a longer run may behave differently (not measured).
- **When the push is sent, and when it cannot ring.** In a local session the tool sends nothing, and raises no event, while the client judges the user present; a remote workspace (`CLAUDE_CODE_REMOTE` set, or a remote workspace) skips this check and the `agentPushNotifEnabled` one (installed 2.1.285: `r=a.CLAUDE_CODE_REMOTE||Fn()`, then `!r&&...V4r()`; source read, no remote session run; found by the cross-family review of this change). The client's rule for a local session, read from the installed binary (`function V4r`, `var KWt=60000`, called only by the PushNotification tool): once the terminal has sent a focus report (DECSET 1004) the last reported state decides, and `focused` counts as present however long the user has been away; before any report the user is present if the last input was under 60 s ago. `CLAUDE_CODE_DISABLE_NOTIFICATION_PRESENCE_CHECK` bypasses the check, at the price that a push is then also sent while the user is watching. So a push, and its bell, reach a user whose tab or window was last reported unfocused (or who was idle for 60 s before any report), and do not reach one who walked away from a tab last reported focused. In a terminal session the permission prompt's own notification is timed by inactivity, not by the focus report: the hooks reference says it arrives once the user has not typed for about six seconds, the timer starting when the prompt appears and each keystroke deferring it, and the installed client's terminal path compares `Date.now()` with the later of the prompt's appearance and the last interaction (`function tye`, source read, not run). The fixed-delay timer in the binary (`function G`, guarded by `CLAUDE_CODE_DISABLE_PERMISSION_PROMPT_NOTIFY_HOOKS`) is the Agent SDK path, which the reference times about six seconds after the request whether or not the user types; an earlier wording of this record took it for the terminal dialog and was corrected on 2026-09-30 when the cross-family review's finding on this was verified and refuted. The probe's arms measure both branches with a synthetic report (see the evidence table). Windows Terminal defines mode 1004 (`DispatchTypes.hpp` L541 at v1.24.11911.0); whether it reports focus for a background tab or an unfocused window, and what the last report is when a real user leaves, was not measured. Two more conditions leave the bell silent: in a local session with Remote Control connected and the mobile-push setting off (`agentPushNotifEnabled`, default false) the tool returns `config_off` before it raises the event (a remote workspace skips this check too), and the tool exists only where the server-side flag `tengu_kairos_push_notifications` is on (it is on for this account).
- **Every type now carries a decision.** Eight ring (`push_notification` joins the seven), six documented types stay quiet on purpose (`idle_prompt`, `auth_success`, `elicitation_complete`,
  `elicitation_response`, `agent_completed`, `quota_auto_resume_fired`) and three undocumented ones stay quiet (`computer_use_enter`, `computer_use_exit`, `model_refusal_fallback`). None is unclassified.
  One table (`DECISIONS` in the scan, imported by the test) gives each type its decision, whether the hooks reference documents it and its reason; the test also reads the installed client with the scan's own reader and fails on a type the table lacks (skipped where no client is installed), and the scan exits 1 on one.
- **Agent teams need nothing more in Windows Terminal.** The default `in-process` display works in any terminal and runs the teammates inside the lead's terminal (upstream's display-mode page), so the lead's own alerts ring in its tab; whether an alert that a teammate raises (`worker_permission_prompt`) reaches the hook was not observed. Split panes are opt-in and need tmux or iTerm2, and upstream's limitations say split-pane mode isn't supported in Windows Terminal (it may mean native panes; tmux inside WSL is outside its stated support and unmeasured for teams here), so none is configured. What was measured is only that tmux 3.4 forwards a pane's BEL to the outer terminal by default (a pty in the probe) and that `bell-action none` or `visual-bell on` stops it (5 arms with a negative control).

### Decisions

| Decision | Chosen | Alternatives rejected | Overturned when |
| --- | --- | --- | --- |
| Push notification | Add `push_notification` to the overlay matcher and to this host's and the second distro's settings (both backed up; only the bell group changed) | Leave it silent: the type of the model's own "come back" signal would ring nothing in Windows Terminal (a probe with no bell hook for it rang nothing). A second hook or a `Stop` hook: it would ring for every turn | Models over-notify and the bell stops being rare: take the type out again and rely on the alert types above |
| Presence check | Keep the client's default (`CLAUDE_CODE_DISABLE_NOTIFICATION_PRESENCE_CHECK` unset) | Setting it to 1: a push is then sent, and rings, while the user is watching as well, and it is the way this record knows to be alerted after leaving a tab last reported focused in a local session; unmeasured here and against this record's quiet bell | A long workflow finished or blocked while the user was away from a focused tab and nothing rang: set it for those sessions and measure how often a push rings while watching |
| The other types | Quiet, each with its reason in the scan's table | `idle_prompt` and `agent_completed`: a ping for every finished turn or background run, the noise this record removed. Keeping `agent_completed` quiet also silences a background session that failed while agent view is open (the person is looking at that view) | The user wants completion pings, or a background failure went unnoticed: add the type to the matcher |
| Team display mode | Keep the default `in-process`; no `teammateMode` setting; no tmux configuration | Setting `teammateMode` (documented in the settings reference; `--teammate-mode` overrides it per session) to `tmux`: upstream's limitations say split-pane mode isn't supported in Windows Terminal, and split panes under tmux there are unmeasured for teams here. Setting it to `auto` changes nothing in a plain tab, where it falls back to in-process | A team run needs several visible panes at once and someone measures split panes under tmux in Windows Terminal |
| Team quality-gate hooks | Not adopted here | `TeammateIdle`, `TaskCreated`, `TaskCompleted` hooks (exit 2 gives feedback): upstream's gates, but they need a rule to enforce and the hook set is to be frozen for the Gate A window | A team run repeats a defect that a gate would catch, and the freeze is over |

### Evidence

| Claim | Class | Result |
| --- | --- | --- |
| The installed binary knows 17 notification types, all valid matcher values; 8 ring, 9 stay quiet, none without a decision | native, the binary read by `notification_types_scan.py` | 17 distinct types (a 15-item base array plus the two elicitation completion types), 12 of them documented in the hooks reference; 8 ring, 9 quiet; the same 17 in 2.1.283, 2.1.284 and 2.1.285; the scan exits 0 |
| A model push raises `push_notification`, rings nothing without a bell hook, and rings once with one; in a local session the tool sends only while the client judges the user away | native Claude Code 2.1.285, interactive pty, negative controls | arm A (no user settings, observers only, focus-out report sent): 1 event, 0 BEL; arm B (plus the bell hook): 1 event, 1 BEL; arm C (this host's own settings after the change): 1 event, 1 BEL, the tool called 53.7 s after Enter. The presence rule, both branches: with no focus report, arm D (`sleep 75`, tool called 81.1 s after Enter) raised the event and arm E (`sleep 15`, 20.1 s) raised none and rang nothing (the probe does not record the tool's reply; the client's text for a present user reads "Not sent because you're active in this terminal."). Before the change the same probe on this host's settings gave 1 event and 0 BEL (coordinator's own output, recorded as values). In arm D an `idle_prompt` event also fired while the model's shell command was still running; that type stays quiet. |
| tmux forwards a pane's BEL to the outer terminal | native tmux 3.4, private server, a pty as the outer terminal, negative controls | default 1, `bell-action any` set explicitly 1 (it is the default `tmux show-options -g bell-action` reports), `bell-action none` 0, `visual-bell on` 0, no-BEL pane 0 |
| The scan reads the whole matcher catalog whatever the minified spread name is | native, the three installed releases, negative control | 2.1.283 (its spread name `P$o` contains a dollar sign), 2.1.284 and 2.1.285: base array 15, catalog found, 17 matcher values each. The scan's first pattern (`\w+`) read 15 of the 17 on 2.1.283 without an error; now a blind reader exits 1, two synthetic-binary tests cover spread names with and without `$`, and each is shown to fail against a mutant |
| The settings replacement tool refuses what it cannot replace safely | our integration check on a synthetic `HOME`, mutants as negative controls | 17 cases, 0 problems (refusals for another hook in the group, extra hook keys, a matcher type the overlay lacks, an absent matcher, an existing different `preferredNotifChannel`, two bell groups, a symlink, an unknown target or flag; `--apply` writes a backup equal to the original and keeps the mode); 9 mutants, each removing one guard, each fail exactly the cases named for them |
| Both settings files changed only in the bell group | native, the repository's merge tool on a private copy | this host's file `adf498161eb0` to `a36476496a39` and the second distro's `5d0c86aed514` to `6f9931921c14` (SHA-256 prefixes), every other key and hook event equal, backups kept; a rerun of the hardened tool still reports "nothing to do" on both, although this host's file was rewritten after the change (its hash moved; the bell group is unchanged) |
| Agent teams: `in-process` works in any terminal, split panes need tmux or iTerm2 and are not supported in Windows Terminal, three team hooks exist | source review | [agent teams](https://code.claude.com/docs/en/agent-teams), "Choose a display mode", "Enforce quality gates with hooks" and the last limitation, fetched 2026-09-29 |

Limits: one workstation and one probe model (Haiku); the probe's "away" is a synthetic focus-out report or 60+ s without input in a pty, not a real absence, and it does not show how Windows Terminal reports focus (a background tab, an unfocused window, or the last report when a real user walks away); the probe does not record the tool's reply, so the "Not sent" text comes from the binary; no audible bell in Windows Terminal was observed by the user; the probe cannot say how often a model chooses to send a push, so the overturn condition is the check; the `notificationType:"…"` literals are a lower bound: `computer_use_enter` occurs once in the binary, in the matcher list, and `model_refusal_fallback` is a matcher value and a system-message subtype with no such call site (a text search cannot prove absence; this host also sets `CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK=1`), while `computer_use_exit` has one (the client says "Claude is done using your computer"); nothing here was run in a team session.


## Update 2026-09-30: the cross-family review of the terminal lane

The Codex cross-family round of #484, #498, #510 and #519 could not run on 2026-09-29 (every GPT-6 account was at its weekly limit). On 2026-09-30 the user asked to finalize the lane with GPT-6.1 Sol
(or GPT-6 ultra) through the SOTA harness and OmniRoute, with the token-save practice. The round ran: nine read-only jobs of the packaged Codex lane, `cx/gpt-6.1-sol` at effort `max`, Codex CLI 0.159.2
through the local gateway. The [receipt](../../evidence/receipts/cross-family-review-terminal-lane-20260930.json) and its [artifacts](../../evidence/artifacts/terminal-lane-cross-family-review-20260930/README.md)
hold the evidence, and `findings.json` there has a row for each of the 46 findings.

### What was found

- **Controls and checks that could not fail (the largest group).** The login-shell check passed when a startup file exited before the probe ran, accepted a shell function that the profiles' `exec` cannot start,
  and failed a healthy home because of an empty `~/.bash_login` that bash never reads; the digest script hashed the empty output of a failed shell; the Codex strict-config check accepted any failure it did not
  recognise; the tmux probe's exit status ignored its `visual-bell` arm; the pty probes' hooks-disabled control could not fail by exit status; the 512-combination login-shell oracle compared only an exported mark that
  is empty for 344 of the 512 combinations, so a wrong `first_read` passed; the notification-type scan chose its base array by contents, so an unrelated array could hide a new type; the overlay oracle ignored `disableAllHooks`;
  the host check accepted `C:\Windows\Media\missing\Windows Ding.wav` as a measured quiet sound. Each is repaired with a control that fails without the repair.
- **A tool that could lose settings.** `replace_bell_group.py` installed over a settings file that another writer had saved after the tool read it (the client and other tools save that file), dropped keys on the bell group
  that it refused on the inner hook, and printed a matcher value in a refusal. It now compares the live file with the bytes it read before the backup and again right before the rename, refuses those keys and counts what it would drop (a save between the last comparison and the rename is still lost, and is in neither the installed file nor the backup: a documented residual with a case of its own); its second-distro target went with that distro.
- **Statements that were wrong.** `tmux through 3.6 lacks synchronized output` (tmux has a `sync` terminal feature; measured); the bell icon `stays until the tab is focused` (on the focused tab it clears after about 2 s);
  the PushNotification presence rule stated for every session (a remote workspace skips it and the `agentPushNotifEnabled` check); the advice to copy `profiles.defaults` variables into a fragment's `environment` (Windows Terminal ranks
  a profile's own value, then `profiles.defaults`, then a fragment's profile, so a `defaults` key beats the fragment); a README that called every script temporary-directory-only although the plan probe makes the client write a plan file.
- **Probe hygiene.** SIGTERM and SIGHUP left the raw payload directory and the client process behind; the BEL counter disagreed with the pinned output engine on ignored UTF-8 C1 characters; the colour counter counted
  `38;2;...` in cursor-position sequences; probes printed notification text and the screen although they promised counts only; a receipt named the private profiles of the second distro.
- **Two findings were wrong.** Claude Code runs identical command hooks once, so a repeated bell hook does not ring twice; and a terminal's permission notification is timed by inactivity (the fixed-delay timer the reviewer
  read is the Agent SDK path). The second refutation also showed that the coordinator's own first correction of this record had taken the SDK timer for the terminal's, and had to be undone.

### The bounded re-check of the repairs

One re-check followed the repairs, as the bounded-review rule allows (one review, one repair round, the residuals recorded): three read-only jobs of the same lane (`cx/gpt-6.1-sol`, one per lens: the tool
and the probes; the scan, the tests and the scripts; the claims and the evidence) and one job of `cx/gpt-6-astra-ultra`, a second GPT-6 model asked for an adversarial second opinion. They returned 33 findings
(1 high, 24 medium, 8 low): 12 duplicates of another finding, 2 checked by the coordinator, 19 graded by Claude verifiers (16 confirmed, 3 partly, none refuted). `recheck-findings.json`, `recheck-verification.json`
and `recheck-results.json` in the artifact directory hold them. The first repairs were incomplete or wrong in several places, so a passing repair is not treated as a finished one here:

- **A claim that was false.** `replace_bell_group.py` said the backup holds a save that lands between its last comparison and the rename; it holds the bytes the tool read, so that save is in neither file. The tool now
  compares the live file once more right before the rename (which also closes an atomic save made while the backup is copied), states the residual that cannot be closed without a lock the client does not take, and has
  one case per interleaving (after the merge, at the backup, while the backup is copied by an atomic save, after the backup, at the rename), each requiring the harness's marker so an injection that did not happen fails.
- **Signal handling that still left the client behind.** A second signal, a signal during the probe's own normal-exit cleanup, a signal between the child's creation and its registration, and a double Ctrl-C each left
  the client running or the payload directory behind. The first signal now wins, the cleanups run with SIGINT, SIGTERM and SIGHUP deferred, and the client is created under a spawn flag: a signal
  mask around the spawn would be inherited by the client (a verifier saw it, and a `sleep` child of a process that blocks SIGTERM, SIGHUP and SIGINT shows `SigBlk` 0x4003; a shell stand-in clears its own mask, so
  the end-to-end cases read the mask of the exec'd program from `/proc`). `pty_probe_mutants.py` shows that each case fails without its guard.
- **Controls that still could not fail.** The end-to-end SIGTERM case passed when its stand-in client never started; the scrub probe's selftest compared appended and replaced files against an already-changed baseline;
  the scan accepted a member assignment `obj.x=[...]` for the catalog's array; the landscape comparison dropped `Notifications`' default, the `terminal_title` field and multi-line attributes; the colour counter misread
  colon sub-parameters; the login-shell check accepted a stale hashed or a non-executable path; the digest hashed the first `PATH=` line of the shell's output; the derived push probe's hooks-disabled control exited 0
  after a BEL; the documentation test recognised a matcher only when it named `permission_prompt`; a mode control depended on the caller's umask.
- **Claims without a record.** The decision record said a rerun of the strengthened scrub probe was recorded, and the login-shell receipt said a rerun gave the same digest; both reruns are now recorded (the digest
  value of 2026-09-29 was never recorded, so no comparison with it is claimed). The artifact README said three pool points where the receipt said four, the tmux probes said they write only inside their private
  directory while their socket sat in `/tmp/tmux-<uid>/` (it now lives inside the directory), and the review record republished two private project labels.

Residuals of this round: the repairs are checked by controls, mutants and native reruns but were not read again by a reviewer; a save between the settings-swap tool's last comparison and the rename is still lost;
a scan of a minified bundle cannot resolve a name by scope (stated in the scan, and not triggered by the three release binaries); the colour counter treats an incomplete `38;2` group as unclassified, where the
terminal applies missing components as 0; and the probes' timing-dependent case (a signal inside the normal-exit cleanup, about 1.8 s wide) fails loudly rather than passing if the probe is slow.

### Decisions

| Decision | Chosen | Alternatives rejected | Overturned when |
| --- | --- | --- | --- |
| Cross-family review lane | The packaged Codex lane on the local OmniRoute gateway: `cx/gpt-6.1-sol`, effort `max`, read-only, one prompt per unit and lens, Codex 0.159.2, no self-written runner | The native Codex login (exhausted until 2026-10-04); GPT-6 astra (the earlier default: Sol is the newer model at lower cost per OpenAI's release notes, not compared head to head here); a self-written runner (the top rule) | The pool is exhausted again, or a head-to-head shows Sol and astra find different defects |
| Verify before repairing | Every finding is graded by a read-only Claude verifier (Opus, effort max) or checked by the coordinator against the code or the upstream source before any change | Applying the findings as returned: 2 of 23 graded findings were refuted and 4 were narrower than claimed, and one refutation caught a wrong earlier correction | A review lane whose findings are proven on their own by a test each (41 of 46 came with a command, not all a test) |
| Where the repairs live | In place, in the scripts of the earlier artifact directories; a new receipt for this pass; a correction limitation in each of the four older receipts (their recorded values come from the earlier script versions, whose hashes they name) | New artifact directories per revised script (the earlier receipts would then cite scripts that no longer exist); rewriting the older receipts (they record what ran) | The manifest validator starts to require a receipt's script hashes to match the tree |
| Second-distro target of the settings-swap tool | Removed with the distro (unregistered 2026-09-29); three findings about its shell snippet close with it | Keeping an untestable path | Another distro needs the swap |
| Fragment install guidance | The platform page and recipe now say a `profiles.defaults` key beats a fragment-only profile's value and how to override it (remove the key, or use the `settings.json` entry for the profile's GUID) | Leaving the copy-the-variables advice (it changes nothing for a fragment-only profile) | Windows Terminal changes its layering |

### Evidence

| Claim | Class | Result |
| --- | --- | --- |
| Nine review jobs on `gpt-6.1-sol` at `max` through OmniRoute returned 46 findings | native, the packaged runner's own records | all exit 0; 3 high, 34 medium, 9 low; 41 with a command the reviewer ran; 24.47M input tokens, 95.0% cache reads, 0.36M output, 71 minutes, four points of the pool |
| The findings were checked before anything changed | native (Claude Workflow, three waves) plus coordinator checks | 23 graded (17 confirmed, 4 partly, 2 refuted), 11 duplicates, 12 coordinator checks; 39 repaired, 2 refuted, 3 removed, 2 kept |
| The repairs hold | our integration checks, negative controls | 238 unit tests OK (one skipped); the settings-swap tool: 27 controls (a fixed umask) and 15 mutants each failing exactly its cases (the unmutated script passes all 27); 8 reader mutants; the two pty probes' selftests with seven end-to-end signal cases each and 12 mutants (six per probe) showing that each case fails without its guard (the unmutated probes pass all six); 11 login-shell homes; 512 bash combinations with `first_read` compared; the practice repository: 29 profile-check cases |
| The strengthened scrub probe and the PATH digest were rerun natively | native, native client 2.1.285 in throwaway homes; this host's login shell | 19 real-home names unchanged by lstat mode, size, mtime and inode; the arms reproduce 27 and 26 empty files; 13 PATH entries (`recorded/scrub_placeholder_probe.txt`, `recorded/login_path_digest.txt`) |
| Four re-check jobs (three `gpt-6.1-sol`, one `gpt-6-astra-ultra`) returned 33 findings, all repaired | native, the packaged runner's own records; Claude Workflow verifiers | 1 high, 24 medium, 8 low; 19 graded (16 confirmed, 3 partly), 12 duplicates, 2 coordinator checks; 17.47M input tokens (96.0% cache reads), 0.18M output, 46 minutes, the pool 11 to 22 points |
| tmux 3.4 emits synchronized output only when the terminal is declared to support it | native, private tmux server, negative control | 3 pairs of `ESC[?2026h`/`ESC[?2026l` with `terminal-features xterm*:sync`, none without |
| The colour counter's earlier counts stand | native rerun of `claude --bare` in a pty | 0 vs 45 truecolor and 41 vs 0 256-colour sequences, now counted as SGR only |

Limits: one workstation; one review model and one verifier family, and the verifiers saw the reviewers' evidence; no Windows Terminal or interactive Claude Code session was run (the bell and the focus reports remain
unobserved); the remote-workspace branch of the push tool, Windows Terminal's parent order and the focused-tab bell timer rest on source reading; the repairs got one bounded re-check (above), and the fifth-round repairs
were not read again by a reviewer (their residuals are listed above).
