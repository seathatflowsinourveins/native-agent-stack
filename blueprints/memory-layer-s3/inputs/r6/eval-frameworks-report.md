Source: <scratch>/eval-frameworks/report.md; capture date: 2026-09-27.
**Use upstream frameworks for orchestration and statistics, while retaining explicit task contracts. W1 and W3 have no verified complete replacement meeting every requirement unchanged.**

Read-only research as of **2026-09-27**; no installations, service/model runs, edits, commits, or credential-store reads. Maintenance counts below came from paginated `gh api repos/OWNER/REPO/commits?since=2026-06-29T00:00:00Z&per_page=100`, including default-branch merges. Licenses are informational.

| Workflow | Primary | Runner-up | Recommended pin / latest release | Maintained | Fit | Remaining gaps | What it replaces |
|---|---|---|---|---|---|---|---|
| **W1** | [Harbor](https://github.com/harbor-framework/harbor) | Inspect AI + inspect_swe | **v0.23.0**, Sep 12; Apache-2.0 | 533 commits | Native Codex/Claude transcripts, repetitions, concurrency, sandbox tasks | Exact `stack-worker` profile, existing worktree binding, same-call success/sentinel assertion, Loki reconciliation | Orchestration in `m13_probe.py` and `matrix_scan.py`, conditionally; retain `loki_reconcile.py` |
| **W2** | [Promptfoo](https://github.com/promptfoo/promptfoo) | Inspect AI | **0.123.1**, Sep 18; MIT | 844 commits | Gateway providers, headers, structured output, repeated comparisons, usage/latency | Dynamic request headers, aggregate micro-F1, paired inference, affinity verification | [eval_arm.py](~/code/native-agent-stack/blueprints/convergence-practice/local-inference-latest-20260926/eval_arm.py) request/repetition/reporting code |
| **W3** | [AMB](https://github.com/vectorize-io/agent-memory-benchmark), **conditional**, plus original LongMemEval scorer | Native LongMemEval retrieval harness | **03c1d0f1d27da63034f0931121c858faba512383**; no release; last push Sep 22; license undeclared | 12 commits | LongMemEval-S orchestration; Hindsight/cognee adapters | Six adapters, unchanged metric integration, backbone configuration, lifecycle acceptance; CLI defect | Planned S3 runner and [lme_harness.py](~/code/native-agent-stack/blueprints/memory-stack/longmemeval/v4/lme_harness.py), only after gaps close |
| **W4** | [MTEB](https://github.com/embeddings-benchmark/mteb) | BEIR | **2.21.8**, Sep 23; Apache-2.0 | 406 commits | Registered LoCoMo, retrieval and two-stage reranking | Dataset/model choices still required; no memory lifecycle evaluation | W4 use of [mteb_lmeb.py](~/code/native-agent-stack/blueprints/memory-stack/longmemeval/v4/mteb_lmeb.py) and `rerank_stage.py` |
| **W5** | [SciPy](https://github.com/scipy/scipy) + [statsmodels](https://github.com/statsmodels/statsmodels) | arch | **1.18.1**, Aug 21 / **0.15.0**, Aug 27; BSD-3-Clause | 571 / 1,265 commits | Paired bootstrap, permutation tests, Holm, statistical inference | Cluster unit, estimand, non-inferiority margin remain study definitions | [analyze.py:85](~/code/native-agent-stack/blueprints/convergence-practice/local-inference-latest-20260926/analyze.py:85) `paired_bootstrap`; proposed S3 statistics |
| **W6** | Each tool’s upstream suite, below | Inspect AI for shared task-quality comparison | Seven pins below | All show recent activity | Native compression/retrieval evidence | No suite establishes all seven tools’ agent-task quality unchanged | Replace fixture-only E2E claims; retain accounting/integration files |
| **W7** | [Anthropic skill-creator](https://github.com/anthropics/skills) paired benchmark procedure | Superpowers TDD/verification | **33375500bcea98d610eb30ce10ac4e59b89c390d**, Sep 24; no release; selected skills Apache-2.0 | 14 commits | Paired skill/baseline quality, time and tokens | Procedure requires actual runs; not W5 statistical inference | Ad hoc evaluation procedures; no separate harness file identified |

Commands below are **migration instructions, not executed acceptance**. Angle-bracket inputs denote case artifacts still requiring preparation.

**W1 — choose Harbor for native transcripts.** Its pinned adapters invoke [Codex `--json` and preserve native sessions](https://github.com/harbor-framework/harbor/blob/v0.23.0/src/harbor/agents/installed/codex.py#L1436), and [Claude `stream-json`](https://github.com/harbor-framework/harbor/blob/v0.23.0/src/harbor/agents/installed/claude_code.py#L1895). Rewardkit provides [tool-used/tool-not-used criteria](https://github.com/harbor-framework/harbor/blob/v0.23.0/docs/content/docs/rewardkit/built-in-criteria.mdx#L82), but these alone do not prove that the same successful call returned the correct worktree sentinel.

```bash
uv tool install 'harbor==0.23.0'
harbor run -p '<gate-dataset>' -a codex -m '<provider/model>' --ak version=0.157.1 -k 20 -n 2
harbor run -p '<gate-dataset>' -a claude-code -m '<provider/model>' --ak version=2.1.283 -k 20 -n 2
```

These flags establish repetitions/concurrency, **not the required two existing worktrees**. Harbor uses temporary client homes; unchanged `-p stack-worker` support was not found in its inspected options/source. Retain the native gate until positive, disabled-server and wrong-root cases satisfy binding and Loki reconciliation.

Inspect **0.3.271** (Sep 26; 1,504 commits; MIT) with inspect_swe **0.2.71** (Sep 17; 76 commits; MIT) is the runner-up: its [bridge proxies model calls](https://github.com/meridianlabs-ai/inspect_swe/blob/0.2.71/docs/_snippets/agent_intro.md#L3), and [Codex transcripts are reconstructed from bridge events](https://github.com/meridianlabs-ai/inspect_swe/blob/0.2.71/src/inspect_swe/_codex_cli/_events/consumer.py#L3).

Installed Claude 2.1.283 independently offers:

```bash
claude plugin eval '<gate-plugin>' --runs 20 --concurrency 2 --mocks off --ablation none --no-publish --json '<results.json>'
```

Installed help confirms `--mocks record|off` and `--allow-real-servers`; recorded mocks require the latter to contact missing real servers. This is a useful Claude-only lane.

**W2 — retain Promptfoo, with explicit metric and header integration.** Its pinned documentation covers [base URL, headers, schema/tool output and effort](https://github.com/promptfoo/promptfoo/blob/0.123.1/site/docs/providers/openai.md#L182) and [session hooks](https://github.com/promptfoo/promptfoo/blob/0.123.1/site/docs/configuration/reference.md#L365).

Configure the two model IDs against `http://127.0.0.1:20128/v1`; enumerate singleton combinations explicitly. Preserve one session key per conversation while generating fresh request IDs. Static headers alone are insufficient.

```bash
npm install -g promptfoo@0.123.1
promptfoo eval -c '<gateway-cases.yaml>' --repeat 20 --max-concurrency 1 --no-cache --no-share -o '<gateway-results.json>'
```

Use its [Python scorer interface](https://github.com/promptfoo/promptfoo/blob/0.123.1/site/docs/configuration/expected-outputs/python.md#L15) with frozen li26 semantics: **aggregate TP/FP/FN before micro-F1; do not average filing F1**. Pair observations by case/repetition and analyze with W5.

Promptfoo’s response-cache switch differs from `X-OmniRoute-No-Cache`. Provider cache-read tokens are [separate accounting fields](https://github.com/promptfoo/promptfoo/blob/0.123.1/src/providers/openai/util.ts#L997); calculate cached-input share from returned provider counts, not `tokenUsage.cached`. Affinity still requires gateway observation.

OpenAI Evals had zero commits in the window; that does not describe hosted API capabilities. [lm-evaluation-harness supports endpoint/header configuration](https://github.com/EleutherAI/lm-evaluation-harness/blob/v0.4.13/docs/API_guide.md#L104), but offers a less direct fit than Promptfoo’s case/provider comparison workflow.

**W3 — do not commission a new eight-arm harness yet.** AMB’s [registry](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/memory/__init__.py#L15) covers **Hindsight and cognee**. Coverage among the eight requested systems is:

- AMB: **2/8**.
- [Supermemory MemoryBench](https://github.com/supermemoryai/memorybench/blob/94e2af54b661d90e77dddbd8fa4fa5b28c07a24e/src/providers/index.ts#L9): **0/8**; adapts Supermemory, Mem0, Zep, filesystem and RAG.
- [THUIR MemoryBench](https://github.com/THUIR/MemoryBench/blob/247ba8c1e327fa297c0d57aaad0e3cbd66bac656/README.md#L166), [mem0’s suite](https://github.com/mem0ai/memory-benchmarks/tree/4b61c5d31b9c668a12b4f5e78064248a02c82d2b), and [Letta Evals](https://github.com/letta-ai/letta-evals/tree/688e099a70295a281ea3667398fb53b4d7af89d4): **0/8** in reviewed adapters.
- Native LongMemEval: **0/8 service adapters**, but the required scorer.

Retain [LongMemEval `eval_utils.py:24–46`](https://github.com/xiaowu0162/LongMemEval/blob/9e0b455f4ef0e2ab8f2e582289761153549043fc/src/retrieval/eval_utils.py#L24): `recall_all@5` means **every gold session appears among five unique retrieved sessions**, a binary question-level result—not fractional recall or answer accuracy. AMB’s retrieval-only mode uses different assertions.

```bash
git clone https://github.com/vectorize-io/agent-memory-benchmark.git
cd agent-memory-benchmark
git checkout 03c1d0f1d27da63034f0931121c858faba512383
uv run amb providers
uv run amb run --dataset longmemeval --split s --memory hindsight
uv run amb run --dataset longmemeval --split s --memory cognee
```

These cover a subset only. OpenAI answer-model configuration exists, but the [CLI unconditionally requires a Gemini key](https://github.com/vectorize-io/agent-memory-benchmark/blob/03c1d0f1d27da63034f0931121c858faba512383/src/memory_bench/cli.py#L25). GPT-6 through a custom URL for every system’s backbone, unchanged scoring, and lifecycle acceptance remain unresolved.

**W4 — explicitly select LoCoMo.** Its first verified MTEB release is **2.13.8, May 19**; it remains [registered in 2.21.8](https://github.com/embeddings-benchmark/mteb/blob/2.21.8/mteb/tasks/retrieval/eng/lmeb_retrieval.py#L996). Use the [upstream two-stage example](https://github.com/embeddings-benchmark/mteb/blob/2.21.8/docs/get_started/advanced_usage/two_stage_reranking.md#L23):

```bash
pip install 'mteb==2.21.8'
mteb run -m sentence-transformers/static-similarity-mrl-multilingual-v1 -t LoCoMo --prediction-folder w4-predictions
python -c 'import mteb; t=mteb.get_task("LoCoMo").convert_to_reranking("w4-predictions",top_k=100); mteb.evaluate(mteb.get_model("cross-encoder/ms-marco-TinyBERT-L2-v2"),t)'
```

These models reproduce the upstream example; substitute frozen evaluation arms. BEIR **v2.2.0**, June 4, 2025, has zero commits since cutoff and needs LoCoMo conversion. MTEB’s LoCoMo dataset license is separately CC-BY-NC-4.0.

**W5 — replace statistical algorithms, preserve the estimand.**

```bash
pip install 'scipy==1.18.1' 'statsmodels==0.15.0'
```

There is no upstream CLI consuming the local li26/S3 format. Bind existing data/scoring to these supported APIs:

- [`bootstrap`](https://github.com/scipy/scipy/blob/v1.18.1/scipy/stats/_resampling.py#L363): `paired=True, method="percentile", confidence_level=.95, alternative="greater", n_resamples=10000`.
- Resample **question-cluster IDs**, retaining both arms and all observations within each sampled cluster. Recompute aggregate metrics.
- [`permutation_test`](https://github.com/scipy/scipy/blob/v1.18.1/scipy/stats/_resampling.py#L1705): `permutation_type="samples"` for paired swaps, respecting cluster boundaries.
- [`multipletests`](https://github.com/statsmodels/statsmodels/blob/v0.15.0/statsmodels/stats/multitest.py#L233): `method="holm"` on valid family p-values.
- Predeclare non-inferiority margin δ; compare the one-sided lower bound with `−δ`, with the multiplicity policy specified separately.

Cluster-robust covariance is not cluster bootstrap. arch is the bootstrap-focused runner-up; Pingouin adds no necessary primitive here.

**W6 — run upstream suites, then add task-quality acceptance where absent.** Source-checkout commands below require the linked tag.

- **[RTK v0.50.0](https://github.com/rtk-ai/rtk/blob/v0.50.0/scripts/benchmark.sh#L31)** — Sep 24; 881 commits; Apache-2.0. Install: `cargo install --git https://github.com/rtk-ai/rtk --tag v0.50.0 --locked`. Run `rtk verify --require-all`; `bash scripts/benchmark.sh`. Benchmark tokens are characters/4 estimates; no agent-quality gate.
- **[context-mode v1.0.169](https://github.com/mksglu/context-mode/blob/v1.0.169/tests/ecosystem-benchmark.ts#L449)** — Jun 29; 146; Elastic-2.0. Install `npm install -g context-mode@1.0.169`; checkout: `npm install && npm run test:ecosystem`. Measures execution/bytes, not answer quality.
- **[Headroom v0.39.1](https://github.com/headroomlabs-ai/headroom/blob/v0.39.1/headroom/evals/README.md#L108)** — Sep 26; 1,154; Apache-2.0. `pip install 'headroom-ai[evals]==0.39.1'`; `python -m headroom.evals suite --tier 1 --ci`. Provides before/after quality evaluations; still needs the actual workflow.
- **[jCodeMunch v1.108.319](https://github.com/jgravelle/jcodemunch-mcp/blob/v1.108.319/benchmarks/competitive/run.py#L1)** — Sep 16; 1,080; Dual-Use 1.1. `pip install 'jcodemunch-mcp==1.108.319' tiktoken`; `python benchmarks/competitive/run.py --adapters null_readall,null_grep,jcodemunch --runs 20 --sandbox none`. Citation F1 and baselines; not completed coding-task quality.
- **[Serena v1.7.0](https://github.com/oraios/serena/blob/v1.7.0/docs/04-evaluation/020_prompts/000_prompts.md#L3)** — Aug 9; 442; **MIT at this tag**. `uv tool install -p 3.13 'serena-agent==1.7.0'`. Use upstream evaluation prompts; no standalone deterministic benchmark command found. Self-evaluation is insufficient for independent acceptance.
- **[QMD v2.8.3](https://github.com/tobi/qmd/blob/v2.8.3/README.md#L1058)** — Aug 16; 110; MIT. `npm install -g @tobilu/qmd@2.8.3`; then `qmd collection add test/eval-docs --name eval-docs`, `qmd embed -c eval-docs`, `qmd bench src/bench/fixtures/example.json --json`. Retrieval quality/latency, not downstream answer quality.
- **[TOON v4.1.1](https://github.com/toon-format/toon/blob/v4.1.1/benchmarks/README.md#L8)** — Aug 5; 135; MIT. `npm install -g @toon-format/cli@4.1.1`; checkout `pnpm install`; in `benchmarks/`, run `pnpm benchmark:tokens` and `pnpm benchmark:accuracy`. Deterministic answer scoring covers comprehension, not generation quality.

Keep [token_manifest.py](~/code/native-agent-stack/tools/token-report/token_manifest.py) for accounting and [native_token_ci.py](~/code/native-agent-stack/scripts/native_token_ci.py:2) for integration fixtures; its existing documentation already distinguishes these evidence levels.

**W7 — load targeted upstream skills.** Installed cached **Vercel skills 1.7.0** discovery was actually run for skill-creator, E2E, testing and property-based testing; no installation occurred.

Load the existing Anthropic skill-creator copy recorded by adoption, rather than installing a duplicate. Its [paired benchmark procedure](https://github.com/anthropics/skills/blob/33375500bcea98d610eb30ce10ac4e59b89c390d/skills/skill-creator/SKILL.md#L169) consumes completed runs with:

```bash
python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
```

For a clean host:

```bash
npx skills@1.7.0 add https://github.com/anthropics/skills/tree/33375500bcea98d610eb30ce10ac4e59b89c390d/skills/skill-creator -a codex claude-code -y
```

Load Superpowers verification for W1–W6 and TDD for integration changes: **v6.4.2**, Sep 25, 74 commits, MIT. Load Trail of Bits property-based-testing for parser/scorer invariants: **0cc1c73a5e96749ab32d7ea5e14892fafa6972ae**, Sep 24, no release, 81 commits, CC-BY-SA-4.0. Harbor’s [Rewardkit skill](https://github.com/harbor-framework/harbor/blob/v0.23.0/docs/content/docs/rewardkit/index.mdx#L9) specifically fits W1 verifier construction. `mcp-builder` fits MCP implementation changes; webapp-testing has no W1–W6 browser requirement.

**Records retained or overturned:** retain Promptfoo 0.123.1 for W2 and MLflow’s conditional tracking status. Narrow Inspect’s default for W1; correct its “unversioned” metadata using [0.3.271’s tag/changelog](https://github.com/UKGovernmentBEIS/inspect_ai/blob/0.3.271/CHANGELOG.md#L1). Update MTEB 2.21.0 to 2.21.8 and replace W4’s LongMemEval selection with LoCoMo. Correct li26’s **2.5th-percentile** lower endpoint to the requested **5th percentile**. Superpowers [renamed `testing-anti-patterns.md` to `writing-good-tests.md`](https://github.com/obra/superpowers/blob/v6.4.2/RELEASE-NOTES.md#L130). Preserve community-sweep R18’s rejection of blanket `networkidle`; the current Anthropic skill still contains it. No source review here establishes new acceptance.

**Not found:** S3 `PREREGISTRATION.md` in this checkout; a complete unchanged W1 gate/Loki reconciler; an eight-system S3 command preserving the required metric; or a turnkey li26 statistical CLI. Those gaps should not be filled by inventing another harness.

TOKEN TOOLS USED: RTK: bounded CLI output, context-mode: API/source processing, Serena: exact statistical symbol inspection, QMD: recorded-document retrieval, ai-memory: historical decision leads.