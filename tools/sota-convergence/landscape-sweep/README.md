# Landscape sweep harness

This directory runs the landscape-sweep lane of [recipes/saturation-sweep.md](../../../recipes/saturation-sweep.md)
from this repository, on Linux/WSL2 or macOS. Before this harness, the lane ran only from an agent-lab coordinator
session; agent-lab remains an alternative. The lane is a Claude Code Workflow with two model families:

- **Discovery.** Each due layer gets a Claude researcher and a GPT-6 researcher (through the Codex CLI).
- **Refutation.** A facts refuter checks every merged proposal, and two fit refuters, one from each family, judge
  it.
- **Critic.** A completeness critic runs after the first round, followed by at most one bounded follow-up round.

The harness then turns the run into the retained evidence that `scripts/saturation_ledger.py` binds. It never
writes `catalogs/landscape/`, `catalogs/sota-convergence/` or `research-state.json`. Those files, and publishing
the merged manifest, stay with the lane owners.

## Files

| File | Runs | Role |
| --- | --- | --- |
| `build_inputs.py` | checkout | Writes the per-layer inputs the workers read, `<work-dir>/inputs/<layer>.json`, and `layers.json`, from the frozen scope, the landscape catalogs, the ledger's last completed sweep, a baseline manifest, a freshness manifest and optional seeds. |
| `build_args.py` | checkout | Stages a run into the work directory: frozen dated templates, schemas, the GPT-6 runtime, first-round GPT-6 prompts, `staged.json`, `prompts_sha256.txt`, the compact `args.json` and `sweep.embedded.js`. |
| `sweep.js` | Workflow | The lane itself (`const A = args`; its header documents the args object). |
| `codex_call.sh`, `codex_job.py` | staged | The GPT-6 job runner the wrapper agents call (`start`, `wait`, `result`). |
| `make_prompt.py` | staged | Composes a GPT-6 prompt from the frozen templates. |
| `templates.json`, `schemas/` | staged | The prompts, with `<<DATE>>`, `<<LAYER_COUNT>>` and `<<SKILLS_CHECKED_AT>>` open, and the strict return schemas. `probe.json` is for the one-call lane probe. |
| `usage_record.py` | checkout | Runs the vendored `examples/claude-native/workflows/child-usage.mjs` over the run's transcripts and writes the sanitized usage record. |
| `convert.py` | checkout | Converts the run record into `returns.json`, `lanes.json`, `layers.json` and `survivors.json`. |
| `source_reviews.py` | checkout | Writes one upstream-provenance review per survivor (`gh api` only). |
| `make_result.py` | checkout | Assembles `RESULT.json` for `saturation_ledger.py --append`. |
| `sweep_common.py` | checkout | Helpers shared by the checkout-run tools. |
| `seeds-20260926.json` | checkout | The seeds the 2026-09-26 run gave its workers. It is a record, and an example of the `--seeds` format. |

Everything is Python 3.9+ standard library, bash 3.2-compatible shell and node (for `child-usage.mjs` and the
tests). The runner uses no `flock`, `setsid` or `timeout` commands, so it runs unchanged on macOS.

## Model roles

| Label | Model and effort | Role |
| --- | --- | --- |
| `discover:<layer>` | Claude `opus` (claude-opus-5-5 on 2026-09-26), max | Discovery researcher: at most 6 proposals within 12 searches, 8 fetches and 40 GitHub API calls. |
| `gpt6-discover:<layer>` | Claude `sonnet` wrapper, max, running GPT-6-Astra at effort max | Second-family discovery, with the same prompt and the layer input embedded. |
| `refute-facts:<layer>` | Claude `sonnet` (claude-sonnet-5), max | Facts and identity refuter, within 8 searches, 10 fetches and 30 GitHub API calls. |
| `refute-fit:<layer>` | Claude `opus`, max | Fit and standing refuter, with the same budget. |
| `gpt6-refute-fit:<layer>` | Claude `sonnet` wrapper, max, running GPT-6-Astra at effort max | Second-family fit refuter. |
| `critic` | Claude `opus`, max | Completeness critic. It flags at most 8 layers for the follow-up round, whose labels end in `:followup`. |

