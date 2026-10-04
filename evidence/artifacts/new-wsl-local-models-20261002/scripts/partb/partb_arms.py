"""The four arms of Part B's embedding condition, built as amendments 4 and 4a of PREREGISTRATION-local-models.md
state, and the shared checks every Part B script uses. Holds no measurement logic of its own."""
import json
import pathlib
import subprocess
import urllib.request

import mteb

OLLAMA = "http://127.0.0.1:21434"
TASK = "CQADupstackUnixRetrieval"
DATASET_REVISION = "6c6430d3a6d36f8d2a829195bc5dc94d7e063e53"
BATCH_SIZE = 16
GENERATION = "swift-iq3s-s2o-64k"
REGISTERED = {
    "E3": ("nvidia/Nemotron-3-Embed-1B-BF16", "f880174635613cff04033875fc6a69296cb72006"),
    "E4": ("tencent/WeMM-Embedding-2B", "df8094e5caf29083d9cac28e96fad6cfbe3ee57f"),
}
OLLAMA_NAMES = {"E1": "qwen3-embedding-8k:latest", "E2": "embeddinggemma:latest"}
GEMMA_PROMPTS = {"Retrieval-query": "task: search result | query: ", "Retrieval-document": "title: none | text: "}
HOME = str(pathlib.Path.home())


def scrub(text):
    """A message with the home folder written as ~, for records."""
    return str(text).replace(HOME, "~")


def task():
    loaded = mteb.get_task(TASK)
    revision = loaded.metadata.dataset["revision"]
    if revision != DATASET_REVISION:
        raise SystemExit(f"the task's dataset revision is {revision}, not the frozen {DATASET_REVISION}")
    return loaded


def build(arm):
    if arm == "E1":
        from mteb.models import OpenAIAPIEncodeWrapper
        from mteb.models.model_implementations.qwen3_models import instruction_template
        # prompt_dict={} is needed for the wrapper to take its instruction branch (amendment 4a, B1)
        return OpenAIAPIEncodeWrapper(endpoint_url=OLLAMA, model_name=OLLAMA_NAMES["E1"], use_chat_template=False,
                                      modalities=["text"], prompt_dict={}, use_instructions=True,
                                      instruction_template=instruction_template, apply_instruction_to_documents=False)
    if arm == "E2":
        from mteb.models import OpenAIAPIEncodeWrapper
        wrapper = OpenAIAPIEncodeWrapper(endpoint_url=OLLAMA, model_name=OLLAMA_NAMES["E2"], use_chat_template=False,
                                         modalities=["text"], use_instructions=False, prompt_dict=dict(GEMMA_PROMPTS))
        # the prompt name is looked up in model_prompts and the text in prompts_dict (amendment 4a, B1)
        wrapper.model_prompts = dict(GEMMA_PROMPTS)
        return wrapper
    if arm in REGISTERED:
        name, revision = REGISTERED[arm]
        meta = mteb.get_model_meta(name)
        if meta.revision != revision:
            raise SystemExit(f"MTEB registers {name} at {meta.revision}, not the frozen {revision}")
        return mteb.get_model(name, revision, device="cuda")
    raise SystemExit(f"unknown arm {arm}")


def gpu():
    try:
        return subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
                              capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as error:
        return f"nvidia-smi failed: {type(error).__name__}"


def resident():
    """The models the measurement server lists, or an error string."""
    try:
        with urllib.request.urlopen(OLLAMA + "/api/ps", timeout=10) as response:
            models = json.loads(response.read().decode()).get("models", [])
        return [{"name": m["name"], "size": m.get("size"), "size_vram": m.get("size_vram"),
                 "context_length": m.get("context_length")} for m in models]
    except Exception as error:
        return f"api/ps failed: {type(error).__name__}: {scrub(error)[:200]}"


def generation_only(listed):
    """True when the generation model is the only model listed and is entirely on the GPU."""
    return (isinstance(listed, list) and len(listed) == 1 and listed[0]["name"].split(":")[0] == GENERATION
            and listed[0]["size"] == listed[0]["size_vram"])


def generation_on_gpu(listed):
    return isinstance(listed, list) and any(m["name"].split(":")[0] == GENERATION and m["size"] == m["size_vram"]
                                            for m in listed)


def unload(name):
    """Unload one model of the measurement server (keep_alive 0), returning a short status."""
    try:
        body = json.dumps({"model": name, "keep_alive": 0, "input": []}).encode()
        request = urllib.request.Request(OLLAMA + "/api/embed", data=body, headers={"content-type": "application/json"})
        with urllib.request.urlopen(request, timeout=60) as response:
            response.read()
        return "unloaded"
    except Exception as error:
        return f"unload failed: {type(error).__name__}: {scrub(error)[:200]}"


def ollama_digests():
    try:
        with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=10) as response:
            models = json.loads(response.read().decode()).get("models", [])
        return {m["name"]: m.get("digest") for m in models}
    except Exception as error:
        return f"api/tags failed: {type(error).__name__}"


def versions():
    import importlib.metadata as metadata
    out = {}
    for name in ("mteb", "sentence-transformers", "transformers", "torch", "pytrec-eval-terrier", "qwen-vl-utils",
                 "accelerate"):
        try:
            out[name] = metadata.version(name)
        except Exception:
            out[name] = None
    return out


def module_devices(model):
    """The set of devices of every torch parameter reachable from the wrapper's attributes (two levels)."""
    import torch
    devices, seen = set(), set()

    def visit(obj, depth):
        if id(obj) in seen or depth > 2:
            return
        seen.add(id(obj))
        if isinstance(obj, torch.nn.Module):
            devices.update(str(p.device.type) for p in obj.parameters())
            return
        for value in list(vars(obj).values()) if hasattr(obj, "__dict__") else []:
            visit(value, depth + 1)

    visit(model, 0)
    return sorted(devices)
