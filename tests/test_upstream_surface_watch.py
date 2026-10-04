"""scripts/upstream_surface_watch.py against synthetic reduced fixtures (local integration checks, not upstream tests).

Every upstream artifact here is a small synthetic stand-in shaped like the real one (npm dist-tags and packument, the
Agent SDK's sdk.d.ts, the env-vars and mods pages, the Codex release JSON and config-schema.json, `codex features
list`, CHANGELOG.md, the GraphQL release list); none is a recorded observation. A fake replaces the network layer
(http_get, gh_api, probe_codex), and the offline tests make socket creation raise. NegativeControlTests run small mutant
parsers, each with a known defect and none built by filtering the real parser's output, and require every mutant to
agree with the real parser on a plain fixture and fail a fixture that the real parser passes, so a parser regression
cannot pass silently (precedent: a regex that missed `$` in minified identifiers read 15 of 17 values with exit 0).
TestCommittedCatalogs checks the two committed catalogs. CachedArtifactTests optionally reads real vendor artifacts
from UPSTREAM_SURFACE_TEST_CACHE (or the default watch cache); those are local integration checks, not upstream tests.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts import currency_due as cd
from scripts import upstream_surface_watch as usw

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-04T12:00:00Z"
CODEX_BIN = "/synthetic/bin/codex"


def cached_artifact(test: unittest.TestCase, source: str) -> bytes:
    """Read optional real upstream inputs for local integration checks, never upstream tests.
    UPSTREAM_SURFACE_TEST_CACHE selects a read-only cache copy; ordinary fixture tests need no cache."""
    cache = Path(os.environ.get("UPSTREAM_SURFACE_TEST_CACHE", usw.default_state_dir() / usw.CACHE_DIR))
    path = cache / f"{source}.body"
    if not path.is_file():
        test.skipTest(f"cached upstream input unavailable: {source}; set UPSTREAM_SURFACE_TEST_CACHE")
    return path.read_bytes()

# ----------------------------------------------------------------------------------------------- fixture builders

FILLER_SETTINGS = [f"fillerSetting{index:02d}" for index in range(60)]
TRAP_SETTINGS = ["$schema", "quoted-key", "double-quoted", "recordOfArrays", "mapOfSets", "recordOfPartials",
                 "newlineFirst", "newlineSecond", "unionAcrossLines", "genericOnNextLine", "afterGeneric",
                 "policyHelper", "afterNested", "literal", "onEvent", "frozen", "readonly", "conditional", "resolve"]
HOOKS = ["PreToolUse", "PostToolUse", "Notification", "UserPromptSubmit", "SessionStart", "SessionEnd", "Stop",
         "SubagentStart", "SubagentStop", "PreCompact", "PostCompact", "ConfigChange"]
MODS = ["cc-plugin-agents-md", "cc-plugin-diff", "cc-plugin-you-should-know", "cc-plugin-alpha", "cc-plugin-beta",
        "cc-plugin-gamma"]  # six, as the real overview page lists
ENV_NAMES = [f"CLAUDE_CODE_SYNTHETIC_{index:03d}" for index in range(110)]
FEATURES = {f"feature_{index:02d}": (("under development", "stable", "removed")[index % 3], index % 3 == 1)
            for index in range(40)}
CLAUDE_TAGS = {"stable": "2.1.285", "latest": "2.1.289", "next": "2.1.289"}
CODEX_TAGS = {"latest": "0.160.0", "alpha": "0.162.0-alpha.12", "linux-x64": "0.160.0-linux-x64"}

# The traps: braces and "word:" text inside JSDoc, `$` and quoted keys, commas inside type arguments (<...>), a
# construct signature, members that end at a line break (after a complete type, never after ':' or '|'), a multi-line
# union and a type on the line after its colon, a nested object type followed by more keys, a string literal holding }
# and ;, a template literal type, a function type with an object parameter, modifiers, an index signature, a
# conditional type and a method. An indented interface of the same name inside a namespace and a longer interface
# name must not count.
TRAP_INTERFACE = """/**
 * AUTO-GENERATED - DO NOT EDIT
 *
 * This file is auto-generated from the settings JSON schema.
 */
