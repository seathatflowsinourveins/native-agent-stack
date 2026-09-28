"""Owned lifecycle for the upstream SDK-in-image recipe; no work on import.

Host actions: frozen task checkout/patch transport, supported upstream grader
installation, owned Docker supervision and read-only gateway receipts. Candidate
code executes in worker/grader containers. No installation or execution on import.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
from datetime import datetime, timezone
import json
import io
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

from recipe import HERE, arm_config, digest, llm_config, read_json, render_mcp
from e2e.task import load_task, worker_instruction
from receipt import create_receipt, read_bounded, time_value


DOCKER = ["docker", "--context", "rootless"]
# SWE-bench worker default; the resolver mode uses 3740 (README "Workflow dispatch").
DEFAULT_PORT = 3730
# Agent limits whose partial patch is still graded: SDK@fcc102a
# conversation/impl/local_conversation.py:753-755 (STUCK) and :2021-2043,
# :2339-2360 (ERROR with ConversationErrorEvent code "MaxIterationsReached").
AGENT_LIMITS = frozenset({"stuck", "max_iterations_reached"})
# SDK@fcc102a openhands-agent-server/openhands/agent_server/config.py:24.
SESSION_KEY_NAME = "OH_SESSION_API_KEYS_0"


def owned_port(value):
    """Mirror PR #428 crawl4ai host.py:44-45: an exact int (bool refused) in 3730..3799."""
    if type(value) is not int or not 3730 <= value <= 3799:
        raise ValueError("owned_port_3730_3799_required")
    return value


def cli_port(text):
    # Non-decimal text reaches run() unchanged, so preflight refuses it with a receipt.
    return int(text) if re.fullmatch(r"[0-9]{1,5}", text) else text


def private_file(path):
    path = Path(path).absolute()
    info = path.stat()
    if (path.resolve() != path or not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600 or path.is_relative_to(HERE.parents[2])):
        raise ValueError("owned_mode_0600_file_outside_checkout_required")
    return path


def check_server_env():
    """Require the session-key variable NAME in the server env file; values stay unread.

    SDK@fcc102a agent_server/__main__.py:282-285 binds all interfaces only with a
    session API key (config.py:24 names OH_SESSION_API_KEYS_0). Without one the
    server listens on container loopback, which the published port cannot reach.
    docker/cli@v29.8.1 pkg/kvfile/kvfile.go:92-124 is the --env-file format:
    newline-delimited lines, a BOM dropped on line one, leading whitespace
    trimmed, "#" comments, and the name ends at the first "=". A bare name copies
    the Docker CLI's own environment, so only the NAME= form is accepted. Only
    the text before "=" is compared; no value is kept, printed or logged.
    """
    name = os.environ.get("OPENHANDS_SERVER_ENV")
    if not name:
        raise ValueError("OPENHANDS_SERVER_ENV_required")
    path = private_file(name)
    try:
        text = read_bounded(path, limit=64 * 1024)
    except UnicodeDecodeError:
        raise ValueError("server_env_must_be_utf8") from None
    for number, line in enumerate(text.split("\n")):
        if number == 0:
            line = line.removeprefix("\N{BYTE ORDER MARK}")
        # Go unicode.IsSpace: str.isspace() without U+001C..U+001F.
        line = re.sub(r"^[^\S\x1c-\x1f]+", "", line)
        separator = line.find("=")
        if not line.startswith("#") and separator > 0 and line[:separator] == SESSION_KEY_NAME:
            return path
    raise ValueError("server_env_session_key_name_required")


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


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


def checked_mount(source, allowed):
    """Resolve before checking; only selected tool/collection roots may be bound."""
    candidate = Path(source)
    if not candidate.is_absolute() or not candidate.is_dir():
        raise ValueError("existing_absolute_directory_required")
    candidate = candidate.resolve()
    home = Path.home().resolve()
    protected = [home / part for part in (".config", ".ssh", ".codex", ".claude", ".aws", ".gnupg",
                                         ".local/share/omniroute", ".local/share/omniroute-fw")]
    protected.append(Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))).resolve())
    if (candidate == home or candidate in home.parents
            or any(candidate == p or candidate.is_relative_to(p) or p.is_relative_to(candidate) for p in protected)
            or any(part in {"credentials", ".ssh", ".codex", ".claude", ".aws", ".gnupg"} for part in candidate.parts)):
        raise ValueError("broad_or_authentication_mount_refused")
    if candidate not in {Path(path).resolve() for path in allowed}:
        raise ValueError("mount_outside_selected_roots")
    return candidate


