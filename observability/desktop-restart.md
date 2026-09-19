# Desktop restart acceptance — September 19, 2026

The resumed Desktop task now uses Context Mode directly and exports its own
metadata to the local observation stack. This closes the earlier discovery and
parent-log gap. The [receipt](restart-receipt.json) preserves results, failures
and scope. No new CLI/SDK/Claude inference fixture was run for this acceptance.

| Native operation | Actual result |
|---|---|
| Current Desktop tool catalog | 11 Context Mode tools exposed |
| Direct `ctx_execute` | Python executed; explicit user-bus health query returned six active services, each exit 0 |
| Direct `ctx_doctor` | Server PASS; FTS5/SQLite PASS; six plugin hooks registered |
| Direct `ctx_stats` snapshot | 15 calls, 5 minutes, 52.4 KB entered context, **0 tokens saved** |
| Loki query for exact current conversation | 155 records, all 155 matched, all bodies `[content omitted]` |
| Correlated Context Mode results | 14 successful results: 12 execution, 1 doctor, 1 stats |
| Prometheus native targets API | Seven targets up; no scrape errors at the independent snapshot |
| Recovered MCPorter bridge | Native start succeeded; 11 tools discovered; execution returned `bridge-recovered` |

The Loki snapshot was captured at 15:41:40 UTC, starting with the observed
post-restart prompt at 15:29:19 UTC. It contains ongoing work and is not the
end-of-task total. The stats and Loki snapshots have different capture times;
their counts need not equal one another. Native logs identify the parent as
Codex App Server 0.155.0-alpha.9.2 using Astra. Service names alone were not used
as identity: the query matched the exact conversation field.

## Root cause and native repair

The upstream [Context Mode plugin manifest](https://github.com/mksglu/context-mode/blob/v1.0.169/.codex-plugin/mcp.json)
launches `node ./start.mjs`. Desktop's process environment could not resolve
Linux `node`, and its native startup log reported `No such file or directory`.
The already installed Node 24.21.0 worked in interactive shells. A no-clobber
symlink in `/usr/local/bin`, already on Desktop's path, made that same binary
available to the plugin. The plugin and its hook definitions were unchanged.
Direct tools subsequently appeared and executed in this same task; a second
app restart was not required. No explicit reload command was issued, so the
exact client refresh trigger is not asserted.

On this host the equivalent repair command was:

```bash
# Resolve NODE_BINARY from the installation manifest first.
# Only create this link when the destination is absent; never use ln -f.
sudo -n ln -s "$NODE_BINARY" /usr/local/bin/node
/usr/local/bin/node --version
# v24.21.0
```

This is a local administrator-managed runtime link, not a portable installer
requirement. It must be updated deliberately if that pinned runtime is removed.
For rollback, remove only the link after verifying its target. Official
[Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp)
keeps plugin transport commands in the plugin itself.

MCPorter separately refused stale ownership metadata after the WSL restart.
Its [upstream ownership guard](https://github.com/openclaw/mcporter/blob/v0.13.13/src/daemon/host.ts)
was behaving as designed. The old PID was absent, its Unix socket refused a
connection, and its start time preceded the current WSL boot. Only after those
checks was the stale metadata moved to a private evidence directory. The
daemon key and configuration were preserved; upstream startup replaced the
inactive socket. This manual metadata recovery is not claimed to be automatic.

```bash
mcporter --config "$MCPORTER_CONFIG" daemon start
# Single-user daemon started.
mcporter --config "$MCPORTER_CONFIG" list context-mode --brief --no-oauth
# 11 tools
mcporter --config "$MCPORTER_CONFIG" call context-mode.ctx_execute \
  --args '{"language":"python","code":"print(\"bridge-recovered\")"}' \
  --output text --no-oauth
# bridge-recovered
```

## Replay the observation queries

These are native API queries. Supply the intended task's private identifier;
do not publish it or infer identity from a service label. Select a fresh time
window for another acceptance. Native Desktop tools were invoked directly by
their MCP names above; a bridge invocation proves the bridge only.

```bash
curl --fail --silent --get http://127.0.0.1:13100/loki/api/v1/query_range \
  --data-urlencode "query={service_name=~\".+\"} | conversation_id = \"$CURRENT_DESKTOP_THREAD\"" \
  --data-urlencode 'start=2026-09-19T15:29:19Z' \
  --data-urlencode 'end=2026-09-19T15:41:40.084709Z' \
  --data-urlencode 'limit=2000' --data-urlencode 'direction=forward'

curl --fail --silent http://127.0.0.1:19090/api/v1/targets
```

Inspect native `event_name` for event classification; `event_kind` can describe
a response subtype. Compare the Loki line with the Collector's exact literal
`[content omitted]`. An initial local parser used the wrong field and literal;
its incorrect summary was retained privately and superseded before publication.

## Limits retained

- Parent log correlation is accepted. Parent metrics lack a unique process
  instance/client-scope identity, so unscoped histogram series cannot establish
  its exact final total. Request completion fields are not a completed-turn bill.
- The Context Mode counter is an upstream estimate for its connection. Its
  observed value is zero. The earlier **188,769 → 500** selected-artifact
  comparison is separate; neither proves net provider savings for this task.
- Doctor reports four available language runtimes and a Bun performance warning.
  Execution/search work; optional language/performance warnings are preserved.
  Registered hooks are not proof that every lifecycle hook was exercised.
- Six services and seven scrape targets are local health evidence. Off-host
  backup/paging, receipt expiry/recovery, continuous hosting and trading execution
  retain the boundaries in the [gap register](../blueprints/us-equities/gap-resolution.md).
- The independent reviewer confirmed initial parent correlation and service
  health, then hit quota. A second source reviewer failed authentication. Neither
  was retried; full independent review of the final publication is not claimed.
