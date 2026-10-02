# Catalog freshness drift

Published manifest: `catalogs/sota-convergence/manifest-20260929.json` (counts: {'foundation_layers': 20, 'trading_layers': 12, 'trading_layers_note': 'trading_layers counts only taxonomy layers with at least one selected entry, unlike foundation_layers (which counts every row); trading[] itself always has one row per taxonomy id, so len(manifest["trading"]) can exceed trading_layers whenever a taxonomy layer happens to have zero selected entries', 'components_confirmed': 0, 'pins_behind_upstream': 51, 'candidates_total': 188, 'pins_behind_upstream_unique_components': 33, 'pins_behind_upstream_by_review_status': {'not_individually_reviewed': 51}, 'review_status_pin_behind_upstream': 0, 'pin_status_disputed': 0, 'pin_status_disputed_by_lane_status': {}, 'other_lane_reviews_pin_status_disputed': 0, 'pin_status_note': "pins_behind_upstream counts the generator's computed pin fields; pins_behind_upstream_by_review_status splits those rows by published review_status. A row's review_status is pin_behind_upstream[_unverified] only when its computed pin_behind_upstream is true, so review_status_pin_behind_upstream equals the pin_behind_upstream[_unverified] share of that split; a lane pin claim the computed fields contradict is published as pin_status_disputed[_unverified] (the lane's claim in disputed_lane_status and the row evidence) or, on an OS-package pin, distro_managed", 'pins_behind_note': 'components with a commit-pinned version (a parenthetical hash), a non-GitHub repository, or an OS-distribution package pin (matched by an -Nubuntu/-Ndeb/+debN pin suffix, or by id via --os-package-ids, e.g. systemd even though its own repository is on GitHub) are excluded from the pin-vs-upstream comparison rather than counted either way', 'pins_not_compared': 20, 'pins_not_compared_by_reason': {'commit_pinned': 1, 'os_package_pin': 3, 'unversioned': 16}, 'pins_not_compared_note': 'rows whose pin the generator could not compare with upstream (the exclusions above, plus a pin or upstream latest with no parseable version, reason unversioned) carry pin_behind_upstream null and pin_comparison not_compared, never a definite false', 'candidates_by_disposition': {'refuted_keep_but_compare': 83, 'refuted_not_adopted': 24, 'targeted_candidate': 18, 'refuted_targeted_candidate': 44, 'keep_but_compare': 10, 'not_adopted_confirmed': 9}, 'lane_groupings': 0, 'lane_grouping_candidates': 0, 'unmatched_lane_items': 0, 'unmatched_lane_items_by_lane': {}, 'lane_groupings_note': "every foundation/trading-scoped count above (candidates_total, candidates_by_disposition, components_confirmed, pins_behind_upstream, pins_behind_upstream_unique_components) is computed from all_rows = manifest['foundation'] + manifest['trading'] only, and so excludes lane_groupings[].selected rows the same way it excludes lane_groupings[].candidates; candidates inside lane_groupings (a review-lane grouping id outside the foundation/taxonomy baseline, e.g. an awesome-list survey) are counted only in lane_grouping_candidates; counts.citation_review (computed below, by apply_citation_review) is the same way scoped -- its rows_flagged/attached only ever count a foundation/trading row, never a lane_groupings[].selected row, since apply_citation_review only walks manifest['foundation'] and manifest['trading']", 'citation_review': {'findings_in_artifact': 0, 'findings': 0, 'out_of_scope': 0, 'attached': 0, 'rows_flagged': 0, 'general': 0}})
Rebuilt manifest: `manifest-20261002.json` (counts: {'foundation_layers': 20, 'trading_layers': 12, 'trading_layers_note': 'trading_layers counts only taxonomy layers with at least one selected entry, unlike foundation_layers (which counts every row); trading[] itself always has one row per taxonomy id, so len(manifest["trading"]) can exceed trading_layers whenever a taxonomy layer happens to have zero selected entries', 'components_confirmed': 0, 'pins_behind_upstream': 105, 'candidates_total': 0, 'pins_behind_upstream_unique_components': 55, 'pins_behind_upstream_by_review_status': {'not_individually_reviewed': 105}, 'review_status_pin_behind_upstream': 0, 'pin_status_disputed': 0, 'pin_status_disputed_by_lane_status': {}, 'other_lane_reviews_pin_status_disputed': 0, 'pin_status_note': "pins_behind_upstream counts the generator's computed pin fields; pins_behind_upstream_by_review_status splits those rows by published review_status. A row's review_status is pin_behind_upstream[_unverified] only when its computed pin_behind_upstream is true, so review_status_pin_behind_upstream equals the pin_behind_upstream[_unverified] share of that split; a lane pin claim the computed fields contradict is published as pin_status_disputed[_unverified] (the lane's claim in disputed_lane_status and the row evidence) or, on an OS-package pin, distro_managed", 'pins_behind_note': 'components with a commit-pinned version (a parenthetical hash), a non-GitHub repository, or an OS-distribution package pin (matched by an -Nubuntu/-Ndeb/+debN pin suffix, or by id via --os-package-ids, e.g. systemd even though its own repository is on GitHub) are excluded from the pin-vs-upstream comparison rather than counted either way', 'pins_not_compared': 20, 'pins_not_compared_by_reason': {'commit_pinned': 1, 'os_package_pin': 3, 'unversioned': 16}, 'pins_not_compared_note': 'rows whose pin the generator could not compare with upstream (the exclusions above, plus a pin or upstream latest with no parseable version, reason unversioned) carry pin_behind_upstream null and pin_comparison not_compared, never a definite false', 'candidates_by_disposition': {}, 'lane_groupings': 0, 'lane_grouping_candidates': 0, 'unmatched_lane_items': 0, 'unmatched_lane_items_by_lane': {}, 'lane_groupings_note': "every foundation/trading-scoped count above (candidates_total, candidates_by_disposition, components_confirmed, pins_behind_upstream, pins_behind_upstream_unique_components) is computed from all_rows = manifest['foundation'] + manifest['trading'] only, and so excludes lane_groupings[].selected rows the same way it excludes lane_groupings[].candidates; candidates inside lane_groupings (a review-lane grouping id outside the foundation/taxonomy baseline, e.g. an awesome-list survey) are counted only in lane_grouping_candidates; counts.citation_review (computed below, by apply_citation_review) is the same way scoped -- its rows_flagged/attached only ever count a foundation/trading row, never a lane_groupings[].selected row, since apply_citation_review only walks manifest['foundation'] and manifest['trading']", 'citation_review': {'findings_in_artifact': 0, 'findings': 0, 'out_of_scope': 0, 'attached': 0, 'rows_flagged': 0, 'general': 0}})

