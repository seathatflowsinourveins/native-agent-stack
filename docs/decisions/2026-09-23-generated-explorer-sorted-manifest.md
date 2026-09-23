# Decision: stop committing the generated explorer, and keep the evidence manifest sorted (2026-09-23)

**Decided by:** unit `generated-explorer-sorted-manifest`, an owned worktree
checkout of this repository, branch `claude/generated-explorer-sorted-manifest`,
originally started from base commit `a10de9f6a270f5d2802476f93f0c23ed4b43bfe0`
(`main` at the time) and rebased onto `168a3a8` (`main` after `#91`) during a
fix round that found the branch was one commit behind and conflicted with
`#91`'s changes to this same scope; see "Fix round" below. Approved by the
coordinating session `agent-lab-e9` on the evidence below.

**Scope:** `docs/ecosystem/index.html` (the built public explorer) and
`manifests/evidence.json`'s `files[]` array. No product application code;
this is repository-maintenance/CI scope only.

## Decision

### 1. `docs/ecosystem/index.html` is generated, not committed

- `git rm --cached docs/ecosystem/index.html`, added to `.gitignore`, and its
  entry removed from `manifests/evidence.json` `files[]`.
- `scripts/build_ecosystem.py --write` is unchanged in effect: it still
  rebuilds `docs/ecosystem/index.html` locally (now an untracked, gitignored
  file).
