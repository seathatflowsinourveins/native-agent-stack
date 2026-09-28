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
    if not isinstance(value, str) or not re.fullmatch(r"(?:cx/gpt-6(?:-[a-z0-9]+)*|sharedgw/gpt-6-astra-max)", value):
        raise ValueError("this gateway recipe accepts only approved GPT-6 model routes")
    return value


def select_routes(env):
    """Round-3 common arm contract; CLI CONFIG_PATH: GPTR@0957c301 config.py:158-166."""
    arm = env.get("RUNTIME_WORKER_ARM", "control")
    if arm not in ("control", "engines-on"):
        raise ValueError("unknown worker arm")
    base = "http://127.0.0.1:20129/v1" if arm == "engines-on" else BASE_URL
    model = "sharedgw/gpt-6-astra-max" if arm == "engines-on" else "cx/gpt-6-astra-max"
    worker = {"base_url": env.get("GPTR_BASE_URL", base), "model": env.get("GPTR_MODEL", model)}
    judge = {"base_url": env.get("GPTR_JUDGE_BASE_URL", BASE_URL),
             "model": env.get("GPTR_JUDGE_MODEL", "cx/gpt-6-astra-max")}
    if worker["base_url"] != base or judge["base_url"] != BASE_URL:
        raise ValueError("base URL does not match worker arm or control judge")
    for route in (worker, judge):
        validate_route(**route)
    return {"arm": arm, "worker": worker, "judge": judge}


def validate_route(base_url, model):
    model_id(model)
    expected = "http://127.0.0.1:20129/v1" if model.startswith("sharedgw/") else BASE_URL
    if base_url != expected:
        raise ValueError("model namespace does not match the allowlisted gateway")


def render_config(template, route, session):
    validate_route(**route)
    cfg = copy.deepcopy(template)
    for role in ("FAST_LLM", "SMART_LLM", "STRATEGIC_LLM"):
        cfg[role] = "openai:" + route["model"]
    headers = {"x-omniroute-session": session}
    if route["base_url"].endswith(":20129/v1"):
        headers["x-omniroute-compression"] = "allow-lossy"
    cfg["LLM_KWARGS"].update(base_url=route["base_url"], default_headers=headers,
                             reasoning_effort="max")
    return cfg


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
    def __init__(self, session, base_url=BASE_URL, model="cx/gpt-6-astra-max", correlation_log=None):
        if not session or not re.fullmatch(r"[a-zA-Z0-9_-]+", session):
            raise ValueError("invalid conversation identifier")
        self.session = session
        validate_route(base_url, model)
        self.base_url = base_url
        self.model = model
        self.correlation_log = correlation_log

    def record(self, event):
        if self.correlation_log is not None:
            with self.correlation_log.open("a") as handle:
                handle.write(json.dumps(event) + "\n")

    def response_hook(self, response):
        # HTTPX@0.28.1 docs/advanced/event-hooks.md:5-7,35-40: headers are
        # available before streamed bodies; never read the body in this hook.
        correlation = response.headers.get("X-Correlation-Id")
        if not isinstance(correlation, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", correlation):
            correlation = None
        self.record({"event": "response", "correlation_id": correlation})

    async def async_response_hook(self, response):
        self.response_hook(response)

    def headers(self, payload):
        validate_route(self.base_url, payload.get("model"))
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
        headers = {"x-omniroute-session": self.session, "Idempotency-Key": uuid.uuid4().hex}
        if self.base_url == "http://127.0.0.1:20129/v1":
            headers["x-omniroute-compression"] = "allow-lossy"
        return headers

    def request_hook(self, request):
        if str(request.url) not in (self.base_url + "/chat/completions", self.base_url + "/responses"):
            raise ValueError("unexpected model endpoint")
        request.headers.update(self.headers(json.loads(request.content)))
        self.record({"event": "request"})

    async def async_request_hook(self, request):
        self.request_hook(request)

    def grader_post(self, sender):
        """Adapt DRB-II's module-local requests.post; leave its prompt intact."""
        def post(url, **kwargs):
            if url != self.base_url + "/chat/completions":
                raise ValueError("unexpected grader endpoint")
            payload = {**kwargs["json"], "response_format": copy.deepcopy(DRB_RESPONSE_FORMAT)}
            kwargs["json"] = payload
            kwargs["headers"] = {**kwargs.get("headers", {}), **self.headers(payload)}
            self.record({"event": "request"})
            response = sender(url, **kwargs)
            self.response_hook(response)
            return response
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
        with httpx.Client(event_hooks={"request": [self.request_hook], "response": [self.response_hook]}, trust_env=False) as sync_client:
            async with httpx.AsyncClient(event_hooks={"request": [self.async_request_hook], "response": [self.async_response_hook]}, trust_env=False) as async_client:
                def factory(cls, provider, **kwargs):
                    if provider != "openai":
                        raise ValueError("only GPT-6 OpenAI-compatible routing is configured")
                    model_id(kwargs.get("model"))
                    kwargs.update(http_client=sync_client, http_async_client=async_client,
                                  max_retries=0, temperature=None, base_url=self.base_url)
                    return original(provider, **kwargs)
                GenericLLMProvider.from_provider = classmethod(factory)
                try:
                    yield
                finally:
                    GenericLLMProvider.from_provider = descriptor
