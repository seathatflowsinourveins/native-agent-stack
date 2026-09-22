# Gap resolution, 2026-09-22

This page summarizes the machine-readable ledger [`catalogs/landscape/gap-resolution-20260922.json`](../catalogs/landscape/gap-resolution-20260922.json). It records a disposition for every `open_gaps` entry of the 32 landscape rows and the receipts of the checks run on 2026-09-22 under [`evidence/artifacts/gap-resolution-20260922/`](../evidence/artifacts/gap-resolution-20260922/). The ledger changes no verdict. A verdict changes only through a lane run recorded by `tools/sota-convergence/record_verdicts.py`.

## How the gaps were handled

1. **Triage.** One read-only reader per layer classified each gap by what blocks it and proposed runnable checks. An Opus critic rejected or corrected 31 of the proposed checks for invented flags, reruns that could not settle a comparison, or unauthorized installs. A second pass covered the 12 layers the first pass skipped.
2. **Execution.** Eleven units ran the vetted checks, each in its own worktree. Each unit had one Opus evidence review and one fix round. Reviewers downgraded several overclaims, for example a smoke test labelled as settling a comparison gap, or a post-hoc expectation labelled as preregistered. Those corrections are recorded inside each receipt.
3. **Limits of authority.** No paid data, LLM API key, order, credential or second machine was used. SEC EDGAR was not queried because it requires a contact email the user has not approved. Codex was usage-limited during the run, so its gaps stayed open; the limit has since lifted.

## Totals

| Status | Gaps |
| --- | ---: |
| settled | 7 |
| advanced | 33 |
| not_settled | 5 |
| open | 270 |

| Category (why a gap is open or what it needs) | Gaps |
| --- | ---: |
| executable_now | 80 |
| not_actionable | 53 |
| codex_limited | 43 |
| documentation_fix | 34 |
| manifest_gap | 33 |
| needs_paid_entitlement | 21 |
| needs_hardware | 20 |
| peer_owned | 16 |
| needs_user_input | 10 |
| needs_user_login | 3 |
| time_gated | 2 |

## Per layer

| Catalog | Layer | Gaps | Settled | Advanced | Not settled | Open |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| foundation | agent-sdks | 11 | 0 | 0 | 0 | 11 |
| foundation | ci-supply-chain | 11 | 0 | 0 | 0 | 11 |
| foundation | code-navigation | 11 | 0 | 0 | 0 | 11 |
| foundation | document-retrieval | 7 | 0 | 2 | 0 | 5 |
| foundation | durable-memory | 10 | 0 | 1 | 0 | 9 |
| foundation | git-github-automation | 11 | 1 | 0 | 2 | 8 |
| foundation | hosting-services | 9 | 0 | 0 | 0 | 9 |
| foundation | instructions-skills | 11 | 0 | 0 | 0 | 11 |
| foundation | isolation | 12 | 0 | 0 | 0 | 12 |
| foundation | mcp-surfaces | 9 | 0 | 0 | 0 | 9 |
| foundation | native-clients | 8 | 0 | 0 | 0 | 8 |
| foundation | observation-inference | 8 | 0 | 2 | 0 | 6 |
| foundation | quality-evaluation | 12 | 0 | 0 | 0 | 12 |
| foundation | recovery-portability | 8 | 0 | 3 | 0 | 5 |
| foundation | scheduling-supervision | 8 | 1 | 0 | 0 | 7 |
| foundation | secrets-credentials | 8 | 1 | 2 | 0 | 5 |
| foundation | semantic-rag | 11 | 0 | 1 | 0 | 10 |
| foundation | token-efficiency | 10 | 0 | 3 | 0 | 7 |
| foundation | web-research | 10 | 0 | 0 | 0 | 10 |
| foundation | workers | 11 | 0 | 2 | 1 | 8 |
| us-equities | agents-models-workers | 12 | 0 | 3 | 0 | 9 |
| us-equities | backtesting-engine | 12 | 0 | 0 | 0 | 12 |
| us-equities | data-quality-orchestration | 9 | 2 | 1 | 0 | 6 |
| us-equities | evaluation-experiments | 9 | 0 | 2 | 0 | 7 |
| us-equities | execution-broker | 9 | 1 | 2 | 0 | 6 |
| us-equities | identity-provenance | 8 | 0 | 3 | 0 | 5 |
| us-equities | market-data-reference | 12 | 0 | 1 | 1 | 10 |
| us-equities | observability-hosting | 12 | 0 | 0 | 0 | 12 |
| us-equities | portfolio-risk | 9 | 1 | 0 | 0 | 8 |
| us-equities | research-factors-ml | 11 | 0 | 3 | 0 | 8 |
| us-equities | security-supply-chain | 8 | 0 | 0 | 0 | 8 |
| us-equities | storage-compute | 8 | 0 | 2 | 1 | 5 |

## Receipts

