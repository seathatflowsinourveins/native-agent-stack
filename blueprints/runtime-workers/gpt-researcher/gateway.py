"""Scoped gateway transport, using upstream client hooks, not a proxy service.

Sources: GPT Researcher 0957c301 generic/base.py:146-158;
langchain-openai 1.6.6 chat_models/base.py:1022-1034 (HTTP client injection);
httpx 0.28.1 docs/advanced/event-hooks.md (request header mutation);
DRB-II b38f360 gpt_client.py:85-109 and run_evaluation.py:95-116 (wire schema).
"""
from contextlib import asynccontextmanager
import copy
import json
import math
import re
import uuid

BASE_URL = "http://127.0.0.1:20128/v1"
CHAT_URL = BASE_URL + "/chat/completions"
DRB_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "drb2_rubric_scores", "strict": True,
        "schema": {
            "type": "object", "additionalProperties": False, "required": ["results"],
            "properties": {"results": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["rubric_item", "score", "reason", "evidence"],
                "properties": {
                    "rubric_item": {"type": "string"},
                    "score": {"type": "integer", "enum": [-1, 0, 1]},
                    "reason": {"type": "string"}, "evidence": {"type": "string"}
                }
            }}}
        }
    }
}


def model_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"cx/gpt-6(?:-[a-z0-9]+)*", value):
        raise ValueError("this gateway recipe accepts only cx/gpt-6 model routes")
    return value


def strict_objects(schema):
    """Reject, rather than silently rewrite, an unsafe strict schema."""
    if isinstance(schema, list):
        for child in schema:
            strict_objects(child)
    elif isinstance(schema, dict):
        types = schema.get("type")
        if types == "object" or (isinstance(types, list) and "object" in types) or "properties" in schema:
            if (schema.get("additionalProperties") is not False
                    or set(schema.get("required", [])) != set(schema.get("properties", {}))):
                raise ValueError("strict schema requires closed objects and all properties required")
        for child in schema.values():
            strict_objects(child)


class GatewayTransport:
    def __init__(self, session):
        if not session or not re.fullmatch(r"[a-zA-Z0-9_-]+", session):
            raise ValueError("invalid conversation identifier")
        self.session = session

    def headers(self, payload):
        model_id(payload.get("model"))
        temperature = payload.get("temperature")
        if temperature is not None and (type(temperature) not in (int, float)
                                        or not math.isfinite(temperature) or temperature <= 0.1):
            raise ValueError("temperature must be omitted or greater than 0.1")
        # Validate both Chat Completions and Responses format locations.
        fmt = payload.get("response_format") or payload.get("text", {}).get("format")
        if fmt and fmt.get("type") != "text":
            definition = fmt.get("json_schema", fmt)
            if fmt.get("type") != "json_schema" or definition.get("strict") is not True:
                raise ValueError("use tool calling or a strict JSON schema, never json_object")
            strict_objects(definition["schema"])
        for tool in payload.get("tools", []):
            function = tool.get("function", tool)
            if function.get("strict"):
                strict_objects(function.get("parameters", {}))
        return {"x-omniroute-session": self.session, "Idempotency-Key": uuid.uuid4().hex}

    def request_hook(self, request):
        if str(request.url) not in (CHAT_URL, BASE_URL + "/responses"):
            raise ValueError("unexpected model endpoint")
        request.headers.update(self.headers(json.loads(request.content)))

    async def async_request_hook(self, request):
        self.request_hook(request)

    def grader_post(self, sender):
        """Adapt DRB-II's module-local requests.post; leave its prompt intact."""
        def post(url, **kwargs):
            if url != CHAT_URL:
                raise ValueError("unexpected grader endpoint")
            payload = {**kwargs["json"], "response_format": copy.deepcopy(DRB_RESPONSE_FORMAT)}
            kwargs["json"] = payload
            kwargs["headers"] = {**kwargs.get("headers", {}), **self.headers(payload)}
            return sender(url, **kwargs)
        return post

    @asynccontextmanager
    async def worker_clients(self):
        """Supply native LangChain clients to every nested researcher factory.

        JSON config cannot carry live HTTP clients. This process-local factory
        adapter is restored on exit; upstream source and prompts stay unchanged.
        Each SDK generation has retries disabled and receives a fresh key.
        Native outer retry loops are separate generation attempts (see README).
        """
        import httpx
        from gpt_researcher.llm_provider.generic.base import GenericLLMProvider

        descriptor = GenericLLMProvider.__dict__["from_provider"]
        original = GenericLLMProvider.from_provider
        with httpx.Client(event_hooks={"request": [self.request_hook]}, trust_env=False) as sync_client:
            async with httpx.AsyncClient(event_hooks={"request": [self.async_request_hook]}, trust_env=False) as async_client:
                def factory(cls, provider, **kwargs):
                    if provider != "openai":
                        raise ValueError("only GPT-6 OpenAI-compatible routing is configured")
                    model_id(kwargs.get("model"))
                    kwargs.update(http_client=sync_client, http_async_client=async_client,
                                  max_retries=0, temperature=None, base_url=BASE_URL)
                    return original(provider, **kwargs)
                GenericLLMProvider.from_provider = classmethod(factory)
                try:
                    yield
                finally:
                    GenericLLMProvider.from_provider = descriptor
