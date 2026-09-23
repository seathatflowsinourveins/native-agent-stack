# Requirement list: public catalog repository, GitHub automation change

Grade each item as met, partial, unmet or not_applicable. Judge only from the arm's diff and its
checkout. Items that depend on repository state the arm could not see (a file added to the
default branch after the arm's base) are not_applicable.

R1. A new security workflow runs on pull_request (no path filter, so its PR job can be a required
check), on push to the default branch, on a weekly schedule and on manual dispatch. The top-level
token is read-only, write scopes are job-local, and every job has a timeout, checkout without
persisted credentials, and an audit-mode egress-hardening first step, as sibling workflows do.

R2. A dependency-vulnerability scanner (OSV-Scanner) is installed checksum-verified. It scans an
explicit list covering every tracked lockfile or manifest, using the correct parser for file
names the scanner cannot infer. A unit test fails when a tracked lockfile is missing from the
list. Any deliberately vulnerable test fixture is excluded only with a written reason.

R3. The scanner fails on any unignored vulnerability. Ignores carry an id, a reason and an expiry
of at most 90 days. No other suppression mechanism bypasses that policy.

R4. On non-PR events the scanner's SARIF reaches code scanning, including when vulnerabilities
are found. A scanner error (not a findings exit) fails the job.

R5. A workflow analyzer (zizmor) runs its online audits on non-PR events and uploads SARIF.
Findings do not fail the job; an analyzer crash does, and a crash never uploads an empty or
invalid SARIF. The analyzer never receives a token that can write code-scanning results. The
offline PR gate elsewhere stays.

R6. OpenSSF Scorecard SARIF is uploaded to code scanning with a job-scoped write permission, and
publish_results stays false.

R7. Dependency review fails on high-severity advisories and is not warn-only.

R8. The SBOM vulnerability scan (grype) gates at high severity, with a reviewed ignore file whose
entries carry a justification and a review date. Changes to that ignore file trigger the gate on
push and pull_request.

R9. Dependabot has an explicit cooldown for its version updates. No pip version-update ecosystems
are added for the reproducible, hash-locked lock files.

R10. A tag-only release job creates a GitHub Release with the attested archive and SBOM attached
so that immutable releases are satisfied (assets present at publication), verifies asset digests
against the attested digests, and holds contents: write only in that job.

R11. The target branch ruleset file adds the dependency-review and OSV required checks and a
code-scanning rule (CodeQL, security high_or_higher, alerts errors). It keeps squash as the only
merge method, and it does NOT add required_signatures (a signed-commits rule was measured to
block PRs whose branch commits are unsigned) and does NOT set strict required checks (auto-merge
without a merge queue would stall PRs). The tag ruleset files equal the live split tag rulesets.

R12. SECURITY.md states that private vulnerability reporting is enabled, links the reporting form,
and describes release verification that matches the release job.

R13. Workflow hardening tests cover the new workflow and jobs: pins, permissions and the failure
semantics above.

R14. The machine-readable automation catalog and generated artifacts are updated so the
repository's validators pass. Stale statements in the automation docs and handbook are corrected.

R15. A dated decision record gives, per change, the evidence (primary source plus measured
numbers), the alternatives, the decision and an overturn condition. It supersedes the earlier
"CodeQL not activated", "dependency review warn-only" and "grype threshold pending" decisions, and
records the SaaS verdict. Its claims are supported by the measurements it cites.
