# Matched prepared-context research comparison

This small experiment compares full public-document context with a deterministic
QMD lexical selection for two research questions. Each native client answers the
same question under both conditions. The coordinator authorized at most eight
fresh native process submissions: two questions × two conditions × two providers.
It is a feasibility measurement, not causal or general token-savings evidence.

The actual corpus, questions, retrieval queries, rubric, prompts, execution order,
runtime commands and selected executable/SDK source hashes are frozen before the
first model submission. Sources are eight existing public READMEs from commit
`cb79080cf5d9510818c67ac51c521b1d2a1b80fe`; full source text totals 71,223 bytes.
Every source keeps the same ID and verbatim text in both conditions. The exact
question and instructions are identical; only the supplied source block changes.

QMD 2.8.3 builds a separate eight-document BM25 corpus and returns at most two
documents per frozen query. Native `get` retrieves every returned document; the
adapter verifies its full text against the frozen original. No hand replacement,
query reformulation, model-backed retrieval, embeddings or downloads are used.
No shared QMD index is modified. A retrieval miss remains a quality result.

The two tasks ask about FB/META observation eligibility and prior paired native
usage/selected-text evidence. Within each provider the order is task A full then
focused, task B focused then full. Every run is a fresh session. Provider caches
are retained; fresh sessions do not imply cold caches. The two provider tokenizers,
system instructions and client behavior differ, so comparisons stay within each
provider/task pair.

## Observed native results — September 20, 2026

All eight native model invocations completed. The two independent blinded
readers accepted all eight answers against the content rubric. Six answers also
passed the structural and 250-word protocol; the two Claude full-context answers
contained 327 and 260 words. Those failures and their usage remain in the result.

| Native client / task | Full context tokens | Focused context tokens | Full minus focused | Content scores, full / focused | Both protocol passes |
| --- | ---: | ---: | ---: | ---: | --- |
| Codex GPT-6 Astra / A | 38,102 | 22,691 | 15,411 (40.4467%) | 10 / 10 | Yes |
| Codex GPT-6 Astra / B | 38,130 | 25,069 | 13,061 (34.2539%) | 10 / 9.5 | Yes |
| Claude Opus 5 / A | 44,595 | 20,136 | 24,459 (54.8470%) | 9.5 / 10 | No: full answer word limit |
| Claude Opus 5 / B | 45,652 | 24,562 | 21,090 (46.1973%) | 9.5 / 9.5 | No: full answer word limit |

These are exact observed native token totals and arithmetic differences for the
four pairs. They are not estimates of future savings or causal effects. The
Claude pairs fail the shared protocol on their full-context condition. Codex B's
focused answer cleared the frozen threshold with a small content-score decrease.
No cross-provider total or dollar savings is inferred.

The [sanitized native receipt](native-receipt.json) gives every run's uncached
input, cache creation/read, output, included reasoning, missing fields, duration,
hook counts, word count, blinded score and raw-evidence hashes. All eight raw
outputs were replayed against the frozen packets after scoring. Both inference
helpers and the original graded packet remained unchanged. The original
execution seal, blind packet and independently sealed grades have separate hashes.

Native QMD selected S01 for task A and S08/S07 for task B. Six local index/search/get
commands took 607 ms in total; that local time is separate from model usage.
The comparison excludes coordinator, preparation and reviewer usage. It does
not establish savings for this enclosing Desktop conversation or every future
session, nor does it accept the whole trading ecosystem again.

## Native execution and usage

Codex uses the installed official `openai-codex` SDK with `gpt-6-astra`, read-only
sandbox, deny-all approvals and the existing research developer policy. Native
configuration, account, hooks and selected model remain in place. A requested
and audited zero-tool limit rejects any unexpected result action. This is weaker
than preventing every MCP invocation before it happens. Native usage comes from
the single returned thread total; cumulative `last` or event snapshots are not
added to it. Cached input and reasoning are subsets of input/output, respectively.

Claude uses its native subscription command:

```sh
claude -p --model claude-opus-5 --output-format stream-json --verbose \
  --include-hook-events --max-turns 1 --tools '' --disallowedTools '*' \
  --permission-mode dontAsk --permission-prompts none
```

That command exposes no model tools, but native lifecycle hooks still run. Its
single terminal usage record separates ordinary input, cache creation, cache
reads and output. Thinking, when exposed, is included in output. The harness
never adds per-message or per-model usage to the terminal aggregate. Absent
categories, retries and unavailable failure usage remain NULL. Hook counts do
not establish a token count for hooks; SDK hook counts are not exposed here.

Each process has a 120-second deadline and reuses the existing accepted process
group supervisor. Native SDK interruption is requested before outer cleanup.
This bounds the local invocation; it does not prove cancellation of remote work.
There are no automatic resubmissions, model fallbacks or route changes. A native
authentication/quota refusal stops that provider's remaining submissions. An
unfinished reservation also blocks that provider until explicitly investigated.
Invocation counts and confirmed model submissions are distinct.

