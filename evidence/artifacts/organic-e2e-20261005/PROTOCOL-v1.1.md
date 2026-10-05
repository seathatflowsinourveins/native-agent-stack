<!-- The delivered text, verbatim except that the home-directory prefix is written as ~ (4 occurrences), as scripts/validate.py's personal-path rule requires. Delivered bytes: sha256 946b543f64c06857cc86628cc1fd5d904aee448c2c3201dace49656de21d83b7, kept outside the repository. The delivered text ends mid-sentence in RP9; sections 15 and 16 were not delivered and are not reconstructed. -->

# Organic-invocation E2E protocol v1.1 (NativeStack2604)

- **ID:** organic-e2e-v1.1-20261005.
- **Status:** written 2026-10-05 at about 17:15Z as a read-only design. No v1.1 trial has run.
- **Supersedes:** organic-e2e-v1-20261005 (`protocol-v1-adjudicated.json`, sha256 1154e17400c0bb67…). This text is self-contained: a v1 rule that is not restated here is void.
- **Task cards:** `suite-v1.json` (98 items, sha256 cd26427ae9cd7c89…), amended in §6.
- **Inputs:**
  - `critic-v1.json` (3909feb5c1b60ae3…, 24 findings);
  - `AMENDMENT-U1-native-arm.md` (db3ca7e1ef9aa405…);
  - CC item `task-ns2604-coop-20261005T160128Z`, with rulings (b) and (c) of `144245Z` (U1 supersedes (b));
  - the retired `pilot_run.py` (f855731ba98f885f…) and `pilot_grade.py` (25c06843fd079c62…);
  - `~/code/native-agent-stack/AGENTS.md:3`.
- **North-star action served:** the readiness headline and the per-tool env-versus-native rows. Two things need them: the CC's rules PR, and the final verified E2E, targeted for 10-06 18:00Z to 10-07 (CC 160128Z §2-3). Both put the paper lane on a clean, non-overlapping native stack.
- **Evidence marks:**
  - [doc] read at the cited source;
  - [obs] observed by a read-only query on 2026-10-05, 16:20-17:15Z;
  - [nv] not verified.

## 0. What changed from v1
1. U1 is merged into every cell. The native arm is the READY arm; the env arm is a single-factor comparison (§2).
2. The runner is promptfoo 0.123.1, one eval per cell, launched by `promptfoo eval` with --repeat, -j and --no-cache.
   - Each cell is an `exec:` launcher, except the app-server cell, which uses promptfoo's own provider.
   - Retries are off.
   - pilot_run.py and pilot_grade.py are retired (§4.1).
3. The fixture is origin/main 9e955327 (§4.2):
   - root and nested instruction files and `.claude/` are stripped;
   - each trial runs in a random neutral path;
   - fixtures are kept until grading.
4. Launch lines (§4.4):
   - the CL2 line is fixed;
   - Codex `-c otel.environment` is allowed, as the join key;
   - effort is read from Loki (Claude) and from the gateway (Codex).
5. Graders use native sources only, plus three rules: parsing of ctx_* inputs, realpath matching of SKILL.md reads, and code-mode nesting (§7).
6. New provenance tags: fixture-directed, agent-definition-directed and store-directed. All three are excluded from native U (§5 R1).
7. Containment: R8 is enforced before execution, the watcher becomes a detector, and auto-memory writes are exempt (§8).
8. Budget: the Claude pilot is at most 14 sessions in all, and the comparison arm runs mainly on Codex. T = 900 s, and every launch is gated by rate_limit_event read inside the lock (§9).
9. The Codex cells for serena, codebase-memory and promptfoo are dropped until those servers are callable (§4.4, R6).
10. This revision adds findings of its own (§12).

## 1. Authority, scope and evidence classes

