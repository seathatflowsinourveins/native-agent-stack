#!/usr/bin/env python3
"""Per-layer winner-isolation check for a blind export (independent re-review of #145, blindness N1).

For every repository list in the export's JSON files, test whether it partitions a layer's adopted candidates
(from its packet) so that exactly the recorded winner set is left over ("complement": adopted - list == winners)
or named alone ("names_alone": adopted & list == winners). An isolating list under a key that does not cite evidence
(challenger_repositories, components, interfaces) is a role label and fails the check. One under an evidence key
(a receipt's references or sources) is evidence-volume asymmetry: what was exercised is cited, and that stays.
Adapted from the GitHub-automation session's reviewer script (stdlib only).

The packets themselves are checked the same way (review of #145, F5): a candidate field present on exactly the
winners among a layer's adopted candidates isolates them. On the 2026-09-23 packets, component_id, pin,
upstream, decisions and recipe_ref did so in 6 layers before lane_packets.py sealed them and in none after;
registered_receipts still does in 6. A field that cites evidence (EVIDENCE_FIELDS) is evidence-volume asymmetry
and stays; any other is a role label and fails.

Usage: export_isolation_check.py EXPORT_DIR PACKETS_DIR [LEDGER_ROOT]   (exit 1 on a role-label hit)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SLUG = re.compile(r"(?:https?://)?(?:www\.)?(github\.com|huggingface\.co)/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)")
LEDGERS = {"foundation": "catalogs/landscape/foundation.json", "us-equities": "catalogs/landscape/us-equities.json"}
# A list under a key that cites evidence (sources, references, evidence, observations) records what a run
# exercised: isolating the winner there, by naming it alone or by covering only the others, is evidence-volume
# asymmetry, not a label. Any other isolating list is a role label.
EVIDENCE_KEY = re.compile(r"source|reference|evidence|observation")
# Packet candidate fields a lane opens or reads as evidence and description; the candidate's identity fields.
EVIDENCE_FIELDS = frozenset({"evidence_refs", "registered_receipts", "evidence_kind", "role", "card_limitations"})
IDENTITY_FIELDS = frozenset({"key", "name", "repository", "adopted"})


def slug(value):
    match = SLUG.search(str(value or ""))
    return f"{match.group(1)}/{match.group(2)}".lower().removesuffix(".git") if match else None


def element_slug(item):
    if isinstance(item, str):
        return slug(item)
    if isinstance(item, dict):
        for key in ("repository", "repo", "url", "upstream", "source"):
            if isinstance(item.get(key), str) and slug(item[key]):
                return slug(item[key])
    return None


def lists_in(node, path="$"):
    if isinstance(node, list):
        slugs = {s for s in (element_slug(item) for item in node) if s}
        if slugs:
            yield path, slugs
        for index, item in enumerate(node):
            yield from lists_in(item, f"{path}[{index}]")
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from lists_in(value, f"{path}.{key}")


def ledger_winners(root: Path) -> dict:
    winners = {}
    for catalog, relative in LEDGERS.items():
        for row in json.loads((Path(root) / relative).read_text(encoding="utf-8")).get("layers") or []:
            winners[f"{catalog}::{row['layer_id']}"] = {s for s in (slug(w.get("repository"))
                                                                   for w in row.get("winners") or []) if s}
    return winners


def isolation_hits(export_dir: Path, packets_dir: Path, winners: dict) -> dict:
    """layer -> sorted {file, path, mode} of every list that isolates the layer's winners."""
    layers = {}
    for packet in sorted(Path(packets_dir).glob("*__*.json")):
        group, layer_id = packet.stem.split("__", 1)
        candidates = json.loads(packet.read_text(encoding="utf-8")).get("candidates") or []
        adopted = {s for s in (slug(c.get("repository")) for c in candidates if c.get("adopted")) if s}
        win = winners.get(f"{group}::{layer_id}") or set()
        if adopted and win:
            layers[f"{group}::{layer_id}"] = (adopted, (win & adopted) or win)
    all_lists = []
    for path in sorted(Path(export_dir).rglob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, ValueError):
            continue
        relative = path.relative_to(export_dir).as_posix()
        all_lists.extend((relative, json_path, slugs) for json_path, slugs in lists_in(document))
    report = {}
    for key, (adopted, win) in sorted(layers.items()):
        hits = set()
        for relative, json_path, slugs in all_lists:
            shared = adopted & slugs
            if not shared or shared == adopted:
                continue
            if adopted - slugs == win or shared == win:
                hits.add((relative, re.sub(r"\[\d+\]", "[]", json_path),
                          "complement" if adopted - slugs == win else "names_alone"))
        report[key] = [dict(zip(("file", "path", "mode"), hit)) for hit in sorted(hits)]
    return report


def packet_field_hits(packets_dir: Path, winners: dict) -> dict:
    """layer -> sorted candidate fields present (not null or empty) on exactly the winners among the layer's
    adopted candidates, when that is a strict subset of them."""
    report = {}
    for packet in sorted(Path(packets_dir).glob("*__*.json")):
        group, layer_id = packet.stem.split("__", 1)
        candidates = [c for c in json.loads(packet.read_text(encoding="utf-8")).get("candidates") or []
                      if isinstance(c, dict) and c.get("adopted")]
        win = winners.get(f"{group}::{layer_id}") or set()
        adopted = {slug(c.get("repository")) for c in candidates} - {None}
        if not (win & adopted) or len(candidates) < 2:
            continue
        fields = set().union(*(c.keys() for c in candidates)) - IDENTITY_FIELDS
        hits = []
        for field in sorted(fields):
            present = {slug(c.get("repository")) for c in candidates if c.get(field) not in (None, "", [], {})}
            if present and present != adopted and present == (win & adopted):
                hits.append(field)
        report[f"{group}::{layer_id}"] = hits
    return report


def packet_role_label_hits(report: dict) -> list:
    """Packet field hits that are not evidence (EVIDENCE_FIELDS)."""
    return [{"layer": layer, "field": field} for layer, fields in report.items() for field in fields
            if field not in EVIDENCE_FIELDS]


def role_label_hits(report: dict) -> list:
    """Isolating lists that are labels, not evidence: any whose key does not cite evidence."""
    labels = []
    for layer, hits in report.items():
        for hit in hits:
            last_key = hit["path"].rsplit(".", 1)[-1].removesuffix("[]")
            if not EVIDENCE_KEY.search(last_key):
                labels.append({"layer": layer, **hit})
    return labels


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    export_dir, packets_dir = Path(argv[0]), Path(argv[1])
    root = Path(argv[2]) if len(argv) > 2 else Path(__file__).resolve().parents[2]
    winners = ledger_winners(root)
    report = isolation_hits(export_dir, packets_dir, winners)
    labels = role_label_hits(report)
    fields = packet_field_hits(packets_dir, winners)
    field_labels = packet_role_label_hits(fields)
    print(json.dumps({"layers": len(report), "layers_with_hits": sum(bool(h) for h in report.values()),
                      "role_label_hits": labels,
                      "packet_evidence_field_hits": {layer: hits for layer, hits in fields.items() if hits},
                      "packet_role_label_hits": field_labels}, indent=1))
    return 1 if labels or field_labels else 0


if __name__ == "__main__":
    raise SystemExit(main())
