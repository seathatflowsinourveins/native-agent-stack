#!/usr/bin/env python3
"""Build/check W-BOOK from published recommendations and explicit W-PROF evidence.

Reference implementation: scripts/build_ecosystem.py at 20ea4ae23a18565676823b9e3a23541c2100bb39.
This projection performs no installation, model call, or target-host acceptance.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shlex
import sys
from urllib.parse import unquote, urlsplit

try:
    from .build_ecosystem import canonical_json, digest, require
    from .catalog_decisions import safe_file
    from .new_wsl_profile import validate_default_installs
    from .validate import PRIVATE_CONTENT
except ImportError:
    from build_ecosystem import canonical_json, digest, require
    from catalog_decisions import safe_file
    from new_wsl_profile import validate_default_installs
    from validate import PRIVATE_CONTENT


BASE = "evidence/artifacts/new-wsl-clean-install-selection-20261001"
OWNERSHIP = f"{BASE}/ownership.json"
SELECTION = f"{BASE}/selection.json"
PACKETS = f"{BASE}/packets"
PREREGISTRATION = f"{BASE}/preregistration.json"
EDITION = "catalogs/foundation/new-wsl-architecture-20261001.json"
RESEARCH = "catalogs/landscape/research-state.json"
TRADING = "catalogs/landscape/us-equities.json"
DISTRO = "adoption/platforms/linux-wsl2-new-distro.md"
ADOPTION = "adoption/manifest.json"
PROFILE = "adoption/new-wsl-profile.json"
DEFAULTS_MANIFEST = "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json"
OUTPUTS = ("docs/new-wsl-handbook.md", "docs/new-wsl-handbook.json")
SOURCES = (OWNERSHIP, SELECTION, EDITION, RESEARCH, TRADING, DISTRO,
           ADOPTION, PREREGISTRATION)
FAMILIES = ("claude", "codex")
# The manifest producer's closed sets: rows_of() states and row kinds and apply_convergence() outcomes in
# assemble_manifest.py at 675bdd51c96af28aa98012d9e4ff772a77a38f3d. "" is a slot with no decision yet (counted as open).
# Its later apply_consensus() step adds the row kind "consensus": such a row comes from the layer-consensus record that
# the manifest names under sources.consensus, is never definitive, and carries an outcome that is none of OUTCOMES.
# An owner batch of that record (amendment 4, wave 3, 2026-10-04) adds the row kind "owner_decision" with the outcome
# OWNER_ROW_OUTCOME, and gives a row whose decided default installed nothing an owner default (OWNER_DEFAULT_OUTCOME),
# keeping the fields it replaced, with their outcome of the rounds, under overturned.fields.
SLOT_STATES = {"", "definitive", "resolved", "split", "measurement"}
ROW_KINDS = {"first_round", "added", "judged", "pinned", "project_practice", "no_blind_default_today", "consensus",
             "owner_decision"}
OUTCOMES = {"final", "installed_on_critic", "not_installed", "split", "kept"}
OWNER_ROW_OUTCOME, OWNER_DEFAULT_OUTCOME = "added_by_owner_decision", "owner_default"
WAVE_KEY = re.compile(r"wave(?P<number>[2-9]|[1-9][0-9]+)")
HOST_PATH = re.compile(
    r"(?<!\w)/(?:home|Users|tmp|var/tmp)/[^\s<]"
    r"|(?<!\w)/root(?=/|$|[\s'\"`])"
    r"|(?<!\w)/mnt/[a-z]/(?:Users|Documents and Settings)/[^\s<]"
    r"|(?<![A-Za-z0-9])[A-Za-z]:[\\/]",
    re.IGNORECASE,
)
# Published selection.json durable-memory/Hindsight install_command at 20ea4ae.
# This multiline reference contains provider placeholders, not executable shell
# syntax. Bind its whole text before exempting its one named-volume destination.
HINDSIGHT_INSTALL_TEMPLATE_SHA256 = "349e199f6163d419fbd1fb362e2159a77381f0d9acae27651cfa4fbad015f276"

# These are uses explicitly stated in ownership.json, not new tool selections.
REUSES = {
    ("workers", "claude-code (native subagents, worktree isolation, agent teams)"): "native-clients",
    ("workers", "Codex native workers (subagents)"): "native-clients",
    ("workers", "Worktrunk"): "git-github-automation",
    ("isolation", "Worktrunk"): "git-github-automation",
    ("isolation", "Podman (rootless)"): "hosting-services",
    ("semantic-rag", "ollama"): "observation-inference",
    ("scheduling-supervision", "systemd"): "cross:wsl-distro",
}


def host_path_scan_text(value):
    """Allow named-volume destinations only in a simple container run command.

    Uses the stdlib shlex tokenizer, not shell evaluation. The allowlist follows
    Docker's run/volume syntax and Podman's named-volume syntax; see the source
    links in the generator decision. Complex shell text gets no exception.
    Supplied commands are never rewritten or executed.
    """
    if digest(value.encode()) == HINDSIGHT_INSTALL_TEMPLATE_SHA256:
        return value.replace("-v hindsight-data:/home/example/.pg0", "-v hindsight-data:<published-container-destination>")
    if not HOST_PATH.search(value) or any(char in value for char in "\n\r$`"):
        return value
    try:
        lexer = shlex.shlex(value, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""  # Comments are still public text to check.
        words = list(lexer)
    except ValueError:
        return value
    if len(words) < 3 or words[:2] not in (["docker", "run"], ["podman", "run"]):
        return value
    if any(re.fullmatch(r"[();<>|&]+", word) for word in words):
        return value
    switches = {"--rm", "-d", "--detach", "-i", "--interactive", "-t", "--tty", "-it", "-ti"}
    volume_name = r"[A-Za-z0-9][A-Za-z0-9_.-]*"
    i = 2
    while i < len(words):
        word = words[i]
        if word in switches:
            i += 1
            continue
        if not word.startswith("-"):
            # IMAGE ends run options. Never exempt its command/arguments.
            return " ".join(words)
        flag, separator, argument = word.partition("=")
        if flag not in {"-v", "--volume", "--mount"}:
            return value  # Unknown option arity: keep the ordinary path check.
        target = i
        if not separator:
            if i + 1 == len(words):
                return value
            target = i + 1
            argument = words[target]
        if flag in {"-v", "--volume"}:
            fields = argument.split(":")
            if len(fields) in {2, 3} and re.fullmatch(volume_name, fields[0]) and fields[1].startswith("/"):
                fields[1] = "<named-volume-destination>"
            argument = ":".join(fields)
        else:
            fields = argument.split(",")
            parsed = [field.partition("=") for field in fields]
            types = [value for key, equals, value in parsed if key == "type" and equals]
            sources = [value for key, equals, value in parsed if key in {"source", "src"} and equals]
            destinations = [(index, key, value) for index, (key, equals, value) in enumerate(parsed)
                            if key in {"target", "destination", "dst"} and equals]
            if (types == ["volume"] and len(sources) == len(destinations) == 1
                    and re.fullmatch(volume_name, sources[0]) and destinations[0][2].startswith("/")):
                index, key, _ = destinations[0]
                fields[index] = key + "=<named-volume-destination>"
            argument = ",".join(fields)
        words[target] = flag + "=" + argument if separator else argument
        i = target + 1
    return value  # A run without an IMAGE is not an eligible command.


def validate_payload(value):
    """Check all external fields, including metadata omitted by projection."""
    if isinstance(value, str):
        require(not HOST_PATH.search(host_path_scan_text(value)), "host path in handbook input payload")
        for label, pattern in PRIVATE_CONTENT:
            require(not pattern.search(value), f"{label} in handbook input payload")
    elif isinstance(value, dict):
        for key, child in value.items():
            validate_payload(key)
            validate_payload(child)
    elif isinstance(value, list):
        for child in value:
            validate_payload(child)


def public_path(value):
    path = Path(value)
    require(not path.is_absolute() and ".." not in path.parts and "\\" not in value,
            f"source must be a public repository path: {value!r}")
    return path.as_posix()


def index_rows(rows, label):
    result = {}
    for row in rows:
        key = row["layer_id"]
        require(key not in result, f"duplicate layer {key} in {label}")
        result[key] = row
    return result


class Inputs:
    def __init__(self, root):
        self.root = root
        self.sources = {}

    def read(self, path, *, override=None, as_json=True):
        path = public_path(path)
        raw = (override if override is not None else safe_file(self.root, path)).read_bytes()
        self.sources[path] = {"path": path, "sha256": digest(raw)}
        value = json.loads(raw) if as_json else raw.decode("utf-8")
        if override is not None:
            validate_payload(value)
        return value


def profile_fields(entry):
    """Expose supplied facts and name each missing install/acceptance fact."""
    entry = entry or {}
    gaps = list(entry.get("blocking_gaps", []))
    pin = entry.get("pin")
    checksum = entry.get("checksum")
    install = entry.get("install")
    acceptance = entry.get("acceptance")
    if not pin or str(pin).lower() in {"pending", "unknown", "latest"}:
        gaps.append("pin: release or immutable revision pending in W-PROF")
    if not isinstance(checksum, dict) or not re.fullmatch(r"[a-fA-F0-9]{64}", str(checksum.get("value", ""))):
        gaps.append("checksum: real SHA-256 and its source pending in W-PROF")
    elif checksum.get("algorithm") != "sha256" or not checksum.get("source"):
        gaps.append("checksum: algorithm or source pending in W-PROF")
    if isinstance(checksum, dict) and checksum.get("kind") not in {"artifact", "lock"}:
        gaps.append("checksum: source identity does not verify an install artifact or lockfile")
    if not isinstance(install, dict) or not install.get("command") or not install.get("source"):
        gaps.append("install: upstream-documented command and source pending in W-PROF")
    if not isinstance(acceptance, dict) or not acceptance.get("command") or not acceptance.get("source"):
        gaps.append("acceptance: upstream test or documented example and source pending in W-PROF")
    elif re.search(r"(?:--version| -V|version\s*\()", acceptance["command"]) and not re.search(r"&&|;|\n", acceptance["command"]):
        gaps.append("acceptance: a version print is not an upstream test or documented example")
    if entry.get("stage") is None or entry.get("position") is None:
        gaps.append("install order: stage and position pending in W-PROF")
    facts = {"pin": pin, "checksum": checksum, "install": install, "acceptance": acceptance,
             "stage": entry.get("stage"), "position": entry.get("position"),
             "provisioning_status": entry.get("provisioning_status", "pending"),
             "evidence_refs": entry.get("evidence_refs", []),
             "blocking_gaps": list(dict.fromkeys(gaps))}
    for field in ("version_policy", "native_update"):
        if entry.get(field):
            facts[field] = entry[field]
    return facts


def profile_package(entry):
    """Read package identity from canonical npm/PyPI metadata URLs only.

    Uses stdlib urllib.parse and the published registry URL/name formats cited
    in the generator decision. This projects supplied metadata without fetching
    a registry, parsing an install command, or claiming artifact acceptance.
    """
    checksum = (entry or {}).get("checksum")
    source = checksum.get("source") if isinstance(checksum, dict) else None
    if not isinstance(source, str) or re.search(r"[\x00-\x20\x7f]", source):
        return None
    try:
        parsed = urlsplit(source)
        path = unquote(parsed.path, errors="strict")
    except ValueError:
        return None
    if parsed.scheme != "https" or parsed.query or parsed.fragment:
        return None
    if parsed.netloc == "registry.npmjs.org":
        match = re.fullmatch(
            r"/((?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*)/([A-Za-z0-9][A-Za-z0-9.+-]*)", path)
        return "npm:" + match[1] if match else None
    if parsed.netloc == "pypi.org":
        match = re.fullmatch(
            r"/pypi/([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)(?:/([A-Za-z0-9][A-Za-z0-9.!+_-]*))?/json", path)
        return "pypi:" + re.sub(r"[-_.]+", "-", match[1]).lower() if match else None
    return None


def read_verdicts(inputs, path, family, selection_hash, packets, releases):
    if path is None:
        return {}, None
    path = Path(path)
    raw = json.loads(path.read_bytes())
    validate_payload(raw)
    source = raw.get("source_path")
    if source is None:
        require(path.resolve().is_relative_to(inputs.root.resolve()),
                "external verdict input needs a public source_path")
        source = path.resolve().relative_to(inputs.root.resolve()).as_posix()
    data = inputs.read(source, override=path)
    require(data.get("family") == family, f"{family} verdict family mismatch")
    selection_binding = data.get("selection_sha256")
    if selection_binding is not None:
        require(selection_binding == selection_hash,
                f"{family} verdict does not bind the current selection SHA-256")
    records = index_rows(data["layers"], f"{family} verdicts")
    bound = {}
    for layer_id, record in records.items():
        gaps = []
        row_selection = record.get("selection_sha256", selection_binding)
        if row_selection is None:
            gaps.append("selection SHA-256 binding pending")
        else:
            require(row_selection == selection_hash,
                    f"{family}/{layer_id} verdict does not bind the current selection SHA-256")
        packet = packets.get(layer_id)
        packet_binding = record.get("packet_sha256")
        if packet is None or packet_binding is None:
            gaps.append("exact judged packet SHA-256 binding pending")
        else:
            require(packet_binding == packet["sha256"],
                    f"{family}/{layer_id} verdict does not bind the current packet SHA-256")
        requirement_binding = record.get("requirement_sha256")
        requirement_text = record.get("requirement")
        if packet is None or (requirement_binding is None and requirement_text is None):
            gaps.append("explicit judged requirement binding pending")
        else:
            requirement = packet["data"]["requirement"]
            raw_requirement = requirement if isinstance(requirement, str) else canonical_json(requirement)
            if requirement_binding is not None:
                require(requirement_binding == digest(raw_requirement.encode()),
                        f"{family}/{layer_id} requirement binding differs from the current requirement")
            if requirement_text is not None:
                require(requirement_text == requirement,
                        f"{family}/{layer_id} requirement binding differs from the current requirement")
        release_binding = record.get("release_pins")
        if release_binding is None:
            gaps.append("judged release_pins binding pending")
        else:
            require(isinstance(release_binding, dict), f"{family}/{layer_id} release binding must map tool names to pins")
            expected = releases.get(layer_id, {})
            if not expected:
                gaps.append("release binding has no current tool inventory to verify")
            for name in sorted(set(expected) | set(release_binding)):
                if name not in release_binding or expected.get(name) is None:
                    gaps.append(f"release binding pending for {name}")
                else:
                    require(release_binding[name] == expected[name],
                            f"{family}/{layer_id} release binding differs from the current pin for {name}")
        bound[layer_id] = {"status": "pending" if gaps else "published", "source": source,
                           "record": record, "binding_gaps": gaps}
    return bound, source


def inventory_slot_ids(slot):
    """Use assemble_manifest.py rows_of()'s role and multi-default ID rules."""
    if "roles" in slot:
        for role in slot["roles"]:
            yield from inventory_slot_ids(dict(role, slot_id=f"{slot['slot_id']}/{role['slot_id']}"))
    elif isinstance(slot.get("default"), list):
        for part in slot["default"]:
            tail = "".join(char if char.isalnum() else "-" for char in part["name"].lower()).strip("-")[:32]
            yield from inventory_slot_ids(dict(slot, default=part, slot_id=f"{slot['slot_id']}/{tail}"))
    else:
        yield slot["slot_id"]


