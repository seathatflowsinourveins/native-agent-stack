# route-mapper post-resume findings, 2026-09-28. Relayed verbatim in substance by team-lead from teammate messages. route-mapper cannot write files.

All read-only: GET, sqlite mode=ro, app.log, source at a58000c7+PR14904 (the routing files are the same as dd6e9607e).

## Check 1: traffic affected by providerStrategies.codex.fallbackStrategy=expiry-first (option d)
- chat.ts:1685-1686 gives every chat request a sessionKey: the affinity key, else the session id, else request:<uuid>. Affinity (auth.ts:1965-1993 -> sessionAffinityPin.ts:272-320) returns the pin, or places a new pin by LRU (:306). Strategy runs only when affinity returns nothing (auth.ts:1995).
- On an upstream 429 the inner Codex rotation (providerExecutionPipeline.ts:373-405):
  - marks the scope rate-limited until Retry-After (default 60 s);
  - clears the pin;
  - calls getProviderCredentials("codex", null, null, model, {excludeConnectionIds}) with NO sessionKey. That is the strategy branch (auth.ts:1997-2157), where round-robin's LRU fallback sits (:2058-2082).
  - This is the ONLY place (d) changes anything. The rotation target is not pinned.
- The outer retry (chat.ts:2236-2248) and the next request on the same key get a new LRU pin (:306). The strategy is not reached.
- Source-derived risk, not yet observed (0 x 429 in 24 h): one 429 can move a session twice (rotation target, then LRU re-pin), costing two cold turns.
- Verdict: (d) affects only the inner 429 rotation target within a request. It is optional and low value, and was NOT applied (20128 is frozen for R02 anyway).

## Check 2: quota window
- scoreExpiryFirstQuota (open-sse/services/combo/quotaScoring.ts:412-445) loops over RESET_WINDOW_NAMES=["weekly","session","monthly"] (combo/types.ts:13).
  - usable = MIN remaining across the windows present; deadline = NEAREST reset.
  - score = usable/hours-to-reset, with a 0.25 h floor (:375-388).
  - Score 0 when usable <=1% or limitReached.
  - Input: buildConnectionQuotaWindowsView (expiryFirstAccountSelection.ts:47-64), quota cache only.
  - It does not read codexLimitPolicy use5h/useWeekly; those feed only the 99% cutoff (auth.ts:259-268, 309-323, 359-376).
- window_key assignment: codexQuotaFetcher.ts:38-39 and :372-374, :426-428. The upstream usage response's primary_window is stored as "session" and secondary_window as "weekly". So window_key records position, not a measured duration.
  - CORRECTION to an earlier message: "session" is NOT filled from the x-codex-5h-usage header. quota.ts:26-31 parses those headers into a separate cooldown snapshot (0.95 threshold, quota.ts:84-87).
  - The writer is quotaCache.ts:579-584. window_duration_ms is null on every row.
- quota_snapshots: 555 rows, all window_key=session, none weekly. One next_reset_at per account across the whole history, and no upward jump over 2 points:

| prio | rows | span | remaining | reset |
|---|---|---|---|---|
| 1 | 122 | 09-27 07:18Z -> 09-28 00:43Z | 100 -> 6 | 2026-10-04T06:58Z |
| 2 | 116 | 07:18Z -> 00:43Z | 100 -> 17 | 2026-10-04T06:59Z |
| 3 | 123 | 07:18Z -> 01:11Z | 100 -> 12 | 2026-10-04T07:00Z |
| 4 | 120 | 07:18Z -> 01:11Z | 100 -> 5 | 2026-10-04T07:02Z |
| 5 | 51 | 18:58Z -> 01:11Z | 81 -> 56 | 2026-10-04T00:35Z |
| 6 | 23 | 22:21Z -> 01:17Z | 82 -> 71 | 2026-10-03T17:14Z |

- Binding window: the upstream's primary window, stored as "session". It BEHAVES AS 7-DAY, not 5 h: there was no reset in 18 h, and the prio1-4 resets fall exactly 7 days after first use (09-27 ~07:00Z). This is inferred, because the length is not recorded.
- Cutoff comparator: getQuotaWindowStatus (quotaCache.ts:713-755) triggers at remaining <=0 or used >=99, i.e. remaining <=1%. evaluateQuotaLimitPolicy (auth.ts:384-425) checks session and weekly; weekly has no data and is skipped.
- Projection (not measured): the pool has 167 account-% (about 161 above the cutoffs). At the pre-pause burn of about 28%/h summed, every account reaches its cutoff after about 5.7 h of full load.
- Recomputed expiry-first ranking at 01:22Z: 6(0.52) > 5(0.39) > 2(0.11) > 3(0.08) > 1(0.04) > 4(0.03).

## Part 1 interim (01:22Z): cutoff capture
- Codex turns per 5 min fell from 33-67 (23:30-00:10Z) to 0-14 during the pause. Every turn since 23:30Z returned 200 (no 429, 499 or 5xx).
- No cutoff happened. prio4 went 6 -> 5 (00:43 -> 00:59Z); prio1 has been flat at 6 since 00:25Z. The earlier projection (prio4 ~01:21Z, prio1 ~01:29Z) no longer holds.
- app.log since 01:00Z: 4 affinity hits; no new, cleared, rotation or limit-policy lines.
- (The final part 1 report follows after 01:45Z.)

## Part 3: upstream fix search for the occupancy-after-affinity defect (P1)
- Base a58000c7685f (2026-09-27T05:01:55Z) = the head of the default branch release/v3.8.51.
- 547 branches, each compared a58000c7...<head>: 520 diverged, 26 behind, 1 identical, 0 errors.
  - 31 branches have non-base commits touching auth.ts, chat.ts, sessionAffinityPin.ts or oauthSessionOccupancy.ts (main is not among them).
  - 22 were patch-scanned for moreAvailablePeer, reserveOAuthSession, getOAuthSessionAvailability, oauthSessionOccupancy, selectSessionAffinityConnection, applySessionAffinityPin and "occupancy": 0 lines.
  - 9 had patches too large; checked by commits?path&since=2026-08-01: 1 non-base commit, e52842b926 (2026-08-04 merge on compression-core), which predates the override itself (#8940 = d774cceca, 2026-08-11).
  - 27 branches hit the 300-file compare cap; checked by commits?path&since=2026-08-11: 87 commits, 2 non-base, 0 token lines.
- PR search: 10 queries. Only "occupancy" returned results, 12 PRs (#3922, #8940, #9021, #10362, #11389, #11758, #11775, #12395, #13675, #13676 open, #13840, #14457). All concern chat admission or leases.
- Open PRs: 354 in total; 23 touch those files. Only #13102 changes the override:
  - "[defer] feat(auth): add per-API-key ordered connection preference". Open; labels deferred-v3.8.52 and protected-surface; mergeable_state dirty; base release/v3.8.51; head baaaaf318c61aec0dfdfa979df41ec0767a2944b.
  - It adds `&& !selectedByApiKeyPreference` to the reserveOAuthSession/oauth condition (auth.ts L2154-2158 at its head). The preference pick runs only when affinity returned nothing, so it exempts API-key-preferred picks only and does NOT protect affinity pins.
- Result: no upstream fix on any branch or open PR as of 2026-09-28 ~01:30Z.
- Caveats: the token scan would miss a restructure that touches none of those identifiers; the since-filters use committer dates.
