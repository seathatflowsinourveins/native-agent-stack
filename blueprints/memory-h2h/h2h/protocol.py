"""Common reader and reset -> ingest -> recall protocol.

The direct answer template is copied verbatim from LongMemEval
@9e0b455f4ef0e2ab8f2e582289761153549043fc, src/generation/run_generation.py
L57. The single-user-message request follows L360-L370; direct gen_length=500
is at L339-L343. Native retrieved text is used without extra extraction calls.
"""

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .data import Question, parse_date
from .types import MemoryAdapter, ModelRoute, Retrieved, Session


ANSWER_PROMPT = (
    "I will give you several history chats between you and a user. Please answer "
    "the question based on the relevant chat history.\n\n\nHistory Chats:\n\n{}"
    "\n\nCurrent Date: {}\nQuestion: {}\nAnswer:"
)


@dataclass(frozen=True)
class Completion:
    text: str
    usage: dict[str, Any] | None
    model: str | None
    response_id: str | None
    finish_reason: str | None
    seconds: float


class CompletionFailure(RuntimeError):
    """A model attempt failed; preserve any usage returned before the failure."""

    def __init__(self, message: str, completion: Completion):
        super().__init__(message)
        self.completion = completion
        self.record: dict[str, Any] | None = None


def chat_completion(route: ModelRoute, prompt: str, max_tokens: int) -> Completion:
    """One non-streaming call; retain usage exactly, including nested counters.

    Missing usage is unknown, not zero. There are no implicit retries whose
    usage would disappear from the experiment. Keys are read only at call time.
    """
    base = urlsplit(route.base_url)
    if (
        base.scheme not in ("http", "https") or not base.hostname
        or base.username is not None or base.password is not None
        or base.query or base.fragment
    ):
        raise ValueError("Model base_url must be an HTTP(S) URL without credentials, query or fragment")
    if not route.model or not route.api_key_env.isidentifier():
        raise ValueError("A model id and an API key environment variable name are required")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    key = os.environ.get(route.api_key_env)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": route.model,
        "messages": [{"role": "user", "content": prompt}],
        "n": 1,
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    request = Request(
        route.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=300) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise CompletionFailure(
            f"Chat Completions failed with HTTP {exc.code}",
            Completion("", None, None, None, None, time.perf_counter() - started),
        ) from None
    except (URLError, OSError, HTTPException):
        raise CompletionFailure(
            "Chat Completions transport failed",
            Completion("", None, None, None, None, time.perf_counter() - started),
        ) from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise CompletionFailure(
            "Chat Completions returned invalid JSON",
            Completion("", None, None, None, None, time.perf_counter() - started),
        ) from None
    try:
        choice = result["choices"][0]
        content = choice["message"]["content"]
        if not isinstance(content, str):
            raise TypeError
        usage = result.get("usage")
        if usage is not None and not isinstance(usage, dict):
            raise TypeError
    except (KeyError, IndexError, TypeError):
        metadata = result if isinstance(result, dict) else {}
        usage = metadata.get("usage")
        raise CompletionFailure(
            "Malformed Chat Completions response: expected text and optional usage object",
            Completion("", usage if isinstance(usage, dict) else None,
                       metadata.get("model"), metadata.get("id"), None,
                       time.perf_counter() - started),
        ) from None
    return Completion(
        content.strip(), usage, result.get("model"), result.get("id"),
        choice.get("finish_reason"), time.perf_counter() - started,
    )


def model_call(stage: str, route: ModelRoute, completion: Completion) -> dict[str, Any]:
    return {
        "stage": stage,
        "requested_model": route.model,
        "returned_model": completion.model,
        "response_id": completion.response_id,
        "finish_reason": completion.finish_reason,
        "seconds": completion.seconds,
        "usage": completion.usage,
        "outcome": "success",
    }


