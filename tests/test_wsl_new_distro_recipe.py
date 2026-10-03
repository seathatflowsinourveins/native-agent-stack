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
- the two release-to-sha256 pairs match the primary sources in the recipe, record and synthetic receipt example, and the
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
  - D: P3 records the current boot's ``hv_storvsc`` kernel journal count, without the driver's registration line, as
    a baseline and stops only when the newest error line is less than one hour old by its kernel time; W5 counts again
    after the first launch on both paths; attachment-only increases before cloud-init starts are recorded, and later
    storage errors or a provisioning failure with a storage cause stop the run (the 2026-10-02 rehearsal correction);
  - E1 and E2: W7 terminates ``<Name>`` once after the first launch, relaunches it and reads the owner of a file created
    from Windows (microsoft/WSL#40941, PR #40977);
  - F: W1 reads the two idle keys of the global WSL configuration, F2 observes ``<Name>`` for two minutes with no client
    attached, and the host-wide check passes a plain ``Select-String`` or ``grep`` read of ``.wslconfig`` and nothing
    else that names it;
  - G: R1, the page's first step, rehearses on a throwaway name with both storage readings and removes only that
    name, exporting it first when the rehearsal failed;
- the follow-up of 2026-10-02 to the first observations of the updated host (WSL 3.0.1.0), each rule bound to the recipe,
  the record, the checklist and the receipt example, and each with in-memory controls that restore the pre-change text:
  - Host-wide rules adopt stable WSL 3.0.1 or later for a second systemd distribution, as policy, and say the host was
    updated and passed its check with the two-distribution proof still owed;
  - W1 records the workstation's baseline of five values without sudo (``/proc/self`` where W1 read ``/proc/1``), and W5
    reads the same five values from both running distributions, after its cgroup block and before F1, under the receipt's
    ``paired_isolation`` (one object per distribution); W6 repeats that record;
  - F1 accepts ``degraded`` only when ``systemctl --failed --no-legend --plain`` lists exactly ``systemd-binfmt.service``
    and its log holds the read-only flush message (microsoft/WSL#40621 and #41226); any other failed unit stops the run;
  - no recipe command controls ``systemd-binfmt``: the restart that served WSL 2.7.x exits 1 on the adopted release, so a
    failed interop check after an unregister stops for review with two records after the check (a history sentence may
    still name the restart).
- the stage-2 follow-up of 2026-10-02 (the client-configuration work, tools/adoption/new_wsl_client_config.py), bound to
  the recipe, the record's command table, the checklist and the receipt example:
  - F9 is one ``sh`` block, the install plan's ``install.sh`` and ``accept.sh``, then the tool's ``--check`` and
    ``--apply``, and runs no profile of the bootstrap; the two native sign-ins are named after that block and the plan's
    ``accept.sh --only <slot> --stage after_sign_in`` after them, for exactly the owners whose plan row has that stage;
    the record's table and the receipt example carry the same five rows, and both comparisons read F9 like any other step;
  - the host template's collector port is the install plan's OTLP/HTTP port (``config/otel.yaml``), its other ports are
    neither the plan's nor the workstation's, and F8's exclusion set names the workstation's collector and Qdrant ports
    (24318 and 26333, observed listening 2026-10-02);

- the repair of 2026-10-02 after the cross-family review of the client-configuration pull request, bound to the recipe, the
  checklist and the receipt example:
  - the command block of F9 keeps the plain ``--apply``; the authorization settings (the ones that grant a permission or
    suppress a confirmation) are written only with ``--with-authorization-settings``, which F9 names in prose, for a host
    whose owner asked for the repository's permission practice, and the receipt's ``authorization_settings`` records who
    asked;
  - F9 says that a unit of the instruction blocks is left out when it names a tool that is not wired (a name the map lists
    for an unwired piece, or the former default of a manifest row that installs nothing), that a unit is not left out merely
    for naming a skill or timer that neither lists, and that this step does not establish those skills;
  - F9 says what the line ``--apply`` prints about the authorization settings says: every outcome, in the words the tool
    prints;

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
SOURCE_RECEIPT = ROOT / "evidence/artifacts/new-wsl-dual-image-20261001/receipt.json"
HOST_EXAMPLE = ROOT / "adoption/hosts/example.json"
STACK = ROOT / "manifests/stack.json"
BOOTSTRAP = ROOT / "adoption/bootstrap.md"

IMAGE = "ubuntu-<RELEASE>-wsl-amd64.wsl"
IMAGE_BYTES = 388975696
RELEASE_PINS = {
    "26.04.1": {
        "file": "ubuntu-26.04.1-wsl-amd64.wsl",
        "url": "https://releases.ubuntu.com/26.04.1/ubuntu-26.04.1-wsl-amd64.wsl",
        "sha256": "48d56724b5c8e60f24893e83e73bbb58c60b3ca22fba3da977075420acd54104",
        "catalog_name": "Ubuntu-26.04",
        "bytes": 418495746,
    },
    "24.04.5": {
        "file": "ubuntu-24.04.5-wsl-amd64.wsl",
        "url": "https://releases.ubuntu.com/24.04.5/ubuntu-24.04.5-wsl-amd64.wsl",
        "sha256": "bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e",
        "catalog_name": "Ubuntu-24.04",
        "bytes": IMAGE_BYTES,
    },
}
PLACEHOLDER = "${WSL_USER}"
# The review contract is independent of the recipe, checklist and receipt. Losing a stage from all three must fail.
REQUIRED_STAGE_IDS = (
    "R1", "P1", "P2", "P3", "W1", "W2", "W3", "W4", "W5", "W6", "W7",
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11",
)
SELECTED_IMAGE_DIGEST_FIELDS = ("sha256_published", "sha256_computed", "sha256_distributioninfo")
INTEROP_VERIFY = ("wsl.exe -d '<Survivor>' --exec sh -c "
                  "'test -e /proc/sys/fs/binfmt_misc/WSLInterop && /mnt/c/Windows/System32/cmd.exe /d /c ver'")
INTEROP_GUARD = ("if ($LASTEXITCODE -ne 0) { throw "
                 "'interop failed: recover in the surviving distribution before continuing' }")
# The follow-up of 2026-10-02 (the updated host, WSL 3.0.1). W1 records the workstation's baseline of five values and W5
# reads the same five from both running distributions. The namespace read is `/proc/self`, which needs no sudo, where the
# earlier W1 read `/proc/1`.
OLD_NAMESPACE_READ = "readlink /proc/1/ns/cgroup"
NAMESPACE_READ = "readlink /proc/self/ns/cgroup"
WORKSTATION_COMMANDS = ["id -u", "systemctl is-system-running", "systemctl --failed --no-legend --plain",
                        'systemctl is-active "user@$(id -u).service"', NAMESPACE_READ]
NEW_COMMANDS = ["/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec " + command for command in
                (*WORKSTATION_COMMANDS[:3], "sh -c '" + WORKSTATION_COMMANDS[3] + "'", NAMESPACE_READ)]
WORKSTATION_BASELINE = "\n".join(WORKSTATION_COMMANDS)
PAIRED_NEW = "\n".join(NEW_COMMANDS)
ISOLATION_KEYS = {"uid", "system_state", "failed_units", "user_manager", "cgroup_namespace"}
CGROUP_PROCS = "cat '/sys/fs/cgroup/system.slice/<COMMON_UNIT>/cgroup.procs'"
USER_MANAGER_ACTIVE = ('/mnt/c/Windows/System32/wsl.exe -d \'<Name>\' --exec sh -c '
                       '\'systemctl is-active "user@$(id -u).service"\'')
STORAGE_RULE = ("On both paths, record P3's baseline before the import and `second_count` after the first launch. "
                "An increase confined to the window in which the new disk is attached, before cloud-init starts, "
                "is recorded with the new lines and does not stop the run. Any storage error after that window, "
                "or any provisioning step that fails with a storage cause, stops the run.")
OLD_STORAGE_RULE = ("On both paths, the second storage count equals P3's baseline; a larger count is recorded "
                    "with the new lines, a failed W5 counts as exposure to microsoft/WSL#41482, and nothing "
                    "continues to stage 2 until that is decided.")
# The follow-up of 2026-10-02, change 1: the adopted target, as policy, and the two sentences it replaced.
ADOPTED_TARGET = ("This recipe adopts stable WSL 3.0.1 or later for a second systemd distribution, and requires it "
                  "before W4 or any W6 import.")
HOST_UPDATE = ("The host was updated to WSL 3.0.1.0 on 2026-10-02 and passed its check (rootless container, interop, "
               "user manager); run 2 observed distinct cgroup namespaces, local process ids and two active user "
               "managers while both distributions ran.")
OLD_ADOPTED_TARGET = "A second systemd distribution requires WSL 3.0.1 or later before W4 or any W6 import."
OLD_HOST_UPDATE = "The host's 2.7.13 must be updated outside this page before this second-distribution run."
# Change 3: on the adopted release WSL mounts the binfmt status file read-only (microsoft/WSL#40621) while the
# distribution's protectBinfmt setting is on (its default; a best-effort step), and systemd-binfmt.service then fails,
# which upstream calls benign (#41226). F1 accepts that one failed unit.
BINFMT_UNIT = "systemd-binfmt.service"
F1_FAILED = "systemctl --failed --no-legend --plain"
F1_LOG = "journalctl -b 0 -t systemd-binfmt --no-pager -n 4"
F1_PASS = ("`degraded` when `systemctl --failed --no-legend --plain` lists exactly `systemd-binfmt.service` and that "
           "unit's log, from the `journalctl` line, holds")
FLUSH_MESSAGE = "Failed to flush binfmt_misc rules, ignoring: Read-only file system"
# F1 reads that log as `<WSL_USER>` without sudo (the user is in `adm`); on `degraded` with only the journal's permission
# notice, the line is repeated once with sudo, which the recipe's other journal commands also use.
F1_SUDO_FALLBACK = ("On `degraded`, if the `journalctl` line prints only `Hint: You are currently not seeing messages from "
                    "other users and the system.` or `-- No entries --`, the user cannot read the journal: repeat that line "
                    "once with `sudo`, record both outputs and judge the second.")
BINFMT_PR = "https://github.com/microsoft/WSL/pull/40621"
BINFMT_ISSUE = "https://github.com/microsoft/WSL/issues/41226"
BINFMT_BENIGN = "The systemd error is benign and won't affect registration of user defined binfmt settings."
OLD_F1 = ("```sh\nsystemctl is-system-running --wait\nsystemctl --failed --no-legend\n"
          "systemctl list-unit-files --type=service --no-pager\n```\n\n"
          "Proof: `running`, no failed unit, and the service list prints. Ubuntu's own setup tests require `running` for "
          "a new\ninstance. On `degraded`, record `systemctl --failed` and stop for review.\n\n")
# The interop recovery: the restart was the WSL 2.7.x remedy; on the adopted release it exits 1, so a failed check stops
# for review with two records. The native check stays in front of them.
NATIVE_INTEROP = "test -e /proc/sys/fs/binfmt_misc/WSLInterop && /mnt/c/Windows/System32/cmd.exe /d /c ver"
INTEROP_RECORDS = ("ls /proc/sys/fs/binfmt_misc", "systemctl status systemd-binfmt.service --no-pager")
RESTART_UNIT = "sudo systemctl restart systemd-binfmt || exit 1"
OLD_INTEROP_RECOVERY = RESTART_UNIT + "\n" + NATIVE_INTEROP + "\n" + 'if [ "$?" -ne 0 ]; then exit 1; fi' + "\n"
UNIT_CONTROL_RE = re.compile(r"\bsystemctl\b.*\b(?:restart|try-restart|reload-or-restart|start|stop)\b.*systemd-binfmt")
USER_SESSION_WARNING = "wsl: Failed to start the systemd user session"
# Loopback ports the workstation distribution already uses: the four in adoption/hosts/example.json, the gateway,
# memory and the 2026-09-25 relocations named in adoption/platforms/linux-wsl2.md ("Listeners and ports"), and every
# 127.0.0.1 port in observability/backends/templates and configure.py. The recipe lists the same set (F8). 24318 and
# 26333 are the workstation's own collector and Qdrant after their 2026-09-25 relocation, observed listening on
# 2026-10-02 in the first real run of F8.
WORKSTATION_PORTS = frozenset({3710, 3800, 8231, 13000, 13100, 14318, 14333, 16333, 18080, 18231, 18525, 18888,
                               18889, 19090, 19093, 20128, 20129, 24318, 26333, 31415, 49374, 49474})
URL_KEYS = ("OTEL_ENDPOINT", "AI_MEMORY_URL", "QDRANT_URL", "EMBED_URL")
SHELLS = ("powershell", "sh")
# F11: the code block right after this lead in adoption/bootstrap.md (step 4a) is the per-project registration.
JCODEMUNCH_LEAD = "**jCodeMunch, per project.**"
JCODEMUNCH_OUTCOMES = ("registered", "not installed", "skipped")
CLONE = "cd ~/code/native-agent-stack"
# F9 (2026-10-02, tools/adoption/new_wsl_client_config.py): stage 2 is the install plan, the client-configuration tool's
# check and apply, the native sign-ins by hand and the plan's after-sign-in checks, not the bootstrap's profile. The
# record's command table and the receipt example carry the same five rows, and f9_errors pins the block and its prose.
F9_PLAN = "evidence/artifacts/new-wsl-install-plan-20261002"
PLAN_DIR = ROOT / F9_PLAN
F9_COMMANDS = [
    CLONE,
    f"bash {F9_PLAN}/install.sh",
    f"bash {F9_PLAN}/accept.sh",
    "python3 -B tools/adoption/new_wsl_client_config.py --check",
    "python3 -B tools/adoption/new_wsl_client_config.py --apply --host '<host>'",
]
F9_SIGN_IN = "After the `--apply` line, run `codex login`, then `claude`, by hand"
F9_AFTER_SIGN_IN = "accept.sh --only <slot> --stage after_sign_in"
# The repair of 2026-10-02: the plain --apply writes no authorization setting, the option is prose, and F9's sentence about
# the instruction blocks says what the filter does (it goes by the names the map lists for unwired pieces and the former
# defaults of the manifest rows that install nothing) and what it does not establish. The same words stand in the decision
# records, and tests/test_new_wsl_client_config.py holds them against the tool's own dropped list and printed line.
AUTHORIZATION_OPTION = "--with-authorization-settings"
F9_AUTHORIZATION_PHRASES = (
    "writes none of the authorization settings",
    "`--with-authorization-settings` to that line only on a host whose owner asked for the repository's permission practice",
    "the receipt's `authorization_settings` records who asked",
    "F9's `authorization_settings`",
)
F9_BLOCKS_SENTENCE = ("a unit is left out when it names a tool that is not wired, which is a name the map lists for an "
                      "unwired piece or the former default of a manifest row that installs nothing; a unit is not left out "
                      "merely for naming a skill or timer that neither lists, and whether those skills exist on the host is "
                      "not established by this step")
F9_OLD_BLOCKS_CLAIM = "every unit that names a tool the manifest does not install left out"
# The fourth round's wording, which the dropped list contradicts: the Promptfoo unit names no tool of any map entry (it is the
# former default of the manifest row `promptfoo`) and names `skill-creator`, and it is left out of both blocks.
F9_PREVIOUS_BLOCKS_CLAIM = "every unit that names a tool the map declares as not wired left out"
# What F9 says of the line that --apply prints about the authorization settings: every outcome, as the tool prints it.
AUTHORIZATION_LINE_SENTENCE = ("a line before the summary that starts `authorization settings:` and says `left to the "
                               "clients' own defaults` when the option was not given and, when it was, `applied`, `partly "
                               "applied`, `kept` or `not applied` (`would be applied` or `would be partly applied` in a dry "
                               "run), followed by what it added, kept, found already the same and did not reach, a skipped "
                               "step and a failed step told apart")
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
SUMS_URL = "https://releases.ubuntu.com/$RELEASE/SHA256SUMS"
CD_IMAGE_SIGNER = "843938DF228D22F7B3742BC0D94AA3F0EFE21092"
P1_COMMANDS = [
    'SUMS_DIR="$(mktemp -d)"',
    f'curl -fsSL -o "$SUMS_DIR/SHA256SUMS" "{SUMS_URL}" || exit 1',
    f'curl -fsSL -o "$SUMS_DIR/SHA256SUMS.gpg" "{SUMS_URL}.gpg" || exit 1',
    'gpgv --homedir "$SUMS_DIR" --keyring /usr/share/keyrings/ubuntu-archive-keyring.gpg "$SUMS_DIR/SHA256SUMS.gpg" '
    '"$SUMS_DIR/SHA256SUMS"',
    'grep -F " *ubuntu-$RELEASE-wsl-amd64.wsl" "$SUMS_DIR/SHA256SUMS" || exit 1',
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
STORVSC_COUNT = ("sudo journalctl -k -b 0 --no-pager | grep hv_storvsc | "
                 "grep -Evc 'registering driver hv_storvsc|[Cc]ommand line:'")
# The coordinator's P3 rule (2026-10-01): the count is a baseline; the newest error line's kernel time against the
# uptime decides whether errors are current; W5 counts again after the first launch.
STORVSC_NEWEST = ("sudo journalctl -k -b 0 --no-pager -o short-monotonic --no-hostname | grep hv_storvsc | "
                  "grep -Ev 'registering driver hv_storvsc|[Cc]ommand line:' | tail -n 1")
# Earlier evidence sections retain the commands actually run in the 2026-10-01 artifact check (B6).
HISTORICAL_STORAGE_COMMANDS = tuple(command.replace("grep -Ev", "grep -v").replace("|[Cc]ommand line:", "")
                                    for command in (STORVSC_COUNT, STORVSC_NEWEST))
UPTIME = "cat /proc/uptime"
P3_COMMANDS = [STORVSC_COUNT, STORVSC_NEWEST, UPTIME, "swapon --show"]
STORAGE_FIELDS = {"baseline": "<P3", "newest_line_time": "<P3", "swap": "<P3", "second_count": "<W5", "new_lines": "<W5"}
THRESHOLD_SOURCE = "this recipe's choice, not an upstream figure"
STORVSC_ISSUE = "https://github.com/microsoft/WSL/issues/41482"
OWNER_ISSUE = "https://github.com/microsoft/WSL/issues/40941"
OWNER_FIX = "https://github.com/microsoft/WSL/pull/40977"
OWNER_FIX_QUOTE = "this only recovers after a distro termination"
RELAUNCH = "wsl.exe -d '<Name>' --exec id -un"
PROBE_SHARE = r"\\wsl.localhost\<Name>\home\<WSL_USER>\wsl-owner-probe"
PROBE_CREATE = f"New-Item -ItemType File -Path '{PROBE_SHARE}'"
PROBE_OWNER = "wsl.exe -d '<Name>' --exec stat -c %u:%g '/home/<WSL_USER>/wsl-owner-probe'"
PROBE_DELETE = f"Remove-Item -LiteralPath '{PROBE_SHARE}'"
GETTY_UNIT = "getty@tty1.service"
GETTY_MASK = "systemctl mask --now " + GETTY_UNIT
GETTY_BOOTCMD = "bootcmd:\n- [systemctl, mask, --now, getty@tty1.service]\n"
GETTY_ENABLED = "wsl.exe -d '<Name>' --exec systemctl is-enabled " + GETTY_UNIT
GETTY_SHOW = "wsl.exe -d '<Name>' --exec systemctl show " + GETTY_UNIT + " -p LoadState -p ActiveState -p NRestarts"
GETTY_RESULT = "systemctl show " + GETTY_UNIT + " -p Result -p NRestarts"
F10_PROBE = ("wsl.exe -d '<Name>' -u '<WSL_USER>' --exec /bin/bash -lc "
             "'for n in claude codex; do p=$(type -P $n); [[ -f $p && -x $p ]] && echo executable: $p; done'")
R1_BUS_PROBE = "wsl.exe -d '<Name>' --exec bash -lc 'stat -c %U,%F /run/user/$(id -u) /run/user/$(id -u)/bus'"
F5_GUARDED = ('grep -q "^$(id -un):" /etc/subuid || sudo usermod --add-subuids 100000-165535 '
              '--add-subgids 100000-165535 "$(id -un)"')
IDLE_READ = ("Select-String -LiteralPath (Join-Path $env:USERPROFILE '.wslconfig') -Pattern '^\\s*\\[', "
             "'^\\s*instanceIdleTimeout\\s*=', '^\\s*vmIdleTimeout\\s*=' -ErrorAction SilentlyContinue")
IDLE_POLL = ("foreach ($Poll in 1..12) { Start-Sleep -Seconds 10; [DateTime]::UtcNow.ToString('HH:mm:ss'); "
             "wsl.exe --list --running --quiet }")
REHEARSAL_TAR = r"Z:\WSL\downloads\<Name>-rehearsal.tar"
REHEARSAL_EXPORT = f"wsl.exe --export '<Name>' '{REHEARSAL_TAR}'"
REHEARSAL_FIELDS = {"name", "result", "creation_path", "schema_system", "ownership_probe", "idle_observation",
                    "storage_readings", "export"}

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
    commands = Counter(recipe_rows(recipe))
    table = Counter(command_table(record))
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
    if template.count(GETTY_BOOTCMD) != 1:
        errors.append("the user-data must hold the exact bootcmd getty mask once")
    if not re.search(r"^    default=\$\{WSL_USER\}\n\n(?:#[^\n]*\n){1,4}" + re.escape(GETTY_BOOTCMD), template, re.M):
        errors.append("the bootcmd must follow write_files with one blank line and at most four comment lines")
    if re.search(r"^\s*(passwd|hashed_passwd|plain_text_passwd):", rendered, re.M):
        errors.append("the user-data sets a password; the recipe's user has a locked password and NOPASSWD sudo")
    return errors


def plan_rows() -> list[dict]:
    """The install plan's owner rows (evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json)."""
    return json.loads(read(PLAN_DIR / "install-plan.json"))["owners"]


def plan_after_sign_in_slots() -> list[str]:
    """The slots of the installed rows whose acceptance has an ``after_sign_in`` stage, in the plan's order."""
    return [row["slot"] for row in plan_rows() if row.get("installed") and "after_sign_in" in (row.get("acceptance") or {})]


def plan_collector_ports() -> tuple[int, int]:
    """(OTLP/gRPC port, OTLP/HTTP port) of the install plan's collector, read from the plan's config/otel.yaml and not
    from the tool that renders from it."""
    match = re.search(r"protocols:\s*\n\s*grpc:\s*\n\s*endpoint:\s*127\.0\.0\.1:(\d+)\s*\n\s*http:\s*\n"
                      r"\s*endpoint:\s*127\.0\.0\.1:(\d+)", read(PLAN_DIR / "config/otel.yaml"))
    if match is None:
        raise AssertionError("the install plan's config/otel.yaml has no OTLP grpc and http endpoints")
    return int(match.group(1)), int(match.group(2))


def plan_loopback_ports() -> set[int]:
    """Every loopback port the install plan's services (their ``service.port``) and configuration files use."""
    ports = {int(row["service"]["port"]) for row in plan_rows()
             if isinstance(row.get("service"), dict) and row["service"].get("port") is not None}
    for config in sorted((PLAN_DIR / "config").iterdir()):
        ports.update(int(port) for port in re.findall(r"127\.0\.0\.1:(\d+)", read(config)))
    return ports | set(plan_collector_ports())


def host_template_errors(template: str, example: dict, recipe: str, user: str = "example") -> list[str]:
    errors = []
    collector, plan_used = plan_collector_ports()[1], plan_loopback_ports()
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
        if key == "OTEL_ENDPOINT" and port != collector:
            errors.append(f"OTEL_ENDPOINT uses {port}; the install plan's collector listens on {collector} (OTLP/HTTP), "
                          "the port the client-configuration tool renders into both clients")
        elif key != "OTEL_ENDPOINT" and port in plan_used:
            errors.append(f"{key} uses {port}, a port the install plan's services use")
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
    """Require the exact primary-source release pairs, not merely membership in a set of two hashes."""
    errors = []
    expected_values = {pin["sha256"] for pin in RELEASE_PINS.values()}
    for name, text in (("recipe", recipe), ("checklist", checklist)):
        if set(SHA256_RE.findall(text)) != expected_values:
            errors.append(f"the {name} does not name exactly the two primary-source image hashes")
    for release, pin in RELEASE_PINS.items():
        for name, text in (("recipe", recipe), ("record", record), ("checklist", checklist)):
            values = {value for line in text.splitlines() if pin["file"] in line for value in SHA256_RE.findall(line)}
            if values != {pin["sha256"]}:
                errors.append(f"the {name}'s {release} file-to-sha256 pairing differs from its primary-source pin")
    arms = re.findall(r"^\s*'([^']+)' \{ \$Expected = '([0-9a-f]{64})'; \$CatalogName = '([^']+)' \}$",
                      section(recipe, "W2"), re.M)
    expected_arms = {(release, pin["sha256"], pin["catalog_name"]) for release, pin in RELEASE_PINS.items()}
    if len(arms) != 2 or set(arms) != expected_arms:
        errors.append("W2 does not control the two release-to-hash-to-catalog mappings")
    w2 = section(recipe, "W2")
    for needed in ("default { throw 'unsupported release: do not download or install' }",
                   "$Actual -ne $Expected", "$Published -ne $Expected", "$Listed.Amd64Url.Sha256 -ne $Expected",
                   "$Listed.Amd64Url.Url -ne $ImageUrl", "throw 'sha256 mismatch: do not install'",
                   "(Get-FileHash -Algorithm SHA256 -LiteralPath $ImagePath).Hash.ToLowerInvariant()"):
        if needed not in w2:
            errors.append(f"W2 lacks its selected-image verification: {needed}")
    if receipt.get("supported_images") != RELEASE_PINS:
        errors.append("the synthetic receipt's controlled release pins or observed sizes differ from the primary sources")
    image = receipt.get("image", {}) if isinstance(receipt, dict) else {}
    if image.get("release") != "<RELEASE>" or image.get("file") != IMAGE or image.get("url") != (
            "https://releases.ubuntu.com/<RELEASE>/" + IMAGE):
        errors.append("the synthetic receipt does not name the selected release's file and URL")
    for key in ("bytes", *SELECTED_IMAGE_DIGEST_FIELDS):
        if not is_placeholder(image.get(key), "<W2"):
            errors.append(f"the synthetic receipt's selected-image {key} must be filled from the actual W2 run")
    return errors + selected_image_digest_errors(recipe, receipt)


def selected_image_digest_errors(recipe: str, receipt: dict) -> list[str]:
    """Check every selected-image digest, including additional digest fields, against the recipe's release pair."""
    image = receipt.get("image", {})
    errors = [f"image lacks {key}" for key in SELECTED_IMAGE_DIGEST_FIELDS if key not in image]
    release = image.get("release")
    synthetic = receipt.get("artifact_class") == "synthetic_fixture" and release == "<RELEASE>"
    if not synthetic and release not in RELEASE_PINS:
        return errors + ["image has no supported selected release"]
    selected = RELEASE_PINS if synthetic else {release: RELEASE_PINS[release]}
    recipe_hashes = {}
    for name, pin in selected.items():
        hashes = {value for line in recipe.splitlines() if pin["file"] in line for value in SHA256_RE.findall(line)}
        if len(hashes) != 1:
            errors.append(f"recipe has no single digest for {name}")
        else:
            recipe_hashes[name] = hashes.pop()
    for key, value in image.items():
        if "sha256" not in key.lower():
            continue
        if synthetic:
            if not is_placeholder(value, "<W2") or "recipe" not in value or "selected-release" not in value:
                errors.append(f"image.{key} must await the selected release's W2 digest")
        elif value != recipe_hashes.get(release):
            errors.append(f"image.{key} differs from the recipe's {release} digest")
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
    if steps != set(REQUIRED_STAGE_IDS):
        errors.append("the recipe does not contain the independent required stage ids")
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
    mask = field(receipt, "first_launch", "getty_mask")
    if not isinstance(mask, dict) or set(mask) != {"is_enabled", "load_state", "active_state", "n_restarts"} or not all(
            is_placeholder(value, "<W5") for value in mask.values()):
        errors.append("first_launch.getty_mask must retain W5's four mask observations")
    export = field(receipt, "w5_failure_export")
    if not isinstance(export, dict) or set(export) != {"file", "sha256", "bytes", "cause"} or not all(
            is_placeholder(value, "<W5") for value in export.values()):
        errors.append("w5_failure_export must hold W5 placeholders for file, sha256, bytes and cause")
    baseline = field(receipt, "host", "workstation_baseline")
    if isinstance(baseline, dict) and "getty_tty1_result" in baseline:
        optional = baseline["getty_tty1_result"]
        if not is_placeholder(optional, "<W1") or not all(part in optional for part in
                ("present only when", "Result=start-limit-hit", "NRestarts", "omit this key")):
            errors.append("getty_tty1_result is optional and present only when W1's extra command ran")
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
    if tuple(steps) != REQUIRED_STAGE_IDS or tuple(listed) != REQUIRED_STAGE_IDS:
        errors.append("the recipe or checklist differs from the independent required stage ids and order")
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
    if F10_PROBE in f10:
        return []
    return ["F10 does not obtain each path without word splitting and test it inside [[ -f ... && -x ... ]]"]


def powershell_quote_errors(recipe: str) -> list[str]:
    """Rehearsal run 3 (2026-10-02): Windows PowerShell 5.1 does not escape a double quote inside an argument it hands
    to a native program, so `wsl.exe ... 'stat -c "%U %F" ...'` reached Bash as `stat -c %U` and returned
    `stat: missing operand`. No single-quoted argument of a `wsl.exe` command in a PowerShell block holds one."""
    errors = []
    for step, shell, command in recipe_rows(recipe):
        if shell != "powershell" or not command.startswith("wsl.exe"):
            continue
        for argument in re.findall(r"'([^']*)'", command):
            if '"' in argument:
                errors.append(f"{step}: a PowerShell command hands wsl.exe an argument with a double quote: {command}")
                break
    return errors


def f9_errors(recipe: str) -> list[str]:
    """F9 is one sh block of exactly F9_COMMANDS and runs no profile of the bootstrap. The two native sign-ins come after
    the block's last line (the tool's --apply needs no signed-in client, and the configuration must exist before a first
    start leaves a config.toml behind), then the plan's after-sign-in check, for exactly the owners whose plan row has that
    stage. The sign-in and the checks are prose, not comments in the block: a `#` line inside a fence starts a new unit for
    tests/test_adoption_docs_consistency.py."""
    errors = []
    blocks = step_blocks(recipe, "F9")
    if blocks != [F9_COMMANDS]:
        errors.append(f"F9 must hold one command block of exactly {F9_COMMANDS}, not {blocks}")
    text = section(recipe, "F9")
    if "--configure-full-profile" in "\n".join(command for block in blocks for command in block) or any(
            command.startswith("adoption/bootstrap-linux.sh") for block in blocks for command in block):
        errors.append("F9 runs the bootstrap's profile, which installs and wires tools the manifest does not install")
    fences = [match["lang"] for match in FENCE_RE.finditer(text)]
    if fences != ["sh"]:
        errors.append(f"F9 must hold exactly one fenced block, an sh block, not {fences}")
    if "<id>" in text:
        errors.append("F9 names an <id> placeholder, which only the bootstrap's --profile took")
    fence = FENCE_RE.search(text)
    before = " ".join(text[:fence.start()].split()) if fence else ""
    after = " ".join(text[fence.end():].split()) if fence else " ".join(text.split())
    if "run `codex login`" in before or F9_SIGN_IN not in after:
        errors.append("F9 does not say, after the block, to sign in by hand: `codex login`, then `claude`")
    elif F9_AFTER_SIGN_IN not in after or after.index(F9_AFTER_SIGN_IN) < after.index(F9_SIGN_IN):
        errors.append("F9 does not give the plan's after-sign-in check after the sign-in sentence")
    slots = {row["slot"] for row in plan_rows()}
    named = {token for token in re.findall(r"`([^`]+)`", after) if token in slots}
    owners = set(plan_after_sign_in_slots())
    if named != owners:
        errors.append(f"F9 names the owners {sorted(named)} for the after-sign-in checks; the plan's rows with that stage "
                      f"are {sorted(owners)}")
    return errors


def reword(page: str, phrase: str, new: str) -> str:
    """The page with `phrase` replaced once, found by its words whatever the line breaks, so that the page stays wrapped
    and its sections still parse (a page joined into one line has no F9 section: every phrase would then read as missing,
    and a mutant would fail for that reason and not for its own)."""
    pattern = r"\s+".join(re.escape(word) for word in phrase.split())
    changed, count = re.subn(pattern, lambda match: new, page, count=1)
    assert count == 1, phrase
    return changed


def authorization_errors(recipe: str, checklist: str, receipt: dict) -> list[str]:
    """The plain `--apply` of F9 writes none of the authorization settings. The option that writes the missing ones is named in
    F9's prose, for a host whose owner asked for the repository's permission practice, and never in the command block; the
    receipt records who asked; and F9 says what the filter of the instruction blocks does and does not establish."""
    errors = []
    text = " ".join(section(recipe, "F9").split())
    whole = " ".join(recipe.split())
    for phrase in F9_AUTHORIZATION_PHRASES[:3] + (F9_BLOCKS_SENTENCE, AUTHORIZATION_LINE_SENTENCE):
        if phrase not in text:
            errors.append(f"F9 lacks: {phrase}")
    if F9_AUTHORIZATION_PHRASES[3] not in whole:
        errors.append("the receipt contents list does not name F9's authorization_settings")
    for claim in (F9_OLD_BLOCKS_CLAIM, F9_PREVIOUS_BLOCKS_CLAIM):
        if claim in text:
            errors.append(f"F9 still says {claim!r}; the filter goes by the names the map lists for unwired pieces and by "
                          "the former defaults of the manifest rows that install nothing")
    if any(AUTHORIZATION_OPTION in command for block in step_blocks(recipe, "F9") for command in block):
        errors.append(f"the F9 command block carries {AUTHORIZATION_OPTION}; the operator adds it, the page does not")
    line = next((line for line in checklist.splitlines() if line.startswith("- [ ] **F9**")), "")
    if AUTHORIZATION_OPTION not in line or "authorization_settings" not in line:
        errors.append("the checklist's F9 line does not name the option and the receipt's authorization_settings")
    field = receipt.get("authorization_settings") if isinstance(receipt, dict) else None
    if not isinstance(field, str) or not field.startswith("<F9:") or f"who asked for {AUTHORIZATION_OPTION}" not in field:
        errors.append("the receipt example has no authorization_settings field that records who asked for the option")
    return errors


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
    docs/decisions/2026-09-23-claude-user-profile.md), and no script registers it. Since 2026-10-02 F9 does not copy the
    carrier blocks, so no session on the new distribution is told to use jCodeMunch; F11 stays as the way a host that
    installs the binary registers it. F11 runs bootstrap step 4a's own line
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


def reword(text: str, old: str, new: str) -> str:
    """``text`` with the one phrase ``old`` replaced by ``new``, however the Markdown wraps it. It fails when the phrase is
    not there exactly once, so a control that restores the pre-change wording cannot pass by changing nothing."""
    pattern = r"\s+".join(re.escape(word) for word in old.split())
    mutated, count = re.subn(pattern, lambda _match: new, text)
    if count != 1:
        raise AssertionError(f"{old!r} occurs {count} times, expected one")
    return mutated


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
    for needed in ("for RELEASE in 26.04.1 24.04.5; do", 'if [ "$?" -ne 0 ]; then exit 1; fi', "done"):
        if needed not in lines:
            errors.append(f"P1 lacks both-arm signature verification: {needed}")
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
    """Item D (critic item 3), under the coordinator's rule of 2026-10-01. The workstation distribution shares the
    kernel. Before stage 1, P3 counts the current boot's ``hv_storvsc`` kernel journal lines (sudo: the user cannot read
    the kernel journal; ``dmesg`` keeps only the recent ring buffer), by the driver's name rather than a device id and
    without the driver's registration line, which every boot logs. The count is a baseline, not a verdict. P3 prints the
    newest error line with its kernel time and the uptime: a line less than one hour old means errors are happening now,
    and the run stops. The one-hour threshold is the recipe's choice. W5 counts again after the first launch, on both
    paths: attachment errors before cloud-init starts are recorded; later errors or a provisioning failure with a
    storage cause stop the run. A bare count that stops on any line was rejected: it cannot tell
    an old burst from errors that are happening now."""
    steps = STEP_RE.findall(recipe)
    if "P3" not in steps:
        return ["the recipe has no ### P3. step (the kernel storage errors)"]
    errors = [] if before_stage_1(steps, "P3") else ["P3 does not run before stage 1"]
    if step_commands(recipe, "P3") != [("sh", command) for command in P3_COMMANDS]:
        errors.append(f"P3's commands are not {P3_COMMANDS}")
    p3 = prose(section(recipe, "P3"))
    errors += [f"P3's text does not name {needed}" for needed in
               (STORVSC_ISSUE, "a baseline, not a verdict", "less than one hour", "3600", THRESHOLD_SOURCE,
                "registration line", "swap=0", "stops the run") if needed not in p3]
    if "A nonzero count stops the run" in p3:
        errors.append("P3 still stops the run on any nonzero count")
    rows = recipe_rows(recipe)
    second = [index for index, (step, shell, command) in enumerate(rows) if step == "W5" and shell == "sh"]
    launch = [index for index, (step, _, command) in enumerate(rows) if step == "W5" and "< NUL" in command]
    counts = [index for index in second if rows[index][2] == STORVSC_COUNT]
    if len(counts) != 1 or not launch or counts[0] < launch[0]:
        errors.append("W5 does not count the storage errors again, in the workstation distribution, after the launch")
    w5 = prose(section(recipe, "W5"))
    errors += [f"W5's text does not name {needed}" for needed in
               ("On both paths", "P3's baseline", "the new lines", "exposure to microsoft/WSL#41482", "stage 2")
               if needed not in w5]
    evidence = prose(chapter(record, "Evidence classes"))
    errors += [f"the record's Evidence classes lack P3's {needed}" for needed in
               (*HISTORICAL_STORAGE_COMMANDS, UPTIME, "swapon --show", "registering driver hv_storvsc", "baseline")
               if needed not in evidence]
    if THRESHOLD_SOURCE not in prose(record) or "bare count" not in prose(chapter(record, "Alternatives")):
        errors.append("the record does not say the threshold is the recipe's choice and why a bare count was rejected")
    line = checklist_line(checklist, "P3")
    if not all(part in line for part in ("baseline", "one hour", "41482")):
        errors.append("the checklist's P3 line does not require the baseline and the one-hour rule")
    if "P3's baseline" not in checklist_line(checklist, "W5"):
        errors.append("the checklist's W5 line does not compare the second count with P3's baseline")
    block = field(receipt, "storage_errors")
    if not isinstance(block, dict) or set(block) != set(STORAGE_FIELDS) or not all(
            is_placeholder(block[key], prefix) for key, prefix in STORAGE_FIELDS.items()):
        errors.append(f"the receipt example has no storage_errors block with {sorted(STORAGE_FIELDS)}")
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
                "W6's export rule", "`rehearsal`", "P3's baseline and W5's second count") if needed not in r1]
    blocks = [block for block in step_blocks(recipe, "R1") if UNREGISTER in block]
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

    def test_the_template_collector_port_is_the_install_plans_otlp_http_port(self):
        grpc, http = plan_collector_ports()
        # The plan states the collector's ports twice, in config/otel.yaml and in its inventory row; they agree.
        stated = re.search(r"OTLP grpc/http endpoint=127\.0\.0\.1:(\d+)/(\d+)", next(
            row for row in plan_rows() if row["slot"] == "otel-collector-contrib")["service"]["port_setting"])
        self.assertEqual((grpc, http), tuple(int(port) for port in stated.groups()))
        values = json.loads(string.Template(read(HOST_TEMPLATE)).substitute(WSL_USER="example"))
        self.assertEqual(values["OTEL_ENDPOINT"], f"127.0.0.1:{http}")
        # None of the template's other ports is one the plan's services or configuration files use.
        others = {int(values[key].rsplit(":", 1)[1]) for key in URL_KEYS if key != "OTEL_ENDPOINT"}
        self.assertEqual(others & plan_loopback_ports(), set())
        self.assertEqual(others & WORKSTATION_PORTS, set())

    def test_the_check_rejects_a_collector_port_that_is_not_the_plans_and_a_plan_port_elsewhere(self):
        example, good, recipe = json.loads(read(HOST_EXAMPLE)), read(HOST_TEMPLATE), read(RECIPE)
        grpc, http = plan_collector_ports()
        other = next(port for port in range(21900, 21999) if port not in plan_loopback_ports()
                     and port not in WORKSTATION_PORTS)
        plan_port = next(int(row["service"]["port"]) for row in plan_rows() if row["slot"] == "local-model-server")
        qdrant = int(re.search(r'"QDRANT_URL": "127\.0\.0\.1:(\d+)"', good).group(1))

        def moved(key: str, old: int, new: int):
            """The template and the recipe's probe both moved, so only the plan comparison can object."""
            return (good.replace(f'"{key}": "127.0.0.1:{old}"', f'"{key}": "127.0.0.1:{new}"'),
                    recipe.replace(f"sport = :{old}", f"sport = :{new}"))

        mutants = {
            "the workstation's collector port": moved("OTEL_ENDPOINT", http, 24318),
            "a free port that is not the plan's": moved("OTEL_ENDPOINT", http, other),
            "the plan's gRPC port": moved("OTEL_ENDPOINT", http, grpc),
            "Qdrant on a port the plan's services use": moved("QDRANT_URL", qdrant, plan_port),
            "the workstation's Qdrant port": moved("QDRANT_URL", qdrant, 26333),
            "the relocated collector port not excluded": (good, recipe.replace("`24318`", "24318")),
            "the relocated Qdrant port not excluded": (good, recipe.replace("`26333`", "26333")),
        }
        for name, (template, page) in mutants.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(template + page, good + recipe)
                self.assertTrue(host_template_errors(template, example, page))
        template, page = moved("OTEL_ENDPOINT", http, other)
        self.assertTrue(any("install plan's collector" in error for error in host_template_errors(template, example, page)))
        template, page = moved("QDRANT_URL", qdrant, plan_port)
        self.assertTrue(any("install plan's services" in error for error in host_template_errors(template, example, page)))

    def test_f8_gives_the_reason_for_excluding_the_workstations_collector_and_qdrant_ports(self):
        text = " ".join(section(read(RECIPE), "F8").split())
        for part in ("`24318` and `26333`", "collector", "Qdrant", "observed listening 2026-10-02"):
            self.assertIn(part, text)


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


