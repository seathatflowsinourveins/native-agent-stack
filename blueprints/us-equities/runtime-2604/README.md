# NativeStack2604 offline research runtime — October 4, 2026

The selected research runtime installed successfully on NativeStack2604 and all
**25 offline acceptance checks passed** on October 4, 2026, from
**21:17:20Z to 21:23:33Z**. This is historical host-local execution of native
software. The [run receipt](../../../evidence/receipts/native-trading-runtime-2604-20261004.json)
retains the recorded results and failed attempts; packaging these files does not
repeat installation or acceptance. No paper or broker execution occurred.

Packaging updates the installer's provenance comment and expresses the acceptance
script's synthetic sandbox home through a variable, preserving its actual mount
and environment arguments. The runtime project files remain unchanged.

This recipe serves the US-equities research and historical-simulation north star:
[NautilusTrader 2.0.0rc5](../../../catalogs/us-equities/runtime-target.json), its
in-tree IBKR adapter and the separately staged Alpaca adapter. It installs a
research environment and stages images. Its only execution entrypoint runs
offline examples. Broker-specific paper readiness, data acceptance and strategy
qualification remain separate under the [architecture boundaries](../architecture/README.md).

The preparation used repository snapshot
`d323b53437e025be3d054b9b5e4d292fe396c75e`; this package was integrated against
`38ac9aca114ad9ef4a15d8620d947eb5c2f518c3`. The
[decision record](../../../docs/decisions/2026-10-04-trading-2604-preparation.md)
records alternatives, repairs and remaining comparisons. The canonical runtime
target specifies Python `>=3.12,<3.15`, rather than an exact patch or the complete
matrix below. These supplemental pins remain subject to trading-lane ratification.

## Files and use

Keep the two scripts beside `trading-2604-runtime/`. Its `pyproject.toml` and
`uv.lock` are byte-identical to the reviewed staged project. The lock contains
242 package entries, including project metadata; it is not a claim of 242
installed distributions. The installer checks both embedded SHA256 values and
refuses modified project metadata on rerun. It uses locked sync, rather than a
fresh target-host resolution. The retained `exclude-newer` cutoff is
`2026-10-06T04:00:00Z`, after the run date; the delivered lock freezes the set.

Both scripts require NativeStack2604, Linux x86_64 and a non-root user. Foundation
prerequisites are uv **0.12.17**, Git, curl, core utilities, an already responding
rootless Docker daemon and Bubblewrap with permitted user/network namespaces.
The historical host default uv was 0.12.22; the coordinator supplied the required
version through `mise exec`. From the repository root, the corresponding commands
on that adopted host are:

```sh
rtk proxy env TMPDIR=/tmp/t2604-pkg-work nice -n 19 mise exec uv@0.12.17 -- \
  bash blueprints/us-equities/runtime-2604/install-trading-2604.sh
rtk proxy env TMPDIR=/tmp/t2604-pkg-work nice -n 19 mise exec uv@0.12.17 -- \
  bash blueprints/us-equities/runtime-2604/accept-trading-2604.sh
```

The scripts invoke native tools directly. They install no foundation service,
change no global Python default and request no WSL restart. The installer owns
`~/projects/us-equities-runtime`, including its managed interpreter, `.venv`,
cache, clean installer home, Docker configuration, staged public sources and
lockfile. An existing nonempty directory without its ownership marker is refused.
`uv python install --no-bin` prevents global executable links.

The selected Docker endpoint is captured before clearing the environment and
passed explicitly with a clean configuration. Default system sockets are refused;
an unavailable daemon blocks installation before Python work. The installer
removes a stale completion marker and writes a replacement atomically only after
both immutable images have been inspected. Acceptance requires that marker and
both images. An incomplete install blocks all 25 checks.

## Pinned sources

