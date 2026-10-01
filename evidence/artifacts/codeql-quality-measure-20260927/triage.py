#!/usr/bin/env python3
"""Join the triage verdicts to the drawn sample and compute population checks.

Evidence class: local integration (thin glue). Verdicts are human judgments
recorded in triage_verdicts.json; this script only checks that each verdict
names the same rule, path and line as the drawn alert, tallies them, and
computes structural population checks over the full SARIF result sets:
  - wrong-argument calls: where the resolved callee lives relative to the
    caller, and whether the caller's own project holds a module of the same
    name (the one its sys.path import would load);
  - uninitialized-variable results preceded by a never-returning call;
  - implicit string concatenation: whitespace at every literal boundary;
  - file-not-closed: chained open(...).read()/.write() one-liners;
  - share of code-quality results in evidence/ and in hash-listed files.
The volume-weighted extrapolation applies each sampled rule's verdict to
that rule's other results (results under evidence/ of a "real" rule count
as not actionable); it is an extrapolation, not a per-result verdict.

Usage: triage.py SARIF_DIR SOURCE_ROOT SAMPLE_JSON VERDICTS_JSON OUT_DIR
"""
import ast
import collections
import io
import json
import re
import subprocess
import sys
import tokenize
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import summarize_sarif as s  # noqa: E402

NORETURN = re.compile(r"skipTest\(|self\.fail\(|sys\.exit\(|os\._exit\(|\braise\b|pytest\.skip\(")
CHAINED_OPEN = re.compile(r"open\((?:[^()]|\([^()]*\))*\)\.(?:read|write|readlines)\(")


