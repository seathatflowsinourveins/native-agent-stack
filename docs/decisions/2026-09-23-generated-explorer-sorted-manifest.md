# Decision: stop committing the generated explorer, and keep the evidence manifest sorted (2026-09-23)

**Decided by:** unit `generated-explorer-sorted-manifest`, an owned worktree
checkout of this repository, branch `claude/generated-explorer-sorted-manifest`,
base commit `a10de9f6a270f5d2802476f93f0c23ed4b43bfe0` (`main`). Approved by the
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
- `rtk proxy python3 scripts/build_ecosystem.py --check` run twice against
  the real repository state after this change reported the identical
  `output_sha256` both times (`9d9981d7d2c967a2b0218970b29467fab06fc8e37bc6bf279e44c876dc71dcf6`,
  12,926,840 bytes) -- the explorer build is deterministic from this
  source tree.
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
  downloadable, attested explorer without ever touching `main`.
- **GitHub merge queue** -- **REJECTED**: GitHub merge queues are only
  available for organization-owned repositories (public repositories owned
  by an organization, or private repositories on GitHub Enterprise Cloud).
  `gh api users/seathatflowsinourveins` returns `"type": "User"`: this
  repository is owned by a personal account, not an organization, so a merge
  queue is not an available feature here regardless of its merits for the
  underlying conflict problem.

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
