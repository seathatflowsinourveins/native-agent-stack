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

The handbook is regenerated through `scripts/build_new_wsl_handbook.py`.
Its rolling integration receipt preserves previous bindings and validation
history while recording the new profile/output hashes and generator checks.
The repository's existing profile/handbook tests and `scripts/validate.py`
verify the projection and evidence consistency; they do not install Harbor.

The inverse restores the former profile row and regenerates the handbook
through the same builder. It changes source recommendation metadata and
does not alter an installed launcher or client configuration. Both
designated reads, required CI, pre-cue and explicit command-center cue remain
landing gates for this draft PR.
