#!/usr/bin/env python3
"""Summarize CodeQL SARIF counts per suite, rule, severity and lane.

Evidence class: local integration (thin glue, not a tool). It only reads
fields defined by OASIS SARIF v2.1.0 (result.ruleId / result.rule,
result.level, reportingDescriptor.defaultConfiguration.level, whose default
is "warning" (SARIF 2.1.0 section 3.50.3), result.locations[0].physicalLocation)
and the rule properties GitHub documents in "SARIF support for code
scanning" (properties.security-severity, properties.tags,
properties.precision, properties.problem.severity).

Security-severity bands follow the CVSS v3.1 qualitative scale that
GitHub's "About code scanning alerts" cites: >= 9.0 critical, >= 7.0 high,
>= 4.0 medium, > 0 low.

Lane ownership comes from docs/lanes.md at the measured commit
("Path ownership" and "Trading tests"); paths it does not list are
reported as "unlisted", never guessed.

Usage: summarize_sarif.py LOCAL_SARIF_DIR LIVE_SARIF_DIR OUT_JSON
"""
import collections
import fnmatch
import json
import sys
from pathlib import Path

SUITES = ("code-scanning", "code-quality", "security-and-quality", "security-extended")
LANGS = {"python": "python", "javascript": "javascript-typescript", "actions": "actions"}

# docs/lanes.md "Path ownership" (trading and shared rows) and "Trading tests".
TRADING_PREFIXES = (
    "catalogs/us-equities/", "blueprints/us-equities/",
    "observability/paper-trading-live/",
)
TRADING_FILES = {
    "catalogs/landscape/us-equities.json", "scripts/trading_gates.py",
    "scripts/verify_nautilus_ci.py", "docs/paper-lane-policy.md",
    "docs/decisions/2026-09-22-broker-credential-handling.md",
}
TRADING_GLOBS = ("blueprints/gap-wave2-20260923/us-equities__*",)
TRADING_TESTS = (
    "test_trading_gates.py", "test_native_nautilus_ci.py", "adaptive_paper_hermetic.py",
    "test_adaptive_*.py", "test_alpaca_*.py", "test_broad_universe_*.py", "test_catalyst_*.py",
    "test_historical_*.py", "test_ibkr_*.py", "test_lifecycle_*.py", "test_mover_*.py",
    "test_order_*.py", "test_promotion_gate*.py", "test_research_*.py",
    "test_corporate_action_readiness.py", "test_delisting_coverage.py",
    "test_execution_realism.py", "test_extreme_gainer_audit.py", "test_financial_data.py",
    "test_ingest_snapshot.py", "test_memory_lifecycle.py", "test_nanosecond_replay.py",
    "test_native_faults_min.py", "test_nautilus_equity_replay.py", "test_pit_availability.py",
    "test_point_in_time.py", "test_security_identity.py", "test_spy_parity.py",
    "test_supply_chain_scan.py", "test_sim_*.py",
)
SHARED_FILES = {"manifests/evidence.json", "manifests/stack.json",
                "observability/grand-dashboard/state.json", "AGENTS.md"}
SHARED_GLOBS = ("catalogs/sota-convergence/*", "catalogs/landscape/gap-*.json", "docs/gap-*.md")
FOUNDATION_PREFIXES = (
    "catalogs/foundation/", "catalogs/convergence-practice/", "catalogs/saturation/",
    "catalogs/landscape/", "tools/", "recipes/", "examples/", "fixtures/", "adoption/",
    "evidence/hosts/", "docs/", "blueprints/", "observability/backends/",
    "observability/collector/", "observability/native-data/",
)


def lane(path: str) -> str:
    if path in SHARED_FILES or any(fnmatch.fnmatch(path, g) for g in SHARED_GLOBS):
        return "shared"
    if (path in TRADING_FILES or path.startswith(TRADING_PREFIXES)
            or any(fnmatch.fnmatch(path, g) for g in TRADING_GLOBS)):
        return "trading"
    if path.startswith("tests/"):
        name = path.split("/", 1)[1]
        if "/" not in name and any(fnmatch.fnmatch(name, g) for g in TRADING_TESTS):
            return "trading"
        # lanes.md: a test module belongs to the lane of the code it loads; the
        # listed modules are the trading ones, the rest load foundation code.
        return "foundation"
    if path.startswith(FOUNDATION_PREFIXES):
        return "foundation"
    return "unlisted"


