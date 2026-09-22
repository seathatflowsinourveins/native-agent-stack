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

Prefer GitHub's private vulnerability reporting once it is enabled for this
repository (Security tab -> "Report a vulnerability"). Until then, open a
public issue without secret detail: describe the affected file/workflow, the
exact commit and the risk, but do not paste tokens, keys or other credential
material into the issue body. Do not open a pull request that demonstrates a
working exploit against a hosted secret.

## Supported versions

Security fixes are made against `main` and the latest published tag matching
`v*`. Older tags and dated catalog manifests are historical records and are
not backported.

## Verifying releases

Published artifacts from this repository carry [GitHub artifact
attestations](docs/catalog-provenance.md). Verify a downloaded release or
catalog artifact with:

```sh
gh attestation verify <artifact-path> --repo seathatflowsinourveins/native-agent-stack
```

A successful verification proves provenance (which workflow, revision and
repository produced the artifact); it does not prove the artifact's claims
are correct, current or complete. See [docs/github-automation.md](docs/github-automation.md)
for the automation maintaining this policy and the scanning that supports it.
