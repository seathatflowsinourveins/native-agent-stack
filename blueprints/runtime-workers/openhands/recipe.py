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


def llm_config(config, model=None):
    result = dict(config["llm"])
    selected = model or result["model"]
    if not isinstance(selected, str) or not re.fullmatch(r"[A-Za-z0-9_./:-]+", selected):
        raise ValueError("invalid_model")
    # LiteLLM strips its openai provider prefix; the gateway receives selected.
    result["model"] = "openai/" + selected
    result["base_url"] = config["runtime"]["gateway_base_url"]
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
