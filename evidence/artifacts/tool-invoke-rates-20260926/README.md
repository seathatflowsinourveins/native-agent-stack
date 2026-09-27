# Tool invoke rates: privacy-checker fix and receipt (2026-09-26)

PR #366 ("Tool invoke rates"), decision record
[`docs/decisions/2026-09-26-tool-invoke-rates.md`](../../../docs/decisions/2026-09-26-tool-invoke-rates.md).
This closes review thread `PRRT_kwDOUg_LrM6mT7_M` (commit a sanitized reproducible receipt before the
sanitizer is called proven) and window-2 finding 2 (the checker accepted a synthetic leaked `pwd` body in
both sinks). It also documents what remains unverified rather than rounding it up.

The cross-family repair against `a0348904` also fixes batch truncation, missing/non-string
bodies, structural attribute scanning and the synthetic-only replay path. Its new
results below are separate from the historical native replay and live host proof.

## The defect, and the fix

The pre-fix `prove_check.py` (a) loaded its `--forbidden-file` lines with an 8-character floor, and
`prove.sh` separately generated that file with its own 12-character floor, so a short executed command like
the probe's own `pwd` was silently never a candidate to check; and (b) never asserted a tagged record's body
against the Collector's fixed placeholder (`observability/collector/collector.yaml`,
`transform/privacy`: `set(body, "[content omitted]")`) -- it only searched a serialized text blob for
whatever forbidden strings survived the floor. Both defects are independent of each other and both had to be
fixed: removing the floor alone still leaves the checker relying on knowing which strings to search for.

Fixed in [`checker-fix/prove_check.py`](checker-fix/prove_check.py) and
[`checker-fix/prove.sh`](checker-fix/prove.sh):

1. Both length floors are gone (`prove.sh` also now adds the probe's `pwd` literal explicitly, since sentence
   -splitting a descriptive prompt never isolates a bare short command onto its own line).
2. `privacy_checks()` now asserts every tagged record's body equals the fixed placeholder exactly, in both
   the Loki sink and the Collector's file-exporter sink.
3. Forbidden-string matching now searches decoded string values at every OTLP level, never the raw serialized
   blob or JSON line, so a short literal (e.g. `pwd`) cannot false-positive on JSON punctuation or an
   unrelated key name.
4. `prove_check.py` is now import-safe (argparse and the network fetch moved into `main()`), so
   `privacy_checks()`, `streams_to_lines()`, `scan_otlp()`, `events_privacy_checks()` and `load_forbidden()` are
   reusable, offline-replayable functions. The live-mode checker and `offline_recheck.py` now use the same
   events-file assertions; the retained live proof ran an earlier checker. The original import-safe
   refactor was exercised end to end (real subprocess, real
   argparse, against a local mock Loki) by
   [`checker-fix/dry_run_smoke.py`](checker-fix/dry_run_smoke.py) / [`.out`](checker-fix/dry_run_smoke.out):
   `--dry-run` still produces exactly the expected 15 `PASS ...` lines (12 `CHECKS` + 3 `ZERO_CHECKS`), so
   `main()`/`build_checks()`/`instant()`/`by()` have no `NameError`/`AttributeError` left over from moving
   them out of module scope.
