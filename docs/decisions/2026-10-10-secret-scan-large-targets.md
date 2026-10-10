# Scan large CI targets with an explicit generated-file exclusion — 2026-10-10

The blanket `--max-target-megabytes 2` flag made native secret scans return no
findings for large targets. This change removes it from all four history/dir
commands in `validate.yml`, using the vendor's default0. The config now excludes
only `^docs/ecosystem/index\.html$`. That generated HTML path is the deliberate
incomplete-coverage boundary; neighboring and prefixed paths remain covered.

## Primary mechanism and correction

- [gitleaks/gitleaks v8.30.1@83d9cd684c87d95d656c1458ef04895a7f1cbd8e:cmd/root.go:84](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/cmd/root.go#L84) sets the default cap0. [cmd/directory.go:62](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/cmd/directory.go#L62) multiplies by decimal1,000,000; [sources/files.go:93](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/sources/files.go#L93) skips files strictly larger than that limit. [detect/detect.go:431](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/detect/detect.go#L431) compares the integer-MB fragment length, so cap2 skips at3,000,000 bytes in git mode.
- [betterleaks/betterleaks v1.8.1@5eab48332cc48565864514e3bc6de89df091a7c4:cmd/root.go:92](https://github.com/betterleaks/betterleaks/blob/5eab48332cc48565864514e3bc6de89df091a7c4/cmd/root.go#L92) also defaults to0. [cmd/directory.go:66](https://github.com/betterleaks/betterleaks/blob/5eab48332cc48565864514e3bc6de89df091a7c4/cmd/directory.go#L66) supplies the decimal limit to [sources/files.go:85](https://github.com/betterleaks/betterleaks/blob/5eab48332cc48565864514e3bc6de89df091a7c4/sources/files.go#L85). Its git source has no corresponding size option; the obsolete flag is removed there as well.
- Both implementations use [config/allowlist.go:PathAllowed](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/config/allowlist.go#L135) for the explicit path pattern. The exact exclusion is tested with the native binaries, and adjacent/prefixed paths still yield findings.

The earlier cap2 “vendor default” interpretation is corrected by the pinned
CLI definition and reproduced boundary. Directory scans can log a skip warning
and still exit0 with no finding; git's fragment skip is a debug message. Neither
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

Betterleaks1.8.1 was independently measured:1,999,999 and2,000,000 bytes detect;
2,000,001,2,999,999 and3,000,000 miss under cap2. Its report-only `--exit-code 0`
is retained; detection assertions inspect the report, not that exit status.
The initial completed red run has8 failed assertions and no harness errors.
The initial green module gives4 tests passing; larger required suites include
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

The current base is main `c8a29c3ee9b4337564165d9e588b3fe81e8ba817`. It carries
the landed large G5 catalog, strengthening the need to scan large current files.
Scanner versions, event/history scope, archive-depth0, reviewed fingerprints,
redaction, report-only betterleaks status, permissions and action pins retain
their existing contract. This change does not perform credential validation or
scan unrelated branches. The separately owned event-scope PR reconciles at the
CC landing turn.
