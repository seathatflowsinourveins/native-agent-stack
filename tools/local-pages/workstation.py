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
import time
from datetime import datetime, timezone
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

ENDPOINT = "http://127.0.0.1:21090"
TIMEOUT = 2.0
MAX_AGE_SECONDS = 120
MAX_RESPONSE_BYTES = 262144
METRICS = (
    "windows_memory_available_bytes",
    "node_memory_MemAvailable_bytes",
    "node_memory_SwapTotal_bytes",
    "node_memory_SwapFree_bytes",
    "windows_memory_physical_total_bytes",
    "node_memory_MemTotal_bytes",
)
WINDOWS_JOB = "workstation-windows"
# A range selector returns original sample timestamps, not evaluation timestamps.
QUERY = '{__name__=~"' + "|".join(METRICS) + '"}[5m]'
FIELDS = {
    "windows_available_gib": (METRICS[0],),
    "wsl_available_gib": (METRICS[1],),
    "swap_used_gib": (METRICS[2], METRICS[3]),
    "windows_total_gib": (METRICS[4],),
    "wsl_total_gib": (METRICS[5],),
}
OPTIONAL_TOTALS = {"windows_total_gib", "wsl_total_gib"}


def _utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


class _NoRedirect(HTTPRedirectHandler):
    """Refuse redirects through urllib's supported redirect_request seam.

    https://docs.python.org/3.13/library/urllib.request.html#urllib.request.HTTPRedirectHandler.redirect_request
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, msg, headers, fp)


def _fetch(query, *, timeout):
    url = ENDPOINT + "/api/v1/query?" + urlencode(
        {"query": query, "timeout": "1s"}
    )
    # The native API must stay loopback even when a process has a proxy set.
    with build_opener(ProxyHandler({}), _NoRedirect()).open(url, timeout=timeout) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("response exceeds limit")
    return json.loads(raw)


def _sample(rows, metric_name, now, job):
    matches = [
        row for row in rows
        if row.get("metric", {}).get("__name__") == metric_name
        and row.get("metric", {}).get("job") == job
    ]
    if len(matches) != 1:
        raise ValueError("missing series" if not matches else "ambiguous series")
    row = matches[0]
    labels = {k: v for k, v in row["metric"].items() if k != "__name__"}
    if not isinstance(labels.get("instance"), str) or not labels["instance"]:
        raise ValueError("missing target instance")
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


def _node_job(rows, requested_job):
    node_metrics = {metric for metric in METRICS if metric.startswith("node_")}
    targets = {
        (row.get("metric", {}).get("job"), row.get("metric", {}).get("instance"))
        for row in rows
        if row.get("metric", {}).get("__name__") in node_metrics
        and (requested_job is None or row.get("metric", {}).get("job") == requested_job)
    }
    if len(targets) != 1:
        raise ValueError("missing node target" if not targets else "ambiguous node target")
    job, instance = next(iter(targets))
    if not all(isinstance(value, str) and value for value in (job, instance)):
        raise ValueError("unproven node target")
    if job == WINDOWS_JOB:
        raise ValueError("node series uses the Windows job")
    return job


def _fallback(fallback, field):
    value = fallback.get(field)
    read_utc = fallback.get(field + "_read_utc", fallback.get("read_utc"))
    if isinstance(read_utc, dict):
        read_utc = read_utc.get(field)
    if isinstance(value, dict):
        read_utc = value.get("read_utc", read_utc)
        value = value.get("value_gib")
    date_reason = None
    if read_utc is not None:
        try:
            if not isinstance(read_utc, str) or not read_utc or len(read_utc) > 50:
                raise ValueError("unbounded fallback date")
            parsed = datetime.fromisoformat(read_utc.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("timezone absent")
            parsed.astimezone(timezone.utc)
        except (ValueError, TypeError, AttributeError, OverflowError):
            read_utc = None
            date_reason = "fallback date requires bounded timezone-aware text"
    return {
        "value_gib": value,
        "source": "cc-now fallback",
        "read_utc": read_utc,
        "query": QUERY,
        "sample_utc": None,
        "sample_labels": [],
        "fallback_reason": "missing series",
        **({"date_reason": date_reason} if date_reason else {}),
    }


def validate_fallback(fallback):
    """Validate scalar and per-figure values; invalid dates remain unreported."""
    if not isinstance(fallback, dict):
        raise ValueError("workstation fallback requires an object")
    for field in ("windows_available_gib", "wsl_available_gib", "swap_used_gib"):
        value = _fallback(fallback, field)["value_gib"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("invalid current-view workstation fallback")


def normalize_optional_totals(readings):
    """Keep valid total observations; record unknown optional values separately."""
    result = dict(readings)
    existing_statuses = result.get("optional_total_status", {})
    statuses = dict(existing_statuses) if isinstance(existing_statuses, dict) else {}
    for field, available in (("windows_total_gib", "windows_available_gib"),
                             ("wsl_total_gib", "wsl_available_gib")):
        if field not in result:
            continue
        reading = result[field]
        reason = None
        value = reading.get("value_gib") if isinstance(reading, dict) else None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            reason = "optional total requires a finite positive numeric value"
        elif not isinstance(reading.get("source"), str):
            reason = "optional total source is not reported"
        else:
            if reading.get("date_reason"):
                reason = reading["date_reason"]
            available_reading = result.get(available)
            amount = available_reading.get("value_gib") if isinstance(available_reading, dict) else None
            if isinstance(amount, (int, float)) and not isinstance(amount, bool) and math.isfinite(amount) and value < amount:
                reason = "optional total is below available memory"
            recorded = reading.get("read_utc")
            if recorded is not None:
                try:
                    if not isinstance(recorded, str) or not recorded or len(recorded) > 50:
                        raise ValueError("unbounded date")
                    parsed = datetime.fromisoformat(recorded.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        raise ValueError("timezone absent")
                    parsed.astimezone(timezone.utc)
                except (ValueError, TypeError, AttributeError, OverflowError):
                    reason = "optional total date requires timezone-aware text"
        if reason:
            result.pop(field)
            statuses[field] = {"status": "UNKNOWN", "reason": reason}
        else:
            statuses.pop(field, None)
    if statuses:
        result["optional_total_status"] = statuses
    else:
        result.pop("optional_total_status", None)
    return result


def collect(fallback, fetch=None, *, wsl_job=None):
    """Return per-value provenance using fetch(query, timeout=2.0) if supplied.

    Missing, ambiguous, old, invalid or failed API results keep the exact CC
    value and its read time. Windows selects the CC-specified exporter job.
    Node series require one labelled target across the queried node metrics;
    an optional caller-verified job can narrow that selection. Swap requires
    matching total/free target labels.
    Total figures are optional when absent from fallback and live samples.
    """
    result = {
        field: _fallback(fallback, field)
        for field in FIELDS
        if field not in OPTIONAL_TOTALS or field in fallback
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
    except (OSError, HTTPException, ValueError, TypeError, KeyError, AttributeError) as error:
        result["fetched_utc"] = _utc(time.time())
        result["API_errors"].append({
            "endpoint": ENDPOINT,
            "read_utc": result["fetched_utc"],
            "type": type(error).__name__,
        })
        for field in FIELDS:
            if field in result:
                result[field]["fallback_reason"] = "API read failed"
        return normalize_optional_totals(result)
    now = time.time()
    result["fetched_utc"] = _utc(now)
    for field, metrics in FIELDS.items():
        try:
            job = WINDOWS_JOB if field.startswith("windows_") else _node_job(rows, wsl_job)
            samples = [_sample(rows, metric, now, job) for metric in metrics]
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
            result.setdefault(field, _fallback(fallback, field)).update(
                value_gib=value / (1024 ** 3),
                source="prometheus",
                read_utc=sample_utc,
                sample_utc=sample_utc,
                sample_labels=[sample[2] for sample in samples],
                fallback_reason=None,
            )
            # A valid live observation replaces all fallback provenance,
            # including an earlier malformed fallback date classification.
            result[field].pop("date_reason", None)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError) as error:
            if field in result:
                result[field]["fallback_reason"] = str(error) if isinstance(error, ValueError) else "invalid sample"
    return normalize_optional_totals(result)
