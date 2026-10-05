"""The two arms' per-trial treatment (§2, §4.3, §8.1, §8.2).

Claude: a per-trial --settings file holding the §8.1 deny list; the native arm adds claudeMdExcludes for the user
CLAUDE.md, the env arm does not (one factor).
Codex: a per-trial CODEX_HOME clone of the host home (U1 recipe, amended): copied config files, symlinked shared
directories, fresh state databases. The native clone has no AGENTS.md; the env clone keeps a copy of the host's. Both
add GH_CONFIG_DIR inside the existing [shell_environment_policy.set] table and rules/organic-e2e.rules.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from common import CODEX_HOME_REAL, HOME, USER_CLAUDE_MD, run, sha256_bytes, sha256_file, sha256_json, tree_manifest

# §8.1 Bash rules; each is also denied with an rtk prefix.
BASH_DENY_BASE = [
    "git push *",
    *[f"gh pr {verb} *" for verb in ("comment", "review", "merge", "close", "edit", "create", "ready")],
    *[f"gh issue {verb} *" for verb in ("comment", "create", "edit", "close")],
    *[f"gh run {verb} *" for verb in ("rerun", "cancel")],
    *[f"gh release {verb} *" for verb in ("create", "delete", "edit", "upload")],
    *[f"gh repo {verb} *" for verb in ("create", "delete", "edit")],
    "claude *", "codex *",
    "npm i -g *", "npm install -g *", "pip install --user *", "uv tool install *", "mise use -g *",
    "systemctl --user *", "crontab *",
]
GH_API_METHODS = ("POST", "PATCH", "PUT", "DELETE")


def gh_api_write_rules() -> list[str]:
    """gh api write forms only (GET stays allowed): the method flag spaced, attached (-XPOST) and as --method=, after the
    endpoint or first; and the body flags. A pattern's leading space before * needs a preceding token, so the first-
    position forms are listed separately."""
    rules = []
    for method in GH_API_METHODS:
        for form in (f"-X {method}*", f"-X{method}*", f"--method {method}*", f"--method={method}*"):
            rules += [f"gh api {form}", f"gh api * {form}"]
    for flag in ("-f", "-F", "--field", "--raw-field", "--input"):
        rules += [f"gh api {flag} *", f"gh api * {flag} *"]
    return rules


TOOL_DENY = ["CronCreate", "RemoteTrigger", "PushNotification",
             "mcp__plugin_context-mode_context-mode__ctx_upgrade", "mcp__plugin_context-mode_context-mode__ctx_purge"]
EDIT_DENY = ["~/.claude/settings*.json", "~/.claude.json", "~/.claude/CLAUDE.md", "~/.claude/agents/**",
             "~/.claude/skills/**", "~/.claude/plugins/**", "~/.codex/**", "~/.agents/**"]
# docs/secret-storage.md's list beyond the committed settings' denies: the OpenHands per-attempt session keys.
SECRET_STORAGE_EXTRA_READ = ["~/.local/state/native-agent-stack/runtime-workers/openhands/secrets/**"]


def committed_credential_denies(repo: Path, commit: str) -> dict:
    """The credential-read denies of the committed .claude/settings.json at the freeze commit (§8.1 Read, §12.8)."""
    from fixture import git_blob
    settings = json.loads(git_blob(repo, commit, ".claude/settings.json"))
    deny = (settings.get("permissions") or {}).get("deny") or []
    return {"read": [r for r in deny if r.startswith("Read(")], "edit": [r for r in deny if r.startswith("Edit(")],
            "bash": [r for r in deny if r.startswith("Bash(")], "source_sha256": sha256_json(deny)}


def deny_list(credential: dict) -> list[str]:
    bash = BASH_DENY_BASE + gh_api_write_rules()
    rules = [f"Bash({p})" for p in bash] + [f"Bash(rtk {p})" for p in bash]
    rules += TOOL_DENY
    rules += [f"Edit({p})" for p in EDIT_DENY]
    rules += credential["read"] + credential["edit"] + credential["bash"]
    rules += [f"Read({p})" for p in SECRET_STORAGE_EXTRA_READ]
    seen, out = set(), []
    for rule in rules:
        if rule not in seen:
            seen.add(rule)
            out.append(rule)
    return out


def claude_settings(arm: str, deny: list[str]) -> dict:
    settings = {"permissions": {"deny": deny}}
    if arm == "native":
        settings = {"claudeMdExcludes": [str(USER_CLAUDE_MD)], **settings}
    return settings


# ---------------------------------------------------------------------------------------------------------------------
# Codex rules (§8.2). Prefix rules only; labelled partial.

RULE_JUSTIFICATION = "not permitted in this workspace"


def codex_rule_patterns() -> list[list]:
    base = [
        ["git", "push"],
        ["gh", "pr", ["comment", "review", "merge", "close", "edit", "create", "ready"]],
        ["gh", "issue", ["comment", "create", "edit", "close"]],
        ["gh", "run", ["rerun", "cancel"]],
        ["gh", "release", ["create", "delete", "edit", "upload"]],
        ["gh", "repo", ["create", "delete", "edit"]],
        ["gh", "api", "-X", list(GH_API_METHODS)],
        ["gh", "api", [f"-X{m}" for m in GH_API_METHODS]],
        ["gh", "api", "--method", list(GH_API_METHODS)],
        ["gh", "api", [f"--method={m}" for m in GH_API_METHODS]],
        ["gh", "api", ["-f", "-F", "--field", "--raw-field", "--input"]],
        ["claude"], ["codex"],
        ["npm", ["i", "install"], "-g"], ["npm", ["i", "install"], "--global"],
        ["pip", "install", "--user"], ["pip3", "install", "--user"],
        ["uv", "tool", "install"], ["mise", "use", "-g"], ["mise", "use", "--global"],
        ["systemctl", "--user"], ["crontab"],
    ]
    return base + [["rtk", *p] for p in base]


def _starlark(value) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_starlark(v) for v in value) + "]"
    return json.dumps(value)


def codex_rules_text() -> str:
    lines = ["# Forbidden prefixes for this workspace (prefix rules; partial by construction)."]
    for pattern in codex_rule_patterns():
        lines.append(f"prefix_rule(pattern = {_starlark(pattern)}, decision = \"forbidden\", "
                     f"justification = \"{RULE_JUSTIFICATION}\")")
    return "\n".join(lines) + "\n"


def _first_expansion(pattern: list) -> list[str]:
    return [p[0] if isinstance(p, list) else p for p in pattern]


def verify_codex_rules(rules_path: Path, codex_bin: str) -> dict:
    """codex execpolicy check --rules on one command per rule (each alternative of each rule), plus GET reads that must
    stay allowed. Every forbidden probe must return decision forbidden."""
    probes, results = [], []
    for pattern in codex_rule_patterns():
        alternatives = [[]]
        for part in pattern:
            options = part if isinstance(part, list) else [part]
            alternatives = [a + [o] for a in alternatives for o in options]
        for tokens in alternatives:
            probes.append((tokens + ["x"], "forbidden"))
    for tokens in (["gh", "api", "repos/o/r/pulls"], ["gh", "pr", "list"], ["git", "status"], ["gh", "auth", "status"]):
        probes.append((tokens, "allowed"))
    failures = []
    for tokens, expect in probes:
        proc = run([codex_bin, "execpolicy", "check", "--rules", str(rules_path), *tokens], timeout=60)
        try:
            decision = json.loads(proc.stdout.decode() or "{}").get("decision") or "no-match"
        except ValueError:
            decision = "unparsed"
        ok = decision == "forbidden" if expect == "forbidden" else decision != "forbidden"
        results.append(ok)
        if not ok:
            failures.append({"command": " ".join(tokens), "expected": expect, "got": decision})
    return {"probes": len(probes), "passed": sum(results), "failures": failures, "pass": not failures,
            "label": "partial: prefix rules miss endpoint-first gh api forms, rewrites and assignment-prefixed scripts"}


# ---------------------------------------------------------------------------------------------------------------------
# Codex per-trial clone (§4.3).

COPY = ("config.toml", "omniroute.config.toml", "hooks.json", "models_cache.json")
SYMLINK = ("skills", "plugins", "packages", "context-mode", "sessions", "cache")


def insert_gh_config_dir(config_text: str, gh_dir: str) -> str:
    """GH_CONFIG_DIR goes inside the existing [shell_environment_policy.set] table (a second header of that name is a
    TOML error); without the table, one is appended."""
    line = f'GH_CONFIG_DIR = {json.dumps(gh_dir)}'
    lines = config_text.splitlines()
    for index, text in enumerate(lines):
        if re.match(r"^\s*\[shell_environment_policy\.set\]\s*$", text):
            for later in lines[index + 1:]:
                if re.match(r"^\s*\[", later):
                    break
                if re.match(r"^\s*GH_CONFIG_DIR\s*=", later):
                    raise ValueError("GH_CONFIG_DIR already set in the host table")
            lines.insert(index + 1, line)
            return "\n".join(lines) + ("\n" if config_text.endswith("\n") else "")
    return config_text.rstrip("\n") + "\n\n[shell_environment_policy.set]\n" + line + "\n"


def build_clone(dest: Path, arm: str, gh_dir: Path, rules_text: str) -> dict:
    """Create one CODEX_HOME clone. Returns its record: manifest digest, gate result and the diff against the host."""
    import tomllib
    if dest.exists():
        raise FileExistsError(str(dest))
    dest.mkdir(parents=True, mode=0o700)
    host = CODEX_HOME_REAL
    copied, linked = {}, {}
    for name in COPY:
        src = host / name
        if src.exists():
            shutil.copy2(src, dest / name)
            os.chmod(dest / name, 0o600)
            copied[name] = sha256_file(src)
    if (host / "rules").is_dir():
        shutil.copytree(host / "rules", dest / "rules")
        copied["rules/"] = sha256_json({p.name: sha256_file(p) for p in sorted((host / "rules").iterdir()) if p.is_file()})
    for name in SYMLINK:
        if (host / name).exists():
            os.symlink(host / name, dest / name)
            linked[name] = str(host / name).replace(str(HOME), "~")
    if arm == "env":
        shutil.copy2(host / "AGENTS.md", dest / "AGENTS.md")
        os.chmod(dest / "AGENTS.md", 0o600)
        copied["AGENTS.md"] = sha256_file(host / "AGENTS.md")
    original = (dest / "config.toml").read_text(encoding="utf-8")
    patched = insert_gh_config_dir(original, str(gh_dir))
    (dest / "config.toml").write_text(patched, encoding="utf-8")
    parsed = tomllib.loads(patched)
    gh_ok = ((parsed.get("shell_environment_policy") or {}).get("set") or {}).get("GH_CONFIG_DIR") == str(gh_dir)
    (dest / "rules").mkdir(exist_ok=True)
    (dest / "rules" / "organic-e2e.rules").write_text(rules_text, encoding="utf-8")
    added_lines = [l for l in patched.splitlines() if l not in original.splitlines()]
    gate = {
        "agents_md_absent": not (dest / "AGENTS.md").exists() if arm == "native" else None,
        "agents_md_matches_host": (sha256_file(dest / "AGENTS.md") == sha256_file(host / "AGENTS.md")) if arm == "env" else None,
        "config_only_adds_gh_config_dir": added_lines == [f'GH_CONFIG_DIR = {json.dumps(str(gh_dir))}'] and gh_ok,
        "copies_match_host": all(sha256_file(dest / n) == sha256_file(host / n) for n in COPY if n != "config.toml" and (host / n).exists()),
        "symlinks": sorted(linked) == sorted(n for n in SYMLINK if (host / n).exists()),
        "no_login_or_state": not any((dest / n).exists() for n in ("auth.json", "history.jsonl", "state_5.sqlite",
                                                                    "queue_1.sqlite", "memories_1.sqlite", "goals_1.sqlite")),
    }
    gate["pass"] = all(v for v in gate.values() if v is not None)
    manifest = tree_manifest(dest)
    return {"arm": arm, "copied": copied, "linked": linked, "gate": gate, "manifest_sha256": sha256_json(manifest),
            "config_sha256": sha256_bytes(patched.encode()), "rules_sha256": sha256_bytes(rules_text.encode())}
