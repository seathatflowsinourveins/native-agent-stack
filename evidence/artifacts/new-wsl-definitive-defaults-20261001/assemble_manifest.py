#!/usr/bin/env python3
"""Build definitive-manifest.json: one row per slot of the new WSL architecture, across both catalogs.

It reads the two committed compact documents, settlements and convergence decisions in this folder and writes a flat table next to them. The output is
deterministic: running it again over unchanged inputs writes the same bytes.
A settlement settles a split or measurement row of the compact documents before the convergence decisions, or a split row
that those decisions add (an added slot) right after them; either way the row's resolution stays as the rounds recorded it.
The last step reads the layer-consensus record (evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json): it adds that
record's rows and records its amendments, and changes no field that the rounds decided. Each later batch of the record
(wave2, wave3, ..., in their numeric order) is folded the same way, under its own records and acknowledgements. A batch of a
direct consensus (wave 2) records the interim installs of its amendment 3: an interim is written to the row's own `interim`
field, beside the fields the rounds decided, which stay as they were. A batch on the owner's decision (wave 3, amendment 4)
adds rows of kind owner_decision and gives a row whose decided default installs nothing an owner default; the fields an owner
default replaces, and an interim it drops or amends, are kept on the row under `overturned`.

Usage: assemble_manifest.py [--check]
"""
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FOUNDATION = HERE / "foundation-definitive.compact.json"
TRADING = HERE / "trading" / "trading-definitive.compact.json"
SETTLEMENTS = HERE / "settlements.json"
CONVERGENCE = HERE / "convergence.json"
CONSENSUS = ROOT / "evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json"
OUT = HERE / "definitive-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def family_status(slot, family):
    fam = (slot.get("families") or {}).get(family)
    if fam:
        return fam.get("status", "returned")
    block = slot.get(family)
    if isinstance(block, dict):
        return block.get("status", "returned")
    return "not judged"


def rows_of(catalog, layer, slot):
    """One row per default. A slot that holds several roles, or names several tools with distinct roles, gives one row each."""
    if "roles" in slot:
        out = []
        for role in slot["roles"]:
            out.extend(rows_of(catalog, layer, dict(role, slot_id=f"{slot['slot_id']}/{role['slot_id']}")))
        return out
    default = slot.get("default")
    if isinstance(default, list):
        out = []
        for part in default:
            tail = "".join(c if c.isalnum() else "-" for c in part["name"].lower()).strip("-")[:32]
            out.extend(rows_of(catalog, layer, dict(slot, default=part, slot_id=f"{slot['slot_id']}/{tail}")))
        return out
    default = default or {}
    name = default.get("name", "")
    if "installs_nothing_extra" in default:
        nothing = bool(default["installs_nothing_extra"])
    else:
        nothing = name.lower().startswith(("no ", "not installed", "none"))
    # A slot whose single finalist the first round upheld is a first-round row, whichever catalog it is in.
    kind = "first_round" if slot["row_kind"] == "judged" and slot.get("decision_stage") == "first_round" else slot["row_kind"]
    state = ("definitive" if slot.get("definitive") else "measurement" if slot.get("decided_by_measurement_at_user_request")
             else "split" if slot.get("split") else "")
    return [{
        "catalog": catalog, "layer_id": layer["layer_id"], "slot_id": slot["slot_id"], "row_kind": kind,
        "default": name, "repository": default.get("repository", ""), "installs_nothing_extra": nothing,
        "definitive": bool(slot.get("definitive")), "label": slot.get("label") or slot.get("reason", ""),
        "state": state,
        "measurement": {"returned": False, "receipts": []} if state in ("split", "measurement") else None,
        # Whether the default coincides with what the owning lane's record already names. The trading lane states it per
        # slot; the foundation rows do not carry it yet (None), and the record names the foundation's coincidences in prose.
        "coincides_with_lane_record": (slot.get("lane_record") or {}).get("coincides"),
        "claude": family_status(slot, "claude"), "gpt": family_status(slot, "gpt"),
    }]


def verify_receipts(sid, settlement):
    if not settlement["receipts"]:
        raise ValueError(f"settlement {sid}: no receipts")
    for receipt in settlement["receipts"]:
        path = ROOT / receipt["path"]
        if not path.is_file():
            raise ValueError(f"settlement {sid}: receipt missing: {receipt['path']}")
        if sha(path) != receipt["sha256"]:
            raise ValueError(f"settlement {sid}: receipt sha256 mismatch: {receipt['path']}")


def settle(row, settlement):
    row.update({"state": "measurement", "default": settlement["default"]["name"],
                "repository": settlement["default"]["repository"], "installs_nothing_extra": False,
                "definitive": False, "label": settlement["label"],
                "measurement": {"returned": True, "receipts": settlement["receipts"]}})


def apply_settlements(rows):
    """Settle the split or measurement rows that the compact documents carry.

    A settlement whose slot has no row yet is returned unapplied: the convergence decisions add that slot (an added slot),
    and apply_added_settlements() settles it after them.
    """
    seen, deferred = set(), []
    for settlement in json.loads(SETTLEMENTS.read_text(encoding="utf-8")):
        sid = settlement["slot_id"]
        if sid in seen:
            raise ValueError(f"settlement {sid}: duplicate slot")
        seen.add(sid)
        matches = [row for row in rows if row["slot_id"] == sid]
        if not matches:
            deferred.append(settlement)
            continue
        if len(matches) != 1 or matches[0]["state"] not in ("split", "measurement"):
            raise ValueError(f"settlement {sid}: not a split or measurement row")
        verify_receipts(sid, settlement)
        settle(matches[0], settlement)
    return deferred


def apply_added_settlements(rows, deferred):
    """Settle the split rows that the convergence decisions added, once their measurement has returned.

    The row must be a split of the rounds (state and outcome split). It keeps its resolution (the outcome, the arms and the
    deciding measurement that the rounds recorded); the settlement sets the same fields as for a row of the compact
    documents. The installed job stays owned by one row.
    """
    by_slot = {row["slot_id"]: row for row in rows}
    for settlement in deferred:
        sid = settlement["slot_id"]
        row = by_slot.get(sid)
        if row is None or row.get("state") != "split" or (row.get("resolution") or {}).get("outcome") != "split":
            raise ValueError(f"settlement {sid}: not a split or measurement row")
        verify_receipts(sid, settlement)
        settle(row, settlement)
        owners = [other["slot_id"] for other in rows if other is not row and installs(other) and other.get("job") == row["job"]]
        if owners:
            raise ValueError(f"settlement {sid}: installed job also owned by {owners[0]}: {row['job']}")


