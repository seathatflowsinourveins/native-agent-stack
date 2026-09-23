# Component evidence matrix

Generated 2026-09-22 by `python3 scripts/component_matrix.py --write` from `catalogs/landscape/component-evidence-matrix.json`. Per-component independent-review status and per-platform E2E state, joined from catalogs/landscape/{foundation,us-equities}.json winners/alternatives, catalogs/foundation/decisions.json lifecycle stage_refs, scripts/host_receipts.py receipts and the gap crosswalk (open executable_now gaps per layer, when present). It never selects a winner or records a receipt; it is a read-only join of evidence recorded elsewhere.

## Totals

| Metric | Count |
| --- | --- |
| layers | 32 |
| winners | 66 |
| alternatives | 183 |
| dual_lane_same_winner | 20 |
| dual_lane_adjudicated | 10 |
| pending_lanes | 2 |
| single_lane | 0 |

## Per-layer

| Layer | Independent review | Winners: e2e_state (linux-wsl2-x86_64 / macos-arm64) |
| --- | --- | --- |
| `foundation/agent-sdks` | dual_lane_same_winner | codex (accepted / untested) |
| `foundation/ci-supply-chain` | dual_lane_same_winner | zizmor (accepted / untested); syft (accepted / untested); candidate:actions-attest (accepted / untested) |
| `foundation/code-navigation` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-code-navigation-20260922.json`) | serena (accepted / untested) |
| `foundation/document-retrieval` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-document-retrieval-20260922.json`) | qmd (conditional / untested); markitdown (conditional / untested); poppler (conditional / untested) |
| `foundation/durable-memory` | dual_lane_same_winner | ai-memory (accepted / untested) |
| `foundation/git-github-automation` | dual_lane_same_winner | worktrunk (not_established / untested); candidate:cli-cli (not_established / untested); difftastic (not_established / untested) |
| `foundation/hosting-services` | dual_lane_same_winner | fastapi (accepted / untested); nextjs (accepted / untested); postgresql (accepted / untested) |
| `foundation/instructions-skills` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-instructions-skills-20260922.json`) | affaan-m/ECC (conditional / untested); candidate:typesafe-ai-skills (conditional / untested); candidate:openai-skills (conditional / untested) |
| `foundation/isolation` | dual_lane_same_winner | worktrunk (accepted / untested); sandbox-runtime (accepted / untested) |
| `foundation/mcp-surfaces` | dual_lane_same_winner | mcporter (accepted / untested); mcp-inspector (accepted / untested) |
| `foundation/native-clients` | dual_lane_same_winner | claude-code (accepted / untested); codex (accepted / untested) |
| `foundation/observation-inference` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-observation-inference-20260922.json`) | opentelemetry-collector-contrib (conditional / untested); prometheus (conditional / untested); loki (conditional / untested) |
| `foundation/quality-evaluation` | dual_lane_same_winner | promptfoo (conditional / untested); playwright-test (conditional / untested) |
| `foundation/recovery-portability` | dual_lane_same_winner | restic (conditional / untested); candidate:astral-sh-uv (conditional / untested) |
| `foundation/scheduling-supervision` | dual_lane_same_winner | dagu (conditional / untested); systemd (conditional / untested) |
| `foundation/secrets-credentials` | dual_lane_same_winner | gitleaks (conditional / untested) |
| `foundation/semantic-rag` | dual_lane_same_winner | socraticode (accepted / untested); qdrant (accepted / untested); vllm (accepted / untested) |
| `foundation/token-efficiency` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-token-efficiency-20260922.json`) | rtk (conditional / untested); headroom (conditional / untested); ccusage (conditional / untested) |
| `foundation/web-research` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-web-research-20260922.json`) | tavily-cli (conditional / untested); agent-browser (conditional / untested); openresearch (conditional / untested) |
| `foundation/workers` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-workers-20260922.json`) | claude-code (conditional / untested); worktrunk (conditional / untested) |
| `us-equities/agents-models-workers` | dual_lane_same_winner | codex-native-sdk (accepted / untested); foundation-ai-memory (accepted / untested); foundation-socraticode (accepted / untested) |
| `us-equities/backtesting-engine` | dual_lane_same_winner | nautilustrader (accepted / untested); lean (accepted / untested) |
| `us-equities/data-quality-orchestration` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-data-quality-orchestration-20260922.json`) | dagu (conditional / untested); data-pandera (conditional / untested) |
| `us-equities/evaluation-experiments` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-evaluation-experiments-20260922.json`) | foundation-agent-retrieval-bench (not_established / untested); inspect-ai (not_established / untested); data-mlflow (not_established / untested) |
| `us-equities/execution-broker` | pending_lanes (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-execution-broker-20260922.json`) | - |
| `us-equities/identity-provenance` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-identity-provenance-20260922.json`) | data-dvc (not_established / untested) |
| `us-equities/market-data-reference` | dual_lane_same_winner | data-alpaca-py (accepted / untested); data-edgartools (accepted / untested); data-exchange-calendars (accepted / untested) |
| `us-equities/observability-hosting` | pending_lanes (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-observability-hosting-20260922.json`) | - |
| `us-equities/portfolio-risk` | dual_lane_same_winner | skfolio (accepted / untested) |
| `us-equities/research-factors-ml` | dual_lane_same_winner | skfolio (accepted / untested); data-edgartools (accepted / untested) |
| `us-equities/security-supply-chain` | dual_lane_same_winner | grype (accepted / untested); syft (accepted / untested); gitleaks (accepted / untested) |
| `us-equities/storage-compute` | dual_lane_same_winner | data-duckdb (accepted / untested) |

