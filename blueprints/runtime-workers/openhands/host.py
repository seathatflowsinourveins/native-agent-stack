"""Owned lifecycle for the upstream SDK-in-image recipe; no work on import.

Host actions: frozen task checkout/patch transport, supported upstream grader
installation, owned Docker supervision and read-only gateway receipts. Candidate
code executes in worker/grader containers. No installation or execution on import.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
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
    check_rootless()
    return pins, host, mcp


def install_workspace_skills(stack_root, workspace):
    """Pending shared skills PR: no copy/symlink/global-install fallback."""
    # Vercel skills 1.7.0 add.ts:2130-2160 also creates a root local lock.
    # A task's existing paths must never become installer-owned or ignored.
    if any(os.path.lexists(workspace / name) for name in (".agents", "skills-lock.json")):
        raise ValueError("task_conflicts_with_skill_installer_paths")
    subprocess.run([
        sys.executable, str(stack_root / "tools/adoption/install_skills.py"),
        "--manifest", "blueprints/runtime-workers/skills/manifest.json",
        "--project-dir", str(workspace), "--agent", "universal",
    ], cwd=stack_root, check=True, timeout=600)
    with (workspace / ".git/info/exclude").open("a") as stream:
        stream.write("\n/.agents/\n/skills-lock.json\n")


def workspace_skills(stack_root, workspace):
    manifest = stack_root / "blueprints/runtime-workers/skills/manifest.json"
    entries = read_json(manifest)["skills"]
    installed = workspace / ".agents/skills"
    names = [entry["name"] for entry in entries]
    if len(names) != len(set(names)) or not {"tdd", "verification-before-completion"} <= set(names):
        raise ValueError("runtime_skills_manifest_contract")
    for entry in entries:
        path = installed / entry["name"] / "SKILL.md"
        if not re.fullmatch(r"[a-z0-9-]+", entry["name"]):
            raise ValueError("invalid_skill_name")
        if not path.resolve().is_relative_to(installed.resolve()):
            raise ValueError("skills_must_be_project_local")
        if digest(path) != entry["skill_md_sha256"]:
            raise ValueError("installed_project_skill_pin_mismatch")
    return {"names": sorted(names), "manifest_sha256": digest(manifest)}


def docker_args(pins, name, *, network=True):
    if not re.fullmatch(r"rw-openhands-[a-z0-9-]+", name):
        raise ValueError("owned_container_name_required")
    limits = read_json(HERE / "config/worker.json")["runtime"]
    args = DOCKER + [
        "run", "--rm", "--pull=never", "--name", name, "--platform", pins["image"]["platform"],
        "--label", "com.native-agent-stack.owner=gpt6-omniroute-framework-integration",
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
        cleanup_container(name, logfile)


def cleanup_container(name, logfile):
    cleanup = {"confirmed_removed": False, "error_type": None}
    try:
        removed = subprocess.run(DOCKER + ["rm", "-f", name], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, check=False, timeout=30)
        if removed.returncode == 0:
            cleanup["confirmed_removed"] = True
        else:
            remaining = subprocess.run(DOCKER + ["ps", "-aq", "--filter", "name=^/" + re.escape(name) + "$"],
                                       capture_output=True, text=True, check=False, timeout=30)
            cleanup["confirmed_removed"] = remaining.returncode == 0 and not remaining.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        cleanup["error_type"] = type(exc).__name__
    write_json(logfile.with_suffix(logfile.suffix + ".cleanup.json"), cleanup)


def logged_command(argv, logfile, *, cwd, timeout, env=None):
    """Private command/exit capture; no claim that exit zero is task success."""
    record = {"argv": list(map(str, argv)), "started_at": utc_now(), "exit_code": None}
    try:
        with logfile.open("w") as log:
            completed = subprocess.run(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT,
                                       timeout=timeout, check=False)
            record["exit_code"] = completed.returncode
    except subprocess.TimeoutExpired:
        record["exit_code"] = 124
    except OSError:
        record["exit_code"] = 127
    finally:
        record["finished_at"] = utc_now()
        write_json(logfile.with_suffix(".command.json"), record)
    return record["exit_code"]


def grade(prefix, result, dataset, instance_id, run_id):
    """Upstream conversion, then its unchanged official Docker grading CLI."""
    from e2e.check import check_input, read_report
    grader = prefix / "benchmarks"
    pin = read_json(HERE / "pins.json")["grader"]
    for checkout, expected in ((grader, pin["commit"]),
                               (grader / "vendor/software-agent-sdk", pin["sdk_submodule_commit"])):
        actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True, timeout=30).strip()
        if actual != expected:
            raise ValueError("grader_checkout_pin_mismatch")
        if subprocess.check_output(["git", "-C", str(checkout), "status", "--porcelain",
                                    "--untracked-files=no"], text=True, timeout=30).strip():
            raise ValueError("grader_checkout_modified")
    source = result / "output.jsonl"
    check_input(source, instance_id)
    # The SDK Docker API uses DOCKER_HOST, not the CLI's --context option.
    endpoint = subprocess.check_output(DOCKER + ["context", "inspect", "rootless", "--format",
                                                 "{{.Endpoints.docker.Host}}"], text=True, timeout=30).strip()
    if not endpoint.startswith("unix://"):
        raise ValueError("rootless_local_docker_endpoint_required")
    environment = {**os.environ, "DOCKER_HOST": endpoint, "PYTHONDONTWRITEBYTECODE": "1",
                   "HF_HOME": str(result / "grader-cache")}
    convert = [str(grader / ".venv/bin/swebench-eval"), str(source),
               "--dataset", str(dataset), "--run-id", run_id, "--workers", "1",
               "--no-modal", "--skip-evaluation"]
    code = logged_command(convert, result / "convert.log", cwd=result, env=environment, timeout=180)
    if code:
        return {"upstream_resolved": None, "grader_exit_code": None, "conversion_exit_code": code}
    predictions = result / "output.swebench.jsonl"
    converted = [json.loads(line) for line in predictions.read_text().splitlines() if line]
    if (len(converted) != 1 or converted[0].get("instance_id") != instance_id
            or converted[0].get("model_name_or_path") != "OpenHands"
            or not isinstance(converted[0].get("model_patch"), str)):
        raise ValueError("upstream_conversion_scope_mismatch")
    command = [
        str(grader / ".venv/bin/python"), str(HERE / "e2e/docker_grader.py"),
        "--dataset_name", str(dataset), "--predictions_path", str(predictions),
        "--instance_ids", instance_id, "--run_id", run_id, "--max_workers", "1",
        "--split", "test", "--timeout", "1800", "--namespace", "swebench",
        "--cache_level", "instance", "--clean", "false", "--modal", "false",
    ]
    # swebench TestSpec.get_instance_container_name, with our prefix only.
    name = "rw-openhands-sweb.eval." + instance_id.lower() + "." + run_id
    try:
        code = logged_command(command, result / "grader.log", cwd=result, env=environment, timeout=2400)
    finally:
        cleanup_container(name, result / "grader.log")
    report = result / ("OpenHands." + run_id + ".json")
    try:
        relayed = read_report(report, instance_id)
    except (OSError, ValueError, TypeError):
        relayed = {"upstream_resolved": None, "transport_error": "missing_or_malformed_output"}
    return {**relayed, "grader_exit_code": code, "conversion_exit_code": 0,
            "raw_prediction_sha256": digest(source), "converted_prediction_sha256": digest(predictions)}


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
    pins, _, _ = preflight(prefix, state)
    for directory in (prefix, state, state / "cache"):
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
    name = "rw-openhands-install-" + uuid.uuid4().hex[:12]
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
    subprocess.run(["bash", str(HERE / "install-grader.sh"), str(prefix / "benchmarks"),
                    str(state / "cache")], check=True, timeout=1200)
    print("Installed SDK and pinned upstream grader; model/MCP/E2E acceptance remains pending.")


def runtime_mounts(host):
    args = []
    for source in host["mcp_readonly_mounts"]:
        args += mount(Path(source).resolve(), source)
    for name, source in host["qmd_collections"].items():
        args += mount(Path(source).resolve(), "/documents/" + name)
    return args


def run(prefix, state):
    from e2e.task import load_task, worker_instruction
    from recipe import llm_config
    pins, host, mcp = preflight(prefix, state)
    installed = read_json(state / "installation.json")
    if installed.get("exit_code") != 0 or installed.get("requirements_sha256") != pins["requirements_sha256"]:
        raise ValueError("matching_successful_installation_required")
    if not os.path.lexists(prefix / "venv/bin/python"):
        raise ValueError("owned_sdk_venv_missing")
    cfg = read_json(HERE / "config/worker.json")
    selected_model = os.environ.get(cfg["model_env"], cfg["llm"]["model"])
    llm_config(cfg, selected_model)
    private_directory(state / "runs")
    result = Path(tempfile.mkdtemp(prefix="attempt-", dir=state / "runs"))
    for directory in (result / "input", result / "worker", result / "mcp"):
        private_directory(directory)
    window = {"started_at": utc_now(), "finished_at": None, "worker_exit_code": None, "model": selected_model}
    checked = {"upstream_resolved": None, "grader_exit_code": None}
    stem = "rw-openhands-e2e-" + uuid.uuid4().hex[:12]
    stage = "prepare"
    try:
        original = Path(os.environ["OPENHANDS_TASK_FILE"]).resolve()
        task_sha = os.environ["OPENHANDS_TASK_SHA256"]
        task = load_task(original, task_sha)
        window.update(instance_id=task["instance_id"], run_id=stem)
        # Frozen oracle bytes are outside every worker mount.
        dataset = result / ("dataset" + original.suffix)
        shutil.copyfile(original, dataset)
        load_task(dataset, task_sha)
        write_json(result / "task-identity.json", {
            "instance_id": task["instance_id"], "repo": task["repo"],
            "base_commit": task["base_commit"], "dataset_sha256": task_sha,
        })
        workspace = result / "workspace"
        code = logged_command(["git", "clone", "--no-checkout", "--single-branch", "--", "https://github.com/" + task["repo"] + ".git",
                               str(workspace)], result / "clone.log", cwd=result, timeout=300)
        if code:
            raise RuntimeError("task_clone_failed")
        code = logged_command(["git", "-C", str(workspace), "reset", "--hard", task["base_commit"]],
                              result / "checkout.log", cwd=result, timeout=120)
        if code:
            raise RuntimeError("task_checkout_failed")
        # SWE-bench 4.1.0 test_spec/python.py:274-292 removes future refs and
        # reflogs before exposing the checkout. This bare-checkout adaptation
        # drops every tag (not only newer tags) and checks surviving refs below.
        code = logged_command(["git", "-C", str(workspace), "remote", "remove", "origin"],
                              result / "remove-remote.log", cwd=result, timeout=30)
        if code:
            raise RuntimeError("task_history_isolation_failed")
        tags = subprocess.check_output(["git", "-C", str(workspace), "tag", "--list"], text=True, timeout=30).splitlines()
        for tag in tags:
            subprocess.run(["git", "-C", str(workspace), "update-ref", "-d", "refs/tags/" + tag],
                           check=True, timeout=30, stdin=subprocess.DEVNULL)
        for phase, argv in (("reflog", ["reflog", "expire", "--expire=now", "--all"]),
                            ("gc", ["gc", "--prune=now"])):
            if logged_command(["git", "-C", str(workspace), *argv], result / (phase + ".log"),
                              cwd=result, timeout=300):
                raise RuntimeError("task_history_isolation_failed")
        refs = subprocess.check_output(["git", "-C", str(workspace), "for-each-ref", "--format=%(objectname)"],
                                       text=True, timeout=30).splitlines()
        if not refs or any(ref != task["base_commit"] for ref in refs):
            raise ValueError("unexpected_task_reference")
        stage = "skills"
        stack_root = Path(os.environ.get("OPENHANDS_STACK_ROOT", str(HERE.parents[2]))).resolve()
        if not (stack_root / "blueprints/runtime-workers/skills/manifest.json").is_file():
            raise ValueError("skills_program_pending_pr")
        install_workspace_skills(stack_root, workspace)
        skills = workspace_skills(stack_root, workspace)
        write_json(result / "input/skills.json", skills)
        write_json(result / "input/mcp.json", mcp)
        (result / "input/task.txt").write_text(worker_instruction(task))
        for name in mcp:
            for child in ("cache", "config", "data", "state"):
                private_directory(result / "mcp" / name / child)
        serena_home = result / "mcp/serena/home"
        private_directory(serena_home)
        shutil.copyfile(HERE / "config/serena_config.yml", serena_home / "serena_config.yml")
        # Only the worker venv, not the grader checkout/environment, is mounted.
        base = mount(prefix / "venv", prefix / "venv") + mount(HERE, "/recipe")
        base += mount(result / "input", "/run-input") + mount(result / "mcp", "/state/mcp", False)
        base += mount(workspace, "/workspace", False) + mount(workspace / ".git", "/workspace/.git")
        base += mount(workspace / ".agents", "/workspace/.agents") + runtime_mounts(host)
        if (workspace / "skills-lock.json").is_file():
            base += mount(workspace / "skills-lock.json", "/workspace/skills-lock.json")
        stage = "qmd_setup"
        args = docker_args(pins, stem + "-qmd") + base
        args += ["--entrypoint", str(prefix / "venv/bin/python"), pins["image"]["ref"], "/recipe/qmd-setup.py"]
        if execute_container(args, stem + "-qmd", result / "qmd-setup.log", 900):
            raise RuntimeError("qmd_setup_failed")
        stage = "agent"
        args = docker_args(pins, stem + "-agent") + base + mount(result / "worker", "/run-output", False)
        args += ["--workdir", "/workspace", "--env", "OPENHANDS_OWNED_CONTAINER=1",
                 "--env", f"PATH={prefix}/venv/bin:" + host["variables"]["HOST_PATH"],
                 "--env", "XDG_CACHE_HOME=/run-output/cache", "--env", "XDG_STATE_HOME=/run-output/state",
                 "--env", "XDG_DATA_HOME=/run-output/data", "--env", "XDG_CONFIG_HOME=/run-output/config",
                 "--env", cfg["model_env"] + "=" + selected_model,
                 "--entrypoint", str(prefix / "venv/bin/python"), pins["image"]["ref"], "/recipe/worker.py"]
        window["started_at"] = utc_now()
        window["worker_exit_code"] = execute_container(args, stem + "-agent", result / "worker.log",
                                                       cfg["runtime"]["timeout_seconds"])
        window["finished_at"] = utc_now()
        if window["worker_exit_code"]:
            raise RuntimeError("worker_failed")
        stage = "export"
        # Native benchmarks/run_infer.py get_patch uses git add -A then cached
        # diff for unfinished/uncommitted work. No candidate Python runs here.
        code = logged_command(["git", "-C", str(workspace), "add", "-A"],
                              result / "stage-patch.log", cwd=result, timeout=60)
        if code:
            raise RuntimeError("patch_export_failed")
        patch_text = subprocess.check_output(
            ["git", "-C", str(workspace), "--no-pager", "diff", "--no-color", "--cached", task["base_commit"]],
            text=True, timeout=60)
        (result / "output.jsonl").write_text(json.dumps({
            "instance_id": task["instance_id"], "test_result": {"git_patch": patch_text}, "error": None,
        }) + "\n")
        stage = "grader"
        checked = grade(prefix, result, dataset, task["instance_id"], stem)
    except (Exception, KeyboardInterrupt) as exc:
        window["failure_stage"] = stage
        window["failure_type"] = type(exc).__name__
    finally:
        window["finished_at"] = window["finished_at"] or utc_now()
        write_json(result / "window.json", window)
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
