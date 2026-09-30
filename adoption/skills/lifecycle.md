# Native skill lifecycle

This is the one lifecycle guide for the skills in [the selected manifest](manifest.json):
how a task finds its skill, selection, installation, activation, per-client
invocation, the listing budget, updates, recovery and retirement. The client
chooses applicable skills from their descriptions; read a selected `SKILL.md` and
use its supported workflow. The current user request and canonical project
instructions settle conflicts. Load supporting references only for the branch
that needs them.

This follows [OpenAI's September 11 Astra guidance](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra),
[Codex native skills](https://developers.openai.com/codex/skills), and
[Claude native skills](https://code.claude.com/docs/en/skills). It uses the maintained
[Vercel Skills CLI at `7407f389` / v1.7.0](https://github.com/vercel-labs/skills/tree/7407f3893ad4dceab546ac002c3ef806e4000c73),
the newest release tag and npm `latest` on 2026-09-30, not a second router or
installer. The selections and their listing states are decided in the
[skills trial record](../../docs/decisions/2026-09-25-skills-trial-and-usage.md) and the
[LLM-native listing record](../../docs/decisions/2026-09-30-skills-llm-native-listing.md).
See the [September 30 maintenance record](../../docs/decisions/2026-09-30-native-skill-lifecycle.md)
for observed execution and its limits, and the
[native evaluation of two selected skills](../../evidence/artifacts/native-skill-finalization-20260930/README.md)
for their Codex and Claude outcomes. The finalization record, with the host's source
refresh and the cross-family review, lands with unit F1.

## How a task finds its skill

1. **Listed skills.** Both clients list the name and description of every
   model-invocable skill, within their listing budgets. The two upstream user-only
   skills are not listed (`/name` in Claude, `$name` in Codex; see
   [Activate and invoke](#activate-and-invoke)), and a listing over its budget
   loses descriptions (see [Listing budget](#listing-budget)).
   Match the task's actual workflow rather than a shared keyword, then read the
   whole selected `SKILL.md` before acting. A name mention is not an application.
2. **`search-first`.** When no listed skill fits, the model invokes
   [`search-first`](https://github.com/affaan-m/ECC/blob/c70874fae9eb0e5ad0365beb7e2955899fd1d30f/skills/search-first/SKILL.md),
   which checks installed skill roots, packages, MCP servers and repositories
   before any custom code is written.
3. **`find-skills`.** For a gap that remains, the model invokes `find-skills` for
   registry discovery: its steps 1-3 read the skills.sh leaderboard and run
   `"$SKILLS_BIN" find <query>`. Its install-count, source and star thresholds
   (step 4) guide discovery only; popularity is not evidence. Its step-6
   `skills add <owner/repo@skill> -g -y` is replaced by a pin in the manifest:
   a session never installs a skill ad hoc; it records the candidate and the
   coordinator pins it (see [Install and inspect](#install-and-inspect)).
4. **The sweep.** Candidates for a gap compete head-to-head through the
   [landscape sweep](../../tools/sota-convergence/landscape-sweep/README.md) or a
   scoped comparison in a dated decision record that names the alternatives, the
   evidence and the overturn condition. Only the selected winner is pinned and
   installed.

## Select and pin

Keep one selected workflow per capability and short applicability descriptions.
Record in [the manifest](manifest.json) the immutable tree URL and 40-hex `ref`,
`path`, `tree_sha` (the git tree of the skill folder, which the Skills CLI stores
as `skillFolderHash`), `skill_md_sha256`, `skill_md_bytes`, `description_chars`
(the manifest's `description_chars_method`), the upstream
`disable-model-invocation` flag, `upstream_allow_implicit_invocation: false` when the
skill's `agents/openai.yaml` sets `allow_implicit_invocation: false`, `claude_listing`
and `codex_enabled`. Then update the budget sums and the runtime-worker `reuse_ref`
copies.

Verify each pin from a blobless clone of its source repository
(`git clone --filter=blob:none --no-checkout <repository>`, then
`git rev-parse <ref>:<path>` and `git show <ref>:<path>/SKILL.md`), not with
per-file API calls. A newer repository commit alone does not establish a better
workflow: retain an unchanged skill tree at its existing pin, and re-pin only
after reviewing a change to the skill's own tree (`git rev-parse origin/HEAD:<path>`
differs from `tree_sha`). A registry listing's installed flag may cover only its
own directory; it does not inspect every native skill root. Plugins and built-in
skills also consume context, outside this manifest's description budget.

## Install and inspect

Use the explicit isolated executable from the selected host's tools root:

```sh
SKILLS_BIN=<tools-root>/skills-1.7.0/bin/skills
"$SKILLS_BIN" --version
python3 tools/adoption/install_skills.py --skills-bin "$SKILLS_BIN" --dry-run --json
python3 tools/adoption/install_skills.py --skills-bin "$SKILLS_BIN" --json
python3 tools/adoption/install_skills.py --skills-bin "$SKILLS_BIN" --check-only --json
python3 scripts/skills_status.py --skills-bin "$SKILLS_BIN" --json
"$SKILLS_BIN" list -g --json
```

The existing installer checks the CLI pin, calls upstream `skills add` with each
immutable tree URL and only the selected clients, then verifies or rolls back a
failed installation. It disables telemetry and the add-time audit request. A
matching existing installation is reused. Apply only the selected profile's
listing controls from [the update guide](../update.md#apply-the-skills-manifest).

A session never installs a skill ad hoc; it records the candidate and the
coordinator pins it, and installation runs only through this manifest-driven
installer. The Claude settings template therefore denies, in every session, the
Skills CLI commands that write installed skills (skills 1.7.0
[`src/cli.ts` L336-402](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/cli.ts#L336-L402):
`add`, `a`, `i`, `install`, `remove`, `rm`, `r`, `check`, `update`, `upgrade` and
`experimental_*`) in four forms: a bare `skills`, `npx [flags] skills`,
`npx [flags] skills@<version>` and a path ending in `bin/skills`, such as the pinned
`<tools-root>/skills-1.7.0/bin/skills`. `Edit(~/.agents/**)` keeps the file tools
out of the canonical skill folders. `find`, `list`, `init`, `use` and `--version`
stay allowed, and the installer's own `add` and rollback `remove` run as
subprocesses, which Bash rules do not see. The rules match the command text a
model writes, not every route to the program: `"$SKILLS_BIN" add`, `sh -c`,
`node <path>/cli.mjs` or another package runner is not matched
([permissions](https://code.claude.com/docs/en/permissions), "Wildcard patterns",
"Compound commands" and "What a Bash rule doesn't match"), so the manifest and
`skills_status.py` stay the check of what is installed.
The three bare-form verb rules end in `<word>*` (`Bash(skills check*)`, `update*`, `upgrade*`) so that Context
Mode's plain-regex matcher (mksglu/context-mode 1.0.169, `evaluateCommandDenyOnly`), which applies the same user
rules to `ctx_execute` commands without the bare-command match, also denies the bare command; the short aliases
keep ` *` because `skills init` is legitimate. A leading assignment is not stripped on that path.

`skills_status.py` checks required metadata and reports supporting-file hashes
separately. Its zero exit does not establish full-tree integrity or successful
native skill invocation. The documented `supply-chain-risk-auditor` `uv.lock`
exception has its own
[per-blob check and controls](../../evidence/artifacts/skills-listing-restore-20260928/README.md).
Preserve local changes before a supported reinstall; `--force` does not make the
wrapper reinstall a folder it already classifies as `ok`.

## Activate and invoke

Every skill the model may invoke is listed and enabled in both clients: Claude
`claude_listing: "on"` (the description is listed; the model and `/name` can
invoke it) and Codex `codex_enabled: true`. The exceptions follow upstream, not
listing savings. A skill whose upstream frontmatter sets
`disable-model-invocation: true` stays `user-invocable-only` for Claude (hidden
from the model, `/name` only), and its upstream `agents/openai.yaml`
`allow_implicit_invocation: false` limits Codex to an explicit `$name`. The pinned
`skill-creator` stays off for Codex, which ships its own `.system/skill-creator`;
the table that turns the pinned copy off names its path, so Codex's own copy stays
on. `name-only` (name without description) remains available, and `off` marks a
retired selection.

- **Claude.** The settings template's `skillOverrides` carries each state, and
  `tools/adoption/apply_claude_settings.py` deep-merges it into the host settings.
  Claude watches skill directories and applies `SKILL.md` edits within the running
  session. Run `/reload-skills` for a top-level skills directory created after the
  session started, and `/reload-plugins` for plugin hooks, MCP or agent changes.
  These are different operations.
- **Codex.** Disabled selections are the `[[skills.config]]` tables that
  `tools/adoption/install_skills.py --print-codex-config` prints for
  `~/.codex/config.toml` (`$CODEX_HOME/config.toml`). Each selects the installed
  copy by the absolute path of its `SKILL.md`, never by name:

  ```toml
  [[skills.config]]
  path = "<home>/.agents/skills/skill-creator/SKILL.md"
  enabled = false
  ```

  Codex applies a `name` rule to every loaded skill of that name, its bundled
  `.system` skills included, and a `path` rule only to the skill whose canonical
  `SKILL.md` it names
  ([`skills_config.rs` L94-125](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/config/src/skills_config.rs#L94-L125),
  [`host_outcome.rs` L52-54](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/ext/skills/src/host_outcome.rs#L52-L54)).
  A global install leaves a Codex skill only in the canonical
  `~/.agents/skills/<name>`
  ([`installer.ts` L392-402](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/installer.ts#L392-L402)),
  which Codex loads from its `$HOME/.agents/skills` root
  ([`host_roots.rs` L103-108](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/ext/skills/src/host_roots.rs#L103-L108)).
  The installer prints paths under `--home`; for a project-scoped manifest it
  requires `--project-dir` and names `<project>/.agents/skills/<name>/SKILL.md`,
  and the table still goes in the user config, the only file layer Codex reads
  rules from. `scripts/skills_status.py` accepts the path form, resolved as Codex
  resolves it (`~`, a path relative to the config folder, symlinks), and fails a
  `name` table for a name Codex's bundled skills carry (`imagegen`, `openai-docs`,
  `review-agent`, `skill-creator` and `skill-installer` at `rust-v0.159.2`).
  Restart Codex after changing `config.toml`, as the
  [Codex skills page](https://developers.openai.com/codex/skills) says for these
  tables. Codex detects changed and newly installed skills; check the new listing
  and use in a fresh turn or session, and restart Codex only if the change is
  missing.

Installation does not override these policies or make a disabled skill available.

Use [upstream skill evaluation](https://developers.openai.com/blog/eval-skills):
check explicit invocation, a realistic implicit positive and an adjacent negative.
Inspect the actual instruction read and task result. A name mention or a usage
count does not establish correct application. Record misses and unnecessary
work. `/skill-doctor` and the existing
[skill usage tool](../../tools/skill-usage/README.md) supplement that observation.
Keep raw native logs private and publish compact sanitized receipts.

Grade the requested artifact and the response contract separately: a section
word limit and a whole-response limit are different checks. When a downstream
consumer needs JSON, use the client's native output schema and inspect the actual
structured result. Keep original format failures when adding a separately
declared follow-up; a passing enabled/disabled baseline establishes no quality
gain by itself. Sources: [native eval guidance](https://developers.openai.com/blog/eval-skills)
and [Claude structured output](https://code.claude.com/docs/en/headless).

## Listing budget

- **Claude** fits the listing to `skillListingBudgetFraction` of the model's
  context window (default 0.01, with an 8,000-character fallback) and cuts each
  entry at 1,536 characters. On overflow it drops descriptions, starting with the
  least-invoked skills, and writes a warning to the debug log. The template sets
  0.05; never also set `SLASH_COMMAND_TOOL_CHAR_BUDGET`, which pins a fixed count.
  Check a host with `claude --debug -p ok` on a 200k and a 1M-context model, the
  `/doctor` estimate and the `/context` Skills row, then follow the
  measure-then-lower plan in the listing record.
- **Codex** fits its catalog to `[skills] max_context_tokens`, capped at 10,000
  tokens when set; unset, the budget is 2% of the context window, and 8,000
  characters when the window is unknown. Each description is cut at 1,024
  characters. The template sets 6,000 tokens.
- **Manifest.** `budget.claude_on_description_chars` stays within
  `trial.on_description_char_cap`, and `budget.codex_enabled_description_chars`
  counts every Codex-enabled description; the manifest tests recompute both.
  `budget.codex_catalog_description_chars` counts the descriptions Codex shows the
  model, leaving out `upstream_allow_implicit_invocation: false` skills;
  `budget.codex_configured_budget_tokens` equals the Codex template's
  `max_context_tokens`; and `codex_fallback_budget_chars` keeps the 8,000-character
  fallback as metadata, not a cap. `skills_status.py` estimates the shown catalog
  in tokens as `render.rs` charges it, each line and its newline at
  ceil(bytes / 4), and reports the estimate beside the configured budget.

Sources: the Claude [skills](https://code.claude.com/docs/en/skills) and
[environment variables](https://code.claude.com/docs/en/env-vars) references, and
`codex-rs/ext/skills/src/render.rs` L19-25, L126-160 and L258-267 at
[rust-v0.159.2](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/ext/skills/src/render.rs).

## Update and recover

Review the exact changed upstream skill directory, update its immutable URL, ref,
tree and file hashes, reuse consumers and budgets, then dry-run and rerun the same installer.
The Skills CLI preserves recorded immutable refs on update.
Do not use `skills check` as a read-only gate: at v1.7.0 it calls the same
[mutating update path](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/cli.ts#L398).

Before replacing a selected skill, retain its existing folder and public lock
metadata in private lifecycle state. To recover, restore the previous manifest
pin and re-add its immutable source through the same supported installer, then
repeat metadata, supporting-file and native activation checks. Do not replace
client accounts, authentication stores or another skill's state.

## Retire and remove

A selection leaves through a dated decision record, or when upstream removes it.
Move it from `skills[]` to `excluded[]` with a `retired` date, the reason and the
overturn condition, and keep its historical pin (ref, tree and `SKILL.md` hash)
recoverable in that reason. The settings writer deep-merges, so omitting a key
from the template preserves a host's earlier value: keep an explicit `"off"` for
the retired name in `skillOverrides` (the manifest tests derive it from
`retired`). The Codex tables that `--print-codex-config` prints cover only
manifest skills, so remove a retired skill's installed folder instead. Remove its
runtime-worker `reuse_ref` entry and coverage selections while retaining dated
evidence.

For removal, the host batch runs upstream `"$SKILLS_BIN" remove NAME -g -y` from a
shell outside a Claude session, since the settings template denies the CLI's
remove commands in a session (see [Install and inspect](#install-and-inspect)).
Then inspect the canonical folder, lock and client links. Omit `-g` in an owned
disposable project.
Removing a shared selected skill affects its client aliases; update its selection
before claiming the host still matches the manifest. Retain useful evidence and
delete only the owned temporary installation. Rollback and cleanup are operations
to verify, not conclusions implied by a successful install.
