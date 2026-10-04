# PR-A U3: Codex-side measures, host differential and census (2026-09-29)

This directory holds the before/after evidence for PR-A unit U3, the Codex-side measures of
`tools/skill-usage/skill_usage.py --lanes` and the shared `child-usage.mjs` kernel. The units are
items 10a, 10b, 10d, 10e and 10g, and the Codex normalization, built on branch
`claude/pra-u3-codex-measures-2d-20260929`. Evidence class: a `local_integration` measurement of this host's
native Codex rollouts plus synthetic transcripts. It is not a model run, not provider acceptance and not
an unchanged upstream test.

Every figure below is a count, a state or a model/effort key, printed by the scripts here unless the text
names another source. No thread id,
call id, path, host name or command text is in this directory. The full reports and summaries stayed
private (mode 0600, outside every checkout).

## Scripts

- `run-differential.py` runs one revision at a time. It extracts `tools/skill-usage`,
  `examples/claude-native/workflows` and `adoption/skills` with `git archive` into a private directory and runs
  `skill_usage.py --lanes --codex-root <store> --since S --until U --now U --json --out <private>`,
  with `--rtk-check` on request. It reduces each report to aggregate counts: every group field flattened, plus
  per-actor histograms of routes, completeness, M4 status and spawn states. `--compare` prints the fields
  that differ between two summaries. `--totals` sums the quoted fields over the three disjoint groups
  (`workers`, `negative_controls`, `unclassified`).
- `census.py` recounts, from the rollouts and with the checkout's own scanners, the code-mode forms behind
  commits 7 and 8. It covers each emitted item under the old span rule and the new turn rule, `wait` calls,
  `web_search_call` records, outer exec sites and HTTP mentions, and extra exec outputs.
- `claude-byte-identity.py` runs the kernel's `--lanes-sweep --rtk-check` at two revisions over a synthetic
  Claude root that it writes. The root holds the rtk control commands of `tests/test_token_measurement.py`
  in an Agent-tool child, a workflow child and a main transcript, with one hook rewrite. Each revision runs
  twice: with a temporary HOME and the root as the working directory, and with the caller's HOME and the
  checkout as the working directory.

## Inputs

- The store is this host's Codex sessions store (path withheld). It held 1,620 rollout files at every run:
  277 from codex-cli 0.155.1 and 1,343 from 0.157.1, all `history_mode: paginated`.
- The window is `--since 2026-01-01T00:00:00Z --until 2026-09-29T00:00:00Z`, with `--now` equal to
  `--until`. 1,436 sessions fall in it at every run, with 0 parse errors. Records after `--until` are never
  read, so the live store's growth cannot move a figure; `sessions_ran_past_window_end` is left out of the
  comparison.
- The runs, by label, revision and design commit:

| Label | Revision | Design commit | `--rtk-check` | Seconds |
|---|---|---|---|---|
| R0 | ae0f5bad | 3 (10b) | no | 922.9 |
| R1 | 368a9b8e | 4 (route values) | no | 774.4 |
| R2 | 709aaf27 | 5 (10g spawn join) | no | 994.4 |
| R3 | 1bbf81e9 | 6 (normalization A) | no | 842.8 |
| R4 | 9799d5fa | 7 (10e nested attribution) | no | 808.6 |
| R5 | e79a5c18 | 8 (10e legacy spans, outer JS) | no | 697.8 |
| R5r | e79a5c18 | 8 | yes | 1245.7 |
| R6p | 14e3c376 | 9 (10d replay agent, D7) | yes | 956.7 |
| R6r | 14e3c376 | 9, repeated | yes | 952.4 |

R0 to R3 ran in the stage before this one. R3 is the parent of R4, because cd04dc34 and ba42e70f, the
commits between them, change tests only.

## Results per design commit

Counts of differing fields (`--compare`), then the quoted totals (`--totals`):

