#!/usr/bin/env python3
"""Read-only refresh of the upstream landscape behind docs/decisions/2026-09-28-terminal-experience.md (needs `gh` signed in).

Prints one JSON summary: Windows Terminal releases and the two toast signals (does a release tag's BellStyle enum carry
"notification", and does `compare` report the OSC 777 merge commit as an ancestor); the newest Claude Code and Codex releases; how
many lines of Codex's notification, palette and config sources differ between the installed tag and the newest stable tag; the
candidate notifiers' heads and latest releases against the pins the decision recorded; and the public Claude Code issues about the
placeholder files that CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 leaves behind. It only reads; it never files or comments.
usage: python3 -B landscape_refresh.py [--installed-codex rust-v0.157.1] | --selftest      (--selftest needs neither gh nor a network)

Revised 2026-09-30 after a cross-family review: see definitions() and bellstyle_from_schema(): an anchor that is not found is null (unknown), never False or "identical".
"""
import difflib, json, re, subprocess, sys

INSTALLED_CODEX = sys.argv[sys.argv.index("--installed-codex") + 1] if "--installed-codex" in sys.argv else "rust-v0.157.1"
TOAST_MERGE_BASE = "93bdbfaa3d62304f4b50b4ca4484da4dd08e4a1f"   # the merge commit of microsoft/terminal#20012 (OSC 777)
# repository -> (short head, latest release) recorded when this script first ran, 2026-09-29. Six of them were pins the decision's table
# already carried; BASELINES were first recorded here, so for them "unchanged" has nothing earlier to compare with and reads null.
CANDIDATES = {
    "DevinoSolutions/anotifier-for-claude-codex-cursor": ("92c080a7", "v1.2.6"), "777genius/agent-notifications": ("0376f9c9", "v1.45.18"),
    "congmnguyen/claude-code-wsl2-setup": ("69620ec4", "v1.0.0"), "shanselman/toasty": ("973eeb8d", "v0.8.1"),
    "PeonPing/peon-ping": ("8ef37660", None), "mylee04/code-notify": ("dcfd4ae6", None), "asheshgoplani/agent-deck": ("035fd602", None),
    "kbwo/ccmanager": ("ee0af836", None), "zellij-org/zellij": ("a79e15e1", "v0.45.1"),
}
BASELINES = {"asheshgoplani/agent-deck", "kbwo/ccmanager", "zellij-org/zellij"}
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
    return bellstyle_from_schema(json.loads(schema))


def bellstyle_from_schema(data):
    """True when an enum that holds "taskbar" (the BellStyle values) also holds "notification"; False when such an enum exists without it; None when no such enum was found."""
    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("enum"), list) and "taskbar" in node["enum"]:
                yield "notification" in node["enum"]
            for value in node.values():
                yield from walk(value)
        elif isinstance(node, list):
            for value in node:
                yield from walk(value)
    results = list(walk(data))
    return any(results) if results else None


ATTRIBUTES = r"((?:[ \t]*#\[(?:[^\[\]]|\[[^\]]*\])*\][ \t]*\n|[ \t]*///[^\n]*\n)*)"   # attributes (a bracket group may span lines and hold one nested bracket) and doc comments in front of an item


def normalized(text):
    """Whitespace runs become one space and the spaces next to punctuation go, so re-wrapping an attribute over several lines is not a change while any changed token is."""
    return re.sub(r"\s*([(){}\[\],;:=<>])\s*", r"\1", re.sub(r"\s+", " ", text)).strip()


def definitions(text):
    """The parts of codex-rs/config/src/types.rs that define the TUI notification and terminal-title settings, whole (attributes, which may span lines, and doc comments included) with whitespace
    normalized: the Notifications, NotificationMethod and NotificationCondition enums, the TuiNotificationSettings struct, the Display impls of the two enums, the Default impl of Notifications (what
    `notifications` is when the key is absent) and the `terminal_title` field of Tui. A part that is not found is None."""
    found = {}
    for kind, name in (("enum", "Notifications"), ("enum", "NotificationMethod"), ("enum", "NotificationCondition"), ("struct", "TuiNotificationSettings")):
        match = re.search(ATTRIBUTES + "pub " + kind + " " + name + r" \{.*?\n\}", text, re.S)
        found[name] = normalized(match.group(0)) if match else None
    for name in ("NotificationMethod", "NotificationCondition"):
        match = re.search(r"impl fmt::Display for " + name + r" \{.*?\n\}", text, re.S)
        found[name + " Display"] = normalized(match.group(0)) if match else None
    match = re.search(r"impl Default for Notifications \{.*?\n\}", text, re.S)
    found["Notifications Default"] = normalized(match.group(0)) if match else None
    match = re.search(ATTRIBUTES + r"[ \t]*pub terminal_title:[^\n]*\n", text)
    found["Tui terminal_title"] = normalized(match.group(0)) if match else None
    return found


