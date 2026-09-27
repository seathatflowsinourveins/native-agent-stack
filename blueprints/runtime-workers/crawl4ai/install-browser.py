#!/usr/bin/env python3
"""Verified mirror for Playwright's supported install command. See research.md.

References: playwright 1.63.0 driver/package/lib/coreBundle.js:33650-33675
(PLAYWRIGHT_DOWNLOAD_HOST), Python 3.12 http.server and urllib.request.
"""
import functools
import hashlib
import http.server
import json
import os
import subprocess
import threading
import urllib.request
from pathlib import Path

from host import load_host, locations


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    prefix, state = locations()
    metadata = json.loads((Path(__file__).parent / "browser-artifacts.json").read_text())
    downloads = state / "downloads"
    for artifact in metadata["artifacts"]:
        target = downloads / artifact["mirror_path"]
        target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if not target.exists():
            temporary = target.with_suffix(".partial")
            try:
                with urllib.request.urlopen(artifact["url"], timeout=60) as response, temporary.open("wb") as out:
                    while block := response.read(1024 * 1024):
                        out.write(block)
                with temporary.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != artifact["sha256"]:
                        raise ValueError("browser artifact checksum mismatch")
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        with target.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != artifact["sha256"]:
                raise ValueError("retained browser artifact checksum mismatch")
        if target.stat().st_size != artifact["size"]:
            raise ValueError("browser artifact size mismatch")
    port = load_host()["mirror_port"]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(QuietHandler, directory=str(downloads)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = os.environ.copy()
    env["PLAYWRIGHT_DOWNLOAD_HOST"] = f"http://127.0.0.1:{port}"
    for key in ("PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST", "PLAYWRIGHT_FIREFOX_DOWNLOAD_HOST", "PLAYWRIGHT_WEBKIT_DOWNLOAD_HOST"):
        env.pop(key, None)
    try:
        subprocess.run([str(prefix / "venv/bin/python"), "-m", "playwright", *metadata["install_args"]], env=env, check=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
