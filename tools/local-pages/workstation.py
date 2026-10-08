"""Read local exporter memory samples; keep CC readings when unavailable.

Primary metric contracts (source pins, not exporter-installation claims):
https://github.com/prometheus/prometheus/blob/5241a27fe3c6983549fccc32f6e65917408c63cd/docs/querying/api.md
https://github.com/prometheus-community/windows_exporter/blob/210e98bdde4cf9cd27f6bbddfa5c479294722131/docs/collector.memory.md
https://github.com/prometheus/node_exporter/blob/1271bc244266457fd225dcef9b8a33641b582c64/collector/meminfo_linux.go
https://github.com/prometheus/node_exporter/blob/1271bc244266457fd225dcef9b8a33641b582c64/collector/meminfo.go
This does not reinterpret hostmetrics ``free`` as ``available``.
"""

import json
import math
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener

ENDPOINT = "http://127.0.0.1:19090"
TIMEOUT = 2.0
MAX_AGE_SECONDS = 120
MAX_RESPONSE_BYTES = 262144
METRICS = (
    "windows_memory_available_bytes",
    "node_memory_MemAvailable_bytes",
    "node_memory_SwapTotal_bytes",
    "node_memory_SwapFree_bytes",
)
LOCAL_INSTANCE = r"(localhost|127[.]0[.]0[.]1)(:[0-9]+)?"
# A range selector returns original sample timestamps, not evaluation timestamps.
QUERY = (
    '{__name__=~"' + "|".join(METRICS) + '",instance=~"'
    + LOCAL_INSTANCE + '"}[5m]'
)
FIELDS = {
    "windows_available_gib": (METRICS[0],),
    "wsl_available_gib": (METRICS[1],),
    "swap_used_gib": (METRICS[2], METRICS[3]),
}


def _utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _fetch(query, *, timeout):
    url = ENDPOINT + "/api/v1/query?" + urlencode(
        {"query": query, "timeout": "1s"}
    )
    # The native API must stay loopback even when a process has a proxy set.
    with build_opener(ProxyHandler({})).open(url, timeout=timeout) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("response exceeds limit")
    return json.loads(raw)


def _sample(rows, metric_name, now):
    matches = [row for row in rows if row.get("metric", {}).get("__name__") == metric_name]
    if len(matches) != 1:
        raise ValueError("missing series" if not matches else "ambiguous series")
    row = matches[0]
    labels = {k: v for k, v in row["metric"].items() if k != "__name__"}
    if not re.fullmatch(LOCAL_INSTANCE, labels.get("instance", "")):
        raise ValueError("series is not a local target")
    samples = row.get("values", [])
    if not samples:
        raise ValueError("missing sample")
    latest = max(samples, key=lambda sample: float(sample[0]))
    timestamp, value = float(latest[0]), float(latest[1])
    if not math.isfinite(timestamp) or not math.isfinite(value) or value < 0:
        raise ValueError("invalid sample")
    if not 0 <= now - timestamp <= MAX_AGE_SECONDS:
        raise ValueError("stale or future sample")
    return value, timestamp, labels


def collect(fallback, fetch=None):
    """Return per-value provenance using fetch(query, timeout=2.0) if supplied.

    Missing, ambiguous, old, invalid or failed API results keep the exact CC
    value and its read time. Swap is derived only from matching total/free
    series for the same local target.
    """
    result = {
        field: {
            "value_gib": fallback.get(field),
            "source": "cc-now fallback",
            "read_utc": fallback.get("read_utc"),
            "query": QUERY,
            "sample_utc": None,
            "sample_labels": [],
            "fallback_reason": "missing series",
        }
        for field in FIELDS
    }
    result.update(endpoint=ENDPOINT, query=QUERY, API_errors=[])
    try:
        payload = (fetch or _fetch)(QUERY, timeout=TIMEOUT)
        if payload.get("status") != "success":
            raise ValueError("Prometheus API error status")
        data = payload.get("data", {})
        if data.get("resultType") != "matrix" or not isinstance(data.get("result"), list):
            raise ValueError("invalid API result shape")
        if payload.get("warnings"):
            raise ValueError("Prometheus API warnings")
        rows = data["result"]
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        result["fetched_utc"] = _utc(time.time())
        result["API_errors"].append({
            "endpoint": ENDPOINT,
            "read_utc": result["fetched_utc"],
            "type": type(error).__name__,
        })
        for field in FIELDS:
            result[field]["fallback_reason"] = "API read failed"
        return result
    now = time.time()
    result["fetched_utc"] = _utc(now)
    for field, metrics in FIELDS.items():
        try:
            samples = [_sample(rows, metric, now) for metric in metrics]
            value = samples[0][0]
            if len(samples) == 2:
                if samples[0][2] != samples[1][2]:
                    raise ValueError("swap targets differ")
                if abs(samples[0][1] - samples[1][1]) > 30:
                    raise ValueError("swap sample times differ")
                value -= samples[1][0]
                if value < 0:
                    raise ValueError("swap free exceeds total")
            sample_utc = _utc(min(sample[1] for sample in samples))
            result[field].update(
                value_gib=value / (1024 ** 3),
                source="prometheus",
                read_utc=sample_utc,
                sample_utc=sample_utc,
                sample_labels=[sample[2] for sample in samples],
                fallback_reason=None,
            )
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError) as error:
            result[field]["fallback_reason"] = str(error) if isinstance(error, ValueError) else "invalid sample"
    return result