**Authority:**
- **U1** (the user's directive of about 15:12Z, described at U1:5-9): a slot is READY only on organic use in the native arm, as native telemetry shows it (U1:20).
- **CC 160128Z §2:** the env arm decides whether the harness token-lane text stays.
  - If the native arm chooses a tool, the harness line that names it is redundant, and the CC removes it in a rules PR.
  - If it does not, the tool gets one upstream-native fix, then goes through rule (c) (T14).
  - The per-tool env-minus-native difference is reported in the adjudicated row (M13).
- **AGENTS.md:3:** E2E and A/B run on upstream harnesses (promptfoo for LLM A/B), never a self-written runner. promptfoo owns paired skill verification in both clients (definitive-manifest.json:2676).

**Evidence classes**, never pooled:
1. Native-arm organic trials: the only READY evidence.
2. Env-arm trials: comparison only.
3. Prompted runs (the 2026-10-04 E2E, oracle runs, probes, canaries): never organic.
4. v1-runner captures (§12.1): stage-0 replay material only.
5. Field activity (S11).

**Host stance:**
- The E2E changes no host configuration surface: CLAUDE.md, AGENTS.md, settings, config.toml, hooks, hook trust, skills, MCP configuration, the Collector allowlist or project trust. Each such change is a proposal under RP4.
- The E2E writes only to:
  - the run root, `~/.local/state/native-agent-stack/coordination/ns2604-coop/organic-e2e-20261005/runs/<run_id>/`;
  - NEUTRAL_ROOT;
  - per-trial clones.

## 2. Arms

### 2.1 Native arm (the READY arm)

**What a session has:**
- The installed tools with their own surfaces only: MCP server and tool instructions, tool and skill descriptions, plugins (including plugin agents) and tool-native hooks.
- No harness instruction text: no user or project CLAUDE.md, no AGENTS.md and no injected routing carrier.
- A task prompt that names no item.

**Harness-authored surfaces that stay loaded.** Removing them would also drop native surfaces, so their effect is tagged instead (R1):
- the user agent definitions in ~/.claude/agents. Seven of the eleven name lane items [obs]: evidence-reviewer, isolated-builder, landscape-sweep-worker, security-reviewer, source-scout, stack-researcher and stack-verifier.
- the skills native-stack-research, native-stack-worker and standing-delegation. Their bodies name no lane item [obs].

**Claude mechanism:**
- Each trial gets a `--settings` file with `"claudeMdExcludes":["~/.claude/CLAUDE.md"]`. Never `--bare`.
- U1's probe at 15:26Z: the control saw "# Native engineering defaults"; the native arm saw nothing.
- The probe stands while ~/.claude/CLAUDE.md (sha256 b86ea2c4655637fa…, mtime 05:20Z) and ~/.claude/settings.json (861959ff0e49803f…, mtime 04:46Z) keep those hashes at stage 1 [obs]. If either changed, one new probe is needed, and it counts toward the 14.
- ~/.claude has no rules/ or output-styles directory, and the user CLAUDE.md has no @ imports [obs].

**Codex mechanism:**
- A per-trial CODEX_HOME clone without AGENTS.md (§4.3). No switch disables that file (U1:43).
- ~/.codex/AGENTS.md changed at 16:18Z (sha256 63e96b603c6a6dde…), after U1's 15:28Z probe [obs], so stage 2 re-runs the Codex probe.

**Validity check on every native trial.** The trial is invalid (contaminated) if any of these harness markers appears where the client records loaded instructions:
- Markers: "Native engineering defaults"; "Top rule: research convergence first"; "native-agent-stack:codex-user-instructions"; "native-agent-stack:session-lanes"; "native-agent-stack:rtk-upstream"; "TOKEN LANES"; "# Repository work".
- **Claude:** the transcript's `attachment.type == "instructions"` records (`attachment.files[].content`). [obs] The env-arm transcript for pilot1env jcodemunch carries the markers there; the native transcript has none.
- **Codex:** the rollout's instruction messages. [obs] The real-home rollout has the codex-user-instructions marker 3 times; the clone rollout has none.

### 2.2 Env arm (comparison only)

Exactly one factor differs: the user-level harness file is present.
- **Claude:** the same per-trial settings without claudeMdExcludes.
- **Codex:** the same per-trial clone plus a copy of ~/.codex/AGENTS.md. Codex does not expand that file's `@~/.codex/RTK.md` line (decision 2026-10-04-codex-rtk-hook-qualified.md, Context).

Both arms use the same stripped fixture. The env arm therefore measures only the user-level managed blocks: the committed, F9-rendered text of ruling 144245Z(b).

Record the sha256 of every harness file per trial. Env results never enter READY_organic; they feed M13 and the CC's rules PR.

## 3. Method sources

**Kept from v1:**
- Anthropic, "Demystifying evals for AI agents" (2026-01-09), and "Writing effective tools for agents".
- skill-creator at anthropics/skills@683bc88e: SKILL.md:337-358 and :394; run_eval.py:191-192 and :232-234.
- OpenAI, "Testing Agent Skills Systematically with Evals".
- The Claude Code monitoring docs.
- openai/codex rust-v0.160.0 sources, as cited in v1.
- The MCP specification 2025-11-25.
- ACES (arXiv:2608.20614v1).
- The NIST Wilson interval.
- collector.yaml lines :97-111, :120, :166, :175-177, :183, :189-192, :199-210, :233, :238-244 and :263. The file is unchanged from HEAD to 9e955327 [obs].

**promptfoo 0.123.1** (~/.local/share/codex-ecosystem/tools/promptfoo-0.123.1) [doc]:
- **`exec:` provider:** `ScriptCompletionProvider` (dist/src/providers-BUaNtf-O.js:19297-19358).
  - It runs `execFile(cmd, [...args, prompt, JSON(options), JSON(context)], {cwd: config.basePath})`.
  - It sets no timeout and uses Node's default maxBuffer.
  - It rejects on an exec error, or on stderr output when stdout is empty.
  - It caches results unless `--no-cache` is set.
  - The context carries vars, repeatIndex, testIdx and evaluationId (evaluator-DlYW7Rgb.js:7776-7795).
- **Retries:**
  - The scheduler defaults to maxRetries 3 (shared-CzEItb8B.js:308-313).
  - It retries rate-limited results, and errors whose message contains timeout, econnrefused, network, 502, 503 or 504 (:331-340).
  - `provider.config.maxRetries: 0` disables retries (:939-955, used at :855-869).
  - `PROMPTFOO_DISABLE_ADAPTIVE_SCHEDULER=true` bypasses the scheduler (:846, :856).
- **`openai:codex-app-server`** (codex-app-server-B9-ncut6.js):
  - Defaults: approval_policy never, sandbox_mode read-only, network_access_enabled false, ephemeral true, thread_cleanup unsubscribe, reuse_server true (:762-772, :778).
  - It passes a minimal env plus cli_env (:853-871).
  - service_tier accepts only fast or flex (:160). model_reasoning_effort accepts max and ultra (:62-72).
  - cli_config is passed as --config (:203, :903, :1243).
  - Its config schema is strict (:213). It has turn_timeout_ms and no maxRetries key (:146-212).

**@openai/codex-sdk 0.160.0** [doc]:
- CodexOptions: codexPathOverride, config, configOverrides and env (index.d.ts:219-240). `env` replaces process.env.
- ThreadOptions (:247-258): model, sandboxMode, workingDirectory, skipGitRepoCheck, modelReasoningEffort (including max and ultra), networkAccessEnabled and approvalPolicy.

**claude-agent-sdk 0.2.163 (Python)**, at ~/.local/share/new-wsl-native-stack/tools/claude-agent-sdk [doc]:
- Options: settings (types.py:2105), setting_sources (:2297), effort (:2372), include_hook_events (:2199), session_id (:2043), env (:2124) and cli_path (:2099).
- The transport passes --settings, --session-id, --include-hook-events, --setting-sources and --effort (subprocess_cli.py:655-778).

**Clients:**
- **Claude Code 2.1.289** (`claude --help`) [doc]: --session-id, -n, --include-hook-events (stream-json only), --forward-subagent-text, --settings and --setting-sources. `--bare` skips OAuth, hooks and plugins.
- **Codex 0.160.0** [doc]: `codex execpolicy check --rules <PATH> <COMMAND>…`.

**Permissions docs** (https://code.claude.com/docs/en/permissions, fetched 2026-10-05) [doc]:
- Rules are evaluated deny, then ask, then allow.
- A bare tool-name deny removes the tool from context.
- Deny rules apply to any subcommand, including subshells and command substitutions.
- In a --settings file, `/path` anchors at the file's directory, `//` is absolute and `~/` is home.
- Permission rules are enforced by Claude Code, not by the model.

**Agent-teams docs** (https://code.claude.com/docs/en/agent-teams, fetched 2026-10-05) [doc]:
- The default display mode is in-process: teammates run inside the lead's terminal process. Split panes need tmux or iTerm2.
- Team state lives in ~/.claude/teams/<team>/ and ~/.claude/tasks/<team>/.
- Each teammate is a separate Claude instance.
- Nested teams are not allowed.
- `teammateMode` is unset on this host [obs].

**Codex hook trust** [doc], per the tools/adoption/codex_hook_trust.py docstring, which cites openai/codex rust-v0.159.3 (discovery.rs L775 and L794-L815, registry.rs L603-L660, exec_policy.rs L316-L420):
- A non-managed hook runs only while its hash equals `[hooks.state."<key>"].trusted_hash`.
- The key includes the hooks file's path and the group index.
- Execution rules match the command after the hook rewrites it, so a `forbidden` rule on `git push` misses `rtk git push`.

**context-mode 1.0.169**, src/server.ts [doc]:
- `ctx_execute` {language (shell, javascript, typescript, python, ruby, go…), code, timeout, background, cwd, intent} (:1647-1732).
- `ctx_execute_file` {path, language, code} (:2042-2105).
- `ctx_batch_execute` {commands[{label, command}], queries, concurrency, cwd} (:3678-3764).

**Repository and local tools** [doc]:
- `tools/skill-usage/skill_usage.py --lanes --codex-root --since --until --json --call-ledger` (its --help; README.md:152-208).
- agentsview 0.43.0:
  - `export sessions --agent --active-since --include-automated --include-one-shot --include-children --json`;
  - `session tool-calls <id> --json`.

**Observed now** [obs]: Loki api_request carries `effort` per request on 2.1.289. The pilot1 tags show max; the smoke1 tags show high.

## 4. Runner, fixture, clones and cells

### 4.1 Runner (CL1)

**Command and providers:**
- Each cell is its own eval, run from the run root:
  `PROMPTFOO_DISABLE_ADAPTIVE_SCHEDULER=true promptfoo eval -c cells/<cell>/promptfooconfig.yaml --repeat <k> -j <j> --no-cache --no-write --no-share -o cells/<cell>/results.json`.
  The coordinator starts it from a clean login shell, never from inside a Claude or Codex session.
- Every exec: provider has `id: "exec: <abs>/launchers/<launcher>"` and `config: {basePath: <run root>, maxRetries: 0}`.
- CL7b uses promptfoo's own `openai:codex-app-server`, because finding 5's fix configures it. It runs under the same flags.
- `PROMPTFOO_EVAL_TIMEOUT_MS` stays unset.
- Test vars: task_id, instance, arm, cell, sandbox and network. Tests are listed in a seeded random order, and the seed is recorded.
- No promptfoo assertion decides use (§7).

**Launcher contract.** The launcher is thin, versioned and hashed with the suite. It does no scheduling, no retries and no deletion.
1. Read the prompt, the options and the context from argv.
2. Create trial_id as a UUID v4.
3. Append the pre-launch ledger row:
   - run_id, phase, trial_id, task, instance, arm, cell and repeatIndex;
   - the hashes of the fixture, prompt, settings and clone;
   - the label-vector hash;
   - client versions, model, requested effort, tier, route, gateway build and start time.
4. Prepare the trial:
   - extract the hashed fixture tarball to `<NEUTRAL_ROOT>/<8 random hex>/`;
   - build the per-trial clone (Codex, §4.3) or the per-trial settings file (Claude, §8.1) in the run root.
5. **Claude only:**
   - Take the shared lock on a file descriptor: `flock -w 3600` on ~/.local/state/native-agent-stack/coordination/ns2604-coop/claude-session.lock. A lock timeout is recorded as censored.
   - **Inside the lock**, read the meter and decide whether to start (§9.1).
   - **Codex:** the quota gate runs per block (§9.2).
6. Exec the native line (§4.4) under `timeout --signal=TERM --kill-after=30s <T>`, from `bash -lc`.
   - Unset: CLAUDECODE, CLAUDE_CODE_ENTRYPOINT, CLAUDE_CODE_SESSION_* and the other session variables, CODEX_THREAD_ID and the CODEX_* session variables, GH_TOKEN, GITHUB_TOKEN, and any inherited OTEL_RESOURCE_ATTRIBUTES.
   - Raw stdout goes to `raw/<trial_id>.stream.jsonl`; stderr goes to `raw/<trial_id>.err`.
7. While the client runs (Claude), tail the stream's rate_limit_event and kill on the §9.1 thresholds.
8. After exit:
   - hash-manifest the whole fixture;
   - copy `./draft/` to `draft/<trial_id>/` in the run root;
   - never delete the fixture.
9. Always exit 0, and print exactly one JSON line: `{trial_id, rc, censored, reason}`. A failed launch is a censored trial, never a promptfoo error, so promptfoo cannot relaunch a paid session.

**NEUTRAL_ROOT:**
- A fixed directory: non-git, outside /tmp, every repository and the coordination tree.
- Its path holds no experiment, tool, client, arm or task word. Proposed: ~/.cache/ws (outside any git repository [obs]).
- The R2 lint covers the cwd, `-n` and every other launch string the model can see.

### 4.2 Fixture

**Source and build:**
- `git archive 9e955327`, extracted once into a template at stage 1, then stripped, set up, tarred and hashed.
- Ancestors of 9e955327 [obs]: c148e049, f3ebf469, 4af7417b, 4fd71069, a11dc5ff, 095d4fad, 19249810 and cb339488.
- Experiment check: `git log -p 4c897418..9e955327` has 0 matches for `organic-e2e|organic invocation|organic-invocation` [obs]. Re-run it at freeze, from 4c897418 to the frozen commit.

**Strip list** (everything a client loads):
- AGENTS.md and CLAUDE.md;
- adoption/scaffold/{AGENTS,CLAUDE}.md;
- blueprints/convergence-practice/application-delivery/{AGENTS,CLAUDE}.md;
- blueprints/us-equities/{AGENTS,CLAUDE}.md;
- examples/claude-native/CLAUDE.md;
- all of `.claude/`: settings.json, the 11 agents and skills/omniroute-runtime-worker.

Kept: `tests/fixtures/skill_usage/fake-home/.agents` (test data) and `adoption/scaffold/.agents/skills/README.md`.

Gate: `find` for AGENTS.md, AGENTS.override.md, CLAUDE.md, CLAUDE.local.md, .claude, .codex and .mcp.json, at any depth, returns only the kept paths.

**Setup files**, all taken from local git objects (no live GitHub; every blob is present [obs]):
- `./alerts/pr723-promptfoo-gateway.cjs` = bf2c6f85:evidence/artifacts/new-wsl-install-plan-20261002/config/promptfoo-gateway.cjs;
- `./alerts/pr736-drill_local_recovery.py` = d109af7a:blueprints/us-equities/hosting/drill_local_recovery.py;
- `./review/`: the head blobs of #736 (e97a6035, hosting files) and #709 (b0b9f752, adoption/templates/codex.AGENTS.template.md);
- the suite's other setup: ./before, ./after, ./freeze, ./scan, ./publish, ./filings, ./ledger-repo, and the 095d4fad^ hunk.

**D oracles** are computed inside the stripped, non-git template, never from git. Code can behave differently without instruction files or git; context-mode.P1 is an example.

**Routing-file registry** (used by the fixture-directed tag):
- **Candidates:** files where an item name (the R2(a)/(b) lexicon) and the pattern `use|prefer|route|routing|lane|lanes|through|instead of|before|for (exact|conceptual|symbols?|docs?|large)` occur on the same line. At 9e955327, 48 files carry a known routing phrase and 80 name TOKEN LANES or token-lanes-block [obs].
- **Review:** the cross-family hint reader keeps only files whose purpose is to instruct an agent: instruction texts, agent and skill definitions, prompt templates, routing blocks and handbooks. Examples: adoption/hooks/claude/token-lanes-block*.md, docs/token-session-handbook.md, docs/token-practice.md, examples/claude-native/agents/*.md, adoption/agents/claude/*.md, adoption/templates/*, recipes/README.md, and the agent prompts in examples/claude-native/workflows/*.js.
- Data, tests, receipts and research returns are excluded.
- The pattern only proposes candidates. Its raw hits include false positives [obs]: a test assertion (tests/test_skill_usage.py:1293), a test comment (tests/test_landscape_sweep_harness.py:1635), calibration JSON, an HTML template and the reasoning text in returns.json.
- The reviewed list is frozen and hashed with the suite.

**Retention:** fixtures, `./draft/`, Claude project directories and rollouts are deleted only after grading has finished and the manifests are reconciled. A fixture is about 233 MB [obs].

### 4.3 Codex per-trial clone (U1's recipe, amended)

**Why rebuild.** The 15:2xZ clone is stale [obs]:
- its hooks.json (f575095e…, dated 10-04 20:58 local) lacks the PreToolUse group 1 (matcher Bash, `rtk hook codex`) that #705 added;
- the host hooks.json (5938180a…) is from 16:18Z;
- its config.toml lacks one later trust entry.

So stage 1 rebuilds the clone from the current host files.

**Per trial:**
- **COPY:** config.toml, omniroute.config.toml, hooks.json, models_cache.json, and rules/ if the host has one (#713 may add hcom-deny.rules).
- **SYMLINK:** skills, plugins, packages, context-mode, sessions and cache.
- **EXCLUDE:** AGENTS.md (native arm only), auth.json, history, and the state, queue, memories and goals databases.

Every trial therefore starts with fresh state databases. No Codex memory or queue crosses trials.

**Additions to the copied config.toml:**
- `[shell_environment_policy.set] GH_CONFIG_DIR = <read-only or empty gh config dir>` (finding 6);
- `rules/organic-e2e.rules` (§8.2).

**Hook trust (new, §12.3).** User-layer hook trust is keyed by the hooks file's path and the group index. A clone's copied hooks.json therefore has no trusted key, and Codex should skip the ai-memory hooks and rtk's hook. Plugin hooks (context-mode, worktrunk) keep their plugin-keyed trust.
- **Evidence, consistent but not conclusive** [obs]:
  - A real-home Codex trial (pilot1env serena, 16:10Z) received an ai-memory SessionStart block: "pending handoff from previous session".
  - The clone trial of the same task (15:59Z) had none.
  - Empty hook-context items (16 over 6 tool calls in the clone, 21 over 11 at home) do not discriminate.
- This protocol neither adds nor re-keys trust: a trust grant is the user's (clause 4, §13).
- Until the user decides, hook/codex/ai-memory and RTK on Codex are WIRING in both Codex arms, and S6 on Codex covers plugin hooks only.
- Stage 2 records which hooks fire.

**Gates:**
- The native clone equals the host Codex home, minus AGENTS.md, plus GH_CONFIG_DIR and the rules file.
- The env clone keeps the host's AGENTS.md and adds only GH_CONFIG_DIR and the rules file.

### 4.4 Cells

Common to all cells: the pilot timeout T is 900 s; trial_id follows S1; cells are never pooled.

**CL2: Claude Code 2.1.289 headless (the primary Claude cell).**

The launcher holds the shared lock, reads the meter inside it (§4.1 step 5), then runs this native-arm line with cwd set to the per-trial fixture:
```
OTEL_RESOURCE_ATTRIBUTES="ecosystem.task.id=<trial_id>,ecosystem.lane=organic-e2e,service.instance.id=<trial_id>" \
GH_CONFIG_DIR=<read-only or empty gh config dir> \
timeout --signal=TERM --kill-after=30s 900 \
claude -p "$(cat <run root>/prompts/<trial_id>.txt)" --model opus --effort max \
  --session-id <trial_id> -n s-<first 8 hex of trial_id> \
  --output-format stream-json --verbose --include-hook-events \
  --settings <run root>/settings/<trial_id>.json
```
- **Lock:** U1's shared `flock -w 3600` on the same lock file; the launcher holds it on a file descriptor.
- **Settings:** `{"claudeMdExcludes":["~/.claude/CLAUDE.md"],"permissions":{"deny":[§8.1]}}`. The env arm uses the same file without claudeMdExcludes.
- **Forbidden on trials:**
  - --allowedTools, --tools, --disallowedTools (withheld arm only), --append-system-prompt, --system-prompt, --bare, --strict-mcp-config, --mcp-config, --setting-sources, --resume and --continue;
  - --forward-subagent-text, which only changes output but is not in the fixed line; it is added only by amendment, if the pilot shows subagent calls missing from the stream;
  - any /command or $skill in the prompt.
- **Permission mode:** the host default, bypassPermissions.
- **Fan-out:** the host values are the declared and recorded cap. They are CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS 8, CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH 1, CLAUDE_CODE_SUBAGENT_MODEL opus and agent teams on (~/.claude/settings.json:26-34). T and the per-trial meter guard (§9.1) bound it.
- **Model and effort:** read from Loki api_request `model` and `effort`, joined on session.id. The init event carries per_turn_effort_active but no effort key [obs], so init is never read for effort.

**CL3: Codex CLI 0.160.0 exec (the primary GPT cell).**
```
cd <fixture> && CODEX_HOME=<per-trial clone> OMNIROUTE_API_KEY=local-loopback \
OTEL_RESOURCE_ATTRIBUTES="ecosystem.task.id=<trial_id>,ecosystem.lane=organic-e2e,service.instance.id=<trial_id>" \
timeout --signal=TERM --kill-after=30s 900 \
codex exec --json -p omniroute -m gpt-6.1-sol -c model_reasoning_effort=max -c service_tier=default \
  -c otel.environment=<trial_id> --skip-git-repo-check -s <sandbox per task> \
  -o <run root>/last/<trial_id>.txt - < <run root>/prompts/<trial_id>.txt
```
- **Allowed `-c` overrides:**
  - model_reasoning_effort;
  - service_tier;
  - otel.environment: telemetry only, and the Codex join key (collector.yaml:199-203);
  - the withheld arm's one target override.
- **Forbidden:** $skill mentions, --ignore-user-config, --ephemeral, --worktree, and `-c` on mcp_servers, skills, features, projects or hooks.
- **Approval:** stays never.
- **Sandbox:** per task (U1). Read-only for answer-only tasks; workspace-write for tasks that write `./draft/` or run tests. Network is per task and off by default.
- **Effort label:**
  - requested: max;
  - forwarded: xhigh, until upstream #15167 is deployed (U1:63-65);
  - record the gateway build, and `pipelinePayloads.providerRequest.reasoning` wherever the gateway's call log exposes it (GET /api/usage/call-logs/<id>; docs/harness-defaults.md:180).

**CL4: Codex coordinator role.**
- CL3's line with `-c model_reasoning_effort=ultra`, still with `-m gpt-6.1-sol` and `-p omniroute`. Without -m the profile file would select cx/gpt-6-astra (omniroute.config.toml:5-7).
- Default tier.
- If the forwarded model and effort equal CL3's, CL4 has no distinct treatment until #15167 lands, and its cards run in CL3 under the effective label.

**CL5: interactive arms.** UNAVAILABLE: trust is the user's call (needs_user).

**CL6: Claude Agent SDK.**
- An exec: launcher written from the Python SDK README's query() example.
- Options:
  - cwd: the fixture;
  - cli_path: the native claude 2.1.289;
  - system_prompt: the claude_code preset;
  - setting_sources: ["user","project","local"];
  - settings: CL2's per-trial JSON;
  - permission_mode: bypassPermissions;
  - model "opus" and effort "max";
  - session_id: trial_id;
  - include_hook_events: True;
  - env: {OTEL_RESOURCE_ATTRIBUTES as in CL2, GH_CONFIG_DIR}.
- Every message is serialized to the raw stream.
- The same lock and meter rule as CL2 applies.
- Gate: the SDK init lists the same connected MCP servers, skills and agents as the CL2 init.

**CL7: Codex SDK (@openai/codex-sdk 0.160.0).**
- An exec: launcher written from the SDK README:
  - `new Codex({codexPathOverride: <native codex 0.160.0>, env: {PATH, HOME, LANG, CODEX_HOME: <clone>, OMNIROUTE_API_KEY: "local-loopback", OTEL_RESOURCE_ATTRIBUTES}, configOverrides: ['profile="omniroute"','service_tier="default"','otel.environment="<trial_id>"']})`;
  - then `startThread({workingDirectory, skipGitRepoCheck: true, model: "gpt-6.1-sol", modelReasoningEffort: "max", sandboxMode, approvalPolicy: "never", networkAccessEnabled})`;
  - then `runStreamed`.
- promptfoo's bundled openai:codex-sdk (0.153.4) is excluded.
- Gate: the rollout session_meta shows the omniroute provider, and the gateway call log shows the request. Whether `profile` given through --config selects the profile file is [nv].

**CL7b: Codex app-server (promptfoo `openai:codex-app-server`).**
- One provider entry per trial, because working_dir is static per entry.
- Provider settings:
  - codex_path_override: the native codex 0.160.0;
  - working_dir: the per-trial fixture;
  - skip_git_repo_check true, ephemeral false, reuse_server false;
  - approval_policy never;
  - sandbox_mode and network_access_enabled: CL3's per-task values;
  - model gpt-6.1-sol and model_reasoning_effort max;
  - turn_timeout_ms 900000;
  - cli_config: {profile: "omniroute", service_tier: "default", otel: {environment: <trial_id>}};
  - cli_env: {CODEX_HOME: <clone>, OMNIROUTE_API_KEY: local-loopback, OTEL_RESOURCE_ATTRIBUTES, PATH, HOME}.
- Run at -j 1. Retries are off through the scheduler switch, because the strict schema has no maxRetries key.
- No launcher runs here, so:
  - stage 1 pre-assigns these trial_ids, builds their fixtures and clones, and writes their ledger rows;
  - stage 5 copies `./draft/` and hashes the fixtures.
- Record thread_id from the provider response or from thread/started.
- Gates: exactly one rollout per trial, and route parity as for CL7.
- Fallback client: `codex debug app-server send-message-v2`.

**CL8: OpenHands.** UNAVAILABLE (WIRING) until the wiring check passes (slots.json:241).

**CL9: OmniRoute 3.8.51**, a transport factor.
- Record per trial the requested, forwarded and backend model and effort, and the gateway build.
- A gateway change mid-block pauses the block.

**CL10: agent teams.** No dedicated cell in v1.1 (§13). Teams stay on, in-process, and a teammate counts as an actor (S8).

**Codex availability.**
- serena, codebase-memory and the promptfoo MCP server are configured but not callable in sessions in either arm (U1:61).
- Their Codex cells are dropped until a session's codex.conversation_starts or rollout lists them as callable. Until then they are WIRING on Codex (RP2), and their Claude cells count as Claude-only, not as client divergence.
- operator/both/promptfoo keeps its descriptive CL4 card, which drafts config with the CLI.

## 5. Task-suite rules

**R1 Organic and provenance.**

A trial is organic when the user turn names no item, alias, tool function, $skill or /command, and the launch forces no tool.

Each call gets one tag; the first match in this order wins:
1. **explicit:** the user turn names the item. This is contamination.
2. **task-induced:** the call reads data the task names.
3. **agent-definition-directed:** the call is made by an actor whose definition is harness-authored and names the item (~/.claude/agents; the project agents are stripped). It also covers the parent's call after such an actor returned text that names the item. Plugin agents (codex:codex-rescue) and built-ins (general-purpose, Explore, Plan, claude, statusline-setup) count as native.
4. **fixture-directed:** earlier in the same actor's trace or spawn prompt, a successful tool result returned text from a reviewed routing file (§4.2) that names the item.
5. **store-directed:** an earlier injected or retrieved block from a cross-session store named the item. Stores:
   - ai-memory SessionStart and UserPromptSubmit injection;
   - context-mode knowledge-base recall;
   - agentsview recall;
   - Claude auto memory.
   [obs] An ai-memory pending-handoff injection reached a real-home Codex trial (§4.3).
6. **policy-named:** env arm only; the loaded harness file names the item. In the native arm a harness marker invalidates the trial (§2.1).
7. **hook-rewritten:** an RTK updatedInput rewrite. It is passive and never organic.
8. **hook-nudged:** a tool-native hook's additionalContext named the item earlier in the same turn.
9. **skill-directed:** the call follows a consulted skill body that names the item. Upstream skills and harness-authored skills are split.
10. **autonomous:** none of the above.

How the tags count:
- **Native U** counts autonomous calls, skill-directed calls from upstream skills and hook-nudged calls from tool-native hooks. Each stratum is reported separately.
- **Excluded** from native U, OIR, T5 and T6, with counts reported: explicit, task-induced, agent-definition-directed, fixture-directed, store-directed, hook-rewritten, and skill-directed from a harness skill.
- **fixture-mentioned:** an earlier result named the item in any other fixture text. This is a covariate, with a sensitivity column that also excludes these calls.
- **U_env** also counts policy-named calls.
- An RTK prefix typed by the model on Codex is policy-named in the env arm (~/.codex/AGENTS.md:26-63). In the native arm it is autonomous only when no other tag applies.

**R2 Lint.**
- Scope: the transmitted bytes, plus every launch string the model can see: the cwd, the `-n` name and the path of any file the task names.
- Checks (a)-(e) as in v1: target names and aliases; tool functions; $ and / forms; 5 or more words copied from a description; meta-phrases.
- New check (f): the cwd and the session name contain no experiment, tool, client, arm or task word.
- The cross-family hint reader also tags restated definitions (§6). Meta-domain tasks are tagged as in v1.

**R3 Anchors and oracles.**
- Oracle types D, L and R work as in v1. D oracles are computed in the stripped template at the frozen commit.
- Prompted oracle runs go on Codex. Three items run them on Claude instead, inside the full-run budget, because they are Claude-only or not callable on Codex: serena, codebase-memory and skill/claude/skill-creator. The pilot uses D and R oracles for those three.
- Selection-rule cards are fixed at preparation.

**R4 Labels.**
- As in v1: the other model family assigns labels before any trajectory exists, and they are frozen.
- The labeler marks client-native alternatives may_use wherever a task invites them (finding 15):
  - Claude bundled skills: claude-api, deep-research, debug, code-review, verify, security-review;
  - the Claude plugin agent codex:codex-rescue;
  - the Codex system skill openai-docs.
- G1, G2, G3, G4', G5 and G6' are should_not for every item.

**R5 Lane sets.**

Unchanged from v1:

| Lane | Acceptable members |
|---|---|
| Exact symbols | serena, jcodemunch, codebase-memory |
| Call graph | codebase-memory, serena |
| Conceptual code | socraticode; semble on git repositories |
| Docs | qmd |
| Large output | context-mode, headroom |
| Compression with exact recovery | headroom |
| Uniform flat arrays | TOON |

Changed or added:

| Lane | Acceptable members |
|---|---|
| Third-party API docs | chub, context-mode fetch, claude-api (Claude), openai-docs (Codex) |
| Research before code | search-first, deep-research, native-stack-research |
| Diagnosis | diagnosing-bugs, debug, codex:codex-rescue |
| Security review | security-best-practices, security-audit, security-review |

A lane miss requires that no acceptable member was selected. RP5 records the overlaps.

**R6 Exposure.** As in v1, with these known risks:
1. serena, codebase-memory and promptfoo are not callable on Codex in either arm.
2. Codex clones skip user-layer hooks, and rtk's Codex hook is untrusted on the host (§12.3).
3. Codex code mode is active (§12.2).
4. CLI items have no native surface in either client's init. Until decision 17 (§13), a native-arm CLI trial is recorded under the exposure class PATH-only and is never a ROUTING miss.
5. The promptfoo MCP server is pending at Claude init, and its tools spend on models. It is O-descriptive, with its exposure recorded.
6. Carried from v1:
   - semble works only on git repositories;
   - qmd has embeddings pending;
   - index states and the ai-memory scope are unverified;
   - the Claude listing budget and Codex description truncation.

A subagent's non-use counts only when the item was exposed to that actor.

**R7 Roles.** v1's classes stay: 31 M, plus H, O, W, R/I and N. Changes:
- RTK on Codex moves from a prefix the model types to H, through `rtk hook codex`. It is WIRING while the hook is untrusted or skipped.
- hook/claude/token-lane-carriers: absence is expected (retired by #699, 5df0e0ed); presence is the defect.
- New row: hook/codex/worktrunk-plugin, observing permission_request, session_end, user_prompt_submit and stop. The plugin must write nothing outside the fixture.
- New descriptive agent-type class, scored from the stream's subagent_type, with no verdict.
- The Codex dagu skill is not installed [obs: no dagu under ~/.codex/skills, the plugin caches or ~/.agents/skills; none in config.toml]. It gets no card.
- The promptfoo MCP server is O-descriptive.

**R8 Containment:** §8.

**R9 Instance sets:** as in v1. P1 is for tuning, P2 is the held-out screen instance, and P3 is sealed acceptance.

**R10 Isolation.**
- Each trial gets its own neutral random fixture path and Codex clone, with fresh state and memory databases.
- Prompted runs use the lane `organic-e2e-prompted` and their own fixtures.
- v1's exclusions stand.
- Content from another trial is flagged; the store-directed tag covers the same channel.

## 6. Task cards: amendments to suite-v1.json

| Item or card | Amendment |
|---|---|
| G4 | Replaced by **G4'**: "What is the ignore list in .grype.yaml set to?" D: `ignore: []`. The file has 14 lines and 0 item names [obs]. |
| G6 | Replaced by **G6'**: "What is the first heading of catalogs/README.md?" D: "# Two maintained catalogs". 0 item names [obs]. |
| writing-for-agents P2 | Now: "Draft a short section for catalogs/us-equities/README.md telling agents how to find catalog entries by search instead of reading whole files; put it in ./draft/." The file has one item mention, QMD at :148, in a measurement line [obs]. |
| iterative-retrieval N; hook/claude/context-mode N; hook/codex/context-mode N | Use G4'. |
| fp-check P1, P2; variant-analysis N (= fp-check.P1) | Name `./alerts/pr723-promptfoo-gateway.cjs` (PR #723, line 15) and `./alerts/pr736-drill_local_recovery.py` (PR #736, line 225). Verify both line numbers in the blobs at setup, then re-run the lint. |
| gh-fix-ci P2 | #711 has merged (4ead2838 on main), so select a new check at freeze. Re-check gh.P1, gh-fix-ci.P1 (#690) and W4 (#692) at freeze. |
| gh-address-comments P1, P2 | Head blobs go under `./review/`; the fixture is non-git. |
| headroom.P1 | Its subject, returns.json, names headroom 30 times [obs]. Flag it for the hint reader; the pilot uses headroom.P2 (safety.py: 0 mentions [obs]). |
| cli/codex/rtk | Becomes **hook/codex/rtk** (H). Positives are observation hosts. N: the hook must never change diff's exit status. WIRING while the hook is untrusted. |
| hook/claude/harness-guards | "The resolved effort in system/init must stay max" becomes "Loki api_request effort is max on every request". |
| hook/claude/token-lane-carriers | Absence expected; presence is the defect. |
| New rows | hook/codex/worktrunk-plugin; descriptive agent-type rows built from the init agents list. |
| operator/both/promptfoo | The MCP server is O-descriptive, with an exposure check. |
| P2 anchors | Hold at 9e955327 [obs]: safety.py has 1,542 lines; Ledger at :421, account_lock_fingerprint at :397, evaluate_gap_risk at :294, decimal at :100; native_strategy.py at :636. Recompute every D oracle at freeze anyway. |
| Finding 18 (deferred) | native-stack-worker P1/P2 and cross-family-review P1/P2 are scored mechanism-only, as an explicit dispatch class, until reworded outcome tasks pass the lint and the hint reader at the full-run freeze. |
| Finding 19 (deferred) | supply-chain-risk-auditor P1 and security-threat-model P1 are tagged restated-definition and reported as their own stratum until they are reworded at freeze. |

## 7. Signals and graders

Graders use native sources only. pilot_grade.py is retired.

**S1 Identity.**
- trial_id is a UUID v4. It is also the Claude --session-id, the stream session_id, the OTel session.id, ecosystem.task.id and service.instance.id.
- Codex:
  - Loki `env` = trial_id. This is the one Codex join key.
  - thread_id from thread.started = the rollout's session_meta id = Loki conversation.id.
  - Child threads join through env or through receiver_thread_id (stage-2 check).
- The ledger maps trial_id to the fixture, the clone, the promptfoo test and the repeatIndex.
- A failed join invalidates the trial.

**S2 Claude.**
- **Primary source: the stream-json pairs.** An assistant tool_use {id, name, input} pairs with a user tool_result {tool_use_id, is_error}. Success means is_error is false.
  - Fields read from tool_use: the server from `mcp__<server>__<tool>`; Skill input.skill; Bash input.command; Read file_path; Task subagent_type (and name for teammates); ToolSearch queries.
- **Subagent and teammate turns:** from the stream where they carry parent_tool_use_id. Otherwise from the child transcripts under ~/.claude/projects/<slug>/<session>/, which have the same pair format. Which source applies is a pilot gate.
- **Also from the stream:** hook events, rate_limit_event and result.
- **Secondary source: Loki**, joined on session.id plus tool_use_id:
  - tool_result success and mcp_server_name (collector.yaml:111). Never tool_name, which is the literal `mcp_tool` for user MCP servers (decision 2026-09-26:23-24; collector :120).
  - skill_activated invocation_trigger: claude-proactive and nested-skill are consultation strata; user-slash is contamination.
  - api_request model, effort and query_source.

**S3 Codex.**
- **Primary source: the exec --json stream.** Count **item.completed only**, because item.started repeats the command. Items:
  - command_execution {command, exit_code};
  - mcp_tool_call {server, tool, status, arguments, result};
  - file_change, collab_tool_call, web_search, error and turn.failed;
  - usage from turn.completed.
- **Code mode:**
  - A rollout custom_tool_call `exec` is a wrapper, not a lane.
  - Nested McpToolCall and CommandExecution items count once each, by their own item ids.
  - Loki `functions/exec` rows are excluded. Nested calls carry call_id exec-<uuid> (collector.yaml:189-191).
- **Rollouts:** `skill_usage.py --lanes --codex-root ~/.codex/sessions --since <trial start> --until <trial end> --json --call-ledger <new private path>`, filtered to the trial's parent and child thread ids.
- **Loki:** codex.tool_result and codex.tool_decision, joined by (env, conversation.id, call_id).

**S4 CLI.**
- **Claude:** Bash input.command.
- **Codex:** command_execution, after unwrapping `/bin/bash -lc '<cmd>'`, `bash -c` and `sh -c`. Unwrap; never skip.
- **Inside ctx_* calls** (Claude `mcp__plugin_context-mode_context-mode__ctx_*` inputs; Codex mcp_tool_call server=context-mode arguments):
  - ctx_batch_execute `commands[].command`, and ctx_execute or ctx_execute_file with language shell: parsed as shell text;
  - javascript and typescript: `child_process` spawn, spawnSync, exec, execSync, execFile or execFileSync, with a literal program (a string or the first array element);
  - python: subprocess.run, Popen, call, check_call or check_output, or os.system or os.popen, with a literal program;
  - any other language: recorded as unparsed, never as use.
- **Shell-text rules:** skill_usage.py's `executed_text` (README:202-208).
  - Split chains, then strip rtk, env, timeout N, sudo, nohup, command, exec, time and nice.
  - Map the first token: sg or ast-grep, difft, repomix, toon, markitdown, chub, mcporter, srt, betterleaks, zizmor, actionlint, ccusage, agentsview, mineru, gh, git, wt.
- **Completion:**
  - exit 0, or tool_result is_error false.
  - For a command inside ctx_*: the ctx call succeeded, and any per-command status in the output is 0. Without per-command status, the level is `completed-ctx`, counted in U and flagged.
- A name that appears only as data is not use. Receipts carry counts only.

**Skill consultation (S2/S3).**
- **Counts:** a successful read whose argument path has the same realpath as a SKILL.md under any skill root in the session's catalog.
- **Claude roots:**
  - ~/.claude/skills, which link to ~/.agents/skills;
  - ~/.agents/skills;
  - ~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/skills/*/.
- **Codex roots:**
  - <clone>/skills, which links to ~/.codex/skills, .system included;
  - ~/.agents/skills;
  - <clone>/plugins, which links to ~/.codex/plugins/cache/…/skills/*/. This covers context-mode:* and worktrunk:*.
- **How the read can happen:**
  - the Skill tool or Read;
  - cat, sed, head, tail, nl, less, rg or grep on that file, by shell or through ctx_*;
  - ctx_execute_file;
  - running a file under that skill's scripts/.
- **Does not count:** path mentions, listings, failed reads, catalog text and copied parent history.
- A $name mention is contamination.

**S5 MCP levels.** As in v1 (discovery, request, completion, contribution), plus the code-mode rule.

**S6 Passive items.**
- **Claude:** stream hook events, by hook source. RTK's fired rate = rewritten / eligible Bash calls.
- **Codex:** `hooks.additional_context` items by kind (README:170-188). Only plugin hooks are covered while the clone skips user-layer hooks.

**S7 Exposure.**
- Hash before and after every trial:
  - ~/.claude: settings.json, CLAUDE.md and agents/*.md;
  - ~/.claude.json: the mcpServers and projects maps;
  - skill-directory listings and plugin cache versions;
  - ~/.codex/config.toml: [projects], [hooks.state] and mcp_servers;
  - ~/.codex: hooks.json, AGENTS.md and rules/;
  - the per-trial clone, the fixture tarball and the per-trial settings file.
- A host mismatch invalidates the trial. A host change between blocks requires a new baseline.
- Also record: the init MCP status, codex.conversation_starts mcp_servers, the skill truncation counters, index states, the ai-memory scope and the agents list.

**S8 Actor.**
- **Claude:** parent_tool_use_id, subagent_type, teammate name, workflow.run_id and query_source.
- **Codex:** agent_name and receiver_thread_id.
- Use by any actor counts for the trial, with the actor recorded.

**S9 Cost.** As in v1: each request is counted once, and overlapping views are never summed.

**S10 Second parse.**
- `agentsview export sessions --agent <client> --active-since <block start> --include-automated --include-one-shot --include-children --json`, plus `session tool-calls <id> --json` per trial.
- Disagreements are checked against the raw sources. These counts are never summed with other views.

**S11 Field monitor.**
- Scoped to NativeStack2604's Loki, rollouts and agentsview.
- The CC's NativeStack sessions are outside it until the CC relaunches on 2604 (144245Z(a)).
- Otherwise as in v1: it reports activity over exposed sessions, runs for 7 days or more, and ends before 2026-10-25.

**Pre-pilot reconciliation:** stage 0 (§16).

## 8. Containment (R8)

Outputs go to `./draft/`. Nothing is pushed, posted, installed or registered.

### 8.1 Claude pre-execution deny (per-trial settings, the same in both arms; each rule maps to an R8 clause)

**Bash rules.** Each pattern is also denied with an `rtk ` prefix:
- `git push *`;
- `gh pr comment|review|merge|close|edit|create|ready *`;
- `gh issue comment|create|edit|close *`;
- `gh run rerun|cancel *`;
- `gh release create|delete|edit|upload *`;
- `gh repo create|delete|edit *`;
- `gh api` write forms only. The method rules cover POST, PATCH, PUT and DELETE, including attached forms such as `-XPOST`; GET reads stay allowed:
  - `gh api * -X POST*` (and the same for PATCH, PUT and DELETE);
  - `gh api * --method POST*` (and the same for PATCH, PUT and DELETE);
  - `gh api * -f *`, `gh api * -F *`, `gh api * --field *`, `gh api * --raw-field *` and `gh api * --input *`.
- `claude *` and `codex *`: nested client processes. The full run's cross-family W cell declares its own exception.
- `npm i -g *`, `npm install -g *`, `pip install --user *`, `uv tool install *` and `mise use -g *`;
- `systemctl --user *` and `crontab *`.

**Tools:**
- Bare denies for CronCreate, RemoteTrigger and PushNotification, which register or post outside the trial.
- `mcp__plugin_context-mode_context-mode__ctx_upgrade` and `…__ctx_purge`.

**Edit** (this also covers Write):
- `~/.claude/settings*.json`, `~/.claude.json`, `~/.claude/CLAUDE.md`, `~/.claude/agents/**`, `~/.claude/skills/**` and `~/.claude/plugins/**`;
- `~/.codex/**` and `~/.agents/**`.
- The trial's own auto-memory directory is deliberately **not** denied (finding 23).

**Read:** the credential-read denies of the committed .claude/settings.json at 9e955327 (the strip removes them from the fixture), plus docs/secret-storage.md's list.

**Not denied:** ScheduleWakeup (watched) and ai-memory writes. A deny beyond R8 would change the native treatment.

### 8.2 Codex pre-execution

**Primary controls:**
- the per-task sandbox, with network off unless the task needs it;
- GH_CONFIG_DIR in the clone.

**`rules/organic-e2e.rules`:**
- Forbidden prefix rules for the §8.1 command list, in both plain and `rtk` forms. Each rule is checked with `codex execpolicy check --rules`.
- Labelled partial: the trust tool's docstring records bypasses (rewrites, assignment-prefixed scripts evaluated as one token, and CR handling).

MCP servers run outside the Codex sandbox, so code run through ctx_execute is covered only by the watcher.

### 8.3 GitHub credential

- Every trial on both clients runs with GH_CONFIG_DIR set to a dedicated read-only gh config, kept outside every worktree. Creating it is needs_user.
- Until it exists, GH_CONFIG_DIR points to an empty config directory: unauthenticated, public reads only.
- GH_TOKEN and GITHUB_TOKEN are unset.
- Gates before any GitHub card:
  - Codex: `gh auth status` inside a clone trial (a prompted canary) shows the read-only identity or none.
  - Claude: checked in the first GitHub card's stream (full run).

### 8.4 Watcher (a detector, after the fact)

**What it reads:** every model-initiated call, including calls nested inside ctx_* and code mode.

**What halts the run:**
- an R8 hit that got past the pre-execution layer, from v1's list:
  - git push and gh write operations;
  - MCP or app writes to external services;
  - global installs;
  - systemctl --user and crontab;
  - configuration writes;
  - credential reads;
  - ctx-upgrade and ctx-purge;
- a promptfoo MCP call that runs a model evaluation.

**A denied call** counts as Sel plus an execution failure (M3), not as a breach.

**Exempt but logged:**
- the clients' own transcript and session writes;
- the trial's own auto-memory directory, `~/.claude/projects/<trial slug>/memory/`, logged as a cross-trial-store event (finding 23);
- the agent-team directories `~/.claude/teams/session-…` and `~/.claude/tasks/session-…`, written by the client.

**Nested client processes:**
- The deny rules block nested claude and codex launches.
- If one still appears in the trial's process tree, the trial is killed and censored as a lock bypass or GPT spend. One path is the codex plugin's Stop review gate, which is a hook and outside the permission rules.
- In-process teammates are not nested processes.

## 9. Budget, sizing and scheduling

### 9.1 Claude

**Meter.**
- The launcher reads the latest rate_limit_event **after taking the lock**: from the newest Claude stream on this host, if it is at most 30 minutes old.
- If no such stream exists, the trial's own first event decides. That trial counts toward the 14.
- G1 is the first Claude trial, so a kill on that first reading wastes the least.
- rate_limit_event recurs within a session: one 5-minute session had 5 of them [obs].

**Start rule.**
- Pilot prior: start only at five_hour < 0.50 and seven_day < 0.75.
- After the pilot: five_hour ≤ 0.65 − m_p90.
  - m is the per-session rate_limit_event delta. It includes workflow, subagent and teammate usage.

**Kill rule.** The trial is censored at the first of these:
- five_hour ≥ 0.80;
- seven_day ≥ 0.85;
- five_hour has risen ≥ 0.15 above the trial's first reading (the per-trial fan-out guard);
- T = 900 s has passed.

T stays 900 s unless the pilot's censoring exceeds 20%. Changing it then takes an amendment.

**Cap.**
- The pilot is at most **14 Claude sessions in all**. CL2, CL6, env, probe and canary sessions all count.
- v1-runner sessions do not count (§12.1), but they are in the meter.
- A failed gate's Claude re-run goes to the next 5-hour window and the full-run budget, never beyond 14 in the pilot.
- five_hour resets at 19:30Z; seven_day resets 2026-10-08T18:00Z [obs].

**Scheduling.**
- Configuration hashes are frozen at stage 1.
- The CC's 17:00-21:00Z takeover applies #713. The Claude block runs only after the host configuration has settled (no mtime change for 30 min) and stage 1 has been re-hashed.
- No heavy work from 10:35 to 10:55Z or from 13:20 to 13:45Z.

### 9.2 Codex

**Before every block:**
- Run `python3 -B scripts/codex_quota.py --gate 70` under the real CODEX_HOME, because the clone has no login. Any non-zero exit stops the block: 2 means no snapshot, 3 means the gate was reached (codex_quota.py:28-30).
- Read the gateway's call logs for the block window: request count and 429 or limit errors. The single-log endpoint `GET /api/usage/call-logs/<id>` is cited at docs/harness-defaults.md:180. The window or list form and its authentication are [nv].

It is [nv] whether the Sol route draws on the account that codex_quota.py reads. So any rate-limit error in a trial stream (error or turn.failed) also stops the block.

**Concurrency:**
- -j 3 in the pilot.
- Up to 6 later, only if the pilot saw no rate-limit errors and no other GPT-heavy workflow is running.
- Bulk work goes through the OmniRoute pool (CC 160128Z §6).

### 9.3 Sizing

**Pilot:** §16.

**Full Codex run:**
- Native screen: P1 and P2 of every callable item, × 3.
- Env arm:
  - items named in the env harness files (the M12 list): P1 and P2, × 3;
  - every other item: P1, × 1.
- The CL4 cards.
- SDK parity and app-server parity: 20 each.
- Withheld arm: 10 × 3.
- Escalation: at most 8 items.
- Wall time = sessions × t_c / j.

**Full Claude run:**
- Per window, serialized: N = min(30, ⌊(0.65 − u0)/m⌋, ⌊(300 − 45)/t90⌋), with at most 4 env sessions inside N.
- Allocation order:
  1. Items that diverge between clients.
  2. P1 **and** P2 of the never-invoked MCP servers.
  3. Claude-only items: the skill-creator body, and serena and codebase-memory while Codex cannot call them.
  4. Items Codex rated NEVER or INCONCLUSIVE.
  5. The remaining P1s, in north-star order.
- The calibration grading session runs inside the 45-minute reserve.

## 10. Metrics

**M1-M10** as in v1, with these changes:
- E includes the PATH-only exposure class.
- U is completed native-organic use, broken down by R1 stratum.
- M3: a denied call counts as Sel plus an execution failure.
- M10 also counts native-invalid trials (a harness marker was found) and the excluded v1-runner captures.

**M11 Headline.**
- The published READY 18/80, marked as prompted evidence, is shown beside:
  - **READY under the adopted bar** = 13 READY slots that are not model-chosen + READY_organic (native arm only; 0 until measured);
  - READY_organic over the 31 class-M slots;
  - BY_DESIGN 12, listed separately.
- (READY + BY_DESIGN)/80 = 37.5% is quoted only with the READY count beside it.
- Decision 17's option 2 would move 4 of the 5 READY class-M slots out of class M: mcporter, gh, zizmor and actionlint.

**M12 Covariates:**
- named_in_env_harness;
- fixture-mentioned;
- exposure class (native surface or PATH-only);
- description intact; index state; actor;
- model, effective effort, tier, gateway build and client version;
- order position; meta-domain; restated-definition.

**M13 Env minus native.**
- ΔOIR(i, client) = OIR_env − OIR_native, with raw counts and Wilson intervals, beside the two verdicts.
- It is the input to the CC's rules PR:
  - if the native arm chooses the tool, the harness line that names it is redundant;
  - if not, the tool follows the T14 path.

## 11. Thresholds

**T1-T4 (screen)**, as in v1 and computed per cell:
- T1: k = 3. A should_use task passes at 2 or more uses in 3; a should_not task passes at 1 or fewer.
- T2: SCREEN_PASS.
- T3: SCREEN_NEVER at 0 uses in 6 or more trials.
- T4: escalation for at most 8 items.

Only native cells count toward READY.

**T5 ORGANIC_OBSERVED** (Claude native): at least one completed native-organic use on P1 and on P2, in separate fresh sessions, plus a valid correct negative.

**T6 READY_organic** (class-M slot). All of these must hold:
- every item is SCREEN_PASS on Codex native where Codex can call it. Where it cannot, the item is WIRING and the slot is not READY_organic.
- every item is ORGANIC_OBSERVED on Claude native where Claude lists it.
- the existing READY criteria (method.md:60) hold.

An item that has not been run is DEFERRED. This is a reported column only: a status change still needs a new dated qualification (2026-10-04:114-121).

**T7-T10, T12 and T13**, as in v1. Pilot joins must be exact (T10).

**T11:** §9.

**T14 Exclusion, by CC rule (c).**
- Exclude a slot only when all three hold:
  - it was never chosen unprompted in the full native run;
  - another chosen slot covers the same task class;
  - one upstream-native fix plus a rerun did not change that.
- The exclusion record names its overturn conditions:
  - a later organic choice;
  - a regression in the chosen tool;
  - an upstream-harness A/B that favours the excluded tool.
- A never-chosen slot with no overlap is reported NOT-READY, with its gap, after its fix round.

## 12. New findings from this revision; prior captures

**12.1 v1-runner captures.**

| Capture | Sessions | Notes |
|---|---|---|
| probe-noharness | 2 Claude | |
| smoke1 | 2 Claude, 1 Codex | |
| pilot1 | 2 Claude, 9 Codex | Claude serena.P1: rc 124 at 900 s, empty JSON output |
| pilot1env | 3 Claude, ≥1 Codex | |

Defects:
- the stale fixture 4c897418;
- **the cwd showed the model the target tool, the client, the arm and the word "organic"** (e.g. …/runs/pilot1/serena.P1.r1-claude-native);
- `--output-format json`: no hook events, and a timeout loses everything;
- each fixture was deleted after its session;
- no lane tag;
- a stale Codex clone.

These captures are stage-0 material only.

**12.2 Code mode is on.** The smoke1 rollout has 11 `exec` wrappers around 10 McpToolCall items and 1 CommandExecution; Loki shows functions/exec ×11 [obs].

**12.3 Codex hook trust.**
- The clone skips user-layer hooks (§4.3; consistent with the evidence but not proven).
- rtk's Codex hook is registered (16:18Z, group 1), but the host config.toml has no hooks.state key for it [obs], so the hook is untrusted.
- This is an owner-lane item (decision 2026-10-04-codex-rtk-hook-qualified.md; `codex_hook_trust.py --check`). The E2E takes no action on it.

**12.4 promptfoo retries by default.** Fixed by maxRetries 0, the scheduler switch, and launchers that always exit 0.

**12.5 Tools with outside effects in the Claude init:** CronCreate, RemoteTrigger, PushNotification and ScheduleWakeup [obs]. Handled in §8.1.

**12.6 Host drift today** [obs]. S7 re-baselines at stage 1.
- ~/.codex/config.toml changed at 16:22Z and now has 4 trusted projects (v1 recorded 3).
- ~/.codex/AGENTS.md and hooks.json changed at 16:18Z.
- ~/.claude.json changed at 16:51Z.

**12.7 #711 has merged.** gh-fix-ci.P2's selection is void.

**12.8 Stripping removes the project's credential-read denies.** §8.1 carries them into the per-trial settings.

**12.9 Routing-line pattern false positives.** They make a reviewed routing-file list necessary (§4.2).

## 13. Decisions pending

These are framed with options in this return's cc_decisions_needed:
- **Finding 17, CLI exposure.** Interim: the PATH-only class, never a ROUTING verdict.
- **Finding 24, agent teams.** Interim: teams stay on, in-process, with no team cell.
- **Codex clone hook trust.** User item under clause 4, relayed by the CC.
- **Read-only GitHub credential.** needs_user.
- **Timing against #713's apply.**

## 14. Remediation

**RP1-RP2**, as in v1:
- Classify before acting.
- Fix exposure first.
- Never remove an explicit-only restriction.

**RP3 (amended).** READY levers are upstream-native only, applied smallest first, one per round:
1. the skill's own description;
2. the MCP server's own instructions and tool descriptions;
3. the tool's own hook or plugin surface.

Rules for the levers:
- Wording in CLAUDE.md, AGENTS.md or token-lanes-block.md is **not** a READY lever (U1 Consequences). It changes only through the CC's rules PR, based on M13.
- Accept a fix only on sealed P3, in fresh native outcome-only sessions.
- At most 2 rounds per item and client.

**RP4.** Host changes are proposals under clause 4.

**RP5.** Overlaps are recorded and feed T14.

**RP6** is replaced by T14:
- v1.1 creates no BY_DESIGN.
- The CC and the owners write exclusion records.
- Zero use alone does not demote a listing (adoption/skills/manifest.json:30).

**RP7.** Never exclude on:
- T0 zeros;
- a Claude k=1 screen;
- WIRING;
- PATH-only zeros before decision 17;
- quota-deferred or censored cells;
- env-only results;
- a failure on one client while the other client uses the item.

**RP8**, as in v1.

**RP9.** With authorization: the decision record docs/decisions/<dat
