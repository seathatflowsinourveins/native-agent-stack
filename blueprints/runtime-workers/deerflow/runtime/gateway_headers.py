"""Request metadata for the pinned langchain-openai payload hook; see pins.json."""
import hashlib
import os
import uuid


def call_headers(scope):
    namespace = os.environ.get("DEERFLOW_SESSION_NAMESPACE", "deerflow-worker")
    affinity = hashlib.sha256((namespace + ":" + str(scope)).encode()).hexdigest()
    return {
        "x-omniroute-session": affinity,
        "Idempotency-Key": str(uuid.uuid4()),
        "X-OmniRoute-No-Cache": "true",
    }
