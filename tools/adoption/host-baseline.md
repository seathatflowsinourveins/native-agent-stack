# PR-0 host baseline

`host_baseline_probe.py` is a local integration observer for unit A's credential
guard and agent shell conformance work. It requires Python 3.11 or newer with
stdlib `tomllib` and `ctypes`; no distribution shipping version is inferred. The
coordinator's retained 26.04 artifacts show the original probe completed there,
but do not record the Python or bwrap versions. Its output is
one JSON object. Each observation has `command`, the actual `exit`, sanitized
`output`, and `date_utc` with the command, exit and output of `date -u`. Every
package-query and executable-lookup exit is retained. `dpkg-query -W` can exit 0
for a known but uninstalled package, so its exit is not an installation predicate.
Future package rows contain tab-separated `${binary:Package}`, `${Version}` and
`${db:Status-Status}`; an empty version remains an empty column. The retained
r0 and r1 rows lack the status field, as their receipt metadata states. The
24.04 gdb row has exit 0 and an empty version, while its path lookup exits 1
and its version call exits 127. The bwrap check records
only its exit and discards both streams. Sudo and sudo-rs are never executed.
The other launchers run only `--version`; bwrap runs `true` in new user and PID
namespaces. The updated probe also records gdb identity, bwrap's version and
the time, util-linux, procps, systemd and gdb package versions.

The probe makes no explicit changes to host configuration. Native client startup
can have incidental effects: Codex 0.159.3 attempts PATH-alias creation before
its version output. The 24.04 reference runs in the builder's read-only client
sandbox, which blocks that write. Its diagnostic is retained as `stderr`, while
the Codex version value is the first stdout line only. The coordinator's native
26.04 captures were made outside that sandbox; their lack of a warning does not
prove that client startup made no writes. This repair changes no host installation
or settings; the captures do not guarantee side-effect-free upstream executables.

`host_checkout.output` identifies `~/code/native-agent-stack` independently of
the recorder. The updated `probe.output` object labels its canonical-source hash
`self_reported_canonical_source`, with `executed_input_sha256: null` and
`executed_input_verified: false`. Reconstructing the source envelope cannot
attest bytes consumed by `python3 -`: extra executable wrapper bytes can change
the program without changing that hash. The coordinator must hash the exact
frozen input outside the probe and record it in the receipt.

The retained captures' string-valued `probe.output` hashes are also self-reported,
unverified canonical-source evidence. No external input hash was recorded for
those runs, and receipt amendments do not invent one. The unchanged r0 source
is archived as `evidence/artifacts/host-baseline-20261004/host-baseline-probe-r0.txt`
for both original 26.04 captures. The r1 24.04 source is archived alongside it as
`host-baseline-probe-r1.txt`. Receipts bind those immutable archives, whose
independently computed file hashes match the historical self-reports. They do
not bind the mutable supported entrypoint, and that match is not a transport
attestation.

The passwd record retains field 7 only, and the sudoers marker retains existence,
mode and size only. Its owner column is discarded. Passwordless sudo remains
`unknown`: `adoption/platforms/linux-wsl2-new-distro.md:624` is a recipe criterion,
not a per-host acceptance record. No such acceptance is linked by these receipts.
PR-1 must label root rows `status-unknown` until it has that separate evidence;
neither an absent marker nor a denied stat proves those rows unreachable.

