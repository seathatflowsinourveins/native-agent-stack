#!/usr/bin/env python3
"""G4 configuration transport; native validators remain the acceptance commands.

Reference: this PR: observability/backends/configure.py.
Upstream formats: OTel Contrib v0.162.0 file_storage; Grafana v13.2.3 provisioning;
Alertmanager v0.34.1 docs/configuration.md (webhook_config and telegram_config).
Private destination files are inspected by metadata only, never opened here.
The grafana action also renders the research dashboard's emitter units (observability/grand-dashboard/install.py
adapted in ns2604-research-progress.service and .timer) into <config-root>/systemd/; install.sh installs them.
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
# (template in config/, published path under the config root); the grafana action renders each.
GRAFANA_FILES = (
    ("grafana.ini", "grafana.ini"),
    ("grafana-datasources.yaml", "grafana-provisioning/datasources/native-stack.yaml"),
    ("grafana-dashboards.yaml", "grafana-provisioning/dashboards/native-stack.yaml"),
    ("grafana-token-layer.json", "grafana-dashboards/token-layer.json"),
    ("grafana-research-grand.json", "ecosystem-grafana-dashboards/research-grand.json"),
    ("grafana-ecosystem-native.json", "ecosystem-grafana-dashboards/ecosystem-native.json"),
    ("grafana-native-foundation-data.json", "ecosystem-grafana-dashboards/native-foundation-data.json"),
    ("grafana-lanes.json", "grafana-dashboards/lanes.json"),
    ("ns2604-research-progress.service", "systemd/ns2604-research-progress.service"),
    ("ns2604-research-progress.timer", "systemd/ns2604-research-progress.timer"),
)
# Filename stems and provisioned UIDs are separate native Grafana identifiers.
DASHBOARD_UIDS = {"research-grand": "research-grand", "ecosystem-native": "ecosystem-native",
                  "native-foundation-data": "native-foundation-data", "lanes": "cc-lanes"}
EMITTER_UNITS = ("ns2604-research-progress.service", "ns2604-research-progress.timer")
UNIT_PATH_UNSAFE = re.compile(r"[\s%\"'\\$]")
CODEX_TOKEN_METRIC = re.compile(r"\b(?:ecosystem_)?codex_turn_token_usage_sum\b")
CODEX_TOKEN_DESCRIPTION = (
    "Lower bound until deployed created-timestamp-zero-ingestion and a newly born single-turn "
    "counter reconciliation pass. NativeStack2604 has no proposed anchored-query flag. "
    "Prometheus edge extrapolation can overcount; it does not prove complete first samples. "
    "Input/cache and output/reasoning subsets are not additive. Never add this total to Loki request usage."
)


def qualify_codex_token_panels(board):
    """NativeStack2604-only policy shared by standalone provisioning and the repo renderer.

    Uses the existing Grafana v13.2.3 JSON panel/target format. Keep this
    stdlib-only helper in the installed configuration script, not an uncopied
    repository dependency. Workstation templates are unchanged.
    """
    def panels(items):
        for panel in items:
            yield panel
            yield from panels(panel.get("panels", []))

    for panel in panels(board.get("panels", [])):
        source = panel.get("datasource") or {}
        for target in panel.get("targets", []):
            effective = target.get("datasource") or source
            prometheus = isinstance(effective, dict) and (
                effective.get("type") == "prometheus"
                or effective.get("uid") in ("ecosystem-prometheus", "ns2604-prometheus")
            )
            if prometheus and CODEX_TOKEN_METRIC.search(target.get("expr", "")):
                if "lower bound" not in panel.get("title", "").lower():
                    panel["title"] += " — lower bound until step 7 read-back"
                panel["description"] = CODEX_TOKEN_DESCRIPTION
                break
    return board


# Exact user-designated retired host renders; their bytes were hashed, but their
# historical rendered inputs were not reconstructed. Never recognize a header
# or acquire an operator-custody file solely because its digest is listed here.
HISTORICAL_PLAN_RENDER_DIGESTS = {
    "prometheus.yaml": {"1568a5025ee2e6cab6e0a853031e438d7f04ae03a0d700aa5eb6a406b3e89e65"},
    "otel.yaml": {"d928bbb9dbd61a5245933e94c4e371289e8b7bf0013488116c6d76de5c346a1e"},
}


# Co-op A30 (2026-10-05): exact retired provisioning paths remain custodian-owned.
# Their historical digests are provenance, never permission to publish/migrate.
# Grafana@6193dc03:docs/sources/administration/provisioning/index.md:90,339,371.
LEGACY_GRAFANA_PATHS = (
    "grafana-provisioning/datasources/ns2604.yaml",
    "grafana-provisioning/dashboards/token-layer.yaml",
    "grafana-dashboards/token-layer/token-layer.json",
)


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
    if mode not in ("webhook", "telegram", "on-host"):
        raise ValueError("NATIVE_STACK_ALERT_RECEIVER must be webhook, telegram or on-host")
    if mode == "telegram":
        pointers = {"@BOT_TOKEN_FILE@": Path(os.environ.get("NATIVE_STACK_ALERT_BOT_TOKEN_FILE", str(store / "alertmanager-telegram-token"))),
                    "@CHAT_ID_FILE@": Path(os.environ.get("NATIVE_STACK_ALERT_CHAT_ID_FILE", str(store / "alertmanager-telegram-chat-id")))}
    else:
        pointers = {"@URL_FILE@": Path(os.environ.get("NATIVE_STACK_ALERT_URL_FILE", str(store / "alertmanager-webhook-url")))}
    states = [private_file(p) for p in pointers.values()]
    if "unsafe" in states:
        raise ValueError("alert destination metadata is unsafe; require owned 0600 files in a 0700 directory outside Git worktrees")
    return mode, pointers, "absent" not in states


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("otel", "grafana", "alerting", "alerting-ready", "grafana-check", "prometheus"))
    parser.add_argument("--config-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--tools-root", type=Path)
    parser.add_argument("--plan-file", type=Path)
    # The emitter unit runs progress.py from this checkout. Default: three levels above the plan folder, as
    # install.sh derives repo_root.
    parser.add_argument("--repo-root", type=Path)
    args = parser.parse_args()
    root = args.config_root
    source = args.source_root or root
    if args.action in ("grafana", "grafana-check"):
        # CPython@v3.13.16:Lib/pathlib/_abc.py:432-437, unlike exists(),
        # lstat sees a dangling symlink. Check before any ledger read or write.
        for name in LEGACY_GRAFANA_PATHS:
            try:
                (root / name).lstat()
            except FileNotFoundError:
                continue
            except OSError as error:
                raise ValueError(f"needs_owner: cannot verify legacy Grafana path {name}") from error
            raise ValueError(f"needs_owner: retained legacy Grafana path {name}; co-op custody required")
    data = Path(os.environ.get("NS2604_OBSERVABILITY_DATA", str(
        Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "new-wsl-native-stack/observability")))
    if not data.is_absolute():
        raise ValueError("NS2604_OBSERVABILITY_DATA must be absolute")
    ledger_path = root / ".g4-source-digests.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}

    def known_plan_render(name, text, template):
        if name in ledger.get("operator_migrations", {}):
            return False
        value = digest(text)
        return (value in (PRISTINE.get(name), ledger.get(name),
                         digest(template) if template is not None else None)
                or value in HISTORICAL_PLAN_RENDER_DIGESTS.get(name, set()))

    def publish(name, text, template=None, validate=None, owned=True):
        path = root / name
        if owned and name in ledger.get("operator_migrations", {}):
            raise ValueError(f"needs_owner: retained operator custody for {name}")
        if path.is_symlink():
            raise ValueError(f"needs_owner: retained symlink for {name}; migrate its owner configuration separately")
        if path.exists():
            old = path.read_text()
            if old != text and not ((not owned and old == template) or known_plan_render(name, old, template)):
                raise ValueError(f"needs_owner: retained operator configuration for {name}; merge the G4 source separately")
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

    if args.action == "prometheus":
        # Render a candidate only. The co-op owns active-unit apply and activation.
        # native-agent-stack@f946c6d4:observability/backends/configure.py:100,107-110.
        if args.tools_root is None or args.plan_file is None:
            raise ValueError("prometheus rendering requires --tools-root and --plan-file")
        rows = [row for row in json.loads(args.plan_file.read_text())["owners"]
                if row.get("slot") == "prometheus"]
        if len(rows) != 1:
            raise ValueError("prometheus rendering requires exactly one plan row")
        row = rows[0]
        release = row.get("release")
        features = (row.get("service") or {}).get("enable_features")
        port = (row.get("service") or {}).get("port")
        if not isinstance(release, str) or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", release):
            raise ValueError("invalid plan Prometheus release")
        if (not isinstance(features, list) or not features
                or any(not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", value) for value in features)
                or len(set(features)) != len(features)):
            raise ValueError("invalid plan Prometheus feature list")
        if type(port) is not int or not 0 < port < 65536:
            raise ValueError("invalid plan Prometheus loopback port")
        tools = args.tools_root
        for path in (root, data, tools):
            if not path.is_absolute() or re.search(r"[\s'\"%\\$]", str(path)):
                raise ValueError("unit render paths must be absolute without whitespace, quotes, percent, backslash or dollar")
        markers = {
            "@CONFIG_ROOT@": str(root),
            "@DATA_ROOT@": str(data),
            "@PROMETHEUS_TOOL@": str(tools / "prometheus" / ("prometheus-" + release[1:] + ".linux-amd64") / "prometheus"),
            "@PROMETHEUS_PORT@": str(port),
            "@PROMETHEUS_FEATURES@": ",".join(features),
        }
        template = (source / "ns2604-prometheus.service.example").read_text()
        rendered = template
        for marker, value in markers.items():
            rendered = rendered.replace(marker, value)
        if re.search(r"@[A-Z_]+@", rendered):
            raise ValueError("unresolved Prometheus unit template marker")
        publish("ns2604-prometheus.service", rendered, template)
    elif args.action == "otel":
        for name in ("otelcol/queue", "collector", "sdk-receipts"):
            (data / name).mkdir(parents=True, exist_ok=True, mode=0o700)
        target = root / "otel.yaml"
        if target.is_symlink():
            raise ValueError("retained symlink for otel.yaml; migrate its owner configuration separately")
        template = (source / "otel.yaml").read_text()
        backup = target.with_name("otel.yaml.pre-g4-observability")
        # Recover the earlier ledger bug as well as retaining new migrations.
        # A migration backup/receipt records operator custody, never template ownership.
        operator_custody = (backup.exists() or backup.is_symlink()
                            or "otel.yaml" in ledger.get("operator_migrations", {}))
        if operator_custody:
            if ledger.pop("otel.yaml", None) is not None:
                atomic(ledger_path, json.dumps(ledger, indent=2) + "\n")
            if not target.exists():
                print("needs_owner: otel.yaml is absent under retained operator custody", file=sys.stderr)
                return 3
        if operator_custody or (target.exists() and not known_plan_render("otel.yaml", target.read_text(), template)):
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
            print("needs_owner: retained operator otel.yaml; G4 source was not applied", file=sys.stderr)
            return 3
        publish("otel.yaml", template)
    elif args.action == "grafana":
        for name in ("grafana", "grafana/logs", "grafana/plugins", "grand-dashboard"):
            (data / name).mkdir(parents=True, exist_ok=True, mode=0o700)
        repo = (args.repo_root or source / "../../../..").resolve()
        if not (repo / "observability/grand-dashboard/progress.py").is_file():
            raise ValueError("--repo-root must be a repository checkout that holds observability/grand-dashboard/progress.py")
        if UNIT_PATH_UNSAFE.search(str(repo)) or UNIT_PATH_UNSAFE.search(str(data)):
            raise ValueError("emitter unit paths require no whitespace, percent signs, quotes, backslashes or dollar signs")
        for name, output in GRAFANA_FILES:
            template = (source / name).read_text()
            rendered = template.replace("@CONFIG_ROOT@", str(root)).replace("@DATA_ROOT@", str(data))
            rendered = rendered.replace("@DASHBOARD_PATH_JSON@", json.dumps(str(root / "grafana-dashboards")))
            rendered = rendered.replace("@ECOSYSTEM_DASHBOARD_PATH_JSON@", json.dumps(str(root / "ecosystem-grafana-dashboards")))
            rendered = rendered.replace("@REPO_ROOT@", str(repo))
            if output.endswith(".json"):
                # Includes token-layer, which is published directly from its
                # native template rather than through the repository renderer.
                rendered = json.dumps(qualify_codex_token_panels(json.loads(rendered)), indent=2) + "\n"
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
        # The ported dashboards query this host's datasources and metric names, and link no old-host port.
        providers = (root / "grafana-provisioning/dashboards/native-stack.yaml").read_text()
        if json.dumps(str(root / "ecosystem-grafana-dashboards")) not in providers:
            raise ValueError("missing the Ecosystem dashboard provider")
        if json.dumps(str(root / "grafana-dashboards")) not in providers or "folder: Token efficiency" not in providers:
            raise ValueError("missing the Token efficiency dashboard provider")
        for stem, uid in DASHBOARD_UIDS.items():
            directory = "grafana-dashboards" if stem == "lanes" else "ecosystem-grafana-dashboards"
            text = (root / directory / f"{stem}.json").read_text()
            board = json.loads(text)
            if board["uid"] != uid or not board["panels"]:
                raise ValueError(f"missing {uid} dashboard")
            if re.search(r'"uid": "ecosystem-(?:loki|prometheus)"|(?<![\w:])ecosystem_(?!lane\b)|127\.0\.0\.1:13[01]00', text):
                raise ValueError(f"{uid} still targets the workstation's datasources, metric prefix or ports")
        if not re.search(r"(?m)^\[news\]\nnews_feed_enabled = false$", (root / "grafana.ini").read_text()):
            raise ValueError("grafana.ini must disable the news feed")
        units = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "systemd/user"
        for name in EMITTER_UNITS:
            rendered = (root / "systemd" / name).read_text()
            if re.search(r"@[A-Z_]+@", rendered):
                raise ValueError(f"{name} has an unrendered placeholder")
            if not (units / name).is_file() or (units / name).read_text() != rendered:
                raise ValueError(f"{name} is not installed as rendered; rerun install.sh --only grafana")
    else:
        if args.action == "alerting":
            # Install source/receiver wiring together for a pristine or previously owned plan.
            # Custom Prometheus configuration is retained for its owner to merge.
            publish("prometheus.yaml", (source / "prometheus.yaml").read_text())
        mode, pointers, ready = destination()
        if not ready:
            print("needs_user: choose the alert destination and supply its private destination file(s); disarmed placeholder retained", file=sys.stderr)
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