def manifest_source_path(source):
    """Resolve one provenance entry of the defaults manifest to a public repository path.

    assemble_manifest.py build() at 675bdd51c96af28aa98012d9e4ff772a77a38f3d writes `file`, relative to the
    manifest's folder, for the two compact catalogs, the settlements and the convergence decisions, and `path`,
    relative to the repository root, for the rule and the combined results that convergence.json cites. The
    layer-consensus record that its apply_consensus() step reads is named by `path` as well.
    """
    require(isinstance(source, dict), "defaults manifest source must be an object")
    require(re.fullmatch(r"[a-fA-F0-9]{64}", str(source.get("sha256", ""))), "defaults manifest source needs SHA-256")
    require(("file" in source) != ("path" in source), "defaults manifest source needs exactly one of file or path")
    if "file" in source:
        return (Path(DEFAULTS_MANIFEST).parent / public_path(source["file"])).as_posix()
    return public_path(source["path"])


def read_manifest_sources(inputs, sources, catalogs):
    """Read every source the manifest names and bind each to its declared SHA-256.

    The catalogs, the convergence decisions and the layer-consensus record are parsed because they give the slot
    inventory. The other files are hashed only, so the handbook's provenance lists exactly the inputs the manifest
    rests on.
    """
    data = {}
    for name, source in sources.items():
        path = manifest_source_path(source)
        data[name] = inputs.read(path, as_json=name in catalogs or name in {"convergence", "consensus"})
        require(inputs.sources[path]["sha256"] == source["sha256"].lower(),
                f"defaults manifest source {name} differs from its declared SHA-256")
    return data


