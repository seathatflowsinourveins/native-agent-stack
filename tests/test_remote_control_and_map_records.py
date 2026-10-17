"""The records of the 2026-10-17 client wiring say what the map and the settings do, and cite what holds them (PR #1242 fold, B7-B10).

B7: each setting of the authorization bundle has its own effect, as upstream gives it (cross-session-messaging.md lines 195
and 203-206, permission-modes.md line 571): `bypassPermissions` alone removes the tool-call prompts, `crossSessionInbound =
"accept"` only delivers messages that Claude Code would otherwise hold, in two cases.
B8: the addendum that first wrote remoteControlAtStartup states the final rule (its own opt-in), not the first one.
B9: the dispositions row for remoteControlAtStartup cites the amendment that narrows the decision and the host read it is true as.
B10: the map's SocratiCode and context-mode launch commands and SocratiCode's embedder pins are recorded in an addendum.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISION = ROOT / "docs/decisions/2026-10-17-new-wsl-remote-control-at-startup.md"
RECORD = ROOT / "docs/decisions/2026-10-02-new-wsl-client-configuration.md"
MAP = ROOT / "adoption/new-wsl/client-config-map.json"
DISPOSITIONS = ROOT / "catalogs/foundation/upstream-surface-dispositions.json"
G3_RULING_UTC = "2026-10-17T03:11:03Z"      # the CC's ruling G3 (hcom #14261), the time the amendment's wording dates from
OPTION = "--with-remote-control-at-startup"
ROW_PREFIX = "| `claude/settings/setting/remoteControlAtStartup`"
INBOUND_ROW_PREFIX = "| `claude/settings/setting/crossSessionInbound`"


def read(path):
    return path.read_text(encoding="utf-8")


def flat(text):
    return " ".join(text.split())


def section(text, heading):
    """The text from a heading line to the next line that starts with '## '."""
    start = text.index(heading + "\n")
    end = text.find("\n## ", start + 1)
    return text[start:end if end != -1 else len(text)]


def map_entry(piece):
    return next(entry for entry in json.loads(read(MAP))["entries"] if piece in entry["match"])


class AuthorizationEffectsTests(unittest.TestCase):
    def test_the_decision_gives_each_setting_its_own_effect_from_upstream(self):
        """B7: the no-prompt part comes from bypassPermissions alone; accept is about messages; neither is said to come from both."""
        text = flat(section(read(DECISION), "## Why authorization"))
        self.assertNotIn("Together they make Remote Control", text)
        self.assertIn("https://code.claude.com/docs/en/permission-modes.md, lines 571 and 573", text)
        self.assertIn("lines 195 and 203-206", text)
        # Delta B3: permission-modes.md:573 follows :571 with the actions no mode auto-approves, which still prompt.
        self.assertIn("except that \"the actions no mode auto-approves still prompt in this mode\" (line 573)", text)
        self.assertIn("run with no prompt, apart from the actions no mode auto-approves,", text)
        self.assertIn("`bypassPermissions` \"disables permission prompts and safety checks so tool calls execute immediately\"", text)
        self.assertIn("It alone makes a turn started from claude.ai/code or the Claude app run its tool calls with no prompt", text)
        self.assertIn("`crossSessionInbound = \"accept\"` decides only whether a message from the user's other sessions is "
                      "delivered to Claude", text)
        for case in ("a receiving session that prompts for permissions holds one when the sender identifies itself as bypassing",
                     "a receiving session that bypasses holds each one unless the sender also bypasses"):
            self.assertIn(case, text)
        self.assertIn("`accept` delivers both. It changes no tool call's prompting.", text)
        self.assertIn("`remoteControlAtStartup: true` starts the Remote Control bridge in each interactive session", text)

    def test_the_g3_amendment_says_the_bundle_still_writes_accept_and_what_that_does(self):
        text = flat(section(read(DECISION), "## Amendment (2026-10-17): a separate opt-in inside the authorization class"))
        self.assertIn("The authorization bundle still writes `crossSessionInbound = \"accept\"`", text)
        self.assertIn("both when a prompting session receives from a bypassing one and when a bypassing session receives from a "
                      "non-bypassing one", text)
        self.assertIn("It does not make Remote Control's tool calls run without a prompt; `bypassPermissions` does that.", text)
        self.assertIn("Writing the bundle without the new option leaves Remote Control off and `accept` on.", text)

    def test_the_maps_reason_and_the_addenda_tables_name_both_hold_cases(self):
        wiring = map_entry("claude/settings/setting/crossSessionInbound")["wiring"]
        self.assertTrue(wiring.startswith("authorization:"))
        reason = wiring.removeprefix("authorization:")
        for part in ("cross-session-messaging.md:195", ":203-206",
                     "a session that prompts holds a message from a session that bypasses permission prompts",
                     "a session that bypasses holds a message from a session that does not",
                     "\"accept\" delivers both", "whether tool calls prompt is permissions.defaultMode's effect"):
            self.assertIn(part, reason)
        self.assertNotIn("without the approval hold that otherwise applies to a sender that is not in bypass mode", reason)
        # Every table of this pull request's 2026-10-17 addenda repeats the map's reason, not the earlier one-case form.
        text = read(RECORD)
        first = text.index("## Addendum 2026-10-17: ai-memory 3.1.0's client wiring")
        rows = [line for line in text[first:].splitlines() if line.startswith(INBOUND_ROW_PREFIX)]
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row.split(" | ")[3], reason, row[:80])


class RemoteControlAddendaTests(unittest.TestCase):
    def test_the_first_remote_control_addendum_states_the_final_rule(self):
        """B8: the addendum that first wrote the key with the bundle alone is superseded by the next one; it says so, and its
        text and table row state the final rule (the key needs the option as well)."""
        text = read(RECORD)
        first = flat(section(text, "## Addendum 2026-10-17: Remote Control at startup"))
        self.assertIn("rendered and written only with `--with-authorization-settings` and `--with-remote-control-at-startup` together", first)
        self.assertIn("This addendum first wrote the key with the bundle alone", first)
        self.assertNotIn("rendered and written only with `--with-authorization-settings` and never", first)
        later = section(text, "## Addendum 2026-10-17: Remote Control at startup becomes its own opt-in")
        for block in (section(text, "## Addendum 2026-10-17: Remote Control at startup"), later):
            rows = [line for line in block.splitlines() if line.startswith(ROW_PREFIX)]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].rstrip("|").rsplit("|", 1)[1].strip(), f"`{OPTION}`", rows[0][:90])


class DispositionsRowTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads(read(DISPOSITIONS))
        self.row = next(row for row in self.document["rows"] if row["key"] == "claude:setting:remoteControlAtStartup")

    def test_the_row_cites_the_amendment_lines_that_narrow_the_decision(self):
        """B9: the row cited decision :14, the first form, which the amendment narrows."""
        match = re.fullmatch(r"(?P<path>docs/decisions/[\w.-]+\.md):(?P<first>\d+)-(?P<last>\d+)", self.row["source"])
        self.assertIsNotNone(match, self.row["source"])
        self.assertEqual(match["path"], DECISION.relative_to(ROOT).as_posix())
        lines = read(DECISION).splitlines()
        first, last = int(match["first"]), int(match["last"])
        self.assertEqual(lines[first - 1], "## Amendment (2026-10-17): a separate opt-in inside the authorization class")
        cited = "\n".join(lines[first - 1:last])
        self.assertIn("**Separately opt-in, default off.**", cited)
        self.assertIn("SEPARATE_OPT_INS", cited)
        self.assertLess(last, len(lines))
        self.assertTrue(lines[last].startswith("- **Why.**"), lines[last][:40])    # the cited lines end with the opt-in bullet

    def test_the_row_is_dated_after_the_wording_it_uses_and_labels_enabled_as_the_host_read(self):
        self.assertGreater(self.row["reviewed_utc"], G3_RULING_UTC)
        self.assertEqual(self.row["scope"], "NativeHorizonNY")
        self.assertEqual(self.row["disposition"], "enabled")
        self.assertIn("host read", self.row["reason"])
        self.assertIn("default is off", self.row["reason"])
        self.assertIn("separate opt-in", self.row["reason"])

    def test_the_whole_catalog_still_validates(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import upstream_surface_watch as watch
        finally:
            sys.path.pop(0)
        self.assertEqual(watch.validate_dispositions(self.document), [])


class MapChangesAreRecordedTests(unittest.TestCase):
    def test_the_socraticode_and_context_mode_commands_and_embedder_pins_have_an_addendum(self):
        """B10: the map overrides the Node launcher of SocratiCode and context-mode and pins SocratiCode's embedder and width;
        an addendum of 2026-10-17 names each piece and value."""
        addendum = flat(section(read(RECORD),
                                "## Addendum 2026-10-17: SocratiCode and context-mode launch commands, and SocratiCode's embedder pins"))
        claude = map_entry("claude/mcp/server/socraticode")["override"]
        shim = claude["command"]
        self.assertEqual(shim, "${HOME}/.local/share/mise/shims/node")
        pieces = {"codex/config/mcp_servers.socraticode.command": shim,
                  "codex/config/mcp_servers.context-mode.command": shim,
                  "codex/config/mcp_servers.socraticode.env.EMBEDDING_MODEL": claude["env"]["EMBEDDING_MODEL"],
                  "codex/config/mcp_servers.socraticode.env.EMBEDDING_DIMENSIONS": claude["env"]["EMBEDDING_DIMENSIONS"]}
        for piece, value in pieces.items():
            self.assertEqual(map_entry(piece)["override"], value, piece)
            self.assertIn(f"`{piece}`" if piece.endswith(("command",)) else piece.rsplit(".", 1)[1], addendum)
        self.assertIn(f"`{shim}`", addendum)
        self.assertIn(f"`EMBEDDING_MODEL = {claude['env']['EMBEDDING_MODEL']}`", addendum)
        self.assertIn(f"`EMBEDDING_DIMENSIONS = {claude['env']['EMBEDDING_DIMENSIONS']}`", addendum)
        for source in ("adoption/bootstrap-linux.sh:370-383", "dist/services/provider-lmstudio.js:10", "`:262`",
                       "README.md:116", "2a4f9cb5", "jdx/mise@bc11f90c"):
            self.assertIn(source, addendum)
        # The install plan's embedder is not the host's: recorded as a gap that goes to the follow-up, not changed here.
        self.assertIn("Qwen3-Embedding-0.6B through Ollama", addendum)
        self.assertIn("client-configuration follow-up", addendum)
        plan = read(ROOT / "evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json").splitlines()
        self.assertIn("Qwen3-Embedding-0.6B through Ollama", plan[1169])


if __name__ == "__main__":
    unittest.main()