- **Commit 4, R0 to R1: 18 fields.**
  - 111 attempts move from `gpt-6-astra|None` to `gpt-6-astra|ultra`: the effort is kept whatever its name.
  - The 116 `(other)` routes become `cx/gpt-6-astra|max` (91), `cx/gpt-6-sol|max` (1) and
    `cx/gpt-6-sol|medium` (24): a model keeps one provider segment.
  - `cache_write_input_tokens` is new. It is null in 246 actor totals and 229 attempts, the same counts
    as their unknown usage.
  - `max_request_input_tokens` is set on 1,487 attempts and null on 16.
- **Commit 5, R1 to R2: 79 fields, all new.** 238 sub-agents, 238 `joined`.
  - `fork_turns` reads `all` 68, `default_all` 161 and `none` 9, and all 238 are `fork_consistent`.
  - `route_vs_parent_turn` matches on the model 238 times, and on the effort 234 times (4 mismatches).
- **Commit 6, R2 to R3: 28 fields.** All are the new, zero-valued `codex_commands` counters. The previous
  stage's forms probe, which is not kept here, read every `CommandExecution` item of the store (all
  records, no window, copied ones included) and found each to be `bash -lc` (7,634) or `bash -c` (17).
- **Commit 7, R3 to R4: 315 fields.**

| Total over the groups | R3 | R4 |
|---|---|---|
| `sandbox_operations` | 30,620 | 30,891 |
| `m3.results` | 18,549 | 18,284 |
| `calls_without_result` | 6 | 0 |
| `m5.results` | 153 | 0 |
| `proxy.nested` | 588 | 593 |
| `by_carrier.code_mode.results` | 16,410 | 16,762 |
| `by_carrier.other.results` | 1,874 | 1,522 |
| `m4.remote_fetches`, `shell_fetch`, `ctx_sandbox_fetch` | 8,222, 0, 9 | unchanged |
| `code_mode` `exec_calls`, `wait_calls`, `nested_items`, `unattributed_items` | absent | 16,410, 352, 30,891, 0 |

  - 271 items move from direct to nested. That is 75 `CommandExecution` and 196 `McpToolCall`, all after
    an exec of their turn but outside the old span (the census below).
  - 352 `wait` outputs move from `other` to `code_mode`.
  - M3 loses 265 results; the other 6 moved items had no output. M5 loses all 153 of its results: each
    came from a ctx item the new rule nests, after an exec of its turn.
  - U1's `cli_lanes` `rtk_proxy` carrier `nested` gains 27 (`ctx` 22 and `rtk_proxy` 5 before).
  - The M4 split does not move, because no moved item ran `curl` or `wget`. No actor histogram changes.
- **Commit 8, R4 to R5: 28 fields, all new.**
  - `legacy_unobservable_exec_calls` and `_sites` are 0, since every rollout is paginated.
  - `outer_http_unverified_exec_calls` is 0, since every rollout names a client whose isolate was read.
  - `outer_http_mentions` totals 1,532 (workers 1,531, negative controls 1).
- **Commit 9, R5r to R6p: 99 fields.** Both ran with `--rtk-check` under this host's HOME, whose Claude
  settings hold 26 Bash deny rules (a count, read without values). The working directory was a scratch
  directory outside any checkout. R6r repeated R6p concurrently and differs from it in 0 fields.

