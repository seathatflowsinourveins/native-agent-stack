"""Public fragment identifiers from Microsoft's supported UUIDv5 recipe.

Ported from nativestack-practice@a7b8018524575cabbd979e6f2e1c84ee6e94700f:
checks/check-terminal-profiles.py:39–44. Official recipe:
https://learn.microsoft.com/en-us/windows/terminal/json-fragment-extensions
(last updated 2025-11-12; checked 2026-10-06).
The namespace is a public platform constant, not a client/session identifier.
"""
from copy import deepcopy
import uuid

FRAGMENT_NAMESPACE = uuid.UUID(hex="f65ddb7e706b44998a5040313caf510a")
FRAGMENT_FOLDER = "NativeStack"


def derived_guid(folder: str, name: str) -> str:
    application = uuid.uuid5(FRAGMENT_NAMESPACE, folder.encode("UTF-16LE").decode("ASCII"))
    return "{" + str(uuid.uuid5(application, name.encode("UTF-16LE").decode("ASCII"))) + "}"


def _guid_key(value):
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def project_terminal_settings(
    settings, canonical_profiles, *, legacy_native_stack_profiles=(),
    default_name="NativeStack2604 - Claude",
):
    """Project supplied settings without reading or writing any host state.

    microsoft/terminal@dc8ae365847d41f62d1ebca93815bb00959bc12f:
    src/cascadia/TerminalSettingsModel/CascadiaSettingsSerialization.cpp:915,
    1074-1092 loads every fragment and merges profiles by GUID. Its
    doc/cascadia/profiles.schema.json supplies the hidden override. Explicitly
    supplied legacy metadata belongs to the NativeStack fragment source; an
    existing settings entry establishes ownership only with that source.

    Return (projected_settings, changed). When changed is false, the caller
    should preserve the original settings file bytes, including JSONC comments.
    """
    canonical = {}
    desired = None
    for profile in canonical_profiles:
        key = _guid_key(profile.get("guid"))
        if key is None or key in canonical:
            raise ValueError("Canonical profile GUIDs must be valid and unique")
        canonical[key] = profile
        if profile.get("name") == default_name:
            if desired is not None:
                raise ValueError("Default profile name must be unique")
            desired = profile
    if desired is None:
        raise ValueError("Canonical default profile is missing")

    profile_settings = settings.get("profiles", {})
    if isinstance(profile_settings, dict):
        entries = profile_settings.get("list", [])
    elif isinstance(profile_settings, list):
        entries = profile_settings
    else:
        raise ValueError("Settings profiles must be an object or array")
    if not isinstance(entries, list) or any(not isinstance(p, dict) for p in entries):
        raise ValueError("Settings profile list must contain objects")

    obsolete = {}
    observed = [(p, False) for p in entries]
    observed.extend((p, True) for p in legacy_native_stack_profiles)
    for profile, legacy in observed:
        source = profile.get("source")
        if source != FRAGMENT_FOLDER and not (legacy and source is None):
            continue
        name = profile.get("name")
        if not isinstance(name, str) or not name.startswith("NativeStack2604 - "):
            continue
        guid = profile.get("guid")
        if guid is None and legacy:
            guid = derived_guid(FRAGMENT_FOLDER, name)
        key = _guid_key(guid)
        if key is None:
            raise ValueError("Owned observed profiles need a valid GUID")
        if key not in canonical:
            obsolete[key] = guid

    projected = deepcopy(settings)
    projected_profiles = projected.get("profiles", {})
    projected_entries = (projected_profiles.get("list", [])
                         if isinstance(projected_profiles, dict) else projected_profiles)
    for key, guid in obsolete.items():
        matches = [p for p in projected_entries if _guid_key(p.get("guid")) == key]
        if any(p.get("source") not in (None, FRAGMENT_FOLDER) for p in matches):
            raise ValueError("Obsolete GUID has a conflicting profile source")
        if matches:
            for profile in matches:
                profile["hidden"] = True
        else:
            projected_entries.append({"guid": guid, "source": FRAGMENT_FOLDER, "hidden": True})
    if obsolete:
        if isinstance(projected_profiles, dict):
            projected_profiles["list"] = projected_entries
        projected["profiles"] = projected_profiles

    current_default = settings.get("defaultProfile")
    desired_key = _guid_key(desired["guid"])
    name_collision = any(
        p.get("name") == default_name and _guid_key(p.get("guid")) != desired_key
        for p, _legacy in observed
    )
    if (_guid_key(current_default) != desired_key
            and (current_default != default_name or name_collision)):
        projected["defaultProfile"] = desired["guid"]
    return projected, projected != settings