def norm(url):
    # Repository matching follows convergence/combine.py and RULE.md, including the distribution's image URL.
    u = (url or "").strip().lower().rstrip("/")
    parts = urlsplit(u)
    if parts.netloc in ("github.com", "www.github.com"):
        return "/".join(parts.path.strip("/").split("/")[:2])
    return u


def installs(row):
    return bool(row["default"]) and not row["installs_nothing_extra"]


def installs_now(row):
    """Whether the row installs something on the destination: its decided default, or an interim under amendment 3."""
    return installs(row) or bool(row.get("interim"))


# A row the convergence data resolves states its current basis; the first round's text moves to resolution.first_round_record.
BASIS = {"final": "both families: the Claude record and the blind GPT samples",
         "installed_on_critic": "kept or added on a blind critic's verdict",
         "not_installed": "not installed: resolved by the rule or a blind critic",
         "split": "split: decided by the named measurement, nothing installed until it returns"}
STALE_GPT = "pending: the blind GPT-6.1 Sol run"


def gpt_status(sid, row, outcome, repos, layer):
    """The GPT family's current status on a resolved row, from its layer's entry in combined.json (RULE.md and amendment 1)."""
    samples = layer["gpt_samples_present"]
    if not samples:
        raise ValueError(f"convergence {sid}: combined.json holds no blind GPT sample for layer {row['layer_id']}")
    if outcome == "final":
        # Where amendment 1 leaves the first sample uncounted, the two Sol-ultra orders are the whole GPT side.
        if layer["g1_counted"] and samples == 3:
            return "returned: at least two of three blind GPT samples"
        if not layer["g1_counted"] and samples == 2 and layer["orders_present"] == 2:
            return "returned: both blind Sol-ultra orders"
        raise ValueError(f"convergence {sid}: combined.json holds {samples} GPT samples for layer {row['layer_id']}, not the set a final row needs")
    named = {norm(repo): count for key in ("claude_only", "gpt_only", "single_gpt_votes") for repo, count in layer[key]}
    counts = [named[repo] for repo in repos if repo in named]
    if len(counts) > 1:
        raise ValueError(f"convergence {sid}: more than one repository in combined.json: {'; '.join(repos)}")
    if counts:
        return f"returned: {counts[0]} of {samples} blind GPT samples"
    if row["row_kind"] == "added":
        return "returned: named by the critic or the added-slot round, not by the layer's blind samples"
    if repos:
        raise ValueError(f"convergence {sid}: repository not in combined.json: {'; '.join(repos)}")
    # A first-round default that installs nothing has no repository for a sample to name.
    return f"returned: 0 of {samples} blind GPT samples"


def verify_evidence(ref, sid, source="convergence"):
    if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
        raise ValueError(f"{source} {sid}: evidence path and sha256 required")
    path = ROOT / ref["path"]
    if not path.is_file():
        raise ValueError(f"{source} {sid}: evidence missing: {ref['path']}")
    if sha(path) != ref["sha256"]:
        raise ValueError(f"{source} {sid}: evidence sha256 mismatch: {ref['path']}")


