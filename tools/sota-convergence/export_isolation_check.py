#!/usr/bin/env python3
"""Per-layer winner-isolation check for a blind export (independent re-review of #145, blindness N1).

Every container in the export's JSON files -- a list (its strings, and the id fields of its objects) or an
object's key set -- is matched against each layer's adopted candidates (from its packet). A candidate is named by
its repository slug, repository name, component id or name, normalized (independent review of #145, round 4, F1:
the first version read only github.com/huggingface.co URLs and missed id-keyed lists such as the adoption
profiles' component_ids and recipe_map). A container isolates the layer's winners when the adopted candidates it
names are exactly the winners ("names_alone") or exactly the others ("complement").

A hit is evidence-volume asymmetry, reported and kept, when it sits in an evidence record (a file under
evidence/, blueprints/ or observability/, or any *receipt*.json: what was exercised is cited) or in a
names_alone list under an evidence key (sources, references, evidence, observations) of another file, or at a
REVIEWED_EVIDENCE_PATHS position. Any other hit is a role label and fails: a complement list outside an evidence
record fails whatever its key (round 4, F6).

The packets are checked the same way (review of #145, F5): a candidate field present on exactly the winners
among a layer's adopted candidates isolates them. On the 2026-09-23 packets, component_id, pin, upstream,
decisions and recipe_ref did so in 6 layers before lane_packets.py sealed them and in none after;
registered_receipts still does in 6. A field that cites evidence (EVIDENCE_FIELDS) is evidence-volume asymmetry
and stays; any other is a role label and fails.

Adapted from the GitHub-automation session's reviewer scripts (stdlib only).

Usage: export_isolation_check.py EXPORT_DIR PACKETS_DIR [LEDGER_ROOT] [--packet-keys FILE]
       (exit 1 on a role-label hit). A --withhold-labels packet carries no component ids; --packet-keys (the
       lane_packets.py --keys-out file) restores them so id-keyed containers are matched.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SLUG = re.compile(r"(?:https?://)?(?:www\.)?(github\.com|huggingface\.co)/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)")
LEDGERS = {"foundation": "catalogs/landscape/foundation.json", "us-equities": "catalogs/landscape/us-equities.json"}
# Whole key tokens that cite evidence (round 4, F6: matched as tokens, not substrings, and never with a role word).
EVIDENCE_KEY_TOKENS = frozenset({"source", "sources", "reference", "references", "evidence", "observation",
                                 "observations", "refs"})
ROLE_WORDS = frozenset({"selected", "winner", "winners", "default", "primary", "incumbent", "incumbents", "chosen",
                        "adopted", "stack"})
EVIDENCE_PREFIXES = ("evidence/", "blueprints/", "observability/")
# The keys blind_checkout.py strips under evidence/ as a selection of candidates (EVIDENCE_SELECTION_KEY there).
EVIDENCE_SELECTION_KEY = re.compile(r"^selected_(?:component|repositor|tool|candidate|stack)")
EVIDENCE_ROLE_WORDS = frozenset({"winner", "winners", "incumbent", "incumbents", "chosen"})
# Positions reviewed as evidence although neither rule covers them: (file, container path) -> why.
REVIEWED_EVIDENCE_PATHS = {
    ("catalogs/landscape/native-practice.json", "$.installation_method.agents"):
        "the agents a recorded skill installation ran for; its recorded_commands name the same agents",
}
# Object fields read as a list element's identity.
ELEMENT_ID_FIELDS = ("id", "component_id", "selected_component_id", "repository", "repo", "url", "name")
# Packet candidate fields a lane opens or reads as evidence and description; the candidate's identity fields.
# role and card_limitations are prose (reduced by lane_packets.withhold_prose) and evidence_kind a label (withheld),
# so an isolation there fails (round 5, N5).
EVIDENCE_FIELDS = frozenset({"evidence_refs", "registered_receipts"})
IDENTITY_FIELDS = frozenset({"key", "name", "repository", "adopted"})


def slug(value):
    match = SLUG.search(str(value or ""))
    return f"{match.group(1)}/{match.group(2)}".lower().removesuffix(".git") if match else None


def norm(value) -> str:
    text = str(value).strip().lower()
    for prefix in ("candidate:", "foundation-", "data-"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text.replace("_", "-").replace(" ", "-")


def candidate_ids(candidate: dict) -> set:
    ids = set()
    found = slug(candidate.get("repository"))
    if found:
        ids |= {found, norm(found.split("/")[-1])}
    for field in ("component_id", "name"):
        if candidate.get(field):
            ids.add(norm(candidate[field]))
    return ids


def value_ids(values) -> set:
    ids = set()
    for value in values:
        ids.add(norm(value))
        found = slug(value)
        if found:
            ids.add(found)
    return ids


def containers(node, path="$"):
    """(path, strings) of every list (its strings and its objects' id fields) and every object's key set."""
    if isinstance(node, list):
        values = set()
        for item in node:
            if isinstance(item, str):
                values.add(item)
            elif isinstance(item, dict):
                values |= {item[field] for field in ELEMENT_ID_FIELDS if isinstance(item.get(field), str)}
        if values:
            yield path, values
        for item in node:
            yield from containers(item, f"{path}[]")
    elif isinstance(node, dict):
        keys = {key for key in node if isinstance(key, str)}
        if keys:
            yield f"{path}{{keys}}", keys
        for key, value in node.items():
            yield from containers(value, f"{path}.{key}")


def ledger_winners(root: Path) -> dict:
    """layer -> [(repository slug, normalized component id)] of the ledger's recorded winners."""
    winners = {}
    for catalog, relative in LEDGERS.items():
        for row in json.loads((Path(root) / relative).read_text(encoding="utf-8")).get("layers") or []:
            winners[f"{catalog}::{row['layer_id']}"] = [(slug(w.get("repository")), norm(w.get("component_id") or ""))
                                                       for w in row.get("winners") or []]
    return winners


def load_packets(packets_dir: Path, packet_keys: dict = None) -> dict:
    """layer -> the packet's adopted candidates, each with its sealed fields restored from ``packet_keys``."""
    sealed = (packet_keys or {}).get("packets") or {}
    layers = {}
    for packet_file in sorted(Path(packets_dir).glob("*__*.json")):
        group, layer_id = packet_file.stem.split("__", 1)
        restored = (sealed.get(packet_file.name) or {}).get("candidates") or {}
        candidates = [dict(c, **restored.get(c.get("key"), {}))
                      for c in json.loads(packet_file.read_text(encoding="utf-8")).get("candidates") or []
                      if isinstance(c, dict)]
        layers[f"{group}::{layer_id}"] = [c for c in candidates if c.get("adopted")]
    return layers


def winner_keys(adopted: list, winners: list) -> set:
    """The keys of the adopted candidates that are the recorded winners (by slug, disambiguated by id)."""
    keys = set()
    for winner_slug, winner_id in winners:
        found = [c for c in adopted if winner_slug and slug(c.get("repository")) == winner_slug]
        if len(found) > 1:
            found = [c for c in found if winner_id in candidate_ids(c)] or found
        if not found:
            found = [c for c in adopted if winner_id and winner_id in candidate_ids(c)]
        keys |= {c.get("key") for c in found}
    return keys


def isolation_hits(export_dir: Path, packets_dir: Path, winners: dict, packet_keys: dict = None) -> dict:
    """layer -> sorted {file, path, mode} of every container that isolates the layer's winners."""
    documents = []
    for path in sorted(Path(export_dir).rglob("*.json")):
        try:
            documents.append((path.relative_to(export_dir).as_posix(), json.loads(path.read_text(encoding="utf-8"))))
        except (UnicodeDecodeError, ValueError):
            continue
    all_containers = [(relative, json_path, value_ids(values))
                      for relative, document in documents for json_path, values in containers(document)]
    report = {}
    for layer, adopted in load_packets(packets_dir, packet_keys).items():
        win = winner_keys(adopted, winners.get(layer) or [])
        if not adopted or not win:
            continue
        ids = {c.get("key"): candidate_ids(c) for c in adopted}
        everyone = set(ids)
        hits = set()
        for relative, json_path, found in all_containers:
            named = {key for key, candidate in ids.items() if candidate & found}
            if not named or named == everyone:
                continue
            if named == win:
                hits.add((relative, json_path, "names_alone"))
            elif everyone - named == win:
                hits.add((relative, json_path, "complement"))
        report[layer] = [dict(zip(("file", "path", "mode"), hit)) for hit in sorted(hits)]
    return report


def _key_tokens(json_path: str) -> set:
    last = json_path.rsplit(".", 1)[-1].replace("{keys}", "").replace("[]", "")
    return set(re.split(r"[_\-]", last.lower()))


def evidence_hit(hit: dict) -> bool:
    """Whether an isolating container is evidence (see the module docstring). Inside an evidence record, a key that
    carries a role word (selected_repositories, primary_stack) is a label all the same (review of 52344da8)."""
    if (hit["file"], hit["path"]) in REVIEWED_EVIDENCE_PATHS:
        return True
    tokens = _key_tokens(hit["path"])
    last = hit["path"].rsplit(".", 1)[-1].replace("{keys}", "").replace("[]", "")
    if hit["file"].startswith(EVIDENCE_PREFIXES) or "receipt" in hit["file"].rsplit("/", 1)[-1]:
        # A selection of candidates, or a strong role word, is a label even in an evidence record; a receipt's
        # other selected_* data (selected_checks: the commands run and their output) is evidence.
        # "primary" (primary sources) and "default" (default config) are ordinary in receipts, so only the
        # unambiguous role words count there.
        return not (EVIDENCE_SELECTION_KEY.match(last) or tokens & EVIDENCE_ROLE_WORDS)
    return hit["mode"] == "names_alone" and bool(tokens & EVIDENCE_KEY_TOKENS) and not tokens & ROLE_WORDS


def role_label_hits(report: dict) -> list:
    """Isolating containers that are labels, not evidence."""
    return [{"layer": layer, **hit} for layer, hits in report.items() for hit in hits if not evidence_hit(hit)]


def packet_field_hits(packets_dir: Path, winners: dict) -> dict:
    """layer -> sorted candidate fields present (not null or empty) on exactly the winners among the layer's
    adopted candidates, when that is a strict subset of them."""
    report = {}
    for layer, adopted in load_packets(packets_dir).items():
        win = winner_keys(adopted, winners.get(layer) or [])
        if not win or len(adopted) < 2:
            continue
        everyone = {c.get("key") for c in adopted}
        fields = set().union(*(c.keys() for c in adopted)) - IDENTITY_FIELDS
        hits = []
        for field in sorted(fields):
            present = {c.get("key") for c in adopted if c.get(field) not in (None, "", [], {})}
            if present and present != everyone and present == win:
                hits.append(field)
                continue
            # A value, or a list element, held by exactly the winners isolates them too (round 5, N5).
            holders: dict = {}
            listed = any(isinstance(candidate.get(field), list) for candidate in adopted)
            for candidate in adopted:
                value = candidate.get(field)
                for item in (value if isinstance(value, list) else [value]):
                    if item not in (None, "", [], {}):
                        holders.setdefault(json.dumps(item, sort_keys=True), set()).add(candidate.get("key"))
            # A scalar field only when categorical (some value shared by two or more candidates, as evidence_kind
            # was); a list element only when shared by two or more winners. A value unique to one candidate says
            # nothing about which one won.
            if listed:
                isolating = any(keys == win and len(win) >= 2 and keys != everyone for keys in holders.values())
            else:
                isolating = any(len(keys) >= 2 for keys in holders.values()) and any(
                    keys == win and keys != everyone for keys in holders.values())
            if isolating:
                hits.append(field)
        report[layer] = hits
    return report


def packet_role_label_hits(report: dict) -> list:
    """Packet field hits that are not evidence (EVIDENCE_FIELDS)."""
    return [{"layer": layer, "field": field} for layer, fields in report.items() for field in fields
            if field not in EVIDENCE_FIELDS]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    packet_keys = None
    if "--packet-keys" in argv:
        index = argv.index("--packet-keys")
        packet_keys = json.loads(Path(argv[index + 1]).read_text(encoding="utf-8"))
        del argv[index:index + 2]
    export_dir, packets_dir = Path(argv[0]), Path(argv[1])
    root = Path(argv[2]) if len(argv) > 2 else Path(__file__).resolve().parents[2]
    winners = ledger_winners(root)
    report = isolation_hits(export_dir, packets_dir, winners, packet_keys)
    labels = role_label_hits(report)
    fields = packet_field_hits(packets_dir, winners)
    field_labels = packet_role_label_hits(fields)
    print(json.dumps({"layers": len(report), "layers_with_hits": sum(bool(h) for h in report.values()),
                      "layers_with_evidence_hits": sorted(layer for layer, hits in report.items()
                                                          if any(evidence_hit(hit) for hit in hits)),
                      "role_label_hits": labels,
                      "packet_evidence_field_hits": {layer: hits for layer, hits in fields.items() if hits},
                      "packet_role_label_hits": field_labels}, indent=1))
    return 1 if labels or field_labels else 0


if __name__ == "__main__":
    raise SystemExit(main())
