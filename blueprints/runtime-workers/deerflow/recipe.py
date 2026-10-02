"""Bounded installer/renderer for the upstream Compose graph and release images.

References: v2.1.0 docker/docker-compose.yaml, scripts/deploy.sh,
backend/Dockerfile, frontend/Dockerfile; artifact provenance in pins.json.
Only the installer writes the owned prefix/state; nothing is installed by tests.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PREFIX = Path.home() / ".local/share/codex-ecosystem/tools/deerflow-2.1.0"
STATE = Path.home() / ".local/state/native-agent-stack/runtime-workers/deerflow"
OWNER = "com.native-agent-stack.owner=gpt6-omniroute-framework-integration"


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def sha(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def expand(value, values):
    if isinstance(value, str):
        return re.sub(r"\$\{([A-Z_]+)\}", lambda m: str(values[m[1]]), value)
    if isinstance(value, dict):
        return {k: expand(v, values) for k, v in value.items()}
    if isinstance(value, list):
        return [expand(v, values) for v in value]
    return value


def mount(source, target, read_only=True):
    return {"type": "bind", "source": str(source), "target": str(target),
            "read_only": read_only, "bind": {"create_host_path": False}}


def dependency_mount(item, settings, prefix):
    """Allow only resolved adopted executable/tool roots and declared collections.

    Compose-spec@914ec15d 05-services.md volumes long syntax; never mount a
    credential store via an ancestor or a symlink under an otherwise allowed root.
    """
    source, target = Path(item["source"]), Path(item["target"])
    real = source.resolve()
    home = Path.home().resolve()
    eco = Path(settings["variables"]["ECO_ROOT"]).resolve()
    allowed = [eco / "bin"] + [eco / "tools" / name for name in (
        "context-mode-1.0.169", "serena-0.1.4", "socraticode-1.15.0", "qmd-2.8.3")]
    # Versioned native tool prefixes from the host declaration are allowed only
    # beneath tools, and must resolve there (no symlink escape to home stores).
    is_tool = (real.is_relative_to(eco / "tools") and len(real.relative_to(eco / "tools").parts) >= 1
               and re.fullmatch(r"[a-zA-Z0-9_.-]+-[0-9][a-zA-Z0-9_.-]*", real.relative_to(eco / "tools").parts[0]))
    allowed += [Path(c["path"]).resolve() for c in settings.get("qmd_snapshot", {}).get("collections", {}).values()]
    protected = [home / n for n in (".config", ".codex", ".claude", ".ssh", ".aws", ".gnupg",
                 ".local/share/omniroute", ".local/share/omniroute-fw")]
    protected.append(Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))) / "native-agent-stack")
    if (not source.is_absolute() or source != target or not item.get("read_only", True)
            or home.is_relative_to(real) or real == eco or Path(prefix).resolve().is_relative_to(real)
            or any(real.is_relative_to(p.resolve()) or p.resolve().is_relative_to(real) for p in protected)
            or real.name.endswith(".sock") or not (real in allowed or is_tool)):
        raise ValueError("MCP mounts must resolve to allowed dependency/collection roots, never credentials")
    return mount(real, target)


def host_settings(path):
    path = Path(path).resolve()
    if path.stat().st_mode & 0o077:
        raise ValueError("private host file must have mode 0600")
    settings = read(path)
    if "/ABSOLUTE/" in json.dumps(settings) or "LOCAL_QDRANT_PORT" in json.dumps(settings):
        raise ValueError("fill the private host file before installing")
    for name in ("ECO_ROOT", "HOST_PATH", "QDRANT_URL", "EMBED_URL"):
        if not settings["variables"].get(name):
            raise ValueError("missing private host variable")
    # These are already-local services. Never route embeddings through OmniRoute.
    for name in ("QDRANT_URL", "EMBED_URL"):
        if not re.fullmatch(r"10\.0\.2\.2:[0-9]{2,5}", settings["variables"][name]):
            raise ValueError("container service endpoints must use the measured rootless host address")
    if settings["variables"]["EMBED_URL"].endswith(":20128"):
        raise ValueError("OmniRoute does not serve embeddings")
    return settings


def worker_model(settings):
    model = settings.get("model") or read(HERE / "defaults.json")["model"]
    if not isinstance(model, str) or model not in {
        "cx/gpt-6.1-sol", "cx/gpt-6.1-sol-max", "cx/gpt-6-sol-max",
        "cx/gpt-6-astra", "cx/gpt-6-astra-max", "sharedgw/gpt-6-astra-max",
    }:
        raise ValueError("worker/judgment roles require an approved GPT-6 gateway route")
    return model


def arm_settings(settings, arm=None):
    """Round-3 gateway-owner contract; never infer the arm from a model slug.

    DeerFlow@345f08be config/app_config.py:432,565 resolves $VAR model fields.
    The control override preserves the requested approved GPT-6 model ID.
    """
    arm = arm if arm is not None else os.environ.get("RUNTIME_WORKER_ARM", "control")
    if arm not in {"control", "engines-on"}:
        raise ValueError("RUNTIME_WORKER_ARM must be control or engines-on")
    model = "sharedgw/gpt-6-astra-max"
    port = 20129
    if arm == "control":
        model = worker_model({"model": os.environ.get("DEERFLOW_CONTROL_MODEL") or settings.get("model")})
        if not model.startswith("cx/"):
            raise ValueError("the control arm requires a cx/ GPT-6 route")
        port = 20128
    headers = ["Idempotency-Key", "x-omniroute-session"]
    if arm == "engines-on":
        headers.append("x-omniroute-compression")
    return {"arm": arm, "model": model, "base_url": f"http://10.0.2.2:{port}/v1",
            "host_base_url": f"http://127.0.0.1:{port}/v1", "reasoning_effort": "max",
            "header_names": sorted(headers)}


def usage_database(arm):
    if arm not in {"control", "engines-on"}:
        raise ValueError("invalid arm")
    return Path.home() / ".local/share" / ("omniroute" if arm == "control" else "omniroute-fw") / "storage.sqlite"


def render(settings, prefix, state):
    """Render secrets-free model/MCP config and explicit private bind mounts."""
    prefix, state = Path(prefix), Path(state)
    defaults, pins = read(HERE / "defaults.json"), read(HERE / "pins.json")
    values = dict(settings["variables"])
    values.update({"IMAGE_" + k.upper(): v for k, v in pins["images"].items()})
    arm = arm_settings(settings)
    values.update({"DEERFLOW_MODEL": arm["model"], "DEERFLOW_BASE_URL": arm["base_url"],
                   "RUNTIME_WORKER_ARM": arm["arm"]})
    config = read(HERE / "config.yaml.template")
    ext = expand(read(HERE / "extensions_config.json.template"), values)
    ext["mcpServers"]["qmd"]["env"].update({
        "PATH": values["ECO_ROOT"] + "/bin:" + values["HOST_PATH"],
        "XDG_CONFIG_HOME": "/state/mcp/qmd/config",
        "XDG_CACHE_HOME": "/state/mcp/qmd/cache",
    })
    cfg = state / "config"
    write(cfg / "config.yaml", config)  # JSON is valid YAML.
    write(cfg / "extensions_config.json", ext)
    proxy = (HERE / "egress.conf.template").read_text().replace("GATEWAY_ORIGIN", arm["base_url"].removesuffix("/v1"))
    (cfg / "egress.conf").write_text(proxy)
    (cfg / "egress.conf").chmod(0o644)
    cfg.chmod(0o755)  # Config contains no secrets; nginx's non-root UID can read it.
    compose = expand(read(HERE / "compose.json.template"), values)
    s = compose["services"]
    for service in (s["gateway"], s["egress"]):
        service["labels"].update({"com.native-agent-stack." + k: arm[k] for k in ("arm", "model", "base_url")})
    s["gateway"]["environment"]["DEERFLOW_SESSION_NAMESPACE"] = settings["session_namespace"]
    s["gateway"]["env_file"] = [str(state / "private.env")]
    s["frontend"]["env_file"] = [str(state / "private.env")]
    s["gateway"]["volumes"] = [
        mount(prefix / "runtime", "/runtime"), mount(cfg, "/config"),
        mount(state / "data", "/state", False), mount(state / "work", "/work", False),
        # Supported legacy custom category; the coordinator owns installation.
        mount(state / "work/.agents/skills", "/skills/custom"),
        mount(state / "work/.agents/skills", "/work/.agents/skills"),
    ]
    for item in settings["mcp_mounts"]:
        s["gateway"]["volumes"].append(dependency_mount(item, settings, prefix))
    s["redis"]["volumes"] = [mount(state / "redis", "/data", False),
                                mount(prefix / "runtime", "/runtime"),
                                mount(state / "redis-password", "/run/secrets/redis-password")]
    s["gateway"]["volumes"].append(mount(state / "redis-password", "/run/secrets/redis-password"))
    s["egress"]["volumes"] = [mount(cfg / "egress.conf", "/config/egress.conf")]
    s["frontend"]["volumes"] = [mount(prefix / "runtime", "/runtime")]
    s["nginx"]["volumes"] = [mount(prefix / "runtime", "/runtime"),
                                  mount(prefix / "source/docker/nginx/nginx.conf", "/config/nginx.conf")]
    write(state / "compose.json", compose)
    return compose


def docker(settings, *args, **kwargs):
    return subprocess.run([settings["docker_bin"], "--context", "rootless", *args],
                          check=True, **kwargs)


def require_rootless(settings):
    info = json.loads(docker(settings, "info", "--format", "{{json .SecurityOptions}}",
                             capture_output=True, text=True).stdout)
    if not any("rootless" in option for option in info):
        raise ValueError("the selected Docker context must be rootless")


def install_skills(workspace):
    """Coordinator's project/universal extension is pending its separate PR.

    No direct writes, symlinks, bundled-public fallback or alternative installer.
    Source: tools/adoption/install_skills.py and the Round-2 skills contract.
    """
    subprocess.run([
        sys.executable, str(REPO / "tools/adoption/install_skills.py"),
        "--manifest", str(REPO / "blueprints/runtime-workers/skills/manifest.json"),
        "--project-dir", str(workspace), "--agent", "universal",
    ], check=True)


def install_grader(prefix):
    """GAIA v0.22.0 install with uv@0.12.17 generated hashes; no sdist builds."""
    pins = read(HERE / "pins.json")["grader"]
    lock = HERE / pins["lock_file"]
    if sha(lock) != pins["lock_sha256"]:
        raise ValueError("grader lock hash mismatch")
    if sys.version_info[:2] != (3, 13):
        raise ValueError("grader lock targets CPython 3.13 on Linux x86_64")
    environment = Path(prefix) / "grader"
    subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
    subprocess.run([str(environment / "bin/python"), "-m", "pip", "install",
                    "--require-virtualenv", "--no-cache-dir", "--disable-pip-version-check",
                    "--require-hashes", "--only-binary=:all:", "--no-deps", "-r", str(lock)], check=True)
    subprocess.run([str(environment / "bin/python"), "-m", "pip", "check"], check=True)
    subprocess.run([str(environment / "bin/python"), "-c",
                    "import importlib.metadata as m; assert m.version('inspect-ai') == '0.3.271'; "
                    "assert m.version('inspect-evals') == '0.22.0'"], check=True)


def seed_qmd(settings, state):
    """QMD 2.8.3 collections.ts:101-125, store.ts:636-653,1181-1270.

    A consistent native SQLite backup seeds owned writable state. Never open the
    shared source writable, copy a live WAL database as a plain file, or index.
    """
    allowed = set(read(HERE / "runtime/tool-policy.json")["qmd_collections"])
    spec = settings["qmd_snapshot"]
    if set(spec["collections"]) != allowed:
        raise ValueError("QMD snapshot must configure exactly the four adopted collections")
    collections = {}
    for name, value in spec["collections"].items():
        # Preserve only the native collection path/pattern, never update hooks.
        if not Path(value["path"]).is_absolute():
            raise ValueError("QMD source collection paths must be absolute")
        collections[name] = {"path": value["path"], "pattern": value.get("pattern", "**/*.md")}
    root = Path(state) / "qmd-seed"
    destination = root / "cache/qmd/native-agent-stack-catalog.sqlite"
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not destination.exists():
        temporary = destination.with_suffix(".part")
        source_uri = Path(spec["database"]).resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(source_uri, uri=True)) as source:
            counts = dict(source.execute("SELECT collection, COUNT(*) FROM documents GROUP BY collection"))
            if set(counts) != allowed or not all(counts.values()):
                raise ValueError("QMD source must contain nonempty documents from exactly the adopted collections")
            with closing(sqlite3.connect(temporary)) as output:
                source.backup(output)
        temporary.chmod(0o600)
        temporary.replace(destination)
        write(root / "snapshot.json", {"collections": counts, "sha256_at_capture": sha(destination),
                                       "evidence_class": "retained local index snapshot, not new indexing"})
    write(root / "config/qmd/native-agent-stack-catalog.yml", {"collections": collections})


def install_entrypoints(prefix):
    """Ship the reviewed wrapper and its configuration beside the native skill adapter."""
    prefix = Path(prefix)
    for name in ("recipe.py", "dispatch.py", "deerflow-run", "defaults.json", "pins.json",
                 "run-e2e.sh", "lifecycle.sh", "compose.json.template", "config.yaml.template",
                 "extensions_config.json.template", "egress.conf.template"):
        shutil.copy2(HERE / name, prefix / name)
    for name in ("deerflow-run", "run-e2e.sh", "lifecycle.sh"):
        (prefix / name).chmod(0o700)


def install(host_file):
    os.umask(0o077)
    settings = host_settings(host_file)
    pins = read(HERE / "pins.json")
    require_rootless(settings)
    for folder in (PREFIX, STATE, STATE / "downloads", STATE / "config", STATE / "data",
                   STATE / "work", STATE / "redis", STATE / "runs"):
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        folder.chmod(0o700)
    with (STATE / "install.lock").open("w") as lockfile:
        import fcntl
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Fail here if the coordinator's manifest/CLI extension is not merged.
        install_skills(STATE / "work")
        install_grader(PREFIX)
        archive = STATE / "downloads/source.tar.gz"
        if not archive.exists():
            temporary = archive.with_suffix(".part")
            with urllib.request.urlopen(pins["archive"]["url"], timeout=120) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
            if sha(temporary) != pins["archive"]["sha256"]:
                raise ValueError("source archive hash mismatch; partial download retained")
            temporary.replace(archive)
        if sha(archive) != pins["archive"]["sha256"]:
            raise ValueError("source archive hash mismatch")
        source = PREFIX / "source"
        if not source.exists():
            with tempfile.TemporaryDirectory(dir=PREFIX) as staging:
                with tarfile.open(archive) as tar:
                    tar.extractall(staging, filter="data")
                (Path(staging) / ("deer-flow-" + pins["commit"])).rename(source)
        for name, expected in pins["lockfiles"].items():
            if sha(source / name) != expected:
                raise ValueError("upstream lockfile hash mismatch")
        seed_qmd(settings, STATE)
        if not (STATE / "data/mcp/qmd").exists():
            shutil.copytree(STATE / "qmd-seed", STATE / "data/mcp/qmd")
        for subdir in ("runtime", "e2e"):
            shutil.copytree(HERE / subdir, PREFIX / subdir, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copy2(HERE / "e2e/drive.py", PREFIX / "runtime/drive.py")
        install_entrypoints(PREFIX)
        for script in (PREFIX / "runtime").glob("*.sh"):
            script.chmod(0o755)  # Secrets-free runtime code; nginx runs as UID 101.
        # Native internal-auth token is generated once, never printed.
        # Gateway auth/config.py persists its own JWT secret under DEER_FLOW_HOME.
        env = STATE / "private.env"
        if not env.exists():
            env.write_text("DEER_FLOW_INTERNAL_AUTH_TOKEN=" + secrets.token_hex(32) + "\n")
        env.chmod(0o600)
        password = STATE / "redis-password"
        if not password.exists():
            password.write_text(secrets.token_hex(32) + "\n")
        password.chmod(0o600)
        old = read(STATE / "host.json") if (STATE / "host.json").exists() else {}
        settings["session_namespace"] = old.get("session_namespace") or secrets.token_hex(16)
        write(STATE / "host.json", settings)
        render(settings, PREFIX, STATE)
        pulled = {}
        for service, image in pins["images"].items():
            try:
                docker(settings, "image", "inspect", image, capture_output=True)
            except subprocess.CalledProcessError:
                docker(settings, "pull", "--platform", "linux/amd64", image)
            detail = json.loads(docker(settings, "image", "inspect", image, capture_output=True, text=True).stdout)[0]
            if not any(x.endswith("@" + image.split("@", 1)[1]) for x in detail.get("RepoDigests", [])):
                raise ValueError("pulled image digest mismatch")
            if service in {"gateway", "frontend"}:
                if detail["Config"].get("Labels", {}).get("org.opencontainers.image.revision") != pins["commit"]:
                    raise ValueError("release image revision mismatch")
            pulled[service] = {"reference": image, "image_id": detail["Id"]}
        write(STATE / "images.json", pulled)
        docker(settings, "compose", "-f", str(STATE / "compose.json"), "config", "--quiet")
        print("Installed pinned artifacts and rendered private configuration; no services started. Run lifecycle.sh check next.")


def lifecycle(action):
    settings = read(STATE / "host.json")
    require_rootless(settings)
    common = ["compose", "-f", str(STATE / "compose.json")]
    if action == "up":
        for status in (STATE / "dispatch").glob("*/status.json"):
            if read(status).get("status") in {"starting", "pending", "running"}:
                raise ValueError("finish or cancel active dispatches before switching the server arm")
        render(settings, PREFIX, STATE)
        docker(settings, *common, "up", "-d", "--force-recreate", "--wait", "--wait-timeout", "180", "--no-build", "--pull", "never")
    elif action == "down":
        # Literal owned names only. Preserve all application bind-mount data.
        commands = [("rm", "--force", "rw-deerflow-" + name)
                    for name in ("nginx", "frontend", "gateway", "redis", "egress")]
        commands.append(("network", "rm", "rw-deerflow-network"))
        commands.append(("network", "rm", "rw-deerflow-egress-network"))
        for command in commands:
            try:
                docker(settings, *command, capture_output=True, text=True)
            except subprocess.CalledProcessError as exc:
                if not any(reason in (exc.stderr or "").lower() for reason in ("no such container", "no such network", "network rw-deerflow-network not found")):
                    raise
    elif action == "check":
        docker(settings, *common, "run", "--rm", "--no-deps", "--name", "rw-deerflow-preflight",
               "--label", OWNER, "-T", "gateway",
               "/app/backend/.venv/bin/python", "/runtime/preflight.py")
    elif action == "upstream-tests":
        docker(settings, *common, "run", "--rm", "--no-deps", "--name", "rw-deerflow-upstream-tests",
               "--label", OWNER, "-T", "--workdir", "/app/backend", "gateway",
               "uv", "run", "--no-sync", "pytest", "-m", "not live",
               "tests/test_model_factory.py", "tests/test_mcp_client_config.py", "tests/test_client.py", "-q")
    else:
        raise ValueError("supported lifecycle actions: up, down, check, upstream-tests")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "lifecycle"])
    parser.add_argument("argument")
    args = parser.parse_args()
    try:
        install(args.argument) if args.action == "install" else lifecycle(args.argument)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        # Private paths/configuration/command environments stay out of public output.
        print("Recipe stopped: " + type(exc).__name__ + ". Inspect prerequisites in the README.")
        raise SystemExit(1) from None