def apply_convergence(rows, layers):
    data = json.loads(CONVERGENCE.read_text(encoding="utf-8"))
    for source in ("rule", "combined"):
        verify_evidence(data[source], source)
    combined = {layer["layer_id"]: layer for layer in json.loads((ROOT / data["combined"]["path"]).read_text(encoding="utf-8"))["rows"]}
    by_slot = {row["slot_id"]: row for row in rows}
    by_layer = {(layer["catalog"], layer["layer_id"]): [] for layer in layers}
    for row in rows:
        by_layer[row["catalog"], row["layer_id"]].append(row)
    added_jobs = {}
    for added in data["added_slots"]:
        sid, lid = added["slot_id"], added["layer_id"]
        if sid in by_slot:
            raise ValueError(f"convergence {sid}: duplicate added slot")
        matches = [layer for layer in layers if layer["layer_id"] == lid]
        if len(matches) != 1:
            raise ValueError(f"convergence {sid}: unknown or ambiguous layer: {lid}")
        layer = matches[0]
        row = rows_of(layer["catalog"], layer, {"slot_id": sid, "row_kind": "added", "default": added["default"]})[0]
        by_slot[sid] = row
        by_layer[layer["catalog"], lid].append(row)
        added_jobs[sid] = added.get("job")
    rows[:] = [row for layer in layers for row in by_layer[layer["catalog"], layer["layer_id"]]]
    decisions = {}
    for decision in data["decisions"] + data["added_slots"]:
        sid = decision["slot_id"]
        if sid not in by_slot:
            raise ValueError(f"convergence {sid}: decision for unknown slot")
        if sid in decisions:
            raise ValueError(f"convergence {sid}: duplicate decision")
        decisions[sid] = decision
    for sid in data["jobs"]:
        if sid not in by_slot:
            raise ValueError(f"convergence {sid}: job for unknown slot")
    measurements = {}
    for row in rows:
        sid = row["slot_id"]
        if sid not in decisions:
            raise ValueError(f"convergence {sid}: missing decision")
        job = data["jobs"].get(sid, added_jobs.get(sid))
        if not isinstance(job, str) or not job.strip():
            raise ValueError(f"convergence {sid}: missing job")
        row["job"] = job
        decision = decisions[sid]
        outcome = decision.get("outcome")
        if outcome not in ("final", "installed_on_critic", "not_installed", "split", "kept"):
            raise ValueError(f"convergence {sid}: unknown outcome: {outcome}")
        resolution = {key: decision[key] for key in ("outcome", "by", "votes", "evidence", "reason", "covered_by") if key in decision}
        row["resolution"] = resolution
        # Both are read before a branch below changes the row: the inherited status, and the repository that was judged.
        inherited = {"claude": row["claude"], "gpt": row["gpt"], "label": row["label"]}
        repos = [norm(repo) for repo in row["repository"].split(";") if norm(repo)]
        if outcome in ("installed_on_critic", "split") and "critic" not in decision:
            raise ValueError(f"convergence {sid}: critic evidence required")
        for key in ("critic", "evidence"):
            if key in decision:
                verify_evidence(decision[key], sid)
                resolution["evidence"] = decision[key]
        if outcome == "final":
            final = {norm(repo) for repo in combined.get(row["layer_id"], {}).get("final", [])}
            if not repos or any(repo not in final for repo in repos):
                raise ValueError(f"convergence {sid}: final repository not in combined.json: {row['repository']}")
            row.update({"state": "definitive", "definitive": True, "measurement": None})
        elif outcome == "installed_on_critic":
            row.update({"state": "resolved", "definitive": False, "measurement": None})
        elif outcome in ("not_installed", "split"):
            resolution["former_default"] = {"name": row["default"], "repository": row["repository"]}
            row.update({"state": "resolved" if outcome == "not_installed" else "split", "definitive": False,
                        "repository": "", "installs_nothing_extra": True})
            if not decision.get("reason"):
                raise ValueError(f"convergence {sid}: reason required")
            if outcome == "not_installed":
                row.update({"default": "Not installed: " + decision["reason"], "measurement": None})
            else:
                for key in ("arms", "deciding_measurement", "measurement_id"):
                    if not decision.get(key):
                        raise ValueError(f"convergence {sid}: split requires {key}")
                    resolution[key] = decision[key]
                mid = decision["measurement_id"]
                if mid in measurements and measurements[mid] != decision["arms"]:
                    raise ValueError(f"convergence {sid}: inconsistent arms for measurement {mid}")
                measurements[mid] = decision["arms"]
                row.update({"default": "Not installed until the deciding measurement returns",
                            "measurement": {"returned": False, "receipts": []}})
        elif not decision.get("reason"):
            raise ValueError(f"convergence {sid}: kept decision requires a reason")
        if outcome != "kept":
            layer = combined.get(row["layer_id"])
            if layer is None:
                raise ValueError(f"convergence {sid}: layer not in combined.json: {row['layer_id']}")
            added = row["row_kind"] == "added"
            # A decision may state the GPT side itself where the row has no repository for a sample to name.
            row.update({"claude": "not judged in the first round" if added else row["claude"],
                        "gpt": decision.get("gpt_status") or gpt_status(sid, row, outcome, repos, layer),
                        "label": BASIS[outcome]})
            if not added:
                resolution["first_round_record"] = inherited
        elif row["catalog"] == "us-equities" and row["gpt"].startswith(STALE_GPT):
            # The blind GPT round judged the 21 foundation packets only; a trading row never waits on it.
            resolution["first_round_record"] = inherited
            row["gpt"] = "not judged: the blind GPT round covered the 21 foundation packets only"
    for correction in data["hygiene"]:
        sid, field = correction["slot_id"], correction["field"]
        if sid not in by_slot:
            raise ValueError(f"convergence {sid}: hygiene for unknown slot")
        row = by_slot[sid]
        if field not in row:
            raise ValueError(f"convergence {sid}: unknown hygiene field: {field}")
        if field == "repository":
            if correction.get("judged_as") != row["repository"]:
                raise ValueError(f"convergence {sid}: hygiene judged_as differs from repository")
            row["resolution"]["judged_repository"] = row["repository"]
        row[field] = correction["value"]
        reason = row["resolution"].get("reason", "")
        row["resolution"]["reason"] = (reason + "; " if reason else "") + correction["reason"]
    jobs = {}
    for row in rows:
        sid = row["slot_id"]
        if installs(row):
            if row["job"] in jobs:
                raise ValueError(f"convergence {sid}: installed job also owned by {jobs[row['job']]}: {row['job']}")
            jobs[row["job"]] = sid
        if row["state"] == "split" or (row["measurement"] and not row["measurement"]["returned"]):
            if installs(row) or row["repository"] or not row["installs_nothing_extra"]:
                raise ValueError(f"convergence {sid}: pending measurement installs something")
        if row["resolution"]["outcome"] == "not_installed":
            if row["repository"] or not row["installs_nothing_extra"]:
                raise ValueError(f"convergence {sid}: not_installed row installs something")
            covered = row["resolution"].get("covered_by")
            if covered == "not needed":
                continue
            if not isinstance(covered, list) or not covered:
                raise ValueError(f"convergence {sid}: covered_by must name covering slots or not needed")
            for owner in covered:
                if owner not in by_slot:
                    raise ValueError(f"convergence {sid}: covered_by names unknown slot: {owner}")
                if not installs(by_slot[owner]):
                    raise ValueError(f"convergence {sid}: covered_by {owner} installs nothing")
    return data


# The layer-consensus record adds rows and records amendments beside what the rounds decided (its "rule").
# STATES are the states this assembler writes ("" is a row no round decided, counted as open). ROW_FIELDS are a row's
# fields in the order rows_of() and apply_convergence() write them. ROUND_OUTCOMES are the outcomes apply_convergence()
# accepts; a consensus row carries none of them. PROTECTED are the fields the rounds decided: no amendment carries one.
STATES = ("", "definitive", "resolved", "split", "measurement")
ROW_FIELDS = ("catalog", "layer_id", "slot_id", "row_kind", "default", "repository", "installs_nothing_extra", "definitive",
              "label", "state", "measurement", "coincides_with_lane_record", "claude", "gpt", "job", "resolution")
ROUND_OUTCOMES = ("final", "installed_on_critic", "not_installed", "split", "kept")
PROTECTED = ("default", "state", "definitive", "repository", "installs_nothing_extra", "row_kind")
FAMILIES = ("claude", "gpt")
# The record's wave-2 batch (2026-10-03): its own rule text (amendment 3 and its exception to the no-install rule), its hashed
# records and its acknowledgements, with the families whose acknowledgement is still owed named, never assumed.
BATCH_FIELDS = (("date_utc", str), ("meaning", str), ("interim_rule", str), ("no_install_rule_exception", str),
                ("records", dict), ("acknowledgements", list), ("acknowledgements_owed", list), ("add_rows", list),
                ("amend_rows", list), ("interim_rows", list))
# Amendment 3: an interim install, written to the row's `interim` field (outside PROTECTED), on a row whose decided default
# installs nothing. It names what it installs and at which pin, what replaces or removes it (decided_by), the authority that
# installs it meanwhile, each family's recorded review and its hashed records. The authority is the owner's dated decision
# (as the record that relays it states it, with the owner's own words where that record quotes them, and with the exact
# slot and repository pair it authorizes) or a direct consensus that carries both families' acknowledgements.
INTERIM_FIELDS = ("date_utc", "default", "repository", "pin", "label", "decided_by", "authority", "reviews", "records")
INTERIM_TEXT = ("date_utc", "default", "repository", "pin", "label", "decided_by")
INTERIM_OPTIONAL = ("configuration", "open_acceptance_gates", "sources")
AUTHORITY_KINDS = {"owner_decision": ("date_utc", "decision", "relayed_by"), "direct_consensus": ("acknowledgements",)}
# How an owner's decision names the record that relays it: one of the interim's hashed records and an entry of its
# owner_decisions list, e.g. "wave2-records.json owner_decisions[0]".
RELAYED_BY = re.compile(r"(?P<name>[A-Za-z0-9._-]+\.json) owner_decisions\[(?P<index>[0-9]+)\]")
# The affirmative actions with which a relayed decision authorizes an interim: the entry's `authorizes` lists each slot and
# repository pair its decision installs or puts to use, under the decision's own verb. Any other action authorizes nothing.
AUTHORIZING_ACTIONS = ("install", "use")
# The record's later batches are its keys wave2, wave3, ..., folded in their numeric order. A batch of a direct consensus has
# BATCH_FIELDS; a batch on the owner's decision (amendment 4, wave 3) has OWNER_BATCH_FIELDS: its own rule text, the owner's
# decision as the hashed record that relays it states it, and no acknowledgement owed, since no family consensus is its
# authority.
WAVE = re.compile(r"wave(?P<number>[2-9]|[1-9][0-9]+)")
OWNER_BATCH_FIELDS = (("date_utc", str), ("meaning", str), ("owner_rule", str), ("no_install_rule_exception", str),
                      ("authority", dict), ("records", dict), ("acknowledgements", list), ("acknowledgements_owed", list),
                      ("add_rows", list), ("amend_rows", list))
