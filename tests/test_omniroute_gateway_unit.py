"""Structural tests for the OmniRoute gateway systemd --user unit template.

Offline text checks only, in the style of test_token_report_refresh_units.py. Nothing here loads, starts, enables or
verifies a unit with a live systemd manager; `systemd-analyze --user verify` on a rendered copy is a separate, manual
acceptance check. The template must render to the unit recorded as installed on the workstation
(evidence/artifacts/omniroute-gateway-20260927/omniroute.service), apart from its Description= and one documented
extra line. The unit text holds no secret, names exactly one EnvironmentFile= and gives every Environment= line a reason
comment. A text test cannot see what a user service inherits from the user manager's environment; the template's header
says how to keep credentials out of it. Each check is a helper function that a planted violation must fail (the
discriminating controls at the end).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "adoption/templates/systemd/omniroute.service"
INSTALLED = ROOT / "evidence/artifacts/omniroute-gateway-20260927/omniroute.service"
DECISION = ROOT / "docs/decisions/2026-09-27-omniroute-account-pool.md"

# The workstation's values, as the recorded installed unit shows them.
WORKSTATION = {
    "OMNIROUTE_PREFIX": "%h/.local/share/codex-ecosystem/tools/omniroute-3.8.51-a58000c7-pr14904-pr13788",
    "NODE_PREFIX": "%h/.local/share/codex-ecosystem/tools/node-24.21.0",
    "CODEX_CLIENT_VERSION": "0.157.1",
}
# The one directive the template adds on purpose (see its header); the installed environment file sets the same value.
TEMPLATE_ONLY = {"Environment=OMNIROUTE_SERVER_HOST=127.0.0.1"}
ENVIRONMENT_NAMES = {
    "PATH", "OMNIROUTE_SERVER_HOST", "OMNIROUTE_MEMORY_MB", "CODEX_CLIENT_VERSION", "STREAM_READINESS_TIMEOUT_MS",
    "STREAM_READINESS_MAX_TIMEOUT_MS", "STREAM_ACTIVE_TIMEOUT_MS", "CLI_ALLOW_CONFIG_WRITES",
}
PLACEHOLDER = re.compile(r"@([A-Z][A-Z0-9_]*)@")
SECRET_LIKE = re.compile(r"SECRET|PASSWORD|TOKEN|COOKIE|_KEY\b|^KEY\b")
EXEC_START = "ExecStart=@OMNIROUTE_PREFIX@/bin/omniroute serve --port 20128 --no-open --no-tray"


def directives(text: str) -> list[str]:
    """Non-blank, non-comment lines, in order (section headers included)."""
    return [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def render(text: str, values: dict[str, str]) -> str:
    """Substitute the known placeholders; header prose such as "@NAME@" is left as it is."""
    return PLACEHOLDER.sub(lambda match: values.get(match.group(1), match.group(0)), text)


def environment_names(text: str) -> list[str]:
    return [line.split("=", 2)[1] for line in directives(text) if line.startswith("Environment=")]


def secret_like_environment(text: str) -> list[str]:
    """Environment= names that look like secrets; a secret belongs only in the EnvironmentFile=."""
    return [name for name in environment_names(text) if SECRET_LIKE.search(name)]


def unexplained_environment(text: str) -> list[str]:
    """Environment= lines whose preceding line is not a comment: each needs its own one-line reason."""
    lines = text.splitlines()
    return [line for index, line in enumerate(lines)
            if line.startswith("Environment=") and not (index and lines[index - 1].startswith("#"))]


def mirror_differences(template: str, installed: str) -> list[str]:
    """Directives present in only one of the rendered template and the installed unit, Description= aside."""
    rendered = [line for line in directives(render(template, WORKSTATION))
                if not line.startswith("Description=") and line not in TEMPLATE_ONLY]
    recorded = [line for line in directives(installed) if not line.startswith("Description=")]
    if rendered == recorded:
        return []
    return sorted(set(rendered) ^ set(recorded)) or ["same directives in a different order"]


class OmniRouteUnitTemplateTests(unittest.TestCase):
    def setUp(self):
        self.template = TEMPLATE.read_text(encoding="utf-8")
        self.installed = INSTALLED.read_text(encoding="utf-8")

    def test_renders_to_the_recorded_installed_unit(self):
        self.assertEqual(mirror_differences(self.template, self.installed), [])
        for line in TEMPLATE_ONLY:
            self.assertIn(line, directives(self.template))
            self.assertNotIn(line, directives(self.installed))

    def test_placeholders_are_exactly_the_documented_set_and_render_away(self):
        used = set(PLACEHOLDER.findall("\n".join(directives(self.template))))
        self.assertEqual(used, set(WORKSTATION))
        header = "\n".join(line for line in self.template.splitlines() if line.startswith("#"))
        for name in WORKSTATION:
            self.assertIn(f"@{name}@", header, f"@{name}@ is not documented in the header")
        self.assertEqual(PLACEHOLDER.findall("\n".join(directives(render(self.template, WORKSTATION)))), [])

    def test_no_inline_secret_and_exactly_one_environment_file(self):
        lines = directives(self.template)
        self.assertEqual([line for line in lines if line.startswith("EnvironmentFile=")],
                         ["EnvironmentFile=%h/.local/share/omniroute/server.env"])
        self.assertEqual(set(environment_names(self.template)), ENVIRONMENT_NAMES)
        self.assertEqual(len(environment_names(self.template)), len(ENVIRONMENT_NAMES))
        self.assertEqual(secret_like_environment(self.template), [])
        self.assertIsNone(re.search(r"(?i)bearer|\bexport\s|[0-9a-f]{32,}", "\n".join(lines)))

    def test_every_environment_line_has_its_own_reason(self):
        self.assertEqual(unexplained_environment(self.template), [])

    def test_serve_runs_in_the_foreground_under_systemd_supervision(self):
        lines = directives(self.template)
        self.assertEqual([line for line in lines if line.startswith("ExecStart=")], [EXEC_START])
        for setting in ("Type=simple", "Restart=on-failure", "UMask=0077", "NoNewPrivileges=true",
                        "[Install]", "WantedBy=default.target"):
            self.assertIn(setting, lines)
        for flag in ("--daemon", "--no-recovery", "npm start", "timeout "):
            self.assertNotIn(flag, "\n".join(lines))

    def test_the_decision_record_names_the_template(self):
        self.assertIn("adoption/templates/systemd/omniroute.service", DECISION.read_text(encoding="utf-8"))

    # Discriminating controls: each helper must fail on a planted violation.

    def test_a_planted_secret_environment_line_is_caught(self):
        planted = self.template.replace(
            "Environment=OMNIROUTE_MEMORY_MB=16384",
            "Environment=OMNIROUTE_MEMORY_MB=16384\n# reason\nEnvironment=JWT_SECRET=fixture-not-a-secret")
        self.assertEqual(secret_like_environment(planted), ["JWT_SECRET"])
        self.assertEqual(secret_like_environment("Environment=OMNIROUTE_API_KEY=x\n"), ["OMNIROUTE_API_KEY"])

    def test_an_environment_line_without_a_reason_is_caught(self):
        planted = self.template.replace("Environment=CLI_ALLOW_CONFIG_WRITES=false",
                                        "Environment=CLI_ALLOW_CONFIG_WRITES=false\nEnvironment=EXTRA=1")
        self.assertEqual(unexplained_environment(planted), ["Environment=EXTRA=1"])

    def test_a_drifted_template_no_longer_mirrors_the_installed_unit(self):
        drifted = self.template.replace("STREAM_ACTIVE_TIMEOUT_MS=3600000", "STREAM_ACTIVE_TIMEOUT_MS=0")
        self.assertEqual(mirror_differences(drifted, self.installed),
                         ["Environment=STREAM_ACTIVE_TIMEOUT_MS=0", "Environment=STREAM_ACTIVE_TIMEOUT_MS=3600000"])
        dropped = self.template.replace("UMask=0077\n", "")
        self.assertEqual(mirror_differences(dropped, self.installed), ["UMask=0077"])


if __name__ == "__main__":
    unittest.main()
