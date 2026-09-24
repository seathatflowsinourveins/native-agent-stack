#!/usr/bin/env python3
"""Two-family, counterbalanced adjudication of the layers on which the two lanes disagree.

A layer's Claude and Codex returns (``<work-dir>/{claude,codex}/<catalog>__<layer_id>.json``) disagree
when their winner component sets, resolved against the layer packet with
``scripts/landscape.py lane_winner_components``, differ. Such a layer is judged blind by both model
families, each in both presentation orders, and every judgment is attacked by one refuter:

1. ``inputs``: writes ``<work-dir>/adjudication-inputs/<name>.AB.json`` and ``<name>.BA.json``, the two
   scrubbed returns in complementary positions, plus the adjudication index (``index_path``: under
   ``$NAS_ADJUDICATION_STATE_DIR`` or ``~/.local/state/native-agent-stack/adjudication/``, outside the work dir).
   Which position holds the Claude return is drawn per layer and recorded only in that index, so neither a file
   name nor this code tells a judge which family wrote A (independent review of #145); assemble also derives it
   from the input contents.
   Scrubbing keeps only the judged content (SCRUB_KEEP) and drops any kept key present in one return
   but not the other, so lane identity, model and provenance are not shown to the judge.
2. ``codex``: one ``codex exec`` judge call and one refuter call per input file, built like
   codex_lane.py's command (read-only sandbox, codex_lane.ISOLATION_ARGS, ``--output-schema``,
   ``-o``, ``--json``). Writes ``<work-dir>/adjudication-judgments/codex/<name>.<order>.json``.
3. ``claude-args`` / ``claude-collect``: the args for ``adjudication-lane.js`` (the Claude family's
   saved workflow) and the step that turns its return into
   ``<work-dir>/adjudication-judgments/claude/<name>.<order>.json`` in the same shape.
4. ``assemble``: builds one adjudication record per layer, ``<out>/<name>.json``, validated by
   ``scripts/landscape.py judge_adjudication(raw, grandfathered=False, packet_sha256=...)`` before it is
   written; ``record_verdicts.py --adjudications <out>`` reads them.

A winner needs unanimous, unrefuted judgments from both families, each covering both orders; anything
else is a split (winner_lane null). A judge or refuter that finds reviewer identity in its input answers
``leak: true`` with the text (adjudication-prompt.md): that judgment is missing with failure "leak", never
counted. Leak records accumulate per family in ``adjudication-judgments/<family>/leaks.json``, keyed by input
file name and input sha256; an input with a recorded leak stays leaked (not rerun, never counted) until
``inputs`` rebuilds it with different content, and ``assemble`` reports its layer as a split in
``<work-dir>/adjudication-leaks.json``. Inputs carry no host path (``scrub_strings``) and no packet path, and
every repository root must pass ``root_issue``, the blind-adjudicator rule. A judgment counts only when both its judge and its refuter returned
a valid object: a lost refuter is never read as "unrefuted". Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import secrets
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
for _path in (HERE, REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import codex_lane  # noqa: E402
from build_manifest import sanitize_value  # noqa: E402  (the sealed form record_verdicts.sealed_text writes)
from scripts.landscape import (  # noqa: E402
    FAMILY_MODEL_PATTERNS, LANE_FAMILIES, judge_adjudication, lane_winner_components, model_family_issue,
    packet_keys_issue, packet_seals_candidates, unseal_packet)

PROMPT_PATH = HERE / "adjudication-prompt.md"
JUDGE_SCHEMA = HERE / "adjudication-judge.schema.json"
REFUTE_SCHEMA = HERE / "adjudication-refute.schema.json"
WORKFLOW_PATH = HERE / "adjudication-lane.js"
REFUTER_MARKER = "<!-- refuter -->"
ORDERS = ("AB", "BA")
# Which position shows the Claude return is a per-layer secret (independent review of #145, F3): `inputs` draws it
# for each layer and records it only in the index outside the inputs directory, so neither an input's file name
# nor this code tells a judge which family wrote A. The two orders always show it in complementary positions.


def claude_position(entry: dict, order: str):
    """The position ("A" or "B") that showed the Claude return in ``order`` for this index entry, or None."""
    value = (entry.get("claude_position") or {}).get(order) if isinstance(entry, dict) else None
    return value if value in ("A", "B") else None


def current_return_sha256(path: Path, lane_roots=()):
    """sealed_form_sha256 of the lane return at ``path`` now, or None when it is missing or not UTF-8 JSON."""
    try:
        return sealed_form_sha256(json.loads(Path(path).read_bytes().decode("utf-8")), lane_roots)
    except (OSError, ValueError):
        return None


def sealed_form_sha256(data, lane_roots=()) -> str:
    """sha256 of a lane return in exactly the form record_verdicts.py seals it: sources_read under a lane root
    relativized (``record_verdicts.with_relative_sources`` against this catalog checkout and the same
    ``lane_roots`` that record_verdicts gets as --lane-repo-root), then sanitized, sorted, indent 1, newline.
    The adjudication binds these, so CI can compare them with the row's lanes.<lane>.sealed_sha256 (independent
    review of #145, M2 and re-review R2)."""
    from record_verdicts import with_relative_sources  # the sealing code itself, not a copy of it
    relative = with_relative_sources(data, REPO_ROOT, tuple(Path(root) for root in lane_roots))
    return hashlib.sha256((json.dumps(sanitize_value(relative), sort_keys=True, indent=1) + "\n")
                          .encode("utf-8")).hexdigest()
FAMILIES = {"claude": "anthropic", "codex": "openai"}
assert FAMILIES == LANE_FAMILIES
SCRUB_KEEP = ("winner_keys", "why_selected", "winner_evidence_class", "winner_evidence_refs", "alternatives",
              "challenger_preferred", "overturn_when", "overturn_protocol", "open_gaps", "sources_read", "limits")
# Words that can name a lane in the kept prose. Only reported (index.json identity_mentions), never
# redacted: a candidate can legitimately be called "codex" or "claude".
IDENTITY_WORDS = re.compile(r"\b(claude|codex|anthropic|openai|opus|sonnet|haiku|gpt-[\w.-]+)\b", re.IGNORECASE)
MIN_WHY = 60
DEFAULT_TIMEOUT = 900.0
INPUTS_DIR = "adjudication-inputs"
# The index (with each layer's secret claude_position map) sits beside, not inside, the inputs directory, which
# the Codex judges may read (independent review of #145, F3).
INDEX_NAME = "adjudication-index.json"
# The index lives outside the work dir (Codex review of #145): every input path names the work dir, so a judge that
# listed it could read the positions. It sits under a state directory keyed by the work dir's path
# (NAS_ADJUDICATION_STATE_DIR, else ~/.local/state/native-agent-stack/adjudication), which no task names. Claude
# judges' reads are instruction-bound (the role and prompt name the only three paths); Codex judges' reads are
# audited, and a flagged call voids its judgment.
STATE_DIR_ENV = "NAS_ADJUDICATION_STATE_DIR"


def index_path(work_dir: Path) -> Path:
    base = Path(os.environ.get(STATE_DIR_ENV) or Path.home() / ".local" / "state" / "native-agent-stack" / "adjudication")
    key = hashlib.sha256(str(Path(work_dir).resolve()).encode("utf-8")).hexdigest()[:16]
    return base / key / INDEX_NAME
JUDGMENTS_DIR = "adjudication-judgments"
JUDGMENT_SCHEMA_VERSION = 1


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------- inputs

# Keys whose value is a list of evidence paths, at any depth of a kept field (winner_evidence_refs,
# alternatives[].evidence_refs, challenger_preferred.evidence_refs, overturn_protocol.fixture_paths, ...).
PATH_LIST_KEYS = frozenset({"sources_read", "winner_evidence_refs", "evidence_refs", "fixture_paths"})
_TRAILING_PUNCTUATION = ",;:)"
# A trailing line reference ("path:60-104", "path:L12") is a note too; record_verdicts.py strips the same form.
_LINE_SUFFIX = re.compile(r":[0-9L][0-9L,\-]*$")


def bare_path(entry: str, repo_roots=()) -> str:
    """The leading path token of one evidence-path entry, without the lane's notes: in the 2026-09-22
    returns 263 of 423 Claude sources_read entries read like "path (lines 60-104, prior round)" while every
    Codex entry is a bare path, so the notes alone told the judge which lane wrote A. A ``#fragment`` stays
    (it is part of the token), a trailing ``:line`` reference goes, and an absolute path under one of
    ``repo_roots`` becomes repository-relative."""
    token = entry.strip().split(None, 1)[0] if entry.strip() else ""
    path, hash_mark, fragment = token.partition("#")
    path = _LINE_SUFFIX.sub("", path.rstrip(_TRAILING_PUNCTUATION)).rstrip(_TRAILING_PUNCTUATION)
    for root in repo_roots:
        prefix = str(root).rstrip("/") + "/"
        if path.startswith(prefix):
            path = path[len(prefix):]
            break
    return path + (hash_mark + fragment.rstrip(_TRAILING_PUNCTUATION) if hash_mark else "")


