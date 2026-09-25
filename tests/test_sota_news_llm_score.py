"""SYN: score.py with a mocked scorer (no GPU, torch, tiktoken or model files).

Covers resumable scoring, per-event provenance fields, parse outcomes, context overflow,
batch planning and the static load-policy rules (weights_only loading, no
from_pretrained, no remote-code loader).
"""

import gzip
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints/us-equities/sota-mover/news-llm"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, BLUEPRINT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


score = load("news_llm_score_under_test", "score.py")
sig = score.sig
VARIANT = "llt_alpaca"  # a YES/NO/UNKNOWN variant; the operative choice is tested in the signal tests


class FakeScorer:
    """Stands in for score.Scorer: words are tokens, outputs come from the headline."""

    instances = []

    def __init__(self, storage, pins, device="cuda", dtype_name="float32", matmul="highest", decoder="full"):
        self.matmul = matmul
        self.decoder = decoder
        self.device = SimpleNamespace(type="cpu")
        self.dtype_name = dtype_name
        self.context = pins["tokenizer"]["context_tokens"]
        self.loaded = []
        self.revision = None
        self.weights_sha256 = None
        self.load_seconds = 0.0
        self.batches = []
        FakeScorer.instances.append(self)

    def encode(self, text):
        n = 5000 if "OVERFLOW" in text else len(text.split())
        return list(range(n))

    def decode(self, ids):
        return " ".join(str(i) for i in ids)

    def load(self, year):
        self.loaded.append(year)
        entry = score.load_pins()["checkpoints"][str(year)]
        self.revision = entry["revision"]
        self.weights_sha256 = entry["files"]["pytorch_model.bin"]["sha256"]

    def decode_batch(self, token_lists):
        return self.generate(token_lists)

    def generate(self, token_lists, max_new=16):
        self.batches.append(len(token_lists))
        out = []
        for tokens in token_lists:
            text = FakeScorer.by_length[len(tokens)]
            out.append((text, "newline", 2))
        return out


def event(i, headline, year):
    return {
        "event_id": f"{i}:SYM{i}",
        "news_id": str(i),
        "symbol": f"SYM{i}",
        "company": f"Company {i} Inc.",
        "headline": headline,
        "checkpoint_year": year,
    }


class ScoreRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        heads = [
            ("Acme wins a large contract", 2019, "YES\n"),
            ("Acme loses its largest customer badly", 2019, "NO\n"),
            ("Acme schedules an annual meeting for shareholders soon", 2019, "UNKNOWN\n"),
            ("Acme says something odd about the weather today again", 2023, "Perhaps\n"),
            ("OVERFLOW headline", 2023, None),
        ]
        self.events = [event(i, h, y) for i, (h, y, _) in enumerate(heads)]
        FakeScorer.by_length = {}
        for ev, (_, _, out) in zip(self.events, heads):
            if out is not None:
                n = len(sig.model_input(ev["company"], ev["headline"], VARIANT).split())
                self.assertNotIn(n, FakeScorer.by_length, "fixture lengths must be distinct")
                FakeScorer.by_length[n] = out
        self.events_path = self.dir / "events.jsonl.gz"
        with gzip.open(self.events_path, "wt") as fh:
            for ev in self.events:
                fh.write(json.dumps(ev) + "\n")
        self.original = score.Scorer
        score.Scorer = FakeScorer
        FakeScorer.instances = []

    def tearDown(self):
        score.Scorer = self.original
        self.tmp.cleanup()

    def run_score(self, *extra):
        score.main(["run", "--events", str(self.events_path), "--out", str(self.dir / "scores"), "--batch-size", "2", "--variant", VARIANT, *extra])

    def rows(self):
        out = {}
        for path in sorted((self.dir / "scores").glob("scores-*.jsonl")):
            for line in path.read_text().splitlines():
                row = json.loads(line)
                out[row["event_id"]] = row
        return out

    def test_scores_every_event_with_provenance_and_is_resumable(self):
        self.run_score()
        rows = self.rows()
        self.assertEqual(len(rows), 5)
        by_head = {ev["headline"]: rows[ev["event_id"]] for ev in self.events}
        self.assertEqual(by_head["Acme wins a large contract"]["label"], "YES")
        self.assertEqual(by_head["Acme wins a large contract"]["score"], 1)
        self.assertEqual(by_head["Acme loses its largest customer badly"]["score"], -1)
        self.assertEqual(by_head["Acme schedules an annual meeting for shareholders soon"]["label"], "UNKNOWN")
        odd = by_head["Acme says something odd about the weather today again"]
        self.assertEqual((odd["label"], odd["score"], odd["parse_ok"]), ("PARSE_FAIL", 0, False))
        over = by_head["OVERFLOW headline"]
        self.assertEqual((over["stop"], over["label"]), ("context_overflow", "PARSE_FAIL"))
        pins = score.load_pins()
        for ev in self.events:
            row = rows[ev["event_id"]]
            year = ev["checkpoint_year"]
            self.assertEqual(row["checkpoint_year"], year)
            self.assertEqual(row["revision"], pins["checkpoints"][str(year)]["revision"])
            self.assertEqual(row["weights_sha256"], pins["checkpoints"][str(year)]["files"]["pytorch_model.bin"]["sha256"])
            self.assertEqual(row["code_sha256"], pins["reviewed_code"]["sha256"])
            self.assertEqual((row["variant"], row["template_sha256"]), (VARIANT, sig.template_sha256(VARIANT)))
            self.assertEqual(row["prompt_sha256"], sig.sha256_text(sig.model_input(ev["company"], ev["headline"], VARIANT)))
            self.assertIn("raw_output", row)
        self.assertTrue((self.dir / "scores/scores-20191231.jsonl").exists())
        self.assertTrue((self.dir / "scores/scores-20231231.jsonl").exists())
        self.assertEqual(FakeScorer.instances[0].loaded, [2019, 2023])
        progress = json.loads((self.dir / "scores/progress.json").read_text())
        self.assertEqual(progress["scored_this_run"], 5)
        self.assertEqual(progress["by_checkpoint"]["2019"]["labels"], {"YES": 1, "NO": 1, "UNKNOWN": 1})
        # a second run finds nothing left to score
        self.run_score()
        self.assertEqual(len(self.rows()), 5)
        progress = json.loads((self.dir / "scores/progress.json").read_text())
        self.assertEqual((progress["to_score"], progress["scored_this_run"]), (0, 0))

    def test_torn_last_line_is_rescored(self):
        self.run_score()
        path = self.dir / "scores/scores-20231231.jsonl"
        lines = path.read_text().splitlines()
        path.write_text("\n".join(lines[:-1]) + "\n" + lines[-1][: len(lines[-1]) // 2])
        self.run_score()
        progress = json.loads((self.dir / "scores/progress.json").read_text())
        self.assertEqual(progress["scored_this_run"], 1)

    def test_resumed_sample_keeps_the_same_events(self):
        self.run_score("--sample", "2", "--years", "2019")
        first = set(self.rows())
        self.assertEqual(len(first), 2)
        self.run_score("--sample", "2", "--years", "2019")
        self.assertEqual(set(self.rows()), first)  # nothing new drawn on resume
        self.run_score("--sample", "3", "--years", "2019")
        self.assertEqual(len(self.rows()), 3)
        self.assertTrue(first < set(self.rows()))

    def test_lanes_filter(self):
        for i, ev in enumerate(self.events):
            ev["lane"] = "liquid" if i % 2 == 0 else "small"
        with gzip.open(self.events_path, "wt") as fh:
            for ev in self.events:
                fh.write(json.dumps(ev) + "\n")
        self.run_score("--lanes", "liquid")
        self.assertEqual(len(self.rows()), 3)
        self.run_score("--lanes", "small")
        self.assertEqual(len(self.rows()), 5)

    def test_years_filter_and_limit(self):
        self.run_score("--years", "2023", "--limit", "1")
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(next(iter(rows.values()))["checkpoint_year"], 2023)


class Helpers(unittest.TestCase):
    def test_plan_batches_sorts_by_length_then_id(self):
        items = [{"event_id": e, "tokens": [0] * n} for e, n in (("c", 3), ("a", 5), ("b", 3), ("d", 1))]
        batches = score.plan_batches(items, 2)
        self.assertEqual([[i["event_id"] for i in b] for b in batches], [["d", "b"], ["c", "a"]])

    def test_plan_batches_token_budget(self):
        items = [{"event_id": f"e{i}", "tokens": [0] * 84} for i in range(10)]  # width 100 with 16 new tokens
        batches = score.plan_batches(items, 32, max_batch_tokens=400)
        self.assertEqual([len(b) for b in batches], [4, 4, 2])
        self.assertEqual([len(b) for b in score.plan_batches(items, 3, max_batch_tokens=10_000)], [3, 3, 3, 1])
        one_big = [{"event_id": "big", "tokens": [0] * 1000}]
        self.assertEqual(len(score.plan_batches(one_big, 32, max_batch_tokens=400)), 1)  # never empty

    def test_sample_events_is_deterministic_and_label_agnostic(self):
        evs = [{"event_id": f"{i}:X", "headline": "h"} for i in range(50)]
        a = score.sample_events(evs, 7)
        b = score.sample_events(list(reversed(evs)), 7)
        self.assertEqual([e["event_id"] for e in a], [e["event_id"] for e in b])
        self.assertEqual(len(a), 7)


class LoadPolicy(unittest.TestCase):
    """Static checks of score.py against the checkpoints.json load policy."""

    source = (BLUEPRINT / "score.py").read_text()

    def test_every_torch_load_is_weights_only(self):
        calls = re.findall(r"torch\.load\(([^)]*)\)", self.source)
        self.assertTrue(calls)
        for args in calls:
            self.assertIn("weights_only=True", args)

    def test_no_remote_code_or_from_pretrained(self):
        code = "\n".join(line for line in self.source.splitlines() if not line.lstrip().startswith("#"))
        self.assertFalse("trust_remote_code" in code)
        self.assertFalse("AutoModel" in code)
        self.assertIsNone(re.search(r"\.from_pretrained\(", code))
        self.assertTrue('os.environ["HF_HUB_OFFLINE"] = "1"' in code)

    def test_float32_is_the_default_and_the_override_drops_only_the_bf16_casts(self):
        self.assertTrue('r.add_argument("--dtype", default="float32"' in self.source)
        body = self.source[self.source.index("def install_fp32_forwards"):self.source.index("class Scorer")]
        code = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("#"))
        code = code.split('"""')[0] + code.split('"""')[2]  # drop the docstring
        self.assertFalse("bfloat16" in code)
        self.assertFalse("half(" in code)
        for op in ("15 * torch.tanh(logits / 15)", "self.skip_weights[i] * skip_connections.pop()",
                   "x0 = norm(self.embed(inputs))", "base = [emb(inputs) for emb in self.embed]"):
            self.assertTrue(op in code)
        self.assertTrue('r.add_argument("--matmul", default="highest"' in self.source, "exact fp32 matmuls by default")
        self.assertTrue('torch.backends.cuda.matmul.allow_tf32 = matmul == "tf32"' in self.source)

    def test_model_code_is_hash_checked_before_import(self):
        body = self.source[self.source.index("def _import_model_code"):self.source.index("def load(self, year)")]
        self.assertLess(body.index("sha256_file(path)"), body.index("exec_module"))

    def test_fetch_uses_pinned_revisions_only(self):
        self.assertTrue("resolve/{entry['revision']}/{name}" in self.source)
        pins = json.loads((BLUEPRINT / "checkpoints.json").read_text())
        for entry in pins["checkpoints"].values():
            for meta in entry["files"].values():
                self.assertRegex(meta["sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
