"""Run the unchanged official SWE-bench CLI with owned Docker transport.

Reference: swebench==4.1.0 harness/docker_build.py:516 and
harness/run_evaluation.py:580. Only Docker creation metadata/limits are adapted.
No tests, scoring, patch application or report-writing logic is replaced.
"""
from __future__ import annotations

import importlib.metadata
import json
import re
import runpy
from pathlib import Path


OWNER_KEY = "com.native-agent-stack.owner"
OWNER = "gpt6-omniroute-framework-integration"


def owned_container_options(options):
    result = dict(options)
    name = result.get("name", "")
    if not re.fullmatch(r"sweb\.eval\.[a-z0-9_.-]+", name):
        raise ValueError("unexpected_upstream_container_name")
    if any(result.get(key) for key in ("ports", "publish_all_ports", "volumes", "mounts", "network", "network_mode")):
        raise ValueError("grader_requires_no_ports_volumes_or_custom_networks")
    result["name"] = "rw-openhands-" + name
    result["labels"] = {**result.get("labels", {}), OWNER_KEY: OWNER}
    result.update(mem_limit="8g", nano_cpus=4_000_000_000, pids_limit=384)
    return result


def main():
    if importlib.metadata.version("swebench") != "4.1.0":
        raise RuntimeError("exact_upstream_grader_version_required")
    from docker.models.containers import ContainerCollection
    from docker.models.networks import NetworkCollection
    from docker.models.volumes import VolumeCollection
    from docker.api.client import APIClient

    create = ContainerCollection.create

    def owned_create(collection, *args, **kwargs):
        kwargs = owned_container_options(kwargs)
        # A separate host supervisor retains these exact names for cleanup.
        with Path("docker-created.jsonl").open("a") as stream:
            stream.write(json.dumps({"name": kwargs["name"]}) + "\n")
        return create(collection, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise RuntimeError("use_prebuilt_images_without_new_volumes_or_networks")

    ContainerCollection.create = owned_create
    # Namespace swebench uses prebuilt images. Never create unlabelled build
    # intermediates or additional resources if the selected upstream changes.
    APIClient.build = forbidden
    VolumeCollection.create = forbidden
    NetworkCollection.create = forbidden
    runpy.run_module("swebench.harness.run_evaluation", run_name="__main__")


if __name__ == "__main__":
    main()
