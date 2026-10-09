# Runtime host-local name checks

F11 uses the installed Betterleaks 1.9.0 scanner for host-local bare names. The
scanner source is `betterleaks/betterleaks` at
`81aff7a638638aae3a659845d089043e1d8fe9ac`. Runtime names come from `id -un`,
`uname -n`, the Windows computer name, personal profile directories under
`/mnt/c/Users`, and the effective private Git email local part. When that mount
is absent, the native Windows `Win32_UserProfile` source supplies profile names.
If the Linux hostname equals `WSL_DISTRO_NAME` ignoring case, that public distro identifier is
excluded from the hostname source only; coincident private identity, profile and
email sources remain. Windows source commands request UTF-8 console output and
have a 30-second subprocess timeout. Email values without `@` remain private
literal sources.
GitHub's documented `users.noreply.github.com` identities are public commit
identities and are excluded from the email source; coincident user/profile/host
sources remain active. Windows' shared `Public` folder, `Default` template, and `All Users` /
`Default User` compatibility junctions are not personal profile names and are
excluded from that filesystem source. The identity and email sources retain their
values even if those values coincide with a system-folder name. The synthetic-only
`NATIVE_AGENT_HOST_NAMES_JSON` override replaces
all runtime sources for tests. Candidates and native configuration stay in process
memory. Nothing registers or prints the candidate list.

The adapter generates supported native custom rules with escaped, case-insensitive
literal regexes. Betterleaks Expr filters exclude matches next to Unicode letters
or numbers; punctuation and literal newline/tab/carriage-return escapes remain
valid bare-name boundaries. Native decoding uses the upstream depth-5 default.
The adapter performs
source collection, input framing, subprocess isolation and location mapping. It
does not implement matching or Unicode boundary checks.

## Native framing and privacy

The pinned `sources/file.go` reads 100,000-byte chunks. `sources/common.go` adds
at most 25,000 bytes while seeking a double-newline boundary, without overlap.
Passing an arbitrary long original record directly can therefore lose a match
or its neighbor context at a chunk boundary. Rejecting every long record also
prevents a clean repository tip from passing its gate.

Each original line becomes bounded records of at most 4,096 Unicode code points,
separated by double newlines. Overlap covers a complete candidate in a single
native percent/Unicode encoding and both neighbor characters; sources exceeding
that framing capacity refuse rather than silently losing coverage. Artificial
edges receive alphanumeric guards. Native Expr
filters discard matches that consume those guards, and only admit content
records; the initial text prefix cannot become a finding. This preserves native
boundary decisions while mapping every retained record back to the original
file and line. Malformed UTF-8 becomes replacement runes, preserving valid UTF-8
names inside mixed binary input and following Go regexp's malformed-input
semantics.
Raw U+001E and U+001F are replaced with U+FFFD before framing so original content
cannot impersonate the internal record markers. A two-line native probe proves
names following either raw control character still receive their original lines.

The native command receives only its inline configuration environment. Competing
scanner configurations, logging overrides and unrelated credentials are not
inherited. `cmd/root.go` can print inline configuration on a parse error despite
redaction, so native stdout, diagnostics and exception values are captured and
never forwarded. Only validated opaque rule IDs and integer line locations leave
the report parser. Native git mode also receives only its inline configuration
and a system executable path. One candidate snapshot sanitizes relative file locators.
Correction from the micro-read: the upstream `cmd/root.go:464-469` also loads an
ignore file from its source directory regardless of `--gitleaks-ignore-path`.
The repository's existing native ignore fingerprints therefore apply. The flag
does not promise to bypass source-directory ignores; no custom upstream fork or
ignore-file rewrite is introduced by this change.
Private authentication filenames and symbolic links are refused before reading
their bytes or targets. The version probe also receives an empty environment.

`validate.py --scan-file PATH` checks both the existing private-content patterns
and the native runtime names. It emits a status/count JSON record and safe
file:line locators, with exit 0 for a clean input, 1 for findings and 2 for an
unavailable or invalid scan. JSON identifies `source: host|synthetic`, and a
synthetic override also prints an explicit notice. `matching_locations` counts
distinct masked file:line locations, so two matches on one line do not masquerade
as one individual match. Repeated paths and locations are deduplicated.

The pre-push hook scans all tracked bytes at the immutable tip, plus each ref's
`remote_oid..local_oid` history through native Betterleaks git mode. New refs scan
commits absent from remote refs. An added-then-removed name is therefore refused.
The same private list checks each pushed commit's author/committer names and
emails, with only masked metadata locators reported. Every ref's range is checked
even when tips coincide; registry tests remain once per tip. Git's documented
repository-local variables are cleared inside the scanner/test subshells so a
linked worktree's pushing index cannot replace the immutable checkout. Registry
tests continue when scanning refuses, and the checkout is removed on success or
refusal.
Fallback errors identify the host/synthetic source and use `scanned_files: null`
when the scanner could not determine a count.

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