def selected_mcp_roots(eco):
    # adoption/bootstrap-linux.sh:240,439,457 and pins-linux-x86_64.json.
    return [eco / name for name in (
        "bin", "tools/context-mode-1.0.169", "tools/qmd-2.8.3", "tools/node-24.21.0",
        "python-tools/serena", "python-tools/jcodemunch-mcp",
    )]


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
    eco = Path(variables["ECO_ROOT"])
    for value in host["mcp_readonly_mounts"]:
        checked_mount(value, selected_mcp_roots(eco))
    stack = Path(os.environ.get("OPENHANDS_STACK_ROOT", str(HERE.parents[2]))).resolve()
    documents = [stack / name for name in ("docs", "adoption", "blueprints/us-equities", "catalogs/us-equities")]
    for value in host["qmd_collections"].values():
        checked_mount(value, documents)
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


def docker_args(pins, name, *, network="none", installer=False):
    if not re.fullmatch(r"rw-openhands-[a-z0-9-]+", name):
        raise ValueError("owned_container_name_required")
    limits = read_json(HERE / "config/worker.json")["runtime"]
    if network is False:
        network = "none"
    if network not in {"none", "rw-openhands-egress-control", "rw-openhands-egress-engines-on"}:
        if not (installer and network == "bridge" and "-install-" in name):
            raise ValueError("explicit_scoped_model_network_required")
    args = DOCKER + [
        "run", "--rm", "--pull=never", "--name", name, "--platform", pins["image"]["platform"],
        "--label", "com.native-agent-stack.owner=gpt6-omniroute-framework-integration",
        "--user", "0:0" if installer else "10001:10001", "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev,mode=1777",
        "--tmpfs", "/state/home:rw,nosuid,nodev,mode=0700," + ("uid=0,gid=0" if installer else "uid=10001,gid=10001"),
        "--env", "HOME=/state/home",
        "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "UV_PYTHON_DOWNLOADS=never",
        "--cpus", limits["cpus"], "--memory", limits["memory"], "--pids-limit", str(limits["pids_limit"]),
    ]
    args += ["--network=" + network]
    # Base launches publish nothing; dispatch adds only the loopback mapping.
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


def prepare_grader_image(result, instance_id):
    """Bind the upstream instance tag to a coordinator-frozen registry digest.

    SWE-bench@v4.1.0 test_spec/test_spec.py:106-115 defines this tag. Docker
    SDK@7.1.0 models/resource.py:28-33 provides the independently checked Id.
    The coordinator pre-pulls the digest; grading cannot pull mutable tags.
    """
    raw = read_bounded(os.environ["OPENHANDS_GRADER_IMAGE_FILE"], limit=1024 * 1024)
    expected = os.environ["OPENHANDS_GRADER_IMAGE_SHA256"]
    if hashlib.sha256(raw.encode()).hexdigest() != expected:
        raise ValueError("frozen_grader_image_pin_hash_mismatch")
    pin = json.loads(raw)
    tag = ("swebench/sweb.eval.x86_64." + instance_id.lower() + ":latest").replace("__", "_1776_")
    ref = pin.get("ref", "")
    canonical = ref.removeprefix("docker.io/")
    if (pin.get("instance_id") != instance_id or pin.get("tag") != tag or not pin.get("source")
            or not re.fullmatch(re.escape(tag.removesuffix(":latest")) + r"@sha256:[a-f0-9]{64}", canonical)):
        raise ValueError("frozen_instance_image_required")
    images = json.loads(subprocess.check_output(DOCKER + ["image", "inspect", ref], text=True, timeout=30))
    if len(images) != 1:
        raise ValueError("one_prepulled_image_required")
    info = images[0]
    if (canonical not in [v.removeprefix("docker.io/") for v in info.get("RepoDigests", [])]
            or info.get("Architecture") != "amd64" or info.get("Os") != "linux"
            or not re.fullmatch(r"sha256:[a-f0-9]{64}", info.get("Id", ""))):
        raise ValueError("prepulled_image_identity_mismatch")
    subprocess.run(DOCKER + ["tag", ref, tag], check=True, timeout=30)
    selected = {"ref": ref, "tag": tag, "image_id": info["Id"], "pin_sha256": expected}
    write_json(result / "grader-image.json", selected)
    return selected


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
    image = prepare_grader_image(result, instance_id)
    # The SDK Docker API uses DOCKER_HOST, not the CLI's --context option.
    endpoint = subprocess.check_output(DOCKER + ["context", "inspect", "rootless", "--format",
                                                 "{{.Endpoints.docker.Host}}"], text=True, timeout=30).strip()
    if not endpoint.startswith("unix://"):
        raise ValueError("rootless_local_docker_endpoint_required")
    environment = {**os.environ, "DOCKER_HOST": endpoint, "PYTHONDONTWRITEBYTECODE": "1",
                   "HF_HOME": str(result / "grader-cache"), "OPENHANDS_GRADER_IMAGE_ID": image["image_id"]}
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
    for directory in (prefix, prefix / "venv", state, state / "cache"):
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
    args = docker_args(pins, name, installer=True, network="bridge")
    args += install_mounts(prefix, state)
    args += ["--entrypoint", "/bin/bash", pins["image"]["ref"], "/recipe/install-container.sh", str(prefix)]
    private_directory(state / "install-attempts")
    attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=state / "install-attempts"))
    code = execute_container(args, name, attempt / "install.log", 900)
    write_json(state / "installation.json", {"version": pins["version"], "image": pins["image"]["ref"],
                                            "requirements_sha256": pins["requirements_sha256"], "exit_code": code})
    if code:
        raise RuntimeError("container_install_failed_see_private_install_log")
    model_visible(prefix / "venv", writable=False)
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


