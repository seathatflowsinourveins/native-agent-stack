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
   rename status per repository. Resumable: a repository already present in
   `--out` is skipped unless `--refresh`; `--max-repos` bounds a trial run.

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
  `.devN` commit-tracking pin (e.g. `2.0.0.dev0 @ <commit>`), and its parsed
  leading version is lower than GitHub's latest release/tag. Non-GitHub
  repositories (OS packages such as systemd) and `.devN` pins are excluded
  from the comparison rather than counted either way. A version merely
  *annotated* with a commit fingerprint (`0.25.0 (<commit>)`) is still
  compared normally.
- **Selected trading baseline**: only catalog `decision` values `default` and
  `conditional` are promoted into a manifest row; `alternative`/`watch`/
  `excluded` entries stay discoverable in `trading-by-layer.json` and can
  only reach the manifest through the lane candidate/alternative mechanism.
- **Disposition never promotes** (`disposition`): a lane proposes a label,
  two refuters try to break it. A surviving `not_adopted` stays
  `not_adopted_confirmed`; nothing is upgraded by surviving review.
- **Sanitize-then-refuse**: `sanitize()` strips `/home/...` fragments;
  `assert_no_leak()` then raises if `/home/` or `APCA` is still present, and
  `build_manifest.py` never writes on that path.

## Evidence classes

Keep these separate when reading or citing the output:

- **Metadata** (`github-freshness.json`, `upstream` fields in the manifest) --
  GitHub REST facts (stars, pushed_at, release tags). Not a behavioral test.
- **Source review** (`lanes.json` selections/candidates, `review_status`
  values not prefixed `confirmed`) -- a lane read documentation/READMEs and
  reasoned about fit; nothing was installed or run.
- **Native run** (`review_status` prefixed `confirmed_*` after surviving
  adversarial verification, and anything cited to a receipt under
  `evidence/` or `manifests/evidence.json`) -- an actual reproducible
  execution exists, separate from this manifest.

Inclusion in any working file or the manifest is never installation, E2E
acceptance, or superiority.

## Regression note

`build_manifest.py` run against the real 2026-09-22 working files reproduces
`catalogs/sota-convergence/manifest-20260922.json` exactly on the
`(layer, repository, review_status)` identity set for both foundation and
trading, on `candidates_total`/`candidates_by_disposition`, and on
`components_confirmed`. The raw/unique `pins_behind_upstream` counts differ
by a small, understood margin: two GitHub-metadata `.devN` pins
(`serena`, `alphalens-reloaded`) that the *published* manifest's own prose
already says are "ahead of GitHub's latest release" were nonetheless flagged
`True` by the original, unrecovered baseline generator -- `classify_pin`'s
`.devN` rule fixes exactly that inconsistency, per its own worked example.
`modal`'s freshness in the original run came from a live PyPI read (noted in
the trading lane's own limitations as one of "six PyPI JSON reads" outside
the `gh api`/`web_fetch`/`web_search` budget); this tool's freshness step is
GitHub-only, so `modal`'s pin-vs-upstream comparison is not reproducible
without adding a PyPI fetch. Neither difference changes a selection,
candidate disposition, or count that a decision was made from.