Config files are opened read-only, with symlinks and non-regular files refused.
The selected Codex keys record presence, the `inherit` predicate `is_none`, and
explicit boolean settings where present. Missing keys stay missing; no defaults
are inferred. Claude records only whether `env` has `CLAUDE_CODE_SHELL`. The
probe reads `~/.codex/config.toml` and `~/.claude/settings.json`; it does not
resolve profile overlays, managed settings, project settings or environment
overrides. Parse failures omit exception text to avoid disclosing values.
Single-line, whitespace-free absolute values use stdlib `posixpath.normpath`
before checking membership in the current home, without resolving symlinks.
An absolute value containing a `/`-delimited `..` component on any line fails
closed, including traversal that ends inside the home or ends at a line break.
Only a normalized path equal to the current home, or beginning with that complete
home component followed by `/`, is converted to `~`. Prefix-sharing sibling paths
and embedded home references remain unchanged. For values with whitespace or line
breaks, only a leading complete home prefix is replaced with `~`; the remainder
stays verbatim. The same normalization applies recursively to keys and values.
For homes under `/home/`, remaining home paths anywhere in the document make
the output fail closed. The gate does not compare against the actual home:
embedded references to homes elsewhere can survive unless a profile pattern or
login check matches. The personal-home
and Windows-user-path patterns
copied from `scripts/validate.py` also cover macOS user directories and Windows
profiles, including WSL paths such as `/mnt/c/Users/<login>.HOST/AppData/...`.
They apply to the whole document and do not depend on the current login. Their
reserved `example` placeholder exception is retained; the existing Linux home
prefix check remains stricter and has no placeholder exception.

Login checks inspect observation output and stderr values after casefolding.
They match the login at ASCII alphanumeric boundaries, rejecting compounds such
as `/srv/<login>-data`, `/var/lib/<login>.d`, `<login>.HOST` and `<login>_backup`.
A separate check rejects a numeric trailing suffix such as `<login>123`.
Attached user/group options, including `-u<login>`, `-nu<login>` and `-g<login>`,
are rejected. The complete fixed marker path
`/etc/sudoers.d/90-wsl-default-user` is exempt; a longer lookalike path is checked.
There is no blanket component-prefix exemption.

Before any label exemption, the enumerated raw checks cover `USER=<login>`,
`LOGNAME=<login>`, `--user=<login>`, `-u <login>`, `<login>@`, `~<login>`,
`uid=N(<login>)` and `<login>:x:`. A value consisting only of the login also fails
closed, even when it is a tool name.

Fixed schema keys, command descriptions and selected OS identifiers are not
account identities. An executable's declared basename is excluded while its
parent path is checked. The exact default launcher parent
`~/.local/share/codex-ecosystem/bin` is also a system label in a matching
`command -v` result; arbitrary parent paths remain checked. In its own
`--version` output, the tool-name exemption covers only the leading product
label: an optional `GNU` prefix, the declared tool name or Codex's `codex-cli`
brand, and an immediate parenthesized repetition such as `(GNU Time)` or `(GDB)`.
Claude's numeric version followed by `(Claude Code)` is its leading label.
Any prerelease or build suffix stays in the text checked for login tokens.
Later tool-name words remain checked, including account annotations such as
`gid=N(<login>)`, `--owner <login>` and `Built by <login>`. The OS-release ID is
exempt only in a vendor group immediately following the leading tool label on
the same line. Thus login `claude` accepts `2.1.289 (Claude Code)`, and login
`ubuntu` accepts `GNU gdb (Ubuntu ...)`. Neither exemption erases later account
annotations or crosses from stdout into merged stderr.

In a returned dpkg row matching the queried package, a distribution tag followed
by digits inside a numeric version is also a label: for example, `~ubuntu25` in
`0.0.0~ubuntu25`. Checking exemptions do not change the recorded values. The
boundary rule deliberately accepts a login embedded within a longer ASCII word
or preceded by a letter/digit, preserving `fixture-userland` for login `user`
and `1ubuntu2` for login `ubuntu`. This is weaker than r1's arbitrary substring
check because those fragments are system/package labels; punctuation compounds
and trailing numeric-only suffixes remain checked.
A detected disclosure returns exit 3 with empty stdout and stderr, including with
`python3 -O`. Every exception in `main()`
is caught and returns the same silent exit 3, including unexpected identity,
filesystem and decoding errors.

## Record from NativeStack

