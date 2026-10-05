# Keyless web-search comparison — 2026-10-05

Status: preregistration; no measured verdict. This unit serves the north-star
research/adoption workflow used to build complex systems and the US-equities
research and historical-simulation stack.

Ruling 12 requests a scoped comparison of current keyless search against an
isolated SearXNG deployment. The two arms are unchanged DeerFlow v2.1.0 tools:
DuckDuckGo/DDGS 9.14.1 with `backend: auto`, and SearXNG at source
`d48c4b555421e824342c51d68482dd0898e54d0f`. DDGS auto is a multi-engine baseline;
this experiment does not claim it is pure DuckDuckGo. Brave and Tavily are out.
The previously prepared thirty query texts and order remain unchanged; only the
old keyed-arm and install-row proposals are superseded.

The maintained upstream search tools already implement both integrations. A
small promptfoo Python provider supplies its documented return protocol and
DeerFlow's scoped AppConfig, then calls the original native `web_search_tool`.
It leaves returned JSON unchanged: DDGS uses an object containing `results`,
whereas SearXNG uses a list. The scorer accepts both native formats. Neither
runtime, search client nor evaluation runner is reimplemented.

## Frozen method and decision rule

The corpus contains thirty public foundation software/doc/release queries,
three independent repeat rounds, and five returned results per call. Frozen
primary URL/path families are an operational target for source discovery, not
ground truth for answer correctness or completeness. Promptfoo 0.123.1 scores
every native response with contract validity, nonempty usable results, primary
hit@5, first-primary MRR@5 and distinct URL fraction. Error objects, malformed
JSON, HTML challenges, invalid URLs and empty results receive zero primary
credit. Every attempted call stays in its denominator. Duplicate URLs cannot
increase hit or reciprocal-rank credit.

Usable results require valid HTTP(S) URLs plus nonblank native titles and
snippets/content. Native provider errors short-circuit promptfoo assertions, so
missing named scores on those rows are zero-credit outcomes rather than omitted
observations ([evaluator source](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/evaluator.ts#L1342)). All individual metrics retain positive assertion weights because promptfoo's
named scores are weighted; the decision uses each named metric, never its
combined average score. Offline controls confirm rank-five MRR=0.2 and duplicate
distinctness=0.5, with all other invalid/unrelated controls rejected.

The statistical unit is each paired query's mean over three repeats, giving
thirty pairs rather than ninety independent observations per arm. SearXNG wins
only if all preregistered conditions hold: mean primary hit@5 improves by at
least 0.10; a one-sided exact sign test on positive versus negative, non-tied
paired query differences gives p<0.05; usable-result rate is at least the
baseline rate minus 0.02; and native-call p95 latency is at most 30 seconds and
at most twice baseline p95. MRR and duplicate fraction are secondary reported
metrics and cannot rescue a failed primary gate. Zero non-tied pairs gives p=1.
The exact binomial upper tail is sum(comb(n,k) for k=wins..n)/2**n. Latency p95
uses nearest rank ceil(0.95*n), and includes failed calls when native latency is
present. Missing latency prevents a latency gate from passing.

If no candidate win is established, retain the current BY_DESIGN search
disposition within this corpus; uncertainty and power limits remain explicit.
This is not a claim of general equivalence. If SearXNG wins, propose a provider
owner row with this scoped evidence; plan staging and host acceptance remain
with their owners. No installation or readiness change occurs from this
measurement alone. The overturn condition is another source-pinned matched
trial satisfying these same gates on representative research queries, or a
maintained upstream change that invalidates the tested configurations.

## Native execution and isolation

Promptfoo is the only evaluation runner. Each round uses three native batches
of ten queries selected by frozen native `--filter-pattern` expressions in query
order. Every query still receives three calls per arm. Each batch uses the CLI with
`--repeat 1 --max-concurrency 1 --delay 1000 --no-cache --no-share --no-write
--no-table --no-progress-bar --output <round.json>`. Round order alternates the
provider list (baseline/candidate, candidate/baseline, baseline/candidate),
preserving all query texts/order and scoring. Its documented Python interpreter
environment variable selects the existing locked DeerFlow environment. Each
provider uses one native worker and a 60-second native provider timeout. The
unchanged SearXNG client uses a 30-second HTTP timeout; no retries are added by
this adapter. Upstream engine retries remain unknown unless returned natively.
Native promptfoo exit 100 denotes a scored failure and is retained separately
from process execution failure.

Offline controls exercise native promptfoo `providerOutput` before live calls,
covering a correct response, empty/error outputs, malformed JSON, HTML challenge,
invalid URL, valid unrelated results, duplicate hits and an expected source
outside the first five. They are synthetic local integration checks, not web
search or upstream runtime acceptance. Provider/import checks and container
health checks have separate scopes and do not enter the search denominators.

SearXNG uses the published upstream image
`searxng/searxng:2026.10.4-d48c4b555@sha256:76b0bf285aca014c7191fc4d9234c4bfb358624ac33d8883833d496c059ec072`.
Official publication and native container CI run 37182502127 bind it to the
source commit. Deployment uses the existing rootless Docker daemon, a loopback
port, lane-owned config/cache directories, upstream default engines and the
supported JSON-format setting. It is measurement-only and removed afterward.
No install.sh, shared plan row, service restart, rootful daemon or source/image
build is used. One heavy step runs at a time; rounds are started only when they
can stop before the strict paper windows. Each twenty-call batch starts only
with at least 22 minutes remaining before a window, accounting for sixty-second
provider deadlines, delays and startup. Interrupted attempts and their causes
are retained; a window never silently drops a failed call.

Actual native output, timestamps, exit codes and pin observations will be kept
with the results. Provider-native token and internal-retry counts are unknown;
no savings claim is made. Only bounded sanitized public-query outputs enter the
repository. Private host paths/configuration and side-project identities stay
out. Native container/search execution, local scoring controls, source review
and structural validation remain separate evidence classes.

The completeness critic requires future financial/regulatory, primary-paper/PDF,
freshness-sensitive and ambiguous-query corpus coverage. Frozen q27 contains an
ambiguous cache-mode phrase; an official workflow-reference URL hit cannot
establish that capability. Source-topic queries accept official current-branch
aliases and do not establish version accuracy. The unchanged DeerFlow SearXNG
tool omits native per-engine diagnostics from its normalized output; retained
container logs/configuration are separate observations, and unavailable
per-query engine/retry counters remain unknown.

## Primary sources

- [DeerFlow v2.1.0 config search bindings](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/config.example.yaml#L804), [DDGS native tool/output](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/community/ddg_search/tools.py#L156), [SearXNG native tool](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/community/searxng/tools.py#L37), [HTTP client](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/community/searxng/searxng_client.py#L34), and [scoped AppConfig](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/config/app_config.py#L768).
- [promptfoo 0.123.1 Python provider](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/providers/python.md#L102), [native assertions](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/configuration/expected-outputs/javascript.md#L203), [precomputed control output](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/configuration/reference.md#L65), and [native eval options](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/commands/eval.ts#L141).
- [SearXNG supported container deployment](https://github.com/searxng/searxng/blob/d48c4b555421e824342c51d68482dd0898e54d0f/docs/admin/installation-docker.rst#L173), [default search formats](https://github.com/searxng/searxng/blob/d48c4b555421e824342c51d68482dd0898e54d0f/searx/settings.yml#L83), [settings overlay](https://github.com/searxng/searxng/blob/d48c4b555421e824342c51d68482dd0898e54d0f/searx/settings_loader.py#L130), and [published upstream container CI](https://github.com/searxng/searxng/actions/runs/37182502127). The archived searxng-docker repository is not used.
