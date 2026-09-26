#!/usr/bin/env python3
"""Convert a landscape-sweep Workflow run into the retained evidence the repository's tools read (no network).

  convert.py --workflow-output RUN.json --out DIR [--work-dir W] [--scope W/scope.json] [--lane NAME]
             [--usage child-usage-<run>.json] [--limit TEXT ...]

RUN.json is the run record Claude Code keeps for the run (<session>/workflows/<run id>.json; its "result" is the
sweep's return) or the bare return. The lane defaults to the return's `sweep`. Writes into DIR:
  returns.json   discovery/<layer> {catalog, layer_id, proposed[], requirement_sha256, platform_profiles_sha256,
                 families, families_returned}; votes/<layer>/<i>/{facts|fit} {role, repository, refuted, ...};
                 raw/<layer>/<round> (both families' discovery returns, dropped proposals, GPT-6 job metadata);
                 skills_usage; gpt6_usage
  lanes.json     {lanes: [{lane, result: {layers, calls, limits}, proposals}], critic, lost} for build_manifest.py
  layers.json    ledger layer entries whose refs start with @RETURNS@ (make_result.py puts in the returns path)
  survivors.json [{layer_id, repository}] for source_reviews.py
Survival: the facts refuter AND the Claude fit refuter AND the GPT-6 fit refuter did not refute (the fit vote is
two-family: refuted when either family refutes). A missing vote counts as refuted and is noted. A layer none of whose
rounds returned is left out of layers.json (excluded_layers in the summary) rather than recorded as a clean layer
with no proposals; a round in which one family's discovery did not return is listed as degraded_discovery.
Models: vote objects name the resolved Claude models from --usage (child-usage.mjs output); without it they name the
requested aliases. The GPT-6 model is the one its job reported (default gpt-6-astra).
Privacy: work-dir, checkout and home paths become <work-dir>, <repo> and ~. Any string still matching
scripts/validate.py PRIVATE_CONTENT is listed by pointer and kind (never its text), and the exit code is 3.
Integrity: with --work-dir, every GPT-6 output the workflow received through its wrapper agent is compared with the
file Codex wrote (gpt6/<job>/last.json). A mismatch is recorded under raw and makes the exit code 4.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sweep_common import (REPO_ROOT, canon, host_replacements, load_json, private_content,  # noqa: E402
                          private_findings, sanitize, slug, write_json)

ALIASES = {"discover": "opus", "refute-facts": "sonnet", "refute-fit": "opus", "critic": "opus"}
GPT6_DEFAULT = {"model": "gpt-6-astra", "effort": "max"}
MERGE_CAP = 8        # sweep.js MAX_PROPOSALS
FOLLOWUP_CAP = 8     # sweep.js MAX_FOLLOWUPS
FIT_RULE = "two-family: refuted when either the Claude or the GPT-6 fit refuter refuted"
EXIT_PRIVATE, EXIT_MISMATCH = 3, 4


def method_limits(models: dict) -> list[str]:
    return [
        f"Discovery per layer: a Claude researcher ({models['discover']}, effort max) and a GPT-6 researcher "
        f"({GPT6_DEFAULT['model']} through the Codex CLI, effort max, web search, read-only sandbox, user config "
        "ignored), each proposing at most 6 repositories within 12 web searches, 8 page fetches and 40 GitHub API "
        f"calls; the two returns are merged by canonical repository and capped at {MERGE_CAP} per layer (two-family "
        "proposals first; dropped proposals are logged and kept under raw).",
        f"Adversarial verification per layer: a facts/identity refuter ({models['refute-facts']}, effort max) and "
        f"two fit/standing refuters ({models['refute-fit']} and {GPT6_DEFAULT['model']}, effort max), each defaulting "
        "to refuted, within 8 web searches, 10 page fetches and 30 GitHub API calls; a candidate survives only when "
        "no refuter refutes it, and a missing vote counts as refuted.",
        f"One completeness critic ({models['critic']}, effort max) and one bounded follow-up round over at most "
        f"{FOLLOWUP_CAP} critic-flagged layers, with the same roles.",
        "Source review and GitHub metadata only: no candidate was installed, run, benchmarked or compared with a "
        "winner; survival means the proposal withstood fact and fit checks, not that it beats a winner.",
    ]


def load_run(path: Path):
    doc = load_json(path)
    result = doc.get("result", doc) if isinstance(doc, dict) else doc
    if isinstance(result, str):
        result = json.loads(result)
    if not isinstance(result, dict) or not isinstance(result.get("first"), list):
        raise ValueError(f"{path} holds no sweep return (expected result.first)")
    meta = {key: doc.get(key) for key in ("runId", "status", "durationMs", "agentCount", "totalTokens")
            if isinstance(doc, dict) and key in doc}
    return result, meta


def resolved_models(usage: dict | None) -> dict:
    """Role prefix -> resolved Claude model(s) from child-usage output; the requested alias without it."""
    children = ((usage or {}).get("child_usage") or {}).get("children") or []
    out = {}
    for prefix, alias in ALIASES.items():
        found = sorted({model for child in children if isinstance(child, dict)
                        for model in (child.get("resolved_models") or [])
                        if child.get("label") == prefix or str(child.get("label", "")).startswith(prefix + ":")})
        out[prefix] = "+".join(found) if found else alias
    return out


def votes_by_slug(vote_doc) -> dict:
    return {slug(vote.get("repository")): vote for vote in ((vote_doc or {}).get("votes") or [])
            if isinstance(vote, dict)}


def gpt6_out(entry):
    return (entry or {}).get("output") if (entry or {}).get("status") == "ok" else None


def gpt6_meta(entry, keys=("status", "output", "usage", "started", "finished")) -> dict:
    entry = entry or {}
    meta = {key: entry.get(key) for key in keys}
    meta.update({key: entry[key] for key in ("model", "effort", "codex_version", "limit") if key in entry})
    return meta


def copy_check(work: Path | None, job: str, entry) -> str | None:
    """Did the wrapper agent hand the workflow exactly what Codex wrote? None when there is no job to check."""
    if work is None or entry is None:
        return None
    path = work / "gpt6" / job / "last.json"
    received = gpt6_out(entry)
    if not path.is_file():
        return "no_file" if received is not None else None
    try:
        written = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return "file_unparseable"
    if received is None:
        return "file_only"  # Codex finished, but the workflow never used this output
    return "match" if written == received else "mismatch"


def convert(res: dict, scope: dict, lane: str, models: dict, work: Path | None = None, limits=(),
            workflow_run: str | None = None) -> dict:
    returns = {"sweep_id": lane, "discovery": {}, "votes": {}, "raw": {}}
    if workflow_run:
        returns["workflow_run"] = workflow_run
    lane_layers, proposals, ledger_layers, survivors, lost = [], [], [], [], []
    calls_total, skills_usage, gpt6_usage, checks = {}, {}, {"jobs": 0, "by_status": {}, "usage": {}}, {}
    rounds_by_layer = {}
    for entry in (res.get("first") or []) + (res.get("followups") or []):
        if entry:
            rounds_by_layer.setdefault(entry["layer_id"], []).append(entry)

    excluded, degraded = [], []
    for layer_id, rounds in rounds_by_layer.items():
        catalog = rounds[0]["catalog"]
        key = f"{catalog}/{layer_id}"
        for r in rounds:
            if r.get("lost"):
                lost.append(f"{layer_id}:{r.get('round')}")
        if all(r.get("lost") for r in rounds):
            # No round returned: nothing of this layer was retained, so it must not become a clean
            # `votes: retained` layer with an empty proposal list.
            excluded.append(layer_id)
            continue
        merged, facts_v, fitc_v, fitg_v, calls, raw, returned = [], {}, {}, {}, {}, {}, {}
        for r in rounds:
            if r.get("lost"):
                continue
            rnd = r.get("round", "first")
            suffix = "-followup" if rnd == "followup" else ""
            cd, gd, fg = r.get("claude_discover"), r.get("gpt6_discover"), r.get("fit_gpt6")
            returned[rnd] = [family for family, value in (("claude", cd), ("gpt6", gpt6_out(gd))) if value is not None]
            if len(returned[rnd]) < 2:
                degraded.append(f"{layer_id}:{rnd}")
            raw[rnd] = {"claude_discover": cd, "gpt6_discover": gpt6_meta(gd), "dropped": r.get("dropped"),
                        "fit_gpt6_meta": gpt6_meta(fg, ("status", "usage", "started", "finished")),
                        "followup_reason": r.get("followup_reason")}
            check = {name: copy_check(work, f"gpt6-{name}-{layer_id}{suffix}", entry)
                     for name, entry in (("discover", gd), ("fit", fg))}
            check = {name: value for name, value in check.items() if value is not None}
            if check:
                raw[rnd]["gpt6_copy_check"] = check
                for value in check.values():
                    checks[value] = checks.get(value, 0) + 1
            for entry in (gd, fg):
                if entry is None:
                    continue
                gpt6_usage["jobs"] += 1
                status = str(entry.get("status"))
                gpt6_usage["by_status"][status] = gpt6_usage["by_status"].get(status, 0) + 1
                for counter, value in (entry.get("usage") or {}).items():
                    if isinstance(value, int) and not isinstance(value, bool):
                        gpt6_usage["usage"][counter] = gpt6_usage["usage"].get(counter, 0) + value
            for name, value in ((cd or {}).get("calls") or {}).items():
                calls[name] = calls.get(name, 0) + int(value)
            for name, value in ((gpt6_out(gd) or {}).get("calls") or {}).items():
                calls[f"gpt6_{name}"] = calls.get(f"gpt6_{name}", 0) + int(value)
            seen = {slug(p["repository"]) for p in merged}
            for p in r.get("merged") or []:
                if slug(p["repository"]) not in seen:
                    merged.append(p)
                    seen.add(slug(p["repository"]))
            for role_key, obj in (("discover_claude", cd), ("discover_gpt6", gpt6_out(gd)), ("facts", r.get("facts")),
                                  ("fit_claude", r.get("fit_claude")), ("fit_gpt6", gpt6_out(fg))):
                for skill in ((obj or {}).get("skills_used") or []):
                    skills_usage.setdefault(role_key, {}).setdefault(skill, 0)
                    skills_usage[role_key][skill] += 1
            # A later round's vote on the same repository replaces an earlier one, with that round's skills and,
            # for the GPT-6 vote, the model its job reported.
            for store, obj, job_meta in ((facts_v, r.get("facts"), None), (fitc_v, r.get("fit_claude"), None),
                                         (fitg_v, gpt6_out(fg), gpt6_meta(fg, ("status",)))):
                skills = list(((obj or {}).get("skills_used")) or [])
                for repo_slug, vote in votes_by_slug(obj).items():
                    store[repo_slug] = (vote, skills, job_meta)
        for name, value in calls.items():
            calls_total[name] = calls_total.get(name, 0) + value
        proposed = [canon(p["repository"]) for p in merged]
        returns["discovery"][layer_id] = {"catalog": catalog, "layer_id": layer_id, "proposed": proposed,
                                          "requirement_sha256": scope["requirement_sha256"][key],
                                          "platform_profiles_sha256": scope["platform_profiles_sha256"],
                                          "families": {canon(p["repository"]): p.get("families") for p in merged},
                                          "families_returned": returned}
        returns["raw"][layer_id] = raw
        returns["votes"][layer_id] = []
        survived, refuted, new_candidates = [], [], []
        for index, p in enumerate(merged):
            repo_slug, repository = slug(p["repository"]), canon(p["repository"])
            fv, fskills, _ = facts_v.get(repo_slug, (None, [], None))
            cv, cskills, _ = fitc_v.get(repo_slug, (None, [], None))
            gv, gskills, gmeta = fitg_v.get(repo_slug, (None, [], None))
            notes = []
            if fv is None:
                notes.append("facts vote missing (counted as refuted)")
            if cv is None:
                notes.append("Claude fit vote missing (counted as refuted)")
            if gv is None:
                notes.append("GPT-6 fit vote missing (counted as refuted)")
            facts_refuted = bool(fv is None or fv.get("refuted"))
            fit_refuted = bool(cv is None or cv.get("refuted") or gv is None or gv.get("refuted"))
            gpt6_model = (gmeta or {}).get("model") or GPT6_DEFAULT["model"]
            gpt6_effort = (gmeta or {}).get("effort") or GPT6_DEFAULT["effort"]
            vote_fields = ("refuted", "confidence", "reasoning", "refs")
            facts_obj = {"role": "facts", "repository": repository, "refuted": facts_refuted, "family": "anthropic",
                         "model": models["refute-facts"], "effort": "max", "confidence": (fv or {}).get("confidence"),
                         "reasoning": (fv or {}).get("reasoning"), "refs": (fv or {}).get("refs", []),
                         "skills_used": fskills}
            fit_obj = {"role": "fit", "repository": repository, "refuted": fit_refuted, "rule": FIT_RULE,
                       "claude": {"model": models["refute-fit"], "effort": "max",
                                  **({k: cv.get(k) for k in vote_fields} if cv else {"missing": True}),
                                  "skills_used": cskills},
                       "gpt6": {"model": gpt6_model, "effort": gpt6_effort,
                                **({k: gv.get(k) for k in vote_fields} if gv else {"missing": True}),
                                "skills_used": gskills}}
            if notes:
                facts_obj["notes"] = notes
                fit_obj["notes"] = notes
            returns["votes"][layer_id].append({"facts": facts_obj, "fit": fit_obj})
            ref = f"votes/{layer_id}/{index}"
            entry = {"repo": repository,
                     "facts": {"vote": "refuted" if facts_refuted else "not_refuted", "ref": f"@RETURNS@#/{ref}/facts"},
                     "fit": {"vote": "refuted" if fit_refuted else "not_refuted", "ref": f"@RETURNS@#/{ref}/fit"}}
            survives = not facts_refuted and not fit_refuted
            (survived if survives else refuted).append(entry)
            if survives:
                survivors.append({"layer_id": layer_id, "repository": repository})
            new_candidates.append({"repository": repository, "source": f"{lane}: {p.get('source', '')}"[:600],
                                   "demonstrated_gap": p.get("demonstrated_gap"), "proposed_label": p.get("proposed_label"),
                                   "comparison_that_would_overturn": p.get("comparison_that_would_overturn"),
                                   "evidence": p.get("evidence", []), "upstream_now": p.get("upstream_now")})
            proposals.append({"layer": layer_id, "repository": repository, "kind": "new_candidate", "survives": survives,
                              "votes": [
                                  {"refuted": facts_refuted, "confidence": (fv or {}).get("confidence"),
                                   "reasoning": f"facts ({models['refute-facts']}): " + ((fv or {}).get("reasoning") or "missing")},
                                  {"refuted": bool(cv is None or cv.get("refuted")), "confidence": (cv or {}).get("confidence"),
                                   "reasoning": f"fit ({models['refute-fit']}): " + ((cv or {}).get("reasoning") or "missing")},
                                  {"refuted": bool(gv is None or gv.get("refuted")), "confidence": (gv or {}).get("confidence"),
                                   "reasoning": f"fit ({gpt6_model}): " + ((gv or {}).get("reasoning") or "missing")}]})
        lane_layers.append({"layer_id": layer_id, "selected": [], "alternatives_keep_but_compare": [],
                            "new_candidates": new_candidates})
        ledger_layers.append({"catalog": catalog, "layer_id": layer_id, "votes": "retained",
                              "discovery_ref": f"@RETURNS@#/discovery/{layer_id}", "calls": calls or None,
                              "proposed": proposed, "survived": survived, "refuted": refuted, "reopen": []})
    returns["skills_usage"] = skills_usage
    returns["gpt6_usage"] = gpt6_usage
    lanes = {"lanes": [{"lane": lane, "result": {"layers": lane_layers, "calls": calls_total,
                                                 "limits": [*method_limits(models), *limits]},
                        "proposals": proposals}],
             "critic": res.get("critic"), "lost": lost}
    return {"returns": returns, "lanes": lanes, "layers": ledger_layers, "survivors": survivors,
            "summary": {"lane": lane, "layers": len(ledger_layers), "proposals": len(proposals),
                        "survivors": len(survivors), "lost": lost, "excluded_layers": excluded,
                        "degraded_discovery": degraded, "calls": calls_total,
                        "skills_usage": skills_usage, "gpt6_jobs": gpt6_usage["jobs"],
                        "gpt6_by_status": gpt6_usage["by_status"], "gpt6_copy_check": checks}}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workflow-output", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--work-dir", default=os.environ.get("SWEEP_WORK_DIR"))
    parser.add_argument("--scope", type=Path, help="default <work-dir>/scope.json")
    parser.add_argument("--lane", help="default: the return's sweep")
    parser.add_argument("--usage", type=Path, help="usage_record.py output for this run")
    parser.add_argument("--limit", action="append", default=[], help="a run-specific lane limit (repeatable)")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    try:
        work = Path(args.work_dir).expanduser().resolve() if args.work_dir else None
        if args.scope is None and work is None:
            raise ValueError("pass --work-dir (for scope.json and the GPT-6 copy check) or --scope")
        scope = load_json(args.scope or work / "scope.json")
        res, meta = load_run(args.workflow_output)
        lane = args.lane or res.get("sweep")
        if not lane:
            raise ValueError("the return names no sweep; pass --lane")
        models = resolved_models(load_json(args.usage) if args.usage else None)
        out = convert(res, scope, lane, models, work, args.limit, meta.get("runId"))
        patterns = private_content(args.repo_root)
    except (ValueError, OSError, KeyError) as error:
        print(f"convert.py: {error}", file=sys.stderr)
        return 2
    replacements = host_replacements(work, args.repo_root.resolve())
    args.out.mkdir(parents=True, exist_ok=True)
    findings = []
    for name in ("returns", "lanes", "layers", "survivors"):
        document = sanitize(out[name], replacements)
        write_json(args.out / f"{name}.json", document)
        findings.extend((f"{name}.json#{pointer}", kind) for pointer, kind in private_findings(document, patterns))
    summary = {**out["summary"], "run": meta}
    if meta.get("status") not in (None, "completed"):
        summary["warning"] = f"the run record's status is {meta.get('status')!r}, not completed"
    print(json.dumps(summary, indent=1))
    if findings:
        print("possible private content (redact before registering; text not shown):", file=sys.stderr)
        for pointer, kind in findings:
            print(f"  {pointer}: {kind}", file=sys.stderr)
        return EXIT_PRIVATE
    if out["summary"]["gpt6_copy_check"].get("mismatch"):
        print("a wrapper agent's copy of a GPT-6 output differs from the file Codex wrote; see raw/*/*/gpt6_copy_check",
              file=sys.stderr)
        return EXIT_MISMATCH
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
