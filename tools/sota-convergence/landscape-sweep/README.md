# Landscape sweep harness

This directory runs the landscape-sweep lane of [recipes/saturation-sweep.md](../../../recipes/saturation-sweep.md)
from this repository, on Linux/WSL2 or macOS. Before this harness, the lane ran only from an agent-lab coordinator
session; agent-lab remains an alternative. The lane is a Claude Code Workflow with two model families:

- **Discovery.** Each due layer gets a Claude researcher and a GPT-6 researcher (through the Codex CLI).
- **Refutation.** A facts refuter checks every merged proposal, and two fit refuters, one from each family, judge
  it.
- **Critic.** A completeness critic runs after the first round, followed by at most one bounded follow-up round.

The harness then turns the run into the retained evidence that `scripts/saturation_ledger.py` binds. It never
writes `catalogs/landscape/`, `catalogs/sota-convergence/` or `research-state.json`. Those files, and publishing
the merged manifest, stay with the lane owners.

## Files

| File | Runs | Role |
| --- | --- | --- |
| `build_inputs.py` | checkout | Writes the per-layer inputs the workers read, `<work-dir>/inputs/<layer>.json`, and `layers.json`, from the frozen scope, the landscape catalogs, the ledger's last completed sweep, a baseline manifest, a freshness manifest and optional seeds. |
| `build_args.py` | checkout | Stages a run into the work directory: frozen dated templates, schemas, the GPT-6 runtime, first-round GPT-6 prompts, `staged.json`, `prompts_sha256.txt`, the compact `args.json` and `sweep.embedded.js`. |
| `sweep.js` | Workflow | The lane itself (`const A = args`; its header documents the args object). |
| `codex_call.sh`, `codex_job.py` | staged | The GPT-6 job runner the wrapper agents call (`start`, `wait`, `result`). |
| `codex_quota.py` | staged | A copy of the checkout's `scripts/codex_quota.py`, the account quota probe the runner's optional quota gate runs. |
| `make_prompt.py` | staged | Composes a GPT-6 prompt from the frozen templates. |
| `templates.json`, `schemas/` | staged | The prompts, with `<<DATE>>`, `<<LAYER_COUNT>>` and `<<SKILLS_CHECKED_AT>>` open, and the strict return schemas. `probe.json` is for the one-call lane probe. |
| `usage_record.py` | checkout | Runs the vendored `examples/claude-native/workflows/child-usage.mjs` over the run's transcripts and writes the sanitized usage record. |
| `convert.py` | checkout | Converts the run record into `returns.json`, `lanes.json`, `layers.json` and `survivors.json`. |
| `source_reviews.py` | checkout | Writes one upstream-provenance review per survivor (`gh api`; the public Hugging Face Hub API for a model repository). |
| `make_result.py` | checkout | Assembles `RESULT.json` for `saturation_ledger.py --append`. |
| `sweep_common.py` | checkout | Helpers shared by the checkout-run tools. |
| `seeds-20260926.json` | checkout | The seeds the 2026-09-26 run gave its workers. It is a record, and an example of the `--seeds` format. |

Everything is Python 3.9+ standard library, bash 3.2-compatible shell and node (for `child-usage.mjs` and the
tests). The runner uses no `flock`, `setsid` or `timeout` commands, so it runs unchanged on macOS.

## Model roles

| Label | Model and effort | Role |
| --- | --- | --- |
| `discover:<layer>` | Claude `opus` (claude-opus-5-5 on 2026-09-26), max, as `landscape-sweep-worker` | Discovery researcher: at most 6 proposals within 12 searches, 8 fetches and 40 GitHub API calls. |
| `gpt6-discover:<layer>` | Claude `sonnet` wrapper, max, running GPT-6-Astra at effort max | Second-family discovery, with the same prompt and the layer input embedded. |
| `refute-facts:<layer>` | Claude `opus`, max, as `landscape-sweep-worker` | Facts and identity refuter, within 8 searches, 10 fetches and 30 GitHub API calls. |
| `refute-fit:<layer>` | Claude `opus`, max, as `landscape-sweep-worker` | Fit and standing refuter, with the same budget. |
| `gpt6-refute-fit:<layer>` | Claude `sonnet` wrapper, max, running GPT-6-Astra at effort max | Second-family fit refuter. |
| `critic` | Claude `opus`, max, as `landscape-sweep-worker` | Completeness critic. It flags at most 8 layers for the follow-up round, whose labels end in `:followup`. |

Survival is two-family on fit. A proposal survives only when the facts refuter, the Claude fit refuter and the
GPT-6 fit refuter all vote not refuted. Every refuter defaults to refuted, and `convert.py` reads a vote the same
way: a missing vote, a vote whose `refuted` is not `false`, and a repository voted on twice with one refuting vote
all count as refuted. When the follow-up round proposes a repository again, that round's proposal and all three of
its votes replace the first round's; a vote missing from the follow-up is never taken from the first round. A
proposal that no returned vote refutes, but that a missing vote refutes, is refuted by absence: `returns.json` marks
the missing vote `{missing: true}`, the layer's `votes_note` names the proposal, and neither the ledger's known/new
split nor the next sweep's `previous_sweep` (`not_adjudicated`) treats it as refuted on merit.

Why the roles are split this way:

- Every Claude judgment role (discovery, facts, fit, completeness) runs on Opus, the strongest Claude model.
  - The facts role moved from Sonnet to Opus on 2026-09-27. Checking facts is verification, and the user's model rule keeps Sonnet for command wrappers and mechanical extraction.
  - Sonnet still runs the two GPT-6 wrappers, which only run commands and return the raw result.
- The GPT-6 lanes add a second family to discovery and to the fit judgment, where single-family bias matters most.
- The Claude judgment roles run as the **`landscape-sweep-worker`** agent type (`adoption/agents/claude/landscape-sweep-worker.md`): Opus at effort max, with `disallowedTools: WebFetch`.
  - The type keeps every other inherited tool, including Skill and context-mode's `ctx_*`. So pages come in through `ctx_fetch_and_index` and `ctx_search` as the page's own text, not as a smaller model's answer about the page.
  - The worker prompts no longer mention WebFetch.
  - Why: in the 2026-09-27 smoke 2, with WebFetch available and the token-lanes guidance injected, all 15 Claude page fetches used WebFetch and none used context-mode (counted per agent by the token lane).
  - The built-in `stack-researcher` type also excludes WebFetch, but it has no Skill tool, so the pinned skills the templates name would be lost.

The role split is the design of the 2026-09-26 prototype, with these 2026-09-27 changes. No measured comparison has tested it. Moving the facts role to GPT-6 would change a vote's family, which the survival rule and the copy check key on, so it needs its own comparison first.

Every `agent()` call names its model and `effort: 'max'`, so no stage inherits the coordinator's effort
([max-effort decision](../../../docs/decisions/2026-09-23-max-effort-default.md)). The vote objects in
`returns.json` name the model and effort each Claude refuter was measured at (its own child in the usage record),
not the requested ones. Without `--usage`, `convert.py` writes the requested alias and effort `null`.
`usage_record.py` exits 1 when a child ran at another effort (`CLAUDE_CODE_EFFORT_LEVEL` would override every
child; a skill whose frontmatter sets `effort`, such as `property-based-testing` with `effort: low`, lowers the
turns after it loads). `convert.py --usage` records each such worker as an `effort_deviation` retained failure of
its layer (the critic's of every layer), and `make_result.py` refuses the record unless every one is recorded so in
each of its layers. The same holds for a worker whose WebSearch call the session's cap refused (`web_search_capped`,
under Coordination).

