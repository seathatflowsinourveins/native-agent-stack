---
status: proposed
date: 2026-10-05
decision-makers: github-ci-finalize campaign lane (A7 authorization; acceptance pending)
consulted: Independent source and ownership reviews; GitHub and GitHub CLI references below
review_by: 2026-10-12
evidence_class: source_review
overturn_when: One observed extra native verification call on an unchanged tuple, default report or --strict; one missed tag-only or commit-only re-pin; one nonzero, unavailable or malformed native result accepted; or one supported gh JSON result rejected. Record the failing case and revise before adoption.
---

# Native release verification on tuple re-pin

## Context and decision drivers

A host selects a release by `(source.release_tag, source.release_commit)`.
The existing `scripts/release_due.py` pin and re-pin seams (lines 136 and 260
at `c148e049efee75f8ea8a9a009e7b96b1e97f5c28`) compare only the commit for
strictness, so a tag-only change escapes the re-pin gate. This foundation
change serves reproducible north-star host adoption, not broker or paper
acceptance. Mandatory metadata above is a Campaignr2 extension to MADR.

## Decision

Compare the full tuple. On the `--strict-if-repinned BASE_REF` re-pin path,
invoke exactly one supported native command:

```sh
gh release verify <tag> --repo seathatflowsinourveins/native-agent-stack --format json
```

Keep the existing conservative strict fallback for an unavailable base by
treating it as a re-pin. Capture native output with a 60-second bound; accept
only native exit zero with nonempty `attestation` and `verificationResult`
objects, as returned by the installed native verifier; allow extra fields.
Do not reproduce signature verification or the vendor's complete schema.
Fail the re-pin gate on
nonzero, missing/unavailable or malformed verification with sanitized errors,
never raw native stderr or authentication state. Cryptographic verification
stays in GH; this glue does not implement crypto, a runner or a downloader.
Existing content-report fields retain their meaning; `release_verification`
is separate. Default reporting, unchanged tuples and local before-cut
`--strict` make zero verification/network calls. Do not add daily verification.

Consumer instructions add `gh release verify <tag> --repo REPO` before the
existing `verify-asset`, retaining provenance attestation and asset checks.
Keeping commit-only detection misses tag changes; verifying every report adds
unneeded network calls; implementing a second verifier duplicates the vendor.

## Sources and evidence boundary

- [GitHub CLI native verifier, cli/cli@v2.102.0:pkg/cmd/release/verify/verify.go:172](https://github.com/cli/cli/blob/v2.102.0/pkg/cmd/release/verify/verify.go#L172-L187).
  Installed GH 2.102.0 `release verify --help` confirmed the supported flags.
  The official source was retrieved with an explicit native GET and matched
  Git blob `c1a9ae4a20a019133f1bac6ef4d5039eda00e5cc` (6,725 bytes).
- [GitHub: verify release integrity](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/verify-release-integrity).
- [GitHub CLI: gh release verify](https://cli.github.com/manual/gh_release_verify).
- Local glue source: `scripts/release_due.py::pin`, `repinned` and `main` at
  the base above; local evidence rules: `docs/acceptance-evidence-policy.md`.

**Explicitly partial R1.** Publisher work remains held by #642; bootstrap
work remains held by #706/#642. No workflow, bootstrap, installation or adoption
manifest change is included. The evidence registry updates only this draft's
file hashes. Old tagged workflows use their historical
event ref, so changing these default-branch seams does not update them.

The existing workflow owner must also wire native GH authentication before
adopting this gate for an actual re-pin. At the base pin above,
`.github/workflows/validate.yml:109-113` sets only `BASE_REF` for this step;
the `GH_TOKEN` at line 77 is confined to another step. Installed
`gh help environment` and [GitHub's CLI-in-workflows documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-github-cli)
confirm the supported token environment. This draft does not edit the owned
workflow, inspect credential values or stores, or add a credential workaround.
Captured open owners are #706, #596 and #595; the command center coordinates
their existing workflow ownership rather than this lane competing with them.
A hosted real re-pin with owner-provided authentication is a remaining
integration acceptance condition; unchanged-tuple PRs stay offline.

The bounded native SDK unit finished with ten model requests. Its worker did
not execute tests. Root ran 30 release-pin tests and 21 focused adoption-doc
tests successfully. The Git fixtures exercise the report and tuple paths;
the GH subprocess boundary is synthetic, including failure controls. These
checks establish local integration, not unchanged upstream acceptance.

One unchanged native `gh release verify v2026.10.05.1 --repo
seathatflowsinourveins/native-agent-stack --format json` returned exit zero and
an attestation plus verification result for pinned commit
`77d7516d81a94b1cb0e77a7b6c910c28c8104dc9`. The retained returned output proves
only that named release and native verifier capability; it is not a hosted
execution of this new gate or acceptance of the held publisher/bootstrap
changes. The compact [receipt](../../evidence/artifacts/github-ci-r1-20261005.json)
keeps these classes and original-output digests separate. An independent
completeness critic caught the worker's broader nonempty-object acceptance:
valid JSON such as `{"status":"failed"}` was incorrectly accepted as a native
verification result. The two native object fields above and additional fixture
controls correct that claim, verified against retained native output and the
vendor export seam at lines 178–187. No hosted acceptance
exists yet. Registration is committed last; the review date is not acceptance.
