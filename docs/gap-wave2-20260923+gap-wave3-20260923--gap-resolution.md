# Gap evidence, combined waves `gap-wave2-20260923` + `gap-wave3-20260923` (gap-resolution layers)

This page summarizes [`catalogs/landscape/gap-wave2-20260923+gap-wave3-20260923--gap-resolution.json`](../catalogs/landscape/gap-wave2-20260923+gap-wave3-20260923--gap-resolution.json). It records the executed checks for the `executable_now` gaps the [crosswalk](gap-crosswalk-92bb279.md) assigned to `gap-resolution`, keyed to the rows at `92bb279`. Each receipt was reviewed by an Opus evidence reviewer and corrected in one fix round. No verdict changes here.

Rule: status is the best credit over the receipts naming the gap; settles_gap true/partially/false credit settled/advanced/not_settled, but a receipt naming several gaps credits each at most advanced; not_run means no receipt names the gap. No verdict changes here.

## Totals

| Status | Gaps |
| --- | ---: |
| settled | 10 |
| advanced | 59 |
| not_settled | 0 |
| not_run | 0 |

Receipts: 60; native model calls recorded: 101.

## Per gap

| Layer | Gap | Status | Receipts |
| --- | ---: | --- | --- |
| native-clients | 0 | advanced | [codex-resume-pinned-build](../evidence/artifacts/gap-wave2-20260923/native-clients/codex-resume-pinned-build.json) |
| native-clients | 1 | advanced | [claude-resume-mcp-toolset](../evidence/artifacts/gap-wave2-20260923/native-clients/claude-resume-mcp-toolset.json) |
| native-clients | 2 | advanced | [arm-comparison-research-task](../evidence/artifacts/gap-wave3-20260923/native-clients/arm-comparison-research-task.json) |
| native-clients | 5 | advanced | [claude-resume-mcp-toolset](../evidence/artifacts/gap-wave2-20260923/native-clients/claude-resume-mcp-toolset.json), [codex-resume-pinned-build](../evidence/artifacts/gap-wave2-20260923/native-clients/codex-resume-pinned-build.json) |
| native-clients | 7 | advanced | [agent-sdk-install-and-tool-use](../evidence/artifacts/gap-wave2-20260923/native-clients/agent-sdk-install-and-tool-use.json) |
| native-clients | 8 | advanced | [arm-comparison-research-task](../evidence/artifacts/gap-wave3-20260923/native-clients/arm-comparison-research-task.json) |
| native-clients | 10 | advanced | [codex-resume-pinned-build](../evidence/artifacts/gap-wave2-20260923/native-clients/codex-resume-pinned-build.json) |
| native-clients | 12 | advanced | [sdk-vs-cli-resume-comparison](../evidence/artifacts/gap-wave3-20260923/native-clients/sdk-vs-cli-resume-comparison.json) |
| native-clients | 13 | settled | [mcporter-context-mode-bridge-recovery](../evidence/artifacts/gap-wave2-20260923/native-clients/mcporter-context-mode-bridge-recovery.json) |
| instructions-skills | 0 | advanced | [frozen-skill-arm-ab](../evidence/artifacts/gap-wave2-20260923/instructions-skills/frozen-skill-arm-ab.json) |
| instructions-skills | 1 | advanced | [frozen-skill-arm-ab](../evidence/artifacts/gap-wave2-20260923/instructions-skills/frozen-skill-arm-ab.json), [forced-skill-arm-ab](../evidence/artifacts/gap-wave3-20260923/instructions-skills/forced-skill-arm-ab.json) |
| instructions-skills | 2 | advanced | [skill-sync-and-closure-reconciliation](../evidence/artifacts/gap-wave2-20260923/instructions-skills/skill-sync-and-closure-reconciliation.json) |
| instructions-skills | 3 | advanced | [ecc-trigger-activation-test](../evidence/artifacts/gap-wave2-20260923/instructions-skills/ecc-trigger-activation-test.json) |
| instructions-skills | 4 | settled | [worker-skill-declaration-documented-behavior](../evidence/artifacts/gap-wave2-20260923/instructions-skills/worker-skill-declaration-documented-behavior.json), [worker-skill-preload-probe](../evidence/artifacts/gap-wave3-20260923/instructions-skills/worker-skill-preload-probe.json) |
| instructions-skills | 5 | advanced | [gh-fix-ci-failing-path-trial](../evidence/artifacts/gap-wave2-20260923/instructions-skills/gh-fix-ci-failing-path-trial.json) |
| instructions-skills | 6 | advanced | [security-best-practices-reference-drift](../evidence/artifacts/gap-wave2-20260923/instructions-skills/security-best-practices-reference-drift.json) |
| instructions-skills | 7 | advanced | [frozen-skill-arm-ab](../evidence/artifacts/gap-wave2-20260923/instructions-skills/frozen-skill-arm-ab.json), [typesafe-extended-label-set](../evidence/artifacts/gap-wave3-20260923/instructions-skills/typesafe-extended-label-set.json) |
| instructions-skills | 8 | settled | [ecc-shan-pin-diff](../evidence/artifacts/gap-wave2-20260923/instructions-skills/ecc-shan-pin-diff.json) |
| instructions-skills | 9 | settled | [claude-code-templates-source-review](../evidence/artifacts/gap-wave2-20260923/instructions-skills/claude-code-templates-source-review.json) |
| semantic-rag | 0 | advanced | [held-out-recall-benchmark](../evidence/artifacts/gap-wave2-20260923/semantic-rag/held-out-recall-benchmark.json) |
| semantic-rag | 1 | advanced | [watcher-kill-restart-recovery](../evidence/artifacts/gap-wave2-20260923/semantic-rag/watcher-kill-restart-recovery.json) |
| semantic-rag | 5 | advanced | [held-out-recall-benchmark](../evidence/artifacts/gap-wave2-20260923/semantic-rag/held-out-recall-benchmark.json) |
| semantic-rag | 6 | advanced | [socraticode-token-comparison](../evidence/artifacts/gap-wave2-20260923/semantic-rag/socraticode-token-comparison.json) |
| semantic-rag | 7 | advanced | [socraticode-vs-baselines](../evidence/artifacts/gap-wave2-20260923/semantic-rag/socraticode-vs-baselines.json) |
| semantic-rag | 8 | advanced | [held-out-recall-benchmark](../evidence/artifacts/gap-wave2-20260923/semantic-rag/held-out-recall-benchmark.json) |
| semantic-rag | 9 | advanced | [qdrant-restart-reconnect](../evidence/artifacts/gap-wave2-20260923/semantic-rag/qdrant-restart-reconnect.json) |
| semantic-rag | 10 | advanced | [coordinated-snapshot-restore](../evidence/artifacts/gap-wave2-20260923/semantic-rag/coordinated-snapshot-restore.json) |
| semantic-rag | 11 | advanced | [vllm-0.30.0-acceptance-batch](../evidence/artifacts/gap-wave2-20260923/semantic-rag/vllm-0.30.0-acceptance-batch.json) |
| semantic-rag | 12 | advanced | [code-memory-comparison](../evidence/artifacts/gap-wave2-20260923/semantic-rag/code-memory-comparison.json) |
| semantic-rag | 13 | advanced | [held-out-recall-benchmark](../evidence/artifacts/gap-wave2-20260923/semantic-rag/held-out-recall-benchmark.json) |
| ci-supply-chain | 0 | settled | [zizmor-negative-control](../evidence/artifacts/gap-wave2-20260923/ci-supply-chain/zizmor-negative-control.json) |
| ci-supply-chain | 1 | settled | [publish-catalog-dispatch-attestation](../evidence/artifacts/gap-wave2-20260923/ci-supply-chain/publish-catalog-dispatch-attestation.json) |
| ci-supply-chain | 2 | advanced | [supply-chain-hosted-run-and-wider-syft](../evidence/artifacts/gap-wave2-20260923/ci-supply-chain/supply-chain-hosted-run-and-wider-syft.json) |
| ci-supply-chain | 3 | advanced | [syft-signature-verification-and-wider-scan](../evidence/artifacts/gap-wave2-20260923/ci-supply-chain/syft-signature-verification-and-wider-scan.json) |
| ci-supply-chain | 5 | advanced | [zizmor-online-audit](../evidence/artifacts/gap-wave2-20260923/ci-supply-chain/zizmor-online-audit.json) |
| ci-supply-chain | 7 | advanced | [archive-reproducibility](../evidence/artifacts/gap-wave2-20260923/ci-supply-chain/archive-reproducibility.json) |
| ci-supply-chain | 9 | advanced | [syft-signature-verification-and-wider-scan](../evidence/artifacts/gap-wave2-20260923/ci-supply-chain/syft-signature-verification-and-wider-scan.json) |
| ci-supply-chain | 12 | advanced | [lockfile-audit](../evidence/artifacts/gap-wave2-20260923/ci-supply-chain/lockfile-audit.json) |
| ci-supply-chain | 13 | settled | [grype-known-cve-fixture](../evidence/artifacts/gap-wave2-20260923/ci-supply-chain/grype-known-cve-fixture.json) |
| hosting-services | 0 | advanced | [backup-restore-app-rebuild](../evidence/artifacts/gap-wave2-20260923/hosting-services/backup-restore-app-rebuild.json) |
| hosting-services | 2 | advanced | [migration-up-down-up-data-survival](../evidence/artifacts/gap-wave2-20260923/hosting-services/migration-up-down-up-data-survival.json) |
| hosting-services | 3 | advanced | [podman-rootless-feasibility-and-native-comparison](../evidence/artifacts/gap-wave2-20260923/hosting-services/podman-rootless-feasibility-and-native-comparison.json), [container-build-start-resource-vs-native](../evidence/artifacts/gap-wave3-20260923/hosting-services/container-build-start-resource-vs-native.json), [container-recovery-isolation-cpu-mem-vs-native](../evidence/artifacts/gap-wave3-20260923/hosting-services/container-recovery-isolation-cpu-mem-vs-native.json) |
| hosting-services | 4 | settled | [systemd-run-supervision-kill-restart](../evidence/artifacts/gap-wave2-20260923/hosting-services/systemd-run-supervision-kill-restart.json) |
| hosting-services | 9 | advanced | [hardened-postgres-tls-scram](../evidence/artifacts/gap-wave2-20260923/hosting-services/hardened-postgres-tls-scram.json) |
| hosting-services | 10 | advanced | [podman-rootless-feasibility-and-native-comparison](../evidence/artifacts/gap-wave2-20260923/hosting-services/podman-rootless-feasibility-and-native-comparison.json), [container-build-start-resource-vs-native](../evidence/artifacts/gap-wave3-20260923/hosting-services/container-build-start-resource-vs-native.json), [container-recovery-isolation-cpu-mem-vs-native](../evidence/artifacts/gap-wave3-20260923/hosting-services/container-recovery-isolation-cpu-mem-vs-native.json) |
| recovery-portability | 1 | advanced | [clean-prefix-context-mode-ai-memory-mcporter](../evidence/artifacts/gap-wave2-20260923/recovery-portability/clean-prefix-context-mode-ai-memory-mcporter.json) |
| recovery-portability | 6 | advanced | [restic-mtime-sparse-uid-extension](../evidence/artifacts/gap-wave2-20260923/recovery-portability/restic-mtime-sparse-uid-extension.json) |
| recovery-portability | 8 | advanced | [restic-vs-litestream-uv-vs-mise](../evidence/artifacts/gap-wave2-20260923/recovery-portability/restic-vs-litestream-uv-vs-mise.json) |
| recovery-portability | 10 | advanced | [uv-fresh-cache-sdk-graph-sync](../evidence/artifacts/gap-wave2-20260923/recovery-portability/uv-fresh-cache-sdk-graph-sync.json) |
| recovery-portability | 14 | advanced | [restic-vs-litestream-uv-vs-mise](../evidence/artifacts/gap-wave2-20260923/recovery-portability/restic-vs-litestream-uv-vs-mise.json) |
| secrets-credentials | 0 | advanced | [credential-path-containment](../evidence/artifacts/gap-wave2-20260923/secrets-credentials/credential-path-containment.json) |
| secrets-credentials | 2 | advanced | [gitleaks-headancestry-and-ci-pipeline](../evidence/artifacts/gap-wave2-20260923/secrets-credentials/gitleaks-headancestry-and-ci-pipeline.json) |
| secrets-credentials | 5 | advanced | [openbao-lifecycle-comparison](../evidence/artifacts/gap-wave2-20260923/secrets-credentials/openbao-lifecycle-comparison.json) |
| secrets-credentials | 6 | advanced | [gitleaks-precommit-enforcement](../evidence/artifacts/gap-wave2-20260923/secrets-credentials/gitleaks-precommit-enforcement.json) |
| secrets-credentials | 8 | settled | [gitleaksignore-allrefs-clean](../evidence/artifacts/gap-wave2-20260923/secrets-credentials/gitleaksignore-allrefs-clean.json) |
| secrets-credentials | 9 | advanced | [gitleaks-html-chunk-coverage](../evidence/artifacts/gap-wave2-20260923/secrets-credentials/gitleaks-html-chunk-coverage.json) |
| secrets-credentials | 10 | advanced | [openbao-lifecycle-comparison](../evidence/artifacts/gap-wave2-20260923/secrets-credentials/openbao-lifecycle-comparison.json) |
| git-github-automation | 0 | advanced | [gh-inventory-baseline](../evidence/artifacts/gap-wave2-20260923/git-github-automation/gh-inventory-baseline.json) |
| git-github-automation | 1 | advanced | [gh-pr-flow](../evidence/artifacts/gap-wave2-20260923/git-github-automation/gh-pr-flow.json) |
| git-github-automation | 3 | advanced | [codex-review-lane](../evidence/artifacts/gap-wave2-20260923/git-github-automation/codex-review-lane.json) |
| git-github-automation | 4 | advanced | [difftastic-fixture-rerun-4](../evidence/artifacts/gap-wave2-20260923/git-github-automation/difftastic-fixture-rerun-4.json) |
| git-github-automation | 5 | advanced | [worktrunk-crash-cleanup-probe-5](../evidence/artifacts/gap-wave2-20260923/git-github-automation/worktrunk-crash-cleanup-probe-5.json) |
| git-github-automation | 6 | advanced | [worktree-and-diff-challenger-6](../evidence/artifacts/gap-wave2-20260923/git-github-automation/worktree-and-diff-challenger-6.json) |
| git-github-automation | 7 | advanced | [gh-inventory-baseline](../evidence/artifacts/gap-wave2-20260923/git-github-automation/gh-inventory-baseline.json) |
| git-github-automation | 8 | advanced | [worktree-e2e-comparison-8](../evidence/artifacts/gap-wave2-20260923/git-github-automation/worktree-e2e-comparison-8.json) |
| git-github-automation | 9 | advanced | [worktrunk-hooks-umask-crash-9](../evidence/artifacts/gap-wave2-20260923/git-github-automation/worktrunk-hooks-umask-crash-9.json) |
| git-github-automation | 10 | advanced | [difftastic-multilang-scoring-10](../evidence/artifacts/gap-wave2-20260923/git-github-automation/difftastic-multilang-scoring-10.json) |
| git-github-automation | 11 | settled | [ruleset-doc-correction](../evidence/artifacts/gap-wave2-20260923/git-github-automation/ruleset-doc-correction.json) |
| git-github-automation | 12 | advanced | [codex-review-lane](../evidence/artifacts/gap-wave2-20260923/git-github-automation/codex-review-lane.json) |

## Receipts that refute the incumbent

- [lockfile-audit](../evidence/artifacts/gap-wave2-20260923/ci-supply-chain/lockfile-audit.json) (partially)

## Limits

- A status records what a receipt shows about the gap text at the source revision; a later re-record needs a new crosswalk.
- `not_run` gaps stayed open for the reasons recorded in the units' results (budget, shared-account window, or a check that needs the user).
