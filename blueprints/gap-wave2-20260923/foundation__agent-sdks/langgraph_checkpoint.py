#!/usr/bin/env python3
"""LangGraph checkpoint save/resume across two OS processes (no model call).

Phase `start`: a three-node graph with interrupt_before=["approve"] runs to the
interrupt and is checkpointed in SQLite. Phase `resume` (a new process) opens the
same SQLite file, reads the saved state for the thread id and resumes with
invoke(None, config); the final state must contain both pre- and post-interrupt
node outputs and the pre-interrupt node must not run again.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from typing import Annotated, TypedDict
import operator

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    log: Annotated[list[str], operator.add]
    total: int


def fetch(state: State) -> dict:
    return {"log": [f"fetch@pid{os.getpid()}"], "total": state["total"] + 40}


def approve(state: State) -> dict:
    return {"log": [f"approve@pid{os.getpid()}"], "total": state["total"] + 1}


def publish(state: State) -> dict:
    return {"log": [f"publish@pid{os.getpid()}"], "total": state["total"] + 1}


def build(saver):
    g = StateGraph(State)
    g.add_node("fetch", fetch)
    g.add_node("approve", approve)
    g.add_node("publish", publish)
    g.add_edge(START, "fetch")
    g.add_edge("fetch", "approve")
    g.add_edge("approve", "publish")
    g.add_edge("publish", END)
    return g.compile(checkpointer=saver, interrupt_before=["approve"])


def main() -> int:
    phase, db, out = sys.argv[1], sys.argv[2], sys.argv[3]
    config = {"configurable": {"thread_id": "gap8-thread"}}
    conn = sqlite3.connect(db, check_same_thread=False)
    saver = SqliteSaver(conn)
    graph = build(saver)
    rec = {"phase": phase, "pid": os.getpid()}
    if phase == "start":
        result = graph.invoke({"log": [], "total": 0}, config)
        snap = graph.get_state(config)
        rec.update(result=result, next=list(snap.next))
    else:
        before = graph.get_state(config)
        rec["loaded_state"] = {"values": before.values, "next": list(before.next)}
        result = graph.invoke(None, config)
        after = graph.get_state(config)
        rec.update(result=result, next=list(after.next),
                   checkpoints=sum(1 for _ in saver.list(config)))
    conn.close()
    with open(out, "w") as f:
        json.dump(rec, f, indent=2)
    print(json.dumps(rec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
