# Report Codex profile drift without replacing operator values

Date: 2026-10-05. Lane: foundation. North-star action: keep the native research and coding workers' configured model and tool policy observable for US-equities research and historical simulation.

The co-op reported four keys in the installed OmniRoute profile that differed from the NativeStack2604 render, although F9 reported success. This unit reproduces that failure with synthetic profiles; it does not reread the reported host profile or claim host acceptance.

At native-agent-stack@2d849ba1fe1b879144cfa470f0514d3ac3b8e487, `tools/adoption/new_wsl_client_config.py:1475-1521` checks repository wiring, never installed profile files. Its `:2409-2437` profile step creates absent files and preserves existing ones, but labels the step current when it creates nothing, including when an existing file differs. Verification at `:2452-2467` checks login-shell resolution rather than profile contents. The failure is a comparison-scope gap in F9, independently reproduced by a failing check fixture and a failing apply-verification fixture.

## Upstream boundary

Installed Codex 0.160.0's top-level help describes profile-v2 files as an override layer. An expected-render comparator was not found in the installed top-level, doctor or debug help or the version's [release notes](https://github.com/openai/codex/releases/tag/rust-v0.160.0). At openai/codex@a956835d020762cb2b570053af06f643a11c0ecc (rust-v0.160.0), [loader/mod.rs:286-333](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/config/src/loader/mod.rs#L286-L333) layers the selected profile over the base user config. [merge.rs:96-149](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/config/src/merge.rs#L96-L149) recursively merges tables and replaces non-table values. Native [config/read parameters:389-407](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/app-server-protocol/src/protocol/v2/config.rs#L389-L407) expose configuration and its origins, without an expected-render input. Native TOML health checks ([doctor.rs:1188-1201](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli/src/doctor.rs#L1188-L1201)) do not supply the repository's desired values.

F9 already owns that render and a typed additive merge. Extend its check; introduce no installer, client wrapper or dependency. Use stdlib TOML parsing ([tomllib conversion table](https://docs.python.org/3.11/library/tomllib.html#conversion-table)) and native-agent-stack@2d849ba1's existing `strict_equal` (`:1567-1573`) and `plan_merge` (`:1626-1661`). Compare missing and conflicting render-owned paths. Comparing against the merge's expected tree would hide deliberate preservation of operator values.

## Decision

`--check --host NAME` compares the wired stack-worker and OmniRoute profile files under `--home` (defaulting to the user's home) to the selected host render. Plain `--check` remains the repository structural check. Report missing files, missing rendered keys and conflicting typed values using profile basenames and dotted key names. Ignore extra operator-only fields and formatting. `--with-authorization-settings` selects the same comparison scope as the explicit render option; checking it writes nothing and grants no authorization.

Apply retains create-only profile handling. Existing bytes and operator values stay intact. A mismatching profile makes the profile step `drifted`; default verification fails with the key list. Explicitly skipping `codex-files` also omits its profile verification. Dry-run retains its existing no-write planning behavior. No replacement flag is added. Base configuration merging, backups and authorization-write controls keep their existing contract.

Sanitize TOML and OS errors to their exception class, rather than echoing content or host paths. Keep the existence check inside that handler: [python/cpython@v3.11.17, Lib/pathlib.py:1230-1238](https://github.com/python/cpython/blob/v3.11.17/Lib/pathlib.py#L1230-L1238) can propagate permission errors from `exists()`.

This reports file drift against the repository render. It does not prove the effective configuration of a running session, MCP availability, upstream acceptance or new provider execution. The configuration owner decides whether an intentional override should stay and applies any host change through its owned route.

## Evidence and alternatives

The [sanitized receipt](../../evidence/artifacts/codex-profile-drift-check-20261005/receipt.json) retains the red reproduction, repaired module suite and validation separately from pinned source review and native help metadata. Fixtures cover drift, matching values with extra operator fields, merge-kept values, missing keys, malformed TOML, permission errors and explicit authorization comparison. JSON and Markdown modes retain their output formats while returning failure and key-only diagnostics.

A presence-only check repeats the observed false pass. Automatic profile replacement violates the existing operator-value boundary. Native doctor or config/read can establish native syntax or effective configuration, but cannot compare a repository render they do not receive. Read-only static review found the permission-error edge; that finding became a focused regression test. No cross-family readiness approval is claimed; the PR stays draft for the command center's Claude read.

Revisit this glue if upstream ships a supported expected-render comparator, if the owned profile set changes, or if the configuration owner changes the desired-key policy. In particular, adopting profile `skills.config` rule arrays requires a declared comparison policy: the reused merge accepts existing extra rules, and neither current profile renders that array.