5. `scan_otlp()` retains **every** log record's body, including a failure entry for a missing or non-string
   body. `events_privacy_checks()` rejects unparseable JSON and empty batches. The structural walk checks
   resource, scope and record fields, including nested arrays and key-value lists; banned keys are checked
   after JSON decoding, independently of whitespace. Reference: OpenTelemetry
   [`logs.proto` at v1.9.0](https://github.com/open-telemetry/opentelemetry-proto/blob/v1.9.0/opentelemetry/proto/logs/v1/logs.proto)
   and [`common.proto` at v1.9.0](https://github.com/open-telemetry/opentelemetry-proto/blob/v1.9.0/opentelemetry/proto/common/v1/common.proto).

Pre-fix snapshot for provenance: `design/prove_check.py.old-20260926`,
sha256 `0f78148934b6e19894c0918e2229c93f1038ccef78d9738b2032d826f1fd7722` (scratch only, not committed here;
the failing-first control below is a byte-faithful transcription of its seven privacy assertions).

## Evidence classes (docs/acceptance-evidence-policy.md)

| # | Class | What it is | Result |
| --- | --- | --- | --- |
| 1 | Historical local integration | Scratch replay: real probe captures + synthetic sentinel records through the staged logs pipeline on pinned otelcol-contrib 0.161.0 and a scratch Loki 3.7.8 | **109 passed, 0 failed**, not re-run here |
| 2 | Historical host acceptance | Live host proof, `prove.sh`, one real `claude -p` and one real `codex exec`, 2026-09-26T23:47:42Z-23:49:21Z, checked with the **pre-fix** checker | **33 passed, 0 failed**, not re-run here |
| 3 | Discriminating control | Failing-first A/B, fully synthetic, offline: old checker vs. fixed checker against a body of `"pwd"` | Old **accepts** the leak; fixed checker **rejects** it |
| 4 | Local integration (offline re-derivation) | Corrected structural scanner against proof #2's **retained, real** events-file batches, run 2026-09-27T03:55:26Z | **3 passed, 0 failed**; **270 records in 29 batches**, 26 forbidden strings, zero hits (events-file sink only). The input rotated out at 04:05:11Z, so this run cannot be repeated (part 4) |
| 5 | Synthetic regression controls | Checker structural cases; synthetic-only replay with stubbed HTTP and reference exporter output | Checker **2 passed, 10 failed** before / **12 passed, 0 failed** after; replay **25 passed, 20 failed** before / **25 passed, 0 failed** after |
| 6 | Local integration (native synthetic replay) | `replay-test.sh`, synthetic-only, on the installed pinned Collector 0.161.0 and Loki 3.7.8 with scratch loopback ports 45700-45703 and scratch storage. The coordinator ran it on the host, outside the repair sandbox | **67 passed, 0 failed**, no scratch listener left ([output](scratch-replay/synthetic-native.out)). The repair sandbox's blocked attempt is retained ([output](scratch-replay/synthetic-native-attempt.out)) |
| -- | Independent observation (not re-run here) | Window-2's own separate all-stream Loki scan, 22:45:00Z-00:24:44Z (contains proof #2's window) | Every `claude-code`/`codex_exec` body exactly `[content omitted]`, corroborating but not the fixed checker |

## 1. Scratch replay -- 109/109 (local integration)

Source: scratch `u6/DESIGN.md` (`replay-test.sh`, final run 19:29Z) and `u6/REVIEW-RESOLUTION.md` (round-2
rerun, `round2/replay-output-final.txt`: 567 records = 536 captured + 31 synthetic; 72 forbidden strings, 0
found under the *pre-fix* rules; 62 metadata keys, all allowlisted; 19/19 dashboard targets; 21/21 Loki
checks). Versions: otelcol-contrib 0.161.0, Loki 3.7.8 (pinned binaries), Claude Code 2.1.283 capture,
codex-cli 0.157.1 capture. `replay-receipt.json`'s own privacy scan (this receipt's convention: the account
username, home-directory paths, session-scratch-directory paths, UUID-shaped strings, emails) returned zero
hits before it was copied here unmodified.

| File | Content |
| --- | --- |
| [`scratch-replay/replay.py`](scratch-replay/replay.py) | The harness (`build-config`/`post`/`assert`/`loki`/`forbidden`/`receipts`/`assert-receipts`) **and** the reference implementation (`expected_derived()`): a second, independently written mapping from raw attributes to the derived fields (`tool_family`, `actor`, `client`, ...), compared record-by-record against the Collector's own OTTL output. Already fully parameterized by its own argparse (no session path was ever hard-coded); two of its synthetic sentinel test values were adjusted for this receipt's own privacy-scan convention (a home-directory-shaped sentinel path was moved under a `/srv/example/...` prefix; two placeholder UUIDs de-hyphenated) -- both are `U6SENTINEL`-tagged test fixtures, never real paths or ids, and the substitution changes nothing about what they exercise (a model-typed absolute-path shape; an id-shaped `conversation.id` value not on the export allowlist). |
| [`scratch-replay/replay-test.sh`](scratch-replay/replay-test.sh) | Stages a scratch Collector (logs processors copied verbatim) and scratch Loki from the repository template on ports 45700-45799. With no captures, `post --synthetic` uses a recent default timestamp. Historical-count and live-scenario assertions require the complete A/B/C/Codex capture set; synthetic record and dashboard assertions remain active. Native execution of this repaired path was attempted but blocked here; see part 5. |
| [`scratch-replay/run_panel_queries.py`](scratch-replay/run_panel_queries.py) | Runs every dashboard target with panel id >= 28 as an instant query and prints series counts/values; already fully parameterized. |
| [`scratch-replay/replay-receipt.json`](scratch-replay/replay-receipt.json) | The derived result: pinned versions, the base commit hashes the patch applied to, and all 109 `PASS ...` lines with their names and small label/count details (e.g. `posted records=567 requests=62 inputs=4 synthetic=True`, `derived names/families/actors equal the reference spec on every record :: mismatches={}`). No raw capture content; copied unmodified (privacy-scanned clean, see above). **Its own `evidence_class.host_acceptance: "not run"` field is a snapshot from when it was recorded (2026-09-26T19:37:08Z) and is now stale** -- the live host proof below (part 2) ran afterward, at 23:47:42Z-23:49:21Z; this file is not re-edited to keep it an unaltered copy of what the replay actually produced. |

