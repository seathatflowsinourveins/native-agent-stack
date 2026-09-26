#!/usr/bin/env python3
"""Write one upstream-provenance source review per sweep survivor (network: gh api only; no model calls).

  source_reviews.py --survivors OUT/survivors.json --out evidence/artifacts/<lane> --lane <lane>
                    [--fit-models "Claude Opus 5.5 and GPT-6-Astra"] > OUT/reviews.json

The shape follows evidence/artifacts/landscape-sweep-20260923/*.json: schema_version, id, kind, evidence_class,
repository, reviewed_commit, readme_path, license, layers, claim, observed, documentation_excerpts. A repository
surviving in several layers gets one review listing every layer. Prints [{repository, path, layers}] (make_result.py
--reviews reads it). A repository gh cannot read is reported and skipped (exit 1 after the others are written).
`gh auth status` must already pass.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path


class GhError(RuntimeError):
    pass


def gh(path: str) -> dict:
    done = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise GhError(f"gh api {path}: {done.stderr.strip()[:200]}")
    return json.loads(done.stdout)


def review(repository: str, layers: list, lane: str, fit_models: str) -> dict:
    match = re.search(r"github\.com/([^/]+)/([^/#?]+)", repository)
    if not match:
        raise GhError(f"{repository} is not a GitHub repository URL")
    meta = gh(f"repos/{match.group(1)}/{match.group(2)}")
    full, branch = meta["full_name"], meta["default_branch"]
    commit = gh(f"repos/{full}/commits/{branch}")["sha"]
    license_id = (meta.get("license") or {}).get("spdx_id") or "NOASSERTION"
    excerpts, readme_path = [], None
    try:
        readme = gh(f"repos/{full}/readme?ref={commit}")
        readme_path = readme["path"]
        text = base64.b64decode(readme["content"]).decode("utf-8", "replace")
        paragraphs = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", text)]
        paragraphs = [part for part in paragraphs if len(part) > 60 and not part.startswith(("<", "[![", "![", "|"))]
        excerpts = [{"source": f"{readme_path}@{commit}", "text": part[:500]} for part in paragraphs[:3]]
    except GhError:
        pass
    description = (meta.get("description") or "").strip()
    name = re.sub(r"[^a-z0-9]+", "-", full.lower()).strip("-")
    return {"schema_version": 1, "id": f"source-review-{name}", "kind": "upstream_provenance",
            "evidence_class": "source_review", "repository": f"https://github.com/{full}", "reviewed_commit": commit,
            "readme_path": readme_path, "license": license_id, "layers": sorted(set(layers)),
            "claim": (f"Source and documentation review of {full} at commit {commit} (license {license_id}), read from "
                      f"{readme_path or 'the repository metadata'} at that commit"
                      + (f". Repository description: \"{description}\"." if description else ".")
                      + f" Survived the {lane} facts refuter and both fit refuters ({fit_models}); "
                        "no native install, run or comparison with a winner."),
            "observed": {"stars": meta.get("stargazers_count"), "pushed_at": meta.get("pushed_at"),
                         "archived": meta.get("archived"), "default_branch": branch},
            "documentation_excerpts": excerpts}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--survivors", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--fit-models", default="Claude Opus 5.5 and GPT-6-Astra",
                        help="the two fit refuters' resolved models, as the claim names them")
    args = parser.parse_args(argv)
    survivors = json.loads(args.survivors.read_text(encoding="utf-8"))
    by_repo: dict[str, list] = {}
    for survivor in survivors:
        by_repo.setdefault(survivor["repository"], []).append(survivor["layer_id"])
    args.out.mkdir(parents=True, exist_ok=True)
    written, failed = [], []
    for repository, layers in sorted(by_repo.items()):
        try:
            doc = review(repository, layers, args.lane, args.fit_models)
        except (GhError, KeyError, ValueError) as error:
            failed.append(f"{repository}: {error}")
            continue
        path = args.out / f"{doc['id'][len('source-review-'):]}.json"
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append({"repository": doc["repository"], "path": path.name, "layers": doc["layers"]})
    print(json.dumps(written, indent=1))
    for line in failed:
        print(f"source_reviews.py: {line}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