def default_slot_inventory(data, catalogs):
    """Bind IDs to the compact catalogs and the added slots that the manifest producer reads.

    Reference: assemble_manifest.py build(), rows_of() and apply_convergence() at
    675bdd51c96af28aa98012d9e4ff772a77a38f3d: one row for each catalog slot, role or multi-default part, one for each
    pinned requirement, and one for each added slot of convergence.json. Its apply_consensus() step adds one row for
    each add_rows entry of the layer-consensus record, where the manifest names that record. Read identifiers and
    owners only; recommendations and states stay supplied.
    """
    inventory, layer_catalogs = {}, {}
    for catalog in catalogs:
        document = data[catalog]
        require(isinstance(document, dict) and isinstance(document.get("layers"), list),
                "defaults manifest slot inventory needs catalog layers")
        for layer in document["layers"] + document.get("cross_rows", []):
            require(layer["layer_id"] not in layer_catalogs, f"duplicate layer in catalog inventory: {layer['layer_id']}")
            layer_catalogs[layer["layer_id"]] = catalog
            identifiers = [identifier for slot in layer.get("slots", []) for identifier in inventory_slot_ids(slot)]
            for pin in document.get("pinned_requirements", []):
                if pin["owner"] == layer["layer_id"]:
                    identifiers.append("pinned/" + "".join(
                        char if char.isalnum() else "-" for char in pin["name"].lower()).strip("-")[:40])
            for identifier in identifiers:
                require(identifier not in inventory, f"duplicate slot in catalog inventory: {identifier}")
                inventory[identifier] = (catalog, layer["layer_id"])
    convergence = data.get("convergence")
    require(convergence is None or isinstance(convergence, dict), "defaults manifest convergence source must be an object")
    for added in (convergence or {}).get("added_slots", []):
        identifier, layer_id = added["slot_id"], added["layer_id"]
        require(layer_id in layer_catalogs, f"added slot {identifier} names an unknown layer: {layer_id}")
        require(identifier not in inventory, f"duplicate slot in catalog inventory: {identifier}")
        inventory[identifier] = (layer_catalogs[layer_id], layer_id)
    for identifier, layer_id, _ in consensus_slots(data):
        require(layer_id in layer_catalogs, f"consensus slot {identifier} names an unknown layer: {layer_id}")
        require(identifier not in inventory, f"duplicate slot in catalog inventory: {identifier}")
        inventory[identifier] = (layer_catalogs[layer_id], layer_id)
    return inventory


def consensus_slots(data):
    """(slot, layer, row kind) of each row that the layer-consensus record adds: in its first batch (add_rows) and in each
    later batch (wave2, wave3, ..., in their numeric order, as assemble_manifest.py folds them), where a batch on the
    owner's decision (it states an owner_rule, amendment 4) adds rows of kind owner_decision and every other batch rows of
    kind consensus; none where the manifest names no such record."""
    consensus = data.get("consensus")
    require(consensus is None or isinstance(consensus, dict), "defaults manifest consensus source must be an object")
    batches = []
    for key in (consensus or {}):
        if key.startswith("wave"):
            match = WAVE_KEY.fullmatch(key)
            require(match is not None, "defaults manifest consensus batch must be named wave<n> with n at least 2")
            batches.append((int(match["number"]), key))
    rows = [(row, "consensus") for row in (consensus or {}).get("add_rows", [])]
    require(isinstance((consensus or {}).get("add_rows", []), list), "defaults manifest consensus rows must be lists")
    for _, key in sorted(batches):
        batch = consensus[key]
        require(isinstance(batch, dict), "defaults manifest consensus batch must be an object")
        added = batch.get("add_rows", [])
        require(isinstance(added, list), "defaults manifest consensus rows must be lists")
        kind = "owner_decision" if "owner_rule" in batch else "consensus"
        rows += [(row, kind) for row in added]
    require(all(isinstance(row, dict) and isinstance(row.get("slot_id"), str)
                and isinstance(row.get("layer_id"), str) for row, _ in rows),
            "defaults manifest consensus source needs slot and layer identifiers")
    return [(row["slot_id"], row["layer_id"], kind) for row, kind in rows]


def require_slot_inventory(identifiers, inventory):
    unknown = sorted(set(identifiers) - set(inventory))
    missing = sorted(set(inventory) - set(identifiers))
    require(not unknown and not missing,
            f"defaults manifest slot inventory differs: unknown ids {unknown}; missing ids {missing}")