**Not committed (by design):** the 536 real captured records (`u6/raw/claude-{A,B,C}-logs.json`,
`codex-logs.json`) and `design/make_stage.py` (which mechanically stages this PR's own already-committed
`collector.yaml`/dashboard files -- confirmed byte-identical to this PR's committed
`observability/collector/collector.yaml` and `observability/backends/templates/ecosystem-dashboard.json.example`
at commit `a6d00d02` (PR #366's tip when this receipt was built), sha256 `ff229df9...` and `0625f7bb...`
respectively, so `replay-test.sh` above reads them directly from a checkout instead. Scoped to that one
commit: this receipt's own panel-34 description edit (part 3 below of the decision record, not of this
folder) changes that dashboard file's text after `a6d00d02` with no `expr` change, so the *current* PR file's
hash will differ from `0625f7bb...` on description bytes alone -- re-hash against whatever commit you check
out, not against this fixed string).

## 2. Historical live host proof -- 33/0 (pre-fix checker)

Source: scratch `monitor-window/PROVE2.md` section "(D) u6 proof (live): exit 0, 33 passed, 0 failed", and
retained output `monitor-window/prove2/u6-prove-live.txt` / `u6/raw/prove-20260926T234742Z/`.
`setsid nohup bash prove.sh` ran 2026-09-26T23:47:42Z-23:49:21Z (`rc=0`), against production Loki/Collector,
with the **pre-fix** checker (its mtime, 19:06:19Z, predates this fix).

| File | Content |
| --- | --- |
| [`live-proof/u6-prove-live.txt`](live-proof/u6-prove-live.txt) | The run's full retained stdout (7 preflight + 2 probe-exit + 22 Loki checks + 2 after-run checks = 33), with the UUID-shaped task id replaced by a fixed placeholder (this receipt's own convention, not because the id itself is secret). |
| [`live-proof/checks.txt`](live-proof/checks.txt) | The 22 Loki-check lines alone, byte-identical to the retained file. |
| [`live-proof/settings-flags.txt`](live-proof/settings-flags.txt), [`dashboard-compare.txt`](live-proof/dashboard-compare.txt), [`panels.txt`](live-proof/panels.txt) | Copied unmodified: live-settings key *truthiness* only (no values), the deployed-vs-staged dashboard match, and all 19 dashboard targets' returned series. |
| [`live-proof/hashes.txt`](live-proof/hashes.txt) | SHA-256 and byte counts only for the run's real transcripts (`claude-result.json`, `codex-exec.jsonl`, stderr files) and its own `forbidden.txt` -- never their content. |

**What this class does and does not show.** The 33/0 result is real and reproduced the expected per-server,
per-skill, per-subagent and per-client counts within the deadline. But its 7 privacy assertions ran under the
checker this fix replaces: it never asserted body content, and its forbidden-string list was filtered by
length. [`checker-fix/verify_forbidden_list.sh`](checker-fix/verify_forbidden_list.sh) (output in
[`verify_forbidden_list.out`](checker-fix/verify_forbidden_list.out)) actually re-derives that list from the
real probe prompt and `prove.sh`'s own `CODEX_TASK` literal, rather than assuming: the pre-fix (12-character
floor) recomputation is **25 lines, sha256 `1b59bd73...`, byte-identical to the retained `forbidden.txt`**,
confirming this receipt's provenance for that file. The fixed (no-floor, plus the explicit `pwd` literal)
recomputation is **27 lines** -- two more, not one: `pwd` itself, *and one other short fragment from the
sentence-split prompt/task text that the pre-fix floor was also silently dropping* (its content is not shown
here, only that it existed; see the script's own docstring to reproduce this yourself with the real prompt
files). So the length floor was not a no-op for this run after all. What the old checker structurally could
not do, for any run, is notice a short literal like `pwd` (or that other dropped fragment) if it ever
appeared as a body -- see part 3.

## 3. Failing-first control (discriminating control)

[`checker-fix/failing_first_ab.py`](checker-fix/failing_first_ab.py), output in
[`checker-fix/failing_first_ab.out`](checker-fix/failing_first_ab.out). Fully synthetic, offline, no network.
Builds one fake tagged Loki record and one fake tagged events-file line in two bodies -- the fixed placeholder
(clean) and the bare literal `"pwd"` (a leaked short executed command) -- and runs both the frozen pre-fix
logic and the fixed `prove_check.privacy_checks()` over each:

