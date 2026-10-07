# Codex profile and environment content fold (2026-10-07)

The command center's A14 and FOLDS-RULED directions consolidate PR716 and
PR756 into the existing environment PR770 by content, on its current base.
This keeps one reviewed foundation client-configuration chain for the native
workers supporting US-equities research and simulation. The root publishes
once; this change performs no host apply or landing rebase.

## Sources and composition

- PR716 at `b63381f877dd1108a0347300f4a3ee765eb1f0d6`, compared with
  `4af7417b7d4db8936c0136235a86717f31d16f27`, supplies missing-key recovery
  for existing Codex profile-v2 files and the two slot-bound approval defaults.
  Its [source decision](2026-10-05-codex-token-parity.md) names the supported
  upstream loader and separates the RTK owner's route from this change.
- PR756 at `5cfb02f7ab11161711bc0de4cb898744bf2296b6`, compared with
  `424b8a778222ae8857aade42c49ae6f7a13b3138`, supplies a value-free profile
  drift check. Its [source decision](2026-10-05-codex-profile-drift-check.md)
  records the original comparison gap and the native configuration interfaces.
- Codex [`a956835d`, loader/mod.rs:286-333](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/config/src/loader/mod.rs#L286-L333)
  layers profile-v2 over the base user configuration; [merge.rs:96-149](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/config/src/merge.rs#L96-L149)
  merges tables and replaces other values. These upstream loader semantics
  motivate the repository's expected-render comparison, not automatic scalar
  replacement on an operator's host.
- The retained PR770 source at `1a567f540ac9231328bbe349ad05baeaa12b5ad9`
  already contains login-env and the native main-config one-time migration.
  The latter follows [Codex app-server configuration writes](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/app-server/src/config_manager_service.rs#L426-L438).

The shared merge now accepts a staged filename, group and step. Pending owned
migrations and native daemon writes are enabled only for `codex/config`.
Profiles use the additive text merge, backup, running-client guard, typed
read-back and restoration. A profile keeps a differing existing scalar,
including service tier, and does not stamp the main-config migration marker.
Missing authorization keys are added only with the existing explicit option;
slot ownership remains the prerequisite. Role carriers remain create-only.

The check compares rendered keys, not the merge's intentionally preserved
expected values. Existing operator differences therefore remain drift, reported
by key name. Apply verification runs that comparison unless codex-files was
explicitly skipped. Invalid TOML and OS errors in this comparator report their
exception class without echoing contents or host paths.

The [byte ledger](../../evidence/artifacts/codex-profile-env-fold-20261007/source-bytes.json)
records all 72 added donor files copied unchanged. Shared controller, tests,
template, anti-pattern table, generated decision projection and registry are
composed and individually explained in the [new receipt](../../evidence/artifacts/codex-profile-env-fold-20261007/receipt.json).
The target's original decided text and historical observations remain; current
generated counts/tables appear in an appended dated amendment. The donor's
older create-only profile statement is a historical source condition, superseded
for this composition by additive recovery plus independent drift reporting.

## Alternatives and evidence boundary

Whole-file replacement would discard the environment and migration contracts;
it is rejected. Treating a preserved conflict as current would hide drift;
it is rejected. This composition reuses both bounded behaviors and verifies
their interaction with synthetic profiles. A later owner decision can replace
this route through a new sourced record and its native read-back.

Copied gateway measurements and failed source attempts remain historical
text-artifact preprocessing evidence. They are not new model calls, integrated
gateway qualification or cumulative token savings. Fresh local integration and
structural checks are reported separately. PR770's previously declared wider
suite limitations are not erased by these focused checks. Host application
remains the command center's supported F9 route after landing and review.