Survival is two-family on fit. A proposal survives only when the facts refuter, the Claude fit refuter and the
GPT-6 fit refuter all vote not refuted. Every refuter defaults to refuted, and `convert.py` reads a vote the same
way: a missing vote, a vote whose `refuted` is not `false`, and a repository voted on twice with one refuting vote
all count as refuted. When the follow-up round proposes a repository again, that round's proposal and all three of
its votes replace the first round's; a vote missing from the follow-up is never taken from the first round.

Why the roles are split this way:

- Judgment-heavy roles (discovery, fit, completeness) run on the strongest model of each family.
- The facts role runs on Sonnet, because facts can be checked against primary sources (`gh api`, release pages).
- The GPT-6 lanes add a second family to discovery and to the fit judgment, where single-family bias matters most.

This split is the design of the 2026-09-26 prototype. No measured comparison has tested it.

Every `agent()` call names its model and `effort: 'max'`, so no stage inherits the coordinator's `xhigh`
([max-effort decision](../../../docs/decisions/2026-09-23-max-effort-default.md)). The vote objects in
`returns.json` name the model and effort each Claude refuter was measured at (its own child in the usage record),
not the requested ones. Without `--usage`, `convert.py` writes the requested alias and effort `null`.
`usage_record.py` exits 1 when a child ran at another effort (`CLAUDE_CODE_EFFORT_LEVEL` would override every
child), and `make_result.py` refuses such a record.

The Sonnet wrappers only run three commands and return the raw result. `convert.py` checks each copy against the
file Codex wrote.

GPT-6 always runs at effort max, never ultra. Ultra lets Codex delegate to sub-agents, which breaks the one-model
lane. The GPT-6 model is a per-run choice (`build_args.py --gpt6-model`, default `gpt-6-astra`). It is recorded in
`staged.json`, in each job directory and in every GPT-6 vote.

The templates tell each role which pinned skills to use (search-first and iterative-retrieval for discovery;
verification-before-completion, supply-chain-risk-auditor and fp-check for refutation, plus layer-specific skills).
Each worker reports the skills it used in `skills_used`, and `returns.json` totals them in `skills_usage`.

`build_args.py` refuses to stage a run when the templates name a skill that `adoption/skills/manifest.json` does not
pin as kept or trial. The same check also refuses a pinned skill that the templates name but `TEMPLATE_SKILLS` omits.

The GPT-6 lanes run with `--ignore-user-config`, so per-skill `enabled = false` entries in a host's Codex
`config.toml` do not apply there. Which skills Codex lists inside the lane is untested; `skills_used` records what
each worker says it used.

## Evidence contract

`saturation_ledger.py --check` and `--append` need the following. Each item names the part of the harness that
provides it.

- **Labels.** A completed sweep needs a completed `discover:<layer>` child for every recorded layer, and completed
  `refute-facts:<layer>` and `refute-fit:<layer>` children for every layer with proposals (prefix match, so
  `:followup` children count too). `sweep.js` uses exactly these labels. The `gpt6-*` wrappers and `critic` are
  extra children.
- **Usage.** The usage record is `child-usage.mjs` output wrapped as `{schema_version, measurement, child_usage}`.
  For a completed sweep, `child_usage.status` must be `complete`. `workflow_run` must equal the last segment of
  `child_usage.transcript_dir`, which `usage_record.py` rewrites to
  `<session-transcripts>/subagents/workflows/<run id>`. `lost_workers` must list exactly the incomplete children.
  `make_result.py` also needs `measurement.exit_code` 0 and every child measured at effort `max` alone.
- **Failures.** A failed part of the lane never leaves a clean layer. `convert.py` lists each layer's retained
  failures under `failures/<layer>` in `returns.json`: a lost round, a discovery family that did not return, a
  missing vote, a lost critic, a critic-flagged layer beyond the follow-up cap, and a GPT-6 copy problem. It gives
  that layer the reopen entry `{"trigger": "retained_failure", "ref": "<returns_ref>#/failures/<layer>"}`, which
  resets the layer's clean count. `make_result.py` refuses a layer whose failures lack that entry.
