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

The profile sampler is the tracked `tools/sota-convergence/start_closure_sampler.py` (SHA256 `9b6ecd5317949b8a217668648d0649cdfa8101f80ab333c7776e7de5f00c7102`), using native [CPython 3.14.4 random.sample](https://github.com/python/cpython/blob/v3.14.4/Lib/random.py) and pinned `random.py` SHA256 `62dca8cdae7482513b99bb093ff038afd5131954e7eb78166d673a772cee871c`. Its START contract SHA256 is `744e1729ddd16a7d91378aebd35feea0acfba9932e49b831675fb1246a32ffde`. The privacy-safe R3 reseal is `tools/sota-convergence/sealed_r3_generator.py`, SHA256 `759facff52170f452290077b71d328f299b2c763df0358d126973c60886515c7`; historical source SHA256 `80e69ff94f97fffdf906583fa280f2a60a7487a54f0b58b05342264a5adf9627` remains in private custody. Only the two historical path defaults change, to repository siblings; seed, QUOTA and selection source remain byte-identical. The historical R2 contract `tools/sota-convergence/sealed_r3_stratum_contract.json` retains SHA256 `c12428493bd8aa76785a6b08f15b1e0e20b5cc169f2bcd6831c7d75ea84573fd`; the companion explicitly supplies the current protocol and START contract.

Before accepting the new R3 pin, run the original and reseal through the native selection helpers on identical passing-manifest, origin-map and head inputs. Record both commands, both packet hashes and per-stratum selected-row-ID/population-hash equality. A missing origin map keeps this comparison pending; do not substitute fixture results. After the comparison passes, pin the reseal in the companion and use the repository path through `--r3-generator`. The privacy gate remains unchanged. The co-op runs one shared draw after the passing landing-prep head is posted; retain its seed, population hash per stratum, sampler path@commit/hash and selected row IDs. Both families use that single packet and the same defect classes: profile reasons plus pin, locator, capture-hash, disposition and other. Packet creation runs no model read and establishes no zero-defect acceptance.

Keep the PR a draft while inputs or required checks are open. The explicit catalog and release cue controls landing and publication. After landing, attach the final asset and `SHA256SUMS` to its pinned release, verify remote bytes and the tag binding on main, and retain the receipt. A prospective tag or local archive does not substitute for that verification.

For the bounded START gate, apply the complete [start-closure/1 definition](decisions/2026-10-08-g5-compact-evidence.md). Keep original fragments byte-identical. Resolve eligible null pins from retained repository-file bytes through Git blob IDs and GitHub's cached tree/path-history interfaces: default head first, then at most 20 path-history commits, one cached recursive tree per repository and fewer than 1,000 observed GitHub calls per hour. Record resolved/no-body/no-match/not-a-repository-file counts and actual request usage. Preserve the ten original disagreement assertions and their evidence-backed resolution or visible PENDING state. Normalize transport placeholders only in derived inputs. Retain hash-pinned source, field, 368-star and two-document witnesses and distinct per-list counting units. List omissions with their specific disposition and G5-F1/G5-F2/G5-F3 follow-up IDs; undispositioned omissions still block.

At each of the nine source-defect append sites, default qualification keeps its original blocker. Under the explicit profile, an action row remains a blocker; a non-action row retains the exact class, bucket, count and settling measurement in `closure.residue`. The definition maps list scope to counted-inventory, foreign source subject to PENDING-PIN, skill source qualification to PENDING-PIN/PENDING-LOCATOR and G5-F2, original identity to literal origin-unresolved, unsupported JSON selection to PENDING-LOCATOR, and unbound fields to G5-F1. Residue reasons cannot accompany ADOPT-NOW or TRIAL. Byte integrity, archive confinement, duplicate keys, declared pin/source disagreements, schemas, action evidence and promoted mapping checks remain strict.

For the single direct massive-com/client-python TRIAL scope defect, retain a derived `scope_witness` on its declared occurrence. Verify line 683 against the pinned awesome-quant README bytes and computed section 675–760, plus the existing boundary and slot/field declarations and cached commit/tree/blob chain. A failure remains a blocker; a disposition change requires its separate owner decision. Original source bytes and original ledgers stay unchanged.

For G5-F3, declare the actual outside-union count and SHA256 of the sorted occurrence-ID list with `cc_disposition_id: "G5-F3"` and `follow_up_id: "G5-F3"`. Complete the union declaration or exclude each source with its reason later. Its 803 IDs include six references on five TRIAL rows; this is a global census omission. The face prints its count and hash. A duplicate, missing or stale declaration fails, and the default profile still blocks it.

These commands use the actual prepared full asset and its intended profile-specific manifest path. The default command retains the complete qualification contract; its returned failures remain evidence rather than being relabeled as a closure result.

```sh
python3 tools/sota-convergence/compact_manifest.py \
  --asset g5-landscape-evidence-2026-10-08.tar.zst \
  --manifest catalogs/landscape/grand-catalog-20261008.json \
  --write --profile start-closure/1
python3 tools/sota-convergence/compact_manifest.py \
  --asset g5-landscape-evidence-2026-10-08.tar.zst \
  --manifest catalogs/landscape/grand-catalog-20261008.json \
  --check --profile start-closure/1
python3 tools/sota-convergence/compact_manifest.py \
  --asset g5-landscape-evidence-2026-10-08.tar.zst \
  --manifest full-qualification.manifest.json --write
python3 tools/sota-convergence/compact_manifest.py \
  --asset g5-landscape-evidence-2026-10-08.tar.zst \
  --manifest full-qualification.manifest.json --check
```

The co-op's shared packet command uses the committed sampler source and exact frozen inputs. Replace the task variables with their actual paths, hashes and landing-prep head; use native Python 3.14.4:

```sh
python3 tools/sota-convergence/start_closure_sampler.py \
  --profile start-closure/1 \
  --manifest "$G5_MANIFEST" --manifest-sha256 "$G5_MANIFEST_SHA256" \
  --origin-map "$G5_ORIGIN_MAP" --origin-map-sha256 "$G5_ORIGIN_MAP_SHA256" \
  --protocol-sha256 "$G5_PROTOCOL_SHA256" \
  --r3-generator tools/sota-convergence/sealed_r3_generator.py \
  --head "$G5_HEAD" --output-root "$G5_PACKET_ROOT" --output "$G5_PACKET_NAME"
```

The face must identify `validation.profile` and every class/bucket count, including PENDING-PIN, PENDING-LOCATOR, counted-inventory, origin-unresolved and G5-F1/F2/F3. Test each row-level class against default blocking, action blocking, non-action counting and equality of face counts to per-row residue sums. Record separate unique-row, append-event, physical inventory, claim-ID and global mapping units; overlapping buckets are not added. Run module tests with a 600-second timeout. Register the two owned docs with the repository's `host_receipts.register_file` before `python3 scripts/validate.py`, and commit the shared registry last.

Post the actual result, preserving stdout/stderr and the failed attempts:

```text
## G5-CHECK rc=<n> profile=start-closure/1 asset=<sha256> rows=<n> action=<n> pinned=<n> pending_pin=<n> pending_locator=<n> counted_inventory=<n> origin_unresolved=<n> f1=<n> f2=<n> f3=<n> disagreements=<resolved>/10 lists=<n> blockers=<list or none>
## G5-CHECK-STDERR <actual stderr when rc is not 0; explicitly empty if zero bytes>
```

After a full-asset closure-profile check returns 0, derive the literal final ADOPT-NOW/TRIAL projection with each native row identity, exact pin, all primary locators and capture SHA256. Post its actual count/hash and compare that set with the earlier action packet before designated reads. Both designated families read that action census and every PENDING-CONFLICT row, including its original contradictory claims; conflicts are excluded from all sampled pools. Draw the other final disposition and PENDING-PIN/PENDING-LOCATOR buckets, including source-residue rows, with the companion profile and sealed R3 seed 202610081850. Preserve sample overlaps and code/test hashes for both readers; a wider held-source-claim crosswalk remains a follow-up. A defect requires correction and a new sealed draw, never repeated sampling for a favorable result. The exact result, class/bucket reasons, ten-disagreement outcomes, list counts, action projection and conflict census belong in the read packet. Both reads cover profile code/tests and all required census/sample rows; packet generation does not establish a passed read.

Only check 0 and both passing designated reads permit G5 MET under this profile, with G5-F1, G5-F2 and G5-F3 open on the readiness manifest. The designated pre-cue tool, required hosted CI, explicit owner cue and 5f landing remain separate required steps. Keep the PR draft until those conditions pass; never push to a cued or LANDING-READY PR. After landing and a release cue, publish and verify the hash-pinned asset and release-tag binding. The default full-profile target remains check 0 after deferred qualification is completed.
