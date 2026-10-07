# Research-skill round-2 input pack (2026-10-05)

Status: evidence input for the command center's omitted round-2 decision;
the research-skill disposition remains INTERIM. This record activates no skill,
MCP server or HTTP service. It serves the north-star action of returning useful,
verified research from both native clients through a maintained research owner.

The readiness roadmap assigns this lane the pack and isolated executable probe.
The two blind decisions, consequential critic, cross-family verification and any
activation remain with their assigned owners. The existing
[round-2 quality method](2026-10-04-repository-quality-rule.md#decision) and
[activation gate](2026-10-02-new-wsl-layer-consensus.md#decision) govern that work.

## Maintenance and executable facts

Primary GitHub API reads on October 5 returned default-branch HEAD
`63884773685b1f12c7f0d9e283b3d71a5b9b5fda`, committed
`2025-11-07T07:46:52Z`, and exactly one published release, v0.0.1,
`2025-03-30T17:55:52Z`. The repository is not archived. These dates are 332 and
554 days old at the decision date and fail the recorded round's commit/release
currency gates; a later repository updated_at is not a new source commit.
Sources: [commit API](https://api.github.com/repos/assafelovic/gptr-mcp/commits?per_page=1),
[releases API](https://api.github.com/repos/assafelovic/gptr-mcp/releases?per_page=100),
and [release](https://github.com/assafelovic/gptr-mcp/releases/tag/v0.0.1).

At GPT Researcher v3.7.0, pin
`0957c301ed06c2a5857b834358c7227c739041d4`, the startup specification is the
repository-root [.mcp.json:4-6](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/.mcp.json#L4).
The [plugin manifest:15](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/.codex-plugin/plugin.json#L15)
references that file. Correction: `.codex-plugin/.mcp.json` does not exist at
this pin. The command is unversioned `uvx gpt-researcher`.
[pyproject.toml:23-30](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/pyproject.toml#L23)
declares package 0.16.0 and Python >=3.12; its parsed tables contain no console
entry point. This source observation alone does not prove the published command.

The isolated native probe resolves that uncertainty:

| Input | Returned result | Scope |
| --- | --- | --- |
| Unversioned uvx command with current PyPI resolution | 0.16.1 installed; exit 1, `Package gpt-researcher does not provide any executables` | Current published command cannot start; no MCP handshake occurred |
| Explicit source-declared distribution 0.16.0 | 0.16.0 installed; exit 1 with the same executable-discovery failure | Published version matching the source's version declaration, without asserting wheel/tag byte equivalence |
| Same isolated 0.16.1 environment, Python control | Exit 0, `Python 3.12.3` | Installer/environment works; this does not qualify MCP or research |

The probes used uv 0.12.22, CPython 3.12.3, an empty inherited environment,
isolated XDG/cache/tool directories outside /tmp, no user uv configuration,
and no GPT Researcher source build. `--help` is passed only after executable
discovery, so it does not explain either discovery failure. The supported
installer built dependencies lacking wheels; no runtime fork, rebuilt GPT
Researcher source or replacement executable was created. Native semantics:
[uv tools](https://docs.astral.sh/uv/guides/tools/).

Retained non-decisive attempts matter: a guessed binary path exited 127;
restricting every dependency to wheels selected older 0.13.3, and explicit
0.16.x wheel-only attempts failed on docopt. Those results cannot qualify the
current command. The corrected probes above use native dependency installation.
The [probe receipt](../../evidence/artifacts/research-skill-round2-20261005/probe.json)
keeps return codes, source/distribution scopes and private-log hashes; returned
output excerpts are committed separately. Exact per-process UTC times were not
captured; the observed execution window is retained rather than invented times.
Provider-native usage remains unknown; no research command ran.

## HTTP and activation gates

The separate held gptr-mcp source is not qualified by fixing the vendor command.
At [server.py:277-312](https://github.com/assafelovic/gptr-mcp/blob/63884773685b1f12c7f0d9e283b3d71a5b9b5fda/server.py#L277),
startup checks OPENAI_API_KEY and returns when absent; ordinary stdout is printed
before STDIO startup, and a busy loop follows a returned mcp.run. These are
source-reviewed lifecycle concerns, without a new server execution. Its
[tester](https://github.com/assafelovic/gptr-mcp/blob/63884773685b1f12c7f0d9e283b3d71a5b9b5fda/tests/test_mcp_server.py#L5)
exercises SSE, which cannot establish the recorded STDIO gate. That gate still
requires a pinned environment, protocol-clean handshake, five-tool discovery,
useful results in both clients, and bounded start/stop/removal.

DeerFlow v2.1.0 at `345f08be00c8a9495079b732a39b46aa9af1584e` offers a distinct
HTTP skill. Its [SKILL.md:8,17-28,46,56-66](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/skills/public/claude-to-deerflow/SKILL.md#L8)
and [chat.sh:26-42](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/skills/public/claude-to-deerflow/scripts/chat.sh#L26)
require reachable gateway health, thread creation and a streamed run. Embedded
DeerFlowClient.chat acceptance starts no HTTP service and cannot prove these
conditions. The existing native plan keeps HTTP conditional on this skill gate;
this lane does not restore it or install an overlapping skill.

Mode correction: [chat.sh:55-59](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/skills/public/claude-to-deerflow/scripts/chat.sh#L55)
enables subagents only for ultra; pro enables planning without subagents. A
comparison must freeze the script's actual mode rather than transfer the skill
prose's broader pro/ultra claim.

## Existing-owner comparison and recommendation

The native-stack-research skill remains the installed research-harnesses entry
point. The repository plan installs it into both clients, but its exact name is
absent from the checked adoption skills manifest at the input base
`4fd710698f53c3581cb1cfe9258ef7b1854ac080`. The skills-lifecycle owner must resolve
that ownership gap. The co-op's retained research-harnesses receipt records
after_sign_in failure and No results found/GraphRecursionError; it is historical
executor evidence, not a fresh failure or a reason to duplicate the repair.

Recommendation for the command-center decision: preserve the current hold,
consider serving this job through the existing research-harnesses owner, and
require a measured overlap win before adopting an HTTP skill. This is an input
recommendation, not a BY_DESIGN verdict or a new acceptance claim. The
[frozen task/evaluation design](../../evidence/artifacts/research-skill-round2-20261005/head-to-head-design.json)
uses upstream promptfoo and six fixed research tasks, and requires matched
DeerFlow modes before execution for
report/entry-route A/B. The repository's native Claude skill-creator paired
benchmark remains a separate skill-adoption gate; this report-scoring design
cannot replace it.
Material runtime/model/search inputs must be preregistered after owner gates
return; the design is not an executed convergence experiment. The separate
30-query search-provider comparison cannot establish skill, client or HTTP
acceptance.

Overturn conditions: a maintained upstream MCP route with a functioning entry
point and all native activation gates; or an owner-approved HTTP skill that
passes lifecycle/client gates and wins the matched head-to-head. For the
maintenance finding, reread the default-branch commit and releases APIs. For the
executable finding, freeze the new distribution and rerun both discovery and
protocol acceptance. Installed-client sign-in alone supplies neither provider
credentials nor these gates.

Completeness critic inputs: the vendor
[mcp-server README:3](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/mcp-server/README.md#L3)
redirects to the held gptr-mcp server, not a separate maintained implementation;
[pinned MCP setup docs:36](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/docs/docs/gpt-researcher/mcp-server/getting-started.md#L36)
claim Python 3.10 while core requires >=3.12; HTTP mode and embedded mode
must remain separate. These source corrections feed the next research-skill
lifecycle sweep, without starting a new foundation landscape sweep.
The next comparison sweep should include a primary-paper/PDF/table task; this
software-focused six-task design supplies no evidence for those modalities.
