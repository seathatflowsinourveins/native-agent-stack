# Data and research-evaluation source follow-up

Checked **September 19, 2026** against publication base `bfd03bc`. This is a
read-only review of **eight repositories and 29 selected source/configuration/test
files in two discovery waves**. Candidate commands below were not executed.
No packages, model calls, SEC retries, broker requests or paid compute were used.
The [machine-readable evidence](data-evaluation-followup.json) includes full pins,
dates, source URLs, byte/hash metadata and the precise scope of each finding.

## Public-star identity refresh

Native `gh api --paginate --slurp` returned all four pages of the signed-in
account's starred list. Filtering `private == false` retained **337 public
repositories**. There were **zero new repository identities** compared with the
prior public ledger:

| Prior name | Current canonical name | Verified GitHub repository ID |
| --- | --- | ---: |
| `huangruiteng/loopx` | `loopx-project/loopx` | 1255217938 |
| `iterative/dvc` | `treeverse/dvc` | 83878269 |

LoopX accounts for the one removed and one added raw starred name. Both API
routes resolved to the same repository ID. DVC was already canonicalized in the
catalog; this pass independently confirmed its existing alias. Original source
URLs, source pins, review dates and historical decisions remain unchanged.

The current raw public-name set has SHA-256
`c3e3abcfa39c36dbb5b86c6917c1b9807376034be83095c1664314d408a02cd1`.
A name-set hash changes on a transfer; this is not evidence of another starred
repository. The grand index remains **453 identities**, including **337 public
stars and 116 beyond**. Its core remains **152 cards / 147 unique repositories**.

## Wave one: existing candidates and underreviewed stars

The first wave reviewed six already indexed identities. Dates below are commit
dates, not package release dates. Licenses use repository SPDX metadata; unknown
is not inferred to be permissive.

| Repository and immutable source | Date; license | Selected source and resulting decision |
| --- | --- | --- |
| [dgunning/edgartools](https://github.com/dgunning/edgartools/tree/e23d04eba952e70310c0f62402f4c2523f9a44bf) | Sep 17; MIT | `edgar/settings.py`, `httpclient.py`, `httprequests.py`: explicit identity, cache and transport boundaries. Keep the existing candidate; a new wrapper does not resolve missing SEC access or reconstruct historical knowledge. |
| [unionai-oss/pandera](https://github.com/unionai-oss/pandera/tree/1c9a139436ae2657dd2cb100655b84138d7da443) | Sep 14; MIT | Pandas schema and backend containers: reusable contracts and collected errors. Strictness, uniqueness and coercion need explicit choices; a schema cannot prove source provenance or temporal availability. |
| [skfolio/skfolio](https://github.com/skfolio/skfolio/tree/c99fcf71349e2df4a7a1033ee85ca2e9ced9abee) | Sep 19; BSD-3-Clause | `_walk_forward.py`, `_combinatorial.py`: preferred existing evaluation candidate after defining labels and horizon. Purge defaults to zero; CPCV gaps count rows. A final chronological holdout remains necessary. |
| [xbtlin/ai-berkshire](https://github.com/xbtlin/ai-berkshire/tree/d608cf3c900f05f072415fe39d503393cf5edc8e) | Sep 19; MIT | `tools/report_audit.py`, `financial_rigor.py`, tests and installer: useful audit patterns, with float conversion and default 15% sampling capped at 30 items. Do not substitute this for exact-decimal verification of every cited numerical claim. |
| [virattt/dexter](https://github.com/virattt/dexter/tree/ecaed3011f24ea24ef687ab536aa7f22f7294038) | Aug 4; unknown SPDX | Finance API, rubric evaluator and package manifest: FinancialDatasets key/entitlement, extra model-judge invocation and browser postinstall. Overlaps the existing native worker; no new framework adoption is justified. |
| [treeverse/dvc](https://github.com/treeverse/dvc/tree/56e59829512ff134aa269099a2099587b810b4dd) | Aug 6; Apache-2.0 | `dvc/stage/serialize.py`, `commands/repro.py`: data/parameter lock provenance when datasets branch. Current receipts already cover the small workflow; hashes and dry runs do not prove PIT or data rights. |

The ai-berkshire installer also removes existing same-name skill directories
before copying its generated skills. Source review therefore does not justify
running its broad installer. Its numerical audit sampling and float conversion
are explicit implementation boundaries, not a finding that every report it
produces is wrong.

## Wave two: interval-aware validation alternatives

The second wave examined two **uncatalogued discovery leads**. Neither was added
to the 453-identity index or adopted stack.

| Repository and immutable source | Date; license | Selected source and resulting decision |
| --- | --- | --- |
| [eslazarev/purged-cross-validation](https://github.com/eslazarev/purged-cross-validation/tree/f742966834457b9b6e6c49f4498d8d6c86872223) | Sep 4; MIT | `_purge.py`, `_intervals.py` and purge/embargo property tests: interval-aware alternative for variable-duration labels. Version 0.1.6 and half-open interval conventions need independent acceptance against the chosen label contract. |
| [landtml/purgedcv](https://github.com/landtml/purgedcv/tree/aee3396422192d18bc30d376dfe9e31b2399abab) | Aug 12; MIT | `_splitter.py`, CPCV tests and `verify_leakage.py`: competing event-end implementation. The verification script downloads market data, so it is not an offline acceptance command. |

Both repositories declare the **`purgedcv` distribution/import name** despite
different implementations and APIs. Evaluate only one per isolated environment.
Neither fixes missing PIT source data, investment quality, a mislabeled horizon,
or a holdout used repeatedly for model selection.

Wave two added **two implementation alternatives and zero new actionable
categories**. The known categories remain acquisition/availability, data
contracts, temporal evaluation, report provenance and dataset versioning. This
is bounded saturation within the stated two waves, not a universal or permanent
claim that no useful project remains undiscovered.

## Prospective native acceptance commands

These are upstream command entrypoints and existing test paths at the recorded
pins. They remain **unexecuted** and require their declared development
dependencies in an isolated checkout. The full upstream test environments have
not been audited for every possible external action.

| Candidate | Command |
| --- | --- |
| EdgarTools | `python -m pytest tests/issues/regression/test_07lk121_settings_extraction.py -q` |
| Pandera | `python -m pytest tests/polars/test_polars_container.py -q` |
| skfolio | `python -m pytest tests/test_model_selection/test_walk_forward.py tests/test_model_selection/test_combinatorial.py -q` |
| ai-berkshire | `python tests/test_report_audit.py` |
| Dexter | `bun test src/evals/evaluator.test.ts` |
| DVC | `python -m pytest tests/unit/stage/test_serialize_pipeline_lock.py -q`; `dvc repro --dry` only previews an explicitly reviewed pipeline |
| eslazarev alternative | `python -m pytest tests/test_purge_embargo_properties.py tests/test_walk_forward.py -q` |
| landtml alternative | `python -m pytest tests/test_cpcv.py tests/test_sklearn.py -q` |

The next practical moves remain to resolve the honest SEC identity/access
prerequisite, then define a fixed research horizon and held-out evaluation using
the existing skfolio candidate. An interval-aware alternative becomes useful if
the chosen labels have variable duration. More repository installation cannot
substitute for either decision or for actual source and evaluation acceptance.
