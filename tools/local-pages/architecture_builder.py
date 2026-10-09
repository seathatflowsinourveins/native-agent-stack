#!/usr/bin/env python3
"""Build a source-bound local Architecture page, preserving the input records.

Uses the installed zstd stream reader through architecture_sources, the native
landscape layer contract, and the existing local-pages document/publish API.
No install, gate adjudication, network fetch or credential/config read.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location("local_architecture_" + name, HERE / (name + ".py"))
    if spec is None or spec.loader is None:
        raise ValueError("local architecture module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_invocation_roles(components: list[dict], role_map: dict) -> None:
    """Project copied rows once, keeping original instances for future passes."""
    projected = {}
    for component in components:
        invoke = component.get("invoke")
        if not isinstance(invoke, dict):
            continue
        if id(invoke) in projected:
            component["invoke"] = projected[id(invoke)]
            continue
        normalized = copy.deepcopy(invoke)
        rows, groups = [], {}
        for row in invoke.get("roles", []):
            if row.get("client") != "Codex":
                rows.append(copy.deepcopy(row))
                continue
            observations = row.get("instance_observations") or [row]
            for observation in observations:
                original = copy.deepcopy(observation)
                instance = original.get("source_instance", original.get("role"))
                original["source_instance"] = instance
                owner = role_map.get(instance) or "unattributed instances"
                key = (owner, original.get("server"), original.get("window_hours"))
                if key not in groups:
                    group = copy.deepcopy(original)
                    group.update(
                        role=owner,
                        attribution="launch-window registry" if role_map.get(instance) else "unattributed",
                        source_instances=[], instance_observations=[],
                        aggregation_scope="sum of published instance counts; distinct cross-instance conversations unverified",
                    )
                    group.pop("source_instance", None)
                    groups[key] = group
                    rows.append(group)
                group = groups[key]
                group["instance_observations"].append(original)
                if instance not in group["source_instances"]:
                    group["source_instances"].append(instance)
        for group in groups.values():
            for field in ("calls", "conversations"):
                values = [row.get(field) for row in group["instance_observations"]]
                group[field] = sum(values) if all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in values) else None
        normalized["roles"] = rows
        projected[id(invoke)] = normalized
        projected[id(normalized)] = normalized
        component["invoke"] = normalized


def build(root: Path, state_root: Path, output_dir: Path, receipt: Path,
          first_layer: str | None = None, asset: Path | None = None) -> dict:
    pages = load("build_pages")
    output_dir, receipt = pages.no_symlinks(output_dir), pages.no_symlinks(receipt)
    if receipt.is_relative_to(output_dir):
        raise ValueError("architecture receipt must remain outside serving root")
    model = load("architecture_sources").build(root, state_root, asset)
    inventory = load("architecture_inventory").build(root, state_root)
    evidence = load("architecture_evidence")
    if hasattr(evidence, "attach_inventory"):
        inventory["items"] = evidence.attach_inventory(inventory.get("items", []), model.get("evidence_index", {}))
    role_projection = None
    if (HERE / "adoption_roles.py").exists():
        observation = model.get("adoption_observation") or {}
        source_path = observation.get("path")
        if source_path:
            source_document = json.loads(Path(source_path).read_text())
            role_projection = load("adoption_roles").project(source_document, state_root)
            role_map = role_projection.get("instances", {}).get("role_map") or {}
            components = inventory.get("items", []) + [component for layer in model["layers"] for category in ("winners", "candidates", "alternatives", "rejected", "source_quality", "g5_candidates") for component in layer.get(category, []) if isinstance(component, dict)]
            _normalize_invocation_roles(components, role_map)
    body, counts = load("architecture_view").render(model, inventory, first_layer)
    if first_layer is None and counts["rendered_layer_count"] != model["layer_count"]:
        raise ValueError("architecture section count differs from canonical landscape")
    if counts["rendered_layer_count"] == 0:
        raise ValueError("selected architecture layer does not exist")
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    native, _ = pages.load_native(root)
    manifest_sha = hashlib.sha256(native.render(native.build(root, state_root, root / "tools/north-star/sources.json"))).hexdigest()
    scope = "Builder reads dated landscape choices, current CC stage records and published invoke observations."
    html = pages.document("architecture", "Architecture by layer", "Read the selected tools, alternatives, inventories and evidence for each layer.", scope, body, generated, manifest_sha, [])
    builder_path = Path(__file__).resolve()
    outputs = {"architecture.html": html}
    for name in ("site.css", "site.js"):
        outputs["assets/" + name] = (HERE / "assets" / name).read_bytes()
    result = {"schema": "local-architecture/1", "generated_utc": generated,
              "builder": {"path": str(builder_path), "sha256": hashlib.sha256(builder_path.read_bytes()).hexdigest()},
              **counts, "first_layer": first_layer,
              "design": model.get("design"), "g5": model.get("g5"),
              "invocation_source": {key: (model.get("adoption_observation") or {}).get(key) for key in ("path", "sha256", "generated_utc", "window_hours")},
              "role_attribution_sources": role_projection.get("sources", []) if role_projection else [],
              "modules": [{"path": str(HERE / (name + ".py")), "sha256": hashlib.sha256((HERE / (name + ".py")).read_bytes()).hexdigest()} for name in ("architecture_sources", "architecture_inventory", "architecture_evidence", "architecture_view", "build_pages")],
              "sources": model.get("sources"), "inventory_sources": inventory.get("sources"),
              "inventory_coverage": inventory.get("coverage"),
              "native_readiness_manifest_sha256": manifest_sha,
              "outputs": {name: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)} for name, raw in outputs.items()},
              "limits": ["Published source records and metadata observations do not confer gate acceptance or fresh-session evidence.", "Only explicit layer IDs or exact repository identity associate inventory; unmapped items remain visible."]}
    pages.publish(output_dir, receipt, outputs, result)
    return result


def refresh_if_changed(root: Path, state_root: Path, output_dir: Path, receipt: Path) -> dict:
    """The hourly published snapshot drives rebuilds; ordinary refreshes reuse."""
    pages = load("build_pages")
    evidence = load("architecture_evidence")
    observation = evidence.invocation_source(state_root)
    signature = {"adoption_sha256": observation.get("sha256"), "files": []}
    paths = list((root / "catalogs/landscape").glob("*.json"))
    paths += [state_root / "coordination/command-center/pages/cc-now.json", root / "adoption/skills/manifest.json", root / "manifests/stack.json", root / "adoption/manifest.json"]
    paths += [HERE / (name + ".py") for name in ("architecture_builder", "architecture_sources", "architecture_inventory", "architecture_evidence", "architecture_view")]
    paths += [HERE / "build_pages.py", HERE / "assets/site.css", HERE / "assets/site.js", root / "manifests/evidence.json", root / "catalogs/north-star/readiness.json"]
    if (HERE / "adoption_roles.py").exists():
        paths.append(HERE / "adoption_roles.py")
    if receipt.exists():
        retained = json.loads(receipt.read_text())
        for source in retained.get("sources", []):
            path = Path(source.get("path", ""))
            if path.suffix == ".zst" and path.is_absolute() and path.is_relative_to(state_root):
                paths.append(path)
    for path in paths:
        path = pages.no_symlinks(path)
        stat = path.stat()
        signature["files"].append([str(path), stat.st_size, stat.st_mtime_ns])
    cache_path = pages.no_symlinks(receipt.with_name("architecture-cache.json"))
    if cache_path.is_relative_to(output_dir):
        raise ValueError("architecture cache must remain outside the served root")
    if cache_path.exists() and receipt.exists() and (output_dir / "architecture.html").exists():
        previous = json.loads(cache_path.read_text())
        if previous.get("signature") == signature:
            return json.loads(receipt.read_text())
    result = build(root, state_root, output_dir, receipt)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"signature": signature, "generated_utc": result["generated_utc"]}, sort_keys=True) + "\n")
    temporary.replace(cache_path)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--state-root", type=Path, default=Path.home() / ".local/state/native-agent-stack")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--first-layer")
    parser.add_argument("--g5-asset", type=Path)
    args = parser.parse_args(argv)
    output = args.output_dir or args.state_root / "coordination/command-center/local-pages"
    receipt = args.receipt or args.state_root / "research/fullspeed-20261008/g5-stars-gap/local-pages/architecture/architecture-receipt.json"
    try:
        result = build(args.root, args.state_root, output, receipt, args.first_layer, args.g5_asset)
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        parser.exit(1, f"architecture: build failed ({type(error).__name__}): {error}\n")
    print(json.dumps({"output": str(output / "architecture.html"), "receipt": str(receipt),
                      "builder_sha256": result["builder"]["sha256"],
                      "rendered_layer_count": result["rendered_layer_count"],
                      "canonical_layer_count": result["canonical_layer_count"],
                      "unmapped_inventory_items": result["unmapped_inventory_items"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
