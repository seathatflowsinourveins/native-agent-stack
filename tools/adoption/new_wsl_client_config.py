#!/usr/bin/env python3
"""Configure Claude Code and Codex on the new WSL distribution from the definitive manifest. Stdlib only.

The new distribution is built by the recipe (adoption/platforms/linux-wsl2-new-distro.md) and the install plan
(evidence/artifacts/new-wsl-install-plan-20261002/), which installs the owners that the definitive manifest
(evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json) installs by default. This tool
configures the two clients for that distribution, and the rule that decides every piece is:

    a client is wired to a tool only if the manifest installs that tool, or the piece is repository practice that
    needs no tool outside the repository. Nothing is decided by what the old workstation has.

adoption/new-wsl/client-config-map.json names every piece of the client templates (each hook entry, plugin,
marketplace, status line, group of variables, permission rule, MCP server, Codex key, copied hook or agent file,
instruction block and step of this tool) and gives it one wiring: `slot:<manifest slot>` (wired while that slot
installs and its default is the owner the entry names; a row's interim install, amendment 3 of the manifest's decision rule,
counts as what the slot installs while the row carries it), `practice`, `not_wired:<reason>`, or `authorization:<reason>` (a
setting that grants a permission or suppresses a confirmation: written only with --with-authorization-settings and,
when the entry also names a `slot` and its `owner`, only while that slot installs the owner). The map is a closed world:
a piece it does not name is an error. The tool does not read the old bootstrap profile
(adoption/bootstrap-linux.sh --profile, --configure-full-profile). Three of the templates take the new distribution's
additions (adoption/new-wsl/templates/, TEMPLATE_ADDITIONS): keys only this tool renders, such as the Codex shells'
`inherit = "none"` with its set table, the semble servers and the tool approval modes the distribution's no-prompt
requirement needs, so the shared templates stay what render_config.py and the bootstrap render on every other host.

  --check    reads the manifest, the map, the templates and the install plan; fails when a piece is unmapped, a map
             entry names no piece, a slot is unknown, a practice piece runs a tool outside the repository, a hook file
             a wired hook runs is not one the repository copies, an authorization setting is classed practice or as a
             slot, the plan's two sources for a port disagree, or a file of the example host's render (without and with the authorization
             settings) names a tool that is not wired. Prints one line per piece (wired, not wired with the reason, or
             authorization, listed apart) and notes. --json prints the table; --markdown prints the tables of
             docs/decisions/2026-10-02-new-wsl-client-configuration.md.
             A piece mapped to a slot that does not install is not wired, not an error: the manifest decides, and the
             piece is wired when the slot installs the owner the entry names.
  --render   --host NAME --out DIR [--with-authorization-settings]: settings.json (and the WSL overlay),
             mcp-servers.json, codex.config.toml, codex.hooks.json and the two Codex profiles for that host value file,
             with wired pieces only; the authorization settings (the ones that grant a permission or suppress a
             confirmation: Claude Code permissions.defaultMode and skipDangerousModePermissionPrompt, Codex approval_policy
             and sandbox_mode, a Codex project's trust_level, and the tool approval mode of a Codex MCP server, which
             also needs its server wired) only with the option. Placeholders
             are filled by tools/adoption/render_config.py. The telemetry endpoint, the gateway port and AI_MEMORY_BIN
             (the ai-memory executable the plan's memory-owner row links) come from the install plan; HOST_PATH gains
             the directories of the wired path pieces.
  --write-blocks
             writes adoption/new-wsl/claude-user-instructions.md and codex-user-instructions.md: the two instruction blocks
             (examples/claude-native/CLAUDE.md, adoption/templates/codex.AGENTS.template.md) with every sentence, list item,
             paragraph and heading that names a tool that is not wired left out and nothing written in its place; --dropped
             lists every unit left out, in full. --check fails while a committed file differs from what the filter makes.
  --apply    --host NAME [--home DIR] [--claude-bin P] [--codex-bin P] [--codex-process-name N]
             [--with-authorization-settings] [--dry-run] [--skip STEP]: puts the render in place with the repository's
             own tools, one step each (the names --skip
             takes). It installs no tool and no pinned client; it backs up what it changes, runs again to the same files,
             and prints what it did and what it left out. --dry-run runs no client binary and writes nothing.
             While the render wires an interim install (amendment 3 of the manifest's decision rule) and the layer
             consensus's wave-2 batch still owes an acknowledgement (consensus.json wave2.acknowledgements_owed), a real
             run refuses and writes nothing, and a dry run says so. While the map wires step/codex-remote-plugin-rules,
             the Codex config also gets a [[skills.config]] name rule per skill of the account's remote plugins and an off
             switch per plugin MCP server, read from the home's plugin cache (remote_plugin_rules); --render has no home
             and leaves them out.
             An existing ~/.codex/config.toml is merged, never rewritten: every key and table it has stays as it is, what
             the render has and it lacks is added (a rule list, [[skills.config]], gains the render's rules it lacks after
             its own, and one written as an inline array, an empty `config = []` included, is refused, with nothing
             written), a value that differs stays (shown beside the render's, each value cut to
             300 characters with `...` in the display only, and the step ends `merged with conflicts kept`), the file is
             backed up first, read back with tomllib after the write and put back when it is not the merge.
             features.daemon_auto_start goes through Codex's own writer. A running Codex (`pgrep -x`) stops either write of
             config.toml, the merge and the creation of a file that is absent (close the sessions, run again; the message
             also names a running app-server daemon and how to stop it, read from /proc, or from `ps -ww -o command=`
             where there is no /proc), and so does a `pgrep` that cannot run or exits with a status other than 0 or 1:
             whether a Codex runs is then not known, and the step fails. A Claude setting the map marks keep_existing
             (the theme), and every authorization setting, is written only when settings.json has no value for it. The
             authorization settings are not written without --with-authorization-settings, and an existing value of them
             is then never touched; --apply prints a line before the summary that starts `authorization settings:` and
             says `left to the clients' own defaults` when the option was not given and, when it was, `applied`, `partly
             applied`, `kept` or `not applied` (`would be applied` or `would be partly applied` in a dry run), followed by
             what it added, kept, found already the same and did not reach, a skipped step and a failed step told apart.

Reused, not rewritten: render_config.render_one (placeholders), install_claude_profile.py (hook and agent copies with
their checksums, MCP registration), apply_claude_settings.py (settings merge and backup), managed_block.py (instruction
blocks, the login-shell PATH block), codex_home.py (the Codex config), apply_codex_lane.py's create-only write and
codex_roles.py's source checks, the bootstrap's own `install_native` function for the max-effort launcher, and
scripts/adoption_status.py's login-shell probe. apply_codex_lane.py as a whole is not used: it writes the
context-mode entry into config.toml, which this distribution does not wire.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import fnmatch
import json
import os
import re
import shlex
import shutil
import stat
import string
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
import apply_claude_settings as file_io  # noqa: E402
import apply_codex_lane as lane  # noqa: E402
import codex_home  # noqa: E402
import codex_roles  # noqa: E402
import install_claude_profile as icp  # noqa: E402
import managed_block  # noqa: E402
import render_config  # noqa: E402
from scripts import adoption_status  # noqa: E402

MAP_REL = "adoption/new-wsl/client-config-map.json"
MAP_SCHEMA = "native-agent-stack/new-wsl-client-config-map/v1"
MANIFEST_REL = "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json"
# The layer consensus whose wave-2 batch records amendment 3 (the interim installs) and the acknowledgements both model
# families owe it; --apply refuses to wire an interim install while one is owed (owed_acknowledgements).
CONSENSUS_REL = "evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json"
PLAN_REL = "evidence/artifacts/new-wsl-install-plan-20261002"
HOST_TEMPLATE_REL = "adoption/templates/wsl/host.new-distro.json.template"
BOOTSTRAP_REL = "adoption/bootstrap-linux.sh"
TEMPLATES = {
    "claude/settings": "adoption/templates/claude.settings.template.json",
    "claude/overlay": "adoption/templates/claude.settings.linux-wsl2.overlay.json",
    "claude/mcp": "adoption/mcp/claude-user.json",
    "codex/config": "adoption/templates/codex.config.template.toml",
    "codex/stack-worker": "adoption/templates/codex.stack-worker.config.toml",
    "codex/omniroute": "adoption/templates/codex.omniroute.config.toml",
    "codex/hooks": "adoption/templates/codex.hooks.template.json",
}
# The new distribution's additions to three shared templates: keys only this tool renders, because no other host takes
# them (render_config.py, install_claude_profile.py and the bootstrap never read these files, so each shared template
# stays what every other host renders). template_data merges a group's additions into its template; a key both define is
# refused, and an additions file's `_comment` is not a piece.
TEMPLATE_ADDITIONS = {
    "claude/settings": "adoption/new-wsl/templates/claude.settings.additions.json",
    "claude/mcp": "adoption/new-wsl/templates/claude-user.mcp.additions.json",
    "codex/config": "adoption/new-wsl/templates/codex.config.additions.toml",
}
CLAUDE_AGENTS_REL = "adoption/agents/claude"
CODEX_ROLES_REL = "adoption/agents/codex"
CLAUDE_MD_PIECE = "claude/instructions/claude-md"
CODEX_MD_PIECE = "codex/instructions/agents-md"
BLOCK_TEXT_REL = {CLAUDE_MD_PIECE: "examples/claude-native/CLAUDE.md",
                  CODEX_MD_PIECE: "adoption/templates/codex.AGENTS.template.md"}
# The two blocks as this distribution installs them: the sources above with every unit that names a tool that is not
# wired left out (filter_block), committed so that a change of the sources, the map or the manifest shows as a stale file.
GENERATED_BLOCKS = {CLAUDE_MD_PIECE: "adoption/new-wsl/claude-user-instructions.md",
                    CODEX_MD_PIECE: "adoption/new-wsl/codex-user-instructions.md"}
RENDERED_BLOCKS = {CLAUDE_MD_PIECE: "claude-user-instructions.md", CODEX_MD_PIECE: "codex-user-instructions.md"}
STEP_PIECES = ("step/claude-launcher", "step/login-path-block", "step/skills", "path/local-bin", "path/mise-shims",
               "step/codex-remote-plugin-rules")
REMOTE_PLUGIN_PIECE = STEP_PIECES[5]
# The account's remote plugins, which no row of the definitive manifest selects: Codex keeps their bundles under
# <Codex home>/plugins/cache/<marketplace>/<plugin>/<version>/ (core-plugin-common/src/installed.rs PLUGINS_CACHE_DIR,
# core-plugins/src/store.rs plugin_root, remote.rs REMOTE_GLOBAL_MARKETPLACE_NAME at openai/codex rust-v0.160.0).
REMOTE_MARKETPLACE = "openai-curated-remote"
# Where a plugin's manifest may be, in the order Codex looks (exec-server-protocol/src/protocol.rs L49-53 at rust-v0.160.0).
PLUGIN_MANIFESTS = (".codex-plugin/plugin.json", ".claude-plugin/plugin.json", ".cursor-plugin/plugin.json")
# The settings that grant a permission or suppress a confirmation. A tool must not write them on a fresh host by default,
# so the map classes them `authorization:<reason>`, and --with-authorization-settings is the one way to render and apply
# them. The tool, not the map, says which pieces they are (is_authorization_piece): the map cannot class one of them as
# practice or as a slot, whatever installs.
AUTHORIZATION_PIECES = (
    "claude/settings/setting/permissions.defaultMode",
    "claude/settings/setting/skipDangerousModePermissionPrompt",
    "codex/config/approval_policy",
    "codex/config/sandbox_mode",
)
# An allow rule grants a permission too. A Codex project's trust_level is the saved answer to the folder-trust question:
# a trusted project's own .codex/config.toml layers load instead of loading disabled (codex-rs/config/src/loader/mod.rs
# L131-133 at rust-v0.160.0), and the TUI asks nothing for it (codex-rs/tui/src/config_update.rs L338-366); see the
# addendum of 2026-10-04 in docs/decisions/2026-10-02-new-wsl-client-configuration.md.
AUTHORIZATION_PATTERNS = ("claude/*/permission/allow/*", "codex/*/projects.*.trust_level")
# Codex's tool approval modes (config.schema.json at rust-v0.160.0, AppToolApproval: auto, prompt, writes, approve). The key
# `default_tools_approval_mode` is an authorization piece whatever its value; `approval_mode` (one tool's) is one when the
# value approves. They sit under the table of an MCP server, so the map ties them to the slot that wires the server too.
APPROVAL_MODE_KEYS = ("default_tools_approval_mode", "approval_mode")
APPROVING_MODES = ("approve",)
AUTHORIZATION_OPTION = "--with-authorization-settings"
# What the line --apply prints about the authorization settings starts with, and the words that follow it (documented in the
# recipe, the decision record, the receipt example and above; tests/test_new_wsl_client_config.py pins every place).
AUTHORIZATION_OUTCOMES = ("left to the clients' own defaults", "applied", "would be applied", "partly applied",
                          "would be partly applied", "kept", "not applied")
# The step of --apply that writes the authorization settings of each group of pieces.
AUTHORIZATION_STEP = {"claude/settings": "claude-settings", "claude/overlay": "claude-settings",
                      "codex/config": "codex-config", "codex/stack-worker": "codex-files", "codex/omniroute": "codex-files"}
EXAMPLE_HOST = "example"   # the host value file whose render --check scans
LAUNCHER_PIECE, PATH_BLOCK_PIECE = STEP_PIECES[0], STEP_PIECES[1]
# The steps --apply runs, in order; --skip names one.
STEPS = ("claude-hooks", "claude-agents", "claude-mcp", "claude-settings", "claude-launcher", "claude-md",
         "codex-config", "codex-files", "codex-md", "login-path", "verify")
# Command words a practice hook may run besides the files the repository copies: the shell's own words, python3 (the
# interpreter of every tool in tools/adoption/) and jq (F4 of adoption/platforms/linux-wsl2-new-distro.md installs it and
# adoption/bootstrap-linux.sh requires it). Any other word is a tool outside the repository.
BASE_COMMAND_WORDS = frozenset({"python3", "jq", "[", "test", "true", ":"})
TOML_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
HEADING = re.compile(r"^(#{1,6})\s")
SENTENCE_BREAK = re.compile(r"(?<=[.!?])(\s+)(?=[A-Z`\[(<\"'*_])")
SENTENCE_END = re.compile(r"[.!?][\"')\]`*_]*$")
# The wrap width of the RTK awareness text that adoption/templates/codex.AGENTS.template.md carries verbatim
# (rtk-ai/rtk hooks/rtk-awareness-full.md): a run of lines that are all this short, with a sentence running on from
# one line into the next, is one wrapped paragraph; longer lines are one statement each.
WRAP_WIDTH = 80
HOST_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")  # the bootstrap's --host rule
# What the repository's tools print when they change something (install_claude_profile, apply_claude_settings,
# managed_block, codex_home).
CHANGE_REPORT = re.compile(r"\b(installed|registered|written|Wrote|created|set to false)\b")


class ConfigError(ValueError):
    """The map, a template, the manifest or the plan cannot be used as they are."""


class ProcessCheckError(ConfigError):
    """The check for a running Codex itself failed, so whether one runs is not known and the step must not write."""


@dataclasses.dataclass(frozen=True)
class Piece:
    key: str
    group: str
    path: tuple = ()
    value: object = None
    command: str | None = None


@dataclasses.dataclass(frozen=True)
class Entry:
    index: int
    match: tuple
    wiring: str
    raw: dict

    @property
    def owner(self) -> str:
        return self.raw.get("owner", "")

    @property
    def names(self) -> tuple:
        return tuple(self.raw.get("names", ()))

    @property
    def keep_existing(self) -> bool:
        """A Claude setting that is a person's choice: written only when the settings file has no value for it."""
        return self.raw.get("keep_existing") is True

    @property
    def slot(self) -> str:
        """The manifest slot an authorization entry is also tied to (with `owner`): the piece belongs to a tool's own
        configuration, so it is written only when the option is given and that slot installs the owner."""
        return self.raw.get("slot", "")


@dataclasses.dataclass(frozen=True)
class Verdict:
    piece: Piece
    entry: Entry
    wired: bool
    reason: str

    @property
    def authorization(self) -> bool:
        """The piece is an authorization setting: wired only when --with-authorization-settings was given."""
        return self.entry.wiring.partition(":")[0] == "authorization"