def read_default_decisions(inputs, reference, override=None):
    """Project the owner's slot protocol; never derive a decision or readiness.

    Source schema: assemble_manifest.py at 675bdd51c96af28aa98012d9e4ff772a77a38f3d. An empty state is a slot with no
    decision yet and is shown as open, as the producer's own counts name it. A row installs something by the
    producer's rule (a default, and not installs_nothing_extra); the same invariants the producer enforces for a
    split, an unreturned measurement and a not_installed row are checked here so that no row is shown contradicting
    them. Every count is computed from the rows and must equal the manifest's own counts.
    """
    if override is not None:
        require(Path(override).is_file(), "explicit defaults manifest input does not exist")
        value = inputs.read(DEFAULTS_MANIFEST, override=Path(override))
    else:
        path = inputs.root / DEFAULTS_MANIFEST
        if not path.exists() and not path.is_symlink():
            return None
        value = inputs.read(DEFAULTS_MANIFEST)
    validate_payload(value)
    require(isinstance(value, dict) and value.get("schema_version") == 1
            and value.get("kind") == "new-wsl-definitive-manifest", "unsupported defaults manifest schema")
    require(isinstance(value.get("layers"), list) and isinstance(value.get("slots"), list),
            "defaults manifest needs layer and slot lists")
    layers = index_rows(value["layers"], "defaults manifest")
    require(set(layers) == set(reference), "defaults manifest layer inventory differs from the handbook")
    sources = value["sources"]
    require(isinstance(sources, dict), "defaults manifest needs catalog provenance")
    catalogs = sorted({row["catalog"] for row in layers.values()})
    for catalog in catalogs:
        require(catalog in sources, "defaults manifest layer has unknown source catalog")
    source_data = read_manifest_sources(inputs, sources, set(catalogs))
    inventory = default_slot_inventory(source_data, catalogs)
    added_by = {identifier: kind for identifier, _, kind in consensus_slots(source_data)}
    declarations = set()
    for row in layers.values():
        for field in ("owns", "uses"):
            require(isinstance(row.get(field), list)
                    and all(isinstance(item, str) and item.strip() for item in row[field]),
                    "defaults manifest ownership declarations must be text lists")
        for declaration in row["owns"]:
            normalized = declaration.casefold().strip()
            require(normalized not in declarations, "duplicate defaults manifest ownership declaration")
            declarations.add(normalized)
    slots = {layer_id: [] for layer_id in layers}
    identifiers = set()
    kinds, states = {}, {}
    pending = returned = 0
    for slot in value["slots"]:
        layer_id = slot["layer_id"]
        require(layer_id in layers, "defaults manifest slot has unknown layer")
        require(slot["catalog"] == layers[layer_id]["catalog"], "defaults manifest slot catalog differs from its owner")
        identifier = slot["slot_id"]
        require(isinstance(identifier, str) and identifier.strip(), "defaults manifest slot needs an identifier")
        require(identifier not in identifiers, "duplicate slot in defaults manifest")
        identifiers.add(identifier)
        state = slot.get("state", "")
        require(state in SLOT_STATES, "invalid defaults manifest slot state")
        require(isinstance(slot.get("definitive"), bool) and slot["definitive"] == (state == "definitive"),
                "defaults manifest definitive flag differs from its state")
        kind = slot["row_kind"]
        require(kind in ROW_KINDS, "unknown defaults manifest row kind")
        require((kind in ("consensus", "owner_decision")) == (identifier in added_by)
                and (identifier not in added_by or added_by[identifier] == kind),
                f"defaults manifest consensus row differs from the layer-consensus record: {identifier}")
        require(all(isinstance(slot.get(field), str) for field in ("default", "label", "repository", "claude", "gpt")),
                "defaults manifest slot recommendation and provenance must be text")
        require(isinstance(slot.get("job"), str) and slot["job"].strip(),
                f"defaults manifest slot needs its job: {identifier}")
        resolution, measurement = slot.get("resolution"), slot.get("measurement")
        outcome = resolution.get("outcome") if isinstance(resolution, dict) else None
        kept = slot.get("overturned")
        replaced = kept.get("fields") if isinstance(kept, dict) else None
        if kind == "consensus":
            # The producer's rule for a row added by direct consensus: never definitive, and no outcome of the rounds.
            require(isinstance(outcome, str) and outcome.strip() and outcome not in OUTCOMES and not slot["definitive"],
                    f"defaults manifest consensus slot is never definitive and carries no outcome of the rounds: {identifier}")
        elif kind == "owner_decision":
            # Amendment 4: a row the owner added is never definitive and carries the owner's outcome, not one of the rounds.
            require(outcome == OWNER_ROW_OUTCOME and not slot["definitive"],
                    f"defaults manifest owner row is never definitive and carries the owner's outcome: {identifier}")
        elif replaced is not None:
            # Amendment 4: an owner default carries the owner's outcome; the outcome the rounds decided stays, with the
            # fields it replaced, under overturned.fields.
            decided = replaced.get("resolution") if isinstance(replaced, dict) else None
            require(outcome == OWNER_DEFAULT_OUTCOME and not slot["definitive"] and isinstance(decided, dict)
                    and decided.get("outcome") in OUTCOMES,
                    f"defaults manifest owner default needs the owner's outcome and the rounds' outcome it replaced: {identifier}")
        else:
            require(isinstance(resolution, dict) and outcome in OUTCOMES,
                    f"defaults manifest slot needs a known outcome: {identifier}")
        require(kept is None or (isinstance(kept, dict) and isinstance(kept.get("amendment"), dict) and all(
            isinstance(kept["amendment"].get(key), str) and kept["amendment"][key].strip()
            for key in ("date_utc", "by", "decision"))),
                f"defaults manifest owner amendment needs its date, its author and its decision: {identifier}")
        amendments = slot.get("amendments")
        require(amendments is None or (isinstance(amendments, list) and amendments and all(
            isinstance(item, dict) and all(isinstance(item.get(key), str) and item[key].strip()
                                           for key in ("date_utc", "by", "decision"))
            for item in amendments)),
                f"defaults manifest slot amendment needs its date, its author and its decision: {identifier}")
        require(measurement is None or (isinstance(measurement, dict) and isinstance(measurement.get("returned"), bool)),
                f"defaults manifest slot measurement must be empty or say whether it returned: {identifier}")
        require(isinstance(slot.get("installs_nothing_extra"), bool),
                f"defaults manifest slot must say whether it installs anything: {identifier}")
        installs = bool(slot["default"]) and not slot["installs_nothing_extra"]
        waiting = state == "split" or (measurement is not None and not measurement["returned"])
        if waiting or resolution["outcome"] == "not_installed":
            require(slot["installs_nothing_extra"] and not slot["repository"],
                    f"defaults manifest row installs something while it waits or is not installed: {identifier}")
        if measurement is not None:
            pending, returned = pending + (not measurement["returned"]), returned + measurement["returned"]
        kinds[kind] = kinds.get(kind, 0) + 1
        states[state or "open"] = states.get(state or "open", 0) + 1
        slots[layer_id].append({
            "state": state or "open", "installed": installs,
            "not_installed_reason": None if installs else resolution.get("reason") or slot["default"] or slot["label"],
            "record": slot})
    require_slot_inventory(identifiers, inventory)
    for slot in value["slots"]:
        require(inventory[slot["slot_id"]] == (slot["catalog"], slot["layer_id"]),
                f"defaults manifest slot owner differs from inventory: {slot['slot_id']}")
    installed = sum(row["installed"] for rows in slots.values() for row in rows)
    counts = {"layers": len(layers), "slots": len(identifiers),
              "definitive": sum(slot["definitive"] for slot in value["slots"]),
              "by_row_kind": kinds, "by_state": states, "installed": installed}
    if any(re.fullmatch(r"consensus_wave[0-9]+", key) for key in value):
        # Amendment 3 of the decision rule (the layer consensus's wave-2 batch, and every later batch): the rows that carry
        # an interim install, counted apart from the decided installs, as the producer counts them.
        counts["interim"] = sum(1 for slot in value["slots"] if slot.get("interim"))
    require(value["counts"] == counts, "defaults manifest counts differ from its records")
    return {"source": DEFAULTS_MANIFEST,
            "status": "supplied-preview" if override is not None else "published-source",
            "metadata": {key: child for key, child in value.items() if key not in {"layers", "slots"}},
            "inventory": dict(counts, not_installed=len(identifiers) - installed,
                              measurements_pending=pending, measurements_returned=returned,
                              amendments=sum(len(slot.get("amendments", [])) for slot in value["slots"]),
                              owner_amendments=sum(1 for slot in value["slots"] if slot.get("overturned"))),
            "layers": layers, "slots": slots}


FENCE = "`" * 3
# Page anchors: prose that begins the blocks to copy. They locate text; the copied commands and rules are the page's own.
PAIRED_NOTE = "Then record the same five observations from both running distributions at once"
PAIRED_RULE = "Proof: both distributions print the same uid"
GETTY_PROOF = "prints `masked`"


def page_section(page, step):
    """The text of one recipe-page step, from its heading to the next heading."""
    headings = list(re.finditer(rf"^### {re.escape(step)}\. .+$", page, re.MULTILINE))
    require(len(headings) == 1, f"recipe page needs exactly one {step} step")
    rest = page[headings[0].end():]
    following = re.search(r"^#{2,3} ", rest, re.MULTILINE)
    return rest[:following.start()] if following else rest


def page_blocks(section):
    """Split a section into paragraphs and fenced code blocks, in page order.

    A paragraph is ("text", text) and a fenced block is ("code", info string, body).
    """
    blocks, lines, fence = [], [], None
    for line in section.splitlines():
        if fence is None and line.startswith(FENCE):
            if lines:
                blocks.append(("text", "\n".join(lines)))
            lines, fence = [], line[len(FENCE):].strip()
        elif fence is not None and line.startswith(FENCE):
            blocks.append(("code", fence, "\n".join(lines)))
            lines, fence = [], None
        elif fence is None and not line.strip():
            if lines:
                blocks.append(("text", "\n".join(lines)))
            lines = []
        else:
            lines.append(line)
    require(fence is None, "recipe page step ends inside a code fence")
    if lines:
        blocks.append(("text", "\n".join(lines)))
    return blocks


def page_bullet(section, marker):
    """The one list item of a section whose text holds the marker: it starts with `- ` and indented lines continue it."""
    lines = section.splitlines()
    items, current = [], []
    for line in lines:
        if line.startswith("- "):
            items.append(current)
            current = [line]
        elif current and line.startswith("  ") and line.strip():
            current.append(line)
        else:
            items.append(current)
            current = []
    items.append(current)
    found = [" ".join(" ".join(item).split())[2:] for item in items if item and marker in " ".join(item)]
    require(len(found) == 1, f"recipe page needs exactly one list item that holds {marker!r}")
    return found[0]


