# Retained vendor documentation for Claude federation diagnostics

Revision index: [snapshots.json](snapshots.json). Each document has a stable
`sha256:<digest>` revision, retrieval date, byte count and material line locators.
The three captures are byte-identical to the reviewed source packet staged on
2026-10-10 at 07:03:18 UTC. The packet supplies the retrieval date; separate
request timestamps were not recorded. Its staging time is not relabeled as
three exact fetch times.

- GitHub OIDC visible text: 37,248 bytes, revision `sha256:35d79cb17e94732a467c63e59c3a01d18029b47f4b5f9cbf15d92037164b03cd`; immutable subject syntax at lines 352–359, pull_request suffix at 332–336.
- Claude WIF GitHub guide Markdown: 14,693 bytes, revision `sha256:edc97bf1872a1292911b08600aadfc494295009cc6db1da232279dae46c0429b`; opaque denial and history diagnosis at 316.
- Claude WIF concepts Markdown: 25,749 bytes, revision `sha256:d929e36810bcfdcc7a9bf5de39df8b08fbfde60a6d4c138b097f0940feb13bb7`; all configured matchers required at 42.

The source packet also records the GitHub raw HTML hash
`5a88f1469d4a089770722ec216dca785396c432762b9be98c0843273c6d80325`.
This directory retains the reviewed visible-text revision; the upstream raw HTML
is not asserted as a separately retained file here. Canonical vendor URLs and
the exact material lines are recorded per snapshot.

These are source-review artifacts. They establish what the cited vendor pages
said at retrieval and do not establish a successful federation exchange, model
review, native identity-token claim, Console rule correction or deployment.
Only vendor reference text and public examples are retained. The PR adds no
account configuration or operational credential.

The public vendor examples include organization UUIDs. Publication validation
recognizes only these two exact Markdown paths at their approved whole-file
SHA-256 revisions as public reference text for that one UUID heuristic. Each
must still be hash-registered. Other private-content patterns remain enforced;
modified/rehashed bytes, another path or an unregistered file lose the exception.
The validator regressions also prove private paths and synthetic token patterns
still fail even when the UUID-only classification is permitted. No source bytes
are redacted or encoded to avoid publication checks.

File registration uses the documented `scripts.host_receipts.register_file`
routine; `scripts/evidence_manifest.py --check` verifies sorted registrations,
and FULL `scripts/validate.py` verifies all hashes, sizes and scope.
