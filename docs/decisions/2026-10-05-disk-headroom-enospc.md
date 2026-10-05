# Root-disk headroom after the 2026-10-04 ENOSPC incident

Date: 2026-10-05. Bounded job: job-062. Base: `43005a9f86ae6e5fcf0e4774ccf0cc3e7135e1d3`
(`origin/main` at builder start). Status: source-backed template and test changes;
coordinator integration and host rollout remain separate from this sandbox's acceptance.

This protects the north-star action of running US-equities research and historical
simulation on the NativeStack foundation without test scratch exhausting the disk
that also persists the Collector and Prometheus data. The builder stays in its own
worktree, leaves changes uncommitted and leaves `manifests/evidence.json` to the coordinator.

## Incident timeline and provenance

The incident facts below are **coordinator and peer observations supplied in the
job-062 brief**, rather than a new journal inspection or a reproduced disk outage.
NativeStack's root ext4 filesystem was reported as `/dev/sdd`, capacity `1007G`.
The rules select the root mountpoint rather than pinning that host's device name.

| UTC | Observation | Provenance |
| --- | --- | --- |
| 2026-10-04 about 23:55Z (19:55 EDT) | Root disk reached zero bytes free. | Coordinator/peer incident brief. |
| 2026-10-05 about 00:10Z (2026-10-04 20:10 EDT) | Root was again near full; Collector export failures and Prometheus `Scrape commit failed` appeared in the journal. | Coordinator's reported journal observations. |
| Recovery, exact time not supplied | Sessions removed their own scratch, worktrees and recursive copy; about 128–129 GiB became free. | Coordinator and peer observations. |
| Subsequent remediation, exact time not supplied | Coordinator installed the interim timer and reported archiving about 117G of its own finished state to Z:. | Coordinator observation; archive-log verification remains open below. |
| 2026-10-05 00:40:10Z–00:46:12Z | Five supplied CSV samples showed 128 GiB four times, then 127 GiB. | Builder read of `disk-headroom-samples.csv`; only `utc` and `free_gib` fields retained. |

Peer session **5f** identified the root cause: a full test-suite run put `TMPDIR`
inside its worktree. A test copied the checkout into a temporary destination that
was itself inside the checkout. The source therefore included that destination and
the copy recursed, consuming about 128 GiB within minutes. The builder did not
recreate a recursive copy or fill a real filesystem. Its regression control runs
the actual test-package setup with a mocked effective tempdir and a sentinel that
prevents any unsafe scratch allocation, even while the guard is absent.

## Selected upstream sources and comparison

The quick `search-first` workflow selected the already installed Collector,
Prometheus renderer and native `promtool`, plus Python's standard library. The
`diagnosing-bugs` workflow supplied a failing regression control before the guard.
The peer's established root cause makes another hypothesis search and a destructive
outage reproduction unnecessary. No package or exporter installation is needed.

