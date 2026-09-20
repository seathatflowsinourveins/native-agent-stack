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
locations. The coordinator separately reported successful installation of these
two exact files as shared user skills, matching both hashes below, with Claude
symlinks added and project copies preserved. Native runtime discovery remains
pending independent review. Installation/discovery results belong in their own
receipt; this source review did not install or execute a new native task.

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
