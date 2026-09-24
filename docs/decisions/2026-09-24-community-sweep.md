# Decision: community-practice sweep dispositions (2026-09-24)

**Decided by:** unit `community-adoptions`, branch `claude/community-adoptions-20260924`
(base `origin/main@e2f014fd`), from the coordinator's verified adoption list for the
community sweep dated 2026-09-24 UTC (2026-09-23 on this host's clock).

**Scope:** twelve community and Anthropic repositories at the pins in
[the 2026-09-24 review](../community-native-practice.md#2026-09-24-review), 69 items:
15 adopt, 14 needs-measurement, 40 reject. The verifier checked each item against current
code.claude.com documentation and against the default-branch heads of this catalog
(`e2f014fd`) and of the adopted project, agent-lab (`a458886`). This change applies the
catalog adoptions A6, A12 and A15. A14's catalog half is left to the owner of the file it
touches, and every other item is listed with where it applies or why it was not taken.
Nothing here installs a repository, edits live settings or calls a model.

## Adoptions

| ID | Source | Change | Where it applies | Status in this change |
| --- | --- | --- | --- | --- |
| A1 | anthropics/claude-code-action (item 11) | Stop exporting broker and Hugging Face credentials into every shell (PS-6). First give the three `os.environ` consumers (`alpaca-paper/paper_runner.py`, `alpaca-historical/collect.py`, `security-identity/probe.py`) the `--env-file` loading that `adaptive-paper/runner.py` already uses, then delete the exports from the shell start-up files. | `blueprints/us-equities/` and the host's dotfiles | Not applied: pending its owner. Another session owns `blueprints/`, and the dotfiles are host state. |
| A2 | karanb192/claude-code-hooks | Project-level override for the built-in Explore subagent (Sonnet at effort max, source-scout-shaped body), a routing row, and an explicit decision for Plan. All 31 measured Explore children ran on Opus. | agent-lab | Not applied here (agent-lab). |
| A3 | wshobson/agents (#6) | `child-usage.mjs` flags content-classifier fallback with a version-aware rule, with fixtures. | agent-lab, then re-vendored to this catalog | Not applied here. |
| A4 | wshobson/agents (#19, part 1) | The contract suite requires a non-empty agent `description`, with a mutation case. | agent-lab | Not applied here. |
| A5 | wshobson/agents (#19, part 2) | The e2e `claude plugin validate` step fails on warnings, and a `.claude/skills` step is added. | agent-lab | Not applied here. |
| A6 | karanb192/claude-code-hooks | The effort guard stops relying on SessionEnd output: a self-heal leaves a one-line notice that the next SessionStart shows once and deletes. | `adoption/hooks/claude/effort-default-guard.py`, `adoption/hooks/claude/SHA256SUMS`, `tests/test_effort_default_guard.py`, `recipes/claude-native-profile.md` | Applied. The host copy in `~/.claude/hooks/` follows after merge (`python3 tools/adoption/install_claude_profile.py --only guard`); until then `test_shipped_guard_is_verbatim` fails on a host that still has the old copy. |
| A7 | hesreallyhim/awesome-claude-code | Point the acceptance-policy link at agent-lab `AGENTS.md:8` to a path that resolves from worktree checkouts. | agent-lab | Not applied here. |
| A8 | addyosmani/agent-skills (#72); Yeachan-Heo/oh-my-claudecode | The integrating coordinator stages explicit paths only and never runs `git add -A`, `git add .` or `git commit -a`. | agent-lab `AGENTS.md` | Not applied here. |
| A9 | Yeachan-Heo/oh-my-claudecode | Root-anchored ignores for two stray root artifacts, and a per-path decision for the compare outputs. | agent-lab `.gitignore` | Not applied here. |
| A10 | addyosmani/agent-skills (#77) | Guard `run-arms.mjs`'s recursive delete: one path component, strictly under its index root. | agent-lab | Not applied here. |
| A11 | anthropics/skills (drift under the marketplace gap) | Re-sync two stale user-level agents, merge this catalog's branch `claude/max-effort-default-20260923`, and decide whether `adoption/agents/claude/` ships all seven agents. | user-level agents; this catalog's max-effort branch | Not applied here: owned by the max-effort change. |
| A12 | shanraisshan/claude-code-best-practice | Correct records that credit sandbox configuration that does not exist. | [The devcontainer row](../community-native-practice.md#2026-09-23-review) of the community practice page; agent-lab `README.md:9` | Applied here (catalog half). |
| A13 | shanraisshan/claude-code-best-practice | Record-only notes under PS-1 (an opt-in, skill-scoped PreToolUse deny hook is the first response if its overturn fires) and MI-7 (count a future budget in bytes or tokens). | agent-lab harness-rules record | Not applied here. |
| A14 | shanraisshan/claude-code-best-practice (record gap) | Add review-changes.js as an arm of the planned seeded-defect review comparison, beside native /code-review, the /codex:review lanes and OCR, at equal quota. | `catalogs/sota-convergence/manifest-20260923.json` (the alibaba/open-code-review overturn text) and an agent-lab keep-but-compare row | Not applied: outside this change's listed scope. The manifest is registered evidence last changed by the landscape-sweep lane (#153), so its owner adds the arm. |
| A15 | anthropics/claude-plugins-official (item 1, record half) | The context-mode commit is a reviewed revision, not an enforced pin, and the new-PC bootstrap checks `installed_plugins.json` against the recipe table. | `recipes/README.md`, `adoption/bootstrap.md` step 4a, `tests/test_adoption_docs_consistency.py` | Applied. |

### A6: effort-guard notice handoff

The [hooks reference](https://code.claude.com/docs/en/hooks) (fetched 2026-09-24) says
SessionEnd hooks have no decision control and "Claude Code discards their JSON output fields,
such as `systemMessage`". The guard's SessionEnd self-heal therefore saved
`modelSettings.<model>.effortLevel = "xhigh"` silently, although its docstring said it
"says so".

- **SessionEnd:** every precedence rule is unchanged. After a successful save, the guard also
  appends one line to `~/.claude/effort-default-guard.notice` (created `0600`, opened with
  `O_NOFOLLOW`). It still prints its previous `systemMessage`, which Claude Code discards.
- **SessionStart:** when the event carries `model`, the guard claims the notice with an atomic
  rename, so exactly one of several simultaneous starts shows it. It then shows the notice
  through the existing `systemMessage` plus `additionalContext` output and deletes it. A
  predictive warning in the same event shares that one JSON object. The same reference says
  `model` "can be omitted, for example after `/clear` or when a session is restored through
  conversation recovery"; such an event leaves the notice for the next start that reports a
  model. The template registers the guard for `startup` and `resume` only.
- **Fail-safe:** the guard still exits 0 and never blocks. If the notice path cannot be
  written (for example, it is a directory), the notice is skipped and the save still happens.
- **Known limits.** Delivery is best effort; the saved setting never depends on it.
  - The same reference says a `/clear` or conversation switch while SessionStart hooks are
    still running discards what they return. A notice claimed by that start is lost.
  - The docs do not say whether headless `claude -p` starts carry `model`; the guard's
    docstring records that they omit it. A headless start that does carry it would consume
    the notice where no one reads it.

### A12: sandbox record correction

The devcontainer row credited "the project's own sandbox/permission settings". None exist.
The catalog's settings template, this host's user settings and agent-lab's
`.claude/settings.json` have no `sandbox` key, and that project file has no `permissions` key
either (inspected 2026-09-24). Isolation is native worktrees plus a per-task
[sandbox-runtime](../../recipes/README.md#on-demand-isolation) policy around owned commands
(PERM-09 in [the harness rules convergence](../harness-rules-convergence-20260922.md)).
Enabling the built-in Bash sandbox stays M1.

### A15: context-mode reviewed revision

- **Documentation.** [Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
  (fetched 2026-09-24): "Git-based marketplace sources support `ref` (branch/tag) but not
  `sha`". `marketplace add` pins "a branch or tag" with `@ref`, and third-party marketplaces
  have auto-update off by default ([discover plugins](https://code.claude.com/docs/en/discover-plugins)).
- **Measured on this host**, Claude Code 2.1.281 with a scratch `CLAUDE_CONFIG_DIR`:
  - `claude plugin marketplace add mksglu/context-mode@6f0cc68…` exited 1 with a failed clone.
    Claude Code's SSH fallback then failed host-key verification here.
  - Plain `git clone --branch 6f0cc68…` fails with "Remote branch … not found".
  - The same command without a ref succeeded, recorded `{"source": "github", "repo":
    "mksglu/context-mode"}` with no ref, and checked out `5a92b7c`. That head is six commits
    past `6f0cc68`, and the six change only `stats.json` (`gh api` compare).
- **Recipe changes.** The recipe now installs with the documented no-ref form and calls
  `6f0cc68` a reviewed revision. The claude-hud row gains `ef5f1c8…`, the commit that its
  annotated tag `v0.8.0` dereferences to (`gh api`). codex-for-claude's `db52e28…` is tag
  `v1.0.6`'s commit.
- **Bootstrap check.** Step 4a compares `installed_plugins.json` `gitCommitSha` with those
  three commits. On this host it printed `ok` for all three. Against a synthetic registry
  holding `5a92b7c` it printed `MISMATCH`, and it reported a missing plugin as not installed.
  `PluginRevisionCheckTests` binds the step's copy of the commits to the recipe rows.

## Keep-but-compare

Each item stays keep-but-compare until its named measurement runs. Adopt only on the stated
result. M4, M7 and M9 also require dispatch through Agent-tool workers or the coordinator
rather than a workflow stage, because they spend account usage, with that usage recorded by
`child-usage.mjs`.

| ID | Source | Candidate change | Named measurement and adoption rule |
| --- | --- | --- | --- |
| M1 | shanraisshan/claude-code-best-practice | Enable the built-in Bash sandbox (`sandbox.enabled`) in user settings. | PERM-09's named test: one throwaway session launched with `claude --settings` set to `sandbox.enabled: true` and `allowUnsandboxedCommands: false`. In it, run the RTK hook, `rtk proxy`, the guarded gitleaks, `gh`, qmd, SocratiCode/Qdrant and ai-memory on 127.0.0.1, and the codex companion, and record every command that fails. Adopt only if every command passes and the user opts in, or if a worker is observed taking a harmful action. |
| M2 | shanraisshan/claude-code-best-practice | `.claude/rules/*.md` with `paths` frontmatter for lazily loaded conventions. | MI-5's session pair: the pointer list was ignored, and a paths-scoped rule (for example on `.claude/workflows/**`) changed which files were read. |
| M3 | shanraisshan/claude-code-best-practice | Keep sessions under 30-40% context usage. | SIZE-07's local trial ties utilization above 40% to measurably worse extraction or review quality in the child-usage records. Then set `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` or `autoCompactWindow`. |
| M4 | anthropics/claude-code | A short fail-open checklist in evidence-reviewer or the review-changes reviewer packet. | Replay review-changes.js on this catalog's `d093a4c^..d093a4c` in a scratch worktree, in two arms at the current reviewer configuration (with and without the checklist); an optional third arm unions two samples. Adopt only if the checklist arm recovers at least one of the three Codex-found fail-open majors that the baseline misses, without more refuted findings. |
| M5 | anthropics/claude-code-action (item 11, second half) | `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` as a second layer after A1. | A scratch headless session with the scrub on and the five credential names present. Record which names a Bash child, a hook and an MCP-stdio child can still read, and whether the ai-memory hooks, the RTK hook, `rtk proxy`, the guarded gitleaks and the codex companion still work. Adopt only if the names are stripped and nothing breaks. Known side effects: on 2.1.251+ it removes `CLAUDE_CONFIG_DIR` from children, and on Linux Bash runs in its own PID namespace. |
| M6 | anthropics/claude-code-action (item 12) | Replace `--bare` in HOST-07 and the profile invariants with a flag set that keeps the OAuth login and keeps the project's env block out. | Build a scratch repo with a project settings env marker and marker hook, a project skill with a frontmatter hook and `allowed-tools`, a subagent with a frontmatter hook, a `.mcp.json` server and a `CLAUDE.md` marker. Run one OAuth `claude -p` per arm: `--setting-sources user`; `--safe-mode`; `--restricted`; `--safe-mode --setting-sources user`. Record auth success, marker visibility and hook runs. Adopt the cheapest arm that isolates every marker with OAuth; keep HOST-07 if `--bare` alone already blocks the env block. |
| M7 | anthropics/skills | The effort sweep that is the first overturn condition of the max-effort decision; it also re-baselines the pre-Opus 5.5 routing receipts. | The same frozen packets at max, xhigh and high for source-scout, isolated-builder, evidence-reviewer and blind-judge, with preregistered quality metrics, repeats, and usage per completed task. Lower a role only where max shows no quality gain at higher cost. |
| M8 | anthropics/claude-plugins-official (item 1) | Enforce the three plugin pins natively: catalog-owned `marketplace.json` files whose plugin entries carry a 40-character `sha`, plus a CI check that each equals the recipe table. | Install from the new manifests into a scratch `CLAUDE_CONFIG_DIR`. Check that `installed_plugins.json` `gitCommitSha` equals `6f0cc6841c687e754059f36714a11233fda1a02b`, `ef5f1c8b167572ad1443c70629763ea8780af96b` and `db52e28f4d9ded852ab3942cea316258ae4ef346`, that context-mode's hooks fire, that its cache-heal still matches `context-mode@context-mode`, and that the HUD resolves. Adopt only if all of these hold. |
| M9 | anthropics/claude-plugins-official (#46); addyosmani/agent-skills (#15, #86); anthropics/skills | Re-run the inconclusive TypeSafe with/without-skill A/B, and qualify skill triggering, with `claude plugin eval --ablation with-without`. | Seal new cases with comparison-preregister, including one adjacent-intent should-not-trigger case per skill. Hide the user-level typesafe-ai copy in the without-arm. Use deterministic `tool_used: Skill` graders or blind-judge on stripped packets, with `--judge-model` pinned to a model other than Haiku. Run 2 arms x 3 runs after a usage reset. Adopt only on a positive, stable delta; `--max-cost-usd` caps a list-price estimate, not plan usage. |
| M10 | hesreallyhim/awesome-claude-code | Run `/skill-doctor` once to settle the open `skillOverrides` name-only decision. | One interactive agent-lab session, with the report attached to its Claude SOTA profile record; set name-only only for never-invoked skills. Overturned if a name-only skill then fails to trigger on a task that needs it. |
| M11 | hesreallyhim/awesome-claude-code | Ctxlint as a dead-reference linter for instruction files. | Inspect Ctxlint read-only at a pinned commit, then run it offline on a frozen fixture of the prompt audit's pre-fix dead references plus the current head. Adopt only if it flags every fixture reference with fewer false positives than the naive check (16 of its 17 flags were false). |
| M12 | hesreallyhim/awesome-claude-code | Benchmark an owned skill with and without the skill before its next edit. | 3 realistic prompts x 3 runs x 2 arms, recording pass rate, tokens and time. Adopt as a pre-merge check for owned-skill edits only on a stable positive delta. |
| M13 | wshobson/agents (#19, part 3) | An invalid-key, closed-port headless probe as a local acceptance command that proves every agent and skill loads. | Run it twice, and again after the next auto-update, with `CLAUDE_CONFIG_DIR` at a scratch directory. Adopt only if `system/init` lists all seven agents and all skills every time, with no completed request. |
| M14 | jarrodwatts/claude-hud | `statusLine.refreshInterval` (5-10 s) plus an env-injected `diff.autoRefreshIndex=false` in the statusLine wrapper. | In one live interactive session with background workers, stay idle. Record whether the agents, todos or git segments go stale, and record the `.git/index` mtime and any `index.lock` errors. Adopt both changes if the segments go stale. |

## Rejected

| ID | Source | Practice or premise | Reason |
| --- | --- | --- | --- |
| R1 | shanraisshan/claude-code-best-practice | Auto permission mode instead of `bypassPermissions` | The user kept the frictionless profile on 2026-09-22 (PS-8 is keep-but-compare). |
| R2 | shanraisshan/claude-code-best-practice | Mark side-effect hooks `async: true` | No demonstrated cost; RTK, the SessionStart handoff and the effort guard need synchronous output, and async hooks cannot block. |
| R3 | shanraisshan/claude-code-best-practice | Subagent persistent memory (`memory:` field) | It enables Read, Write and Edit automatically, breaks blind-judge independence, and creates a store Codex cannot see while ai-memory is the memory of record. |
| R4 | shanraisshan/claude-code-best-practice; anthropics/claude-plugins-official (#35); Yeachan-Heo/oh-my-claudecode; addyosmani/agent-skills (#28) | Mandatory human approval gates at each phase | Contradicts the user's rules against repeated approvals; three of four executors in one recorded run stopped to ask for a go-ahead already given. |
| R5 | shanraisshan/claude-code-best-practice | `/loop` tasks expire after 3 days | Stale: recurring tasks now expire after 7 days, and resume restores unexpired ones. |
| R6 | anthropics/claude-code | Tell every subagent that all tools work and to make no test calls | Tools demonstrably fail here, and the rules depend on reporting failures. |
| R7 | anthropics/claude-code | Motivate loops with anecdotal outcomes | An anecdote with no method or sample is not evidence. |
| R8 | anthropics/claude-code; anthropics/claude-plugins-official (#43) | An inline code comment suppresses an AI reviewer's finding | Security guidance is additive only, and an unanchored gitleaks allowlist once exempted an unrelated secret on the same line. |
| R9 | anthropics/claude-code; anthropics/claude-plugins-official (#18) | Hooks load only at session start | Hook edits in settings files are picked up by the file watcher, and `/reload-plugins` reloads plugin hooks. |
| R10 | anthropics/claude-code-action | The official Claude App has no workflow write access | Its documented permission table lists Workflows read and write; if the action is adopted, use the job's `GITHUB_TOKEN` or a narrower custom App. |
| R11 | anthropics/claude-code-action | Per-command `allowed-tools` as least privilege | `allowed-tools` does not restrict which tools are available. |
| R12 | anthropics/skills; anthropics/claude-plugins-official (#21) | "Pushy" skill descriptions | Descriptions are truncated and the listing budget drops the least-used first, so longer ones push others out; no under-triggered skill is recorded. |
| R13 | anthropics/skills; anthropics/claude-plugins-official | An automated description-optimization loop | No missed trigger is recorded; native `claude plugin eval` comes first. |
| R14 | anthropics/skills | A routine re-check of sibling cache reuse | Refuted by measurement: 231 of 300 same-configuration sibling groups across 257 runs show a first-request prefix read. |
| R15 | anthropics/skills | Run everything at low effort and re-run failures higher | The user's max-quality requirement holds, and the recorded cost trigger (usage limits block work) has not fired. |
| R16 | anthropics/skills | Distribute agents and skills as a plugin-marketplace entry | The contract requires each agent file in `.claude/agents`, and plugin subagents ignore `hooks`, `mcpServers` and `permissionMode`; the drift is fixed by A11. |
| R17 | anthropics/skills | Subagent usage cannot be recovered after the task notification | `child-usage.mjs` reads persisted transcripts after the fact (checked over 257 runs). |
| R18 | anthropics/skills | Always wait for `networkidle` before inspecting the DOM | Playwright marks `networkidle` discouraged in favor of web assertions. |
| R19 | anthropics/skills | Test a generated artifact only after presenting it | Verification comes before claiming completion, and pre-integration checks have caught real defects. |
| R20 | anthropics/claude-plugins-official | An owning-service test for credentials read by third-party plugins | No such plugin is installed or proposed. |
| R21 | anthropics/claude-plugins-official | A prompt-suppressing prefix on every unattended git call | No recorded run stalled on a git prompt, and no native source covers it. |
| R22 | anthropics/claude-plugins-official | A readability-over-line-count simplification rule | No defect is traced to compressed code, and native `/simplify` covers the need. |
| R23 | anthropics/claude-plugins-official | Exactly one unchained command per Bash call | Permission rules match each subcommand, and unattended runs pass `--permission-prompts none`. |
| R24 | hesreallyhim/awesome-claude-code | Read all custom commands and key files at session start | Contradicts CT-1 and the measured first-prompt sizes (42,396 tokens for the default child against 8,048 for source-scout). |
| R25 | hesreallyhim/awesome-claude-code; wshobson/agents; Yeachan-Heo/oh-my-claudecode; karanb192/claude-code-hooks | Route extraction and execution to Haiku | DS-4's same-packet trial: Sonnet 14/14, Haiku 9/14 with a quote attributed to a file that does not contain it. |
| R26 | addyosmani/agent-skills | A cross-session WebFetch cache validated by ETag and Last-Modified | No stale-doc incident is recorded, and a cache hit returns an old summary, not the original source. |
| R27 | addyosmani/agent-skills (#49, #75) | A STRIDE trust-boundary pass before security work | Deferred: no trust-boundary defect is recorded and the first real boundary, the paper execution adapter, is not built. |
| R28 | addyosmani/agent-skills | `simplify-ignore` annotations that hide code from the model | They rewrite files on disk with placeholders until Stop, in a checkout that concurrent sessions share. |
| R29 | addyosmani/agent-skills | "Subagents cannot spawn other subagents" | They nest up to three layers by default; the project sets `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` explicitly. |
| R30 | addyosmani/agent-skills | Use the built-in Explore agent because it runs on Haiku | Since v2.1.198 Explore inherits the main model; 31 of 31 measured Explore children ran on Opus (A2 addresses this). |
| R31 | wshobson/agents | Codex hard-truncates SKILL.md bodies at 8 KB | Codex tells the agent to read SKILL.md completely; the 8,000-character budget applies to the skills list. |
| R32 | wshobson/agents | Prefer `model: inherit` over an explicit tier | A coordinator whose stages omitted a model once exhausted the Fable quota. |
| R33 | wshobson/agents | Globally unique agent names against cross-plugin overwrite | Plugin agents load under scoped names, and this project publishes no plugins. |
| R34 | wshobson/agents | Hook input via a `$TOOL_INPUT` environment variable | Command hooks receive the event JSON on stdin; no such variable is documented. |
| R35 | Yeachan-Heo/oh-my-claudecode | Remove a stale inventory header | Refuted: already removed on agent-lab's default branch. |
| R36 | Yeachan-Heo/oh-my-claudecode | A delegation-enforcer hook because agent-definition models are not applied | The documented resolution order applies the frontmatter model, and a probe observed it taking effect. |
| R37 | Yeachan-Heo/oh-my-claudecode | Auto-capture `<remember>` tags into priority notes | Durable memory is written only on explicit request, and auto-capture would let untrusted content seed later sessions. |
| R38 | karanb192/claude-code-hooks | A CI meta-check that fails when a tracked test file is not run | Refuted at the latest ref: the hermetic-suites job runs the suites by glob and documents each exclusion. |
| R39 | karanb192/claude-code-hooks | A scan for invisible Unicode in loaded instruction files | A one-off scan of 256 loaded files found none, and the session-lock variant would be gating under PS-1. |
| R40 | mksglu/context-mode | Run `git log -S`, blame or `--follow` before fixing a bug | No regression in which a fix undid an earlier fix is recorded. |

## Not covered by this sweep

The verifier's completeness pass named these gaps; nothing above covers them.

- The Codex half: openai/codex (skills-list budget, sandbox and approval defaults, AGENTS.md
  guidance) and openai/codex-plugin-cc v1.0.6 (its stop-review gate and rescue agent).
- Upstream re-checks of the other in-use components: RTK and its Claude hook, ai-memory
  2.3.2, Serena, SocratiCode 1.14.0, jCodeMunch, QMD, Beads, Headroom, TOON, ccusage,
  sandbox-runtime 0.0.77, MCP Inspector, skills-ref, zizmor 1.30.1, gitleaks 8.30.1 and
  OSV-Scanner 2.6.0. Only context-mode and claude-hud were re-checked.
- Anthropic primary sources beyond the code.claude.com pages: the engineering posts (Claude
  Code best practices, context engineering, writing tools for agents, the multi-agent research
  system, sandboxing, Agent Skills), the Agent SDK documentation and repositories,
  anthropics/claude-code-security-review and anthropics/claude-cookbooks.
- Absent community repositories: obra/superpowers, ruvnet/claude-flow,
  davila7/claude-code-templates, SuperClaude-Org/SuperClaude_Framework,
  disler/claude-code-hooks-mastery, disler/claude-code-hooks-multi-agent-observability,
  zilliztech/claude-context, musistudio/claude-code-router, smtg-ai/claude-squad and
  Piebald-AI/claude-code-system-prompts. VoltAgent/awesome-claude-code-subagents and
  punkpeye/awesome-mcp-servers are due for re-review.
- The evaluation layer: no maintained framework (promptfoo, inspect_ai) was compared with the
  custom comparison chain, and `claude plugin eval` is named in M9 but not qualified.
- Forward compatibility: the headless docs say `--bare` will become the default for `-p`. On
  an OAuth-only host with unpinned auto-update that would break every `claude -p` lane. No
  record tracks it, and the CLI changelog after 2.1.281 was not reviewed.
- Mixed refs: several gap checks read a local checkout 40 commits behind agent-lab's default
  branch, which produced two false gaps (R35, R38). Future sweeps pin every local citation to
  the default-branch head.
- Distribution from this catalog to hosts (A11): the max-effort branch is unmerged,
  `adoption/agents/claude/` ships pre-max efforts and five of seven agents, and the installer
  overwrites differing user copies.
- A host-wide secret-exposure audit beyond the dotfiles: systemd user units' `Environment=`
  settings, long-running service environments, and a stored setup token whose revocation is
  still open.
- Native settings without a dated disposition: `switchModelsOnFlag` (unset, so classifier
  fallback switches silently), `CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS`, `--safe-mode` for
  untrusted headless runs, and subagent fallback model chains.
- The trading north-star layer was out of scope, although A1 and R27 touch its paper-execution
  path.

## Alternatives considered

- **A6.** The minimal variant, correcting the docstring and test to say the SessionEnd save is
  silent, was rejected: the user would never learn that a setting changed. A Stop hook cannot
  see the model, because it runs before the turn's assistant row is written. A notice file per
  session id is unnecessary: one file with an atomic claim covers simultaneous starts.
- **A15.** Keeping the `@<sha>` form was rejected: it is undocumented and failed on 2.1.281.
  Catalog-owned sha-pinned manifests are M8. anthropics/claude-plugins-community as a source
  was rejected, because it pins context-mode at `37dc25b9` rather than the reviewed `6f0cc68`,
  pins claude-hud 14 commits behind v0.8.0, and would change the plugin keys that context-mode's
  cache-heal and the HUD statusLine match.
- **A12.** Enabling the built-in sandbox now is M1.

## Evidence that would overturn this decision

- A documented change that makes SessionEnd surface `systemMessage`. The notice file is then
  redundant.
- M8's acceptance run passes. The recipe can then call the context-mode commit enforced.
- A Claude Code sandbox setting or example is committed. The devcontainer row then credits it.
- For each M row, its named measurement. For each R row, the overturn recorded in the verified
  list, for example a measured hook cost that slows tool calls (R2) or DS-4's Haiku repeat
  trial passing (R25).

## Evidence class

- **A6** is `local_integration`. `tests/test_effort_default_guard.py` drives the shipped guard
  with synthetic SessionEnd and SessionStart events under a temporary HOME. No live Claude
  Code session has run the new guard.
- **A15** combines native CLI runs in a scratch `CLAUDE_CONFIG_DIR` (marketplace add only, no
  plugin install and no model call), `gh api` reads, and the documented check run read-only
  against this host's plugin registry and a synthetic drifted one.
- **A12 and the M and R rows** are documentation and settings inspection, as the verifier
  reported them; they were not re-measured here.
