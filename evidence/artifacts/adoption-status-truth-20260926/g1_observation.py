#!/usr/bin/env python3
"""local_integration, read-only: the observation behind observability/native-data/render.py's G1 text (panels 10
and 19). Anonymous loopback queries only, all evaluated at one instant: Prometheus (127.0.0.1:19090) for the
Claude Code token counter's series, their instance label, their counter resets and increase() of output tokens
over the last hour, and Loki (127.0.0.1:13100) for the output tokens the same hour's claude-code api_request
events carry. Prints aggregate numbers only."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

METRIC = "ecosystem_claude_code_token_usage_tokens_total"


def query(base: str, path: str, expr: str, at: float) -> list:
    url = f"{base}{path}?" + urllib.parse.urlencode({"query": expr, "time": f"{at:.3f}"})
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)["data"]["result"]


def number(result: list) -> float | None:
    return float(result[0]["value"][1]) if result else None


def main() -> int:
    at = time.time()
    prom = lambda expr: query("http://127.0.0.1:19090", "/api/v1/query", expr, at)  # noqa: E731
    loki = lambda expr: query("http://127.0.0.1:13100", "/loki/api/v1/query", expr, at)  # noqa: E731
    series = number(prom(f"count({METRIC})"))
    unscoped = number(prom(f'count({METRIC}{{instance="unscoped"}})'))
    resets = number(prom(f"sum(resets({METRIC}[1h]))"))
    increase = number(prom(f'sum(increase({METRIC}{{type="output"}}[1h]))'))
    by_type = {item["metric"].get("type", "?"): int(float(item["value"][1]))
               for item in prom(f"count by (type) ({METRIC})")}
    logged = number(loki('sum(sum_over_time({service_name="claude-code"} | event_name="api_request"'
                         ' | unwrap output_tokens [1h]))'))
    print(json.dumps({
        "evaluated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(at)),
        "prometheus_series": series, "prometheus_series_instance_unscoped": unscoped,
        "prometheus_series_by_type": by_type,
        "prometheus_counter_resets_last_1h": resets,
        "prometheus_increase_output_tokens_last_1h": increase,
        "loki_api_request_output_tokens_last_1h": logged,
        "increase_over_loki": None if not logged or increase is None else round(increase / logged, 1),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
