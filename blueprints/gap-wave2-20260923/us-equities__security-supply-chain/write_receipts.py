#!/usr/bin/env python3
"""Fill the preregistered gap-wave-2 receipts with commands, results and outcomes.

The preregistration block of each receipt is never modified. Every raw output a
receipt cites must exist under raw/ and is listed with its SHA-256. results.json
is generated from the receipts afterwards (see --results), never by hand.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
EV = REPO / "evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain"
BP = "blueprints/gap-wave2-20260923/us-equities__security-supply-chain"
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
FIRST_PASS = ("First pass (same unit, earlier session) between 2026-09-23T08:13:24Z and 08:27:10Z, after the "
              "08:13:16Z preregistration; this pass resumed at 16:26Z.")

GRYPE_SDK_CMDS = [
    f"bash {BP}/grype_sdk.sh  # GRYPE_DB_CACHE_DIR=isolated cache, GRYPE_DB_AUTO_UPDATE=false",
    "grype sbom:$HOME/codex-ecosystem/state/supply-chain-20260919/inventory/runtime.syft.json -o json",
    "grype sbom:<same SBOM> -o cyclonedx-json",
    "grype sbom:<same SBOM with requests changed to 2.19.0> -o json   # positive control 1",
    "grype purl:<file: pkg:pypi/requests@2.19.0, pkg:pypi/urllib3@1.24.1> -o json   # positive control 2",
]
GRYPE_SDK_RESULTS = [
    "SBOM sha256 6912fc526853724556519872207534d54bda90f9c22b48c9625b689c12b210fc (equals receipt.json raw_artifacts runtime.syft.json)",
    "sdk-json exit=0; sdk-cdx exit=0; mutated exit=0; purls exit=0",
    "sbom artifacts: 36 Counter({'python': 36}); sbom has openai ['3.16.2'], openai-codex ['0.154.0'], exchange-calendars ['4.13.2']",
    "grype cdx components by type: Counter({'file': 87, 'library': 36})",
    "sdk matches: 0 db built: 2026-09-23T06:31:39Z schema: v6.1.9",
    "mutated matches: 5 (GHSA-9hjg-9r4m-mvj7, GHSA-9wx4-h78v-vm56, GHSA-gc5v-m9x4-r6x2, GHSA-j8r2-6x86-q33q, GHSA-x84v-xcm2-53pg)",
    "positive matches: 17 on the same DB",
]
GRYPE_SDK_RAW = ["grype-sdk/exits.log", "grype-sdk/db-status.json.txt", "grype-sdk/sdk.grype.json",
                 "grype-sdk/sdk.grype.cdx.summary.json", "grype-sdk/mutated.grype.json",
                 "grype-sdk/positive.grype.json", "grype-sdk/positive.purls", "grype-sdk/sdk.stderr"]

SIG_CMDS = [
    f"bash {BP}/verify_signatures.sh",
    "cosign verify-blob --certificate syft_1.52.0_checksums.txt.pem --signature syft_1.52.0_checksums.txt.sig "
    "--certificate-identity https://github.com/anchore/syft/.github/workflows/release.yaml@refs/heads/main "
    "--certificate-oidc-issuer https://token.actions.githubusercontent.com "
    "--certificate-github-workflow-sha <syft gitCommit 02ba369d13b4…, full value in raw/signatures/signatures.log> syft_1.52.0_checksums.txt",
    "cosign verify-blob ... --certificate-identity-regexp '^https://github\\.com/anchore/syft/\\.github/workflows/.+' ...",
    "(same two for grype 0.119.0, workflow sha b6f519453774…, full value in raw/signatures/signatures.log)",
    "negative controls: verify-blob on a checksum file with one appended byte; verify-blob with identity anchore/other",
    "sha256sum --ignore-missing -c <tool>_checksums.txt; sha256sum of each installed binary vs the binary extracted from the verified archive",
    "curl https://api.github.com/repos/gitleaks/gitleaks/releases/tags/v8.30.1  # asset list",
    "curl https://api.github.com/repos/gitleaks/gitleaks/attestations/sha256:551f6fc8...  # attestation lookup",
    "curl https://api.github.com/repos/cli/cli/attestations/sha256:9bca2d1c...  # positive control for the lookup method (gh 2.101.0 archive)",
]
SIG_RESULTS = [
    "syft verify-blob exact identity exit=0; identity regexp exit=0; NEGATIVE tampered blob exit=1; NEGATIVE wrong identity exit=1; archive checksum in signed list exit=0",
    "grype verify-blob exact identity exit=0; identity regexp exit=0; NEGATIVE tampered blob exit=1; NEGATIVE wrong identity exit=1; archive checksum in signed list exit=0",
    "installed vs archive binary sha256: syft 15a52d01... == 15a52d01...; grype e02ba256... == e02ba256...; gitleaks 88f91962... == 88f91962...",
    "gitleaks archive checksum in unsigned list exit=0",
    "gitleaks v8.30.1 assets: checksums.txt plus platform archives only; no .sig, .pem, .sigstore.json or .intoto asset",
    "gitleaks attestation lookup: {\"message\": \"Not Found\", \"status\": \"404\"} http_status=404",
    "positive control (cli/cli, gh_2.101.0_linux_amd64.tar.gz digest): http_status=200, attestations 2",
    "cosign v3.1.3 binary sha256 4629c757...7f71 equals the GitHub release asset digest and cosign_checksums.txt entry (cosign itself is checksum-verified only)",
]
SIG_RAW = ["signatures/signatures.log", "signatures/gh-attestation-positive-control.json",
           "signatures/gh-attestation-positive-control.cmd"]

GL_CMDS = [
    f"bash {BP}/gitleaks_scans.sh control   # 6 synthetic secret-shaped files generated at runtime in a temp repo",
    "gitleaks-guarded git --no-banner --redact=100 --report-format json <temp control repo>             # default rules",
    "gitleaks-guarded git ... --config .gitleaks.toml <temp control repo>                                 # repo config",
    "gitleaks-guarded git ... --config .gitleaks.toml --log-opts=HEAD .                                   # first pass, uncapped",
    f"bash {BP}/gitleaks_scans.sh head2mb",
    "gitleaks-guarded git ... --config .gitleaks.toml --max-target-megabytes 2 --log-opts=HEAD .",
    "git rev-list --objects HEAD | git cat-file --batch-check  # list blobs > 2 MB (the cap's exclusions)",
    f"bash {BP}/gitleaks_scans.sh oversized   # gitleaks-guarded dir --config .gitleaks.toml docs/ecosystem/index.html (HEAD version)",
    "gitleaks-guarded dir --redact=0 ... docs/ecosystem/index.html -> private cache file (umask 077), classified by shape and by other tracked files containing the value, then deleted",
    f"bash {BP}/gitleaks_scans.sh allrefs   # --max-target-megabytes 2 --log-opts=--all",
    f"FIX ROUND: bash {BP}/gitleaks_fix_round.sh controls   # oversized-blob and merge-resolution detection controls (runtime-generated synthetic github-pat tokens)",
    f"FIX ROUND: bash {BP}/gitleaks_fix_round.sh oversized   # git cat-file every blob > 2 MB reachable from HEAD d67f77a into a 0700 temp dir; gitleaks-guarded dir --redact=0 --config .gitleaks.toml <batch dir> (5 batches of <= 40 blobs)",
    f"FIX ROUND: bash {BP}/gitleaks_fix_round.sh merges   # gitleaks-guarded git --config .gitleaks.toml --max-target-megabytes 2 '--log-opts=--merges --diff-merges=first-parent HEAD' .",
    f"FIX ROUND: python3 {BP}/classify_findings.py <private dir> <out> <repo>   # per finding: rule, value shape, count of other HEAD-tracked files containing the value (git grep -F -f <private pattern file>); values never written; private dir deleted",
]
GL_RESULTS = [
    "control-default-rules exit=1: 6 findings (aws-access-token, generic-api-key x2 [config.py, alpaca.env], github-pat, private-key, slack-bot-token)",
    "control-repo-config exit=1: the same 6 findings under .gitleaks.toml (the repo allowlists do not suppress these shapes)",
    "head-repo-config (uncapped, first pass) exit=143 seconds=600: stopped by the guard's 600 s limit; no report",
    "head commits: 502 head=ba3e7c2b1c66 (full id in raw/gitleaks/exits.log) (402 non-merge + 100 merge commits)",
    "blobs over 2 MB reachable from HEAD: 163, all versions of docs/ecosystem/index.html",
    "head-repo-config-2mb exit=0 seconds=63: '402 commits scanned.' 'scanned ~973880469 bytes (973.88 MB) in 1m3.1s' 'no leaks found'",
    "oversized-head-index exit=1: 'scanned ~12918618 bytes (12.92 MB)' 'leaks found: 11' -> 1 generic-api-key (hex64 under openapi_sha256, also in 3 other tracked files) + 10 sourcegraph-access-token (hex40 values also present in catalogs/us-equities/star-audit.json or catalogs/*/trading-sources.json); all content-digest shaped",
    "FIX ROUND oversized-control exit=1: unmodified.html 11 findings, planted.html 12 (the extra one is the synthetic github-pat) -> dir-mode scan of a 13 MB blob detects an appended token",
    "FIX ROUND merge-control (4 commits, 1 merge whose resolution alone adds a synthetic token): merge-control-default exit=0 0 findings (default git scan misses resolution content); merge-control-first-parent exit=1 1 finding (github-pat)",
    "FIX ROUND oversized: 'blobs over 2 MB reachable from HEAD: 164' (the 163 listed at ba3e7c2 plus 43164e4bcd4a, the index.html rebuilt in 888793d); 'blobs written: 164 in 5 batches'; batch exits b00=1 b01=1 b02=1 b03=0 b04=0 (no 75/143); scanned bytes per batch 469628803+305991536+173984590+142676318+10780263 = 1103061510 = sum of listed blob sizes",
    "FIX ROUND oversized findings: 521 in 87 of 164 blobs (sourcegraph-access-token 434 hex40, generic-api-key 87 hex64 under openapi_sha256); unclassified 0: every value is digest-shaped and occurs in other HEAD-tracked files (e.g. catalogs/us-equities/star-audit.json, catalogs/us-equities/architecture/trading-sources.json, docs/native-dashboards.md)",
    "FIX ROUND merges: 'merge commits: 100'; merges-first-parent-2mb exit=0 seconds=22: '100 commits scanned.' 'scanned ~479562184 bytes (479.56 MB)' 'no leaks found'",
    "allrefs-repo-config-2mb exit=1 seconds=68: 'all-ref commits: 1216', '1047 commits scanned', 'leaks found: 7'; all 7 are on commits NOT in this branch's ancestry: 4x generic-api-key observability/memory-scheduled-20260923.json @b801fe474 (codex/memory-scheduled-evidence-20260923), 2x generic-api-key evidence/artifacts/gap-wave2-20260923/foundation__durable-memory/raw/*.txt @711187171 (claude/g2-durable-memory-20260923), 1x generic-api-key tests/test_lane_packets.py @34fc51bea (claude/gc-pr5-packets); not triaged here (other owners)",
]
GL_RAW = ["gitleaks/exits.log", "gitleaks/control-default-rules.json", "gitleaks/control-default-rules.stderr",
          "gitleaks/control-repo-config.json", "gitleaks/control-repo-config.stderr",
          "gitleaks/head-repo-config.stderr", "gitleaks/head-repo-config-2mb.json",
          "gitleaks/head-repo-config-2mb.stderr", "gitleaks/head-blobs-over-2mb.txt",
          "gitleaks/oversized-head-index.json", "gitleaks/oversized-head-index.stderr",
          "gitleaks/oversized-classification.txt", "gitleaks/allrefs-repo-config-2mb.json",
          "gitleaks/allrefs-repo-config-2mb.stderr", "gitleaks-fix/exits.log", "gitleaks-fix/oversized-blobs-now.txt",
          "gitleaks-fix/classified.json", "gitleaks-fix/oversized-control.stderr", "gitleaks-fix/merge-control-default.stderr",
          "gitleaks-fix/merge-control-first-parent.stderr", "gitleaks-fix/oversized-b00.stderr", "gitleaks-fix/oversized-b01.stderr",
          "gitleaks-fix/oversized-b02.stderr", "gitleaks-fix/oversized-b03.stderr", "gitleaks-fix/oversized-b04.stderr",
          "gitleaks-fix/merges-first-parent-2mb.stderr"]
GL_LIMITS = [
    "Size exclusion (closed in the fix round): the 2 MB-capped history scan skipped 163 versions of docs/ecosystem/index.html; the fix round scanned all 164 blobs > 2 MB reachable from HEAD d67f77a as whole files in dir mode (byte totals match the listed sizes). Uncapped `gitleaks git` over history exceeded the guard's 600 s limit (exit 143) and the limit was not raised. Blob scans cover content, not the diff/commit metadata of those versions.",
    "Merge commits (closed in the fix round): the default `git log -p` walk shows no diff for the 100 merge commits; the fix round scanned each merge against its first parent (a superset of resolution-only content), with a control showing the default walk misses and the first-parent walk finds resolution-only content. That scan kept the 2 MB cap; index.html versions produced by merges are among the 164 blobs scanned whole.",
    "Classification of the 521 historical findings is by value shape and presence in other tracked files (content digests / commit ids in catalogs); it is not a manual review of each occurrence.",
    "Decode depth 5 and archive depth 0 (gitleaks defaults) applied; nested archives are not traversed.",
    "The history scan is of HEAD ba3e7c2 ancestry and the fix-round scans of HEAD d67f77a; later commits on this branch (these receipts) are covered by the post-commit range scan reported in the handoff, not by this receipt.",
    "Pattern scanning cannot certify that no secrets exist or that every secret type is detectable; the control shows only that the 6 planted shapes are detected.",
]

SYFT_CMDS = [
    f"bash {BP}/syft_binary_coverage.sh venv   # syft scan dir:<nautilus rc5 venv> --select-catalogers +binary-classifier-cataloger,+elf-binary-package-cataloger,+cargo-auditable-binary-cataloger,+go-module-binary-cataloger ; grype sbom:<that>",
    "first attempt with --select-catalogers +binary: exit=1 'invalid expression: \"binary\": tags are not allowed with this operation (must use exact names)'",
    f"bash {BP}/syft_binary_coverage.sh root   # ecosystem-bounded-run (1200 s, 8G) syft scan dir:/ (same catalogers) --exclude ./proc/** ./sys/** ./dev/** ./mnt/** ./run/** ./tmp/** ./home/** ./root/** ./lost+found/** ./var/tmp/** ; grype sbom:<that>; dpkg-query -W",
    f"bash {BP}/syft_binary_coverage.sh interp   # syft dir:<uv-managed CPython 3.13.15 used by the SDK venv> ; grype",
    f"bash {BP}/syft_binary_coverage.sh ibkr   # syft dir:$HOME/Jts/ibgateway/1050/{{jars,jre}} (data/ not read) and dir:<ibkr-lane venv>; grype each",
]
SYFT_RESULTS = [
    "venv-syft exit=0 seconds=8; venv-grype exit=0: 21 packages, all python-installed-package-cataloger; 74 .so files (ELF metadata recorded for all 74); 0 .so files tied to a package identity; binary-identified packages: none; grype matches 0",
    "root-syft exit=0 seconds=608; root-grype exit=0 seconds=20: 3034 packages (linux-kernel-module 961, binary 842 [PE], deb 834 [677 dpkg-db + 157 deb-archive], go-module 277, python 61, dotnet 55, java-archive 4)",
    "dpkg-db packages 677 == dpkg-query 677 (both 677, dpkg-query-only 0)",
    "host .so files with ELF metadata 1221, of which 1159 related to a package (dpkg ownership)",
    "root grype matches 5433: deb 3036, go-module 2397; severities Medium 3952, High 1012, Low 254, Critical 184, Negligible 21, Unknown 10 (Grype DB built 2026-09-23T06:31:39Z)",
    "Nautilus venv interpreter is /usr/bin/python3.12 (pyvenv.cfg home=/usr/bin): covered by dpkg python3.12 3.12.3-1ubuntu0.17; grype 17 matches on each python3.12 deb package",
    "SDK interpreter (uv CPython 3.13.15, under $HOME, outside the root scan): binary-classifier identified python 3.13.15; grype 8 matches (cpe-based)",
    "IB Gateway 1050 jars: 25 java-archive packages, grype 17 matches (High 9, Medium 8), e.g. jackson-databind 2.12.3 (9), jackson-core 2.12.3 (3), log4j-core 2.25.3 (3, Medium), commons-io 2.11.0 (1, High)",
    "IB Gateway bundled JRE: openjdk 25.0.2.0.101 identified by binary classifier, grype 22 matches (cpe-match; High 5, Medium 10, Low 7)",
    "IBKR adapter venv (nautilus_ibapi 10.45.1, protobuf 5.29.6, defusedxml 0.7.1): grype 0 matches",
]
SYFT_RAW = ["syft-binary/exits.log", "syft-binary/exits.attempt1-tag-rejected.log", "syft-binary/venv.syft.attempt1.stderr",
            "syft-binary/venv-so-files.txt", "syft-binary/venv.grype.json", "syft-binary/syft-summaries.json",
            "syft-binary/grype-summaries.json", "syft-binary/dpkg-query.tsv", "syft-binary/root.syft.stderr.txt",
            "syft-binary/root.grype.stderr", "syft-binary/interp.grype.json", "syft-binary/ibkr-venv.grype.json"]
SYFT_LIMITS = [
    "Bundled native code inside wheels (Rust in nautilus_trader/_libnautilus, Cython/C extensions, numpy.libs OpenBLAS/gfortran, duckdb) is inventoried as ELF files but gets no package identity: no cargo-auditable data or binary classifier matched, so vulnerabilities in statically linked crates/libraries are not matched.",
    "Root scan excluded /home, /root, /tmp, /var/tmp, /mnt (Windows drives), /run, /proc, /sys, /dev and lost+found; permission-denied paths (e.g. /etc/ssl/private, /var/spool/cron/crontabs) were skipped (see root.syft.stderr.txt). Software under $HOME was covered only for the targeted directories named above.",
    "IBKR server-side software and the IB Gateway's runtime-downloaded components are not scannable from this host; only the locally installed Gateway jars/JRE were scanned.",
    "Grype matches are database matches (exact-direct for Java/Python, CPE for binaries and some OS packages), not reachability or exploitability findings; CPE matches can be false positives.",
    "The full root/venv Syft and Grype JSON (31.6 MB and 50.7 MB for root) are not committed; syft-summaries.json and grype-summaries.json record their sizes and SHA-256 and deterministic summaries.",
]

OB_CMDS = [
    f"bash {BP}/openbao_install.sh   # curl the v2.6.2 linux/amd64 archive, checksums.txt and .sigstore.json bundles into the isolated cache",
    "sha256sum -c against the GitHub asset digest and the publisher checksums.txt",
    "cosign verify-blob --bundle checksums.txt.sigstore.json --certificate-identity https://github.com/openbao/openbao/.github/workflows/release.yml@refs/heads/release/2.6.x --certificate-oidc-issuer https://token.actions.githubusercontent.com checksums.txt (and the archive)",
    f"bash {BP}/openbao_lifecycle.sh   # bao server -dev -dev-listen-address=127.0.0.1:<ephemeral> -dev-root-token-id=<random> -dev-no-store-token, temp HOME",
    "bao policy write broker-reader / research; bao kv put secret/broker/alpaca-paper (synthetic); bao token create -policy=broker-reader|research -ttl=15m",
    "bao kv get (broker token, research token); bao kv put (rotation); bao kv destroy -versions=1; bao token revoke; bao kv get / token lookup after revoke",
]
OB_RESULTS = [
    "github asset digest exit=0; publisher checksum list exit=0; cosign verify-blob checksums.txt exit=0 'Verified OK'; archive exit=0 'Verified OK'; NEGATIVE tampered archive exit=1; NEGATIVE wrong identity (tag ref) exit=1",
    "first identity attempt (tag-ref regexp) exit=1: SAN was .../release.yml@refs/heads/release/2.6.x (retained log)",
    "OpenBao v2.6.2 (dd9c19c37a878cf4a81b18efb8d6f0599c7da923); bao sha256 8d180523...3b00",
    "policy-broker-reader exit=0; policy-research exit=0; kv-put-v1 exit=0; token-create-broker exit=0; token-create-research exit=0",
    "broker-token-read-v1 exit=0 (read value matches v1: yes)",
    "research-token-read-broker-DENIED exit=2 err=[Code: 403]; research-token-read-own-path exit=0; broker-token-write-DENIED exit=2 err=[Code: 403]",
    "kv-rotate-v2 exit=0; broker-token-read-after-rotation exit=0 (matches v2: yes; differs from v1: yes); kv-destroy-v1 exit=0; read-destroyed-v1 exit=2; metadata current_version 2 {'1': True, '2': False} (destroyed flags)",
    "token-revoke-broker exit=0; broker-token-read-after-revoke-DENIED exit=2 err=[Code: 403]; broker-token-lookup-after-revoke-DENIED exit=2 err=[Code: 403]; research-token-still-valid exit=0; token-revoke-research exit=0",
    "server stopped; listeners_left_on_port=0; unexpected_steps=0 (the driver's final `grep -c UNEXPECTED` returned 1 because the count was 0)",
]
OB_RAW = ["openbao/install.log", "openbao/install.attempt1-wrong-identity-regexp.log", "openbao/lifecycle.log"]

ENV_CMDS = [
    f"bash {BP}/worker_env_check.sh",
    "A: equity-worker-sdk python: CodexClient(CodexConfig(codex_bin=<stub that records env names>, env={CODEX_HOME, CONTEXT_MODE_PROJECT_DIR, OTEL_RESOURCE_ATTRIBUTES})).start()  # exactly the env overlay native_worker.py passes",
    "A1 launcher env + synthetic canaries for APCA_API_KEY_ID APCA_API_SECRET_KEY APCA_API_BASE_URL ALPACA_API_KEY ALPACA_SECRET_KEY TWS_USERNAME TWS_PASSWORD TWS_ACCOUNT IBKR_ACCOUNT_ID; A2 env -i PATH=/usr/bin:/bin HOME=<temp>",
    "B: CODEX_HOME=<temp empty> codex sandbox -- /bin/sh -c '<list broker var names; count /proc/*/environ containing the canary>'  (default shell_environment_policy); control: same probe unsandboxed",
    "B2: codex sandbox -c shell_environment_policy.inherit=none -- ...; B3: codex sandbox -c shell_environment_policy.ignore_default_excludes=false -- ...",
]
ENV_RESULTS = [
    "A:launcher-with-broker-env exit=0 broker_vars_in_codex_child=[ALPACA_ACCOUNT_PROFILE,ALPACA_API_KEY,ALPACA_PAPER,ALPACA_PAPER_ENDPOINT,ALPACA_SECRET_KEY,APCA_API_BASE_URL,APCA_API_KEY_ID,APCA_API_SECRET_KEY,IBKR_ACCOUNT_ID,TWS_ACCOUNT,TWS_PASSWORD,TWS_USERNAME]",
    "A:dedicated-research-env exit=0 broker_vars_in_codex_child=[]",
    "B:codex-sandbox-default-policy exit=0 broker_vars_in_shell=[<same 12 names>] procs_with_canary_in_environ=2",
    "B:control-unsandboxed broker_vars_in_shell=[<same 12 names>] procs_with_canary_in_environ=1",
    "B2:codex-sandbox-inherit-none exit=0 broker_vars_in_shell=[] procs_with_canary_in_environ=0",
    "B3:codex-sandbox-default-excludes-on exit=0 broker_vars_in_shell=[ALPACA_ACCOUNT_PROFILE,ALPACA_PAPER,ALPACA_PAPER_ENDPOINT,APCA_API_BASE_URL,IBKR_ACCOUNT_ID,TWS_ACCOUNT,TWS_PASSWORD,TWS_USERNAME] procs_with_canary_in_environ=2",
    "ambient_launcher_broker_var_names=[ALPACA_ACCOUNT_PROFILE,ALPACA_API_KEY,ALPACA_PAPER,ALPACA_PAPER_ENDPOINT,ALPACA_SECRET_KEY,APCA_API_BASE_URL,APCA_API_KEY_ID,APCA_API_SECRET_KEY] (names only; values were not read and may be empty)",
    "codex-cli 0.155.1",
]
ENV_RAW = ["worker-env/results.log"]
ENV_LIMITS = [
    "Detection method: per-run random canary values placed in the launcher environment; a variable is reported present when its NAME reaches the child, and /proc/*/environ is searched for the canary VALUE. A1 and the unsandboxed control show the probe detects presence.",
    "The SDK child was a stub standing in for the codex binary (no model call, no account access); `codex sandbox` exercises the Linux sandbox and shell_environment_policy directly, not a full model-driven turn.",
    "The Alpaca paper-order attempt arm needs broker contact; it is deferred to peer session sota-workflow-resolution (owner of broker/paper lanes and gate rows).",
    "Ambient broker variable names were observed in this host's launcher environment; their values were not read, so whether they hold live credentials is unknown.",
    "native_worker.py was not changed; enforcing a scrubbed environment (env -i launch or shell_environment_policy.inherit=none plus an SDK-side environment allowlist) is a follow-up for the worker owner.",
]

CMP_CMDS = [
    f"bash {BP}/scanner_comparison.sh install   # trivy 0.74.0 (asset digest, checksum list, cosign bundle), osv-scanner 2.6.0 (asset digest, SHA256SUMS), pip-audit 2.10.1 via uv into an isolated venv",
    f"bash {BP}/scanner_comparison.sh scan",
    "syft scan dir:<nautilus rc5 site-packages> -o syft-json -o cyclonedx-json",
    "ecosystem-bounded-run trivy rootfs --scanners vuln --list-all-pkgs --cache-dir <isolated> <same site-packages>",
    "grype sbom:<syft json>; osv-scanner scan source -L <syft cdx json>; pip-audit --path <same site-packages> --format json",
    "positive controls: trivy fs <dir with requirements.txt requests==2.19.0 urllib3==1.24.1>; osv-scanner -L that requirements.txt; pip-audit -r that file --no-deps --disable-pip; grype purl: control from gap 0",
]
CMP_RESULTS = [
    "trivy-asset-digest exit=0; trivy-checksum-list exit=0; trivy-cosign-verify exit=0 'Verified OK'; osv-asset-digest exit=0; osv-checksum-list exit=0; pip-audit-install exit=0 (first venv attempt exit=1: host python lacks ensurepip; retried with uv)",
    "trivy DB downloaded from mirror.gcr.io/aquasec/trivy-db:2 (116.44 MiB), UpdatedAt 2026-09-23T12:53:55Z",
    "syft 21 python packages; trivy 21 python-pkg packages; raw (name, version) difference: syft-only [pydantic-core 2.46.5, typing-extensions 4.16.0], trivy-only [pydantic_core 2.46.5, typing_extensions 4.16.0]; after PEP 503 name normalization (lowercase, [-_.]+ -> '-'): syft-only [], trivy-only [], both 21 (raw/compare/inventory-diff.json, computed by inventory_diff.py from the committed raw files)",
    "grype-venv exit=0: 0 matches; trivy-rootfs exit=0: 0 vulnerabilities; osv-venv exit=0: stderr 'found 21 packages', osv.json '\"results\": []'; pip-audit-venv-scan exit=0: stderr 'No known vulnerabilities found', pip-audit.json 21 dependencies, 0 vulns",
    "positive controls: grype 17 GHSA ids; trivy 17 CVE ids; osv-scanner exit=1 34 ids (17 GHSA + PYSEC aliases, 17 groups); pip-audit exit=1 'Found 34 known vulnerabilities in 2 packages'; all 17 grype GHSA ids appear in osv-scanner's 17 alias groups",
]
CMP_RAW = ["compare/exits.log", "compare/versions.txt", "compare/syft.summary.json", "compare/trivy.json",
           "compare/trivy.stderr.txt", "compare/trivy-positive.json", "compare/grype.json",
           "compare/osv.stderr.filtered.txt", "compare/osv-positive.json", "compare/pip-audit.json",
           "compare/pip-audit-positive.json", "compare/positive/requirements.txt.fixture", "compare/trivy-cosign.stderr",
           "compare/osv.json", "compare/pip-audit.stderr", "compare/pip-audit-positive.stderr", "compare/scan.driver.log",
           "compare/inventory-diff.json"]

G = {
    0: dict(commands=GRYPE_SDK_CMDS, results=GRYPE_SDK_RESULTS, raw=GRYPE_SDK_RAW, outcome="settled",
            evidence_class="native_proven",
            note="Grype ran on the exact 2026-09-19 equity-worker-sdk SBOM (36 packages), DB build time and match count (0) recorded; two positive controls on the same DB produced 5 and 17 matches.",
            limits=["Zero matches means no database match for these versions on this DB build; it is not a safety guarantee.",
                    "Scan target is the SBOM (Python package metadata), not native code inside the wheels (see gaps 3/9).",
                    FIRST_PASS + " The first pass ran the same Grype commands; this receipt cites the 16:26Z rerun (grype_sdk.sh) against the same DB."]),
    10: dict(commands=GRYPE_SDK_CMDS + ["git show ba3e7c2 -- blueprints/us-equities/supply-chain/README.md"],
             results=GRYPE_SDK_RESULTS + [
                 "README section 'Vulnerability scan - pinned NautilusTrader 2.0.0rc5 runtime ...' now reads: 'This scan targeted the NautilusTrader rc5 runtime, **not** the 36-package `equity-worker-sdk` inventoried above.' and a new section 'Vulnerability scan of the September 19 equity-worker-sdk SBOM, September 23, 2026' records the 36-package / 0-match result and controls (commit ba3e7c2)"],
             raw=GRYPE_SDK_RAW, outcome="settled", evidence_class="native_proven",
             note="SDK SBOM scanned (gap 0 evidence) and the README wording corrected to the target actually scanned.",
             limits=["Same limits as gap 0."]),
    2: dict(commands=SIG_CMDS, results=SIG_RESULTS, raw=SIG_RAW, outcome="advanced", evidence_class="native_proven",
            note="Syft and Grype: cosign keyless verification exit 0 with exact workflow identity and commit, negative controls exit 1, installed binaries byte-identical to the verified archives; signature_verified now set from these exit codes. Remains: gitleaks 8.30.1 publishes no signature and no GitHub attestation, so it stays checksum-only.",
            limits=["Verification covers the signed checksum files (cosign signs the checksum list, not each archive); the archive is tied to it by sha256.",
                    "cosign v3.1.3 itself was verified only by checksum and GitHub asset digest.",
                    "Gitleaks provenance cannot be established from upstream artifacts; a reproducible source build was not attempted.",
                    FIRST_PASS + " signatures.log is from the first pass (08:15Z); the attestation positive control was re-run at 16:4xZ with its exact command recorded."]),
    13: dict(commands=SIG_CMDS, results=SIG_RESULTS, raw=SIG_RAW, outcome="advanced", evidence_class="native_proven",
             note="Native cosign verify-blob with --certificate-identity(-regexp) and the GitHub OIDC issuer succeeded for the syft and grype releases (tampered blob and wrong identity fail). Remains: gitleaks has no upstream signature to verify.",
             limits=["Same limits as gap 2."]),
    3: dict(commands=SYFT_CMDS, results=SYFT_RESULTS, raw=SYFT_RAW, outcome="advanced", evidence_class="native_proven",
            note="Venv scan with binary catalogers plus a host-root scan (677 OS packages, 1159/1221 host .so files attributed) piped to Grype, the SDK interpreter and local IB Gateway jars/JRE also scanned. Remains: the 74 bundled .so files in the Nautilus venv get no package identity (statically linked Rust/C code unmatched), IBKR server-side software is unscannable here, and $HOME was covered only for targeted dirs.",
            limits=SYFT_LIMITS),
    9: dict(commands=SYFT_CMDS, results=SYFT_RESULTS, raw=SYFT_RAW, outcome="advanced", evidence_class="native_proven",
            note="syft dir:/ with binary catalogers + grype ran (3034 packages, 5433 matches); OS packages fully covered (677 = dpkg-query), both external interpreters covered (dpkg python3.12; uv CPython 3.13.15 by binary classifier), local IB Gateway scanned. Remains: complete bundled native-library coverage and broker-side coverage.",
            limits=SYFT_LIMITS),
    5: dict(commands=GL_CMDS, results=GL_RESULTS, raw=GL_RAW, outcome="advanced", evidence_class="native_proven",
            note="Guarded gitleaks over the full HEAD ancestry (502 commits; 402 non-merge commits with diffs) exited 0 with no findings under the repo config and a 2 MB cap. Fix round: all 164 blobs > 2 MB reachable from HEAD (every docs/ecosystem/index.html version) were scanned whole (521 findings, all digest-shaped values present in other tracked files), and the 100 merge commits were scanned against their first parent (0 findings), each method with a detection control. Commit count, exit codes and the remaining limits are recorded. Remains only the clause no pattern scanner can close: certifying that no secrets exist (permanent limit, so the outcome stays advanced per the fix-round preregistration).",
            limits=GL_LIMITS),
    12: dict(commands=GL_CMDS, results=GL_RESULTS, raw=GL_RAW, outcome="advanced", evidence_class="native_proven",
             note="Current full-HEAD-history scan recorded with commit count and exclusions; the positive control detected 6/6 planted secret shapes (5 rule types) under both default and repo configs. Fix round closed the size exclusion (164 oversized blobs scanned whole) and the merge exclusion (100 merges against first parent), each with a detection control. Remains only the clause no pattern scanner can close: detection of every secret type (permanent limit, so the outcome stays advanced per the fix-round preregistration).",
             limits=GL_LIMITS),
    6: dict(commands=OB_CMDS, results=OB_RESULTS, raw=OB_RAW, outcome="advanced", evidence_class="native_proven",
            note="Pinned, cosign-verified OpenBao 2.6.2 dev server on loopback: KV write, policy-scoped token issue, read, rotation (new version, old destroyed), token revoke and post-revoke denial all returned the expected exit codes. Remains: no catalog winner is wired to manage or scope the broker environment variables (a catalog/runtime decision), and dev mode is in-memory, unsealed and single-node.",
            limits=["Dev server only (in-memory storage, auto-unsealed, root token); no production storage, sealing, TLS, audit device or HA was exercised.",
                    "The credential was synthetic; no broker credential was read or stored.",
                    "Delivery of the secret into a broker process environment (agent/template, env injection) was not exercised."]),
    14: dict(commands=OB_CMDS + ENV_CMDS, results=OB_RESULTS + ENV_RESULTS, raw=OB_RAW + ENV_RAW, outcome="advanced",
             evidence_class="local_integration",
             note="Issuance, rotation, revocation, post-revoke read failure and research-policy denial (403) were shown on OpenBao. The worker environment check shows the SDK overlays its env onto the parent environment and nothing enforces the documented launch (blueprints/us-equities/workers/README.md: launch from a dedicated research environment with no broker secrets): the documented launch (A2) gave the codex child zero broker variables, but an undocumented launch from this host's launcher (A1) forwarded every broker variable to the codex child and, under Codex's default shell policy, into sandboxed tool shells; only env -i or shell_environment_policy.inherit=none removed them. Remains: denial of broker authority to research workers is not established by default, and the paper-order arm is deferred to sota-workflow-resolution.",
             limits=ENV_LIMITS + ["OpenBao limits as in gap 6."]),
    7: dict(commands=CMP_CMDS, results=CMP_RESULTS, raw=CMP_RAW, outcome="settled", evidence_class="native_proven",
            note="Same Nautilus rc5 venv: Syft and Trivy inventories identical after PEP 503 name normalization (21/21; raw names differ only in '-' vs '_' for pydantic-core and typing-extensions); Grype, osv-scanner and pip-audit (plus Trivy) all report 0 vulnerabilities; every scanner detects the positive control (17 advisories, 34 ids with PYSEC aliases).",
            limits=["Agreement on a zero-finding target has little discriminating power; the positive control shows detection, not equal recall on real-world findings.",
                    "Different databases and times: Grype DB 2026-09-23T06:31:39Z, Trivy DB 2026-09-23T12:53:55Z, osv-scanner and pip-audit query live APIs at 16:42Z.",
                    "One venv (21 Python packages); no OS, binary or container comparison.",
                    "Network downloads: trivy archive 50.4 MB, trivy DB 116.44 MiB, osv-scanner 57.5 MB, pip-audit and dependencies from PyPI."]),
    8: dict(commands=ENV_CMDS, results=ENV_RESULTS, raw=ENV_RAW, outcome="advanced", evidence_class="local_integration",
            note="Environment arm executed with canaries and a positive control: the documented launch from a dedicated research environment (A2) gave the codex child zero broker variables, but the SDK overlays the parent environment and nothing enforces that launch, so an undocumented launch from this host's launcher (A1, which already carries 8 broker-prefixed names) forwarded all broker variables to the codex child, and the default Codex sandbox shell policy forwarded them to tool shells. Only env -i or inherit=none removed them. Remains: the Alpaca paper-order failure arm (deferred, owner sota-workflow-resolution) and enforcing a scrubbed worker environment.",
            limits=ENV_LIMITS),
}


def receipt_path(idx: int) -> Path:
    matches = sorted(EV.glob(f"{idx}-*.json"))
    assert len(matches) == 1, (idx, matches)
    return matches[0]


def fill() -> None:
    sums = dict(line.split("  ", 1)[::-1] for line in (EV / "raw/SHA256SUMS").read_text().splitlines())
    for idx, g in G.items():
        p = receipt_path(idx)
        r = json.loads(p.read_text())
        prereg = json.dumps(r["preregistration"], sort_keys=True)
        missing = [x for x in g["raw"] if x not in sums]
        assert not missing, (idx, missing)
        r.update(commands=g["commands"], results=g["results"], outcome=g["outcome"],
                 evidence_class=g["evidence_class"], outcome_note=g["note"], limits=g["limits"], checked_at=NOW,
                 raw_outputs=[{"path": f"raw/{x}", "sha256": sums[x]} for x in g["raw"]],
                 helper_scripts=sorted(f"{BP}/{s.name}" for s in (REPO / BP).glob("*") if s.suffix in (".sh", ".py")),
                 timeline={"preregistration_written_at": r["preregistration"]["written_at"],
                           "first_pass": "2026-09-23T08:13:24Z..08:27:10Z (same unit, earlier session)",
                           "this_pass": "2026-09-23T16:26Z..%s" % NOW,
                           "post_preregistration_additions": "all-refs gitleaks scan, oversized-file dir scan, SDK interpreter and IB Gateway scans, B2/B3 sandbox policy arms, and the attestation-lookup positive control were added after preregistration as stronger checks of the same claims",
                           "fix_round": "after the independent Opus review: fix_round_preregistration written 2026-09-23T16:56:53Z (commit d67f77a) before the oversized-blob, merge first-parent and control scans (16:58Z..17:00Z) and the osv/inventory re-analysis"})
        if idx in (8, 14):
            r["deferred_arm"] = {"arm": "Alpaca paper order attempt from the research worker must fail",
                                 "owner": "sota-workflow-resolution",
                                 "blocker": "broker contact / paper-account calls belong to the peer session's lanes"}
        assert json.dumps(r["preregistration"], sort_keys=True) == prereg
        p.write_text(json.dumps(r, indent=2) + "\n")
        print(f"filled {p.name}: {g['outcome']}")


def results() -> None:
    out = {}
    for p in sorted(EV.glob("[0-9]*-*.json"), key=lambda q: int(q.name.split("-", 1)[0])):
        r = json.loads(p.read_text())
        out[str(r["gap_index"])] = {"outcome": r["outcome"], "receipt": p.name,
                                    "receipt_sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    (EV / "results.json").write_text(json.dumps({"layer": "us-equities/security-supply-chain", "generated_at": NOW,
                                                 "generated_by": f"{BP}/write_receipts.py --results",
                                                 "gaps": out}, indent=2) + "\n")
    print(json.dumps({k: v["outcome"] for k, v in out.items()}))


if __name__ == "__main__":
    if "--results" in sys.argv:
        results()
    else:
        fill()
