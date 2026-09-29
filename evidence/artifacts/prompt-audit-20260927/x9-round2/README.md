# X9, second round (2026-09-28)

X9 is the prompt audit's flag on `CLAUDE.md:3-4`, which tells the model to use `/mcp` and `/context`, commands it
cannot invoke. Round 1 split 2 and 2 between two replacement texts (see
[`docs/decisions/2026-09-27-prompt-audit-resolution.md`](../../../../docs/decisions/2026-09-27-prompt-audit-resolution.md)).
This second round added the installed client's own responses, an executed comparison of the three texts and new
dated sources. It then asked both model families again, blind, in both orders.

**Outcome: split, no edit.**
- Attempt 2, the final attempt, passed its recorded audit.
  - Both GPT-6 judgments chose the text from the GPT-6 lane (`arms/gpt6.txt`).
  - Both Claude judgments chose the text from the Claude lane (`arms/claude.txt`).
- All four rejected keeping the current line. The two Claude judgments give the reason: the client refuses the
  commands it names (C1, C2). Both GPT-6 judgments cite C1 and C2. Only a text chosen unanimously is applied.
- `CLAUDE.md` is unchanged. The decision record's addendum of 2026-09-28 gives the positions and what would decide
  the question.
- **The packets misstated K4's model.** They said every comparison run used the host's default model, Opus 5.5. K1-K3
  did, but K4 ran on Sonnet 5, and why is not recorded. Both Claude judgments cite that scope. The published packets
  are the judges' inputs as sent, except that K4's nine answer heads are withheld (see "Settings content" below).
  The outcome stands, because a split means no edit either way.

## Layout

| Path | What it is | Evidence class |
| --- | --- | --- |
| `prereg.json`, `prereg.sha256` | Preregistration of K1-K3, revision 1, written before any counted run | protocol |
| `run_arm.sh`, `summarize.py`, `metrics.py`, `analyze.py`, `arms/` | Harness and the three `CLAUDE.md` texts, byte for byte (the hashes in `prereg.json` hold) | protocol |
| `promptfooconfig.yaml`, `eval.log` | promptfoo 0.123.1 config and log, with the harness host path replaced (its preregistered hash is of the file as run). The log reports every test as failed and exit code 100 by design: promptfoo's per-test pass needs every assertion, and the preregistration does not use it (`not_used`) | local integration run |
| `analysis.json`, `results-compact.json`, `run-window.json` | K1-K3: 27 headless Claude Code 2.1.283 runs on Opus 5.5 (`claude-opus-5-5[1m]`) from 02:23:47Z to 02:36:42Z, deterministic graders, 0 grader disagreements | local integration run |
| `k4/` | K4: 9 runs on Sonnet 5 (`claude-sonnet-5`) from 02:55:10Z to 03:03:34Z, all metrics descriptive. It was preregistered after K1-K3 and after attempt 1 was voided, to exercise the fallback, which K1-K3 never did. Of the three returns seen from attempt 1 (`attempt1/`), the Claude return called the fallback decisive, and both GPT-6 returns held that coverage outweighs it. The packet's disclosure says the returns seen had named the fallback as the difference that decides. The nine answer heads are withheld, because they quote client configuration files; each answer's first sentence is kept. `k4/skill-list-mentions.json` keeps the sentences behind "seven of nine answers cited the plugin's commands from the skill list" | local integration run |
| `settings-reads.json` | For each comparison run, the client configuration file names its Bash commands named, without their contents | local integration run |
| `probe/` | Uncounted probes: the Skill tool's refusals for `context` and `mcp` (C1, C2), and the command and skill counts from the headless init event, with the built-in commands checked (C4) | installed-client observation |
| `sources-round2.json` | 38 dated sources with verbatim quotes, and 5 recorded searches that found nothing | source review |
| `sources-supplement.json` | The skills-page quote that the packets' K4 section cites and `sources-round2.json` does not hold | source review |
| `isolation-receipt.json` | The coordinator's steps before attempt 2's dispatch, with their commands, outputs and times | coordinator record |
| `attempt1/` | The void first attempt: the void record (made before any Claude choice was seen), the rules for attempt 2 as amended before any attempt-2 judge started, the returns that were seen, and the audit's self-test on these transcripts | retained model judgments (void) |
| `attempt2/` | The final attempt: builder, inputs, packets, prompts, schema, mapping, the four returns, the audit, the tally, the checks below and usage | retained model judgments |
| `usage.json` | Provider usage of both attempts and of the comparison runs, each counter kept separate. The attempt-1 buckets include the round's source research (a `stack-researcher` agent, 73 API calls) and the GPT-6 runner probe | usage record |
| `package_x9_attempt2.py` | The script that wrote this package: what it copied byte for byte, replaced, dropped or withheld | protocol |