def install_mounts(prefix, state):
    return (mount(prefix / "venv", prefix / "venv", False) + mount(state / "cache", "/state/cache", False)
            + mount(prefix / "recipe", "/recipe"))


def model_network(host, arm):
    """Require coordinator network-policy evidence before granting any egress.

    Docker docs@4e9a575 firewall-iptables.md:22-24,48-95 defines DOCKER-USER.
    Rootless namespace placement and actual rule effects require host probes.
    A network name or MCP allowlist alone is never network acceptance.
    """
    selection = arm_config(arm)
    entry = host.get("egress", {}).get(arm, {})
    name = "rw-openhands-egress-" + arm
    if entry.get("network") != name or not entry.get("policy_receipt"):
        raise ValueError("verified_per_port_egress_policy_required")
    path = Path(entry["policy_receipt"])
    if path.stat().st_uid != os.getuid() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("private_host_policy_receipt_required")
    proof = json.loads(read_bounded(path))
    age = datetime.now(timezone.utc) - time_value(proof["verified_at"])
    if not 0 <= age.total_seconds() <= 900:
        raise ValueError("fresh_egress_verification_required")
    if (proof.get("mechanism") != "docker-user-iptables"
            or proof.get("allowed_tcp") != [f"10.0.2.2:{selection['gateway_port']}"]
            or any(proof.get(k) is not True for k in (
                "default_deny", "host_input_denied", "ipv6_disabled", "gateway_reachable", "other_host_ports_denied"))):
        raise ValueError("egress_policy_contract_mismatch")
    info = json.loads(subprocess.check_output(DOCKER + ["network", "inspect", name], text=True, timeout=30))[0]
    if (info.get("Id") != proof.get("network_id") or info.get("Driver") != "bridge"
            or info.get("EnableIPv6") or info.get("Labels", {}).get("com.native-agent-stack.owner")
            != "gpt6-omniroute-framework-integration"):
        raise ValueError("egress_network_identity_mismatch")
    return name


def clone_command(prefix, task, workspace):
    # SWE-bench@v4.1.0 test_spec/python.py:271-277, including branch exceptions.
    code = ("import json,sys; from importlib.metadata import version; "
            "assert version('swebench') == '4.1.0'; "
            "from swebench.harness.test_spec.python import REPO_BASE_COMMIT_BRANCH; "
            "print(json.dumps(REPO_BASE_COMMIT_BRANCH.get(sys.argv[1], {}).get(sys.argv[2], '')))")
    branch = json.loads(subprocess.check_output([
        str(prefix / "benchmarks/.venv/bin/python"), "-c", code, task["repo"], task["base_commit"]],
        text=True, timeout=30))
    if not isinstance(branch, str) or (branch and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch)):
        raise ValueError("invalid_upstream_branch_mapping")
    return ["git", "clone", "--no-checkout", "--single-branch", *(["--branch", branch] if branch else []),
            "--", "https://github.com/" + task["repo"] + ".git", str(workspace)]


