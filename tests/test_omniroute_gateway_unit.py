"""Structural tests for the two OmniRoute systemd --user unit templates.

Offline text checks only, in the style of test_token_report_refresh_units.py. Nothing here loads, starts, enables or
verifies a unit with a live systemd manager; `systemd-analyze --user verify` on a rendered copy is a separate, manual
acceptance check. Each template must render to the unit recorded as installed on the workstation after the 2026-09-30
rebuild (evidence/artifacts/omniroute-rebuild-20260930/), apart from its Description= and one documented extra line: the
gateway (20128) template to omniroute.service, the framework (20129) template to omniroute-fw.service. The gateway
template must also still render to the unit recorded on 2026-09-27 (evidence/artifacts/omniroute-gateway-20260927/),
with that build's prefix, which stays as the historical record. Each unit text holds no secret, names exactly one
EnvironmentFile= and gives every Environment= line a one-line reason. A text test cannot see what a user service
inherits from the user manager's environment; the gateway template's header says how to keep credentials and bind
variables out of it. Every check of a template's text is a helper function, and a planted violation fails each helper
(the discriminating controls in each class). So does each cross-reference check.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "adoption/templates/systemd"
RECEIPT = ROOT / "evidence/artifacts/omniroute-rebuild-20260930"
DECISION_20260927 = ROOT / "docs/decisions/2026-09-27-omniroute-account-pool.md"
DECISION_20260930 = ROOT / "docs/decisions/2026-09-30-omniroute-rebuild.md"
TOOLS = "%h/.local/share/codex-ecosystem/tools"
NODE_PREFIX = f"{TOOLS}/node-24.21.0"
# The release/v3.8.51 commit both running builds are based on (evidence/artifacts/omniroute-rebuild-20260930/receipt.json).
UPSTREAM_BASE = "2f42a9ac1"
TEMPLATE_NAMES = ("adoption/templates/systemd/omniroute.service", "adoption/templates/systemd/omniroute-fw.service")


class Unit(NamedTuple):
    template: Path
    installed: Path
    values: dict[str, str]
    environment_file: str
    exec_start: str


# The workstation's values, as the recorded installed units show them.
GATEWAY = Unit(
    template=TEMPLATES / "omniroute.service",
    installed=RECEIPT / "omniroute.service",
    values={"OMNIROUTE_PREFIX": f"{TOOLS}/omniroute-3.8.51-2f42a9ac-pr13788-affinity2", "NODE_PREFIX": NODE_PREFIX,
            "CODEX_CLIENT_VERSION": "0.159.1"},
    environment_file="EnvironmentFile=%h/.local/share/omniroute/server.env",
    exec_start="ExecStart=@OMNIROUTE_PREFIX@/bin/omniroute serve --port 20128 --no-open --no-tray",
)
GATEWAY_20260927 = GATEWAY._replace(
    installed=ROOT / "evidence/artifacts/omniroute-gateway-20260927/omniroute.service",
    values={**GATEWAY.values, "OMNIROUTE_PREFIX": f"{TOOLS}/omniroute-3.8.51-a58000c7-pr14904-pr13788",
            "CODEX_CLIENT_VERSION": "0.157.1"},
)
FRAMEWORK = Unit(
    template=TEMPLATES / "omniroute-fw.service",
    installed=RECEIPT / "omniroute-fw.service",
    values={"OMNIROUTE_PREFIX": f"{TOOLS}/omniroute-3.8.51-2f42a9ac-pr13788", "NODE_PREFIX": NODE_PREFIX,
            "CODEX_CLIENT_VERSION": "0.159.1"},
    environment_file="EnvironmentFile=%h/.local/share/omniroute-fw/server.env",
    exec_start="ExecStart=@OMNIROUTE_PREFIX@/bin/omniroute serve --port 20129 --no-open --no-tray",
)
# The one directive each template adds on purpose (see its header); the installed process environment has the same value.
TEMPLATE_ONLY = {"Environment=OMNIROUTE_SERVER_HOST=127.0.0.1"}
ENVIRONMENT_NAMES = {
    "PATH", "OMNIROUTE_SERVER_HOST", "OMNIROUTE_MEMORY_MB", "CODEX_CLIENT_VERSION", "STREAM_READINESS_TIMEOUT_MS",
    "STREAM_READINESS_MAX_TIMEOUT_MS", "STREAM_ACTIVE_TIMEOUT_MS", "CLI_ALLOW_CONFIG_WRITES",
}
PLACEHOLDER = re.compile(r"@([A-Z][A-Z0-9_]*)@")
SECRET_LIKE = re.compile(r"SECRET|PASSWORD|TOKEN|COOKIE|_KEY\b|^KEY\b")
CREDENTIAL_TEXT = re.compile(r"(?i)bearer|\bexport\s|[0-9a-f]{32,}")
SUPERVISION = ("Type=simple", "Restart=on-failure", "UMask=0077", "NoNewPrivileges=true", "[Install]",
               "WantedBy=default.target")
FORBIDDEN = ("--daemon", "--no-recovery", "npm start", "timeout ")
# A commit id or a PR number: a Description= that names a build goes stale at the next rebuild.
BUILD_REFERENCE = re.compile(r"\b[0-9a-f]{7,40}\b|#\d+")


def directives(text: str) -> list[str]:
    """Non-blank, non-comment lines, in order (section headers included)."""
    return [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def header(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if line.startswith("#"))


def render(text: str, values: dict[str, str]) -> str:
    """Substitute the known placeholders; header prose such as "@NAME@" is left as it is."""
    return PLACEHOLDER.sub(lambda match: values.get(match.group(1), match.group(0)), text)


def environment_names(text: str) -> list[str]:
    return [line.split("=", 2)[1] for line in directives(text) if line.startswith("Environment=")]


def secret_like_environment(text: str) -> list[str]:
    """Environment= names that look like secrets; a secret belongs only in the EnvironmentFile=."""
    return [name for name in environment_names(text) if SECRET_LIKE.search(name)]


def environment_files(text: str) -> list[str]:
    """EnvironmentFile= directives, in order; a unit must have exactly its own server.env line."""
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


def placeholder_problems(text: str, unit: Unit = GATEWAY) -> list[str]:
    """Placeholders outside the documented set, documented ones the directives do not use, ones the header omits, and
    any left in the directives after rendering with the workstation's values."""
    used = set(PLACEHOLDER.findall("\n".join(directives(text))))
    leftover = set(PLACEHOLDER.findall("\n".join(directives(render(text, unit.values)))))
    return ([f"unknown @{name}@" for name in sorted(used - set(unit.values))]
            + [f"unused @{name}@" for name in sorted(set(unit.values) - used)]
            + [f"undocumented @{name}@" for name in sorted(unit.values) if f"@{name}@" not in header(text)]
            + [f"unrendered @{name}@" for name in sorted(leftover)])


