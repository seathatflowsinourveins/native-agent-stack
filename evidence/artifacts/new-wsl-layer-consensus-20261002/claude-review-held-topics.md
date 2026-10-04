# The Claude lane's review of the Codex lane's scoped source dispositions (2026-10-02)

This is the Claude lane's independent primary-source review of the claims behind four dispositions in the Codex lane's
note (`codex-decisions.md`, section "Scoped novelty source dispositions"): the amendment to `credential-guard` (HOL
Guard held for a scoped enforcement comparison) and the three topics held without a row change (the evaluation
harness with AgentCompass, Docker Compose 5.6.0, and catalog freshness with Updatecli). The Claude lane had
acknowledged these dispositions from the note in pull request 608, comment 5959684384 (2026-10-02T19:16:53Z); this
review came afterwards and was made from the sources themselves. It was returned to the coordinator as data on
2026-10-02 and is written here as prose: each topic's disposition as the note states it, each claim with its verdict,
its sources and the reviewer's note, the reviewer's judgment and what the note omits, all as returned, except that host
paths were replaced as listed at the end. A claim marked "(Brief)" answers a question of the review's brief rather than
a claim of the note.

It gives 36 claims behind these four dispositions a verdict of confirmed, qualified (true, with a limit that the note
does not state) or refuted, reading each source at a pinned commit where it cites one and otherwise as the source stood
on 2026-10-02 (for example release pages, the release and commit feeds and Docker's apt index), and it leaves
unchecked what its notes mark as not checked or not verified, among them the "explicitly unlaunchable V2" wording
(claim 3.4), whether the repository variable that turns on scheduled proposals is set (claim 3.3), the process
statements of the Compose disposition (topic 4, omission 4) and whether Claude Code fires PermissionRequest hooks under
bypassPermissions (topic 1, omission 4); it does not re-verify the HASP claims of the custody row beyond one README
check, install or run any of these tools, measure anything, or change any decision.

Of the 36 claims, 27 are confirmed and 9 are qualified; none is refuted.

## 1. HOL Guard 3.17.1 (hashgraph-online/hol-guard @ 85090ce61ed5bb5457104b5a73cb2bbc9443fda0) vs the repository guard K4 (scripts/hooks/secret_path_guard.py)

Disposition, as the note states it: KEEP current guard; HOLD HOL Guard for scoped enforcement comparison. Note text: 'HOL3.17.1 at85090ce… (Apache-2.0) declares native interception/managed launches beyond current K4's Claude Bash text heuristic. Its matrix is a source claim; native client compatibility, failure behavior and preservation of existing hooks are unqualified. This compares enforcement with K4, separately from HASP custody/injection; do not merge unlike capabilities into one winner.' (evidence/artifacts/new-wsl-layer-consensus-20261002/codex-decisions.md:48; file mtime 2026-10-02T19:11:49Z, committed in WIP 8d2f5946b)

1. Claim: Tag v3.17.1 is commit 85090ce61ed5bb5457104b5a73cb2bbc9443fda0, and that tree is version 3.17.1.
   - Verdict: confirmed.
   - Sources: https://github.com/hashgraph-online/hol-guard/blob/85090ce61ed5bb5457104b5a73cb2bbc9443fda0/pyproject.toml#L7 ; `git ls-remote https://github.com/hashgraph-online/hol-guard refs/tags/v3.17.1` -> 85090ce61ed5bb5457104b5a73cb2bbc9443fda0 (lightweight tag)
   - Note: Observed now (2026-10-02). requires-python >=3.10 (pyproject.toml#L11).
2. Claim: Licence Apache-2.0.
   - Verdict: confirmed.
   - Sources: https://github.com/hashgraph-online/hol-guard/blob/85090ce61ed5bb5457104b5a73cb2bbc9443fda0/pyproject.toml#L10 ; https://github.com/hashgraph-online/hol-guard/blob/85090ce61ed5bb5457104b5a73cb2bbc9443fda0/LICENSE#L1-L2
   - Note: Documented: license = "Apache-2.0"; the LICENSE file is Apache License 2.0.
3. Claim: Declares native interception for Codex and Claude Code.
   - Verdict: confirmed.
   - Sources: https://github.com/hashgraph-online/hol-guard/blob/85090ce61ed5bb5457104b5a73cb2bbc9443fda0/docs/guard/harness-support.md?plain=1#L13 ; ?plain=1#L27 ; ?plain=1#L185-L186
   - Note: Documented, not observed. L13: Codex gets Guard-owned PreToolUse and PermissionRequest hooks as 'the authoritative complete-command boundary', denying shell commands 'even when Codex itself is running in YOLO mode'. L27: Claude Code has native PreToolUse and PermissionRequest coverage, but Guard does not install UserPromptSubmit, so 'native prompt submission is not intercepted'. L185-186: Codex event surfaces are shell, prompt, mcp_tool, file_read and tool_result; Claude Code's are shell, mcp_tool, file_read and tool_result.
4. Claim: Declares managed launches for Claude Code and Codex.
   - Verdict: qualified.
   - Sources: https://github.com/hashgraph-online/hol-guard/blob/85090ce61ed5bb5457104b5a73cb2bbc9443fda0/docs/guard/harness-support.md?plain=1#L15-L17 ; https://github.com/hashgraph-online/hol-guard/blob/85090ce61ed5bb5457104b5a73cb2bbc9443fda0/README.md?plain=1#L78-L83 ; harness-support.md?plain=1#L24-L29
   - Note: Managed (wrapper-mode) launch is declared for Codex only: `hol-guard run codex`, which refuses to launch when the native hooks are missing or disabled. Copilot (L35) and OpenCode (L84) also get one. The Claude Code entry (L24-29) lists no managed launch, and neither file contains `guard run claude`. Claude coverage is hooks only, installed into the project-local `.claude/settings.local.json` (L26).
5. Claim: This goes beyond K4, which is a Claude Code Bash-command text heuristic.
   - Verdict: confirmed.
   - Sources: scripts/hooks/secret_path_guard.py:2,9,76-77,4838-4839 = https://github.com/seathatflowsinourveins/native-agent-stack/blob/18eea2c1de992b46c266d79ef0cc40f93c9fb943/scripts/hooks/secret_path_guard.py#L2 (identical at origin/main 0eb47187); adoption/templates/claude.settings.template.json:176,184 ; adoption/templates/codex.hooks.template.json:2
   - Note: Observed in code. K4 is a 'Claude Code PreToolUse guard for Bash' (L2) and a 'deterministic text heuristic' (L9). It returns 0 for any tool other than Bash (L4838-4839) and says it does not inspect 'other tool types' (L76-77). It is wired only as a Claude PreToolUse hook with matcher "Bash" (template L176, L184). Codex gets no guard: the Codex template says 'B1 applies no Codex hook' and holds only the currency notice. K4 reads the command text for credential-store paths, environment dumps, secret-variable echoes, token printing, keyring reads, runner/launcher commands and OmniRoute management routes (L9-77).
6. Claim: The support matrix is a source claim, not a verified capability.
   - Verdict: confirmed.
   - Sources: https://github.com/hashgraph-online/hol-guard/blob/85090ce61ed5bb5457104b5a73cb2bbc9443fda0/docs/guard/harness-support.md?plain=1#L214-L220 ; ?plain=1#L233-L243
   - Note: Upstream says so itself: deployment health and evidence level 'default to `unverified` and `not_run`; file presence and synthetic canaries do not establish a live block'. Only Cline capability rows are generated in the document, with host/version scope 'unknown'. There are no Codex or Claude Code rows.
7. Claim: Native client compatibility and failure behaviour for Codex/Claude are unqualified.
   - Verdict: confirmed.
   - Sources: https://github.com/hashgraph-online/hol-guard/blob/85090ce61ed5bb5457104b5a73cb2bbc9443fda0/docs/guard/harness-support.md?plain=1#L247-L251 ; ?plain=1#L96 ; ?plain=1#L108 ; ?plain=1#L119 ; ?plain=1#L127 ; README.md?plain=1#L69
   - Note: What the matrix says: one general rule (L247-251), that every harness routes decisions through a bundled Rust runtime whose 'identity, protocol, rule-digest, policy-snapshot, overload, timeout, transport, and response failures fail closed'. It says nothing Codex- or Claude-specific about a crashed or timed-out hook process, and gives no client version scope. For other harnesses it states fail-open on hook crash or timeout: Kimi L96, Grok L108, ZCode L119, Devin L127 (allow envelope). README L69 claims the matrix documents failure behaviour, but the Codex and Claude entries do not.
8. Claim: Preservation of existing hooks is unqualified.
   - Verdict: confirmed.
   - Sources: https://github.com/hashgraph-online/hol-guard/blob/85090ce61ed5bb5457104b5a73cb2bbc9443fda0/docs/guard/harness-support.md?plain=1#L11 ; ?plain=1#L14 ; ?plain=1#L26 ; ?plain=1#L48 ; ?plain=1#L104 ; ?plain=1#L117 ; ?plain=1#L141
   - Note: Claude (L26) says only 'local hook install and uninstall in .claude/settings.local.json'. Codex (L11) 'detects Guard-managed native hook entries in .codex/config.toml and migrates legacy .codex/hooks.json entries' and does not say whether non-Guard entries survive. The 'unrelated profile bytes' wording at L14 covers shell profiles, not hooks. Explicit 'without overwriting user-owned hooks' appears only for Cline (L48), Grok (L104) and ZCode (L117). L141 is a general design aim ('reversible overlay behavior').
9. Claim: The enforcement comparison with K4 is separate from the HASP custody/injection comparison (unlike capabilities).
   - Verdict: confirmed.
   - Sources: https://github.com/gethasp/hasp/blob/624b3b38ac4f7a267e6925c545768c95945d781a/README.md?plain=1#L57-L63 ; ?plain=1#L114-L120 ; https://github.com/hashgraph-online/hol-guard/blob/85090ce61ed5bb5457104b5a73cb2bbc9443fda0/docs/guard/harness-support.md?plain=1#L153
   - Note: Documented. HASP is a local encrypted vault and broker: run/inject/MCP, git repo hooks that block managed secrets from commits and deploy paths, and audit. `hasp agent connect` writes MCP config for claude-code, codex-cli and cursor. It declares no agent tool-call interception. HOL Guard's secret-file intent checks (L153) overlap K4's purpose instead. This was a light check of the HASP README only; the HASP claims in item 6 were not otherwise re-verified.
10. Claim: (Brief) HOL Guard is maintained, and 3.17.1 is its current release.
    - Verdict: qualified.
    - Sources: https://github.com/hashgraph-online/hol-guard/releases/tag/v3.17.2 ; https://github.com/hashgraph-online/hol-guard/releases/tag/v3.17.1 ; https://github.com/hashgraph-online/hol-guard/commits/main.atom
    - Note: Observed now. The project is heavily maintained. v3.17.1 was released 2026-10-02T15:18:08Z. v3.17.2 was released 2026-10-02T21:12:17Z, is marked Latest, and /releases/latest redirects to it; it was cut from 9754d139, after the note was written. The last main commit is c968b755 at 2026-10-02T22:07:37Z. releases.atom lists six releases on 2026-10-02 alone (v3.16.3 to v3.17.2, by feed-updated time).

Judgment: The disposition follows from the sources. HOL Guard declares a wider surface than K4 (Codex hooks, non-Bash events), but upstream labels its own capability rows unverified and says nothing Claude- or Codex-specific about hook crash/timeout behaviour or keeping existing user hooks. Holding it for a scoped enforcement comparison, kept apart from HASP custody, is supported. That comparison should pin 3.17.2 or later and treat Claude Code as hook-only.

Omitted by the note: (1) 3.17.2 replaced 3.17.1 about two hours after the note's file time. It includes 'Restore native hook review across frozen launches and linked worktrees (#3411)', which matters for this worktree-heavy repository. With six releases in one day, the comparison needs a frozen pin. (2) Claude Code has no managed launch. HOL's Claude hooks go into the project-local .claude/settings.local.json, while K4 is installed at user scope by tools/adoption/install_claude_profile.py:6,51,59. (3) K4's own failure behaviour, to test both guards under the same failure modes. It blocks (exit 2) on oversize input, budget overrun and internal error (secret_path_guard.py:4843-4862). Unreadable hook input exits 1 and the command runs (L4835-4837). By its own comments, a hook that times out blocks nothing (L4844, L4858). The settings wrapper does nothing when the guard file is absent (claude.settings.template.json:184; 10 s timeout at L185). (4) The Claude profile sets "defaultMode": "bypassPermissions" (claude.settings.template.json:169), and HOL's Claude coverage relies on PreToolUse plus PermissionRequest (matrix L27). Whether PermissionRequest hooks fire under bypassPermissions is a condition to verify; Claude Code docs were not checked here. (5) HOL's Codex adapter 'migrates legacy .codex/hooks.json entries' (L11). That could touch the repository's template-only Codex SessionStart notice in hooks.json (codex.hooks.template.json:2); not verified. (6) HOL runs a resident runtime and approval centre (matrix L143-149; the 3.17.2 notes mention a managed resident and daemon budgets). The comparison therefore needs restart and removal lifecycle checks; K4 is a stateless hook.

## 2. AgentCompass 1.0.0 (open-compass/AgentCompass @ 2b2a272ed2a00231d4dff3c2e33e21fa8a28593e)

Disposition, as the note states it: KEEP Inspect 0.3.273/Harbor 0.23; AgentCompass only for an identified unmet evaluation requirement. Note text: 'AgentCompass1.0.0 at2b2a272… (Apache-2.0, Python>=3.12) supplies composable harness/environment/trajectory/resume machinery; comparative advantage is unmeasured. Codex/Claude adapters default permission bypass on and Claude supplies provider API configuration, so native account-route equivalence is not established. No adapter or permission change is adopted.' (codex-decisions.md:49)

1. Claim: Tag v1.0.0 is commit 2b2a272ed2a00231d4dff3c2e33e21fa8a28593e, and that tree is version 1.0.0.
   - Verdict: confirmed.
   - Sources: https://github.com/open-compass/AgentCompass/blob/2b2a272ed2a00231d4dff3c2e33e21fa8a28593e/pyproject.toml#L7 ; `git ls-remote https://github.com/open-compass/AgentCompass refs/tags/v1.0.0` -> 2b2a272e… ; https://github.com/open-compass/AgentCompass/releases/tag/v1.0.0
   - Note: Observed now. Released 2026-09-30T12:33:11Z, marked Latest, and it is the only release. main has since moved to 00027285.
2. Claim: Licence Apache-2.0.
   - Verdict: confirmed.
   - Sources: https://github.com/open-compass/AgentCompass/blob/2b2a272ed2a00231d4dff3c2e33e21fa8a28593e/pyproject.toml#L11-L12 ; https://github.com/open-compass/AgentCompass/blob/2b2a272ed2a00231d4dff3c2e33e21fa8a28593e/LICENSE#L1-L3 ; README.md?plain=1#L95
   - Note: Documented. The LICENSE file opens with 'Copyright 2026 AgentCompass Authors. All rights reserved.' followed by the Apache License text.
3. Claim: Python >= 3.12.
   - Verdict: confirmed.
   - Sources: https://github.com/open-compass/AgentCompass/blob/2b2a272ed2a00231d4dff3c2e33e21fa8a28593e/pyproject.toml#L10
   - Note: The note's #L5 anchor points to the [project] header. The value requires-python = ">=3.12" is on L10. The classifier says 'Development Status :: 4 - Beta' (L16).
4. Claim: Supplies composable harness/environment/trajectory/resume machinery.
   - Verdict: confirmed.
   - Sources: https://github.com/open-compass/AgentCompass/blob/2b2a272ed2a00231d4dff3c2e33e21fa8a28593e/README.md?plain=1#L31 ; ?plain=1#L37-L40
   - Note: Documented. The README says it decouples Model, Benchmark, Harness and Environment, runs locally, in Docker or in remote sandboxes, and supports resumable evaluations and trajectory, tool-call, usage and latency records.
5. Claim: The Codex adapter turns permission bypass on by default.
   - Verdict: confirmed.
   - Sources: https://github.com/open-compass/AgentCompass/blob/2b2a272ed2a00231d4dff3c2e33e21fa8a28593e/src/agentcompass/harnesses/codex.py#L62-L65 ; #L112 ; #L388-L392
   - Note: Observed in code. dangerously_bypass_approvals_and_sandbox defaults to True, and the launch argv appends --dangerously-bypass-approvals-and-sandbox next to --sandbox (default workspace-write, L53-56).
6. Claim: The Claude adapter turns permission bypass on by default.
   - Verdict: confirmed.
   - Sources: https://github.com/open-compass/AgentCompass/blob/2b2a272ed2a00231d4dff3c2e33e21fa8a28593e/src/agentcompass/harnesses/claude_code.py#L64-L67 ; #L110 ; #L346-L347 ; #L352-L353
   - Note: Observed in code. dangerously_skip_permissions defaults to True, which appends --dangerously-skip-permissions. The adapter also sets IS_SANDBOX=1 in that case (its semantics were not checked here).
7. Claim: The Claude adapter supplies provider API configuration.
   - Verdict: confirmed.
   - Sources: https://github.com/open-compass/AgentCompass/blob/2b2a272ed2a00231d4dff3c2e33e21fa8a28593e/src/agentcompass/harnesses/claude_code.py#L278-L300 ; #L323-L324 ; #L345
   - Note: Observed in code. It raises RuntimeError without an Anthropic-compatible base URL and API key (L280-283). It writes ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN and model overrides into a settings JSON (by default /tmp/agentcompass-claude-<uuid>/settings.json) and launches with --settings.
8. Claim: Therefore native account-route equivalence is not established (the note names only the Claude adapter as supplying provider configuration).
   - Verdict: qualified.
   - Sources: https://github.com/open-compass/AgentCompass/blob/2b2a272ed2a00231d4dff3c2e33e21fa8a28593e/src/agentcompass/harnesses/codex.py#L126-L128 ; #L318-L342 ; #L488-L491
   - Note: Understated. The Codex adapter has the same requirement: it raises without an OpenAI-compatible base URL and API key (L320-323), writes its own CODEX_HOME config.toml with model_provider = "agentcompass" and env_key CODEX_API_KEY, and injects CODEX_API_KEY. As shipped, neither adapter can run on a native subscription sign-in. Both need an API-key and base-URL route, such as a gateway.
9. Claim: The incumbents are Inspect AI 0.3.273 and Harbor 0.23.
   - Verdict: confirmed.
   - Sources: evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json:1394-1397,1432-1435 = https://github.com/seathatflowsinourveins/native-agent-stack/blob/18eea2c1de992b46c266d79ef0cc40f93c9fb943/evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json#L1394-L1435
   - Note: Observed in the selected plan: inspect-ai 0.3.273 and Harbor v0.23.0. The file is unchanged at origin/main.
10. Claim: No adapter or permission change is adopted.
    - Verdict: confirmed.
    - Sources: `rg -i -c "agentcompass|hol-guard|updatecli" --glob '!evidence/**' .` in a read-only checkout of origin/main (0eb47187)
    - Note: Observed now. The only hit outside evidence/ is docs/decisions/2026-10-02-daily-catalog-currency.md (3 matches, all Updatecli). AgentCompass appears nowhere.
11. Claim: Its comparative advantage is unmeasured.
    - Verdict: confirmed.
    - Sources: https://github.com/open-compass/AgentCompass/blob/2b2a272ed2a00231d4dff3c2e33e21fa8a28593e/README.md?plain=1#L31-L40
    - Note: The reviewed sources contain no head-to-head result against Inspect or Harbor. Upstream cites its own paper (README L122-123), which was not reviewed.

Judgment: The disposition follows from the sources. AgentCompass 1.0.0 is a Beta-classified sole release from 2026-09-30, and both its Codex and Claude adapters default to permission bypass and require API-key/base-URL provider configuration. It cannot stand in for the native-account Inspect/Harbor path without adapter changes, so adopting it only for a named unmet requirement is supported.

Omitted by the note: (1) The Codex adapter also requires an API key and base URL and writes its own CODEX_HOME config; the note attributes provider configuration to the Claude adapter only. (2) The Claude adapter writes the API key in plaintext into a settings JSON, by default under /tmp (claude_code.py L285-300, L323-324; file mode not verified). That conflicts with the repository's rule that credentials stay in 0600 env files passed by pointer (AGENTS.md, docs/secret-storage.md). (3) Both adapters default to install_strategy 'install_if_missing' with an unpinned `npm install -g @openai/codex` or `@anthropic-ai/claude-code` (codex.py L38-45, claude_code.py L40-47). An evaluation environment could therefore get a client other than the selected Codex 0.160.0 or Claude 2.1.287. (4) The note's pyproject anchor #L5 should be #L10 (python), #L11 (licence) and #L7 (version).

## 3. Updatecli 0.122.0 (updatecli/updatecli @ 20e57d1b35190c25e41f3e2a8339621027484c0c) vs .github/workflows/catalog-freshness.yml

Disposition, as the note states it: KEEP existing automation; qualify daily source reporting. Note text: 'Existing catalog-freshness is weekly metadata/drift reporting with guarded evidence-only proposal PRs. Root's separate daily-currency branch changes that cadence and corrects notice documentation; it does not start the explicitly unlaunchable V2 landscape model sweep. Updatecli0.122.0 at20e57d1b supplies source/condition/target policies and overlaps that existing mechanism. No demonstrated extra closure warrants a new dependency. Claude notice registration and Codex template-only native /hooks review remain different adoption states. Current notice code uses eight days; a historical48h statement needs a dated correction.' (codex-decisions.md:47)

1. Claim: Updatecli 0.122.0 is commit 20e57d1b.
   - Verdict: confirmed.
   - Sources: `git ls-remote https://github.com/updatecli/updatecli 'refs/tags/v0.122.0^{}'` -> 20e57d1b35190c25e41f3e2a8339621027484c0c (annotated tag object b1546c23) ; https://github.com/updatecli/updatecli/releases/tag/v0.122.0
   - Note: Observed now. Released 2026-09-26T19:33:30Z and marked Latest. Apache-2.0 (https://github.com/updatecli/updatecli/blob/20e57d1b35190c25e41f3e2a8339621027484c0c/LICENSE#L1-L2). The note's README.md link resolves (HTTP 200).
2. Claim: Updatecli supplies source/condition/target policies.
   - Verdict: confirmed.
   - Sources: https://github.com/updatecli/updatecli/blob/20e57d1b35190c25e41f3e2a8339621027484c0c/README.md?plain=1#L18-L28
   - Note: Documented. It is a declarative update policy engine. Sources fetch the new value, Conditions verify prerequisites, and Targets apply the change and open a pull request when an SCM is configured ('Automatically open a PR … when a file update is needed').
3. Claim: The existing catalog-freshness workflow is weekly metadata/drift reporting with guarded evidence-only proposal PRs.
   - Verdict: qualified.
   - Sources: https://github.com/seathatflowsinourveins/native-agent-stack/blob/18eea2c1de992b46c266d79ef0cc40f93c9fb943/.github/workflows/catalog-freshness.yml#L5 ; https://github.com/seathatflowsinourveins/native-agent-stack/blob/0eb47187925bf8134660b7a305aa32b0d44b9e17/.github/workflows/catalog-freshness.yml#L5 ; same file #L17-L18 ; #L176-L195
   - Note: Weekly ('17 6 * * 1') was true at the note's pin 18eea. Since #613 (0eb47187, merged 2026-10-02T21:35:12Z) it runs daily ('17 6 * * *'). The rest is confirmed: the reporting job is read-only. The proposal job only adds files under evidence/artifacts and evidence/receipts plus the evidence.json registration, and never writes manifests/stack.json, catalogs/landscape/*.json or catalogs/sota-convergence/* (L176-181). It runs only on a manual open_pr dispatch or on a schedule with CATALOG_FRESHNESS_PROPOSE == 'true', and only for an unbounded, error-free fetch (L182-195). Whether that repository variable is set was not checked.
4. Claim: Root's separate daily-currency branch changes the cadence and corrects the notice documentation, without starting the landscape sweep.
   - Verdict: qualified.
   - Sources: https://github.com/seathatflowsinourveins/native-agent-stack/blob/0eb47187925bf8134660b7a305aa32b0d44b9e17/docs/decisions/2026-10-02-daily-catalog-currency.md?plain=1#L3-L16 ; `git show 0eb47187 -- docs/decisions/2026-09-30-session-currency-notice.md`
   - Note: The branch is no longer separate: it merged to main as #613 after the note's file time (19:11:49Z). The decision record says the change 'neither sets the opt-in nor enables the separate landscape sweep' (L15-16). The 'explicitly unlaunchable V2' wording itself was not checked.
5. Claim: Updatecli overlaps the existing mechanism.
   - Verdict: qualified.
   - Sources: https://github.com/seathatflowsinourveins/native-agent-stack/blob/0eb47187925bf8134660b7a305aa32b0d44b9e17/.github/workflows/catalog-freshness.yml#L47-L106 ; #L176-L181 ; https://github.com/updatecli/updatecli/blob/20e57d1b35190c25e41f3e2a8339621027484c0c/README.md?plain=1#L24-L28
   - Note: The overlap is in detection only. Updatecli's sources and conditions correspond to the workflow's freshness fetch, manifest rebuild and drift diff (L47-106). Its distinguishing stage, targets that edit pinned files and open PRs with those edits, is exactly what the workflow withholds (L176-181), because pins are owned by the separate convergence review.
6. Claim: No demonstrated extra closure warrants a new dependency.
   - Verdict: confirmed.
   - Sources: https://github.com/seathatflowsinourveins/native-agent-stack/blob/0eb47187925bf8134660b7a305aa32b0d44b9e17/docs/decisions/2026-10-02-daily-catalog-currency.md?plain=1#L18-L21
   - Note: The decision record on main already says: 'updatecli/updatecli v0.122.0 was reviewed as an upstream alternative; the gap is the cadence of an existing report, so no additional updater is adopted or installed.' The cron change closes the cadence gap.
7. Claim: The current notice code uses eight days.
   - Verdict: confirmed.
   - Sources: adoption/hooks/claude/currency-due-notice.py:39 = https://github.com/seathatflowsinourveins/native-agent-stack/blob/18eea2c1de992b46c266d79ef0cc40f93c9fb943/adoption/hooks/claude/currency-due-notice.py#L39
   - Note: Observed: MAX_AGE = timedelta(days=8). The file is unchanged from 18eea to 0eb47187 (`git diff --quiet` exit 0).
8. Claim: A historical 48h statement needs a dated correction.
   - Verdict: qualified.
   - Sources: `git show 0eb47187925bf8134660b7a305aa32b0d44b9e17 -- docs/decisions/2026-09-30-session-currency-notice.md`
   - Note: The correction has since landed. #613 adds '**Correction (2026-10-02):** the implemented notice uses `MAX_AGE = timedelta(days=8)`, not the 48-hour …' and keeps the original text.
9. Claim: Claude notice registration and Codex template-only /hooks review are different adoption states.
   - Verdict: confirmed.
   - Sources: adoption/templates/claude.settings.template.json:232 ; tools/adoption/install_claude_profile.py:11,57 ; adoption/templates/codex.hooks.template.json:2 (a read-only checkout of main at 0eb47187)
   - Note: Observed. The Claude template registers currency-due-notice.py and the profile installer copies it. The Codex file is 'a template only, not applied by any installer; B1 applies no Codex hook', and Codex lists the hook as untrusted until it is reviewed in /hooks.

Judgment: 'No new dependency' is supported. The existing workflow already does daily detection and guarded, evidence-only reporting, and the Updatecli capability it lacks (automated target edits and PRs on pins) is what the repository's pin-ownership rule deliberately keeps out of automation. The note's 'weekly' and 'separate branch' wording is now out of date.

Omitted by the note: (1) #613 merged at 2026-10-02T21:35:12Z, so the consensus record should cite catalog-freshness.yml at 0eb47187 (daily) rather than 18eea (weekly). The decision record also states the cron change 'is not evidence of a newly executed scheduled run' (L6-7). (2) The Updatecli disposition is already recorded on main (daily-catalog-currency.md L18-21), so the consensus record can cite it. (3) Scheduled proposal PRs need CATALOG_FRESHNESS_PROPOSE=true, which was not checked. Without it, daily runs produce report artifacts only.

## 4. Docker Compose 5.6.0 (docker/compose tag v5.6.0, commit 42f48072bbf92ee9b0e43f9fdf2008d03546e7ca)

Disposition, as the note states it: QUALIFY Compose 5.6.0 update; retain selected 5.5.1 until owner acceptance. Note text: 'Official42f48072… (Apache-2.0) is the same incumbent, with dry-run/config-hash/watch/monitor/log fixes. Its jobs are manual-only, not a new scheduling substitute. Root has assigned isolated official-package version/help binding and supported-test prerequisite review; no daemon/container/global/target installation or rootless acceptance occurs.' (codex-decisions.md:50)

1. Claim: The official release v5.6.0 is commit 42f48072.
   - Verdict: confirmed.
   - Sources: https://github.com/docker/compose/releases/tag/v5.6.0 ; `git ls-remote https://github.com/docker/compose 'refs/tags/v5.6.0^{}'` -> 42f48072bbf92ee9b0e43f9fdf2008d03546e7ca (annotated tag object 3626e0e4)
   - Note: Observed now. Released 2026-10-02T16:07:06Z by github-actions and marked Latest. The commit signature was verified 2026-10-02 15:37:05 UTC. 42f48072 is also the current main HEAD.
2. Claim: Licence Apache-2.0.
   - Verdict: confirmed.
   - Sources: https://github.com/docker/compose/blob/42f48072bbf92ee9b0e43f9fdf2008d03546e7ca/LICENSE#L2-L3
   - Note: Documented: Apache License, Version 2.0.
3. Claim: It is the same incumbent as the selected 5.5.1.
   - Verdict: confirmed.
   - Sources: https://github.com/seathatflowsinourveins/native-agent-stack/blob/18eea2c1de992b46c266d79ef0cc40f93c9fb943/evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json#L1736-L1773
   - Note: The plan's docker-compose slot selects docker/compose v5.5.1 through the official apt docker-compose-plugin, matched exactly and failing if unavailable (notes at L1773).
4. Claim: The release's changes are dry-run, config-hash, watch, monitor and log fixes.
   - Verdict: qualified.
   - Sources: https://github.com/docker/compose/releases/tag/v5.6.0
   - Note: Those fixes are present: dry-run #14150 and #14270, config-hash #14215 and #14253, watch #14202, up monitor #14990→#13990, logs #14140. The list is incomplete. The release also adds partial jobs (#14093); provider-service relay networks and image phase (#14175, #14193, #14258, #14275, #14252); warnings for unsupported compose-file attributes (#14196); optional PRIVATE_PORT for `docker compose port` (#13577); --parallel honoured across all bulk engine-call fan-outs (#14177); `down --rmi` dangling-image handling (#14266); port tie order (#14213); an OCI publish fallback warning (#14146); build progress handed to bake (#14194); compose-go v2.16.1 x-initialSync (#14281); reconciler and pre_start runner changes (#14200, #14221); and dependency bumps: docker/cli 29.8.2 (#14279), moby api module 1.56.0 (#14211), moby/containerd (#14282), containerd v2.3.5 (#14183), buildkit 0.33.1 (#14277) and moby/sys/userns v0.2.1 (#14199).
5. Claim: Its jobs are manual-only, not a new scheduling substitute.
   - Verdict: confirmed.
   - Sources: https://github.com/docker/compose/releases/tag/v5.6.0
   - Note: Documented in the release notes: 'only manually-triggered jobs are supported for now, scheduled jobs are not yet available. Full job support will land once the corresponding Docker Engine support is merged.'
6. Claim: (Brief) Nothing in 5.6.0 changes behaviour that the install plan or the rootless engine relies on.
   - Verdict: qualified.
   - Sources: install-plan.json#L1760-L1763, #L1777-L1831, #L2393-L2399 (blob at 18eea above) ; evidence/artifacts/new-wsl-install-plan-20261002/install.sh:104-124 ; https://github.com/docker/compose/pull/14215 ; https://github.com/docker/compose/pull/14253 ; https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/docker/docker-compose-dev.yaml ; https://raw.githubusercontent.com/bytedance/deer-flow/v2.1.0/docker/docker-compose.yaml
   - Note: The plan relies on four things: `docker compose version`; an exact apt install of 5.5.1; DeerFlow's `docker compose -p deer-flow-dev -f docker-compose-dev.yaml config --quiet` and `restart: unless-stopped`; and the rootless Engine 29.8.2 user socket. No release note mentions rootless, and the docker/cli 29.8.2 bump matches the selected Engine. Upstream states historical config hashes are preserved (#14215 commit: 'Golden hashes unchanged'; #14253: TestHashGoldenValues 'passes unchanged … preserved every historical hash', 'no release shipped in that window'). So 5.5.1-created containers should not be force-recreated, but this is not verified on a host, and nothing is claimed about volume hashes. DeerFlow v2.1.0's two Compose files contain none of the Swarm-only attributes #14196 warns about; they have only service_started/service_healthy conditions (dev L253; main L62, L64, L151), so no new warnings are expected (by inspection, not execution). The --parallel change matters only if a limit is set. API negotiation with the moby api module 1.56.0 against Engine 29.8.2 was not verified.

Judgment: The disposition follows from the sources. 5.6.0 is the same project's newest release, published the same day as the note, with no rootless-specific change and an upstream statement that config hashes are preserved. It still carries functional changes well beyond the five fix areas the note names (jobs, provider relay networks, new warnings, --parallel scope, engine-library bumps), so qualifying it before replacing 5.5.1 is supported. However, the plan enforces 5.5.1 only at install time.

Omitted by the note: (1) Release date: 2026-10-02T16:07:06Z, about three hours before the note's file time. (2) Docker's Ubuntu Resolute apt channel already carries docker-compose-plugin 5.6.0-1~ubuntu.26.04~resolute next to 5.5.1-1 (https://download.docker.com/linux/ubuntu/dists/resolute/stable/binary-amd64/Packages, Last-Modified Fri, 02 Oct 2026 16:29:41 GMT, observed now). install.sh installs 5.5.1 exactly (L120-124) and fails if it is absent (L104-112), but nothing in the plan directory holds the package (no apt-mark hold or apt preferences found). A later `apt upgrade` would therefore move to 5.6.0 without the review. containerd.io and docker-buildx-plugin are also installed unpinned (install.sh L117-118). (3) The DeerFlow supporting source cites compose_config.md at the 5.5.1 commit 5f94fb0a (install-plan.json:2444); re-anchor it if 5.6.0 is accepted. (4) The process statements (root-assigned package/help binding review; no installation or rootless acceptance) cannot be checked against upstream and were not verified here. (5) No gh api calls were used (0 of 15).

## Replacements

The review named files on the host where it ran. Those host paths are not published; nothing else differs from the review as it was returned.

- A path to a read-only checkout of main, in front of a repository path, was removed, so that the repository path stays: in the sources of claims 1.5, 2.9, 3.7 and 4.6.
- The same checkout, named as the place where a command ran, is written "a read-only checkout of origin/main" (claim 2.10), and its folder name is written "a read-only checkout of main" (claim 3.9).
- A path to the checkout of this record's branch, in front of a repository path, was removed in the disposition of topic 1.
