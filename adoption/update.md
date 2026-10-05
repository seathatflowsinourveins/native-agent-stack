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
   gh release verify <tag> --repo seathatflowsinourveins/native-agent-stack
   gh release verify-asset <tag> native-agent-stack-<commit>.tar.gz \
     --repo seathatflowsinourveins/native-agent-stack
   ```
   Stop on any verification failure. Native `gh release verify` checks the
   release integrity; it does not replace provenance attestation or the asset
   check. [`docs/catalog-provenance.md`](../docs/catalog-provenance.md) covers
   the attestation model and detached-bundle verification.
3. Open a re-pin PR that sets `source.release_tag` and `source.release_commit`
   (and `updated_at`) in `adoption/manifest.json` and re-registers its hash in
   `manifests/evidence.json`. `python3 scripts/release_due.py --strict` must
   print `"status": "current"` (empty `due` and `changed`: tag the latest `main`
   and open the re-pin PR before other new-machine changes land, or cut again;
   update the PR branch from `main` right before merging, because the main
   ruleset does not require an up-to-date branch and the post-merge push run of
   `validate.yml` is not strict);
   `validate.yml` runs
   `release_due.py --strict-if-repinned origin/main`, which becomes strict
   when either member of the `(release_tag, release_commit)` tuple changes.
   That re-pin path invokes
   `gh release verify <tag> --repo seathatflowsinourveins/native-agent-stack --format json`
   exactly once; an unavailable base is conservatively treated as a re-pin.
   Native failure, unavailability or malformed JSON fails the gate. Default
   reporting, an unchanged tuple and `--strict` alone make no verification or
   network calls; this is a re-pin check, not a daily verification task.
   `--strict` remains the local before-cut content check, and the report's
   `status`, `due` and `changed` still describe content; re-pin verification
   is reported separately as `release_verification` and through the exit code.
   `tests/test_release_pin_contents.py` checks that the tag resolves to the
   pinned commit and that the release's own documents reference only paths
   it contains. The "added after `vT`" and
   "changed after `vT`" notes and the "(X at `vT`)" pin-coverage notes name the
   release they were written against, so they stay true at the new tag and
   the re-pin PR does not have to edit them;
   `tests/test_adoption_docs_consistency.py` then requires notes only for
   what the new release still lacks or runs differently, naming the new tag.
   Stale history notes can be dropped in any later PR.

The [re-pin verification decision](../docs/decisions/2026-10-05-ci-release-repin-verification.md)
records the verification boundary and evidence.

**3. What the host re-runs after moving.** Receipts bind to the component
version they recorded, so a pin change retires them for that component.

```sh
cd "$HOST_CHECKOUT"
git status --short                 # keep local work; never reset it away
git fetch --tags origin
old="$(git rev-parse HEAD)"
tag="$(git show origin/HEAD:adoption/manifest.json | python3 -c "import json,sys;print(json.load(sys.stdin)['source']['release_tag'])")"
git diff --stat "$old" "$tag" -- adoption/pins-linux-x86_64.json adoption/pins-macos-arm64.json \
  adoption/manifest.json adoption/templates adoption/mcp adoption/agents manifests/stack.json catalogs/landscape
git checkout "$tag"
```

1. If a pin file or `adoption/manifest.json` profile changed, rerun the
   bootstrap for each profile this host installed
   ([bootstrap step 2](bootstrap.md)); it installs the new pinned versions.
   It also repoints each tool's `bin/` link at once, so when the ai-memory pin
   changed on a host with an existing store, stop the service and take the
   at-rest copy in [upgrading an existing store](../recipes/README.md#upgrading-an-existing-store)
   before this re-run.
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
5. If `adoption/mcp/` or `adoption/agents/` changed, rerun the client
   installers from the new checkout, each first as a report. On the Claude
   side, `python3 tools/adoption/install_claude_profile.py --dry-run`, then
   without `--dry-run`: it registers the template's servers this host lacks
   and leaves a differing registration unchanged unless `--replace-mcp` is
   given, so a server registered by hand is kept. Since 2026-09-30 the
   template names `socraticode`, `headroom`, `codebase-memory` and `qmd`
   besides `ai-memory` and `serena`; install each first
   ([bootstrap step 4a](bootstrap.md)). On the Codex side, the dry run of
   `python3 tools/adoption/apply_codex_lane.py` plans the role carriers, and
   `--worker-roles` adds the three worker roles of
   `adoption/agents/codex/workers/` once the token-adoption E2E's Gate A window
   has closed
   ([F4 Codex roles](../docs/decisions/2026-09-26-stack-agents-role-dispatch.md#addendum-2026-09-30-f4-codex-roles));
   apply what the dry run printed with its `--apply` form.

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
qmd --index native-agent-stack-catalog status   # read "Vectors: N embedded"
qmd --index native-agent-stack-catalog embed    # only when N is above 0
qmd --index native-agent-stack-catalog search "native worker" \
  -c us-equities-foundation -n 3 --format json
```

