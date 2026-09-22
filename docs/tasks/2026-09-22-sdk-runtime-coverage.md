# SDK, harness, runtime and worker coverage sweep (2026-09-22, PR-7)

Scope: extend the catalog's SDK / runtime-worker coverage beyond Claude Code and Codex with a
full-coverage discovery of agent SDKs, coding harnesses, durable runtimes, sandbox and worker
runtimes, dispatch frameworks and protocol SDKs; select on preregistered criteria with adversarial
refutation; deliver a dated ledger the layer owners can fold into the `agent-sdks`, `workers`,
`isolation` and `mcp-surfaces` verdict rows after PR-5 lands. This PR adds only
`catalogs/sota-convergence/sdk-runtime-coverage-20260922.{json,md}`, the per-category evidence
artifacts under `evidence/artifacts/sdk-runtime-coverage-20260922/` and this record; it edits no
landscape ledger, verdict row, manifest entry or handbook section (PR-5 owns those).

## Method and runs

| Stage | Workflow run | Agents | Output |
| --- | --- | --- | --- |
| Discover | `wf_80ca4602-50a` | 19 (12 Sonnet finders, Opus critic, 6 Sonnet gap agents) | 356 unique repositories, 297 not in the catalog; 120 critic gaps verified |
| Enrich and gate | Python over `gh api` (no model) | 0 | 290 pass, 64 flagged (license unknown), 2 excluded (archived, stale) |
| Shortlist, evidence, refute, select, critic | `wf_2f8bd708-1a9` | 151 (18 Opus shortlist judges, 38 Sonnet evidence packets, 76 Opus refutation votes, 18 Opus selection judges, 1 Opus critic) | 38 of 372 category-rows shortlisted by majority; 334 rejections with the three judges' reasons retained |
| Re-collect placeholder packets | `wf_029f0ae2-61a` | 18 | three packets that had come back as placeholder text rebuilt, refuted and re-judged |

Criteria C1-C6, the incumbents C5 is measured against, and the dispositions are quoted in the
ledger. Agreement between judges never promotes; every row's comparison or acceptance command is
retained. Every shortlisted row points at its evidence packet and both refutation votes in the
per-category artifact files (split so that no published file exceeds the guarded Gitleaks 2 MB
target cap).

Dispositions are per (category, repository): a repository judged as a coding harness and as a
protocol SDK answers two different questions, so the majority in each category stands
(`agentclientprotocol/agent-client-protocol` and `agentclientprotocol/codex-acp` keep different
dispositions per category). Coordinator resolutions applied in code (listed in the ledger): the only
no-majority row (`prefecthq/prefect`) lands on `keep_but_compare` per the preregistered overlap rule;
`dagger/container-use` keeps the same-date canonical `refuted` record by a named canonical-record
precedence rule (a coordinator rule, not a preregistered criterion; the judges' keep_but_compare
votes and their comparison are retained as the way to reopen it); the three re-collected rows
replace the discarded placeholders; rows whose judges treated `dagu` as absent carry a presence note
(the 2.16.6 binary is installed under the ecosystem tools directory but not linked on the ecosystem
PATH). The ledger's critic section is the pre-resolution critique, preceded by a status list of how
each item was resolved.

## Result

| Disposition | Rows |
| --- | --- |
| integrate_now | 1 (`modelcontextprotocol/inspector`, protocol-sdks, 3/3) |
| targeted_candidate | 6 (`awslabs/cli-agent-orchestrator`, `swe-agent/mini-swe-agent`, `anthropics/claude-code-action`, `untrivial-ai/agent-orchestrator`, `trailofbits/coop`, `snyk/agent-scan`) |
| keep_but_compare | 18 |
| not_adopted | 7 |
| refuted | 6 |

