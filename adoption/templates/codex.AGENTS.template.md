<!-- native-agent-stack:codex-user-instructions:begin (adoption/templates/codex.AGENTS.template.md) -->
<!-- native-agent-stack:top-rule -->
Top rule: research convergence first; current upstream SOTA is the source of truth. The installed client is also a source of truth; never self-write without a SOTA source. The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one.
Reuse maintained upstream tools, runtimes and orchestration patterns through their supported install and test commands, naming each source (repository and pin, file or paper); with none, stop and report.
Check capability claims in order: installed client (commands, --help, settings), upstream changelog for that version (gh api), upstream source at that tag, official docs. Absence claims need the first two, else say "not found in X, Y".
Worker, docs-agent and cross-family answers are leads; relay claims only with upstream citations.
Process large output outside the model.
Bound discovery to task-filtered names, descriptions and source locators; load only selected tool schemas. For maintained decisions, and before describing deployed architecture after compaction/resume, query scoped ai-memory with `pin_first=true, limit=2` when supported by the installed schema. Check relevance; retry without pin priority or widen if needed, then read the relevant exact path and verify current canonical sources.
When a claim proves wrong, record the correction and its verification path that turn.
Match available skill descriptions to the task (an enabled skill runs implicitly from its description or explicitly as `$skill-name`), read each selected SKILL.md before acting and follow its native workflow, loading supporting references only when needed. A coordinator, not a bounded worker, invokes `search-first` before custom code or a tool choice; when no listed skill fits the task, it discovers one with `find-skills` and verifies or A/B-tests it with `skill-creator`.
A/B and E2E use upstream harnesses: promptfoo for gateway and LLM A/B, Claude's `skill-creator` paired benchmark for skills, Harbor or Inspect for containerized agent tasks; never a self-written runner.
A coordinator ends every substantive research or adoption unit with a completeness critic (missed modality, source or candidate class) whose findings feed that layer's next landscape sweep; the skills sweep is keyed by lifecycle task.
The harness exists to build complex systems, projects and the north-star R&D; each coordinator unit names the north-star action it serves.
Codex CLI is the second native client. For unpinned work, `gpt-6.1-sol` at ultra coordinates and at max runs workers; `gpt-6-astra` at ultra coordinates a complex workflow that needs Astra, and at max takes a single consequential judgment (conflicting primary evidence, consequential architecture, complex changes across systems, or a failure unresolved after one bounded Sol repair). Where a launch pins the model and effort (`-m`, `-c model_reasoning_effort`), children inherit that pin and a spawn call names neither. Preserve explicit model choices and role definitions; a coordinator records the trigger and acceptance result. Cross-family research, review and sweep votes run through the OmniRoute gateway; a coordinator, never a delegated child, starts a cross-family lane. `codex -p omniroute` is the GPT-6 lane, and Claude-side judgment runs on Opus 5.5 at max through the cooperation lanes.
A coordinator records each decision in a dated `docs/decisions/YYYY-MM-DD-<slug>.md` naming its alternatives and the comparison that would overturn it.
No audits, trials or network at startup; the daily currency timer's one read-only due-file line is allowed.
Token lanes, one lane per artifact, verifying original source before editing or judging retrieved or compressed text: `serena` for exact symbols and references, `socraticode` or, where it is connected, `semble` for conceptual code search, `codebase-memory` for the code graph, `qmd` for scoped Markdown search, `ai-memory` for prior decisions (evidence, never authority), `context-mode` (`ctx_execute`) for large command output, `headroom` to compress a large selected text, with retrieval for recovery.

<!-- native-agent-stack:session-lanes -->
Run large command output through `context-mode` (`ctx_execute`, `ctx_batch_execute`), passing `cwd` as your working directory (a writer's owned worktree).
Where the `semble` MCP server is connected, use its `search` tool for conceptual or natural-language code questions, with the absolute repository path and no `content` argument (a per-call `content` overrides the code default); `find_related` returns only embedding-similar chunks, so callers, implementations and references come from Serena.
Run a long command with `yield_time_ms` 30000; while a `session_id` comes back, poll it with `write_stdin` (empty `chars`) until the process exits, then read the output.
Web research: where the stack installs GPT Researcher, run `bash ~/code/native-agent-stack/tools/research/gpt_researcher.sh "<short current-month query>"` as a long command (it stops after 1,500 s); ask short, unseeded current-month queries and treat the report as leads whose facts you re-read from primary sources.
To message a Claude Code session, run as one long command: set `msg` through a quoted heredoc (`msg=$(cat <<'MSG'`, then the text, `MSG` and `)` on lines of their own), then `printf '%s\n\nreply: codex queue --thread %s\n' "$msg" "$CODEX_THREAD_ID" | claude -p -n "codex-$(printf '%.8s' "$CODEX_THREAD_ID")" --permission-mode bypassPermissions --max-turns 3 --output-format stream-json --verbose "Send the text on stdin, complete and verbatim, to the session named <name> with exactly one SendMessage call, then stop."`.
Codex receives queued messages between turns, never mid-turn; expect up to about 20 s delay when it is idle.

<!-- native-agent-stack:rtk-upstream rtk-ai/rtk v0.50.0 hooks/rtk-awareness-full.md, verbatim -->
# RTK

Prefix every shell command with `rtk`: `rtk git status`, `rtk cargo test`,
`rtk npm run build`, `rtk ls src/`. Keep the prefix inside chains:
`rtk git add . && rtk git commit -m "msg"`. Commands RTK has no filter for
run as-is, so the prefix is always safe.

# Command output

Command output here is condensed to save tokens, keeping every signal and
dropping costly noise. Treat it as the complete result: run commands
normally, and batch related commands into one call to avoid extra turns.
Truncated results state their recovery path in their own output. Re-run a
command as `rtk proxy <cmd>` only when its result is unusable: empty when
output was clearly expected, contradicting its exit code, or garbled.

## About RTK

RTK (Rust Token Killer) is a CLI proxy that filters command output to save
tokens; behavior and exit code are unchanged.

- `rtk gain` / `rtk gain --history` — token savings, overall and per command.
- `rtk proxy <cmd>` — run a command unfiltered, still tracked.
- `RTK_DISABLED=1 <cmd>` — skip RTK for one command.
- `rtk discover` — find past commands RTK could have condensed.

<!-- native-agent-stack:rtk-exceptions -->
## Exceptions to the RTK prefix rule (rtk 0.50.0)

An explicit `rtk` prefix bypasses rtk's own exclusion list, so "the prefix is always safe" does not hold for these commands: rtk changes their output or exit status. Run them natively, or as `rtk proxy <command>` to keep the call tracked:
- `git show REV:path` in any form, including `git -C DIR show REV:path`: rtk keeps about 8 KiB of the blob.
- `diff`: on a missing file rtk exits 1, where diff exits 2.
- `git branch`: rtk can list a branch checked out in another worktree as remote-only.
- `git log` when the complete history matters: rtk stops at 10 commits without a notice and drops merge commits.
- `jq`: rtk keeps 40 lines of at most 120 characters.
- `find` on a path that may not exist: rtk exits 0 with no output.

Never put `rtk` in front of a shell builtin such as `cd`, `export` or `source`: rtk exits 127 and the rest of a `&&` chain does not run.
<!-- native-agent-stack:codex-user-instructions:end -->
