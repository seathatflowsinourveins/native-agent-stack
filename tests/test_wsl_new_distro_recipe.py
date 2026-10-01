"""The new-distro WSL recipe, its templates and its decision record must agree with each other.

Added 2026-10-01 with adoption/platforms/linux-wsl2-new-distro.md and
docs/decisions/2026-10-01-new-wsl-distro-recipe.md. Each test names the drift it stops:

- the cloud-init user-data template renders with ``string.Template`` and its only ``$`` is the
  ``${WSL_USER}`` placeholder, so the recipe's PowerShell ``.Replace`` writes the same bytes; the
  render starts with the ``#cloud-config`` header (no byte order mark, LF line ends) and creates the
  user the recipe describes: uid 1000, the groups the image's wsl-setup gives an interactive user,
  passwordless sudo, a locked password and ``[user] default`` appended to /etc/wsl.conf;
- the host value template renders to JSON with exactly adoption/hosts/example.json's keys, every
  service on 127.0.0.1 at a port outside the workstation distribution's ports (WSL 2 distributions
  share one network namespace), and the recipe's ``ss`` probe checks exactly those ports;
- every command line in the recipe's ``powershell`` and ``sh`` code blocks is a row of the decision
  record's command table under the same step and shell, once per occurrence, and the table lists
  nothing else;
- the image sha256 is one value in the recipe, the record and the stage-1 receipt example, and the
  receipt example carries the payload keys scripts/validate.py compares with a ``receipts[]`` row;
- no recipe command shuts WSL down, updates it, edits .wslconfig, changes the default distribution,
  or terminates, unregisters or manages any distribution but ``<Name>`` (decision 4), and the one
  install command is ``--install --from-file ... --name <Name> --location ... --no-launch``;
- the first-boot checklist and the receipt example name exactly the recipe's steps;
- the three findings of the 2026-10-01 cross-family review stay fixed:
  - after the first launch, W5 expects ``status: disabled`` by ``disabled-by-marker-file`` and reads completion and
    errors from /var/lib/cloud/data/result.json and status.json (cloud-init 26.1 cloudinit/cmd/status.py:284-286 and
    cloudinit/cmd/main.py:1017-1030);
  - W1 tests both Ubuntu Pro files, the Landscape instance file and agent.yaml
    (cloudinit/sources/DataSourceWSL.py:241-270 and 317-336);
  - F10 tests every path ``type -P`` prints with ``test -f`` and ``test -x``.

These are local consistency checks over repository text and an in-memory render of the templates.
Nothing here runs wsl.exe, PowerShell or cloud-init; a pass is not a host run.
"""

from __future__ import annotations

import json
import re
import string
import unittest
from collections import Counter
from pathlib import Path

from scripts import validate

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "adoption/platforms/linux-wsl2-new-distro.md"
RECORD = ROOT / "docs/decisions/2026-10-01-new-wsl-distro-recipe.md"
TEMPLATES = ROOT / "adoption/templates/wsl"
USER_DATA = TEMPLATES / "cloud-init.user-data.template"
HOST_TEMPLATE = TEMPLATES / "host.new-distro.json.template"
RECEIPT_EXAMPLE = TEMPLATES / "stage1-receipt.example.json"
CHECKLIST = TEMPLATES / "first-boot-checklist.md"
HOST_EXAMPLE = ROOT / "adoption/hosts/example.json"
STACK = ROOT / "manifests/stack.json"

IMAGE = "ubuntu-24.04.5-wsl-amd64.wsl"
IMAGE_BYTES = 388975696
PLACEHOLDER = "${WSL_USER}"
# Loopback ports the workstation distribution already uses: the four in adoption/hosts/example.json, the gateway,
# memory and the 2026-09-25 relocations named in adoption/platforms/linux-wsl2.md ("Listeners and ports"), and every
# 127.0.0.1 port in observability/backends/templates and configure.py. The recipe lists the same set (F8).
WORKSTATION_PORTS = frozenset({3710, 3800, 8231, 13000, 13100, 14318, 14333, 16333, 18080, 18231, 18525, 18888,
                               18889, 19090, 19093, 20128, 20129, 31415, 49374, 49474})
