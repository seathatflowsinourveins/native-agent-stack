# Native SDK dependency inventory — September 19, 2026

Upstream **Syft 1.52.0** inventoried the existing `equity-worker-sdk` directory.
The native command exited **0** in **1.252 seconds**, with no standard-error
output. It found **36 Python packages**; their names and versions match all
36 installed `dist-info/METADATA` distributions. No SDK packages were changed.

The [sanitized receipt](receipt.json) contains every package name, version,
PURL, observed license-expression coverage, command result and artifact hash.
Detailed SBOMs remain private because they include file and build metadata.

| Native result | Observed value |
| --- | ---: |
| Syft JSON packages | 36, all Python |
| Cataloger | `python-installed-package-cataloger` |
| CycloneDX version | 1.7 |
| CycloneDX components | 36 libraries + 87 files |
| Package name/version/PURL agreement between formats | 36/36 |
| Installed Python metadata name/version agreement | 36/36 |
| Packages with license metadata | 34/36 |
| Packages with an SPDX expression | 31/36 |
| Catalogued file records / relationships | 166 / 177 |
| Selected source regular files / bytes | 7,700 / 537,874,984 |
| Source content and symlink fingerprint before/after | Identical |
| New model calls / vulnerability scans | 0 / 0 |

The selected runtime includes `openai 3.16.2`, `openai-codex 0.154.0`,
`alpaca-py 0.44.0` and `duckdb 1.5.5`. These are observed installed versions,
not a claim that every dependency is the newest available release.
`duckdb` and `pyluach` had no catalogued license metadata; `pandas`,
`python-dateutil` and `sseclient-py` had metadata without a parsed SPDX
expression. Those are inventory review items, not legal conclusions.

## Verified native installation

The pinned Linux amd64 release was downloaded from the official GitHub
release. Its SHA-256 matched both the publisher's checksum list and GitHub's
release-asset digest:

```text
archive: caeedb81fb0491615f1ebd1761e4145d41ee86dd2cc7bf80669f9f5ad9d6133d
binary:  15a52d0122953081d16e6695f48055216a4de293bb005948663bb739a63880f9
version: 1.52.0
commit:  02ba369d13b4248395b20a504eca94b0cab564d8
build:   2026-09-17T14:32:25Z, go1.26.3, linux/amd64
```

Release publication was September 17, 2026, 14:38:17 UTC. The executable is
statically linked. No existing executable was replaced; a new versioned tool
directory and previously absent `syft` link were created in the adopted local
tools layout. Signature verification was **not** performed at installation.
Matching checksums does not independently establish publisher identity or
build provenance. On September 23, 2026, `cosign verify-blob` (v3.1.3) checked
the Syft and Grype checksum files against their keyless signatures and exited
0. The signer identity was each repository's
`.github/workflows/release.yaml@refs/heads/main`, with issuer
`https://token.actions.githubusercontent.com`. The workflow commit matched each
binary's `gitCommit`. A tampered blob and a wrong identity each failed with
exit 1. The installed binaries are byte-identical to the verified archives.
Gitleaks 8.30.1 publishes neither a signature nor a GitHub attestation, so it
remains checksum-only. The details are in the gap-wave-2 receipts for gaps 2
and 13.

Set these variables to explicit absolute paths. `NEW_DOWNLOAD_DIR` and
`NEW_INSTALL_DIR` must not exist; the target link must also be absent.
The following reproduces the native release-download and checksum steps:

```sh
umask 077
mkdir "$NEW_DOWNLOAD_DIR"
gh release download v1.52.0 --repo anchore/syft \
  --dir "$NEW_DOWNLOAD_DIR" \
  --pattern syft_1.52.0_linux_amd64.tar.gz \
  --pattern syft_1.52.0_checksums.txt
(
  cd "$NEW_DOWNLOAD_DIR"
  sha256sum --check --ignore-missing syft_1.52.0_checksums.txt
)
gh api repos/anchore/syft/releases/tags/v1.52.0 \
  --jq '.assets[] | select(.name == "syft_1.52.0_linux_amd64.tar.gz") | .digest'
```