The measured provider usage covers the complete narrow answer task, including
whatever native context the provider reports. It excludes this coordinator,
fixture construction, independent reviewers and local retrieval. Local retrieval
commands and elapsed times are recorded separately. No model was used to build
the retrieval packets. This comparison does not measure an autonomous agent's
query-planning or multi-step coding workflow, or prove whole-session savings.

## Reproduce on an explicitly adopted host

Use the already adopted native Codex/Claude accounts and pinned SDK environment;
do not copy authentication stores or select a paid API fallback. Establish native
readiness using the [existing inspection recipe](../research-runtime/README.md)
and `claude auth status`. Claude auth status does not expose remaining allowance.
The repository needs the corpus commit in its local Git history. Set the following
host-local paths; keep run directories outside Git.

```sh
"$SDK_PYTHON" blueprints/us-equities/research-efficiency/experiment.py prepare \
  --out "$EFFICIENCY_RUN" --qmd "$QMD_BIN" --qmd-package "$QMD_PACKAGE" \
  --runtime-path "$NATIVE_RUNTIME_PATH" --sdk-python "$SDK_PYTHON" \
  --codex-bin "$NATIVE_CODEX_BIN" --claude-bin "$NATIVE_CLAUDE_BIN" \
  --codex-home "$NATIVE_CODEX_HOME" --workspace "$ADOPTED_WORKSPACE"

# Follow the frozen provider-wise order; each combination is accepted once.
"$SDK_PYTHON" blueprints/us-equities/research-efficiency/experiment.py run \
  --out "$EFFICIENCY_RUN" --freeze-sha256 "$FREEZE_SHA256" \
  --provider codex --task A --condition full \
  --sdk-python "$SDK_PYTHON" --codex-bin "$NATIVE_CODEX_BIN" \
  --claude-bin "$NATIVE_CLAUDE_BIN" --codex-home "$NATIVE_CODEX_HOME" \
  --workspace "$ADOPTED_WORKSPACE" --runtime-path "$NATIVE_RUNTIME_PATH"
```

The adapter is project-owned orchestration of native QMD, the official Codex SDK
and Claude CLI; it is not an upstream benchmarking feature. `prepare` retains the
exact native QMD collection/search/get commands and outputs. Process invocation
arguments, frozen prompt hashes and original stdout/stderr remain private.
Every output directory and run combination refuses replacement. Source/runtime
checks run before each model invocation. Only selected package source files are
fingerprinted; no claim covers every transitive runtime dependency or mutable
native account/hook configuration.

The frozen Claude command path is the existing launcher, which selects version
2.1.278 and disables its auto-updater. The underlying Claude executable was not
separately fingerprinted. The frozen Codex path resolves to the native executable.

The frozen native retrieval calls include these exact query arguments. Run them
only with the isolated `QMD_CONFIG_DIR` and `XDG_CACHE_HOME` established by
`prepare`; the public receipt records all six calls, timings and exit codes.

```sh
export QMD_CONFIG_DIR="$EFFICIENCY_RUN/qmd-config"
export XDG_CACHE_HOME="$EFFICIENCY_RUN/qmd-cache"
"$QMD_BIN" --index research-efficiency search \
  'META unmapped quarantine historical universe' -c research-corpus -n 2 --format json
"$QMD_BIN" --index research-efficiency search \
  'native usage cache reduction' -c research-corpus -n 2 --format json
"$QMD_BIN" --index research-efficiency get \
  'qmd://research-corpus/s01.md?index=research-efficiency' --no-line-numbers
```

After every attempted invocation has a retained receipt, export all answers for
independent review. Keep the mapping outside the grader's directory until the
grades are sealed; do not submit models again to repair a failed answer.

```sh
"$SDK_PYTHON" blueprints/us-equities/research-efficiency/review.py \
  --source "$EFFICIENCY_RUN" --freeze-sha256 "$FREEZE_SHA256" --out "$BLIND_REVIEW"
```

The native QMD named-index formatter appends `?index=research-efficiency` to source
URIs. The first local preparation preserved a failure on that format before
model submission. A focused regression verifies the exact allowed index and
collection, and the second preparation retained the original frozen queries.

## Quality and limits

The frozen rubric scores required facts (4), supported citations (2), preserved
unknowns/limits (2), absence of unsupported claims (1), and completion (1).
Quality requires at least 8/10, at least 3/4 required facts, and no fabricated value,
citation, historical eligibility or net-savings claim. Reports have the same
250 whitespace-word prose cap. Structure, citation availability, missing usage,
unexpected tools and failures are recorded independently of semantic quality.

The independent reviewer receives anonymized answers, question, rubric and full
frozen source corpus before provider, condition, ordering or usage is revealed.
An omitted fact can reduce completion without becoming a fabrication. Raw failed
outputs remain retained; no cheaper failure is described as accepted efficiency.
Provider defaults/hooks and prefix-cache reuse are uncontrolled, and two tasks
per provider cannot estimate order effects, confidence intervals or generality.

References: [Codex noninteractive execution](https://learn.chatgpt.com/docs/non-interactive-mode),
[native Claude flags](https://code.claude.com/docs/en/cli-reference),
[prior paired usage](../../../adoption/paired/README.md), and
[the bounded QMD retrieval evaluation](../retrieval-evaluation/README.md).