export declare interface Settings {
    /**
     * JSON Schema reference. Example: { "nested": true }; key: value
     */
    $schema?: string;
    'quoted-key'?: boolean;
    "double-quoted"?: number;
    recordOfArrays?: Record<string, Array<string>>;
    mapOfSets?: Map<string, Set<number>>;
    recordOfPartials?: Record<string, Partial<Foo>>;
    new (x: string): Foo;
    newlineFirst: string
    newlineSecond: number
    unionAcrossLines?:
        | Array<string>
        | Map<string, number>
    genericOnNextLine?:
        Partial<Foo>
    afterGeneric?: boolean;
    /**
     * Executable that computes managed settings.
     */
    policyHelper?: {
        /**
         * Absolute path to the helper executable
         */
        path: string;
        timeoutMs?: number;
        refresh?: {
            intervalMs: number;
        };
    };
    /** Default: false */
    afterNested?: string;
    literal?: 'a}b' | "c;d" | `x${string}}y`;
    onEvent?: (event: string, detail: { kind: string }) => void;
    readonly frozen?: boolean;
    readonly?: boolean;
    [k: string]: unknown;
    conditional?: Base extends Other ? Yes : No;
    resolve(name: string): string;
@FILLER@
}
declare namespace Inner {
    interface Settings {
        innerOnly?: string;
    }
}
export declare interface SettingsSchemaOther {
    notASettingsKey?: string;
}
"""
PLAIN_INTERFACE = """export declare interface Settings {
@FILLER@
}
"""


def filler(names, comments=True) -> str:
    return "\n".join(("    /** Filler setting */\n" if comments else "") + f"    {name}?: string;" for name in names)


def sdk_dts(settings_extra=(), hooks=HOOKS, interface=TRAP_INTERFACE, settings=True, hook_events=True,
            multiline_hooks=True, comments=True) -> str:
    parts = ["/** Agent SDK declarations (synthetic fixture). */",
             "export declare type HookEvent = (typeof HOOK_EVENTS)[number];",
             "export {\n    HOOK_EVENTS,\n    Settings\n};"]
    if hook_events:
        if multiline_hooks:
            listed = ",\n    ".join(f'"{name}"' if index % 2 else f"'{name}'" for index, name in enumerate(hooks))
            parts.append(f"export declare const HOOK_EVENTS: readonly [\n    {listed}, // the last event\n    /* end */\n];")
        else:
            parts.append("export declare const HOOK_EVENTS: readonly [" + ", ".join(f"'{name}'" for name in hooks) + "];")
    if settings:
        parts.append(interface.replace("@FILLER@", filler([*FILLER_SETTINGS, *settings_extra], comments)))
    return "\n".join(parts) + "\n"


REFERENCE_KEYS = [*FILLER_SETTINGS, "docsOnlySetting"]


def reference_page(keys=REFERENCE_KEYS, title=True, global_section=True) -> str:
    """settings-reference.md shaped like the real page: its title, "## " sections of "### `key`" entries (a Scope
    bullet and a fenced example each), a dotted heading, a removed and a deprecated entry, a Global config key outside
    its section, fenced lines that look like headings, and the `## Global config settings` section, whose keys are
    not settings keys. It documents ``keys`` plus fillerSetting00 (dotted) and deprecatedSetting."""
    def entry(key: str, scope: str = "Any file", warning: str | None = None) -> list[str]:
        lines = [f"### `{key}`", ""]
        if warning:
            lines += ["<Warning>", f"  {warning}", "</Warning>", ""]
        return lines + ["A synthetic setting.", "", f"* **Scope**: [`{scope}`](#scopes)", "* **Type**: Boolean", "",
                        "```json settings.json theme={null}", "{", f'  "{key}": true', "}", "```", ""]

    indexed = [*keys, "fillerSetting00.nested", "removedSetting", "deprecatedSetting", "scopeMarkedElsewhere"]
    if global_section:
        indexed += ["globalOnlyKey", "sectionOnlyGlobal"]
    lines = ["> ## Documentation Index", "", "# All settings" if title else "# Something else", "",
             "## Settings index", "", "| Key | Description | Topic | Scope |", "| :- | :- | :- | :- |",
             *(f"| [`{key}`](#{key.lower()}) | A synthetic setting | Settings | Any file |" for key in indexed),
             "", "## Model and responses", ""]
    for key in keys:
        lines += entry(key)
    lines += entry("fillerSetting00.nested")
    lines += entry("removedSetting", warning="Removed in v2.1.200, together with the tool it sized.")
    lines += entry("deprecatedSetting", warning="Deprecated since v2.1.100. Claude Code still reads it.")
    lines += entry("scopeMarkedElsewhere", scope="Global config")
    lines += ["```text", "## Not a section", "### `fencedFake`", "```", ""]
    if global_section:
        lines += ["## Global config settings", "", "Save these keys in `~/.claude.json`, not in a settings file.", ""]
        lines += entry("globalOnlyKey", scope="Global config")
        lines += entry("sectionOnlyGlobal")  # in the section, whatever its Scope bullet says
        lines += ["```text", "# a comment line of an example", "```", ""]
    return "\n".join([*lines, "## See also", "", "- [Settings](/docs/en/settings)", ""])


def env_page(extra=(), heading=True, names=ENV_NAMES) -> str:
    lines = ["# Environment variables" if heading else "# Something else", "", "## Variables", ""]
    lines += [f"- `{name}`: a synthetic variable." for name in [*names, *extra]]
    lines += ["", "Set `CLAUDECODE` to detect a nested session. Sizes take `K` or `M`; `OTEL_` is a prefix.",
              "An assignment `FOO_BAR=1` and a `lowercase_name` are not names.", "", "```bash",
              "export NOT_BACKTICKED_NAME=1", "```", ""]
    return "\n".join(lines)


def mods_page(mods=MODS, heading=True) -> str:
    title = "## Mods built into Claude Code" if heading else "## Something else"
    return ("# Mods overview\n\n" + title + "\n\n" + "\n".join(f"| `{name}` | synthetic |" for name in mods)
            + f"\n\nRead https://example.com/source/{mods[0]}/ and {mods[-1]}.\n")


def codex_schema(extra_top=(), features=None) -> dict:
    names = features or [f"feature_{index:02d}" for index in range(25)]
    properties = {f"top_{index:02d}": {"type": "string"} for index in range(35)}
    properties.update({name: {"type": "boolean"} for name in extra_top})
    properties["features"] = {"type": "object", "additionalProperties": False,
                              "properties": {name: {"type": "boolean"} for name in names}}
    properties["tui"] = {"$ref": "#/definitions/Tui"}
    properties["mcp_servers"] = {"type": "object", "additionalProperties": {"$ref": "#/definitions/McpServer"}}
    properties["hooks"] = {"type": "object", "properties": {
        "PreToolUse": {"type": "array", "items": {"$ref": "#/definitions/HookGroup"}}}}
    properties["model"] = {"anyOf": [{"$ref": "#/definitions/Model"}, {"type": "null"}]}
    properties["bulk"] = {"type": "object", "properties": {f"entry_{index:03d}": {"type": "integer"}
                                                           for index in range(150)}}
    # Named profiles repeat root keys (ConfigProfile); only profile_only is a profile's own key.
    properties["profiles"] = {"type": "object", "additionalProperties": {"$ref": "#/definitions/Profile"}}
    definitions = {
        "Profile": {"type": "object", "properties": {
            "top_00": {"type": "string"}, "tui": {"$ref": "#/definitions/Tui"}, "profile_only": {"type": "boolean"},
            "features": {"type": "object", "properties": {name: {"type": "boolean"} for name in names}}}},
        "Tui": {"type": "object", "properties": {"theme": {"type": "string"},
                                                 "notifications": {"allOf": [{"$ref": "#/definitions/Note"}]}}},
        "Note": {"type": "object", "properties": {"enabled": {"type": "boolean"}}},
        "McpServer": {"type": "object", "properties": {"command": {"type": "string"},
                                                       "env": {"type": "object",
                                                               "additionalProperties": {"type": "string"}}}},
        "HookGroup": {"type": "object", "properties": {"matcher": {"type": "string"},
                                                       "hooks": {"type": "array", "items": {"$ref": "#/definitions/Hook"}}}},
        "Hook": {"type": "object", "properties": {"command": {"type": "string"}, "timeout": {"type": "integer"}}},
        "Model": {"type": "object", "properties": {"name": {"type": "string"}, "fallback": {"$ref": "#/definitions/Model"}}},
    }
    return {"$schema": "http://json-schema.org/draft-07/schema#", "title": "ConfigToml", "type": "object",
            "properties": properties, "definitions": definitions}


def real_shaped_schema() -> dict:
    """codex_schema() reshaped like the real config-schema.json of rust-v0.160.0, where most paths sit behind a $ref
    inside an anyOf (schemars' Option<T>): read without its definitions the real one gives 266 of its 1,341 paths, and
    without allOf/anyOf/oneOf 553. Here 20 sections of 40 keys each sit behind such a reference."""
    schema = codex_schema()
    for index in range(20):
        schema["definitions"][f"Section{index:02d}"] = {"type": "object", "properties": {
            f"key_{key:02d}": {"type": "string"} for key in range(40)}}
        schema["properties"][f"section_{index:02d}"] = {"anyOf": [{"$ref": f"#/definitions/Section{index:02d}"},
                                                                  {"type": "null"}]}
    schema["properties"]["bulk"]["properties"].update({f"entry_{index:03d}": {"type": "integer"}
                                                       for index in range(150, 250)})
    return schema


def without_combinators(node):
    if isinstance(node, dict):
        return {key: without_combinators(value) for key, value in node.items()
                if key not in ("allOf", "anyOf", "oneOf")}
    return [without_combinators(item) for item in node] if isinstance(node, list) else node


def env_table_page(names) -> str:
    """env-vars.md shaped like the real page: its title and one table row per variable."""
    return "\n".join(["# Environment variables", "", "| Variable | Purpose |", "| :- | :- |",
                      *(f"| `{name}` | a synthetic variable |" for name in names), ""])


STRUCTURED_PATHS = {"features", "tui", "tui.theme", "tui.notifications", "tui.notifications.enabled", "mcp_servers",
                    "mcp_servers.*.command", "mcp_servers.*.env", "hooks", "hooks.PreToolUse",
                    "hooks.PreToolUse[].matcher", "hooks.PreToolUse[].hooks", "hooks.PreToolUse[].hooks[].command",
                    "hooks.PreToolUse[].hooks[].timeout", "model", "model.name", "model.fallback", "bulk", "profiles",
                    "profiles.*.profile_only"}


def expected_paths(extra_top=()) -> set[str]:
    return (STRUCTURED_PATHS | {f"top_{index:02d}" for index in range(35)} | set(extra_top)
            | {f"features.feature_{index:02d}" for index in range(25)}
            | {f"bulk.entry_{index:03d}" for index in range(150)})


def features_list(features) -> str:
    return "\n".join(f"{name:<40} {stage:<18} {'true' if enabled else 'false'}"
                     for name, (stage, enabled) in sorted(features.items())) + "\n"


def changelog(sections) -> str:
    return "# Changelog\n\n" + "\n".join(f"## {version}\n\n" + "\n".join(f"- {entry}" for entry in entries) + "\n"
                                         for version, entries in sections)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Upstream:
    """The synthetic upstream that the fake network layer answers from; each test changes what it needs."""

    def __init__(self):
        self.claude_tags = dict(CLAUDE_TAGS)
        self.codex_tags = dict(CODEX_TAGS)
        self.sdk_pairs = [("0.3.288", "2.1.288"), ("0.3.289", "2.1.289"), ("0.3.290-beta.1", "2.1.290")]
        self.settings_extra: list[str] = []
        self.hooks = list(HOOKS)
        self.dts_override: str | None = None
        self.reference_keys = list(REFERENCE_KEYS)
        self.reference_override: str | None = None
        self.env_extra: list[str] = []
        self.env_override: str | None = None
        self.mods = list(MODS)
        self.mods_override: str | None = None
        self.codex_tag = "rust-v0.160.0"
        self.schema_extra: list[str] = []
        self.schema_override: bytes | None = None
        self.features = dict(FEATURES)
        self.features_override: str | None = None
        self.changelog = [("2.1.289", ["Fixed a synthetic thing"]), ("2.1.288", ["Added a synthetic `/thing` command"])]
        self.changelog_override: str | None = None
        self.release_body = "## New Features\n\n- Browse older tasks\n\n## Bug Fixes\n\n- Fixed a reconnect\n"
        self.release_list: dict | None = None
        self.broken: set[str] = set()
        self.calls: list[tuple] = []

    def schema_bytes(self) -> bytes:
        if self.schema_override is not None:
            return self.schema_override
        return json.dumps(codex_schema(self.schema_extra)).encode("utf-8")

    def schema_url(self) -> str:
        return f"https://github.com/openai/codex/releases/download/{self.codex_tag}/config-schema.json"

    def release(self) -> dict:
        return {"tag_name": self.codex_tag, "name": self.codex_tag.removeprefix("rust-v"),
                "published_at": "2026-10-01T20:19:13Z", "prerelease": False, "draft": False,
                "body": self.release_body,
                "assets": [{"name": "codex-x86_64-unknown-linux-musl.tar.gz",
                            "browser_download_url": f"https://github.com/openai/codex/releases/download/"
                                                    f"{self.codex_tag}/codex-x86_64-unknown-linux-musl.tar.gz"},
                           {"name": "config-schema.json", "browser_download_url": self.schema_url(),
                            "digest": "sha256:" + sha256(self.schema_bytes())}]}

    def bodies(self) -> dict[str, bytes]:
        dts = (self.dts_override if self.dts_override is not None
               else sdk_dts(self.settings_extra, self.hooks)).encode("utf-8")
        bodies = {
            usw.DIST_TAGS_URL.format(package=usw.CLAUDE_PACKAGE): json.dumps(self.claude_tags).encode(),
            usw.DIST_TAGS_URL.format(package=usw.CODEX_PACKAGE): json.dumps(self.codex_tags).encode(),
            usw.PACKUMENT_URL.format(package=usw.SDK_PACKAGE): json.dumps({"name": usw.SDK_PACKAGE, "versions": {
                sdk: {"name": usw.SDK_PACKAGE, "version": sdk, "claudeCodeVersion": code, "types": "sdk.d.ts"}
                for sdk, code in self.sdk_pairs}}).encode(),
            usw.SETTINGS_REFERENCE_URL: (self.reference_override if self.reference_override is not None
                                         else reference_page(self.reference_keys)).encode("utf-8"),
            usw.ENV_VARS_URL: (self.env_override if self.env_override is not None
                               else env_page(self.env_extra)).encode("utf-8"),
            usw.MODS_URL: (self.mods_override if self.mods_override is not None else mods_page(self.mods)).encode(),
            self.schema_url(): self.schema_bytes(),
            usw.CHANGELOG_URL: (self.changelog_override if self.changelog_override is not None
                                else changelog(self.changelog)).encode("utf-8"),
        }
        for sdk, _ in self.sdk_pairs:
            bodies[usw.UNPKG_URL.format(package=usw.SDK_PACKAGE, version=sdk, path="sdk.d.ts")] = dts
        return bodies

    def http_get(self, url: str, timeout: int = 60) -> bytes:
        self.calls.append(("http", url))
        bodies = self.bodies()
        if url in self.broken or url not in bodies:
            raise OSError(f"synthetic failure for {url}")
        return bodies[url]

    def gh_api(self, arguments, timeout: int = 60):
        self.calls.append(("gh", tuple(arguments)))
        endpoint = arguments[0]
        if endpoint in self.broken:
            return None, "synthetic gh failure"
        if endpoint == usw.CODEX_LATEST_PATH:
            return json.dumps(self.release()).encode("utf-8"), None
        if endpoint == "graphql" and self.release_list is not None:
            return json.dumps(self.release_list).encode("utf-8"), None
        return None, "HTTP 404: Not Found (synthetic)"

    def probe(self, binary: str, timeout: int = 60):
        self.calls.append(("probe", binary))
        if "probe" in self.broken:
            raise OSError("synthetic probe failure")
        text = self.features_override if self.features_override is not None else features_list(self.features)
        return text.encode("utf-8"), "codex-cli 0.160.0"

    @contextlib.contextmanager
    def patched(self):
        with mock.patch.object(usw, "http_get", self.http_get), mock.patch.object(usw, "gh_api", self.gh_api), \
                mock.patch.object(usw, "probe_codex", self.probe):
            yield


def short_temp_base() -> str:
    """The shortest writable temporary base (tests/test_currency_due.py short_temp_base(): a long macOS TMPDIR would
    push the summary's absolute command out of the 160-character line)."""
    usable = [c for c in (tempfile.gettempdir(), "/tmp") if os.path.isdir(c) and os.access(c, os.W_OK)]
    return min(usable, key=lambda c: len(os.path.realpath(c)))


class Watch:
    """A temporary checkout with its own copy of the script and the committed dispositions catalog, an XDG_STATE_HOME
    beside it (the default state directory, as the timer's environment gives it), and no baseline until seed()."""

    def __init__(self, test: unittest.TestCase):
        temporary = tempfile.TemporaryDirectory(dir=short_temp_base())
        test.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        self.root, self.xdg = base / "checkout", base / "xdg"
        self.state = self.xdg / usw.STATE_NAME / usw.WATCH_DIR
        self.script = self.root / usw.SCRIPT_PATH
        self.script.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / usw.SCRIPT_PATH, self.script)
        self.dispositions = self.root / usw.DISPOSITIONS_PATH
        self.dispositions.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / usw.DISPOSITIONS_PATH, self.dispositions)
        self.baseline = self.root / usw.BASELINE_PATH
        self.latest = self.state / usw.LATEST_FILE

    def run(self, *arguments: str, upstream: Upstream | None = None, codex: str = CODEX_BIN):
        stdout, stderr = io.StringIO(), io.StringIO()
        context = upstream.patched() if upstream is not None else contextlib.nullcontext()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), context, \
                mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.xdg)}):
            try:
                code = usw.main(["--root", str(self.root), "--now", NOW, "--codex-bin", codex, *arguments])
            except SystemExit as exit_:  # argparse usage errors
                code = exit_.code
        return code, stdout.getvalue(), stderr.getvalue()

    def seed(self, test: unittest.TestCase, upstream: Upstream) -> None:
        code, _, stderr = self.run("--network", "--write-baseline", upstream=upstream)
        test.assertEqual(code, 0, stderr)

    def document(self, *arguments: str, upstream: Upstream | None = None) -> dict:
        code, stdout, stderr = self.run(*arguments, "--json", upstream=upstream)
        if code != 0:
            raise AssertionError(f"exit {code}: {stderr}")
        return json.loads(stdout)

    def add_rows(self, *rows: dict) -> None:
        catalog = json.loads(self.dispositions.read_text(encoding="utf-8"))
        catalog["rows"] += list(rows)
        self.dispositions.write_text(json.dumps(catalog), encoding="utf-8")


