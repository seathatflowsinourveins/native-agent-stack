"""Send one synthetic OTLP span to a loopback Phoenix and read it back. Usage: phoenix_span_roundtrip.py BASE_URL"""
import json
import sys
import time
import urllib.request

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

base = sys.argv[1].rstrip("/")
provider = TracerProvider(resource=Resource.create({"service.name": "gap-wave2-probe",
                                                    "openinference.project.name": "default"}))
provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=base + "/v1/traces")))
tracer = provider.get_tracer("gap-wave2")
with tracer.start_as_current_span("synthetic-evaluation-probe") as span:
    span.set_attribute("probe.kind", "synthetic")
    span.set_attribute("openinference.span.kind", "CHAIN")
    trace_id = format(span.get_span_context().trace_id, "032x")
provider.force_flush(); provider.shutdown()

found, attempts, body = None, 0, None
for attempts in range(1, 21):
    try:
        with urllib.request.urlopen(base + "/v1/projects/default/spans?limit=50", timeout=5) as response:
            body = json.loads(response.read())
        spans = body.get("data", [])
        found = next((s for s in spans if s.get("name") == "synthetic-evaluation-probe"), None)
        if found:
            break
    except Exception as error:  # retained in output
        body = {"error": repr(error)}
    time.sleep(1)
print(json.dumps({"sent_trace_id": trace_id, "readback_endpoint": "/v1/projects/default/spans",
                  "attempts": attempts, "found": bool(found),
                  "readback_trace_id": (found or {}).get("context", {}).get("trace_id"),
                  "readback_name": (found or {}).get("name"),
                  "readback_attributes": (found or {}).get("attributes"),
                  "last_body_if_missing": None if found else body}, indent=1))
sys.exit(0 if found and found.get("context", {}).get("trace_id") == trace_id else 1)
