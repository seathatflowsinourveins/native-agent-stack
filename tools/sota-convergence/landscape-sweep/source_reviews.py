#!/usr/bin/env python3
"""Write one upstream-provenance source review per sweep survivor (network: gh api, and the public Hugging Face
Hub API for a model repository; no model calls).

  source_reviews.py --survivors OUT/survivors.json --out evidence/artifacts/<lane> --lane <lane>
                    [--fit-models "Claude Opus 5.5 and GPT-6-Astra"] > OUT/reviews.json

The shape follows evidence/artifacts/landscape-sweep-20260923/*.json: schema_version, id, kind, evidence_class,
repository, reviewed_commit, readme_path, license, layers, claim, observed, documentation_excerpts. A repository
surviving in several layers gets one review listing every layer. Prints [{repository, path, layers}] (make_result.py
--reviews reads it). A review is named <owner>-<repo>.json, lowercased with every other character run as "-", like
the 2026-09-23 reviews; when two repositories share that name (acme/a-b and acme-a/b), each gets a suffix of 10 hex
characters of the sha256 of its owner/repo, so no review overwrites another. A repository gh cannot read, or whose
file name already holds a review of another repository, is reported and skipped (exit 1 after the others are
written). `gh auth status` must already pass.
A Hugging Face model repository (https://huggingface.co/<namespace>/<name>, which a model layer can keep) is reviewed
at the commit of its default revision: the Hub's model-info endpoint /api/models/<repo_id> (the one huggingface_hub's
HfApi.model_info calls) gives the commit, the model card's license and the repository state, and the model card is
read at that commit through the documented "Resolve a file" endpoint /<repo_id>/resolve/<sha>/README.md. Both are
anonymous GETs (no token is read or sent), and the card's YAML metadata block is not excerpted. Its review is named
hf-<namespace>-<name>.json.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sweep_common import slug  # noqa: E402

OWNER_REPO = re.compile(r"[a-z0-9-]+/[a-z0-9._-]+")
HUB = "https://huggingface.co"
HUB_MODEL = re.compile(r"https://huggingface\.co/([A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*)/?")
# First path segments that are Hub sections, never a model repository's namespace.
HUB_SECTIONS = {"api", "blog", "buckets", "collections", "containers", "datasets", "docs", "models", "organizations",
                "papers", "settings", "spaces"}
HUB_DEFAULT_REVISION = "main"  # huggingface_hub constants.DEFAULT_REVISION
HEX40 = re.compile(r"[0-9a-f]{40}")


class GhError(RuntimeError):
    pass


class HubError(GhError):
    """The Hugging Face Hub could not answer (reported and skipped like a repository gh cannot read)."""


def gh(path: str) -> dict:
    done = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise GhError(f"gh api {path}: {done.stderr.strip()[:200]}")
    return json.loads(done.stdout)


def hub_get(path: str, text: bool = False):
    """An anonymous GET of a public Hugging Face Hub path: parsed JSON, or the body as text."""
    request = urllib.request.Request(f"{HUB}/{path}", headers={"User-Agent": "native-agent-stack source_reviews.py"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
        return body.decode("utf-8", "replace") if text else json.loads(body)
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise HubError(f"GET {HUB}/{path}: {error}") from None


def hub_model(repository: str) -> str | None:
    """<namespace>/<name> of a Hugging Face model repository URL, else None."""
    match = HUB_MODEL.fullmatch(str(repository or "").strip())
    if match and match.group(1).split("/", 1)[0].lower() not in HUB_SECTIONS:
        return match.group(1)
    return None


def excerpts_from(text: str, source: str) -> list:
    """The first three prose paragraphs of a README (badges, tables and HTML skipped), each cut at 500 characters."""
    paragraphs = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", text)]
    paragraphs = [part for part in paragraphs if len(part) > 60 and not part.startswith(("<", "[![", "![", "|"))]
    return [{"source": source, "text": part[:500]} for part in paragraphs[:3]]


def hub_license(meta: dict) -> str:
    """The model card's license (cardData.license, else a license:<id> tag); "other" keeps the card's license_name."""
    card = meta.get("cardData") if isinstance(meta.get("cardData"), dict) else {}
    value = card.get("license")
    if isinstance(value, list):
        value = " OR ".join(str(item) for item in value if item)
    if not value:
        tags = [tag[len("license:"):] for tag in meta.get("tags") or [] if isinstance(tag, str)
                and tag.startswith("license:")]
        value = tags[0] if tags else "NOASSERTION"
    if value == "other" and isinstance(card.get("license_name"), str) and card["license_name"]:
        value = f"other ({card['license_name']})"
    return str(value)


def hub_review(repo_id: str, layers: list, lane: str, fit_models: str) -> dict:
    meta = hub_get(f"api/models/{urllib.parse.quote(repo_id, safe='/')}")
    full, commit = meta.get("id") or repo_id, meta.get("sha")
    if not (isinstance(full, str) and isinstance(commit, str) and HEX40.fullmatch(commit)):
        raise HubError(f"{HUB}/{repo_id}: the Hub reported no model id and commit")
    license_id = hub_license(meta)
    excerpts, readme_path = [], None
    try:
        card = hub_get(f"{urllib.parse.quote(full, safe='/')}/resolve/{commit}/README.md", text=True)
        readme_path = "README.md"
        if card.startswith("---"):  # the model card's YAML metadata block
            end = card.find("\n---", 3)
            card = card[end + 4:] if end >= 0 else card
        excerpts = excerpts_from(card, f"{readme_path}@{commit}")
    except HubError:
        pass
    return {"schema_version": 1, "id": f"source-review-hf-{review_name(full)}", "kind": "upstream_provenance",
            "evidence_class": "source_review", "repository": f"{HUB}/{full}", "reviewed_commit": commit,
            "readme_path": readme_path, "license": license_id, "layers": sorted(set(layers)),
            "claim": (f"Source and documentation review of the Hugging Face model repository {full} at commit {commit} "
                      f"(license {license_id}, as its model card declares it), read from "
                      f"{readme_path or 'the repository metadata'} at that commit. Survived the {lane} facts refuter "
                      f"and both fit refuters ({fit_models}); no native install, run or comparison with a winner."),
            "observed": {"likes": meta.get("likes"), "last_modified": meta.get("lastModified"),
                         "gated": meta.get("gated"), "disabled": meta.get("disabled"),
                         "default_branch": HUB_DEFAULT_REVISION},
            "documentation_excerpts": excerpts}


def review_name(full_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", full_name.lower()).strip("-")


def unique_stems(names: dict) -> dict:
    """owner/repo -> file stem: its readable name, or, for a name two repositories share, that name plus 10 hex
    characters of the sha256 of the owner/repo."""
    groups: dict[str, list] = {}
    for key, name in names.items():
        groups.setdefault(name, []).append(key)
    stems = {key: name if len(groups[name]) == 1 else f"{name}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:10]}"
             for key, name in names.items()}
    if len(set(stems.values())) != len(stems):
        raise ValueError(f"review file names still collide: {sorted(stems.values())}")
    return stems


def review(repository: str, layers: list, lane: str, fit_models: str) -> dict:
    repo_id = hub_model(repository)
    if repo_id:
        return hub_review(repo_id, layers, lane, fit_models)
    owner_repo = slug(repository)
    if not OWNER_REPO.fullmatch(owner_repo):
        raise GhError(f"{repository} is neither a GitHub repository nor a Hugging Face model repository URL")
    meta = gh(f"repos/{owner_repo}")
    full, branch = meta["full_name"], meta["default_branch"]
    commit = gh(f"repos/{full}/commits/{branch}")["sha"]
    license_id = (meta.get("license") or {}).get("spdx_id") or "NOASSERTION"
    excerpts, readme_path = [], None
    try:
        readme = gh(f"repos/{full}/readme?ref={commit}")
        readme_path = readme["path"]
        text = base64.b64decode(readme["content"]).decode("utf-8", "replace")
        excerpts = excerpts_from(text, f"{readme_path}@{commit}")
    except GhError:
        pass
    description = (meta.get("description") or "").strip()
    return {"schema_version": 1, "id": f"source-review-{review_name(full)}", "kind": "upstream_provenance",
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
    by_repo: dict[str, dict] = {}  # owner/repo -> the survivor URL first seen and every layer it survived in
    for survivor in survivors:
        item = by_repo.setdefault(slug(survivor["repository"]), {"repository": survivor["repository"], "layers": []})
        item["layers"].append(survivor["layer_id"])
    written, failed, docs = [], [], {}
    for key, item in sorted(by_repo.items()):
        try:
            docs[key] = review(item["repository"], item["layers"], args.lane, args.fit_models)
        except (GhError, KeyError, ValueError) as error:
            failed.append(f"{item['repository']}: {error}")
    try:
        stems = unique_stems({key: doc["id"][len("source-review-"):] for key, doc in docs.items()})
    except ValueError as error:
        print(f"source_reviews.py: {error}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    for key, doc in sorted(docs.items()):
        doc["id"] = f"source-review-{stems[key]}"
        path = args.out / f"{stems[key]}.json"
        if path.is_file():
            try:
                previous = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                previous = None
            reviewed = previous.get("repository", "") if isinstance(previous, dict) else ""
            if str(reviewed).lower().rstrip("/") != doc["repository"].lower():
                failed.append(f"{by_repo[key]['repository']}: {path} already holds a review of another repository; "
                              "not overwritten")
                continue
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append({"repository": doc["repository"], "path": path.name, "layers": doc["layers"]})
    print(json.dumps(written, indent=1))
    for line in failed:
        print(f"source_reviews.py: {line}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
