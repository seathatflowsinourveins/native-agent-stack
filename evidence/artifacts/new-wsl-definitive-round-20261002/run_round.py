#!/usr/bin/env python3
"""Runner of the clean-room definitive round (decision-rule.txt).

Every evidence-producing model call runs in a clean room, verified by the probes in clean-room.json:
- Claude: ``claude -p --safe-mode --restricted --strict-mcp-config`` from a scratch directory (no CLAUDE.md, hooks,
  plugins, skills, MCP servers or settings files), with only the tools a stage needs;
- GPT: ``codex exec`` with an isolated CODEX_HOME that holds only a provider config for the OmniRoute gateway on
  loopback port 20128 (no AGENTS.md, no MCP servers), read-only sandbox, ephemeral sessions.

Stages (each idempotent; a finished output is never redone):
  clone       shallow clone of every GitHub contender at its latest release tag (else its default-branch head)
  dossiers    one dossier per contender (Claude Sonnet 5.5, effort max), then one verification (Claude Opus 5.5,
              effort max), one repair and re-verification on a failed check
  packets     two orders per unit: unit.json, dossiers/<key>.json, clones/<key> links
  decide      per family, per unit, per order: one decider
  critic      per family, per unit: one critic over both deciders
  adjudicate  per contested slot: one adjudicator per family, in both A/B orders
  status      counts and usage so far

Usage: run_round.py <stage> --work <private run dir> [--jobs N] [--only unit_or_contender ...]
The private run dir holds clones, raw returns and event streams; nothing in it is committed. The assembler
(assemble.py) writes the sanitized record into this folder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AUDIT = ROOT / "evidence/artifacts/upstream-audit-20261002/observations.json"
WRITER_MODEL, JUDGE_MODEL = "claude-sonnet-5-5", "claude-opus-5-5"
GPT_MODEL, GPT_EFFORT = "cx/gpt-6-astra", "max"
GATEWAY = "http://127.0.0.1:20128/v1"
CLAUDE_CLEAN = ["claude", "-p", "--no-session-persistence", "--safe-mode", "--restricted", "--strict-mcp-config",
                "--output-format", "json"]
TIMEOUT = {"dossier": 2700, "verify": 1800, "decide": 3600, "critic": 3600, "adjudicate": 2400}
# Pages for contenders that are not GitHub repositories (distribution images, a model card).
PAGES = {
    "page:ubuntu-26-04-1-lts-canonical-wsl-image": ["https://releases.ubuntu.com/26.04.1/",
                                                    "https://documentation.ubuntu.com/wsl/latest/",
                                                    "https://ubuntu.com/about/release-cycle"],
    "page:ubuntu-24-04-5-lts-canonical-wsl-image": ["https://releases.ubuntu.com/24.04.5/",
                                                    "https://documentation.ubuntu.com/wsl/latest/",
                                                    "https://ubuntu.com/about/release-cycle"],
    "page:debian-13-wsl-distribution": ["https://raw.githubusercontent.com/microsoft/WSL/master/distributions/DistributionInfo.json",
                                        "https://www.debian.org/releases/trixie/", "https://wiki.debian.org/InstallingDebianOn/Microsoft/Windows/SubsystemForLinux"],
    "page:arch-linux-wsl-distribution": ["https://raw.githubusercontent.com/microsoft/WSL/master/distributions/DistributionInfo.json",
                                         "https://wiki.archlinux.org/title/Install_Arch_Linux_on_WSL"],
    "page:fedora-wsl-distribution": ["https://raw.githubusercontent.com/microsoft/WSL/master/distributions/DistributionInfo.json",
                                     "https://docs.fedoraproject.org/en-US/cloud/wsl/", "https://docs.fedoraproject.org/en-US/releases/lifecycle/"],
    "page:nvidia-nemotron-3-embed-1b-bf16-embedding-model": ["https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16"],
}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe(cid: str) -> str:
    return cid.replace("/", "__").replace(":", "_")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def criteria() -> str:
    return (HERE / "criteria.txt").read_text(encoding="utf-8").strip()


def run(cmd: list, cwd: Path, timeout: int, env: dict | None = None, stdout_path: Path | None = None) -> dict:
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=timeout)
        out, err, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        out, err, code = (exc.stdout or ""), f"timeout after {timeout}s", 124
        out = out.decode() if isinstance(out, bytes) else out
    if stdout_path:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text(out, encoding="utf-8")
        stdout_path.with_suffix(".stderr.txt").write_text(err or "", encoding="utf-8")
    return {"exit": code, "seconds": round(time.time() - started, 1), "stdout": out, "stderr": err}


# ---------------------------------------------------------------- Claude and GPT clean rooms

def claude(prompt: str, cwd: Path, model: str, tools: list, schema: dict, timeout: int, raw: Path,
           add_dirs: list | None = None) -> dict:
    cmd = CLAUDE_CLEAN + ["--model", model, "--effort", "max", "--tools", ",".join(tools),
                          "--allowedTools", *tools, "--json-schema", json.dumps(schema)]
    for d in add_dirs or []:
        cmd += ["--add-dir", str(d)]
    cmd.append(prompt)
    result = run(cmd, cwd, timeout, stdout_path=raw)
    parsed, usage = None, None
    try:
        envelope = json.loads(result["stdout"])
        usage = {"usage": envelope.get("usage"), "model_usage": envelope.get("modelUsage"),
                 "num_turns": envelope.get("num_turns"), "duration_ms": envelope.get("duration_ms"),
                 "is_error": envelope.get("is_error")}
        parsed = envelope.get("structured_output")
        if parsed is None and isinstance(envelope.get("result"), str):
            text = envelope["result"].strip()
            start, end = text.find("{"), text.rfind("}")
            parsed = json.loads(text[start:end + 1]) if start >= 0 else None
    except Exception:  # noqa: BLE001 - recorded as a failed attempt
        parsed = None
    return {"exit": result["exit"], "seconds": result["seconds"], "parsed": parsed, "usage": usage,
            "stderr_tail": (result["stderr"] or "")[-400:]}


def gpt_home(work: Path) -> Path:
    home = work / "codex-home"
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.toml").write_text("\n".join([
        f'model = "{GPT_MODEL}"', 'model_provider = "omniroute"', f'model_reasoning_effort = "{GPT_EFFORT}"', "",
        "[features]", "shell_snapshot = false", "standalone_web_search = true", "",
        "[shell_environment_policy.filters]", 'OMNIROUTE_API_KEY = "exclude"', "",
        "[model_providers.omniroute]", 'name = "OmniRoute"', f'base_url = "{GATEWAY}"',
        'env_key = "OMNIROUTE_API_KEY"', "requires_openai_auth = false", 'wire_api = "responses"',
        "supports_standalone_web_search = true", ""]), encoding="utf-8")
    if (home / "AGENTS.md").exists() or (home / "AGENTS.override.md").exists():
        raise SystemExit("the isolated CODEX_HOME must not hold instruction files")
    return home


def gpt(prompt: str, cwd: Path, schema_path: Path, timeout: int, raw: Path, work: Path) -> dict:
    env = dict(os.environ, CODEX_HOME=str(gpt_home(work)), OMNIROUTE_API_KEY="local-loopback")
    last = raw.with_suffix(".last.json")
    cmd = ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only", "-C", str(cwd),
           "-m", GPT_MODEL, "-c", f'model_reasoning_effort="{GPT_EFFORT}"', "-c", 'web_search="live"', "--json",
           "--output-schema", str(schema_path), "-o", str(last), prompt]
    result = run(cmd, cwd, timeout, env=env, stdout_path=raw)
    parsed, usage = None, None
    try:
        parsed = json.loads(last.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        parsed = None
    for line in reversed(result["stdout"].splitlines()):
        if '"turn.completed"' in line:
            try:
                usage = json.loads(line).get("usage")
            except Exception:  # noqa: BLE001
                pass
            break
    return {"exit": result["exit"], "seconds": result["seconds"], "parsed": parsed, "usage": usage,
            "stderr_tail": (result["stderr"] or "")[-400:]}


def attempt(fn, *args, **kwargs) -> dict:
    """At most one retry; every attempt is kept."""
    attempts = []
    for _ in range(2):
        r = fn(*args, **kwargs)
        attempts.append({k: r[k] for k in ("exit", "seconds", "usage", "stderr_tail")})
        if r["exit"] == 0 and isinstance(r["parsed"], dict):
            return {"parsed": r["parsed"], "attempts": attempts}
    return {"parsed": None, "attempts": attempts}


# ---------------------------------------------------------------- stages

def contenders() -> list:
    return load(HERE / "contenders.json")["contenders"]


def units() -> list:
    return load(HERE / "units.json")["units"]


def release_tag(repo: str, audit: dict) -> str | None:
    obs = audit.get(repo.lower()) or {}
    if isinstance(obs.get("release"), dict) and obs["release"].get("tag"):
        return obs["release"]["tag"]
    proc = subprocess.run(["gh", "api", f"repos/{repo}/releases/latest", "--jq", ".tag_name"], capture_output=True,
                          text=True, timeout=60)
    tag = proc.stdout.strip()
    return tag if proc.returncode == 0 and tag else None


def clone_one(c: dict, work: Path, audit: dict) -> dict:
    cid = c["contender"]
    dest = work / "clones" / safe(cid)
    meta = dest / ".round-meta.json"
    if meta.is_file():
        return load(meta)
    if cid.startswith("page:"):
        dest.mkdir(parents=True, exist_ok=True)
        info = {"contender": cid, "kind": "pages", "pages": PAGES.get(cid, [c.get("repository")]), "tag": None,
                "commit": None, "read_at": now()}
        dump(meta, info)
        return info
    repos = [c["repository"]] + list(c.get("extra_repositories") or [])
    parts = []
    for i, url in enumerate(repos):
        repo = url.split("github.com/", 1)[1].strip("/").removesuffix(".git")
        target = dest if i == 0 else dest / "_extra" / safe(repo)
        tag = release_tag(repo, audit)
        cmd = ["git", "clone", "--quiet", "--depth", "1", "--filter=blob:limit=1m"]
        if tag:
            cmd += ["--branch", tag]
        cmd += [f"https://github.com/{repo}.git", str(target)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if proc.returncode != 0 and tag:
            shutil.rmtree(target, ignore_errors=True)
            proc = subprocess.run(cmd[:6] + [f"https://github.com/{repo}.git", str(target)], capture_output=True,
                                  text=True, timeout=1800)
            tag = None
        commit = subprocess.run(["git", "-C", str(target), "rev-parse", "HEAD"], capture_output=True,
                                text=True).stdout.strip() if proc.returncode == 0 else None
        parts.append({"repository": repo, "tag": tag, "commit": commit, "exit": proc.returncode,
                      "error": proc.stderr.strip()[-300:] if proc.returncode else None})
    info = {"contender": cid, "kind": "git", "repositories": parts, "tag": parts[0]["tag"],
            "commit": parts[0]["commit"], "read_at": now()}
    dest.mkdir(parents=True, exist_ok=True)
    dump(meta, info)
    return info


def stage_clone(work: Path, jobs: int, only: set) -> None:
    audit = load(AUDIT)["repositories"] if AUDIT.is_file() else {}
    todo = [c for c in contenders() if not only or c["contender"] in only]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda c: clone_one(c, work, audit), todo))
    failed = [r["contender"] for r in results if r["kind"] == "git" and any(p["exit"] for p in r["repositories"])]
    print(json.dumps({"stage": "clone", "contenders": len(results), "failed": failed}))


def unit_context(cid: str) -> str:
    lines = []
    for u in units():
        if any(f["contender"] == cid for f in u["field"]):
            lines.append(f"- {u['title']}: {u['requirement']}")
            lines += [f"  - {s['question']}" for s in u["slots"]]
    return "\n".join(lines)


def dossier_one(c: dict, work: Path) -> dict:
    cid = c["contender"]
    out = work / "dossiers" / f"{safe(cid)}.json"
    if out.is_file():
        return load(out)
    clone = work / "clones" / safe(cid)
    meta = load(clone / ".round-meta.json")
    project = {"name": c["name"], "repository": c["repository"], "extra_repositories": c.get("extra_repositories"),
               "revision": {"tag": meta.get("tag"), "commit": meta.get("commit")}}
    if meta["kind"] == "pages":
        project["pages_to_read"] = meta["pages"]
    tools = ["Read", "Grep", "Glob"] + (["WebFetch"] if meta["kind"] == "pages" else [])
    prompt = ((HERE / "dossier-prompt.txt").read_text(encoding="utf-8")
              .replace("__CONTENDER__", json.dumps(project, indent=2)).replace("__UNITS__", unit_context(cid)))
    schema = load(HERE / "dossier-schema.json")
    raw_dir = work / "raw" / "dossiers"
    written = attempt(claude, prompt, clone, WRITER_MODEL, tools, schema, TIMEOUT["dossier"],
                      raw_dir / f"{safe(cid)}.writer.json")
    record = {"contender": cid, "meta": meta, "writer": written["attempts"], "dossier": written["parsed"],
              "verification": [], "repaired": False}
    if record["dossier"]:
        record["dossier"]["contender"] = cid
        for round_ in (1, 2):
            v_prompt = (HERE / "verify-prompt.txt").read_text(encoding="utf-8").replace(
                "__DOSSIER__", json.dumps(record["dossier"], indent=2))
            verified = attempt(claude, v_prompt, clone, JUDGE_MODEL, tools, load(HERE / "verify-schema.json"),
                               TIMEOUT["verify"], raw_dir / f"{safe(cid)}.verify{round_}.json")
            record["verification"].append({"round": round_, "attempts": verified["attempts"],
                                           "result": verified["parsed"]})
            result = verified["parsed"] or {}
            if result.get("verdict") != "fail" or round_ == 2:
                break
            repair = (prompt + "\n\nA verifier checked your earlier dossier and found these problems; fix them and "
                      "return the full corrected dossier:\n" + json.dumps(result.get("repairs") or [], indent=2)
                      + "\n\nEarlier dossier:\n" + json.dumps(record["dossier"], indent=2))
            redone = attempt(claude, repair, clone, WRITER_MODEL, tools, schema, TIMEOUT["dossier"],
                             raw_dir / f"{safe(cid)}.repair.json")
            record["writer"] += redone["attempts"]
            if redone["parsed"]:
                record["dossier"], record["repaired"] = redone["parsed"], True
                record["dossier"]["contender"] = cid
    dump(out, record)
    return record


def stage_dossiers(work: Path, jobs: int, only: set) -> None:
    todo = [c for c in contenders() if not only or c["contender"] in only]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda c: dossier_one(c, work), todo))
    print(json.dumps({"stage": "dossiers", "done": sum(1 for r in results if r.get("dossier")),
                      "missing": [r["contender"] for r in results if not r.get("dossier")]}))


def audit_block(cid: str, audit: dict) -> dict | None:
    obs = audit.get(cid)
    if not obs:
        return None
    rel = obs.get("release") or {}
    return {"latest_release": rel.get("tag"), "released": rel.get("published_at"),
            "attested_assets": len([a for a in rel.get("attested_assets") or [] if a.get("attestations")]),
            "assets": rel.get("assets"), "advisories": obs.get("advisories"), "check_runs": obs.get("check_runs"),
            "archived": obs.get("archived"), "last_commit": (obs.get("head") or {}).get("date"),
            "scorecard": ((obs.get("deps_dev") or {}).get("scorecard")), "observed_at": obs.get("observed_at")}


def stage_packets(work: Path) -> None:
    audit = load(AUDIT)["repositories"] if AUDIT.is_file() else {}
    for u in units():
        for order in (1, 2):
            d = work / "units" / safe(u["unit_id"]) / f"order-{order}"
            (d / "dossiers").mkdir(parents=True, exist_ok=True)
            (d / "clones").mkdir(parents=True, exist_ok=True)
            field = u["field"] if order == 1 else list(reversed(u["field"]))
            listed = []
            for f in field:
                rec = load(work / "dossiers" / f"{safe(f['contender'])}.json")
                dossier = dict(rec.get("dossier") or {}, audit=audit_block(f["contender"], audit),
                               verification=(rec["verification"][-1]["result"] if rec["verification"] else None))
                dossier.pop("contender", None)
                dump(d / "dossiers" / f"{f['key']}.json", dossier)
                link = d / "clones" / f["key"]
                if not link.exists():
                    link.symlink_to(work / "clones" / safe(f["contender"]))
                listed.append({"key": f["key"], "name": f["name"], "repository": f["repository"],
                               "revision": {"tag": rec["meta"].get("tag"), "commit": rec["meta"].get("commit")},
                               "dossier": f"dossiers/{f['key']}.json", "source": f"clones/{f['key']}"})
            packet = {k: u[k] for k in ("unit_id", "title", "requirement", "target_hosts",
                                        "a_deciding_comparison_would_measure", "comparisons_on_record")}
            packet["slots"] = [{k: s[k] for k in ("slot_id", "question", "no_additional_component_allowed")}
                               for s in u["slots"]]
            packet["field"] = listed
            dump(d / "unit.json", packet)
    print(json.dumps({"stage": "packets", "units": len(units())}))


def unit_dirs(work: Path, unit_id: str) -> list:
    base = work / "units" / safe(unit_id)
    return [base / "order-1", base / "order-2"]


def clone_dirs(work: Path, unit: dict) -> list:
    return [work / "clones" / safe(f["contender"]) for f in unit["field"]]


def decide_one(task: tuple, work: Path) -> dict:
    family, unit, order = task
    d = unit_dirs(work, unit["unit_id"])[order - 1]
    out = work / "decisions" / family / f"{safe(unit['unit_id'])}.order-{order}.json"
    if out.is_file():
        return load(out)
    prompt = (HERE / "decide-prompt.txt").read_text(encoding="utf-8").replace("__CRITERIA__", criteria())
    raw = work / "raw" / "decide" / family / f"{safe(unit['unit_id'])}.order-{order}.json"
    if family == "claude":
        r = attempt(claude, prompt, d, JUDGE_MODEL, ["Read", "Grep", "Glob", "WebSearch", "WebFetch"],
                    load(HERE / "decide-schema.json"), TIMEOUT["decide"], raw, add_dirs=clone_dirs(work, unit))
    else:
        r = attempt(gpt, prompt, d, HERE / "decide-schema.json", TIMEOUT["decide"], raw, work)
    record = {"family": family, "unit_id": unit["unit_id"], "order": order, "decision": r["parsed"],
              "attempts": r["attempts"]}
    dump(out, record)
    return record


def stage_decide(work: Path, jobs: int, only: set, families: list) -> None:
    tasks = [(fam, u, o) for fam in families for u in units() if not only or u["unit_id"] in only for o in (1, 2)]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda t: decide_one(t, work), tasks))
    print(json.dumps({"stage": "decide", "done": sum(1 for r in results if r["decision"]),
                      "missing": [(r["family"], r["unit_id"], r["order"]) for r in results if not r["decision"]]}))


def critic_one(task: tuple, work: Path) -> dict:
    family, unit = task
    out = work / "critics" / family / f"{safe(unit['unit_id'])}.json"
    if out.is_file():
        return load(out)
    d = unit_dirs(work, unit["unit_id"])[0]
    decisions = {f"decider_{o}": load(work / "decisions" / family / f"{safe(unit['unit_id'])}.order-{o}.json")["decision"]
                 for o in (1, 2)}
    dump(d / "decisions.json", decisions)
    prompt = (HERE / "critic-prompt.txt").read_text(encoding="utf-8").replace("__CRITERIA__", criteria())
    raw = work / "raw" / "critic" / family / f"{safe(unit['unit_id'])}.json"
    if family == "claude":
        r = attempt(claude, prompt, d, JUDGE_MODEL, ["Read", "Grep", "Glob", "WebSearch", "WebFetch"],
                    load(HERE / "critic-schema.json"), TIMEOUT["critic"], raw, add_dirs=clone_dirs(work, unit))
    else:
        r = attempt(gpt, prompt, d, HERE / "critic-schema.json", TIMEOUT["critic"], raw, work)
    (d / "decisions.json").unlink(missing_ok=True)
    record = {"family": family, "unit_id": unit["unit_id"], "critic": r["parsed"], "attempts": r["attempts"]}
    dump(out, record)
    return record


def stage_critic(work: Path, jobs: int, only: set, families: list) -> None:
    tasks = [(fam, u) for fam in families for u in units() if not only or u["unit_id"] in only]
    # Critics of one family share each unit's order-1 directory for decisions.json, so run one family at a time.
    results = []
    for fam in families:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            results += list(pool.map(lambda t: critic_one(t, work), [t for t in tasks if t[0] == fam]))
    print(json.dumps({"stage": "critic", "done": sum(1 for r in results if r["critic"]),
                      "missing": [(r["family"], r["unit_id"]) for r in results if not r["critic"]]}))


def family_picks(work: Path, family: str, unit_id: str) -> dict:
    path = work / "critics" / family / f"{safe(unit_id)}.json"
    critic = (load(path)["critic"] or {}) if path.is_file() else {}
    picks = {}
    for s in critic.get("slots") or []:
        picks[s["slot_id"]] = s["surviving_default"] if s.get("verdict") in ("converged", "revised") else None
    return {"picks": picks, "critic": critic}


def contested(work: Path) -> list:
    out = []
    for u in units():
        c, g = family_picks(work, "claude", u["unit_id"]), family_picks(work, "gpt", u["unit_id"])
        for s in u["slots"]:
            a, b = c["picks"].get(s["slot_id"]), g["picks"].get(s["slot_id"])
            if a is None or b is None or a != b:
                out.append((u, s, c, g))
    return out


def adjudicate_one(task: tuple, work: Path) -> dict:
    family, u, s, c, g, flip = task
    tag = f"{safe(u['unit_id'])}.{s['slot_id']}.{'BA' if flip else 'AB'}"
    out = work / "adjudications" / family / f"{tag}.json"
    if out.is_file():
        return load(out)

    def ret(fam_record):
        crit = next((x for x in (fam_record["critic"].get("slots") or []) if x["slot_id"] == s["slot_id"]), {})
        return {k: crit.get(k) for k in ("verdict", "surviving_default", "checks", "issues", "settling_measurement",
                                         "overturn_check")}
    returns = {"A": ret(g if flip else c), "B": ret(c if flip else g)}
    d = work / "adjudication-dirs" / family / tag
    (d / "dossiers").mkdir(parents=True, exist_ok=True)
    src = unit_dirs(work, u["unit_id"])[0]
    shutil.copy(src / "unit.json", d / "unit.json")
    for f in (src / "dossiers").glob("*.json"):
        shutil.copy(f, d / "dossiers" / f.name)
    if not (d / "clones").exists():
        (d / "clones").symlink_to(src / "clones")
    dump(d / "returns.json", returns)
    prompt = ((HERE / "adjudicate-prompt.txt").read_text(encoding="utf-8").replace("__CRITERIA__", criteria())
              .replace("__SLOT__", f"{s['slot_id']}: {s['question']}"))
    raw = work / "raw" / "adjudicate" / family / f"{tag}.json"
    if family == "claude":
        r = attempt(claude, prompt, d, JUDGE_MODEL, ["Read", "Grep", "Glob", "WebSearch", "WebFetch"],
                    load(HERE / "adjudicate-schema.json"), TIMEOUT["adjudicate"], raw, add_dirs=clone_dirs(work, u))
    else:
        r = attempt(gpt, prompt, d, HERE / "adjudicate-schema.json", TIMEOUT["adjudicate"], raw, work)
    parsed = r["parsed"] or {}
    choice = parsed.get("choice")
    resolved = returns[choice]["surviving_default"] if choice in ("A", "B") else None
    record = {"family": family, "unit_id": u["unit_id"], "slot_id": s["slot_id"], "order": "BA" if flip else "AB",
              "return_a_family": "gpt" if flip else "claude", "result": r["parsed"], "resolved_default": resolved,
              "attempts": r["attempts"]}
    dump(out, record)
    return record


def stage_adjudicate(work: Path, jobs: int, families: list) -> None:
    tasks = [(fam, u, s, c, g, flip) for (u, s, c, g) in contested(work) for fam in families for flip in (False, True)]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda t: adjudicate_one(t, work), tasks))
    print(json.dumps({"stage": "adjudicate", "tasks": len(results),
                      "missing": sum(1 for r in results if not r["result"])}))


def stage_status(work: Path) -> None:
    counts = {k: len(list((work / k).rglob("*.json"))) if (work / k).exists() else 0
              for k in ("dossiers", "decisions", "critics", "adjudications")}
    clones = len(list((work / "clones").glob("*/.round-meta.json"))) if (work / "clones").exists() else 0
    print(json.dumps({"clones": clones, **counts}))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("stage", choices=["clone", "dossiers", "packets", "decide", "critic", "adjudicate", "status"])
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--only", nargs="*", default=[])
    parser.add_argument("--families", nargs="*", default=["claude", "gpt"])
    args = parser.parse_args(argv)
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    only = set(args.only)
    if args.stage == "clone":
        stage_clone(work, args.jobs, only)
    elif args.stage == "dossiers":
        stage_dossiers(work, args.jobs, only)
    elif args.stage == "packets":
        stage_packets(work)
    elif args.stage == "decide":
        stage_decide(work, args.jobs, only, args.families)
    elif args.stage == "critic":
        stage_critic(work, args.jobs, only, args.families)
    elif args.stage == "adjudicate":
        stage_adjudicate(work, args.jobs, args.families)
    else:
        stage_status(work)
    return 0


if __name__ == "__main__":
    sys.exit(main())