| Total over the groups | R5r | R6p |
|---|---|---|
| `rtk_parts.calls` | 6,932 | 6,932 |
| `rtk_parts.eligible_parts` | 3,024 | 3,024 |
| `rtk_parts.observed_covered_parts` | 1,965 | 1,965 |
| `rtk_parts.explicit_rtk_on_excluded_or_sensitive` | 206 | 206 |
| `rtk_parts.ineligible_parts` | 3,243 | 3,294 |
| `rtk_parts.unknown_calls` | 798 | 747 |
| `rtk_parts.d7` `eligible_parts`, `covered_parts` | absent | 3,024, 1,965 |
| `rtk_parts.d7` `log_find_unresolved_parts`, `log_find_requires_raw_parts` | absent | 9, 0 |
| `rtk_parts.d7.wrapped_exceptions` | absent | 206 |

  - `rtk_parts.agent` reads `codex` in every group.
  - `unknown_calls` falls by 51 and `ineligible_parts` rises by 51 (32 in workers, 19 in negative
    controls). The claude replay met a home deny rule and answered with a denial, which the kernel counts
    as unknown. The codex replay has no rules to meet, and under it the same parts read as ineligible.
    The eligible parts, their coverage and M6c's zero counter do not move.
  - `d7` equals the fixed-config eligible parts here, since no `rtk_log_find` review exists. Its 9
    unreviewed `log` or `find` parts (7 in workers, 2 in negative controls) leave `d7.status` incomplete in
    those groups. All 206 `wrapped_exceptions` come from `explicit_rtk_on_excluded_or_sensitive`.
    `d7.coverage` is 0.4706 for workers and 0.941 for negative controls.
  - `rtk_parts.status` is incomplete in both runs for workers and negative controls, because of their
    remaining unknown calls. This run does not break them down by cause.

## Census (`census.py`, the checkout at 14e3c376)

```
client.cli_version=0.155.1	277
client.cli_version=0.157.1	1343
client.history_mode=paginated	1620
exec.calls	16410
exec.extra_outputs	38
exec.http_mentions	1532
exec.http_mentions.no_nested_ctx_code_item	51
exec.more_than_one_output	25
exec.sites	22888
exec.sites.bracket	183
exec.with_http_mentions	1091
exec.with_http_mentions.no_nested_ctx_code_item	33
exec.with_sites	14106
exec.with_sites.no_attributed_item	100
item.CommandExecution.span_rule=direct.turn_rule=nested	75
item.CommandExecution.span_rule=nested.turn_rule=nested	6857
item.McpToolCall.span_rule=direct.turn_rule=nested	196
item.McpToolCall.span_rule=nested.turn_rule=nested	20113
item.web.search.span_rule=nested.turn_rule=nested	3650
rollouts	1620
wait.after_exec_in_turn	352
```

- `item.*` splits the emitted items without a model call id by the two rules.
- `exec.extra_outputs` counts the code-mode `notify()` outputs beyond an exec call's first (description.rs:34).
  The kernel keeps the first result of a call, so these 38 outputs are not in M3; this is a residual,
  not changed here.
- 1,481 of the 1,532 outer HTTP mentions are in exec calls that have a nested Context Mode code item
  (`ctx_execute`, `ctx_execute_file` or `ctx_batch_execute`) after them, whose code the kernel reads
  itself. The other 51, in 33 exec calls, have none. The census counts co-occurrence only; it does not
  match a mention to an item.

## Claude byte identity (`claude-byte-identity.py e97080fa 14e3c376`)

```
e97080fa hermetic exit=0 bytes=93191 sha256=0f300368b75b1ba5ded8370404047693cd9de1b7162645075a7fe001a9c19f20 rtk_parts.status=measured calls=32 eligible_parts=21 d7=False
e97080fa host exit=0 bytes=107930 sha256=a9cbecc44027f6c7e1b3ca4de7a7e7f4e567a1cfe93fc8d4d46967bc18543883 rtk_parts.status=measured calls=32 eligible_parts=21 d7=False
14e3c376 hermetic exit=0 bytes=93191 sha256=0f300368b75b1ba5ded8370404047693cd9de1b7162645075a7fe001a9c19f20 rtk_parts.status=measured calls=32 eligible_parts=21 d7=False
14e3c376 host exit=0 bytes=107930 sha256=a9cbecc44027f6c7e1b3ca4de7a7e7f4e567a1cfe93fc8d4d46967bc18543883 rtk_parts.status=measured calls=32 eligible_parts=21 d7=False
IDENTICAL
```

The replay was measured in every run (32 Bash calls, 21 eligible parts), so the identity covers the changed
code path. `d7` is absent from the Claude output.

