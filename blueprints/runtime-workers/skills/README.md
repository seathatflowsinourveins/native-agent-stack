# Runtime-worker skills trial

The [manifest](manifest.json) selects **137 skills from 13 pinned sources** for
a broad worker trial: 77 OpenHands registry skills, 14 of the 15 superpowers
lifecycle skills, all 28 of the adoption manifest's skills reused by `reuse_ref`,
and targeted additions for evaluation, research, browser testing and framework
review. `security-audit` and `skill-creator` joined the reused set on 2026-09-30, when
main promoted the first and pinned the second
([LLM-native listing decision](../../../docs/decisions/2026-09-30-skills-llm-native-listing.md)).
`verification-before-completion`, which main removed from
its trial under M4 (#464), is excluded; see [Gates of reused adoption skills](#gates-of-reused-adoption-skills). [Research](research.md)
records the source review; each skill has its own `repo@commit path:line`
merit citation. Selection means `trial`, not native acceptance or measured SOTA.

The build provides installation and verification code, a coverage contract and
a report-only freshness workflow. It does not install on this host, start workers,
change active client configuration, or claim E2E invocation. The CLI was absent
on the builder's PATH; synthetic subprocess tests are labeled as such in
[validation](validation.json). Worker discovery, invocation, task quality and
prompt cost are the next native acceptance measurements.

## Source selection and collisions

`OpenHands/extensions@bea7a20c59c44ec4dacddac3fc0efe58b9c73880` is release
`v0.25.0`, published 2026-09-27. Its recursive tree contains **66**
`skills/<name>/SKILL.md` files and **18** plugin skill entrypoints. The manifest
records all 84 in `openhands_inventory`: 77 selected, seven explicitly excluded.
The exclusions are two magic-word fixtures, the separate-copying `add-skill`
implementation, three name collisions, and the `openhands` plugin bundle
entrypoint. Individual API/SDK/automation skills cover the latter. Native plugin
hooks, commands, marketplace registration and MCP configuration are not installed
by a SKILL.md package installation.

| Collision | Selected source | Reason |
| --- | --- | --- |
| `frontend-design` | Anthropic, existing adoption pin | Reuse the adopted reference; avoid OpenHands shadowing it. |
| `skill-creator` | Anthropic | Includes baseline trials, rubric grading, variance and blind A/B output comparison. |
| `code-review` | OpenHands | Repository and acceptance criteria ground risk review; no Matt-specific tracker configuration required. |
| `release-notes` | OpenHands `skills/release-notes` | Standalone history-to-changelog instructions; no plugin hook required. |
| `theme-factory` | OpenHands | Keep the registry's worker entry; the Anthropic duplicate cannot coexist by name. |
| `pdf` | Anthropic | Format-specific processing resources for research and extraction outputs. |
| `linear` | OpenHands | Fits the registry's ticket and automation procedures. |

The manifest records all conflicting repository/ref/path triples. Superpowers
contributes planning, isolated execution, TDD, debugging, review and branch
completion as separate skills; that composable lifecycle merits a trial. Its
verification skill, `verification-before-completion`, is excluded as on main (see
[Gates of reused adoption skills](#gates-of-reused-adoption-skills)). The
lifecycle's Claude/Codex tool assumptions, namespaced skill references and hooks
need native worker acceptance. Installing its files does not register a
`superpowers:` namespace or SessionStart hook. Worker calls use installed skill
names; session/user instructions retain precedence over skill workflows.

`grill-me`, `handoff`, `improve-codebase-architecture`, `to-spec` and `to-tickets`
carry upstream `disable-model-invocation: true`. Preserve those bytes and use
explicit supported invocation where appropriate; do not reinterpret an absent
automatic activation as proof that the worker cannot load them.
At the inspected OpenHands SDK pin, `invoke_skill` rejects these five skills
even if a model explicitly requests that tool call. A client-specific user
invocation route must be verified separately; it is not established by this
catalog ([invoke_skill.py:109](https://github.com/OpenHands/software-agent-sdk/blob/da28c7736ea667ceae51cf3a3b9b37ab5f528f22/openhands-sdk/openhands/sdk/tool/builtins/invoke_skill.py#L109)).

## Gates of reused adoption skills

Every skill in `adoption/skills/manifest.json` is either reused by `reuse_ref` or
listed in `excluded` with an `adoption_ref`, a `reason` and an `overturn` condition.
Both references are the value `"adoption/skills/manifest.json"` and match the
adoption skill of the same name, so main can reorder or insert skills without
moving a reference. `tests.test_runtime_worker_skills` fails when main adds a skill
that is in neither set, and when a reused entry's pin differs from main's.

- **Codex.** A reused entry carries no `codex_enabled` or `claude_listing` of its
  own. `install_skills.py` resolves each `reuse_ref` when it reads the manifest,
  refuses an entry whose pin drifted, that restates a gate or whose name main does
  not carry exactly once, and takes both gates from the adoption entry. `--print-codex-config` on this manifest therefore prints
  an `enabled = false` table for every reused skill main keeps off for Codex
  (16 of the 27 on 2026-09-28; only `skill-creator`, of 29, on 2026-09-30). Each
  table selects `<project>/.agents/skills/<name>/SKILL.md` by `path`, never by
  `name`, which would also disable Codex's bundled skill of that name
  ([skills lifecycle](../../../adoption/skills/lifecycle.md#activate-and-invoke)).
- **Claude listing.** `claude_listing` (`on`, `name-only`, `user-invocable-only`,
  `off`) is a Claude Code client setting, applied through the `skillOverrides`
  settings key rather than the skill's frontmatter
  ([Claude Code skills](https://code.claude.com/docs/en/skills#override-skill-visibility-from-settings);
  [2026-09-25 decision](../../../docs/decisions/2026-09-25-skills-trial-and-usage.md)).
  It is not applied inside OpenHands or other runtime containers, which have no
  Claude skill listing. The OpenHands SDK's skill loader reads skill directories:
  project `.agents/skills`, `.openhands/skills` and `.openhands/microagents`
  ([skill.py:1123-1130](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/skills/skill.py#L1123-L1130)),
  and user `~/.agents/skills`, the OpenHands persistence directories and
  OpenHands' own enabled installed skills
  ([skill.py:936-973](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/skills/skill.py#L936-L973)).
  With project loading on, it also reads the third-party instruction files
  `.cursorrules`, `AGENTS.md`, `agent.md`, `CLAUDE.md` and `GEMINI.md`
  ([skill.py:346-352](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/skills/skill.py#L346-L352))
  from the work directory and from the Git repository root, the nearest ancestor
  holding `.git`
  ([skill.py:981-992](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/skills/skill.py#L981-L992),
  [skill.py:1084-1106](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/skills/skill.py#L1084-L1106)),
  and nested copies below the work directory as path-scoped rules
  ([skill.py:1108-1121](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/skills/skill.py#L1108-L1121)).
  Each such file becomes a skill without a trigger, which is permanent context
  rather than an on-demand listing
  ([skill.py:635-651](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/skills/skill.py#L635-L651),
  [skill.py:874](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/skills/skill.py#L874)).
  It also reads each skill's SKILL.md frontmatter, including
  `disable-model-invocation`
  ([skill.py:278-284](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/skills/skill.py#L278-L284),
  [skill.py:528-538](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/skills/skill.py#L528-L538)).
  Its rendered `<available_skills>` block gives each SKILL.md skill's name and
  description only: `<location>` is omitted on purpose, so that `invoke_skill`
  stays the one invocation path
  ([skill.py:1524-1530](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/skills/skill.py#L1524-L1530)),
  although the class docstring still lists a location
  ([skill.py:184](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/skills/skill.py#L184)).
  `skill.py` never reads Claude Code settings or a `skillOverrides` key, so main's
  `claude_listing` has no effect there. OpenHands' own controls are that
  frontmatter flag; `AgentContext.disabled_skills`, a deny-list applied by name
  after every source has loaded
  ([agent_context.py:171-182](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/context/agent_context.py#L171-L182),
  [agent_context.py:291-297](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/context/agent_context.py#L291-L297));
  and the source flags `load_user_skills`, `load_public_skills` and
  `load_project_skills`, each `False` by default
  ([agent_context.py:93-109](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/context/agent_context.py#L93-L109),
  [agent_context.py:127-142](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/context/agent_context.py#L127-L142)).
  The installed-skill enable state covers only skills under
  `~/.openhands/skills/installed/`; it does not disable a same-named copy found in
  a project directory, and a project skill overrides a same-named explicit skill.
  `skill.py` is the same blob at `fcc102a6` and at the `da28c773` pin cited
  elsewhere in this README; `agent_context.py` is cited at `fcc102a6` only.
  A Claude Code worker must apply main's `claude_listing` in its own settings;
  this installer writes no client settings.
- **Reused after promotion.** `security-audit` (#448, `8315274f`) stayed out while
  main kept it Codex-disabled and name-only. Main promoted it on 2026-09-30 (listing
  `on`, Codex enabled; the M5c bake-off against `/security-review` still decides its
  trial), which met the exclusion's overturn condition: it is a `reuse_ref` entry for
  the `security` scenario and the `coding` and `orchestration` roles.
  `test_security_audit_is_reused_since_main_promoted_it` fails if main changes that
  gate again, so a demotion cannot pass unnoticed.
- **Excluded with main.** `verification-before-completion` stays out because main
  removed it from its trial under the skills-trial conflict rule M4 (#464;
  [decision](../../../docs/decisions/2026-09-28-delegated-decisions.md)). Its
  SKILL.md at `8ca22db` requires a fresh run of the verification command before any
  completion claim and rates a previous run as not sufficient, while `AGENTS.md:16`
  says to reuse passing evidence when its inputs still match. A worker whose work
  directory is a checkout of this repository loads that `AGENTS.md` too: OpenHands
  with project loading on (above), and Claude Code through the `@AGENTS.md` first
  line of `CLAUDE.md`. Main now lists the skill under its own `excluded` rather
  than `skills`, so this exclusion keeps the reviewed pin but carries no
  `adoption_ref`. If main re-admits it,
  `test_verification_before_completion_stays_excluded_until_main_readmits_it` fails
  and the coverage contract finds it neither reused nor excluded: replace the
  exclusion with a `reuse_ref` entry and restore its `tdd`, `github-ci-fix` and
  `code-review` assignments. Until then extraction callers have no direct CI-fix
  skill (see [Explicit capability gaps](#explicit-capability-gaps)).

## Lifecycle through the existing installer

Use the already provisioned **skills 1.7.0** executable and `gh`. The manifest
carries `"scope": "project"`: the wrapper refuses it without `--project-dir`,
before any CLI call, so a global run cannot place the whole trial in
`~/.agents/skills`, which Codex and OpenHands user loading read
(`--print-codex-config`, which only prints, needs `--project-dir` too: its tables
name the project's installed `SKILL.md` paths). The wrapper verifies the
CLI version; project checks first fetch every selected `(source, ref)`
through `gh api`, before any add, then use those cached trees to bind project
lock entries to their pins. A failed lookup stops without changing the project;
`unverified (gh unavailable)` is distinct from a content mismatch. A selected
skill whose pinned tree differs from its manifest `tree_sha` also stops the whole
run before any add, because a rollback after add is not reliable (see the in-use
guard below). This lookup and comparison also run for project dry-run/check-only.
It never copies a skill, writes a lock, or patches upstream SKILL.md.

Before the version check, the wrapper also refuses a project that could redirect
a write outside itself: `.agents/skills`, `.claude/skills` or `skills-lock.json`
passing through a symlink, a selected skill's canonical or Claude path resolving
outside `--project-dir`, or `--project-dir` equal to `--home`. The pinned CLI
recreates `<project>/.agents/skills/<name>` with `rm` and `mkdir`, so through such
a link an add and its rollback would replace and then delete a global skill
([installer.ts:193-200](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/installer.ts#L193-L200),
[installer.ts:388](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/installer.ts#L388)).
Default invocation of a manifest without a scope (main's adoption manifest)
without `--project-dir` retains the existing global Claude Code/Codex behavior.

The project interface supports `universal`, `claude-code` and `codex`. Other CLI
agent adapters are outside this wrapper's verified path contract. For Claude,
the wrapper also selects universal so the canonical copy exists alongside the
native `.claude/skills` link. Each worker gets a dedicated existing project
directory; workers do not share a writable skill lock.

```bash
STACK_ROOT="$PWD"
SKILL_MANIFEST="$STACK_ROOT/blueprints/runtime-workers/skills/manifest.json"
SKILLS_BIN=skills

worker_skills() {
  worker_project="$1"
  worker_agent="$2"
  shift 2
  python3 "$STACK_ROOT/tools/adoption/install_skills.py" \
    --manifest "$SKILL_MANIFEST" --project-dir "$worker_project" \
    --agent "$worker_agent" --skills-bin "$SKILLS_BIN" "$@"
}

# Set these to the owned workspaces already allocated by the runtime launcher.
# They must be existing directories outside this repository and outside any Git
# checkout whose AGENTS.md or CLAUDE.md should not reach the worker (see below).
# These are examples, not active host config.
WORKER_ROOT="$HOME/runtime-workers"
OH_PROJECT="$WORKER_ROOT/openhands"
DF_PROJECT="$WORKER_ROOT/deerflow"
RESEARCH_PROJECT="$WORKER_ROOT/research-caller"
EXTRACTION_PROJECT="$WORKER_ROOT/extraction-caller"
```

A worker project inside this checkout would make `$STACK_ROOT` its Git root: an
OpenHands worker with project loading on would then take this repository's
`AGENTS.md` and `CLAUDE.md` as permanent context (see
[Gates of reused adoption skills](#gates-of-reused-adoption-skills)).

| Worker target | Add (broad trial) | Check installed pins, read only | Update after reviewed manifest repin |
| --- | --- | --- | --- |
| OpenHands coding/orchestration | `worker_skills "$OH_PROJECT" universal` | `worker_skills "$OH_PROJECT" universal --check-only` | Rerun its add command with the revised `SKILL_MANIFEST`. |
| DeerFlow orchestration/research | `worker_skills "$DF_PROJECT" universal` | `worker_skills "$DF_PROJECT" universal --check-only` | Rerun add, then refresh native discovery/projection. |
| Agent calling GPT Researcher (Codex example) | `worker_skills "$RESEARCH_PROJECT" codex` | `worker_skills "$RESEARCH_PROJECT" codex --check-only` | Rerun add; start a fresh caller session. |
| Agent calling crawl4ai (Claude example) | `worker_skills "$EXTRACTION_PROJECT" claude-code` | `worker_skills "$EXTRACTION_PROJECT" claude-code --check-only` | Rerun add; start a fresh caller session. |

Use `--dry-run` to list planned adds; it is not an integrity pass for absent
skills. `--check-only` exits 1 on missing, modified or drifted entries and makes
no add/remove calls. It is not offline: it still verifies the pinned `skills`
binary with `skills --version`, and in project mode it needs `gh` sign-in and
network access for the pinned-tree preflight above. `--only NAME` is repeatable
for a bounded repair or explicitly scoped subset; a name the manifest marks
pruned fails as pruned, not as unknown. A pruned entry is never installed, with
or without `--project-dir`. The broad trial defaults to every non-pruned
manifest skill.
For `--agent claude-code`, an existing `.claude/skills/<name>` must be a symlink
resolving to `.agents/skills/<name>`. A real directory, file or foreign symlink
is `local-modified` with or without a project lock, even if its SKILL.md matches
the pin. The wrapper refuses to overwrite it unless `--force` is given, because
the upstream alias creator replaces existing directories
([installer.ts:254-264](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/installer.ts#L254-L264)).

Project locks are **`<project>/skills-lock.json`**, with `computedHash` (SHA-256),
source, ref and `skillPath`; they do not carry global `skillFolderHash` (Git tree
SHA). Verification checks installed SKILL.md SHA-256, requested target placement,
lock source/ref/path and independently fetched pinned directory tree SHA.
This retains the original verifier's boundary: it does not hash all installed
support files. A pinned-tree mismatch is refused before any add (above). A
SKILL.md or lock-identity mismatch after a successful add removes that skill with
the native CLI, checks removal and returns failure. This is cleanup, not
restoration of a previous version. Recover by rerunning a retained previous manifest.
See [vercel-labs/skills@7407f389 local-lock.ts:15](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/local-lock.ts#L15)
and [add.ts:2066](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/add.ts#L2066).

Remove uses the CLI in the same target project, without `-g` and with exactly
the `-a` targets used for add. Omitting `-a` targets every agent, including an
OpenClaw `skills/<name>` source directory. Check the canonical folder, project
lock entry and, for Claude, `.claude/skills/<name>` independently after removal;
a dangling link also means cleanup is incomplete. The native in-use guard keeps
the canonical folder and its lock entry while any detected agent outside the
`-a` targets has an install path there. For an agent whose project directory is
`.agents/skills`, that path is the canonical folder itself, so retention is
certain whenever such an agent is detected under the wrapper's `HOME` and not
targeted: Codex whenever `$CODEX_HOME` (when unset, `~/.codex`) or `/etc/codex`
exists, unless `--agent codex` targets it
([agents.ts:10](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/agents.ts#L10),
[remove.ts:293-331](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/remove.ts#L293-L331),
[agents.ts:224-232](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/agents.ts#L224-L232)).
The retained copy stays loadable by every loader that reads the project's
`.agents/skills`, including Codex and, with project loading on, the OpenHands SDK.
The wrapper then returns
`error: rollback retained, in use by another agent`; keep that failure visible,
remove the copy deliberately, and never widen the deletion to other agents.
Sources: [remove.ts:209-333](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/remove.ts#L209-L333),
[agents.ts:166-169](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/agents.ts#L166-L169).

```bash
SKILL_NAME=example-skill
(cd "$OH_PROJECT" && DISABLE_TELEMETRY=1 "$SKILLS_BIN" remove "$SKILL_NAME" -y -a universal)
(cd "$DF_PROJECT" && DISABLE_TELEMETRY=1 "$SKILLS_BIN" remove "$SKILL_NAME" -y -a universal)
(cd "$RESEARCH_PROJECT" && DISABLE_TELEMETRY=1 "$SKILLS_BIN" remove "$SKILL_NAME" -y -a universal codex)
(cd "$EXTRACTION_PROJECT" && DISABLE_TELEMETRY=1 "$SKILLS_BIN" remove "$SKILL_NAME" -y -a universal claude-code)
```

Run only the relevant target's remove command. For a prune, retain the entry,
set `status: "pruned"`, attach `prune_evidence` and update the coverage/gap cells;
subsequent installs skip it. For a removed skill still marked trial,
`--check-only` correctly reports it missing and a subsequent add reinstalls it.
Refresh worker discovery after removal and start a new session: an old prompt
may still contain instructions that were loaded earlier.

For an **update**, inspect the freshness artifact, resolve the selected new
commit with `gh api repos/OWNER/REPO/commits/REF`, inspect the pinned diff, obtain
the directory SHA from `gh api repos/OWNER/REPO/git/trees/COMMIT?recursive=1`, and
retrieve the exact SKILL.md via `gh api repos/OWNER/REPO/contents/PATH/SKILL.md?ref=COMMIT`
with `Accept: application/vnd.github.raw+json`. Recompute its SHA-256, byte count,
trimmed parsed description length and disable flag; update URL/ref/merit citation,
coverage and source receipt. Reused adoption entries remain tied to their adoption
pin until that source manifest is updated deliberately. Run the contract tests,
then the same add/check commands above against the reviewed manifest. Record
native load events and repeat the applicable E2E/prompt measurement before
accepting the new pin. Keep the prior manifest for recovery.

**Do not use upstream `skills check` as a report-only operation.** At the pin,
`check` and `update` both enter `runUpdate`; project checks can reinstall or remove
entries and do not preserve an explicitly selected agent argument in the same
way as this wrapper. A SHA-pinned source follows that SHA instead of advancing
to HEAD ([cli.ts:398](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/cli.ts#L398),
[update.ts:849](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/src/update.ts#L849)).

The [scheduled workflow](../../../.github/workflows/runtime-worker-skills-freshness.yml)
runs [runtime_skill_freshness.py](../../../tools/adoption/runtime_skill_freshness.py),
compares each immutable pin with one resolved HEAD per source, and distinguishes
repository movement, changed skill trees, removal at HEAD, invalid pins and
unfetched data. It also reports CLI release drift. It has read-only permissions,
bounded workers/time, SHA-pinned actions and retained JSON/Markdown reports; it
does not install, update, open a PR, merge or change a manifest. Native `check`
semantics are source-verified, not represented as a command execution.

```bash
python3 tools/adoption/runtime_skill_freshness.py \
  --manifest blueprints/runtime-workers/skills/manifest.json \
  --output .runtime/skills-freshness.json --markdown .runtime/skills-freshness.md
```

## Native loader wiring

**OpenHands:** use the actual worker workspace as `--project-dir`. The inspected
SDK loads `.agents/skills` natively and prefers it over the legacy location.
Reference: [OpenHands/software-agent-sdk@da28c773 skill.py:1052](https://github.com/OpenHands/software-agent-sdk/blob/da28c7736ea667ceae51cf3a3b9b37ab5f528f22/openhands-sdk/openhands/sdk/skills/skill.py#L1052).
This source pin is an inspected capability, not an implicit SDK upgrade. Match
the worker's installed revision before claiming it follows this path, then start
a fresh conversation with the native project loader enabled: `load_project_skills`
is `False` by default. Enabling it also loads the work directory's and its Git
root's `AGENTS.md`, `CLAUDE.md` and other third-party instruction files as
permanent context
([skill.py:1084-1121](https://github.com/OpenHands/software-agent-sdk/blob/fcc102a697874d54a357e36004e02c95040dbdc0/openhands-sdk/openhands/sdk/skills/skill.py#L1084-L1121)),
so keep the worker project outside this repository; exclude any unwanted skill by
name with `disabled_skills`.

**DeerFlow:** the repository's recorded native pin is
`42334f26d7025d905678f9075b079fc65f9beaf9` (see its
[existing receipt](../../us-equities/deerflow/native-receipt.json)). That loader
expects category directories such as `public` and skips hidden directories;
a flat `.agents/skills` root is insufficient. A minimal, source-derived projection
keeps CLI ownership and adds one relative category link:

```bash
# After worker_skills "$DF_PROJECT" universal, in this owned worker project only:
if [ ! -e "$DF_PROJECT/.agents/public" ] && [ ! -L "$DF_PROJECT/.agents/public" ]; then
  ln -s skills "$DF_PROJECT/.agents/public"
fi
test "$(readlink "$DF_PROJECT/.agents/public")" = skills
export DEER_FLOW_SKILLS_PATH="$DF_PROJECT/.agents"
# Start DeerFlow using its existing native launch recipe with this environment.
# Preserve its configured container_path and normal read-only public projection.
```

The native configuration accepts `DEER_FLOW_SKILLS_PATH`; the directory walker
follows links under its category root. Its sandbox provider projects public
skills at the configured container path. This bridge is an integration candidate
requiring native discovery/load acceptance, not a shipped universal CLI adapter.
References: [DeerFlow@42334f26 skills_config.py:25](https://github.com/bytedance/deer-flow/blob/42334f26d7025d905678f9075b079fc65f9beaf9/backend/packages/harness/deerflow/config/skills_config.py#L25),
[local_skill_storage.py:75](https://github.com/bytedance/deer-flow/blob/42334f26d7025d905678f9075b079fc65f9beaf9/backend/packages/harness/deerflow/skills/storage/local_skill_storage.py#L75),
[local_sandbox_provider.py:117](https://github.com/bytedance/deer-flow/blob/42334f26d7025d905678f9075b079fc65f9beaf9/backend/packages/harness/deerflow/sandbox/local/local_sandbox_provider.py#L117).
After add/update/remove, restart the owned worker or use its native discovery
refresh; inspect `DeerFlowClient.list_skills()` and a real load in the sandbox.
If this worker already has native skills, merge the additional category into its
owned native configuration deliberately; changing the root is not evidence that
the previous skill inventory was preserved.

**GPT Researcher / crawl4ai callers:** install into the calling agent's project
and choose its native target. Do not install into the Python library's source
directory and call that worker activation. The official GPT Researcher caller
skill is included ([assafelovic/gpt-researcher@0957c301 SKILL.md:1](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/skills/gpt-researcher/SKILL.md#L1));
it is a small MCP entrypoint, not a research-quality guarantee. Native skills
loaders were not found in the bounded pinned runtime-source scans of GPT
Researcher or crawl4ai. Crawl4ai's inspected tree exposes a skill ZIP, but no
CLI-discoverable SKILL.md; the no-hand-copy policy leaves that specific package
as a gap. General caller research, citation and security skills still apply.

## Invocation and pruning

Freeze the E2E run set before installation: one realistic task per covered
scenario/role cell, including issue-to-PR, review, failing CI, release-note
generation, uv/Docker setup, research with cited outputs, and extraction with
source-preserving assertions. Include with/without-skill baselines and repeated
blind output comparisons for the evaluation cells. Reuse the same task inputs,
worker/model/tool revisions and output rubric. A load is necessary evidence of
use; it does not prove better task quality.

For each `(run_id, worker_revision, skill_name, skill_ref)`, retain the native
event IDs, activation route, distinct activation count, run outcome, quality
result and sanitized evidence location. Record failures and missing events.
Count each native event once, and distinguish listing/discovery from loading:

- **OpenHands:** trajectory `MessageEvent.activated_skills` proves trigger-based
  activation. Successful `InvokeSkillObservation.skill_name` with `is_error`
  false proves explicit tool invocation. Deduplicate by event identity and
  keep the two routes separately observable. Do not invent a `SkillLoad` event.
  References: [SDK@da28c773 local_conversation.py:1842](https://github.com/OpenHands/software-agent-sdk/blob/da28c7736ea667ceae51cf3a3b9b37ab5f528f22/openhands-sdk/openhands/sdk/conversation/impl/local_conversation.py#L1842),
  [invoke_skill.py:98](https://github.com/OpenHands/software-agent-sdk/blob/da28c7736ea667ceae51cf3a3b9b37ab5f528f22/openhands-sdk/openhands/sdk/tool/builtins/invoke_skill.py#L98).
- **DeerFlow at 42334f26:** discovery through `list_skills()` is only a registry
  check. Pair AI `read_file` calls with successful ToolMessage results and native
  `skill_context_entry` metadata for SKILL.md loads. Explicit slash invocations
  inject content without a read_file call; retain that route too. Freeze
  `skills.deferred_discovery` across runs. References:
  [skill_context.py:127](https://github.com/bytedance/deer-flow/blob/42334f26d7025d905678f9075b079fc65f9beaf9/backend/packages/harness/deerflow/agents/middlewares/skill_context.py#L127),
  [prompt.py:869](https://github.com/bytedance/deer-flow/blob/42334f26d7025d905678f9075b079fc65f9beaf9/backend/packages/harness/deerflow/agents/lead_agent/prompt.py#L869).
  HEAD `827acf51dc4a713d99632f0319a62ee487598c77` adds `skill_usage` and content
  hashes; those fields are not available at the recorded pin and are not claimed
  here as deployed telemetry.
- **Research/extraction callers:** retain the calling agent's native skill-load
  event and, separately, its GPT Researcher MCP call or crawl4ai tool/API call.
  A tool response alone does not prove that the caller loaded a skill.
- **Claude Code callers:** freeze and record the skill-listing budget setting
  for each run: `skillListingBudgetFraction` or `SLASH_COMMAND_TOOL_CHAR_BUDGET`.
  Record the value and configuration source (including default/unset), both
  settings if present, and the effective budget with the model/context window.
  Capture `/context` output and any excluded-skill warnings, plus debug-log
  listing-overflow warnings. Retain which descriptions the model actually saw.
  Claude keeps names but can drop descriptions when the budget is exceeded;
  a skill whose description was dropped is **uninstrumented (unknown)** for
  pruning, not a zero-activation observation. Missing visibility evidence also
  means unknown. Source: [Claude Code skills, description budget](https://code.claude.com/docs/en/skills#skill-descriptions-are-cut-short)
  (read 2026-09-27).

After the entire frozen E2E run set completes with working activation capture
and confirmed description visibility for each eligible Claude run,
**zero activations => `pruned`**. Store the run-set revision, run IDs, zero count,
instrumentation completeness, per-run listing-budget settings, visibility and
warning evidence in `prune_evidence`, then remove through the CLI and update
coverage. Incomplete runs, dropped descriptions or missing instrumentation mean
unknown, not zero. Report `activations / completed eligible runs` per role,
quality and first-prompt cost before deciding which activated skills to keep.
No skill in this manifest has been pruned or promoted on invented invoke rates.

## First-prompt measurement

Capture the **first actual serialized model request before and after installation**
in a fresh worker conversation, with identical initial task, tools, model route,
worker pin, discovery settings and prior memory state. Measure UTF-8 request
bytes, the portion attributable to advertised skill metadata, and provider-native
input tokens, including cached input tokens as a separate subset. Keep raw
requests private; publish sanitized hashes, byte counts, native usage snapshots,
worker/manifest revisions and matched task IDs. Do not sum overlapping usage.

Measure a neutral first task and a fixed activating task separately: some native
triggers inject bodies immediately. Use a model's own tokenizer only as a labeled
estimate when no provider count is available. Catalog sums are **1,042,408
SKILL.md bytes and 37,215 trimmed description characters**; neither is a prompt
size or token count. Both provider-token fields remain `null` until a real run.
Also record end-to-end input/output usage, latency and task quality so a smaller
first prompt cannot hide repeated reads or failed work.

## Explicit capability gaps

The matrix below has 15 empty role/scenario cells, each also recorded in the
manifest's `gaps`. These are direct-role gaps; a coding-worker handoff remains
available but does not turn the empty cell into an accepted native capability.
Research has no selected direct TDD, E2E, code-review, security, GitHub workflow,
release-note or deployment skill assignment; extraction callers have no direct
issue-to-PR, PR-review, CI-fix, Actions or release-note assignment. The CI-fix
cell became empty when `verification-before-completion`, its only selection, was
excluded with main.

Further limits: skill-output blind A/B evaluation does not implement product
traffic randomization, statistical power or sequential testing; repository memory
does not establish a durable vector-memory service; native plugin hooks and
superpowers tool/namespace adaptation remain separate. No primary-source evidence
found in this review closes these gaps, so no replacement skill was invented.

## Scenario-by-role coverage

Names indicate source-reviewed applicability, not measured invocation. Every
empty cell is marked **GAP** and recorded in `manifest.json`; the machine-readable
`coverage` object contains the same names.

<!-- coverage-table -->

| Scenario | Coding | Orchestration | Research | Extraction caller |
| --- | --- | --- | --- | --- |
| planning-and-specs | `add-javadoc`, `agent-canvas-environment`, `agent-creator`, `agent-readiness-report`, `agent-sdk-builder`, `azure-devops`, `bitbucket`, `bitbucket-cloud`, `bitbucket-data-center`, `brainstorming`, `build-setup`, `canvas-extension-api`, `cobol-modernization`, `codebase-design`, `dispatching-parallel-agents`, `domain-modeling`, `executing-plans`, `frontend-design`, `gitlab`, `gitlab-issue-to-mr`, `improve-agent-readiness`, `linear`, `linear-triage`, `mainframe-planning`, `mainframe-removal`, `mcp-builder`, `openhands-api`, `openhands-automation`, `openhands-sdk`, `prd`, `setup-agents-md`, `spark-version-upgrade`, `subagent-driven-development`, `to-java-migration`, `to-spec`, `to-tickets`, `using-git-worktrees`, `using-superpowers`, `vercel-composition-patterns`, `writing-for-agents`, `writing-plans` | `add-javadoc`, `agent-canvas-environment`, `agent-creator`, `agent-readiness-report`, `agent-sdk-builder`, `azure-devops`, `bitbucket`, `bitbucket-cloud`, `bitbucket-data-center`, `brainstorming`, `build-setup`, `canvas-extension-api`, `cobol-modernization`, `codebase-design`, `dispatching-parallel-agents`, `domain-modeling`, `executing-plans`, `gitlab`, `gitlab-issue-to-mr`, `improve-agent-readiness`, `linear`, `linear-triage`, `mainframe-planning`, `mainframe-removal`, `mcp-builder`, `openhands-api`, `openhands-automation`, `openhands-sdk`, `prd`, `setup-agents-md`, `spark-version-upgrade`, `subagent-driven-development`, `to-java-migration`, `to-spec`, `to-tickets`, `using-git-worktrees`, `using-superpowers`, `writing-for-agents`, `writing-plans` | `brainstorming`, `domain-modeling`, `prd`, `to-spec`, `writing-plans` | `brainstorming`, `codebase-design`, `domain-modeling`, `prd`, `to-spec`, `writing-plans` |
| tdd | `build-setup`, `cobol-modernization`, `mainframe-planning`, `mainframe-removal`, `property-based-testing`, `spark-version-upgrade`, `tdd`, `test-driven-development`, `to-java-migration` | `build-setup`, `cobol-modernization`, `mainframe-planning`, `mainframe-removal`, `property-based-testing`, `spark-version-upgrade`, `tdd`, `test-driven-development`, `to-java-migration` | **GAP** | `property-based-testing`, `tdd`, `test-driven-development` |
| e2e-testing | `agent-browser`, `playwright`, `qa-changes`, `webapp-testing` | `agent-browser`, `playwright`, `qa-changes`, `webapp-testing` | **GAP** | `agent-browser`, `playwright`, `qa-changes`, `webapp-testing` |
| ab-testing-and-evaluation | `diagnosing-superpowers`, `jupyter`, `jupyter-notebook`, `migration-mapping`, `migration-report`, `migration-scoring`, `property-based-testing`, `score-quality`, `score-style`, `skill-creator`, `typesafe-ai`, `vercel-optimize`, `writing-skills` | `diagnosing-superpowers`, `migration-mapping`, `migration-report`, `migration-scoring`, `property-based-testing`, `score-quality`, `score-style`, `skill-creator`, `typesafe-ai`, `vercel-optimize`, `writing-skills` | `jupyter`, `jupyter-notebook`, `skill-creator`, `writing-skills` | `jupyter`, `jupyter-notebook`, `property-based-testing`, `skill-creator`, `typesafe-ai`, `writing-skills` |
| debugging | `datadog`, `diagnosing-bugs`, `diagnosing-superpowers`, `openhands-enterprise-troubleshooting`, `systematic-debugging` | `datadog`, `diagnosing-bugs`, `diagnosing-superpowers`, `openhands-enterprise-troubleshooting`, `systematic-debugging` | `diagnosing-bugs`, `systematic-debugging` | `diagnosing-bugs`, `systematic-debugging` |
| code-review | `code-review`, `code-simplifier`, `codebase-design`, `frontend-design`, `gh-address-comments`, `migration-mapping`, `migration-report`, `migration-scoring`, `receiving-code-review`, `requesting-code-review`, `score-quality`, `score-style`, `vercel-composition-patterns`, `vercel-react-best-practices`, `web-design-guidelines` | `code-review`, `code-simplifier`, `codebase-design`, `gh-address-comments`, `migration-mapping`, `migration-report`, `migration-scoring`, `receiving-code-review`, `requesting-code-review`, `score-quality`, `score-style`, `vercel-react-best-practices`, `web-design-guidelines` | **GAP** | `codebase-design` |
| security | `agentic-actions-auditor`, `codeql`, `fp-check`, `sarif-parsing`, `security`, `security-audit`, `security-best-practices`, `security-threat-model`, `supply-chain-risk-auditor`, `variant-analysis` | `agentic-actions-auditor`, `codeql`, `fp-check`, `sarif-parsing`, `security`, `security-audit`, `security-best-practices`, `security-threat-model`, `supply-chain-risk-auditor`, `variant-analysis` | **GAP** | `security`, `security-best-practices`, `security-threat-model` |
| github-issue-to-pr | `finishing-a-development-branch`, `github`, `github-issue-to-pr`, `github-issue-triage`, `github-repo-monitor`, `jira-issue-to-pr`, `ticket-to-code-change`, `upstream-fork-sync` | `finishing-a-development-branch`, `github`, `github-issue-to-pr`, `github-issue-triage`, `github-repo-monitor`, `jira-issue-to-pr`, `ticket-to-code-change`, `upstream-fork-sync` | **GAP** | **GAP** |
| github-pr-review | `code-review`, `code-simplifier`, `finishing-a-development-branch`, `gh-address-comments`, `github`, `github-delivery-watchdog`, `github-pr-review`, `github-pr-reviewer`, `receiving-code-review`, `requesting-code-review`, `setup-pr-review`, `upstream-fork-sync` | `code-review`, `code-simplifier`, `finishing-a-development-branch`, `gh-address-comments`, `github`, `github-delivery-watchdog`, `github-pr-review`, `github-pr-reviewer`, `receiving-code-review`, `requesting-code-review`, `setup-pr-review`, `upstream-fork-sync` | **GAP** | **GAP** |
| github-ci-fix | `gh-fix-ci`, `github-stale-ci-pr-closer`, `iterate` | `gh-fix-ci`, `github-stale-ci-pr-closer`, `iterate` | **GAP** | **GAP** |
| github-actions | `agentic-actions-auditor`, `github-actions`, `setup-openhands` | `agentic-actions-auditor`, `github-actions`, `setup-openhands` | **GAP** | **GAP** |
| release-notes | `release-notes` | `release-notes` | **GAP** | **GAP** |
| docs-and-citations | `add-javadoc`, `agent-memory`, `agent-readiness-report`, `doc-coauthoring`, `docx`, `evidence-based-citations`, `find-skills`, `github-agents-md-maintainer`, `handoff`, `improve-agent-readiness`, `iterative-retrieval`, `learn-from-code-review`, `mcp-builder`, `pdf`, `pdflatex`, `plain-english-content`, `pptx`, `release-notes`, `research`, `search-first`, `setup-agents-md`, `technical-writing`, `theme-factory`, `writing-for-agents`, `writing-skills`, `xlsx` | `add-javadoc`, `agent-memory`, `agent-readiness-report`, `discord`, `doc-coauthoring`, `docx`, `evidence-based-citations`, `find-skills`, `github-agents-md-maintainer`, `gpt-researcher`, `handoff`, `improve-agent-readiness`, `incident-retrospective`, `iterative-retrieval`, `learn-from-code-review`, `mcp-builder`, `notion`, `pdf`, `pdflatex`, `plain-english-content`, `pptx`, `release-notes`, `research`, `research-brief`, `search-first`, `setup-agents-md`, `slack-channel-monitor`, `slack-standup-digest`, `technical-writing`, `theme-factory`, `writing-for-agents`, `writing-skills`, `xlsx` | `agent-memory`, `discord`, `doc-coauthoring`, `docx`, `evidence-based-citations`, `find-skills`, `github-agents-md-maintainer`, `gpt-researcher`, `handoff`, `incident-retrospective`, `iterative-retrieval`, `learn-from-code-review`, `notion`, `pdf`, `pdflatex`, `plain-english-content`, `pptx`, `research`, `research-brief`, `search-first`, `slack-channel-monitor`, `slack-standup-digest`, `technical-writing`, `theme-factory`, `writing-skills`, `xlsx` | `agent-memory`, `doc-coauthoring`, `docx`, `evidence-based-citations`, `find-skills`, `github-agents-md-maintainer`, `gpt-researcher`, `handoff`, `iterative-retrieval`, `learn-from-code-review`, `pdf`, `pdflatex`, `plain-english-content`, `pptx`, `research`, `research-brief`, `search-first`, `technical-writing`, `theme-factory`, `writing-skills`, `xlsx` |
| research | `find-skills`, `iterative-retrieval`, `jupyter`, `jupyter-notebook`, `research`, `search-first` | `find-skills`, `gpt-researcher`, `iterative-retrieval`, `news-digest`, `research`, `research-brief`, `search-first` | `find-skills`, `gpt-researcher`, `iterative-retrieval`, `jupyter`, `jupyter-notebook`, `news-digest`, `research`, `research-brief`, `search-first` | `find-skills`, `gpt-researcher`, `iterative-retrieval`, `jupyter`, `jupyter-notebook`, `news-digest`, `research`, `research-brief`, `search-first` |
| deployment-uv-docker | `agent-canvas-environment`, `canvas-extension-api`, `deno`, `docker`, `kubernetes`, `modern-python`, `npm`, `ssh`, `swift-linux`, `uv`, `vercel`, `vercel-optimize` | `agent-canvas-environment`, `canvas-extension-api`, `deno`, `docker`, `kubernetes`, `modern-python`, `npm`, `ssh`, `swift-linux`, `uv`, `vercel`, `vercel-optimize` | **GAP** | `deno`, `docker`, `kubernetes`, `modern-python`, `npm`, `ssh`, `swift-linux`, `uv`, `vercel` |
| memory | `agent-memory`, `github-agents-md-maintainer`, `handoff`, `learn-from-code-review` | `agent-memory`, `discord`, `github-agents-md-maintainer`, `handoff`, `incident-retrospective`, `learn-from-code-review`, `notion`, `slack-channel-monitor`, `slack-standup-digest` | `agent-memory`, `discord`, `github-agents-md-maintainer`, `handoff`, `incident-retrospective`, `learn-from-code-review`, `notion`, `slack-channel-monitor`, `slack-standup-digest` | `agent-memory`, `github-agents-md-maintainer`, `handoff`, `learn-from-code-review` |