def paired_record_from_page(distro):
    """Read W5's paired record, its pass rule and its getty mask proof from the recipe page.

    Nothing here is typed: the commands and the rules are the page's own text, so a change of the page changes the
    handbook, and a page that no longer has these blocks stops the generator.
    """
    headings = re.findall(r"^### (W5\. .+)$", distro, re.MULTILINE)
    require(len(headings) == 1, "recipe page needs exactly one W5 step")
    section = page_section(distro, "W5")
    blocks = page_blocks(section)
    starts = [i for i, block in enumerate(blocks)
              if block[0] == "text" and " ".join(block[1].split()).startswith(PAIRED_NOTE)]
    require(len(starts) == 1 and starts[0] + 2 < len(blocks), "recipe page W5 has no paired record")
    note, commands, rule = blocks[starts[0]:starts[0] + 3]
    require(commands[0] == "code" and rule[0] == "text" and " ".join(rule[1].split()).startswith(PAIRED_RULE),
            "recipe page W5 paired record is not a paragraph, a command block and its pass rule")
    masks = [block for block in blocks if block[0] == "code" and "getty@tty1.service" in block[2]]
    require(masks, "recipe page W5 has no getty mask commands")
    return {"source": DISTRO, "step": headings[0],
            "observation_note": " ".join(note[1].split()),
            "observation_commands": commands[2].splitlines(),
            "pass_rule": " ".join(rule[1].split()),
            "getty_mask": {"commands": [line for line in masks[0][2].splitlines() if "getty@tty1.service" in line],
                           "proof": page_bullet(section, GETTY_PROOF)}}


def stage_two_commands_from_page(distro):
    """The command block of F9, the recipe page's hand-off to stage 2."""
    codes = [block for block in page_blocks(page_section(distro, "F9")) if block[0] == "code"]
    require(len(codes) == 1, "recipe page F9 needs exactly one command block")
    return codes[0][2].splitlines()


