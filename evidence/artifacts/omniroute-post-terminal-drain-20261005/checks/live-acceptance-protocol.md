# Live acceptance of the drain build on 20128: the protocol, frozen before the switch (2026-10-06)

This file is frozen by the commit that adds it, before the canary switch. It fixes the inputs, the commands, the repetitions, the expected outcomes and the rollback triggers (`docs/acceptance-evidence-policy.md`, "Preserve the returned result").
A run that misses an expected outcome is recorded as a failed or inconclusive attempt and is not repeated until it is green; the only repeat the protocol allows is the one named under "Inconclusive, fail, rollback".

## What it decides, and what it does not

**Decides:** whether the drain build, running as the 20128 unit, persists exactly one `call_logs` row and one `usage_history` row for a client that closes right after the terminal event, for Responses clients (raw clients and the native `codex exec`) and for a
Chat Completions client (a non-Responses format); whether a client that reads to the end or closes later is still logged (no regression); and whether the switch changes the effort the gateway sends upstream. The switch moves 20128 from build `cf6748d04`
(v3.8.51 release branch + #13788 + the affinity patch + PR 15167 head `f5d8e150b`) to the drain build `2a41147b7` (v3.8.51 tag + the affinity patch + PR 15167 head `0585aba55` + the drain patch, no #13788), so the 12 files that only the newer PR head has
(`effortStandardization.ts` and the Responses translator helpers among them) are exercised by the effort probes below.

**Does not decide:** Anthropic-format (`message_stop`) clients (the drain applies to them by code reading; no test or probe runs one); a client that closes while the upstream tail outlasts the 10 s grace period (it still leaves neither a 200 nor a 499 row,
by design of this patch; see the record's "What the patch does not close"); the 2604 host (its install has its own read-back); a tool-call turn of the native client (observed, not a gate).

## Frozen inputs

- Build under test: `omniroute-3.8.51-drain-b7c68690.tgz`, sha256 `5b0e986bdff81487130cfd7c7dad20c6534f447836ff1c757e7c4bcf82d0fa14`, `dist/BUILD_SHA` `2a41147b7`, installed in the private prefix `omniroute-3.8.51-c1e30b76-affinity-pr15167-drain-b7c68690`.
- Baseline build (the condition absent): the running 20128 build `cf6748d04`, prefix `omniroute-3.8.51-2f42a9ac-pr13788-affinity2-pr15167`. The same frozen scripts ran against it BEFORE the switch (`checks/live-acceptance-baseline-*.txt`), so a pass of the canary is read next to runs in which the patch is absent.
- Scripts: `scripts/live-acceptance.py.txt` (sha256 `8aa14054401c00a5af1e8c180fc83af80c79cc0a807da98ea519149291188859`) and `scripts/native-exec-acceptance.py.txt` (sha256 `9f511620db390c3b4c7177f858342c6592680efd1d383e2e02ecf3f5d249fdee`), run from copies without the `.txt` suffix;
  the sha256 each run prints on its `FROZEN` line must equal the value above, or the run does not count.
- Request shapes: raw clients send one streamed request each with the documented loopback placeholder key; the prompt is `Reply with: ok`; the model is `cx/gpt-6-astra` at client effort `max` unless the mode names another.
  A mode `responses:early:<s>` closes the socket `<s>` seconds after the data line that carries `response.completed` (what `codex exec` does when it exits), `chat:early:<s>` `<s>` seconds after the line `data: [DONE]`; `<format>:eof` reads to the end of the stream;
  `chat` is `/v1/chat/completions`, `responses` is `/v1/responses`; `effort:<model>[:<effort>]` is a Responses request read to the end with that client effort. The native shapes are `astra-max` (one request, the final-request shape: `cx/gpt-6-astra` at effort `max`, prompt `Reply with: ok`) and
  `two-request` (a tool call, then the final answer). `codex exec` runs with a scratch `CODEX_HOME` that holds only the repository's omniroute profile and the loopback placeholder key.
- Attribution: `call_logs` rows by the response's `X-Correlation-Id` (`/v1/chat/completions`) or the response id (`/v1/responses`, whose correlation header is not always set); `usage_history` rows (no correlation id) by the same model and token counts as the matched
  `call_logs` row within 3 s of it, and exactly one must match. The totals of both tables in the request's window are printed, so other lanes' traffic is visible. The native `codex exec` cannot read the header: it runs only in a quiet window (before a turn no worker process of another lane
  is running and no `call_logs` row was written in the last 120 s; the script polls up to its `--quiet-timeout` and otherwise sends nothing and reports INCONCLUSIVE), and after the turn the window must hold exactly the expected number of rows in each table (more rows mean other traffic: INCONCLUSIVE).
- Reads: READ1 12 s after each request ended (past the 10 s disconnect grace period by 2 s), READ2 60 s after the last request of the run ended. A row that appears or disappears between the reads turns a PASS into a FAIL.
- Verdicts (the script's own): `--expect observe` prints OBSERVED and no verdict; `--expect all-logged` gives PASS only for exactly one `call_logs` row with status 200 and exactly one `usage_history` row, in READ1 and READ2; INCONCLUSIVE when the usage match is ambiguous;
  FAIL otherwise. Exit code 0 when every verdict is PASS or OBSERVED, 1 when any is FAIL, 2 when none failed but any is INCONCLUSIVE.

## Preconditions

1. The command center has lifted the hold on the canary; 5f and c5 are told the restart time and 5f holds new GPT launches through 20128 until the acceptance is recorded (a worker in flight is cut by the restart).
2. The baseline files exist, are committed and pushed (this file's commit or a later one before the switch).
3. The previous prefix `omniroute-3.8.51-2f42a9ac-pr13788-affinity2-pr15167` (build `cf6748d04`) stays installed untouched until the acceptance passes: it is the first-hop rollback target (see the record, "Rollback of the drain switch").
4. `scripts/show-log-receipt.py.txt` is run before and after the switch (value-free receipt of the units).

## Commands (exact argument vectors) and repetitions (frozen)

Run from `/tmp` (the scripts print their `cwd` and start and end times). `P` is the directory of the scripts. The baseline column is what already ran, same day, against build `cf6748d04`.

```
# 1 raw set: eleven requests (responses:early:0 twice, chat:early:0 twice, the rest once)
python3 $P/live-acceptance.py --expect observe --wait1 12 --wait2 60 \
  responses:eof responses:early:0 responses:early:0 responses:early:0.5 responses:early:2 \
  chat:eof chat:early:0 chat:early:0 \
  effort:cx/gpt-6-astra:max effort:cx/gpt-6.1-sol-max effort:cx/gpt-6.1-sol:max                       # baseline (checks/live-acceptance-baseline-raw.txt)
python3 $P/live-acceptance.py --expect all-logged --baseline checks/live-acceptance-baseline-raw.txt --wait1 12 --wait2 60 <the same eleven modes>   # canary (gate)

# 2 race set: responses:early:0 six times
python3 $P/live-acceptance.py --expect observe --wait1 12 --wait2 60 responses:early:0 (x6)           # baseline (checks/live-acceptance-baseline-race.txt)
python3 $P/live-acceptance.py --expect all-logged --wait1 12 --wait2 60 responses:early:0 (x6)       # canary (gate)

# 3 native codex exec, quiet window: three single-request turns (gate), then one tool-call turn (observed only)
python3 $P/native-exec-acceptance.py --expect observe --wait1 12 --wait2 60 --quiet-timeout 900 astra-max astra-max astra-max     # baseline (checks/live-acceptance-baseline-native.txt)
python3 $P/native-exec-acceptance.py --expect all-logged --wait1 12 --wait2 60 --quiet-timeout 900 astra-max astra-max astra-max  # canary (gate)
python3 $P/native-exec-acceptance.py --expect observe --wait1 12 --wait2 60 --quiet-timeout 900 two-request                         # baseline (checks/live-acceptance-baseline-native-tworequest.txt) and canary, never a gate
```

## Expected outcomes (frozen) and what the baseline showed

| Run | Mode | Baseline build `cf6748d04`, observed (no verdict) | Canary, drain build `2a41147b7` (verdict) |
| --- | --- | --- | --- |
| raw | `responses:eof` | 1 `call_logs` and 1 `usage_history` row | PASS: 1 and 1, status 200, in READ1 and READ2 (no regression) |
| raw | `responses:early:0` (x2) | one request logged, one lost (0 and 0, in READ1 and READ2) | PASS: 1 and 1 each |
| raw | `responses:early:0.5`, `responses:early:2` | 1 and 1 each (the upstream tail has usually ended by then) | PASS: 1 and 1 each (no regression) |
| raw | `chat:eof` | 1 and 1 | PASS: 1 and 1 |
| raw | `chat:early:0` (x2) | 1 and 1 each (the Chat Completions stream's terminal chunk and the upstream end coincide; the handler check of the record covers the chat drain) | PASS: 1 and 1 each (no regression) |
| effort | `effort:cx/gpt-6-astra:max` | model `gpt-6-astra`, requested model `codex/gpt-6-astra`, requested effort `max`, upstream effort `max` | PASS: 1 and 1 and exactly these four columns |
| effort | `effort:cx/gpt-6.1-sol-max` | model `gpt-6.1-sol-max`, requested model `codex/gpt-6.1-sol-max`, requested effort `None`, upstream effort `max` | PASS: 1 and 1 and exactly these four columns |
| effort | `effort:cx/gpt-6.1-sol:max` | model `gpt-6.1-sol`, requested model `codex/gpt-6.1-sol`, requested effort `max`, upstream effort `max` | PASS: 1 and 1 and exactly these four columns |
| race | `responses:early:0` (x6) | 5 lost (0 and 0 in both reads), 1 logged | PASS: 6 of 6, 1 and 1 each |
| native | `astra-max` (x3) | no row in either table, three times, in both reads | PASS: each turn leaves exactly 1 `call_logs` and 1 `usage_history` row in a quiet window, in READ1 and READ2 |
| native | `two-request` | 2 `call_logs` and 2 `usage_history` rows in one run (the loss is a race, so this run does not discriminate) | recorded as observed (not a gate) |

**Which checks discriminate.** The fix is evidenced only by the checks the baseline failed: the race set, `responses:early:0` of the raw set and the native `astra-max` turns. On build `cf6748d04`, between 20:17Z on 2026-10-05 and 00:11Z on 2026-10-06, 12 of the 14 raw `responses:early:0` requests of five retained runs left no row
(`checks/pre-patch-repro-20128.txt` 2 of 2, `checks/live-acceptance-control-unpatched-v2-script.txt` 2 of 2, `superseded/live-acceptance-baseline-attempt1-output.txt` 2 of 2, `checks/live-acceptance-baseline-raw.txt` 1 of 2, `checks/live-acceptance-baseline-race.txt` 5 of 6) and the three native turns left none.
Eight of eight `responses:early:0` requests logged on the canary would have probability about 1.7e-7 at that loss rate (12/14) and 0.4% at a loss rate of one half, if the build did nothing and the requests were independent; the native turns add three more. The other modes passed on the baseline: on the canary they are no-regression checks and say nothing about the fix.
If a rerun of the baseline ever shows no lost request in the race set, the race set is a no-regression check only and the native turns carry the evidence.

## Inconclusive, fail, rollback

- INCONCLUSIVE (the usage match is ambiguous, or the native window was not quiet): that mode is repeated once, in a quieter window; two INCONCLUSIVE results for the same mode count as not accepted.
- FAIL in any gated mode (including a mode that passed on the baseline), an effort column that differs from the values above, a health failure of the unit, or a `Failed to save call log` line in the unit's journal during the window: the canary is rolled back at once
  (`switch_gateways.py --rollback <the switch directory it printed>`: only 20128 is restarted, to the baseline prefix) and the failed run is kept as recorded.
- The acceptance must be complete within two hours of the switch; otherwise the canary is rolled back.
- After a pass, the journal of the unit is scanned over 30 minutes of normal lane traffic: zero `Failed to save call log` lines, and the receipt after the switch shows the same drop-in, a new `MainPID`, health ok and no credential-shaped strings except the known `[ModelSync]` account labels.

## Records kept

For every run: the exact argument vector, the working directory, the start and end times, the script sha256 (all on the `FROZEN` line), the exit code (the `SUMMARY` line and the shell's) and the full stdout, as `checks/live-acceptance-canary-*.txt` next to the baselines (the committed copy shortens UUID-shaped correlation ids to their first 8 hex digits, because the repository's publication check rejects full UUIDs, and starts with a note carrying the sha256 of the unshortened text, as the baseline files do). The unit's state before and after the switch is kept value-free
(`systemctl --user show` fields, the receipt script's output). Failed or inconclusive runs stay in the folder.