def band(score):
    if score is None:
        return None
    return "critical" if score >= 9.0 else "high" if score >= 7.0 else "medium" if score >= 4.0 else "low" if score > 0 else None


def load(path: Path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    run = doc["runs"][0]
    tool = run["tool"]
    components = [tool["driver"]] + list(tool.get("extensions", []))
    rules = {}
    for comp in components:
        for rule in comp.get("rules", []) or []:
            rules[rule["id"]] = rule
    results = []
    for res in run.get("results", []):
        rid = res.get("ruleId") or (res.get("rule") or {}).get("id")
        rule = rules.get(rid, {})
        props = rule.get("properties", {})
        level = res.get("level") or rule.get("defaultConfiguration", {}).get("level") or "warning"
        sev = props.get("security-severity")
        sev = float(sev) if sev not in (None, "") else None
        loc = res["locations"][0]["physicalLocation"]
        uri = loc["artifactLocation"]["uri"]
        line = loc.get("region", {}).get("startLine")
        tags = props.get("tags", [])
        related = []
        for rel in res.get("relatedLocations", []) or []:
            rloc = rel.get("physicalLocation", {})
            related.append(f"{rloc.get('artifactLocation', {}).get('uri')}:{rloc.get('region', {}).get('startLine')}")
        results.append({
            "rule": rid, "level": level, "security_severity": sev, "band": band(sev),
            "precision": props.get("precision"), "problem_severity": props.get("problem.severity"),
            "tags": tags, "uri": uri, "line": line, "lane": lane(uri),
            "column": loc.get("region", {}).get("startColumn"),
            "top": uri.split("/", 1)[0] if "/" in uri else "(root)",
            "message": res.get("message", {}).get("text", ""),
            "related": related,
            "suppressed": bool(res.get("suppressions")),
        })
    versions = {c.get("name"): c.get("semanticVersion") or c.get("version") for c in components}
    return {"rules": rules, "results": results, "versions": versions}


def kind(r):
    t = set(r["tags"])
    if "security" in t:
        return "security"
    if "quality" in t or "maintainability" in t or "reliability" in t:
        sub = [x for x in ("reliability", "maintainability") if x in t]
        return "quality/" + (sub[0] if sub else "other")
    return "other"


def summarize(data):
    res = data["results"]
    per_rule = collections.defaultdict(lambda: {"count": 0, "lanes": collections.Counter()})
    for r in res:
        entry = per_rule[r["rule"]]
        entry["count"] += 1
        entry["lanes"][r["lane"]] += 1
        entry.update(level=r["level"], security_severity=r["security_severity"],
                     precision=r["precision"], kind=kind(r))
    return {
        "results": len(res),
        "rules_in_sarif": len(data["rules"]),
        "rules_with_results": len(per_rule),
        "by_level": dict(collections.Counter(r["level"] for r in res)),
        "by_security_band": dict(collections.Counter(r["band"] for r in res if r["band"])),
        "by_kind": dict(collections.Counter(kind(r) for r in res)),
        "by_lane": dict(collections.Counter(r["lane"] for r in res)),
        "by_lane_and_top_dir": {f"{k[0]}|{k[1]}": n for k, n in sorted(
            collections.Counter((r["lane"], r["top"]) for r in res).items())},
        "by_lane_and_level": {f"{k[0]}|{k[1]}": n for k, n in sorted(
            collections.Counter((r["lane"], r["level"]) for r in res).items())},
        "by_top_dir": dict(collections.Counter(r["top"] for r in res).most_common()),
        "suppressed": sum(r["suppressed"] for r in res),
        "error_level_non_security": sum(1 for r in res if r["level"] == "error" and r["band"] is None),
        "security_high_or_higher": sum(1 for r in res if r["band"] in ("high", "critical")),
        "per_rule": {k: {**{x: y for x, y in v.items() if x != "lanes"}, "lanes": dict(v["lanes"])}
                     for k, v in sorted(per_rule.items(), key=lambda kv: (-kv[1]["count"], kv[0]))},
    }


def ident(r):
    return (r["rule"], r["uri"], r["line"], r["column"])


def compare(local, live):
    local_ids = collections.Counter(ident(r) for r in local["results"])
    live_ids = collections.Counter(ident(r) for r in live["results"])
    return {
        "live_versions": live["versions"],
        "live_results": len(live["results"]), "local_results": sum(local_ids.values()),
        "live_rules_in_sarif": len(live["rules"]), "local_rules_in_sarif": len(local["rules"]),
        "same_rule_ids": set(live["rules"]) == set(local["rules"]),
        "only_live": sorted(map(list, (live_ids - local_ids).elements())),
        "only_local_count": sum((local_ids - live_ids).values()),
        "identical_rule_path_line_column_multiset": local_ids == live_ids,
    }


def main():
    local_dir, live_dir, out = map(Path, sys.argv[1:4])
    report = {"languages": {}, "parity": {}, "parity_negative_control": {}, "overlap": {}}
    loaded = {}
    for lang, category in LANGS.items():
        report["languages"][category] = {}
        for suite in SUITES:
            data = load(local_dir / f"{lang}-{suite}.sarif")
            loaded[(lang, suite)] = data
            report["languages"][category][suite] = {"versions": data["versions"], **summarize(data)}
        live = load(live_dir / f"{category}.sarif")
        report["parity"][category] = compare(loaded[(lang, "code-scanning")], live)
        if lang == "python":
            # Discriminating control: the same comparator on a mismatched pair
            # (local code-quality SARIF against the live default-suite SARIF).
            report["parity_negative_control"][category] = {
                k: v for k, v in compare(loaded[(lang, "code-quality")], live).items() if k != "only_live"}
        base = collections.Counter(ident(r) for r in loaded[(lang, "code-scanning")]["results"])
        cq = collections.Counter(ident(r) for r in loaded[(lang, "code-quality")]["results"])
        saq = collections.Counter(ident(r) for r in loaded[(lang, "security-and-quality")]["results"])
        ext = collections.Counter(ident(r) for r in loaded[(lang, "security-extended")]["results"])
        added_by_ext = [r for r in loaded[(lang, "security-extended")]["results"] if ident(r) not in base]
        report["overlap"][category + ":extended"] = {
            "extended_results_not_in_default": sum((ext - base).values()),
            "default_results_not_in_extended": sum((base - ext).values()),
            "extended_results_not_in_security_and_quality": sum((ext - saq).values()),
            "added_by_extended_per_rule": dict(collections.Counter(r["rule"] for r in added_by_ext)),
            "added_by_extended_bands": dict(collections.Counter(r["band"] for r in added_by_ext)),
            "added_by_extended_lanes": dict(collections.Counter(r["lane"] for r in added_by_ext)),
        }
        report["overlap"][category] = {
            "results_multiset": {"default": sum(base.values()), "code_quality": sum(cq.values()),
                                 "security_and_quality": sum(saq.values())},
            "distinct_rule_path_line_column": {"default": len(base), "code_quality": len(cq),
                                               "security_and_quality": len(saq)},
            "distinct_rule_path_line": {
                "code_quality": len({k[:3] for k in cq}), "security_and_quality": len({k[:3] for k in saq})},
            "code_quality_results_also_in_default": sum((cq & base).values()),
            "code_quality_results_not_in_security_and_quality": sum((cq - saq).values()),
            "default_results_not_in_security_and_quality": sum((base - saq).values()),
            "security_and_quality_results_in_neither_default_nor_code_quality": sum((saq - cq - base).values()),
            "code_quality_rules_absent_from_security_and_quality_suite": sorted(
                set(loaded[(lang, "code-quality")]["rules"]) - set(loaded[(lang, "security-and-quality")]["rules"])),
            "rules_in_suite": {s: len(loaded[(lang, s)]["rules"]) for s in SUITES},
        }
    Path(out).write_text(json.dumps(report, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    for category, suites in report["languages"].items():
        for suite, s in suites.items():
            print(f"{category:22s} {suite:21s} results={s['results']:4d} rules={s['rules_in_sarif']:3d} "
                  f"fired={s['rules_with_results']:3d} levels={s['by_level']} lanes={s['by_lane']} "
                  f"err_nonsec={s['error_level_non_security']} sec_high+={s['security_high_or_higher']}")
    for name in ("parity", "parity_negative_control"):
        for category, p in report[name].items():
            print(f"{name} {category}: live={p['live_results']} local={p['local_results']} "
                  f"rules live/local={p['live_rules_in_sarif']}/{p['local_rules_in_sarif']} "
                  f"same_rule_ids={p['same_rule_ids']} "
                  f"identical={p['identical_rule_path_line_column_multiset']} only_local={p['only_local_count']}")
    for category, o in report["overlap"].items():
        print(f"overlap {category}: {json.dumps(o)}")


if __name__ == "__main__":
    main()