URL_KEYS = ("OTEL_ENDPOINT", "AI_MEMORY_URL", "QDRANT_URL", "EMBED_URL")
SHELLS = ("powershell", "sh")

SHA256_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
FENCE_RE = re.compile(r"^(?P<indent>[ \t]*)```(?P<lang>[\w-]*)[^\n]*\n(?P<body>.*?)^(?P=indent)```[ \t]*$", re.M | re.S)
STEP_RE = re.compile(r"^### (?P<step>[WF]\d+)\. ", re.M)
CHECKLIST_STEP_RE = re.compile(r"^- \[ \] \*\*(?P<step>[WF]\d+)\*\*", re.M)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def fenced_commands(text: str) -> list[tuple[str, str]]:
    """(shell, command) for every command line of the ``powershell`` and ``sh`` code blocks: indentation removed,
    sh backslash continuations joined, blank lines and ``#`` comment lines skipped."""
    commands = []
    for match in FENCE_RE.finditer(text):
        if match["lang"] not in SHELLS:
            continue
        indent = len(match["indent"])
        lines = [line[indent:] if line[:indent].strip() == "" else line for line in match["body"].splitlines()]
        body = "\n".join(lines)
        if match["lang"] == "sh":
            body = re.sub(r"[ \t]*\\\n[ \t]*", " ", body)
        for line in body.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                commands.append((match["lang"], line))
    return commands


def recipe_rows(text: str) -> list[tuple[str, str, str]]:
    """(step, shell, command) for every command line of the recipe, the step being the last ``### W<n>.`` or
    ``### F<n>.`` heading above its code block."""
    headings = [(match.start(), match["step"]) for match in STEP_RE.finditer(text)]
    rows = []
    for match in FENCE_RE.finditer(text):
        step = next((name for position, name in reversed(headings) if position < match.start()), "")
        rows += [(step, shell, command) for shell, command in fenced_commands(match.group(0))]
    return rows


def command_table_rows(text: str) -> list[tuple[str, str, str, str]]:
    """(step, shell, command, proof) for every row of the record's "## Command table" section; a command cell is one
    code span, with ``\\|`` for a literal pipe."""
    section = text.split("\n## Command table\n", 1)
    if len(section) != 2:
        return []
    rows = []
    for line in section[1].split("\n## ", 1)[0].splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) < 4 or cells[0] in ("Step", "") or set(cells[0]) <= set("-: "):
            continue
        step, shell, command, proof = cells[0], cells[1], cells[2], cells[3]
        if command.startswith("`") and command.endswith("`"):
            command = command[1:-1]
        rows.append((step, shell, command.replace("\\|", "|"), proof))
    return rows


def command_table(text: str) -> list[tuple[str, str, str]]:
    """(step, shell, command) for every row of the record's command table."""
    return [(step, shell, command) for step, shell, command, _ in command_table_rows(text)]


def command_table_errors(recipe: str, record: str) -> list[str]:
    """The table lists each recipe command line once per occurrence, under its step and shell, and nothing else."""
    commands, table = Counter(recipe_rows(recipe)), Counter(command_table(record))
    errors = [] if commands else ["the recipe has no powershell or sh command"]
    errors += [f"recipe command missing from the record's command table: {step} {shell}: {command}"
               for (step, shell, command), count in sorted((commands - table).items()) for _ in range(count)]
    errors += [f"command table row not in the recipe: {step} {shell}: {command}"
               for (step, shell, command), count in sorted((table - commands).items()) for _ in range(count)]
    return errors


