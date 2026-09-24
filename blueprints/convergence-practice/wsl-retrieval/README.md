# Bounded native WSL retrieval

The retained September 20, 2026 Linux x86_64 runs qualify two selected retrieval
fixtures: **22 source checks across six native commands** and **70 QMD lexical
checks across 17 native commands**. [source-receipt.json](source-receipt.json)
and [qmd-receipt.json](qmd-receipt.json) preserve selected command outputs,
stdout/stderr digests, exact frozen inputs, and outcomes. These are historical
WSL observations. The September 23 completion work performs offline checks only.

Under the current [acceptance evidence policy](../../../docs/acceptance-evidence-policy.md),
these are locally authored integration checks with synthetic document fixtures
and a frozen repository source file. No unchanged upstream test suite was recorded
for these attempts. The retained native command results and independent artifact
audit support this limited fixture scope, not upstream-suite acceptance.

The source fixture uses ripgrep **15.2.0** and ast-grep **0.45.3** against the
frozen accepted planner from repository revision
`6f74bc503ccecaaf6ccebd53677b23aedab50921`. Independent Python string and AST
oracles check the exact file, lines, byte spans, and returned source text.
Absent queries return empty results; ripgrep and ast-grep both returned the
expected exit 1 for these recorded negatives.

QMD **2.8.3**, Node **24.21.0**, better-sqlite3 **13.0.3**, and sqlite-vec
**0.1.9** use the exact [package lock](package-lock.json). The three-document
primary collection and one-document decoy exercise five positive queries,
two absent/cross-collection queries, Unicode paths and bodies, a one-line `get`,
process reopen, update, and deletion. Search output must preserve the named
index, collection, path, line, and exact body. Successful searches return one
document within 2,048 bytes; the one-line `get` is within 1,024 bytes. The final
database has integrity `ok`, three active documents, and zero vector rows.

These fixtures establish selected lexical and structural retrieval behavior.
They do not qualify semantic RAG, a production corpus, default-index routing,
Codex/Claude integration, a service, or model inference. The source test does not
cover general ignore rules or every language. Result limits are fixture
acceptance checks after process capture, not a streaming memory limit.

## Preserved failure and provenance

The first QMD attempt stopped after five native commands because its checker
compared an entire URI with a bare collection/path. QMD returned the expected
document with `?index=wsl-retrieval-fixture`. The retained
[initial receipt](qmd-attempt-1.json) reports `qmd-positive-0_paths` as failed;
[run-initial.py.txt](run-initial.py.txt) preserves its executed bytes. The
correction in [run.py](run.py) parses the URI, checks the named index and
collection, and decodes the path. Attempt 2 passed. Both attempts remain in the
[convergence contract](experiment.json); the failed attempt is not an absent
answer or an extra successful run.

[pins.json](pins.json) preserves the exact release, binary, package, and license
identities. [source-review.json](source-review.json) extracts the existing
September 20 official-source preflight without private host paths. Its release
currency is dated to that review, not September 23. The package-install
[receipt](install-receipt.json) records successful lock creation and `npm ci`
with `--ignore-scripts --omit=optional`; [inventory](install-inventory.json)
records the Linux sqlite-vec binding and no optional llama backend or model
files. No install or download occurs in the offline completion checks.

Each native runner writes full per-command stdout/stderr, a partial receipt,
and the final receipt under its private run directory. The prior handoff reports
that these logs were retained, but their exact private subdirectories were not
available to the offline completion worker. The checked-in digests and selected
facts remain inspectable; the full historical raw logs were not reopened.
Hashes establish consistency of the retained evidence, not independent proof of
historical execution. The independent [audit](audit.py) verifies frozen runner
mappings and inputs, exact source spans and QMD bodies, the failed URI result,
dependency-lock identity, and declared scope.

## Offline verification

From the repository root:

```sh
python3 blueprints/convergence-practice/wsl-retrieval/audit.py
python3 -m unittest tests.test_wsl_retrieval -v
python3 scripts/validate_convergence.py \
  blueprints/convergence-practice/wsl-retrieval/experiment.json --root . --json
python3 scripts/validate.py
```

[verification.json](verification.json) records completion check exits and
limits. The 18 focused tests reject mismatched spans, bodies, URI scope,
unbounded `get` content, error-as-absence, stale updates, model artifacts,
erased failed attempts, changed frozen inputs, and unsupported usage claims.
The contract binds the receipts, both runners, fixtures, dependency metadata,
audit, and tests to their SHA-256 identities. Shared catalog registration and
publication belong to the coordinator.

## Deliberate native reproduction

Reproduction requires a reviewed Linux x86_64 host, the exact pinned native
executables and an already prepared private package prefix matching the lock.
Use a new private directory outside the checkout for each mode. The runner
does not install dependencies or fetch models:

```sh
python3 blueprints/convergence-practice/wsl-retrieval/run.py --mode source \
  --run-dir "$NEW_PRIVATE_SOURCE_RUN" \
  --source blueprints/convergence-practice/native-worker/accepted/planner.py \
  --rg "$PINNED_RIPGREP_BINARY" --ast-grep "$PINNED_AST_GREP_BINARY"
python3 blueprints/convergence-practice/wsl-retrieval/run.py --mode qmd \
  --run-dir "$NEW_PRIVATE_QMD_RUN" \
  --node "$PINNED_NODE_BINARY" --package-prefix "$OWNED_PACKAGE_PREFIX"
```

The current runner includes the URI correction; it cannot recreate the initial
checker's failure. Both original source-run and failed-QMD receipts map their
`run.py` hash to `run-initial.py.txt`. Reproduction would be a new observation,
not a refresh of the historical receipts.

QMD gets explicit `QMD_CONFIG_DIR`, `XDG_CACHE_HOME`, `QMD_FORCE_CPU=1`, and
`--index wsl-retrieval-fixture`. The real HOME is preserved. Only the copied
synthetic corpus is indexed, updated, or deleted. No persistent service starts,
no model command runs, and no native client, account, global index, or history
capture is configured. This is scoped execution, not OS confinement or an
independent network-traffic audit. Rollback is retiring only owned trial files
after preserving required evidence. Whole-task parent/child/retry/cache usage
remains unknown; no token-saving claim is made.
