"""chronology: stages, kept sessions, segments, embargo, censoring and the prospective holdout window."""
from __future__ import annotations

from core.calendar import year_of
from core.params import CHRONO

STAGES = ("development", "validation", "holdout")


def stage_range(stage: str):
    return tuple(CHRONO[stage])


def kept_sessions(cal, first: str, last: str, dropped_years=frozenset()) -> list:
    return [d for d in cal.range(first, last) if year_of(d) not in dropped_years]


def segments(cal, first: str, last: str, dropped_years=frozenset()) -> list:
    """Maximal runs of kept sessions; each edge of a dropped year is a segment boundary."""
    out, run = [], []
    for d in cal.range(first, last):
        if year_of(d) in dropped_years:
            if run:
                out.append((run[0], run[-1]))
            run = []
        else:
            run.append(d)
    if run:
        out.append((run[0], run[-1]))
    return out


def stage_segments(cal, stage: str, dropped_years=frozenset(), holdout=None) -> list:
    if stage == "holdout":
        return [holdout] if holdout else []
    first, last = stage_range(stage)
    return segments(cal, first, last, dropped_years)


def segment_of(segs: list, session: str):
    for i, (a, b) in enumerate(segs):
        if a <= session <= b:
            return i
    return None


def embargoed(cal, stage: str, segs: list, session: str, dropped_years=frozenset()) -> bool:
    """Multi-session items give up the first 6 sessions of validation and the first 6 kept sessions after a
    dropped year as entry sessions. None at N0 (the holdout) and none after the warm-up."""
    if stage == "holdout":
        return False
    i = segment_of(segs, session)
    if i is None:
        return False
    first = segs[i][0]
    prev = cal.offset(first, -1)
    after_dropped = prev is not None and year_of(prev) in dropped_years
    starts_validation = stage == "validation" and first == cal.next_on_or_after(stage_range("validation")[0])
    if not (after_dropped or starts_validation):
        return False
    return cal.index(session) - cal.index(first) < CHRONO["embargo_sessions"]


def freeze_session(cal, freeze_time: float):
    """The first XNYS session whose scheduled open is at or after the freeze commit's committer time."""
    return cal.session_of_time(freeze_time)


def n0(cal, freeze_time: float):
    fs = freeze_session(cal, freeze_time)
    return None if fs is None else cal.offset(fs, CHRONO["n0_offset_sessions"])


def holdout_segment(cal, n0_session: str, blocks: int = 0):
    """(first, last) of the holdout after `blocks` 63-session extension blocks (actual sessions)."""
    if not 0 <= blocks <= CHRONO["max_extension_blocks"]:
        raise ValueError("at most 2 extension blocks")
    n = CHRONO["holdout_sessions"] + blocks * CHRONO["extension_block_sessions"]
    last = cal.offset(n0_session, n - 1)
    return (n0_session, last) if last else None
