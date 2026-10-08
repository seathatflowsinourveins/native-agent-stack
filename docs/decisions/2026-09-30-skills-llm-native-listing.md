# Decision: every model-invocable skill listed in full for Claude and enabled for Codex (2026-09-30)

**Decision context:** expose every model-invocable skill through [Claude's skill visibility settings](https://code.claude.com/docs/en/skills#override-skill-visibility-from-settings)
and [Codex's native catalog/config](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/config/src/skills_config.rs). Carried out on 2026-09-30 as unit F3 of coordinator session `native-agent-stack-c5`, on
branch `claude/sota-defaults-f3-20260930` from `origin/main@e45328d3`, rebuilt on `origin/main@11227bfd`. The branch
is opened for review and merged with the Gate A owner's batch. Skill discovery, selection, installation, invocation,
verification, update and withdrawal follow the lifecycle guide and [Vercel Skills CLI 1.7.0](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/cli.ts).
The 2026-09-30 scope includes task-based landscape research across skill sources, with model invocation bounded by
each upstream skill's declared eligibility and the two clients' actual catalog exposure.

**Scope:** `adoption/skills/manifest.json`, the skill keys of the two client templates
(`adoption/templates/claude.settings.template.json` `skillOverrides`, `skillListingBudgetFraction` and the Skills CLI
rules of `permissions.deny`; `adoption/templates/codex.config.template.toml` `[skills]`), the runtime-worker skills
manifest with the two tables its tests mirror, the [lifecycle guide](../../adoption/skills/lifecycle.md), the attributed
[native skill lifecycle record](2026-09-30-native-skill-lifecycle.md) with its evidence, the
[re-pin verification output](../../evidence/artifacts/skills-pin-verification-20260930/pin-verification.json), the
[skills-trial record](2026-09-25-skills-trial-and-usage.md)'s 2026-09-30 addendum, and their tests.
Nothing is installed or applied on a host by this change. The host batch runs the installer, the settings apply and
the Codex config step (see the addendum's host steps).

**#381 interaction:** applied on a host, this change alters the practice that the sealed #381 token-adoption E2E
measures ([preregistration](../../evidence/artifacts/token-adoption-e2e-20260926/preregistration.json)).

- Codex arms B and A read the user configuration, so they go from 11 to 25 visible skills. Arm N ignores it
  (`--ignore-user-config`, the [N shape](../../examples/codex-native/README.md)) and, by the Gate A owner's count,
  already saw 26. The 14 skills new to B and A include `agent-browser`, `semgrep`, `codeql`, `security-audit` and
  `find-skills`.
- M4 and M8 are arm-B thresholds. M4 needs at least 90% of remote fetches routed, and 5 of the fetch lane's 10 arm-B
  opportunities are the Codex web-table tasks (`seed-codex-web-table-1..5`). M8 needs at least 80% correct lane use per
  required lane, and 2 of the symbol-references lane's 9 arm-B opportunities (1 of the ai-memory lane's 7) are Codex
  tasks.
- A call diverted to a newly visible skill could miss either threshold. The B-versus-A gates cannot see it, because A
  changes the same way.
- The applied Claude settings are frozen values too: `claude.settings.user.sha256` and `permissions_deny_count`
  ([token-e2e](../../tools/token-e2e/README.md)).
- Gate A's frozen inputs and M4/M8 thresholds require its separate amendment before a host applies these catalog changes.

## Context

At `e45328d3` the manifest held 28 skills:

- 20 were listed `on`.
- 5 were `name-only`: `agent-browser`, `iterative-retrieval`, `search-first`, `security-audit` and `typesafe-ai`.
- 3 were `user-invocable-only`: `find-skills`, `grill-me` and `improve-codebase-architecture`.
- 17 were disabled for Codex.

Upstream defines those states from the model's side:

- `"name-only"`: "Claude sees the skill by name without its description" (settings reference, `skillOverrides`).
  Where Claude Code drops a description for budget, Claude "can still invoke those skills but is less likely to choose
  one on its own" (settings reference, `skillListingBudgetFraction`). That second statement is about budget drops, not
  `name-only`; it is the nearest documented effect.
- `"user-invocable-only"`: "Claude doesn't see the skill, but you can still type `/name`" (settings reference).
- A Codex `[[skills.config]]` table with `enabled = false` removes the skill from Codex. Its only other state is
  enabled.

Only the user could start 3 skills, the model could not see the descriptions of 5, and Codex could not use 17. The
selected native catalogs expose eligible skills with descriptions, while respecting upstream user-only declarations.

Two skills are user-only by upstream design. `grill-me` and `improve-codebase-architecture` set
`disable-model-invocation: true` in their SKILL.md frontmatter at `mattpocock/skills@c55ee46`, and their
`agents/openai.yaml` sets `allow_implicit_invocation: false`. For Claude, that frontmatter means "Only you can invoke
the skill" (skills page). Codex marks such a skill `hidden_from_prompt()`, so only an explicit `$name` runs it
(`codex-rs/ext/skills/src/provider/host.rs` L147-148 at `rust-v0.157.1`).

The listing budget constrains the change:

- **Claude Code.** The budget "scales at 1% of the model's context window" (skills page). The env-vars reference gives
  "a fallback of 8,000 characters" and each entry is cut at 1,536 characters. "When the listing overflows, Claude Code
  drops descriptions starting with the skills you invoke least." The 26 model-invocable skills' descriptions total
  9,755 characters, over that fallback before names, bundled skills or plugin skills are counted.
- **Codex.** Unset, the catalog budget is 2% of the model context window, which is 5,440 tokens for `gpt-6-astra`'s
  272,000-token window in `models-manager/models.json`. The 8,000-character figure applies only when the window is
  unknown. A set `[skills] max_context_tokens` is capped at 10,000 tokens (`codex-rs/ext/skills/src/render.rs` L17-20
  and L123-149).

The manifest had carried Codex's 8,000 as `codex_default_budget_chars`, which is the fallback, not the default, and
`scripts/skills_status.py` measured the Codex-enabled description characters against it.

`skill-creator` was excluded as a duplicate of the synced `anthropic-skills:skill-creator` and Codex's
`.system/skill-creator`. The sync ended on 2026-09-26 ([skills-trial record](2026-09-25-skills-trial-and-usage.md),
L360-415), so Claude had no skill-creator left. Codex still ships one: `codex-rs/skills/src/lib.rs` L55-69 installs
`src/assets/samples` into `CODEX_HOME/skills/.system`, `skill-creator` included.

## Alternatives

1. **Keep the 2026-09-26 and 2026-09-28 states.** Rejected: they prioritize reduced listing context over the selected native
   description exposure. The trial kept deliberate-invocation and long-description skills `name-only`, and `find-skills`,
   `grill-me` and `improve-codebase-architecture` `user-invocable-only`. Either state leaves the choice to the user or
   to a name without its description.
2. **Fork or locally edit the two upstream user-only skills** to drop `disable-model-invocation`. Rejected on three
   grounds:
   - The installer takes a pin as is. `tools/adoption/install_skills.py` counts an installed SKILL.md as current only
     when its sha256 matches the pin, and rolls back an add that does not match. A local frontmatter edit therefore
     breaks the pin (the skills-trial record's 2026-09-27 addendum, **Enforcement residual**).
   - Upstream marks both as user-triggered on purpose.
   - A model-invocable replacement comes from the skills sweep (unit D1), qualified by a paired with/without-skill
     benchmark (unit D2).
3. **A fixed `SLASH_COMMAND_TOOL_CHAR_BUDGET`.** Rejected: it sets "a fixed character count" (skills page) that does not
   scale with the window. The settings key is the documented fraction, and the template never sets both.
4. **Keep the default 1% and demote only low-priority entries to `name-only`** (the skills page's other remedy).
   Rejected: that hides descriptions the native selection depends on. The documented fraction is set high now and lowered after
   measurement (see Decision, point 5).
5. **Codex `skill-creator`:**
   - (a) **Enable the pinned copy as well.** Codex dedupes skills by SKILL.md path only
     (`ext/skills/src/loader/host_merge.rs` L232-233), so two entries named `skill-creator` would list. It would also
     leave no manifest skill disabled for Codex, which `tests/test_install_skills.py` `ReuseRefGateTests` needs.
   - (b) **Disable it by name.** Rejected: a name rule disables every loaded skill of that name
     (`codex-rs/config/src/skills_config.rs` L109-119), so it would hide Codex's own `.system/skill-creator` as well.
   - (c) **Disable the installed copy by path.** Chosen (Decision, point 3): a path rule disables only the skill whose
     canonical `SKILL.md` it names.

## Decision

1. **Claude listing.**
   - Every manifest skill without upstream `disable-model-invocation` is `on`: the 25 that remain after the retirement
     in point 8 and `skill-creator`, 26 in all. `tests/test_skills_manifest.py` `LlmNativeListingTests` holds that
     rule.
   - `grill-me` and `improve-codebase-architecture` stay `user-invocable-only`. Their gap texts say so, citing the
     upstream frontmatter, with replacement pending unit D1 and unit D2.
   - The template's `skillOverrides` mirrors the manifest.
2. **Codex.**
   - All 27 remaining skills are enabled, 16 of them newly; the retired `resolving-merge-conflicts` was the 17th.
   - For `grill-me` and `improve-codebase-architecture` this restores an explicit `$name` only, which is the upstream
     policy.
3. **`skill-creator` re-admitted** from `anthropics/skills@8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4`, that repository's
   HEAD on 2026-09-29.
   - Tree `3cf9a8db32597ba3e24b584a3d696f4e11c7d7b6`; SKILL.md 33,168 bytes, sha256
     `dcd4803e61e913e6fc27294184cd3a71f09f5e924ff20c8a9a20173e7b3c2bcf`. Both are identical at `33375500`.
   - Description 319 characters (PyYAML 6.0.3); per-skill Apache-2.0 `LICENSE.txt`.
   - skills.sh labels: Gen Agent Trust Hub Pass, Socket Warn, Snyk Pass. The raw audit API reads Socket risk
     `critical`, 1 alert: a LOW Anomaly in `eval-viewer/viewer.html`. Rule 3 reads the labels, and a Warn is not a Fail.
   - It is `on` for Claude and disabled for Codex, which ships `.system/skill-creator`.
   - `excluded[]` keeps only the `openai/skills` copy, still Gen Agent Trust Hub Fail on 2026-09-30.
   - **Disabled by path, not by name.** The embedded Codex copy is also named `skill-creator`
     (`samples/skill-creator/SKILL.md` L2), and a name selector disables every loaded skill of that name
     (`codex-rs/config/src/skills_config.rs` L109-119). `install_skills.py --print-codex-config` therefore prints a
     path-keyed table, `path = "<home>/.agents/skills/skill-creator/SKILL.md"` with `enabled = false`, which Codex
     matches against each loaded skill's canonical `path_to_skills_md` (`host_service.rs` L366-371, `host_outcome.rs`
     L52-54). A global install leaves the Codex copy only in that canonical folder (skills CLI `src/installer.ts`
     L392-402), which Codex loads from `$HOME/.agents/skills` (`host_roots.rs` L103-108).
   - `scripts/skills_status.py` accepts that table and fails a name-keyed `skill-creator` table as hiding Codex's own
     copy. The project-scoped runtime-worker manifest prints only with `--project-dir`, whose installed paths the
     tables name.
4. **`find-skills`** becomes model-invoked registry discovery.
   - Its install-count and star thresholds guide discovery only. `AGENTS.md:3` says stars, installs and popularity are
     not evidence.
   - Its `npx skills add … -g -y` step is replaced by a pin in this manifest. A session never installs a skill ad hoc;
     it records the candidate and the coordinator pins it.
   - The settings template enforces that for the spellings a model writes. Its `bypassPermissions` default denied
     neither step 6 nor the body's `npx skills update` (L28-29, L90, L100). 41 `Bash(...)` deny rules now cover every
     Skills CLI command that writes installed skills (skills 1.7.0 `src/cli.ts` L336-402: `add`, `a`, `i`, `install`,
     `remove`, `rm`, `r`, `check`, `update`, `upgrade` and `experimental_*`).
     Round 4 (the owner's decision, 2026-09-30): the three bare-form verb rules end in `<word>*` so that Context Mode's
     plain-regex matcher (mksglu/context-mode 1.0.169, `evaluateCommandDenyOnly`) denies the bare `skills update`,
     `check` and `upgrade` on its `ctx_execute` path too; the short aliases keep ` *` because `skills init` is legitimate.
     A leading assignment is still not stripped there.
   - The rules take four forms: a bare `skills`, `npx [flags] skills`, `npx [flags] skills@<version>` and a path
     ending in `bin/skills`. The versioned form leaves out the one-letter aliases, which are common query words.
     `Edit(~/.agents/**)` keeps the file tools out of the canonical skill folders.
   - `find`, `list`, `init`, `use` and `--version` stay allowed. `install_skills.py`'s own `add` and rollback `remove`
     are subprocesses, which Bash rules do not see.
   - The rules match command text, not every route to the program: `"$SKILLS_BIN" add` or `sh -c` is not matched
     (permissions page, L237-251). `tests/test_install_claude_profile.py` checks the rules and samples of blocked and
     allowed command lines.
5. **Budgets.**
   - The manifest's own cap on the `on`-listed sum moves from 8,000 to 10,500 characters. The sum moves from 7,184 to
     10,191: the 25 remaining model-invocable descriptions (9,872 characters, `search-first` now 328) plus
     `skill-creator`'s 319.
   - The Codex-enabled sum moves from 2,829 to 10,048. Codex hides the two upstream user-only skills from its catalog,
     so 9,872 of those characters reach it.
   - The Claude template sets `skillListingBudgetFraction: 0.05`. That is five times the 1% default. On a
     200,000-token window it reserves 10,000 tokens, where 1% gives 2,000.
   - The 1% default and the 8,000-character fallback agree at about 4 characters per token (2,000 tokens against 8,000
     characters). That ratio is an inference from the two documented figures, not a documented rate. By it, 5% is about
     40,000 characters, about four times the 10,191 (3.9). On a 1,000,000-token window, 1% is already 10,000 tokens,
     about 40,000 characters, and 5% is about 200,000.
   - The measurement plan in the addendum lowers the fraction to the smallest value that shows no overflow warning.
   - The Codex template sets `[skills] max_context_tokens = 6000`. That fixes the catalog budget above the 5,440-token
     default of `gpt-6-astra` and `gpt-6.1-sol` (both a 272,000-token `context_window` at `rust-v0.159.2`) and makes it
     independent of a child's model.
   - The 25 catalog-visible skills render to 11,904 bytes with a 28-character skills root. `render.rs` charges each line
     and its newline at ceil(bytes / 4) (L154-160 and L25 at `rust-v0.159.2`; line format L258-267), 2,987 tokens in
     all, under half the configured 6,000. The 26 visible before the fold rendered to 11,889 bytes.
   - The manifest records `codex_configured_budget_tokens` (6,000, kept equal to the template by
     `tests/test_skills_manifest.py`), `codex_catalog_description_chars` (9,872) and `codex_fallback_budget_chars`
     (8,000, metadata only), which replaces `codex_default_budget_chars`; `upstream_allow_implicit_invocation: false`
     marks the two skills Codex keeps to an explicit `$name`. `scripts/skills_status.py` estimates the catalog the same
     way from the manifest and compares the estimate with the configured budget. It counts `description_chars` as the
     description's bytes; four descriptions carry one 3-byte character each, so it reports 2,985 tokens for the root
     above. `budget.client_budgets` records the labels.
6. **Prune rule.**
   - Zero use no longer demotes a listing: the review keeps a zero-use trial skill or removes it through a dated
     decision record.
   - Kept winners change status only through a verdict re-record, and their listing only through a dated decision
     record, as here.
7. **Runtime workers.** `blueprints/runtime-workers/skills/manifest.json` follows main:
   - `security-audit`'s exclusion met its overturn condition and became a `reuse_ref` entry (scenario `security`,
     roles `coding` and `orchestration`).
   - Its `skill-creator` became a `reuse_ref` at main's pin.
8. **Same-day source review and one lifecycle document.** A source review of the selected skills came from
   pre-existing uncommitted changes observed in the main checkout; original author not established (snapshot r2,
   `tracked.diff` sha256 `314bd1b260da0939`). The fold briefs' earlier attribution to the Codex coordinator lane rested
   on a process census of file writes, which does not establish document authorship, and the lane concerned asked for
   this neutral wording. This branch folds the review and keeps the
   [native skill lifecycle record](2026-09-30-native-skill-lifecycle.md) as its record.
   - Six re-pins, each re-verified from a blobless clone of its source repository: `search-first` to
     `affaan-m/ECC@c70874fa`; `diagnosing-bugs`, `tdd`, `codebase-design` and `improve-codebase-architecture` to
     `mattpocock/skills@d81f3a18`; `semgrep` to `trailofbits/skills@82fe8226`. All 28 selected pins match their
     upstream tree, SKILL.md hash, size, description length and invocation flag, and every selected path is unchanged
     at its repository's HEAD on 2026-09-30.
   - The checker's output is retained as
     [`pin-verification.json`](../../evidence/artifacts/skills-pin-verification-20260930/pin-verification.json): one
     row per skill, `skill-creator` and the six re-pins included, from the 18:02Z run. A recheck at 22:53Z, after a
     fresh fetch with every remote HEAD confirmed by `git ls-remote`, returned byte-identical output: 28 passes.
   - `resolving-merge-conflicts` is retired: upstream removed it in `daa01d8` (2026-09-24). It moves to `excluded[]`
     with a dated `retired` marker; the template keeps it `"off"` so the deep merge cannot leave a host's earlier
     `"on"`; the runtime-worker manifest drops its entry and coverage selections.
   - [`adoption/skills/lifecycle.md`](../../adoption/skills/lifecycle.md) is the single lifecycle document for both
     clients. A task finds its skill in this order: the listed skills, then `search-first`, then `find-skills` registry
     discovery, then the landscape sweep; only a selected winner is pinned. It also covers pinning, installation,
     per-client invocation, the listing budget, updates, recovery and retirement.
9. **#381 interaction.** The Gate A owner decided three things for the sealed #381 measurement:
   - Amendment 4 names the skill catalog as part of the measured practice.
   - No threshold is loosened.
   - A call diverted to a newly visible skill is reported and never reclassified.

   This change adds two guards of its own. The deny rules of point 4 keep a session from installing or removing a
   skill during a run. The addendum's budget-fraction measurement stays outside #381 window W, and a template change
   after the Amendment 4 seal re-seals.

## Overturn condition

- **Listing overflow at 200k.** Suppose a `claude --debug -p ok --model sonnet` run on a 200,000-token model shows the
  listing-over-budget warning with the template's fraction. Then raise the fraction or trim through the manifest,
  template and budget together. Suppose instead the measurement ladder in the addendum finds a lower fraction without
  the warning at 200k. Then lower the template to that value.
- **Measured proactive invocation.** Suppose `/skill-doctor` and `tools/skill-usage` counts over a skill's clean `on`
  window show no model-initiated use, while its listing cost is measured, or a misfire costs a turn. Then the review
  keeps or removes that skill through a dated record. A move back to `name-only` or `user-invocable-only` needs an explicit
  selection amendment, rather than treating reduced listing cost alone as permission to change model exposure.
- **Client or pin change:**
  - a Claude Code release changes the listing budget, the `skillOverrides` states or the absent-key default;
  - Codex changes its catalog budget or `allow_implicit_invocation`;
  - a new pin changes a description or adds `disable-model-invocation`.
- **Codex selector semantics.** A Codex release changes how a `[[skills.config]]` path or name rule matches
  (`skills_config.rs` L94-125), where it loads user skills from, or which bundled skills it ships. Then change the
  installer's table form and `scripts/skills_status.py`'s `CODEX_BUNDLED_SKILL_NAMES` together.
- **Upstream user-only skills.** An upstream revision of `grill-me` or `improve-codebase-architecture` drops
  `disable-model-invocation`, or unit D1/D2 qualifies a model-invocable replacement. Then re-pin or replace it through
  the manifest.
- **Upstream drift or removal.** A selected skill's tree changes at its repository's HEAD, or upstream removes it. Then
  review the change and re-pin, or retire it, through the lifecycle guide. `resolving-merge-conflicts` returns only if
  upstream restores a maintained directory that passes a new source review and activation check.
- **Skills CLI commands or rule matching.** A Skills CLI release adds or renames a command that writes installed
  skills, or Claude Code changes how a `Bash(...)` rule matches. Then change the template's rules and
  `test_a_session_cannot_install_or_remove_skills_through_the_skills_cli` together.

## Sources

Read 2026-09-30 unless dated otherwise. Page hashes are of the fetched markdown.

- Claude Code settings reference, <https://code.claude.com/docs/en/settings-reference> (sha256 `18498a9b…`):
  `skillListingBudgetFraction` (L2944-2958: default `0.01`, "a fraction greater than `0` and at most `1`"),
  `skillListingMaxDescChars` (L2960-2974, default `1536`) and `skillOverrides` (L4196-4221).
- Claude Code skills page, <https://code.claude.com/docs/en/skills> (sha256 `4356e382…`):
  - the invocation table (L538-544) and `disable-model-invocation` (L376, L515);
  - the `skillOverrides` visibility table (L819-851);
  - "Skill descriptions are cut short" (L1117-1125): 1% scaling, least-invoked descriptions dropped first, the
    `--debug` warning, the `/context` Skills row and the fraction or env-var remedy.
- Claude Code env-vars reference, <https://code.claude.com/docs/en/env-vars> (sha256 `d797d591…`),
  `SLASH_COMMAND_TOOL_CHAR_BUDGET` (L486): "The budget scales dynamically at 1% of the context window, with a fallback
  of 8,000 characters".
- `openai/codex` at tag `rust-v0.157.1`:
  - `codex-rs/core/config.schema.json` L3961-3985 (`SkillsConfig.max_context_tokens`: "Defaults to 2% of the model
    context window and is capped at 10,000 tokens when set"; file sha256 `17fbda7e…`);
  - `codex-rs/ext/skills/src/render.rs` L17-25 and L123-149;
  - `codex-rs/ext/skills/src/provider/host.rs` L144-148;
  - `codex-rs/skills/src/model.rs` L23-28;
  - `codex-rs/config/src/skills_config.rs` L70-125;
  - `codex-rs/ext/skills/src/host_service.rs` L366-370 (a rule matches each loaded skill's name or `path_to_skills_md`);
  - `codex-rs/ext/skills/src/loader/host_merge.rs` L232-233;
  - `codex-rs/skills/src/lib.rs` L55-69;
  - `codex-rs/skills/src/assets/samples/skill-creator/SKILL.md` L1-5;
  - `codex-rs/models-manager/models.json` (`gpt-6-astra`: `context_window` 272000).
- `anthropics/skills`:
  - `gh api repos/anthropics/skills/commits/HEAD`: `8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4`,
    2026-09-29T02:20:03Z;
  - `contents/skills?ref=8a1541c4…`: `skill-creator` tree `3cf9a8db…`, the same as at `33375500`;
  - SKILL.md raw bytes hashed locally at both refs.
- `mattpocock/skills@c55ee46073ed923f86ce59a5eb3b6d895095d1b7`: `skills/productivity/grill-me` and
  `skills/engineering/improve-codebase-architecture`, SKILL.md frontmatter and `agents/openai.yaml`.
- `vercel-labs/skills@7407f3893ad4dceab546ac002c3ef806e4000c73` `skills/find-skills/SKILL.md` L35-103 (sha256
  `c00eeea0…`, equal to the manifest pin).
- `cloudflare/security-audit-skill@c1c8a8c1471069fb0e188eeaff69b8e8db6564a8` `skills/security-audit/SKILL.md` L3, L12
  and L172-175 (sha256 `5e3e96a1…`, equal to the manifest pin). The tree is untruncated, and the folder is `ccbc33ed…`.
- skills.sh:
  - `anthropics/skills/skill-creator` (page sha256 `e70389cc…`; Socket detail: 1 LOW Anomaly,
    `eval-viewer/viewer.html`);
  - `openai/skills/skill-creator` (Gen Agent Trust Hub Fail);
  - the audit API `https://add-skill.vercel.sh/audit?source=<owner/repo>&skills=skill-creator` for both.
- Rebuild on `11227bfd`, read 2026-09-30:
  - blobless clones (`git clone --filter=blob:none --no-checkout`) of `typesafe-ai/skills`, `openai/skills`,
    `affaan-m/ECC`, `mattpocock/skills`, `trailofbits/skills`, `anthropics/skills`, `vercel-labs/agent-browser`,
    `vercel-labs/skills` and `cloudflare/security-audit-skill`: every pin's tree (`git rev-parse <ref>:<path>`),
    SKILL.md sha256 and bytes, PyYAML description and `disable-model-invocation`, ancestry to `origin/HEAD`, and the
    path's tree at `origin/HEAD`;
  - `mattpocock/skills` `daa01d8` ("Remove resolving-merge-conflicts", 2026-09-24) and
    `.changeset/remove-resolving-merge-conflicts.md` at `d81f3a18`; `trailofbits/skills` `82fe822` (semgrep
    `--max-target-bytes` and the oversized report);
  - `openai/codex` at `rust-v0.159.2` (shallow blobless fetch): `codex-rs/ext/skills/src/render.rs` L19-27, L126-152 and
    L241-266, `codex-rs/core/config.schema.json` L4122-4127, `codex-rs/models-manager/models.json` (`gpt-6-astra` and
    `gpt-6.1-sol` `context_window` 272000); `skills_config.rs`, `provider/host.rs` and `skills/src/lib.rs` are
    byte-identical to `rust-v0.157.1`;
  - `vercel-labs/skills` v1.7.0 (`7407f389`, the newest tag; npm `latest` 1.7.0): `src/cli.ts` L394-401,
    `src/list.ts` L60-62, `src/remove.ts` L409-411;
  - <https://developers.openai.com/codex/skills> (sha256 `d1579156…`; L129, L172-173, L180-185 and L215: automatic
    detection with restart fallback, `[[skills.config]]`, `allow_implicit_invocation`) and the Claude skills page as
    fetched then (sha256 `adc20053…`; L290-294: watcher, `/reload-skills`, `/reload-plugins`).
- Review repair for PR #553, read 2026-09-30:
  - `openai/codex` at `rust-v0.159.2` (commit `ff6aec96`, blobless clone): `codex-rs/config/src/skills_config.rs`
    L70-125 (a name rule selects every loaded skill of the name, a path rule one canonical document path) and L150-210
    (rules only from the user and session-flag layers; an entry with both selectors, neither or a blank name is
    ignored; a name is trimmed); `codex-rs/ext/skills/src/host_service.rs` L366-371 and `host_outcome.rs` L52-54
    (`path_to_skills_md` is the matched path); `host_roots.rs` L95-113 (`$CODEX_HOME/skills`, `$HOME/.agents/skills`
    and the `.system` cache as user and system roots); `loader/host.rs` L192-196 (skill paths canonicalized);
    `codex-rs/utils/absolute-path/src/lib.rs` L28-58 and L392-406 with `absolutize.rs` L22-45 (`~` expansion, the
    base folder, lexical normalization); `codex-rs/config/src/loader/mod.rs` L573-582 and L1424-1447 (a layer's
    paths resolve against its config folder); `codex-rs/core/config.schema.json` L4082-4105 (`SkillConfig`: `enabled`
    required, `name` and `path`); `codex-rs/skills/src/lib.rs` L55-67 and `src/assets/samples/` (bundled `imagegen`,
    `openai-docs`, `review-agent`, `skill-creator` and `skill-installer`; `rust-v0.157.1` also ships
    `plugin-creator`); `codex-rs/ext/skills/src/render.rs` L154-160, L258-267 and L1158-1174, `catalog.rs` L261-263,
    `provider/host.rs` L129-149, `codex-rs/skills/src/model.rs` L22-28 and `codex-rs/utils/string/src/truncate.rs`
    L71-74 (the catalog line, its token charge and the implicit-invocation default);
  - the same Codex skills page, L180-186: `[[skills.config]]` with `path = "/path/to/skill/SKILL.md"` and
    `enabled = false`;
  - `vercel-labs/skills@7407f389`: `src/agents.ts` L224-232 and L907-912 (Codex is a universal agent) and
    `src/installer.ts` L128-131, L151-159 and L392-402 (a global install leaves it only the canonical
    `~/.agents/skills/<name>`);
  - each pin's `agents/openai.yaml` in the blobless clones: `policy.allow_implicit_invocation: false` only for
    `grill-me` and `improve-codebase-architecture`; four descriptions (`property-based-testing`, `sarif-parsing`,
    `fp-check`, `variant-analysis`) carry one em dash each.
- Repository: `tools/adoption/install_skills.py` (`print_codex_config` and the `--print-codex-config` branch of
  `main`), `scripts/skills_status.py` (`CODEX_BUNDLED_SKILL_NAMES`, `check_codex_disable`, `codex_catalog_tokens` and
  `budget_report`), `tools/adoption/apply_claude_settings.py` L141-177, and the
  [skills-trial record](2026-09-25-skills-trial-and-usage.md) L360-415, L444-449 and L1128-1166.
- The Gate A owner's review of PR #553 at `d6041854` (2026-09-30), read against:
  - [`evidence/artifacts/token-adoption-e2e-20260926/preregistration.json`](../../evidence/artifacts/token-adoption-e2e-20260926/preregistration.json):
    `thresholds.M4` (`routed_fetch_rate_gte` 0.9) and `thresholds.M8` (`correct_lane_use_rate_gte` 0.8,
    `per_required_lane`), `arm_b_opportunity_counts` (fetch 10, symbol-references 9, ai-memory 7) and each task's
    `family`, `arms` and `lane_tags`;
  - `examples/codex-native/README.md` L169 (arm N's `--ignore-user-config`) and `tools/token-e2e/README.md` L84-85
    (the frozen settings values);
  - `adoption/skills/manifest.json` at `origin/main@29458b43` against this branch: 11 and 25 Codex skills in the
    catalog, 14 of them new.
- Claude Code permissions page, <https://code.claude.com/docs/en/permissions> (sha256 `8691dd40…`): "Wildcard patterns"
  (L138-183), "Compound commands" (L211-221, deny rules apply to any subcommand), "Wrappers" (L223-235: `npx` is not
  stripped, and a deny rule matches past any leading assignment), "What a Bash rule doesn't match" (L237-251), "Read
  and Edit" (L325-337) and "Symlinks" (L429-457).
- `vercel-labs/skills@7407f389`: `src/cli.ts` L336-402 (the commands and their aliases) and
  `skills/find-skills/SKILL.md` L28-29, L90 and L100 (`npx skills add`, `npx skills update`).
