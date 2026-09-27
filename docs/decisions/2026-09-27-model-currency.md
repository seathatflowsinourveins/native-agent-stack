# Decision: model currency across the routed lanes, and the routes to an older model (2026-09-27)

**Decided by:** a workflow unit on host `nativestack-5975wx-20260925`, for the user's request of 2026-09-27 to use
only the latest state-of-the-art models, including those released in the past weeks. Branch
`claude/w5-model-currency-20260927`, based on `origin/main@ec8a4892`, checked against Claude Code 2.1.283 and
codex-cli 0.157.1.

**Method (2026-09-27).** Three Opus 5.5 research units, one per model family: Anthropic Claude as Claude Code 2.1.283
uses it; OpenAI through Codex CLI 0.157.1 and the OmniRoute loopback gateway; and the open-weight models the
workstation hosts for memory, retrieval and local inference. One adversarial refuter per unit re-checked its return.
Each refuter answered "corrected": they refuted 3, 5 and 4 claims, and the open-weight refuter added 12 missed models,
none of which changed an action. One Opus synthesis merged the six returns into the table below. The returns and the
synthesis are scratch inputs, not retained receipts, so every claim here cites its primary source. Before writing,
this unit re-fetched the Anthropic release notes, models overview and Opus 5.5 announcement, the OpenAI API changelog,
the npm registry entry for Claude Code, the gateway's model list and the GitHub release data named below.

