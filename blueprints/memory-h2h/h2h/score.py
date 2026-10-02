"""Official LongMemEval QA judgment with caller-supplied model routing.

Verbatim prompts: LongMemEval@9e0b455f4ef0e2ab8f2e582289761153549043fc,
src/evaluation/evaluate_qa.py L24-L43. Request, abstention detection and yes
substring parsing: L101-L117. In particular, parsing is intentionally not a
stricter yes/no parser than upstream's `'yes' in eval_response.lower()`.
"""

import time
from typing import Any

from .data import Question
from .protocol import CompletionFailure, chat_completion, model_call
from .types import ModelRoute


def get_anscheck_prompt(task, question, answer, response, abstention=False):
    if not abstention:
        if task in ['single-session-user', 'single-session-assistant', 'multi-session']:
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the information required by the answer, answer no. \n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            prompt = template.format(question, answer, response)
        elif task == 'temporal-reasoning':
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the information required by the answer, answer no. In addition, do not penalize off-by-one errors for the number of days. If the question asks for the number of days/weeks/months, etc., and the model makes off-by-one errors (e.g., predicting 19 days when the answer is 18), the model's response is still correct. \n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            prompt = template.format(question, answer, response)
        elif task == 'knowledge-update':
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response contains some previous information along with an updated answer, the response should be considered as correct as long as the updated answer is the required answer.\n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            prompt = template.format(question, answer, response)
        elif task == 'single-session-preference':
            template = "I will give you a question, a rubric for desired personalized response, and a response from a model. Please answer yes if the response satisfies the desired response. Otherwise, answer no. The model does not need to reflect all the points in the rubric. The response is correct as long as it recalls and utilizes the user's personal information correctly.\n\nQuestion: {}\n\nRubric: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            prompt = template.format(question, answer, response)
        else:
            raise NotImplementedError
    else:
        template = "I will give you an unanswerable question, an explanation, and a response from a model. Please answer yes if the model correctly identifies the question as unanswerable. The model could say that the information is incomplete, or some other information is given but the asked information is not.\n\nQuestion: {}\n\nExplanation: {}\n\nModel Response: {}\n\nDoes the model correctly identify the question as unanswerable? Answer yes or no only."
        prompt = template.format(question, answer, response)
    return prompt


def parse_judgment(response: str) -> bool:
    return 'yes' in response.strip().lower()


def judge_question(question: Question, hypothesis: str, judge_route: ModelRoute) -> dict[str, Any]:
    prompt = get_anscheck_prompt(
        question.question_type, question.question, question.answer, hypothesis,
        abstention='_abs' in question.question_id,
    )
    completion = chat_completion(judge_route, prompt, 10)
    return {
        "autoeval_label": {"model": judge_route.model, "label": parse_judgment(completion.text)},
        "judge_response": completion.text,
        "usage": completion.usage,
        "model_call": model_call("judge", judge_route, completion),
        "seconds": completion.seconds,
    }


def score_record(record: dict[str, Any], question: Question, judge_route: ModelRoute) -> dict[str, Any]:
    """Return a new, completed record and preserve the original answer usage."""
    if record["question_id"] != question.question_id:
        raise ValueError("Record and reference question ids do not match")
    if record.get("protocol_error"):
        raise ValueError(record["protocol_error"])
    started = time.perf_counter()
    try:
        judgment = judge_question(question, record["hypothesis"], judge_route)
    except CompletionFailure as exc:
        result = dict(record)
        attempt = model_call("judge", judge_route, exc.completion)
        attempt.update(outcome="error", error=str(exc))
        result["model_calls"] = [*record["model_calls"], attempt]
        result["usage"] = {**record["usage"], "judge": exc.completion.usage}
        result["seconds"] = record["seconds"] + time.perf_counter() - started
        result["timings"] = {**record["timings"], "judge": exc.completion.seconds}
        exc.record = result
        raise
    result = dict(record)
    result["autoeval_label"] = judgment["autoeval_label"]
    result["judge_response"] = judgment["judge_response"]
    result["usage"] = {**record["usage"], "judge": judgment["usage"]}
    result["model_calls"] = [*record["model_calls"], judgment["model_call"]]
    result["timings"] = {**record["timings"], "judge": judgment["seconds"]}
    result["seconds"] = record["seconds"] + time.perf_counter() - started
    result["status"] = "complete"
    return result


def recall_at_k(record: dict[str, Any], k: int) -> float | None:
    """Gold-session coverage of the first k retrieved items, deduplicating IDs.

    Nonempty results without provenance are unscorable. Mixed provenance gives
    a lower bound using the reported IDs only. Explicit reports_session_ids=True
    lets an adapter report an empty result as zero recall. Abstentions have no
    gold answer location and are skipped, as upstream README.md L206 specifies.
    """
    if k < 0:
        raise ValueError("k must be nonnegative")
    gold = set(record.get("answer_session_ids", ()))
    if not gold or '_abs' in record["question_id"]:
        return None
    items = record.get("retrieved", [])
    if items and not any(item.get("session_ids") for item in items):
        return None
    reports_ids = record.get("session_ids_reported") is True or any(
        item.get("session_ids") for item in items
    )
    if not reports_ids:
        return None
    found = {sid for item in items[:k] for sid in item.get("session_ids", ())}
    return len(found & gold) / len(gold)