## Checks you can repeat

Run these from this directory.

- `sha256sum -c prereg.sha256` and `(cd k4 && sha256sum -c prereg-k4.sha256)`.
- The `sha256` maps inside `prereg.json` and `k4/prereg-k4.json` hold for every file copied byte for byte. The two
  promptfoo configs differ only by the replaced host path, and the raw probe transcripts are not published.
- `python3 attempt2/check_orders.py attempt2/packets attempt2/mapping.json` checks that the two orders carry the same
  evidence once the A/B labels are mapped back, and exits 1 on any difference.
  - The first version, run before dispatch at 03:07:50Z, printed False and exited 0 either way. It compared the
    per-text clauses inside a line (such as "[c] 3; [g] 2") in their written order, and each order lists its
    Return A first. `attempt2/check_orders_first.py` is that version, recovered verbatim from the coordinator's
    session log (its only write, at 03:07:47Z); `python3 attempt2/check_orders_first.py attempt2 attempt2/mapping.json`
    reproduces the False.
  - The published version was revised after review. It sorts those clauses and prints True on the same packets.
- `python3 attempt2/retally.py` recomputes the tally from the published files with the rule of `tally_attempt2.py`,
  and exits 1 if the result differs from `attempt2/tally.json`. `tally_attempt2.py` itself reads the coordinator's
  working layout:

  | Working file | Published as |
  | --- | --- |
  | `returns2/<family>-<order>.json` | the `return` object of `attempt2/<family>.<order>.json` |
  | `attempt2-mapping.json` | `attempt2/mapping.json` |
  | `audit-attempt2.json` | `attempt2/audit.json` |
  | `tally-attempt2.json` | `attempt2/tally.json` |
  | `adjudication-inputs/` | `attempt2/inputs/` |
  | `attempt1-void.json` | `attempt1/void.json` |
  | `audit-selftest-attempt1.json` | `attempt1/audit-selftest.json`, each hit without its text window |
  | `probe/probe-skill-builtins.jsonl`, `probe/probe-0.jsonl` (raw, withheld) | `probe/skill-builtins.json`, `probe/init-lists.json` (facts only) |

- The hashes of `audit_attempt2.py`, `tally_attempt2.py` and `void_patterns.py` were recorded in
  `attempt1/void.json` (`attempt_2_rules.audit`) at 03:12:01Z, before any attempt-2 return was read.
- `attempt2/sent-sha256.json` holds the hash of every file the attempt-2 judges received.
  - The inputs and schema are published byte for byte.
  - The packets and the two judge prompts are published with K4's nine answer heads withheld, because those heads
    quote client configuration files.
  - The four prompt files are also published with the repository root's host path replaced.
- `attempt2/audit.json`, `attempt2/judge-actions.json` and the Claude usage cannot be recomputed from this package.
  Their scripts read the judges' session transcripts, which are withheld because they carry the host's injected
  session context.

## How attempt 2 was kept blind

- **The root the judges read.**
  - The judges read a plain export of `main` at `ba1700ad`, with no `.git`. That commit predates the round-1
    decision record, which names the lanes.
  - A scan of its 7,935 files found no string that maps a text to a lane, before dispatch and again afterwards
    (`attempt2/root-scan.txt`, with a `diff -rq` against a fresh export).
