"""Thin ChatOpenAI extension, not a replacement model client.

Source: langchain-openai 1.2.1 chat_models/base.py:1683-1712,3327-3345;
SHA256-verified sdist and DeerFlow model factory references are in pins.json.
The upstream payload is passed unchanged except for per-call HTTP headers and
omitting temperature. OpenAI SDK retries reuse this already-built payload.
"""
from langchain_openai import ChatOpenAI as UpstreamChatOpenAI
from langgraph.config import get_config
from gateway_headers import call_headers


class ChatOpenAI(UpstreamChatOpenAI):
    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        try:
            scope = get_config().get("configurable", {}).get("thread_id", "background")
        except RuntimeError:
            scope = "background"
        payload["extra_headers"] = {
            **(payload.get("extra_headers") or {}), **call_headers(scope)
        }
        payload.pop("temperature", None)
        return payload
