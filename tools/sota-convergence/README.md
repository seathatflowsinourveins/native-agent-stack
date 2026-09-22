# SOTA convergence tools

Reproducible, CLI-driven steps for the dated SOTA repository convergence
published at [`catalogs/sota-convergence/`](../../catalogs/sota-convergence/README.md).
The 2026-09-22 wave was produced by two ad hoc, host-path-hardcoded scripts;
these four steps replace them with arguments, resumability and a checked-in
default reconciliation file. No step here calls a model.

## The four steps

1. **`extract_layers.py`** -- deterministic, no-network. Reads
   `catalogs/foundation/{manifest,decisions}.json`, `manifests/stack.json` and
   the four `catalogs/us-equities/{foundation-memory,agents-operations,
   data-research,engines-strategies}.json` layer files, plus `models.json`,
   `star-audit.json` and `coverage.json`. Writes `foundation-layers.json`,
   `trading-catalog.json`, `trading-by-layer.json` (consolidated onto the
   12-layer taxonomy copied live from
   `catalogs/sota-convergence/manifest-20260922.json#/taxonomy`),
   `star-candidates.json` and `models.json` into `--out`.

   ```sh
   python3 tools/sota-convergence/extract_layers.py --repo-root . --out /path/to/work-dir
   ```

2. **`github_freshness.py`** -- a real network step (authenticated `gh api`
   calls; `gh auth status` must already pass). Reads the repository URLs out
   of the three working files above and writes `github-freshness.json` with
   stars, `pushed_at`, latest release/tag, head commit, license, archived and
   rename status per repository, plus every alias URL seen for that
   repository's normalized GitHub slug (`"aliases"` -- a `/releases/tag/vX`
   or `/tree/...` catalog URL and the canonical form both resolve to the same
   record; `build_manifest.py` looks records up by slug, not by exact URL).
   Resumable: a repository already present in `--out` *without* an `"error"`
   or `"partial_errors"` field is skipped unless `--refresh`. A repository
   whose record carries `"error"` (the primary `repos/{slug}` call itself
   timed out or failed) stays pending and is retried on the next run. A
   repository whose primary call succeeded but a releases/tags/commit
   sub-request failed with something other than an ordinary 404 "no
   releases" (a timeout, 429, or 5xx) keeps that failure in
   `"partial_errors"`, is counted in the document's top-level
   `partial_errors`, and is also retried on the next run -- it is not
   silently treated as done just because the primary call succeeded. One
   `gh` call raising (a timeout, missing binary, etc.) never aborts the batch
   -- `gh_api` catches it and records `{"error": "..."}` for that repository
   only -- and progress is checkpointed to `--out` every 25 fetched
   repositories and again in a `finally` block, so a long run interrupted
   partway still leaves
   what it fetched on disk. `--max-repos` bounds a trial run.

   ```sh
   python3 tools/sota-convergence/github_freshness.py --work-dir /path/to/work-dir --workers 6
   ```

3. **Review lanes** (between steps 2 and 3) -- run as the agent-lab saved
   workflow named `sota-convergence` (args: `{work_dir}`). It reads the
   working files and the freshness snapshot from `work_dir` and writes a
   `lanes.json` there with the schema `build_manifest.py` expects:
   `{lanes: [{lane, result: {layers: [...], calls, limits}, proposals: [...]}],
   critic}`. Each lane proposes labels (`confirmed_default`,
   `not_adopted`, `keep_but_compare`, `targeted_candidate`, ...); every
   proposal is then adversarially verified by two refuters recorded in
   `proposals[].votes[].refuted`.

