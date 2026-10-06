# Live acceptance of the drain build on 20128: the protocol, version 2, frozen before the switch (2026-10-06)

> **DRAFT (work in progress): NOT FROZEN.** The same-day baselines of version 2 of the scripts have not been run yet, so the expected-outcomes table has no baseline column and the wrapper carries no baseline hash. This file is frozen only by a later commit that adds the baselines, the wrapper's baseline hash and the numbers below; until then no canary may be run and the command center's hold is unchanged. (Pushed as a safe point before a supervised restart of the host.)


This file is frozen by the commit that adds it, before the canary switch. It fixes the inputs, the commands, the repetitions, the expected outcomes, the guards and the rollback triggers (`docs/acceptance-evidence-policy.md`, "Preserve the returned result").
A run that misses an expected outcome is recorded as a failed or inconclusive attempt and is not repeated until it is green; the only repeat the protocol allows is the one named under "Inconclusive, void, fail, rollback".
Version 1 of this protocol and of its scripts (committed at `c62df3a8d`, pushed at `bcb09e8b8`) is superseded; its scripts and its baseline results are kept (`superseded/`, `checks/live-acceptance-baseline-v1-*.txt`). "Amendments" at the end lists what changed and why.

## What it decides, and what it does not

**Decides:** whether the drain build, running as the 20128 unit, persists the `call_logs` and `usage_history` rows of every request of a client that closes right after the terminal event: for Responses clients (raw clients, and the native `codex exec` in its one-request and its tool-call shapes) and for a
Chat Completions client (a non-Responses format); whether a client that reads to the end or closes later is still logged (no regression); and whether the switch changes the effort the gateway sends upstream. The switch moves 20128 from build `cf6748d04`
(v3.8.51 release branch + #13788 + the affinity patch + PR 15167 head `f5d8e150b`) to the drain build `2a41147b7` (v3.8.51 tag + the affinity patch + PR 15167 head `0585aba55` + the drain patch, no #13788), so the 12 files that only the newer PR head has
(`effortStandardization.ts` and the Responses translator helpers among them) are exercised by the effort probes.

**Does not decide:** Anthropic-format (`message_stop`) clients (the drain applies to them by code reading; no test or probe runs one); a client that closes while the upstream tail outlasts the 10 s grace period (it still leaves neither a 200 nor a 499 row,
by design of this patch; see the record's "What the patch does not close"); the 2604 host (its install has its own read-back); the gateway's pending-request counter (observed and recorded, not gated).

## Frozen inputs

- Build under test: `omniroute-3.8.51-drain-b7c68690.tgz`, sha256 `5b0e986bdff81487130cfd7c7dad20c6534f447836ff1c757e7c4bcf82d0fa14`, `dist/BUILD_SHA` `2a41147b7`, installed in the private prefix `omniroute-3.8.51-c1e30b76-affinity-pr15167-drain-b7c68690`.
- Baseline build (the condition absent) and first-hop rollback target: the running 20128 build `cf6748d04`, prefix `omniroute-3.8.51-2f42a9ac-pr13788-affinity2-pr15167`. The same frozen scripts ran against it BEFORE the switch, on 2026-10-06 (`checks/live-acceptance-baseline-*.txt`), and run again right before the switch (the pre-switch control below).
- The scripts, committed as `.txt` copies whose content is byte-identical to the scripts (run from copies without the suffix, all in one directory; the wrapper checks the first three hashes and refuses to run on a difference):

  | Script | Role | sha256 |
  | --- | --- | --- |
  | `scripts/live-acceptance.py.txt` | raw clients, `--expect observe|all-logged` | `fa8fa6f8dc3a0e7360be4a0737c34daaf4d4b58696df6a7ab3483896cb739e82` |
  | `scripts/native-exec-acceptance.py.txt` | native `codex exec`, identity and completeness | `9bd478a1502839e7cfe2c5999e3485d6e9ba5d10bfe62e2593e061b7441dda71` |
  | `scripts/gateway-identity.py.txt` | identity read-back of the unit (exit 5 on a mismatch) | `a7932710412e9e834f6b992f267db5620b64bbe62f25021013c8004a7eec6011` |
  | `scripts/pre-switch-guard.py.txt` | the pre-switch guard (exit 4 when not clean) | `b491de6b3e4a5a1d3a3761c8fa8aefc439cca8cf4c453d696c7b9cb41a73af3a` |
  | `scripts/run-acceptance.sh.txt` | the wrapper (`baseline`, `canary`, `precontrol`; its hash changes when the baseline hash is frozen into it) | `57e96463568c534cecf5f25eb35c1586d3a1cb34073ba62ea7245ce6158bd2d1` |
  | `scripts/show-log-receipt.py.txt` | the allowlisted receipt (version 2) | `7dd746bce15964c68d8b847f8072257a4b5712adca7ed7cd9089c09273ff26d6` |
- The switch tool is the committed evidence copy `evidence/artifacts/omniroute-sol-max-20260930/scripts/switch_gateways.py.txt`, sha256 `97d1b87bb651d6f43e184b9617d03afa7861ee7715e7030ad23ed29057bc23e3` (git blob `<blob id of the committed copy on main>`), run from a copy without the suffix; the guard checks the hash of the copy it is given.
  The behaviour relied on (`--only`, the single-unit rollback, the dry run's lines) was read from that copy; its rollback prints health only, so identity after a rollback is read back by `gateway-identity.py`.
- The raw baseline file the canary compares effort columns with: `evidence/artifacts/omniroute-post-terminal-drain-20261005/checks/live-acceptance-baseline-raw.txt` (git blob `(pending)`, sha256 `(pending)`), passed to the wrapper by ABSOLUTE path (a relative path made version 1's frozen command crash from `/tmp`).
- Raw requests: one streamed request each with the documented loopback placeholder key; the prompt is `Reply with: ok`; the model is `cx/gpt-6-astra` at client effort `max` unless the mode names another. A mode `responses:early:<s>` closes the socket `<s>` seconds after the data line that carries `response.completed`
  (what `codex exec` does when it exits), `chat:early:<s>` `<s>` seconds after the line `data: [DONE]`; `<format>:eof` reads to the end of the stream; `chat` is `/v1/chat/completions`, `responses` is `/v1/responses`; `effort:<model>[:<effort>]` is a Responses request read to the end with that client effort.
- Native turns: `codex exec --json -p omniroute --ephemeral` in a scratch `CODEX_HOME` that holds only the repository's omniroute profile and the loopback placeholder key, with stdin closed. Shape `astra-max`: `cx/gpt-6-astra` at effort `max`, prompt `Reply with: ok` (one request). Shape `two-request`: the same model and effort, the prompt
  asks for one shell command and then `ok` (a tool call, then the final answer; the turn must contain at least one command execution).
- Attribution of a raw request: its `call_logs` rows by the response's `X-Correlation-Id` (Chat Completions) or the response id (Responses, whose correlation header is not always set); its `usage_history` row (no correlation id) by the same model and token counts within 3 s of the matched `call_logs` row, exactly one.
- Attribution of a native turn, by IDENTITY and not by time window: each turn carries its own `X-OmniRoute-Session-Id` (a static provider header set per turn with `-c model_providers.omniroute.http_headers=...`); the gateway stores a caller-supplied session id outright as `call_logs.session_tag`
  (`open-sse/services/conversationTracker.ts` `resolveConversationId`, upstream #8249; probed on live 20128 for both paths, and the real client sends it: `checks/acceptance-controls.txt` N1). The turn's rows are `where session_tag = <its id>`, at both reads, whatever else runs on the gateway.
- Completeness of a native turn, checked against the client: the sums of `tokens_in` and `tokens_out` over the turn's `call_logs` rows must EQUAL the `input_tokens` and `output_tokens` that the client reports in its `turn.completed` event. `checks/native-usage-calibration.txt` shows why this is sound: on the unpatched build
  every turn whose rows were all stored had sums equal to the client's usage exactly, and every turn that lost its final request's rows had smaller sums. Fewer tokens stored means a request's rows are missing; more means duplicate rows.
- Reads: READ1 12 s after each request or turn ended (past the 10 s disconnect grace period by 2 s), READ2 60 s after the last one of the invocation ended. Both reads apply the full predicate, and the rows at READ2 must be the same rows with the same values as at READ1 (row id, status, path, model, tokens, effort columns).
- Verdicts and exit codes of the two acceptance scripts (spelled out in their docstrings): 0 every verdict PASS or OBSERVED, 1 any FAIL, 2 none failed but any INCONCLUSIVE, 3 a usage or script error (no verdict; raised by a preflight BEFORE any request or turn, or by an unexpected exception). A run that printed no `SUMMARY` line is not a verdict and counts as INCONCLUSIVE.
  raw, `--expect all-logged`: INCONCLUSIVE when the HTTP status is 5xx, 408 or 429, no terminal event was received, an early mode did not close early (`terminal=True closed_early=True` are required of every early-mode line), or the usage match is ambiguous; FAIL on another 4xx status, or when at either read there is not exactly one `call_logs` row
  for the request with status 200, the mode's path and the mode's model, or not exactly one `usage_history` row with status 200, or (with `--baseline`) an effort probe's four columns differ from the baseline's, or the rows changed between the reads; PASS otherwise.
  native, `--expect all-logged`: INCONCLUSIVE when the exec exits non-zero or does not exit within `--exec-timeout` (value-free diagnostics are printed: event types, stdout and stderr tails, the rows under the session id), the client reports no usage, a `two-request` turn made no tool call, or the usage match is ambiguous;
  FAIL when at either read the rows under the session id are fewer than the shape needs (1, or 2), have a status other than 200, a path other than `/v1/responses`, a model other than `gpt-6-astra` or a requested model other than `codex/gpt-6-astra`, their token sums differ from the client's usage, the matched `usage_history` rows are not one per call row with status 200, or the rows changed between the reads; PASS otherwise.
- Gateway identity: `gateway-identity.py` reads, with the same reads as the switch tool (`systemctl --user show`, the `ps` command line's `/tools/omniroute-...` segment, `dist/BUILD_SHA`, `GET /api/health`), the MainPID, the start timestamp, the running prefix, the BUILD_SHA and the health of the unit. The wrapper reads it before and after EVERY run; a run whose identity
  differs between the two reads (or is unreadable, or is not the build the kind of run is for) is VOID. The pending-request counter (`pending_total`, the gateway's own count of requests it still considers in flight) is printed with it as an observation, never a gate.

## Order of steps

1. **Freeze.** This file, the scripts and the baselines are committed and pushed; the coordinator confirms that `git ls-remote origin refs/heads/claude/99-omniroute-drain-patch-20261005` equals that commit. The commit id is the frozen head.
2. **Announce.** Send the frozen head and the planned restart time to 5f, c5 and the command center, and wait for the command center's lift of the hold (a ledger row). 5f confirms that its last 20128 run has ended (`#754 r8` ended 2026-10-06 00:34Z) and holds new GPT launches through 20128 until the acceptance is recorded; c5, the command center's lanes
   and the hindsight services are asked to pause during the acceptance windows (attribution does not depend on it, but a quiet gateway avoids INCONCLUSIVE results from the usage match).
3. **Pre-switch control**, within 15 minutes before the switch: `run-acceptance.sh precontrol <dir>` (the race set and four native two-request turns on the unpatched build, `--expect observe`, bracketed by the identity read-back, which must be the unpatched build). Rule: if it loses fewer than 2 of the 6 race requests it cannot discriminate at this hour;
   repeat it once (6 more); if the pooled result is still fewer than 2 of 12, the race set and the early modes are no-regression checks only for this canary, and the fix cannot be demonstrated now: the canary may proceed as a no-regression check, but its record says so and the PR is not queued on it (see "Queueing").
4. **Receipt before:** `show-log-receipt.py` (version 2, an allowlisted output).
5. **Dry run**, required: `python3 switch_gateways.py --only 20128 --prefix-20128 omniroute-3.8.51-c1e30b76-affinity-pr15167-drain-b7c68690 --desc-20128 "<the unit description of the record>" --dry-run` must print all of:
   `20129 omniroute-fw.service: NOT in scope`; `running omniroute-3.8.51-2f42a9ac-pr13788-affinity2-pr15167 (cf6748d04) -> omniroute-3.8.51-c1e30b76-affinity-pr15167-drain-b7c68690 (2a41147b7, shim v2)`; `prefix problems: []`; `dry run: no unit file written, nothing restarted`. Anything else stops the procedure.
6. **Guard and switch, one command line:** `python3 pre-switch-guard.py --switch-tool <the copy of the switch tool> && python3 switch_gateways.py --only 20128 <the same arguments as the dry run> --apply`. The guard exits 0 only when: the switch tool's sha256 is the pinned one; the rollback prefix has `bin/omniroute`, `dist/BUILD_SHA` `cf6748d04` and `shim/lsof` with sha256 `b6ae9002...` and is what the unit runs now (identity read-back, health ok);
   the target prefix has `bin/omniroute`, `dist/BUILD_SHA` `2a41147b7`, the same shim and the drain marker; and for 30 s (6 samples) no worker process of another lane (`omniroute-codex-sdk/worker.py`, `codex exec`, an interactive `codex` naming the omniroute profile or the port), no `call_logs` row in the last 120 s and no ACTIVE client connection to port 20128
   (a connection that carries traffic or queued data during the window). The command center asked for "no established client connection"; that cannot hold literally on this host (nine idle keep-alive connections from a periodic poller exist at rest, last active within the same 50 ms, none with queued data, owners in other PID namespaces), so the guard tolerates idle ones, reports them,
   and fails on active ones. It cannot see a request that is silent on the wire (waiting for the upstream) or an interactive client between requests: steps 2 and 3 are not replaceable by it. Keep the rollback directory the switch prints.
7. **After the switch:** the apply output must show `20128: health=True (ok) running prefix=omniroute-3.8.51-c1e30b76-affinity-pr15167-drain-b7c68690 identity_ok=True`, `20129 omniroute-fw.service: untouched; running omniroute-3.8.51-2f42a9ac-pr13788 (87c4c488d)` and `switched: ['20128']`; then `show-log-receipt.py` again (a new MainPID, the same drop-in declaration, health ok).
8. **Acceptance**, within 2 hours of the switch: `run-acceptance.sh canary <dir> <absolute path of the raw baseline file>` (about 17 minutes). Its exit status must be 0.
9. **After a pass:** the journal command below at the end of the acceptance and again 30 minutes later; the PR is updated with the results (`checks/live-acceptance-canary-*.txt`, the receipts) and queued only under "Queueing".

## Commands (exact argument vectors) and repetitions (frozen)

`run-acceptance.sh` runs these four commands in this order (`<E>` is `observe` for `baseline` and `precontrol`, `all-logged` for `canary`; the canary adds `--baseline <absolute path>` to the first), each bracketed by the identity read-back and followed by the journal check. `P` is the directory of the scripts; the wrapper runs from `/tmp`:

```
# 1 raw set: eleven requests (responses:early:0 twice, chat:early:0 twice, the rest once)
python3 $P/live-acceptance.py --expect <E> [--baseline <absolute path>] --wait1 12 --wait2 60 \
  responses:eof responses:early:0 responses:early:0 responses:early:0.5 responses:early:2 chat:eof chat:early:0 chat:early:0 \
  effort:cx/gpt-6-astra:max effort:cx/gpt-6.1-sol-max effort:cx/gpt-6.1-sol:max
# 2 race set: responses:early:0 six times
python3 $P/live-acceptance.py --expect <E> --wait1 12 --wait2 60 responses:early:0 (x6)
# 3 native, one-request shape: four turns
python3 $P/native-exec-acceptance.py --expect <E> --wait1 12 --wait2 60 --quiet-timeout 120 --exec-timeout 300 astra-max (x4)
# 4 native, tool-call shape: eight turns
python3 $P/native-exec-acceptance.py --expect <E> --wait1 12 --wait2 60 --quiet-timeout 120 --exec-timeout 300 two-request (x8)
```

The `precontrol` kind runs only commands 2 and 4 (with four turns) and prints `PRECONTROL race_lost=<n>/6 tworequest_incomplete=<m>/4 race_discriminating=<True|False>`.
The journal check, run by the wrapper after every run and by hand at the end of the acceptance and 30 minutes later: `journalctl --user -u omniroute.service --since "<the unit's ExecMainStartTimestamp>" -o cat --no-pager | grep -c 'Failed to save call log'`; any count above zero on the canary is a rollback trigger.
Each wrapper run's status: 4 VOID, 1 FAIL (a script exit 1, or a journal count above zero), 2 INCONCLUSIVE (a script exit 2 or 3, or no SUMMARY line), else 0; the wrapper exits with the first that applies of 4, 1, 2, 0.

## Expected outcomes (frozen) and what the baseline showed

| Run | Mode | Baseline build `cf6748d04`, v2 scripts, observed | Canary, drain build `2a41147b7` (verdict) |
| --- | --- | --- | --- |
| raw | `responses:eof` | pending | PASS: 1 and 1, status 200, at READ1 and READ2 (no regression) |
| raw | `responses:early:0` (x2) | pending (version 1 of the scripts: 1 of 2 lost on 2026-10-06) | PASS: 1 and 1 each |
| raw | `responses:early:0.5`, `responses:early:2` | pending | PASS: 1 and 1 each (no regression) |
| raw | `chat:eof`, `chat:early:0` (x2) | pending | PASS: 1 and 1 each (no regression) |
| effort | the three effort probes | pending: the four effort columns of each | PASS: 1 and 1 and exactly the baseline's four columns |
| race | `responses:early:0` (x6) | pending (version 1: 5 of 6 lost) | PASS: 6 of 6, 1 and 1 each |
| native | `astra-max` (x4) | pending (calibration: 1 of 3 single-request turns lost its rows) | PASS: every turn complete (token sums equal to the client's usage), at READ1 and READ2 |
| native | `two-request` (x8) | pending (calibration: 3 of 7 turns lost the final request's rows) | PASS: every turn complete, at READ1 and READ2 (a gate) |

**Which checks discriminate.** Pending the version-2 baselines. Observed so far on the unpatched build: the race set lost 5 of 6 requests and the raw `responses:early:0` requests 12 of 14 across five runs of version 1 of the scripts (`checks/live-acceptance-baseline-v1-*.txt`, `checks/pre-patch-repro-20128.txt`), and the calibration series (`checks/native-usage-calibration.txt`) lost the final request's rows in 3 of 7 two-request turns and the rows of 1 of 3 single-request turns.

## Offline controls of the scripts

`checks/acceptance-controls.txt` and `checks/acceptance-controls-v1-reproduction.txt` hold the controls of the scripts' decision logic, run before the baselines: version 1 and version 2 against a stub gateway with the live store's table definitions, the real `codex exec` as the native client where it can complete a turn and a fake client where it cannot (a tool-call turn, a failing exec, a hang);
the identity read-back and the guard against dummy processes and a scratch tools directory; the wrapper against the stub. They are synthetic-fixture checks (evidence class `local_integration`), not evidence about OmniRoute, and no gateway request was sent for them. They show version 1 giving the wrong answer in the cases the reads named (three healthy native turns failing at the second read,
unrelated rows or a failed exec passing, a status that changes after the first read passing, a missing terminal event passing, a missing baseline file or an unknown mode exiting with the FAIL code) and version 2 giving the right one, and they cover INCONCLUSIVE for a hang, a failed exec, a turn without a tool call, no client usage, HTTP 429 and 5xx and an ambiguous usage match,
exit 3 before any request for every usage error, and the guard's red and green cases.

## Inconclusive, void, fail, rollback

- INCONCLUSIVE (a raw sample that does not exercise its mode, a native turn that did not complete or lacks what the shape needs, an ambiguous usage match, a script error, no SUMMARY line): the INCONCLUSIVE requests or turns are repeated once, as a smaller invocation with the same argument vector and the missing count, in a quieter window;
  a repeat that is again INCONCLUSIVE counts as NOT ACCEPTED. The scripts print their value-free diagnostics for every such turn (event types, stdout and stderr tails, the rows stored under the session id); they stay in the folder with the run.
- VOID (the gateway's identity changed during a run, was unreadable, or was not the build under test): a restart of the unit, a change of prefix or a failed health read during the acceptance means the build under test was not stable: roll back.
- Roll back at once (`python3 switch_gateways.py --rollback <the switch directory it printed>`, which restarts only 20128 to the baseline prefix) on any of: a FAIL; a VOID; an effort column that differs from the baseline's; a health failure of the unit; a `Failed to save call log` line; NOT ACCEPTED; no complete acceptance within 2 hours of the switch.
  The failed run is kept as recorded.
- After ANY rollback: `gateway-identity.py --expect-prefix omniroute-3.8.51-2f42a9ac-pr13788-affinity2-pr15167 --expect-build cf6748d04` must exit 0 (health ok), `show-log-receipt.py` is run again, and 20129 must still run `omniroute-3.8.51-2f42a9ac-pr13788` (`87c4c488d`). 20129 is not switched at any point.
- After a pass, the unit's journal is scanned over 30 minutes of normal lane traffic (the journal command above): zero `Failed to save call log` lines, and the receipt after the switch shows the same drop-in declaration, a new `MainPID`, health ok and no credential-shaped strings except the known `[ModelSync]` account labels.

## Queueing

The PR is queued only after every gated request and turn of the canary passed at both reads (the wrapper's exit status 0), the 30-minute journal scan is clean and the after-switch receipt is recorded, all in `checks/`. On a FAIL, a VOID or a rollback the record is amended first (the candidate was rolled back, why, with the failed run kept as recorded) and the PR is not queued on the strength of "the results are in".
A canary that passed only as a no-regression check (the pre-switch control found the race set unable to discriminate) is recorded as that and does not support adoption.

## Records kept

For every run: the exact argument vector, the working directory, the start and end times, the script sha256 (all on the `FROZEN` line), the exit code (the `SUMMARY` line, `exit=` and `RUN-STATUS`), the identity before and after, the journal count, the pending-counter delta and the full stdout, as `checks/live-acceptance-canary-*.txt` next to the baselines
(the committed copy shortens UUID-shaped correlation ids to their first 8 hex digits, because the repository's publication check rejects full UUIDs, and starts with a note carrying the sha256 of the unshortened text; the unshortened outputs of the baselines, the controls and the canary are kept gzipped in the first host's private artifact directory and listed with their sha256 in `checks/logs/MANIFEST.txt`).
The unit's state before and after the switch is kept value-free (`systemctl --user show` fields, the receipts, the identity lines). Failed, inconclusive and void runs stay in the folder.

## Amendments

- 2026-10-06, before the switch, after a full-scope read of `bcb09e8b8` (GPT-6 Astra max, relayed by 5f) and the command center's round-3 ruling on the same head: version 1 of this protocol and of its three scripts is replaced. The reads found, and offline controls reproduced, that version 1 (a) failed a healthy three-turn native canary at the second read (each turn's window ran to the present),
  (b) passed a failed exec plus unrelated rows, (c) let a raw request pass with no terminal event or after its call status changed from 200 to 499 (only the row COUNT was compared at the second read), (d) left the native two-request turn ungated although it exercises the tool-handoff path the patch changes, (e) printed every line of the drop-in file in a "value-free" receipt,
  (f) crashed from `/tmp` on its relative `--baseline` path with exit 1, the FAIL code, and exited 1 or 2 on usage errors and hangs, (g) said nothing about restarting 20128 while a client run is in flight, (h) did not pin the switch tool, re-check the rollback prefix or verify identity after a rollback, (i) did not tie results to the build that was serving,
  (j) named no command for the `Failed to save call log` trigger and no action for NOT ACCEPTED, and (k) took its discriminating control from earlier in the day. Version 2 fixes each (identity and completeness for native turns, the full predicate and stability at both reads for raw requests, exit 3 and a preflight for errors, the guard, the identity read-back and VOID rule,
  the pinned switch tool and its required lines, the pre-switch control, the journal command, the queue rule), and the baselines were run again with it. The offline controls also found that `codex exec` waits on an open stdin, so the native script closes it, and the live trial of the guard found that the command center's "no established client connection" cannot hold on this host (see step 6).
