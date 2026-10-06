"""Stage 1 fixture builder (§4.2, pilot spec stage 1.3-1.4).

git archive of the freeze commit into a non-git template, strip the instruction files and .claude/, run the find gate
(any ASCII case), write the setup files from local git objects, tar deterministically and hash. D oracles are computed in
a scratch extraction of the tarball (never from git, never in the template the tar came from). The routing-file
registry gets its pattern candidates here; the cross-family hint reader's review is the coordinator's, so the registry
written here is marked provisional.

Per trial, extract_fixture() unpacks the hashed tarball to NEUTRAL_ROOT/<8 random hex>/ and never deletes it.
"""
from __future__ import annotations

import ast
import os
import re
import secrets
import shutil
import subprocess
from pathlib import Path

from common import (EXPERIMENT_BASE, FIXTURE_CACHE, FREEZE_COMMIT, GATE_NAMES, HOME, KEPT_AGENTS_PATHS, NEUTRAL_ROOT,
                    STRIP_PATHS, load_json, manifest_digest, run, sha256_bytes, sha256_file, sha256_json, tree_manifest,
                    utc_now, write_json)

GIT_IDENTITY = {"GIT_AUTHOR_NAME": "Ledger Maintainer", "GIT_AUTHOR_EMAIL": "maintainer@example.invalid",
                "GIT_COMMITTER_NAME": "Ledger Maintainer", "GIT_COMMITTER_EMAIL": "maintainer@example.invalid"}
ROUTING_PATTERN = re.compile(r"\b(use|prefer|route|routing|lane|lanes|through|instead of|before|"
                             r"for (exact|conceptual|symbols?|docs?|large))\b", re.I)
# §4.2 examples of files whose purpose is to instruct an agent; the provisional registry keeps candidates under these.
# Finding 9 adds the user-level instruction sources (the env arm's harness files are rendered from them) and every
# agent definition under adoption/agents/ (Claude markdown and Codex TOML, workers included).
REVIEW_GLOBS = ("adoption/hooks/claude/token-lanes-block*.md", "docs/token-session-handbook.md", "docs/token-practice.md",
                "examples/claude-native/agents/*.md", "adoption/agents/*", "adoption/templates/*",
                "recipes/README.md", "examples/claude-native/workflows/*.js",
                "adoption/new-wsl/claude-user-instructions.md", "adoption/new-wsl/codex-user-instructions.md")
TRADING_RECEIPT = re.compile(r"(alpaca|ibkr|nautilus|adaptive-paper|trading)", re.I)


def git(repo: Path, *args, env=None, check=True) -> bytes:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, env=env)
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])} failed: {proc.stderr.decode(errors='replace')[:300]}")
    return proc.stdout


def git_blob(repo: Path, rev: str, path: str) -> bytes:
    return git(repo, "show", f"{rev}:{path}")


def builder_hash() -> str:
    here = Path(__file__).resolve().parent
    return sha256_bytes(b"".join((here / name).read_bytes() for name in ("fixture.py", "common.py", "suite.py")))


def _write(path: Path, data: bytes, mode: int = 0o644) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.chmod(path, mode)
    return {"bytes": len(data), "sha256": sha256_bytes(data)}


def strip_template(template: Path) -> list[dict]:
    records = []
    for rel in STRIP_PATHS:
        path = template / rel
        if path.is_dir() and not path.is_symlink():
            records.append({"path": rel, "type": "tree", "manifest_sha256": manifest_digest(tree_manifest(path)),
                            "files": len(tree_manifest(path))})
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            records.append({"path": rel, "type": "file", "sha256": sha256_file(path)})
            path.unlink()
        else:
            records.append({"path": rel, "type": "absent"})
    return records


def find_gate(template: Path) -> dict:
    """§4.2 gate: names AGENTS.md, AGENTS.override.md, CLAUDE.md, CLAUDE.local.md, .claude, .codex and .mcp.json at any
    depth, in any ASCII case, must be gone; the only .agents paths are the two kept ones."""
    hits, agents = [], []
    for dirpath, dirnames, filenames in os.walk(template):
        base = Path(dirpath)
        for name in dirnames + filenames:
            rel = (base / name).relative_to(template).as_posix()
            if name.lower() in GATE_NAMES:
                hits.append(rel)
            if name.lower() == ".agents":
                agents.append(rel)
    return {"instruction_hits": sorted(hits), "agents_paths": sorted(agents),
            "pass": not hits and sorted(agents) == sorted(KEPT_AGENTS_PATHS)}


