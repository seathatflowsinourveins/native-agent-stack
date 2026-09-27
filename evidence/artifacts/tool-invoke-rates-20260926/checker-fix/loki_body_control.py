#!/usr/bin/env python3
"""Failing-first control for the always-run Loki fixed-body check (GPT-6 re-check of #366, finding 2).

Runs replay.py's real loki() against a stubbed Loki (no sockets). Its query_range returns either clean records,
where every line is the Collector placeholder, or leaking records, where every line is "pwd". The control
reports whether a fixed-body check caught the leak. The exported records come from replay.py's own
synthetic_batches, transformed the way synthetic_replay_control.py does. Only the fixed-body check is scored;
the dashboard checks are not, because the stub returns no series for them.
Usage: python loki_body_control.py [--replay PATH_TO_REPLAY_PY] WORK_DIR
Exit 0 only if the clean records pass the fixed-body check and the leaking records fail it.
"""
import argparse
import contextlib
import copy
import importlib.util
import io
import json
import sys
import urllib.parse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
parser = argparse.ArgumentParser()
parser.add_argument("--replay", default=str(HERE.parent / "scratch-replay/replay.py"))
parser.add_argument("work")
args = parser.parse_args()
spec = importlib.util.spec_from_file_location("replay_under_test", args.replay)
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)

work = Path(args.work)
work.mkdir(parents=True, exist_ok=True)
collector = REPO / "observability/collector/collector.yaml"
dashboard = REPO / "observability/backends/templates/ecosystem-dashboard.json.example"
now = 1_800_000_000_000_000_000
resource_allow, log_allow = replay.staged_allowlists(collector)
output, services = [], set()
for line_no, source in enumerate(replay.synthetic_batches(now)):
    doc = copy.deepcopy(source)
    n = 0
    for rl in doc["resourceLogs"]:
        resource = replay.attrs(rl["resource"]["attributes"])
        services.add(str(resource.get("service.name", "")))
        rl["resource"]["attributes"] = [{"key": k, "value": replay.to_otlp_value(v)}
                                         for k, v in resource.items() if k in resource_allow]
        for sl in rl["scopeLogs"]:
            sl["scope"] = {"name": "native-agent-telemetry"}
            for record in sl["logRecords"]:
                original = replay.attrs(record["attributes"])
                final = {k: v for k, v in original.items() if k in log_allow and k not in replay.DERIVED_KEYS}
                final.update(replay.expected_derived(original, resource))
                final["receipt_id"] = f"u6s-{line_no}-{n}"
                n += 1
                record["attributes"] = [{"key": k, "value": replay.to_otlp_value(v)} for k, v in final.items()]
                record["body"] = {"stringValue": "[content omitted]"}
    output.append(json.dumps(doc))
out_path = work / "reference-output.jsonl"
out_path.write_text("\n".join(output) + "\n")
total = sum(len(sl["logRecords"]) for line in output for rl in json.loads(line)["resourceLogs"]
            for sl in rl["scopeLogs"])


class Response:
    def __init__(self, payload):
        self._bytes = json.dumps(payload).encode()
        self.status = 200

    def read(self, *_):
        return self._bytes

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def stub(line):
    streams = [{"stream": {"service_name": svc},
                "values": [[str(now + i), line, {"structuredMetadata": {"receipt_id": f"u6s-{svc}-{i}"}}]
                           for i in range(total)] if svc == sorted(services)[0] else []}
               for svc in sorted(services)]

    def urlopen(target, timeout=None):
        url = target.full_url if hasattr(target, "full_url") else target
        if "query_range" in url:
            return Response({"data": {"result": streams}})
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("query", [""])[0]
        if "count_over_time" in query and "receipt_id" in query and query.startswith("sum(count"):
            return Response({"data": {"result": [{"value": [now / 1e9, str(total)]}]}})
        return Response({"data": {"result": []}})
    return urlopen


def body_check(line):
    replay.results.update({"pass": 0, "fail": 0})
    buffer = io.StringIO()
    with patch.object(replay.urllib.request, "urlopen", side_effect=stub(line)), contextlib.redirect_stdout(buffer):
        replay.loki(SimpleNamespace(port=45702, collector=str(collector), out=str(out_path), dashboard=str(dashboard),
                                    window="3h", at=now / 1e9))
    found = [l for l in buffer.getvalue().splitlines() if "Loki record line is exactly" in l]
    return found


clean, leak = body_check("[content omitted]"), body_check("pwd")
print(f"INFO replay under test: {Path(args.replay).name}; exported records={total}")
print(f"INFO clean records -> fixed-body check lines: {clean or 'none'}")
print(f"INFO leaking records ('pwd') -> fixed-body check lines: {leak or 'none'}")
clean_ok = len(clean) == 1 and clean[0].startswith("PASS")
leak_caught = len(leak) == 1 and leak[0].startswith("FAIL")
print(f"{'PASS' if clean_ok else 'FAIL'} clean Loki records pass the fixed-body check")
print(f"{'PASS' if leak_caught else 'FAIL'} a leaked 'pwd' body in Loki is caught by the fixed-body check")
print(f"SUMMARY loki_body_control: {int(clean_ok) + int(leak_caught)} passed, {2 - int(clean_ok) - int(leak_caught)} failed")
sys.exit(0 if clean_ok and leak_caught else 1)
