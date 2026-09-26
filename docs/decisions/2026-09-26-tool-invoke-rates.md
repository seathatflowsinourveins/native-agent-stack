# Decision: tool, MCP server, skill and subagent invoke rates from Collector-extracted names in Loki (2026-09-26)

**Status: proposed; the user decided on 2026-09-26 to turn `OTEL_LOG_TOOL_DETAILS` on with this
filtering ("1 and full sota convergence practice we proceed").**
[docs/secret-storage.md](../secret-storage.md#telemetry-and-pasted-values) recommends, as a user
decision, keeping tool details off while broker keys exist on the host, and records this change as its
one dated exception. The Collector part works without the flag. This change is stacked
on [telemetry writer identity](2026-09-26-telemetry-writer-identity.md), which left workflow and agent
attribution on the Loki allowlist as a separate gap. It has not been applied on the host.

**Scope:** `observability/collector/collector.yaml` (new `transform/tool_names`, log allowlist, logs
pipeline), `OTEL_LOG_TOOL_DETAILS` in both Claude settings examples, a new row in
`observability/backends/templates/ecosystem-dashboard.json.example`, the Collector and backends
READMEs, the template sentence in `docs/secret-storage.md`, and
`tests/test_observability_tool_names.py`.

## Context

- Claude Code 2.1.283, from three headless probe runs on this host on 2026-09-26 and the
  [monitoring docs](https://code.claude.com/docs/en/monitoring-usage):
  - For user-configured MCP servers, `tool_decision` and `tool_result` report `tool_name` as the
    literal `mcp_tool`.
  - The MCP server and tool names, the Skill tool's skill and the Agent tool's `subagent_type` appear
    only in `tool_parameters`. That JSON string is exported only with `OTEL_LOG_TOOL_DETAILS=1`, and it
    also carries `full_command`. With the flag on, `tool_input` carries subagent prompts and workflow
    scripts.
  - `skill_activated` is logged only for a skill that was invoked, and names user skills
    `custom_skill` unless the flag is on.
  - `api_request` carries `query_source`, `agent.name` and the `mcp_server.name` whose result that
    request consumed. User-configured servers appear as `custom` unless the flag is on. User-defined
    agent names on `api_request` and `subagent_completed` are `custom` unless the flag is on.
  - Workflow children carry `workflow.run_id` on their events. Agent-tool subagents carry no marker on
    tool events: `agent_id` is a trace-span attribute, and traces stay off.
  - `tool_result` is logged when a tool completes. For the Agent tool that is when its subagent
    finishes: in each probe run the accepted `tool_decision` came first, the subagent's own events
    followed, and the `tool_result` came 7.1 to 7.6 seconds later.
- Codex 0.157.1, from one probe run and the source at `rust-v0.157.1`:
  - `codex.tool_result` logs `agent_name` (`/root` or `/root/<task>`, where the model chooses the task
    name), `mcp_server`, `originator`, `arguments` and `output`.
  - `codex.agent_communication` logs spawn edges between thread ids. It carries no originator.
  - The app-server always exports `service.name` `codex-app-server`; a thread's `originator` is the
    name of the client that initialized the process, or of the client that created a resumed thread.
  - Production Loki kept none of these fields, because the log allowlist dropped them.
- otelcol-contrib 0.161.0 OTTL provides `ParseJSON`, `IsMatch`, `IsMap`, `ContainsValue`,
  `replace_pattern`, `ToLowerCase` and `delete_matching_keys`, and a statement group can have its own
  `conditions` and cache. Under `error_mode: silent`, a failing statement is skipped and not logged.
  `otelcol-contrib validate` parses every statement.
- Loki 3.7.8 stores OTLP log attributes as structured metadata by default. Labels should be
  low-cardinality, and ids such as trace or order ids must never become labels.

## Decision

1. Both logs pipelines run `transform/tool_names` before `transform/privacy`.
   - Names are sorted by who writes them. Names that Claude Code or Codex write from their own
     configuration (MCP server and tool names, a skill on `skill_activated`, `originator`, the derived
     `client`) must be a short identifier with no run of 24 or more letters and digits, or they become
     `other`.
   - Agent types (`subagent_type`, `agent.name`, `agent_type`) keep only the built-in agents of the
     [subagent docs](https://code.claude.com/docs/en/sub-agents) and the workflow child; any other value
     becomes `custom`, as Claude Code itself reports user-defined agents without the flag.
   - Values the model types are not exported: the Skill tool's `skill_name`, `workflow.name` and Codex
     agent paths. The agent path only decides `actor`.
   - For Claude, it parses `tool_parameters` and copies only `mcp_server_name`, `mcp_tool_name` and
     `subagent_type`. From `bash_command` it derives one boolean, `shell_rtk`.
   - For Codex, it copies `mcp_server` and the MCP tool name, and derives `shell_rtk` from
     `exec_command`'s `cmd`. First-party `Codex <App>` originators become `codex_<app>`.
   - It adds a bounded `tool_family` and `actor`, and `client`: the originator for `codex-app-server`,
     else `service.name`.
   - It deletes `tool_parameters`, `tool_input`, `arguments`, `output`, `content` and `error`.
   - Enumerations and ids outside their pattern are deleted.
   - Incoming derived keys are deleted first. SDK receipts lose every invoke-rate key.
2. The log allowlist gains 19 keys: the extracted and derived names, and ids kept only as structured
   metadata. The metric allowlist is unchanged.
3. Both Claude settings examples set `OTEL_LOG_TOOL_DETAILS` to `"1"`. The other content flags stay
   `false`, and traces stay off. Codex needs no key change: keep `log_user_prompt = false`,
   `[otel.tool_result] max_bytes = 0` and `trace_exporter = "none"`.
4. The dashboard gains a Loki row with ten panels:
   - calls per minute by family, for each client;
   - MCP calls by client and server;
   - skill activations by name;
   - subagent and workflow launches, counted at the accepted `tool_decision` for Claude and at the
     spawn message for Codex;
   - calls by client and actor;
   - MCP share;
   - ctx and rtk adoption;
   - an integrity panel whose values should be 0;
   - MCP-consuming API requests per actor.

   Every query uses `keep` and `[$__auto]`. None groups by an id.

## Alternatives considered

| Alternative | Why not now |
|---|---|
| Keep `OTEL_LOG_TOOL_DETAILS` off | Claude MCP servers stay `custom` and skills stay `custom_skill`, with no `subagent_type` and no Claude rtk ratio. Everything else in this change still works. This is the fallback if the user declines. |
| Keep `tool_parameters` in Loki and parse it at query time | Stores whole Bash commands and prompts in Loki. |
| Loki labels for `tool_family` or MCP server | More streams for no query gain at about 50 calls per minute. |
| Traces (`agent_id`) for per-call subagent attribution | Needs a trace exporter and a tracing store, and the profile keeps traces off. Revisit if calls from the main thread and from Agent subagents must be split per call. |
| A PreToolUse hook that emits only names | A custom emitter on every tool call. The skills trial rejected the same hook for the same reason ([skills decision](2026-09-25-skills-trial-and-usage.md)). |
| Names as Prometheus labels | Adds series per server, skill and agent, and reopens the writer-identity collisions. |
| `/skill-doctor` | Remains the tool for per-skill trial counts. It has no rates per client or actor, and no MCP servers. |
| A shape check alone for every name | Rejected in the second review round: a file name typed into the Skill tool, an agent type and a Codex agent path with a dotted segment passed it. Model-typed values are now dropped or mapped to a closed list. |
| An explicit list for every name, MCP servers and skills included | MCP server, MCP tool and skill names come from the host's configuration, not from the model; a list would show every new server or skill as `other`. Adopted only for agent types. |
| A normalized originator for every text | Turning every space into `_` would make any text identifier-shaped; only the documented `Codex <App>` form is normalized. |

## Evidence and its class

- **Local integration** (scratch replay; the sanitized receipt is to be committed with the host proof):
  replay of the probe captures (Claude runs A, B and C, and Codex exec) plus synthetic sentinel records,
  including forged derived keys, addresses, token-shaped names, a forged SDK receipt, model-typed names
  shaped like file names and hidden paths, and two app-server clients.
  - The staged pipeline ran on the pinned otelcol-contrib 0.161.0, and a scratch Loki 3.7.8 ran from
    the repository's Loki template. Every assertion passed (109 of 109).
  - The derived fields matched a separately written reference implementation on every record.
  - No command, prompt, script, argument, output or sentinel text reached the file exporter or Loki.
  - Each new dashboard target returned the value computed from the exported records.
- **Unit test:** `tests/test_observability_tool_names.py` passes, including the pinned-binary class.
  It fails on the writer-identity profile without this change.
- **Independent review:** two read-only Codex (gpt-6-astra) review rounds. The first raised nine
  findings; eight were fixed and the ninth, that shape checks cannot bound meaning, was recorded as a
  limit. The second demonstrated that limit and raised six more findings: the names above, the host
  merge helper, client grouping, launch timing, install and rollback drift, and the Claude flag
  rollback. All were fixed in one repair round; the residuals are recorded below.
- **Production Loki, read-only, before any apply:** all 19 repaired dashboard targets and the 15 proof
  queries parse and return. The hour before that run had about 83 Claude and 43 Codex tool calls per
  minute.
- **Host acceptance after application:** not yet run. `prove.sh` must pass: one `claude -p` and one
  `codex exec` tagged with `ecosystem.task.id`, with the counts per server, skill, subagent and client
  in Loki within 120 seconds and no command text stored.

## Overturn when

- Claude Code exports MCP, skill or subagent names on tool events without the flag: turn the flag off.
- Claude Code marks Agent-subagent tool events: replace `main_or_subagent`.
- The integrity panel shows `tool_details="unparsed"` or names replaced by `other` on real traffic.
  Fix the pattern or the parse.
- Custom agents matter to the dashboards: add their names to the agent list in `transform/tool_names`.
- Codex logs a per-connection client name on its events: group by it instead of the originator.
- The row's queries become slow at the host's volume: consider `tool_family` as a label.
- The user keeps tool details off: set the flag back to `"false"` and keep the Collector change.

## Limits

- Claude sessions started before the flag change carry no names.
- Agent-subagent tool calls are counted as `main_or_subagent`. The panels add `total_tool_uses` at
  completion and the MCP attribution of `api_request`. The latter counts requests, so several MCP
  results consumed by one request count once.
- Custom agents count as `custom` until their names join the list.
- One app-server process gives new threads the originator of the first client that initialized it, so
  front-ends sharing one process still share a `client`. Codex spawn messages carry no originator.
- Codex `functions/exec` and `functions/wait` count as `code_mode`. Multi-agent v1 also names a tool
  `wait`.
- `shell_rtk` looks at the command's first word only.
- MCP server, MCP tool and skill names are bounded by shape, because they come from configuration.
  A server or skill whose configured name carries private text would export it.
