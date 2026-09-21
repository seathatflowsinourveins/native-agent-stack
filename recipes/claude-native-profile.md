# Native Claude profile and foundation practice

This is the selected September 20, 2026 native profile for the existing
foundation. It combines the native client, task-scoped instructions, selected
upstream skills, existing context tools and bounded workers. It does not require
another scheduler, gateway, SDK or complete plugin bundle at session startup.

The [community candidate review](../docs/community-native-practice.md) records
source revisions, merits and exclusions. The [foundation catalog](../catalogs/foundation/manifest.json)
retains all sixteen layers and their actual acceptance boundaries. Installation,
native discovery, task correctness, interactive behavior and measured efficiency
are separate results.

## Native installation and terminal entry

Reuse a working native installation. For a new Linux/WSL machine, follow the
[official installer](https://code.claude.com/docs/en/setup) and the pinned
`claude-code` recipe in [the installation table](README.md). The accepted runtime
for this profile is 2.1.278; a later release needs its own selected checks.
Run `claude --version` and `claude doctor` from the intended project. Complete
the native sign-in flow; do not copy authentication stores from another PC.

Launch `claude` in the selected repository. This PC already has an
`ecosystem-claude --project /absolute/project` launcher that selects its existing
native scope and refreshes usage on return. That host launcher is a local
integration, not an upstream Claude executable and not installed by this recipe.
On another PC, native `claude` is sufficient; retain any accepted local launcher.

For Windows Terminal, add a named profile with paths resolved on that PC:

```json
{
  "name": "Claude Code (Ubuntu)",
  "commandline": "wsl.exe -d Ubuntu-24.04 --cd /absolute/project --exec /absolute/native/claude",
  "hidden": false
}
```

Use the actual distro, project and native executable. If the accepted local
launcher is selected instead, append its `--project /absolute/project` option.
Preserve other profiles and the user's terminal default. Windows Terminal
already supports Shift+Enter; use the official
[terminal configuration](https://code.claude.com/docs/en/terminal-config) only
for a demonstrated keyboard/display problem. Shell or tmux customizations are
not prerequisites.

For the matching Codex entry, add a separate `Codex (Ubuntu)` profile using the
same distro/project and the installed native `codex` executable. On this host,
the accepted `ecosystem-codex --project /absolute/project` launcher selects the
existing native Linux home. Preserve Desktop's separate home and native sign-in.
Both named profiles are now installed on the recorded host. Open them through
[Windows Terminal's upstream command interface](https://learn.microsoft.com/en-us/windows/terminal/command-line-arguments):

```sh
wt.exe -w 0 new-tab -p "Claude Code (Ubuntu)"
wt.exe -w 0 new-tab -p "Codex (Ubuntu)"
```

Both commands returned exit 0, and separate interactive Claude 2.1.278 and
Codex 0.155.1 processes were observed in the intended project on distinct TTYs.
The [terminal observation](../evidence/receipts/native-terminal-profiles-20260920.json)
records that narrow result. Opening the client does not complete sign-in or prove
interactive commands/HUD; use the session's native flow. If `wt.exe` is unavailable
as a WSL execution alias, Microsoft's documented `cmd.exe /c wt.exe` entry is the
portable fallback. Do not repeatedly run either command unless another tab is wanted.

## Small persistent contract; selected upstream skills

Merge the [short instruction example](../examples/claude-native/CLAUDE.md) into
the user's existing `~/.claude/CLAUDE.md`, preserving independent preferences and
managed imports. Keep project-specific tests, memory scope and domain policy in
that project's `CLAUDE.md`/`AGENTS.md`. Do not preload this catalog or duplicate
the installed tool inventory in every worker.

ECC's requested `everything-claude-code` URL resolves to `affaan-m/ECC`. Select
only `skills/search-first` and `skills/iterative-retrieval` at revision
`2b6e839771e53096d8451a213d40dc64ec8acac0`. They were already installed in the
starter project; this adoption makes them available to other projects too.
Use the official Codex skill-installer when present:

```sh
python3 /absolute/codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo affaan-m/ECC --ref 2b6e839771e53096d8451a213d40dc64ec8acac0 \
  --path skills/search-first skills/iterative-retrieval \
  --dest "$HOME/.agents/skills"
```

Resolve the installer's actual path; it refuses an existing destination. Preserve
project customizations instead of replacing them. Claude's official
[skill directory](https://code.claude.com/docs/en/skills) is `~/.claude/skills`.
On Linux/WSL, link each missing Claude skill directory to the installed shared
directory, or install directly there if Codex sharing is not needed. Check an
existing destination before creating a link. Compare the installed files with
the recorded source hashes in the candidate review. Claude loads the skill body
when it is invoked; available skill names/descriptions still have context cost.

Do not install the full ECC hooks/rules/plugin collection over the existing
RTK, Context Mode and ai-memory lifecycle handlers. The selected reference
repository `shanraisshan/claude-code-best-practice` supplies reviewed guidance,
not a runtime daemon. A source review is its relevant acceptance level.

## Supported quality defaults

For the selected native Codex 0.155.1 and GPT-6-Astra, this host saves the same
quality-oriented reasoning setting already selected in Desktop:

```toml
model = "gpt-6-astra"
model_reasoning_effort = "ultra"
```

Merge only the effort field into the intended Codex home. Preserve the native and
Desktop homes, account, model, permissions and project configuration. The installed
upstream `codex debug models --bundled` catalog explicitly supports `ultra` for
this model; its unconfigured native default is `low`. Generic API effort tables
are not the native client's complete model-specific catalog. Fresh native
`config/read` calls through the official SDK returned `ultra` in both homes,
including this project's configuration layers, without starting a model turn.

For Claude Code 2.1.278, merge this field into the existing user settings:

```json
{"effortLevel": "xhigh"}
```

Retain the selected `opus[1m]` model. The installed persistent schema accepts
`low`, `medium`, `high` and `xhigh`; `max` is a session-selected effort, not a
valid persisted `effortLevel`. Native adaptive thinking already applies when
`alwaysThinkingEnabled` is absent or true. Preserve that default and avoid fixed
thinking-token or global effort environment overrides. See [Claude model
configuration](https://code.claude.com/docs/en/model-config) and
[settings lifecycle](https://code.claude.com/docs/en/settings).

Saved effort defaults apply to fresh sessions. Already-open sessions can retain
their previous selection; Claude supports `/effort` for the current session.
Do not interrupt active work to reload a default. [Codex worker settings](https://learn.chatgpt.com/docs/agent-configuration/subagents)
and [Claude subagent frontmatter](https://code.claude.com/docs/en/sub-agents)
can override effort/model inheritance, so do not claim all workers run at the
coordinator's maximum. The short global instruction example makes task-based
acceptance, original-source verification and independent review persistent.

The [settings receipt](../evidence/receipts/native-quality-defaults-20260920.json)
records supported values, effective configuration and preservation checks. More
reasoning can increase time and tokens; no quality improvement or savings is
established until the actual task is evaluated.

## Architectural token practice

- Preserve the requested model and native cache, compaction and deferred MCP
  discovery. Match retrieval and worker scope to the actual task.
- Process large logs/data in code and return the required fields with recovery
  locations. Known focused reads can cost less than an indexed retrieval.
- Delegate independent work with explicit input/output contracts. Use owned
  writing checkouts and one integration owner; include worker usage and retries.
- Reuse checkpoints and accepted results. Design idempotency for each new
  external effect. Existing Dagu/systemd recovery does not prove arbitrary
  application or broker replay.
- Keep current native clients as defaults. Use the accepted Codex SDK when a
  programmatic workflow needs it; Claude SDK/DeerFlow additions require their
  own settings/tool/scope/usage contract. Multiple orchestration layers must
  not retry the same effect independently.

These choices follow [Claude cost guidance](https://code.claude.com/docs/en/costs),
[Claude subagents](https://code.claude.com/docs/en/sub-agents), the
[Codex SDK](https://learn.chatgpt.com/docs/codex-sdk) and the existing
[native harness contract](../docs/harness-defaults.md). No default savings
percentage follows from enabling them.

## Native acceptance and review

Inside an authenticated interactive Claude session, use `/context all`, `/mcp`
and `/usage` to inspect loaded context, connections and usage. Retain their
actual output. `/compact` performs model summarization: exercise it when useful
and verify the next task still has its required facts. Do not treat a headless
prompt containing `/context` as a zero-cost inspection command.

For an independent file review, the existing native CLI supports this shape:

```sh
claude -p --tools Read,Glob,Grep \
  --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
  --output-format stream-json --verbose --include-hook-events \
  --max-turns 12 --permission-mode dontAsk --permission-prompts none < review-prompt.txt
```

Use a trusted checkout and a bounded, explicit file list. Capture stdout/stderr
privately, preserve a deadline and the returned exit code, and require one
successful final result plus a grounded report. Verify the actual `system:init`
tool inventory is `Read`, `Glob` and `Grep`; a requested flag alone is not
execution evidence. Native hooks may still run;
the file tool list is not an operating-system sandbox. An SDK is unnecessary
for a single native review. A launcher must keep its own notices on stderr so
the upstream JSON/JSONL stream remains parseable whenever a native child runs.
The local launcher's `--check` mode prints a plain-text diagnostic and starts no
native stream. Installed plugin hooks can contribute guidance even when this
particular review disables MCP servers; count that overhead rather than claiming
that tool restriction removes every startup token.

Keep Codex and Claude reviews independent before comparing findings. Resolve
supported disagreements using the source and relevant checks. Reviewer agreement
alone is not correctness or an independent test. Record complete native usage,
including failed attempts, and preserve unknowns. Use the existing token report
after meaningful changes; do not add its native estimates to provider totals.

## Adoption, maintenance and rollback

Back up the current instruction file and terminal settings before merging.
Record the selected skill source hashes, actual command results, changed files
and preserved client settings. Restore only owned changes when rolling back;
remove only the two skill directories/links introduced by this adoption.
Keep the existing scheduled catalog maintenance and GitHub validation workflow.
Another framework or newer release needs a task-relevant reason and evidence.

## Recorded host results — September 20, 2026

| Check | Returned or independently checked result |
| --- | --- |
| `claude install 2.1.278` | Exit 0; standard native executable installed. Existing launcher retained. |
| `claude doctor` | No installation issues found after PATH repair. Intentional RAG embedding-prefix whitespace remains reported. |
| Pinned ECC skill installer | Both selected skills installed; source hashes match and native Claude initialization lists both. |
| Windows Terminal profile | One named Claude profile added; existing profiles, order and default preserved. Interactive use reached the native first-run sign-in screen. |
| Native Claude file review | Exit 0; successful result with actual Read/Glob/Grep tool inventory. Reported input, cache creation/read and output sum to 389,351 tokens. |
| Official Codex SDK file review | Exit 0; successful native read-only review. Total input plus output: 129,552 tokens; cached input is already included. |
| Short global instruction artifact | 1,175 → 418 tokens with installed tiktoken 0.14.0 / o200k_base: 757 fewer tokens for this exact artifact pair. |
| Local launcher checks | 20 passed, with no model requests. These verify the local integration, not upstream Claude behavior. |

Both reviews produced source-grounded findings that were resolved and checked.
Their different workloads are not a performance comparison. Their usage excludes
the coordinator, research and other workers. The instruction reduction is not a
provider saving or a per-session/lifetime counter. Interactive `/context`, `/usage`,
`/compact` and HUD behavior remain unqualified pending native sign-in.

Exact commands, returned output, hashes and scope are recorded in
[the profile receipt](../evidence/receipts/native-claude-profile-20260920.json) and
[command manifest](../evidence/artifacts/native-claude-profile-20260920/selected-commands.json).
This recipe is a reproducible guideline, not a claim that every future host or
every optional SDK has passed E2E.
