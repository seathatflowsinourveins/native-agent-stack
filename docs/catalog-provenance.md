# Catalog archive provenance

The manual [catalog publication workflow](../.github/workflows/publish-catalog.yml)
packages one validated `main` commit and uses GitHub's native artifact attestation
service to identify its origin. It has no schedule, model execution, release,
registry push or Pages deployment. A dispatch on another branch is skipped.

**Implementation status:** local verification is recorded below. Hosted issuance,
artifact download and consumer verification require integration into `main` and a
manual run. The [PR #26 qualification record](https://github.com/seathatflowsinourveins/native-agent-stack/pull/26)
links the resulting run, source SHA and consumer observations when available;
the local observations here do not establish those hosted outcomes.
An attestation proves origin and byte integrity; catalog correctness and practical
usefulness still need their own [acceptance evidence](acceptance-evidence-policy.md).

## Scope and maintained interfaces

The default token is read-only. Only the publication job has `id-token: write`
and `attestations: write`, alongside `contents: read`. Its repository and ref
guard admits only this repository's `refs/heads/main`; no revision input or
pull-request trigger can select unreviewed code. Checkout does not persist
credentials. The job has a ten-minute timeout and uses a standard GitHub runner.

The existing integrity, catalog, foundation, convergence and explorer validators
must pass before packaging. These remain structural validation and recorded
evidence checks; they do not rerun native clients, upstream qualification or
broker adapters. Routine PR validation owns the unit suite and workflow audit;
publication repeats only checks relevant to the exported commit and its content.

`git archive` packages the complete tracked commit, including catalogs, published
evidence, manifests, validators and licenses. Its output goes into runner
temporary storage. A recursive archive of the worktree could collect runtime or
untracked files; this workflow never uses that approach. It confirms the checkout
SHA equals the triggering event SHA and rejects a changed working tree.

| Interface | Reviewed revision | Selection |
| --- | --- | --- |
| [actions/checkout](https://github.com/actions/checkout/tree/3d3c42e5aac5ba805825da76410c181273ba90b1) | `v7.0.1`, `3d3c42e5aac5ba805825da76410c181273ba90b1` | Reuse the repository's exact checkout pin; event commit and no persisted credentials. |
| [actions/attest](https://github.com/actions/attest/tree/1e69f48acb82d1966a394da916b4c1698aa569d6) | `v4.2.2`, `1e69f48acb82d1966a394da916b4c1698aa569d6` | Maintained native provenance interface with an explicit archive subject. |
| [actions/upload-artifact](https://github.com/actions/upload-artifact/tree/043fb46d1a93c77aae656e7c1c64a875d1fc6a0a) | `v7.0.1`, `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` | Existing pin; supported single-file `archive: false` preserves the subject bytes and digest. |
| [GitHub CLI attestation verification](https://cli.github.com/manual/gh_attestation_verify) | Local verification used `gh 2.101.0`; hosted version is captured per run | Native signer workflow, source SHA/ref, runner policy and detached-bundle verification. |

[attest-build-provenance v4](https://github.com/actions/attest-build-provenance/tree/4d101475d8b20a2381f78447822ac1eab6504dd8)
is a compatibility wrapper and directs new implementations to `actions/attest`.
The selected action defaults to SLSA provenance. Registry and storage-record
creation are explicitly disabled; `artifact-metadata: write`, package writes and
repository content writes are unnecessary. Subject autodiscovery is not used.

`archive: false` accepts exactly one file and names the artifact after that file;
the upload action ignores its `name` input in this mode. The evidence logs and
detached bundle are uploaded separately with the ordinary ZIP behavior. Do not
compare that evidence ZIP's digest with the catalog archive's attested digest.

## Run and verify

After integration, the maintainer can dispatch the default branch:

```bash
gh workflow run publish-catalog.yml --ref main \
  --repo seathatflowsinourveins/native-agent-stack
```

The workflow preserves source/run identity, validation output, archive checksum,
attestation bundle, verification results and upload digest. It fetches the native
[trusted root](https://cli.github.com/manual/gh_attestation_trusted-root) once for
detached-bundle verification. It verifies the original, requires rejection of a
copy with appended bytes, then rechecks the original under the same offline
policy. Failure output survives in the evidence artifact, including the CLI's
nonzero negative-control result. Unexpected acceptance or failure of the final
original verification fails the job. No failure is ignored to turn the run green.

Download the catalog archive and evidence artifact from the same successful run
into a fresh directory. Inspect the run and artifact list first:

```bash
repo=seathatflowsinourveins/native-agent-stack
run_id=SUCCESSFUL_RUN_ID
gh api "repos/$repo/actions/runs/$run_id" \
  --jq '{head_sha,head_branch,conclusion,path,run_attempt}'
gh api "repos/$repo/actions/runs/$run_id/artifacts" \
  --jq '.artifacts[] | {id,name,expired,digest}'
```

Confirm `main`, the expected workflow path and a successful conclusion. Set the
following values from those records, selecting the nonexpired archive whose name
contains the source SHA. The [REST artifact download endpoint](https://docs.github.com/en/rest/actions/artifacts#download-an-artifact)
returns the stored payload through a redirect; retain those bytes directly. Use
`gh run download` only for the separate ZIP evidence artifact:

```bash
commit=FULL_SOURCE_COMMIT_FROM_THE_RUN
artifact_id=CATALOG_ARCHIVE_ARTIFACT_ID
attempt=RUN_ATTEMPT
archive="native-agent-stack-${commit}.tar.gz"
gh api "repos/$repo/actions/artifacts/$artifact_id/zip" > "$archive"
gh run download "$run_id" --repo "$repo" \
  --name "catalog-publication-evidence-${run_id}-${attempt}" --dir .
```

Despite the API route's `zip` suffix, an artifact uploaded with `archive: false`
contains the original file. Do not unzip that response. In the reviewed
[GitHub CLI v2.101.0 implementation](https://github.com/cli/cli/blob/v2.101.0/pkg/cmd/run/download/http.go),
`gh run download` always tries ZIP extraction, so it is unsuitable for this plain
archive. The first hosted qualification must check the downloaded digest and
attestation; source inspection alone does not establish this repository's round
trip. Verify the archive itself:

```bash
repo=seathatflowsinourveins/native-agent-stack
commit=FULL_SOURCE_COMMIT_FROM_THE_RUN
archive="native-agent-stack-${commit}.tar.gz"
sha256sum -c archive.sha256
gh attestation verify "$archive" --repo "$repo" \
  --signer-workflow "$repo/.github/workflows/publish-catalog.yml" \
  --source-ref refs/heads/main --source-digest "$commit" \
  --deny-self-hosted-runners --format json
```

For verification from the retained bundle, add `--bundle attestation.json`.
On an offline consumer, obtain trusted root material independently through
`gh attestation trusted-root` while connected and pass it using
`--custom-trusted-root /path/to/trusted-root.jsonl`. A trusted root supplied by an
untrusted distributor is not an independent trust anchor. The run's retained root
is useful for diagnostics; default online verification obtains its own trust.

Extracting and running the archive's shipped validators is a separate content
check. Record its commands and outcomes separately from the cryptographic check.
Do not label unchanged receipts as newly executed native/provider evidence.

## Local observations and remaining qualification

The following observations were collected on 2026-09-20:

- At source `aeaf4773d25ef36dbc7f67d4c3e1569250647277`, the tracked tree held
  978 files totaling 16,204,389 bytes. A read-only `git archive --format=tar.gz HEAD`
  command exited 0, emitted 3,894,040 bytes, and had empty stderr. Its SHA256 was
  `551813d9e5cd0e37d864f9b59e627a04a8009f1f1a07b3295af9881ed34f4334`.
  This trial had no prefix; the workflow's prefix and future commits change its
  archive digest. It established local packaging only.
- A reused upstream `actionlint_1.7.12_linux_amd64.tar.gz` and its real GitHub
  attestation bundle were verified with `gh 2.101.0`: the unchanged file exited 0;
  a sandbox copy with appended bytes exited 1 with
  `Error: verifying with issuer "sigstore.dev"`. This is an upstream artifact
  consumer check, not issuance or publication evidence for this repository.
- An obsolete GitHub documentation URL returned HTTP 404. Research recovered
  through the current official [attestation guide](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations).

The workflow-specific checks used the implementation in this change and the
unmodified base commit above for the clean packaging replay:

| Command or replay | Actual result |
| --- | --- |
| `actionlint .github/workflows/publish-catalog.yml` (`1.7.12`) | Final exit 0; empty stdout/stderr. |
| `zizmor --offline --no-config --no-ignores --no-progress --persona regular --strict-collection --format json .github/workflows/publish-catalog.yml` (`1.30.1`) | Exit 0; stdout `[]`; stderr reported this workflow completed. |
| `python3 scripts/validate.py` | Exit 0; 68 components, 977 hashed files, 4 profiles, 100 receipts; explicitly reported integrity/scope checks only. |
| `python3 scripts/validate_catalogs.py` | Exit 0; 147 unique catalog repositories; explicitly reported source claims and native executions were not rerun. |
| `python3 scripts/validate_foundation.py --root . --json` | Exit 0; `ok: true`, `errors: []`. |
| `python3 scripts/validate_convergence.py --all-recorded --root . --json` | Exit 0; all 13 recorded experiments valid, with empty error lists. |
| `python3 scripts/build_ecosystem.py --check` | Exit 0; 3,719,994 bytes, SHA256 `56c03e8b3d2caddb30d9a724d39408455faad59217f9b709b21652fb71a1e6f3`. |
| Exact prepare, validation and archive step bodies in a temporary clean clone at the base commit | All exited 0; archive had 978 regular files, all under `native-agent-stack/`, with no parent traversal or `.git` entries. |
| Same archive step after adding an untracked sandbox file | Exit 1, empty stdout/stderr; dirty source was rejected before packaging. |

The prefixed archive replay emitted 3,894,489 bytes and this exact checksum:

```text
e6d602951d3f17a986c2979dad01f70cf196de9947910f0b28cabf867a3ff695  native-agent-stack-aeaf4773d25ef36dbc7f67d4c3e1569250647277.tar.gz
```

The first actionlint run exited 1 with `context "runner" is not allowed here`
for a job-level environment expression. The corrected implementation prepares
the directory from `$RUNNER_TEMP` and exports it through the supported
`$GITHUB_ENV` file. Both analyzers passed after that correction; no findings were
suppressed.

A second real upstream-artifact consumer check used
`gh attestation trusted-root` (exit 0), then `gh attestation verify` with
`--repo rhysd/actionlint --deny-self-hosted-runners --bundle BUNDLE
--custom-trusted-root ROOT --format json`. The unchanged, modified, unchanged
sequence exited **0, 1, 0** under identical detached-bundle/root inputs. Each
successful command emitted 16,058 bytes of verification JSON and empty stderr;
the altered archive emitted no JSON and the issuer error quoted above. Its
SHA256 changed from
`8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8` to
`7781a8d7a6ba88990c142efc1b449b752620ee20ad218ef41f4728f57ace95fc`.
An initial scratch-directory collision raised `FileExistsError` before that
sequence; retrying with a fresh temporary directory completed it. This is local
consumer integration against an existing upstream attestation, not an unchanged
upstream test suite or new repository issuance.

Hosted signature issuance, upload digest equality, successful consumer download,
main-only event handling and the workflow's complete negative control are not
established by local lint or the upstream artifact example.

## Ownership, limits and rollback

The GitHub automation maintainer owns this workflow, its pinned action updates
and consumer instructions. Dependabot can propose action-pin updates; review must
retain the same subject, permission and failure behavior. Catalog-maintenance
automation may propose changes but does not dispatch publications or promote
versions into accepted runtime status.

[Native attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations)
are available for public repositories on current GitHub plans. Standard public
GitHub-hosted runner execution is free; artifact storage is a separate allowance
described by [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
One manual run uploads roughly a few megabytes plus bounded logs, with seven-day
retention. No larger runner, model subscription or paid entitlement is enabled.
The archive is an expiring Actions artifact, not a permanent release channel.

The run's artifact ID, URL, commit, actual compressed size and digest must be
recorded during hosted qualification. Artifact expiry does not retract public
attestation records, and attestations do not guarantee the truth, adequacy or
currency of the evidence inside. Failure during service or artifact upload can
also prevent evidence preservation; workflow logs remain the fallback record.

Rollback: disable `publish-catalog.yml` to stop future dispatches, or revert this
workflow and guide through a reviewed change. Existing validation and maintenance
continue independently. Previously published bytes and attestation records are
historical results and must not be silently relabeled or treated as new evidence.
