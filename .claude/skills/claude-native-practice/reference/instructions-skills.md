# Instructions and skills (`instructions-skills`)

Client 2.1.295, checked 2026-10-09. Index: [slots.md](slots.md).

## skills-library

**Status:** default. **Default:** Native Agent Skills at personal scope, filled from the pinned vendor manifest (adoption/skills/manifest.json) and governed by `skillOverrides`, `skillListingBudgetFraction` and `/skill-doctor`

- **Route:** Claude Code discovers nested `<subdir>/.claude/skills` (at start or lazily) and names clashes `<dir>:<name>`; Codex reads `<dir>/.agents/skills` only from the project root down to its working directory
- **Alternatives, ranked:** 1. anthropics/claude-plugins-official; 2. anthropics/skills content (a blinded comparison is owed before any re-rule); 3. `claude plugin init` skills-dir plugins
- **Rejected:** `syncClaudeAiSkills: true` (synced skills bypass the pinned manifest); Packaging our own skills and agents as marketplace plugins (R56); github/awesome-copilot as a library; obra/superpowers process skills (excluded in the manifest)
- **Evidence:** skills.md 'Choose where skills load'; skills-I1, skills-I2 (inline-verified); CHANGELOG L7339 (2.1.6), L4303 and L4313 (2.1.178)
- **Notes:** Adjudicated: the native mechanism with the pinned manifest stands; the refuter upheld it. Owed: paired with/without runs per manifest skill on our tasks.
- **Supersedes:** M9 (judge still defaults to haiku); M23 (disable-model-invocation documented)
- **Overturn when:** A paired with/without run shows a manifest skill lowering quality, or a blinded comparison shows another library ahead.

## plugin-marketplaces

**Status:** default (scoped). **Default:** Native marketplaces with commit-pinned plugin sources (plugin-level `sha`), the official marketplace first

- **Route:** A catalog-owned marketplace.json with sha-pinned entries; a sha pin holds while the commit stays reachable; marketplace sources take a `ref`, never a `sha`
- **Alternatives, ranked:** 1. Publisher marketplaces pinned by tag (current state)
- **Rejected:** Packaging our own agents and skills as plugins; Managed marketplace allowlists on this host
- **Evidence:** plugin-marketplaces reference (sha on plugin sources); plugins-marketplaces-O7, O8, O9
- **Notes:** Our marketplaces use tags or no ref (context-mode, worktrunk, codex). codex 0.162.0 now ships the review capability codex-plugin-cc bridged: trial owed (currency).
- **Supersedes:** M8 answered (no sha on marketplace sources); R56 reaffirmed
- **Overturn when:** A release adds sha pins to marketplace sources, or a pinned commit becomes unreachable.

## output-styles

**Status:** default (scoped). **Default:** Built-in Default output style in the repository templates

- **Route:** The owner's primary checkout sets `Concise` in its untracked settings.local.json: an owner choice, not a repository default
- **Alternatives, ranked:** 1. Built-in Concise style (pending M19's paired run)
- **Rejected:** Explanatory and learning style plugins as defaults; Terse-output prompt packs
- **Evidence:** output-styles.md; output-styles-O8, O9
- **Notes:** The dispositions catalog marks Concise 'declined' without a measurement; it should read 'not measured, pending M19'.
- **Supersedes:** M19 (runs on 2.1.295)
- **Overturn when:** M19's paired run shows Concise at quality parity with a measured saving.

## commands

**Status:** default. **Default:** Skills (`SKILL.md`) as the only surface for custom slash commands

- **Route:** `.claude/commands` still works, but a skill wins a name clash; a model-invocable skill named `verify` is run before commits since 2.1.286 (#814)
- **Alternatives, ranked:** 1. `.claude/commands` files; 2. Plugin commands
- **Rejected:** SuperClaude command packs; claude-code-templates command packs
- **Evidence:** skills.md 'Custom commands have been merged into skills'; skills-O9 (2.1.286 verify)
- **Overturn when:** A release separates commands from skills again.

## practice-references

**Status:** default. **Default:** Pinned, read-only practice-reference catalog with a weekly freshness check; primary sources first, community guides as leads

- **Route:** catalogs/foundation/practice-references.json and practice-references-freshness.yml; this review's re-pins go to grand-catalog as a candidate file
- **Alternatives, ranked:** 1. FlorianBruniaux/claude-code-ultimate-guide; 2. shanraisshan/claude-code-best-practice; 3. hesreallyhim/awesome-claude-code
- **Rejected:** Installing a guide's .claude configuration wholesale
- **Evidence:** practice_references.py; the 2026-10-09 candidate file (37 references, 11 new)
- **Overturn when:** A guide is archived or goes stale under the 90-day rule, or a vendor publishes a maintained practice catalog.
