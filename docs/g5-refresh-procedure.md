# Refresh the landscape and its release evidence

The Git record contains compact decisions, the slot index, generator and verification receipts. Discovery originals, list mining and source captures are retained in a dated release asset. The manifest records its SHA256 and release tag. An unpublished local package is marked prepared; a future PC uses it after the published tag and asset binding are verified.

The basis is GitHub's [large-file contract](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github), [release-assets contract](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#storage-and-bandwidth-quotas), the native [landscape sweep](../tools/sota-convergence/landscape-sweep/README.md), [compact row schema](../tools/sota-convergence/schemas/compact-decision.json) and [coverage schema](../tools/sota-convergence/schemas/compact-coverage.json). Source pins, dates and native acceptance remain separate facts.

Freeze the next run's repository revision, exact committed selectors, platform profile, seed hints and budgets before discovery. This snapshot has 20 foundation, 12 trading and 13 skills lifecycle selectors; enumerate their IDs rather than assuming those counts next time. Use the native repository discovery schema for repository fields and native skills schema for skills fields. A locator bundle binds per-field originals; it is not a single-field discovery or completed native workflow.

Keep seeds, current public stars, every mined-list occurrence and live discovery beyond them separate. Each source population names its repository or URL, pin, file, content hash, language/section, parser revision and entry-kind grammar. Preserve occurrence IDs, original pointers or physical lines, ordinals and slots. Different sections and parser units remain separate populations. Repository, query, referral and resource totals never silently become a list denominator. Every omitted or inaccessible population is named and keeps coverage incomplete.

Research uses maintained releases, source and official documentation at declared versions. Retain failed queries and accesses as failures. A no-results exception without an observed successful HTTP response does not establish candidate absence. A source-entry pin does not assert a candidate's implementation version. Installation uses a vendor recipe, native check, inverse and verified routing in both clients only for an accepted ADOPT-NOW row.

Each compact row names the entry, slot and literal role qualification; disposition and evidence class; source pin and primary locators; capture hash and safe archive member; lane and refresh date. REJECT names searched surfaces. PENDING retains competing source claims, a conservative provisional state excluding ADOPT-NOW, one settling measurement and an owner. Different scopes split; repeated same-class claims keep every locator; same-slot contradictions require convergent pinned primary evidence.

Prepare a private stage containing `compact/rows.json`, `compact/coverage.json`, original public captures and custody receipts. Original inventory, population census and source bindings are hash-bound archive witnesses. Raw statuses, conversations, personal host paths, credentials and active client configuration do not belong in a public asset. Sanitized publication bytes keep their own hashes. Include internal `SHA256SUMS` for every selected member.

GNU tar and vendor zstd create the asset. Use a sorted NUL-delimited list of confined relative regular-file members, stored outside the archive. Replace this example's date and private variables for a new refresh:

```sh
tar --sort=name --format=posix --mtime=@0 --owner=0 --group=0 --numeric-owner \
  --pax-option=delete=atime,delete=ctime \
  --use-compress-program='zstd --single-thread -3 -q' --null \
  -C "$STAGE" -T "$MEMBER_FILES" \
  -cf "$ASSET_DIR/g5-landscape-evidence-2026-10-08.tar.zst"
zstd --test --quiet "$ASSET_DIR/g5-landscape-evidence-2026-10-08.tar.zst"
sha256sum "$ASSET_DIR/g5-landscape-evidence-2026-10-08.tar.zst"
```

Snapshot packaging versions are GNU tar 1.35 and zstd 1.5.7. Verify installed versions and vendor interfaces on a future machine. Compression integrity verifies the container, not evidence truth or completeness.

The generator rebuilds from the asset; producer paths are optional equality witnesses. Mechanical checks require the full frozen census, pinned locators, capture hashes, unique entry/slot/qualification keys and resolved original occurrence pointers. An incomplete union, unknown pin or unmatched occurrence keeps the result blocked.

```sh
python3 tools/sota-convergence/compact_manifest.py \
  --asset "$ASSET_DIR/g5-landscape-evidence-2026-10-08.tar.zst" \
  --release-tag v2026.10.08 \
  --manifest catalogs/landscape/grand-catalog-20261008.json --write
python3 tools/sota-convergence/compact_manifest.py \
  --asset "$ASSET_DIR/g5-landscape-evidence-2026-10-08.tar.zst" \
  --release-tag v2026.10.08 \
  --manifest catalogs/landscape/grand-catalog-20261008.json --check
```

Run native catalog and manifest checks. Register owned evidence with `host_receipts.register_file`, commit the shared registry last and reconcile it from current main. Preserve historical saturation entries unless an actual native sweep satisfies the converter/result contract; a source-only release cannot manufacture a completed sweep.

Both designated families review every ADOPT-NOW and TRIAL row against primary sources. Other rows follow the [stratified plan](decisions/2026-10-08-g5-compact-evidence.md): 59 random rows per fragment and disposition, or census for smaller strata, with a frozen seed, population and sampler version. Retain defects, root-cause corrections, failed attempts and revised seeds. State only the verification claim supported by actual results.

Keep the PR a draft while inputs or required checks are open. The explicit catalog and release cue controls landing and publication. After landing, attach the final asset and `SHA256SUMS` to its pinned release, verify remote bytes and the tag binding on main, and retain the receipt. A prospective tag or local archive does not substitute for that verification.