def setup_files(repo: Path, template: Path, commit: str) -> tuple[list[dict], list[dict]]:
    """The suite's setup files, from local git objects only. Returns (records, gaps)."""
    records, gaps = [], []

    def blob(rev, src, dest, note=""):
        data = git_blob(repo, rev, src)
        rec = _write(template / dest, data)
        rec.update({"dest": dest, "source": f"{rev}:{src}", "note": note})
        records.append(rec)
        return data

    pr723 = blob("bf2c6f85", "evidence/artifacts/new-wsl-install-plan-20261002/config/promptfoo-gateway.cjs",
                 "alerts/pr723-promptfoo-gateway.cjs", "fp-check P1 (PR #723)")
    pr736 = blob("d109af7a", "blueprints/us-equities/hosting/drill_local_recovery.py",
                 "alerts/pr736-drill_local_recovery.py", "fp-check P2 (PR #736)")
    lines723, lines736 = pr723.decode(errors="replace").splitlines(), pr736.decode(errors="replace").splitlines()
    records.append({"check": "alert line numbers", "pr723_line15_exists": len(lines723) >= 15,
                    "pr723_line15_url_substring_shape": bool(len(lines723) >= 15 and re.search(
                        r"(includes|indexOf|startsWith|endsWith)\s*\(", lines723[14])),
                    "pr736_line225_exists": len(lines736) >= 225,
                    "pr736_line225_names_password": bool(len(lines736) >= 225 and re.search(r"pass", lines736[224], re.I))})
    # ./review/: #736 head blobs of the hosting files the PR changed against its merge base with main, and #709's template.
    base736 = git(repo, "merge-base", commit, "e97a6035").decode().strip()
    changed = git(repo, "diff", "--name-only", "--diff-filter=AMR", base736, "e97a6035", "--",
                  "blueprints/us-equities/hosting/").decode().split()
    for path in changed:
        blob("e97a6035", path, f"review/{path}", "PR #736 head (gh-address-comments P1)")
    blob("b0b9f752", "adoption/templates/codex.AGENTS.template.md", "review/adoption/templates/codex.AGENTS.template.md",
         "PR #709 head (gh-address-comments P2; threads at :56 and :62)")
    # ./before and ./after: two sides of f3ebf469 and 095d4fad.
    blob("f3ebf469^", "scripts/freshness_propose.py", "before/freshness_propose.py", "difftastic P1 before")
    blob("f3ebf469", "scripts/freshness_propose.py", "after/freshness_propose.py", "difftastic P1 after")
    blob("095d4fad^", "blueprints/us-equities/adaptive-paper/sessions.py", "before/sessions.py", "difftastic P2 before")
    blob("095d4fad", "blueprints/us-equities/adaptive-paper/sessions.py", "after/sessions.py", "difftastic P2 after")
    # ./freeze from the tree.
    for src, dest in (("evidence/artifacts/rtk-fold-harbor-20261004/FREEZE.json", "freeze/a.json"),
                      ("evidence/artifacts/rtk-fold-harbor-20261004/FREEZE-v4.json", "freeze/b.json")):
        data = (template / src).read_bytes()
        rec = _write(template / dest, data)
        rec.update({"dest": dest, "source": f"tree:{src}"})
        records.append(rec)
    # ./publish: a copy of the trading-lane receipts (builder's selection rule; review before the full-run freeze).
    receipts = sorted(p for p in (template / "evidence/receipts").glob("*.json") if TRADING_RECEIPT.search(p.name))
    for src in receipts:
        data = src.read_bytes()
        rec = _write(template / "publish" / src.name, data)
        rec.update({"dest": f"publish/{src.name}", "source": f"tree:evidence/receipts/{src.name}",
                    "note": "selection rule: evidence/receipts/*.json named alpaca|ibkr|nautilus|adaptive-paper|trading"})
        records.append(rec)
    # ./scan: real SARIF from zizmor and betterleaks, run offline on the template, under neutral names.
    records.extend(_scans(template, gaps))
    # ./ledger-repo: builder-authored nested repository for the git and worktrunk cards.
    try:
        records.append(_ledger_repo(template / "ledger-repo"))
    except Exception as error:  # noqa: BLE001
        gaps.append({"setup": "ledger-repo", "reason": f"construction failed: {type(error).__name__}: {error}"[:300]})
    gaps.append({"setup": "filings/annual-report.pdf", "reason": "needs a network download from SEC EDGAR with the "
                 "private SEC contact string (a credential-store entry); no pilot card reads it. Coordinator item."})
    gaps.append({"setup": "095d4fad^ hunk", "reason": "restoring the pre-fix overnight-cap hunk edits engine files whose "
                 "anchors other cards use (safety.py, native_strategy.py, P2 anchors held at 9e955327); the exact hunk is "
                 "for the diagnosing-bugs.P2 card owner to name. No pilot card reads it. Deferred to the full-run freeze."})
    (template / "draft").mkdir(exist_ok=True)
    return records, gaps


