#!/usr/bin/env python3
"""Synthetic-only harness regression; no sockets, private captures or native acceptance.

Uses replay.py's existing synthetic_batches and design reference expected_derived
at the post/load/assert seams. HTTP is stubbed and exporter bytes come from that
reference, so GREEN proves harness control flow only, not Collector/Loki behavior.
Usage: python synthetic_replay_control.py WORK_DIR
"""
import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

HERE = Path(__file__).resolve().parent
REPLAY = HERE.parent / "scratch-replay/replay.py"
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("replay", REPLAY)
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)

work = Path(sys.argv[1])
work.mkdir(parents=True, exist_ok=True)
empty = work / "empty-capture.json"
empty.write_text("")
tags_path = work / "tags.json"
out_path = work / "reference-output.jsonl"
collector = REPO / "observability/collector/collector.yaml"
now = 1_800_000_000_000_000_000
posted = []


def accept(request, **kwargs):
    posted.append(json.loads(request.data))
    response = MagicMock()
    response.__enter__.return_value.status = 200
    return response


post_ok = False
try:
    with patch.object(replay.time, "time_ns", return_value=now), \
            patch.object(replay.urllib.request, "urlopen", side_effect=accept):
        replay.post(SimpleNamespace(port=45700, task_id=None, tags=str(tags_path),
                                    synthetic=True, inputs=[str(empty)]))
    sent = [record for doc in posted for rl in doc["resourceLogs"]
            for sl in rl["scopeLogs"] for record in sl["logRecords"]]
    post_ok = len(sent) == 31 and all(now - 120_000_000_000 <= int(r["timeUnixNano"]) <= now for r in sent)
    print(f"{'PASS' if post_ok else 'FAIL'} empty-capture post uses a recent default timestamp: records={len(sent)}")
except ValueError as error:
    print(f"FAIL empty-capture post: {type(error).__name__}: {error}")

# Independent of post success: expose the downstream unconditional historical
# assertions even when the old post fails before making its first request.
resource_allow, log_allow = replay.staged_allowlists(collector)
tags, output = {}, []
for line_no, source in enumerate(replay.synthetic_batches(now)):
    doc = copy.deepcopy(source)
    n = 0
    for rl in doc["resourceLogs"]:
        resource = replay.attrs(rl["resource"]["attributes"])
        rl["resource"]["attributes"] = [{"key": k, "value": replay.to_otlp_value(v)}
                                         for k, v in resource.items() if k in resource_allow]
        for sl in rl["scopeLogs"]:
            sl["scope"] = {"name": "native-agent-telemetry"}
            for record in sl["logRecords"]:
                tag = f"u6s-{line_no}-{n}"
                n += 1
                tags[tag] = "u6s"
                original = replay.attrs(record["attributes"])
                final = {k: v for k, v in original.items()
                         if k in log_allow and k not in replay.DERIVED_KEYS}
                final.update(replay.expected_derived(original, resource))
                final["receipt_id"] = tag
                record["attributes"] = [{"key": k, "value": replay.to_otlp_value(v)} for k, v in final.items()]
                record["body"] = {"stringValue": "[content omitted]"}
    output.append(json.dumps(doc))
tags_path.write_text(json.dumps(tags))
out_path.write_text("\n".join(output) + "\n")
replay.results.update({"pass": 0, "fail": 0})
replay.run_assertions(SimpleNamespace(out=str(out_path), tags=str(tags_path), collector=str(collector),
                                     inputs=[str(empty)]))
print(f"SUMMARY synthetic_replay_control (stub transport, reference export): "
      f"{replay.results['pass'] + int(post_ok)} passed, {replay.results['fail'] + int(not post_ok)} failed")
sys.exit(0 if post_ok and not replay.results["fail"] else 1)