def user_data_errors(template: str, user: str = "example") -> list[str]:
    errors = []
    if "$" in template.replace(PLACEHOLDER, ""):
        errors.append("the template has a $ other than ${WSL_USER}, so PowerShell's literal .Replace and "
                      "string.Template disagree")
    try:
        rendered = string.Template(template).substitute(WSL_USER=user)
    except (KeyError, ValueError) as error:
        return errors + [f"string.Template cannot render the template: {error!r}"]
    if rendered != template.replace(PLACEHOLDER, user):
        errors.append("string.Template and a literal replace render different text")
    if rendered.startswith("﻿"):
        errors.append("the render starts with a byte order mark; cloud-init needs #cloud-config as the first bytes")
    if "\r" in rendered:
        errors.append("the render has CR line ends")
    if rendered.splitlines()[:1] != ["#cloud-config"]:
        errors.append("the first line is not exactly #cloud-config")
    required = (r"^users:$", rf"^- name: {re.escape(user)}$", r"^  uid: 1000$",
                r"^  groups: \[adm, cdrom, sudo, dip, plugdev\]$", r'^  sudo: "ALL=\(ALL\) NOPASSWD:ALL"$',
                r"^  shell: /bin/bash$", r"^  lock_passwd: true$", r"^write_files:$", r"^- path: /etc/wsl\.conf$",
                r"^  append: true$", r"^  content: \|$", r"^    \[user\]$", rf"^    default={re.escape(user)}$")
    errors += [f"the render lacks a line matching {pattern}" for pattern in required
               if not re.search(pattern, rendered, re.M)]
    if re.search(r"^\s*(passwd|hashed_passwd|plain_text_passwd):", rendered, re.M):
        errors.append("the user-data sets a password; the recipe's user has a locked password and NOPASSWD sudo")
    return errors


def host_template_errors(template: str, example: dict, recipe: str, user: str = "example") -> list[str]:
    errors = []
    if "$" in template.replace(PLACEHOLDER, ""):
        errors.append("the host template has a $ other than ${WSL_USER}")
    try:
        values = json.loads(string.Template(template).substitute(WSL_USER=user))
    except (KeyError, ValueError) as error:
        return errors + [f"the host template does not render to JSON: {error!r}"]
    if sorted(values) != sorted(example):
        errors.append(f"keys {sorted(values)} are not adoption/hosts/example.json's {sorted(example)}")
    ports = []
    for key in URL_KEYS:
        match = re.fullmatch(r"127\.0\.0\.1:(\d{1,5})", str(values.get(key, "")))
        if match is None:
            errors.append(f"{key} is not 127.0.0.1:<port>")
            continue
        port = int(match.group(1))
        ports.append(port)
        if port in WORKSTATION_PORTS:
            errors.append(f"{key} uses {port}, a port the workstation distribution holds in the shared namespace")
    if len(set(ports)) != len(ports):
        errors.append("two services share a port")
    for key in ("HOME", "ECO_ROOT", "PROJECT_ROOT", "CODE_INDEX_PATH"):
        if not str(values.get(key, "")).startswith(f"/home/{user}"):
            errors.append(f"{key} is not under the new user's home")
    probes = [command for shell, command in fenced_commands(recipe) if shell == "sh" and command.startswith("ss -ltnH")]
    probed = {int(port) for command in probes for port in re.findall(r"sport = :(\d+)", command)}
    if probed != set(ports):
        errors.append(f"the recipe's ss probe checks {sorted(probed)}, the template uses {sorted(ports)}")
    missing = sorted(port for port in WORKSTATION_PORTS if f"`{port}`" not in recipe)
    if missing:
        errors.append(f"the recipe's exclusion set does not list {missing}")
    return errors


def sha256_errors(recipe: str, record: str, receipt: dict, checklist: str) -> list[str]:
    errors = []
    recipe_values = set(SHA256_RE.findall(recipe))
    if len(recipe_values) != 1:
        return [f"the recipe names {len(recipe_values)} distinct sha256 values, expected exactly one (the image's)"]
    (expected,) = recipe_values
    record_values = {value for line in record.splitlines() if IMAGE in line for value in SHA256_RE.findall(line)}
    if not record_values:
        errors.append(f"the record names no sha256 on a line that names {IMAGE}")
    elif record_values != {expected}:
        errors.append(f"the record's {IMAGE} sha256 {sorted(record_values)} differs from the recipe's {expected}")
    if set(SHA256_RE.findall(checklist)) != {expected}:
        errors.append("the checklist's W2 sha256 differs from the recipe's")
    image = receipt.get("image", {}) if isinstance(receipt, dict) else {}
    if image.get("file") != IMAGE or image.get("bytes") != IMAGE_BYTES:
        errors.append("the receipt example's image is not the recipe's file and size")
    if image.get("sha256_published") != expected:
        errors.append("the receipt example's sha256_published differs from the recipe's")
    return errors