def build_answer_prompt(
    question: Question, retrieved: list[Retrieved], token_cap: int,
) -> tuple[str, dict[str, Any]]:
    """Budget conservatively without installing a model-specific tokenizer.

    UTF-8 byte count bounds ordinary byte-BPE token counts; reserve 32 additional
    units for the one-message chat framing. This is deliberately conservative,
    not an exact tokenizer for arbitrary OpenAI-compatible servers. We retain
    provider usage and check reported prompt_tokens after the call as well.
    Truncate only retrieved context; never truncate the question or date.
    """
    if token_cap <= 0:
        raise ValueError("token_cap must be positive")
    empty = ANSWER_PROMPT.format("", question.question_date or "", question.question)
    available = token_cap - len(empty.encode("utf-8")) - 32
    if available < 0:
        raise ValueError("token_cap is too small for the question and answer prompt")
    history = "\n\n".join(item.text for item in retrieved)
    encoded = history.encode("utf-8")
    context = encoded[:available].decode("utf-8", errors="ignore")
    prompt = ANSWER_PROMPT.format(context, question.question_date or "", question.question)
    return prompt, {
        "method": "utf8_bytes_plus_32_chat_framing",
        "token_cap": token_cap,
        "budget_used": len(prompt.encode("utf-8")) + 32,
        "retrieved_utf8_bytes": len(encoded),
        "included_utf8_bytes": len(context.encode("utf-8")),
        "truncated": len(context.encode("utf-8")) < len(encoded),
    }


def run_question(
    adapter: MemoryAdapter, question: Question, k: int,
    answer_route: ModelRoute, token_cap: int,
) -> dict[str, Any]:
    if k < 0:
        raise ValueError("k must be nonnegative")
    build_answer_prompt(question, [], token_cap)  # Validate before costly ingestion.
    started = time.perf_counter()
    namespace = "h2h-" + hashlib.sha256(question.question_id.encode("utf-8")).hexdigest()[:32]
    stage_started = time.perf_counter()
    adapter.reset(namespace)
    reset_seconds = time.perf_counter() - stage_started
    ordered = sorted(question.sessions, key=lambda session: parse_date(session.date))
    # Upstream evidence IDs contain "answer". Blind these labels before passing
    # sessions to a memory system; retain the inverse map only inside the core.
    sessions = [Session(f"session-{i:06d}", session.date, session.turns) for i, session in enumerate(ordered)]
    source_ids = {blind.session_id: source.session_id for blind, source in zip(sessions, ordered, strict=True)}
    stage_started = time.perf_counter()
    ingest = adapter.ingest(namespace, sessions)
    ingest_seconds = time.perf_counter() - stage_started
    stage_started = time.perf_counter()
    retrieved = list(adapter.retrieve(namespace, question.question, k, question.question_date))[:k] if k else []
    retrieve_seconds = time.perf_counter() - stage_started
    prompt, budget = build_answer_prompt(question, retrieved, token_cap)
    failure = None
    try:
        completion = chat_completion(answer_route, prompt, 500)
    except CompletionFailure as exc:
        failure = exc
        completion = exc.completion
    reported = (completion.usage or {}).get("prompt_tokens")
    budget["reported_prompt_tokens"] = reported
    budget["provider_cap_exceeded"] = isinstance(reported, (int, float)) and reported > token_cap
    record = {
        "question_id": question.question_id,
        "question_type": question.question_type,
        "question": question.question,
        "question_date": question.question_date,
        "answer_session_ids": list(question.answer_session_ids),
        "arm": adapter.name,
        "version": adapter.version,
        "namespace": namespace,
        "k": k,
        "retrieved": [
            {**asdict(item), "session_ids": [source_ids.get(sid, sid) for sid in item.session_ids],
             "adapter_session_ids": list(item.session_ids)}
            for item in retrieved
        ],
        "session_ids_reported": True if any(item.session_ids for item in retrieved) else getattr(
            adapter, "reports_session_ids", None
        ),
        "provenance": (
            "complete" if retrieved and all(item.session_ids for item in retrieved)
            else "partial" if any(item.session_ids for item in retrieved)
            else "empty" if not retrieved
            else "unreported"
        ),
        "hypothesis": completion.text,
        "ingest": asdict(ingest),
        "ingest_attempts": [asdict(ingest)],
        "seconds": time.perf_counter() - started,
        "timings": {
            "reset": reset_seconds, "ingest": ingest_seconds,
            "retrieve": retrieve_seconds, "answer": completion.seconds,
        },
        "prompt_budget": budget,
        "usage": {"answer": completion.usage},
        "model_calls": [model_call("answer", answer_route, completion)],
        "adapter_model_usage": None,
        "status": "answered",
    }
    if budget["provider_cap_exceeded"]:
        record["protocol_error"] = "Provider prompt_tokens exceeded token_cap; the provider needs its own tokenizer"
    if failure is not None:
        record["status"] = "answer_failed"
        record["model_calls"][-1].update(outcome="error", error=str(failure))
        failure.record = record
        raise failure
    return record