def bare_paths(value, repo_roots=()):
    """``value`` with every PATH_LIST_KEYS list reduced to sorted, deduplicated bare paths, at any depth."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in PATH_LIST_KEYS and isinstance(item, list) and all(isinstance(entry, str) for entry in item):
                result[key] = sorted({path for path in (bare_path(entry, repo_roots) for entry in item) if path})
            else:
                result[key] = bare_paths(item, repo_roots)
        return result
    if isinstance(value, list):
        return [bare_paths(item, repo_roots) for item in value]
    return value


# Host paths in any string of a return (round-2 review, adjudication round 3). The blind-adjudicator role and
# adjudication-prompt.md treat an absolute host path outside the repository root as a leak, and both lanes
# record such paths (the packet's absolute path in sources_read, for one), so every string is scrubbed:
# a path under <work-dir>/packets/ becomes PACKET, a path under a lane repository root becomes relative, and
# any other absolute path, ~ or $HOME path, or <host-path> placeholder becomes the bare <outside-path>.
# http(s) URLs are left alone.
_PATH_CHARS = r"[^\s'\"|;&<>()`,]"
_PATH_START = r"(?:^|(?<=[\s'\"(=:\[{,`>]))"
# The first character of an absolute path's first segment (Codex review of #145): any word character,
# Unicode included (/évidence/x), or a dot; any other legal character (/-private/x, /@host/x) only when a
# later "/" shows a path, so prose such as "+/-" is not taken for one.
_SEGMENT_START = r"(?:[\w.]|(?!/)" + _PATH_CHARS + r"(?=" + _PATH_CHARS + r"*/))"
# A URL ends at a field separator too (Codex review of #145): "source=https://x;local=/home/..." must not exempt the
# host path after the semicolon.
URL = re.compile(r"https?://[^\s<>\"'`)\];,]+")
ABSOLUTE_TEXT_PATH = re.compile(_PATH_START + r"/+" + _SEGMENT_START + _PATH_CHARS + "*")
HOME_TEXT_PATH = re.compile(r"(?:~|\$HOME\b|\$\{HOME\})(?:/" + _PATH_CHARS + r"*)?(?![\w])")
HOST_PLACEHOLDER = re.compile(r"<host-path>(?:/" + _PATH_CHARS + "*)?")
PARENT_TEXT_PATH = re.compile(_PATH_START + r"\.\.(?:/" + _PATH_CHARS + r"*)?(?![\w])")
# Windows host paths (Codex review of #145), the forms build_manifest.HOST_PATH_PATTERNS also names: a drive
# path (C:\Users\example, C:/x) or a rooted backslash path (\Users\example\y, \\server\share\x).
WINDOWS_TEXT_PATH = re.compile(r"(?<![\w\\])(?:[A-Za-z]:[\\/]|\\{1,2}(?=[^\s\\'\"|;&<>()`,]+\\))"
                               + _PATH_CHARS + "*")
OUTSIDE = "<outside-path>"
# A host path can hold spaces (/home/example user/x.json, C:\Users\Example User\x.json): after an outside
# path is replaced, each following space-separated token that continues it (holds a / or \ separator) is
# absorbed too, so no suffix of it survives (Codex review of #145). Repository roots and work dirs cannot hold
# spaces (root_issue, refuse_work_dir_inside), so only outside paths need this.
# Where a spaced path ends cannot be told from prose ("/srv/My Project/private key" then "now"), so the rest of
# the clause after an outside path is absorbed: every following space-separated token up to a delimiter
# (,;()"'`|&<>), a line end, or a token ending a sentence (. ! ? :), whose punctuation is kept (Codex review of
# #145). Prose after a host path is lost; a private basename never survives.
_OUTSIDE_CONTINUATION = re.compile(r"<outside-path>((?:[ \t]+[^\s'\"|;&<>()`,]+)+)")


# A path segment glued to a delimiter the scrubber stops at ("/home/example,private/result.json") continues the
# path when a / or \ follows: absorbed whole (Codex review of #145).
_OUTSIDE_GLUED = re.compile(r"<outside-path>[,;()'\"`|&]+[^\s<>]*[/\\][^\s<>]*")


def _absorb_clause(match) -> str:
    """Absorb the tokens after an outside path up to and including the first that ends a sentence (keeping its
    punctuation); the text after that sentence end is kept (delta review of #145)."""
    text = match.group(1)
    for token in re.finditer(r"[^ \t]+", text):
        if token.group(0)[-1] in ".!?:":
            return OUTSIDE + token.group(0)[-1] + text[token.end():]
    return OUTSIDE
PACKET_TOKEN = "PACKET"
# What must never remain in an input after scrubbing (checked by ``unscrubbed_paths``): an absolute path, a
# ~ path (~/x or ~user/x), $HOME or ${HOME}, or a <host-path> placeholder.
RESIDUAL_PATTERNS = (
    # Independent of the replacement boundary (Codex review of #145): any "/" that starts a path segment
    # after a non-path character, so a path inside `backticks` or after other punctuation is still caught.
    re.compile(r"(?<![\w.:/~-])/+" + _SEGMENT_START + _PATH_CHARS + "*"),
    re.compile(r"(?<![\w])~[\w.-]*/" + _PATH_CHARS + "*"),
    re.compile(r"\$HOME\b|\$\{HOME\}"),
    re.compile(r"<host-path>"),
    re.compile(r"(?<![\w.])\.\./"),
    WINDOWS_TEXT_PATH,
)


def _outside(path: str) -> str:
    # The bare token only: a kept basename can name a lane (a worktree folder such as "nas-wt-codex-blind",
    # or a file only one lane's client reads, such as RTK.md) -- independent review of round 2.
    return OUTSIDE


def map_host_path(path: str, packets_dir: str, repo_roots=()) -> str:
    """One absolute path: PACKET under ``packets_dir``, repository-relative under a lane root, else
    the bare ``<outside-path>``."""
    # Resolve . and .. first (Codex review of #145): /root/export/../codex/x must not become ../codex/x.
    core = posixpath.normpath("/" + path.lstrip("/"))
    packets = str(packets_dir).rstrip("/")
    if core == packets or core.startswith(packets + "/"):
        return PACKET_TOKEN
    for root in repo_roots:
        prefix = str(root).rstrip("/")
        if core == prefix:
            return "."
        if core.startswith(prefix + "/"):
            return core[len(prefix) + 1:]
    return _outside(core)


def scrub_text(text: str, packets_dir: str, repo_roots=()) -> str:
    """Every host path in ``text`` (prose included) mapped by ``map_host_path``; http(s) URLs untouched."""
    pieces, last = [], 0
    for url in URL.finditer(text):
        pieces.append(_scrub_segment(text[last:url.start()], packets_dir, repo_roots))
        pieces.append(url.group(0))
        last = url.end()
    pieces.append(_scrub_segment(text[last:], packets_dir, repo_roots))
    return "".join(pieces)


def _split_tail(token: str):
    core = token.rstrip(".,;:")
    return core, token[len(core):]


def _scrub_segment(text: str, packets_dir: str, repo_roots) -> str:
    def absolute(match):
        core, tail = _split_tail(match.group(0))
        return map_host_path(core, packets_dir, repo_roots) + tail

    def outside(match):
        core, tail = _split_tail(match.group(0))
        return _outside(core) + tail

    text = WINDOWS_TEXT_PATH.sub(outside, text)
    text = HOST_PLACEHOLDER.sub(outside, text)
    text = HOME_TEXT_PATH.sub(outside, text)
    text = PARENT_TEXT_PATH.sub(outside, text)
    text = ABSOLUTE_TEXT_PATH.sub(absolute, text)
    text = _OUTSIDE_GLUED.sub(OUTSIDE, text)
    return _OUTSIDE_CONTINUATION.sub(_absorb_clause, text)


def scrub_strings(value, packets_dir: str, repo_roots=()):
    """``value`` with ``scrub_text`` applied to every string at any depth (keys are schema names and stay)."""
    if isinstance(value, dict):
        return {key: scrub_strings(item, packets_dir, repo_roots) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub_strings(item, packets_dir, repo_roots) for item in value]
    return scrub_text(value, packets_dir, repo_roots) if isinstance(value, str) else value


def unscrubbed_paths(value) -> list:
    """Every string fragment in ``value`` that still looks like a host path after scrubbing, sorted."""
    found = set()
    if isinstance(value, dict):
        for item in value.values():
            found.update(unscrubbed_paths(item))
    elif isinstance(value, list):
        for item in value:
            found.update(unscrubbed_paths(item))
    elif isinstance(value, str):
        text = URL.sub(" ", value)
        for pattern in RESIDUAL_PATTERNS:
            found.update(match.group(0) for match in pattern.finditer(text))
    return sorted(found)


def scrub_pair(claude_return: dict, codex_return: dict, repo_roots=(), packets_dir: str = None):
    """(scrubbed claude, scrubbed codex): only SCRUB_KEEP keys present in both returns; every string has its
    host paths mapped (``scrub_strings``), then every evidence-path list is reduced to sorted bare paths
    (``bare_paths``)."""
    shared = [key for key in SCRUB_KEEP if key in claude_return and key in codex_return]
    packets = packets_dir or "/nonexistent-packets-dir"
    return tuple(bare_paths(scrub_strings({key: data[key] for key in shared}, packets, repo_roots), repo_roots)
                 for data in (claude_return, codex_return))


# The repository-root rule lives in codex_lane.py so every blind tool enforces the same one (independent
# review of #145, O3); adjudicate keeps its names.
MIN_ROOT_COMPONENTS = codex_lane.MIN_ROOT_COMPONENTS
REFUSED_ROOTS = codex_lane.REFUSED_ROOTS
root_issue = codex_lane.root_issue


def refuse_roots(label: str, roots, must_exist: bool = False) -> str:
    """The exit-2 message for the first refused root, or None. ``must_exist``: the root's tree is hashed, so a
    missing directory (whose empty walk hashes to a valid-looking digest) is refused (Codex review of #145)."""
    for root in roots:
        issue = root_issue(root) or (f"{str(root)!r} is not an existing directory"
                                     if must_exist and not Path(root).is_dir() else None)
        if issue:
            return (f"adjudicate: {label} {issue}; blind-adjudicator refuses such a repository root, so neither "
                    "family would judge it -- use a blind export at least four directories deep")
    return None


def refuse_work_dir_inside(work_dir: Path, repo: Path) -> str:
    """blind-adjudicator refuses an input or packet file inside the repository root."""
    work, root = str(Path(work_dir).resolve()), str(Path(repo).resolve()).rstrip("/")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", work):
        return (f"adjudicate: the work dir {work} contains whitespace or a character outside [A-Za-z0-9._/-], "
                "which path scrubbing cannot tokenize")
    if work == root or work.startswith(root + "/"):
        return (f"adjudicate: the work dir {work} is inside the repository root {root}; blind-adjudicator refuses an "
                "input or packet file inside the repository root")
    return None


def identity_mentions(scrubbed: dict) -> list:
    return sorted({match.group(0).lower() for match in IDENTITY_WORDS.finditer(json.dumps(scrubbed))})


def components_list(components) -> list:
    return sorted([component_id, repository] for component_id, repository in components)


PACKET_SNAPSHOTS_DIR = "adjudication-packets"


def build_inputs(work_dir: Path, layers=None, repo_roots=(), packet_keys=None) -> dict:
    """Write the counterbalanced input files and index.json; return the index. ``repo_roots`` are the
    checkouts the lanes were given (their absolute evidence paths become repository-relative).
    ``packet_keys`` (lane_packets.py --keys-out) restores the sealed manifest fields of a --withhold-labels
    packet's candidates, so winner component sets compare as record_verdicts.py compares them; judges still
    read the sealed packet. An input is
    ``{layer, packet_sha256, A, B}``: the packet path is not in it (the judge's labelled ``Packet file:`` line
    carries it, from index.json). A layer whose scrubbed returns still hold a host path is listed in
    ``skipped`` with the offenders and gets no input file."""
    work_dir = Path(work_dir).resolve()
    out_dir = work_dir / INPUTS_DIR
    packets_dir = str((work_dir / "packets").resolve())
    index = {"schema_version": 2, "layers": [], "skipped": []}
    for packet_path in sorted((work_dir / "packets").glob("*.json")):
        name = packet_path.stem
        if "__" not in name or (layers and name.split("__", 1)[1] not in layers and name not in layers):
            continue
        paths = {lane: work_dir / lane / f"{name}.json" for lane in FAMILIES}
        if not all(path.is_file() for path in paths.values()):
            # Recorded as skipped, so assemble purges any earlier record for it (Codex review of #145).
            index["skipped"].append({"layer": name, "reason": "a lane return is missing: "
                                     + ", ".join(sorted(lane for lane, path in paths.items() if not path.is_file()))})
            continue
        # Each file is read once (Codex review of #145): the parsed object, its sha256 and the packet snapshot
        # all come from the same bytes, so a file rewritten while inputs runs cannot split them.
        returns, reasons, return_sha256 = {}, [], {}
        try:
            packet_bytes = packet_path.read_bytes()
            packet = json.loads(packet_bytes.decode("utf-8"))
        except (OSError, ValueError) as error:
            index["skipped"].append({"layer": name, "reason": f"packet unreadable: {error}"})
            continue
        packet_sha256 = hashlib.sha256(packet_bytes).hexdigest()
        resolved_packet = packet
        if packet_seals_candidates(packet):
            issue = (packet_keys_issue(packet_keys, packet_path.name, packet_sha256, packet) if packet_keys is not None
                     else "the packet seals its candidates' manifest fields: pass --packet-keys")
            if issue:
                index["skipped"].append({"layer": name, "reason": issue})
                continue
            resolved_packet = unseal_packet(packet, packet_keys, packet_path.name)
        for lane, path in paths.items():
            try:
                data = json.loads(path.read_bytes().decode("utf-8"))
                return_sha256[lane] = sealed_form_sha256(data, repo_roots)
            except (OSError, ValueError) as error:
                reasons.append(f"{lane} return does not parse: {error}")
                continue
            if not isinstance(data, dict):
                reasons.append(f"{lane} return is not a JSON object")
            elif data.get("packet_sha256") != packet_sha256:
                reasons.append(f"{lane} return packet_sha256 {data.get('packet_sha256')!r} is not the packet's "
                               f"{packet_sha256}")
            else:
                returns[lane] = data
        components = {}
        for lane, data in returns.items():
            issue, found = lane_winner_components(data, resolved_packet)
            if issue:
                reasons.append(f"{lane} return: {issue}")
            else:
                components[lane] = found
        if reasons:
            index["skipped"].append({"layer": name, "reason": "; ".join(reasons)})
            continue
        # Judges read an immutable, content-addressed copy of the packet bytes this index was built from
        # (Codex review of #145), never the live packet: <work-dir>/adjudication-packets/<sha>/packets/<name>.json.
        snapshot_packet = work_dir / PACKET_SNAPSHOTS_DIR / packet_sha256 / "packets" / packet_path.name
        if not snapshot_packet.is_file() or sha256_file(snapshot_packet) != packet_sha256:
            snapshot_packet.parent.mkdir(parents=True, exist_ok=True)
            snapshot_packet.write_bytes(packet_bytes)
        entry = {"layer": name, "packet_path": str(snapshot_packet), "packet_sha256": packet_sha256,
                 "components": {lane: components_list(components[lane]) for lane in FAMILIES},
                 # The lane return files these inputs were built from (Codex review of #145): assemble and
                 # record_verdicts.py refuse the adjudication for any other returns.
                 "lane_returns_sha256": dict(return_sha256),
                 # The lane roots the hashes were relativized against; record_verdicts.py must get the same
                 # --lane-repo-root, and assemble rechecks with these.
                 "lane_repo_roots": [str(root) for root in repo_roots]}
        if components["claude"] == components["codex"]:
            entry["agreement"] = "agree"
            index["layers"].append(entry)
            continue
        entry["agreement"] = "disagree"
        first = secrets.choice(("A", "B"))
        entry["claude_position"] = {"AB": first, "BA": "B" if first == "A" else "A"}
        claude_scrubbed, codex_scrubbed = scrub_pair(returns["claude"], returns["codex"], repo_roots, packets_dir)
        offenders = unscrubbed_paths([name, claude_scrubbed, codex_scrubbed])
        if offenders:
            # Never send a known leak to a judge: no input file for this layer, and a stale one is removed.
            for order in ORDERS:
                (out_dir / f"{name}.{order}.json").unlink(missing_ok=True)
            index["skipped"].append({"layer": name, "reason": "host paths remain after scrubbing: "
                                                                + ", ".join(offenders), "unscrubbed": offenders})
            continue
        entry["identity_mentions"] = sorted(set(identity_mentions(claude_scrubbed))
                                            | set(identity_mentions(codex_scrubbed)))
        entry["inputs"], entry["input_sha256"] = {}, {}
        for order in ORDERS:
            a, b = ((claude_scrubbed, codex_scrubbed) if entry["claude_position"][order] == "A"
                    else (codex_scrubbed, claude_scrubbed))
            input_path = out_dir / f"{name}.{order}.json"
            write_json(input_path, {"layer": name, "packet_sha256": packet_sha256, "A": a, "B": b})
            entry["inputs"][order] = str(input_path)
            entry["input_sha256"][order] = sha256_file(input_path)
        index["layers"].append(entry)
    if layers:
        # A selective rebuild keeps every other layer's earlier entry, so assemble still purges (or rebuilds)
        # their records instead of leaving them unrepresented (Codex review of #145).
        previous_path = index_path(work_dir)
        previous = load_json(previous_path) if previous_path.is_file() else {}
        rebuilt = {item["layer"] for item in index["layers"] + index["skipped"]}

        def selected(name):
            return name in layers or str(name).split("__", 1)[-1] in layers

        kept = {"layers": [], "skipped": []}
        for key in ("layers", "skipped"):
            for item in previous.get(key) or []:
                if not isinstance(item, dict) or item.get("layer") in rebuilt:
                    continue
                if selected(item.get("layer")):
                    # Selected but its packet is gone: skipped, so assemble purges its old record.
                    kept["skipped"].append({"layer": item["layer"], "reason": "the packet is missing"})
                else:
                    kept[key].append(item)
        for key in ("layers", "skipped"):
            index[key] = kept[key] + index[key]
    write_json(index_path(work_dir), index)
    (work_dir / INDEX_NAME).unlink(missing_ok=True)  # the round-15 location inside the work dir
    (out_dir / "index.json").unlink(missing_ok=True)  # the pre-F3 location, never read again
    return index


def load_index(work_dir: Path) -> dict:
    path = index_path(work_dir)
    if not path.is_file():
        raise SystemExit(f"adjudicate: {path} is missing; run `adjudicate.py inputs` first")
    return load_json(path)


def packet_paths(index: dict) -> dict:
    """layer name -> the packet path index.json records for it (inputs no longer carry it)."""
    return {entry["layer"]: entry.get("packet_path") or "" for entry in index.get("layers") or []}


def inputs_changed(index: dict, stems) -> list:
    """Stems ("<layer>.<order>") whose input file no longer has the sha256 `inputs` indexed (Codex review of
    #145): an edited input is not what scrub_pair produced and must not be judged."""
    indexed = {f"{entry['layer']}.{order}": (path, (entry.get("input_sha256") or {}).get(order))
               for entry in index.get("layers") or [] for order, path in (entry.get("inputs") or {}).items()}
    changed = []
    for stem in stems:
        path, sha = indexed.get(stem, (None, None))
        if not path or not Path(path).is_file() or sha is None or sha256_file(Path(path)) != sha:
            changed.append(stem)
    return changed


def layer_inputs_of(index: dict, name: str) -> dict:
    for entry in index.get("layers") or []:
        if entry.get("layer") == name:
            return entry.get("inputs") or {}
    return {}


def layer_input_hashes(index: dict, name: str) -> dict:
    """{input file name: current sha256} for both orders of one layer, sampled together."""
    for entry in index.get("layers") or []:
        if entry.get("layer") == name:
            return {Path(path).name: (sha256_file(Path(path)) if Path(path).is_file() else None)
                    for path in (entry.get("inputs") or {}).values()}
    return {}


def pending_items(index: dict, layers=None) -> list:
    """[(name, order, input_path, packet_sha256)] for every disagreeing layer."""
    items = []
    for entry in index.get("layers") or []:
        if entry.get("agreement") != "disagree":
            continue
        name = entry["layer"]
        if layers and name not in layers and name.split("__", 1)[1] not in layers:
            continue
        for order in ORDERS:
            items.append((name, order, entry["inputs"][order], entry["packet_sha256"]))
    return items


# ---------------------------------------------------------------- judgment objects

def leak_text(data):
    """The reported text when a judge or refuter object declares ``leak: true``, else None. A leak refusal
    never counts as a judgment (round-2 review)."""
    if isinstance(data, dict) and data.get("leak") is True:
        text = data.get("leak_text")
        return text if isinstance(text, str) and text.strip() else "(no leak text given)"
    return None


def valid_judge(data):
    """The judge object reduced to its schema keys, or None (a ``leak: true`` object is never valid)."""
    if not isinstance(data, dict) or leak_text(data) is not None:
        return None
    why, refs = data.get("why"), data.get("evidence_refs")
    if (data.get("preferred") not in ("A", "B") or not isinstance(why, str) or len(why.strip()) < MIN_WHY
            or not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs)):
        return None
    return {"preferred": data["preferred"], "why": why, "evidence_refs": refs}