def _scans(template: Path, gaps: list) -> list[dict]:
    out = []
    jobs = (("scan/results-a.json", ["zizmor", "--offline", "--no-config", "--format", "sarif", ".github/workflows"]),
            ("scan/results-b.json", ["betterleaks", "dir", ".", "--no-banner", "--redact", "--report-format", "sarif",
                                     "--report-path", "-", "--exit-code", "0", "--log-level", "error"]))
    for dest, cmd in jobs:
        tool = cmd[0]
        if not shutil.which(tool):
            gaps.append({"setup": dest, "reason": f"{tool} not on PATH"})
            continue
        version = run([tool, "--version"] if tool == "zizmor" else [tool, "version"], timeout=60).stdout.decode().strip()
        proc = run(cmd, cwd=template, timeout=1800)
        data = proc.stdout
        text = data.decode(errors="replace")
        if not text.strip().startswith("{"):
            gaps.append({"setup": dest, "reason": f"{tool} produced no SARIF (rc {proc.returncode})"})
            continue
        # Neutral names: no host path or template location may reach the model.
        text = text.replace(str(template) + "/", "").replace(str(template), ".").replace(str(HOME), "~")
        data = text.encode()
        rec = _write(template / dest, data)
        rec.update({"dest": dest, "source": f"{tool} {version} run offline on the template", "rc": proc.returncode,
                    "mentions_cache_path": "ns2604-organic-fixtures" in text})
        out.append(rec)
    return out


def _ledger_repo(root: Path) -> dict:
    """A small owned repository: two branches with conflicting edits to docs/limits.md and docs/limits-notes.md, a
    rounding change planted in price_tools.py's history, and a linked worktree (relative paths) whose worktree-level
    core.hooksPath points at a failing pre-commit hook. Fixed identity and dates make the commit ids reproducible."""
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    base_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    base_env.update(GIT_IDENTITY)
    base_env["GIT_CONFIG_GLOBAL"] = os.devnull
    base_env["GIT_CONFIG_NOSYSTEM"] = "1"

    def g(*args, date=None):
        env = dict(base_env)
        if date:
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
        return git(root, *args, env=env)

    def put(rel, text, mode=0o644):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        os.chmod(path, mode)

    g("init", "-q", "-b", "main")
    g("config", "extensions.worktreeConfig", "true")
    put("price_tools.py", PRICE_V1)
    put("docs/limits.md", LIMITS_V1)
    put("docs/limits-notes.md", NOTES_V1)
    put(".githooks/pre-commit", HOOK, 0o755)
    put("README.md", "# Ledger tools\n\nSmall helpers for the paper ledger: price rounding and the limit table.\n")
    g("add", "-A")
    g("commit", "-q", "-m", "Ledger tools: price rounding and the limit table", date="2026-09-01T10:00:00+00:00")
    put("price_tools.py", PRICE_V2)
    g("commit", "-q", "-am", "Add notional() for order sizing", date="2026-09-03T10:00:00+00:00")
    put("price_tools.py", PRICE_V3)
    g("commit", "-q", "-am", "Simplify price rounding", date="2026-09-05T10:00:00+00:00")
    put("README.md", "# Ledger tools\n\nSmall helpers for the paper ledger: price rounding, notional sizing and the "
        "limit table in docs/limits.md.\n")
    g("commit", "-q", "-am", "README: mention notional sizing", date="2026-09-08T10:00:00+00:00")
    g("branch", "limits-order-cap")
    g("branch", "limits-position-cap")
    g("checkout", "-q", "limits-order-cap")
    put("docs/limits.md", LIMITS_A)
    put("docs/limits-notes.md", NOTES_A)
    g("commit", "-q", "-am", "Lower the per-order cap after the 09-10 review", date="2026-09-10T10:00:00+00:00")
    g("checkout", "-q", "limits-position-cap")
    put("docs/limits.md", LIMITS_B)
    put("docs/limits-notes.md", NOTES_B)
    g("commit", "-q", "-am", "Raise the position cap for the larger paper account", date="2026-09-11T10:00:00+00:00")
    g("checkout", "-q", "main")
    (root / ".git" / "info").mkdir(parents=True, exist_ok=True)
    with open(root / ".git" / "info" / "exclude", "a") as handle:
        handle.write(".worktrees/\n")
    g("worktree", "add", "-q", "--relative-paths", "-b", "release-check", ".worktrees/release-check", "main")
    git(root / ".worktrees" / "release-check", "config", "--worktree", "core.hooksPath", ".githooks", env=base_env)
    head = g("rev-parse", "HEAD").decode().strip()
    planted = g("log", "--format=%H", "-1", "--grep=Simplify", "--", "price_tools.py").decode().strip()
    return {"dest": "ledger-repo", "source": "builder-authored (review before the full-run freeze)",
            "head": head, "planted_rounding_commit": planted, "branches": ["main", "limits-order-cap", "limits-position-cap",
                                                                            "release-check"],
            "hook_worktree": ".worktrees/release-check", "manifest_sha256": manifest_digest(tree_manifest(root))}