## Needs host evidence

Winners whose per-platform `e2e_state` is neither `accepted` nor `host_verified`, grouped by platform. This is the list other WSL/macOS machines should work through with [`docs/contributing-evidence.md`](contributing-evidence.md); most `macos-arm64` entries are expected here today, since every current `macos-arm64` `platform_status` is `untested`.

### linux-wsl2-x86_64

- `foundation/document-retrieval`: `markitdown` (catalog/e2e state: conditional)
- `foundation/document-retrieval`: `poppler` (catalog/e2e state: conditional)
- `foundation/document-retrieval`: `qmd` (catalog/e2e state: conditional)
- `foundation/git-github-automation`: `candidate:cli-cli` (catalog/e2e state: not_established)
- `foundation/git-github-automation`: `difftastic` (catalog/e2e state: not_established)
- `foundation/git-github-automation`: `worktrunk` (catalog/e2e state: not_established)
- `foundation/instructions-skills`: `affaan-m/ECC` (catalog/e2e state: conditional)
- `foundation/instructions-skills`: `candidate:openai-skills` (catalog/e2e state: conditional)
- `foundation/instructions-skills`: `candidate:typesafe-ai-skills` (catalog/e2e state: conditional)
- `foundation/observation-inference`: `loki` (catalog/e2e state: conditional)
- `foundation/observation-inference`: `opentelemetry-collector-contrib` (catalog/e2e state: conditional)
- `foundation/observation-inference`: `prometheus` (catalog/e2e state: conditional)
- `foundation/quality-evaluation`: `playwright-test` (catalog/e2e state: conditional)
- `foundation/quality-evaluation`: `promptfoo` (catalog/e2e state: conditional)
- `foundation/recovery-portability`: `candidate:astral-sh-uv` (catalog/e2e state: conditional)
- `foundation/recovery-portability`: `restic` (catalog/e2e state: conditional)
- `foundation/scheduling-supervision`: `dagu` (catalog/e2e state: conditional)
- `foundation/scheduling-supervision`: `systemd` (catalog/e2e state: conditional)
- `foundation/secrets-credentials`: `gitleaks` (catalog/e2e state: conditional)
- `foundation/token-efficiency`: `ccusage` (catalog/e2e state: conditional)
- `foundation/token-efficiency`: `headroom` (catalog/e2e state: conditional)
- `foundation/token-efficiency`: `rtk` (catalog/e2e state: conditional)
- `foundation/web-research`: `agent-browser` (catalog/e2e state: conditional)
- `foundation/web-research`: `openresearch` (catalog/e2e state: conditional)
- `foundation/web-research`: `tavily-cli` (catalog/e2e state: conditional)
- `foundation/workers`: `claude-code` (catalog/e2e state: conditional)
- `foundation/workers`: `worktrunk` (catalog/e2e state: conditional)
- `us-equities/data-quality-orchestration`: `dagu` (catalog/e2e state: conditional)
- `us-equities/data-quality-orchestration`: `data-pandera` (catalog/e2e state: conditional)
- `us-equities/evaluation-experiments`: `data-mlflow` (catalog/e2e state: not_established)
- `us-equities/evaluation-experiments`: `foundation-agent-retrieval-bench` (catalog/e2e state: not_established)
- `us-equities/evaluation-experiments`: `inspect-ai` (catalog/e2e state: not_established)
- `us-equities/identity-provenance`: `data-dvc` (catalog/e2e state: not_established)

