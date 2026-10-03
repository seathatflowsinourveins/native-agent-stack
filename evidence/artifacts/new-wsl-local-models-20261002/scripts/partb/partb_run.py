#!/usr/bin/env python3
"""Part B (amendments 4 and 4a): run one embedding arm on the frozen retrieval task through MTEB 2.22.1, with
predictions saved; record provenance, time, GPU memory and the generation model's residency before and after; unload
an Ollama embedder after its run. Decides nothing. Refuses to start unless the generation model is the only model the
measurement server lists and is entirely on the GPU, and refuses an output folder that exists. Every outcome, a failure
included, ends in run-record.json. usage: partb_run.py <E1|E2|E3|E4> <output dir>"""
import json
import logging
import pathlib
import sys
import time
import traceback

import partb_arms

ARM, OUT = sys.argv[1], pathlib.Path(sys.argv[2])
if OUT.exists():
    raise SystemExit(f"{OUT.name} exists; a run is never repeated under the same name")
OUT.mkdir(parents=True)
logging.basicConfig(filename=str(OUT / "mteb.log"), level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
record = {"arm": ARM, "out": OUT.name, "status": "not started", "versions": partb_arms.versions(),
          "gpu_before": partb_arms.gpu()}
try:
    record["resident_before"] = partb_arms.resident()
    record["generation_only_before"] = partb_arms.generation_only(record["resident_before"])
    if not record["generation_only_before"]:
        record["status"] = "refused"
        record["reason"] = "the generation model is not the only listed model, or not entirely on the GPU"
        raise SystemExit(2)
    if ARM in partb_arms.OLLAMA_NAMES:
        record["ollama_digests"] = partb_arms.ollama_digests()
    import mteb
    from mteb.cache import ResultCache
    the_task = partb_arms.task()
    model = partb_arms.build(ARM)
    record["wrapper"] = type(model).__name__
    for key in ("prompts_dict", "model_prompts", "use_instructions", "apply_instruction_to_passages", "model_name",
                "use_chat_template"):
        if hasattr(model, key):
            record.setdefault("wrapper_settings", {})[key] = getattr(model, key)
    if ARM in partb_arms.REGISTERED:
        record["devices"] = partb_arms.module_devices(model)
    started = time.time()
    try:
        mteb.evaluate(model, [the_task], cache=ResultCache(OUT / "cache"), prediction_folder=OUT / "predictions",
                      encode_kwargs={"batch_size": partb_arms.BATCH_SIZE}, show_progress_bar=False)
        record["status"] = "completed"
    except BaseException as error:  # a failed run is a result, kept with its reason
        record["status"] = "failed"
        record["error"] = partb_arms.scrub(f"{type(error).__name__}: {error}")[:600]
        record["out_of_memory"] = "out of memory" in str(error).lower() or type(error).__name__ == "OutOfMemoryError"
    record["wall_seconds"] = round(time.time() - started, 1)
    if ARM in partb_arms.REGISTERED:
        import torch
        record["torch_max_memory_allocated_bytes"] = torch.cuda.max_memory_allocated()
        free, total = torch.cuda.mem_get_info()
        record["torch_mem_get_info_bytes"] = {"free": free, "total": total}
    scores = sorted((OUT / "cache").rglob(f"{partb_arms.TASK}.json"))
    if scores:
        data = json.loads(scores[0].read_text())
        test = data.get("scores", {}).get("test", [{}])[0]
        record["score_file"] = str(scores[0].relative_to(OUT))
        record["ndcg_at_10"] = test.get("ndcg_at_10")
        record["main_score"] = test.get("main_score")
        record["mteb_evaluation_time"] = data.get("evaluation_time")
    record["prediction_files"] = [str(p.relative_to(OUT)) for p in sorted((OUT / "predictions").glob("*.json"))]
except SystemExit:
    pass
except BaseException as error:
    record["status"] = "failed before or after the run"
    record["error"] = partb_arms.scrub(traceback.format_exc())[-1500:]
finally:
    record["gpu_after"] = partb_arms.gpu()
    record["resident_after"] = partb_arms.resident()
    record["generation_on_gpu_after"] = partb_arms.generation_on_gpu(record["resident_after"])
    if ARM in partb_arms.OLLAMA_NAMES and record["status"] != "refused":
        record["unload"] = partb_arms.unload(partb_arms.OLLAMA_NAMES[ARM])
        time.sleep(3)
        record["resident_after_unload"] = partb_arms.resident()
    (OUT / "run-record.json").write_text(json.dumps(record, indent=1, default=str) + "\n")
    print(json.dumps(record, default=str))
sys.exit(0 if record["status"] == "completed" else 1)
