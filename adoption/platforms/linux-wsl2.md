# Linux/WSL2 x86_64 — status: accepted

## Get the catalog

Clone the catalog and check out its attested release tag before running any
step below (see [`adoption/bootstrap.md`](../bootstrap.md) step 0 for the
full detail, including `gh attestation verify` for a downloaded release
archive):

```sh
git clone https://github.com/seathatflowsinourveins/native-agent-stack.git
cd native-agent-stack
python3 scripts/release_due.py   # on the default branch: steps main documents that the pinned release lacks
tag="$(python3 -c "import json;print(json.load(open('adoption/manifest.json'))['source']['release_tag'])")"
commit="$(python3 -c "import json;print(json.load(open('adoption/manifest.json'))['source']['release_commit'])")"
git checkout "$tag"
if test "$(git rev-parse HEAD)" = "$commit"; then echo "at $tag ($commit)"; else echo "error: $tag is not the pinned release commit $commit" >&2; false; fi
```

That checkout target is `adoption/manifest.json` `source.release_tag` (or a
later tag), confirmed at `source.release_commit` and published with SLSA
build provenance by `.github/workflows/publish-catalog.yml`. Read both values
before the checkout, as above: the release's own manifest names the release
before it, so `scripts/release_due.py` runs on the default branch. Do
**not** check out `source.baseline_commit`: that field predates `adoption/`
and `tools/adoption/` entirely and is never a checkout target (Codex
cross-family review finding, `codex-review-72`; `codex-review-64` is the
separate promotion-gate cross-family review finding);
[`scripts/adoption_status.py`](../../scripts/adoption_status.py) uses
`baseline_commit` only as the comparison point for its
`baseline_matches`/`baseline_differs` `git` result, never as something a
reader should check out.