Preserve the complete JSON artifact and write a plain `kind: host_baseline`
receipt under `evidence/receipts/`, with `id`, `claim`, `limitations`,
`recorded_at_utc`, `host`, `evidence_class: local_integration`, and `artifacts`
containing relative paths and independently computed SHA256s. Bind the
observation and an immutable archive of the input source. For future captures,
record the coordinator's external input measurement as
`probe_identity.executed_input_sha256`, with basis `coordinator_input_bytes`;
the probe's self-report remains unverified. No client version is typed into an
acceptance receipt. These
component-free receipts are hash-listed evidence files, outside the component
acceptance index. Their host observation exits remain in the full artifacts.

Use the existing NativeStack identity `nativestack-5975wx-20260925` for the 24.04
reference. The same distribution must not be presented as another physical host.
For a future capture, freeze the source before hashing or running it. Use a new
capture directory and receipt instead of replacing a retained historical capture.
The following local recipe hashes the exact archived bytes it sends on stdin;
`sha256sum` runs on the coordinator side and prints a digest with `-`, without a
private source path. Put that digest in the new receipt as the input measurement:

```bash
set -e
nice -n 19 mkdir -p "$HOME/.cache/t710t"
export TMPDIR="$HOME/.cache/t710t"
capture_dir="evidence/artifacts/host-baseline-<capture-id>"
nice -n 19 mkdir "$capture_dir"
probe_input="$capture_dir/probe-source.txt"
nice -n 19 cp tools/adoption/host_baseline_probe.py "$probe_input"
nice -n 19 chmod 0444 "$probe_input"
nice -n 19 sha256sum < "$probe_input"
nice -n 19 python3 - < "$probe_input" > "$capture_dir/nativestack-2404.json"
```

On this host `wsl.exe` is not on PATH. Invoking the executable directly with
`-- python3 -` also omits the user's login-shell PATH, causing installed clients
to appear absent. The coordinator's command for the two r0 26.04 captures
(repair round r1) was
`nice -n 19 /mnt/c/Windows/System32/wsl.exe -d <name> -- bash -lc 'nice -n 19 python3 -' < tools/adoption/host_baseline_probe.py`.
For future captures, use the same login shell agents use with the frozen input
above and measure its hash on the coordinator side before sending it:

```bash
nice -n 19 sha256sum < "$probe_input"
nice -n 19 /mnt/c/Windows/System32/wsl.exe -d <name> -- bash -lc 'nice -n 19 python3 -' < "$probe_input" > "$capture_dir/<host-id>.json"
```

This sends the same probe bytes on stdin and needs no target checkout. The target
host's checkout HEAD, including an older checkout, remains a separate field.
The coordinator schedules StackMeasure2604 within its owner's measurement window
and captures stdout to the corresponding artifact. The builder does not invoke
another distribution. The supplied NativeStack2604 capture is after F9 apply at
2026-10-05T01:02:27Z; StackMeasure2604 was captured at 01:02:53Z-01:02:54Z
on the same UTC date. The artifacts retain the
exact per-field UTC times. They use the archived r0 source and lack the repair's
additional gdb, launcher-package and bwrap-version observations; those fields
remain unobserved on both 26.04 hosts. Retain their original bytes and hashes.

The three host receipts and the historical coreutils sidecar are
`evidence/receipts/host-baseline-*-20261004.json`. Their `recorded_at_utc` stamps
date initial receipt assembly; observation and upgrade times stay in the bound
artifacts. Later metadata corrections are dated separately by
`amendments[].amended_at_utc`, obtained from `date -u`. Each amendment names its
review reference and changed fields, retaining prior values for rewritten fields.
The t2 entries retrospectively document the t1 corrections; their stamps date
the amendment entries, not the earlier t1 edits or a new host observation.
The coreutils sidecar names NativeStack2604 and the three historical coordination
source files, and states that no upgrade was re-executed. Its evidence class is
the policy's `Independent observation` for inspection of native histories,
rather than `local_integration`. This plain receipt is outside the component
host-receipt schema's three-class enum. StackMeasure2604's
current coreutils version is supported by its own retained probe artifact.
Register the artifact and all other changed evidence files after finishing them with
`scripts/host_receipts.py`'s `register_file(Path("."), relative_path)` function.
The evidence manifest does not register its own bytes.