**Scope:**
- `.claude/settings.json`, `examples/claude-native/ultracode.settings.json` and its embedded copy in
  `recipes/claude-native-ultracode.md`: the two model-fallback guards
  ([below](#the-fallback-guards-in-the-committed-settings)).
- `adoption/templates/claude.settings.template.json`: `advisorModel` ([below](#the-advisor-in-the-template)).
- `catalogs/foundation/decisions.json`: the `isolated-builder` label of `lean-workflow-child-routing`. This closes
  follow-up 5 of the [harness-settings record](2026-09-27-claude-harness-settings.md#independent-verification-2026-09-27).
- `tests/test_install_claude_profile.py` and `tests/test_foundation_catalog.py`.
- Not changed: `manifests/stack.json` keeps the llama.cpp pin at b11057
  ([below](#llamacpp-pin-a-recorded-divergence-not-a-re-pin)).

Nothing is installed or applied on a host by this change.

## Decision table

No row switches a model: every routed model is the newest in its family on 2026-09-27, and four rows hold a newer
model behind an upstream gate.

| Lane and role | Current | Latest available (release date) | Action | Sources |
| --- | --- | --- | --- | --- |
| Claude Code, Anthropic API: main model for design, build, research, review, verification and synthesis (effort max) | `claude-opus-5-5` through `opus` and `opus[1m]`: the template's `model`, `model: opus` in every shipped agent definition except `source-scout`, and `model: 'opus'` workflow stages | Claude Opus 5.5 (2026-09-22). The release-notes entries of 2026-09-23 and 2026-09-24 launch no model, and Claude Code 2.1.283 (2026-09-25) is the npm `latest` | keep | [release notes](https://platform.claude.com/docs/en/release-notes/overview) ("We've launched Claude Opus 5.5"); [models overview](https://platform.claude.com/docs/en/about-claude/models/overview) ("start with Claude Opus 5.5 for most workloads"); CHANGELOG 2.1.280 ("now the default Opus model"); [model-config](https://code.claude.com/docs/en/model-config) alias table; [npm registry](https://registry.npmjs.org/@anthropic-ai/claude-code) |
| Native `/advisor`, for truly complex calls | `fable` in this host's user settings; the template had no `advisorModel`, so a new host got no advisor | Claude Fable 5.1 (2026-09-01). Claude Mythos 5.1, released the same day, is for Project Glasswing participants | keep; the template now carries `"advisorModel": "fable"` | models overview ("Use Claude Fable 5.1 for demanding reasoning and long-horizon agentic work"); [advisor](https://code.claude.com/docs/en/advisor), "Choose an advisor model"; [settings reference](https://code.claude.com/docs/en/settings-reference#advisormodel) |
| Pure command wrappers, mechanical extraction and acceptance re-runs | `claude-sonnet-5` through `sonnet` (`source-scout`, the Codex-wrapper stages) | Claude Sonnet 5 (2026-06-30). Claude Sonnet 5.5 was announced on 2026-09-22 for "the coming weeks" and has no model ID | keep; hold for Sonnet 5.5 | release notes; [Opus 5.5 announcement](https://www.anthropic.com/claude-opus-5-5) ("Claude Sonnet 5.5 and Claude Haiku 5.5 will follow in the coming weeks"); model-config alias table |
| Trivial probes (policy only) | `claude-haiku-4-5-20251001`, not routed: in the same-packet trial Haiku scored 9/14 against Sonnet's 14/14 ([workflows README](../../examples/claude-native/workflows/README.md)) | Claude Haiku 4.5 (2025-10-15); Claude Haiku 5.5 is announced with no model ID | keep, not routed | models overview; [model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations); Opus 5.5 announcement |
| OmniRoute gateway, Claude IDs | none: no repository configuration routes a Claude role through the gateway | The gateway serves no `claude-opus-5-5`. Its newest Claude IDs are `dva/claude-fable-5-1-*` (Fable 5.1) and `dva/claude-opus-5-*` (Opus 5, 2026-07-24) | hold: Opus-role stages stay on native Claude Code | read-only `GET /v1/models` on the loopback gateway, 2026-09-27: 582 IDs, 55 of them Claude, none with `opus-5-5` |
| Codex CLI 0.157.1: judgment (research, discovery, refutation, review, verdicts) | `gpt-6-astra` at `model_reasoning_effort=max` (the stack-worker profile, the landscape-sweep lane, `tools/adoption/prove_codex_lane.py`) | GPT-6 Astra (2026-09-03, "our most capable model"). GPT-6 Sol and GPT-6 Luna (2026-09-22) are lower tiers | keep | [OpenAI API changelog](https://developers.openai.com/api/docs/changelog); openai/codex `rust-v0.157.1` [`codex-rs/models-manager/models.json`](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/models-manager/models.json#L4) (first entry) |
| Codex CLI 0.157.1: mechanical, deterministically scored extraction | `gpt-6-sol` at medium, a preregistration binding ([#359 arm S1](../../blueprints/convergence-practice/gpt6-family-tiering-20260926/README.md)); no lane outside that experiment sets it | GPT-6 Sol (2026-09-22), released with GPT-6 Luna | keep | API changelog; the #359 decision: every arm within the frozen 0.02 micro-F1 bound, S1 cheapest by billed tokens |
| Codex CLI 0.157.1: interactive default | `gpt-6-astra` at `ultra` (`adoption/templates/codex.config.template.toml`, lines 1-2); lanes override the effort to `max` | as above | keep | the template; [Codex models](https://developers.openai.com/codex/models) |
| vLLM 0.30.0 on the workstation: code and document embedding | `nvidia/Nemotron-3-Embed-1B-BF16` at `c0c9fea9`, with 0.16 of the GPU | the same model (2026-07-16) is the strongest that fits: every open model above the 81.9 six-task RTEB(Code) bar has at least 4.02B parameters | keep | [model card at `c0c9fea9`](https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16/raw/c0c9fea93ea424587517f2c59e20db9f1d6bf615/README.md); [MTEB results at `e0c9e75e`](https://github.com/embeddings-benchmark/results/tree/e0c9e75e914e21b7b5d224fe06d19212d0f942e8/results); [vLLM releases](https://github.com/vllm-project/vllm/releases) (`v0.30.0`, 2026-09-22, the latest) |
| qmd 2.8.3: catalog embedding | `ggml-org/embeddinggemma-300M-GGUF` Q8_0, the qmd default | embeddinggemma-300m (2025-09-04), the newest model in a prompt format qmd 2.8.3 supports; a 2026 embedder would need a qmd change | keep | tobi/qmd `v2.8.3` [`src/llm.ts`](https://github.com/tobi/qmd/blob/v2.8.3/src/llm.ts#L86-L119); [Google model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card); qmd `v2.8.3` (2026-08-16) is the latest release |
| qmd 2.8.3: reranking | `ggml-org/Qwen3-Reranker-0.6B-Q8_0-GGUF` (Qwen3-Reranker-0.6B, 2025-06-05) | `jinaai/jina-reranker-v3.5` (2026-08-03) | hold ([gate](#holds-and-their-gates)) | [Jina release post](https://jina.ai/news/jina-reranker-v3-5-faster-listwise-reranking-hybrid-attention-self-distillation/); [GGUF card at `884f7c67`](https://huggingface.co/jinaai/jina-reranker-v3.5-GGUF/raw/884f7c67/README.md); [ggml-org/llama.cpp#26286](https://github.com/ggml-org/llama.cpp/pull/26286) (open) |
| qmd 2.8.3: query expansion | `tobil/qmd-query-expansion-1.7B-gguf` q4_k_m, the qmd default | the same model; its publisher has released nothing newer that qmd can use | keep | [Hugging Face API](https://huggingface.co/api/models/tobil/qmd-query-expansion-1.7B-gguf); tobi/qmd `v2.8.3` [`finetune/README.md`](https://github.com/tobi/qmd/blob/v2.8.3/finetune/README.md) |
| llama.cpp b11146 (v0.5.0) on the workstation: general local model | `unsloth/Qwen3.8-27B-GGUF` UD-Q4_K_M at `4ca72078`, li26 C2 serving profile | Qwen3.8-27B (2026-08-14), the strongest model that fits the C2 admission of about 17.5 GB | keep | [QwenLM/Qwen3.8 README](https://github.com/QwenLM/Qwen3.8/blob/main/README.md); [model card at `1d4bf0f2`](https://huggingface.co/Qwen/Qwen3.8-27B/raw/1d4bf0f2/README.md); [li26 results](../../blueprints/convergence-practice/local-inference-latest-20260926/README.md) |
| ai-memory 2.4.1: memory embedder | `all-MiniLM-L6-v2` on the hard-wired `local` provider; `manifests/stack.json` labels it "not latest SOTA" | `nvidia/Nemotron-3-Embed-1B-BF16` through `openai-compat` with the `query: ` and `passage: ` prefixes, which needs ai-memory 2.5.0 | hold ([gate](#holds-and-their-gates)) | [ai-memory releases](https://github.com/akitaonrails/ai-memory/releases) (`v2.4.1`, 2026-09-25, the latest); [akitaonrails/ai-memory#859](https://github.com/akitaonrails/ai-memory/pull/859) (merged into `release/2.5` on 2026-09-23); [workstation refresh record](2026-09-25-workstation-sota-refresh.md#ai-memory-embedder-nemotron-through-openai-compat-with-prefixes) |

Two rows keep a model that a single source could rank lower:

- **Advisor.** The Opus 5.5 announcement calls Opus 5.5 "the new leading model" and puts it ahead of Fable 5.1 on
  every row of its table, while adding that "the gap between Opus 5.5 and Claude Fable 5.1 is narrower than these
  scores suggest". Anthropic's routing text keeps Fable 5.1 as the escalation tier: the models overview uses it "when
  your evals on Claude Opus 5.5 at higher effort still fall short", and the advisor pairing table accepts a Fable
  advisor for an Opus 5.5 main model but rejects an Opus advisor for a Fable 5.1 main model. The user's rule assigns
  Fable 5.1 and allows `opus` when that fits, so no switch is needed.
- **Extraction.** GPT-6 Luna shares Sol's release date. The frozen #359 metric (billed tokens) picked Sol; a rerun that
  scores credits or included usage could favour Luna, and changing that metric is the user's call.

## Holds and their gates

- **jina-reranker-v3.5 for qmd.** qmd reranks through node-llama-cpp's `createRankingContext` and `rankAll`
  (tobi/qmd `v2.8.3` `src/llm.ts`), so only a GGUF that stock llama.cpp can rank-pool is a drop-in. The v3.5 GGUF card
  requires the `littlewine/llama.cpp` fork, a `projector.safetensors` file and a Python listwise scorer, and the
  upstream pull request it cites (#26286, "qwen3 : add sliding-window attention pattern support") is open.
  **Gate:** stock llama.cpp and node-llama-cpp gain rank-pooling for it; then qualify it on the catalog task.
- **Nemotron-3-Embed-1B for ai-memory.** Prefix support (#859) is merged into `release/2.5` but unreleased; the latest
  release is `v2.4.1`. **Gate:** ai-memory 2.5.0 ships with #859; then run the preregistered evaluation of the
  [workstation refresh record](2026-09-25-workstation-sota-refresh.md#evaluation-only).
- **Claude Sonnet 5.5 and Claude Haiku 5.5.** Announced on 2026-09-22 with no model ID, price or release-notes entry
  (re-fetched 2026-09-27). When they ship, the `sonnet` and `haiku` aliases move with a Claude Code update, but three
  version-keyed places will not: the template's `modelSettings` (keyed `claude-opus-5-5`), `LEGACY_EXACT` in
  `adoption/hooks/claude/effort-default-guard.py`, and `ALIAS_RESOLUTION` in
  `examples/claude-native/workflows/child-usage.mjs`. **Gate:** a release-notes entry with a model ID; then repeat the
  same-packet inventory trial of the workflows README before routing either model.
- **OmniRoute and Opus 5.5.** The gateway serves Fable 5.1 but no Opus 5.5, so an Opus lane sent through it would run
  on Opus 5. **Gate:** the gateway lists `claude-opus-5-5`; until then Opus-role stages stay on native Claude Code.

## The fallback guards in the committed settings

**Decision.** `.claude/settings.json` and `examples/claude-native/ultracode.settings.json` carry the template's two
guards in the template's form: `"switchModelsOnFlag": false` and `env.CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK = "1"`. The
recipe's embedded copy of the portable file matches it. Before this change only the user-settings template carried
them ([fallback-guard record](2026-09-25-model-fallback-guard.md)), so a session that loaded only this repository's
files, or `claude --settings examples/claude-native/ultracode.settings.json`, could re-run a flagged Opus 5.5 or Fable
request on an older model. This host was guarded through its user settings. The change closes the "ultracode recipe
alone" gap that the fallback-guard record left to the recipe's owner.

**What the two keys do, and where they are honoured.**
- `switchModelsOnFlag`: [settings reference](https://code.claude.com/docs/en/settings-reference#switchmodelsonflag)
  (fetched 2026-09-27): "Scope: Any file"; `false` pauses an interactive session so you can switch or edit the
  prompt, and "where no dialog can show, such as a `-p` run, the flagged request ends as an error"; the default is
  `true`. [Model-config](https://code.claude.com/docs/en/model-config#automatic-model-fallback) gives the targets:
  for "Fable 5.1, Fable 5, and Opus 5.5", biology-flagged requests re-run on Opus 5 and cybersecurity-flagged requests
  on Opus 4.8, and "After a fallback, the session continues on the fallback model."
- `CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK`: not found in the [environment variables
  reference](https://code.claude.com/docs/en/env-vars), model-config or the settings reference (all fetched
  2026-09-27), nor in the CHANGELOG at anthropics/claude-code
  [`7779afb1`](https://github.com/anthropics/claude-code/blob/7779afb12e3635f46f56ec823979d68350ae000b/CHANGELOG.md),
  the `v2.1.283` tag. Neither key has a CHANGELOG entry there. Its behaviour rests on the installed 2.1.283 client
  (`source_review`, not probed):
  - `jD()` is `!a.CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK&&!Ote()`, and the query loop handles a `fallback_request` only
    when `jD()` holds or the attempt is a server-armed silent retry, the lane the fallback-guard record describes. That
    lane's target, `IAr()`, returns the refusing model itself or nothing. The variable therefore stops every switch to
    another model; only a same-model silent retry remains.
  - `orn()` returns `"subagent"` for any thread other than the main one before it reads `switchModelsOnFlag`, so the
    setting alone still does not stop a subagent's or workflow child's fallback, as in 2.1.282.
  - `a` is built by `Rhn()`, whose getters read `process.env[name]` at each access and parse it with `M.bool()`, so an
    `env` value from any settings file reaches the check once Claude Code applies it.
  - The set of variables that project and local settings cannot set (`Qzn`) does not contain it, and the documented
    list (settings reference, "Variables Claude Code ignores in `env`") does not name it.
  - The fallback-guard record's watch command still counts 1 on the 2.1.283 binary.
- **Project scope.** The settings reference gives `env` "Scope: Any file"; project and local values apply "after you
  trust the workspace, or at startup in `-p` mode". A project value outranks the user settings and a shell export;
  `.claude/settings.local.json` outranks it ([settings](https://code.claude.com/docs/en/settings#settings-precedence)).

**Effect and override.** In this repository, a request that the safeguards flag now ends in a refusal in the main
thread and in every child, instead of an answer from Opus 4.8 or Opus 5. The coordinator follows the portable
instruction: check the child's transcript for a refusal, edit the brief and retry on the current model. A contributor
who wants the automatic switch sets `"switchModelsOnFlag": true` and the variable to `"0"` in
`.claude/settings.local.json`.

## The advisor in the template

**Decision.** `adoption/templates/claude.settings.template.json` sets `"advisorModel": "fable"`, so a new host that
applies it gets the advisor the user's rule assigns (Opus 5.5 main, Fable 5.1 advisor for truly complex calls).

**Evidence.**
- [Settings reference](https://code.claude.com/docs/en/settings-reference#advisormodel) (fetched 2026-09-27): "Scope:
  Any file"; one of `"fable"`, `"opus"` or `"sonnet"`, or a full model ID; unset leaves the advisor off; `/advisor`
  saves the pick to `~/.claude/settings.json`, the file the template renders into.
- [Advisor](https://code.claude.com/docs/en/advisor), "Choose an advisor model": an "Opus 5.5 or Opus 5" main model
  accepts "Fable, and Opus 5 or later", and a Sonnet 5 main model accepts Fable, so the template's `opus[1m]` main
  model and the Sonnet stages both pair with it. "Subagents inherit the configured advisor and apply the same pairing
  check against their own model"; that is documented, not observed in a workflow child.
- Where Fable is not usable yet, nothing fails: "With Fable already saved as your `advisorModel`, Claude Code sends
  requests without the advisor. In an interactive session whose main model supports the advisor, it also shows a
  notification that points to `/model fable`." On Amazon Bedrock and Claude Platform on AWS the key has no effect.
- The advisor needs feature-flag fetching. The template sets none of `DISABLE_GROWTHBOOK`, `DISABLE_TELEMETRY`,
  `DO_NOT_TRACK` and `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, which turn it off, nor
  `CLAUDE_CODE_DISABLE_ADVISOR_TOOL` ([env-vars](https://code.claude.com/docs/en/env-vars), "Features that need
  feature-flag fetching").

**Template precedence.** `tools/adoption/apply_claude_settings.py` merges scalars with the template winning, as it does
for `model` and `effortLevel`. A re-apply therefore resets a host that chose `opus` or turned the advisor off. Such a
host sets its choice in the rendered template before applying (`"opus"`, or no key and then `/advisor off`), or runs
`/advisor` again afterwards.

## The `isolated-builder` label

`lean-workflow-child-routing` in `catalogs/foundation/decisions.json` described `isolated-builder` as "Sonnet/max";
all three copies of its definition declare `model: opus` and `effort: max` (the [harness-settings
record](2026-09-27-claude-harness-settings.md), item 1). The label now reads "Opus/max". A new test compares every
"`agent` (Model/effort)" label in the foundation decisions with the agent's frontmatter.

## llama.cpp pin: a recorded divergence, not a re-pin

**Facts (GitHub API, 2026-09-27).**
- `b11057` is commit `59657a613ab0fa4ab327d6c790123dff30bfbd67`, the `source_pin` in `manifests/stack.json`.
- `b11146` is commit `7fe450e19305b828c199d602c23a8337aaa1f03b` ("llama.cpp : bump version to 0.5.0 (#29333)"), a
  prerelease published 2026-09-23T18:36:37Z.
- `v0.5.0` is the annotated tag object `c13fcbf684171d5e0bca3fc5c34be6a99174b05f`, which points to the same commit.
  Its release (2026-09-23T20:50:06Z) is the repository's latest and is not a prerelease. The release's
  `target_commitish` names `d2e54583`, three commits later; the tag, not that field, names the commit.
- Newer nightlies run to `b11222` (2026-09-27T17:43:57Z); all are prereleases.
- `manifests/stack.json` already names b11146 as the `runtime_version` of its `unsloth/Qwen3.8-27B-GGUF` entry while
  the `llama-cpp` component pins b11057.

**Decision.** Keep the b11057 pin. The [workstation refresh record](2026-09-25-workstation-sota-refresh.md#llamacpp-b11146-v050)
recorded b11146 "not qualified" and set the re-pin gate: a paired acceptance in an owned window, with a freshly
installed b11057 baseline, fixtures, throughput within 0.90x and placement with `--fit off`, which needs the
production generation unit stopped. That acceptance has not run: on 2026-09-27 `origin/main` (`c8362c02`) held no
llama.cpp receipt dated after 2026-09-26 and still pinned b11057. The later receipts show this host serving b11146 and
the li26 experiment running on it: `nativestack-5975wx-20260925--llama-cpp--install--20260926`,
`nativestack-5975wx-20260925--llama-cpp--install--20260926-2`, `nativestack-5975wx-20260925--llama-cpp--use--20260926`
and `local-inference-c2-serving-switch-20260926`.

**Review status of those receipts** (their `reviews` and `limitations` fields, read 2026-09-27):
- Each of the three host receipts carries the recorder's self review and an `independent_session` review from the
  li26 results PR (#342). The first install receipt's independent verdict is `needs_changes`; `-2` supersedes it,
  because the first generation's verify-arms call ran without `-B`. The independent verdict on `-2` and on the use
  receipt is `agree`.
- `local-inference-c2-serving-switch-20260926` has no `reviews` field. Its `limitations[4]` sentence that the host
  receipts "carry only self reviews" was recorded at 2026-09-26T12:43:24Z, before the independent reviews (12:57:39Z
  and 13:02:09Z), and is stale. So is each host receipt's own limitation that it "carries only the recorder's self
  review".
- The decision does not rest on review status. Each independent `agree` accepts its receipt's scoped claim, that
  b11146 is installed and serving, and each receipt states that it does not rebind the pin. None compares against a
  b11057 baseline, and li26 cannot supply one:
  [`eval_arm.py`](../../blueprints/convergence-practice/local-inference-latest-20260926/eval_arm.py) (lines 114-116)
  refuses a plan unless every arm names the b11146 runtime.

**Qualification needed.** The paired acceptance of the 2026-09-25 record in an owned window, against a freshly
installed b11057 baseline, is the remaining gate. Then re-pin `llama-cpp` to b11146, which is `v0.5.0` (commit
`7fe450e1`), in a hot-file commit. Builds from b11183 on carry a decode-path rewrite and are the next candidates
against that baseline.

## Evidence

| Claim | Class | Source |
| --- | --- | --- |
| Model release dates and current recommendations | `source_review` | the Anthropic release notes, models overview, model deprecations and Opus 5.5 announcement; the OpenAI API changelog; the Hugging Face cards and GitHub releases in the table, re-fetched 2026-09-27 |
| Claude Code 2.1.283 is the latest client | independent observation (platform record) | npm registry `dist-tags.latest` = 2.1.283, published 2026-09-25T18:46:11Z; the CHANGELOG's newest heading is 2.1.283 at `7779afb1` |
| The gateway serves no Opus 5.5 | native operation (read-only) | `GET /v1/models` on the loopback gateway, 2026-09-27: 582 IDs, 55 Claude, no `opus-5-5` |
| Both guard keys exist; the setting's scope; the variable's effect and scope | `source_review` | settings reference and model-config (fetched 2026-09-27); the installed 2.1.283 client (`jD`, `orn`, `IAr`, `Rhn`, `Qzn`) |
| The committed files carry the guards; the recipe matches the portable file | `structural_validation`, failing-first | `CommittedSettingsFallbackGuardTests`: both paths failed at `ec8a4892`; after the two settings files changed, the recipe test failed until the embedded copy matched |
| The template carries a Fable advisor that pairs with its main model | `structural_validation`, failing-first | `test_the_advisor_is_fable_and_accepted_for_the_main_model` failed at `ec8a4892` (`None != 'fable'`) |
| Foundation decision labels match the agent definitions | `structural_validation`, failing-first | `CheckedInAgentLabelTests` failed at `ec8a4892` (`('sonnet', 'max') != ('opus', 'max')`) |
| llama.cpp tag identities | independent observation (platform record) | `gh api` `git/ref/tags/b11057`, `b11146`, `v0.5.0`; `git/tags/c13fcbf6`; `releases/latest`, 2026-09-27 |
| Review status of the 2026-09-26 llama.cpp receipts; no later llama.cpp receipt | `source_review` (repository records) | the `reviews` and `limitations` fields of the three host receipts under `evidence/hosts/nativestack-5975wx-20260925/` and of `evidence/receipts/local-inference-c2-serving-switch-20260926.json`; the tree and `manifests/stack.json` of `origin/main` at `c8362c02`, 2026-09-27 |
| `deniedModels` exists and is managed-only; that denying the older Opus IDs would stop the fallback to them without disabling the `opus` wildcard is an inference | `source_review` | CHANGELOG at `7779afb1`, lines 6-7; settings reference, `deniedModels`; model-config lines 350, 353, 364 and 517 (Markdown source, fetched 2026-09-27); not probed |
| The host's `bin/vllm` link points at the 0.30.0 prefix | the coordinator's host observation (no receipt in the repository) | repointed 2026-09-27T19:21:18Z; the 0.25.0 prefix is retained and no systemd unit uses the link |

No native run backs the guard or advisor changes: no request was flagged on purpose (deliberately tripping a safety
classifier is not an acceptable test), and no session was started with the changed files.

## Alternatives considered

1. **Leave the repository files unguarded and rely on user settings.** Rejected: an adopter of the recipe or a host
   that has not applied the template would run children that silently switch to Opus 4.8 or Opus 5.
2. **`switchModelsOnFlag: false` alone.** Insufficient: 2.1.283 still decides a subagent's fallback before it reads the
   setting. It stays as the documented backstop.
3. **An `availableModels` allowlist.** Rejected for the reasons in the fallback-guard record: excluding older Opus
   versions disables the family wildcard, so the next Opus would stay excluded until the list is edited.
4. **The `deniedModels` managed setting (Claude Code 2.1.283).** The CHANGELOG at `7779afb1` adds it "to block
   specific models, even when `availableModels` allows them" (line 7, beside `availableModelsMatch` on line 6).
   [Model-config](https://code.claude.com/docs/en/model-config#block-specific-models-or-versions) says a blocked
   model "is treated as a blocked selection everywhere the allowlist applies" (line 364), that "The fallback model is
   checked against `availableModels`. When it is blocked, no fallback occurs" (line 517), and that a release no entry
   blocks stays permitted (line 350); the line numbers are the page's Markdown source, fetched 2026-09-27. Inference,
   since no page says it in one sentence: denying the older Opus IDs would stop the fallback to them without disabling
   the `opus` wildcard, so the next Opus would stay permitted. The entries must name the minor version,
   `claude-opus-5-0` and `claude-opus-4-8`: the [settings
   reference](https://code.claude.com/docs/en/settings-reference#deniedmodels) says `"claude-opus-5"` also blocks
   Opus 5.5. As the fallback-guard record notes for the allowlist, the docs do not limit the check to the main
   session; nothing here probed it. Not adopted: the settings reference gives the key "Scope: Managed", and Claude
   Code "ignores the key in user, project, and local settings and in `--settings`, with a warning". Those are the
   Claude Code settings files this repository's portable foundation ships or writes (the user-settings template,
   `.claude/settings.json` and the portable file for `claude --settings`); it writes no managed settings file, and its
   effort guard only reads one.
5. **A workflow-contract check in `test-envelope.mjs`.** Deferred: it would change the portable contract, its
   `SHA256SUMS` and every adopter's vendored copy. The Python tests cover this repository's files.
6. **Advisor `opus`, or no template default.** `opus` is allowed by the user's rule and by the pairing table, but the
   user chose Fable 5.1, which Anthropic's overview keeps as the escalation tier. No default leaves new hosts without
   the assigned advisor.
7. **`advisorModel` in the project settings.** Rejected: it would turn the advisor, and its Fable billing, on for
   every session in this repository whatever the contributor's plan; `/advisor` itself saves to user settings.
8. **Re-pin llama.cpp on the 2026-09-26 receipts and li26.** Rejected: the current install and use receipts carry
   independent `agree` reviews, but none compares against the b11057 baseline that the re-pin gate requires, each
   states that it does not rebind the pin, and li26 ran every arm on b11146. Moving to the newest nightly is rejected
   too: it is unqualified.

## Overturn

- **Any model row:** a newer model in the same family appears in its vendor's release notes or changelog, or the
  vendor's routing text stops recommending the current one. On a Microsoft Foundry host `opus` resolves to Opus 4.6,
  and on Bedrock, Google Cloud, Foundry or Claude Platform on AWS `sonnet` resolves to a 4.x model
  ([model-config](https://code.claude.com/docs/en/model-config) alias table): pin `claude-opus-5-5` and
  `claude-sonnet-5` there.
- **Advisor:** Anthropic stops ranking Fable 5.1 above Opus 5.5 for pairing, a Fable successor ships, or a same-task
  comparison of this host's advisor calls shows Opus 5.5 at max matching Fable 5.1.
- **Extraction:** a preregistered rerun that scores credits or included usage finds GPT-6 Luna at medium the cheapest
  routable arm.
- **Guards:** a documented control that user, project or `--settings` files can set stops the content-based fallback
  in subagents without a version-pinned allowlist; or a client release stops reading the variable, or widens the
  silent-retry lane to other models. Adopting managed settings would make `deniedModels` (alternative 4, with
  `claude-opus-5-0` and `claude-opus-4-8`) the preferred guard on that host, with `requiredMinimumVersion` set because
  earlier clients ignore the key (model-config line 353).
- **Holds and the llama.cpp pin:** the gates above.

## Unresolved

- Whether workflow children inherit `advisorModel` is documented for subagents but not observed, and the resolved
  advisor ID has not been seen in a transcript.
- The variable is undocumented, so a client update can drop it silently; the recipe and the fallback-guard record say
  to re-check it after each update, and no automated watch exists in this catalog yet.
- No code pin sets `-m gpt-6-sol -c model_reasoning_effort=medium`, so which stages use Sol is unknown.
- OmniRoute: which provider the judgment lane uses in practice (the Codex template keeps the native provider; the
  OmniRoute profile is opt-in), and whether the running gateway build passes `max` rather than clamping it to
  `xhigh`. The gateway still lists deprecated or retiring IDs that no role uses.
- Release dates not confirmed: `gpt-reserve`, `codex-auto-review`, GPT-6 Pro in ChatGPT and
  `tobil/qmd-query-expansion-1.7B-gguf`, and most in-window Hugging Face models, which carry only repository creation
  dates.
- Workstation boundaries: FP8 or INT8 serving of the 4B and 8B embedders on Ada in vLLM 0.30.0, GGUF rank-pooling of
  Qwen3-Reranker-4B and mxbai-rerank-large-v2, and the Qwen3.8-27B derivatives are unmeasured. The [refresh
  record's](2026-09-25-workstation-sota-refresh.md#qmd-283-qdrant-1191-ccusage-20024-worktrunk-0790-vllm-0300)
  `bin/vllm` follow-up is closed on this host: the link now points at the 0.30.0 prefix (repointed
  2026-09-27T19:21:18Z), the 0.25.0 prefix is retained and no systemd unit uses the link (the coordinator's host
  observation).
- The three 2026-09-26 llama.cpp host receipts and the serving-switch receipt keep their stale limitation sentences
  about self reviews ([above](#llamacpp-pin-a-recorded-divergence-not-a-re-pin)); this change edits no receipt.
- Other hosts, such as the Mac, need their own alias-resolution check.

## Limitations

- One host (`nativestack-5975wx-20260925`, WSL2) and one client version (Claude Code 2.1.283). The client-code reading
  names minified identifiers that change between releases.
- The research returns and the synthesis stay private session files; this record states their facts with primary
  sources but does not publish them.
- Nothing is applied: hosts keep their current user settings until the template is applied again.
