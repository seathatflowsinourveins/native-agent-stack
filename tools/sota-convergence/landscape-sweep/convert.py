#!/usr/bin/env python3
"""Convert a landscape-sweep Workflow run into the retained evidence the repository's tools read (no network).

  convert.py --workflow-output RUN.json --out DIR [--work-dir W] [--scope W/scope.json] [--lane NAME]
             [--usage child-usage-<run>.json] [--limit TEXT ...]

RUN.json is the run record Claude Code keeps for the run (<session>/workflows/<run id>.json; its "result" is the
sweep's return) or the bare return. The lane defaults to the return's `sweep`. Writes into DIR:
  returns.json   discovery/<layer> {catalog, layer_id, proposed[], requirement_sha256, platform_profiles_sha256,
                 families, families_returned}; votes/<layer>/<i>/{facts|fit} {role, repository, refuted, round, ...};
                 raw/<layer>/<round> (both families' discovery returns, dropped proposals, GPT-6 job metadata, or
                 {lost: true}); failures/<layer> (the layer's retained failures); skills_usage; gpt6_usage
  lanes.json     {lanes: [{lane, result: {layers, calls, limits}, proposals}], critic, lost} for build_manifest.py
  layers.json    ledger layer entries whose refs start with @RETURNS@ (make_result.py puts in the returns path)
  survivors.json [{layer_id, repository}] for source_reviews.py
Survival: the facts refuter AND the Claude fit refuter AND the GPT-6 fit refuter did not refute (the fit vote is
two-family: refuted when either family refutes). A vote refutes unless it says refuted: false, so a missing or
malformed vote counts as refuted and is noted. When a later round proposes a repository again, that round's proposal
and all three of its votes replace the earlier round's; a vote missing from that round is never taken from an
earlier one.
Retained failures: a round that returned nothing, a discovery family that did not return, a missing vote, a lost
completeness critic, a critic-flagged layer beyond the follow-up cap, and a GPT-6 copy problem are listed under
failures/<layer>, and the layer gets the reopen entry {trigger: retained_failure, ref: @RETURNS@#/failures/<layer>},
so it never counts as a clean layer. A layer none of whose rounds returned is left out of layers.json
(excluded_layers in the summary).
Models and effort: each Claude vote names the resolved model and the effort its own worker ran at, from --usage
(child-usage.mjs output); without it, the requested alias and effort null (not measured). The GPT-6 vote names the
model and effort its job reported.
Privacy: work-dir, checkout and home paths become <work-dir>, <repo> and ~. Any string still matching
scripts/validate.py PRIVATE_CONTENT is listed by pointer and kind (never its text), and the exit code is 3.
Integrity: with --work-dir, every GPT-6 output is compared with the file Codex wrote (gpt6/<job>/last.json). Exit 4
when the workflow used an output that differs from that file (mismatch), that Codex never wrote (no_file) or that
Codex wrote as non-JSON (file_unparseable), or when a job that finished with exit 0 wrote an output that never
reached the workflow (file_only). Each is also a retained failure of its layer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sweep_common import (REPO_ROOT, canon, host_replacements, load_json, pointer_token,  # noqa: E402
                          private_content, private_findings, sanitize, slug, write_json)

ALIASES = {"discover": "opus", "refute-facts": "sonnet", "refute-fit": "opus", "critic": "opus"}
GPT6_DEFAULT = {"model": "gpt-6-astra", "effort": "max"}
MERGE_CAP = 8        # sweep.js MAX_PROPOSALS
FOLLOWUP_CAP = 8     # sweep.js MAX_FOLLOWUPS
FIT_RULE = "two-family: refuted when either the Claude or the GPT-6 fit refuter refuted"
EXIT_PRIVATE, EXIT_COPY = 3, 4
# Copy checks that mean the workflow's GPT-6 input is not exactly what Codex wrote (exit 4, and a retained failure).
COPY_FAILURES = ("mismatch", "no_file", "file_unparseable", "file_only")
VOTE_ROLES = (("facts", "facts"), ("fit_claude", "Claude fit"), ("fit_gpt6", "GPT-6 fit"))


def method_limits(models: dict, gpt6_model: str = GPT6_DEFAULT["model"]) -> list[str]:
    return [
        f"Discovery per layer: a Claude researcher ({models['discover']}, effort max) and a GPT-6 researcher "
        f"({gpt6_model} through the Codex CLI, effort max, web search, read-only sandbox, user config "
        "ignored), each proposing at most 6 repositories within 12 web searches, 8 page fetches and 40 GitHub API "
        f"calls; the two returns are merged by canonical repository and capped at {MERGE_CAP} per layer (two-family "
        "proposals first; dropped proposals are logged and kept under raw).",
        f"Adversarial verification per layer: a facts/identity refuter ({models['refute-facts']}, effort max) and "
        f"two fit/standing refuters ({models['refute-fit']} and {gpt6_model}, effort max), each defaulting "
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


def as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def resolved_models(usage: dict | None) -> dict:
    """Role prefix -> resolved Claude model(s) from child-usage output; the requested alias without it."""
    children = as_dict(as_dict(usage).get("child_usage")).get("children") or []
    out = {}
    for prefix, alias in ALIASES.items():
        found = sorted({model for child in children if isinstance(child, dict)
                        for model in (child.get("resolved_models") or [])
                        if child.get("label") == prefix or str(child.get("label", "")).startswith(prefix + ":")})
        out[prefix] = "+".join(found) if found else alias
    return out


def usage_children(usage: dict | None) -> dict:
    """Child label -> child of the child-usage output (the first child when a label repeats)."""
    out = {}
    for child in as_dict(as_dict(usage).get("child_usage")).get("children") or []:
        if isinstance(child, dict) and isinstance(child.get("label"), str):
            out.setdefault(child["label"], child)
    return out


def measured(children: dict, label: str, fallback_model: str) -> tuple[str, str | None]:
    """(model, effort) of the Claude worker `label` as the usage record measured them; the role's model and effort
    None (not measured) when the record has no such child."""
    child = as_dict(children.get(label))
    models = sorted({m for m in child.get("resolved_models") or [] if isinstance(m, str) and m})
    efforts = sorted({e for e in child.get("efforts") or [] if isinstance(e, str) and e})
    return ("+".join(models) if models else fallback_model), ("+".join(efforts) if efforts else None)


def is_refuted(vote) -> bool:
    """A vote refutes unless it says refuted: false; a missing or malformed vote refutes, as the refuters default."""
    return not (isinstance(vote, dict) and vote.get("refuted") is False)


def votes_by_slug(vote_doc) -> dict:
    """Repository slug -> its vote; when a refuter voted twice on one repository, a refuting vote wins."""
    out = {}
    for vote in as_dict(vote_doc).get("votes") or []:
        if not isinstance(vote, dict):
            continue
        key = slug(vote.get("repository"))
        if key and (key not in out or (is_refuted(vote) and not is_refuted(out[key]))):
            out[key] = vote
    return out


def gpt6_out(entry):
    entry = as_dict(entry)
    return entry.get("output") if entry.get("status") == "ok" else None


def gpt6_meta(entry, keys=("status", "output", "usage", "started", "finished")) -> dict:
    entry = as_dict(entry)
    meta = {key: entry.get(key) for key in keys}
    meta.update({key: entry[key] for key in ("model", "effort", "codex_version", "limit") if key in entry})
    return meta


def job_exit(directory: Path):
    try:
        return int((directory / "exit").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def copy_check(work: Path | None, job: str, entry) -> str | None:
    """Did the workflow receive exactly what Codex wrote (gpt6/<job>/last.json)? None when there is nothing to
    compare: no work dir, no job, or a job that failed and whose output the workflow rightly did not use."""
    if work is None or entry is None:
        return None
    directory = work / "gpt6" / job
    received = gpt6_out(entry)
    if not (directory / "last.json").is_file():
        return "no_file" if received is not None else None
    try:
        written = json.loads((directory / "last.json").read_text(encoding="utf-8"))
    except ValueError:
        return "file_unparseable" if received is not None else None
    if received is None:
        return "file_only" if job_exit(directory) == 0 else None
    return "match" if written == received else "mismatch"


def planned_followups(critic, layer_ids) -> list:
    """The critic's follow-up requests as sweep.js plans them: layers of this sweep, the first request per layer, in
    the critic's order. The first FOLLOWUP_CAP of them get a follow-up round."""
    seen, known = set(), []
    for item in as_dict(critic).get("followup_layers") or []:
        layer_id = as_dict(item).get("layer_id")
        if layer_id in layer_ids and layer_id not in seen:
            seen.add(layer_id)
            known.append(item)
    return known


