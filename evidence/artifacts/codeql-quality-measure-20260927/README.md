# CodeQL quality-suite measurement (2026-09-27)

Plan move M4 measured the CodeQL quality suites before any change to code
scanning. This receipt holds that measurement. The decision is in
[`docs/decisions/2026-09-27-codeql-quality-suites.md`](../../../docs/decisions/2026-09-27-codeql-quality-suites.md).

- **Commit:** `ba1700adc6557b03d3c9336c4d3a951791fc8de5` (`catalog_revision`).
- **Engine:** CodeQL CLI 2.27.1, the version live default setup used at that
  commit. It came from the verified `codeql-bundle-v2.27.1` release of
  `github/codeql-action`.
- **Languages:** python, javascript-typescript and actions.
- **Suites, all from the bundle:** default (`code-scanning`),
  `security-extended`, `code-quality` and `security-and-quality`.

## Results

| Suite | python | javascript-typescript | actions |
| --- | --- | --- | --- |
| default (`code-scanning`) | 16 (error 16) | 1 (warning 1) | 0 |
| `security-extended` | 50 (error 17, warning 33) | 2 (warning 2) | 0 |
| `code-quality` | 979 (error 60, warning 418, note 501) | 188 (error 13, warning 173, note 2) | 0 (the suite selects 0 queries) |
| `security-and-quality` | 1072 (error 107, warning 453, note 512) | 190 (error 13, warning 175, note 2) | 0 |

**Production parity.** For each language, the local default-suite results
equal the live default-setup analysis of the same commit, compared as
multisets of (rule, path, line, column). Python matches 16 = 16 results and
43 = 43 rules; javascript-typescript 1 = 1 and 87 = 87. Actions has 0 = 0
results, so only its rule set (17 = 17) is a non-vacuous match. The same
comparator reports a mismatch when given the code-quality SARIF instead.

**Triage.** The 20 stratified code-quality alerts split into:
- 8 false positives;
- 8 real and actionable: 7 hygiene findings and 1 reliability finding;
- 4 real but not actionable, because they sit in captured third-party
  pages under `evidence/`.

None of the 6 error-level alerts in the sample is actionable. A supplement
of 6 alerts from gate-relevant rules that only the broader suites add
contains 6 false positives.

Per-rule counts, the lane split and the overlaps are in `counts.json`. Each
verdict has its reason in `triage.json`.

## Files

| File | What it is | Evidence class |
| --- | --- | --- |
| `receipt.json` | Versions, bundle digest and verification with negative controls, sanitized argv with timings and exit codes, the live default-setup records, parity, evidence classes, sources and limitations | mixed; each claim is labelled |
| `counts.json` | Per language and suite: results, rules, levels, security-severity bands, lanes, directories and per-rule counts; parity and its negative control; suite overlaps | upstream-unchanged output, summarized by our integration |
| `triage.json` | The 20-alert sample and the 6-alert supplement with verdicts, tallies and the volume-weighted extrapolation | our-integration (this unit's judgment) |
| `heuristics.json` | Structural checks over whole rule populations, such as callee resolution, never-returning calls, literal boundaries and evidence share | our-integration |
| `triage_verdicts.json` | The verdicts as authored input, each tied to its rule, path and line | our-integration |
| `run.sh`, `summarize_sarif.py`, `sample_alerts.py`, `triage.py` | Thin glue around the upstream CLI and SARIF 2.1.0; each file names its sources | our-integration |

## Reproduce

1. Download `codeql-bundle-linux64.tar.gz` from release
   `codeql-bundle-v2.27.1` of `github/codeql-action` into a scratch
   directory outside the checkout.
2. Verify it before running anything: check the release asset digest,
   `sha256sum -c` against the checksum asset, and run
   `gh release verify-asset codeql-bundle-v2.27.1 <file> --repo github/codeql-action`.
3. Extract the bundle and copy `run.sh` next to the extracted `codeql/`
   directory.
4. Run `run.sh <worktree at the commit>`. It writes `db/`, `sarif/`,
   `logs/` and `steps.tsv` beside itself, so keep that directory outside
   the checkout.
5. Run the three `security-extended` analyses with the argv listed in
   `receipt.json`.
6. Fetch the live SARIF for each language as `live/<category>.sarif` (the
   command is in `receipt.json`).
7. Run the summaries:
   - `python3 summarize_sarif.py sarif live counts.json`
   - `python3 sample_alerts.py sarif sample.json`
   - `python3 triage.py sarif <worktree> sample.json triage_verdicts.json .`

Rerunning the committed scripts on this unit's SARIF reproduced `counts.json`,
`triage.json` and `heuristics.json` byte for byte.

## Sanitization

Raw SARIF, the databases and the logs stay in the unit's scratch directory,
because SARIF records the absolute source root. This receipt publishes
instead:
- the SHA-256 of every SARIF file;
- counts derived from them;
- repository-relative locations.

Scratch and worktree paths are replaced by `<dl>` and `<worktree>`. The
receipt holds no credential values.
