# Exact approved query capture through native research dispatch

The approved G5 Claude Q/S plan requires source retrieval from the literal query
strings returned by Claude Q. The ordinary research dispatcher invokes the
installed embedded DeerFlow producer, which performs model planning. That route
cannot establish exact query strings or a phase with zero additional model calls.
This change adds an explicitly selected mechanical capture mode to the same
dispatcher for the approved 45-field G5 scope.

## Sources and choice

- Maintained [deedy5/ddgs v9.16.0](https://github.com/deedy5/ddgs/tree/70a5635510fb8d5b15d5ba6ceced6a67e212149b),
  release tag `v9.16.0`, commit `70a5635510fb8d5b15d5ba6ceced6a67e212149b`:
  `ddgs/ddgs.py` (`text`, `_search_sync`, `extract`),
  `ddgs/engines/duckduckgo.py` (literal query request), and
  `ddgs/http_client.py` (native transport). The installed native research runtime
  already supplies this distribution. The adapter checks its distribution
  version and the retained source hashes before executing retrieval; it installs
  no dependency and implements no search engine or model.
- Landed native dispatcher `618dd6c05ff6750705b52426261748d11e003477`,
  `tools/research/dispatch`, provides HCOM identity, owned process sessions,
  timeout/cancellation and retained receipts. The extension reuses those controls.
- CC154647Z approved a separate 45-field, 90-request Claude Q/S Batch plan with a
  40 USD ceiling. Its Condition 3 requires neutral question inputs, literal native
  query retrieval and the landed dispatcher. The private approval and immutable
  proposal retain their original hashes and failures. This change neither
  executes that plan nor authorizes an additional model request.

Direct DDGS is the supported vendor route for this gap. The installed GPT
Researcher DuckDuckGo wrapper truncates returned snippets; the adapter instead
retains the full values returned by DDGS. The ordinary DeerFlow route remains
the supported path for a research question that needs model planning.

## Native command and retained result

The cost-plan owner creates the query envelope from actual Claude Q output,
without rewriting queries or filtering candidates. Each field contains its
`layer_id`, exact `repository` or `skills` modality, and two or three ordered
query strings. The supplied scope file contains exactly the 45 approved unique
IDs and modalities; its complete bytes must match the approved SHA256.

```sh
tools/research/dispatch --name <hcom-name> \
  --exact-queries-file <approved-literal-queries.json> \
  --approved-scope-file <approved-field-scope.json> \
  --approved-scope-sha256 <approved-scope-sha256> \
  --mechanical-python <absolute-installed-ddgs-python>
```

The default invocation validates and freezes inputs without network activity.
Add `--execute` to perform native DDGS search. Source extraction defaults to
zero; an explicit `--fetch-top-k 0..5` bounds native extraction attempts for
each query. Mechanical flags require the query-file mode and cannot silently
fall through to model-powered DeerFlow, including an explicit top-k of zero.

The worker receives the frozen query and scope snapshots, checks their binding,
then calls the installed `DDGS.text` with the exact query, fixed DuckDuckGo
backend, region `wt-wt`, page 1 and `max_results=5`. DDGS owns its ranking and
filtering. Every item actually returned by DDGS is retained in native order,
including complete snippets, rank, URL, UTC capture time and content hashes.
The adapter does not apply an additional five-item slice. Optional extraction
calls the vendor's `DDGS.extract` and records each returned source or failure.

The command prints a result-receipt path. It retains frozen input hashes,
native dependency/source checks, logical search/extraction counts, process
exit/cancellation, original output files and their hashes. Search/source errors
remain errors. Validation, mechanical capture and failed attempts have separate
statuses; none becomes a cited-answer, landscape Workflow, complete measured
usage record or adoption verdict. A finished capture with retained query/source
errors has status `captured_with_errors` and native exit 1. The parent accepts
that partial record only after checking the original parsed-input witness and
that every approved logical query finished. This exit is distinct from an
interrupted or failed worker. Consumers must inspect the status, witness and
per-field source/error records, rather than treating exit 1 as cancellation or
as complete usable source coverage.

DDGS 9.16.0 raises its native `No results found.` exception for an empty search;
the adapter records that exact vendor observation separately from a transport
timeout. An empty bounded query is not evidence that a whole field or candidate
class is absent. Partial records may support fields with actual usable sources;
empty, failed and missing-source occurrences remain explicit and cannot close
those fields. Duplicate keys in the query or scope JSON are refused rather than
silently choosing one value.

## Validation and limits

Targeted checks cover exact UTF-8 bytes and ordering, all 45 IDs/modalities,
duplicate/out-of-scope/query-count inverses, source hashes, all returned hit
retention, native request payloads without network, failure retention, isolated
worker environment and the existing default dispatch/cancellation path.
These are local integration and synthetic checks. Live G5 retrieval is an
independent post-landing action using real approved Q output.

Logical DDGS calls and timeouts are bounded. Total vendor HTTP fanout/retries,
bandwidth, source publication dates, DNS resolution and redirect behavior remain
unverified. Obvious literal nonpublic or credentialed extraction URLs are refused.
No total-network or arbitrary-URL isolation claim follows from those checks.

Removing the explicit mechanical arguments returns the caller to the ordinary
DeerFlow command. Repository rollback removes this opt-in adapter without a
host sign-in, active settings change or installation inverse. A future maintained
DeerFlow exact-query, zero-model API that preserves the same records would
overturn this integration choice; compare the literal request/return evidence
before replacing it.
