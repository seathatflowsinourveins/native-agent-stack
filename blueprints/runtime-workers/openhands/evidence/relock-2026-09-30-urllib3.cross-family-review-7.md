changes-needed

1. **P2 — Statement (b) can be false while tests pass.** [tests/test_osv_lockfile_coverage.py:552](<worktree>/tests/test_osv_lockfile_coverage.py:552) rejects only an override named exactly `next`. Adding `name="nex[t]"`, `nameIsRegex=true`, `ignore=true`, a reason, and `effectiveUntil=2026-12-24` passes. The pinned scanner reports `Package npm/next/16.3.5 has been filtered out`.
   **Ran:** the in-memory unittest harness and network-isolated `osv-scanner scan source --offline --config <(printf %s "$REVIEW_CONFIG") …`.

2. **P2 — Statement (c) can be false while tests pass.** [tests/test_osv_lockfile_coverage.py:559](<worktree>/tests/test_osv_lockfile_coverage.py:559) checks only lowercase `id`. Adding `ID = "GHSA-8988-9cw3-xx77"` beside the frozen entry’s existing `id` passes. The pinned scanner accepted this config and reported the other advisory as its decoded ignore in all 12 repetitions. Validate entry keys as well as values.
   **Ran:** the same unittest harness and 12 network-isolated native configuration probes.

3. **P2 — Statements (e) and (f) can be false while tests pass.** [tests/test_osv_lockfile_coverage.py:568](<worktree>/tests/test_osv_lockfile_coverage.py:568) checks fragments, while `scan_partition` independently models the intended partition. Both mutations passed:
   - Append `scan+=(--config "$frozen_config")`: the ordinary invocation uses the frozen exception.
   - Exclude `.github/requirements-ci.txt` in the ordinary jq expression and change the count comparison from `-eq` to `-le`: Bash scans only 48 inventory entries and exits 0.

   **Ran:** `rtk proxy bwrap … python3 -B -c …` over both test modules, followed by `rtk proxy bash --noprofile --norc -eo pipefail -c …` executing the mutated blocks. Each variant had 102 passing tests and 10 unrelated skips. No passing false variant was found for (a) or (d).

4. **P2 — Findings discovered during SARIF generation can leave CI green.** [security-scan.yml:98](<worktree>/.github/workflows/security-scan.yml:98) discards SARIF exit code 1. With `WRITE_SARIF=true`, scanner returns `(ordinary, frozen, ordinary-SARIF, frozen-SARIF) = (0,0,0,1)` produce step exit **0**. These are separate scans, so the comment that findings were “already reported above” is not guaranteed.
   **Ran:** the extracted block through `rtk proxy bash --noprofile --norc -eo pipefail -c …`, with controlled scanner return codes.

5. **P2 — A failed ordinary upload prevents uploading a valid frozen report.** [security-scan.yml:150](<worktree>/.github/workflows/security-scan.yml:150) has no condition allowing execution after the preceding upload fails. Input: ordinary SARIF missing or rejected, frozen SARIF valid. The second upload receives GitHub’s default success condition and is skipped.
   **Ran:** Python extraction of both upload-step blocks; neither contains an explicit `if`. This is a static finding; Actions were not executed.

6. **nit — The documented removal procedure leaves the required check failing.** [2026-09-22-github-automation-closure.md:365](<worktree>/docs/decisions/2026-09-22-github-automation-closure.md:365) names deleting the config, inventory key and `FROZEN_LOCKS` row, but the workflow also requires a nonempty frozen list. Removing that inventory assignment makes the extracted step exit **1 before either scanner runs**. The procedure must include removing or adapting that invocation and its guard.
   **Ran:** the extracted Bash block with an inventory containing no frozen entries.

7. **nit — Some review-history assertions lack retained output.** [osv-urllib3-next-20260930.json:245](<worktree>/evidence/receipts/osv-urllib3-next-20260930.json:245) records “22 events” and a provider rejection; line 249 records cancellation; lines 260–263 attribute findings and instructions to a verifier/coordinator exchange. The corresponding event streams and exchange are not retained. Section H supports the reproduced scanner behavior, not those provenance assertions.
   **Ran:** Python enumeration of the retained siblings and comparison with `independent_review`.

8. **nit — The reproduction helper’s network claim is inaccurate.** [osv-split-controls.py.txt:12](<worktree>/blueprints/runtime-workers/openhands/evidence/relock-2026-09-30-urllib3.osv-split-controls.py.txt:12) says nothing is sent over the network, but its scanner invocations omit `--offline`.
   **Ran:** inspection of the helper and `rtk proxy <osv-bin>/osv-scanner scan source --help`.

Mutations used in-memory copies because this session forbids filesystem writes. Native offline runs scanned 49/98 inputs but returned 127 without a cached vulnerability database. Pinned upload-action documentation was not found locally, so that documentation comparison remains unverified. The working tree is unchanged.