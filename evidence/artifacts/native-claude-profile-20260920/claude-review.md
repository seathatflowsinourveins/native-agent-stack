## Verdict

**Approve with follow-ups.** The launcher fix is correct and the JSON-stream invariant now holds (independently confirmed against this session's own stream). No blocking defect. Two items (F1, F2) should land before the profile receipt is published, because F2 weakens the "reduced context without losing recovery" claim the receipt will make.

## Findings

**F1 — Validator hardcodes a host path (defect, medium)**
`validation/verify-native-scope.cjs:21` asserts `launched.options.cwd === '<PROJECT>'` while lines 7/22 correctly use `os.homedir()`. Combined with `launch-linux-agent.cjs:17` (`fs.realpathSync`), the check requires that exact directory to exist and to not be a symlink, so it fails on any other host or after a path move. Fix: `path.join(os.homedir(),'code/agent-lab')`, or pass `--project` with a fixture directory. Pre-existing (same line in the backup at `:20`), carried forward rather than introduced.

**F2 — Recovery pointers lost in the 1175→401 reduction (defect, medium)**
`~/.claude/CLAUDE.md:13` now names only `native-session-commands.md` and `token-session-setup.md`. The removed inventory previously pointed at six other docs (backup `CLAUDE.md:9,11,13,15,17,22,25`). `native-session-commands.md` references only `native-additions.md` (L44, L119) and `native-ecosystem-activation.md` (L76) — it does not reference `native-client-e2e.md`, `native-upstream-additions.md`, `native-token-workflow.md` or `token-practice.md`. So `difft`/`shellcheck`/the Codex-for-Claude bridge, `bd`/`otel-tui`/`skills-ref`, and jCodeMunch/Headroom/Context-Mode-root-repair are no longer reachable in one hop from the persistent contract. Fix belongs in `native-session-commands.md` (add the four pointers), not by re-expanding `CLAUDE.md` — the 401-token contract stays intact.

**F3 — Shipped example diverges from the installed file (defect, low-medium)**
`recipes/claude-native-profile.md:49` tells adopters to merge `examples/claude-native/CLAUDE.md`, but that example's line 11 omits *"Keep durable memory and indexes scoped to that project"*, which the installed `~/.claude/CLAUDE.md:11` has. Adopting hosts would get a weaker scoped-memory rule than this host — against the stated goal. Conversely the example's line 5 retains the "unchanged upstream tests" evidence class that the global dropped. Make the two identical apart from the host-specific line 13 and the `@RTK.md` import (correctly generalized at example line 15).

**F4 — Review command is less bounded than the repo's own receipted shape (defect, low)**
`recipes/claude-native-profile.md:115-118` uses `--tools Read,Glob,Grep` with no `--disallowedTools` and no `--permission-mode`; the receipted execution at `blueprints/us-equities/convergence-review/receipt.json:24-31` paired `--tools ''` **with** `--disallowedTools '*'` and `--permission-mode dontAsk` to obtain `exposed_tools: 0`. The allowlist does in fact hold (see verified scope), but the recipe should tell the reader to confirm the `system:init` `tools` array rather than trust the flag. Note the interaction: `launch-linux-agent.cjs:24` prepends `--permission-mode bypassPermissions` for `claude`, so anything that *is* exposed runs unprompted.

**F5 — `--check` branch still writes to stdout (note, low)**
`launch-linux-agent.cjs:22` keeps `console.log`. Harmless — `--check` never spawns a child, so no stream exists — but untested, and the stated invariant at `recipes/claude-native-profile.md:126` reads as absolute. Phrase it as "notices on stderr whenever a native stream can be produced."

**F6 — Hook injects guidance for tools that are not exposed (note, low)**
The SessionStart hook supplied ~700 tokens of `mcp__plugin_context-mode_*` tool instructions, but `--strict-mcp-config` with an empty `mcpServers` left only three tools live. In a profile whose purpose is small task-specific contexts, that is pure overhead plus a misleading tool menu. `recipes/claude-native-profile.md:124` discloses that hooks still run; consider scoping the hook by exposed tool set.

## Verified in this review

- **Launcher fix is exactly one line and correct.** `launch-linux-agent.cjs:30` `console.log` → `console.error`; every other byte is identical to `backups/launch-linux-agent.cjs`. Since `stdio:'inherit'` (line 28) passes the child stream straight through, that trailing notice was the only launcher-originated stdout contamination, and it landed *after* the final JSON object — exactly the parse break the fix removes.
- **JSON output intact, observed not inferred.** This review's own stream at `state/foundation-practice-20260920/claude-review-stream.jsonl:11` reports `"tools":["Glob","Grep","Read"]` — the init event is well-formed and the allowlist held at exactly three tools, no Bash/Write/Edit/MCP.
- **Check count reconciles:** `4 + 8×2 = 20` (`verify-native-scope.cjs:11,27`), matching the reported pass. Env-scope assertions (`CODEX_HOME` redirected to `~/.codex`, `CLAUDE_CONFIG_DIR` dropped, unrelated vars preserved, caller env unmutated) are genuine and non-mutating; `model_requests:0` is accurate — `spawnSync` is mocked at line 17.
- **Essential rules survive the reduction.** Direct execution without approval loops, upstream-first research, evidence-class separation, one-lane retrieval, coordinator/bounded-worker rules, project-canonical memory scope, and separation of estimated reductions from provider usage all map from the backup to `~/.claude/CLAUDE.md:3-13`. `@RTK.md` is preserved (line 15).
- **Host-path hygiene improved.** The example file genericizes the two absolute `<ECOSYSTEM_HOME>/...` pointers, and dropping the `<!-- native-harness-defaults -->` block (backup lines 31-34) also removed a stale reference to a different checkout (`native-agent-stack-token-practice-review`). No repo-side emitter of those markers exists — only receipt IDs — but verify nothing in codex-ecosystem re-injects it.
- **Version pin is internally consistent:** `recipes/claude-native-profile.md:19` and `recipes/README.md:72` both say 2.1.278, and README honestly flags that auto-update can change it.
- Expected-absent links confirmed absent: `docs/community-native-practice.md`, `evidence/receipts/native-claude-profile-20260920.json`. All other recipe links resolve (`recipes/README.md`, `../examples/claude-native/CLAUDE.md`, `../catalogs/foundation/manifest.json`, `../docs/harness-defaults.md`).

## Evidence characterization (not defects)

- **The regression test is new, not pre-existing.** `backups/verify-native-scope.cjs:17` swallowed console output (`log(){},error(){}`) and counted 16 checks. The stdout/stderr capture and assertions at `:18,25,26` were authored alongside the fix. "Failed before, passes now" is true and meaningful, but describe it as *one-line launcher fix plus a new 20-check assertion* — not a standing test that caught a bug.
- **The 1175→401 figure needs its scope stated.** It is o200k_base (not Claude's tokenizer) over one artifact, and `CLAUDE.md:15` expands `@RTK.md` at load — if the count is file-bytes-only, the loaded contract exceeds 401. It also does not describe `examples/claude-native/CLAUDE.md`, which is a different text (F3). Already correctly conceded as not a provider saving; `recipes/claude-native-profile.md:102,132` state that well.

## Remaining measurements

Separate from the defects above, these are untested:

1. `/context all`, `/usage`, `/compact` — interactive session reached onboarding only, so `recipes/claude-native-profile.md:106-110` is unexercised.
2. **Skill discovery.** Byte-equality of the two ECC skills to source is established; that the names/descriptions actually appear in a Claude session — and that `~/.claude/skills` symlinks into the shared directory resolve (line 70-73) — is not.
3. The skill-installer invocation (lines 61-66) was not run; the recipe already discloses it refuses an existing destination.
4. Windows Terminal profile (lines 31-37) never launched. Two specific risks: `wsl.exe --exec` bypasses the login shell, so a PATH-dependent node shim (nvm) would fail where the login shell works; and the profile block has no `guid`. "Windows Terminal already supports Shift+Enter" (line 42) is an unverified claim.
5. The 2.1.278 pin — I did not open `claude-doctor.txt`/`claude-native-install.txt`. Re-confirm after the separate native install repair lands; I have assumed nothing about its result.