def receipt_errors(receipt: dict, recipe: str, component_ids: set[str]) -> list[str]:
    errors = []
    for key in ("id", "kind", "component_ids", "claim", "limitations"):
        if key not in receipt:
            errors.append(f"the receipt example lacks {key}, which scripts/validate.py compares with its receipts[] row")
    if receipt.get("kind") not in validate.RECEIPT_KINDS:
        errors.append(f"kind {receipt.get('kind')!r} is not one of scripts/validate.py RECEIPT_KINDS")
    ids = receipt.get("component_ids")
    if not isinstance(ids, list) or not ids or not set(ids) <= component_ids:
        errors.append(f"component_ids {ids!r} are not manifests/stack.json components")
    limitations = receipt.get("limitations")
    if not isinstance(limitations, list) or not limitations or not all(isinstance(item, str) and item for item in limitations):
        errors.append("limitations must be a non-empty list of text")
    steps = set(STEP_RE.findall(recipe))
    named = {entry.get("step") for entry in receipt.get("steps", []) if isinstance(entry, dict)}
    if not named or not named <= steps:
        errors.append(f"receipt steps {sorted(map(str, named))} are not all recipe steps {sorted(steps)}")
    for entry in receipt.get("steps", []):
        if not isinstance(entry, dict) or not {"step", "cmd", "exit", "output_excerpt"} <= set(entry):
            errors.append(f"receipt step {entry!r} lacks step, cmd, exit or output_excerpt")
    return errors


def host_wide_errors(recipe: str) -> list[str]:
    errors = []
    commands = [command for _, command in fenced_commands(recipe)]
    wsl = [command for command in commands if re.search(r"(?<![\w.-])wsl(?:\.exe)?\s", command)]
    for command in commands:
        if ".wslconfig" in command:
            errors.append(f"`{command}` touches the global .wslconfig")
    for command in wsl:
        if re.search(r"--shutdown\b", command):
            errors.append(f"`{command}` shuts down every distribution, the workstation's included")
        if re.search(r"--update\b", command):
            errors.append(f"`{command}` updates WSL, which is the keys lane's decision")
        if re.search(r"(?:--set-default|\s-s)(?:\s|$)", command) and "--set-default-user" not in command:
            errors.append(f"`{command}` changes the default distribution")
        if re.search(r"--terminate\b|--unregister\b|--manage\b|\s-t(?:\s|$)", command) and "<Name>" not in command:
            errors.append(f"`{command}` acts on a distribution other than <Name>")
    installs = [command for command in wsl if re.search(r"--install\b", command)]
    if len(installs) != 1:
        errors.append(f"the recipe has {len(installs)} --install commands, expected one")
    else:
        for part in ("--from-file", IMAGE, "--name '<Name>'", "--location", "--no-launch"):
            if part not in installs[0]:
                errors.append(f"the install command lacks {part}")
    return errors


def checklist_errors(checklist: str, recipe: str) -> list[str]:
    steps, listed = STEP_RE.findall(recipe), CHECKLIST_STEP_RE.findall(checklist)
    if not steps:
        return ["the recipe has no ### W<n>. or ### F<n>. step headings"]
    errors = []
    if sorted(set(listed)) != sorted(set(steps)):
        errors.append(f"the checklist names {sorted(set(listed))}, the recipe has {sorted(set(steps))}")
    if len(listed) != len(set(listed)):
        errors.append("the checklist names a step twice")
    return errors


def section(text: str, step: str) -> str:
    """One ``### <step>.`` section of the recipe, up to the next heading."""
    match = re.search(rf"^### {re.escape(step)}\. .*?(?=^##)", text, re.M | re.S)
    return match.group(0) if match else ""


