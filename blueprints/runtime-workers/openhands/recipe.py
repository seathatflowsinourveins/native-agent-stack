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
# Phase 2 (O1): the agent reaches its arm's gateway only through the per-attempt
# proxy alias on the internal run network (config/proxy-nginx.conf); the
# proxy's upstream port selects the arm.
PROXY_BASE_URL = "http://gw:8081/v1"
# Header-selected combos in the 20129 apply record read back at
# 2026-09-28T03:50:11Z (all twelve engines globally off there). The engines-on
# default stays the round-3 "allow-lossy"; the control arm sends none.
COMPRESSION_COMBOS = frozenset({
    "allow-lossy", "fw-ccr", "fw-codex-responses", "fw-headroom", "fw-lite", "fw-rtk", "fw-session-dedup",
})
DEFAULT_COMPRESSION = "allow-lossy"


def read_json(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tool_filter(policy, additional=()):
    """FastMCP 3.2.0 multi-server names use one underscore, not two."""
    parts = [r"terminal", r"file_editor", *additional]
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


def arm_config(arm="control", model=None, base_url=None, compression=None):
    """Round-3 common contract; provider prefix belongs to LiteLLM only.

    SDK@fcc102a llm/llm.py:442-446; coordinator's 2026-09-27 one-slash probe.
    Entry-gateway model matching is explicit: OmniRoute logs the routed model.
    Both arms call PROXY_BASE_URL; gateway_upstream is the proxy's fixed
    upstream, so the rendered proxy config and this selection cannot disagree.
    """
    if arm not in {"control", "engines-on"}:
        raise ValueError("unknown_arm")
    port = 20128 if arm == "control" else 20129
    selected = model or ("cx/gpt-6-astra-max" if arm == "control" else "sharedgw/gpt-6-astra-max")
    valid = (isinstance(selected, str) and selected in {
                 "cx/gpt-6.1-sol", "cx/gpt-6.1-sol-max", "cx/gpt-6-sol-max", "cx/gpt-6-sol-medium",
                 "cx/gpt-6-astra", "cx/gpt-6-astra-max",
             }
             if arm == "control" else selected == "sharedgw/gpt-6-astra-max")
    if not valid:
        raise ValueError("gateway_requires_gpt6_route_for_selected_arm")
    if base_url is not None and base_url != PROXY_BASE_URL:
        raise ValueError("base_url_must_match_arm")
    if arm == "control":
        if compression is not None:
            raise ValueError("control_arm_sends_no_compression_header")
        combo = None
    else:
        combo = DEFAULT_COMPRESSION if compression is None else compression
        if combo not in COMPRESSION_COMBOS:
            raise ValueError("unrecorded_compression_combo")
    return {"arm": arm, "requested_model": selected, "base_url": PROXY_BASE_URL,
            "gateway_port": port, "gateway_upstream": f"http://10.0.2.2:{port}/v1",
            "gateway_model": selected.split("/", 1)[1], "gateway_path": "/v1/responses",
            "compression_combo": combo,
            "headers": {"x-omniroute-compression": combo} if combo else {}}


def environment_selection(environment, arm=None):
    """The one reader of OPENHANDS_* selection variables for host and worker.

    An explicit arm (the host CLI flag) wins over OPENHANDS_ARM. An empty
    OPENHANDS_COMPRESSION means unset: the control arm's container gets "".
    """
    return arm_config(arm or environment.get("OPENHANDS_ARM", "control"), environment.get("OPENHANDS_MODEL"),
                      environment.get("OPENHANDS_BASE_URL"), environment.get("OPENHANDS_COMPRESSION") or None)


def llm_config(config, model=None, *, arm="control", base_url=None, compression=None):
    result = dict(config["llm"])
    selected = arm_config(arm, model, base_url, compression)
    if result.get("reasoning_effort") != "max":
        raise ValueError("max_reasoning_effort_required")
    if any(result.get(key) is not None for key in ("temperature", "top_p", "top_k")):
        raise ValueError("gpt6_sampling_parameters_must_be_omitted")
    if result.get("response_format") is not None or result.get("native_tool_calling") is not True:
        raise ValueError("use_native_tool_calling_for_structured_output")
    # LiteLLM strips its openai provider prefix; the gateway receives selected.
    result["model"] = "openai/" + selected["requested_model"]
    result["base_url"] = selected["base_url"]
    result["extra_headers"] = selected["headers"]
    # SDK@dcf401af v1.50.0 LLM.litellm_extra_body is the native extra_body field.
    extra_body = dict(result.get("litellm_extra_body") or {})
    extra_body["reasoning"] = {**(extra_body.get("reasoning") or {}), "effort": "max"}
    result["litellm_extra_body"] = extra_body
    return result


def task_profile(environment):
    """Select an explicit native capability profile; extra services stay off."""
    config = read_json(HERE / "config/profiles.json")
    name = environment.get("OPENHANDS_PROFILE", config["default"])
    if name not in config["profiles"]:
        raise ValueError("unknown_worker_profile")
    return name, {**config["profiles"][name], "delegation": config["delegation"], "goal": config["goal"]}


def profile_skills(skills, manifest, profile):
    """Native skills stay objects; expose only descriptions relevant to this role.

    Bodies and resources remain available through native invoke_skill. Older
    role-less input is accepted for the coding baseline only; other profiles
    need the manifest role metadata recorded by the host before any model call.
    """
    roles = manifest.get("roles")
    if roles is None:
        if profile["role"] != "coding":
            raise ValueError("profile_requires_skill_role_metadata")
        return skills
    relevant = {name: skill for name, skill in skills.items()
                if profile["role"] in roles.get(name, [])
                or name == "verification-before-completion"}
    prefixes = profile.get("skill_prefixes")
    return {name: skill for name, skill in relevant.items() if name.startswith(tuple(prefixes))} if prefixes else relevant


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
