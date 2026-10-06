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
3. **Discovery.** The common rule is: when no skill fits, use installed `find-skills` or Skills CLI `find` and `skill-creator` for verification or A/B; check client exposure and the skills lifecycle.
   For registry discovery, `find-skills` steps 1-3 read the skills.sh leaderboard and run
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

A global entry may name its own targets: `agents` (a subset of `claude-code` and
`codex`, both when absent) and `copy: true`, which installs a copy into the one
target's own skills folder instead of the shared canonical folder with links
(skills 1.7.0 README:91, :141-142). The supported form is a copy for Claude Code
only (`"agents": ["claude-code"], "copy": true`): `tools/adoption/install_skills.py`
runs the add with `--copy -a claude-code` and reads the copy back from Claude
Code's skills folder; it takes the copy for installed only as a real folder
there with no entry of its name in `~/.agents/skills`, and reports a link or a
same-name entry as `misplaced` (exit 1 in every mode, `--check-only`
included, with nothing deleted). `--print-codex-config` prints no rule for it, and
`scripts/skills_status.py` checks it there and fails when a same-name folder sits
in `~/.agents/skills`, where Codex loads skills. `skill-creator` uses it, because
Codex embeds its own (wave-2 skills ruling, 2026-10-03).

### Held

A selected skill whose install waits for a named measurement or gate has
`status: "held"` and a `held_for` naming it. `install_skills.py` installs it
neither in a full run nor with `--only`, which refuses it as held, and
`skills_status.py` reports it as `held` (and whether a folder from an earlier
install is still present) without failing. Its listing, budget and template
entries stay, so the measurement's result changes only the status. A held skill
that the measurement rejects leaves through a dated record as under
[Retire and remove](#retire-and-remove). `agent-browser` is held for the
browser-tool measurement (since 2026-10-03).

The accepted October 6 round-two lifecycle supersedes the historical unchanged-ref
preference: guidance follows upstream HEAD and every verified move retains its prior
canonical identity. `install_skills.py --record` resolves the public commit and binds
its skill-directory tree to the actual installed tree. When HEAD no longer matches,
an earlier immutable ref is a fallback only after its own source tree matches the
installed content. A newer ref is recorded identity, not evidence of improved fit.
Compare source, URL, path, ref, tree and SKILL.md digest together: identical bytes at
a fork do not inherit the earlier origin, license or audit evidence. Unverified rows
preserve the earlier entry and remain unresolved; no ref is guessed. See the
[recording and live-budget decision](../../docs/decisions/2026-10-06-skill-recording-and-live-catalog-budgets.md).

Tool-coupled skills follow their binary release. The status check compares retained
binary-release metadata and reports an advisory upstream restore/update proposal;
missing release evidence is unknown. It adds no deny rule or automatic host restore.
Vendor-generated HF records the pinned generator and exact emitted SKILL.md bytes
with `tree_sha: null`; its mirror stays separate comparison provenance. That
exception does not authorize null trees for other sources or project/worker installs.
A registry listing's installed flag may cover only its own directory. Plugins and
built-in skills also consume the actual client catalog budget.

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

Installation may use the selected upstream's supported route; Tier A observes the
public lock, folders and plugin caches, and Tier B reconciles verified identities in
an owned worktree. The October 6 configuration changes have their own review and
host-apply authorization; these commands do not apply client settings or hooks:

```sh
python3 tools/adoption/install_skills.py --record --dry-run --json
python3 tools/adoption/install_skills.py --record --json
python3 scripts/skills_status.py --metadata-only --ledger <state>/skills/ledger.jsonl --json
```

The metadata-only status reads bounded regular files with required no-follow and
nonblocking descriptor flags. It preserves canonical Claude directory aliases into
the explicit shared roots; unknown external targets, final-file symlinks and FIFOs
are not read or hashed. Missing or stale ledger coverage is reported. Neither status
nor the recorder starts a fresh model session. Full budget evidence uses explicitly
retained native listing/catalog inputs; absent inputs are unknown, not passed.
Coverage matches the current canonical `state_key` and SKILL.md digest, so a visit to
another native profile cannot replace or remove the first profile's identity.
Legacy ledger rows without that supported binding stay unbound rather than proving coverage.

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

### Project-scope exception: 2026-10-03

The repository-owned
[`omniroute-runtime-worker`](../../.claude/skills/omniroute-runtime-worker/SKILL.md)
is a Claude Code project skill, auto-listed only in this repository through
`.claude/skills/omniroute-runtime-worker/SKILL.md`, following
[Claude's native project-skill scope](https://code.claude.com/docs/en/skills).
It is maintained with the SDK example rather than installed globally through
the selected third-party skill manifest. Its description costs 129 characters
(129 UTF-8 bytes), in addition to the manifest's listing totals; the body loads
on invocation. Hosts whose `.git/info/exclude` hides `/.claude/` must retain it
in the real review index with
`rtk git add -f .claude/skills/omniroute-runtime-worker/SKILL.md`.
On each SDK or route change, update the skill, example and dated decision
together, verify the description length and native listing/read observation,
and run the example's documented checks. The September 30 callsite receipt
remains the historical listing/read observation; this repair adds no new
Claude model run. See the
[October 3 decision](../../docs/decisions/2026-10-03-omniroute-sdk-worker-0160.md)
for current qualification limits.

- **Claude** fits the listing to `skillListingBudgetFraction` of the model's
  context window (default 0.01, with an 8,000-character fallback) and cuts each
  entry at 1,536 characters. On overflow it drops descriptions, starting with the
  least-invoked skills, and writes a warning to the debug log. The template sets
  the fraction to 0.05 under the user's
  [September 30 directive](../../docs/decisions/2026-09-30-skills-llm-native-listing.md)
  so eligible skills remain visible with descriptions; never also set
  `SLASH_COMMAND_TOOL_CHAR_BUDGET`, which pins a fixed count.
  Check a host with `claude --debug -p ok` on a 200k and a 1M-context model, the
  `/doctor` estimate and the `/context` Skills row, then follow the
  [October 5 budget decision](../../docs/decisions/2026-10-05-harness-context-budget.md).
  Skill listing is governed by that directive independently of the startup file
  budget. The new-WSL apply step keeps this fraction, including on NativeStack2604;
  main's ordinary settings merge preserves unmentioned host keys.
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

For an approved global retirement, use `install_skills.py --retire NAME --skills-bin
"$SKILLS_BIN" --json`. It invokes upstream `skills remove NAME -g -y -a claude-code
codex`, then confirms absence from the canonical folder, Claude alias, global lock
and native legacy `$CODEX_HOME/skills/NAME` root before changing the manifest. It
does not inspect or delete unrelated bundled `.system/NAME`. A zero native exit with
any retained global copy is reported as a limit and leaves the selected entry intact.
`--dry-run` makes a proposal only; `excluded[].last_pin` keeps the full prior source.
The HF generated form's removal is explicitly unsupported by this adapter rather
than replaced with a custom file remover. Project retirement remains a separate
owned native operation. Configuration and hook activation changes require their
own reviewed host-apply step; these commands do not apply that configuration.
Removing a shared selected skill affects its client aliases; update its selection
before claiming the host still matches the manifest. Retain useful evidence and
delete only the owned temporary installation. Rollback and cleanup are operations
to verify, not conclusions implied by a successful install.
