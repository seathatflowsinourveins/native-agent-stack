import json, os, time, tomllib, pathlib
home = pathlib.Path(__file__).parent / "home"
prov = tomllib.load(open(os.path.expanduser("~/.codex/omniroute.config.toml"), "rb"))["model_providers"]["omniroute"]
keyvar = prov["env_key"]
if not os.environ.get(keyvar): os.environ[keyvar] = "keyless-gateway-placeholder"
(home / "config.toml").write_text(
    '[model_providers.omniroute]\nname = "OmniRoute"\nbase_url = "http://127.0.0.1:20128/v1"\nwire_api = "responses"\n'
    f'env_key = "{keyvar}"\nrequires_openai_auth = false\nsupports_standalone_web_search = true\n')
os.environ["CODEX_HOME"] = str(home)
from openai_codex import Codex
marker = "SDK_01600_GATEWAY_CANARY_OK"; t0 = time.time()
with Codex() as codex:
    th = codex.thread_start(model="cx/gpt-6.1-sol", model_provider="omniroute", ephemeral=True, config={"model_reasoning_effort": "max"})
    r = th.run(f"Reply with exactly this text and nothing else: {marker}")
    print(json.dumps({"marker_exact_match": (r.final_response or "").strip() == marker, "final_response": (r.final_response or "")[:200],
                      "usage": r.usage.model_dump() if getattr(r, "usage", None) is not None else None, "seconds": round(time.time() - t0, 1)}, default=str))
