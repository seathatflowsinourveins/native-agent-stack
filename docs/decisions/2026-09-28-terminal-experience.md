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
| Six of the seven matcher types are documented: `permission_prompt` (held until the prompt has waited about 6 s), `elicitation_dialog` and `elicitation_url_dialog` (about 6 s without typing), `agent_needs_input` (a background session waiting while agent view is open, or a teammate setup question after about 6 s), `quota_auto_resume_stale` and `quota_auto_resume_disabled` (fire on the quota event). `worker_permission_prompt` is not documented: it rests on the installed binary, whose notification type list contains it and whose team inbox poller emits it with "needs permission for" and "needs network access to" messages | code.claude.com hooks reference, Notification type table and timing notes; installed `2.1.284` binary (type list and inbox poller) |
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
   in the host repository refuses any sound outside the measured quiet set on the Claude and Codex profiles, and refuses
   `audible` on the static ones.
3. **Alerts only when a decision is pending.** `~/.claude/settings.json`: `preferredNotifChannel` is
   `notifications_disabled` (hooks still run) and one `Notification` hook, matcher
   `permission_prompt|elicitation_dialog|elicitation_url_dialog|agent_needs_input|quota_auto_resume_stale|quota_auto_resume_disabled|worker_permission_prompt`,
   command `jq -nc --arg s "$(printf '\a')" '{terminalSequence:$s}'` (the hooks reference's construction, so no control
   byte sits in the settings string). The dialog types wait about 6 s for the user first; `agent_needs_input` fires when a background
   session starts waiting while agent view is open (its documented 6 s applies to an agent-team setup question); the
   quota types fire when the quota event occurs; `worker_permission_prompt` fires from the team inbox poller. `idle_prompt` (the finished-and-waiting
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
`NativeStack - Agents` profile (`claude agents`) beside the per-tab profiles; failing keeps one tab per session.

Validated but not adopted, tmux 3.4 (each line checked against the 3.4 tag's `options-table.c` and `tmux.1`):
`default-terminal tmux-256color`; `terminal-features xterm*:RGB`; `terminal-features xterm*:extkeys` with `extended-keys on`
(no effect on Windows Terminal: no modifyOtherKeys); `allow-passthrough all`; `focus-events on`; `escape-time 10`;
`mouse on`; `history-limit 50000`; `set-titles on`; `set-titles-string '#S: #T'`; `detach-on-destroy off`. Anthropic's
three-line block does less here than its page implies: `auto` emits nothing on Windows Terminal, so passthrough carries
nothing, and tmux through 3.6 lacks synchronized output.

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
