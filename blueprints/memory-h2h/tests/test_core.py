"""Authored offline integration fixtures, not live/upstream acceptance tests."""

import contextlib
import importlib
import io
import json
import math
import os
import tempfile
import unittest
from collections import Counter
from dataclasses import asdict, replace
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from h2h.adapters.bm25 import BM25
from h2h.data import Question, file_sha256, load_questions, parse_date, stratified_subset
from h2h.protocol import CompletionFailure, build_answer_prompt, chat_completion, run_question
from h2h.run import _read_records, main, summarize
from h2h.score import get_anscheck_prompt, judge_question, parse_judgment, recall_at_k, score_record
from h2h.stats import accuracy, holm_adjust, paired_difference
from h2h.types import IngestStats, ModelRoute, Retrieved, Session, Turn


ROUTE = ModelRoute("https://models.invalid/v1/", "reader", "TEST_H2H_KEY")
JUDGE = ModelRoute("https://models.invalid/v1/", "judge", "TEST_H2H_KEY")


def fixture() -> list[dict]:
    cases = [
        ("q-user", "single-session-user", "What color is my bicycle?", "blue"),
        ("q-time", "temporal-reasoning", "How many days passed?", "18 days"),
        ("q-update", "knowledge-update", "Where do I live now?", "Boston"),
    ]
    return [{
        "question_id": qid, "question_type": task, "question": question,
        "answer": answer, "question_date": "2023/05/25 (Thu) 14:32",
        "haystack_session_ids": ["answer_late", "filler_early"],
        "haystack_dates": ["2023/05/20 (Sat) 18:21", "2023/05/20 (Sat) 02:21"],
        "haystack_sessions": [
            [{"role": "user", "content": f"The relevant fact is {answer}", "has_answer": True},
             {"role": "assistant", "content": "Acknowledged.", "has_answer": False}],
            [{"role": "user", "content": "Unrelated filler.", "has_answer": False}],
        ],
        "answer_session_ids": ["answer_late"],
    } for qid, task, question, answer in cases]


def questions() -> list[Question]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fixture.json"
        path.write_text(json.dumps(fixture()), encoding="utf-8")
        return load_questions(path)


class FakeAdapter:
    name = "fake"
    version = "fixture-v1"
    needs_llm = True
    reports_session_ids = True

    def __init__(self):
        self.calls = []
        self.sessions = []
        self.namespace = None

    def start(self, workdir, llm, embed):
        self.calls.append(("start", workdir, llm, embed))

    def reset(self, namespace):
        self.calls.append(("reset", namespace))
        self.namespace = namespace
        self.sessions = []

    def ingest(self, namespace, sessions):
        if namespace != self.namespace or self.sessions:
            raise AssertionError("reset must precede ingest")
        self.calls.append(("ingest", namespace, sessions))
        self.sessions = list(sessions)
        return IngestStats(len(sessions), 0.25, 2, ["synthetic ingestion"])

    def retrieve(self, namespace, query, k, question_date):
        if namespace != self.namespace:
            raise AssertionError("incorrect namespace")
        self.calls.append(("retrieve", namespace, query, k, question_date))
        chosen = self.sessions[-1]
        return [Retrieved("\n".join(turn.content for turn in chosen.turns), (chosen.session_id,), 0.8)]

    def stop(self):
        self.calls.append(("stop",))
        self.sessions.clear()


