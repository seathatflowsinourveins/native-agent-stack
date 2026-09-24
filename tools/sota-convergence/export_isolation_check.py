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
       (exit 1 on a role-label hit, 2 on a usage or input error). A --withhold-labels packet carries no component
       ids; --packet-keys (the lane_packets.py --keys-out file, required then and checked against every packet)
       restores them so id-keyed containers are matched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import landscape  # noqa: E402

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
# Inside an evidence record, a key carrying one of these words is a label when it isolates the winners.
EVIDENCE_ROLE_WORDS = frozenset({"winner", "winners", "incumbent", "incumbents", "chosen"})
# These are reported, not failed, inside evidence records (round 6, B6-6; round 7, OPR7-2): "primary_references",
# "selected_tests" and "primary_sources_and_pins" are what a receipt ran and cited, and a winner change made them
# isolate the new winner in a third of single-layer changes. A wave lists them in its record.
EVIDENCE_REPORTED_ROLE_WORDS = frozenset({"selected", "selection", "pick", "picked", "picks", "recommended",
                                          "preferred", "default", "primary", "current"})
# Positions reviewed as evidence although neither rule covers them: (file, container path) -> why.
REVIEWED_EVIDENCE_PATHS = {
    ("catalogs/landscape/native-practice.json", "$.installation_method.agents"):
        "the agents a recorded skill installation ran for; its recorded_commands name the same agents",
    # Round 6, B6-6 (role words now count in evidence records; these three positions were reviewed 2026-09-24).
    ("evidence/artifacts/native-returned-results-20260921/native-clients.json", "$.records[].selected_checks{keys}"):
        "the checks each recorded client session ran (rtk, qmd, context-mode, serena), keyed by tool, each with its "
        "command and returned result",
    ("blueprints/convergence-practice/service-reboot/plan.json", "$.primary_sources_reviewed_2026_09_20"):
        "the documentation and source URLs the reboot plan was reviewed against",
    ("blueprints/us-equities/research-evaluation/receipt.json", "$.primary_sources"):
        "the pinned documentation and source URLs the research-evaluation receipt cites",
}
# Record fields that cite evidence, by exact name: a token match would pass evidence_level, a label.
RECORD_EVIDENCE_FIELDS = frozenset({"evidence_refs", "evidence_ref", "evidence", "sources", "references",
                                    "source_findings", "observations", "registered_receipts"})
