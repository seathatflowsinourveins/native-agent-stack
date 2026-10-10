# Scan large CI targets with an explicit generated-file exclusion — 2026-10-10

The blanket `--max-target-megabytes 2` flag made native secret scans return no
findings for large targets. This change removes it from all four history/dir
commands in `validate.yml`, using the vendor's default 0. The config now excludes
only `^docs/ecosystem/index\.html$`. That generated HTML path is the deliberate
incomplete-coverage boundary; neighboring and prefixed paths remain covered.

## Primary mechanism and correction

- [gitleaks/gitleaks v8.30.1@83d9cd684c87d95d656c1458ef04895a7f1cbd8e:cmd/root.go:84](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/cmd/root.go#L84) sets the default cap0. [cmd/directory.go:62](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/cmd/directory.go#L62) multiplies by decimal1,000,000; [sources/files.go:93](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/sources/files.go#L93) skips files strictly larger than that limit. [detect/detect.go:431](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/detect/detect.go#L431) compares the integer-MB fragment length, so cap2 skips at3,000,000 bytes in git mode.
- [betterleaks/betterleaks v1.8.1@5eab48332cc48565864514e3bc6de89df091a7c4:cmd/root.go:92](https://github.com/betterleaks/betterleaks/blob/5eab48332cc48565864514e3bc6de89df091a7c4/cmd/root.go#L92) also defaults to0. [cmd/directory.go:66](https://github.com/betterleaks/betterleaks/blob/5eab48332cc48565864514e3bc6de89df091a7c4/cmd/directory.go#L66) supplies the decimal limit to [sources/files.go:85](https://github.com/betterleaks/betterleaks/blob/5eab48332cc48565864514e3bc6de89df091a7c4/sources/files.go#L85). Its git source has no corresponding size option; the obsolete flag is removed there as well.
- Gitleaks applies the explicit path pattern through [config/allowlist.go:136, PathAllowed](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/config/allowlist.go#L136); line135 is its comment.
- Betterleaks v1.8.1 translates configured path patterns into its prefilter at [config/translate_filters.go:96](https://github.com/betterleaks/betterleaks/blob/5eab48332cc48565864514e3bc6de89df091a7c4/config/translate_filters.go#L96). The expression checks `attributes["path"]` at 96–108. [detect/detect.go:436, SkipFunc](https://github.com/betterleaks/betterleaks/blob/5eab48332cc48565864514e3bc6de89df091a7c4/detect/detect.go#L436) evaluates that prefilter and supplies the source callback. [sources/common.go:55](https://github.com/betterleaks/betterleaks/blob/5eab48332cc48565864514e3bc6de89df091a7c4/sources/common.go#L55) applies it to file paths; [sources/files.go:117](https://github.com/betterleaks/betterleaks/blob/5eab48332cc48565864514e3bc6de89df091a7c4/sources/files.go#L117) and :124 skip those files. The Git source sets the changed path at :423 and applies `ShouldSkip` to its commit attributes at [sources/git.go:436](https://github.com/betterleaks/betterleaks/blob/5eab48332cc48565864514e3bc6de89df091a7c4/sources/git.go#L436). The callback at :460 is propagated into the archive-blob `File` branch at :449–461; it is not the text-diff path. Its `PathAllowed` helper has no non-test caller at this pin; the earlier shared-helper citation did not name its production mechanism.

The exact exclusion is tested with both native binaries, and adjacent/prefixed
paths still yield findings. Focused source-claim controls require the pinned
prefilter/callback citations and the gitleaks function's corrected line; restoring
the earlier mechanism paragraph fails both controls before this correction.

The earlier cap2 “vendor default” interpretation is corrected by the pinned
CLI definition and reproduced boundary. Directory scans can log a skip warning
and still exit 0 with no finding; git's fragment skip is a debug message. Neither
is acceptable coverage for the current large manifests/catalogs. The former
guide's git-only coverage description was wrong and is updated. Dated prior
history measurements retain their original scope.

## Measured red and green

The new regression extracts the actual CI scanner arguments, uses the existing
fabricated GitHub-PAT fixture, and pads tracked-shape files to exact byte sizes.
Reports are fully redacted. Git fixtures have a clean base and one target commit;
their scan is the explicit PR-shaped base..HEAD range. The full-history runtime
is not measured or executed locally.

| Native scanner mode | Bytes | Before: cap2 | After: no cap |
| --- | ---: | --- | --- |
| gitleaks git | 2,000,001 | detected | detected |
| gitleaks git | 3,000,000 | missed, rc0 | detected |
| gitleaks dir | 2,000,001 | missed, rc0 | detected |
| gitleaks dir | 3,000,000 | missed, rc0 | detected |
| betterleaks dir | 2,000,001 | missed, rc0 | detected |
| betterleaks dir | 3,000,000 | missed, rc0 | detected |

Betterleaks 1.8.1 was independently measured: 1,999,999 and 2,000,000 bytes detect;
2,000,001, 2,999,999 and 3,000,000 miss under cap 2. Its report-only `--exit-code 0`
is retained; detection assertions inspect the report, not that exit status.
The initial completed red run has 8 failed assertions and no harness errors.
The initial green module gives 4 tests passing; larger required suites include
all preexisting allowlist and workflow-policy controls.

Local Linux WSL GNU-time measurements for the repaired boundary targets:

| Scanner/mode | Bytes | Elapsed seconds | Peak RSS KiB |
| --- | ---: | ---: | ---: |
| gitleaks git | 2,000,001 | 0.65 | 110700 |
| gitleaks git | 3,000,000 | 0.76 | 135340 |
| gitleaks dir | 2,000,001 | 0.43 | 62644 |
| gitleaks dir | 3,000,000 | 0.45 | 61048 |
| betterleaks dir | 2,000,001 | 0.31 | 43708 |
| betterleaks dir | 3,000,000 | 0.33 | 46332 |

[measurements.json](../../evidence/artifacts/secret-scan-large-targets-20261010/measurements.json)
records exact pins, red/green output hashes, boundary results and measurement
limits. These are native scanner invocations on fabricated inputs in local
Linux, not hosted production performance. The native Ubuntu CI jobs run the
same regression against their checksum/signature-verified binaries and print
elapsed/peak-RSS measurements for runner-specific acceptance after publication.
No new package or YAML parser is installed; the existing stdlib job parser is used.

## Timer portability and full-scan acceptance

The initial fixture helper incorrectly treated any `/usr/bin/time` as GNU time
and labeled an existing timer as Linux. It now checks `platform.system()`, file
availability and the timer's successful GNU `--version` response. Darwin and an
existing non-GNU timer execute the scanner directly with an accurate platform
and an explicit unmeasured label. Simulated BSD-option rejection reproduces the
old detection failure; Darwin/non-GNU fallback and native Linux GNU measurement
controls pass. `ScannerTimerTests` runs in the hosted job with the installed,
verified gitleaks binary, alongside the large-target controls. This is not a
native macOS execution claim.

GNU time's supported `%e`, `%M` and `%x` formats measure elapsed seconds, peak RSS
in KiB and the command exit status. The native Linux workflow verifies GNU time
and wraps all four actual uncapped scanner commands, preserving their reviewed
arguments, redaction, HEAD ancestry scope and native exit status. The canary
parser consumes the scanner options behind this timing prefix. The shipped-step
control retains twelve scanner/status combinations in fresh Git fixtures;
restoring the prior unmeasured steps fails all twelve receipt assertions.

Each command emits a `full-*.metrics.json` resource receipt with the exact
checked-out commit, native event/ref/run/attempt, tool version, actual result and
workflow/config/ignore-file hashes. Only resource receipts are uploaded; raw
betterleaks reports remain on the runner. The receipts are named
`secret-scan-metrics-gitleaks-RUN_ID-ATTEMPT` and
`secret-scan-metrics-betterleaks-RUN_ID-ATTEMPT`. `scripts/secret_scan_metrics.py`
records numeric measurements and safe scope metadata, without paths to the host
home, credentials or matched values. A failed metric writer fails a successful
scan step; a nonzero scanner status keeps its original status.

After publication, retain these four native receipts and the jobs API's start
and completion times. Full job duration includes checkout, installation,
verification, regressions, scans and post steps. Compare it with the unchanged
600-second gitleaks and 1,200-second betterleaks budgets and report the remaining
margin. The six local fixture figures above remain a separate measurement;
they do not establish full-repository timeout or memory acceptance. No local
unbounded-history measurement is performed.

Native Ubuntu full production measurements were retained from
[run38053675250](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/38053675250),
attempt 1, `pull_request`, `refs/pull/964/merge`, exact checkout
`f2f10412c68a859800b2bcad034c8ab639fd6f2e`. The workflow/config hashes in the
resource artifacts bind those figures to the source used for that run. This
checkout revision records evidence provenance; it is not a fixture/dependency
pin and does not substitute for fresh CI at the landing head.

| Actual uncapped production scan | Seconds | Peak RSS KiB | Exit status | Findings |
| --- | ---: | ---: | ---: | ---: |
| gitleaks 8.30.1 git, HEAD ancestry | 37.42 | 745128 | 0 | 0 |
| gitleaks 8.30.1 dir | 14.52 | 126772 | 0 | native gating status; no JSON report |
| betterleaks 1.8.1 git, HEAD ancestry | 19.01 | 1074456 | 0 | 1687, report-only |
| betterleaks 1.8.1 dir | 4.16 | 147360 | 0 | 1685, report-only |

The complete native jobs include checkout, installation, verification,
regressions, both scans, uploads and post steps. Gitleaks
[job114217705392](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/38053675250/job/114217705392)
completed SUCCESS in 116 seconds of its 600-second limit, leaving 484 seconds.
Betterleaks [job114217705237](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/38053675250/job/114217705237)
completed SUCCESS in 64 seconds of its 1,200-second limit, leaving 1,136 seconds.
Artifacts are `secret-scan-metrics-gitleaks-38053675250-1` (11670637536) and
`secret-scan-metrics-betterleaks-38053675250-1` (11670032999), downloaded and
retained with native receipt hashes by the lane. Both scanner jobs passed;
that full run's separate inventory-grant failure was corrected by adding the
exact repository grant and a manually measured count of 93. Betterleaks' finding
counts remain report-only, distinct from gitleaks' gating result.

Mechanism sources: [GNU time manual](https://www.gnu.org/software/time/manual/time.html),
version1.9 (installed package1.9-0.4; native `--help`/`--version` and shipped info
manual independently checked), and [CPython v3.12.3:Doc/library/platform.rst](https://github.com/python/cpython/blob/v3.12.3/Doc/library/platform.rst)
for `platform.system()`'s Linux/Darwin labels. Native Linux step execution
reproduces GNU format/output/quiet/status behavior; the BSD controls are
simulations at the external command boundary.

The current base is main `c8a29c3ee9b4337564165d9e588b3fe81e8ba817`. It carries
the landed large G5 catalog, strengthening the need to scan large current files.
Scanner versions, event/history scope, archive-depth0, reviewed fingerprints,
redaction, report-only betterleaks status, permissions and action pins retain
their existing contract. This change does not perform credential validation or
scan unrelated branches. The separately owned event-scope PR reconciles at the
CC landing turn.
