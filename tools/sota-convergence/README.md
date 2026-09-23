# SOTA convergence tools

Reproducible, CLI-driven steps for the dated SOTA repository convergence
published at [`catalogs/sota-convergence/`](../../catalogs/sota-convergence/README.md).
The 2026-09-22 wave was produced by two ad hoc, host-path-hardcoded scripts;
these four steps replace them with arguments, resumability and a checked-in
default reconciliation file. No step here calls a model.

## The five steps

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
   Output has the key layout of `manifest-20260922.json`: `schema_version,
   id, checked_at, scope, method, taxonomy, foundation, trading,
   lane_groupings, citation_review, critic, lane_calls, lane_limits,
   reconciliations, counts`, plus `unmatched_lane_items` after
   `lane_groupings`. `lane_groupings` carries, verbatim, any
   review-lane layer id outside the foundation/taxonomy baseline (e.g. a
   "beyond" lane's own grouping like `awesome-list-convergence`) that would
   otherwise not match `trading[].layer`'s exact-taxonomy contract.
   `unmatched_lane_items` publishes every lane `selected[]` item at a
   foundation/trading layer that no card row took (`reason`
   `no_card_with_repository_in_layer` or `catalog_id_names_no_card`; with
   `lane, layer, repository, catalog_id, status, survives, verified,
   evidence, note, lane_item`), counted in `counts.unmatched_lane_items[_by_lane]`;
   such items were previously dropped without trace.
   `citation_review` (optional `--citation-review PATH`) overlays an
   independent citation review's findings onto the rows they name -- data
   only, see "Citation-review overlay, data only" below; always present,
   `{"general": []}` when the flag is not given. Refuses to write if a host
   path, a bare session UUID, or a known secret-prefix marker survives
   sanitization.

   ```sh
   python3 tools/sota-convergence/build_manifest.py \
     --work-dir /path/to/work-dir --lanes /path/to/work-dir/lanes.json \
     [--citation-review /path/to/citation-review.json] \
     --out /path/to/manifest.json --checked-at YYYY-MM-DD --id sota-convergence-YYYYMMDD
   ```

5. **`build_verdicts.py`** -- no network. A separate, independent join from the
   four steps above: it does not read `foundation-layers.json` or
   `trading-by-layer.json`. It reads the **landscape ledger**
   (`catalogs/landscape/{foundation,us-equities}.json`, layer-verdict schema
   v2 -- see [`catalogs/landscape/README.md`](../../catalogs/landscape/README.md#layer-verdict-schema-v2)),
   the dated sota manifest (`catalogs/sota-convergence/manifest-20260922.json`,
   for each layer's `components[]`/`entries[]` `id`/`pin`/`upstream`/
   `review_status`/`pin_behind_upstream`) and `adoption/manifest.json`'s
   `recipe_map`, and writes the join deterministically
   (`json.dumps(..., sort_keys=True)`, trailing newline) to
   `catalogs/sota-convergence/layer-verdicts-20260922.json`. It also replaces
   the generated table between `<!-- verdicts:begin -->` /
   `<!-- verdicts:end -->` in
   [`docs/grand-catalog-handbook.md`](../../docs/grand-catalog-handbook.md#per-layer-verdicts-generated)
   (added under a "## Per-layer verdicts (generated)" heading at the end of
   the file the first time it runs) with one Markdown table per catalog:
   layer, group, verdict status (a `pending_lanes` row renders as `pending`),
   winner(s) + pin, evidence class, alternatives count, `overturn_when`
   (truncated to 120 characters), recipe anchor and platform status. Reuses
   (imports, does not reimplement) `build_manifest.py`'s `sanitize_value` /
   `assert_no_leak` and refuses to write when a leak survives sanitization --
   applied to both generated outputs, since the handbook table renders field
   values (e.g. `overturn_when`) directly, not only the JSON document.
   **Waves.** Each dated wave document
   (`catalogs/sota-convergence/layer-verdicts-<run-id>.json`) is registered
   by sha256 in
   [`layer-verdict-waves.json`](../../catalogs/sota-convergence/layer-verdict-waves.json)
   together with its manifest and `checked_at`. A ledger row names its wave
   through `lanes.sealed_base` (a row without one belongs to the 2026-09-22
   wave). The *current* wave is the newest run id (lexicographic, so dated
   `YYYYMMDD` ids sort chronologically) present in the rows or the registry;
   every older wave is frozen. `--check` (the default, and CI's unchanged
   `validate.yml` invocation) verifies every registered wave (a) byte for byte
   against its registered sha256 and (b) against the current rows whose
   `lanes.sealed_base` names it, fails when a row names a wave that has no
   registered document, and regenerates only the current wave's document and
   the handbook's generated block from the current rows. `--check --run-id X`
   verifies wave X alone. `--write` regenerates the current wave (or
   `--run-id X` for a new, newer wave), writes the handbook block and
   registers the new sha256; it refuses to rewrite a frozen wave, and a
   registered grandfathered wave (`20260922`) is frozen even while it is the
   newest, so a row that must change is re-recorded under a new `--run-id`
   instead.

   ```sh
   python3 tools/sota-convergence/build_verdicts.py --check --root .
   ```

   `--run-id` feeds the `id` field (`layer-verdicts-<run-id>`) and the
   defaults for `--manifest` (`catalogs/sota-convergence/manifest-<run-id>.json`)
   and `--out` (`catalogs/sota-convergence/layer-verdicts-<run-id>.json`);
   either can still be overridden directly, and a registered wave reuses its
   registered manifest, path and `checked_at` (a new `YYYYMMDD` wave defaults
   `checked_at` to that date). With the 32 rows still on the 2026-09-22 wave,
   `--check` reproduces
   `catalogs/sota-convergence/layer-verdicts-20260922.json` and
   `docs/grand-catalog-handbook.md` byte for byte (`--write` refuses that wave).

   ```sh
   python3 tools/sota-convergence/build_verdicts.py --write --root . --run-id 20260923 --checked-at 2026-09-23
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
- **Pin comparison state** (2026-09-23 citation review): every
  foundation/trading row carries `pin_comparison` (`compared` or
  `not_compared`). A pin the generator could not compare (a non-GitHub
  repository, an OS-package or `.devN` pin, or a pin/upstream with no
  parseable version, reason `unversioned`) publishes `pin_behind_upstream:
  null` and `pin_comparison_reason`, never a definite `false`;
  `counts.pins_not_compared[_by_reason]` totals them. A lane's
  `pin_behind_upstream` status on an OS-package pin (systemd) is published as
  `distro_managed` (the `_unverified` suffix kept), the lane's status noted in
  the row evidence. Any other lane pin claim that contradicts the row's
  computed pin fields -- `pin_behind_upstream` on a row whose
  `pin_behind_upstream` is false or null, or a lane-returned `confirmed_*`
  (or a refuted-pin `confirmed_pin`) on a row whose `pin_behind_upstream` is
  true -- is published as `pin_status_disputed` (suffix kept), on the row and
  in `other_lane_reviews`, with the lane's claim in `disputed_lane_status` and
  a row-evidence note (`reconcile_status_with_pin`). A refuted demotion's
  `confirmed_*` makes no pin claim and is left alone.
  `counts.pins_behind_upstream_by_review_status`,
  `review_status_pin_behind_upstream`, `pin_status_disputed[_by_lane_status]`
  and `other_lane_reviews_pin_status_disputed` reconcile the computed and
  lane-claimed pin counts. A tag-only upstream whose listed tag is not
  version-shaped (`release-6-3` for the postgres mirror, `show` for kafka) is
  moved to `upstream.latest_flag` and `upstream.latest` is null: the
  freshness step reads the first tag in GitHub's name order, not the newest
  release.
- **Slug-keyed lane join** (`repo_join_key`, `index_status_by_join_key`):
  lane entries, their adversarial verdicts and lane_groupings rows join on
  `(layer, normalized GitHub slug)`, so a card whose repository carries a
  `/releases/tag/...` or `/tree/...` suffix keeps the lane review of the plain
  URL (15 lane reviews were dropped by the previous exact-string join in the
  2026-09-23 draft). `merge_lanes` still returns its exact-string index for
  direct callers.
- **Checkout-relative citations** (`--checkout-root`, repeatable, default:
  the checkout the tool runs from): a cited path inside a checkout of this
  repository is published repository-relative (`manifests/stack.json`), so
  same-named files stay distinct; the checkout root itself becomes
  `<checkout>`. Paths outside it keep the `<work-dir>/` or `<host-path>/`
  basename redaction.
- **Component-field citation findings**: a review finding that does not
  resolve to a single card but carries its own `component` field attaches to
  every card that field names within the layers its `layer` field names (all
  layers of its catalog when it names none, e.g. `multiple`).
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
- **Sanitize-then-refuse, keeping the basename and any JSON pointer**
  (G5): `sanitize_value()` walks the manifest's decoded dict/list/str values
  and redacts Linux/macOS/Windows host-path fragments *before* `json.dumps`
  (never the already-serialized text -- see its docstring for why that can
  produce invalid JSON on a quoted embedded path); the serialized result is
  then round-tripped through `json.loads` to prove it is still valid JSON,
  and `assert_no_leak()` raises if a home path or the broker key prefix
  survived. `build_manifest.py` never writes on either failure. A redacted
  host path keeps its basename and any trailing `#/json/pointer` suffix
  verbatim -- a bare `<host-path>` token alone made 223 evidence citations
  in a real manifest unresolvable, since the reader could no longer tell
  which of hundreds of files under the redacted directory a citation named.
  A path inside the private `--work-dir` becomes `<work-dir>/<basename>`;
  any other host path becomes the generic `<host-path>/<basename>`. A `/tmp`
  session-scratch path (a UUID, `claude-<uid>` or `scratchpad` segment) and
  a bare session UUID stay scrubbed to a bare token exactly as before -- a
  session-scoped path is not a stable citation target the way a file under
  the review's own working directory is.
- **Optional lane fields carried, never invented** (`merge_lanes`,
  `status[key]["entries"][*]["lane_item"]`): every field a lane's
  `selected[]` item sets beyond `repository`/`status`/`evidence`/`note`
  (`MERGED_SELECTED_KEYS`) -- `why_selected`, `comparison_that_would_overturn`,
  `role`, `catalog_id`, `catalog_pin`, `upstream_now`, or any future field --
  is copied verbatim into that entry's own `lane_item` dict generically (no
  fixed whitelist), the same place `note`/`evidence` already land per lane.
  `build_manifest()` decides per row kind which of `lane_item` reaches the
  merged row: a foundation `components[]` or trading `entries[]` row already
  carries the baseline `pin`/`upstream`, so it takes only `ROW_LANE_FIELDS`
  (`why_selected`, `comparison_that_would_overturn`) from the row's *chosen*
  entry (see the lane-review precedence rule below); a `lane_groupings[].selected`
  row has no baseline to fall back on, so it takes the whole `lane_item`
  verbatim, `catalog_id` included. Absent on the lane item means absent on
  the merged row -- `merge_lanes` never synthesizes a value for any of these
  fields.
- **Multi-lane precedence, never a silent overwrite** (`select_row_review`,
  G1): two lanes independently selecting the same `(layer, repository)` --
  e.g. a `foundation` lane's and a `beyond` lane's own row for the same
  repository -- is a real, observed shape, not an error; `merge_lanes` keeps
  every lane's entry under `status[key]["entries"]`. The row's own
  `review_status`/`review_note`/`evidence`/`lane_item` come from exactly one
  entry, chosen by a documented, deterministic precedence: (a) an entry that
  was adversarially verified (a matching proposal with `survives` true or
  false) beats an unverified one; (b) among equals, the lane that owns the
  catalog (the `foundation` lane for a foundation row, the `trading` lane for
  a trading row; no owner for a `lane_groupings` row) beats any other lane;
  (c) tie -> lexical lane name. The row also carries `review_lane` (the
  chosen lane's name) and, when another entry exists at the row's
  `(layer, repository)` key -- whether or not it also matched this card's
  own `catalog_id` (G4): a second lane's `catalog_id`-less entry sitting
  alongside a first lane's entry that DID match this card's id is not
  dropped just because it never became the chosen entry -- `other_lane_
  reviews[]` (`{lane, status, evidence, note, lane_item}` per other entry,
  verbatim) -- nothing at that key is ever silently lost off every card it
  could apply to.
- **A refuted demotion/unmaintained-signal proposal never promotes past the
  component's own baseline decision** (`resolve_refuted_marker`,
  `REFUTED_TO_CONFIRMED_MARKER`, G2): `merge_lanes` has no baseline decision
  to resolve a refuted `demotion_proposed`/`unmaintained_signal` proposal
  from, so it emits the `"refuted_to_confirmed"` marker (with the original
  proposed status recorded in the entry's own note/evidence) rather than
  guessing `confirmed_default`. `build_manifest()` resolves the marker per
  row kind at row-build time: a foundation component uses its governing
  `foundation-layers.json` decision's `selection` (`default` ->
  `confirmed_default`, `conditional` -> `confirmed_conditional`, anything
  else, e.g. `optional` -> `confirmed_selected`); a trading entry uses its
  own `decision` the same way; a `lane_groupings` row (no baseline) always
  resolves to `confirmed_as_selected`. The marker is never left in a
  published row. A component named by more than one decision in the same
  layer resolves to the MOST RESTRICTIVE selection among all of them
  (`SELECTION_RESTRICTIVENESS_RANK`: `optional` < `conditional` <
  `default`), not the first one listed in `decisions[]` order -- listing a
  looser `default` decision before a stricter `conditional` one naming the
  same component could otherwise let a refuted demotion resolve to
  `confirmed_default`, promoting the component past the conditional
  decision that also names it.
- **The same lane's verdict for a repository is shared across layers, never
  contradicted** (`merge_lanes`' `verdicts_by_repo_kind`, G3): a lane's
  adversarial verdict for a `(repository, kind)` is about the repository,
  not a particular layer. When the same lane proposes the same status for
  the same repository in a second layer with no verdict of its own there,
  the first layer's verdict (sorted by layer id, for a deterministic choice
  among more than one candidate) applies there too, with an added evidence
  line `"verdict shared from layer <id>"`; a layer that already has its own
  exact verdict is never overridden by a shared one. This keeps one lane
  from publishing two different verified classes for the same repository
  and proposal kind across layers.
- **Multi-card keys** (`match_lane_entries`, G4): two components/entries
  that share one repository in one layer (e.g. an `execution-broker`
  card and a `market-data-reference` card for the same SDK) are matched
  against a lane's `selected[]` item by the item's own `catalog_id` first
  (matched against the card's own `id`); an item with no `catalog_id` still
  applies to every card sharing that repository, and the row's evidence then
  notes `"lane entry matched by repository only; <n> cards share it"` when
  more than one card shares it. A lane's card never silently inherits a
  sibling card's `why_selected`/evidence this way.
- **Citation-review overlay, data only** (`apply_citation_review`, G6, `--citation-review`
  is optional): an independent citation review's `findings[]` are resolved
  to the manifest row they name -- `catalog` must be `foundation` or
  `trading` (a `reviewer: "tooling"` finding reviews this tool's own
  code/docs/tests, not a manifest row, and is ignored); `layer` is split on
  `"/"` and its first segment must be a real layer id; within that layer, a
  card is matched by its own `id` appearing as a hyphen-delimited whole
  segment in the finding's `repository`/`claim` text first, and only when
  no id matches, by the card's repository slug in that same text, with the
  same boundary protection (`_id_named_in`: excludes a preceding/following
  word-or-hyphen character, not a plain `\bID\b` regex boundary -- a hyphen
  is a non-word character, so a plain boundary still fires inside a longer
  sibling id or slug from either direction, e.g. `alpaca-py` inside
  `data-alpaca-py`, `card-one` inside `data-card-one`, or the slug
  `example/alpha` inside `example/alpha-extended`; a plain substring `in`
  check, previously used for the slug branch, has no boundary protection at
  all and collides the same way). A finding resolving to zero or more than
  one row is never dropped -- it is preserved, unchanged, under
  `manifest["citation_review"]["general"]` instead. The overlay only adds a
  `citation_review` field ({`reviewer`, `severity`, `claim`, `fix`, `file`,
  `line`, `evidence` -- the same citation locators as the `general` bucket,
  so a row-attached finding stays traceable back to its cited line) to the
  rows/general bucket it resolves to; it never edits a row's own fields
  (`why_selected` included). `counts.citation_review` is
  `{findings_in_artifact, findings, out_of_scope, attached, rows_flagged,
  general}`: `findings_in_artifact` is every finding in the artifact,
  `findings` is the in-scope (`foundation`/`trading`) subset,
  `out_of_scope` is the rest (e.g. `reviewer: "tooling"`), `attached` is
  the total findings actually attached to a row (can exceed `rows_flagged`,
  the count of distinct rows touched, when more than one finding names the
  same row) and `general` is the unresolved bucket's size --
  `findings_in_artifact = findings + out_of_scope` and
  `findings = attached + general` are both checkable from the manifest
  alone.
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

A later fix made `trading[]` rows exactly the taxonomy layer ids (taxonomy
order, not the previous alphabetical `layers` order) and moved any review-lane
layer id outside the foundation/taxonomy baseline (e.g. a "beyond" lane's
`awesome-list-convergence` grouping) out of `trading[]` into a new
`lane_groupings` section, so `scripts/landscape.py`'s exact-coverage check no
longer sees an id outside the 12-layer taxonomy. This touches two different
datasets, kept separate here:

- The 16-foundation-layer private input behind the reproduction above has no
  non-taxonomy trading row, so its reproduced
  `(layer, repository, review_status)` identity set, `candidates_total` and
  the rest of `counts` are unaffected by the fix.
- The newer 2026-09-22, 20-foundation-layer, "beyond"-lane work-dir the fix
  actually targets (the private `layer-verdicts-20260922` work directory
  outside the repository) *was* rerun (`build_manifest.py --work-dir
  .../layer-verdicts-20260922 ...`, no `catalogs/` write). Before the fix, an
  uncommitted pre-fix regeneration of the manifest against that same
  work-dir -- not preserved in git, and not reproducible from either commit
  on this branch -- reported 15 trading rows (three of them the non-taxonomy
  `awesome-list-convergence`/`star-audit-targeted-candidates`/
  `unmaintained-reference-material` ids) and `candidates_total=18`; the
  post-fix rerun instead reports 12 trading rows, `candidates_total=16`,
  `lane_groupings=3` and `lane_grouping_candidates=2` -- the two candidates
  that moved out of `candidates_total` are exactly the ones the three
  non-taxonomy lane layers contributed. Only the post-fix numbers are
  independently verifiable, against the manifest actually committed at this
  branch's head. No selection, pin comparison or disposition changed; only
  where the non-taxonomy rows live in the manifest, and which count they are
  scoped to, changed.

A later round (this fix) resolved six further generator defects found by an
independent citation review of the committed manifest, again against the
private `layer-verdicts-20260922` work directory (`build_manifest.py
--work-dir .../layer-verdicts-20260922 ... --citation-review
evidence/artifacts/sota-convergence-review-20260922/manifest-citation-review.json`,
no `catalogs/` write, not reproducible from a committed pre-fix path for the
same reason as the round above): a later lane's `selected[]` item for the
same `(layer, repository)` no longer silently overwrites an earlier lane's
(G1 -- headroom's `token-efficiency` row went from a self-contradictory
"pin_behind_upstream ... refuted by adversarial verification" pair to a
single internally-consistent `confirmed_pin` row with the beyond lane's
entry preserved under `other_lane_reviews`); a refuted demotion/
unmaintained-signal proposal no longer promotes a component past its own
governing decision (G2 -- agentskills/skills-ref, a `conditional`-selection
component, now resolves to `confirmed_conditional`, not `confirmed_default`;
the two codex-for-claude rows, `optional`-selection, both resolve to
`confirmed_selected`); the same lane's verdict for a repository is now
shared across layers instead of contradicted (G3 -- codex-for-claude's
`workers` and `git-github-automation` rows now carry the same class instead
of `confirmed_selected` vs. `unmaintained_signal`); two cards sharing one
repository in one layer no longer collapse onto one status (G4 -- the
`execution-broker` `alpaca-py` and `data-alpaca-py` cards now keep their own
`why_selected`/evidence); a redacted host path keeps its basename and any
JSON pointer suffix (G5 -- see the corrected token counts below, measured
against the manifest this round's fixes actually produce, not the earlier
pre-round rerun); and the citation review's own 31 in-scope findings are
overlaid onto the rows they name, or preserved in `citation_review.general`
when unresolvable (G6 -- 27 rows flagged, 28 findings attached, 3 findings
in `general` in this rerun). This rerun's full counts:
`foundation_layers=20, trading_layers=12, lane_groupings=3,
components_confirmed=109, candidates_total=16,
pins_behind_upstream_unique_components=17,
citation_review={findings_in_artifact: 36, findings: 31, out_of_scope: 5,
attached: 28, rows_flagged: 27, general: 3}`. No pin was changed by this
round -- review overlays and lane-merge fixes never touch
`pin`/`upstream`/`pin_behind_upstream`.

A further round (this fix) resolved six defects an independent citation
review found in the manifest this same round's own fixes produced, again
against the private `layer-verdicts-20260922` work directory and the same
`--citation-review` flag, not reproducible from a committed pre-fix path for
the same reason as the rounds above: (1, high) a card matched by
`catalog_id` used to drop every OTHER lane's entry for the same
`(layer, repository)` that set no `catalog_id`, instead of preserving it
under `other_lane_reviews` -- on the real `lanes.json`, 7
`(layer, repository)` keys lost a `beyond`-lane entry entirely this way
(`backtesting-engine/nautilus_trader`, `backtesting-engine/Lean`,
`market-data-reference/alpaca-py`, `market-data-reference/gdelt-doc-api`,
`portfolio-risk/quantstats`, `portfolio-risk/empyrical-reloaded`,
`evaluation-experiments/inspect_ai`); `_build_card_row` now folds every
entry at that key not already in the chosen card's `matched` set into
`other_lane_reviews`, whichever card it names. (2) the documented
word-boundary protection in `apply_citation_review` (`\bID\b`) did not
actually stop a hyphen-adjacent substring collision (`alpaca-py` inside
`data-alpaca-py`, or the reverse, `card-one` inside `data-card-one`) --
verified in-sandbox and against the real artifact, where it silently
mis-attributed a `codex-for-claude` cross-layer finding to the sibling
`codex` card via a substring hit inside `openai/codex-plugin-cc`; fixed
with `_id_named_in`'s hyphen-aware boundary, applied to both the id- and
(the same, previously boundary-free) slug-matching branches. (3)
`counts.citation_review.findings` silently dropped the 5 `catalog: "tooling"`
findings with no trace; `counts.citation_review` now also reports
`findings_in_artifact`, `out_of_scope` and `attached`, so
`findings_in_artifact = findings + out_of_scope` and
`findings = attached + general` are both checkable from the manifest alone.
(4) a row-attached `citation_review[]` record kept only
`reviewer`/`severity`/`claim`/`fix`, dropping `file`/`line`/`evidence` --
the exact citation locators this review round exists to preserve, while the
`general` bucket kept all ten fields; row-attached records now carry
`file`/`line`/`evidence` too. (5, this section) the previous "173
`<work-dir>` and 72 `<host-path>` tokens ... each keep a basename" sentence
was itself wrong (28 of the 72 `<host-path>` tokens were bare, mostly
`/tmp` session-scratch redactions, which are bare by design -- see
`sanitize()`'s docstring); measured fresh against the manifest this round's
fixes actually produce: `<work-dir>` 187 tokens, 0 bare (every one keeps a
basename); `<host-path>` 121 tokens, 72 bare and 49 keeping a basename.
Removing only the `file`/`line`/`evidence` fields fix 4 above adds to
row-attached `citation_review[]` records (verified by stripping them back
out and re-measuring) drops `<host-path>` to 77 tokens, 28 bare -- i.e. fix
4 alone accounts for all 44 of the additional `<host-path>` tokens over
that baseline, and all 44 are bare: 28 are the citation artifact's own
pre-redacted `"file": "<host-path>"` literal, one per attached finding
(the artifact's `file` field is already the bare token for every one of
its 36 findings, with no basename to preserve); the other 16 are inside
`evidence` free text that itself already quotes a bare `<host-path>` token
from an earlier-sanitized manifest. The 28-bare, 77-token baseline itself
matches the pre-fix-4 measurement in spirit (28 pre-existing bare tokens,
unrelated to this round's file/line/evidence addition -- `/tmp`
session-scratch redactions and the `citation_review.general` bucket's own
already-bare fields, both bare by design). (6) `counts.lane_groupings_note`
claimed to enumerate "every
foundation/trading-scoped count above" but omitted `counts.citation_review`
-- also computed only from `manifest['foundation'] + manifest['trading']`
rows -- the note now names it explicitly. No selection, pin, disposition or
`review_status` changed by fixes 2-6; fix 1 changes `other_lane_reviews[]`
contents only (which lane's entry is *chosen* per row is unaffected, since
G1's `select_row_review` precedence already operated correctly on whichever
entries it was given -- the bug was `_build_card_row` handing it an
incomplete list). No pin was changed by this round either.

## Lane packets

The layer-verdict lanes (Claude and Codex, run by the coordinator -- nothing
here calls a model) each judge one packet per landscape ledger layer, not the
raw ledger row: **`lane_packets.py`** withholds the incumbent's own verdict
(`current_choice`, `decision`, the layer-level `rationale` and each
candidate's `disposition`/`rationale`) so a lane argues from retained
evidence rather than copying the existing selection, and writes one packet
per `(catalog, layer_id)` to `<work_dir>/packets/<catalog>__<layer_id>.json`
plus a `<work_dir>/packets/SHA256SUMS` (`sha256sum` format).

**Layer-specific trading candidates** (`--trading-candidates manifest`). The trading
ledger rows carry four group-wide candidate lists (one per domain card), so sibling layers
chose from identical candidates and several 2026-09-22 verdicts named tools that are not the
layer's own. In manifest mode each us-equities packet instead holds the sota manifest's own
entries for that layer (adopted when their domain card decision is `default` or
`conditional`), then the layer's newcomer and keep-but-compare repositories (never adopted).
Evidence paths, role and limitations come from the entry's card in
`catalogs/us-equities/{agents-operations,data-research,engines-strategies,foundation-memory}.json`;
the card rationale and decision are withheld, and manifest review labels are not carried
at all: over the 112 2026-09-22 trading entries every label value, including
`not_individually_reviewed` and `unmaintained_signal`, correlates with the withheld decision.
The `pin_behind_upstream` flag and the upstream metadata stay. Because the ledger's requirement, limitations and
overturn text is shared by the layer's group, each packet also carries the layer's own scope
terms from the manifest taxonomy (`layer_scope_terms`) with a `requirement_note` telling the
lane to judge fit against them. A manifest entry without a card is an error, not a silent
non-adopted candidate. Card `role` and limitation prose and newcomer notes are passed through
as evidence and can still name the current pick ("selected destination runtime"); like the
`adopted` flag, that is a known limit of the withholding. So is evidence strength: over
the 112 2026-09-22 trading entries, `native_proven` evidence and a resolvable `recipe_ref`
occur far more often on default entries than on conditional ones. Foundation packets are identical in
both modes, and the default `ledger` mode still reproduces the 2026-09-22 packets byte for byte.

Known limit of the withholding (2026-09-22 independent review): each
candidate keeps its `adopted` flag, which the never-promote rule needs, and by
default foundation packets attach the matched decisions' `selection` value
(`default`/`conditional`/`optional`); the layer's `limitations` and
`existing_overturn_when` can also name the current choice. The default mode
reproduces the first 2026-09-22 packets byte for byte. `--withhold-labels`
drops candidate and SOTA-component `review_status` and the decisions'
`selection` and `review_status` from ledger-built packets; the recorded
cross-family run used it (`--trading-candidates manifest --withhold-labels`;
the 32 packets and their `SHA256SUMS` are retained under
`evidence/artifacts/layer-verdicts-20260922/packets/`). The repository a lane
reads still carries those labels in the catalog files, so withholding them from
the packets alone does not blind a lane; see the handbook's label-exposure limit.

**Registered receipts** (`--registered-receipts`, 2026-09-23 re-record). A packet's `evidence_refs` come from
the ledger row, so a lane could not see a native receipt the row never named. Under Linux, `platform_status`
accepts a `native_proven` or `measured_comparison` winner only when it cites a registered `evidence/` file.
With the flag, every candidate and `sota_components_not_in_candidates` entry carries `registered_receipts`:
the `manifests/evidence.json` receipts that name its component, sorted by path, each with `kind`, `path` and
`matched_by`.
- **`matched_by: "component_id"`:** the receipt's `component_ids` names the item's own id.
- **`matched_by: "alias"`:** receipts name components in the `manifests/stack.json` id space, which differs
  from the sota manifest's for some components. `receipt-component-aliases.json` maps each such stack id to
  its sota id (`nautilus-trader` to `nautilustrader`; `duckdb`, `edgartools` and `exchange-calendars` to their
  `data-` ids), and a receipt naming the stack id is attached to the sota id with `matched_by: "alias"`. The
  index build fails when an alias's two ids do not share one repository (see "Receipt aliases" below).
- **`matched_by: "repository"`:** a fallback for a respelling the alias map does not list. It is used only
  when (a) the item's own id and aliases match no receipt,
  (b) exactly one `manifests/stack.json` component uses the item's repository slug and the receipt names
  that component, and (c) no other sota manifest component id, in either catalog, uses that slug.
  Otherwise nothing is attached by repository (PR #142 re-review: an unconditional repository match gave
  `nautilus-ibkr-adapter` all six NautilusTrader engine receipts and `codex-native-sdk` every Codex CLI
  receipt).
- **Receipt ids:** under `--withhold-labels` the receipt `id` is dropped, because ids such as
  `native-session-defaults-20260920` can name the incumbent's role, and the packet's `withheld` list names
  `candidates[].registered_receipts[].id` and `sota_components_not_in_candidates[].registered_receipts[].id`.
  Paths and receipt contents are not stripped, and a receipt describing an adoption still says so.

A packet-level `registered_receipts_note` says how each entry matched, that a receipt may name several
components and that its `kind` is the registrant's label. The lane opens the receipt and judges what it ran
for this component.

Measured on the 2026-09-23 tree (round-2 review, rebuilt with
`lane_packets.py --root . --out <dir> --manifest catalogs/sota-convergence/manifest-20260923.json
--trading-candidates manifest --withhold-labels --registered-receipts`):
- 93 of 286 candidates carry at least one receipt.
- Candidate entries by `matched_by`: `component_id` 1097, `alias` 34, `repository` 0.
- The alias entries: `data-edgartools` 14, `data-duckdb` 13, `nautilustrader` 6 and `data-exchange-calendars` 1.
- `nautilus-ibkr-adapter`, `codex-native-sdk` and the trading `foundation-*` ids (for example
  `foundation-ai-memory`) get no receipt by repository, because each shares its slug with another manifest id.

**Limit: withholding receipt ids hides little.** 99 of the 142 registered receipt paths contain the receipt id
(`evidence/receipts/<id>.json` and similar), and the path stays in the packet so the lane can open it.

The flag is off by default, so the 2026-09-22 packets reproduce.

**Gap-wave receipts** (`--gap-receipts`, 2026-09-23 re-record). The gap-resolution waves executed checks
for the evidence gaps that the previous verdicts listed, but no ledger `evidence_refs` point to their
receipts.

With the flag, every packet carries `gap_receipts`: the sorted receipt paths that the gap-wave owner ledgers
(`catalogs/landscape/gap-wave*--*.json`) list for its layer, with missing files dropped. A
`gap_receipts_note` tells the lane to judge them like `evidence_refs`. The gap text and status are not
carried: they derive from the previous verdict rows' `open_gaps`, which can name the incumbent. The flag is
off by default.

**Popularity and recency are withheld too** (2026-09-23 peer audit: 132
foundation-packet objects still carried GitHub `stars` and `pushed_at` through
`candidates[].upstream`). Under `--withhold-labels` every packet -- manifest-mode
trading packets included -- loses `stars`, `forks`, `watchers`, `pushed_at`,
`released_at` and any other popularity or timestamp key (`*_at`, or a name
containing star/fork/watcher/subscriber/download) from every
`candidates[]` and `sota_components_not_in_candidates[]` copy and its
`upstream` record; `archived` and `license` are kept only when the packet's
`requirement` names them (archiv/maintained, licen). Each stripped field is
listed in the packet's `withheld` list (for example
`candidates[].upstream.stars`). The latest upstream release is withheld too
(2026-09-23 re-review: a date-based tag such as inspect_ai's
`release/2025-11-28` carries a release date): `upstream.latest` is stripped
always, not only when it is date-shaped (the stricter of the two options; no
packet requirement names releases, versions or maintenance), together with
`upstream.prerelease`, which describes that release, and the copy's
`pin_behind_upstream`, which is derived by comparing the pin with it, and
`upstream.latest_flag`, the flagged tag-listing fallback (it can be
date-shaped, such as `release/2025-11-28`). The strip reaches any depth of a
copy, not only the copy and its `upstream` record. The pin
itself and `upstream.renamed_to` stay. The default mode is byte-identical, so the retained
2026-09-22 packets still reproduce; they were built before this rule and carry
those fields.

```sh
python3 tools/sota-convergence/lane_packets.py --root . --out /path/to/work-dir
python3 tools/sota-convergence/lane_packets.py --root . --out /path/to/work-dir --catalog us-equities --seed 20260922
```

No network access; every input is already checked into `catalogs/` and
`adoption/`. Each candidate is matched to a `catalogs/sota-convergence/
manifest-20260922.json` component/entry by normalized GitHub slug (override
the dated manifest joined in with `--manifest <path>`, e.g. to match a later
`build_verdicts.py --manifest`/`--run-id` run so the packets and the verdict
catalog agree on the pins; default `catalogs/sota-convergence/
manifest-20260922.json` reproduces the 2026-09-22 packets byte for byte)
(`build_manifest.github_repo_slug` -- lowercase `owner/repo`, `.git`/
`/tree/...`/`/releases/tag/...` stripped); a candidate without a `repository`,
or whose repository is not a GitHub URL, never matches, and a matched
candidate carries the manifest's `pin`/`upstream`/`review_status`/
`pin_behind_upstream` fields through unmodified. `recipe_ref` prefers
`adoption/manifest.json`'s `recipe_map` keyed by the matched `component_id`,
else the first of the candidate's own `evidence_refs` that resolves to a real
path under `--root` (`scripts/catalog_decisions.safe_file` keeps that
confined to the repository), else `null`. Foundation candidates additionally
carry every `catalogs/foundation/decisions.json` decision whose
`component_ids` include the matched component (`us-equities` candidates never
carry decisions -- the decisions ledger only ever names foundation layers).
Manifest components/entries for the layer that no candidate matched are
listed separately under `sota_components_not_in_candidates`, so a lane can
see what the current landscape row has not yet considered.

Candidate order is shuffled per packet with `random.Random` seeded from
`sha256(f"{seed}{catalog}{layer_id}")` (`--seed`, default `20260922`), so
repeated runs at the same seed reproduce the same order for both lanes (no
first-listed-wins signal), while a different seed can reorder them. The
five numbered rules in `lane-prompt.md`'s "Rules" section are parsed at
build time (never duplicated by hand) into each packet's `rules` field, so
the packet and the shared prompt can never drift apart. Reuses (imports,
does not reimplement) `build_manifest.py`'s `sanitize_value`/`assert_no_leak`
and `github_repo_slug`, and `scripts/landscape.py`'s `DISPOSITIONS`/
`WINNER_EVIDENCE_CLASSES` enums (also duplicated literally, since a static
schema file cannot import them, into `lane-return.schema.json`'s own
`enum` arrays -- `tests/test_lane_packets.py` asserts the two stay in sync).
Every packet is sanitized and leak-checked before anything is written; like
`build_verdicts.py`, a leak anywhere aborts the whole run before any packet
file reaches disk.

`lane-return.schema.json` is the JSON Schema (draft 2020-12, fully inlined --
no `$ref`/`$defs` -- and `additionalProperties: false` everywhere) a lane's
returned JSON must match; it is usable directly as a `codex --output-schema`
file. `lane-prompt.md` is the shared prompt both lanes receive, with
`{PACKET_PATH}`/`{REPO_ROOT}`/`{LANE}` placeholders filled in by whichever
runner invokes the lane.

## Record verdicts

`record_verdicts.py` -- no network. Consumes the per-layer Claude/Codex lane
returns a separate lane run produces against `lane_packets.py`'s packets
(see the PR-5 lane contract's "Packet" and "Lane return" shapes) and records
them onto the layer-verdict schema v2 rows in
`catalogs/landscape/{foundation,us-equities}.json`. It never selects a
winner itself -- a lane already returned `winner_keys`, `why_selected` and
the rest of the lane-return contract; this tool only validates each lane
file, seals the accepted ones as retained evidence and derives the row's
`winners`/`alternatives`/`open_gaps`/`lanes` fields deterministically.

```sh
python3 tools/sota-convergence/record_verdicts.py \
  --root . --work-dir /path/to/work-dir --run-id YYYYMMDD [--checked-at YYYY-MM-DD] \
  [--adjudications /path/to/adjudications] --write
python3 tools/sota-convergence/record_verdicts.py \
  --root . --work-dir /path/to/work-dir --run-id YYYYMMDD [--checked-at YYYY-MM-DD] --check
```

`--checked-at` (the date stamped on every re-recorded row) defaults to the
run id's own date (`--run-id 20260923` stamps `2026-09-23`), like
`build_verdicts.default_checked_at`; a run id that is not a `YYYYMMDD` date
needs `--checked-at` explicitly.

`--write` and `--check` are a required, mutually exclusive pair (argparse
rejects both together and rejects neither) -- there is no silent default
mode.

`--run-id` is required (there is no default wave) and reruns the pipeline on
a new date without disturbing the sealed 2026-09-22 record: it is the trailing
component of
each recorded `run_id` (`<catalog>-<layer_id>-<run-id>`) and of the sealed
directory (`evidence/artifacts/layer-verdicts-<run-id>/`). Pass the same
`--run-id` to `--check` as was used for `--write`. A row recorded under a
non-default `--run-id` also carries `lanes.sealed_base` (e.g.
`evidence/artifacts/layer-verdicts-20260923`) so `scripts/landscape.py`
resolves its sealed files from the row itself, not from a hardcoded
constant; a row recorded (or never re-recorded) under the default omits
`sealed_base` and `scripts/landscape.py` falls back to the sealed
2026-09-22 directory, so every already-checked-in row stays valid. `--write
--run-id 20260922` is refused once `--root` holds that wave (see
*Grandfathered run id* below); `--check --run-id 20260922` still reproduces it. `--run-id` is validated
against the same character class `scripts/landscape.py` requires of
`lanes.<lane>.sealed_base` (`[0-9A-Za-z]+`; no `-`, `/` or `..`) before any
sealed file is written, in both `record_verdicts.py` and
`build_verdicts.py`'s own `--run-id` -- a malformed value is rejected up
front rather than surfacing only when `scripts/landscape.py` runs later.

```sh
python3 tools/sota-convergence/record_verdicts.py \
  --root . --work-dir /path/to/work-dir --checked-at YYYY-MM-DD \
  --run-id 20260923 --write
```

**A later wave keeps CI green.** After `record_verdicts.py --run-id <new>
--write`, run `build_verdicts.py --write --run-id <new> --checked-at
YYYY-MM-DD` once to register the new wave document; CI's unchanged
`build_verdicts.py --check` then verifies every wave: the frozen
`layer-verdicts-20260922.json` byte for byte against its registered hash and
against the rows still naming 2026-09-22, and the new wave (current) by
regenerating it and the handbook block from the rows. A row still naming a
frozen wave cannot change without failing that check; re-record it under the
new run id instead. The simulated second wave is
`tests/test_layer_verdicts.py` `WaveFreezeTests`.

**Integrity rules outside the grandfathered wave** (2026-09-23 peer audit;
shared code in `scripts/landscape.py`, applied here at record time and
re-applied by `scripts/landscape.py` in CI to the sealed files):

- *Grandfathered run id.* `GRANDFATHERED_RUN_IDS = {"20260922"}`. The 32 rows
  sealed on 2026-09-22 predate these rules: their lane returns declare no
  `model.family` or `provenance`, their 12 adjudications are Opus-only (both
  presentation orders, no judge identity), they have no run manifest (their
  `packets/` and `SHA256SUMS` are retained under the sealed base; a manifest
  generated now could not list the rejections of that run, so none is
  fabricated), and their Linux `platform_status` came from the lane's evidence
  class alone: 13 of their 33 Linux `accepted` winners (six rows:
  `foundation/ci-supply-chain`, `foundation/hosting-services`,
  `us-equities/market-data-reference`, `storage-compute`,
  `research-factors-ml`, `portfolio-risk`) cite no registered `evidence/` file,
  so `scripts/platform_status.py` would derive `conditional`. Those rows stay valid because the committed wave is
  frozen, whether or not a later wave exists yet: `record_verdicts.py` has no
  default `--run-id` and its `--write` refuses a grandfathered id once `--root`
  holds that wave (its sealed directory or a registered wave document), so it
  never re-records a row or writes a run manifest there; `build_verdicts.py
  --write` refuses to regenerate or re-register a registered grandfathered
  wave even as the newest, and `--check` fails if any row naming 2026-09-22
  differs from the hash-registered `layer-verdicts-20260922.json`; and
  `tests/test_layer_verdicts.py` `GrandfatheredWavePinTests` (CI's `python3 -m
  unittest`) pins that document, its registry entry and the sha256 listing of
  every file under the sealed 2026-09-22 directory. Every other run id gets
  every rule below.
- *Single-family winner.* Claude-only (`codex_absent`) records nothing by
  default: the row stays `pending_lanes`. `--allow-single-lane PATH` (an
  existing file under `docs/decisions/` with a date, `YYYY-MM-DD` or
  `YYYYMMDD`, in its name) records a `codex_absent` layer from Claude alone
  only when the record carries the exact line
  `single-lane-authorization: <catalog>/<layer_id>` for it (mentioning the
  layer id anywhere else, as a wave document does for all 32 layers,
  authorizes nothing), and stores the path and the record's sha256 on the row
  as `lanes.single_lane_decision` and `lanes.single_lane_decision_sha256`;
  `scripts/landscape.py` re-checks all of it and rejects any recorded
  `codex_absent` row without such a record (this rule has no grandfathering:
  no 2026-09-22 row is `codex_absent`).
- *New-wave rows cannot opt out.* `scripts/landscape.py` applies every rule
  below to a row whose `lanes.sealed_base` or any lane `run_id`
  (`<catalog>-<layer_id>-<run-id>`) names a non-grandfathered wave, whether or
  not a lane carries a run id: the run ids must then name that same wave and
  layer, a lane carries a run id exactly when it carries a sealed hash, and a
  run id naming a new wave under the grandfathered `sealed_base` is rejected.
  On every recorded row, `same_winner` and `disagree` need both lanes sealed
  and `codex_absent` needs the claude lane sealed and the codex lane unsealed.
- *Identity and family.* Each lane return declares `model.family`: `anthropic`
  for the claude lane with a name matching
  `claude-*|opus|sonnet|fable|haiku`, `openai` for the codex lane with a name
  matching `gpt-*|codex`; the two lanes' families must differ. Every
  adjudication judgment records `judge: {model, family}` (family anthropic or
  openai, name matching it) and the `stripped_packet_sha256` its judge saw,
  which must equal the layer's sealed lane packet (its `packets/SHA256SUMS`
  entry at record time, its run-manifest `packet_sha256` in CI): hand the
  judge the `--withhold-labels` packet the lanes judged, not a reduction. A
  winner is accepted only when judgments from both lane families are present,
  each family covers both presentation orders, all pick the same lane and none
  is refuted; otherwise the adjudication is sealed as a split and the row stays
  `pending_lanes` (a missing family is named in `open_gaps`). `winner_lane` is
  checked after that two-family rule: a unanimous single-family adjudication is
  a split whether its `winner_lane` is `null` or names the lane its judges
  chose. A recorded
  `disagree` row needs its sealed adjudication in CI as well.
- *The row is what its sealed wave establishes* (review of catalog #122).
  `scripts/landscape.py` recomputes a new-wave row's `agreement` from both
  sealed returns' `winner_keys`, resolved to component ids through the
  retained packet each return names (`packet_sha256`), and requires a recorded
  row's winners to be exactly the chosen lane's set (`same_winner` or
  `codex_absent`: the claude lane; `disagree`: the adjudication's
  `winner_lane`); an unrecorded row carries no winners. Relabelling a
  disagreement or swapping in the other lane's winners fails CI.
- *Claude refutation.* A new-wave Claude return carries the lane's
  `refutation` summary (`layer-verdict-lane.js`, copied by `claude_lane.py`);
  it is rejected unless `status` is `unrefuted` and both lens votes
  (`evidence`, `challenger`) on the round that produced the final returned
  `refuted: false`. A layer whose final was refuted or unknown gets no return.
- *Survivorship.* Every run writes
  `evidence/artifacts/layer-verdicts-<run-id>/run-manifest.json`: every packet
  (catalog, layer, packet sha256), each lane's outcome (`sealed` with its run id
  and sealed sha256, `rejected` with its reasons, `failed` with the reason the
  lane runner listed in `<work-dir>/<lane>/failures.json`, or `missing`),
  rejected adjudications, the retained packets (`retained_packets`) and the
  `packets/SHA256SUMS` text. A reason that would still carry a leak marker is
  replaced by a fixed note. `scripts/landscape.py` requires every row recorded
  in a non-grandfathered wave to appear in that manifest exactly once, with both
  lanes accounted for and its packet hash in the recorded SHA256SUMS text.
- *Retained packets.* A new wave's `--write` copies the packets and their
  `SHA256SUMS` into `<sealed_base>/packets/` and refuses a packet that still
  carries a withheld key (`scripts/landscape.py` `withheld_packet_keys`, which
  walks the whole packet: at any depth a popularity count, any `*_at` other
  than the packet's own `checked_at`, `pin_behind_upstream`, `newcomer`,
  `note`, or a key naming the latest version, a release or a newcomer --
  `upstream.latest`, `upstream.prerelease`, `upstream.latest_flag`, a nested
  `release` or a top-level `newcomers` list; `archived`/`license` unless the
  requirement names them; on a candidate or component copy `selection`,
  `disposition`, `rationale`, `current_choice` or a non-null `review_status`;
  and any always-listed policy label missing from `withheld[]`, which shows
  the packet was not built with `--withhold-labels`). `withhold_popularity`
  strips with the same predicate at any depth. CI re-reads each retained
  packet (hash and withheld keys), requires each row's packet there, and binds
  the adjudication judgments' `stripped_packet_sha256` to it.
- *A sealed wave is never rewritten.* A new wave's `--write` refuses once its
  `run-manifest.json` exists, unless `--append-rows CATALOG/LAYER_ID[,...]`
  names only rows absent from it (the manifest keeps its entries and gains
  those rows), and never overwrites a sealed file with other bytes. Each row
  stores `lanes.run_manifest_sha256` (an append re-binds the wave's rows) and,
  when an adjudication was sealed for it, `lanes.adjudication_sha256`, which
  the manifest entry also lists (`adjudication: {outcome: sealed, sha256}`);
  `scripts/landscape.py` verifies each against the other and the file, rejects
  any file under a new wave's sealed folder that no row and not the run
  manifest references, and rejects a `layer-verdicts-<id>` folder whose id is
  not alphanumeric (no row can name it).
- *Platform status (one shared rule).* `record_verdicts.platform_status_for`
  calls `scripts/platform_status.py` `platform_status(platform_id, winner,
  context)` for every platform, with `context = load_context(root)` read once
  per run; `scripts/landscape.py` and `scripts/component_matrix.py` call the
  same function. Linux `accepted` needs a qualifying host receipt, or a
  `native_proven`/`measured_comparison` winner citing a hash-registered
  `manifests/evidence.json` `files[]` entry under `evidence/`; `macos-arm64`
  moves off `untested` only through host receipts bound to the winner's pin.
  Nothing under `evidence/artifacts/layer-verdicts-<run-id>/` counts (packets,
  lane returns, adjudications and their inputs are lane inputs or opinions).
  `scripts/landscape.py` holds a new-wave row to this rule on every platform
  (`declared_status_error`) and a grandfathered row on `ENFORCED_PLATFORMS`
  only (`macos-arm64`; the re-record widens it to Linux).
- *Reproducible lanes.* A Claude return carries `provenance: {workflow_path,
  workflow_sha256, agentlab_commit}` and a Codex return `provenance:
  {codex_lane_py_sha256, prompt_sha256}`. Both must name lane code listed in
  the append-only `tools/sota-convergence/lane-provenance.json` (the full
  `workflow_path` is matched, not its basename), which `scripts/landscape.py`
  re-checks for every sealed new-wave return in CI. At record time the Claude
  hash must also equal the current `examples/claude-native/workflows/SHA256SUMS`
  entry of the vendored copy the registry entry names (the lane workflow is
  vendored there, pinned in `vendored-lanes.json`), and the Codex hashes this
  checkout's `codex_lane.py` and `lane-prompt.md`. When any of those files
  changes, append an entry (never edit one);
  `tests/test_verdict_lane_vendoring.py` fails until the current bytes are
  listed. `codex_lane.py` writes its provenance and the whole `model` field
  itself: `model.name` is the `--model` it passed to `codex exec -m`, else the
  model name the event stream carried, else `unknown` (never the model's own
  response text), `model.effort` is `--effort` and `model.family` is
  `"openai"`; the strict schema it passes to `codex exec` omits `provenance`
  and `model.family`. The
  vendored Claude workflow returns only `model {name: "opus", effort: "high"}`
  and writes no files; `claude_lane.py` is the step that writes
  `<work-dir>/claude/<catalog>__<layer_id>.json` from the workflow result,
  adding `model.family: "anthropic"`, the resolved model name and
  `provenance`. It exits 2 when the agent-lab workflow file differs from that
  checkout's `HEAD` or from the vendored `SHA256SUMS` entry:

  ```sh
  python3 tools/sota-convergence/claude_lane.py --result /path/to/lane-result.json \
    --work-dir /path/to/work-dir --agentlab-root /path/to/agent-lab \
    --resolved-model claude-opus-5-5
  ```

**Two-family adjudication is keep-but-compare** (decision
[`docs/decisions/2026-09-23-verdict-integrity.md`](../../docs/decisions/2026-09-23-verdict-integrity.md)).
The rule that a disagreement is settled only by unanimous, unrefuted judgments
from both lane families (Anthropic and OpenAI), each in both presentation
orders, is the current default, not a proven best judge design: the judges
share a family with a lane they rule on. Overturn condition: a qualified
third-family judge (for example the key-free local Qwen3-8B-AWQ worker) clears
a preregistered judge-agreement bar on the sealed 2026-09-22 and 2026-09-23
adjudication packets; the rule then moves to (or adds) that judge.

- **Per-lane validation, never aborts the run.** For every layer with at
  least one `<work-dir>/{claude,codex}/<catalog>__<layer_id>.json` file, each
  present lane file is checked against the full lane-return contract (schema
  shape, `packet_sha256` matching `<work-dir>/packets/SHA256SUMS`, every
  `winner_keys` entry an adopted packet candidate, every adopted non-winner
  candidate present in `alternatives`, `why_selected` distinct from every
  `why_not_default`, `overturn_when` naming a `fixtures/`, `blueprints/`,
  `tests/` path or a runnable `python3`/`node` command, no property outside
  `lane-return.schema.json` at any level, an https `challenger_preferred`
  repository, and a `why_selected` that names at least one of its own
  `winner_evidence_refs` paths). The packet file itself must hash to its
  `SHA256SUMS` entry. A lane whose sealed text would still carry a leak
  marker after sanitization is rejected the same way, and a malformed
  adjudication file is reported (lane `adjudication`) instead of ignored.
  A file that fails any rule is reported (catalog, layer id, lane, the
  failing rule) and treated as absent for that layer -- this never aborts
  the run, but the process exits 1 at the end if any lane file was rejected,
  in both `--write` and `--check`.
- **Sources read.** A lane records the absolute paths it opened. Before
  sealing, each is rewritten to its longest suffix that names a file in this
  repository (a trailing note is kept); paths outside the repository are
  left for `sanitize_value` to redact.
- **Winner never an alternative.** When a losing lane (or a lane's own list)
  names a winner as an alternative, that entry is dropped from the recorded
  row; if no indexed alternative remains, the row stays `pending_lanes` with
  that gap, matching `scripts/landscape.py`'s recorded-verdict rule.
- **Integrity.** `--check` also compares every recomputed sealed file with
  the file on disk, and `scripts/landscape.py` verifies each
  `lanes.<lane>.sealed_sha256` against the sealed file's bytes.
- **Sealing.** Every accepted lane return is reserialized deterministically
  (`sort_keys=True, indent=1` + newline -- the same convention every
  generator here uses, subject to the same `build_manifest.py`
  leak defense) and written to
  `evidence/artifacts/layer-verdicts-<run-id>/<lane>/<catalog>-<layer_id>-<run-id>.json`
  (`<run-id>` from the required `--run-id`); its sha256 becomes the
  row's `lanes.<lane>.sealed_sha256`.
- **Derived winner `pin`** (never taken from the lane): the packet's own
  manifest-joined `pin`, else the winning candidate's real v1 pin text if
  any -- the ledger's actual `candidates[]` schema carries this as
  `source_pin` (preferred) or, on a few rows, `revision`; there is no
  `v1_pin` field anywhere in the repository -- else the literal string
  `"unpinned"`.
- **Agreement.** Both lanes valid and their winner component-id sets equal
  -> `same_winner` (recorded from Claude's `why_selected`/`overturn_when`, the latter written to
  `verdict_overturn_when`,
  Codex's `open_gaps` appended); Claude only -> `codex_absent` (`pending_lanes`
  unless `--allow-single-lane` names a dated decision record naming the layer;
  see the integrity rules above); both valid but
  disagreeing -> `disagree`: recorded from the lane an optional
  `--adjudications/<catalog>__<layer_id>.json`
  (`{"winner_lane": "claude"|"codex"|null, "why", "evidence_refs": [...],
  "judgments": [{"claude_position": "A"|"B", "preferred_position": "A"|"B",
  "preferred_lane", "refuting_votes"}, ...]}`) names (the file itself is
  retained at
  `evidence/artifacts/layer-verdicts-<run-id>/adjudication/<run_id>.json`).
  The tool enforces the counterbalanced rule: the judgments must include
  both presentation orders (Claude's return shown as A and as B), each
  `preferred_lane` must follow from its positions, and `winner_lane` must be
  the lane every judgment chose with no refuting vote. When the judgments
  split or any was refuted, `winner_lane` must be `null`; the file is still
  sealed and the row stays `pending_lanes` with the tally in `open_gaps`.
  Outside the grandfathered 2026-09-22 wave each judgment also names its
  judge (`judge: {model, family}`) and `stripped_packet_sha256` (the layer's
  sealed packet hash), and a unanimous winner still needs both lane families in both orders, else the
  row is a sealed split.
  Without an adjudication file the row stays `pending_lanes` with the open
  disagreement recorded
  (`open_gaps` names the two lanes' winner *component_ids* -- the same
  identity the agreement check itself compares -- never the packet-local
  candidate keys, which are opaque outside the packet). Codex-only (no
  dedicated agreement value exists for it) folds into the same "neither lane
  ran" `pending` state -- Codex's file is still sealed for later reuse, but
  no winner is recorded from a single non-Claude lane.
- **Alternatives** are the union of both lanes' `alternatives` by normalized
  repository slug (Claude's entry first; `source` is always `lane:claude` or
  `lane:codex`, never a packet-derived value). An alternative whose
  repository is not in the canonical index
  (`catalogs/landscape/manifest.json#/sources/repository_index`) is moved
  into `open_gaps` as `"unindexed alternative <name> <url>"` instead of
  being rejected -- this check runs on every processed row, including one
  that stays `pending_lanes` (e.g. a disagreement), not only a `recorded` one.
- **Never modifies a v1 field.** The winning lane's `overturn_when` (which the
  lane-return contract requires to carry one of `fixtures/`, `blueprints/`,
  `tests/`, `python3 ` or `node `) is written to the v2-owned
  `verdict_overturn_when`; the v1 `overturn_when` stays the dated review's text,
  which `catalogs/landscape/candidate-quality-review.json` mirrors per layer.
- **Citations are normalized in code.** A lane cites evidence the way a reader
  would (`docs/x.md:107-130`, `catalogs/y.json#L564 (note)`, `receipt.json lines
  10-11`). Each row keeps only the bare canonical repository path (or safe https
  URL), deduplicated in first-seen order; the sealed lane return keeps every
  full citation. Citations that resolve to no repository file (for example one
  naming the lane packet itself) or name a generated publication index
  (`manifests/evidence.json`, `docs/ecosystem/index.html`, whose citation would
  make the explorer embed its own hash) are counted in one `open_gaps` entry,
  never kept in `evidence_refs`.
- `--check` recomputes every row in memory and exits 1 on any difference
  from what is checked in, without writing; `--write` writes the two ledger
  files (`json.dumps(doc, indent=2, ensure_ascii=False)` + newline -- the
  exact serialization these hand-maintained files already use, so an
  untouched row's bytes, including field order, do not move) and the sealed
  evidence files. Re-running `--write` on an already-current work dir writes
  byte-identical output.

After recording, refresh the generated join and narrative and rerun the
landscape and publication checks:

```sh
python3 tools/sota-convergence/build_verdicts.py --write --root . --run-id YYYYMMDD --checked-at YYYY-MM-DD
python3 scripts/landscape.py --root .
python3 scripts/validate.py
```

## Blind checkout

`blind_checkout.py` -- no network, no model call. Given `--source` (an
existing git checkout), `--rev` and a `--dest` that does not yet exist, it
runs `git worktree add --detach <dest> <rev>` and then mutates files only
inside `<dest>`, so a lane can review candidates without seeing what a
previous run (or the checked-in ledger) already chose.

```sh
python3 tools/sota-convergence/blind_checkout.py \
  --source . --rev HEAD --dest /path/to/blind-checkout --export /path/to/blind-export
# ... run the blind lanes against /path/to/blind-export (no .git, no BLIND-MANIFEST.json) ...
git worktree remove --force /path/to/blind-checkout
```

`--export` copies the stripped tree without `.git` or `BLIND-MANIFEST.json`. The worktree's `.git` reaches
the source repository's history, so `git show <rev>:<path>` would recover every stripped value.
Hand the lanes this copy, not the worktree, and place it outside every repository (`codex_lane.py` refuses
a `--repo` below any `.git`).

**Instruction files in the export (PR #141 review).** A coding agent loads project instructions from the
tree it starts in, and this repository's `AGENTS.md` names the incumbent choices (the selected destination
engine, for one). In the export only, never in the worktree:
- every `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md` and `CLAUDE.local.md`, at any depth, is replaced by
  one neutral stub (`blind_checkout.EXPORT_INSTRUCTION_STUB`). The stub says the tree is a sanitized export
  for a blind layer-verdict lane, that the lane judges only from its packet and the files, and that no
  file is an instruction to the lane. The root always gets `AGENTS.md` and `CLAUDE.md` stubs.
- every `.claude/`, `.codex/` and `.agents/` directory, at any depth, is left out.

On the 2026-09-23 tree this covers `AGENTS.md`, `CLAUDE.md`,
`blueprints/convergence-practice/application-delivery/{AGENTS,CLAUDE}.md` and
`examples/claude-native/CLAUDE.md`; the tree has no `.claude/`, `.codex/` or `.agents/` directory. The CLI
prints both lists (`export_instruction_files_replaced`, `export_instruction_dirs_removed`).

**Remaining limits: what the export still carries.** The export strips the JSON label fields under
`catalogs/` and `blueprints/` (below) and the instruction files. It does not strip:
- **Markdown prose.** It is copied unchanged and still names selections, for example `README.md` ("selected
  components"), `docs/foundation-stack.md`, `docs/landscape-continuation.md`,
  `blueprints/us-equities/north-star.md`, `blueprints/us-equities/engine-nautilus/`, `adoption/`, `recipes/`
  and the `catalogs/**/*.md` narratives. (`docs/grand-catalog-handbook.md` is removed outright.)
- **Prior evidence artifacts.** JSON under `evidence/artifacts/` other than `layer-verdicts-*` is kept,
  because packets cite prior artifacts as evidence. On the 2026-09-23 tree, "selected" (case-insensitive)
  occurs 1,799 times in 121 JSON files across 35 of those directories. The largest are
  `blind-catalog-convergence-20260921/` (541 in 9 files; `claude-final-layers.json` alone has 158),
  `full-stack-convergence-20260921/` (220), `claude-repository-evidence-20260921/` (152),
  `sdk-runtime-coverage-20260922/` (139) and `catalog-runtime-review-20260921/` (133).
  `catalog-reconciliation-20260922/claude-return.json` also records a prior lane's selections.
- **Instruction files outside the export.** The export cannot neutralize instructions a client loads from
  elsewhere: a parent directory's `AGENTS.md` or `CLAUDE.md`, `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md`
  (`$CODEX_HOME/AGENTS.md`). A probe Codex child quoted `~/.codex/AGENTS.md`, so it is known to load for
  Codex children. The Claude lane's `blind-lane-reviewer` agents run with `omitClaudeMd`.

None of these is stripped wholesale, because a lane also reads them as evidence. The controls are lane-prompt
rule 1, placing the export outside every repository, and the post-run blind audit (a lower bound). A
coordinator discloses these limits with the wave.

It removes outright: `evidence/artifacts/layer-verdicts-*/` (recursively),
`catalogs/sota-convergence/layer-verdicts-*.json`,
`docs/grand-catalog-handbook.md`, `docs/ecosystem/index.html` and
`docs/ecosystem/manifest.json`. In the two landscape ledgers
(`catalogs/landscape/{foundation,us-equities}.json`) it resets every row's
layer-verdict schema v2 fields to `pending_lanes` with empty
`winners`/`alternatives`/`open_gaps`, a pending `lanes` object, an empty
`verdict_overturn_when` and an empty `overturn_protocol`
(`{"fixture_paths": [], "metric": "", "arms": []}`) -- keeping
`requirement`/`evidence_refs`/`overturn_when`. `open_gaps` and
`overturn_protocol` reset alongside `winners`/`alternatives` because
`record_verdicts.process_row` writes them from the same lanes' returns, and
an `open_gaps` entry or an `overturn_protocol.arms` value routinely names a
lane's winner or a disagreement between the lanes by name. It also removes
the v1 label fields `current_choice`, `decision`, `rationale` (row level) and
`disposition`, `rationale`, `review_status` (each `candidates[]` entry).
Every other JSON file under `catalogs/` has `selection`, `decision`,
`disposition`, `current_choice` and `review_status` removed wherever they
appear, regardless of value; under `blueprints/` the same five keys are
removed only when the value is itself a label -- a closed-vocabulary string
(the closed-vocabulary labels in `blind_checkout.LABEL_VALUES`, for example `selected`, `retain`, `confirmed_default`,
`selected_destination`, `adopt_within_scope`, `reject_evidence`, `defer`,
`advisory_supported`/`advisory_contradicted`/`advisory_insufficient` and
their `... retained; reviewer concurs` forms, `qualified_within_isolated_
synthetic_scope`, `retain_2.3.1_pending_functional_acceptance`,
`source-reviewed-not-executed`, `language alternative only`, etc.), free
text stating a selection (contains "selected", or matches "keep ...
selected"), or free text that opens with "retain"/"adopt"/"reject"/"defer"
(case-insensitively, at a word boundary -- e.g. `"Retain current catalog
pin..."`) -- a mapping/rule value or an unrelated data or procedural value
(e.g. `"top_20"`, or `"Submission is deferred by session, not by bar
count..."`, which does not open with the decision verb) under one of those
keys is left alone. Longer free text is classified by review into
`LABEL_TEXT_SHA256` (stripped) and `DATA_VALUE_SHA256` (kept, including one
corpus methodology statement the "selected" rule would otherwise catch), keyed by
the sha256 of the exact string. `tests/test_blind_checkout.py` fails when a value
under these keys in this repository's `blueprints/` is neither a label by rule
nor classified, so each new value gets a decision when it first appears.

`<dest>/BLIND-MANIFEST.json` lists every removed file and every stripped
JSON path together with its old value's **HMAC-SHA256** (never a plain
unsalted `sha256`, and never the value itself) -- a small closed vocabulary
of label strings would otherwise let a lane dictionary-attack an unsalted
hash straight back to the original value. The key is a fresh random 32
bytes generated per run and is never written under `<dest>`;
`blind_checkout.py`'s CLI writes it to `<dest>.hmac-key` (a sibling of
`<dest>`, not inside the worktree handed to a lane) so an operator can
verify a hash later, or pass `hmac_key=` explicitly to `run_blind_checkout`/
`strip_worktree` when two runs' hashes must be directly comparable. `--rev`
is resolved to a full commit SHA (`git rev-parse <rev>^{commit}`) before the
worktree is created, and the manifest records that resolved SHA plus the
originally requested `--rev` string as `rev`/`requested_rev` -- it never
records `--source`'s absolute host path.

This tool never removes the worktree it creates; the caller does that with
`git worktree remove --force <dest>` once the blind lane has finished.
The worktree itself is not blind. It is a `git worktree` of `--source` and shares that repository's
object store, so `git log`, `git diff` or `git show HEAD:<path>` inside `<dest>` recovers every stripped
value. `git archive` does not help either: it exports the committed tree before stripping. Use
`--export`, which omits `.git`; `codex_lane.py` refuses a repository with `.git` unless
`--allow-git-history`.

The manifest's per-field hashes are keyed, but they still let an operator who holds the key map every
stripped path to its class of change. They are the operator's audit trail, and `--export` leaves them out.

## Codex lane

`codex_lane.py` is the Codex half of the layer-verdict lane pair described in
the PR-5 lane contract (Claude's own lane is run as an agent-lab saved
workflow, not from this repository). It is a subprocess/text pipeline over
`codex exec`, not a schema validator: full validation of the returned JSON
against `lane-return.schema.json` is `record_verdicts.py`'s job.

For every packet under `<work-dir>/packets/<catalog>__<layer_id>.json`
(written by `lane_packets.py`) without an already-valid
`<work-dir>/codex/<catalog>__<layer_id>.json` on disk -- valid meaning: the
existing file parses as a JSON object with `lane == "codex"`, `catalog` and
`layer_id` matching this packet, if it already has a `packet_sha256`,
that hash still matching the packet file's current bytes, and its `provenance`
equal to the current `lane_provenance(--prompt)` (this `codex_lane.py`'s and the
prompt template's sha256; a return from older lane code, an older prompt or
without provenance is rerun, not skipped, because `record_verdicts.py` would
reject it on every later run), and its `model.name` neither `"unknown"` nor, when `--model` is given,
different from it (round-2 review) -- it fills the
shared lane prompt (`lane-prompt.md`, placeholders `{PACKET_PATH}`
`{REPO_ROOT}` `{LANE}`) and runs:

```sh
codex exec --sandbox read-only --skip-git-repo-check --ephemeral \
  -C <repo> --output-schema <schema> -o <out.tmp> --json \
  -c model_reasoning_effort=<effort> \
  --ignore-user-config -c features.hooks=false -c features.plugin_hooks=false \
  -c 'web_search="disabled"' <filled prompt>
```

The four isolation settings on the last two lines are `ISOLATION_ARGS`; `tests/test_codex_lane.py` fails when
this block or the module docstring leaves one out.

capturing the full JSON event stream to
`<work-dir>/codex/events/<catalog>__<layer_id>.jsonl` and appending one usage
row per attempt (`catalog`, `layer`, `attempt`, `exit_code`, `timed_out`,
`model`, `seconds`, plus whatever token fields were found) to
`<work-dir>/codex/usage.jsonl`. The event stream's shape is never assumed
beyond "JSON objects, one per line": model name and usage/token fields are
extracted from the last events that carry them anywhere in the object,
tolerant of unknown shapes, and a layer is never failed merely because usage
was not found.

`-o`'s output file (the agent's last message) is parsed as one JSON object.
`lane` is always forced to `"codex"`; `packet_sha256` is filled from the
packet file's own sha256 only when the model's response did not already set
one; `model` is filled from the event stream (falling back to
`{"name": "unknown", "effort": <--effort>}`) only when the response did not
already carry a usable `model.name` -- an already-set field from the model's
own response is never overwritten. A failing attempt (non-zero exit,
timeout, or a missing/unparseable `-o` file) is retried exactly once; if the
retry also fails, the layer is left unwritten (picked up again by the next
run, via the resumable-skip check above) and the run's own exit code is 1.
Any `<catalog>__<layer_id>.out.tmp` left over from a prior attempt (or an
earlier run killed by SIGKILL/Ctrl-C/OOM before it could clean up) is removed
immediately before each attempt is launched, not only after a failure is
detected, so a stale file is never misread as the current attempt's own
output.

A blind wave gives the lane a `blind_checkout.py --export` copy placed outside every repository (`--repo .`
exits 2, because the checkout has `.git`):

```sh
python3 tools/sota-convergence/blind_checkout.py \
  --source . --rev HEAD --dest /path/outside/repos/blind-checkout --export /path/outside/repos/blind-export
python3 tools/sota-convergence/codex_lane.py \
  --work-dir /path/to/work-dir --repo /path/outside/repos/blind-export --effort high
python3 tools/sota-convergence/codex_lane.py \
  --work-dir /path/to/work-dir --repo /path/outside/repos/blind-export --layers native-clients,market-data-reference
python3 tools/sota-convergence/codex_lane.py \
  --work-dir /path/to/work-dir --repo /path/outside/repos/blind-export --dry-run   # prints the command per pending layer, writes nothing
git worktree remove --force /path/outside/repos/blind-checkout
# Not blind: a run against the checkout itself, whose git history recovers every stripped label.
python3 tools/sota-convergence/codex_lane.py \
  --work-dir /path/to/work-dir --repo . --allow-git-history
```

**Blind children (2026-09-23 re-record).** Memory stores, code indexes, the web and git history can
return the incumbent verdicts or the catalog's selection labels.

What configuration denies. Every `codex exec` runs with:
- `--ignore-user-config`, which skips `$CODEX_HOME/config.toml`. Auth still uses `CODEX_HOME`. The
  user's MCP servers, plugins, profiles and project trust do not load, and without trust no project
  `.codex/config.toml` loads either.
- Lifecycle hooks off: `features.hooks` and `features.plugin_hooks`.
- Native web search off: `web_search="disabled"`.

Measured with codex-cli 0.155.1:
- **MCP servers** (`RUST_LOG=info`, from the agent-lab checkout): a default run initialized seven MCP
  servers (ai-memory, SocratiCode, jCodeMunch, Serena, context-mode, plugin-runtime and OpenAI
  Developers MCP). With the flags, only plugin-runtime and OpenAI Developers MCP initialized.
- **Web search:** a probe child without the web-search pin ran a web search. With it, the child reported
  no web search tool.
- **Rejected alternative:** per-server `mcp_servers.<name>.enabled=false` overrides failed with
  "invalid transport". Codex rejects such a partial table when the loaded config does not define that
  server.

What remains and how it is handled:
- **Shell reads:** `--sandbox read-only` still lets a child read any host path and run CLIs such as
  ai-memory from `PATH`. Rule 1 of `lane-prompt.md` forbids it, and so does the Claude lane's blind rule.
- **Global instructions:** a probe child quoted `$CODEX_HOME/AGENTS.md`, so that file still loads.
- **Git history:** `codex_lane.py` refuses a `--repo` when it or any parent directory has `.git`, because git
  walks up from a subdirectory. Pass `--allow-git-history` only outside a blind wave. Run the lanes on a
  `blind_checkout.py --export` copy placed outside every repository.
- **Blind audit:** after each run, `codex_lane.py` writes `<work-dir>/codex/blind-audit.json`, a
  report-only reading of each child's events. It counts web searches and MCP tool calls, and flags
  commands that do any of the following:
  - name an absolute path outside the repository and the packets directory. Only `/dev/null` and a
    command segment's executable token are exempt, and the token only when it is under `/bin/`, `/sbin/`,
    `/usr/bin/`, `/usr/sbin/` or `/usr/local/bin/`. The executable token is the first word at the start,
    after `;`, `&&`, `||`, `|` or a newline, or right after `bash -lc '` (or `sh -c "`). A data path under
    `/usr/` or `/bin/` is flagged, so `/bin/cat /usr/local/share/prior-verdict.json` flags
    `/usr/local/share/prior-verdict.json`, and so is an executable elsewhere under `/usr/`, such as
    `bash -lc '/usr/local/share/verdicts/show'`;
  - use a `~`, `$HOME` or `${HOME}` path, or any other `$VAR/...` or `${VAR}/...` path (for example
    `$CODEX_HOME/AGENTS.md`), whose value the event does not show;
  - `cd` somewhere the command does not name: bare `cd`, `cd -`, `cd ~`, or `cd` to a bare variable such as
    `$OLDPWD` or `"$OLDPWD"`;
  - climb out with `..`;
  - run git, ai-memory, agentsview, mcporter, qmd, socraticode, jcodemunch, serena, sqlite3, curl or wget.

  A flag is evidence for the coordinator to review and disclose, not a verdict. The audit is a heuristic
  lower bound: it reads only the command text. Known gaps include a path a program computes (a
  `python3 -c` that joins path parts, a glob, a variable set in an earlier command) and anything a command
  reads indirectly (a script's own reads, a config file it loads, a symlink under the repository).
- **Claude lane:** it has no equivalent audit in these tools. Its agents run Read, Glob and Grep only, but
  those have no path limit. A wave's coordinator audits the file paths in the lane's agent transcripts and
  discloses the result.

`--prompt` and `--schema` override the default `lane-prompt.md` /
`lane-return.schema.json` paths (both otherwise resolved next to
`codex_lane.py` itself); `--timeout` overrides the default 900-second
per-attempt `codex exec` timeout; `--jobs` runs that many packets
concurrently (default 1, sequential). `tests/test_codex_lane.py` never
invokes a real `codex` binary -- `tests/fixtures/codex-lane/bin/codex` is an
env-var-driven fake placed first on `PATH` that records its own argv,
optionally sleeps (timeout coverage), replays a canned event stream, exits
non-zero on chosen attempts (retry coverage), can exit 0 while skipping the
`-o` write or writing unparseable/non-object JSON to it on chosen attempts
(covers the "exit 0 but no usable output" retry path, distinct from a
non-zero exit or a timeout), and otherwise copies a canned return to
whatever `-o` path it was given; `tests/fixtures/codex-lane/` also
carries a fixture copy of the contract's verbatim prompt text and a minimal
fixture `lane-return.schema.json`, since the real ones (owned by the
`lane_packets.py` unit) are siblings, not inputs this unit reads.
A later fix made `trading[]` rows exactly the taxonomy layer ids (taxonomy
order, not the previous alphabetical `layers` order) and moved any review-lane
layer id outside the foundation/taxonomy baseline (e.g. a "beyond" lane's
`awesome-list-convergence` grouping) out of `trading[]` into a new
`lane_groupings` section, so `scripts/landscape.py`'s exact-coverage check no
longer sees an id outside the 12-layer taxonomy. This touches two different
datasets, kept separate here:

- The 16-foundation-layer private input behind the reproduction above has no
  non-taxonomy trading row, so its reproduced
  `(layer, repository, review_status)` identity set, `candidates_total` and
  the rest of `counts` are unaffected by the fix.
- The newer 2026-09-22, 20-foundation-layer, "beyond"-lane work-dir the fix
  actually targets (the private `layer-verdicts-20260922` work directory
  outside the repository) *was* rerun (`build_manifest.py --work-dir
  .../layer-verdicts-20260922 ...`, no `catalogs/` write): the pre-fix
  working-tree manifest at `catalogs/sota-convergence/manifest-20260922.json`
  (itself a pre-fix run against that same work-dir) has 15 trading rows
  (three of them the non-taxonomy `awesome-list-convergence`/
  `star-audit-targeted-candidates`/`unmaintained-reference-material` ids) and
  `candidates_total=18`; the post-fix rerun instead reports 12 trading rows,
  `candidates_total=16`, `lane_groupings=3` and `lane_grouping_candidates=2`
  -- the two candidates that moved out of `candidates_total` are exactly the
  ones the three non-taxonomy lane layers contributed. No selection, pin
  comparison or disposition changed; only where the non-taxonomy rows live in
  the manifest, and which count they are scoped to, changed.

## Two-family adjudication

`adjudicate.py` produces the adjudication records that `record_verdicts.py --adjudications` reads for layers
where the two lanes chose different winner components (2026-09-23 re-record).
- **The rule:** `scripts/landscape.py` `judge_adjudication` accepts a winner only when the judgments cover both
  lane families (anthropic and openai), each in both presentation orders, all pick the same lane, and none is
  refuted. Anything else is sealed as a split, and the row stays `pending_lanes` with an executed comparison
  named.
- **Blinding:** each judge and refuter is blind to which lane produced A or B, and reads only its input file,
  the packet and the blind export.

```sh
python3 tools/sota-convergence/adjudicate.py inputs --work-dir W \
  --lane-repo-root <claude lane export> --lane-repo-root <codex lane export>   # A/B and B/A inputs, index.json
python3 tools/sota-convergence/adjudicate.py codex --work-dir W --repo <blind export> --model <model>
python3 tools/sota-convergence/adjudicate.py claude-args --work-dir W --repo <blind export> > args.json
# run tools/sota-convergence/adjudication-lane.js with args.json (blind-lane-reviewer agents)
python3 tools/sota-convergence/adjudicate.py claude-collect --work-dir W --result <workflow result> --model <resolved>
python3 tools/sota-convergence/adjudicate.py assemble --work-dir W --out W/adjudications
```

- **`inputs`:** finds the disagreeing layers with `landscape.lane_winner_components`, the function CI uses. It
  writes each layer's two returns in both orders, scrubbed to the eleven verdict fields both lanes share.
  Lane, model, provenance and refutation fields are removed. Prose that names a lane is reported in
  `index.json` as `identity_mentions`, not removed.
  Every evidence-path list is reduced to sorted, deduplicated bare paths (round-2 review). This covers
  `sources_read`, `winner_evidence_refs`, every nested `evidence_refs` (`alternatives[]`,
  `challenger_preferred`) and `overturn_protocol.fixture_paths`. Each entry keeps its leading path token and
  any `#fragment`, loses a trailing `:line` reference and every note, and becomes repository-relative when it
  is absolute under a `--lane-repo-root`. In the 2026-09-22 sealed returns, 263 of 423 Claude `sources_read`
  entries carried notes such as "path (lines 60-104, prior round)", while all 558 Codex entries were bare
  paths, so the notes alone showed which lane wrote A.
- **`codex`:** runs one judge and one refuter per input through `codex exec` with `codex_lane.ISOLATION_ARGS`
  (no user config, hooks or web search) and the strict schemas `adjudication-judge.schema.json` and
  `adjudication-refute.schema.json`. It refuses a repository under any `.git`, retries once, resumes, and
  writes a blind audit. `--model` is required and must match the openai pattern in `scripts/landscape.py`
  `FAMILY_MODEL_PATTERNS` (exit 2 otherwise). It is passed to `codex exec -m` and recorded on each judgment
  ahead of the event-stream model name, the same order `codex_lane.py` uses. Resume skips a judgment only when
  it is usable and was made with this `--model`.
- **`adjudication-lane.js`:** the Claude family's judge and refuter, one pair per input. Both run as
  `blind-lane-reviewer` (Read, Glob and Grep; no skills or project instructions). `claude-collect` records
  its return; a lost judge or refuter makes that judgment missing, never unrefuted.
- **`assemble`:** writes one record per layer. `claude_position` follows the order, `refuting_votes` is 1 when
  the refuter refuted, and `judge` is `{model, family}`. `stripped_packet_sha256` is the layer's sealed lane
  packet. Each record is validated with `judge_adjudication` before it is written. A missing family gives a
  split record naming it. A judgment whose model does not match its family's pattern (for example
  `"unknown"`) does not count (`usable_judgment`), so a resumed run reruns it. Each written record carries a
  top-level `provenance`: `adjudicate_py_sha256`, `prompt_sha256` (`adjudication-prompt.md`),
  `judge_schema_sha256`, `refute_schema_sha256` and `workflow_sha256` (`adjudication-lane.js`).
  `judge_adjudication` and `record_verdicts.load_adjudication` ignore extra top-level keys, so the key needs
  no validator change. Nothing checks these hashes against a registry yet.

**Limits:**
- Writing style can still reveal a lane.
- The raw lane returns sit next to the adjudication inputs in the work directory
  (`<work-dir>/{claude,codex}/`, beside `<work-dir>/adjudication-inputs/`). A judge that reads outside its
  input file can read the unscrubbed returns, which name the lane, model and provenance. The Codex blind audit
  allows the inputs directory and the packets but not the lane directories, so such a read is flagged there.
- `provenance.prompt_sha256` is the default `adjudication-prompt.md`; a `codex --prompt` override is not
  recorded.
- One refuter per judgment, not two.
- The judge may read the packet outside the repository root, which it needs for the requirement and
  candidate keys.

**Receipt aliases.** `receipt-component-aliases.json` maps a `manifests/stack.json` component id (the id space
receipts name) to the sota manifest id for the same component where the spellings differ: `nautilus-trader`
to `nautilustrader`, and `duckdb`, `edgartools` and `exchange-calendars` to their `data-` ids.
- `lane_packets.py --registered-receipts` attaches such receipts with `matched_by: alias`.
- The index build fails when an alias's two ids do not share one repository.
- An explicit entry is required where one repository serves several manifest ids. nautechsystems/nautilus_trader
  is both `nautilustrader` and `nautilus-ibkr-adapter`, and a repository match cannot tell which component a
  receipt exercised.

