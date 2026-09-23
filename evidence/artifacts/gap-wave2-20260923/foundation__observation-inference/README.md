# Gap wave 2 (2026-09-23): foundation / observation-inference

Eight open gaps from the crosswalk (main 92bb279, PR #85) were checked on one Linux/WSL
host. Base commit 41d39b3, branch `claude/g2-observation-inference-20260923`.
`results.json` is generated from the receipts by
`blueprints/gap-wave2-20260923/foundation__observation-inference/make_results.py`.
`build_receipts.py` in the same directory reads every quoted number from `raw/`.

| Gap | Outcome | Receipt | What was run |
|---:|---|---|---|
| 0 | advanced | `0-privacy-canary-script.json` | Re-runnable canary script: 37 synthetic canaries through log, metric, resource, scope and SDK-receipt fields; 0 leaks with the repository privacy processors in 4 runs (the latest, in fix round 3, from the committed script with unedited output), every positive control in every expected backend; passthrough self-test finds 31/37. Arbitrary-content DLP still absent. |
| 1 | settled | `1-usage-reconciliation-script.json` | `reconcile_usage.py` runs one bounded native `claude -p`. Its usage matched the Prometheus counter delta exactly in all four categories. |
| 2 | advanced | `2-scheduled-unit-journal-persistence.json` | A read-only journal check covered 4 boots. The timer-triggered service started after all 50 user-manager starts and all 15 daemon-reloads (manual starts cannot be excluded). 3 runs failed. Fix round 3: a private `systemd --user` in an unprivileged namespace, carrying the pipeline timer settings, fired after enable+start, after a deliberate daemon-reload and after a manager restart (SIGKILL plus fresh start). The live-manager arms and the post-`wsl --shutdown` check were not run (blocker below). |
| 3 | advanced | `3-task-attribution-isolated.json` | The collector received telemetry only from this task, so the before snapshot was empty. The per-category delta equals the task usage, and the only `session.id` seen was the child's. The outcome stays advanced under the preregistered fix-round rule: the planned live-leak detector (`session_id`) had no detection power. A signature probe designed afterwards found 0 matches among 621 live events. Fix round 3 gave that matcher a positive control (a known event matched). It also ran the preregistered live-Prometheus check, which rounds 1-2 had skipped; that detector failed its control, so the outcome stays advanced. |
| 4 | advanced | `4-sdk-spool-fill-outage-expiry.json` | 128 KiB tmpfs spool: full disk refuses writes cleanly; 180 s collector outage and an overlapping collector+Loki outage lose 0; a ~335 s Loki outage loses 8/8 from Loki (twice), 0/8 with `max_elapsed_time: 0s`; Loki-confirmed expiry policy + tests. |
| 5 | advanced | `5-jaeger-codex-trace-by-id.json` | A checksum-verified Jaeger 2.21.0 received traces from one ephemeral `codex exec`. That session's traces were fetched by ID. The live pipeline is unchanged. |
| 6 | settled | `6-alertmanager-ntfy-latency.json` | 20 synthetic alerts through Alertmanager to ntfy, two runs: firing median 5.003 s (5.002-5.004), resolved median 20.5 s (11.0-30.0). |
| 8 | advanced | `8-llama-parallel-kill-recovery.json` | The frozen b11057 plus Qwen3.8-27B route ran at `--parallel 4`: 12 of 12 succeeded. After a SIGKILL, 0 of 8 in-flight requests survived. After restart, the server was healthy in 5.3 s, the first success came 10.7 s after the kill, and 8 of 8 succeeded. |

## Isolation

All backends ran from installed upstream binaries. Each ran as a child process on free
`127.0.0.1` ports, with private data under
`$HOME/.cache/gap-wave2-20260923/observation-inference/` (`isostack.py`). Every one was stopped
afterwards. The live `ecosystem-*` services, systemd units, `~/.config`, ai-memory and Qdrant
were not touched. Gap 2 read the user journal and timer properties. In fix round 3 it also ran a private `systemd --user` (`private_user_manager.sh`) inside `unshare --user --pid --mount` and an `ecosystem-bounded-run` scope. The live `/run/user/1000` was hidden under a tmpfs, `HOME`, `XDG_*` and `SYSTEMD_UNIT_PATH` pointed into a temp root, and the service was replaced by a timestamp append. The system user generators still ran, and wrote only into the private runtime dir.

The single Claude call (gaps 1 and 3) ran under these constraints:

- `env -i`, from a fresh temp cwd
- `--setting-sources local`: user settings, user hooks, user-installed plugins and the live OTLP endpoint were not loaded; the built-in `agents-md` and `telemetry` plugins still loaded
- `disableAllHooks`, an empty strict MCP config and no tools
- `AI_MEMORY_SERVER_URL` pointed at a closed port

Gap 3's leak probes made read-only GET queries to the live Loki and, in fix round 3, the live Prometheus; nothing was written to either.

The single Codex call (gap 5) used `--ephemeral --sandbox read-only --ignore-user-config --disable hooks`, with only the trace exporter enabled.

The spool test ran inside `unshare --user --map-root-user --mount`.

Network downloads are all in the cache directory. Each was pinned and checked:

- Jaeger 2.21.0 (61 MB)
- llama.cpp b11057 CUDA 13.3 runtime (560 MB)
- Qwen3.8-27B-Q4_K_M.gguf (18.97 GB), via `ecosystem-bounded-run`
- strace 6.8 Ubuntu noble .deb (584 kB, sha256 d588810a...), fetched with `apt-get download` and extracted with `dpkg -x` for the gap 2 diagnosis only, not installed

## What remains

- **Gap 0:** The filter is key-based, so it is not arbitrary-content DLP. Allowlisted values and metric names pass through. Six metric fields are never persisted by any backend, so the canary cannot test them.
- **Gap 3:** A live-Prometheus change/new-series detector with a correct control label (`claude-opus-5-5[1m]`), preregistered before it runs. The Loki matcher now has a working positive control. A post-hoc change check found no haiku series matching the child's usage. Live logs, like live metrics, carry no `session_id`, so live telemetry cannot be attributed per task.
- **Gap 2:** The private manager exercised the timer across daemon-reload and restart. Its restart was a SIGKILL plus fresh start, because it ignored SIGTERM even with a stub `exit.target`, and it ran a stand-in service. Still needed: a deliberate daemon-reload and restart of the live user manager with the real service, plus `check_persistence.py` after a coordinated `wsl --shutdown`. Blocker: both restart live services and the WSL VM shared with peer sessions, which this unit's isolation rules forbid. A private manager cannot reproduce a VM restart or the live backends' data. Owner: coordinator or user, in a quiet window.
- **Gap 4:** Apply `otlphttp/loki.retry_on_failure.max_elapsed_time: 0s` to `observability/collector/collector.yaml`, which is outside this unit's paths. Schedule `spool_expiry.py`. Multi-hour outages and exhaustion of the collector queue directory were not tested.
- **Gap 5:** Choose a persistent trace backend and a retention policy. Traces carry the working-directory path and thread IDs, and they bypass the collector privacy processors. Claude trace export was not tested.
- **Gap 8:** Only one kill trial was run. Clients do not retry in-flight requests. Quality was not rechecked. Portability to another host is untested.

## Timestamps

- **Preregistration:** written at 02:46:44Z in `preregistrations.json` and committed in 1a59606 before any check ran.
- **Follow-ups:** the gap 4 follow-up (03:13:09Z) and the revised gap 8 plan (03:18:03Z) were each committed before their runs.
- **Late:** the journal analysis for gap 2 was designed after the preregistration and is labelled late in its receipt.
- **Fix round:** preregistered at 03:28:46Z (commit 'Record the Codex review and preregister the fix round') after the independent Codex review in `raw/review-codex-round1.txt`.
- **Fix round 3:** preregistered at 14:15:26Z (commit 929154c, `fix_round_3` in `preregistrations.json`) after the independent Opus review in `raw/review-opus-round3.json`, before any fix-round-3 run. Gap 2 has three addenda, each committed before the attempt it describes: 13a9fd8 (14:21:30Z), e8b3be5 (14:43:16Z) and 05d3da0 (14:47:11Z). The gap 3 post-hoc Prometheus check is labelled not preregistered.

## Independent review

The Codex review raised 12 points. The fix round made these changes:

- **All receipts:** each now carries the `next_check` text and a status for every arm.
- **Gap 0:** a positive-control backend matrix is enforced.
- **Gap 1:** the reconciliation verdict is stricter. It was applied to the retained run without a new model call.
- **Gap 2:** the analysis counts timer starts rather than completions, and the failure lines are retained.
- **Gap 3:** a read-only live-Loki leak probe was added. The live records have no `session_id`, so the session detector had no power there. The token-signature detector was designed afterwards and is labelled late.
- **Gap 4:** the overlapping-outage arm was run, and the space-release timing was relabelled.
- **Gap 6:** resolved alerts are now timestamped before sending.

Earlier runs are retained under `raw/` with run1/run2 names.

The second review round is in `raw/review-codex-round2.txt`. The first attempt timed out after 1000 s with no output. The second, narrower attempt returned these results:

- **Resolved:** 9 of the 12 round-1 findings.
- **Gap 2 timer wording (partial):** the note now names manual starts as not excludable.
- **Gap 3 outcome (partial):** changed to advanced, following the preregistered rule.
- **README plugin wording (partial):** corrected here; this was outside what the reviewer could check.
- **Gap 4 timeline (new finding):** the receipt now quotes the recorded values.

## Fix round 3 (Opus review)

The Opus review (`raw/review-opus-round3.json`) raised four minor findings. All four were acted on:

- **Gap 2, isolated alternative not tried:** tried in four preregistered attempts. Attempt 1 failed: this shell sits in the root-owned `/init.scope` cgroup, and `systemd --user` exits 1 on `EACCES` writing `cgroup.procs` (strace in `raw/2-fr3-private-manager-diag.txt`). Attempts 2-3 ran inside an `ecosystem-bounded-run` scope; the timer failed because the private unit path lacked `basic.target`. Attempt 4 fired after enable+start (48 s), after daemon-reload (130 s) and after a manager restart (49 s).
- **Gap 3, live-Prometheus check not reported:** now reported. It had not been run in rounds 1-2. Its first run failed the preregistered positive control, so gap 3 stays advanced. A labelled post-hoc change check is included.
- **Gap 3, `signature_detection_demonstrated` flag:** documented in `raw/3-live-loki-probe.annotation.txt`; the raw file and `live_session_probe.py` are unchanged. The flag means only that the query path returned events. The matcher's detection power was shown in fix round 3.
- **Gap 0, script hash mismatch:** reran both modes with the committed `privacy_canary.py`, whose output is unedited (`raw/0-canary-fr3-*`). The receipt also names the pre-change blob (80b7ec7, commit 424eeb7) used by the earlier runs.

## Publication redaction

Three UUIDs were replaced with labels in the committed raw files and receipts. This follows the repository validator rule for local session identifiers.

- **`<child-claude-session-id>`:** the child Claude session.
- **`<codex-thread-id>`:** the Codex thread.
- **`<collector-instance-id>`:** the service.instance.id of the isolated collector.

Equality and attribution checks were computed on the unredacted private outputs before redaction. Trace IDs (32 hex characters) are not session identifiers and were kept.

The `logs.attr.api_key` canary value is also withheld in the committed `raw/0-canary*.json` files: that label with that value tripped the repository's gitleaks `generic-api-key` rule. The branch history was rewritten with `git filter-branch --tree-filter` from the first receipt commit onward, so that no commit carries the value. Commit dates were preserved. Leak detection used the full value, which is kept only in the private run directories. `privacy_canary.py` now publishes sha256 prefixes instead of raw canary values; the fix-round-3 `raw/0-canary-fr3-*` files come from that version and were not edited. The live Prometheus instance id in `raw/3-fr3-live-prom-posthoc-detail.txt` is replaced by `<live-instance-id>` inside the script before output.
