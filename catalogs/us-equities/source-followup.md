# Bounded source follow-up

Checked September 19, 2026. This follow-up examined eight repositories: four adopted release pins and four operational candidates. It refreshed all public-star identities but did not repeat every repository review, install software or run models/services. The [typed receipt](source-followup-receipt.json) records sources and scope.

The public endpoint still returned **337 public stars**, with **0 additions, 0 removals and 0 identities missing from the prior 451-repository index**. Adding two previously absent observability alternatives produces **453 repository identities: 337 public stars plus 116 beyond them**. There are now **151 layer cards covering 146 distinct catalog repositories**, including 105 beyond the stars. The earlier baseline/candidate records add 24 distinct identities to the core, forming a 170-reference subset. These counts measure examined references, not installations.

## Recorded pins and latest stable releases

| Repository | Recorded installed pin | Latest GitHub stable release | Published | Decision |
| --- | --- | --- | --- | --- |
| [Context Mode](https://github.com/mksglu/context-mode/releases/tag/v1.0.169) | 1.0.169 | v1.0.169 | 2026-06-29 | Retain |
| [ai-memory](https://github.com/akitaonrails/ai-memory/releases/tag/v2.3.1) | 2.3.1 | v2.3.1 | 2026-09-17 | Retain |
| [RTK](https://github.com/rtk-ai/rtk/releases/tag/v0.49.0) | 0.49.0 | v0.49.0 | 2026-09-11 | Retain |
| [SocratiCode](https://github.com/giancarloerra/SocratiCode/releases/tag/v1.14.0) | 1.14.0 | v1.14.0 | 2026-09-16 | Retain |

These are recorded manifest pins compared with the official GitHub `releases/latest` response. Executables were not rerun; npm, PyPI, development branches and prerelease channels were not treated as interchangeable releases. Newer default-branch commits alone do not justify changing an accepted runtime.

## Useful operational decisions

| Repository | Source pin / license | Catalog status | Decision and missing acceptance |
| --- | --- | --- | --- |
| [node_exporter](https://github.com/prometheus/node_exporter/releases/tag/v1.12.1) | v1.12.1, 2026-07-14; Apache-2.0 | Newly added alternative | Prefer the existing Collector's host receiver for basic CPU, RAM and filesystem metrics. Adopt a separate exporter only for a required node collector/dashboard. No install or scrape was performed. |
| [OpenLIT](https://github.com/openlit/openlit/releases/tag/openlit-2.1.0) | openlit-2.1.0, 2026-09-10; Apache-2.0 | Newly added alternative | Native coding-agent instrumentation is present in the pinned source, but another hook/transcript collector overlaps accepted native OTLP. Defer until a specific trace/evaluation need and content policy justify it. |
| [abtop](https://github.com/graykode/abtop/releases/tag/v0.5.5) | v0.5.5, 2026-09-14; MIT | Existing targeted star disposition | Optional operator view. Its JSON mode avoids summary inference, but snapshots contain private transcript-derived context. TUI and `--once` summaries can invoke Claude. |
| [restic](https://github.com/restic/restic/releases/tag/v0.19.1) | v0.19.1, 2026-07-05; BSD-2-Clause | Existing star disposition | Useful encrypted backup/restore candidate. An off-host destination, consistent source exports, password recovery and actual restore acceptance remain pending. |

The baseline Collector configuration lacked host-capacity collection. Its already adopted [contrib v0.161.0 receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.161.0/receiver/hostmetricsreceiver/README.md) documents the component name `host_metrics`, with selected scrapers and collection intervals. Extending that process is the smaller first step. Subsequent configuration validation and actual host metrics belong in separate runtime evidence; this source finding does not prove delivery, Windows host coverage or GPU monitoring.

OpenLIT's [release README](https://github.com/openlit/openlit/blob/openlit-2.1.0/README.md) and [coding command source](https://github.com/openlit/openlit/blob/openlit-2.1.0/cli/internal/coding/cmd.go) document per-vendor installation. Its [Codex transcript reader](https://github.com/openlit/openlit/blob/openlit-2.1.0/cli/internal/coding/hook/codex/transcript.go) confirms that this is more than a metrics dashboard. The platform release tag is not a verified CLI binary/package version. No OpenLIT commands were run, and the adopted local stack has no accepted trace-storage pipeline.

The abtop distinction is source-backed: [`src/lib.rs`](https://github.com/graykode/abtop/blob/v0.5.5/src/lib.rs) calls `tick_no_summaries()` for `--json`, while `--once` calls `app.tick()` and waits/retries summaries. Its [privacy documentation](https://github.com/graykode/abtop/blob/v0.5.5/README.md#privacy) describes the richer transcript-derived JSON fields. Do not export a raw snapshot as public evidence or assume every mode is model-free.

For restic, the prospective upstream sequence is `init`, `backup` of an application-consistent export directory, `check --read-data`, then `restore latest --target` an empty owned directory. [Integrity checking](https://restic.readthedocs.io/en/stable/045_working_with_repos.html) and [restore behavior](https://restic.readthedocs.io/en/stable/050_restore.html) are distinct checks. A same-machine encrypted copy alone does not establish recovery from host loss, and arbitrary copies of live databases are not accepted consistent exports.

No new memory or RAG replacement is warranted by this bounded release check. Source freshness, local operational visibility and backup recovery are different concerns from retrieval quality, provider accounting and maximum token efficiency; each requires its own acceptance scope.
