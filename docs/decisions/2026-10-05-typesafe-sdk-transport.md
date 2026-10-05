# TypeSafe crosswalk transport through the vendor SDK

Date: 2026-10-05. Scope: `tools/sota-convergence/gap_crosswalk.py::call()`.
This serves the north-star research stack by maintaining the existing landscape
gap judgments without duplicating the vendor's HTTP and retry implementation.
It authorizes no new model run or reinterpretation of recorded judgments.

## Decision and compatibility gates

Use the published `typesafe-sdk==0.7.2` wheel, from
`typesafe-ai/typesafe-sdk-python@v0.7.2`, commit
`f078f1e208a0d885154dc758344ae4fce77ac168`, through its public
`TypeSafeClient.system_one()` and `RetryPolicy`. The release was published on
2026-09-26. Import it only inside `call()`, reached by `judge`; an absent or
different SDK fails with the pinned `uv run --with typesafe-sdk==0.7.2` command.
`build`, `build --check` and `score` retain their standard-library dependency
boundary. The existing environment-only API-key consumer is unchanged.

All three prerequisite gates pass by source review:

1. Dict-shaped instructions and criteria are JSON content in
   [ChoiceModel:39-49](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f078f1e208a0d885154dc758344ae4fce77ac168/src/typesafe_sdk/_core/question_types.py#L39).
   [normalize_questions:10-23](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f078f1e208a0d885154dc758344ae4fce77ac168/src/typesafe_sdk/_core/questions.py#L10)
   accepts the existing raw choice dictionaries; no prompt conversion is added.
2. The response preserves
   [usage:65-73](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f078f1e208a0d885154dc758344ae4fce77ac168/src/typesafe_sdk/_core/response_types.py#L65),
   [choice probabilities:25-30](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f078f1e208a0d885154dc758344ae4fce77ac168/src/typesafe_sdk/_schemas/models.py#L25),
   and [public raw HTTP metadata:81-94](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f078f1e208a0d885154dc758344ae4fce77ac168/src/typesafe_sdk/_core/schemas/base.py#L81).
   Native `model_dump(mode="json")` supplies the existing `validate()` input.
   Reading the raw header retains the prior optional request ID; the SDK's
   stricter `request_id` property would reject a missing header.
   A strict SDK schema now sits between the wire response and `validate()`
   and the ledger. The [base schema:21](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f078f1e208a0d885154dc758344ae4fce77ac168/src/typesafe_sdk/_core/schemas/base.py#L21)
   uses `extra="ignore"` and `strict=True`; the
   [ChoiceAnswer schema:19-24](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f078f1e208a0d885154dc758344ae4fce77ac168/src/typesafe_sdk/_schemas/models.py#L19)
   requires `confidence`. The
   [response preparation:86-93](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f078f1e208a0d885154dc758344ae4fce77ac168/src/typesafe_sdk/_core/response_types.py#L86)
   drops answers of unknown type from the parsed response. This loses nothing
   on every retained successful recorded row:
   [eval judgments](../../evidence/artifacts/gap-crosswalk-92bb279/typesafe-eval.json)
   contain 315 rows / 1,039 answers and
   [current judgments](../../evidence/artifacts/gap-crosswalk-92bb279/typesafe-current.json)
   contain 380 rows / 1,215 answers. All 695 rows contain modeled usage fields
   and all 2,254 answers contain exactly the four modeled Choice
   fields, including confidence. This static artifact census is source review,
   not a new SDK or model run. For a future response that does not match the
   schema, the boundary can change acceptance and drops extra fields before our
   unchanged validator and ledger. Raw HTTP data remains available through the
   SDK, but the ledger receives its parsed model dump. This schema boundary was
   omitted from the initial decision and is now explicit following cross-family
   source review.
3. [RetryPolicy:52-123](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f078f1e208a0d885154dc758344ae4fce77ac168/src/typesafe_sdk/_core/retry.py#L52)
   supports both 429 and 529 and explicit backoff configuration.

The published wheel's PyPI SHA256 is
`0a961148187d52e18276ed7f2d02617cfac48e3b97673cb631a8749397d43d1e`;
the distribution metadata is available at
[PyPI 0.7.2](https://pypi.org/pypi/typesafe-sdk/0.7.2/json).
Acceptance installs the published wheel in a private uv cache with source builds
disabled. It does not install a new host-stack component.

Dependency-resolution limitation: the install hint pins the SDK only, while its
[dependency declarations:35-40](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f078f1e208a0d885154dc758344ae4fce77ac168/pyproject.toml#L35)
allow dependency ranges. The tested environment used `httpx2==2.13.1`,
`pydantic==2.13.5` and `tenacity==9.1.4`, as retained in
`evidence/artifacts/typesafe-sdk-transport-20261005/checks.json`. Pinning that
tested dependency set in the hint is deferred; another resolution may select
versions outside this observed set. This task does not qualify every supported
dependency resolution.

## Retry and response metadata contract

| Setting | Legacy urllib transport | SDK defaults | Selected SDK policy |
| --- | --- | --- | --- |
| Total attempts | 5 | 3 | 5 (`max_retries=4`) |
| Retried statuses | 429, 529 | 408, 429, all 5xx | 429, 529 |
| Delay before retries | 1, 2, 4, 8 seconds | Initial 0.5, cap 5, jitter 0.25 | 1, 2, 4, 8; no jitter |
| Retry-After | Ignored | Honored | Ignored |
| Connection/timeout retries | Disabled | Enabled | Disabled |
| Overall retry budget | None | 30 seconds | None |
| Per-attempt HTTP timeout | 60 seconds | SDK default | 60 seconds |

The existing retry field remains the zero-based successful attempt number,
obtained from the SDK's own
[X-TypeSafe-Retry-Count:68-74](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f078f1e208a0d885154dc758344ae4fce77ac168/src/typesafe_sdk/_core/transport.py#L68)
on the public originating request. Its absence on the first attempt means zero.

Two transport details change explicitly. The SDK sets `User-Agent` to
`typesafe-sdk/0.7.2`, replacing `agent-lab-gap-crosswalk/1 (python-urllib)`;
its [header construction:116-127](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f078f1e208a0d885154dc758344ae4fce77ac168/src/typesafe_sdk/_core/transport.py#L116)
overwrites a caller-supplied User-Agent. Accept the vendor's header contract.
The latency field now uses the successful response's public `elapsed` HTTP
exchange duration, excluding SDK decoding. The legacy timer also covered final
JSON decoding. Both exclude earlier attempts and backoff; existing ledger bytes
remain unchanged. The public dependency contract is
[pydantic/httpx2@v2.0.0, d426e2c4:_models.py:579-604](https://github.com/pydantic/httpx2/blob/d426e2c44d1247fcf3326ed1cb496e56353efa4a/src/httpx2/httpx2/_models.py#L579).

## Alternatives and overturn condition

Keeping the urllib loop duplicates the supported vendor implementation. Using
SDK defaults changes the five-attempt retry contract. A wrapper or fork to
override vendor headers or count retries adds unnecessary transport glue.
Use the public client and its metadata directly.

Keep the prior glue if a prerequisite fails at the selected pin. Revisit this
decision if a future supported SDK cannot preserve structured questions,
probabilities, usage, request metadata or the retry policy. A comparison through
the upstream MockTransport seam must establish any proposed replacement before
another transport change.

## Acceptance boundary and completeness critic

`tests/test_gap_crosswalk_sdk.py` uses the upstream
[MockTransport seam:33](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f078f1e208a0d885154dc758344ae4fce77ac168/tests/conftest.py#L33)
and the vendor's unchanged parser and retry implementation. These are synthetic
integration checks, not an unchanged upstream suite or a live judgment. They
comprise six MockTransport tests plus three offline import and version checks.
They cover structured questions, usage/probabilities/request metadata, both retry
statuses, exhaustion, a non-retried 500, absent request ID and missing usage.
Wrong probability keys still fail the unchanged validator. Streamed mock
responses exercise the native client's HTTP elapsed metadata. The first fixture
used preloaded responses without elapsed metadata and failed three tests; that
failed attempt and the fixture correction are retained in
`evidence/artifacts/typesafe-sdk-transport-20261005/checks.json`.
Offline import checks cover absent and mismatched SDK installations. Independent
review caught that an initial install hint omitted `judge`'s required `--set`
and `--out` flags. The final hint asks users to prefix their original command,
preserving those flags and their output path; the guard test checks that hint.

The source review also checked the omitted contracts: optional metadata,
retry-count provenance, per-attempt timing, fixed endpoint, SDK-owned headers
and the offline CI build. Native service behavior remains unmeasured because
this task authorizes no live judge run. `request_body()`, `validate()`, the
threshold, ledger construction and recorded judgments are preserved.
