#!/usr/bin/env python3
"""What the review's symlink rule changes on the skills catalog's GitHub sources at their pins: for each source, the
symlinks in its git tree, the search locations at or below one, the SKILL.md symlinks, and for every folder name the
resolver finds in a search location, its pick with the rule (source_reviews.location_doubt and the plugin-manifest
doubt) and without it (the round-4 resolver). Each SKILL.md counts as valid and named after its folder, as
cli_skill_dir assumes without a reader; the manifests are read from the fetched objects.

  symlink_impact.py <checkout> <git work dir of corpus.py> > symlinks.json
"""

import collections
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

CHECKOUT, ROOT = Path(sys.argv[1]), Path(sys.argv[2])
HARNESS = CHECKOUT / "tools" / "sota-convergence" / "landscape-sweep"
sys.path.insert(0, str(HARNESS))
spec = importlib.util.spec_from_file_location("source_reviews", HARNESS / "source_reviews.py")
source_reviews = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source_reviews)
ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "HOME": str(ROOT / "home"),
       "PATH": os.environ.get("PATH", "/usr/bin:/bin")}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, env=ENV, check=True).stdout


catalog = json.loads((CHECKOUT / "catalogs" / "landscape" / "skills-lifecycle.json").read_text(encoding="utf-8"))
rows, totals = [], collections.Counter()
for source in catalog["sources"]:
    url, pin = source["url"], source.get("pin") or ""
    if not url.startswith("https://github.com/") or len(pin) != 40:
        continue
    full = url[len("https://github.com/"):]
    repo = ROOT / full.replace("/", "__")
    entries = {}
    for record in git(repo, "ls-tree", "-r", "-z", pin).decode("utf-8", "surrogateescape").split("\0"):
        if record:
            meta, path = record.split("\t", 1)
            mode, kind, sha = meta.split()
            entries[path] = {"mode": mode, "type": kind, "sha": sha}
    blobs = {path for path, entry in entries.items() if entry["type"] == "blob"}
    skill_dirs = {path[:-len("/SKILL.md")] for path in blobs if path.endswith("/SKILL.md")}
    symlinks = {path for path, entry in entries.items() if entry["mode"] == "120000"}
    linked = {path[:-len("/SKILL.md")] for path in symlinks if path.endswith("/SKILL.md")}
    # As source_reviews.plugin_manifests: a symlinked .claude-plugin, or a manifest that is not a regular file, leaves
    # the plugin folders unknown.
    manifests, plugin_doubt = [], ("a symlinked .claude-plugin"
                                   if source_reviews.symlink_at_or_above(".claude-plugin", symlinks) else None)
    for path in source_reviews.PLUGIN_MANIFESTS:
        entry = entries.get(path)
        if entry and entry["type"] == "blob" and entry["mode"] not in source_reviews.REGULAR_FILE_MODES:
            plugin_doubt = plugin_doubt or f"{path} is not a regular file"
        try:
            manifests.append(json.loads(git(repo, "cat-file", "blob", entry["sha"]))
                             if entry and entry["mode"] in source_reviews.REGULAR_FILE_MODES else None)
        except ValueError:
            manifests.append(None)
    plugin_dirs = source_reviews.cli_plugin_dirs(*manifests)
    locations = source_reviews.cli_locations(skill_dirs, plugin_dirs)
    names = sorted({folder.rsplit("/", 1)[-1] for *_, found in locations for folder in found})
    counts = collections.Counter()
    for name in names:
        before = source_reviews.cli_skill_dir(skill_dirs, name, plugin_dirs)[0]
        try:
            after = source_reviews.cli_skill_dir(
                skill_dirs, name, plugin_dirs, plugin_doubt=plugin_doubt,
                doubt=lambda container, depth: source_reviews.location_doubt(container, depth, skill_dirs, symlinks,
                                                                             linked))[0]
            outcome = "same pick" if after == before else "another pick"
        except source_reviews.LocationUnverified:
            outcome = "stopped by the rule"
        counts[outcome if before else "no pick either way" if outcome == "same pick" else outcome] += 1
    symlinked = sorted({container for container, *_ in locations
                        if container and source_reviews.symlink_at_or_above(container, symlinks)})
    rows.append({"source": f"{full}@{pin[:12]}", "symlinks": len(symlinks), "symlinked_search_locations": symlinked,
                 "skill_md_symlinks": len(linked), "plugin_manifests_unknown": bool(plugin_doubt),
                 "names": len(names), "outcomes": dict(sorted(counts.items()))})
    totals.update(counts)
print(json.dumps({"sources": rows, "totals": dict(sorted(totals.items())),
                  "sources_with_a_symlinked_search_location": sum(bool(row["symlinked_search_locations"]) for row in rows),
                  "sources_with_a_skill_md_symlink": sum(bool(row["skill_md_symlinks"]) for row in rows)}, indent=1))
