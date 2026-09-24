# Incomplete historical WSL retrieval reference

The retained September 20, 2026 receipts are an **incomplete historical fixture
reference**. They do not establish native E2E or adoption acceptance. Per-command
`argv` and working directories were not retained, and the original private raw-log
locations could not be verified. Selected outputs and hashes can be checked for
consistency, but cannot independently identify the commands that produced them.
The historical QMD installation also disabled all npm lifecycle scripts, which is
not the supported fresh-host recipe. The current assessment therefore defers
acceptance in [experiment.json](experiment.json).

The receipts report these outcomes, without a new native run during offline review:

| Retained attempt | Reported outcome | Recorded commands |
| --- | --- | --- |
| [Source attempt 1](source-receipt.json) | 22 checks passed | 6 |
| [QMD attempt 1](qmd-attempt-1.json) | URI-checker assertion failed | 5 |
| [QMD attempt 2](qmd-receipt.json) | 70 checks passed | 17 |

The source fixture contains the frozen planner from repository revision
`6f74bc503ccecaaf6ccebd53677b23aedab50921`. Its selected ripgrep **15.2.0** and
ast-grep **0.45.3** results contain exact file lines, byte spans and source text.
The QMD **2.8.3** fixture reports Node **24.21.0**, better-sqlite3 **13.0.3** and
sqlite-vec **0.1.9**, with the retained [package lock](package-lock.json). It covers
five positive and two negative queries, Unicode, a one-line `get`, process reopen,
update and deletion in a three-document primary collection plus one decoy.
The final recorded database has integrity `ok`, three active documents and zero
vector rows. These are receipt contents, not independently recovered execution.

These locally authored integration checks use synthetic documents and a frozen
source file. Under the [acceptance evidence policy](../../../docs/acceptance-evidence-policy.md),
they cannot substitute for unchanged upstream tests. No semantic RAG, production
corpus, native client, service, inference, OS-confinement or token-saving acceptance
is claimed. Output bounds are assertions after capture, not streaming limits.

## Preserved history and the provenance gap

The initial QMD checker compared an entire URI with a bare collection/path. The
selected output included the expected body and `?index=wsl-retrieval-fixture`, but
`qmd-positive-0_paths` failed. [run-initial.py.txt](run-initial.py.txt) preserves the
source attempt and failed QMD attempt's runner. The corrected historical runner
is now archived as [run-qmd-attempt-2.py.txt](run-qmd-attempt-2.py.txt), with its
original SHA-256 `4cbcceac02158629ca78262aaa826c995c21bbe45fa83481f7c139f16a6c52d2`.
The successful QMD receipt originally mapped `run.py` directly; the offline audit
now resolves that historical name to the archived bytes. Neither receipt was
rewritten to pretend it recorded today's file or missing invocation metadata.

The [install receipt](install-receipt.json) still records the actual historical
`npm ci --ignore-scripts --omit=optional` action. Its contents and digest are
unchanged. The [inventory](install-inventory.json) reports no optional llama
backend or model files, but does not qualify fresh native dependency setup.
[pins.json](pins.json) and [source-review.json](source-review.json) preserve dated
identities; release currency remains September 20, without a new latest-release
claim from the September 23 offline completion or subsequent review.

Original handoffs reported full stdout/stderr logs under private run directories.
Their exact locations remain unavailable, and those logs have not been reopened.
No command line or working directory has been reconstructed as an observation.
The historical [verification.json](verification.json) preserves the earlier
18-test offline check record; its original acceptance wording is superseded by
this incomplete assessment. Failed attempts and original evidence remain intact.

## Offline verification

From the repository root:

```sh
python3 blueprints/convergence-practice/wsl-retrieval/audit.py
python3 -m unittest tests.test_wsl_retrieval -v
python3 scripts/validate_convergence.py \
  blueprints/convergence-practice/wsl-retrieval/experiment.json --root . --json
python3 scripts/validate.py
```

The [audit](audit.py) requires the exact frozen-input and check-name sets for all
three receipts before comparing hashes and results. Mutation regressions reject
omitted inputs and same-count replacement checks as well as incorrect spans,
source bodies, URI scope, stale updates, erased failures and unsupported claims.
A zero audit exit means retained facts are consistent; its result explicitly
reports `native_acceptance_established: false`. It cannot repair missing evidence.

## Future command capture and supported installation

[run.py](run.py) is a future recording aid. It now retains each attempted command's
sanitized argument vector and working directory before launch, preserves argument
boundaries, and records failed launches and timeouts. Private path roots become
scope markers such as `<RUN>` and `<NODE>`; original historical facts receive no
fabricated fields. Mocked regressions exercise this recording without invoking
native retrieval. Both previously executed runner versions remain archived.

For a separately authorized fresh QMD trial, follow the maintained
[QMD native recipe](../../../recipes/README.md#component-catalog-install-and-check) and
[native token fixture guidance](../../../docs/native-token-ci.md). The supported
installation control is:

```sh
NODE_LLAMA_CPP_SKIP_DOWNLOAD=true npm install --global \
  --prefix "$NEW_OWNED_QMD_PREFIX" @tobilu/qmd@2.8.3
```

Required npm dependency lifecycle scripts remain enabled. Do not reuse the
historical blanket `--ignore-scripts` command as a fresh-host recipe. The retained
lock and optional-backend assertions describe the historical prefix; they do not
prove compatibility of a newly installed prefix. Use the maintained native fixture
for current supported installation acceptance, retaining its actual install and
runtime commands and outputs. This review performs no install or native rerun.

Acceptance requires recovered verifiable historical invocation evidence or a
separately authorized reachable-host trial with supported installation and complete
command capture. Preserve native accounts, model/effort settings, caching and
compaction. No automatic history capture is introduced. Whole-task provider,
parent/child/retry/cache usage remains unknown; no savings claim is made.