`update` re-indexes changed files and computes no vectors. Where the index carries embeddings (`status` reports `Vectors:` above 0), `embed` then embeds only the documents still lacking current vectors, such as new or changed ones (`embed -f` would re-embed everything); without it, the `vec` and `hyde` arms of `query` miss those documents. The lexical profile of [native catalog setup](../catalogs/us-equities/native-workflows.md) carries no vectors and skips `embed`; it also avoids a plain `query`, which expands the text with one model and reranks with another, both downloaded on first use. A `query` made of typed lexical searches with `rerank` off is model-free ([recipes](../recipes/README.md)). `update`'s closing "Run 'qmd embed'" notice prints on any index with unembedded documents, lexical ones included, so it is not the signal. Sources, qmd `v2.8.3`: README [L556](https://github.com/tobi/qmd/blob/v2.8.3/README.md?plain=1#L556), [L644-L651](https://github.com/tobi/qmd/blob/v2.8.3/README.md?plain=1#L644-L651) and [L1016-L1018](https://github.com/tobi/qmd/blob/v2.8.3/README.md?plain=1#L1016-L1018); `src/cli/qmd.ts` [L561](https://github.com/tobi/qmd/blob/v2.8.3/src/cli/qmd.ts#L561) and [L994-L1002](https://github.com/tobi/qmd/blob/v2.8.3/src/cli/qmd.ts#L994-L1002); `src/store.ts` [L1974-L1978](https://github.com/tobi/qmd/blob/v2.8.3/src/store.ts#L1974-L1978).

Use `qmd get` on the exact returned document URI with a bounded range. [Native catalog setup](../catalogs/us-equities/native-workflows.md) records explicit collections; do not index the whole home or authentication directories. A host that adopted the index before 2026-09-27 adds the two foundation collections, `foundation-adoption` and `foundation-docs`, once with the commands there; the carrier names all four collections in every `query`. The frozen retrieval evaluation retains its original corpus and queries even when the live index grows. A generation-model upgrade does not automatically change embeddings or retrieval quality.

## Apply the skills manifest

On a host that has adopted [`adoption/skills/manifest.json`](skills/manifest.json) (added after
`v2026.09.25.2`; see [the trial record](../docs/decisions/2026-09-25-skills-trial-and-usage.md)):

```sh
SKILLS=<tools-root>/skills-1.7.0/bin/skills
npm install --global --prefix <tools-root>/skills-1.7.0 skills@1.7.0    # the manifest's cli.install (pinned, isolated)
python3 tools/adoption/install_skills.py --skills-bin "$SKILLS" --dry-run   # prints what would change, changes nothing
python3 tools/adoption/install_skills.py --skills-bin "$SKILLS"             # installs every manifest entry at its pinned ref
python3 tools/adoption/install_skills.py --print-codex-config              # [[skills.config]] lines for ~/.codex/config.toml
python3 scripts/skills_status.py --skills-bin "$SKILLS"                    # per-skill ref, lock, links, listing state, Codex config, on-disk tree (informational)
claude -p "/skill-doctor" --output-format json                             # native per-skill use count, 0 API tokens
```

Run the dry run first on a host that has never applied this manifest, and compare its printed
changes against the manifest before running `--write`. The status script and `/skill-doctor` are
both read-only and safe to re-run by hand on any schedule; neither installs, removes or updates
anything, and `/skill-doctor` costs 0 API tokens (`num_turns` 0, model `<synthetic>`). Do not
wrap either read-only command in a systemd/launchd timer: this project's `automatic_model_calls`
policy is `false`, and a timer that invokes a model command is exactly what that policy
excludes, whatever the command's own token cost.

The `skills` step of `--configure-full-profile` (next section) runs the same `install_skills.py`,
after installing the manifest's pinned CLI under `$ECO_INSTALL_ROOT/tools/skills-<version>` when it is
missing.

## Refresh the user profile from main

Added after `v2026.09.26.2`. On Linux/WSL2, one command re-applies every user-scope layer this
catalog manages, instead of the hand steps of [bootstrap](bootstrap.md) steps 4 and 4a and the section
above:

```sh
git -C "$MAIN_CLONE" fetch origin && git -C "$MAIN_CLONE" checkout --detach origin/main
bash "$MAIN_CLONE/adoption/bootstrap-linux.sh" --profile <id> --configure-full-profile --host <name>
```

