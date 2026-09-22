# Clean installation evidence for the next WSL PC

On September 21, 2026 (America/New_York), a read-only checkout of
`dac2d1a3f880c04f6afadebe8bf3a251a64ab605` was tested in a fresh SDK prefix on
the existing WSL host. This is a package reproducibility check, not a clean WSL
distribution or second-PC acceptance.

The native uv 0.12.17 installer and CPython 3.13.15 downloaded all **36 locked
distributions** from public PyPI with required hashes, no cache and no source
builds. Package consistency passed; the exact installed name/version set matched
the lock. Seven actual imports resolved inside the new prefix, all six required
Codex SDK symbols imported, and a DuckDB query returned its expected result.
The lock includes 867 accepted artifact hashes; only the selected platform's
artifacts were downloaded.

**55 existing data fixtures passed** across financial data, catalysts,
point-in-time data and nanosecond replay. The broader suite initially reported
766 tests: 763 passed, one error and two skips. The audit had removed `HOME`;
the failing native-environment test requires it. A targeted rerun preserving
native `HOME` passed. Both outcomes are retained. The skips concerned the separate
EdgarTools environment and unavailable QEMU.

Portable and historical catalog validators passed. Prerequisite inspection found
all recipe references valid, while Dagu, .NET and eight telemetry executables
were missing from that process's `PATH`; this does not establish that they are
absent from disk. The checkout was clean before and after.

See the [observed commands](../../evidence/artifacts/catalog-clean-install-20260921/commands.json),
[audit](../../evidence/artifacts/catalog-clean-install-20260921/AUDIT.md),
[source hashes](../../evidence/artifacts/catalog-clean-install-20260921/source-manifest.json)
and [receipt](../../evidence/receipts/catalog-clean-install-20260921.json).
Public logs retain actual output with personal paths replaced by placeholders;
the verbose suite log is explicitly excerpted. Private originals and their hashes
remain available. `${STACK_REPO}`, `${SDK_ENV}`, `${UV_BIN}`, `${PYTHON_BIN}` and
`${NATIVE_HOME}` denote the explicitly selected checkout, isolated environment,
native executables and existing native home; they are not literal install paths.

To repeat the supported install, follow [adoption/sdk/README.md](../../adoption/sdk/README.md)
in a new prefix, then [the handbook](../../docs/grand-catalog-handbook.md) and
[adoption profiles](../../adoption/README.md). Preserve native `HOME` for checks
that verify it. Record each destination's actual prerequisites and useful behavior.

This run did not install or qualify every `foundation-cpu` component, including
Context Mode, ai-memory and MCPorter. Native sign-ins, complete client routing,
GPU/Docker/telemetry services, scoped memory, recovery and broker operation still
need the destination's own evidence. No accounts, shared settings, services,
credentials or broker operations were changed by this audit.