## Upstream sources read for commits 7 to 9

Each file was fetched read-only at its pinned revision; the sha256 is of its bytes.

- openai/codex `rust-v0.157.1` (tag object ac0e23e5, commit 36650394):
  - `codex-rs/code-mode-protocol/src/description.rs`
    2dbd58a3210c05fab918dca4426c3947a6732ec48e80a05344d432e314546c95. Line 24 reads "Runs raw
    JavaScript -- no Node, no file system, no network access, no console."
  - `codex-rs/code-mode-runtime/src/runtime/globals.rs`
    e62df37ddd8d36f3f799d3a2713b225661e3706dcaf2fe97b3cf183427903c07. Lines 36-48 install `tools`,
    `ALL_TOOLS`, `clearTimeout`, `setTimeout`, `text`, `image`, `audio`, `generatedImage`, `store`,
    `load`, `notify`, `yield_control` and `exit`.
  - `codex-rs/code-mode-protocol/src/lib.rs`
    c1c852edadb044f8941741d432ee8343e15df1d9d01776642c6eb0fa05b18893. Lines 51-52 name `exec` and
    `wait`.
- openai/codex `rust-v0.155.1` (tag object 4e21628f, commit be2951ea34f0d295ed0becf97079f92fa5f6950e):
  - `description.rs` a85090f7b639db03dc336937490b3230e37203da5d780d5c20b0bf378276ee24, with the same
    sentence at line 20.
  - `globals.rs` and `lib.rs` are byte-identical to 0.157.1's.
- rtk-ai/rtk `v0.50.0` (commit 1d87b8e719ce0a50c223cd93ca64dd16921f9aec):
  - `src/hooks/decision.rs` 9106ef9384fd4250dec83ae2e849c91387d9291743a7176b6a60534b89c78978.
    Lines 61-97 decide the same way for every agent: a Deny verdict denies, an unattestable construct
    defers, otherwise the rewrite. Lines 190-205 map `claude` and `copilot` to `InProcess(Host::Claude)`
    and `codex` to `InProcess(Host::Codex)`.
  - `src/hooks/permissions.rs` f0c1b3e4f177b17eab184fda38ada1bf63c78779a9844e02256c1756265065ac.
    Lines 56-67 give `Host::Codex` no rule source. Lines 141-175 merge the Bash rules of the project's and
    the home's `.claude/settings.json` and `settings.local.json` for `Host::Claude`.
  - `src/hooks/hook_check.rs` b88ac3400b27cb70603c16999e63e918cb13ef99775f3a678b2269638d3ba002.
    Lines 26-59 and 88-135: the claude path prints a once-a-day "No hook installed" warning when a Claude
    directory registers no rtk hook. The kernel's five-exclusion probe reads that as an error.
  - Behavior, run here with rtk 0.50.0: under a HOME whose settings deny `Bash(git status)` (and register
    the hook), `rtk hook check --agent claude 'git status'` exits 1 with "Denied by a permission rule",
    and `--agent codex` prints the rewrite `rtk git status`. Either agent answers the empty command with
    "No rewrite for: ".

## Residuals (reported, not changed)

- Extra `notify()` exec outputs (38 across 25 exec calls here) are not in M3: the kernel keeps a call's
  first result.
- A hosted web search's `TurnItem::WebSearch` item is not emitted (0 `web_search_call` records here),
  as the Claude kernel counts no server tool.
- The Claude replay (unchanged, byte-identical) is `unavailable` in a process whose first claude answer
  carries rtk's once-a-day warning.
- The outer-JS decision (tools/skill-usage/README.md, "The outer exec code") awaits the PR-A owner's
  acceptance.

## Repair round (2026-09-29): the Codex call ledger

