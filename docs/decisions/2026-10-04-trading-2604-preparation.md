# 2026-10-04 — Package the NativeStack2604 offline research runtime

North-star action: retain the selected NautilusTrader 2.0.0rc5 research and
historical-simulation runtime as a portable, source-cited recipe with truthful
host-local evidence, preserving separate IBKR and Alpaca paper qualification.

## Decision and sources

Package job-031's repaired scripts under
`blueprints/us-equities/runtime-2604/`, with their required sibling
`trading-2604-runtime/` project. Follow existing feature recipes such as
`blueprints/us-equities/research-runtime/` and the retained native rc5 receipt
`evidence/receipts/native-nautilus-v2-20260920.json`. Reuse the repository's
`scripts/host_receipts.py`, `adoption/host-receipt.schema.json`, publication
validators and evidence registration helper at packaging base
`38ac9aca114ad9ef4a15d8620d947eb5c2f518c3`; no new recorder or test runner is added.

The bounded search-first pass found those existing packaging and recording
interfaces sufficient. No package, skill or runtime replacement is selected and
no network discovery or new trial is needed for this archival unit. The exact
upstream pins and file locators inherited from the preparation are in the
[runtime README](../../blueprints/us-equities/runtime-2604/README.md) and scripts.
They include [uv 0.12.17's project workflow](https://github.com/astral-sh/uv/blob/0.12.17/docs/guides/projects.md)
and [lock semantics](https://github.com/astral-sh/uv/blob/0.12.17/docs/concepts/projects/sync.md),
the [unchanged rc5 quickstart at 1b0a49d2](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/getting_started/quickstart.py),
the [Alpaca source at dca821cc](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/native_adapter.py),
[Git 2.43.0 sparse checkout](https://github.com/git/git/blob/v2.43.0/Documentation/git-sparse-checkout.txt),
[Docker v29.8.1 context inspection](https://github.com/docker/cli/blob/v29.8.1/docs/reference/commandline/context_inspect.md)
and [Bubblewrap v0.9.0](https://github.com/containers/bubblewrap/blob/v0.9.0/bubblewrap.c).

Keep CPython **3.12.3**, uv **0.12.17**, all 14 direct requirements, the MCP and
pandas extras, source pins and immutable OCI image indexes as delivered. The
515-byte project and 353,069-byte lock remain byte-identical to the staged copies:

| File | SHA256 |
| --- | --- |
| `pyproject.toml` | `581bbb38a265068791c1a8c92435f9859876fd613d3c2c87d618a223376b01e0` |
| `uv.lock` | `c6b5f25cd3198c1b847c1cb602fe5441dce7e038aa16976c46ecf5f0beb7b086` |

The 242-entry lock retains cutoff `2026-10-06T04:00:00Z`. Delivering and checking
the actual lock prevents a fresh resolution against that future cutoff. The
canonical runtime target remains a selected engine plus Python compatibility
range; this receipt does not ratify an exact patch or complete canonical matrix.

Alternatives were a global install, a fresh target-host resolution, the
foundation's 3.13.15 supplemental Python pin, a newer arbitrary 3.12 patch,
replacement analysis tools, or treating a container pull as a replacement LEAN
oracle. The retained approach follows the requested scope and the
[adapter's tested Python 3.12 line](https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/requirements.txt)
and earlier rc5 execution on 3.12.3. A frozen same-input 3.12.3-versus-3.13
comparison with better upstream support and passing engine/adapter behavior would
overturn this supplemental choice, with a new verified lock and trading-lane
ratification. A newer release or successful import alone is insufficient.

## Preparation, review and corrections

The staged decision and readiness documents record a preparation phase without
runtime execution. Its initial 3.13.15, 203-entry lock was superseded by repaired
3.12.3 metadata and the delivered 242-entry lock with `mlflow[mcp]==3.16.1`.
The supplied r1 Claude verdict contains two P1 findings, one P2 finding and 15
residuals. Repaired code uses an indexed pinned sparse checkout before checking
cleanliness, preserves the selected rootless Docker endpoint across `env -i`,
and calls core utilities natively. It also gates acceptance on completion and
both exact images, verifies adapter source before import and cleans pending
temporaries through its final status handler.

The preparation records public checkout, trap-fragment and dependency-metadata
proofs. Those scratch artifacts were not staged for packaging and are not
promoted into newly verified public execution. The supplied handoff reports the
second Claude read of r2 as PASS; its verdict file was not supplied. That review
of prepared files is separate from independent observation of the later run.

Two coordinator corrections are substantiated by the retained host logs:

- The host default uv **0.12.22** fails the required **0.12.17** version gate at
  exit **69**. `mise exec uv@0.12.17` supplies the pinned tool; the next attempt's
  native version output reports 0.12.17. Exact uv source guidance is linked above.
- `uv python find --managed-python` conflicts with the already supplied
  `UV_PYTHON_PREFERENCE=only-managed`: native output reports the argument conflict
  and install exit **2**. The final command keeps `--system --no-project
  --no-python-downloads` and removes the redundant flag. The final install exits
  **0**. Both corrections are preserved in the scripts and dated run receipt.

The original export concern was corrected during preparation by reading the
complete [Rust/PyO3 registration](https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/adapters/interactive_brokers/src/python/mod.rs#L98)
behind the Python facade. The offline `ibkr_adapter` row later passes its named
imports; that is config/export acceptance, not a broker connection.

## Historical evidence and publication

The [companion receipt](../../evidence/receipts/native-trading-runtime-2604-20261004.json)
is `native_cli_e2e`, retaining all 25 rows, software pins, exact staged summary,
sanitized outer logs and both unsuccessful attempts. The separate
`host_acceptance` receipt follows the one-component/one-host/one-stage schema for
the landscape winner **nautilustrader**, scoped to native offline engine use.
It records the combined successful install/accept batch at stage `use`, because
the staged timestamps measure that batch rather than each script separately.
The normalized sequential command display and the combined **373 s** duration
are explicitly bounded; individual script durations and the outer coordinator
argv were not staged. No install-only host receipt with an invented duration is
created. The host is another WSL distribution, with no evidence of a second
physical machine; `second_physical_machine` is false.

Host class `native_proven` covers the unchanged native engine example. Local
import/version/hash/isolation probes and transcribed examples are separately
labelled `local_integration`; synthetic FX/three-row inputs and bundled SP500
fixtures retain their input limitations. Structural publication checks do not
repeat the run. No broker, paper account, market-data request, provider inference,
container execution, strategy merit or new upstream-suite pass is claimed.

Publication replaces five home-path occurrences in the successful outer log
with `~`, preserves native status/exit lines and all public source/image hashes,
and hashes only published sanitized output. Private source-job state paths,
account identifiers and raw review conversations are excluded. Every touched
publication file is scanned explicitly and registered last with `register_file`;
derived host reports use only their supported `--write` commands. The dated
runtime-target followup records evidence without moving selections or gates.

Packaging correction: the first transcription assertion failed at exit 1 because
its status-name character class admitted a newline. Anchoring each row with a
non-whitespace name corrected that parser; the second import exited 0 and checked
all 25 named native rows against the staged summary. This was an archival parsing
correction, not a new failed or successful host acceptance attempt.

The first full publication validation also exited 1: its home-path pattern
mistook the synthetic sandbox cache path for a personal user directory. The
published acceptance script now names its existing synthetic home through
`sandbox_home` and expands that variable in the same mount/environment arguments.
The actual sandbox argv is unchanged. The validator is preserved, and this
source-representation change is covered by renewed syntax and publication scans.

The guarded Gitleaks launcher exited 1 before scanning because it opens the
existing per-user runtime lock for writing in a read-only directory. The installed
8.30.1 native `dir --help` and launcher source were read. A native retry retained
that same lock through a read-only descriptor, but exited 2 before scanning:
a 4 GiB virtual-address cap could not accommodate RE2/WASM's 4 GiB reservation
plus the runtime. Raising that process cap to 6 GiB, matching the launcher's
maximum, preserved the exclusive lock, 60-second native timeout and nice 19;
the scan of the isolated 21-file publication copy exited 0, scanned about
3.78 MB and found no leaks. No host launcher, lock file or configuration changed.
This reuses [Gitleaks v8.30.1](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md)
and the repository's [documented bounded directory-scan practice](../../adoption/tools/README.md).
Both failed scan conditions remain distinct from runtime acceptance.

The staged result summary has no final newline; its bytes are preserved. All
published new files have zero trailing whitespace. The separate `git diff
--no-index --check /dev/null FILE` checks returned the expected difference exit 1
for each new file with no whitespace diagnostics; the working-tree
`git diff --check` passed at 0.

The required scoped ai-memory lookup was attempted with `pin_first=true,
limit=2` and rejected by automatic approval review: the tool requires approval
while this session's policy is `never`. No memory result is claimed. Current
canonical files and original staged artifacts supply this packaging evidence.

## Open comparisons and completeness critic

Ratifying **Python 3.12.3 against 3.13** remains open. The **EdgarTools 5.59.1
overturn test** also remains open before changing catalog 5.58.0. It must examine
the relevant 10-K/10-Q section boundaries and 10-K breadcrumb regression, as
identified by the preparation's
[5.59.0](https://github.com/dgunning/edgartools/releases/tag/v5.59.0) and
[5.59.1](https://github.com/dgunning/edgartools/releases/tag/v5.59.1) references
and definitive source supplement. This offline run exercises neither filings
nor that comparison. Canonical matrix ratification, point-in-time data, realistic
chronological evaluation, LEAN oracle parity and separate rc5 IBKR/Alpaca paper
risk, recovery and operational qualification remain open.

Completeness critic: preserve failed attempts as well as the green summary;
separate the synthetic/bundled input modality from actual native execution;
retain the delivered lock rather than treating the future cutoff as a freeze;
and distinguish pre-run review from missing post-run observation. The next
trading-lane qualification should target the Python and EdgarTools comparisons,
per-check native logs, missing discriminating controls for local smoke checks,
domain data, broker recovery and source-to-image/oracle parity. Packaging performs
no new landscape convergence comparison, broker/provider call or runtime trial.
Independent review of the imported host receipt remains explicitly requested.