- **Returns.** In `returns.json`:
  - `discovery/<layer>` holds `{catalog, layer_id, proposed[], requirement_sha256, platform_profiles_sha256}`,
    with the two hashes copied from the scope frozen before the run.
  - `votes/<layer>/<i>/facts` and `.../fit` hold `{role, repository, refuted, ...}`. The fit object is the
    two-family vote, and its `claude` and `gpt6` members keep each family's vote.
  - Each layer's `discovery_ref` and every vote `ref` in the record is `<returns_ref>#/json/pointer`.
    `convert.py` writes them as `@RETURNS@#/...` and `make_result.py` fills in the path.
  - `proposed` must equal the set of adjudicated repositories, and every proposal gets both votes.
- **`prompts_sha256`.** This is `sha256(json.dumps(T, sort_keys=True, ensure_ascii=False))` of the run's frozen,
  dated templates. `build_args.py` writes it to `prompts_sha256.txt`. With the 2026-09-26 values filled in, the
  templates here give `3adfbed7…18d4` (tested), the value computed on 2026-09-26 from that run's staged
  `templates.json`. That is a local check; the run's registered record is the evidence of what it used.
- **Manifest.** `manifest_ref` is the dated SOTA manifest built from `lanes.json`. The record's `date` is its
  `checked_at`, and the manifest's rows for this lane must equal each layer's proposals and survival.
- **Source reviews.** Each survivor needs one registered source review whose `layers` names the layer.
  `source_reviews.py` names a review `<owner>-<repo>.json`, as the 2026-09-23 reviews are named. When two survivors
  share that name (`acme/a-b` and `acme-a/b`), each gets a suffix of 10 hex characters of the sha256 of its
  `owner/repo`. A file that already reviews another repository is never overwritten.
- **Registration.** Every cited file is registered in `manifests/evidence.json`.

## Run it

The prerequisites are a Claude Code coordinator session with the Workflow tool (this repository's
`.claude/settings.json` turns Ultracode on), `gh` signed in, `codex` on PATH signed in natively, node, and python3.

The work directory `W` holds prompts, host paths and raw Codex output, so it must sit outside every git repository.
Every tool here refuses a work directory inside one; Codex would also load that repository's `AGENTS.md` into the
lane. Commands run from this checkout.

```sh
H=tools/sota-convergence/landscape-sweep
W=/path/outside/every/repository/landscape-sweep-20261026
DATE=2026-10-26; STAMP=20261026; LANE=landscape-sweep-$STAMP
mkdir -p "$W/work" "$W/freshness"

# 1. Scope (no network): check the ledger, list the due layers, freeze the scope hashes.
python3 scripts/saturation_ledger.py --check
python3 scripts/receipt_staleness.py --json --out "$W/receipt-staleness.json" > /dev/null
python3 scripts/saturation_ledger.py --report --json --staleness "$W/receipt-staleness.json" > "$W/report.json"
python3 scripts/saturation_ledger.py --scope > "$W/scope.json"

# 2. Working files and pin freshness (network; gh signed in). Or download the latest catalog-freshness
#    artifact instead: gh run download <run-id> -n catalog-freshness-<run-id> -D "$W/freshness"
python3 tools/sota-convergence/extract_layers.py --repo-root . --out "$W/work"
python3 tools/sota-convergence/github_freshness.py --work-dir "$W/work" --workers 6
printf '{"lanes": [], "critic": null, "lost": []}\n' > "$W/freshness/lanes.json"
python3 tools/sota-convergence/build_manifest.py --work-dir "$W/work" --lanes "$W/freshness/lanes.json" \
  --out "$W/freshness/manifest-$STAMP.json" --checked-at "$DATE" --id "catalog-freshness-$STAMP"

# 3. Layer inputs (no network). --seeds is optional: {"<layer_id>": ["candidate or note", ...]}.
python3 $H/build_inputs.py --work-dir "$W" --freshness-manifest "$W/freshness/manifest-$STAMP.json"

# 4. Stage a one-layer smoke run and probe the GPT-6 lane with one cheap call.
python3 $H/build_args.py --work-dir "$W" --sweep-id "$LANE" --date "$DATE" --smoke mcp-surfaces
bash "$W/codex_call.sh" start gpt6-probe "$W/prompts/gpt6-probe.txt" "$W/schemas/probe.json"
bash "$W/codex_call.sh" wait gpt6-probe 600; bash "$W/codex_call.sh" result gpt6-probe   # expect exit 0, limit false
```

