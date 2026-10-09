# Decision: the token layer is the new distribution's client default (2026-10-04)

## Owner directive and native configuration practice

On 2026-10-04 the owner directed the token-efficiency stack to become the native default for future sessions.

They required clean upstream installation, default launch and invocation, real fresh-session end-to-end execution,
and monitoring of token use, saved tokens and repository invocation rates with upstream lifecycle commands and skills.
Their scope included Ultracode subagents and experimental teams; they asked to keep resolving the native workflow and
report readiness to the main session. [RTK's native initializer](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/init/codex.rs) and [Context Mode 1.0.169](https://github.com/mksglu/context-mode/blob/589d8214d56740a28b5f7bf63167743d586b0b40/README.md) supply the shipped interfaces.
This directive sets the configuration default below; installed components and unexecuted plans establish no savings.
SessionStart notices and task-specific SubagentStart carriers retain separate loading and lifecycle checks.
Destination loading, useful invocation and native counter observations are required for a new execution claim; the diagnostic is not a qualified upstream A/B result.

This record applies that owner directive to NativeStack2604's client configuration. The configuration is built by
`tools/adoption/new_wsl_client_config.py` from `adoption/new-wsl/client-config-map.json`. The workstation
(NativeStack) already runs these pieces.

## Decision

The builder wires the token layer by default. Each piece below was not wired in
[the 2026-10-02 record](2026-10-02-new-wsl-client-configuration.md), and this record replaces that ruling for the
named pieces only. The closed-world rule stays in force for every other piece: a piece that names a tool the
distribution does not install stays unwired.

| Pieces | 2026-10-02 ruling (superseded) | Wiring now |
|---|---|---|
| `RTK_TELEMETRY_DISABLED` (Claude Code env; the Codex shell `set` table of the user config and the stack-worker profile), the PreToolUse Bash hook `rtk hook claude`, and the six `Bash(rtk git push … -f/--force …)` deny rules | slot context-supply installs 'context-mode 1.0.169' (interim install), not 'rtk' | `slot:context-supply` with `directive` (this record): wired while the slot installs anything |
| The SubagentStart hook `token-lanes-subagent-start.py`, the default block and the five role blocks | the token-lane carrier names retrieval and compression servers (SocratiCode, jCodeMunch, headroom, codebase-memory) that this distribution does not install, and the wave-2 code-search ruling keeps it unwired here (change 7) | `practice` (python3 and seven files that `install_claude_profile.py` copies, byte-pinned in `adoption/hooks/claude/SHA256SUMS`) |
| The Claude Code SessionStart currency notice `currency-due-notice.py` and its file | the hook prints the due file that the daily stack-currency timer writes and no installed owner runs that timer, so it would never print | `practice` |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (new, in `adoption/new-wsl/templates/claude.settings.additions.json`) | none (no piece carried it) | `practice` |

### How each piece works

1. **The `directive` field.** A slot entry may name the dated record of an owner's directive. The builder then wires
   the entry's owner beside what the slot installs, but only while the slot installs anything. If the slot's deciding
   measurement ends with the slot installing nothing, the rtk pieces unwire along with it. `--check` fails when the
   record is not a file of the repository. The manifest is not changed: context-supply's decided default and its
   interim install (context-mode 1.0.169, amendment 3) stay as recorded.
2. **rtk's variable inside MCP server tables.** Copies of `RTK_TELEMETRY_DISABLED` inside a Codex MCP server's table
   now follow that server's own entry. A server that is not wired (SocratiCode, headroom, codebase-memory) therefore
   never gets a table holding only that variable.
3. **The token-lane carrier.** The carrier is installed whole. Its files are the byte-pinned files that the
   workstation runs, at the same hashes. The shared carrier also names lanes this distribution does not install:
   SocratiCode, jCodeMunch, headroom, codebase-memory and TOON. Its first line tells the agent that ToolSearch returns
   only the tools the agent is granted. A carrier filtered to the installed lanes (context-mode, Serena, qmd,
   ai-memory, semble and rtk) is the follow-up. It needs a second byte-pinned hook directory, and
   `install_claude_profile.py` would have to accept that directory. The name `jcodemunch` moves to the code-graph
   entry, which stays unwired, so the instruction blocks still leave out every sentence that names jCodeMunch.
4. **The currency notice.** The notice prints the due file that the stack-currency timer writes. The timer is
   installed by the commands in `adoption/lifecycle.md` (the `stack-currency.service` and `stack-currency.timer`
   templates); until it runs on the host, the hook prints nothing and exits within its 5-second timeout. The Codex
   copy (`codex/hooks/*`) stays unwired: `~/.codex/hooks.json` is written by ai-memory 2.5.2's own `install-hooks`, so
   this builder would be a second writer, and the template's handler has no reviewed trust hash.
5. **Agent teams.** <https://code.claude.com/docs/en/agent-teams> (read 2026-10-04) says that agent teams are off
   unless `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` is `1` in settings.json or the environment, and that `0` turns named
   subagents back into plain subagents. NativeStack's user settings carry `1`. The 2.1.284 probe found that a team
   needs an interactive lead. No probe has run on 2.1.289 yet.

### Wired before this record (no change)

The context-mode plugin and its marketplace, the Codex plugin and MCP server, and the Codex hook trust entries are all
wired through the context-supply interim install. The OTel environment is wired through slot
`otel-collector-contrib`.

## Not claimed

This record decides configuration, not merit. No token saving is measured on this configuration:

- On Harbor v0.23.0 (single agent, 36 SWE-bench Verified tasks), no tool reduced whole-task cost. context-mode's cost
  ratio was 1.34 [1.209, 1.456]. On tokens per accepted task, rtk was 0.955 [0.847, 1.078] (inconclusive)
  (`catalogs/foundation/new-wsl-architecture-20261001.json` L745 and L748).
- The subagent regime carries 81.3% of spend, and Harbor did not measure it (same file, L749).
- rtk's own `rtk gain` figures are the tool's self-report, not a provider count.

The deciding measurement is the preregistered multi-agent fresh-session comparison. Its F-token ablation arm removes
context-mode, the rtk hook and the token-lane hook. It is scored by the context-supply overturn rule
(`docs/decisions/2026-10-01-new-wsl-definitive-defaults.md` L171): the paired ratio of raw tool-output tokens entering
context per agent must lie wholly below 1, and the one-sided 95% lower bound of the task-success difference must not
fall below -0.10.

Provider-side token use on the distribution is metered by the install plan's OpenTelemetry Collector on
127.0.0.1:21317/21318. A probe at 2026-10-04T07:15:50Z found no listener there, so the collector's unit must be running
before any reading counts.

## Found and left unchanged

- **context-mode's marketplace pin.** A marketplace source accepts `ref` as a branch or tag and has no `sha` field
  (<https://code.claude.com/docs/en/plugins/marketplace-reference>, Plugin sources: a `github` marketplace source has
  `repo`, `ref`, `path` and `sparsePaths`; read 2026-10-04). The release tag `v1.0.169` (tag object 442f1eb6) is 133
  commits behind the interim pin 6f0cc684 (GitHub compare 6f0cc684...v1.0.169: `behind`, 133), so a tag `ref` would
  install an older commit than the pin. The distribution's plugin cache commit 9f3ecc8b is 21 commits ahead of 6f0cc684,
  and the compare lists only `stats.json`, which the manifest's interim pin allows. To pin 6f0cc684 exactly, the
  install plan has to check out a directory source at that commit, as NativeStack does. That is an install-plan
  follow-up, not a map change.
- The Codex role carriers stay unwired, and the 2026-10-02 reason for that changes. Before this record, a copy
  filtered of the unwired names failed `cwd_rule`, `exact_shapes` and `f4_block`. With rtk wired, the filtered
  `stack-researcher.toml` loses one sentence (the jCodeMunch one) and keeps all three rules, but it no longer matches
  its pinned hash. `stack-verifier.toml` names no tool that is not wired. Both roles are left to the filtered-carrier
  follow-up, and the map entry's reason says so.

## Apply (not run by this record)

Apply from current `main`, never from an older checkout on the destination:

1. Run `python3 tools/adoption/new_wsl_client_config.py --apply --host <host file> --dry-run`, then run it again
   without `--dry-run`. The tool backs up every file it changes.
2. Put `rtk` on the PATH that the rendered settings give, at the pinned release. The first directory of that PATH is
   `${ECO_ROOT}/bin`, then `~/.local/bin`, then the mise shims. Then check `command -v rtk`, `rtk --version`,
   `rtk init -g --show` and `rtk verify`.
3. Check that `~/.claude/hooks/token-lanes*` match `adoption/hooks/claude/SHA256SUMS`, and that a fresh session's
   subagent receives the SubagentStart block.
4. Install the stack-currency timer by the commands in `adoption/lifecycle.md`, and start the collector's unit.

## Counts

`--check` now counts: 404 pieces, 354 wired (207 practice, 147 through a slot), 35 not wired (0 through a slot that
does not install, 35 by their own entry) and 15 authorization pieces. The 2026-10-02 record's counts sentence and its
`--check --markdown` tables are recounted in the same change. The branch `c5/new-wsl-codex-0160` edits the same
sentence, so whichever of the two lands second recounts it.

## What would overturn it

- An F-token result that fails the overturn rule above. The directive is then removed, and the pieces return to their
  2026-10-02 rulings.
- context-supply resolving to no layer. The rtk pieces unwire with the slot automatically.
- A filtered carrier for the installed lanes. It replaces the shared carrier on this distribution.


## Retained scope after PR833 — 2026-10-08

The Harbor/token-component selection and future comparative retention gates in this dated record are historical. Foundation selection/readiness follows upstream evidence and the maintained vendor installation/check; its earlier results, usage boundaries and wiring evidence keep their original scope. Read the [October6 supersession record](2026-10-06-upstream-evidence-over-local-evaluation.md) with the [October7 amendment](2026-10-07-clean-upstream-install-finalizes-a-candidate.md) for the current rule. This appended pointer preserves the preceding historical text and line citations. The [daily decision/receipt/correction index](2026-10-08-decision-record-index.md) keeps the original and replacement evidence findable.
