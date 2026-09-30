# Native runtime worker candidates

Use one native coordinator and a bounded worker for the current task. These
recipes compose maintained upstream runtimes; they do not replace native agent
loops, native sign-ins, caching or compaction. Each candidate has its own
installation, task contract, state, cleanup and acceptance boundary. A passing
fixture or a source pin does not promote the entire roster.

| Task | Source-backed runtime and integration | Current qualification |
| --- | --- | --- |
| Claude research, review and GitHub coordination | Native Claude Code and [reviewed role/workflow dispatch](../../examples/claude-native/workflows/README.md); [direct cross-session coordination receipt](../../docs/decisions/2026-09-30-runtime-worker-coordination.md) | Actual peer replies received; default-harness owner retains global SDK/config promotion |
| Programmatic GPT tools and thread recovery | Official [Codex Python SDK 0.159.2](https://github.com/openai/codex/tree/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python), native custom-provider config through OmniRoute Responses | Separate shared-lane follow-up branch: real dynamic tool and new-process resume; bounded local integration, not a default promotion |
| Coding, planning, review, browser and bounded child tasks | [OpenHands SDK/server 1.50.0](openhands/README.md), eight task profiles, native planning/browser/TaskToolSet, persistence and bounded goal review | 1,208 selected unchanged upstream tests passed; live image, independent observer and task-quality gates pending |
| Grounded report research | [GPT Researcher v3.7.0](gpt-researcher/README.md), native keyword context and LangChain Responses configuration | Native install and 24 selected unchanged tests; no report/citation-quality acceptance |
| Multi-step research runtime | [DeerFlow v2.1.0](deerflow/README.md), source-backed ChatOpenAI Responses adapter and scoped extensions | Native install/CLI, 309 selected backend tests and 8 GAIA scorer tests; upstream dependency override and live runtime gates remain |
| Browser crawling and deterministic extraction | [Crawl4AI v0.9.4](crawl4ai/README.md), model-free REST jobs for a separate Responses caller | Real model-free native job and 16 unchanged extraction tests; no end-to-end caller quality acceptance |
| Task-scoped skills | [Pinned skill trial](skills/README.md), native description discovery and body loading when invoked | Trial remains unaccepted; source freshness and native discovery are narrower than invocation evidence |

Exact research-roster outputs, failures and source hashes are in the
[qualification artifacts](../../evidence/artifacts/runtime-roster-20260930/README.md).
OpenHands' [upgrade outputs](openhands/evidence/upgrade-150-commands.json) and
[image triage](openhands/evidence/image-triage-20260930.json) remain separate.
The Codex SDK follow-up is held for the Claude owner's pin promotion and the
shared-lane acknowledgement; its actual thread total is excluded from Gate A.

## Route and state contract

The qualification route is the explicit `cx/gpt-6-astra-max` alias on the clean
loopback OmniRoute lane, using Responses and max effort. It records the plan's
explicit model choice; it does not replace current Sol/Ultra coordination and
Sol/Max worker defaults. Claude uses its native model/account path. A separate
20129 compression arm is a candidate requiring fresh model discovery and a
matched quality/usage comparison. Older `sharedgw/*` recipes are historical
trial inputs, not evidence that those aliases are currently advertised.

Keep provider selection, model, effort, route discovery and actual execution
distinct. Do not add sampling parameters unsupported by the selected reasoning
route. Crawl4AI's native LLM extraction uses Chat Completions and remains an
explicitly selected, unqualified comparison; default crawling uses no model.
No optional embedding, memory or GPU service starts merely because a recipe
lists it. Native credentials remain native and private.

Each writing worker needs an owned checkout and bounded paths. Child tasks,
goal judges, persistence, interruption and resume use the selected upstream
runtime's supported interfaces. OpenHands limits TaskToolSet fan-out to two
children, child iterations to twelve and goal review to three. Its goal judge
has a separate usage ID. Local server profiles and the Cloud profiles API are
different interfaces; source inspection does not qualify a Cloud API on the
local server.

## Skills, extensions and token practice

Load the task profile's selected skills and reachable tools. The trial's broad
inventory is a source catalog; it is not a startup prompt or an instruction to
install every skill. Native discovery provides names/descriptions; invocation
loads the selected body. Resources are part of a skill's source tree, so an
unchanged `SKILL.md` alone cannot qualify changed resources. GPT Researcher
configuration or DeerFlow extension metadata does not prove that an arbitrary
`SKILL.md` body was loaded. Record actual invocation separately.

Use exact-source reads, lexical retrieval, compact tool results and context
processing according to the information needed. Keep native caches and
compaction. Measure complete attempts before changing a default: parents,
children, retries, failed conditions and judges belong to the same experiment.
Count the final cumulative native thread snapshot once; cache and reasoning
subsets are not additional tokens. Unknown provider/whole-task usage stays
unknown. No enclosing-task saving is claimed by these receipts.

## Gates before broader adoption

Run the existing source-pinned native quality tasks and discriminating controls
for the requested capability: OpenHands' SWE-bench harness, GPT Researcher's
DeepResearch-Bench-II grader, DeerFlow's GAIA scorer and Crawl4AI's deterministic
extraction assertions. For review and GitHub repair, freeze the seeded defect
or failing-check oracle and independently inspect the resulting diff and native
check. Grader installation or a mocked tool stream is not a task-quality pass.
Hosted GitHub Actions validate deterministic artifacts; native Claude runs
retain their own host/model evidence.

OpenHands' full image needs maintained replacement inputs and a native rescan.
The host-owned observer must independently bind skills/tool events and source
versions to the inputs; worker-writable event files cannot provide that claim.
Gate A/P3, compression quality and whole-task metering remain open. The current
foundation catalog and dashboard retain these gates instead of treating the
roster as accepted.
