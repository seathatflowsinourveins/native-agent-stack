# Keyless web-search comparison — 2026-10-05

Status: observed; retain current DDGS(auto) BY_DESIGN within the frozen corpus.
This unit serves the north-star
research/adoption workflow used to build complex systems and the US-equities
research and historical-simulation stack.

Ruling 12 requests a scoped comparison of current keyless search against an
isolated SearXNG deployment. The two arms are unchanged DeerFlow v2.1.0 tools:
DuckDuckGo/DDGS 9.14.1 with `backend: auto`, and SearXNG at source
`d48c4b555421e824342c51d68482dd0898e54d0f`. DDGS auto is a multi-engine baseline;
this experiment does not claim it is pure DuckDuckGo. Separate keyed Brave and
Tavily arms are excluded; DDGS' internal keyless engine selection is unchanged.
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
three separate repeat rounds, and five returned results per call. Frozen
primary URL/path families are an operational target for source discovery, not
ground truth for answer correctness or completeness. Promptfoo 0.123.1 scores
every native response with contract validity, nonempty usable results, primary
hit@5, first-primary MRR@5 and distinct URL fraction. Error objects, malformed
JSON, HTML challenges, invalid URLs and empty results receive zero primary
credit. Every attempted call stays in its denominator. Duplicate URLs cannot
increase hit or reciprocal-rank credit. Distinctness counts exact returned URL
strings, not canonical URLs. Promptfoo cache bypass does not establish search
engine or index independence; the nominal sign-test p-value is scoped to this
fixed corpus and these repeated tool calls.

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
The exact binomial upper tail is sum(comb(n,k) for k=wins..n)/2**n, corresponding
to the documented [one-sided binomial test](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html)
with p=0.5 and alternative='greater'. Latency p95
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

Actual native output, timestamps, exit codes and pin observations are retained
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

