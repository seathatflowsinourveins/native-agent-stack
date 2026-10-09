# Architecture inventory input custody

The GPT R3 read at ddb7a2a9419dac5047bb73df85b30c95bc0c98b8 found two
blocking source-policy regressions. Verdict SHA-256
9c4ed3c41e4e678981b75a71a398df373d0c6798a3d6b5ddb5403f85a1f94e59
was read in full. The fixes narrow frozen-input eligibility and carry the
existing independent reader into the remaining complete-build inventory leg.

The original frozen-artifact tripwire reproduced its one failure in a genuine
worktree before the change. Two unused input permissions were removed.
`scripts/local_pages_policy_grants.py` now derives a proposal from full-SHA
Git tree and registration metadata and the pinned test's eligibility
declaration, excluding frozen and shared protected paths. It prints proposals
for review; it never writes runtime permissions from discovered input files,
opens the referenced artifact bodies or pins executable grants as descriptions.
The exact receipt union narrows4650to4648; no other receipt is added or removed.

The complete builder's independent reader now reaches inventory content,
metadata and cache signatures. Hashes and parsed metadata use one captured
approved payload. Exact canonical approval precedes content/digest access,
and shared checks reject protected lexical and canonical aliases. Unknown
runtime inputs fail the complete build/cache reuse before publishing rather
than adding themselves to permissions. Complete-builder synthetic regressions
reproduced the two reported forbidden opens, then verified zero such opens
and byte-exact preservation of prior published output and receipt.

There are129independentexact inventory content paths: pinned repo selectors,
the fixed sanitized automation projection and41reviewed installed skill
targets. User content is restricted to exact `SKILL.md` assets. A separate
94-path metadata-only role covers user agent/service registrations; it cannot
authorize file body access. Existing native descriptor-relative no-follow
directory traversal and stat observe those metadata targets without reading
client configuration or service Environment values. Newly installed assets
require a new independent policy review before content capture, never a
runtime-derived wildcard grant. File presence or hash equality still does not
establish wiring, execution or acceptance.

The supported source primitives are reused from the native reader at
ddb7a2a9419dac5047bb73df85b30c95bc0c98b8 and installed CPython3.13.16,
full source pin cbc944f4bc59639a444dd971c737788ba2283a91:
[os descriptor interfaces](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Doc/library/os.rst),
[pathlib](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Lib/pathlib/_local.py),
and [buffered I/O](https://github.com/python/cpython/blob/cbc944f4bc59639a444dd971c737788ba2283a91/Modules/_io/bufferedio.c).
Native installed Git supplies immutable `ls-tree`/`show` metadata, rather than
another repository walker or archive parser. The reader captures64KiB chunks
within its original bound; a small approved payload cannot trigger a caller's
large-bound buffer allocation. Scope-limit errors remain failures, with no
read-limit widening.

Alternatives rejected: expanding subtree/wildcard permissions from discovery
would preserve the reported bypass; adding descriptive pins for frozen input
grants would contradict the tripwire's eligibility rule; hashing raw user
service/agent configuration would read content outside the approved metadata
scope. Replacing the reader would duplicate maintained native no-follow and
descriptor semantics. The selected seam instead passes the existing reader
and adds reviewed exact roles. A supported upstream API with the same custody
and smaller maintained surface, or a reproduced counterexample under these
fixtures, would overturn this integration choice.

Measured checks are local integration with synthetic repository/state/user
fixtures, scope/tripwire validation and bounded native filesystem calls.
Final command/exit/head/UTC receipts, CC Claude/co-op GPT review, exact-head CI
and the one authorized landing-turn rebase remain separate gates. Previous
production byte/inventory/unmapped counts are not promoted to this changed
source policy. No provider, market-data pull, live-service promotion or native
Darwin acceptance is inferred.
