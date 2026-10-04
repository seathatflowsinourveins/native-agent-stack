# Decision: changelog parity between NativeStack and NativeStack2604 (2026-10-04)

**Decided by:** the user's directive of 2026-10-04, relayed by the command center (session `wsl-architecture-design`):
"we need all the sota features, latest changlogs, fully enalbed seamlessly within our naitve workflow for new wsl also".
The command center took the four decisions below on the user's own earlier choices, and session native-agent-stack-99's
unit U7 measured the parity and carried them out.

**Scope:**

- `adoption/new-wsl/client-config-map.json`: an own entry for `advisorModel` (an override), an authorization entry for
  `crossSessionInbound`, `service_tier` in the Codex practice entry;
- `AUTHORIZATION_PIECES` and three prose lines of `tools/adoption/new_wsl_client_config.py`;
- `adoption/new-wsl/templates/claude.settings.additions.json` and `codex.config.additions.toml`;
- the shared `adoption/templates/codex.config.template.toml` (one feature key);
- the Context Hub acceptance of the install plan (`accept.sh` and `install-plan.json`): it resolves `node` from the PATH
  the script prepares, because no plan command links Node into `${ECO_ROOT}/bin` (the delta read of PR 684);
- the tests of the builder and the prose and counts of `docs/decisions/2026-10-02-new-wsl-client-configuration.md`.

## Method

NativeStack's live `~/.claude/settings.json` and `~/.codex/config.toml` against `new_wsl_client_config.py --render --host
example --with-authorization-settings` of the PR 684 head with the You-should-know mod and the ConfigChange audit hook
folded in. Key names were compared, and values were read only for non-secret scalars; the cached upstream sources of
2026-10-04 (the settings reference, the Codex config schema of rust-v0.160.0 and `codex features list`) say what each key is.

Every enabled Claude Code key, environment name, hook event and mod of NativeStack was already rendered for 2604 except
the items this record settles. What stays different, and why:

| Item | State | Why |
| --- | --- | --- |
| `codex@openai-codex` plugin and its marketplace | NativeStack on, 2604 out | the map keeps the Codex plugin for Claude Code out, by decision |
| `feedbackDrafts` | a NativeStack value, 2604 default | an unattributed 2026-09-25 edit; 2604 keeps the 2.1.247 SendFeedback default |
| Codex `features.plugin_hooks = true` | NativeStack only | the installed Codex lists the flag as `removed`, default false: a no-op, and a stale key on NativeStack |
| Codex `check_for_update_on_startup = false` | NativeStack only | 2604's Codex is the self-updating install, so it keeps Codex's check |
| Codex `features.daemon_auto_start` | NativeStack true, 2604 false | hosts differ by design (the shared daemon is NativeStack's qualified queue) |
| `model`, `model_reasoning_effort`, PATH, OTLP endpoints, `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS` | differ | host choices and host capacity |
| `mcp_servers.hindsight`, `hooks.state` trust hashes, TUI notice state | NativeStack only | an evaluation server and host state |

NativeStack lags the shared template on four items that a re-apply fixes: `skillListingBudgetFraction`, nine
`skillOverrides` values, `env.MCP_TIMEOUT` and Codex `skills.max_context_tokens`.

## Decisions

1. **`advisorModel` is `opus` on 2604**, as on NativeStack. The user decided on 2026-10-04 (about 04:50Z, question tool):
   "ONLY USE fable when situation truly needed, otherwise use opus5.5 as main". The map renders it through its own
   `override` entry, as it does for `model`, so the shared template's value (`fable` until the pull request that changes
   it lands) does not move it.
2. **`crossSessionInbound = "accept"` is an authorization piece.** The setting takes `accept`, `hold` or `refuse`
   (settings reference; https://code.claude.com/docs/en/cross-session-messaging#control-inbound-messages), and `accept`
   delivers a message from another session without the approval hold that applies to a sender that is not in bypass mode.
   It is written only with `--with-authorization-settings` and never over a value the file already has. This overturns the
   wave-2 messaging ruling, which left the key unset because a message between two bypass-mode sessions delivers anyway,
   on the user's directive above and his yes on the Claude-Codex messaging posture of 2026-10-02.
3. **Codex `service_tier = "fast"` is on 2604.** The user chose the fast tier for every route that honours it on
   2026-10-03, and NativeStack runs it (measured through the gateway the same day: 61 against 33 output tokens per second).
   The 0.160.0 config schema calls `fast` the legacy spelling of the `priority` tier and says it still works. The tier
   counts 2.5 times against included usage, and the user's later policy of 2026-10-04 ("Fast where it matters") keeps bulk
   fan-out jobs on the standard tier in their own worker homes: this is the interactive default of the user config.
4. **Codex `features.analytics_plan_history = true` is on both hosts**, in the shared template. It is experimental and off
   by default (`codex features list`) and adds the seven-day five-hour and weekly allowance history to `/analytics`
   through one ChatGPT-backend request, not a model call.

## Evidence

- `python3 tools/adoption/new_wsl_client_config.py --check` exit 0: 396 pieces, 347 wired, 35 not wired, 14 authorization.
- `unittest tests.test_new_wsl_client_config` and the other builder, template and new-WSL modules: local integration checks,
  not upstream tests. The render test pins the four values; the authorization tests pin the fifth piece in every place
  that lists the class.
- The install plan's acceptance for Context Hub runs with `node` from the prepared PATH (`check_plan.py` agrees with the
  script): exercised in a scratch home with the real Context Hub 0.1.4, telemetry=false feedback=false, exit 0.

## What would overturn it

- Decision 1: the user names another advisor, or Fable 5.5 releases and benchmarks above Opus 5.5.
- Decision 2: a measured case of an unwanted message delivered without a hold, or the user asking for `hold`.
- Decision 3: the user asks for the standard tier as the default, or the gateway stops honouring `fast`.
- Decision 4: `plan_limit_history` returns nothing for our plans, or Codex removes the flag.