### macos-arm64

- `foundation/agent-sdks`: `codex` (catalog/e2e state: untested)
- `foundation/ci-supply-chain`: `candidate:actions-attest` (catalog/e2e state: untested)
- `foundation/ci-supply-chain`: `syft` (catalog/e2e state: untested)
- `foundation/ci-supply-chain`: `zizmor` (catalog/e2e state: untested)
- `foundation/code-navigation`: `serena` (catalog/e2e state: untested)
- `foundation/document-retrieval`: `markitdown` (catalog/e2e state: untested)
- `foundation/document-retrieval`: `poppler` (catalog/e2e state: untested)
- `foundation/document-retrieval`: `qmd` (catalog/e2e state: untested)
- `foundation/durable-memory`: `ai-memory` (catalog/e2e state: untested)
- `foundation/git-github-automation`: `candidate:cli-cli` (catalog/e2e state: untested)
- `foundation/git-github-automation`: `difftastic` (catalog/e2e state: untested)
- `foundation/git-github-automation`: `worktrunk` (catalog/e2e state: untested)
- `foundation/hosting-services`: `fastapi` (catalog/e2e state: untested)
- `foundation/hosting-services`: `nextjs` (catalog/e2e state: untested)
- `foundation/hosting-services`: `postgresql` (catalog/e2e state: untested)
- `foundation/instructions-skills`: `affaan-m/ECC` (catalog/e2e state: untested)
- `foundation/instructions-skills`: `candidate:openai-skills` (catalog/e2e state: untested)
- `foundation/instructions-skills`: `candidate:typesafe-ai-skills` (catalog/e2e state: untested)
- `foundation/isolation`: `sandbox-runtime` (catalog/e2e state: untested)
- `foundation/isolation`: `worktrunk` (catalog/e2e state: untested)
- `foundation/mcp-surfaces`: `mcp-inspector` (catalog/e2e state: untested)
- `foundation/mcp-surfaces`: `mcporter` (catalog/e2e state: untested)
- `foundation/native-clients`: `claude-code` (catalog/e2e state: untested)
- `foundation/native-clients`: `codex` (catalog/e2e state: untested)
- `foundation/observation-inference`: `loki` (catalog/e2e state: untested)
- `foundation/observation-inference`: `opentelemetry-collector-contrib` (catalog/e2e state: untested)
- `foundation/observation-inference`: `prometheus` (catalog/e2e state: untested)
- `foundation/quality-evaluation`: `playwright-test` (catalog/e2e state: untested)
- `foundation/quality-evaluation`: `promptfoo` (catalog/e2e state: untested)
- `foundation/recovery-portability`: `candidate:astral-sh-uv` (catalog/e2e state: untested)
- `foundation/recovery-portability`: `restic` (catalog/e2e state: untested)
- `foundation/scheduling-supervision`: `dagu` (catalog/e2e state: untested)
- `foundation/scheduling-supervision`: `systemd` (catalog/e2e state: untested)
- `foundation/secrets-credentials`: `gitleaks` (catalog/e2e state: untested)
- `foundation/semantic-rag`: `qdrant` (catalog/e2e state: untested)
- `foundation/semantic-rag`: `socraticode` (catalog/e2e state: untested)
- `foundation/semantic-rag`: `vllm` (catalog/e2e state: untested)
- `foundation/token-efficiency`: `ccusage` (catalog/e2e state: untested)
- `foundation/token-efficiency`: `headroom` (catalog/e2e state: untested)
- `foundation/token-efficiency`: `rtk` (catalog/e2e state: untested)
- `foundation/web-research`: `agent-browser` (catalog/e2e state: untested)
- `foundation/web-research`: `openresearch` (catalog/e2e state: untested)
- `foundation/web-research`: `tavily-cli` (catalog/e2e state: untested)
- `foundation/workers`: `claude-code` (catalog/e2e state: untested)
- `foundation/workers`: `worktrunk` (catalog/e2e state: untested)
- `us-equities/agents-models-workers`: `codex-native-sdk` (catalog/e2e state: untested)
- `us-equities/agents-models-workers`: `foundation-ai-memory` (catalog/e2e state: untested)
- `us-equities/agents-models-workers`: `foundation-socraticode` (catalog/e2e state: untested)
- `us-equities/backtesting-engine`: `lean` (catalog/e2e state: untested)
- `us-equities/backtesting-engine`: `nautilustrader` (catalog/e2e state: untested)
- `us-equities/data-quality-orchestration`: `dagu` (catalog/e2e state: untested)
- `us-equities/data-quality-orchestration`: `data-pandera` (catalog/e2e state: untested)
- `us-equities/evaluation-experiments`: `data-mlflow` (catalog/e2e state: untested)
- `us-equities/evaluation-experiments`: `foundation-agent-retrieval-bench` (catalog/e2e state: untested)
- `us-equities/evaluation-experiments`: `inspect-ai` (catalog/e2e state: untested)
- `us-equities/identity-provenance`: `data-dvc` (catalog/e2e state: untested)
- `us-equities/market-data-reference`: `data-alpaca-py` (catalog/e2e state: untested)
- `us-equities/market-data-reference`: `data-edgartools` (catalog/e2e state: untested)
- `us-equities/market-data-reference`: `data-exchange-calendars` (catalog/e2e state: untested)
- `us-equities/portfolio-risk`: `skfolio` (catalog/e2e state: untested)
- `us-equities/research-factors-ml`: `data-edgartools` (catalog/e2e state: untested)
- `us-equities/research-factors-ml`: `skfolio` (catalog/e2e state: untested)
- `us-equities/security-supply-chain`: `gitleaks` (catalog/e2e state: untested)
- `us-equities/security-supply-chain`: `grype` (catalog/e2e state: untested)
- `us-equities/security-supply-chain`: `syft` (catalog/e2e state: untested)
- `us-equities/storage-compute`: `data-duckdb` (catalog/e2e state: untested)

## Needs independent review

Rows whose `independent_review` is `pending_lanes` (a dual-lane disagreement that the counterbalanced adjudication did not resolve) or `single_lane` (no second lane recorded).

- `us-equities/execution-broker`: pending_lanes
- `us-equities/observability-hosting`: pending_lanes

## How to update this page

This page and `catalogs/landscape/component-evidence-matrix.json` are generated, not hand-edited. After adding host receipts, a decision, a gap-crosswalk regeneration or a landscape verdict update, run `python3 scripts/component_matrix.py --write` and commit both files. `python3 scripts/component_matrix.py --check` (run in CI) recomputes both outputs and also enforces the flip rule: a winner cannot show `macos-arm64` `platform_status: accepted` without at least one independently reviewed passing `native_proven` host receipt for that platform at stage `use` or `install`. Never edit `platform_status` in the landscape files to make this page pass; add the underlying host receipt instead, following [`docs/contributing-evidence.md`](contributing-evidence.md).
