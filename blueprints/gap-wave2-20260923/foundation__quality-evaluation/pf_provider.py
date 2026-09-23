"""Promptfoo Python provider: prints only the prediction, never the label.

Token usage is the endpoint's own meta.billed_units.input_tokens, returned in
Promptfoo's tokenUsage field so the harness reports it directly.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heldout_common import predict  # noqa: E402


def call_api(prompt, options, context):
    pred, tokens = predict(prompt)
    return {
        "output": f"pred={pred}",
        "tokenUsage": {"total": tokens, "prompt": tokens, "completion": 0, "numRequests": 1},
    }
