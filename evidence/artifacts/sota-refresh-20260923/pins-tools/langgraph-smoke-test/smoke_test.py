"""langgraph worker/runtime acceptance smoke test.

Two parts, run against both the retained pin (1.2.11) and the candidate
release (1.2.12) in isolated venvs:

1. A minimal two-node StateGraph, compiled and invoked synchronously and via
   streaming, checking final state and event count.
2. A checkpointed graph using langgraph.checkpoint.memory.InMemorySaver (the
   exact import cited in this repository's
   catalogs/us-equities/agents-operations.json langgraph entry and the
   acceptance_gate in catalogs/us-equities/architecture/foundation.json),
   invoked with a thread_id, then resumed on the same thread_id to confirm
   the checkpointer persists and replays state across a second invoke call.

This is a local_integration check (no retained upstream receipt exercising
langgraph's runtime was found in this repository's evidence tree at run
time), not a full E2E, and does not cover LANGGRAPH_STRICT_MSGPACK,
durable/persistent (non-memory) checkpoint backends, or subgraphs. It does
exercise interrupt()/Command(resume=...) pause-and-resume on a single
thread_id via the InMemorySaver checkpointer (see part 2 above).
"""
import sys
from typing import TypedDict

from langgraph.graph import StateGraph, END


class State(TypedDict):
    count: int
    log: list


def step_a(state: State) -> State:
    return {"count": state["count"] + 1, "log": state["log"] + ["a"]}


def step_b(state: State) -> State:
    return {"count": state["count"] + 10, "log": state["log"] + ["b"]}


def build():
    g = StateGraph(State)
    g.add_node("a", step_a)
    g.add_node("b", step_b)
    g.set_entry_point("a")
    g.add_edge("a", "b")
    g.add_edge("b", END)
    return g.compile()


class CkState(TypedDict):
    total: int
    steps: list


def ask_human(state: CkState) -> CkState:
    from langgraph.types import interrupt

    answer = interrupt({"question": "how much to add?"})
    return {"total": state["total"] + answer, "steps": state["steps"] + [answer]}


def build_checkpointed(saver):
    g = StateGraph(CkState)
    g.add_node("ask", ask_human)
    g.set_entry_point("ask")
    g.add_edge("ask", END)
    return g.compile(checkpointer=saver)


def main():
    import langgraph
    print("langgraph version:", getattr(langgraph, "__version__", "unknown"))

    app = build()
    result = app.invoke({"count": 0, "log": []})
    assert result["count"] == 11, f"unexpected count: {result}"
    assert result["log"] == ["a", "b"], f"unexpected log: {result}"

    events = list(app.stream({"count": 0, "log": []}))
    assert len(events) == 2, f"unexpected stream event count: {len(events)}"

    print("RESULT:", result)
    print("STREAM_EVENTS:", len(events))

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command

    saver = InMemorySaver()
    ck_app = build_checkpointed(saver)
    cfg = {"configurable": {"thread_id": "smoke-thread-1"}}

    # First invoke hits an interrupt() inside the "ask" node and pauses;
    # the checkpointer persists the paused state under thread_id.
    paused = ck_app.invoke({"total": 0, "steps": []}, config=cfg)
    assert "__interrupt__" in paused, f"expected a pending interrupt, got: {paused}"

    snapshot_before_resume = ck_app.get_state(cfg)
    assert snapshot_before_resume.next == ("ask",), (
        f"checkpointer did not persist the paused node position: {snapshot_before_resume.next}"
    )

    # Resume on the same thread_id via Command(resume=...): langgraph must
    # load the persisted checkpoint (not start over) and complete the node.
    resumed = ck_app.invoke(Command(resume=5), config=cfg)
    assert resumed["total"] == 5, f"checkpointer did not resume from persisted state: {resumed}"
    assert resumed["steps"] == [5], f"unexpected resumed steps: {resumed}"

    final_snapshot = ck_app.get_state(cfg)
    assert final_snapshot.values["total"] == 5, f"get_state mismatch: {final_snapshot.values}"
    assert final_snapshot.next == (), f"expected graph to be finished: {final_snapshot.next}"

    history_len = len(list(ck_app.get_state_history(cfg)))
    assert history_len >= 2, f"expected at least 2 checkpoints (pause + resume), got {history_len}"

    print("CHECKPOINT_PAUSED:", paused)
    print("CHECKPOINT_RESUMED:", resumed)
    print("CHECKPOINT_GET_STATE:", dict(final_snapshot.values))
    print("CHECKPOINT_HISTORY_LEN:", history_len)
    print("SMOKE_TEST: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("SMOKE_TEST: FAIL", repr(e))
        sys.exit(1)