**5. Smoke.** In the coordinator session, call `Workflow({scriptPath: "<W>/sweep.embedded.js"})` with no `args`.
Then run steps 7 and 8 below on the smoke run into a scratch output directory, and check the summary: GPT-6
statuses `ok`, `gpt6_copy_check` `match`, `skills_usage` present. Archive the smoke before the full run:
`mkdir -p "$W/attempts/smoke" && mv "$W/gpt6" "$W/prompts" "$W/attempts/smoke/"`. `build_args.py` refuses to
restage while `gpt6/` holds jobs, because a finished job with the same id would be reused.

**6. Full run.** Stage the due layers, then call `Workflow({scriptPath: "<W>/sweep.embedded.js"})` again:

```sh
python3 $H/build_args.py --work-dir "$W" --sweep-id "$LANE" --date "$DATE" --due-report "$W/report.json"
```

The embedded copy carries the ~12 KB of templates and schemas, so they never pass through the coordinator's
context, and a resume needs only `Workflow({scriptPath, resumeFromRunId})`. Launching `sweep.js` with the contents
of `args.json` as `args` works too, at that context cost.

After the run, set `T` to the transcript directory the Workflow tool prints (`.../subagents/workflows/<run id>`)
and `RUN` to the run id. Copy the run record without reading it into context. It is large: the one-layer smoke
returned about 130 KB.

```sh
cp "${T%/subagents/workflows/*}/workflows/$RUN.json" "$W/run-$RUN.json"
```

Claude Code keeps the record there, as `tools/sota-convergence/transcript_audit.py` also documents.

```sh
# 7. Usage (needs node): the vendored child-usage.mjs over the run's transcripts, sanitized.
#    Exit 1: incomplete usage or a child not at effort max. The record is still written; make_result.py refuses it.
python3 $H/usage_record.py --transcript-dir "$T" --out "$W/child-usage-$RUN.json"

# 8. Convert. Exit 3: possible private content, redact first. Exit 4: a GPT-6 output the workflow used is not
#    exactly the file Codex wrote, or a finished Codex output never reached the workflow (see the summary).
python3 $H/convert.py --workflow-output "$W/run-$RUN.json" --work-dir "$W" --usage "$W/child-usage-$RUN.json" \
  --out "$W/out" --limit "<run-specific note, e.g. usage figures or incidents>"

# 9. Merge the lane into the dated manifest: step 4 of recipes/sota-convergence-practice.md's six commands.
#    Review and publication (steps 5-6) stay with the lane owners.
python3 tools/sota-convergence/build_manifest.py --work-dir "$W/work" --lanes "$W/out/lanes.json" \
  --out "$W/manifest-$STAMP.json" --checked-at "$DATE" --id "sota-convergence-$STAMP"

# 10. Source reviews, written straight into the lane's evidence directory.
A=evidence/artifacts/$LANE
python3 $H/source_reviews.py --survivors "$W/out/survivors.json" --out "$A" --lane "$LANE" > "$W/out/reviews.json"

# 11. Retain and register (after the manifest is published at catalogs/sota-convergence/manifest-$STAMP.json).
mkdir -p "$A-attempts"
cp "$W/out/returns.json" "$A/returns.json"; cp "$W/child-usage-$RUN.json" "$A-attempts/"
python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, "scripts"); import host_receipts
for p in sys.argv[1:]: host_receipts.register_file(Path("."), p)' "$A"/*.json "$A-attempts"/*.json \
  "catalogs/sota-convergence/manifest-$STAMP.json"
python3 scripts/validate.py

# 12. Record: RESULT.json, append, check.
python3 $H/make_result.py --layers "$W/out/layers.json" --reviews "$W/out/reviews.json" --sweep-id "$LANE" \
  --returns-ref "$A/returns.json" --usage-ref "$A-attempts/child-usage-$RUN.json" \
  --manifest-ref "catalogs/sota-convergence/manifest-$STAMP.json" --work-dir "$W" > "$W/RESULT.json"
python3 scripts/saturation_ledger.py --append "$W/RESULT.json"
python3 scripts/saturation_ledger.py --check --base origin/main
python3 -m unittest tests.test_saturation_ledger tests.test_landscape_sweep_harness
```

