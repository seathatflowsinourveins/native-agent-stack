# P1 freeze and partial native execution

This artifact qualifies a proposed replacement for the existing required CI
scanner. It adds no security gate, local hook, host configuration or install.
The current result is **no swap**: Betterleaks fails the retained unprefixed40-hex
controls, introduces99 unreviewed history locations, and has no completed
CredData quality arm. The required Gitleaks CI scanner remains in place.

The frozen inputs are [`preregistration.json`](preregistration.json), SHA256
`5191f057bf6b8708c39b08c6a7f2a42d74099f831778c698d9f00bae875b54c3`.
It was written before any scanner arm and remains unchanged. Source-review
clarifications recorded before fixture/corpus arms are separately preserved in
[`envelope-clarifications.json`](envelope-clarifications.json).
[`run-record.json`](run-record.json) carries the commands, retained failures,
scope and pending prerequisites; [`returned-summary.txt`](returned-summary.txt)
retains safe lines of actual returned output. Location projections remove all
content, rules, authors and other native fields; private redacted native JSON
and observer traces remain in the lane's isolated cache.

| Native check | Gitleaks8.30.1 | Betterleaks1.9.0 |
| --- | ---: | ---: |
| History findings / unique locations | 0 /0 | 99 /99 |
| History wall seconds with tracing | 153.59 | 410.35 |
| History max RSS KiB | 428044 | 2391676 |
| Observed history network syscalls | 0 | 0 |
| Unchanged fixture methods run | 23 | 23 |
| Fixture failures | 0 | 4 in3 methods |
| Fixture errors/skips | 0 /0 | 0 /0 |

Four failures are d2, d4 twice, and d5. They retain the old unprefixed40-hex
class contract; no exception is accepted. The99 novel history locations are
unreviewed detections, not asserted false positives. Each arm ran once under
the same observer envelope, so timings are observations, not a general
performance ranking. The native scans reported different byte totals and
cannot establish merge-resolution coverage for100 merges in the1039-commit
graph. The2MB/archive0 limits also require labelled skip accounting before
complete-corpus acceptance.

Current Samsung/CredData's legacy Gitleaks report adapter passes an empty rule;
the current scorer requires a native metadata category. A field-only JSON
conversion cannot score this arm. Quality execution and acquisition are held
under lane Q5, due before2026-10-20, until the native contract is settled.
No own scorer, label-derived category oracle or historical-corpus substitution
is implemented. The project's native load interface is cited in the
[decision](../../../docs/decisions/2026-10-05-betterleaks-p1-freeze.md).

The Betterleaks author publishes full-scanner CredData F1.8922 with a modified
config and a replacement scorer. It is prior publication evidence rather than
this run's quality score: [author](https://lookingatcomputer.substack.com/p/rare-not-random),
[official mirror](https://www.aikido.dev/blog/token-efficiency-secrets-scan).

The new glue projects native positions only, preserving spans/columns/history
commits and counting rule duplicates. Its12 checks plus6 existing completion-
error tests pass. These and the unchanged synthetic controls are local
integration evidence. Upstream Go suite execution is absent (Go unavailable),
and source/CI review is not promoted to upstream native acceptance. Clean
release archives were checksum verified; Betterleaks's GitHub immutable
release attestation also verified, without a builder-provenance claim.

The independent critic found the fixture envelope mismatch, labelled skip
coverage, parser ambiguity and native field-source omissions. Corrections
retain the original freeze, tighten invalid roots/duplicate JSON keys, and
explicitly hold all unresolved coverage. The next sweep must revisit the
native scoring contract, same-span value/label ambiguity,100 merge resolutions,
labelled size/archive skips and99 unreviewed locations. No host apply or merge
is authorized by these results.
