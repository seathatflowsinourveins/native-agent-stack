#!/usr/bin/env python3
"""Frozen host E2E. Two native provider arms, plus bounded upstream container MCP.

Sources: upstream pricing example, MCP socket example, stdlib http.server;
see README for scope and native-vs-local evidence boundaries.
"""
import argparse
import asyncio
import contextlib
import functools
import http.server
import importlib.metadata
import json
import os
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from host import load_host, locations, private_file
from worker import extract, model_for, arm_settings, selected_arm
from receipt import make_receipt, exit_code
from grade import grade, run_controls, observation
from dispatch import write_json, finish, announce


def now():
    return datetime.now(timezone.utc).isoformat()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def compression_snapshot():
    # OmniRoute@a58000c7 src/app/api/analytics/compression/route.ts:13-24.
    # All-time cumulative counters avoid a moving 24-hour boundary. No auth
    # store is read; a management-auth refusal is incomplete evidence.
    try:
        with urllib.request.urlopen("http://127.0.0.1:20129/api/analytics/compression?since=all", timeout=5) as response:
            data = json.load(response)
        return {k: data[k] for k in ("totalRequests", "totalTokensSaved")
                if type(data.get(k)) is int and data[k] >= 0}
    except (OSError, ValueError, KeyError):
        return {}


def main(argv=None):
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--arm", choices=("control", "engines-on", "comparison"), default=None)
    args = parser.parse_args(argv)
    arm = args.arm or selected_arm()
    directory = args.run_dir.resolve()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not (directory / "status.json").exists():
        write_json(directory / "status.json", {"arm": arm, "state": "running", "exit_code": None,
            "receipt_path": str(directory / "receipt.json"), "status_path": str(directory / "status.json")})
    write_json(directory / "receipt.json", {"passed": False, "outcome": "incomplete_evidence"})
    metadata = {"framework_version": None, "start": now(), "selected_arms": [arm], "arms": {}, "probes": {},
                "skills_at_start": {"names": [], "status": "no native skill inventory/loader in reviewed v0.9.4"}}
    correlations = {}
    server, server_thread, container_attempted = None, None, False
    lifecycle = (directory / "lifecycle.log").open("w")
    try:
        config = json.loads((ROOT / "config/worker.json").read_text())
        # Exactly one explicit arm per run; dispatch serializes runs on this host.
        config["e2e"]["arms"] = [arm]
        route = arm_settings(config, arm)
        host = load_host()
        os.chdir(host["working_directory"])
        _, state = locations()
        metadata["framework_version"] = importlib.metadata.version("crawl4ai")
        executable = os.environ["NAS_CRAWL4AI_GRADER"]
        metadata["grader_controls"] = run_controls(directory / "controls", executable)
        for name, expected in (("known-pass", 0), ("known-fail", 100), ("malformed-output", 100)):
            control = observation(directory / "controls" / name)
            if control["status"] != "observed" or control["exit_code"] != expected or control["passed"] is not (expected == 0):
                raise ValueError("upstream grader controls failed; no model trial attempted")
        for arm in config["e2e"]["arms"]:
            model_for(config, arm)  # refuse unavailable routes before starting resources
        server = http.server.ThreadingHTTPServer(("127.0.0.1", host["fixture_port"]),
            functools.partial(QuietHandler, directory=str(ROOT / "e2e/fixtures")))
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        # Independent work continues even when the known WS source gap fails.
        try:
            from mcp_probe import probe
            container_attempted = True
            subprocess.run(["bash", str(ROOT / "container.sh"), "start-e2e"], check=True,
                           stdout=lifecycle, stderr=subprocess.STDOUT, timeout=90,
                           env=dict(os.environ, CRAWL4AI_ARM=arm))
            base = f"http://127.0.0.1:{host['e2e_api_port']}"
            deadline = time.monotonic() + 90
            while True:
                try:
                    with urllib.request.urlopen(base + "/health", timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("container readiness timed out")
                    time.sleep(1)
            token_file = state / "secrets/api_token"
            private_file(token_file)
            token = token_file.read_text().strip()
            metadata["probes"] = asyncio.run(probe(base,
                f"http://10.0.2.2:{host['fixture_port']}/beacon.html", token))
            del token
        except Exception as exc:
            metadata["container_error_class"] = type(exc).__name__
            traceback.print_exc(file=lifecycle)
        for arm in config["e2e"]["arms"]:
            output = directory / arm
            output.mkdir(mode=0o700)
            route = arm_settings(config, arm)
            info = {"start": now(), "model": route["model"], "base_url": route["base_url"],
                    "expected_effort": route["expected_effort"], "gateway": route["gateway"],
                    "header_names": ["x-omniroute-session", "Idempotency-Key"] +
                        (["x-omniroute-compression"] if arm == "engines-on" else [])}
            correlations[arm] = []
            if arm == "engines-on":
                metadata["compression"] = {"before": compression_snapshot()}
            try:
                with (output / "native.log").open("w") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    info["measurements"] = asyncio.run(extract(config, arm,
                        f"http://127.0.0.1:{host['fixture_port']}", output / "result.json", output, correlations[arm]))
            except Exception as exc:
                info["error_class"] = type(exc).__name__
                with (output / "native.log").open("a") as log:
                    traceback.print_exc(file=log)
            finally:
                info["end"] = now()
                info["correlation_capture_count"] = sum(value is not None for value in correlations[arm])
                if arm == "engines-on":
                    metadata["compression"]["after"] = compression_snapshot()
                # End the provider window before offline grading. EchoProvider's
                # counters never enter native model usage or gateway attribution.
                try:
                    info["grader"] = grade(output, executable)
                except Exception as exc:
                    info["grader_error_class"] = type(exc).__name__
                    traceback.print_exc(file=lifecycle)
                metadata["arms"][arm] = info
                (directory / "run.json").write_text(json.dumps(metadata, indent=2))
    except Exception as exc:
        metadata["setup_error_class"] = type(exc).__name__
        traceback.print_exc(file=lifecycle)
    finally:
        metadata["cleanup_passed"] = True
        if container_attempted:
            try:
                with (directory / "container.log").open("w") as log:
                    subprocess.run(["bash", str(ROOT / "container.sh"), "logs-e2e", metadata["start"]], stdout=log,
                                   stderr=subprocess.STDOUT, timeout=30, check=False)
            except Exception:
                traceback.print_exc(file=lifecycle)
            finally:
                try:
                    stopped = subprocess.run(["bash", str(ROOT / "container.sh"), "stop-e2e"],
                                             stdout=lifecycle, stderr=subprocess.STDOUT, timeout=60, check=False)
                    metadata["cleanup_passed"] = stopped.returncode == 0
                except Exception:
                    metadata["cleanup_passed"] = False
                    traceback.print_exc(file=lifecycle)
        if server is not None:
            server.shutdown()
            server.server_close()
            server_thread.join()
        lifecycle.close()
        (directory / "run.json").write_text(json.dumps(metadata, indent=2))
        try:
            receipt = make_receipt(directory, correlations=correlations)
        except Exception as exc:
            # Even damaged recipe metadata cannot erase the stable result.
            receipt = {"passed": False, "arms": [], "error_class": type(exc).__name__,
                       "setup_error_class": metadata.get("setup_error_class")}
        finish(directory, receipt, exit_code(receipt))
    return announce(directory)


if __name__ == "__main__":
    raise SystemExit(main())