The Sonnet wrappers only run three commands and return the raw result. `convert.py` checks each copy against the
file Codex wrote.

The harness default stays max. A lane may stage `codex.effort: "ultra"` in `staged.json`; the lane stager chooses
per the current GPT worker standard. Blind or isolated review lanes must stay at max, because ultra auto-delegates
in multi-agent v2 (openai/codex `rust-v0.159.2`, `codex-rs/core/src/session/multi_agents.rs:77-103`).
Ultra resolves each root request to the model catalog's `multi_agent_reasoning_effort`, else max for an
ultra-capable model (`codex-rs/protocol/src/openai_models/reasoning_effort.rs:12-35`,
`codex-rs/core/src/client.rs:863-872`): Astra and Sol 6.1 send xhigh (`codex-rs/models-manager/models.json:22,196`).
The runner validates effort against that pin's catalog, including namespaced aliases, and records staged `effort`
and resolved `request_effort` in `inputs.json` and `result`; changing effort reruns a completed job.
Ultra usage is `primary_thread_only`, even when delegation items do not appear; any collab/sub-agent item also
marks that status on other lanes. The counts remain available but do not establish complete delegated usage
(`codex-rs/exec/src/lib.rs:1636-1638`, `codex-rs/exec/src/event_processor_with_jsonl_output.rs:509-511,533-535`).
The model remains a per-run choice (`build_args.py --gpt6-model`,
default `gpt-6-astra`), recorded in `staged.json`, in each job directory and in every GPT-6 vote.
If staged settings change between binding inputs and launching the detached runner, the attempt is refused with
exit 2, failure kind `inputs_changed`, including invalid restaging; `exit`, `done` and `failure.json` record it.
Initial invalid settings are refused before any job state changes; a refusal against a running job leaves its
owned state intact. Other terminal refusals, including LIMIT, quota, missing Codex and missing gateway key, write
failure receipts. Start it again to bind valid new settings.

The templates tell each role which pinned skills to use (search-first and iterative-retrieval for discovery;
supply-chain-risk-auditor and fp-check for refutation, which takes evidence before any verdict, plus layer-specific
skills).
Each worker reports the skills it used in `skills_used`, and `returns.json` totals them in `skills_usage`.

`build_args.py` refuses to stage a run when the templates name a skill that `adoption/skills/manifest.json` does not
pin as kept or trial. The same check also refuses a pinned skill that the templates name but `TEMPLATE_SKILLS` omits.

The GPT-6 lanes run with `--ignore-user-config`, so per-skill `enabled = false` entries in a host's Codex
`config.toml` do not apply there. Which skills Codex lists inside the lane is untested; `skills_used` records what
each worker says it used.

### GPT-6 through OmniRoute (`--gpt6-provider omniroute`)

With `build_args.py --gpt6-provider omniroute --codex-host <HOST>`, the GPT-6 lane runs through the local OmniRoute gateway. OmniRoute pools the operator's accounts. The lane gets its own Codex home, so the host's interactive config never applies.

