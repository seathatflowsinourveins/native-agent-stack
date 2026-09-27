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
import tarfile
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PREFIX = Path.home() / ".local/share/codex-ecosystem/tools/deerflow-2.1.0"
STATE = Path.home() / ".local/state/native-agent-stack/runtime-workers/deerflow"


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
    if Path(settings["skills_root"]).resolve() != (Path.home() / ".agents/skills").resolve():
        raise ValueError("skills_root must reference the adopted skills directory")
    return settings


def render(settings, prefix, state):
    """Render secrets-free model/MCP config and explicit private bind mounts."""
    prefix, state = Path(prefix), Path(state)
    defaults, pins = read(HERE / "defaults.json"), read(HERE / "pins.json")
    values = dict(settings["variables"])
    values.update({"IMAGE_" + k.upper(): v for k, v in pins["images"].items()})
    values["DEERFLOW_MODEL"] = settings.get("model") or defaults["model"]
    config = read(HERE / "config.yaml.template")
    config["models"][0]["base_url"] = defaults["container_gateway"]
    ext = expand(read(HERE / "extensions_config.json.template"), values)
    ext["mcpServers"]["qmd"]["env"].update({
        "PATH": values["ECO_ROOT"] + "/bin:" + values["HOST_PATH"],
        "XDG_CONFIG_HOME": "/state/mcp/qmd/config",
        "XDG_CACHE_HOME": "/state/mcp/qmd/cache",
    })
    cfg = state / "config"
    write(cfg / "config.yaml", config)  # JSON is valid YAML.
    write(cfg / "extensions_config.json", ext)
    compose = expand(read(HERE / "compose.json.template"), values)
    s = compose["services"]
    s["gateway"]["environment"]["DEERFLOW_SESSION_NAMESPACE"] = settings["session_namespace"]
    s["gateway"]["env_file"] = [str(state / "private.env")]
    s["frontend"]["env_file"] = [str(state / "private.env")]
    s["gateway"]["volumes"] = [
        mount(prefix / "runtime", "/runtime"), mount(cfg, "/config"),
        mount(state / "data", "/state", False), mount(state / "work", "/work", False),
        mount(state / "skills", "/skills"),
        mount(settings["skills_root"], settings["skills_root"]),
        mount(prefix / "source/skills/public", "/upstream-skills"),
    ]
    for item in settings["mcp_mounts"]:
        source, target = Path(item["source"]), Path(item["target"])
        # Pin dependencies at their real paths so executable symlinks stay valid.
        # Forbid broad home/ecosystem/credential mounts and the installer oracle.
        forbidden = (Path.home(), Path(settings["variables"]["ECO_ROOT"]), Path("/"))
        if (not source.is_absolute() or source != target or source in forbidden
                or source == prefix or prefix.is_relative_to(source)
                or any(p in {".ssh", ".codex", ".claude", ".aws", ".gnupg"} for p in source.parts)
                or source.name.endswith(".sock")):
            raise ValueError("MCP mounts must be narrow dependency/index paths, not credentials or sockets")
        if not item.get("read_only", True):
            raise ValueError("shared MCP dependencies/index mounts must be read-only")
        s["gateway"]["volumes"].append(mount(source, target))
    s["redis"]["volumes"] = [mount(state / "redis", "/data", False),
                                mount(prefix / "runtime", "/runtime")]
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


def link(directory, target):
    if directory.is_symlink():
        if os.readlink(directory) != str(target):
            raise ValueError("refusing to replace an unrelated skill symlink")
    elif directory.exists():
        raise ValueError("refusing to replace an existing skill directory")
    else:
        directory.symlink_to(target, target_is_directory=True)


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
    root = Path(state) / "data/mcp/qmd"
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


def install(host_file):
    os.umask(0o077)
    settings = host_settings(host_file)
    pins = read(HERE / "pins.json")
    require_rootless(settings)
    for folder in (PREFIX, STATE, STATE / "downloads", STATE / "config", STATE / "data",
                   STATE / "work", STATE / "redis", STATE / "runs", STATE / "skills/custom"):
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        folder.chmod(0o700)
    with (STATE / "install.lock").open("w") as lockfile:
        import fcntl
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
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
        manifest = read(REPO / "adoption/skills/manifest.json")
        selected = [s for s in manifest["skills"] if s.get("codex_enabled")]
        for skill in selected:
            target = Path(settings["skills_root"]) / skill["name"]
            if sha(target / "SKILL.md") != skill["skill_md_sha256"]:
                raise ValueError("adopted skill differs from its manifest pin: " + skill["name"])
            link(STATE / "skills/custom" / skill["name"], target)
        link(STATE / "skills/public", Path("/upstream-skills"))
        seed_qmd(settings, STATE)
        for subdir in ("runtime", "e2e"):
            shutil.copytree(HERE / subdir, PREFIX / subdir, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copy2(HERE / "e2e/task.md", PREFIX / "runtime/task.md")
        shutil.copy2(HERE / "e2e/drive.py", PREFIX / "runtime/drive.py")
        shutil.copy2(HERE / "pins.json", PREFIX / "pins.json")
        for script in (PREFIX / "runtime").glob("*.sh"):
            script.chmod(0o700)
        # Native internal-auth token is generated once, never printed.
        # Gateway auth/config.py persists its own JWT secret under DEER_FLOW_HOME.
        env = STATE / "private.env"
        if not env.exists():
            env.write_text("DEER_FLOW_INTERNAL_AUTH_TOKEN=" + secrets.token_hex(32) + "\n")
        env.chmod(0o600)
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
        docker(settings, *common, "up", "-d", "--wait", "--wait-timeout", "180", "--no-build", "--pull", "never")
    elif action == "down":
        docker(settings, *common, "down", "--timeout", "30")
    elif action == "check":
        docker(settings, *common, "run", "--rm", "--no-deps", "-T", "gateway",
               "/app/backend/.venv/bin/python", "/runtime/preflight.py")
    elif action == "upstream-tests":
        docker(settings, *common, "run", "--rm", "--no-deps", "-T", "--workdir", "/app/backend", "gateway",
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
