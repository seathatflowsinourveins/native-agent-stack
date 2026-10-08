# Command-center and lane skill picks — 2026-10-08

Select `hcom-agent-messaging`, `promptfoo-evals` and `loki` from their maintainers' own skill definitions for command-center and native lane work. CC item `task-ns2604-coop-20261008T080508Z`, foundation-finalize synthesis row 9, authorizes these three pins after row 4 reaches 16/16. The two outstanding native CodeQL operations have now passed; their private full-return receipts establish the prerequisite, independently of this source-selection change.

## Sources and applicability

The exact vendor skill bodies and immutable folder trees were verified on 2026-10-08. No skill body is copied or rewritten in this repository. The central manifest records the full source/tree/byte hashes and the existing lifecycle uses those pins.

| Skill | Maintainer source and immutable pin | Skill file | License | Description characters |
| --- | --- | --- | --- | ---: |
| `hcom-agent-messaging` | [aannoo/hcom@b2a7c192003e7fd67ed93265289e4ac36276f965](https://github.com/aannoo/hcom/tree/b2a7c192003e7fd67ed93265289e4ac36276f965), release `v0.7.28` | [`skills/hcom-agent-messaging/SKILL.md`](https://github.com/aannoo/hcom/blob/b2a7c192003e7fd67ed93265289e4ac36276f965/skills/hcom-agent-messaging/SKILL.md) | MIT, repository `LICENSE` | 153 |
| `promptfoo-evals` | [promptfoo/promptfoo@30949931ee90c963acd487e97828c9441db0bcd4](https://github.com/promptfoo/promptfoo/tree/30949931ee90c963acd487e97828c9441db0bcd4), release `0.124.0` | [`.claude/skills/promptfoo-evals/SKILL.md`](https://github.com/promptfoo/promptfoo/blob/30949931ee90c963acd487e97828c9441db0bcd4/.claude/skills/promptfoo-evals/SKILL.md) | MIT, repository `LICENSE` | 325 |
| `loki` | [grafana/skills@1ccacf29049fde66637fe01ab93a83a772da323b](https://github.com/grafana/skills/tree/1ccacf29049fde66637fe01ab93a83a772da323b) | [`skills/grafana-lgtm/loki/SKILL.md`](https://github.com/grafana/skills/blob/1ccacf29049fde66637fe01ab93a83a772da323b/skills/grafana-lgtm/loki/SKILL.md) | Apache-2.0, repository `LICENSE` and skill frontmatter | 412 |

Hcom covers native agent messaging setup and troubleshooting. Promptfoo covers ordinary evaluation suites and regression matrices, with adversarial red-team setup explicitly outside its description. Loki covers LogQL, log ingestion and log-pipeline troubleshooting. These are source-reviewed applicability claims. This change records no new skill invocation, parser/model run, performance improvement, marketplace scan or host installation.

The vendor definitions are selected directly instead of writing local procedures or adopting community copies of the same vendor workflows. `promql` remains deferred to the owner's listing-cap decision. Popularity and marketplace counts did not establish the selection. Marketplace audit verdicts are `Unknown`, with no fabricated scan date; their URLs are locators only.

## Listing check

Use the unchanged repository counter in [`scripts/skills_status.py`](../../scripts/skills_status.py), including its `budget_report` function, with [`adoption/skills/manifest.json`](../../adoption/skills/manifest.json). The character method remains parsed frontmatter description Unicode code points with surrounding whitespace stripped, as the manifest documents.

| Declared listing | Before | After | Change |
| --- | ---: | ---: | ---: |
| Claude on-listed descriptions | 9,484 | 10,374 | +890 |
| Codex enabled/catalog descriptions | 9,165 | 10,055 | +890 |
| Codex catalog skill count | 24 | 27 | +3 |

The three descriptions add `153 + 325 + 412 = 890` characters. The Claude manifest ceiling stays 10,500, leaving 126 characters. These are declared listing/counter results, including the manifest's existing held entries; they are separate from a client's observed listing, token usage or cache counters. An uninstalled skill remains uninstalled even when its pin fits this ceiling.

The checked-in Claude settings template adds the three `"on"` entries so its declarative overrides equal the manifest. The Codex template's comment counts 27 catalog-visible skills and points to the existing counter for the path-dependent render estimate; the configured 6,000-token budget is unchanged. These are repository templates for the later host step, not live client changes.

## Worker scope and installation

These picks serve the command center and native lanes. [`blueprints/runtime-workers/skills/manifest.json`](../../blueprints/runtime-workers/skills/manifest.json) explicitly excludes them from its current worker selection through the existing central-adoption contract. Its 134 selected skills, 13 sources, 25 reused adoption skills, coverage, budgets, roles and scenarios are preserved. The worker README's stale opening totals are corrected to those actual manifest totals. A later dated worker assignment can overturn an exclusion; this PR does not enlarge worker deployment grants or start wave-1 work.

After the PR lands, the designated host shell outside Claude installs the selected skills by [`adoption/skills/lifecycle.md`](../../adoption/skills/lifecycle.md) and the existing pinned Vercel Skills CLI route (`vercel-labs/skills@7407f3893ad4dceab546ac002c3ef806e4000c73`, v1.7.0), then retains native inspection and per-client invocation evidence. CC plan row 31 owns that later host step. Nothing is installed by this PR. The paper-runtime lock freeze and the 10:35–13:45Z quiet window remain in force.

Promptfoo's skill includes `npx promptfoo` examples. A skill pin does not pin npm resolution: later host checks use the already installed pinned promptfoo 0.124.0 executable instead of silently acquiring npm latest. Hcom and Loki likewise use their existing native component bindings; the skill definition does not install or qualify a component.

## Validation, inverse and overturn

The repository counter and manifest/worker contract checks verify the pin/listing declarations. `python3 scripts/validate.py` is the required final repository check before publication. These are local structural/integration checks, not upstream skill acceptance. Host installation and use remain unmeasured by this PR.

Correction from the first focused check: the initial source review said the templates needed no update. The unchanged manifest/worker tests ran 55 checks with 53 passing and two failing: `ListingBudgetTemplateTests.test_codex_template_comment_counts_the_skills_the_catalog_shows` and `TemplateSkillOverridesConsistencyTests.test_skill_overrides_equals_name_to_claude_listing`. Their concrete requirements are the count comment and override map above. The failed conditions are retained here; a pin-only edit does not keep those existing projections consistent.

The first hosted validation at `0a243fcadf5ecb65cbb059290d24e3c11a2a8f9f` exposed 16 further assertions across four shards ([run 37752245767](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/37752245767)). Three source/task entries were missing from the skills-lifecycle landscape, two existing count expectations still said 24, and the shifted manifest citation needed line 866. Those projections now follow the same selection; the equality checks are retained.

The other eleven assertions exposed a namespace collision: the client renderer's text scan treated `/skillOverrides/loki` as a reference to an unwired Loki service. The existing renderer now distinguishes native skill identifier keys from service references when scanning `settings.json`; it keeps override values and all other fields in the scan and does not modify the rendered configuration or declare Loki wired. The repository render reproducer and a regression at that same render boundary failed before this correction. Controls confirm that an actual Loki endpoint, MCP server or value still fails. The generic text scanner's whole-word/case behavior is unchanged.

The reversible metadata inverse is to revert this pin commit, including its budget sums and worker exclusions. Any later host uninstall follows the existing lifecycle's retirement/removal procedure and its retained installation receipt; a metadata revert alone is not a host cleanup claim.

Replace a pin when the maintainer changes the skill's own folder and primary-source review plus the applicable native check supports the replacement. Revisit a selection if a documented lane task needs a better-evidenced workflow or the owner's cap decision admits `promql`. No new approval rule or evaluation runner is introduced here.
