#!/usr/bin/env python3
"""Deterministic, no-network extraction of the SOTA-convergence working files.

Reads the two maintained catalogs and writes the fixed set of intermediate
"working files" that ``github_freshness.py`` and ``build_manifest.py`` consume.
Nothing here calls a network API or reads a private host path; every input is
a repository-relative file already checked into ``catalogs/`` and
``manifests/``.

Inputs (repository-relative, overridable):
  catalogs/foundation/manifest.json    - the 16 foundation layer ids/titles + top_gaps
  catalogs/foundation/decisions.json   - per-decision layer_ids + component_ids
  manifests/stack.json                 - component id -> repository/version/license/profile/role
  catalogs/us-equities/foundation-memory.json
  catalogs/us-equities/agents-operations.json
  catalogs/us-equities/data-research.json
  catalogs/us-equities/engines-strategies.json
  catalogs/us-equities/models.json
  catalogs/us-equities/star-audit.json
  catalogs/us-equities/coverage.json
  catalogs/sota-convergence/manifest-20260922.json  - source of the 12-layer taxonomy only
  the source records named in TRADING_PIN_SOURCES (trading pins outside the cards)
  the source records named in RUNTIME_PIN_SOURCES (GPT runtime pins: the new-WSL
    install plan, the runtime-worker recipe pin record, the native SDK constraints)

Outputs (written under --out):
  foundation-layers.json  {checked_at, layers:[{layer_id,title,summary,decisions,components}], top_gaps}
  trading-catalog.json    {entries:[fine-grained entries + catalog_file], layer_index:{tag:[entry ids]}}
  trading-by-layer.json   {taxonomy:{layer_id:[tags]}, layers:{layer_id:[entries]}}
  trading-pins.json       {entries:[{id, layer, repository, pin, pin_source, repository_source}]}
  runtime-pins.json       {entries:[{id, group, kind, repository, pin, pin_source, named_in, error}]}
  star-candidates.json    {star_candidates, beyond_stars, star_count}
  models.json             {entries:[...]}

Every output is deterministic for a fixed set of inputs: components and
entries are sorted by id, and tag/layer indexes are sorted by key, so two
runs against unchanged inputs byte-for-byte match (module the ``checked_at``
stamps carried over verbatim from the source catalogs).
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Foundation: catalogs/foundation/{manifest,decisions}.json + manifests/stack.json
# ---------------------------------------------------------------------------

FOUNDATION_DECISION_FIELDS = (
    "id", "capability", "selection", "review_status", "component_ids",
    "activation", "candidate", "evidence_ids",
)
FOUNDATION_COMPONENT_FIELDS = ("id", "repository", "version", "license", "role", "profile")


def build_foundation_layers(manifest: dict, decisions_doc: dict, stack: dict) -> dict:
    layer_order = [layer["id"] for layer in manifest.get("layers", [])]
    titles = {layer["id"]: layer.get("title", layer["id"]) for layer in manifest.get("layers", [])}
    by_layer = {lid: {"layer_id": lid, "title": titles[lid], "summary": "", "decisions": [], "components": []}
                for lid in layer_order}
    stack_components = {c["id"]: c for c in stack.get("components", [])}

    for decision in decisions_doc.get("decisions", []):
        entry = {field: decision.get(field) for field in FOUNDATION_DECISION_FIELDS}
        for layer_id in decision.get("layer_ids") or []:
            if layer_id in by_layer:
                by_layer[layer_id]["decisions"].append(entry)

    for layer_id in layer_order:
        layer = by_layer[layer_id]
        referenced = set()
        for decision in layer["decisions"]:
            referenced.update(decision.get("component_ids") or [])
        for component_id in sorted(referenced):
            component = stack_components.get(component_id)
            if component is None:
                continue
            layer["components"].append({field: component.get(field) for field in FOUNDATION_COMPONENT_FIELDS})

    return {
        "checked_at": decisions_doc.get("checked_at"),
        "layers": [by_layer[lid] for lid in layer_order],
        "top_gaps": manifest.get("top_gaps", []),
    }


# ---------------------------------------------------------------------------
# Trading: catalogs/us-equities/{foundation-memory,agents-operations,data-research,engines-strategies}.json
# ---------------------------------------------------------------------------

TRADING_SOURCE_FILES = ("foundation-memory", "agents-operations", "data-research", "engines-strategies")


def build_trading_catalog(us_equities_dir: Path) -> dict:
    entries = []
    layer_index = defaultdict(list)
    for name in TRADING_SOURCE_FILES:
        path = us_equities_dir / f"{name}.json"
        if not path.exists():
            continue
        doc = load_json(path)
        for raw in doc.get("entries", []):
            entry = dict(raw)
            entry["catalog_file"] = name
            entries.append(entry)
            for tag in entry.get("layers") or []:
                layer_index[tag].append(entry["id"])
    entries.sort(key=lambda e: e.get("id") or "")
    return {
        "entries": entries,
        "layer_index": {tag: sorted(ids) for tag, ids in sorted(layer_index.items())},
    }


def load_taxonomy(taxonomy_source: Path) -> dict:
    """The 12-layer taxonomy is copied from manifest-20260922.json#/taxonomy;
    reading it live keeps this extraction in sync with that fixed record
    instead of duplicating a second stale copy in source."""
    doc = load_json(taxonomy_source)
    taxonomy = doc.get("taxonomy") if isinstance(doc, dict) else None
    if not isinstance(taxonomy, dict):
        raise ValueError(f"{taxonomy_source} has no #/taxonomy mapping")
    return taxonomy


def tag_to_layers_map(taxonomy: dict) -> dict:
    """Invert {layer_id: [tags]} into {tag: [layer_id, ...]}."""
    mapping: dict = defaultdict(list)
    for layer_id, tags in taxonomy.items():
        for tag in tags:
            mapping[tag].append(layer_id)
    return dict(mapping)


def unmapped_tags(entries, tag_map: dict) -> list:
    """Tags used by entries that the taxonomy does not place in any layer."""
    unmapped = set()
    for entry in entries:
        for tag in entry.get("layers") or []:
            if tag not in tag_map:
                unmapped.add(tag)
    return sorted(unmapped)


def build_trading_by_layer(trading_catalog: dict, taxonomy: dict) -> dict:
    tag_map = tag_to_layers_map(taxonomy)
    by_layer = defaultdict(list)
    for entry in trading_catalog["entries"]:
        matched = set()
        for tag in entry.get("layers") or []:
            matched.update(tag_map.get(tag, []))
        for layer_id in matched:
            by_layer[layer_id].append(entry)
    layers = {layer_id: sorted(entries, key=lambda e: e.get("id") or "")
              for layer_id, entries in by_layer.items()}
    # Every taxonomy layer appears even if no entry currently matches it.
    for layer_id in taxonomy:
        layers.setdefault(layer_id, [])
    return {"taxonomy": taxonomy, "layers": {lid: layers[lid] for lid in sorted(layers)}}


# ---------------------------------------------------------------------------
# Trading pins that no selected catalog card carries
# ---------------------------------------------------------------------------

# Trading upstreams that a blueprint or runtime record pins but that no
# selected (default/conditional) catalogs/us-equities card carries. The
# card-based trading baseline never reaches them, so without this list
# github_freshness.py would not fetch them and the catalog-freshness report
# would not list them. Each pin (and the repository, where the record carries
# one) is read from its source record at extraction time, never copied here, so
# a pin bump in that record reaches the report without editing this list. A
# pointer that no longer resolves raises (resolve_trading_pins) instead of
# silently dropping the component; tests/test_catalog_freshness_trading.py
# resolves every entry against the checked-in repository.
TRADING_PIN_SOURCES = (
    {
        # Simulation-lane cross-check engine. Its only catalog mention is a
        # backtesting-engine alternative with disposition out_of_scope
        # (catalogs/landscape/us-equities.json); it has no us-equities card.
        "id": "hftbacktest",
        "layer": "backtesting-engine",
        "path": "blueprints/us-equities/sim-crosscheck-hftbacktest/receipt.json",
        "repository_pointer": "/upstream/source_url",
        "pin_pointer": "/upstream/pinned_version",
    },
    {
        # The PyPI TWS API client used by the accepted NautilusTrader IB paper run
        # (runtime-target.json broker_boundaries ibkr python_adapter_paper_evidence).
        # The PyPI project URL is IB's tws-api site, which is not on GitHub. The
        # GitHub source used here is the one named in
        # catalogs/landscape/claude-independent-discovery.json.
        "id": "nautilus-ibapi",
        "layer": "execution-broker",
        "path": "blueprints/us-equities/engine-nautilus/ibkr-paper-orders/evidence/receipt-20260923-passed.json",
        "repository": "https://github.com/nautechsystems/nautilus_ibapi",
        "pin_pointer": "/ibapi_version",
    },
    {
        # The Rust ibapi crate pinned by the selected NautilusTrader 2.0.0rc5 Rust IB
        # adapter. runtime-target.json upstream_ibapi_pin records the upstream
        # fix and pin-update dependency on this crate.
        "id": "rust-ibapi",
        "layer": "execution-broker",
        "path": "catalogs/us-equities/runtime-target.json",
        "repository": "https://github.com/wboayue/rust-ibapi",
        "pin_pointer": "/broker_boundaries/0/upstream_ibapi_pin/rc5_pin",
    },
)


def resolve_json_pointer(doc, pointer: str):
    """RFC 6901 lookup. Raises KeyError when any segment is absent."""
    if pointer == "":
        return doc
    if not pointer.startswith("/"):
        raise KeyError(f"not a JSON pointer: {pointer!r}")
    node = doc
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list) and token.isdigit() and int(token) < len(node):
            node = node[int(token)]
        elif isinstance(node, dict) and token in node:
            node = node[token]
        else:
            raise KeyError(f"{pointer!r} does not resolve at segment {token!r}")
    return node


def _source_file(repo_root: Path, relative: str) -> Path:
    parts = Path(relative).parts
    if Path(relative).is_absolute() or ".." in parts:
        raise ValueError(f"pin source path must be repository-relative: {relative!r}")
    return repo_root / relative


def resolve_trading_pins(repo_root: Path, sources=TRADING_PIN_SOURCES, taxonomy=None,
                         card_ids=()) -> dict:
    """Resolve each declared off-card trading pin against its source record.

    Raises ValueError naming the entry when a source file is missing, a pointer
    does not resolve to a non-empty string, a layer is not a taxonomy layer
    (when ``taxonomy`` is given), or an id collides with a catalog card id or
    another declared pin. Each of these would otherwise drop the component or
    make its report row ambiguous."""
    entries, seen = [], set(card_ids)
    for source in sources:
        entry_id = source["id"]
        if entry_id in seen:
            raise ValueError(f"trading pin id {entry_id!r} duplicates a catalog card or another pin")
        seen.add(entry_id)
        if taxonomy is not None and source["layer"] not in taxonomy:
            raise ValueError(f"trading pin {entry_id!r}: layer {source['layer']!r} is not a taxonomy layer")
        path = _source_file(repo_root, source["path"])
        try:
            doc = load_json(path)
            pin = resolve_json_pointer(doc, source["pin_pointer"])
            repository = (resolve_json_pointer(doc, source["repository_pointer"])
                          if source.get("repository_pointer") else source.get("repository"))
        except (OSError, ValueError, KeyError) as error:
            raise ValueError(f"trading pin {entry_id!r} does not resolve from {source['path']}: {error}") from error
        for field, value in (("pin", pin), ("repository", repository)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"trading pin {entry_id!r}: {field} is not a non-empty string")
        entries.append({
            "id": entry_id,
            "layer": source["layer"],
            "repository": repository,
            "pin": pin,
            "pin_source": {"path": source["path"], "pointer": source["pin_pointer"]},
            "repository_source": ({"path": source["path"], "pointer": source["repository_pointer"]}
                                  if source.get("repository_pointer") else None),
        })
    entries.sort(key=lambda e: e["id"])
    return {"entries": entries}


# ---------------------------------------------------------------------------
# GPT runtime workers, SDKs and agents: pins in runtime records, plus watch-only upstreams
# ---------------------------------------------------------------------------

# The reviewed new-WSL install plan. tests/test_catalog_freshness_runtime.py checks
# that it is tools/adoption/new_wsl_client_config.py's PLAN_REL plus
# "/install-plan.json", so this tracker and the client configuration tool move to
# a new plan revision together.
NEW_WSL_INSTALL_PLAN = "evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json"
RUNTIME_GROUPS = ("native-client", "agent-sdk", "model-sdk", "gateway", "runtime-worker",
                  "evaluation-harness", "coding-agent", "ci-action")
RUNTIME_PIN_KIND = "pin_source"
RUNTIME_WATCH_KIND = "watch_only"
# Exactly one of these names where a pin source's pin comes from (see RUNTIME_PIN_SOURCES).
RUNTIME_SOURCE_FORMS = ("pin_pointer", "row", "requirement")
# A "row" source reads these two fields of the row it selects. A composite row
# (several upstreams in one slot) joins its parts with RUNTIME_PART_SEPARATOR in
# both fields, in the same order.
RUNTIME_ROW_REPOSITORY_FIELD = "repository"
RUNTIME_ROW_PIN_FIELD = "release"
RUNTIME_PART_SEPARATOR = ";"
# A repository literal declared below is exactly https://github.com/<owner>/<repo>.
GITHUB_REPOSITORY_LITERAL_RE = re.compile(r"https://github\.com/[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+")
# A repository resolved from a record only has to be a GitHub URL the fetch step
# can turn into a slug: github_freshness.py's GITHUB_URL_RE, kept independent here.
GITHUB_URL_RE = re.compile(r"^https?://github\.com/([^/\s]+)/([^/\s#?]+)")
# One "name==version" line of a pip constraints file. Comment and blank lines
# never match; the captured name is compared PEP 503-normalized.
REQUIREMENT_LINE_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([^\s;#\\]+)")

# GPT-route runtime workers, agent SDKs, the GPT gateway, evaluation harnesses
# and the native Codex client, each at the pin a runtime record installs. Some of
# these upstreams also have a catalog row (openai/codex, OmniRoute, inspect_ai and
# deer-flow are selected trading cards); that row carries the catalog's pin and
# stays in the drift or trading table, while the entry here carries the runtime
# record's pin, which can differ. They are not TRADING_PIN_SOURCES: a trading pin
# must not repeat a selected card's repository and must sit in a trading taxonomy
# layer. As there, each pin (and repository) is read from its source record at
# extraction time, never copied here. Unlike there, a record that moved does not
# raise: the daily job keeps its foundation and trading report, and the entry is
# written with "pin": null and an "error" (resolve_runtime_pins). Each source has
# exactly one RUNTIME_SOURCE_FORMS key:
#   pin_pointer  an RFC 6901 pointer into a JSON record, with repository_pointer
#                or a literal repository, as in TRADING_PIN_SOURCES;
#   row          {"array", "key", "value"[, "part_repository"]}: the one row of the
#                JSON array at "array" whose "key" equals "value"; its
#                RUNTIME_ROW_REPOSITORY_FIELD and RUNTIME_ROW_PIN_FIELD give the
#                repository and pin, and part_repository picks one upstream of a
#                composite row (the release part at the same position);
#   requirement  a requirement name whose one "name==version" line in a pip
#                constraints file gives the pin; the repository is a literal.
RUNTIME_PIN_SOURCES = (
    {
        # Codex CLI, the second native client. Its native installer self-updates,
        # so the row's release is the reviewed release (the row says
        # version_pinned false), not a lock.
        "id": "new-wsl:codex",
        "group": "native-client",
        "path": NEW_WSL_INSTALL_PLAN,
        "row": {"array": "/owners", "key": "slot", "value": "codex"},
    },
    {
        # The Codex SDK; the native codex binary owns codex exec and app-server.
        "id": "new-wsl:codex-sdk",
        "group": "agent-sdk",
        "path": NEW_WSL_INSTALL_PLAN,
        "row": {"array": "/owners", "key": "slot", "value": "codex-sdk-and-codex-exec-app-server"},
    },
    {
        # The Claude Agent SDK, the Codex SDK's pair in the plan's agent-sdks layer.
        "id": "new-wsl:claude-agent-sdk",
        "group": "agent-sdk",
        "path": NEW_WSL_INSTALL_PLAN,
        "row": {"array": "/owners", "key": "slot", "value": "claude-agent-sdk"},
    },
    {
        # OmniRoute, the GPT gateway that cross-family lanes run through.
        "id": "new-wsl:omniroute",
        "group": "gateway",
        "path": NEW_WSL_INSTALL_PLAN,
        "row": {"array": "/owners", "key": "slot", "value": "gpt-gateway"},
    },
    {
        # The OpenHands software-agent SDK, the plan's agent runtime worker.
        "id": "new-wsl:openhands-sdk",
        "group": "runtime-worker",
        "path": NEW_WSL_INSTALL_PLAN,
        "row": {"array": "/owners", "key": "slot", "value": "agent-runtime-worker"},
    },
    {
        # GPT Researcher, the first upstream of the composite research-harnesses row.
        "id": "new-wsl:gpt-researcher",
        "group": "runtime-worker",
        "path": NEW_WSL_INSTALL_PLAN,
        "row": {"array": "/owners", "key": "slot", "value": "research-harnesses",
                "part_repository": "https://github.com/assafelovic/gpt-researcher"},
    },
    {
        # DeerFlow, the second upstream of the composite research-harnesses row.
        "id": "new-wsl:deer-flow",
        "group": "runtime-worker",
        "path": NEW_WSL_INSTALL_PLAN,
        "row": {"array": "/owners", "key": "slot", "value": "research-harnesses",
                "part_repository": "https://github.com/bytedance/deer-flow"},
    },
    {
        # Harbor, the containerized agent E2E runner.
        "id": "new-wsl:harbor",
        "group": "evaluation-harness",
        "path": NEW_WSL_INSTALL_PLAN,
        "row": {"array": "/owners", "key": "slot", "value": "harbor-containerized-agent-e2e-runner"},
    },
    {
        # Inspect AI. Upstream has no version-shaped GitHub release, so the row
        # reports activity and stays not compared.
        "id": "new-wsl:inspect-ai",
        "group": "evaluation-harness",
        "path": NEW_WSL_INSTALL_PLAN,
        "row": {"array": "/owners", "key": "slot", "value": "inspect-ai"},
    },
    {
        # The OpenHands SDK tag the runtime-worker recipe pins its wheels, image and
        # source archive to; it can differ from the plan's agent-runtime-worker row.
        "id": "recipe:openhands-sdk",
        "group": "runtime-worker",
        "path": "blueprints/runtime-workers/openhands/pins.json",
        "pin_pointer": "/tag",
        "repository_pointer": "/repository",
    },
    {
        # The openai-codex Python SDK in the native SDK constraints. Its official
        # source is openai/codex's sdk/python (adoption/sdk/README.md).
        "id": "sdk-lock:openai-codex",
        "group": "agent-sdk",
        "path": "adoption/sdk/accepted-constraints.txt",
        "requirement": "openai-codex",
        "repository": "https://github.com/openai/codex",
    },
    {
        # The openai Python SDK in the same constraints file.
        "id": "sdk-lock:openai",
        "group": "model-sdk",
        "path": "adoption/sdk/accepted-constraints.txt",
        "requirement": "openai",
        "repository": "https://github.com/openai/openai-python",
    },
)

# Watch-only upstreams: named in a file on main ("named_in") but with no pin
# record on main, so their rows report upstream activity and are never compared.
# pi's trial pin lives on unmerged PR #524; the crawl4ai, DeepAgents and
# codex-action pins live on unmerged PRs #428, #566 and #550. Promote an entry to
# RUNTIME_PIN_SOURCES when its pin record lands on main.
RUNTIME_WATCH_SOURCES = (
    {
        # pi, a coding harness and multi-provider agent toolkit.
        "id": "watch:pi",
        "group": "coding-agent",
        "repository": "https://github.com/earendil-works/pi",
        "named_in": "catalogs/saturation/ledger.json",
    },
    {
        # oh-my-pi, an extended fork of the pi coding agent.
        "id": "watch:oh-my-pi",
        "group": "coding-agent",
        "repository": "https://github.com/can1357/oh-my-pi",
        "named_in": "catalogs/landscape/upstream-snapshot.json",
    },
    {
        # The OpenAI Agents SDK for Python.
        "id": "watch:openai-agents-python",
        "group": "agent-sdk",
        "repository": "https://github.com/openai/openai-agents-python",
        "named_in": "catalogs/us-equities/agents-operations.json",
    },
    {
        # The OpenAI Agents SDK for JavaScript/TypeScript.
        "id": "watch:openai-agents-js",
        "group": "agent-sdk",
        "repository": "https://github.com/openai/openai-agents-js",
        "named_in": "docs/decisions/2026-10-02-gpt-runtime-tracking.md",
    },
    {
        # Crawl4AI, a conditional foundation alternative for bulk Markdown ingestion.
        "id": "watch:crawl4ai",
        "group": "runtime-worker",
        "repository": "https://github.com/unclecode/crawl4ai",
        "named_in": "catalogs/landscape/foundation.json",
    },
    {
        # Deep Agents, a conditional foundation alternative for an application-owned worker.
        "id": "watch:deepagents",
        "group": "runtime-worker",
        "repository": "https://github.com/langchain-ai/deepagents",
        "named_in": "catalogs/landscape/foundation.json",
    },
    {
        # The Codex GitHub Action, for running Codex in CI.
        "id": "watch:codex-action",
        "group": "ci-action",
        "repository": "https://github.com/openai/codex-action",
        "named_in": "catalogs/saturation/ledger.json",
    },
)


class _RuntimeSourceUnresolved(Exception):
    """One runtime source record moved or changed shape. The message is built only
    from the declared repository-relative path, the pointer, slot or requirement
    and a short reason, so it is safe to publish."""


def _github_slug(url):
    """Lower-cased 'owner/repo' for a GitHub URL, or None. Mirrors
    github_freshness.github_slug (kept independent: this module imports no sibling)."""
    match = GITHUB_URL_RE.match(url) if isinstance(url, str) else None
    if not match:
        return None
    return f"{match.group(1)}/{match.group(2).removesuffix('.git')}".lower()


def _normalize_requirement(name: str) -> str:
    """PEP 503 name normalization (https://peps.python.org/pep-0503/#normalized-names)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _check_repository_literal(entry_id, value, field="repository") -> None:
    if not isinstance(value, str) or not GITHUB_REPOSITORY_LITERAL_RE.fullmatch(value):
        raise ValueError(f"runtime source {entry_id!r}: {field} {value!r} is not "
                         "https://github.com/<owner>/<repo>")


def _check_runtime_declaration(repo_root: Path, source: dict, kind: str, seen: set, reserved: set) -> None:
    """Raise ValueError for a declaration only a code edit can produce."""
    required = ("id", "group", "path") if kind == RUNTIME_PIN_KIND else ("id", "group", "repository")
    missing = [field for field in required if not isinstance(source.get(field), str) or not source[field]]
    if missing:
        raise ValueError(f"runtime source {source.get('id')!r} has no {', '.join(missing)}")
    entry_id = source["id"]
    if entry_id in seen:
        raise ValueError(f"runtime source id {entry_id!r} duplicates another runtime source")
    if entry_id in reserved:
        raise ValueError(f"runtime source id {entry_id!r} duplicates a foundation component, "
                         "trading entry or trading pin id")
    seen.add(entry_id)
    if source["group"] not in RUNTIME_GROUPS:
        raise ValueError(f"runtime source {entry_id!r}: group {source['group']!r} is not in RUNTIME_GROUPS")
    if source.get("repository") is not None:
        _check_repository_literal(entry_id, source["repository"])
    if kind == RUNTIME_WATCH_KIND:
        if source.get("named_in") is not None:
            _source_file(repo_root, source["named_in"])
        return
    _source_file(repo_root, source["path"])
    forms = [form for form in RUNTIME_SOURCE_FORMS if source.get(form) is not None]
    if len(forms) != 1:
        raise ValueError(f"runtime source {entry_id!r} needs exactly one of {', '.join(RUNTIME_SOURCE_FORMS)}, "
                         f"not {forms}")
    if forms == ["pin_pointer"]:
        if not isinstance(source["pin_pointer"], str):
            raise ValueError(f"runtime source {entry_id!r}: pin_pointer is not a string")
        if not isinstance(source.get("repository_pointer"), str) and not source.get("repository"):
            raise ValueError(f"runtime source {entry_id!r}: a pin_pointer source needs repository_pointer "
                             "or repository")
    elif forms == ["requirement"]:
        if not isinstance(source["requirement"], str) or not source["requirement"]:
            raise ValueError(f"runtime source {entry_id!r}: requirement is not a non-empty string")
        if not source.get("repository"):
            raise ValueError(f"runtime source {entry_id!r}: a requirement source needs a literal repository")
    else:
        row = source["row"]
        if not isinstance(row, dict) or any(not isinstance(row.get(field), str) or not row[field]
                                            for field in ("array", "key", "value")):
            raise ValueError(f"runtime source {entry_id!r}: row needs string array, key and value")
        if row.get("part_repository") is not None:
            _check_repository_literal(entry_id, row["part_repository"], field="part_repository")


def _runtime_locator(source: dict) -> str:
    """Where a pin source's pin is read, for an error message: declared values only."""
    if source.get("pin_pointer") is not None:
        return f"{source['path']}#{source['pin_pointer']}"
    if source.get("requirement") is not None:
        return f"{source['path']} requirement {source['requirement']}"
    row = source["row"]
    locator = f"{source['path']}#{row['array']} {row['key']} {row['value']!r}"
    if row.get("part_repository"):
        locator += f" part {row['part_repository']}"
    return locator


def _runtime_pin_source(source: dict) -> dict:
    if source.get("pin_pointer") is not None:
        return {"path": source["path"], "pointer": source["pin_pointer"]}
    if source.get("requirement") is not None:
        return {"path": source["path"], "requirement": source["requirement"]}
    return {"path": source["path"], "row": dict(source["row"])}


def _read_runtime_source(repo_root: Path, source: dict, locator: str, as_json: bool):
    try:
        text = _source_file(repo_root, source["path"]).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        # Never str(error): an OSError's text carries the absolute host path.
        raise _RuntimeSourceUnresolved(f"{locator}: source file is missing or unreadable") from None
    if not as_json:
        return text
    try:
        return json.loads(text)
    except ValueError:
        raise _RuntimeSourceUnresolved(f"{locator}: source file is not valid JSON") from None


def _runtime_pointer(doc, pointer: str, locator: str):
    try:
        return resolve_json_pointer(doc, pointer)
    except KeyError:
        raise _RuntimeSourceUnresolved(f"{locator}: pointer {pointer} does not resolve") from None


def _runtime_parts(value) -> list:
    """Composite rule: split on RUNTIME_PART_SEPARATOR and strip each part; a value
    without the separator, or one that is not a string, is one part."""
    if isinstance(value, str):
        return [part.strip() for part in value.split(RUNTIME_PART_SEPARATOR)]
    return [value]


def _resolve_runtime_row(doc, row: dict, locator: str):
    rows = _runtime_pointer(doc, row["array"], locator)
    if not isinstance(rows, list):
        raise _RuntimeSourceUnresolved(f"{locator}: {row['array']} is not a list")
    matches = [item for item in rows if isinstance(item, dict) and item.get(row["key"]) == row["value"]]
    if len(matches) != 1:
        raise _RuntimeSourceUnresolved(f"{locator}: {len(matches)} rows match, expected exactly one")
    repository = matches[0].get(RUNTIME_ROW_REPOSITORY_FIELD)
    pin = matches[0].get(RUNTIME_ROW_PIN_FIELD)
    part_repository = row.get("part_repository")
    if not part_repository:
        if any(isinstance(value, str) and RUNTIME_PART_SEPARATOR in value for value in (repository, pin)):
            raise _RuntimeSourceUnresolved(f"{locator}: composite row, but the source declares no "
                                           "part_repository")
        return repository, pin
    repositories, pins = _runtime_parts(repository), _runtime_parts(pin)
    if len(repositories) != len(pins):
        raise _RuntimeSourceUnresolved(f"{locator}: {len(repositories)} repository part(s) but "
                                       f"{len(pins)} release part(s)")
    wanted = _github_slug(part_repository)
    positions = [index for index, part in enumerate(repositories) if _github_slug(part) == wanted]
    if len(positions) != 1:
        raise _RuntimeSourceUnresolved(f"{locator}: {len(positions)} parts match part_repository, "
                                       "expected exactly one")
    return repositories[positions[0]], pins[positions[0]]


def _resolve_runtime_requirement(text: str, name: str, locator: str) -> str:
    wanted = _normalize_requirement(name)
    versions = [match.group(2) for match in map(REQUIREMENT_LINE_RE.match, text.splitlines())
                if match and _normalize_requirement(match.group(1)) == wanted]
    if not versions:
        raise _RuntimeSourceUnresolved(f"{locator}: requirement not found")
    if len(versions) > 1:
        raise _RuntimeSourceUnresolved(f"{locator}: requirement found {len(versions)} times, expected once")
    return versions[0]


def _resolve_runtime_source(repo_root: Path, source: dict):
    """(repository, pin) for one pin source; raises _RuntimeSourceUnresolved."""
    locator = _runtime_locator(source)
    if source.get("requirement") is not None:
        text = _read_runtime_source(repo_root, source, locator, as_json=False)
        repository, pin = source["repository"], _resolve_runtime_requirement(text, source["requirement"], locator)
    else:
        doc = _read_runtime_source(repo_root, source, locator, as_json=True)
        if source.get("row") is not None:
            repository, pin = _resolve_runtime_row(doc, source["row"], locator)
        else:
            pin = _runtime_pointer(doc, source["pin_pointer"], locator)
            repository = (_runtime_pointer(doc, source["repository_pointer"], locator)
                          if isinstance(source.get("repository_pointer"), str) else source.get("repository"))
    if not isinstance(pin, str) or not pin.strip():
        raise _RuntimeSourceUnresolved(f"{locator}: pin is not a non-empty string")
    if RUNTIME_PART_SEPARATOR in pin:
        raise _RuntimeSourceUnresolved(f"{locator}: pin still contains {RUNTIME_PART_SEPARATOR!r}")
    if _github_slug(repository) is None:
        raise _RuntimeSourceUnresolved(f"{locator}: repository is not a GitHub URL")
    return repository, pin


def resolve_runtime_pins(repo_root: Path, pin_sources=RUNTIME_PIN_SOURCES, watch_sources=RUNTIME_WATCH_SOURCES,
                         reserved_ids=()) -> dict:
    """Resolve each declared runtime pin against its source record, then add the
    watch-only upstreams. Entries are sorted by id.

    Raises ValueError for a declaration only a code edit can produce: a missing
    id/group/path (pin source) or id/group/repository (watch source), a group
    outside RUNTIME_GROUPS, an id that repeats another runtime id or one of
    ``reserved_ids``, a pin source without exactly one RUNTIME_SOURCE_FORMS key, a
    pointer source with neither repository_pointer nor repository, a requirement
    source without a literal repository, a repository literal that is not
    https://github.com/<owner>/<repo>, or a path that is absolute or contains "..".

    A record that moved or changed shape does not raise, so the daily job keeps its
    foundation and trading report: that entry is written with ``"pin": None``, its
    ``repository`` is the declared literal or None, and its ``"error"`` names only
    the declared path, the pointer, slot or requirement and a short reason. It
    never carries an exception's text: an OSError's carries an absolute host path,
    which build_manifest.assert_no_leak and scripts/validate.py reject."""
    seen, reserved = set(), set(reserved_ids or ())
    for source in pin_sources:
        _check_runtime_declaration(repo_root, source, RUNTIME_PIN_KIND, seen, reserved)
    for source in watch_sources:
        _check_runtime_declaration(repo_root, source, RUNTIME_WATCH_KIND, seen, reserved)
    entries = []
    for source in pin_sources:
        try:
            repository, pin = _resolve_runtime_source(repo_root, source)
            error = None
        except _RuntimeSourceUnresolved as unresolved:
            repository, pin, error = source.get("repository"), None, str(unresolved)
        entries.append({
            "id": source["id"], "group": source["group"], "kind": RUNTIME_PIN_KIND,
            "repository": repository, "pin": pin, "pin_source": _runtime_pin_source(source),
            "named_in": None, "error": error,
        })
    for source in watch_sources:
        entries.append({
            "id": source["id"], "group": source["group"], "kind": RUNTIME_WATCH_KIND,
            "repository": source["repository"], "pin": None, "pin_source": None,
            "named_in": source.get("named_in"), "error": None,
        })
    entries.sort(key=lambda e: e["id"])
    return {"entries": entries}


# ---------------------------------------------------------------------------
# Beyond the stars: catalogs/us-equities/{star-audit,coverage}.json
# ---------------------------------------------------------------------------

STAR_CANDIDATE_FIELDS = ("repository", "decision", "layers", "role", "rationale", "license")


def build_star_candidates(star_audit: dict, coverage: dict) -> dict:
    star_candidates = [
        {field: entry.get(field) for field in STAR_CANDIDATE_FIELDS}
        for entry in star_audit.get("entries", [])
    ]
    return {
        "star_candidates": star_candidates,
        "beyond_stars": coverage.get("beyond_stars", []),
        "star_count": (star_audit.get("counts") or {}).get("public_stars"),
    }


def build_models(models_doc: dict) -> dict:
    return {"entries": models_doc.get("entries", [])}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=Path("."),
                         help="Repository root; all default input paths are relative to this.")
    parser.add_argument("--foundation-manifest", type=Path, default=None)
    parser.add_argument("--foundation-decisions", type=Path, default=None)
    parser.add_argument("--stack", type=Path, default=None)
    parser.add_argument("--us-equities-dir", type=Path, default=None)
    parser.add_argument("--taxonomy-source", type=Path, default=None,
                         help="JSON document with a top-level #/taxonomy mapping.")
    parser.add_argument("--out", type=Path, required=True, help="Output directory for the working files.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root = args.repo_root
    foundation_manifest = args.foundation_manifest or root / "catalogs/foundation/manifest.json"
    foundation_decisions = args.foundation_decisions or root / "catalogs/foundation/decisions.json"
    stack_path = args.stack or root / "manifests/stack.json"
    us_equities_dir = args.us_equities_dir or root / "catalogs/us-equities"
    taxonomy_source = args.taxonomy_source or root / "catalogs/sota-convergence/manifest-20260922.json"

    manifest = load_json(foundation_manifest)
    decisions_doc = load_json(foundation_decisions)
    stack = load_json(stack_path)
    foundation_layers = build_foundation_layers(manifest, decisions_doc, stack)

    trading_catalog = build_trading_catalog(us_equities_dir)
    taxonomy = load_taxonomy(taxonomy_source)
    trading_by_layer = build_trading_by_layer(trading_catalog, taxonomy)
    unmapped = unmapped_tags(trading_catalog["entries"], tag_to_layers_map(taxonomy))
    trading_pins = resolve_trading_pins(
        root, taxonomy=taxonomy, card_ids={entry.get("id") for entry in trading_catalog["entries"]},
    )
    # A runtime id must not reuse an id a foundation or trading report row already has.
    reserved_ids = {component["id"] for layer in foundation_layers["layers"] for component in layer["components"]}
    reserved_ids.update(entry.get("id") for entry in trading_catalog["entries"])
    reserved_ids.update(entry["id"] for entry in trading_pins["entries"])
    reserved_ids.discard(None)
    runtime_pins = resolve_runtime_pins(root, reserved_ids=reserved_ids)

    star_audit = load_json(us_equities_dir / "star-audit.json")
    coverage = load_json(us_equities_dir / "coverage.json")
    star_candidates = build_star_candidates(star_audit, coverage)

    models_doc = load_json(us_equities_dir / "models.json")
    models_out = build_models(models_doc)

    out = args.out
    write_json(out / "foundation-layers.json", foundation_layers)
    write_json(out / "trading-catalog.json", trading_catalog)
    write_json(out / "trading-by-layer.json", trading_by_layer)
    write_json(out / "trading-pins.json", trading_pins)
    write_json(out / "runtime-pins.json", runtime_pins)
    write_json(out / "star-candidates.json", star_candidates)
    write_json(out / "models.json", models_out)

    print(json.dumps({
        "foundation_layers": len(foundation_layers["layers"]),
        "trading_entries": len(trading_catalog["entries"]),
        "trading_layers": len(trading_by_layer["layers"]),
        "unmapped_tags": unmapped,
        "trading_pins": [entry["id"] for entry in trading_pins["entries"]],
        "star_candidates": len(star_candidates["star_candidates"]),
        "beyond_stars": len(star_candidates["beyond_stars"]),
        "models": len(models_out["entries"]),
        "runtime_pins": len(runtime_pins["entries"]),
        "runtime_unresolved": sorted(entry["id"] for entry in runtime_pins["entries"] if entry["error"]),
    }))
    if unmapped:
        print(f"warning: {len(unmapped)} tag(s) have no taxonomy layer: {unmapped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
