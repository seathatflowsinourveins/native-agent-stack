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

Before its existing address checks, the adapter now refuses any percent escape
or non-ASCII character in the hostname. It keeps the original vendor URL, hit,
rank and error evidence unchanged. Extraction does not run for a refused host.
This deliberately leaves internationalized-host support unqualified rather than
assuming that standard-library normalization matches the native transport.

Four offline capture regressions feed the exact measured spellings through the
existing capture seam: an ideographic dot, fullwidth digits, percent-encoded
digits and a percent-encoded dot. Each asserts no extraction call and unchanged
retained URL/result/rank. All four fail before the guard and pass afterward.
These fixtures are local integration evidence, separate from the native vendor
canonicalization probe retained by the post-merge reader.

The existing strict input, finished-partial, witness and interruption contracts
remain in place. DNS, redirects, arbitrary-URL isolation and broader IDNA support
remain unverified. A vendor-supported extraction boundary proven on the same
host forms could replace this narrow refusal policy; compare original request
and transport evidence before changing it. Repository rollback restores the
previous policy and requires no installation or active configuration change.
