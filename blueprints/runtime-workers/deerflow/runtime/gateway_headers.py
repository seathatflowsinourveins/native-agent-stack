"""Request metadata for the pinned langchain-openai payload hook; see pins.json."""
import hashlib
import os
import uuid


def call_headers(scope):
    namespace = os.environ.get("DEERFLOW_SESSION_NAMESPACE", "deerflow-worker")
    # One embedded conversation owns this process, including child/background
    # calls. Interactive workers without this variable retain native thread scope.
    scope = os.environ.get("DEERFLOW_CONVERSATION_ID") or scope
    affinity = hashlib.sha256((namespace + ":" + str(scope)).encode()).hexdigest()
    return {
        "x-omniroute-session": affinity,
        "Idempotency-Key": str(uuid.uuid4()),
        "X-OmniRoute-No-Cache": "true",
    }