`platform_profiles` entry `linux-wsl2-x86_64` in [`adoption/manifest.json`](../manifest.json),
evidence at [`adoption/receipt.json`](../receipt.json). This is the initial and
only accepted target platform; `adoption/manifest.json` `supported_platforms`
stays Linux/x86_64/Python 3.13 only (see
[`adoption/README.md`](../README.md), "The initial target is Linux/WSL2
x86_64").

## What is accepted here

[`adoption/receipt.json`](../receipt.json) records native uv 0.12.17
recreating all 36 accepted SDK distributions in a fresh
Linux/Python 3.13.15 prefix on the existing WSL host, exact
name/version match after an uncached reinstall, and useful local SDK/data
checks passing; Codex required sign-in on first inspection and passed
discovery/allowance checks after native device sign-in. This is a fresh
prefix on the existing host, not a second physical machine — the receipt's
own `scope.second_physical_machine` is `false`.

[`docs/portable-userspace-install-20260921.md`](../../docs/portable-userspace-install-20260921.md)
additionally qualified pinned Claude/Codex installation, four token tools and
two ECC skills inside a fresh official Ubuntu Base 24.04.5 filesystem on the
existing WSL kernel: the unchanged token fixture runner passed 41 native
commands and 14 semantic checks, with repeat-install, overwrite-protection and
rollback checks passing in scope. That page's own boundary applies here too:
fresh Linux userspace on the existing WSL kernel is not a booted new PC, an
independent kernel, or a full-foundation deployment.

## vLLM pin: 0.30.0 (0.29.0 fails on WSL)

The working WSL vLLM pin is **0.30.0** since 2026-09-25
([`evidence/receipts/vllm-030-switch-20260925.json`](../../evidence/receipts/vllm-030-switch-20260925.json)).
0.30.0 carries the pinned-memory fallback for WSL (vllm-project/vllm PR
#56908) and closes GHSA-25q3-v2hm-8vpf and GHSA-5fj9-pfhr-6j48. On the
NativeStack RTX 4090 host it served the same Nemotron-3-Embed-1B-BF16 files
with embeddings and code-index results identical to 0.25.0, first on an
owned instance and then in production; 0.25.0 stays installed for rollback.
Version **0.29.0 failed real startup with "UVA is not available"** on this
WSL GPU path (unified virtual addressing unsupported by the WSL GPU driver
surface at that release).
[`adoption/lifecycle.md`](../lifecycle.md) records this exactly: "The working
WSL vLLM pin remains 0.25.0. Version 0.29.0 failed real startup with
unavailable UVA support. Preserve the accepted environment and model/vector
data; repeating installation until the version number is newer would not
resolve that compatibility failure." Do not bump this pin on a new WSL host
without first re-testing 0.29.0 (or any newer release) startup on that host's
actual GPU/driver combination; a newer upstream version number is not by
itself evidence the WSL UVA gap closed.

## Ordered steps for a new Linux/WSL2 host

1. Follow [`adoption/bootstrap.md`](../bootstrap.md) steps 1–3 (prerequisites,
   `bootstrap-linux.sh --profile <id>`, native sign-in).
   `adoption/bootstrap-linux.sh` and its `claude-code` pin
   changed after `v2026.09.24.1`: at that tag the pin is 2.1.280 and the
   script reinstalls it even over a newer Claude Code, so a re-run
   downgrades a native auto-updated install. On main the pin is 2.1.281 and a floor: the script
   keeps a `~/.local/bin/claude` whose `--version` reports 2.1.281 or newer
   (logging `Kept installed claude-code <version>`, with nothing downloaded
   or installed) and runs the checksum-verified install only when that
   launcher is missing, older or unreadable.
   Its version report changed after `v2026.09.24.1`: that release, and
   every earlier one, runs `--version` on every file in
   `$ECO_INSTALL_ROOT/bin` and blocks on `context-mode`, which serves MCP on
   stdin instead, so run such a release's script with `</dev/null` (step 2 of
   [`adoption/bootstrap.md`](../bootstrap.md) has the details and the
   `mcp-inspector` case).
2. Recreate the SDK only for the `research-runtime` profile using
   [`adoption/sdk/README.md`](../sdk/README.md)'s transitive lock; retain the
   same exact-match and uncached-reinstall checks as
   [`adoption/receipt.json`](../receipt.json).
3. Render configs with [`tools/adoption/render_config.py`](../../tools/adoption/render_config.py)
   (`adoption/bootstrap.md` step 4) using this host's own
   `adoption/hosts/<host>.json`.
4. Start selected `systemd --user` units per
   [`adoption/lifecycle.md`](../lifecycle.md#native-client-integration-and-process-lifecycle);
   never stop the shared MCPorter daemon to clean up another component.
5. Run `uv run --no-project --python 3.13 python scripts/adoption_status.py --profile <id> --json` (changed after
   `v2026.09.23.1`, which runs plain `python3`: Ubuntu 24.04's `python3` is 3.12,
   which the manifest does not support; run this form there too) and record
   the per-host receipt (`adoption/bootstrap.md` steps 6–7).
6. Contribute what ran: record host receipts with `scripts/host_receipts.py`
   from a branch of current `main`, refresh the generated matrix and grand
   list, and open a PR, following
   [`docs/contributing-evidence.md`](../../docs/contributing-evidence.md).
7. When a newer release is pinned, follow
   [moving a host to a new release](../update.md#moving-a-host-to-a-new-release).

## Windows-side commands from WSL

Lessons from work on the WSL workstation in September 2026; the links give the
upstream behavior behind each.

- Do not pipe a script to `powershell.exe -Command -`. PowerShell reads
  standard input one statement at a time, as if typed at the prompt, and does
  not run a statement that fails to parse
  ([about_PowerShell_exe](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_powershell_exe?view=powershell-5.1)),
  so a multi-line block can be dropped without an error. Write a `.ps1` file
  and run it with
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w file.ps1)"`.
- Strip `\r` and `\0` from Windows-side output before comparing or parsing it,
  for example with `tr -d '\r\0'`. Windows programs end lines with CRLF, and
  `wsl.exe` writes UTF-16 unless `WSL_UTF8=1` is set
  ([`WslClient.cpp` at 2.7.14](https://github.com/microsoft/WSL/blob/2.7.14/src/windows/common/WslClient.cpp#L1843-L1852)).
- `Get-ChildItem -Filter 'name.*'` also matches an extensionless `name`: the
  filter follows Win32 wildcard rules, in which `.*` also matches no extension
  ([.NET `FileSystemName`](https://github.com/dotnet/runtime/blob/v10.0.0/src/libraries/System.Private.CoreLib/src/System/IO/Enumeration/FileSystemName.cs#L139)).
  Before any `Remove-Item`, select with `-LiteralPath` or an exact list of
  names and print that list. `Remove-Item` deletes permanently; it does not use
  the Recycle Bin
  ([PowerShell#6801](https://github.com/PowerShell/PowerShell/issues/6801)).
- A long script passed inline, as in `wsl.exe -d <distro> -- bash -lc '...'`,
  can fail with `Argument list too long`: Linux refuses a single argument of
  128 KiB or more (measured on the workstation's WSL kernel: 131,071 bytes
  ran, 131,072 did not), and a Windows command line is limited to 32,767
  characters
  ([CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw)).
  `/dev/stdin` could not be reopened by path across the interop boundary
  either. Pipe the script to `bash -s` instead:
  `wsl.exe -d <distro> -- bash -s < script.sh`.

## Listeners and ports

- All WSL 2 distributions share one network namespace
  ([About WSL](https://learn.microsoft.com/en-us/windows/wsl/about)), so
  `ss -ltnp` in one distribution lists the other distributions' listeners too,
  without a process. Attribute a listener to its distribution, unit and
  upstream documentation before labelling it. On the WSL workstation on
  2026-09-25, `127.0.0.1:49374`, this repository's default ai-memory port, was
  held by another distribution, and that host's scoped `nativestack-memory`
  unit binds `127.0.0.1:49474`. The ai-memory MCP registration and the
  rendered hook commands (`AI_MEMORY_URL` in the host's
  `adoption/hosts/<host>.json`) must name the port the host's own ai-memory
  unit binds. The user-scope template `adoption/mcp/claude-user.json` keeps
  the default 49374, and its comment gives the remove-then-add sequence for
  another port. That template changed after `v2026.09.24.1`: serena runs
  `${ECO_ROOT}/bin/serena` instead of a `serena-context` wrapper, and
  jcodemunch is no longer registered at user scope (a per-project opt-in in
  `adoption/bootstrap.md` step 4a).
- With `networkingMode=mirrored`, a wildcard (`*` or `0.0.0.0`) listener can be
  reached from the local network
  ([mirrored mode](https://learn.microsoft.com/en-us/windows/wsl/networking#mirrored-mode-networking))
  unless the Hyper-V firewall blocks it. WSL 2.0.9 and later turn that
  firewall on by default on Windows 11 22H2 and later
  ([WSL and firewall](https://learn.microsoft.com/en-us/windows/wsl/networking#wsl-and-firewall)),
  and the mirrored-mode page opens inbound connections only by changing the
  firewall's settings or adding a firewall rule. Bind services to `127.0.0.1`
  and check `ss -ltnp` after each start.
- vLLM listens on a wildcard port even with `--host 127.0.0.1`. vLLM 0.25.0
  initializes `torch.distributed` over TCP on a single GPU too (its
  `UniProcExecutor` passes a `tcp://` init method), and PyTorch's `TCPStore`
  listens on all interfaces by default. vLLM documents this as known,
  intended PyTorch behavior and says to firewall the internal ports
  ([security guidance at v0.25.0](https://github.com/vllm-project/vllm/blob/v0.25.0/docs/usage/security.md#security-and-firewalls-protecting-exposed-vllm-systems)).
  On the WSL workstation on 2026-09-25 (vLLM 0.25.0, torch 2.11.0, API server
  on `127.0.0.1:18231`), `ss -ltnp` showed the engine-core process
  (`VLLM::EngineCor`) listening on `*:24706`. Treat this as a known upstream
  limitation that the Hyper-V firewall mitigates only while it blocks inbound
  connections: keep that firewall on and its inbound default at block.

## Boundaries

Executable presence, a passed `--version`, or this document being valid does
not establish account readiness, service health, or model-mediated behavior
on a new WSL host — each new host repeats its own native sign-in and at least
one bounded useful call (`adoption/README.md`, "Native verification tiers").
