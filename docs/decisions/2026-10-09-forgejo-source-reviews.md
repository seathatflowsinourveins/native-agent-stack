# Anonymous Codeberg source reviews through Forgejo REST v1

The source-review harness now recognizes Codeberg repository URLs alongside its existing GitHub and Hugging Face paths. It reads the repository's metadata, resolves the default branch to a commit, reads documentation and declared license evidence at that commit, and records releases and tags in the existing review shape. It performs no installation, model call or adoption.

## SOTA sources and client choice

- [forgejo/forgejo v16.0.5, templates/swagger/v1_json.tmpl](https://code.forgejo.org/forgejo/forgejo/raw/tag/v16.0.5/templates/swagger/v1_json.tmpl): official REST v1 route and response contract, retrieved on 2026-10-09. Source bytes:853,965; SHA-256 `5047480080ab408814b3a1b13db5fb17aac084831556be17b6e28321afb2c332`.
- [Forgejo API usage](https://forgejo.org/docs/latest/user/api-usage/), accessed 2026-10-09: one-based page/limit, Link pagination and instance limits.
- [forgejo/forgejo v16.0.5, services/repository/files/content.go](https://code.forgejo.org/forgejo/forgejo/raw/tag/v16.0.5/services/repository/files/content.go): commit-ref content lookup and base64 file responses.
- [CPython3.13.16, Lib/urllib/request.py](https://github.com/python/cpython/blob/v3.13.16/Lib/urllib/request.py): the installed standard library's request and redirect implementation. The extension uses that existing anonymous transport, with explicit origin validation and throttling.
- [harabat/pyforgejo2.0.7](https://codeberg.org/harabat/pyforgejo), [published release metadata](https://pypi.org/pypi/pyforgejo/2.0.7/json): inspected wheel SHA-256 `4456c0e3de0470d66111901101a62e623eb29713fd57599220404f1e7caa824d`. `pyforgejo/client.py` loads dotenv configuration and requires an API key; `core/client_wrapper.py` adds token authorization. It also requires httpx, Pydantic, pydantic-core and python-dotenv. This anonymous read-only harness instead extends its existing transport against the official REST contract.

Codeberg's separately observed deployed version was `16.0.0-dev-753-6bcc6da0+gitea-1.22.0`. The release-pinned spec and deployed server are distinct versions. Recorded real responses establish the fields used by this adapter; this record does not infer compatibility with every Forgejo version or repository object format.

## Field mapping and boundaries

| Review evidence | Forgejo source |
| --- | --- |
| Repository identity, description, stars, archived, default branch | GET /api/v1/repos/{owner}/{repo}; stars_count maps to stars |
| Reviewed commit and commit time | GET /branches/{branch}; commit.id and commit.timestamp |
| README excerpts and blob identity | GET /contents/README.md?ref={commit}; regular base64 file, pinned path and Git blob checked |
| Declared license | Commit-pinned Cargo.toml package.license, or workspace package license when inherited |
| Latest stable release and official asset metadata | GET /releases/latest; explicit404 means no release |
| Release and tag lists | GET /releases and /tags; page/limit plus same-origin Link continuation |

Forgejo's Repository schema has no license or pushed_at field, and its spec has no repository /license or /readme route. The review preserves pushed_at=null, separately records updated_at and head_committed_at, and records NOASSERTION when no supported license declaration exists. Arbitrary license prose is not assigned an inferred SPDX identifier. Reviewed commits use the existing SHA-1 review contract.

Only anonymous HTTPS GETs to codeberg.org on port443 are allowed. Initial JSON requests remain under /api/v1/. Redirects and final response URLs are checked for the same host, HTTPS, permitted port and absent userinfo. No credential is read or sent; proxy inheritance is disabled. Each request start, including a redirect, is spaced by at least one second. Requests have a60-second timeout and JSON bodies an8MiB bound; there are no automatic retries. HTTP status and Retry-After identify a failure without publishing its response body.

Only explicit404 responses may leave optional README, Cargo or latest-release evidence absent. Authentication/rate/error statuses fail that repository's review. Malformed identities are reported individually while valid survivors continue. Pagination follows validated Link next URLs, handles server-clamped pages, rejects cycles or malformed responses, and refuses its20-page evidence bound instead of silently truncating a list.

## Recorded verification

The vendor fixture contains11 real responses: metadata, branch, commit-pinned README/Cargo, latest release, complete release/tag listings, and first/next limit1 pages for both collections. The captured default-branch commit is `633fc1bf2e8d4941619fc1c49137b0f1ec9b56aa`; its Cargo declaration is GPL-3.0-only. The snapshot has26 releases and29 tags, with latest stable release v0.20.0. Response wire-body hashes and byte counts are recorded separately from the fixture's normalized JSON serialization.

The public fixture omits172 occurrences of the unused Attachment.uuid field, whose opaque public asset handles match the publication validator's session-identifier shape. This is an explicit field projection: original HTTP-body hashes and byte counts remain bound to the original capture, not the projected bodies. Every field the adapter consumes is retained. The complete captured responses are retained privately for custody; no guard or validator exception is added.

The first163,058-byte capture was indexed before fixture materialization. One bounded export recovery repeated the anonymous capture, verified the same commit and total response bytes, and retained that provenance distinction in the fixture. No landscape judgments were rerun. The completed live source review and measured official distribution digest remain source-review evidence with no install or adoption credit.

The completed [mergiraf source review](../../evidence/artifacts/forgejo-source-reviews-20261009/mergiraf-source-review.json) is published unchanged: 49,943 bytes, SHA-256 `34c8c8666526a35c53727f92cf09b6c052047d0329b03e60e8f30c23b53515c8`. It records default-branch commit `633fc1bf2e8d4941619fc1c49137b0f1ec9b56aa`, the commit-pinned GPL-3.0-only declaration and documented source/release/tag observations.

The [official distribution digest](../../evidence/artifacts/forgejo-source-reviews-20261009/mergiraf-distribution-digest.json) is also published unchanged: 876 bytes, SHA-256 `c0696f03ce1df01209edbc16994322f399aeba8c0b2f818257d1a7c4cced621b`. The vendor's Codeberg v0.20.0 `mergiraf_x86_64-unknown-linux-gnu.tar.gz` asset was streamed read-only and measured at 7,472,707 bytes with SHA-256 `4341127da8d1da29eced669fbacc1e5d6e530115098de0b82cc9dc551a1acf37`; HTTP 200 and byte count agree with the recorded official asset metadata. This local measurement is distinct from the source review and from the release-tag commit recorded in the digest. No archive extraction, installation, execution or adoption occurred.

`tests/test_source_reviews_forgejo.py` replays these recorded responses with live networking blocked. Synthetic status/redirect cases are explicitly labelled protocol fixtures and cite Forgejo16.0.5 and the relevant HTTP standards; they are not live vendor observations. The tests cover pagination, missing release, rate/error statuses, same-host and refused outside-host redirects, metadata/license/commit mapping, pinned blob identity and batch continuation after an unsafe URL. The new module passes29/29 with no skips. The existing landscape-sweep module passes286/289; its three unexecuted cases require CONTEXT_MODE_SECURITY_JS, a real Bash3.2 binary and ShellCheck, respectively.
