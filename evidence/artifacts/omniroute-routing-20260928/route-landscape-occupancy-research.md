# route-landscape: SOTA reference for the affinity-over-occupancy fix (2026-09-28 ~01:28Z). Relayed by team-lead from the teammate's message; route-landscape cannot write files.

This is source review at pinned refs only; nothing here was measured by route-landscape. dd6e9607e does not resolve upstream (gh api commits/dd6e9607e returned 422). The same code was verified at release/v3.8.51 head a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3.

## (a) Upstream OmniRoute
- At a58000c7:
  - auth.ts:1984-1987 sets `connection` from selectSessionAffinityConnection, and the strategy branches are skipped (:1996).
  - :2159-2177 then runs unconditionally for OAuth. It replaces `connection` with any OAuth peer whose priority is <= selected+1 and whose getOAuthSessionAvailability (1/(1+foreign sessions), oauthSessionOccupancy.ts:35-41) is higher.
  - New pins are placed by LRU (sessionAffinityPin.ts:309-321). The pin is NOT moved to the served account.
  - chat.ts:1711 hardcodes reserveOAuthSession:true; the same flag drives the reservation at auth.ts:1078-1079.
- #8939 (issue, closed) asked for occupancy as "a soft negative ranking factor, not a hard exclusion" and to "Preserve stronger signals such as ... explicit account pins".
- #8940 (PR, merged 2026-08-11, d774cceca): "Preserve quota, health, explicit pins, configured priorities, and existing same-session affinity as stronger routing constraints."
  - The defect is present in #8940's own merge: affinity at auth.ts:1532, override at :1703.
  - No test asserts that a provider-path pinned session survives a foreign occupant.
- Precedent: #5903 (issue) and #5943 (PR, merged 2026-07-02, 8d2df914), "session affinity wins over reset-aware re-scoring for codex". Implemented in sessionAffinityPin.ts:512-539 applySessionAffinityPin, with break conditions in isConnectionEligibleForAffinityPin :486-508:
  - excluded, model excluded, rate-limited, terminal status, codex scope unavailable, model lock, quota exhausted, quota-policy blocked.
- #13102 (PR, OPEN, not draft, base release/v3.8.51, head baaaaf318c61aec0dfdfa979df41ec0767a2944b, updated 2026-09-25), "feat(auth): add per-API-key ordered connection preference". Labels deferred-v3.8.52 and protected-surface.
  - auth.ts:1954-1959 sets `let selectedByApiKeyPreference = false; ... = true`.
  - :2154-2157 makes the guard `options.reserveOAuthSession === true && connection?.authType === "oauth" && !selectedByApiKeyPreference`.
- Other post-#8940 items that touch the area but do not change the override:
  - #10362 (merged, exclusive managed session leases: "Session affinity provides soft locality and continuity, but not exclusive lifetime ownership");
  - #11775 (merged, live lease occupancy gate);
  - #13840 (closed unmerged, session-aware admission slots);
  - #13676 (open, admission queue wait);
  - #14907 (open, thread-scoped prompt_cache_key).
