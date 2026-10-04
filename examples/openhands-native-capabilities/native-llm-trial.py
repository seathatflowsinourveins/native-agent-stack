"""One bounded SDK generation, with a local exact-output acceptance oracle.

Source: OpenHands/software-agent-sdk v1.50.1, commit
1e1390acc8788346ba4804c34323284009bf3f5e, sdk/llm/{llm,message,llm_response}.py
and tests/sdk/llm/test_responses_parsing_and_kwargs.py. The provider-qualified
route follows sdk/llm/utils/litellm_provider.py and LiteLLM v1.93.2's
litellm/litellm_core_utils/get_llm_provider_logic.py. No Conversation is created.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path

EXPECTED = "OH_NATIVE_LLM_OK_20260930"
PROMPT = f"Return exactly {EXPECTED} with no other text or whitespace."
MODEL = "openai/cx/gpt-6.1-sol-max"
CANONICAL_MODEL = "gpt-6.1-sol"
BASE_URL = "http://127.0.0.1:25371/v1"


def check_output(text: str) -> dict[str, object]:
    """Our integration oracle; exact equality includes all whitespace."""
    return {
        "exact_output_passed": text == EXPECTED,
        "output_characters": len(text),
        "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def contract() -> dict[str, object]:
    return {
        "sdk_version": "1.50.1",
        "litellm_version": "1.93.2",
        "model": MODEL,
        "wire_model": "cx/gpt-6.1-sol-max",
        "model_canonical_name": CANONICAL_MODEL,
        "base_url": BASE_URL,
        "api_mode": "responses",
        "reasoning_effort": "max",
        "api_key_kind": "public-local-loopback-placeholder",
        "num_retries": 0,
        "transport_max_retries": 0,
        "timeout_seconds": 180,
        "outer_deadline_seconds": 240,
        "max_output_tokens": 1024,
        "stream": False,
        "store": False,
        "tools": 0,
        "generate_calls": 1,
        "expected_output": EXPECTED,
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("prepare", "generate", "check-output"), default="prepare"
    )
    parser.add_argument("--persistence-dir", type=Path)
    parser.add_argument("--output", help="Local oracle input; never sent to a provider")
    args = parser.parse_args()
    if args.mode == "check-output":
        if args.output is None:
            parser.error("check-output requires --output")
        result = check_output(args.output)
        print(json.dumps({"mode": args.mode, **result}, sort_keys=True))
        return 0 if result["exact_output_passed"] else 2

    if args.persistence_dir is None or not args.persistence_dir.is_absolute():
        parser.error("prepare/generate require an absolute --persistence-dir")
    persistence_dir = args.persistence_dir.resolve()
    if not persistence_dir.is_dir():
        parser.error("the owned persistence directory must already exist")
    # This must precede every SDK import; OPENHANDS_* controls CLI state only.
    os.environ["OH_PERSISTENCE_DIR"] = str(persistence_dir)

    from openhands.sdk import LLM
    from openhands.sdk.llm import Message, TextContent
    from openhands.sdk.llm.utils.litellm_provider import LLMProvider
    from openhands.sdk.utils.path import get_user_persistence_dir
    from pydantic import SecretStr

    for package, version in (("openhands-sdk", "1.50.1"), ("litellm", "1.93.2")):
        if importlib.metadata.version(package) != version:
            raise RuntimeError(f"{package} must match the frozen version {version}")
    if get_user_persistence_dir().resolve() != persistence_dir:
        raise RuntimeError("native SDK persistence scope does not match")

    llm = LLM(
        usage_id="native-llm-trial",
        model=MODEL,
        model_canonical_name=CANONICAL_MODEL,
        base_url=BASE_URL,
        api_key=SecretStr("local-loopback"),
        api_mode="responses",
        reasoning_effort="max",
        native_tool_calling=True,
        caching_prompt=True,
        num_retries=0,
        timeout=180,
        stream_idle_timeout=180,
        max_output_tokens=1024,
        stream=False,
        log_completions=False,
        capability_overrides={
            "supports_reasoning_effort": True,
            "supports_sampling_params": False,
            "supports_responses_api": True,
        },
    )
    provider = LLMProvider.from_model(model=llm.model, api_base=llm.base_url)
    if provider.name != "openai" or provider.model != "cx/gpt-6.1-sol-max":
        raise RuntimeError("native provider resolution does not match the frozen route")
    if not llm.uses_responses_api():
        raise RuntimeError("native API mode does not match the frozen Responses route")
    metadata = {
        "mode": args.mode,
        "contract": contract(),
        "native_provider": provider.name,
        "native_persistence_scoped": True,
    }
    if args.mode == "prepare":
        print(json.dumps(metadata, sort_keys=True))
        return 0

    response = llm.generate(
        messages=[Message(role="user", content=[TextContent(text=PROMPT)])],
        store=False,
        max_retries=0,
    )
    message = response.message
    text_only = all(isinstance(item, TextContent) for item in message.content)
    text = "".join(item.text for item in message.content if isinstance(item, TextContent))
    result = check_output(text)
    result["assistant_text_only"] = (
        message.role == "assistant" and text_only and not message.tool_calls
    )
    usage = getattr(response.raw_response, "usage", None)
    metadata.update(
        result,
        provider_usage=usage.model_dump(mode="json") if usage is not None else "unknown",
    )
    print(json.dumps(metadata, sort_keys=True))
    return 0 if result["exact_output_passed"] and result["assistant_text_only"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
