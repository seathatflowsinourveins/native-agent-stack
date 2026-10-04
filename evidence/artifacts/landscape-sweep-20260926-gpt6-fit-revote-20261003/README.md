# GPT-6 fit re-vote of the 2026-09-26 landscape sweep (run 2026-10-03)

- **Label:** `landscape-sweep-20260926-gpt6-fit-revote-20261003`, the `sweep_id` staged in both lanes.
- **Workflow run:** `wf_555874dd-5a7`. The earlier launch, `wf_8066ceb5-b9a`, is kept as a failed attempt.
  [Its retained usage record](child-usage-wf_8066ceb5-b9a.json) reports `child_usage.status: incomplete`, one Opus
  planner, 64 requests, 71 tool calls and the issue "no result entry in journal". Its counters are `input_tokens`
  130, `output_tokens` 62,672, `cache_read_input_tokens` 11,564,262 and `cache_creation_input_tokens` 305,171.
- **Evidence class:** returned GPT-6 votes. Per the workflow script, Claude Sonnet command wrappers (`run:<layer>`,
  effort max) started and relayed the jobs: they ran `codex_call.sh` start, wait and result and made no judgment.
  Opus agents planned, criticized and recorded the run. No Claude vote enters the tabulation; the facts and Claude
  fit votes are the sealed 2026-09-26 votes.
- **Sealed record unchanged:** `../landscape-sweep-20260926/`, its ledger record, `manifest-20260926.json` and the
  layer-verdict wave files are byte-unchanged against `origin/main`.

## What was re-voted

The 2026-09-26 sweep's `returns.json` holds 71 fit votes whose `gpt6` member is `{missing: true}`: the first-round
GPT-6 fit jobs of nine layers never returned. In 27 of them the facts vote and the Claude fit vote are both not
refuted, so the missing vote alone refutes them (`convert.py` lines 562-567; `catalogs/saturation/ledger.json` line
2847, "refuted by absence, not on merit"). `scripts/saturation_ledger.py` `refuted_by_absence` gives the same 27.
They are 26 repositories, because openai/codex is decisive in `workers/0` and `web-research/3`. The Record brief and
the workflow's description said 28; the count is 27.

Each layer's job ran the first-round GPT-6 fit prompt again over the same proposals. The prompt was composed from the
frozen 2026-09-26 templates, the original layer inputs (`../landscape-sweep-20260926/inputs/`) and the proposals as
the run's GPT-6 wrappers received them (`props/`). `provenance.json` binds every hash and gives the regeneration
recipe. This stage re-ran that recipe at 2026-10-03T09:59:23Z: it reproduced the templates hash (`12fc198d…`,
prompts_sha256 `3adfbed7…`) and all nine prompt hashes. The staging checks recorded there are kept as found: the
prompt hash of the 2026-09-26 ad-hoc re-vote differs for instructions-skills and code-navigation, and the in-run
wrapper prompt for workers had 240 lines against 239 here. This record does not resolve those differences.

## Method

1. **Completion gate.** At 09:46:10Z this stage ran `codex_call.sh --work-dir <lane> result gpt6-fit-<layer>` for the
   nine native jobs, `result gpt6-fit-<layer>-omni` in the OmniRoute lane and `result gpt6-probe`, and saved each JSON
   line unchanged in the private work directory, which is not published. `jobs.json` keeps every field of each line as
   `result` except two. `output_text` is replaced by `output`, the parsed `last.json` of a counted job (equal to the
   parsed `output_text`), and `output_sha256`, the sha256 of the `last.json` bytes; the never-started OmniRoute jobs
   have a null `output_text` and neither field. `stderr_tail` is not retained; `stderr` summarizes it. A review-round
   check at 2026-10-03T16:48:45Z re-serialized each `output` as compact JSON (`separators=(",", ":")`,
   `ensure_ascii=False`) and reproduced all ten counted lines' `output_text` byte for byte. A job counts only when its
   status is done, its exit is 0 and `last.json` parses. A layer's votes come from its native job when that job counts,
   else from its OmniRoute job.
