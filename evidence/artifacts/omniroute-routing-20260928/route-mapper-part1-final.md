
## Part 1 FINAL (01:22Z -> 03:29Z), received 03:3xZ
- No cutoff: no account reached <=1% or was marked exhausted. Latest remaining: p1 6 (00:43Z), p2 17 (00:43Z), p3 12 (01:41Z), p4 4 (02:51Z), p5 52 (03:08Z), p6 70 (02:51Z).
  - Snapshots are written only when the value changes (quotaCache.ts:569-575, #4438), so a missing row means an unchanged value.
  - No log line exists for a limit-policy exclusion; a cutoff would appear as traffic stopping, plus affinity-cleared and new-affinity lines.
- 20128: 83 Codex turns, all 200 (no 429, 499, 5xx or invalid_encrypted_content). app.log: 70 affinity hits, 7 new pins; 0 cleared, 0 rotation. audit_log: 0 codex.account_rotation. Cache share 83.2%. Peak in-flight 7 in total, <=2 per account.
- Off-pin (served != pin), per-turn method (the AUTH affinity line matched to call_logs within ±0.5 s, unique pairs only):
  - since 01:22Z: 0/66;
  - 06:58Z -> 00:13Z: 339/4231 = 8.0%, all with served prio <= pin prio + 1; cache 85.6% on moved turns vs 94.5% on the rest;
  - the earlier 10.3% used the per-conversation pin-creation method on the same day.
  - The rate depends on load: hours with peak 4-8 mostly 0%; 12Z 16.7% (peak 13); 14Z 17.4% (14); 16Z 21.7% (32); 23:30-00:15Z 2.3% (peak 6).
  - => 0/66 at peak 7 is not evidence of a fix. A usable pre-patch control needs a loaded window (peak >=10 or >~300 turns/h), captured BEFORE the patch.
- 20129 after the limiter was disabled: GET /api/rate-limits shows sharedgw enabled=false, queued 0, running 0. 2 turns (01:53:18Z, 02:53:19Z), both 200 with added_wait_ms 0; no queue or limit lines in the fw app.log.
  - Caveat: the 18 turns before the change also show added_wait_ms 0, so that column may not record limiter waits.
