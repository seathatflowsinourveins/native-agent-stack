#!/usr/bin/env python3
"""Skeleton of the ranked catalog index: the API names only, for the fail-first run of its contract tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from . import component_matrix
except ImportError:  # running as a plain script, not a package
    import component_matrix


FROZEN_AT = "2026-09-29"
OUTPUT_JSON = "catalogs/landscape/catalog-index.json"
LISTING_INPUT = "catalogs/**/*.json + manifests/*.json"
EXPECTED_LAYER_COUNT = 32
SIZE_WARN_BYTES = 1_500_000
SIZE_LIMIT_BYTES = 2_000_000
RULE: dict = {"frozen_at": FROZEN_AT}


class InvalidIndex(ValueError):
    pass


def evidence_tier(field, recorded, retained_local_result=False):
    return "U"


def has_retained_local_result(evidence_refs):
    return False


def verification_level(role, state):
    return 0


def sort_key(placement):
    return [0, 0, 0, 0]


def positions(keys):
    return [(1, False) for _key in keys]


def comparability_key(measurement):
    return ""


def measured_split(members, measurements, *, layer, metric):
    return {member: {"group": None, "rank": 0, "basis": ""} for member in members}


def rank_layer(placements, measurements, *, layer, metric):
    return placements


def load_measurements(reader):
    return []


def build_document(root):
    return {"schema_version": 1, "id": "catalog-index", "scope": "", "universal_superiority": "", "rule": {},
            "inputs": [], "counts": {"placements": {}, "conservation": {}, "status_items": {}, "coverage": {},
                                     "overturn_metrics": {}},
            "layers": [], "entities": [], "evidence": {"receipts_unattached": [], "experiments": []},
            "unresolved": [], "status_items": [], "coverage": {"catalog_files": [], "unmodeled_collections": []},
            "measurements": []}


def check_document(document):
    return None


def serialize(document):
    return component_matrix.serialize(document)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.parse_args(argv)
    print(json.dumps({"status": "not_implemented"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