## Sources

- Repository reference `3b8f9c8a1b938358d65bf422f61592dc3b89407d`:
  `scripts/host_receipts.py` (`register_file`), `docs/contributing-evidence.md`,
  `docs/acceptance-evidence-policy.md`, and the plain receipt style in
  `blueprints/us-equities/catalyst-provenance/new-host-native-network-20260924.json`.
- Repair reference `68ed2b16045e66599f8a1fa2933adb5f1d6f5a0f`:
  `docs/acceptance-evidence-policy.md` (Independent observation),
  `docs/contributing-evidence.md` and `adoption/host-receipt.schema.json`
  (component host-receipt classes), `scripts/validate.py` (`RECEIPT_KINDS`
  applies to indexed component receipts), and the plain observation-class
  precedent `evidence/receipts/github-ci-measurements-20261003.json`.
- Delta repair reference `d06098ffb070dacfcbc9a424874de989cb55c8db`:
  `scripts/validate.py:29-30` supplies the unchanged personal-home and
  Windows-user-path patterns; the three committed host artifacts supply the
  Claude version-banner fixtures. No host is recaptured to test those banners.
- Privacy repair reference `22ec2b15419cb5f508976bac586aece72c3a7a3b`:
  `scripts/adoption_status.py:1124-1134` defines the default launcher root; the
  committed 26.04 package rows retain `coreutils-from-uutils 0.0.0~ubuntu25`.
  Replaying those captures supplies the scoped system-label controls.
- Structural privacy repair reference `ce2c11ba0382e9d227f241669f20094a4490edaa`:
  the probe's normalization and version-label checks supply the before-fix code;
  the committed 24.04 artifact supplies the time, script, watch, find and env
  banners. Tests cover all three captures with all five common-login controls.
- Installed `dpkg-query --help` and `dpkg-query(1)` at
  `/usr/share/man/man1/dpkg-query.1.gz`: `-W` reports package information,
  `-f` selects fields, and `db:Status-Status` supplies the package status word.
- [Python 3.12 tomllib](https://docs.python.org/3.12/library/tomllib.html) and
  [subprocess](https://docs.python.org/3.12/library/subprocess.html): unchanged
  stdlib parsers and native exit capture. The probe is local glue using these
  interfaces, not an upstream acceptance test.
- [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference),
  verified against installed 0.159.3 and
  [rust-v0.159.3 configuration source](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/config/src/config_toml.rs#L218),
  [environment policy](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/protocol/src/shell_environment.rs#L100),
  and [feature names](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/features/src/lib.rs#L1012).
- [Codex 0.159.3 startup source](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/arg0/src/lib.rs#L166):
  PATH-alias setup precedes CLI entry; alias creation failures produce the
  separate warning captured by the local sandbox observation.
- [Claude Code v2.1.289 changelog](https://github.com/anthropics/claude-code/blob/v2.1.289/CHANGELOG.md#L7127):
  key existence observation only.
- [Linux Landlock ABI query](https://www.kernel.org/doc/html/latest/userspace-api/landlock.html):
  `syscall(444, NULL, 0, LANDLOCK_CREATE_RULESET_VERSION=1)` queries support and
  does not create a ruleset or apply a restriction.
- [bubblewrap v0.9.0 source](https://github.com/containers/bubblewrap/blob/v0.9.0/bubblewrap.c#L316):
  unit A's 24.04 version observation and the documented namespace, bind and proc options; the probe's
  command runs `true` and records its exit only.

The canonical-source self-report, final privacy gate and fixture tests are repository
integration code using the cited stdlib and native interfaces.