def cloud_init_status_errors(recipe: str, record: str, checklist: str) -> list[str]:
    """Review finding 1. Once /etc/cloud/cloud-init.disabled exists, cloud-init 26.1 reports ``disabled`` whatever its
    run did (cloudinit/cmd/status.py:284-286, 385-386), and ``status`` reads errors only from the boot's /run copy
    (:471-490). The checks after the first launch must expect that state and read completion and errors from the
    files kept in /var/lib/cloud/data (cloudinit/cmd/main.py:880-888, 1017-1030)."""
    errors = []
    proofs = [proof for step, _, command, proof in command_table_rows(record)
              if step == "W5" and command.endswith("cloud-init status --long")]
    if not proofs:
        errors.append("the record has no W5 `cloud-init status --long` row")
    for proof in proofs:
        if "status: disabled" not in proof or "disabled-by-marker-file" not in proof:
            errors.append("the W5 status row does not expect `status: disabled` by `disabled-by-marker-file`")
        if "status: done" in proof:
            errors.append("the W5 status row expects `status: done`, which 26.1 never prints once the marker exists")
    w5 = [command for step, _, command in recipe_rows(recipe) if step == "W5"]
    for retained in ("/var/lib/cloud/data/result.json", "/var/lib/cloud/data/status.json"):
        if not any(command.endswith(f"cat {retained}") for command in w5):
            errors.append(f"W5 does not read {retained}")
    if "status: done" in section(recipe, "W5"):
        errors.append("the recipe's W5 proof still expects `status: done`")
    line = next((line for line in checklist.splitlines() if line.startswith("- [ ] **W5**")), "")
    if "disabled-by-marker-file" not in line or "result.json" not in line or "is `done`" in line:
        errors.append("the checklist's W5 line does not expect the marker state and the retained result")
    return errors


def landscape_preflight_errors(recipe: str) -> list[str]:
    """Review finding 2. In cloud-init 26.1 the Landscape instance file replaces the local user-data
    (cloudinit/sources/DataSourceWSL.py:241-270, 465-476), and every top-level key of agent.yaml replaces the
    user-data's key (:317-336, called at :490). W1 therefore tests both files and lists agent.yaml's top-level keys."""
    w1 = [command for step, _, command in recipe_rows(recipe) if step == "W1"]
    errors = [f"W1 does not test for {name}" for name in
              (r".ubuntupro\.cloud-init\<Name>.user-data", r".ubuntupro\.cloud-init\agent.yaml")
              if not any(command.startswith("Test-Path") and name in command for command in w1)]
    if not any(command.startswith("Select-String") and "agent.yaml" in command for command in w1):
        errors.append("W1 does not list the top-level keys of agent.yaml")
    if "`users:`" not in section(recipe, "W1") or "`write_files:`" not in section(recipe, "W1"):
        errors.append("W1's proof does not name the agent.yaml keys that would replace the user-data's")
    return errors


def path_proof_errors(recipe: str) -> list[str]:
    """Review finding 3. ``type -P`` can print a stale hashed or non-executable path and still exit 0
    (adoption/platforms/linux-wsl2.md, Windows Terminal step 2), so F10 tests every printed path with ``test -f`` and
    ``test -x``."""
    f10 = [command for step, _, command in recipe_rows(recipe) if step == "F10"]
    if any("type -P claude codex" in command and "test -f" in command and "test -x" in command for command in f10):
        return []
    return ["F10 does not test each path `type -P claude codex` prints with `test -f` and `test -x`"]


class UserDataTemplateTests(unittest.TestCase):
    def test_the_template_renders_to_the_recipe_user(self):
        self.assertEqual(user_data_errors(read(USER_DATA)), [])

    def test_the_check_rejects_a_bom_a_stray_dollar_a_password_and_a_lost_line(self):
        good = read(USER_DATA)
        mutants = {
            "bom": "﻿" + good,
            "stray dollar": good.replace("lock_passwd: true", "lock_passwd: true\n  homedir: $HOME"),
            "password": good.replace("lock_passwd: true", "lock_passwd: true\n  plain_text_passwd: x"),
            "sudo with a password": good.replace("NOPASSWD:ALL", "ALL"),
            "no default user": good.replace("default=", "default_user="),
            "header": good.replace("#cloud-config", "# cloud-config", 1),
        }
        for name, mutant in mutants.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(mutant, good)
                self.assertTrue(user_data_errors(mutant))