4. **`build_manifest.py`** -- no network. Recomputes the baseline (pins vs.
   upstream) directly from `foundation-layers.json` + `trading-by-layer.json`
   + `github-freshness.json`, then merges in `lanes.json` and a
   reconciliations file (default:
   [`reconciliations-20260922.json`](reconciliations-20260922.json), the
   three reconciliations already published in the 2026-09-22 manifest).
   Output has the exact key layout of `manifest-20260922.json`: `schema_version,
   id, checked_at, scope, method, taxonomy, foundation, trading, critic,
   lane_calls, lane_limits, reconciliations, counts`. Refuses to write if a
   host path or a known secret-prefix marker survives sanitization.

   ```sh
   python3 tools/sota-convergence/build_manifest.py \
     --work-dir /path/to/work-dir --lanes /path/to/work-dir/lanes.json \
     --out /path/to/manifest.json --checked-at YYYY-MM-DD --id sota-convergence-YYYYMMDD
   ```

## Rules encoded in `build_manifest.py`

- **Pin-vs-upstream** (`classify_pin`): a component/entry only counts as
  `pin_behind_upstream` when its repository is a GitHub URL, its pin is not a
  `.devN` commit-tracking pin (e.g. `2.0.0.dev0 @ <commit>`), its pin is not
  an OS-distribution package pin, and its parsed leading version is lower
  than GitHub's latest release/tag. Non-GitHub repositories and `.devN` pins
  are excluded from the comparison rather than counted either way. An
  OS-package pin is excluded even when the project's own `repository` field
  is a real GitHub URL (e.g. `systemd/systemd`): a distro package string like
  `255.4-1ubuntu8.17` is not comparable to an upstream tag. Detection is
  twofold -- an `-NubuntuM` / `-Ndeb` / `+debN` suffix on the pin itself, or
  the component/entry id being in `--os-package-ids` (default: `systemd`),
  which also excludes a distro pin that happens not to match the suffix
  pattern. A version merely *annotated* with a commit fingerprint
  (`0.25.0 (<commit>)`) is still compared normally.
- **Slug-normalized freshness lookup** (`github_repo_slug`,
  `compute_upstream`, `repository_known`): a component/entry's `repository`
  field is looked up in the freshness snapshot first by exact URL, then by
  normalized GitHub slug (owner/name, lower-cased, `.git`/release-tag/tree
  suffixes and a trailing slash stripped) -- so a catalog URL that happens to
  use a `/releases/tag/vX` or `/tree/...` form still resolves to the same
  freshness record as the canonical URL, instead of silently losing upstream
  metadata on an exact-string miss.
- **Selected trading baseline**: only catalog `decision` values `default` and
  `conditional` are promoted into a manifest row; `alternative`/`watch`/
  `excluded` entries stay discoverable in `trading-by-layer.json` and can
  only reach the manifest through the lane candidate/alternative mechanism.
- **Disposition never promotes** (`disposition`): a lane proposes a label,
  two refuters try to break it. A surviving `not_adopted` stays
  `not_adopted_confirmed`; nothing is upgraded by surviving review. The same
  explicit-`False`-vs-`None` handling applies to a `selected` entry's own
  status verdict (`merge_lanes`): a refuted (`survives: False`) proposal is
  confirmed as unchanged, but an unknown verdict (`survives: None`, e.g. no
  refuter voted) stays `<status>_unverified` and is never promoted to
  `confirmed_*` -- `not verdict["survives"]` alone would treat `None` the
  same as `False`, which is the review finding this fixed.
- **Sanitize-then-refuse**: `sanitize_value()` walks the manifest's decoded
  dict/list/str values and redacts Linux/macOS/Windows host-path fragments
  *before* `json.dumps` (never the already-serialized text -- see its
  docstring for why that can produce invalid JSON on a quoted embedded path);
  the serialized result is then round-tripped through `json.loads` to prove
  it is still valid JSON, and `assert_no_leak()` raises if a home path or the
  broker key prefix survived. `build_manifest.py` never writes on either
  failure.
- **Deterministic ordering**: per-layer `components`/`entries` and
  `candidates` are sorted by `(decision-rank, id)` (`row_item_sort_key`) and
  `(disposition-rank, repository)` (`candidate_sort_key`) respectively before
  being written, not left in the source JSON's or the lane's insertion order.
  Rebuilding the manifest from the same working files and `lanes.json`
  content -- even if a lane lists its candidates or a catalog lists its
  entries in a different order -- produces byte-identical row ordering, so
  reruns diff cleanly.

