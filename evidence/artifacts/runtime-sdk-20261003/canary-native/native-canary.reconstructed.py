# Reconstructed from qualification facts, not an attested copy of the original heredoc.
# The supplied facts retain configuration/output but contain no source text.
import json, time
from openai_codex import Codex
marker = "SDK_01600_NATIVE_CANARY_OK"; t0 = time.time()
with Codex() as codex:
    th = codex.thread_start(model="gpt-6.1-sol", ephemeral=True, config={"model_reasoning_effort": "low"})
    r = th.run(f"Reply with exactly this text and nothing else: {marker}")
    print(json.dumps({"marker_exact_match": (r.final_response or "").strip() == marker,
                      "final_response": (r.final_response or "")[:200],
                      "item_types": [type(item).__name__ for item in r.items],
                      "usage": r.usage.model_dump() if getattr(r, "usage", None) is not None else None,
                      "seconds": round(time.time() - t0, 1)}, default=str))
