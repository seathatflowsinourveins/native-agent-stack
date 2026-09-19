# Recreate the accepted native SDK

The existing five direct dependencies remain in [workers/requirements.txt](../../blueprints/us-equities/workers/requirements.txt). Native **uv 0.12.17** resolved their full dependency graph under the [36 accepted version constraints](accepted-constraints.txt), producing [the hash lock](requirements-linux-x86_64-py313.lock): **36 distributions and 867 SHA-256 artifact hashes**. Multiple platform wheel hashes do not make the dependency resolution universally portable.

This lock targets **CPython 3.13.15, Linux x86_64 glibc**. It does not contain an interpreter, OS libraries, GPU services, broker credentials or all npm/native-tool dependencies. The SDK bundles Codex CLI 0.154.0; the existing worker deliberately selects the separately accepted native Codex 0.155.1 with `--codex-bin`. The [official SDK](https://learn.chatgpt.com/docs/codex-sdk) documents this binary override. No model names are replaced during installation.

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

The fresh-prefix acceptance is in [the receipt](../receipt.json). It compares installed name/version pairs to the accepted Syft inventory, exercises the SDK import and existing useful DuckDB/data tests, and records model-account readiness separately. This is another prefix on the same WSL host, not a physical second-machine deployment.

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
