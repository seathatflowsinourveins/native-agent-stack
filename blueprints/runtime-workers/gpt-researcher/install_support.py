"""Hash verification/extraction glue for the upstream native source recipe.

References: pinned pyproject.toml PEP 517 backend, PyPI JSON digests,
https://docs.python.org/3.12/library/tarfile.html#extraction-filters .
"""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import urllib.request


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def extract(artifact, archive, source):
    if not archive.exists() or digest(archive) != artifact["sha256"]:
        temporary = archive.with_suffix(".download")
        with urllib.request.urlopen(artifact["url"], timeout=120) as response, temporary.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        if digest(temporary) != artifact["sha256"]:
            raise SystemExit("source archive checksum mismatch")
        temporary.replace(archive)
    source.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Re-extract verified immutable bytes on every run; do not trust a stale source tree.
    with tarfile.open(archive) as bundle:
        if any(member.issym() or member.islnk() for member in bundle.getmembers()):
            raise SystemExit("source archive contains unsupported links")
        bundle.extractall(source, filter="data")


def main():
    recipe, prefix, state = map(Path, sys.argv[1:])
    pins = json.loads((recipe / "pins.json").read_text())
    for name, expected in pins["locks"].items():
        if digest(recipe / name) != expected:
            raise SystemExit("lock checksum mismatch: " + name)
    source = prefix / "source"
    extract(pins["source_archive"], state / "downloads/source.tar.gz", source)
    project = source / ("gpt-researcher-" + pins["commit"])
    for name, expected in pins["upstream_files"].items():
        if digest(project / name) != expected:
            raise SystemExit("upstream file checksum mismatch: " + name)
    grader = pins["grader"]
    source = prefix / "grader-source"
    extract(grader["source_archive"], state / "downloads/grader-source.tar.gz", source)
    project = source / ("DeepResearch-Bench-II-" + grader["commit"])
    for name, expected in grader["files"].items():
        if digest(project / name) != expected:
            raise SystemExit("upstream grader checksum mismatch: " + name)


if __name__ == "__main__":
    main()