def build_data(root, profile_path=None, claude_verdicts=None, codex_verdicts=None, defaults_manifest=None):
    root = Path(root)
    inputs = Inputs(root)
    ownership = inputs.read(OWNERSHIP)
    selection = inputs.read(SELECTION)
    edition = inputs.read(EDITION)
    research = inputs.read(RESEARCH)
    trading = index_rows(inputs.read(TRADING)["layers"], TRADING)
    distro = inputs.read(DISTRO, as_json=False)
    adoption = inputs.read(ADOPTION)
    preregistration = inputs.read(PREREGISTRATION)
    selected = index_rows(selection["layers"], SELECTION)
    owners = index_rows(ownership["layers"], OWNERSHIP)
    reference = index_rows(edition["rows"], EDITION)
    default_decisions = read_default_decisions(inputs, reference, defaults_manifest)
    declarations = {}
    for layer_id, row in owners.items():
        for declaration in row["owns"]:
            normalized = declaration.casefold().strip()
            require(normalized not in declarations,
                    f"duplicate ownership declaration: {declaration}")
            declarations[normalized] = layer_id
    require(set(selected) <= set(reference), "selection layer missing from reference universe")
    require(set(owners) <= set(reference), "ownership layer missing from reference universe")
    require(len(research["saturation"]["close_only_when"]) == 5, "expected five finality gates")
    preregistered = {item["layer_id"]: item for item in preregistration["packets"]}
    packets = {}
    for layer_id in selected:
        # Match the maintained packet builder's filename mapping exactly.
        packet_path = f"{PACKETS}/{layer_id.replace(':', '_')}.json"
        packet_data = inputs.read(packet_path)
        packet_hash = inputs.sources[packet_path]["sha256"]
        require(layer_id in preregistered and packet_hash == preregistered[layer_id]["sha256"],
                f"packet differs from preregistration: {layer_id}")
        packets[layer_id] = {"path": packet_path, "data": packet_data, "sha256": packet_hash}
    if profile_path is not None:
        require(Path(profile_path).is_file(), "explicit W-PROF input does not exist")
    profile_path = Path(profile_path) if profile_path else root / PROFILE
    profile = None
    if profile_path.exists():
        raw = json.loads(profile_path.read_bytes())
        validate_payload(raw)
        profile = inputs.read(raw.get("source_path", PROFILE), override=profile_path)
    gaps = [] if profile else ["W-PROF profile has not been published; install metadata and order remain pending."]
    entries = (profile or {}).get("entries", [])
    if default_decisions is not None:
        validate_default_installs(profile or {}, [slot["record"] for slots in default_decisions["slots"].values()
                                                  for slot in slots])
    entry_map = {}
    for entry in entries:
        key = (entry["layer_id"], entry["name"])
        require(key not in entry_map, f"duplicate profile tool {key}")
        require(entry["layer_id"] in reference, f"unknown profile layer {entry['layer_id']}")
        require(entry.get("owner_layer_id") in owners, f"unknown profile owner for {entry['name']}")
        require(entry.get("status") in {"picked", "head-to-head-arm"},
                "profile tool status must be picked or head-to-head-arm; final is derived from five gates")
        entry_map[key] = entry
    packages_by_repository = {}
    for entry in entries:
        package = profile_package(entry)
        if package and entry.get("repository"):
            key = (entry["owner_layer_id"], entry["repository"].rstrip("/").removesuffix(".git"))
            packages_by_repository.setdefault(key, set()).add(package)
    tools_by_key = {}
    layer_tools = {key: [] for key in reference}
    consumed = set()

    def add_tool(layer_id, choice, status, entry=None, extra=False):
        name = choice["name"]
        owner = REUSES.get((layer_id, name), layer_id)
        if extra:
            owner = entry["owner_layer_id"]
        elif entry:
            require(entry["owner_layer_id"] == owner, f"profile owner conflicts with ownership.json: {name}")
        require(owner in owners, f"tool owner missing from ownership.json: {name}")
        require(owners[owner]["owns"], f"tool owner has no ownership declaration: {name}")
        if owner != layer_id and not extra:
            require(owners[layer_id]["uses"], f"tool reuse missing from ownership.json: {name}")
        repository = choice.get("repository")
        if entry and entry.get("repository"):
            require(not repository or entry["repository"].rstrip("/") == repository.rstrip("/"),
                    f"profile repository conflicts with selection: {name}")
            repository = entry["repository"]
        repository_identity = (repository or name).rstrip("/").removesuffix(".git")
        candidates = packages_by_repository.get((owner, repository_identity), set())
        package = profile_package(entry)
        # Only a selection alias without its own profile entry may inherit the
        # sole package. Explicit entries need their own supported URL binding.
        if package is None and entry is None and len(candidates) == 1:
            package = next(iter(candidates))
        # Distribution versions remain distinct comparison arms. npm and PyPI
        # packages in one repository are distinct installables, not aliases.
        identity = (owner, repository_identity,
                    name if layer_id == "cross:wsl-distro" else (package or ""))
        tool_id = digest(canonical_json(identity).encode())[:16]
        if identity not in tools_by_key:
            tools_by_key[identity] = {
                "tool_id": tool_id, "name": name, "aliases": [], "repository": repository,
                "owner_layer_id": owner, "ownership_source": OWNERSHIP,
                "status": status, "used_by": [], "selection_sources": [],
                "documented_install": [], "_entries": [],
            }
            if package:
                tools_by_key[identity]["package_id"] = package
        tool = tools_by_key[identity]
        if name not in tool["aliases"]:
            tool["aliases"].append(name)
        if layer_id == owner:
            tool["name"] = name
        if layer_id not in tool["used_by"]:
            tool["used_by"].append(layer_id)
        if tool_id not in layer_tools[layer_id]:
            layer_tools[layer_id].append(tool_id)
        tool["selection_sources"].append({"source": (profile or {}).get("source_path", PROFILE) if extra else SELECTION,
                                           "layer_id": layer_id, "name": name})
        if choice.get("install_command"):
            item = {"command": choice["install_command"], "source": choice.get("install_source")}
            if item not in tool["documented_install"]:
                tool["documented_install"].append(item)
        if entry:
            tool["_entries"].append(entry)
            tool["status"] = entry["status"]

    for layer_id, row in selected.items():
        require(row["status"] in {"recommended", "compare"}, f"unknown selection status: {row['status']}")
        names = set()
        for choice in row["selection"]:
            require(choice["name"] not in names, f"duplicate selected tool in {layer_id}: {choice['name']}")
            names.add(choice["name"])
            key = (layer_id, choice["name"])
            entry = entry_map.get(key)
            consumed.add(key)
            add_tool(layer_id, choice, "picked" if row["status"] == "recommended" else "head-to-head-arm", entry)
    for key, entry in entry_map.items():
        if key not in consumed:
            add_tool(entry["layer_id"], entry, entry["status"], entry, extra=True)
    tools = list(tools_by_key.values())
    for tool in tools:
        matches = tool.pop("_entries")
        for field in ("pin", "checksum", "install", "acceptance"):
            facts = {canonical_json(entry[field]) for entry in matches if entry.get(field)}
            require(len(facts) <= 1, f"conflicting profile {field} for {tool['name']}")
        merged = {key: value for entry in matches for key, value in entry.items() if value is not None}
        # A user of a shared tool cannot clear blockers supplied by its owner
        # or another user. Preserve every supplied blocker in source order.
        merged["blocking_gaps"] = list(dict.fromkeys(
            gap for entry in matches for gap in entry.get("blocking_gaps", [])
        ))
        tool.update(profile_fields(merged))
        repository_identity = (tool["repository"] or tool["name"]).rstrip("/").removesuffix(".git")
        candidates = packages_by_repository.get((tool["owner_layer_id"], repository_identity), set())
        if not tool.get("package_id") and candidates:
            tool["blocking_gaps"].append(
                "package identity: multiple installable packages share this repository; W-PROF binding pending"
                if len(candidates) > 1 else
                "package identity: explicit W-PROF entry has no supported binding to the repository's identified package")
        if not tool["repository"]:
            tool["blocking_gaps"].append("repository: upstream source pending")
    tools_by_id = {tool["tool_id"]: tool for tool in tools}
    releases = {layer_id: {tools_by_id[key]["name"]: tools_by_id[key]["pin"] for key in keys}
                for layer_id, keys in layer_tools.items()}
    verdicts = {}
    selection_hash = inputs.sources[SELECTION]["sha256"]
    for family, path in zip(FAMILIES, (claude_verdicts, codex_verdicts)):
        verdicts[family] = read_verdicts(inputs, path, family, selection_hash, packets, releases)

    layers = []
    for layer_id, ref in reference.items():
        row = selected.get(layer_id)
        owner = owners.get(layer_id)
        comparison = (profile or {}).get("comparisons", {}).get(layer_id, {})
        if comparison:
            require(comparison.get("selection_sha256") == selection_hash,
                    f"comparison does not bind current selection: {layer_id}")
            require(comparison.get("preregistration_source"),
                    f"comparison needs a preregistration source: {layer_id}")
        missing = []
        packet = packets[layer_id]["data"] if row else None
        if packet:
            requirement = {"text": packet["requirement"], "source": packets[layer_id]["path"], "status": "published"}
        elif layer_id in trading:
            requirement = {"text": trading[layer_id]["requirement"], "source": TRADING, "status": "published"}
        else:
            requirement = {"text": None, "source": None, "status": "pending"}
            missing.append("Requirement for this cross row has not been published in the clean-install packet.")
        if not row:
            missing.append("Clean-install selection and deciding comparison pending from the owning lane.")
        if not owner:
            missing.append("Clean-install owns/uses declaration pending from the owning lane.")
        elif any("compare" in item.lower() for item in owner["owns"]):
            missing.append("Ownership declares comparison groups in prose; W-PROF must enumerate every arm and baseline with its install evidence.")
        families = {}
        for family in FAMILIES:
            records, source = verdicts[family]
            verdict = records.get(layer_id)
            families[family] = verdict or {"status": "pending", "source": None,
                                          "reason": "No verdict file for these recommendation packets was supplied."}
        gate_input = (profile or {}).get("finality", {}).get(layer_id, {})
        gates = {}
        for i in range(1, 6):
            key = f"c{i}"
            gate = gate_input.get(key)
            require(not gate or gate.get("status") in {"met", "partial", "unmet", "pending"},
                    f"invalid finality gate {layer_id}/{key}")
            if gate and gate.get("status") == "met":
                require(gate.get("source"), f"finality gate needs evidence source: {layer_id}/{key}")
            gates[key] = gate or {"status": "pending", "source": None}
        status = "pending" if not row else ("picked" if row["status"] == "recommended" else "head-to-head-arm")
        final = (row and all(gate["status"] == "met" for gate in gates.values())
                 and comparison.get("preregistration_source")
                 and all(value["status"] == "published"
                         and value["record"].get("verdict") == "confirmed"
                         and value["record"].get("material_gaps") == [] for value in families.values())
                 and layer_tools[layer_id]
                 and all(not tools_by_id[key]["blocking_gaps"] for key in layer_tools[layer_id]))
        if final:
            status = "final"
        layers.append({
            "layer_id": layer_id, "title": ref["title"], "catalog": ref["catalog"],
            "requirement": requirement, "status": status,
            "owns": owner["owns"] if owner else [], "uses": owner["uses"] if owner else [],
            "ownership_source": OWNERSHIP if owner else None, "tools": layer_tools[layer_id],
            "family_verdicts": families, "finality": gates,
            "deciding_comparison": {"proposal": row["deciding_comparison"] if row else None,
                                    "proposal_source": SELECTION if row else None,
                                    "preregistration_source": comparison.get("preregistration_source"),
                                    "status": "preregistered" if comparison else "pending target-host experiment preregistration"},
            "overturn_condition": {"text": comparison.get("overturn_condition") or (row["deciding_comparison"] if row else None),
                                   "source": comparison.get("preregistration_source") or (SELECTION if row else None),
                                   "note": "The published proposal includes deciding/overturn conditions; a measured decision is pending."},
            "evidence_class_today": selection["evidence_class"] if row else "pending clean-install assessment",
            "reference_edition": {"source": EDITION, "role": "reference only; no winners, pins or closure inherited"},
            "blocking_gaps": missing,
        })
        if default_decisions is not None:
            layers[-1]["default_slots"] = default_decisions["slots"][layer_id]
            layers[-1]["default_ownership"] = default_decisions["layers"][layer_id]
    final_layers = {row["layer_id"] for row in layers if row["status"] == "final"}
    for tool in tools:
        if tool["owner_layer_id"] in final_layers and not tool["blocking_gaps"]:
            tool["status"] = "final"

    stage1 = re.findall(r"^### (W\d+\. .+)$", distro, re.MULTILINE)
    first_boot = re.findall(r"^### (F[1-8]\. .+)$", distro, re.MULTILINE)
    after_stage2 = re.findall(r"^### (F1[01]\. .+)$", distro, re.MULTILINE)
    profile_id = (profile or {}).get("profile_id")
    native_profiles = {row["id"] for row in adoption["profiles"]}
    if profile_id and profile_id not in native_profiles:
        gaps.append("W-PROF is not registered in adoption/manifest.json; native bootstrap activation is pending.")
    result = {
        "schema_version": 1, "kind": "generated_new_wsl_handbook", "as_of": selection["date_utc"],
        "evidence_class": "repository integration artifact; source projection, not host acceptance",
        "new_host_acceptance_claimed": False,
        "meaning": selection["meaning"], "cross_family_boundary": selection["cross_family"],
        "profile": {"source": (profile or {}).get("source_path", PROFILE), "status": "published" if profile else "pending",
                    "profile_id": profile_id, "native_manifest_registered": profile_id in native_profiles,
                    "host_prerequisites": (profile or {}).get("host_prerequisites", [])},
        "stage_order": [
            {"stage": 1, "source": DISTRO, "steps": stage1, "first_boot_prerequisites": first_boot,
             "boundary": "Recipe order only. The distro recipe is reference evidence; the clean-install image comparison remains open."},
            {"stage": 2, "source": DISTRO, "steps": [
                "Install the selected pinned profile with the first bootstrap command of F9.",
                "Complete the native sign-ins F9 names on this host; they are never copied from another machine.",
                "Configure the same profile with the second bootstrap command of F9; collect its native receipts."],
             "commands": stage_two_commands_from_page(distro),
             "profile_order": (profile or {}).get("stage_order", []),
             "after_bootstrap": after_stage2,
             "boundary": "Per-tool order is the W-PROF stage/position; missing entries block installation."},
        ],
        "comparison_order": [
            {"before": "hosting-services", "after": "isolation", "source": SELECTION},
            {"before": "semantic-rag", "after": "observation-inference", "source": SELECTION},
        ],
        "comparison_order_text": selection["comparison_order"],
        "finality_gates": [{"id": f"c{i}", "requirement": text, "source": RESEARCH}
                           for i, text in enumerate(research["saturation"]["close_only_when"], 1)],
        "paired_proof": paired_record_from_page(distro),
        "trading_boundary": {"text": ownership["trading_rule"], "source": OWNERSHIP},
        "cross_boundaries": ownership["boundary"], "layers": layers, "tools": tools,
        "blocking_gaps": gaps,
        "sources": sorted(inputs.sources.values(), key=lambda source: source["path"]),
    }
    if default_decisions is not None:
        require_slot_inventory([slot["record"]["slot_id"] for layer in layers for slot in layer["default_slots"]],
                               [slot["record"]["slot_id"] for slots in default_decisions["slots"].values()
                                for slot in slots])
        result["default_decisions"] = {key: value for key, value in default_decisions.items()
                                       if key not in {"layers", "slots"}}
    validate_payload(result)
    return result


