# Gap wave 2: us-equities / research-factors-ml (2026-09-23)

This directory holds the executed checks for the nine open gaps assigned to this
layer: 0, 1, 5, 6, 7, 9, 10, 13 and 14. Their indices come from crosswalk PR #85
at main 92bb279. [preregistration.json](preregistration.json) was committed in
99efc32 before any check ran. Five fix rounds were added later, each dated when it
was written: the Nautilus audit rounding rule; the split of the forecast
comparison after the first attempt was stopped; and the detector negative
controls, the Ljung-Box degrees of freedom and the merge metadata raised by an
independent Codex review; (fix round 4, 15:36:22Z, on a re-dispatch) the six
gap-5 candidates that had not run; and (fix round 5, 15:59:30Z) the controls and
tolerance raised by a Codex review of fix round 4. [results.json](results.json) is
generated from the receipts by
`blueprints/gap-wave2-20260923/us-equities__research-factors-ml/build_receipts.py`.
Raw outputs are under [raw/](raw/), and [raw/MANIFEST.json](raw/MANIFEST.json)
lists the original and committed sha256 for each file. Host paths were replaced
with `$HOME`, and UUIDs (engine event and order identities, Codex session ids)
with `<uuid-redacted>`.

| Gap | Outcome | What ran | What remains |
| ---: | --- | --- | --- |
| 0 | advanced | Frozen selections from 20 development folds and the reserved segment, run in a NautilusTrader 2.0.0rc5 BacktestEngine with RAW and dividend-adjusted (ADJ) price arms, fills at the open, 10 bp per side fee, exact cash and fill reconciliation, and per-position PnL within 0.01 USD. RAW fill ratios equal `evaluate.label` for 138/138 episodes. | Point-in-time universe, total-return labels in `evaluate.py`, alpha, and in-engine dividend crediting (peer-owned SimulationModule). |
| 1 | advanced | Purge/embargo arms Z-check, Z-leaky, P6 and P6E5, with fold-boundary assertions, plus Z-choose and P6-assert negative controls (both raise). Selections are identical in all 20 folds. Ljung-Box test included. | Samples are not independent: momentum60 labels are autocorrelated at lags 2-4 (p<0.01). |
| 5 | advanced | All 15 candidates now have a retained execution on the frozen data. Rounds 1-3: c2 arcticdb, c3 sktime, c4 alphalens, c5 chronos, c6 tsfresh, c10 river, c12 statsforecast, c15 arch and c20 statsmodels. Fix rounds 4-5 (`extra_arms.py`): c14 docling, c17 ray-serve, c18 timesfm and c21 sentence-transformers met their pass criteria. c9 haystack ran but returned the right document for only 182 of 216 keyed BM25 queries. c24 Qlib ran, but 294 of its 9066 values miss the preregistered rtol-only tolerance (all are within 1e-6 absolute). | c9 and c24 failed their preregistered criteria; redesigned tests would need their own preregistration. None of this is accuracy or alpha acceptance. |
| 6 | advanced | Preregistered per-fold MAE comparison over the 20 folds: chronos-bolt-small vs statsforecast gives -0.00083, 95% CI [-0.00179, 0.0000076], so no difference is resolved. | The winner set is still not a performance ranking; linking the result to the verdict belongs to the ledger owner. |
| 7 | advanced | Kronos-small vs naive: +0.0247, 95% CI [0.0179, 0.0319]. Naive is better, and Kronos wins in only 2 of 20 folds. | The packet `evidence_refs` link was not made (read-only here). |
| 9 | deferred | Not run: needs the Alpaca paper account. | Owner: sota-workflow-resolution. |
| 10 | advanced | The same Nautilus run with dividend-inclusive bars, a fee model and reconciled cash. Volume participation is at most 0.0000844. | Realistic fills, capacity, financing and in-engine dividend cash. |
| 13 | advanced | statsforecast, chronos and statsmodels ARIMA per fold with bootstrap intervals. No superiority is resolved. | Feature-extraction and financial-NLP alternatives were not compared. |
| 14 | advanced | Kronos vs naive (as gap 7). c13 backtest-expert skill vs control on a seeded five-defect fixture, run with Codex (2 runs each): every run found 5/5 defects, so the fixture hit its ceiling. | A harder fixture or more runs; a native Claude harness run; packet `evidence_refs` linkage. |

