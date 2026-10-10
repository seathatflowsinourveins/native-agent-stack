# Opt-in OmniRoute transport for the blind Codex lane

Add the requested insurance transport as `codex_lane.py --provider omniroute`; native remains the default.
The candidate is ready for code review, but the CC's requirement that the gateway applies no prompt rewriting,
compression, memory or system-prompt injection is not proved. Do not use it as a qualified blind-wave failover
until that independent requirement is resolved. A source review cannot substitute a guarantee the source lacks.

The implementation follows the existing landscape-sweep [automatic failover](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4d345267866403d75edece400fde6cd35ec4d05c/tools/sota-convergence/landscape-sweep/README.md#L351-L388)
and its [transport-only inline provider](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4d345267866403d75edece400fde6cd35ec4d05c/tools/sota-convergence/landscape-sweep/codex_job.py#L695-L703)
at main `4d345267866403d75edece400fde6cd35ec4d05c`. It keeps every `ISOLATION_ARGS` setting, the read-only
sandbox, ephemeral execution, fresh private `CODEX_HOME`, empty `HOME`/`TMPDIR`, disabled hooks and strict
child environment. OmniRoute never accesses or links native auth; no API-key placeholder is introduced.
Only `OMNIROUTE_BASE_URL` joins the existing child environment. The endpoint must be a keyless loopback
HTTP(S) `/v1` URL; port, userinfo, query, fragment and type checks run before a child or home is created.

The default endpoint is `http://127.0.0.1:21128/v1`. The model defaults to `gpt-6.1-sol` on the `cx/` route;
an explicit model is retained, with `cx/` treated only as routing syntax. Model identity, provider and
canonical endpoint are stamped by the runner, and provider/endpoint changes invalidate resume. The shared
sealer permits only the two new Codex transport fields, keeps every required digest and accepts legacy native
receipts. Code registration remains append-only. The memory opt-out and compression-off request are native
provider headers, not new environment variables.

The recorded gateway composition is base OmniRoute `c1e30b7676975feb298b49eff6ff58923c04b89e` (3.8.51),
PR15167 `0585aba5589d5a1f49243a13a8db249558e7c9e3`, affinity `045aa81f3`, build `5f4b3d577` and
tree `f1336dfd6c8ebd81586dd6c71e7ef668ef8c949f`, as recorded in
[the composition record](https://github.com/seathatflowsinourveins/native-agent-stack/blob/4d345267866403d75edece400fde6cd35ec4d05c/docs/decisions/2026-10-05-omniroute-gateway-composition.md#L39-L48).
This public record does not establish the actual post-October-9 deployed identity or hidden configuration.
The pinned [Codex registry](https://github.com/diegosouzapw/OmniRoute/blob/0585aba5589d5a1f49243a13a8db249558e7c9e3/open-sse/config/providers/registry/codex/index.ts#L9-L17)
selects the `cx` Codex Responses executor and registers Sol/effort aliases at lines 71-74.

Pinned primary sources establish these limits:

| Mechanism | Evidence at the recorded pin |
| --- | --- |
| Native passthrough | [passthroughHelpers.ts:47-89](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/handlers/chatCore/passthroughHelpers.ts#L47-L89) preserves format; it does not disable later mutation stages. |
| Default instructions and role normalization | [codex.ts:1325-1362](https://github.com/diegosouzapw/OmniRoute/blob/0585aba5589d5a1f49243a13a8db249558e7c9e3/open-sse/executors/codex.ts#L1325-L1362) fills blank instructions and normalizes system input roles. |
| Global prompt injection | [chatCore.ts:3156](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/handlers/chatCore.ts#L3156) calls [systemPrompt.ts:275-283](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/services/systemPrompt.ts#L275-L283), which can wrap existing nonblank instructions. |
| Memory/skills opt-out | [headers.ts:19-32](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/handlers/chatCore/headers.ts#L19-L32) and [chatCore.ts:1364-1369](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/handlers/chatCore.ts#L1364-L1369) honour `x-omniroute-no-memory:true`. |
| Compression | [strategySelector.ts:232-249](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/services/compression/strategySelector.ts#L232-L249) invokes adaptive planning after the off base plan; [resolveAdaptivePlan.ts:48-68](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/services/compression/adaptiveCompression/resolveAdaptivePlan.ts#L48-L68) can escalate from off. The header is not a hard kill. |
| Other rewrites | [chat.ts:915-918](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/src/sse/handlers/chat.ts#L915-L918), [chatCore.ts:655-682](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/handlers/chatCore.ts#L655-L682) and [upstreamBody.ts:323-328](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/handlers/chatCore/upstreamBody.ts#L323-L328) allow middleware, plugins and payload rules to mutate a request. |

The installed Codex 0.162.1 client canary used a synthetic loopback HTTP receiver returning a terminal HTTP400,
so no upstream model turn occurred. It captured one request containing the exact 81 UTF-8 prompt bytes,
`cx/gpt-6.1-sol`, requested max effort and both policy headers; the home had no auth link. The captured
`instructions` field was absent/blank, so the executor's fallback condition is a material boundary rather
than an assumed exemption. A separate fixture canary checks the CLI argument bytes. These are client-boundary
measurements, not proof of provider-received bytes or the live gateway's configuration.

Provider-body comparison cannot be obtained under the authorized read boundary. Gateway settings and call-log
detail return private credential/account/body data and are forbidden; permitted list metadata is not a body
attestation. No forbidden route was requested. A supported upstream route/configuration guarantee or an
explicit CC revision of the preservation criterion is needed before operational use.

The no-model native quota helper reported `ordinaryUsageAllowed=false`, primary reset `2026-10-14T03:28Z`,
at 07:53:36Z and 08:22:46Z on October 10. It calls `account/rateLimits/read` through the standard native
client and does not manually read/copy credentials or native config. Native recovery requires an explicit
allowed result; a timestamp or successful probe alone is insufficient.

Fail-before tests cover the missing opt-in and provider receipts; follow-up regressions cover endpoint
canonicalization, malformed JSON endpoint types and routed model identity. All 110 Codex-lane and provenance
registry tests pass, including the unchanged isolation tuple and README command guard. The synthetic tier-1
dry-run writes no output or home. Evidence classes and measured boundaries are in the
[dated receipt](../../tools/sota-convergence/evidence/codex-lane-omniroute-20261010.json).
