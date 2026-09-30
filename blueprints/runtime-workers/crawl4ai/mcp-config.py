#!/usr/bin/env python3
"""Native Claude SSE registration; config contains a helper, never a bearer value.

Sources: Crawl4AI@133e1d92 docs/md_v2/core/self-hosting.md:404-419;
anthropics/claude-code@v2.1.283 CHANGELOG.md:5048,6971 (headersHelper),
installed `claude mcp add-json --help`; code.claude.com/docs/en/mcp.
"""
import argparse
import json
import shlex
import subprocess
from host import load_host, locations, private_file


def configuration():
    prefix, _ = locations()
    return {"type": "sse", "url": f"http://127.0.0.1:{load_host()['api_port']}/mcp/sse",
            "headersHelper": "python3 " + shlex.quote(str(prefix / "recipe/mcp-config.py")) + " headers",
            "timeout": 180000}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("config", "register", "headers"))
    args = parser.parse_args()
    if args.action == "headers":
        # Only Claude's trusted headersHelper should invoke this action.
        _, state = locations()
        token = state / "secrets/api_token"
        private_file(token)
        print(json.dumps({"Authorization": "Bearer " + token.read_text().strip()}))
        return 0
    config = json.dumps(configuration())
    if args.action == "register":
        return subprocess.run(["claude", "mcp", "add-json", "crawl4ai", "--scope", "local", config], check=False).returncode
    print(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