2. **Votes.** `convert.gpt6_out` and `convert.votes_by_slug` (a refuting vote wins a duplicate) over `last.json`. The
   proposals of `props/<layer>.json` pair in order with the sealed indices whose `fit.gpt6` is missing; the
   `sweep_common.slug` of each pair matched (71 of 71). The new `gpt6` member takes `convert.py`'s fields (lines
   549-551). The rules are the harness's: `convert.is_refuted`, `convert.FIT_RULE` (two-family fit), survival (line
   562) and refuted by absence (lines 562-567).
3. **No license flag.** `tabulation.json` carries no `license_based_refutation` flag: a keyword rule would also mark
   refutations that only mention a license. The license gate is a lane limit (below).

## Result

All nine native jobs counted (status done, exit 0, `last.json` parses; gpt-6-astra, effort and request_effort max,
codex-cli 0.159.3, web_search cached, no earlier attempts, `limit` and `limit_marker` false). No OmniRoute job started:
each native job counted, so the fallback was never needed, and its nine result lines read `not_running`.

| Layer | Started | Finished | Votes | GPT-6 refuted | Decisive | Decisive surviving |
| --- | --- | --- | --- | --- | --- | --- |
| native-clients | 09:06:29Z | 09:17:52Z | 8 | 6 | 1 | 1 |
| instructions-skills | 09:29:19Z | 09:41:59Z | 8 | 5 | 1 | 0 |
| workers | 09:17:54Z | 09:29:54Z | 8 | 3 | 2 | 2 |
| isolation | 09:06:34Z | 09:18:43Z | 8 | 4 | 2 | 1 |
| code-navigation | 09:18:44Z | 09:29:15Z | 8 | 1 | 2 | 2 |
| document-retrieval | 09:29:55Z | 09:40:00Z | 7 | 5 | 5 | 2 |
| semantic-rag | 09:14:41Z | 09:25:31Z | 8 | 2 | 5 | 4 |
| durable-memory | 09:06:33Z | 09:14:40Z | 8 | 2 | 5 | 4 |
| web-research | 09:25:31Z | 09:35:58Z | 8 | 5 | 4 | 3 |

All 71 GPT-6 votes returned; 33 refute. The 27 decisive proposals, before and after (before, every one was refuted by
absence; the OmniRoute column is empty because no OmniRoute job started):

| Sealed pointer | Repository | Proposed label | Native GPT-6 fit | After (V1) | landscape-sweep-20260929 |
| --- | --- | --- | --- | --- | --- |
| native-clients/2 | earendil-works/pi | not_adopted | upheld 0.88 | survives | refuted on fit (GPT-6) |
| instructions-skills/0 | mattpocock/skills | targeted_candidate | refuted 0.94 | refuted on merit | survived |
| workers/0 | openai/codex | targeted_candidate | upheld 0.83 | survives | survived |
| workers/3 | sipyourdrink-ltd/bernstein | keep_but_compare | upheld 0.79 | survives | refuted on fit (Claude) |
| isolation/0 | superradcompany/microsandbox | keep_but_compare | upheld 0.92 | survives | survived |
| isolation/1 | boxlite-ai/boxlite | targeted_candidate | refuted 0.97 | refuted on merit | survived |
| code-navigation/0 | anthropics/claude-plugins-official | targeted_candidate | upheld 0.92 | survives | survived |
| code-navigation/7 | abhigyanpatwari/gitnexus | not_adopted | upheld 0.99 | survives | survived |
| document-retrieval/0 | opendatalab/mineru | targeted_candidate | refuted 0.99 | refuted on merit | survived |
| document-retrieval/3 | docling-project/docling | keep_but_compare | upheld 0.94 | survives | survived |
| document-retrieval/4 | cinnamon/kotaemon | not_adopted | refuted 0.88 | refuted on merit | not re-proposed |
| document-retrieval/5 | huggingface/sentence-transformers | targeted_candidate | refuted 0.97 | refuted on merit | not re-proposed |
| document-retrieval/6 | arabold/docs-mcp-server | keep_but_compare | upheld 0.87 | survives | survived |
| semantic-rag/1 | osu-nlp-group/hipporag | not_adopted | upheld 0.88 | survives | not re-proposed |
| semantic-rag/2 | lightonai/next-plaid | targeted_candidate | upheld 0.91 | survives | survived |
| semantic-rag/3 | minishlab/semble | targeted_candidate | upheld 0.90 | survives | survived |
| semantic-rag/6 | ollama/ollama | targeted_candidate | refuted 0.90 | refuted on merit | survived |
| semantic-rag/7 | giancarloerra/socraticode | targeted_candidate | upheld 0.97 | survives | not re-proposed |
| durable-memory/1 | campfirein/byterover-cli | not_adopted | refuted 0.82 | refuted on merit | refuted on fit (GPT-6) |
| durable-memory/2 | rohitg00/agentmemory | targeted_candidate | upheld 0.92 | survives | survived |
| durable-memory/3 | mempalace/mempalace | targeted_candidate | upheld 0.90 | survives | survived |
| durable-memory/4 | vshulcz/deja-vu | targeted_candidate | upheld 0.91 | survives | survived |
| durable-memory/7 | vbcherepanov/total-agent-memory | keep_but_compare | upheld 0.88 | survives | not re-proposed |
| web-research/0 | exa-labs/exa-mcp-server | targeted_candidate | upheld 0.91 | survives | not re-proposed |
| web-research/1 | unclecode/crawl4ai | not_adopted | refuted 0.94 | refuted on merit | refuted on fit (both) |
| web-research/2 | adbar/trafilatura | targeted_candidate | upheld 0.93 | survives | survived |
| web-research/3 | openai/codex | targeted_candidate | upheld 0.90 | survives | not re-proposed in web-research |