`MAIN_CLONE` is a clone used only for this; it must sit at `origin/main`, or the flag refuses and
prints both commits. The steps, in order, are `claude-profile`, `claude-settings`, `claude-md`,
`skills`, `codex-lane`, `path-block` and `login-shell` (the table is in
[bootstrap step 2](bootstrap.md)); each is idempotent and can be left out with `--skip <step>`. It
writes managed blocks into `~/.claude/CLAUDE.md` and `~/.profile` (backups beside each file), gives
a Codex home without `config.toml` the rendered user-level one minus the source host's trust state
(an existing `config.toml` is kept and only gains `features.daemon_auto_start = false` through
`codex features disable`, after a backup), and ends by checking that `claude` in a login shell is
the ecosystem launcher. A failed step exits 6
after the others have run. A host installed from a release tag keeps the per-step commands until
that release carries the flag.

## Refresh only native instruction blocks

Added after `v2026.09.26.2`. Use an exact reviewed source commit in a separate
source clone, as [bootstrap's newer-step rule](bootstrap.md) permits. Keep the
runtime installation checkout at its release pin. For example, with `NAS_SOURCE`
pointing to that source clone and `NAS_SOURCE_SHA` set to the accepted full SHA:

The full-block commands below are for files this catalog manages. A personal
file beginning `Generated from config/directives` belongs to its separate
producer. These commands refuse
that generated output; use the minimal source handoff below.

```sh
(
  set -eu
  test -n "$NAS_SOURCE_SHA"
  test -z "$(git -C "$NAS_SOURCE" status --porcelain)"
  git -C "$NAS_SOURCE" fetch origin main
  git -C "$NAS_SOURCE" checkout --detach "$NAS_SOURCE_SHA"
  test "$(git -C "$NAS_SOURCE" rev-parse HEAD)" = "$NAS_SOURCE_SHA"
  python3 "$NAS_SOURCE/tools/adoption/managed_block.py" --dry-run claude-md
  python3 "$NAS_SOURCE/tools/adoption/managed_block.py" --dry-run codex-md \
    --codex-home "${CODEX_HOME:-$HOME/.codex}"
)
```

Review the printed diffs, then recheck the exact clean source before writing:

```sh
(
  set -eu
  test -z "$(git -C "$NAS_SOURCE" status --porcelain)"
  test "$(git -C "$NAS_SOURCE" rev-parse HEAD)" = "$NAS_SOURCE_SHA"
  python3 "$NAS_SOURCE/tools/adoption/managed_block.py" claude-md
  python3 "$NAS_SOURCE/tools/adoption/managed_block.py" codex-md \
    --codex-home "${CODEX_HOME:-$HOME/.codex}"
)
```

These file-only operations
preserve text outside their owned markers, file modes and backups. Damaged
markers, detectable unmanaged copies and a nonblank Codex `AGENTS.override.md`
refuse rather than duplicate or shadow the rules. Select the intended Codex home
explicitly when this host has multiple clients. No client executable/version,
configuration, profile, role, authentication or service is changed by this helper.
The command establishes synchronized files; native client consumption remains
the host owner's separate readback/acceptance step.

### Minimal routing handoff for an existing instruction source

Added after `v2026.09.26.2`. The [three-line fragment](templates/decision-routing.md)
contains only the current bounded-discovery and maintained-decision paragraph,
between its own markers. It includes no model, effort, role, profile or RTK pack.
From the same exact clean source checkout:

```sh
(
  set -eu
  test -z "$(git -C "$NAS_SOURCE" status --porcelain)"
  test "$(git -C "$NAS_SOURCE" rev-parse HEAD)" = "$NAS_SOURCE_SHA"
  python3 "$NAS_SOURCE/tools/adoption/managed_block.py" decision-md --print
)
```

`--print` reads only the canonical source template and fragment. For the Mac
handoff, give this fragment to the `agent-ecosystem` producer owner. That owner
integrates it once in its owned `config/directives/shared.md`, renders through
its own `agent-ecosystem/scripts/directives.py`, and reviews the resulting instruction diff.
Do not append another full defaults/RTK pack to generated personal files or
change the producer's source from this cloud task. The owner retains its source
revision, local rules, imports, profiles, hook trust and installation receipt.

For an instruction source you already own, the helper can preview only
this paragraph. It prints the target's SHA-256:

```sh
python3 "$NAS_SOURCE/tools/adoption/managed_block.py" --dry-run decision-md \
  --target "$OWNED_INSTRUCTION_SOURCE"
```

Apply the reviewed fragment through the source owner's own guarded workflow.
`decision-md` exports or previews; it never writes a target, backup or temporary
file. A hash check followed by replacement cannot provide atomic protection
against a different writer, so this helper does not offer that write path.

The preview requires an existing nonblank source and proposes keeping every byte
outside its small block, including line endings, inline RTK and trailing blanks.
It refuses a generated output, damaged/repeated markers, conflicting
unmanaged routing text, symlink, nonregular or non-UTF-8 target. A single exact
current paragraph, including a wrapped paragraph, is already current. Standalone
native personal files can preview with
`--client claude` or `--client codex --codex-home PATH` instead of `--target`;
Codex still refuses a nonblank `AGENTS.override.md`. A later full-pack operation
refuses a narrow block rather than duplicating its rule.
When `CLAUDE_CONFIG_DIR` is set, either Claude operation requires an explicit
`--target` rather than guessing the intended user-memory location.
The full-profile bootstrap passes `$HOME/.claude/CLAUDE.md` explicitly, consistent
with its other profile/settings steps; a custom store needs its own native
scope/readback qualification.

### Installed ecosystem-catalog producer

The installed `ecosystem-catalog/SKILL.md`, `ecosystem-catalog/scripts/catalog.py`
and `ecosystem-catalog/data/registry.json`
is generated by a separate repository, not by `native-agent-stack` or QMD.
The [Mac owner's provenance handoff](https://github.com/seathatflowsinourveins/native-agent-stack/issues/384#issuecomment-5926166036)
and follow-up identify `seathatflowsinourveins/agent-ecosystem`, with that owner's
clean source revision `753777ac8163332a3570888680893821439ee4ab`. Preserve that
source-owner boundary; a registry `catalog_revision` is a content hash, not a
Git checkout revision.

That producer owns `catalog/registry.json`, host records in `manifest.json`,
runtime evidence in `acceptance.json`, and its generated skill data. Its
`agent-ecosystem/scripts/catalog_refresh.py --apply` is a broad managed-file install, not a
registry-only sync. It also preserves existing decisions/import pins, so a
metadata refresh alone does not retire VelaNext or turn older ai-memory and
SocratiCode selections into current Mac deployment facts. Do not hand-edit or
replace the generated consumer, invent selective flags, or copy around the
producer's receipt hashes.

The producer owner must reconcile its current source imports and retired-host
routing, preserve historical evidence and measured/blind promotion gates, then
use or add a tested receipt-aware selective synchronization path there. A
source render/check is separate from installing the resulting registry. No
selective installed-registry command is supplied by this repository.

For an adopted catalog QMD index, verify its selected collection roots point to
this source revision first. Follow [catalog retrieval](../docs/catalog-retrieval.md)
for a path-only relocation that preserves masks, contexts, models and unrelated
collections; `update` alone does not move an old root. Then:

```sh
qmd --index native-agent-stack-catalog update
qmd --index native-agent-stack-catalog status
qmd --index native-agent-stack-catalog embed   # only if this adopted index already carries vectors
```

A source/text/index refresh is not a runtime re-pin or promotion. Retain reported
host deployment facts separately from installer pins, historical experiments and
open measured/blind convergence gates. Do not run a broad bootstrap solely to
refresh instructions on a host whose verified production versions differ from
its older installation pins.

## Start a new repository

Added after `v2026.09.26.2`. Scaffold every new repository from this catalog, so it carries the
standing rule and the `sota-sources` check from its first commit
([new repositories](bootstrap.md#new-repositories)):

```sh
python3 tools/adoption/scaffold_repo.py --target <repo> --dry-run
python3 tools/adoption/scaffold_repo.py --target <repo>
```

A rerun changes nothing; a file edited since is skipped (exit 3) unless `--force <path>` names it,
with the path as the table prints it. To move an existing repository's workflow to a newer gate,
commit first, then name only the workflow:

```sh
python3 tools/adoption/scaffold_repo.py --target <repo> --dry-run --force .github/workflows/sota-sources.yml
python3 tools/adoption/scaffold_repo.py --target <repo> --force .github/workflows/sota-sources.yml
```

That replaces the workflow alone (no backup is kept) with one pinned to the current main commit.
Every other file that differs, such as a filled-in `AGENTS.md` or this host's `.codex/config.toml`,
is left as it is and reported `skipped`, so the run exits 3. A bare `--force`, or a path that is not
a scaffold file, is a usage error (exit 2) and writes nothing. The new pin takes effect once that
commit on GitHub carries `.github/workflows/sota-sources-gate.yml`.

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
