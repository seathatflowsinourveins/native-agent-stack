# Qualification implementation evidence — 2026-10-02

This is implementation acceptance, not comparative backend qualification.
The selected production memory remains ai-memory; no replacement winner or
full native readiness is asserted.

The [deployment decision is closed](VERDICT.md). The prospective native
comparison and canary were not executed and are not queued. Completed source,
fixture and recovery checks retain their original scope.

| Evidence class | Observed result | Scope and limitation |
| --- | --- | --- |
| Local regression tests | `uv run --frozen python -m pytest`: 20 passed, exit 0 | Final source includes the extension-parent binding repair; deterministic fixtures only. |
| Dependency inventory repair | `python3 -m unittest -v tests.test_osv_lockfile_coverage`: 38 passed, exit 0 | Both package dependency files are registered; matching existing evidence hash/byte count refreshed. |
| Pre-push integration after repair | `python3 -m unittest -v tests.test_pre_push_gate`: 16 passed, no skips, exit 0 | Run against the committed inventory repair, since these tests read Git HEAD. |
| Actual upstream Inspect CLI integration | 12 samples, status success, zero sample errors, all scored 1.0; exit 0 | Authored development responses, `actual=false`, zero model events, empty model usage. This is not a model or backend quality result. |
| Unchanged upstream test | `tests/solver/test_solver.py::test_solvers_termination`: 1 passed, exit 0 | Inspect source `c05398d897affcb85bd4cb9d10a7c03e1779a18e`; `--noconftest -o addopts=` excludes unavailable moto/xdist setup. Initial setup failures are retained privately. |
| Actual isolated operation | ai-memory backup, separate-volume restore, restart and reread passed | Synthetic wiki page and DB-only pending message; external configuration restored separately. See the full [operation receipt](runtime/observed-20261002.json). |
| Bounded source review | No remaining actionable finding after five targeted regressions and invalid-manifest check, exit 0 | Four implementation/dependency files reviewed. Actual source fallback used because graph metadata was stale. Same-family review does not satisfy blind cross-family convergence. |
| Repository validation | `python3 scripts/validate.py`: passed, exit 0 | Integrity and scope only; no provider or GPU execution. |

The independent review produced repairs for common-retrieval model/budget
equality, immutable original observations during extension, native result
identity, verified corpus snapshots, invalid-input extension eligibility and
the extension manifest's parent linkage. Missing source artifacts or inconsistent
provenance fail closed. Structural validation still cannot certify the honesty
of a producer's runtime assertions.

Initial failures remain evidence: missing implementation, an Inspect/Pydantic
dynamic namespace error, upstream test setup dependencies, restore directory
permissions, absent producer scope, missing archive attempts and publication
redaction checks. Later passing checks do not rewrite those earlier outcomes.

PR #603's initial full CI additionally found the new dependency manifest and
lockfile missing from the OSV inventory. macOS reported 9,443 tests, one failure
and 1,326 skips; Linux reported 9,443 tests, eight failures and 967 skips. The
Linux total includes seven pre-push checks cascading from the same inventory
failure. The repair registers both files and refreshes only the existing
inventory evidence hash/byte count; original CI logs remain retained.

The closed-verdict commit `9ac024a` then exposed one unclassified disposition
string in the new closure record. macOS completed 9,556 tests with one failure
and 1,326 skips; Linux completed 9,556 tests with eight failures and 967 skips,
including seven pre-push cascades. The closure now uses the existing classified
`retain` disposition and a separate `new_acceptance_established: false` flag.
Both repository-classification tests passed after that semantic-preserving
repair. The original full-suite failures remain evidence.

Full command logs and original native identifiers are retained in the private
task directory; public runtime evidence uses stable synthetic labels.

The implementation uses Sol workers and one bounded Sol review; no Astra
escalation was needed. Whole-task model usage, cost and net savings are unknown.
One final read-only consistency audit confirmed that the closed verdict preserves
the evidence limits, distinguishes the separate SDK success from the legacy ACP
gap and queues no runtime experiment. It is not an additional model benchmark.
The [native gate record](runtime/native-gates-20261002.json) retains the remaining
ownership, isolation, model, lifecycle, latency, convergence and canary checks.
