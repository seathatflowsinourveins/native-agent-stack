# GPT-6 family tiering for a mechanical extraction stage: frozen preregistration

Frozen on 2026-09-26, before any call to the provider. This change adds the plan,
the scripts and offline tests only. No arm has run, and nothing here is a
measurement of any GPT-6 model.

## What and why

Every GPT-6 step on `nativestack-5975wx-20260925` runs `gpt-6-astra` at `max`
effort, and every step draws on one shared weekly Codex allowance. Some stages
are mechanical: their output can be scored deterministically. Such a stage may
not need the largest model at maximum effort. This plan asks:

> For a mechanical, deterministically scored extraction stage, which GPT-6 family
> member and reasoning effort matches `gpt-6-astra` at `max` at lower token cost,
> so that mechanical stages can route to it and the allowance does more work?

The token-save practice is the base layer. The measure is Codex's own
`turn.completed` usage for every call, including failed and retried calls. The
decision is frozen before any call, so no arm can be chosen after the fact.

## Arms

Every arm runs through the same frozen command. Only `-m` and the effort change.
The bundled catalog of `codex-cli 0.157.1` (`codex debug models --bundled`, read
offline) lists every model and effort below. Ultra is never used.

| Arm | Model | Effort | Role |
|---|---|---|---|
| A0 | `gpt-6-astra` | `max` | Control: today's default |
| A1 | `gpt-6-astra` | `medium` | Same model, less reasoning |
| S0 | `gpt-6-sol` | `max` | Workhorse model at maximum effort |
| S1 | `gpt-6-sol` | `medium` | Workhorse model at its default effort |
| L0 | `gpt-6-luna` | `max` | Fast, affordable model at maximum effort |
| L1 | `gpt-6-luna` | `medium` | Fast, affordable model at its default effort |

```sh
codex exec --ignore-user-config --skip-git-repo-check -s read-only -m <model> \
  -c model_reasoning_effort="<effort>" --output-schema <schema> -o <reply> --json "<prompt>" </dev/null
```

Each call runs in an empty 0700 directory outside every repository, without
`--search`, with `RUST_LOG` removed from its environment. `--ignore-user-config`
keeps the host's `config.toml` out. The native sign-in is used as it is.

## Task and data

The task, data and scoring come from
[`local-inference-latest-20260926`](../local-inference-latest-20260926/README.md)
(li26), unchanged:

- **Filings**: 8-K item extraction on the 2020-03-02 daily-index cohort, 360
  eligible filings.
- **Labels**: the filer-declared header `ITEMS`. They are not hand-checked or
  frontier-model labels.
- **Inputs**: li26's normalized primary-document texts, with its
  16,000-character head-and-tail cap.
- **Acquisition**: li26's private acquisition `acq-20260926`, with
  `inputs_sha256` `2a5c8c9bd1650bc20a3e7364defef2d725904f6eb1ef509a511a49526a32bfe0`.
  `run_arm.py` and `analyze.py` verify it with li26's own `load_inputs`, and
  li26's `verify-inputs` reported 360 eligible filings while this plan was
  written.

SEC filings are public, so sending them to the provider is permitted. Filing
text never enters the repository.

## Batches

The 360 filings keep their frozen (accession) order and are cut greedily into
batches:

- A filing joins the current batch while the batch then holds at most **15**
  filings and its whole prompt stays **under 110,000 bytes**. Otherwise it
  starts the next batch.
- Each prompt is one argument; Linux caps one argument at 131,072 bytes. A filing
  that reaches the bound alone, or that contains a batch delimiter or a NUL
  character, is refused before any call.
- On the frozen inputs this gives **25 batches**: 23 of 15 filings, one of 14 and
  one of 1. The prompts run from 12,088 to 106,870 bytes.
- The layout's SHA-256 is frozen in [`plan.json`](plan.json). Every arm, and
  `analyze.py`, rebuilds the layout and refuses a different one, so every arm
  sends the same batches.

[`prompt.txt`](prompt.txt) is li26's instruction adapted to a batch, with li26's
item list verbatim. [`response.schema.json`](response.schema.json) asks for one
`{accession, items[]}` object per filing, with items restricted to the 34 listed
codes. Codex sends the schema as a strict JSON-schema output format.

## Calls, slots, retries and the usage limit

[`run_arm.py`](run_arm.py) runs one arm with one call per batch:

- **Concurrency.** At most **3** calls run at once. Before its call, each worker
  takes a free slot lock (`slot-1` to `slot-3`, `fcntl.flock`) in the host's
  shared Codex lock directory, given as `--lock-dir`. The landscape-sweep runner
  takes the same locks, so all Codex jobs on the host together stay within its
  three-slot pool. codex inherits the slot lock and the arm's run lock, so a
  killed runner frees neither while its codex still runs. The lock directory is
  never created, so a mistyped path cannot start a private pool.
- **Per call.** The runner records exit code, wall time, slot and slot wait, the
  summed `turn.completed` usage, the reply's JSON validity and any usage-limit
  event. Usage covers input, cached input, cache-write input, output and
  reasoning output tokens.
- **Failures.** A failed call is one that:
  - timed out after 3,000 s;
  - exited non-zero;
  - reported `turn.failed`;
  - completed no turn;
  - wrote no reply, or a reply that is not the response envelope;
  - could not start;
  - or was left unfinished by a runner that died.

  Its batch runs **once more**. A batch that fails twice is recorded as failed and
  never runs again. Its filings stay in every denominator as invalid, so no batch
  is ever dropped silently.
- **Usage limit.** A usage-limit event is Codex's own `error` or `turn.failed`
  event saying "hit your usage limit". Model content and stderr never count. On
  such an event, running calls finish and are recorded, no call starts, and the
  run writes `LIMIT` in the state directory and **exits 3**. The coordinator then
  tells the user. While `LIMIT` exists, every run exits 3 without a call, and an
  arm already running (another arm's run may have written it) starts no further
  call and exits 3. After
  the reset, the coordinator removes it and runs the same arm again. Finished
  batches are kept, and the limited batch runs again without using its retry.
- **Interruption.** SIGINT or SIGTERM stops the running calls. Their process
  groups get TERM, then KILL after 10 s. The calls are recorded as interrupted
  (not counted), and the run exits 5.
- **Refusals.** Before any call, a run refuses (exit 2):
  - a changed frozen hash, plan value, input or layout;
  - a Codex version other than `codex-cli 0.157.1`;
  - a state directory that is not owner-only;
  - a run already in progress;
  - a later run whose plan, prompt, schema, inputs, layout or Codex version
    differs from the arm's first run.

## Metrics and decision rule

[`analyze.py`](analyze.py) reads every attempt of every batch, so no call can be
left out. It reuses li26's scoring functions unchanged: per-filing counts,
micro-F1, macro-F1 over codes with at least five labelled filings, and the paired
bootstrap. It reports, per arm:

- micro-F1 and macro-F1;
- the JSON-valid rate;
- calls by outcome, and retried, failed and pending batches;
- tokens per filing by kind;
- wall time.

A filing is JSON-valid only when its batch's final reply is exactly the envelope,
its accession has exactly one entry and the entry passes li26's per-filing rule.

**Billed tokens** are uncached input (input minus cached input) plus output.
Codex's `output_tokens` already includes `reasoning_output_tokens`
([`docs/token-practice.md`](../../../docs/token-practice.md)): the task's
"output plus reasoning" is that one number, and adding reasoning again would
count it twice. Cached input and reasoning are reported separately. The means
per filing divide an arm's totals over all its calls by 360.

**Rule.** An arm is routable for mechanical extraction when all three hold:

1. The paired bootstrap (10,000 resamples, seed 20260926) 95% lower bound of
   micro-F1(arm) − micro-F1(A0) is at least −0.02.
2. Its JSON-valid rate is at least 0.98.
3. Every one of its batches completed.

Among routable arms whose every call reported usage, the recommendation is the
lowest mean billed tokens per filing. A call ended by the usage limit counts with
whatever usage it reports. Ties go to the lower median wall time of ok calls,
then to plan order. A0 is itself a candidate, and if it wins, the default stays.

The result is inconclusive, and nothing changes, in these cases:

- A0 has not run, is incomplete, has a failed batch or an inconsistent record,
  or is below 0.98 JSON-valid.
- Any call reports cached input above input, or reasoning above output.

The decision file marks `final: true` only when all six arms are complete.

**Quota percentages** are context only. The coordinator can pass them with
`--quota-context`, but other sessions share the account, so a percentage change
is not attributable to one arm and never enters the rule.

## How to run it

The commands below are frozen. None of them ran in this change. Use pointer
variables; never spell out a private path in a shared record:

```sh
LI26_ACQ=~/.local/state/native-agent-stack/local-inference-latest-20260926/sec/acq-20260926
CODEX_SLOT_LOCKS=<the host's shared Codex slot directory, holding slot-1..slot-3>
```

1. Check the frozen files and the layout, which reads only the private inputs
   and prints aggregates:

   ```sh
   python3 blueprints/convergence-practice/gpt6-family-tiering-20260926/run_arm.py verify-frozen
   python3 blueprints/convergence-practice/gpt6-family-tiering-20260926/run_arm.py layout --acquisition "$LI26_ACQ"
   ```

2. Run the arms one after another. Two arms may also run at once; the slot pool
   still caps the host at three calls.

   ```sh
   for arm in A0 A1 S0 S1 L0 L1; do
     python3 blueprints/convergence-practice/gpt6-family-tiering-20260926/run_arm.py run \
       --arm "$arm" --acquisition "$LI26_ACQ" --lock-dir "$CODEX_SLOT_LOCKS" || break
   done
   ```

   Exit 3 means the shared usage limit was reached. Tell the user, wait for the
   reset, remove the `LIMIT` note named in the output's state directory, and run
   the same arm again. Exit 0 means the arm has no pending batch.

3. Analyze:

   ```sh
   python3 blueprints/convergence-practice/gpt6-family-tiering-20260926/analyze.py \
     --acquisition "$LI26_ACQ" --out <decision.json> [--quota-context <quota.json>]
   ```

The planning estimate below is not a measurement. One arm's 25 prompts total
2,016,724 bytes, roughly half a million input tokens at about 4 bytes per token.
Codex's own instructions are sent with every call, and reasoning at `max` adds
output, so the six arms spend a few million tokens of the shared allowance.

A new host must establish its own acquisition, its own slot directory and its
own Codex version check. This host's planning facts are not its acceptance.

## Evidence classes

- **This change.** Offline artifact checks only:
  - frozen hashes;
  - the validated planned record;
  - [the tests](../../../tests/test_gpt6_family_tiering_20260926.py). They use a
    fake `codex` that prints scripted `--json` events. They are local integration
    checks on synthetic fixtures, not upstream tests, and no test reaches the
    provider.
- **Planning reads.** `codex debug models --bundled` shows the catalog shipped in
  the binary; it is not the provider's live catalog. The layout aggregates come
  from the verified private inputs, and only aggregates were recorded.
- **The later run.** Native execution of hosted models on this host through the
  native sign-in, one run per arm. Its token counts are Codex's own counters. Its
  wall times are shared-host, shared-account observations.

## Privacy boundary

- Everything a run writes stays under
  `~/.local/state/native-agent-stack/gpt6-family-tiering-20260926/`, with 0700
  directories and 0600 files: Codex events, stderr, replies and per-call records.
- Codex keeps its usual session files under its own home, as it does for every
  `exec` run.
- The decision file holds aggregates only: no filing text, reply text or
  accession numbers. Registering results as receipts is a later change.

## What this does not claim

No result exists yet. When results exist, they will not establish:

- general or cross-task quality, or frontier parity;
- accuracy against hand-checked labels;
- any stage other than mechanical extraction with a deterministic scorer;
- provider cost in money, or a quota share attributable to one arm;
- whole-task token savings;
- stability over time, other days, other batch sizes, other Codex versions or
  later provider behaviour. There is one run per arm on one day, and Codex exec
  exposes no temperature or seed.

`gpt-6-sol` and `gpt-6-luna` run at their catalog default `priority` tier, and
`gpt-6-astra` at its default. Wall time only breaks ties.

## Files

| File | Role |
|---|---|
| [`plan.json`](plan.json) | Frozen arms, command, catalog observation, batching and layout hash, call limits, metrics, rule and the SHA-256 of every frozen file |
| [`experiment.json`](experiment.json) | Planned convergence record (`scripts/validate_convergence.py`) |
| [`prompt.txt`](prompt.txt) | The batch instruction; `@@FILING_COUNT@@` and `@@FILINGS@@` receive the batch |
| [`response.schema.json`](response.schema.json) | The strict response schema given to `--output-schema` |
| [`run_arm.py`](run_arm.py) | One arm: frozen checks, layout, slot-limited calls, retries, limit stop and resume |
| [`analyze.py`](analyze.py) | Scores, tokens, wall time, paired bootstrap and the recommendation |

Offline checks:
`uv run --no-project --with jsonschema --with pyyaml python -B -m unittest tests.test_gpt6_family_tiering_20260926 -v`.