# Record fields reviewed as evidence although they are not citations: field -> why.
REVIEWED_EVIDENCE_FIELDS = {
    "qualification_gap": "states how far each candidate's evidence goes; fourteen challengers share the generic "
                         "'pinned source review only' text, the exercised winners carry specific gaps",
    "evidence_scope": "states whether a card's commands ran ('only the referenced receipt scope ran') or were a "
                      "pinned source review; the same exercised/not-exercised split the registered receipts show",
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
    """The lower-case words of a container path's last key: split on _ and -, and at camelCase boundaries."""
    last = json_path.rsplit(".", 1)[-1].replace("{keys}", "").replace("[]", "")
    return {token.lower() for token in re.split(r"[_\-\s]+|(?<=[a-z0-9])(?=[A-Z])", last) if token}


def _record_lists(node, path="$"):
    """(path, [record]) of every list of objects in a JSON document."""
    if isinstance(node, list):
        records = [item for item in node if isinstance(item, dict)]
        if records:
            yield path, records
        for item in node:
            yield from _record_lists(item, f"{path}[]")
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _record_lists(value, f"{path}.{key}")


def record_field_hits(export_dir: Path, packets_dir: Path, winners: dict, packet_keys: dict = None) -> dict:
    """layer -> sorted {file, path, field} of every field of a list of candidate records (catalog cards and the
    like) that isolates the layer's winners among the adopted candidates the list covers: present on exactly the
    winners, or a scalar value shared by two or more records and held by exactly the winners (independent review of
    #145, round 6, B6-3: evidence_level and installed_version did so in exported cards)."""
    lists = []
    for path in sorted(Path(export_dir).rglob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, ValueError):
            continue
        relative = path.relative_to(export_dir).as_posix()
        lists.extend((relative, json_path, records) for json_path, records in _record_lists(document))
    report = {}
    for layer, adopted in load_packets(packets_dir, packet_keys).items():
        win = winner_keys(adopted, winners.get(layer) or [])
        ids = {c.get("key"): candidate_ids(c) for c in adopted}
        hits = set()
        for relative, json_path, records in lists:
            matched = {}
            for record in records:
                found = value_ids(record[field] for field in ELEMENT_ID_FIELDS if isinstance(record.get(field), str))
                keys = [key for key, candidate in ids.items() if candidate & found]
                if len(keys) == 1:
                    matched.setdefault(keys[0], record)
            covered = set(matched)
            # Three records at least: with two, any field on one of them isolates whichever wins (round 7, OPR7-2).
            if not win or not (win <= covered) or covered == win or len(covered) < 3:
                continue
            fields = set().union(*(record.keys() for record in matched.values())) - set(ELEMENT_ID_FIELDS)
            for field in sorted(fields):
                present = {key for key, record in matched.items() if record.get(field) not in (None, "", [], {})}
                holders: dict = {}
                for key, record in matched.items():
                    value = record.get(field)
                    if isinstance(value, (str, int, float, bool)) and value not in ("",):
                        holders.setdefault(json.dumps(value), set()).add(key)
                # A column of few distinct values (a status, a level), not free text or versions where one duplicate
                # made every other value "isolate" its candidate (round 7, OPR7-2).
                categorical = (any(len(keys) >= 2 for keys in holders.values())
                               and len(holders) <= max(2, len(matched) // 2))
                if present in (win, covered - win) or (categorical and any(keys == win for keys in holders.values())):
                    hits.add((relative, json_path, field))
        report[layer] = [dict(zip(("file", "path", "field"), hit)) for hit in sorted(hits)]
    return report


def record_label_hits(report: dict) -> list:
    """Record-field hits not on an evidence field, each marked whether it sits in an evidence record. Reported, never
    failed (round 7, OPR7-2: intrinsic attributes such as license or a version isolate a new winner by coincidence);
    evidence-record hits are listed too, so a wave discloses them (BL7-6)."""
    return [{"layer": layer, **hit,
             "evidence_record": hit["file"].startswith(EVIDENCE_PREFIXES) or "receipt" in hit["file"].rsplit("/", 1)[-1]}
            for layer, hits in report.items() for hit in hits
            if hit["field"] not in RECORD_EVIDENCE_FIELDS and hit["field"] not in REVIEWED_EVIDENCE_FIELDS]


def evidence_hit(hit: dict) -> bool:
    """Whether an isolating container is evidence (see the module docstring). Inside an evidence record, a key that
    carries a role word (selected_repositories, primary_stack) is a label all the same (review of 52344da8)."""
    if (hit["file"], hit["path"]) in REVIEWED_EVIDENCE_PATHS:
        return True
    tokens = _key_tokens(hit["path"])
    last = hit["path"].rsplit(".", 1)[-1].replace("{keys}", "").replace("[]", "")
    if hit["file"].startswith(EVIDENCE_PREFIXES) or "receipt" in hit["file"].rsplit("/", 1)[-1]:
        # A selection of candidates, or a role word, is a label even in an evidence record when the container
        # isolates the winners; a reviewed position (REVIEWED_EVIDENCE_PATHS, returned above) is evidence.
        return not (EVIDENCE_SELECTION_KEY.match(last) or tokens & EVIDENCE_ROLE_WORDS)
    return hit["mode"] == "names_alone" and bool(tokens & EVIDENCE_KEY_TOKENS) and not tokens & ROLE_WORDS


def role_label_hits(report: dict) -> list:
    """Isolating containers that are labels, not evidence: the check's failing set."""
    return [{"layer": layer, **hit} for layer, hits in report.items() for hit in hits if not evidence_hit(hit)]


def evidence_role_word_hits(report: dict) -> list:
    """Isolating containers in evidence records under a key with a reported role word (EVIDENCE_REPORTED_ROLE_WORDS)
    at an unreviewed position: listed for the wave's disclosure, not failed (round 7, OPR7-2)."""
    return [{"layer": layer, **hit} for layer, hits in report.items() for hit in hits
            if evidence_hit(hit) and (hit["file"], hit["path"]) not in REVIEWED_EVIDENCE_PATHS
            and (hit["file"].startswith(EVIDENCE_PREFIXES) or "receipt" in hit["file"].rsplit("/", 1)[-1])
            and _key_tokens(hit["path"]) & EVIDENCE_REPORTED_ROLE_WORDS]


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
            # Present on exactly the winners, or on exactly the others (round 6, B6-6: a role absent on the winner).
            if present and present != everyone and (present == win or present == everyone - win):
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


PROSE_SUFFIXES = (".md", ".markdown", ".txt", ".rst")
_BLOCK_START = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|#{1,6}\s|>|\|)")
# A table header cell that states a selection makes each body row a selection statement (round 7, BL7-1:
# "| Layer | Selected native practice |" over "| Web research | Tavily, ..., OpenResearch |").
TABLE_CHOICE_HEADER = re.compile(r"\b(?:selected|selection|choices?|chosen|decisions?|in use|primary|current|default|"
                                 r"adopted|retained|retain|winners?|incumbents?)\b", re.I)
_PATH_TOKEN = re.compile(r"\S*/\S*|\S+\.(?:json|jsonl|md|txt|ya?ml|py|sh)\b")
_TABLE_SEPARATOR = re.compile(r":?-{2,}:?")


def _prose_blocks(text: str):
    """Paragraphs and list items (wrapped lines joined) and table rows; fenced code is skipped."""
    block, fenced = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            yield " ".join(block)
            block = []
            continue
        if fenced:
            continue
        if not line.strip() or _BLOCK_START.match(line) or (block and block[0].lstrip().startswith("|")):
            yield " ".join(block)
            block = []
        if line.strip():
            block.append(line.strip())
    yield " ".join(block)


def prose_statements(text: str):
    """(statement, choice_headed) pairs: each sentence of a paragraph or list item, and each table body row, marked
    when its table's header states a selection (round 7, BL7-1: a row was scored alone and its header lost)."""
    header = None
    for block in _prose_blocks(text):
        stripped = block.strip()
        if stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if cells and all(_TABLE_SEPARATOR.fullmatch(cell) for cell in cells if cell):
                continue
            if header is None:
                header = bool(TABLE_CHOICE_HEADER.search(" ".join(cells)))
                continue
            yield stripped, header
            continue
        header = None
        for sentence in re.split(r"(?<=[.!?;])\s+", stripped):
            if sentence:
                yield sentence, False


# An imperative choice right before a winner's name ("Retain skfolio 1.2.9", "Keep Serena for symbols").
IMPERATIVE_CHOICE = re.compile(r"(?:^|[|.;:]\s*)\s*(?:retain|keep|select|choose|adopt|prefer)\s+(?:the\s+)?", re.I)
IMPERATIVE_REACH = 30


def _states_selection(statement: str, winners) -> bool:
    """Whether a statement states a selection: a choice phrase, a status copula or opening label
    (lane_packets.CHOICE_PHRASE, STATUS_COPULA, opens_with_status), or an imperative choice before a winner's name.
    Not a bare selection word near a name, which also reads "`gh attestation verify` defaults ..." or "retained
    accepted SEC run" (round 7, BL7-1: false positives in 6 of the 18 layers)."""
    from lane_packets import CHOICE_PHRASE, STATUS_COPULA, opens_with_status
    if CHOICE_PHRASE.search(statement) or STATUS_COPULA.search(statement) or opens_with_status(statement):
        return True
    for match in IMPERATIVE_CHOICE.finditer(statement):
        window = statement[match.end():match.end() + IMPERATIVE_REACH]
        if any(any(start == 0 or window[:start].strip() == "" for start, _end in matcher.spans(window))
               for matcher in winners):
            return True
    return False


def _statement_exposes(statement: str, choice_headed: bool, winners, others) -> bool:
    """Whether a statement tells the winners apart from the adopted non-winners: it names a winner and no adopted
    non-winner, and states a selection, as a choice-headed table row or by _states_selection with path tokens removed
    (so "stack.json" in a file list is no choice) (round 7, BL7-1)."""
    if not any(matcher.search(statement) for matcher in winners):
        return False
    if any(matcher.search(statement) for matcher in others):
        return False
    return choice_headed or _states_selection(_PATH_TOKEN.sub(" ", statement), winners)


def prose_exposure(export_dir: Path, packets_dir: Path, winners: dict, packet_keys: dict = None) -> dict:
    """layer -> {"scored", "cited_files", "export_files"}: the exported prose files holding a statement that tells
    the layer's winners apart from its adopted non-winners (_statement_exposes), among the files its packet cites
    (directly or through a cited JSON file) and across the whole export, which a lane may also search. A layer
    whose winners are not among its adopted candidates is not scored. Exported prose is never rewritten (round 6,
    B6-4), so this is the exposure a wave discloses."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    from blind_checkout import _string_values, bare_reference
    from lane_packets import candidate_matcher
    export_dir = Path(export_dir)
    statements = {}
    for path in sorted(export_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in PROSE_SUFFIXES:
            statements[path] = list(prose_statements(path.read_text(encoding="utf-8", errors="replace")))
    packets = {}
    for packet_file in sorted(Path(packets_dir).glob("*__*.json")):
        packets[packet_file.stem.replace("__", "::", 1)] = json.loads(packet_file.read_text(encoding="utf-8"))
    report = {}
    for layer, adopted in load_packets(packets_dir, packet_keys).items():
        win = winner_keys(adopted, winners.get(layer) or [])
        if not win:
            report[layer] = {"scored": False, "cited_files": [], "export_files": []}
            continue
        winner_matchers = [candidate_matcher([c]) for c in adopted if c.get("key") in win]
        other_matchers = [candidate_matcher([c]) for c in adopted if c.get("key") not in win]
        refs = set()
        for candidate in packets.get(layer, {}).get("candidates") or []:
            for raw in (candidate.get("evidence_refs") or []) + [r.get("path") for r in candidate.get("registered_receipts") or []
                                                                 if isinstance(r, dict)]:
                bare = bare_reference(raw)
                if bare:
                    refs.add(bare)
        cited = set()
        for ref in refs:
            path = export_dir / ref
            cited |= {path} if path.is_file() else ({q for q in path.rglob("*") if q.is_file()} if path.is_dir() else set())
        for path in list(cited):
            if path.suffix == ".json":
                try:
                    values = _string_values(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, UnicodeError, ValueError):
                    continue
                cited |= {export_dir / bare for bare in (bare_reference(v) for v in values)
                          if bare and (export_dir / bare).is_file()}
        exposing = sorted(path.relative_to(export_dir).as_posix() for path, found in statements.items()
                          if any(_statement_exposes(text, headed, winner_matchers, other_matchers)
                                 for text, headed in found))
        cited_names = {path.relative_to(export_dir).as_posix() for path in cited}
        report[layer] = {"scored": True, "cited_files": [name for name in exposing if name in cited_names],
                         "export_files": exposing}
    return report


def packet_keys_input_issue(packets_dir: Path, keys_path) -> tuple:
    """(packet-keys document or None, issue or None): every packet parses, a packet that seals its candidates needs
    --packet-keys, and the document seals exactly each packet's candidates (independent review of #145, round 6,
    OPR6-5: a mistyped path must not read as a role-label hit)."""
    packets = {}
    for packet_file in sorted(Path(packets_dir).glob("*__*.json")):
        data = packet_file.read_bytes()
        try:
            packet = json.loads(data.decode("utf-8"))
        except ValueError as error:
            return None, f"packet {packet_file.name}: {error}"
        if not isinstance(packet, dict) or not isinstance(packet.get("candidates") or [], list):
            return None, f"packet {packet_file.name} is not a layer packet"
        packets[packet_file.name] = (hashlib.sha256(data).hexdigest(), packet)
    if not packets:
        return None, f"no layer packets under {packets_dir}"
    if keys_path is None:
        sealed = sorted(name for name, (_, packet) in packets.items() if landscape.SEALED_COMMITMENT_KEY in packet)
        return None, (f"packets {sealed[:3]} seal their candidates; pass --packet-keys" if sealed else None)
    try:
        document = json.loads(Path(keys_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return None, f"--packet-keys {keys_path}: {error}"
    for name, (digest, packet) in packets.items():
        issue = landscape.packet_keys_issue(document, name, digest, packet)
        if issue:
            return None, f"--packet-keys {keys_path}: {issue}"
    return document, None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Report which exported containers, catalog records and packet "
                                                 "fields isolate each layer's winners (exit 1 on a label hit).")
    parser.add_argument("export_dir", type=Path)
    parser.add_argument("packets_dir", type=Path)
    parser.add_argument("root", type=Path, nargs="?", default=REPO_ROOT,
                        help="catalog checkout whose ledgers name the winners (default: this checkout)")
    parser.add_argument("--packet-keys", help="the lane_packets.py --keys-out document; required for sealed packets")
    args = parser.parse_args(argv)
    for label, path in (("export", args.export_dir), ("packets", args.packets_dir), ("root", args.root)):
        if not path.is_dir():
            print(f"export_isolation_check: {label} directory {path} does not exist", file=sys.stderr)
            return 2
    packet_keys, issue = packet_keys_input_issue(args.packets_dir, args.packet_keys)
    if issue:
        print(f"export_isolation_check: {issue}", file=sys.stderr)
        return 2
    export_dir, packets_dir = args.export_dir, args.packets_dir
    winners = ledger_winners(args.root)
    report = isolation_hits(export_dir, packets_dir, winners, packet_keys)
    labels = role_label_hits(report)
    records = record_label_hits(record_field_hits(export_dir, packets_dir, winners, packet_keys))
    fields = packet_field_hits(packets_dir, winners)
    field_labels = packet_role_label_hits(fields)
    exposure = prose_exposure(export_dir, packets_dir, winners, packet_keys)
    print(json.dumps({"layers": len(report), "layers_with_hits": sum(bool(h) for h in report.values()),
                      "layers_with_evidence_hits": sorted(layer for layer, hits in report.items()
                                                          if any(evidence_hit(hit) for hit in hits)),
                      # Failing: labels outside evidence records and packet fields on exactly the winners.
                      "role_label_hits": labels, "packet_role_label_hits": field_labels,
                      # Reported for the wave's disclosure (round 7, OPR7-2, BL7-6).
                      "record_label_hits": records, "evidence_role_word_hits": evidence_role_word_hits(report),
                      "packet_evidence_field_hits": {layer: hits for layer, hits in fields.items() if hits},
                      "prose_exposed_layers": {layer: entry["cited_files"] for layer, entry in exposure.items()
                                               if entry["cited_files"]},
                      "prose_reachable_layers": sorted(layer for layer, entry in exposure.items()
                                                       if entry["export_files"]),
                      "unscored_layers": sorted(layer for layer, entry in exposure.items() if not entry["scored"])},
                     indent=1))
    return 1 if labels or field_labels else 0


if __name__ == "__main__":
    raise SystemExit(main())