- `scripts/build_ecosystem.py --check` no longer reads or compares against
  any committed/on-disk file (there isn't one to compare against). It now
  builds the explorer twice, each time into its own temporary directory,
  requires the two builds to be byte-identical (a determinism check), and
  prints a JSON report carrying two digests: `input_sha256` (sha256 over the
  canonical-JSON-encoded, path-sorted list of every input path this build
  actually read, with each input's own sha256/bytes/scope -- the same
  `inputs` array already embedded in the built page) and `output_sha256`
  (sha256 of the built HTML bytes). Every existing input validation the
  builder performs (schema versions, duplicate/unknown identities, path
  confinement, symlink rejection, safe-URL filtering, etc.) is unchanged;
  only the committed-file comparison was removed and replaced by the
  two-directory determinism check.
- `publish-catalog.yml` now has a "Build the public explorer" step
  (`python3 scripts/build_ecosystem.py --write`, run against the same
  validated `$GITHUB_SHA` checkout used for the source archive/SBOM) and
  publishes the result as its own artifact
  (`native-agent-stack-<sha>-explorer`, `*.explorer.html`), attested with the
  same pinned `actions/attest@1e69f48...` step already used for the archive
  and SBOM (default build-provenance predicate, `push-to-registry: false`,
  `create-storage-record: false`), with the same uploaded-digest-matches-
  attested-file check the archive and SBOM steps already do. `permissions`
  is unchanged (`contents: read` at workflow level;
  `id-token: write`/`attestations: write` already present at job level for
  the existing attestations); no new secret was added; every action
  reference stays pinned to a full commit SHA. `zizmor --offline` on the
  changed workflow: "No findings to report" (2 suppressed, pre-existing).
- Every prose reference to `docs/ecosystem/index.html`/`ecosystem/index.html`
  across the repository (`git grep`, ~40 files) was checked. Reader-facing
  links/instructions (`AGENTS.md`, `adoption/README.md`,
  `adoption/lifecycle.md`, `catalogs/README.md`,
  `catalogs/foundation/README.md`, `catalogs/landscape/README.md`,
  `catalogs/us-equities/README.md`, and the `docs/*.md` guides that link the
  explorer) were updated to say how to get the file now: build it locally
  with `python3 scripts/build_ecosystem.py --write`, or download it from the
  `publish-catalog.yml` release artifact. `.gitleaks.toml`'s header comment
  and `docs/github-automation.md`'s "Secret-scan coverage boundary" section
  were updated: the `--max-target-megabytes 2` skip is no longer a coverage
  hole for the current working tree or for any future commit (nothing
  generated is committed any more); it remains a real, separately recorded
  coverage hole for the repository's *existing* git history, since every
  commit made before this change still carries the old committed
  `docs/ecosystem/index.html` (up to ~13 MB) inside git's object history,
  and a full `gitleaks git .` history scan still skips those old blobs at
  that size. Dated historical records that quote the file's committed state
  at a point in time (`docs/tasks/2026-09-22-*.md`,
  `docs/decisions/2026-09-22-actions-hardening-fix-round.md`,
  `evidence/receipts/*.json`, `evidence/artifacts/*/*.json`,
  `catalogs/landscape/gap-crosswalk-92bb279.json`,
  `docs/gap-crosswalk-92bb279.md`) were left untouched: they are point-in-time
  evidence of what was true when they were written, not live instructions,
  and editing them would misrepresent history. `manifests/evidence.json`
  (data, not prose) and `tools/sota-convergence/blind_checkout.py` /
  `record_verdicts.py` (domain logic that names the path defensively/for
  citation-exclusion, correct whether or not the file is currently committed)
  were also left as-is. `tests/test_ecosystem_manifest.py`,
  `tests/test_blind_checkout.py` and `tests/test_record_verdicts.py` already
  build the explorer only into synthetic per-test temporary directories
  (`tempfile.TemporaryDirectory()` fixtures with their own `--root`); none of
  them read the real repository's committed file, so none needed changing
  for that reason. `tests/test_ecosystem_manifest.py`'s `--check` tests
  *did* need updating for the new `--check` semantics (see Evidence below).
- `docs/ecosystem/claude-repository-evidence.html` (496 KB) and
  `docs/ecosystem/claude-upstream-checks.html` (60 KB) were checked for the
  same problem and do **not** have it: each has exactly one commit in
  `git log`, neither is rebuilt by `scripts/build_ecosystem.py` (or any other
  script found by `git grep`), and both are well under the 2 MB
  `--max-target-megabytes` threshold. They stay committed; this decision
  changes only `docs/ecosystem/index.html`.

### 2. `manifests/evidence.json` `files[]` stays sorted by path

- New `scripts/evidence_manifest.py --write|--check`: `--write` sorts
  `files[]` by `path` (stable sort, every entry's own fields unchanged,
  every other top-level key's order unchanged) and rewrites the file in its
  existing exact serialization (`json.dumps(..., indent=2,
  ensure_ascii=True)` + trailing newline -- verified byte-identical to the
  file's current format before any content change). `--check` exits 1 (and
  names the normalizer command) if `files[]` is out of order or has a
  duplicate path.
- `scripts/validate.py`'s `validate()` now also requires `files[]` to be
  strictly sorted by path with no duplicates, with an error message naming
  `python3 scripts/evidence_manifest.py --write` as the fix.
- `scripts/host_receipts.py`'s `register_file()` (used by both `record` and
  `review`) now inserts a new path at its sorted position with
  `bisect.bisect_left` instead of always appending, so parallel
  `record`/`review` calls land as conflict-friendly inserts rather than
  always colliding on the same tail of the array. Updating an existing path
  still updates in place at its current position. New tests
  (`tests/test_host_receipts.py::RegisterFileSortTests`) cover sorted
  insertion, in-place update, and insertion-order independence.
- The normalizer was run once on the current manifest (after
  `tools/rehash_evidence.py` recomputed the hashes of every file changed by
  this unit, including the removed `docs/ecosystem/index.html` entry).

## Evidence

- Every doc change previously rewrote the full 12+ MB
  `docs/ecosystem/index.html` in the same commit, so parallel PRs touching
  any of its ~40 input files conflicted on that one file; `#91` needed three
  main re-merges in an hour for exactly this reason.
- The committed file's content made every PR's gitleaks *history* scan
  report roughly 2,322 pre-existing SHA-like strings as findings; CI avoided
  that only via the `--max-target-megabytes 2` size skip, which
  `docs/github-automation.md`'s prior "Secret-scan coverage boundary" note
  already recorded as an incomplete-coverage hole for exactly this file.
- GitHub Pages is not enabled for this repository (`GET
  repos/seathatflowsinourveins/native-agent-stack/pages` returns 404), so no
  live site depended on the committed file.
- `python3 scripts/build_ecosystem.py --check` builds once in-process and once in a
  separate interpreter with a different `PYTHONHASHSEED`, and requires identical bytes.
  Run three times on the final branch head (including once with `PYTHONHASHSEED=7`),
  it reported the same `output_sha256` each time (`86cb0f85d7c96a3da51fb22cb63ee897bbceb0b9b346e5bb86789e098664c615`, 12,929,289
  bytes; `input_sha256` `30bfe38d7eb2f3ebc2d8a1da8fe3b31ec3d797a32103a49ba418f2a34efcc5d2`). The digest changes whenever an input
  document changes, which is expected: it describes this tree, not a pinned value.
- `tests/test_ecosystem_manifest.py` (46 tests, `python3 -m unittest`) and
  `tests/test_host_receipts.py::RegisterFileSortTests` pass locally against
  this change.

## Alternatives considered

- **Sharded manifests** (split `manifests/evidence.json` into several
  smaller files, e.g. per date or per family) would reduce single-file
  contention further, but changes every consumer (`scripts/validate.py`,
  `scripts/host_receipts.py`, `scripts/build_ecosystem.py`, and every script
  that loads the evidence receipts) and every existing receipt reference by
  path. Rejected for now: sorting already removes the specific
  always-append-at-the-tail collision pattern seen in practice, at far less
  churn; sharding is a larger, separate migration to revisit if sorted
  inserts still collide often in measured PR history.
- **Commit the explorer only on release tags** (keep it tracked, but only
  regenerate/commit it as part of a tag-triggered release commit) would
  still leave every day-to-day PR paying the diff/gitleaks cost on `main`
  between tags, and still requires a bot commit or manual regeneration step
  on tag creation. Rejected: it keeps most of the problem (main-branch churn
  and full-history gitleaks exposure) while adding process complexity;
  publishing a build artifact from CI (what this decision does) gets a
  downloadable, attested explorer without ever touching `main`, at the cost
  of the workflow artifact's own 7-day retention and its
  `workflow_dispatch`/`v*`-tag-only trigger (see "Fix round" below); that
  cost applies equally to the rejected alternative, since it too would only
  regenerate the file at tag time.
- **GitHub merge queue** -- **REJECTED**: GitHub merge queues are only
  available for organization-owned repositories (public repositories owned
  by an organization, or private repositories on GitHub Enterprise Cloud).
  `gh api users/seathatflowsinourveins` returns `"type": "User"`: this
  repository is owned by a personal account, not an organization, so a merge
  queue is not an available feature here regardless of its merits for the
  underlying conflict problem.

## Fix round (2026-09-22)

An independent review of this branch (base `a10de9f`) found it one commit
behind `main` (then `168a3a8`, `#91`) and conflicting with `#91`'s changes to
both files this branch rewrites, plus three other major findings. All four
were fixed on this branch before commit:

1. **Stale base / merge conflict with `#91`.** `#91` (`Add the pre-registered
   leverage schedule v1`) modified `docs/ecosystem/index.html` (this branch
   deletes it) and added 5 new `manifests/evidence.json` entries plus
   rehashed 18 existing ones (this branch fully rewrites `files[]` to sort
   it). The branch was rebased onto `168a3a8`: the `docs/ecosystem/index.html`
   modify/delete conflict resolved to the deletion (this decision's whole
   point), and the `manifests/evidence.json` conflict resolved to `#91`'s
   current entries (including its 5 new leverage entries) minus the removed
   `docs/ecosystem/index.html` entry, then rehashed with
   `tools/rehash_evidence.py` and re-sorted with
   `scripts/evidence_manifest.py --write`. The base commit note above and
   `manifests/evidence.json` itself now reflect `168a3a8`, not the stale
   `a10de9f`.
2. **The published explorer bypassed the private-content scan.**
   `scripts/validate.py`'s `scan_publication()` only ever walks git-tracked
   and git-listed-untracked paths (`Validator.publication_paths()`); a
   generated, gitignored artifact built fresh in `publish-catalog.yml` right
   before it is attested was invisible to it, reopening exactly the
   `docs/ecosystem/index.html` private-path finding this repository already
   hit once (`evidence/artifacts/foundation-convergence-20260921/validation-attempts.json`).
   Added `scripts/validate.py --scan-file PATH` (repeatable), a standalone
   mode that runs the same `PRIVATE_CONTENT` patterns directly against a
   given file's bytes, independent of `--root`'s git-based enumeration.
   `publish-catalog.yml` now runs `python3 scripts/validate.py --scan-file
   "$explorer"` on the freshly built explorer immediately after the "Build
   the public explorer" step and before the "Attest the public explorer"
   step.
3. **The explorer's own guide (`docs/ecosystem/README.md`) still described
   the pre-decision committed-file model** and was never updated by the
   original change, despite this record's earlier claim that every
   reader-facing reference was updated. Its dead `index.html` link, "GitHub
   shows HTML source; download the file" instruction, "stale generated bytes
   fail the build" description and "update the existing publication hash
   manifest after regeneration" instructions were all rewritten to match the
   current build-locally-or-download-the-workflow-artifact model and the
   actual two-temporary-directory `--check` semantics.
   `adoption/manifest.json`'s `sources.ecosystem_explorer` pointer keeps its
   existing plain-string-path shape (every `sources` entry is a bare path
   string elsewhere; adding an adjacent non-path note key would have broken
   that invariant, which `tests/test_adoption_contract.py` enforces by
   iterating every `sources` value as a file reference) -- its value
   (`docs/ecosystem/index.html`) is unchanged and still correct, since that
   is still exactly where `--write` places the file, just no longer
   committed there. `tests/test_adoption_contract.py`'s
   `test_continuation_references_resolve_without_copying_gate_states` (which
   asserts every `sources` reference is a real file on disk, and would now
   fail on a clean checkout that never ran `--write`) now explicitly skips
   only the `ecosystem_explorer` key with a comment naming why, and pins its
   exact expected path value so the exclusion cannot silently hide a
   different, genuinely broken reference.
4. **The workflow artifact is not a persistent release, and every
   reader-facing reference calling it a "release artifact" overstated that.**
   `publish-catalog.yml`'s explorer artifact uses `actions/upload-artifact`
   with `retention-days: 7` and only runs on `workflow_dispatch` or a `v*`
   tag push (`on: workflow_dispatch / push: tags: ['v*']`), not on every
   commit; there is no GitHub Release upload step. Every occurrence of
   "`publish-catalog.yml` release artifact" across `AGENTS.md`,
   `adoption/README.md`, `adoption/lifecycle.md`, the `catalogs/*/README.md`
   guides and the other `docs/*.md` guides was reworded to name the actual
   retention window and trigger scope
   (`` `publish-catalog.yml` workflow artifact (7-day retention,
   `workflow_dispatch`/`v*`-tag runs only) ``). No new persistence mechanism
   (a GitHub Release, longer retention, or a scheduled re-publish) was added
   in this fix round -- that would be new infrastructure scope beyond
   correcting the documentation to match the workflow's actual, already-
   approved behavior. A reader who needs the explorer more than 7 days after
   the last `workflow_dispatch`/tag run, or between such runs, must rebuild
   it locally; this limitation is carried forward rather than hidden.

## Overturn conditions

- The repository moves to an organization-owned account: reconsider a
  GitHub merge queue as a complementary (not alternative) fix for
  general multi-PR conflict churn, not specific to the explorer.
- GitHub Pages is enabled for this repository, or another consumer starts
  depending on a *committed* `docs/ecosystem/index.html` at a stable path
  (rather than a locally-built or release-downloaded copy): reconsider
  committing a built artifact again, scoped to that consumer's actual
  requirement.
- The build is shown to be non-deterministic (the two-temporary-directory
  `--check` in `scripts/build_ecosystem.py` starts failing on an unmodified
  source tree, or a hosted `publish-catalog.yml` run produces a different
  digest than a local build of the same commit): treat that as a bug in the
  builder to fix directly, and re-examine whether `--check`'s determinism
  guarantee still holds before relying on the published artifact's digest
  as a proxy for "what `--write` would produce here."
- A reader needs the explorer between `workflow_dispatch`/`v*`-tag runs, or
  more than 7 days after the last one, and rebuilding locally with
  `python3 scripts/build_ecosystem.py --write` is not an acceptable
  substitute for their use case: reconsider a persistence mechanism (a
  GitHub Release upload, longer `retention-days`, or a scheduled republish)
  rather than only documenting the current 7-day/trigger-scoped window.