def template_only_problems(template: str, installed: str) -> list[str]:
    """The documented template-only directives must be in the template and absent from the installed unit."""
    return ([f"template lacks {line}" for line in sorted(TEMPLATE_ONLY) if line not in directives(template)]
            + [f"installed unit has {line}" for line in sorted(TEMPLATE_ONLY) if line in directives(installed)])


def supervision_problems(text: str, unit: Unit = GATEWAY) -> list[str]:
    """Departures from a foreground serve under systemd supervision."""
    lines = directives(text)
    joined = "\n".join(lines)
    return (([] if [line for line in lines if line.startswith("ExecStart=")] == [unit.exec_start]
             else ["ExecStart differs"])
            + [f"missing {setting}" for setting in SUPERVISION if setting not in lines]
            + [f"forbidden {flag.strip()}" for flag in FORBIDDEN if flag in joined])


def unexplained_environment(text: str) -> list[str]:
    """Environment= lines without exactly one reason line: the line before must be a comment, the one before that not."""
    lines = text.splitlines()

    def comment(index: int) -> bool:
        return index >= 0 and lines[index].startswith("#")

    return [line for index, line in enumerate(lines)
            if line.startswith("Environment=") and not (comment(index - 1) and not comment(index - 2))]


def mirror_differences(template: str, installed: str, unit: Unit = GATEWAY) -> list[str]:
    """Directives present in only one of the rendered template and the installed unit, Description= aside."""
    rendered = [line for line in directives(render(template, unit.values))
                if not line.startswith("Description=") and line not in TEMPLATE_ONLY]
    recorded = [line for line in directives(installed) if not line.startswith("Description=")]
    if rendered == recorded:
        return []
    return sorted(set(rendered) ^ set(recorded)) or ["same directives in a different order"]