def definitions_identical(old, new):
    """True or False when every part was found in both texts; None (unknown) when any part is missing from either."""
    first, second = definitions(old), definitions(new)
    if any(value is None for value in first.values()) or any(value is None for value in second.values()):
        return None
    return first == second


SYNTHETIC = """
#[derive(Serialize, Debug, Clone, PartialEq, Eq, Deserialize, JsonSchema)]
#[serde(untagged)]
pub enum Notifications {
    Enabled(bool),
    Custom(Vec<String>),
}

impl Default for Notifications {
    fn default() -> Self {
        Self::Enabled(true)
    }
}

#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, JsonSchema, Default)]
#[serde(rename_all = "lowercase")]
pub enum NotificationMethod {
    #[default]
    Auto,
    Osc9,
    Bel,
}

impl fmt::Display for NotificationMethod {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            NotificationMethod::Auto => write!(f, "auto"),
        }
    }
}

#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, JsonSchema, Default)]
#[serde(rename_all = "lowercase")]
pub enum NotificationCondition {
    /// Emit TUI notifications only while the terminal is unfocused.
    #[default]
    Unfocused,
    Always,
}

impl fmt::Display for NotificationCondition {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            NotificationCondition::Unfocused => write!(f, "unfocused"),
        }
    }
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq, Default, JsonSchema)]
#[schemars(deny_unknown_fields)]
pub struct TuiNotificationSettings {
    #[serde(default, rename = "notifications")]
    pub notifications: Notifications,
    #[serde(default, rename = "notification_method")]
    pub method: NotificationMethod,
    #[serde(default, rename = "notification_condition")]
    pub condition: NotificationCondition,
}

/// Collection of settings that are specific to the TUI.
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Default, JsonSchema)]
#[schemars(deny_unknown_fields)]
pub struct Tui {
    #[serde(default, flatten)]
    pub notification_settings: TuiNotificationSettings,
    /// Ordered terminal title items.
    /// When unset, the TUI defaults to: `activity`, `thread-name`, and `project-name`.
    #[serde(default)]
    pub terminal_title: Option<Vec<String>>,
}
"""

WRAPPED = SYNTHETIC.replace('#[serde(rename_all = "lowercase")]\npub enum NotificationMethod', '#[serde(\n    rename_all = "lowercase"\n)]\npub enum NotificationMethod')
WRAPPED_DERIVE = SYNTHETIC.replace('#[derive(Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, JsonSchema, Default)]\n#[serde(rename_all = "lowercase")]\npub enum NotificationMethod',
                                   '#[derive(\n    Serialize, Deserialize, Debug, Clone, Copy, PartialEq, Eq, JsonSchema, Default\n)]\n#[serde(rename_all = "lowercase")]\npub enum NotificationMethod')


