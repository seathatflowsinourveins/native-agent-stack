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

Each winner shows, for linux-wsl2-x86_64 / macos-arm64, its `e2e_state` and host receipts as [pass/fail/independently reviewed pass/independently reviewed fail], plus `dissented N` when a reviewer's latest verdict is disagree or needs_changes. Receipt counts ignore pins; the derived status in the JSON binds receipts to the winner's current pin.

| Layer | Independent review | Winners: e2e_state [receipts] (linux-wsl2-x86_64 / macos-arm64) |
| --- | --- | --- |
| `foundation/agent-sdks` | dual_lane_same_winner | codex (accepted [1/0/1/0] / untested [0/0/0/0]) |
| `foundation/ci-supply-chain` | dual_lane_same_winner | zizmor (accepted [0/0/0/0] / untested [0/0/0/0]); syft (accepted [0/0/0/0] / untested [0/0/0/0]); candidate:actions-attest (accepted [0/0/0/0] / untested [0/0/0/0]) |
| `foundation/code-navigation` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-code-navigation-20260922.json`) | serena (accepted [0/0/0/0] / untested [0/0/0/0]) |
| `foundation/document-retrieval` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-document-retrieval-20260922.json`) | qmd (host_verified [1/0/1/0] / untested [0/0/0/0]); markitdown (host_verified [1/0/1/0] / untested [0/0/0/0]); poppler (conditional [1/0/1/0] / untested [0/0/0/0]) |
| `foundation/durable-memory` | dual_lane_same_winner | ai-memory (accepted [1/0/1/0] / untested [0/0/0/0]) |
| `foundation/git-github-automation` | dual_lane_same_winner | worktrunk (host_verified [1/0/1/0] / host_verified [1/0/1/0]); candidate:cli-cli (not_established [0/0/0/0] / untested [0/0/0/0]); difftastic (host_verified [1/1/1/0] / untested [0/0/0/0]) |
| `foundation/hosting-services` | dual_lane_same_winner | fastapi (accepted [0/0/0/0] / untested [1/0/0/0] dissented 1); nextjs (accepted [0/0/0/0] / untested [1/0/0/0] dissented 1); postgresql (accepted [0/0/0/0] / untested [1/0/0/0] dissented 1) |
| `foundation/instructions-skills` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-instructions-skills-20260922.json`) | affaan-m/ECC (conditional [0/0/0/0] / untested [0/0/0/0]); candidate:typesafe-ai-skills (conditional [0/0/0/0] / untested [0/0/0/0]); candidate:openai-skills (conditional [0/0/0/0] / untested [0/0/0/0]) |
| `foundation/isolation` | dual_lane_same_winner | worktrunk (host_verified [1/0/1/0] / host_verified [1/0/1/0]); sandbox-runtime (accepted [0/0/0/0] / untested [0/0/0/0]) |
| `foundation/mcp-surfaces` | dual_lane_same_winner | mcporter (accepted [1/0/1/0] / untested [0/0/0/0]); mcp-inspector (accepted [0/0/0/0] / untested [0/0/0/0]) |
| `foundation/native-clients` | dual_lane_same_winner | claude-code (accepted [0/0/0/0] / untested [0/0/0/0]); codex (accepted [1/0/1/0] / untested [0/0/0/0]) |
| `foundation/observation-inference` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-observation-inference-20260922.json`) | opentelemetry-collector-contrib (host_verified [1/0/1/0] / untested [0/0/0/0]); prometheus (host_verified [1/0/1/0] / untested [0/0/0/0]); loki (host_verified [1/0/1/0] / untested [0/0/0/0]) |
| `foundation/quality-evaluation` | dual_lane_same_winner | promptfoo (conditional [0/0/0/0] / untested [0/0/0/0]); playwright-test (conditional [0/0/0/0] / untested [1/0/0/0] dissented 1) |
| `foundation/recovery-portability` | dual_lane_same_winner | restic (host_verified [1/0/1/0] / untested [0/0/0/0]); candidate:astral-sh-uv (conditional [0/0/0/0] / untested [0/0/0/0]) |
| `foundation/scheduling-supervision` | dual_lane_same_winner | dagu (host_verified [1/0/1/0] / untested [0/0/0/0]); systemd (conditional [1/0/0/0] dissented 1 / untested [0/0/0/0]) |
| `foundation/secrets-credentials` | dual_lane_same_winner | gitleaks (host_verified [1/0/1/0] / host_verified [1/0/1/0]) |
| `foundation/semantic-rag` | dual_lane_same_winner | socraticode (accepted [0/0/0/0] / untested [0/0/0/0]); qdrant (host_verified [1/0/1/0] / untested [0/0/0/0]); vllm (host_verified [2/0/1/0] / untested [0/0/0/0]) |
| `foundation/token-efficiency` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-token-efficiency-20260922.json`) | rtk (host_verified [2/0/1/0] / host_verified [1/0/1/0]); headroom (conditional [1/0/1/0] / untested [0/0/0/0]); ccusage (conditional [1/0/1/0] / untested [0/0/0/0]) |
| `foundation/web-research` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-web-research-20260922.json`) | tavily-cli (conditional [0/0/0/0] / untested [0/0/0/0]); agent-browser (conditional [0/0/0/0] / untested [0/0/0/0]); openresearch (conditional [0/0/0/0] / untested [0/0/0/0]) |
| `foundation/workers` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/foundation-workers-20260922.json`) | claude-code (conditional [0/0/0/0] / untested [0/0/0/0]); worktrunk (host_verified [1/0/1/0] / host_verified [1/0/1/0]) |
| `us-equities/agents-models-workers` | dual_lane_same_winner | codex-native-sdk (accepted [0/0/0/0] / untested [0/0/0/0]); foundation-ai-memory (accepted [0/0/0/0] / untested [0/0/0/0]); foundation-socraticode (accepted [0/0/0/0] / untested [0/0/0/0]) |
| `us-equities/backtesting-engine` | dual_lane_same_winner | nautilustrader (host_verified [1/0/1/0] / untested [0/0/0/0] +1 alias receipt(s), not counted); lean (accepted [0/0/0/0] / untested [0/0/0/0]) |
| `us-equities/data-quality-orchestration` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-data-quality-orchestration-20260922.json`) | dagu (host_verified [1/0/1/0] / untested [0/0/0/0]); data-pandera (conditional [0/0/0/0] / untested [0/0/0/0]) |
| `us-equities/evaluation-experiments` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-evaluation-experiments-20260922.json`) | foundation-agent-retrieval-bench (not_established [0/0/0/0] / untested [0/0/0/0]); inspect-ai (not_established [0/0/0/0] / untested [0/0/0/0]); data-mlflow (not_established [0/0/0/0] / untested [0/0/0/0]) |
| `us-equities/execution-broker` | pending_lanes (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-execution-broker-20260922.json`) | - |
| `us-equities/identity-provenance` | dual_lane_adjudicated (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-identity-provenance-20260922.json`) | data-dvc (not_established [0/0/0/0] / untested [0/0/0/0]) |
| `us-equities/market-data-reference` | dual_lane_same_winner | data-alpaca-py (accepted [0/0/0/0] / untested [0/0/0/0] +1 alias receipt(s), not counted); data-edgartools (accepted [0/0/0/0] / untested [0/0/0/0]); data-exchange-calendars (accepted [0/0/0/0] / untested [0/0/0/0]) |
| `us-equities/observability-hosting` | pending_lanes (adjudication: `evidence/artifacts/layer-verdicts-20260922/adjudication/us-equities-observability-hosting-20260922.json`) | - |
| `us-equities/portfolio-risk` | dual_lane_same_winner | skfolio (accepted [0/0/0/0] / untested [0/0/0/0]) |
| `us-equities/research-factors-ml` | dual_lane_same_winner | skfolio (accepted [0/0/0/0] / untested [0/0/0/0]); data-edgartools (accepted [0/0/0/0] / untested [0/0/0/0]) |
| `us-equities/security-supply-chain` | dual_lane_same_winner | grype (accepted [0/0/0/0] / untested [0/0/0/0]); syft (accepted [0/0/0/0] / untested [0/0/0/0]); gitleaks (host_verified [1/0/1/0] / host_verified [1/0/1/0]) |
| `us-equities/storage-compute` | dual_lane_same_winner | data-duckdb (accepted [0/0/0/0] / untested [0/0/0/0] +1 alias receipt(s), not counted) |

## Alias receipts (listed, never counted)

Receipts recorded under a `manifests/stack.json` id whose repository is a winner's repository (`scripts/host_receipts.py` `winner_stack_aliases`). Receipts bind to a winner only by its own `component_id` and full pin, so these never enter the counts, the derived status, the flip rule or `e2e_state`. `scripts/host_receipts.py record` refuses such ids, and `validate` rejects such receipts except those grandfathered unchanged, by path and recorded-claim digest, in `GRANDFATHERED_ALIAS_RECEIPTS`; re-recording on the same host under the winner's `component_id` with its full pin is the path to binding. Listed: 3 alias receipt(s) from host(s) `macos-m5pro-20260924`, observed 2026-09-24; 3 of 3 grandfathered.

- `us-equities/backtesting-engine` `nautilustrader` macos-arm64: `evidence/hosts/macos-m5pro-20260924/macos-m5pro-20260924--nautilus-trader--use--20260924.json` recorded as `nautilus-trader` '2.0.0rc5' (local_integration, use, pass); binds: no (id alias; version does not match the pin in full; grandfathered)
- `us-equities/market-data-reference` `data-alpaca-py` macos-arm64: `evidence/hosts/macos-m5pro-20260924/macos-m5pro-20260924--alpaca-py--use--20260924.json` recorded as `alpaca-py` '0.44.0' (native_proven, use, pass); binds: no (id alias; version does not match the pin in full; grandfathered)
- `us-equities/storage-compute` `data-duckdb` macos-arm64: `evidence/hosts/macos-m5pro-20260924/macos-m5pro-20260924--duckdb--use--20260924.json` recorded as `duckdb` '1.5.5' (native_proven, use, pass); binds: no (id alias; version does not match the pin in full; grandfathered)

## Needs host evidence

Winners whose per-platform `e2e_state` is neither `accepted` nor `host_verified`, grouped by platform. This is the list other WSL/macOS machines should work through with [`docs/contributing-evidence.md`](contributing-evidence.md). `macos-arm64` entries stay here until a Mac records receipts that `scripts/platform_status.py` accepts and the layer rows are re-recorded.

### linux-wsl2-x86_64

- `foundation/document-retrieval`: `poppler` (catalog/e2e state: conditional)
- `foundation/git-github-automation`: `candidate:cli-cli` (catalog/e2e state: not_established)
- `foundation/instructions-skills`: `affaan-m/ECC` (catalog/e2e state: conditional)
- `foundation/instructions-skills`: `candidate:openai-skills` (catalog/e2e state: conditional)
- `foundation/instructions-skills`: `candidate:typesafe-ai-skills` (catalog/e2e state: conditional)
- `foundation/quality-evaluation`: `playwright-test` (catalog/e2e state: conditional)
- `foundation/quality-evaluation`: `promptfoo` (catalog/e2e state: conditional)
- `foundation/recovery-portability`: `candidate:astral-sh-uv` (catalog/e2e state: conditional)
- `foundation/scheduling-supervision`: `systemd` (catalog/e2e state: conditional)
- `foundation/token-efficiency`: `ccusage` (catalog/e2e state: conditional)
- `foundation/token-efficiency`: `headroom` (catalog/e2e state: conditional)
- `foundation/web-research`: `agent-browser` (catalog/e2e state: conditional)
- `foundation/web-research`: `openresearch` (catalog/e2e state: conditional)
- `foundation/web-research`: `tavily-cli` (catalog/e2e state: conditional)
- `foundation/workers`: `claude-code` (catalog/e2e state: conditional)
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
- `foundation/hosting-services`: `fastapi` (catalog/e2e state: untested)
- `foundation/hosting-services`: `nextjs` (catalog/e2e state: untested)
- `foundation/hosting-services`: `postgresql` (catalog/e2e state: untested)
- `foundation/instructions-skills`: `affaan-m/ECC` (catalog/e2e state: untested)
- `foundation/instructions-skills`: `candidate:openai-skills` (catalog/e2e state: untested)
- `foundation/instructions-skills`: `candidate:typesafe-ai-skills` (catalog/e2e state: untested)
- `foundation/isolation`: `sandbox-runtime` (catalog/e2e state: untested)
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
- `foundation/semantic-rag`: `qdrant` (catalog/e2e state: untested)
- `foundation/semantic-rag`: `socraticode` (catalog/e2e state: untested)
- `foundation/semantic-rag`: `vllm` (catalog/e2e state: untested)
- `foundation/token-efficiency`: `ccusage` (catalog/e2e state: untested)
- `foundation/token-efficiency`: `headroom` (catalog/e2e state: untested)
- `foundation/web-research`: `agent-browser` (catalog/e2e state: untested)
- `foundation/web-research`: `openresearch` (catalog/e2e state: untested)
- `foundation/web-research`: `tavily-cli` (catalog/e2e state: untested)
- `foundation/workers`: `claude-code` (catalog/e2e state: untested)
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
- `us-equities/security-supply-chain`: `grype` (catalog/e2e state: untested)
- `us-equities/security-supply-chain`: `syft` (catalog/e2e state: untested)
- `us-equities/storage-compute`: `data-duckdb` (catalog/e2e state: untested)

## Needs independent review

Rows whose `independent_review` is `pending_lanes` (a dual-lane disagreement that the counterbalanced adjudication did not resolve) or `single_lane` (no second lane recorded).

- `us-equities/execution-broker`: pending_lanes
- `us-equities/observability-hosting`: pending_lanes

## How to update this page

This page and `catalogs/landscape/component-evidence-matrix.json` are generated, not hand-edited. After adding host receipts, a decision, a gap-crosswalk regeneration or a landscape verdict update, run `python3 scripts/component_matrix.py --write` and commit both files. `python3 scripts/component_matrix.py --check` (run in CI) recomputes both outputs and also enforces the flip rule, which `scripts/landscape.py` enforces too through the same function (`scripts/platform_status.py`): a declared `macos-arm64` `platform_status` may not claim more than the recorded evidence supports. `accepted` needs a host receipt for that platform at stage `use` (an `install` pass supports `conditional` at most) that is `result: pass` and `evidence_class: native_proven`, records the winner's current pin in `tool_versions`, declares `host.second_physical_machine: true`, has `host.os`/`host.architecture` consistent with `adoption/manifest.json`'s `platform_profiles[]` entry, and carries an `agree` review from a reviewer identity other than the recorder's with no standing `disagree`/`needs_changes` review. A `native_proven` `use`/`install` fail that is the latest receipt for its host and stage blocks `accepted` until that host records a later pass. `conditional` needs a pin-bound, non-`synthetic` pass from a declared second physical machine with no standing dissent. Never edit `platform_status` in the landscape files to make this page pass; add the underlying host receipt instead, following [`docs/contributing-evidence.md`](contributing-evidence.md).
