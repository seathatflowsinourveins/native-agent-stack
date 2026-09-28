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
    arm = os.environ.get("RUNTIME_WORKER_ARM", "control")
    if arm not in {"control", "engines-on"}:
        raise ValueError("invalid runtime worker arm")
    headers = {
        "x-omniroute-session": affinity,
        "Idempotency-Key": str(uuid.uuid4()),
    }
    if arm == "engines-on":
        headers["x-omniroute-compression"] = "allow-lossy"
    return headers