def valid_refuter(data):
    if not isinstance(data, dict) or leak_text(data) is not None:
        return None
    refs = data.get("evidence_refs")
    if (type(data.get("refuted")) is not bool or not isinstance(data.get("reason"), str)
            or not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs)):
        return None
    return {"refuted": data["refuted"], "reason": data["reason"], "evidence_refs": refs}


LEAK = "leak"


def judgment_record(family, name, order, input_path, packet_sha256, model, repo, judge, refuter,
                    failure=None, exit_codes=None, leak=None, input_sha256=None, effort=None,
                    provenance=None) -> dict:
    """``leak`` is ``{"stage": "judge"|"refuter", "text": ...}`` when an agent refused on a reviewer-identity
    leak; the judgment is then missing with failure "leak"."""
    record = {"schema_version": JUDGMENT_SCHEMA_VERSION, "family": family, "layer": name, "order": order,
              "input_path": str(input_path), "input_sha256": input_sha256, "packet_sha256": packet_sha256,
              "model": model, "effort": effort, "provenance": provenance,
              "repo": str(repo) if repo else None, "judge": judge, "refuter": refuter,
              "failure": LEAK if leak else failure, "exit_codes": exit_codes or {}}
    if leak:
        record["leak"] = leak
    return record


def model_issue(model, family):
    """None when ``model`` is a name matching ``family``'s scripts/landscape.py model pattern."""
    return model_family_issue({"family": family, "name": model}, family, "model")