- Coverage:
  - commits since 2026-08-11 on release/v3.8.51: auth.ts 61, oauthSessionOccupancy.ts 1 (#8940), sessionAffinityPin.ts 6; none changes the override;
  - all 354 open PRs patch-scanned: only #13102 matched;
  - branch-name scan: no relevant hits.

## (b) Reference gateways at pinned clones
- CLIProxyAPI v8.0.2 (4a2c8186):
  - Keep: selector.go:1059-1064 returns the bound auth on a cache hit if it is in `available`; Pick has no later load/occupancy step.
  - Break: only when the bound auth is not in `available` (:1066-1077), which reselects and rebinds the chosen auth. `available` spans all priority tiers (:1041-1047) and excludes disabled, 401-failed, expired-token, quota-exceeded and model cooldown/quota/unavailable auths (isAuthBlockedForModel :823-870).
  - Concurrency busy is not retried onto another credential: conductor_selection.go:1341-1344 returns no-retry for HomeConcurrencyBusyError.
- sub2api v0.2.8 (fd80b08c90b55edcad5b00171b53f08721d30da1), a Codex/ChatGPT OAuth pool and the closest analog:
  - Layer order in openai_account_scheduler.go:382-473: previous_response_id, then guardian parent, then session_hash sticky (:455-468, returns on hit), then load_balance (:472) only on a sticky miss.
  - Break (selectBySessionHash :495-611): excluded/unschedulable/missing, shouldClearStickySession, platform/model/transport mismatch, quota-blocked, team/model 429 window.
  - Escape that preserves the binding (:468 PreserveStickyBinding): TTFT > 15000 ms or error rate > 0.5 (:642-654, defaults :2597-2604), or the configured concurrency cap is full (:594-596). Otherwise it waits on the same account (:604 WaitPlan).
  - The cold path binds the account actually acquired (:1328-1330).
  - The Claude path has the same shape: gateway_scheduling.go:523-625, with a bounded wait plan (config.go:1465-1466).
- LiteLLM v1.102.1 (d09bbae1):
  - router.py: cooldown filter (:12767), blocked filter, then callback filters (:12782). DeploymentAffinityCheck narrows candidates to [pinned] (deployment_affinity_check.py:473-500). Only then does the strategy choose among survivors (:13041, :13064-13069).
  - Break: the pinned deployment is not in the healthy list (cooldown_handlers.py:318-395).
  - The pin is written for the deployment actually chosen (deployment_affinity_check.py:544).
- llm-d-router v0.11.0 (a5cbe600):
  - Keep: session_affinity.go:148-152 returns the session's endpoint if it is a candidate. The filter runs before the load scorers.
  - Break: the endpoint is not a candidate. Bounded-load variant: prefixcacheaffinity/plugin.go:75-78 (MaxTTFTPenaltyMs 18000).
- Across all four, a live binding is kept whenever the bound account is still eligible. None moves a bound session because a peer is less occupied. Breaks come from ineligibility or an absolute bound; relative occupancy decides only cold bindings.

## (c) Conclusion: a cited minimal local change exists
1. Primary copy source: #13102 head baaaaf31, auth.ts:1954-1959 (the flag) and :2154-2157 (`&& !selectedBy...` in the occupancy guard).
   - The analog is `selectedBySessionAffinity`, set at a58000c7 auth.ts:1984-1987 when an existing eligible pin was REUSED (tell reuse from a fresh pin with getSessionAccountAffinity, sessionAffinityPin.ts:280-281), plus `&& !selectedBySessionAffinity` at :2159.
   - Break conditions stay isConnectionEligibleForAffinityPin (#5943 precedent).
2. Intent: #8939 and #8940.
3. External ordering: sub2api openai_account_scheduler.go:455-473; CLIProxyAPI selector.go:1059-1064; LiteLLM router.py:12782 then :13064-13069.
- Nuance: the guard alone leaves one miss for fresh pins. If occupancy moves the first turn, the LRU pin still points at the original account, so turn 2 misses. The references bind the account actually chosen (CPA selector.go:1066-1077 bind(auth.ID); sub2api :1328-1330; LiteLLM deployment_affinity_check.py:544). The full fix is (i) skip the override for a reused pin, plus (ii) for a fresh pin, write the pin to the final connection.
- Caveats: #13102 is open and deferred (it is a pattern source, not merged behaviour). A local patch must be re-applied or dropped on upgrade.
- Verify with the served!=pin rate (target ~0 outside ineligible accounts), the cache-read share on formerly overridden conversations, and the per-account in-flight spread.
- Clones: $SCRATCH/src/sub2api (v0.2.8). OmniRoute reference files in $SCRATCH/omni-ref/.

## User decision (2026-09-28 ~01:35Z)
"Full patch after R02 (Recommended)": (i) plus (ii), upstream suite, rebuild, restart 20128 only after the R02 scored run, then live verification.