class Endpoint:
    """urlopen replacement: validates the wire request, never opens a socket."""

    def __init__(self, fail_judge=False, missing_usage=False):
        self.requests = []
        self.fail_judge = fail_judge
        self.missing_usage = missing_usage

    def __call__(self, request, timeout):
        if request.full_url != "https://models.invalid/v1/chat/completions":
            raise AssertionError(request.full_url)
        if request.get_method() != "POST" or timeout != 300:
            raise AssertionError("wrong method/timeout")
        if request.get_header("Content-type") != "application/json":
            raise AssertionError("missing JSON content type")
        body = json.loads(request.data)
        self.requests.append(body)
        if body["n"] != 1 or body["temperature"] != 0:
            raise AssertionError("request differs from upstream")
        if len(body["messages"]) != 1 or body["messages"][0]["role"] != "user":
            raise AssertionError("incorrect message shape")
        judge = body["model"] == "judge"
        if body["max_tokens"] != (10 if judge else 500):
            raise AssertionError("incorrect generation limit")
        prompt = body["messages"][0]["content"]
        if judge:
            if self.fail_judge:
                raise HTTPError(request.full_url, 503, "fixture failure", {}, None)
            text = "yes"
        else:
            if "Correct Answer:" in prompt or "has_answer" in prompt or "answer_late" in prompt:
                raise AssertionError("gold metadata leaked to answerer")
            text = "unknown"
            for answer in ("blue", "18 days", "Boston"):
                if f"fact is {answer}" in prompt:
                    text = answer
        result = {
            "id": f"response-{len(self.requests)}", "model": body["model"],
            "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        }
        if not self.missing_usage:
            result["usage"] = {
                "prompt_tokens": 40 if judge else 50, "completion_tokens": 1 if judge else 2,
                "total_tokens": 41 if judge else 52,
                "prompt_tokens_details": {"cached_tokens": 0},
            }
        return io.BytesIO(json.dumps(result).encode("utf-8"))


class DataTests(unittest.TestCase):
    def test_loader_preserves_dates_roles_and_dataset_gold(self):
        item = questions()[0]
        self.assertEqual(item.answer_session_ids, ("answer_late",))
        self.assertEqual(item.sessions[0].date, "2023/05/20 (Sat) 18:21")
        self.assertEqual([turn.role for turn in item.sessions[0].turns], ["user", "assistant"])
        self.assertEqual(set(asdict(item.sessions[0].turns[0])), {"role", "content"})

    def test_dates_include_time_after_parenthesized_weekday(self):
        self.assertLess(parse_date("2023/05/20 (Sat) 02:21"), parse_date("2023/05/20 (Sat) 18:21"))
        self.assertEqual(parse_date("2023/05/20 (Sat) 02:21"), parse_date("2023-05-20T02:21:00Z"))
        with self.assertRaises(ValueError):
            parse_date("not a date")

    def test_checksum_and_alignment_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            path.write_text(json.dumps(fixture()), encoding="utf-8")
            self.assertEqual(len(load_questions(path, file_sha256(path))), 3)
            with self.assertRaises(ValueError):
                load_questions(path, "0" * 64)
            raw = fixture()
            raw[0]["haystack_dates"].pop()
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_questions(path)

    def test_duplicate_ids_and_invalid_roles_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            for mutate in (
                lambda raw: raw.append(raw[0]),
                lambda raw: raw[0]["haystack_sessions"][0][0].update(role="system"),
                lambda raw: raw[0]["haystack_session_ids"].__setitem__(1, "answer_late"),
            ):
                raw = fixture()
                mutate(raw)
                path.write_text(json.dumps(raw), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_questions(path)

    def test_subset_is_equal_seeded_and_input_order_independent(self):
        pool = [replace(question, question_id=f"{question.question_id}-{i}") for question in questions() for i in range(12)]
        first = stratified_subset(pool, 12, 20261002)
        self.assertEqual(first, stratified_subset(list(reversed(pool)), 12, 20261002))
        self.assertEqual(sorted(Counter(q.question_type for q in first).values()), [4, 4, 4])
        self.assertEqual(len({q.question_id for q in first}), 12)
        self.assertNotEqual(first, stratified_subset(pool, 12, 1))
        for start in range(0, 12, 3):
            self.assertEqual(len({q.question_type for q in first[start:start + 3]}), 3)

    def test_invalid_subset_does_not_silently_unbalance(self):
        pool = questions()
        self.assertEqual(stratified_subset(pool, 0, 7), [])
        for n in (-1, 2, 6):
            with self.assertRaises(ValueError):
                stratified_subset(pool, n, 7)


class ProtocolTests(unittest.TestCase):
    def test_whole_protocol_on_three_questions(self):
        adapter, endpoint = FakeAdapter(), Endpoint()
        records = []
        with patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", endpoint):
            for question in questions():
                answered = run_question(adapter, question, 10, ROUTE, 4096)
                records.append(score_record(answered, question, JUDGE))
        self.assertEqual(len(endpoint.requests), 6)
        self.assertEqual([record["hypothesis"] for record in records], ["blue", "18 days", "Boston"])
        self.assertTrue(all(record["autoeval_label"]["label"] for record in records))
        self.assertEqual(len({record["namespace"] for record in records}), 3)
        self.assertEqual([call[0] for call in adapter.calls], ["reset", "ingest", "retrieve"] * 3)
        for record in records:
            self.assertEqual(record["retrieved"][0]["session_ids"], ["answer_late"])
            self.assertEqual(record["ingest"]["sessions"], 2)
            self.assertEqual(record["ingest"]["llm_calls"], 2)
            self.assertEqual(record["usage"]["answer"]["total_tokens"], 52)
            self.assertEqual(record["usage"]["judge"]["total_tokens"], 41)
            self.assertEqual(record["model_calls"][0]["usage"]["prompt_tokens_details"], {"cached_tokens": 0})
            self.assertEqual(recall_at_k(record, 10), 1.0)
            self.assertGreaterEqual(record["seconds"], 0)
        for call in adapter.calls:
            if call[0] == "ingest":
                sessions = call[2]
                self.assertEqual([s.date for s in sessions], ["2023/05/20 (Sat) 02:21", "2023/05/20 (Sat) 18:21"])
                self.assertEqual([s.session_id for s in sessions], ["session-000000", "session-000001"])
                self.assertNotIn("has_answer", repr(sessions))

    def test_answer_template_is_official_direct_reader(self):
        question = questions()[0]
        prompt, budget = build_answer_prompt(question, [Retrieved("native context")], 4096)
        self.assertEqual(prompt,
            "I will give you several history chats between you and a user. Please answer the question based on the relevant chat history.\n\n\nHistory Chats:\n\nnative context\n\nCurrent Date: 2023/05/25 (Thu) 14:32\nQuestion: What color is my bicycle?\nAnswer:")
        self.assertFalse(budget["truncated"])

    def test_unicode_context_is_truncated_without_cutting_question(self):
        question = questions()[0]
        prompt, budget = build_answer_prompt(question, [Retrieved("🌙雪" * 1000)], 500)
        self.assertLessEqual(len(prompt.encode("utf-8")) + 32, 500)
        self.assertIn(question.question, prompt)
        self.assertIn(question.question_date, prompt)
        self.assertTrue(budget["truncated"])
        self.assertNotIn("\ufffd", prompt)
        with self.assertRaises(ValueError):
            build_answer_prompt(question, [], 1)

    def test_zero_k_skips_native_recall(self):
        adapter, endpoint = FakeAdapter(), Endpoint()
        with patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", endpoint):
            record = run_question(adapter, questions()[0], 0, ROUTE, 4096)
        self.assertEqual(record["retrieved"], [])
        self.assertEqual(record["hypothesis"], "unknown")
        self.assertEqual([call[0] for call in adapter.calls], ["reset", "ingest"])

    def test_missing_usage_is_unknown(self):
        with patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", Endpoint(missing_usage=True)):
            record = run_question(FakeAdapter(), questions()[0], 1, ROUTE, 4096)
            record = score_record(record, questions()[0], JUDGE)
        self.assertEqual(record["usage"], {"answer": None, "judge": None})
        self.assertIsNone(record["adapter_model_usage"])

    def test_body_read_failures_retain_an_unknown_model_attempt(self):
        class BrokenBody(io.BytesIO):
            def __init__(self, error):
                super().__init__(b"")
                self.error = error
            def read(self, *args):
                raise self.error
        for error in (TimeoutError("fixture timeout"), IncompleteRead(b"", 3)):
            with self.subTest(error=type(error).__name__), patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", return_value=BrokenBody(error)):
                with self.assertRaises(CompletionFailure) as caught:
                    run_question(FakeAdapter(), questions()[0], 1, ROUTE, 4096)
            record = caught.exception.record
            self.assertEqual(record["status"], "answer_failed")
            self.assertEqual(record["model_calls"][0]["outcome"], "error")
            self.assertIsNone(record["model_calls"][0]["usage"])

    def test_designated_key_is_transient_and_url_secrets_are_rejected(self):
        requests = []
        endpoint = Endpoint()
        def capture(request, timeout):
            requests.append(request)
            return endpoint(request, timeout)
        with patch.dict(os.environ, {"TEST_H2H_KEY": "fixture-key"}, clear=True), patch("h2h.protocol.urlopen", capture):
            record = run_question(FakeAdapter(), questions()[0], 1, ROUTE, 4096)
            self.assertEqual(requests[0].get_header("Authorization"), "Bearer fixture-key")
            for url in ("https://secret@models.invalid/v1", "https://models.invalid/v1?key=value"):
                with self.assertRaises(ValueError):
                    chat_completion(ModelRoute(url, "reader"), "q", 500)
        self.assertNotIn("fixture-key", json.dumps(record))

    def test_reported_over_budget_response_cannot_be_judged(self):
        def over_budget(request, timeout):
            response = json.load(Endpoint()(request, timeout))
            response["usage"]["prompt_tokens"] = 9000
            return io.BytesIO(json.dumps(response).encode())
        with patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", over_budget):
            record = run_question(FakeAdapter(), questions()[0], 1, ROUTE, 4096)
            self.assertTrue(record["prompt_budget"]["provider_cap_exceeded"])
            with self.assertRaises(ValueError):
                score_record(record, questions()[0], JUDGE)


class JudgeTests(unittest.TestCase):
    def test_handwritten_cases_for_every_type(self):
        cases = [
            ("single-session-user", "What color?", "blue", "It is blue.", "Correct Answer: blue", "subset of the information"),
            ("single-session-assistant", "What did you book?", "train", "I booked a train.", "Correct Answer: train", "intermediate steps"),
            ("multi-session", "Which two cities?", "Paris and Rome", "Paris", "Correct Answer: Paris and Rome", "subset of the information"),
            ("temporal-reasoning", "How many days?", "18", "19 days", "Correct Answer: 18", "do not penalize off-by-one errors"),
            ("knowledge-update", "Where now?", "Boston", "Previously Paris, now Boston.", "Correct Answer: Boston", "previous information along with an updated answer"),
            ("single-session-preference", "Recommend a snack", "vegan", "Choose a vegan snack.", "Rubric: vegan", "does not need to reflect all the points"),
        ]
        for task, question, answer, hypothesis, reference, policy in cases:
            with self.subTest(task=task):
                prompt = get_anscheck_prompt(task, question, answer, hypothesis)
                self.assertIn(f"Question: {question}", prompt)
                self.assertIn(reference, prompt)
                self.assertIn(f"Model Response: {hypothesis}", prompt)
                self.assertIn(policy, prompt)
                self.assertTrue(prompt.endswith("Is the model response correct? Answer yes or no only."))
        self.assertEqual(
            get_anscheck_prompt("single-session-user", "q", "a", "h"),
            "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the information required by the answer, answer no. \n\nQuestion: q\n\nCorrect Answer: a\n\nModel Response: h\n\nIs the model response correct? Answer yes or no only.")

    def test_abstention_prompt_and_upstream_id_detection(self):
        question = replace(questions()[0], question_id="example_abs_suffix", answer="Not provided")
        endpoint = Endpoint()
        with patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", endpoint):
            result = judge_question(question, "I don't have that information.", JUDGE)
        prompt = endpoint.requests[0]["messages"][0]["content"]
        self.assertIn("an unanswerable question", prompt)
        self.assertIn("Explanation: Not provided", prompt)
        self.assertIn("Does the model correctly identify the question as unanswerable?", prompt)
        self.assertTrue(result["autoeval_label"]["label"])

    def test_yes_substring_parser_is_faithful_even_for_odd_outputs(self):
        for text in ("yes", " YES\n", "Yes.", "no, yes", "yesterday"):
            self.assertTrue(parse_judgment(text))
        for text in ("no", "NO.", "", "correct"):
            self.assertFalse(parse_judgment(text))
        with self.assertRaises(NotImplementedError):
            get_anscheck_prompt("unknown", "q", "a", "h")


class RecallTests(unittest.TestCase):
    def test_gold_coverage_deduplicates_ids_and_respects_k(self):
        record = {"question_id": "q", "answer_session_ids": ["s1", "s2", "s2"],
                  "retrieved": [{"session_ids": ["s1", "s1"]}, {"session_ids": ["s2", "other"]}]}
        self.assertEqual(recall_at_k(record, 1), 0.5)
        self.assertEqual(recall_at_k(record, 2), 1.0)

    def test_mixed_provenance_is_labeled_and_counted_as_a_lower_bound(self):
        class MixedAdapter(FakeAdapter):
            def retrieve(self, namespace, query, k, question_date):
                return super().retrieve(namespace, query, k, question_date) + [Retrieved("Unattributed context")]
        question = replace(questions()[0], answer_session_ids=("answer_late", "filler_early"))
        with patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", Endpoint()):
            record = score_record(run_question(MixedAdapter(), question, 10, ROUTE, 4096), question, JUDGE)
        self.assertEqual(record["provenance"], "partial")
        self.assertEqual(recall_at_k(record, 10), 0.5)
        result = summarize([record], {"question_ids": [question.question_id], "k": 10})
        self.assertEqual(result["recall_at_k"]["partial_provenance_questions"], 1)
        self.assertEqual(result["recall_at_k"]["eligible_questions"], 1)
        self.assertEqual(result["recall_at_k"]["mean"], 0.5)

    def test_absence_of_provenance_is_not_zero_recall(self):
        base = {"question_id": "q", "answer_session_ids": ["s1"], "retrieved": [{"text": "context", "session_ids": []}]}
        self.assertIsNone(recall_at_k(base, 10))
        self.assertIsNone(recall_at_k({**base, "session_ids_reported": True}, 10))
        self.assertIsNone(recall_at_k({**base, "retrieved": []}, 10))
        self.assertEqual(recall_at_k({**base, "retrieved": [], "session_ids_reported": True}, 10), 0.0)
        self.assertIsNone(recall_at_k({**base, "question_id": "q_abs", "session_ids_reported": True}, 10))


class StatisticsTests(unittest.TestCase):
    def test_accuracy_known_answers_and_fixed_seed(self):
        self.assertEqual(accuracy([True] * 12)["ci95"], [1.0, 1.0])
        self.assertEqual(accuracy([False] * 12)["ci95"], [0.0, 0.0])
        balanced = accuracy([False, True])
        self.assertEqual(balanced["accuracy"], 0.5)
        self.assertEqual(balanced["ci95"], [0.0, 1.0])
        self.assertEqual(balanced, accuracy([False, True]))
        self.assertEqual(balanced["resamples"], 10_000)
        self.assertIsNone(accuracy([])["accuracy"])

    def test_failing_control_paired_interval_excludes_zero(self):
        good = [{"question_id": str(i), "autoeval_label": {"label": True}} for i in range(30)]
        bad = [{"question_id": str(i), "autoeval_label": {"label": False}} for i in reversed(range(30))]
        result = paired_difference(good, bad)
        self.assertEqual(result["difference"], 1.0)
        self.assertEqual(result["ci95"], [1.0, 1.0])
        self.assertGreater(result["ci95"][0], 0)
        self.assertEqual(paired_difference(bad, good)["ci95"], [-1.0, -1.0])
        self.assertEqual(paired_difference(good, list(reversed(good)))["ci95"], [0.0, 0.0])
        with self.assertRaises(ValueError):
            paired_difference(good, bad[:-1])

    def test_pairing_aligns_heterogeneous_question_ids_and_rejects_duplicates(self):
        first = [{"question_id": str(i), "autoeval_label": {"label": bool(i % 2)}} for i in range(10)]
        result = paired_difference(first, list(reversed(first)))
        self.assertEqual(result["difference"], 0.0)
        self.assertEqual(result["ci95"], [0.0, 0.0])
        with self.assertRaises(ValueError):
            paired_difference(first, first + [first[0]])

    def test_holm_step_down_preserves_original_order(self):
        self.assertEqual(holm_adjust([0.04, 0.01, 0.03]), [0.06, 0.03, 0.06])
        self.assertEqual(holm_adjust([0.8, 0.9]), [1.0, 1.0])
        self.assertEqual(holm_adjust([]), [])
        for values in ([-0.1], [1.1], [float("nan")]):
            with self.assertRaises(ValueError):
                holm_adjust(values)


class ControlTests(unittest.TestCase):
    def test_bm25_reference_formula_both_roles_and_reset(self):
        memory = BM25()
        memory.start(Path("unused"), None, None)
        sessions = [
            Session("s1", "2023-01-01", (Turn("assistant", "alpha alpha"),)),
            Session("s2", "2023-01-02", (Turn("user", "beta beta"),)),
            Session("s3", "2023-01-03", (Turn("user", "gamma gamma"),)),
        ]
        memory.reset("one")
        self.assertEqual(memory.ingest("one", sessions).llm_calls, 0)
        hits = memory.retrieve("one", "ALPHA", 1, None)
        self.assertEqual(hits[0].session_ids, ("s1",))
        self.assertAlmostEqual(hits[0].score, math.log(2.5 / 1.5) * 5 / 3.5)
        self.assertIn("assistant: alpha alpha", hits[0].text)
        memory.reset("two")
        memory.ingest("two", [Session("s4", "2023-01-04", ())])
        self.assertEqual(memory.retrieve("two", "alpha", 1, None)[0].session_ids, ("s4",))
        with self.assertRaises(ValueError):
            memory.retrieve("one", "alpha", 1, None)
        memory.stop()
        with self.assertRaises(ValueError):
            memory.retrieve("two", "alpha", 1, None)

    def test_bm25_empty_store_and_stable_ties(self):
        memory = BM25()
        memory.reset("empty")
        memory.ingest("empty", [])
        self.assertEqual(memory.retrieve("empty", "q", 10, None), [])
        memory.ingest("empty", [Session("first", "2023-01-01", ()), Session("second", "2023-01-01", ())])
        self.assertEqual([hit.session_ids for hit in memory.retrieve("empty", "q", 10, None)], [("first",), ("second",)])

    def test_bm25_preserves_upstream_negative_idf_floor(self):
        memory = BM25()
        memory.reset("common")
        memory.ingest("common", [
            Session(word, "2023-01-01", (Turn("user", f"common {word}"),))
            for word in ("alpha", "beta", "gamma")
        ])
        average_idf = (math.log(0.5 / 3.5) + 3 * math.log(2.5 / 1.5)) / 4
        for hit in memory.retrieve("common", "common", 3, None):
            self.assertAlmostEqual(hit.score, 0.25 * average_idf)

    def test_no_memory_control_returns_nothing(self):
        memory = importlib.import_module("h2h.adapters.none").build()
        endpoint = Endpoint()
        with patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", endpoint):
            result = run_question(memory, questions()[0], 10, ROUTE, 4096)
        self.assertEqual(result["retrieved"], [])
        self.assertEqual(result["hypothesis"], "unknown")
        self.assertEqual(result["ingest"]["llm_calls"], 0)
        self.assertIsNone(recall_at_k(result, 10))


class RunnerTests(unittest.TestCase):
    def _argv(self, directory):
        data = Path(directory) / "fixture.json"
        data.write_text(json.dumps(fixture()), encoding="utf-8")
        return ["--arm", "fake", "--data", str(data), "--n", "3", "--seed", "20261002",
                "--k", "10", "--answer-model", "reader", "--judge-model", "judge",
                "--base-url", "https://models.invalid/v1/", "--out", str(Path(directory) / "out"),
                "--allow-custom-data"]

    def test_cli_outputs_resume_and_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = self._argv(directory)
            adapter, endpoint = FakeAdapter(), Endpoint()
            with patch("h2h.adapters.build", return_value=adapter), patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", endpoint), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(argv + ["--limit", "1"]), 0)
                self.assertEqual(main(argv), 0)
                calls_after_finish = len(endpoint.requests)
                self.assertEqual(main(argv), 0)
            out = Path(directory) / "out" / "fake"
            records = [json.loads(line) for line in (out / "records.jsonl").read_text().splitlines()]
            hypotheses = [json.loads(line) for line in (out / "hypotheses.jsonl").read_text().splitlines()]
            summary = json.loads((out / "summary.json").read_text())
            self.assertEqual(len(records), 3)
            self.assertEqual(len({record["question_id"] for record in records}), 3)
            self.assertEqual(len(endpoint.requests), calls_after_finish)
            self.assertEqual(calls_after_finish, 6)
            self.assertEqual([set(entry) for entry in hypotheses], [{"question_id", "hypothesis"}] * 3)
            self.assertEqual(summary["accuracy"]["accuracy"], 1.0)
            self.assertEqual(summary["model_usage"]["answer"]["counters"]["total_tokens"]["reported_sum"], 156)
            self.assertEqual(summary["status"], "complete")
            self.assertFalse(summary["config"]["pinned_cleaned_s"])
            self.assertEqual(sum(call[0] == "start" for call in adapter.calls), 2)
            self.assertEqual(sum(call[0] == "stop" for call in adapter.calls), 2)

    def test_failed_judge_keeps_answer_usage_and_resumes_without_ingest(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = self._argv(directory) + ["--limit", "1"]
            first = FakeAdapter()
            with patch("h2h.adapters.build", return_value=first), patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", Endpoint(fail_judge=True)), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):
                    main(argv)
            out = Path(directory) / "out" / "fake"
            summary = json.loads((out / "summary.json").read_text())
            self.assertEqual(summary["completed"], 0)
            self.assertEqual(summary["pending_questions"], 1)
            self.assertEqual(summary["model_usage"]["answer"]["counters"]["total_tokens"]["reported_sum"], 52)
            self.assertEqual(summary["model_usage"]["judge"]["calls"], 1)
            self.assertEqual(summary["model_usage"]["judge"]["unreported_calls"], 1)
            self.assertEqual(summary["ingest_seconds"], 0.25)
            self.assertEqual(summary["ingest_llm_calls"]["reported_sum"], 2)
            second, endpoint = FakeAdapter(), Endpoint()
            with patch("h2h.adapters.build", return_value=second), patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", endpoint), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(argv), 0)
            self.assertEqual(second.calls, [])
            self.assertEqual(len(endpoint.requests), 1)
            self.assertEqual(endpoint.requests[0]["model"], "judge")
            record = json.loads((out / "records.jsonl").read_text())
            self.assertEqual([call["outcome"] for call in record["model_calls"]], ["success", "error", "success"])
            self.assertIsNone(record["model_calls"][1]["usage"])

    def test_scored_pending_and_torn_append_resume_without_any_model_or_system_call(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = self._argv(directory) + ["--limit", "1"]
            original_open = Path.open
            def fail_append(path, mode="r", *args, **kwargs):
                if path.name == "records.jsonl" and mode == "a":
                    raise OSError("simulated killed records append")
                return original_open(path, mode, *args, **kwargs)
            with patch("h2h.adapters.build", return_value=FakeAdapter()), patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", Endpoint()), patch.object(Path, "open", fail_append), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(OSError):
                    main(argv)
            out = Path(directory) / "out" / "fake"
            pending = json.loads((out / "pending.json").read_text())
            self.assertEqual(next(iter(pending.values()))["status"], "complete")
            (out / "records.jsonl").write_text('{"question_id":', encoding="utf-8")
            adapter = FakeAdapter()
            with patch("h2h.adapters.build", return_value=adapter), patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", side_effect=AssertionError("paid call repeated")), patch.object(adapter, "start", side_effect=AssertionError("system restarted")), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(argv), 0)
            self.assertEqual(adapter.calls, [])
            record = json.loads((out / "records.jsonl").read_text())
            self.assertEqual(len(record["model_calls"]), 2)
            self.assertEqual(record["usage"]["judge"]["total_tokens"], 41)
            self.assertTrue((out / "records.partial").exists())

    def test_failed_answer_attempt_is_preserved_when_resume_reingests(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = self._argv(directory) + ["--limit", "1"]
            def malformed(request, timeout):
                result = json.load(Endpoint()(request, timeout))
                result["choices"] = []
                return io.BytesIO(json.dumps(result).encode())
            with patch("h2h.adapters.build", return_value=FakeAdapter()), patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", malformed), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):
                    main(argv)
            adapter, endpoint = FakeAdapter(), Endpoint()
            with patch("h2h.adapters.build", return_value=adapter), patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", endpoint), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(argv), 0)
            out = Path(directory) / "out" / "fake"
            record = json.loads((out / "records.jsonl").read_text())
            self.assertEqual([call["outcome"] for call in record["model_calls"]], ["error", "success", "success"])
            self.assertEqual(record["model_calls"][0]["usage"]["total_tokens"], 52)
            summary = json.loads((out / "summary.json").read_text())
            self.assertEqual(summary["model_usage"]["answer"]["counters"]["total_tokens"]["reported_sum"], 104)
            self.assertEqual(summary["ingest_llm_calls"]["reported_sum"], 4)

    def test_limit_zero_never_starts_an_adapter_or_calls_a_model(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = self._argv(directory) + ["--limit", "0"]
            adapter = FakeAdapter()
            with patch("h2h.adapters.build", return_value=adapter), patch("h2h.protocol.urlopen", side_effect=AssertionError("unexpected model call")), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(argv), 0)
            self.assertEqual(adapter.calls, [])
            summary = json.loads((Path(directory) / "out" / "fake" / "summary.json").read_text())
            self.assertEqual(summary["completed"], 0)
            self.assertIsNone(summary["accuracy"]["accuracy"])

    def test_summary_never_infers_unreported_provenance_from_another_question(self):
        with patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", Endpoint()):
            one = score_record(run_question(FakeAdapter(), questions()[0], 1, ROUTE, 4096), questions()[0], JUDGE)
        two = {**one, "question_id": "different", "retrieved": [{"text": "unreported", "session_ids": []}], "session_ids_reported": None}
        summary = summarize([one, two], {"question_ids": [one["question_id"], "different"], "k": 1})
        self.assertEqual(summary["recall_at_k"]["eligible_questions"], 1)
        self.assertEqual(summary["recall_at_k"]["mean"], 1.0)

    def test_resume_refuses_changed_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = self._argv(directory)
            with patch("h2h.adapters.build", return_value=FakeAdapter()), patch.dict(os.environ, {}, clear=True), patch("h2h.protocol.urlopen", Endpoint()), contextlib.redirect_stdout(io.StringIO()):
                main(argv + ["--limit", "1"])
                with self.assertRaises(ValueError):
                    main(argv + ["--k", "2"])

    def test_torn_records_tail_is_preserved_and_recovered(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            record = {"question_id": "done", "status": "complete", "autoeval_label": {"label": True}}
            tail = b'{"question_id": "partial'
            path.write_bytes(json.dumps(record).encode() + b"\n" + tail)
            self.assertEqual(_read_records(path), [record])
            self.assertEqual(path.with_name("records.partial").read_bytes(), tail)
            self.assertTrue(path.read_bytes().endswith(b"\n"))

    def test_list_arms_does_not_import_or_construct_system_modules(self):
        from h2h import adapters
        output = io.StringIO()
        with patch.object(adapters.importlib, "import_module", side_effect=AssertionError("unexpected import")), contextlib.redirect_stdout(output):
            self.assertEqual(main(["--list-arms"]), 0)
        self.assertIn("bm25", output.getvalue().splitlines())
        self.assertIn("none", output.getvalue().splitlines())


if __name__ == "__main__":
    unittest.main()
