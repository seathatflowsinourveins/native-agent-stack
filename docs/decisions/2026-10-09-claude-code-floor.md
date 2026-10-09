# Raise the Claude Code minimum to 2.1.295

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

Existing floor tests exercise the new exact boundary, a newer release,
versions below the minimum, numeric ordering and invalid version output.
Historical snapshots and measured-client fixtures retain their recorded
versions. The PR records the complete targeted module results and repository
validation. No native install, update, sign-in or model acceptance is run.

The repository inverse restores the previous installer minimum and its
artifact digests. It does not downgrade a newer installed launcher. The
unrelated search-route build remains parked for its source handoff; this
minimum-version PR does not alter that build or the live gateway. Both
designated reads, required CI, the pre-cue tool and an explicit command-center
cue remain landing gates.
