route-mapper: the pre-patch off-pin control is frozen as the hourly table below, with its method and hashes. The script is inline at the end, because Write is disabled for me. Everything was read-only. It ran at 2026-09-28T03:31:57Z with argv START=2026-09-27T06:00:00Z and END=2026-09-28T04:00:00Z; the 03Z hour is partial.

**Method**
1. **Pinned connection:** each app.log JSON line with tag AUTH and a message matching "-> connection <8 hex>" (both "(affinity)" hits and "new affinity created"). **Served connection:** the first 8 characters of connection_id on the call_logs row with provider='codex' (all paths), whose start time = timestamp − duration/1000.
2. **Pairing:** a log line pairs with a row only when exactly one row starts within ±0.5 s of it AND no other affinity line falls within ±1.0 s. The pair counts as off-pin when served ≠ pinned, and it is bucketed by the log line's UTC hour.
3. **Cache share:** Σtokens_cache_read / Σtokens_in over paired 200 rows.
   - **Peak in-flight:** a sweep over the [start, end] intervals of the codex rows, sampled at start events inside the hour. peak_acct is the maximum over accounts.
   - **Mid-turn changes:** from the request artifacts (call_logs artifact_relpath under ~/.local/share/omniroute/call_logs/), requestBody.client_metadata gives (thread_id, turn_id). A change is a consecutive request in the same turn served by a different account.
   - **Sources:** storage.sqlite (call_logs, provider_connections) opened with mode=ro; logs/application/app.log*.

**Hashes**
- sha256(script) = c4515e7660c47d725c79696c7211b71f26bd0c5d789b3f2a7e9a444f1d778477 (4790 bytes, UTF-8, ends with a single newline).
- sha256(SQL_PRIO + "\n" + SQL_ROWS) = c8f207c52479795c3c24c302b918afcbb6882055796162c7b095c4a5f8d7f9b4
- Run it as `python3 offpin_control.py <START> <END>`.

**Meta:** 1 log file, starting 2026-09-27T06:58:38Z; 7436 affinity lines; 7270 codex rows; 306 (thread, turn) groups.

hour_utc | turns | peak_total | peak_acct | matched | off | off% | off_rule_ok | cache_moved% | cache_kept% | req_with_turn_id | midturn_changes
09-27T06 | 12 | 5 | 2 | 4 | 0 | 0.0 | 0 | - | 0.0 | 2 | 0
09-27T07 | 49 | 5 | 2 | 45 | 0 | 0.0 | 0 | - | 83.4 | 45 | 0
09-27T08 | 347 | 8 | 6 | 218 | 0 | 0.0 | 0 | - | 94.2 | 331 | 0
09-27T09 | 127 | 5 | 5 | 76 | 0 | 0.0 | 0 | - | 94.0 | 121 | 0
09-27T10 | 14 | 4 | 1 | 10 | 0 | 0.0 | 0 | - | 97.7 | 0 | 0
09-27T11 | 34 | 4 | 2 | 30 | 0 | 0.0 | 0 | - | 87.6 | 30 | 0
09-27T12 | 474 | 13 | 6 | 228 | 38 | 16.7 | 38 | 87.7 | 94.8 | 427 | 33
09-27T13 | 239 | 6 | 3 | 202 | 10 | 5.0 | 10 | 91.7 | 96.0 | 163 | 7
09-27T14 | 312 | 14 | 4 | 219 | 38 | 17.4 | 38 | 78.8 | 95.9 | 243 | 25
09-27T15 | 557 | 13 | 5 | 360 | 33 | 9.2 | 33 | 88.1 | 95.1 | 394 | 14
09-27T16 | 1348 | 32 | 11 | 543 | 118 | 21.7 | 118 | 88.5 | 94.0 | 944 | 131
09-27T17 | 824 | 15 | 6 | 363 | 13 | 3.6 | 13 | 89.5 | 96.1 | 557 | 7
09-27T18 | 666 | 18 | 10 | 361 | 10 | 2.8 | 10 | 85.4 | 96.3 | 506 | 7
09-27T19 | 398 | 10 | 3 | 291 | 18 | 6.2 | 18 | 90.1 | 93.4 | 346 | 2
09-27T20 | 529 | 11 | 3 | 391 | 16 | 4.1 | 16 | 66.0 | 95.6 | 351 | 9
09-27T21 | 231 | 7 | 4 | 176 | 5 | 2.8 | 5 | 96.9 | 94.6 | 209 | 1
09-27T22 | 292 | 9 | 3 | 212 | 0 | 0.0 | 0 | - | 89.8 | 278 | 2
09-27T23 | 511 | 9 | 2 | 397 | 40 | 10.1 | 40 | 85.6 | 91.8 | 435 | 9
09-28T00 | 214 | 7 | 2 | 175 | 0 | 0.0 | 0 | - | 92.0 | 173 | 0
09-28T01 | 28 | 5 | 2 | 22 | 0 | 0.0 | 0 | - | 87.3 | 22 | 0
09-28T02 | 58 | 7 | 2 | 47 | 0 | 0.0 | 0 | - | 85.6 | 51 | 0
09-28T03 (partial) | 6 | 5 | 1 | 0 | 0 | - | 0 | - | - | 0 | 0
TOTAL | 7270 | 32 | 11 | 4370 | 339 | 7.8 | 339 | 85.6 | 94.3 | 5628 | 247

**By load** (summed by hand from the rows above):
- **Loaded hours (peak_total ≥10):** 12, 14, 15, 16, 17, 18, 19 and 20Z. Off-pin 284 of 2756 = 10.3%; 228 of the 247 mid-turn changes.
- **Other hours:** 55 of 1614 = 3.4%. Of those, 40 fall in 23Z, at peak 9.
- off_rule_ok = off in every hour: every move went to an account with priority ≤ the pinned account's priority + 1.
- The 247 mid-turn changes match the P19 figure from before.

**Caveats**
- app.log begins at 06:58:38Z, so 06Z has only 4 matched pairs.
- If app.log rotates, the post-patch run relies on the app.log* glob reaching the rotated files in the same directory.
- 5628 of 7270 rows have a readable turn_id; the rest have missing or truncated artifacts.
- Artifact and app.log retention is unknown, so this table is the frozen copy.
- peak_acct is sampled only at the account's own start events.

**Script** (save the bytes between the markers as offpin_control.py, with one trailing newline, and check sha256sum):
