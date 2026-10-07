# Held-out skill-routing prototype

This local plugin is inactive in every production template. It contains no
registration, installer, permission decision or model call. Its command requires
the explicit `--benchmark-hints` treatment flag; without it the command returns
zero before reading runtime data. Global activation requires B13 and the command
center's review/ACK. Production routes remain description/native discovery and
the existing pointer until then.

## Source and demonstrated gap

Vendor organization discovery came first. Reviewed official interfaces are
[Claude hooks](https://code.claude.com/docs/en/hooks) and
[Codex hooks](https://developers.openai.com/codex/hooks), with Codex schemas at
`a956835d020762cb2b570053af06f643a11c0ecc` under
`codex-rs/hooks/schema/generated/{user-prompt-submit,post-tool-use,subagent-start}.command.output.schema.json`.
The existing native wrapper and blind exclusion are
`native-agent-stack@ecfa112764c664d35377dd66b8cfcb67e5a94d60:adoption/hooks/claude/token-lanes-subagent-start.py:35-45`.
Context-mode 1.0.169's formatter is a PreToolUse implementation, not a serializer
for these events; each output here uses the exact native event name.

The closest maintained reviewed framework is
[Assembly at aba8bed](https://github.com/alex-macra/claude-codex-skills-assembly/tree/aba8bedadd83998cd2004838683ee41eaa449c1f):
MIT at LICENSE, an unchanged UserPromptSubmit executable at
`hooks/skill-activation.py:644`, Linux/macOS installation documented in README,
and five successful platform CI checks at that pin. Releases/tags queries returned
empty. Its supported catalog/routing overlay is useful for the unchanged
prompt-only comparator. It does not consume our workflow-row format, tool events
or verified role grants. Its opt-in installer bundles guards and listing caps;
we do not run it or import its unrelated workflows. Keep its executable and
catalogs unchanged in a separate owned comparator root.

[Diet's showcase at 07f75ce](https://github.com/diet103/claude-code-infrastructure-showcase/tree/07f75ce3c301259e857343596e7883b8ce5a9f50)
has a Codex adapter, so Claude-only would be an incorrect characterization.
That adapter can block and synthesizes Edit events; optional activation paths
call models. No release was returned and the pinned GitHub workflows path was
unavailable. It is a reference, not a selected complete S9 framework.
The bounded review found no complete fit; it establishes no ecosystem-wide
absence. No maintained framework is forked or rebuilt by this prototype.

## Runtime interface

`hooks/skill-routing.py --client claude|codex [--lane NAME]`
reads native hook JSON from stdin. The default manifest is the caller's project
root `adoption/workflow/manifest.json`. An explicit `--manifest` selects the same
canonical layout in an owned qualification fixture; it is not a new pin store.
The S1 dependency supplies `schema_version: 1`, `kind: sota_workflow_manifest`,
`trigger_syntax: python_regex`, typed `uses`, triggers and measure gates.

Only kept/trial rows and registered kept/trial skills qualify. Central client
listing/implicit-invocation policy is preserved. Whole-row `pending_skills` and
lane-specific `pending_lane_dependencies` stay inert. Coordinator-only refs are
excluded in child callbacks. Input, files, patterns, matching time, context and
skill count are bounded. The output contains fixed text and safe registered
skill names only; prompts, commands, paths, role bodies and tool output are
never echoed. There is no state store or transcript read.

Main callbacks require a nonempty native channel list in their actual row/lane.
An empty/missing lane or an `inert` ultracode stage cannot become active through
the treatment flag. Child callbacks require the actual active ultracode stage
and matching verified role; main callbacks cannot select a child-stage object.
Malformed trigger lists/members and measure containers are silent. Each trigger
list has at most 16 entries, and every regex/glob attempt shares the 100 ms match
deadline, with an individual timer capped by the remaining budget. File reads
and native-process startup remain outside that matching budget.

Optional `triggers.skill_intents` maps canonical row skill names to bounded regex
lists for UserPromptSubmit. When present, only a named matching skill qualifies;
an empty map hints nothing. Without the map, the row's relevant skill set applies.
This prevents the CI and PR-comment skills from being emitted together merely
because one outcome matched. Fetch-only tool events still remain silent.

Unknown/malformed data produces no output and exits zero. POSIX file reads use
explicit nonredirected project/user-role roots and parent-directory checks before
nonblocking/no-follow opens and regular-file validation. An explicit manifest
locator must be absolute and retain the canonical layout. Redirected roots or
`adoption/workflow`, skill-store or agent parents are refused, without reading the
redirected file. These checks assume cooperating processes, rather than forming
a race-proof filesystem sandbox. Regular-file I/O
latency still depends on the filesystem. Regex timeboxing uses the maintained
Assembly design as a reference, while matching our different row schema.

Path hints use Python 3.13's unchanged
[`glob.translate`](https://docs.python.org/3.13/library/glob.html#glob.translate),
with recursive segments and hidden paths enabled, a `/` separator and case
sensitive matching. The repository-supported Python line is 3.13
(`adoption/manifest.json:13-18`); source inspection observed python3 3.13.16 on
this qualification host. Older Python makes path hints silent. The supported
subset is relative literal components, `*` and complete `**` components. Brace,
extglob, character-class, `?`, backslash and parent-reference patterns are silent.
This avoids a custom parser and does not claim parity with every native glob
extension. Local fixtures cover zero/multiple intervening directories and ensure
single `*` does not cross a separator; actual native path-rule controls remain
part of qualification.

Native relative edit paths resolve from the event's validated `cwd` inside the
project; missing, relative, outside or redirected cwd is silent. Codex's patch
callback carries raw patch text in `tool_input.command`, verified in
`openai/codex@a956835d020762cb2b570053af06f643a11c0ecc:codex-rs/core/src/tools/handlers/apply_patch.rs:290-295,437-450`.
The previous `input`/`patch` fixture shape was unsupported and is now a negative
control. The replacement is an authored upstream-shaped fixture, not a fresh
native callback. No instruction body or patch text appears in a hint.

Claude child hints require a registered canonical role plus matching on-disk
project/user role metadata with an explicit Skill tool. Missing/wildcard/inherited
tools are not proof. Preloaded refs receive no redundant hint. Blind roles and
the blind lane are silent. Native Codex child capability remains pending S10;
a same-named Claude definition cannot establish it, so Codex child hints are
silent. Main Codex hints use its native skills discovery policy.
Inert/planned-ultracode previews do not establish a caller. The current S1
Skill-grant previews have no accepted native caller, so their child channel
remains pending even when a generated role file exists.
Project definitions keep native priority. The global fallback uses the explicitly
selected `CLAUDE_CONFIG_DIR/agents`, or `~/.claude/agents` when unset; a custom
profile cannot borrow the default profile's grant. Only the public path override
is inspected. Settings, authentication stores and runtime CLI override policies
are not read, so the file capability check is source evidence; the exact native
qualification must still observe the role and its effective grant.

Fetch-only reads, including `gh pr view`, `gh api` and `gh run view --log-failed`,
are silent: PostToolUse contains no original user intent and cannot distinguish
address/repair from list/summarize. Clear edits and matched action commands can
qualify. B13 retains these fetch-only negatives. A measured comparison can
overturn this conservative choice; no extra session store or model call infers
missing intent.

## Qualification and deployment boundary

The native Claude local-plugin hooks are in `hooks/hooks.json`; no template or
host references them. The passive `codex-hooks-proposal.json` must be rendered
with a reviewed absolute plugin path and appended after existing groups,
preserving group/handler indices. It grants no trust. The Codex SDK trust/apply
ticket is unresolved; a treatment whose hook was skipped is untested, not a
zero-gain verdict.

Frozen cases and native harness preparation live in
[`tools/skill-routing-b13`](../../../../tools/skill-routing-b13/README.md).
Only after prerequisite qualification may the command center run B13. Each
client must show an actual hook-firing positive control, load-rate gain above
zero, adjacent-negative false-hint rate at most 10%, and no task pass-rate
regression. Keep actual failed attempts, counters and provider identities.
Native discovery, source inspection, local fixtures and model efficacy remain
separate evidence classes.

Rollback removes the explicitly added plugin/hook groups after matching their
reviewed definitions; it does not mutate unrelated hooks or trust indices.
