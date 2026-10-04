"""Re-verify the eight macOS token-efficiency pins against their official upstream artifacts.

Read-only network: GitHub release metadata/assets (gh api + HTTPS download), the npm registry
(npm view + tarball download), the PyPI JSON API (+ file download) and the GitHub commits/contents
API. Nothing is installed. Prints a plain-text log (stdout) and exits 1 on any mismatch.
Paths in the log are relative to the fetch directory; no host paths are printed.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

PINS = Path(sys.argv[1])  # adoption/pins-macos-arm64.json of the worktree
LINUX_PINS = Path(sys.argv[2])
FETCH = Path(sys.argv[3])
FETCH.mkdir(parents=True, exist_ok=True)

by_id = {tool["id"]: tool for tool in json.loads(PINS.read_text())["tools"]}
linux_by_id = {tool["id"]: tool for tool in json.loads(LINUX_PINS.read_text())["tools"]}
failures: list[str] = []
lines: list[str] = []


def log(text: str = "") -> None:
    lines.append(text)
    print(text, flush=True)


def check(label: str, ok: bool) -> None:
    log(f"  {'MATCH' if ok else 'MISMATCH'}: {label}")
    if not ok:
        failures.append(label)


def run(*argv: str) -> str:
    result = subprocess.run(argv, capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(argv[:3])} ... exited {result.returncode}: {result.stderr.strip()[:300]}")
    return result.stdout


def get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "native-agent-stack-pin-check"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def status(url: str) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": "native-agent-stack-pin-check"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def download(url: str, name: str) -> bytes:
    data = get(url)
    (FETCH / name).write_bytes(data)
    return data


def digests(data: bytes) -> tuple[str, str, str]:
    return (hashlib.sha256(data).hexdigest(),
            "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode(),
            hashlib.sha1(data).hexdigest())


log(f"# macOS token-efficiency pin re-verification, {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
log("# Every download below was fetched fresh into an empty scratch directory for this run.")
log()

# 1. rtk: GitHub release asset, publisher checksums.txt and the API asset digest.
tool = by_id["rtk"]
log(f"## rtk {tool['version']} ({tool['kind']})")
asset = tool["url"].rsplit("/", 1)[-1]
release = json.loads(run("gh", "api", f"repos/rtk-ai/rtk/releases/tags/v{tool['version']}"))
assets = {entry["name"]: entry for entry in release["assets"]}
api_digest = assets[asset].get("digest")
log(f"  gh api repos/rtk-ai/rtk/releases/tags/v{tool['version']}: asset {asset} size={assets[asset]['size']} digest={api_digest}")
checksums = download(assets["checksums.txt"]["browser_download_url"], "rtk-checksums.txt").decode()
checksum_line = next((line for line in checksums.splitlines() if line.split()[-1].lstrip("*") == asset), None)
log(f"  checksums.txt line: {checksum_line}")
data = download(tool["url"], asset)
sha256 = digests(data)[0]
log(f"  downloaded {asset}: {len(data)} bytes, sha256 {sha256}")
check("rtk: computed sha256 == pin", sha256 == tool["sha256"])
check("rtk: checksums.txt line == pin", checksum_line is not None and checksum_line.split()[0] == tool["sha256"])
check("rtk: GitHub API asset digest == pin", api_digest == f"sha256:{tool['sha256']}")
with tarfile.open(FETCH / asset, "r:gz") as archive:
    members = [(member.name, member.isfile(), oct(member.mode & 0o777)) for member in archive.getmembers()]
log(f"  tar -tzf members (name, regular file, mode): {members}")
check("rtk: archive holds exactly one bare 'rtk' regular file", [name for name, _, _ in members] == ["rtk"] and members[0][1])
log()

# 2-5. npm registry tarballs: dist.integrity (sha512), dist.shasum (sha1), the tarball's sha256,
# and the Linux pin's sha256 for the same version.
for tool_id, package in (("qmd", "@tobilu/qmd"), ("repomix", "repomix"), ("toon", "@toon-format/cli"),
                         ("ccusage", "ccusage")):
    tool = by_id[tool_id]
    log(f"## {tool_id} {tool['version']} ({tool['kind']}, npm {package})")
    # The whole version document: `npm view <spec> dist optionalDependencies --json` flattens to
    # the one field that exists when the other is absent.
    meta = json.loads(run("npm", "view", f"{package}@{tool['version']}", "--json"))
    check(f"{tool_id}: registry document is {package}@{tool['version']}",
          (meta.get("name"), meta.get("version")) == (package, tool["version"]))
    dist = meta["dist"]
    log(f"  npm view {package}@{tool['version']} dist.tarball = {dist['tarball']}")
    log(f"  npm view dist.integrity = {dist['integrity']}")
    log(f"  npm view dist.shasum = {dist['shasum']}")
    optional = meta.get("optionalDependencies") or {}
    log(f"  npm view optionalDependencies = {json.dumps(optional, sort_keys=True)}")
    check(f"{tool_id}: pin url == registry dist.tarball", tool["url"] == dist["tarball"])
    data = download(dist["tarball"], dist["tarball"].rsplit("/", 1)[-1])
    sha256, sha512, sha1 = digests(data)
    log(f"  downloaded: {len(data)} bytes, sha256 {sha256}")
    check(f"{tool_id}: computed sha512 == dist.integrity", sha512 == dist["integrity"])
    check(f"{tool_id}: computed sha1 == dist.shasum", sha1 == dist["shasum"])
    check(f"{tool_id}: computed sha256 == pin", sha256 == tool["sha256"])
    check(f"{tool_id}: pin sha512 quoted in checksum_ref == dist.integrity", dist["integrity"] in tool["checksum_ref"])
    linux = linux_by_id[tool_id]
    check(f"{tool_id}: Linux pin is the same version and sha256",
          (linux["version"], linux["sha256"]) == (tool["version"], tool["sha256"]))
    if tool_id == "qmd":
        check("qmd: optionalDependencies has sqlite-vec-darwin-arm64", "sqlite-vec-darwin-arm64" in optional)
        log(f"  sqlite-vec builds listed: {sorted(name for name in optional if name.startswith('sqlite-vec-'))}")
    elif tool_id == "ccusage":
        check("ccusage: optionalDependencies has @ccusage/ccusage-darwin-arm64",
              "@ccusage/ccusage-darwin-arm64" in optional)
        log(f"  native builds listed: {sorted(name for name in optional if name.startswith('@ccusage/ccusage-'))}")
    else:
        check(f"{tool_id}: no optionalDependencies", optional == {})
    log()

# 6-7. PyPI: JSON API digest for the pinned file, plus a fresh download and re-hash.
for tool_id, project in (("headroom", "headroom-ai"), ("markitdown", "markitdown")):
    tool = by_id[tool_id]
    log(f"## {tool_id} {tool['version']} ({tool['kind']}, PyPI {project})")
    meta = json.loads(get(f"https://pypi.org/pypi/{project}/{tool['version']}/json"))
    files = meta["urls"]
    log(f"  https://pypi.org/pypi/{project}/{tool['version']}/json lists {len(files)} files:")
    for entry in files:
        log(f"    {entry['filename']} ({entry['packagetype']}, {entry['size']} bytes) sha256 {entry['digests']['sha256']}")
    filename = tool["url"].rsplit("/", 1)[-1]
    entry = next((entry for entry in files if entry["filename"] == filename), None)
    check(f"{tool_id}: pinned file {filename} is listed", entry is not None)
    if entry is None:
        continue
    check(f"{tool_id}: pin url == PyPI url", entry["url"] == tool["url"])
    check(f"{tool_id}: PyPI digests.sha256 == pin", entry["digests"]["sha256"] == tool["sha256"])
    data = download(entry["url"], filename)
    sha256 = digests(data)[0]
    log(f"  downloaded {filename}: {len(data)} bytes, sha256 {sha256}")
    check(f"{tool_id}: computed sha256 == pin", sha256 == tool["sha256"])
    check(f"{tool_id}: downloaded size == PyPI size", len(data) == entry["size"])
    if tool_id == "headroom":
        mac = [e["filename"] for e in files if "macosx" in e["filename"]]
        log(f"  macOS wheels listed: {mac}")
        check("headroom: the only macOS wheel is the pinned arm64 one", mac == [filename])
        check("headroom: no platform-independent artifact (sdist or py3-none-any wheel)",
              not any(e["packagetype"] == "sdist" or e["filename"].endswith("-none-any.whl") for e in files))
        check("headroom: macOS pin differs from the Linux manylinux pin",
              tool["sha256"] != linux_by_id["headroom"]["sha256"])
        requires = meta["info"].get("requires_python")
        log(f"  info.requires_python = {requires}")
        try:
            from packaging.specifiers import SpecifierSet
        except ImportError:
            log("  (packaging not importable; requires_python not evaluated)")
        else:
            check("headroom: requires_python admits 3.13 (the bootstrap's --python 3.13)",
                  requires is not None and "3.13" in SpecifierSet(requires))
    else:
        wheel = next((e for e in files if e["filename"].endswith("py3-none-any.whl")), None)
        log(f"  wheel uv installs: {wheel['filename'] if wheel else None}")
        if wheel is not None:
            wheel_data = download(wheel["url"], wheel["filename"])
            wheel_sha = digests(wheel_data)[0]
            log(f"  downloaded {wheel['filename']}: {len(wheel_data)} bytes, sha256 {wheel_sha}")
            check("markitdown: wheel re-hash == PyPI digest", wheel_sha == wheel["digests"]["sha256"])
            check("markitdown: wheel sha256 quoted in install_note", wheel_sha in tool["install_note"])
        check("markitdown: Linux pin is the same url and sha256",
              (linux_by_id["markitdown"]["url"], linux_by_id["markitdown"]["sha256"]) == (tool["url"], tool["sha256"]))
    log()

# 8. serena: the pinned commit exists upstream, declares 2.0.0.dev0 as serena-agent, and PyPI has
# no release of that version.
tool = by_id["serena"]
log(f"## serena {tool['version']} ({tool['kind']})")
commit = tool["commit"]
api = json.loads(run("gh", "api", f"repos/oraios/serena/commits/{commit}"))
log(f"  gh api repos/oraios/serena/commits/{commit}: sha={api['sha']} committer.date={api['commit']['committer']['date']}")
check("serena: GitHub commits API returns the pinned commit", api["sha"] == commit)
pyproject = base64.b64decode(json.loads(run("gh", "api", f"repos/oraios/serena/contents/pyproject.toml?ref={commit}"))["content"]).decode()
name_line = next((line.strip() for line in pyproject.splitlines() if line.strip().startswith("name =")), None)
version_line = next((line.strip() for line in pyproject.splitlines() if line.strip().startswith("version =")), None)
log(f"  pyproject.toml at {commit[:12]}: {name_line}; {version_line}")
check("serena: pyproject declares name serena-agent", name_line == 'name = "serena-agent"')
check("serena: pyproject declares version 2.0.0.dev0", version_line == 'version = "2.0.0.dev0"')
code = status("https://pypi.org/pypi/serena-agent/2.0.0.dev0/json")
log(f"  https://pypi.org/pypi/serena-agent/2.0.0.dev0/json -> HTTP {code}")
check("serena: PyPI has no 2.0.0.dev0 release", code == 404)
linux = linux_by_id["serena"]
check("serena: Linux pin is the same commit, package and url",
      (linux["commit"], linux["package"], linux["url"]) == (commit, tool["package"], tool["url"]))
log()

log(f"# result: {'FAIL' if failures else 'PASS'} ({len(failures)} mismatches)")
for failure in failures:
    log(f"#   {failure}")
sys.exit(1 if failures else 0)
