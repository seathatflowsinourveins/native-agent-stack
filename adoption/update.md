# Refresh and continue the stack

Use [manifest.json](manifest.json) as a small reference map. Do not load every catalog, memory archive or repository into a worker. The accepted pins live in `manifests/stack.json`; dated research and open gates live in `catalogs/us-equities/convergence-review.json`; receipt claims and hashes live in `manifests/evidence.json`.

## Resume an existing checkout

```sh
git status --short
git rev-parse HEAD
python3 scripts/validate.py
python3 scripts/validate_catalogs.py
```

Preserve uncommitted work. Fetch and review remote changes before selecting a new revision; never use a destructive reset to “refresh” a working machine. Read the relevant gate and native recipe, then inspect only its local prerequisites. A new host starts with unknown account, activation and acceptance state even when the checkout validates.

## Refresh sources with native commands

Set `STAR_OWNER` to the intended public account and `PRIVATE_RUN_DIR` to a new private directory outside Git. Native GitHub CLI uses its own login; do not export its tokens into scripts.

```sh
gh api --paginate --slurp "users/$STAR_OWNER/starred?per_page=100" \
  > "$PRIVATE_RUN_DIR/public-stars.pages.json"
gh api repos/astral-sh/uv/releases/latest \
  > "$PRIVATE_RUN_DIR/uv-release.json"
gh api repos/mksglu/context-mode/commits/main \
  > "$PRIVATE_RUN_DIR/context-mode-main.json"
hf models info nvidia/Nemotron-3-Embed-1B-BF16
```

These examples read changing metadata; they are **not** installers or automatic upgrades. Verify current native CLI help before applying a changed upstream command. The HF model identity is an example from the catalog; preserve exact publisher ID/revision/task/pooling/dimensions when selecting the actual model. For HF endpoints not supported by the installed CLI, use its documented Python Hub client rather than inventing flags.

Compare repository identities against the full starred ledger, then inspect changes only for selected layers and plausible alternatives. For each candidate record repository identity, release/source revision, review timestamp, source URLs, license, concrete capability, omissions and a decision: adopt, retain, investigate or omit. Metadata review, source review, useful native CLI acceptance and model-mediated E2E are separate depths. Save failed access attempts; do not repeatedly retry unchanged entitlement, authentication or rate-limit failures.

Two bounded review waves can exhaust the **selected candidate set**, not the whole field. The September 19 portability review checked six environment managers and the full public-star identity delta. A newer release does not supersede an accepted pin until relevant compatibility passes; the recorded vLLM/WSL failure is a concrete reason to retain a working version.

## Change only the selected layer

1. Review upstream release/command documentation and dependency/architecture/license implications. Keep a rollback prefix and source reference.
2. Install the candidate in an isolated target through native tools. For SDK changes update direct requirements and affected constraints, then regenerate the [hash lock](sdk/README.md).
3. Run the smallest useful acceptance for that capability. Installation/version output alone is insufficient. Record exact native command, exit/status, useful result, skips, scope, inputs and limitations.
4. For model workers, check native account/model readiness first. Use the current selected model and bounded evidence packet; preserve complete usage categories. Keep deterministic numeric/risk/order logic outside model decisions.
5. If observability is selected, query the matching run's events and reconcile native usage once. Context Mode estimates, selected-text reductions, cache reuse and provider totals are different measurements; never add them into a claimed net saving.
6. Update the component pin only after acceptance. Append a sanitized receipt with a reciprocal component/evidence link; keep old failures dated. Update the convergence gate only when its stated requirement is met.
7. Refresh both evidence-integrity maps when their covered bytes change, run validation/tests in the appropriate environment, obtain independent review for substantive code, scan publication content for secrets, then publish. Inspect the exact commit's CI result.

Repository verification:

```sh
python3 scripts/validate.py
python3 scripts/validate_catalogs.py
"$SDK_ENV/bin/python" -m unittest discover -s tests -v
git diff --check
gitleaks dir . --redact --no-banner
```

CI validates public artifacts and code behavior. It does not log in, place broker orders, reproduce the GPU stack or consume model allowance. Local accepted runtime results retain their own receipts.

## Refresh only adopted retrieval

On a host that already adopted the named index:

```sh
qmd --index native-agent-stack-catalog update
qmd --index native-agent-stack-catalog search "native worker" \
  -c us-equities-foundation -n 3 --format json
```

Use `qmd get` on the exact returned document URI with a bounded range. [Native catalog setup](../catalogs/us-equities/native-workflows.md) records explicit collections; do not index the whole home or authentication directories. The frozen retrieval evaluation retains its original corpus and queries even when the live index grows. A generation-model upgrade does not automatically change embeddings or retrieval quality.

## Current next moves

Continue with the [September 20 catalyst-convergence plan](../blueprints/us-equities/catalyst-convergence/plan.json)
and its [native results and next gates](../blueprints/us-equities/catalyst-convergence/README.md).
Reuse verified retained sources where available; a new machine must acquire its
own permitted data and establish its own observations. A historical receipt is
not that host's first-received evidence or an authenticated provider result.

Start with the [latest offline acceptances](../blueprints/us-equities/acceptance-wave/README.md)
and the frozen [daily/intraday catalyst protocol](../blueprints/us-equities/catalyst-experiment/protocol.json).
The +200% historical mover cohort is a discovery design, not a collected dataset
or a strategy result. Preserve all eligible candidates, revisions and failed
signals when defining the next historical replay.

The canonical [open-gate ledger](../catalogs/us-equities/convergence-review.json) retains required inputs and accepted evidence. Priorities are:

The [architecture and role contract](../blueprints/us-equities/architecture/README.md)
and [latest source reviews](../catalogs/us-equities/architecture/README.md) record
platform, worker, data, execution-realism and Elite-adapter boundaries. New research
supplements must be registered with `scripts/catalog_decisions.py --write --supplement
PATH.json#/collection`; `--check` validates the union, counts and typed source
pointers. Regenerate after changing aliases or referenced decisions. This does
not automatically install a candidate or change an accepted native pin.

- Preserve the [accepted native Astra → Claude workflow](paired/README.md). Native device sign-in and fresh allowance checks succeeded on the authoring host; new hosts must establish their own readiness before replay.
- Select an entitled point-in-time data source and a strategy/universe/horizon/risk specification. The sample backtest is engine evidence, not an investment recommendation or approved strategy.
- Calibrate fill/latency/cost/capacity assumptions and test deterministic order recovery offline. Keep advanced Alpaca instructions unaccepted until payload preservation, valid wire contracts and actual account support pass.
- Improve retrieval against new held-out relevance judgments; preserve the measured lexical misses and evaluate the compatible semantic/hybrid lane before changing defaults.
- Select an independent backup/key destination and intended hosting lifecycle, then exercise recovery and interruption behavior. Same-host restore and a running local history server are narrower results.

A future session should pick a concrete unresolved gate, read its references, and make measurable progress. Repeatedly enlarging the catalog is not itself evidence that a runtime works.