- **What the judges were given.**
  - The inputs carry no model name and no host path.
  - Before dispatch, every worktree was removed, and the attempt-1 files and the coordinator's work directory were
    moved into a held directory. The audit's ACCESS patterns flag any access to that directory.
  - `isolation-receipt.json` records these steps from the coordinator's own log: the worktrees removed (03:08:23Z),
    the move into the held directory (03:08:39Z), the root scan (03:08:48Z) and the start of the GPT-6 judges
    (03:09:14Z).
- **Who judged.**
  - The Claude judges were `blind-adjudicator` agents, with Read, Glob and Grep only.
  - The GPT-6 judges ran through the packaged runner: `codex_call.sh`, gpt-6-astra at effort max, a read-only
    sandbox (`codex_job.py:434` at `ba1700ad` passes `-s read-only`), and prompts that set explicit read limits.
- **The audit.** `attempt2/audit.json` applies `void_patterns.py` to:
  - every command, tool input and output;
  - every web search;
  - every advisor result;
  - every injected attachment.

  It found no voiding hit in any of the four judgments.
- **Where the judges read.** `attempt2/judge-actions.json` lists every command, search and file access.
  - No judge opened a path outside its input, its packet and the root.
  - The four "outside" strings listed for claude-AB come from the text of its own leak-check Grep pattern, not from
    files it opened.
- **Which checkout the GPT-6 judges read.** `attempt2/gpt6-workdir.txt` re-runs their read-only greps in the root
  and in the live checkout.
  - Every line specific to the root appears in the recorded outputs (80 of 80 and 177 of 177), so the judges read
    the root.
  - One line specific to the live checkout matched in each (1 of 47 and 1 of 102). It is the empty context line
    `examples/claude-native/workflows/README.md-273-`, a prefix of the root's longer line 273 in the recorded output
    (`attempt2/gpt6-workdir-liveonly.txt`).

## Attempt 1's self-test

`attempt1/void.json` says that the tool inputs of the Claude A/B judgment named neither the round-1 record nor the
private work directory, and that its blindness was not established. The self-test's hits for that judgment bear this
out; `attempt1/audit-selftest.json` keeps their text windows, with the host prefix cut:
- its ACCESS matches are reads of its own attempt-1 input directory;
- its one MAPPING match in a tool input is an exclusion glob, `!evidence/artifacts/prompt-audit-20260927/**`;
- its search results returned lines 214 and 224 of the round-1 record at `ed3cd96c`, one line of each X9 text.

## What is not claimed

- **Scope of the runs.** Each case ran headless on one model: K1-K3 on Opus 5.5, the host's default, and K4 on
  Sonnet 5.
  - Interactive sessions and other effort levels were not tested.
  - Nor was a claim that the session truly cannot settle. K4's premise did not hold, since the plugin's commands are
    listed to the model with its skills.
- **Settings content.**
  - K2 and K4 runs read client settings files under `bypassPermissions`, the host's default permission mode.
    `settings-reads.json` lists the file names each run's commands named, including one K3 run.
  - This package keeps those names, the K1-K3 answers' first 240 characters and each K4 answer's first sentence.
    Bash command text is dropped.
  - The K4 answer heads quote enabled-plugin entries, status-line wiring and plugin install records. They are withheld
    in every published copy: the packets, the judge prompts, `k4/analysis-k4.json` and `k4/results-k4-compact.json`.
    The judges received them; `attempt2/sent-sha256.json` holds the hashes of the files as sent.
  - `k4/skill-list-mentions.json` keeps, from the full K4 answers, each sentence that cites the plugin's commands from
    the skill list, cut to 300 characters; none quotes a settings file.
  - The K2 answer heads name the MCP servers whose tools the session had loaded, the stack's documented components.
- **Family alignment.** Each family chose its own lane's text in both orders, blind and audit-clean. That is two
  judgments per family on one unit. It is a measured fact for this unit, not a general claim of bias.
- **Advisor calls.** Both Claude judges consulted the server-side advisor (2 calls and 1 call). Its own model usage
  is not in the recorded usage fields.
