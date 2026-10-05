# PR-0 host baseline

`host_baseline_probe.py` is a local integration observer for unit A's credential
guard and agent shell conformance work. It requires Python 3.11 or newer with
stdlib `tomllib` and `ctypes`; no distribution shipping version is inferred. The
coordinator's retained 26.04 artifacts show the original probe completed there,
but do not record the Python or bwrap versions. Its output is
one JSON object. Each observation has `command`, the actual `exit`, sanitized
`output`, and `date_utc` with the command, exit and output of `date -u`. Package
and executable absence retain their nonzero native exits. The bwrap check records
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

The `probe.output` SHA256 identifies the recorder bytes, while
`host_checkout.output` identifies `~/code/native-agent-stack` independently.
The Python source envelope keeps the probe bytes available even after `python3 -`
consumes stdin. File execution checks the envelope against the actual file; tests
compare both execution forms with the file's independently calculated SHA256.
Receipts also bind the independently hashed source file. The unchanged r0 source
is archived as `evidence/artifacts/host-baseline-20261004/host-baseline-probe-r0.txt`
for the two original 26.04 captures; it is evidence, not the supported entrypoint.

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
Home paths are normalized to `~`. Remaining home paths or the account's login
name, case-insensitively, make the complete output fail closed with exit 3 and
empty stdout and stderr, including with `python3 -O`. Every exception in `main()`
is caught and returns the same silent exit 3, including unexpected identity,
filesystem and decoding errors.

## Record from NativeStack

Preserve the complete JSON artifact and write a plain `kind: host_baseline`
receipt under `evidence/receipts/`, with `id`, `claim`, `limitations`,
`recorded_at_utc`, `host`, `evidence_class: local_integration`, and `artifacts`
containing relative paths and independently computed SHA256s. Bind both the
observation and actual source bytes, then compare the source hash with
`probe.output`. No client version is typed into an acceptance receipt. These
component-free receipts are hash-listed evidence files, outside the component
acceptance index. Their host observation exits remain in the full artifacts.

Use the existing NativeStack identity `nativestack-5975wx-20260925` for the 24.04
reference. The same distribution must not be presented as another physical host.
The local collection command is:

```bash
mkdir -p "$HOME/.cache/t-pr0-baseline-r1"
export TMPDIR="$HOME/.cache/t-pr0-baseline-r1"
nice -n 19 python3 - < tools/adoption/host_baseline_probe.py > evidence/artifacts/host-baseline-20261004/nativestack-2404.json
```

On this host `wsl.exe` is not on PATH. Invoking the executable directly with
`-- python3 -` also omits the user's login-shell PATH, causing installed clients
to appear absent. The coordinator's documented and used command runs the probe
in the login shell agents use:

```bash
nice -n 19 /mnt/c/Windows/System32/wsl.exe -d <name> -- bash -lc 'nice -n 19 python3 -' < tools/adoption/host_baseline_probe.py
```

This sends the same probe bytes on stdin and needs no target checkout. The target
host's checkout HEAD, including an older checkout, remains a separate field.
The coordinator schedules StackMeasure2604 within its owner's measurement window
and captures stdout to the corresponding artifact. The builder does not invoke
another distribution. The supplied NativeStack2604 capture is after F9 apply at
01:02Z; StackMeasure2604 was captured around 01:03Z. The artifacts retain the
exact per-field UTC times. They use the archived r0 source and lack the repair's
additional gdb, launcher-package and bwrap-version observations; those fields
remain unobserved on both 26.04 hosts. Retain their original bytes and hashes.

The three host receipts and the historical coreutils sidecar are
`evidence/receipts/host-baseline-*-20261004.json`. Their `recorded_at_utc` stamps
date receipt assembly; observation and upgrade times stay in the bound artifacts.
The coreutils sidecar names NativeStack2604 and the three historical coordination
source files, and states that no upgrade was re-executed. StackMeasure2604's
current coreutils version is supported by its own retained probe artifact.
Register the artifact and all other changed evidence files after finishing them with
`scripts/host_receipts.py`'s `register_file(Path("."), relative_path)` function.
The evidence manifest does not register its own bytes.

## Sources

- Repository reference `3b8f9c8a1b938358d65bf422f61592dc3b89407d`:
  `scripts/host_receipts.py` (`register_file`), `docs/contributing-evidence.md`,
  `docs/acceptance-evidence-policy.md`, and the plain receipt style in
  `blueprints/us-equities/catalyst-provenance/new-host-native-network-20260924.json`.
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

The source envelope, final privacy gate and fixture tests are repository
integration code using the cited stdlib and native interfaces.
