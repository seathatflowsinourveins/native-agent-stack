# Selected native skill practice — September 21, 2026

[The practice supplement](../catalogs/landscape/native-practice.json) records
TypeSafe and two focused official OpenAI skills for native Codex and Claude.
It fills the public catalog's missing structured TypeSafe choice and gives each
skill a source pin, purpose, activation boundary and verification status.
These are evidenced fits for specific work, not a universal skill ranking.

| Skill | Reason to retain or add | Qualification boundary |
| --- | --- | --- |
| [TypeSafe](https://github.com/typesafe-ai/skills/blob/65a39f393687675ce170e6094757de20370365b9/skills/typesafe-ai/SKILL.md) | Typed routing, ranking, extraction and evidence judgments complement deterministic rules and execution. | Pinned installation, completed native source reviews and an eight-case API diagnostic: 7/8 frozen labels, with the disagreement retained. |
| [gh-fix-ci](https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/gh-fix-ci) | Reuse the official standard-library helper for GitHub checks, field drift and job-log fallback instead of new parsing. | Actual clean-check helper execution passed; failure repair and client skill invocation remain separate. |
| [security-best-practices](https://github.com/openai/skills/tree/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/security-best-practices) | On-demand framework review guidance adds application security coverage beyond secret/workflow scanners. | Pinned installation and client discovery; security findings and false-positive control remain unqualified. |

## Supported installation and activation

Use the upstream **`npx skills`** installation workflow for the named selected
skills and both `codex` and `claude-code` agents. All three are installed at user
scope; TypeSafe is also installed in the adopted project through the same method.
The other two are user-level skills available across projects. Do not introduce
a second TypeSafe installer, overwrite unrelated skills or copy authentication
stores. Keep the full selected skill directories, support files and licenses.

The successful recorded global commands were:

```sh
npx --yes skills add typesafe-ai/skills --skill typesafe-ai --agent codex claude-code --global --yes --json
npx --yes skills add openai/skills --skill gh-fix-ci security-best-practices --agent codex claude-code --global --yes --json
```

The adopted project's TypeSafe command uses `--copy` and omits `--global`.
The exact command is retained in the supplement. These repository sources are
resolved at invocation; verify the resulting source pin and bytes rather than
treat a future installation as proof that the same reviewed revision was used.

The coordinator reported successful installation. Independent read-only
inspection found the corresponding global installer registrations and the project
TypeSafe registration. All three global `SKILL.md` hashes matched the pinned
upstream files, and the project TypeSafe copy matched as well. This is
installation/source identity evidence; each client's actually
loaded skill and task behavior require their own observation. The
[native receipt](../blueprints/native-skill-practice/native-receipt.json) retains
the returned results, tool visibility and failed attempt. All three selected
directories also passed the installed `skills-ref` format check.

Upstream bytes are preserved. Current user instructions, task scope and existing
project authorization take precedence over imported procedural advice. In
particular, `gh-fix-ci`'s repeated plan/implementation approval language must not
create a new approval loop for an already authorized repair. Skill installation
does not expand credentials, publishing authority or any task's allowed actions.

TypeSafe reads [live task-relevant documentation](https://docs.typesafe.ai/llms.txt)
before integration. The selected evidence-review workers receive the relevant
skill and sanitized advisory packet, with **no credentials or API calls**. Only
the coordinator's authorized process loads the required credential scope. Keep
exact rules, risk checks and execution in code; qualify model judgments against
representative evidence.
Typed answers and confidence do not establish truth or permission to act.

The security skill remains limited to requested security guidance/review or
secure-default work in its supported languages. Its references explicitly name
FastAPI **0.128.x** and Next.js **16.1.x**, while the reviewed foundation pins are
**0.141.1** and **16.3.5**. Use current framework primary sources for changing API
details; the reference's age neither proves a defect nor qualifies every newer
version. Do not mistake a local development configuration for a production issue.

## Actual retained helper observation

The pinned `inspect_pr_checks.py` was inspected and run unchanged from process
memory against [PR #55](https://github.com/seathatflowsinourveins/native-agent-stack/pull/55)
with `--pr 55 --json`. It returned exit **0**, no stderr and
`PR #55: no failing checks detected.` A separate native check query observed
**five SUCCESS checks**. The script hash and exact bounded result are retained
in the supplement. This checked the clean path without editing or rerunning CI.
It did not exercise failing-log extraction, a repair or native agent discovery.
The clean result is plain text even with `--json`; callers must preserve that
upstream behavior rather than assume all outputs are JSON.

## Alternatives and comparison threshold

The inspected Vercel UI review skill is a conditional third capability for a real
accessibility/interface review; it fetches mutable external rules, so preserve
their revision when used. The broader React performance guide is unnecessary
for this static catalog task. Anthropic's webapp-testing skill overlaps accepted
browser tooling; no result shows its blanket `networkidle` wait improves the
current workflow. Trail of Bits' deeper differential review is appropriate for
selected security-sensitive changes, with its report effort and plugin-agent
dependency checked before adoption. Agent Skills remains the existing reference
format validator, not another skill pack. Exact pins and original source links
are in the supplement.

Awesome lists help find candidates. Recent commits, stars, official authorship
and list inclusion do not demonstrate superior task quality. Reopen a choice when
a concrete missing behavior and a matching comparative trial justify the added
surface. No matched provider-savings or quality-improvement claim follows from
this review.

## Actual TypeSafe and native role results

The coordinator's opt-in role sources are the
[Claude role](../examples/claude-native/agents/semantic-evidence-reviewer.md) and
[Codex role](../examples/codex-native/agents/semantic-evidence-reviewer.toml).
They inherit model/effort and explicitly separate source review from supplied
TypeSafe judgments. The [eight-case catalog diagnostic](../blueprints/native-skill-practice/catalog-cases.json)
and [evaluation configuration](../blueprints/native-skill-practice/promptfooconfig.yaml)
are separate qualification inputs. The [portable recipe](../blueprints/native-skill-practice/README.md)
contains the commands and frozen case-pack hash. Eight uncached TypeSafe requests
used `jev-1.13.0`, returned zero service errors and matched **7/8** independently
frozen labels, versus **3/8** for weak literal containment. The
[result](../blueprints/native-skill-practice/typesafe-result.json) preserves
Promptfoo exit **100** and all assertion failures. C4 was classified
`contradicted` rather than the frozen `insufficient`; no label or prompt was tuned
after inference. The claim remains unqualified under either interpretation.
This is a small diagnostic, not representative general accuracy or superiority.

Fresh **Codex 0.155.1** and **Claude Code 2.1.278** invocations completed the
bounded source review. Both returned all eight judgments, corrected C4 to
`insufficient` and kept C6's deterministic availability rejection. Claude's
direct tool trace confirms selected skill/source reads (first 40 skill lines and
a targeted lookup of its typed-output rule). This was a top-level native
`--agent` role invocation; it did not verify Claude child dispatch.
Its initialization lists all three
installed skills, but its headless worker did not visibly receive the TypeSafe
body automatically; the role now includes an explicit-read fallback. Claude
resolved to **claude-fable-5-1**, confirmed by native initialization and usage
metadata. Its effort was unavailable.

The first Codex invocation inherited the desktop configuration and could not
read the packet through its optional context tools. It returned no case verdicts;
CLI exit 0 did not make it a functional pass. The existing Linux
`ecosystem-codex --project <project>` launcher and explicit native read-only file
access produced the completed review. The retained CLI stream exposes the
coordinator's completed child report, without the raw child tool trace or resolved
model/effort; those limits remain explicit. No global model or effort was changed.

The receipt preserves usage categories and raw private-log hashes. Codex cache
and reasoning counts overlap its totals; Claude thinking tokens overlap output.
Codex parent usage coverage of children is unspecified. These differently scoped
runs cannot establish savings or a model ranking. Claude's descriptive output
also requires human/source review; it is not a schema-validated action interface.
All judgments remain advisory, and workers receive no API credential.

Native Codex/Claude remain selected for the current agent work. SDKs are
conditional on an embedding need; LangGraph on application state/checkpoint
requirements; Temporal on distributed durable execution. Existing Dagu scheduling
and native workflow lanes keep their separate acceptance. No examined result
justifies replacing them merely to pass a skill into a worker. Current host
workflow size is `unrestricted`; the older `small` recipe is a dated observation,
not a reason to overwrite current settings.

Failure-log repair with `gh-fix-ci`, security finding quality and safe controls,
matched model/cost comparisons, and new-PC runtime execution remain separate
qualification boundaries. They are not installation failures. The selected
skills are ready to use on relevant tasks; another PC must collect its own
native discovery and task evidence. Structural validation and source pins do
not transfer this host's runtime acceptance to another machine.
