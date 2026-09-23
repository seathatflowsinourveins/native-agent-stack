# Wave-2 gap checks: us-equities / data-quality-orchestration (2026-09-23)

Gap list: crosswalk at main 92bb279 (PR #85), layer `data-quality-orchestration`.
Base commit 41d39b3. Preregistrations were committed in 9cef641 (written
05:16:19Z) before any check ran. The branch was later rewritten after 9cef641 so
that round-1 raw files carrying base64-encoded host paths were never committed;
the commits made before that rewrite are not on this branch. All fix-round
preregistrations were therefore first committed on this branch in 1c7fe43:
gap-7 fix round 1 (written 05:26:05Z), fix round 2 for gaps 2, 5, 6 and 7
(05:40:45Z, after the first independent review and before the reruns) and gap-2
fix round 3 (05:48:47Z). Only the gap-7 fix-round-1 time is corroborated
independently: it precedes the second Dagu kill run at 05:26:18Z, and both times
appear in [raw/0-first-round-mtimes.txt](raw/0-first-round-mtimes.txt). The
fix-round-2 and fix-round-3 `written_at` values are self-reported; the reruns'
own output timestamps (05:40:59Z onward and 05:48:51Z) postdate them. The gap-2
fix-round-4 preregistration (05:57:08Z, after the second independent review)
is also self-reported; it precedes its check output (05:57:19Z and 05:59:57Z). [results.json](results.json) is generated from the
receipts by `blueprints/gap-wave2-20260923/us-equities__data-quality-orchestration/finalize_layer.py`.

| Gap | Outcome | Receipt | Evidence class |
|---:|---|---|---|
| 1 | covered_elsewhere | [paired model DAG](1-paired-model-dag.json) | source_review |
| 2 | settled | [dashboard auth mode](2-dashboard-auth-mode.json) | native_proven |
| 3 | covered_elsewhere | [2.17.0 hosting checks](3-dagu-2170-hosting-checks.json) | local_integration |
| 5 | settled | [duckdb gate input](5-duckdb-gate-input.json) | local_integration |
| 6 | advanced | [Temporal local execution](6-temporal-local-execution.json) | local_integration |
| 7 | settled | [Dagu vs Temporal kill comparison](7-dagu-vs-temporal-kill-compare.json) | local_integration |

## Findings

1. **Gap 1.** The paired Astra-to-Claude DAG already ran under Dagu 2.16.6 on
   2026-09-19 (`adoption/paired/receipt.json`, commit a9f40f2). The retained
   native run record, replayed with the pinned `dagu history --run-id ... --format json`
   in a temp home, shows `research-pair` `succeeded`. Both model steps show
   `succeeded`, and their printed results match the receipt (Astra 14,953 ms,
   Claude 10,538 ms). The retained reports match their recorded hashes. No new
   inference was run.
2. **Gap 2.** The running `dagu-equities` service serves `authMode: "none"`. It
   returned 200 to an anonymous GET of `/api/v1/dags` and 200 to a GET with a dummy
   Basic header. A loopback control using the same binary with `auth.mode: basic`
   returned 401 anonymous, sent a Basic challenge, and returned 401 for a wrong
   password, so the probe would have detected basic auth. The preregistered
   criterion (a), recording the config's `auth.mode` line, was replaced: the private
   config was not read, and the receipt records the served mode instead (see
   `preregistration_deviations`). In fix round 4, a loopback control showed that
   2.16.6 refuses to start when an `auth.basic` block is set under `none`. The hosting
   README now separates that config rejection from request-level Basic headers,
   which `none` ignores, and links to this receipt as superseding the 2026-09-19
   401/200 codes.
3. **Gap 3.** The pin decision belongs to `evidence/artifacts/sota-refresh-20260923/pins-runtime/dagu.json`
   (main commit 43bb931, #87; not present at base 41d39b3). This unit also reran the hosting receipt's failure, cancel and
   restart-history checks on both 2.16.6 and 2.17.0. The 2.16.6 archive matches
   the publisher checksums.txt. For 2.17.0 this unit only compared the binary hash
   with the value sota-refresh records for its checksum-verified extraction; it did
   not check a 2.17.0 checksums.txt itself. Outcomes were identical: exit 23 gave `failed` with the
   dependent step aborted and CLI exit 1; `dagu stop` gave `aborted` with exit 0;
   history was preserved across a server restart.
4. **Gap 5.** `duckdb://` inputs reproduced every retained fixture result: status,
   row_count and each check's status, for both pandas-registered and DuckDB
   auto-typed tables. `duckdb==1.5.5` is now in `requirements.in`/`requirements.lock`,
   and the recompile moved no other pin. A new `DuckdbInputRuns` test passes with a
   venv synced from the new lock. It fails when the venv lacks duckdb under
   `REQUIRE_PROMOTION_GATE_VENV=1`.
5. **Gap 6.** Temporal CLI 1.9.1 (checksum verified) ran a two-activity workflow on
   a loopback dev server. The scenarios covered success, retry after an injected
   attempt-1 failure, a non-retryable failure, cancellation, and a worker SIGKILL
   followed by a new worker (completed 24.8 s after the kill in fix round 2, 24.9 s in round 1). OTel spans came from
   the SDK TracingInterceptor, and the server metrics were scraped. History survived
   a server restart. Modal remains untested: with an empty HOME the client reports
   `Token missing` and needs `modal token new`, which requires a user login.
6. **Independent review.** One read-only `codex exec` call reviewed round 1
   ([raw/0-codex-review-r1.md](raw/0-codex-review-r1.md)). Blocking findings:
   base64 Temporal payloads still held a host path, and `*.jsonl` raw files were
   gitignored. Should-fix findings: provenance claims had no retained output, raw
   files had no capture timestamps, and the second-worker delay was hardcoded.
   All were resolved in fix round 2 with reruns for gaps 2, 5 and 6 and retained
   provenance output. The reruns reproduced every outcome. A second independent
   (Opus) review found five minor issues: commit labels lost in the rewrite,
   the ai-memory hook disclosure, the gap-2 criterion substitution, the 2.17.0
   checksum wording, and the hosting README's auth sentence. Fix round 4 resolved
   all five, with one new loopback check for the last. Each receipt's `review`
   field maps findings to resolutions.
7. **Gap 7.** On this host, Temporal recovered the killed step automatically.
   Dagu 2.16.6 kept the killed run in `running` and refused `dagu retry` at 35 s and
   95 s. An isolated `dagu scheduler` confirmed the zombie about 230 s after the
   kill. A manual `dagu retry` then re-ran step1 from scratch and succeeded. The
   first Dagu kill attempt had a harness defect (step env not passed through). It is
   disclosed and kept, and a preregistered fix round replaced it.

## Isolation and limits

All installs and data were kept under `$HOME/.cache/gap-wave2-20260923/data-quality-orchestration/`
(venvs, temporal CLI, dagu binary copies, disposable DAGU_HOMEs, a temp sqlite
file) and used loopback ports 17733-17740 and 18631-18674. Every started process
was stopped. The live `dagu-equities` service received only GET requests, and
its start timestamp did not change. No broker call or paid API
call was made. The unit made no direct ai-memory CLI or HTTP call. However, the
host's global Codex hooks (`$HOME/.codex/hooks.json`) post every lifecycle event
of a Codex session to the live ai-memory service at 127.0.0.1:49374, so the one
sanctioned `codex exec` review (cwd = this worktree) most likely left
hook-captured observations there. The Claude worker session's own hooks
(`$HOME/.claude/settings.json`) post to the same service. The unit did not query
the live store, so the coordinator still has to confirm that those hooks did not
create a live project or workspace for the worktree path. The checks used no
model inference; the only model call was the single Codex review. Network downloads: the temporal CLI archive
(45,298,806 bytes), the dagu 2.16.6 archive for checksum verification
(50,466,314 bytes), and PyPI
wheels (temporalio, opentelemetry-sdk, modal, duckdb and the locked gate
packages). Raw outputs cited by the receipts are under [raw/](raw/). Host paths
are replaced with `$HOME` and UUIDs with `uuid-redacted-<n>`. The same
replacement is applied inside base64 payloads, which are decoded and re-encoded. Each receipt
records the sanitized and original sha256.
A later pass on 2026-09-23 (after both reviews) also replaced the host name
and login name, which remained in plaintext in the Temporal worker and CLI
`identity` fields and the Dagu scheduler's service-registry lines, with
`<hostname>` and `<user>@<hostname>`. This changed eight raw files in gaps 6
and 7. The pass used
`blueprints/gap-wave2-20260923/us-equities__data-quality-orchestration/sanitize_host_identity.py`,
which fails if either string remains. `finalize_layer.py` then refreshed the
receipts' `sha256`/`bytes`, while `original_sha256` still identifies the
unsanitized cache files. No outcome or quoted result changed.

Coordinator note (2026-09-23): after Codex review of PR #132,
`duckdb_gate_check.py` now exits 1 unless every case matches on both loaders;
before, a DIFF was printed but the exit was 0. No receipt pins the script's
sha256. Gap 5's recorded runs (old lock, new lock, fix round 2) all report
`all_pandas_match` and `all_native_match` true with all 10 cases matching, so
they would have exited 0 under the new rule as well. The same review changed
the gate's DuckDB loader: only base tables are accepted, a pending `.wal` is
rejected, and `volume` is read as exact text. Rerun on 2026-09-23 against the
changed gate, the script matched all 10 cases and exited 0. With one retained
expectation altered, it exited 1.