def header_problems(text: str, unit: Unit) -> list[str]:
    """The header must name the recorded installed unit the template mirrors and the upstream base its source
    citations are pinned to."""
    record = unit.installed.relative_to(ROOT).as_posix()
    return ([] if record in header(text) else [f"header does not name {record}"]) + (
        [] if UPSTREAM_BASE in header(text) else [f"header does not name {UPSTREAM_BASE}"])


def description_problems(text: str) -> list[str]:
    """Exactly one Description=, naming no commit or PR: the build identity belongs to the receipt."""
    lines = [line for line in directives(text) if line.startswith("Description=")]
    if len(lines) != 1:
        return [f"{len(lines)} Description= lines"]
    return [f"Description names a build: {match}" for match in BUILD_REFERENCE.findall(lines[0])]


def unit_settings(text: str) -> tuple[str | None, str | None, str | None]:
    """The EnvironmentFile= path, the WorkingDirectory= path and the serve port of a unit text."""
    lines = directives(text)

    def value(prefix: str) -> str | None:
        return next((line.split("=", 1)[1] for line in lines if line.startswith(prefix)), None)

    exec_start = value("ExecStart=") or ""
    port = re.search(r"--port (\d+)", exec_start)
    return value("EnvironmentFile="), value("WorkingDirectory="), port.group(1) if port else None


def separation_problems(gateway: str, framework: str) -> list[str]:
    """The framework instance shares no port, environment file or data directory with the gateway, and runs from its
    own data directory."""
    gateway_file, _, gateway_port = unit_settings(gateway)
    framework_file, framework_dir, framework_port = unit_settings(framework)
    problems = []
    if framework_port is None or framework_port == gateway_port:
        problems.append("shared or missing port")
    if framework_file is None or framework_file == gateway_file:
        problems.append("shared or missing EnvironmentFile")
    if framework_file and gateway_file and framework_file.rsplit("/", 1)[0] == gateway_file.rsplit("/", 1)[0]:
        problems.append("shared data directory")
    if framework_file is None or framework_dir != framework_file.rsplit("/", 1)[0]:
        problems.append("WorkingDirectory is not the framework's data directory")
    return problems


def missing_template_names(text: str, names: tuple[str, ...] = TEMPLATE_NAMES) -> list[str]:
    """Template paths a decision record does not name."""
    return [name for name in names if name not in text]


def read(path: Path) -> str:
    """The file's text, or "" when it is absent, so that a missing template fails the checks instead of erroring."""
    return path.read_text(encoding="utf-8") if path.is_file() else ""


