# Runtime host-local name checks

F11 uses the installed Betterleaks 1.9.0 scanner for host-local bare names. The
scanner source is `betterleaks/betterleaks` at
`81aff7a638638aae3a659845d089043e1d8fe9ac`. Runtime names come from `id -un`,
personal profile directories under `/mnt/c/Users`, and the effective Git email
local part. Windows' shared `Public` folder, `Default` template, and `All Users` /
`Default User` compatibility junctions are not personal profile names and are
excluded from that filesystem source. The identity and email sources retain their
values even if those values coincide with a system-folder name. The synthetic-only
`NATIVE_AGENT_HOST_NAMES_JSON` override replaces
all three sources for tests. Candidates and native configuration stay in process
memory. Nothing registers or prints the candidate list.

The adapter generates supported native custom rules with escaped, case-insensitive
literal regexes. Betterleaks Expr filters exclude matches next to Unicode letters
or numbers; punctuation remains a valid bare-name boundary. The adapter performs
source collection, input framing, subprocess isolation and location mapping. It
does not implement matching or Unicode boundary checks.

## Native framing and privacy

The pinned `sources/file.go` reads 100,000-byte chunks. `sources/common.go` adds
at most 25,000 bytes while seeking a double-newline boundary, without overlap.
Passing an arbitrary long original record directly can therefore lose a match
or its neighbor context at a chunk boundary. Rejecting every long record also
prevents a clean repository tip from passing its gate.

Each original line becomes bounded records of at most 4,096 Unicode code points,
separated by double newlines. Overlap covers the longest candidate and both
neighbor characters. Artificial edges receive alphanumeric guards. Native Expr
filters discard matches that consume those guards, and only admit content
records; the initial text prefix cannot become a finding. This preserves native
boundary decisions while mapping every retained record back to the original
file and line. Malformed UTF-8 becomes replacement runes, preserving valid UTF-8
names inside mixed binary input and following Go regexp's malformed-input
semantics.

The native command receives only its inline configuration environment. Competing
scanner configurations, logging overrides and unrelated credentials are not
inherited. `cmd/root.go` can print inline configuration on a parse error despite
redaction, so native stdout, diagnostics and exception values are captured and
never forwarded. Only validated opaque rule IDs and integer line locations leave
the report parser. One candidate snapshot also sanitizes relative file locators.
Private authentication filenames and symbolic links are refused before reading
their bytes or targets. The version probe also receives an empty environment.

`validate.py --scan-file PATH` checks both the existing private-content patterns
and the native runtime names. It emits a status/count JSON record and safe
file:line locators, with exit 0 for a clean input, 1 for findings and 2 for an
unavailable or invalid scan. Repeated paths and findings are deduplicated. The
pre-push hook uses an immutable tip checkout and continues the existing three
registry tests even when the name scan refuses the push. Its temporary checkout
is removed on both success and refusal.

## Evidence and limits

Synthetic native regressions reproduce long records, Unicode neighbors, all
ASCII punctuation pairs, adjacent names, MIME magic, mixed binary/UTF-8 input,
multifile line mapping, config escaping, source failures and safe error output.
Native Git push tests require the planted file's actual locator before accepting
a name refusal, and also cover a clean committed tip despite contaminated local,
untracked and ignored files. Tests inject synthetic candidates; they do not
discover or record real host identities.

The first real all-tracked working-tree precheck reported 32,136 file/line
findings. A controlled source diagnostic found all four Windows system folders
in the candidate set: the ten changed files produced 19 findings, and zero with
those non-personal entries omitted. Microsoft identifies their shared/template/
junction roles. The source regression preserves coincident id/email identities,
and filters only those filesystem entries. The tracked-file selection stays the
same; no delta fallback or finding allowlist is introduced.

The scan checks literal content. Decoding and archive expansion are disabled;
compressed or encrypted content is outside this check. Source, native-process
and report failures refuse the gate. CI cannot substitute for the host-local
check because it cannot hold the real source names. CI installs the immutable
upstream 1.9.0 Linux release with the official asset digest, and the publication
scan uses an explicit synthetic source. Its existing private-content patterns
still check the actual artifact; its synthetic native scan does not establish
real host-name coverage. The test override supports fixtures and is an explicit
local input, with the same trust level as a user's ability to bypass a Git hook.

The current gate selects all tracked files in a committed tip. R25 asks the CC
to confirm that scope or select complete added/modified/renamed files in the
push/PR delta. The adapter's framing and privacy behavior do not depend on that
selection; scope closure and the maintained CC pre-cue integration remain
required before claiming F11 complete.

## SOTA sources

Primary sources checked at the full scanner pin; framing source was fetched on
2026-10-09 at approximately 14:37Z and reproduced with the installed 1.9.0 CLI:

- [Supported native custom rules and Expr filters](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/docs/config.md).
- [Command setup, configuration and diagnostic behavior](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/cmd/root.go).
- [Supported stdin entry point](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/cmd/stdin.go).
- [Native file reads and initial MIME detection](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/sources/file.go).
- [Bounded lookahead and double-newline framing](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/sources/common.go).
- [Byte-column and line location computation](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/detect/location.go).
- [Go regexp UTF-8 and replacement-rune contract](https://pkg.go.dev/regexp).
- [Git pre-push hook protocol](https://git-scm.com/docs/githooks#_pre_push).
- [Immutable Betterleaks 1.9.0 release and official asset digests](https://api.github.com/repos/betterleaks/betterleaks/releases/tags/v1.9.0), fetched 2026-10-09 at approximately 15:08Z; Linux X64 archive SHA256 `f8b185a39ffcece2a1ca82bf3a4e7435cd81963ffd16b7a9128daf75f35f6de7`.
- [Microsoft default profile template](https://learn.microsoft.com/en-us/troubleshoot/windows-client/setup-upgrade-and-drivers/customize-default-local-user-profile), [shared known folders](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid), and [system compatibility junctions](https://learn.microsoft.com/en-us/windows/win32/vss/junction-points), fetched 2026-10-09.

`gitleaks/gitleaks` at `83d9cd684c87d95d656c1458ef04895a7f1cbd8e`
(v8.30.1) was a candidate, but its CLI was absent from this host. No native
Gitleaks result is claimed. Betterleaks supplies the required maintained native
feature and is used through its supported command and configuration interfaces.
