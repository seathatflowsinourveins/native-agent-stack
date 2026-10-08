# Coordinator research routing — 2026-10-08

CC correction #76 routes coordinator research through the existing research
runtime. The CC's 14:01 refinement keeps targeted primary-source verification
inline: a marked coordinator's WebSearch is denied; WebFetch and context-mode's
fetch-and-index keep their normal client permission checks and record their
requested URLs and claim labels. Three or more fetched URLs in a turn produces
a dispatch warning. CC135949Z authorizes the PR; CC142518Z supplies the routine
landing path through 5f. Host F9 application and fresh-session acceptance remain
with the command center after landing.

## Primary sources and demonstrated gap

- Claude Code **2.1.294**, confirmed by installed `claude --version`, and its
  [official hooks reference](https://code.claude.com/docs/en/hooks), read
  2026-10-08: matcher evaluation, common input fields, PreToolUse decision control
  and UserPromptSubmit decision control. The current live documentation is a
  dated source review, rather than an immutable versioned client test.
- [bytedance/deer-flow](https://github.com/bytedance/deer-flow/tree/345f08be00c8a9495079b732a39b46aa9af1584e)
  at `345f08be00c8a9495079b732a39b46aa9af1584e` (v2.1.0), its embedded
  `DeerFlowClient.chat()` interface and the installed `deer-flow-research.sh`
  producer. The existing producer owns model routing, retrieval, timeout,
  native metadata and retained failure artifacts. The dispatcher calls it
  once; it does not create another research runner or modify its environment.
- [aannoo/hcom](https://github.com/aannoo/hcom/tree/b2a7c192003e7fd67ed93265289e4ac36276f965)
  at `b2a7c192003e7fd67ed93265289e4ac36276f965` (0.7.28), the installed native
  `list self --json` identity contract. The dispatch adapter binds the existing
  calling coordinator through that read-only interface.
- Repository integration base `58d235e83c308d97947e623bb7d8503ef6eec369`:
  `adoption/templates/claude.settings.template.json`,
  `tools/adoption/install_claude_profile.py`,
  `tools/adoption/new_wsl_client_config.py` and the current research launcher.
  The template already ships RTK, secret-path and memory hooks; it has no
  coordinator research gate. The research producer prints mixed console output
  and a run directory, rather than a one-command cited-result-path interface.

The chosen approach composes the existing native hooks, HCOM identity and
DeerFlow producer. A global tool deny would also restrict lane/R&D sessions;
an instruction-only reminder does not refuse a WebSearch call. A new research
framework or host-global launcher edit would duplicate existing ownership.
Replace this small adapter if the maintained producers ship the same native
coordinator scope and cited-result contract, or native acceptance shows this
integration fails its declared scope.

## Exact session marker owned by the coordinator launchers

Only CC and co-op launcher owners set both values for their **native Claude
session**:

```sh
NAS_RESEARCH_COORDINATOR_ROLE=command-center
NAS_RESEARCH_COORDINATOR_SESSION_ID=<native-Claude-session-uuid>
```

The co-op role is `co-op`. The launcher supplies that UUID with Claude's native
`--session-id` option, exports the two marker values for that launch, and keeps
the same UUID on resume. This is a launcher contract, not a global Claude
`env` setting. The repo's generic ecosystem launcher and ordinary lane/R&D
launches set neither marker. Private CC/co-op launcher files are outside this
PR's owned paths and are applied by their owners.

The hook acts only when the role is one of those two strings and the payload's
`session_id` equals the marked UUID. An inherited marker alone does not scope
a separately launched child session. A nonempty native `agent_id` is exempt
when supplied, but the reviewed PreToolUse common schema does not guarantee
that field. An in-process research subagent sharing the marked session is
therefore an explicit untested boundary; run research through the separate
runtime when this exemption cannot be observed. This marker is a routing
scope, not an authentication or tamper-proof security boundary.

## Hook output and retained state

The installed hook receives the upstream stdin JSON. For a marked WebSearch,
it returns `hookSpecificOutput.hookEventName = "PreToolUse"`,
`permissionDecision = "deny"` and a `permissionDecisionReason` containing
`tools/research/dispatch --question '<research question>'`. Denial needs no
state read or write. Other tools keep their normal permission flow; the hook
never returns a broad `allow` decision or rewrites their inputs.

WebFetch and the exact standalone/plugin context-mode fetch tool names in the
template record one requested-URL line per fetch, including each URL in a batch.
The claim is the supplied WebFetch prompt or context source/intent label. A
missing label is `unprovided`, not an invented verified claim. URL userinfo,
credential query fields, fragments, headers and complete tool inputs are omitted.
These are **attempt records**: PreToolUse occurs before permissions and fetching,
so a log line does not prove a successful fetch or verified claim.

Private state lives at
`${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/research-routing/`
under the SHA256 of the native session ID. A locked `turn.json` counter resets
at each native UserPromptSubmit. `verification.jsonl` retains the newest 256
records for that session; no transcript is read. At three or more requested
URLs, PreToolUse returns the native `additionalContext` dispatch warning.
An unavailable log/reset emits an explicit warning and leaves normal fetch
permissions intact. A malformed marked input is reported through the native
nonblocking hook error contract. Unmarked sessions are silent and create no
state. The local command uses Python's standard library and the host's file
locking; Windows-native portability is untested, while the selected WSL/Linux
and macOS hosts provide that interface.

## Dispatch and host acceptance

From the repository, the coordinator calls:

```sh
tools/research/dispatch --question '<public research question>'
```

The command uses the existing native HCOM identity and installed embedded
DeerFlow launcher. A successful response is the original cited `answer.md`
path, with a scoped receipt retaining the producer's answer/metadata hashes,
native verdict and citations. Failure preserves the producer artifacts and
does not return a passing cited-result path. The question is passed as one
argument rather than evaluated as shell code. Consult the command's `--help`
for the optional explicit HCOM identity. The producer is the existing
`new-wsl-native-stack/deer-flow-research.sh` under the caller's XDG config root;
this adapter does not introduce another producer selector or model route.

After 5f lands the reviewed head, the CC performs its existing F9 render/apply
from that head, including the checksum-verified hook file. The CC/co-op launcher
owners then apply the exact-session markers. In a **fresh marked native session**:

1. Request one WebSearch call and retain the actual hook denial and redirect.
2. Run one dispatch on a public question and inspect the original cited result,
   native metadata, result path and receipt. A source-partial report remains
   source-partial even when the producer's execution verdict passes.
3. Observe an unmarked lane or separate R&D session to confirm its tool call is
   outside this gate. Check targeted fetch logging and reset in the marked
   session. Record the real client/version, session IDs, outputs and limits.

The PR's local subprocess tests use **synthetic producer/HCOM/hook fixtures**.
They exercise native command and stdin/stdout contracts, scope, failure retention,
counter reset, batches and concurrency. They are not unchanged upstream tests,
fresh Claude model runs or live research acceptance. No host F9 apply, launcher
edit, model-provider call, credential use or fresh-session acceptance is claimed
by this PR.

## Changed existing test contracts

Three existing F9 test methods explicitly list the shipped hooks or invocations.
Their updated contracts add the checksum-bound `research-routing-guard.py`:

- `tests.test_new_wsl_client_config.RenderTests.test_every_wired_hook_runs_a_file_the_repository_copies_with_its_checksum`:
  the rendered default references four copied/checksum-verified hook files,
  including the research-routing guard; carrier hooks remain held out.
- `tests.test_new_wsl_client_config.ApplyTests.test_the_first_run_writes_what_the_wired_pieces_name_and_nothing_else`:
  the isolated F9 install writes those four files, and the rendered event set
  includes UserPromptSubmit for the per-turn reset. Other copied files and the
  idempotent application checks retain their existing contracts.
- `tests.test_new_wsl_client_config.RenderTests.test_settings_keep_the_practice_pieces_and_drop_the_old_profile_pieces`:
  the copied-hook command count grows from four to six because the new single
  hook runs at PreToolUse and UserPromptSubmit; the rendered file count grows
  by one, and all remaining practice/profile permission assertions are kept.

The added
`RenderTests.test_coordinator_research_hooks_render_native_matchers_without_globally_marking_sessions`
checks the actual rendered tool matcher and reset command, including the
template's escaped end anchor, and proves that global `env` does not mark lanes.
The original `RecordTests.test_the_counts_that_the_record_states_are_the_ones_check_prints`
keeps its latest-dated-projection contract unchanged; its new dated F9 counts
are appended to the existing decision record without rewriting old observations.

The exact class names were checked in source. This declaration does not turn
fixture evidence into upstream acceptance.

## Recovery and next observation

Before host application, the inverse is reverting this PR's repository changes;
the existing host is untouched. After application, CC/co-op launchers can remove
the two marker exports to make the shipped hook inert, then apply the previous
reviewed F9 settings to remove the hook entries. Retain the bounded verification
records and research producer receipts. Removing a hook file without its settings
entry would leave a native command error, so the source-owner F9 settings rollback
precedes any file cleanup.

The completeness critic must check the plugin fetch name, URL-batch counting,
turn resets, native-session inheritance, F9 file/checksum/map coverage, original
result-path/citation retention and the unavailable in-process subagent field.
The next primary acceptance is the CC's post-landing fresh-session run, not
another synthetic replay or a duplicate of the observability lane's live research.
