"""Owned lifecycle for the upstream SDK-in-image recipe; no work on import.

Host actions: path/hash validation, rootless Docker CLI, fixture byte copies,
bounded process supervision and read-only gateway receipts. Candidate Python
and all SDK/MCP processes execute inside the digest-pinned image.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import urllib.request
import uuid

from recipe import HERE, digest, read_json, render_mcp


DOCKER = ["docker", "--context", "rootless"]


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def private_directory(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError("owned_directory_is_symlink")
    path.chmod(0o700)


def mount(source, target, readonly=True):
    if any(char in str(source) + str(target) for char in (",", "\n", "\r")):
        raise ValueError("unsupported_mount_path")
    return ["--mount", f"type=bind,src={source},dst={target}" + (",readonly" if readonly else "")]


def check_rootless():
    result = subprocess.run(DOCKER + ["info", "--format", "{{json .SecurityOptions}}"],
                            capture_output=True, text=True, check=True, timeout=30)
    if "name=rootless" not in json.loads(result.stdout):
        raise ValueError("rootless_docker_required")


def preflight(prefix, state):
    pins = read_json(HERE / "pins.json")
    if digest(HERE / "requirements.lock") != pins["requirements_sha256"]:
        raise ValueError("runtime_lock_hash_mismatch")
    if digest(HERE / "build-requirements.lock") != pins["build_requirements_sha256"]:
        raise ValueError("build_lock_hash_mismatch")
    expected_prefix = Path.home() / ".local/share/codex-ecosystem/tools" / ("openhands-" + pins["version"])
    expected_state = Path.home() / ".local/state/native-agent-stack/runtime-workers/openhands"
    if prefix != expected_prefix or state != expected_state:
        raise ValueError("unexpected_owned_prefix")
    for path in (prefix, state):
        if path.resolve() != path:
            raise ValueError("owned_path_must_not_follow_symlinks")
    private_name = os.environ.get("OPENHANDS_HOST_FILE")
    if not private_name:
        raise ValueError("OPENHANDS_HOST_FILE_required")
    path = Path(private_name).expanduser()
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid():
        raise ValueError("private_host_file_must_be_owned_regular_file")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("private_host_file_requires_mode_0600")
    if path.resolve().is_relative_to(HERE.parents[2].resolve()):
        raise ValueError("private_host_file_must_be_outside_checkout")
    host = read_json(path)
    if "<" in json.dumps(host):
        raise ValueError("host_file_has_unfilled_placeholders")
    variables = host["variables"]
    if variables["AI_MEMORY_URL"] != "10.0.2.2:49474":
        raise ValueError("ai_memory_container_endpoint_required")
    if variables["EMBED_URL"] != "10.0.2.2:18232":
        raise ValueError("local_embedder_required")
    if variables["CODE_INDEX_PATH"] != "/state/mcp/jcodemunch":
        raise ValueError("owned_jcodemunch_store_required")
    mcp = render_mcp(variables)
    required = set(read_json(HERE / "config/mcp-policy.json")["qmd"]["collections"])
    if set(host["qmd_collections"]) != required:
        raise ValueError("exact_qmd_collections_required")
    for value in [*host["mcp_readonly_mounts"], *host["qmd_collections"].values()]:
        candidate = Path(value)
        if not candidate.is_absolute() or not candidate.is_dir():
            raise ValueError("existing_absolute_directory_required")
        forbidden = (Path("/"), Path.home(), Path("/run"), Path("/var/run"), Path.home() / ".local")
        if candidate.resolve() in forbidden or any(part in {".ssh", ".codex", ".claude", "credentials"} for part in candidate.parts):
            raise ValueError("broad_or_authentication_mount_refused")
    skills = []
    for entry in read_json(HERE / "config/skills.lock.json")["skills"]:
        source = Path.home() / ".agents/skills" / entry["name"]
        if digest(source / "SKILL.md") != entry["skill_md_sha256"]:
            raise ValueError("installed_skill_pin_mismatch:" + entry["name"])
        skills.append((entry["name"], source.resolve()))
    check_rootless()
    return pins, host, mcp, skills


def docker_args(pins, name, *, network=True):
    limits = read_json(HERE / "config/worker.json")["runtime"]
    args = DOCKER + [
        "run", "--rm", "--pull=never", "--name", name, "--platform", pins["image"]["platform"],
        "--label", "native-agent-stack.runtime-worker=openhands",
        "--user", "0:0", "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,mode=1777", "--tmpfs", "/root:rw,nosuid,nodev,mode=0700",
        "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "UV_PYTHON_DOWNLOADS=never",
        "--cpus", limits["cpus"], "--memory", limits["memory"], "--pids-limit", str(limits["pids_limit"]),
    ]
    if not network:
        args += ["--network=none"]
    # No HTTP listener and no port publication; image EXPOSE is not publishing.
    return args


def execute_container(args, name, logfile, timeout):
    """Bound the Docker client and remove exactly its container on every exit."""
    try:
        with logfile.open("w") as log:
            result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=timeout, check=False)
            return result.returncode
    except subprocess.TimeoutExpired:
        return 124
    except OSError:
        return 127
    finally:
        cleanup = {"confirmed_removed": False, "error_type": None}
        try:
            removed = subprocess.run(DOCKER + ["rm", "-f", name], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, check=False, timeout=30)
            if removed.returncode == 0:
                cleanup["confirmed_removed"] = True
            else:
                # --rm usually removed it already. A successful empty listing
                # establishes absence; daemon errors never count as absence.
                remaining = subprocess.run(DOCKER + ["ps", "-aq", "--filter", "name=^/" + name + "$"],
                                           capture_output=True, text=True, check=False, timeout=30)
                cleanup["confirmed_removed"] = remaining.returncode == 0 and not remaining.stdout.strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            cleanup["error_type"] = type(exc).__name__
        write_json(logfile.with_suffix(logfile.suffix + ".cleanup.json"), cleanup)


def download_verified(artifact, target):
    if target.exists():
        if digest(target) != artifact["sha256"]:
            raise ValueError("cached_artifact_hash_mismatch")
        return
    temporary = target.with_suffix(target.suffix + ".partial")
    with urllib.request.urlopen(artifact["url"], timeout=120) as response, temporary.open("wb") as out:
        shutil.copyfileobj(response, out)
    if digest(temporary) != artifact["sha256"]:
        raise ValueError("downloaded_artifact_hash_mismatch")
    temporary.replace(target)


def install(prefix, state):
    pins, _, _, skills = preflight(prefix, state)
    for directory in (prefix, state, state / "cache", prefix / "skills"):
        private_directory(directory)
    # Source bytes are retained for reproducibility, not executed or patched.
    download_verified(pins["source_archive"], state / "cache/upstream.tar.gz")
    download_verified(pins["uv_lock"], state / "cache/upstream.uv.lock")
    subprocess.run(DOCKER + ["pull", "--platform", pins["image"]["platform"], pins["image"]["ref"]], check=True)
    image_id = subprocess.check_output(DOCKER + ["image", "inspect", "--format", "{{.Id}}", pins["image"]["ref"]], text=True).strip()
    if image_id != "sha256:" + pins["image"]["config_sha256"]:
        raise ValueError("image_configuration_hash_mismatch")
    # A reviewable snapshot, with no repository metadata or host configuration.
    if HERE.resolve() != (prefix / "recipe").resolve():
        shutil.copytree(HERE, prefix / "recipe", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name, source in skills:
        link = prefix / "skills" / name
        if link.is_symlink() and link.resolve() == source:
            continue
        if link.exists() or link.is_symlink():
            raise ValueError("existing_skill_reference_conflict")
        link.symlink_to(source, target_is_directory=True)
    name = "openhands-install-" + uuid.uuid4().hex[:12]
    args = docker_args(pins, name)
    args += mount(prefix, prefix, False) + mount(state, "/state", False) + mount(prefix / "recipe", "/recipe")
    args += ["--entrypoint", "/bin/bash", pins["image"]["ref"], "/recipe/install-container.sh", str(prefix)]
    private_directory(state / "install-attempts")
    attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=state / "install-attempts"))
    code = execute_container(args, name, attempt / "install.log", 900)
    write_json(state / "installation.json", {"version": pins["version"], "image": pins["image"]["ref"],
                                            "requirements_sha256": pins["requirements_sha256"], "exit_code": code})
    if code:
        raise RuntimeError("container_install_failed_see_private_install_log")
    print("Installed pinned SDK wheels in owned container venv; model/MCP/E2E acceptance remains pending.")


def runtime_mounts(host, skills):
    args = []
    for source in host["mcp_readonly_mounts"]:
        args += mount(Path(source).resolve(), source)
    for name, source in host["qmd_collections"].items():
        args += mount(Path(source).resolve(), "/documents/" + name)
    for name, source in skills:
        args += mount(source, "/skills/" + name)
    return args


def run(prefix, state):
    pins, host, mcp, skills = preflight(prefix, state)
    installed = read_json(state / "installation.json")
    if installed.get("exit_code") != 0 or installed.get("requirements_sha256") != pins["requirements_sha256"]:
        raise ValueError("matching_successful_installation_required")
    # The venv's interpreter link resolves inside the image, not on the host.
    if not os.path.lexists(prefix / "venv/bin/python"):
        raise ValueError("owned_sdk_venv_missing")
    cfg = read_json(HERE / "config/worker.json")
    private_directory(state / "runs")
    result = Path(tempfile.mkdtemp(prefix="attempt-", dir=state / "runs"))
    for directory in (result / "input", result / "worker", result / "mcp"):
        private_directory(directory)
    for name in mcp:
        for child in ("cache", "config", "data", "state"):
            private_directory(result / "mcp" / name / child)
    serena_home = result / "mcp/serena/home"
    private_directory(serena_home)
    shutil.copyfile(HERE / "config/serena_config.yml", serena_home / "serena_config.yml")
    shutil.copytree(HERE / "e2e/fixture-repo", result / "workspace")
    write_json(result / "input/mcp.json", mcp)
    runtime = cfg["runtime"]
    stem = "openhands-e2e-" + uuid.uuid4().hex[:12]
    window = {"started_at": utc_now(), "finished_at": None, "worker_exit_code": None}
    stage = "baseline"
    try:
        name = stem + "-baseline"
        args = docker_args(pins, name, network=False) + mount(prefix, prefix) + mount(HERE, "/recipe")
        args += mount(result / "workspace", "/workspace")
        args += ["--entrypoint", str(prefix / "venv/bin/python"), pins["image"]["ref"],
                 "-I", "-B", "/recipe/e2e/check.py", "--baseline", "/workspace"]
        code = execute_container(args, name, result / "baseline.log", 60)
        baseline = json.loads((result / "baseline.log").read_text().splitlines()[-1])
        write_json(result / "baseline.json", baseline)
        if code != 1 or baseline.get("tests_run") != 1 or baseline.get("failures") != 1 or baseline.get("errors") != 0:
            raise ValueError("frozen_baseline_not_red")
        base = mount(prefix, prefix) + mount(HERE, "/recipe") + mount(result / "input", "/run-input")
        base += mount(result / "mcp", "/state/mcp", False) + mount(result / "workspace", "/workspace", False)
        base += runtime_mounts(host, skills)
        stage = "qmd_setup"
        name = stem + "-qmd"
        args = docker_args(pins, name) + base
        args += ["--entrypoint", str(prefix / "venv/bin/python"), pins["image"]["ref"], "/recipe/qmd-setup.py"]
        if execute_container(args, name, result / "qmd-setup.log", 900) != 0:
            raise RuntimeError("qmd_setup_failed")
        stage = "agent"
        name = stem + "-agent"
        args = docker_args(pins, name) + base + mount(result / "worker", "/run-output", False)
        args += ["--workdir", "/workspace", "--env", "OPENHANDS_OWNED_CONTAINER=1",
                 "--env", f"PATH={prefix}/venv/bin:" + host["variables"]["HOST_PATH"],
                 "--env", "XDG_CACHE_HOME=/run-output/cache", "--env", "XDG_STATE_HOME=/run-output/state",
                 "--env", "XDG_DATA_HOME=/run-output/data", "--env", "XDG_CONFIG_HOME=/run-output/config"]
        selected_model = os.environ.get(cfg["model_env"], cfg["llm"]["model"])
        # Validate before forwarding. No API credential environment is forwarded.
        from recipe import llm_config
        llm_config(cfg, selected_model)
        window["model"] = selected_model
        args += ["--env", cfg["model_env"] + "=" + selected_model,
                 "--entrypoint", str(prefix / "venv/bin/python"), pins["image"]["ref"], "/recipe/worker.py"]
        window["started_at"] = utc_now()
        window["worker_exit_code"] = execute_container(args, name, result / "worker.log", runtime["timeout_seconds"])
    except (Exception, KeyboardInterrupt) as exc:
        # Retain failed attempts, but do not put private exception text in receipts.
        window["failure_stage"] = stage
        window["failure_type"] = type(exc).__name__
    finally:
        window["finished_at"] = utc_now()
        write_json(result / "window.json", window)
        name = stem + "-check"
        args = docker_args(pins, name, network=False) + mount(prefix, prefix) + mount(HERE, "/recipe")
        args += mount(result, "/result")
        args += ["--entrypoint", str(prefix / "venv/bin/python"), pins["image"]["ref"],
                 "-I", "-B", "/recipe/e2e/check.py", "--result", "/result"]
        check_code = execute_container(args, name, result / "check.log", 90)
        try:
            checked = json.loads((result / "check.log").read_text().splitlines()[-1])
        except (ValueError, IndexError):
            checked = {"passed": False, "failures": ["checker_did_not_return_json"]}
        checked["exit_code"] = check_code
        write_json(result / "check.json", checked)
        from receipt import create_receipt
        receipt = create_receipt(result)
        write_json(result / "receipt.json", receipt)
    print(json.dumps({"task_passed": receipt["task_passed"], "evidence_complete": receipt["evidence_complete"]}))
    return 0 if receipt["task_passed"] and receipt["evidence_complete"] else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "run"))
    parser.add_argument("--prefix", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    # SIGTERM goes through container cleanup and the failed-attempt receipt path.
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    if args.action == "install":
        install(args.prefix, args.state)
        return 0
    return run(args.prefix, args.state)


if __name__ == "__main__":
    raise SystemExit(main())
