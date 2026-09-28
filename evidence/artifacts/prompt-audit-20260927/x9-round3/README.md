# X9, third round (2026-09-28)

X9 is the prompt audit's flag on `CLAUDE.md:3-4`, which tells the model to use `/mcp` and `/context`, commands it
cannot invoke. Rounds 1 and 2 split between two replacement texts. The round-2 addendum of
[`docs/decisions/2026-09-27-prompt-audit-resolution.md`](../../../../docs/decisions/2026-09-27-prompt-audit-resolution.md)
named the comparison that would decide it. This round ran that comparison and then asked both model families again,
blind, in both orders.

**Outcome: applied, unanimously.**
- All four judgments chose the GPT-6 lane's text (`../x9-round2/arms/CLAUDE.g.md`), with no voiding audit hit.
  `CLAUDE.md` now holds it at lines 3-8.
- The preregistered metric order would have chosen the same text: wrong statuses tie at 0, and correct statuses are
  10 to 8.
- Interactive sessions were not tested. Only the user can run them, and they are this decision's overturn condition.

## Layout

| Path | What it is | Evidence class |
| --- | --- | --- |
| `prereg-r3.json`, `prereg-r3.sha256`, `prereg-r3.draft.json`, `freeze_prereg_r3.py` | The preregistration of K5 and K6, frozen before the first counted run; the unhashed draft; and the script that froze it and hashed every harness file | protocol |
| `prereg-check.json` | Each hashed file checked against its published copy. Two files changed after freezing and are published twice (see below). The three texts are round 2's published arms, byte for byte | protocol |
| `fixtures/` | `workspace-guard`, a plugin with one `SessionStart` hook and nothing else (K5), and `ticket-tracker`, a stdio server on the MCP Python SDK 2.2.0 that ends 1 s after its first `tools/list` and refuses to restart (K6) | protocol |
| `run_arm_r3.sh`, `summarize.py`, `summarize_r3.py`, `metrics.py`, `metrics_r3.py`, `analyze_r3.py`, `grader_selftest.py` | Harness, deterministic graders and their 33 labelled answers | protocol |
| `promptfooconfig-r3.yaml`, `eval-r3.log` | promptfoo 0.123.1 config and log, with the harness host path replaced. The log reports every test as failed by design, because the preregistration does not use promptfoo's per-test pass (`not_used`) | local integration run |
| `analysis-r3.json`, `results-r3-compact.json`, `run-window.json` | 30 headless Claude Code 2.1.283 runs on `claude-opus-5-5[1m]`, 08:14:47-08:31:10Z; all 30 included and 0 grader mismatches | local integration run |
| `probe/`, `probe_r3.sh`, `probe_facts.py` | The four uncounted probes, as facts about the fixtures only (`facts.json`) plus the fixture server's own logs. The raw transcripts are withheld because they hold the host's init data | installed-client observation |
| `sources-r3.json` | Dated sources with verbatim quotes, gathered by one `stack-researcher` agent for this round's X9 questions (Q1, Q2) and lane A (Q3-Q5) | source review |
| `make_x9_round3.py`, `make_x9_round3.frozen.py` | The builder of the judges' inputs, packets and prompts, as run and as frozen | protocol |
| `check_orders_r3.py`, `check_orders_r3.frozen.py` | The check that both presentation orders carry the same evidence, as run and as frozen | protocol |
| `isolate_r3.sh`, `isolation-receipt.json`, `isolation_receipt_r3.py` | The steps before dispatch (worktrees removed, work moved away, root scanned, orders checked, the sent prompts scanned for configuration text, the GPT-6 judges started), with commands, outputs and times from the coordinator's log | coordinator record |
| `judges/` | Inputs, packets, prompts, schema and mapping as sent (`sent-sha256.json` holds each file's hash as received), the four returns with the runner's own records, the audit, the judge actions, the tally and their scripts | retained model judgments |
| `void_patterns_r3.py`, `audit_r3.py`, `tally_r3.py` | The void patterns, audit and tally, hashed before any return was read | protocol |
| `usage.json` | Provider usage of the comparison runs, the probes, the four judges and the source research, each counter kept separate | usage record |
| `exposure_scan_dir.py`, `package_x9_round3.py` | The count-only scan run on this directory before its first push, and the script that wrote this package | protocol |

## Checks you can repeat

Run these from this directory.

- `sha256sum -c prereg-r3.sha256` prints `prereg-r3.json: OK`.
- `python3 -B grader_selftest.py` prints `33 of 33 classified as labelled` and exits 0.
- `python3 -B check_orders_r3.py judges/packets judges/mapping.json` prints `same evidence in both orders: True` and
  exits 0.
  - `python3 -B check_orders_r3.frozen.py judges/packets judges/mapping.json` reproduces the false difference and exits
    1. The frozen copy's clause pattern also stops at commas, so a clause such as `[c] K1 0, K2 3, K3 1` is cut
    short. The copy as run uses round 2's revised pattern again.
- `judges/audit.json`, `judges/judge-actions.json` and the Claude usage cannot be recomputed from this package. Their
  scripts read the judges' session transcripts, which are withheld because they carry the host's injected session
  context.

## Changed after freezing

Both changes were made after the counted runs and before any judge started. The frozen copies carry the hashes that
`prereg-r3.json` records.
- **`make_x9_round3.py`.** As first written, it withheld every K5 status sentence, because every K5 run read settings
  files.
  - It now withholds a status sentence only when the sentence quotes client configuration or names a settings file.
  - It still withholds an answer head whenever its run read settings files.
  - For each K5 run, it adds a list of what the run's commands consulted, taken from the commands' own text. This
    list was observed, not preregistered.
- **`check_orders_r3.py`.** Its clause pattern gained a comma when it was copied from round 2's revised check. That
  produced the false difference described above.

## Settings content

- The runs used `bypassPermissions`, and every K5 run read client settings files through Bash.
  - The packets and prompts were built with those runs' answer heads already withheld.
  - Each answer's status sentence is kept unless it quotes client configuration or names a settings file.
- The configuration-text scan finds five matches in each packet and judge prompt. None is a configuration value:
  - two metric definitions name settings files;
  - a round-2 K4 summary line names the kinds of file its runs read;
  - one round-2 K4 status sentence lists the checks its run made (a settings file, the status-line wiring);
  - the list of untested cases names `enabledPlugins`.
- The scan's other matches in this directory are its own pattern text, in the scripts and in `isolation-receipt.json`.

## What is not claimed

- **Scope of the runs.** The runs were headless, on one model (Opus 5.5), under `bypassPermissions`, with 5 runs per
  text and case.
  - The five K5 affirmations under the applied text followed Bash reads of the process command line and the fixture's
    hook state file. A session in another permission mode may need approval for those reads.
  - The difference is the output of a decision rule, not a significance claim.
- **Cases not covered.**
  - A plugin installed from a marketplace and listed in `enabledPlugins`.
  - An MCP server whose tools come from the discovery cache without a process.
  - A stdio server that the client restarts successfully. Probe p2 saw Claude Code 2.1.283 do that, although the MCP
    docs say stdio servers are not reconnected automatically.
- **Interactive sessions.** A user can answer a request to run a command there. Only the user can run these sessions.
- **Advisor calls.** Each Claude judge made one server-side advisor call. The advisor's own model usage is not in
  `usage.json`.