| Receipt | Settles | Direction | Evidence class |
| --- | --- | --- | --- |
| [ai-memory-local-scope-reread](../evidence/artifacts/gap-resolution-20260922/agents-models-workers/ai-memory-local-scope-reread.json) | partially | inconclusive | native_proven |
| [dagu-inflight-resume-after-kill](../evidence/artifacts/gap-resolution-20260922/data-quality-orchestration/dagu-inflight-resume-after-kill.json) | partially | refutes_incumbent | native_proven |
| [promotion-gate-fixture-suite](../evidence/artifacts/gap-resolution-20260922/data-quality-orchestration/promotion-gate-fixture-suite.json) | True | supports_incumbent | synthetic |
| [cite-executed-retrieval](../evidence/artifacts/gap-resolution-20260922/document-retrieval/cite-executed-retrieval.json) | partially | refutes_incumbent | source_review |
| [qmd-repeated-bench-isolated](../evidence/artifacts/gap-resolution-20260922/document-retrieval/qmd-repeated-bench-isolated.json) | no | inconclusive | native_proven |
| [upstream-currency-sweep-20260922--document-retrieval](../evidence/artifacts/gap-resolution-20260922/document-retrieval/upstream-currency-sweep.json) | partially | inconclusive | source_review |
| [deletion-erasure-probe](../evidence/artifacts/gap-resolution-20260922/durable-memory/deletion-erasure-probe.json) | partially | supports_incumbent | native_proven |
| [upstream-currency-sweep-20260922--evaluation-experiments](../evidence/artifacts/gap-resolution-20260922/evaluation-experiments/upstream-currency-sweep.json) | partially | inconclusive | source_review |
| [capture-alpaca-wire-serialization](../evidence/artifacts/gap-resolution-20260922/execution-broker/capture-alpaca-wire-serialization.json) | True | supports_incumbent | synthetic |
| [rerun-frozen-fixture-suite](../evidence/artifacts/gap-resolution-20260922/execution-broker/rerun-frozen-fixture-suite.json) | partially | inconclusive | synthetic |
| [difftastic-larger-fixture](../evidence/artifacts/gap-resolution-20260922/git-github-automation/difftastic-larger-fixture.json) | False | inconclusive | native_proven |
| [upstream-currency-sweep-20260922--git-github-automation](../evidence/artifacts/gap-resolution-20260922/git-github-automation/upstream-currency-sweep.json) | partially | inconclusive | source_review |
| [worktrunk-0-79-0-requalify](../evidence/artifacts/gap-resolution-20260922/git-github-automation/worktrunk-0-79-0-requalify.json) | True | supports_incumbent | native_proven |
| [delta-rs-header-run](../evidence/artifacts/gap-resolution-20260922/identity-provenance/delta-rs-header-run.json) | partially | not_applicable | native_proven |
| [dvc-arm-restore-compare](../evidence/artifacts/gap-resolution-20260922/identity-provenance/dvc-arm-restore-compare.json) | partially | supports_incumbent | native_proven |
| [sdk-env-baseline](../evidence/artifacts/gap-resolution-20260922/identity-provenance/sdk-env-baseline.json) | partially | supports_incumbent | native_proven |
| [xnys-multiyear-holiday-check](../evidence/artifacts/gap-resolution-20260922/market-data-reference/xnys-multiyear-holiday-check.json) | partially | supports_incumbent | native_proven |
| [observability-offline-regression](../evidence/artifacts/gap-resolution-20260922/observation-inference/observability-offline-regression.json) | partially | inconclusive | native_proven |
| [vllm-0.30.0-uva-smoke](../evidence/artifacts/gap-resolution-20260922/observation-inference/vllm-0.30.0-uva-smoke.json) | partially | not_applicable | native_proven |
| [skf_walkforward_optimizer](../evidence/artifacts/gap-resolution-20260922/portfolio-risk/skf_walkforward_optimizer.json) | True | supports_incumbent | native_proven |
| [local-ai-memory-qdrant-rebind](../evidence/artifacts/gap-resolution-20260922/recovery-portability/local-ai-memory-qdrant-rebind.json) | partially | supports_incumbent | native_proven |
| [restic-filesystem-semantics](../evidence/artifacts/gap-resolution-20260922/recovery-portability/restic-filesystem-semantics.json) | partially | supports_incumbent | native_proven |
| [repo-local-full-test-rerun](../evidence/artifacts/gap-resolution-20260922/research-factors-ml/repo-local-full-test-rerun.json) | partially | inconclusive | local_integration |
| [sklearn-timeseriessplit-matched-arm](../evidence/artifacts/gap-resolution-20260922/research-factors-ml/sklearn-timeseriessplit-matched-arm.json) | partially | inconclusive | native_proven |
| [dagu-2170-checkpoint-parity](../evidence/artifacts/gap-resolution-20260922/scheduling-supervision/dagu-2170-checkpoint-parity.json) | True | supports_incumbent | native_proven |
| [upstream-currency-sweep-20260922--scheduling-supervision](../evidence/artifacts/gap-resolution-20260922/scheduling-supervision/upstream-currency-sweep.json) | partially | inconclusive | source_review |
| [attestation-endpoint-recheck-20260922](../evidence/artifacts/gap-resolution-20260922/secrets-credentials/attestation-endpoint-recheck.json) | True | supports_incumbent | source_review |
| [gitleaks-repo-history-scan-20260922](../evidence/artifacts/gap-resolution-20260922/secrets-credentials/gitleaks-repo-history-scan.json) | partially | supports_incumbent | native_proven |
| [vllm-0.30.0-uva-smoke](../evidence/artifacts/gap-resolution-20260922/semantic-rag/vllm-0.30.0-uva-smoke.json) | partially | not_applicable | native_proven |
| [duckdb-regression](../evidence/artifacts/gap-resolution-20260922/storage-compute/duckdb-regression.json) | partially | supports_incumbent | native_proven |
| [financial-data-offline-regression](../evidence/artifacts/gap-resolution-20260922/storage-compute/financial-data-offline-regression.json) | partially | supports_incumbent | native_proven |
| [sec-edgar-acquisition-deferred](../evidence/artifacts/gap-resolution-20260922/storage-compute/sec-edgar-acquisition-deferred.json) | False | not_applicable | source_review |
| [ccusage-real-log-coverage](../evidence/artifacts/gap-resolution-20260922/token-efficiency/ccusage-real-log-coverage.json) | partially | supports_incumbent | native_proven |
| [headroom-0.38.0-upgrade-recovery](../evidence/artifacts/gap-resolution-20260922/token-efficiency/headroom-0.38.0-upgrade-recovery.json) | partially | supports_incumbent | native_proven |
| [rtk-second-artifact-pair](../evidence/artifacts/gap-resolution-20260922/token-efficiency/rtk-second-artifact-pair.json) | partially | supports_incumbent | native_proven |
| [upstream-currency-sweep-20260922--token-efficiency](../evidence/artifacts/gap-resolution-20260922/token-efficiency/upstream-currency-sweep.json) | partially | inconclusive | source_review |
| [beads-lease-recovery-probe](../evidence/artifacts/gap-resolution-20260922/workers/beads-lease-recovery-probe.json) | partially | supports_incumbent | native_proven |
| [upstream-currency-sweep-20260922--workers](../evidence/artifacts/gap-resolution-20260922/workers/upstream-currency-sweep.json) | partially | inconclusive | source_review |
| [worktrunk-crash-cleanup-probe](../evidence/artifacts/gap-resolution-20260922/workers/worktrunk-crash-cleanup-probe.json) | False | inconclusive | native_proven |

