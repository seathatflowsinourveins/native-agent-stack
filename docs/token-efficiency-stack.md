# Native token-efficiency stack: commands and returned evidence

This is the topic-specific entry point for the selected stack on September 20,
2026. The [machine-readable list](token-efficiency-stack.json) contains the full
upstream install, use and statistics commands, versioned sources, returned results,
baseline comparisons and lifecycle limits for each tool. The
offline HTML (`ecosystem/index.html#efficiency`, generated with
`python3 scripts/build_ecosystem.py --write` -- not committed, or download it
from a `publish-catalog.yml` workflow artifact (7-day retention, `workflow_dispatch`/`v*`-tag runs only)) embeds this guide and those rows;
its Setup view contains all 66 selected components across ten layers. The broader
512-repository catalog includes alternatives and references, not 512 installations.

The installed commands are usable in their recorded native lanes. Four tools
have upstream savings estimates. The other ten core tools have no established
native session/lifetime savings counter; their useful evidence is retrieved
content, conversion correctness, or a scoped artifact comparison. An installation
does not guarantee a reduction against the cheapest adequate baseline.

## Core list

The later [foundation wave](foundation-stack.md) adds an optional OmniRoute
runtime row alongside the fourteen core and nine observation rows. Both native
clients passed seven requested MCP calls with exact source, each reporting a
4,970-token jCodeMunch estimate; its shared retained estimate is now49,700.
The foundation receipt also preserves rejected compression previews, gateway
quota failures and the independently verified Claude telemetry-readiness recipe.
Earlier figures below retain their original observation times.

Commands below name the upstream operation; full arguments and portable path
variables are in the machine list and each linked recipe. MCP operations use the
installed native client or the upstream MCPorter bridge. Measurements are dated
source-host observations. Arrows compare the exact retained representations,
not provider bills, and lossy representations require the documented quality check.

