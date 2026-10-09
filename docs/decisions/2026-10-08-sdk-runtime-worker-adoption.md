# SDK and runtime-worker adoption record — 2026-10-08

Status: proposed foundation record; designated reads, landed G5 binding, CI,
pre-cue check, owner decisions and the CC's cue are pending. The decisions
describe the current host contract and the test that would demonstrate adoption.
Deployment follows the owner-gated path through 5f.

The inventory covers application agent SDKs and foundation worker entry points.
The research owner's final list owns research/API surface selection, and the
orchestration record owns hcom, teams, workflows and agent-orchestrator. Domain
SDKs follow their domain records. The base is
`aba02ec3456d383bcc2fc72883db098f9be7918a`.

## Evidence and the measurement correction

[Observations](../../evidence/artifacts/sdk-runtime-adoption-20261008/observations.json)
retains source paths, SHA-256 values, current package/client status, public
registry observations, sealed native scopes and candidate G5 pointers.
[Decisions](../../evidence/artifacts/sdk-runtime-adoption-20261008/decisions.json)
is the machine-readable per-layer record. Raw captures are hash-named under
`${STATE_ROOT}/research/fullspeed-20261008/sdk-harness-ready/adoption-record-20261008/`.
The sealed readiness index remains bound to
`affc6ee209a92cad2a18e1cddea78ffcf19560268f527a1afc2865ad877fdf3d`.

`adoption-now/1`, generated `2026-10-08T23:42:51Z`, SHA-256
`5de97cf238b3d28aa9f7d5110a05857204a847b0c75cda8971de8e142e362e36`,
reports a 24-hour population of 63 Claude sessions and 841 Codex conversations.
These are the counter's client populations, not SDK invocation totals. Its
`adoption_invoke.py` source, SHA-256
`10784aa8862eaed3a5e0520ecdb2eb58cdf0277f4bab62f8868a86b703954408`,
enumerates MCP servers and uses Loki's native `tool_result`/`codex.tool_result`
selectors. It supplies no SDK/runtime-worker per-role count. Those counts are
**unmeasured**, represented as `null`. The existing
[invoke-rate decision](2026-09-26-tool-invoke-rates.md) also separates SDK
receipts from client invoke-rate keys.

Each previous readiness run explicitly requested a named SDK/native probe.
Those receipts establish their stated native scopes; they do not establish
ordinary task selection by a fresh owning role. No layer receives KEEP from
that evidence. WIRE preserves a demonstrated job while recording the missing
vendor routing and the subsequent measurement. RETIRE removes a duplicate
from the proposed active role contract; it is not a claim about every future
application or a comparative performance result.

## Per-layer decisions

| Layer and observed version | Decision | Job and owning role | Evidence, comparison and pending test |
| --- | --- | --- | --- |
| Claude Agent SDK `0.2.163` | WIRE | Programmatic packet worker under the authorized W2/coordinator plan | Sealed live `query()` result; vendor `skills`/`setting_sources` options. Activate the role through native skill discovery; T1. |
| Python Codex SDK worker, locked `0.160.0` | WIRE | Selected foreground foundation worker called by Claude | October 3 read-only caller receipt and existing project skill. Bind that role's native skill and the host's `21128` child route; T2. |
| TypeScript Codex SDK `0.160.0` | RETIRE | Second adapter to the same native Codex harness; no distinct current caller | Sealed `startThread().run()` qualification. The selected Python deployment supplies the current worker job. A real Node application requirement can overturn this; T3. |
| OpenAI Agents SDK, no installation found in bounded inventory | RETIRE | Caller-owned API loop; no demonstrated host application job | G5 candidate `agent-sdks` and official SDK scope. Add only for a demonstrated application handoff/guardrail requirement; T3. |
| OpenHands SDK/worker, `1.50.1` metadata / `1.53.0` source | RETIRE | Additional owned coding runtime | Sealed successful owned job and file oracle, G5 NO-GAP lead; native Claude/Codex supply the present coding job. A matched real requirement can overturn this; T3. |
| Deep Agents SDK `0.7.23`, isolated environment | RETIRE | Additional planning, subagent and file harness | Filesystem fixture is the entire qualified scope. Selected native workers own those jobs; T3. G5's dcode row is a different product. |
| Claude gateway worker trial, locked SDK `0.2.162` | RETIRE | Additional gateway-translated worker experiment | Trial verification leaves activation, routing and recovery unverified. Native Claude and the current SDK package supply the present role; T3. |
| GPT Researcher checkout `v3.7.0`, pyproject `0.16.0` | WIRE | Independent public research gatherer; Codex research role proposed | Sealed CLI report; vendor Codex MCP skill is absent and is only a routing stub. Its supported MCP dependency needs verification before wiring; T4. |
| DeerFlow harness `2.1.0` | WIRE | Independent research gatherer; Claude research role proposed | Sealed embedded-client retrieval/citation evidence. Vendor HTTP skill is absent and needs its separate native service qualification; T5. |

The source-pinned routing layers are:

