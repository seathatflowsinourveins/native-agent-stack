#!/usr/bin/env python3
"""One bounded official Responses SDK request to an existing loopback gateway.

Use the existing gateway inference key in OMNIROUTE_API_KEY. This does not read
provider stores, change routes, retry errors or provision paid API access.
Output is private and must be reviewed before publication.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

from openai import OpenAI


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:20128/v1")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if (url.scheme not in ("http", "https") or url.hostname not in
            ("127.0.0.1", "localhost", "::1") or url.username or url.password):
        parser.error("base-url must be the existing loopback gateway")
    key = os.environ.get("OMNIROUTE_API_KEY")
    if not key:
        parser.error("provide the existing local gateway inference key in OMNIROUTE_API_KEY")
    here = Path(__file__).resolve().parent
    output = args.output_dir.resolve()
    if output.is_relative_to(here.parents[2]):
        parser.error("output-dir must be outside the public repository")
    os.umask(0o077)
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    request = json.loads((here / "omniroute-astra-request.json").read_text())
    if request.get("model") != "cx/gpt-6-astra" or request.get("stream") is not True:
        parser.error("this recipe requires the explicit streamed Astra route")
    headers = {"x-omniroute-compression": "off", "X-OmniRoute-No-Cache": "true",
               "x-omniroute-no-memory": "true"}
    result = {"requested_model": request["model"], "attempts": 1, "status": "started"}
    (output / "request.json").write_text(json.dumps(request, indent=2) + "\n")
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    events = []
    started = time.monotonic()
    try:
        with OpenAI(base_url=args.base_url, api_key=key, max_retries=0, timeout=60) as client:
            # with_raw_response returns LegacyAPIResponse, not a context manager.
            with client.responses.with_streaming_response.create(**request, extra_headers=headers) as response:
                result["http_status"] = response.status_code
                result["route_headers"] = {name: response.headers.get(name) for name in
                    ("X-OmniRoute-Provider", "X-OmniRoute-Model")}
                for event in response.parse():
                    raw = event.model_dump(mode="json")
                    events.append(raw)
                    if raw.get("type") in ("response.completed", "response.failed", "response.incomplete"):
                        payload = raw.get("response", {})
                        result.update(status=raw["type"], returned_model=payload.get("model"),
                                      usage=payload.get("usage"), output=payload.get("output"),
                                      error=payload.get("error"))
                        break
    except Exception as error:
        result.update(status="exception", error_type=type(error).__name__, error=str(error),
                      http_status=getattr(error, "status_code", None))
    if result["status"] == "started":
        result["status"] = "stream_ended_without_terminal_event"
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    result["identity_matches"] = (
        result.get("returned_model") == "gpt-6-astra" and
        result.get("route_headers") == {"X-OmniRoute-Provider": "cx", "X-OmniRoute-Model": "gpt-6-astra"})
    (output / "events.json").write_text(json.dumps(events, indent=2) + "\n")
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    passed = result["status"] == "response.completed" and result["identity_matches"]
    print(json.dumps({"status": result["status"], "identity_matches": result["identity_matches"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