def main():
    sarif_dir, src, sample_path, verdicts_path, out_dir = map(Path, sys.argv[1:6])
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    verdicts = json.loads(verdicts_path.read_text(encoding="utf-8"))
    by_id = {v["id"]: v for v in verdicts["verdicts"]}
    rows = [("S", a) for a in sample["sample"]] + [("X", a) for a in sample["supplement"]]
    joined, mismatches = [], []
    counters = {"S": 0, "X": 0}
    for prefix, alert in rows:
        counters[prefix] += 1
        vid = f"{prefix}{counters[prefix]:02d}"
        v = by_id.get(vid)
        if v is None or (v["rule"], v["uri"], v["line"]) != (alert["rule"], alert["uri"], alert["line"]):
            mismatches.append(vid)
            continue
        joined.append({"id": vid, **alert, "verdict": v["verdict"], "value": v["value"], "reason": v["reason"]})
    if mismatches or len(joined) != len(by_id):
        sys.exit(f"verdicts do not align with the drawn sample: {mismatches}")

    def tally(items):
        return {
            "alerts": len(items),
            "by_verdict": dict(collections.Counter(j["verdict"] for j in items)),
            "real_actionable_by_value": dict(collections.Counter(j["value"] for j in items if j["verdict"] == "real_actionable")),
            "error_level_by_verdict": dict(collections.Counter(j["verdict"] for j in items if j["level"] == "error")),
            "by_language": {lang: dict(collections.Counter(j["verdict"] for j in items if j["language"] == lang))
                            for lang in sorted({j["language"] for j in items})},
        }

    main_rows = [j for j in joined if j["id"].startswith("S")]
    supp_rows = [j for j in joined if j["id"].startswith("X")]

    # Volume-weighted extrapolation over the code-quality result sets.
    tracked = subprocess.run(["git", "-C", str(src), "ls-files"], capture_output=True, text=True,
                             check=True).stdout.split()
    manifest = json.loads((src / "manifests" / "evidence.json").read_text(encoding="utf-8"))
    listed = {f["path"] for f in manifest["files"]}
    rule_verdict = {j["rule"]: j for j in main_rows}
    extrapolation, shares = {}, {}
    for lang in ("python", "javascript"):
        results = s.load(sarif_dir / f"{lang}-code-quality.sarif")["results"]
        c = collections.Counter()
        for r in results:
            j = rule_verdict.get(r["rule"])
            if j is None:
                cls = "unsampled_rule"
            elif j["verdict"] == "false_positive":
                cls = "false_positive"
            elif r["uri"].startswith("evidence/"):
                cls = "real_not_actionable"
            else:
                cls = f"real_actionable:{j['value']}"
            c[(cls, r["level"])] += 1
        by_class = collections.Counter()
        for (cls, _level), n in c.items():
            by_class[cls] += n
        extrapolation[s.LANGS[lang]] = {
            "by_class": dict(sorted(by_class.items())),
            "by_class_and_level": {f"{k[0]}|{k[1]}": n for k, n in sorted(c.items())},
        }
        shares[s.LANGS[lang]] = {
            "results": len(results),
            "under_evidence": sum(r["uri"].startswith("evidence/") for r in results),
            "in_hash_listed_files": sum(r["uri"] in listed for r in results),
            "evidence_files": len({r["uri"] for r in results if r["uri"].startswith("evidence/")}),
        }

    lines_cache = {}

    def lines(uri):
        if uri not in lines_cache:
            lines_cache[uri] = (src / uri).read_text(encoding="utf-8", errors="replace").splitlines()
        return lines_cache[uri]

    heur = {}
    cq_py = s.load(sarif_dir / "python-code-quality.sarif")["results"]
    calls = [r for r in cq_py if r["rule"] in ("py/call/wrong-arguments", "py/call/wrong-named-argument")]
    loc, same_name = collections.Counter(), collections.Counter()
    for r in calls:
        callee = r["related"][0].rsplit(":", 1)[0] if r["related"] else None
        if callee is None:
            loc["no_related_location"] += 1
            continue
        loc["same_file" if callee == r["uri"] else
            "same_project" if callee.split("/")[:3] == r["uri"].split("/")[:3] else "other_project"] += 1
        project = "/".join(r["uri"].split("/")[:3])
        base = callee.rsplit("/", 1)[-1]
        own = [p for p in tracked if p.startswith(project + "/") and p.rsplit("/", 1)[-1] == base]
        same_name["caller_project_has_same_named_module" if own else "no_same_named_module_in_caller_project"] += 1
    heur["wrong_argument_calls"] = {"results": len(calls), "callee_location": dict(loc),
                                    "same_named_module_in_caller_project": dict(same_name),
                                    "project_prefix": "first three path components"}
    saq_py = s.load(sarif_dir / "python-security-and-quality.sarif")["results"]
    unin = [r for r in saq_py if r["rule"] == "py/uninitialized-local-variable"]
    heur["uninitialized_local_variable"] = {"results": len(unin), "never_returning_call_in_prior_8_lines": sum(
        bool(NORETURN.search("\n".join(lines(r["uri"])[max(0, r["line"] - 9): r["line"] - 1]))) for r in unin)}
    raw = json.loads((sarif_dir / "python-code-quality.sarif").read_text(encoding="utf-8"))["runs"][0]["results"]
    spans, boundary, sites = collections.Counter(), collections.Counter(), []
    for r in raw:
        if r["ruleId"] != "py/implicit-string-concatenation-in-list":
            continue
        pl = r["locations"][0]["physicalLocation"]
        reg, uri = pl["region"], pl["artifactLocation"]["uri"]
        end_line = reg.get("endLine", reg["startLine"])
        spans["spans_lines" if end_line > reg["startLine"] else "single_line"] += 1
        seg = lines(uri)[reg["startLine"] - 1: end_line]
        seg[-1] = seg[-1][: reg.get("endColumn", len(seg[-1]) + 1) - 1]
        seg[0] = seg[0][reg.get("startColumn", 1) - 1:]
        frags = []
        try:
            for tok in tokenize.generate_tokens(io.StringIO("\n".join(seg)).readline):
                if tok.type == tokenize.STRING:
                    frags.append(ast.literal_eval(tok.string))
        except (tokenize.TokenError, IndentationError, ValueError, SyntaxError):
            frags = []
        if len(frags) < 2 or not all(isinstance(f, str) for f in frags):
            boundary["unparsed"] += 1
            continue
        ok = all(a[-1:].isspace() or b[:1].isspace() or a[-1:] in "-/" for a, b in zip(frags, frags[1:]) if a and b)
        boundary["whitespace_at_every_boundary" if ok else "boundary_without_whitespace"] += 1
        if not ok:
            sites.append(f"{uri}:{reg['startLine']}")
    heur["implicit_string_concatenation"] = {"span": dict(spans), "boundaries": dict(boundary),
                                             "boundary_without_whitespace_sites": sites}
    fnc = [r for r in cq_py if r["rule"] == "py/file-not-closed"]
    heur["file_not_closed"] = {
        "results": len(fnc),
        "chained_open_call_one_liners": sum(bool(CHAINED_OPEN.search(lines(r["uri"])[r["line"] - 1])) for r in fnc),
        "by_top_directory": dict(collections.Counter(r["top"] for r in fnc).most_common())}
    perm = [r for r in saq_py if r["rule"] == "py/overly-permissive-file"]
    heur["overly_permissive_file"] = {"results": len(perm),
                                      "by_top_directory": dict(collections.Counter(r["top"] for r in perm).most_common())}
    heur["code_quality_result_locations"] = shares
    js = s.load(sarif_dir / "javascript-code-quality.sarif")["results"]
    heur["javascript_code_quality_files"] = dict(collections.Counter(r["uri"] for r in js).most_common())

    triage = {"verdict_set": verdicts["verdict_set"], "value_set": verdicts["value_set"],
              "judged_by": verdicts["judged_by"], "seed": sample["seed"], "quotas": sample["quotas"],
              "supplement_counts": sample["supplement_counts"],
              "tally_main_sample": tally(main_rows), "tally_supplement": tally(supp_rows),
              "volume_weighted_extrapolation": extrapolation,
              "population_reviews": verdicts["population_reviews"],
              "alerts": joined}
    (out_dir / "triage.json").write_text(json.dumps(triage, indent=1) + "\n", encoding="utf-8")
    (out_dir / "heuristics.json").write_text(json.dumps(heur, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"main": triage["tally_main_sample"], "supplement": triage["tally_supplement"],
                      "extrapolation": extrapolation}, indent=1))
    print(json.dumps(heur, indent=1)[:3000])


if __name__ == "__main__":
    main()
