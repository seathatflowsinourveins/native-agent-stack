# PR-0 host baseline

`host_baseline_probe.py` is a read-only local integration observer for unit A's
credential guard and agent shell conformance work. It uses Python 3.11 or newer
and the standard library already shipped on Ubuntu 24.04 and 26.04. Its output is
one JSON object. Each observation has `command`, the actual `exit`, sanitized
`output`, and `date_utc` with the command, exit and output of `date -u`. Package
and executable absence retain their nonzero native exits. The bwrap check records
only its exit and discards both streams. No privilege launcher is executed.

The `probe.output` SHA256 identifies the recorder bytes, while
`host_checkout.output` identifies `~/code/native-agent-stack` independently.
The Python source envelope keeps the probe bytes available even after `python3 -`
consumes stdin. File execution checks the envelope against the actual file; tests
compare both execution forms with the file's independently calculated SHA256.

The passwd record retains field 7 only, and the sudoers marker retains existence,
mode and size only. Its owner column is discarded. The recipe's acceptance
record at `adoption/platforms/linux-wsl2-new-distro.md:624` is the other source for
passwordless operation; this probe does not establish that capability.

Config files are opened read-only, with symlinks and non-regular files refused.
The selected Codex keys record presence, the `inherit` predicate `is_none`, and
explicit boolean settings where present. Missing keys stay missing; no defaults
are inferred. Claude records only whether `env` has `CLAUDE_CODE_SHELL`. The
probe reads `~/.codex/config.toml` and `~/.claude/settings.json`; it does not
resolve profile overlays, managed settings, project settings or environment
overrides. Parse failures omit exception text to avoid disclosing values.
Home paths are normalized to `~`. Remaining home paths or the account's login
name, case-insensitively, make the complete output fail closed with exit 3 and
empty stdout and stderr, including with `python3 -O`.

## Record from NativeStack

`scripts/host_receipts.py record` executes commands locally and has no probe JSON
import subcommand. Use its supported `--cmd` interface. Preserve the complete
JSON as an artifact: the standard receipt's output excerpt is limited to 400
characters. The example below creates the local 24.04 reference. The existing
`claude-code` component anchors the receipt with the observed installed version;
`local_integration` and `stage=install` describe the observation and do not
qualify a guard, model run or functional client workload.

```bash
mkdir -p .tmp-build/host-baseline evidence/artifacts/host-baseline-20261004
export TMPDIR="$PWD/.tmp-build/host-baseline"
identity="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
cmd=$(cat <<'CMD'
nice -n 19 python3 - < tools/adoption/host_baseline_probe.py > evidence/artifacts/host-baseline-20261004/nativestack-2404.json
probe_exit=$?
if [ "$probe_exit" -ne 0 ]; then
    exit "$probe_exit"
fi
python3 -c 'import hashlib, json; from pathlib import Path; p=Path("evidence/artifacts/host-baseline-20261004/nativestack-2404.json"); data=json.loads(p.read_text()); print(json.dumps({"artifact":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"probe_sha256":data["probe"]["output"]},separators=(",",":")))'
CMD
)
nice -n 19 python3 scripts/host_receipts.py record \
  --host-id nativestack-2404-20261004 --platform-id linux-wsl2-x86_64 \
  --component-id claude-code --component-version 2.1.289 \
  --allow-unbound-version --stage install --evidence-class local_integration \
  --identity "$identity" --timeout 180 \
  --claim 'Read-only native PR-0 host baseline; the full probe output is in the artifact named by the command excerpt.' \
  --limitation 'Individual probe failures and absences are retained in the artifact; recorder success means collection completed.' \
  --limitation 'Version and settings observation only; no credential access, guard replay, model workload or passwordless operation was exercised.' \
  --cmd "$cmd"
```

Inside a Claude session omit `--identity` and its token generation, as documented
by the native receipt CLI. A nonzero probe exit is preserved without a pipeline
masking it. The excerpt binds the full published artifact hash and probe hash.

For each 26.04 host the coordinator substitutes the host id, installed client
version and artifact filename, and replaces the first command in `cmd` with:

```bash
nice -n 19 wsl.exe -d <name> -- nice -n 19 python3 - < tools/adoption/host_baseline_probe.py > evidence/artifacts/host-baseline-20261004/<host-id>.json
```

This sends the same probe bytes on stdin and needs no target checkout. The target
host's checkout HEAD, including an older checkout, remains a separate field.
The coordinator schedules StackMeasure2604 within its owner's measurement window.
The recorder runs from NativeStack, so its standard `catalog_revision` describes
that checkout and its standard recording timestamp describes collection there;
the JSON artifact carries every target observation's timestamp. Register the
artifact and all other changed evidence files after finishing them with
`scripts/host_receipts.py`'s `register_file(Path("."), relative_path)` function.
The evidence manifest does not register its own bytes.

## Sources

- Repository reference `3b8f9c8a1b938358d65bf422f61592dc3b89407d`:
  `scripts/host_receipts.py` (`record`, `run_command`, `register_file`),
  `adoption/host-receipt.schema.json`, `docs/contributing-evidence.md`, and
  `docs/acceptance-evidence-policy.md`.
- [Python 3.12 tomllib](https://docs.python.org/3.12/library/tomllib.html) and
  [subprocess](https://docs.python.org/3.12/library/subprocess.html): unchanged
  stdlib parsers and native exit capture. The probe is local glue using these
  interfaces, not an upstream acceptance test.
- [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference),
  verified against installed 0.159.3 and
  [rust-v0.159.3 configuration source](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/config/src/config_toml.rs#L218),
  [environment policy](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/protocol/src/shell_environment.rs#L100),
  and [feature names](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/features/src/lib.rs#L1012).
- [Claude Code v2.1.289 changelog](https://github.com/anthropics/claude-code/blob/v2.1.289/CHANGELOG.md#L7127):
  key existence observation only.
- [Linux Landlock ABI query](https://www.kernel.org/doc/html/latest/userspace-api/landlock.html):
  `syscall(444, NULL, 0, LANDLOCK_CREATE_RULESET_VERSION=1)` queries support and
  does not create a ruleset or apply a restriction.
- [bubblewrap v0.9.0 source](https://github.com/containers/bubblewrap/blob/v0.9.0/bubblewrap.c#L316):
  installed 0.9.0, the documented namespace, bind and proc options; the probe's
  command runs `true` and records its exit only.

The source envelope, final privacy gate and fixture tests are repository
integration code. Broader inventory tools or package dependencies would add
unneeded information and deployment requirements to this fixed field contract.
