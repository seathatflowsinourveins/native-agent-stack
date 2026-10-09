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
The exact receipt union narrows 4650 to 4648; no other receipt is added or removed.

The complete builder's independent reader now reaches inventory content,
metadata and cache signatures. Hashes and parsed metadata use one captured
approved payload. Exact canonical approval precedes content/digest access,
and shared checks reject protected lexical and canonical aliases. The later
CC read at 64809272 identified an availability regression: ordinary unknown
names had become fatal to all pages. Those names now produce UNAPPROVED
name-only records, without target stat/resolve/open/hash or invented presence.
They cannot add themselves to permissions. Protected inputs still refuse the
Architecture observation; the optional composer adapter retains its last
page or shows an UNREPORTED placeholder while other pages refresh. Cache
signatures include unknown names, so installing an unapproved entry changes
the inventory observation without accessing its content. Complete-builder
synthetic regressions retain zero forbidden opens and verify this availability
and privacy distinction.

There are 129 independent exact inventory content paths: pinned repo selectors,
the fixed sanitized automation projection and 41 reviewed installed skill
targets. User content is restricted to exact `SKILL.md` assets. A separate
94-path metadata-only role covers user agent/service registrations; it cannot
authorize file body access. Existing native descriptor-relative no-follow
directory traversal and stat observe those metadata targets without reading
client configuration or service Environment values. Newly installed assets
require a new independent policy review before content capture, never a
runtime-derived wildcard grant. File presence or hash equality still does not
establish wiring, execution or acceptance.

A checked-in names-only directory snapshot and independent bindings reproduce
the 41 skill, 94 metadata and one design grant, including 33 exact aliases.
Additional names remain unapproved rather than expanding permissions. A CI
test compares repository grants with the current committed `git ls-files`
selector; landing-head regeneration is required after the authorized rebase.
Adoption role attribution separately reuses the same native no-follow reader
for fixed co-op metadata paths and reviewed parking/capacity filenames;
refusals leave measured call counts unattributed and report safe source errors.
No raw co-op payload or user configuration body is read during derivation.

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
