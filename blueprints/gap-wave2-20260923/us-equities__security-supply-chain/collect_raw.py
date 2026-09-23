#!/usr/bin/env python3
"""Copy the raw outputs cited by the gap-wave-2 receipts into the evidence tree.

Host paths become $HOME, UUIDs become <uuid> (the publication validator treats
them as local session identifiers), and signed blob URLs are dropped. Outputs
too large to commit (full host SBOM/Grype JSON) are summarised deterministically
here; the summary records the full file's size and SHA-256 in the local cache.
Writes raw/SHA256SUMS over every committed raw file.
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import re
import sys
from pathlib import Path

HOME = os.path.expanduser("~")
C = Path(os.environ.get("C", f"{HOME}/.cache/gap-wave2-20260923/security-supply-chain"))
W = C / "work"
REPO = Path(__file__).resolve().parents[3]
RAW = REPO / "evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/raw"
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)
SIGNED = re.compile(r"https://tmaproduction\.blob\.core\.windows\.net/[^\"\s]+")


def sanitize(text: str) -> str:
    text = text.replace(HOME, "$HOME")
    text = UUID.sub("<uuid>", text)
    return SIGNED.sub("<signed-url-removed>", text)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(rel: str, text: str) -> None:
    # A captured output named .json that is not JSON (empty, or stdout mixed with warnings) is retained
    # as .json.txt, so evidence discovery, which parses every hash-listed .json, can read the tree.
    if rel.endswith(".json"):
        try:
            json.loads(text)
        except ValueError:
            rel += ".txt"
    dest = RAW / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(sanitize(text))


def copy(src_rel: str, dest_rel: str | None = None) -> None:
    put(dest_rel or src_rel, (W / src_rel).read_text(errors="replace"))


def big(src_rel: str) -> dict:
    p = W / src_rel
    return {"cache_path": "$HOME/" + str(p.relative_to(HOME)), "bytes": p.stat().st_size, "sha256": sha(p),
            "committed": False}


def grype_summary(src_rel: str, detail: bool = True) -> dict:
    g = json.loads((W / src_rel).read_text())
    m = g["matches"]
    out = {"source_file": big(src_rel), "db_built": g["descriptor"]["db"]["status"]["built"],
           "db_schema": g["descriptor"]["db"]["status"]["schemaVersion"], "grype_version": g["descriptor"]["version"],
           "matches": len(m),
           "by_artifact_type": dict(collections.Counter(x["artifact"]["type"] for x in m).most_common()),
           "by_severity": dict(collections.Counter(x["vulnerability"]["severity"] for x in m).most_common()),
           "by_match_type": dict(collections.Counter(x["matchDetails"][0]["type"] for x in m).most_common())}
    if detail:
        out["rows"] = sorted({(x["artifact"]["name"], x["artifact"]["version"], x["vulnerability"]["id"],
                               x["vulnerability"]["severity"], x["matchDetails"][0]["type"]) for x in m})
    return out


def syft_summary(src_rel: str) -> dict:
    d = json.loads((W / src_rel).read_text())
    arts = d["artifacts"]
    files = {f["id"]: f for f in d.get("files", [])}
    ex = [f for f in files.values() if f.get("executable")]
    so = {f["id"] for f in ex if ".so" in f["location"]["path"].rsplit("/", 1)[-1]}
    aid = {a["id"] for a in arts}
    related = {r["child"] for r in d["artifactRelationships"]
               if r["type"] in ("contains", "evident-by") and r["parent"] in aid and r["child"] in files}
    return {"source_file": big(src_rel), "syft_version": d["descriptor"]["version"],
            "source_name": d["source"]["name"], "packages": len(arts),
            "by_type": dict(collections.Counter(a["type"] for a in arts).most_common()),
            "by_cataloger": dict(collections.Counter(a.get("foundBy") for a in arts).most_common()),
            "executable_files": len(ex),
            "executable_formats": dict(collections.Counter(f["executable"]["format"] for f in ex)),
            "so_files_with_elf_metadata": len(so),
            "so_files_related_to_a_package": len(so & related),
            "binary_identified_packages": sorted({(a["name"], a["version"], a.get("foundBy")) for a in arts
                                                  if a["type"] == "binary" and a.get("foundBy") != "pe-binary-package-cataloger"}),
            "package_list": sorted({(a["type"], a["name"], a["version"]) for a in arts})
            if len(arts) <= 200 else "omitted (>200 packages); see by_type"}


def main() -> int:
    # Gaps 0/10
    for f in ("exits.log", "db-status.json", "sdk.grype.json", "mutated.grype.json", "positive.grype.json",
              "positive.purls", "sdk.stderr"):
        copy(f"grype-sdk/{f}")
    put("grype-sdk/sdk.grype.cdx.summary.json", json.dumps({
        "source_file": big("grype-sdk/sdk.grype.cdx.json"),
        "component_types": dict(collections.Counter(
            c["type"] for c in json.loads((W / "grype-sdk/sdk.grype.cdx.json").read_text())["components"]))}, indent=1))
    # Gaps 2/13 and OpenBao/trivy provenance
    copy("signatures/signatures.log")
    copy("signatures/gh-attestation-positive-control.json")
    copy("signatures/gh-attestation-positive-control.cmd")
    copy("openbao/install.log"); copy("openbao/install.attempt1-wrong-identity-regexp.log")
    # Gaps 5/12
    for f in ("exits.log", "control-default-rules.json", "control-default-rules.stderr", "control-repo-config.json",
              "control-repo-config.stderr", "head-repo-config-2mb.json", "head-repo-config-2mb.stderr",
              "head-repo-config.stderr", "head-blobs-over-2mb.txt", "oversized-head-index.json",
              "oversized-head-index.stderr", "oversized-classification.txt"):
        copy(f"gitleaks/{f}")
    for f in ("allrefs-repo-config-2mb.json", "allrefs-repo-config-2mb.stderr"):
        if (W / "gitleaks" / f).exists():
            copy(f"gitleaks/{f}")
    # Gaps 5/12 fix round: oversized historical blobs and merge first-parent diffs (redacted summaries only).
    gf = W / "gitleaks-fix"
    for f in ["exits.log", "oversized-blobs-now.txt", "classified.json"] + sorted(x.name for x in gf.glob("*.stderr")):
        copy(f"gitleaks-fix/{f}")
    # Gaps 3/9
    sb = "syft-binary"
    for f in ("exits.log", "exits.attempt1-tag-rejected.log", "venv.syft.attempt1.stderr", "venv-so-files.txt",
              "venv.grype.json", "interp.grype.json", "ibkr-venv.grype.json", "dpkg-query.tsv", "root.grype.stderr"):
        copy(f"{sb}/{f}")
    put(f"{sb}/root.syft.stderr.txt", (W / sb / "root.syft.stderr").read_text(errors="replace").replace("\r", "\n"))
    summ = {n: syft_summary(f"{sb}/{n}.syft.json") for n in ("venv", "root", "interp", "ibgw-jars", "ibgw-jre", "ibkr-venv")}
    root = json.loads((W / sb / "root.syft.json").read_text())
    debs = {(a["name"], a["version"]) for a in root["artifacts"] if a.get("foundBy") == "dpkg-db-cataloger"}
    dq = {tuple(line.split("\t")[:2]) for line in (W / sb / "dpkg-query.tsv").read_text().splitlines()}
    summ["root"]["dpkg_db_packages_vs_dpkg_query"] = {"syft_dpkg_db": len(debs), "dpkg_query": len(dq),
                                                      "both": len(debs & dq), "dpkg_query_only": len(dq - debs)}
    put(f"{sb}/syft-summaries.json", json.dumps(summ, indent=1))
    gs = {"root": grype_summary(f"{sb}/root.grype.json", detail=False)}
    for n in ("ibgw-jars", "ibgw-jre", "interp"):
        gs[n] = grype_summary(f"{sb}/{n}.grype.json")
    put(f"{sb}/grype-summaries.json", json.dumps(gs, indent=1))
    # Gaps 6/14
    copy("openbao/lifecycle.log")
    # Gaps 8/14
    copy("worker-env/results.log")
    # Gap 7
    cp = "compare"
    osv_err = (W / cp / "osv.stderr").read_text(errors="replace").splitlines()
    noise = [l for l in osv_err if l.startswith("Neither CPE nor PURL found for package")]
    put(f"{cp}/osv.stderr.filtered.txt", f"# {len(noise)} lines 'Neither CPE nor PURL found for package: <CycloneDX file component>' "
        f"removed (file components, not packages); full stderr {big(cp + '/osv.stderr')}\n"
        + "\n".join(l for l in osv_err if l not in noise) + "\n")
    for f in ("exits.log", "versions.txt", "trivy.json", "trivy-positive.json", "grype.json",
              "osv.json", "osv-positive.json", "pip-audit.json", "pip-audit.stderr", "pip-audit-positive.json",
              "pip-audit-positive.stderr", "trivy-cosign.stderr", "scan.driver.log"):
        copy(f"{cp}/{f}")
    # Retained under a non-manifest name so GitHub's dependency graph does not treat this deliberately
    # vulnerable positive control as a repository dependency (dependency review fails on high advisories).
    copy(f"{cp}/positive/requirements.txt", f"{cp}/positive/{NEW}")
    put(f"{cp}/trivy.stderr.txt", "\n".join(l for l in (W / cp / "trivy.stderr").read_text(errors="replace")
                                           .replace("\r", "\n").splitlines() if "MiB /" not in l) + "\n")
    put(f"{cp}/syft.summary.json", json.dumps(syft_summary(f"{cp}/syft.json"), indent=1))
    # Fix round: Syft vs Trivy set difference, raw and PEP 503-normalized, from the committed files.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import inventory_diff
    inventory_diff.main()
    # Checksums over everything committed.
    lines = [f"{sha(p)}  {p.relative_to(RAW)}" for p in sorted(RAW.rglob("*")) if p.is_file() and p.name != "SHA256SUMS"]
    (RAW / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    print(f"raw files: {len(lines)}; bytes: {sum((RAW / l.split('  ', 1)[1]).stat().st_size for l in lines)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