def usable_judgment(data, family, order, packet_sha256, leaked_inputs=None, entry=None):
    """None when the judgment file counts, else the reason it does not. A judgment whose model does not
    match its family's pattern (for example "unknown") does not count, so a resumed run reruns it rather
    than leaving a record judge_adjudication will reject. ``leaked_inputs`` (``recorded_leaks``) makes a
    judgment of an input whose current content has a recorded leak, by either family, count as "leak"."""
    if not isinstance(data, dict):
        return "not a JSON object"
    if leaked_inputs and input_key(data.get("input_path")) in leaked_inputs:
        return LEAK
    if data.get("family") != family or data.get("order") != order:
        return "family or order does not match its file name"
    if entry is not None and (data.get("layer") != entry.get("layer")
                              or data.get("input_path") != (entry.get("inputs") or {}).get(order)
                              or data.get("input_sha256") != (entry.get("input_sha256") or {}).get(order)):
        # The judgment must name this index's input for the layer (independent review of #145, M3): a copied
        # work dir's judgments point at another directory's inputs.
        return "judged an input this index did not build"
    # A judgment counts only for the input content it judged (Codex review of #145): rerunning `inputs`
    # after a lane return changed must not let an old A/B preference be read against new returns.
    input_path = data.get("input_path")
    current = sha256_file(Path(input_path)) if isinstance(input_path, str) and Path(input_path).is_file() else None
    if current is None or data.get("input_sha256") != current:
        return "judged a different input"
    issue = model_issue(data.get("model"), family)
    if issue:
        return issue
    if data.get("packet_sha256") != packet_sha256:
        return "judged a different packet"
    if data.get("leak") or data.get("failure") == LEAK:
        return LEAK
    if family == "openai" and data.get("audit_clean") is not True:
        # A Codex judgment counts only when its own calls' blind audit was clean (binding re-review N2).
        return data.get("failure") or "no clean blind audit recorded for this judgment"
    if valid_judge(data.get("judge")) is None:
        return data.get("failure") or "no valid judge object"
    if valid_refuter(data.get("refuter")) is None:
        return data.get("failure") or "no valid refuter object"
    return None


def split_prompt(text: str):
    if REFUTER_MARKER not in text:
        raise SystemExit(f"adjudicate: the prompt has no {REFUTER_MARKER} line separating judge and refuter")
    judge, refuter = text.split(REFUTER_MARKER, 1)
    return judge.strip() + "\n", refuter.strip() + "\n"


def fill(template: str, input_path, repo, judgment=None, packet_path="") -> str:
    """Fill the three labelled lines' placeholders ({INPUT_PATH}, {PACKET_PATH}, {REPO_ROOT}) and {JUDGMENT}.
    ``packet_path`` comes from index.json (``packet_paths``)."""
    text = (template.replace("{INPUT_PATH}", str(input_path)).replace("{PACKET_PATH}", str(packet_path))
            .replace("{REPO_ROOT}", str(repo)))
    return text.replace("{JUDGMENT}", json.dumps(judgment, sort_keys=True)) if judgment is not None else text


def refuse_git_repo(repo: Path):
    git_dirs = [str(path) for path in (repo, *repo.parents) if (path / ".git").exists()]
    if git_dirs:
        return (f"adjudicate: {git_dirs[0]} has .git, whose history a judge can read from {repo}; judge against a "
                "blind_checkout.py --export copy placed outside every repository")
    return None


# ---------------------------------------------------------------- codex

def run_codex_call(repo, schema, out_tmp, effort, prompt, model, timeout, events_path, validate):
    """Run one codex exec call, retried once. Returns (object or None, event model or None, exit codes, failure,
    leak text or None). A ``leak: true`` answer is final: it is not retried and never returns an object."""
    cmd = codex_lane.build_command(repo, schema, out_tmp, effort, prompt, model, codex_lane.ISOLATION_ARGS)
    exit_codes, event_model, failure = [], None, "no attempt ran"
    events_path.write_text("", encoding="utf-8")
    for _attempt in (1, 2):
        out_tmp.unlink(missing_ok=True)
        result = codex_lane.run_attempt(cmd, timeout)
        exit_codes.append(result["exit_code"])
        with events_path.open("a", encoding="utf-8") as handle:
            for line in result["stdout"].splitlines():
                if line.strip():
                    handle.write(line + "\n")
        found_model, _usage = codex_lane.extract_events_summary(codex_lane.parse_events(result["stdout"]))
        event_model = found_model or event_model
        if result["timed_out"] or result["exit_code"] != 0:
            failure = "timed out" if result["timed_out"] else f"codex exec exited {result['exit_code']}"
            continue
        try:
            data = load_json(out_tmp)
        except (OSError, ValueError):
            failure = "codex exec wrote no parseable output"
            continue
        finally:
            out_tmp.unlink(missing_ok=True)
        leaked = leak_text(data)
        if leaked is not None:
            return None, event_model, exit_codes, LEAK, leaked
        checked = validate(data)
        if checked is None:
            failure = "the output did not satisfy the schema"
            continue
        return checked, event_model, exit_codes, None, None
    return None, event_model, exit_codes, f"failed after retry: {failure}", None


