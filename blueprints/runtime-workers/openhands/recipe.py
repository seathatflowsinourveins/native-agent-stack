"""Pure configuration helpers; SDK references are listed in README.md.

No SDK imports, service calls, credential discovery or installation on import.
Codex tool limits are translated to the SDK's native filter_tools_regex.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from string import Template


HERE = Path(__file__).resolve().parent


def read_json(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tool_filter(policy):
    """FastMCP 3.2.0 multi-server names use one underscore, not two."""
    parts = [r"terminal", r"file_editor"]
    for server, limits in policy.items():
        if not limits.get("enabled", True):
            continue
        prefix = re.escape(server + "_")
        if "enabled_tools" in limits:
            parts.extend(prefix + re.escape(name) for name in limits["enabled_tools"])
        else:
            denied = limits.get("disabled_tools", [])
            exclusion = "(?!(?:" + "|".join(map(re.escape, denied)) + ")$)" if denied else ""
            parts.append(prefix + exclusion + r"[A-Za-z][A-Za-z0-9_]*")
    return r"^(?:" + "|".join(parts) + r")$"


def render_mcp(variables):
    config = read_json(HERE / "config/mcp.template.json")

    def expand(value):
        if isinstance(value, str):
            return Template(value).substitute(variables)
        if isinstance(value, list):
            return [expand(item) for item in value]
        if isinstance(value, dict):
            return {key: expand(item) for key, item in value.items()}
        return value

    config = expand(config)
    for name, server in config.items():
        if server["transport"] == "stdio":
            server["cwd"] = "/workspace"
            server.setdefault("env", {}).update({
                "XDG_CACHE_HOME": f"/state/mcp/{name}/cache",
                "XDG_CONFIG_HOME": f"/state/mcp/{name}/config",
                "XDG_DATA_HOME": f"/state/mcp/{name}/data",
                "XDG_STATE_HOME": f"/state/mcp/{name}/state",
            })
    config["qmd"]["env"].update({
        "QMD_CONFIG_DIR": "/state/mcp/qmd/config",
        "INDEX_PATH": "/state/mcp/qmd/catalog.sqlite",
    })
    return config


def arm_config(arm="control", model=None, base_url=None):
    """Round-3 common contract; provider prefix belongs to LiteLLM only.

    SDK@fcc102a llm/llm.py:442-446; coordinator's 2026-09-27 one-slash probe.
    Entry-gateway model matching is explicit: OmniRoute logs the routed model.
    """
    if arm not in {"control", "engines-on"}:
        raise ValueError("unknown_arm")
    port = 20128 if arm == "control" else 20129
    selected = model or ("cx/gpt-6-astra-max" if arm == "control" else "sharedgw/gpt-6-astra-max")
    valid = (isinstance(selected, str) and re.fullmatch(r"cx/gpt-6(?:-[a-z0-9]+)*", selected)
             if arm == "control" else selected == "sharedgw/gpt-6-astra-max")
    if not valid:
        raise ValueError("gateway_requires_gpt6_route_for_selected_arm")
    expected_url = f"http://10.0.2.2:{port}/v1"
    if base_url is not None and base_url != expected_url:
        raise ValueError("base_url_must_match_arm")
    return {"arm": arm, "requested_model": selected, "base_url": expected_url,
            "gateway_port": port, "gateway_model": selected.split("/", 1)[1],
            "gateway_path": "/v1/responses",
            "headers": {"x-omniroute-compression": "allow-lossy"} if arm == "engines-on" else {}}


def llm_config(config, model=None, *, arm="control", base_url=None):
    result = dict(config["llm"])
    selected = arm_config(arm, model, base_url)
    if result.get("reasoning_effort") != "max":
        raise ValueError("max_reasoning_effort_required")
    if result.get("temperature") is not None and result["temperature"] <= 0.1:
        raise ValueError("gateway_temperature_must_exceed_0_1_or_be_omitted")
    if result.get("response_format") is not None or result.get("native_tool_calling") is not True:
        raise ValueError("use_native_tool_calling_for_structured_output")
    # LiteLLM strips its openai provider prefix; the gateway receives selected.
    result["model"] = "openai/" + selected["requested_model"]
    result["base_url"] = selected["base_url"]
    result["extra_headers"] = selected["headers"]
    return result


def inventory(root):
    """Byte and type inventory; symlinks, special files and additions are visible."""
    root = Path(root)
    if not root.is_dir():
        return {}
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = "symlink"
        elif path.is_file():
            result[relative] = digest(path)
        elif path.is_dir():
            result[relative + "/"] = "directory"
        else:
            result[relative] = "special"
    return result
