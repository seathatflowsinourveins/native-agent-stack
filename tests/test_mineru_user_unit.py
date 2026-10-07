"""Offline contract checks for the proposed MinerU user unit.

The vendor entry is MinerU@c221cc41:mineru/cli/commands/server.py:242-248
and mineru/doclib/app.py:443-449. The text-test pattern follows
tests/test_omniroute_gateway_unit.py. These tests never contact or start a
service; negative fixtures discriminate lifecycle and source mistakes.
"""

from __future__ import annotations

import re
import shlex
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "adoption/templates/systemd/mineru.service"
PYTHON = "%h/.local/share/uv/tools/mineru/bin/python"


def unit_problems(text: str) -> list[str]:
    """Check the bounded source/lifecycle contract, without executing a unit."""
    entries: dict[tuple[str, str], list[str]] = defaultdict(list)
    section = ""
    problems = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
        elif "=" in line:
            key, value = line.split("=", 1)
            entries[(section, key.strip())].append(value.strip())
        else:
            problems.append("malformed directive")

    for section, key, value in (
        ("Unit", "OnFailure", "stack-alert@%n.service"),
        ("Unit", "StartLimitIntervalSec", "60"),
        ("Unit", "StartLimitBurst", "3"),
        ("Service", "Type", "exec"),
        ("Service", "Restart", "on-failure"),
        ("Service", "RestartSec", "5"),
        ("Service", "KillMode", "control-group"),
        ("Install", "WantedBy", "default.target"),
    ):
        if entries[(section, key)] != [value]:
            problems.append(f"{section}.{key} must be {value}")

    starts = entries[("Service", "ExecStart")]
    try:
        argv = shlex.split(starts[0]) if len(starts) == 1 else []
    except ValueError:
        argv = []
    if argv != [PYTHON, "-m", "mineru.doclib.app"]:
        problems.append("ExecStart must supervise the shipped foreground module")

    environments = entries[("Service", "Environment")]
    if environments != ["MINERU_MODEL_SOURCE=local"]:
        problems.append("Environment must contain only the supported local source override")
    for (section, key), values in entries.items():
        if key in {"EnvironmentFile", "PassEnvironment", "LoadCredential", "LoadCredentialEncrypted", "SetCredential"}:
            problems.append(f"{section}.{key} adds an unapproved environment or credential carrier")
        if key in {"ExecStartPre", "ExecStartPost", "ExecStop", "ExecStopPost", "PIDFile", "RemainAfterExit"}:
            problems.append(f"{section}.{key} changes foreground lifecycle")
        if key == "Environment" and any(re.search(r"SECRET|PASSWORD|TOKEN|COOKIE|API_KEY", v) for v in values):
            problems.append("credential placeholder in Environment")
    return problems


class MinerUUserUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = TEMPLATE.read_text()

    def test_template_follows_source_and_lifecycle_contract(self) -> None:
        self.assertEqual([], unit_problems(self.text))

    def test_remote_or_absent_source_is_rejected(self) -> None:
        for replacement in ("Environment=MINERU_MODEL_SOURCE=huggingface", ""):
            with self.subTest(replacement=replacement):
                self.assertTrue(unit_problems(self.text.replace("Environment=MINERU_MODEL_SOURCE=local", replacement)))

    def test_background_cli_cannot_replace_foreground_entry(self) -> None:
        bad = self.text.replace(f"ExecStart={PYTHON} -m mineru.doclib.app", "ExecStart=%h/.local/bin/mineru server start")
        self.assertIn("ExecStart must supervise the shipped foreground module", unit_problems(bad))

    def test_failure_routing_and_bounded_recovery_are_required(self) -> None:
        for directive in ("OnFailure=stack-alert@%n.service", "StartLimitBurst=3", "Restart=on-failure"):
            with self.subTest(directive=directive):
                self.assertTrue(unit_problems(self.text.replace(directive, "")))

    def test_parser_children_must_share_stop_lifecycle(self) -> None:
        self.assertTrue(unit_problems(self.text.replace("KillMode=control-group", "KillMode=process")))
        self.assertTrue(unit_problems(self.text.replace("Type=exec", "Type=forking")))

    def test_unapproved_credential_and_environment_carriers_are_rejected(self) -> None:
        for directive in ("Environment=MINERU_API_KEY=@KEY@", "EnvironmentFile=%h/.mineru/config.yaml", "PassEnvironment=MINERU_MODEL_SOURCE"):
            with self.subTest(directive=directive):
                self.assertTrue(unit_problems(self.text.replace("[Service]", f"[Service]\n{directive}")))

    def test_unproved_gpu_environment_guard_is_rejected(self) -> None:
        bad = self.text.replace("[Service]", "[Service]\nEnvironment=LLAMA_ARG_N_GPU_LAYERS=0")
        self.assertTrue(unit_problems(bad))

    def test_duplicate_or_daemon_lifecycle_directive_is_rejected(self) -> None:
        for directive in ("ExecStart=/bin/true", "RemainAfterExit=yes", "PIDFile=%h/.mineru/doclib.pid"):
            with self.subTest(directive=directive):
                self.assertTrue(unit_problems(self.text.replace("[Service]", f"[Service]\n{directive}")))


if __name__ == "__main__":
    unittest.main()
