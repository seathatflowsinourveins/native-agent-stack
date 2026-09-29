#!/usr/bin/env python3
"""Read-only refresh of the upstream landscape behind docs/decisions/2026-09-28-terminal-experience.md (needs `gh` signed in).

Prints one JSON summary: Windows Terminal releases and the two toast signals (does a release tag's BellStyle enum carry
"notification", and does `compare` report the OSC 777 merge commit as an ancestor); the newest Claude Code and Codex releases; how
many lines of Codex's notification, palette and config sources differ between the installed tag and the newest stable tag; the
candidate notifiers' heads and latest releases against the pins the decision recorded; and the public Claude Code issues about the
placeholder files that CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 leaves behind. It only reads; it never files or comments.
usage: python3 -B landscape_refresh.py [--installed-codex rust-v0.157.1]
"""
import difflib, json, re, subprocess, sys

INSTALLED_CODEX = sys.argv[sys.argv.index("--installed-codex") + 1] if "--installed-codex" in sys.argv else "rust-v0.157.1"
TOAST_MERGE_BASE = "93bdbfaa3d62304f4b50b4ca4484da4dd08e4a1f"   # the merge commit of microsoft/terminal#20012 (OSC 777)
CANDIDATES = {  # repository -> pin recorded in the decision (short head, latest release where one was recorded)
    "DevinoSolutions/anotifier-for-claude-codex-cursor": ("92c080a7", "v1.2.6"), "777genius/agent-notifications": ("0376f9c9", "v1.45.18"),
    "congmnguyen/claude-code-wsl2-setup": ("69620ec4", "v1.0.0"), "shanselman/toasty": ("973eeb8d", "v0.8.1"),
    "PeonPing/peon-ping": ("8ef37660", None), "mylee04/code-notify": ("dcfd4ae6", None), "asheshgoplani/agent-deck": ("035fd602", None),
    "kbwo/ccmanager": ("ee0af836", None), "zellij-org/zellij": ("a79e15e1", "v0.45.1"),
}
CODEX_FILES = ["codex-rs/tui/src/chatwidget/notifications.rs", "codex-rs/tui/src/notifications/mod.rs", "codex-rs/tui/src/terminal_palette.rs",
               "codex-rs/config/src/types.rs"]
ISSUE_QUERIES = ["bash_profile sandbox", "\"mount point\" sandbox empty file", "SUBPROCESS_ENV_SCRUB leftover", "sandbox leaves empty .zshrc"]
ISSUES = [76236, 78072, 94008, 81602, 83497]


def gh(path, raw=False, params=None):
    argv = ["gh", "api"] + (["-X", "GET"] if params else []) + [path] + (["-H", "Accept: application/vnd.github.raw"] if raw else [])
    for key, value in (params or {}).items():
        argv += ["-f", f"{key}={value}"]
    run = subprocess.run(argv, capture_output=True, text=True, timeout=90)
    if run.returncode:
        return None
    return run.stdout if raw else json.loads(run.stdout)


def bellstyle_has_notification(tag):
    schema = gh(f"repos/microsoft/terminal/contents/doc/cascadia/profiles.schema.json?ref={tag}", raw=True)
    if schema is None:
        return None
    data = json.loads(schema)
    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("enum"), list) and "taskbar" in node["enum"]:
                yield "notification" in node["enum"]
            for value in node.values():
                yield from walk(value)
        elif isinstance(node, list):
            for value in node:
                yield from walk(value)
    return any(walk(data))


