"""Append-only files outside the study tree: the run log, the access log (core.gate) and the calendar and fee
amendment files (run_discipline.data_files, run_log).

Review round 8, R8-2: every run-log line and every results file carries protocol_sha256.
Review round 8, R8-10: an amendment line must reach origin/main (the GitHub-recorded time) before 09:30 ET of the
session it concerns (a calendar line), or before the first holdout count or read that used its dates (a fee line).
Review round 9, M-3 and F5: core.runner.context applies both checks before every run. A line's reach time is the
committer time of the first first-parent commit of origin/main whose version of the file holds it (line_reach); the
repository squash-merges, and GitHub sets and signs a squash commit's committer time when it merges the pull request.
Review round 10, M3: line_reach refuses a commit whose signature does not verify against the pinned web-flow key, so
a client-set (backdated) committer time never counts. F2: every amendment line also needs an 'amend' access-log
record that reached origin/main before the line's deadline (check_amend_logged).
"""
from __future__ import annotations

import json
from pathlib import Path

from core.canon import dumps, sha256_bytes
from core.calendar import parse_utc

RUN_LOG_FIELDS = ("utc_start", "utc_end", "stage", "purpose", "commit", "study_tree", "runtime_lock_sha256",
                  "protocol_sha256", "data_file_sha256s", "amendment_files", "input_snapshot_sha256s", "status",
                  "results_sha256")


class AppendOnlyViolation(Exception):
    pass


def append_line(path, obj) -> None:
    p = Path(path)
    with p.open("a", encoding="utf-8") as f:
        f.write(dumps(obj) + "\n")


def read_lines(path) -> list:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def file_state(path) -> dict:
    data = Path(path).read_bytes() if Path(path).exists() else b""
    return {"sha256": sha256_bytes(data), "bytes": len(data)}


def is_prefix_extension(current: bytes, logged: dict) -> bool:
    """The content logged at an earlier run (sha256 and byte length) is a byte prefix of the current content."""
    return len(current) >= logged["bytes"] and sha256_bytes(current[: logged["bytes"]]) == logged["sha256"]


def check_amendment_files(paths: dict, run_log: list) -> list:
    """Refusals for any amendment file whose content at an earlier logged run is not a prefix of today's."""
    refusals = []
    for name, path in paths.items():
        current = Path(path).read_bytes() if Path(path).exists() else b""
        for line in run_log:
            logged = (line.get("amendment_files") or {}).get(name)
            if logged and not is_prefix_extension(current, logged):
                refusals.append(f"{name}: edited, not appended, since the run at {line.get('utc_start')}")
                break
    return refusals


def check_run_log_line(line: dict) -> list:
    return [f"run-log line lacks {f}" for f in RUN_LOG_FIELDS if f not in line]


def check_calendar_amendments(lines: list, reach_times: dict, cal, freeze_session: str) -> list:
    """lines: calendar amendment records; reach_times: {line index: epoch seconds the line first became reachable
    from origin/main, as GitHub records it}. A line must concern a session on or after the freeze session and
    reach main before 09:30 ET of that session."""
    refusals = []
    for i, rec in enumerate(lines):
        s = rec.get("session")
        if not s or s < freeze_session:
            refusals.append(f"calendar amendment {i}: concerns {s}, before the freeze session")
            continue
        if not rec.get("source"):
            refusals.append(f"calendar amendment {i}: no primary source")
        t = reach_times.get(i)
        if t is None or t >= cal.at(s, "09:30"):
            refusals.append(f"calendar amendment {i}: not on origin/main before 09:30 ET of {s}")
    return refusals


def check_fee_amendments(lines: list, reach_times: dict, first_use: dict, freeze_session: str) -> list:
    """first_use: {line index: epoch seconds of the first holdout count or read that used a date the line
    covers}. A fee line concerns dates on or after the freeze session and must reach main before that use."""
    refusals = []
    for i, rec in enumerate(lines):
        if rec.get("from", "") < freeze_session:
            refusals.append(f"fee amendment {i}: starts {rec.get('from')}, before the freeze session")
        if rec.get("kind") == "finra_taf" and rec.get("max_per_trade") is None:
            refusals.append(f"fee amendment {i}: a TAF line must carry max_per_trade")
        use, t = first_use.get(i), reach_times.get(i)
        if use is not None and (t is None or t >= use):
            refusals.append(f"fee amendment {i}: reached main after the first count or read that used its dates")
    return refusals


def results_lines(run_log: list, stage: str, purpose: str = "evaluate") -> list:
    return [x for x in run_log if x.get("stage") == stage and x.get("purpose") == purpose and x.get("results_sha256")]


