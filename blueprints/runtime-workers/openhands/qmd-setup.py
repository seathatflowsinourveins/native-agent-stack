"""Native QMD setup, following qmd v2.8.3 src/cli/qmd.ts collection add/update.

Only this worker's config/index is writable. No embed/model-download operation.
"""

import json
import os
from pathlib import Path
import subprocess


os.umask(0o077)
config = json.loads(Path("/run-input/mcp.json").read_text())["qmd"]
environment = {**os.environ, **config["env"]}
collections = json.loads(Path("/recipe/config/mcp-policy.json").read_text())["qmd"]["collections"]
command = [config["command"], "--index", "native-agent-stack-catalog"]
# The generated configuration has only these fixed paths and collection names.
# Re-registering is unnecessary; native update refreshes an existing index.
config_file = Path(environment["QMD_CONFIG_DIR"]) / "native-agent-stack-catalog.yml"
if not config_file.exists():
    for name in collections:
        subprocess.run(command + ["collection", "add", f"/documents/{name}", "--name", name, "--mask", "**/*.md"],
                       env=environment, cwd="/workspace", check=True, timeout=180)
subprocess.run(command + ["update"], env=environment, cwd="/workspace", check=True, timeout=300)