This diff is report-only; it changes no catalog selection.

| id | pin (published) | pin (fresh) | upstream latest (published) | upstream latest (fresh) | behind (published) | behind (fresh) |
| --- | --- | --- | --- | --- | --- | --- |
| `affaan-m/ECC` | `dd6ee538aee0f548d4a6b520118f875431fd749e` | `dd6ee538aee0f548d4a6b520118f875431fd749e` | `v2.2.1` | `v2.2.3` | `(none)` | `(none)` |
| `agent-browser` | `0.38.1` | `0.38.1` | `v0.38.1` | `v0.38.2` | `False` | `True` |
| `ai-memory` | `2.4.1` | `2.4.1` | `v2.4.1` | `v2.5.2` | `False` | `True` |
| `apple-container` | `1.4.1` | `1.4.1` | `1.4.1` | `1.5.0` | `False` | `True` |
| `beads` | `1.3.0` | `1.3.0` | `v1.3.0` | `v1.3.1` | `False` | `True` |
| `claude-code` | `2.1.284` | `2.1.284` | `v2.1.284` | `v2.1.288` | `False` | `True` |
| `claude-hud` | `0.8.0` | `0.8.0` | `v0.8.0` | `v0.10.0` | `False` | `True` |
| `codex` | `0.157.1` | `0.159.3` | `rust-v0.158.0` | `rust-v0.160.0` | `True` | `True` |
| `codex-acp` | `v1.12.0` | `v1.12.0` | `v2.0.0` | `v2.1.1` | `True` | `True` |
| `codex-native-sdk` | `CLI rust-v0.155.1; Python openai-codex 0.154.0` | `CLI rust-v0.155.1; Python openai-codex 0.154.0` | `rust-v0.158.0` | `rust-v0.160.0` | `True` | `True` |
| `dagu` | `v2.16.6` | `v2.16.6` | `v2.17.2` | `v2.18.1` | `True` | `True` |
| `data-clickhouse` | `v26.8.7.19-lts; source f29d27def7ee0adb10e7e2fff080ba204054dd4b` | `v26.8.7.19-lts; source f29d27def7ee0adb10e7e2fff080ba204054dd4b` | `v26.9.5.2-stable` | `v26.3.39.7-lts` | `True` | `False` |
| `data-edgartools` | `v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a` | `v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a` | `v5.59.1` | `v5.60.0` | `True` | `True` |
| `data-iceberg` | `Apache Iceberg 1.11.0; PyIceberg 0.12.0; source 6976e020b894f6a6777704df2b8c4458cb291ae9` | `Apache Iceberg 1.11.0; PyIceberg 0.12.0; source 6976e020b894f6a6777704df2b8c4458cb291ae9` | `apache-iceberg-1.11.0` | `apache-iceberg-1.12.0` | `False` | `True` |
| `e2b` | `e2b@2.51.0` | `e2b@2.51.0` | `e2b@2.51.0` | `e2b@2.52.0` | `False` | `True` |
| `fastapi` | `0.141.1` | `0.141.1` | `0.141.1` | `0.142.2` | `False` | `True` |
| `foundation-ai-memory` | `v2.4.1` | `v2.4.1` | `v2.4.1` | `v2.5.2` | `False` | `True` |
| `foundation-docling` | `v2.129.0` | `v2.129.0` | `v2.130.0` | `v2.132.0` | `True` | `True` |
| `foundation-haystack` | `v3.1.1` | `v3.1.1` | `v3.2.0` | `v3.3.0` | `True` | `True` |
| `foundation-mteb` | `2.21.0` | `2.21.0` | `2.21.8` | `2.22.1` | `True` | `True` |
| `foundation-pageindex` | `v0.2.18` | `v0.2.18` | `v0.2.20` | `v0.2.21` | `True` | `True` |
| `foundation-pgvector` | `v0.8.6 documented tag; reviewed HEAD efa08fda9ec485d80292d0487a77939c087dedcc` | `v0.8.6 documented tag; reviewed HEAD efa08fda9ec485d80292d0487a77939c087dedcc` | `v0.8.6` | `v0.8.7` | `False` | `True` |
| `foundation-rtk` | `v0.49.0` | `v0.49.0` | `v0.50.0` | `v0.51.0` | `True` | `True` |
| `grafana` | `v13.2.2` | `v13.2.2` | `v13.2.2` | `v13.2.3` | `False` | `True` |
| `grype` | `v0.119.0` | `v0.119.0` | `v0.119.0` | `v0.120.0` | `False` | `True` |
| `huggingface-hub-native` | `1.32.0` | `1.32.0` | `v2.0.0` | `v2.1.0` | `True` | `True` |
| `jcodemunch-mcp` | `1.108.319` | `1.108.319` | `v1.108.319` | `v1.108.327` | `False` | `True` |
| `mcp-inspector` | `2.8.0` | `2.8.0` | `2.8.0` | `2.9.0` | `False` | `True` |
| `mcporter` | `0.14.1` | `0.14.1` | `v0.14.1` | `v0.14.2` | `False` | `True` |
| `nextjs` | `16.3.6` | `16.3.8` | `v16.3.6` | `v16.3.8` | `False` | `False` |
| `omniroute` | `v3.8.50` | `v3.8.50` | `v3.8.50` | `v3.8.51` | `False` | `True` |
| `openbao` | `v2.6.2` | `v2.6.2` | `v2.7.0` | `v2.7.1` | `True` | `True` |
| `openresearch` | `0.2.7` | `0.2.7` | `v0.2.12` | `v0.2.15` | `True` | `True` |
| `opentelemetry-collector-contrib` | `v0.161.0` | `v0.161.0` | `v0.161.0` | `v0.162.0` | `False` | `True` |
| `phoenix` | `arize-phoenix-v20.14.0` | `arize-phoenix-v20.14.0` | `arize-phoenix-otel-v0.17.2` | `arize-phoenix-v20.19.0` | `False` | `True` |
| `ray-serve` | `ray-2.58.0` | `ray-2.58.0` | `ray-2.58.0` | `ray-2.59.0` | `False` | `True` |
| `rtk` | `0.50.0` | `0.50.0` | `v0.50.0` | `v0.51.0` | `False` | `True` |
| `sandbox-runtime` | `v0.0.77` | `v0.0.77` | `v0.0.77` | `v0.0.78` | `False` | `True` |
| `skfolio` | `1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee` | `1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee` | `v1.4.8` | `v1.4.10` | `True` | `True` |
| `syft` | `v1.52.0` | `v1.52.0` | `v1.52.0` | `v1.54.0` | `False` | `True` |