Source correction during execution review: the frozen adapter supplies
`deerflow.sandbox.local:LocalSandbox` in AppConfig's required sandbox field.
The upstream exported provider selector is
`deerflow.sandbox.local:LocalSandboxProvider`
([config.example.yaml:1437](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/config.example.yaml#L1437),
[local module export](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/sandbox/local/__init__.py#L1)).
This field is never resolved or instantiated by the direct native search-tool
calls; both tools read only their scoped tool configuration. The measured
adapter remains frozen, and its results establish no sandbox-provider acceptance
or reusable full-runtime configuration. A future reusable adapter must use the
documented provider selector. Source and frozen-byte checks, rather than an
assumed sandbox capability, determine the scope of this experiment.

## Measured result and owner handoff

The preregistration was published before live search calls in source commit
`05481fc85e6dfcdf46f8e45a893886250ea0a0a3` on draft #718.
All nine native promptfoo batches completed, with 180 cells covering every query,
arm and round exactly once. All frozen variables, provider order, one-worker
settings and cache-off settings match the published pack. Every cell retains a
numeric native latency and its actual output; no provider error, missing score,
interrupted batch or added retry occurred. Every enclosing CLI returned graded
exit 100, which does not mean every individual search failed.

| Metric, 90 attempted calls per arm | Current DDGS(auto) | SearXNG |
| --- | ---: | ---: |
| Native JSON contract valid | 90/90 | 90/90 |
| Nonempty usable results | 90/90 | 18/90 |
| Primary-source hit@5 | 33/90 (36.67%) | 12/90 (13.33%) |
| Mean first-primary MRR@5 | 0.3361 | 0.1028 |
| Mean exact-URL distinctness, empty=0 | 1.0000 | 0.2000 |
| Native provider-call p95 | 31,713 ms | 3,952 ms |

SearXNG returns 72 valid empty lists. Its first twenty calls yield fifteen usable
responses; the remaining seventy yield three, including none in the final twenty
post-hold calls. The retained container log contains CAPTCHA, rate-limit and
timeout records, but those emitted records can duplicate conditions and do not
establish per-query causes. The [controls and cleanup receipt](../../evidence/artifacts/web-search-comparison-20261005/checks-and-cleanup.json)
keeps the exact log hash, bounded diagnostic counts and independent removal
observation. Its latency gates pass, but its primary-hit
gain is -7/30 (-23.33 percentage points) and its usable-result change is -4/5
(-80 percentage points). Across thirty paired query means, the candidate wins
three, loses thirteen and ties fourteen; the predeclared greater-tail sign test
gives 65399/65536 = 0.9979095459. The gain, sign-test and usable-rate gates fail.
These are source-discovery results on this fixed corpus and host configuration,
not a general claim that the providers are equivalent or that one is universally
better.

Retain the current BY_DESIGN disposition. Do not propose a SearXNG READY owner row
from this measurement. The command center retains provider selection, plan
staging, cross-family review and landing. This lane changed no shared install
plan or provider configuration.

The [derived summary](../../evidence/artifacts/web-search-comparison-20261005/summary.json)
contains all thirty paired-query results and nine batch timestamps.
The [observed experiment](../../evidence/artifacts/web-search-comparison-20261005/experiment.json)
keeps eighteen arm views of nine shared CLI processes, with literal exit 100,
null aggregate semantic/contract quality and unknown usage. It assigns no
provider subprocess exit and declares no qualification run. Compact native
receipts preserve returned URL order, field-validity flags, native grades,
scores, counters and latency. Their hashes identify exact private native exports
and exact decoded-output UTF-8 bytes. Native cell/evaluation identifiers are
published only as SHA-256 of their exact UTF-8 strings; literal identifiers and
full titles/snippets/output remain in those
retained originals for independent observation. The immutable
`preregistered-experiment.json` stays alongside the observed record.

The strict paper-window hold separates round 3's first batch from its final two.
The service retained its upstream engine state during that hold; no tuning,
restart or rescore occurred. Batch timestamps are native observations, and no
per-call timestamps or hidden engine-retry counts are invented. The service and
owned config/data were removed after measurement using the existing rootless
daemon. A mapped-UID permission error on the first state deletion was corrected
within the rootless user namespace using the cached upstream image and
`--network none --pull never`. Native Docker/container and directory-absence
observations establish removal; inconclusive loopback timeouts are not absence
proof. [Docker's rootless documentation](https://docs.docker.com/engine/security/rootless/)
and installed Docker 29.8.2 `run --help` support this namespace/entrypoint cleanup.

The completeness critic feeds the next sweep with domain-balanced financial and
regulatory queries, primary papers/PDFs/tables, non-English official sources,
freshness and ambiguous-capability questions, source redirects/HTML.md aliases,
current-versus-pinned-version pairs, canonical duplicate variants, engine-health
observation and time-blocked confirmation. A future owner-qualified current DDGS
baseline belongs in a new matched trial. These findings do not change the frozen
oracle or rescue the failed gates. A new preregistered representative comparison
meeting the same quality/usable/latency gates, or an upstream change invalidating
these tested configurations, overturns this scoped retain verdict.


## Primary sources

- [DeerFlow v2.1.0 config search bindings](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/config.example.yaml#L804), [DDGS native tool/output](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/community/ddg_search/tools.py#L156), [SearXNG native tool](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/community/searxng/tools.py#L37), [HTTP client](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/community/searxng/searxng_client.py#L34), and [scoped AppConfig](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/packages/harness/deerflow/config/app_config.py#L768).
- [promptfoo 0.123.1 Python provider](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/providers/python.md#L102), [native assertions](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/configuration/expected-outputs/javascript.md#L203), [precomputed control output](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/site/docs/configuration/reference.md#L65), and [native eval options](https://github.com/promptfoo/promptfoo/blob/34f74d34e140b5e17d23770dfb2340057b1936b8/src/commands/eval.ts#L141).
- [SearXNG supported container deployment](https://github.com/searxng/searxng/blob/d48c4b555421e824342c51d68482dd0898e54d0f/docs/admin/installation-docker.rst#L173), [default search formats](https://github.com/searxng/searxng/blob/d48c4b555421e824342c51d68482dd0898e54d0f/searx/settings.yml#L83), [settings overlay](https://github.com/searxng/searxng/blob/d48c4b555421e824342c51d68482dd0898e54d0f/searx/settings_loader.py#L130), and [published upstream container CI](https://github.com/searxng/searxng/actions/runs/37182502127). The archived searxng-docker repository is not used.