PRICE_V1 = '''from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def round_price(value) -> Decimal:
    """Round a price to the cent, halves away from zero, as the broker does."""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
'''
PRICE_V2 = PRICE_V1 + '''

def notional(quantity: int, price) -> Decimal:
    """Order notional in dollars at the rounded price."""
    return round_price(price) * quantity
'''
PRICE_V3 = '''from decimal import Decimal

CENT = Decimal("0.01")


def round_price(value) -> Decimal:
    """Round a price to the cent."""
    return Decimal(round(float(value), 2)).quantize(CENT)


def notional(quantity: int, price) -> Decimal:
    """Order notional in dollars at the rounded price."""
    return round_price(price) * quantity
'''
LIMITS_V1 = "# Limits\n\n| limit | value |\n|---|---|\n| max_position_usd | 25000 |\n| max_order_usd | 5000 |\n| max_orders_per_day | 40 |\n"
LIMITS_A = "# Limits\n\n| limit | value |\n|---|---|\n| max_position_usd | 25000 |\n| max_order_usd | 4000 |\n| max_orders_per_day | 40 |\n"
LIMITS_B = "# Limits\n\n| limit | value |\n|---|---|\n| max_position_usd | 30000 |\n| max_order_usd | 5000 |\n| max_orders_per_day | 40 |\n"
NOTES_V1 = "# Notes on the limits\n\n- 2026-09-01: initial table.\n"
NOTES_A = NOTES_V1 + "- 2026-09-10: max_order_usd lowered to 4000 after the review of oversized fills.\n"
NOTES_B = NOTES_V1 + "- 2026-09-11: max_position_usd raised to 30000 for the larger paper account.\n"
HOOK = "#!/bin/sh\n# Release check: refuse a commit while the limit table has no review line for today.\necho 'pre-commit: docs/limits-notes.md has no review entry for today' >&2\nexit 1\n"


def experiment_check(repo: Path, commit: str) -> dict:
    """§4.2: git log -p EXPERIMENT_BASE..commit must hold 0 matches for the experiment's names."""
    out = git(repo, "log", "-p", f"{EXPERIMENT_BASE}..{commit}")
    text = out.decode(errors="replace")
    count = len(re.findall(r"organic-e2e|organic invocation|organic-invocation", text, re.I))
    return {"range": f"{EXPERIMENT_BASE}..{commit[:8]}", "matches": count, "pass": count == 0}