class StageTwoTests(unittest.TestCase):
    """F9 runs the install plan, the client-configuration tool's check and apply, then the native sign-ins by hand, then
    the plan's after-sign-in checks."""

    def test_f9_is_the_install_plan_the_tool_the_sign_ins_and_the_after_sign_in_checks(self):
        self.assertEqual(f9_errors(read(RECIPE)), [])

    def test_the_commands_name_files_that_exist(self):
        for command in F9_COMMANDS[1:]:
            path = re.search(r"(?:bash|python3 -B) (\S+)", command).group(1)
            self.assertTrue((ROOT / path).is_file(), path)
        self.assertEqual(sorted(path.name for path in PLAN_DIR.iterdir() if path.name.endswith(".sh")),
                         ["accept.sh", "install.sh"])

    def test_the_after_sign_in_owners_are_read_from_the_plan_and_accept_sh_takes_the_stage_and_the_slot(self):
        owners = plan_after_sign_in_slots()
        self.assertEqual(owners, ["codex", "claude-agent-sdk", "codex-sdk-and-codex-exec-app-server",
                                  "local-model-server", "agent-runtime-worker", "research-harnesses"])
        script = read(PLAN_DIR / "accept.sh")
        for part in ("--only)", "--stage)", "post_install|service_health|after_sign_in) ;;"):
            self.assertIn(part, script)
        accepted = re.search(r'case "\$only" in\n\s*(\S+?)\) ;;', script).group(1).split("|")
        self.assertEqual([owner for owner in owners if owner not in accepted], [])

    def test_the_check_rejects_the_old_commands_a_lost_step_a_wrong_order_and_a_second_block(self):
        recipe = read(RECIPE)
        block = "\n".join(F9_COMMANDS[1:3])
        old = ("adoption/bootstrap-linux.sh --profile '<id>'\n"
               "adoption/bootstrap-linux.sh --profile '<id>' --configure-full-profile --host '<host>'")
        tool = "\n".join(F9_COMMANDS[3:])
        self.assertIn(block, recipe)
        sign_in_and_checks = re.search(r"(After the `--apply` line, run `codex login`.*?signed in\)\.)\s+"
                                       r"(Then run the plan's\s+after-sign-in checks.*?has that stage\.)", recipe, re.S)
        self.assertIsNotNone(sign_in_and_checks)
        mutants = {
            "the old bootstrap commands": recipe.replace(block, old),
            "no acceptance script": recipe.replace(F9_COMMANDS[2] + "\n", ""),
            "no check before the apply": recipe.replace(F9_COMMANDS[3] + "\n", ""),
            "apply before check": recipe.replace(tool, "\n".join(reversed(F9_COMMANDS[3:]))),
            "no sign-in sentence": recipe.replace(F9_SIGN_IN, "Sign in later"),
            "the sign-in before the tool, the earlier order": recipe.replace(
                F9_SIGN_IN, "After the `accept.sh` line and before the `--check` line, run `codex login`, then `claude`, by hand"),
            "a sign-in sentence before the block": recipe.replace(
                f"```sh\n{CLONE}\nbash {F9_PLAN}/install.sh", f"First run `codex login`.\n\n```sh\n{CLONE}\nbash {F9_PLAN}/install.sh"),
            "no after-sign-in checks": recipe.replace("--stage after_sign_in", "--stage post_install"),
            "the checks before the sign-in": recipe.replace(
                sign_in_and_checks.group(0), sign_in_and_checks.group(2) + " " + sign_in_and_checks.group(1)),
            "an owner lost": recipe.replace("`agent-runtime-worker` and ", ""),
            "an owner without that stage": recipe.replace("`research-harnesses`", "`research-harnesses` and `claude-code`"),
            "an id placeholder": recipe.replace("`--dry-run` shows", "`--dry-run` '<id>' shows"),
            "a second block": recipe.replace("Proof: `accept.sh` exits 0", "```sh\necho again\n```\n\nProof: `accept.sh` exits 0"),
            "the profile after the tool": recipe.replace(tool, tool + "\nadoption/bootstrap-linux.sh --configure-full-profile"),
        }
        for name, mutant in mutants.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(mutant, recipe)
                self.assertTrue(f9_errors(mutant), name)

    def test_f9_keeps_the_plain_apply_names_the_option_in_prose_and_the_receipt_records_who_asked(self):
        recipe, checklist = read(RECIPE), read(CHECKLIST)
        receipt = json.loads(read(RECEIPT_EXAMPLE))
        self.assertEqual(authorization_errors(recipe, checklist, receipt), [])
        self.assertEqual(step_blocks(recipe, "F9"), [F9_COMMANDS])
        self.assertEqual(F9_COMMANDS[-1], "python3 -B tools/adoption/new_wsl_client_config.py --apply --host '<host>'")
        without_field = {key: value for key, value in receipt.items() if key != "authorization_settings"}
        mutants = {
            "no sentence about what the plain apply writes": (
                recipe.replace("writes none of the authorization settings", "writes the settings"), checklist, receipt),
            "no condition on the owner's request": (
                recipe.replace("only on a host whose owner asked for the repository's permission practice",
                               "on any host"), checklist, receipt),
            "no word that the receipt records who asked": (
                re.sub(r"and the receipt's\s+`authorization_settings` records who asked", "", recipe), checklist, receipt),
            "the option in the command block": (
                recipe.replace(F9_COMMANDS[-1], F9_COMMANDS[-1] + " " + AUTHORIZATION_OPTION), checklist, receipt),
            "the old claim about the instruction blocks": (
                reword(recipe, F9_BLOCKS_SENTENCE, F9_OLD_BLOCKS_CLAIM), checklist, receipt),
            "the fourth round's claim about the instruction blocks": (
                reword(recipe, F9_BLOCKS_SENTENCE, F9_PREVIOUS_BLOCKS_CLAIM), checklist, receipt),
            "no manifest row among the names that decide": (
                reword(recipe, " or the former default of a manifest row that installs nothing", ""), checklist, receipt),
            "a unit left out merely for naming a skill": (
                reword(recipe, "a unit is not left out merely for naming a skill or timer that neither lists",
                       "sentences that name skills or timers stay as written"), checklist, receipt),
            "no sentence about the line --apply prints": (
                reword(recipe, AUTHORIZATION_LINE_SENTENCE, "a line about the settings"), checklist, receipt),
            "a line without the partial outcome": (reword(recipe, "`partly applied`, ", ""), checklist, receipt),
            "no word that the skills are not established": (
                re.sub(r"whether those skills exist on the host is not\s+established by this step",
                       "those skills exist on the host", recipe), checklist, receipt),
            "a receipt contents list without the field": (
                recipe.replace("F9's `authorization_settings`", "F9's settings"), checklist, receipt),
            "a checklist without the option": (recipe, checklist.replace(AUTHORIZATION_OPTION, "--x"), receipt),
            "a receipt without the field": (recipe, checklist, without_field),
            "a receipt field that does not say who asked": (
                recipe, checklist, dict(receipt, authorization_settings="<F9: none>")),
        }
        for name, mutant in mutants.items():
            with self.subTest(mutant=name):
                # A mutant must differ from the page in what is read, and must still be a page whose F9 section parses:
                # an unparsable page would fail every check for that reason alone.
                self.assertNotEqual((" ".join(mutant[0].split()), *mutant[1:]), (" ".join(recipe.split()), checklist, receipt))
                self.assertTrue(section(mutant[0], "F9").strip(), name)
                self.assertTrue(authorization_errors(*mutant), name)
        # The command block is also pinned by f9_errors, so the option in it fails there too.
        self.assertTrue(f9_errors(recipe.replace(F9_COMMANDS[-1], F9_COMMANDS[-1] + " " + AUTHORIZATION_OPTION)))

    def test_the_record_and_the_receipt_example_carry_the_f9_rows_and_both_comparisons_read_them(self):
        recipe, record = read(RECIPE), read(RECORD)
        receipt = json.loads(read(RECEIPT_EXAMPLE))
        components = {component["id"] for component in json.loads(read(STACK))["components"]}
        self.assertEqual([command for step, _, command in command_table(record) if step == "F9"], F9_COMMANDS)
        self.assertEqual([entry["cmd"] for entry in receipt["steps"] if entry["step"] == "F9"], F9_COMMANDS)
        self.assertEqual(command_table_errors(recipe, record), [])
        self.assertEqual(receipt_errors(receipt, recipe, components), [])
        # F9 is compared like any other step: a lost row, a changed command and a stale old row each fail.
        check = F9_COMMANDS[3]
        row = next(line for line in record.splitlines() if line.startswith(f"| F9 | sh | `{check}` |"))
        stale = "| F9 | sh | `adoption/bootstrap-linux.sh --profile '<id>'` | stage 2 (bootstrap step 2) |"
        for name, mutant in {"a lost row": record.replace(row + "\n", ""),
                             "a changed command": record.replace(row, row.replace(check, check + " --skip verify")),
                             "a stale old row": record.replace(row + "\n", row + "\n" + stale + "\n")}.items():
            with self.subTest(record=name):
                self.assertNotEqual(mutant, record)
                self.assertTrue(command_table_errors(recipe, mutant))
        apply = F9_COMMANDS[4]
        entry_mutants = {
            "a lost entry": [e for e in receipt["steps"] if not (e["step"] == "F9" and e["cmd"] == check)],
            "a changed command": [dict(e, cmd=e["cmd"] + " --skip verify") if e["step"] == "F9" and e["cmd"] == apply else e
                                  for e in receipt["steps"]],
            "a stale old entry": [*receipt["steps"], {"step": "F9", "cmd": "adoption/bootstrap-linux.sh --profile '<id>'",
                                                      "exit": "<exit code>", "output_excerpt": "<sanitized output>"}],
        }
        for name, entries in entry_mutants.items():
            with self.subTest(receipt=name):
                self.assertTrue(receipt_errors(dict(receipt, steps=entries), recipe, components))
        # Another step still fails both comparisons, as before.
        step, shell, command = next(row for row in recipe_rows(recipe) if row[0] == "F8")
        self.assertTrue(command_table_errors(recipe.replace(command, command + " # changed"), record))