OWNER_AUTHORITY_FIELDS = ("kind", "date_utc", "decision", "verbatim", "relayed_by", "rule_basis")
# Amendment 4: a row the owner adds has this kind and outcome; a row whose decided default installs nothing and which the
# owner gives a default keeps its kind and takes OWNER_DEFAULT_OUTCOME. Neither is definitive: the state is resolved. The
# fields an owner default replaces are OVERTURNED_FIELDS, kept on the row under overturned.fields.
OWNER_ROW_KIND = "owner_decision"
OWNER_ROW_OUTCOME = "added_by_owner_decision"
OWNER_DEFAULT_OUTCOME = "owner_default"
OWNER_LABEL = "owner decision"
OWNER_DEFAULT_FIELDS = ("default", "repository", "label", "claude", "gpt", "replaces_interim", "resolution")
OVERTURNED_FIELDS = ("default", "repository", "installs_nothing_extra", "definitive", "label", "state", "measurement", "claude",
                     "gpt", "resolution")
OWNER_RESOLUTION_TEXT = ("by", "batch", "reason", "pin", "overturn")
# The interim fields an owner batch may amend, beside the ones the interim's own authority set.
INTERIM_AMENDABLE = ("default", "repository", "pin", "label", "decided_by", "open_acceptance_gates")


def relayed_decision(sid, interim, authority):
    """The owner's decision an interim's authority relays, resolved in the hashed record it names: the entry must be dated
    as the authority is, name the slot or the owner (the last part of the interim's repository) in its text, and list
    the interim's exact slot and repository in its `authorizes` under an affirmative action (AUTHORIZING_ACTIONS). So the
    record, not the batch's own text, says what the owner decided: neither a hold the owner kept nor a tool the decision
    only mentions (the browser hold's crawl4ai, to be measured first) can gain an interim this way."""
    match = RELAYED_BY.fullmatch(authority["relayed_by"].strip())
    if not match:
        raise ValueError(f"consensus {sid}: the owner's decision is relayed by '<records file> owner_decisions[<n>]', not "
                         f"{authority['relayed_by']!r}")
    refs = [ref for ref in interim["records"] if isinstance(ref, dict) and Path(str(ref.get("path"))).name == match["name"]]
    if not refs:
        raise ValueError(f"consensus {sid}: the owner's decision is relayed by {match['name']}, which is not one of the "
                         "interim's hashed records")
    decisions = json.loads((ROOT / refs[0]["path"]).read_text(encoding="utf-8")).get("owner_decisions")
    index = int(match["index"])
    if not isinstance(decisions, list) or index >= len(decisions) or not isinstance(decisions[index], dict):
        raise ValueError(f"consensus {sid}: {match['name']} has no owner_decisions[{index}]")
    entry = decisions[index]
    owner = interim["repository"].rstrip("/").rsplit("/", 1)[-1].lower()
    text = str(entry.get("decision", "")).lower()
    if not any(re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])", text) for name in (sid.lower(), owner)):
        raise ValueError(f"consensus {sid}: {match['name']} owner_decisions[{index}] names neither the slot nor {owner}")
    grants = entry.get("authorizes")
    if not (isinstance(grants, list) and any(
            isinstance(grant, dict) and grant.get("action") in AUTHORIZING_ACTIONS and grant.get("slot_id") == sid
            and isinstance(grant.get("repository"), str) and norm(grant["repository"]) == norm(interim["repository"])
            for grant in grants)):
        raise ValueError(f"consensus {sid}: {match['name']} owner_decisions[{index}] authorizes no "
                         f"{' or '.join(AUTHORIZING_ACTIONS)} of {interim['repository']} in the slot {sid}")
    if entry.get("date_utc") != authority["date_utc"]:
        raise ValueError(f"consensus {sid}: the owner's decision is dated {authority['date_utc']}, and the entry it relays "
                         f"{entry.get('date_utc')}")
    return entry


def acknowledged_families(acknowledgements):
    """The families with an acknowledgement that names its comment."""
    return {ack.get("family") for ack in acknowledgements if isinstance(ack, dict) and ack.get("url")}


def wave_batches(data):
    """[(name, batch)] of the record's later batches (wave2, wave3, ...) in their numeric order. A top-level key that starts
    with 'wave' and is not one of them is refused, so a misspelt batch is never skipped."""
    found = []
    for key in data:
        if key.startswith("wave"):
            match = WAVE.fullmatch(key)
            if not match:
                raise ValueError(f"consensus {key}: a batch is named wave<n> with n at least 2")
            found.append((int(match["number"]), key))
    return [(key, data[key]) for _, key in sorted(found)]


def is_owner_batch(batch):
    """Whether a batch rests on the owner's decision (amendment 4) rather than on a direct consensus of the families."""
    return isinstance(batch, dict) and "owner_rule" in batch


def batch_rule(batch):
    """The rule text a batch appends to the manifest's decision rule."""
    return batch["owner_rule"] if is_owner_batch(batch) else batch["interim_rule"]


def https_parts(value):
    """The URLs of a repository field, which may name several repositories separated by '; ', or None if one is not https."""
    parts = [part.strip() for part in str(value or "").split(";")]
    return parts if parts and all(part.startswith("https://") and " " not in part for part in parts) else None


def check_records_and_acknowledgements(name, batch):
    if not batch["records"]:
        raise ValueError(f"consensus {name}: the batch names its hashed records")
    for record in sorted(batch["records"]):
        verify_evidence(batch["records"][record], f"{name}.records.{record}", "consensus")
    for ack in batch["acknowledgements"]:
        if not (isinstance(ack, dict) and ack.get("family") in FAMILIES and str(ack.get("url", "")).startswith("https://github.com/")
                and all(isinstance(ack.get(key), str) and ack[key].strip() for key in ("at", "covers"))):
            raise ValueError(f"consensus {name}: an acknowledgement is one family's pull-request comment, with its time and what it covers")


