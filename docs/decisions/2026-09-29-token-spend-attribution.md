# Decision: run shape is where token spend concentrates; the savings sought are architectural (2026-09-29)

**Decided by:** session `native-agent-stack-76` on host `nativestack-5975wx-20260925`, for the user's request of 2026-09-29
("find our what causes our token spend high? is the context, skills,memory repos mcp tools we load? ... are we enact all the sota
token save practice?"). Decisions 1 to 3 are the user's answers of the same day, recorded as their choices and not as measured results:
enact "with max token save via architectectural optimization with harm only minimal quality", effort "Keep max", and the advisor stays on
("the limit should not be restrict our quality"). Decision 4 is derived from the receipt. Checked against Claude Code 2.1.284 and ccusage
20.0.26. The measurement is the receipt
[`claude-spend-attribution-20260929`](../../evidence/receipts/claude-spend-attribution-20260929.json); a seven-agent Workflow (three
source-research stages, a measurement verifier, a gap table, a gap-table refuter and a synthesis) sourced the practices below; its refuter
corrected four of 25 gap rows, which are reflected here.

**Scope:** this record, the receipt, its scan script (`evidence/artifacts/claude-spend-scan.py.txt`) and the "Run shape and
accounting" section of `docs/token-practice.md`. It changes no setting, agent definition, hook, carrier text or pin. The frozen treatment
of Gate A (#381, owner `native-agent-stack-2d`), the compaction window (#416) and the effort, model and advisor policy are left as they
are; the levers that touch them are listed for their owners.

## What the measurement says

At API list prices (a proxy; the plan meter weights tokens differently), spend concentrates in how runs are shaped. The receipt does not
size the always-loaded files (decision 5):

- Agent-tool and workflow children are 81.3% of dollars, workflow stages 66.0%; 4 of 579 session trees cover half.
- A child of more than 60 calls is 24.0% of children and 53.4% of dollars. A child with no role definition is 63.9% of
  children and 41.7% of dollars, at a median first call of 39.5K tokens.
- Effort `max` covers 82.3% of calls and thinking is 60.8% of output tokens, which stays in later context by default on Opus 4.5+.
- The advisor is 14.0% of dollars (1,839 iterations) and its transcript read is uncached; `child-usage.mjs` leaves it out.
- Calls above 400K tokens of context are 23.1% of dollars. Children's rewrites after 5-minute to 1-hour gaps are 20.0% of their
  5-minute writes.
- Context Mode is 98.6% of MCP calls; the other code-index servers are small but their ToolSearch loads exceed their calls.

## Decisions

1. **Effort stays `max` for every role (the user's answer: "Keep max").** The docs advise testing `max` before broad adoption, so the M7
   arms of the [max-default record](2026-09-29-max-default-effort.md) stay the overturn path.
2. **The advisor stays on (the user's answer: "the limit should not be restrict our quality").** `advisorModel` has been opus since
   2026-09-28; 750 of the 1,839 iterations ran on `claude-fable-5-1`, all but 17 before that date. As a documented fact, not part of the user's
   reasoning: `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1` is a global switch with no cap or per-agent opt-out, so any cheaper advisor policy
   needs its own quality-per-cost result.
3. **Savings are sought in architecture (the user's request: "max token save via architectectural optimization with harm only minimal
   quality").** In practice: dispatch by role, bounded fresh-context units, packets that carry excerpts instead of re-reads, tool-output
   discipline, session boundaries, campaign budgets and complete accounting. No model, effort or advisor change is made to save
   tokens without a paired quality result.
4. **The subagent cache TTL stays at the 5-minute default (derived from the receipt).** Children wrote 833.6M tokens to the 5-minute class
   and rewrote 166.5M of them after 5-minute to 1-hour gaps (20.0%). At the generic price ratios a 1-hour class costs a net +308.8M
   input-equivalents (+500.3M for every remaining write at 2x instead of 1.25x, less 191.5M for turning the rewrites into 0.1x reads),
   and pays only above a rewrite share of 0.39. Overturn: misses attributed to agent types show a type whose rewrite share exceeds
   0.39.
5. **The always-loaded files are not treated as a lever here.** The receipt does not size them. They are inside their documented size
   limits ([memory](https://code.claude.com/docs/en/memory): 200 lines / 25KB for `MEMORY.md`, under 200 lines per `CLAUDE.md`), the
   skill listing follows `adoption/skills/manifest.json`, and the one change made is #499, which moves the trading-lane block out of the root
   `AGENTS.md`.

## Practice status

Read back from the files the client loads (repository at `origin/main@16f3c7fe`, targets re-checked at `9ad7bebe`). Sources are Claude
Code docs (CC), API docs (API) and the [multi-agent research post](https://www.anthropic.com/engineering/multi-agent-research-system).

| Practice | Source | Status | Next |
| --- | --- | --- | --- |
| Call budget per brief, fresh-context units | multi-agent post; `examples/claude-native/workflows/README.md` brief contract | partly (brief text only) | report calls per stage against the budget |
| `maxTurns` backstop | CC sub-agents (partial marking from v2.1.246) | partly (5 of 11 roles) | Gate A owner, after #381 |
| Effort matched to task | CC model-config: Opus 5.5 defaults to `medium` | no (`max` by user decision) | M7 sweep |
| Context editing (`clear_thinking`, `clear_tool_uses`) | API context editing | no Claude Code setting found; thinking caps rejected in the 2026-09-28 sweep | upstream watch |
| Sparing, cached advisor | CC advisor; API advisor tool | no (no cap, uncached by design) | upstream watch (#91110, #94656) |
| Role-agent dispatch | CC sub-agents; `AGENTS.md` | partly (no `// dispatch:` check) | report the agent-type mix per run |
| `omitClaudeMd` | CC sub-agents (v2.1.271) | partly (5 of 11 roles) | Gate A owner |
| Hand off findings, not re-reads | multi-agent post | partly | prior-stage excerpts in the brief contract |
| `/clear` and a handoff between tasks | CC costs | no rule (mention only) | rule in `docs/token-practice.md` |
| Native auto-compact | CC settings `autoCompactWindow` | yes (native default) | #416 decides |
| Subagent cache TTL | CC settings `subagentPromptCacheTtl` | yes (5m, decision 4) | misses by agent type |
| Lean always-loaded files and skill listing | CC memory, `skillListingBudgetFraction` | yes | measure the listing on a default-typed child |
| Deferred MCP tools | CC mcp, prompt caching | partly (the carrier forces two serena loads per task) | Gate A owner |
| Cap and filter tool output | CC `bashOutputMaxChars`, `MAX_MCP_OUTPUT_TOKENS` | partly (RTK hook, Context Mode) | measure the Bash size tail |
| Advisor-aware metering, run caps, spend alarm | API advisor tool; CC `--max-budget-usd` | partly (ccusage counts the advisor; `child-usage.mjs` does not; integrity alerts exist, no rate alert) | see levers |
| Cache-stable headless prompts | CC `--exclude-dynamic-system-prompt-sections` | no | paired probe (M36) |

Three refuted rows changed the plan: the trading block already had an experiment (M2/KC-09), so #499 runs it under the hot-file
protocol; alerts on the Claude token and cost counters already exist in
`observability/backends/templates/ecosystem-prometheus-rules.yml.example`, so only a rate or budget rule is missing; and the
compaction window belongs to #416, not to a repository-safe change.

## Levers by owner

- **Repository (queued after this record):** count `usage.iterations` advisor entries in `child-usage.mjs` (agent-lab first, then
  re-vendored byte-identical; the file changed in #432, so tell the Gate A owner) and report calls per stage and the agent-type mix;
  prior-stage excerpts in the brief contract; `--max-budget-usd` at headless call sites (print mode only, subagent spend counts); a
  spend-rate rule beside the existing counter alerts; a session-boundary rule.
- **This host:** re-run the scan per window, attribute the 5m-1h misses to agent types, measure the Bash result-size tail, prune
  index entries whose delete condition is met.
- **Gate A owner, after #381 closes:** `maxTurns` on the six uncapped roles, `omitClaudeMd` starting with `landscape-sweep-worker`
  (47.9K-token first call), a limit of about three queries per `ctx_batch_execute`, the serena ids out of the mandatory select,
  per-agent `experimental.cacheTtl`, any `bashOutputMaxChars` change (`tools/token-report/token_manifest.py` hard-codes 30,000).
- **User policy:** per-wave budgets and stop rules for token-programme campaigns; effort and advisor stay as decided above.
- **Upstream:** context editing in Claude Code, advisor caching, a per-agent advisor opt-out, the `maxTurns` misreport (#80848).

## Overturn conditions

Revisit this record when any of these happens:

- a paired quality-per-cost result (M7 arms, an advisor arm) supports a lower effort, another model or a different advisor policy for
  a role;
- Claude Code adds a setting for thinking or tool-result clearing, an advisor cap or opt-out, or advisor caching;
- a scan over a later window shows the shares moving (children below 75% of dollars, children over 60 calls below 40%, or default-typed
  children below 30%), which would mean the run shape changed and the levers above need re-ranking;
- misses attributed to agent types put a type's rewrite share above the 0.39 break-even, which makes a 1-hour class pay for it.

## Limitations

- **One host, one window.** The receipt counts this workstation's retained transcripts for six days, during which a token-saving
  programme was itself the largest consumer (an earlier private count put its sessions at 58.7% of the top 40). Shares describe that
  window, not steady state. The transcripts come from Claude Code 2.1.280 to 2.1.284.
- **Dollars are a proxy.** List prices are applied to counted tokens; the plan meter's weighting is unknown. Cache reads on Opus 5.5
  are priced at 0.05x, which the earlier input-equivalent count (a flat 0.1x) overstated.
- **No quality comparison.** Nothing here shows that fewer or shorter children, a lower effort or a different advisor keep quality; each
  needs its own paired result.
- **Approximate miss bins.** A miss is a call whose cache read fell below half the previous context; its gap includes the next
  call's response time, and calls after a compaction also meet the rule.
- **The history-composition estimate is not receipted.** An earlier private fit of what fills the context (Bash results about a quarter,
  Context Mode results a tenth) has R-squared 0.71 and unstable small families, so no lever above depends on it.
- **Unsized inference.** Session titles, compaction, WebFetch summaries and the auto-mode classifier have no usage record.

## Sources

- Receipt `claude-spend-attribution-20260929`; ccusage <https://github.com/ccusage/ccusage> (v20.0.26 installed, advisor counting from v20.0.17).
- Claude Code docs read 2026-09-29: [costs](https://code.claude.com/docs/en/costs), [model configuration](https://code.claude.com/docs/en/model-config),
  [prompt caching](https://code.claude.com/docs/en/prompt-caching), [advisor](https://code.claude.com/docs/en/advisor),
  [memory](https://code.claude.com/docs/en/memory), [sub-agents](https://code.claude.com/docs/en/sub-agents).
- API docs: [advisor tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool),
  [context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing),
  [pricing](https://platform.claude.com/docs/en/about-claude/pricing).
- [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) (about 15x the tokens of a chat).
- Repository: `docs/decisions/2026-09-28-community-sweep.md` (M2, M7, M36), `examples/claude-native/workflows/README.md`,
  `docs/lanes.md`.
