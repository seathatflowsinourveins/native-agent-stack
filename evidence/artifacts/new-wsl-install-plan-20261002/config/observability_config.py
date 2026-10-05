#!/usr/bin/env python3
"""G4 configuration transport; native validators remain the acceptance commands.

Reference: this PR: observability/backends/configure.py.
Upstream formats: OTel Contrib v0.162.0 file_storage; Grafana v13.2.3 provisioning;
Alertmanager v0.34.1 docs/configuration.md (webhook_config and telegram_config).
Private destination files are inspected by metadata only, never opened here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


PRISTINE = {
    "otel.yaml": "1bcdf496537bab925fd39b42fd5b2b8226e2d4fb4f95b3aaba1d52e23c3d731f",
    "grafana.ini": "139c743c02b428653de39bfac449a9a0f4f02f786732891715838022b25f936d",
    "alertmanager.yaml": "b4ff240a87515fa2c9b606c3570ed9c6c64dc36bd2cbad52c8ee62f22745f6a4",
    "prometheus.yaml": "1565e9df52167eb06e5b33a4d57bc45fa1f9d1bd87a1bc3c268f9a3d5f0e58c4",
}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".g4-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def private_file(path):
    """Return absent/ok/unsafe, without reading a credential or its value."""
    if not path.is_absolute():
        return "unsafe"
    try:
        info, parent = path.lstat(), path.parent.lstat()
    except FileNotFoundError:
        return "absent"
    if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.getuid() or info.st_nlink != 1
            or not stat.S_ISDIR(parent.st_mode) or stat.S_IMODE(parent.st_mode) != 0o700
            or parent.st_uid != os.getuid()):
        return "unsafe"
    inside = subprocess.run(["git", "-C", str(path.parent.resolve()), "rev-parse", "--is-inside-work-tree"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    if inside.returncode == 0 and inside.stdout.strip() == "true":
        return "unsafe"
    return "ok"


def destination():
    store = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "native-agent-stack"
    mode = os.environ.get("NATIVE_STACK_ALERT_RECEIVER", "webhook")
    if mode != "webhook":
        raise ValueError("Telegram and on-host destinations were overturned; select the approved ntfy.sh webhook")
    pointers = {"@URL_FILE@": Path(os.environ.get("NATIVE_STACK_ALERT_URL_FILE", str(store / "alertmanager-webhook-url")))}
    states = [private_file(p) for p in pointers.values()]
    if "unsafe" in states:
        raise ValueError("alert destination metadata is unsafe; require owned 0600 files in a 0700 directory outside Git worktrees")
    return mode, pointers, "absent" not in states


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("otel", "grafana", "alerting", "alerting-ready", "grafana-check"))
    parser.add_argument("--config-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    root = args.config_root
    source = args.source_root or root
    data = Path(os.environ.get("NS2604_OBSERVABILITY_DATA", str(
        Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "new-wsl-native-stack/observability")))
    if not data.is_absolute():
        raise ValueError("NS2604_OBSERVABILITY_DATA must be absolute")
    ledger_path = root / ".g4-source-digests.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}

    def publish(name, text, template=None, validate=None, owned=True):
        path = root / name
        if path.is_symlink():
            raise ValueError(f"retained symlink for {name}; migrate its owner configuration separately")
        if path.exists():
            old = path.read_text()
            if old != text and digest(old) not in (PRISTINE.get(name), ledger.get(name), digest(template or "")):
                raise ValueError(f"retained operator configuration for {name}; merge the G4 source separately")
        if validate:
            fd, temporary = tempfile.mkstemp(prefix=".g4-validate-", dir=root)
            try:
                with os.fdopen(fd, "w") as stream:
                    stream.write(text)
                result = subprocess.run(validate + [temporary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if result.returncode:
                    raise ValueError(f"upstream validator refused {name}; original retained")
            finally:
                os.unlink(temporary)
        atomic(path, text)
        if owned:
            ledger[name] = digest(text)
        else:
            ledger.pop(name, None)
            ledger.setdefault("operator_migrations", {})[name] = digest(text)
        atomic(ledger_path, json.dumps(ledger, indent=2) + "\n")

    if args.action == "otel":
        for name in ("otelcol/queue", "collector", "sdk-receipts"):
            (data / name).mkdir(parents=True, exist_ok=True, mode=0o700)
        target = root / "otel.yaml"
        if target.is_symlink():
            raise ValueError("retained symlink for otel.yaml; migrate its owner configuration separately")
        template = (source / "otel.yaml").read_text()
        backup = target.with_name("otel.yaml.pre-g4-observability")
        # Recover the earlier ledger bug as well as retaining new migrations.
        # A migration backup/receipt records operator custody, never template ownership.
        operator_custody = backup.exists() or "otel.yaml" in ledger.get("operator_migrations", {})
        if operator_custody:
            if ledger.pop("otel.yaml", None) is not None:
                atomic(ledger_path, json.dumps(ledger, indent=2) + "\n")
            if not target.exists():
                return 0
        if operator_custody or (target.exists() and digest(target.read_text()) not in (
                digest(template), PRISTINE["otel.yaml"], ledger.get("otel.yaml"))):
            # Port only the earlier repair's exact container-directory migration; preserve all pipelines.
            original = target.read_text()
            pattern = r"(?m)^(\s*directory:\s*)([\"']?)/otelcol/queue/?\2(\s*(?:#.*)?)$"
            migrated, count = re.subn(pattern, lambda m: m[1] + json.dumps(str(data / "otelcol/queue")) + m[3], original)
            if count:
                # Validate this one-time migration without acquiring operator ownership.
                try:
                    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    pass
                else:
                    with os.fdopen(fd, "w") as stream:
                        stream.write(original)
                previous = os.environ.get("NS2604_OBSERVABILITY_DATA")
                os.environ["NS2604_OBSERVABILITY_DATA"] = str(data)
                try:
                    publish("otel.yaml", migrated, template=original,
                            validate=["otelcol-contrib", "validate", "--config"], owned=False)
                finally:
                    if previous is None:
                        os.environ.pop("NS2604_OBSERVABILITY_DATA", None)
                    else:
                        os.environ["NS2604_OBSERVABILITY_DATA"] = previous
            return 0
        publish("otel.yaml", template)
    elif args.action == "grafana":
        for name in ("grafana", "grafana/logs", "grafana/plugins"):
            (data / name).mkdir(parents=True, exist_ok=True, mode=0o700)
        for name, output in (("grafana.ini", "grafana.ini"),
                             ("grafana-datasources.yaml", "grafana-provisioning/datasources/native-stack.yaml"),
                             ("grafana-dashboards.yaml", "grafana-provisioning/dashboards/native-stack.yaml"),
                             ("grafana-token-layer.json", "grafana-dashboards/token-layer.json")):
            template = (source / name).read_text()
            rendered = template.replace("@CONFIG_ROOT@", str(root)).replace("@DATA_ROOT@", str(data))
            rendered = rendered.replace("@DASHBOARD_PATH_JSON@", json.dumps(str(root / "grafana-dashboards")))
            publish(output, rendered, template)
    elif args.action == "grafana-check":
        dashboard = json.loads((root / "grafana-dashboards/token-layer.json").read_text())
        if dashboard["uid"] != "token-layer" or not dashboard["panels"]:
            raise ValueError("missing token-layer dashboard")
        for p in dashboard["panels"]:
            for target in p.get("targets", []):
                if "claude_code_" in target.get("expr", "") and "[1h]" in target["expr"] and target.get("interval") != "1m":
                    raise ValueError("hourly Claude query must have a 1m minimum step")
        for name in ("datasources", "dashboards"):
            if not (root / f"grafana-provisioning/{name}/native-stack.yaml").is_file():
                raise ValueError("missing native Grafana provisioning")
    else:
        if args.action == "alerting":
            # Install source/receiver wiring together for a pristine or previously owned plan.
            # Custom Prometheus configuration is retained for its owner to merge.
            publish("prometheus.yaml", (source / "prometheus.yaml").read_text())
        mode, pointers, ready = destination()
        if not ready:
            print("needs_user: supply the selected ntfy.sh topic URL with ?template=alertmanager in its owned 0600 URL file; the disarmed placeholder cannot accept delivery", file=sys.stderr)
            return 78 if args.action == "alerting-ready" else 0
        template = (source / ("alertmanager-telegram.yaml" if mode == "telegram" else "alertmanager-webhook.yaml")).read_text()
        rendered = template
        for marker, pointer in pointers.items():
            rendered = rendered.replace(marker, json.dumps(str(pointer)))
        if args.action == "alerting-ready":
            if not (root / "alertmanager.yaml").is_file() or (root / "alertmanager.yaml").read_text() != rendered:
                raise ValueError("destination exists but is not wired; rerun install.sh --only alerting and restart Alertmanager")
        else:
            tool_root = Path(os.environ["tool_root"])
            amtool = str(tool_root / "alertmanager/alertmanager-0.34.1.linux-amd64/amtool")
            publish("alertmanager.yaml", rendered, (source / "alertmanager.yaml").read_text(),
                    validate=[amtool, "check-config"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        # Do not relay native validator output or credential values.
        print(str(error), file=sys.stderr)
        sys.exit(1)