Native percent, Unicode, hex and base64 decoder measurements confirm that the
record markers and artificial guards survive decoding. The opening-record filter
admits decoded newline characters while preserving the guard checks. Native
codec limits remain: hex runs need at least 32 characters, and base64 runs need
at least 16 non-padding characters plus the vendor's likely-character heuristic.
Shorter opaque encodings, or larger nested encoding spans crossing framed
records, are outside the measured native detection guarantee. Archive
expansion is disabled; compressed or encrypted content is outside this check. Source, native-process
and report failures refuse the gate. CI cannot substitute for the host-local
check because it cannot hold the real source names. CI installs the immutable
upstream 1.9.0 Linux release after the existing Sigstore/cosign signed-checksum
verification and official asset digest check. The publication
scan uses an explicit synthetic source. Its existing private-content patterns
still check the actual artifact; its synthetic native scan does not establish
real host-name coverage. The test override supports fixtures and is an explicit
local input, with the same trust level as a user's ability to bypass a Git hook.

Correction from the CC's real-host read: the seven frozen historical report
locations contained only the public GitHub no-reply email local part, not a
private user/profile name. Excluding that public-only source fixes the refusal
without modifying the frozen artifact. The current gate keeps the all-tracked
tip scan and adds pushed history and identity metadata. The maintained CC
pre-cue integration remains CC-owned; publication, review and its activation
remain distinct from the native host run.

The CC's second host read separated the public distro hostname from the genuine
Windows computer source. A source-specific equality exclusion addresses the
public identifier. The two named current-tree files contained three bare
computer-name references, which are now masked; a longer ordinary task-name
substring is preserved. Original historical execution claims stay unchanged;
their publication metadata is rehashed after this privacy correction.

Remaining measured-scope limits from the micro-read: commit messages, annotated
tag contents and ref names are not scanned; metadata checks cover author and
committer names/emails. Native Git scanning skips non-archive binary blobs and
uses its default merge-diff behavior. New refs exclude commits reachable from
all local remote-tracking refs, rather than only the push destination. ANSI,
hex/octal/backspace/NUL delimiter escape coverage is not claimed by the current
boundary exception. These remain declared P3 scope items, not passing tests.

## SOTA sources

Primary sources checked at the full scanner pin; framing source was fetched on
2026-10-09 at approximately 14:37Z and reproduced with the installed 1.9.0 CLI:

- [Supported native custom rules and Expr filters](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/docs/config.md).
- [Command setup, configuration and diagnostic behavior](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/cmd/root.go).
- [Supported stdin entry point](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/cmd/stdin.go).
- [Native file reads and initial MIME detection](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/sources/file.go).
- [Bounded lookahead and double-newline framing](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/sources/common.go).
- [Byte-column and line location computation](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/detect/location.go).
- [Native decoded filter context and original finding locations](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/detect/detect.go), [decoder and original-range mapping](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/detect/codec/decoder.go), and [codec recognition limits](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/detect/codec/encodings.go), reproduced with synthetic fixtures on 2026-10-09.
- [Native Git source and log options](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/sources/git.go) and [Git entry point](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/cmd/git.go).
- [GitHub public no-reply email formats](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address).
- [Native PowerShell CIM command](https://learn.microsoft.com/en-us/powershell/module/cimcmdlets/get-ciminstance) and [Windows profile source](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/userprofileprov/win32-userprofile).
- [Go regexp UTF-8 and replacement-rune contract](https://pkg.go.dev/regexp).
- [Git pre-push hook protocol](https://git-scm.com/docs/githooks#_pre_push).
- [Python direct source-file loading](https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly): the isolated hook preloads its exact scanner file into the module cache rather than adding the entire scripts directory to an import path. The existing resolver traces inline file loaders as file dependencies; its direct-script directory rule is retained.
- [GitHub same-repository action syntax, 2026-07-30](https://github.blog/changelog/2026-07-30-reference-same-repository-actions-with-self-repository-syntax/): `$/` binds the local composite action to the exact running workflow commit. Native zizmor1.30.1 accepts this form; the observed hosted runner2.337.0 exceeds the2.336.0 minimum. Existing workflow inventory tests recognize the supported syntax. The installer appends a literal trusted `runner.temp` path, preserving its pinned/signature checks.
- [Immutable Betterleaks 1.9.0 release and official asset digests](https://api.github.com/repos/betterleaks/betterleaks/releases/tags/v1.9.0), fetched 2026-10-09 at approximately 15:08Z; Linux X64 archive SHA256 `f8b185a39ffcece2a1ca82bf3a4e7435cd81963ffd16b7a9128daf75f35f6de7`.
- [Signed checksum bundle](https://github.com/betterleaks/betterleaks/releases/download/v1.9.0/checksums.txt.sigstore.json) and [pinned release signing configuration](https://github.com/betterleaks/betterleaks/blob/81aff7a638638aae3a659845d089043e1d8fe9ac/.goreleaser.yml). The signer is the tag's release workflow with GitHub OIDC, the pinned commit and push trigger. The installer reuses this repository's existing cosign 3.0.6 bootstrap and verification pattern.
- [Microsoft default profile template](https://learn.microsoft.com/en-us/troubleshoot/windows-client/setup-upgrade-and-drivers/customize-default-local-user-profile), [shared known folders](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid), and [system compatibility junctions](https://learn.microsoft.com/en-us/windows/win32/vss/junction-points), fetched 2026-10-09.

`gitleaks/gitleaks` at `83d9cd684c87d95d656c1458ef04895a7f1cbd8e`
(v8.30.1) was a candidate, but its CLI was absent from this host. No native
Gitleaks result is claimed. Betterleaks supplies the required maintained native
feature and is used through its supported command and configuration interfaces.