- 19 survive the V1 three-vote rule, 8 are refuted on merit by the native GPT-6 vote, and none remains refuted by
  absence.
- A proposal survives with its proposed label. For a `not_adopted` proposal, survival keeps the rejection. A refuted
  `not_adopted` proposal (kotaemon, byterover-cli, crawl4ai) means the rejection's stated rationale did not hold, not
  that the repository should be adopted.
- The other 44 proposals were already refuted by a returned facts or Claude fit vote. The GPT-6 vote refuted 25 of
  them and upheld 19: a second-family opinion that changes no outcome.
- Two of the eight merit refutations rest on the frozen template's license gate, read from the vote text:
  opendatalab/mineru ("custom-restrictive-license gate") and huggingface/sentence-transformers ("license-clarity
  gate"). The 2026-09-26 anti-pattern row in `docs/harness-defaults.md` ("Gating candidates on license") sends such
  refutations to re-decision.

## Lanes, effort and windows

- **Native class:** jobs in the private work directory's `lane`, through Codex's built-in OpenAI provider. Effort is
  the result line's effort and request_effort, max/max. Every vote in `tabulation.json` is from this class.
- **OmniRoute class:** jobs in `lane-omni`, through OmniRoute 20128. The lane was staged but no job started, so no
  vote of this class exists, no effort check against 20128's call logs was needed, and the harness README parity
  check (lines 343-349) does not apply to this record. The `result` lines of the never-started jobs carry
  `codex_job.py`'s defaults (web_search `live`), not the lane's staged `cached`; `jobs.json` says so per job.
- **Windows:** no attempt started in 06:30-09:00Z (the runtime lane's pool window) or 13:00-16:00Z (c5's exclusive
  slot, PR #608 comment 5966629642), and none was running at 13:00Z. The earliest attempt was the pre-launch probe at
  09:00:10Z, 10 s after the pool window closed; the first fit job started at 09:06:29Z and the last finished at
  09:41:59Z.
- **Slot deferral:** none. No result line has exit 3, `limit` and `limit_marker` are false in all of them, and neither
  lane held a LIMIT file at 09:46:10Z.

## Lane limits

Native lane:

- codex-cli 0.159.3. The 2026-09-26 GPT-6 lanes were qualified on 0.155.1 and 0.157.1, and the sealed returns do not
  record which of them ran.
- `--ignore-user-config` still loads `~/.codex/AGENTS.md` as global instructions (harness README line 306). That file
  has sha256 `50524adf7e4eef59dec3a367839f328f356e5a6e96e70c002108dc34bfb5dd14` and was modified 2026-09-30, so it is
  not the file the 2026-09-26 lane read.
- The installed skills under `~/.agents/skills` follow `adoption/skills/manifest.json` checked_at 2026-09-30 (#553);
  the frozen templates were filled with the skills date 2026-09-25. `skills_used` is the model's own report: in the
  durable-memory job, stderr shows an MCP resources/read of the plugin skill verification-before-completion failing,
  and the output still lists that skill.
- web_search is `cached`. That it sends `external_web_access: false` rests on the 0.155.1/0.157.1 qualification of
  `codex --search exec`; it is not measured at 0.159.3.
- The prompts carry Date 2026-09-26 but ran on 2026-10-03.
- The frozen V1 fit template still carries the license gate ("its license is non-commercial, custom-restrictive or
  unclear for this use") that the 2026-09-26 anti-pattern row retired.
- The votes ran through Codex's native sign-in. The retained native job records in [jobs.json](jobs.json) show
  `limit` and `limit_marker` false; they record no usage limit.

## What reads the label

Nothing in this flow reads the label. `codex_job.py` never reads `sweep_id`. `make_result.py` refuses a GPT-6-only
supplement: it builds a completed sweep's record from that sweep's returns, a complete Claude usage record
(`check_usage`) and a manifest. The `RUN_ID_PATTERN`
`[0-9A-Za-z]+` of `record_verdicts.py` (line 127) and `build_verdicts.py` (line 62) rejects hyphens. A later verdict
wave cites this directory under its own alphanumeric run id.

No ledger record is appended: the ledger has no supplement record type, and the 2026-09-26 README names the verdict
wave as the place for these votes. `lane_packets.absence_refuted` keeps the 27 as newcomers until a verdict wave
adjudicates them.

## Dispositions

1. The sealed 2026-09-26 record does not change; this is a new evidence record, not a ledger edit.
2. For 44 of the 71 proposals, facts or Claude fit already refuted; the new vote is a second-family opinion.
3. landscape-sweep-20260929, the latest completed sweep, re-proposed and adjudicated 20 of the 27 with returned
   cx/gpt-6-astra max votes, so their current disposition comes from that record: 16 survived and 4 were refuted on
   fit. The re-vote's outcome matches 14 of those 20. It differs for six: pi and bernstein survive here, and
   mattpocock/skills, boxlite, mineru and ollama are refuted here. The 2026-09-29 proposals carry their own text, so
   this is not a like-for-like comparison, and the 2026-09-29 record still governs.
4. Seven were never re-proposed in their layer. Five survive the V1 three-vote rule here: osu-nlp-group/hipporag,
   giancarloerra/socraticode, vbcherepanov/total-agent-memory, exa-labs/exa-mcp-server and openai/codex
   (web-research); they need `source_reviews.py` and then the verdict wave. Two are V1-refuted on merit:
   cinnamon/kotaemon and huggingface/sentence-transformers (the latter on the license gate).
5. Under U11 (`docs/decisions/2026-10-01-u11-merit-neutral-selection.md`), V1-refuted members enter the eligible field
   as pending until a V2 screen. A V1 re-vote on the frozen template (winners visible, license gate) resolves none of
   them, so no U11 field disposition changes.

Layer-verdict wave 20260922 is not affected. No row of `catalogs/sota-convergence/layer-verdicts-20260922.json`
(sha256 `2fef6da7…`, frozen by `layer-verdict-waves.json`) cites landscape-sweep-20260926, and no row's overturn
condition is a sweep fit vote. For information only, rows that name one of the 26 repositories: foundation
semantic-rag winner SocratiCode; foundation native-clients and agent-sdks winner openai/codex; foundation workers
alternative openai/codex (conditional); foundation document-retrieval alternative Docling; foundation web-research
alternative Crawl4AI; us-equities agents-models-workers winners openai/codex and SocratiCode; us-equities
identity-provenance alternative SocratiCode; us-equities research-factors-ml alternatives Docling and
sentence-transformers. These votes reach verdicts only through a new verdict-wave run id in `record_verdicts.py` with
a sealed cross-family review.

## Usage

GPT-6, from the result lines (each job's final attempt; no earlier attempts; no unavailable usage), as Codex reports
it. Counters are never added to each other.

| Jobs | input_tokens | cached_input_tokens | output_tokens | reasoning_output_tokens |
| --- | --- | --- | --- | --- |
| 9 fit jobs, native | 15,909,199 | 14,354,176 | 142,287 | 83,620 |
| pre-launch probe, native | 129,366 | 84,224 | 759 | 475 |

Claude usage was measured at 2026-10-03T10:14:35Z in the two retained files below. [jobs.json](jobs.json) remains
the Record stage's earlier 2026-10-03T09:59:23Z snapshot, including its historical `claude_usage.status: pending`
and superseded-launch description; the later usage records supply the current measured state and failed-attempt
counters. The Claude table copies each file's `child_usage.by_resolved_model` counters and stays separate from
the GPT-6 table. The two tables are never summed, and token categories are never added to one another.

| Usage record | child_usage.status | Total children | Resolved model | Model children | input_tokens | output_tokens | cache_read_input_tokens | cache_creation_input_tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [wf_555874dd-5a7](child-usage-wf_555874dd-5a7.json) | complete | 13 | claude-opus-5-5 | 4 | 768 | 527,983 | 87,987,107 | 2,843,752 |
| [wf_555874dd-5a7](child-usage-wf_555874dd-5a7.json) | complete | 13 | claude-sonnet-5-5 | 9 | 230 | 119,756 | 6,513,081 | 898,490 |
| [wf_8066ceb5-b9a](child-usage-wf_8066ceb5-b9a.json) | incomplete | 1 | claude-opus-5-5 | 1 | 130 | 62,672 | 11,564,262 | 305,171 |

The incomplete record contains only the planner and its issue "no result entry in journal". The files'
`child_usage.status` and `measurement.exit_code` (0 for `wf_555874dd-5a7`, 1 for `wf_8066ceb5-b9a`) are
counter-measurement results. They do not authenticate the parent workflow's exit or any model driver's exit.

## Usage limits and reset credits

The retained [job records](jobs.json) show no usage limit, and all nine native fit jobs counted, so the OmniRoute
fallback was not exercised. This run supplies no fallback or reset acceptance evidence.
[codex-client-check-20261003.txt](codex-client-check-20261003.txt) retains the R650 check's `date -u`,
`codex --version` (`codex-cli 0.159.3`) and full `codex --help` output, with each exit code. A reset-credit command
was not found in that help output or the version's
[release notes](https://github.com/openai/codex/releases/tag/rust-v0.159.3), retained in
[codex-upstream-check-20261003.json](codex-upstream-check-20261003.json). The pinned upstream source declares
`ConsumeAccountRateLimitResetCredit => "account/rateLimitResetCredit/consume"` in
[openai/codex rust-v0.159.3 common.rs, line 1315](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/app-server-protocol/src/protocol/common.rs#L1315);
the same receipt retains the verified source excerpt. This is upstream source evidence; no installed-schema
generation result is retained.

## Files

- `jobs.json`: label, workflow run, the saved result line of every job in both lanes with its lane class
  (`output_text` kept only as the parsed output, `stderr_tail` summarized), the pre-launch probe, GPT-6 usage, the
  window and slot-deferral checks.
- `props/<layer>.json`: byte-identical copies of the jobs' proposals, full 40-hex ids kept (the recorded hashes
  depend on them). `prompt.txt` is not published; the recipe in `provenance.json` regenerates it.
- `provenance.json`: the staging provenance (per layer input_path and input_sha256, props_sha256, prompt_sha256 and
  schema_sha256), workflow run, superseded launch and the verified regeneration recipe.
- `tabulation.json`: the 71 rows with sealed pointers, lane class and job id, and the 27 decisive rows' before and
  after, with native and OmniRoute in separate fields.
- [child-usage-wf_555874dd-5a7.json](child-usage-wf_555874dd-5a7.json): later Claude counter measurement, complete,
  13 children, with `by_resolved_model` counters.
- [child-usage-wf_8066ceb5-b9a.json](child-usage-wf_8066ceb5-b9a.json): later Claude counter measurement of the failed
  attempt, incomplete, one planner with "no result entry in journal".
- [codex-client-check-20261003.txt](codex-client-check-20261003.txt): dated installed-client version and full help
  output, including command exit codes.
- [codex-upstream-check-20261003.json](codex-upstream-check-20261003.json): dated release-note fields and the exact
  numbered reset-credit method excerpt from the pinned upstream source.