class ImageHashTests(unittest.TestCase):
    def test_the_recipe_record_receipt_example_and_checklist_pin_both_image_sha256_pairs(self):
        receipt = json.loads(read(RECEIPT_EXAMPLE))
        self.assertEqual(sha256_errors(read(RECIPE), read(RECORD), receipt, read(CHECKLIST)), [])

    def test_the_check_rejects_a_drifted_hash(self):
        recipe, record, checklist = read(RECIPE), read(RECORD), read(CHECKLIST)
        receipt = json.loads(read(RECEIPT_EXAMPLE))
        other = "0" * 64
        for release, pin in RELEASE_PINS.items():
            expected = pin["sha256"]
            with self.subTest(release=release):
                self.assertTrue(sha256_errors(recipe, record.replace(expected, other), receipt, checklist))
                self.assertTrue(sha256_errors(recipe.replace(expected, other, 1), record, receipt, checklist))
                self.assertTrue(sha256_errors(recipe, record, receipt, checklist.replace(expected, other)))
                pins = {key: dict(value) for key, value in receipt["supported_images"].items()}
                pins[release]["sha256"] = other
                self.assertTrue(sha256_errors(recipe, record, dict(receipt, supported_images=pins), checklist))
        self.assertTrue(sha256_errors(recipe, record, dict(receipt, image=dict(receipt["image"], sha256_published=other)),
                                      checklist))
        trial, fallback = (RELEASE_PINS[release]["sha256"] for release in ("26.04.1", "24.04.5"))
        swapped = recipe.replace(trial, "SWAP").replace(fallback, trial).replace("SWAP", fallback)
        self.assertTrue(sha256_errors(swapped, record, receipt, checklist))
        pins = {key: dict(value) for key, value in receipt["supported_images"].items()}
        pins["26.04.1"]["bytes"] = IMAGE_BYTES
        self.assertTrue(sha256_errors(recipe, record, dict(receipt, supported_images=pins), checklist))
        self.assertTrue(sha256_errors(recipe + "\n" + other, record, receipt, checklist))
        self.assertTrue(sha256_errors(recipe.replace("$Actual -ne $Expected", "$Actual -eq $Expected"), record,
                                      receipt, checklist))


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
        self.assertIn("[[ -f $p && -x $p ]] && ", recipe)
        self.assertTrue(path_proof_errors(recipe.replace("[[ -f $p && -x $p ]] && ", "")))


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
                self.assertTrue(mutant != good, f"control made no change: {name}")
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
            "missing trial arm": (recipe.replace("for RELEASE in 26.04.1 24.04.5; do", "for RELEASE in 24.04.5; do"),
                                  record, checklist, receipt),
            "signature failure continues": (recipe.replace('if [ "$?" -ne 0 ]; then exit 1; fi\n', ""), record,
                                             checklist, receipt),
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
    """Item D (critic item 3), under the coordinator's rule: P3 records a baseline and stops only on errors less than
    one hour old; W5 counts again after the first launch on both paths."""

    def test_p3_records_a_baseline_with_a_recency_rule_and_w5_counts_again(self):
        self.assertEqual(kernel_storage_errors(*self.inputs()), [])

    def test_the_check_rejects_the_old_rule_no_recency_rule_no_second_reading_and_lost_records(self):
        recipe, record, checklist, receipt = self.inputs()
        p3, w5, count = section(recipe, "P3"), section(recipe, "W5"), STORVSC_COUNT + "\n"
        for line in (count, STORVSC_NEWEST + "\n", UPTIME + "\n"):
            self.assertIn(line, p3)
        self.assertIn(count, w5)
        later = "### W5. "
        page = lambda new: (recipe.replace(p3, p3.replace(count, new)), record, checklist, receipt)  # noqa: E731
        text = lambda old, new: (recipe.replace(p3, p3.replace(old, new)), record, checklist, receipt)  # noqa: E731
        self.assert_mutants_fail(kernel_storage_errors, {
            "dmesg": page(count.replace("sudo journalctl -k -b 0 --no-pager", "dmesg")),
            "no sudo": page(count.replace("sudo ", "", 1)),
            "registration line counted": page("sudo journalctl -k -b 0 --no-pager | grep -c hv_storvsc\n"),
            "a device id": page(count.replace("grep hv_storvsc", "grep " + "-".join(("0" * 8, "0" * 4, "0" * 4, "0" * 4, "0" * 12)))),
            "no swap state": text("swapon --show\n", ""),
            "no issue": text(STORVSC_ISSUE, "https://example.invalid/"),
            "no newest line": text(STORVSC_NEWEST + "\n", ""),
            "no uptime": text(UPTIME + "\n", ""),
            "no recency rule": text("less than one hour", "recent"),
            "the old stop rule": text("a baseline, not a verdict", "A nonzero count stops the run"),
            "no second reading": (recipe.replace(w5, w5.replace(count, "")), record, checklist, receipt),
            "second reading on one path": (recipe.replace(w5, w5.replace("On both paths", "On path A")), record,
                                           checklist, receipt),
            "no exposure rule": (recipe.replace(w5, w5.replace("exposure to microsoft/WSL#41482", "a warning")), record,
                                 checklist, receipt),
            "after the install": (recipe.replace(p3, "").replace(later, p3 + later, 1), record, checklist, receipt),
            "record without the run": (recipe, record.replace("sudo journalctl -k -b 0 --no-pager", "the journal read"),
                                        checklist, receipt),
            "record without the threshold's source": (recipe, record.replace(THRESHOLD_SOURCE, "an upstream figure"),
                                                      checklist, receipt),
            "checklist with the old rule": (recipe, record, checklist.replace(checklist_line(checklist, "P3"),
                                                                              "- [ ] **P3** The count is `0` (41482)."),
                                            receipt),
            "checklist without the second count": (recipe, record, checklist.replace("P3's baseline", "the baseline"),
                                                   receipt),
            "no receipt block": (recipe, record, checklist, without(receipt, "storage_errors")),
            "no second count in the receipt": (recipe, record, checklist, without(receipt, "storage_errors",
                                                                                  "second_count")),
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
            "no storage readings": (recipe.replace(r1, reword(r1, "P3's baseline and W5's second count", "the counts")),
                                    record, checklist, receipt, experiment),
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
                self.assertTrue(mutant != (recipe, record, checklist, receipt, experiment), f"control made no change: {name}")
                self.assertTrue(rehearsal_errors(*mutant))


class DualImageParameterizationTests(unittest.TestCase):
    """Public recipe artifacts, checked against the two signed primary-source pins; no host execution."""

    def test_both_releases_are_pinned_and_install_the_selected_file(self):
        recipe = read(RECIPE)
        self.assertEqual(set(SHA256_RE.findall(recipe)), {pin["sha256"] for pin in RELEASE_PINS.values()})
        for release, pin in RELEASE_PINS.items():
            with self.subTest(release=release):
                self.assertIn(f"'{release}' {{ $Expected = '{pin['sha256']}'; $CatalogName = '{pin['catalog_name']}' }}",
                              section(recipe, "W2"))
        self.assertIn("default { throw 'unsupported release: do not download or install' }", section(recipe, "W2"))
        for step in ("W4", "W6"):
            self.assertIn("Z:\\WSL\\downloads\\ubuntu-<RELEASE>-wsl-amd64.wsl", section(recipe, step))
        receipt = json.loads(read(RECEIPT_EXAMPLE))
        self.assertEqual(receipt.get("supported_images"), RELEASE_PINS)

    def test_preregistered_rehearsals_cover_both_images_without_claiming_acceptance(self):
        recipe, receipt = read(RECIPE), json.loads(read(RECEIPT_EXAMPLE))
        criteria = {"first_boot", "systemd_user_from_second_instance", "wsl_gpu", "uv_cpython_3_13", "node_24"}
        arms = receipt.get("comparison_arms", {})
        self.assertEqual(set(arms), set(RELEASE_PINS))
        for release, arm in arms.items():
            with self.subTest(release=release):
                self.assertEqual(arm["status"], "unrun")
                self.assertEqual(set(arm) - {"status", "name"}, criteria)
                self.assertTrue(all(is_placeholder(arm[key], "<R1") for key in criteria))
        r1 = section(recipe, "R1")
        for criterion in criteria:
            self.assertIn(f"`{criterion}`", r1)
        for command in ("systemctl --user is-system-running --wait", "test -c /dev/dxg",
                        "/usr/lib/wsl/lib/nvidia-smi", "uv run --no-project --python 3.13 python --version",
                        "node --version"):
            self.assertTrue(any(command in line for _, line in step_commands(recipe, "R1")), command)
        self.assertIn("26.04.1 is the single default", prose(r1))
        self.assertIn("release-caused 26.04 failure with no in-release remedy", prose(r1))
        self.assertIn("from the workstation's second-instance session", prose(r1))
        self.assertIn("host check is not image qualification", prose(section(recipe, "P2")))
        self.assertIn("wsl.exe -d '<Name>' -u root --exec cloud-init --version",
                      [line for _, line in step_commands(recipe, "W5")])
        experiment = json.loads(read(EXPERIMENT))
        self.assertEqual(experiment["status"], "planned")
        self.assertEqual(experiment["observations"], [])
        self.assertEqual(experiment["decision_and_scope"]["qualification_run_ids"], [])
        self.assertEqual(quality_rule_errors(experiment), [])


def version_gate_errors(recipe: str, checklist: str) -> list[str]:
    errors = []
    w1 = prose(section(recipe, "W1"))
    if ("powershell", "wsl.exe --version") not in step_commands(recipe, "W1"):
        errors.append("W1 does not record the installed WSL version")
    for needed in ("3.0.1 or later", "second systemd distribution", "before W4 or W6", "stop", "40519", "41512"):
        if needed not in w1:
            errors.append(f"W1 lacks the cgroup version precondition: {needed}")
    if "3.0.1 or later" not in checklist_line(checklist, "W1"):
        errors.append("the checklist still accepts an older second systemd distribution")
    rules = prose(chapter(recipe, "Host-wide rules"))
    for needed in ("single systemd distribution", "2.4.10 or later", "2.7.13", "shared cgroup"):
        if needed not in rules:
            errors.append(f"the host rules lack the older single-distribution boundary: {needed}")
    if "No WSL update is needed to install" in rules or "2.4.10 or later" in w1:
        errors.append("the second-distribution preflight still accepts the old install-only minimum")
    return errors


def namespace_observation_errors(recipe: str, checklist: str) -> list[str]:
    errors = []
    if not any(block == WORKSTATION_COMMANDS for block in step_blocks(recipe, "W1")):
        errors.append("W1 lacks the native observation on the running distribution")
    for needed in ("cgroup:[4026531835]", "PROC_CGROUP_INIT_INO", "initial cgroup namespace",
                   "A noninitial namespace is necessary but does not prove isolation"):
        if needed not in prose(section(recipe, "W1")):
            errors.append(f"W1 lacks the namespace observation's interpretation: {needed}")
    if NAMESPACE_READ not in checklist:
        errors.append("the checklist omits the namespace observation")
    return errors


def cgroup_launch_errors(recipe: str, checklist: str) -> list[str]:
    errors = []
    w5 = section(recipe, "W5")
    order = ("systemctl is-active '<COMMON_UNIT>'",
             "/mnt/c/Windows/System32/wsl.exe -d '<Name>' --exec systemctl is-active '<COMMON_UNIT>'", CGROUP_PROCS, USER_MANAGER_ACTIVE)
    blocks = step_blocks(recipe, "W5")
    if not any(all(command in block for command in order) and
               [block.index(command) for command in order] == sorted(block.index(command) for command in order)
               for block in blocks):
        errors.append("W5 lacks the native cross-distribution cgroup and user-manager checks in order")
    for needed in ("after the first launch", "before F1", "while both distributions run", "no `0` entry",
                   "user@<uid>.service", "empty or unreadable", "never stop or restart a unit in either distribution"):
        if needed not in prose(w5):
            errors.append(f"W5 lacks its conclusive cgroup proof or recovery rule: {needed}")
    failed_tar = r"Z:\WSL\downloads\<Name>-w5-failed.tar"
    export = f"wsl.exe --export '<Name>' '{failed_tar}'"
    failures = [block for block in blocks if export in block]
    if len(failures) != 1:
        errors.append("W5 lacks the recovery for any failed proof")
    else:
        block = failures[0]
        recovery = (TERMINATE, export, EXPORT_GUARD, UNREGISTER, INTEROP_VERIFY, INTEROP_GUARD)
        if not all(command in block for command in recovery) or (
                [block.index(command) for command in recovery] != sorted(block.index(command) for command in recovery)):
            errors.append("cgroup failure must terminate only the new distro, guard the export, unregister and check interop")
        if any(re.search(r"systemctl\s+(?:stop|restart)\b", command) for command in block):
            errors.append("cgroup failure recovery tries to stop or restart a system unit")
    if "cgroup.procs" not in checklist_line(checklist, "W5"):
        errors.append("the checklist lacks the post-launch cgroup proof")
    return errors


def unregister_interop_errors(recipe: str, checklist: str) -> list[str]:
    errors = []
    sites = Counter()
    for step in REQUIRED_STAGE_IDS:
        for block in step_blocks(recipe, step):
            for index, command in enumerate(block):
                if command != UNREGISTER:
                    continue
                sites[step] += 1
                if block[index + 1:index + 3] != [INTEROP_VERIFY, INTEROP_GUARD]:
                    errors.append(f"{step} unregister {sites[step]} lacks the immediate surviving-distribution interop check")
    if sites != Counter({"R1": 2, "W5": 1, "W6": 1}):
        errors.append(f"unregister sites {dict(sites)} differ from the four reviewed removals")
    r1 = prose(section(recipe, "R1"))
    # The follow-up of 2026-10-02: on the adopted release the restart exits 1, so the recovery is a stop for review with two
    # records (binfmt_recovery_errors); the stop when Windows execution does not return stays a requirement here.
    if "stop for review" not in r1:
        errors.append("interop recovery lacks a stop for review when Windows execution does not return")
    for step in ("R1", "W6"):
        if "WSLInterop" not in checklist_line(checklist, step) or "Windows executable" not in checklist_line(checklist, step):
            errors.append(f"the checklist's {step} removal lacks both interop observations")
    if "whether binfmt registrations survive" in recipe:
        errors.append("the recipe still presents the observed binfmt loss as an open question")
    return errors


def storage_window_errors(recipe: str, checklist: str) -> list[str]:
    errors = []
    for name, text in (("recipe", section(recipe, "W5")), ("checklist", checklist_line(checklist, "W5"))):
        if STORAGE_RULE not in prose(text):
            errors.append(f"the {name} lacks the single storage-count and attachment-window rule")
        if "count equals P3's baseline" in prose(text) or "count equals the baseline" in prose(text):
            errors.append(f"the {name} still stops on an attachment-only increase")
        if USER_SESSION_WARNING not in text:
            errors.append(f"the {name} does not stop on the systemd user-session launch warning")
    p3 = STEP_RE.findall(recipe).index("P3") if "P3" in STEP_RE.findall(recipe) else -1
    w4 = STEP_RE.findall(recipe).index("W4") if "W4" in STEP_RE.findall(recipe) else -1
    if not 0 <= p3 < w4 or ("sh", STORVSC_COUNT) not in step_commands(recipe, "P3"):
        errors.append("the baseline is not recorded before the import")
    if ("sh", STORVSC_COUNT) not in step_commands(recipe, "W5"):
        errors.append("there is no second count after the first launch")
    return errors


def adopted_target_errors(recipe: str) -> list[str]:
    """Change 1 of the follow-up of 2026-10-02. "Host-wide rules" states, as policy, that the recipe adopts stable WSL
    3.0.1 or later for a second systemd distribution. The 2.9.8 and 2.9.13 pre-release history stays beside it, and one
    sentence says the host was updated to 3.0.1.0 on 2026-10-02 and passed its check, with the two-distribution proof still
    owed. The two sentences the change replaced must not come back."""
    rules = prose(chapter(recipe, "Host-wide rules"))
    errors = [f"Host-wide rules lack: {needed}" for needed in
              (ADOPTED_TARGET, HOST_UPDATE, "Neither pre-release is adopted", "2.9.8 pre-release notes",
               "2.9.13 pre-release notes") if needed not in rules]
    errors += [f"Host-wide rules still say: {old}" for old in (OLD_ADOPTED_TARGET, OLD_HOST_UPDATE) if old in rules]
    return errors


def paired_isolation_errors(recipe: str, record: str, checklist: str, receipt: dict) -> list[str]:
    """Change 2 of the follow-up of 2026-10-02. A reading of one distribution cannot show the same uid, distinct namespaces
    and two healthy managers, so W5 runs, natively in the workstation's shell after its cgroup block and before F1, one
    block of ten command lines that read the same five values from both running distributions, and records them under the
    receipt's ``paired_isolation`` (one object per distribution). W1 holds the workstation's baseline of the five, without
    sudo, and W6 repeats the record as it repeats the cgroup proof."""
    errors = []
    w1 = step_commands(recipe, "W1")
    if not all(("sh", command) in w1 for command in WORKSTATION_COMMANDS):
        errors.append("W1 lacks the workstation's baseline of the five observations")
    if ("sh", OLD_NAMESPACE_READ) in w1:
        errors.append("W1 still records the lone `/proc/1` namespace read, which needs privilege")
    blocks = step_blocks(recipe, "W5")
    paired = [block for block in blocks if "systemctl is-system-running" in block or NEW_COMMANDS[0] in block]
    if paired != [WORKSTATION_COMMANDS + NEW_COMMANDS]:
        errors.append("W5 does not hold one block of ten separate paired commands, the workstation's five first")
    else:
        cgroup = next((index for index, block in enumerate(blocks) if CGROUP_PROCS in block), len(blocks))
        if blocks.index(paired[0]) <= cgroup:
            errors.append("W5's paired block does not come after its cgroup block")
    w5 = prose(section(recipe, "W5"))
    errors += [f"W5's proof does not say: {needed}" for needed in (
        "both distributions print the same uid", "both user managers print `active`",
        "the new distribution's system state is `running` with no failed unit, or `degraded` with "
        "`systemd-binfmt.service` as its only failed unit",
        "differ from each other and neither is `cgroup:[4026531835]`",
        "equal its own values recorded in W1 before the import",
        "the WSL version and kernel from W1 and the image revision from W2", "`paired_isolation`",
        *(f"`{key}`" for key in sorted(ISOLATION_KEYS))) if needed not in w5]
    if "paired record" not in prose(section(recipe, "W6")):
        errors.append("W6 does not repeat the paired record with the cgroup proof")
    rows = command_table(record)
    errors += [f"the record's command table lacks {step} {command}" for step, command in
               [*(('W1', command) for command in WORKSTATION_COMMANDS),
                *(('W5', command) for command in WORKSTATION_COMMANDS + NEW_COMMANDS)]
               if (step, "sh", command) not in rows]
    w1_line, w5_line = checklist_line(checklist, "W1"), checklist_line(checklist, "W5")
    if NAMESPACE_READ not in checklist or "baseline" not in w1_line:
        errors.append("the checklist's W1 line does not require the workstation's baseline")
    if "paired_isolation" not in w5_line or "W1 baseline" not in w5_line:
        errors.append("the checklist's W5 line does not require the paired record against the W1 baseline")
    if "paired record" not in checklist_line(checklist, "W6"):
        errors.append("the checklist's W6 line does not repeat the paired record")
    record_block = field(receipt, "paired_isolation")
    objects = [value for value in record_block.values() if isinstance(value, dict)] if isinstance(record_block, dict) else []
    if len(objects) != 2 or not all(set(value) == ISOLATION_KEYS and all(is_placeholder(item, "<W5") for item in
                                                                         value.values()) for value in objects):
        errors.append("the receipt example has no paired_isolation with the five keys for two distributions")
    host = field(receipt, "host")
    baseline = host.get("workstation_baseline") if isinstance(host, dict) else None
    if not isinstance(baseline, dict) or set(baseline) - {"getty_tty1_result"} != ISOLATION_KEYS or not all(
            is_placeholder(item, "<W1") for item in baseline.values()):
        errors.append("the receipt example's host has no workstation_baseline with the five keys (W1)")
    if isinstance(host, dict) and "cgroup_namespace" in host:
        errors.append("the receipt example's host still holds the lone cgroup_namespace read")
    return errors


def binfmt_unit_errors(recipe: str, record: str, checklist: str, receipt: dict) -> list[str]:
    """Change 3 of the follow-up of 2026-10-02, the unit. On the adopted release WSL mounts the binfmt status file
    read-only (microsoft/WSL#40621) while ``protectBinfmt`` is on, its default, so ``systemd-binfmt.service`` then fails
    with ``Failed to flush binfmt_misc rules, ignoring: Read-only file system``, which upstream calls benign (#41226). F1 passes on ``running``, or on
    ``degraded`` only when ``systemctl --failed --no-legend --plain`` lists exactly that unit and its log holds the
    message; any other failed unit stops the run. A text that accepts every ``degraded`` state, or stops at every one, fails."""
    errors = []
    f1 = [command for _, command in step_commands(recipe, "F1")]
    wanted = ["systemctl is-system-running --wait", F1_FAILED, F1_LOG]
    if any(command not in f1 for command in wanted) or [f1.index(command) for command in wanted] != sorted(
            f1.index(command) for command in wanted):
        errors.append(f"F1 does not run {wanted} in that order")
    if "systemctl --failed --no-legend" in f1:
        errors.append("F1 still lists the failed units without --plain")
    text = prose(section(recipe, "F1"))
    errors += [f"F1's text does not say: {needed}" for needed in
               (F1_PASS, FLUSH_MESSAGE, "Any other failed unit stops the run", BINFMT_PR, BINFMT_ISSUE, BINFMT_BENIGN,
                "`adm`", F1_SUDO_FALLBACK) if needed not in text]
    if "On `degraded`, record" in text:
        errors.append("F1 still stops at every `degraded`")
    decision = prose(chapter(record, "Decision"))
    errors += [f"the record's decision does not say: {needed}" for needed in
               ("`degraded` when `systemctl --failed --no-legend --plain` lists exactly `systemd-binfmt.service`",
                "microsoft/WSL#40621", "#41226") if needed not in decision]
    if "F1 reports `degraded` on a clean run" in prose(chapter(record, "Overturn condition")):
        errors.append("the record's overturn condition still revisits every `degraded` F1")
    rows = command_table(record)
    errors += [f"the record's command table lacks F1 {command}" for command in (F1_FAILED, F1_LOG)
               if ("F1", "sh", command) not in rows]
    errors += [f"the record's Sources lack {url}" for url in (BINFMT_PR, BINFMT_ISSUE) if url not in record]
    line = checklist_line(checklist, "F1")
    if not all(part in line for part in ("`running`", "`degraded`", "exactly `systemd-binfmt.service`",
                                         "any other failed unit stops", FLUSH_MESSAGE, "with no failed unit")):
        errors.append("the checklist's F1 line does not accept `degraded` for the one unit only")
    first = next((entry for entry in receipt.get("steps", []) if entry.get("step") == "F1"
                  and entry.get("cmd") == "systemctl is-system-running --wait"), {})
    if not all(isinstance(first.get(key), str) and "degraded" in first[key] for key in ("exit", "output_excerpt")):
        errors.append("the receipt example's F1 entry for the wait command still holds a fixed `running`")
    arms = receipt.get("comparison_arms", {})
    if not arms or not all("F1's pass condition" in str(arm.get("first_boot")) for arm in arms.values()):
        errors.append("the receipt example's first_boot criteria do not refer to F1's complete pass condition")
    return errors


def binfmt_recovery_errors(recipe: str, record: str, checklist: str, receipt: dict) -> list[str]:
    """Change 3 of the follow-up of 2026-10-02, the recovery. ``sudo systemctl restart systemd-binfmt`` was the WSL 2.7.x
    remedy for the lost WSLInterop registration. On the adopted release the registration is protected and that restart
    exits 1, so no recipe command may control the unit (a history sentence may still name the restart). Every unregister
    keeps its check. After R1's removal blocks, a native ``sh`` block repeats the check and records ``ls
    /proc/sys/fs/binfmt_misc`` and ``systemctl status systemd-binfmt.service --no-pager``, and the page stops for review,
    importing and provisioning nothing."""
    errors = [f"the recipe runs `{command}`, a control of systemd-binfmt" for _, command in fenced_commands(recipe)
              if UNIT_CONTROL_RE.search(command)]
    errors += [f"the record's command table has `{command}`, a control of systemd-binfmt"
               for _, _, command in command_table(record) if UNIT_CONTROL_RE.search(command)]
    r1 = step_commands(recipe, "R1")
    blocks = [block for block in step_blocks(recipe, "R1") if INTEROP_RECORDS[0] in block]
    if len(blocks) != 1 or blocks[0] != [NATIVE_INTEROP, *INTEROP_RECORDS]:
        errors.append("R1 lacks one sh block of the native check, `ls /proc/sys/fs/binfmt_misc` and "
                      "`systemctl status systemd-binfmt.service --no-pager`, in that order")
    else:
        guards = [index for index, (_, command) in enumerate(r1) if command == INTEROP_GUARD]
        first = next(index for index, (shell, command) in enumerate(r1) if shell == "sh" and command == NATIVE_INTEROP)
        if not guards or first < guards[-1]:
            errors.append("R1's records do not come after its interop checks")
    r1_text = prose(section(recipe, "R1"))
    errors += [f"R1's text does not say: {needed}" for needed in
               ("On WSL 2.7.13", "no remedy on the adopted release", BINFMT_PR, "exits 1", "stop for review",
                "do not import or provision another distribution", "`interop_after_unregister`")
               if needed not in r1_text]
    errors += [f"R1 still says: {old}" for old in
               ("If either check still fails, stop;", "Proof: the restart exits 0", "Recover from a native shell")
               if old in r1_text]
    w6 = prose(section(recipe, "W6"))
    if "do not import" not in w6 or "repeat both observations before resuming" in w6:
        errors.append("W6 does not stop for review without an import when the guard throws")
    for step in ("R1", "W6"):
        line = checklist_line(checklist, step)
        if "stops for review" not in line or "systemctl restart" in line:
            errors.append(f"the checklist's {step} line does not stop for review, or still runs the restart")
    decision = prose(chapter(record, "Decision"))
    if "stops for review" not in decision or "supported `sudo systemctl restart systemd-binfmt` recovery" in decision:
        errors.append("the record's decision does not stop for review, or still names the supported restart recovery")
    interop = receipt.get("interop_after_unregister") if isinstance(receipt, dict) else None
    if not isinstance(interop, str) or "stop for review" not in interop or "systemd-binfmt recovery" in interop:
        errors.append("the receipt example's interop_after_unregister does not record the stop for review")
    return errors


class RehearsalRepairTests(unittest.TestCase):
    """Source contracts from the real rehearsal; controls restore the unsafe old text in memory only."""

    def test_required_stages_are_independent_even_when_all_artifacts_lose_one(self):
        recipe, checklist = read(RECIPE), read(CHECKLIST)
        receipt = json.loads(read(RECEIPT_EXAMPLE))
        components = {c["id"] for c in json.loads(read(STACK))["components"]}
        self.assertEqual(tuple(STEP_RE.findall(recipe)), REQUIRED_STAGE_IDS)
        self.assertTrue(all(("W1", "sh", command) in recipe_rows(recipe) for command in WORKSTATION_COMMANDS))
        # The old checks derived their entire contract from the recipe and accepted this coordinated deletion.
        old_page = recipe.replace(section(recipe, "F4"), "")
        old_ticks = checklist.replace(checklist_line(checklist, "F4") + "\n", "")
        old_receipt = dict(receipt, steps=[e for e in receipt["steps"] if e["step"] != "F4"])
        self.assertTrue(checklist_errors(old_ticks, old_page))
        self.assertTrue(receipt_errors(old_receipt, old_page, components))

    def test_every_selected_image_digest_rejects_the_old_unchecked_fields(self):
        recipe, record, checklist = read(RECIPE), read(RECORD), read(CHECKLIST)
        receipt = json.loads(read(RECEIPT_EXAMPLE))
        self.assertEqual(sha256_errors(recipe, record, receipt, checklist), [])
        for key in SELECTED_IMAGE_DIGEST_FIELDS:
            with self.subTest(field=key, control="old unchecked selected digest"):
                old = dict(receipt, image=dict(receipt["image"], **{key: "0" * 64}))
                self.assertTrue(sha256_errors(recipe, record, old, checklist))
        for release, pin in RELEASE_PINS.items():
            image = dict(pin, release=release, **{key: pin["sha256"] for key in SELECTED_IMAGE_DIGEST_FIELDS})
            selected = dict(receipt, image=image)
            self.assertEqual(selected_image_digest_errors(recipe, selected), [])
            other = next(p["sha256"] for r, p in RELEASE_PINS.items() if r != release)
            for key in (*SELECTED_IMAGE_DIGEST_FIELDS, "sha256_additional"):
                with self.subTest(release=release, field=key, control="swapped selected digest"):
                    self.assertTrue(selected_image_digest_errors(recipe, dict(selected, image=dict(image, **{key: other}))))
            for key in SELECTED_IMAGE_DIGEST_FIELDS:
                self.assertTrue(selected_image_digest_errors(recipe, dict(selected, image={k:v for k,v in image.items()
                                                                                           if k != key})))

    def test_version_gate_rejects_the_old_install_only_minimum(self):
        recipe, checklist = read(RECIPE), read(CHECKLIST)
        self.assertEqual(version_gate_errors(recipe, checklist), [])
        old_w1 = section(recipe, "W1").replace("3.0.1 or later", "2.4.10 or later")
        self.assertNotEqual(old_w1, section(recipe, "W1"))
        self.assertTrue(version_gate_errors(recipe.replace(section(recipe, "W1"), old_w1), checklist))
        self.assertTrue(version_gate_errors(recipe, checklist.replace("3.0.1 or later", "2.4.10 or later")))

    def test_namespace_is_observed_and_never_used_as_the_version_gate(self):
        recipe, checklist = read(RECIPE), read(CHECKLIST)
        self.assertEqual(namespace_observation_errors(recipe, checklist), [])
        old = recipe.replace(WORKSTATION_BASELINE + "\n", "")
        self.assertNotEqual(old, recipe)
        self.assertTrue(namespace_observation_errors(old, checklist))
        self.assertTrue(namespace_observation_errors(recipe, checklist.replace(NAMESPACE_READ, "the namespace")))
        self.assertTrue(namespace_observation_errors(recipe.replace("does not prove isolation", "proves isolation"),
                                                      checklist))

    def test_cgroups_are_checked_from_the_running_distribution_before_f1(self):
        recipe, checklist = read(RECIPE), read(CHECKLIST)
        self.assertEqual(cgroup_launch_errors(recipe, checklist), [])
        for command in (CGROUP_PROCS, USER_MANAGER_ACTIVE):
            with self.subTest(control="old launch without isolation proof", command=command):
                old = recipe.replace(command + "\n", "")
                self.assertNotEqual(old, recipe)
                self.assertTrue(cgroup_launch_errors(old, checklist))

    def test_cgroup_failure_uses_only_the_new_distribution_recovery(self):
        recipe, checklist = read(RECIPE), read(CHECKLIST)
        self.assertEqual(cgroup_launch_errors(recipe, checklist), [])
        w5 = section(recipe, "W5")
        old = recipe.replace(w5, w5.replace("wsl.exe --export '<Name>' 'Z:\\WSL\\downloads\\<Name>-w5-failed.tar'\n", ""))
        self.assertNotEqual(old, recipe)
        self.assertTrue(cgroup_launch_errors(old, checklist))
        unsafe = recipe.replace(w5, w5.replace(TERMINATE + "\n", "sudo systemctl restart user@1000.service\n", 1))
        self.assertTrue(cgroup_launch_errors(unsafe, checklist))

    def test_every_unregister_checks_surviving_interop_and_stops_on_failed_recovery(self):
        recipe, checklist = read(RECIPE), read(CHECKLIST)
        self.assertEqual(unregister_interop_errors(recipe, checklist), [])
        self.assertEqual(sum(command == UNREGISTER for _, _, command in recipe_rows(recipe)), 4)
        removal = UNREGISTER + "\n" + INTEROP_VERIFY + "\n" + INTEROP_GUARD + "\n"
        self.assertEqual(recipe.count(removal), 4)
        for site in range(4):
            with self.subTest(control="old unregister without interop check", site=site + 1):
                parts = recipe.split(removal)
                parts[site] += UNREGISTER + "\n"
                old = removal.join(parts[:site + 1]) + removal.join(parts[site + 1:])
                self.assertEqual(old.count(removal), 3)
                self.assertTrue(unregister_interop_errors(old, checklist))
        # The interop recovery is a stop for review since 2026-10-02 (BinfmtRecoveryTests); dropping that stop is still rejected.
        r1 = section(recipe, "R1")
        old = recipe.replace(r1, reword(r1, "then stop for review", "then continue"))
        self.assertNotEqual(old, recipe)
        self.assertTrue(unregister_interop_errors(old, checklist))

    def test_both_storage_rules_reject_the_old_equal_count_requirement(self):
        recipe, checklist = read(RECIPE), read(CHECKLIST)
        self.assertEqual(storage_window_errors(recipe, checklist), [])
        pattern = re.escape(STORAGE_RULE).replace(r"\ ", r"\s+")
        for name in ("recipe", "checklist"):
            with self.subTest(control="old equal-count storage rule", file=name):
                page = re.sub(pattern, OLD_STORAGE_RULE, recipe) if name == "recipe" else recipe
                ticks = re.sub(pattern, OLD_STORAGE_RULE, checklist) if name == "checklist" else checklist
                self.assertNotEqual((page, ticks), (recipe, checklist))
                self.assertTrue(storage_window_errors(page, ticks))

    def test_launch_warning_stops_even_when_the_launch_exits_zero(self):
        recipe, checklist = read(RECIPE), read(CHECKLIST)
        self.assertEqual(storage_window_errors(recipe, checklist), [])
        for name in ("recipe", "checklist"):
            with self.subTest(control="old exit-zero launch proof", file=name):
                page = recipe.replace(USER_SESSION_WARNING, "launch exit 0") if name == "recipe" else recipe
                ticks = checklist.replace(USER_SESSION_WARNING, "launch exit 0") if name == "checklist" else checklist
                self.assertTrue(storage_window_errors(page, ticks))

    def test_default_and_rollback_reject_the_old_symmetric_arms(self):
        inputs = (read(RECIPE), read(RECORD), read(CHECKLIST))
        self.assertEqual(default_image_errors(*inputs), [])
        for index, text in enumerate(inputs):
            with self.subTest(control="old symmetric image arms", file=index):
                old = text + "\nBoth are symmetric provisional arms with no merit precedence.\n"
                mutant = (*inputs[:index], old, *inputs[index + 1:])
                self.assertTrue(default_image_errors(*mutant))

    def test_signature_class_rejects_unretained_output_claims(self):
        record, receipt = read(RECORD), json.loads(read(SOURCE_RECEIPT))
        self.assertEqual(signature_class_errors(record, receipt), [])
        old = record + "\nThe retained logs are each release's native-signed-sums.stdout and native-signed-sums.stderr.\n"
        self.assertTrue(signature_class_errors(old, receipt))
        old_receipt = dict(receipt, source_verification=dict(receipt['source_verification'],
                                                           evidence_class='native signature output for both releases'))
        self.assertTrue(signature_class_errors(record, old_receipt))

    def test_rootless_start_rejects_the_old_bus_only_f3(self):
        recipe, checklist = read(RECIPE), read(CHECKLIST)
        self.assertEqual(rootless_start_errors(recipe, checklist), [])
        f3 = section(recipe, "F3")
        old_f3 = f3.split("Right after the bus proof,", 1)[0]
        self.assertNotEqual(old_f3, f3)
        self.assertTrue(rootless_start_errors(recipe.replace(f3, old_f3), checklist))
        old_ticks = checklist.replace(checklist_line(checklist, "F3"),
                                      "- [ ] **F3** The bus is a socket and the user manager is running.")
        self.assertTrue(rootless_start_errors(recipe, old_ticks))


def default_image_errors(recipe: str, record: str, checklist: str) -> list[str]:
    errors = []
    for name, text in (("recipe", recipe), ("record", record), ("checklist", checklist)):
        for needed in ("single default", "26.04.1", "24.04.5", "rollback",
                       "release-caused 26.04 failure with no in-release remedy"):
            if needed not in prose(text):
                errors.append(f"the {name} lacks the default/rollback contract: {needed}")
        if "no merit precedence" in text:
            errors.append(f"the {name} still presents symmetric clean-install arms")
    return errors


def signature_class_errors(record: str, receipt: dict) -> list[str]:
    errors = []
    if "no retained verification output" not in prose(record):
        errors.append("the record does not qualify the 26.04.1 signature evidence")
    if any(name in record for name in ("native-signed-sums.stdout", "native-signed-sums.stderr")):
        errors.append("the record claims unretained signature output streams")
    evidence = field(receipt, "source_verification", "evidence_class")
    if not isinstance(evidence, str) or not all(part in evidence for part in
            ("reported", "exit codes", "fingerprint", "stream hash match", "no retained verification output")):
        errors.append("the receipt's signature class exceeds its retained reported facts")
    return errors


def rootless_start_errors(recipe: str, checklist: str) -> list[str]:
    errors = []
    info = "docker --context rootless info --format '{{json .SecurityOptions}}'"
    run = "docker --context rootless run --rm hello-world"
    blocks = step_blocks(recipe, "F3")
    if not any(info in block and run in block and block.index(info) < block.index(run) for block in blocks):
        errors.append("F3 does not prove rootless mode before starting a container as the user")
    for needed in ("owed on the first run after the WSL update", "41492", "name=rootless",
                   "failed container start", "stops the run", "before F9"):
        if needed not in prose(section(recipe, "F3")):
            errors.append(f"F3 lacks its rootless-container proof, stop or owed result: {needed}")
    if run not in checklist_line(checklist, "F3") or "owed" not in checklist_line(checklist, "F3"):
        errors.append("the checklist still accepts the bus proof without the rootless-container result")
    return errors


class AdoptedTargetTests(unittest.TestCase):
    """Change 1 of the follow-up of 2026-10-02: Host-wide rules adopt stable WSL 3.0.1 or later as policy."""

    def test_host_wide_rules_adopt_wsl_3_0_1_and_record_the_host_update(self):
        self.assertEqual(adopted_target_errors(read(RECIPE)), [])

    def test_the_check_rejects_the_pre_change_rule_a_stale_or_lost_update_sentence_and_a_misplaced_policy(self):
        recipe = read(RECIPE)
        rules = chapter(recipe, "Host-wide rules")
        mutants = {
            "pre-change rule": recipe.replace(rules, reword(rules, ADOPTED_TARGET, OLD_ADOPTED_TARGET)),
            "pre-change update sentence": recipe.replace(rules, reword(rules, HOST_UPDATE, OLD_HOST_UPDATE)),
            "update sentence lost": recipe.replace(rules, reword(rules, HOST_UPDATE, "")),
            "pre-releases adopted": recipe.replace(rules, reword(rules, "Neither pre-release is adopted:",
                                                                 "Both pre-releases are adopted:")),
            "policy outside Host-wide rules": recipe.replace(rules, reword(rules, ADOPTED_TARGET, "")).replace(
                "Start with R1", ADOPTED_TARGET + " Start with R1", 1),
        }
        for name, mutant in mutants.items():
            with self.subTest(mutant=name):
                self.assertNotEqual(mutant, recipe)
                self.assertTrue(adopted_target_errors(mutant))


class PairedIsolationTests(FollowUpCase):
    """Change 2 of the follow-up of 2026-10-02: W5 reads the same five observations from both running distributions."""

    def test_w5_pairs_the_five_observations_and_w1_holds_the_workstation_baseline(self):
        self.assertEqual(paired_isolation_errors(*self.inputs()), [])

    def test_the_check_rejects_the_pre_change_pages_a_half_pair_and_lost_records(self):
        recipe, record, checklist, receipt = self.inputs()
        w1, w5, w6 = section(recipe, "W1"), section(recipe, "W5"), section(recipe, "W6")
        block = f"```sh\n{WORKSTATION_BASELINE}\n{PAIRED_NEW}\n```\n"
        cgroup_block = "```sh\nsystemctl is-active '<COMMON_UNIT>'\n"
        self.assertIn(WORKSTATION_BASELINE + "\n", w1)
        self.assertIn(block, w5)
        self.assertIn(cgroup_block, w5)
        row = next(line for line in record.splitlines() if line.startswith(f"| W5 | sh | `{NEW_COMMANDS[0]}` |"))
        pair = receipt["paired_isolation"]
        names = [name for name, value in pair.items() if isinstance(value, dict)]
        host = {key: value for key, value in receipt["host"].items() if key != "workstation_baseline"}
        page = lambda old_w5: recipe.replace(w5, old_w5)  # noqa: E731
        self.assert_mutants_fail(paired_isolation_errors, {
            "pre-change W1": (recipe.replace(w1, w1.replace(WORKSTATION_BASELINE, OLD_NAMESPACE_READ)), record, checklist,
                              receipt),
            "pre-change W5": (page(w5.replace(block, "")), record, checklist, receipt),
            "the workstation's line only": (page(w5.replace(block, f"```sh\n{WORKSTATION_BASELINE}\n```\n")), record,
                                            checklist, receipt),
            "the new distribution's line only": (page(w5.replace(block, f"```sh\n{PAIRED_NEW}\n```\n")), record, checklist,
                                                 receipt),
            "lines in the wrong order": (page(w5.replace(block, f"```sh\n{PAIRED_NEW}\n{WORKSTATION_BASELINE}\n```\n")),
                                         record, checklist, receipt),
            "lines in two blocks": (page(w5.replace(block, f"```sh\n{WORKSTATION_BASELINE}\n```\n\n```sh\n{PAIRED_NEW}\n```\n")),
                                    record, checklist, receipt),
            "before the cgroup block": (page(w5.replace(block, "").replace(cgroup_block, block + "\n" + cgroup_block, 1)),
                                        record, checklist, receipt),
            "no five keys in the proof": (page(reword(w5, "each with `uid`, `system_state`, `failed_units`, "
                                                          "`user_manager` and `cgroup_namespace`", "each with its values")),
                                          record, checklist, receipt),
            "no comparison with W1": (page(reword(w5, "equal its own values recorded in W1 before the import",
                                                  "are healthy")), record, checklist, receipt),
            "no namespace comparison": (page(reword(w5, "differ from each other and neither is `cgroup:[4026531835]`",
                                                    "are printed")), record, checklist, receipt),
            "no version, kernel or image record": (page(reword(w5, "with the WSL version and kernel from W1 and the image "
                                                                   "revision from W2,", "")), record, checklist, receipt),
            "W6 without the paired record": (recipe.replace(w6, reword(w6, "Repeat W5's cgroup-isolation proof and its "
                                                                           "paired record", "Repeat W5's cgroup-isolation "
                                                                           "proof")), record, checklist, receipt),
            "record without the row": (recipe, record.replace(row + "\n", ""), checklist, receipt),
            "checklist without the baseline": (recipe, record, checklist.replace(
                checklist_line(checklist, "W1"), "- [ ] **W1** WSL 3.0.1 or later is recorded."), receipt),
            "checklist without the pair": (recipe, record, checklist.replace("paired_isolation", "the receipt"), receipt),
            "no receipt key": (recipe, record, checklist, without(receipt, "paired_isolation")),
            "one distribution in the receipt": (recipe, record, checklist,
                                                dict(receipt, paired_isolation={key: value for key, value in pair.items()
                                                                                if key != names[1]})),
            "a lost key in the receipt": (recipe, record, checklist, dict(receipt, paired_isolation=dict(
                pair, **{names[1]: {key: value for key, value in pair[names[1]].items() if key != "uid"}}))),
            "pre-change receipt host": (recipe, record, checklist, dict(receipt, host=dict(
                host, cgroup_namespace="<W1: actual readlink /proc/1/ns/cgroup output in the already-running distribution>"))),
        })


class BinfmtUnitTests(FollowUpCase):
    """Change 3 of the follow-up of 2026-10-02: F1 accepts `degraded` only for systemd-binfmt.service, the by-design failure."""

    def test_f1_accepts_degraded_only_with_the_binfmt_unit_as_the_single_failed_unit(self):
        self.assertEqual(binfmt_unit_errors(*self.inputs()), [])

    def test_the_check_rejects_the_old_f1_any_degraded_state_and_lost_references(self):
        recipe, record, checklist, receipt = self.inputs()
        f1, overturn = section(recipe, "F1"), chapter(record, "Overturn condition")
        for line in (F1_FAILED, F1_LOG):
            self.assertIn(line + "\n", f1)
        log_row = next(line for line in record.splitlines() if line.startswith("| F1 | sh | `journalctl -b 0 -t "))
        pass_rule = f"Proof: `running` with no failed unit, or {F1_PASS} `{FLUSH_MESSAGE}`;"
        first = next(entry for entry in receipt["steps"] if entry["step"] == "F1"
                     and entry["cmd"] == "systemctl is-system-running --wait")
        old_steps = [dict(entry, exit=0, output_excerpt="running") if entry is first else entry
                     for entry in receipt["steps"]]
        old_arms = {name: dict(arm, first_boot=arm["first_boot"].replace("F1's pass condition", "F1 running")) for name, arm in
                    receipt["comparison_arms"].items()}
        page = lambda new_f1: (recipe.replace(f1, new_f1), record, checklist, receipt)  # noqa: E731
        self.assert_mutants_fail(binfmt_unit_errors, {
            "pre-change F1": page(f1[:f1.index("```sh")] + OLD_F1),
            "any degraded state passes": page(reword(f1, pass_rule, "Proof: `running` or `degraded`;")),
            "no single-unit condition": page(reword(f1, "lists exactly `systemd-binfmt.service`", "lists a failed unit")),
            "no log condition": page(reword(f1, "that unit's log, from the `journalctl` line, holds", "it holds")),
            "other failed units pass": page(reword(f1, "Any other failed unit stops the run",
                                                   "Another failed unit is recorded")),
            "no flush message": page(f1.replace(FLUSH_MESSAGE, "the message")),
            "no pull request": page(f1.replace(BINFMT_PR, "https://example.invalid/pull")),
            "no issue": page(f1.replace(BINFMT_ISSUE, "https://example.invalid/issue")),
            "no upstream quote": page(reword(f1, BINFMT_BENIGN, "It is fine.")),
            "no journal command": page(f1.replace(F1_LOG + "\n", "")),
            "failed units without --plain": page(f1.replace(F1_FAILED + "\n", "systemctl --failed --no-legend\n")),
            "journal read before the failed list": page(f1.replace(F1_FAILED + "\n" + F1_LOG + "\n",
                                                                    F1_LOG + "\n" + F1_FAILED + "\n")),
            "no adm statement": page(f1.replace("`adm`", "`wheel`")),
            "no sudo fallback for an unreadable journal": page(reword(f1, F1_SUDO_FALLBACK, "")),
            "a stop at the journal notice, even on running": page(reword(
                f1, F1_SUDO_FALLBACK, "A `Hint: You are currently not seeing messages from other users and the system.` "
                                      "notice or `-- No entries --` means it cannot: record it and stop for review.")),
            "old overturn condition": (recipe, record.replace(overturn, reword(
                overturn, "F1 reports `degraded` with a failed unit other than `systemd-binfmt.service`, or without that "
                          "unit's read-only flush message, on a clean run;", "F1 reports `degraded` on a clean run;")),
                                       checklist, receipt),
            "record without the journal row": (recipe, record.replace(log_row + "\n", ""), checklist, receipt),
            "record without the pull request": (recipe, record.replace(BINFMT_PR, "https://example.invalid/pull"), checklist,
                                                receipt),
            "checklist with the old F1": (recipe, record, checklist.replace(
                checklist_line(checklist, "F1"), "- [ ] **F1** `systemctl is-system-running --wait` prints `running`; "
                                                 "no failed unit."), receipt),
            "receipt with a fixed running": (recipe, record, checklist, dict(receipt, steps=old_steps)),
            "arms that still read running": (recipe, record, checklist, dict(receipt, comparison_arms=old_arms)),
        })


class BinfmtRecoveryTests(FollowUpCase):
    """Change 3 of the follow-up of 2026-10-02: the interop recovery stops for review; nothing restarts systemd-binfmt."""

    def test_no_recipe_command_controls_the_unit_and_r1_stops_for_review_with_two_records(self):
        self.assertEqual(binfmt_recovery_errors(*self.inputs()), [])

    def test_a_history_sentence_may_name_the_restart_but_a_command_block_may_not(self):
        recipe = read(RECIPE)
        self.assertIn("`sudo systemctl restart systemd-binfmt` there restored it", prose(section(recipe, "R1")))
        self.assertEqual([command for _, command in fenced_commands(recipe) if UNIT_CONTROL_RE.search(command)], [])
        for command in (RESTART_UNIT, "sudo systemctl start systemd-binfmt.service", "systemctl stop systemd-binfmt",
                        "sudo systemctl try-restart systemd-binfmt.service"):
            with self.subTest(command=command):
                self.assertTrue(UNIT_CONTROL_RE.search(command))
        for command in (*INTEROP_RECORDS, F1_FAILED, F1_LOG):
            with self.subTest(command=command):
                self.assertFalse(UNIT_CONTROL_RE.search(command))

    def test_the_check_rejects_the_old_restart_recovery_and_a_lost_record_or_stop(self):
        recipe, record, checklist, receipt = self.inputs()
        r1, w6, decision = section(recipe, "R1"), section(recipe, "W6"), chapter(record, "Decision")
        block = "\n".join([NATIVE_INTEROP, *INTEROP_RECORDS]) + "\n"
        self.assertIn("```sh\n" + block + "```\n", r1)
        native_row = next(line for line in record.splitlines() if line.startswith(f"| R1 | sh | `{NATIVE_INTEROP}` |"))
        old_row = f"| R1 | sh | `{RESTART_UNIT.replace('|', chr(92) + '|')}` | only after removal, on the survivor: exit 0; " \
                  "failure stops recovery |"
        new_checklist = {"R1": (", and when either check fails R1's records (`ls /proc/sys/fs/binfmt_misc` and "
                                "`systemctl status systemd-binfmt.service --no-pager`) are kept and the run stops for review, "
                                "importing or provisioning nothing"),
                         "W6": ", and when either check fails R1's records are kept and the run stops for review with no import"}
        old_checklist = ", with R1's `sudo systemctl restart systemd-binfmt` recovery if needed and a stop if either check " \
                        "still fails"
        for step, fragment in new_checklist.items():
            self.assertIn(fragment, checklist_line(checklist, step))
        new_decision = ("If registration or Windows execution does not return, the run stops for review after the new "
                        "distribution is removed, with `ls /proc/sys/fs/binfmt_misc` and `systemctl status "
                        "systemd-binfmt.service --no-pager` recorded; nothing is imported or provisioned. The WSL 2.7.x "
                        "remedy, restarting `systemd-binfmt`, is not used on the adopted release, where that restart exits 1.")
        old_decision = ("R1's supported `sudo systemctl restart systemd-binfmt` recovery runs only after the new distribution "
                        "is removed; if registration or Windows execution does not return, the run stops.")
        new_w6 = ("If the guard throws, do not import: take R1's interop recovery there, which records the observations and "
                  "stops for review.")
        old_w6 = ("If the guard throws, run R1's interop recovery there and repeat both observations before resuming at "
                  "`--import`; if interop does not return, stop.")
        old_interop = ("<R1/W5/W6: after each actual unregister, surviving WSLInterop exists and /mnt/c/Windows/System32/"
                       "cmd.exe /d /c ver launches; record any systemd-binfmt recovery and repeat observations; failure "
                       "stops>")
        moved = r1.replace("```sh\n" + block + "```\n", "").replace("\n\n", "\n\n```sh\n" + block + "```\n\n", 1)
        page = lambda new_r1: (recipe.replace(r1, new_r1), record, checklist, receipt)  # noqa: E731
        self.assert_mutants_fail(binfmt_recovery_errors, {
            "the old restart recovery": page(r1.replace(block, OLD_INTEROP_RECOVERY)),
            "the restart beside the records": page(r1.replace(block, RESTART_UNIT + "\n" + block)),
            "a restart in another step": (recipe.replace("```sh\n" + GETTY_MASK + "\n", "```sh\nsudo systemctl restart "
                                                         "systemd-binfmt\n" + GETTY_MASK + "\n", 1), record, checklist,
                                          receipt),
            "a start beside the records": page(r1.replace(block, block + "sudo systemctl start systemd-binfmt.service\n")),
            "no listing of the formats": page(r1.replace(INTEROP_RECORDS[0] + "\n", "")),
            "no status of the unit": page(r1.replace(INTEROP_RECORDS[1] + "\n", "")),
            "records in the wrong order": page(r1.replace("\n".join(INTEROP_RECORDS) + "\n",
                                                          "\n".join(reversed(INTEROP_RECORDS)) + "\n")),
            "records before the interop checks": page(moved),
            "no stop for review": page(reword(r1, "then stop for review", "then continue")),
            "another distribution may be imported": page(reword(r1, "stop, do not import or provision another distribution, "
                                                                    "and record", "stop and record")),
            "no history of the 2.7.13 loss": page(reword(r1, "On WSL 2.7.13 the rehearsal's unregister removed this VM-wide "
                                                             "registration on the surviving distribution, and `sudo "
                                                             "systemctl restart systemd-binfmt` there restored it.", "")),
            "W6 resumes after the recovery": (recipe.replace(w6, reword(w6, new_w6, old_w6)), record, checklist, receipt),
            "R1 checklist with the restart": (recipe, record, checklist.replace(new_checklist["R1"], old_checklist), receipt),
            "W6 checklist with the restart": (recipe, record, checklist.replace(new_checklist["W6"], old_checklist), receipt),
            "record with the restart row": (recipe, record.replace(native_row, native_row + "\n" + old_row), checklist,
                                            receipt),
            "record decision with the restart": (recipe, record.replace(decision, reword(decision, new_decision,
                                                                                           old_decision)), checklist, receipt),
            "receipt with the old recovery note": (recipe, record, checklist, dict(receipt, interop_after_unregister=old_interop)),
        })


ORIGINAL_QUALITY_RULE = (
    "Both 26.04.1 trial and 24.04.5 fallback are symmetric provisional arms with no merit precedence. "
    "Preregister the same separate-throwaway R1 comparisons on one unchanged host/kernel/driver, checkout, "
    "user-data and bootstrap profile. Both signed sums pass P1; P2 workstation schema is not image qualification. "
    "W2 hashes the whole selected image against its exact signed/catalog release mapping; W4/W6 use that filename. "
    "Each arm must record first_boot (W5 default uid 1000, retained results, selected-image cloud-init version/schema "
    "and F1 running); systemd_user_from_second_instance (F2 linger/idle and F3 directory/socket ownership plus manager "
    "running from the workstation second instance); wsl_gpu (/dev/dxg and native nvidia-smi visibility on the same "
    "Windows driver); uv_cpython_3_13 (separate managed Python 3.13.x through uv); node_24 (bootstrap v24.21.0 startup). "
    "Preserve P3 age/baseline, W5 second count, W7 owner 1000:1000 and failed-rehearsal/W6 export-before-unregister "
    "guards. Missing, failed or skipped criteria do not qualify an arm or rank its peer. Record sanitized native "
    "per-arm output before selecting within the measured host scope. Full-stack, GPU-workload and model acceptance "
    "remain separate and unrun."
)
FIRST_QUALITY_AMENDMENT = (
    "; amended on 2026-10-02 before any comparison ran: on WSL 3.0.1 the criterion is F1's pass condition, running, "
    "or degraded with systemd-binfmt.service as the only failed unit, which fails by design there"
)
QUALITY_AMENDMENT_RE = re.compile(r"; amended on 2026-10-02 .*?(?=; amended on 2026-10-02 |\); "
                                  r"systemd_user_from_second_instance)")
BASELINE_STOP_PARTS = (
    "The workstation's baseline passes only when all four hold:",
    "its uid equals the new distribution's planned default uid `1000`",
    "its system state is `running` with no failed unit, or `degraded` with its failed set contained in "
    "{`systemd-binfmt.service`, `getty@tty1.service`}",
    "its user manager is `active`",
    "its cgroup namespace is not `cgroup:[4026531835]`",
    "Anything else stops the run before W4 and before any W6 import",
)
BASELINE_STOP_RE = re.compile(r"^- The workstation's baseline passes.*?(?=^- |^```|\Z)", re.M | re.S)
LINUX_ENTRIES = (
    '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass '
    '-File "$(wslpath -w step.ps1)"',
    "/mnt/c/Windows/System32/wsl.exe -d <Name>",
    "/mnt/c/Windows/System32/wsl.exe -d <Name> -- bash -s < steps.sh",
    "/mnt/c/Windows/System32/wsl.exe -d <Name> -u root",
    "/mnt/c/Windows/System32/wsl.exe -d <Name> -u root -- bash -s < path-b.sh",
)


def quality_rule_errors(experiment: dict) -> list[str]:
    """Keep the full original preregistration and the first amendment; remove only the two dated amendments."""
    rule = field(experiment, "predeclared_metrics", "quality_rule")
    if not isinstance(rule, str):
        return ["quality_rule is not text"]
    retained, count = QUALITY_AMENDMENT_RE.subn("", rule)
    errors = []
    if retained != ORIGINAL_QUALITY_RULE:
        errors.append("the quality rule outside its dated amendments differs from the full original wording")
    if count != 2 or rule.count(FIRST_QUALITY_AMENDMENT) != 1:
        errors.append("the quality rule must retain the first amendment and exactly one further dated amendment")
    amendments = QUALITY_AMENDMENT_RE.findall(rule)
    if len(amendments) != 2 or "F1's complete pass condition" not in amendments[-1] or FLUSH_MESSAGE not in amendments[-1]:
        errors.append("the second amendment must interpret the first short form as F1's complete pass condition")
    return errors


def workstation_stop_errors(recipe: str) -> list[str]:
    """W1 must reject every incompatible baseline before any install or import, in its own stop paragraph."""
    w1 = section(recipe, "W1")
    paragraph = BASELINE_STOP_RE.search(w1)
    stop = prose(paragraph.group(0)) if paragraph else ""
    errors = [f"W1's baseline stop lacks: {part}" for part in BASELINE_STOP_PARTS if part not in stop]
    for part in ("leftover of an earlier collision", "`Result=start-limit-hit` is required",
                 "another result stops the run", "`getty_tty1_result`"):
        if part not in prose(w1):
            errors.append(f"W1 lacks the conditional getty baseline proof: {part}")
    if ("sh", GETTY_RESULT) not in step_commands(recipe, "W1"):
        errors.append("W1 lacks the extra read-only command for an already failed getty")
    return errors


def receipt_baseline_errors(receipt: dict) -> list[str]:
    """Each of the five workstation instructions must require equality to its own W1 baseline."""
    workstation = field(receipt, "paired_isolation", "workstation")
    return [f"workstation {key} does not require equality to host.workstation_baseline" for key in sorted(ISOLATION_KEYS)
            if not is_placeholder(field(workstation, key), "<W5") or
            "equal to host.workstation_baseline" not in str(field(workstation, key))]


def separate_observation_errors(recipe: str, record: str, checklist: str, receipt: dict) -> list[str]:
    """Commands and receipt entries retain each observation's exit; no compound or tail pipeline hides it."""
    errors = []
    if WORKSTATION_COMMANDS not in step_blocks(recipe, "W1"):
        errors.append("W1 must hold five native commands on five lines")
    if WORKSTATION_COMMANDS + NEW_COMMANDS not in step_blocks(recipe, "W5"):
        errors.append("W5 must hold five commands per distribution on ten lines")
    if [command for _, command in fenced_commands(checklist)] != (
            WORKSTATION_COMMANDS + WORKSTATION_COMMANDS + NEW_COMMANDS):
        errors.append("the checklist must repeat W1's five commands and W5's two halves separately")
    table = Counter(command_table(record))
    entries = Counter((entry.get("step"), entry.get("cmd")) for entry in receipt.get("steps", []))
    for step, commands in (("W1", WORKSTATION_COMMANDS), ("W5", WORKSTATION_COMMANDS + NEW_COMMANDS)):
        for command in commands:
            expected = 2 if step == "W5" and command == USER_MANAGER_ACTIVE else 1
            if table[(step, "sh", command)] != expected or entries[(step, command)] != expected:
                errors.append(f"{step} must record each occurrence of {command} in the table and receipt")
    texts = (recipe, checklist, json.dumps(receipt), "\n".join(command for _, _, command in command_table(record)))
    for text in texts:
        if "id -u; systemctl is-system-running;" in text or "| tail -n 4" in text:
            errors.append("an operational command still hides exits in the old compound or journal pipeline")
    return errors


def storage_filter_errors(recipe: str, record: str, receipt: dict) -> list[str]:
    """All three operational filters exclude registration and both forms of the kernel's command-line echo."""
    expected = Counter({STORVSC_COUNT: 2, STORVSC_NEWEST: 1})
    inventories = ([command for _, _, command in recipe_rows(recipe)],
                   [command for _, _, command in command_table(record)],
                   [entry.get("cmd", "") for entry in receipt.get("steps", [])])
    errors = []
    for commands in inventories:
        filters = [command for command in commands if "grep hv_storvsc" in command]
        if Counter(filters) != expected:
            errors.append("the operational inventory does not hold exactly the three corrected hv_storvsc filters")
    return errors


def getty_proof_errors(recipe: str, record: str, receipt: dict) -> list[str]:
    errors = []
    for command in (GETTY_ENABLED, GETTY_SHOW):
        if ("powershell", command) not in step_commands(recipe, "W5") or (
                "W5", "powershell", command) not in command_table(record):
            errors.append(f"W5 or the command table lacks {command}")
    roots = [block for block in step_blocks(recipe, "W6") if any(line.startswith("id -u '<WSL_USER>'") for line in block)]
    if len(roots) != 1 or roots[0][:1] != [GETTY_MASK]:
        errors.append("W6's root block must start with the getty mask")
    for part in ("`masked`", "exit 1", "`LoadState=masked`", "`ActiveState=inactive`", "`NRestarts=0`",
                 "refused job of a masked unit"):
        if part not in prose(section(recipe, "W5")):
            errors.append(f"W5 lacks its getty proof: {part}")
    if "starts the getty before the first line below can run" not in prose(section(recipe, "W6")):
        errors.append("W6 must state the import's first-boot ordering limitation")
    values = field(receipt, "first_launch", "getty_mask")
    for key, part in (("is_enabled", "masked"), ("load_state", "LoadState=masked"),
                      ("active_state", "ActiveState=inactive"), ("n_restarts", "NRestarts=0")):
        if not is_placeholder(field(values, key), "<W5") or part not in str(field(values, key)):
            errors.append(f"the receipt lacks the getty_mask.{key} proof")
    return errors


def w5_recovery_errors(recipe: str, record: str, checklist: str, receipt: dict) -> list[str]:
    errors = []
    for text in (recipe, record, checklist, json.dumps(receipt)):
        if "cgroup" + "_failure_export" in text or "<Name>-cgroup" + "-failed.tar" in text:
            errors.append("an old W5 recovery name remains")
    w5 = prose(section(recipe, "W5"))
    for part in ("When any W5 proof fails", "Do not take path B for any such failure", "`w5_failure_export`",
                 "`cgroup`, `tty` or a short text", "this recovery block serves every failed W5 proof"):
        if part not in w5:
            errors.append(f"W5's recovery lacks: {part}")
    export = field(receipt, "w5_failure_export")
    if not isinstance(export, dict) or set(export) != {"file", "sha256", "bytes", "cause"}:
        errors.append("w5_failure_export lacks file, sha256, bytes or cause")
    elif "<Name>-w5-failed.tar" not in str(export["file"]) or not all(part in str(export["cause"]) for part in
                                                                          ("cgroup", "tty", "short text")):
        errors.append("w5_failure_export does not name the recovery file and its possible causes")
    return errors


def linux_entry_errors(recipe: str) -> list[str]:
    errors = [f"the Linux entry lacks its full Windows path: {command}" for command in LINUX_ENTRIES
              if "`" + command + "`" not in recipe]
    inline = re.findall(r"`([^`\n]*)`", recipe)
    if any(command.startswith("powershell.exe -NoProfile") or (command.startswith("wsl.exe -d <Name>") and
            ("bash -s" in command or "-u root" in command)) for command in inline):
        errors.append("a Linux entry starts a Windows program by a bare name")
    if any(shell == "sh" and re.match(r"(?:wsl|powershell)\.exe\b", command)
           for shell, command in fenced_commands(recipe)):
        errors.append("an sh block starts a Windows program by a bare name")
    return errors


def release_size_errors(recipe: str, receipt: dict) -> list[str]:
    row = next((line for line in recipe.splitlines() if line.startswith("| 26.04.1 |")), "")
    errors = []
    if "418,495,746; rehearsal run 2, 2026-10-02" not in row:
        errors.append("the release table lacks run 2's observed 26.04.1 size")
    if field(receipt, "supported_images", "26.04.1", "bytes") != 418495746:
        errors.append("the receipt's supported image size does not match run 2")
    return errors


class Run2RepairTests(FollowUpCase):
    """The accepted PR #593 repair; every test asserts the new contract before trying a pre-change mutation."""

    def test_bootcmd_is_exact_and_the_template_has_only_the_wsl_user_placeholder(self):
        template = read(USER_DATA)
        self.assertEqual(user_data_errors(template), [])
        self.assertEqual(set(string.Template(template).get_identifiers()), {"WSL_USER"})
        self.assertEqual(string.Template(template).substitute(WSL_USER="example"), template.replace(PLACEHOLDER, "example"))
        for old in (template.replace(GETTY_BOOTCMD, ""), template.replace("mask, --now", "mask"),
                    template + "# ${OTHER_USER}\n"):
            with self.subTest(control="old or incorrect bootcmd"):
                self.assertNotEqual(old, template)
                self.assertTrue(user_data_errors(old))

    def test_observations_are_separate_in_page_checklist_receipt_and_table(self):
        inputs = self.inputs()
        self.assertEqual(separate_observation_errors(*inputs), [])
        recipe, record, checklist, receipt = inputs
        for step, commands in (("W1", WORKSTATION_COMMANDS), ("W5", WORKSTATION_COMMANDS + NEW_COMMANDS)):
            for command in commands:
                with self.subTest(control="lost separate observation", step=step, command=command):
                    current = WORKSTATION_BASELINE if step == "W1" else WORKSTATION_BASELINE + "\n" + PAIRED_NEW
                    removed = re.sub(r"^" + re.escape(command) + r"\n", "", current + "\n", count=1, flags=re.M)
                    old = section(recipe, step).replace(current + "\n", removed, 1)
                    self.assertTrue(separate_observation_errors(recipe.replace(section(recipe, step), old), record,
                                                                checklist, receipt))
        self.assertTrue(separate_observation_errors(recipe, record, checklist.replace(WORKSTATION_BASELINE, "id -u; "
                                                    "systemctl is-system-running; " + NAMESPACE_READ), receipt))
        for step, command in (("W1", WORKSTATION_COMMANDS[1]), ("W5", NEW_COMMANDS[1])):
            row = next(line for line in record.splitlines() if line.startswith(f"| {step} | sh | `{command}` |"))
            self.assertTrue(separate_observation_errors(recipe, record.replace(row + "\n", ""), checklist, receipt))
            self.assertTrue(separate_observation_errors(recipe, record, checklist, dict(receipt, steps=[entry for entry in
                            receipt["steps"] if (entry["step"], entry["cmd"]) != (step, command)])))

    def test_w1_stop_paragraph_is_required(self):
        recipe = read(RECIPE)
        self.assertEqual(workstation_stop_errors(recipe), [])
        self.assertTrue(workstation_stop_errors(BASELINE_STOP_RE.sub("", recipe)))

    def test_w1_stop_requires_the_uid_1000_condition(self):
        recipe = read(RECIPE)
        self.assertEqual(workstation_stop_errors(recipe), [])
        self.assertTrue(workstation_stop_errors(reword(recipe, BASELINE_STOP_PARTS[1], "")))

    def test_w1_stop_requires_a_noninitial_namespace(self):
        recipe = read(RECIPE)
        self.assertEqual(workstation_stop_errors(recipe), [])
        self.assertTrue(workstation_stop_errors(reword(recipe, BASELINE_STOP_PARTS[4], "")))

    def test_w1_stop_requires_an_active_user_manager(self):
        recipe = read(RECIPE)
        self.assertEqual(workstation_stop_errors(recipe), [])
        self.assertTrue(workstation_stop_errors(reword(recipe, BASELINE_STOP_PARTS[3], "")))

    def test_w1_stop_requires_the_system_state_and_conditional_getty_result(self):
        recipe = read(RECIPE)
        self.assertEqual(workstation_stop_errors(recipe), [])
        for part in (BASELINE_STOP_PARTS[2], "`Result=start-limit-hit` is required", "another result stops the run"):
            with self.subTest(control=part):
                self.assertTrue(workstation_stop_errors(reword(recipe, part, "")))
        self.assertTrue(workstation_stop_errors(recipe.replace(GETTY_RESULT + "\n", "")))

    def test_all_five_receipt_instructions_require_the_workstation_baseline(self):
        receipt = json.loads(read(RECEIPT_EXAMPLE))
        self.assertEqual(receipt_baseline_errors(receipt), [])
        for key in sorted(ISOLATION_KEYS):
            with self.subTest(control="weakened baseline equality", key=key):
                old = json.loads(json.dumps(receipt))
                value = old["paired_isolation"]["workstation"][key]
                old["paired_isolation"]["workstation"][key] = value.replace("equal to host.workstation_baseline", "recorded")
                self.assertEqual(len(receipt_baseline_errors(old)), 1)

    def test_checklist_f1_requires_the_read_only_flush_message(self):
        inputs = self.inputs()
        self.assertEqual(binfmt_unit_errors(*inputs), [])
        recipe, record, checklist, receipt = inputs
        old = checklist.replace(FLUSH_MESSAGE, "any message is accepted")
        self.assertNotEqual(old, checklist)
        self.assertTrue(binfmt_unit_errors(recipe, record, old, receipt))

    def test_quality_rule_retains_every_original_word_and_the_first_amendment(self):
        experiment = json.loads(read(EXPERIMENT))
        self.assertEqual(quality_rule_errors(experiment), [])
        rule = experiment["predeclared_metrics"]["quality_rule"]
        controls = ("no merit precedence", rule.replace("and F1 running", "and any state"),
                    rule.replace(FIRST_QUALITY_AMENDMENT, ""), QUALITY_AMENDMENT_RE.sub("", rule),
                    rule.replace(FLUSH_MESSAGE, "any message"))
        for old in controls:
            with self.subTest(control="original or amendment weakened"):
                mutant = dict(experiment, predeclared_metrics=dict(experiment["predeclared_metrics"], quality_rule=old))
                self.assertTrue(quality_rule_errors(mutant))

    def test_all_three_storage_filters_exclude_the_command_line_echo(self):
        recipe, record, _, receipt = self.inputs()
        self.assertEqual(storage_filter_errors(recipe, record, receipt), [])
        rows = [(step, command) for step, _, command in recipe_rows(recipe) if "grep hv_storvsc" in command]
        self.assertEqual(len(rows), 3)
        for step, command in rows:
            with self.subTest(control="pre-change filter", step=step, command=command):
                old_filter = command.replace("grep -Ev", "grep -v").replace("|[Cc]ommand line:", "")
                old = section(recipe, step).replace(command, old_filter, 1)
                self.assertTrue(storage_filter_errors(recipe.replace(section(recipe, step), old), record, receipt))

    def test_w5_getty_proofs_are_commands_and_command_table_rows(self):
        recipe, record, _, receipt = self.inputs()
        self.assertEqual(getty_proof_errors(recipe, record, receipt), [])
        for command in (GETTY_ENABLED, GETTY_SHOW):
            with self.subTest(control="lost getty command or row", command=command):
                self.assertTrue(getty_proof_errors(recipe.replace(command + "\n", ""), record, receipt))
                row = next(line for line in record.splitlines() if line.startswith(f"| W5 | powershell | `{command}` |"))
                self.assertTrue(getty_proof_errors(recipe, record.replace(row + "\n", ""), receipt))

    def test_w6_root_block_starts_with_the_getty_mask(self):
        recipe, record, _, receipt = self.inputs()
        self.assertEqual(getty_proof_errors(recipe, record, receipt), [])
        self.assertTrue(getty_proof_errors(recipe.replace(GETTY_MASK + "\n", ""), record, receipt))
        w6 = section(recipe, "W6")
        old = w6.replace(GETTY_MASK + "\n", "").replace("touch /etc/cloud/cloud-init.disabled\n",
                                                         "touch /etc/cloud/cloud-init.disabled\n" + GETTY_MASK + "\n")
        self.assertTrue(getty_proof_errors(recipe.replace(w6, old), record, receipt))

    def test_recovery_uses_the_w5_filename_key_and_cause_for_every_failure(self):
        inputs = self.inputs()
        self.assertEqual(w5_recovery_errors(*inputs), [])
        recipe, record, checklist, receipt = inputs
        old_file = "<Name>-cgroup" + "-failed.tar"
        for index, text in enumerate((recipe, record, checklist)):
            old = text.replace("<Name>-w5-failed.tar", old_file)
            self.assertNotEqual(old, text)
            self.assertTrue(w5_recovery_errors(*((*inputs[:index], old, *inputs[index + 1:]))))
        old = json.loads(json.dumps(receipt))
        old["cgroup" + "_failure_export"] = old.pop("w5_failure_export")
        self.assertTrue(w5_recovery_errors(recipe, record, checklist, old))
        self.assertTrue(w5_recovery_errors(recipe, record, checklist, without(receipt, "w5_failure_export", "cause")))
        self.assertTrue(w5_recovery_errors(reword(recipe, "Do not take path B for any such failure", "Take path B"),
                                           record, checklist, receipt))

    def test_linux_entry_commands_use_full_windows_paths(self):
        recipe = read(RECIPE)
        self.assertEqual(linux_entry_errors(recipe), [])
        for command in LINUX_ENTRIES:
            with self.subTest(command=command):
                self.assertIn("`" + command + "`", recipe)
                old = recipe.replace("`" + command + "`", "`" + command.rsplit("/", 1)[-1] + "`", 1)
                self.assertTrue(linux_entry_errors(old))

    def test_f10_quotes_each_path_without_word_splitting(self):
        recipe, record, _, receipt = self.inputs()
        self.assertEqual(path_proof_errors(recipe), [])
        self.assertIn(("F10", "powershell", F10_PROBE), command_table(record))
        self.assertTrue(any(entry["step"] == "F10" and entry["cmd"] == F10_PROBE for entry in receipt["steps"]))
        for old_probe in (F10_PROBE.replace("[[ -f $p && -x $p ]]", "test -f $p && test -x $p"),
                          F10_PROBE.replace("for n in claude codex; do p=$(type -P $n);", "for p in $(type -P claude codex); do")):
            self.assertTrue(path_proof_errors(recipe.replace(F10_PROBE, old_probe)))

    def test_no_powershell_command_hands_wsl_an_argument_with_a_double_quote(self):
        recipe, record, _, receipt = self.inputs()
        self.assertEqual(powershell_quote_errors(recipe), [])
        # the two forms that failed in rehearsal run 3 must be caught
        quoted_stat = "wsl.exe -d '<Name>' --exec bash -lc 'stat -c \"%U %F\" \"/run/user/$(id -u)\" \"/run/user/$(id -u)/bus\"'"
        quoted_loop = ("wsl.exe -d '<Name>' -u '<WSL_USER>' --exec /bin/bash -lc 'for n in claude codex; do p=\"$(type -P \"$n\")\"; "
                       "test -f \"$p\" && test -x \"$p\" && echo \"executable: $p\"; done'")
        self.assertIn(R1_BUS_PROBE, recipe)
        self.assertTrue(powershell_quote_errors(recipe.replace(R1_BUS_PROBE, quoted_stat)))
        self.assertTrue(powershell_quote_errors(recipe.replace(F10_PROBE, quoted_loop)))
        self.assertIn(("R1", "powershell", R1_BUS_PROBE), command_table(record))
        self.assertTrue(any(entry["cmd"] == R1_BUS_PROBE for entry in receipt["steps"]))

    def test_f5_adds_a_range_only_when_none_exists(self):
        recipe, record, _, receipt = self.inputs()
        f5 = [command for step, _, command in recipe_rows(recipe) if step == "F5"]
        self.assertIn(F5_GUARDED, f5)
        self.assertNotIn(F5_GUARDED.split(" || ", 1)[1], f5, "the unguarded usermod line would add a second range")
        self.assertIn(("F5", "sh", F5_GUARDED), command_table(record))
        self.assertTrue(any(entry["step"] == "F5" and entry["cmd"] == F5_GUARDED for entry in receipt["steps"]))

    def test_release_table_and_receipt_hold_the_observed_image_size(self):
        recipe, _, _, receipt = self.inputs()
        self.assertEqual(release_size_errors(recipe, receipt), [])
        row = next(line for line in recipe.splitlines() if line.startswith("| 26.04.1 |"))
        self.assertIn("418,495,746; rehearsal run 2, 2026-10-02", row)
        self.assertEqual(receipt["supported_images"]["26.04.1"]["bytes"], 418495746)
        self.assertTrue(release_size_errors(recipe.replace(row, row.replace("418,495,746", "unknown")), receipt))
        old = json.loads(json.dumps(receipt))
        old["supported_images"]["26.04.1"]["bytes"] = None
        self.assertTrue(release_size_errors(recipe, old))

    def test_receipt_new_keys_validate_and_the_getty_baseline_key_is_optional(self):
        recipe, record, checklist, receipt = self.inputs()
        components = {component["id"] for component in json.loads(read(STACK))["components"]}
        self.assertEqual(receipt_errors(receipt, recipe, components), [])
        self.assertEqual(getty_proof_errors(recipe, record, receipt), [])
        self.assertEqual(paired_isolation_errors(recipe, record, checklist, receipt), [])
        optional = without(receipt, "host", "workstation_baseline", "getty_tty1_result")
        self.assertEqual(receipt_errors(optional, recipe, components), [])
        self.assertEqual(paired_isolation_errors(recipe, record, checklist, optional), [])
        for key in ("is_enabled", "load_state", "active_state", "n_restarts"):
            with self.subTest(control="lost mask key", key=key):
                self.assertTrue(receipt_errors(without(receipt, "first_launch", "getty_mask", key), recipe, components))
        self.assertTrue(receipt_errors(without(receipt, "w5_failure_export", "cause"), recipe, components))
        old = json.loads(json.dumps(receipt))
        old["host"]["workstation_baseline"]["getty_tty1_result"] = "<W1: always record it>"
        self.assertTrue(receipt_errors(old, recipe, components))


if __name__ == "__main__":
    unittest.main()
