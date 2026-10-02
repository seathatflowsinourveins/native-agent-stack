"""Local cleaned-S loader; gold evidence never reaches the memory adapter.

Schema: LongMemEval@9e0b455f4ef0e2ab8f2e582289761153549043fc,
README.md L79-L88. Dates: data/custom_history/sample_haystack_and_timestamp.py L88.
"""

import hashlib
import json
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .types import Session, Turn


@dataclass(frozen=True)
class Question:
    question_id: str
    question_type: str
    question: str
    answer: str
    question_date: str | None
    sessions: tuple[Session, ...]
    answer_session_ids: tuple[str, ...]


def file_sha256(path: str | Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def parse_date(value: str) -> datetime:
    """Parse for ordering only; retain the original timestamp in Session.date."""
    cleaned = re.sub(r"\s*\([^)]*\)", "", value).strip()
    for fmt in ("%Y/%m/%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Unrecognized LongMemEval timestamp: {value!r}") from exc
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def load_questions(path: str | Path, expected_sha256: str | None = None) -> list[Question]:
    """Read the caller's JSON file; never download a dataset.

    Supply pins.json's expected_sha256 to verify the official release. Omitting
    it also permits local synthetic fixtures. The runner records the input hash.
    """
    if expected_sha256 is not None and file_sha256(path) != expected_sha256:
        raise ValueError("Dataset SHA256 does not match the expected pinned release")
    with Path(path).open(encoding="utf-8") as stream:
        raw = json.load(stream)
    if not isinstance(raw, list):
        raise ValueError("LongMemEval data must be a JSON array")
    questions = []
    seen_ids = set()
    for item in raw:
        qid = item["question_id"]
        if not isinstance(qid, str) or not qid or qid in seen_ids:
            raise ValueError(f"Invalid or duplicate question_id: {qid!r}")
        seen_ids.add(qid)
        ids, dates, histories = (
            item["haystack_session_ids"], item["haystack_dates"], item["haystack_sessions"]
        )
        if not (len(ids) == len(dates) == len(histories)):
            raise ValueError(f"Misaligned session ids, dates and histories for {qid}")
        if len(set(ids)) != len(ids):
            raise ValueError(f"Duplicate session ids for {qid}")
        sessions = []
        for sid, date, history in zip(ids, dates, histories, strict=True):
            if not isinstance(sid, str) or not isinstance(date, str):
                raise ValueError(f"Session id and date must be strings for {qid}")
            parse_date(date)
            turns = []
            for turn in history:
                if turn["role"] not in ("user", "assistant") or not isinstance(turn["content"], str):
                    raise ValueError(f"Invalid conversation turn for {qid}/{sid}")
                # Deliberately discard has_answer and all other gold annotations.
                turns.append(Turn(turn["role"], turn["content"]))
            sessions.append(Session(sid, date, tuple(turns)))
        if not isinstance(item["question"], str) or not isinstance(item["question_type"], str):
            raise ValueError(f"Question and question_type must be strings for {qid}")
        qdate = item.get("question_date")
        if qdate is not None and not isinstance(qdate, str):
            raise ValueError(f"question_date must be a string or null for {qid}")
        gold_ids = item["answer_session_ids"]
        if not isinstance(gold_ids, list) or any(not isinstance(sid, str) for sid in gold_ids):
            raise ValueError(f"answer_session_ids must be a list of strings for {qid}")
        questions.append(Question(
            qid, item["question_type"], item["question"], str(item["answer"]),
            qdate, tuple(sessions), tuple(gold_ids),
        ))
    return questions


def stratified_subset(questions: list[Question], n: int, seed: int) -> list[Question]:
    """Equal allocation by question_type, independent of input order.

    Reject a non-divisible n or an undersized stratum instead of silently changing
    the allocation. Interleave sorted strata, so prefixes also stay balanced.
    """
    if n < 0:
        raise ValueError("n must be nonnegative")
    if len({q.question_id for q in questions}) != len(questions):
        raise ValueError("Question ids must be unique")
    groups: dict[str, list[Question]] = defaultdict(list)
    for question in questions:
        groups[question.question_type].append(question)
    if n == 0:
        return []
    if not groups or n % len(groups):
        raise ValueError("n must be a multiple of the number of question types")
    per_type = n // len(groups)
    rng = random.Random(seed)
    selected = []
    for qtype in sorted(groups):
        candidates = sorted(groups[qtype], key=lambda q: q.question_id)
        if len(candidates) < per_type:
            raise ValueError(f"Question type {qtype!r} has fewer than {per_type} questions")
        selected.append(rng.sample(candidates, per_type))
    return [group[i] for i in range(per_type) for group in selected]