def row(key: str, disposition: str = "declined", **changes) -> dict:
    entry = {"key": key, "disposition": disposition, "reason": "synthetic decision", "source":
             "https://code.claude.com/docs/en/settings.md", "carrier": None, "value": None, "scope": None,
             "overturn": "a measured gain on the target host", "reviewed_utc": NOW, "version": "2.1.289"}
    if disposition in ("enabled", "adopt-pending"):
        entry["carrier"] = "adoption/templates/claude.settings.template.json"
    entry.update(changes)
    return entry


# ----------------------------------------------------------------------------------------------- parser tests


class ParserTests(unittest.TestCase):
    def test_typescript_string_escapes_are_decoded_for_hooks_and_settings(self):
        """Synthetic fixtures, not upstream tests: TypeScript literal spellings denote decoded member names."""
        cases = [(r"\x50reToolUse", "PreToolUse"), (r"\u0050reToolUse", "PreToolUse"),
                 (r"\u{50}reToolUse", "PreToolUse"), (r"Pre\nToolUse", "Pre\nToolUse"),
                 (r"Pre\rToolUse", "Pre\rToolUse"), (r"Pre\tToolUse", "Pre\tToolUse"),
                 (r"Pre\bToolUse", "Pre\bToolUse"), (r"Pre\fToolUse", "Pre\fToolUse"),
                 (r"Pre\vToolUse", "Pre\vToolUse"), (r"Pre\0ToolUse", "Pre\0ToolUse"),
                 (r"Pre\\ToolUse", "Pre\\ToolUse"), (r"Pre\'ToolUse", "Pre'ToolUse"),
                 (r'Pre\"ToolUse', 'Pre"ToolUse'), ("Pre\\\nToolUse", "PreToolUse"),
                 ("Pre\\\r\nToolUse", "PreToolUse"), ("Pre\\\rToolUse", "PreToolUse"),
                 ("Pre\\\u2028ToolUse", "PreToolUse"), ("Pre\\\u2029ToolUse", "PreToolUse"),
                 (r"\u{1F600}", "\U0001f600"), (r"\uD83D\uDE00", "\U0001f600"),
                 (r"Pre\qToolUse", "PreqToolUse")]
        for spelling, value in cases:
            with self.subTest(spelling=spelling):
                text = sdk_dts().replace("'PreToolUse'", f"'{spelling}'", 1)
                text = text.replace("'quoted-key'?:", f'"{spelling}"?:', 1)
                self.assertEqual(set(usw.parse_hook_events(text)), (set(HOOKS) - {"PreToolUse"}) | {value})
                self.assertEqual(set(usw.parse_settings_keys(text)),
                                 ({*TRAP_SETTINGS, *FILLER_SETTINGS} - {"quoted-key"}) | {value})

    def test_invalid_typescript_string_escapes_fail_both_name_parsers(self):
        """Synthetic fixtures, not upstream tests: malformed numeric escapes are parse errors, never new names."""
        for spelling in (r"\x", r"\x4G", r"\u12", r"\uZZZZ", r"\u{}", r"\u{GG}", r"\u{110000}",
                         r"\01", r"\8", r"\9", "Pre\nToolUse"):
            with self.subTest(spelling=spelling):
                hooks = sdk_dts().replace("'PreToolUse'", f"'{spelling}'", 1)
                settings = sdk_dts().replace("'quoted-key'?:", f'"{spelling}"?:', 1)
                with self.assertRaisesRegex(usw.AnchorMissing, r"anchor missing: sdk\.d\.ts:HOOK_EVENTS"):
                    usw.parse_hook_events(hooks)
                with self.assertRaisesRegex(usw.AnchorMissing, r"anchor missing: sdk\.d\.ts:interface Settings"):
                    usw.parse_settings_keys(settings)

    def test_unresolved_local_schema_refs_are_integrity_errors(self):
        """Synthetic fixtures, not upstream tests: even one dangling local reference must fail integrity."""
        for reference in ("#/definitions/Missing", "#/$defs/Missing", "#/properties/missing"):
            with self.subTest(reference=reference):
                schema = codex_schema()
                schema["properties"]["top_00"] = {"$ref": reference}
                with self.assertRaisesRegex(usw.AnchorMissing, r"anchor missing: config-schema\.json:\$ref"):
                    usw.flatten_codex_schema(json.dumps(schema).encode())

    def test_local_schema_refs_resolve_defs_json_pointers_and_named_anchors(self):
        """Synthetic fixtures, not upstream tests: valid local reference targets retain the known property paths."""
        for reference in ("#/$defs/Alias", "#/definitions/Alias~1~0", "#/examples/0", "#tui"):
            with self.subTest(reference=reference):
                schema = codex_schema()
                target = schema["definitions"]["Tui"]
                schema["$defs"] = {"Alias": dict(target, **{"$anchor": "tui"})}
                schema["definitions"]["Alias/~"] = target
                schema["examples"] = [target]
                schema["properties"]["tui"] = {"$ref": reference}
                self.assertEqual(set(usw.flatten_codex_schema(json.dumps(schema).encode())), expected_paths())

    def test_an_unvisited_definition_with_a_dangling_ref_is_an_integrity_error(self):
        """Synthetic fixture, not an upstream test: integrity covers references outside observed config paths."""
        schema = codex_schema()
        schema["definitions"]["Unused"] = {"$ref": "#/definitions/Missing"}
        with self.assertRaisesRegex(usw.AnchorMissing, r"config-schema\.json:\$ref"):
            usw.flatten_codex_schema(json.dumps(schema).encode())

    def test_settings_index_disagreement_allows_two_keys_but_rejects_three(self):
        """Synthetic fixtures, not upstream tests: two distinct top-level keys is the documented editorial tolerance."""
        for count in (1, 2, 3):
            with self.subTest(differing_keys=count):
                rows = "\n".join(f"| `indexOnly{index}` | Description with `notAKey` | Settings | Any file |"
                                 for index in range(count))
                page = reference_page().replace("## Model and responses", rows + "\n\n## Model and responses", 1)
                if count <= 2:
                    self.assertEqual(usw.parse_settings_reference(page), sorted({*REFERENCE_KEYS, "deprecatedSetting"}))
                else:
                    with self.assertRaisesRegex(usw.AnchorMissing, r"key headings/settings index"):
                        usw.parse_settings_reference(page)

    def test_settings_keys_survive_comments_quotes_dollar_nesting_literals_and_modifiers(self):
        keys = usw.parse_settings_keys(sdk_dts())
        self.assertEqual(set(keys), {*TRAP_SETTINGS, *FILLER_SETTINGS})
        self.assertEqual(keys, sorted(keys))
        for absent in ("path", "timeoutMs", "intervalMs", "kind", "k", "innerOnly", "notASettingsKey", "key",
                       "Example", "Default", "event", "detail", "Array", "Set", "Partial", "Map", "Foo", "new"):
            self.assertNotIn(absent, keys)

    def test_member_rules_for_type_arguments_construct_signatures_and_line_breaks(self):
        def members(body: str) -> list[str]:
            text = "export declare interface Settings {\n" + body + "\n}\n"
            return usw.interface_members(text, usw.SETTINGS_ANCHOR.search(text).end())

        cases = {
            "env?: Record<string, Array<string>>;": ["env"],
            "m?: Map<string, Set<number>>;": ["m"],
            "new (x: string): Foo;\nnew <T>(x: T): Foo;": [],  # construct signatures
            "new?: boolean;": ["new"],  # a property named new
            "new?(): void;\n'new'(): void;": ["new", "new"],  # methods named new
            "a: string\nb: number": ["a", "b"],
            "u?:\n  | Array<string>\n  | Map<string, number>\nnext?: string": ["u", "next"],
            "c?: A extends\n  B<C> ? D : E\nd: string": ["c", "d"],
            "x: string // trailing\ny: number /* a\nblock */ w: boolean": ["x", "y", "w"],
            "<T>(x: T): T\n[k: string]: unknown\nafter: string": ["after"],  # call and index signatures
        }
        for body, expected in cases.items():
            with self.subTest(body=body):
                self.assertEqual(members(body), expected)

    def test_settings_reference_keys_follow_the_page_structure(self):
        keys = usw.parse_settings_reference(reference_page())
        self.assertEqual(keys, sorted({*REFERENCE_KEYS, "deprecatedSetting"}))
        for absent in ("removedSetting", "scopeMarkedElsewhere", "globalOnlyKey", "sectionOnlyGlobal", "fencedFake",
                       "fillerSetting00.nested"):
            self.assertNotIn(absent, keys)

    def test_fenced_heading_lines_neither_start_nor_end_a_section(self):
        entries = usw.reference_entries(reference_page())
        self.assertEqual({entry["key"] for entry in entries if entry["section"] == usw.GLOBAL_CONFIG_SECTION},
                         {"globalOnlyKey", "sectionOnlyGlobal"})
        self.assertNotIn("fencedFake", {entry["key"] for entry in entries})
        self.assertEqual({entry["section"] for entry in entries}, {"Model and responses", "Global config settings"})

    def test_hook_events_read_a_multiline_array_with_both_quotes_and_comments(self):
        self.assertEqual(usw.parse_hook_events(sdk_dts()), sorted(HOOKS))
        self.assertEqual(usw.parse_hook_events(sdk_dts(multiline_hooks=False)), sorted(HOOKS))

    def test_env_names_are_whole_backticked_upper_case_tokens_of_two_or_more_characters(self):
        names = usw.parse_env_names(env_page(extra=("ANOTHER_NAME",)))
        self.assertEqual(set(names), {*ENV_NAMES, "ANOTHER_NAME", "CLAUDECODE"})
        for absent in ("K", "M", "OTEL_", "FOO_BAR", "NOT_BACKTICKED_NAME", "lowercase_name"):
            self.assertNotIn(absent, names)

    def test_mod_names_are_the_cc_plugin_tokens(self):
        self.assertEqual(usw.parse_mod_names(mods_page()), sorted(MODS))

    def test_codex_paths_follow_refs_combinators_maps_and_arrays_and_skip_containers_and_cycles(self):
        paths = usw.flatten_codex_schema(json.dumps(codex_schema(extra_top=("extra_flag",))).encode())
        self.assertEqual(set(paths), expected_paths(("extra_flag",)))
        self.assertNotIn("mcp_servers.*", paths)
        self.assertNotIn("mcp_servers.*.env.*", paths)
        self.assertNotIn("model.fallback.name", paths)  # the recursive $ref is not followed again

    def test_profile_paths_that_mirror_root_paths_are_left_out(self):
        paths = set(usw.flatten_codex_schema(json.dumps(codex_schema()).encode()))
        self.assertIn("profiles.*.profile_only", paths)  # a profile's own key stays
        self.assertFalse({path for path in paths if path.startswith("profiles.*.") and path != "profiles.*.profile_only"})
        self.assertTrue({"top_00", "tui.theme", "features.feature_00"} <= paths)

    def test_a_ref_with_sibling_properties_counts_both(self):
        schema = codex_schema()
        schema["properties"]["tui"] = {"$ref": "#/definitions/Tui", "properties": {"sibling": {"type": "string"}}}
        paths = usw.flatten_codex_schema(json.dumps(schema).encode())
        self.assertIn("tui.sibling", paths)
        self.assertIn("tui.theme", paths)

    def test_codex_features_keep_two_word_stages(self):
        rows = usw.parse_codex_features(features_list(FEATURES))
        self.assertEqual(rows["feature_00"], {"stage": "under development", "enabled": False})
        self.assertEqual(rows["feature_01"], {"stage": "stable", "enabled": True})
        self.assertEqual(len(rows), 40)

    def test_the_sdk_release_is_matched_by_claude_code_version_and_prereleases_are_skipped(self):
        packument = json.dumps({"versions": {
            "0.3.288": {"claudeCodeVersion": "2.1.288", "types": "sdk.d.ts"},
            "0.3.289": {"claudeCodeVersion": "2.1.289", "types": "sdk.d.ts"},
            "0.3.290-beta.1": {"claudeCodeVersion": "2.1.290"}}}).encode()
        self.assertEqual(usw.resolve_sdk(packument, "2.1.289"),
                         {"version": "0.3.289", "claude_code_version": "2.1.289", "matched": True, "types": "sdk.d.ts"})
        fallback = usw.resolve_sdk(packument, "2.1.290")
        self.assertEqual((fallback["version"], fallback["matched"]), ("0.3.289", False))
        with self.assertRaises(usw.AnchorMissing):
            usw.resolve_sdk(packument, "2.1.100")

    def test_changelog_delta_lists_newer_versions_and_selects_surface_entries(self):
        text = changelog([("2.1.291", ["[VSCode] Added a toggle", "Fixed a crash", "Fixed `CLAUDE_CODE_X_Y` parsing"]),
                          ("2.1.290", ["New `/mods` command", "Improved the hooks timeout", "Fixed a typo"]),
                          ("2.1.289", ["Added an old thing"])])
        delta = usw.claude_changelog_delta(text, "2.1.289")
        self.assertEqual(delta["versions"], ["2.1.291", "2.1.290"])
        self.assertEqual((delta["entries"], delta["matching"]), (6, 4))
        self.assertEqual(delta["titles"][0], "2.1.291: [VSCode] Added a toggle")
        self.assertNotIn("2.1.289: Added an old thing", delta["titles"])

    def test_release_notes_under_a_new_heading_are_selected(self):
        delta = usw.codex_notes_delta([{"tag": "rust-v0.161.0", "body": "## New Features\n- Browse tasks\n"
                                                                         "## Bug Fixes\n- Fixed a crash\n"}],
                                      "rust-v0.160.0", True, None)
        self.assertEqual((delta["entries"], delta["matching"], delta["titles"]), (2, 1, ["0.161.0: Browse tasks"]))


