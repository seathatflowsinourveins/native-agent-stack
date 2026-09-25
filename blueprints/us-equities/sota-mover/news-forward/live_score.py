#!/usr/bin/env python3
"""Long-running ChronoGPT-Instruct scorer for live headlines (runs in the vLLM runtime).

Reads queued events from <state>/score-queue.jsonl, writes one row per event to
<state>/scores.jsonl (resumable by event_id), and a heartbeat to
<state>/scorer-status.json. The model path is the study's own ``score.py`` loaded by
path: pinned revision from checkpoints.json, sha256-verified weights loaded with
torch.load(weights_only=True, mmap=True), the reviewed model code imported by path
after its sha256 check, float32 with "highest" matmul precision, the cached decoder and
the operative FAVORABLE/UNFAVORABLE/UNCLEAR prompt variant. No remote-code loader.

The supervisor decides the device (GPU schedule) and launches this process in its own
transient systemd unit with MemoryMax=9G. With --idle-exit N the process exits after N
idle seconds so the GPU is released between overnight bursts.
"""
import argparse
import json
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

score = common.load_by_path("news_llm_score", os.path.join(common.NEWS_LLM, "score.py"))
sig = score.sig

STOP = False


def _stop(*_):
    global STOP
    STOP = True


class MmapCpuScorer(score.Scorer):
    """CPU variant of score.Scorer whose weights stay file-backed (no 7 GB anonymous copy).

    Identical checks and numerics: the same sha256-verified pytorch_model.bin loaded
    with torch.load(weights_only=True, mmap=True), the reviewed model code imported
    by path after its sha256 check, float32 forwards and the cached decoder. The only
    difference from Scorer.load is load_state_dict(assign=True) on a meta-device model,
    so parameters are the (copy-on-write) mmap tensors themselves: resident pages are
    clean page cache the kernel can reclaim, instead of anonymous memory that pushed the
    host under earlyoom's threshold on 2026-09-25 (the copy-based CPU load was SIGKILLed
    by earlyoom at 7.5 GB RSS).
    """

    def load(self, year):
        if self.loaded_year == year:
            return
        torch = self.torch
        entry = self.pins["checkpoints"][str(year)]
        base = score.checkpoint_dir(self.storage, year, self.pins)
        weights = os.path.join(base, "pytorch_model.bin")
        expected = entry["files"]["pytorch_model.bin"]["sha256"]
        started = time.time()
        if score.sha256_file(weights) != expected:
            raise SystemExit(f"weights sha256 mismatch for {year}; refusing to load")
        module = self._import_model_code(base)
        with open(os.path.join(base, "config.json"), encoding="utf-8") as handle:
            config = json.load(handle)
        with torch.device("meta"):
            model = module.ChronoGPT(**config)
        state = torch.load(weights, map_location="cpu", weights_only=True, mmap=True)
        model.load_state_dict(state, strict=True, assign=True)
        del state
        bad = sorted({str(p.dtype) for p in model.parameters() if p.dtype != torch.float32})
        if bad:
            raise SystemExit(f"non-float32 parameters in checkpoint {year}: {bad}")
        for block in model.blocks:
            if block.attn is not None:
                block.attn.rotary.max_seq_len = 2048
                block.attn.rotary._create_buffers(device=self.device)
                block.attn.kv_cache = None
        meta = [n for n, b in model.named_buffers() if b.is_meta]
        if meta:
            raise SystemExit(f"uninitialized buffers after load: {meta[:5]}")
        model.eval()
        self.model = model
        self.loaded_year = year
        self.load_seconds = round(time.time() - started, 1)
        self.weights_sha256 = expected
        self.revision = entry["revision"]


def done_ids(path):
    return {r["event_id"] for r in common.read_jsonl(path) if "event_id" in r}


