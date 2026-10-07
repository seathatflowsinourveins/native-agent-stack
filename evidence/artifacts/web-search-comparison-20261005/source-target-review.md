# Primary-source target review

The executable URL-family oracle is frozen in `queries.yaml` at preregistration
source `05481fc85e6dfcdf46f8e45a893886250ea0a0a3`, before live search. An independent
read-only reviewer verified the primary paths before freezing; root reread
selected pinned source, exact release APIs and current official documentation.
These locators support source-discovery scoring, not semantic answer truth.

| Queries | Primary locator and verification basis |
| --- | --- |
| q01–q05 | [promptfoo Python provider](https://www.promptfoo.dev/docs/providers/python/), [HTTP provider](https://www.promptfoo.dev/docs/providers/http/), [configuration](https://www.promptfoo.dev/docs/configuration/reference/), [Python assertions](https://www.promptfoo.dev/docs/configuration/expected-outputs/python/), [metrics](https://www.promptfoo.dev/docs/configuration/expected-outputs/); equivalent exact documentation paths at promptfoo@34f74d34e140b5e17d23770dfb2340057b1936b8 |
| q06–q08 | [DeerFlow@345f08be config.example.yaml:804](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/config.example.yaml#L804), corresponding unchanged DDGS/SearXNG/Tavily source paths. Tavily is a query topic, never an eligible provider arm. |
| q09 | [DeerFlow tagged client.py](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/client.py) and README |
| q10 | [GPT Researcher@0957c301 cli.py:336](https://github.com/assafelovic/gpt-researcher/blob/0957c301ed06c2a5857b834358c7227c739041d4/cli.py#L336) and README; source-family scoring does not establish a working packaged CLI |
| q11–q15 | [SearXNG container](https://docs.searxng.org/admin/installation-docker.html), [search API](https://docs.searxng.org/dev/search_api.html), [search settings](https://docs.searxng.org/admin/settings/settings_search.html), [official image](https://hub.docker.com/r/searxng/searxng), [outgoing settings](https://docs.searxng.org/admin/settings/settings_outgoing.html), [engine settings](https://docs.searxng.org/admin/settings/settings_engines.html); equivalent exact source paths at d48c4b555421e824342c51d68482dd0898e54d0f |
| q16 | [promptfoo0.123.1 release](https://github.com/promptfoo/promptfoo/releases/tag/0.123.1), native release API published2026-09-18T01:07:54Z |
| q17 | [DeerFlowv2.1.0 release](https://github.com/bytedance/deer-flow/releases/tag/v2.1.0), published2026-09-24T10:40:44Z |
| q18 | [GPT Researcherv3.7.0 release](https://github.com/assafelovic/gpt-researcher/releases/tag/v3.7.0), published2026-09-26T17:46:25Z |
| q19 | [OpenHands SDKv1.52.0 release](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.52.0), published2026-10-05T04:10:05Z |
| q20 | [Harborv0.23.0 release](https://github.com/harbor-framework/harbor/releases/tag/v0.23.0), published2026-09-12T04:55:17Z; verified v-prefix |
| q21 | [Inspect evaluation logs](https://inspect.aisi.org.uk/eval-logs.html), [metrics](https://inspect.aisi.org.uk/metrics.html), [errors](https://inspect.aisi.org.uk/handling-errors.html), [limits](https://inspect.aisi.org.uk/setting-limits.html); frozen official HTML/HTML.md aliases |
| q22 | [Current Harbor docs](https://docs.harborframework.com/), its pre-integrated agents/sandboxes pages, documented legacy harborframework.com/docs redirect and upstream README |
| q23 | [open_deep_research@1b7d2e80 configuration.py:78](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/configuration.py#L78) and README |
| q24 | [Stanford STORM](https://github.com/stanford-oval/storm), [primary paper](https://arxiv.org/abs/2402.14207), official storm-project.stanford.edu; retrieval eligibility is separate from runtime maintenance/adoption |
| q25 | [DDGS@70a56355 README:167](https://github.com/deedy5/ddgs/blob/70a5635510fb8d5b15d5ba6ceced6a67e212149b/README.md#L167) and [PyPI](https://pypi.org/project/ddgs/) |
| q26 | [GitHub reusable workflow documentation](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows) |
| q27 | [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax); the frozen cache-mode phrase is ambiguous, so a URL hit establishes only the broad source family |
| q28 | [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/) |
| q29 | [uv tools guide](https://docs.astral.sh/uv/guides/tools/), independently HTTP403 in that review; [verified source@46b84fd0:195](https://github.com/astral-sh/uv/blob/46b84fd0bfec23b72f29e8e2185ba68a65052f48/docs/guides/tools.md#L195) is the authoritative fallback |
| q30 | [OpenTelemetry Collector configuration](https://opentelemetry.io/docs/collector/configuration/) |

Patterns require a parsed HTTP(S) host and bounded path. Query strings/fragments
do not supply primary credit, and lookalike hosts fail the controls. Exact release
tag URLs are required for q16–q20. Source-topic paths accept official branch
aliases without claiming retrieved-version correctness; frozen aliases may be
underinclusive. The corpus has no full-answer, multilingual, image/PDF or
financial/regulatory quality oracle. These gaps feed the next landscape sweep.

Statistical reference: [SciPy binomtest](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html).
The preregistered exact binomial upper tail uses non-tied paired query means,
not the ninety repeated calls as independent units. Native promptfoo metrics
remain the scores; later arithmetic only aggregates them.