The accepted installation checked archive member types and allowed only
top-level release files before extraction. The archive contains `syft`,
`README.md`, `LICENSE` and `CHANGELOG.md`. After the checks pass, these native
commands extract into a new directory and create a previously absent link:

```sh
tar -tzf "$NEW_DOWNLOAD_DIR/syft_1.52.0_linux_amd64.tar.gz"
mkdir "$NEW_INSTALL_DIR"
tar --no-same-owner -xzf "$NEW_DOWNLOAD_DIR/syft_1.52.0_linux_amd64.tar.gz" \
  -C "$NEW_INSTALL_DIR"
chmod 0755 "$NEW_INSTALL_DIR/syft"
ln -s "$NEW_INSTALL_DIR/syft" "$NEW_SYFT_LINK"
"$NEW_INSTALL_DIR/syft" version -o json
```

These shell extraction commands are the replay recipe; the recorded install
used Python's filtered archive extraction after checking every member. Do not
use an unpinned installer or overwrite another tool to replay this evidence.

## Exact native inventory workflow

`SYFT_BIN` names that verified binary, `SDK_ENV` names only the adopted SDK
prefix, and `NEW_OUTPUT_DIR` names a fresh private output directory. The
accepted run used the existing native **bubblewrap 0.9.0** to mount the SDK
read-only, clear inherited environment/configuration and isolate networking.
No other host filesystem was mounted. Syft also received its upstream
`--base-path` boundary. Three symlinks resolving outside the SDK were therefore
not followed; the external Python interpreter and host libraries are excluded.

```sh
umask 077
mkdir "$NEW_OUTPUT_DIR"
bwrap --unshare-all --die-with-parent --new-session --cap-drop ALL \
  --clearenv \
  --ro-bind "$SYFT_BIN" /syft \
  --ro-bind "$SDK_ENV" /sdk \
  --bind "$NEW_OUTPUT_DIR" /output \
  --proc /proc --dev /dev --tmpfs /tmp --chdir /tmp \
  --setenv HOME /tmp --setenv SYFT_CHECK_FOR_APP_UPDATE false \
  /syft scan dir:/sdk --base-path /sdk --source-name equity-worker-sdk \
  --parallelism 2 \
  -o syft-json=/output/runtime.syft.json \
  -o cyclonedx-json=/output/runtime.cdx.json
```

The scanner did not execute SDK packages or download a vulnerability database.
Its before/after source fingerprint covered regular-file bytes and symlink
targets. Raw output permissions were set to `0600` under a `0700` directory.
The native output formats agree on all 36 package name/version/PURL tuples.
A first summary reader incorrectly assumed every CycloneDX component had a
version; its `KeyError` was corrected by separating library and file components.
The successful native scan and its two original outputs were retained.

This closes the selected SDK's installed-package inventory gap. It does not
establish whole-host coverage, complete vendored-library discovery, dependency
authenticity, license approval, vulnerability status, token savings or a
recurring operational policy. The raw SBOM is an input to later scoped review,
not a security verdict.

## Upstream sources

