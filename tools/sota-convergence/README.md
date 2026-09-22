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
   Output has the exact key layout of `manifest-20260922.json`: `schema_version,
   id, checked_at, scope, method, taxonomy, foundation, trading,
   lane_groupings, citation_review, critic, lane_calls, lane_limits,
   reconciliations, counts`. `lane_groupings` carries, verbatim, any
   review-lane layer id outside the foundation/taxonomy baseline (e.g. a
   "beyond" lane's own grouping like `awesome-list-convergence`) that would
   otherwise not match `trading[].layer`'s exact-taxonomy contract.
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
   `--check` (the default) recomputes both outputs in memory and exits 1 on
   any difference from what is checked in, without writing; `--write`
   recomputes and writes them.

   ```sh
   python3 tools/sota-convergence/build_verdicts.py --write --root .
   python3 tools/sota-convergence/build_verdicts.py --check --root .
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
`adopted` flag, that is a known limit of the withholding. Foundation packets are identical in
both modes, and the default `ledger` mode still reproduces the 2026-09-22 packets byte for byte.

Known limit of the withholding (2026-09-22 independent review): each
candidate keeps its `adopted` flag, which the never-promote rule needs, and
foundation packets attach the matched decisions' `selection` value
(`default`/`conditional`/`optional`); the layer's `limitations` and
`existing_overturn_when` can also name the current choice. A lane therefore
sees which adopted candidate is the incumbent default. The 2026-09-22 run used
these packets unchanged so they stay reproducible from this tool; the
comparison that would change this is a rerun with `selection` stripped from
the attached decisions and the two runs' winner sets compared layer by layer.

```sh
python3 tools/sota-convergence/lane_packets.py --root . --out /path/to/work-dir
python3 tools/sota-convergence/lane_packets.py --root . --out /path/to/work-dir --catalog us-equities --seed 20260922
```

No network access; every input is already checked into `catalogs/` and
`adoption/`. Each candidate is matched to a `catalogs/sota-convergence/
manifest-20260922.json` component/entry by normalized GitHub slug
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
  --root . --work-dir /path/to/work-dir --checked-at YYYY-MM-DD \
  [--adjudications /path/to/adjudications] --write
python3 tools/sota-convergence/record_verdicts.py \
  --root . --work-dir /path/to/work-dir --checked-at YYYY-MM-DD --check
```

`--write` and `--check` are a required, mutually exclusive pair (argparse
rejects both together and rejects neither) -- there is no silent default
mode.

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
  `evidence/artifacts/layer-verdicts-20260922/<lane>/<catalog>-<layer_id>-20260922.json`;
  its sha256 becomes the row's `lanes.<lane>.sealed_sha256`.
- **Derived winner `pin`** (never taken from the lane): the packet's own
  manifest-joined `pin`, else the winning candidate's real v1 pin text if
  any -- the ledger's actual `candidates[]` schema carries this as
  `source_pin` (preferred) or, on a few rows, `revision`; there is no
  `v1_pin` field anywhere in the repository -- else the literal string
  `"unpinned"`.
- **Agreement.** Both lanes valid and their winner component-id sets equal
  -> `same_winner` (recorded from Claude's `why_selected`/`overturn_when`, the latter written to
  `verdict_overturn_when`,
  Codex's `open_gaps` appended); Claude only -> `codex_absent` (recorded,
  `open_gaps` gets "codex lane absent for this layer"); both valid but
  disagreeing -> `disagree`: recorded from the lane an optional
  `--adjudications/<catalog>__<layer_id>.json`
  (`{"winner_lane": "claude"|"codex", "why", "evidence_refs": [...]}`) names
  (the file itself is retained at
  `evidence/artifacts/layer-verdicts-20260922/adjudication/<run_id>.json`),
  else the row stays `pending_lanes` with the open disagreement recorded
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
python3 tools/sota-convergence/build_verdicts.py --write --root .
python3 scripts/landscape.py --root .
python3 scripts/validate.py
```

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
`layer_id` matching this packet, and, if it already has a `packet_sha256`,
that hash still matching the packet file's current bytes -- it fills the
shared lane prompt (`lane-prompt.md`, placeholders `{PACKET_PATH}`
`{REPO_ROOT}` `{LANE}`) and runs:

```sh
codex exec --sandbox read-only --skip-git-repo-check --ephemeral \
  -C <repo> --output-schema <schema> -o <out.tmp> --json \
  -c model_reasoning_effort=<effort> <filled prompt>
```

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

```sh
python3 tools/sota-convergence/codex_lane.py \
  --work-dir /path/to/work-dir --repo . --effort high
python3 tools/sota-convergence/codex_lane.py \
  --work-dir /path/to/work-dir --repo . --layers native-clients,market-data-reference
python3 tools/sota-convergence/codex_lane.py \
  --work-dir /path/to/work-dir --repo . --dry-run   # prints the command per pending layer, writes nothing
```

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