def sweep_rounds(res: dict) -> list:
    """Every round of the return. With a critic (a full run), the follow-up rounds must be exactly the critic's
    planned requests, in order, so none can go missing; one returned as null (by a sweep.js from before lost
    follow-ups were recorded) becomes {lost: true} for the layer the plan gives it. Without a critic, a null
    follow-up cannot be attributed and is an error, never dropped."""
    first = list(res.get("first") or [])
    for index, entry in enumerate(first):
        if not (isinstance(entry, dict) and entry.get("layer_id") and entry.get("catalog")):
            raise ValueError(f"first-round entry {index} is not a round (sweep.js records a lost round as "
                             "{layer_id, catalog, lost: true})")
    catalogs = {entry["layer_id"]: entry["catalog"] for entry in first}
    followups = list(res.get("followups") or [])
    if "critic" in res:
        plan = planned_followups(res.get("critic"), catalogs)[:FOLLOWUP_CAP]
        if len(plan) != len(followups) or any(isinstance(entry, dict) and entry.get("layer_id") != request["layer_id"]
                                              for entry, request in zip(followups, plan)):
            raise ValueError("the follow-up rounds do not match the critic's requests (sweep.js runs one round per "
                             f"flagged layer of this sweep, in the critic's order, at most {FOLLOWUP_CAP})")
        followups = [entry if isinstance(entry, dict) else
                     {"layer_id": request["layer_id"], "catalog": catalogs[request["layer_id"]], "round": "followup",
                      "lost": True, "followup_reason": {"reason": request.get("reason"),
                                                        "search_directions": request.get("search_directions")}}
                     for entry, request in zip(followups, plan)]
    elif not all(isinstance(entry, dict) for entry in followups):
        raise ValueError("a follow-up round returned nothing and the return has no critic to say which layer it was")
    for index, entry in enumerate(followups):
        if not (entry.get("layer_id") and entry.get("catalog")):
            raise ValueError(f"follow-up entry {index} names no layer_id and catalog")
    return first + followups


