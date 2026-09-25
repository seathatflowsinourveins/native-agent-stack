# Refresh and continue the stack

Use [manifest.json](manifest.json) as a small reference map. Do not load every catalog, memory archive or repository into a worker. The accepted pins live in `manifests/stack.json`; dated research and open gates live in `catalogs/us-equities/convergence-review.json`; receipt claims and hashes live in `manifests/evidence.json`.

For context/tool selection and usage comparisons, read the current
[token practice](../docs/token-practice.md). Retained-history counters, conversion
heuristics, exact artifact counts and final provider usage are separate. Keep their
scope and failures; do not sum snapshots or rerun model trials on ordinary resume.

## Resume an existing checkout

```sh
git status --short
git rev-parse HEAD
python3 scripts/validate.py
python3 scripts/validate_catalogs.py
```

Preserve uncommitted work. Fetch and review remote changes before selecting a new revision; never use a destructive reset to “refresh” a working machine. Read the relevant gate and native recipe, then inspect only its local prerequisites. A new host starts with unknown account, activation and acceptance state even when the checkout validates.

## Moving a host to a new release

A host installs from the release pinned in `adoption/manifest.json`
`source.release_tag`/`source.release_commit` ([bootstrap step 0](bootstrap.md)).
Main moves ahead of that pin; a coordinator cuts a new release and re-pins, and
each host then moves to it on its own schedule.