- **OLD checker: all 5 relevant assertions PASS identically for the clean body and the `"pwd"`-leak body** --
  it cannot tell them apart (`"pwd"` never survives the 8-character forbidden-list floor, and there is no
  body assertion).
- **Fixed checker: PASSes the clean body, and correctly FAILs 4 assertions on the `"pwd"`-leak body**
  (the new body-equality assertion, on both sinks, plus the no-floor forbidden-string search on both sinks).

This satisfies `docs/acceptance-evidence-policy.md`'s discriminating-control rule: the check is shown to fail
when its condition (the leak) is present, next to the same check passing when it is absent, in the same
receipt.

The extended control also exercises a leak before a clean body in the same batch, missing and non-string
bodies, resource/scope attributes, nested key-value lists and arrays, and spaced/nested banned keys.
[`failing_first_ab.red.out`](checker-fix/failing_first_ab.red.out) records the actual run against `a0348904`:
both clean controls passed and all ten rejection controls failed (exit 1).
The regenerated [`failing_first_ab.out`](checker-fix/failing_first_ab.out) records **12 passed, 0 failed**
(exit 0), including the unchanged clean-body control. The earlier frozen A/B outcomes still match.

## 4. Offline re-check against the retained live-proof exports

[`checker-fix/offline_recheck.py`](checker-fix/offline_recheck.py), output in
[`checker-fix/offline_recheck.out`](checker-fix/offline_recheck.out). No new host run: no live Loki query, no
new model call, no new probe. `prove_check.py`'s live-mode privacy block never persisted the raw fetched Loki
records to disk (only its own derived PASS/FAIL text was saved, in `checks.txt`), so **the fixed body-equality
assertion cannot be retroactively evaluated against proof #2's Loki sink** -- there is nothing on disk to
re-run it against. That is a real, stated limit, not rounded up.