Executed on 2026-09-22 (native, WSL2 host, `local_integration`): the `integrate_now` row. agent-lab
carries `tools/mcp-conformance/check.sh`, which runs the pinned MCP Inspector 2.7.0 from the
ecosystem PATH with `--cli`, a timeout and `--stored-auth-only` against every server in `.mcp.json`:
`tools/list` must return a non-empty tool array and `--strict` must exit 0 (exit 6 is an
error-severity schema-portability finding; any other non-zero exit is a probe failure); an empty or
unreadable config refuses with exit 2. `--self-test` runs a two-mode fixture MCP server: the
portable mode passes and the unportable mode (a bare boolean where a schema object is expected, the
linter's error-severity `boolean-schema` rule) exits 6, so the gate's failing path is observed rather
than assumed. Observed: self-test status 0 (portable 0, unportable 6); serena 22 tools, ai-memory 23,
socraticode 26, strict ok. It establishes protocol conformance of the configured servers, not their
behaviour.

## Follow-ups (each gated as stated)

1. Ecosystem configuration: link `dagu` 2.16.6 into the ecosystem bin or record the deliberate
   omission; unblocks every scheduling and durability comparison.
2. Viability probes that need no account, consent or paid key run as a separate follow-up on the
   WSL2 host: `awslabs/cli-agent-orchestrator` and the TypeScript Agent SDK on the native Claude
   login (the latter settles the SDK's C1 `api_key_required` label), and the
   `untrivial-ai/agent-orchestrator` headless backend from its checksummed release.
3. Gated on a user decision: `anthropics/claude-code-action` needs a scratch repository and a
   repository secret; `trailofbits/coop` needs `/dev/kvm` group membership; `snyk/agent-scan` needs a
   separate Snyk token; `swe-agent/mini-swe-agent` needs a model endpoint (the host's local endpoint
   serves an embedding model only).
4. Layer owners: fold the `agent-sdks`, `workers`, `isolation` and `mcp-surfaces` rows into the
   landscape ledger's alternatives and `overturn_when` fields after PR-5, with the named comparisons.

## Limits

- Source review, plus unretained spot probes some judges and refuters ran on the host (named in the
  ledger's evidence-class statement), plus the one retained conformance check above. No candidate
  was installed by the sweep, no macOS arm64 execution exists for any row, and the incumbents'
  capabilities were not re-exercised.
- The rejections are metadata triage by three judges, not quality judgements of the projects.
- Evidence packets were written by Sonnet agents from primary sources and refuted by Opus agents;
  three placeholder packets slipped through the first pass and were re-collected; other packet
  defects the critic named are retained in the ledger's critic section.
- Host details in worker output (local user name and groups, credential file locations, token
  scopes) were redacted before publication; loopback service ports remain, as on `main`.
- Usage: discovery about 1.3 M, selection about 12.0 M, re-collection about 1.2 M subagent tokens
  (workflow-reported, not lifetime provider totals).

## Viability probes (follow-up, 2026-09-22)

Workflow `wf_1f3da910-f1c` (three Sonnet/high executors, three Opus/high verifiers) probed the TypeScript
Agent SDK, `awslabs/cli-agent-orchestrator` and the `untrivial-ai/agent-orchestrator` daemon on the WSL2
host; results are summarised in the ledger's `viability_probes` block and Markdown section, with the
sanitised receipts, verifications and coordinator notes in
`evidence/artifacts/sdk-runtime-coverage-20260922/probes-20260922.json`. Executed evidence overturns the
TypeScript SDK's `api_key_required` C1 label on this host; no disposition changes. The review of this
record found that the agent-orchestrator daemon had imported the host Codex login (refresh token
included) into its probe data directory without being asked; that copy was deleted after the review and
the host login still reports valid. Removed from the user home after verification: a probe plan file,
two session transcripts, their cache logs and session-env directories. Remaining: one project entry for
a probe path in the Claude Code user config, ai-memory hook rows naming the two probe sessions, a stale
tmux socket with no server, and the Codex credential rewrite (not reversible).