8 component(s) were fetched successfully this run but have no GitHub release or tag at all; this is not drift:

`data-kafka`, `inspect-ai`, `lean-alpaca`, `poppler`, `postgresql`, `shanraisshan/claude-code-best-practice`, `skills-ref`, `tavily-cli`

## Trading components: pin vs upstream latest

Report-only. This table lists every pinned trading component, including those that did not change since the published manifest: each selected (`default`/`conditional`) `catalogs/us-equities` card, plus the trading pins that blueprint or runtime records declare outside those cards (`tools/sota-convergence/extract_layers.py` `TRADING_PIN_SOURCES`). A dormant upstream has no GitHub release and no default-branch commit in the last 180 days as of `2026-10-02`. Dormant and archived rows are not drift. They select nothing.

| id | layers | pin | upstream latest | behind | last release | last commit | days since release/commit | dormant | archived |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `adaptive-paper-alpaca-adapter` | `execution-broker` | `7e7eefe28315f3de3aa4dc75cc8b6524f70829cb (blueprints/us-equities/adaptive-paper)` | `v2026.09.26.2` | `not compared (unversioned)` | `2026-09-26` | `2026-10-02` | `0` | `no` | `no` |
| `alertmanager` | `observability-hosting` | `v0.34.1` | `v0.34.1` | `no` | `2026-09-17` | `2026-09-29` | `3` | `no` | `no` |
| `alpaca-py` | `execution-broker` | `0.44.0` | `v0.44.0` | `no` | `2026-08-11` | `2026-09-28` | `4` | `no` | `no` |
| `alphalens-reloaded` | `research-factors-ml` | `0.4.6` | `0.4.5` | `no` | `2025-07-23` | `2025-06-02` | `436` | `yes` | `no` |
| `arch` | `research-factors-ml` | `8.0.0` | `v8.0.0` | `no` | `2025-10-21` | `2026-09-27` | `5` | `no` | `no` |
| `chronos` | `research-factors-ml` | `2.3.2` | `v2.3.2` | `no` | `2026-09-08` | `2026-09-17` | `15` | `no` | `no` |
| `codex-acp` | `agents-models-workers` | `v1.12.0` | `v2.1.1` | `yes` | `2026-10-01` | `2026-10-02` | `0` | `no` | `no` |
| `codex-native-sdk` | `agents-models-workers` | `CLI rust-v0.155.1; Python openai-codex 0.154.0` | `rust-v0.160.0` | `yes` | `2026-10-01` | `2026-10-02` | `0` | `no` | `no` |
| `cosign` | `identity-provenance, security-supply-chain` | `v3.1.3` | `v3.1.3` | `no` | `2026-08-06` | `2026-10-02` | `0` | `no` | `no` |
| `cvxportfolio` | `backtesting-engine, portfolio-risk` | `1.5.1` | `1.5.1` | `no` | `2025-07-06` | `2026-04-27` | `158` | `no` | `no` |
| `dagu` | `data-quality-orchestration` | `v2.16.6` | `v2.18.1` | `yes` | `2026-09-29` | `2026-10-02` | `0` | `no` | `no` |
| `data-alpaca-py` | `market-data-reference, execution-broker` | `v0.44.0; source cc4cb3b7ba50ae250e621983c2779047fb16bb28` | `v0.44.0` | `no` | `2026-08-11` | `2026-09-28` | `4` | `no` | `no` |
| `data-arcticdb` | `identity-provenance, research-factors-ml` | `v6.26.0; source e620d8572a1e62c9ec07df8cbc8f5c432cd84325` | `v6.26.0` | `no` | `2026-09-14` | `2026-10-02` | `0` | `no` | `no` |
| `data-arrow` | `storage-compute` | `apache-arrow-25.0.1; source beccec0d0c451b7aa3e4530416ac431b3c035c69` | `apache-arrow-25.0.1` | `no` | `2026-08-10` | `2026-10-02` | `0` | `no` | `no` |
| `data-clickhouse` | `storage-compute` | `v26.8.7.19-lts; source f29d27def7ee0adb10e7e2fff080ba204054dd4b` | `v26.3.39.7-lts` | `no` | `2026-10-02` | `2026-10-02` | `0` | `no` | `no` |
| `data-databento` | `market-data-reference` | `v0.86.0; source e675ef30369f5ee9f68b04606080c519adf3be69` | `v0.87.0` | `yes` | `2026-09-22` | `2026-09-22` | `10` | `no` | `no` |
| `data-dlt` | `market-data-reference, storage-compute` | `1.30.0; source a2f4a21e22e5c266278271b6591c70dbc485aea8` | `1.30.0` | `no` | `2026-08-11` | `2026-10-02` | `0` | `no` | `no` |
| `data-duckdb` | `storage-compute` | `v1.5.5; source d8cdaa33fda8df955cc76ef58a280f68f4cd43fa` | `v1.5.6` | `yes` | `2026-09-28` | `2026-10-02` | `0` | `no` | `no` |
| `data-dvc` | `identity-provenance` | `3.67.1; source 356dfa03278058b02df42124f243c2c345329dae` | `3.67.1` | `no` | `2026-03-31` | `2026-08-06` | `57` | `no` | `no` |
| `data-edgartools` | `market-data-reference, research-factors-ml` | `v5.58.0; source abe44344c56cf4bfb5443e0debca7e39342f6e7a` | `v5.60.0` | `yes` | `2026-10-02` | `2026-10-02` | `0` | `no` | `no` |
| `data-exchange-calendars` | `market-data-reference` | `4.13.2; source dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a` | `4.13.2` | `no` | `2026-03-10` | `2026-09-15` | `17` | `no` | `no` |
| `data-feast` | `market-data-reference, storage-compute` | `v0.66.0; source 1d5be950cf718a674cb01eaf0fd0ad6f0a4c6335` | `v0.66.0` | `no` | `2026-08-21` | `2026-10-02` | `0` | `no` | `no` |
| `data-fredapi` | `market-data-reference` | `v0.5.2; source bf7cc8fdb03b12f8224bbb1bf66381b9d21c6d6d` | `v0.5.2` | `no` | `2024-05-05` | `2026-01-28` | `247` | `yes` | `no` |
| `data-gdeltdoc` | `market-data-reference` | `1.12.0; source f2e500144b0a6090d63723f94453b32717e5fd23` | `1.12.0` | `no` | `2025-04-03` | `2025-04-22` | `528` | `yes` | `no` |
| `data-iceberg` | `identity-provenance, storage-compute` | `Apache Iceberg 1.11.0; PyIceberg 0.12.0; source 6976e020b894f6a6777704df2b8c4458cb291ae9` | `apache-iceberg-1.12.0` | `yes` | `2026-09-30` | `2026-10-02` | `0` | `no` | `no` |
| `data-kafka` | `market-data-reference, identity-provenance` | `4.3.1; source 26b251a451ce941d3d7a55e6487bcb7f16b5ad48` | `(none)` | `not compared (unversioned)` | `(none)` | `2026-10-02` | `0` | `no` | `no` |
| `data-massive` | `market-data-reference` | `v2.8.0; source 3c247d78c603fc13d274fda1aa26749e7c8c3710` | `v2.8.0` | `no` | `2026-05-26` | `2026-07-09` | `85` | `no` | `no` |
| `data-mlflow` | `identity-provenance, evaluation-experiments` | `v3.16.1; source 32792afe5b0183fce10532d3a023f5cfa8612d09` | `v3.16.1` | `no` | `2026-09-17` | `2026-10-02` | `0` | `no` | `no` |
| `data-openlineage` | `identity-provenance` | `1.53.0; source 8ad5c14c63fbab63fedd8ff42f9a208d86ad07fe` | `1.53.0` | `no` | `2026-09-01` | `2026-10-02` | `0` | `no` | `no` |
| `data-pandera` | `storage-compute, data-quality-orchestration` | `v0.33.1; source 62f55e2dccf0a199cfe4d6ce3eda0c1d29e2e4e6` | `v0.33.1` | `no` | `2026-09-01` | `2026-09-26` | `6` | `no` | `no` |
| `data-questdb` | `market-data-reference, storage-compute` | `10.0.1; source 7a391566ac827e0d8c269b91f2415c16b0a32a84` | `10.0.1` | `no` | `2026-08-24` | `2026-10-02` | `0` | `no` | `no` |
| `data-river` | `research-factors-ml, evaluation-experiments` | `0.26.1; source 64285b9dd6c606804753235fe992bcf25b9856ee` | `0.26.1` | `no` | `2026-08-21` | `2026-10-02` | `0` | `no` | `no` |
| `data-sktime` | `research-factors-ml` | `v1.1.0; source 918fa838d99eb3703fe9bc963891619608aa35b4` | `v1.2.0` | `yes` | `2026-09-22` | `2026-09-27` | `5` | `no` | `no` |
| `data-statsforecast` | `research-factors-ml` | `v2.1.1; source 264166ec0ddbfd481ee8e0b71e5ca42d2c0676fc` | `v2.1.1` | `no` | `2026-07-16` | `2026-10-01` | `1` | `no` | `no` |
| `data-tsfresh` | `research-factors-ml` | `v0.21.2; source 6aa24fdef7e3c3f48b19482535693f5796f2b598` | `v0.21.2` | `no` | `2026-05-31` | `2026-07-06` | `88` | `no` | `no` |
| `deerflow` | `research-factors-ml, agents-models-workers` | `stable v2.0.0; discovery commit 42334f26d7025d905678f9075b079fc65f9beaf9 (2.1.0-rc0)` | `v2.1.0` | `yes` | `2026-09-24` | `2026-10-02` | `0` | `no` | `no` |
| `e2b` | `observability-hosting` | `e2b@2.51.0` | `e2b@2.52.0` | `yes` | `2026-10-01` | `2026-10-02` | `0` | `no` | `no` |
| `empyrical-reloaded` | `portfolio-risk` | `0.5.12` | `0.5.12` | `no` | `2025-06-01` | `2025-07-29` | `430` | `yes` | `no` |
| `foundation-agent-retrieval-bench` | `evaluation-experiments, agents-models-workers` | `v0.2.1` | `v0.2.1` | `no` | `2026-07-26` | `2026-08-04` | `59` | `no` | `no` |
| `foundation-ai-memory` | `agents-models-workers` | `v2.4.1` | `v2.5.2` | `yes` | `2026-10-01` | `2026-10-02` | `0` | `no` | `no` |
| `foundation-codebase-memory-mcp` | `agents-models-workers` | `v0.11.0` | `v0.11.0` | `no` | `2026-09-15` | `2026-10-02` | `0` | `no` | `no` |
| `foundation-context-mode` | `agents-models-workers` | `v1.0.169` | `v1.0.169` | `no` | `2026-06-29` | `2026-10-02` | `0` | `no` | `no` |
| `foundation-docling` | `research-factors-ml` | `v2.129.0` | `v2.132.0` | `yes` | `2026-10-01` | `2026-10-02` | `0` | `no` | `no` |
| `foundation-graphiti` | `agents-models-workers` | `v0.30.2` | `v0.30.2` | `no` | `2026-09-08` | `2026-09-30` | `2` | `no` | `no` |
| `foundation-haystack` | `research-factors-ml` | `v3.1.1` | `v3.3.0` | `yes` | `2026-10-01` | `2026-10-02` | `0` | `no` | `no` |
| `foundation-markitdown` | `research-factors-ml` | `v0.1.7` | `v0.1.8` | `yes` | `2026-09-21` | `2026-10-02` | `0` | `no` | `no` |
| `foundation-mteb` | `evaluation-experiments` | `2.21.0` | `2.22.1` | `yes` | `2026-10-01` | `2026-10-02` | `0` | `no` | `no` |
| `foundation-pageindex` | `agents-models-workers` | `v0.2.18` | `v0.2.21` | `yes` | `2026-10-01` | `2026-10-01` | `1` | `no` | `no` |
| `foundation-pgvector` | `agents-models-workers` | `v0.8.6 documented tag; reviewed HEAD efa08fda9ec485d80292d0487a77939c087dedcc` | `v0.8.7` | `yes` | `(none)` | `2026-10-01` | `1` | `no` | `no` |
| `foundation-qdrant` | `agents-models-workers` | `v1.19.1` | `v1.19.1` | `no` | `2026-09-04` | `2026-09-03` | `28` | `no` | `no` |
| `foundation-qmd` | `research-factors-ml` | `v2.8.3` | `v2.8.3` | `no` | `2026-08-16` | `2026-10-02` | `0` | `no` | `no` |
| `foundation-repomix` | `agents-models-workers` | `v1.18.0` | `v1.18.1` | `yes` | `2026-09-21` | `2026-09-28` | `4` | `no` | `no` |
| `foundation-rtk` | `agents-models-workers` | `v0.49.0` | `v0.51.0` | `yes` | `2026-10-02` | `2026-10-02` | `0` | `no` | `no` |
| `foundation-sentence-transformers` | `research-factors-ml` | `v6.1.0` | `v6.1.0` | `no` | `2026-09-18` | `2026-09-21` | `11` | `no` | `no` |
| `foundation-serena` | `agents-models-workers` | `v1.7.0` | `v1.7.0` | `no` | `2026-08-09` | `2026-09-30` | `2` | `no` | `no` |
| `foundation-socraticode` | `identity-provenance, agents-models-workers` | `v1.14.0` | `v1.16.0` | `yes` | `2026-09-28` | `2026-10-02` | `0` | `no` | `no` |
| `foundation-toon` | `storage-compute, agents-models-workers` | `v4.1.1` | `v4.1.1` | `no` | `2026-08-05` | `2026-10-02` | `0` | `no` | `no` |
| `gitleaks` | `security-supply-chain` | `v8.30.1` | `v8.30.1` | `no` | `2026-03-21` | `2026-07-22` | `72` | `no` | `no` |
| `grafana` | `observability-hosting` | `v13.2.2` | `v13.2.3` | `yes` | `2026-09-29` | `2026-10-02` | `0` | `no` | `no` |
| `grype` | `security-supply-chain` | `v0.119.0` | `v0.120.0` | `yes` | `2026-10-02` | `2026-10-02` | `0` | `no` | `no` |
| `hftbacktest` | `backtesting-engine` | `2.4.4` | `rust-v0.9.4` | `no` | `2025-12-10` | `2025-12-23` | `283` | `yes` | `no` |
| `inspect-ai` | `evaluation-experiments` | `inspect-ai0.3.266; source ec4dfc6953784dc45b79de3147530c89868c6e26` | `(none)` | `not compared (unversioned)` | `(none)` | `2026-10-02` | `0` | `no` | `no` |
| `langgraph` | `agents-models-workers` | `langgraph 1.2.11; separately released langgraph SDK0.4.4` | `cli==0.4.32.dev0` | `no` | `2026-09-23` | `2026-10-02` | `0` | `no` | `no` |
| `lean` | `backtesting-engine` | `985ef30ad3ac774218c5ac516b4cb0aa2655730f` | `v2.4.0.1` | `not compared (unversioned)` | `2017-08-08` | `2026-10-02` | `0` | `no` | `no` |
| `lean-alpaca` | `execution-broker` | `1973f6165bee212acf656ed2f9cb0af86d4f2a18` | `(none)` | `not compared (unversioned)` | `(none)` | `2026-09-28` | `4` | `no` | `no` |
| `loki` | `observability-hosting` | `v3.7.8` | `v3.7.8` | `no` | `2026-09-17` | `2026-10-02` | `0` | `no` | `no` |
| `mlflow` | `evaluation-experiments, observability-hosting` | `v3.16.1` | `v3.16.1` | `no` | `2026-09-17` | `2026-10-02` | `0` | `no` | `no` |
| `modal` | `data-quality-orchestration, observability-hosting` | `Python modal1.5.5; source be5f129326efe4864d666d263d249214bd9b4ed2` | `v1.3.1` | `no` | `(none)` | `2026-10-02` | `0` | `no` | `no` |
| `nautilus-ibapi` | `execution-broker` | `10.45.1` | `ibapi-latest@10.49.02` | `yes` | `2026-08-05` | `2026-04-23` | `58` | `no` | `yes` |
| `nautilus-ibkr-adapter` | `execution-broker` | `2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e)` | `v1.231.0` | `no` | `2026-08-02` | `2026-10-02` | `0` | `no` | `no` |
| `nautilustrader` | `backtesting-engine` | `2.0.0rc5 (tag v2.0.0rc5; source pin from evidence/receipts/native-nautilus-v2-20260920.json — commit 1b0a49d2792a9432a3aca3fcb617ce7a630d905e)` | `v1.231.0` | `no` | `2026-08-02` | `2026-10-02` | `0` | `no` | `no` |
| `ntfy` | `observability-hosting` | `v2.28.0` | `v2.28.0` | `no` | `2026-08-27` | `2026-09-29` | `3` | `no` | `no` |
| `omniroute` | `agents-models-workers` | `v3.8.50` | `v3.8.51` | `yes` | `2026-09-30` | `2026-10-02` | `0` | `no` | `no` |
| `openbao` | `security-supply-chain` | `v2.6.2` | `v2.7.1` | `yes` | `2026-10-01` | `2026-10-02` | `0` | `no` | `no` |
| `opensandbox` | `observability-hosting` | `server/v0.2.3; Python SDK0.1.16` | `release-1.1.0` | `yes` | `2026-09-21` | `2026-10-01` | `1` | `no` | `no` |
| `opentelemetry-collector` | `observability-hosting` | `v0.161.0` | `v0.162.0` | `yes` | `2026-09-28` | `2026-10-02` | `0` | `no` | `no` |
| `opentelemetry-collector-contrib` | `observability-hosting` | `v0.161.0` | `v0.162.0` | `yes` | `2026-09-29` | `2026-10-02` | `0` | `no` | `no` |
| `phoenix` | `evaluation-experiments, observability-hosting` | `arize-phoenix-v20.14.0` | `arize-phoenix-v20.19.0` | `yes` | `2026-10-01` | `2026-10-02` | `0` | `no` | `no` |
| `prometheus` | `observability-hosting` | `v3.14.0` | `v3.15.0` | `yes` | `2026-09-25` | `2026-10-02` | `0` | `no` | `no` |
| `qlib` | `research-factors-ml` | `0.9.7` | `v0.9.7` | `no` | `2025-08-15` | `2026-09-16` | `16` | `no` | `no` |
| `quantstats` | `portfolio-risk` | `0.0.81` | `v0.0.86` | `yes` | `2026-09-27` | `2026-09-27` | `5` | `no` | `no` |
| `ray-serve` | `storage-compute, research-factors-ml` | `ray-2.58.0` | `ray-2.59.0` | `yes` | `2026-10-02` | `2026-10-02` | `0` | `no` | `no` |
| `restic` | `observability-hosting` | `v0.19.1; publisher-signed linux/amd64 release asset` | `v0.19.1` | `no` | `2026-07-05` | `2026-09-25` | `7` | `no` | `no` |
| `rust-ibapi` | `execution-broker` | `Rust ibapi =3.3.0 (Cargo.toml at tag v2.0.0rc5)` | `v4.2.0` | `yes` | `2026-09-21` | `2026-10-02` | `0` | `no` | `no` |
| `sandbox-runtime` | `observability-hosting` | `v0.0.77` | `v0.0.78` | `yes` | `2026-09-30` | `2026-10-02` | `0` | `no` | `no` |
| `scikit-learn` | `research-factors-ml` | `1.9.1` | `1.9.1` | `no` | `2026-09-11` | `2026-10-02` | `0` | `no` | `no` |
| `skfolio` | `research-factors-ml, portfolio-risk` | `1.2.9; WalkForward source c99fcf71349e2df4a7a1033ee85ca2e9ced9abee` | `v1.4.10` | `yes` | `2026-09-30` | `2026-10-01` | `1` | `no` | `no` |
| `statsmodels` | `research-factors-ml` | `0.15.0` | `v0.15.0` | `no` | `2026-08-27` | `2026-10-02` | `0` | `no` | `no` |
| `syft` | `security-supply-chain` | `v1.52.0` | `v1.54.0` | `yes` | `2026-10-01` | `2026-10-02` | `0` | `no` | `no` |
| `temporal` | `data-quality-orchestration` | `server v1.32.0; CLI1.9.1; Python SDK1.33.0` | `v1.32.0` | `no` | `2026-09-11` | `2026-10-02` | `0` | `no` | `no` |
| `timesfm` | `research-factors-ml` | `v3.0.0` | `v3.0.0` | `no` | `2026-08-28` | `2026-09-29` | `3` | `no` | `no` |
| `vllm` | `research-factors-ml, agents-models-workers` | `active0.25.0 (702f4814fe54fabff350d43cb753ae3e47c0c276); latest0.29.0` | `v0.30.0` | `yes` | `2026-09-22` | `2026-10-02` | `0` | `no` | `no` |

5 dormant upstream(s) (no release or default-branch commit in 180+ days):

`alphalens-reloaded`, `data-fredapi`, `data-gdeltdoc`, `empyrical-reloaded`, `hftbacktest`

1 archived upstream repository(ies):

`nautilus-ibapi`
