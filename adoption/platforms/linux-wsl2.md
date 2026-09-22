# Linux/WSL2 x86_64 — status: accepted

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

## vLLM pin: 0.25.0, not 0.29.0

The working WSL vLLM pin is **0.25.0**. Version **0.29.0 failed real startup
with "UVA is not available"** on this WSL GPU path (unified virtual
addressing unsupported by the WSL GPU driver surface at that release).
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
5. Run `python3 scripts/adoption_status.py --profile <id> --json` and record
   the per-host receipt (`adoption/bootstrap.md` steps 6–7).

## Boundaries

Executable presence, a passed `--version`, or this document being valid does
not establish account readiness, service health, or model-mediated behavior
on a new WSL host — each new host repeats its own native sign-in and at least
one bounded useful call (`adoption/README.md`, "Native verification tiers").
