# PR-A U2: Claude-side kernel measures, host evidence and differential

Local transcript analysis on one workstation, 2026-09-29. These are count-only scans of the host's Claude Code
transcript store (5,131 to 5,168 `.jsonl` files as it grew during the day), a property check of the part
splitter on synthetic commands, and a differential of the U2 kernel against its base. None of it is a provider
run. No output here holds an id, a path, a host name or transcript text. Each scan prints key names, enum values
(model names, client versions, `speed`, `service_tier`, `inference_geo`, iteration, hook, tool and status names)
and counts only.

## Files

| File | What it is |
| --- | --- |
| `sources.json` | Every upstream document a U2 rule cites, with URL, fetch time, sha256 and the exact sentence it rests on |
| `expected-changes.json` | The allow-list of the differential: per U2 stage, the key paths U2 adds and the pre-existing paths it changes, with equality required everywhere else |
| `differential.mjs` | Runs the base kernel and the U2 kernel as their own CLIs with identical arguments and classifies every differing leaf path against `expected-changes.json` |
| `combine-chunks.mjs` | Sums `differential.mjs` outputs over adjacent windows that partition one window |
| `differential-sweep-waa.json` | The sweep differential over W_AA without `--rtk-check` |
| `differential-sweep-waa-rtk.json` | The sweep differential over W_AA with `--rtk-check`, run as twelve adjacent windows at once and combined |
| `differential-runs.json` | The run-mode differential over 232 finished workflow runs |
| `waa-invariants.py` and `.json` | The U2 design's real-window invariants over the U2 kernel's sweep of W_AA: call-state invariant violations, hook blocks against claims by event, and M15 per server |
| `scans/parts-compare.mjs` and `.json` | The base and U2 part splitters over every Bash call in W_AA, with `bash -n` deciding each call on which they disagree |
| `shell-parts-property.mjs` and `.json` | Binding decision B8's part splitter on generated commands whose parts are known by construction (checked with `bash -n`), on random strings, and at growing sizes |
| `scans/usage-iterations-{1..4}.py` and `.json` | Shapes of `message.usage` on assistant rows: `iterations[]` types and keys, the executor-sum invariant, the 5m/1h split, streamed rows and advisor calls |
| `scans/hook-rows.py` and `.json` | Hook attachment rows: events, name shapes, content shapes, stdout claims and pairing |
| `scans/large-results.py` and `.json` | Results over 5,120 B per tool: content shapes, JSON as returned, after the ctx code echo, after the Read `cat -n` numbers |
| `scans/kernel-usage.mjs` and `.json` | The U2 kernel's `transcriptUsage` over every transcript: how often each B9 reason makes usage incomplete |
| `scans/kernel-split-differs.mjs` and `.json` | Which message has a 5m/1h split unequal to its combined counter under the kernel |
| `scans/call-states.py` and `.json` | Tool results by template class (the client's not-executed texts and its MCP texts), with `is_error`, `toolDenialKind`, the `toolUseResult` form and the tool kind |
| `scans/not-executed-delta.mjs` and `.json` | U1's not-executed rule (copied verbatim from ebcca292) against the extended `callState`, call by call, and the cause of every call that did not run |
| `scans/kernel-m14-m15.mjs` and `.json` | The U2 kernel's `call_states` and `m15` over every transcript: invariant checks and the per-server M15 classes and rates |
| `scans/final-returns.py` and `.json` | Item 6: background-task result keys by tool, `run_in_background` inputs, notification locations and the kind of each transcript's final assistant row |
| `scans/task-notifications.py` and `.json` | Item 6: which tool started each task a `<task-notification>` names, the notifications' tags and `<status>` values, and each task's state at the final assistant row |
| `scans/task-stop.py`, `task-stop-2.py` and `.json` | Item 6: whether a TaskStop result names a task of its own transcript, and whether a terminal notification follows it |

Reproduce with the Claude Code projects directory as `<root>`. The `.mjs` checks also take the kernel path.
The store keeps growing, so expect later counts to be larger.

```
python3 scans/usage-iterations-1.py <root> > scans/usage-iterations-1.json
node scans/kernel-usage.mjs examples/claude-native/workflows/child-usage.mjs <root> > scans/kernel-usage.json
node shell-parts-property.mjs examples/claude-native/workflows/child-usage.mjs 2000 20260929 > shell-parts-property.json
node differential.mjs --base <base child-usage.mjs> --new examples/claude-native/workflows/child-usage.mjs \
  --expected expected-changes.json [--rtk-check] --root <root> --since 2026-09-26T00:00:00Z --until 2026-09-26T18:37:00Z
node differential.mjs --base <base child-usage.mjs> --new examples/claude-native/workflows/child-usage.mjs \
  --expected expected-changes.json --run <workflow transcript dir> [--run <dir> ...]
```

The base kernel is `git show fe9f511b:examples/claude-native/workflows/child-usage.mjs`, placed beside a copy of
`shell-parser.pin.json` (unchanged by U2), so both kernels read the same verified tree-sitter-bash install.

## What the scans establish (these back the rules in child-usage.mjs)

- **Usage iterations (B9).** 291,833 of 436,898 assistant rows carry an `iterations` list. The entry types are
  `message` (291,337), `advisor_message` (3,314) and `fallback_message` (3). On every row with advisor entries
  (3,303 of 3,303) the top-level counters equal the sum of the `message` entries, and never that sum plus the
  advisor entries. The exceptions to the executor-sum rule are:
  - 4,211 rows with an empty list (clients 2.1.283 and 2.1.284);
  - one message whose top-level counters are 0 while its `message` entry is not;
  - one fallback-served message, whose top level equals its `fallback_message` entry.
  (`usage-iterations-2.json`, `usage-iterations-3.json`)
- **The 5m/1h split.** On every row with more than one iteration, the top-level `cache_creation` object equals
  the first iteration's split (3,706 of 3,706; `usage-iterations-4.json`). It therefore equals the sum of the
  `message` entries' splits only when the later entries write no cache. Inside each entry the split always
  equals its own combined counter (294,672 of 294,672; `usage-iterations-2.json`). Under the kernel, a
  message's split equals its combined counter for 201,150 of 201,151 known messages; the exception is the
  inconsistent message above. (`kernel-usage.json`, `kernel-split-differs.json`)
- **Advisor calls.** A successful advisor result has its `advisor_message` entry wherever the counted row
  carries iterations (2,052 of 2,052 message ids). Error results have none. 105 message ids with a
  successful result carry no iterations at all (clients 2.1.283: 79, 2.1.284: 26), and 47 have a call
  without a result. Under the kernel, 143 of 4,667 transcripts with messages read `usage.complete: false`
  for these reasons. (`usage-iterations-3.json`, `kernel-usage.json`)
- **Tier fields.** `speed` is `standard`, absent or null; `service_tier` is `standard` or null; and
  `inference_geo` is `not_available` or null (317 rows carry null in all three). No `fast`, priority or
  regional value occurs here, so those cases are covered by synthetic fixtures only.
  (`usage-iterations-1.json`)
- **Hook rows (item 1).**
  - Insertions: PreToolUse 7,367, SessionStart 919 (69 with two entries) and SubagentStart 1,670. Every
    PreToolUse insertion pairs with the `hook_success` row of the same toolUseID and hookName.
  - Every `hook_success` row carries `hookEvent`.
  - JSON claims equal inserted blocks for SessionStart (988) and PreToolUse (7,367). For SubagentStart
    there are 1,732 claims against 1,670 blocks. That gap fits the hooks reference, which says a re-run
    of the hook injects context only when the subagent does not already hold it; the scan does not prove
    that this is the cause.
  - There are no plain-stdout claims, no hook name over 80 characters, and one other hook row type
    (`hook_system_message`, 5).
  (`hook-rows.json`)
- **Large results (item 4).** The rebuilt context-mode code echo is a prefix of every `ctx_execute`
  (7,686) and `ctx_execute_file` (49) result over 5,120 B. As returned, 0 of them read as JSON; without
  the echo, 29 do. Every text Read result over 5,120 B (11,467; another 133 hold a non-text block) is
  numbered on every line. As returned, 0 read as JSON; without the numbers, 990 do. (`large-results.json`)
- **Calls that did not run (item 7).** Every such row carries a `toolDenialKind` or a `<tool_use_error>` or
  user-rejection content (`call-states.json`, 5,168 files). The config text "Permission to use ... has been
  denied." (8 rows) and the cancelled text "Not run: the response that made this tool call ..." (1 row) are read
  by U1's rule only through their denial kind. Hook denials carry `permission-rule` (817 of 817), and so does
  "Permission for this command was denied by a built-in ..." (11 rows). The interrupt marker
  "[Request interrupted by user for tool use]" is a user text block after a user-rejection result (37 of 37),
  never a result.
  Over 228,531 calls, U1's rule and the extended `callState` mark the same 1,228 calls as not run and differ on 0
  (`not-executed-delta.json`, which also gives the causes).
- **M14 and M15 over the store (`kernel-m14-m15.json`).** Across 4,349 actors with calls there are 0 invariant
  violations (per actor and per server). `calls_without_result` equals `cancelled_or_unfinished` for every one of
  them, since a Claude transcript has no native statuses. The context-mode server's 34,427 calls classify
  completely: 0 `unmatched` and 0 `echo_mismatch`, a rate of 0.0028 and a ceiling of 0.0044.
  The client's MCP texts occur as counted in `call-states.json`: 16 "is not connected", 4 idle timeouts,
  1 "Connection closed" and 1 −32602 validation error. Server names outside the stack's vocabulary are
  folded into `(other)`.
- **Background tasks (item 6).** Over 4,861 transcripts (3,823 subagent, 1,038 main), tasks start from four
  sources, not one: Bash `backgroundTaskId` (1,054, including commands moved to the background at their
  timeout), Monitor `taskId` (198), Workflow `taskId` (350) and an async Agent's `agentId` with `isAsync`
  true (307). The design read `backgroundTaskId` only. `<task-notification>` blocks arrive in `queued_command`
  prompts (2,155), in a user row's string content (1,178) and in user text blocks (7). Their `<status>` is
  `completed` (2,499), `failed` (83), `killed` (14) or `stopped` (18), or absent (726): 444 of the 547
  notifications of Monitor tasks are events with no status, so "any notification" (the design's rule) would
  end a monitor at its first event. (`final-returns.json`, `task-notifications.json`)
- **TaskStop (item 6).** 97 TaskStop results carry `toolUseResult.task_id`; 96 name a task their own transcript
  started, and none is an error. After a TaskStop of a Bash, Monitor or Workflow task no terminal notification
  follows (34 + 15 + 39 = 88 of 88); after one of an Agent a `killed` notification does (8 of 8). 35 more
  TaskStop results have no `toolUseResult` and name no task of their transcript, and 8 are errors. So a
  TaskStop that is not an error and names a task ends it. (`task-stop.json`, `task-stop-2.json`)
- **Final rows (item 6).** The final assistant row of a subagent transcript is a `tool_use` (2,955: a
  workflow child's return is its StructuredOutput call), a `text` (837) or neither (28: thinking 9,
  server_tool_use 15, advisor_tool_result 4); of a main transcript, `text` (954) or `tool_use` (31). Every
  final message's rows hold one block each (4,805 of 4,805), so its text is the text blocks of its rows.
  (`final-returns.json`)

## B8 part splitter (`shell-parts-property.json`, `scans/parts-compare.json`)

- Over the 30,673 Bash calls in W_AA, the U2 splitter reads 4,459 calls the base splitter refused, and GNU bash
  5.2.21 accepts all 4,459 (`bash -n`). They hold a here-document operator (4,262), a comment (755), a
  substitution inside double quotes (583), backquotes inside double quotes (406) or an arithmetic expansion (204),
  among others. The base splitter read 1 call the U2 splitter refuses; bash rejects it (three backquotes inside
  double quotes open a substitution that never closes). 17 calls that both read split differently, all of them
  around a `"$( )"` (the base ended the quote at a `"` inside the substitution). 63 calls neither reads; bash
  accepts 62 of them, and every one of those 62 holds a `case` statement, whose pattern `)` the frame machine
  reads as a closing parenthesis. They are 0.2% of the calls, under B8's 5% bound.
- 2,000 generated commands, from 30 construct classes (1,218 with a top-level here-document, 111 with a newline
  inside a substitution before a pending body, 131 with a here-document a substitution leaves open), are all
  accepted by GNU bash 5.2.21 (`bash -n`), and `shellParts` returns exactly their parts for all 2,000.
- 2,000 random strings over the shell metacharacters: 1,889 read as unparsable, 111 as parts, 0 throws, at most
  0.34 ms each.
- Scaling: 2,000, 4,000, 8,000 and 16,000 parts (46,676 to 373,317 characters) take 7.1, 11.1, 20.4 and 43.1 ms.
- The two newline rules for here-document bodies were checked with GNU bash 5.2.21 and dash on 2026-09-29. A body
  begins at a newline of its operator's frame depth or shallower. When a substitution leaves a here-document open
  beside another pending body on the same line, the shells disagree (bash reads the substitution's body first,
  dash gives it none); the kernel reads in operator order, and the generator leaves that case out.

## Differential

`expected-changes.json` lists, stage by stage, the key paths U2 adds and the pre-existing paths it changes on
purpose; `differential.mjs` requires equality on every other leaf path. The sweep ran on a frozen copy of the
1,451 transcript and meta files that can hold a row in W_AA = [2026-09-26T00:00Z, 2026-09-26T18:37Z) (binding
decision B7's baseline window), so a store that grows between the two runs cannot make a difference; the copy
was deleted afterwards. Run mode used the 232 workflow runs whose journals were last written between
2026-09-26T00:00Z and 2026-09-29T12:00Z.

| Run | Base leaf paths | Equal | Changed, allowed | New, allowed | Unexpected | Exit |
| --- | --- | --- | --- | --- | --- | --- |
| Sweep over W_AA, no `--rtk-check` | 381,557 | 381,552 | 5 | 253,611 | 0 | 0 |
| Sweep over W_AA, `--rtk-check`, twelve adjacent windows | 440,414 | 436,513 | 3,901 | 286,344 | 0 | 0 (all 12) |
| Run mode, 232 runs | 1,175,479 | 1,175,219 | 260 | 768,224 | 0 | 0 |

W_AA holds 707 children and 37 main sessions. What changed, by allow-list entry (the JSON files give the
per-entry counts):

- **B9 (`usage.complete`).** 4 actors in the sweep and 92 children in run mode now read incomplete usage.
- **Item 6.** Of the 707 children, 673 have a measured final return (553 end with a `tool_use`, 118 with text, 2
  with neither), 34 ran past the window end (`unobserved`), 1 ended with a wait notice and 1 with a background
  task still running. Of the 37 main sessions, 29 are measured, 6 unobserved and 2 not applicable. In run mode,
  2 of the 232 runs' children became incomplete (282 were incomplete at the base, 284 now): one handed on only a
  wait notice for a monitor (the AA:21 case) and one returned with a background task that had no completion
  notification. Those 2 runs are now incomplete and exit 1 (162 runs were complete at the base, 160 now), and the
  160 that stay complete have the new `reason` text.
- **B8 and B5 (`rtk_parts`, `--rtk-check`, sums over the twelve windows).** `calls` is unchanged (28,064 child
  and 2,609 main Bash calls). Unknown calls fall from 3,970 to 196 for children (share 0.1415 to 0.0070) and from
  669 to 32 for main sessions (0.2564 to 0.0123): 4,412 calls moved from unknown to classified and 1 the other way
  (the call bash rejects, above). Under B8's rule M-R1 becomes evaluable (`measured` in every window; at the base
  11 of the 12 windows read `incomplete`, for children and for main sessions alike). The newly classified calls add eligible parts that rtk never covered,
  since rtk v0.50.0 rewrites no heredoc or `$((` command: child eligible parts rise from 24,914 to 26,571 and
  observed covered parts from 18,051 to 18,061, so child coverage falls from 0.7245 to 0.6797 (main: 0.5299 to
  0.4326). `explicit_rtk_on_excluded_or_sensitive` rises from 21 to 22 and `proxy_parts` from 837 to 878. Of the
  15,010 child calls with an eligible part, 14,560 succeeded, 357 failed, 57 were rejected, 21 invalid and 15 have
  no result; 9,670 succeeded with an eligible part observed covered (`observed_covered_succeeded_calls`, the M1
  numerator). Those sums count each call in the window of its first row; a Bash call whose hook row falls in the
  next window has its rewrite unread there, so they can differ slightly from one sweep over the whole window.
- **The limits string** changed once (the docs stage).

`hook_context.by_hook['(other)']` and the cli_lanes `not_executed` counters did not change on this window, as
expected (no hook name over 80 characters; every not-executed row carries a denial kind).

## Real-window checks (U2 design 10, steps 4 and 5)

Over the U2 kernel's sweep of W_AA (744 actors, `waa-invariants.json`):

- The call-state invariants (`attempted` is the sum of its states, `executed` of its three, `rejected` of its
  sources) hold for every actor and every per-server row: 0 violations over 744 actors and 113 server rows, and no
  unmeasured `final_return` carries a counter.
- Hook blocks equal claims for every event: children PreToolUse 604 and 604, SessionStart 2 and 2, SubagentStart 5
  and 5; main sessions PreToolUse 55 and 55, SessionStart 46 and 46. No plain-stdout claim and no other hook row.
- M15: every server classifies every error (`every_error_classified`), and no server is `threshold_sensitive`. The
  context-mode server has 6 infrastructure errors in 1,312 child calls (rate 0.0046) and 2 in 57 main-session
  calls (0.0351, above the 0.01 threshold); codebase-memory has 1 in 3 child calls. These are baseline
  descriptions, not a gate result.
- The private ledger: a sweep with `--call-ledger` wrote 41,602 records into a new file of mode 600; its stdout was
  byte-identical to the sweep without the flag and held none of the ledger's 42,337 distinct call, session and
  agent ids, as a value or as a substring, nor the root directory. A ledger path inside this repository exited 2
  and wrote nothing.
