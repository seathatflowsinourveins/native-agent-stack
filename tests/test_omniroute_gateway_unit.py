"""Structural tests for the OmniRoute gateway systemd --user unit template.

Offline text checks only, in the style of test_token_report_refresh_units.py. Nothing here loads, starts, enables or
verifies a unit with a live systemd manager; `systemd-analyze --user verify` on a rendered copy is a separate, manual
acceptance check. The template must render to the unit recorded as installed on the workstation
(evidence/artifacts/omniroute-gateway-20260927/omniroute.service), apart from its Description= and one documented
extra line. The unit text holds no secret, names exactly one EnvironmentFile= and gives every Environment= line a one-line
reason comment. A text test cannot see what a user service inherits from the user manager's environment; the template's header
says how to keep credentials and bind variables out of it. Every check of the template's text is a helper function, and
a planted violation fails each helper (the discriminating controls at the end). The one cross-reference check, that
the decision record names the template, is a direct assertion without a control.
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
ENVIRONMENT_FILE = "EnvironmentFile=%h/.local/share/omniroute/server.env"
ENVIRONMENT_NAMES = {
    "PATH", "OMNIROUTE_SERVER_HOST", "OMNIROUTE_MEMORY_MB", "CODEX_CLIENT_VERSION", "STREAM_READINESS_TIMEOUT_MS",
    "STREAM_READINESS_MAX_TIMEOUT_MS", "STREAM_ACTIVE_TIMEOUT_MS", "CLI_ALLOW_CONFIG_WRITES",
}
PLACEHOLDER = re.compile(r"@([A-Z][A-Z0-9_]*)@")
SECRET_LIKE = re.compile(r"SECRET|PASSWORD|TOKEN|COOKIE|_KEY\b|^KEY\b")
CREDENTIAL_TEXT = re.compile(r"(?i)bearer|\bexport\s|[0-9a-f]{32,}")
EXEC_START = "ExecStart=@OMNIROUTE_PREFIX@/bin/omniroute serve --port 20128 --no-open --no-tray"
SUPERVISION = ("Type=simple", "Restart=on-failure", "UMask=0077", "NoNewPrivileges=true", "[Install]",
               "WantedBy=default.target")
FORBIDDEN = ("--daemon", "--no-recovery", "npm start", "timeout ")


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


def environment_files(text: str) -> list[str]:
    """EnvironmentFile= directives, in order; the unit must have exactly the one server.env line."""
    return [line for line in directives(text) if line.startswith("EnvironmentFile=")]


def environment_name_drift(text: str) -> list[str]:
    """Documented Environment= names that are missing, undocumented names, and names given more than once."""
    names = environment_names(text)
    return ([f"missing {name}" for name in sorted(ENVIRONMENT_NAMES - set(names))]
            + [f"undocumented {name}" for name in sorted(set(names) - ENVIRONMENT_NAMES)]
            + [f"repeated {name}" for name in sorted({name for name in names if names.count(name) > 1})])


def credential_like_directives(text: str) -> list[str]:
    """Directive lines with bearer text, a shell export or a run of 32 or more hex digits."""
    return [line for line in directives(text) if CREDENTIAL_TEXT.search(line)]


def placeholder_problems(text: str) -> list[str]:
    """Placeholders outside the documented set, documented ones the directives do not use, ones the header omits, and
    any left in the directives after rendering with the workstation's values."""
    used = set(PLACEHOLDER.findall("\n".join(directives(text))))
    header = "\n".join(line for line in text.splitlines() if line.startswith("#"))
    leftover = set(PLACEHOLDER.findall("\n".join(directives(render(text, WORKSTATION)))))
    return ([f"unknown @{name}@" for name in sorted(used - set(WORKSTATION))]
            + [f"unused @{name}@" for name in sorted(set(WORKSTATION) - used)]
            + [f"undocumented @{name}@" for name in sorted(WORKSTATION) if f"@{name}@" not in header]
            + [f"unrendered @{name}@" for name in sorted(leftover)])


