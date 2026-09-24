"""A stage end to end over one store: the plan (for the fetch loop and the reproduction check), the D events,
the evaluation and the holdout count. Stage specs:

  development  screen sessions 2016-01-04 .. 2019-12-31 (warm-up included, for the tercile pool), kept years only
  validation   the last kept 2019 session (a decision whose entry is 2020-01-02) and the 2020 sessions
  holdout      the breakpoint screen 2024-11-01 .. 2025-12-31 (fetched under the first 'count'), N0 - 1 and the
               holdout sessions; the gap 2026-01-02 .. N0 - 2 is never screened
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from core import chronology as CH
from core import count_unit as CU
from core import evaluate as EV
from core import events as EVS
from core import plan, screen
from core import terciles as TC
from core.calendar import year_of
from core.identity import rename_pairs
from core.trades import Ctx, trade


@dataclass
class StageSpec:
    stage: str
    cal: object
    symbols: list
    actions: list
    active: frozenset = frozenset()
    dropped_years: frozenset = frozenset()
    n0: str | None = None
    holdout_last: str | None = None
    fees: object = None
    cells: dict | None = None
    paper_exposed: frozenset = frozenset()
    late_sessions: frozenset = frozenset()
    carried: tuple | None = None
    extra: dict = field(default_factory=dict)

    def arms(self, mode: str) -> tuple:
        """Every arm, except at a holdout read, which plans and books only the carried items' arms (M-1)."""
        if self.stage == "holdout" and self.carried is not None and mode != "count":
            return EV.arms_for(self.carried)
        return EV.ARMS

    @property
    def segs(self):
        hold = (self.n0, self.holdout_last) if self.stage == "holdout" else None
        return CH.stage_segments(self.cal, self.stage, self.dropped_years, hold)

    def screen_sessions(self) -> list:
        cal, dy = self.cal, self.dropped_years
        if self.stage == "development":
            return CH.kept_sessions(cal, "2016-01-04", "2019-12-31", dy)
        if self.stage == "validation":
            kept = CH.kept_sessions(cal, "2020-01-02", "2020-12-31", dy)
            if not kept:
                return []
            prev = cal.offset(kept[0], -1)
            return ([prev] if prev and year_of(prev) not in dy else []) + kept
        part_a = cal.range("2024-11-01", "2025-12-31")
        return part_a + cal.range(cal.offset(self.n0, -1), self.holdout_last)

    def stage_sessions(self) -> list:
        if self.stage == "holdout":
            return self.cal.range(self.n0, self.holdout_last)
        return CH.kept_sessions(self.cal, *CH.stage_range(self.stage), self.dropped_years)

    def pool(self) -> list:
        if self.stage == "development":
            return TC.pool_development(self.cal, self.dropped_years)
        if self.stage == "validation":
            return TC.pool_validation(self.cal, self.dropped_years)
        return TC.pool_holdout(self.cal, self.n0, self.holdout_last)

    def ctx(self, mode: str) -> Ctx:
        return Ctx(cal=self.cal, stage=self.stage, segs=self.segs, dropped_years=self.dropped_years,
                   actions=self.actions, fees=self.fees, cells=self.cells, mode=mode,
                   paper_exposed=self.paper_exposed, late_sessions=self.late_sessions)


def _screen_reqs(spec, store=None) -> list:
    """The screen requests of the stage. A holdout store holds the sealed collection batches, merged per (symbol,
    session); only the symbol-sessions that no batch holds are requested (review round 9, M-6)."""
    uncovered = getattr(store, "uncovered", None)
    if uncovered is None:
        return [r for s in spec.screen_sessions() for r in plan.screen_requests(spec.cal, s, spec.symbols)]
    out = []
    for s in spec.screen_sessions():
        for batch in plan.batches(spec.symbols):
            missing = uncovered(s, batch)
            if missing:
                out.extend(plan.screen_requests(spec.cal, s, missing))
    return out


def d_events(spec, store, strict: bool = True):
    """(events, counts, needs, used): D events of the stage's screen sessions; used lists every per-event request
    the candidates require (the plan), needs the ones not yet sealed."""
    counts = Counter()
    cands, sc, report = screen.candidates(store, spec.cal, spec.screen_sessions(), spec.symbols,
                                          rename_pairs(spec.actions), spec.active)
    counts.update(sc)
    events, needs, used = [], [], []
    segs = spec.segs
    hold = spec.stage == "holdout"
    for c in cands:
        end = plan.event_end(spec.cal, c["t"], segs)
        used.extend(plan.event_requests(spec.cal, c["symbol"], c["t"], end, holdout=hold))
        data = EVS.event_data(store, spec.cal, c["symbol"], c["t"], end, strict=strict, holdout=hold)
        if "needs" in data:
            needs.extend(data["needs"])
            continue
        ev = EVS.build_event(spec.cal, c, data, counts, holdout=hold)
        if ev is not None:
            events.append(ev)
    counts["d_events"] = len(events)
    return events, dict(counts), needs, used


def planner(spec, mode: str = "plan"):
    """The plan as a function of the sealed store (core.driver.to_fixpoint and the reproduction check)."""
    def requests(store) -> list:
        reqs = _screen_reqs(spec, store)
        if any(not store.has(r["key"]) for r in reqs):
            return reqs
        events, _, needs, used = d_events(spec, store, strict=False)
        reqs.extend(needs)
        reqs.extend(used)
        ctx = spec.ctx(mode)
        ctx.trace = []
        sset = set(spec.stage_sessions())
        for ev in events:
            if not EV.in_stage(ctx, ev, sset):
                continue
            for arm in spec.arms(mode):
                tr = trade(ev, arm, ctx, store)
                reqs.extend(tr.get("needs", []))
        reqs.extend(ctx.trace)
        return sorted({r["key"]: r for r in reqs}.values(), key=lambda r: r["key"])
    return requests


def evaluate_stage(spec, store, protocol_id: str, *, tested=True, void=None, carried=None, validation_signs=None, B=None,
                   qualifiers=(), identity_limited=None):
    events, counts, _, _ = d_events(spec, store, strict=True)
    carried = carried if carried is not None else spec.carried
    res = EV.evaluate(spec.stage, events, spec.ctx("read"), store, protocol_id=protocol_id,
                      stage_sessions=spec.stage_sessions(), pool=spec.pool(), tested=tested, void=void,
                      carried=tuple(carried) if carried is not None else EV.ITEM_IDS,
                      validation_signs=validation_signs, B=B, qualifiers=tuple(qualifiers),
                      identity_limited=identity_limited)
    res["counts"].update({"membership": counts})
    return res


def count_stage(spec, store) -> dict:
    events, counts, _, _ = d_events(spec, store, strict=True)
    ctx = spec.ctx("count")
    sset = set(spec.stage_sessions())
    evs = [ev for ev in events if EV.in_stage(ctx, ev, sset)]
    terc = EV.assign_terciles(events, spec.pool(), lambda ev: EV.in_stage(ctx, ev, sset))
    return CU.count(evs, ctx, store, terc)