`make_result.py` takes `--reopen reopen.json` (`{"<layer_id>": [{"trigger", "ref"}]}`) for the other reopen entries
the recipe asks for, such as the report's current `pin_moved` or `stale_receipt` triggers. Add them after reading
the report and the run; they are added to the `retained_failure` entries `convert.py` wrote, never in their place.
Record a stopped run by hand, as recipe section 4 describes (`status: stopped`, `lower_bound_usage: true`,
`votes: not_returned`, `lost_workers`). Retain the smoke's usage record under `$A-attempts/` as a run of its own.

Read these fields of `convert.py`'s summary before appending:

- **`retained_failures`** and **`reopened_layers`**: each layer's failures (`<round>:<cause>`), all of them reopened.
  `degraded_discovery`, `critic_lost` and each vote's `notes` give the detail.
- **`excluded_layers`**: every round of the layer was lost. Such a layer is left out of the record, so it neither
  counts nor resets.
- **`lost`**: every lost round, first or follow-up, as `<layer>:<round>`. `sweep.js` returns a lost follow-up round
  as `{lost: true}` too. `convert.py` refuses a return whose follow-up rounds do not match the critic's requests,
  so no round can go missing silently.

## Cost reference

No measured cost is quoted here. The 2026-09-26 one-layer smoke (run `wf_1753e674-5dc`, prototype harness) was
read only from that session's files, and a figure without a retained record is not evidence. Each run's own record
is its cost reference:

- `child-usage-<run>.json` (`usage_record.py`) for the Claude workers;
- `returns.json` `gpt6_usage` for GPT-6: `usage` sums the final attempt of each job and `earlier_attempts` the
  attempts the runner kept, with `usage_unavailable` counting attempts that reported none. Complete GPT-6 usage is
  the per-counter sum of the two.

Each counter is its own kind, so Claude and GPT-6 counters are never summed together. A full sweep has up to one
round per due layer, plus at most 8 follow-up rounds and a critic; the recipe classes the lane as high cost. Plan a
new run from the latest retained record, and say so when no record exists yet.

## Coordination

- **Codex quota.** The Codex account and its quota are shared with every session and host signed in to it. The
  semaphore (3 slots by default, `--slots`) bounds only the jobs of runs that share its lock directory. That
  directory is `<W>/locks` by default; pass the same `--lock-dir` to sweeps that run at the same time. Interactive
  Codex use and reviews are not counted, so check with the other sessions before a full run, and lower `--slots`
  while they are busy.
- **Agent concurrency.** `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS` bounds the Workflow's agents (this host
  starts at 8), and a layer uses up to three agents at a time. A GPT-6 wrapper waits at most 8 × 540 s for its job
  and then returns the job as unfinished. The vote then counts as missing and the layer is reopened, and a job that
  finishes later makes `convert.py` exit 4 (`file_only`). Keep the number of queued GPT-6 jobs small relative to the
  slots.
- **Usage limit.** A real Codex usage-limit error writes `<W>/LIMIT`. After that no job starts, and jobs still
  waiting for a slot end with exit 3. Stop the Workflow and tell the user the reset time, which the job's
  `stderr.txt` or its `error` event gives. Do not sign in again (provider state is shared). Record the stopped run
  as the recipe says. Remove `LIMIT` only after the reset. A failed job runs again at its next `start`; its failed
  attempt moves unchanged to `gpt6/<job>/attempts/<n>/` and stays in `result` and `gpt6_usage`. A finished job
  returns "already done" only for the same inputs (prompt and schema sha256, model, effort), so a resumed Workflow
  whose regenerated prompt differs gets a fresh GPT-6 vote, never a cached one for another claim.
- **Resume.** `Workflow({scriptPath: "<W>/sweep.embedded.js", resumeFromRunId: "wf_..."})` replays the unchanged
  agent calls from the cache.

## Privacy and token practice

- **Work directory.** Keep `W` private and never commit it. Codex thread ids, raw events, prompts with host paths
  and the run record stay there.
- **`convert.py`.** Rewrites work-directory, checkout and home paths to `<work-dir>`, `<repo>` and `~`. It then
  scans every output string with `scripts/validate.py`'s `PRIVATE_CONTENT` patterns and reports each match by
  pointer and kind, never its text, with exit 3.
- **`usage_record.py`.** Rewrites the transcript path to `<session-transcripts>/...` and refuses to write a record
  that still matches one of those patterns.
