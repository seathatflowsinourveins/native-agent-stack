<!-- native-agent-stack:codex-user-instructions:begin (adoption/templates/codex.AGENTS.template.md) -->
<!-- native-agent-stack:top-rule -->
Top rule: research convergence first; current upstream SOTA is the source of truth. The installed client is also a source of truth; never self-write without a SOTA source. The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one.
Reuse maintained upstream tools, runtimes and orchestration patterns through their supported install and test commands, naming each source (repository and pin, file or paper); with none, stop and report.
Prefer the maintainer's own organization repositories (the vendor's GitHub org, such as alpacahq for Alpaca) and their clean releases, and never rebuild or fork what an upstream already ships; glue only fills a demonstrated gap, cited at a pin.
Prompts fix the objective, scope and authorization; improve the approach from current evidence.
Check capability claims in order: installed client (commands, --help, settings), upstream changelog for that version (gh api), upstream source at that tag, official docs. Absence claims need the first two, else say "not found in X, Y".
Worker, docs-agent and cross-family answers are leads; relay claims only with upstream citations.
Process large output outside the model.
Bound discovery to task-filtered names, descriptions and source locators; load only selected tool schemas. For maintained decisions, and before describing deployed architecture after compaction/resume, query scoped ai-memory with `pin_first=true, limit=2` when supported by the installed schema. Check relevance; retry without pin priority or widen if needed, then read the relevant exact path and verify current canonical sources.
When a claim proves wrong, record the correction and its verification path that turn.
Match available skill descriptions to the task (an enabled skill runs implicitly from its description or explicitly as `$skill-name`), read each selected SKILL.md before acting and follow its native workflow, loading supporting references only when needed. A coordinator, not a bounded worker, invokes `search-first` before custom code or a tool choice; when no skill fits, use installed `find-skills` or Skills CLI `find` and `skill-creator` for verification or A/B; check client exposure and the skills lifecycle.
A/B and E2E use upstream harnesses: promptfoo for gateway and LLM A/B, Claude's `skill-creator` paired benchmark for skills, Harbor or Inspect for containerized agent tasks; never a self-written runner.
A coordinator ends every substantive research or adoption unit with a completeness critic (missed modality, source or candidate class) whose findings feed that layer's next landscape sweep; the skills sweep is keyed by lifecycle task.
The harness exists to build complex systems, projects and the north-star R&D; each coordinator unit names the north-star action it serves.
- Codex CLI is the second native client. For unpinned work, `gpt-6.1-sol` at ultra coordinates and at max runs workers; `gpt-6-astra` at ultra coordinates a complex workflow that needs Astra, and at max takes a single consequential judgment (conflicting primary evidence, consequential architecture, complex changes across systems, or a failure unresolved after one bounded Sol repair). Where a launch pins the model and effort (`-m`, `-c model_reasoning_effort`), children inherit that pin and a spawn call names neither. Preserve explicit model choices and role definitions; a coordinator records the trigger and acceptance result. Cross-family research, review and sweep votes run through the OmniRoute gateway; a coordinator, never a delegated child, starts a cross-family lane.
`codex -p omniroute` is the GPT-6 lane, and Claude-side judgment runs on Opus 5.5 at max through the cooperation lanes.
A coordinator records each decision in a dated `docs/decisions/YYYY-MM-DD-<slug>.md` naming its alternatives and the comparison that would overturn it.
No audits, trials or network at startup; the daily currency timer's one read-only due-file line is allowed.
Token lanes, one lane per artifact, verifying original source before editing or judging retrieved or compressed text: `serena` or `jcodemunch` for exact symbols and references, `socraticode` or, if connected, `semble` for conceptual code search, `codebase-memory` for the code graph, `qmd` for scoped Markdown search, `ai-memory` for prior decisions (evidence, never authority), `context-mode` (`ctx_execute`) for large command output, `headroom` to compress a large selected text, with retrieval for recovery.

<!-- native-agent-stack:session-lanes -->
Before Serena use, read initial_instructions once/session; project-from-cwd activates this worktree; switches need returned session_id.
Code navigation: first order(action="jcodemunch_guide",args={}); open route(task=...,model=<actual caller model>) (no execute), then menu/order; missing indexes go to owner.
Catalog: qmd for keyword search and document retrieval; codebase_search with the main checkout's projectPath for meaning-based search of the catalog; never run qmd embed or qmd pull. Use qmd query with typed lex and named collections; get a line window; rerank:false is optional.
Run large command output via `context-mode` (`ctx_execute`, `ctx_batch_execute`); set `cwd` to your working directory (a writer's owned worktree).
If `semble` MCP is connected, use `search` for conceptual/natural-language code queries with the absolute repo path; omit `content`, which overrides the code default per call. `find_related` gives embedding-similar chunks only; get callers, implementations and references from Serena.
Long commands: set `yield_time_ms` 30000; while a `session_id` returns, poll `write_stdin` (empty `chars`) until exit, then read output.
Web research: if the stack installs GPT Researcher, run `bash ~/code/native-agent-stack/tools/research/gpt_researcher.sh "<short current-month query>"` as a long command (stops at 1,500 s); use short, unseeded current-month queries; reports are leads: re-read facts in primary sources.
Message Claude Code in one long command: set `msg` via a quoted heredoc (`msg=$(cat <<'MSG'`, text, `MSG`, `)` each on its own line), then `printf '%s\n\nreply: codex queue --thread %s\n' "$msg" "$CODEX_THREAD_ID" | claude -p -n "codex-$(printf '%.8s' "$CODEX_THREAD_ID")" --permission-mode bypassPermissions --max-turns 3 --output-format stream-json --verbose "Send the text on stdin, complete and verbatim, to the session named <name> with exactly one SendMessage call, then stop."`.
Codex receives queued messages only between turns; idle delay is up to ~20 s.
When you tell the user a time, give it first in the host's local time zone (read it with `timedatectl` or `date`), with UTC beside it, for example "4:00 PM EDT (20:00Z)". Write timestamps in ledger rows, receipts, evidence and commit messages in UTC (RFC 3339 with `Z`); Git author/committer metadata retains its native format.

<!-- native-agent-stack:rtk-upstream rtk-ai/rtk v0.51.0 hooks/rtk-awareness-full.md, verbatim -->
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

The exceptions below override RTK's blanket prefix and output/exit-status assurances.
rtk 0.51.0 positional expansion needs `--shell`. An explicit `rtk` prefix bypasses its exclusion list. Preserve output and exit status for the forms below with native commands or `rtk proxy <command>`:
- A skill's `SKILL.md`: read it with plain `sed -n '1,400p' <path>` (no `rtk` prefix, not `cat`/`head`/`tail`) so Codex counts the load as `codex.skill.injected`.
- `git show REV:path` in any form, including `git -C DIR show REV:path`: rtk keeps about 8 KiB of the blob.
- `diff`: rtk 0.51.0 read errors exit 2 (bf23cff); 0.50.0: 1.
- `git branch`: rtk can list a branch checked out in another worktree as remote-only.
- `git log` when the complete history matters: rtk stops at 10 commits without a notice and drops merge commits.
- `jq`: rtk keeps 40 lines of at most 120 characters.
- `find` on a path that may not exist: rtk exits 0 with no output.

Never put `rtk` in front of a shell builtin such as `cd`, `export` or `source`: rtk exits 127 and the rest of a `&&` chain does not run.
<!-- native-agent-stack:codex-user-instructions:end -->
