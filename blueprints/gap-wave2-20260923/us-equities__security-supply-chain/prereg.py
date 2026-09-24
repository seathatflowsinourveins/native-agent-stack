#!/usr/bin/env python3
"""Write preregistration-only receipt skeletons before any gap check runs.

Refuses to overwrite an existing receipt so a preregistration cannot be
silently re-dated after results exist.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

UNITS = Path(sys.argv[1])
OUT = Path(__file__).resolve().parents[3] / "evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain"

SLUGS = {
    0: "grype-sdk-sbom",
    2: "signature-provenance",
    3: "syft-binary-os-coverage",
    5: "gitleaks-current-history",
    6: "openbao-secret-lifecycle",
    7: "scanner-comparison",
    8: "research-worker-broker-authority",
    9: "syft-root-binary-coverage",
    10: "grype-sdk-readme-correction",
    12: "gitleaks-full-history-types",
    13: "cosign-verify-blob",
    14: "openbao-and-worker-denial",
}

PREREG = {
    0: ("Grype 0.119.0 on the 2026-09-19 equity-worker-sdk Syft SBOM reports 36 packages scanned with a fresh DB; match count unknown in advance (could be >0 because openai/codex/exchange-calendars were never scanned).",
        ["settled if grype exits 0 on the exact 2026-09-19 SBOM (sha256 recorded), the scanned package count is 36, DB build time and match count are recorded, and a positive-control SBOM with a known-vulnerable package yields >=1 match on the same DB (shows the probe can detect matches)",
         "not_settled if grype fails or the package count differs from 36 without explanation"]),
    2: ("Syft and Grype publish cosign keyless signatures of their checksum files (.sig/.pem); gitleaks 8.30.1 may publish no cosign signature. Expect syft/grype verify-blob exit 0 and gitleaks either unsupported or verified via another native attestation.",
        ["settled only if all three installed tools (syft, grype, gitleaks) get an upstream signature/provenance verification with exit 0 and the installed archive/binary is tied to the verified checksum file",
         "advanced if at least one tool verifies and the others lack an upstream signature (record exact absence evidence)",
         "negative control: verify-blob against a tampered checksum file must fail (non-zero), proving the check can detect failure"]),
    3: ("syft dir:<nautilus rc5 venv> with +binary catalogers finds some but not all bundled .so files as packages; a dpkg-db scan of / enumerates host OS packages; grype matches OS packages (likely >0 matches).",
        ["advanced if the venv binary scan and the host OS scan both run and are piped into grype with counts of .so files attributed vs total and OS packages/matches recorded; IBKR-side software cannot be scanned on this host (no IBKR install) and stays open",
         "settled only if every clause (Rust/Cython/.so, host OS, IBKR-side, code outside venv) is covered"]),
    5: ("Guarded gitleaks git over the full HEAD history of this repository (base 41d39b3) exits 0 with zero findings, or reports findings (redacted) with exit 1.",
        ["advanced/settled decision: the currency clause is closed if the guarded scan covers every commit reachable from HEAD (commit count cross-checked against git rev-list --count) with exit code, and limits (decode depth 5, archive depth 0, no size cap) recorded",
         "the clause 'does not certify that no secrets exist' cannot be closed by any pattern scanner; if it is the only remainder, record it as a permanent limit",
         "positive control: a temp repo with a synthetic secret-shaped string must yield a finding, proving the scan can detect"]),
    6: ("A pinned OpenBao release (checksum verified) runs `bao server -dev` on loopback; KV write, policy-scoped token issue, read, rotation (new version), token revoke all exit 0; read with revoked token fails (non-zero).",
        ["advanced if the full lifecycle succeeds with recorded exit codes but no catalog winner is wired to manage the broker env vars (a catalog/runtime decision outside this unit)",
         "settled only if the lifecycle succeeds and a managed/scoped delivery of broker variables is also demonstrated",
         "not_settled if any lifecycle step fails unexpectedly"]),
    7: ("Trivy and Syft agree on most of the 21 Python packages in the Nautilus venv; osv-scanner (or pip-audit) and Grype both report 0 vulnerabilities for the venv, and both detect the known-vulnerable positive control.",
        ["settled if all four arms run on the same venv: syft vs trivy package counts (with set difference) and grype vs osv-scanner/pip-audit matches, plus a positive control that each vulnerability scanner detects",
         "advanced if one arm cannot run here (record blocker)"]),
    8: ("The research worker (native_worker.py) does not scrub broker variables itself; it inherits the launcher environment. A documented dedicated-environment launch has no ALPACA_*/IBKR* vars.",
        ["the Alpaca paper order attempt arm requires broker contact/paper-account call, owned by peer session sota-workflow-resolution: deferred",
         "the environment arm is executed locally with canary (fake) values and a positive control (canary present in parent env must be detected in the worker child when not scrubbed)"]),
    9: ("syft dir:/ (excluding /proc, /sys, /dev, /mnt, /run, /tmp and user home trees) with binary catalogers enabled catalogs dpkg OS packages plus some ELF/binary packages; grype yields OS-package matches.",
        ["advanced if the scan runs and records covered OS packages/native library counts; external interpreter coverage recorded; broker-side coverage cannot be scanned on this host and remains open",
         "not_settled if the scan exceeds 20 minutes"]),
    10: ("Same run as gap 0 (grype on the 2026-09-19 SDK SBOM) plus a README correction that names the 21-package Nautilus runtime as the 2026-09-22 target and cites the new SDK scan.",
         ["settled if the grype run succeeds (as gap 0 criteria) and the README wording at the 2026-09-22 section is corrected in this branch",
          "advanced if either part is missing"]),
    12: ("Same guarded full-history gitleaks run as gap 5, plus a positive control covering several distinct secret types.",
         ["advanced: full-history cleanliness can be recorded for the default ruleset, but 'detection of every secret type' cannot be established by any scanner; record rule count and which control types were detected",
          "not_settled if the scan fails or is blocked"]),
    13: ("cosign verify-blob with --certificate-identity-regexp for the upstream release workflow and issuer https://token.actions.githubusercontent.com exits 0 for syft and grype checksum files; gitleaks has no cosign signature to verify.",
         ["settled only if every installed tool archive gets a successful verify-blob",
          "advanced if syft and grype verify and gitleaks has no upstream signature (absence recorded from the release asset list)",
          "negative control: tampered blob must fail"]),
    14: ("OpenBao dev lifecycle succeeds (issue scoped token, rotate, revoke, read fails after revoke); research-worker token under a research policy is denied the broker path; worker environment has no broker variables when launched as documented.",
         ["settled if both arms run: OpenBao lifecycle incl. post-revoke read failure and research-policy denial, and research-worker env check with a positive control",
          "advanced if the env check shows broker canaries can reach worker tool shells under some documented launch, or if an arm cannot run"]),
}


def main() -> int:
    units = json.loads(UNITS.read_text())
    entry = next(e for e in units if e.get("layer_id") == "security-supply-chain")
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    OUT.mkdir(parents=True, exist_ok=True)
    for gap in entry["gaps"]:
        idx = gap["index"]
        path = OUT / f"{idx}-{SLUGS[idx]}.json"
        if path.exists():
            print(f"skip existing {path.name}")
            continue
        expectation, criteria = PREREG[idx]
        receipt = {
            "id": f"gap-wave2-20260923/us-equities/security-supply-chain/{idx}",
            "gap_index": idx,
            "gap_text": gap["text"],
            "gap_text_sha256": hashlib.sha256(gap["text"].encode()).hexdigest(),
            "next_check": gap["next_check"],
            "preregistration": {"written_at": now, "expectation": expectation, "criteria": criteria},
            "commands": [], "results": [], "outcome": None, "evidence_class": None,
            "limits": [], "checked_at": None,
        }
        path.write_text(json.dumps(receipt, indent=2) + "\n")
        print(f"wrote {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
