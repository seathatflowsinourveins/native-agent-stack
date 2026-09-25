#!/usr/bin/env python3
"""Real, scoped native-tool fixtures; no providers, account reads or model commands.

Only sanitized fixture outputs survive cleanup. --install uses upstream commands
in a new temporary prefix; omission reuses explicit installed executables.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tarfile
import tempfile
import time
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PINS = {"rtk": "0.49.0", "qmd": "2.8.3", "repomix": "1.18.1", "toon": "4.1.1"}
PACKAGES = {"qmd": "@tobilu/qmd", "repomix": "repomix", "toon": "@toon-format/cli"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def signal_group(process: subprocess.Popen, signum: int) -> None:
    """Signal a timed-out command's process group unless it has already finished.

    The group can finish between the timeout and the signal: Linux then reports ESRCH once it is
    reaped, and macOS reports EPERM while its members are unreaped zombies (XNU killpg1 skips
    them). EPERM while the leader still runs is a real refusal and is raised."""
    try:
        os.killpg(process.pid, signum)
    except ProcessLookupError:
        pass
    except PermissionError:
        if process.poll() is None:
            raise


def verify_archive(archive: Path, checksums: str) -> None:
    matches = [line.split()[0] for line in checksums.splitlines()
               if len(line.split()) == 2 and line.split()[1].lstrip("*") == archive.name]
    require(len(matches) == 1, "Publisher checksums must contain the exact asset once")
    require(re.fullmatch(r"[0-9a-fA-F]{64}", matches[0]) is not None,
            "Publisher checksum is not SHA-256")
    require(digest(archive.read_bytes()) == matches[0].lower(), "Archive checksum mismatch")
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            path = Path(member.name)
            require(not path.is_absolute() and ".." not in path.parts
                    and (member.isfile() or member.isdir()), "Unsafe archive member")


def verify_pack(xml: str, originals: dict[str, str]) -> None:
    files = ET.fromstring(xml).findall(".//file")
    require(len(files) == len(originals), "Pack has missing or extra files")
    actual = {item.attrib.get("path"): item.text or "" for item in files}
    require(set(actual) == set(originals), "Pack file selection differs from the explicit inputs")
    for path, content in originals.items():
        # XML wrapper newlines are formatting; every source character within them matters.
        require(actual[path].strip("\n") == content.strip("\n"),
                f"Packed source differs: {path}")


def verify_qmd_document(response: str, uri: str, docid: str, body: str) -> None:
    # Pinned `get --no-line-numbers` framing: canonical URI/docid, separator,
    # then the original body plus console.log's one terminating newline.
    canonical_uri = uri.partition("?")[0]
    require(re.fullmatch(r"#[0-9a-f]+", docid) is not None, "QMD search docid is malformed")
    expected = f"{canonical_uri}  {docid}\n---\n\n{body}\n"
    require(response == expected, "QMD document identity/body differs from source")


def verify_json_roundtrip(original: str, recovered: str) -> None:
    # Preserve JSON types, including bool versus int, while ignoring object key order.
    def canonical(value: str) -> str:
        return json.dumps(json.loads(value), sort_keys=True, ensure_ascii=False)
    require(canonical(original) == canonical(recovered), "Decoded JSON values/types differ")


class Run:
    def __init__(self, output: Path, work: Path):
        self.output, self.work = output, work
        self.tools: dict[str, str] = {}
        self.report = {
            "schema_version": 1, "kind": "native_cli_e2e",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "pins": PINS, "status": "running", "commands": [], "checks": [],
            "failures": [], "artifacts": {},
            "scope": "Fresh Linux fixture state; selected upstream CLIs, no native model task",
            "limits": ["Not a new-PC, native Codex/Claude, GPU or provider acceptance",
                       "Top-level package pins; npm transitive ranges resolve at installation",
                       "RTK counters are fixture-local estimates, not provider savings",
                       "No token-saving requirement: fidelity may need the larger representation",
                       "Retained text replaces local paths; raw byte hashes precede sanitization"],
        }
        # A fresh allowlist excludes tokens, provider routing and inherited tool-state overrides.
        self.env = {key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ}
        self.env.update({
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC", "TERM": "dumb",
            "CI": "true", "NO_COLOR": "1", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
            "XDG_CONFIG_HOME": str(work / "config"), "XDG_CACHE_HOME": str(work / "cache"),
            "XDG_DATA_HOME": str(work / "data"), "XDG_STATE_HOME": str(work / "state"),
            "TMPDIR": str(work / "tmp"), "RTK_DB_PATH": str(work / "data/rtk/history.db"),
            "RTK_TELEMETRY_DISABLED": "1",
            "QMD_CONFIG_DIR": str(work / "config/qmd"), "QMD_FORCE_CPU": "1",
            "INDEX_PATH": str(work / "cache/qmd/native-ci-docs.sqlite"),
            "NODE_LLAMA_CPP_SKIP_DOWNLOAD": "true",
            "NPM_CONFIG_CACHE": str(work / "npm-cache"),
            "NPM_CONFIG_USERCONFIG": str(work / "empty.npmrc"),
            "NPM_CONFIG_GLOBALCONFIG": str(work / "empty-global.npmrc"),
        })
        for folder in ("config", "cache/qmd", "data/rtk", "state", "tmp", "config/qmd", "install"):
            (work / folder).mkdir(parents=True, exist_ok=True)
        (work / "empty.npmrc").write_text("")
        (work / "empty-global.npmrc").write_text("")
        self.report["environment"] = {key: self.clean(value) for key, value in self.env.items()
                                      if key not in {"HOME", "PATH"}}
        self.report["native_home_preserved"] = self.env.get("HOME") == os.environ.get("HOME")
        self.report["source_sha256"] = {
            name: digest((ROOT / name).read_bytes()) for name in (
                "scripts/native_token_ci.py", ".github/workflows/native-token-e2e.yml",
                "manifests/stack.json", "fixtures/rag-note.md", "fixtures/records.json",
                "fixtures/before.py", "fixtures/after.py")
        }
        self.flush()

    def clean(self, value: str) -> str:
        replacements = [(str(self.work), "<WORK>"), (str(ROOT), "<CHECKOUT>"),
                        (str(self.output), "<RESULTS>")]
        replacements += [(path, f"<TOOL:{name}>") for name, path in self.tools.items()]
        if os.environ.get("HOME"):
            replacements.append((os.environ["HOME"], "<NATIVE_HOME>"))
        for source, target in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
            value = value.replace(source, target)
        return value

    def flush(self) -> None:
        (self.output / "receipt.json").write_text(json.dumps(self.report, indent=2) + "\n")

    def command(self, label: str, argv: list[str], cwd: Path | None = None,
                nonzero: bool = False, timeout: int = 90) -> str:
        start = time.monotonic()
        timed_out = False
        process = subprocess.Popen(argv, cwd=cwd or self.work, env=self.env,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            signal_group(process, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                signal_group(process, signal.SIGKILL)
                stdout, stderr = process.communicate()
        entry = {"label": label, "argv": [self.clean(arg) for arg in argv],
                 "cwd": self.clean(str(cwd or self.work)), "exit_code": process.returncode,
                 "expected_exit": "nonzero" if nonzero else "zero", "timed_out": timed_out,
                 "elapsed_seconds": round(time.monotonic() - start, 3),
                 "stdout_raw_sha256": digest(stdout), "stderr_raw_sha256": digest(stderr),
                 "stdout": self.clean(stdout.decode("utf-8", errors="replace")),
                 "stderr": self.clean(stderr.decode("utf-8", errors="replace"))}
        self.report["commands"].append(entry)
        self.flush()
        require(not timed_out, f"{label}: timed out")
        require((process.returncode != 0) if nonzero else (process.returncode == 0),
                f"{label}: unexpected exit {process.returncode}")
        return stdout.decode("utf-8")

    def check(self, label: str, condition: bool) -> None:
        self.report["checks"].append({"label": label, "passed": bool(condition)})
        self.flush()
        require(condition, label)

    def artifact(self, name: str, source: Path) -> None:
        raw = source.read_bytes()
        public = self.clean(raw.decode("utf-8")).encode()
        (self.output / name).write_bytes(public)
        self.report["artifacts"][name] = {"raw_sha256": digest(raw),
                                           "retained_sha256": digest(public)}

    def install(self, name: str) -> str:
        prefix = self.work / "install" / name
        prefix.mkdir()
        if name in PACKAGES:
            self.command(f"install-{name}", ["npm", "install", "--global", "--prefix",
                         str(prefix), "--registry=https://registry.npmjs.org", "--no-audit",
                         "--no-fund", f"{PACKAGES[name]}@{PINS[name]}"], timeout=360)
            self.command(f"installed-metadata-{name}", ["npm", "list", "--global", "--prefix",
                         str(prefix), "--depth=0", "--json"])
            return str(prefix / "bin" / name)
        asset = "rtk-x86_64-unknown-linux-musl.tar.gz"
        base = f"https://github.com/rtk-ai/rtk/releases/download/v{PINS[name]}"
        for filename in (asset, "checksums.txt"):
            self.command(f"download-{filename}", ["curl", "--disable", "--fail", "--silent", "--show-error",
                         "--location", "--output", str(prefix / filename), f"{base}/{filename}"])
        archive = prefix / asset
        checksums = (prefix / "checksums.txt").read_text()
        verify_archive(archive, checksums)
        self.report["rtk_archive_sha256"] = digest(archive.read_bytes())
        self.command("rtk-publisher-checksum", ["sha256sum", "--check", "--ignore-missing",
                                               "checksums.txt"], cwd=prefix)
        self.command("rtk-archive-members", ["tar", "-tf", asset], cwd=prefix)
        self.command("rtk-extract", ["tar", "-xf", asset], cwd=prefix)
        return str(prefix / "rtk")


def rtk_fixture(run: Run) -> None:
    repo = run.work / "git-fixture"
    repo.mkdir()
    run.command("git-init", ["git", "init", "--quiet"], repo)
    for key, value in (("user.name", "Native CI Fixture"), ("user.email", "ci@example.invalid")):
        run.command(f"git-{key}", ["git", "config", key, value], repo)
    for number, message in enumerate(("CI_BASELINE_FIXED", "CI_FOLLOWUP_FIXED")):
        (repo / "selected.txt").write_text(f"public fixture revision {number}\n")
        run.command(f"git-add-{number}", ["git", "add", "selected.txt"], repo)
        run.command(f"git-commit-{number}", ["git", "commit", "--quiet", "-m", message], repo)
    tool = run.tools["rtk"]
    before = json.loads(run.command("rtk-gain-before", [tool, "gain", "--format", "json"], repo))
    run.check("rtk-fixture-ledger-starts-empty", before["summary"]["total_commands"] == 0)
    baseline = run.command("git-log-baseline", ["git", "log", "-2"], repo)
    compact = run.command("rtk-git-log", [tool, "git", "log", "-2"], repo)
    run.check("rtk-preserves-both-commit-subjects",
              all(message in compact for message in ("CI_BASELINE_FIXED", "CI_FOLLOWUP_FIXED")))
    recovered = run.command("rtk-raw-recovery", [tool, "proxy", "git", "log", "-2"], repo)
    run.check("rtk-proxy-exact-stdout", recovered == baseline)
    run.command("rtk-upstream-error", [tool, "proxy", "git", "rev-parse", "--verify",
                                     "refs/heads/ci-missing-ref"], repo, nonzero=True)
    after = json.loads(run.command("rtk-gain-after", [tool, "gain", "--format", "json"], repo))
    run.check("rtk-retained-fixture-database", Path(run.env["RTK_DB_PATH"]).is_file())
    run.check("rtk-native-statistics-returned", isinstance(after, dict) and bool(after))
    run.check("rtk-three-command-counter-increment", after["summary"]["total_commands"] == 3)


def qmd_fixture(run: Run) -> None:
    docs = run.work / "docs-fixture"
    docs.mkdir()
    original = (ROOT / "fixtures/rag-note.md").read_text()
    source = docs / "rag-note.md"
    source.write_text(original)
    cli = [run.tools["qmd"], "--index", "native-ci-docs"]
    run.command("qmd-collection-add", cli + ["collection", "add", str(docs), "--name",
                                           "native-ci-docs", "--mask", "*.md"])
    found = json.loads(run.command("qmd-bm25-search", cli + ["search", "Nemotron", "-c",
                                        "native-ci-docs", "-n", "1", "--json"]))
    require(isinstance(found, list) and len(found) == 1, "QMD search must return one fixture")
    uri = found[0]["file"]
    run.check("qmd-returned-fixture-uri",
              uri == "qmd://native-ci-docs/rag-note.md?index=native-ci-docs")
    first = run.command("qmd-get-fresh-process", cli + ["get", uri, "--no-line-numbers"])
    verify_qmd_document(first, uri, found[0]["docid"], original)
    run.check("qmd-reopened-exact-document-content", True)
    updated = original + "\nAmberquartz persistence marker: 19.\n"
    source.write_text(updated)
    run.command("qmd-update", cli + ["update"])
    found = json.loads(run.command("qmd-search-updated-document", cli + ["search", "Amberquartz",
                                      "-c", "native-ci-docs", "-n", "1", "--json"]))
    run.check("qmd-updated-search-source", len(found) == 1 and found[0]["file"] == uri)
    fresh = run.command("qmd-get-updated-fresh-process", cli + ["get", uri, "--no-line-numbers"])
    verify_qmd_document(fresh, uri, found[0]["docid"], updated)
    run.check("qmd-update-content-fidelity", True)
    run.command("qmd-status", cli + ["status"])
    run.command("qmd-remove-owned-collection", cli + ["collection", "remove", "native-ci-docs"])
    run.check("qmd-no-model-files", not any(run.work.rglob("*.gguf")))
    run.artifact("qmd-input.md", source)


def repomix_fixture(run: Run) -> None:
    inputs = run.work / "pack-fixture"
    inputs.mkdir()
    originals = {}
    for name in ("before.py", "after.py"):
        originals[name] = (ROOT / "fixtures" / name).read_text()
        (inputs / name).write_text(originals[name])
    (inputs / "unselected.txt").write_text("DO_NOT_PACK_CI_UNSELECTED\n")
    config = run.work / "repomix.config.json"
    config.write_text("{}\n")
    packed = run.work / "selected.xml"
    base = [run.tools["repomix"], str(inputs), "--config", str(config), "--include",
            "before.py,after.py", "--style", "xml", "--parsable-style",
            "--token-count-encoding", "o200k_base", "--no-file-summary", "--no-directory-structure"]
    run.command("repomix-selected-originals", base + ["--output", str(packed)])
    verify_pack(packed.read_text(), originals)
    run.check("repomix-source-fidelity-and-selection", True)
    run.artifact("repomix-originals.xml", packed)
    compressed = run.work / "selected-compressed.xml"
    run.command("repomix-selected-structure", base + ["--compress", "--output", str(compressed)])
    content = compressed.read_text()
    run.check("repomix-structural-output-only", all(name in content for name in originals)
              and "greeting" in content and "DO_NOT_PACK_CI_UNSELECTED" not in content)
    run.artifact("repomix-structure.xml", compressed)


def toon_fixture(run: Run) -> None:
    source = run.work / "records.json"
    source.write_bytes((ROOT / "fixtures/records.json").read_bytes())
    encoded, recovered = run.work / "records.toon", run.work / "recovered.json"
    cli = run.tools["toon"]
    run.command("toon-encode-statistics", [cli, str(source), "--stats", "-o", str(encoded)])
    run.command("toon-strict-decode", [cli, str(encoded), "--decode", "--strict", "-o", str(recovered)])
    verify_json_roundtrip(source.read_text(), recovered.read_text())
    run.check("toon-exact-json-value-roundtrip", True)
    malformed = run.work / "malformed.toon"
    malformed.write_text("items[2]{name,count}:\n  alpha,1\n")
    run.command("toon-rejects-truncated-array", [cli, str(malformed), "--decode", "--strict"], nonzero=True)
    run.artifact("records.toon", encoded)
    run.artifact("records.recovered.json", recovered)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New sanitized result directory")
    parser.add_argument("--install", action="store_true", help="Install pinned tools into a fresh owned prefix")
    args = parser.parse_args()
    output = args.output.expanduser().absolute()
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="native-token-ci-") as directory:
        run = Run(output, Path(directory))
        run.report["installation"] = "fresh-upstream-prefix" if args.install else "existing-executables"
        completed = False
        try:
            components = {row["id"]: row for row in json.loads((ROOT / "manifests/stack.json").read_text())["components"]}
            for name, version in PINS.items():
                require(components[name]["version"] == version, f"Manifest pin changed: {name}")
            for name, fixture in (("rtk", rtk_fixture), ("qmd", qmd_fixture),
                                  ("repomix", repomix_fixture), ("toon", toon_fixture)):
                try:
                    binary = run.install(name) if args.install else shutil.which(name)
                    require(bool(binary), f"Missing native executable: {name}")
                    run.tools[name] = str(binary)
                    version = run.command(f"version-{name}", [str(binary), "--version"])
                    require(re.search(rf"(?<![\d.]){re.escape(PINS[name])}(?![\d.])", version) is not None,
                            f"Installed {name} differs from its manifest pin")
                    fixture(run)
                except Exception as error:
                    run.report["failures"].append({"component": name, "error": run.clean(str(error))})
                    run.flush()
            completed = True
        except Exception as error:
            run.report["failures"].append({"component": "harness", "error": run.clean(str(error))})
        finally:
            if not completed and not run.report["failures"]:
                run.report["failures"].append({"component": "harness", "error": "Execution interrupted before completion"})
            work = run.work
            # Only this newly created TemporaryDirectory is removed; no shared state or install.
            try:
                shutil.rmtree(work)
            except OSError as error:
                run.report["failures"].append({"component": "cleanup", "error": run.clean(str(error))})
            run.report["cleanup"] = {"owned_temporary_directory_absent": not work.exists(),
                                     "retained_output_exists": output.is_dir()}
            run.report["execution_completed"] = completed
            run.report["status"] = "passed" if completed and not run.report["failures"] else "failed"
            run.flush()
    print(json.dumps({"status": run.report["status"], "commands": len(run.report["commands"]),
                      "checks": len(run.report["checks"]), "failures": run.report["failures"],
                      "cleanup": run.report["cleanup"]}))
    return 0 if run.report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