def run_codex(args) -> int:
    work_dir = args.work_dir.resolve()
    repo = args.repo.resolve()
    if model_issue(args.model, "openai"):
        print(f"adjudicate: --model {args.model!r} does not match the openai pattern "
              f"{FAMILY_MODEL_PATTERNS['openai'].pattern}", file=sys.stderr)
        return 2
    # The path as given (absolutized, symlinks kept) and its resolved form must both pass: on macOS /home is a
    # symlink whose target is deep enough to pass the depth check (Codex review of #145, macOS CI).
    refusal = (refuse_roots("--repo", [Path(os.path.abspath(args.repo)), repo], must_exist=True)
               or refuse_git_repo(repo) or refuse_work_dir_inside(work_dir, repo))
    if refusal:
        print(refusal, file=sys.stderr)
        return 2
    judge_template, refute_template = split_prompt(args.prompt.read_text(encoding="utf-8"))
    layers = {item.strip() for item in args.layers.split(",") if item.strip()} if args.layers else None
    index = load_index(work_dir)
    packets = packet_paths(index)
    leaked_inputs = recorded_leaks(work_dir)
    items = pending_items(index, layers)
    entries_by_layer = {entry["layer"]: entry for entry in index.get("layers") or []}
    out_dir = work_dir / JUDGMENTS_DIR / "codex"
    # The code, prompt and evidence tree this run judges with, captured at launch (Codex review of #145).
    # Codex judges never load the user's global Codex instructions (codex_lane.isolated_codex_home).
    codex_lane.CHILD_CODEX_HOME = codex_lane.isolated_codex_home(work_dir)
    try:
        run_provenance = adjudication_provenance(args.prompt, repo)
    except ValueError as error:  # an escaping symlink: not a blind export
        print(f"adjudicate: {error}", file=sys.stderr)
        return 2
    pending, failures = [], []
    for name, order, input_path, packet_sha256 in items:
        out_path = out_dir / f"{name}.{order}.json"
        if input_key(input_path) in leaked_inputs:
            # Sticky: an input with a recorded leak is not rerun until `inputs` rebuilds it.
            failures.append((f"{name}.{order}", "leak recorded for this input; rebuild it with `inputs`"))
            continue
        if packets_changed([{"name": name, "order": order, "packet_path": packets.get(name, ""),
                             "packet_sha256": packet_sha256}]):
            failures.append((f"{name}.{order}", "the packet changed after `inputs`; rerun inputs"))
            continue
        if inputs_changed(index, [f"{name}.{order}"]):
            failures.append((f"{name}.{order}", "the input changed after `inputs` built it; rerun inputs"))
            continue
        try:
            existing = load_json(out_path)
            # Resume skips only a judgment made with the configured model and effort, under this run's
            # provenance: the same code, prompt, schemas, role and evidence tree (Codex review of #145).
            if (usable_judgment(existing, "openai", order, packet_sha256,
                                entry=entries_by_layer.get(name)) is None
                    and existing.get("model") == args.model and existing.get("effort") == args.effort
                    and existing.get("provenance") == run_provenance):
                continue
        except (OSError, ValueError, AttributeError):
            pass
        pending.append((name, order, input_path, packet_sha256, out_path))
    if pending and shutil.which("codex") is None:
        print("adjudicate: the codex CLI is not on PATH", file=sys.stderr)
        return 2
    events_dir = out_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    schemas = {}
    for label, source in (("judge", JUDGE_SCHEMA), ("refute", REFUTE_SCHEMA)):
        schemas[label] = out_dir / f"adjudication-{label}.codex-strict.schema.json"
        schemas[label].write_text(json.dumps(codex_lane.strict_output_schema(load_json(source)), indent=1,
                                             sort_keys=True) + "\n", encoding="utf-8")
    leaks, lock = [], threading.Lock()

    def process(item):
        name, order, input_path, packet_sha256, out_path = item
        stem = f"{name}.{order}"
        leak = None
        if inputs_changed(index, [stem]):
            # Rebuilt, edited or deleted after the scheduling check (Codex review of #145): never judge unindexed
            # bytes, and a missing input is a failure rather than a traceback.
            with lock:
                failures.append((stem, "the input changed after `inputs` built it; rerun inputs"))
            return
        try:
            judged_sha256 = sha256_file(Path(input_path))
        except OSError:  # deleted between the check and the read
            with lock:
                failures.append((stem, "the input changed after `inputs` built it; rerun inputs"))
            return
        # Both orders' content before the call: a leak suppresses both, bound to what was judged.
        both_sha256 = layer_input_hashes(index, name)
        judge, judge_model, judge_codes, failure, judge_leak = run_codex_call(
            repo, schemas["judge"], out_dir / f"{stem}.judge.out.tmp", args.effort,
            fill(judge_template, input_path, repo, packet_path=packets.get(name, "")), args.model, args.timeout,
            events_dir / f"{stem}.judge.jsonl", valid_judge)
        refuter, refute_model, refute_codes = None, None, []
        if judge_leak is not None:
            leak = {"stage": "judge", "text": redact_leak_text(judge_leak)}
        elif judge is not None:
            refuter, refute_model, refute_codes, failure, refute_leak = run_codex_call(
                repo, schemas["refute"], out_dir / f"{stem}.refute.out.tmp", args.effort,
                fill(refute_template, input_path, repo, judge, packets.get(name, "")), args.model, args.timeout,
                events_dir / f"{stem}.refute.jsonl", valid_refuter)
            if refute_leak is not None:
                leak = {"stage": "refuter", "text": redact_leak_text(refute_leak)}
            failure = f"refuter {failure}" if failure else None
        elif failure:
            failure = f"judge {failure}"
        if leak:
            failure = LEAK
        if packets_changed([{"name": name, "order": order, "packet_path": packets.get(name, ""),
                             "packet_sha256": packet_sha256}]):
            # The packet copy changed while the judges ran: nothing they returned counts.
            judge, refuter, leak, failure = None, None, None, "the packet snapshot changed during the call"
        elif inputs_changed(index, [stem]):
            # The input changed while the judges read it (Codex review of #145).
            judge, refuter, leak, failure = None, None, None, "the input changed during the call; rerun inputs"
        # This call's own audit, before its record is written (binding re-review N2): a flagged call is void even if
        # the run is interrupted before the end-of-run audit, and a resume never counts it.
        call_roots = [str(repo), str(Path(input_path).resolve()), str(Path(packets.get(name, "")).resolve())]
        flagged_calls = [stage for stage in ("judge", "refute")
                         if (events_dir / f"{stem}.{stage}.jsonl").is_file()
                         and audit_flagged(codex_lane.blind_audit(events_dir / f"{stem}.{stage}.jsonl", call_roots))]
        audit_clean = not flagged_calls
        if flagged_calls:
            judge, refuter, leak, failure = None, None, None, AUDIT_FLAGGED
        if leak:
            # Held until the run's tree and audit checks pass (Codex review of #145): a leak from a voided call is
            # not persisted, so it cannot suppress later valid runs.
            with lock:
                leaks.append((name, order, input_path, {**leak, "family": "openai", "input_sha256": judged_sha256,
                                                        "inputs_sha256": both_sha256}))
        # The configured --model first, as codex_lane.py records it; the event stream only reports.
        model = args.model or judge_model or "unknown"
        record = judgment_record(
            "openai", name, order, input_path, packet_sha256, model, repo, None if leak else judge,
            refuter, failure, {"judge": judge_codes, "refuter": refute_codes}, leak, judged_sha256, args.effort,
            run_provenance)
        record["audit_clean"] = audit_clean
        write_json(out_path, record)
        if refute_model and refute_model != judge_model:
            print(f"adjudicate: {stem} judge model {judge_model!r} and refuter model {refute_model!r} differ",
                  file=sys.stderr)
        if failure:
            with lock:
                failures.append((stem, failure))

    if args.jobs > 1:
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            list(executor.map(process, pending))
    else:
        for item in pending:
            process(item)
    try:
        provenance_after = adjudication_provenance(args.prompt, repo)
    except ValueError:  # an escaping link, loop or FIFO appeared: not the tree the judges were bound to
        provenance_after = None
    if pending and provenance_after != run_provenance:
        # The evidence tree (or the code, prompt or schemas) changed while the judges read it (Codex review of
        # #145): no judgment of this run is bound to what it read, so none counts.
        for name, order, _input_path, _packet_sha256, out_path in pending:
            try:
                record = load_json(out_path)
            except (OSError, ValueError):
                continue
            record.update({"judge": None, "refuter": None, "leak": None, "failure": TREE_CHANGED})
            write_json(out_path, record)
            failures.append((f"{name}.{order}", TREE_CHANGED))

    # The judges' labelled packet paths are the content-addressed snapshots (Codex review of #145).
    # Each call may read only the repository, its own input file and its packet snapshot (independent review of
    # #145, F3): not the inputs directory, which could hold other inputs, and not the index with the positions.
    call_files = {f"{name}.{order}": [input_path, packets.get(name, "")]
                  for name, order, input_path, _packet_sha256 in items}
    audit, roots_by_call = {}, {}
    for events in sorted(events_dir.glob("*.jsonl")):
        call = events.name[:-len(".jsonl")]
        stem = call.rsplit(".", 1)[0]
        roots_by_call[call] = [str(repo)] + [str(Path(path).resolve()) for path in call_files.get(stem, []) if path]
        audit[call] = codex_lane.blind_audit(events, roots_by_call[call])
    write_json(out_dir / "blind-audit.json", {"schema_version": 2, "allowed_roots": roots_by_call, "calls": audit})
    flagged = sorted(key for key, entry in audit.items()
                     if entry["web_search"] or entry["mcp_tool_calls"] or entry["flagged_commands"])
    if flagged:
        print(f"adjudicate: blind audit flags {len(flagged)} call(s): {', '.join(flagged)}", file=sys.stderr)
    # A flagged call (web search, an MCP tool, or a command reaching outside the repository, its input and its
    # packet) voids that judgment (Codex review of #145): it may have read the index or other inputs.
    this_run = {f"{name}.{order}" for name, order, _input, _sha, _out in pending}
    for stem in sorted({call.rsplit(".", 1)[0] for call in flagged} & this_run):
        record_path = out_dir / f"{stem}.json"
        try:
            record = load_json(record_path)
        except (OSError, ValueError):
            continue
        record.update({"judge": None, "refuter": None, "leak": None, "failure": AUDIT_FLAGGED})
        write_json(record_path, record)
        failures.append((stem, AUDIT_FLAGGED))
    voided = {stem for stem, failure in failures if failure in (TREE_CHANGED, AUDIT_FLAGGED)}
    record_leaks(out_dir / LEAKS_NAME, index, [leak for leak in leaks if f"{leak[0]}.{leak[1]}" not in voided])
    for stem, failure in sorted(failures):
        print(f"adjudicate: codex {stem}: {failure}", file=sys.stderr)
    return 1 if failures else 0


# ---------------------------------------------------------------- leaks

LEAKS_NAME = "leaks.json"
_LEAKS_LOCK = threading.Lock()
TREE_CHANGED = "the evidence tree or adjudication code changed during the run; rerun on a fixed export"
AUDIT_FLAGGED = "the blind audit flagged this judgment's calls (web, MCP or a read outside its input, packet and repository)"
ROLE_CHANGED = "the blind-adjudicator definition the workflow loads changed after claude-args; rerun claude-args"
LEAK_TEXT_LIMIT = 400


def redact_leak_text(text):
    """A reported leak's text as it may be retained or printed (Codex review of #145): the adjudicator quotes
    what it found, which can be a host path, so every path form the input scrubbing removes becomes
    <outside-path> here too, and the text is bounded."""
    if not isinstance(text, str):
        return text
    for pattern in (WINDOWS_TEXT_PATH, HOST_PLACEHOLDER, HOME_TEXT_PATH, ABSOLUTE_TEXT_PATH, PARENT_TEXT_PATH,
                    *RESIDUAL_PATTERNS):
        text = pattern.sub(OUTSIDE, text)
    text = _OUTSIDE_GLUED.sub(OUTSIDE, text)
    text = _OUTSIDE_CONTINUATION.sub(_absorb_clause, text)
    return text[:LEAK_TEXT_LIMIT]


def audit_flagged(entry: dict) -> bool:
    """A blind-audit entry that voids its judgment: web search, an MCP tool, or a flagged command."""
    return bool(entry.get("web_search") or entry.get("mcp_tool_calls") or entry.get("flagged_commands"))


def input_key(input_path):
    """(input file name, sha256 of its current bytes), or None when it cannot be read."""
    try:
        return (Path(input_path).name, sha256_file(input_path))
    except (OSError, TypeError):
        return None


def load_leak_records(path: Path) -> list:
    try:
        records = load_json(path).get("leaks")
    except (OSError, ValueError, AttributeError):
        return []
    return [record for record in records or [] if isinstance(record, dict)]


def record_leaks(path: Path, index: dict, leaks) -> list:
    """Append leak records to ``path`` (a family's ``leaks.json``); existing records are never removed or
    rewritten. Each record is keyed by the input file name and the input's sha256 when the leak was reported,
    and lists both of the layer's input files, since the leaking text sits in the layer's returns. Returns the
    new records."""
    inputs = {entry["layer"]: entry.get("inputs") or {} for entry in index.get("layers") or []}
    with _LEAKS_LOCK:
        records = load_leak_records(path)
        seen = {(r.get("input"), r.get("input_sha256"), r.get("family"), r.get("stage")) for r in records}
        added = []
        for name, order, input_path, leak in sorted(leaks, key=lambda item: (item[0], item[1])):
            key = input_key(input_path) or (Path(str(input_path)).name, None)
            # A leak binds to the content that was judged when the caller knows it (the Codex call's pre-call
            # hash), so a stale leak cannot mark an input rebuilt while the call ran (Codex review of #145).
            judged = leak.get("input_sha256") or key[1]
            # Both orders hold the same two returns, so a leak in one is a leak in both (Codex review of
            # #145): the other order's content at leak time is recorded too, and recorded_leaks marks both.
            layer_inputs = inputs.get(name, {})
            if isinstance(leak.get("inputs_sha256"), dict):
                # The caller sampled both orders before the judgment (Codex review of #145).
                both_by_name = dict(leak["inputs_sha256"])
            else:
                both_by_name = {Path(path).name: (judged if other == order else
                                                  (sha256_file(Path(path)) if Path(path).is_file() else None))
                                for other, path in layer_inputs.items()}
            record = {"input": key[0], "input_sha256": judged, "layer": name, "order": order,
                      "inputs_sha256": both_by_name,
                      "family": leak.get("family"), "stage": leak.get("stage"),
                      "text": redact_leak_text(leak.get("text")),
                      # Basenames only (Codex review of #145): the indexed paths expose the work-dir layout.
                      "inputs": {order_key: Path(str(path)).name for order_key, path in inputs.get(name, {}).items()}}
            if (record["input"], record["input_sha256"], record["family"], record["stage"]) in seen:
                continue
            seen.add((record["input"], record["input_sha256"], record["family"], record["stage"]))
            records.append(record)
            added.append(record)
        write_json(path, {"schema_version": 2, "leaks": records})
    for record in added:
        print(f"adjudicate: LEAK {record['family']} {record['layer']}.{record['order']} {record['stage']}: "
              f"{record['text']}", file=sys.stderr)
    return added


