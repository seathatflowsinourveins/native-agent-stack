# PR-A U2: Claude-side kernel measures, host evidence and differential inputs

Local transcript analysis on one workstation, 2026-09-29. These are count-only scans of the host's Claude Code
transcript store (5,131 to 5,137 `.jsonl` files as it grew during the day), not provider runs and not a
differential. No output here holds an id, a path, a host name or transcript text. Each scan prints key names,
enum values (model names, client versions, `speed`, `service_tier`, `inference_geo`, iteration and hook types)
and counts only.

## Files

| File | What it is |
| --- | --- |
| `sources.json` | Every upstream document a U2 rule cites, with URL, fetch time, sha256 and the exact sentence it rests on |
| `expected-changes.json` | The allow-list for the U2 differential: the key paths U2 adds or changes, with equality required everywhere else |
| `scans/usage-iterations-{1..4}.py` and `.json` | Shapes of `message.usage` on assistant rows: `iterations[]` types and keys, the executor-sum invariant, the 5m/1h split, streamed rows and advisor calls |
| `scans/hook-rows.py` and `.json` | Hook attachment rows: events, name shapes, content shapes, stdout claims and pairing |
| `scans/large-results.py` and `.json` | Results over 5,120 B per tool: content shapes, JSON as returned, after the ctx code echo, after the Read `cat -n` numbers |
| `scans/kernel-usage.mjs` and `.json` | The U2 kernel's `transcriptUsage` over every transcript: how often each B9 reason makes usage incomplete |
| `scans/kernel-split-differs.mjs` and `.json` | Which message has a 5m/1h split unequal to its combined counter under the kernel |

Reproduce with the Claude Code projects directory as `<root>`. The `.mjs` checks also take the kernel path.
The store keeps growing, so expect later counts to be larger.

```
python3 scans/usage-iterations-1.py <root> > scans/usage-iterations-1.json
node scans/kernel-usage.mjs examples/claude-native/workflows/child-usage.mjs <root> > scans/kernel-usage.json
```

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

## Differential (a later U2 stage)

`expected-changes.json` lists, stage by stage, the key paths U2 adds and the two pre-existing paths it
changes on purpose. These are `hook_context.by_hook['(other)']`, which loses over-long MCP hook names to
their server-level key, and `usage.complete` under B9. The later stage runs the base and U2 kernels over one
root and window and requires equality on every other path.