class AnchorTests(unittest.TestCase):
    """Every missing anchor, and a count outside its bound, is exit 3 naming the anchor; nothing is written."""

    CASES = (
        ("no Settings interface", lambda u: setattr(u, "dts_override", sdk_dts(settings=False)),
         "anchor missing: sdk.d.ts:interface Settings"),
        ("no HOOK_EVENTS", lambda u: setattr(u, "dts_override", sdk_dts(hook_events=False)),
         "anchor missing: sdk.d.ts:HOOK_EVENTS"),
        ("too few hook events", lambda u: setattr(u, "hooks", HOOKS[:3]), "anchor missing: sdk.d.ts:HOOK_EVENTS"),
        ("too few settings", lambda u: setattr(u, "dts_override", sdk_dts(interface="export declare interface "
                                                                         "Settings {\n    only?: string;\n}\n")),
         "anchor missing: sdk.d.ts:interface Settings (count"),
        ("settings reference without its title", lambda u: setattr(u, "reference_override",
                                                                    reference_page(title=False)),
         "anchor missing: settings-reference.md:# All settings"),
        ("settings reference without its global config section",
         lambda u: setattr(u, "reference_override", reference_page(global_section=False)),
         "anchor missing: settings-reference.md:## Global config settings"),
        ("settings reference with too few keys", lambda u: setattr(u, "reference_keys", FILLER_SETTINGS[:10]),
         "anchor missing: settings-reference.md:key headings (count"),
        ("env page without its title", lambda u: setattr(u, "env_override", env_page(heading=False)),
         "anchor missing: env-vars.md:# Environment variables"),
        ("env page with too few names", lambda u: setattr(u, "env_override", env_page(names=ENV_NAMES[:5])),
         "anchor missing: env-vars.md:backticked names (count"),
        ("mods page without its section", lambda u: setattr(u, "mods_override", mods_page(heading=False)),
         "anchor missing: mods/overview.md:built-in mods heading"),
        ("schema without features", lambda u: setattr(u, "schema_override", json.dumps(
            {"properties": {f"k{i}": {"type": "string"} for i in range(40)}}).encode()),
         "anchor missing: config-schema.json:features"),
        ("schema without properties", lambda u: setattr(u, "schema_override", b'{"type": "object"}'),
         "anchor missing: config-schema.json:properties"),
        ("features list in another format", lambda u: setattr(u, "features_override",
                                                              "\n".join(f"{n}|{s}" for n, (s, _) in FEATURES.items())),
         "anchor missing: codex features list:rows"),
        ("changelog without version headings", lambda u: setattr(u, "changelog_override", "# Changelog\n\n- x\n"),
         "anchor missing: CHANGELOG.md:## X.Y.Z headings"),
        ("dist-tags without latest", lambda u: setattr(u, "claude_tags", {"stable": "2.1.285"}),
         "anchor missing: npm-dist-tags:@anthropic-ai/claude-code"),
    )

    def test_each_missing_anchor_exits_3_and_writes_nothing(self):
        for label, change, message in self.CASES:
            with self.subTest(case=label):
                watch, upstream = Watch(self), Upstream()
                watch.seed(self, upstream)
                before = watch.latest.read_bytes()
                change(upstream)
                code, _, stderr = watch.run("--network", upstream=upstream)
                self.assertEqual(code, 3, stderr)
                self.assertIn(message, stderr)
                self.assertEqual(watch.latest.read_bytes(), before)

    def test_the_default_bounds_reject_a_tiny_fixture(self):
        with self.assertRaises(usw.AnchorMissing) as raised:
            usw.parse_settings_keys(sdk_dts(interface=PLAIN_INTERFACE.replace("@FILLER@", "    one?: string;")))
        self.assertIn("count 1 outside 50..2000", str(raised.exception))


class FloorTests(unittest.TestCase):
    """M1: the reviewer's degraded artifacts, real-shaped, against the deployed bounds (BOUNDS and FLOOR_PERCENT as
    shipped, never lifted). Missing definitions fail reference integrity before the floor; the other degraded counts
    still pass their absolute bounds and fail the 80%-of-baseline floor. Every failed run writes nothing."""

    def degraded_run(self, prepare, degrade, message: str, absolute, bound: str):
        watch, upstream = Watch(self), Upstream()
        prepare(upstream)
        watch.seed(self, upstream)
        before = watch.latest.read_bytes()
        degrade(upstream)
        self.assertGreaterEqual(absolute(upstream), usw.BOUNDS[bound][0])  # the absolute bound passes
        code, _, stderr = watch.run("--network", upstream=upstream)
        self.assertEqual(code, 3, stderr)
        self.assertIn(message, stderr)
        self.assertIn("or a real removal of more than 20% at once", stderr)
        self.assertEqual(watch.latest.read_bytes(), before)

    def test_a_schema_read_without_its_definitions_fails_the_floor(self):
        """Synthetic fixture, not an upstream test: the historic floor control now fails earlier on integrity."""
        schema = real_shaped_schema()
        watch, upstream = Watch(self), Upstream()
        upstream.schema_override = json.dumps(schema).encode()
        watch.seed(self, upstream)
        latest_before, baseline_before = watch.latest.read_bytes(), watch.baseline.read_bytes()
        upstream.schema_override = json.dumps(dict(schema, definitions={})).encode()
        for arguments in (("--network",), ("--network", "--write-baseline", "--force")):
            with self.subTest(arguments=arguments):
                code, _, stderr = watch.run(*arguments, upstream=upstream)
                self.assertEqual(code, 3, stderr)
                self.assertIn("anchor missing: config-schema.json:$ref", stderr)
                self.assertNotIn("below 80%", stderr)
                self.assertEqual(watch.latest.read_bytes(), latest_before)
                self.assertEqual(watch.baseline.read_bytes(), baseline_before)

    def test_a_schema_read_without_its_combinators_fails_the_floor(self):
        schema = real_shaped_schema()
        self.degraded_run(
            lambda u: setattr(u, "schema_override", json.dumps(schema).encode()),
            lambda u: setattr(u, "schema_override", json.dumps(without_combinators(schema)).encode()),
            "anchor missing: codex:config below 80% of baseline",
            lambda u: len(usw.flatten_codex_schema(u.schema_override)), "codex:config")

    def test_an_env_page_cut_at_half_its_table_fails_the_floor(self):
        names = [f"CLAUDE_CODE_TABLE_{index:03d}" for index in range(400)]
        self.degraded_run(
            lambda u: setattr(u, "env_override", env_table_page(names)),
            lambda u: setattr(u, "env_override", env_table_page(names[:200])),
            "anchor missing: claude:env below 80% of baseline (count 200, baseline 400",
            lambda u: len(usw.parse_env_names(u.env_override)), "claude:env")

    def test_a_settings_reference_cut_at_half_fails_its_own_floor_while_the_union_holds(self):
        # The SDK also types the cut keys, so claude:setting (the union) keeps its count; the per-source floor fires.
        extra = [f"documentedSetting{index:03d}" for index in range(100)]

        def prepare(upstream):
            upstream.settings_extra = list(extra)
            upstream.reference_keys = [*FILLER_SETTINGS, *extra]

        self.degraded_run(prepare, lambda u: setattr(u, "reference_keys", list(FILLER_SETTINGS)),
                          "anchor missing: claude:setting from settings-reference.md below 80% of baseline "
                          "(count 61, baseline 161",
                          lambda u: len(usw.parse_settings_reference(reference_page(u.reference_keys))),
                          "claude:setting/settings-reference")

    def test_a_removal_under_the_floor_is_reported_and_counted(self):
        # One mod of six gone (17%) passes the floor: removed is in the line, in coverage.counts and in latest.json.
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.mods = [name for name in MODS if name != "cc-plugin-beta"]
        document = watch.document("--network", upstream=upstream)
        self.assertTrue(document["summary_line"].startswith("surface watch: nothing new, 1 removed"),
                        document["summary_line"])
        self.assertEqual(document["coverage"]["counts"]["claude:mod"],
                         {"observed": 5, "baseline": 6, "new": 0, "removed": 1})
        self.assertEqual([item["key"] for item in document["removed"]], ["claude:mod:cc-plugin-beta"])

    def test_a_reviewed_rebaseline_is_not_blocked_by_the_floor(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.mods = MODS[:3]  # half the mods removed upstream, a real change
        code, _, stderr = watch.run("--network", upstream=upstream)
        self.assertEqual(code, 3, stderr)
        self.assertIn("anchor missing: claude:mod below 80% of baseline (count 3, baseline 6", stderr)
        code, _, stderr = watch.run("--network", "--write-baseline", "--force", upstream=upstream)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(watch.baseline.read_text(encoding="utf-8"))["kinds"]["claude:mod"],
                         sorted(MODS[:3]))
        self.assertEqual(watch.run("--network", upstream=upstream)[0], 0)


