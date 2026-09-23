# Gap evidence wave `gap-wave2-20260923` (agent-lab-17 layers)

This page summarizes [`catalogs/landscape/gap-wave2-20260923--agent-lab-17.json`](../catalogs/landscape/gap-wave2-20260923--agent-lab-17.json). It records the executed checks for the `executable_now` gaps the [crosswalk](gap-crosswalk-92bb279.md) assigned to `agent-lab-17`, keyed to the rows at `92bb279`. Each receipt was reviewed by an Opus evidence reviewer and corrected in one fix round. No verdict changes here.

Rule: status is the best credit over the receipts naming the gap; settles_gap true/partially/false credit settled/advanced/not_settled, but a receipt naming several gaps credits each at most advanced; not_run means no receipt names the gap. No verdict changes here.

## Totals

| Status | Gaps |
| --- | ---: |
| settled | 60 |
| advanced | 94 |
| not_settled | 12 |
| covered_elsewhere | 11 |
| deferred | 12 |
| not_run | 0 |

Receipts: 189; native model calls recorded: 0.

## Per gap

| Layer | Gap | Status | Receipts |
| --- | ---: | --- | --- |
| workers | 0 | deferred | [0-head-to-head-comparison-deferred](../evidence/artifacts/gap-wave2-20260923/foundation__workers/0-head-to-head-comparison-deferred.json) |
| workers | 1 | advanced | [1-wt-model-child-dispatch](../evidence/artifacts/gap-wave2-20260923/foundation__workers/1-wt-model-child-dispatch.json) |
| workers | 2 | deferred | [2-workflow-crash-deferred](../evidence/artifacts/gap-wave2-20260923/foundation__workers/2-workflow-crash-deferred.json) |
| workers | 3 | advanced | [3-child-usage-accounting-advanced](../evidence/artifacts/gap-wave2-20260923/foundation__workers/3-child-usage-accounting-advanced.json) |
| workers | 4 | deferred | [4-restricted-role-recovery-deferred](../evidence/artifacts/gap-wave2-20260923/foundation__workers/4-restricted-role-recovery-deferred.json) |
| workers | 5 | advanced | [5-worktrunk-dirty-sibling-crash-probe](../evidence/artifacts/gap-wave2-20260923/foundation__workers/5-worktrunk-dirty-sibling-crash-probe.json) |
| workers | 6 | deferred | [6-review-workflow-project-settings-deferred](../evidence/artifacts/gap-wave2-20260923/foundation__workers/6-review-workflow-project-settings-deferred.json) |
| workers | 7 | deferred | [7-sealed-oracle-deferred](../evidence/artifacts/gap-wave2-20260923/foundation__workers/7-sealed-oracle-deferred.json) |
| workers | 8 | advanced | [8-beads-kill-restart-integrity](../evidence/artifacts/gap-wave2-20260923/foundation__workers/8-beads-kill-restart-integrity.json) |
| isolation | 0 | advanced | [0-network-fixture-extension](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/0-network-fixture-extension.json) |
| isolation | 1 | settled | [1-filesystem-fixture-versioned](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/1-filesystem-fixture-versioned.json) |
| isolation | 2 | settled | [2-readiness-race-quantified](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/2-readiness-race-quantified.json) |
| isolation | 3 | settled | [3-overlapping-denyread-write-reproduced](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/3-overlapping-denyread-write-reproduced.json) |
| isolation | 4 | advanced | [4-resource-limit-workloads](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/4-resource-limit-workloads.json) |
| isolation | 5 | advanced | [5-worktrunk-0-79-0-cargo-test](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/5-worktrunk-0-79-0-cargo-test.json) |
| isolation | 6 | advanced | [6-worktrunk-lifecycle-rerun-versioned](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/6-worktrunk-lifecycle-rerun-versioned.json) |
| isolation | 7 | settled | [7-worktrunk-dirty-removal-refused](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/7-worktrunk-dirty-removal-refused.json) |
| isolation | 8 | advanced | [8-worktrunk-crash-cleanup-fixture](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/8-worktrunk-crash-cleanup-fixture.json) |
| isolation | 10 | not_settled | [10-podman-boundary-deferred](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/10-podman-boundary-deferred.json) |
| isolation | 12 | advanced | [12-worktrunk-crash-cleanup-fixture-dup](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/12-worktrunk-crash-cleanup-fixture-dup.json) |
| isolation | 13 | advanced | [13-network-and-resource-limits-combined](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/13-network-and-resource-limits-combined.json) |
| isolation | 14 | covered_elsewhere | [14-readiness-race-quantified-dup](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/14-readiness-race-quantified-dup.json) |
| isolation | 15 | advanced | [15-overlapping-denyread-write-reproduced-dup](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/15-overlapping-denyread-write-reproduced-dup.json) |
| isolation | 17 | not_settled | [17-podman-comparison-deferred](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/17-podman-comparison-deferred.json) |
| isolation | 18 | advanced | [18-worktrunk-lifecycle-rerun-versioned-dup](../evidence/artifacts/gap-wave2-20260923/foundation__isolation/18-worktrunk-lifecycle-rerun-versioned-dup.json) |
| code-navigation | 0 | advanced | [0-matched-cross-candidate-benchmark](../evidence/artifacts/gap-wave2-20260923/foundation__code-navigation/0-matched-cross-candidate-benchmark.json) |
| code-navigation | 1 | advanced | [1-symbol-rename-delete-correctness](../evidence/artifacts/gap-wave2-20260923/foundation__code-navigation/1-symbol-rename-delete-correctness.json) |
| document-retrieval | 0 | not_settled | [0-qmd-four-mode-disposable-bench](../evidence/artifacts/gap-wave2-20260923/foundation__document-retrieval/0-qmd-four-mode-disposable-bench.json) |
| document-retrieval | 2 | advanced | [2-qmd-freshness-and-recall](../evidence/artifacts/gap-wave2-20260923/foundation__document-retrieval/2-qmd-freshness-and-recall.json) |
| document-retrieval | 3 | advanced | [3-poppler-difficult-layouts](../evidence/artifacts/gap-wave2-20260923/foundation__document-retrieval/3-poppler-difficult-layouts.json) |
| document-retrieval | 4 | advanced | [4-markitdown-extras-fixtures](../evidence/artifacts/gap-wave2-20260923/foundation__document-retrieval/4-markitdown-extras-fixtures.json) |
| document-retrieval | 5 | advanced | [5-e2e-single-question-pilot](../evidence/artifacts/gap-wave2-20260923/foundation__document-retrieval/5-e2e-single-question-pilot.json) |
| durable-memory | 0 | deferred | [0-no-benchmark-run](../evidence/artifacts/gap-wave2-20260923/foundation__durable-memory/0-no-benchmark-run.json) |
| durable-memory | 1 | not_settled | [1-auto-improve-not-rerun](../evidence/artifacts/gap-wave2-20260923/foundation__durable-memory/1-auto-improve-not-rerun.json) |
| durable-memory | 2 | not_settled | [2-restore-reindex-source-review](../evidence/artifacts/gap-wave2-20260923/foundation__durable-memory/2-restore-reindex-source-review.json) |
| durable-memory | 5 | covered_elsewhere | [5-stale-pin-covered-elsewhere](../evidence/artifacts/gap-wave2-20260923/foundation__durable-memory/5-stale-pin-covered-elsewhere.json) |
| durable-memory | 6 | deferred | [6-token-savings-deferred](../evidence/artifacts/gap-wave2-20260923/foundation__durable-memory/6-token-savings-deferred.json) |
| durable-memory | 8 | not_settled | [8-autonomous-learning-not-rerun](../evidence/artifacts/gap-wave2-20260923/foundation__durable-memory/8-autonomous-learning-not-rerun.json) |
| durable-memory | 9 | deferred | [9-matched-comparison-not-run](../evidence/artifacts/gap-wave2-20260923/foundation__durable-memory/9-matched-comparison-not-run.json) |
| durable-memory | 11 | not_settled | [11-ttl-forget-sweep-live-store-incident](../evidence/artifacts/gap-wave2-20260923/foundation__durable-memory/11-ttl-forget-sweep-live-store-incident.json) |
| durable-memory | 12 | not_settled | [12-live-client-rebind-deferred](../evidence/artifacts/gap-wave2-20260923/foundation__durable-memory/12-live-client-rebind-deferred.json) |
| durable-memory | 13 | covered_elsewhere | [13-stale-pin-covered-elsewhere](../evidence/artifacts/gap-wave2-20260923/foundation__durable-memory/13-stale-pin-covered-elsewhere.json) |
| durable-memory | 14 | advanced | [14-network-bytes-not-measured](../evidence/artifacts/gap-wave2-20260923/foundation__durable-memory/14-network-bytes-not-measured.json) |
| web-research | 0 | advanced | [0-agent-browser-vs-playwright-cli](../evidence/artifacts/gap-wave2-20260923/foundation__web-research/0-agent-browser-vs-playwright-cli.json) |
| web-research | 1 | settled | [1-agent-browser-fixture-version-uname](../evidence/artifacts/gap-wave2-20260923/foundation__web-research/1-agent-browser-fixture-version-uname.json) |
| web-research | 2 | advanced | [2-session-recovery-and-site-compat](../evidence/artifacts/gap-wave2-20260923/foundation__web-research/2-session-recovery-and-site-compat.json) |
| web-research | 3 | deferred | [3-tavily-target-hit-rate](../evidence/artifacts/gap-wave2-20260923/foundation__web-research/3-tavily-target-hit-rate.json) |
| web-research | 4 | deferred | [4-tavily-gold-labelled-benchmark](../evidence/artifacts/gap-wave2-20260923/foundation__web-research/4-tavily-gold-labelled-benchmark.json) |
| web-research | 5 | advanced | [5-openresearch-discovery-and-currency](../evidence/artifacts/gap-wave2-20260923/foundation__web-research/5-openresearch-discovery-and-currency.json) |
| web-research | 6 | advanced | [6-crawl4ai-browseruse-fixture](../evidence/artifacts/gap-wave2-20260923/foundation__web-research/6-crawl4ai-browseruse-fixture.json) |
| token-efficiency | 0 | deferred | [0-native-task-onoff-baseline](../evidence/artifacts/gap-wave2-20260923/foundation__token-efficiency/0-native-task-onoff-baseline.json) |
| token-efficiency | 1 | not_settled | [1-headroom-interception-doctor](../evidence/artifacts/gap-wave2-20260923/foundation__token-efficiency/1-headroom-interception-doctor.json) |
| token-efficiency | 2 | advanced | [2-rtk-lite-preview-rerun](../evidence/artifacts/gap-wave2-20260923/foundation__token-efficiency/2-rtk-lite-preview-rerun.json) |
| token-efficiency | 3 | not_settled | [3-ccusage-attempt-child-coverage](../evidence/artifacts/gap-wave2-20260923/foundation__token-efficiency/3-ccusage-attempt-child-coverage.json) |
| token-efficiency | 4 | not_settled | [4-context-mode-paired-causality](../evidence/artifacts/gap-wave2-20260923/foundation__token-efficiency/4-context-mode-paired-causality.json) |
| token-efficiency | 5 | not_settled | [5-headroom-pin-stale-requalify](../evidence/artifacts/gap-wave2-20260923/foundation__token-efficiency/5-headroom-pin-stale-requalify.json) |
| quality-evaluation | 0 | settled | [0-promptfoo-heldout-30case](../evidence/artifacts/gap-wave2-20260923/foundation__quality-evaluation/0-promptfoo-heldout-30case.json) |
| quality-evaluation | 1 | settled | [1-playwright-upstream-todomvc](../evidence/artifacts/gap-wave2-20260923/foundation__quality-evaluation/1-playwright-upstream-todomvc.json) |
| quality-evaluation | 2 | settled | [2-mutation-catch-three-winners](../evidence/artifacts/gap-wave2-20260923/foundation__quality-evaluation/2-mutation-catch-three-winners.json) |
| quality-evaluation | 3 | settled | [3-shellcheck-difft-content-assert](../evidence/artifacts/gap-wave2-20260923/foundation__quality-evaluation/3-shellcheck-difft-content-assert.json) |
| quality-evaluation | 4 | settled | [4-promptfoo-vs-inspect-ai](../evidence/artifacts/gap-wave2-20260923/foundation__quality-evaluation/4-promptfoo-vs-inspect-ai.json) |
| quality-evaluation | 5 | advanced | [5-typesafe-c4-expansion](../evidence/artifacts/gap-wave2-20260923/foundation__quality-evaluation/5-typesafe-c4-expansion.json) |
| quality-evaluation | 7 | advanced | [7-independent-queries-tokenusage](../evidence/artifacts/gap-wave2-20260923/foundation__quality-evaluation/7-independent-queries-tokenusage.json) |
| quality-evaluation | 9 | advanced | [9-inspect-mlflow-local-vllm](../evidence/artifacts/gap-wave2-20260923/foundation__quality-evaluation/9-inspect-mlflow-local-vllm.json) |
| quality-evaluation | 10 | advanced | [10-typesafe-c4-agreement](../evidence/artifacts/gap-wave2-20260923/foundation__quality-evaluation/10-typesafe-c4-agreement.json) |
| scheduling-supervision | 1 | advanced | [1-provider-cancel-broker-exactly-once](../evidence/artifacts/gap-wave2-20260923/foundation__scheduling-supervision/1-provider-cancel-broker-exactly-once.json) |
| scheduling-supervision | 2 | settled | [2-real-workflow-scheduled-recovered](../evidence/artifacts/gap-wave2-20260923/foundation__scheduling-supervision/2-real-workflow-scheduled-recovered.json) |
| scheduling-supervision | 3 | covered_elsewhere | [3-dagu-2170-requalify](../evidence/artifacts/gap-wave2-20260923/foundation__scheduling-supervision/3-dagu-2170-requalify.json) |
| scheduling-supervision | 4 | advanced | [4-challenger-harness](../evidence/artifacts/gap-wave2-20260923/foundation__scheduling-supervision/4-challenger-harness.json) |
| scheduling-supervision | 6 | advanced | [6-executed-challenger-comparison](../evidence/artifacts/gap-wave2-20260923/foundation__scheduling-supervision/6-executed-challenger-comparison.json) |
| scheduling-supervision | 11 | advanced | [11-reboot-real-workload-plus-upstream-retry](../evidence/artifacts/gap-wave2-20260923/foundation__scheduling-supervision/11-reboot-real-workload-plus-upstream-retry.json) |
| observation-inference | 0 | advanced | [0-privacy-canary-script](../evidence/artifacts/gap-wave2-20260923/foundation__observation-inference/0-privacy-canary-script.json) |
| observation-inference | 1 | settled | [1-usage-reconciliation-script](../evidence/artifacts/gap-wave2-20260923/foundation__observation-inference/1-usage-reconciliation-script.json) |
| observation-inference | 2 | advanced | [2-scheduled-unit-journal-persistence](../evidence/artifacts/gap-wave2-20260923/foundation__observation-inference/2-scheduled-unit-journal-persistence.json) |
| observation-inference | 3 | advanced | [3-task-attribution-isolated](../evidence/artifacts/gap-wave2-20260923/foundation__observation-inference/3-task-attribution-isolated.json) |
| observation-inference | 4 | advanced | [4-sdk-spool-fill-outage-expiry](../evidence/artifacts/gap-wave2-20260923/foundation__observation-inference/4-sdk-spool-fill-outage-expiry.json) |
| observation-inference | 5 | advanced | [5-jaeger-codex-trace-by-id](../evidence/artifacts/gap-wave2-20260923/foundation__observation-inference/5-jaeger-codex-trace-by-id.json) |
| observation-inference | 6 | settled | [6-alertmanager-ntfy-latency](../evidence/artifacts/gap-wave2-20260923/foundation__observation-inference/6-alertmanager-ntfy-latency.json) |
| observation-inference | 8 | advanced | [8-llama-parallel-kill-recovery](../evidence/artifacts/gap-wave2-20260923/foundation__observation-inference/8-llama-parallel-kill-recovery.json) |
| agent-sdks | 0 | advanced | [0-judge-pin-recovery-closure](../evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/0-judge-pin-recovery-closure.json) |
| agent-sdks | 1 | advanced | [1-cancel-usage-vs-native-logs](../evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/1-cancel-usage-vs-native-logs.json) |
| agent-sdks | 2 | settled | [2-worker-isolation](../evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/2-worker-isolation.json) |
| agent-sdks | 3 | settled | [3-persistent-resume-custom-tool](../evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/3-persistent-resume-custom-tool.json) |
| agent-sdks | 4 | settled | [4-c4-three-turns-rerun](../evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/4-c4-three-turns-rerun.json) |
| agent-sdks | 6 | settled | [6-sdk-0155-requalification](../evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/6-sdk-0155-requalification.json) |
| agent-sdks | 8 | settled | [8-langgraph-temporal-openhands](../evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/8-langgraph-temporal-openhands.json) |
| agent-sdks | 9 | settled | [9-matched-sdk-comparison](../evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/9-matched-sdk-comparison.json) |
| agent-sdks | 10 | advanced | [10-codex-custom-tool-event-handling](../evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/10-codex-custom-tool-event-handling.json) |
| agent-sdks | 11 | advanced | [11-cancel-billing-exactly-once](../evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/11-cancel-billing-exactly-once.json) |
| agent-sdks | 12 | settled | [12-file-tool-scope-approval](../evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/12-file-tool-scope-approval.json) |
| agent-sdks | 13 | settled | [13-sdk-resume-new-process](../evidence/artifacts/gap-wave2-20260923/foundation__agent-sdks/13-sdk-resume-new-process.json) |
| mcp-surfaces | 0 | settled | [0-retained-bridge-rerun](../evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/0-retained-bridge-rerun.json) |
| mcp-surfaces | 1 | settled | [1-mcporter-0.14.0-matched](../evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/1-mcporter-0.14.0-matched.json) |
| mcp-surfaces | 2 | settled | [2-owned-daemon-lifecycle-stages](../evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/2-owned-daemon-lifecycle-stages.json) |
| mcp-surfaces | 3 | settled | [3-retained-operation-ids-defined](../evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/3-retained-operation-ids-defined.json) |
| mcp-surfaces | 4 | advanced | [4-inspector-tools-list-local-servers](../evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/4-inspector-tools-list-local-servers.json) |
| mcp-surfaces | 5 | settled | [5-project-config-without-registry](../evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/5-project-config-without-registry.json) |
| mcp-surfaces | 6 | settled | [6-alternative-bridge-comparison](../evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/6-alternative-bridge-comparison.json) |
| mcp-surfaces | 7 | settled | [7-awesome-mcp-servers-recovery-review](../evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/7-awesome-mcp-servers-recovery-review.json) |
| mcp-surfaces | 8 | advanced | [8-inspector-project-file-scope](../evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/8-inspector-project-file-scope.json) |
| mcp-surfaces | 9 | settled | [9-induced-stale-metadata-and-startup-timeout](../evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/9-induced-stale-metadata-and-startup-timeout.json) |
| mcp-surfaces | 10 | settled | [10-disposable-daemon-lifecycle-fixture](../evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/10-disposable-daemon-lifecycle-fixture.json) |
| mcp-surfaces | 12 | settled | [12-matched-set-three-bridges](../evidence/artifacts/gap-wave2-20260923/foundation__mcp-surfaces/12-matched-set-three-bridges.json) |
| market-data-reference | 1 | advanced | [1-ca-currency-field](../evidence/artifacts/gap-wave2-20260923/us-equities__market-data-reference/1-ca-currency-field.json) |
| market-data-reference | 4 | settled | [4-alpaca-py-latest-seams](../evidence/artifacts/gap-wave2-20260923/us-equities__market-data-reference/4-alpaca-py-latest-seams.json) |
| market-data-reference | 5 | advanced | [5-parameterized-comparator](../evidence/artifacts/gap-wave2-20260923/us-equities__market-data-reference/5-parameterized-comparator.json) |
| market-data-reference | 6 | advanced | [6-us-venue-calendars-extended-hours](../evidence/artifacts/gap-wave2-20260923/us-equities__market-data-reference/6-us-venue-calendars-extended-hours.json) |
| market-data-reference | 7 | advanced | [7-data-licensing-clauses](../evidence/artifacts/gap-wave2-20260923/us-equities__market-data-reference/7-data-licensing-clauses.json) |
| market-data-reference | 8 | advanced | [8-feast-pit-join](../evidence/artifacts/gap-wave2-20260923/us-equities__market-data-reference/8-feast-pit-join.json) |
| market-data-reference | 12 | advanced | [12-ca-currency-shared-capture](../evidence/artifacts/gap-wave2-20260923/us-equities__market-data-reference/12-ca-currency-shared-capture.json) |
| market-data-reference | 14 | advanced | [14-adhoc-closures-nyse-corroboration](../evidence/artifacts/gap-wave2-20260923/us-equities__market-data-reference/14-adhoc-closures-nyse-corroboration.json) |
| market-data-reference | 17 | advanced | [17-sec-api-python-disposition](../evidence/artifacts/gap-wave2-20260923/us-equities__market-data-reference/17-sec-api-python-disposition.json) |
| market-data-reference | 18 | advanced | [18-rossod4-quantlab-disposition](../evidence/artifacts/gap-wave2-20260923/us-equities__market-data-reference/18-rossod4-quantlab-disposition.json) |
| identity-provenance | 0 | settled | [0-dvc-repro-restore-contract](../evidence/artifacts/gap-wave2-20260923/us-equities__identity-provenance/0-dvc-repro-restore-contract.json) |
| identity-provenance | 2 | advanced | [2-dvc-executes-selection-quarantine](../evidence/artifacts/gap-wave2-20260923/us-equities__identity-provenance/2-dvc-executes-selection-quarantine.json) |
| identity-provenance | 4 | settled | [4-four-store-comparison](../evidence/artifacts/gap-wave2-20260923/us-equities__identity-provenance/4-four-store-comparison.json) |
| identity-provenance | 5 | settled | [5-openlineage-mlflow-bindings](../evidence/artifacts/gap-wave2-20260923/us-equities__identity-provenance/5-openlineage-mlflow-bindings.json) |
| storage-compute | 0 | advanced | [0-alpaca-snapshot-parquet-duckdb-gate](../evidence/artifacts/gap-wave2-20260923/us-equities__storage-compute/0-alpaca-snapshot-parquet-duckdb-gate.json) |
| storage-compute | 3 | settled | [3-four-store-throughput-concurrency](../evidence/artifacts/gap-wave2-20260923/us-equities__storage-compute/3-four-store-throughput-concurrency.json) |
| storage-compute | 4 | settled | [4-real-snapshot-promotion-gate](../evidence/artifacts/gap-wave2-20260923/us-equities__storage-compute/4-real-snapshot-promotion-gate.json) |
| storage-compute | 6 | covered_elsewhere | [6-paired-astra-claude-covered](../evidence/artifacts/gap-wave2-20260923/us-equities__storage-compute/6-paired-astra-claude-covered.json) |
| storage-compute | 10 | settled | [10-four-store-latency-recovery-footprint](../evidence/artifacts/gap-wave2-20260923/us-equities__storage-compute/10-four-store-latency-recovery-footprint.json) |
| data-quality-orchestration | 1 | covered_elsewhere | [1-paired-model-dag](../evidence/artifacts/gap-wave2-20260923/us-equities__data-quality-orchestration/1-paired-model-dag.json) |
| data-quality-orchestration | 2 | settled | [2-dashboard-auth-mode](../evidence/artifacts/gap-wave2-20260923/us-equities__data-quality-orchestration/2-dashboard-auth-mode.json) |
| data-quality-orchestration | 3 | covered_elsewhere | [3-dagu-2170-hosting-checks](../evidence/artifacts/gap-wave2-20260923/us-equities__data-quality-orchestration/3-dagu-2170-hosting-checks.json) |
| data-quality-orchestration | 5 | settled | [5-duckdb-gate-input](../evidence/artifacts/gap-wave2-20260923/us-equities__data-quality-orchestration/5-duckdb-gate-input.json) |
| data-quality-orchestration | 6 | advanced | [6-temporal-local-execution](../evidence/artifacts/gap-wave2-20260923/us-equities__data-quality-orchestration/6-temporal-local-execution.json) |
| data-quality-orchestration | 7 | settled | [7-dagu-vs-temporal-kill-compare](../evidence/artifacts/gap-wave2-20260923/us-equities__data-quality-orchestration/7-dagu-vs-temporal-kill-compare.json) |
| research-factors-ml | 0 | advanced | [0-nautilus-frozen-selections](../evidence/artifacts/gap-wave2-20260923/us-equities__research-factors-ml/0-nautilus-frozen-selections.json) |
| research-factors-ml | 1 | advanced | [1-purge-embargo-fold-boundary](../evidence/artifacts/gap-wave2-20260923/us-equities__research-factors-ml/1-purge-embargo-fold-boundary.json) |
| research-factors-ml | 5 | advanced | [5-factor-forecast-econometrics-executions](../evidence/artifacts/gap-wave2-20260923/us-equities__research-factors-ml/5-factor-forecast-econometrics-executions.json) |
| research-factors-ml | 6 | advanced | [6-statsforecast-vs-chronos-folds](../evidence/artifacts/gap-wave2-20260923/us-equities__research-factors-ml/6-statsforecast-vs-chronos-folds.json) |
| research-factors-ml | 7 | advanced | [7-kronos-small-vs-naive](../evidence/artifacts/gap-wave2-20260923/us-equities__research-factors-ml/7-kronos-small-vs-naive.json) |
| research-factors-ml | 9 | deferred | [9-alpaca-paper-pipeline](../evidence/artifacts/gap-wave2-20260923/us-equities__research-factors-ml/9-alpaca-paper-pipeline.json) |
| research-factors-ml | 10 | advanced | [10-nautilus-dividend-fee-cash](../evidence/artifacts/gap-wave2-20260923/us-equities__research-factors-ml/10-nautilus-dividend-fee-cash.json) |
| research-factors-ml | 13 | advanced | [13-forecast-econometric-matched-comparison](../evidence/artifacts/gap-wave2-20260923/us-equities__research-factors-ml/13-forecast-econometric-matched-comparison.json) |
| research-factors-ml | 14 | advanced | [14-kronos-and-trading-skills-seeded-defects](../evidence/artifacts/gap-wave2-20260923/us-equities__research-factors-ml/14-kronos-and-trading-skills-seeded-defects.json) |
| backtesting-engine | 0 | covered_elsewhere | [0-spy-lean-parity-peer](../evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/0-spy-lean-parity-peer.json) |
| backtesting-engine | 1 | advanced | [1-nautilus-alpaca-bars-corporate-actions](../evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/1-nautilus-alpaca-bars-corporate-actions.json) |
| backtesting-engine | 2 | settled | [2-nautilus-latest-stable-release](../evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/2-nautilus-latest-stable-release.json) |
| backtesting-engine | 4 | advanced | [4-lean-oracle-alpaca-brokerage-model](../evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/4-lean-oracle-alpaca-brokerage-model.json) |
| backtesting-engine | 6 | settled | [6-comparator-modes-and-review-count](../evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/6-comparator-modes-and-review-count.json) |
| backtesting-engine | 7 | covered_elsewhere | [7-one-zero-distributions-fill-rule-peer](../evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/7-one-zero-distributions-fill-rule-peer.json) |
| backtesting-engine | 8 | advanced | [8-aapl-action-window-replay](../evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/8-aapl-action-window-replay.json) |
| backtesting-engine | 9 | covered_elsewhere | [9-stress-margin-adaptive-parity-peer](../evidence/artifacts/gap-wave2-20260923/us-equities__backtesting-engine/9-stress-margin-adaptive-parity-peer.json) |
| portfolio-risk | 0 | settled | [0-skfolio-cpcv-prior-estimator](../evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/0-skfolio-cpcv-prior-estimator.json) |
| portfolio-risk | 1 | settled | [1-candidate-libs-execution](../evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/1-candidate-libs-execution.json) |
| portfolio-risk | 2 | settled | [2-walkforward-source-hash-match](../evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/2-walkforward-source-hash-match.json) |
| portfolio-risk | 3 | advanced | [3-evaluate-rerun-hash-compare](../evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/3-evaluate-rerun-hash-compare.json) |
| portfolio-risk | 4 | advanced | [4-nautilus-weights-accounting](../evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/4-nautilus-weights-accounting.json) |
| portfolio-risk | 5 | advanced | [5-extended-reserved-significance](../evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/5-extended-reserved-significance.json) |
| portfolio-risk | 6 | advanced | [6-nautilus-riskengine-denial](../evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/6-nautilus-riskengine-denial.json) |
| portfolio-risk | 7 | covered_elsewhere | [7-skfolio-130-upgrade](../evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/7-skfolio-130-upgrade.json) |
| portfolio-risk | 9 | advanced | [9-matched-four-candidate-runner](../evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/9-matched-four-candidate-runner.json) |
| portfolio-risk | 10 | settled | [10-nautilus-optimizer-pnl](../evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/10-nautilus-optimizer-pnl.json) |
| portfolio-risk | 11 | advanced | [11-nautilus-study-episodes-fees](../evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/11-nautilus-study-episodes-fees.json) |
| portfolio-risk | 14 | advanced | [14-parity-and-paper](../evidence/artifacts/gap-wave2-20260923/us-equities__portfolio-risk/14-parity-and-paper.json) |
| evaluation-experiments | 0 | settled | [0-promptfoo-inspect-two-arm](../evidence/artifacts/gap-wave2-20260923/us-equities__evaluation-experiments/0-promptfoo-inspect-two-arm.json) |
| evaluation-experiments | 1 | settled | [1-five-package-installs](../evidence/artifacts/gap-wave2-20260923/us-equities__evaluation-experiments/1-five-package-installs.json) |
| evaluation-experiments | 2 | settled | [2-matched-promptfoo-inspect-comparison](../evidence/artifacts/gap-wave2-20260923/us-equities__evaluation-experiments/2-matched-promptfoo-inspect-comparison.json) |
| evaluation-experiments | 3 | settled | [3-inspect-fixture-authored-frozen](../evidence/artifacts/gap-wave2-20260923/us-equities__evaluation-experiments/3-inspect-fixture-authored-frozen.json) |
| evaluation-experiments | 4 | advanced | [4-arb-trace2code-host-rerun](../evidence/artifacts/gap-wave2-20260923/us-equities__evaluation-experiments/4-arb-trace2code-host-rerun.json) |
| evaluation-experiments | 5 | advanced | [5-fixture-abstention-bootstrap](../evidence/artifacts/gap-wave2-20260923/us-equities__evaluation-experiments/5-fixture-abstention-bootstrap.json) |
| evaluation-experiments | 7 | settled | [7-river-delayed-progressive-validation](../evidence/artifacts/gap-wave2-20260923/us-equities__evaluation-experiments/7-river-delayed-progressive-validation.json) |
| evaluation-experiments | 8 | advanced | [8-research-evaluation-mlflow-binding](../evidence/artifacts/gap-wave2-20260923/us-equities__evaluation-experiments/8-research-evaluation-mlflow-binding.json) |
| agents-models-workers | 0 | advanced | [0-worker-backend-head-to-head](../evidence/artifacts/gap-wave2-20260923/us-equities__agents-models-workers/0-worker-backend-head-to-head.json) |
| agents-models-workers | 2 | advanced | [2-mcp-allowlist-order-block](../evidence/artifacts/gap-wave2-20260923/us-equities__agents-models-workers/2-mcp-allowlist-order-block.json) |
| agents-models-workers | 4 | settled | [4-socraticode-holdout-recall](../evidence/artifacts/gap-wave2-20260923/us-equities__agents-models-workers/4-socraticode-holdout-recall.json) |
| agents-models-workers | 5 | settled | [5-fomc-dated-retrieval](../evidence/artifacts/gap-wave2-20260923/us-equities__agents-models-workers/5-fomc-dated-retrieval.json) |
| agents-models-workers | 6 | advanced | [6-ai-memory-pin-and-features](../evidence/artifacts/gap-wave2-20260923/us-equities__agents-models-workers/6-ai-memory-pin-and-features.json) |
| agents-models-workers | 7 | advanced | [7-winner-readiness-today](../evidence/artifacts/gap-wave2-20260923/us-equities__agents-models-workers/7-winner-readiness-today.json) |
| agents-models-workers | 9 | settled | [9-composed-sdk-worker-restart-handoff](../evidence/artifacts/gap-wave2-20260923/us-equities__agents-models-workers/9-composed-sdk-worker-restart-handoff.json) |
| agents-models-workers | 11 | settled | [11-twelve-query-per-lane](../evidence/artifacts/gap-wave2-20260923/us-equities__agents-models-workers/11-twelve-query-per-lane.json) |
| agents-models-workers | 12 | settled | [12-exhaustive-source-recovery](../evidence/artifacts/gap-wave2-20260923/us-equities__agents-models-workers/12-exhaustive-source-recovery.json) |
| agents-models-workers | 15 | advanced | [15-artifact-reduction-whole-task](../evidence/artifacts/gap-wave2-20260923/us-equities__agents-models-workers/15-artifact-reduction-whole-task.json) |
| agents-models-workers | 16 | advanced | [16-non-adopted-candidate-comparison](../evidence/artifacts/gap-wave2-20260923/us-equities__agents-models-workers/16-non-adopted-candidate-comparison.json) |
| observability-hosting | 0 | advanced | [0-executed-comparison-dagu-arm](../evidence/artifacts/gap-wave2-20260923/us-equities__observability-hosting/0-executed-comparison-dagu-arm.json) |
| security-supply-chain | 0 | settled | [0-grype-sdk-sbom](../evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/0-grype-sdk-sbom.json) |
| security-supply-chain | 2 | advanced | [2-signature-provenance](../evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/2-signature-provenance.json) |
| security-supply-chain | 3 | advanced | [3-syft-binary-os-coverage](../evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/3-syft-binary-os-coverage.json) |
| security-supply-chain | 5 | advanced | [5-gitleaks-current-history](../evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/5-gitleaks-current-history.json) |
| security-supply-chain | 6 | advanced | [6-openbao-secret-lifecycle](../evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/6-openbao-secret-lifecycle.json) |
| security-supply-chain | 7 | settled | [7-scanner-comparison](../evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/7-scanner-comparison.json) |
| security-supply-chain | 8 | advanced | [8-research-worker-broker-authority](../evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/8-research-worker-broker-authority.json) |
| security-supply-chain | 9 | advanced | [9-syft-root-binary-coverage](../evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/9-syft-root-binary-coverage.json) |
| security-supply-chain | 10 | settled | [10-grype-sdk-readme-correction](../evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/10-grype-sdk-readme-correction.json) |
| security-supply-chain | 12 | advanced | [12-gitleaks-full-history-types](../evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/12-gitleaks-full-history-types.json) |
| security-supply-chain | 13 | advanced | [13-cosign-verify-blob](../evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/13-cosign-verify-blob.json) |
| security-supply-chain | 14 | advanced | [14-openbao-and-worker-denial](../evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/14-openbao-and-worker-denial.json) |

## Receipts that refute the incumbent

None.

## Limits

- A status records what a receipt shows about the gap text at the source revision; a later re-record needs a new crosswalk.
- `not_run` gaps stayed open for the reasons recorded in the units' results (budget, shared-account window, or a check that needs the user).
