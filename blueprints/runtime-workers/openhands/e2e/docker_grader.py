"""Run the unchanged official SWE-bench CLI with owned Docker transport.

Reference: swebench==4.1.0 harness/docker_build.py:516 and
harness/run_evaluation.py:580. Only Docker creation names, labels and the
network mode are adapted. No tests, scoring, patch application or
report-writing logic is replaced.

Every grader container is created with network mode "none", which
docker/docker-py@7.1.0 documents as "No networking for this container"
(docker/models/containers.py:686-694). The SDK builds one HostConfig
(types/containers.py:351) and posts it through create_container_from_config
(api/container.py:445-457), which is checked as well. moby/moby@docker-v29.8.1
records the mode as the single NetworkSettings.Networks entry "none" at create
(daemon/create.go:251; daemon/container_operations.go:363-406) and refuses to
connect such a container to another network (container_operations.go:202-204).
A created container whose inspect shows anything else is removed, not graded.
"""
from __future__ import annotations

import contextlib
import importlib.metadata
import json
import os
import re
import runpy
from pathlib import Path


OWNER_KEY = "com.native-agent-stack.owner"
OWNER = "gpt6-omniroute-framework-integration"
NETWORK_MODE = "none"
NETWORK_KEYS = ("network", "network_mode", "networking_config", "network_disabled")


def checked_image(collection, image, expected_id):
    """Docker SDK Image.id binds the mutable upstream tag to a pre-pulled digest."""
    if not isinstance(expected_id, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", expected_id):
        raise ValueError("pinned_grader_image_required")
    actual = collection.client.images.get(image).id
    if actual != expected_id:
        raise ValueError("grader_image_identity_mismatch")
    return actual


def owned_container_options(options):
    result = dict(options)
    name = result.get("name", "")
    if not re.fullmatch(r"sweb\.eval\.[a-z0-9_.-]+", name):
        raise ValueError("unexpected_upstream_container_name")
    if any(result.get(key) for key in ("ports", "publish_all_ports", "volumes", "mounts")):
        raise ValueError("grader_requires_no_ports_volumes_or_custom_networks")
    requested = {key: result[key] for key in NETWORK_KEYS if result.get(key)}
    if requested not in ({}, {"network_mode": NETWORK_MODE}):
        raise ValueError("grader_requires_no_ports_volumes_or_custom_networks")
    result["name"] = "rw-openhands-" + name
    result["labels"] = {**result.get("labels", {}), OWNER_KEY: OWNER}
    result["network_mode"] = NETWORK_MODE
    return result


def checked_create_config(config):
    """The body of every SDK POST /containers/create must carry mode none."""
    host = config.get("HostConfig") if isinstance(config, dict) else None
    if not isinstance(host, dict) or host.get("NetworkMode") != NETWORK_MODE or config.get("NetworkingConfig"):
        raise ValueError("grader_container_requires_network_none")
    return config


def checked_network_none(container):
    """The created container's inspect: mode none and no other network."""
    attrs = getattr(container, "attrs", None) or {}
    mode = (attrs.get("HostConfig") or {}).get("NetworkMode")
    networks = (attrs.get("NetworkSettings") or {}).get("Networks")
    if mode != NETWORK_MODE or not isinstance(networks, dict) or set(networks) != {NETWORK_MODE}:
        raise ValueError("grader_container_network_not_none")
    return container


def owned_create(create, collection, args, kwargs, image_id, record):
    options = owned_container_options(kwargs)
    image = options.get("image", args[0] if args else None)
    checked_image(collection, image, image_id)
    # A separate host supervisor retains these exact names for cleanup.
    with Path(record).open("a") as stream:
        stream.write(json.dumps({"name": options["name"]}) + "\n")
    # docker-py 7.1.0 create() returns self.get(Id), a fresh inspect
    # (models/containers.py:913-936).
    container = create(collection, *args, **options)
    try:
        return checked_network_none(container)
    except ValueError:
        # The host's grade() also removes this recorded name afterwards.
        with contextlib.suppress(Exception):
            container.remove(force=True)
        raise


def install_transport(containers, api, images, volumes, networks, image_id, record="docker-created.jsonl"):
    create = containers.create
    post = api.create_container_from_config

    def created(collection, *args, **kwargs):
        return owned_create(create, collection, args, kwargs, image_id, record)

    def posted(client, config, *args, **kwargs):
        return post(client, checked_create_config(config), *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise RuntimeError("use_prebuilt_images_without_new_volumes_or_networks")

    containers.create = created
    api.create_container_from_config = posted
    # Namespace swebench uses prebuilt images. Never create unlabelled build
    # intermediates or additional resources if the selected upstream changes.
    api.build = forbidden
    images.pull = forbidden
    volumes.create = forbidden
    networks.create = forbidden


def main():
    if importlib.metadata.version("swebench") != "4.1.0":
        raise RuntimeError("exact_upstream_grader_version_required")
    from docker.models.containers import ContainerCollection
    from docker.models.networks import NetworkCollection
    from docker.models.volumes import VolumeCollection
    from docker.models.images import ImageCollection
    from docker.api.client import APIClient

    install_transport(ContainerCollection, APIClient, ImageCollection, VolumeCollection, NetworkCollection,
                      os.environ.get("OPENHANDS_GRADER_IMAGE_ID"))
    runpy.run_module("swebench.harness.run_evaluation", run_name="__main__")


if __name__ == "__main__":
    main()