# ----------------------------------------------------------------------------------------------- run tests


class CachedArtifactTests(unittest.TestCase):
    """Local integration checks using optional cached vendor artifacts; these are not upstream tests."""

    def test_equivalent_string_escapes_preserve_the_real_sdk_hook_and_settings_sets(self):
        """Local integration check, not an upstream test: escaped hook and quoted $schema spellings preserve names."""
        sdk = cached_artifact(self, "claude-agent-sdk-types").decode("utf-8")
        hooks, settings = usw.parse_hook_events(sdk), usw.parse_settings_keys(sdk)
        self.assertEqual((len(hooks), len(settings)), (33, 173))
        escaped = sdk.replace("'PreToolUse'", r"'\u0050reToolUse'", 1)
        anchor = usw.SETTINGS_ANCHOR.search(escaped)
        key = re.compile(r"(?m)^([ \t]+)\$schema(\??[ \t]*:)").search(escaped, anchor.end())
        self.assertIsNotNone(key)
        escaped = escaped[:key.start()] + key.group(1) + r'"\x24sch\u0065ma"' + key.group(2) + escaped[key.end():]
        self.assertEqual(usw.parse_hook_events(escaped), hooks)
        self.assertEqual(usw.parse_settings_keys(escaped), settings)

    def test_escaped_quoted_setting_preserves_the_real_sdk_settings_set(self):
        """Local integration check, not an upstream test: quote a real SDK key and decode its hexadecimal escapes."""
        sdk = cached_artifact(self, "claude-agent-sdk-types").decode("utf-8")
        original = usw.parse_settings_keys(sdk)
        self.assertEqual(len(original), 173)
        anchor = usw.SETTINGS_ANCHOR.search(sdk)
        key = re.compile(r"(?m)^([ \t]+)\$schema(\??[ \t]*:)").search(sdk, anchor.end())
        self.assertIsNotNone(key)
        escaped = sdk[:key.start()] + key.group(1) + r'"\x24sch\u0065ma"' + key.group(2) + sdk[key.end():]
        self.assertEqual(usw.parse_settings_keys(escaped), original)

    def test_commonmark_closing_markers_on_every_heading_preserve_the_real_settings(self):
        """Local integration check, not an upstream test: CommonMark ATX formatting preserves all 171 keys."""
        page = cached_artifact(self, "claude-settings-reference-page").decode("utf-8")
        expected = usw.parse_settings_reference(page)
        self.assertEqual(len(expected), 171)
        for indent in range(4):
            with self.subTest(leading_spaces=indent):
                reformatted = re.sub(r"(?m)^(#{1,6})([ \t]+.*)$",
                                     lambda match: " " * indent + match.group() + "\t" + match.group(1) + " \t", page)
                self.assertEqual(usw.parse_settings_reference(reformatted), expected)

    def test_closing_markers_on_the_ten_docs_only_headings_preserve_the_real_settings(self):
        """Local integration check, not an upstream test: the SDK union cannot mask lost docs-only headings."""
        page = cached_artifact(self, "claude-settings-reference-page").decode("utf-8")
        expected = usw.parse_settings_reference(page)
        sdk = usw.parse_settings_keys(cached_artifact(self, "claude-agent-sdk-types").decode("utf-8"))
        docs_only = set(expected) - set(sdk)
        self.assertEqual(len(docs_only), 10)
        headings = re.findall(r"(?m)^### `([^`]+)`$", page)
        self.assertEqual({key.split(".")[0] for key in headings if key.split(".")[0] in docs_only}, docs_only)
        reformatted = re.sub(r"(?m)^### `([^`]+)`$",
                             lambda match: match.group() + " ###" if match.group(1).split(".")[0] in docs_only
                             else match.group(), page)
        self.assertEqual(usw.parse_settings_reference(reformatted), expected)

    def test_setext_docs_only_headings_trip_the_independent_index_guard(self):
        """Local integration check, not an upstream test: an unsupported heading form cannot silently lose ten keys."""
        page = cached_artifact(self, "claude-settings-reference-page").decode("utf-8")
        sdk = usw.parse_settings_keys(cached_artifact(self, "claude-agent-sdk-types").decode("utf-8"))
        docs_only = set(usw.parse_settings_reference(page)) - set(sdk)
        self.assertEqual(len(docs_only), 10)
        unsupported = re.sub(r"(?m)^### `([^`]+)`$",
                             lambda match: f"`{match.group(1)}`\n---" if match.group(1).split(".")[0] in docs_only
                             else match.group(), page)
        with self.assertRaisesRegex(usw.AnchorMissing, r"anchor missing: settings-reference\.md:key headings/settings index"):
            usw.parse_settings_reference(unsupported)

    def test_incomplete_schema_is_rejected_daily_and_when_writing_baseline(self):
        """Local integration check, not an upstream test: corrupt the real rust-v0.160.0 schema offline."""
        original = cached_artifact(self, "codex-config-schema")
        self.assertEqual(len(usw.flatten_codex_schema(original)), 1034)
        missing_definitions = json.loads(original)
        del missing_definitions["definitions"]
        dangling = json.loads(original)
        dangling["properties"]["model"]["$ref"] = "#/$defs/Missing"
        for label, schema in (("definitions deleted", missing_definitions), ("one dangling ref", dangling)):
            for mode in ("daily", "write-baseline"):
                with self.subTest(schema=label, mode=mode):
                    watch, upstream = Watch(self), Upstream()
                    upstream.schema_override = original
                    watch.seed(self, upstream)
                    code, _, stderr = watch.run()
                    self.assertEqual(code, 0, stderr)
                    baseline_before = watch.baseline.read_bytes()
                    latest_before = watch.latest.read_bytes()
                    cache = watch.state / usw.CACHE_DIR
                    body = json.dumps(schema).encode()
                    (cache / "codex-config-schema.body").write_bytes(body)
                    meta_path = cache / "codex-config-schema.json"
                    meta = json.loads(meta_path.read_text())
                    meta.update(sha256=sha256(body), bytes=len(body))
                    meta_path.write_text(json.dumps(meta))
                    release_path = cache / "github-codex-latest-release.body"
                    release = json.loads(release_path.read_bytes())
                    release["assets"][-1]["digest"] = "sha256:" + sha256(body)
                    release_body = json.dumps(release).encode()
                    release_path.write_bytes(release_body)
                    release_meta_path = cache / "github-codex-latest-release.json"
                    release_meta = json.loads(release_meta_path.read_text())
                    release_meta.update(sha256=sha256(release_body), bytes=len(release_body))
                    release_meta_path.write_text(json.dumps(release_meta))
                    if mode == "write-baseline":
                        watch.baseline.unlink()
                    code, _, stderr = watch.run(*(["--write-baseline"] if mode == "write-baseline" else []))
                    self.assertEqual(code, 3, stderr)
                    self.assertIn("anchor missing: config-schema.json:$ref", stderr)
                    self.assertNotIn("below 80%", stderr)
                    if mode == "write-baseline":
                        self.assertFalse(watch.baseline.exists())
                    else:
                        self.assertEqual(watch.baseline.read_bytes(), baseline_before)
                    self.assertEqual(watch.latest.read_bytes(), latest_before)