def main():
    out = {}
    terminal = gh("repos/microsoft/terminal/releases?per_page=6") or []
    stable = next((r["tag_name"] for r in terminal if not r["prerelease"]), None)
    preview = next((r["tag_name"] for r in terminal if r["prerelease"]), None)
    out["windows_terminal"] = {"releases": [(r["tag_name"], r["prerelease"], r["published_at"][:10]) for r in terminal],
                               "toast_signals": {}}
    for label, tag in (("stable", stable), ("preview", preview)):
        compare = gh(f"repos/microsoft/terminal/compare/{TOAST_MERGE_BASE}...{tag}")
        out["windows_terminal"]["toast_signals"][label] = {
            "tag": tag, "bellstyle_enum_has_notification": bellstyle_has_notification(tag), "ancestry_status": compare["status"] if compare else None}
    claude = gh("repos/anthropics/claude-code/releases?per_page=3") or []
    out["claude_code"] = [(r["tag_name"], r["published_at"][:16]) for r in claude]
    codex = [r for r in (gh("repos/openai/codex/releases?per_page=8") or []) if not r["prerelease"]]
    newest = codex[0]["tag_name"] if codex else None
    out["codex"] = {"installed_tag": INSTALLED_CODEX, "newest_stable": (newest, codex[0]["published_at"][:16]) if codex else None, "source_diff_changed_lines": {}}
    for path in CODEX_FILES:
        a = gh(f"repos/openai/codex/contents/{path}?ref={INSTALLED_CODEX}", raw=True)
        b = gh(f"repos/openai/codex/contents/{path}?ref={newest}", raw=True)
        if a is None or b is None:
            out["codex"]["source_diff_changed_lines"][path] = None
            continue
        delta = [l for l in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        out["codex"]["source_diff_changed_lines"][path] = len(delta)
    types_old = gh(f"repos/openai/codex/contents/codex-rs/config/src/types.rs?ref={INSTALLED_CODEX}", raw=True) or ""
    types_new = gh(f"repos/openai/codex/contents/codex-rs/config/src/types.rs?ref={newest}", raw=True) or ""
    def definitions(text):
        enum = re.search(r"pub enum Notifications \{[^}]*\}", text)
        fields = re.findall(r"pub (?:terminal_title|notification_method|notification_condition): [^\n]*", text)
        return (re.sub(r"\s+", " ", enum.group(0)) if enum else None, fields)
    out["codex"]["notification_definitions_identical"] = definitions(types_old) == definitions(types_new) and definitions(types_old)[0] is not None
    notifications = gh(f"repos/openai/codex/contents/{CODEX_FILES[0]}?ref={newest}", raw=True) or ""
    out["codex"]["notification_kind_literals_at_newest"] = sorted(set(re.findall(r'=> "([a-z-]+)"', notifications)))
    out["candidates"] = {}
    for repo, (pin, release) in CANDIDATES.items():
        meta = gh(f"repos/{repo}")
        head = gh(f"repos/{repo}/commits/{meta['default_branch']}") if meta else None
        latest = gh(f"repos/{repo}/releases/latest")
        out["candidates"][repo] = {"head": head["sha"][:8] if head else None, "pin_unchanged": bool(head) and head["sha"].startswith(pin),
                                   "latest_release": latest["tag_name"] if latest else None, "archived": meta["archived"] if meta else None}
    reported = {}
    for query in ISSUE_QUERIES:
        found = gh("search/issues", params={"q": f"repo:anthropics/claude-code {query}", "per_page": 8}) or {"items": []}
        for item in found["items"]:
            reported[item["number"]] = item
    out["claude_code_issues"] = {}
    for number in ISSUES:
        item = gh(f"repos/anthropics/claude-code/issues/{number}")
        if item:
            out["claude_code_issues"][number] = {"state": item["state"], "state_reason": item.get("state_reason"), "created": item["created_at"][:10],
                                                  "closed": (item.get("closed_at") or "")[:10] or None, "found_by_search": number in reported}
    out["claude_code_changelog_sandbox_stub_entries"] = None
    changelog = gh("repos/anthropics/claude-code/contents/CHANGELOG.md", raw=True)
    if changelog is not None:
        out["claude_code_changelog_top_version"] = re.search(r"^## (\d+\.\d+\.\d+)", changelog, re.M).group(1)
        entries, version = [], None
        for line in changelog.splitlines():
            heading = re.match(r"^## (\d+\.\d+\.\d+)", line)
            if heading:
                version = heading.group(1)
            elif re.search(r"sandbox|SUBPROCESS_ENV_SCRUB|bwrap|bubblewrap", line, re.I) and re.search(
                    r"placeholder|empty (regular )?file|stub|mount point|mask file|clean ?up|left behind|leftover|0-byte|\.lock", line, re.I):
                entries.append((version, line.strip("- ").strip()[:150]))
        out["claude_code_changelog_sandbox_stub_entries"] = entries
    print(json.dumps(out, indent=2, default=list))


if __name__ == "__main__":
    main()