def check_batch(batch, name="wave2"):
    """A consensus batch's shape, records and acknowledgements. An acknowledgement is a pull-request comment of one family; a
    family without one is named in acknowledgements_owed, so the record never claims an acknowledgement it does not hold."""
    if not isinstance(batch, dict) or set(batch) != {key for key, _ in BATCH_FIELDS} or not all(
            isinstance(batch[key], kind) for key, kind in BATCH_FIELDS):
        raise ValueError(f"consensus {name}: the batch needs exactly " + ", ".join(key for key, _ in BATCH_FIELDS))
    if not all(batch[key].strip() for key, kind in BATCH_FIELDS if kind is str):
        raise ValueError(f"consensus {name}: the batch's date, meaning and rule texts are not blank")
    check_records_and_acknowledgements(name, batch)
    owed = sorted(set(FAMILIES) - acknowledged_families(batch["acknowledgements"]))
    if batch["acknowledgements_owed"] != owed:
        raise ValueError(f"consensus {name}: acknowledgements_owed must name exactly the families without an acknowledgement: {owed}")


def changed_slots(batch):
    """The slots an owner batch adds or amends, in the batch's order."""
    return ([row.get("slot_id") for row in batch["add_rows"] if isinstance(row, dict)]
            + [entry.get("slot_id") for entry in batch["amend_rows"] if isinstance(entry, dict)])


def batch_repositories(batch):
    """Every repository an owner batch's rows and amendments name."""
    named = [row.get("repository") for row in batch["add_rows"] if isinstance(row, dict)]
    for entry in batch["amend_rows"]:
        if isinstance(entry, dict):
            for key in ("owner_default", "interim"):
                if isinstance(entry.get(key), dict) and "repository" in entry[key]:
                    named.append(entry[key]["repository"])
    return [part for value in named for part in (https_parts(value) or [str(value)])]


def check_owner_batch(name, batch):
    """An owner batch (amendment 4): its shape, records and acknowledgements, and the owner's decision it rests on. The decision
    is the one the hashed record named by authority.relayed_by states: that record quotes the owner's words verbatim and names
    every slot the batch adds or amends (as `slot`) and every repository they install, so the record, not the batch's own
    text, says what the owner decided. No acknowledgement is owed, since no family consensus is the batch's authority."""
    if not isinstance(batch, dict) or set(batch) != {key for key, _ in OWNER_BATCH_FIELDS} or not all(
            isinstance(batch[key], kind) for key, kind in OWNER_BATCH_FIELDS):
        raise ValueError(f"consensus {name}: an owner batch needs exactly " + ", ".join(key for key, _ in OWNER_BATCH_FIELDS))
    if not all(batch[key].strip() for key, kind in OWNER_BATCH_FIELDS if kind is str):
        raise ValueError(f"consensus {name}: the batch's date, meaning and rule texts are not blank")
    check_records_and_acknowledgements(name, batch)
    if batch["acknowledgements_owed"] != []:
        raise ValueError(f"consensus {name}: an owner batch owes no acknowledgement; its authority is the owner's decision")
    authority = batch["authority"]
    if set(authority) != set(OWNER_AUTHORITY_FIELDS) or not all(
            isinstance(authority[key], str) and authority[key].strip() for key in OWNER_AUTHORITY_FIELDS):
        raise ValueError(f"consensus {name}: the owner's decision needs exactly " + ", ".join(OWNER_AUTHORITY_FIELDS))
    if authority["kind"] != "owner_decision":
        raise ValueError(f"consensus {name}: an owner batch's authority is an owner_decision, not {authority['kind']}")
    if authority["date_utc"] != batch["date_utc"]:
        raise ValueError(f"consensus {name}: the owner's decision is dated {authority['date_utc']}, and the batch {batch['date_utc']}")
    refs = [ref for ref in batch["records"].values() if isinstance(ref, dict) and ref.get("path") == authority["relayed_by"]]
    if not refs:
        raise ValueError(f"consensus {name}: the owner's decision is relayed by {authority['relayed_by']}, which is not one of "
                         "the batch's hashed records")
    text = (ROOT / refs[0]["path"]).read_text(encoding="utf-8")
    if authority["verbatim"] not in text:
        raise ValueError(f"consensus {name}: {authority['relayed_by']} does not quote the owner's words verbatim")
    for sid in changed_slots(batch):
        if not isinstance(sid, str) or f"`{sid}`" not in text:
            raise ValueError(f"consensus {name}: {authority['relayed_by']} does not name the slot {sid}")
    for repository in batch_repositories(batch):
        if repository not in text:
            raise ValueError(f"consensus {name}: {authority['relayed_by']} does not name the repository {repository}")


def owner_resolution(sid, resolution, outcome, name):
    """The resolution an owner row or owner default carries: its outcome, the owner's decision, the batch, why, the pin, the
    comparison that would remove it, and its sources."""
    if not isinstance(resolution, dict) or resolution.get("outcome") != outcome:
        raise ValueError(f"consensus {sid}: an owner {'row' if outcome == OWNER_ROW_OUTCOME else 'default'} has the outcome {outcome}")
    blank = [key for key in OWNER_RESOLUTION_TEXT if not (isinstance(resolution.get(key), str) and resolution[key].strip())]
    if blank:
        raise ValueError(f"consensus {sid}: an owner decision's resolution needs a non-empty {', '.join(blank)}")
    if resolution["batch"] != name:
        raise ValueError(f"consensus {sid}: the resolution names the batch {resolution['batch']}, not {name}")
    if not (isinstance(resolution.get("sources"), list) and resolution["sources"]):
        raise ValueError(f"consensus {sid}: an owner decision names its sources")


