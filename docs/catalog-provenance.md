# Catalog archive provenance

The [catalog publication workflow](../.github/workflows/publish-catalog.yml)
packages one validated event commit and uses GitHub's native artifact attestation
service to identify its origin. A manual dispatch on `main` publishes the source
archive, SPDX SBOM, generated explorer and verification evidence as Actions
artifacts. A `v*` tag push also runs the release job, which attaches the archive
and SBOM to an immutable GitHub Release. There is no schedule, model execution,
registry push or Pages deployment. Other branch refs are skipped; matching tag
refs are admitted by the job guards, including a manual dispatch on such a tag.
The coordinator's tag-first, verify-then-re-pin procedure is in
[Moving a host to a new release](../adoption/update.md#moving-a-host-to-a-new-release).

**Qualified on 2026-09-20:** [publication run 35541322881](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/35541322881)
succeeded at `d0fe136c218fedff93c93ac674e302ae19b2d924`. Independent consumer
download, online and detached verification, altered-byte rejection, and archive
content validation passed. [PR #26](https://github.com/seathatflowsinourveins/native-agent-stack/pull/26)
retains the qualification record; [the automation manifest](../catalogs/foundation/automation.json)
records exact artifact identity and remaining limits. Historical local observations
below remain separate from this hosted result.
That qualification covers the named commit's archive publication only. It does
not establish the later SBOM, explorer or immutable-release behavior. The current
description was reconciled on 2026-10-08 against this repository at
[`eb5fee4db9a494729deb29bdf38dbabac23ee643`](https://github.com/seathatflowsinourveins/native-agent-stack/tree/eb5fee4db9a494729deb29bdf38dbabac23ee643),
the workflow and adoption procedure above, GitHub's
[attestation guide](https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds)
and [immutable-release contract](https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases).
This reconciliation is source review, not a new hosted publication qualification.
An attestation proves origin and byte integrity; catalog correctness and practical
usefulness still need their own [acceptance evidence](acceptance-evidence-policy.md).

## Scope and maintained interfaces

Top-level `permissions: {}` grants no token scopes by default. The `publish` job
has `contents: read`, `id-token: write` and `attestations: write`. Its repository
and ref guard admits only this repository's `refs/heads/main` or `refs/tags/v*`.
The dependent `release` job has `contents: write` to create the GitHub Release
and attach its two files; its guard requires the same repository and a matching
tag ref. Release-tag custody is therefore part of the trust boundary. There is
no revision input or pull-request trigger. Checkout does not persist credentials.
Each job has a ten-minute timeout and uses `ubuntu-24.04` with the pinned runner
hardening action in audit mode. Runs on the same ref are serialized and a started
run is not cancelled by a newer one.

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
The generated explorer is a separate, scanned and attested HTML artifact; it is
not part of the tracked source archive. The SPDX SBOM is generated from the
checkout using checksum-verified Syft. The tag-ref release job downloads only
the archive and SBOM by their publication artifact IDs, rejects download digest
mismatches, and rechecks both files against the SHA256 digests attested and
uploaded by `publish` before attaching them to the release.

| Interface | Reviewed revision | Selection |
| --- | --- | --- |
| [actions/checkout](https://github.com/actions/checkout/tree/3d3c42e5aac5ba805825da76410c181273ba90b1) | `v7.0.1`, `3d3c42e5aac5ba805825da76410c181273ba90b1` | Reuse the repository's exact checkout pin; event commit and no persisted credentials. |
| [actions/attest](https://github.com/actions/attest/tree/1e69f48acb82d1966a394da916b4c1698aa569d6) | `v4.2.2`, `1e69f48acb82d1966a394da916b4c1698aa569d6` | Maintained native provenance interface with an explicit archive subject. |
| [actions/upload-artifact](https://github.com/actions/upload-artifact/tree/043fb46d1a93c77aae656e7c1c64a875d1fc6a0a) | `v7.0.1`, `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` | Existing pin; supported single-file `archive: false` preserves the subject bytes and digest. |
| [actions/download-artifact](https://github.com/actions/download-artifact/tree/3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c) | `v8.0.1`, `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` | Release job selects the publication artifact IDs with `digest-mismatch: error`. |
| [anchore/syft](https://github.com/anchore/syft/releases/tag/v1.54.0) | `v1.54.0`; Linux archive SHA256 `54a87372498168b2d033e876fd41fa4e8035b872699e525a57046e1f2f09c860` | Generate the SPDX SBOM using the workflow's exact upstream binary and checksum. |
| [GitHub CLI attestation verification](https://cli.github.com/manual/gh_attestation_verify) | Historical verification used `gh 2.101.0`; current command contracts checked with installed `gh 2.102.0`; hosted version is captured per run | Native signer workflow, source SHA/ref, predicate and detached-bundle verification; `gh release verify-asset` verifies the separate release attestation. |

[attest-build-provenance v4](https://github.com/actions/attest-build-provenance/tree/4d101475d8b20a2381f78447822ac1eab6504dd8)
is a compatibility wrapper and directs new implementations to `actions/attest`.
The selected action uses its default SLSA provenance predicate for the archive
and explorer. The SBOM file is its own attestation subject, with the SPDX document
as the `https://spdx.dev/Document` predicate. Registry and storage-record creation
are explicitly disabled; `artifact-metadata: write` and package writes are
unnecessary. Repository content writes belong only to the release job. Subject
autodiscovery is not used.

`archive: false` accepts exactly one file and names the artifact after that file;
the upload action ignores its `name` input in this mode. The evidence logs and
detached bundles are uploaded separately with the ordinary ZIP behavior. Do not
compare that evidence ZIP's digest with an attested file's digest. The release
does not attach the explorer or this evidence ZIP; it requires exactly the
archive and SBOM assets.

## Run and verify

A maintainer can dispatch the default branch for Actions artifact publication:

```bash
gh workflow run publish-catalog.yml --ref main \
  --repo seathatflowsinourveins/native-agent-stack
```

This `main` dispatch creates no release. A release uses the coordinator's
[tag-first procedure](../adoption/update.md#moving-a-host-to-a-new-release):
review the commit and tag, push the `v*` tag, wait for the publication and release
jobs, verify the published files, then open the adoption re-pin PR. A tag-ref
dispatch also satisfies the release guard, so do not use it as an upload-only
replay or try to recreate a release that already exists.

### Download and verify an immutable release

Use a fresh directory and the reviewed tag and its full source commit. Inspect
the release before downloading: require the expected tag, `isDraft: false`,
`isImmutable: true` and exactly the archive and SBOM assets. Compare each file's
SHA256 with its `assets[].digest` value, then verify both artifact attestations
and their membership in the release:

```bash
repo=seathatflowsinourveins/native-agent-stack
tag=REVIEWED_RELEASE_TAG
commit=FULL_SOURCE_COMMIT_FROM_THE_REVIEWED_TAG
archive="native-agent-stack-${commit}.tar.gz"
sbom="native-agent-stack-${commit}.spdx.json"
gh release view "$tag" --repo "$repo" \
  --json tagName,isDraft,isImmutable,assets,url
gh release download "$tag" --repo "$repo" \
  --pattern "$archive" --pattern "$sbom" --dir .
sha256sum "$archive" "$sbom"
gh attestation verify "$archive" --repo "$repo" \
  --signer-workflow "$repo/.github/workflows/publish-catalog.yml" \
  --source-ref "refs/tags/$tag" --source-digest "$commit" \
  --deny-self-hosted-runners --format json
gh attestation verify "$sbom" --repo "$repo" \
  --signer-workflow "$repo/.github/workflows/publish-catalog.yml" \
  --source-digest "$commit" --predicate-type https://spdx.dev/Document \
  --deny-self-hosted-runners --format json
gh release verify-asset "$tag" "$archive" --repo "$repo"
gh release verify-asset "$tag" "$sbom" --repo "$repo"
```

The archive uses the default SLSA predicate. The SBOM verification selects the
SPDX predicate explicitly, matching the workflow's SBOM command; do not apply
the archive's default predicate to it. GitHub generates a separate release
attestation when an immutable release is published. `gh release verify-asset`
checks that a downloaded file matches that release's attested asset digest; it
complements the workflow artifact attestations. Neither check establishes the
correctness or currency of the catalog or the completeness of the SBOM.

The workflow uses `gh release create --verify-tag` with both files. The installed
[GitHub CLI implementation at v2.102.0](https://github.com/cli/cli/blob/v2.102.0/pkg/cmd/release/create/create.go)
creates a draft, uploads assets and publishes it, following GitHub's
[recommended immutable-release sequence](https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases#best-practices-for-publishing-immutable-releases).
The final workflow check fails unless the release is published, immutable and
has exactly the two expected assets with their attested digests. This describes
the source contract; require a successful run and consumer verification for
each selected release.

### Actions artifacts and detached verification

The workflow preserves source/run identity, validation output, archive checksum,
attestation bundles, verification results and upload digests. It fetches the native
[trusted root](https://cli.github.com/manual/gh_attestation_trusted-root) once for
detached-bundle verification. It verifies the original, requires rejection of a
copy with appended bytes, then rechecks the original under the same offline
policy. Failure output survives in the evidence artifact, including the CLI's
nonzero negative-control result. Unexpected acceptance or failure of the final
original verification fails the job. No failure is ignored to turn the run green.

For a `main` dispatch, download the catalog archive and evidence artifact from
the same successful run into a fresh directory. Inspect the run and artifact
list first:

```bash
repo=seathatflowsinourveins/native-agent-stack
run_id=SUCCESSFUL_RUN_ID
gh api "repos/$repo/actions/runs/$run_id" \
  --jq '{head_sha,head_branch,conclusion,path,run_attempt}'
gh api "repos/$repo/actions/runs/$run_id/artifacts" \
  --jq '.artifacts[] | {id,name,expired,digest}'
```

Confirm `main`, the expected workflow path and a successful conclusion; the
retained `source.log` must agree on repository, commit and `refs/heads/main`.
For tag-run evidence, use the reviewed `refs/tags/<tag>` source ref instead.
Set the
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
archive. Check the downloaded digest and attestation on every selected publication;
the first hosted round trip is recorded above. Verify the archive itself:

```bash
repo=seathatflowsinourveins/native-agent-stack
commit=FULL_SOURCE_COMMIT_FROM_THE_RUN
archive="native-agent-stack-${commit}.tar.gz"
source_ref=refs/heads/main
awk -v name="$archive" '$2 == name' archive.sha256 | sha256sum --check --strict
gh attestation verify "$archive" --repo "$repo" \
  --signer-workflow "$repo/.github/workflows/publish-catalog.yml" \
  --source-ref "$source_ref" --source-digest "$commit" \
  --deny-self-hosted-runners --format json
```

`archive.sha256` also lists the separate SBOM and explorer; the command above
selects the archive's checksum instead of requiring files not downloaded here.
When verifying a tag-run archive, set `source_ref="refs/tags/$tag"` from the
reviewed tag and run identity before executing the verification command.

For verification from the retained bundle, add `--bundle attestation.json`.
The SBOM has its own `attestation-sbom.json` bundle and still requires
`--predicate-type https://spdx.dev/Document` when verified separately.
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

The 2026-09-20 workflow-specific checks used that revision's implementation and
the unmodified base commit above for the clean packaging replay. They are
historical results, not reruns of the current workflow:

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

The later hosted qualification established issuance, upload digest equality,
consumer download and the complete negative control for the named commit only.
[Non-main dispatch 35541389048](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/35541389048)
was skipped with zero job steps. Local lint and the upstream artifact example
remain distinct evidence; neither establishes those hosted outcomes on its own.

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
Actions artifacts have seven-day retention, including publication evidence and
the separate explorer. Sizes depend on the selected commit and are recorded per
run; the 2026-09-20 archive sizes above are historical. Tag-ref runs additionally
publish the archive and SBOM as GitHub Release assets, which are not subject to
that Actions-artifact retention. No larger runner, model subscription or paid
entitlement is enabled.

The run's artifact ID, URL, commit, actual compressed size and digest must be
recorded during hosted qualification. For a release, also retain the tag, source
commit, release URL, immutability result and both release-asset digests. GitHub's
immutable-release contract locks the associated tag and assets while the release
exists; title and notes can still change. Artifact expiry does not retract public
attestation records, and attestations do not guarantee the truth, adequacy or
currency of the evidence inside. Failure during service or artifact upload can
also prevent evidence preservation; workflow logs remain the fallback record.

Rollback: disable `publish-catalog.yml` to stop future publications, or revert a
workflow or guide change through review. Existing validation and maintenance
continue independently. Published immutable assets and their tag cannot be
rewritten in place; a corrected catalog needs a new reviewed tag, publication
and adoption re-pin. Previously published bytes and attestation records remain
historical results and must not be silently relabeled or treated as new evidence.
