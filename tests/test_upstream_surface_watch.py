"""scripts/upstream_surface_watch.py against synthetic reduced fixtures (local integration checks, not upstream tests).

Every upstream artifact here is a small synthetic stand-in shaped like the real one (npm dist-tags and packument, the
Agent SDK's sdk.d.ts, the env-vars and mods pages, the Codex release JSON and config-schema.json, `codex features
list`, CHANGELOG.md, the GraphQL release list); none is a recorded observation. A fake replaces the network layer
(http_get, gh_api, probe_codex), and the offline tests make socket creation raise. NegativeControlTests run small mutant
parsers, each with one known defect, and require every mutant to fail a fixture that the real parser passes, so a
parser regression cannot pass silently (precedent: a regex that missed `$` in minified identifiers read 15 of 17
values with exit 0). TestCommittedCatalogs checks the two committed catalogs; it is the only test that reads repository
data rather than fixtures.
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
from pathlib import Path
from unittest import mock

from scripts import upstream_surface_watch as usw

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-04T12:00:00Z"
CODEX_BIN = "/synthetic/bin/codex"

# ----------------------------------------------------------------------------------------------- fixture builders

FILLER_SETTINGS = [f"fillerSetting{index:02d}" for index in range(60)]
TRAP_SETTINGS = ["$schema", "quoted-key", "double-quoted", "policyHelper", "afterNested", "literal", "onEvent",
                 "frozen", "readonly", "conditional", "resolve"]
HOOKS = ["PreToolUse", "PostToolUse", "Notification", "UserPromptSubmit", "SessionStart", "SessionEnd", "Stop",
         "SubagentStart", "SubagentStop", "PreCompact", "PostCompact", "ConfigChange"]
MODS = ["cc-plugin-agents-md", "cc-plugin-diff", "cc-plugin-you-should-know"]
ENV_NAMES = [f"CLAUDE_CODE_SYNTHETIC_{index:03d}" for index in range(110)]
FEATURES = {f"feature_{index:02d}": (("under development", "stable", "removed")[index % 3], index % 3 == 1)
            for index in range(40)}
CLAUDE_TAGS = {"stable": "2.1.285", "latest": "2.1.289", "next": "2.1.289"}
CODEX_TAGS = {"latest": "0.160.0", "alpha": "0.162.0-alpha.12", "linux-x64": "0.160.0-linux-x64"}

# The traps: braces and "word:" text inside JSDoc, `$` and quoted keys, a nested object type followed by more keys, a
# string literal holding } and ;, a template literal type, a function type with an object parameter, modifiers, an
# index signature, a conditional type and a method. An indented interface of the same name inside a namespace and a
# longer interface name must not count.
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
    definitions = {
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


STRUCTURED_PATHS = {"features", "tui", "tui.theme", "tui.notifications", "tui.notifications.enabled", "mcp_servers",
                    "mcp_servers.*.command", "mcp_servers.*.env", "hooks", "hooks.PreToolUse",
                    "hooks.PreToolUse[].matcher", "hooks.PreToolUse[].hooks", "hooks.PreToolUse[].hooks[].command",
                    "hooks.PreToolUse[].hooks[].timeout", "model", "model.name", "model.fallback", "bulk"}


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
    def test_settings_keys_survive_comments_quotes_dollar_nesting_literals_and_modifiers(self):
        keys = usw.parse_settings_keys(sdk_dts())
        self.assertEqual(set(keys), {*TRAP_SETTINGS, *FILLER_SETTINGS})
        self.assertEqual(keys, sorted(keys))
        for absent in ("path", "timeoutMs", "intervalMs", "kind", "k", "innerOnly", "notASettingsKey", "key",
                       "Example", "Default", "event", "detail"):
            self.assertNotIn(absent, keys)

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


# ----------------------------------------------------------------------------------------------- run tests


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
        self.assertEqual(list(document), ["schema_version", "generated_at", "versions", "new", "removed",
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
        line = usw.summary_line(["nothing new"], "(Claude Code 2.1.289, Codex 0.160.0)", candidates, False)
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
                                ["python3 " + "y" * 90 + " --dry-run"], True)
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
        environment = json.dumps({"configurableVariables": [{"name": "CLAUDECODE"}, {"name": "TRACKER_ONLY_VAR"}],
                                  "supplements": [], "providedToHooks": []}).encode()
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
        self.assertEqual(crossed["claude"]["claude:env"]["only_theirs"], ["TRACKER_ONLY_VAR"])
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
        self.assertIn("valid, 0 rows", stdout)
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


def mutant_plain_identifiers(text: str) -> list[str]:
    """Defect: a key must be a plain identifier ([A-Za-z_][A-Za-z0-9_]*), so `$` and quoted keys are lost."""
    with mock.patch.object(usw, "IDENT", re.compile(r"[A-Za-z_][A-Za-z0-9_]*")):
        keys = usw.interface_members(text, usw.SETTINGS_ANCHOR.search(text).end())
    return sorted(key for key in set(keys) if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key))


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
        for mutant in (mutant_first_brace, mutant_plain_identifiers, mutant_counts_comments):
            with self.subTest(mutant=mutant.__name__):
                self.assertEqual(mutant(plain), sorted(FILLER_SETTINGS))
                self.assertNotEqual(set(mutant(trap)), {*TRAP_SETTINGS, *FILLER_SETTINGS})

    def test_each_mutant_misses_what_its_defect_predicts(self):
        trap = sdk_dts()
        self.assertNotIn("afterNested", mutant_first_brace(trap))
        self.assertTrue({"$schema", "quoted-key", "double-quoted"}.isdisjoint(mutant_plain_identifiers(trap)))
        self.assertTrue({"key", "Default"} & set(mutant_counts_comments(trap)))

    def test_the_hook_mutant_fails_the_multiline_fixture(self):
        self.assertEqual(mutant_single_line_hooks(sdk_dts(multiline_hooks=False)), sorted(HOOKS))
        self.assertNotEqual(mutant_single_line_hooks(sdk_dts()), sorted(HOOKS))
        self.assertEqual(usw.parse_hook_events(sdk_dts()), sorted(HOOKS))

    def test_the_flatten_mutant_fails_the_ref_fixture(self):
        # Mutant: $ref not followed (the definitions emptied), so every property behind a definition is lost.
        body = json.dumps(codex_schema()).encode()
        self.assertEqual(set(usw.flatten_codex_schema(body)), expected_paths())
        missed = expected_paths() - set(_flatten_unbounded(dict(json.loads(body), definitions={})))
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