def make_tar(template: Path, tar_path: Path, mtime: int) -> dict:
    """Deterministic tar (sorted names, fixed owner and mtime) of the template's contents."""
    tar_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tar_path.with_name(tar_path.name + ".tmp")
    proc = run(["tar", "-C", str(template), "--sort=name", "--owner=0", "--group=0", "--numeric-owner",
                f"--mtime=@{mtime}", "--format=gnu", "-cf", str(tmp), "."], timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError(f"tar failed: {proc.stderr.decode(errors='replace')[:300]}")
    os.replace(tmp, tar_path)
    return {"path": str(tar_path), "sha256": sha256_file(tar_path), "bytes": tar_path.stat().st_size}


def extract_tar(tar_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=False)
    proc = run(["tar", "-C", str(dest), "-xf", str(tar_path)], timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError(f"tar extract failed: {proc.stderr.decode(errors='replace')[:300]}")


def extract_fixture(tar_path: Path, expected_sha256: str, *, verify: bool = True) -> Path:
    """One fixture copy per trial at NEUTRAL_ROOT/<8 random hex>/ (§4.1 step 4). Refuses a tarball whose hash moved."""
    if verify and sha256_file(tar_path) != expected_sha256:
        raise RuntimeError("fixture tarball hash mismatch")
    NEUTRAL_ROOT.mkdir(parents=True, exist_ok=True)
    for _ in range(16):
        dest = NEUTRAL_ROOT / secrets.token_hex(4)
        if not dest.exists():
            extract_tar(tar_path, dest)
            (dest / "draft").mkdir(exist_ok=True)
            return dest
    raise RuntimeError("could not allocate a fixture path")


def routing_registry(template: Path, lex_names: list[str]) -> dict:
    """§4.2 pattern candidates: a line that names an item and matches the routing pattern. The provisional reviewed list
    keeps candidates under the protocol's example globs (fnmatch: * crosses directories, so adoption/agents/* covers
    the workers too); the hint reader's review replaces it before the freeze. marker_files lists every template file
    that carries a §2.1 harness marker, for that review (receipts and tests among them are data, not routing files);
    the grader tags a use after any tool result carrying a marker regardless of the registry."""
    from common import MARKERS
    names = [n for n in lex_names if len(n) >= 3]
    name_re = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")(?![a-z0-9])", re.I)
    candidates, marker_files = {}, {}
    for dirpath, dirnames, filenames in os.walk(template):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules")]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() not in (".md", ".js", ".mjs", ".py", ".json", ".toml", ".yaml", ".yml", ".txt", ".sh", ".html"):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            rel = path.relative_to(template).as_posix()
            markers = sorted(m for m in MARKERS if m in text)
            if markers:
                marker_files[rel] = markers
            for number, line in enumerate(text.splitlines(), 1):
                if ROUTING_PATTERN.search(line):
                    found = name_re.findall(line)
                    if found:
                        entry = candidates.setdefault(rel, {"lines": 0, "items": set()})
                        entry["lines"] += 1
                        entry["items"].update(f.lower() for f in found)
    import fnmatch
    provisional = sorted(rel for rel in candidates if any(fnmatch.fnmatch(rel, glob) for glob in REVIEW_GLOBS))
    return {"candidates": {rel: {"lines": v["lines"], "items": sorted(v["items"])} for rel, v in sorted(candidates.items())},
            "provisional_reviewed": provisional, "review_globs": list(REVIEW_GLOBS),
            "marker_files": dict(sorted(marker_files.items())),
            "status": "provisional: pattern candidates under the protocol's example globs; the cross-family hint "
                      "reader's review must replace this list before the full-run freeze"}


# ---------------------------------------------------------------------------------------------------------------------
# D oracles, computed inside a scratch extraction of the tarball.

def _source_span(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            return node, tree
    return None, tree


def _lines(path: Path) -> list[str]:
    """Physical lines as editors and ast number them: split on newline only (str.splitlines also splits on form feeds
    and U+2028, which would shift every later line number)."""
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")


def _callers(root: Path, func: str, module_rel: str) -> list[str]:
    """Call sites of module_rel's func: bare calls inside that module, and in any other file that names the module
    (import, from-import or a loader string), calls of func by name or as an attribute."""
    out = []
    module_stem = Path(module_rel).stem
    for path in sorted(root.rglob("*.py")):
        if ".git" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except (SyntaxError, UnicodeDecodeError, OSError, ValueError):
            continue
        own = rel == module_rel
        if not own and module_stem not in text:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if own and isinstance(fn, ast.Name) and fn.id == func:
                    out.append(f"{rel}:{node.lineno}")
                elif not own and ((isinstance(fn, ast.Attribute) and fn.attr == func) or (isinstance(fn, ast.Name) and fn.id == func)):
                    out.append(f"{rel}:{node.lineno}")
    return sorted(out, key=lambda s: (s.rsplit(":", 1)[0], int(s.rsplit(":", 1)[1])))


def compute_oracles(work: Path, *, run_tests: bool = True) -> dict:
    """D oracles for the pilot cards that a local, offline computation can establish (G12). R oracles and the external
    semble.P1 oracle are listed as not computed here."""
    out = {"computed_at": utc_now(), "in": "scratch extraction of the fixture tarball (stripped, non-git)"}
    stack = load_json(work / "manifests/stack.json")
    out["control/both/G1"] = {"top_level_keys": len(stack), "keys": sorted(stack.keys())}
    readme = _lines(work / "tools/skill-usage/README.md")
    out["control/both/NM1"] = {"lines": "tools/skill-usage/README.md:103-111", "text": "\n".join(readme[102:111])}
    out["skill/both/diagnosing-bugs.P1"] = {"lines": "tools/skill-usage/README.md:194-199", "text": "\n".join(readme[193:199])}
    su = work / "tools/skill-usage/skill_usage.py"
    su_lines = _lines(su)
    node, tree = _source_span(su, "scan_codex_roots")
    helpers = {}
    if node:
        module_funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        called = sorted({c.func.id for c in ast.walk(node) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                         and c.func.id in module_funcs and c.func.id != "scan_codex_roots"})
        for name in called:
            fn = module_funcs[name]
            helpers[name] = {"lines": f"{fn.lineno}-{fn.end_lineno}",
                             "sha256": sha256_bytes("\n".join(su_lines[fn.lineno - 1:fn.end_lineno]).encode())}
        out["mcp_server/both/jcodemunch.P1"] = {
            "file_lines": len(su_lines) - (1 if su_lines and su_lines[-1] == "" else 0),
            "scan_codex_roots": f"{node.lineno}-{node.end_lineno}",
            "sha256": sha256_bytes("\n".join(su_lines[node.lineno - 1:node.end_lineno]).encode()), "helpers": helpers}
    out["mcp_server/both/socraticode.P1"] = {"skill_usage.py:911": su_lines[910].strip() if len(su_lines) > 910 else None,
                                             "skill_usage.py:863": su_lines[862].strip() if len(su_lines) > 862 else None}
    safety = work / "blueprints/us-equities/adaptive-paper/safety.py"
    s_lines = _lines(safety)
    ledger, _ = _source_span(safety, "Ledger")
    out["mcp_server/both/headroom.P2"] = {"file_lines": len(s_lines) - (1 if s_lines and s_lines[-1] == "" else 0),
                                          "Ledger": f"{ledger.lineno}-{ledger.end_lineno}" if ledger else None,
                                          "sha256_421_to_end": sha256_bytes("\n".join(s_lines[420:]).encode())}
    out["mcp_server/both/serena.P1"] = {"callers_of_parse_iso": _callers(work, "parse_iso", "tools/skill-usage/skill_usage.py"),
                                        "rule": "bare calls in skill_usage.py; attribute or bare calls in files naming the module"}
    hr = work / "scripts/host_receipts.py"
    hr_lines = _lines(hr)
    out["mcp_server/both/codebase-memory.P1"] = {f"host_receipts.py:{n}": hr_lines[n - 1].strip() if len(hr_lines) >= n else None
                                                 for n in (2024, 727, 1207)}
    hits = []
    for top in ("scripts", "tools"):
        for path in sorted((work / top).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError, ValueError):
                continue
            for call in ast.walk(tree):
                if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "run"
                        and isinstance(call.func.value, ast.Name) and call.func.value.id == "subprocess"
                        and not any(k.arg == "check" for k in call.keywords)):
                    hits.append(f"{path.relative_to(work).as_posix()}:{call.lineno}")
    out["cli/both/ast-grep.P1"] = {"subprocess_run_without_check": hits, "count": len(hits),
                                   "rule": "subprocess.run(...) called as an attribute of the subprocess module, no check= keyword"}
    if run_tests:
        modules = sorted(p.stem for p in (work / "tests").glob("test_catalog_freshness_*.py")) + ["test_landscape_sweep_harness"]
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "CLAUDE", "CODEX"))}
        proc = run(["python3", "-m", "unittest", *[f"tests.{m}" for m in modules]], cwd=work, env=env, timeout=1500)
        text = proc.stderr.decode(errors="replace")
        failed = sorted(set(re.findall(r"^(?:FAIL|ERROR): (\S+ \([^)]+\))", text, re.M)))
        summary = re.findall(r"^(Ran \d+ tests? in [\d.]+s)$", text, re.M)
        tail = re.findall(r"^(OK.*|FAILED \(.*\))$", text, re.M)
        out["mcp_server/both/context-mode.P1"] = {"modules": modules, "rc": proc.returncode, "ran": summary[-1] if summary else None,
                                                  "result": tail[-1] if tail else None, "failed_or_errored": failed}
    out["not_computed_here"] = {
        "mcp_server/both/semble.P1": "upstream openai/codex rust-v0.160.0 codex-rs/otel/src/tool_result.rs:57-79 (suite source)",
        "skill/both/search-first.P1": "R", "skill/claude/skill-creator.P1": "R", "skill/codex/skill-creator.P1": "R",
        "skill/both/variant-analysis.P1": "D/R: the candidate list from docs/harness-defaults.md:123 is compiled by the card owner",
    }
    return out