`build_args.py` writes `<work-dir>/codex-home/` with three files:
- `config.toml`:
  - the provider block: `model = "cx/gpt-6-astra"`, `model_provider = "omniroute"`, `model_reasoning_effort = "max"`, and `[model_providers.omniroute]` with a loopback `base_url` ending in `/v1`, `env_key = "OMNIROUTE_API_KEY"`, `requires_openai_auth = false` and `wire_api = "responses"`, plus a static `http_headers` table only when `--omniroute-header` is given (see [the framework instance](#staging-on-the-framework-instance-20129)). The fields follow the [Codex config reference](https://developers.openai.com/codex/config-reference).
  - the `[mcp_servers.*]` tables of `adoption/templates/codex.config.template.toml`. The checkout's own `tools/adoption/render_config.py` renders them for `adoption/hosts/<HOST>.json`: serena, ai-memory, socraticode, headroom, codebase-memory, qmd and context-mode.
- `stack-worker.config.toml`: the Codex worker profile (`--stack-worker-profile`, default `adoption/templates/codex.stack-worker.config.toml`), copied verbatim.
- `AGENTS.md`: the host's Codex user instructions, the managed block of `adoption/templates/codex.AGENTS.template.md` read through `tools/adoption/apply_codex_lane.py`'s `agents_block()`: the top rule, rtk-ai/rtk v0.50.0's `hooks/rtk-awareness-full.md` verbatim, and the RTK exactness exceptions. Codex reads `$CODEX_HOME/AGENTS.md` as global instructions, so without it the lane's model got neither the top rule nor RTK's instructions, which the native lane's workers get from `~/.codex/AGENTS.md`. `staged.json` records its `agents_sha256`.

What the lane config also sets:
- **`[features] shell_snapshot = false`.** Codex's shell snapshot writes the exported environment, the provider key included, into `<CODEX_HOME>/shell_snapshots/*.sh` with mode 0644 (`codex-rs/shell-command/src/shell_snapshot_exports.rs` at rust-v0.157.1). A GPT-6 probe reproduced this.
- **`[shell_environment_policy.filters] OMNIROUTE_API_KEY = "exclude"`.** Codex 0.157.1 applies its default `*KEY*`, `*SECRET*` and `*TOKEN*` excludes only when `ignore_default_excludes` is false, and that setting defaults to true (`codex-rs/config/src/shell_environment_policy.rs`, `codex-rs/protocol/src/shell_environment.rs`). Without the filter, a real key would reach every command the model runs.
- **Web search for GPT-6 Astra.** Astra runs Responses Lite, which carries no hosted tools, so search reaches it only as Codex's standalone web search (`web.run`). The lane therefore sets:
  - `supports_standalone_web_search = true` on the provider, which defaults to false for custom providers ([Codex advanced config](https://learn.chatgpt.com/docs/config-file/config-advanced));
  - `[features] standalone_web_search = true`, which is under development in 0.157.1.

  The capability flag alone enables nothing: OmniRoute must serve a compatible endpoint, and the parity check below has to show it working before a sweep counts on GPT-6 search through the gateway.

  Measured 2026-09-27: `web.run` POSTs `<base_url>/alpha/search`. OmniRoute release/v3.8.51 at `a58000c7` answers 404 there. Upstream PR #13788 adds the route, but answers from OmniRoute's own search registry, not OpenAI's hosted search: the keyless `duckduckgo-free` provider, unless a keyed provider is configured. Through that route, `site:` queries returned nothing and plain queries few results. GPT-6 fell back to fetched pages and the GitHub API through context-mode.
- **Skills.** Codex lists user skills from `$CODEX_HOME/skills` and `$HOME/.agents/skills` (`codex-rs/ext/skills/src/host_roots.rs` at rust-v0.157.1). In the lane, `$CODEX_HOME/skills` holds only Codex's `.system` cache; the pinned skills are in `$HOME/.agents/skills`, where `install_skills.py` puts them.
  - The lane's GPT-6 loads them with context-mode's `ctx_execute_file`. That tool refuses a path outside its project directory, here the runner's `<work-dir>/empty`, unless a `Read(...)` allow rule in `<project>/.claude/settings.json` names it (context-mode 1.0.169 `build/security.js`, `evaluateProjectContainment`, issue #852).
  - Without such a rule, the 2026-09-27 smoke's GPT-6 workers asked for their skills, were refused, and reported `skills_used: []`.
  - `build_args.py` writes `<work-dir>/empty/.claude/settings.json` with **one exact rule per file** under `$HOME/.agents/skills`. It follows symlinked directories, lists each real directory once, and leaves out any path containing `*` or `?`. `staged.json` records the root symbolically and the file count.
  - The rules are exact because context-mode also matches an allow rule against the raw path. A wildcard rule such as `<root>/**` would admit `<root>/../elsewhere` and every sibling path under the root. The test `test_context_mode_reads_only_the_listed_skill_files` runs context-mode's own matcher (set `CONTEXT_MODE_SECURITY_JS` to an installed `build/security.js`): listed files pass; siblings, outside files and `..` traversals do not. Its control shows the wildcard admitting the traversal.
  - The host's deny rules still apply.
  - Residual (context-mode 1.0.169): the matcher turns backslashes into slashes before matching, but the executor opens the literal Linux file name. A file whose name holds backslashes that normalize to a listed path would therefore pass too, as a GPT-6 re-check reproduced with a planted symlink. No rule can exclude it, because deny matching normalizes the same way. No such file exists, and creating one needs write access that `ctx_execute` already has.
  - The #852 boundary limits `ctx_execute_file` only. `ctx_execute`, which the stack-worker profile leaves enabled for the token practice, runs code with the user's own file access, outside Codex's read-only sandbox. The lane's `-s read-only` binds Codex's own shell tool, not its MCP servers.
  - A native restage of the work directory removes the file, because the native lane has no context-mode.

What the lane does not carry or allow:
- Project and hook trust are left out, because they describe the host's interactive client.
- `supports_websockets` stays unset. OmniRoute forwards the Codex client version only on its HTTP `/v1/responses` path.
- `--omniroute-base-url` must point at loopback.

Isolation limits:
- `CODEX_HOME` replaces the user-config location, but a trusted `.codex/config.toml` in the working directory and the system config still layer in.
- The runner works in `<work-dir>/empty`. It holds only `.claude/settings.json`, which context-mode reads and Codex does not, so no Codex project layer applies there. A host system config (`/etc/codex/config.toml`) would apply, so keep it absent on sweep hosts.

How the runner uses it:
- `codex_job.py` sets `CODEX_HOME` to that home, drops `--ignore-user-config` and adds `-p stack-worker`: `codex exec -p stack-worker --skip-git-repo-check -s read-only -m cx/gpt-6-astra -c model_reasoning_effort="max" -c web_search="live" ...`. Staged effort and search settings override these defaults and the profile.
- The key comes from `$OMNIROUTE_API_KEY` in the harness's environment. For a keyless loopback gateway, upstream's non-interactive setup with no login or API key, the staged placeholder `local-loopback` fills an unset variable; Codex's `env_key` only needs the variable to exist. `--omniroute-require-key` stages no placeholder, so a job without the variable ends with exit 6 before codex starts.
- `--quota-stop-percent` is refused with this provider: the quota probe reads the native login, not the gateway's pool.
- A job's `inputs.json` records the provider, so a gateway run never reuses a native job's result. It also records any provider headers, so a job finished under other headers is rerun, not reused.

Before a full run through the gateway, run the lane's parity check on the staged home, and do not claim a gateway result as max quality until it passes. The check covers:
- max effort reaching the upstream model, shown in the gateway's request log and the rollout's `turn_context`;
- the shell tool;
- an MCP call such as `ctx_execute`;
- `--output-schema` output;
- reported usage;
- whether hosted web search passes through for a custom provider.

#### Staging on the framework instance (20129)

The default gateway stays 20128: `--omniroute-base-url` defaults to `http://127.0.0.1:20128/v1`, the model to `cx/gpt-6-astra`, and no provider headers are sent. To stage the lane on the framework OmniRoute instance at port 20129, which compresses a request and then passes it to 20128 through its `sharedgw` node:

```sh
python3 $H/build_args.py --work-dir "$W" --sweep-id "$LANE" --date "$DATE" --smoke mcp-surfaces \
  --gpt6-provider omniroute --codex-host <HOST> \
  --omniroute-base-url http://127.0.0.1:20129/v1 \
  --gpt6-model sharedgw/gpt-6-astra-max \
  --omniroute-header x-omniroute-compression=allow-lossy
```

Use exactly one slash for this lane: `sharedgw/gpt-6-astra-max`. The established 2026-09-27 route check returned HTTP 200 with reasoning: 20129 forwards the bare `gpt-6-astra-max` through `sharedgw` to 20128, whose built-in Codex provider serves it at max. This route observation does not qualify a landscape sweep.

Every manual framework-lane invocation must pass `-m sharedgw/gpt-6-astra-max`. Under `-p stack-worker`, the profile's `model = "gpt-6-astra"` otherwise overrides the lane home's `model`. The established 2026-09-27 probe omitted `-m`, sent `gpt-6-astra` to 20129 and received six 401 responses. `codex_job.py` already passes `-m` explicitly. Profile precedence follows [openai/codex rust-v0.157.1, config loader L286-334](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/config/src/loader/mod.rs#L286-L334).

Check prompt parity without a model call using the staged lane home and the runner's working directory, `$W/empty`, for both commands. The control uses `cx/gpt-6-astra-max`; both commands pin the model with `-m` and with the requested prompt-debug config override. `prompt-input` sends no request, so the keyless placeholder fills the key variable:

```sh
cd "$W/empty"
CODEX_HOME="$W/codex-home" OMNIROUTE_API_KEY=local-loopback codex -p stack-worker -m sharedgw/gpt-6-astra-max \
  debug prompt-input -c model=sharedgw/gpt-6-astra-max > "$W/prompt-sharedgw.json"
CODEX_HOME="$W/codex-home" OMNIROUTE_API_KEY=local-loopback codex -p stack-worker -m cx/gpt-6-astra-max \
  debug prompt-input -c model=cx/gpt-6-astra-max > "$W/prompt-cx.json"
for f in sharedgw cx; do
  jq -S 'walk(if type == "object" then del(.id, .create_time) else . end)' "$W/prompt-$f.json" |
    sed -e 's#sharedgw/gpt-6-astra-max#<model>#g' -e 's#cx/gpt-6-astra-max#<model>#g' > "$W/prompt-$f.norm.json"
done
cmp "$W/prompt-sharedgw.norm.json" "$W/prompt-cx.norm.json"
```

If no lane home has been staged, use the installed `stack-worker` profile with `-c model_provider=omniroute` for both commands. Compare the rendered items' content, as above: without each item's `id` and `create_time`, with the model names masked, the two files must be identical. Equal item counts alone do not show an identical prompt. At this pin, `prompt-input` returns only `prompt.input`, so it does not expose `base_instructions` ([Codex rust-v0.157.1, prompt_debug.rs](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/src/prompt_debug.rs)). Compare the nonempty base instructions separately in `codex debug models --bundled`, applying the pinned namespace/longest-slug-prefix lookup: both names strip to `gpt-6-astra-max` and resolve to the same catalog entry ([manager.rs L745-780](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/models-manager/src/manager.rs#L745-L780)). Label that result as a source/catalog comparison, distinct from the rendered item comparison. Both debug commands run without model inference. Report only the two parity results and keep the prompt private.

The header option:

- `--omniroute-header NAME=VALUE` is repeatable and valid only with `--gpt6-provider omniroute`. It renders `http_headers = { "x-omniroute-compression" = "allow-lossy" }` in `[model_providers.omniroute]`. That is Codex's own provider field: Codex 0.157.1 adds these headers to every request to the provider (`codex-rs/model-provider-info/src/lib.rs:166-168`, `build_header_map` at 385-412, rust-v0.157.1; `model_providers.<id>.http_headers` in the config reference).
- Codex silently drops a header whose name or value is invalid. Its config loader also ignores a misspelled provider key, because `deny_unknown_fields` there (`lib.rs:135`) is a JSON-schema attribute only. `build_args.py` therefore checks every header before staging and reads `config.toml` back to compare the table.
- Only OmniRoute 3.8.51's per-request switches are accepted, lowercased and each once: `x-omniroute-compression` (`open-sse/handlers/chatCore/headers.ts:35-46`), `x-omniroute-no-cache` (`src/lib/semanticCache.ts:483-486` and `501-504`), `x-omniroute-no-memory` (`headers.ts:18-33`) and `x-omniroute-strip-reasoning` (`headers.ts:48-65`). Values are 1-128 printable ASCII characters without `"` or `\`.
- Other `x-omniroute-*` headers can carry a secret under a name with no credential word, such as `x-omniroute-self-hop` (`open-sse/utils/selfHop.ts:1-12`) and `x-omniroute-video-bridge-broker` (`src/lib/guardrails/videoBridgeBrokerAuth.ts:7-19`). So the names are listed rather than filtered by word.
- The values are recorded in `staged.json` (`codex.http_headers`) and in each job's `inputs.json`. The runner refuses to start when the lane home's `http_headers` differs from `codex.http_headers`.
- Both read-backs parse `config.toml` with `tomllib` (Python 3.11+). Staging already requires it. Without it, the runner refuses a lane with staged headers; a header-less lane still runs on Python 3.9, such as macOS's `/usr/bin/python3`.

What `allow-lossy` does (read from the installed OmniRoute 3.8.51 source, not measured):

- OmniRoute reads `x-omniroute-compression` from each request, case-insensitively (`open-sse/handlers/chatCore/headers.ts:41-46`).
- Without an opt-in, OmniRoute replaces lossy steps with the safe pipeline (session-dedup, lite). `allow-lossy` keeps the operator's plan (`open-sse/services/compression/lossyRequestPolicy.ts:29-47`).
- The other values are `off`, `default`, `engine:<id>` and a named combo (`open-sse/services/compression/planResolution.ts:24-58`). No value turns compression on while the instance's master switch is off (`open-sse/services/compression/strategySelector.ts:126-129`).

Known limits of the chained route:

- **Headers stop at 20129.** It forwards to 20128 only User-Agent, `x-opencode-*`, `x-session-id` and `x-title`, besides its node's own static custom headers (`open-sse/executors/default.ts:678-685`, `open-sse/utils/opencodeHeaders.ts:102-116`). `x-omniroute-compression` goes no further, and neither do Codex's identity headers (`session-id`, `thread-id`, `x-client-request-id`, `x-codex-*`). Codex's `prompt_cache_key` travels in the request body, and 20128's Codex executor keeps a key it receives and lists it among the body fields it sends upstream (`open-sse/executors/codex.ts:1509-1514` and `1550-1562`). The effect of the lost headers on cache hits is not measured.
- **Model metadata.** Both the builder and runner refuse a second slash, and a provider segment with characters other than letters, digits, `_` and `-`. Codex strips exactly one namespace segment, and only one of those characters ([openai/codex rust-v0.157.1, manager.rs L763-780](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/models-manager/src/manager.rs#L763-L780)); any other slug causes [fallback metadata, model_info.rs L99-150](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/models-manager/src/model_info.rs#L99-L150): a different prompt template, no Responses Lite, no multi-agent, a 272,000-token context window and a 10,000-byte tool-output truncation policy. Use `sharedgw/gpt-6-astra-max` and check prompt parity above.
- **Slashless aliases failed on 20129.** The established 2026-09-27 observation returned 401, `No active credentials for provider: codex`. Its cause was not established from source, so a slashless alias is not a supported alternative for this lane.
- **Null effort columns prove nothing.** OmniRoute populates `call_logs.reasoning_effort_requested` and `reasoning_effort_upstream` only when the response carries encrypted reasoning (installed OmniRoute 3.8.51, `src/lib/usage/callLogs.ts` L646-653). A non-null `reasoning_effort_upstream` is read from the body the gateway sent upstream, so it is positive evidence.
- **What a gateway sent upstream** is `pipelinePayloads.providerRequest` in `GET /api/usage/call-logs/<id>` at that gateway (`open-sse/handlers/chatCore/attemptLogging.ts` L513-516, `src/lib/usage/callLogs.ts` L1047-1053). It is recorded only while the gateway's detailed pipeline logging is on (`call_log_pipeline_enabled`, or `ENABLE_REQUEST_LOGS=true`; `src/lib/db/detailedLogs.ts` L56-64). `requestBody` is the body the gateway received from its client (`attemptLogging.ts` L575-582), not what it sent: 20128's Codex executor rewrites `reasoning.effort` from forced rules, the model suffix and its clamp (`open-sse/executors/codex.ts` L1451-1465).

Status: the route check above succeeded, but harness acceptance remains open; the manual verification probe without `-m` failed. Before a sweep counts on this route, run one probe job and one discover job through 20129 and record:

- a valid `last.json`;
- 20129's compression analytics for the request, showing a stacked plan with lossy engines rather than the safe downgrade;
- max effort in 20128's outbound request, evidenced by `pipelinePayloads.providerRequest.reasoning` in 20128's detailed call log, or by a non-null `reasoning_effort_upstream`;
- the cached-input-token ratio against a control job sent straight to 20128.

Keep failed attempts and their usage.

## Evidence contract

`saturation_ledger.py --check` and `--append` need the following. Each item names the part of the harness that
provides it.

- **Labels.** A completed sweep needs a completed `discover:<layer>` child for every recorded layer, and completed
  `refute-facts:<layer>` and `refute-fit:<layer>` children for every layer with proposals (prefix match, so
  `:followup` children count too). `sweep.js` uses exactly these labels. The `gpt6-*` wrappers and `critic` are
  extra children.
- **Usage.** The usage record is `child-usage.mjs` output wrapped as `{schema_version, measurement, child_usage}`.
  For a completed sweep, `child_usage.status` must be `complete`. `workflow_run` must equal the last segment of
  `child_usage.transcript_dir`, which `usage_record.py` rewrites to
  `<session-transcripts>/subagents/workflows/<run id>`. `lost_workers` must list exactly the incomplete children.
  When a Workflow pauses at a Claude usage limit, it re-runs its waiting agents after the reset under the same
  journal key; `child-usage.mjs` lists each earlier attempt that returned nothing under `superseded_attempts`
  (with `superseded_by`), not among the children, and still counts its usage in `by_resolved_model`. Usage such an
  attempt holds that `by_resolved_model` cannot count (an assistant message without provider usage or without a
  resolved model, or no transcript) is its `usage_issues` and makes the status `incomplete`.
  `make_result.py` also needs every child and superseded attempt measured at effort `max` alone, or recorded as an
  `effort_deviation` retained failure, and `measurement.exit_code` 0 (1 only for such recorded deviations). Every
  child and attempt must also carry a measured `web_search`, and each one with a capped WebSearch call must be a
  `web_search_capped` retained failure. Both are checked per worker and per layer: a `<role>:<layer>` worker's
  failure in its own layer, the critic's in every layer of the record.
- **Failures.** A failed part of the lane never leaves a clean layer. `convert.py` lists each layer's retained
  failures under `failures/<layer>` in `returns.json`: a lost round, a discovery family that did not return, a
  missing vote, a lost critic, a critic-flagged layer beyond the follow-up cap, a GPT-6 copy problem, and (with
  `--usage`) a worker measured at another effort than max (`effort_deviation`) or a worker with a WebSearch call
  the session's cap refused (`web_search_capped`); the critic's belongs to every layer. It gives
  that layer the reopen entry `{"trigger": "retained_failure", "ref": "<returns_ref>#/failures/<layer>"}`, which
  resets the layer's clean count. `make_result.py` refuses a layer whose failures lack that entry.
- **Returns.** In `returns.json`:
  - `discovery/<layer>` holds `{catalog, layer_id, proposed[], requirement_sha256, platform_profiles_sha256}`,
    with the two hashes copied from the scope frozen before the run.
  - `votes/<layer>/<i>/facts` and `.../fit` hold `{role, repository, refuted, ...}`. The fit object is the
    two-family vote, and its `claude` and `gpt6` members keep each family's vote.
  - Each layer's `discovery_ref` and every vote `ref` in the record is `<returns_ref>#/json/pointer`.
    `convert.py` writes them as `@RETURNS@#/...` and `make_result.py` fills in the path.
  - `proposed` must equal the set of adjudicated repositories, and every proposal gets both votes.
- **`prompts_sha256`.** This is `sha256(json.dumps(T, sort_keys=True, ensure_ascii=False))` of the run's frozen,
  dated templates. `build_args.py` writes it to `prompts_sha256.txt`. With the 2026-09-26 values filled in, the
  templates here give `PROMPTS_SHA256_CURRENT` in `tests/test_landscape_sweep_harness.py`, which changes with
  every intended template edit; the 2026-09-26 run's own value is kept there as `PROMPTS_SHA256_20260926`.
  That is a local check; the run's registered record is the evidence of what it used.
- **Manifest.** `manifest_ref` is the dated SOTA manifest built from `lanes.json`. The record's `date` is its
  `checked_at`, and the manifest's rows for this lane must equal each layer's proposals and survival.
- **Source reviews.** Each survivor needs one registered source review whose `layers` names the layer.
  `source_reviews.py` names a review `<owner>-<repo>.json`, as the 2026-09-23 reviews are named. When two survivors
  share that name (`acme/a-b` and `acme-a/b`), each gets a suffix of 10 hex characters of the sha256 of its
  `owner/repo`. A file that already reviews another repository is never overwritten. A model layer can keep a
  Hugging Face model repository (the 2026-09-26 sweep kept one), which `gh` cannot read. Its review,
  `hf-<namespace>-<name>.json`, pins the commit of the repository's default revision from the Hub's model-info
  endpoint `/api/models/<repo_id>` (the endpoint `huggingface_hub`'s `HfApi.model_info` calls). It reads the model
  card at that commit through the documented "Resolve a file" endpoint, anonymously, without the card's YAML
  metadata block.
- **Registration.** Every cited file is registered in `manifests/evidence.json`.

## Run it

The prerequisites:
- a Claude Code coordinator session with the Workflow tool (this repository's `.claude/settings.json` turns Ultracode on);
- the `landscape-sweep-worker` agent installed (`python3 tools/adoption/install_claude_profile.py --only agents`);
- `gh` signed in;
- `codex` on PATH, signed in natively;
- node and python3.

The work directory `W` holds prompts, host paths and raw Codex output, so it must sit outside every git repository.
Every tool here refuses a work directory inside one; Codex would also load that repository's `AGENTS.md` into the
lane. A repository marker is a `.git` directory holding `HEAD`, or a non-empty `.git` file. An empty `.git` doesn't
count: Codex's Linux sandbox creates empty `.git`, `.agents` and `.codex` mount targets under its writable roots,
`/tmp` included, while a command runs, and removes them afterwards (`codex-rs/linux-sandbox/src/bwrap.rs` at
rust-v0.157.1, `SyntheticMountTarget`). On 2026-09-27, other sessions' workspace-write Codex jobs made `/tmp/.git`
appear several times a minute, and the older check refused work directories under `/tmp` at random. Commands run
from this checkout.

```sh
H=tools/sota-convergence/landscape-sweep
W=/path/outside/every/repository/landscape-sweep-20261026
DATE=2026-10-26; STAMP=20261026; LANE=landscape-sweep-$STAMP
mkdir -p "$W/work" "$W/freshness"

# 1. Scope (no network): check the ledger, list the due layers, freeze the scope hashes.
python3 scripts/saturation_ledger.py --check
python3 scripts/receipt_staleness.py --json --out "$W/receipt-staleness.json" > /dev/null
python3 scripts/saturation_ledger.py --report --json --staleness "$W/receipt-staleness.json" > "$W/report.json"
python3 scripts/saturation_ledger.py --scope > "$W/scope.json"

# 2. Working files and pin freshness (network; gh signed in). Or download the latest catalog-freshness
#    artifact instead: gh run download <run-id> -n catalog-freshness-<run-id> -D "$W/freshness"
python3 tools/sota-convergence/extract_layers.py --repo-root . --out "$W/work"
python3 tools/sota-convergence/github_freshness.py --work-dir "$W/work" --workers 6
printf '{"lanes": [], "critic": null, "lost": []}\n' > "$W/freshness/lanes.json"
python3 tools/sota-convergence/build_manifest.py --work-dir "$W/work" --lanes "$W/freshness/lanes.json" \
  --out "$W/freshness/manifest-$STAMP.json" --checked-at "$DATE" --id "catalog-freshness-$STAMP"

# 3. Layer inputs (no network). --seeds is optional: {"<layer_id>": ["candidate or note", ...]}.
python3 $H/build_inputs.py --work-dir "$W" --freshness-manifest "$W/freshness/manifest-$STAMP.json"

# 4. Stage a one-layer smoke run and probe the GPT-6 lane with one cheap call.
python3 $H/build_args.py --work-dir "$W" --sweep-id "$LANE" --date "$DATE" --smoke mcp-surfaces
bash "$W/codex_call.sh" start gpt6-probe "$W/prompts/gpt6-probe.txt" "$W/schemas/probe.json"
bash "$W/codex_call.sh" wait gpt6-probe 600; bash "$W/codex_call.sh" result gpt6-probe   # expect exit 0, limit false
```

**5. Smoke.** In the coordinator session, call `Workflow({scriptPath: "<W>/sweep.embedded.js"})` with no `args`.
Then run steps 7 and 8 below on the smoke run into a scratch output directory, and check the summary: GPT-6
statuses `ok`, `gpt6_copy_check` `match`, `skills_usage` present. Archive the smoke before the full run:
`mkdir -p "$W/attempts/smoke" && mv "$W/gpt6" "$W/prompts" "$W/attempts/smoke/"`. `build_args.py` refuses to
restage while `gpt6/` holds jobs, because a finished job with the same id would be reused.

**6. Full run.** Stage the due layers, then call `Workflow({scriptPath: "<W>/sweep.embedded.js"})` again:

```sh
python3 $H/build_args.py --work-dir "$W" --sweep-id "$LANE" --date "$DATE" --due-report "$W/report.json"
```

The embedded copy carries the ~12 KB of templates and schemas, so they never pass through the coordinator's
context, and a resume needs only `Workflow({scriptPath, resumeFromRunId})`. Launching `sweep.js` with the contents
of `args.json` as `args` works too, at that context cost.

After the run, set `T` to the transcript directory the Workflow tool prints (`.../subagents/workflows/<run id>`)
and `RUN` to the run id. Copy the run record without reading it into context. It is large: the one-layer smoke
returned about 130 KB.

```sh
cp "${T%/subagents/workflows/*}/workflows/$RUN.json" "$W/run-$RUN.json"
```

Claude Code keeps the record there, as `tools/sota-convergence/transcript_audit.py` also documents.

```sh
# 7. Usage (needs node): the vendored child-usage.mjs over the run's transcripts, sanitized.
#    Exit 1: incomplete usage or a child not at effort max. The record is still written; make_result.py refuses it.
#    Its summary also names the workers whose WebSearch calls the session cap refused (web_search.capped_children).
python3 $H/usage_record.py --transcript-dir "$T" --out "$W/child-usage-$RUN.json"

# 8. Convert. Exit 3: possible private content, redact first. Exit 4: a GPT-6 output the workflow used is not
#    exactly the file Codex wrote, or a finished Codex output never reached the workflow (see the summary).
python3 $H/convert.py --workflow-output "$W/run-$RUN.json" --work-dir "$W" --usage "$W/child-usage-$RUN.json" \
  --out "$W/out" --limit "<run-specific note, e.g. usage figures or incidents>"

# 9. Merge the lane into the dated manifest: step 4 of recipes/sota-convergence-practice.md's six commands.
#    Review and publication (steps 5-6) stay with the lane owners.
python3 tools/sota-convergence/build_manifest.py --work-dir "$W/work" --lanes "$W/out/lanes.json" \
  --out "$W/manifest-$STAMP.json" --checked-at "$DATE" --id "sota-convergence-$STAMP"

# 10. Source reviews, written straight into the lane's evidence directory.
A=evidence/artifacts/$LANE
python3 $H/source_reviews.py --survivors "$W/out/survivors.json" --out "$A" --lane "$LANE" > "$W/out/reviews.json"

# 11. Retain and register (after the manifest is published at catalogs/sota-convergence/manifest-$STAMP.json).
mkdir -p "$A-attempts"
cp "$W/out/returns.json" "$A/returns.json"; cp "$W/child-usage-$RUN.json" "$A-attempts/"
python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, "scripts"); import host_receipts
for p in sys.argv[1:]: host_receipts.register_file(Path("."), p)' "$A"/*.json "$A-attempts"/*.json \
  "catalogs/sota-convergence/manifest-$STAMP.json"
python3 scripts/validate.py

# 12. Record: RESULT.json, append, check.
python3 $H/make_result.py --layers "$W/out/layers.json" --reviews "$W/out/reviews.json" --sweep-id "$LANE" \
  --returns-ref "$A/returns.json" --usage-ref "$A-attempts/child-usage-$RUN.json" \
  --manifest-ref "catalogs/sota-convergence/manifest-$STAMP.json" --work-dir "$W" > "$W/RESULT.json"
python3 scripts/saturation_ledger.py --append "$W/RESULT.json"
python3 scripts/saturation_ledger.py --check --base origin/main
python3 -m unittest tests.test_saturation_ledger tests.test_landscape_sweep_harness
```

`make_result.py` takes `--reopen reopen.json` (`{"<layer_id>": [{"trigger", "ref"}]}`) for the other reopen entries
the recipe asks for, such as the report's current `pin_moved` or `stale_receipt` triggers. Add them after reading
the report and the run; they are added to the `retained_failure` entries `convert.py` wrote, never in their place.
Record a stopped run by hand, as recipe section 4 describes (`status: stopped`, `lower_bound_usage: true`,
`votes: not_returned`, `lost_workers`). Retain the smoke's usage record under `$A-attempts/` as a run of its own.

Read these fields of `convert.py`'s summary before appending:

- **`retained_failures`** and **`reopened_layers`**: each layer's failures (`<round>:<cause>`), all of them reopened.
  `degraded_discovery`, `critic_lost`, `effort_deviations` and each vote's `notes` give the detail.
  `effort_deviations_unmapped` lists a worker at another effort whose label names no layer of this sweep;
  `make_result.py` refuses the record until it is resolved.
- **`web_search`**, **`web_search_capped`** and **`web_search_capped_unmapped`**: the run's WebSearch calls and
  capped calls, the workers with a capped call (each a retained failure of its layer), and any capped worker whose
  label names no layer of this sweep (`make_result.py` refuses the record until it is resolved). A capped worker
  means the session reached its WebSearch cap; say so in a lane limit.
- **`refuted_by_absence`**: per layer, the proposals refuted only because a vote did not return. Their layer's
  `votes_note` names them; they are candidates for the missing vote in a later sweep or the verdict wave.
- **`excluded_layers`**: every round of the layer was lost. Such a layer is left out of the record, so it neither
  counts nor resets.
- **`lost`**: every lost round, first or follow-up, as `<layer>:<round>`. `sweep.js` returns a lost follow-up round
  as `{lost: true}` too. `convert.py` refuses a return whose follow-up rounds do not match the critic's requests,
  so no round can go missing silently.

## Cost reference

No measured cost is quoted here. The 2026-09-26 one-layer smoke (run `wf_1753e674-5dc`, prototype harness) was
read only from that session's files, and a figure without a retained record is not evidence. Each run's own record
is its cost reference:

- `child-usage-<run>.json` (`usage_record.py`) for the Claude workers;
- `returns.json` `gpt6_usage` for GPT-6: `usage` sums the final attempt of each job and `earlier_attempts` the
  attempts the runner kept, with `usage_unavailable` counting attempts that reported none. Complete GPT-6 usage is
  the per-counter sum of the two.

Each counter is its own kind, so Claude and GPT-6 counters are never summed together. A full sweep has up to one
round per due layer, plus at most 8 follow-up rounds and a critic; the recipe classes the lane as high cost. Plan a
new run from the latest retained record, and say so when no record exists yet.

## Coordination

- **Web search.** GPT-6 jobs default to `-c web_search="live"`; `staged.json` `codex.web_search` can choose
  `disabled`, `cached`, `indexed` or `live` (openai/codex `rust-v0.159.2`,
  `codex-rs/protocol/src/config_types.rs:371-382`). The chosen mode is bound to inputs and recorded in `result`,
  so changing it reruns a completed job; an absent mode in older inputs means live. A gateway lane can stage
  `disabled` when its route rejects live search. Historical qualification (2026-09-26): `--search` before `exec`
  (the form this harness used through its first run) and passing no flag both send `external_web_access: false`, so
  search reads a cached index; only `web_search="live"` sends true. The evidence is the #332 qualification artifacts
  `evidence/artifacts/sota-refresh-20260926/codex/results/websearch-*.json`, cases W1 to W3. The 2026-09-26 run's
  GPT-6 lanes ran cached, and its record states that as a lane limitation.
- **Claude WebSearch budget (2026-09-26).** Claude Code caps WebSearch per session with
  `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION`, which the installed binary reads at session start (default 200).
  Workflow agents share their parent session's budget. The 2026-09-26 run used all 200 at 04:10Z, and later Claude
  workers searched nothing. The repository's `.claude/settings.json` now sets 1500, which covers a full run's
  budgets (about 1,120 searches). A session started before the change keeps its old cap, so start a fresh
  session, or headless `claude -p` lanes, for a sweep.
- **Codex quota.** The Codex account and its quota are shared with every session and host signed in to it. The
  semaphore (3 slots by default, `--slots`) bounds only the jobs of runs that share its lock directory. That
  directory is `<W>/locks` by default; pass the same `--lock-dir` to sweeps that run at the same time. Interactive
  Codex use and reviews are not counted, so check with the other sessions before a full run, and lower `--slots`
  while they are busy.
- **Agent concurrency.** `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS` bounds the Workflow's agents (this host
  starts at 8), and a layer uses up to three agents at a time. A GPT-6 wrapper waits at most 8 × 540 s for its job
  and then returns the job as unfinished. The vote then counts as missing and the layer is reopened, and a job that
  finishes later makes `convert.py` exit 4 (`file_only`). Keep the number of queued GPT-6 jobs small relative to the
  slots.
- **Usage limit.** A real Codex usage-limit error writes `<W>/LIMIT`. After that no job starts, and jobs still
  waiting for a slot end with exit 3. Stop the Workflow and tell the user the reset time, which the job's
  `stderr.txt` or its `error` event gives. An HTTP 429 with no usage-limit body counts as a limit too. Codex retries
  no 429 (`retry_429` is false for every provider, `codex-rs/model-provider-info/src/lib.rs` at rust-v0.157.1), so it
  prints `exceeded retry limit, last status: 429 Too Many Requests` for the first one, as an `error` or `turn.failed`
  event (`RetryLimitReachedError`, built in `codex-rs/codex-api/src/api_bridge.rs`). A pooled gateway answers so when
  its accounts are exhausted, and the report cannot tell that from a brief rate limit, so the first such job stops the
  sweep: `LIMIT` then holds a reason and no reset time. Read the account pool (`scripts/codex_quota.py` for a native
  login, the gateway for a pooled route) and remove `LIMIT` when it has capacity; after a usage limit, remove it only
  after the reset. The 2026-09-29 run had no such stop: nine of its twelve follow-up GPT-6 jobs ended in 429 after one
  or two seconds each, the Workflow finished its Claude follow-up stages (the round cost $88 at Claude list price, see
  the recipe's cost class) and six layers stayed reopened
  (`evidence/artifacts/landscape-sweep-20260929-attempts/gpt6-job-outcomes.json`). Watch for `LIMIT` while the
  Workflow runs, and stop it when it appears. Do not sign in again (provider state is shared).
  Record the stopped run as the recipe says. A failed job runs again at its next `start`; its failed
  attempt moves unchanged to `gpt6/<job>/attempts/<n>/` and stays in `result` and `gpt6_usage`. A finished job
  returns "already done" only with exit 0, a `turn.completed` event, a non-empty `-o` output file and the same inputs
  (prompt and schema sha256, model, effort, web search mode), so a resumed Workflow
  whose regenerated prompt differs gets a fresh GPT-6 vote, never a cached one for another claim.
- **Completion and recovery.** Exit 0 without a completed turn and non-empty output becomes harness exit 126,
  failure kind `incomplete`, with `result.status: "failed"`; the next start reruns it and retains the failed attempt.
  Legacy false successes are rejected by the same rule in both `wait` and `result` and archived unchanged. Successful output uses
  `result.status: "done"`. Codex only emits `turn.completed` for a completed turn and can write an empty final
  message or fail to write it (openai/codex `rust-v0.159.2`,
  `codex-rs/exec/src/event_processor_with_jsonl_output.rs:525-536,631-635`,
  `codex-rs/exec/src/event_processor.rs:31-46`).
  Native jobs use Codex's built-in OpenAI provider and its retry/idle defaults
  (`codex-rs/model-provider-info/src/lib.rs:63-65,492-510,532-551`). Both lanes retain the default-on connection
  retry feature (`codex-rs/features/src/lib.rs:1292-1297`), so Codex rides out a connection outage shorter than the
  idle budget; a longer one is stopped by the watchdog and retried once, budget permitting.
  Reconnect `error` JSONL events are not progress: connection retries emit them between sleeps of 5 to 60 seconds
  (`codex-rs/core/src/responses_retry.rs:18-19,71-96`,
  `codex-rs/exec/src/event_processor_with_jsonl_output.rs:447-458`). Configurable `codex.idle_timeout_s` defaults to
  1800 seconds, nearly four times the coordinator's observed 473 seconds of healthy silence on 2026-09-30;
  `codex.timeout_s` defaults to 4000 seconds for non-ultra lanes. An unqueued job fits the wrapper's 4320-second
  wait: even counting a default quota probe plus backstop (30 + 30), version check (60) and both grace periods
  (10 + 10) separately yields 4140 seconds. The deadline actually includes the version check and every probe.
  Ad-hoc research lanes may stage a larger total budget and need a caller that waits that long.
  When effort is ultra, absent settings default to `idle_timeout_s: 4200` and `timeout_s: 14400`; explicitly staged
  values remain in force. An ultra idle timeout of 3600 seconds or less is refused before initial state changes,
  because the upstream default multi-agent wait cap is 3600 seconds (`codex-rs/core/src/config/mod.rs:257`,
  `codex-rs/core/src/tools/handlers/multi_agents_v2/wait.rs:53-64`). A lane-local override of that upstream cap
  needs a correspondingly larger idle budget. The sweep wrapper cannot wait for the ultra total default.
  Idle expiry stops the process group with exit 125 and retries once. Capacity failures retry at most twice, with
  exponential backoff and jitter (30 seconds base, 120 seconds cap); a backoff or retry starts only with at least
  300 seconds remaining after the delay. Otherwise the original failure stays terminal. The total budget covers
  the version check, every quota probe, all attempts and backoff. When the deadline follows `turn.completed`,
  the runner waits up to `kill_grace_s` for a clean exit before stopping the group, because exec shuts down before
  writing `-o` (`codex-rs/exec/src/lib.rs:1318-1321`,
  `codex-rs/exec/src/event_processor_with_jsonl_output.rs:631-636`).
  Stopping a group whose members have all exited is complete on macOS although `killpg` reports EPERM there
  (apple-oss-distributions/xnu `xnu-12377.121.6` `bsd/kern/kern_sig.c` `killpg1` skips zombies and returns EPERM when
  nothing was signalled, where Linux signals a zombie silently): the runner treats ESRCH and EPERM alike, which the
  2026-09-30 macOS full-suite job on this branch had reported as exit 2 "refused" for every watchdog test whose group
  died at TERM.
  Usage-limit and HTTP-429 handling take precedence.
- **Quota gate (optional).** `build_args.py --quota-stop-percent 95` writes `codex.quota_stop_percent` into
  `staged.json`; without it the gate is off. With it, each job, after it gets its slot and before every attempt,
  runs the staged `codex_quota.py --json --gate 95`. That reads the account's usage snapshot through the native
  `codex app-server` method `account/rateLimits/read` (no model turn, no transcript, no credential file) and
  reports the gate when a window's `used_percent` reaches the percent, `rateLimitReachedType` is set or
  `ordinaryUsageAllowed` is false. The job then ends with exit 3 before codex starts, and `<W>/LIMIT` (when absent)
  and the job's `stderr.txt` name the reason, the used percent and the reset time: stop and tell the user, as for
  a usage limit. Every probe is kept in its attempt's `quota.json` (earlier attempts under `attempts/<n>/`), and
  `result` summarizes the current one as `quota`. A probe that
  fails (no snapshot within `codex.quota_timeout_s`, default 30 s, an error answer or a missing script) is recorded
  there and never blocks the job; the usage-limit rule above still catches a real limit. A running sweep keeps the
  runtime it was staged with, so a work directory staged before this gate existed has no gate.
- **Resume.** `Workflow({scriptPath: "<W>/sweep.embedded.js", resumeFromRunId: "wf_..."})` replays the unchanged
  agent calls from the cache.
- **WebSearch cap.** Claude Code allows one session at most `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION` WebSearch
  calls (default 200, from v2.1.212). The count covers the main conversation and every subagent, workflow children
  included. A capped call returns a notice that tells the worker to go on without searching; nobody sees an error
  ([tools reference, "Session search limit"](https://code.claude.com/docs/en/tools-reference#session-search-limit);
  [environment variables](https://code.claude.com/docs/en/env-vars)). The lane's own budgets allow far more. Each
  Claude discovery worker may make 12 searches (40 workers with the follow-up round: 480). Each facts and each fit
  refuter may make 8 (80 workers: 640). A full sweep may therefore make 1,120 searches before the critic, and the
  session's earlier searches count too. The 2026-09-26 sweep reached the cap at 04:10:13Z; after that no Claude
  refuter, critic or follow-up discovery worker got a search result. Before a full sweep, start the coordinator
  session with the variable set above the lane's sum plus the session's other searches (for example
  `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION=1500`; the value can be raised but not turned off). `/clear` resets
  the count, but not while a workflow is still running. `child-usage.mjs` counts each child's WebSearch calls and
  capped calls (`web_search`) from the transcripts. `convert.py --usage` records every capped worker as a
  `web_search_capped` retained failure of its layer; the critic's counts for every layer. `make_result.py` refuses a
  record in which a capped worker is not recorded that way in each of its layers.

## Privacy and token practice

- **Work directory.** Keep `W` private and never commit it. Codex thread ids, raw events, prompts with host paths
  and the run record stay there.
- **`convert.py`.** Rewrites work-directory, checkout and home paths to `<work-dir>`, `<repo>` and `~`. It then
  scans every output string with `scripts/validate.py`'s `PRIVATE_CONTENT` patterns and reports each match by
  pointer and kind, never its text, with exit 3.
- **`usage_record.py`.** Rewrites the transcript path to `<session-transcripts>/...` and refuses to write a record
  that still matches one of those patterns.
- **Token practice.**
  - Claude workers read the layer inputs from files; only the GPT-6 prompts embed them.
  - The Workflow args hold only templates, schemas and layer ids, and the embedded copy keeps even those out of
    the coordinator's context.
  - GPT-6 outputs are returned compact, and merged rows no longer repeat each family's full proposal.
  - Read a run through `convert.py`'s summary, not the record.

## Differences from the 2026-09-26 prototype

The prompt templates are the only part with a retained comparison to the prototype. Until the 2026-09-27 template edits (#385),
this package's templates filled with the run's values gave `PROMPTS_SHA256_20260926` in the tests (a local check),
and the run's registered record, `landscape-sweep-20260926` in `catalogs/saturation/ledger.json`, carries the same
`prompts_sha256`. On 2026-09-26 three unretained local checks were run (prompt bytes, the smoke's conversion,
`usage_record.py` on the smoke's transcripts); their outputs are not kept, so they are not evidence, and parity of
the smoke's conversion and of `usage_record.py` stays unverified.

The deliberate changes:

- **Parameterized paths and dates.** No path is hardcoded; every tool takes `--work-dir` or `SWEEP_WORK_DIR`, and
  the staged runtime uses its own directory. The date, layer count and skills-manifest date are template
  placeholders.
- **Portable runner.** The runner is portable (stdlib locks, sessions and timeout).
- **Usage-limit detection.** The runner reads Codex's `error` and `turn.failed` JSONL events. `codex exec
  --json` prints fatal errors on stdout, so the prototype's stderr-only check could miss a real limit; see
  openai/codex `rust-v0.155.1`, `codex-rs/exec/src/exec_events.rs`. Model content never counts. Codex runs without
  the caller's `RUST_LOG` (at trace level it logs model response data, `codex-rs/codex-api/src/sse/responses.rs`),
  and a stderr line counts only when it is an `ERROR`/`Error` line and no turn completed.
- **Job reruns.** A failed job reruns with its earlier attempt kept under `attempts/<n>/`; a done job is reused only
  for the same inputs; a running one is never started twice.
- **Timeout cleanup.** On timeout the job's whole process group gets TERM, then KILL after the grace period
  (`kill_grace_s`, 10 s), even when Codex itself has already exited, so no child keeps a slot or job lock.
- **Layer inputs.**
  - The fields have undated names (`previous_sweep`, `components_vs_upstream`, `seeded_candidates`,
    `upstream_checked_at`).
  - Trading pins are included.
  - Known-repository slugs are no longer cut by `rstrip(".git")`, which had shortened, for example, `qdrant/qdrant`
    to `qdrant/qdran` in 30 of 32 layers.
  - The previous sweep is the last completed one.
- **Placeholder filling.** Placeholders are filled in one pass, with no `$&` expansion. Merged rows drop
  `by_family`.
- **`convert.py` additions.**
  - A lost layer is excluded instead of being recorded as an empty retained layer.
  - Degraded discovery is reported.
  - Votes carry resolved model names from the usage record and per-round skills.
  - It adds `gpt6_usage`, the wrapper copy check and the method's lane limits.
- **Review repairs (2026-09-26).** A Claude Opus and GPT-6-Astra review of the first package found these, each now
  covered by a test:
  - A layer with a failed lane (every GPT-6 fit job failed, say) derived as clean. Retained failures now reopen it.
  - A repository proposed again in the follow-up kept its first-round proposal but took later votes one by one.
    The later round's proposal and all three of its votes now travel together.
  - A lost follow-up round vanished. `sweep.js` now keeps it as `{lost: true}`, and the critic's repeated layers
    get one round.
  - Vote efforts were written as max whatever was measured, and effort drift passed `usage_record.py`.
  - Wrapper commands did not quote the work directory. Every argument and redirection target is now
    POSIX-quoted.
  - `canon()` left owners whose names start with `http` (`httpie/cli`) uncanonical.
  - Two repositories could share one source-review file.
  - `make_result.py --reopen` replaced a layer's reopen entries instead of adding to them.
- **Record review repairs (2026-09-26).** The review of the 2026-09-26 record found two more, each now covered by a
  test:
  - The lane's WebSearch budgets exceed the session's WebSearch cap, and nothing recorded a capped call. That run's
    refutation phase, critic and follow-up round ran after the cap, and three layers still derived as clean.
    `child-usage.mjs` now counts capped calls, and `convert.py` reopens each capped worker's layer.
  - A proposal refuted only because the GPT-6 fit vote did not return counted downstream as refuted on merit: as
    known in later sweeps and as `previous_sweep.refuted` in the next discovery input. The ledger now reads the
    vote's missing marker.
- **GPT-6 review repairs (2026-09-26).** A read-only GPT-6-Astra review of the record's checkout found two more,
  each now covered by a regression test that failed before the repair:
  - A superseded attempt's assistant message without provider usage left the run `complete`, although
    `by_resolved_model` could not count it. `child-usage.mjs` now keeps such usage-integrity failures of superseded
    attempts (`usage_issues`) and reports the run incomplete.
  - `make_result.py` checked failure coverage over all layers at once, so one layer could lose its critic failure
    and its reopen entry (and count as clean) while another layer's `critic` failure satisfied the check. Coverage
    is now checked per worker and per layer.

## Tests

```sh
python3 -m unittest tests.test_landscape_sweep_harness -v
```

The suite uses synthetic fixtures and makes no network or model calls:

- A fake `codex` and a fake `gh` sit early on PATH; the fake `codex app-server` answers the quota probe.
  `tests/test_codex_quota.py` covers the probe itself against a stricter protocol fake.
- `sweep.js` runs under node with stubbed `agent`, `parallel` and `pipeline`.
- The converted evidence is appended to a synthetic ledger checkout with `saturation_ledger.py` itself.

Node, `shellcheck` and `BASH32_BINARY` (a real bash 3.2, as on macOS) are optional; each test that needs one is
skipped without it.