def convert(res: dict, scope: dict, lane: str, models: dict, work: Path | None = None, limits=(),
            workflow_run: str | None = None, usage: dict | None = None) -> dict:
    returns = {"sweep_id": lane, "discovery": {}, "votes": {}, "raw": {}, "failures": {}}
    if workflow_run:
        returns["workflow_run"] = workflow_run
    children = usage_children(usage)
    lane_layers, proposals, ledger_layers, survivors, lost = [], [], [], [], []
    calls_total, skills_usage, gpt6_usage, checks = {}, {}, {"jobs": 0, "by_status": {}, "usage": {}}, {}
    gpt6_models = set()
    rounds_by_layer = {}
    for entry in sweep_rounds(res):
        rounds_by_layer.setdefault(entry["layer_id"], []).append(entry)
    # The completeness step: a full run returns `critic` (a smoke run has no critic key).
    critic_lost = "critic" in res and not isinstance(res.get("critic"), dict)
    beyond_cap = {as_dict(item).get("layer_id"): item for item in
                  planned_followups(res.get("critic"), rounds_by_layer)[FOLLOWUP_CAP:]}

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
        failures = []
        # Repository slug -> the latest round that proposed it: that round's proposal row with that round's votes.
        final, order = {}, []
        calls, raw, returned = {}, {}, {}
        for r in rounds:
            rnd = r.get("round", "first")
            if r.get("lost"):
                raw[rnd] = {"lost": True, "followup_reason": r.get("followup_reason")}
                failures.append({"round": rnd, "cause": "round_lost",
                                 "detail": "the round returned nothing, so its discovery and votes are missing"})
                continue
            suffix = "-followup" if rnd == "followup" else ""
            cd, gd, fg = r.get("claude_discover"), r.get("gpt6_discover"), r.get("fit_gpt6")
            returned[rnd] = [family for family, value in (("claude", cd), ("gpt6", gpt6_out(gd))) if value is not None]
            if len(returned[rnd]) < 2:
                degraded.append(f"{layer_id}:{rnd}")
                for family in ("claude", "gpt6"):
                    if family not in returned[rnd]:
                        failures.append({"round": rnd, "cause": "discovery_missing", "family": family,
                                         "status": as_dict(gd).get("status") if family == "gpt6" else None,
                                         "detail": f"the {family} discovery researcher returned nothing usable"})
            raw[rnd] = {"claude_discover": cd, "gpt6_discover": gpt6_meta(gd), "dropped": r.get("dropped"),
                        "fit_gpt6_meta": gpt6_meta(fg, ("status", "usage", "started", "finished")),
                        "followup_reason": r.get("followup_reason")}
            check = {name: copy_check(work, f"gpt6-{name}-{layer_id}{suffix}", entry)
                     for name, entry in (("discover", gd), ("fit", fg))}
            check = {name: value for name, value in check.items() if value is not None}
            if check:
                raw[rnd]["gpt6_copy_check"] = check
                for name, value in check.items():
                    checks[value] = checks.get(value, 0) + 1
                    if value in COPY_FAILURES:
                        failures.append({"round": rnd, "cause": "gpt6_copy", "job": f"gpt6-{name}-{layer_id}{suffix}",
                                         "check": value})
            for entry in (gd, fg):
                if not isinstance(entry, dict):
                    continue
                gpt6_usage["jobs"] += 1
                status = str(entry.get("status"))
                gpt6_usage["by_status"][status] = gpt6_usage["by_status"].get(status, 0) + 1
                if entry.get("model"):
                    gpt6_models.add(str(entry["model"]))
                for counter, value in as_dict(entry.get("usage")).items():
                    if isinstance(value, int) and not isinstance(value, bool):
                        gpt6_usage["usage"][counter] = gpt6_usage["usage"].get(counter, 0) + value
            for name, value in as_dict(as_dict(cd).get("calls")).items():
                calls[name] = calls.get(name, 0) + int(value)
            for name, value in as_dict(as_dict(gpt6_out(gd)).get("calls")).items():
                calls[f"gpt6_{name}"] = calls.get(f"gpt6_{name}", 0) + int(value)
            round_votes = {"facts": r.get("facts"), "fit_claude": r.get("fit_claude"), "fit_gpt6": gpt6_out(fg)}
            for role_key, obj in (("discover_claude", cd), ("discover_gpt6", gpt6_out(gd)), *round_votes.items()):
                for skill in as_dict(obj).get("skills_used") or []:
                    skills_usage.setdefault(role_key, {}).setdefault(skill, 0)
                    skills_usage[role_key][skill] += 1
            by_role = {role: votes_by_slug(obj) for role, obj in round_votes.items()}
            skills = {role: list(as_dict(obj).get("skills_used") or []) for role, obj in round_votes.items()}
            for p in r.get("merged") or []:
                repo_slug = slug(as_dict(p).get("repository"))
                if not repo_slug:
                    continue
                if repo_slug not in final:
                    order.append(repo_slug)
                final[repo_slug] = {"round": rnd, "proposal": p, "skills": skills,
                                    "gpt6_job": gpt6_meta(fg, ("status",)),
                                    **{role: by_role[role].get(repo_slug) for role in round_votes}}
        if critic_lost:
            failures.append({"round": "critic", "cause": "critic_lost",
                             "detail": "the completeness critic returned nothing, so no layer's completeness was "
                                       "checked and no follow-up round could be requested"})
        if layer_id in beyond_cap:
            failures.append({"round": "critic", "cause": "followup_not_run",
                             "reason": as_dict(beyond_cap[layer_id]).get("reason"),
                             "detail": f"the critic flagged this layer, but only the first {FOLLOWUP_CAP} flagged "
                                       "layers get a follow-up round"})
        for name, value in calls.items():
            calls_total[name] = calls_total.get(name, 0) + value
        merged = [final[repo_slug]["proposal"] for repo_slug in order]
        proposed = [canon(p["repository"]) for p in merged]
        returns["discovery"][layer_id] = {"catalog": catalog, "layer_id": layer_id, "proposed": proposed,
                                          "requirement_sha256": scope["requirement_sha256"][key],
                                          "platform_profiles_sha256": scope["platform_profiles_sha256"],
                                          "families": {canon(p["repository"]): p.get("families") for p in merged},
                                          "families_returned": returned}
        returns["raw"][layer_id] = raw
        returns["votes"][layer_id] = []
        survived, refuted, new_candidates, missing = [], [], [], {}
        for index, repo_slug in enumerate(order):
            row = final[repo_slug]
            rnd, p = row["round"], row["proposal"]
            repository = canon(p["repository"])
            fv, cv, gv = row["facts"], row["fit_claude"], row["fit_gpt6"]
            notes = []
            for role, name in VOTE_ROLES:
                if row[role] is None:
                    notes.append(f"{name} vote missing (counted as refuted)")
                    missing.setdefault((rnd, role), []).append(repository)
            facts_refuted, claude_refuted, gpt6_refuted = is_refuted(fv), is_refuted(cv), is_refuted(gv)
            fit_refuted = claude_refuted or gpt6_refuted
            label_suffix = ":followup" if rnd == "followup" else ""
            facts_model, facts_effort = measured(children, f"refute-facts:{layer_id}{label_suffix}",
                                                 models["refute-facts"])
            fit_model, fit_effort = measured(children, f"refute-fit:{layer_id}{label_suffix}", models["refute-fit"])
            gmeta = row["gpt6_job"]
            gpt6_model = gmeta.get("model") or GPT6_DEFAULT["model"]
            gpt6_effort = gmeta.get("effort") or GPT6_DEFAULT["effort"]
            vote_fields = ("refuted", "confidence", "reasoning", "refs")
            facts_obj = {"role": "facts", "repository": repository, "refuted": facts_refuted, "round": rnd,
                         "family": "anthropic", "model": facts_model, "effort": facts_effort,
                         "confidence": as_dict(fv).get("confidence"), "reasoning": as_dict(fv).get("reasoning"),
                         "refs": as_dict(fv).get("refs", []), "skills_used": row["skills"]["facts"]}
            fit_obj = {"role": "fit", "repository": repository, "refuted": fit_refuted, "round": rnd, "rule": FIT_RULE,
                       "claude": {"model": fit_model, "effort": fit_effort,
                                  **({k: cv.get(k) for k in vote_fields} if cv else {"missing": True}),
                                  "skills_used": row["skills"]["fit_claude"]},
                       "gpt6": {"model": gpt6_model, "effort": gpt6_effort,
                                **({k: gv.get(k) for k in vote_fields} if gv else {"missing": True}),
                                "skills_used": row["skills"]["fit_gpt6"]}}
            if notes:
                facts_obj["notes"] = notes
                fit_obj["notes"] = notes
            returns["votes"][layer_id].append({"facts": facts_obj, "fit": fit_obj})
            ref = f"votes/{pointer_token(layer_id)}/{index}"
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
                                  {"refuted": facts_refuted, "confidence": as_dict(fv).get("confidence"),
                                   "reasoning": f"facts ({facts_model}): " + (as_dict(fv).get("reasoning") or "missing")},
                                  {"refuted": claude_refuted, "confidence": as_dict(cv).get("confidence"),
                                   "reasoning": f"fit ({fit_model}): " + (as_dict(cv).get("reasoning") or "missing")},
                                  {"refuted": gpt6_refuted, "confidence": as_dict(gv).get("confidence"),
                                   "reasoning": f"fit ({gpt6_model}): " + (as_dict(gv).get("reasoning") or "missing")}]})
        for (rnd, role), repositories in missing.items():
            failure = {"round": rnd, "cause": "vote_missing", "role": role, "repositories": repositories,
                       "detail": f"the {dict(VOTE_ROLES)[role]} refuter returned no vote on these proposals; each "
                                 "counts as refuted"}
            if role == "fit_gpt6":
                failure["status"] = as_dict(raw.get(rnd)).get("fit_gpt6_meta", {}).get("status")
            failures.append(failure)
        reopen = []
        if failures:
            returns["failures"][layer_id] = failures
            reopen.append({"trigger": "retained_failure", "ref": f"@RETURNS@#/failures/{pointer_token(layer_id)}"})
        lane_layers.append({"layer_id": layer_id, "selected": [], "alternatives_keep_but_compare": [],
                            "new_candidates": new_candidates})
        ledger_layers.append({"catalog": catalog, "layer_id": layer_id, "votes": "retained",
                              "discovery_ref": f"@RETURNS@#/discovery/{pointer_token(layer_id)}",
                              "calls": calls or None, "proposed": proposed, "survived": survived, "refuted": refuted,
                              "reopen": reopen})
    returns["skills_usage"] = skills_usage
    returns["gpt6_usage"] = gpt6_usage
    gpt6_model_text = "+".join(sorted(gpt6_models)) or GPT6_DEFAULT["model"]
    lanes = {"lanes": [{"lane": lane, "result": {"layers": lane_layers, "calls": calls_total,
                                                 "limits": [*method_limits(models, gpt6_model_text), *limits]},
                        "proposals": proposals}],
             "critic": res.get("critic"), "lost": lost}
    failures_summary = {layer_id: [f"{f['round']}:{f['cause']}" for f in items]
                        for layer_id, items in returns["failures"].items()}
    return {"returns": returns, "lanes": lanes, "layers": ledger_layers, "survivors": survivors,
            "summary": {"lane": lane, "layers": len(ledger_layers), "proposals": len(proposals),
                        "survivors": len(survivors), "lost": lost, "excluded_layers": excluded,
                        "degraded_discovery": degraded, "critic_lost": critic_lost,
                        "retained_failures": failures_summary, "reopened_layers": sorted(failures_summary),
                        "calls": calls_total, "skills_usage": skills_usage, "gpt6_jobs": gpt6_usage["jobs"],
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
        usage = load_json(args.usage) if args.usage else None
        out = convert(res, scope, lane, resolved_models(usage), work, args.limit, meta.get("runId"), usage=usage)
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
    copy_problems = {kind: count for kind, count in out["summary"]["gpt6_copy_check"].items() if kind in COPY_FAILURES}
    if copy_problems:
        print(f"GPT-6 copy check failed {json.dumps(copy_problems, sort_keys=True)}; see raw/<layer>/<round>/"
              "gpt6_copy_check. mismatch: the wrapper's copy differs from Codex's file; no_file: the workflow used an "
              "output Codex never wrote; file_unparseable: Codex's file is not JSON; file_only: a job that finished "
              "with exit 0 wrote an output that never reached the workflow. Each affected layer is reopened "
              "(retained_failure).", file=sys.stderr)
        return EXIT_COPY
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
