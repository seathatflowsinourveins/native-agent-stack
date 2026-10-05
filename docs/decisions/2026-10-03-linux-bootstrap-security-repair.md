# Linux platform-package verification and publication repair

Date: 2026-10-03. Scope: contract A4 on PR #626, based on
`ad9787c313c05e4325416060a8737641d4cd714d`; no shared-host switch.
North-star action: keep the native Codex foundation reproducible for complex
systems and US-equities research and historical simulation.

The selected implementation extends the existing macOS bootstrap reference at
`511168f4a`, using native npm installation/rebuild, Node package resolution,
archive checks and Python `os.replace`. It adds the missing Linux integrity
invariants without adopting another installer or test framework. The installed
search-first and diagnosing-bugs skills guided source selection and regression
controls; security-audit supplied focused boundary guidance. This is repair
work, rather than a new ecosystem-wide convergence or model-quality claim.
The scoped ai-memory tool is not exposed in this session; the exact contract,
scripts, pins and existing receipts supply the prior evidence.

Sources checked before implementation:

- `openai/codex`, `rust-v0.160.0`,
  `a956835d020762cb2b570053af06f643a11c0ecc`: the release returned by
  `gh api repos/openai/codex/releases/tags/rust-v0.160.0`, and the actual npm
  wrapper/platform archives linked from the shipped pin. Wrapper SHA-256
  `373517768e912eeb5054024ae9215e2c90a1420957b66fe134ef745a00948d4a`;
  platform SHA-256
  `37a41d61c3399182b8c727b77090cc7a1566bd849d0f09070a0bbc6fec4c58dc`.
  Both actual `package.json` files have no scripts or dependencies; the wrapper
  maps `@openai/codex-linux-x64` to
  `npm:@openai/codex@0.160.0-linux-x64`. The archive launcher resolves this alias.
- Installed `npm/cli` 11.19.0: native `npm help package-spec` and
  `npm help rebuild`, and
  `node_modules/@npmcli/config/lib/definitions/definitions.js` for
  `allow-scripts`. [Alias specification](https://docs.npmjs.com/cli/v11/using-npm/package-spec),
  [rebuild](https://docs.npmjs.com/cli/v11/commands/npm-rebuild).
- Installed Node 24.21.0: native fixture executions exercise
  `require.resolve`, `fs.realpathSync`, `fs.readdirSync` and JSON parsing.
  [Module resolution](https://nodejs.org/docs/latest-v24.x/api/modules.html#all-together).
- The existing `adoption/bootstrap-macos.sh` installation/publication functions
  and `tests/test_adoption_bootstrap_macos.py` integration checks.
  Native Python `unittest` remains the test harness; these are repository
  integration checks and synthetic fault injections, not unchanged upstream tests.

The Linux pin now keeps scripts disabled. Verification binds the installed
wrapper's exact dependency mapping and permitted package inventories to the
independently verified platform copy. An alias must be new and contained.
Pins that explicitly permit scripts must preserve the complete platform tree's
contents, file types and permissions after rebuilding. The native binary still
requires a contained executable path and its pinned SHA-256 before publication.

Python is an explicit prerequisite. Archive SHA-512 verification uses isolated
Python and runs before npm installation. Each versioned directory is created
fresh. Cleanup removes unpublished trees, preserves a tree already published
when a signal precedes the state clear, restores a failed migration with GNU
`mv -T` on Linux, and reports a post-publication leftover for deletion.
Pruning cannot remove the newly published tree.

S3's required parity test necessitated changes to the shared macOS
`install_npm`, pruning and corresponding cleanup state. Its platform installer
and pins retain their existing contract. Five shared helpers are byte-identical;
`install_npm` is identical apart from comment lines. The macOS cleanup retains
BSD `mv --` and its existing failed-rollback diagnostic.

Alternatives considered were trusting npm's automatic optional fetch, hashing
only the main executable after lifecycle scripts, and duplicating publication
logic separately per platform. The original-script controls show the first two
permit the wrong launcher or changed auxiliary executable; parity rejects the
third. A future upstream installer with independently pinned dependency
resolution, complete executable-tree verification and equivalent recoverable
publication would overturn this choice after the same negative controls and
isolated native installation pass.

Corrections discovered during verification:

- npm 11.19.0 can suppress fixture lifecycle scripts through `allow-scripts`.
  Explicitly allow only the fixture wrapper in its isolated npm configuration
  before using rebuild corruption as a discriminating control. The repeated
  original-script control and repaired integration suite provide the evidence.
- The first broad run's unchanged macOS npm fixtures returned exit 226 while
  using the ambient cache/configuration. The required rerun uses a fresh writable
  npm cache and empty configuration files; no host cache or configuration is edited.
- The first macOS parity cleanup port applied GNU `mv -T` in a macOS fixture,
  defeating its BSD rollback-failure shim and diagnostic assertion. Preserve
  the native macOS rollback command and verify that exact existing test.
- A prerequisite negative control needs the original script in a valid source
  layout. Retain the corrected layout, and refuse network in its curl fixture,
  instead of treating a missing-manifest failure as an interpreter control.
- `host_receipts.register_file` updates file hashes and sizes; it does not
  mirror an existing publication receipt's claim and limitations. The first
  publication validation rejected those two stale fields. Synchronize that
  receipt registration from its payload, re-register final files, and rerun
  `scripts/validate.py`; the returned failure is retained separately.

The isolated native bootstrap selects the shipped Codex pin and the script's
mandatory Node/uv/gh prerequisites through a Codex-only fixture manifest. The
shipped script and pins are copied byte for byte. It installs into a fresh
dedicated prefix and uses empty npm configuration, an isolated cache and a
dedicated Codex state directory. Returned exit code, installed binary hash,
version and sanitized output are retained under
`evidence/artifacts/runtime-sdk-20261003/linux-bootstrap-a4/`.
The older SDK/gateway canary receipt remains `compatibility_attempt` with its
original provenance limits.

Completeness critic: cover both nested and alias placement, scoped/unscoped
package inventories, wrapper mapping, NODE_PATH decoys, primary and auxiliary
executables (including modes), malformed pins, archive hashes, interpreter
absence, migration, failed publication, prefix collisions, pruning and shared
platform parity. The remaining candidate class is a future platform package
with lifecycle scripts or additional runtime dependencies: it requires a new
pin contract and fresh source/negative-control review before acceptance. No
provider run, upstream suite, cross-host recovery or signature/attestation
acceptance follows from these local checks.

Hosted macOS correction (coordinator, 2026-10-03): `validate-macos` at
`ad9787c31` failed three `tests.test_adoption_bootstrap.NpmIgnoreScriptsTests`
cases, because npm's argv carries the canonicalized versioned prefix
(`/private/var/...` under macOS's `/var` symlink) while the test expected the
temporary path as given. The test now expects the canonical prefix and the
downloaded archive as given, matching `install_npm`; the canonical-prefix
guarantee is unchanged. Reproduced and cleared on Linux by running the four
bootstrap test modules under a symlinked `TMPDIR`: 273 tests, `OK
(skipped=32)`, with and without the symlink. The hosted macOS run at the new
head is the remaining confirmation.
