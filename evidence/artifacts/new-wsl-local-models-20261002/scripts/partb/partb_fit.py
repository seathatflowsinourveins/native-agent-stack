#!/usr/bin/env python3
"""Part B gate F (amendments 4 and 4a) for E3 or E4: with the generation model as the only model the measurement server
lists and entirely on the GPU, load the arm on CUDA, encode the first 256 documents of the frozen task's corpus at batch
size 16 through MTEB's own dataloader, and judge: passes when no error occurred, every parameter of the arm is on CUDA,
torch allocated GPU memory, and the generation model is still entirely on the GPU afterwards. Prints one JSON object.
Exit 0: passed. Exit 1: failed by running out of memory or by the generation model leaving the GPU (does not fit).
Exit 2: failed for another reason (an error that is not a fit result). usage: partb_fit.py <E3|E4>"""
import json
import sys
import traceback

import partb_arms

ARM = sys.argv[1]
record = {"arm": ARM, "gate": "F", "versions": partb_arms.versions(), "gpu_before": partb_arms.gpu()}
code = 2
try:
    listed = partb_arms.resident()
    record["resident_before"] = listed
    if not partb_arms.generation_only(listed):
        record.update(passed=False, reason="the generation model is not the only listed model, or not entirely on the GPU")
        raise SystemExit
    import torch
    from mteb._create_dataloaders import create_dataloader
    from mteb.types import PromptType
    the_task = partb_arms.task()
    the_task.load_data()
    sample = the_task.dataset["default"]["test"]["corpus"].select(range(256))
    try:
        model = partb_arms.build(ARM)
        record["devices"] = partb_arms.module_devices(model)
        loader = create_dataloader(sample, task_metadata=the_task.metadata, prompt_type=PromptType.document,
                                   batch_size=partb_arms.BATCH_SIZE)
        embeddings = model.encode(loader, task_metadata=the_task.metadata, hf_split="test", hf_subset="default",
                                  prompt_type=PromptType.document, batch_size=partb_arms.BATCH_SIZE)
        record["encoded"] = list(getattr(embeddings, "shape", []))
        record["out_of_memory"] = False
    except torch.OutOfMemoryError as error:
        record["out_of_memory"] = True
        record["error"] = partb_arms.scrub(f"OutOfMemoryError: {error}")[:400]
    record["torch_max_memory_allocated_bytes"] = torch.cuda.max_memory_allocated()
    free, total = torch.cuda.mem_get_info()
    record["torch_mem_get_info_bytes"] = {"free": free, "total": total}
    record["gpu_after"] = partb_arms.gpu()
    record["resident_after"] = partb_arms.resident()
    record["generation_on_gpu_after"] = partb_arms.generation_on_gpu(record["resident_after"])
    on_cuda = record.get("devices") == ["cuda"]
    record["passed"] = (bool(record.get("encoded")) and record["out_of_memory"] is False and on_cuda
                        and record["torch_max_memory_allocated_bytes"] > 0 and record["generation_on_gpu_after"])
    if record["passed"]:
        code = 0
    elif record.get("out_of_memory") or not record["generation_on_gpu_after"]:
        code = 1
        record["reason"] = "does not fit beside the generation model"
    else:
        record["reason"] = "failed for another reason (devices, allocation or encoding), not a fit result"
except SystemExit:
    pass
except BaseException:
    record["passed"] = False
    record["error"] = partb_arms.scrub(traceback.format_exc())[-1500:]
print(json.dumps(record, default=str))
sys.exit(code)
