# GPT-6 family tiering for a mechanical extraction stage: frozen preregistration

Frozen on 2026-09-26, before any call to the provider, and amended the same day
after one review round, still before any call. This change adds the plan, the
scripts, a loopback probe of the Codex command and offline tests only. No arm
has run, and nothing here is a measurement of any GPT-6 model.

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
decision rule is frozen in [`plan.json`](plan.json), and `analyze.py` refuses to
run when any frozen script or scorer has changed, so no arm can be chosen after
the fact.

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
  -c model_reasoning_effort="<effort>" \
  -c agents.enabled=false -c web_search="disabled" -c features.shell_tool=false \
  -c features.unified_exec=false -c features.view_image=false -c features.goals=false \
  -c features.sleep_tool=false -c features.hooks=false -c features.plugins=false \
  -c features.apps=false -c features.unbounded_connection_retries=false \
  -c cli_auth_credentials_store="file" \
  --output-schema <schema> -o <reply> --json "<prompt>" </dev/null
```

### Why the overrides

The first version of this plan froze the command without the `-c` overrides.
Review showed that this command still offers the model a web search, a shell
and sub-agents. The [isolation probe](isolation-probe/probe.py) confirmed it on
2026-09-26. The probe runs `codex-cli 0.157.1` against a loopback fake Responses
provider inside a private network namespace, with no credential. Its results
are in [`isolation-probe/results.json`](isolation-probe/results.json).

- **The command without overrides.** The first request offered code mode's
  `exec` and `wait`, `request_user_input`, `clock.sleep` and six
  `collaboration` tools, including `spawn_agent`. A scripted `web.run` call sent
  a search request. A code-mode cell ran `exec_command pwd`: that is a shell.
- **With the overrides.** For `gpt-6-astra`, `gpt-6-sol` and `gpt-6-luna` alike,
  only `exec`, `wait` and `request_user_input` remain. Code mode's nested tools
  shrink to `apply_patch`, which the read-only sandbox refuses, and
  `clock__curr_time`. Web search and `spawn_agent` are refused as unsupported
  calls.
- **`agents.enabled=false`, not `features.multi_agent=false`.** The model
  catalog turns the sub-agent tools on before the `multi_agent` feature is
  consulted (`codex-rs/core/src/config/mod.rs` at the pinned commit). With
  `features.multi_agent=false` alone, the probe still saw all six
  `collaboration` tools; `agents.enabled=false` removes them.
- **An unreachable provider.** Without the overrides, Codex kept printing
  "Reconnecting... waiting for network" until the probe's 60 s timeout. With
  `unbounded_connection_retries` off, the call failed in under a second. An
  outage now fails a call instead of hanging it until the 3,000 s timeout.

The prompt asks for no tool. Any tool call still fails the call, so no reply
produced with a tool is ever scored (see Calls below).

### Where each call runs

- **Codex home.** Each call gets its own `CODEX_HOME` inside its private
  attempt directory. It holds only a symlink to the native `auth.json`, which is
  never read or copied. `--ignore-user-config` does not skip
  `$CODEX_HOME/AGENTS.md` or the user's skills, so a fresh home keeps the host's
  global instructions, skills, hooks and earlier sessions out of every call. It
  also keeps Codex's own session record for the call private. Codex's file
  credential store writes a refreshed token in place through the link. The link
  is removed after the call.
- **Scratch directory.** `HOME`, `TMPDIR` and the working directory are one
  empty scratch directory in the system temporary directory. It lies outside
  the state tree and every repository, and it is removed after the call. With
  no `.git` above it, Codex reads project `AGENTS.md` files from that empty
  directory only.
- **Environment.** Only an allowlist passes: `PATH`, locale, `TERM`,
  certificate and proxy variables. No API key and no `RUST_LOG` reach Codex.
- **System configuration.** A run refuses to start while `/etc/codex/config.toml`,
  `requirements.toml` or `managed_config.toml` exists, because
  `--ignore-user-config` does not skip those layers.

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

## Calls, slots, retries and stops

[`run_arm.py`](run_arm.py) runs one arm with one call per batch.

**Concurrency.** At most **3** calls run at once. Before its call, each worker
takes a free slot lock (`slot-1` to `slot-3`, `fcntl.flock`) in the host's
shared Codex lock directory, given as `--lock-dir`. The landscape-sweep runner
takes the same locks, so all Codex jobs on the host together stay within its
three-slot pool. The lock directory is never created, so a mistyped path cannot
start a private pool. codex inherits the slot lock and the arm's run lock, so a
killed runner frees neither while its codex still runs.

**Launch gate.** A worker checks for a stop note and starts its call while
holding a state-wide lock, `launch.lock`. Every stop note is written under the
same lock, so once a note exists, no call of any arm starts. A worker releases
its slot only after its call is recorded and any stop note is published.

**Per call.** The runner records:

- exit code, wall time, launch time, slot and slot wait;
- the summed `turn.completed` usage (input, cached input, cache-write input,
  output and reasoning output tokens);
- the reply's JSON validity;
- the item types in Codex's session record and in the `--json` stream;
- what happened to the credential link and the scratch directory.

**Outcomes.** Only `failed` uses a batch's single retry.

| Outcome | When | What follows |
|---|---|---|
| `ok` | A completed turn, exit 0, no tool item, and a reply that is the response envelope. | The batch is complete. |
| `failed` | The model ran, but the call timed out (3,000 s), used a tool (`tool_use`), exited non-zero or failed its turn, or left no valid reply. | The batch runs once more. A batch that fails twice is final, and its filings stay in every denominator as invalid. |
| `limit` | Codex's own `error` or `turn.failed` event says "hit your usage limit". Model content and stderr never count. | `LIMIT` is published at once, while the call still runs. Running calls finish, and the run exits **3**. |
| `unavailable` | No completed turn without a limit event (network, sign-in, a rate limit, a server error, a failed launch). Or a completed turn whose session record is missing or holds an item type the plan does not know. | `UNAVAILABLE` is published, and the run exits **4**. |
| `interrupted` | SIGINT or SIGTERM. The call's process group gets TERM, then KILL after 10 s. | The run exits **5**. |
| `abandoned` | A runner died before recording the call. The arm's next run records it and removes its credential link. | The batch runs again. If the call's events show the usage limit, it is a `limit` call, and the next run publishes `LIMIT` before any call. |

A `limit`, `unavailable`, `interrupted` or `abandoned` call never uses the
batch's retry. Its batch runs again in a later run. While `LIMIT` or
`UNAVAILABLE` exists, every run of every arm exits 3 or 4 without a call.

**Codex's session record.** Tool use is judged from the session record in the
call's `CODEX_HOME`, not only from the `--json` stream. The stream does not show
code mode's `exec` cells, while the session record lists every one (probe cases
`committed-code-mode` and `isolated-code-mode`).

**Refusals.** Before any call, a run refuses (exit 2):

- a changed frozen hash, plan value, input or layout;
- a Codex version other than `codex-cli 0.157.1`;
- a system Codex configuration file;
- a missing native sign-in file;
- a state directory that is not owner-only, or a temporary directory inside it
  or inside a repository;
- a run already in progress;
- a later run whose plan, prompt, schema, inputs, layout or Codex version
  differs from the arm's first run.

**Exits.** Exit **0** means the arm has no pending and no failed batch. Exit
**6** means it has no pending batch, but a batch failed twice. Exit 6 is final
for that arm, and the failure reasons deserve a look before the next arm
starts.

## Metrics and decision rule

[`analyze.py`](analyze.py) first verifies every frozen file against
`plan.json`: both scripts, the prompt, the schema, and li26's reused scorers.
It then reads every attempt of every batch, so no call can be left out. It
reuses li26's scoring functions unchanged: per-filing counts, micro-F1,
macro-F1 over codes with at least five labelled filings, and the paired
bootstrap. It reports, per arm:

- micro-F1 and macro-F1;
- the JSON-valid rate;
- calls by outcome and reason, and retried, failed and pending batches;
- tokens per filing by kind;
- wall time.

A filing is JSON-valid only when its batch's final reply is exactly the envelope,
its accession has exactly one entry and the entry passes li26's per-filing rule.

**Billed tokens** are uncached input (input minus cached input) plus output.
Codex's `output_tokens` already includes `reasoning_output_tokens`
([`docs/token-practice.md`](../../../docs/token-practice.md)): the task's
"output plus reasoning" is that one number, and adding reasoning again would
count it twice. Cached input and reasoning are reported separately. The means
per filing divide an arm's totals over every call that reported usage by 360.

**Unknown usage.** A call without a usage report counts as zero only after a
failed launch, or when the usage limit refused its turn. Any other call without
a report may have spent tokens Codex never reported: a timeout, or an
unavailable, interrupted or abandoned call. Such a call makes its arm's usage
incomplete, and its reported total becomes a lower bound. Interrupting a run
therefore has a cost.

**Rule.** An arm is routable for mechanical extraction when all three hold:

1. The paired bootstrap (10,000 resamples, seed 20260926) 95% lower bound of
   micro-F1(arm) − micro-F1(A0) is at least −0.02.
2. Its JSON-valid rate is at least 0.98.
3. Every one of its batches completed.

A candidate is recommended only when three things hold: it is routable, its
usage is complete, and its mean billed tokens per filing are **strictly below
A0's**. Among such candidates the cheapest wins. Ties go to the lower median
wall time of ok calls, then to plan order. A tie with A0 keeps the default,
because the question asks for lower cost. Otherwise the default stays, and the
decision names the reason: `no_routable_candidate`,
`no_candidate_with_known_usage` or `no_candidate_below_control`.

If A0's usage is incomplete, its reported cost is a lower bound. A candidate
below that bound is still certainly cheaper, so it is still recommended.
Otherwise the result is `inconclusive_control_usage_incomplete`. The result is
also inconclusive, and nothing changes, when:

- A0 has not run, is incomplete, has a failed batch or an inconsistent record,
  or is below 0.98 JSON-valid;
- any call reports cached input above input, or reasoning above output.

The decision file marks `final: true` only when all six arms are complete, and
it records the frozen map it verified.

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

   The loop stops on any non-zero exit:

   - **3.** The shared usage limit was reached. Tell the user and wait for the
     reset. Then remove `LIMIT` from the state directory and run the loop again
     from the same arm.
   - **4.** Codex was unavailable, or a call could not be checked. Read the
     attempt that `UNAVAILABLE` names (its `stderr.txt`, `events.jsonl` and
     `call.json`) and fix the cause. An item type the plan does not know needs
     a plan amendment. Then remove the note and run the loop again from the
     same arm.
   - **6.** The arm is finished, but a batch failed twice. Read the failure
     reasons, then start the loop again from the next arm. Rerunning the same
     arm only prints 6 again, without a call.

   Finished batches are always kept.

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

To repeat the isolation probe (no provider, no credential), copy `probe.py` and
`fake_tool_calls.py` into an empty work directory. Run the command in
`probe.py`'s docstring, which uses `bwrap --unshare-net`, with the pinned codex.

## Evidence classes

- **This change.** Offline artifact checks only:
  - frozen hashes;
  - the validated planned record;
  - [the tests](../../../tests/test_gpt6_family_tiering_20260926.py). They use a
    fake `codex` that prints scripted `--json` events and writes a scripted
    session record. They are local integration checks on synthetic fixtures,
    not upstream tests, and no test reaches the provider.
- **The isolation probe.** A local loopback run of the pinned CLI against a
  scripted fake provider, inside a network namespace. It shows which tools Codex
  offers and how it handles calls. It says nothing about how the hosted models
  behave.
- **Upstream source reads.** The pinned `openai/codex` files named in
  `plan.json`: feature flags, sub-agent gating, `AGENTS.md` discovery, the file
  credential store and the config layers. They are source reading, not
  execution.
- **Planning reads.** `codex debug models --bundled` shows the catalog shipped in
  the binary; it is not the provider's live catalog. The layout aggregates come
  from the verified private inputs, and only aggregates were recorded.
- **The later run.** Native execution of hosted models on this host through the
  native sign-in, one run per arm. Its token counts are Codex's own counters. Its
  wall times are shared-host, shared-account observations.

## Privacy boundary

- Everything a run writes stays under
  `~/.local/state/native-agent-stack/gpt6-family-tiering-20260926/`, with 0700
  directories and 0600 files: Codex events, stderr, replies and per-call
  records.
- Each call's Codex home, with Codex's own session record, logs and state for
  that call, lives in the call's attempt directory. Its link to the native
  sign-in exists only while the call runs.
- The scratch `HOME`, `TMPDIR` and working directory are removed after the call.
  The call record counts anything Codex left there.
- The decision file holds aggregates only: no filing text, reply text or
  accession numbers. Registering results as receipts is a later change.

## What this does not claim

No result exists yet. When results exist, they will not establish:

- general or cross-task quality, or frontier parity;
- accuracy against hand-checked labels;
- any stage other than mechanical extraction with a deterministic scorer, or a
  stage that lets the model use tools;
- provider cost in money, or a quota share attributable to one arm;
- tokens Codex never reported;
- whole-task token savings;
- stability over time, other days, other batch sizes, other Codex versions or
  later provider behaviour. There is one run per arm on one day, and Codex exec
  exposes no temperature or seed.

`gpt-6-sol` and `gpt-6-luna` run at their catalog default `priority` tier, and
`gpt-6-astra` at its default. Wall time only breaks ties.

## Files

| File | Role |
|---|---|
| [`plan.json`](plan.json) | Frozen arms, command and overrides, catalog observation, batching and layout hash, call handling, metrics, rule, the amendment record and the SHA-256 of every frozen file |
| [`experiment.json`](experiment.json) | Planned convergence record (`scripts/validate_convergence.py`) |
| [`prompt.txt`](prompt.txt) | The batch instruction; `@@FILING_COUNT@@` and `@@FILINGS@@` receive the batch |
| [`response.schema.json`](response.schema.json) | The strict response schema given to `--output-schema` |
| [`run_arm.py`](run_arm.py) | One arm: frozen checks, layout, per-call isolation, slot-limited calls through the launch gate, retries, stop notes and resume |
| [`analyze.py`](analyze.py) | Frozen-code check, scores, tokens, wall time, paired bootstrap and the recommendation |
| [`isolation-probe/`](isolation-probe/) | The loopback probe of the command's tool surface: `probe.py`, its fake provider and `results.json` |

Offline checks:
`uv run --no-project --with jsonschema --with pyyaml python -B -m unittest tests.test_gpt6_family_tiering_20260926 -v`.
