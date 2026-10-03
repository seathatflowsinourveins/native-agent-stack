# Recreate the pinned native SDK

The existing five direct dependencies remain in [workers/requirements.txt](../../blueprints/us-equities/workers/requirements.txt). Native **uv 0.12.17** resolved their full dependency graph under the [36 accepted version constraints](accepted-constraints.txt), producing [the hash lock](requirements-linux-x86_64-py313.lock): **36 distributions and 867 SHA-256 artifact hashes**. Multiple platform wheel hashes do not make the dependency resolution universally portable.

This lock targets **CPython 3.13.15, Linux x86_64 glibc**. It does not contain an interpreter, OS libraries, GPU services, broker credentials or all npm/native-tool dependencies. The current SDK and bundled CLI are **0.160.0**; `--codex-bin` selects an explicit native binary. The [official SDK source](https://github.com/openai/codex/tree/rust-v0.160.0/sdk/python) documents this binary override, and the [published SDK metadata](https://pypi.org/pypi/openai-codex/0.160.0/json) requires `openai-codex-cli-bin==0.160.0`. The release builder stages those versions explicitly; the tag's development `pyproject.toml` is not the released package metadata. The other 34 distribution versions remain unchanged. The [September 30 route and lifecycle qualification](../../evidence/artifacts/runtime-sdk-20260930/receipt.json) retains its original 0.159.2 scope; it does not qualify this upgraded pair or rewrite earlier adoption evidence.

The [October 3 pair and route qualification](../../evidence/artifacts/runtime-sdk-20261003/receipt.json) records the coordinator's strict-hash installation, compatible package inventory, matching bundled/npm-platform binary and completed native-account SDK, gateway SDK and gateway CLI marker canaries for 0.160.0. The two SDK canaries retain their native usage; CLI usage and stdout/stderr hashes were not supplied. Gateway backend model and effort were not read from the call log. The shared host launcher, daemon and production prefix still run 0.159.3 until a coordinated switch. This same-host evidence does not establish model-quality or replacement-host acceptance.

The [October 1 pair and native-account qualification](../../evidence/artifacts/runtime-sdk-20261001/receipt.json) retains its original 0.159.3 scope, gateway HTTP 429 and post-return classifier failure. The new canaries have their own qualification; earlier receipts remain unchanged.

Set `SDK_ENV` to a **new, dedicated private environment path**, and `PYTHON_BIN` to an installed CPython 3.13.15 interpreter. Do not sync a shared/system environment: native sync removes packages outside the lock.

From the repository root:

```sh
uv --version
"$PYTHON_BIN" --version
uv venv --python "$PYTHON_BIN" --no-python-downloads "$SDK_ENV"
uv pip sync --python "$SDK_ENV/bin/python" --require-hashes --no-build \
  --strict --default-index https://pypi.org/simple --no-sources \
  adoption/sdk/requirements-linux-x86_64-py313.lock
uv pip check --python "$SDK_ENV/bin/python"
"$SDK_ENV/bin/python" -m unittest discover -s tests -v
```

Use a clean package-manager environment: review local uv configuration and package-index overrides without printing credential values. The recorded native run used public PyPI. Its additional `--no-cache --reinstall` replay fetched all 36 distributions again, then installed successfully with required hashes and no source builds. Download availability is not guaranteed forever; hashes verify selected artifact bytes, not security or model quality.

The historical 0.154.0 fresh-prefix acceptance is in [the adoption receipt](../receipt.json). It compares installed name/version pairs to the then-accepted Syft inventory, exercises the SDK import and existing useful DuckDB/data tests, and records model-account readiness separately. The September 30 prefix uses the updated lock and a separately recorded execution; the old receipt is not acceptance of the upgraded packages. Both are prefixes on the same WSL host.

## Recompile intentionally

This is a maintenance command, **not** needed for normal installation:

```sh
uv pip compile blueprints/us-equities/workers/requirements.txt \
  --constraints adoption/sdk/accepted-constraints.txt \
  --python "$PYTHON_BIN" --python-version 3.13.15 \
  --python-platform x86_64-unknown-linux-gnu --generate-hashes --no-build \
  --no-sources --default-index https://pypi.org/simple --no-header \
  --output-file adoption/sdk/requirements-linux-x86_64-py313.lock --quiet
```

The first compile attempt supplied both `--no-build` and `--only-binary :all:`; upstream uv rejected the mutually exclusive flags with exit 2. The corrected command above succeeded. Failures are retained rather than presented as successful work.

For an upgrade, review the direct requirement and affected constraint together, regenerate the lock, inspect the dependency diff and recreate a new prefix. Keep the previous prefix for rollback. Do not append `--upgrade` to a reproduction command. [Upstream locking/sync documentation](https://docs.astral.sh/uv/pip/compile/) explains the native distinction between constraints, installation and exact synchronization.