| Component | Delivered pin | Primary source |
| --- | --- | --- |
| CPython / uv | 3.12.3 / 0.12.17 | [Adapter's tested Python line](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/requirements.txt), [retained rc5 runtime](../../../evidence/receipts/native-nautilus-v2-20260920.json), [uv Python installation](https://github.com/astral-sh/uv/blob/0.12.17/docs/guides/install-python.md) and [locked sync](https://github.com/astral-sh/uv/blob/0.12.17/docs/concepts/projects/sync.md) |
| NautilusTrader / IBKR adapter | 2.0.0rc5; source `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`; in-tree Rust ibapi 3.3.0 | [Installation](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/getting_started/installation.md), [IBKR integration](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/integrations/interactive_brokers.md) |
| alpaca-py | 0.44.0 | [README at cc4cb3b7](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/README.md) |
| Separate Alpaca adapter | `dca821cca85dce3647fa7b488d5a23fbe5b85d4a` | [Native adapter source](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/native_adapter.py) |
| EdgarTools | 5.58.0 | [README at abe44344](https://github.com/dgunning/edgartools/blob/abe44344c56cf4bfb5443e0debca7e39342f6e7a/README.md) |
| exchange_calendars | 4.13.2 | [README at dbe38b1f](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/README.md) |
| DVC | 3.67.1 | [README at 356dfa03](https://github.com/treeverse/dvc/blob/356dfa03278058b02df42124f243c2c345329dae/README.rst) |
| DuckDB | 1.5.5 | [Python README at b236c819](https://github.com/duckdb/duckdb-python/blob/b236c8194ed14c7a7c685e0534dde501cc855b3a/README.md) |
| pandera[pandas] | 0.33.1 | [README at 62f55e2d](https://github.com/unionai-oss/pandera/blob/62f55e2dccf0a199cfe4d6ce3eda0c1d29e2e4e6/README.md) |
| skfolio | 1.2.9 | [Installation at c99fcf71](https://github.com/skfolio/skfolio/blob/c99fcf71349e2df4a7a1033ee85ca2e9ced9abee/docs/user_guide/install.rst) |
| fincore | 0.5.1 | [README at 576459c4](https://github.com/cloudQuant/fincore/blob/576459c495a8f7ff839f55e0d3057daa636174cc/README.md) |
| mlflow[mcp] | 3.16.1 | [MCP guide at 32792afe](https://github.com/mlflow/mlflow/blob/32792afe5b0183fce10532d3a023f5cfa8612d09/docs/docs/genai/mcp/index.mdx) |
| arch | 8.0.0 | [README at 038d78b7](https://github.com/bashtage/arch/blob/038d78b709e75f2590890757af32705817a6fad8/README.md) |
| purgedcv (eslazarev) | 0.1.10 | [README at aee1215c](https://github.com/eslazarev/purged-cross-validation/blob/aee1215c58d65a60a1d6af4b483f929fecde76e2/README.md) |
| NumPy / pandas | 2.5.3 / 3.0.6 | [Unchanged rc5 quickstart](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/getting_started/quickstart.py) and [retained rc5 runtime](../../../evidence/receipts/native-nautilus-v2-20260920.json) |

Package installation follows their PyPI requirements through uv's documented
project workflow. The rc5 wheel declares no runtime dependencies, so NumPy and
pandas are explicit. Use only the eslazarev purgedcv implementation; the distinct
landtml project shares its distribution/import name. Including requested Pandera
does not replace the separately judged Pointblank selection.

| Staged image | Immutable OCI index digest | Boundary |
| --- | --- | --- |
| IB Gateway 10.45.1j | `ghcr.io/gnzsnz/ib-gateway@sha256:91165c0752ca534c0dad3c40683ae7c2745974d4d277651a90e90411ca609d8d` | [README pin e19aa0be](https://github.com/gnzsnz/ib-gateway-docker/blob/e19aa0bebe5d0ddd55c6d0e25549380f9c7d1bf7/README.md); image label names build c147d206. Image staging does not sign in or qualify a gateway. |
| LEAN 18149 | `docker.io/quantconnect/lean@sha256:70071d1bbb90385deb60c7d20bc3830c7f4c79f6c09c5d1ade9196c009f68861` | [Dockerfile at 33e3945f](https://github.com/QuantConnect/Lean/blob/33e3945f2faa95308d972dfd3d7b762f7743d1d5/Dockerfile); source-to-image reproducibility and retained-oracle parity remain open. |

Both images were pulled for `linux/amd64` and inspected, without container
creation or execution. LEAN's retained source-built oracle at
`985ef30ad3ac774218c5ac516b4cb0aa2655730f` remains a separate reference.

## What the acceptance establishes

The 25 recorded PASS rows cover isolation, Python, 14 package imports/versions,
IBKR config-class exports, separate Alpaca source integrity and import, the
unchanged Nautilus quickstart's checksum and execution, and four example checks.
The host receipt's `native_proven` claim is scoped to actual native engine use;
the companion receipt labels each local probe and adapted example separately.
No complete unchanged upstream test suite was run.

Each check uses [Bubblewrap 0.9.0's options](https://github.com/containers/bubblewrap/blob/v0.9.0/bubblewrap.c)
with a cleared environment, fresh network/process/user namespaces and read-only
software/source mounts. Host home, broker credentials, Docker sockets and
cross-distribution mounts are excluded. One owned output directory and private
`/tmp` are writable. A namespace failure blocks dependent examples. Native logs
remain under `~/projects/us-equities-runtime/acceptance/run.*`; the staged handoff
contains the outer run logs and status rows, rather than these per-check logs.

The Nautilus file is unchanged, hash-checked in the executing process and uses
10,000 synthetic EUR/USD bars. DuckDB transcribes its pinned in-memory query;
Pandera uses its three-row README schema. skfolio's minimum-variance example
uses its wheel-bundled SP500 loader; arch fits its notebook's bundled SP500
input. Added assertions make these local integration smoke checks. DVC and
MLflow were imported; their remotes, services and backends were not exercised.

The two earlier blocked/failed attempts remain published. The first install
exited 69 at the uv-version prerequisite; acceptance exited 1 with all checks
blocked. The second install exited 2 because `--managed-python` conflicted with
`UV_PYTHON_PREFERENCE=only-managed`; acceptance again exited 1. The successful
attempt supplied uv 0.12.17 through mise and used the corrected Python discovery
command. Both final scripts exited 0.

## Open qualification

- Ratify supplemental **CPython 3.12.3 against 3.13**, including the foundation's
  3.13.15 alternative, and ratify the complete runtime matrix on frozen matching
  engine/adapter inputs. A successful 3.12.3 smoke does not complete this comparison.
- Complete the **EdgarTools 5.59.1 overturn test** before moving catalog 5.58.0:
  compare the relevant 10-K/10-Q section-boundary and 10-K breadcrumb cases. The
  [5.59.0](https://github.com/dgunning/edgartools/releases/tag/v5.59.0) and
  [5.59.1](https://github.com/dgunning/edgartools/releases/tag/v5.59.1) release
  references and the [definitive comparison](../../../evidence/artifacts/new-wsl-definitive-defaults-20261001/trading/trading-definitive.compact.json)
  remain preparation evidence; this run did not parse or acquire SEC filings.
- Qualify point-in-time US-equity/filing data, rights, identities, revisions,
  corporate actions, delistings, cost/liquidity assumptions and chronological
  evaluation. The already inspected 2021 control is not an untouched holdout.
- Qualify rc5 IBKR risk/recovery and each broker's separate paper lifecycle:
  order/cancel/fill/flatten, reconnect with open orders, restart reconciliation,
  durable journals, numeric bounds, alerts and independent kill switch.
- Establish LEAN container parity with frozen retained oracle cases and clarify
  image/source reproducibility. Pulling the image does not close either gate.
- Obtain an independent review of the imported historical host receipt. The
  supplied second Claude PASS concerns prepared r2 files; its verdict artifact
  and a post-run independent observation were not included in the staged bundle.

Paper credentials stay on NativeStack and are never copied across distributions.
Later paper operation on 2604 needs its own placement/configuration, native
sign-in and entitlements, unique client IDs and coordinated single-writer
ownership. Existing paper authorization remains as recorded in
[paper-lane-policy.md](../../../docs/paper-lane-policy.md). This package creates
no paper runner, live entrypoint, credential provision, service or paid hosting.
