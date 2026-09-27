"""Loaded by the native server's supported --import-modules startup option.

SDK@fcc102a agent_server/__main__.py:74-135,240-273. Keep its ENTRYPOINT,
native LLM types, retries and serialization; reuse the per-call header adapter.
"""
import atexit
import os

from openhands.sdk import LLM
from worker import capture_correlation, gateway_transport

if os.environ.get("OPENHANDS_OWNED_CONTAINER") != "1":
    raise RuntimeError("server_transport_requires_owned_container")

_transport = gateway_transport(LLM, correlation_callback=capture_correlation)
_transport.__enter__()
atexit.register(_transport.__exit__, None, None, None)
