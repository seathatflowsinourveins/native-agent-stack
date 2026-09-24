# Gap wave 2: us-equities / security-supply-chain (2026-09-23)

This directory holds one receipt per open gap from the crosswalk (main 92bb279, PR #85)
for this layer. Each receipt keeps its preregistration, which was written at
2026-09-23T08:13:16Z before any check ran. After an independent review, receipts 5, 12 and 7
gained a separate `fix_round_preregistration` block, written at 2026-09-23T16:56:53Z (commit
d67f77a) before the fix-round checks ran; the original blocks are unchanged. Each receipt also records the exact
commands, quoted results, outcome, evidence class, limits and the SHA-256 of
every raw output it cites. `results.json` is generated from the receipts by
`blueprints/gap-wave2-20260923/us-equities__security-supply-chain/write_receipts.py --results`.

| Gap | Outcome | What was run | What remains |
| --- | --- | --- | --- |
| 0 | settled | Grype 0.119.0 on the exact Sept 19 SDK SBOM: 36 packages, 0 matches, DB built 2026-09-23T06:31:39Z. The positive controls gave 5 and 17 matches. | Zero matches is not a safety guarantee. |
| 10 | settled | The gap-0 scan, plus a README correction naming the rc5 runtime as the Sept 22 target (commit ba3e7c2). | None. |
| 2 | advanced | cosign `verify-blob` passed (exit 0) for the Syft and Grype checksum files, pinned to the workflow identity and commit. The tampered-blob and wrong-identity controls failed (exit 1). The installed binaries are byte-identical to the verified archives. | Gitleaks 8.30.1 has no signature or attestation (asset list; attestation API 404, which returns 200 for a control). It stays checksum-only. |
| 13 | advanced | Same run as gap 2. | Same as gap 2. |
| 3 | advanced | Syft with binary catalogers on the Nautilus venv, host root, SDK interpreter and local IB Gateway 1050 jars/JRE, each piped to Grype. | The 74 bundled `.so` files in the venv have no package identity. IBKR server-side software cannot be scanned here. `$HOME` was scanned only in targeted directories. |
| 9 | advanced | `syft dir:/` found 3034 packages. Its 677 OS packages match `dpkg-query` exactly; 1159 of 1221 host `.so` files are attributed. Grype reported 5433 matches. Both interpreters are covered. | Full coverage of bundled native libraries and broker-side software. |
| 5 | advanced | Guarded Gitleaks over all 502 HEAD commits (402 with diffs), with the repo config and a 2 MB cap: exit 0, no findings. Fix round: all 164 blobs over 2 MB reachable from HEAD (every `docs/ecosystem/index.html` version) were scanned whole; the 521 findings are all digest-shaped values that also occur in other tracked files. The 100 merge commits were scanned against their first parent, with 0 findings. Each method has a detection control. The all-refs scan found 7 findings, all on other branches. | Only the permanent limit: no scanner can certify absence. |
| 12 | advanced | Same run as gap 5, including the fix round. The positive control detected 6 of 6 planted shapes (5 rules) under both the default and repo configs. | Only the permanent limit: detection of every secret type cannot be established. |
| 6 | advanced | OpenBao 2.6.2, pinned and cosign-verified, as a loopback dev server. Write, scoped token, read, rotate, destroy the old version and revoke all returned the expected exit codes. Reads after revocation were denied (403). | No catalog winner manages the broker variables. Dev mode only. |
| 14 | advanced | The OpenBao lifecycle, a research-policy token denied the broker path (403), and a worker environment check. | Nothing enforces the documented broker-free launch, so research workers are not denied broker variables by default. The paper-order arm is deferred to `sota-workflow-resolution`. |
| 7 | settled | Same venv: Syft and Trivy inventories are identical (21 of 21) after PEP 503 name normalization; raw names differ only in `-`/`_` for two packages (`raw/compare/inventory-diff.json`). Grype, osv-scanner (`osv.json` results `[]`) and pip-audit (with Trivy) all report 0. Every scanner detects the positive control. | Agreement on a zero-finding target discriminates little. |
| 8 | advanced | Canary environment check. The documented launch from a dedicated research environment gave the codex child no broker variables. The SDK overlays the parent environment and nothing enforces that launch, so a launch from this host's launcher forwarded every broker variable to the codex child. Codex's default sandbox shell policy forwards them to tool shells. The `*KEY*`/`*SECRET*`/`*TOKEN*` excludes still pass TWS_PASSWORD and TWS_USERNAME. Only `env -i` or `inherit=none` removes them. | The paper-order arm is deferred to `sota-workflow-resolution`. A scrubbed worker environment is not enforced. |

Notable findings for owners:

- **Local IB Gateway 1050.** Its jars include jackson-databind 2.12.3 (9 Grype matches, including High), jackson-core 2.12.3, commons-io 2.11.0 and log4j-core 2.25.3 (Medium). Its bundled OpenJDK 25.0.2 has 22 CPE matches. These are database matches, not reachability findings.
- **Launcher environment on this host.** It carries eight broker-prefixed variable names, including `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`. Values were not read. The worker README documents a launch from a broker-free environment, but nothing enforces it: a research worker launched from this launcher without `env -i` inherits them.
- **All-refs Gitleaks findings on other branches, not triaged here.**
  - `codex/memory-scheduled-evidence-20260923` at b801fe474 (4)
  - `claude/g2-durable-memory-20260923` at 711187171 (2)
  - `claude/gc-pr5-packets` at 34fc51bea (1)

Evidence classes are `native_proven` (upstream tools executed on real targets) and `local_integration` (gaps 8 and 14). Gap 14 is `local_integration` because it includes the SDK stub-child check. `raw/` holds sanitized outputs: host paths are `$HOME`, UUIDs are `<uuid>` and signed URLs are removed. `raw/SHA256SUMS` lists every committed file. `raw/gitleaks-fix/classified.json` holds only redacted, classified findings: the unredacted fix-round reports lived in a 0700 temp directory and were deleted after classification. The full root and venv SBOM/Grype JSON stay in the local cache and are listed by size and SHA-256 in `raw/syft-binary/*-summaries.json`.

Network downloads, all into `$HOME/.cache/gap-wave2-20260923/security-supply-chain/`:

- The Grype DB (first pass; about 2.1 GB unpacked)
- cosign 3.1.3 and the Syft/Grype/Gitleaks release archives (first pass)
- The OpenBao 2.6.2 archive (76 MB)
- The Trivy 0.74.0 archive (50 MB) and Trivy DB (116 MiB)
- osv-scanner 2.6.0 (58 MB)
- pip-audit 2.10.1 from PyPI
- OSV and PyPI vulnerability API queries

Nothing was installed on `PATH`, no service or unit was touched, and the OpenBao dev server was stopped.

## Coordinator note (2026-09-23)

The gap-7 positive-control input is retained as `raw/compare/positive/requirements.txt.fixture`. The scanners read it as `positive/requirements.txt` in the work directory, and `raw/compare/osv-positive.json` still names that path.
- **Why:** under its original name, GitHub's dependency graph read the retained copy as a repository manifest. Dependency review, a required check that fails on high advisories, then blocked the integration PR on `requests@2.19.0`, the advisory this control exists to trigger.
- **What changed:** the file was renamed at integration. Its bytes and sha256 (`4230baa8…`) are unchanged, and `raw/SHA256SUMS` and the receipt list the new name.
- **Collector:** `collect_raw.py` now writes the new name.
- **OSV inventory:** the file is no longer a lockfile, so its exclusion entry in `.github/osv-scanner-lockfiles.json` was removed.
- **Not-JSON captures:** Eleven captured outputs across three layers were named `.json` but are not JSON: four empty stdout captures (`raw/bench-out/*.json` in document-retrieval), six stdout captures mixed with library or Ray warnings (research-factors-ml `raw/libs/libs__alphalens.json`, `raw/r4/*ray*.json`, `raw/r5/*ray*.json`), and a Grype `db status` output with a trailing line (`raw/grype-sdk/db-status.json`). The evidence-record discovery in `scripts/validate_convergence.py` parses every hash-listed `.json`, so at integration they were renamed to `.json.txt` with unchanged bytes. The receipts, raw manifests and `SHA256SUMS` name the new files, and the collectors now apply the same rule. Paths under `$HOME/.cache` in raw manifests are the names at capture time and are unchanged.