def build(repo: Path, *, commit_ref: str = FREEZE_COMMIT, lex_names=(), run_tests: bool = True, force: bool = False) -> dict:
    commit = git(repo, "rev-parse", f"{commit_ref}^{{commit}}").decode().strip()
    # A template whose D oracles were computed without the unit tests (--skip-oracle-tests, self-tests) has its own
    # cache directory: smoke-20261006a reused one and froze a null context-mode.P1 oracle, which G12 then flagged.
    out_dir = FIXTURE_CACHE / f"fixture-{commit[:8]}-{builder_hash()[:8]}{'' if run_tests else '-nt'}"
    record_path = out_dir / "fixture.json"
    if record_path.exists() and not force:
        record = load_json(record_path)
        if Path(record["tar"]["path"]).exists() and sha256_file(record["tar"]["path"]) == record["tar"]["sha256"] \
                and record.get("oracle_tests_run", True) == run_tests:
            record["reused"] = True
            return record
    if out_dir.exists():
        shutil.rmtree(out_dir)
    template = out_dir / "template"
    template.mkdir(parents=True)
    archive = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", commit], capture_output=True, check=True).stdout
    proc = subprocess.run(["tar", "-C", str(template), "-xf", "-"], input=archive, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError("archive extraction failed")
    record = {"built_at": utc_now(), "commit": commit, "builder_sha256": builder_hash(), "archive_sha256": sha256_bytes(archive)}
    record["experiment_check"] = experiment_check(repo, commit)
    record["strip"] = strip_template(template)
    record["gate"] = find_gate(template)
    setup, gaps = setup_files(repo, template, commit)
    record["setup"], record["setup_gaps"] = setup, gaps
    record["gate_after_setup"] = find_gate(template)
    manifest = tree_manifest(template)
    write_json(out_dir / "template-manifest.json", manifest, 0o600)
    record["template_manifest_sha256"] = manifest_digest(manifest)
    record["template_files"] = len(manifest)
    commit_time = int(git(repo, "show", "-s", "--format=%ct", commit).decode().strip())
    record["tar"] = make_tar(template, out_dir / "fixture.tar", commit_time)
    registry = routing_registry(template, list(lex_names))
    record["registry_sha256"] = write_json(out_dir / "routing-registry.json", registry, 0o600)
    record["registry_counts"] = {"candidates": len(registry["candidates"]), "provisional_reviewed": len(registry["provisional_reviewed"]),
                                 "marker_files": len(registry["marker_files"])}
    work = out_dir / "oracle-work"
    extract_tar(out_dir / "fixture.tar", work)
    oracles = compute_oracles(work, run_tests=run_tests)
    record["oracle_tests_run"] = run_tests
    record["oracles_sha256"] = write_json(out_dir / "oracles.json", oracles, 0o600)
    record["oracles_digest_without_time"] = sha256_json({k: v for k, v in oracles.items() if k != "computed_at"})
    record["dir"] = str(out_dir)
    write_json(record_path, record, 0o600)
    return record
