# Native Claude telemetry and notification formatting

The September 21 check exercised a real native Claude task, its memory capture,
the existing OpenTelemetry exporter, Prometheus, and the rendered Grafana panel.
It also corrected the local ntfy Alertmanager template through ntfy's supported
template directory. [The receipt](../observability/backends/telemetry-resolution-20260921.json)
separates returned results, upstream checks, local replay, and deployment.

## Claude: current activity, not retrospective telemetry

Native Claude Code 2.1.278 was already signed in through its normal first-party
subscription. Its existing user settings enabled OTLP over HTTP/protobuf to the
loopback Collector, with cumulative metrics and content logging disabled. No
persistent account, provider, model, permission, or client settings changed.

The fresh task used the configured `claude-fable-5-1` model to run the actual
`ai-memory status --json` command once. It completed in two model turns. Native
hooks captured the tool result and a completed session in the explicit
`agent-lab` workspace/project. MCP discovery was limited for this one task;
ordinary lifecycle hooks remained enabled.

```sh
claude auth status
claude -p --output-format stream-json --verbose --max-turns 3 \
  --tools Bash --allowedTools 'Bash(ai-memory status --json)' \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' -- \
  'Run ai-memory status --json once and summarize its actual embedding and LLM status. Do not edit files, change settings, write memory or invoke other workers.'
promtool query instant http://127.0.0.1:19090 \
  'sum by (type) (ecosystem_claude_code_token_usage_tokens_total)'
```

Use the final `--` before the prompt: `--mcp-config` accepts multiple values.
The initial omitted separator failed before inference and remains in the private
receipt. The corrected invocation reported these totals, which matched the
subsequent native Prometheus response exactly:

| Native category | Returned tokens |
| --- | ---: |
| Input | 34 |
| Cache creation | 16,402 |
| Cache read | 14,959 |
| Output | 787 |

These are this invocation's provider usage categories, not lifetime savings.
The Grafana Claude panel showed all four series in the selected 30-minute range.
The earlier empty panel was a dated absence of samples; this run does not export
older conversations retroactively. The pre-run query already contained another
Claude process's counters. Do not subtract those process snapshots to estimate
this task: the explicit native result is the task's usage evidence.

Upstream reference: [Claude Code monitoring](https://code.claude.com/docs/en/monitoring-usage).

## ntfy: use its supported template override

The installed ntfy 2.28.0 bundled Alertmanager template printed an absent
`instance` as `<no value>` and joined the start/end timestamps. The local override
retains the upstream title and webhook fields, omits missing optional fields,
puts timestamps on separate lines, and shows an end time only for a resolved
alert with a nonzero end timestamp.

The portable renderer now writes
`ecosystem-ntfy-templates/alertmanager.yml` and sets `template-dir` in the ntfy
configuration. Alertmanager's existing `?template=alertmanager` receiver remains
unchanged. On an already configured host, merge only this setting and template;
do not regenerate unrelated active backend configurations.

For the first `template-dir` change, restart only the existing ntfy service.
ntfy's SIGHUP handler reloads logging settings, not this directory. Subsequent
template-file edits are read on each webhook and require no service restart.
The native restart passed, health returned `healthy: true`, and all 24 retained
notifications survived byte-for-byte.

Verification used ntfy source tag `v2.28.0`, commit
`10cb6506f836dbb00bb77e3b52669f6ace37f555`:

```sh
make cli-deps-static-sites
go test ./server \
  -run '^TestServer_MessageTemplate_(TemplateFileNewlines|FromNamedTemplate_GitHubIssueOpened_OverrideConfigTemplate)$' \
  -count=1
amtool check-config "$ALERTMANAGER_CONFIG"
systemctl --user restart ecosystem-ntfy.service
ntfy subscribe --poll --since all http://127.0.0.1:18080/ecosystem-alerts
```

The two unchanged upstream tests passed. A separately labelled local integration
check invoked ntfy's real renderer directly with its unchanged Alertmanager and
Grafana fixtures plus a replay derived from the previously observed real local
alert. All three renderings passed. It made no HTTP publication and created no
alert. The initial source test failed because generated static assets were
missing; the upstream make target above supplied them before the passing run.

The real gateway alert resolved before template deployment. Its retained
notification still displays the original text; historical messages were not
rewritten. No post-deployment production webhook was observed in this bounded
check, so template replay and deployment are established, while the next real
notification's formatting remains to be observed. Browser desktop notification
permission is separate from successful topic-feed delivery.

Sources: [ntfy custom templates](https://docs.ntfy.sh/publish/#custom-templates),
[upstream template](https://github.com/binwiederhier/ntfy/blob/v2.28.0/server/templates/alertmanager.yml),
[native file renderer](https://github.com/binwiederhier/ntfy/blob/v2.28.0/server/server_template.go),
[SIGHUP behavior](https://github.com/binwiederhier/ntfy/blob/v2.28.0/cmd/serve_unix.go).
