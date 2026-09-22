# SDK, harness, runtime and worker coverage sweep (2026-09-22, PR-7)

Scope: extend the catalog's SDK / runtime-worker coverage beyond Claude Code and Codex with a
full-coverage discovery of agent SDKs, coding harnesses, durable runtimes, sandbox and worker
runtimes, dispatch frameworks and protocol SDKs; select on preregistered criteria with adversarial
refutation; deliver a dated ledger the layer owners can fold into the `agent-sdks`, `workers`,
`isolation` and `mcp-surfaces` verdict rows after PR-5 lands. This PR adds only
`catalogs/sota-convergence/sdk-runtime-coverage-20260922.{json,md}` and this record; it edits no
landscape ledger, verdict row, manifest entry or handbook section (PR-5 owns those).

## Method and runs

| Stage | Workflow run | Agents | Output |
| --- | --- | --- | --- |
| Discover | `wf_80ca4602-50a` (agent-lab) | 19 (12 Sonnet finders, Opus critic, 6 Sonnet gap agents) | 356 unique repositories, 297 not in the catalog; 120 critic gaps verified |
| Enrich and gate | Python over `gh api` (no model) | 0 | 290 pass, 64 flagged (license unknown), 2 excluded (archived, stale) |
| Shortlist, evidence, refute, select, critic | `wf_2f8bd708-1a9` | 151 (18 Opus shortlist judges, 38 Sonnet evidence packets, 76 Opus refutation votes, 18 Opus selection judges, 1 Opus critic) | 38 of 372 category-rows shortlisted by majority; 334 rejections with the three judges' reasons retained |
| Re-collect placeholder packets | `wf_029f0ae2-61a` | 18 | three packets that had come back as placeholder text rebuilt, refuted and re-judged |

Criteria C1-C6 and the dispositions are quoted in the ledger. Agreement between judges never
promotes; every row's comparison or acceptance command is retained. Coordinator resolutions applied
in code (listed in the ledger): the only no-majority row (`prefecthq/prefect`) lands on
`keep_but_compare` per the preregistered rule rather than the judges' strongest claim;
`agentclientprotocol/codex-acp` is unified to `keep_but_compare` in both categories because an ACP
consumer is in scope; `dagger/container-use` keeps the same-date canonical `refuted` record rather
than reopening it; the three re-collected rows replace the discarded placeholders; rows whose judges
discounted `dagu` as absent carry a presence note (the 2.16.6 binary is installed under the ecosystem
tools directory but not symlinked on the ecosystem PATH).

## Result

| Disposition | Rows |
| --- | --- |
| integrate_now | 1 (`modelcontextprotocol/inspector`, protocol-sdks, 3/3) |
| targeted_candidate | 6 (`awslabs/cli-agent-orchestrator`, `swe-agent/mini-swe-agent`, `anthropics/claude-code-action`, `untrivial-ai/agent-orchestrator`, `trailofbits/coop`, `snyk/agent-scan`) |
| keep_but_compare | 19 |
| not_adopted | 6 |
| refuted | 6 |

Executed today (native, WSL2 host, `local_integration`): the `integrate_now` row. agent-lab now
carries `tools/mcp-conformance/check.sh`, which runs the pinned MCP Inspector 2.7.0 from the
ecosystem PATH with `--cli`, a timeout and `--stored-auth-only` against every server in `.mcp.json`:
`tools/list` must return a non-empty tool array and `--strict` must not exit 6. Observed on
2026-09-22: serena 22 tools, ai-memory 23, socraticode 26, strict ok, exit 0 for all three; the
check is a `docs/validation.md` row in agent-lab. It establishes protocol conformance of the
configured servers, not their behaviour.

## Follow-ups (each gated as stated; none executed here)

1. Ecosystem configuration: symlink `dagu` 2.16.6 into the ecosystem bin or record the deliberate
   omission; unblocks every scheduling and durability comparison (Codex-owned configuration audit).
2. C1 correction independent of any run: the TypeScript Agent SDK's `api_key_required` label is
   contradicted by the executed Python-sibling probe on native Claude Code login
   (agent-lab `docs/tasks/2026-09-22-executed-comparisons.md`); narrow the penalty on the card.
3. Preregistered agent-sdks worker arms (pydantic-ai with a key-free local model; the TypeScript
   Agent SDK with `pathToClaudeCodeExecutable`) need a local chat model or a native login path; no
   local chat model is served on this host today (the local endpoint is an embedding model).
4. `anthropics/claude-code-action` CI smoke needs a scratch repository and a repository secret (an
   account decision); `trailofbits/coop` needs an OS consent step (`/dev/kvm` group membership);
   `untrivial-ai/agent-orchestrator` headless probe needs no model spend and can run under the
   bounded runner.
5. Layer owners: fold the `agent-sdks`, `workers`, `isolation` and `mcp-surfaces` rows into the
   landscape ledger's alternatives and `overturn_when` fields after PR-5, with the named comparisons.

## Limits

- Source review end to end; no candidate was installed or executed by the judges, and no macOS
  arm64 execution exists for any row. The incumbents' capabilities were not re-exercised.
- The rejections are metadata triage by three judges, not quality judgements of the projects.
- Evidence packets were written by Sonnet agents from primary sources and refuted by Opus agents;
  three placeholder packets slipped through the first pass and were re-collected; other packet
  defects the critic named (one quotation that does not exist in its cited source, second-hand
  measurements carried into dispositions) are recorded in the ledger's critic section.
- Usage: discovery about 1.3 M output tokens, selection about 12.0 M, re-collection about 1.2 M
  (workflow-reported subagent tokens, not lifetime provider totals).