def result_exit(receipt):
    if receipt.get("failure_stage"):
        return 3
    verdict = receipt.get("upstream_grader", {})
    if any(verdict.get(key) not in (None, 0) for key in ("grader_exit_code", "conversion_exit_code")):
        return 3
    if verdict.get("upstream_resolved") is False:
        return 1 if verdict.get("upstream_bucket") in {"unresolved_ids", "empty_patch_ids"} else 3
    if verdict.get("upstream_resolved") is True and receipt.get("agent_termination") in AGENT_LIMITS:
        return 1  # An officially graded partial patch after an agent limit is never a pass.
    if receipt.get("task_passed") and receipt.get("evidence_complete"):
        return 0
    return 2


def begin_attempt(state, run_id, arm):
    if not re.fullmatch(r"rw-openhands-[a-z0-9-]{1,64}", run_id):
        raise ValueError("owned_run_id_required")
    arm_config(arm)
    result = state / "runs" / run_id / arm
    if result.exists():
        raise ValueError("run_id_arm_already_exists")
    private_directory(result)
    for directory in (result / "input", result / "worker", result / "mcp"):
        private_directory(directory)
    write_json(result / "status.json", {"run_id": run_id, "arm": arm, "status": "starting",
                                        "receipt": str(result / "receipt.json")})
    return result


def model_visible(root, *, writable):
    """Owned mount contents only; private mode-0700 attempt parent stays private.

    Rootless Docker's UID mapping is not host UID equality. The upstream image
    user is 10001 (Dockerfile@fcc102a:7-9,343). Never chmod symlink targets.
    """
    root = Path(root)
    for path in (root, *root.rglob("*")):
        if path.is_symlink():
            continue
        mode = path.stat().st_mode
        if stat.S_ISDIR(mode):
            path.chmod(0o777 if writable else 0o755)
        elif stat.S_ISREG(mode):
            path.chmod((0o666 if writable else 0o644) | (0o111 if mode & 0o111 else 0))
        else:
            raise ValueError("special_file_in_model_mount")


def prepare_native_dispatch(result, prefix, pins, base, network, host, selection, run_id, port=DEFAULT_PORT):
    from dispatch import check_server, private_file, server_command
    stem = run_id + "-" + selection["arm"]
    env_file = private_file(os.environ["OPENHANDS_SERVER_ENV"])
    private_file(os.environ["OPENHANDS_HEADERS"])
    environment = ["--env", "OPENHANDS_OWNED_CONTAINER=1",
                   "--env", "OPENHANDS_RUN_ID=" + run_id, "--env", "OPENHANDS_ARM=" + selection["arm"],
                   "--env", "OPENHANDS_MODEL=" + selection["requested_model"],
                   "--env", "OPENHANDS_BASE_URL=" + selection["base_url"],
                   "--env", f"PATH={prefix}/venv/bin:" + host["variables"]["HOST_PATH"]]
    render = docker_args(pins, stem + "-request") + base + mount(result / "worker", "/run-output", False)
    render += environment + ["--entrypoint", str(prefix / "venv/bin/python"), pins["image"]["ref"], "/recipe/worker.py", "--request"]
    if execute_container(render, stem + "-request", result / "request.log", 120):
        raise RuntimeError("native_request_serialization_failed")
    # Host copy made before a model can run; later worker edits cannot change it.
    body = json.loads(read_bounded(result / "worker/start.json"))
    write_json(result / "start.json", body)
    private_directory(result / "server")
    model_visible(result / "server", writable=True)
    mounts = base + environment + mount(result / "server", "/state/server", False) + mount(result / "worker", "/run-output", False)
    name = stem + "-server"
    try:
        if logged_command(server_command(pins, name, mounts, network, env_file, port=port),
                          result / "server-start.log", cwd=result, timeout=60):
            raise RuntimeError("native_server_launch_failed")
        check_server(body, port=port)
    except (Exception, KeyboardInterrupt):
        cleanup_container(name, result / "server.log")
        raise
    # Host-owned status is the dispatch commands' only port source.
    write_json(result / "status.json", {"run_id": run_id, "arm": selection["arm"], "status": "prepared",
                                        "server_name": name, "port": port, "receipt": str(result / "receipt.json")})


