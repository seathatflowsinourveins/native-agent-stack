# Refuse ambiguous extraction host spellings

The exact-query adapter delegates source extraction to installed DDGS. Native
transport canonicalization can map Unicode or percent-escaped hostname spellings
to a loopback address after a lexical hostname check has accepted them. The
2026-10-08 post-merge review reproduced four such forms through unchanged native
DDGS/primp extraction; a syscall guard refused the attempted connection. That
evidence establishes the transport sink, not successful access.

The supported dependency is [deedy5/ddgs v9.16.0](https://github.com/deedy5/ddgs/tree/70a5635510fb8d5b15d5ba6ceced6a67e212149b),
commit `70a5635510fb8d5b15d5ba6ceced6a67e212149b`. The relevant pinned source is
`ddgs/ddgs.py:135-272` (search and extraction, including the extraction return),
`ddgs/engines/duckduckgo.py:15-42` (literal query request; line 42 is EOF), and
`ddgs/http_client.py` (native transport). The adapter changes no vendor source
or search engine.

Before its existing address checks, the adapter now refuses any percent escape,
backslash or non-ASCII character in the hostname. It keeps the original vendor URL, hit,
rank and error evidence unchanged. Extraction does not run for a refused host.
This deliberately leaves internationalized-host support unqualified rather than
assuming that standard-library normalization matches the native transport.

Four offline capture regressions feed the exact measured spellings through the
existing capture seam: an ideographic dot, fullwidth digits, percent-encoded
digits and a percent-encoded dot. Each asserts no extraction call and unchanged
retained URL/result/rank. All four fail before the guard and pass afterward.
These fixtures are local integration evidence, separate from the native vendor
canonicalization probe retained by the post-merge reader. An additional ASCII
backslash spelling is conservatively refused because parsers can interpret that
delimiter differently; its regression proves the adapter refuses extraction,
without claiming a newly measured native transport sink.

The existing strict input, finished-partial, witness and interruption contracts
remain in place. DNS, redirects, arbitrary-URL isolation and broader IDNA support
remain unverified. A vendor-supported extraction boundary proven on the same
host forms could replace this narrow refusal policy; compare original request
and transport evidence before changing it. Repository rollback restores the
previous policy and requires no installation or active configuration change.

## Explicit measured native backend

The pinned DDGS `text` interface also supports native `backend="auto"`. The
adapter's existing default remains DuckDuckGo; a mechanical caller can now
explicitly select `--backend auto` while keeping the same full approved query
and scope snapshots, literal query bytes, all returned hits and partial/error
records. The worker receives that parameter unchanged and returns a backend
witness checked against the requested choice before completion is credited.
Mechanical options cannot select the DeerFlow model route.

A retained 2026-10-08 native measurement called five previously failed literal
queries once in each of three vendor parameter arms: omitted default, explicit
AUTO and a supported Brave/Mojeek engine list. That is 15 logical searches,
zero source fetches and zero model calls. Omitted default returned two queries
with ten hits; explicit AUTO returned two queries with six hits; the engine
list returned none. All raw counts, errors and query hashes are retained.
DDGS's omitted default already means AUTO, so these differences establish no
provider, reliability or quality advantage. HTTP status and total internal
request counts remain unknown.

The option uses the vendor mechanism that returned actual results. It adds no
query planning, model rewrite, retry loop, subset runner, observer or search
engine. AUTO's internal provider selection remains native DDGS behavior. The
caller explicitly chooses the backend for an authorized capture; this record
does not install a new default or authorize another full pass. Field discovery,
source availability and Claude S acceptance remain independent evidence.