def link(path, label=None):
    if not path:
        return "pending"
    target = path if path.startswith(("https://", "http://")) else f"../{path}"
    return f"[{label or path}]({target})"


def cell(value):
    if value is None:
        return "pending"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).replace("|", "\\|").replace("\n", " ")


STATE_ORDER = ("definitive", "resolved", "split", "measurement", "open")


def inventory_sentence(counts):
    """One sentence of counts, every one of them computed from the manifest's rows."""
    states = ", ".join(f"{state} {counts['by_state'][state]}" for state in STATE_ORDER if state in counts["by_state"])
    kinds = ", ".join(f"{kind} {count}" for kind, count in sorted(counts["by_row_kind"].items()))
    interim = (f" {counts['interim']} of the slots that install nothing by their decided default carry an interim install "
               "(amendment 3 of the decision rule)." if counts.get("interim") else "")
    return (f"The manifest holds {counts['slots']} slots in {counts['layers']} layers. By state: {states}. "
            f"By row kind: {kinds}. {counts['installed']} slots install something and {counts['not_installed']} install nothing.{interim} "
            f"Measurements not yet returned: {counts['measurements_pending']}; returned: {counts['measurements_returned']}.")


def render_paired_record(paired):
    """The recipe page's W5 paired record: prose is quoted and commands are fenced, all of it read from the page."""
    return [f"### {paired['step']}: the paired record, as the recipe page gives it", "",
            f"The generator copies the next blocks from {link(paired['source'])}; none of their text is typed here.", "",
            "> " + paired["observation_note"], "", FENCE + "sh", *paired["observation_commands"], FENCE, "",
            "> " + paired["pass_rule"], "",
            "The getty mask proof for the new distribution, from the same step:", "",
            FENCE + "powershell", *paired["getty_mask"]["commands"], FENCE, "",
            "> " + paired["getty_mask"]["proof"], ""]


def render_host_prerequisites(data):
    """Each prerequisite the profile declares, then the page's own paired record."""
    lines = ["## Host prerequisites", ""]
    for item in data["profile"]["host_prerequisites"]:
        lines += [f"### {item.get('title') or item['id']}", "", item["requirement"], ""]
        for key, label in (("not_adopted", "Pre-releases"), ("single_distribution", "Single-distribution install"),
                           ("receipt", "Receipt")):
            if item.get(key):
                lines += [f"{label}: {item[key]}", ""]
        if item.get("observations"):
            lines += ["Observations, kept apart from the policy:", ""]
            lines += [f"- {text}" for text in item["observations"]] + [""]
        if item.get("execution_status"):
            lines += [f"Status for the real distribution: **{item['execution_status']}**.", ""]
        if item.get("rehearsal"):
            rehearsal = item["rehearsal"]
            lines += [f"Rehearsal: {rehearsal['result']} Record: {link(rehearsal['record'])}. {rehearsal['scope']}", ""]
        if item.get("gate"):
            lines += [f"Gate: {item['gate']}", ""]
        lines += [f"The gate is executed in {link(item['gate_source'])}.", ""]
        if item.get("sources"):
            lines += ["Sources: " + "; ".join(link(source) for source in item["sources"]) + ".", ""]
    return lines + render_paired_record(data["paired_proof"])