class TemplateChecks:
    """The checks and controls both templates share; each subclass names its unit."""

    unit: Unit

    def setUp(self):
        self.template = read(self.unit.template)
        self.installed = self.unit.installed.read_text(encoding="utf-8")

    def test_template_file_exists(self):
        self.assertTrue(self.unit.template.is_file(), self.unit.template.relative_to(ROOT).as_posix())

    def test_renders_to_the_recorded_installed_unit(self):
        self.assertEqual(mirror_differences(self.template, self.installed, self.unit), [])
        self.assertEqual(template_only_problems(self.template, self.installed), [])

    def test_placeholders_are_exactly_the_documented_set_and_render_away(self):
        self.assertEqual(placeholder_problems(self.template, self.unit), [])

    def test_no_inline_secret_and_exactly_one_environment_file(self):
        self.assertEqual(environment_files(self.template), [self.unit.environment_file])
        self.assertEqual(environment_name_drift(self.template), [])
        self.assertEqual(secret_like_environment(self.template), [])
        self.assertEqual(credential_like_directives(self.template), [])

    def test_every_environment_line_has_its_own_reason(self):
        self.assertEqual(unexplained_environment(self.template), [])

    def test_serve_runs_in_the_foreground_under_systemd_supervision(self):
        self.assertEqual(supervision_problems(self.template, self.unit), [])

    def test_header_names_the_recorded_unit_and_the_upstream_base(self):
        self.assertEqual(header_problems(self.template, self.unit), [])

    def test_description_names_no_build(self):
        self.assertEqual(description_problems(self.template), [])

    def test_the_rebuild_decision_record_names_both_templates(self):
        self.assertEqual(missing_template_names(DECISION_20260930.read_text(encoding="utf-8")), [])

    # Discriminating controls: each helper must fail on a planted violation.

    def test_a_planted_secret_environment_line_is_caught(self):
        planted = self.template.replace(
            "Environment=OMNIROUTE_MEMORY_MB=16384",
            "Environment=OMNIROUTE_MEMORY_MB=16384\n# reason\nEnvironment=JWT_SECRET=fixture-not-a-secret")
        self.assertEqual(secret_like_environment(planted), ["JWT_SECRET"])
        self.assertEqual(secret_like_environment("Environment=OMNIROUTE_API_KEY=x\n"), ["OMNIROUTE_API_KEY"])

    def test_a_second_or_missing_environment_file_is_caught(self):
        second = "EnvironmentFile=%h/.config/omniroute-extra.env"
        planted = self.template.replace(self.unit.environment_file, f"{self.unit.environment_file}\n{second}")
        self.assertEqual(environment_files(planted), [self.unit.environment_file, second])
        self.assertEqual(environment_files(self.template.replace(self.unit.environment_file + "\n", "")), [])

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
        self.assertEqual(placeholder_problems(unknown, self.unit), ["unknown @DATA_DIR@", "unrendered @DATA_DIR@"])
        unused = self.template.replace("Environment=CODEX_CLIENT_VERSION=@CODEX_CLIENT_VERSION@",
                                       "Environment=CODEX_CLIENT_VERSION=0.157.1")
        self.assertEqual(placeholder_problems(unused, self.unit), ["unused @CODEX_CLIENT_VERSION@"])
        undocumented = "\n".join(line for line in self.template.splitlines()
                                 if not (line.startswith("#") and "@NODE_PREFIX@" in line))
        self.assertEqual(placeholder_problems(undocumented, self.unit), ["undocumented @NODE_PREFIX@"])

    def test_template_only_drift_is_caught(self):
        (line,) = TEMPLATE_ONLY
        dropped = self.template.replace(line + "\n", "")
        self.assertEqual(template_only_problems(dropped, self.installed), [f"template lacks {line}"])
        installed_too = self.installed.replace("Restart=on-failure", f"{line}\nRestart=on-failure")
        self.assertEqual(template_only_problems(self.template, installed_too), [f"installed unit has {line}"])

    def test_supervision_drift_is_caught(self):
        daemon = self.template.replace("--no-tray\n", "--no-tray --daemon\n")
        self.assertEqual(supervision_problems(daemon, self.unit), ["ExecStart differs", "forbidden --daemon"])
        unmasked = self.template.replace("UMask=0077\n", "")
        self.assertEqual(supervision_problems(unmasked, self.unit), ["missing UMask=0077"])

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
        self.assertEqual(mirror_differences(drifted, self.installed, self.unit),
                         ["Environment=STREAM_ACTIVE_TIMEOUT_MS=0", "Environment=STREAM_ACTIVE_TIMEOUT_MS=3600000"])
        dropped = self.template.replace("UMask=0077\n", "")
        self.assertEqual(mirror_differences(dropped, self.installed, self.unit), ["UMask=0077"])

    def test_a_header_that_misses_the_record_or_the_base_is_caught(self):
        record = self.unit.installed.relative_to(ROOT).as_posix()
        no_record = self.template.replace(record, "evidence/artifacts/elsewhere/unit.service")
        self.assertEqual(header_problems(no_record, self.unit), [f"header does not name {record}"])
        old_base = self.template.replace(UPSTREAM_BASE, "a58000c7")
        self.assertEqual(header_problems(old_base, self.unit), [f"header does not name {UPSTREAM_BASE}"])

    def test_a_description_that_names_a_build_is_caught(self):
        lines = [line for line in directives(self.template) if line.startswith("Description=")]
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertEqual(description_problems(self.template.replace(line, line + " dd6e9607e")),
                         ["Description names a build: dd6e9607e"])
        self.assertEqual(description_problems(self.template.replace(line, line + " (PR #13788)")),
                         ["Description names a build: #13788"])
        self.assertEqual(description_problems(self.template.replace(line + "\n", "")), ["0 Description= lines"])

    def test_a_record_that_omits_a_template_is_caught(self):
        self.assertEqual(missing_template_names("adoption/templates/systemd/omniroute.service only"),
                         ["adoption/templates/systemd/omniroute-fw.service"])
        self.assertEqual(missing_template_names(""), list(TEMPLATE_NAMES))