def is_authorization_piece(key: str, value=None) -> bool:
    """Whether a piece is a setting that grants a permission or suppresses a confirmation: one of the settings named above,
    an allow rule, a `default_tools_approval_mode` of any value, or an `approval_mode` that approves. `value` is the piece's
    value (the template's), which only the last kind needs."""
    leaf = key.rsplit(".", 1)[-1]
    return (key in AUTHORIZATION_PIECES or any(fnmatch.fnmatchcase(key, pattern) for pattern in AUTHORIZATION_PATTERNS)
            or leaf == APPROVAL_MODE_KEYS[0] or (leaf == APPROVAL_MODE_KEYS[1] and value in APPROVING_MODES))


def authorization_label(key: str) -> str:
    """How --apply names an authorization piece: the client, the Codex profile when the piece is in one (the same tool
    approval mode can be in the user config and in the stack-worker profile), and an allow rule as one."""
    group, _, name = key.rpartition("/")
    if key.startswith("claude/"):
        return f"Claude Code allow rule {name}" if group.endswith("/permission/allow") else f"Claude Code {name}"
    profile = {"codex/stack-worker": " stack-worker profile", "codex/omniroute": " omniroute profile"}.get(group, "")
    return f"Codex{profile} {name}"


# ---------------------------------------------------------------------------------------------------------------
# the manifest, the install plan and the map

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(root: Path) -> dict:
    """{slot id: row} of the manifest's foundation catalog."""
    slots = read_json(root / MANIFEST_REL)["slots"]
    return {row["slot_id"]: row for row in slots if row.get("catalog") == "foundation"}


def installs(row: dict) -> bool:
    """The install plan's rule (evidence/artifacts/new-wsl-install-plan-20261002/check_plan.py L146-168): the row
    carries an interim install (amendment 3 of the manifest's decision rule), or it names a default, installs something
    extra, is not resolved as not installed and is not split."""
    if row.get("interim"):
        return True
    outcome = (row.get("resolution") or {}).get("outcome")
    return (bool(row.get("default")) and not row.get("installs_nothing_extra") and outcome != "not_installed"
            and (row.get("state") or "") != "split")


def installed_default(row: dict) -> str:
    """What the row installs: its interim's default while it carries one, otherwise its decided default."""
    return str((row.get("interim") or {}).get("default") or row.get("default"))


def owed_acknowledgements(root: Path) -> list:
    """The model families whose acknowledgement of the layer consensus's wave-2 batch is still owed (wave2.
    acknowledgements_owed). The interim installs of amendment 3 wait for both: 'Until all of that exists, nothing is
    installed' (wave-2 code-search ruling, change 1); install.sh's interim_acknowledged reads the same list."""
    owed = (read_json(root / CONSENSUS_REL).get("wave2") or {}).get("acknowledgements_owed")
    if not (isinstance(owed, list) and all(isinstance(name, str) and name for name in owed)):
        raise ConfigError(f"{CONSENSUS_REL}: wave2.acknowledgements_owed is not a list of names, so whether the interim "
                          "installs may be wired is not known")
    return owed


def wired_interims(results: list, manifest: dict) -> list:
    """The slots whose interim install (amendment 3) a wired piece belongs to: a slot entry's slot, or the slot an
    authorization entry is tied to."""
    slots = set()
    for verdict in results:
        kind, _, argument = verdict.entry.wiring.partition(":")
        slot = argument if kind == "slot" else verdict.entry.slot if kind == "authorization" else ""
        if verdict.wired and slot and (manifest.get(slot) or {}).get("interim"):
            slots.add(slot)
    return sorted(slots)


def why_not_installed(slot: str, row: dict) -> str:
    outcome = (row.get("resolution") or {}).get("outcome")
    if (row.get("state") or "") == "split":
        cause = "split, it waits for the deciding measurement"
    elif outcome == "not_installed":
        cause = "resolved as not installed"
    elif row.get("installs_nothing_extra"):
        cause = f"it installs nothing extra ({row.get('state') or 'open'})"
    else:
        cause = "it names no default"
    return f"slot {slot}: {cause}: {str(row.get('default'))[:80]}"


def load_plan(root: Path) -> dict:
    """{rows: {slot: row}, ports: {...}}; each port is read from two files of the plan and the two must agree."""
    base = root / PLAN_REL
    rows = {row["slot"]: row for row in read_json(base / "install-plan.json")["owners"]}
    otel = (base / "config" / "otel.yaml").read_text(encoding="utf-8")
    listening = re.search(r"protocols:\s*\n\s*grpc:\s*\n\s*endpoint:\s*127\.0\.0\.1:(\d+)\s*\n\s*http:\s*\n"
                          r"\s*endpoint:\s*127\.0\.0\.1:(\d+)", otel)
    stated = re.search(r"OTLP grpc/http endpoint=127\.0\.0\.1:(\d+)/(\d+)",
                       rows["otel-collector-contrib"]["service"]["port_setting"])
    # Plain NAME=value lines since the wave-2 gateway ruling (change 12): systemd's EnvironmentFile= drops `export` lines.
    env = re.search(r"^(?:export )?PORT=(\d+)$", (base / "config" / "omniroute.env.example").read_text(encoding="utf-8"), re.M)
    if not (listening and stated and env):
        raise ConfigError("the install plan's collector or gateway port could not be read")
    gateway = rows["gpt-gateway"]["service"]["port"]
    if listening.groups() != stated.groups() or gateway != int(env.group(1)):
        raise ConfigError("the install plan states a port twice and the two statements differ: "
                          f"collector {listening.groups()} / {stated.groups()}, gateway {gateway} / {env.group(1)}")
    release = re.fullmatch(r"rust-v(\d+\.\d+\.\d+)", rows["codex"]["release"])
    if release is None:
        raise ConfigError(f"the plan's Codex release {rows['codex']['release']!r} is not rust-v<semver>")
    return {"rows": rows,
            "ports": {"collector_grpc_port": int(listening.group(1)), "collector_http_port": int(listening.group(2)),
                      "gateway_port": gateway},
            "codex_model": render_config.codex_model_for(release.group(1)),
            "skills": installed_skills(rows, root),
            "ai_memory_bin": ai_memory_link(rows.get("memory-owner") or {})}


def ai_memory_link(row: dict):
    """The path, under $HOME, of the ai-memory executable the plan's memory-owner row links, or None while the row does
    not install it. The Claude hooks run AI_MEMORY_BIN; without it render_config.py derives the path from the platform's
    pin (${ECO_ROOT}/tools/ai-memory-<version>/ai-memory), which is not where this plan installs ai-memory."""
    if not row.get("installed"):
        return None
    for command in row.get("commands", []):
        link = re.search(r'ln -sfn "\$HOME/[^"]+/ai-memory" "\$HOME/([^"$]+/ai-memory)"', command)
        if link:
            return link.group(1)
    raise ConfigError("the install plan's memory-owner row installs ai-memory but links no ai-memory executable under "
                      "$HOME, so the hooks' AI_MEMORY_BIN could not be read")


SKILLS_MANIFEST_REL = "adoption/skills/manifest.json"
SKILLS_INSTALLER = "tools/adoption/install_skills.py"


def installed_skills(rows: dict, root: Path = ROOT) -> frozenset:
    """The skills the plan installs. Since the wave-2 skills ruling (change 7) its skills rows run the repository's
    installer against adoption/skills/manifest.json: over every selected skill (none pruned or held) without --only, or
    over its --only names. A row that runs the skills CLI's own add names its skills after -s."""
    selected = {skill["name"] for skill in read_json(root / SKILLS_MANIFEST_REL)["skills"]
                if skill.get("status") not in ("pruned", "held")}
    found = set()
    for row in rows.values():
        for command in row.get("commands", []):
            if SKILLS_INSTALLER in command and "--check-only" not in command:
                only = re.findall(r"--only ([a-z0-9][a-z0-9._-]*)", command)
                found.update(selected & set(only) if only else selected)
            match = re.search(r" -s ((?:[a-z0-9][a-z0-9-]* )+)-y", command)
            if match:
                found.update(match.group(1).split())
    return frozenset(found)


def load_map(root: Path) -> list:
    data = read_json(root / MAP_REL)
    if data.get("schema") != MAP_SCHEMA or not isinstance(data.get("entries"), list):
        raise ConfigError(f"{MAP_REL} is not a {MAP_SCHEMA} file")
    entries = []
    for index, raw in enumerate(data["entries"]):
        match = raw.get("match")
        if not (isinstance(match, list) and match and all(isinstance(item, str) and item for item in match)):
            raise ConfigError(f"map entry {index}: match must be a non-empty list of patterns")
        wiring = str(raw.get("wiring", ""))
        kind, separator, argument = wiring.partition(":")
        if wiring != "practice" and not (kind in ("slot", "not_wired", "authorization") and separator
                                         and argument.strip()):
            raise ConfigError(f"map entry {index} ({match[0]}): wiring must be slot:<id>, practice, not_wired:<reason> "
                              "or authorization:<reason>")
        if kind == "slot" and not raw.get("owner"):
            raise ConfigError(f"map entry {index} ({match[0]}): a slot entry names the owner it wires")
        if "slot" in raw and not (kind == "authorization" and isinstance(raw["slot"], str) and raw["slot"].strip()
                                  and raw.get("owner")):
            raise ConfigError(f"map entry {index} ({match[0]}): `slot` ties an authorization entry to the slot that "
                              "installs its tool, and comes with the `owner` the entry names")
        if "keep_existing" in raw and raw["keep_existing"] is not True:
            raise ConfigError(f"map entry {index} ({match[0]}): keep_existing is true or absent")
        entries.append(Entry(index, tuple(match), raw["wiring"], raw))
    return entries


def load_dependents(root: Path) -> list:
    """The sentences the map declares as depending on the sentence before them: [{starts, why}]. A dependent sentence
    goes whenever the sentence before it on its line goes, and is declared, never inferred."""
    declared = read_json(root / MAP_REL).get("dependent_sentences", [])
    out = []
    for index, raw in enumerate(declared if isinstance(declared, list) else [None]):
        starts = raw.get("starts") if isinstance(raw, dict) else None
        why = raw.get("why") if isinstance(raw, dict) else None
        if not (isinstance(raw, dict) and isinstance(starts, str) and starts.strip() and isinstance(why, str)
                and why.strip() and raw.get("on") == "previous"):
            raise ConfigError(f"dependent_sentences[{index}] needs `starts` (the sentence's opening words), `why` and "
                              "`on: previous`")
        out.append({"starts": starts, "why": why})
    return out


# ---------------------------------------------------------------------------------------------------------------
# the pieces of the templates

def read_template(path: Path):
    return tomllib.loads(path.read_text(encoding="utf-8")) if path.suffix == ".toml" else read_json(path)


def merge_additions(base: dict, extra: dict, where: str, path: tuple = ()) -> dict:
    """base with extra's keys added; a table both have is merged key by key, and any other key both define is refused."""
    out = dict(base)
    for key, value in extra.items():
        here = path + (key,)
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = merge_additions(out[key], value, where, here)
        elif key in out:
            raise ConfigError(f"{where} defines {lane.key_path(list(here))}, which its shared template defines too; "
                              "an addition adds a key, it never replaces one (a map entry's override does that)")
        else:
            out[key] = value
    return out


def template_data(root: Path, group: str):
    """A group's template as this tool reads it: the shared template, with the new distribution's additions merged in
    when TEMPLATE_ADDITIONS names a file for the group."""
    data = read_template(root / TEMPLATES[group])
    if group not in TEMPLATE_ADDITIONS:
        return data
    extra = {key: value for key, value in read_template(root / TEMPLATE_ADDITIONS[group]).items() if key != "_comment"}
    return merge_additions(data, extra, TEMPLATE_ADDITIONS[group])


def hook_key(group: str, event: str, matcher, hook: dict) -> str:
    tail = hook.get("command") or json.dumps(hook, sort_keys=True)
    return f"{group}/hook/{event}/matcher={'-' if matcher is None else matcher}/{tail}"


def settings_pieces(group: str, data: dict) -> list:
    """The removable units of a Claude settings file (or of the Codex hooks template, which has the same shape)."""
    out = []
    for key, value in data.items():
        if key == "env":
            out += [Piece(f"{group}/env/{name}", group, ("env", name), val) for name, val in value.items()]
        elif key == "permissions":
            for pkey, pval in value.items():
                if isinstance(pval, list):
                    out += [Piece(f"{group}/permission/{pkey}/{entry}", group, ("permissions", pkey, index), entry)
                            for index, entry in enumerate(pval)]
                else:
                    out.append(Piece(f"{group}/setting/permissions.{pkey}", group, ("permissions", pkey), pval))
        elif key == "hooks":
            for event, groups in value.items():
                for gindex, hgroup in enumerate(groups):
                    for hindex, hook in enumerate(hgroup.get("hooks", [])):
                        out.append(Piece(hook_key(group, event, hgroup.get("matcher"), hook), group,
                                         ("hooks", event, gindex, hindex), hook, hook.get("command")))
        elif key == "enabledPlugins":
            out += [Piece(f"{group}/plugin/{name}", group, (key, name), val) for name, val in value.items()]
        elif key == "extraKnownMarketplaces":
            out += [Piece(f"{group}/marketplace/{name}", group, (key, name), val) for name, val in value.items()]
        else:
            command = value.get("command") if isinstance(value, dict) else None
            out.append(Piece(f"{group}/setting/{key}", group, (key,), value, command))
    return out


def toml_leaves(node: dict, prefix: tuple = ()):
    for key, value in node.items():
        if isinstance(value, dict) and value:
            yield from toml_leaves(value, prefix + (key,))
        else:
            yield prefix + (key,), value


def toml_pieces(group: str, data: dict) -> list:
    return [Piece(f"{group}/{lane.key_path(list(path))}", group, path, value) for path, value in toml_leaves(data)]


def collect_pieces(root: Path) -> list:
    pieces = []
    for group in ("claude/settings", "claude/overlay"):
        pieces += settings_pieces(group, template_data(root, group))
    for name, spec in template_data(root, "claude/mcp").get("mcpServers", {}).items():
        command = " ".join([spec.get("command") or spec.get("url", ""), *spec.get("args", [])])
        pieces.append(Piece(f"claude/mcp/server/{name}", "claude/mcp", ("mcpServers", name), spec, command))
    pieces += [Piece(f"claude/profile/hook-file/{name}", "claude/profile", value=name) for name in icp.HOOKS]
    pieces += [Piece(f"claude/profile/agent/{path.name}", "claude/profile", value=path.name)
               for path in sorted((root / CLAUDE_AGENTS_REL).glob("*.md"))]
    pieces.append(Piece(CLAUDE_MD_PIECE, "claude/instructions"))
    for group in ("codex/config", "codex/stack-worker", "codex/omniroute"):
        pieces += toml_pieces(group, template_data(root, group))
    pieces += settings_pieces("codex/hooks", template_data(root, "codex/hooks"))
    pieces.append(Piece(CODEX_MD_PIECE, "codex/instructions"))
    pieces += [Piece(f"codex/role/{path.name}", "codex/role", value=path.name)
               for path in sorted((root / CODEX_ROLES_REL).glob("*.toml"))]
    pieces += [Piece(f"codex/worker-role/{path.name}", "codex/role", value=path.name)
               for path in sorted((root / CODEX_ROLES_REL / "workers").glob("*.toml"))]
    pieces += [Piece(key, "step") for key in STEP_PIECES]
    keys = [piece.key for piece in pieces]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise ConfigError(f"two template pieces have the same key: {duplicates[0]}")
    return pieces


def assign(pieces: list, entries: list):
    """Each piece goes to the first entry whose patterns match its key (so a specific entry precedes a general one).
    Returns ({key: entry}, errors): an unmapped piece and an entry that no piece reaches are errors."""
    taken, used, errors = {}, {entry.index: 0 for entry in entries}, []
    for piece in pieces:
        for entry in entries:
            if any(fnmatch.fnmatchcase(piece.key, pattern) for pattern in entry.match):
                taken[piece.key] = entry
                used[entry.index] += 1
                break
        else:
            errors.append(f"unmapped piece: {piece.key}")
    errors += [f"map entry {entry.index} matches no piece that an earlier entry left: {entry.match[0]!r}"
               for entry in entries if not used[entry.index]]
    return taken, errors