class HostTemplateTests(unittest.TestCase):
    def test_the_host_template_renders_with_example_keys_and_free_ports(self):
        example = json.loads(read(HOST_EXAMPLE))
        self.assertEqual(host_template_errors(read(HOST_TEMPLATE), example, read(RECIPE)), [])

    def test_the_check_rejects_a_workstation_port_a_lost_key_and_a_stale_probe(self):
        example, good, recipe = json.loads(read(HOST_EXAMPLE)), read(HOST_TEMPLATE), read(RECIPE)
        port = re.search(r'"AI_MEMORY_URL": "127\.0\.0\.1:(\d+)"', good).group(1)
        mutants = {
            "workstation port": (good.replace(f"127.0.0.1:{port}", "127.0.0.1:49374"), recipe),
            "lost key": (re.sub(r'\s*"EMBED_URL": "[^"]*",?', "", good).replace('",\n}', '"\n}'), recipe),
            "stale probe": (good, recipe.replace(f"sport = :{port}", "sport = :1")),
            "missing exclusion": (good, recipe.replace("`49474`", "49474")),
        }
        for name, (template, page) in mutants.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(template + page, good + recipe)
                self.assertTrue(host_template_errors(template, example, page))


class CommandTableTests(unittest.TestCase):
    def test_every_recipe_command_is_a_row_of_the_record_command_table(self):
        self.assertEqual(command_table_errors(read(RECIPE), read(RECORD)), [])

    def test_the_check_rejects_a_missing_row_an_extra_row_a_wrong_shell_and_a_wrong_step(self):
        recipe, record = read(RECIPE), read(RECORD)
        step, shell, command = recipe_rows(recipe)[0]
        row = next(line for line in record.splitlines()
                   if line.startswith(f"| {step} | {shell} | `{command.replace('|', chr(92) + '|')}` |"))
        other = "sh" if shell == "powershell" else "powershell"
        mutants = {
            "missing row": record.replace(row + "\n", ""),
            "extra row": record.replace(row + "\n", row + "\n| X9 | sh | `echo stale` | none |\n"),
            "wrong shell": record.replace(row, row.replace(f"| {shell} |", f"| {other} |", 1)),
            "wrong step": record.replace(row, row.replace(f"| {step} |", "| F99 |", 1)),
        }
        for name, mutant in mutants.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(mutant, record)
                self.assertTrue(command_table_errors(recipe, mutant))

    def test_commands_are_read_from_indented_fences_with_continuations(self):
        text = "1. Step\n\n   ```sh\n   # comment\n   apt-get install \\\n     jq\n   ```\n\n```text\nnot a command\n```\n"
        self.assertEqual(fenced_commands(text), [("sh", "apt-get install jq")])


class ImageHashTests(unittest.TestCase):
    def test_the_recipe_record_receipt_example_and_checklist_name_one_image_sha256(self):
        receipt = json.loads(read(RECEIPT_EXAMPLE))
        self.assertEqual(sha256_errors(read(RECIPE), read(RECORD), receipt, read(CHECKLIST)), [])

    def test_the_check_rejects_a_drifted_hash(self):
        recipe, record, checklist = read(RECIPE), read(RECORD), read(CHECKLIST)
        receipt = json.loads(read(RECEIPT_EXAMPLE))
        (expected,) = set(SHA256_RE.findall(recipe))
        other = "0" * 64
        self.assertTrue(sha256_errors(recipe, record.replace(expected, other), receipt, checklist))
        self.assertTrue(sha256_errors(recipe.replace(expected, other, 1), record, receipt, checklist))
        self.assertTrue(sha256_errors(recipe, record, dict(receipt, image=dict(receipt["image"], sha256_published=other)),
                                      checklist))
        self.assertTrue(sha256_errors(recipe, record, receipt, checklist.replace(expected, other)))


class ReceiptExampleTests(unittest.TestCase):
    def setUp(self):
        self.components = {component["id"] for component in json.loads(read(STACK))["components"]}

    def test_the_receipt_example_carries_the_validated_payload_keys(self):
        self.assertEqual(receipt_errors(json.loads(read(RECEIPT_EXAMPLE)), read(RECIPE), self.components), [])

    def test_the_check_rejects_an_unknown_kind_component_and_step(self):
        receipt, recipe = json.loads(read(RECEIPT_EXAMPLE)), read(RECIPE)
        for name, mutant in {"kind": dict(receipt, kind="host_run"),
                             "component": dict(receipt, component_ids=["wsl-distro"]),
                             "step": dict(receipt, steps=[*receipt["steps"], {"step": "W99", "cmd": "x", "exit": 0,
                                                                              "output_excerpt": ""}]),
                             "limitations": dict(receipt, limitations=[])}.items():
            with self.subTest(mutant=name):
                self.assertTrue(receipt_errors(mutant, recipe, self.components))


