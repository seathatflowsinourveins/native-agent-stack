"""Fail on API/schema/type drift without rewriting checked-in artifacts."""
import json
from pathlib import Path
import subprocess
import tempfile
from backend.app import app

root = Path(__file__).resolve().parent
expected = json.dumps(app.openapi(), sort_keys=True, indent=2) + "\n"
if (root / "openapi.json").read_text() != expected:
    raise SystemExit("OpenAPI schema drift: run make schema and review the change.")
(root / ".runtime").mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="schema-", dir=root / ".runtime") as directory:
    generated = Path(directory) / "api.generated.ts"
    subprocess.run(["pnpm", "exec", "openapi-typescript", "openapi.json", "-o", str(generated)],
                   cwd=root, check=True)
    if generated.read_bytes() != (root / "app/api.generated.ts").read_bytes():
        raise SystemExit("Generated API type drift: run make schema and review the change.")
print("Native API schema and generated TypeScript agree.")
