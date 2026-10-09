# Claude Code 2.1.295 minimum and plugin notification decision

Both native bootstrap manifests now select the Claude Code 2.1.295 installer
artifact as their minimum release. Their existing `version_probe.match` is
`minimum`, and both `install_native` functions keep an equal or newer native
launcher. The new-WSL profile also explicitly defines its pin as a floor and
retains the native latest-channel update step. These are minimum-version
schemas; no runtime equality constraint or ceiling is introduced.

The native installer still verifies the selected artifact before installing
it when the launcher is missing, unreadable or below the minimum. A launcher
at 2.1.295 or above is kept without downloading or installing the older
artifact. Functional acceptance runs separately on the resulting version.

## Distribution evidence

The source is Anthropic's native release
[2.1.295 manifest](https://downloads.claude.ai/claude-code-releases/2.1.295/manifest.json)
and [documented integrity/signing procedure](https://code.claude.com/docs/en/setup#binary-integrity-and-code-signing).
The retained cc-native-practice check at **2026-10-09T06:13:50Z** is cited
from `PROPOSAL-guard-fail-closed.md` section B, SHA256
`9ae0a4c2faf71cd93b8aacce931fa4f96b15386e1da62f343d17ba499c096440`.
Its private custody locator is
`$HOME/.local/state/native-agent-stack/coordination/cc-native-practice-20261009/PROPOSAL-guard-fail-closed.md`.

The forwarded check is: manifest **b36d7b37**, **Good signature**, fingerprint
**31DD DE24 … CACE**; linux-x64 **4503bfe1…f358**, **256,113,848 B**.
The source proposal supplies the full values:

| Item | Retained check |
| --- | --- |
| Manifest SHA256 | `b36d7b376c95dd409212ecce0b700cd547266d9ea014ab1f81a1d5bc49cb3cbe` |
| Manifest signature SHA256 | `7cc44851b80b692481cf986699276c4c14b4301b61aabf46682ad9224ab24c32` |
| Release commit | `07e8f67ea3282bf154a9e05673a0942b1b173cef` |
| Build date | `2026-10-08T17:09:12Z` |
| Signing-key fingerprint | `31DD DE24 DDFA B679 F42D 7BD2 BAA9 29FF 1A7E CACE` |
| GPG result | Good signature from “Anthropic Claude Code Release Signing <security@anthropic.com>” |
| linux-x64 SHA256 / size | `4503bfe11a6c7fcc1e0b39b5e0d347c04248f750b03b0977b3ad6b531fe6f358` / 256,113,848 B |
| darwin-arm64 SHA256 / size | `0116ee2e0a513900b633d9951367f18747686478e2b462805b8c31609f047f70` / 239,695,888 B |

This is a retained check performed by cc-native-practice, not a new signature
or artifact verification by currency. The source reports that the host's
installed Linux binary matched the digest and size. It reports no Mac
rehash, execution or `codesign` verification. The macOS row keeps its
`manifest_crosscheck` evidence boundary. Currency did not download the
artifacts, import a key, rerun GPG, inspect credentials or change a client.

## Plugin notification classification

The same 2.1.295 client also carries `plugin_notification`. Its decision is
**quiet**, with `documented=False` in the shared notification decision table.
The primary source is the pinned
[2.1.295 Linux artifact](https://downloads.claude.ai/claude-code-releases/2.1.295/linux-x64/claude)
with the retained digest above. `claude --version` returned
`2.1.295 (Claude Code)`; bounded reads of that installed artifact found the
type in its matcher catalog at zero-based byte offset 207984418 and in its
`$.ui.notify` emitter at 217182500:

```javascript
sI()?.notify?.({message:e.text,title:e.title||n.plugin,notificationType:"plugin_notification"},n.origin)
```

The plugin supplies the text and optional title; otherwise the title is its
name. The enclosing emitter reports the delivery channel, disabled/no-channel
or no-surface status, or a channel-write error. It has no permission or
input-wait predicate. A generic plugin notification therefore does not
establish the needed action that the escalation-only bell policy requires.
The repository bell matcher excludes this quiet type and continues to match
exactly the decision table's ring types. No live settings are applied.

The [official hooks reference](https://code.claude.com/docs/en/hooks#notification)
sample fetched at 2026-10-09T08:53:56Z had zero occurrences of this type,
HTML SHA256 `eed92dc40935f74820bc090b899e529e11574171570e6e1b69d636825a15202b`.
That reference is current documentation, not a version-pinned introduction
claim. The documented-type count remains 12; the enforced decision count
increases from 18 to 19. The pinned-source excerpts, offsets, documentation
sample and evidence limits are retained in
`evidence/artifacts/notification-types-20260929/recorded/f10-2.1.295-source.json`.
No artifact was downloaded or rehashed for this fold.

The installed-client regression case is preserved. At the prior PR head
`d73b1caa1cdba1f94521a34bec5c327e9d35a206`,
`python3 -m unittest tests.test_windows_terminal_defaults` returned 1:
45 tests, with the sole failure reporting `['plugin_notification']` as a
type without a decision. Adding its quiet decision and updating the count
allows the same module to pass. Both native outputs are retained as
`f10-2.1.295-before.txt` and `f10-2.1.295-after.txt` beside the source record.
The public failure traceback replaces its host path with `<repo>`; the raw
before/after outputs are also retained in the lane's private evidence.
This is an installed-client source/consistency check; live plugin delivery
and terminal-bell acceptance were not run.

Ringing for every plugin-authored message would include messages with no
established escalation. The decision should be revisited if a later pinned
client adds an explicit needed-action contract to this type. Removing the
row and restoring the old count reverses the repository classification,
and deliberately restores the fail-closed unknown-type failure on 2.1.295.

## Repository change and verification

The two platform rows receive the new minimum, artifact URLs and manifest
digests. Their component-inventory version mirror and the Mac page's current
artifact table follow those rows. The inventory's existing freshness text
already identifies its version as the bootstrap floor. The new-WSL profile receives the same Linux artifact and updates its
installation example, release source, acceptance prerequisites and receipt
floor. The older host 2.1.287 observation is kept as historical evidence
against the former 2.1.284 floor; it does not satisfy the new minimum.
Destination acceptance stays UNRUN.

The handbook is regenerated with
`python3 scripts/build_new_wsl_handbook.py --write`; its generated Markdown
and JSON are not hand-edited. Its rolling integration receipt refreshes the
profile/output digests and appends this local regeneration while preserving
its earlier validation history. Bootstrap documentation and floor examples
follow the new minimum. The separate historical 2.1.284 compatibility
threshold for the interactive Max-effort wrapper remains unchanged.

The generated new-host grand list receives its current component version
from that inventory, so its JSON and Markdown are refreshed through
`python3 scripts/new_host_grand_list.py --write` and checked with `--check`.
The component evidence matrix remains current without a status change.

The explorer's rolling upstream snapshot also mirrors the current selected
version. Its Claude Code selection is synchronized to 2.1.295, with a dated
local-integration refresh that preserves the September 29 upstream checks
and describes the selected floor as newer than that dated observation.
This repairs the profile generator's freshness-consistency failure; it is
not a new upstream latest-release observation.

Existing floor tests exercise the new exact boundary, a newer release,
versions below the minimum, numeric ordering and invalid version output.
Historical snapshots and measured-client fixtures retain their recorded
versions. The PR records the complete targeted module results and repository
validation. No native install, update, sign-in or model acceptance is run.

The repository inverse restores the previous installer minimum and its
artifact digests. It does not downgrade a newer installed launcher. The
separately recorded search-route build keeps its own source, build and
owner gates. Both
designated reads, required CI, the pre-cue tool and an explicit command-center
cue remain landing gates.
