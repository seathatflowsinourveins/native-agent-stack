"""Promptfoo Python provider (fix round 2): Nemotron with the model card's input types.

Prints only the prediction; token usage is the endpoint's billed input tokens
summed over the query and document requests.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heldout_common import predict_typed  # noqa: E402


def call_api(prompt, options, context):
    pred, tokens = predict_typed(prompt)
    return {
        "output": f"pred={pred}",
        "tokenUsage": {"total": tokens, "prompt": tokens, "completion": 0, "numRequests": 2},
    }
