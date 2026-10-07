#!/usr/bin/env python3
"""Produce names-only role denominator metadata; never initialize a client.

Sources: installed Codex app-server generate-json-schema (0.160.1), native
Claude Code --help (version checked per snapshot), and the existing role map.
JSON config extraction uses jq's native keys operator; TOML extraction reads
only table headers and assignment names, parsing synthetic empty tables with
Python's maintained stdlib tomllib. No config scalar value is emitted or used.
This is a metadata counter, not an execution/acceptance harness. No network,
SDK imports, MCP discovery, model calls, installation, or config writes occur.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from datetime import datetime, timezone


NAME = re.compile(r"^[A-Za-z0-9_.@:/+-]+$")
HEADER = re.compile(r"^\s*(\[\[?.*\]\]?)\s*(?:#.*)?$")
KEY = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*=")
JSON_KEY_QUERY = """{
  mcp_server_keys: (.mcpServers // {} | keys),
  enabled_plugin_keys: (.enabledPlugins // {} | keys),
  relevant_section_keys: (keys | map(select(. == "mcpServers" or
    . == "enabledPlugins" or . == "permissions" or . == "skillOverrides"))),
  project_mcp_server_keys: (.projects[$repo].mcpServers // {} | keys)
}"""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_paths(tree: dict, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    paths = []
    for name, value in tree.items():
        path = (*prefix, name)
        paths.append(path)
        if isinstance(value, dict):
            paths.extend(table_paths(value, path))
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            paths.extend(table_paths(value[0], path))
    return paths


def toml_names(path: Path, scope: str) -> dict:
    result = {"scope": scope, "path": str(path), "status": "missing_known_path",
              "explicit_server_keys": [], "plugin_server_keys": [],
              "relevant_section_keys": [], "server_field_keys": []}
    if not path.is_file():
        return result
    servers, plugins, sections, fields = set(), set(), set(), set()
    current: tuple[str, ...] = ()
    malformed_headers = 0
    multiline_delimiter = None
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if multiline_delimiter:
                if multiline_delimiter in line:
                    multiline_delimiter = None
                continue
            assignment = KEY.match(line)
            if assignment:
                # A table-looking line inside a multiline scalar is not a key.
                # Inspect delimiter markers only; do not retain its content.
                remainder = line[assignment.end():].lstrip()
                for delimiter in ('"""', "'''"):
                    if remainder.startswith(delimiter) and remainder.count(delimiter) == 1:
                        multiline_delimiter = delimiter
            match = HEADER.match(line)
            if match:
                try:
                    paths = table_paths(tomllib.loads(match.group(1) + "\n"))
                    current = max(paths, key=len) if paths else ()
                except tomllib.TOMLDecodeError:
                    current = ()
                    malformed_headers += 1
                if current and current[0] in {"mcp_servers", "agents", "skills", "plugins"}:
                    # Paths inside unrelated project/hook/env tables are excluded.
                    sections.add(current[0])
                if len(current) > 1 and current[0] == "mcp_servers":
                    servers.add(current[1])
                if len(current) > 3 and current[0] == "plugins" and current[2] == "mcp_servers":
                    plugins.add(current[3])
            elif current and current[0] == "mcp_servers" and len(current) == 2:
                match = KEY.match(line)
                if match:
                    fields.add(match.group(1))
    result.update(status="keys_extracted", explicit_server_keys=sorted(servers),
                  explicit_server_key_count=len(servers), plugin_server_keys=sorted(plugins),
                  plugin_server_key_count=len(plugins), relevant_section_keys=sorted(sections),
                  server_field_keys=sorted(fields), malformed_header_count=malformed_headers,
                  qualification="TOML server table-header keys only; inline mappings not read. Merge, enabled state and launch selection unknown. Header zero is not effective zero")
    return result


def json_names(path: Path, scope: str, repo: Path) -> dict:
    result = {"scope": scope, "path": str(path), "status": "missing_known_path"}
    if not path.is_file():
        return result
    # Native key listing: no command arguments, env values, permissions or auth
    # values appear in the query result. Never call this on a credential store.
    proc = subprocess.run(["rtk", "proxy", "jq", "-c", "--arg", "repo", str(repo),
                           JSON_KEY_QUERY, str(path)], capture_output=True, text=True, check=False)
    if proc.returncode:
        result.update(status="key_extraction_failed", exit_code=proc.returncode)
        return result
    result.update(json.loads(proc.stdout), status="keys_extracted",
                  qualification="File key count only; enabled state and role grant unknown")
    result["explicit_server_key_count"] = len(result["mcp_server_keys"])
    result["project_server_key_count"] = len(result["project_mcp_server_keys"])
    return result


def skill_listing(root: Path, scope: str) -> dict:
    records = []
    if root.is_dir():
        # Follow only named immediate skill dirs plus .system, never a host-wide
        # recursive search. Read only the frontmatter name; never descriptions.
        candidates = list(root.glob("*/SKILL.md")) + list(root.glob(".system/*/SKILL.md"))
        for path in sorted(set(candidates)):
            if path.is_file():
                declared_name, active = None, False
                with path.open(encoding="utf-8") as stream:
                    for line in stream:
                        if line.strip() == "---":
                            if active:
                                break
                            active = True
                        elif active:
                            match = re.match(r"^name:\s*['\"]?([A-Za-z0-9_.:/+-]+)['\"]?\s*$", line)
                            if match:
                                declared_name = match.group(1)
                                break
                        else:
                            break
                records.append({"name": declared_name, "directory_name": path.parent.name,
                                "path": str(path), "resolved_path": str(path.resolve())})
    return {"scope": scope, "root": str(root), "root_present": root.is_dir(),
            "listing_count": len(records), "skills": records,
            "qualification": "Filesystem listings; enabled/native exposure unknown. Zero applies only to this named root"}


def native_sources(schema_dir: Path) -> dict:
    versions = {}
    for name, executable in [("codex", "codex"), ("claude", str(Path.home() / ".local/bin/claude"))]:
        proc = subprocess.run(["rtk", executable, "--version"], capture_output=True,
                              text=True, timeout=20, check=False)
        match = re.search(r"\b(\d+\.\d+\.\d+)\b", proc.stdout) if not proc.returncode else None
        versions[f"{name}_version"] = match.group(1) if match else None
    claude_flags = ["--agents", "--allowedTools", "--disallowedTools", "--tools",
                    "--mcp-config", "--strict-mcp-config", "--disable-slash-commands"]
    # The filtered help lost --strict-mcp-config despite exit 0. Its result was
    # unusable for grant-field verification; native proxy recovered the flag.
    help_result = subprocess.run(["rtk", "proxy", str(Path.home() / ".local/bin/claude"), "--help"],
                                 capture_output=True, text=True, timeout=20, check=False)
    observed_flags = [flag for flag in claude_flags if flag in help_result.stdout] if not help_result.returncode else []
    jq_result = subprocess.run(["rtk", "proxy", "jq", "--version"], capture_output=True,
                               text=True, timeout=20, check=False)
    jq_match = re.fullmatch(r"jq-(\d+\.\d+(?:\.\d+)?)\s*", jq_result.stdout)
    schemas = []
    selected = ["SkillsListParams", "SkillsListResponse", "ListMcpServerStatusParams",
                "ListMcpServerStatusResponse", "ThreadStartParams"]
    for name in selected:
        path = schema_dir / "v2" / f"{name}.json"
        if path.is_file():
            data = json.loads(path.read_text())
            schemas.append({"path": str(path), "sha256": digest(path),
                            "property_names": sorted(data.get("properties", {})),
                            "selected_nested_property_names": {
                                key: sorted(value.get("properties", {}))
                                for key, value in data.get("definitions", {}).items()
                                if key in {"McpServerStatus", "SkillMetadata", "SkillsListEntry"}}})
    return {**versions, "codex_schema_files": schemas,
            "codex_schema_generated_from_version": "0.160.1",
            "codex_schema_matches_installed_version": versions.get("codex_version") == "0.160.1",
            "codex_methods": ["skills/list", "mcpServerStatus/list"],
            "claude_native_help_flags": observed_flags,
            "claude_native_help_exit_code": help_result.returncode,
            "claude_native_help_sha256": hashlib.sha256(help_result.stdout.encode()).hexdigest(),
            "source_correction": "RTK filtered Claude help omitted --strict-mcp-config; recovered via rtk proxy native --help. Prior absence inference rejected",
            "metadata_primitives": {"toml_headers": f"CPython {sys.version.split()[0]} stdlib tomllib (synthetic empty tables only)",
                                    "json_keys": f"jqlang/jq {jq_match.group(1) if jq_match else 'UNKNOWN'} native keys operator"},
            "upstream_codex_locator": "openai/codex sdk/python and codex-rs/app-server-protocol; installed native schema is current evidence; no network verification attempted"}


def agent_keys(repo: Path, name: str) -> list[dict]:
    records = []
    for path in [repo / ".claude/agents" / f"{name}.md",
                 Path.home() / ".claude/agents" / f"{name}.md"]:
        if not path.is_file():
            continue
        keys, active = [], False
        for line in path.open(encoding="utf-8"):
            if line.strip() == "---":
                if active:
                    break
                active = True
            elif active:
                match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):", line)
                if match:
                    keys.append(match.group(1))
        records.append({"path": str(path), "frontmatter_keys": keys})
    return records


def roles_for_unit(text: str) -> tuple[str, list[str], str]:
    unit = re.split(r"[: (.]", text, maxsplit=1)[0]
    groups = {
        "cc": (["wsl-architecture-design"], "claude"),
        "coop": (["ns2604-coop"], "claude"),
        "5f": (["native-agent-stack-5f"], "claude"),
        "99": (["native-agent-stack-99"], "claude"),
        "agents-research": (["stack-researcher", "landscape-sweep-worker"], "claude-agent"),
        "agents-execution": (["source-scout", "stack-verifier"], "claude-agent"),
        "agents-review": (["evidence-reviewer", "security-reviewer", "semantic-evidence-reviewer"], "claude-agent"),
        "agents-build": (["isolated-builder"], "claude-agent"),
        "Held": (["grand-catalog", "convergence-practice", "overlap-codenav"], "codex"),
    }
    if unit in groups:
        names, client = groups[unit]
    else:
        names = [unit]
        client = "codex" if unit.startswith("lane-") else "sdk" if unit.startswith("sdk-") else "unknown"
    # Do not silently introduce additional roles if the role-map changes.
    for name in names:
        if name not in text and name != unit:
            raise ValueError("Role-map membership changed; require a reviewed mapping")
    return unit, names, client


def produce(args: argparse.Namespace) -> dict:
    repo = args.repo.resolve()
    role_map = json.loads(args.role_map.read_text())
    units = role_map["result"]["synthesis"]["per_unit"]
    readback = json.loads(args.readback.read_text())["servers"]
    if not all(isinstance(k, str) and isinstance(v, list) and
               all(isinstance(t, str) and NAME.fullmatch(t) for t in v)
               for k, v in readback.items()):
        raise ValueError("Readback must contain only namespace/tool-name lists")
    home = Path.home()
    configs = [toml_names(args.codex_home / "config.toml", "codex-base"),
               toml_names(args.codex_home / "omniroute.config.toml", "codex-omniroute-overlay"),
               toml_names(args.codex_home / "stack-worker.config.toml", "codex-stack-worker-overlay"),
               json_names(home / ".claude.json", "claude-user", repo),
               json_names(home / ".claude/settings.json", "claude-user-settings", repo),
               json_names(repo / ".claude/settings.json", "claude-project-settings", repo),
               json_names(repo / ".mcp.json", "claude-project-mcp", repo)]
    for item in args.sdk_home:
        name, separator, value = item.partition("=")
        if not separator or not NAME.fullmatch(name):
            raise ValueError("sdk-home requires NAME=PATH")
        configs.append(toml_names(Path(value) / "config.toml", f"discovered-sdk-home:{name}"))
    roots = [(args.codex_home / "skills", "codex-installed-and-system"),
             (home / ".agents/skills", "shared-installed"),
             (home / ".claude/skills", "claude-installed"),
             (repo / ".claude/skills", "project-claude"),
             (repo / ".agents/skills", "project-shared"),
             (repo / ".codex/skills", "project-codex")]
    for value in args.skill_root:
        name, _, path = value.partition("=")
        roots.append((Path(path), name))
    listings = [skill_listing(root, scope) for root, scope in roots]
    roles, unit_index = [], []
    for index, entry in enumerate(units):
        unit, names, client = roles_for_unit(entry["unit"])
        unit_index.append({"source_index": index, "unit_key": unit, "role_names": names})
        for name in names:
            scopes = [x["scope"] for x in configs if
                      (client.startswith("claude") and x["scope"].startswith("claude-")) or
                      (client == "codex" and x["scope"].startswith("codex-"))]
            skill_scopes = [x["scope"] for x in listings] if client in {"codex", "claude", "claude-agent"} else []
            role = {"name": name, "source_unit_index": index, "client_family": client,
                    "candidate_config_scope_refs": scopes,
                    "candidate_skill_listing_refs": skill_scopes,
                    "candidate_scope_binding": "UNVERIFIED local-host catalogs; role host/cwd binding unknown",
                    "role_bound_server_keys": None, "role_bound_server_key_count": None,
                    "exact_exposed_tool_names": None, "exact_exposed_tool_count": None,
                    "native_exposed_skills": None, "role_grant": "UNKNOWN",
                    "launch_profile": "UNKNOWN", "exposure_status": "UNKNOWN",
                    "qualification": "Candidate names are not verified role grants; null is not zero"}
            if client == "claude-agent":
                role["definition_key_sources"] = agent_keys(repo, name)
            if name == "lane-overlap-token":
                role.update(exact_exposed_tool_names={k: sorted(set(v)) for k, v in sorted(readback.items())},
                            exact_exposed_tool_count=sum(len(set(v)) for v in readback.values()),
                            exact_exposed_tool_scope="MCP/connector namespaces in retained root readback; native/non-MCP tools excluded",
                            exposure_status="observed_parent_root_readback_only",
                            root_namespace_count=len(readback),
                            qualification="Parent confirmed this readback belongs only to the current overlap-token root session. codex_apps is a connector namespace, not an MCP server key")
            roles.append(role)
    return {"schema_version": 2, "kind": "role-wired-name-denominators",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "producer_source": "tools/invocation-monitoring/role_denominators.py",
            "role_map_source": {"path": str(args.role_map), "sha256": digest(args.role_map)},
            "root_readback_source": {"path": str(args.readback), "sha256": digest(args.readback)},
            "native_sources": native_sources(args.native_schema_dir),
            "unit_count": len(units), "role_count": len(roles), "unit_index": unit_index,
            "unique_resolved_skill_path_count": len({s["resolved_path"] for x in listings for s in x["skills"]}),
            "config_name_catalogs": configs, "skill_filesystem_listings": listings, "roles": roles,
            "limitations": ["Configuration values, auth stores, descriptions and arguments excluded",
                "Known metadata paths only; graph-excluded folders not used to claim absence",
                "File keys and path-derived skill names do not establish enabled state or role exposure",
                "Overlay explicit zero is not an effective merged zero",
                "Local-host candidate catalogs do not establish another host's wiring",
                "Discovered SDK homes have no verified role/launch binding",
                "Skill listing rows may overlap across roots; unique resolved paths counted separately",
                "Root native/non-MCP tool names are not in the retained MCP readback; total client exposure remains unknown",
                "Runtime role grant/profile/native skill exposure needs a matching native session observation",
                "Native schema generation is offline schema evidence, not provider or tool execution"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ["repo", "role-map", "readback", "codex-home", "native-schema-dir", "out"]:
        parser.add_argument(f"--{key}", type=Path, required=True)
    parser.add_argument("--sdk-home", action="append", default=[])
    parser.add_argument("--skill-root", action="append", default=[])
    args = parser.parse_args()
    payload = produce(args)
    args.out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    args.out.parent.chmod(0o700)
    # Only the requested private output is written. O_EXCL prevents replacing
    # another worker's artifact; create a new output filename for later snapshots.
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, separators=(",", ":"), sort_keys=True)
        stream.write("\n")
    print(json.dumps({"unit_count": payload["unit_count"], "role_count": payload["role_count"],
                      "config_scope_count": len(payload["config_name_catalogs"]),
                      "skill_listing_count": sum(x["listing_count"] for x in payload["skill_filesystem_listings"]),
                      "artifact": str(args.out)}))


if __name__ == "__main__":
    main()
