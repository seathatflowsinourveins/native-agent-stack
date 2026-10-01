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
- the first-boot checklist names exactly the recipe's steps, and the receipt example holds one entry per recipe command
  line, under its step, once per occurrence, and nothing else (review finding 1 of PR #569);
- the three findings of the 2026-10-01 cross-family review stay fixed:
  - after the first launch, W5 expects ``status: disabled`` by ``disabled-by-marker-file`` and reads completion and
    errors from /var/lib/cloud/data/result.json and status.json (cloud-init 26.1 cloudinit/cmd/status.py:284-286 and
    cloudinit/cmd/main.py:1017-1030);
  - W1 tests both Ubuntu Pro files, the Landscape instance file and agent.yaml
    (cloudinit/sources/DataSourceWSL.py:241-270 and 317-336);
  - F10 tests every path ``type -P`` prints with ``test -f`` and ``test -x``;
- F11 (added 2026-10-01) runs adoption/bootstrap.md step 4a's own ``claude mcp add --scope local jcodemunch`` line,
  identical once continuations are joined, from the clone's root, after F9 (stage 2) and F10. It runs in a block after
  the one that tests the binary, so a script run never registers a missing binary, and ``claude mcp get jcodemunch``
  proves it. The checklist and the receipt example record its outcome (registered, not installed or skipped), and the
  record cites Claude Code's MCP page;
- F5 keeps 65,536 subordinate ids as the stage-1 value and cites Docker's rootless troubleshooting page for the
  ``lchown <FILE>: invalid argument`` error that says an image needs more; the record lists that page too;
- W6 (review finding 3 of PR #569) stops ``<Name>`` and exports it with Microsoft's ``wsl --export`` into W1's log folder
  in the same block as ``--unregister`` and before it. A nonzero exit throws before the deletion, the file's SHA-256 and
  size go to the receipt's ``failed_attempt_export``, and the checklist and the record say so;
- the follow-up of 2026-10-01 to the completeness critic (items B to G of its brief) stays in place, each rule bound
  to the recipe, the record, the checklist and the receipt example:
  - B: P1 verifies the signed SHA256SUMS with ``gpgv`` and the installed archive keyring, no key import, before stage 1;
  - C1: P2 renders the user-data the way W3 does and runs ``cloud-init schema -c`` before any boot, and W3 prints the
    Windows file's SHA-256 to compare with P2's;
  - C2: W5 runs ``cloud-init schema --system`` as root on path A, and W6 skips it on path B;
  - D: P3 counts ``hv_storvsc`` lines of the current boot's kernel journal, without the driver's registration line,
    and stops on a nonzero count (microsoft/WSL#41482);
  - E1 and E2: W7 terminates ``<Name>`` once after the first launch, relaunches it and reads the owner of a file created
    from Windows (microsoft/WSL#40941, PR #40977);
  - F: W1 reads the two idle keys of the global WSL configuration, F2 observes ``<Name>`` for two minutes with no client
    attached, and the host-wide check passes a plain ``Select-String`` or ``grep`` read of ``.wslconfig`` and nothing
    else that names it;
  - G: R1, the page's first step, rehearses on a throwaway name and removes only that name, exporting it first when
    the rehearsal failed.

These are local consistency checks over repository text and an in-memory render of the templates.
Nothing here runs wsl.exe, PowerShell, gpgv, journalctl or cloud-init; a pass is not a host run.
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
BOOTSTRAP = ROOT / "adoption/bootstrap.md"

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
# F11: the code block right after this lead in adoption/bootstrap.md (step 4a) is the per-project registration.
JCODEMUNCH_LEAD = "**jCodeMunch, per project.**"
JCODEMUNCH_OUTCOMES = ("registered", "not installed", "skipped")
CLONE = "cd ~/code/native-agent-stack"
CLAUDE_MCP_PAGE = "https://code.claude.com/docs/en/mcp"
# F5: Docker says 65,536 entries suffice for most images and names the error an image that needs more produces.
DOCKER_TROUBLESHOOT = "https://docs.docker.com/engine/security/rootless/troubleshoot/"
SUBORDINATE_IDS = 65536
# W6 (review finding 3 of PR #569): the failed attempt is exported before --unregister deletes its disk.
UNREGISTER = "wsl.exe --unregister '<Name>'"
TERMINATE = "wsl.exe --terminate '<Name>'"
EXPORT_RE = re.compile(r"wsl\.exe --export '<Name>' '(?P<file>Z:\\WSL\\downloads\\[^']+\.tar)'")
EXPORT_GUARD = "if ($LASTEXITCODE -ne 0) { throw 'export failed: do not unregister' }"
BASIC_COMMANDS = "https://learn.microsoft.com/en-us/windows/wsl/basic-commands"
BASIC_COMMANDS_TITLE = '"Basic commands for WSL"'
# The 2026-10-01 follow-up (the completeness critic's pre-stage-1 checks). R1 rehearses and removes a throwaway
# distribution, P1 to P3 are sh pre-checks in the workstation distribution, W7 terminates once and probes ownership.
EXPERIMENT = ROOT / "blueprints/convergence-practice/wsl-new-distro-image-20261001/experiment.json"
SUMS_URL = "https://releases.ubuntu.com/24.04.5/SHA256SUMS"
CD_IMAGE_SIGNER = "843938DF228D22F7B3742BC0D94AA3F0EFE21092"
P1_COMMANDS = [
    'SUMS_DIR="$(mktemp -d)"',
    f'curl -fsSL -o "$SUMS_DIR/SHA256SUMS" {SUMS_URL}',
    f'curl -fsSL -o "$SUMS_DIR/SHA256SUMS.gpg" {SUMS_URL}.gpg',
    'gpgv --homedir "$SUMS_DIR" --keyring /usr/share/keyrings/ubuntu-archive-keyring.gpg "$SUMS_DIR/SHA256SUMS.gpg" '
    '"$SUMS_DIR/SHA256SUMS"',
    "grep ' \\*ubuntu-24\\.04\\.5-wsl-amd64\\.wsl$' \"$SUMS_DIR/SHA256SUMS\"",
]
P2_RENDER = ("python3 -c 'import string, sys; sys.stdout.write(string.Template(open(sys.argv[1], encoding=\"utf-8\")"
             ".read()).substitute(WSL_USER=sys.argv[2]))' adoption/templates/wsl/cloud-init.user-data.template "
             "'<WSL_USER>' > \"$RENDER_DIR/<Name>.user-data\"")
P2_COMMANDS = ['RENDER_DIR="$(mktemp -d)"', P2_RENDER, "cloud-init --version",
               'cloud-init schema -c "$RENDER_DIR/<Name>.user-data"', 'sha256sum "$RENDER_DIR/<Name>.user-data"']
W3_HASH = ("(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $env:USERPROFILE '.cloud-init\\<Name>.user-data'))"
           ".Hash.ToLowerInvariant()")
SCHEMA_SYSTEM = "wsl.exe -d '<Name>' -u root --exec cloud-init schema --system"
SCHEMA_LINE = "`^\\s*Valid schema user-data$`"
CLOUD_INIT_HOWTO = "https://ubuntu.com/wsl/docs/stable/howto/cloud-init/"
STORVSC_COUNT = "sudo journalctl -k -b 0 --no-pager | grep hv_storvsc | grep -vc 'registering driver hv_storvsc'"
P3_COMMANDS = [STORVSC_COUNT, "swapon --show"]
STORVSC_ISSUE = "https://github.com/microsoft/WSL/issues/41482"
OWNER_ISSUE = "https://github.com/microsoft/WSL/issues/40941"
OWNER_FIX = "https://github.com/microsoft/WSL/pull/40977"
OWNER_FIX_QUOTE = "this only recovers after a distro termination"
RELAUNCH = "wsl.exe -d '<Name>' --exec id -un"
PROBE_SHARE = r"\\wsl.localhost\<Name>\home\<WSL_USER>\wsl-owner-probe"
PROBE_CREATE = f"New-Item -ItemType File -Path '{PROBE_SHARE}'"
PROBE_OWNER = "wsl.exe -d '<Name>' --exec stat -c %u:%g '/home/<WSL_USER>/wsl-owner-probe'"
PROBE_DELETE = f"Remove-Item -LiteralPath '{PROBE_SHARE}'"
IDLE_READ = ("Select-String -LiteralPath (Join-Path $env:USERPROFILE '.wslconfig') -Pattern '^\\s*\\[', "
             "'^\\s*instanceIdleTimeout\\s*=', '^\\s*vmIdleTimeout\\s*=' -ErrorAction SilentlyContinue")
IDLE_POLL = ("foreach ($Poll in 1..12) { Start-Sleep -Seconds 10; [DateTime]::UtcNow.ToString('HH:mm:ss'); "
             "wsl.exe --list --running --quiet }")
REHEARSAL_TAR = r"Z:\WSL\downloads\<Name>-rehearsal.tar"
REHEARSAL_EXPORT = f"wsl.exe --export '<Name>' '{REHEARSAL_TAR}'"
REHEARSAL_FIELDS = {"name", "result", "creation_path", "schema_system", "ownership_probe", "idle_observation", "export"}

SHA256_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
FENCE_RE = re.compile(r"^(?P<indent>[ \t]*)```(?P<lang>[\w-]*)[^\n]*\n(?P<body>.*?)^(?P=indent)```[ \t]*$", re.M | re.S)
STEP_RE = re.compile(r"^### (?P<step>[RPWF]\d+)\. ", re.M)
CHECKLIST_STEP_RE = re.compile(r"^- \[ \] \*\*(?P<step>[RPWF]\d+)\*\*", re.M)


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
    # Review finding 1 of PR #569: the receipt carries every W and F command, so its entries are compared with the
    # recipe's command rows (the rows the command-table check reads), once per occurrence, and nothing else.
    rows = recipe_rows(recipe)
    steps = set(STEP_RE.findall(recipe))
    if {step for step, _, _ in rows} != steps:
        errors.append(f"recipe steps without a command line: {sorted(steps - {step for step, _, _ in rows})}")
    entries = [entry for entry in receipt.get("steps", []) if isinstance(entry, dict)]
    named = {str(entry.get("step")) for entry in entries}
    if named != steps:
        errors.append(f"receipt steps {sorted(named)} are not the recipe steps {sorted(steps)}")
    expected = Counter((step, command) for step, _, command in rows)
    listed = Counter((str(entry.get("step")), str(entry.get("cmd"))) for entry in entries)
    errors += [f"the receipt example lacks recipe command {step}: {command}"
               for (step, command), count in sorted((expected - listed).items()) for _ in range(count)]
    errors += [f"receipt entry is not a recipe command: {step}: {command}"
               for (step, command), count in sorted((listed - expected).items()) for _ in range(count)]
    for entry in receipt.get("steps", []):
        if not isinstance(entry, dict) or not {"step", "cmd", "exit", "output_excerpt"} <= set(entry):
            errors.append(f"receipt step {entry!r} lacks step, cmd, exit or output_excerpt")
    return errors


def reads_wslconfig(shell: str, command: str) -> bool:
    """Item F of the 2026-10-01 follow-up: W1 reports the two idle keys of the global WSL configuration. A command that
    names .wslconfig passes only as a plain read, ``Select-String`` in PowerShell or ``grep`` in sh, with no pipe, no
    redirection and no second statement, so nothing it prints reaches a writer."""
    head = command.split(maxsplit=1)[0] if command.strip() else ""
    return {"powershell": "Select-String", "sh": "grep"}.get(shell) == head and not re.search(r"[|>;&]", command)


def host_wide_errors(recipe: str) -> list[str]:
    errors = []
    commands = [command for _, command in fenced_commands(recipe)]
    wsl = [command for command in commands if re.search(r"(?<![\w.-])wsl(?:\.exe)?\s", command)]
    for shell, command in fenced_commands(recipe):
        if ".wslconfig" in command and not reads_wslconfig(shell, command):
            errors.append(f"`{command}` touches the global .wslconfig other than by a plain read")
    for command in wsl:
        if re.search(r"--shutdown\b", command):
            errors.append(f"`{command}` shuts down every distribution, the workstation's included")
        if re.search(r"--update\b", command):
            errors.append(f"`{command}` updates WSL, which is the keys lane's decision")
        if re.search(r"(?:--set-default|\s-s)(?:\s|$)", command) and "--set-default-user" not in command:
            errors.append(f"`{command}` changes the default distribution")
        if re.search(r"--terminate\b|--unregister\b|--export\b|--manage\b|\s-t(?:\s|$)", command) and "<Name>" not in command:
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


def step_blocks(recipe: str, step: str) -> list[list[str]]:
    """The command lines of each ``powershell`` or ``sh`` code block of one recipe step, one list per block."""
    return [[command for _, command in fenced_commands(match.group(0))]
            for match in FENCE_RE.finditer(section(recipe, step)) if match["lang"] in SHELLS]


def bootstrap_registration(bootstrap: str) -> list[str]:
    """The command lines of the first code block after adoption/bootstrap.md's "jCodeMunch, per project" lead."""
    _, lead, rest = bootstrap.partition(JCODEMUNCH_LEAD)
    match = FENCE_RE.search(rest) if lead else None
    return [command for _, command in fenced_commands(match.group(0))] if match else []


def jcodemunch_errors(recipe: str, bootstrap: str, record: str, checklist: str, receipt: dict) -> list[str]:
    """F11. Four of the six SubagentStart carrier blocks name jCodeMunch tools. The user-scope MCP template leaves the
    server out, because it registers per project (the 2026-09-25 addendum of
    docs/decisions/2026-09-23-claude-user-profile.md), and no script registers it. F11 runs bootstrap step 4a's own line
    from the clone's root, where local scope is keyed (Claude Code's MCP page), after stage 2 and the PATH proof. It runs
    in a block after the binary test, because one block run as a script would register a missing binary. Every outcome
    is recorded."""
    expected = bootstrap_registration(bootstrap)
    if len(expected) != 1 or not expected[0].startswith("claude mcp add --scope local jcodemunch "):
        return [f"adoption/bootstrap.md's jCodeMunch block is not one `claude mcp add --scope local jcodemunch` line: "
                f"{expected!r}"]
    (registration,) = expected
    binary_test = "test -x " + registration.rsplit(" -- ", 1)[-1]
    steps = STEP_RE.findall(recipe)
    if "F11" not in steps:
        return ["the recipe has no ### F11. step"]
    errors = []
    if not all(step in steps and steps.index(step) < steps.index("F11") for step in ("F9", "F10")):
        errors.append("F11 does not come after stage 2 (F9) and the PATH proof (F10)")
    blocks = step_blocks(recipe, "F11")
    holding = [index for index, block in enumerate(blocks) if registration in block]
    if len(holding) != 1 or blocks[holding[0]].count(registration) != 1:
        errors.append("F11 does not run bootstrap step 4a's registration line exactly once")
    else:
        index = holding[0]
        block = blocks[index]
        if block[:1] != [CLONE]:
            errors.append(f"F11's registration block does not start with `{CLONE}`; local scope is keyed to that path")
        if "claude mcp get jcodemunch" not in block[block.index(registration) + 1:]:
            errors.append("F11 does not prove the registration with `claude mcp get jcodemunch`")
        if binary_test in block:
            errors.append("F11 tests the binary in the registration's own block, so a script run registers a missing one")
        if not any(binary_test in earlier for earlier in blocks[:index]):
            errors.append(f"F11 does not run `{binary_test}` in a block before the registration")
    line = next((line for line in checklist.splitlines() if line.startswith("- [ ] **F11**")), "")
    if not all(part in line for part in ("claude mcp get jcodemunch", *JCODEMUNCH_OUTCOMES[1:])):
        errors.append("the checklist's F11 line does not name the proof and the not-installed and skipped outcomes")
    field = receipt.get("jcodemunch_registration") if isinstance(receipt, dict) else None
    if not isinstance(field, str) or not field.startswith("<F11:") or not all(part in field for part in JCODEMUNCH_OUTCOMES):
        errors.append("the receipt example has no jcodemunch_registration field naming F11's three outcomes")
    if CLAUDE_MCP_PAGE not in record:
        errors.append("the record does not cite Claude Code's MCP page for local scope")
    return errors


def failed_attempt_errors(recipe: str, record: str, checklist: str, receipt: dict) -> list[str]:
    """Review finding 3 of PR #569 (2026-10-01). ``--unregister`` loses all data of the distribution (Microsoft, "Basic
    commands for WSL"), so W6 stops ``<Name>`` and exports it with ``wsl --export <Distribution Name> <FileName>`` into
    W1's log folder. The export comes in the same block as ``--unregister`` and before it, a nonzero exit throws before
    the deletion, and the file's SHA-256 and size go to the receipt's ``failed_attempt_export``."""
    blocks = [block for block in step_blocks(recipe, "W6") if UNREGISTER in block]
    if len(blocks) != 1:
        return [f"W6 has {len(blocks)} blocks with `{UNREGISTER}`, expected one"]
    (block,) = blocks
    before = block[:block.index(UNREGISTER)]
    exports = [line for line in block if EXPORT_RE.fullmatch(line)]
    errors = []
    if len(exports) != 1 or exports[0] not in before:
        errors.append("W6 does not export '<Name>' into Z:\\WSL\\downloads before `--unregister` in the same block")
    else:
        (export,) = exports
        file = EXPORT_RE.fullmatch(export)["file"]
        after_export = before[before.index(export) + 1:]
        if TERMINATE not in before[:before.index(export)]:
            errors.append("W6 does not stop <Name> with `--terminate` before the export")
        for needed in (EXPORT_GUARD, f"(Get-FileHash -Algorithm SHA256 -LiteralPath '{file}').Hash.ToLowerInvariant()",
                       f"(Get-Item -LiteralPath '{file}').Length"):
            if needed not in after_export:
                errors.append(f"W6 does not run `{needed}` between the export and `--unregister`")
    w6 = section(recipe, "W6")
    for named in ("/var/log/cloud-init*.log", "/var/lib/cloud/instance", "failed_attempt_export", BASIC_COMMANDS_TITLE):
        if named not in w6:
            errors.append(f"W6's text does not name {named}")
    line = next((line for line in checklist.splitlines() if line.startswith("- [ ] **W6**")), "")
    if ("--export" not in line and "exported" not in line) or "failed_attempt_export" not in line:
        errors.append("the checklist's W6 line does not require the export and failed_attempt_export")
    field = receipt.get("failed_attempt_export") if isinstance(receipt, dict) else None
    if not isinstance(field, dict) or set(field) != {"file", "sha256", "bytes"} or not all(
            isinstance(value, str) and value.startswith("<W6") for value in field.values()):
        errors.append("the receipt example has no failed_attempt_export with W6 placeholders for file, sha256 and bytes")
    if "wsl --export <Distribution Name> <FileName>" not in record or BASIC_COMMANDS not in record:
        errors.append("the record does not cite Microsoft's `wsl --export` form from Basic commands for WSL")
    return errors


def subordinate_id_errors(recipe: str, record: str) -> list[str]:
    """F5 adds 65,536 subordinate uids and gids, the stage-1 value. A wider range is an image-set need: Docker's rootless
    troubleshooting page gives the error an image that needs more produces, and both the page and the record cite it."""
    ranges = [(int(low), int(high)) for step, _, command in recipe_rows(recipe) if step == "F5"
              for low, high in re.findall(r"--add-sub[ug]ids (\d+)-(\d+)", command)]
    errors = []
    if len(ranges) != 2 or any(high - low + 1 != SUBORDINATE_IDS for low, high in ranges):
        errors.append(f"F5 does not add {SUBORDINATE_IDS} subordinate uids and gids: {ranges}")
    f5 = section(recipe, "F5")
    if DOCKER_TROUBLESHOOT not in f5 or "lchown <FILE>: invalid argument" not in f5:
        errors.append("F5 does not say, with Docker's troubleshooting page, when more than 65,536 ids are needed")
    if DOCKER_TROUBLESHOOT not in record:
        errors.append("the record's sources lack Docker's rootless troubleshooting page")
    return errors


def step_commands(recipe: str, step: str) -> list[tuple[str, str]]:
    """(shell, command) for every command line of one recipe step, in page order."""
    return [(shell, command) for name, shell, command in recipe_rows(recipe) if name == step]


def chapter(text: str, title: str) -> str:
    """The ``## <title>`` section of a Markdown text, up to the next level-2 heading."""
    match = re.search(rf"^## {re.escape(title)}\n.*?(?=^## |\Z)", text, re.M | re.S)
    return match.group(0) if match else ""


def prose(text: str) -> str:
    """Markdown text with each run of whitespace as one space, so a phrase check does not depend on line wrapping."""
    return re.sub(r"\s+", " ", text)


def checklist_line(checklist: str, step: str) -> str:
    return next((line for line in checklist.splitlines() if line.startswith(f"- [ ] **{step}**")), "")


def field(receipt: object, *keys: str) -> object:
    for key in keys:
        receipt = receipt.get(key) if isinstance(receipt, dict) else None
    return receipt


def is_placeholder(value: object, prefix: str) -> bool:
    return isinstance(value, str) and value.startswith(prefix) and value.endswith(">")


def before_stage_1(steps: list[str], step: str) -> bool:
    """The step comes before every W step, so before anything is downloaded on Windows or installed."""
    return step in steps and all(steps.index(step) < index for index, name in enumerate(steps) if name.startswith("W"))


def signed_sums_errors(recipe: str, record: str, checklist: str, receipt: dict) -> list[str]:
    """Item B (critic item 5). W2 compares the image with Canonical's SHA256SUMS but nothing checked that list's signature.
    Before stage 1, P1 downloads SHA256SUMS and SHA256SUMS.gpg into an empty temporary directory and verifies them with
    gpgv, that directory as gpgv's home and the archive keyring Ubuntu installs (no key import), then prints the image's
    signed line. The record keeps this unit's own run with a tampered-copy control."""
    steps = STEP_RE.findall(recipe)
    if "P1" not in steps:
        return ["the recipe has no ### P1. step (the signed checksums)"]
    errors = [] if before_stage_1(steps, "P1") else ["P1 does not run before stage 1 (W1), before anything is installed"]
    commands = step_commands(recipe, "P1")
    if {shell for shell, _ in commands} != {"sh"}:
        errors.append("P1 is not an sh step of the workstation distribution")
    lines = [command for _, command in commands]
    missing = [line for line in P1_COMMANDS if line not in lines]
    errors += [f"P1 lacks `{line}`" for line in missing]
    if not missing and [lines.index(line) for line in P1_COMMANDS] != sorted(lines.index(line) for line in P1_COMMANDS):
        errors.append("P1 does not create the directory, download both files, verify and print the line in that order")
    if any(re.search(r"--recv-keys|--keyserver|--import\b", line) or re.match(r"gpg\s", line) for line in lines):
        errors.append("P1 imports a key or runs gpg; it verifies with gpgv against the installed keyring only")
    p1 = prose(section(recipe, "P1"))
    errors += [f"P1's text does not name {needed}" for needed in (CD_IMAGE_SIGNER, "Good signature", "`ubuntu-keyring`")
               if needed not in p1]
    evidence = prose(chapter(record, "Evidence classes"))
    errors += [f"the record's Evidence classes lack P1's {needed}" for needed in
               (P1_COMMANDS[3], "Good signature", CD_IMAGE_SIGNER, "BAD signature") if needed not in evidence]
    line = checklist_line(checklist, "P1")
    if "Good signature" not in line or CD_IMAGE_SIGNER not in line:
        errors.append("the checklist's P1 line does not require the good signature by the CD image key")
    if not is_placeholder(field(receipt, "pre_checks", "signed_sums"), "<P1"):
        errors.append("the receipt example has no pre_checks.signed_sums placeholder for P1")
    return errors


def user_data_schema_errors(recipe: str, record: str, checklist: str, receipt: dict) -> list[str]:
    """Item C1 (critic item 5). Before any boot, P2 renders the user-data with F8's string.Template program, which writes
    the bytes of W3's literal replace, and validates it with ``cloud-init schema -c``. P2 prints the render's SHA-256 and
    W3 prints the SHA-256 of the file it writes on Windows, so the two can be compared."""
    steps = STEP_RE.findall(recipe)
    if "P2" not in steps:
        return ["the recipe has no ### P2. step (the user-data schema)"]
    errors = [] if before_stage_1(steps, "P2") else ["P2 does not run before stage 1, so before any boot"]
    commands = step_commands(recipe, "P2")
    if {shell for shell, _ in commands} != {"sh"}:
        errors.append("P2 is not an sh step of the workstation distribution")
    lines = [command for _, command in commands]
    errors += [f"P2 lacks `{line}`" for line in P2_COMMANDS if line not in lines]
    f8 = next((command for step, _, command in recipe_rows(recipe) if step == "F8" and command.startswith("python3 -c ")), "")
    if f8.split("' ", 1)[0] != P2_RENDER.split("' ", 1)[0]:
        errors.append("P2 does not render with F8's string.Template program")
    if W3_HASH not in [command for _, command in step_commands(recipe, "W3")]:
        errors.append("W3 does not print the SHA-256 of the file it writes, to compare with P2's")
    p2 = prose(section(recipe, "P2"))
    errors += [f"P2's text does not name {needed}" for needed in ("`Valid schema`", "W3") if needed not in p2]
    evidence = prose(chapter(record, "Evidence classes"))
    errors += [f"the record's Evidence classes lack P2's {needed}" for needed in
               ("cloud-init schema -c", "Valid schema", "Invalid schema", "cloud-init 26.1-0ubuntu1~24.04.1")
               if needed not in evidence]
    if "Valid schema" not in checklist_line(checklist, "P2") or "P2" not in checklist_line(checklist, "W3"):
        errors.append("the checklist does not require P2's valid schema and W3's hash equal to P2's")
    if not is_placeholder(field(receipt, "pre_checks", "user_data_schema"), "<P2"):
        errors.append("the receipt example has no pre_checks.user_data_schema placeholder for P2")
    return errors


def schema_system_errors(recipe: str, record: str, checklist: str, receipt: dict) -> list[str]:
    """Item C2 (critic item 5). After the first launch on path A, W5 runs Canonical's check, ``cloud-init schema
    --system`` as root, and expects a line matching ``^\\s*Valid schema user-data$`` with exit 0. Path B skips it: when
    cloud-init never ran, the command exits 1 (``Config file ... does not exist``; a source reading)."""
    errors = []
    if [command for _, command in step_commands(recipe, "W5")].count(SCHEMA_SYSTEM) != 1:
        errors.append(f"W5 does not run `{SCHEMA_SYSTEM}` once")
    if any("schema --system" in command for _, command in step_commands(recipe, "W6")):
        errors.append("W6 runs `cloud-init schema --system` on path B")
    if SCHEMA_LINE not in prose(section(recipe, "W5")):
        errors.append(f"W5's proof does not require a line matching {SCHEMA_LINE}")
    w6 = prose(section(recipe, "W6"))
    if "skip `cloud-init schema --system`" not in w6 or "does not exist" not in w6:
        errors.append("W6 does not say to skip `cloud-init schema --system` on path B, and why")
    proofs = [proof for step, _, command, proof in command_table_rows(record) if step == "W5" and command == SCHEMA_SYSTEM]
    if len(proofs) != 1 or "Valid schema user-data" not in proofs[0]:
        errors.append("the record's W5 schema row does not expect `Valid schema user-data`")
    if CLOUD_INIT_HOWTO not in record:
        errors.append("the record does not cite Canonical's WSL cloud-init how-to at its current address")
    if "Valid schema user-data" not in checklist_line(checklist, "W5") or "schema --system" not in checklist_line(
            checklist, "W6"):
        errors.append("the checklist does not require the schema check on path A and its skip on path B")
    if not is_placeholder(field(receipt, "first_launch", "schema_system"), "<W5"):
        errors.append("the receipt example has no first_launch.schema_system placeholder for W5")
    return errors


def kernel_storage_errors(recipe: str, record: str, checklist: str, receipt: dict) -> list[str]:
    """Item D (critic item 3). The workstation distribution shares the kernel, so before stage 1 P3 counts the current
    boot's ``hv_storvsc`` kernel journal lines (sudo: the user cannot read the kernel journal; ``dmesg`` keeps only the
    recent ring buffer), searching for the driver name rather than a device id and leaving out the driver's
    registration line, which every boot logs, and records ``swapon --show``. A nonzero count stops the run and names
    microsoft/WSL#41482, whose workaround needs the global file and a WSL shutdown."""
    steps = STEP_RE.findall(recipe)
    if "P3" not in steps:
        return ["the recipe has no ### P3. step (the kernel storage errors)"]
    errors = [] if before_stage_1(steps, "P3") else ["P3 does not run before stage 1"]
    if step_commands(recipe, "P3") != [("sh", command) for command in P3_COMMANDS]:
        errors.append(f"P3's commands are not {P3_COMMANDS}")
    p3 = prose(section(recipe, "P3"))
    errors += [f"P3's text does not name {needed}" for needed in
               (STORVSC_ISSUE, "`0`", "exits 1", "A nonzero count stops the run", "registration line", "swap=0")
               if needed not in p3]
    evidence = prose(chapter(record, "Evidence classes"))
    errors += [f"the record's Evidence classes lack P3's {needed}" for needed in
               (STORVSC_COUNT, "swapon --show", "registering driver hv_storvsc") if needed not in evidence]
    line = checklist_line(checklist, "P3")
    if "`0`" not in line or "41482" not in line:
        errors.append("the checklist's P3 line does not require a count of 0 and name microsoft/WSL#41482")
    if not is_placeholder(field(receipt, "pre_checks", "kernel_storage_errors"), "<P3"):
        errors.append("the receipt example has no pre_checks.kernel_storage_errors placeholder for P3")
    return errors


def terminate_once_errors(recipe: str, record: str, checklist: str) -> list[str]:
    """Item E1 (critic item 2). On WSL 2.7.13 a file Windows creates after the first-run setup can be owned by 0:0
    (microsoft/WSL#40941); its fix, PR #40977, says the state "only recovers after a distro termination". W7 terminates
    ``<Name>`` once after W5's proof (path A) or W6 (path B), before F1, and relaunches it for the F steps."""
    steps = STEP_RE.findall(recipe)
    if "W7" not in steps:
        return ["the recipe has no ### W7. step (terminate once after the first launch)"]
    errors = []
    if not all(name in steps for name in ("W5", "W6", "F1")) or not (
            steps.index("W5") < steps.index("W6") < steps.index("W7") < steps.index("F1")):
        errors.append("W7 does not come after W5 and W6 and before F1")
    blocks = step_blocks(recipe, "W7")
    block = blocks[0] if blocks else []
    if block.count(TERMINATE) != 1:
        errors.append(f"W7's block does not run `{TERMINATE}` once")
    elif RELAUNCH not in block[block.index(TERMINATE) + 1:]:
        errors.append(f"W7 does not relaunch <Name> with `{RELAUNCH}` after the terminate")
    w7 = prose(section(recipe, "W7"))
    if OWNER_FIX_QUOTE not in w7 or OWNER_FIX not in w7:
        errors.append("W7 does not quote the fixing pull request, microsoft/WSL#40977")
    if OWNER_FIX not in record or OWNER_ISSUE not in record:
        errors.append("the record does not cite microsoft/WSL#40941 and its fix #40977")
    if "terminated" not in checklist_line(checklist, "W7"):
        errors.append("the checklist's W7 line does not require the terminate")
    return errors


def ownership_probe_errors(recipe: str, record: str, checklist: str, receipt: dict) -> list[str]:
    """Item E2 (critic item 2). After W7's terminate, a file created from Windows through ``\\\\wsl.localhost\\<Name>``
    under the new user's home must be owned by ``1000:1000``; ``0:0`` means the state persists, and nothing is then
    written into the distribution from Windows. Whether a terminate clears the state is an open question."""
    blocks = step_blocks(recipe, "W7")
    if not blocks:
        return ["W7 has no command block"]
    block, errors = blocks[0], []
    order = (TERMINATE, PROBE_CREATE, PROBE_OWNER, PROBE_DELETE)
    if not all(line in block for line in order):
        errors.append("W7 lacks the terminate, the file created from Windows, its owner read or its deletion")
    elif [block.index(line) for line in order] != sorted(block.index(line) for line in order):
        errors.append("W7 does not terminate, create the file, read its owner and delete it in that order")
    w7 = prose(section(recipe, "W7"))
    errors += [f"W7's text does not name {needed}" for needed in ("`1000:1000`", "`0:0`", "has not been observed")
               if needed not in w7]
    if "40941" not in chapter(recipe, "Open questions"):
        errors.append("the recipe's open questions do not ask whether a terminate clears microsoft/WSL#40941")
    if not re.search(r"^\d+\. \*\*[^*\n]*40941", chapter(record, "Open questions"), re.M):
        errors.append("the record's open questions do not ask whether a terminate clears microsoft/WSL#40941")
    if "1000:1000" not in checklist_line(checklist, "W7"):
        errors.append("the checklist's W7 line does not require 1000:1000")
    if not is_placeholder(field(receipt, "ownership_probe"), "<W7"):
        errors.append("the receipt example has no ownership_probe placeholder for W7")
    return errors


def idle_errors(recipe: str, record: str, checklist: str, receipt: dict) -> list[str]:
    """Item F (critic item 4). W1 reads the two idle keys of the global WSL configuration (``Select-String``, no write).
    After F2, with no client attached, the running distributions are listed every 10 seconds for two minutes. The page
    says what a host without ``instanceIdleTimeout=-1`` does, that changing the file is the user's decision, and that
    whether ``wsl.exe --list --running`` counts as a client is not verified. Open question 2 carries those facts."""
    errors = []
    if IDLE_READ not in [command for _, command in step_commands(recipe, "W1")]:
        errors.append("W1 does not read the two idle keys of the global WSL configuration")
    w1 = prose(section(recipe, "W1"))
    errors += [f"W1's text does not name {needed}" for needed in
               ("`instanceIdleTimeout`", "`vmIdleTimeout`", "15000", "the user's decision") if needed not in w1]
    if ("powershell", IDLE_POLL) not in step_commands(recipe, "F2"):
        errors.append("F2 does not list the running distributions every 10 seconds for two minutes")
    f2 = prose(section(recipe, "F2"))
    errors += [f"F2's text does not say {needed}" for needed in ("close every client", "is not verified") if needed not in f2]
    if "instanceIdleTimeout" not in chapter(recipe, "Open questions"):
        errors.append("the recipe's open questions do not carry the idle-timeout facts")
    match = re.search(r"^2\. .*?(?=^\d+\. |\Z)", chapter(record, "Open questions"), re.M | re.S)
    question = prose(match.group(0)) if match else ""
    errors += [f"the record's open question 2 does not name {needed}" for needed in
               ("instanceIdleTimeout=-1", "LxssUserSession.cpp:2658-2676", "13416", "9968", "is not verified")
               if needed not in question]
    if "Whether a lingering user manager keeps" in question:
        errors.append("the record's open question 2 still asks whether linger keeps the distribution running")
    if "instanceIdleTimeout" not in checklist_line(checklist, "W1") or "two minutes" not in checklist_line(checklist, "F2"):
        errors.append("the checklist does not require W1's idle keys and F2's two-minute observation")
    if not is_placeholder(field(receipt, "host", "idle_keys"), "<W1") or not is_placeholder(
            field(receipt, "idle_observation"), "<F2"):
        errors.append("the receipt example lacks host.idle_keys (W1) or idle_observation (F2)")
    return errors


def rehearsal_errors(recipe: str, record: str, checklist: str, receipt: dict, experiment: dict) -> list[str]:
    """Item G (critic item 1). R1, the page's first step, runs the page on a throwaway name and location through F3 with
    W5's schema check, W7's probe and F2's idle observation, records them in the receipt's ``rehearsal`` block, then
    terminates and unregisters that literal name: without an export when the rehearsal passed, after W6's export rule
    when it failed. Every host-wide rule holds, and the real run comes after."""
    steps = STEP_RE.findall(recipe)
    if "R1" not in steps:
        return ["the recipe has no ### R1. step (the rehearsal)"]
    errors = [] if steps[0] == "R1" else ["R1 is not the page's first step, so the rehearsal does not come first"]
    if "### R1. " not in chapter(recipe, "Rehearsal first"):
        errors.append("R1 is not in a `## Rehearsal first` section")
    r1 = prose(section(recipe, "R1"))
    errors += [f"R1's text does not name {needed}" for needed in
               ("throwaway", "through F3", "`cloud-init schema --system`", "W7", "F2", "only its own distribution",
                "W6's export rule", "`rehearsal`") if needed not in r1]
    blocks = step_blocks(recipe, "R1")
    passed = [block for block in blocks if not any("--export" in command for command in block)]
    failed = [block for block in blocks if any("--export" in command for command in block)]
    if len(passed) != 1 or len(failed) != 1:
        errors.append("R1 does not have one block for a passed rehearsal and one, with the export, for a failed one")
    else:
        for block in (*passed, *failed):
            if TERMINATE not in block or UNREGISTER not in block or block.index(TERMINATE) > block.index(UNREGISTER):
                errors.append("an R1 block does not terminate <Name> and then unregister it")
        (block,) = failed
        if REHEARSAL_EXPORT not in block or UNREGISTER not in block or block.index(REHEARSAL_EXPORT) > block.index(UNREGISTER):
            errors.append(f"R1's failed-rehearsal block does not run `{REHEARSAL_EXPORT}` before `--unregister`")
        else:
            between = block[block.index(REHEARSAL_EXPORT) + 1:block.index(UNREGISTER)]
            errors += [f"R1 does not run `{needed}` between the export and `--unregister`" for needed in
                       (EXPORT_GUARD, f"(Get-FileHash -Algorithm SHA256 -LiteralPath '{REHEARSAL_TAR}').Hash.ToLowerInvariant()",
                        f"(Get-Item -LiteralPath '{REHEARSAL_TAR}').Length") if needed not in between]
    line = checklist_line(checklist, "R1")
    if not all(part in line for part in ("throwaway", "F3", "unregistered", "exported")):
        errors.append("the checklist's R1 line does not require the rehearsal, its removal and a failed one's export")
    block = field(receipt, "rehearsal")
    if not isinstance(block, dict) or set(block) != REHEARSAL_FIELDS:
        errors.append(f"the receipt example has no rehearsal block with {sorted(REHEARSAL_FIELDS)}")
    else:
        export = block["export"]
        if not all(is_placeholder(value, "<R1") for key, value in block.items() if key != "export") or not (
                isinstance(export, dict) and set(export) == {"file", "sha256", "bytes"}
                and all(is_placeholder(value, "<R1") for value in export.values())):
            errors.append("the receipt example's rehearsal block does not hold R1 placeholders")
    if "rehearsal" not in str(experiment.get("next_decision_changing_test", "") if isinstance(experiment, dict) else ""):
        errors.append("the experiment record's next_decision_changing_test does not start with the rehearsal")
    if "R1" not in chapter(record, "Decision"):
        errors.append("the record's decision does not name the rehearsal (R1)")
    return errors


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

    def test_the_check_rejects_each_missing_f11_row(self):
        recipe, record = read(RECIPE), read(RECORD)
        rows = [line for line in record.splitlines() if line.startswith("| F11 | sh | ")]
        self.assertTrue(rows, "the record's command table has no F11 row")
        self.assertEqual(len(rows), sum(1 for step, _, _ in recipe_rows(recipe) if step == "F11"))
        for row in rows:
            with self.subTest(row=row[:70]):
                self.assertTrue(command_table_errors(recipe, record.replace(row + "\n", "", 1)))

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

    def test_the_check_rejects_a_missing_step_a_missing_command_and_an_extra_command(self):
        """Review finding 1 of PR #569: a receipt that omits a step or a command, or adds one, fails."""
        receipt, recipe = json.loads(read(RECEIPT_EXAMPLE)), read(RECIPE)
        entries = receipt["steps"]
        last = entries[-1]
        mutants = {
            "missing step": [entry for entry in entries if entry["step"] != "W1"],
            "missing command": [entry for entry in entries if entry is not last],
            "extra command under a real step": [*entries, dict(last, cmd="echo not in the recipe")],
            "duplicated command": [*entries, dict(last)],
        }
        for name, steps in mutants.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(steps, entries)
                self.assertTrue(receipt_errors(dict(receipt, steps=steps), recipe, self.components))


class HostWideRuleTests(unittest.TestCase):
    def test_no_recipe_command_changes_wsl_for_the_other_distributions(self):
        self.assertEqual(host_wide_errors(read(RECIPE)), [])

    def test_the_check_rejects_shutdown_update_wslconfig_default_and_foreign_targets(self):
        recipe = read(RECIPE)
        for added in ("wsl.exe --shutdown", "wsl.exe --update", "notepad.exe $env:USERPROFILE\\.wslconfig",
                      "wsl.exe --set-default <Name>", "wsl.exe --terminate Ubuntu", "wsl.exe --unregister Ubuntu",
                      "wsl.exe --export Ubuntu 'Z:\\WSL\\downloads\\Ubuntu.tar'"):
            with self.subTest(added=added):
                mutant = recipe.replace("```powershell\n", f"```powershell\n{added}\n", 1)
                self.assertTrue(host_wide_errors(mutant))
        self.assertTrue(host_wide_errors(recipe.replace(" --no-launch", "", 1)))

    def test_a_plain_read_of_wslconfig_passes_and_a_write_a_copy_and_an_editor_fail(self):
        """Item F of the 2026-10-01 follow-up: W1 reads the two idle keys; every other command naming the file fails."""
        recipe = read(RECIPE)
        self.assertIn(IDLE_READ + "\n", recipe)
        self.assertEqual(host_wide_errors(recipe), [])
        sh_read = 'grep -n Timeout "$WINDOWS_HOME/.wslconfig"'
        self.assertEqual(host_wide_errors(recipe.replace("```sh\n", f"```sh\n{sh_read}\n", 1)), [])
        profile = "(Join-Path $env:USERPROFILE '.wslconfig')"
        mutants = {
            "write": ("powershell", f"Add-Content -LiteralPath {profile} -Value 'swap=0'"),
            "copy": ("powershell", f"Copy-Item -LiteralPath {profile} -Destination 'Z:\\WSL\\downloads\\wslconfig.copy'"),
            "editor": ("powershell", f"notepad.exe {profile}"),
            "read into a writer": ("powershell", f"Select-String -LiteralPath {profile} -Pattern 'swap' | "
                                                 "Set-Content -LiteralPath 'Z:\\WSL\\downloads\\swap.txt'"),
            "read and a second statement": ("powershell", f"Select-String -LiteralPath {profile} -Pattern 'swap'; "
                                                          f"Clear-Content -LiteralPath {profile}"),
            "sh redirect": ("sh", 'grep -v swap "$WINDOWS_HOME/.wslconfig" > "$WINDOWS_HOME/.wslconfig.new"'),
            "sh copy": ("sh", 'cp "$WINDOWS_HOME/.wslconfig" /tmp/wslconfig.copy'),
            "sh editor": ("sh", "sed -i 's/^swap=.*/swap=0/' \"$WINDOWS_HOME/.wslconfig\""),
        }
        for name, (shell, added) in mutants.items():
            with self.subTest(mutant=name):
                mutant = recipe.replace(f"```{shell}\n", f"```{shell}\n{added}\n", 1)
                self.assertNotEqual(mutant, recipe)
                self.assertTrue(host_wide_errors(mutant))


class ChecklistTests(unittest.TestCase):
    def test_the_checklist_names_exactly_the_recipe_steps(self):
        self.assertEqual(checklist_errors(read(CHECKLIST), read(RECIPE)), [])

    def test_the_check_rejects_a_missing_and_a_duplicated_step(self):
        checklist, recipe = read(CHECKLIST), read(RECIPE)
        first = CHECKLIST_STEP_RE.search(checklist).group(0)
        self.assertTrue(checklist_errors(checklist.replace(first, "- [ ] **gone**", 1), recipe))
        self.assertTrue(checklist_errors(checklist + f"\n{first} again\n", recipe))

    def test_the_check_rejects_a_checklist_without_f11(self):
        checklist, recipe = read(CHECKLIST), read(RECIPE)
        line = next(line for line in checklist.splitlines() if line.startswith("- [ ] **F11**"))
        self.assertTrue(checklist_errors(checklist.replace(line + "\n", ""), recipe))


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


class JCodeMunchStepTests(unittest.TestCase):
    """F11, added 2026-10-01 after the cross-family review of PR #548: the clone's per-project jCodeMunch registration."""

    def inputs(self):
        return read(RECIPE), read(BOOTSTRAP), read(RECORD), read(CHECKLIST), json.loads(read(RECEIPT_EXAMPLE))

    def test_f11_runs_the_bootstrap_registration_after_stage_2_and_records_the_outcome(self):
        self.assertEqual(jcodemunch_errors(*self.inputs()), [])

    def test_the_bootstrap_block_is_read_with_its_continuations_joined(self):
        (registration,) = bootstrap_registration(read(BOOTSTRAP))
        self.assertEqual(registration, 'claude mcp add --scope local jcodemunch -e "CODE_INDEX_PATH=$HOME/.code-index" '
                                       '-e JCODEMUNCH_SHARE_SAVINGS=0 -- '
                                       '"${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}/bin/jcodemunch-mcp"')

    def test_the_check_rejects_drift_a_missing_guard_a_wrong_order_and_a_lost_record(self):
        recipe, bootstrap, record, checklist, receipt = self.inputs()
        f11 = section(recipe, "F11")
        (registration,) = bootstrap_registration(bootstrap)
        binary_test = "test -x " + registration.rsplit(" -- ", 1)[-1] + "\n"
        get = "claude mcp get jcodemunch\n"
        for line in (binary_test, CLONE + "\n", get):
            self.assertEqual(f11.count(line), 1, line)
        unregistered = {key: value for key, value in receipt.items() if key != "jcodemunch_registration"}
        mutants = {
            "user scope": (recipe.replace(f11, f11.replace("--scope local", "--scope user")), bootstrap, record,
                           checklist, receipt),
            "bootstrap drift": (recipe, bootstrap.replace("JCODEMUNCH_SHARE_SAVINGS=0 \\\n", "JCODEMUNCH_SHARE_SAVINGS=1 \\\n",
                                                          1), record, checklist, receipt),
            "no binary test": (recipe.replace(f11, f11.replace(binary_test, "")), bootstrap, record, checklist, receipt),
            "binary test in the registration block": (
                recipe.replace(f11, f11.replace(binary_test, "").replace(CLONE + "\n", CLONE + "\n" + binary_test)),
                bootstrap, record, checklist, receipt),
            "not from the clone": (recipe.replace(f11, f11.replace(CLONE + "\n", "")), bootstrap, record, checklist,
                                   receipt),
            "no proof": (recipe.replace(f11, f11.replace(get, "")), bootstrap, record, checklist, receipt),
            "before stage 2": (recipe.replace(f11, "").replace("### F9. ", f11 + "### F9. ", 1), bootstrap, record,
                               checklist, receipt),
            "no receipt field": (recipe, bootstrap, record, checklist, unregistered),
            "checklist without not installed": (recipe, bootstrap, record, checklist.replace("not installed", "absent"),
                                                receipt),
            "record without the MCP page": (recipe, bootstrap, record.replace(CLAUDE_MCP_PAGE, "https://example.invalid"),
                                            checklist, receipt),
        }
        for name, mutant in mutants.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(mutant, (recipe, bootstrap, record, checklist, receipt))
                self.assertTrue(jcodemunch_errors(*mutant))


class FailedAttemptExportTests(unittest.TestCase):
    """Review finding 3 of PR #569: W6 preserves the failed attempt before `--unregister` deletes its disk."""

    def inputs(self):
        return read(RECIPE), read(RECORD), read(CHECKLIST), json.loads(read(RECEIPT_EXAMPLE))

    def test_w6_exports_the_failed_attempt_before_unregistering(self):
        self.assertEqual(failed_attempt_errors(*self.inputs()), [])

    def test_the_check_rejects_an_unregister_without_a_preceding_export(self):
        recipe, record, checklist, receipt = self.inputs()
        w6 = section(recipe, "W6")
        (export,) = [line for line in w6.splitlines() if EXPORT_RE.fullmatch(line)]
        unregister = UNREGISTER + "\n"
        self.assertEqual(w6.count(unregister), 1)
        unexported = {key: value for key, value in receipt.items() if key != "failed_attempt_export"}
        mutants = {
            "no export": (recipe.replace(w6, w6.replace(export + "\n", "")), record, checklist, receipt),
            "export after unregister": (recipe.replace(w6, w6.replace(export + "\n", "").replace(
                unregister, unregister + export + "\n")), record, checklist, receipt),
            "no guard": (recipe.replace(w6, w6.replace(EXPORT_GUARD + "\n", "")), record, checklist, receipt),
            "no stop before the export": (recipe.replace(w6, w6.replace(TERMINATE + "\n" + export, export)), record,
                                          checklist, receipt),
            "no receipt field": (recipe, record, checklist, unexported),
            "checklist without the export": (recipe, record, checklist.replace("failed_attempt_export", "the receipt"),
                                             receipt),
            "record without the source": (recipe, record.replace(BASIC_COMMANDS, "https://example.invalid"), checklist,
                                          receipt),
        }
        for name, mutant in mutants.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(mutant, (recipe, record, checklist, receipt))
                self.assertTrue(failed_attempt_errors(*mutant))


class SubordinateIdTests(unittest.TestCase):
    """F5 keeps the stage-1 range and says, with its source, when an image needs a wider one."""

    def test_f5_adds_65536_ids_and_cites_when_an_image_needs_more(self):
        self.assertEqual(subordinate_id_errors(read(RECIPE), read(RECORD)), [])

    def test_the_check_rejects_a_wider_range_and_a_lost_citation(self):
        recipe, record = read(RECIPE), read(RECORD)
        f5 = section(recipe, "F5")
        self.assertIn("100000-165535", f5)
        rootless = "https://docs.docker.com/engine/security/rootless/"
        mutants = {
            "wider range": (recipe.replace(f5, f5.replace("100000-165535", "100000-231071")), record),
            "no citation on the page": (recipe.replace(f5, f5.replace(DOCKER_TROUBLESHOOT, rootless)), record),
            "no citation in the record": (recipe, record.replace(DOCKER_TROUBLESHOOT, rootless)),
        }
        for name, (page, sources) in mutants.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(page + sources, recipe + record)
                self.assertTrue(subordinate_id_errors(page, sources))


class FollowUpCase(unittest.TestCase):
    """The 2026-10-01 follow-up's checks read the recipe, the record, the checklist and the receipt example."""

    def inputs(self):
        return read(RECIPE), read(RECORD), read(CHECKLIST), json.loads(read(RECEIPT_EXAMPLE))

    def assert_mutants_fail(self, check, mutants):
        good = self.inputs()
        for name, mutant in mutants.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(mutant, good)
                self.assertTrue(check(*mutant))


def without(receipt: dict, *keys: str) -> dict:
    """A copy of the receipt example without the nested key ``keys``."""
    *parents, last = keys
    if not parents:
        return {key: value for key, value in receipt.items() if key != last}
    return dict(receipt, **{parents[0]: without(receipt.get(parents[0], {}), *parents[1:], last)})


class SignedSumsTests(FollowUpCase):
    """Item B (critic item 5): P1 verifies Canonical's signed SHA256SUMS before stage 1."""

    def test_p1_verifies_the_signed_sums_with_the_installed_keyring(self):
        self.assertEqual(signed_sums_errors(*self.inputs()), [])

    def test_the_check_rejects_a_key_import_a_shared_home_another_keyring_a_late_run_and_lost_records(self):
        recipe, record, checklist, receipt = self.inputs()
        p1, gpgv = section(recipe, "P1"), P1_COMMANDS[3]
        self.assertIn(gpgv + "\n", p1)
        later = "### W5. "
        import_key = "gpg --keyserver hkp://keyserver.ubuntu.com --recv-keys 0xD94AA3F0EFE21092\n"
        self.assert_mutants_fail(signed_sums_errors, {
            "keyserver import": (recipe.replace(p1, p1.replace(gpgv, import_key + gpgv)), record, checklist, receipt),
            "the operator's GnuPG home": (recipe.replace(gpgv, gpgv.replace('--homedir "$SUMS_DIR" ', "")), record,
                                          checklist, receipt),
            "another keyring": (recipe.replace(gpgv, gpgv.replace("archive-keyring", "archive-removed-keys")), record,
                                checklist, receipt),
            "after the install": (recipe.replace(p1, "").replace(later, p1 + later, 1), record, checklist, receipt),
            "no signed line": (recipe.replace(P1_COMMANDS[4] + "\n", ""), record, checklist, receipt),
            "no key in the proof": (recipe.replace(p1, p1.replace(CD_IMAGE_SIGNER, "the key")), record, checklist, receipt),
            "record without the control": (recipe, record.replace("BAD signature", "a bad signature"), checklist, receipt),
            "checklist without the key": (recipe, record, checklist.replace(CD_IMAGE_SIGNER, "the key"), receipt),
            "no receipt field": (recipe, record, checklist, without(receipt, "pre_checks", "signed_sums")),
        })


class UserDataSchemaTests(FollowUpCase):
    """Item C1 (critic item 5): P2 validates the rendered user-data before any boot, and W3's hash matches P2's."""

    def test_p2_validates_the_rendered_user_data_before_any_boot(self):
        self.assertEqual(user_data_schema_errors(*self.inputs()), [])

    def test_the_check_rejects_a_missing_or_misdirected_check_another_renderer_a_lost_hash_and_a_late_run(self):
        recipe, record, checklist, receipt = self.inputs()
        p2, schema = section(recipe, "P2"), P2_COMMANDS[3]
        self.assertIn(schema + "\n", p2)
        self.assertIn(W3_HASH + "\n", section(recipe, "W3"))
        later = "### W5. "
        self.assert_mutants_fail(user_data_schema_errors, {
            "no schema check": (recipe.replace(p2, p2.replace(schema + "\n", "")), record, checklist, receipt),
            "schema of another file": (recipe.replace(p2, p2.replace(schema, "cloud-init schema -c /etc/cloud/cloud.cfg")),
                                       record, checklist, receipt),
            "another renderer": (recipe.replace(p2, p2.replace("string.Template(", "Template(")), record, checklist,
                                 receipt),
            "no Windows hash": (recipe.replace(W3_HASH + "\n", ""), record, checklist, receipt),
            "after the first boot": (recipe.replace(p2, "").replace(later, p2 + later, 1), record, checklist, receipt),
            "record without the version": (recipe, record.replace("cloud-init 26.1-0ubuntu1~24.04.1", "cloud-init"),
                                           checklist, receipt),
            "checklist without the comparison": (recipe, record, checklist.replace(
                checklist_line(checklist, "W3"), "- [ ] **W3** The file exists."), receipt),
            "no receipt field": (recipe, record, checklist, without(receipt, "pre_checks", "user_data_schema")),
        })


class SchemaSystemTests(FollowUpCase):
    """Item C2 (critic item 5): W5 runs `cloud-init schema --system` on path A; W6 skips it on path B."""

    def test_w5_runs_the_schema_check_on_path_a_and_w6_skips_it(self):
        self.assertEqual(schema_system_errors(*self.inputs()), [])

    def test_the_check_rejects_a_missing_check_a_user_run_a_path_b_run_and_a_lost_proof(self):
        recipe, record, checklist, receipt = self.inputs()
        line, w5, w6 = SCHEMA_SYSTEM + "\n", section(recipe, "W5"), section(recipe, "W6")
        self.assertIn(line, w5)
        imported = "wsl.exe -d '<Name>' -u root --exec cloud-init status --wait --long\n"
        self.assertIn(imported, w6)
        self.assert_mutants_fail(schema_system_errors, {
            "no check": (recipe.replace(line, ""), record, checklist, receipt),
            "not as root": (recipe.replace(line, line.replace(" -u root", "")), record, checklist, receipt),
            "run on path B": (recipe.replace(w6, w6.replace(imported, imported + line)), record, checklist, receipt),
            "no line pattern": (recipe.replace(w5, w5.replace(SCHEMA_LINE, "`Valid schema`")), record, checklist, receipt),
            "no skip on path B": (recipe.replace(w6, w6.replace("skip `cloud-init schema --system`", "run it")), record,
                                  checklist, receipt),
            "record without the how-to": (recipe, record.replace(CLOUD_INIT_HOWTO, "https://example.invalid/"), checklist,
                                          receipt),
            "checklist without the check": (recipe, record, checklist.replace("Valid schema user-data", "a schema"),
                                            receipt),
            "no receipt field": (recipe, record, checklist, without(receipt, "first_launch", "schema_system")),
        })


class KernelStorageTests(FollowUpCase):
    """Item D (critic item 3): P3 counts the current boot's storage errors before stage 1 and stops on any."""

    def test_p3_counts_storage_errors_before_stage_1(self):
        self.assertEqual(kernel_storage_errors(*self.inputs()), [])

    def test_the_check_rejects_dmesg_no_sudo_a_counted_registration_line_a_device_id_and_lost_records(self):
        recipe, record, checklist, receipt = self.inputs()
        p3, count = section(recipe, "P3"), STORVSC_COUNT + "\n"
        self.assertIn(count, p3)
        later = "### W5. "
        page = lambda new: (recipe.replace(p3, p3.replace(count, new)), record, checklist, receipt)  # noqa: E731
        self.assert_mutants_fail(kernel_storage_errors, {
            "dmesg": page(count.replace("sudo journalctl -k -b 0 --no-pager", "dmesg")),
            "no sudo": page(count.replace("sudo ", "", 1)),
            "registration line counted": page("sudo journalctl -k -b 0 --no-pager | grep -c hv_storvsc\n"),
            "a device id": page(count.replace("grep hv_storvsc", "grep 00000000-0000-0000-0000-000000000000")),
            "no swap state": (recipe.replace(p3, p3.replace("swapon --show\n", "")), record, checklist, receipt),
            "no issue": (recipe.replace(p3, p3.replace(STORVSC_ISSUE, "https://example.invalid/")), record, checklist,
                         receipt),
            "no stop": (recipe.replace(p3, p3.replace("A nonzero count stops the run", "A count is recorded")), record,
                        checklist, receipt),
            "after the install": (recipe.replace(p3, "").replace(later, p3 + later, 1), record, checklist, receipt),
            "record without the run": (recipe, record.replace(STORVSC_COUNT, "the count"), checklist, receipt),
            "checklist without the issue": (recipe, record, checklist.replace("41482", "the issue"), receipt),
            "no receipt field": (recipe, record, checklist, without(receipt, "pre_checks", "kernel_storage_errors")),
        })


class TerminateOnceTests(FollowUpCase):
    """Item E1 (critic item 2): W7 terminates `<Name>` once after the first launch and relaunches it."""

    def test_w7_terminates_once_after_the_first_launch_and_relaunches(self):
        self.assertEqual(terminate_once_errors(*self.inputs()[:3]), [])

    def test_the_check_rejects_no_terminate_no_relaunch_a_wrong_place_and_a_lost_citation(self):
        recipe, record, checklist, receipt = self.inputs()
        w7 = section(recipe, "W7")
        for line in (TERMINATE, RELAUNCH):
            self.assertIn(line + "\n", w7)
        mutants = {
            "no terminate": (recipe.replace(w7, w7.replace(TERMINATE + "\n", "")), record, checklist),
            "no relaunch": (recipe.replace(w7, w7.replace(RELAUNCH + "\n", "")), record, checklist),
            "before the first launch": (recipe.replace(w7, "").replace("### W5. ", w7 + "### W5. ", 1), record, checklist),
            "no quote": (recipe.replace(w7, w7.replace(OWNER_FIX_QUOTE, "it recovers")), record, checklist),
            "record without the fix": (recipe, record.replace(OWNER_FIX, "https://example.invalid/"), checklist),
            "checklist without the terminate": (recipe, record, checklist.replace(checklist_line(checklist, "W7"),
                                                                                  "- [ ] **W7** The probe passed.")),
        }
        for name, mutant in mutants.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(mutant, (recipe, record, checklist))
                self.assertTrue(terminate_once_errors(*mutant))


class OwnershipProbeTests(FollowUpCase):
    """Item E2 (critic item 2): after the terminate, a file created from Windows is owned by 1000:1000."""

    def test_w7_probes_the_owner_of_a_file_created_from_windows(self):
        self.assertEqual(ownership_probe_errors(*self.inputs()), [])

    def test_the_check_rejects_a_probe_before_the_terminate_another_file_no_cleanup_and_lost_records(self):
        recipe, record, checklist, receipt = self.inputs()
        w7 = section(recipe, "W7")
        for line in (PROBE_CREATE, PROBE_OWNER, PROBE_DELETE):
            self.assertIn(line + "\n", w7)
        question = next(line for line in chapter(record, "Open questions").splitlines() if "40941" in line)
        early = w7.replace(PROBE_CREATE + "\n", "").replace(TERMINATE + "\n", PROBE_CREATE + "\n" + TERMINATE + "\n")
        self.assert_mutants_fail(ownership_probe_errors, {
            "probe before the terminate": (recipe.replace(w7, early), record, checklist, receipt),
            "another file": (recipe.replace(PROBE_OWNER, PROBE_OWNER.replace("wsl-owner-probe", "other")), record,
                             checklist, receipt),
            "no cleanup": (recipe.replace(w7, w7.replace(PROBE_DELETE + "\n", "")), record, checklist, receipt),
            "no owner proof": (recipe.replace(w7, w7.replace("`1000:1000`", "the owner")), record, checklist, receipt),
            "no open question": (recipe, record.replace(question, ""), checklist, receipt),
            "checklist without the owner": (recipe, record, checklist.replace("1000:1000", "the owner"), receipt),
            "no receipt field": (recipe, record, checklist, without(receipt, "ownership_probe")),
        })


class IdleObservationTests(FollowUpCase):
    """Item F (critic item 4): W1 reads the idle keys, F2 observes `<Name>` with no client attached, and open question 2
    carries the facts."""

    def test_w1_reads_the_idle_keys_and_f2_observes_the_idle_distribution(self):
        self.assertEqual(idle_errors(*self.inputs()), [])

    def test_the_check_rejects_no_key_read_a_short_poll_a_lost_caveat_the_old_question_and_lost_fields(self):
        recipe, record, checklist, receipt = self.inputs()
        for line in (IDLE_READ, IDLE_POLL):
            self.assertIn(line + "\n", recipe)
        w1, f2 = section(recipe, "W1"), section(recipe, "F2")
        match = re.search(r"^2\. .*?(?=^\d+\. |\Z)", chapter(record, "Open questions"), re.M | re.S)
        self.assertIsNotNone(match)
        old = "2. **Linger and the idle timeout.** Whether a lingering user manager keeps the distribution running.\n"
        self.assert_mutants_fail(idle_errors, {
            "no key read": (recipe.replace(IDLE_READ + "\n", ""), record, checklist, receipt),
            "a short poll": (recipe.replace(IDLE_POLL, IDLE_POLL.replace("1..12", "1..2")), record, checklist, receipt),
            "no default": (recipe.replace(w1, w1.replace("15000", "the default")), record, checklist, receipt),
            "no caveat": (recipe.replace(f2, f2.replace("is not verified", "is settled")), record, checklist, receipt),
            "the old question": (recipe, record.replace(match.group(0), old), checklist, receipt),
            "checklist without the observation": (recipe, record, checklist.replace("two minutes", "a while"), receipt),
            "no idle keys in the receipt": (recipe, record, checklist, without(receipt, "host", "idle_keys")),
            "no observation in the receipt": (recipe, record, checklist, without(receipt, "idle_observation")),
        })


class RehearsalTests(unittest.TestCase):
    """Item G (critic item 1): R1 rehearses on a throwaway name first and removes only that name."""

    def inputs(self):
        return (read(RECIPE), read(RECORD), read(CHECKLIST), json.loads(read(RECEIPT_EXAMPLE)),
                json.loads(read(EXPERIMENT)))

    def test_r1_rehearses_on_a_throwaway_name_first_and_removes_only_it(self):
        self.assertEqual(rehearsal_errors(*self.inputs()), [])

    def test_the_check_rejects_a_late_rehearsal_an_unexported_failure_a_wrong_order_and_lost_records(self):
        recipe, record, checklist, receipt, experiment = self.inputs()
        r1, rehearsal = section(recipe, "R1"), chapter(recipe, "Rehearsal first")
        self.assertIn(REHEARSAL_EXPORT + "\n", r1)
        first_boot = "## First boot inside the new distribution\n"
        removal = TERMINATE + "\n" + UNREGISTER + "\n"
        self.assertIn(removal, r1)
        decision = chapter(record, "Decision")
        mutants = {
            "after stage 1": (recipe.replace(rehearsal, "").replace(first_boot, rehearsal + first_boot, 1), record,
                              checklist, receipt, experiment),
            "failure not exported": (recipe.replace(r1, r1.replace(REHEARSAL_EXPORT + "\n", "")), record, checklist,
                                     receipt, experiment),
            "no guard": (recipe.replace(r1, r1.replace(EXPORT_GUARD + "\n", "")), record, checklist, receipt, experiment),
            "unregister before terminate": (recipe.replace(r1, r1.replace(removal, UNREGISTER + "\n" + TERMINATE + "\n", 1)),
                                            record, checklist, receipt, experiment),
            "no host-wide rule": (recipe.replace(r1, r1.replace("only its own distribution", "its distribution")), record,
                                  checklist, receipt, experiment),
            "checklist without R1": (recipe, record, checklist.replace(checklist_line(checklist, "R1") + "\n", ""), receipt,
                                     experiment),
            "no receipt block": (recipe, record, checklist, without(receipt, "rehearsal"), experiment),
            "experiment without the rehearsal": (recipe, record, checklist, receipt,
                                                 dict(experiment, next_decision_changing_test="Run stage 1.")),
            "record without R1": (recipe, record.replace(decision, decision.replace("R1", "the rehearsal step")), checklist,
                                  receipt, experiment),
        }
        for name, mutant in mutants.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(mutant, (recipe, record, checklist, receipt, experiment))
                self.assertTrue(rehearsal_errors(*mutant))


if __name__ == "__main__":
    unittest.main()