def write_status(path, status):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(status, handle, indent=1, sort_keys=True)
    os.replace(tmp, path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", default=common.STATE_ROOT)
    parser.add_argument("--device", choices=("cuda", "cpu"), required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--idle-exit", type=float, default=0.0, help="exit after this many idle seconds (0: never)")
    parser.add_argument("--threads", type=int, default=12, help="CPU threads (cpu device)")
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    queue_path = os.path.join(args.state, "score-queue.jsonl")
    out_path = os.path.join(args.state, "scores.jsonl")
    status_path = os.path.join(args.state, "scorer-status.json")
    pins = score.load_pins()
    variant = sig.OPERATIVE_VARIANT
    code_sha = pins["reviewed_code"]["sha256"]
    status = {"pid": os.getpid(), "device": args.device, "started_at": score.utc_now(), "loaded_year": None,
              "scored": 0, "variant": variant, "template_sha256": sig.template_sha256(variant),
              "dtype": "float32", "matmul": "highest", "decoder": "cached", "state": "starting"}
    write_status(status_path, status)
    scorer_class = MmapCpuScorer if args.device == "cpu" else score.Scorer
    scorer = scorer_class(common.MODEL_STORAGE, pins, device=args.device, dtype_name="float32",
                          matmul="highest", decoder="cached")
    status["loader"] = scorer_class.__name__
    if args.device == "cpu":
        scorer.torch.set_num_threads(max(1, args.threads))
    done = done_ids(out_path)
    idle_since = time.time()
    while not STOP:
        pending = [r for r in common.read_jsonl(queue_path) if r.get("event_id") and r["event_id"] not in done]
        if not pending:
            status.update(state="idle", heartbeat=score.utc_now())
            write_status(status_path, status)
            if args.idle_exit and time.time() - idle_since > args.idle_exit:
                break
            time.sleep(2)
            continue
        by_year = {}
        for ev in pending:
            by_year.setdefault(int(ev["checkpoint_year"]), []).append(ev)
        for year in sorted(by_year):
            if STOP:
                break
            status.update(state=f"loading_{year}", heartbeat=score.utc_now())
            write_status(status_path, status)
            scorer.load(year)
            status.update(loaded_year=year, revision=scorer.revision, weights_sha256=scorer.weights_sha256,
                          load_seconds=scorer.load_seconds, state="scoring")
            items = []
            with open(out_path, "a", encoding="utf-8") as out:
                for ev in by_year[year]:
                    text = sig.model_input(ev["company"], ev["headline"], variant)
                    tokens = scorer.encode(text)
                    item = {"event_id": ev["event_id"], "ev": ev, "text": text, "tokens": tokens}
                    if len(tokens) + score.MAX_NEW_TOKENS > scorer.context:
                        row = score.result_row(item, year, scorer, code_sha, "", "context_overflow", 0, args.batch_size, variant)
                        row.update(device=args.device, latency_seconds=0.0)
                        out.write(json.dumps(row) + "\n")
                        done.add(ev["event_id"])
                        continue
                    items.append(item)
                for batch in score.plan_batches(items, args.batch_size):
                    started = time.time()
                    outputs = scorer.decode_batch([it["tokens"] for it in batch])
                    elapsed = round(time.time() - started, 3)
                    for item, (raw, stop, n_new) in zip(batch, outputs):
                        row = score.result_row(item, year, scorer, code_sha, raw, stop, n_new, len(batch), variant)
                        row.update(device=args.device, batch_seconds=elapsed)
                        out.write(json.dumps(row) + "\n")
                        done.add(item["event_id"])
                        status["scored"] += 1
                    out.flush()
                    os.fsync(out.fileno())
                    status.update(heartbeat=score.utc_now(), last_batch_seconds=elapsed)
                    if scorer.device.type == "cuda":
                        status["max_gpu_memory_allocated_gib"] = round(scorer.torch.cuda.max_memory_allocated() / 2**30, 2)
                    write_status(status_path, status)
                    if STOP:
                        break
        idle_since = time.time()
    status.update(state="exited", heartbeat=score.utc_now())
    write_status(status_path, status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
