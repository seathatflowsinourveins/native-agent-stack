"""Loaded by the native server's supported --import-modules startup option.

SDK@fcc102a agent_server/__main__.py:74-135,240-273. Keep its ENTRYPOINT,
native LLM types, retries and serialization; reuse the per-call header adapter.
"""
import atexit
from contextlib import contextmanager
from functools import wraps
import os

from openhands.sdk import LLM
from worker import capture_correlation, gateway_transport, register_worker_agents

if os.environ.get("OPENHANDS_OWNED_CONTAINER") != "1":
    raise RuntimeError("server_transport_requires_owned_container")

_transport = gateway_transport(LLM, correlation_callback=capture_correlation)
_transport.__enter__()
atexit.register(_transport.__exit__, None, None, None)

# Native factories must exist in the server process as well as the offline
# request serializer. Startup is scoped to one owned dispatch, never global.
register_worker_agents(os.environ, os.environ["OPENHANDS_RUN_ID"])


@contextmanager
def goal_judge_transport(service_type):
    """Pass native EventService's supported judge_llm argument explicitly.

    SDK@dcf401a event_service.py:1416-1468,1620-1667 and example 54.
    The REST route omits judge_llm, so defaulting would combine judge and agent
    usage. Keep the upstream loop and provide a separate native LLM instance.
    """
    originals = {name: getattr(service_type, name) for name in ("start_goal_loop", "resume_goal_loop")}
    def adapted(original):
        @wraps(original)
        async def run(service, *args, **kwargs):
            if "max_iterations" in kwargs and not 1 <= kwargs["max_iterations"] <= 3:
                raise ValueError("goal_audit_cap_is_three")
            if kwargs.get("judge_llm") is None:
                conversation = service._conversation
                if conversation is None:
                    raise ValueError("inactive_service")
                judge = conversation.agent.llm.model_copy(update={"usage_id": "goal-judge"})
                judge.reset_metrics()
                kwargs["judge_llm"] = judge
            return await original(service, *args, **kwargs)
        return run
    for name, original in originals.items():
        setattr(service_type, name, adapted(original))
    try:
        yield
    finally:
        for name, original in originals.items():
            setattr(service_type, name, original)


from openhands.agent_server.event_service import EventService
_goal_transport = goal_judge_transport(EventService)
_goal_transport.__enter__()
atexit.register(_goal_transport.__exit__, None, None, None)