def apply_owner_amendments(rows, by_slot, name, batch):
    """Amendment 4 on rows the rounds or an earlier batch decided: an owner default on a row whose decided default installs
    nothing (it may drop the row's interim), or an amendment of a row's interim. The replaced values are kept on the row under
    overturned, with the amendment that replaced them."""
    for entry in batch["amend_rows"]:
        entry = entry if isinstance(entry, dict) else {}
        sid = entry.get("slot_id")
        if not isinstance(sid, str) or sid not in by_slot:
            raise ValueError(f"consensus {sid}: amendment for unknown slot")
        changes = [key for key in ("owner_default", "interim") if key in entry]
        if set(entry) - {"slot_id", "amendment", "owner_default", "interim"} or len(changes) != 1:
            raise ValueError(f"consensus {sid}: an owner amendment is its slot_id, its amendment and one owner_default or interim")
        amendment = entry.get("amendment")
        if not isinstance(amendment, dict) or not all(
                isinstance(amendment.get(key), str) and amendment[key].strip() for key in ("date_utc", "by", "decision")):
            raise ValueError(f"consensus {sid}: an amendment needs date_utc, by and decision")
        if amendment["date_utc"] != batch["date_utc"]:
            raise ValueError(f"consensus {sid}: the amendment is dated {amendment['date_utc']}, and its batch {batch['date_utc']}")
        replaced = sorted((set(amendment) & set(PROTECTED)) | ({"interim"} & set(amendment)))
        if replaced:
            raise ValueError(f"consensus {sid}: an amendment's own text cannot carry {', '.join(replaced)}")
        row = by_slot[sid]
        if "overturned" in row:
            raise ValueError(f"consensus {sid}: the row already carries an owner amendment")
        overturned = {"amendment": json.loads(json.dumps(amendment))}
        if changes == ["owner_default"]:
            default = entry["owner_default"]
            if not isinstance(default, dict) or set(default) != set(OWNER_DEFAULT_FIELDS):
                raise ValueError(f"consensus {sid}: an owner default carries exactly " + ", ".join(OWNER_DEFAULT_FIELDS))
            if installs(row):
                raise ValueError(f"consensus {sid}: an owner default replaces only a decided default that installs nothing")
            if default["replaces_interim"] is not bool(row.get("interim")):
                raise ValueError(f"consensus {sid}: replaces_interim must say whether the row carries an interim")
            blank = [key for key in ("default", "label", "claude", "gpt")
                     if not (isinstance(default[key], str) and default[key].strip())]
            if blank:
                raise ValueError(f"consensus {sid}: an owner default needs a non-empty {', '.join(blank)}")
            if https_parts(default["repository"]) is None:
                raise ValueError(f"consensus {sid}: an owner default names its repository by an https URL")
            if not default["label"].startswith(OWNER_LABEL):
                raise ValueError(f"consensus {sid}: an owner default's label starts with '{OWNER_LABEL}'")
            owner_resolution(sid, default["resolution"], OWNER_DEFAULT_OUTCOME, name)
            overturned["fields"] = {key: json.loads(json.dumps(row[key])) for key in OVERTURNED_FIELDS}
            if row.get("interim"):
                overturned["interim"] = row.pop("interim")
            row.update({"default": default["default"], "repository": default["repository"], "installs_nothing_extra": False,
                        "definitive": False, "label": default["label"], "state": "resolved", "measurement": None,
                        "claude": default["claude"], "gpt": default["gpt"],
                        "resolution": json.loads(json.dumps(default["resolution"]))})
        else:
            change = entry["interim"]
            if not isinstance(row.get("interim"), dict):
                raise ValueError(f"consensus {sid}: an interim amendment needs a row that carries an interim")
            if not isinstance(change, dict) or not change or set(change) - set(INTERIM_AMENDABLE):
                raise ValueError(f"consensus {sid}: an interim amendment changes only " + ", ".join(INTERIM_AMENDABLE))
            for key, value in change.items():
                ok = (isinstance(value, list) and value and all(isinstance(item, str) and item.strip() for item in value)
                      if key == "open_acceptance_gates" else isinstance(value, str) and value.strip())
                if not ok:
                    raise ValueError(f"consensus {sid}: an interim amendment needs a non-empty {key}")
            if "repository" in change and https_parts(change["repository"]) is None:
                raise ValueError(f"consensus {sid}: an interim names its repository by an https URL")
            if "label" in change and not change["label"].startswith("interim install"):
                raise ValueError(f"consensus {sid}: an interim's label starts with 'interim install'")
            overturned["interim"] = {key: json.loads(json.dumps(row["interim"].get(key))) for key in change}
            row["interim"].update(json.loads(json.dumps(change)))
        owners = [other["slot_id"] for other in rows if other is not row and other["job"] == row["job"] and installs_now(other)]
        if owners:
            raise ValueError(f"consensus {sid}: installed job also owned by {owners[0]}: {row['job']}")
        row["overturned"] = overturned


def apply_interims(rows, by_slot, entries):
    """Record the interim installs of amendment 3 on their rows; no field that the rounds decided changes."""
    for entry in entries:
        entry = entry if isinstance(entry, dict) else {}
        sid, interim = entry.get("slot_id"), entry.get("interim")
        if not isinstance(sid, str) or sid not in by_slot:
            raise ValueError(f"consensus {sid}: interim for unknown slot")
        if set(entry) != {"slot_id", "interim"} or not isinstance(interim, dict):
            raise ValueError(f"consensus {sid}: an interim entry is its slot_id and its interim")
        row = by_slot[sid]
        if installs(row):
            raise ValueError(f"consensus {sid}: an interim installs only on a row whose decided default installs nothing")
        if "interim" in row:
            raise ValueError(f"consensus {sid}: duplicate interim")
        missing = sorted(set(INTERIM_FIELDS) - set(interim))
        unknown = sorted(set(interim) - set(INTERIM_FIELDS) - set(INTERIM_OPTIONAL))
        if missing or unknown:
            raise ValueError(f"consensus {sid}: an interim carries its fields: missing {missing}; unknown {unknown}")
        blank = [key for key in INTERIM_TEXT if not (isinstance(interim[key], str) and interim[key].strip())]
        if blank:
            raise ValueError(f"consensus {sid}: an interim needs a non-empty {', '.join(blank)}")
        if not interim["repository"].startswith("https://"):
            raise ValueError(f"consensus {sid}: an interim names its repository by an https URL")
        authority = interim["authority"] if isinstance(interim["authority"], dict) else {}
        kind = authority.get("kind")
        if kind not in AUTHORITY_KINDS:
            raise ValueError(f"consensus {sid}: an interim's authority is one of {', '.join(AUTHORITY_KINDS)}, not {kind}")
        if kind == "owner_decision":
            blank = [key for key in AUTHORITY_KINDS[kind] if not (isinstance(authority.get(key), str) and authority[key].strip())]
            if blank:
                raise ValueError(f"consensus {sid}: the owner's decision needs its {', '.join(blank)}")
        elif not set(FAMILIES) <= acknowledged_families(authority.get("acknowledgements")
                                                         if isinstance(authority.get("acknowledgements"), list) else []):
            raise ValueError(f"consensus {sid}: a direct consensus needs an acknowledgement of each family")
        reviews = interim["reviews"]
        if not isinstance(reviews, dict) or not all(isinstance(reviews.get(family), str) and reviews[family].strip()
                                                     for family in FAMILIES):
            raise ValueError(f"consensus {sid}: an interim records each family's review")
        if not isinstance(interim["records"], list) or not interim["records"]:
            raise ValueError(f"consensus {sid}: an interim names its hashed records")
        for ref in interim["records"]:
            verify_evidence(ref, f"{sid} interim", "consensus")
        if kind == "owner_decision":
            relayed_decision(sid, interim, authority)
        owners = [other["slot_id"] for other in rows if other is not row and other["job"] == row["job"] and installs_now(other)]
        if owners:
            raise ValueError(f"consensus {sid}: installed job also owned by {owners[0]}: {row['job']}")
        row["interim"] = json.loads(json.dumps(interim))


