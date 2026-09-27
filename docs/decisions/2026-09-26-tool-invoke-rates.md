# Decision: tool, MCP server, skill and subagent invoke rates from Collector-extracted names in Loki (2026-09-26)

**Status: decided; the user decided on 2026-09-26 to turn `OTEL_LOG_TOOL_DETAILS` on with this
filtering ("1 and full sota convergence practice we proceed"). Applied on the host and passed host
acceptance with the pre-fix checker** (`prove.sh`, 2026-09-26T23:47:42Z-23:49:21Z,
33 passed, 0 failed; see "Evidence and its class" for the corrected offline result and remaining limits).
[docs/secret-storage.md](../secret-storage.md#telemetry-and-pasted-values) recommends, as a user
decision, keeping tool details off while broker keys exist on the host, and records this change as its
one dated exception. The Collector part works without the flag. This change is stacked
on [telemetry writer identity](2026-09-26-telemetry-writer-identity.md), which left workflow and agent
attribution on the Loki allowlist as a separate gap of its own.

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

- **Historical local integration** (scratch replay; sanitized receipt committed at
  `evidence/artifacts/tool-invoke-rates-20260926/scratch-replay/`): replay of the probe captures (Claude runs
  A, B and C, and Codex exec) plus synthetic sentinel records, including forged derived keys, addresses,
  token-shaped names, a forged SDK receipt, model-typed names shaped like file names and hidden paths, and two
  app-server clients.
  - The staged pipeline ran on the pinned otelcol-contrib 0.161.0, and a scratch Loki 3.7.8 ran from
    the repository's Loki template. Every assertion passed (109 of 109).
  - The derived fields matched a separately written reference implementation on every record.
  - The historical checker found none of its 72 retained forbidden strings in the file exporter or Loki;
    its length floors and missing fixed-body assertion limit that result.
  - Each new dashboard target returned the value computed from the exported records.
  - The receipt carries the harness and reference implementation (paths parameterized, not hard-coded) and
    the sanitized derived result; it does not carry the 536 real captured records it also covered, only their
    counts. See that folder's README for exactly what is and is not reproducible without them.
- **Unit tests:** the original `tests/test_observability_tool_names.py` result passed, including the
  pinned-binary class, and failed on the writer-identity profile without this change. The repair's requested
  three-module command (`tests.test_observability_tool_names`, `tests.test_observability_writer_identity`,
  `tests.test_observability_writer_identity_host`) ran **78 tests: 57 passed, 21 errors** in the repair
  sandbox. All 21 errors were socket-creation `PermissionError` failures there. The coordinator re-ran the
  same command on the host: **78 tests, OK**.
- **Independent review:** two read-only Codex (gpt-6-astra) review rounds. The first raised nine
  findings; eight were fixed and the ninth, that shape checks cannot bound meaning, was recorded as a
  limit. The second demonstrated that limit and raised six more findings: the names above, the host
  merge helper, client grouping, launch timing, install and rollback drift, and the Claude flag
  rollback. All were fixed in one repair round; the residuals are recorded below. A third, separate
  read-only review (window 2) found that the host proof's own privacy checker (`prove_check.py`) dropped
  forbidden strings under 8 characters (`prove.sh` generated that list with its own 12-character floor) and
  never asserted a tagged record's body against the Collector's fixed placeholder; both are fixed below.
- **Production Loki, read-only, before any apply:** all 19 repaired dashboard targets and the 15 proof
  queries parse and return. The hour before that run had about 83 Claude and 43 Codex tool calls per
  minute.
- **Historical host acceptance:** `prove.sh` ran live against production Loki/Collector, 2026-09-26T23:47:42Z-23:49:21Z:
  one real `claude -p` and one real `codex exec`, tagged with `ecosystem.task.id`. **33 passed, 0 failed** --
  every per-server, per-skill, per-subagent and per-client count appeared in Loki within the deadline. Its 7
  privacy assertions ran under the checker this fix replaces (next item); the 26 other assertions are
  unaffected by that fix. Receipt: `evidence/artifacts/tool-invoke-rates-20260926/live-proof/`.
- **Checker fix, discriminating control and offline re-check** (window-2 finding 2; review thread
  `PRRT_kwDOUg_LrM6mT7_M` on this file): the privacy checker's two length floors are removed, and it now
  asserts every tagged record's body equals the Collector's fixed placeholder (`set(body, "[content
  omitted]")`) exactly, on both the Loki sink and the Collector's file-exporter sink, matched against parsed
  body/attribute values rather than a raw serialized blob (so a short literal like `pwd` cannot
  false-positive on JSON structure either).
  - A fully synthetic, offline A/B control shows the pre-fix checker passing identically on a clean body and
    on a leaked `"pwd"` body -- it cannot tell them apart -- and the fixed checker passing the clean body
    while correctly failing 4 assertions on the leaked one.
  - Cross-family review of `a0348904` found that the first body fix checked only the last body in a batch,
    accepted absent/non-string bodies, ignored resource/scope and nested values, and matched banned keys
    only in minified JSON. The extended `failing_first_ab.py` controls returned **2 passed, 10 failed**
    before this repair (both clean controls stayed green), then **12 passed, 0 failed**. The retained
    `.red.out` and regenerated `.out` preserve both runs. The earlier A/B still rejects the leaked body.
  - A GPT-6 re-check of that repair (`7a15a2e2`) found two more defects, both now fixed:
    - A base64 `bytesValue` was scanned only in its encoded form. It is now also scanned decoded, and an
      undecodable value fails closed. Controls: 12 passed, 3 failed before; **15 passed, 0 failed** after.
    - Loki's fixed-body assertion ran only with historical captures. `replay.py loki_body_checks()` now runs
      on every replay. `checker-fix/loki_body_control.py`, a stubbed Loki with `pwd` bodies: 0 passed, 2 failed
      on the prior replay; 2 passed, 0 failed after.
    - Residual: Loki's structured metadata stores attribute values as strings, so a bytes-typed attribute stays
      base64 there.
  - `scan_otlp()` now traverses decoded keys and values at every OTLP level, including arrays and key-value
    lists, and retains every body's validity. Live and offline paths call one `events_privacy_checks()`
    implementation. The schema references are OpenTelemetry `opentelemetry-proto` `v1.9.0`
    [`logs.proto`](https://github.com/open-telemetry/opentelemetry-proto/blob/v1.9.0/opentelemetry/proto/logs/v1/logs.proto)
    and [`common.proto`](https://github.com/open-telemetry/opentelemetry-proto/blob/v1.9.0/opentelemetry/proto/common/v1/common.proto).
  - The corrected checker was re-run against the **same retained events-file export** of the 23:47Z proof:
    **4 files, 29 tagged batches, 270 records, 26 forbidden strings; 3 passed, 0 failed**. All 270 bodies
    are fixed placeholders, with zero missing/non-string bodies, empty batches, forbidden-value hits or
    banned keys. The batches also contain records sharing a batch with the tagged proof records. The old
    `records=29` was a batch count. The 26-string search is the retained 25 strings plus `pwd`, not the
    separate 27-string recomputation. No violation was found. This is offline real-data evidence, not a new
    host run; see `checker-fix/offline_recheck.out` in the receipt.
  - That run, at 2026-09-27T03:55:26Z, cannot be repeated. The Collector's `file/events` exporter keeps
    10 MB x 3 backups and rotated at 04:05:11Z, dropping the backup that held the proof's records. A
    coordinator re-run at 04:14Z found 0 tagged lines (`checker-fix/offline_recheck.rerun-after-rotation.out`).
  - The Loki sink of that same proof was **not** re-checked: the live run never persisted raw record bodies
    to disk, only derived PASS/FAIL text, so nothing is retained to run the new assertion against, and this
    fix does not requery production Loki to manufacture one. Window-2's separate, independent all-stream scan
    (22:45:00Z-00:24:44Z, containing this proof's window) found every `claude-code`/`codex_exec` body exactly
    the fixed placeholder -- a different method and record set, corroborating but not a run of this checker.
  - Net claim: the events-file sink of the 23:47Z proof is now verified by the fixed checker against real
    retained data; the Loki sink of that specific proof remains verified only by the pre-fix checker. The
    next `prove.sh` run exercises the fixed checker on both sinks. Receipt:
    `evidence/artifacts/tool-invoke-rates-20260926/checker-fix/`.
- **Synthetic-only replay repair:** an empty capture previously raised `ValueError` in `max()` and ran
  unconditional historical assertions. `post --synthetic` now accepts no captures with a recent default
  timestamp. Historical counts and live-proof scenario checks require the complete A/B/C/Codex capture set;
  synthetic record and dashboard assertions remain active. The committed `synthetic_replay_control.py`
  exercises 31 synthetic records with stubbed HTTP and output from the existing design reference:
  **25 passed, 20 failed** before / **25 passed, 0 failed** after; 41 fixture strings, zero hits on the
  reference output. This is a harness regression check, not native Collector/Loki acceptance.
  In the repair sandbox, the full scratch run could not create loopback sockets (`socket: operation not
  permitted`); that attempt is retained at `scratch-replay/synthetic-native-attempt.out`. The coordinator
  then ran the same synthetic-only `replay-test.sh` on the host, with the installed pinned Collector 0.161.0
  and Loki 3.7.8 on scratch loopback ports 45700-45703 and scratch storage: **68 passed, 0 failed**, including
  the always-run Loki fixed-body check, with no
  scratch listener left (`scratch-replay/synthetic-native.out`). Production services and systemd units were
  untouched.

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
- `client` groups by normalized originator name, not by process: two separate app-server processes whose
  originator normalizes to the same name share one `client` label. One app-server process also gives new
  threads the originator of the first client that initialized it, so front-ends sharing one process share a
  `client` too. Codex spawn messages carry no originator.
- Codex `functions/exec` and `functions/wait` count as `code_mode`. Multi-agent v1 also names a tool
  `wait`.
- `shell_rtk` looks at the command's first word only.
- MCP server, MCP tool and skill names are bounded by shape, because they come from configuration.
  A server or skill whose configured name carries private text would export it.