class SourceAvailabilityTests(unittest.TestCase):
    def test_offline_without_a_cache_exits_4_naming_the_source(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        shutil.rmtree(watch.state)
        code, _, stderr = watch.run()
        self.assertEqual(code, 4, stderr)
        self.assertIn("source unavailable: npm-claude-code-dist-tags (no cache; run with --network)", stderr)
        self.assertFalse(watch.state.exists())

    def test_a_failed_fetch_without_a_cache_exits_4(self):
        watch, upstream = Watch(self), Upstream()
        upstream.broken.add(usw.ENV_VARS_URL)
        code, _, stderr = watch.run("--network", "--write-baseline", upstream=upstream)
        self.assertEqual(code, 4, stderr)
        self.assertIn("source unavailable: claude-env-vars-page (OSError: synthetic failure", stderr)
        self.assertFalse(watch.baseline.exists())
        self.assertFalse(watch.state.exists())

    def test_a_failed_fetch_falls_back_to_the_cache_and_says_so(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.broken.add(usw.CODEX_LATEST_PATH)
        document = watch.document("--network", upstream=upstream)
        record = next(item for item in document["coverage"]["sources"]
                      if item["source"] == "github-codex-latest-release")
        self.assertTrue(record["origin"].startswith("cache; the network fetch failed: OSError: synthetic gh failure"))
        self.assertEqual(document["new"], [])

    def test_a_tampered_cache_body_is_no_cache(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        body = watch.state / usw.CACHE_DIR / "claude-mods-overview-page.body"
        body.write_bytes(body.read_bytes() + b"tampered")
        code, _, stderr = watch.run("--dry-run")
        self.assertEqual(code, 4, stderr)
        self.assertIn("source unavailable: claude-mods-overview-page", stderr)

    def test_a_cache_record_without_a_fetch_time_is_no_cache(self):
        # The fetch time ages a report built from the cache; a record without one cannot be aged honestly.
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        meta_path = watch.state / usw.CACHE_DIR / "claude-mods-overview-page.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for value in (None, "yesterday"):
            with self.subTest(fetched_utc=value):
                meta_path.write_text(json.dumps(dict(meta, fetched_utc=value)), encoding="utf-8")
                code, _, stderr = watch.run("--dry-run")
                self.assertEqual(code, 4, stderr)
                self.assertIn("source unavailable: claude-mods-overview-page", stderr)


LATER = "2026-10-06T12:00:00Z"  # two days after NOW, the seed's fetch time


class FreshnessTests(unittest.TestCase):
    """H1: a --network run whose fetch falls back to the cache says so in its line and in the journal line, and its
    generated_at is the cached fetch time, so scripts/currency_due.py stops counting it three days after that fetch."""

    def test_a_failed_fetch_marks_the_line_partial_cache_and_ages_generated_at(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.broken.add(usw.ENV_VARS_URL)
        code, stdout, stderr = watch.run("--network", "--now", LATER, upstream=upstream)  # the journal line
        self.assertEqual(code, 0, stderr)
        self.assertTrue(stdout.startswith("surface watch (partial cache): nothing new"), stdout)
        document = json.loads(watch.latest.read_text(encoding="utf-8"))
        self.assertEqual((document["generated_at"], document["run_at"]), (NOW, LATER))
        self.assertEqual(document["coverage"]["from_cache"], ["claude-env-vars-page"])
        record = next(item for item in document["coverage"]["sources"] if item["source"] == "claude-env-vars-page")
        self.assertTrue(record["origin"].startswith("cache; the network fetch failed"), record)
        self.assertEqual((record["fetched_utc"], record["required"], record["cross_check"]), (NOW, True, False))
        self.assertTrue(any("generated_at is the oldest cached fetch time" in note
                            for note in document["coverage"]["notes"]))

    def test_every_fetch_failing_under_network_says_cache(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.broken.update(upstream.bodies())
        upstream.broken.update({usw.CODEX_LATEST_PATH, "probe"})
        document = watch.document("--network", "--now", LATER, upstream=upstream)
        self.assertTrue(document["summary_line"].startswith("surface watch (cache): "), document["summary_line"])
        self.assertEqual(document["generated_at"], NOW)

    def test_a_clean_network_run_is_unmarked_and_dated_by_the_run(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        document = watch.document("--network", "--now", LATER, upstream=upstream)
        self.assertTrue(document["summary_line"].startswith("surface watch: "), document["summary_line"])
        self.assertEqual((document["generated_at"], document["run_at"], document["coverage"]["from_cache"]),
                         (LATER, LATER, []))

    def test_the_currency_notice_stops_counting_three_days_after_the_cached_fetch(self):
        # The reviewer's case: one good run, then a --network run with one source broken. Its generated_at stays at
        # the cached fetch (NOW), so the notice counts it until NOW + 3 days and calls it stale after that.
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.settings_extra = ["newSetting"]
        upstream.broken.add(usw.ENV_VARS_URL)
        code, _, stderr = watch.run("--network", "--now", LATER, upstream=upstream)
        self.assertEqual(code, 0, stderr)
        surface = {"record": cd.read_record(watch.latest)}
        count, _, coverage = cd.surface_findings(surface, datetime(2026, 10, 7, 11, 59, 59, tzinfo=timezone.utc))
        self.assertEqual((count, coverage["surface_watch"]), (1, cd.SURFACE_FRESH))
        count, details, coverage = cd.surface_findings(surface, datetime(2026, 10, 7, 12, 0, 1, tzinfo=timezone.utc))
        self.assertEqual((count, details, coverage["surface_watch"]), (None, [], cd.SURFACE_STALE))
        self.assertIn(f"data of {NOW} is more than 3 days old", coverage["surface_watch_reason"])

    def test_a_cross_check_from_the_cache_does_not_age_the_report(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        lifecycle = json.dumps({"codex_cli_version": "codex-cli 0.160.0", "cli_features": []}).encode()
        original = upstream.http_get
        upstream.http_get = lambda url, timeout=60: (lifecycle if url == usw.CHENRUI_LIFECYCLE_URL
                                                     else original(url, timeout))
        code, _, stderr = watch.run("--network", "--cross-check", upstream=upstream)  # caches the tracker at NOW
        self.assertEqual(code, 0, stderr)
        upstream.http_get = original  # the tracker is unreachable now; the run falls back to its cache
        document = watch.document("--network", "--cross-check", "--now", LATER, upstream=upstream)
        record = next(item for item in document["coverage"]["sources"] if item["source"] == "xc-chenrui-lifecycle")
        self.assertTrue(record["origin"].startswith("cache; the network fetch failed"), record)
        self.assertIs(record["cross_check"], True)
        self.assertEqual((document["generated_at"], document["coverage"]["from_cache"]), (LATER, []))
        self.assertTrue(document["summary_line"].startswith("surface watch: "), document["summary_line"])


class DigestTests(unittest.TestCase):
    """L4: the config-schema.json asset is verified against GitHub's published sha256 digest when there is one; when
    the release publishes none, the schema is read unverified and the coverage says so."""

    def test_a_published_digest_is_verified_and_recorded(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        document = watch.document("--network", upstream=upstream)
        record = next(item for item in document["coverage"]["sources"] if item["source"] == "codex-config-schema")
        self.assertEqual(record["digest_check"], "verified against the published sha256 digest")

    def test_a_missing_digest_is_recorded_as_unverified(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        release = upstream.release

        def without_digest():
            answer = release()
            for asset in answer["assets"]:
                asset.pop("digest", None)
            return answer

        upstream.release = without_digest
        document = watch.document("--network", upstream=upstream)
        record = next(item for item in document["coverage"]["sources"] if item["source"] == "codex-config-schema")
        self.assertEqual(record["digest_check"], "unverified: no published sha256 digest")
        self.assertTrue(any("published no sha256 digest" in note for note in document["coverage"]["notes"]))
        self.assertEqual(document["new"], [])


class OfflineTests(unittest.TestCase):
    def test_network_off_uses_no_socket_no_gh_and_no_probe(self):
        watch, upstream = Watch(self), Upstream()
        upstream.settings_extra = ["laterSetting"]
        watch.seed(self, upstream)
        networked = watch.document("--dry-run", "--network", upstream=upstream)

        def refuse(*args, **kwargs):
            raise AssertionError("network use in an offline run")

        with mock.patch.object(socket, "socket", side_effect=refuse), \
                mock.patch.object(socket, "create_connection", side_effect=refuse), \
                mock.patch.object(usw, "gh_api", refuse), mock.patch.object(usw, "probe_codex", refuse):
            code, stdout, stderr = watch.run("--dry-run", "--json")
        self.assertEqual(code, 0, stderr)
        offline = json.loads(stdout)
        self.assertTrue(offline["coverage"]["mode"].startswith("offline"))
        self.assertTrue(offline["summary_line"].startswith("surface watch (cache): "))
        self.assertTrue(all(item["origin"] == "cache" for item in offline["coverage"]["sources"]))
        for field in ("new", "removed", "stage_changed", "unreviewed", "versions", "changelog"):
            self.assertEqual(offline[field], networked[field], field)

    def test_dry_run_writes_nothing_and_creates_no_directory(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        shutil.rmtree(watch.state)
        code, stdout, stderr = watch.run("--network", "--dry-run", upstream=upstream)
        self.assertEqual(code, 0, stderr)
        self.assertFalse(watch.state.exists())
        self.assertIn("dry run: wrote nothing", stdout)
        # Nothing was cached, so the command that ends the line fetches again.
        self.assertTrue(stdout.splitlines()[0].endswith("--network"), stdout.splitlines()[0])


class DiffTests(unittest.TestCase):
    def test_new_removed_stage_changed_and_unreviewed_against_the_baseline_and_dispositions(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.settings_extra = ["newSetting"]
        upstream.env_extra = ["CLAUDE_CODE_NEW_SWITCH"]
        upstream.mods = [name for name in MODS if name != "cc-plugin-diff"]
        upstream.features["brand_new"] = ("under development", False)
        upstream.features["feature_00"] = ("stable", True)
        watch.add_rows(row("claude:env:CLAUDE_CODE_NEW_SWITCH", "adopt-pending"))
        document = watch.document("--network", upstream=upstream)
        self.assertEqual([item["key"] for item in document["new"]],
                         ["claude:setting:newSetting", "claude:env:CLAUDE_CODE_NEW_SWITCH", "codex:feature:brand_new"])
        self.assertEqual(document["new"][2]["stage"], "under development")
        self.assertEqual([item["key"] for item in document["removed"]], ["claude:mod:cc-plugin-diff"])
        self.assertEqual(document["stage_changed"], [{"key": "codex:feature:feature_00", "name": "feature_00",
                                                      "from": "under development", "to": "stable"}])
        self.assertEqual(document["unreviewed"], ["claude:setting:newSetting", "codex:feature:brand_new"])
        self.assertTrue(document["summary_line"].startswith(
            "surface watch: 2 unreviewed of 3 new, 1 removed, 1 stage change"), document["summary_line"])

    def test_new_settings_keys_carry_the_sources_that_hold_them(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.settings_extra = ["typedOnly", "inBoth"]
        upstream.reference_keys += ["documentedOnly", "inBoth"]
        document = watch.document("--network", upstream=upstream)
        self.assertEqual({item["name"]: item["sources"] for item in document["new"]},
                         {"documentedOnly": ["settings-reference.md"], "inBoth": ["sdk.d.ts", "settings-reference.md"],
                          "typedOnly": ["sdk.d.ts"]})
        held = document["coverage"]["key_sources"]["claude:setting"]
        self.assertEqual(held["settings-reference.md"]["only_here"], ["deprecatedSetting", "docsOnlySetting",
                                                                      "documentedOnly"])
        self.assertIn("typedOnly", held["sdk.d.ts"]["only_here"])
        self.assertEqual((held["sdk.d.ts"]["observed"], held["sdk.d.ts"]["baseline"]),
                         (len(FILLER_SETTINGS) + len(TRAP_SETTINGS) + 2, len(FILLER_SETTINGS) + len(TRAP_SETTINGS)))
        _, text, _ = watch.run("--dry-run", upstream=upstream)
        self.assertIn("new: claude:setting:documentedOnly (unreviewed) (from settings-reference.md)", text)

    def test_a_new_feature_flag_is_one_unreviewed_key_per_kind(self):
        # L1: profiles.*.features.<name> mirrors features.<name> and is no key of its own.
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.schema_override = json.dumps(codex_schema(
            features=[*(f"feature_{index:02d}" for index in range(25)), "brand_new_flag"])).encode()
        upstream.features["brand_new_flag"] = ("under development", False)
        document = watch.document("--network", upstream=upstream)
        self.assertEqual(document["unreviewed"], ["codex:config:features.brand_new_flag",
                                                  "codex:feature:brand_new_flag"])

    def test_an_unobserved_kind_is_left_out_of_the_diff(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        code, stdout, stderr = watch.run("--network", "--json", upstream=upstream, codex="none")
        self.assertEqual(code, 0, stderr)
        document = json.loads(stdout)
        self.assertEqual(document["removed"], [])
        self.assertEqual(document["coverage"]["kinds_not_observed"], {"codex:feature": "no codex binary found"})
        self.assertIsNone(document["coverage"]["counts"]["codex:feature"]["observed"])

    def test_write_baseline_refuses_an_unobserved_kind(self):
        watch, upstream = Watch(self), Upstream()
        code, _, stderr = watch.run("--network", "--write-baseline", upstream=upstream, codex="none")
        self.assertEqual(code, 1, stderr)
        self.assertIn("not observed: codex:feature", stderr)
        self.assertFalse(watch.baseline.exists())

    def test_an_sdk_that_lags_the_cli_is_read_from_the_previous_release_and_said_so(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.claude_tags["latest"] = "2.1.290"
        document = watch.document("--network", upstream=upstream)
        self.assertEqual(document["versions"]["claude_agent_sdk"],
                         {"version": "0.3.289", "claude_code_version": "2.1.289", "matched": False})
        self.assertTrue(any("no @anthropic-ai/claude-agent-sdk release names Claude Code 2.1.290" in note
                            for note in document["coverage"]["notes"]))


class ChangelogRunTests(unittest.TestCase):
    def test_codex_notes_come_from_the_release_list_when_the_tag_moves(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.codex_tag = "rust-v0.161.0"
        upstream.release_body = "## New Features\n\n- Newest feature\n"
        upstream.release_list = {"data": {"repository": {"releases": {"nodes": [
            {"tagName": "rust-v0.162.0-alpha.1", "isPrerelease": True, "isDraft": False, "description": "alpha"},
            {"tagName": "rust-v0.161.0", "isPrerelease": False, "isDraft": False,
             "description": "## New Features\n\n- Newest feature\n- Fixed a hook\n"},
            {"tagName": "rust-v0.160.1", "isPrerelease": False, "isDraft": False, "description": "- Added `x` setting\n"},
            {"tagName": "rust-v0.160.0", "isPrerelease": False, "isDraft": False, "description": "- Baseline\n"}]}}}}
        upstream.changelog = [("2.1.290", ["Added `CLAUDE_CODE_SOMETHING_NEW`", "Fixed y"]), *upstream.changelog]
        document = watch.document("--network", upstream=upstream)
        codex = document["changelog"]["codex"]
        self.assertEqual(codex["releases"], ["rust-v0.161.0", "rust-v0.160.1"])
        self.assertEqual((codex["entries"], codex["matching"], codex["complete"]), (3, 3, True))
        claude = document["changelog"]["claude"]
        self.assertEqual((claude["versions"], claude["entries"], claude["matching"]), (["2.1.290"], 2, 1))
        self.assertTrue(any(call[0] == "gh" and call[1][0] == "graphql" for call in upstream.calls))

    def test_a_failed_release_list_falls_back_to_the_latest_notes(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.codex_tag = "rust-v0.161.0"
        document = watch.document("--network", upstream=upstream)
        codex = document["changelog"]["codex"]
        self.assertEqual((codex["releases"], codex["complete"]), (["rust-v0.161.0"], False))
        self.assertIn("only the releases/latest notes", codex["note"])

    def test_no_release_list_call_while_the_tag_equals_the_baseline(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.calls.clear()
        watch.document("--network", upstream=upstream)
        self.assertEqual([call for call in upstream.calls if call[0] == "gh"], [("gh", (usw.CODEX_LATEST_PATH,))])


class WriteTests(unittest.TestCase):
    def test_latest_json_is_private_and_atomic(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        self.assertEqual(stat.S_IMODE(watch.latest.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(watch.state.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((watch.state / usw.CACHE_DIR).stat().st_mode), 0o700)
        leftovers = [path.name for path in watch.state.rglob("*") if path.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])
        document = json.loads(watch.latest.read_text(encoding="utf-8"))
        self.assertEqual(list(document), ["schema_version", "generated_at", "run_at", "versions", "new", "removed",
                                          "stage_changed", "changelog", "unreviewed", "coverage", "cross_check",
                                          "summary_line"])

    def test_a_write_that_fails_before_the_rename_keeps_the_earlier_file(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        before = watch.latest.read_bytes()
        upstream.settings_extra = ["changedSetting"]
        with mock.patch.object(usw.os, "replace", side_effect=OSError("simulated rename failure")):
            code, _, stderr = watch.run("--network", upstream=upstream)
        self.assertEqual(code, 1, stderr)
        self.assertIn("simulated rename failure", stderr)
        self.assertEqual(watch.latest.read_bytes(), before)
        self.assertEqual([path.name for path in watch.state.rglob("*.tmp")], [])

    def test_write_baseline_refuses_to_replace_without_force(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        before = watch.baseline.read_bytes()
        upstream.settings_extra = ["laterSetting"]
        code, _, stderr = watch.run("--network", "--write-baseline", upstream=upstream)
        self.assertEqual(code, 2, stderr)
        self.assertIn("pass --force", stderr)
        self.assertEqual(watch.baseline.read_bytes(), before)
        code, _, stderr = watch.run("--network", "--write-baseline", "--force", upstream=upstream)
        self.assertEqual(code, 0, stderr)
        self.assertIn("laterSetting", json.loads(watch.baseline.read_text(encoding="utf-8"))["kinds"]["claude:setting"])

    def test_the_baseline_holds_names_and_artifact_hashes_never_content(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        baseline = json.loads(watch.baseline.read_text(encoding="utf-8"))
        self.assertEqual(usw.validate_baseline(baseline), [])
        self.assertEqual(stat.S_IMODE(watch.baseline.stat().st_mode), 0o644)
        self.assertEqual(baseline["kinds"]["claude:mod"], sorted(MODS))
        self.assertEqual(baseline["source_counts"], {"claude:setting": {
            "sdk.d.ts": len(FILLER_SETTINGS) + len(TRAP_SETTINGS), "settings-reference.md": len(REFERENCE_KEYS) + 1}})
        self.assertEqual(len(baseline["kinds"]["claude:setting"]), len(FILLER_SETTINGS) + len(TRAP_SETTINGS) + 2)
        for source, entry in baseline["sources"].items():
            self.assertEqual(set(entry) - {"url", "command"}, {"version", "fetched_utc", "sha256", "bytes"}, source)
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(baseline["sources"]["codex-config-schema"]["url"], upstream.schema_url())
        self.assertEqual(baseline["sources"]["codex-config-schema"]["sha256"], sha256(upstream.schema_bytes()))
        self.assertNotIn("Browse older tasks", watch.baseline.read_text(encoding="utf-8"))

    def test_usage_errors_exit_2(self):
        watch = Watch(self)
        for arguments in (("--write-baseline", "--dry-run"), ("--force",), ("--json", "--summary"),
                          ("--check-dispositions", "--network"), ("--now", "yesterday")):
            with self.subTest(arguments=arguments):
                code, _, _ = watch.run(*arguments)
                self.assertEqual(code, 2)

    def test_a_state_directory_inside_the_checkout_is_refused(self):
        watch = Watch(self)
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = usw.main(["--root", str(watch.root), "--state-dir", str(watch.root / "state"), "--now", NOW])
        self.assertEqual(code, 2, stderr.getvalue())
        self.assertFalse((watch.root / "state").exists())

    def test_an_invalid_dispositions_catalog_or_missing_baseline_exits_1(self):
        watch, upstream = Watch(self), Upstream()
        code, _, stderr = watch.run("--network", upstream=upstream)
        self.assertEqual(code, 1, stderr)
        self.assertIn("baseline not found", stderr)
        watch.seed(self, upstream)
        watch.add_rows(row("claude:setting:x"), row("claude:setting:x"))
        code, _, stderr = watch.run("--network", upstream=upstream)
        self.assertEqual(code, 1, stderr)
        self.assertIn("duplicate key claude:setting:x", stderr)


class SummaryTests(unittest.TestCase):
    def test_the_summary_is_one_line_within_160_characters_ending_with_a_runnable_command(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.settings_extra = ["newSetting"]
        code, stdout, stderr = watch.run("--network", "--summary", upstream=upstream)
        self.assertEqual(code, 0, stderr)
        line = stdout.rstrip("\n")
        self.assertNotIn("\n", line)
        self.assertLessEqual(len(line), 160)
        command = line.split("; details: ", 1)[1]
        tokens = shlex.split(command)
        self.assertEqual(tokens[:3], ["python3", str(watch.script), "--dry-run"])
        # Runnable: the command, from an unrelated directory and with the same XDG_STATE_HOME, replays the cache this
        # run wrote (offline, the --now clock aside) and agrees.
        result = subprocess.run([sys.executable, *tokens[1:], "--json", "--now", NOW], capture_output=True,
                                text=True, timeout=120, cwd=tempfile.gettempdir(), stdin=subprocess.DEVNULL,
                                check=False, env=dict(os.environ, XDG_STATE_HOME=str(watch.xdg)))
        self.assertEqual(result.returncode, 0, result.stderr)
        replay = json.loads(result.stdout)
        self.assertEqual(replay["unreviewed"], ["claude:setting:newSetting"])

    def test_a_long_command_gives_way_to_cat_of_latest_json(self):
        candidates = ["python3 " + "x" * 140 + " --dry-run", "cat /tmp/state/latest.json"]
        line = usw.summary_line(["nothing new"], "(Claude Code 2.1.289, Codex 0.160.0)", candidates, None)
        self.assertTrue(line.endswith("; details: cat /tmp/state/latest.json"), line)
        self.assertLessEqual(len(line), 160)

    def test_no_fitting_command_is_a_usage_error_before_any_fetch(self):
        watch, upstream = Watch(self), Upstream()
        long_state = watch.root.parent / ("s" * 150)
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), upstream.patched():
            code = usw.main(["--root", str(watch.root), "--state-dir", str(long_state), "--network", "--dry-run",
                             "--now", NOW])
        self.assertEqual(code, 2, stderr.getvalue())
        self.assertEqual(upstream.calls, [])

    def test_counts_are_truncated_rather_than_the_command(self):
        line = usw.summary_line(["9999 unreviewed of 9999 new", "9999 removed", "9999 stage changes"], "(tail)",
                                ["python3 " + "y" * 80 + " --dry-run"], "partial cache")
        self.assertIn("...; details: python3 y", line)
        self.assertLessEqual(len(line), 160)
        self.assertTrue(line.endswith("y --dry-run"))


class CrossCheckTests(unittest.TestCase):
    def test_a_cross_check_failure_never_fails_the_run(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        code, stdout, stderr = watch.run("--network", "--cross-check", "--json", upstream=upstream)
        self.assertEqual(code, 0, stderr)
        crossed = json.loads(stdout)["cross_check"]
        self.assertEqual(crossed["claude"]["status"], "unavailable")
        self.assertEqual(crossed["codex"]["status"], "unavailable")

    def test_cross_check_compares_names_when_the_trackers_answer(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        settings = json.dumps({"claudeCodeVersion": "2.1.288", "facts": [
            {"path": "fillerSetting00"}, {"path": "policyHelper.path"}, {"path": "trackerOnly"}]}).encode()
        # configurableVariables holds plain names, the other groups {name, ...} objects (the tracker's v2.1.289 shape).
        environment = json.dumps({"configurableVariables": ["CLAUDECODE", "TRACKER_ONLY_VAR"],
                                  "supplements": [{"name": "TRACKER_SUPPLEMENT", "scope": "configurable-standard"}],
                                  "providedToHooks": []}).encode()
        lifecycle = json.dumps({"codex_cli_version": "codex-cli 0.160.0", "cli_features": [
            {"key": "feature_00", "stage": "stable", "enabled": False}, {"key": "tracker_feature", "stage": "stable"}]})
        release = {"tag_name": "v2.1.288", "assets": [
            {"name": "settings.catalog.json", "browser_download_url": "https://github.com/amitray007/claude-code-schema/releases/download/v2.1.288/settings.catalog.json", "digest": "sha256:" + sha256(settings)},
            {"name": "environment.catalog.json", "browser_download_url": "https://github.com/amitray007/claude-code-schema/releases/download/v2.1.288/environment.catalog.json", "digest": "sha256:" + sha256(environment)}]}
        original_get, original_gh = upstream.http_get, upstream.gh_api

        def http_get(url, timeout=60):
            extra = {release["assets"][0]["browser_download_url"]: settings,
                     release["assets"][1]["browser_download_url"]: environment,
                     usw.CHENRUI_LIFECYCLE_URL: lifecycle.encode()}
            return extra[url] if url in extra else original_get(url, timeout)

        def gh_api(arguments, timeout=60):
            if arguments[0] == usw.AMIT_LATEST_PATH:
                return json.dumps(release).encode(), None
            return original_gh(arguments, timeout)

        upstream.http_get, upstream.gh_api = http_get, gh_api
        crossed = watch.document("--network", "--cross-check", upstream=upstream)["cross_check"]
        self.assertEqual(crossed["claude"]["status"], "compared")
        self.assertEqual(crossed["claude"]["claude:setting"]["only_theirs"], ["trackerOnly"])
        self.assertEqual(crossed["claude"]["claude:env"]["only_theirs"], ["TRACKER_ONLY_VAR", "TRACKER_SUPPLEMENT"])
        self.assertEqual(crossed["claude"]["claude:env"]["common"], 1)
        self.assertEqual(crossed["codex"]["codex:feature"]["only_theirs"], ["tracker_feature"])
        self.assertEqual(crossed["codex"]["codex:feature"]["stage_differs"], ["feature_00"])


class ProbeTests(unittest.TestCase):
    def test_the_probe_runs_codex_with_an_empty_temporary_home(self):
        with tempfile.TemporaryDirectory(dir=short_temp_base()) as scratch:
            record = Path(scratch) / "environment.json"
            fake = Path(scratch) / "codex"
            fake.write_text("#!" + sys.executable + "\nimport json, os, sys\n"
                            f"record = {str(record)!r}\n"
                            "if sys.argv[1:] == ['--version']:\n    print('codex-cli 9.9.9'); sys.exit(0)\n"
                            "home = os.environ['CODEX_HOME']\n"
                            "json.dump({'env': sorted(os.environ), 'home': os.environ['HOME'], 'codex_home': home,"
                            " 'listing': os.listdir(home)}, open(record, 'w'))\n"
                            "print('alpha_feature                  under development  false')\n", encoding="utf-8")
            fake.chmod(0o700)
            stdout, version = usw.probe_codex(str(fake))
            seen = json.loads(record.read_text(encoding="utf-8"))
        self.assertEqual(version, "codex-cli 9.9.9")
        self.assertIn(b"alpha_feature", stdout)
        self.assertEqual(seen["home"], seen["codex_home"])
        self.assertNotEqual(seen["home"], str(Path.home()))
        self.assertFalse(Path(seen["codex_home"]).exists())  # removed after the probe
        self.assertEqual(set(seen["env"]) - {"PATH", "HOME", "CODEX_HOME", "LANG", "NO_COLOR", "TERM", "LC_CTYPE",
                                             "PWD", "SHLVL", "_"}, set())


# ----------------------------------------------------------------------------------------------- dispositions


def valid_catalog(rows=()) -> dict:
    catalog = json.loads((ROOT / usw.DISPOSITIONS_PATH).read_text(encoding="utf-8"))
    catalog["rows"] = list(rows)
    return catalog


class DispositionsTests(unittest.TestCase):
    def test_the_check_mode_validates_without_fetching_or_a_state_directory(self):
        watch = Watch(self)
        with mock.patch.object(usw, "http_get", side_effect=AssertionError), \
                mock.patch.object(usw, "gh_api", side_effect=AssertionError):
            code, stdout, stderr = watch.run("--check-dispositions")
        self.assertEqual(code, 0, stderr)
        self.assertRegex(stdout, r"valid, \d+ rows")      # the shipped catalog: empty at first, then the reviewed rows
        self.assertFalse(watch.state.exists())

    def test_each_rule_violation_is_reported(self):
        cases = {
            "duplicate key": ([row("claude:setting:a"), row("claude:setting:a")], "duplicate key claude:setting:a"),
            "bad key": ([row("setting autoUpdates")], "key must look like"),
            "bad disposition": ([row("claude:setting:a", "maybe")], "disposition must be one of"),
            "long reason": ([row("claude:setting:a", reason="x" * 161)], "reason must be one line"),
            "two-line reason": ([row("claude:setting:a", reason="a\nb")], "reason must be one line"),
            "bad source": ([row("claude:setting:a", source="somewhere")], "source must be a URL or path:line"),
            "missing carrier": ([row("claude:setting:a", "enabled", carrier=None)], "carrier is required"),
            "missing overturn": ([row("claude:setting:a", overturn=None)], "overturn is required"),
            "bad time": ([row("claude:setting:a", reviewed_utc="2026-10-04")], "reviewed_utc must be"),
            "unknown field": ([dict(row("claude:setting:a"), extra=1)], "unknown field(s) extra"),
            "missing field": ([{key: value for key, value in row("claude:setting:a").items() if key != "scope"}],
                              "missing scope"),
        }
        for label, (rows, message) in cases.items():
            with self.subTest(case=label):
                errors = usw.validate_dispositions(valid_catalog(rows))
                self.assertTrue(any(message in error for error in errors), errors)

    def test_rules_must_document_every_value_and_unknown_top_level_fields_fail(self):
        catalog = valid_catalog()
        del catalog["rules"]["defer-user"]
        catalog["surprise"] = True
        errors = usw.validate_dispositions(catalog)
        self.assertIn("dispositions: rules['defer-user'] must document that value", errors)
        self.assertIn("dispositions: unknown top-level field 'surprise'", errors)

    def test_baseline_unreviewed_rows_may_omit_overturn_and_carrier(self):
        errors = usw.validate_dispositions(valid_catalog([row("codex:config:x.y", "baseline-unreviewed",
                                                              overturn=None)]))
        self.assertEqual(errors, [])

    def test_twelve_hundred_rows_validate_well_under_a_second(self):
        rows = [row(f"{'claude' if index % 2 else 'codex'}:kind-{index % 7}:name_{index}",
                    usw.DISPOSITIONS[index % len(usw.DISPOSITIONS)],
                    source=f"docs/upstream-surface-watch.md:{index + 1}") for index in range(1200)]
        catalog = valid_catalog(rows)
        started = time.perf_counter()
        errors = usw.validate_dispositions(catalog)
        elapsed = time.perf_counter() - started
        self.assertEqual(errors, [])
        self.assertLess(elapsed, 1.0)
        catalog["rows"].append(dict(rows[17]))
        self.assertEqual([error for error in usw.validate_dispositions(catalog) if "duplicate" in error],
                         [f"rows[1200]: duplicate key {rows[17]['key']} (first at rows[17])"])

    def test_a_disposition_row_removes_a_new_name_from_the_unreviewed_list(self):
        watch, upstream = Watch(self), Upstream()
        watch.seed(self, upstream)
        upstream.settings_extra = ["decidedSetting", "openSetting"]
        watch.add_rows(row("claude:setting:decidedSetting", "default-on"))
        document = watch.document("--network", upstream=upstream)
        self.assertEqual(document["unreviewed"], ["claude:setting:openSetting"])


# ----------------------------------------------------------------------------------------------- negative controls


def mutant_first_brace(text: str) -> list[str]:
    """Defect: the interface body ends at the first '}' after the anchor, as a non-greedy regex reads it."""
    body = re.search(r"interface Settings \{(.*?)\}", text, re.S).group(1)
    return sorted({match.group(1) for match in re.finditer(r"(?m)^\s*['\"]?([$A-Za-z_][\w$-]*)['\"]?\??\s*:", body)})


def mutant_regex_lines(text: str) -> list[str]:
    """A genuinely different parser, regular expressions only and no tokenizer: the body runs from the anchor to the
    first column-0 '}', and a member is any line that starts with a name followed by '?', ':', '(' or '<'. Defects:
    it is blind to nesting and to what a line continues, so nested members (path, timeoutMs), a construct signature
    (new) and a type on the line after its colon (Partial) all read as keys."""
    body = re.search(r"interface Settings \{(.*?)^\}", text, re.S | re.M).group(1)
    return sorted({match.group(2) for match in re.finditer(
        r"(?m)^[ \t]*(?:readonly[ \t]+)?(['\"]?)([$\w-]+)\1[ \t]*\??[ \t]*[:(<]", body)})


def mutant_counts_comments(text: str) -> list[str]:
    """Defect: comments are not skipped, so text inside a JSDoc block is read as members."""
    uncommented = re.sub(r"(?m)^(\s*)\*(?!/)", r"\1 ", re.sub(r"/\*\*?|\*/|//", " ", text))
    return sorted(set(usw.interface_members(uncommented, usw.SETTINGS_ANCHOR.search(uncommented).end())))


def mutant_single_line_hooks(text: str) -> list[str]:
    """Defect: HOOK_EVENTS is read as single-quoted names on its declaration line only."""
    line = next(line for line in text.splitlines() if "HOOK_EVENTS: readonly" in line)
    return sorted(set(re.findall(r"'([A-Za-z]+)'", line)))


def _flatten_unbounded(schema: dict) -> list[str]:
    """The real flattener with the count bounds lifted, so a mutated schema is compared by content, not by bound."""
    with mock.patch.dict(usw.BOUNDS, {"codex:config": (0, 10**6), "codex:config/top-level": (0, 10**6),
                                      "codex:config/features": (0, 10**6)}):
        return usw.flatten_codex_schema(json.dumps(schema).encode())


class NegativeControlTests(unittest.TestCase):
    """Synthetic negative controls: each mutant agrees with the real parser on a plain fixture without its trap
    (so it is a plausible parser) and must fail the trap fixture that the real parser passes."""

    def test_each_settings_mutant_fails_the_trap_fixture_the_real_parser_passes(self):
        plain = sdk_dts(interface=PLAIN_INTERFACE, comments=False)
        trap = sdk_dts()
        self.assertEqual(usw.parse_settings_keys(plain), sorted(FILLER_SETTINGS))
        self.assertEqual(set(usw.parse_settings_keys(trap)), {*TRAP_SETTINGS, *FILLER_SETTINGS})
        for mutant in (mutant_first_brace, mutant_regex_lines, mutant_counts_comments):
            with self.subTest(mutant=mutant.__name__):
                self.assertEqual(mutant(plain), sorted(FILLER_SETTINGS))
                self.assertNotEqual(set(mutant(trap)), {*TRAP_SETTINGS, *FILLER_SETTINGS})

    def test_each_mutant_misses_what_its_defect_predicts(self):
        trap = sdk_dts()
        self.assertNotIn("afterNested", mutant_first_brace(trap))
        self.assertTrue({"path", "timeoutMs", "intervalMs", "new", "Partial"} <= set(mutant_regex_lines(trap)))
        self.assertTrue({"key", "Default"} & set(mutant_counts_comments(trap)))

    def test_the_hook_mutant_fails_the_multiline_fixture(self):
        self.assertEqual(mutant_single_line_hooks(sdk_dts(multiline_hooks=False)), sorted(HOOKS))
        self.assertNotEqual(mutant_single_line_hooks(sdk_dts()), sorted(HOOKS))
        self.assertEqual(usw.parse_hook_events(sdk_dts()), sorted(HOOKS))

    def test_the_flatten_mutant_fails_the_ref_fixture(self):
        # Mutant: $ref not followed (the definitions emptied), so every property behind a definition is lost.
        body = json.dumps(codex_schema()).encode()
        self.assertEqual(set(usw.flatten_codex_schema(body)), expected_paths())
        broken = dict(json.loads(body), definitions={})
        with self.assertRaisesRegex(usw.AnchorMissing, r"config-schema\.json:\$ref"):
            _flatten_unbounded(broken)

        # Keep the original missing-path control even for a mutant that drops dangling references to evade integrity.
        def without_refs(node):
            if isinstance(node, dict):
                return {key: without_refs(value) for key, value in node.items() if key != "$ref"}
            return [without_refs(item) for item in node] if isinstance(node, list) else node

        missed = expected_paths() - set(_flatten_unbounded(without_refs(broken)))
        self.assertTrue({"tui.theme", "mcp_servers.*.command", "hooks.PreToolUse[].matcher"} <= missed)


# ----------------------------------------------------------------------------------------------- committed catalogs


class TestCommittedCatalogs(unittest.TestCase):
    """Repository integration checks of the two committed catalogs (not fixtures)."""

    def test_the_committed_dispositions_catalog_validates(self):
        code = usw.main(["--check-dispositions"])
        self.assertEqual(code, 0)

    def test_the_committed_baseline_is_a_valid_names_only_snapshot(self):
        baseline = json.loads((ROOT / usw.BASELINE_PATH).read_text(encoding="utf-8"))
        self.assertEqual(usw.validate_baseline(baseline), [])
        for kind in usw.KINDS:
            low, high = usw.BOUNDS[kind]
            self.assertTrue(low <= len(baseline["kinds"][kind]) <= high, kind)
            self.assertEqual(baseline["counts"][kind], len(baseline["kinds"][kind]))
        self.assertEqual([name for name, _ in baseline["stages"][usw.STAGED_KIND]],
                         baseline["kinds"][usw.STAGED_KIND])
        for source, entry in baseline["sources"].items():
            self.assertTrue(entry.get("url", "https://").startswith("https://"), source)
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(entry["fetched_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


if __name__ == "__main__":
    unittest.main()