class GatewayTemplateTests(TemplateChecks, unittest.TestCase):
    unit = GATEWAY

    def test_still_renders_to_the_20260927_record(self):
        installed = GATEWAY_20260927.installed.read_text(encoding="utf-8")
        self.assertEqual(mirror_differences(self.template, installed, GATEWAY_20260927), [])
        self.assertEqual(template_only_problems(self.template, installed), [])

    def test_the_20260927_decision_record_names_the_gateway_template(self):
        self.assertEqual(missing_template_names(DECISION_20260927.read_text(encoding="utf-8"), TEMPLATE_NAMES[:1]), [])

    def test_a_prefix_mismatch_with_the_20260927_record_is_caught(self):
        installed = GATEWAY_20260927.installed.read_text(encoding="utf-8")
        old_version = GATEWAY_20260927.values["CODEX_CLIENT_VERSION"]
        prefix_only = GATEWAY._replace(values={**GATEWAY.values, "CODEX_CLIENT_VERSION": old_version})
        self.assertEqual(len(mirror_differences(self.template, installed, prefix_only)), 4)

    def test_a_client_version_mismatch_with_the_20260927_record_is_caught(self):
        installed = GATEWAY_20260927.installed.read_text(encoding="utf-8")
        version_only = GATEWAY_20260927._replace(values={**GATEWAY_20260927.values, "CODEX_CLIENT_VERSION": GATEWAY.values["CODEX_CLIENT_VERSION"]})
        self.assertEqual(len(mirror_differences(self.template, installed, version_only)), 2)


class FrameworkTemplateTests(TemplateChecks, unittest.TestCase):
    unit = FRAMEWORK

    def test_shares_no_port_environment_file_or_data_directory_with_the_gateway(self):
        self.assertEqual(separation_problems(read(GATEWAY.template), self.template), [])

    def test_a_shared_port_environment_file_or_data_directory_is_caught(self):
        gateway = read(GATEWAY.template)
        self.assertEqual(separation_problems(gateway, self.template.replace("--port 20129", "--port 20128")),
                         ["shared or missing port"])
        shared_file = self.template.replace(FRAMEWORK.environment_file, GATEWAY.environment_file)
        self.assertEqual(separation_problems(gateway, shared_file),
                         ["shared or missing EnvironmentFile", "shared data directory",
                          "WorkingDirectory is not the framework's data directory"])
        elsewhere = self.template.replace("WorkingDirectory=%h/.local/share/omniroute-fw\n", "WorkingDirectory=%h\n")
        self.assertEqual(separation_problems(gateway, elsewhere),
                         ["WorkingDirectory is not the framework's data directory"])


if __name__ == "__main__":
    unittest.main()