## Evidence classes

Keep these separate when reading or citing the output. `review_status` and
`evidence_level` are two independent axes: `review_status` is whether a
*selection or pin change* survived adversarial review; `evidence_level` is
what was actually *executed*. **`review_status` never establishes native
execution**, regardless of its prefix -- a component/entry can be
`confirmed_default` and `source_review` at the same time (the published
2026-09-22 manifest's `inspect-ai` and `quantstats` rows both are; see
`catalogs/sota-convergence/README.md`'s "Method and limits").

- **Metadata** (`github-freshness.json`, `upstream` fields in the manifest) --
  GitHub REST facts (stars, pushed_at, release tags). Not a behavioral test.
- **`review_status`** (selection/pin confirmation, not execution) --
  `lanes.json` `selected`/`new_candidates` verdicts. A `confirmed_*` prefix
  means the *proposed change* survived two adversarial refuters; any other
  value (including `<status>_unverified`, for an unknown `survives: null`
  verdict) means a lane read documentation/READMEs and reasoned about fit,
  or that no verdict exists yet. Nothing about `review_status` says whether
  the tool itself was installed, built or run.
- **`evidence_level`** (execution classification, from the catalog card) --
  `source_review` means nothing was installed, built or run; `native_proven`
  (or anything cited to a receipt under `evidence/` or
  `manifests/evidence.json`) means an actual reproducible execution exists,
  separate from this manifest. `build_manifest.py` carries this field into a
  manifest trading entry row whenever the source
  `catalogs/us-equities/*.json` card sets it (`extract_layers.py` already
  reads it verbatim); it is absent from foundation components today.

Inclusion in any working file or the manifest is never installation, E2E
acceptance, or superiority.

## Regression note

`build_manifest.py` run against the real 2026-09-22 working files reproduces
`catalogs/sota-convergence/manifest-20260922.json` exactly on the
`(layer, repository, review_status)` identity set for both foundation and
trading, on `candidates_total`/`candidates_by_disposition`,
`pins_behind_upstream_unique_components` and `components_confirmed`. Rerun
2026-09-22 against the host's private state directory for the 2026-09-22 wave
(read-only inputs): `foundation_layers=16, trading_layers=12,
components_confirmed=106, candidates_total=34,
pins_behind_upstream_unique_components=15,
candidates_by_disposition={not_adopted_confirmed:10,
refuted_targeted_candidate:6, refuted_keep_but_compare:11,
refuted_not_adopted:6, targeted_candidate:1}` -- all match the published
manifest's `counts` exactly.

The raw (non-deduplicated, sums every layer occurrence) `pins_behind_upstream`
count differs by a small, understood margin -- 26 here vs. 33 published, a
gap of exactly 7 occurrences across four ids that the published manifest's
own prose already flags as false positives, not four newly-behind repos:
`serena` and `alphalens-reloaded` (`.devN` GitHub-metadata pins the published
prose says are "ahead of GitHub's latest release" but the original,
unrecovered baseline generator nonetheless flagged `True` -- `classify_pin`'s
`.devN` rule fixes exactly that inconsistency, per its own worked example);
`systemd` (an Ubuntu-package pin on a real GitHub repository, flagged
`pin_behind_upstream: true` three times across `workers`,
`scheduling-supervision` and `recovery-portability` in the published data
even though the published manifest's own review note already calls the
behind-flag "a category error" -- this is the bug `classify_pin`'s
OS-package-pin exclusion fixes); and `modal` (its freshness in the original
run came from a live PyPI read, noted in the trading lane's own limitations
as one of "six PyPI JSON reads" outside the `gh api`/`web_fetch`/`web_search`
budget -- this tool's freshness step is GitHub-only, so `modal`'s
pin-vs-upstream comparison is not reproducible without adding a PyPI fetch).
None of these four changes a selection, candidate disposition, or count that
a decision was made from -- and `pins_behind_upstream_unique_components`
(15) already excludes all four in both the published and the rerun manifest.