- [Pinned release assets](https://github.com/anchore/syft/releases/tag/v1.52.0).
- [Pinned upstream README](https://github.com/anchore/syft/blob/v1.52.0/README.md): directory scans and multiple native output formats.
- [Supported scan targets](https://oss.anchore.com/docs/guides/sbom/scan-targets/).
- [Upstream CLI reference](https://oss.anchore.com/docs/reference/syft/cli/): explicit source and path-boundary options; installed `syft scan --help` confirmed the accepted flags.

## Vulnerability scan — pinned NautilusTrader 2.0.0rc5 runtime and Alpaca adapter, September 22, 2026

This scan targeted the NautilusTrader rc5 runtime, **not** the 36-package
`equity-worker-sdk` inventoried above. Packages such as `openai 3.16.2`,
`openai-codex 0.154.0` and `exchange-calendars 4.13.2` are in the SDK
inventory only. The SDK's own vulnerability scan was run separately on
September 23, 2026 (see the next section). Upstream **Syft 1.52.0**, already
installed for the inventory above, generated SBOMs for two targets. Newly
installed upstream **Grype 0.119.0** matched both against its vulnerability
database:

1. The installed Python `site-packages` of the pinned uv-managed runtime venv
   used for `adaptive-paper` NautilusTrader 2.0.0rc5 + Alpaca paper operation
   (21 Python packages, including `nautilus-trader 2.0.0rc5` and
   `alpaca-py 0.44.0`).
2. This repository's `blueprints/us-equities/adaptive-paper` directory, whose
   only version pins are its `requirements.txt` (`nautilus-trader==2.0.0rc5`,
   `alpaca-py==0.44.0`).

| Native result | Observed value |
| --- | ---: |
| Grype version | 0.119.0 |
| Vulnerability database schema / built | v6.1.9 / 2026-09-22T06:30:41Z |
| Runtime SBOM packages scanned | 21 |
| Adapter SBOM packages scanned | 2 |
| Runtime `grype` matches | 0 |
| Adapter `grype` matches | 0 |
| `syft`/`grype` command exit codes | all 0 |

**Zero matches against today's database is not a safety guarantee.** It means
no vulnerability currently published to this database's 2026-09-22 snapshot
maps to the exact package versions scanned; future disclosures, native
extension code inside these wheels, and anything outside Python package
metadata are out of scope. The
[full receipt](scan-nautilus-rc5-20260922/receipt.json) records both tool
versions, the Grype release archive's verified checksum (matching both the
publisher's checksum list and GitHub's release-asset digest), the complete
scanned-package list with license metadata, an explicit (empty, by
construction) per-finding disposition table, and the exact commands run with
their exit codes.

Grype's own installation mirrors the existing Syft install above: the pinned
release archive was downloaded from the official GitHub release, verified
against both the publisher's checksum list and GitHub's release-asset digest,
and extracted into a new versioned directory with a symlink in the same local
tools layout Syft already uses. No existing executable was replaced.

Raw Syft/Grype JSON outputs (about 3.7 MB combined) are **not** committed to
this repository: they embed this machine's personal filesystem paths (scan
source directory, vulnerability database cache path) in tool metadata fields,
which the publication scanner forbids in tracked files. They are retained
outside this repository in a local state directory, and the receipt records
each raw file's exact byte count and SHA-256 so the recorded package and
finding counts in the receipt can be checked against them.

This scan result establishes only what its evidence class states
(`native_proven`, for the scan itself): that a fresh, verified-checksum
Grype run against a fresh database build found no known match for these
exact package versions on this date. It says nothing about NautilusTrader,
Alpaca adapter, or broker-side runtime safety.

## Vulnerability scan of the September 19 equity-worker-sdk SBOM, September 23, 2026

Upstream **Grype 0.119.0** was run against the exact September 19 Syft SBOM of
`equity-worker-sdk`. The SBOM's SHA-256 `6912fc52…12b210fc` matches the value
recorded in [receipt.json](receipt.json). Grype used an isolated, freshly
downloaded database: schema v6.1.9, built 2026-09-23T06:31:39Z.

| Native result | Observed value |
| --- | ---: |
| Packages ingested by Grype (CycloneDX library components) | 36 |
| Grype matches | 0 |
| Positive control: the same SBOM with `requests` changed to 2.19.0 | 5 matches |
| Positive control: PURLs `requests@2.19.0` and `urllib3@1.24.1` | 17 matches |

The two positive controls show that this database and this SBOM input path can
report matches. As with the runtime scan above, zero matches is not a safety
guarantee. The receipt, commands and sanitized raw outputs are in
`evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/`
(gaps 0 and 10).