def template_only_problems(template: str, installed: str) -> list[str]:
    """The documented template-only directives must be in the template and absent from the installed unit."""
    return ([f"template lacks {line}" for line in sorted(TEMPLATE_ONLY) if line not in directives(template)]
            + [f"installed unit has {line}" for line in sorted(TEMPLATE_ONLY) if line in directives(installed)])


def supervision_problems(text: str) -> list[str]:
    """Departures from a foreground serve under systemd supervision."""
    lines = directives(text)
    joined = "\n".join(lines)
    return (([] if [line for line in lines if line.startswith("ExecStart=")] == [EXEC_START] else ["ExecStart differs"])
            + [f"missing {setting}" for setting in SUPERVISION if setting not in lines]
            + [f"forbidden {flag.strip()}" for flag in FORBIDDEN if flag in joined])


def unexplained_environment(text: str) -> list[str]:
    """Environment= lines without exactly one reason line: the line before must be a comment, the one before that not."""
    lines = text.splitlines()

    def comment(index: int) -> bool:
        return index >= 0 and lines[index].startswith("#")

    return [line for index, line in enumerate(lines)
            if line.startswith("Environment=") and not (comment(index - 1) and not comment(index - 2))]


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
        self.assertEqual(template_only_problems(self.template, self.installed), [])

    def test_placeholders_are_exactly_the_documented_set_and_render_away(self):
        self.assertEqual(placeholder_problems(self.template), [])

    def test_no_inline_secret_and_exactly_one_environment_file(self):
        self.assertEqual(environment_files(self.template), [ENVIRONMENT_FILE])
        self.assertEqual(environment_name_drift(self.template), [])
        self.assertEqual(secret_like_environment(self.template), [])
        self.assertEqual(credential_like_directives(self.template), [])

    def test_every_environment_line_has_its_own_reason(self):
        self.assertEqual(unexplained_environment(self.template), [])

    def test_serve_runs_in_the_foreground_under_systemd_supervision(self):
        self.assertEqual(supervision_problems(self.template), [])

    def test_the_decision_record_names_the_template(self):
        self.assertIn("adoption/templates/systemd/omniroute.service", DECISION.read_text(encoding="utf-8"))

    # Discriminating controls: each helper must fail on a planted violation.

    def test_a_planted_secret_environment_line_is_caught(self):
        planted = self.template.replace(
            "Environment=OMNIROUTE_MEMORY_MB=16384",
            "Environment=OMNIROUTE_MEMORY_MB=16384\n# reason\nEnvironment=JWT_SECRET=fixture-not-a-secret")
        self.assertEqual(secret_like_environment(planted), ["JWT_SECRET"])
        self.assertEqual(secret_like_environment("Environment=OMNIROUTE_API_KEY=x\n"), ["OMNIROUTE_API_KEY"])

    def test_a_second_or_missing_environment_file_is_caught(self):
        second = "EnvironmentFile=%h/.config/omniroute-extra.env"
        planted = self.template.replace(ENVIRONMENT_FILE, f"{ENVIRONMENT_FILE}\n{second}")
        self.assertEqual(environment_files(planted), [ENVIRONMENT_FILE, second])
        self.assertEqual(environment_files(self.template.replace(ENVIRONMENT_FILE + "\n", "")), [])

    def test_environment_name_drift_is_caught(self):
        undocumented = self.template.replace(
            "Environment=CLI_ALLOW_CONFIG_WRITES=false",
            "Environment=CLI_ALLOW_CONFIG_WRITES=false\n# reason\nEnvironment=LIVE_WS_HOST=0.0.0.0")
        self.assertEqual(environment_name_drift(undocumented), ["undocumented LIVE_WS_HOST"])
        repeated = self.template.replace(
            "Environment=OMNIROUTE_MEMORY_MB=16384",
            "Environment=OMNIROUTE_MEMORY_MB=16384\n# reason\nEnvironment=OMNIROUTE_MEMORY_MB=8192")
        self.assertEqual(environment_name_drift(repeated), ["repeated OMNIROUTE_MEMORY_MB"])
        missing = self.template.replace("Environment=CLI_ALLOW_CONFIG_WRITES=false\n", "")
        self.assertEqual(environment_name_drift(missing), ["missing CLI_ALLOW_CONFIG_WRITES"])

    def test_credential_like_text_is_caught(self):
        # The hex run is built at test time, so no 32-digit literal sits in this file.
        for planted_line in ("ExecStartPre=/bin/sh -c 'export OMNIROUTE_API_KEY=x'",
                             "Environment=AUTH_HEADER=Bearer fixture",
                             "Environment=FIXTURE=" + "0123456789abcdef" * 2):
            with self.subTest(planted_line=planted_line):
                planted = self.template.replace("Restart=on-failure", f"{planted_line}\nRestart=on-failure")
                self.assertEqual(credential_like_directives(planted), [planted_line])

    def test_placeholder_drift_is_caught(self):
        unknown = self.template.replace("--no-tray\n", "--no-tray --data-dir @DATA_DIR@\n")
        self.assertEqual(placeholder_problems(unknown), ["unknown @DATA_DIR@", "unrendered @DATA_DIR@"])
        unused = self.template.replace("Environment=CODEX_CLIENT_VERSION=@CODEX_CLIENT_VERSION@",
                                       "Environment=CODEX_CLIENT_VERSION=0.157.1")
        self.assertEqual(placeholder_problems(unused), ["unused @CODEX_CLIENT_VERSION@"])
        undocumented = "\n".join(line for line in self.template.splitlines()
                                 if not (line.startswith("#") and "@NODE_PREFIX@" in line))
        self.assertEqual(placeholder_problems(undocumented), ["undocumented @NODE_PREFIX@"])

    def test_template_only_drift_is_caught(self):
        (line,) = TEMPLATE_ONLY
        dropped = self.template.replace(line + "\n", "")
        self.assertEqual(template_only_problems(dropped, self.installed), [f"template lacks {line}"])
        installed_too = self.installed.replace("Restart=on-failure", f"{line}\nRestart=on-failure")
        self.assertEqual(template_only_problems(self.template, installed_too), [f"installed unit has {line}"])

    def test_supervision_drift_is_caught(self):
        daemon = self.template.replace("--no-tray\n", "--no-tray --daemon\n")
        self.assertEqual(supervision_problems(daemon), ["ExecStart differs", "forbidden --daemon"])
        unmasked = self.template.replace("UMask=0077\n", "")
        self.assertEqual(supervision_problems(unmasked), ["missing UMask=0077"])

    def test_an_environment_line_without_a_reason_is_caught(self):
        planted = self.template.replace("Environment=CLI_ALLOW_CONFIG_WRITES=false",
                                        "Environment=CLI_ALLOW_CONFIG_WRITES=false\nEnvironment=EXTRA=1")
        self.assertEqual(unexplained_environment(planted), ["Environment=EXTRA=1"])

    def test_a_two_line_reason_is_caught(self):
        planted = self.template.replace("Environment=CLI_ALLOW_CONFIG_WRITES=false",
                                        "# a second reason line\nEnvironment=CLI_ALLOW_CONFIG_WRITES=false")
        self.assertEqual(unexplained_environment(planted), ["Environment=CLI_ALLOW_CONFIG_WRITES=false"])

    def test_a_drifted_template_no_longer_mirrors_the_installed_unit(self):
        drifted = self.template.replace("STREAM_ACTIVE_TIMEOUT_MS=3600000", "STREAM_ACTIVE_TIMEOUT_MS=0")
        self.assertEqual(mirror_differences(drifted, self.installed),
                         ["Environment=STREAM_ACTIVE_TIMEOUT_MS=0", "Environment=STREAM_ACTIVE_TIMEOUT_MS=3600000"])
        dropped = self.template.replace("UMask=0077\n", "")
        self.assertEqual(mirror_differences(dropped, self.installed), ["UMask=0077"])


if __name__ == "__main__":
    unittest.main()
