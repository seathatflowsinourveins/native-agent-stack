# Role tool-use measurement gate

Status: NOT_READY. Frontmatter checks establish available grants, not organic use.
The five pinned base roles remain byte-identical to the ecfa1127 source. Their
preload-only variants preserve base tool grants. P0-1 token-tool changes are held
as private plan inputs by the newer client-wiring hold, including Serena.

## Before (native run retained as incomplete)

The accepted measure is organic use in Claude Code's native transcripts, not
prompted paired controls. The predeployment snapshot cutoff is 2026-10-06T12:00:00Z;
its seven-day interval is [2026-09-29T12:00:00Z, 2026-10-06T12:00:00Z). Join native
parent Task/Agent subagent_type to child id; use Workflow journals' agentType
where needed. A child without verified attribution is UNKNOWN rather than zero.
Use the unchanged organic-E2E v1.1 grader rules at native-agent-stack@
536487a42af0fa0f959d25a34ee8159694c9868b:
evidence/artifacts/organic-e2e-20261005/harness/grade.py. Count successful calls
only, key MCP calls by native server prefix, match skills by SKILL.md realpath,
and exclude policy-named/prompted calls. The bounded native reader ran once:
exit 2, source_budget, 2,147,275,318 bytes read and 3,681 native source hashes.
Its fixed 2 GiB condition and UNKNOWN result are retained without a larger-budget rerun.
The [actual emitted table](../../evidence/artifacts/skills-role-organic-before-20261007/before.md)
and [compact receipt](../../evidence/artifacts/skills-role-organic-before-20261007/receipt.json)
keep the missing historical bindings and partial native observations.

The supplied 2026-10-06 census has SHA256
`66d2a74064400e36e8fadb5e5f61e4732ae988bb589818e437f872f17ccfce4f`.
Its selected non-auth units contain 32 items plus summaries at JSON pointers
`/units/0`, `/units/1` and `/units/2`. They do not report per-role counts or eligible
child denominators. `/synthesis/verdict` reports the aggregate ten roles/81.3% SOURCE-HOST
spend; `/synthesis/fixes/0` names five families. Neither supplies role attribution.
Global counters include workflow parents and remain separate from this table.
Each layer cell is eligible children with at least one successful call / total
successful calls in that layer. Both values remain unknown after this incomplete
aggregation; availability is not substituted for either count.

| Base role | Eligible children | Semble | Headroom | codebase-memory | context-mode | Serena | jCodeMunch | SocratiCode |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| isolated-builder | unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown |
| stack-researcher | unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown |
| evidence-reviewer | unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown |
| stack-verifier | unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown |
| security-reviewer | unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown | unknown/unknown |

Unknown does not mean zero. The census's global zero counters are not assigned to
role rows. The original private census and raw sessions are not copied here.

The three returned gaps are historical_agent_definition_not_captured,
prior_directive_content_unproven and native_skill_or_input_binding_unproven.
Their per-role counts are in the compact receipt. Increasing only the byte budget
does not establish those missing bindings. Git history supplies candidates;
uncommitted edits and what a child actually loaded remain unknowable without
native capture. Current policy files are not retrospective evidence.

Separately labelled partial successful-result-flag context-mode observations are
717 for isolated-builder, 5,010 for stack-researcher, 2,584 for evidence-reviewer,
1,832 for stack-verifier and 0 for security-reviewer. These are observed lower
bounds in examined records, not organic totals or whole-window non-use. Other
layers remain unresolved; zero observed witnesses do not establish absence.

Next skills-sweep input and forward-capture requirement: retain each child's
agent-definition hash, instruction-carrier hashes and lifecycle-manifest hash
through the existing hooks at run time. Exact role joins, per-reference skill
identity and complete window/source coverage also need evidence. The command
center owns that deployment; this record changes no hook or client configuration.

## After (pending deployment)

The interval is the first seven days after the command center applies the grants,
using the same attribution and success/exclusion rules. No deployment or post-change
native role census has occurred. Actual native events, dispatch, client version and
eligible-child counts must be retained before pending cells become measurements.

| Variant family | Eligible children | Semble | Headroom | codebase-memory | context-mode | Serena | jCodeMunch | SocratiCode |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| isolated-builder variants | pending | pending | pending | pending | pending | pending | pending | pending |
| stack-researcher-token-tools | pending | pending | pending | pending | pending | pending | pending | pending |
| evidence-reviewer-token-tools | pending | pending | pending | pending | pending | pending | pending | pending |
| stack-verifier-token-tools | pending | pending | pending | pending | pending | pending | pending | pending |
| security-reviewer-token-tools | pending | pending | pending | pending | pending | pending | pending | pending |

Retain before and after scopes separately, never adding their counters. Prompted
headless or Workflow controls are distinct units and are excluded from this organic
measure. Blind roles, Skill-less delivery gaps, stale catalogs and failed attribution
need explicit counts. No host application precedes the command-center ACK.

Sources: the dated source census identified above; native-agent-stack@ecfa1127:
adoption/agents/claude; [Claude native subagents](https://code.claude.com/docs/en/sub-agents);
the accepted [organic-E2E v1.1 grader](https://github.com/seathatflowsinourveins/native-agent-stack/blob/536487a42af0fa0f959d25a34ee8159694c9868b/evidence/artifacts/organic-e2e-20261005/harness/grade.py).