The Collector's **file-exporter** sink is different: it is a persistent, append-only file, and the rotated
file covering 2026-09-26T22:53-01:03Z (containing the proof's window) was still on the host at 03:55Z. It
rotated out at 04:05:11Z; see below. This script grepped
it for the run's exact task id (read from a file, never argv) and re-ran the fixed checker's real functions
(`events_privacy_checks`, `scan_otlp`, `FIXED_BODY`) over every record in those batches:

```
INFO events files scanned: 4; tagged lines found: 29; forbidden strings: 26 (added 'pwd': True)
PASS every tagged events-file line parsed as OTLP JSON :: lines=29 parsed=29
PASS every tagged events-file record's body is exactly '[content omitted]' :: records=270 not_fixed=0 empty_batches=0
PASS the events file holds this run's tagged records without command/prompt text (any length) or content/identity keys :: lines=29 value hits=0 banned keys=[]
SUMMARY offline_recheck (events-file sink only; Loki sink not re-queried): 3 passed, 0 failed
```

`tagged lines found: 29` matches the original (pre-fix) run's own `checks.txt` line
(`lines=29`), confirming this re-check reached the same retained batches. Those batches contain **270
records**, including records sharing a batch with the tagged proof records. Every body is exactly
`[content omitted]`; missing/non-string bodies and empty batches count as failures. The 26-string search
(the retained 25 plus `pwd`, not the separately recomputed 27-string list) found zero hits across decoded
resource, scope and log values, including nested values, and no banned keys. The former `records=29`
was a batch count, not a record count. No violation was found by the corrected scanner.

**This run cannot be repeated.** It ran at 2026-09-27T03:55:26Z. The Collector's `file/events` exporter keeps
10 MB x 3 backups (`observability/collector/collector.yaml`, `rotation`). It rotated at 04:05:11Z and dropped
the backup that held the proof's records. A coordinator re-run of the same command at 04:14Z found 0 tagged
lines ([output](checker-fix/offline_recheck.rerun-after-rotation.out)). The 03:55Z output above is the retained
record of the only run of the corrected checker against that data. No input hash was taken before the
rotation.

**Net privacy claim for proof #2, stated precisely:** the events-file sink is now verified by the fixed
checker, offline, against the real retained records. The Loki sink is verified only by the pre-fix checker
(part 2's limit above); the closest independent corroboration is window-2's separate all-stream Loki scan
over 22:45:00Z-00:24:44Z (which contains this proof's window), reporting every `claude-code`/`codex_exec` body
in that broader scan as exactly `[content omitted]` -- a different method, a different (wider) record set, and
not a run of this fixed checker. The Loki sink is not re-verified by the fixed checker for this specific proof;
the next real `prove.sh` run will be.

## 5. Synthetic-only repair and verification limits

The original synthetic-only path raised `ValueError: max() iterable argument is empty`. It also ran
historical assertions requiring omitted captures. `post` now supplies a recent timestamp for an empty
capture, accepts no input files with `--synthetic`, and reports whether the historical capture set is present.
The exact historical-count assertions and live-proof scenario checks run only with that complete set;
record conservation, privacy, derived-field and synthetic assertions remain active for synthetic-only runs.

[`synthetic_replay_control.py`](checker-fix/synthetic_replay_control.py) executes `post` and the replay
assertions with an empty capture, 31 synthetic records, stubbed HTTP and exporter output built from the
existing design reference. The [red output](checker-fix/synthetic_replay_control.red.out) has **25 passed,
20 failed** (exit 1); the [green output](checker-fix/synthetic_replay_control.out) has **25 passed, 0 failed**
(exit 0), with 31 records and 41 fixture strings checked, zero hits. This proves the harness route and
assertion selection. Reference-generated output cannot establish native Collector or Loki behavior.

In the repair sandbox, the full native scratch run could not create loopback sockets
(`socket: operation not permitted`). The repaired shell exits 1 on that startup failure, and its
[sanitized output](scratch-replay/synthetic-native-attempt.out) retains it.

The coordinator then ran the same synthetic-only `replay-test.sh` on the host, outside the sandbox, with the
installed Collector 0.161.0 and Loki 3.7.8 on scratch loopback ports 45700-45703 and scratch storage. Result:
**67 passed, 0 failed**, ending with "no scratch listener left on the replay ports"
([sanitized output](scratch-replay/synthetic-native.out)). This is native local-integration evidence for
the repaired synthetic path. Production services and systemd units were untouched.

In the sandbox, the three-module unittest command ran **78 tests: 57 passed, 21 errors**, all 21 from
socket creation being prohibited. The coordinator re-ran the same command on the host: **78 tests, OK**.
`bash -n` passed for the changed replay shell script. The historical native results in parts 1 and 2 are
retained evidence, not new acceptance for this repair.

## Reproducing this

```bash
# Scratch replay (synthetic-only; add your own capture files as extra positional args for the full mix):
REPO=/path/to/native-agent-stack ./scratch-replay/replay-test.sh

# Fixed checker, dry run against a REACHABLE Loki (no model call):
python3 checker-fix/prove_check.py http://127.0.0.1:13100 some-task-id 5 --dry-run

# Same dry-run path, fully offline (mock Loki, proves the main()/build_checks() refactor has no NameError):
python3 checker-fix/dry_run_smoke.py checker-fix/

# Failing-first control (fully synthetic, no network):
python3 checker-fix/failing_first_ab.py checker-fix/

# Offline synthetic replay harness control (stub transport and reference output; not native acceptance):
python3 checker-fix/synthetic_replay_control.py /path/to/private/scratch

# Offline re-check (needs your own retained events-file export and its task id):
python3 checker-fix/offline_recheck.py '<events-glob>' <task-id-file> <forbidden.txt> checker-fix/

# Re-derive prove.sh's forbidden-string list from your own real probe-prompt.txt, old vs. fixed:
bash checker-fix/verify_forbidden_list.sh <probe-prompt.txt> checker-fix/prove.sh [<retained-forbidden.txt>]

# Live host proof, fixed checker (needs REPO, PROVE_PROMPT_FILE, and production Loki/Collector/Grafana):
REPO=/path/to/native-agent-stack PROVE_PROMPT_FILE=/path/to/your/probe-prompt.txt bash checker-fix/prove.sh
```

`checker-fix/prove.sh` is a reference copy: it reads `$REPO/observability/...` for the staged
collector/dashboard files (this receipt's part 1 already confirmed those are byte-identical to what the
original scratch run staged), reads `run_panel_queries.py` from `../scratch-replay/`, and needs your own
`PROVE_PROMPT_FILE` -- the real Claude probe prompt is not committed here, for the same reason the real
captures in part 1 are not. It writes all raw run output (including real prompts/transcripts) under
`PROVE_OUT_DIR` (default: a fresh `mktemp -d`), never inside a tracked directory.

## Privacy

Every file in this directory was scanned for the account username, home-directory paths, session-scratch
-directory paths, UUID-shaped strings and email addresses before this receipt was finished; see the
decision-record update ("Evidence and its class") for the scan command and result.