def render_markdown(data):
    lines = ["# New WSL handbook", "", "Generated by `python3 scripts/build_new_wsl_handbook.py --write`. Do not edit this file.", "",
             f"As of {data['as_of']}. {data['evidence_class']}.", "",
             "`picked` means a repository recommendation, `head-to-head-arm` means a comparison input, and `final` requires all five gates and both packet-bound family verdicts. `pending` identifies unpublished inputs.", "",
             data["meaning"], "", data["cross_family_boundary"], "",
             "The architecture edition supplies the row inventory and reference links only. Its source-host winners, pins and closure cells are not new-install decisions.", "",
             "## Stage 1 and stage 2", ""]
    for stage in data["stage_order"]:
        lines += [f"### Stage {stage['stage']}", "", stage["boundary"], "", f"Source: {link(stage['source'])}.", ""]
        lines += [f"{i}. {step}" for i, step in enumerate(stage["steps"], 1)] + [""]
        if stage.get("commands"):
            lines += ["Commands, as the recipe page gives them:", "", FENCE + "sh", *stage["commands"], FENCE, ""]
        if stage.get("first_boot_prerequisites"):
            lines += ["First-boot prerequisites before stage 2:", ""]
            lines += [f"- {step}" for step in stage["first_boot_prerequisites"]] + [""]
        if stage.get("after_bootstrap"):
            lines += ["After stage 2:", ""]
            lines += [f"- {step}" for step in stage["after_bootstrap"]] + [""]
    if data.get("default_decisions"):
        defaults = data["default_decisions"]
        lines += ["## Slot default decisions", "", f"Source: {link(defaults['source'])}; {defaults['status']}.", "",
                  defaults["metadata"]["meaning"], "", defaults["metadata"]["not_claimed"], "",
                  inventory_sentence(defaults["inventory"]), "",
                  "An empty source state is displayed as open. A row that installs nothing by the manifest's own rule (a default, and not installs_nothing_extra) is shown as not installed, with the manifest's reason; that includes every split row, every measurement row whose measurement has not returned and every row resolved as not installed. A row that carries an interim install (amendment 3 of the decision rule) is shown with that install, beside its decided default's reason. Slot decisions do not change the tool provisioning fields or the five acceptance gates below.", ""]
        if defaults["inventory"]["by_row_kind"].get("consensus") or defaults["inventory"]["amendments"]:
            lines += ["A row of kind `consensus` was added by a recorded direct consensus of the two model families; its source basis says so and it is never definitive. An amendment by direct consensus is listed under its layer's table and changes no field of its row. "
                      f"Rows of kind consensus: {defaults['inventory']['by_row_kind'].get('consensus', 0)}; amendments: {defaults['inventory']['amendments']}.", ""]
        if defaults["inventory"]["by_row_kind"].get("owner_decision") or defaults["inventory"]["owner_amendments"]:
            lines += ["A row of kind `owner_decision` was added by the owner's decision (amendment 4 of the decision rule), and a row whose decided default installed nothing may carry an owner default, or an interim the owner amended; the source basis says so and none of them is definitive. The table shows the row as the owner's decision left it; what that decision replaced stays on the row under `overturned` and is listed under its layer's table. "
                      f"Rows of kind owner_decision: {defaults['inventory']['by_row_kind'].get('owner_decision', 0)}; owner amendments: {defaults['inventory']['owner_amendments']}.", ""]
    lines += [f"Profile: {link(data['profile']['source']) if data['profile']['status'] == 'published' else 'pending publication'}; native manifest registration: {data['profile']['native_manifest_registered']}.", ""]
    lines += render_host_prerequisites(data)
    lines += [data["comparison_order_text"], "", "## Five finality gates", ""]
    lines += [f"{i}. **{gate['id']}**: {gate['requirement']} ({link(gate['source'])})"
              for i, gate in enumerate(data["finality_gates"], 1)]
    lines += ["", "## Trading and cross-layer boundaries", "", data["trading_boundary"]["text"], ""]
    lines += [f"- {item['capability']}: {item['owner']}. {item['basis']}" for item in data["cross_boundaries"]]
    lines += ["", "## Blocking publication gaps", ""]
    lines += [f"- {gap}" for gap in data["blocking_gaps"]] or ["None at the global level; inspect each layer and tool."]
    tools = {tool["tool_id"]: tool for tool in data["tools"]}
    for row in data["layers"]:
        lines += ["", f"## {row['layer_id']}: {row['title']}", "", f"Status: **{row['status']}**. Evidence today: {row['evidence_class_today']}.", "",
                  f"Requirement: {row['requirement']['text'] or 'pending'} ({link(row['requirement']['source'])}).", "",
                  "Owns: " + ("; ".join(row["owns"]) or "none declared / pending") + ".", "",
                  "Uses: " + ("; ".join(row["uses"]) or "none declared / pending") + ".", "",
                  f"Ownership source: {link(row['ownership_source'])}.", ""]
        if "default_slots" in row:
            owner = row["default_ownership"]
            lines += ["### Slot default decisions", "",
                      "Default ownership: " + cell(owner["owns"]) + "; uses: " + cell(owner["uses"]) + ".", "",
                      "| Slot | State | Job | Default | Install | Repository | Outcome | Source basis | Family source status | Provenance |",
                      "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
            for slot in row["default_slots"]:
                record = slot["record"]
                recommendation = record["default"] or "none"
                if record["repository"]:
                    recommendation = f"[{recommendation}]({record['repository']})"
                interim = record.get("interim")
                install = "installed" if slot["installed"] else "not installed: " + slot["not_installed_reason"]
                if not slot["installed"] and isinstance(interim, dict) and interim.get("default"):
                    # Amendment 3: the row installs its interim meanwhile; its own decision still waits, for the reason shown.
                    # An interim of several repositories (amendment 4 widened one) names them all, not as one link.
                    repositories = [part.strip() for part in interim["repository"].split(";")]
                    named = (f"[{interim['default']}]({repositories[0]})" if len(repositories) == 1
                             else f"{interim['default']} ({', '.join(repositories)})")
                    install = (f"interim install ({interim['date_utc']}, amendment 3): {named}"
                               f"; its decided default is {install}")
                lines.append("| " + " | ".join(map(cell, [
                    record["slot_id"], slot["state"], record["job"], recommendation, install,
                    record["repository"] or "none", record["resolution"]["outcome"], record["label"],
                    f"claude: {record['claude']}; gpt: {record['gpt']}",
                    f"{record['catalog']} / {row['layer_id']} / {record['row_kind']}; {link(data['default_decisions']['source'])}"])) + " |")
            if not row["default_slots"]:
                lines.append("| pending slot publication | " + " | ".join(["pending"] * 9) + " |")
            lines += [""]
            # An amendment stays beside its row: the table above shows the row as the rounds decided it.
            amended = [(slot["record"]["slot_id"], item) for slot in row["default_slots"]
                       for item in slot["record"].get("amendments", [])]
            if amended:
                lines += [f"- Amendment to `{slot_id}` ({item['date_utc']}; {item['by']}): {item['decision']}."
                          + (" " + " ".join(item["text"].split()) if isinstance(item.get("text"), str) else "")
                          for slot_id, item in amended] + [""]
            # Amendment 4: the table shows the owner's decision; what it replaced stays on the row and is listed here.
            overturned = [slot["record"] for slot in row["default_slots"] if slot["record"].get("overturned")]
            for record in overturned:
                kept = record["overturned"]
                replaced = []
                if kept.get("fields"):
                    fields = kept["fields"]
                    replaced.append(f"the decided default {fields['default'] or 'none'} ({fields['state'] or 'open'}, "
                                    f"{fields['resolution']['outcome']})")
                if kept.get("interim"):
                    replaced.append(f"the interim {kept['interim']['default']}" if kept.get("fields") else
                                    "the interim's " + ", ".join(f"{key} {value}" if key == "default" else key
                                                                 for key, value in kept["interim"].items()))
                item = kept["amendment"]
                lines.append(f"- Owner decision on `{record['slot_id']}` ({item['date_utc']}; {item['by']}): {item['decision']}."
                             f" It replaces {'; '.join(replaced)}, kept under `overturned`.")
            if overturned:
                lines.append("")
        lines += ["| Tool / repository | Owner / status | Pin / checksum | Install | Acceptance | Stage / position |", "| --- | --- | --- | --- | --- | --- |"]
        for key in row["tools"]:
            tool = tools[key]
            repository = f"[{tool['name']}]({tool['repository']})" if tool["repository"] else tool["name"]
            if tool.get("package_id"):
                repository += f" (`{tool['package_id']}`)"
            lines.append("| " + " | ".join(map(cell, [repository, f"{tool['owner_layer_id']} / {tool['status']}",
                         f"{cell(tool['pin'])} / {cell(tool['checksum'])}", tool["install"], tool["acceptance"],
                         f"{tool['stage']} / {tool['position']}"])) + " |")
        if not row["tools"]:
            lines.append("| pending selection | pending | pending | pending | pending | pending |")
        lines += [""]
        for family, verdict in row["family_verdicts"].items():
            lines += [f"- {family} verdict: {verdict['status']}; {link(verdict['source'])}." +
                      (" " + cell(verdict["record"]) if "record" in verdict else "")]
            lines += [f"- {family} verdict binding gap: {gap}." for gap in verdict.get("binding_gaps", [])]
        lines += ["", "Finality: " + "; ".join(f"{key}={value['status']} ({link(value.get('source'))})" for key, value in row["finality"].items()) + ".", "",
                  "Deciding comparison: " + (row["deciding_comparison"]["proposal"] or "pending") + ".", "",
                  f"Experiment preregistration: {row['deciding_comparison']['status']} ({link(row['deciding_comparison']['preregistration_source'])}). The packet-judging preregistration is {link(PREREGISTRATION)}; it is not a target-host experiment registration.", "",
                  "Overturn condition: " + (row["overturn_condition"]["text"] or "pending") + ".", "",
                  f"Reference edition: {link(EDITION)}; no source-host acceptance inherited.", ""]
        lines += [f"- Gap: {gap}" for gap in row["blocking_gaps"]]
        for key in row["tools"]:
            tool = tools[key]
            if tool.get("version_policy"):
                lines += [f"- {tool['name']} version rule: {tool['version_policy']}"]
            update = tool.get("native_update")
            if update:
                lines += [f"- {tool['name']} native update: `{update['command']}`, {update['execution_status']}. "
                          f"{update['help_observation']} {update['order']} {update['on_refusal']} {update['after_update']} "
                          "Sources: " + "; ".join(link(source) for source in update["sources"]) + "."]
                lines += [f"- {tool['name']} receipt field {name}: {meaning}"
                          for name, meaning in update["receipt_fields"].items()]
            lines += [f"- {tool['name']} gap: {gap}" for gap in tool["blocking_gaps"]]
            if tool["documented_install"]:
                lines += [f"- {tool['name']} packet install reference (not a pinned recipe): {cell(tool['documented_install'])}"]
    lines += ["", "## Input provenance", "", "| Repository source | SHA-256 |", "| --- | --- |"]
    lines += [f"| {link(source['path'])} | `{source['sha256']}` |" for source in data["sources"]]
    return ("\n".join(lines).rstrip() + "\n").encode()


def render(root, **kwargs):
    data = build_data(root, **kwargs)
    return {OUTPUTS[0]: render_markdown(data),
            OUTPUTS[1]: (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--profile", type=Path, help="W-PROF input; defaults to adoption/new-wsl-profile.json if published")
    parser.add_argument("--claude-verdicts", type=Path, help="Published Claude verdict file bound to selection SHA-256")
    parser.add_argument("--codex-verdicts", type=Path, help="Published Codex verdict file bound to selection SHA-256")
    parser.add_argument("--defaults-manifest", type=Path, help="Explicit slot-decision source preview; otherwise read the published canonical manifest if present")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true", help="Check both committed outputs (default)")
    args = parser.parse_args(argv)
    try:
        options = {"profile_path": args.profile, "claude_verdicts": args.claude_verdicts,
                   "codex_verdicts": args.codex_verdicts, "defaults_manifest": args.defaults_manifest}
        outputs = render(args.root, **options)
        require(outputs == render(args.root, **options), "nondeterministic handbook regeneration")
        for raw in outputs.values():
            text = raw.decode("utf-8")
            for label, pattern in PRIVATE_CONTENT:
                require(not pattern.search(text), f"{label} in generated handbook output")
        for path, raw in outputs.items():
            destination = args.root / path
            if args.write:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(raw)
            else:
                require(destination.exists() and destination.read_bytes() == raw,
                        f"stale generated output: {path}; run --write")
        print(json.dumps({"status": "written" if args.write else "passed",
                          "outputs": {path: digest(raw) for path, raw in outputs.items()}}, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"new-wsl-handbook: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