| Repository | Upstream use / statistics | Returned evidence |
|---|---|---|
| [RTK](https://github.com/rtk-ai/rtk) | `rtk git log -3`; `rtk gain --format json` | Latest retained probe: 55 commands, 1,722 estimated tokens saved; independent SQLite row: 118 input, 104 output, 14 saved. No separate session savings counter. |
| [Context Mode](https://github.com/mksglu/context-mode) | `ctx_execute_file`, `ctx_search`, `ctx_stats` | Recorded Desktop stats: rounded 1.1M estimated saved, 98.9%; the native project bridge returned the independently matched file hash. The older loaded Desktop file connection retains its scope error. |
| [Headroom](https://github.com/chopratejas/headroom) | `headroom compress`; MCP `headroom_compress`, `headroom_retrieve`; `headroom savings --json` | Default ledger: 0 calls / 0 saved. Separate clean-prefix trial: 9,616→2,128 upstream estimated tokens, 7,488 saved; exact recovery and restart passed. |
| [jCodeMunch](https://github.com/jgravelle/jcodemunch-mcp) | MCP `order` with `search_symbols`, `get_symbol_source`, `get_session_stats` | Latest default retained estimate: 39,760 saved (earlier 29,820). Clean-prefix ledger: 0→2,781→2,781 after restart→5,562 after a second exact source read. |
| [QMD](https://github.com/tobi/qmd) | `qmd --index "$QMD_INDEX" search … -c "$QMD_COLLECTION"`; scoped `get` | BM25 returned the intended runtime document at score 0.86 and the requested section. No downloaded embedding models in this profile. |
| [Serena](https://github.com/oraios/serena) | `find_symbol`, `find_referencing_symbols`, `search_for_pattern` | Native symbol retrieval passed; this Desktop query returned `172:def parse_codex(stream, env):`. Selected artifact 3,129→214 tokens. |
| [SocratiCode](https://github.com/giancarloerra/SocratiCode) | `codebase_health`, `codebase_status`, `codebase_search` | Healthy local Qdrant/embedding services; 196 chunks, active watcher, intended source match. Separate retained artifact 2,731→491 tokens. |
| [ai-memory](https://github.com/akitaonrails/ai-memory) | `ai-memory status`; scoped `memory_search`, `memory_get_session` | Native version/status and scoped search passed; current Desktop parent is active with bounded lifecycle observations. These are not complete transcripts. |
| [Repomix](https://github.com/yamadashy/repomix) | `repomix … --include … --compress` | Selected paths present; retained outline artifact 3,697→663 tokens. Read original implementation before editing or judging correctness. |
| [TOON](https://github.com/toon-format/toon) | `toon --encode`; `toon --decode --strict` | Exact JSON round trip passed. Small fixture 1,664→1,307; catalog compact JSON 59,792→66,815, so compact JSON wins for that catalog. |
| [ast-grep](https://github.com/ast-grep/ast-grep) | `ast-grep run --stdin --lang javascript --pattern …` | Eight structural matches, exit 0. Original capture 1,818→674 tokens; later output variant 1,818→686. |
| [codebase-memory](https://github.com/DeusData/codebase-memory-mcp) | `search_graph`, `trace_path` | Intended function and four static callees returned. Artifact 2,731→186 tokens; static edges do not establish runtime execution. |
| [Context Hub](https://github.com/andrewyng/context-hub) | `chub search`; `chub get` | Selected documentation returned, exit 0. Response 2,070→2,155 tokens grew by 85; useful retrieval is not necessarily smaller. |
| [MarkItDown](https://github.com/microsoft/markitdown) | `markitdown "$INPUT_HTML" -o "$OUTPUT_MD"` | Expected heading returned, exit 0; selected HTML 10,322→1,360 tokens. PDF/Office extras are absent. |

The latest final capture is in the machine list and final receipt. Earlier
numbers above retain their original scopes and times. Estimates can include
verification reads, overlap across scopes and expire under native retention.
Do not sum them or label them exact lifetime provider savings.

## Fresh native Codex and Claude acceptance

The [final receipt](../evidence/receipts/native-token-stack-final-20260920.json)
retains the native returned results, independent source checks, observation
correlations and hashes of private command captures.

Native Codex 0.155.1 and Claude 2.1.278 each read the actual project through
Context Mode, searched for the requested function through jCodeMunch, retrieved
its source and continued in the same native session. They used their existing
native sign-ins and configured models. No provider/account configuration changed.

Codex's first launch accidentally used a read-only sandbox instead of the
installed native launch policy. Two MCP calls were refused even though the CLI
exited 0. The corrected same-session launch completed all three MCP calls and
returned byte-exact source. Both process groups ended cleanly. Returned usage is
session-cumulative: **161,720 consumed tokens**, including the failed first
attempt's 64,820; the corrected turn's delta is 96,900. Cached input is already
included. Adding the first attempt again would double-count it.

Claude's functional source and continuity checks passed with three successful
initial MCP calls. Its strict initial JSON-only format check failed because the
response included extra prose; that defect remains recorded. Its first two
invocations consumed 201,200 tokens. One later minimal continuation verified the
observation join and consumed 46,011 more, for **247,211 consumed tokens** across
the three invocations. The latter operation passed its exact marker check.

These are functional/observation acceptance runs, not paired provider-savings
trials. Neither total is avoided tokens. Per-process Context Mode and jCodeMunch
savings statistics were not collected in the initial two-client task, so the
receipt records them as unavailable rather than substituting a global counter.

## Observation that can be independently matched

The earlier [Desktop observation guide](current-session-observation.md) records
four exact-parent tool correlations, live retained hook observations, six active
monitoring services and seven healthy scrape targets. It also retains the initial
Loki readiness failure and the limits on exact Desktop task-to-metric attribution.

For native Claude, telemetry was already arriving. The installed session-ID
privacy setting also removes the session label from its log events, so a raw
session-ID query correctly returned zero matches. Directly invoking the CLI had
also omitted the native launcher's process and client labels. The corrected
continuation supplied the supported resource attributes in that process only:
unique `service.instance.id`, `ecosystem.client.scope=native-claude`, and a stable
SHA-256 task label in `ecosystem.task.id`. Raw session/account suppression stayed
enabled. There was no synthetic event or persistent configuration change.

The resulting native CLI usage matched **both Loki's api_request and Prometheus's
writer-scoped series** in all four categories: input 2, cache creation 2,300,
cache read 43,698, output 11. Total 46,011. The final receipt contains the exact
queries, time bounds, returned values and independent comparison results, with
raw local identities kept private. These checks establish this accepted writer's
delivery and accounting, not universal fleet observability or causal savings.

Codex's two writer-scoped Prometheus totals also match the returned native
64,820 and 96,900 tokens, and Loki records both refused calls and all three
successful calls. Seven per-request completion events reconcile to 161,720.
Two additional startup completion events report 12,886 input and zero output
each: **25,772 additional, unattributed tokens in the raw event stream**. The
receipt preserves them separately; they are absent from the returned turn totals
and Prometheus turn histograms. Summing all nine Loki completion events gives
187,492, so whole-stream equality and final provider billing remain unestablished.

The Collector, Loki, Prometheus and Grafana form the persistent observation path.
MCPorter transports selected MCP calls; ccusage reports consumed usage; AgentsView
is a scoped archive viewer; Claude HUD is native Claude UI; otel-tui is an optional
local telemetry viewer. Viewers are not savings engines. Their separate rows say
whether they were active, tested on demand, or limited by the current UI/account
state. Native Claude HUD is not a Codex Desktop panel.

## Coverage check

Any host (a WSL2 workstation, a Mac) runs one value-free command from its checkout
to see whether the selected practice is present and wired into both native clients:

```sh
uv run --no-project --python 3.13 python scripts/adoption_status.py --profile token-efficiency --client-wiring --json
```

The manifest supports Python 3.13 only. A `python3` of another version (Ubuntu
24.04's is 3.12) still prints the report but keeps the top-level `status` at
`prerequisites_missing` with exit 2, and one older than 3.11 cannot parse the Codex
TOML. This check changed after `v2026.09.25.1`: that release's `adoption_status.py`
has no `--client-wiring` and its manifest has no `token-efficiency` profile, so run it
from a later release or a default-branch clone. The command runs none of the
selected tools. It parses the client files named below whole and in-process, emits no
value from them, and opens no credential store (`~/.claude.json`,
`~/.claude/.credentials.json`, `~/.codex/auth.json`). It prints command presence plus
`client_wiring`: booleans, three hook-event counts, `null` for a file it could not read
or parse (the Codex hook counts also for a `hooks.json` that Codex's own parse rejects,
and the trusted count for an ai-memory hook whose matcher it cannot evaluate; see
below), and the computed `complete`.

Add `--pinned-versions` to also report, per profile, whether each component's
installed version matches its platform pin (`adoption/pins-<os>-<arch>.json`). It runs
only a pin's declared `exec` version probe, never one declared `npm-metadata` (which
exists because any other argument starts that tool's server). As in
`adoption/bootstrap-linux.sh`, each probe runs in its own process group, which is
killed once the probe exits, when the check is interrupted (Ctrl-C, SIGTERM or
SIGHUP; a signal the check started with ignored, as under `nohup`, stays ignored,
as it does for the bootstrap), and when the pin's time bound expires (TERM, then KILL
2 s later); a probe that exits nonzero never counts as a match, whatever it printed.
Components without a pin entry for the platform are reported unchecked. Each profile
also gets `pinned_versions_summary`, its matched, mismatched and unchecked component
ids, and the report gets a top-level `pinned_versions_match`: `false` when any checked
component differs from its pin, `null` when none could be checked. A mismatch changes
neither `status` nor the exit code, which stay the prerequisite result. This flag is
new after `v2026.09.25.1` as well. Its probe handling changed after `v2026.09.26`:
that release's copy counts a probe's output whatever its exit status and, on timeout,
kills only the probe itself. The summary and `pinned_versions_match` changed after
`v2026.09.26.2`: that release reports a mismatch only inside each component's row. Run
the check from a fresh worktree, not only from the main checkout, to confirm that
worktree workers inherit the wiring.

The `token-efficiency` profile in [the adoption manifest](../adoption/manifest.json)
is the selected set. It holds the context-and-usage layer's current choice (RTK,
Context Mode, explicit-file Repomix, guarded Headroom and TOON, ccusage), the Serena,
QMD, MarkItDown, SocratiCode, ai-memory and MCPorter layer winners, and both native
clients. `client_wiring` checks three places:

- `claude`, the user settings: a Bash `PreToolUse` hook runs `rtk hook claude`; the
  number of hook events that run ai-memory; Context Mode is enabled and installed;
  subagent spawn depth is 1; a workflow concurrency cap is set; and neither
  `CLAUDE_CODE_EFFORT_LEVEL` nor the agent-teams opt-in appears in the settings or
  the checker's environment;
- `project`, this checkout: `.claude/settings.json` sets the depth and the cap, and
  a project `.codex/config.toml` names the Serena, SocratiCode and ai-memory servers
  (optional since 2026-09-25: those servers now live at Codex user scope, so a fresh
  worktree inherits them; see
  [the Codex MCP scope decision](decisions/2026-09-25-codex-mcp-scope.md));
- `codex`, the Codex home: the global instructions Codex loads contain `RTK.md`'s
  text inline (`rtk_instructions`; RTK 0.49.0 gives Codex instructions, not a hook);
  Context Mode is enabled and installed; `config.toml` names the same three servers;
  hooks are on (`hooks_feature_enabled`); the number of `hooks.json` events that run
  ai-memory; and how many of those events have an ai-memory hook Codex actually runs
  (`ai_memory_hook_events_trusted`). Codex reads `AGENTS.override.md` when it has
  text, else `AGENTS.md`, and passes the file to the model verbatim: it expands no
  `@RTK.md` reference
  ([`codex-rs/codex-home/src/instructions/mod.rs`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/codex-home/src/instructions/mod.rs),
  the same order at `rust-v0.155.1`). So the pointer `rtk init -g --codex` writes does
  not count, and neither does an inline copy that no longer matches `RTK.md`; the
  comparison ignores whitespace and RTK's `<!-- rtk-owned: ... -->` line. To make it
  true, replace the `@…/RTK.md` line in the file Codex reads with `RTK.md`'s own text,
  and do it again whenever an RTK update changes `RTK.md`; `codex debug prompt-input`
  then shows that text in the model's input. Codex runs a
  `hooks.json` hook only when it is enabled and trusted: the user `config.toml`'s
  `[hooks.state."<hooks.json path>:<event>:<group>:<handler>"]` `trusted_hash` equals the
  hook's current hash. The check computes that hash as `codex-rs/hooks` does at
  `rust-v0.155.1` and `rust-v0.157.1` and compares it in-process; six hashes that Codex
  0.157.1's own app-server `hooks/list` returned are known answers in
  `tests/test_adoption_status.py` (a local integration check, not an upstream test). A
  hook edited after it was trusted, or trusted under another `CODEX_HOME` spelling
  (Codex canonicalizes a set `CODEX_HOME`), counts as untrusted until `/hooks` trusts
  it again. Codex loads no hook at all from a `hooks.json` its serde parse rejects: a
  repeated field, `NaN`, a lone surrogate escape where it parses text, a number a
  field cannot hold, nesting past serde_json's recursion limit, or a hook it cannot
  hash (0.157.1's hook discovery then stops answering). The check follows that parse
  and reports both Codex counts `null` for such a file. Codex also skips a group whose
  matcher Rust's regex crate cannot compile; the check decides a matcher only when it
  uses constructs Python's `re` and that crate parse alike, and otherwise reports the
  trusted count `null` for an ai-memory hook behind it. Codex 0.157.1's own
  `hooks/list` agreed with the check on 64 `hooks.json` shapes, 126 matchers and 12 trust states
  ([retained comparison](../evidence/artifacts/adoption-status-truth-20260926/README.md)).
  Codex 0.155.1 ships its hooks feature
  stable and on by default, and the recipe's `codex features enable hooks` writes
  `[features] hooks = true`. Setting `hooks = false`, or the legacy `codex_hooks =
  false` without a `hooks` key, turns off `hooks.json` and Context Mode's bundled hooks
  together, so both counts are then zero.

The practice is applied on a host when all of these hold:

- the profile's own `status` is `prerequisites_present`: every selected command is on
  `PATH` and every recipe is present. The top-level `status`, and the exit code with
  it, also need a platform and Python the manifest supports, so on macOS, which it
  does not list, and under any interpreter other than 3.13 they stay
  `prerequisites_missing` with exit 2. Neither includes `client_wiring`;
- `client_wiring.complete` is `true`. It computes the wiring rule: every file parsed,
  every `claude`, `project` and `codex` boolean is `true` (each Codex server named in
  the user or the project `config.toml`), both hook counts are above zero, and every
  Codex event that runs ai-memory runs it trusted (`ai_memory_hook_events_trusted`
  equals `ai_memory_hook_events`). The rule changed after `v2026.09.26.2`: that
  release's check accepts a bare `@RTK.md` reference and counts hooks whatever their
  trust, so it reports `complete: true` for a Codex that sees no RTK instructions and
  runs no ai-memory hook;
- each selected tool reports its pinned version. Without `--pinned-versions` this
  command checks presence on `PATH` only; with it, `pinned_versions_match` must be
  `true` (Claude Code's pin is a floor). For the tools a bootstrap installs,
  `installed-versions.txt` from [bootstrap step 2](../adoption/bootstrap.md) runs the
  same `version_probe`; for the components it leaves unchecked (`npm-metadata` pins,
  no pin), compare each recipe's version command with the `manifests/stack.json`
  version.

The other rows of the [machine list](token-efficiency-stack.json) are not in the
profile, so this check treats them as optional: a host without them still follows
the selected practice. jCodeMunch (a per-project opt-in), ast-grep and
codebase-memory-mcp are task-selected options in the code-navigation layer's current
choice, and Context Hub is the document-retrieval current choice's option for
selected developer docs; none of the four is a layer winner or in the
context-and-usage current choice. AgentsView, Claude HUD and otel-tui are viewers, and
OmniRoute is an optional runtime. The Collector, Prometheus, Loki and Grafana rows
belong to the `observability` profile.

The check reports configuration, not activation. Apart from the Codex ai-memory hook
trust above, plugin revisions and Context Mode's bundled hooks (Codex `/hooks`, or the
app-server's `hooks/list`), project trust, Claude MCP registrations (`/mcp`), MCP
server startup and one useful call per tool remain each client's own checks. For the
instructions a Codex session actually receives, `codex debug prompt-input` renders the
model-visible input without a model call. A host records its JSON as its own evidence
through a PR ([contributing host evidence](contributing-evidence.md)); another
host's result, the reference host's included, is not its acceptance.

## Inside Ultracode subagents (2026-09-25)

On the workstation, 16 Sonnet 5 workflow subagents each used one tool on real work in this repository and checked the answer against the plain baseline. The record is in [the E2E receipt](../evidence/artifacts/token-e2e-ultracode-20260925/README.md).

**Coverage.** All 16 tools worked:
- the RTK hook;
- Context Mode, jCodeMunch, Serena, SocratiCode and ai-memory as native MCP;
- Headroom as MCP through MCPorter;
- QMD, Repomix, TOON, ast-grep, codebase-memory-mcp, Context Hub, MarkItDown, agentsview and otel-tui as CLIs.

These 16 are not the `token-efficiency` profile, whose 14 `component_ids` the
[coverage check](#coverage-check) tests. Ten of them are profile rows: RTK, Context
Mode, Serena, SocratiCode, ai-memory, Headroom, QMD, Repomix, TOON and MarkItDown. The
other six are the optional rows named there: jCodeMunch, ast-grep, codebase-memory-mcp,
Context Hub, agentsview and otel-tui. The profile's remaining four are the two native
clients, ccusage (not run here) and MCPorter (here only as Headroom's bridge).
`tests/test_adoption_status.py` checks this split against the receipt's tool list, so
a profile change has to restate it.

Three passed only on a second attempt, each after a real binding constraint:
- Context Mode reads only under the session project root;
- Serena is bound to the session project;
- Context Hub's registry lacks some documents.

**Counters over the 28-minute window:**
- RTK counted +56,527 tokens saved for this run's worktree alone, over 89 commands.
- Headroom's lifetime counter moved +183,904. An exact `o200k_base` comparison of the same compression measured 180,752 removed.
- Exact per-task reductions ranged from 12.5% (codebase-memory caller search) to 99.8% (a Context Mode summary of a 416 KB file).

**Cost.** The subagents spent 649,193 output tokens, provider-returned per child.

**Fresh sessions.** A fresh `claude -p` session loaded the Headroom, codebase-memory and QMD MCP servers registered at user scope, and called each of them.

**Not run.** Codex workers could not run: the account is at its usage limit until 2026-09-30. OmniRoute stays excluded, because it reroutes model traffic.

## Hosted CI coverage (2026-09-26)

The [hosted workflow](../.github/workflows/native-token-e2e.yml) (`native-token-tools`,
`ubuntu-24.04`) installs pinned upstream artifacts into a fresh temporary prefix and runs
[the harness](../scripts/native_token_ci.py) on relevant pushes and pull requests and on
manual dispatch. Of the sixteen tools in the subagent run above, it now exercises nine
through their own CLI or MCP surface: RTK, QMD, Repomix and TOON (since 2026-09-20), and
MarkItDown, ast-grep, codebase-memory-mcp, Headroom and jCodeMunch (added). It also
exercises ccusage, which that list does not include, against a committed synthetic usage
log. Headroom and jCodeMunch are reached through a pinned MCPorter `--stdio` bridge, which
the harness installs and version-checks but gives no fixture of its own. MarkItDown,
Headroom and jCodeMunch install with `uv tool install <name>==<version>`, run by a uv whose
archive is checked against a hash pinned in the harness. Their own PyPI dependencies resolve
at installation with no lockfile or pinned hashes, as the npm packages' dependencies do.
codebase-memory-mcp installs like RTK, from a GitHub release tarball matched against its
published checksums.

The other seven of the sixteen have no hosted fixture and were not attempted in this pass:
Context Mode, Serena, SocratiCode, ai-memory, Context Hub, agentsview and otel-tui.
Whether each could run on a hosted runner is untested.

Each fixture runs the tool's own CLI or MCP commands, upstream native operations, and
this repository's own checks assert on the returned JSON or text. So the receipt labels
itself `local_integration`: evidence of upstream native operations, not of upstream test
suites. The one upstream test is `rtk verify --require-all`, which runs the inline tests
of RTK's built-in filters from its release binary. No other pinned tool documents an
offline self-test command; the run record lists what was checked. Upstream test-suite
qualification of a component belongs in its per-host receipts under
`evidence/hosts/<host>/`, summarized in
[the component evidence matrix](component-evidence-matrix.md), and none recorded so far
for these tools runs an upstream suite. Each version is checked against
`manifests/stack.json`. Each tool's state goes to the run's temporary directory through
that tool's documented settings, listed in [the CI guide](native-token-ci.md). That is
configuration, not an operating-system sandbox; the receipt records what each tool wrote
there. No hosted run of the extended job is recorded yet, and the local runs below are
not hosted results.

Findings from wiring these in follow.
[The local run record](../evidence/artifacts/native-token-ci-extension-20260926/README.md)
lists which checks have a recorded failing control and which do not yet.

- **Installed copies, not `PATH`.** `--install` puts Headroom and jCodeMunch in
  `UV_TOOL_BIN_DIR`, which is not on `PATH`, and MCPorter looks up a bare `--stdio`
  server name on `PATH`. The first draft passed bare names. With no other copy on `PATH`,
  as on a fresh runner, both of its MCP fixtures failed with `spawn ... ENOENT`; on a
  workstation with its own copies on `PATH` it would have run those unverified copies.
  The harness now passes the absolute path of the copy it installed.
- **codebase-memory-mcp was flaky while it shared the account's state.** The first draft
  left codebase-memory-mcp's cache and daemon rendezvous at the account-wide defaults,
  where the workstation's own codebase-memory-mcp daemon also listens. In its six local
  `--install` runs, `index_repository` failed three times with the upstream message "CBM
  daemon endpoint is held by pid N but that process answered no rendezvous within
  30000 ms". The draft's `config set ui_enabled false` also rewrote the workstation's
  default UI setting, whose earlier value was not recorded. The harness now sets the
  documented `CBM_CACHE_DIR` and `CBM_RUNTIME_DIR` to directories inside the run. It
  checks that the settings and the rendezvous appear there and that the project listing
  holds only the fixture project. All eleven of the port's later local `--install` runs
  passed with those settings. In the two final-harness runs a long `TMPDIR` kept
  codebase-memory-mcp from starting, as the run record explains. The cause of the three
  failures was not isolated beyond the shared endpoint, and eleven passes do not
  establish a failure rate. Neither of these two state checks has a recorded failing
  control yet.
- **ast-grep.** The draft compared ast-grep's match count with a `grep` count over the
  live `scripts/` tree, so an unrelated script could change the outcome, and equal counts
  could not show a structural match. The check now reads a frozen fixture,
  `fixtures/ast_grep_calls.py`: ast-grep must return exactly its two `subprocess.run`
  calls, one written `subprocess.run (`, while grep's text baseline finds the other call
  plus a comment and a string literal. ast-grep exits 1, not 0, when nothing matches, as
  grep does.
- **Headroom compressed nothing at first.** The first fixture gave `headroom_compress`
  only a 49-token note, under the 250-token minimum of Headroom's `compress()`, so every
  run got it back unchanged (`router:noop`, 0 tokens saved): storage and retrieval were
  exercised, compression was not. The fixture now also compresses a compact JSON array
  of 24 records, the input Headroom's SmartCrusher handles: 826 tokens became 511
  (`router:smart_crusher:0.42`), and retrieval from a new server process returned the
  original exactly. A control that turns `compress()` into its documented
  `optimize=False` passthrough fails that check; the note stays as the in-run negative
  control.
- **jCodeMunch's source check.** The first version sliced the expected source with the
  line bounds the response itself reported, so an empty source at `line=end_line=999`,
  or the body line alone, passed. The check now compares the symbol's identity, bounds
  and complete source with a frozen oracle, which a unit test checks against Python's
  own parser.
- **jCodeMunch.** Version 1.108.319 sends its compact MUNCH text only when that is at
  least 15% smaller than the JSON (upstream `encoding/gate.py`); otherwise it sends JSON
  text, which MCPorter's `--output json` prints as the parsed object. The first draft
  expected the text form for its zero-result search and failed. Every local run got
  JSON. Measured with the upstream encoder, the MUNCH form of the observed zero-result
  response, and of a minimal one without metadata, was larger than the JSON (350 against
  227 bytes, and 145 against 31), so the text branch that the harness still accepts has
  not been observed. The observed response marked the absence as not citable because the
  worktree had uncommitted changes, which changes only the size of that metadata.

**Codex side (2026-09-26).** Native `codex exec` sessions on gpt-6-astra, at effort `max`, reached 11 of 15 tools with passing checks. RTK counted +17,782 saved for its run-only worktree. The four failures are real limits:
- jCodeMunch is project-scoped (#240), so Codex in a fresh worktree does not have it.
- QMD's catalog index does not include `adoption/`.
- Repomix `--compress` dropped a declaration.
- Context Hub lacked the facts upstream states.

The run also corrects #296's QMD row. See [the Codex receipt](../evidence/artifacts/token-e2e-codex-20260926/README.md).

## Reproduce on another PC

1. Clone the canonical repository and open the offline HTML. Choose the relevant
   [adoption profile](../adoption/README.md); follow each component's pinned
   upstream recipe using prefixes and state directories owned by that installation.
2. Keep native Claude and Codex sign-in/configuration separate from Desktop.
   Use the documented native launcher environment, including telemetry writer,
   client and hashed task labels. Do not copy another PC's authentication stores.
3. Run the component's actual upstream use command against that PC's selected
   project. Verify expected content, errors and owned-process cleanup. For
   persistence tools, run the documented restart/recovery check. Preserve the
   [six-stage lifecycle matrix](../blueprints/token-native-focus/saturation-audit.json):
   stages marked unestablished are not silently accepted by an installation.
4. Record upstream session/retained-history counters separately from exact artifact
   comparisons and native consumed usage. Compare against the cheapest adequate
   representation. Headroom compression plus full recovery grew 5,105→18,777
   tokens; a known 40-token function grew to 324 with search/source envelopes.
   Use direct reads when those satisfy the task more cheaply.
5. Match returned native results with actual writer/task-scoped monitor records,
   retaining bounded failures and private hashes. Run the
   [portable token reporter](../tools/token-report/README.md) to refresh that PC's
   manifest. Source-host results are reference evidence, not that PC's acceptance.

The published snapshot is definitive about the selected versions, commands and
recorded evidence. It does not prove a universally optimal repository set,
guaranteed savings for every task, or all lifecycle stages for every component.