Evidence class throughout is local integration: upstream libraries and engines ran
on this host against the plan's frozen LEAN inputs. None of this is upstream
acceptance, broker execution or alpha evidence. The first forecast attempt was
stopped at the 20-minute bound during the CPU Kronos stage. It is kept in
`raw/fcmp/logs__fcmp-attempt1.stderr`. Its rerun put Kronos on the local GPU,
which departs from the CPU wording in the preregistration.

Fix round 4-5 notes. A Codex review of fix round 4 found that the Qlib check had
added an absolute tolerance the preregistration did not allow. It also found that the
haystack absent-key control could not fail and that TimesFM and MiniLM had no injected
control. Fix round 5 reran those arms with the preregistered tolerance and added the
missing controls, which is why c24 is now recorded as failing. The Ray Serve arm needed `jinja2`, which the `ray[serve]==2.58.0`
metadata does not declare. Its second attempt ran Ray with the host LAN address as its
node IP, so the result of record is the third attempt, run in an unprivileged network
namespace that contains only loopback. The docling arm also ran without network access.
TimesFM 2.5 on the same 783 fcmp forecasts is not resolved against either naive or
chronos-bolt-small (dev mean fold MAE 0.018658, against 0.018682 and 0.018623). That
result is recorded in receipt 5 only; receipts 6 and 13 are unchanged.

## Coordinator note (2026-09-23): not-JSON captures

Eleven captured outputs across three layers were named `.json` but are not JSON: four empty stdout captures (`raw/bench-out/*.json` in document-retrieval), six stdout captures mixed with library or Ray warnings (research-factors-ml `raw/libs/libs__alphalens.json`, `raw/r4/*ray*.json`, `raw/r5/*ray*.json`), and a Grype `db status` output with a trailing line (`raw/grype-sdk/db-status.json`). The evidence-record discovery in `scripts/validate_convergence.py` parses every hash-listed `.json`, so at integration they were renamed to `.json.txt` with unchanged bytes. The receipts, raw manifests and `SHA256SUMS` name the new files, and the collectors now apply the same rule. Paths under `$HOME/.cache` in raw manifests are the names at capture time and are unchanged.

## Coordinator note (2026-09-23): captured requirements files

The probe requirements inputs under `raw/install/` are retained as `requirements*.in.captured`, bytes unchanged. They record what the probe installed, including old pins that the legacy research libraries require (for example pillow 9.5.0, requests 2.9.2 and pyarrow 9.0.0). They are not a manifest of anything the catalog installs. Under their original names, the OSV lockfile inventory required them to be scanned or excluded as fixtures, and a review of PR #132 pointed out that exclusion is reserved for deliberate positive controls. `raw/MANIFEST.json`, the gap-5 receipt and `collect_raw.py` name the new files.

## Coordinator note (2026-09-23): privacy sweep, third pass

RFC 1918 addresses replaced by `<lan-ip>` (loopback and 0.0.0.0 unchanged):

- `5-factor-forecast-econometrics-executions.json`: 1 replacement(s), sha256 `5ff57db7f59e...` -> `1e726b1a13db...`
- `raw/r4/r4__ray-attempt2-binds.txt`: 1 replacement(s), sha256 `928b0c7c8cae...` -> `7616dfd19783...`

Pins updated: `raw/MANIFEST.json` (`committed_sha256`, plus a `lan_ips_redacted` count; `original_sha256` and the raw `bytes` value are unchanged) and receipt 5 (`raw_outputs` committed_sha256). The address in `build_receipts.py`'s receipt text is redacted too. `collect_raw.py` now applies the same replacement; rerunning it from the cache reproduced all 128 files and `MANIFEST.json` byte for byte.
