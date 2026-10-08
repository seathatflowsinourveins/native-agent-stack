# Independent final-lock native 24-case acceptance assessment

Observed 2026-10-08T17:54:30Z. Result: **PASS within the exact native 24-case offline integration scope, with no receipt-binding defect found.** This is an independent read of the returned records and their source controls. No native acceptance, test, installer, runtime, provider, model, GPU, broker, service or configuration operation was rerun by this critic.

## Reviewed returned evidence

| Relative artifact | Bytes | SHA256 |
| --- | --- | --- |
| `request.json` | 1490 | `ed79585fa0af87da4ebda32bb8d62d3cc6e94cbf3da72e24d4f8d7b63396d7a5` |
| `receipt.json` | 5917 | `4a064e39026f205b8e2f273d396044b9145dbcb58a1510b8c9dbf45c56c5a2a5` |
| `native.stdout` | 1361 | `e176e06192e9d027669f42b58b86b395c3df3dfe9dc02a4e439917d23b906313` |
| `native.stderr` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The hashes and byte counts above were recomputed from the original provided files. The zero-byte stderr is empty. The supplied native completion record and receipt both report exit0. The actual output timestamps are **2026-10-08T17:48:39Z through 17:49:09Z**, a30-second interval; both timestamps agree with the receipt.

The original output was parsed directly. It contains exactly24 status lines,24 distinct names, and every line is `PASS | 0`; the parsed case list equals the receipt list exactly. No duplicate, failure, blocked case or omitted receipt case was found.

## Same-output-stream lock and script proof

The same `native.stdout` has one script-checksum line, one before-lock line, the24 case results, one after-lock line and the final exit/time fields, in that order.

```text
acceptance_scope=unchanged-native-24-case-offline-runtime
script_sha256_output=4d7b784aa2b24ccfe05910fd652fb4d7ef99f0298b7200e3a864b7c186207ade  <private-source>
lock_before_sha256_output=f451ef979cdb1ae3686a30df1c883c257402b32753478c1f9c686c057e9c3989  <runtime-lock>
lock_after_sha256_output=f451ef979cdb1ae3686a30df1c883c257402b32753478c1f9c686c057e9c3989  <runtime-lock>
acceptance_exit=0
```

Both lock values were derived from actual `sha256sum` output in this run. Their full checksum payloads, including the original locator, are identical before and after; this observation was not substituted from expected values or an earlier metadata snapshot. The receipt's sanitized stdout matches the original after only its declared private-source-locator replacement.

The unchanged acceptance script bytes independently hash to **`4d7b784aa2b24ccfe05910fd652fb4d7ef99f0298b7200e3a864b7c186207ade`**, agreeing with the request, receipt and emitted script checksum. The receipt envelope independently hashes to **`df83b47c7b71136a80f08ff70b5953c9747fa4c31233359be0b1813e6226edff`**, agreeing with the receipt.

## Returned cases

| Case | Status | Exit |
| --- | --- | --- |
| `offline_isolation` | PASS | 0 |
| `import_nautilus-trader` | PASS | 0 |
| `import_numpy` | PASS | 0 |
| `import_pandas` | PASS | 0 |
| `import_alpaca-py` | PASS | 0 |
| `import_edgartools` | PASS | 0 |
| `import_exchange-calendars` | PASS | 0 |
| `import_duckdb` | PASS | 0 |
| `import_pandera` | PASS | 0 |
| `import_skfolio` | PASS | 0 |
| `import_lightgbm` | PASS | 0 |
| `import_fincore` | PASS | 0 |
| `import_mlflow` | PASS | 0 |
| `import_arch` | PASS | 0 |
| `import_purgedcv` | PASS | 0 |
| `ibkr_adapter` | PASS | 0 |
| `alpaca_adapter_source` | PASS | 0 |
| `alpaca_adapter_import` | PASS | 0 |
| `nautilus_quickstart_sha256` | PASS | 0 |
| `nautilus_quickstart` | PASS | 0 |
| `duckdb_query` | PASS | 0 |
| `pandera_example` | PASS | 0 |
| `skfolio_example` | PASS | 0 |
| `arch_example` | PASS | 0 |

This scope is one offline-isolation check,14 research-distribution imports/version checks with Python3.12.3 verification inside those probes, and nine offline adapter/source/example checks. It is not the28-case prospective recipe and includes no pytest/pluggy/iniconfig dev-probe acceptance.

## Authorization, native entry and source controls

The current coordination record names `SUITE-GO 873-acceptance` at **2026-10-08T17:47:56Z**, after #876's landing-ready line. Both request and receipt cite that same GO. The request timestamp17:48:05Z and actual start17:48:39Z are later. CC172905Z's order and Oct9 quiet-window boundary are consistent with the returned dates. The later17:49:54Z co-op amendment leaves the GO standing; it does not change this run's completed evidence.

The request specifies the full native Windows WSL entrypoint, distributionNativeStack2604 and exec mode, plus `nice -n10 ionice -c2 -n7` and pinned mise uv0.12.17. No requested argument assigns WSL_DISTRO_NAME or WSL_INTEROP. The envelope's existing-WSL/nonroot guard precedes its emitted start line; a guard failure would have exited64. The returned start/case/end sequence and native exit0 agree with successful passage through that guard. This critic did not infer a new native run from the present client's state.

The corrected envelope explicitly checks both date-command exits and UTC formats. It blocks starts between2026-10-09T13:00:00Z and14:30:00Z, verifies the unchanged acceptance-script checksum and expected before-lock hash, captures a failed acceptance exit without errexit, obtains/prints the after-lock hash, and rejects a mismatched hash. These are static observations of the exact envelope used, not separately executed negative tests.

The acceptance source retains Bubblewrap `--unshare-all`, `--clearenv`, read-only runtime venv/interpreter/source mounts and `PYTHONDONTWRITEBYTECODE=1`. It uses the existing interpreter with `-I`. There are no active uv lock/sync/add/remove/pip-install commands. The no-runtime-metadata-or-venv-write claim is consistent with these source controls; only owned synthetic acceptance output is writable. The unchanged lock is directly measured. Full before/after byte invariance of every venv file or all runtime metadata was not independently measured and is not added as a claim.

## Findings, limits and inverse

No mismatch was found in case counts, exact case names/statuses, original receipt/output hashes, script/envelope identity, same-stream before/after lock proof, authorization timestamps or native completion status.

The earlier two24/24 records remain historical: one receipt-reported1fb9f8ca association and one writer-reported17221888 association, neither printing a lock checksum in its own stdout. This fresh f451ef97-bound run supplies its own evidence; it does not retroactively rewrite either earlier run.

Passing these24 cases does not establish the final28/dev-group recipe, a prospective exact legacy-package cleanup or migration, Layer1.5 historical-data engine E2E, strategy/research numbers, broker/paper/data acceptance, model/provider/GPU qualification or global readiness. The Nautilus quickstart here is its bounded unchanged synthetic example, separate from historical-data E2E. N2 STOP remains recorded as latched.

No runtime mutation requires a native inverse for this read-only acceptance. Retain its owned synthetic output and original receipt streams. Parent must bind this actual assessment and run evidence to the new publication head, preserve originals, and complete its separate exact-head CI/review/landing gates. This assessment performed no raw-rollout, authentication store, credential value, private client-configuration or trace-environment read.
