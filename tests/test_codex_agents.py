"""Structural validation of custom-agent instruction payloads.

Sources: openai/codex rust-v0.157.1, codex-rs/agent-roles/src/agent_role_config.rs
and codex-rs/core/src/agent/role.rs; rtk-ai/rtk v0.50.0,
hooks/rtk-awareness-full.md. These are local checks, not spawned-agent acceptance.
"""

import hashlib
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "examples" / "codex-native" / "agents"
UPSTREAM_MARKER = "<!-- native-agent-stack:rtk-upstream rtk-ai/rtk v0.50.0 hooks/rtk-awareness-full.md, verbatim -->\n"
EXCEPTIONS_MARKER = "<!-- native-agent-stack:rtk-exceptions -->\n"
# F4 is the RTK part of the managed block: the upstream text and its marked exceptions. The jCodeMunch section after
# them is not F4, and these roles do not carry it (docs/decisions/2026-09-27-token-lanes-subagent-start.md, jCodeMunch
# route addendum).
JCODEMUNCH_MARKER = "<!-- native-agent-stack:jcodemunch "
# Byte identity of upstream hooks/rtk-awareness-full.md, also checked by the worker-lane tests.
RTK_SHA256 = "278274ef3d08c858d4247cc91419c4d74ef922b95719e987b22e896aef10e1fc"


class CustomAgentInstructionsTests(unittest.TestCase):
    def test_every_custom_agent_carries_verbatim_f4_in_developer_instructions(self):
        template = (ROOT / "adoption/templates/codex.AGENTS.template.md").read_text(encoding="utf-8")
        expected = UPSTREAM_MARKER + template.split(UPSTREAM_MARKER, 1)[1].split(
            "<!-- native-agent-stack:codex-user-instructions:end -->", 1)[0].split("\n" + JCODEMUNCH_MARKER, 1)[0]
        paths = sorted(AGENTS.glob("*.toml"))
        self.assertEqual({path.stem for path in paths},
                         {"evidence-reviewer", "isolated-builder", "semantic-evidence-reviewer"})
        for path in paths:
            with self.subTest(agent=path.stem):
                role = tomllib.loads(path.read_text(encoding="utf-8"))
                instructions = role["developer_instructions"]
                self.assertIn(expected, instructions)
                self.assertEqual(instructions.count(UPSTREAM_MARKER), 1)
                self.assertEqual(instructions.count(EXCEPTIONS_MARKER), 1)
                # The blank separator before the exception marker is outside the upstream file.
                upstream = instructions.split(UPSTREAM_MARKER, 1)[1].split("\n" + EXCEPTIONS_MARKER, 1)[0]
                self.assertEqual(hashlib.sha256(upstream.encode("utf-8")).hexdigest(), RTK_SHA256)
                self.assertFalse(any(line.startswith("@") for line in instructions.splitlines()))


if __name__ == "__main__":
    unittest.main()
