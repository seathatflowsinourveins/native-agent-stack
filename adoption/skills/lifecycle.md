# Native skill lifecycle

Use this guide when installing, activating, updating or recovering the skills in
[the selected manifest](manifest.json). The client chooses applicable skills from
their descriptions; read a selected `SKILL.md` and use its supported workflow.
The current user request and canonical project instructions settle conflicts.
Load supporting references only for the branch that needs them.

This follows [OpenAI's September 11 Astra guidance](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra),
[Codex native skills](https://developers.openai.com/codex/skills), and
[Claude native skills](https://code.claude.com/docs/en/skills). It uses the maintained
[Vercel Skills CLI at `7407f389` / v1.7.0](https://github.com/vercel-labs/skills/tree/7407f3893ad4dceab546ac002c3ef806e4000c73),
not a second router or installer. See the
[September 30 maintenance record](../../docs/decisions/2026-09-30-native-skill-lifecycle.md)
for observed execution and its limits.

For the current host's source refresh, native Codex/Claude outcomes and
cross-family review, read the
[finalization record](../../docs/decisions/2026-09-30-sota-native-finalization.md).

## Discover and select

Match the actual workflow, rather than a shared keyword. Start with the available
client skill catalog and [the manifest](manifest.json). For a new gap, use the
installed research/discovery skill and inspect the maintained upstream repository.
Record its immutable commit, skill-directory tree, file hash, compatibility and
the evidence that would change the selection. A registry listing's installed
flag may cover only its own directory; it does not inspect every native skill root.

Keep one selected workflow per capability and short applicability descriptions.
Retain useful unchanged source trees at their existing pins. A newer repository
commit alone does not establish a better workflow. Plugins and built-in skills
also consume context, outside this manifest's description budget.

## Install and inspect

Use the explicit isolated executable from the selected host's tools root:

```sh
SKILLS_BIN=<tools-root>/skills-1.7.0/bin/skills
rtk "$SKILLS_BIN" --version
rtk python3 tools/adoption/install_skills.py --skills-bin "$SKILLS_BIN" --dry-run --json
rtk python3 tools/adoption/install_skills.py --skills-bin "$SKILLS_BIN" --json
rtk python3 tools/adoption/install_skills.py --skills-bin "$SKILLS_BIN" --check-only --json
rtk python3 scripts/skills_status.py --skills-bin "$SKILLS_BIN" --json
rtk "$SKILLS_BIN" list -g --json
```

The existing installer checks the CLI pin, calls upstream `skills add` with each
immutable tree URL and only the selected clients, then verifies or rolls back a
failed installation. It disables telemetry and the add-time audit request. A
matching existing installation is reused. Apply only the selected profile's
listing controls from [the update guide](../update.md#apply-the-skills-manifest).

`skills_status.py` checks required metadata and reports supporting-file hashes
separately. Its zero exit does not establish full-tree integrity or successful
native skill invocation. The documented `supply-chain-risk-auditor` `uv.lock`
exception has its own
[per-blob check and controls](../../evidence/artifacts/skills-listing-restore-20260928/README.md).
Preserve local changes before a supported reinstall; `--force` does not make the
wrapper reinstall a folder it already classifies as `ok`.

## Activate and verify the task

Codex detects changed skills through its native watcher; check the new listing
and use in a fresh turn/session, and restart only if the change is missing.
Claude watches existing skill directories; use `/reload-skills` for a newly
created top-level directory and `/reload-plugins` for plugin hooks, MCP or agent
changes. These are different operations.

Keep the declared native listing states: Claude `name-only` and
`user-invocable-only`, and Codex-disabled selections, limit implicit discovery.
Codex `agents/openai.yaml` may also disable implicit invocation. Installation
does not override those policies or make a disabled skill available.

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

## Update, recover and remove

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

For removal, use upstream `skills remove NAME -g -y`, then inspect the canonical
folder, lock and client links. Omit `-g` in an owned disposable project. Removing
a shared selected skill affects its client aliases; update its selection before
claiming the host still matches the manifest. Retain useful evidence and delete
only the owned temporary installation. Rollback and cleanup are operations to
verify, not conclusions implied by a successful install.

When retiring a formerly enabled Claude selection, merge an explicit off
override through the supported settings writer; omitting the key from a
deep-merge template preserves its prior value. Remove its current catalog
references while retaining dated evidence and a recoverable old source pin.
