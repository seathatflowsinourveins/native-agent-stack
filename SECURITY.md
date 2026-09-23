# Security policy

## Scope

This repository is a catalog: dated evidence manifests, selection records and
supporting automation/scripts. It is not a deployed service and has no
runtime endpoint, so most upstream web-application vulnerability classes do
not apply. In scope: secrets or credentials committed to history, a supply
chain compromise in a pinned binary/action/dependency referenced here, or a
workflow change that could exfiltrate `secrets.*`/`github.token` or write
with elevated permissions beyond a documented job.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting, which is enabled for this
repository: [report a vulnerability](https://github.com/seathatflowsinourveins/native-agent-stack/security/advisories/new)
(Security tab -> "Report a vulnerability"). Describe the affected
file/workflow, the exact commit and the risk. Do not paste tokens, keys or
other credential material into a public issue, and do not open a pull request
that demonstrates a working exploit against a hosted secret.

## Supported versions

Security fixes are made against `main` and the latest published tag matching
`v*`. Older tags and dated catalog manifests are historical records and are
not backported.

## Verifying releases

Each `v*` tag push runs `publish-catalog.yml`: its `publish` job builds the
catalog archive (`native-agent-stack-<sha>.tar.gz`) and an SPDX SBOM
(`native-agent-stack-<sha>.spdx.json`), creates a [GitHub artifact
attestation](docs/catalog-provenance.md) for each and verifies both in-run.
Its `release` job then re-checks both files against the digests that job
attested and creates the tag's GitHub Release with both files attached at
creation. Releases here are immutable once published: their assets and tag
cannot be changed. The release notes list both digests and these commands:

```sh
gh attestation verify native-agent-stack-<sha>.tar.gz \
  --repo seathatflowsinourveins/native-agent-stack \
  --signer-workflow seathatflowsinourveins/native-agent-stack/.github/workflows/publish-catalog.yml \
  --source-ref refs/tags/<tag> --source-digest <sha>
gh attestation verify native-agent-stack-<sha>.spdx.json \
  --repo seathatflowsinourveins/native-agent-stack \
  --signer-workflow seathatflowsinourveins/native-agent-stack/.github/workflows/publish-catalog.yml \
  --source-digest <sha> --predicate-type https://spdx.dev/Document
gh release verify-asset <tag> native-agent-stack-<sha>.tar.gz --repo seathatflowsinourveins/native-agent-stack
```

A successful verification proves provenance (which workflow, revision and
repository produced the artifact); it does not prove the artifact's claims
are correct, current or complete. See [docs/github-automation.md](docs/github-automation.md)
for the automation maintaining this policy and the scanning that supports it.