- [prometheus/node_exporter v1.12.1 filesystem alerts](https://github.com/prometheus/node_exporter/blob/6044da783597cc3b57aef7580ddcdcff58a4ee99/docs/node-mixin/alerts/alerts.libsonnet#L7-L80)
  and [node-mixin defaults](https://github.com/prometheus/node_exporter/blob/6044da783597cc3b57aef7580ddcdcff58a4ee99/docs/node-mixin/config.libsonnet#L67-L91).
  The tag's [release notes](https://github.com/prometheus/node_exporter/releases/tag/v1.12.1)
  were checked through `gh api`. The requested `fc12f2c0ca65` identifies annotated
  tag object `fc12f2c0ca65e65f046a5583bbcaf996a578afb4`, which dereferences to commit
  `6044da783597cc3b57aef7580ddcdcff58a4ee99`; it is not itself a commit.
- [OpenTelemetry Collector Contrib v0.161.0 filesystem metadata](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/3f8455d8038a985398861171e5310bc9b4e988b2/receiver/hostmetricsreceiver/internal/scraper/filesystemscraper/metadata.yaml#L29-L62),
  [Unix state recording](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/3f8455d8038a985398861171e5310bc9b4e988b2/receiver/hostmetricsreceiver/internal/scraper/filesystemscraper/filesystem_scraper_unix.go#L15-L36)
  and [mount mode mapping](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/3f8455d8038a985398861171e5310bc9b4e988b2/receiver/hostmetricsreceiver/internal/scraper/filesystemscraper/filesystem_scraper.go#L135-L142).
  `manifests/stack.json` pins 0.161.0, and the installed binary returned
  `otelcol-contrib version 0.161.0`. Its [release notes](https://github.com/open-telemetry/opentelemetry-collector-contrib/releases/tag/v0.161.0)
  were checked through `gh api` before source review. The annotated tag resolves
  to commit `3f8455d8038a985398861171e5310bc9b4e988b2`.
- [shirou/gopsutil v4.26.8 Unix disk accounting, lines 21–30](https://github.com/shirou/gopsutil/blob/7d254a02800683e5a322b09e1843d3399f66f307/disk/disk_unix.go#L21-L30).
  The Collector's [hostmetrics go.mod, line 14](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/3f8455d8038a985398861171e5310bc9b4e988b2/receiver/hostmetricsreceiver/go.mod#L14)
  pins that version. This source, rather than `getMountMode`, establishes
  available/used/reserved byte semantics. The mount-mode source above addresses
  only the read-only exclusion. The stack's version is **0.161.0**, not 0.162.0.
- [Prometheus v3.15.0 native rule tests](https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/docs/configuration/unit_testing_rules.md),
  [vector matching](https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/docs/querying/operators.md#L300-L325)
  and [result label implementation](https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/promql/engine.go#L3438-L3457).
  The installed `promtool --version` returned 3.15.0, revision
  `5241a27fe3c6983549fccc32f6e65917408c63cd`, matching
  `observability/backends/pins.json`; its native `test rules --help` and
  [version changelog](https://github.com/prometheus/prometheus/releases/tag/v3.15.0)
  were checked. The new fixtures follow the repository's existing renderer and
  JSON-as-YAML `promtool test rules` pattern.
  Its [predict_linear semantics, lines 769–781](https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/docs/querying/functions.md#L769-L781)
  and [deriv semantics, lines 174–185](https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/docs/querying/functions.md#L174-L185)
  establish the gauge regression and minimum two float samples. A range length
  does not require waiting for that entire range before a forecast can evaluate.
- [CPython v3.13.15 temporary directory selection](https://github.com/python/cpython/blob/v3.13.15/Lib/tempfile.py#L159-L223),
  [gettempdir](https://github.com/python/cpython/blob/v3.13.15/Lib/tempfile.py#L299-L312),
  [resolved paths](https://github.com/python/cpython/blob/v3.13.15/Doc/library/pathlib.rst#L934-L949)
  and [path containment](https://github.com/python/cpython/blob/v3.13.15/Doc/library/pathlib.rst#L513-L530)
  provide the guard's native primitives. The sandbox's Python reported 3.13.15;
  `is_relative_to` is available since Python 3.9.
  [Native copytree, lines 550–596](https://github.com/python/cpython/blob/v3.13.15/Lib/shutil.py#L550-L596)
  supplies the copying API, and [unittest discovery, lines 265–280](https://github.com/python/cpython/blob/v3.13.15/Lib/unittest/loader.py#L265-L280)
  explains why `discover -s tests` imports modules without the test-package guard.

A scoped ai-memory query was rejected by the tool approval policy. The builder
used exact repository files and the primary sources above instead of treating a
memory result as authority. Source discovery remained scoped to this incident.

## Metric translation and alert policy

The Collector metadata declares `system.filesystem.usage` in bytes as a
non-monotonic sum, with `device`, `mode`, `mountpoint`, `type` and `state`
attributes; its states are `free`, `used` and `reserved`. The Unix scraper records
`Used`, `Free`, and `Total - Used - Free` respectively. At gopsutil v4.26.8,
`disk_unix.go:24` sets total from `Blocks`, `:25` sets free from **`Bavail`**,
and `:30` sets used from **`Blocks - Bfree`**, all multiplied by block size.
Consequently reserved is `(Bfree - Bavail) * block size`. Thus available bytes are
**free alone**, and total size is **free + used + reserved**. Reserved bytes
must not be counted as available to ordinary writers.

The existing [collector config](../../observability/collector/collector.yaml)
selects the `/` filesystem and exports with namespace `ecosystem`, producing
`ecosystem_system_filesystem_usage_bytes`. The percentage expressions use
`sum without(state)` for size, preserving each filesystem's other identity and
owner labels. `/ ignoring(state) group_left` retains the numerator's free-state
label so that the ratio matches its per-series forecast in `and`. `mode!="ro"`
ports node-mixin's read-only exclusion using the Collector's mount mode.

All five new rule definitions have `scope: local-ecosystem`. The two upstream
alert names each retain separate warning and critical definitions, as node-mixin
does; both severities can fire together.

| Alert | Severity | Condition | Delay |
| --- | --- | --- | --- |
| `EcosystemRootFilesystemSpaceFillingUp` | warning | Available <40% and six-hour trend predicts exhaustion within 24h. | 1h |
| `EcosystemRootFilesystemSpaceFillingUp` | critical | Available <20% and six-hour trend predicts exhaustion within 4h. | 1h |
| `EcosystemRootFilesystemAlmostOutOfSpace` | warning | Available <5% of size. | 30m |
| `EcosystemRootFilesystemAlmostOutOfSpace` | critical | Available <3% of size. | 30m |
| `EcosystemRootFilesystemBurstFill` | critical | `predict_linear(free[2m], 120) < 0` and free <50 GiB. | 15s |

The burst rule is a local incident-driven extension using native PromQL, not a
node-mixin default. A six-hour regression dilutes a sudden recursive copy, and
node-mixin's one-hour pending duration cannot notify before a minutes-long
128 GiB loss. Repair round 2 replaces the original 15m/1h forecast, 100 GiB cap
and 2m pending duration. That original policy could page on a completed ordinary
download and could miss a four- or five-minute runaway fill.

The absolute **50 GiB** floor approximates node-mixin's **5%** low-space warning
band on this roughly 1 TiB root. Severity is critical only when the two-minute
regression also predicts exhaustion within **120 seconds**. These are local
parameters, derived from the upstream near-space band and Prometheus regression
semantics, rather than new upstream defaults. A 30 GiB write starting at the
coordinator-reported current 151 GiB leaves 121 GiB; starting at the incident's
128 GiB recovery level leaves 98 GiB. Both stay well above the floor and the
native fixtures keep them silent throughout transfer and twenty minutes after
the writer starts. Below the floor, steady space and a slow write also stay
silent unless their forecast predicts imminent exhaustion. A large write on an
already depleted disk can correctly page; a filename or download label cannot
establish that the remaining headroom is safe.

The actual template cadence is **30s** for hostmetrics collection
([collector.yaml:27](../../observability/collector/collector.yaml#L27)), **1s**
batch timeout ([collector.yaml:269–270](../../observability/collector/collector.yaml#L269)),
and **15s** each for scrape and evaluation
([Prometheus template:2–3](../../observability/backends/templates/ecosystem-prometheus.yml.example#L2)).
For a fill fast enough that the two-minute forecast is already negative when free
space crosses the floor (faster than about 50 GiB per two minutes), the configured
worst-phase budget after crossing the low-space floor is approximately
**30 + 1 + 15 + 15 + 15 = 76s**, including the new pending interval. For slower fills
the page arrives roughly (120 s − observation delay − 15 s) before the forecast
reaches zero. In general, for a linear fill at r GiB/s the lead is about
min(50/r, 120) s − observation delay − 15 s, so a fill of 1 GiB/s or faster can exhaust
the disk before the page (independent delta reads, 2026-10-05); the copy guards and the
host's two-minute headroom guard cover that case. This is a configuration budget, not a measured
latency guarantee; transport, scheduling and an unestablished regression can add
delay. At least two float samples are required, and changing the slope can take
time to dominate the two-minute history. Alertmanager's initial **5s group_wait**
adds notification delay after firing, plus delivery time. The annotation states
the cadence budget and limitations.

The repaired runaway fixtures start with six hours at 128 GiB, then simulate
losing all 128 GiB in **four and five minutes**. They use 15s scrape/evaluation
ticks, repeat observations between 30s collector updates and deliberately delay
observations by 60s, exceeding the configured batch/scrape/evaluation phases.
The critical alert fires at **3m45s and 4m45s** from the hypothetical writer's
start, respectively, **15s before physical exhaustion**. It resolves when
recovered headroom becomes visible. The fixtures assert silence before the pending
duration elapses and confirm the slower node-mixin ports have not fired. This is
synthetic timing evidence, not a measured incident rate or live host acceptance.

An exhaustion with less remaining runway than the sampling/pending budget can
still outrun the rule. The TMPDIR guard and call-site copy guard prevent the
known recursive cause; the coordinator's independent **two-minute headroom
guard**, outside this repository, provides a separate best-effort observation
and cleanup path. A sub-two-minute fill can also outrun that timer. Alert rules
notify; they do not stop a writer or guarantee recovery.

The existing `EcosystemRootFilesystemLowSpace` (<5 GiB for 10m),
`EcosystemHostFilesystemMetricsMissing`, and all other rules remain intact.
The template now contains 26 rule definitions, up from 21.

## Guard, interim host remediation and notification route

`tests/__init__.py` now resolves both `tempfile.gettempdir()` and the repository
root and refuses the import if the effective tempdir is the root or a descendant.
The error instructs the operator to put `TMPDIR` in an existing writable directory
outside the repository, such as `/tmp` or the CI runner's external `RUNNER_TEMP`.
It executes before the package creates its hermetic Git scratch. Resolving first
also catches a symlink outside the checkout that points into it. A sibling with
the same name prefix is allowed. No CI bypass is used; external runner scratch
is covered by an actual successful subprocess import.

Package setup alone does not execute under `python3 -m unittest discover -s tests`:
CPython inserts `tests` into the import path as the discovery top-level directory.
The shared [repository_copy.py](../../tests/repository_copy.py) therefore checks
**resolved source and destination paths at the copying call site**, before native
`shutil.copytree` runs. It rejects the source itself, descendants, `..` aliases and
an external symlink into the source, with an instruction to use external scratch.
Both full-checkout copies in [test_catalog_freshness_propose.py](../../tests/test_catalog_freshness_propose.py)
now use it. The variant search also protected all six direct `ROOT` copies in
[test_wsl_retrieval.py](../../tests/test_wsl_retrieval.py), whose root is the WSL
retrieval fixture subtree. The tests inventory had no other full-checkout
`copytree` calls. This keeps the native copying options for safe sibling copies.

The regression imports the real catalog test module as a top-level module,
asserts `tests/__init__.py` never ran, and checks both real `setUpClass` copy sites
with an internal destination. A native copy sentinel makes the absent-guard
control harmless. A separate variant check catches direct unprotected `ROOT`
calls; it is a bounded regression check, not a general Python data-flow proof.

The coordinator reported installing **`disk-headroom-guard.timer` every two
minutes**, sampling free space into a CSV, notifying below **60 GiB**, and running
the supported `uv cache prune` below **30 GiB**. This independent interim host
guard can still act if Prometheus cannot persist data. Its installation and prune
execution were not rerun by the bounded builder, and cache pruning does not stop
a recursive checkout copy. The package check rejects internal effective TMPDIR
for package-based runs; the call-site guard also rejects explicit internal
destinations under top-level discovery. Unrelated copying tools remain outside
these guards' contract. Neither guard depends on Prometheus being writable.

The coordinator also reported moving about **117G of its own finished state to
Z:**. `archive-log.jsonl` was absent from the supplied incident folder at builder
inspection. That amount and ownership remain coordinator-reported; no archive
paths, private state, archive-integrity claim or independently verified transferred
total are published. The [sanitized receipt](../../evidence/artifacts/disk-headroom-enospc-20261005/receipt.json)
records the missing source and the five CSV samples. Do not add the reported
archive amount to the recovered free-space observations: their timing and overlap
were not established.

The current [Alertmanager template](../../observability/backends/templates/ecosystem-alertmanager.yml.example)
routes `local-ecosystem` through the default **`local-ntfy`** receiver to
`http://127.0.0.1:18080/ecosystem-alerts?template=alertmanager`, with
`send_resolved: true`. This is configuration evidence, not a new notification
delivery test. The coordinator's plan is **ntfy.sh once alerting slot 2604 lands**;
that hosted route is pending and is not configured by this change.

## Acceptance and retained failed attempts from round 1

These are **local integration checks over synthetic fixtures**, executed by the
installed upstream tools; they are not unchanged upstream test suites or a live
disk/notification E2E. The [receipt](../../evidence/artifacts/disk-headroom-enospc-20261005/receipt.json)
retains returned native results and distinguishes reported incident observations.

- Before the guard, `python3 -m unittest tests.test_tmpdir_guard` exited 1:
  4 tests ran, with 4 failed assertions across the repository/descendant and
  symlink rejection cases. The scratch sentinel kept the control harmless.
- With the requested job TMPDIR, the initial focused command exited 1:
  12 tests ran, with 8 promtool failures because Go test storage could not be
  created on that read-only path; the 4 guard tests passed. Python's tempfile
  machinery fell back to `/tmp`, whereas Go used the inherited `TMPDIR` directly.
  Sandbox approval is unavailable. The builder used writable `/tmp/job-062-disk-headroom`
  for subsequent native checks. That round did not pass acceptance with the exact
  requested TMPDIR. The repair-round sandbox permits that path; results below
  supersede the scratch-path limitation without erasing the failed attempt.
- The first writable full run exited 1: 40 tests, 5 failures and 3 optional
  PyYAML skips. Native output showed that plain one-to-one `ignoring(state)`
  removed `state` from ratio results, making the filling rules' `and` unmatched.
  Adding `group_left` preserved the label. The other failure was the existing
  native syntax test's old 21-rule count; it now expects 26.
- The corrected focused run passed all 12 tests. The full command
  `TMPDIR=/tmp/job-062-disk-headroom python3 -m unittest tests.test_observability_backends_alerts tests.test_tmpdir_guard`
  returned exit 0, **40 tests, 3 optional PyYAML skips**; all 8 filesystem-rule
  tests and all 4 guard tests executed. Fixtures check firing and resolution of
  every new definition, pending durations, reserved-byte semantics, steady space,
  the burst cap, other mountpoints and read-only roots.
- The same burst fixture with only the rendered burst rule removed returned a
  native promtool failure at 6h5m: expected one critical alert, `got:[]`. This
  disarmed-rule control demonstrates that the firing assertion detects absence.
- `promtool check rules` on `configure.py`'s render returned exit 0 and
  `SUCCESS: 26 rules found` using the pinned Prometheus 3.15.0 binary.
- `python3 scripts/validate.py` returned exit 1 with only expected evidence
  registry drift: SHA-256/byte-count mismatches for the three changed registered
  files (the rules template, `tests/__init__.py`, and the observability tests),
  plus the new receipt not yet being hash-listed. The coordinator owns registry
  reconciliation and registration of new artifacts.
- `git diff --check` returned exit 0. No commit was made; the proposed message
  is `.bounded-job-062/msg-1.txt`.

## Repair round 2 acceptance and CI scope

The call-site regression before repair exited 1 with **two failures**: eight
direct ROOT copies were unprotected, and the top-level catalog setup reached the
copy sentinel. After repair, all **nine guard tests** passed. The focused native
filesystem acceptance then passed all **nine rule tests**, including both fast
runaway timing cases and both ordinary 30 GiB transfer cases.

The existing observability test decorators **skip native promtool checks when
the pinned binary is absent**. The [validate workflow](../../.github/workflows/validate.yml#L233)
(`native-agent-stack@43005a9f86ae6e5fcf0e4774ccf0cc3e7135e1d3:.github/workflows/validate.yml:233–239`)
runs Python unittest, and no promtool provisioning was found in the inspected
`.github/workflows` files (`rg 'promtool|prometheus|observability/backends'` returned
no matches). Thus a green CI suite without that binary does not establish native
rule behavior. This change keeps the optional-binary convention and adds no CI
installation. Native execution on this sandbox with pinned Prometheus 3.15.0
provides the rule evidence recorded below; optional PyYAML structural skips are
reported separately.

All round-2 commands inherited the now-writable external job TMPDIR. Returned
results, including the dirty-tree attempt, are retained in the sanitized receipt:

- The full four-module working-tree run returned exit 1: **175 tests, one failure,
  three optional PyYAML skips**. The sole failure was the catalog freshness
  subprocess fixture's general publication-validator assertion, because it copied
  the five changed registered files and unlisted job receipt into its scratch.
  Its returned errors were exclusively the expected coordinator-owned registry
  drift; no guard or alert behavior failed. The oracle was not weakened.
- To execute that existing publication assertion, the same sources were copied
  into an external scratch snapshot. Only the snapshot's registry was reconciled
  with the existing [register_file implementation](../../scripts/host_receipts.py#L710)
  (`native-agent-stack@43005a9f86ae6e5fcf0e4774ccf0cc3e7135e1d3:scripts/host_receipts.py:710–729`).
  The source bytes were compared with this worktree before testing; scratch
  baseline validation passed. Native
  `python3 -m unittest tests.test_observability_backends_alerts tests.test_tmpdir_guard tests.test_catalog_freshness_propose tests.test_wsl_retrieval`
  then returned **exit 0, 175 tests, three optional PyYAML skips**. This is
  explicitly scratch-registry acceptance; the coordinator's working-tree
  `manifests/evidence.json` was verified unchanged.
- Direct working-tree execution of
  `python3 -m unittest tests.test_observability_backends_alerts tests.test_tmpdir_guard tests.test_wsl_retrieval`
  returned **exit 0, 91 tests, three optional PyYAML skips**.
  `python3 -m unittest discover -s tests -p test_tmpdir_guard.py` returned
  **exit 0, nine tests**, including the real top-level catalog copy sites.
- Standalone pinned `promtool check rules` on `configure.py`'s rendered template
  returned **exit 0, SUCCESS: 26 rules found**. Standalone `promtool test rules`
  returned **exit 0** for all **nine filesystem fixture documents / 13 cases**,
  exported from the same repository test methods with their original intervals
  and expectations. It evaluated actual rules and series; fixture construction
  is not claimed as an extra native test result.
- Working-tree `python3 scripts/validate.py` returned **exit 1**, with exactly
  the expected registry drift: hash/byte mismatches for the five changed
  registered inputs and the unlisted job receipt. The returned error set was
  compared with those eleven expected messages. No source, schema or rule error
  was present. The coordinator owns reconciliation of that registry.
  `git diff --check` returned **exit 0**.

No commit was made. `.bounded-job-062/` remains **untracked**; `msg-1.txt` is kept
and the new proposed message is `msg-2.txt`. Handoff messages are not evidence
registry entries or tracked source changes.

## Corrections and anti-patterns verified during this unit

| Mistake | Correction | Verification path |
| --- | --- | --- |
| Calling `fc12f2c0ca65` the node_exporter tag commit. | It is the annotated tag object; pin its dereferenced commit separately. | `gh api repos/prometheus/node_exporter/git/ref/tags/v1.12.1`, then `gh api repos/prometheus/node_exporter/git/tags/fc12f2c0ca65e65f046a5583bbcaf996a578afb4`. |
| Assuming an ignored state label survives one-to-one PromQL arithmetic. | Preserve the numerator labels with `group_left` so forecast conjunctions match. | Prometheus v3.15.0 `promql/engine.go:3438–3457`, operators documentation, failed native fixture output and corrected firing/resolution fixtures. |
| Assuming an existing requested TMPDIR is writable in the builder sandbox. | Record the round-1 native read-only failure and permitted fallback. Round 2 permits the requested external path and reruns acceptance there. | Go promtool's returned read-only failures, round-1 `/tmp` checks and round-2 requested-path native checks. |
| Treating a 15m forecast and 2m pending interval as coverage for a four-minute outage. | Use a two-minute forecast, 50 GiB floor and 15s pending interval; disclose the approximately 76s configured cadence budget and faster-fill limitations. | Pinned Prometheus forecast semantics, repository collector/scrape/evaluation intervals, and four-/five-minute native fixtures. |
| Keeping a 100 GiB cap near routine host headroom. | Require approximately the upstream 5% near-space band plus predicted exhaustion within two minutes. | node_exporter v1.12.1 `config.libsonnet:84–91`; silent 30 GiB fixtures from 151/128 GiB and steady/slow depleted disks. |
| Assuming test-package setup runs during `discover -s tests`. | Guard every root copy at its call site using resolved source/destination containment. | CPython v3.13.15 `Lib/unittest/loader.py:265–280`; harmless failing control and successful real top-level copy-site regression. |
| Using mount-mode code as evidence of free-byte semantics. | Cite Collector metadata/state recording plus its pinned gopsutil `disk_unix.go:21–30`. | Collector v0.161.0 `receiver/hostmetricsreceiver/go.mod:14` and gopsutil v4.26.8 `Bavail`/`Bfree` accounting at the exact pin. |
| Inheriting a mount-mode citation at lines 149–157. | At v0.161.0 those lines are filter code; mount-mode mapping is at lines 135–142. Keep that citation solely for mode, and use gopsutil for byte semantics. | Exact pinned `filesystem_scraper.go` source fetch and `func getMountMode` line lookup; exact gopsutil `disk_unix.go:21–30` fetch. |

## Alternatives, completeness critic and overturn

**Install node_exporter itself:** it would duplicate the existing OTel hostmetrics
owner and add an install, scrape target and service lifecycle. The pinned Collector
already provides available, total-size components and mount mode, so port the
maintained node-mixin alert policy onto that owner instead. No extra install.

**Keep only the absolute 5 GiB rule or only adopt the unmodified long-window
policy:** the observed minutes-long exhaustion outpaces their pending delays.
Retain the original absolute rule as a backstop, adopt the upstream percentages
and forecasts, and add the bounded burst companion plus causal package/copy guards.

**Use the 3% critical space band or retain the original 100 GiB burst cap:** a
roughly 30 GiB floor leaves too little runway for the configured cadence under
the four-minute 128 GiB synthetic loss. The 100 GiB cap with a one-hour forecast
can page on an ordinary completed transfer. Choose the roughly 5% floor with a
two-minute forecast and test both cases with the pinned native evaluator.

**Rely on cleanup, archival or a larger disk:** these restore headroom but leave
recursive copying possible. Keep the coordinator's interim remediation while
preventing the initiating test condition. Automatic deletion of arbitrary
worktrees or active state is not part of this alert policy.

The completeness critic checked the byte metric, reserved capacity, read-only
mode, filesystem/owner label matching, slow and burst timescales, missing telemetry,
notification resolution, CI scratch, and archive provenance. The repair adds
actual collection/scrape/evaluation phases, short-runway false positives, ordinary
large downloads and top-level discovery to that comparison. Remaining modalities
are inode exhaustion, the Windows backing disk/VHD capacity, and writers outside
the Python test package. They need their own evidence and are not claimed covered
by this byte-space incident fix. The next alerting sweep should verify hosted
ntfy delivery and recovery once slot 2604 lands, and obtain the coordinator's
sanitized archive log. A new sensor is justified only by a demonstrated metric gap.

Overturn or retune this selection if a maintained node-mixin update supplies a
better evidenced burst policy; if measured ordinary scratch workloads create
repeated false positives at the 2m window/120s forecast/50 GiB floor/15s pending
setting; if a captured real burst with sufficient configured runway escapes it;
if root capacity changes enough to invalidate the absolute floor; or if the
existing OTel owner cannot reliably export the state and
mode semantics used here. Compare the candidate and retained policy with the
same native promtool fixtures plus sanitized observed workload traces, including
firing lead time and false notifications. Remove the interim host timer only
after the coordinator verifies deployed warning/firing/resolved delivery and
headroom recovery with the selected route. Revisit the guards if supported tests
no longer copy the checkout; an internal destination cannot be allowed for native
recursive copytree without a separately qualified exclusion strategy.

## Coordinator acceptance at the committed head (2026-10-05T03:38:48Z)

The builder's recorded runs predate the commit. The coordinator re-ran the acceptance on the committed content
(6d1a37b8d on main 4c897418f, registry 4572df248), with TMPDIR outside the checkout:

| Command | Exit | Result |
| --- | --- | --- |
| `python3 -m unittest tests.test_tmpdir_guard tests.test_observability_backends_alerts tests.test_catalog_freshness_propose tests.test_wsl_retrieval` | 0 | 175 tests OK, 3 skipped (optional PyYAML); the 9 `RootFilesystemRuleTests` ran pinned promtool 3.15.0 `test rules` |
| `python3 -m unittest discover -s tests -p test_tmpdir_guard.py` | 0 | 9 tests OK |
| `promtool check rules observability/backends/templates/ecosystem-prometheus-rules.yml.example` | 0 | SUCCESS: 26 rules found |
| `python3 scripts/validate.py` | 0 | passed (10,094 hashed files, 202 receipts) |