def governing_results(run_log: list, stage: str, purpose: str = "evaluate"):
    """The first run of a stage that wrote its results file governs; a second results file is refused."""
    lines = results_lines(run_log, stage, purpose)
    if len(lines) > 1:
        raise AppendOnlyViolation(f"{stage}: {len(lines)} results files; a stage has one governing results file")
    return lines[0] if lines else None


def results_attempts(run_log: list, stage: str, purpose: str = "evaluate") -> list:
    return [x for x in run_log if x.get("stage") == stage and x.get("purpose") == purpose]


def line_reach(repo, path: str, ref: str = "origin/main") -> list:
    """[(commit, committer epoch)] per line of the append-only file at ref: the first first-parent commit of ref
    whose version of the file holds that line. Each such commit must be a merge commit signed by the pinned merge
    key, so the epoch is GitHub's recorded time (review round 10, M3)."""
    from core.guards import committed_bytes, git, require_verified
    rows = git(repo, "log", "--first-parent", "--reverse", "--format=%H %ct", ref, "--", path).splitlines()
    out = []
    for row in rows:
        commit, ct = row.split()
        data = committed_bytes(repo, commit, path) or b""
        n = len([x for x in data.decode("utf-8").splitlines() if x.strip()])
        if len(out) < n:
            require_verified(repo, commit, f"a line of {path}")
        while len(out) < n:
            out.append((commit, int(ct)))
    return out


def line_reach_of(repo, path: str, index: int, ref: str = "origin/main"):
    """The committer epoch at which line `index` of the file first reached origin/main, or None."""
    reach = line_reach(repo, path, ref)
    return reach[index][1] if 0 <= index < len(reach) else None


def fee_first_use(lines: list, run_log: list) -> dict:
    """{line index: epoch of the first holdout count or read (run-log utc_start) whose sessions overlap the line's
    from .. to}. A read's sessions are its fee_span when its line records one: its trades exit, and pay sale fees,
    through the end of the last terminal-search window, 5 sessions after the window's last session (review round 13,
    Codex P2), so a fee line for those dates has a first-use deadline too."""
    out = {}
    for i, rec in enumerate(lines):
        for x in run_log:
            span = x.get("fee_span") or x.get("sessions")
            if x.get("purpose") not in ("count", "read") or not span:
                continue
            if span[0] <= rec.get("to", "") and rec.get("from", "") <= span[1]:
                t = parse_utc(x["utc_start"])
                out[i] = min(out.get(i, t), t)
    return out


# ---------------------------------------------------------------- 'amend' records (review round 10, F2)

def raw_lines(path) -> list:
    """The non-empty lines of an append-only JSON-lines file, as bytes (the unit an 'amend' record cites)."""
    p = Path(path)
    if not p.exists():
        return []
    return [x for x in p.read_bytes().splitlines() if x.strip()]


def amend_records(access_log: list) -> dict:
    """{(amendment file name, line index): (access-log index, amendment)} for every complete completion of a granted
    'amend' authorization (the first one per line)."""
    granted = {r.get("authorization_id") for r in access_log if r.get("record_kind") == "authorization"
               and r.get("decision") == "granted" and r.get("purpose") == "amend"}
    out = {}
    for i, r in enumerate(access_log):
        a = r.get("amendment")
        if r.get("record_kind") != "completion" or r.get("authorization_id") not in granted or \
                r.get("status") != "complete" or not isinstance(a, dict):
            continue
        out.setdefault((a.get("file"), a.get("line")), (i, a))
    return out


def check_amend_logged(name: str, lines: list, raws: list, records: dict, access_reach: dict, deadlines: dict,
                       pending_ok: bool = False) -> list:
    """Every amendment line is logged in the access log under purpose 'amend' (session_calendar, cost_model.fees):
    a completion that cites the file, the line index, the line's sha256 and its primary source, and whose record
    reached origin/main before the line's deadline (deadlines: {line index: epoch or None}). pending_ok lets the
    'amend' path itself run while a line awaits its record."""
    refusals = []
    for i, rec in enumerate(lines):
        got = records.get((name, i))
        if got is None:
            if not pending_ok:
                refusals.append(f"{name} line {i}: not logged in the access log under purpose 'amend'")
            continue
        idx, a = got
        if a.get("line_sha256") != sha256_bytes(raws[i]) or a.get("source") != rec.get("source") or not a.get("source"):
            refusals.append(f"{name} line {i}: its 'amend' record cites other bytes or another source")
        t, deadline = access_reach.get(idx), deadlines.get(i)
        if deadline is not None and (t is None or t >= deadline):
            refusals.append(f"{name} line {i}: its 'amend' record reached origin/main at or after the line's deadline")
    return refusals
