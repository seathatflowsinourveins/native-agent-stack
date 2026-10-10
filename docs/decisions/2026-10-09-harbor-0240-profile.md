# Harbor 0.24.0 in the new-WSL source profile

The profile selects Harbor 0.24.0 and records the vendor's
`uv tool install harbor==0.24.0` route. The entry remains an optional,
unprovisioned source recommendation. This change verifies the release,
source identity and wheel integrity; it does not install Harbor or qualify
its runtime, agent/provider benchmarks or destination WSL acceptance.

The primary upstream is
[harbor-framework/harbor](https://github.com/harbor-framework/harbor).
An initial API request through the former `laude-institute/harbor` identity
redirected to this canonical repository. The
[v0.24.0 release](https://github.com/harbor-framework/harbor/releases/tag/v0.24.0)
is non-draft and non-prerelease, published 2026-10-05T05:04:52Z. Its tag
resolves to [b53b8134e1241686dca7759af188f987ecc48e8b](https://github.com/harbor-framework/harbor/commit/b53b8134e1241686dca7759af188f987ecc48e8b).
The captured `refs/tags/v0.24.0` reference points to an **annotated tag**
object, `bf8996ef6d97d014924dc1a5e4acc7e9b19b27a1`, whose object type is
`tag`. Its captured tag object peels directly to the commit above. This is
reference/object/commit identity proof; no signed-tag verification is claimed.
The reference, tag-object and commit responses are retained in the new
receipt's `upstream/` directory, alongside release and PyPI metadata and the
three pinned source copies: [reference](../../evidence/artifacts/harbor-0240-currency-20261009/upstream/ref-v0.24.0.json),
[tag object](../../evidence/artifacts/harbor-0240-currency-20261009/upstream/tag-object.json),
[commit](../../evidence/artifacts/harbor-0240-currency-20261009/upstream/commit.json),
[release](../../evidence/artifacts/harbor-0240-currency-20261009/upstream/release.json),
[PyPI metadata](../../evidence/artifacts/harbor-0240-currency-20261009/upstream/pypi-0.24.0.json),
[README](../../evidence/artifacts/harbor-0240-currency-20261009/upstream/README.md),
[project metadata](../../evidence/artifacts/harbor-0240-currency-20261009/upstream/pyproject.toml)
and [pytest workflow](../../evidence/artifacts/harbor-0240-currency-20261009/upstream/pytest.yml).
Their [capture/provenance record](../../evidence/artifacts/harbor-0240-currency-20261009/upstream/capture-provenance.json) distinguishes
native capture formatting from the original response bytes.
The pinned [project metadata](https://github.com/harbor-framework/harbor/blob/b53b8134e1241686dca7759af188f987ecc48e8b/pyproject.toml#L3)
also declares version 0.24.0 and Python >=3.12.

The release notes include Codex web-search ID/structured-output trajectory
repairs, sandbox and verifier fixes, agent capability declarations and
RewardKit changes. These are publisher release descriptions, not reproduced
capability or security results. The currency change follows the already
selected Harbor tool and its maintained native install route; it establishes
no new quality ranking from release recency alone.

## Wheel and supported commands

[PyPI's version-specific metadata](https://pypi.org/pypi/harbor/0.24.0/json)
publishes `harbor-0.24.0-py3-none-any.whl`, 2,331,740 bytes, SHA256
`23b7ba616a3aae4eff561ced5e2c51c7186f2981e53a770dea9c689d3969877c`.
The official wheel was downloaded into the lane-owned research prefix and
hashed; bytes and digest matched the published metadata. Reading its
distribution metadata confirmed name `harbor`, version `0.24.0` and Python
`>=3.12`. The wheel was neither installed nor imported. This verifies that
artifact's identity, not the installation's transitive dependency lock or
runtime correctness.

The independently rehashed wheel remains in the lane's private state under
`research/harbor-0240-currency-20261009/harbor-0.24.0-py3-none-any.whl`.
The receipt binds this custody locator, the immutable PyPI file URL, bytes
and digest so a review packet can supply the same pinned artifact. The wheel
is not part of the Git commit. The new public captures permit independent
release/tag/source comparison without treating repeated digest strings as
artifact verification.

The pinned [README:22](https://github.com/harbor-framework/harbor/blob/b53b8134e1241686dca7759af188f987ecc48e8b/README.md#L22)
documents `uv tool install harbor`; the profile applies its selected version
through the existing exact-version form. The pinned
[Linux test workflow:54](https://github.com/harbor-framework/harbor/blob/b53b8134e1241686dca7759af188f987ecc48e8b/.github/workflows/pytest.yml#L54)
uses a locked all-packages/all-extras environment and adds RewardKit unit
tests and coverage to the non-runtime suite:

```text
uv sync --all-packages --all-extras --locked && uv run pytest tests/ packages/rewardkit/tests/unit/ -m "not runtime" --cov=src/harbor --cov=packages/rewardkit/src/rewardkit --cov-report=term-missing
```

The profile records that current command with its Python 3.13,
Docker/Compose and Deno prerequisites. Its execution status stays `UNRUN`.
No upstream source test, container setup or native installation was performed.

## Repository evidence and inverse

`evidence/artifacts/harbor-0240-currency-20261009/receipt.json` binds the
version-specific release, tag, wheel and pinned source observations. The
older core-native-recipe receipt retains its 0.23.0 observation as history.
The current entry points to the new receipt, replaces its source-only
checksum with the verified wheel checksum and keeps the unprovisioned
acceptance gap explicit.

The operative Inspect Scout owner selection also requires Harbor for ATIF
import in its shared Inspect AI environment. The authorized review repair
records a dated 2026-10-09 companion-pin amendment in the consensus source,
while its 2026-10-04 owner row retains the original 0.23.0 summary, pin and
install requirement. The assembler preserves that row under
`prior_owner_decision` and generates the current 0.24.0 projection with an
explicit dated amendment marker and a hash-bound source receipt. The current
trajectory-analysis install-plan row and mirrored scripts use the verified
0.24.0 wheel and version assertion in the same Scout-owned environment;
they remain unexecuted. The plan's other rows and separate pinned Harbor
reproduction are preserved. The generated handbook now carries
the same Harbor version in both installation recommendations. Dated measured
0.23.0 receipts and frozen benchmark reproductions retain their original
versions; the current owner recommendation is distinct from those records.

A regression check compares the current profile pin with imperative Harbor
companion pins in operative owner selections and their generated projection.
It failed before this repair and passes after the owner-input amendment and
native regeneration. This checks the cross-owner installation contract that
ordinary generated-byte equality did not cover.

The handbook is regenerated through `scripts/build_new_wsl_handbook.py`.
Its rolling integration receipt preserves previous bindings and validation
history while recording the new profile/output hashes and generator checks.
The repository's existing profile/handbook tests and `scripts/validate.py`
verify the projection and evidence consistency; they do not install Harbor.

The inverse restores every operative Harbor input to the previous 0.23.0
selection before regenerating any derived output:

1. Restore the Harbor entry in `adoption/new-wsl-profile.json`, including its
   pin, checksum, install/acceptance references and prior receipt binding.
   Update its prose, source table and exact command/checksum block in
   `adoption/new-wsl-profile.md` to that restored JSON contract as well
   (the current profile prose/table were at lines194-196 and225).
2. Remove the 2026-10-09 Harbor entry from
   `evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json`'s
   `current_owner_pin_amendments`. Its original 2026-10-04 Scout owner row
   already retains 0.23.0. Rebuild
   `evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json`
   through `assemble_manifest.py` and regenerate the decision tables with
   `render_tables.py --write docs/decisions/2026-10-01-new-wsl-definitive-defaults.md`.
3. Restore the Harbor owner and Scout companion fields in
   `evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json`, and
   the Harbor release metadata in the adjacent `owners.json`. Its note and
   `current_release_source` must describe the restored0.23.0 source, removing
   the current0.24.0 release claim while retaining the historical repository
   timestamp qualification. Restore all
   executable mirrors together: the Scout wheel URL/checksum in
   `install.sh:1034,1036` and version assertion in `accept.sh:2726`; the direct
   Harbor wheel URL/checksum, version assertion and source-checkout commit
   in those same scripts; and the exact Harbor checkout in
   `config/harbor-worker-telemetry-accept.sh`. Restore the Scout plan summary
   printed by `install.sh:1136`. Use the retained0.23.0 source records for
   its wheel checksum and commit. Update the adjacent install-plan `README.md`:
   its G5 paragraph must identify0.23.0 as the restored current selection,
   with the10-09/0.24.0 amendment retained only as dated reverted history;
   also restore the Scout/Harbor rows formerly at README:624 and:715.
   Restore the current version/commit statements in
   `config/harbor-worker-telemetry-contract.md` (its heading and lines8-12),
   preserving separately identified historical source-method citations.
4. Regenerate `docs/new-wsl-handbook.json` and `.md` through
   `python3 scripts/build_new_wsl_handbook.py --write`. Append a new binding
   to the rolling handbook integration receipt, preserving its earlier
   derivation history; register changed evidence through
   `scripts.host_receipts.register_file`, then normalize with
   `python3 scripts/evidence_manifest.py --write`.
5. Restore pin-dependent regression fixtures/expectations in
   `tests/test_new_wsl_definitive_defaults.py` and
   `tests/test_new_wsl_handbook.py` with the same prior selection. Require
   the corresponding source-contract fixtures in
   `tests/test_harbor_currency_contracts.py` to describe that inverse too.
   the affected definitive-defaults, handbook and evidence tests,
   both generator checks, and FULL `python3 scripts/validate.py` to pass
   before publishing the inverse. The current companion/direct-owner pin
   consistency check must again agree on 0.23.0.

This inverse restores repository source recommendations and executable plan
inputs; it is not a host downgrade procedure or an installed launcher/client
configuration change. Both designated reads, required CI, pre-cue and the
explicit command-center cue remain landing gates.
