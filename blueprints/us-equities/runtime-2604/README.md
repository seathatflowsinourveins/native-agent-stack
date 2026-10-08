# NativeStack2604 offline research runtime — October 4, 2026

The selected research runtime installed successfully on NativeStack2604 and all
**25 offline acceptance checks passed** on October 4, 2026, from
**21:17:20Z to 21:23:33Z**. This is historical host-local execution of native
software. The [run receipt](../../../evidence/receipts/native-trading-runtime-2604-20261004.json)
retains the recorded results and failed attempts; packaging these files does not
repeat installation or acceptance. That recorded run used **EdgarTools 5.58.0**
and lock SHA256 `c6b5f25cd3198c1b847c1cb602fe5441dce7e038aa16976c46ecf5f0beb7b086`.
No paper or broker execution occurred.

The current bundle selects **EdgarTools 5.60.0**, matching the catalog after
[native SEC index acceptance on NativeStack](../catalyst-provenance/native-network-edgartools-5600-20261004.json).
NativeStack2604's recorded installation and **25/25 offline checks passed** at this
pin on **2026-10-05, 01:00:17Z–01:01:07Z**, at commit `d02c0827` on lock
`4c98672d14147a1b`. The [rerun receipt](../../../evidence/receipts/native-trading-runtime-2604-rerun-20261005.json)
records this separate execution; independent review remains pending. The earlier
receipt continues to describe its 5.58.0 execution. These runs predate the current
DVC-free bundle; its separate [24/24 acceptance](#current-acceptance-and-pipeline-evidence--2026-10-08)
is recorded below.

The current lock SHA256 is
`1fb9f8ca6fef9c47a4ded826ddf20012f78d6643926cce3a36b86c674f55eb9c`.
The [2026-10-05 DVC removal](../../../evidence/artifacts/trading-runtime-2604-20261004/diskcache-removal-20261005.json)
reduces the lock from 242 to 188 entries, including project metadata. All 187
retained distributions have unchanged versions and archive hashes; only the
project metadata, removed dependency closure and obsolete build constraint change.
The [lock comparison](../../../evidence/artifacts/edgartools-5600-20261004/runtime-lock-change.json)
records the preceding EdgarTools version/artifact change and project requirement
metadata; all other 240 entries were unchanged at that step. The subsequent
round-c build-constraint relock added only lock manifest metadata, leaving all
242 package entries identical before DVC removal. The
[this-host import smoke](../../../evidence/artifacts/edgartools-5600-20261004/this-host-import-smoke.json)
passes the exact acceptance import/version assertion in a hash-locked 42-package
CPython 3.12.3 environment with networking disabled; its old-version control
fails as expected. The affected recipe tests and dependency check pass.

The packaging worker has native uv 0.12.17 but no Linux mise executable. The
requested mise relock route exits 127 here; resolution and `uv lock --check`
succeed with that native binary and the identical settings below. The
[destination-host rerun](../../../evidence/receipts/native-trading-runtime-2604-rerun-20261005.json)
records successful installation and offline acceptance. Under
`mise exec uv@0.12.17`, the install script ran the shared sync vector:
`uv lock --check`, `uv sync --locked --no-dev` and `uv pip check`, as
[sync-trading-2604.sh](sync-trading-2604.sh#L14) shows. Both relocks used the
installed native uv 0.12.17 executable on the packaging worker, with mise
unavailable: the EdgarTools upgrade (`uv lock --upgrade-package edgartools`)
produced lock `6b4e6a4d`, as recorded in the
[lock comparison](../../../evidence/artifacts/edgartools-5600-20261004/runtime-lock-change.json);
the round-c build-constraint relock produced then-final lock `4c98672d14147a1b`, as
recorded in the
[build-constraint proof](../../../evidence/artifacts/trading-runtime-2604-20261004/build-constraint-proof.json).
Neither relock ran through mise.
Independent review remains pending. The installer still enforces uv 0.12.17;
no shim or host-guard bypass is used.

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

Keep both host scripts and `sync-trading-2604.sh` beside `trading-2604-runtime/`. Its `pyproject.toml` and
`uv.lock` carry the directed 5.60.0 pin move and the 2026-10-05 removal of unused DVC.
The lock contains
188 package entries, including project metadata; it is not a claim of 188
installed distributions. The installer checks both embedded SHA256 values and
refuses arbitrary modified project metadata on rerun. It can migrate the exact
approved round-1 or recorded round-c project/lock hashes, including a partly completed migration;
both files are checked before either is replaced atomically. It checks the lock,
runs `uv sync --locked --no-dev`, then runs `uv pip check` on the project
environment, failing closed at every step. The mise route below supplies uv
0.12.17, enforced by the installer's version gate. The retained `exclude-newer`
cutoff is `2026-10-06T04:00:00Z`, after 5.60.0's October 2 publication, so it needs
no change. The delivered lock freezes the set.

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
both images. An incomplete install blocks all 24 checks in the current recipe.

## Wheel census and shared sync

The current lock has no nonvirtual package without any wheel. Removing DVC
also removes `antlr4-python3-runtime`, its only such package, and the runtime
`setuptools` dependency. The unused build constraint and lock manifest entry
are removed together. The source-build evidence below remains historical.

[tests.test_trading_2604_lock](../../../tests/test_trading_2604_lock.py) checks the
census of packages without any wheel, rejects unused project or lock manifest
build constraints, and prevents DVC, dvc-data or diskcache from returning to this
bundle. Planted fixtures reject a package without any wheel, stale constraints
and a reintroduced diskcache entry. It also checks that every direct dependency
agrees with the install and acceptance pin matrices. The virtual project entry
has no distribution archive and is excluded from the census. This test does not
check target-compatible wheel coverage under Linux markers.

[sync-trading-2604.sh](sync-trading-2604.sh) defines the sole host/CI argument
vector and its Python/uv/cutoff pins. The installer verifies its SHA256 before
sourcing and calling `sync_trading_2604`; future trading-native CI will source
and call the same function with its own clean `safe` command-prefix array,
`project` and managed `runtime_python`. It checks the lock, syncs with
`--locked --no-dev`, then checks installed dependencies, stopping on any error.
The test compares every recorded argv byte between the installer call and a
direct shared-source call, rejects retyped or altered installer calls and stale
source hashes, and plants failures at all three steps. This follows the
[repository's install-command pin pattern](../../../.github/workflows/validate.yml#L196-L225).

## Round-c source-build evidence (historical)

Before DVC removal, the only nonvirtual lock distribution without a wheel was
`antlr4-python3-runtime==4.9.3`. Its source archive lacks `pyproject.toml`, so
[uv 0.12.17's legacy backend](https://github.com/astral-sh/uv/blob/0.12.17/crates/uv-build-frontend/src/lib.rs#L53-L60)
otherwise resolves `setuptools>=40.8.0` separately. Round c used uv's
[hash-carrying build constraint](https://github.com/astral-sh/uv/blob/0.12.17/docs/concepts/projects/build.md#L61-L79)
and [schema](https://github.com/astral-sh/uv/blob/0.12.17/uv.schema.json#L788-L815)
to pin **setuptools 84.0.0** with exactly the runtime lock entry's wheel and
sdist SHA256 values. That lock manifest records both hashes. Native uv 0.12.17
performed this relock because mise remains unavailable to the packaging worker;
Python 3.12.3, prerelease `if-necessary`, the PyPI default index and
`exclude-newer=2026-10-06T04:00:00Z` are unchanged. No package version or archive moved.

The [build-constraint proof](../../../evidence/artifacts/trading-runtime-2604-20261004/build-constraint-proof.json)
records a this-host cold-cache sync with managed CPython 3.12.3 and antlr4's
installed WHEEL generator, plus three negative controls. Invalid-only hash
controls remove the valid alternative archive hash; retaining that alternative
can legitimately succeed. A fresh resolution exercises the backend download,
while the locked-sync control preserves runtime archive hashes. These are local
integration and structural checks. The earlier 25/25 summary is **pre-relock
evidence**; NativeStack2604's rerun on that round-c lock is recorded in its
[separate receipt](../../../evidence/receipts/native-trading-runtime-2604-rerun-20261005.json),
with installation and 25/25 offline checks passing. Independent review remains
pending.
The current DVC-free bundle uses a new completion marker and still needs its own rerun.

## Pinned sources

| Component | Delivered pin | Primary source |
| --- | --- | --- |
| CPython / uv | 3.12.3 / 0.12.17 | [Adapter's tested Python line](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/requirements.txt), [retained rc5 runtime](../../../evidence/receipts/native-nautilus-v2-20260920.json), [uv Python installation](https://github.com/astral-sh/uv/blob/0.12.17/docs/guides/install-python.md) and [locked sync](https://github.com/astral-sh/uv/blob/0.12.17/docs/concepts/projects/sync.md) |
| NautilusTrader / IBKR adapter | 2.0.0rc5; source `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`; in-tree Rust ibapi 3.3.0 | [Installation](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/getting_started/installation.md), [IBKR integration](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/integrations/interactive_brokers.md) |
| alpaca-py | 0.44.0 | [README at cc4cb3b7](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/README.md) |
| Separate Alpaca adapter | `dca821cca85dce3647fa7b488d5a23fbe5b85d4a` | [Native adapter source](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/native_adapter.py) |
| EdgarTools | 5.60.0; source `1e7a61b3a142dbf5d19bc82444f85239c1786348` | [Release](https://github.com/dgunning/edgartools/releases/tag/v5.60.0), [README at the tag commit](https://github.com/dgunning/edgartools/blob/1e7a61b3a142dbf5d19bc82444f85239c1786348/README.md), [native SEC index receipt](../catalyst-provenance/native-network-edgartools-5600-20261004.json) |
| exchange_calendars | 4.13.2 | [README at dbe38b1f](https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/README.md) |
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

## What the recorded historical acceptance establishes

The recorded 25-check runs (locks `c6b5f25c` and `4c98672d`) covered isolation,
Python, 14 package imports/versions,
IBKR config-class exports, separate Alpaca source integrity and import, the
unchanged Nautilus quickstart's checksum and execution, and four example checks.
The host receipt's `native_proven` claim is scoped to actual native engine use;
the companion receipt labels each local probe and adapted example separately.
No complete unchanged upstream test suite was run.
The current recipe has 24 checks with 13 import probes and no DVC import;
its NativeStack2604 qualification is pending.

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

## EdgarTools pin move — 2026-10-04

The [5.60.0 tag](https://github.com/dgunning/edgartools/tree/1e7a61b3a142dbf5d19bc82444f85239c1786348)
resolves to the full commit shown in the table. [PyPI metadata](https://pypi.org/pypi/edgartools/5.60.0/json)
and the [retained source verification](../../../evidence/artifacts/edgartools-5600-20261004/release-evidence.json)
record both artifact hashes, upload times, complete check-suite results and exact
open-issue searches. Those searches found one recent MCP Registry metadata issue
and no bug/regression issue naming the requested versions; that registry issue
does not concern the runtime's native SEC APIs.

| CI evidence | Commit and result |
| --- | --- |
| [Build and Test 37032606429](https://github.com/dgunning/edgartools/actions/runs/37032606429) | Release-day push, October 2, tag commit: SUCCESS |
| [Regression Tests 37032606490](https://github.com/dgunning/edgartools/actions/runs/37032606490) | Release-day push, October 2, tag commit: SUCCESS |
| [Scheduled Build and Test 37122012086](https://github.com/dgunning/edgartools/actions/runs/37122012086) | October 3, same tag commit: FAILURE in the clock-dependent cassette tests described below |
| [Scheduled Build and Test 37204026582](https://github.com/dgunning/edgartools/actions/runs/37204026582) | October 4, later main `237e866a80ab3013cf5aa25a2557cf73c4eb61e4`: SUCCESS; separate from tag CI |

The failed run names the same two tests in all three affected jobs:
`tests/issues/regression/test_issue_893_ttm_staleness.py::test_goog_ttm_revenue_tracks_recent_window`
and `::test_amzn_ttm_revenue_matches_reference`. `test-strict-errors` fails
`assert ttm.is_stale is False`: the cassette's newest period ends at Q1 2026,
while staleness uses the live clock. `test-fast` on 3.10 and 3.13 fails the offline
audit, which identifies those two fast-marked tests as requiring the SEC. The
[first clock fix](https://github.com/dgunning/edgartools/commit/9ea5def31b73816a12fe6ce1a2f3ff68cbdbb33b)
and [calculator-only clock fix](https://github.com/dgunning/edgartools/commit/156c45b327a65e4c86ebfc7652edb778de5cecd8)
each change only that test file, verified through GitHub's commit file lists.
The coordinator's diagnosis identifies a clock-dependent test defect rather than
a library regression. `Company.get_facts().get_ttm_revenue()` staleness is outside
this runtime's filing index, filing documents, SGML headers, company/CIK lookup
and XBRL fact-extraction paths.

Later main also changes `edgar/documents/utils/section_slicer.py` and
`edgar/httprequests.py`; those library changes are **absent from 5.60.0**. The
October 4 main pass is corroborating test-repair evidence, not a new pass of the
release binary or a claim that those changes are delivered here.

The [5.59.0](https://github.com/dgunning/edgartools/releases/tag/v5.59.0),
[5.59.1](https://github.com/dgunning/edgartools/releases/tag/v5.59.1) and
[5.60.0](https://github.com/dgunning/edgartools/releases/tag/v5.60.0) notes cover
filing section boundaries and breadcrumbs, SGML error propagation, XBRL debt and
liability corrections, current-feed timeouts, combined TOC items, paragraph
whitespace and exact exhibit selection. These changes matter to reproducible
SEC research; previously pinned text and values need their version provenance.

The [supplied offline-fixture evidence](../../../evidence/receipts/edgartools-5600-pin-move-20261004.json)
records a complete two-member index fixture and document parsing in a 42-package
scratch environment on NativeStack, with no SEC identity or SEC request. Markdown
is 5,308 bytes at 5.60.0 versus 5,325 at 5.58.0 and 5.59.1; the change removes
source-HTML soft line breaks, with identical whitespace-normalized text at 5,218
characters. That local fixture evidence is distinct from
[native-sec-edgartools-5600-20261004](../catalyst-provenance/native-network-edgartools-5600-20261004.json):
the latter records one HTTP 200, zero retries, 371 index rows and five matching
selected CIK/accession rows on NativeStack with CPython 3.12.3. Together with the
directed move, it supersedes the 5.59.1 overturn item and moves `data-edgartools`
to 5.60.0. It does not qualify broader data, strategy or broker gates. The
[separate NativeStack2604 rerun](../../../evidence/receipts/native-trading-runtime-2604-rerun-20261005.json)
records installation and 25/25 offline acceptance at this pin on lock `4c98672d14147a1b`;
independent review remains pending.

## Diskcache advisory and unused DVC removal — 2026-10-05

[PYSEC-2026-2447](https://osv.dev/vulnerability/PYSEC-2026-2447)
([GHSA-w8v5-vhqr-4h9v](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v))
affects diskcache through 5.6.3: an attacker who can write its SQLite cache or
value files can trigger Python pickle deserialization on a subsequent cache
read. The [5.6.3 implementation](https://github.com/grantjenks/python-diskcache/blob/323787f507a6456c56cce213156a78b17073fe00/diskcache/core.py#L254-L284)
confirms that path. No fixed release is listed by OSV; the latest published
[diskcache release](https://pypi.org/pypi/diskcache/json) remains 5.6.3.
The latest published [dvc-data 3.18.3](https://pypi.org/pypi/dvc-data/3.18.3/json)
still [requires diskcache](https://github.com/treeverse/dvc-data/blob/56af66a26d8c140b812e6a75b3f0cc0c6e77628d/pyproject.toml#L29),
and [DVC 3.67.1](https://pypi.org/pypi/dvc/3.67.1/json)
still [requires dvc-data](https://github.com/treeverse/dvc/blob/356dfa03278058b02df42124f243c2c345329dae/pyproject.toml#L44).

The delivered recipe called DVC only for an import/version probe; no DVC
repository, stage, remote or cache operation serves these offline examples.
Removing its direct dependency removes dvc-data and diskcache without an OSV
ignore. Native uv 0.12.17's supported
[dependency removal](https://github.com/astral-sh/uv/blob/0.12.17/docs/concepts/projects/dependencies.md#L92-L104)
and relock preserve the existing Python, prerelease, index and cutoff settings.
Both CI inventory groups pass OSV-Scanner 2.6.0 with their existing configs.
The [removal artifact](../../../evidence/artifacts/trading-runtime-2604-20261004/diskcache-removal-20261005.json)
records the advisory reads, unchanged retained artifacts, removed closure and
red/green scans. These are packaging-worker checks; the historical destination
host receipts remain unchanged. A future demonstrated DVC workflow requires a
separate reviewed dependency and cache-security decision before reinstatement.

## Current acceptance and pipeline evidence — 2026-10-08

The [5a acceptance receipt](receipts/acceptance-20261008.json) records **rc 0,
24/24 PASS** on NativeStack2604 from **06:20:48Z to 06:21:25Z**, using the installed
runtime at lock `1fb9f8ca6fef9c47`. The unchanged `accept-trading-2604.sh` ran from
the co-op's native WSL shell. This is this repository's offline integration
acceptance; it establishes no upstream test-suite pass and did not repeat
installation. The prior 25/25 result on lock `4c98672d14147a1b` remains historical,
with its independent review pending.

Attempt 1 is retained: the readiness-runner's shell lacked `WSL_DISTRO_NAME`, so
the script's own host guard at line 49 returned rc 1 with all 24 checks BLOCKED.
The co-op's shell receives the NativeStack2604 value from WSL itself; the guard
was unchanged and no value was set by hand. Later guarded scripts run through
the co-op's native shell.

The [5b pipeline receipt](receipts/backtest-pipeline-20261008.json) records a
completed Alpaca-history-to-NautilusTrader rc5 backtest on NativeStack2604,
repeated with identical results. Its inputs are AAPL, MSFT, AMZN and GOOG daily
bars for 2025-01-06 through 2025-01-31 and a fixed buy/close schedule. This
establishes the pipeline only. The original run used provider midnight plus
24 hours for bar timestamps; the XNYS-close correction belongs to the later
entrance exam. Layer 1.5 CIK identity, split verification, delisting and
terminal-price gates remain unaccepted, so this receipt establishes no strategy
eligibility or performance claim.

## Open qualification

- Ratify supplemental **CPython 3.12.3 against 3.13**, including the foundation's
  3.13.15 alternative, and ratify the complete runtime matrix on frozen matching
  engine/adapter inputs. A successful 3.12.3 smoke does not complete this comparison.
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

The command center's 2026-10-08 item `task-ns2604-coop-20261008T060802Z`, §6,
designates **NativeStack2604 as the only trading host**, holding the runtime,
trading data and paper credentials. It supersedes the earlier NativeStack-only
credential placement statement. Historical NativeStack receipts retain their
original host and scope. Paper operation on NativeStack2604 still requires
broker-specific configuration, native sign-in and entitlements, unique client
IDs and coordinated single-writer ownership. Existing paper authorization remains as recorded in
[paper-lane-policy.md](../../../docs/paper-lane-policy.md). This package creates
no paper runner, live entrypoint, credential provision, service or paid hosting.