**1. Learn whether a newer release exists.** Run the check from a fresh clone of
the default branch, not from the host's pinned checkout: the pinned tag may
predate `scripts/release_due.py`, and only the default branch's manifest names
the current pin (a release's own manifest names the release before it).

`HOST_CHECKOUT` is the pinned clone this host installed from; `RUN_DIR` is a
scratch directory for the default-branch clone, which steps 3.4 and 4 reuse
for recording (never record in `$HOST_CHECKOUT`: switching it to a branch of
`main` moves the install checkout off its tag).

```sh
HOST_CHECKOUT="$HOME/code/native-agent-stack"   # the pinned clone; use this host's own path
RUN_DIR="$(mktemp -d)"
git clone https://github.com/seathatflowsinourveins/native-agent-stack.git "$RUN_DIR/catalog-main"
cd "$RUN_DIR/catalog-main"
python3 scripts/release_due.py
python3 -c "import json;print(json.load(open('adoption/manifest.json'))['source']['release_tag'])"
git -C "$HOST_CHECKOUT" describe --tags --exact-match   # the tag this host installed from
gh release list --repo seathatflowsinourveins/native-agent-stack --limit 5
```

If the default branch pins a different tag than the host's checkout, a re-pin
has landed: move the host (steps 3 and 4). `release_due.py` printing
`"status": "release_due"` means main documents steps that the pinned release
lacks (a release is due, not yet cut); the pages that use them mark those steps "added
after `<release_tag>`". `"status": "content_changed"` means the release has every
documented path but ships a different copy of some new-machine files (its
`changed` list: a script, pin file, hook, step text or README's Start here
section). A pinned host runs the release's copies, so a release is due then too. A published release that main does not pin
yet is not a target; wait for its re-pin PR.

**2. How the coordinator cuts and re-pins a release.** This is the maintainer
flow, recorded so a host can check what it receives.

1. Tag a validated `main` commit `vYYYY.MM.DD` (or `vYYYY.MM.DD.N`) and push the
   tag. [`publish-catalog.yml`](../.github/workflows/publish-catalog.yml) runs on
   `v*` tags: its `publish` job validates the commit, builds the `git archive`
   and an SPDX SBOM, attests both with SLSA provenance and uploads them; its
   `release` job (tag pushes only) re-checks both files against the attested
   digests, creates the GitHub Release with both attached at creation, and
   fails unless the published release is immutable and carries exactly those
   digests.
2. Verify the published files (the release notes print these commands with
   the exact values):
   ```sh
   gh attestation verify native-agent-stack-<commit>.tar.gz \
     --repo seathatflowsinourveins/native-agent-stack \
     --signer-workflow seathatflowsinourveins/native-agent-stack/.github/workflows/publish-catalog.yml \
     --source-ref refs/tags/<tag> --source-digest <commit>
   gh release verify-asset <tag> native-agent-stack-<commit>.tar.gz \
     --repo seathatflowsinourveins/native-agent-stack
   ```
   [`docs/catalog-provenance.md`](../docs/catalog-provenance.md) covers the
   attestation model and detached-bundle verification.
3. Open a re-pin PR that sets `source.release_tag` and `source.release_commit`
   (and `updated_at`) in `adoption/manifest.json` and re-registers its hash in
   `manifests/evidence.json`. `python3 scripts/release_due.py --strict` must
   print `"status": "current"` (empty `due` and `changed`: tag the latest `main`
   and open the re-pin PR before other new-machine changes land, or cut again;
   update the PR branch from `main` right before merging, because the main
   ruleset does not require an up-to-date branch and the post-merge push run of
   `validate.yml` is not strict);
   `validate.yml` runs
   `release_due.py --strict-if-repinned origin/main`, which is strict because
   the pinned commit changed, and `tests/test_release_pin_contents.py` checks
   that the tag resolves to the pinned commit and that the release's own
   documents reference only paths it contains. The "added after `vT`" and
   "changed after `vT`" notes and the "(X at `vT`)" pin-coverage notes name the
   release they were written against, so they stay true at the new tag and
   the re-pin PR does not have to edit them;
   `tests/test_adoption_docs_consistency.py` then requires notes only for
   what the new release still lacks or runs differently, naming the new tag.
   Stale history notes can be dropped in any later PR.

**3. What the host re-runs after moving.** Receipts bind to the component
version they recorded, so a pin change retires them for that component.

```sh
cd "$HOST_CHECKOUT"
git status --short                 # keep local work; never reset it away
git fetch --tags origin
old="$(git rev-parse HEAD)"
tag="$(git show origin/HEAD:adoption/manifest.json | python3 -c "import json,sys;print(json.load(sys.stdin)['source']['release_tag'])")"
git diff --stat "$old" "$tag" -- adoption/pins-linux-x86_64.json adoption/pins-macos-arm64.json \
  adoption/manifest.json adoption/templates manifests/stack.json catalogs/landscape
git checkout "$tag"
```

1. If a pin file or `adoption/manifest.json` profile changed, rerun the
   bootstrap for each profile this host installed
   ([bootstrap step 2](bootstrap.md)); it installs the new pinned versions.
2. If `adoption/templates/` changed, render again and compare before
   overwriting ([bootstrap step 4](bootstrap.md), `render_config.py --check`).
3. Rerun `uv run --no-project --python 3.13 python scripts/adoption_status.py --profile <id> --json`.
4. In the default-branch clone from step 1 (`cd "$RUN_DIR/catalog-main"`, on the
   branch step 4 creates), record a new receipt with
   `python3 scripts/host_receipts.py record` for every component whose pin changed (in the pin files, `manifests/stack.json`, or a
   winner's `pin` in `catalogs/landscape/*.json`). A receipt counts toward a
   winner's status only while its `tool_versions` entry equals the winner's
   current pin, so older receipts stop counting until they are re-recorded.
   `python3 scripts/receipt_staleness.py` on the default branch lists them:
   `pin_moved` names each host and stage whose newest receipt is still at a
   retired pin (it clears once that host records at the current pin, even
   though the old receipt stays), `no_bound_receipt` a bucket with none at the
   current pin, and `stale` a latest bound receipt older than 30 days
   (`--max-age-days` to change the window).
   [`receipt-staleness.yml`](../.github/workflows/receipt-staleness.yml) runs
   the same report weekly and uploads it as an artifact; it never fails on a
   flag and writes nothing to the repository.

**4. How the receipts reach the catalog.** Follow
[the host evidence contribution guide](../docs/contributing-evidence.md): record
in the default-branch clone from step 1, not in `$HOST_CHECKOUT`, on a branch
of current `main` (`cd "$RUN_DIR/catalog-main" && git fetch origin && git
switch -c <branch> origin/main`), re-read and scan the receipts, and before opening the PR rebase
onto `origin/main` and rerun

```sh
python3 scripts/component_matrix.py --write
python3 scripts/new_host_grand_list.py --write
python3 scripts/host_receipts.py validate
python3 scripts/validate.py
```

then open the PR with the template's "Host evidence" section and ask for an
independent review. Receipts recorded before the move stay in the tree as dated
evidence; they are not edited or deleted.

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

On macOS, run the Gitleaks step through `adoption/tools/gitleaks-guarded-macos`
so that it takes the per-user lock and the memory cap
([adoption/tools/README.md](tools/README.md#macos-gitleaks-guarded-macos-2026-09-24)).

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

The current entry point is the [20-layer research queue](../catalogs/landscape/research-state.json)
and its [continuation protocol](../docs/landscape-continuation.md). Choose one
recorded gap. For the north star, [runtime-target.json](../catalogs/us-equities/runtime-target.json)
governs the selected Nautilus destination and separate IBKR/Alpaca acceptance.
SPY/LEAN parity and the dividend module are established (the simulation rung
is ready by `python3 scripts/trading_gates.py --check`); native broker fault
cases and the paper and live gates remain open. The
older catalyst plans below retain data/research context and do not override
these current engine and broker boundaries.

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