- Claude SDK
  [`types.py:2297`](https://github.com/anthropics/claude-agent-sdk-python/blob/1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7/src/claude_agent_sdk/types.py#L2297)
  and the [vendor quick start](https://github.com/anthropics/claude-agent-sdk-python/blob/1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7/examples/quick_start.py).
  Current `setting_sources=None` loads all filesystem sources; `skills=None`
  leaves CLI defaults active. The `skills` option configures skill access and
  sources. Missing role activation must not be misdiagnosed as disabled SDK defaults.
- [Codex Python SDK](https://github.com/openai/codex/tree/a956835d020762cb2b570053af06f643a11c0ecc/sdk/python),
  [Claude native skill discovery](https://code.claude.com/docs/en/skills) and the
  [existing coordinator skill](../../.claude/skills/omniroute-runtime-worker/SKILL.md).
  The retained skill's `20128` instruction is stale for this host. The current
  host assignment is `127.0.0.1:21128`; no request to the other distro's `20128`
  is evidence for this worker. Only read-only caller scope is qualified at this pin.
- GPT Researcher's
  [vendor Codex skill](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/skills/gpt-researcher/SKILL.md),
  SHA-256 `d6f8d0c19f5c898f4e80a8865da0b0c0f23950394a71f1aa52388ee1e4340d67`.
  Its 13-line body requests MCP but implements no server. The vendor Claude
  development skill has a different trigger; it does not prove organic research delegation.
- DeerFlow's
  [vendor HTTP skill](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/skills/public/claude-to-deerflow/SKILL.md),
  SHA-256 `b05a6fa8c64ba4137b09a5f61278b6caa0384b2b4e4330ee9676e2485a53269e`.
  It specifies HTTP health, threads and runs. A `DeerFlowClient.chat()` embedded
  receipt does not qualify this HTTP route. Research role/client assignment
  remains subject to the research owner's final list.

Current public registry versions appear separately in observations. They are
source observations, not installed or executed upgrades. OpenHands metadata and
editable source remain distinct, as do GPT Researcher's release and package
numbering. The sampled client binaries are Codex `0.161.0` and Claude `2.1.295`;
the session launcher can have a different pin. G5's `deepagents-code==0.1.83`
at `caaa7e7c12d214afa5cf0a1afed8eb6232aa6f7b` does not bind SDK `0.7.23`
at `9f4bdf7c8b8bfc86877729d80ed286bd71d78706`.

## Fresh-session acceptance tests

All tests are plans. Use an ordinary real task whose prompt contains no SDK,
skill or tool names. Preserve the task, role/client identity, source/config pin,
native skill selection, actual worker invocation, result oracle, usage and
terminal lifecycle. Compare the owning role with the same baseline definition
after wiring. A source read, preflight, prompted probe or successful model hello
is insufficient. Client assignments below follow the recorded job ownership;
no unsupported cross-client routing is inferred.

| Test | Owning client and ordinary task | Evidence that would pass |
| --- | --- | --- |
| T1 | Fresh Claude and Codex coordinator sessions: review a frozen cited packet with a bounded worker | Native description-based role selection invokes the SDK worker; actual `query()` results, citations, task oracle, native usage/cache counters and terminal outcome are bound to each role. W2 execution starts only after its existing store/ledger/frozen-input cues. |
| T2 | Fresh Claude foundation coordinator: delegate a bounded read-only code/evidence analysis | Native project skill selects the existing Python worker at the correct host route, and its native thread/result/usage/close receipt proves completion. Expand to writing only after the separate writing-dispatch acceptance. A Codex owning session uses its native worker role, without inventing a same-family SDK caller. |
| T3 | Fresh Claude and Codex roles: complete ordinary owned coding, review and file-planning tasks | Selected native/Python routes complete each task oracle. Retain route selection and caller records sufficient to show the retired alternatives are outside the active contract. The absent SDK invocation series cannot support a numeric zero claim. A distinct application requirement plus vendor acceptance can overturn retirement. |
| T4 | Fresh Codex researcher: produce a cited primary-source report, with an independent gatherer when the task requires one | After the supported upstream MCP route is verified and the vendor skill is installed through its native discovery path, an ordinary task selects it and emits a genuine report with current retrieval/citation witnesses. Native MCP calls can then be counted by the existing counter definitions. CLI-only evidence does not pass. |
| T5 | Fresh Claude researcher: produce a cited primary-source answer through the proposed independent gatherer | Vendor skill selects its qualified HTTP service; native health/thread/run completion, retrieved primary sources, citation matches and usage are retained. Re-measure its owning-role invocation with the CC-approved worker evidence definition. Embedded-only evidence does not pass. |

## G5 and workflow binding

G5 PR #878 was OPEN at published head
`ae6cc2286643822d3a0218136722c69d0127fcd4` when checked. Landed row binding is
pending. The retained candidate field file, SHA-256
`a948fa5a64c42622f03881d00c61997e5aa372dd15ad03489d13e478453f8fab`,
supplies `/2` workers, `/8` web-research and `/16` agent-sdks. The action file,
SHA-256 `d78bae7f30c83395c475ca5359022ec7e3db7cbb6a8e288ad1674a2d1ff73020`,
supplies DeerFlow row `86c6347b193efc3a8df5` at `/rows/48` and the distinct
dcode row `ad984275af111838f0fc` at `/rows/59`. Rebind each decision to the
landed catalog/release row and asset digest once G5 lands; candidate evidence
does not substitute for that acceptance step.

Reuse `WORKFLOW-BASELINE-20261008.json`, SHA-256
`c6e9f24e207520b1dfa1d83f094b9d7c8996dbd6cd1d9019a0c4f115e7407ad8`,
for uncached input, cache-read share, rebuilds, subagent first requests,
pre-cue/J8 defects, PR ready-to-landed time, Windows available daily minimum and
per-role invocations. Its unavailable metrics remain `null`. This record changes
no runtime, so it supplies no post-change saving or organic-use measurement.
After an approved wire, keep task, role, client, window and definitions matched;
count a cumulative thread usage snapshot once. The two designated families
review the final record head; CI and the canonical pre-cue check precede the
CC's cue and 5f landing. The canonical pre-cue entry point is requested in the
lane questions file rather than replaced with a local substitute.