- **Token practice.**
  - Claude workers read the layer inputs from files; only the GPT-6 prompts embed them.
  - The Workflow args hold only templates, schemas and layer ids, and the embedded copy keeps even those out of
    the coordinator's context.
  - GPT-6 outputs are returned compact, and merged rows no longer repeat each family's full proposal.
  - Read a run through `convert.py`'s summary, not the record.

## Differences from the 2026-09-26 prototype

Parity with the prototype is not established by this package. On 2026-09-26 three unretained local checks were
run (prompt bytes, the smoke's conversion, `usage_record.py` on the smoke's transcripts); their outputs are not
kept, so they are not evidence. `PROMPTS_SHA256_20260926` in the tests is the value this package computes from its
templates, and it matches the 2026-09-26 run only if that run's retained record carries the same
`prompts_sha256`. Treat parity as unverified until that record is registered and compared.

The deliberate changes:

- **Parameterized paths and dates.** No path is hardcoded; every tool takes `--work-dir` or `SWEEP_WORK_DIR`, and
  the staged runtime uses its own directory. The date, layer count and skills-manifest date are template
  placeholders.
- **Portable runner.** The runner is portable (stdlib locks, sessions and timeout).
- **Usage-limit detection.** The runner reads Codex's `error` and `turn.failed` JSONL events. `codex exec
  --json` prints fatal errors on stdout, so the prototype's stderr-only check could miss a real limit; see
  openai/codex `rust-v0.155.1`, `codex-rs/exec/src/exec_events.rs`. Model content never counts. Codex runs without
  the caller's `RUST_LOG` (at trace level it logs model response data, `codex-rs/codex-api/src/sse/responses.rs`),
  and a stderr line counts only when it is an `ERROR`/`Error` line and no turn completed.
- **Job reruns.** A failed job reruns with its earlier attempt kept under `attempts/<n>/`; a done job is reused only
  for the same inputs; a running one is never started twice.
- **Timeout cleanup.** On timeout the job's whole process group gets TERM, then KILL after the grace period
  (`kill_grace_s`, 10 s), even when Codex itself has already exited, so no child keeps a slot or job lock.
- **Layer inputs.**
  - The fields have undated names (`previous_sweep`, `components_vs_upstream`, `seeded_candidates`,
    `upstream_checked_at`).
  - Trading pins are included.
  - Known-repository slugs are no longer cut by `rstrip(".git")`, which had shortened, for example, `qdrant/qdrant`
    to `qdrant/qdran` in 30 of 32 layers.
  - The previous sweep is the last completed one.
- **Placeholder filling.** Placeholders are filled in one pass, with no `$&` expansion. Merged rows drop
  `by_family`.
- **`convert.py` additions.**
  - A lost layer is excluded instead of being recorded as an empty retained layer.
  - Degraded discovery is reported.
  - Votes carry resolved model names from the usage record and per-round skills.
  - It adds `gpt6_usage`, the wrapper copy check and the method's lane limits.
- **Review repairs (2026-09-26).** A Claude Opus and GPT-6-Astra review of the first package found these, each now
  covered by a test:
  - A layer with a failed lane (every GPT-6 fit job failed, say) derived as clean. Retained failures now reopen it.
  - A repository proposed again in the follow-up kept its first-round proposal but took later votes one by one.
    The later round's proposal and all three of its votes now travel together.
  - A lost follow-up round vanished. `sweep.js` now keeps it as `{lost: true}`, and the critic's repeated layers
    get one round.
  - Vote efforts were written as max whatever was measured, and effort drift passed `usage_record.py`.
  - Wrapper commands did not quote the work directory. Every argument and redirection target is now
    POSIX-quoted.
  - `canon()` left owners whose names start with `http` (`httpie/cli`) uncanonical.
  - Two repositories could share one source-review file.
  - `make_result.py --reopen` replaced a layer's reopen entries instead of adding to them.

## Tests

```sh
python3 -m unittest tests.test_landscape_sweep_harness -v
```

The suite uses synthetic fixtures and makes no network or model calls:

- A fake `codex` and a fake `gh` sit early on PATH.
- `sweep.js` runs under node with stubbed `agent`, `parallel` and `pipeline`.
- The converted evidence is appended to a synthetic ledger checkout with `saturation_ledger.py` itself.

Node, `shellcheck` and `BASH32_BINARY` (a real bash 3.2, as on macOS) are optional; each test that needs one is
skipped without it.