# ---------------------------------------------------------------------------------------------------------------
# wiring

def command_words(command: str) -> list:
    """The command words of a shell command line: the first word of each statement, after assignments, `!` and `exec`."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    words, at_start = [], True
    for token in lexer:
        if token and set(token) <= set(";&|()"):
            at_start = True
        elif at_start and (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token) or token in ("!", "exec")):
            continue
        elif at_start:
            words.append(token)
            at_start = False
    return words


def hook_files(command: str) -> list:
    return re.findall(r"\.claude/hooks/([A-Za-z0-9_.-]+)", command or "")


def slot_verdict(piece: Piece, entry: Entry, slot: str, manifest: dict, plan: dict, errors: list, warnings: list) -> tuple:
    """(wired, reason) of a piece that depends on a manifest slot installing the owner the entry names."""
    row = manifest.get(slot)
    if row is None:
        errors.append(f"{piece.key}: slot {slot!r} is not a foundation slot of the manifest")
        return False, f"unknown slot {slot}"
    if not installs(row):
        return False, why_not_installed(slot, row)
    default = installed_default(row)
    interim = " (interim install)" if row.get("interim") else ""
    if entry.owner.casefold() not in default.casefold():
        warnings.append(f"{piece.key}: slot {slot} installs {default!r}{interim}; the map wires {entry.owner!r}")
        return False, f"slot {slot} installs {default!r}{interim}, not {entry.owner!r}"
    if not plan["rows"].get(slot, {}).get("installed"):
        warnings.append(f"{piece.key}: the manifest installs slot {slot}, the install plan does not")
    return True, f"slot {slot} installs {default}{interim}"


def verdicts(pieces: list, taken: dict, manifest: dict, plan: dict, authorization: bool = False) -> tuple:
    """(verdicts, errors, warnings). An authorization piece is wired only when `authorization` is true, and, when its
    entry names a slot, only while that slot installs the owner."""
    out, errors, warnings = [], [], []
    for piece in pieces:
        entry = taken.get(piece.key)
        if entry is None:
            continue
        kind, _, argument = entry.wiring.partition(":")
        known = is_authorization_piece(piece.key, piece.value)
        if known and kind in ("practice", "slot"):
            errors.append(f"{piece.key}: a setting that grants a permission or suppresses a confirmation is classed "
                          f"authorization:<reason>, not {kind}, which would write it by default; it is written only with "
                          f"{AUTHORIZATION_OPTION} (an entry that also names a `slot` and its `owner` keeps the piece "
                          "with the tool it belongs to)")
        elif kind == "authorization" and not known:
            errors.append(f"{piece.key}: classed authorization, which this tool does not know as a setting that grants "
                          "a permission or suppresses a confirmation (is_authorization_piece)")
        if kind == "authorization":
            slot_wired, slot_reason = ((True, "") if not entry.slot else
                                       slot_verdict(piece, entry, entry.slot, manifest, plan, errors, warnings))
            wired = authorization and slot_wired
            tied = f"; {slot_reason}" if entry.slot else ""
            if wired:
                reason = f"authorization setting, written because {AUTHORIZATION_OPTION} was given: {argument}{tied}"
            elif authorization:
                reason = f"authorization setting, not written although {AUTHORIZATION_OPTION} was given: {slot_reason}"
            else:
                reason = f"authorization setting, not written unless {AUTHORIZATION_OPTION} is given: {argument}{tied}"
        elif kind == "practice":
            wired, reason = True, "repository practice"
            for word in command_words(piece.command or ""):
                if word not in BASE_COMMAND_WORDS:
                    errors.append(f"{piece.key}: a practice piece runs `{word}`, which is not in the repository")
            for name in hook_files(piece.command):
                if name not in icp.HOOKS:
                    errors.append(f"{piece.key}: a practice piece runs {name}, which the repository does not copy")
        elif kind == "not_wired":
            wired, reason = False, argument
        else:
            wired, reason = slot_verdict(piece, entry, argument, manifest, plan, errors, warnings)
        out.append(Verdict(piece, entry, wired, reason))
    return out, errors, warnings


def unwired_names(entries_or_verdicts: list, manifest: dict) -> list:
    """The names of tools this distribution does not wire: those the map gives its unwired entries, and the former
    defaults of the manifest rows that install nothing."""
    names = []
    for item in entries_or_verdicts:
        names += list(item.entry.names if isinstance(item, Verdict) and not item.wired else ())
    for row in manifest.values():
        former = (row.get("resolution") or {}).get("former_default") or {}
        if not installs(row) and former.get("repository") and former.get("name"):
            names.append(former["name"])
    return sorted(set(names), key=str.casefold)


def name_hits(text: str, names) -> list:
    """The names of tools that are not wired that a text holds, as whole words and whatever the case."""
    return [name for name in names if re.search(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", text, re.I)]


def scan_names(text: str, names: list) -> list:
    """[(line number, line, [names])] for the lines of text that name a tool in names."""
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        found = codex_roles.name_hits(line, names, True)
        if found:
            hits.append((number, line.strip(), found))
    return hits


def block_text(root: Path, piece_key: str) -> str:
    return (root / BLOCK_TEXT_REL[piece_key]).read_text(encoding="utf-8")


@dataclasses.dataclass(frozen=True)
class Dropped:
    """One unit of a source block that the filter left out, in full."""
    line: int       # the first source line, from 1
    kind: str       # sentence, bullet, paragraph, heading or marker
    text: str       # wrapped lines are joined with a newline
    names: tuple    # the not-wired tools it names (none for a heading that is left with nothing under it)
    note: str = ""


def split_sentences(line: str) -> list:
    """[(sentence, the separator that follows it)]; joining each sentence and its separator gives the line again. A list
    marker (`- `, `3. `) belongs to the first sentence, so that `3.` is never a sentence of its own."""
    marker = LIST_ITEM.match(line)
    head = marker.group(0) if marker else ""
    parts = SENTENCE_BREAK.split(line[len(head):])
    pairs = list(zip(parts[0::2], parts[1::2] + [""]))
    pairs[0] = (head + pairs[0][0], pairs[0][1])
    return pairs


def wrapped_run(run: list) -> bool:
    """Whether consecutive plain lines are one hard-wrapped paragraph: several lines, every one within WRAP_WIDTH, and a
    sentence that runs on past the end of at least one of them."""
    return (len(run) > 1 and all(len(line) <= WRAP_WIDTH for line in run)
            and any(not SENTENCE_END.search(line.rstrip()) for line in run[:-1]))


def block_units(lines: list) -> list:
    """[(first line, end line, kind)] of a block: blank, marker, heading, item (a list item and its indented
    continuation lines), paragraph (a wrapped paragraph, or one plain line) ."""
    units, index = [], 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            units.append((index, index + 1, "blank"))
        elif HEADING.match(line):
            units.append((index, index + 1, "heading"))
        elif line.startswith("<!--") and line.rstrip().endswith("-->"):
            units.append((index, index + 1, "marker"))
        elif LIST_ITEM.match(line):
            end = index + 1
            while end < len(lines) and lines[end].strip() and lines[end][:1].isspace() and not LIST_ITEM.match(lines[end]):
                end += 1
            units.append((index, end, "item"))
            index = end - 1
        else:
            end = index + 1
            while (end < len(lines) and lines[end].strip() and not HEADING.match(lines[end])
                   and not LIST_ITEM.match(lines[end]) and not lines[end].startswith("<!--")):
                end += 1
            if wrapped_run(lines[index:end]):
                units.append((index, end, "paragraph"))
            else:
                units += [(number, number + 1, "paragraph") for number in range(index, end)]
            index = end - 1
        index += 1
    return units


DEPENDS_NOTE = "it depends on the sentence before it, which goes (declared in the map's dependent_sentences)"


def filter_block(text: str, names: list, dependents: tuple = ()) -> tuple:
    """(filtered text, [Dropped]): text without the units that name a tool in names, and no new text.

    A single-line list item that names a tool is left out whole, and so is one whose first sentence names it (the item
    would lose its marker). In a single-line paragraph or in a later sentence of an item only the sentences that name a
    tool go; the others stay word for word, except a sentence that starts with one of `dependents` (declared in the
    map, never inferred), which goes whenever the sentence before it on its line goes. A paragraph or item wrapped over
    several lines goes whole, because a sentence cannot leave wrapped lines without cutting them. A heading or a
    comment line that names a tool goes, and so does a heading with nothing kept under it. Blank lines that would stand
    twice, first or last stay out."""
    if "\r" in text or "```" in text:
        raise ConfigError("the block filter reads plain Markdown lines: no carriage return and no code fence")
    lines = text.split("\n")
    final_newline = lines[-1] == ""
    if final_newline:
        lines = lines[:-1]
    kept, dropped = [], []                   # kept: [[text, kind, heading level]]
    for start, end, kind in block_units(lines):
        chunk = lines[start:end]
        joined = "\n".join(chunk)
        found = tuple(codex_roles.name_hits(joined, names, True))
        if kind == "blank" or not found:
            kept += [[line, kind, len(HEADING.match(line).group(1)) if kind == "heading" else 0] for line in chunk]
        elif kind in ("marker", "heading"):
            dropped.append(Dropped(start + 1, kind, joined, found))
        elif end - start > 1:
            dropped.append(Dropped(start + 1, "bullet" if kind == "item" else "paragraph", joined, found,
                                   "wrapped over several lines, so a sentence cannot leave without cutting a line"))
        else:
            pairs = split_sentences(chunk[0])
            flags = [bool(codex_roles.name_hits(sentence, names, True)) for sentence, _ in pairs]
            follows = [False] * len(pairs)   # goes because the sentence before it went, as the map declares
            for number in range(1, len(pairs)):
                if flags[number - 1] and not flags[number] and any(pairs[number][0].startswith(opening)
                                                                    for opening in dependents):
                    flags[number] = follows[number] = True
            if kind == "item" and (all(flags) or flags[0]):
                note = "" if all(flags) else "its first sentence names the tool, so the item goes with its other sentences"
                dropped.append(Dropped(start + 1, "bullet", chunk[0], found, note))
            else:
                dropped += [Dropped(start + 1, "sentence", sentence,
                                    () if after else tuple(codex_roles.name_hits(sentence, names, True)),
                                    DEPENDS_NOTE if after else "")
                            for (sentence, _), flag, after in zip(pairs, flags, follows) if flag]
                stay = [pair for pair, flag in zip(pairs, flags) if not flag]
                if stay:
                    kept.append(["".join(sentence + (sep if number < len(stay) - 1 else "")
                                         for number, (sentence, sep) in enumerate(stay)), kind, 0])
    for index in reversed(range(len(kept))):
        if kept[index][1] != "heading":
            continue
        level, body = kept[index][2], False
        for later in kept[index + 1:]:
            if later[1] == "heading" and later[2] <= level:
                break
            if later[1] in ("item", "paragraph"):
                body = True
                break
        if not body:
            dropped.append(Dropped(next(number for number, line in enumerate(lines, 1) if line == kept[index][0]),
                                   "heading", kept[index][0], (), "nothing is kept under it"))
            del kept[index]
    out = []
    for line, kind, _ in kept:
        if kind == "blank" and (not out or out[-1] == ""):
            continue
        out.append(line)
    while out and out[-1] == "":
        out.pop()
    marker_last = len(out) >= 2 and out[-1].startswith("<!--") and out[-2] == ""
    if marker_last:
        del out[-2]
    return "\n".join(out) + ("\n" if final_newline else ""), sorted(dropped, key=lambda unit: unit.line)


def generate_blocks(root: Path, names: list) -> dict:
    """{piece: (generated path, filtered text, [Dropped])}: the two blocks filtered by the names of the unwired tools and
    by the dependent sentences the map declares."""
    dependents = tuple(item["starts"] for item in load_dependents(root))
    out = {}
    for piece, relative in GENERATED_BLOCKS.items():
        text, dropped = filter_block(block_text(root, piece), names, dependents)
        out[piece] = (relative, text, dropped)
    return out


def block_errors(root: Path, names: list) -> list:
    """A committed block that is missing, or that differs from what the filter makes of its source now."""
    errors = []
    for piece, (relative, text, _) in generate_blocks(root, names).items():
        path = root / relative
        if not path.is_file():
            errors.append(f"{relative} is missing: run `new_wsl_client_config.py --write-blocks`")
        elif path.read_text(encoding="utf-8") != text:
            errors.append(f"{relative} is stale (its source, the map or the manifest changed): run "
                          "`new_wsl_client_config.py --write-blocks`")
        left = scan_names(text, names)
        if left:
            errors.append(f"{relative}: the filtered block still names {sorted({n for _, _, f in left for n in f})}")
    return errors


def dropped_text(root: Path, generated: dict) -> str:
    """Every dropped unit in full, for the terminal."""
    lines = []
    for piece, (relative, text, dropped) in generated.items():
        source = BLOCK_TEXT_REL[piece]
        total = len(block_text(root, piece).splitlines())
        lines.append(f"{source} -> {relative}: {len(dropped)} unit(s) left out, {len(text.splitlines())} of {total} lines stay")
        for unit in dropped:
            tools = f" names {', '.join(unit.names)}" if unit.names else ""
            note = f" ({unit.note})" if unit.note else ""
            lines.append(f"  line {unit.line}, {unit.kind}{tools}{note}:")
            lines += [f"    {part}" for part in unit.text.split("\n")]
    return "\n".join(lines) + "\n"


def dropped_markdown(root: Path, generated: dict) -> str:
    """The same list for the decision record: one fenced block per source."""
    parts = []
    for piece, (relative, text, dropped) in generated.items():
        total = len(block_text(root, piece).splitlines())
        parts.append(f"`{BLOCK_TEXT_REL[piece]}`, written to `{relative}` ({len(dropped)} unit(s) left out; "
                     f"{len(text.splitlines())} of {total} lines stay):\n\n```text")
        for unit in dropped:
            tools = f"; names {', '.join(unit.names)}" if unit.names else ""
            note = f"; {unit.note}" if unit.note else ""
            parts.append(f"line {unit.line}, {unit.kind}{tools}{note}\n{unit.text}\n")
        parts.append("```\n")
    return "\n".join(parts)


def resolve_blocks(root: Path, results: list, names: list) -> list:
    """The two instruction blocks are practice, installed as the filtered files; one whose filtered text still names a
    tool that is not wired is left out."""
    generated = generate_blocks(root, names)
    out = []
    for verdict in results:
        if verdict.piece.key in GENERATED_BLOCKS and verdict.wired:
            relative, text, dropped = generated[verdict.piece.key]
            left = scan_names(text, names)
            if left:
                verdict = dataclasses.replace(verdict, wired=False,
                                              reason=f"the filtered block still names {len(left)} line(s) with a tool")
            else:
                verdict = dataclasses.replace(
                    verdict, reason=f"repository practice, filtered: {relative} leaves out {len(dropped)} unit(s)")
        out.append(verdict)
    return out


# ---------------------------------------------------------------------------------------------------------------
# rendering

def apply_rewrites(piece_key: str, value, entry: Entry, ports: dict):
    for rewrite in entry.raw.get("rewrite", []):
        if not isinstance(value, str) or rewrite["from"] not in value:
            raise ConfigError(f"{piece_key}: the rewrite source {rewrite['from']!r} is not in the template value")
        value = value.replace(rewrite["from"], rewrite["to"].format(**ports))
    return value


def prune_hook_groups(groups: list, event: str, keep: set) -> list:
    out = []
    for gindex, group in enumerate(groups):
        kept = [hook for hindex, hook in enumerate(group.get("hooks", [])) if ("hooks", event, gindex, hindex) in keep]
        if kept:
            out.append({**{k: v for k, v in group.items() if k != "hooks"}, "hooks": kept})
    return out


def prune_settings(data: dict, keep: set, values: dict) -> dict:
    """data with only the pieces whose path is in keep; values maps a kept path to its replacement value."""
    out = {}
    for key, value in data.items():
        if key == "hooks":
            hooks = {event: pruned for event, groups in value.items()
                     if (pruned := prune_hook_groups(groups, event, keep))}
            if hooks:
                out[key] = hooks
        elif key in ("env", "enabledPlugins", "extraKnownMarketplaces"):
            kept = {name: values.get((key, name), val) for name, val in value.items() if (key, name) in keep}
            if kept:
                out[key] = kept
        elif key == "permissions":
            kept = {}
            for pkey, pval in value.items():
                if isinstance(pval, list):
                    items = [entry for index, entry in enumerate(pval) if ("permissions", pkey, index) in keep]
                    if items:
                        kept[pkey] = items
                elif ("permissions", pkey) in keep:
                    kept[pkey] = pval
            if kept:
                out[key] = kept
        elif (key,) in keep:
            out[key] = values.get((key,), value)
    return out


def prune_toml(node: dict, keep: set, values: dict, prefix: tuple = ()):
    out = {}
    for key, value in node.items():
        path = prefix + (key,)
        if isinstance(value, dict) and value:
            sub = prune_toml(value, keep, values, path)
            if sub:
                out[key] = sub
        elif path in keep:
            out[key] = values.get(path, value)
    return out


def toml_key(key: str) -> str:
    return key if TOML_BARE_KEY.fullmatch(key) else json.dumps(key, ensure_ascii=False).replace("\x7f", "\\u007f")


def toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{toml_key(k)} = {toml_value(v)}" for k, v in value.items()) + " }" if value else "{}"
    raise ConfigError(f"a {type(value).__name__} value cannot be written as TOML")


def is_table_array(value) -> bool:
    """A non-empty list of tables, which TOML writes as an array of tables ([[...]]), as Codex writes [[skills.config]]."""
    return isinstance(value, list) and bool(value) and all(isinstance(item, dict) for item in value)


def table_lines(path: tuple, node: dict) -> list:
    """The lines of one table and, below it, its arrays of tables and its sub-tables; each header has a blank line
    before it. An array of tables is written as [[...]] items, so a later merge can append an item as text."""
    scalars = [(k, v) for k, v in node.items() if not (isinstance(v, dict) and v) and not is_table_array(v)]
    arrays = [(k, v) for k, v in node.items() if is_table_array(v)]
    subs = [(k, v) for k, v in node.items() if isinstance(v, dict) and v]
    lines = []
    if path and (scalars or not (subs or arrays)):
        lines += ["", "[" + ".".join(toml_key(part) for part in path) + "]"]
    lines += [f"{toml_key(k)} = {toml_value(v)}" for k, v in scalars]
    for k, items in arrays:
        for item in items:
            lines += array_item_lines(path + (k,), item)
    for k, v in subs:
        lines += table_lines(path + (k,), v)
    return lines


def array_item_lines(path: tuple, item: dict) -> list:
    """One [[...]] item of an array of tables: its scalars, then its own sub-tables, which belong to this item."""
    lines = ["", "[[" + ".".join(toml_key(part) for part in path) + "]]"]
    lines += [f"{toml_key(k)} = {toml_value(v)}" for k, v in item.items()
              if not (isinstance(v, dict) and v) and not is_table_array(v)]
    for k, v in item.items():
        if is_table_array(v):
            for sub in v:
                lines += array_item_lines(path + (k,), sub)
        elif isinstance(v, dict) and v:
            lines += table_lines(path + (k,), v)
    return lines

def emit_toml(data: dict, header: str) -> str:
    """TOML text for data, scalars before tables, with no template comments; read back to the same data or refused."""
    text = "\n".join([header.rstrip("\n"), *table_lines((), data)]) + "\n"
    if tomllib.loads(text) != data:
        raise ConfigError("the TOML written for a render does not read back to the same data")
    return text


def dedupe_path(value: str) -> str:
    seen = []
    for part in value.split(":"):
        if part and part not in seen:
            seen.append(part)
    return ":".join(seen)


def dedupe_paths(node):
    """Every PATH value of a parsed settings or Codex config without a repeated directory."""
    if isinstance(node, dict):
        return {k: (dedupe_path(v) if k == "PATH" and isinstance(v, str) else dedupe_paths(v)) for k, v in node.items()}
    if isinstance(node, list):
        return [dedupe_paths(item) for item in node]
    return node


def substitute(text: str, values: dict, suffix: str) -> str:
    """The text with its ${NAME} placeholders filled by tools/adoption/render_config.py."""
    with tempfile.TemporaryDirectory(prefix="new-wsl-render-") as scratch:
        path = Path(scratch) / f"template{suffix}"
        path.write_text(text, encoding="utf-8")
        return render_config.render_one(path, values)


def host_values(host: str, plan: dict, home: Path | None, wired_dirs: list) -> dict:
    values = dict(render_config.load_host_values(host))
    if home is not None:
        old, new = values["HOME"].rstrip("/"), str(home).rstrip("/")
        if not old and new:
            # A declared HOME of "/" strips to "", and every absolute value starts with "" + "/": the home's own paths
            # cannot be told apart from the system's, and HOST_PATH's first entry (/usr/local/sbin in the example) would
            # move under the new home: refused. Where the new home is the root as well, nothing moves and nothing is
            # refused.
            raise ConfigError(f"the host value file declares HOME as {values['HOME']!r}: without its trailing slashes "
                              f"that is empty, so every absolute path counts as under the home, and system paths "
                              f"such as HOST_PATH's would be moved under {home}; declare the home its paths were "
                              f"written for")
        values = {k: (new + v[len(old):] if v == old or v.startswith(old + "/") else v) for k, v in values.items()}
    base = values["HOME"].rstrip("/")
    # The systemd user runtime directory of the user this tool runs as, /run/user/UID (user@.service(5)), which the Codex
    # shells' set table names, for systemctl --user and rootless Docker (codex.config.additions.toml); a host value file
    # may name another.
    values.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    values["OTEL_ENDPOINT"] = f"127.0.0.1:{plan['ports']['collector_http_port']}"
    values["CODEX_MODEL"] = plan["codex_model"]
    if plan.get("ai_memory_bin"):
        values["AI_MEMORY_BIN"] = f"{base}/{plan['ai_memory_bin']}"
    values["HOST_PATH"] = ":".join([*(f"{base}/{relative}" for relative in wired_dirs), values["HOST_PATH"]])
    return values


def wired_path_dirs(results: list) -> list:
    return [v.entry.raw["home_dir"] for v in results if v.piece.group == "step" and v.piece.key.startswith("path/")
            and v.wired]


def render(root: Path, results: list, plan: dict, values: dict, manifest: dict | None = None) -> dict:
    """{file name: text} of the wired pieces."""
    wired = {v.piece.key: v for v in results if v.wired}

    def keep_of(group: str):
        """(the paths of the group's wired pieces, {path: replacement value} for those an entry overrides or rewrites)."""
        kept = [v for v in results if v.wired and v.piece.group == group]
        replaced = {v.piece.path: apply_rewrites(v.piece.key, v.piece.value, v.entry, plan["ports"])
                    for v in kept if v.entry.raw.get("rewrite")}
        replaced.update({v.piece.path: v.entry.raw["override"] for v in kept if "override" in v.entry.raw})
        return {v.piece.path for v in kept}, replaced

    files = {}
    # Claude settings (placeholders filled) and the WSL overlay (applied as it is, as the bootstrap applies it).
    keep, replaced = keep_of("claude/settings")
    template = template_data(root, "claude/settings")
    text = json.dumps(prune_settings(template, keep, replaced), indent=2, ensure_ascii=False) + "\n"
    rendered = dedupe_paths(json.loads(substitute(text, values, ".json")))
    files["settings.json"] = json.dumps(rendered, indent=2, ensure_ascii=False) + "\n"
    keep, replaced = keep_of("claude/overlay")
    overlay = prune_settings(template_data(root, "claude/overlay"), keep, replaced)
    files["settings.linux-wsl2.overlay.json"] = json.dumps(overlay, indent=2, ensure_ascii=False) + "\n"
    # The user-scope MCP servers: a wired server with the launch the entry gives it. ${HOME} and ${ECO_ROOT} stay for
    # install_claude_profile.py, which fills them when it registers the file; an override's other placeholders are host
    # values and are filled here (ai-memory's URL takes the host file's AI_MEMORY_URL, as the hooks and Codex do).
    servers = {}
    host_only = {key: value for key, value in values.items() if key not in ("HOME", "ECO_ROOT")}
    for name, spec in template_data(root, "claude/mcp").get("mcpServers", {}).items():
        verdict = wired.get(f"claude/mcp/server/{name}")
        if verdict:
            override = json.loads(string.Template(json.dumps(verdict.entry.raw.get("override", {}))).safe_substitute(
                host_only))
            servers[name] = {**spec, **override}
    files["mcp-servers.json"] = json.dumps({"mcpServers": servers}, indent=2, ensure_ascii=False) + "\n"
    # Codex: the user config (placeholders filled), the hooks and the two profiles.
    keep, replaced = keep_of("codex/config")
    data = prune_toml(template_data(root, "codex/config"), keep, replaced)
    interim = emit_toml(data, "")
    parsed = dedupe_paths(tomllib.loads(substitute(interim, values, ".toml")))
    files["codex.config.toml"] = emit_toml(parsed, header("codex/config"))
    keep, replaced = keep_of("codex/hooks")
    hooks = prune_settings(template_data(root, "codex/hooks"), keep, replaced)
    files["codex.hooks.json"] = json.dumps({"hooks": {}, **hooks}, indent=2, ensure_ascii=False) + "\n"
    for group, name in (("codex/stack-worker", "codex.stack-worker.config.toml"),
                        ("codex/omniroute", "codex.omniroute.config.toml")):
        keep, replaced = keep_of(group)
        profile = prune_toml(template_data(root, group), keep, replaced)
        files[name] = emit_toml(profile, header(group))
    generated = generate_blocks(root, unwired_names(results, manifest if manifest is not None else load_manifest(root)))
    for piece, (_, text, _) in generated.items():
        if piece in wired:
            files[RENDERED_BLOCKS[piece]] = text
    return files


# ---------------------------------------------------------------------------------------------------------------
# the account's remote plugins (wave-2 skills ruling, change 5)
#
# A remote plugin's local toggle does not hold: Codex replaces the local plugins.<id> entry with the synced remote one and
# keeps only its mcp_servers (codex-rs/core-plugins/src/loader.rs merge_remote_plugin_config at rust-v0.160.0). The
# ruling's local fallback, beside the account-level uninstall it names first: one [[skills.config]] name rule per skill of
# each remote plugin no manifest row selects (none is selected), which Codex matches against the qualified name
# <plugin namespace>:<skill name> (config/src/skills_config.rs resolve_disabled_paths; ext/skills/src/loader/namespace.rs
# qualify), and plugins."<id>".mcp_servers.<server>.enabled = false for each MCP server such a plugin ships (the local
# mcp_servers survive the merge). The rules are read from the plugin cache at --apply, so a run after the account's plugin
# set changes renders the new set; a rule is never a bare name, so none can match a .system skill of Codex.

def skill_name(skill_md: Path) -> str | None:
    """The name Codex gives a SKILL.md: the `name` of its YAML frontmatter with its whitespace collapsed, or its directory's
    name when the frontmatter has none (codex-rs/skills/src/parser.rs L44-69 and L200-221; ext/skills/src/loader/host.rs
    default_skill_name and metadata.rs sanitize_single_line at rust-v0.160.0); None for a file without frontmatter, which
    Codex does not load. Only a plain or quoted one-line value is read: any other form is refused, since a guessed name
    would disable nothing."""
    lines = skill_md.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = next((number for number, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None or end == 1:
        return None
    name = None
    for line in lines[1:end]:
        match = re.match(r"name:(.*)$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if len(value) >= 2 and value[0] in "'\"" and value[-1] == value[0]:
            value = value[1:-1]
        elif value[:1] in ("|", ">", "&", "*", "[", "{", "!", "'", '"'):
            raise ConfigError(f"{skill_md}: the frontmatter's name is not a one-line value this tool reads, so the rule "
                              "for the skill cannot be written; disable it by a [[skills.config]] path rule instead")
        else:
            value = re.sub(r"\s+#.*$", "", value)
        name = " ".join(value.split())
    return name or skill_md.parent.name


def plugin_manifest(version_dir: Path) -> dict | None:
    """A cached plugin's manifest, the first of PLUGIN_MANIFESTS that exists; None when it has none."""
    for relative in PLUGIN_MANIFESTS:
        path = version_dir / relative
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    return None


def manifest_paths(version_dir: Path, value, default: str) -> list:
    """The paths a manifest field names (a path or a list of them, relative to the plugin root), or the default path."""
    items = [value] if isinstance(value, str) else value if isinstance(value, list) else []
    paths = [version_dir / item for item in items if isinstance(item, str) and item.strip()]
    return paths or [version_dir / default]


def remote_plugin_rules(codex_home: Path) -> tuple:
    """(qualified skill names, {plugin id: [MCP server names]}) of every plugin in the account's remote plugin cache, over
    each cached version (a rule names no version). A plugin's namespace is its manifest's `name`, or the root's own name
    when that is blank (utils/plugins/src/plugin_namespace.rs plugin_namespace_for_root_uri); its skills are under the
    manifest's `skills` paths or skills/ (core-plugins/src/loader.rs plugin_skill_roots), its MCP servers in the manifest's
    `mcpServers` object or file, or .mcp.json (plugin_mcp_config_paths), at rust-v0.160.0."""
    base = codex_home / "plugins" / "cache" / REMOTE_MARKETPLACE
    names, servers = set(), {}
    for plugin_dir in sorted(path for path in base.iterdir() if path.is_dir()) if base.is_dir() else []:
        plugin_id = f"{plugin_dir.name}@{REMOTE_MARKETPLACE}"
        for version_dir in sorted(path for path in plugin_dir.iterdir() if path.is_dir()):
            manifest = plugin_manifest(version_dir)
            if manifest is None:
                continue
            namespace = str(manifest.get("name") or "").strip() or version_dir.name
            for root in manifest_paths(version_dir, manifest.get("skills"), "skills"):
                for skill_md in sorted(root.rglob("SKILL.md")) if root.is_dir() else []:
                    name = skill_name(skill_md)
                    if name:
                        names.add(f"{namespace}:{name}")
            declared = manifest.get("mcpServers")
            found = dict(declared) if isinstance(declared, dict) else {}
            if not isinstance(declared, dict):
                for path in manifest_paths(version_dir, declared, ".mcp.json"):
                    if path.is_file():
                        data = json.loads(path.read_text(encoding="utf-8"))
                        table = data.get("mcpServers", data) if isinstance(data, dict) else {}
                        found.update(table if isinstance(table, dict) else {})
            servers.setdefault(plugin_id, set()).update(name for name, spec in found.items() if isinstance(spec, dict))
    return sorted(names), {plugin_id: sorted(found) for plugin_id, found in sorted(servers.items()) if found}


def with_remote_plugin_rules(text: str, names: list, servers: dict) -> str:
    """The rendered Codex config with a name rule per remote plugin skill after its own rules, and each remote plugin's MCP
    servers turned off. The plugin's table also gets enabled = false: a local [plugins."<id>"] table is a PluginConfig
    whose `enabled` defaults to true (config/src/types.rs L1004-1006; core-plugins/src/marketplace_policy.rs
    configured_plugins_from_stack), a local entry the account's synced list lacks stays as configured
    (core-plugins/src/loader.rs merge_configured_plugins_with_remote_installed), and load_plugin loads an enabled entry
    whose bundle is cached (loader.rs, the `if !plugin.enabled` return), all at rust-v0.160.0; so a table with only
    mcp_servers would turn on a cached plugin the account no longer installs. While the account installs the plugin, the
    synced entry replaces this one and keeps only its mcp_servers (merge_remote_plugin_config)."""
    data = tomllib.loads(text)
    rules = data.setdefault("skills", {}).setdefault("config", [])
    rules += [rule for rule in ({"name": name, "enabled": False} for name in names) if rule not in rules]
    for plugin_id, found in servers.items():
        table = data.setdefault("plugins", {}).setdefault(plugin_id, {})
        table.setdefault("enabled", False)
        for server in found:
            table.setdefault("mcp_servers", {}).setdefault(server, {"enabled": False})
    return emit_toml(data, header("codex/config"))


def header(group: str) -> str:
    sources = TEMPLATES[group] + (f" and {TEMPLATE_ADDITIONS[group]}" if group in TEMPLATE_ADDITIONS else "")
    return (f"# Rendered by tools/adoption/new_wsl_client_config.py from {sources}.\n"
            "# Only the pieces the definitive manifest wires for the new distribution\n"
            "# (adoption/new-wsl/client-config-map.json); the template's comments are not carried,\n"
            "# because they explain pieces this file leaves out.\n")


def wiring_table(results: list) -> str:
    rows = [{"piece": v.piece.key, "wired": v.wired,
             "wiring": v.entry.wiring if v.entry.wiring.partition(":")[0] not in ("not_wired", "authorization")
             else v.entry.wiring.partition(":")[0], "reason": v.reason} for v in results]
    return json.dumps(rows, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------------------------------------------
# checks and notes

def analyse(root: Path, check_blocks: bool = True, authorization: bool = False):
    """(results, manifest, plan, errors, warnings) for the catalog at root. check_blocks=False leaves the freshness of the
    two generated blocks out, for --write-blocks, which is what makes them fresh. authorization=True wires the
    authorization settings (--with-authorization-settings)."""
    manifest, plan = load_manifest(root), load_plan(root)
    pieces, entries = collect_pieces(root), load_map(root)
    taken, errors = assign(pieces, entries)
    results, more_errors, warnings = verdicts(pieces, taken, manifest, plan, authorization)
    errors += more_errors
    names = unwired_names(results, manifest)
    results = resolve_blocks(root, results, names)
    if check_blocks:
        errors += block_errors(root, names)
    errors += consistency_errors(root, results, entries)
    return results, manifest, plan, errors, warnings


def consistency_errors(root: Path, results: list, entries: list) -> list:
    """What the pieces together must satisfy: a wired piece runs only wired hook files, a wired hook file is the one its
    checksum row pins, a rewrite finds its source text, and a name the map lists for an unwired piece occurs in the
    templates or the instruction and agent text (otherwise the scan for it looks for nothing)."""
    errors = []
    wired_files = {v.piece.value for v in results if v.piece.key.startswith("claude/profile/hook-file/") and v.wired}
    for v in results:
        if v.wired and v.piece.command:
            for name in hook_files(v.piece.command):
                if name not in wired_files:
                    errors.append(f"{v.piece.key}: a wired piece runs {name}, which is not a wired hook file")
        if v.wired and v.piece.key.startswith("claude/profile/hook-file/"):
            source = icp.HOOKS[v.piece.value]
            try:
                if icp.sha256_of(source) != icp.expected_sha256(source):
                    errors.append(f"{v.piece.key}: {source.name} does not match its row in {icp.SHA256SUMS.name}")
            except (OSError, icp.InstallError) as error:
                errors.append(f"{v.piece.key}: {error}")
        if v.entry.raw.get("rewrite"):
            try:
                apply_rewrites(v.piece.key, v.piece.value, v.entry, {"gateway_port": 0})
            except ConfigError as error:
                errors.append(str(error))
    paths = [root / TEMPLATES[group] for group in TEMPLATES] + [root / rel for rel in TEMPLATE_ADDITIONS.values()]
    paths += [root / rel for rel in BLOCK_TEXT_REL.values()]
    paths += sorted((root / CLAUDE_AGENTS_REL).glob("*.md"))
    pool = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    dead = {name for entry in entries for name in entry.names if not codex_roles.name_hits(pool, [name], True)}
    errors += [f"the map lists the name {name!r}, and no template, instruction or agent text holds it"
               for name in sorted(dead)]
    for item in load_dependents(root):
        found = 0
        for piece in BLOCK_TEXT_REL:
            for number, line in enumerate(block_text(root, piece).split("\n"), 1):
                for position, (sentence, _) in enumerate(split_sentences(line)):
                    if sentence.startswith(item["starts"]):
                        found += 1
                        if position == 0:
                            errors.append(f"{BLOCK_TEXT_REL[piece]} line {number}: the dependent sentence "
                                          f"{item['starts']!r} starts its line, so no sentence comes before it")
        if not found:
            errors.append(f"the map declares the dependent sentence {item['starts']!r}, and no instruction block holds it")
    for entry in entries:
        if entry.keep_existing and not all(
                re.fullmatch(r"claude/(settings|overlay)/setting/[A-Za-z0-9_$]+", pattern) for pattern in entry.match):
            errors.append(f"map entry {entry.index} ({entry.match[0]}): keep_existing applies to top-level Claude "
                          "settings only")
    return errors


def frontmatter(text: str) -> dict:
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    fields, key = {}, None
    for line in (match.group(1) if match else "").splitlines():
        if re.match(r"^[A-Za-z]", line) and ":" in line:
            key, _, rest = line.partition(":")
            fields[key.strip()] = rest.strip()
        elif key and line.strip().startswith("- "):
            fields[key] = (fields[key] + "," if fields[key] else "") + line.strip()[2:]
    return fields


def agent_gaps(root: Path, results: list, plan: dict) -> dict:
    """{agent file: {"mcp_tools": [...], "skills": [...]}}: what a project agent's frontmatter names that this
    distribution will not have (nothing is installed to fill the gap)."""
    servers = {v.piece.key.rsplit("/", 1)[1] for v in results if v.wired and v.piece.key.startswith("claude/mcp/server/")}
    # A wired Claude Code plugin supplies its own MCP tools, named mcp__plugin_<plugin>_<server>__<tool>, and its skills,
    # named <plugin>:<skill> (context-mode's plugin: mcp__plugin_context-mode_context-mode__ctx_execute and
    # context-mode:context-mode).
    plugins = {v.piece.key.rsplit("/", 1)[1].split("@", 1)[0] for v in results
               if v.wired and v.piece.key.startswith("claude/settings/plugin/")}

    def supplied(server: str) -> bool:
        return server in servers or any(server.startswith(f"plugin_{plugin}_") for plugin in plugins)

    gaps = {}
    for path in sorted((root / CLAUDE_AGENTS_REL).glob("*.md")):
        fields = frontmatter(path.read_text(encoding="utf-8"))
        tools = [tool.strip() for tool in fields.get("tools", "").split(",") if tool.strip().startswith("mcp__")]
        missing_tools = [tool for tool in tools if not supplied(re.match(r"mcp__(.+?)__", tool).group(1))]
        missing_skills = [skill for skill in fields.get("skills", "").split(",") if skill and skill not in plan["skills"]
                          and skill.partition(":")[0] not in (plugins if ":" in skill else ())]
        if missing_tools or missing_skills:
            gaps[path.name] = {"mcp_tools": missing_tools, "skills": missing_skills}
    return gaps


def host_template_note(root: Path, plan: dict) -> str | None:
    text = (root / HOST_TEMPLATE_REL).read_text(encoding="utf-8")
    match = re.search(r'"OTEL_ENDPOINT":\s*"127\.0\.0\.1:(\d+)"', text)
    plan_port = plan["ports"]["collector_http_port"]
    if match and int(match.group(1)) != plan_port:
        return (f"{HOST_TEMPLATE_REL} carries OTEL_ENDPOINT 127.0.0.1:{match.group(1)}; the plan's collector listens on "
                f"127.0.0.1:{plan_port} (OTLP/HTTP): --render and --apply use the plan's port")
    return None


def markdown_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def markdown_code(text: str) -> str:
    fence = "``" if "`" in text else "`"
    return f"{fence}{markdown_cell(text)}{fence}"


def markdown_tables(root: Path, results: list, plan: dict) -> str:
    """The three tables of docs/decisions/2026-10-02-new-wsl-client-configuration.md: one row per piece that is not wired,
    one row per authorization setting (kept apart: not written unless the option is given), and one row per project agent
    that names skills or MCP tools this distribution will not have."""
    rows = ["| Piece | Wiring | Why it is not wired |", "| --- | --- | --- |"]
    for v in results:
        if not v.wired and not v.authorization:
            reason = v.reason
            wiring = v.entry.wiring if not v.entry.wiring.startswith("not_wired") else "not_wired"
            rows.append(f"| {markdown_code(v.piece.key)} | `{wiring}` | {markdown_cell(reason)} |")
    rows += ["", f"| Authorization setting | Value {AUTHORIZATION_OPTION} writes | Written by default | Why it needs the "
                 "option | Also needs |", "| --- | --- | --- | --- | --- |"]
    for v in results:
        if v.authorization:
            reason = v.entry.wiring.partition(":")[2]
            also = f"slot `{v.entry.slot}` installing `{v.entry.owner}`" if v.entry.slot else "-"
            rows.append(f"| {markdown_code(v.piece.key)} | {markdown_code(json.dumps(v.piece.value))} | no | "
                        f"{markdown_cell(reason)} | {also} |")
    gaps = agent_gaps(root, results, plan)
    rows += ["", "| Project agent | MCP servers of its tools that are not wired | Skills the plan does not install |",
             "| --- | --- | --- |"]
    for name, gap in gaps.items():
        servers = sorted({tool.split("__")[1] for tool in gap["mcp_tools"]})
        rows.append(f"| `{name}` | {', '.join(f'`{s}`' for s in servers) or '-'} | "
                    f"{', '.join(f'`{s}`' for s in gap['skills']) or '-'} |")
    return "\n".join(rows) + "\n"


def rendered_name_errors(root: Path) -> list:
    """Render for the example host without and with the authorization settings and scan every file for the name of a
    tool that is not wired (the names the map declares and the former defaults of the manifest rows that install
    nothing). The instruction blocks are among the files."""
    errors = []
    for with_authorization in (False, True):
        label = f"{'with' if with_authorization else 'without'} {AUTHORIZATION_OPTION}"
        try:
            results, manifest, plan, _, _ = analyse(root, check_blocks=False, authorization=with_authorization)
            files = render(root, results, plan, host_values(EXAMPLE_HOST, plan, None, wired_path_dirs(results)), manifest)
        except (ConfigError, render_config.RenderError, OSError, KeyError, ValueError) as error:
            errors.append(f"the render for the example host {label} failed, so it was not scanned: {error}")
            continue
        names = unwired_names(results, manifest)
        for name, text in files.items():
            hits = name_hits(text, names)
            if hits:
                errors.append(f"the render for the example host {label}: {name} names {', '.join(hits)}, "
                              f"which {'is' if len(hits) == 1 else 'are'} not wired")
    return errors


def short(text: str, width: int = 170) -> str:
    return text if len(text) <= width else text[:width - 3] + "..."


def cmd_check(args: argparse.Namespace) -> int:
    root = args.root
    try:
        results, manifest, plan, errors, warnings = analyse(root)
    except (ConfigError, OSError, KeyError, ValueError) as error:
        print(f"check failed: {error}", file=sys.stderr)
        return 1
    errors = errors + rendered_name_errors(root)
    if args.json:
        sys.stdout.write(wiring_table(results))
    elif args.markdown:
        sys.stdout.write(markdown_tables(root, results, plan))
        sys.stdout.write("\n" + dropped_markdown(root, generate_blocks(root, unwired_names(results, manifest))))
        return 1 if errors else 0
    else:
        for v in results:
            label = "authorization" if v.authorization else "wired    " if v.wired else "not wired"
            print(f"{label}  {short(v.piece.key)}  [{v.entry.wiring.split(':', 1)[0]}]  {short(v.reason, 110)}")
    wired = sum(1 for v in results if v.wired)
    apart = [v for v in results if v.authorization]
    out = sys.stderr if args.json else sys.stdout
    print(f"pieces: {len(results)}; wired: {wired}; not wired: {len(results) - wired - len(apart)}; "
          f"authorization: {len(apart)}", file=out)
    if apart:
        print(f"authorization settings (not rendered and not written unless {AUTHORIZATION_OPTION} is given; an existing "
              "value of them is never changed), with the value the option would write:", file=out)
        for v in apart:
            also = f"  (and only while slot {v.entry.slot} installs {v.entry.owner})" if v.entry.slot else ""
            print(f"  {v.piece.key} = {json.dumps(v.piece.value)}{also}", file=out)
        for reason in dict.fromkeys(v.entry.wiring.partition(":")[2] for v in apart):
            print(f"  why: {reason}", file=out)
    note = host_template_note(root, plan)
    for line in ([note] if note else []) + [f"warning: {w}" for w in warnings]:
        print(f"note: {line}" if not line.startswith("warning") else line, file=out)
    for name, gap in agent_gaps(root, results, plan).items():
        print(f"agent {name}: names {len(gap['mcp_tools'])} MCP tool(s) and {len(gap['skills'])} skill(s) this "
              f"distribution will not have: {', '.join(gap['skills'] + sorted({t.split('__')[1] for t in gap['mcp_tools']}))}",
              file=out)
    if args.dropped:
        sys.stdout.write(dropped_text(root, generate_blocks(root, unwired_names(results, manifest))))
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        print(f"check failed: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("check passed", file=out)
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    if not (args.host and args.out):
        print("--render needs --host NAME and --out DIR", file=sys.stderr)
        return 2
    if not HOST_NAME.fullmatch(args.host):
        print(f"--host must match {HOST_NAME.pattern}", file=sys.stderr)
        return 2
    try:
        results, manifest, plan, errors, _ = analyse(args.root, authorization=args.with_authorization_settings)
        if errors:
            print("render refused: the check fails:\n  " + "\n  ".join(errors), file=sys.stderr)
            return 1
        values = host_values(args.host, plan, None, wired_path_dirs(results))
        files = render(args.root, results, plan, values, manifest) | {"wiring.json": wiring_table(results)}
    except (ConfigError, render_config.RenderError, OSError, KeyError, ValueError) as error:
        print(f"render failed: {error}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (args.out / name).write_text(text, encoding="utf-8")
        print(f"wrote {args.out / name}")
    note = host_template_note(args.root, plan)
    if note:
        print(f"note: {note}")
    return 0


# ---------------------------------------------------------------------------------------------------------------
# merging the render into a Codex config.toml that already exists

ADDED_NOTE = "# added by tools/adoption/new_wsl_client_config.py --apply"
SECRET_NAME = re.compile(r"token|secret|passw|credential|api[_-]?key|bearer", re.I)
DAEMON_PATH = ("features", "daemon_auto_start")  # the one key Codex's own writer sets, as codex_home.py does
# A value is shown at most this many characters wide: a longer one is cut to SHOWN_WIDTH - 3 characters and "...". Only the
# display is cut, never the file. A value that holds a host path (the PATH of the render) is as long as the home it names.
SHOWN_WIDTH = 300
PROC = Path("/proc")   # where Linux keeps the command lines of its processes; macOS has none


class MergeError(ValueError):
    """The config.toml cannot be extended as text, or the result does not read back as the merge: nothing is kept."""


def strict_equal(left, right) -> bool:
    """Equality of parsed TOML that takes neither 1 for true nor 1.0 for 1."""
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(strict_equal(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(strict_equal(a, b) for a, b in zip(left, right))
    return type(left) is type(right) and left == right


def first_difference(left, right, path: tuple = ()):
    """The first key path where two parsed TOML trees differ; None when they do not."""
    if isinstance(left, dict) and isinstance(right, dict):
        for key in [*left, *(k for k in right if k not in left)]:
            if key not in left or key not in right:
                return path + (key,)
            found = first_difference(left[key], right[key], path + (key,))
            if found is not None:
                return found
        return None
    return None if strict_equal(left, right) else path


def drop_path(node: dict, path: tuple) -> bool:
    """Remove path from node, and each parent table the removal leaves empty; True when node itself is left empty."""
    head, rest = path[0], path[1:]
    if head in node:
        if not rest:
            del node[head]
        elif isinstance(node[head], dict) and drop_path(node[head], rest):
            del node[head]
    return not node


# Arrays of tables that Codex reads as lists of rules ([[skills.config]]: codex-rs/config/src/skills_config.rs at
# rust-v0.160.0, each item a path or name selector): the merge adds each rule of the render that the file lacks, after the
# file's own, and never takes the two lists for a conflict.
RULE_LISTS = {("skills", "config")}


@dataclasses.dataclass
class MergePlan:
    expected: dict      # the existing file's data with everything that was missing added
    keys: list          # [(path, value)]: keys the existing tables (or the top level) lack
    tables: list        # [(path, dict)]: whole tables the file lacks
    conflicts: list     # [(path, existing value, rendered value)]: the existing value stays
    appends: list = dataclasses.field(default_factory=list)   # [(path, [item])]: rules a RULE_LISTS array lacks

    def without(self, path: tuple) -> "MergePlan":
        """The same plan with one key left out of the text edits (Codex's own writer adds it)."""
        tables = []
        for table, node in self.tables:
            node = copy.deepcopy(node)
            if path[:len(table)] == table and drop_path(node, path[len(table):]):
                continue
            tables.append((table, node))
        return MergePlan(self.expected, [(p, v) for p, v in self.keys if p != path], tables, self.conflicts,
                         self.appends)


def plan_merge(existing: dict, rendered: dict) -> MergePlan:
    """What adding the render to an existing config means: a key or table the file lacks is added, a table both have is
    merged key by key, and a value that differs stays as the file has it (a conflict, reported). A rule list (RULE_LISTS)
    gains the render's rules it lacks, after its own."""
    keys, tables, conflicts, appends = [], [], [], []

    def walk(path: tuple, have: dict, want: dict) -> None:
        for key, value in want.items():
            here = path + (key,)
            # An existing rule list may be empty (`config = []`, which TOML writes only inline): it still gains the render's
            # rules, so the text edit refuses it as an inline array instead of the rules being kept out as a conflict.
            if here in RULE_LISTS and is_table_array(value) and (key not in have or is_table_array(have[key])
                                                                  or have[key] == []):
                mine = have.get(key, [])
                missing = [item for item in value if not any(strict_equal(item, rule) for rule in mine)]
                if missing:
                    appends.append((here, copy.deepcopy(missing)))
            elif key not in have:
                (tables if isinstance(value, dict) and value else keys).append((here, copy.deepcopy(value)))
            elif isinstance(value, dict) and isinstance(have[key], dict):
                walk(here, have[key], value)
            elif not strict_equal(have[key], value):
                conflicts.append((here, have[key], value))
    walk((), existing, rendered)
    expected = copy.deepcopy(existing)
    for path, value in [*keys, *tables]:
        holder = expected
        for part in path[:-1]:
            holder = holder[part]
        holder[path[-1]] = copy.deepcopy(value)
    for path, items in appends:
        holder = expected
        for part in path[:-1]:
            holder = holder[part]
        holder.setdefault(path[-1], []).extend(copy.deepcopy(items))
    return MergePlan(expected, keys, tables, conflicts, appends)


@dataclasses.dataclass
class TomlLine:
    text: str
    top: bool           # the line starts a statement: it is not inside a multi-line string or array
    kind: str           # blank, comment, header, array-header, item or continuation
    path: tuple = ()    # the table a header names


def scan_toml(text: str) -> list:
    """The lines of a TOML text with what each is. A line inside a multi-line string or array is a continuation, so a
    line that starts with `[` there is never taken for a table header."""
    out, state, depth = [], None, 0
    for line in re.findall(r"[^\n]*\n|[^\n]+", text):
        top = state is None and depth == 0
        i, n = 0, len(line)
        while i < n:
            ch = line[i]
            if state == '"""':
                if ch == "\\":
                    i += 2
                elif line.startswith('"""', i):
                    i += 3
                    while i < n and line[i] == '"':   # up to two more quotes belong to the string
                        i += 1
                    state = None
                else:
                    i += 1
            elif state == "'''":
                if line.startswith("'''", i):
                    i += 3
                    while i < n and line[i] == "'":
                        i += 1
                    state = None
                else:
                    i += 1
            elif ch == "#":
                break
            elif ch == '"':
                if line.startswith('"""', i):
                    state, i = '"""', i + 3
                else:
                    i += 1
                    while i < n and line[i] != '"':
                        i += 2 if line[i] == "\\" else 1
                    i += 1
            elif ch == "'":
                if line.startswith("'''", i):
                    state, i = "'''", i + 3
                else:
                    close = line.find("'", i + 1)
                    i = n if close < 0 else close + 1
            elif ch in "[{":
                depth, i = depth + 1, i + 1
            elif ch in "]}":
                depth, i = depth - 1, i + 1
            else:
                i += 1
        stripped = line.strip()
        if not top:
            out.append(TomlLine(line, False, "continuation"))
        elif not stripped:
            out.append(TomlLine(line, True, "blank"))
        elif stripped.startswith("#"):
            out.append(TomlLine(line, True, "comment"))
        elif stripped.startswith("["):
            path = codex_home.header_key(line)
            if path is None:
                raise MergeError(f"cannot read the table header {stripped!r}")
            out.append(TomlLine(line, True, "array-header" if stripped.startswith("[[") else "header", tuple(path)))
        else:
            out.append(TomlLine(line, True, "item"))
    return out


def merge_toml_text(text: str, plan: MergePlan) -> str:
    """text with plan.keys and plan.tables added and every existing line kept as it is: a key goes after the last
    statement of its table (a top-level key after the last one before the first table), a missing table goes at the end.
    A table that an inline table or dotted keys define cannot take a new key as text, and is refused."""
    lines = scan_toml(text)
    newline = "\r\n" if "\r\n" in text else "\n"
    headers = [(number, line) for number, line in enumerate(lines) if line.kind in ("header", "array-header")]
    plain = {line.path: number for number, line in headers if line.kind == "header"}
    reopenable = {path[:size] for path in [*plain, *(line.path for _, line in headers)] for size in range(1, len(path) + 1)}
    first_header = headers[0][0] if headers else len(lines)
    groups: dict = {}   # line number -> [(text lines, attached)] put before that line; len(lines) is the end of the file

    def statement_end(start: int, stop: int):
        """The line after the last statement that starts in [start, stop): a statement runs to the next top line."""
        last = max((n for n in range(start, stop) if lines[n].kind == "item"), default=None)
        if last is None:
            return None
        return next((n for n in range(last + 1, stop) if lines[n].top), stop)

    by_table: dict = {}
    for path, value in plan.keys:
        by_table.setdefault(path[:-1], []).append((path[-1], value))
    for table, pairs in by_table.items():
        added = [f"{toml_key(key)} = {toml_value(value)}" for key, value in pairs]
        name = lane.key_path(list(table))
        if table == ():
            at = statement_end(0, first_header)
            if at is None and not headers:   # no statement and no table: the keys follow whatever comments the file has
                groups.setdefault(len(lines), []).append(([ADDED_NOTE, *added], False))
            elif at is None:   # nothing precedes the first table: the keys go above it and the comment lines attached to it
                at = first_header
                while at > 0 and lines[at - 1].kind == "comment":
                    at -= 1
                groups.setdefault(at, []).append(([ADDED_NOTE, *added, ""], True))
            else:
                groups.setdefault(at, []).append(([ADDED_NOTE, *added], True))
        elif table in plain:
            after = next((n for n, _ in headers if n > plain[table]), len(lines))
            at = statement_end(plain[table] + 1, after)
            groups.setdefault(plain[table] + 1 if at is None else at, []).append(([ADDED_NOTE, *added], True))
        elif table in reopenable:   # a table that only its sub-tables' headers define: a header of its own can still open it
            groups.setdefault(len(lines), []).append(([ADDED_NOTE, f"[{name}]", *added], False))
        else:
            raise MergeError(f"cannot add {', '.join(key for key, _ in pairs)} inside [{name}]: it is defined as an inline "
                             "table or with dotted keys, which text cannot extend")
    block = []
    for table, node in plan.tables:
        parent = table[:-1]
        if parent and parent not in plain and parent not in reopenable:
            raise MergeError(f"cannot add [{lane.key_path(list(table))}]: [{lane.key_path(list(parent))}] is defined as an "
                             "inline table or with dotted keys, which text cannot extend")
        block += table_lines(table, node)
    arrays = {line.path for _, line in headers if line.kind == "array-header"}
    present = tomllib.loads(text)
    for path, items in plan.appends:
        found, value = lane.get_path(present, list(path))
        if found and path not in arrays:
            raise MergeError(f"cannot add {len(items)} item(s) to {lane.key_path(list(path))}: the file defines it as an "
                             f"inline array, which text cannot extend; write it as [[{lane.key_path(list(path))}]] items"
                             + ("; it is empty, so removing the key is enough" if value == [] else ""))
        for item in items:
            block += array_item_lines(path, item)
    if block:
        groups.setdefault(len(lines), []).append(([ADDED_NOTE, *block[1:]], False))
    out = []
    for number, line in enumerate(lines):
        for added, _attached in groups.get(number, []):
            out.extend(item + newline for item in added)
        out.append(line.text)
    result = "".join(out)
    at_end = groups.get(len(lines), [])
    # Keys that belong to the file's last table come first: whatever follows them is a header of its own.
    for added, attached in [*(group for group in at_end if group[1]), *(group for group in at_end if not group[1])]:
        if result and not result.endswith(("\n", "\r")):
            result += newline
        if not attached and result and not result.endswith(newline * 2):
            result += newline   # one blank line between what the file had and the tables added
        result += "".join(item + newline for item in added)
    return result


def running_codex_pids(name: str) -> list:
    """The pids of the processes whose executable name is exactly `name`, from `pgrep -x`. `pgrep` exits 0 when it found
    some and 1 when it found none; any other status means the check itself failed (an option it refuses, no /proc, a
    signal), and the empty answer that comes with it would switch the refusal off, so this raises instead and the step
    stops. apply_codex_lane.codex_processes makes the same call and drops the status, which is why it is not used here."""
    command = f"pgrep -x {name}"
    try:
        done = subprocess.run(["pgrep", "-x", name], capture_output=True, text=True, errors="replace", check=False,
                              stdin=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        raise ProcessCheckError(f"the check for a running Codex could not run `{command}` ({error}), so whether one runs "
                                "is not known; nothing is written; install pgrep (procps) and run `--apply` again") from None
    if done.returncode not in (0, 1):
        status = (f"was ended by signal {-done.returncode}" if done.returncode < 0
                  else f"exited with status {done.returncode}")
        detail = next((line.strip() for line in reversed(done.stderr.splitlines()) if line.strip()), "")
        raise ProcessCheckError(f"the check for a running Codex failed: `{command}` {status}"
                                f"{': ' + detail if detail else ''} (it exits 0 when it finds a process and 1 when it "
                                "finds none), so whether one runs is not known; nothing is written; fix the check and "
                                "run `--apply` again")
    return done.stdout.split()


def process_command_line(pid: str) -> list:
    """The words of the command line of process `pid` (the program first), or [] when it cannot be read. Where there is a
    /proc (Linux) they are the arguments exactly as they were passed, read from /proc/<pid>/cmdline. Where there is none
    (macOS) they come from `ps -ww -o command= -p <pid>` (the command column only, at any width), which prints the
    arguments joined by spaces, so an argument that holds a space is split into several words. Neither reads the
    environment of the process, and only a pid made of digits is looked up."""
    pid = str(pid)
    if not re.fullmatch(r"[0-9]+", pid):
        return []
    if (PROC / "self").exists():
        try:
            raw = (PROC / pid / "cmdline").read_bytes()
        except OSError:
            return []
        raw = raw[:-1] if raw.endswith(b"\0") else raw     # the kernel ends the last argument with a NUL too
        return [part.decode("utf-8", "replace") for part in raw.split(b"\0")] if raw else []
    try:
        done = subprocess.run(["ps", "-ww", "-o", "command=", "-p", pid], capture_output=True, text=True, errors="replace",
                              timeout=10, check=False, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return []
    return done.stdout.split() if done.returncode == 0 else []


def app_server_pids(pids: list) -> list:
    """The pids among `pids` that run Codex's background app-server: `app-server` is an argument of the command line
    (not the program), as `codex app-server --listen unix://` starts it. Only the hint of the refusal depends on this: the
    refusal itself is `pgrep -x`'s finding, and a command line that cannot be read just leaves the hint out."""
    return [pid for pid in pids if "app-server" in process_command_line(pid)[1:]]


def holds_secret_name(value) -> bool:
    """Whether a table or array inside a value has a key whose name looks like a secret."""
    if isinstance(value, dict):
        return any(SECRET_NAME.search(str(key)) or holds_secret_name(item) for key, item in value.items())
    if isinstance(value, list):
        return any(holds_secret_name(item) for item in value)
    return False


def shown(path: tuple, value) -> str:
    """A value for the terminal: TOML text, bounded, and hidden when the key's name, or a key inside the value, looks like
    a secret."""
    if SECRET_NAME.search(path[-1]) or holds_secret_name(value):
        return "<hidden: the key's name looks like a secret>"
    try:
        text = toml_value(value)
    except ConfigError:
        text = repr(value)
    text = " ".join(text.split())
    return text if len(text) <= SHOWN_WIDTH else text[:SHOWN_WIDTH - 3] + "..."


def merge_report(plan: MergePlan) -> list:
    """What a merge adds and what it keeps, as lines for the terminal."""
    lines = []
    if plan.tables:
        lines.append("tables added: " + ", ".join(f"[{lane.key_path(list(path))}]" for path, _ in plan.tables))
    top = [lane.key_path(list(path)) for path, _ in plan.keys if len(path) == 1]
    nested = [lane.key_path(list(path)) for path, _ in plan.keys if len(path) > 1]
    if top:
        lines.append("top-level keys added: " + ", ".join(top))
    if nested:
        lines.append("keys added to tables the file has: " + ", ".join(nested))
    for path, items in plan.appends:
        lines.append(f"rules added to {lane.key_path(list(path))}: {len(items)}, after the file's own")
    for path, have, want in plan.conflicts:
        lines.append(f"conflict kept: {lane.key_path(list(path))}: the file has {shown(path, have)}; the render has "
                     f"{shown(path, want)}")
    return lines


# ---------------------------------------------------------------------------------------------------------------
# apply

class Apply:
    """One --apply run: the steps, each reported as applied, current, planned, left out, skipped or failed."""

    def __init__(self, args: argparse.Namespace):
        self.args, self.root, self.dry = args, args.root, args.dry_run
        self.home = Path(args.home) if args.home else Path.home()
        self.outcomes: list = []
        self.changed = False
        self.stage: Path | None = None
        self.authorization: dict = {}   # authorization piece key -> added, kept or same, as each step found the file

    # -- plumbing
    def say(self, step: str, text: str) -> None:
        print(f"{step}: {text}")

    def record(self, step: str, outcome: str, text: str = "") -> None:
        self.outcomes.append((step, outcome))
        self.say(step, f"{outcome}" + (f": {text}" if text else ""))

    def env(self) -> dict:
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CONFIG_DIR", "CODEX_HOME")}
        env["HOME"] = str(self.home)
        return env

    def tool(self, step: str, argv: list) -> bool:
        """Run one repository tool as a child process; its output is shown, its failure is this step's, and
        self.changed says whether it reported a change (an install, a registration, a write)."""
        result = subprocess.run([sys.executable, "-B", *argv], env=self.env(), stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=300)
        lines = [line for line in (result.stdout + result.stderr).splitlines() if line.strip()]
        for line in lines:
            self.say(step, f"  {line}")
        self.changed = any(CHANGE_REPORT.search(line) and "already" not in line for line in lines)
        return result.returncode == 0

    def done(self, step: str, ok: bool, detail: str = "") -> None:
        """Record a finished tool call: failed, planned (a dry run), applied (it changed something) or current."""
        self.record(step, "failed" if not ok else "planned" if self.dry else "applied" if self.changed else "current",
                    detail)

    def binary(self, name: str, explicit: str | None) -> str | None:
        """The client's own binary: the native installer's, never the ecosystem launcher's directory."""
        if explicit:
            return explicit if Path(explicit).is_file() else None
        eco = (Path(self.values["ECO_ROOT"]) / "bin").resolve()
        entries = [p for p in os.environ.get("PATH", "").split(":") if p and Path(p).resolve() != eco]
        entries.append(str(self.home / ".local" / "bin"))
        return shutil.which(name, path=":".join(entries))

    # -- the run
    def run(self) -> int:
        args = self.args
        if not args.host or not HOST_NAME.fullmatch(args.host):
            print(f"--apply needs --host NAME, which matches {HOST_NAME.pattern}", file=sys.stderr)
            return 2
        if not self.dry and any(os.environ.get(v) for v in ("CLAUDE_CONFIG_DIR", "CODEX_HOME")) and (
                self.home.resolve() == Path.home().resolve()):
            print("refused: CLAUDE_CONFIG_DIR or CODEX_HOME is set, and this tool configures ~/.claude and ~/.codex "
                  "under --home; unset it for this run", file=sys.stderr)
            return 2
        try:
            self.results, self.manifest, self.plan, errors, _ = analyse(
                self.root, authorization=args.with_authorization_settings)
            if errors:
                print("apply refused: the check fails:\n  " + "\n  ".join(errors), file=sys.stderr)
                return 1
            self.values = host_values(args.host, self.plan, self.home, wired_path_dirs(self.results))
            self.files = render(self.root, self.results, self.plan, self.values, self.manifest)
            interims = wired_interims(self.results, self.manifest)
            owed = owed_acknowledgements(self.root) if interims else []
        except (ConfigError, render_config.RenderError, OSError, KeyError, ValueError) as error:
            print(f"apply failed: {error}", file=sys.stderr)
            return 1
        if owed:
            # The gate of amendment 3 (wave-2 code-search ruling, change 1), recorded in the wave-2 section of
            # docs/decisions/2026-10-02-new-wsl-layer-consensus.md: no interim install is wired before both acknowledgements.
            why = (f"the render wires the interim installs of {', '.join(interims)} (amendment 3 of the manifest's decision "
                   f"rule), and the acknowledgement of the wave-2 batch is still owed by {', '.join(owed)} "
                   f"({CONSENSUS_REL}, wave2.acknowledgements_owed)")
            if not self.dry:
                print(f"apply refused: {why}; nothing is written. Record both acknowledgements, then run again.",
                      file=sys.stderr)
                return 1
            print(f"note: a real run refuses now: {why}")
        self.eco = Path(self.values["ECO_ROOT"])
        self.codex_home = self.home / ".codex"
        self.wired = {v.piece.key: v for v in self.results if v.wired}
        if REMOTE_PLUGIN_PIECE in self.wired:
            cache = self.codex_home / "plugins" / "cache" / REMOTE_MARKETPLACE
            try:
                names, servers = remote_plugin_rules(self.codex_home)
                if names or servers:
                    self.files["codex.config.toml"] = with_remote_plugin_rules(self.files["codex.config.toml"], names,
                                                                               servers)
            except (ConfigError, OSError, ValueError) as error:
                print(f"apply failed: the account's remote plugins in {cache} could not be read: {error}", file=sys.stderr)
                return 1
            # Planned, not done: the codex-config step writes the rules and reads them back, or fails and says so.
            print(f"remote plugins: {len(names)} skill name rule(s) and {sum(len(v) for v in servers.values())} plugin MCP "
                  f"server off switch(es) planned, read from {cache} (wave-2 skills ruling, change 5); they are in place "
                  "once the codex-config step has written and read them back")
        mode = "DRY RUN, nothing is written and no client runs" if self.dry else "applying"
        print(f"home {self.home}; eco root {self.eco}; {mode}")
        declared = render_config.load_host_values(args.host)["HOME"].rstrip("/")
        if declared != str(self.home).rstrip("/"):
            print(f"note: the host value file puts HOME at {declared}; the paths under it are moved under {self.home}")
        with tempfile.TemporaryDirectory(prefix="new-wsl-stage-") as stage:
            self.stage = Path(stage)
            for name, text in self.files.items():
                (self.stage / name).write_text(text, encoding="utf-8")
            for step in STEPS:
                if step in args.skip:
                    self.record(step, "skipped", "--skip")
                    continue
                try:
                    getattr(self, "step_" + step.replace("-", "_"))()
                except (OSError, subprocess.SubprocessError, ConfigError, ValueError, icp.InstallError,
                        file_io.ApplyError, managed_block.Refused) as error:
                    self.record(step, "failed", str(error))
        self.report_authorization()
        print("summary: " + "; ".join(f"{step} {outcome}" for step, outcome in self.outcomes))
        return 1 if any(outcome == "failed" for _, outcome in self.outcomes) else 0

    def report_authorization(self) -> None:
        """One line before the summary. Without the option the authorization settings are left to the clients' own defaults.
        With it the line starts with one of the words of AUTHORIZATION_OUTCOMES: `applied` (every wired setting reached and
        one added), `partly applied` (one added, one not reached), `kept` (every one reached, none added), `not applied`
        (none added and one not reached, or none wired), and `would be applied` and `would be partly applied` in a dry run.
        Then it says what each setting came to: added, kept (the file's own value), already the same, or not reached
        because its step was skipped or failed."""
        if not self.args.with_authorization_settings:
            print("authorization settings: left to the clients' own defaults (Claude Code permissions.defaultMode and "
                  "skipDangerousModePermissionPrompt, Codex approval_policy and sandbox_mode, the trust_level of the wired "
                  "Codex projects, and the tool approval modes and allow rules of the wired MCP servers are not written, "
                  f"and a value of theirs that a file has is not touched; {AUTHORIZATION_OPTION} adds the ones a file "
                  "lacks)")
            return
        verdict_of = {v.piece.key: v for v in self.results if v.authorization and v.wired}
        by_status = {status: [authorization_label(key) for key in verdict_of if self.authorization.get(key) == status]
                     for status in ("added", "kept", "same")}
        parts = ([f"added: {', '.join(by_status['added'])}"] if by_status["added"] else []) + (
            [f"kept your value: {', '.join(by_status['kept'])}"] if by_status["kept"] else []) + (
            [f"already the same: {', '.join(by_status['same'])}"] if by_status["same"] else [])
        missed: dict = {}
        for key, verdict in verdict_of.items():
            if key in self.authorization:
                continue
            step = AUTHORIZATION_STEP.get(verdict.piece.group, verdict.piece.group)
            outcome = next((o for s, o in reversed(self.outcomes) if s == step), None)
            how = {"skipped": "was skipped", "failed": "failed", None: "did not run"}.get(outcome, f"ended {outcome}")
            missed.setdefault((step, how), []).append(authorization_label(key))
        parts += [f"not reached, its step {step} {how}: {', '.join(labels)}" for (step, how), labels in missed.items()]
        if not verdict_of:
            state = "not applied"
            parts = ["no authorization setting is wired: the map leaves each out, or its slot does not install"]
        elif missed:
            state = ("would be partly applied" if self.dry else "partly applied") if by_status["added"] else "not applied"
        elif by_status["added"]:
            state = "would be applied" if self.dry else "applied"
        else:
            state = "kept"
        print(f"authorization settings: {state} ({AUTHORIZATION_OPTION}; {'; '.join(parts)})")

    # -- Claude
    def wired_files(self, prefix: str) -> list:
        return [v.piece.value for v in self.results if v.wired and v.piece.key.startswith(prefix)]

    def backup_differing(self, step: str, pairs: list) -> None:
        for source, target in pairs:
            if target.is_file() and target.read_bytes() != source.read_bytes():
                if self.dry:
                    self.say(step, f"would back up {target} before replacing it")
                else:
                    self.say(step, f"backed up {target} -> {file_io.write_backup(target)}")

    def step_claude_hooks(self) -> None:
        names = self.wired_files("claude/profile/hook-file/")
        self.backup_differing("claude-hooks", [(icp.HOOKS[n], self.home / ".claude" / "hooks" / n) for n in names])
        argv = [str(ROOT / "tools/adoption/install_claude_profile.py"), "--only", "guard", "--home", str(self.home)]
        for name in names:
            argv += ["--hook", name]
        self.done("claude-hooks", self.tool("claude-hooks", argv + (["--dry-run"] if self.dry else [])),
                  f"{len(names)} wired file(s)")

    def step_claude_agents(self) -> None:
        names = self.wired_files("claude/profile/agent/")
        self.backup_differing("claude-agents", [(icp.AGENTS_SRC_DIR / n, self.home / ".claude" / "agents" / n)
                                                for n in names])
        argv = [str(ROOT / "tools/adoption/install_claude_profile.py"), "--only", "agents", "--home", str(self.home)]
        for name in names:
            argv += ["--agent", name]
        self.done("claude-agents", self.tool("claude-agents", argv + (["--dry-run"] if self.dry else [])),
                  f"{len(names)} project agent(s)")
        for name, gap in agent_gaps(self.root, self.results, self.plan).items():
            self.say("claude-agents", f"  {name} names {len(gap['mcp_tools'])} MCP tool(s) of servers that are not wired "
                     f"and {len(gap['skills'])} skill(s) the plan does not install; nothing installs them")

    def step_claude_mcp(self) -> None:
        rendered = self.stage / "mcp-servers.json"
        servers = icp.render_servers(json.loads(rendered.read_text()), self.home, self.eco)
        if self.dry:
            for name, spec in servers.items():
                self.say("claude-mcp", "  would run: " + shlex.join(icp.mcp_add_command("claude", name, spec))
                         + "  (a dry run does not ask the client what is registered)")
            self.record("claude-mcp", "planned", f"{len(servers)} server(s)")
            return
        claude = self.binary("claude", self.args.claude_bin)
        if claude is None:
            self.record("claude-mcp", "failed", f"no claude binary (looked in PATH and {self.home}/.local/bin; "
                        "pass --claude-bin); the plan's claude-code row installs it")
            return
        ok = self.tool("claude-mcp", [str(ROOT / "tools/adoption/install_claude_profile.py"), "--only", "mcp",
                                      "--home", str(self.home), "--eco-root", str(self.eco), "--claude-bin", claude,
                                      "--mcp-template", str(rendered)])
        self.done("claude-mcp", ok, f"{len(servers)} server(s) through {claude}")

    def step_claude_settings(self) -> None:
        """The template and the WSL overlay in one merge (the overlay wins, as the bootstrap's second apply makes it
        win), so there is one backup and one write. A settings file that already holds the result is left alone."""
        target = self.home / ".claude" / "settings.json"
        current = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
        wanted = file_io.merge_settings(json.loads((self.stage / "settings.json").read_text(encoding="utf-8")),
                                        json.loads((self.stage / "settings.linux-wsl2.overlay.json").read_text(
                                            encoding="utf-8")))
        # A setting the map marks keep_existing (the theme, picked at Claude Code's first start) and every authorization
        # setting is a person's choice: the file's own value stays, and the render's is not written over it.
        found = {}
        for verdict in self.results:
            if not (verdict.wired and (verdict.entry.keep_existing or verdict.authorization)
                    and verdict.piece.group in ("claude/settings", "claude/overlay")):
                continue
            path = list(verdict.piece.path)
            if isinstance(path[-1], int):
                # A rule of a permission list (an allow rule): the file has it or it is added; the merge unions the list.
                present, rules = lane.get_path(current, path[:-1])
                found[verdict.piece.key] = ("same" if present and isinstance(rules, list) and verdict.piece.value in rules
                                            else "added")
                continue
            have, mine = lane.get_path(current, path), lane.get_path(wanted, path)
            if have[0] and mine[0]:
                name = ".".join(str(part) for part in path)
                if strict_equal(have[1], mine[1]):
                    found[verdict.piece.key] = "same"
                else:
                    self.say("claude-settings", f"  kept your {name}: {json.dumps(have[1])} (the render has "
                             f"{json.dumps(mine[1])})")
                    found[verdict.piece.key] = "kept"
                drop_path(wanted, tuple(path))
            else:
                found[verdict.piece.key] = "added"
        merged = file_io.merge_settings(current, wanted)
        if target.is_file() and merged == current:
            self.record("claude-settings", "current", f"{target} already holds the wired settings")
        elif self.dry:
            changed = sorted(key for key in merged if merged.get(key) != current.get(key))
            self.record("claude-settings", "planned", f"would merge into {target}: {', '.join(changed)}")
        else:
            (self.stage / "settings.merged.json").write_text(json.dumps(wanted, indent=2) + "\n", encoding="utf-8")
            ok = self.tool("claude-settings", [str(ROOT / "tools/adoption/apply_claude_settings.py"), "--template",
                                               str(self.stage / "settings.merged.json"), "--target", str(target)])
            self.done("claude-settings", ok)
        if self.outcomes[-1][1] != "failed":
            self.authorization.update({key: status for key, status in found.items() if is_authorization_piece(key)})

    def step_claude_launcher(self) -> None:
        verdict = self.wired.get(LAUNCHER_PIECE)
        if verdict is None:
            self.record("claude-launcher", "left out", "the claude-code slot does not install")
            return
        target = self.eco / "bin" / "claude"
        if target.parent.resolve() == (self.home / ".local" / "bin").resolve():
            self.record("claude-launcher", "failed", f"{target.parent} is the native installer's bin directory: a "
                        "launcher there would replace the client it execs")
            return
        data = launcher_bytes(self.root / BOOTSTRAP_REL)
        if not (self.home / ".local" / "bin" / "claude").is_file():
            self.say("claude-launcher", f"  {self.home}/.local/bin/claude is not there yet: the plan's claude-code row "
                     "installs it, and the launcher runs it")
        if target.is_file() and target.read_bytes() == data:
            self.record("claude-launcher", "current", str(target))
        elif self.dry:
            self.record("claude-launcher", "planned", f"would write {target}")
        else:
            if target.is_file() or target.is_symlink():
                self.say("claude-launcher", f"  backed up {target} -> {file_io.write_backup(target)}")
            target.parent.mkdir(parents=True, exist_ok=True)
            lane.atomic_write(target, data, 0o755, lane.sha256_file(target))
            self.record("claude-launcher", "applied", f"wrote {target}")

    def instruction_step(self, step: str, piece: str, subcommand: list) -> None:
        """Install one filtered block through managed_block.py, which keeps every line outside its markers. Its
        --dry-run is a global option, so it comes before the subcommand."""
        verdict = next(v for v in self.results if v.piece.key == piece)
        if not verdict.wired:
            self.record(step, "left out", verdict.reason)
            return
        argv = [str(ROOT / "tools/adoption/managed_block.py"), "--home", str(self.home)]
        argv += ["--dry-run"] if self.dry else []
        self.done(step, self.tool(step, argv + subcommand))

    def step_claude_md(self) -> None:
        self.instruction_step("claude-md", CLAUDE_MD_PIECE, [
            "claude-md", "--target", str(self.home / ".claude" / "CLAUDE.md"),
            "--example", str(self.stage / RENDERED_BLOCKS[CLAUDE_MD_PIECE])])

    def step_codex_md(self) -> None:
        self.instruction_step("codex-md", CODEX_MD_PIECE, [
            "codex-md", "--codex-home", str(self.codex_home),
            "--template", str(self.stage / RENDERED_BLOCKS[CODEX_MD_PIECE])])

    # -- Codex
    def codex_guard(self) -> tuple:
        """(the pids of the running Codex processes, what to do about them). A running Codex writes the same
        config.toml, so neither write of this step may start while one runs, and none may start when the check for one
        fails: ProcessCheckError ends the step as failed, in a dry run too."""
        running = running_codex_pids(self.args.codex_process_name)
        daemons = app_server_pids(running)
        how = ("close the Codex sessions" + (f", stop the app-server daemon (pid {', '.join(daemons)}) with `codex "
                                              "app-server daemon stop`" if daemons else "") + ", then run `--apply` again")
        return running, how

    def codex_refusal(self, running: list, how: str) -> str:
        return (f"{len(running)} {self.args.codex_process_name} process(es) running (pids {', '.join(running)}); a "
                f"running Codex writes the same config.toml: {how}")

    def codex_dry_note(self, running: list, how: str) -> str:
        return (f" (a {self.args.codex_process_name} process runs now, {len(running)}: "
                f"{how.replace(', then run `--apply` again', '')} before the real run)")

    def step_codex_config(self) -> None:
        """A Codex home without config.toml gets the render (codex_home.py); one with a config.toml gets the merge. The
        install plan itself leaves a config.toml behind (`codex plugin marketplace add` writes a table), so the merge is
        the usual case on the new distribution. A running Codex stops either write before it starts: codex_home.py's own
        creation of a missing file has no such check, so this step makes it first."""
        config = self.codex_home / "config.toml"
        if os.path.lexists(config):
            self.merge_codex_config(config)
            return
        running, how = self.codex_guard()
        if running and not self.dry:
            self.record("codex-config", "failed", self.codex_refusal(running, how))   # nothing is written
            return
        if running:
            self.say("codex-config", f"  DRY RUN: {self.codex_dry_note(running, how).strip()}")
        # --keep-hook-trust and --keep-project-trust: the render's [hooks.state] approvals and [projects] trust grants are
        # the ones the map wires (a grant only with --with-authorization-settings), which the merge into an existing
        # config.toml adds too, so a new home and a second run end with the same file.
        argv = [str(ROOT / "tools/adoption/codex_home.py"), "--rendered", str(self.stage / "codex.config.toml"),
                "--eco-root", str(self.eco), "--codex-home", str(self.codex_home), "--keep-hook-trust",
                "--keep-project-trust"]
        codex = self.binary("codex", self.args.codex_bin)
        if codex:
            argv += ["--codex", codex]
        self.done("codex-config", self.tool("codex-config", argv + (["--dry-run"] if self.dry else [])))
        if self.outcomes[-1][1] != "failed":
            self.authorization.update({v.piece.key: "added" for v in self.results
                                       if v.authorization and v.wired and v.piece.group == "codex/config"})

    def merge_codex_config(self, config: Path) -> None:
        """Merge, never rewrite: every key and table the file has stays as it is, what the render has and the file lacks is
        added, and a value that differs stays (shown beside the render's). The file is backed up first, read back after
        the write and put back from memory when it is not the merge. `features.daemon_auto_start` goes through Codex's
        own writer when a codex binary is at hand, as codex_home.py does; every other key is a text edit that the
        read-back proves. A running Codex writes the same file, so the write waits until none runs."""
        step = "codex-config"
        try:
            rendered = tomllib.loads((self.stage / "codex.config.toml").read_text(encoding="utf-8"))
            if config.is_symlink() or not config.is_file():
                raise MergeError(f"{config} is a symlink or not a regular file, so it is not written through; compare it "
                                 "with codex.config.toml from `--render --host <host> --out <dir>` by hand")
            original = config.read_bytes()
            try:
                existing = tomllib.loads(original.decode("utf-8"))
            except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
                raise MergeError(f"{config} is not valid UTF-8 TOML ({error}); fix it, then run again") from None
            plan = plan_merge(existing, rendered)
            adds_daemon = (not lane.get_path(existing, list(DAEMON_PATH))[0]
                           and lane.get_path(plan.expected, list(DAEMON_PATH))[0])
            writer = self.binary("codex", self.args.codex_bin) if adds_daemon else None
            text_plan = plan.without(DAEMON_PATH) if writer else plan
            new_text = None
            if text_plan.keys or text_plan.tables or text_plan.appends:
                new_text = merge_toml_text(original.decode("utf-8"), text_plan)
                wanted = copy.deepcopy(plan.expected)
                if writer:
                    drop_path(wanted, DAEMON_PATH)
                difference = first_difference(tomllib.loads(new_text), wanted)
                if difference is not None:
                    raise MergeError(f"the edited text does not read back as the merge (it differs at "
                                     f"{lane.key_path(list(difference))}); nothing is written")
        except (MergeError, OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
            self.record(step, "failed", str(error))
            return
        for line in merge_report(plan):
            self.say(step, f"  {line}")
        found = {}
        for verdict in self.results:
            if verdict.authorization and verdict.wired and verdict.piece.group == "codex/config":
                # A piece's path is the template's: a key that names a placeholder (a project's trust grant under
                # projects."${PROJECT_ROOT}") is looked up as the render filled it.
                path = [string.Template(part).safe_substitute(self.values) if isinstance(part, str) else part
                        for part in verdict.piece.path]
                have = lane.get_path(existing, path)
                found[verdict.piece.key] = ("added" if not have[0] else "same" if strict_equal(
                    have[1], lane.get_path(rendered, path)[1]) else "kept")
        changes = new_text is not None or writer is not None
        label = "merged with conflicts kept" if plan.conflicts else "applied"
        if not changes:
            self.record(step, "merged with conflicts kept" if plan.conflicts else "current",
                        f"{config} already holds every key of the render"
                        + (f"; {len(plan.conflicts)} value(s) differ and stay as the file has them" if plan.conflicts
                           else ""))
            self.authorization.update(found)
            return
        running, how = self.codex_guard()
        if self.dry:
            self.say(step, f"  DRY RUN: would back up {config} and merge the render into it, nothing written"
                     + (self.codex_dry_note(running, how) if running else ""))
            self.record(step, "planned", f"{config}")
            self.authorization.update(found)
            return
        if running:
            self.record(step, "failed", self.codex_refusal(running, how))
            return
        mode = stat.S_IMODE(config.stat().st_mode)
        backup = file_io.write_backup(config)
        touched = False
        try:
            if new_text is not None:
                lane.atomic_write(config, new_text.encode("utf-8"), mode, lane.sha256_bytes(original))
                touched = True
            if writer:
                touched = True
                self.codex_disable_daemon(writer)
            difference = first_difference(tomllib.loads(config.read_bytes().decode("utf-8")), plan.expected)
            if difference is not None:
                raise MergeError(f"read-back: the file does not equal the merge (it differs at "
                                 f"{lane.key_path(list(difference))})")
        except (MergeError, OSError, subprocess.SubprocessError, lane.Failed, tomllib.TOMLDecodeError,
                UnicodeDecodeError) as error:
            if not touched:   # the file changed under this run before anything was written: leave it as it now is
                self.record(step, "failed", f"{error} (backup {backup})")
                return
            restored = self.restore_config(config, original, mode)
            self.record(step, "failed", f"{error}; " + ("the file is back as it was" if restored else
                        "THE RESTORE FAILED: copy the backup over the file") + f" (backup {backup})")
            return
        self.record(step, label, f"merged into {config} (backup {backup})")
        self.authorization.update(found)

    def codex_disable_daemon(self, codex: str) -> None:
        """Codex's own writer for features.daemon_auto_start (codex-rs/cli/src/main.rs disable_feature_in_config)."""
        result = subprocess.run([codex, "features", "disable", "daemon_auto_start"],
                                env=lane.codex_env(self.codex_home, self.env()), stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=codex_home.CODEX_TIMEOUT_SECONDS, check=False)
        if result.returncode != 0:
            raise MergeError(f"`codex features disable daemon_auto_start` exited {result.returncode}: "
                             f"{lane.last_line(result.stderr) or lane.last_line(result.stdout)}")

    def restore_config(self, config: Path, original: bytes, mode: int) -> bool:
        try:
            lane.atomic_write(config, original, mode, lane.sha256_file(config))
            return config.read_bytes() == original
        except (OSError, lane.Failed):
            return False

    def step_codex_files(self) -> None:
        """The two profiles and the role carriers, created only when absent, as apply_codex_lane.py creates them."""
        items, groups = [], {}
        for target_name, group, staged in (("stack-worker.config.toml", "codex/stack-worker",
                                            "codex.stack-worker.config.toml"),
                                           ("omniroute.config.toml", "codex/omniroute", "codex.omniroute.config.toml")):
            if any(v.wired and v.piece.group == group for v in self.results):
                items.append((self.stage / staged, self.codex_home / target_name))
                groups[self.codex_home / target_name] = group
        items += [(codex_roles.ROLES_SOURCE / name, self.codex_home / "agents" / name)
                  for name in self.wired_files("codex/role/")]  # none while the map leaves the carriers out
        states = []
        for source, target in items:
            data = source.read_bytes()
            state = lane.file_state(target.read_bytes() if target.is_file() else None, data)
            if state == "create" and not self.dry:
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                os.chmod(target.parent, 0o700)
                lane.atomic_write(target, data, 0o600, None, create_only=True)
            if target in groups:   # an authorization setting of the profile: added with the file, or the file's own stays
                self.authorization.update({v.piece.key: {"create": "added", "same": "same", "differs": "kept"}[state]
                                           for v in self.results if v.authorization and v.wired
                                           and v.piece.group == groups[target]})
            states.append(state)
            shown = {"create": "would create" if self.dry else "created", "same": "already there",
                     "differs": "differs from the render and is never overwritten"}[state]
            self.say("codex-files", f"  {target.name}: {shown}")
        done = ("planned" if self.dry else "applied") if "create" in states else "current"
        self.record("codex-files", done, f"{len(items)} file(s)")

    # -- login shell
    def step_login_path(self) -> None:
        extra = []
        for relative in wired_path_dirs(self.results):
            extra += ["--extra-dir", str(self.home / relative)]
        if PATH_BLOCK_PIECE not in self.wired:
            self.record("login-path", "left out", "the map does not wire the managed PATH block")
            return
        argv = [str(ROOT / "tools/adoption/managed_block.py"), "--home", str(self.home)]
        argv += ["--dry-run"] if self.dry else []
        argv += ["profile-path", "--eco-root", str(self.eco), *extra]
        self.done("login-path", self.tool("login-path", argv))

    def step_verify(self) -> None:
        if self.dry:
            self.record("verify", "skipped", "a dry run starts no shell")
            return
        servers = json.loads((self.stage / "mcp-servers.json").read_text())["mcpServers"]
        # A stdio server runs a command a login shell must find; an http server (ai-memory) runs none here.
        commands = (spec["command"] for spec in servers.values() if "command" in spec)
        names = list(dict.fromkeys(["claude", "codex", "mise", *commands]))
        found = login_shell_resolution(self.home, names)
        launcher = self.eco / "bin" / "claude"
        problems = []
        for name, path in found.items():
            self.say("verify", f"  a login shell finds {name}: {path or 'nothing (not installed here yet)'}")
        if found.get("claude") and Path(found["claude"]).resolve() != launcher.resolve():
            problems.append(f"claude resolves to {found['claude']}, not the launcher {launcher}")
        self.record("verify", "failed" if problems else "verified", "; ".join(problems))


def launcher_bytes(bootstrap: Path) -> bytes:
    """The ecosystem `claude` launcher exactly as adoption/bootstrap-linux.sh's install_native writes it: that function
    is cut out of the script and run in a scratch directory beside a stub native client, so no text is copied here.
    The version floor is 0.0.0, so the function keeps the client it finds and its download is never reached; the
    stub `fetch` fails if anything asks for one."""
    match = re.search(r"(?ms)^install_native\(\) \{.*?^\}$", bootstrap.read_text(encoding="utf-8"))
    if match is None:
        raise ConfigError(f"install_native is not in {bootstrap}")
    with tempfile.TemporaryDirectory(prefix="new-wsl-launcher-") as scratch:
        base = Path(scratch)
        (base / "home" / ".local" / "bin").mkdir(parents=True)
        (base / "bin").mkdir()
        (base / "cache").mkdir()
        stub = base / "home" / ".local" / "bin" / "claude"
        stub.write_text("#!/bin/sh\necho '99.0.0 (Claude Code)'\n", encoding="utf-8")
        stub.chmod(0o755)
        harness = (f"set -euo pipefail\ncache_dir={shlex.quote(str(base / 'cache'))}\n"
                   f"bin_dir={shlex.quote(str(base / 'bin'))}\n"
                   "fetch() { echo 'the launcher is generated without downloading a client' >&2; return 1; }\n"
                   + match.group(0) + "\ninstall_native claude-code 0.0.0 https://example.invalid/claude 0 claude\n")
        system = adoption_status.LAUNCHER_LOGIN_PATH
        bash = shutil.which("bash", path=system)
        if bash is None:
            raise ConfigError(f"no bash in {system} to run the bootstrap's install_native")
        result = subprocess.run([bash, "-c", harness], env={"HOME": str(base / "home"), "PATH": system},
                                capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        if result.returncode != 0:
            raise ConfigError(f"the bootstrap's install_native failed: {result.stderr.strip()[-300:]}")
        return (base / "bin" / "claude").read_bytes()


def login_shell_resolution(home: Path, names: list) -> dict:
    """{name: path or None}: where `command -v` finds each name in a Bash login shell started as a Windows Terminal
    profile's `bash -lc` starts one, from the fixed environment scripts/adoption_status.py uses."""
    bash = shutil.which("bash", path=adoption_status.LAUNCHER_LOGIN_PATH)
    if bash is None:
        raise ConfigError("no bash for the login-shell probe")
    env = {"HOME": str(home), "PATH": adoption_status.LAUNCHER_LOGIN_PATH}
    env.update({k: os.environ[k] for k in ("USER", "LOGNAME") if os.environ.get(k)})
    script = "; ".join(f'printf "%s=%s\\n" {shlex.quote(n)} "$(command -v {shlex.quote(n)})"' for n in names)
    result = subprocess.run([bash, "-l", "-c", script], env=env, cwd="/", capture_output=True, text=True, timeout=30,
                            stdin=subprocess.DEVNULL)
    found = {}
    for line in result.stdout.splitlines():
        name, _, path = line.partition("=")
        if name in names:
            found[name] = path or None
    return found


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="check the map against the manifest, plan and templates")
    mode.add_argument("--render", action="store_true", help="write the wired pieces for --host into --out")
    mode.add_argument("--apply", action="store_true", help="put the wired pieces in place for --host")
    mode.add_argument("--write-blocks", action="store_true",
                      help="write the two filtered instruction blocks under adoption/new-wsl/ from their sources")
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="the catalog checkout whose map, templates, manifest and plan are read (default: this one)")
    parser.add_argument("--host", help="adoption/hosts/<name>.json, the host value file")
    parser.add_argument("--out", type=Path, help="--render: the directory to write")
    parser.add_argument("--home", help="--apply: the home directory to configure (default: the current user's)")
    parser.add_argument("--claude-bin", help="--apply: the claude binary (default: the native installer's, from PATH)")
    parser.add_argument("--codex-bin", help="--apply: the codex binary (default: the native installer's, from PATH)")
    parser.add_argument("--dry-run", action="store_true", help="--apply: report each step; run no client, write nothing")
    parser.add_argument("--with-authorization-settings", action="store_true",
                        help="--render and --apply: also render and write the authorization settings, the ones that grant "
                             "a permission or suppress a confirmation (Claude Code permissions.defaultMode and "
                             "skipDangerousModePermissionPrompt, Codex approval_policy and sandbox_mode, the trust_level "
                             "of the host's main checkout in Codex, and the tool approval mode of a Codex MCP server "
                             "whose slot installs it). By default they "
                             "are neither rendered nor written and a value a file already has is never touched; with this "
                             "option a missing one is added and a differing one is kept and printed beside the render's. "
                             "Use it only on a host whose owner asked for the repository's permission practice.")
    parser.add_argument("--codex-process-name", default="codex",
                        help="--apply: the executable name whose running processes stop either write of the Codex "
                             "config.toml, the merge into an existing one and the creation of an absent one (default: "
                             "codex, as codex_home.py and apply_codex_lane.py); a `pgrep -x` that cannot run or exits "
                             "with a status other than 0 or 1 stops them too")
    parser.add_argument("--skip", action="append", choices=STEPS, default=[], help="--apply: leave this step out")
    parser.add_argument("--json", action="store_true", help="--check: print the piece table as JSON")
    parser.add_argument("--dropped", action="store_true",
                        help="--check or --write-blocks: print every unit the filter left out of the two blocks, in full")
    parser.add_argument("--markdown", action="store_true",
                        help="--check: print the three Markdown tables of the decision record (the pieces that are not "
                             "wired, the authorization settings and the agents' gaps), then the list of the units the "
                             "filter left out, and nothing else")
    return parser


def cmd_write_blocks(args: argparse.Namespace) -> int:
    try:
        results, manifest, _, errors, _ = analyse(args.root, check_blocks=False)
        if errors:
            print("write refused: the check fails:\n  " + "\n  ".join(errors), file=sys.stderr)
            return 1
        generated = generate_blocks(args.root, unwired_names(results, manifest))
    except (ConfigError, OSError, KeyError, ValueError) as error:
        print(f"write failed: {error}", file=sys.stderr)
        return 1
    for piece, (relative, text, dropped) in generated.items():
        path = args.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        changed = not path.is_file() or path.read_text(encoding="utf-8") != text
        if changed:
            path.write_text(text, encoding="utf-8")
        print(f"{'wrote' if changed else 'kept'} {path} ({len(dropped)} unit(s) of {BLOCK_TEXT_REL[piece]} left out)")
    if args.dropped:
        sys.stdout.write(dropped_text(args.root, generated))
    return 0


def main(argv: list | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.write_blocks:
        return cmd_write_blocks(args)
    if args.check:
        return cmd_check(args)
    if args.render:
        return cmd_render(args)
    return Apply(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