class HostWideRuleTests(unittest.TestCase):
    def test_no_recipe_command_changes_wsl_for_the_other_distributions(self):
        self.assertEqual(host_wide_errors(read(RECIPE)), [])

    def test_the_check_rejects_shutdown_update_wslconfig_default_and_foreign_targets(self):
        recipe = read(RECIPE)
        for added in ("wsl.exe --shutdown", "wsl.exe --update", "notepad.exe $env:USERPROFILE\\.wslconfig",
                      "wsl.exe --set-default <Name>", "wsl.exe --terminate Ubuntu", "wsl.exe --unregister Ubuntu"):
            with self.subTest(added=added):
                mutant = recipe.replace("```powershell\n", f"```powershell\n{added}\n", 1)
                self.assertTrue(host_wide_errors(mutant))
        self.assertTrue(host_wide_errors(recipe.replace(" --no-launch", "", 1)))


class ChecklistTests(unittest.TestCase):
    def test_the_checklist_names_exactly_the_recipe_steps(self):
        self.assertEqual(checklist_errors(read(CHECKLIST), read(RECIPE)), [])

    def test_the_check_rejects_a_missing_and_a_duplicated_step(self):
        checklist, recipe = read(CHECKLIST), read(RECIPE)
        first = CHECKLIST_STEP_RE.search(checklist).group(0)
        self.assertTrue(checklist_errors(checklist.replace(first, "- [ ] **gone**", 1), recipe))
        self.assertTrue(checklist_errors(checklist + f"\n{first} again\n", recipe))


class CrossFamilyReviewTests(unittest.TestCase):
    """The three findings of the 2026-10-01 GPT-6.1 Sol review of PR #569 stay fixed."""

    def test_the_first_launch_checks_expect_the_marker_and_read_the_retained_result(self):
        self.assertEqual(cloud_init_status_errors(read(RECIPE), read(RECORD), read(CHECKLIST)), [])

    def test_the_status_check_rejects_status_done_and_a_missing_retained_result(self):
        recipe, record, checklist = read(RECIPE), read(RECORD), read(CHECKLIST)
        row = next(line for line in record.splitlines()
                   if line.startswith("| W5 |") and line.split("|")[3].strip().endswith("cloud-init status --long`"))
        retained = "wsl.exe -d '<Name>' -u root --exec cat /var/lib/cloud/data/result.json\n"
        marker = "prints `status: disabled` with `boot_status_code: disabled-by-marker-file`"
        self.assertIn(retained, recipe)
        self.assertIn(marker, checklist)
        mutants = {
            "status done": (recipe, record.replace(row, row.replace("`status: disabled`", "`status: done`")), checklist),
            "no result.json": (recipe.replace(retained, ""), record, checklist),
            "checklist done": (recipe, record, checklist.replace(marker, "is `done` with no errors")),
        }
        for name, (page, table, ticks) in mutants.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(page + table + ticks, recipe + record + checklist)
                self.assertTrue(cloud_init_status_errors(page, table, ticks))

    def test_the_preflight_checks_both_ubuntu_pro_files(self):
        self.assertEqual(landscape_preflight_errors(read(RECIPE)), [])

    def test_the_preflight_check_rejects_a_missing_agent_yaml_test(self):
        recipe = read(RECIPE)
        line = "Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.ubuntupro\\.cloud-init\\agent.yaml')\n"
        self.assertIn(line, recipe)
        self.assertTrue(landscape_preflight_errors(recipe.replace(line, "")))

    def test_the_path_proof_tests_each_printed_path(self):
        self.assertEqual(path_proof_errors(read(RECIPE)), [])

    def test_the_path_proof_check_rejects_type_p_alone(self):
        recipe = read(RECIPE)
        self.assertIn("test -x $p && ", recipe)
        self.assertTrue(path_proof_errors(recipe.replace("test -x $p && ", "")))


if __name__ == "__main__":
    unittest.main()