def leak_record_paths(work_dir: Path) -> list:
    return [Path(work_dir) / JUDGMENTS_DIR / lane / LEAKS_NAME for lane in FAMILIES]


def recorded_leaks(work_dir: Path) -> set:
    """{(input file name, input sha256)} with a recorded leak from either family. An input stays leaked until
    ``inputs`` rebuilds it and its sha256 changes."""
    leaked = set()
    for path in leak_record_paths(work_dir):
        for record in load_leak_records(path):
            leaked.add((record.get("input"), record.get("input_sha256")))
            for name, sha in (record.get("inputs_sha256") or {}).items():
                if sha:
                    leaked.add((name, sha))
    return leaked


# ---------------------------------------------------------------- claude

CLAUDE_ARGS_SNAPSHOT = "args-snapshot.json"
# adjudication-lane.js binds every agent() call to effort 'max' (inline literal, contract style; agent-lab #43).
CLAUDE_LANE_EFFORT = "max"


def claude_args(work_dir: Path, repo: Path, prompt_path: Path = PROMPT_PATH, layers=None, role_files=None) -> dict:
    """The adjudication-lane.js args for every disagreeing layer. The packet path comes from index.json. An
    input with a recorded leak (``recorded_leaks``) is left out and listed under ``leaked`` until ``inputs``
    rebuilds it."""
    index = load_index(work_dir)
    packets, leaked_inputs = packet_paths(index), recorded_leaks(work_dir)
    items, leaked = [], []
    for name, order, path, sha in pending_items(index, layers):
        if input_key(path) in leaked_inputs:
            leaked.append(f"{name}.{order}")
            continue
        items.append({"name": name, "order": order, "path": path, "packet_path": packets.get(name, ""),
                      "packet_sha256": sha})
    changed = packets_changed(items)
    if changed:
        raise ValueError("adjudicate: packets changed after `inputs` (rerun inputs): " + ", ".join(changed))
    edited = inputs_changed(index, [f"{item['name']}.{item['order']}" for item in items])
    if edited:
        raise ValueError("adjudicate: inputs changed after `inputs` built them (rerun inputs): " + ", ".join(edited))
    # The input content each item is judged on and the provenance it runs under; claude-collect binds every
    # judgment to this snapshot through the snapshot_id the workflow echoes back.
    snapshot = {"inputs": {f"{item['name']}.{item['order']}": sha256_file(Path(item["path"])) for item in items},
                "provenance": adjudication_provenance(prompt_path, repo),
                # claude-collect recomputes the provenance from these to catch a tree changed during the run.
                "prompt_path": str(Path(prompt_path).resolve()), "repo": str(repo),
                # The effective blind-adjudicator definitions the workflow will load (Codex review of #145);
                # claude-collect requires them unchanged.
                # The CLI passes --agent-file and any project-level copy; a library caller gets the vendored file.
                "roles": {str(Path(path).resolve()): sha256_file(Path(path))
                          for path in (role_files if role_files is not None else [VENDORED_ADJUDICATOR])}}
    snapshot["snapshot_id"] = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode("utf-8")).hexdigest()
    write_json(Path(work_dir).resolve() / JUDGMENTS_DIR / "claude" / CLAUDE_ARGS_SNAPSHOT, snapshot)
    return {"repo": str(repo), "prompt": prompt_path.read_text(encoding="utf-8"), "items": items, "leaked": leaked,
            "snapshot_id": snapshot["snapshot_id"]}


def packets_changed(items) -> list:
    """Items whose packet file no longer has the sha256 inputs indexed (Codex review of #145): judges would
    compare the old scrubbed returns against a different requirement or candidate set."""
    changed = []
    for item in items:
        path = Path(item.get("packet_path") or "")
        if not path.is_file() or sha256_file(path) != item.get("packet_sha256"):
            changed.append(f"{item['name']}.{item['order']}")
    return changed


def collect_claude(work_dir: Path, result, model: str, repo_override=None) -> list:
    """Write the Claude family's judgment files from the workflow return; returns the missing (stem, reason)."""
    work_dir = Path(work_dir).resolve()
    if not (isinstance(model, str) and FAMILY_MODEL_PATTERNS["anthropic"].fullmatch(model)):
        raise ValueError(f"--model {model!r} does not match the anthropic pattern "
                         f"{FAMILY_MODEL_PATTERNS['anthropic'].pattern}")
    if isinstance(result, dict) and "items" not in result and isinstance(result.get("result"), dict):
        result = result["result"]
    returned = {}
    for item in (result.get("items") if isinstance(result, dict) else None) or []:
        if isinstance(item, dict) and item.get("order") in ORDERS and isinstance(item.get("name"), str):
            returned[(item["name"], item["order"])] = item
    missing, leaks = [], []
    index = load_index(work_dir)
    leaked_inputs = recorded_leaks(work_dir)
    snapshot_path = work_dir / JUDGMENTS_DIR / "claude" / CLAUDE_ARGS_SNAPSHOT
    snapshot_doc = load_json(snapshot_path) if snapshot_path.is_file() else {}
    returned_id = result.get("snapshot_id") if isinstance(result, dict) else None
    # The stored snapshot must still hash to its own id (Codex review of #145): an edited snapshot could swap
    # in another run's repository, provenance and input hashes under an unchanged snapshot_id.
    unsealed = {key: value for key, value in snapshot_doc.items() if key != "snapshot_id"}
    if hashlib.sha256(json.dumps(unsealed, sort_keys=True).encode("utf-8")).hexdigest() != snapshot_doc.get("snapshot_id"):
        raise ValueError("adjudicate: the claude-args snapshot does not hash to its snapshot_id (it was edited); "
                         "rerun claude-args and the workflow")
    if not snapshot_doc.get("inputs"):
        # Nothing disagreed, so claude-args gave the workflow no items and there is nothing to collect (re-review):
        # the workflow then returns an argument issue without a snapshot_id.
        return []
    if returned_id is None or returned_id != snapshot_doc.get("snapshot_id"):
        # The result came from another claude-args run (Codex review of #145): its judgments ran under that
        # snapshot's inputs and evidence tree, not this one's.
        raise ValueError(f"adjudicate: the workflow result's snapshot_id {returned_id!r} is not the current "
                         f"claude-args snapshot {snapshot_doc.get('snapshot_id')!r}; rerun the workflow with "
                         "the current claude-args output")
    # The repository is the one claude-args validated and snapshotted (Codex review of #145); an override or a
    # returned value must name it exactly, since assemble relativizes paths under it.
    repo = snapshot_doc.get("repo")
    for label, value in (("--repo", repo_override),):
        if value is not None and str(value) != repo:
            raise ValueError(f"adjudicate: {label} {str(value)!r} is not the claude-args repository {repo!r}")
    snapshot = snapshot_doc.get("inputs") or {}
    snapshot_provenance = snapshot_doc.get("provenance")
    # What the workflow actually consumed (Codex review of #145): the prompt it echoes must hash to the snapshot's
    # prompt_sha256 and its repo must be the snapshot's; each item's echoed paths are checked below.
    consumed_prompt = result.get("prompt") if isinstance(result, dict) else None
    if not (isinstance(consumed_prompt, str) and isinstance(snapshot_provenance, dict)
            and hashlib.sha256(consumed_prompt.encode("utf-8")).hexdigest() == snapshot_provenance.get("prompt_sha256")):
        raise ValueError("adjudicate: the workflow result's prompt is not the one claude-args snapshotted; rerun "
                         "the workflow with the current claude-args output")
    if (result.get("repo") if isinstance(result, dict) else None) != repo:
        raise ValueError(f"adjudicate: the workflow result's repo is not the claude-args repository {repo!r}")
    # The evidence tree and code the workflow's judges read must still be what claude-args hashed (Codex
    # review of #145); a snapshot that cannot be recomputed counts as changed.
    try:
        tree_changed = adjudication_provenance(Path(snapshot_doc["prompt_path"]),
                                               Path(snapshot_doc["repo"])) != snapshot_provenance
    except (KeyError, TypeError, OSError, ValueError):
        tree_changed = True
    roles = snapshot_doc.get("roles")
    roles_changed = not (isinstance(roles, dict) and roles and all(
        Path(path).is_file() and sha256_file(Path(path)) == digest for path, digest in roles.items()))
    for name, order, input_path, packet_sha256 in pending_items(index):
        if f"{name}.{order}" not in snapshot:
            # Only the items claude-args gave this workflow run are collected; other layers' judgment files
            # (a selective --layers rerun, or an omitted leaked input) are left as they are.
            continue
        item = returned.get((name, order)) or {}
        judged_sha256 = snapshot.get(f"{name}.{order}")
        # A deleted input is a changed one (Codex review of #145), recorded as missing rather than a traceback.
        input_changed = not Path(input_path).is_file() or judged_sha256 != sha256_file(Path(input_path))
        consumed_other = bool(item) and (item.get("path") != input_path
                                         or item.get("packet_path") != packet_paths(index).get(name))
        packet_changed = bool(packets_changed([{"name": name, "order": order,
                                                "packet_path": packet_paths(index).get(name, ""),
                                                "packet_sha256": packet_sha256}]))
        if input_key(input_path) in leaked_inputs:
            # Sticky: a judgment of an input with a recorded leak never counts, whatever the workflow returned.
            write_json(work_dir / JUDGMENTS_DIR / "claude" / f"{name}.{order}.json", judgment_record(
                "anthropic", name, order, input_path, packet_sha256, model, repo, None, None, LEAK,
                leak={"stage": "recorded", "text": "a leak is recorded for this input's current content"}))
            missing.append((f"{name}.{order}", LEAK))
            continue
        judge, refuter = valid_judge(item.get("judge")), valid_refuter(item.get("refuter"))
        leak = item.get("leak") if isinstance(item.get("leak"), dict) else None
        if leak is None:
            for stage in ("judge", "refuter"):
                if leak_text(item.get(stage)) is not None:
                    leak = {"stage": stage, "text": leak_text(item.get(stage))}
                    break
        if leak is not None:
            leak = {"stage": leak.get("stage"), "text": redact_leak_text(leak.get("text"))}
            judge, refuter = None, None
            if not (input_changed or packet_changed or tree_changed or roles_changed or consumed_other):
                # A leak from a run whose bindings no longer hold (a rebuilt input, a changed packet, tree or
                # role, or other consumed arguments) is discarded, so it cannot mark a valid input as leaked
                # (Codex review of #145).
                both = {Path(entry_path).name: snapshot.get(f"{name}.{other}")
                        for other, entry_path in (layer_inputs_of(index, name) or {}).items()}
                leaks.append((name, order, input_path, {**leak, "family": "anthropic",
                                                        "input_sha256": judged_sha256, "inputs_sha256": both}))
        if leak is not None:
            failure = LEAK
        elif not item:
            failure = "lost: the workflow returned no item"
        elif judge is None:
            failure = "judge lost or invalid"
        elif refuter is None:
            failure = "refuter lost or invalid"
        else:
            failure = None
        if item and item.get("packet_sha256") not in (None, packet_sha256):
            failure, judge, refuter = "the workflow judged a different packet", None, None
        if input_changed:
            # The input changed since claude-args built the workflow's items.
            failure, judge, refuter, leak = "the input changed after claude-args; rerun claude-args", None, None, None
        elif packet_changed:
            # The immutable packet copy the judges read no longer holds its indexed bytes.
            failure, judge, refuter, leak = "the packet snapshot changed; rerun inputs", None, None, None
        elif consumed_other:
            failure, judge, refuter, leak = ("the workflow judged other input or packet paths than claude-args "
                                             "gave it"), None, None, None
        elif tree_changed:
            failure, judge, refuter, leak = TREE_CHANGED, None, None, None
        elif roles_changed:
            failure, judge, refuter, leak = ROLE_CHANGED, None, None, None
        write_json(work_dir / JUDGMENTS_DIR / "claude" / f"{name}.{order}.json", judgment_record(
            "anthropic", name, order, input_path, packet_sha256, model, repo, judge, refuter, failure,
            leak=leak, input_sha256=judged_sha256, effort=CLAUDE_LANE_EFFORT, provenance=snapshot_provenance))
        if failure:
            missing.append((f"{name}.{order}", failure))
    record_leaks(work_dir / JUDGMENTS_DIR / "claude" / LEAKS_NAME, index, leaks)
    return missing