def apply_consensus(rows, layers):
    """Add the consensus record's rows and record its amendments; no field that the rounds decided changes.

    An added row is copied as the record gives it and placed after the last row of its layer. An amendment becomes an
    item of its row's amendments list. The exchanged notes that the record names are hashed as verify_evidence does it;
    the acknowledgements are links to pull-request comments and are checked for presence only. Each later batch, in its
    numeric order, adds its rows after the earlier ones; a consensus batch then records its amendments and its interim
    installs (apply_interims), and an owner batch, last, its owner amendments (apply_owner_amendments).
    """
    data = json.loads(CONSENSUS.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(data.get(key), kind) for key, kind in
                                             (("rule", str), ("records", dict), ("add_rows", list), ("amend_rows", list))):
        raise ValueError("consensus: the record needs its rule, records, add_rows and amend_rows")
    records = data["records"]
    notes = sorted(set(records) - {"acknowledgements"})
    for name in notes:
        verify_evidence(records[name], f"records.{name}", "consensus")
    acknowledgements = records.get("acknowledgements") if isinstance(records.get("acknowledgements"), list) else []
    if not notes or not set(FAMILIES) <= acknowledged_families(acknowledgements):
        raise ValueError("consensus records: the exchanged notes and an acknowledgement of each family are required")
    batches = wave_batches(data)
    for name, batch in batches:
        if is_owner_batch(batch):
            check_owner_batch(name, batch)
        else:
            check_batch(batch, name)
    by_slot = {row["slot_id"]: row for row in rows}
    by_layer = {(layer["catalog"], layer["layer_id"]): [] for layer in layers}
    for row in rows:
        by_layer[row["catalog"], row["layer_id"]].append(row)
    catalogs = sorted({layer["catalog"] for layer in layers})
    jobs = {row["job"]: row["slot_id"] for row in rows if installs(row)}

    def add(entries, owner_batch=None):
        """Add a batch's rows: consensus rows, or, with owner_batch (the batch's name), the owner's rows of amendment 4."""
        kind = "consensus" if owner_batch is None else OWNER_ROW_KIND
        for added in entries:
            added = added if isinstance(added, dict) else {}
            sid = added.get("slot_id")
            missing, unknown = sorted(set(ROW_FIELDS) - set(added)), sorted(set(added) - set(ROW_FIELDS))
            if missing or unknown or not isinstance(sid, str) or not sid.strip():
                raise ValueError(f"consensus {sid}: an added row carries the manifest's row fields: missing {missing}; unknown {unknown}")
            if sid in by_slot:
                raise ValueError(f"consensus {sid}: slot already exists")
            if added["row_kind"] != kind:
                raise ValueError(f"consensus {sid}: an added row must have row_kind {kind}, not {added['row_kind']}")
            if added["definitive"] is not False or added["state"] == "definitive":
                raise ValueError(f"consensus {sid}: a{'n owner' if owner_batch else ' consensus'} row is never definitive")
            if owner_batch is not None:
                # An owner row installs what it names, now: resolved, no pending measurement, a label that says what it is.
                if added["state"] != "resolved" or added["measurement"] is not None or not installs(added):
                    raise ValueError(f"consensus {sid}: an owner row is resolved, waits for no measurement and installs its default")
                if https_parts(added["repository"]) is None:
                    raise ValueError(f"consensus {sid}: an owner row names its repository by an https URL")
                if not str(added["label"]).startswith(OWNER_LABEL):
                    raise ValueError(f"consensus {sid}: an owner row's label starts with '{OWNER_LABEL}'")
                owner_resolution(sid, added["resolution"], OWNER_ROW_OUTCOME, owner_batch)
            if added["state"] not in STATES:
                raise ValueError(f"consensus {sid}: unknown state: {added['state']}")
            if added["catalog"] not in catalogs:
                raise ValueError(f"consensus {sid}: unknown catalog: {added['catalog']}")
            if (added["catalog"], added["layer_id"]) not in list(by_layer):
                raise ValueError(f"consensus {sid}: unknown layer: {added['layer_id']}")
            job, resolution = added["job"], added["resolution"]
            if (not isinstance(job, str) or not job.strip() or not isinstance(resolution, dict)
                    or not isinstance(resolution.get("outcome"), str) or resolution["outcome"] in ("",) + ROUND_OUTCOMES):
                raise ValueError(f"consensus {sid}: an added row needs a job and an outcome that no round uses")
            waiting = added["state"] in ("split", "measurement")
            if added["measurement"] != ({"returned": False, "receipts": []} if waiting else None):
                raise ValueError(f"consensus {sid}: state and measurement disagree")
            if waiting and (installs(added) or added["repository"] or not added["installs_nothing_extra"]):
                raise ValueError(f"consensus {sid}: pending measurement installs something")
            if installs(added):
                if job in jobs:
                    raise ValueError(f"consensus {sid}: installed job also owned by {jobs[job]}: {job}")
                jobs[job] = sid
            row = json.loads(json.dumps(added))
            by_slot[sid] = row
            by_layer[row["catalog"], row["layer_id"]].append(row)

    def amend(entries):
        for entry in entries:
            entry = entry if isinstance(entry, dict) else {}
            sid, amendment = entry.get("slot_id"), entry.get("amendment")
            if not isinstance(sid, str) or sid not in by_slot:
                raise ValueError(f"consensus {sid}: amendment for unknown slot")
            if not isinstance(amendment, dict) or not all(
                    isinstance(amendment.get(key), str) and amendment[key].strip() for key in ("date_utc", "by", "decision")):
                raise ValueError(f"consensus {sid}: an amendment needs date_utc, by and decision")
            replaced = sorted((set(entry) | set(amendment)) & set(PROTECTED))
            if replaced:
                raise ValueError(f"consensus {sid}: an amendment cannot replace {', '.join(replaced)}")
            if "interim" in entry or "interim" in amendment:
                raise ValueError(f"consensus {sid}: an interim install is recorded under interim_rows, not as an amendment")
            by_slot[sid].setdefault("amendments", []).append(json.loads(json.dumps(amendment)))

    add(data["add_rows"])
    for name, batch in batches:
        add(batch["add_rows"], name if is_owner_batch(batch) else None)
    rows[:] = [row for layer in layers for row in by_layer[layer["catalog"], layer["layer_id"]]]
    amend(data["amend_rows"])
    for name, batch in batches:
        if not is_owner_batch(batch):
            amend(batch["amend_rows"])
            apply_interims(rows, by_slot, batch["interim_rows"])
    # Owner amendments come last: an owner default may drop an interim, and an interim amendment changes one.
    for name, batch in batches:
        if is_owner_batch(batch):
            apply_owner_amendments(rows, by_slot, name, batch)
    return data


