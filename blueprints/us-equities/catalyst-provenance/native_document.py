#!/usr/bin/env python3
"""Native EdgarTools local parsing of one pinned historical upstream 8-K fixture."""
import argparse
from datetime import timedelta
import importlib.metadata
import json
from pathlib import Path

from catalyst import eligible_at, iso, json_bytes, parse_header, sha, timestamp, write_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    source = json.loads((base / "upstream-8k-source.json").read_text())
    stored = (base / "upstream-8k.html").read_bytes()
    if sha(stored) != source["vendored_file"]["sha256"]:
        raise ValueError("vendored_fixture_hash_mismatch")
    raw = stored[:-1]
    if len(raw) != source["bytes"] or sha(raw) != source["sha256"]:
        raise ValueError("upstream_fixture_hash_mismatch")
    from edgar.documents import HTMLParser
    document = HTMLParser().parse(raw)
    markdown = document.to_markdown()
    event = parse_header(raw, {"accession": source["accession_from_upstream_path"],
                              "form": source["form_from_upstream_path"], "cik": None,
                              "filed_date": None}, source["first_local_observed_at"])
    receipt = {"schema_version": 1, "status": "complete", "mode": "real_upstream_fixture_offline",
               "edgartools": importlib.metadata.version("edgartools"),
               "native_api": "edgar.documents.HTMLParser().parse(raw).to_markdown()",
               "source": source, "native_markdown_bytes": len(markdown.encode()),
               "native_markdown_sha256": sha(markdown.encode()), "temporal_gate": event,
               "eligible_before_first_observation": eligible_at(event, iso(timestamp(source["first_local_observed_at"]) - timedelta(seconds=1))),
               "eligible_after_first_observation": eligible_at(event, source["first_local_observed_at"]),
               "sec_network_requests": 0, "historical_point_in_time": False,
               "limitations": ["Fixture lineage is pinned upstream test data, not a fresh SEC response.",
                               "No SGML acceptance header exists; all trading cutoffs remain quarantined.",
                               "Text conversion and byte counts do not measure model token savings or strategy quality."]}
    write_new(args.out, json_bytes(receipt))
    write_new(args.out.with_suffix(".md"), markdown.encode())
    print(json.dumps({key: receipt[key] for key in ["status", "mode", "edgartools", "native_markdown_bytes", "eligible_before_first_observation", "eligible_after_first_observation", "sec_network_requests"]}))


if __name__ == "__main__":
    main()
