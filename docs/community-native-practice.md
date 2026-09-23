# Community guidance for native practice

Reviewed September 20, 2026 against foundation base `85ead55`. The
[machine-readable review](../catalogs/foundation/community-practice-20260920.json)
records five repositories, exact revisions/licenses/source hashes, two selected
skill files and decisions for all 16 existing foundation layers. This is dated
curation, not a universal ranking or new runtime acceptance.

The requested `affaan-m/everything-claude-code` URL resolves to canonical
[affaan-m/ECC](https://github.com/affaan-m/ECC/tree/2b6e839771e53096d8451a213d40dc64ec8acac0).
It is the existing ECC component, not another repository to install.

## Selected change

Retain the upstream **search-first** and **iterative-retrieval** skills. Exact
copies already exist in the adopted starter project's Claude and shared skill
locations. Both exact files are now installed as shared user skills, matching
the hashes below, with Claude symlinks added and project copies preserved. A
native Claude review returned both names in its actual initialization skill
inventory. Installation, discovery and independently checked review results are
in the [profile receipt](../evidence/receipts/native-claude-profile-20260920.json).

| Selected source at ECC `2b6e839771e53096d8451a213d40dc64ec8acac0` | Bytes | SHA-256 |
| --- | ---: | --- |
| [skills/search-first/SKILL.md](https://github.com/affaan-m/ECC/blob/2b6e839771e53096d8451a213d40dc64ec8acac0/skills/search-first/SKILL.md) | 8,021 | `d66d744228b9cf860acf35f8a90cbbe8195e61367860da9d3632f9fc65706733` |
| [skills/iterative-retrieval/SKILL.md](https://github.com/affaan-m/ECC/blob/2b6e839771e53096d8451a213d40dc64ec8acac0/skills/iterative-retrieval/SKILL.md) | 6,786 | `b453b16d3e36174b8487c05ab807d0321a66c2d058812b2ae129d82824183725` |

Use search-first when selecting an implementation and iterative-retrieval when a
worker demonstrably lacks context. Neither requires another landscape sweep for
a known bounded fix. Keep the repository's [native defaults](harness-defaults.md),
[convergence contract](convergence-architecture.md) and
[acceptance evidence policy](acceptance-evidence-policy.md) authoritative:
relevant upstream work first, bounded useful delegation, complete failed-attempt
records and meaningful verification without repeated permission or setup gates.

Do not install the full ECC plugin, hook/rule bundle or a replacement evaluation
framework for this change. Its plugin enables local hooks by default. The reviewed
verification-loop adds generic periodic reruns, a coverage target and secret-search
output examples that do not define this project's checks. The eval-harness guide
is useful reference, but its candidate execution is explicitly disabled; its
utility receipts cannot establish runtime containment. Neither is selected for
automatic installation.

## Community sources and decisions

| Source and reviewed revision | Decision and reason |
| --- | --- |
| [ECC](https://github.com/affaan-m/ECC/tree/2b6e839771e53096d8451a213d40dc64ec8acac0), MIT; head September 20 | Adopt the two named instruction files only. The repository also ships an installer, plugin, rules and hooks; those broader surfaces are not implied by skill selection. |
| [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice/tree/bde3f03174714fff4145d21cfda41ddd2ffffb28), MIT; head September 20 | Retain explanations and native-format examples. Weather/presentation workflows and contributor tips are reference material, not our foundation's task-performance evidence. Do not copy its repository configuration wholesale. |
| [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code/tree/72f437590bb430a08e88e9b68d44c026ff626904), CC-BY-NC-ND-4.0; head September 20 | Retain as linked discovery. Inspect each discovered implementation independently; no list content is vendored or adapted here. |
| [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents/tree/ca7a50b7648682c3a9e33dbf0a12c5a4c770cb89), MIT; head September 14 | Conditional named-role reference. Native category plugins and individual agent files are available, but the reviewed code-reviewer exposes write tools. Its inherited model does not make it a read-only or proven superior reviewer. |
| [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers/tree/393b4e9fafb0348e5a1c2a4ef5a8719b0d85e061), MIT; head September 15 | Retain as discovery for a concrete missing capability. A server listing does not justify new registration, authority or service installation. |

All five repositories were unarchived at review. Recent activity establishes
maintenance context, not effectiveness. Fit, native compatibility, scoped evidence
and added instruction/dependency cost determine the decision; stars and claims
from authors are not comparative measurements.

## Fit across the existing foundation

Incumbent capability IDs are joined explicitly in the review's `layer_map` to
[foundation decisions](../catalogs/foundation/decisions.json). Their receipts remain
the evidence; this table does not rerun or upgrade them.

| Layer | Selected practice and boundary |
| --- | --- |
| Native clients | Retain native accounts, models and session behavior; community recipes do not replace them. |
| Instructions / skills | Make only the two pinned ECC skills available on demand; preserve canonical project rules. |
| Workers | Retain owned native children and bounded coordination; use iterative retrieval for an observed context gap. |
| Isolation | Retain tested worktree/OS boundaries; role names and hook prose are not isolation. |
| Code navigation | Retain exact, structural and scoped semantic tools; search for existing implementations before new glue. |
| Document retrieval | Apply bounded refinement to relevant misses; the four recorded QMD benchmark misses remain unfixed by this review. |
| Semantic RAG | Retain the accepted runtime and index/recovery evidence; directory inclusion proves no retrieval or GPU quality. |
| Durable memory | Keep ai-memory as the shared memory of record; no parallel learning/capture hook installation. |
| Web research | Use native Search/Extract and primary-source checks; lists remain discovery aids. |
| Token efficiency | Avoid loading whole role/skill catalogs; file sizes are not measured provider savings. |
| Quality / evaluation | Keep actual upstream/project oracles and independent review; evaluation guides remain conditional. |
| CI / supply chain | Keep pinned CI/provenance checks; retain selected skill hashes and licenses. |
| Scheduling / supervision | Reuse accepted Dagu/systemd recipes; no perpetual community loop or new orchestrator is selected. |
| Hosting / services | Reuse accepted services; examples do not require another standing deployment. |
| Recovery / portability | Reuse native checkpoints and backups; handoff prose is supplementary, not recovery evidence. |
| Observation / inference | Keep scoped telemetry/routes; no new HUD, model or gateway acceptance is claimed. |

Current primary Claude documentation supports deliberate
[skill discovery/invocation](https://code.claude.com/docs/en/skills), explicit
[subagent tools and permissions](https://code.claude.com/docs/en/sub-agents), and
[verification tied to the task](https://code.claude.com/docs/en/best-practices).
A preloaded skill's full content differs from ordinary skill discovery. Review
actual tool authority separately from inherited model settings. Community advice
must not override the user's existing authorization or invent a new approval loop.

The source record preserves a nonexistent guessed community rules path and three
refused direct Markdown fetches. Official-page extraction then succeeded through
Tavily with no failed results. Those extract hashes bind returned snippets, not
complete origin-page bytes. No model/provider/broker call, new native qualification,
settings edit or installation was performed by this review; quality and cost
improvement remain unmeasured.

## 2026-09-23 review

Each row's ref is the repository's default-branch HEAD read via `gh api
repos/<owner>/<repo>` and `gh api repos/<owner>/<repo>/commits/<default_branch>`
on 2026-09-23; none were archived. `crawl4ai`, `Firecrawl`, `Docling` and
`browser-use` stay recorded alternatives from prior rounds (not re-reviewed here).

| Repository (ref, checked date) | Overlap | Disposition | Overturn condition |
| --- | --- | --- | --- |
| [jina-ai/reader](https://github.com/jina-ai/reader/tree/1574bfd380d2) (`main@1574bfd380d2`, 2026-09-23) | URL-to-Markdown web extraction, same job as Tavily Extract | Not adopted. This project already has a qualified web-research path (native Search/Extract, `docs/community-native-practice.md`'s web-research row); reader is a hosted proxy (`r.jina.ai`) adding an external network dependency and no demonstrated gap it closes. | A measured extraction-quality or coverage gap on this project's own corpus that the existing native path cannot close. |
| [adbar/trafilatura](https://github.com/adbar/trafilatura/tree/c852cae9708a) (`master@c852cae9708a`, 2026-09-23) | Python HTML text/metadata extraction library | Recorded alternative, not adopted. Overlaps `markitdown`'s and the native web-research path's coverage; no comparison yet shows it beats either on this project's documents. | A measured extraction-accuracy comparison against markitdown/native Extract on representative project documents showing trafilatura wins. |
| [idosal/git-mcp](https://github.com/idosal/git-mcp/tree/c487a29895dc) (`main@c487a29895dc`, 2026-09-23) | Remote MCP server exposing a GitHub repo's docs/code to reduce hallucination | Not adopted. This project's own code navigation (Serena, SocratiCode, jCodeMunch) and QMD already index this repository directly and locally; git-mcp targets *other* GitHub projects' docs via a hosted remote server, a different, unqualified network dependency. | A named task needing indexed access to an external GitHub repo this project does not check out locally. |
| [apify/crawlee](https://github.com/apify/crawlee/tree/b6684527fa90) (`master@b6684527fa90`, 2026-09-23) | Node.js web-scraping/browser-automation crawler library | Recorded alternative, not adopted. `agent-browser` (this profile's own pinned browser-automation tool, see `adoption/pins-linux-x86_64.json`) already covers this project's browser-automation need; crawlee is a heavier standing framework (proxy rotation, multiple engines) with no demonstrated gap `agent-browser` leaves open. | A task needing crawlee's specific multi-engine/proxy-rotation crawling that `agent-browser` cannot perform. |
| [ScrapeGraphAI/Scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai/tree/c75c8084fae2) (`main@c75c8084fae2`, 2026-09-23) | LLM-driven scraping/extraction pipelines | Not adopted. Every scrape step here would itself be an unqualified LLM call against untrusted web content (prompt-injection surface) for a job the native web-research path and markitdown already cover without one. | A demonstrated extraction task neither native Search/Extract nor markitdown can complete, with a reviewed prompt-injection mitigation. |
| [upstash/context7](https://github.com/upstash/context7/tree/6cbdb49c407e) (`master@6cbdb49c407e`, 2026-09-23) | Up-to-date library/API documentation retrieval for LLM coding agents | Recorded alternative, not adopted. Overlaps this project's own QMD scoped-Markdown retrieval and native web research for "current docs" lookups; no comparison yet shows a coverage or freshness gap. | A measured case where QMD/native web research misses current upstream documentation that Context7 finds. |
| [garrytan/gstack](https://github.com/garrytan/gstack/tree/b9706f3635b6) (`main@b9706f3635b6`, 2026-09-23) | 23 opinionated named-role Claude Code tools/subagents (CEO, Designer, etc.) bundled together | Not adopted. This project already defines its own task-matched agents (`source-scout`, `evidence-reviewer`, `isolated-builder`, `semantic-evidence-reviewer`, `blind-judge`) with named tool allowlists and recorded qualification; gstack's role names are not a substitute for that evidence and would duplicate/conflict with the existing set. | A specific gstack role demonstrating a capability none of the five existing agents cover, reviewed and qualified on its own. |
| [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD/tree/1b59caa7f964) (`main@1b59caa7f964`, 2026-09-23) | Agile/agentic-development method and role framework | Not adopted. A process methodology, not a runtime component; this project's `AGENTS.md`/`docs/` already define its own work/evidence/parallelism rules. Adopting a second, overlapping process framework would create conflicting instructions rather than close a gap. | A specific BMAD artifact (e.g. a template or checklist) solving a concretely observed process gap this project's own docs do not cover. |
| [trailofbits/claude-code-config](https://github.com/trailofbits/claude-code-config/tree/2109be998c09) (`main@2109be998c09`, 2026-08-24) | Opinionated Claude Code defaults/workflows from a security firm | Recorded reference, not adopted wholesale. Read for ideas; this catalog's own `adoption/templates/claude.settings.template.json` and hooks are the source of truth and are not overwritten by another org's opinionated defaults. | A specific named default demonstrated safer or more effective than this catalog's own on a reproduced comparison. |
| [trailofbits/claude-code-devcontainer](https://github.com/trailofbits/claude-code-devcontainer/tree/feea113719e5) (`main@feea113719e5`, 2026-08-28) | Sandboxed devcontainer for running Claude Code in bypass mode for security audits | Recorded alternative, not adopted. This host's isolation model is native worktrees plus the project's own sandbox/permission settings (`docs/linux-efficiency.md`); a devcontainer is a heavier, unqualified isolation boundary with no demonstrated gap the current model leaves open. | A task specifically requiring untrusted-code review under bypass mode where worktree isolation is insufficient. |
| [kenryu42/cc-safety-net](https://github.com/kenryu42/cc-safety-net/tree/3a3d24146101) (`main@3a3d24146101`, 2026-09-23) | Pre-execution guard blocking destructive git/filesystem commands and sensitive-file access across several agent CLIs | Recorded alternative, not adopted. This project runs `bypassPermissions` deliberately (per-user decision, `MEMORY.md` "Frictionless permissions") with its own RTK hook and gitleaks/zizmor checks; a second, unreviewed pre-execution guard would add an unqualified interception layer under an explicitly frictionless permission model. | A concrete destructive-command incident this project's existing checks did not catch, with a reviewed false-positive rate for cc-safety-net's own rules. |
| [dyoshikawa/rulesync](https://github.com/dyoshikawa/rulesync/tree/d3cf1caa8663) (`main@d3cf1caa8663`, 2026-09-22) | CLI to sync/generate rule files across multiple AI coding agents from one source | Not adopted. This project's canonical instructions already live in one place per harness (`CLAUDE.md`/`AGENTS.md`) with explicit precedence rules; introducing a generator with its own sync semantics is a process change with no demonstrated multi-agent drift problem here yet. | An observed drift between this project's Claude/Codex instruction files that manual editing failed to keep in sync more than once. |
| [Owloops/claude-powerline](https://github.com/Owloops/claude-powerline/tree/9e9b17f9c05b) (`main@9e9b17f9c05b`, 2026-09-23) | Vim-style powerline status line for Claude Code | Not adopted. This host's `statusLine` is already the pinned `claude-hud` plugin (`adoption/templates/claude.settings.template.json`); a second status-line implementation is redundant, not a capability gap. | A specific claude-hud limitation (e.g. missing signal) that claude-powerline demonstrably fixes. |
| [backnotprop/plannotator](https://github.com/backnotprop/plannotator/tree/dd340515d802) (`main@dd340515d802`, 2026-09-23) | Visual annotation/review tool for agent plans and diffs, with team sharing | Recorded alternative, not adopted. This project's review path is native (`evidence-reviewer`/`blind-judge` agents plus PR review), not a hosted visual annotation service; no demonstrated gap in the existing review path. | A task needing visual, shareable plan/diff annotation the native review agents and PR flow cannot provide. |
| [Piebald-AI/tweakcc](https://github.com/Piebald-AI/tweakcc/tree/b86c6685b942) (`main@b86c6685b942`, 2026-09-23) | Customizes Claude Code's system prompt, toolsets, themes and "unlocks private/unreleased features" | Not adopted, and flagged as a supply-chain/support risk. Modifying the shipped system prompt or unlocking undocumented features conflicts with this project's native-first, evidence-based posture (`docs/acceptance-evidence-policy.md`) and could silently invalidate `omitClaudeMd`/tool-allowlist guarantees the project's own agents rely on. | Never expected to be adopted for the coordinator/main session; a narrow, reviewed cosmetic-only use (e.g. theme only) would need its own isolated evaluation, not a default install. |
| [nizos/tdd-guard](https://github.com/nizos/tdd-guard/tree/2579ec1823fa) (`main@2579ec1823fa`, 2026-09-14) | Automated TDD enforcement hook for Claude Code (blocks non-test-first edits) | Recorded alternative, not adopted. This project's own validators/tests (`scripts/validate.py`, `python3 -m unittest`, per-task acceptance commands) already gate merges; a blocking TDD-order hook is a stricter workflow change not requested for this repository's mixed catalog/tooling content. | A specific code-quality regression this project's existing test-gating did not catch that strict TDD-order enforcement would have. |
| [github/spec-kit](https://github.com/github/spec-kit/tree/2ba6b7bf5406) (`main@2ba6b7bf5406`, 2026-09-23) | Spec-driven development toolkit (spec/plan/tasks templates and CLI) | Not adopted; missing rejection reason now recorded: this project's task records already function as its spec-driven artifact (`docs/tasks/<date>-<slug>.md`, one per bounded outcome, with acceptance commands and evidence), and adopting a second, differently-shaped spec format would fragment that existing convention rather than replace it with a demonstrated improvement. | A concrete case where the existing `docs/tasks/` convention failed to capture a requirement spec-kit's format would have caught. |
| [anthropics/claude-code-action](https://github.com/anthropics/claude-code-action/tree/46a42b432397) (`main@46a42b432397`, 2026-09-23) | Official Anthropic GitHub Action running Claude Code in CI (PR review, issue triage, etc.) | Deferred to a CI smoke test, not decided here. Official/maintained, so the adoption question is scoping (which workflows, which triggers, token scope) rather than a build-vs-buy comparison; a dry run in this repository's Actions before default-enabling for any workflow. | A green, scoped smoke-test run in this repository's own `.github/workflows/` naming exactly which trigger and permission scope it uses. |

`crawl4ai`, `Firecrawl`, `Docling` and `browser-use` remain recorded
alternatives from prior rounds, unchanged by this review.