The independent review of 802c35d7 found binding correction 1 of the U3 build (gap G1 of the U11 design)
neither delivered nor recorded as missing (medium). This round adds `skill_usage.py --lanes --call-ledger PATH`
(tools/skill-usage/README.md, "The private call ledger"), commits 00c458ba to 32d5dde6. The ledger's rows come
from the kernel's `callLedger`, PR-A U2's export, which this branch's kernel does not have. On this branch
`--call-ledger` therefore exits 2 and writes nothing, and 5 of the 14 `CodexCallLedger` tests skip.

### Scripts

- `rehearse-with-u2-kernel.sh REPO REV DEST` extracts this branch at REV with `git archive`. It replaces
  `child-usage.mjs` with PR-A U2's copy at b2dd1eb7 (sha256 `9d20f7e4...300b3f`), and makes no ref, worktree or
  merge. The tree holds U3's Python and U2's kernel only. U3's own kernel changes (the rtk replay agent and D7)
  are absent, and the ledger does not read them.
- `ledger-host-check.py REPORT LEDGER` checks a private ledger against its own lane report. It prints counts,
  states and invariants, never an id, a path or command text.
- `probe-end-of-options.py` counts the store's shell argv forms that the `--`/`-` end-of-options fix reads
  differently.

### Ledger tests with U2's kernel

Run with `python3 -B -m unittest -v tests.test_skill_usage.CodexCallLedger` in the rehearsal tree:

| Tree | Result |
|---|---|
| 00c458ba (tests only) | 13 run, 13 fail (`FAILED (errors=17)`): 6 `TypeError` (no `call_ledger` argument), 5 `AttributeError` (no `kernel_exports`), 2 `SystemExit: 2` (no `--call-ledger` flag) |
| 977e56c4 (the ledger) | 13 run, `OK`, 0 skipped |
| 45a5c0c1 (the head's code) | 14 run, `OK`, 0 skipped (the `--out` refusal test added at fd5268a9) |

On the branch itself (no `callLedger` in the kernel) the same class read `FAILED (errors=12, skipped=5)` at
00c458ba (8 failing, the 5 real-kernel tests skipped) and `OK (skipped=5)` at 45a5c0c1.

### Host run of the rehearsal tree

The tree came from `rehearse-with-u2-kernel.sh` at 5e4943e5. In it, `skill_usage.py --lanes` ran over the store
with the window of R0 to R6 (`--now` equal to `--until`), `--json --out <private> --call-ledger <private>`. It
ran without `--rtk-check`, because U2's kernel lacks U3's replay agent. It exited 0 after 912 seconds, and the
ledger file has mode 0600. `ledger-host-check.py` printed:

```
ledger.mode_0600	true
ledger.rows	49175
ledger.schema	["codex-call-ledger/1"]
ledger.field_sets	1
report.actors	1436
report.sessions_in_window	1436
ledger.actors_with_rows	1390
ledger.threads	1390
ledger.call_id_null	0
ledger.duplicate_keys	0
ledger.by_state	{"cancelled_or_unfinished": 3650, "failed": 1031, "succeeded": 44494}
ledger.by_owner_kind	{"exec": 37200, "subagent": 11975}
ledger.by_history_mode	{"paginated": 49175}
ledger.by_native_status	{"None": 21917, "completed": 26227, "failed": 1031}
ledger.by_cause	{"None": 49175}
ledger.by_tool_class	{"Bash": 6932, "WebFetch": 2035, "WebSearch": 1615, "exec": 16410, "mcp": 20309, "other": 1267, "spawn_agent": 238, "wait": 352, "wait_agent": 17}
ledger.sandbox_true	30891
ledger.code_mode_true	16762
ledger.server_set	20309
report.actors_with_call_states	1436
inv.rows_eq_attempted	[49175, 49175, true]
inv.states_eq	true
inv.state_mismatches	{}
inv.sandbox	[30891, 30891, 30891]
inv.actor_count_mismatches	0
inv.owner_kind_mismatches	0
privacy.ids	50565
privacy.id_equal_to_a_report_string	0
privacy.thread_id_inside_report_text	0
privacy.long_call_ids_checked	49175
privacy.long_call_id_inside_report_text	0
```

- **One row per call the kernel counts.** The 49,175 rows equal the sum of U2's `call_states.attempted` over
  the 1,436 actors, both per actor and per state. The 30,891 sandbox rows equal `call_states.sandbox`,
  `sandbox_operations` and R6p's `code_mode.nested_items`. The 16,410 `exec` rows equal
  `code_mode.exec_calls`. The 16,762 code-mode rows equal the code-mode carrier's results (exec plus `wait`).
- **Keys.** No row has a null `call_id` and no `(thread_id, call_id)` pair repeats. 46 sessions of the window
  hold no call.
- **Privacy.** No thread or call id of the ledger appears in the report, as a whole string or inside one.
- **Finding (reported, not changed): nested web search items read as not executed.** All 3,650
  `cancelled_or_unfinished` rows are nested `WebSearch` (1,615) or `WebFetch` (2,035) calls from `web.search`
  `Extension` items.
  - Such an item has no status field. `WebSearchItem` is `{id, query, action, results}`
    (openai/codex rust-v0.157.1 `protocol/src/items.rs:372-381`), and on this store every one of the 4,220
    such items (all records) has the keys `action, id, kind, query, results, type`.
  - The adapter emits no result for such an item, and no output shares its id.
  - U2's projection therefore reads it as no result with no deciding native status, which is
    `cancelled_or_unfinished`. The kernel's `calls_without_result` leaves sandbox calls out, so it reads 0 here.
  - The `item_completed` event is itself the item's completion. Two ways to decide it are open:
    - the adapter supplies `native_status: completed` for such an item;
    - U2's projection gets a rule for nested calls.

    Until the U2 and U3 owners decide, M14 reads these 3,650 calls (7.4% of the rows) as not executed.

### Differential R7r against R6p

`run-differential.py --rtk-check R7r=5e4943e5` ran under R6p's conditions: this host's HOME, and a scratch
working directory outside any checkout. It exited 0 after 1,110.6 seconds, with 1,436 sessions, 1,620 files and
0 parse errors.

- `--compare` of R6p and R7r prints `DELTAS 0`.
- `--totals` of the two are equal in all 37 fields. Examples: `rtk_parts.calls` 6,932, `eligible_parts` 3,024,
  `unknown_calls` 747, `code_mode.nested_items` 30,891 and `rtk_parts.d7.eligible_parts` 3,024.

This round's code therefore leaves the published report unchanged on this store. The recorded R6p figures
reproduce here. The one later code commit, 8c49aec8, only adds a refusal before the scan, taken when `--out`
and `--call-ledger` name one file, which these runs never do.

### Also checked in this round

- `claude-byte-identity.py 802c35d7 5e4943e5`: `IDENTICAL`, with the digests recorded above (hermetic
  `0f300368...`, 93,191 bytes; host `a9cbecc4...`, 107,930 bytes). This round does not change the kernel.
- The empty command in rtk replay. The kernel's own checker (`rtk hook check --agent <agent>`, rtk 0.50.0,
  the five-exclusion config) was asked through `measureTranscript` with one Bash call whose command is `''`.
  Under `codex` and `claude` alike it reads `measured`, 1 call, 0 unknown calls, 0 parts. The bridge's added
  unknown call for an unresolved command is therefore its only one (the review's double-count question).
- `probe-end-of-options.py`: 1,620 files, 7,651 argv commands, 0 with a `--` or `-` word, 0 read differently.
  The fix changes nothing on this store.

### Residuals of this round (reported, not changed)

- The ledger needs PR-A U2's kernel. Until it is merged here, `--call-ledger` exits 2 and five tests skip.
- Legacy history mode keeps `McpToolCallEnd` and `WebSearchEnd` events and non-completed `SubAgentActivity`
  events (`rollout/src/policy.rs:123-139`), which this adapter does not read. This round corrected the text
  that said none are persisted. Reading them would change the measurement, and this store holds no legacy
  rollout.
- The nested web search state above is left for the U2 and U3 owners to decide.