## Findings that matter for the catalog

- **vLLM 0.30.0 starts on this WSL GPU host.** The 0.29.0 "UVA is not available" crash does not reproduce, because upstream added a device-memory fallback. The 0.25.0 pin stays in place until a throughput and quality comparison against 0.30.0 is recorded. The blocker text "needs new hardware" was wrong: only an install into a new prefix was needed.
- **Dagu 2.16.6 does not resume an in-flight step immediately after the run process is killed.** Recovery beyond the 30 s lock and 90 s heartbeat thresholds is untested.
- **Beads 1.3.0 has a permanent crash-recovery hole.** Its lease recovery works for a bare `--claim`, but `--claim --assignee` leaves an in-progress issue with no lease row, which `bd reclaim` can never select.
- **ai-memory deletion is not byte-level erasure.** Deleted text persists in the SQLite write-ahead log, the git-versioned wiki history and captured observation rows.
- **Restic 0.19.1 round trips preserve all tested metadata locally.** Mode, ACLs, xattrs, symlinks, hardlinks and content hashes survived. The drvfs (`/mnt/c`) target preserves content, symlinks and hardlinks but not all metadata; details are in the receipt.
- **Headroom 0.38.0** compresses and recovers byte-exactly in an isolated store. The unit's invalid first run had written to the live `~/.headroom` store; the coordinator removed exactly those writes after a backup ([cleanup record](../evidence/artifacts/gap-resolution-20260922/token-efficiency/headroom-live-store-cleanup.json)).
- **The gitleaks full-history scan** with the reviewed config and the 2 MB size skip reports one finding. That finding sits on another session's unmerged branch fixture, outside main's ancestry.

## What stays open and who can close it

- **codex_limited:** now runnable, since the Codex limit lifted. The layer-verdict Codex lane (agent-lab-17) covers the per-row "Codex lane absent" gaps; the remaining ones need a Codex arm in their comparison.
- **documentation_fix and manifest_gap:** fixable by editing text or data. Changes to ledger rows wait for the layer-verdict rerun, which can renumber `open_gaps`.
- **needs_paid_entitlement, needs_user_input, needs_user_login:** need a user decision.
- **needs_hardware:** needs a second machine or a Mac.
- **time_gated:** needs market hours.
- **peer_owned:** stays with the named session.
