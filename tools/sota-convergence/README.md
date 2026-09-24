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
  `matched_by` is dropped as well, because `component_id` and `alias` exist only for a manifest component
  (review of #145). Paths and receipt contents are not stripped, and a receipt describing an adoption still
  says so.

A packet-level `registered_receipts_note` says how each entry matched, that a receipt may name several
components and that its `kind` is the registrant's label. The lane opens the receipt and judges what it ran
for this component.

Measured on the 2026-09-23 tree (round-2 review, rebuilt with
`lane_packets.py --root . --out <dir> --manifest catalogs/sota-convergence/manifest-20260923.json
--trading-candidates manifest --withhold-labels --registered-receipts`; since the round-4 review a blind build
also needs `--keys-out <file outside --out>` and no longer writes `matched_by`):
- 93 of 286 candidates carry at least one receipt.
- Candidate entries by `matched_by`: `component_id` 1028, `alias` 32, `repository` 0, after label-bearing receipts are left out.
- The alias entries: `data-edgartools` 14, `data-duckdb` 11, `nautilustrader` 6 and `data-exchange-calendars` 1.
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
carried. The flag is off by default.

**`--gap-receipts` is not blind; a blind wave must not pass it** (round-2 review). Each layer's list is the
set of checks run against the previous winner. Carrying only paths does not hide that:
- 111 of the 249 joined receipt files repeat the ledger gap text word for word, and 13 of them name the
  winner;
- file names such as `7-winner-readiness-today.json` and `0-nautilus-frozen-selections.json` name it too.

The flag and its code stay for non-blind runs, and `lane_packets.py` refuses it together with
`--withhold-labels` (exit 2, nothing written). `scripts/landscape.py` also lists `gap_receipts` and
`gap_receipts_note` in `TOP_LEVEL_WITHHELD_KEYS`, so `withheld_packet_keys` rejects a packet that carries
either. As a result, `record_verdicts.py --write` refuses to seal a new wave whose packets were built with
the flag, and CI rejects a sealed one. The grandfathered 2026-09-22 packets are not re-checked and do not
carry the keys.

**Limit: the blind export still carries the gap waves.** A lane that browses the repository can find the
same receipts without the flag. The export keeps `evidence/artifacts/gap-wave2-20260923/` and
`evidence/artifacts/gap-wave3-20260923/` (2,652 files) and the three owner ledgers
`catalogs/landscape/gap-wave*--*.json` (40 layer entries, 327 gaps, each with its gap text).
`catalogs/landscape/gap-resolution-20260922.json` and `gap-crosswalk-92bb279.json` also carry gap text.
`blind_checkout.py` strips only label keys from them, not gap text. A coordinator discloses this with the
wave.

**Manifest newcomers** (`--manifest-newcomers`, 2026-09-23 landscape sweep). Before this flag, only
manifest-mode trading packets carried the dated manifest's newcomer candidates. Foundation packets took their
candidates from the frozen v1 ledger, so a repository discovered after the ledger never reached a foundation
lane. With the flag:
- **Foundation packets gain newcomers.** Each takes its manifest row's `candidates` and
  `alternatives_keep_but_compare` whose repository is not already a candidate. They are shuffled together
  with the ledger candidates, so a key's position does not tell them apart.
- **Refuted discoveries are left out.** In both catalogs, a repository with a `refuted_*` disposition in any
  of its entries is left out, even where another list repeats it. The refutation is of the discovery
  proposal, not of the repository: the 2026-09-23 refutations of ledger repositories say "not new to the
  catalog" or "already conditional". So it withholds only a newcomer addition, never a ledger candidate.
- **Registered evidence is attached.** A newcomer's `evidence_refs` hold the repository-relative
  `evidence/` path each `evidence[]` entry leads with, when that path is listed in `manifests/evidence.json`
  `files[]` and still has its listed sha256. A locator after the path (`items[3]`, `(lines 1-9)`) is dropped.
  Command/result prose and an unregistered or edited file are not attached. The 2026-09-23 manifest names one
  such file; the landscape-sweep source-review receipts supply the rest. Under `--withhold-labels`, a path that names a selection role or a manifest disposition (for
  example `keep-but-compare`, `refuted`, `targeted-candidate` or `newcomer`) is not attached either; the same
  wider vocabulary applies to registered receipts.

The flag is off by default, so the 2026-09-22 packets reproduce. A non-GitHub https repository, such as a
Hugging Face model, is identified by its lowercased URL rather than dropped. With `manifest-20260923.json`, the
flag adds 35 foundation newcomers, 6 of them Hugging Face models, and removes 9 refuted trading newcomers
across the 32 blind packets (312 candidates).

A newcomer's name must not redact the packet's shared prose (Codex review of #151 at `cf82e689`). A name part
unique to one candidate is a redaction term, so granite-embedding's "embedding" had turned semantic-rag's
requirement "a compatible embedding service" into "a compatible <candidate> service". Capability and format words
seen in newcomer names (`embedding`, `embed`, `reranker`, `multilingual`, `bench`, `https`, `typescript`,
`parallel`, `orchestrator`, `group`, `brokerage` and their variants) are now generic name parts, as `retrieval` and
`memory` already were. A test builds the real 2026-09-24 packets and requires that newcomers add no placeholder
to any packet's requirement, limitations or overturn text. The same list restores "Brokerage model defaults ..."
in LEAN's own card limitation in execution-broker, the only default-build packet it changes.

A newcomer is never adopted, and the lane contract forbids a non-adopted winner
(`scripts/landscape.py lane_winner_components`). A lane can prefer one as its challenger
(`challenger_preferred`) with an overturn protocol. Promoting it takes the measured comparison that protocol
names.

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
and `upstream.renamed_to` of an unclaimed sota component stay; a candidate's pin and whole `upstream` record are
sealed out of a blind packet since round 4 (below). The default mode is byte-identical, so the retained
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
  [--adjudications /path/to/adjudications] [--lane-repo-root /path/to/state/blind/export] --write
python3 tools/sota-convergence/record_verdicts.py \
  --root . --work-dir /path/to/work-dir --run-id YYYYMMDD [--checked-at YYYY-MM-DD] \
  [--adjudications /path/to/adjudications] [--lane-repo-root /path/to/state/blind/export] --check
# --check needs the same --adjudications and --lane-repo-root the --write used.
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
  changes, append an entry (never edit one merged to `main`; one added inside
  an unmerged PR may be amended before merge, since the verdict-review gate
  fails a PR that changes this registry with a sealed verdict, so nothing
  sealed names it yet, and `scripts/landscape.py` fails CI on any sealed
  return an edit would orphan);
  `tests/test_verdict_lane_vendoring.py` fails until the current bytes are
  listed. `codex_lane.py` writes its provenance and the whole `model` field
  itself: `model.name` is the `--model` it passed to `codex exec -m`, else the
  model name the event stream carried, else `unknown` (never the model's own
  response text), `model.effort` is `--effort` and `model.family` is
  `"openai"`; the strict schema it passes to `codex exec` omits `provenance`
  and `model.family`. The
  vendored Claude workflow returns `model {name: "opus", effort: "max"}` (with its echoed `launch`, `prompt` and
  per-layer `packet_path`) and writes no files; `claude_lane.py` is the step that writes
  `<work-dir>/claude/<catalog>__<layer_id>.json` from the workflow result,
  adding `model.family: "anthropic"`, the resolved model name and
  `provenance`. It exits 2 when the agent-lab workflow file differs from that
  checkout's `HEAD` or from the vendored `SHA256SUMS` entry:

  ```sh
  python3 tools/sota-convergence/claude_lane.py --result /path/to/lane-result.json \
    --work-dir /path/to/work-dir --agentlab-root /path/to/agent-lab \
    --agent-file ~/.claude/agents/blind-lane-reviewer.md --repo /path/to/state/blind/export \
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

After recording, follow `recipes/sota-convergence-practice.md` step 7: it refreshes the component matrix, the
generated join and narrative (`build_verdicts.py --write` with `--manifest`, the dated manifest the wave's packets
were built from; without it a missing `manifest-<run-id>.json` is refused, round 7, OPR7-3) and the new-host grand
list, registers and rehashes what the wave changed, and runs the checks.

## Blind checkout

`blind_checkout.py` -- no network, no model call. Given `--source` (an
existing git checkout), `--rev` and a `--dest` that does not yet exist, it
runs `git worktree add --detach <dest> <rev>` and then mutates files only
inside `<dest>`, so a lane can review candidates without seeing what a
previous run (or the checked-in ledger) already chose.

```sh
python3 tools/sota-convergence/blind_checkout.py \
  --source . --rev HEAD --dest /path/to/state/blind/checkout --export /path/to/state/blind/export \
  --allow-from-packets /path/to/work-dir/packets
# ... run the blind lanes against /path/to/state/blind/export (no .git, no BLIND-MANIFEST.json) ...
git worktree remove --force /path/to/state/blind/checkout
# The export must be at least four directories deep (not /, /home, /tmp or a home directory itself) and outside
# every repository; blind_checkout, both lane runners and adjudicate refuse otherwise.
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
`catalogs/`, `adoption/` and `blueprints/` (below) and the instruction files. Since round 6 it rewrites no
sentence of an exported file: Markdown, text and JSON prose are exported verbatim, and the exposure is disclosed
per layer (round 6, below). Measured on the allowlisted 2026-09-23 export (633 files; 611 byte-identical to the
source) at round 7, it still carries:
- **Choice prose.** Counting only statements that tell a layer's winners apart from its adopted non-winners
  (round 7, BL7-1), 13 cited prose files expose 18 of the 30 scored layers (`prose_exposed_layers`), and across
  the whole export, which a lane may also search, 28 of the 30 are reachable (`prose_reachable_layers`). Since
  the Codex review of 68e74f2c (P1) the measure also reads JSON and JSON Lines string values (a receipt's
  `claim` named a git-github-automation winner among "selected components"). On a 2026-09-24 export of this
  branch (639 files, 429 of them JSON) that raises the cited count to 19 files exposing 21 of the 30 layers
  (git-github-automation, portfolio-risk and research-factors-ml added); 28 of 30 stay reachable, through 29
  files instead of 20.
  execution-broker and observability-hosting are not scored: their recorded winners are not among their adopted
  candidates. `record_verdicts.py --write` seals each wave's own measure as `prose-exposure.json` and stamps
  every row's `lanes.prose_exposed` (round 7, BL7-2).
- **Label-stripped files.** 22 exported JSON files differ from the source only by stripped label keys. Five of
  them have their original sha256 recorded in another exported file, so that hash no longer matches in the
  export: `CLAUDE.md` (replaced, in `catalog-clean-install-20260921/source-manifest.json`),
  `blueprints/convergence-practice/offhost-restore/upstream-source.json` (in `upstream-tests.json` and
  `hosted-plan.json`), `blueprints/us-equities/adaptive-paper/receipt.json` (in two trials' `frozen-*.SHA256SUMS`),
  `catalogs/foundation/community-practice-20260920.json` (in `native-review.json`) and
  `evidence/artifacts/claude-upstream-checks-20260921/provenance.json` (in its receipt).
- **Evidence prose in JSON.** String values are not redacted. 206 sentences in 102 JSON files name a winner (its
  name, repository name or component id) with a selection word: 154 under `evidence/`, 35 under `blueprints/`,
  13 under `catalogs/`, 3 under `observability/` and 1 under `adoption/`. Most use the words in their technical
  sense ("selected-step retry", "retained checkpoint").
- **Prior evidence artifacts.** JSON under `evidence/artifacts/` that a packet cites is kept, because packets
  cite prior artifacts as evidence; earlier verdict fields are stripped from it. In the export, "selected"
  (case-insensitive) occurs 387 times in 58 of those JSON files across 20 directories.
- **Instruction files outside the export.** The export cannot neutralize instructions a client loads from
  elsewhere: a parent directory's `AGENTS.md` or `CLAUDE.md` and the user-level files. Blind Codex children run
  with a run-scoped `CODEX_HOME` and an empty `HOME` (below), so `~/.codex/AGENTS.md` and `~/.agents/skills` do
  not load for them; a non-blind `codex_lane --allow-git-history` run inherits the native home. The Claude
  lane's `blind-lane-reviewer` agents run with `omitClaudeMd`.

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
  -c 'web_search="disabled"' -c 'cli_auth_credentials_store="file"' <filled prompt>
```

The five isolation settings on the last two lines are `ISOLATION_ARGS`; `tests/test_codex_lane.py` fails when
this block or the module docstring leaves one out. A blind child runs this with only an allowlisted environment,
a fresh run-scoped `CODEX_HOME`, an empty `HOME` and no stdin (below).

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
- **Global instructions and user skills:** blind runs (`codex_lane` without `--allow-git-history`, `adjudicate
  codex`) run each child with a run-scoped `CODEX_HOME` and an empty `HOME`, so neither `$CODEX_HOME/AGENTS.md`
  nor `~/.agents/skills` loads (probe-measured, round 4). A non-blind `--allow-git-history` run inherits the
  native home and both.
- **Git history:** `codex_lane.py` refuses a `--repo` when it or any parent directory has `.git`, because git
  walks up from a subdirectory. Pass `--allow-git-history` only outside a blind wave. Run the lanes on a
  `blind_checkout.py --export` copy placed outside every repository.
- **Blind audit:** `codex_lane.py` audits each layer's events as soon as its child finishes and records the
  result in `<work-dir>/codex/blind-audit.json`. In a blind run a flagged layer is void before its return is
  written (kept only as `<name>.json.audit-flagged`), and a resume re-audits a kept return's events, rerunning it
  when they are missing or flagged (round 7, REG7-1). The audit counts web searches and MCP tool calls, and flags
  commands that do any of the following:
  - name an absolute path outside the repository and the packets directory. A `/` right after `)` or `]`
    (Python's `Path.cwd()/ref`) starts no path, and neither does a URL's `//` authority (`https://host`,
    `ssh://`, `qmd://`, `s3://`), though `file://`, `jar:file://`, `local://`, any `unix` scheme (`http+unix://%2F...`)
    and `https:///` do. A URL reaches nothing from a blind child without the network or a CLI it cannot resolve.
    Measured the same day, a blind child could create an AF_UNIX socket, but its `connect()` to a probe-owned
    socket that the caller had just reached failed with `PermissionError: [Errno 1] Operation not permitted`. So
    local sockets (the peer sessions' `/run/user/<uid>/cc-socks`) are closed to it too. Measured
    2026-09-24 (codex-cli 0.155.1, `--sandbox read-only`), its Python connection to a local listener the caller
    had just reached, and to 127.0.0.1:6333 (Qdrant's port), failed with `PermissionError: [Errno 1] Operation
    not permitted`, and the listener accepted nothing. The root rule skips a quoted `'/'` joined with `+` between
    two non-literal operands (`p+'/'+k`), but not `'/'+'etc/passwd'` or `''+'/'+x`. Only `/dev/null` and a
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
  - name git, sqlite3, curl or wget anywhere in the command, or any audited CLI by an absolute path outside the
    repository and packets (`/usr/local/bin/qmd`, which is otherwise an exempt system executable token).
  - **PATH enforcement.** A blind child's PATH resolves none of ai-memory, agentsview, mcporter, qmd, socraticode,
    jcodemunch, serena, codex or claude:
    - `child_env` sets PATH to the system directories (`/usr/bin:/bin:/usr/sbin:/sbin`);
    - codex runs by the absolute path the caller's PATH resolves, and an npm `#!/usr/bin/env node` launcher runs with
      the interpreter the caller's PATH resolves;
    - `blind_path_issue` refuses a blind run (codex_lane and adjudicate codex, exit 2) when any of them resolves on
      any PATH a child's command can end up with. That is measured each run after a sentinel: the login shell's
      (Codex runs commands with `bash -lc`; /etc/profile.d adds `/snap/bin` here, and macOS path_helper adds
      /etc/paths), the default a shell sets when a command drops PATH (`/usr/local/bin` included), and
      `os.defpath`.

    **New hosts.** A host that installs one of them where a child's PATH reaches it is refused, and the refusal
    names each directory. For example, Intel Homebrew or npm globals put them in `/usr/local/bin`, which macOS
    path_helper and a PATH-less shell both add. On a Mac, zsh started with an empty environment takes HOME from
    passwd and reads the real `~/.zshenv`, so a Homebrew PATH set there counts too. The refusal is correct, since a
    child's `zsh -c` would get the same PATH, but zsh, fish, ksh and tcsh are untested here. Install the CLIs
    elsewhere (`~/.local/bin`) to run blind lanes there. A shell-script codex launcher (pnpm's cmd-shim, which runs
    node by name, or asdf's `#!/usr/bin/env bash` shims) is refused up front, and a failed child's last stderr lines go to the console, not the record.
    A probe that fails is named in the refusal (`PathUnmeasured`), and non-UTF-8 profile output is read leniently
    (R2-4). The unit suites pin the measured PATH, so they do not depend on the host's (R2-3).

    So their names alone are not flagged in a blind run, since they are also candidates a lane must search for; a
    non-blind run still flags them. Measured 2026-09-24 with a real blind child: every one of them, and node, npx
    and uvx, was missing, while python3, git and Codex's bundled rg resolved.
  - in the text a shell expands (a `sh -c` script with its single-quoted spans removed, so a search for a
    literal backtick is not flagged): a command substitution, `${...}` with an operator, `CODEX_HOME` (the bare
    name too), or an inherited directory variable such as `${TMPDIR}` or `$SSL_CERT_DIR`.

  In a non-blind run a flag is evidence for the coordinator to review and disclose. The audit is a heuristic
  lower bound: it reads only the command text. Known gaps include a path a program computes (a
  `python3 -c` that joins path parts, a glob, a variable set in an earlier command) and anything a command
  reads indirectly (a script's own reads, a config file it loads, a symlink under the repository).
- **Claude family (lane and adjudication):** its agents run Read, Glob and Grep only, and those have no path
  limit, so `transcript_audit.py` audits what they opened in the workflow run's transcripts, which Claude Code
  keeps at `~/.claude/projects/<export slug>/<session>/subagents/workflows/<run id>/agent-*.jsonl` (`transcript_audit.py
  locate` finds the one run of a session). The audit is bound to that run: its record
  (`<session>/workflows/<run id>.json`) must be completed, list each agent's final attempt (whose transcript must
  be present) and hold the very result being collected; any other transcript must be an earlier attempt of a
  retried agent's item (at most attempt − 1 per item), audited against that item's boundary; every agent must
  have run from the export; the recorded digest
  covers the transcripts and the record. Each agent is mapped to the item its prompt names: a lane packet's path,
  or an adjudication input's "Input file:" line. Its reads, compared as resolved paths, must stay under the export
  and that item's packet (and input), and it may use no other tool, server-side and MCP tools included. An
  unreadable transcript line, a relative path without a working directory, a glob that climbs with `..` or an
  agent naming several items flags too. `claude_lane.py --transcripts` voids a flagged layer (kept as
  `.audit-flagged`, recorded as failed). `adjudicate.py claude-collect --transcripts` voids a flagged judgment,
  and records the transcripts' digest with `audit_clean`; `usable_judgment` re-audits them, so an edited record
  does not count. An item no agent served, or a flagged agent that names no item, flags every item. Like the Codex
  audit, this is a lower bound: it sees the paths the tool calls name.

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
python3 tools/sota-convergence/adjudicate.py inputs --work-dir W --lane-repo-root <blind export> \
  --packet-keys <keys>/packet-keys.json   # AB and BA inputs, adjudication-index.json
python3 tools/sota-convergence/adjudicate.py codex --work-dir W --repo <blind export> --model <model>
python3 tools/sota-convergence/adjudicate.py claude-args --work-dir W --repo <blind export> --run-dir <blind export> > args.json
# run tools/sota-convergence/adjudication-lane.js with args.json (blind-adjudicator agents)
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
  - **Host paths (adjudication round 3).** The blind-adjudicator role and `adjudication-prompt.md` count an
    absolute host path outside the repository root as a leak, and both lanes record such paths (the packet's
    absolute path in `sources_read`, for one). So every string in both returns, prose included, is scrubbed:
    - a path under `<work-dir>/packets/` becomes `PACKET`;
    - a path under a `--lane-repo-root` becomes repository-relative;
    - any other absolute path, `~` or `$HOME` path, or `<host-path>` placeholder becomes
      the bare `<outside-path>`: a kept basename could name a lane (a worktree folder, or a file only one lane's client reads).

    http(s) URLs are left alone. `--lane-repo-root` is required and repeatable.
  - **No packet path in an input.** An input is `{layer, packet_sha256, A, B}`. The judge's labelled
    `Packet file:` line carries the packet path, which `claude-args` and `codex` take from `adjudication-index.json`.
  - **Refusal on a surviving path.** If an absolute path, a `~` path, `$HOME` or `${HOME}`, or a `<host-path>`
    placeholder still remains after scrubbing, `inputs` writes no input for that layer and removes a stale
    one. It lists the offenders in `index.json` `skipped[].unscrubbed` and exits 1, so a known leak is never
    sent to a judge.
- **`codex`:** runs one judge and one refuter per input through `codex exec` with `codex_lane.ISOLATION_ARGS`
  (no user config, hooks or web search) and the strict schemas `adjudication-judge.schema.json` and
  `adjudication-refute.schema.json`. It refuses a repository under any `.git`, retries once, resumes, and
  writes a blind audit. `--model` is required and must match the openai pattern in `scripts/landscape.py`
  `FAMILY_MODEL_PATTERNS` (exit 2 otherwise). It is passed to `codex exec -m` and recorded on each judgment
  ahead of the event-stream model name, the same order `codex_lane.py` uses. Resume skips a judgment only when
  it is usable and was made with this `--model`.
- **`adjudication-lane.js`:** the Claude family's judge and refuter, one pair per input. Both run as the
  `blind-adjudicator` role, vendored from agent-lab e070125 as `examples/claude-native/agents/blind-adjudicator.md`
  and installed user-level by the recipe's step-3 copy of `adoption/agents/claude/blind-adjudicator.md`.
  `claude-collect` records its return; a lost judge or refuter makes that judgment missing, never unrefuted.
- **Prompt and leak check (both families, round-2 review):**
  - Every judge and refuter task starts with three labelled lines: `Input file: <path>`, `Packet file: <path>`
    and `Repository root: <path>`. `adjudication-prompt.md` refers only to them and treats any other path as
    data. `claude-args` gives each item its `packet_path` from `adjudication-index.json`.
  - The judge and the refuter first check their input for reviewer identity: a lane, model, provenance or
    refutation key; a model name such as gpt-, o3, opus, sonnet, haiku or claude-opus; wording that
    attributes a return; or a host path outside the repository root. A candidate that shares a vendor name
    is not a leak.
  - On a leak they return `leak: true` with `leak_text` and stop. Both `adjudication-judge.schema.json` and
    `adjudication-refute.schema.json` require `leak` and `leak_text`, because Codex strict mode requires
    every property.
  - `adjudicate.py` records a leak as a missing judgment with failure `leak`, never as a judgment or a vote.
    A Codex leak is not retried, and a judge leak skips the refuter.
  - **Leaks are sticky per input content (adjudication round 3).** `codex` and `claude-collect` append each
    leak to `adjudication-judgments/<family>/leaks.json` and never overwrite or remove a record. A record is
    keyed by the input file name and that input's sha256, and lists both of the layer's input files. While
    an input's current sha256 has a leak record from either family:
    - `usable_judgment` returns `leak` for any judgment of it, whatever the judgment file says;
    - `codex` does not rerun it;
    - `claude-args` leaves it out (listed under `leaked`);
    - `claude-collect` records any returned judgment for it as `leak`.

    It clears only when `inputs` rebuilds the file and its sha256 changes.
  - **Leaked layers get no record.** `assemble` drops every judgment of a leaked input from both families.
    The remaining judgments cannot cover both presentation orders, which `judge_adjudication` requires, so
    no record is written. The layer is reported as a split, with its reason, in
    `<work-dir>/adjudication-leaks.json` (`split_layers`, next to every leak record of both families), and
    `assemble` exits 1. Without an adjudication record, a disagreeing row stays `pending_lanes`. The report is
    not written into `--out`, which `record_verdicts.py` reads.
- **Repository-root rule (adjudication round 3).** `blind-adjudicator` refuses a repository root that is
  `/`, `/home`, a home directory (`/home/<name>`, `/Users/<name>`, `/root` or the current user's), `/tmp`, a
  path with fewer than four components, or a path with a `.` or `..` segment, `~`, `$` or a wildcard. It also
  refuses an input or packet file inside the root. `inputs` (each `--lane-repo-root`), `claude-args` and
  `codex` (`--repo`) apply the same rule first and exit 2 with the reason, so the Claude family never refuses
  alone while the Codex family judges. `claude-args` and `codex` also refuse a work dir inside `--repo`.
- **`assemble`:** writes one record per layer. `claude_position` is the position the input contents show for
  the Claude return (checked against the index's per-layer map), `refuting_votes` is 1 when
  the refuter refuted, and `judge` is `{model, family}`. `stripped_packet_sha256` is the layer's sealed lane
  packet. Each record is validated with `judge_adjudication` before it is written. A missing family gives a
  split record naming it. A judgment whose model does not match its family's pattern (for example
  `"unknown"`) does not count (`usable_judgment`), so a resumed run reruns it. Each written record carries a
  top-level `provenance`: `adjudicate_py_sha256`, `prompt_sha256` (`adjudication-prompt.md`),
  `judge_schema_sha256`, `refute_schema_sha256` and `workflow_sha256` (`adjudication-lane.js`).
  `judge_adjudication` and `record_verdicts.load_adjudication` ignore extra top-level keys, so the key needs
  no validator change. Nothing checks these hashes against a registry yet.

**Binding.**
- **Input content:** every judgment records the `input_sha256` of the input it judged. A resumed or
  assembled judgment counts only while the input file still has that hash, so rebuilding an input after a
  lane return changed invalidates its old judgments.
- **Claude inputs:** `claude-args` snapshots each item's input hash, and `claude-collect` refuses a judgment
  whose input changed after that snapshot.
- **Stale records:** `assemble` deletes a layer's earlier record in `--out` whenever the layer is refused,
  for a leak or for validation, so `record_verdicts.py --adjudications` never reads a stale winner.
- **Paths:** a repository root or work dir containing whitespace is refused, because path scrubbing
  tokenizes on whitespace.
- **Resume:** a Codex judgment is reused only at the same `--model` and `--effort`. The Claude family's
  effort is fixed at `max` by `adjudication-lane.js` (`CLAUDE_LANE_EFFORT` in `adjudicate.py`).
- **Snapshot scope:** `claude-collect` touches only the items in the `claude-args` snapshot. It discards a
  leak reported on an input rebuilt since that snapshot, so the stale leak cannot mark the new content.
- **Assembly:** `assemble` first removes the earlier record of every layer `inputs` indexed or skipped.
- **Missing returns:** a layer with a missing lane return is recorded as skipped, so its earlier record is
  purged too.
- **Provenance:** judgments carry the adjudication provenance captured when they ran: at the Codex run's
  launch, or in the `claude-args` snapshot. `assemble` refuses a layer whose counted judgments ran under
  different provenance.
- **Codex leaks:** a Codex leak is bound to the input content hashed before the call.
- **Paths:** roots and work dirs are limited to `[A-Za-z0-9._/-]`. Backticks are path delimiters, and the
  residual check does not depend on the replacement boundary.
- **Claude lane role:** its provenance includes `agent_sha256`, the hash of the `blind-lane-reviewer`
  definition it loaded. `claude_lane.py` refuses a definition other than the vendored
  `examples/claude-native/agents/blind-lane-reviewer.md`, and `lane-provenance.json` registers the hash.
- **`codex_lane` resume:** a lane return is reused only at the same `--model` and `--effort`.
- **Lane role file:** `claude_lane.py` requires `--agent-file`, naming the `blind-lane-reviewer` definition
  the lane actually loaded. It refuses when a differing project-level copy exists under `--agentlab-root`.
- **Adjudicator role:** adjudication provenance includes `adjudicator_role_sha256`, the hash of the vendored
  `blind-adjudicator.md`. `claude-args --agent-file`, which defaults to the user-level copy, refuses an
  installed role other than the vendored one.
- **`..` paths:** paths are normalized before relativizing, so `<root>/../codex/x` becomes `<outside-path>`.
  A `../` token in prose is scrubbed, or refused by the residual check.
- **Label-bearing receipts:** under `--withhold-labels`, a registered receipt whose id or path names a
  selection role (default, adopt, select, winner, incumbent, chosen, retain) is left out of the packet,
  and the packet's `withheld` list says so. Examples are `native-session-defaults-20260920` and
  `adoption/receipt.json`.
- **Schema:** `lane-return.schema.json` includes `provenance.agent_sha256`.
- **Prompt and evidence binding:** adjudication provenance hashes the prompt actually used, including a
  `codex --prompt` override, and `repo_tree_sha256`, a digest of every file in the evidence export.
  A resumed Codex judgment must match the run's provenance, and a layer is assembled only when every
  counted judgment carries the same provenance.
- **Symlinks:** `blind_checkout --export` removes any symlink that is absolute or resolves outside the
  export, and reports it. The tree digest includes each kept link's text, so retargeting a link changes it.
- **Snapshot binding:** `claude-args` gives each run a `snapshot_id`, which `adjudication-lane.js` echoes.
  `claude-collect` refuses a result from another snapshot.
- **Stale packets:** `claude-args` and `codex` refuse a packet whose bytes changed after `inputs`.
- **Leaks cover both orders:** the AB and BA inputs hold the same two returns, so a leak recorded for one
  order suppresses both.
- **Git-backed roots:** `claude-args` also refuses a repository under any `.git`, as `codex` does.
- **Packet snapshots (round 8):** judges never read the live packet. `inputs` copies each indexed packet to
  `<work-dir>/adjudication-packets/<sha256>/packets/<name>.json`, and `index.json` names that copy.
  `codex` rechecks the copy after each call and voids the judgment ("the packet snapshot changed during the
  call") if it changed. `claude-collect` records a judgment as missing when the copy no longer matches.
- **Selective rebuilds (round 8):** `inputs --layers` keeps every other layer's earlier index entry, so
  `assemble` still purges or rebuilds their records. A selected layer whose packet is gone is listed as
  skipped ("the packet is missing"), so its old record is purged.
- **Exact lane provenance (round 8):** `codex_lane` resumes a return only when its `provenance` equals the
  current one exactly; an extra or changed field reruns the layer.
- **Evidence-tree binding (round 9):** both lanes' provenance names `repo_tree_sha256`, the
  `codex_lane.tree_sha256` digest of the export they read (every file's path and sha256, and each kept
  symlink's text); `scripts/landscape.py` requires it on new-wave returns.
  - `codex_lane` hashes the tree at launch and again after its calls. If the tree changed, it sets that run's
    returns aside as `<name>.json.tree-changed`, and a resume against another export reruns.
  - `claude_lane.py` needs `--repo`. The workflow echoes the caller's `args.launch` (vendored bytes from
    agent-lab #42), and the script refuses (exit 2) unless that launch is `{repo, repo_tree_sha256,
    agent_sha256}` naming `--repo`, the tree's current digest and the vendored role (rounds 10 and 12).
  - `adjudicate codex` recomputes its provenance after the calls and voids that run's judgments when it
    changed. `claude-collect` recomputes it from the `claude-args` snapshot, which now records `prompt_path`
    and `repo`.
- **Bindings added in round 10:**
  - `claude-collect` uses the repository the `claude-args` snapshot validated. A `--repo` override or a
    returned `repo` must name it exactly.
  - Each Codex worker rechecks the indexed input hash when it starts and after its calls.
  - `inputs` records each lane return file's sha256. `assemble` refuses a layer whose lane return changed
    since then, and writes `lane_returns_sha256` into the record; `record_verdicts.py` refuses a new-wave
    adjudication whose `lane_returns_sha256` does not name the lane returns it seals.
  - Leak records keep input basenames only.
- **Independent review of #145 (four Opus lenses: blindness, binding, regressions, operability):**
  - **Family position is a secret (F3).** `inputs` draws, per layer, which position (A or B) shows the Claude
    return in `AB`, and `BA` shows the complement. The map is kept only in the adjudication index (outside the
    work dir since the a2434e2e review; see below),
    outside `adjudication-inputs/`. Each Codex judge call's audit allows only the repository, its own input file
    and its packet snapshot.
  - **Judgments are bound to this index (M3).** A judgment counts only when its layer, input path and input
    sha256 are the index entry's.
  - **`claude-args --run-dir` is required (M4),** so the project-level role in the directory the workflow runs
    from is always checked. In the blind flow this is the export root.
  - **Prompt binding for the Claude lane (M1).** The layer-verdict workflow (agent-lab #45; vendored here as #47's
    merge e070125, sha256 fd77b749, which adds the per-layer packet path) refuses a real run
    without `args.prompt` and echoes it. `claude_lane.py` requires the echoed prompt to be this catalog's
    `lane-prompt.md` and records `prompt_sha256`, which `scripts/landscape.py` now requires and the registry keys.
  - **Adjudication code is registered (M2).** `lane-provenance.json` has an `adjudication` list. A new-wave
    adjudication must name registered code, the lanes' one evidence tree, and `lane_returns_sha256` equal to the
    row's sealed `lanes.<lane>.sealed_sha256` (the sealed form, so CI recomputes it). `record_verdicts.py` and
    `scripts/landscape.py` both check this, and CI also requires both sealed lane returns to name one tree.
  - **UTF-8 only (L2).** Lane returns are decoded as UTF-8 before parsing, so a BOM or UTF-16/32 is refused.
  - **Allowlisted export (F1, F2).** `blind_checkout.py --export … --allow-from-packets <work-dir>/packets` exports
    only the following, and nothing else:
    - the paths the lane packets reference (evidence refs and registered receipts; since round 4 a blind packet
      carries no recipe ref, which is sealed, so a file cited only as a recipe_ref leaves the export; directories
      recursively);
    - one level of `evidence/` and `blueprints/` paths named inside those JSON files;
    - the root instruction stubs.

    Files that name every layer's winners are removed even when referenced (component-evidence-matrix,
    new-host-grand-list, blind-convergence, the sota-convergence manifests and SDK coverage), and non-empty
    winner or incumbent keys are stripped under `catalogs/`. Ledger candidates are sorted by (repository, name):
    the checked-in order listed the incumbent first on every row. Every exported path gets mtime 0.

    On the 2026-09-23 packets the export holds 633 files at this head (604 after the round-4 removals below, 660
    after sealing recipe_ref dropped six recipe-only files, 666 before them, 902
    with the tests/, tools/ and scripts/ trees, 697 before the role-label removal). Before the allowlist it held the
    whole repository.

    **Role labels removed (final-round blindness review).** A per-layer subtraction check
    (`tools/sota-convergence/export_isolation_check.py`, adapted from the reviewer's script) tests every
    repository list in the export: does it isolate a layer's winner set among the layer's adopted candidates,
    either by naming it alone or by leaving it over? The export therefore:
    - removes membership lists and earlier verdict records: `manifests/stack.json`, the upstream snapshot,
      star audit, automation interfaces and saturation audit, and the 2026-09-21 repository-evidence,
      blind-catalog-convergence, upstream-check and full-stack coverage records;
    - strips role keys under `catalogs/` and `adoption/`: since round 4 an explicit list (`selected_path`,
      `selected_skills`, `default_profile`, `retained_comparison_engine`, ...) plus `challenger*`, `rationale`,
      `disposition`, `why_not_default` and the like, never an object that records an observed run
      (`observed_at`, `exit_code`, `sha256`); the earlier `selected_*`/`retained*`/`coordinator_*` prefixes also
      removed retrieval data and exercised checks (round 4, R4-REG-1);
    - strips earlier verdict fields (`sota_verdict`, `primary_stack`, `strongest_challengers`, ...) under
      `evidence/`.

    `tests/test_blind_checkout.py::RealExportIsolationTests` rebuilds the real export and fails on any isolating
    container that is not evidence. Since round 4 the check is id-aware (below). The isolating containers that
    remain sit in evidence records (receipts, experiments, `evidence/` artifacts) or under evidence keys in 13
    layers: evidence-volume asymmetry, since what was exercised is cited, which is evidence, not a label.

    **Prose in cited files.** A packet's evidence references name `docs/`, `catalogs/`, `recipes/` and `adoption/`
    files whose prose called the current choice "selected" or "retain". This round's review measured 10 of 32
    layers; round 4 found the disclosure understated (F3), and the round-4 export redacts such sentences (below).

    **Codex global instructions.** `--ignore-user-config` skips `config.toml` but not `$CODEX_HOME/AGENTS.md`.
    This host's global Codex instructions name nine catalog components (serena, jcodemunch, rtk, qmd, headroom,
    beads, typesafe, zizmor, mcporter). So every blind Codex child, in `codex_lane` without `--allow-git-history`
    and in `adjudicate codex`, runs with a run-scoped `CODEX_HOME` (since round 4 outside the work dir, see below).
    That home, mode 0700, starts with only a symlink to the native `auth.json` (never a copy), an empty `home/` and
    an empty `tmp/`. After a run it also holds what the child wrote (state and log databases, a models cache, the
    bundled skills under `skills/.system`, `plugins/`, `cache/`); it is kept for inspection, with the link removed.
    Measured 2026-09-24: a probe child without it quoted its `# AGENTS.md instructions` block, and with it answered
    "none".

    **Disclosed trade-off (re-review L3):** `lane-prompt.md` and the vendored lane's evidence lens still accept an
    `overturn_when` naming a `tests/` path or a runnable command, and neither `tests/` nor `tools/` is exported
    unless a packet references it. So a lane that cites such a path can be refuted as naming a missing file (9 of
    the 30 current `verdict_overturn_when` rows cite `tests.` commands). The re-record measures how many
    refutations cite a missing tests/ or tools/ path. Rewording the prompt and lens waits for their next
    registered revision, because both are hash-bound.
- **Codex review at 2a2ffb8d:**
  - **Packet prose.** Under `--withhold-labels`, `requirement`, `limitations` and `existing_overturn_when` keep only
    sentences that name no packet candidate and use no selection word. Candidate names count as their name and
    repository name plus distinctive parts, so "NautilusTrader" also matches "Nautilus". A requirement left empty
    becomes a neutral pointer to the layer title and `layer_scope_terms`. The shared ledger prose named the
    incumbent ("Use the selected NautilusTrader destination…"). On the 2026-09-23 packets, none of the 32 keeps
    such a sentence, and 13 requirements are fully withheld.
  - **Codex home.** The run-scoped Codex home is recreated on every blind run, so a leftover `AGENTS.md` is never
    loaded. A dry run creates none.
  - **Claude lane accounting.** `claude_lane.py` accounts for every work-dir packet. One in neither `layers` nor
    `lost` loses any earlier return and is listed as a failure.
  - **Scrubbing.** A URL ends at `;` or `,`, and a path segment glued to a delimiter ("/home/example,private/y") is
    absorbed with its path.
- **The first 2026-09-24 re-record attempt (wave 20260924 at catalog 149940af), set aside:**
  - **The Codex lane voided 15 of 32 layers with no read outside the export.** The reasons:
    - 15 flags named a retrieval CLI that was only a search term or a Python list item (`rg -i 'qmd|...'`,
      `for t in ['serena', ...]`);
    - 8 were a quoted `'/'` joining path parts (`p+'/'+k`);
    - 2 were `Path.cwd()/ref` and `'https://'` read as absolute paths;
    - 1 was a backtick in a quoted heredoc (REG7-3, kept).
  - **The fix is enforcement rather than a name heuristic** (the blind audit above). A blind child's PATH resolves
    no retrieval CLI, which a real child confirmed, and a host where one would resolve is refused. So those names are
    no longer flagged. The root and path rules skip the Python forms.
  - **Replayed over that run's 420 commands, 1 of the 32 layers is still flagged** (the backtick). The same replay
    over the `test_real_reaches_still_flag` cases still flags each.
  - **The Claude lane was killed 20 minutes in.** `claude -p` ended its background workflow 600 s after its turn
    ended. The recipe now sets `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0`.
  - **Review of the fix (#206):** Codex and the independent review found gaps, each fixed with a test that fails without it:
    - an npm `#!/usr/bin/env node` launcher could not start under the child's PATH;
    - a CLI named by an absolute system path was exempt;
    - `file:///` passed as a URL;
    - a `'/'` joined on one side only built `/etc/passwd`;
    - a command dropping PATH got the shell's default, with `/usr/local/bin`;
    - profile output could reach the measured PATH.
  - **Nothing from the attempt is recorded:** codex_lane.py's hash changed, so both lanes rerun on a new wave.
- **Independent round-11 review of ca89c0d8 (audit normalization, registry and regressions), and its fixes:**
  - **A padded component inside a pattern (NORM11-1, medium).** Glob takes an absolute pattern's base (the text
    before its first `*?[{`, cut at the last `/`) through the same trimming path helper, so `<export>/.. /*` listed
    the export's parent while the whole value, starting with `/` and ending with `*`, was unchanged by `trim()` and
    its `.. ` part was not `..`. Any `/`-separated component `trim()` would change now flags, in every Read path
    and Glob or Grep path, pattern and glob. The review found no such component among 28,601 values in 289 real
    workflow runs on this host. File-name listings only were exposed; contents stayed closed.
  - **Each trimmed character is pinned (NORM11-2).** A test lists the 25 ECMA-262 code points independently and
    requires each to flag, and three that `trim()` keeps (U+200B, U+200D, U+0085) not to; 18 of 18 targeted mutants
    are killed.
  - **Registry guards (RR11-1, RR11-2).** The registration test requires the current audit hash for both workflow
    paths the lane may name, and the adjudication test requires every registered adjudication key. The Claude
    uniqueness key includes `transcript_audit_py_sha256`, and adjudication entries are unique too, so an appended
    registration that changes only the audit is accepted.
  - **Adjudication code at record time (RR11-3).** A new-wave adjudication's provenance must hash to this
    checkout's adjudication code (`record_verdicts.ADJUDICATION_FILES`, which a test pins to exactly what
    `adjudicate.adjudication_provenance` hashes), as the Codex and Claude lanes' code must.
  - **Registry edits (the local Codex review's P2).** Entries added inside an unmerged PR may be amended before
    merge; the append-only rule above binds entries merged to `main`. Catalog issue #175 tracks enforcing it in CI.
- **Independent round-10 review of 821c23cc (transcript audit and its binding), and its fixes:**
  - **Whitespace around a path (TA10-1 = BR10-1, high).** Claude Code trims a Read, Glob or Grep path with
    JavaScript's `trim()` before expanding a leading `~`, while the transcript keeps the raw value; " ~/.codex"
    or "<export>/.. " audited clean and opened a path outside the export. A path, pattern or glob that `trim()`
    would change (the ECMA-262 WhiteSpace and LineTerminator set) flags, before the `~` and `$` test; since round
    11 (below) the test applies to each `/`-separated component, not only the whole value.
  - **Mutation coverage (TA10-4).** Tests now cover each whitespace class, a bare `~` and `~user`, a mid-value
    `$`, every per-item retry case and `locate`'s fallbacks; 13 of 13 targeted mutants are killed.
  - **`locate` on a long project name (TA10-2)** treats an unreadable exact path (ENAMETOOLONG) as absent and falls
    back to the session's unique id. **Record entries without an `agentId` (TA10-3)** are ignored, and a missing
    agent list sorts safely.
  - **Registration guard (TA10-5 = BR10-2).** A test requires the current `transcript_audit.py` hash in the
    registry's current Claude entries, so an audit change cannot pass CI unregistered. **Record time (BR10-3)**
    also requires a new-wave Claude return's `transcript_audit_py_sha256` to be this checkout's
    `transcript_audit.py`, as the Codex lane's code is; `claude_lane.py` itself stays unbound (disclosed low).
  - **Return schema (BR10-4).** `lane-return.schema.json`'s provenance lists `transcript_audit_py_sha256`, and a
    test requires every lane's registered provenance fields to be in it. Nothing validated provenance against the
    schema, so no return was rejected: `codex_lane.py` drops the runner-owned provenance from the copy it passes to
    `codex exec --output-schema`, and record time checks provenance keys against the lane's provenance fields.
- **Independent round-9 review of 014d046f (transcript audit, binding and resume, regressions and operability):**
  - **Home and variable spellings (F1, high).** Claude Code expands a leading `~` in a Glob or Grep path when it
    runs the tool, while the transcript keeps the raw text; `~/...` joined onto the working directory looked
    inside the export. Any path, pattern or glob that starts with `~` or holds `$` now flags.
  - **The audit's code is bound (BR9-1).** `transcript_audit.py` is a verdict-review-gate trust path, and its
    sha256 is in the Claude lane's provenance (`transcript_audit_py_sha256`, registered in `lane-provenance.json`)
    and in the adjudication provenance, as `codex_lane.py` and `adjudicate.py` are.
  - **Retried agents (REG9-2).** The run record lists each agent's final attempt; an earlier attempt's transcript
    must map to the item of an agent retried at least that often (at most attempt − 1 per item) and is audited
    against that item's boundary. An extra on a non-retried item, beyond an item's retries, or naming no item
    fails the run. Measured on a real run retried after a usage limit: each earlier attempt carries its final
    attempt's prompt.
  - **macOS and long project names (REG9-1, REG9-7).** The locate test derives the slug from the resolved path
    (macOS resolves `/home` elsewhere), and `locate` finds a shortened project directory by the session's unique id.
  - **Recorded, not read:** each exposure measure's `ledgers_sha256` names the ledger it was measured against; a
    later check cannot recompute it, since the ledger then holds the wave's rows (BR9-2, disclosed).
- **Independent round-8 review of 68e74f2c (regressions, binding and resume, operability, disclosure), and the
  transcript-audit hardening ahead of round 9:**
  - **Audit reads the raw command text again (REG8-1, REG8-3).** Round 7's reading of which spans bash expands
    let double-quoted apostrophes, escaped quotes, heredocs and nested `sh -c` scripts hide reads; substitution,
    `$CODEX_HOME` and inherited directories are matched in the raw text (a literal backtick in a single-quoted
    search voids a layer again: REG7-3 is a known low). The bare word `CODEX_HOME` flags only in a command that
    reads the environment (`printenv`, `env`, `export -p`, `declare -p`), so `rg -n CODEX_HOME docs` is benign.
  - **Interrupted reruns (NEW-1).** A pending layer's old return is removed before its events are rewritten, and a
    resume counts a kept return only beside a non-empty, clean event stream.
  - **Prose exposure bound per layer (NEW-2).** Each layer's measure records its packet's sha256, the export's
    tree and the ledgers' digest. It is taken when the layer's row is first written (a wave's first `--write`, or
    the `--append-rows` that adds it, still before that row); a document present before the first write is
    refused, and an append or `--check` reads the retained one only as the run manifest binds it. `landscape.py`
    requires each row's measure to name its retained packet and its lanes' tree.
  - **CI test scope and the step-7 remedy (OPR8-1, OPR8-2).** The real-export test asserts only the failing kinds,
    with no winner-pinned prose assertion. A step-7 remedy edits a verdict-review-gate trust file, so it lands
    first as a rules-only PR and the wave PR follows on the merged main.
  - **Packet prose (REG8-4).** Another layer's proper nouns match next to `-` and `/` ("Nautilus-native",
    "Codex/Claude"); only a path token keeps its segments. Prose placeholders are 186 spans, 76 in shared fields.
  - **Lows taken where the code was open:** a symlink into a checkout is refused as `--out` or `--keys-out`
    (REG8-5); `keys()` removes its rebuilt document on failure and step 7 and the resume note run `packets_args`
    (OPR8-3, OPR8-4); step 7 follows CI's order (OPR8-6); `blind_checkout` imports `lane_packets` from its own
    directory (OPR8-5).
  - **Transcript audit, bound and fail-closed.** See "Claude family" above: the run record binds the transcripts to
    the completed run, its agents and the collected result; agents must run from the export; paths compare
    resolved; unmodelled, server-side and MCP tool calls, unreadable lines and climbing globs flag. Its tests cover
    each evasion case, and nine mutants of its checks are all killed. The exact-id fix resolves `data-mlflow` to
    one candidate in evaluation-experiments (the winner-change sweep then has 32 trips in 296 scenarios).
  - **Not taken:** LOW-1 (pre-existing: a blind resume would count a clean return written by a non-blind run on the
    same export) and R8-DIS-1/3/4 (exposure over-reporting through generic table headers, sentence-start capitals,
    two OTel role strings) stay disclosed lows.
- **Codex review at 68e74f2c:**
  - **Claude read boundary (P1).** A Claude judge or lane agent could open the sibling lane returns next to its
    input. Both Claude-family surfaces are now audited on their agents' transcripts (see "Claude family" above).
  - **Duplicated Claude items (P1).** The claude-args snapshot binds its exact item list, and `claude-collect`
    refuses a result that returns an item twice or one the snapshot does not hold.
  - **Prose exposure for every new wave (P1).** `record_verdicts.py` refuses a new wave's `--write` without
    `--lane-repo-root` (and a `--check` without the sealed document), and `landscape.py` requires every new wave's
    run manifest to bind `prose_exposure_sha256`.
  - **Exact component ids (P2).** `export_isolation_check` matches a winner by its exact component id before the
    normalized one, so `alpaca-py` no longer also selects `data-alpaca-py` on the same repository.
- **Independent round-7 review of a4dfd99e (blindness, operability, regressions and isolation-integrity lenses),
  under the reviewer's convergence plan: no new detection features; fix the confirmed mediums with real-data tests;
  make the disclosure the resolution; take the lows where the code was open:**
  - **Interrupted and resumed Codex runs (REG7-1, ISO-R7-1..4, ISO-R7-8).** Each layer is audited before its
    return is written, so a flagged layer is void even when the run is interrupted, and a resume re-audits a kept
    return's events. A stop signal (SIGTERM, SIGHUP, SIGINT) sets a stop that starts no attempt, retry or refute
    stage and promotes no return, terminates and waits for every child, and cannot be interrupted by a second
    signal; the executors cancel queued work. Every run home holds an in-use lock its children inherit, so a
    later run's sweep never removes a link a live orphan still uses, and the link is removed only after the
    children are gone. Both runners hold the work dir's own lock (`.codex-run.lock`) before the homes' base lock,
    so a second run of one work dir is refused whatever its `NAS_CODEX_HOME_DIR`. The base is created 0700.
    Tests: an interrupt then a resume never keeps a flagged layer; a stop with `--jobs 2` writes no return and
    starts no retry; a kept return with flagged or missing events reruns; a stop during adjudication writes no
    record and starts no refute stage.
  - **Audit and credentials (REG7-3, ISO-R7-5..7, ISO-R7-9).** Substitution, `CODEX_HOME` (the bare name too) and
    inherited directory variables are matched in the shell-active text only. A proxy variable with inline
    credentials is refused for a blind run, since every child variable reaches the model's shell; the dry-run
    redaction handles a scheme-less value and a password containing `@`.
  - **Checker scope (OPR7-2).** With round 6's rules, 96 of 288 single-layer winner changes failed step 7 and CI,
    mostly on intrinsic card fields (license, a version) and on evidence lists such as `primary_references`. Only
    role labels outside evidence records and packet fields on exactly the winners now fail; record-field hits
    (three records at least, low-cardinality columns only, `evidence_ref` as evidence) and evidence-record role
    words other than winner, incumbent and chosen are reported. The same sweep on this head: 32 of 297 changes in
    18 layers fail (32 of 296 after the exact-id fix below, which leaves one scenario fewer), all on the older container and packet checks (28 of 288 at fe5143e2).
  - **Prose exposure (BL7-1, BL7-2).** A table's body row is scored with its header, so "| Layer | Selected native
    practice |" over the web-research row is an exposure. A statement counts only when it names a winner and no
    adopted non-winner, and states a selection by a choice phrase, a status copula or label, or an imperative
    choice ("Retain skfolio"), not by a selection word merely near a name. `record_verdicts.py --write` measures
    this against the ledger before the wave's rows, over the export the lanes read, seals it as
    `prose-exposure.json` (bound by the run manifest's `prose_exposure_sha256`) and stamps each row's
    `lanes.prose_exposed`; `landscape.py` checks both. Step 7's check is the next wave's pre-check.
  - **Packet prose (BL7-3, BL7-4, BL7-5).** Another layer's name parts match only as capitalized proper nouns
    ("Nautilus", "Alpaca"), and a candidate name that is an ordinary word only as written ("Temporal"), never
    inside a path: the dropped clause "retain scoped telemetry, failed attempts and recoverable state ..." is back
    in 3 requirements, and shared-field placeholders fell from 125 to 74 (prose placeholders 331 to 172). In a
    candidate's own fields a selection word next to its own name, or beside a result marker, no longer drops a
    sentence; a choice phrase or status copula still does. Status needs a copula ("is this catalog's selected
    live-primary broker path") or a labelling opening ("The selected GitHub CLI.", "Selected north-star engine");
    "Default examples use model API credentials", "Failed-turn usage is retained." and the NautilusTrader
    parity-gate record stay. The result marker is case-insensitive and also matches `failed`/`blocked` inside a
    status token and a bare `*.json` name.
  - **Operability (OPR7-1, OPR7-3..6, REG7-4, INT-R7-1).** The wave's date and manifest are fixed once in
    `KEYS_DIR/wave.env`, so `keys()` rebuilds the same packets on any later day; it replaces the keys document
    only after `cmp` passes, so a failed call leaves none, and step 6 chains it. `build_verdicts.py` refuses a
    missing manifest with exit 2. Step 7 lists the validate job's offline steps, including the base commit's
    verdict-review gate, and says to re-register after any later edit. `lane_packets.py` records an absolute
    `--manifest` relative to `--root` and refuses an `--out` or `--keys-out` inside a repository. A sealed
    `component_id` or `pin` of the wrong type is a clean refusal.
- **Independent round-6 review of fe5143e2 (integrity, Codex-isolation, blindness, regressions and operability
  lenses):**
  - **Exported files are verbatim; the exposure is disclosed (design decision, 2026-09-24; B6-4, B6-2).** Six
    rounds showed sentence redaction inside exported files to be a moving target, and at fe5143e2 it did harm: it
    rewrote 60 of 87 exported prose files, removed 14,647 words, broke the sha256 of 30 hash-bound files and
    dropped incumbents' own negative evidence. The export now rewrites no sentence or table. Reduction is limited
    to what this catalog builds for a lane: the packets (below) and the label fields of catalog cards and ledger
    rows. `export_isolation_check.py` reports `prose_exposed_layers`: 18 of 32 layers have a cited prose file
    that states their winner's selection (26 of 89 exported prose files; superseded by round 7's measure, which
    scores tables and counts only discriminating statements). A wave record discloses those layers as
    not blind against cited prose. Alternatives measured: excluding every cited narrative document would drop
    108 of 1,378 packet references and leave 9 adopted candidates without evidence; redaction is above.
    Overturn: a redaction that a mutation test shows removes every seeded choice statement without changing a
    hash-bound file, or a re-record in which the exposed layers' lanes side with the incumbent measurably more
    often than the unexposed layers'.
  - **Packet prose (B6-1, B6-5).** Each packet's matcher also carries every catalog candidate's whole names and
    ids (both ledgers, the manifest's components and entries), so another layer's incumbent sentence no longer
    passes. `CHOICE_PHRASE`
    covers "implementation choice", "prior LEAN oracle", "use stage" and catalog membership words. A candidate's
    own `role` and `card_limitations` lose a sentence only when it states that candidate's status, never one
    carrying a result marker (PASS, FAIL, BLOCKED, an exit code, a count such as 3/5) or a repository path.
  - **Card labels (B6-3).** The checker's `record_field_hits` tests every field of a list of candidate records:
    present on exactly the winners, absent on exactly the winners, or a categorical scalar held by exactly the
    winners. The export strips `evidence_level`, `installed_version` and a role status statement from cards. On
    the real export: 0 record-label hits and 0 role-label hits.
  - **Checker gaps (B6-6).** Key tokens split at camelCase and `-`. Inside evidence records, a key carrying a role
    word (selected, selection, pick, recommended, preferred, default, primary, current, chosen, winner,
    incumbent) is a label when it isolates the winners, unless its position is reviewed with a reason in
    `REVIEWED_EVIDENCE_PATHS`; three such positions were reviewed as evidence (a client session's
    `selected_checks`, two `primary_sources` lists). A packet field absent on exactly the winners is a hit, and a
    selection word or an emptied "(selected)" is removed from a candidate's name.
  - **Sealed keys (INT-R6-1..3).** Each packet commits to its sealed values (`sealed_candidates_sha256`, over the
    sanitized values the document stores). The keys document names the manifest it was built from (path and
    sha256); `record_verdicts.py` checks it and that every sealed component id is unique and registered there.
    `adjudicate.py inputs` checks the document against every packet. The lane runners no longer read it, and the
    recipe deletes it while any model worker runs, rebuilding it deterministically (byte-identical packets)
    only for `adjudicate inputs` and `record_verdicts`.
  - **Codex isolation (ISO-R6-1..5).** One lock per work dir under the homes' base, shared by `codex_lane` and
    `adjudicate codex`; SIGTERM and SIGHUP remove the credential link, and the next run sweeps a link a SIGKILL
    left. The audit flags `$CODEX_HOME`, command substitution and an inherited directory variable (`${TMPDIR}`,
    `$SSL_CERT_DIR`) passed as an argument; a child's `TMPDIR` is an empty directory of its run home. A blind
    child never gets an API key: the native `auth.json` is required (`codex login --with-api-key` makes one from
    a key). Measured 2026-09-24 with `codex-cli 0.155.1`: `-c shell_environment_policy.inherit="core"`, `"none"`
    and `include_only=["PATH"]` left the model's shell environment in `codex exec` unchanged (a planted non-core
    `SSL_CERT_DIR` reached it every time), so that override is not used. Refusals run before the lock and the dry
    run, and the dry run shows proxy credentials as `***`.
  - **Adjudication regressions (REG6-1..5).** A long glued segment no longer raises (`os.path.isfile`); the whole
    glued chain is walked; `inputs` records each lane root's tree digest, and `assemble` reports a changed tree
    and asks for `inputs` to be rerun instead of silently dropping judgments; a leak found by a call whose own checks passed stands even when the
    run end voids the run.
  - **Operability (OPR6-1..5).** Step 7 regenerates what a wave changes (`component_matrix`, `build_verdicts`,
    `new_host_grand_list`), rehashes only the registered files the wave changed, and runs every check
    `validate.yml` runs. The isolation re-check builds into a new directory, and `lane_packets.py` refuses an
    existing `--out` or `--keys-out`. Step 3 copies only the two blind roles. `export_isolation_check.py` exits 2
    on a usage or input error (missing or malformed `--packet-keys`, or none for sealed packets), never the
    label-hit exit 1.
- **Independent round-5 review of a516c477 and the review of 52344da8:**
  - **Fresh Codex homes, allowlisted children (INT-R5-2, ISO-R5-1..4).** Each blind run makes a fresh home with
    `tempfile.mkdtemp` under the base; nothing is ever removed to make one (the round-4 home was recreated with
    `rmtree`, which deleted a native home placed at that path). The base and the native Codex home may not be
    one directory or nest either way, and the base may not overlap the work dir or export. A child's environment
    is an allowlist (`PATH`, locale, `TMPDIR`, `TERM`, certificate and proxy variables), plus `CODEX_HOME`, the
    empty `HOME`, and an API key variable only when no credential is linked: not the caller's, which carries the
    coordinator's transcript pointer, cross-session socket and token, and broker variables. Children get no stdin,
    and the file credential store is pinned (`-c cli_auth_credentials_store="file"`). Probe 2026-09-24,
    `codex-cli 0.155.1`: a child with only `CODEX_HOME`, `HOME`, `LANG`, `PATH` and `TERM` signed in, listed
    only the CLI's bundled skills and received no AGENTS.md; the native credential was intact and the link was
    removed after.
  - **Sealed values committed in the packet (INT-R5-1; Codex review at a516c477).** A blind packet carries
    `sealed_candidates_sha256`, the digest of its candidates' sealed values. `packet_keys_issue` (used by
    `record_verdicts.py`, `adjudicate.py inputs`, `scripts/landscape.py` and `scripts/verdict_review_gate.py`)
    refuses an entry that does not hash to it. A stale, edited or other build's document therefore cannot restore
    other component ids or pins, and every lane return, bound to the packet's sha256, is bound to the values too.
    The lane runners need no keys. The commitment is deterministic; recovering the values from it would mean
    guessing every candidate's exact pins, upstream records and decision prose, none of which a blind export
    holds. `record_verdicts.py --write` also refuses a retained entry that does not seal exactly its packet's
    candidates (INT-R5-4), and a bad `--packet-keys` file is a clean refusal (R5-REG-8).
  - **No keys document while a worker runs (Codex review at a516c477).** A model worker runs as the operator's
    user and can read any file it names, so a keys document placed outside `--out` was still reachable. The recipe
    deletes it right after building the packets. For `adjudicate.py inputs` and `record_verdicts.py`, the only
    steps that need it, it rebuilds it (the build is deterministic) and checks the rebuilt packets are
    byte-identical. It deletes it again before the judges run. A blind `codex_lane` layer whose audit is flagged
    (a read outside the export and packets, web search or an MCP tool) is now void, its return set aside, as a
    flagged adjudication judgment already was.
  - **Packet prose (N1, N2, N4; Codex review at a516c477).** A sentence is dropped only when it states the
    catalog's choice: a choice phrase ("current choice", "selected destination", "implementation choice", "prior
    LEAN oracle", "incumbent"), catalog membership or lifecycle status ("stack.json", "inventory entry", "use
    stage", "qualified component"), or a selection word within 25 characters of a candidate name. Other names
    are written `<candidate>`. Terms cover full names, parenthesized aliases ("GitHub CLI (gh)" gives `gh`),
    repository names, component ids, owners and name parts unique to one candidate (outside the layer's own title
    and scope words), with `-`/`_`/space variants. Short names such as `gh`, `uv` or `RTK` match as whole
    case-sensitive tokens. Since the Codex review, every catalog candidate's whole names and distinctive parts
    (round 7, BL7-3: parts only as capitalized proper nouns, ordinary words only as written)
    count in every packet, so a factor layer's prose no longer names Nautilus, LEAN or Alpaca. A selection word is
    never a term. On the 2026-09-23 packets, 4 requirements are emptied (13 before), all us-equities layers
    sharing the group requirement that names the selected destination, and 363 names are written `<candidate>`
    (125 in the shared requirement, limitations and overturn text; measured at round 6). A packet without `layer_scope_terms`
    is no longer pointed at them. Candidates' `role` and `card_limitations` are reduced too (any selection word
    there goes, since the text is about that candidate). Prose runs before the popularity strip, so the
    archived/license gating reads the requirement the lanes see, and every blind packet is checked with
    `withheld_packet_keys` before anything is written. The export gives the ledger rows and the quality review's
    layer entries the packets' reduced text and drops the review's `evidence_gap`.
  - **`evidence_kind` withheld (N5).** A selected candidate must carry a strong kind, so the kind held exactly the
    winners in 7 layers; blind packets drop it and the export strips it from ledger candidates. The packet check
    now also tests values: a categorical scalar, or a list element shared by two or more winners. At this head
    only `registered_receipts` (11 layers) and `evidence_refs` (2) isolate winners, as evidence.
  - **Export redaction as table units, stricter evidence classes (review of 52344da8).** (Superseded in round 6:
    exported files are no longer redacted.) A Markdown table went whole when any row stated the choice, so no
    single broken row marked the winner. Inside evidence records a
    `selected_repositories`-style selection or an unambiguous role word (winner, incumbent, chosen) is a label,
    and such selections are stripped under `evidence/`. Named role keys are never exempt as evidence objects.
    Six complement lists remain in receipts (commands resolved, components covered) for code-navigation and
    git-github-automation; they record what a session ran and are kept as evidence.
  - **Smaller fixes.** A leak is recorded only when the call's full provenance (code, prompt, schemas, tree) is
    unchanged. A glued segment naming a file under a lane root stays as repository evidence (R5-REG-5), and a host
    path after a URL-closing `|` is scrubbed (R5-REG-6). The review gate accepts a documented `failed` lane
    outcome with its reasons (ops N2). `${...}` is flagged only with an operator. A refused export also removes its
    worktree. The lane prompt no longer promises upstream metadata (N6), and its hash is re-registered.
- **Independent round-4 review of 2a2ffb8d (blindness, binding, regressions and operability lenses):**
  - **Id-aware isolation check and removed selection records (F1).** `export_isolation_check.py` read only
    github.com/huggingface.co URLs, so id-keyed lists passed. It now matches every list (its strings and its
    objects' id fields) and every object's key set against each adopted candidate's slug, repository name,
    component id and name, normalized (`data-`/`foundation-`/`candidate:` prefixes, `_` as `-`). The sealed ids
    come from `--packet-keys`. A hit is evidence when it sits in an evidence record (under `evidence/`,
    `blueprints/`, `observability/` or a `*receipt*.json`), in a names-alone list under an evidence key, or at a
    reviewed position (`REVIEWED_EVIDENCE_PATHS`). A complement list elsewhere fails whatever its key (F6). The
    first real run found `adoption/manifest.json` (profile `component_ids` and `recipe_map`, exact for 10
    layers) and `catalogs/foundation/decisions.json` (decision `component_ids`, 6 layers). Both are now
    removed from every blind export, with `catalogs/us-equities/runtime-target.json` (the selected destination,
    F3) and `blueprints/us-equities/north-star.md` (its "Selected path" table). A `selected_component*` key
    (the upstream-check provenance crosswalk) is stripped under `evidence/`. On the 2026-09-23 export, 0
    role-label hits remain and evidence-record hits remain in 13 layers.
  - **References to removed files (F4, OPS-1, R4-REG-2).** Under `--withhold-labels`, `lane_packets.py` drops
    every evidence reference and registered receipt that names a file the blind export removes
    (`blind_checkout.removed_from_blind_export`), and lists the drop in each packet's `withheld`: 57 references
    in 21 packets. One adopted candidate is left with no evidence reference: web-research Crawl4AI, whose only
    reference was a removed membership file. (Round 6: 69 adopted candidate entries cite only pinned
    upstream sources, with no local receipt; among them web-research Cua Driver, whose only reference is a pinned
    upstream README URL the review could not fetch.) `blind_checkout.py --export` now refuses, and removes the export, when a
    packet references a path the export lacks, unless `--allow-missing-refs` is passed. The real-export test
    asserts none.
  - **Selection prose redacted (F3; superseded in round 6, which exports every file verbatim and discloses the
    exposure instead).** The export dropped, from every exported Markdown or text file outside fenced
    code, each sentence that uses a selection word and names a candidate of any packet. The unit is a paragraph,
    list item or table row, so a sentence wrapped over lines is matched whole. The term set is the union over all
    packets, so what is dropped does not depend on which candidate won. Measured independently (winner names,
    component ids and repository names, word-bounded, against directly cited and one-level transitive files):
    20 of 30 scored layers were exposed before and 0 after. The redaction changed 58 of the 85 exported prose
    files and removed 6,246 words. JSON string prose is not redacted (see "Remaining limits").
  - **Sealed manifest fields (F5).** Only a sota-manifest component carries `component_id`, `pin`, `upstream`,
    `recipe_ref` and `decisions`, so their presence alone marked membership. On the 2026-09-23 packets they
    were present on exactly the recorded winners among the adopted candidates in 6 layers (8 against the v1
    selected/default candidates). Under `--withhold-labels`, `lane_packets.py` now moves them, by candidate key,
    into a packet-keys document at `--keys-out`. That flag is required with `--withhold-labels` and must point
    outside `--out`, which lanes read. `record_verdicts.py --packet-keys` and `adjudicate.py inputs
    --packet-keys` restore the fields after checking the packet's sha256, so winner component ids and pins
    resolve as before. A wave retains the document as `<sealed_base>/packet-keys.json`, bound by the run
    manifest's `packet_keys_sha256`. `scripts/landscape.py` and `scripts/verdict_review_gate.py` restore from
    it, and `withheld_packet_keys` refuses a new-wave packet whose candidates still carry a sealed field.
    `export_isolation_check.packet_field_hits` measures the packet fields themselves and fails on a non-evidence
    field. After the change it finds none. `registered_receipts` still sits on exactly the winners in 6 layers.
    This is disclosed as evidence-volume asymmetry: the catalog ran what it chose.
  - **Codex children's HOME (F2).** Codex also discovers user Agent Skills under `$HOME/.agents/skills`, and
    their names are adopted tools. A blind child now runs with `HOME=<codex-home>/home`, an empty directory
    of mode 0700. Measured 2026-09-24 with `codex-cli 0.155.1`: with the isolated `CODEX_HOME` and the
    caller's `HOME`, a probe child listed qmd, tavily-* and typesafe-ai among its skills. With the empty
    `HOME`, it listed only the CLI's bundled skills.
  - **Codex home safety (BIND-R4-1, R4-REG-3, R4-REG-9, BIND-R4-7, OPS-4; current as of round 6).** Each blind run
    creates a fresh home with `mkdtemp` under `$NAS_CODEX_HOME_DIR` (default
    `~/.local/state/native-agent-stack/codex-home`), named `<sha256(work dir)[:16]>-<random>`, outside the work dir
    and the export. `codex_home_issue` refuses, creating nothing (not even the lock), when the base is, holds or
    sits inside the native Codex home (either spelling), when it overlaps the work dir or the export, and when there
    is no native `auth.json`. A blind child is never given an API key (ISO-R6-4, below). The refusals run before the
    dry run too, and the home is created only when something is pending. A dry run prints each child's whole
    environment as `env -i PATH=... LANG=... TERM=... 'CODEX_HOME=<base>/<prefix>-<run>' 'HOME=<base>/<prefix>-<run>/home'
    codex exec ...`, with proxy credentials shown as `***`. The credential link is removed when the run ends, on an
    exception, on SIGINT, and on SIGTERM or SIGHUP (raised as `SystemExit`). A SIGKILLed run leaves the link; the
    next run of the same work dir, under the same lock, removes every such leftover `auth.json` symlink first,
    except in a home whose in-use lock a live child still holds (round 7, ISO-R7-2). The blind audit also flags
    `${...}` parameter expansion.
  - **Run lock and bound audits (BIND-R4-5, BIND-R4-6).** `codex_lane` and `adjudicate codex` hold an exclusive
    `flock` for the run (since round 6 one shared lock per work dir, `<base>/<prefix>.lock`), so two runs cannot
    recreate each other's home or
    interleave events files. A Codex judgment records each stage's events file and sha256, and
    `usable_judgment` re-audits them, so an edited `audit_clean` does not count.
  - **Per-call binding (BIND-R4-3, BIND-R4-4, BIND-R4-2).** A call deletes its input's stale events first and is
    audited on the stages it ran. A stage that ran but left no events is flagged. The evidence tree is checked
    after each call, and a changed tree voids the judgment at once. A clean call's leak is recorded when the
    call ends, so an interrupted run keeps it. The run-end tree check also catches `OSError`. The adjudication
    provenance and registry now name `codex_lane.py`.
  - **Bindings to the lanes' inputs (BIND-R4-8, BIND-R4-9, OPS-6).** `claude_lane.py` requires the agent-lab
    workflow to be tracked, no uncommitted `.claude/`, `CLAUDE.md` or `AGENTS.md` changes, and HEAD at or
    after the `vendored-lanes.json` commit. Each `--lane-repo-root` given to `record_verdicts.py` and
    `adjudicate inputs` must hold the evidence tree the lanes read and must not contain `..`. `codex_lane` and
    `claude_lane_args` refuse a work dir inside a git repository, and the refusal messages state the root
    rule as `codex_lane.root_issue` applies it.
  - **Smaller fixes.** A non-blind run hashes a looping symlink by its text on Python 3.12 (R4-REG-4).
    Scrubbing absorbs a sentence after a spaced host path when that sentence holds a path separator, and a
    name glued on by `,` or `;` (R4-REG-5); a following sentence citing a repository path is lost, by design.
    `--export` may not overlap `--dest` or `--source` (R4-REG-8). The lane fixtures use a dummy credential
    and fixture homes (R4-REG-7). `RealExportIsolationTests` sits above the `__main__` guard (F8, R4-REG-10).
    The recipe registers and rehashes evidence after `build_verdicts --write`, and runs the isolation check
    before the PR (OPS-2, OPS-3). It also names the agent-lab commit and the role install (OPS-7).
- **Codex review at a2434e2e and the Codex cross-family review:**
  - **No whole trees in the allowlisted export.** `tests/`, `tools/` and `scripts/` carry selection-bearing data
    and assertions (the reconciliations file, `tests/test_catalogs.py`), so a file there is exported only when a
    packet references it.
  - **Escaping symlinks, loops and special files.** For a blind run, `codex_lane.tree_sha256` refuses a symlink
    that is absolute or resolves outside the tree, a symlink loop (found by `os.stat` ELOOP, so on Python 3.12 and
    3.13 alike), and a FIFO, socket or device. The blind lane and adjudication entry points exit 2 on any of them.
    A deliberately non-blind `codex_lane --allow-git-history` run hashes such entries by their link text or
    skips them, because a working checkout can hold a `.venv` link or git's fsmonitor socket.
  - **Position map integrity and location.** `assemble` derives each order's Claude position from the input
    contents, re-scrubbing the hash-bound lane returns, and refuses a judgment whose index map disagrees. The
    index moves out of the work dir, to `$NAS_ADJUDICATION_STATE_DIR` or
    `~/.local/state/native-agent-stack/adjudication/<sha256(work dir)[:16]>/adjudication-index.json`. One
    directory accumulates per work dir. After a wave is recorded, remove it with
    `rm -r "$(python3 -c 'import sys; sys.path.insert(0, "tools/sota-convergence"); import adjudicate; print(adjudicate.index_path(sys.argv[1]).parent)' <work-dir>)"`.
  - **Audit and instruction boundaries.** Each Codex judge call is audited inside its worker, before its record is
    written. A flagged call (web search, an MCP tool, or a command reaching outside its repository, input and
    packet) voids the judgment, and a Codex judgment counts only when its record says `audit_clean`, so an
    interrupted or resumed run cannot count a flagged call. Claude judges' reads are instruction-bound: the role
    and prompt name only three paths, and no filesystem sandbox enforces that. That also covers the lane return
    files in `<work-dir>/claude/` and `<work-dir>/codex/`, which would identify A and B.
  - **One checkout.** `adjudicate` relativizes lane returns against the catalog checkout it runs from, and
    `record_verdicts.py` against its `--root`. Run both from the same checkout; a mismatch fails closed (the
    adjudication is rejected).
  - **Packet paths.** The Claude lane layers echo `packet_path` (agent-lab #47), and `claude_lane.py` requires
    it to be the work dir's packet with the layer's `packet_sha256`.
  - **Unresolved path check.** `claude_lane_args.py` checks the `--repo` as given, not only resolved.
- **Round 14:**
  - `adjudication-lane.js` echoes the prompt it read and each item's consumed input and packet paths.
    `claude-collect` requires the prompt to hash to the snapshot's `prompt_sha256` and the repo to be the
    snapshot's exactly; an item whose echoed paths are not the ones `claude-args` gave is a missing judgment.
  - A leak from a run whose input, packet, tree, role or consumed arguments no longer hold is discarded, not
    recorded.
  - A deleted input is recorded as a missing judgment rather than raising.
  - A spaced final path segment ending in a file extension (`/srv/My Project/private key.json`) is scrubbed
    whole. Since the 3d0943cc review, the rest of the sentence after any outside path is absorbed (up to a
    delimiter, a line end, or the first token ending a sentence, whose punctuation is kept), so an
    extension-less spaced segment cannot leave a word either. Text after that sentence end is kept.
  - `codex` and `claude-args` check both the `--repo` as given (absolutized, symlinks kept) and its resolved
    form: on macOS `/home` is a symlink whose target is deep enough to pass the depth rule.
- **Round 13:**
  - `claude-collect` recomputes the `claude-args` snapshot's digest and refuses a snapshot edited under an
    unchanged `snapshot_id`.
  - An outside host path that holds spaces is scrubbed whole: each following space-separated token that
    continues it with a `/` or `\` is absorbed, so no suffix of it survives.
  - `blind_checkout --export` replaces an instruction name that is a symlink to a directory, or a directory
    itself, with the stub, root files included.
- **Bindings added in round 12:**
  - The Claude lane's echoed `launch` also carries `agent_sha256`, the role digest the launcher checked
    before and after the run. `claude_lane.py` requires it to equal the vendored role digest.
  - `claude-args` snapshots the sha256 of each effective blind-adjudicator definition (`--agent-file` and any
    project-level copy under `--run-dir`). `claude-collect` records every judgment as missing when one of them
    changed.
  - `codex_lane.tree_sha256` refuses a path that is not an existing directory, and `codex_lane`,
    `adjudicate codex`, `adjudicate claude-args` and `claude_lane.py` refuse (exit 2) a missing `--repo`.
- **Bindings added in round 11:**
  - `inputs` reads each packet and lane return once. The parsed object, its sha256 and the packet snapshot
    all come from those bytes.
  - `record_verdicts.py` also reads each lane file once, for validation, the `lane_returns_sha256` check and
    sealing.
  - A new-wave row needs both lanes' `repo_tree_sha256` equal (otherwise the Codex lane is rejected), and an
    adjudication whose provenance names another tree is rejected.
  - Windows host paths (`C:\x`, `C:/x`, `\Users\example\y`, `\\server\share\x`) are scrubbed and caught like
    POSIX ones.
- **Audit roots (round 9, narrowed in the independent review):** each Codex judge call's audit allows only the
  repository, its own input file and its packet snapshot under `<work-dir>/adjudication-packets/`.
- **Leak text (round 9):** a reported leak's text has every path form the input scrubbing removes replaced by
  `<outside-path>`, and is capped at 400 characters, before it is stored in `leaks.json`,
  `adjudication-leaks.json` or printed.
- **Any leading character (round 9):** an absolute path is scrubbed whatever its first character. That covers
  Unicode word characters (`/évidence/x`), and any other legal character when a later `/` follows
  (`/-private/x`, `/@host/x`); prose such as `+/-` or `and/or` is left alone.
- **Gap receipts in a blind build (round 8):** `lane_packets.py` refuses `--gap-receipts` together with
  `--withhold-labels` (exit 2, nothing written).
- **HTML delimiters:** `>` delimits a path, as backticks do.
- **Edited inputs:** `claude-args` and `codex` refuse an input whose bytes differ from the sha256 `inputs`
  indexed.
- **URL bounds:** URLs end at markup and quote characters, so a host path right after a link is still
  scrubbed.
- **Leak hashes:** a leak records both orders' hashes as sampled before the judgment.
- **Record prose:** the judges' prose and evidence refs are scrubbed before a record is written, and a
  surviving host path refuses the layer.
- **Role installation:** both blind roles are in `adoption/agents/claude/`; the recipe's step 3 copies only those
  two into `~/.claude/agents/`. `tools/adoption/install_claude_profile.py --only agents` would replace all seven
  catalog agents user-level (round 6, OPR6-4).
- **Run directory:** `claude-args --run-dir`, which is required, also checks a project-level
  `blind-adjudicator.md` in the directory the workflow runs from.
- **`--agent-file`:** pass the `blind-lane-reviewer` file the lane loaded. That is the user-level copy when
  the lane runs from the blind export, which has no `.claude/`.

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