def selftest():
    problems = []
    checks = [
        ("identical text is identical", definitions_identical(SYNTHETIC, SYNTHETIC), True),
        ("a new NotificationMethod variant is seen", definitions_identical(SYNTHETIC, SYNTHETIC.replace("    Bel,\n}", "    Bel,\n    Toast,\n}")), False),
        ("a new NotificationCondition variant is seen", definitions_identical(SYNTHETIC, SYNTHETIC.replace("    Always,\n}", "    Always,\n    Never,\n}")), False),
        ("a changed default variant of the method is seen", definitions_identical(SYNTHETIC, SYNTHETIC.replace("#[default]\n    Auto,", "Auto,").replace("    Osc9,", "    #[default]\n    Osc9,")), False),
        ("a new struct field is seen", definitions_identical(SYNTHETIC, SYNTHETIC.replace("    pub condition: NotificationCondition,", "    pub condition: NotificationCondition,\n    pub extra: bool,")), False),
        ("a changed default of `notifications` is seen", definitions_identical(SYNTHETIC, SYNTHETIC.replace("Self::Enabled(true)", "Self::Enabled(false)")), False),
        ("a missing Default impl is unknown, not identical", definitions_identical(SYNTHETIC, SYNTHETIC.replace("impl Default for Notifications", "impl Default for Renamed")), None),
        ("a changed terminal_title default in its doc comment is seen", definitions_identical(SYNTHETIC, SYNTHETIC.replace("and `project-name`", "and `branch`")), False),
        ("a changed terminal_title type is seen", definitions_identical(SYNTHETIC, SYNTHETIC.replace("Option<Vec<String>>", "Option<String>")), False),
        ("a missing terminal_title is unknown, not identical", definitions_identical(SYNTHETIC, SYNTHETIC.replace("pub terminal_title", "pub renamed_title")), None),
        ("a changed rename_all in a one-line serde attribute is seen",
         definitions_identical(SYNTHETIC, SYNTHETIC.replace('#[serde(rename_all = "lowercase")]\npub enum NotificationMethod', '#[serde(rename_all = "UPPERCASE")]\npub enum NotificationMethod')), False),
        ("a wrapped derive that loses Default is seen", definitions_identical(WRAPPED_DERIVE, WRAPPED_DERIVE.replace("JsonSchema, Default\n)]\n#[serde(rename_all = \"lowercase\")]\npub enum NotificationMethod",
                                                                                                                  "JsonSchema\n)]\n#[serde(rename_all = \"lowercase\")]\npub enum NotificationMethod")), False),
        ("a serde attribute re-wrapped over several lines is not a change", definitions_identical(SYNTHETIC, WRAPPED), True),
        ("a changed rename_all inside a multi-line serde attribute is seen",
         definitions_identical(WRAPPED, WRAPPED.replace('rename_all = "lowercase"\n)]\npub enum NotificationMethod', 'rename_all = "UPPERCASE"\n)]\npub enum NotificationMethod')), False),
        ("a changed Display text is seen", definitions_identical(SYNTHETIC, SYNTHETIC.replace('write!(f, "auto")', 'write!(f, "automatic")')), False),
        ("a missing definition is unknown, not identical", definitions_identical(SYNTHETIC, SYNTHETIC.replace("pub enum NotificationCondition", "pub enum RenamedCondition")), None),
        ("the same text with only whitespace changes is identical", definitions_identical(SYNTHETIC, SYNTHETIC.replace("    ", "  ")), True),
        ("a BellStyle enum with notification", bellstyle_from_schema({"a": {"enum": ["audible", "taskbar", "notification"]}}), True),
        ("a BellStyle enum without notification", bellstyle_from_schema({"a": {"enum": ["audible", "taskbar"]}}), False),
        ("a schema with the word notification but no taskbar enum is unknown", bellstyle_from_schema({"a": {"enum": ["notification", "window"]}, "b": {"enum": ["audible", "window"]}}), None),
    ]
    for label, got, expected in checks:
        if got is not expected:
            problems.append(f"{label}: got {got!r}, expected {expected!r}")
    print(json.dumps({"selftest_checks": len(checks), "problems": problems}))
    return 1 if problems else 0


def main():
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
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
    out["codex"]["notification_definitions_identical"] = definitions_identical(types_old, types_new)
    notifications = gh(f"repos/openai/codex/contents/{CODEX_FILES[0]}?ref={newest}", raw=True) or ""
    out["codex"]["notification_kind_literals_at_newest"] = sorted(set(re.findall(r'=> "([a-z-]+)"', notifications)))
    out["candidates"] = {}
    for repo, (pin, release) in CANDIDATES.items():
        meta = gh(f"repos/{repo}")
        head = gh(f"repos/{repo}/commits/{meta['default_branch']}") if meta else None
        latest = gh(f"repos/{repo}/releases/latest")
        out["candidates"][repo] = {"head": head["sha"][:8] if head else None,
                                   "pin_unchanged": None if repo in BASELINES else bool(head) and head["sha"].startswith(pin),
                                   "baseline_first_recorded_by_this_script": repo in BASELINES,
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
    out["claude_code_changelog_scrub_variable_entries"] = None
    changelog = gh("repos/anthropics/claude-code/contents/CHANGELOG.md", raw=True)
    if changelog is not None:
        out["claude_code_changelog_top_version"] = re.search(r"^## (\d+\.\d+\.\d+)", changelog, re.M).group(1)
        entries, scrub_entries, version = [], [], None
        for line in changelog.splitlines():
            heading = re.match(r"^## (\d+\.\d+\.\d+)", line)
            if heading:
                version = heading.group(1)
            elif re.search(r"sandbox|SUBPROCESS_ENV_SCRUB|bwrap|bubblewrap", line, re.I) and re.search(
                    r"placeholder|empty (regular )?file|stub|mount point|mask file|clean ?up|left behind|leftover|0-byte|\.lock|dotfile|ghost", line, re.I):
                entries.append((version, line.strip("- ").strip()[:150]))
            if "SUBPROCESS_ENV_SCRUB" in line:
                scrub_entries.append((version, line.strip("- ").strip()[:150]))
        out["claude_code_changelog_sandbox_stub_entries"] = entries
        out["claude_code_changelog_scrub_variable_entries"] = scrub_entries
    print(json.dumps(out, indent=2, default=list))


if __name__ == "__main__":
    main()
