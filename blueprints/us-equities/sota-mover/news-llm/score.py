#!/usr/bin/env python3
"""Score news headlines with chronologically consistent ChronoGPT-Instruct checkpoints.

Subcommands
  fetch   Download the pinned checkpoint files and the tiktoken gpt2 files, verifying
          every sha256 against checkpoints.json (standard library only, resumable).
  run     Score prepared events (JSONL.gz from prepare.py) and append one JSON line per
          event to <out>/scores-<YYYY>1231.jsonl; resumable by event_id. Needs torch and
          tiktoken (the read-only vLLM runtime); nothing is installed.

A score is an input to the study, not an outcome: this script never reads prices.

Security (checkpoints.json load_policy): pickled files are loaded only with
torch.load(..., weights_only=True); ChronoGPT_instruct.py is imported from the local
verified file only after its sha256 matches the reviewed pin; from_pretrained and every
remote-code loader are never used; HF_HUB_OFFLINE=1 and a local TIKTOKEN_CACHE_DIR keep
the scoring process offline.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone


_HERE = os.path.dirname(os.path.abspath(__file__))


def load_news_signal():
    spec = importlib.util.spec_from_file_location("news_signal", os.path.join(_HERE, "news_signal.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules["news_signal"] = module
    spec.loader.exec_module(module)
    return module


sig = load_news_signal()

CHECKPOINTS_FILE = os.path.join(_HERE, "checkpoints.json")
DEFAULT_STORAGE = os.path.expanduser("~/.local/share/native-agent-stack/models/chronogpt-instruct")
MAX_NEW_TOKENS = 16
GPU_MEMORY_FRACTION_CAP = 12.0  # GiB, the brief's per-process VRAM budget


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_pins(path=CHECKPOINTS_FILE):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def checkpoint_dir(storage, year, pins):
    rev = pins["checkpoints"][str(year)]["revision"]
    return os.path.join(storage, f"{year}1231", rev)


def tiktoken_cache_dir(storage):
    return os.path.join(storage, "tiktoken-cache")


def sha256_file(path, chunk=16 * 1024 * 1024):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


# --------------------------------------------------------------------------------------
# fetch
# --------------------------------------------------------------------------------------


def _download(url, dest, expected_sha256, expected_size=None, retries=5):
    """Stream url to dest (resumable via a .part file and HTTP Range), verify sha256."""
    if os.path.exists(dest) and (expected_size is None or os.path.getsize(dest) == expected_size):
        if sha256_file(dest) == expected_sha256:
            return {"url": url, "status": "present", "bytes": os.path.getsize(dest)}
        os.replace(dest, dest + ".bad")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    for attempt in range(retries):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        request = urllib.request.Request(url, headers={"User-Agent": "sota-news-llm-fetch/1"})
        if have:
            request.add_header("Range", f"bytes={have}-")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                mode = "ab" if (have and response.status == 206) else "wb"
                with open(part, mode) as out:
                    while True:
                        block = response.read(8 * 1024 * 1024)
                        if not block:
                            break
                        out.write(block)
            break
        except OSError as error:  # urllib errors subclass OSError
            print(f"fetch retry {attempt + 1}/{retries} for {os.path.basename(dest)}: {type(error).__name__}", flush=True)
            time.sleep(min(60, 5 * (attempt + 1)))
    else:
        raise SystemExit(f"download failed after {retries} attempts: {url}")
    size = os.path.getsize(part)
    if expected_size is not None and size != expected_size:
        raise SystemExit(f"size mismatch for {url}: {size} != {expected_size}")
    actual = sha256_file(part)
    if actual != expected_sha256:
        os.replace(part, dest + ".bad")
        raise SystemExit(f"sha256 mismatch for {url}")
    os.replace(part, dest)
    return {"url": url, "status": "downloaded", "bytes": size}


def cmd_fetch(args):
    pins = load_pins()
    storage = os.path.expanduser(args.storage)
    years = args.years or sorted(int(y) for y in pins["checkpoints"])
    records = []
    started = time.time()
    for url, digest in pins["tokenizer"]["files"].items():
        dest = os.path.join(tiktoken_cache_dir(storage), hashlib.sha1(url.encode()).hexdigest())
        records.append(_download(url, dest, digest))
    for year in years:
        entry = pins["checkpoints"][str(year)]
        base = checkpoint_dir(storage, year, pins)
        for name, meta in sorted(entry["files"].items()):
            url = f"https://huggingface.co/{entry['repo']}/resolve/{entry['revision']}/{name}"
            rec = _download(url, os.path.join(base, name), meta["sha256"], meta["size"])
            rec["year"] = year
            rec["file"] = name
            records.append(rec)
            print(json.dumps({"year": year, "file": name, "status": rec["status"], "bytes": rec["bytes"]}), flush=True)
    manifest = {
        "schema": "sota-news-llm-fetch/1",
        "finished_at": utc_now(),
        "seconds": round(time.time() - started, 1),
        "records": records,
        "bytes_downloaded": sum(r["bytes"] for r in records if r["status"] == "downloaded"),
        "bytes_verified": sum(r["bytes"] for r in records),
    }
    manifest["years"] = years
    name = "fetch-manifest-" + "-".join(str(y) for y in years) + ".json"
    with open(os.path.join(storage, name), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1)
    print(json.dumps({k: manifest[k] for k in ("finished_at", "seconds", "bytes_downloaded", "bytes_verified")}))


# --------------------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------------------


def read_events(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def done_ids(out_dir):
    seen = set()
    if not os.path.isdir(out_dir):
        return seen
    for name in os.listdir(out_dir):
        if name.startswith("scores-") and name.endswith(".jsonl"):
            with open(os.path.join(out_dir, name), encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        seen.add(json.loads(line)["event_id"])
                    except (ValueError, KeyError):
                        continue  # a torn final line from an interrupted run is rescored
    return seen


def plan_batches(items, batch_size, max_batch_tokens=None):
    """Sort by token length so a batch pads little; order is deterministic.

    A batch closes at batch_size items or when (items x padded width incl. the new
    tokens) would exceed max_batch_tokens, which bounds activation and logit memory.
    """
    ordered = sorted(items, key=lambda it: (len(it["tokens"]), it["event_id"]))
    batches, current = [], []
    for it in ordered:
        width = len(it["tokens"]) + MAX_NEW_TOKENS
        if current and (len(current) >= batch_size or (max_batch_tokens and (len(current) + 1) * width > max_batch_tokens)):
            batches.append(current)
            current = []
        current.append(it)
    if current:
        batches.append(current)
    return batches


def sample_events(events, count):
    """Label-agnostic deterministic subset: the `count` smallest sha256(event_id)."""
    return sorted(events, key=lambda ev: hashlib.sha256(ev["event_id"].encode()).hexdigest())[:count]


def install_fp32_forwards(module, torch):
    """Run the reviewed model in float32: replace the only two methods that hard-cast to bf16.

    ChronoGPT_instruct.py (sha256 pinned) casts activations to bfloat16 in exactly two
    places: ValueEmbedding.forward (line 201, `emb(inputs).bfloat16()`) and
    ChronoGPT.forward (line 232, `self.embed(inputs).bfloat16()`); CastedLinear and
    Rotary follow the activation dtype. The replacements below are line-for-line copies
    of those two methods without the casts, so with float32 weights every operation runs
    in float32. Measured on 2026-09-25: in bf16 the logits of one prompt move by up to
    0.6-0.9 with batch shape or padding, more than typical top-2 margins (0.06-0.44), so
    bf16 labels depend on batch composition.
    """
    norm = module.norm

    def value_embedding_forward(self, inputs):
        base = [emb(inputs) for emb in self.embed]
        L = self.num_layers
        half = L // 2
        encoder = [base[i] if i < 3 else None for i in range(half)]
        decoder = [base[i - (half - 3)] if i >= (half - 3) else None for i in range(half)]
        return encoder + decoder

    @torch.inference_mode()
    def chronogpt_forward(self, inputs, past_key_values=None, last_positions=None):
        # last_positions (addition): gather one position per row before the final norm and
        # lm_head, which act per position, so the returned (B, 1, V) logits equal those
        # rows of the full (B, T, V) output without materializing T x V logits.
        B = inputs.size(0)
        if inputs.dim() == 1:
            inputs = inputs.unsqueeze(0)
        x0 = norm(self.embed(inputs))
        x = x0
        ve = [self.value_embeds(inputs[i].view(-1)) for i in range(B)]
        ve = [torch.stack([ve[b][i] for b in range(B)]) if ve[0][i] is not None else None
              for i in range(len(ve[0]))]
        ve_enc, ve_dec = ve[:self.num_encoder_layers], ve[self.num_encoder_layers:]
        if past_key_values is not None:
            for i, block in enumerate(self.blocks):
                if block.attn is not None:
                    block.attn.kv_cache = past_key_values[i]
        present = []
        layer_outputs = []
        skip_connections = []
        for i in range(self.num_encoder_layers):
            block = self.blocks[i]
            x = block(x, ve_enc[i], x0)
            if block.attn is not None:
                present.append(block.attn.kv_cache)
                block.attn.kv_cache = None
            skip_connections.append(x)
            layer_outputs.append(norm(x))
        for i in range(self.num_decoder_layers):
            x = x + self.skip_weights[i] * skip_connections.pop()
            block = self.blocks[self.num_encoder_layers + i]
            x = block(x, ve_dec[i], x0)
            layer_outputs.append(norm(x))
            if block.attn is not None:
                present.append(block.attn.kv_cache)
                block.attn.kv_cache = None
        if last_positions is not None:
            x = x[torch.arange(x.size(0), device=x.device), last_positions].unsqueeze(1)
        x = norm(x)
        logits = self.lm_head(x)
        logits = 15 * torch.tanh(logits / 15)
        return logits.float()

    module.ValueEmbedding.forward = value_embedding_forward
    module.ChronoGPT.forward = chronogpt_forward


class Scorer:
    def __init__(self, storage, pins, device="cuda", dtype_name="float32", matmul="highest", decoder="full"):
        self.storage = storage
        self.pins = pins
        cache = tiktoken_cache_dir(storage)
        os.environ["TIKTOKEN_CACHE_DIR"] = cache
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        import tiktoken  # noqa: PLC0415 - lazy: only the scoring runtime has it
        import torch  # noqa: PLC0415

        self.torch = torch
        self.tokenizer = tiktoken.get_encoding("gpt2")
        self.device = torch.device(device)
        if self.device.type == "cuda" and self.device.index is None:
            self.device = torch.device("cuda", torch.cuda.current_device())
        if dtype_name not in ("float32", "bfloat16"):
            raise SystemExit("dtype must be float32 or bfloat16")
        self.dtype = getattr(torch, dtype_name)
        self.dtype_name = dtype_name
        # "highest": full float32 matmuls, no TF32 (10-bit mantissa) shortcuts.
        # "tf32": tensor-core float32 matmuls, adopted only with a measured label agreement.
        if matmul not in ("highest", "tf32"):
            raise SystemExit("matmul must be highest or tf32")
        self.matmul = matmul
        if decoder not in ("full", "cached"):
            raise SystemExit("decoder must be full or cached")
        self.decoder = decoder
        if decoder == "cached" and dtype_name != "float32":
            raise SystemExit("the cached decoder needs the float32 forward")
        torch.backends.cuda.matmul.allow_tf32 = matmul == "tf32"
        torch.backends.cudnn.allow_tf32 = matmul == "tf32"
        torch.set_float32_matmul_precision("highest" if matmul == "highest" else "high")
        self.eos = pins["tokenizer"]["eos_id"]
        self.context = pins["tokenizer"]["context_tokens"]
        self.model = None
        self.loaded_year = None
        self.module = None
        if self.device.type == "cuda":
            total = torch.cuda.get_device_properties(self.device).total_memory
            torch.cuda.set_per_process_memory_fraction(min(1.0, GPU_MEMORY_FRACTION_CAP * 2**30 / total), self.device)

    def encode(self, text):
        return self.tokenizer.encode(text, allowed_special={"<|endoftext|>"})

    def decode(self, ids):
        return self.tokenizer.decode(ids)

    def _import_model_code(self, base):
        path = os.path.join(base, "ChronoGPT_instruct.py")
        expected = self.pins["reviewed_code"]["sha256"]
        actual = sha256_file(path)
        if actual != expected:
            raise SystemExit("ChronoGPT_instruct.py sha256 does not match the reviewed pin; refusing to import")
        if self.module is None:
            spec = importlib.util.spec_from_file_location("chronogpt_instruct_reviewed", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if self.dtype_name == "float32":
                install_fp32_forwards(module, self.torch)
            self.module = module
        return self.module

    def load(self, year):
        if self.loaded_year == year:
            return
        torch = self.torch
        entry = self.pins["checkpoints"][str(year)]
        base = checkpoint_dir(self.storage, year, self.pins)
        weights = os.path.join(base, "pytorch_model.bin")
        expected = entry["files"]["pytorch_model.bin"]["sha256"]
        started = time.time()
        if sha256_file(weights) != expected:
            raise SystemExit(f"weights sha256 mismatch for {year}; refusing to load")
        module = self._import_model_code(base)
        with open(os.path.join(base, "config.json"), encoding="utf-8") as handle:
            config = json.load(handle)
        if self.model is None:
            with torch.device("meta"):
                model = module.ChronoGPT(**config)
            model = model.to(dtype=self.dtype)
            model = model.to_empty(device=self.device)
            self.model = model
        state = torch.load(weights, map_location="cpu", weights_only=True, mmap=True)
        self.model.load_state_dict(state, strict=True)  # raises on any missing/unexpected key
        del state
        # to_empty leaves the non-persistent rotary buffers uninitialized: rebuild them.
        for block in self.model.blocks:
            if block.attn is not None:
                block.attn.rotary.max_seq_len = 2048
                block.attn.rotary._create_buffers(device=self.device)
                block.attn.kv_cache = None
        self.model.eval()
        if self.device.type == "cuda":
            torch.cuda.empty_cache()
        self.loaded_year = year
        self.load_seconds = round(time.time() - started, 1)
        self.weights_sha256 = expected
        self.revision = entry["revision"]

    def generate(self, token_lists, max_new=MAX_NEW_TOKENS):
        """Batched greedy decoding until each prompt's label is decided (news_signal.label_decided).

        Right padding with the EOS id; each step reads the logits at every sequence's own
        last real position and writes the chosen token at its next position. Causal
        attention keeps positions before a sequence's end unaffected by what follows it.
        """
        torch = self.torch
        b = len(token_lists)
        lens = [len(t) for t in token_lists]
        width = max(lens) + max_new
        buf = torch.full((b, width), self.eos, dtype=torch.long)
        for i, toks in enumerate(token_lists):
            buf[i, : len(toks)] = torch.tensor(toks, dtype=torch.long)
        buf = buf.to(self.device)
        cur = list(lens)
        generated = [[] for _ in range(b)]
        stop = ["max_new_tokens"] * b
        done = [False] * b
        for _ in range(max_new):
            active = [i for i in range(b) if not done[i]]
            if not active:
                break
            length = max(cur[i] for i in active)
            idx = torch.tensor(active, device=self.device)
            pos = torch.tensor([cur[i] - 1 for i in active], device=self.device)
            if self.dtype_name == "float32":
                logits = self.model(buf.index_select(0, idx)[:, :length], last_positions=pos)
                last = logits[:, 0]
            else:  # upstream bf16 forward: full logits, then gather
                logits = self.model(buf.index_select(0, idx)[:, :length])
                last = logits[torch.arange(len(active), device=self.device), pos]
            chosen = torch.argmax(last, dim=-1).tolist()
            del logits, last
            for j, i in enumerate(active):
                tok = int(chosen[j])
                if tok == self.eos:
                    done[i] = True
                    stop[i] = "eos"
                    continue
                generated[i].append(tok)
                buf[i, cur[i]] = tok
                cur[i] += 1
                if sig.label_decided(self.decode(generated[i])):
                    done[i] = True
                    stop[i] = "label_decided"
        return [(self.decode(g), s, len(g)) for g, s in zip(generated, stop)]


def _decode_batch(self, token_lists):
    """Greedy labels with the configured decoder ("full" recompute or "cached")."""
    if self.decoder == "cached":
        return CachedDecoder(self).generate(token_lists)
    return self.generate(token_lists)


Scorer.decode_batch = _decode_batch


class CachedDecoder:
    """Key/value-cached greedy decoding with the same operations as the full forward.

    Prefill runs the model's own forward over the right-padded prompts (identical logits,
    hence an identical first token), while a forward pre-hook on every attention module
    captures that module's inputs so its post-rotary keys and values are recomputed with
    the same operations (c_k, c_v, value-embedding mix, RMS norm, rotary). Each later
    step feeds one new token per row at that row's own position through the same
    per-layer operations as ChronoGPT_instruct.py (Block, CausalSelfAttention, MLP,
    U-net skips, tanh soft-cap), attending to cached positions <= its own. Positions
    beyond a row's prompt hold padding and are masked until overwritten.
    Adopted only after its outputs matched the full-recompute decoder on real prompts
    (protocol scoring.decoder).
    """

    def __init__(self, scorer):
        self.s = scorer
        self.torch = scorer.torch
        self.norm = scorer.module.norm
        self.F = self.torch.nn.functional

    def _rotate(self, rotary, x, pos):
        cos = rotary.cos[pos][:, None, None, :]
        sin = rotary.sin[pos][:, None, None, :]
        x1, x2 = x.float().chunk(2, dim=-1)
        y1 = x1 * cos + x2 * sin
        y2 = x1 * (-sin) + x2 * cos
        return self.torch.cat((y1, y2), 3).type_as(x)

    def _kv_from_input(self, attn, x, ve):
        b, t = x.size(0), x.size(1)
        k = attn.c_k(x).view(b, t, attn.num_heads, attn.head_dim)
        v = attn.c_v(x).view(b, t, attn.num_heads, attn.head_dim)
        if ve is not None:
            v = attn.lambdas[0] * v + attn.lambdas[1] * ve.view_as(v)
        else:
            v = attn.lambdas[0] * v
        k = attn.rotary(self.norm(k))
        return k.transpose(1, 2), v.transpose(1, 2)

    def _attn_step(self, attn, x, ve, pos, cache):
        b = x.size(0)
        q = attn.c_q(x).view(b, 1, attn.num_heads, attn.head_dim)
        k = attn.c_k(x).view(b, 1, attn.num_heads, attn.head_dim)
        v = attn.c_v(x).view(b, 1, attn.num_heads, attn.head_dim)
        if ve is not None:
            v = attn.lambdas[0] * v + attn.lambdas[1] * ve.view_as(v)
        else:
            v = attn.lambdas[0] * v
        q, k = self.norm(q), self.norm(k)
        q, k = self._rotate(attn.rotary, q, pos), self._rotate(attn.rotary, k, pos)
        keys, values = cache
        rows = self.torch.arange(b, device=x.device)
        keys[rows, :, pos, :] = k[:, 0]
        values[rows, :, pos, :] = v[:, 0]
        mask = (self.torch.arange(keys.size(2), device=x.device)[None, :] <= pos[:, None]).view(b, 1, 1, -1)
        y = self.F.scaled_dot_product_attention(q.transpose(1, 2), keys, values, attn_mask=mask)
        y = y.transpose(1, 2).contiguous().view(b, 1, -1)
        return attn.c_proj(y)

    def _block_step(self, block, x, ve, x0, pos, cache):
        x = block.lambdas[0] * x + block.lambdas[1] * x0
        if block.attn is not None:
            x = x + self._attn_step(block.attn, self.norm(x), ve, pos, cache)
        return x + block.mlp(self.norm(x))

    def _step(self, tokens, pos, caches):
        torch, m, norm = self.torch, self.s.model, self.norm
        inputs = tokens.view(-1, 1)
        b = inputs.size(0)
        x0 = norm(m.embed(inputs))
        x = x0
        ve = [m.value_embeds(inputs[i].view(-1)) for i in range(b)]
        ve = [torch.stack([ve[j][i] for j in range(b)]) if ve[0][i] is not None else None for i in range(len(ve[0]))]
        ve_enc, ve_dec = ve[:m.num_encoder_layers], ve[m.num_encoder_layers:]
        skips = []
        for i in range(m.num_encoder_layers):
            x = self._block_step(m.blocks[i], x, ve_enc[i], x0, pos, caches[i])
            skips.append(x)
        for i in range(m.num_decoder_layers):
            x = x + m.skip_weights[i] * skips.pop()
            j = m.num_encoder_layers + i
            x = self._block_step(m.blocks[j], x, ve_dec[i], x0, pos, caches[j])
        logits = m.lm_head(norm(x))
        return (15 * torch.tanh(logits / 15)).float()[:, -1]

    def generate(self, token_lists, max_new=MAX_NEW_TOKENS):
        torch, s = self.torch, self.s
        b = len(token_lists)
        lens = [len(t) for t in token_lists]
        width = max(lens)
        cap = width + max_new
        buf = torch.full((b, width), s.eos, dtype=torch.long)
        for i, toks in enumerate(token_lists):
            buf[i, : len(toks)] = torch.tensor(toks, dtype=torch.long)
        buf = buf.to(s.device)
        blocks = s.model.blocks
        caches = [None] * len(blocks)
        handles = []
        for i, block in enumerate(blocks):
            def hook(module, args, i=i):
                k, v = self._kv_from_input(module, args[0], args[1])
                keys = torch.zeros((b, k.size(1), cap, k.size(3)), dtype=k.dtype, device=s.device)
                values = torch.zeros_like(keys)
                keys[:, :, :width] = k
                values[:, :, :width] = v
                caches[i] = (keys, values)
            handles.append(block.attn.register_forward_pre_hook(hook))
        generated = [[] for _ in range(b)]
        stop = ["max_new_tokens"] * b
        done = [False] * b
        with torch.inference_mode():
            try:
                logits = s.model(buf, last_positions=torch.tensor([n - 1 for n in lens], device=s.device))
            finally:
                for h in handles:
                    h.remove()
            first = logits[:, 0]
            chosen = torch.argmax(first, dim=-1)
            del logits, first
            pos = torch.tensor(lens, device=s.device)
            for step in range(max_new):
                picks = chosen.tolist()
                for i in range(b):
                    if done[i]:
                        continue
                    tok = int(picks[i])
                    if tok == s.eos:
                        done[i] = True
                        stop[i] = "eos"
                        continue
                    generated[i].append(tok)
                    if sig.label_decided(s.decode(generated[i])):
                        done[i] = True
                        stop[i] = "label_decided"
                if all(done) or step == max_new - 1:
                    break
                chosen = torch.argmax(self._step(chosen, pos, caches), dim=-1)
                pos = pos + 1
        return [(s.decode(g), st, len(g)) for g, st in zip(generated, stop)]


def cmd_run(args):
    pins = load_pins()
    storage = os.path.expanduser(args.storage)
    out_dir = os.path.expanduser(args.out)
    os.makedirs(out_dir, exist_ok=True)
    progress_path = os.path.join(out_dir, "progress.json")
    scorer = Scorer(storage, pins, device=args.device, dtype_name=args.dtype, matmul=args.matmul, decoder=args.decoder)
    seen = done_ids(out_dir)
    pending = {}
    total_events = 0
    for ev in read_events(os.path.expanduser(args.events)):
        total_events += 1
        year = int(ev["checkpoint_year"])
        if args.years and year not in args.years:
            continue
        if args.lanes and ev.get("lane") not in args.lanes:
            continue
        pending.setdefault(year, []).append(ev)
    # sample and limit select from the full file, so a resumed probe keeps the same events
    if args.sample:
        for year in pending:
            pending[year] = sample_events(pending[year], args.sample)
    if args.limit:
        for year in pending:
            pending[year] = pending[year][: args.limit]
    for year in list(pending):
        pending[year] = [ev for ev in pending[year] if ev["event_id"] not in seen]
        if not pending[year]:
            del pending[year]
    todo = sum(len(v) for v in pending.values())
    progress = {
        "schema": "sota-news-llm-score-progress/1",
        "started_at": utc_now(),
        "events_in_file": total_events,
        "already_scored": len(seen),
        "to_score": todo,
        "scored_this_run": 0,
        "by_checkpoint": {},
        "batch_size": args.batch_size,
        "dtype": scorer.dtype_name,
        "matmul": scorer.matmul,
        "decoder": scorer.decoder,
        "variant": args.variant,
        "template_sha256": sig.template_sha256(args.variant),
    }

    def write_progress():
        progress["updated_at"] = utc_now()
        elapsed = max(1e-9, time.time() - run_started)
        progress["elapsed_seconds"] = round(elapsed, 1)
        progress["events_per_second"] = round(progress["scored_this_run"] / elapsed, 2)
        rate = progress["events_per_second"]
        progress["eta_seconds"] = round((todo - progress["scored_this_run"]) / rate, 0) if rate > 0 else None
        if scorer.device.type == "cuda":
            progress["max_gpu_memory_allocated_gib"] = round(scorer.torch.cuda.max_memory_allocated() / 2**30, 2)
        tmp = progress_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(progress, handle, indent=1)
        os.replace(tmp, progress_path)

    run_started = time.time()
    write_progress()
    code_sha = pins["reviewed_code"]["sha256"]
    for year in sorted(pending):
        events = pending[year]
        scorer.load(year)
        stats = {"to_score": len(events), "scored": 0, "labels": {}, "stops": {}, "overflow": 0,
                 "load_seconds": scorer.load_seconds, "revision": scorer.revision}
        progress["by_checkpoint"][str(year)] = stats
        items = []
        out_path = os.path.join(out_dir, f"scores-{year}1231.jsonl")
        with open(out_path, "a", encoding="utf-8") as out:
            for ev in events:
                text = sig.model_input(ev["company"], ev["headline"], args.variant)
                tokens = scorer.encode(text)
                item = {"event_id": ev["event_id"], "ev": ev, "text": text, "tokens": tokens}
                if len(tokens) + MAX_NEW_TOKENS > scorer.context:
                    stats["overflow"] += 1
                    out.write(json.dumps(result_row(item, year, scorer, code_sha, "", "context_overflow", 0, args.batch_size, args.variant)) + "\n")
                    stats["scored"] += 1
                    progress["scored_this_run"] += 1
                    continue
                items.append(item)
            out.flush()
            for batch in plan_batches(items, args.batch_size, args.max_batch_tokens):
                outputs = scorer.decode_batch([it["tokens"] for it in batch])
                for item, (raw, stop, n_new) in zip(batch, outputs):
                    row = result_row(item, year, scorer, code_sha, raw, stop, n_new, args.batch_size, args.variant)
                    out.write(json.dumps(row) + "\n")
                    stats["labels"][row["label"]] = stats["labels"].get(row["label"], 0) + 1
                    stats["stops"][stop] = stats["stops"].get(stop, 0) + 1
                out.flush()
                os.fsync(out.fileno())
                stats["scored"] += len(batch)
                progress["scored_this_run"] += len(batch)
                write_progress()
        if args.check_batch1 and items:
            stats["batch1_agreement"] = batch1_agreement(scorer, items, args.check_batch1, out_path, args.variant)
            write_progress()
    progress["finished_at"] = utc_now()
    write_progress()
    print(json.dumps({k: progress[k] for k in ("to_score", "scored_this_run", "events_per_second", "elapsed_seconds")}))


def result_row(item, year, scorer, code_sha, raw, stop, n_new, batch_size, variant):
    label, score, ok = sig.parse_label(raw, variant) if stop != "context_overflow" else ("PARSE_FAIL", 0, False)
    ev = item["ev"]
    return {
        "event_id": ev["event_id"],
        "news_id": ev["news_id"],
        "symbol": ev["symbol"],
        "checkpoint_year": year,
        "repo": sig.checkpoint_repo(year),
        "revision": scorer.revision,
        "weights_sha256": scorer.weights_sha256,
        "code_sha256": code_sha,
        "variant": variant,
        "template_sha256": sig.template_sha256(variant),
        "prompt_sha256": sig.sha256_text(item["text"]),
        "n_prompt_tokens": len(item["tokens"]),
        "n_new_tokens": n_new,
        "raw_output": raw,
        "stop": stop,
        "label": label,
        "score": score,
        "parse_ok": ok,
        "batch_size": batch_size,
        "dtype": scorer.dtype_name,
        "matmul": scorer.matmul,
        "decoder": scorer.decoder,
        "scored_at": utc_now(),
    }


def batch1_agreement(scorer, items, count, out_path, variant):
    """Rescore a deterministic subset one prompt at a time; report label agreement."""
    chosen = sorted(items, key=lambda it: hashlib.sha256(it["event_id"].encode()).hexdigest())[:count]
    labels = {}
    with open(out_path, encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            labels[row["event_id"]] = row["label"]
    agree = 0
    for item in chosen:
        raw, _, _ = scorer.decode_batch([item["tokens"]])[0]
        if sig.parse_label(raw, variant)[0] == labels.get(item["event_id"]):
            agree += 1
    return {"checked": len(chosen), "agree": agree}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--storage", default=DEFAULT_STORAGE)
    f.add_argument("--years", type=int, nargs="*")
    r = sub.add_parser("run")
    r.add_argument("--events", required=True, help="events JSONL(.gz) from prepare.py")
    r.add_argument("--out", required=True, help="private output directory")
    r.add_argument("--storage", default=DEFAULT_STORAGE)
    r.add_argument("--years", type=int, nargs="*")
    r.add_argument("--lanes", nargs="*", help="only these lanes (e.g. liquid first, small later)")
    r.add_argument("--batch-size", type=int, default=32)
    r.add_argument("--max-batch-tokens", type=int, default=4096, help="items x (prompt + 16) cap per batch")
    r.add_argument("--limit", type=int, default=0, help="per-checkpoint cap in file order")
    r.add_argument("--sample", type=int, default=0, help="per-checkpoint label-agnostic sample: smallest sha256(event_id)")
    r.add_argument("--variant", default=sig.OPERATIVE_VARIANT, choices=sorted(sig.VARIANTS))
    r.add_argument("--check-batch1", type=int, default=0, help="rescore N events per checkpoint at batch size 1")
    r.add_argument("--device", default="cuda")
    r.add_argument("--dtype", default="float32", choices=("float32", "bfloat16"))
    r.add_argument("--matmul", default="highest", choices=("highest", "tf32"))
    r.add_argument("--decoder", default="full", choices=("full", "cached"))
    args = parser.parse_args(argv)
    if args.command == "fetch":
        cmd_fetch(args)
    else:
        cmd_run(args)


if __name__ == "__main__":
    main()