def assemble_rows():
    """The rows as the rounds decided them: both catalogs, the settlements and the convergence decisions, before the consensus step."""
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    trading = json.loads(TRADING.read_text(encoding="utf-8"))
    rows = []
    for layer in foundation["layers"] + foundation["cross_rows"]:
        for slot in layer["slots"]:
            rows.extend(rows_of("foundation", layer, slot))
    for layer in trading["layers"]:
        for pin in trading.get("pinned_requirements", []):
            if pin["owner"] == layer["layer_id"]:
                rows.append({"catalog": "us-equities", "layer_id": layer["layer_id"],
                             "slot_id": "pinned/" + "".join(c if c.isalnum() else "-" for c in pin["name"].lower()).strip("-")[:40],
                             "row_kind": "pinned", "default": pin["name"], "repository": "", "installs_nothing_extra": False,
                             "definitive": False, "label": "a requirement the user selected; carried with its committed receipts, never judged",
                             "state": "", "measurement": None,
                             "claude": "not judged", "gpt": "not judged"})
        for slot in layer.get("slots", []):
            rows.extend(rows_of("us-equities", layer, slot))
    deferred = apply_settlements(rows)
    layers = [{"catalog": "foundation", "layer_id": l["layer_id"], "owns": l["owns"], "uses": l["uses"]}
              for l in foundation["layers"] + foundation["cross_rows"]]
    layers += [{"catalog": "us-equities", "layer_id": l["layer_id"], "owns": l["owns"], "uses": l["uses"]} for l in trading["layers"]]
    convergence = apply_convergence(rows, layers)
    apply_added_settlements(rows, deferred)
    return foundation, trading, rows, layers, convergence


def build():
    foundation, trading, rows, layers, convergence = assemble_rows()
    consensus = apply_consensus(rows, layers)
    by_kind, by_state = {}, {}
    for r in rows:
        by_kind[r["row_kind"]] = by_kind.get(r["row_kind"], 0) + 1
        state = r.get("state") or "open"
        by_state[state] = by_state.get(state, 0) + 1
    batches = wave_batches(consensus)
    # Each batch's rule (amendment 3, amendment 4, ...) is appended to the rule after the consensus record's rule, in the
    # batches' order, and their exceptions are stated, joined in the same order, beside the no-install rule; each batch's
    # acknowledgements, and the families whose acknowledgement is owed, are carried as recorded, with an owner batch's authority.
    amendments = {} if not batches else {
        "no_install_rule_exception": " ".join(batch["no_install_rule_exception"] for _, batch in batches),
        **{f"consensus_{name}": {"date_utc": batch["date_utc"], "meaning": batch["meaning"],
                                 **({"authority": {key: batch["authority"][key] for key in ("kind", "date_utc", "relayed_by")}}
                                    if is_owner_batch(batch) else {}),
                                 "acknowledgements": batch["acknowledgements"],
                                 "acknowledgements_owed": batch["acknowledgements_owed"]} for name, batch in batches}}
    doc = {
        "schema_version": 1, "kind": "new-wsl-definitive-manifest", "date_utc": "2026-10-01",
        "meaning": "one default per slot for the clean install of the new WSL distribution; a definitive default is the slot's install decision, "
                   "agreed by both model families, and is not a merit acceptance",
        "decision_rule": "A foundation first-round default is definitive when it is in the Claude record and in enough blind GPT samples "
                         f"under the combination rule ({convergence['rule']['path']} and its amendment 1); a contested one is resolved by a blind "
                         "Claude critic or split to a named measurement. A decision-round default is definitive when both deciders of both families "
                         "name it and both critics return converged, and a split is settled by the measurement the critics name."
                         + " " + consensus["rule"] + "".join(" " + batch_rule(batch) for _, batch in batches),
        "decision_rule_before_amendment_2": foundation["decision_rule"],
        "no_install_rule": foundation["no_install_rule"],
        **amendments,
        "not_claimed": foundation["not_claimed"],
        "sources": {"foundation": {"file": FOUNDATION.name, "sha256": sha(FOUNDATION)},
                    "us-equities": {"file": "trading/" + TRADING.name, "sha256": sha(TRADING), "owner": trading["owner"]},
                    "settlements": {"file": SETTLEMENTS.name, "sha256": sha(SETTLEMENTS)},
                    "convergence": {"file": CONVERGENCE.name, "sha256": sha(CONVERGENCE)},
                    "rule": convergence["rule"], "combined": convergence["combined"],
                    "consensus": {"path": CONSENSUS.relative_to(ROOT).as_posix(), "sha256": sha(CONSENSUS)}},
        "counts": {"layers": len(layers), "slots": len(rows), "definitive": sum(1 for r in rows if r["definitive"]), "by_row_kind": by_kind,
                   "by_state": by_state, "installed": sum(1 for r in rows if installs(r)),
                   **({} if not batches else {"interim": sum(1 for r in rows if r.get("interim"))})},
        "pinned_requirements": {"us-equities": trading.get("pinned_requirements", [])},
        "no_blind_default_today": {"us-equities": trading.get("no_blind_default_today", [])},
        "layers": layers, "slots": rows,
    }
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


if __name__ == "__main__":
    try:
        text = build()
    except ValueError as error:
        print(error)
        sys.exit(1)
    if "--check" in sys.argv[1:]:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("definitive-manifest.json is stale: run assemble_manifest.py")
            sys.exit(1)
        print("definitive-manifest.json is current")
    else:
        OUT.write_text(text, encoding="utf-8")
        doc = json.loads(text)
        counts, by_catalog = doc["counts"], {}
        for row in doc["slots"]:
            by_catalog[row["catalog"]] = by_catalog.get(row["catalog"], 0) + 1
        amended = [row for row in doc["slots"] if row.get("amendments")]
        print("layers", counts["layers"], "| slots", counts["slots"], by_catalog, "| definitive", counts["definitive"],
              "| installed", counts["installed"], "| interim", counts.get("interim", 0), "|", counts["by_row_kind"], "|",
              counts["by_state"], "| amendments", sum(len(row["amendments"]) for row in amended), "on", len(amended), "rows",
              "| overturned", sum(1 for row in doc["slots"] if row.get("overturned")))
