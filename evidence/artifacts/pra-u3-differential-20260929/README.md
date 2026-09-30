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