# ---------------------------------------------------------------- assemble

def relative_ref(ref: str, repo) -> str:
    if repo and isinstance(ref, str) and ref.startswith(str(repo).rstrip("/") + "/"):
        return ref[len(str(repo).rstrip("/")) + 1:]
    return ref


def positions_from_content(work_dir: Path, entry: dict) -> dict:
    """order -> "A" or "B": where each input file shows the Claude return, found by re-scrubbing the current lane
    returns (bound by lane_returns_sha256 before assemble gets here) and comparing; an order whose input matches
    neither arrangement is left out."""
    name = entry["layer"]
    try:
        returns = {lane: json.loads((Path(work_dir) / lane / f"{name}.json").read_bytes().decode("utf-8"))
                   for lane in FAMILIES}
    except (OSError, ValueError):
        return {}
    claude_scrubbed, codex_scrubbed = scrub_pair(returns["claude"], returns["codex"], entry.get("lane_repo_roots") or (),
                                                 str((Path(work_dir) / "packets").resolve()))
    positions = {}
    for order, input_path in (entry.get("inputs") or {}).items():
        try:
            body = load_json(Path(input_path))
        except (OSError, ValueError):
            continue
        if body.get("A") == claude_scrubbed and body.get("B") == codex_scrubbed:
            positions[order] = "A"
        elif body.get("A") == codex_scrubbed and body.get("B") == claude_scrubbed:
            positions[order] = "B"
    return positions


def assemble_layer(work_dir: Path, entry: dict, leaked_inputs=frozenset()):
    """(record, notes, leaked input names) for one disagreeing layer; notes name every judgment that does not
    count. Every judgment of an input whose current content has a recorded leak (either family) is dropped."""
    name, packet_sha256 = entry["layer"], entry["packet_sha256"]
    judgments, whys, refs, notes, provenances, repos = [], [], set(), [], [], set()
    content_positions = positions_from_content(work_dir, entry)
    leaked_orders = [order for order in ORDERS
                     if input_key((entry.get("inputs") or {}).get(order)) in leaked_inputs]
    for lane, family in FAMILIES.items():
        for order in ORDERS:
            if order in leaked_orders:
                notes.append(f"{family} {order}: leak recorded for the input; every judgment of it is dropped")
                continue
            path = work_dir / JUDGMENTS_DIR / lane / f"{name}.{order}.json"
            try:
                data = load_json(path)
            except (OSError, ValueError):
                notes.append(f"{family} {order}: no judgment file")
                continue
            reason = usable_judgment(data, family, order, packet_sha256, leaked_inputs, entry)
            if reason:
                notes.append(f"{family} {order}: {reason}")
                continue
            judge, refuter = data["judge"], data["refuter"]
            provenances.append(data.get("provenance"))
            if isinstance(data.get("repo"), str):
                repos.add(data["repo"])
            position = claude_position(entry, order)
            if position is None or content_positions.get(order) != position:
                # The position is derived from the input contents (the hash-bound lane returns re-scrubbed), so an
                # edited index map cannot flip which family a preference counts for (Codex review of #145).
                notes.append(f"{family} {order}: the index position does not match the input contents; rerun inputs")
                continue
            preferred = judge["preferred"]
            judgments.append({
                "claude_position": position, "preferred_position": preferred,
                "preferred_lane": "claude" if preferred == position else "codex",
                "refuting_votes": 1 if refuter["refuted"] else 0,
                "judge": {"model": data.get("model"), "family": family},
                "stripped_packet_sha256": packet_sha256})
            whys.append(f"{family} {order}: {' '.join(judge['why'].split())}"
                        + (f" [refuted: {' '.join(refuter['reason'].split())}]" if refuter["refuted"] else ""))
            refs.update(relative_ref(ref, data.get("repo")) for ref in judge["evidence_refs"] + refuter["evidence_refs"])
    families = {judgment["judge"]["family"]: set() for judgment in judgments}
    for judgment in judgments:
        families[judgment["judge"]["family"]].add(judgment["claude_position"])
    missing = [family for family in sorted(set(FAMILIES.values())) if families.get(family) != {"A", "B"}]
    lanes = {judgment["preferred_lane"] for judgment in judgments}
    refuted = sum(judgment["refuting_votes"] for judgment in judgments)
    winner = next(iter(lanes)) if judgments and len(lanes) == 1 and not refuted and not missing else None
    if winner:
        head = f"winner {winner}: all {len(judgments)} judgments from both families in both orders agree, none refuted"
    elif missing:
        head = f"split: missing {', '.join(missing)} judgments in both presentation orders"
    elif refuted:
        head = f"split: {refuted} judgment(s) refuted"
    else:
        head = "split: the judgments chose different lanes"
    if leaked_orders:
        winner = None
        head = (f"split: a leak is recorded for input(s) {', '.join(f'{name}.{order}.json' for order in leaked_orders)}"
                f"; no judgment of a leaked input counts")
    record = {"winner_lane": winner, "why": head + ". " + " | ".join(whys) if whys else head,
              "evidence_refs": sorted(refs), "judgments": judgments}
    record["_repos"] = sorted(repos)
    # Every counted judgment must have run under one recorded provenance; assemble stamps it on the record.
    distinct = {json.dumps(item, sort_keys=True) for item in provenances}
    record["_provenance"] = (json.loads(next(iter(distinct))) if len(distinct) == 1 and provenances
                             and isinstance(provenances[0], dict) else None)
    record["_provenance_issue"] = (None if record["_provenance"] is not None or not judgments else
                                   "the counted judgments carry no provenance or different provenance "
                                   "(adjudication code, prompt, schemas or workflow changed between runs)")
    if missing:
        record["missing_families"] = missing
    return record, notes, [f"{name}.{order}.json" for order in leaked_orders]


ADJUDICATOR_ROLE = "blind-adjudicator"
VENDORED_ADJUDICATOR = HERE.parents[1] / "examples" / "claude-native" / "agents" / f"{ADJUDICATOR_ROLE}.md"
DEFAULT_ADJUDICATOR_FILE = Path.home() / ".claude" / "agents" / f"{ADJUDICATOR_ROLE}.md"


# One digest for both the lanes and the adjudication (codex_lane.tree_sha256).
tree_sha256 = codex_lane.tree_sha256


def adjudication_provenance(prompt_path: Path = PROMPT_PATH, repo: Path = None) -> dict:
    """What produced a judgment: this script, the prompt actually used, both judgment schemas, the Claude
    family's workflow, the vendored blind-adjudicator role it runs as (claude-args refuses an installed role
    other than this), and the evidence tree it judged against (Codex review of #145). Both families' counted
    judgments must carry the same provenance for a layer to be assembled."""
    provenance = {"adjudicate_py_sha256": sha256_file(Path(__file__).resolve()),
                  "prompt_sha256": sha256_file(Path(prompt_path)),
                  "judge_schema_sha256": sha256_file(JUDGE_SCHEMA), "refute_schema_sha256": sha256_file(REFUTE_SCHEMA),
                  "workflow_sha256": sha256_file(WORKFLOW_PATH),
                  "adjudicator_role_sha256": sha256_file(VENDORED_ADJUDICATOR)}
    if repo is not None:
        provenance["repo_tree_sha256"] = tree_sha256(Path(repo))
    return provenance


def adjudicator_role_issue(agent_file: Path):
    """None when the role definition the Claude judges will load is the vendored one (Codex review of #145):
    a stale or edited copy could load project instructions or broader tools."""
    if not Path(agent_file).is_file():
        return f"adjudicate: role definition {agent_file} not found; install the vendored {ADJUDICATOR_ROLE}.md"
    if sha256_file(Path(agent_file)) != sha256_file(VENDORED_ADJUDICATOR):
        return (f"adjudicate: {agent_file} is not the vendored {VENDORED_ADJUDICATOR.name}; install the vendored "
                "role before running the Claude judges")
    return None


