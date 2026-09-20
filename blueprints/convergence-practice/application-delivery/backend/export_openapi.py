"""Export the API schema without connecting to PostgreSQL."""
import json
from pathlib import Path
from .app import app

if __name__ == "__main__":
    Path("openapi.json").write_text(json.dumps(app.openapi(), sort_keys=True, indent=2) + "\n")