def run(prefix, state, *, run_id=None, arm=None, prepare_only=False, port=DEFAULT_PORT):
    run_id = run_id or os.environ.get("OPENHANDS_RUN_ID", "rw-openhands-e2e-" + uuid.uuid4().hex[:12])
    arm = arm or os.environ.get("OPENHANDS_ARM", "control")
    try:
        result = begin_attempt(state, run_id, arm)
    except (OSError, ValueError):
        print(json.dumps({"run_id": run_id, "arm": arm, "receipt": None, "failure_stage": "preflight",
                          "task_passed": False, "evidence_complete": False}))
        return 3
    window = {"started_at": utc_now(), "finished_at": None, "worker_exit_code": None, "arm": arm, "run_id": run_id}
    checked = {"upstream_resolved": None, "grader_exit_code": None}
    stem = run_id + "-" + arm
    stage = "preflight"
    prepared = False
    native_receipt = None
    try:
        port = owned_port(port)
        pins, host, mcp = preflight(prefix, state)
        check_server_env()
        installed = read_json(state / "installation.json")
        if installed.get("exit_code") != 0 or installed.get("requirements_sha256") != pins["requirements_sha256"]:
            raise ValueError("matching_successful_installation_required")
        if not os.path.lexists(prefix / "venv/bin/python"):
            raise ValueError("owned_sdk_venv_missing")
        cfg = read_json(HERE / "config/worker.json")
        selection = arm_config(arm, os.environ.get("OPENHANDS_MODEL"), os.environ.get("OPENHANDS_BASE_URL"))
        llm_config(cfg, selection["requested_model"], arm=arm, base_url=selection["base_url"])
        window.update({k: v for k, v in selection.items() if k != "headers"})
        window["header_names"] = sorted([*selection["headers"], "x-omniroute-session", "X-Correlation-Id", "Idempotency-Key"])
        network = model_network(host, arm)
        stage = "prepare"
        original = Path(os.environ["OPENHANDS_TASK_FILE"]).resolve()
        task_sha = os.environ["OPENHANDS_TASK_SHA256"]
        task = load_task(original, task_sha)
        window.update(instance_id=task["instance_id"])
        # Frozen oracle bytes are outside every worker mount.
        dataset = result / ("dataset" + original.suffix)
        shutil.copyfile(original, dataset)
        load_task(dataset, task_sha)
        write_json(result / "task-identity.json", {
            "instance_id": task["instance_id"], "repo": task["repo"],
            "base_commit": task["base_commit"], "dataset_sha256": task_sha,
        })
        workspace = result / "workspace"
        code = logged_command(clone_command(prefix, task, workspace), result / "clone.log", cwd=result, timeout=300)
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
        for directory in (workspace, result / "mcp", result / "worker"):
            model_visible(directory, writable=True)
        model_visible(result / "input", writable=False)
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
        stage = "start"
        prepare_native_dispatch(result, prefix, pins, base, network, host, selection, run_id, port=port)
        prepared = True
        write_json(result / "window.json", window)
        if not prepare_only:
            from dispatch import execute
            with contextlib.redirect_stdout(io.StringIO()):
                for action in ("start", "wait", "result"):
                    if execute(action, state, run_id, arm):
                        break
            native_receipt = read_json(result / "receipt.json")
    except (Exception, KeyboardInterrupt) as exc:
        window["failure_stage"] = stage
        window["failure_type"] = type(exc).__name__
    finally:
        if native_receipt is not None:
            receipt = native_receipt
        else:
            window["finished_at"] = window["finished_at"] or utc_now()
            write_json(result / "window.json", window)
            write_json(result / "check.json", checked)
            receipt = create_receipt(result)
            write_json(result / "receipt.json", receipt)
    output = {"run_id": run_id, "arm": arm, "receipt": str(result / "receipt.json"),
              **{k: receipt[k] for k in ("failure_stage", "task_passed", "evidence_complete")}}
    if not prepared:
        write_json(result / "status.json", {**output, "status": "failed" if receipt["failure_stage"] else "finished"})
    print(json.dumps(output))
    if prepare_only and prepared:
        return 0
    return result_exit(receipt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "run", "prepare"))
    parser.add_argument("--prefix", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--arm", choices=("control", "engines-on"))
    parser.add_argument("--port", type=cli_port, default=DEFAULT_PORT,
                        help="published loopback port in 3730..3799 (default 3730; resolver mode 3740)")
    args = parser.parse_args()
    os.umask(0o077)
    # SIGTERM goes through container cleanup and the failed-attempt receipt path.
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    if args.action == "install":
        install(args.prefix, args.state)
        return 0
    return run(args.prefix, args.state, run_id=args.run_id, arm=args.arm,
               prepare_only=args.action == "prepare", port=args.port)


if __name__ == "__main__":
    raise SystemExit(main())
