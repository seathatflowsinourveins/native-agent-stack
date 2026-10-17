# Decision: Remote Control at startup on the new WSL distribution (2026-10-17)

**Status:** adopted in PR (b) condition 4, under the CC's ruling D6 (2026-10-17). The repository carries the setting; writing
it on a host is the CC's act, through `new_wsl_client_config.py --apply --with-authorization-settings
--with-remote-control-at-startup` (the second option is the amendment below).

**Supersedes:** the `claude:setting:remoteControlAtStartup` row of
`catalogs/foundation/upstream-surface-dispositions.json`, which declined the key with "off on both hosts (read
2026-10-04)". That row is rewritten to `enabled` in the same change, as the NativeHorizonNY host read (the user settings
carry `true` there); it says that the repository default is off (the amendment below). The dated record it cited,
[2026-09-27-mac-single-writer-staged.md](2026-09-27-mac-single-writer-staged.md):57, stays unchanged. It says the key is
valid only in user settings, and this decision follows that.

## Decision

The new WSL distribution's Claude Code user settings carry `remoteControlAtStartup: true`. Each interactive session then
starts the Remote Control bridge, so the owner's own claude.ai/code or Claude app can drive it.

- **Carrier:** `adoption/new-wsl/templates/claude.settings.additions.json`, the user-scope additions that only
  `tools/adoption/new_wsl_client_config.py` renders. The shared template and the WSL2 overlay do not carry the key, so no
  other host takes it.
- **Class: authorization.** `claude/settings/setting/remoteControlAtStartup` is in the tool's `AUTHORIZATION_PIECES`,
  and its map entry is `authorization:<reason>`. It is rendered and written only with `--with-authorization-settings`,
  and never over a value the host's settings.json already has, so a host's own `false` stays. `--check` refuses a map
  that classes the key practice or slot.
- **Not carried:** `agentPushNotifEnabled`. It stays a host choice; its dispositions row (declined) is unchanged.

## Why authorization

The setting grants a remote device control of the session. On this distribution, `--with-authorization-settings` also
writes `permissions.defaultMode = "bypassPermissions"` and `crossSessionInbound = "accept"`, and each has its own
effect, as upstream gives it (https://code.claude.com/docs/en/permission-modes.md, lines 571 and 573, and
https://code.claude.com/docs/en/cross-session-messaging.md, lines 195 and 203-206, both read 2026-10-17):
- `bypassPermissions` "disables permission prompts and safety checks so tool calls execute immediately". It alone makes a
  turn started from claude.ai/code or the Claude app run its tool calls with no prompt, with or without `accept`, except that "the actions no mode auto-approves still prompt in this mode" (line 573).
- `crossSessionInbound = "accept"` decides only whether a message from the user's other sessions is delivered to Claude
  ("delivers each message to Claude"). With no value set, Claude Code holds a message for approval in two cases: a
  receiving session that prompts for permissions holds one when the sender identifies itself as bypassing, and a
  receiving session that bypasses holds each one unless the sender also bypasses. `accept` delivers both. It changes no
  tool call's prompting.
- `remoteControlAtStartup: true` starts the Remote Control bridge in each interactive session, so the owner's own
  claude.ai/code or Claude app can drive it. It changes neither of the other two.

On a host that takes the whole bundle, Remote Control is therefore a remote ingress whose tool calls run with no prompt, apart from the actions no mode auto-approves,
(from `bypassPermissions`) and which other sessions' messages also reach (from `accept`). The Mac stage disclosed the
same combination (evidence/artifacts/mac-stage1-client-layer-20260927/README.md:545-560). Classing
the key practice would write it by default on every apply. The authorization class keeps it with the other settings
that grant a permission or suppress a confirmation, so the host owner chooses it.

## Authority

The CC's ruling D6 for PR (b) condition 4 (hcom #9109, 2026-10-17) names this host's authorizing record. It is the CC's
launcher design, made under the owner's 2026-10-16 direction that sessions relaunch seamlessly, as the previous CC's did
(paraphrased). That design passes `--remote-control` in every launcher it records:

- The CC's tracker CC-TRACKER-NHNY-20261016.md, lines 104-109, records the CC relauncher `relaunch-cc.sh` passing
  `--remote-control nhny-cc`. Line 600 records ruling D6: Remote Control is authorization class, and this host's
  record is the CC launcher design under the owner's 2026-10-16 direction. The tracker is a running file; this record
  read it at 2026-10-17T02:02:58Z.
- The CC relauncher `relaunch-cc.sh`, line 50, passes `--remote-control nhny-cc` at that read. The tracker's entry
  names an earlier revision of the relauncher; both pass the flag.
- The builder launcher `launch-ns51-v4.sh`, line 51, passes `--remote-control nhny-builder`.
- The resolver launcher `launch-resolver.sh`, line 38, passes `--remote-control nhny-resolver`.

These are private records outside the repository, cited by name only; a reviewer on that host can read them there. The
flag starts Remote Control for the one session a launcher opens; the setting does the same for every interactive
session, which is what a clean install of the distribution needs.

## Upstream facts

- Remote Control auto-connect from a settings file: `remoteControlAtStartup` set to `true` in the user
  `~/.claude/settings.json` or in managed settings. In project or local settings, Claude Code honors a `false` and
  ignores a `true` (https://code.claude.com/docs/en/remote-control.md, line 198, read 2026-10-17T02:04:30Z).
- The settings precedence table: a `false` from `.claude/settings.json` or `.claude/settings.local.json` is honored even
  when a managed source sets `true`, and a project or local `true` is ignored (https://code.claude.com/docs/en/settings.md,
  line 741, same read).
- The installed client is Claude Code 2.1.302 (`claude --version`). Its binary reads the key from policy, flag and user
  settings only. It prints "repo-scoped settings cannot enable Remote Control; set it at user scope (/config)" for a project or
  local `true`. This was read from the binary's strings, not documentation, so the two documentation lines above are the
  citation.
- This repository's project settings (`.claude/settings.json`) set no `remoteControlAtStartup`, so no project `false`
  turns it off in this checkout.

## Host read

NativeHorizonNY's `~/.claude/settings.json`, read by key at 2026-10-17T02:19Z: `remoteControlAtStartup` true,
`crossSessionInbound` "accept", `permissions.defaultMode` "bypassPermissions" and `agentPushNotifEnabled` true. The last
of these is a host choice. The dispositions row's "off on both hosts" was therefore stale for this host.

## Overturn

Revisit this when one of these happens:

- A Remote Control session is measured driving an unwanted tool call on a bypassPermissions host.
- The owner asks for Remote Control to start only from a launcher's flag.
- A Claude Code release changes the scope rule for the key.

## Amendment (2026-10-17): a separate opt-in inside the authorization class

The CC's ruling G3 for the PR (b) fold (hcom #14261, sent 2026-10-17T03:11:03Z by the hcom event time) narrows this
decision. Where the sections above differ, this section governs; they stay as first written.

- **Separately opt-in, default off.** `claude/settings/setting/remoteControlAtStartup` stays an authorization setting
  (`AUTHORIZATION_PIECES`, map entry `authorization:<reason>`). The tool also names it in `SEPARATE_OPT_INS` with its
  own option, `--with-remote-control-at-startup`. The key is rendered and written only when that option and
  `--with-authorization-settings` are both given, and still never over a value the host's settings.json already has.
  `--with-authorization-settings` alone no longer writes it, and the new option without the bundle is refused (exit 2).
  `--check` scans a third render of the example host, with both options.
- **Why.** The launchers cited above start Remote Control only for the one named session each opens. The setting starts
  it for every interactive session, a bypassPermissions one included, on any host that takes the authorization bundle,
  and the bundle is all-or-nothing. The wider scope is therefore its own choice.
- **What the bundle still writes, and what each part does.** The authorization bundle still writes
  `crossSessionInbound = "accept"` (a value the host already has is kept). Its own effect is on messages only, as the
  section above gives it from upstream lines 195 and 203-206: it delivers a message that Claude Code would otherwise hold
  for approval, both when a prompting session receives from a bypassing one and when a bypassing session receives from a
  non-bypassing one. It does not make Remote Control's tool calls run without a prompt; `bypassPermissions` does that.
  Writing the bundle without the new option leaves Remote Control off and `accept` on. The map's wiring reason for
  `crossSessionInbound` states the same two cases.
- **The launchers keep their named `--remote-control` flags.** This change touches none of them.
- **Widening it.** Making Remote Control start in every session by default is the owner's choice; the CC puts it to the
  owner. Until the owner decides, the repository carries the key off by default.
- **Tests.** `tests/test_new_wsl_client_config.py` `RemoteControlAtStartupTests` covers the default (off, with or without
  the bundle), the explicit opt-in (on only with both options), an existing value (never written over) and the opt-in
  alone (refused). The dispositions row's reason says the same, and the 2026-10-17 addenda of
  [2026-10-02-new-wsl-client-configuration.md](2026-10-02-new-wsl-client-configuration.md) carry the regenerated tables.