def assemble(work_dir: Path, out_dir: Path, layers=None):
    """Write every valid record; return (written names, issues)."""
    work_dir, out_dir = Path(work_dir).resolve(), Path(out_dir)
    written, issues, split_layers = [], [], []
    index = load_index(work_dir)
    leaked_inputs = recorded_leaks(work_dir)
    # Every layer inputs indexed or skipped loses its earlier record first, so a layer that no longer
    # disagrees, was skipped (for example a surviving host path) or is refused below never leaves a stale
    # winner for record_verdicts --adjudications (Codex review of #145).
    for entry in list(index.get("layers") or []) + list(index.get("skipped") or []):
        name = entry.get("layer") if isinstance(entry, dict) else None
        if isinstance(name, str) and (not layers or name in layers or name.split("__", 1)[-1] in layers):
            (out_dir / f"{name}.json").unlink(missing_ok=True)
    for entry in index.get("layers") or []:
        if entry.get("agreement") != "disagree":
            continue
        name = entry["layer"]
        if layers and name not in layers and name.split("__", 1)[1] not in layers:
            continue
        indexed_returns = entry.get("lane_returns_sha256") or {}
        changed_returns = [lane for lane in FAMILIES
                           if indexed_returns.get(lane) != current_return_sha256(work_dir / lane / f"{name}.json",
                                                                                 entry.get("lane_repo_roots") or ())]
        if changed_returns:
            # A lane was rerun after `inputs` (Codex review of #145): the judges compared other returns.
            issues.append((name, f"the {', '.join(changed_returns)} lane return changed after `inputs`; rerun "
                                 "inputs and adjudicate the current returns"))
            (out_dir / f"{name}.json").unlink(missing_ok=True)
            continue
        record, notes, leaked = assemble_layer(work_dir, entry, leaked_inputs)
        record["lane_returns_sha256"] = {lane: indexed_returns[lane] for lane in FAMILIES}
        for note in notes:
            print(f"adjudicate: {name}: {note}", file=sys.stderr)
        if leaked:
            # A dropped order leaves judgments that cannot cover both presentation orders, which
            # judge_adjudication rejects; the layer is a split and gets no record (it stays pending_lanes).
            split_layers.append({"layer": name, "leaked_inputs": leaked, "reason": record["why"]})
            issues.append((name, record["why"]))
            # An earlier record must not survive for record_verdicts --adjudications (Codex review of #145).
            (out_dir / f"{name}.json").unlink(missing_ok=True)
            continue
        provenance, provenance_issue = record.pop("_provenance"), record.pop("_provenance_issue")
        repos = record.pop("_repos")
        # The judges' prose can repeat host paths (the labelled input, packet or repository paths); the record is
        # published, so every string is scrubbed like an input and a surviving host path refuses the layer
        # (Codex review of #145).
        record["why"] = scrub_text(record["why"], str(work_dir / "packets"), repos)
        record["evidence_refs"] = sorted({scrub_text(ref, str(work_dir / "packets"), repos)
                                          for ref in record["evidence_refs"]})
        leftover = unscrubbed_paths({"why": record["why"], "evidence_refs": record["evidence_refs"]})
        if leftover and not provenance_issue:
            provenance_issue = "host paths remain in the judges' prose after scrubbing: " + ", ".join(leftover)
        issue, _result = judge_adjudication(record, grandfathered=False, packet_sha256=entry["packet_sha256"])
        issue = issue or provenance_issue
        if issue:
            issues.append((name, issue))
            (out_dir / f"{name}.json").unlink(missing_ok=True)
            continue
        # judge_adjudication and record_verdicts.load_adjudication ignore extra top-level keys.
        write_json(out_dir / f"{name}.json", {**record, "provenance": provenance})
        written.append(name)
    # A report next to the adjudication-inputs, not in --out, which record_verdicts.py --adjudications reads:
    # every leak record of both families plus the layers they split. The per-family leaks.json files are the
    # records; this report is rebuilt from them on every run.
    write_json(work_dir / f"adjudication-{LEAKS_NAME}", {
        "schema_version": 2,
        "leaks": [record for path in leak_record_paths(work_dir) for record in load_leak_records(path)],
        "split_layers": split_layers})
    return written, issues


# ---------------------------------------------------------------- cli

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Two-family counterbalanced adjudication of disagreeing layers.")
    sub = parser.add_subparsers(dest="command", required=True)
    inputs = sub.add_parser("inputs", help="Write the AB/BA input files for every disagreeing layer.")
    inputs.add_argument("--work-dir", required=True, type=Path)
    inputs.add_argument("--layers", default=None)
    inputs.add_argument("--lane-repo-root", action="append", required=True, type=Path,
                        help="Required, repeatable: a checkout a lane was given as its repository root. Host paths "
                             "under it become repository-relative in the inputs; any other host path becomes "
                             "the bare <outside-path>, and one under <work-dir>/packets/ becomes PACKET.")
    inputs.add_argument("--packet-keys", type=Path, default=None,
                        help="The lane_packets.py --keys-out file of this run (required for --withhold-labels packets).")
    codex = sub.add_parser("codex", help="Run the Codex judge and refuter for every input file.")
    codex.add_argument("--work-dir", required=True, type=Path)
    codex.add_argument("--repo", required=True, type=Path)
    codex.add_argument("--model", required=True,
                       help="Model passed to codex exec -m and recorded on each judgment; must match the openai "
                            "pattern of scripts/landscape.py FAMILY_MODEL_PATTERNS.")
    codex.add_argument("--effort", default="high")
    codex.add_argument("--jobs", type=int, default=1)
    codex.add_argument("--layers", default=None)
    codex.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    codex.add_argument("--prompt", type=Path, default=PROMPT_PATH)
    cargs = sub.add_parser("claude-args", help="Print the adjudication-lane.js args JSON.")
    cargs.add_argument("--work-dir", required=True, type=Path)
    cargs.add_argument("--repo", required=True, type=Path)
    cargs.add_argument("--layers", default=None)
    cargs.add_argument("--run-dir", required=True, type=Path, default=None,
                       help="The directory the headless adjudication session runs from (for the blind flow, the "
                            "export root); required so a project-level blind-adjudicator.md there is checked "
                            "(independent review of #145, M4), and it must also be the vendored one.")
    cargs.add_argument("--agent-file", type=Path, default=DEFAULT_ADJUDICATOR_FILE,
                       help="The blind-adjudicator definition the Claude judges will load (default: the user-level "
                            "copy; a project-level copy in the directory the workflow runs from wins over it).")
    collect = sub.add_parser("claude-collect", help="Write the Claude judgments from the workflow return.")
    collect.add_argument("--work-dir", required=True, type=Path)
    collect.add_argument("--result", required=True, type=Path)
    collect.add_argument("--model", required=True, help="The resolved child model, e.g. claude-opus-5-5.")
    collect.add_argument("--repo", default=None, type=Path, help="The repo the workflow judged (relativizes refs).")
    assemble_parser = sub.add_parser("assemble", help="Build and validate one adjudication record per layer.")
    assemble_parser.add_argument("--work-dir", required=True, type=Path)
    assemble_parser.add_argument("--out", required=True, type=Path)
    assemble_parser.add_argument("--layers", default=None)
    return parser.parse_args(argv)


def layer_set(text):
    return {item.strip() for item in text.split(",") if item.strip()} if text else None


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.command == "inputs":
        # Each root in both spellings, as given (absolutized) and resolved: a lane records the paths it opened in
        # whichever spelling it was given, and on macOS /tmp resolves to /private/tmp (validate-macos, #145).
        roots = list(dict.fromkeys(spelling for root in args.lane_repo_root
                                   for spelling in (os.path.abspath(root), str(root.resolve()))))
        refusal = refuse_roots("--lane-repo-root", roots)
        if refusal:
            print(refusal, file=sys.stderr)
            return 2
        packet_keys = json.loads(args.packet_keys.read_text(encoding="utf-8")) if args.packet_keys else None
        index = build_inputs(args.work_dir, layer_set(args.layers), roots, packet_keys)
        for skipped in index["skipped"]:
            print(f"adjudicate: skipped {skipped['layer']}: {skipped['reason']}", file=sys.stderr)
        disagree = [entry["layer"] for entry in index["layers"] if entry["agreement"] == "disagree"]
        print(f"adjudicate: {len(disagree)} disagreeing layer(s), "
              f"{len(index['layers']) - len(disagree)} agreeing, {len(index['skipped'])} skipped")
        return 1 if index["skipped"] else 0
    if args.command == "codex":
        return run_codex(args)
    if args.command == "claude-args":
        repo = args.repo.resolve()
        run_dir = (args.run_dir or repo).resolve()
        project_role = run_dir / ".claude" / "agents" / f"{ADJUDICATOR_ROLE}.md"
        # A project-level role in the directory the workflow runs from wins over --agent-file (Codex review of
        # #145), so both must be the vendored definition.
        refusal = (refuse_roots("--repo", [Path(os.path.abspath(args.repo)), repo], must_exist=True)
                   or refuse_git_repo(repo)
                   or refuse_work_dir_inside(args.work_dir, repo) or adjudicator_role_issue(args.agent_file)
                   or (adjudicator_role_issue(project_role) if project_role.exists() else None))
        if refusal:
            print(refusal, file=sys.stderr)
            return 2
        try:
            result = claude_args(args.work_dir, repo, layers=layer_set(args.layers),
                                 role_files=[args.agent_file] + ([project_role] if project_role.exists() else []))
        except ValueError as error:
            print(error, file=sys.stderr)
            return 2
        for stem in result["leaked"]:
            print(f"adjudicate: {stem}: left out, a leak is recorded for this input", file=sys.stderr)
        print(json.dumps(result, indent=1))
        return 0
    if args.command == "claude-collect":
        try:
            missing = collect_claude(args.work_dir, load_json(args.result), args.model,
                                     str(args.repo.resolve()) if args.repo else None)
        except ValueError as error:
            print(f"adjudicate: {error}", file=sys.stderr)
            return 2
        for stem, reason in missing:
            print(f"adjudicate: claude {stem}: missing ({reason})", file=sys.stderr)
        return 1 if missing else 0
    written, issues = assemble(args.work_dir, args.out, layer_set(args.layers))
    for name, issue in issues:
        print(f"adjudicate: {name}: not written: {issue}", file=sys.stderr)
    print(f"adjudicate: wrote {len(written)} adjudication record(s) to {args.out}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
