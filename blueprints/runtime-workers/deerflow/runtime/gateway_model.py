"""Thin ChatOpenAI extension, not a replacement model client.

Source: langchain-openai 1.2.1 chat_models/base.py:1683-1712,3327-3345;
SHA256-verified sdist and DeerFlow model factory references are in pins.json.
Structured output uses upstream function_calling (base.py:2400-2440), without
strict schema enforcement; its native parser still validates the returned value.
Raw JSON modes are refused, since OmniRoute's moved system instructions cannot
satisfy json_object's input-message condition. OpenAI SDK retries reuse a payload.
"""
from langchain_openai import ChatOpenAI as UpstreamChatOpenAI
from langgraph.config import get_config
from gateway_headers import call_headers


class ChatOpenAI(UpstreamChatOpenAI):
    def with_structured_output(self, schema=None, *, method="function_calling",
                               include_raw=False, strict=None, **kwargs):
        if kwargs.get("tools"):
            raise ValueError("Use bind_tools for mixed tools; this structured-output adapter selects one tool")
        kwargs.pop("tools", None)
        return super().with_structured_output(
            schema, method="function_calling", include_raw=include_raw, strict=False, **kwargs
        )

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        if payload.get("response_format") or payload.get("text", {}).get("format", {}).get("type", "text") != "text":
            raise ValueError("Use with_structured_output or bind_tools; raw JSON response formats are not enabled")
        try:
            scope = get_config().get("configurable", {}).get("thread_id", "background")
        except RuntimeError:
            scope = "background"
        payload["extra_headers"] = {
            **(payload.get("extra_headers") or {}), **call_headers(scope)
        }
        payload.pop("temperature", None)
        return payload
