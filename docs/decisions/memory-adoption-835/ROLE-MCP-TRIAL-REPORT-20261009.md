# ROLE-MCP trial: four arms measured (co-op, 2026-10-09)

Plan: ROLE-MCP-TRIAL-PLAN-20261008/PLAN.md, sha256 dd7f58a176b409e09c2d8841c0746e4fe8e149b0a5335e59699232ee7661352d. Each arm ran one real task in its role on Codex 0.162.0 and the standard tier. The co-op launched each arm under the plan's checks: Windows above 16 GiB, no other launch within 2 minutes, an observer before launch, a fatrace capture for the launch minute, and an observer after the first task.

| Arm | Lane, MCP set | Task | First turn (UTC) | Owned processes | Owned PSS (kB) | First completion input / cached | Responses | Launch-minute fatrace events | Code-graph cache new / changed | after-task.json sha256 (16) |
|---|---|---|---|---|---|---|---|---|---|---|
| A control | harness-rules, full native base (empty EXTRA_C, role-mcp-off skipped) | #908 guard render test | 01:18:36 to 01:32:48 | 23 | 1,431,973 | 21,404 / 9,728 | 35 | 111,410 | 0 / 2 | 2b53bc6a7c73307f |
| B structural-scout | overlap-token, scout set | S1-S3 role-carrier trace | 23:02:23 to 23:09:48 | 12 | 674,966 | 23,162 / 9,728 | 15 | 153,023 | 0 / 0 | e091bb161bca6a5b |
| B supplied-artifact | ns-readiness-manifest, supplied-artifact set | #890 rebase and regenerate | 23:56:28 to 00:13:42 | 16 | 837,623 | 21,438 / 9,728 | 34 | 87,489 | 0 / 1 | 995111bca57200c2 |
| C token-parity parent | codex-token-parity, token-parity-parent set | (ii) folded into #902 | 00:14:39 to 00:37:22 | 14 | 947,334 | 21,896 / 9,728 | 49 | 113,808 | 1 / 1 | c65ca9b983be71cc |

## What the numbers show

- **Processes and memory:** the three role-scoped arms each ran 12 to 16 owned processes after their task; the full-set control ran 23. Owned PSS was 0.67 to 0.95 GB in the role-scoped arms, against 1.43 GB in the control.
- **First request:** the first completion's input sizes are all 21.4 to 23.2 thousand tokens, with 9,728 cached in every arm. The MCP set did not visibly change the first request's size. This is consistent with tool schemas not travelling in the request in code mode, but it is not a proof of that.
- **Launch-minute file activity:** the counts (87 to 153 thousand events) are dominated by other sessions' context-mode and agentsview writes. They cannot be attributed to an arm.
- **Code-graph cache:** no arm wrote a code-graph database file. The new or changed files belong to other lanes or to logs, and are candidates only.

## Limits

- **One run per arm, each on a different real task.** Task length and kind differ, so the PSS and process differences are observations, not measured savings. A savings claim needs paired runs of the same task in each arm.
- **Snapshot timing:** PSS was taken at the after-task moment. It includes whatever sub-agents or tool processes were alive then.
- **First-completion figure:** it is the native diagnostic snapshot, not a provider-bound first request (scope `UNKNOWN_without_independent_first_response_binding`).
- **Run evidence:** every number above comes from `runs/<arm>/after-task.json`, `runs/<arm>/before-launch.json` and `runs/<arm>/launch-fatrace-summary.json` in this directory.
