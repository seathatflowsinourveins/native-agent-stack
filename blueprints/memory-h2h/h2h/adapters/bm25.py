"""Session BM25 control, a stdlib port of rank-bm25 0.2.2 scoring.

rank_bm25.py L78-L134 at 2550648efdbdcc5ebadbc8e5c8b26f5eb94b2b36:
k1=1.5, b=0.75, epsilon=0.25 and the negative-IDF floor are unchanged.
Lowercase whitespace tokens follow vectorize-io/agent-memory-benchmark
@f618ed7b1f0eb9cad7b42e876f91a42f0eadb150 memory/bm25.py L23-L24.
We index entire sessions (both roles), without that reference's chunk splitting.
"""

import math
import time
from collections import Counter
from pathlib import Path

from ..types import IngestStats, MemoryAdapter, ModelRoute, Retrieved, Session


class BM25:
    name = "bm25"
    version = "rank-bm25-0.2.2-scoring"
    needs_llm = False
    reports_session_ids = True

    def __init__(self) -> None:
        self._namespace: str | None = None
        self._sessions: list[Session] = []
        self._frequencies: list[Counter[str]] = []
        self._lengths: list[int] = []
        self._idf: dict[str, float] = {}
        self._avg_length = 0.0

    def start(self, workdir: Path, llm: ModelRoute | None, embed: ModelRoute | None) -> None:
        self.stop()

    def reset(self, namespace: str) -> None:
        self.stop()
        self._namespace = namespace

    def _check_namespace(self, namespace: str) -> None:
        if self._namespace != namespace:
            raise ValueError("BM25 namespace has not been reset for this question")

    def ingest(self, namespace: str, sessions: list[Session]) -> IngestStats:
        self._check_namespace(namespace)
        started = time.perf_counter()
        self._sessions = list(sessions)
        tokens = [" ".join(t.content for t in s.turns).lower().split() for s in sessions]
        self._frequencies = [Counter(words) for words in tokens]
        self._lengths = [len(words) for words in tokens]
        self._avg_length = sum(self._lengths) / len(tokens) if tokens else 0.0
        document_frequencies: Counter[str] = Counter()
        for frequencies in self._frequencies:
            document_frequencies.update(frequencies.keys())
        count = len(sessions)
        self._idf = {
            term: math.log(count - frequency + 0.5) - math.log(frequency + 0.5)
            for term, frequency in document_frequencies.items()
        }
        average_idf = sum(self._idf.values()) / len(self._idf) if self._idf else 0.0
        for term, value in self._idf.items():
            if value < 0:
                self._idf[term] = 0.25 * average_idf
        return IngestStats(len(sessions), time.perf_counter() - started, 0)

    def retrieve(self, namespace: str, query: str, k: int, question_date: str | None) -> list[Retrieved]:
        self._check_namespace(namespace)
        if k < 0:
            raise ValueError("k must be nonnegative")
        scores = []
        for frequencies, length in zip(self._frequencies, self._lengths, strict=True):
            score = 0.0
            if self._avg_length:
                for term in query.lower().split():
                    frequency = frequencies.get(term, 0)
                    if frequency:
                        score += self._idf.get(term, 0.0) * (frequency * 2.5) / (
                            frequency + 1.5 * (0.25 + 0.75 * length / self._avg_length)
                        )
            scores.append(score)
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))[:k]
        results = []
        for index in order:
            session = self._sessions[index]
            text = f"Session Date: {session.date}\nSession Content:\n" + "\n\n".join(
                f"{turn.role}: {turn.content}" for turn in session.turns
            )
            results.append(Retrieved(text, (session.session_id,), scores[index]))
        return results

    def stop(self) -> None:
        self._namespace = None
        self._sessions.clear()
        self._frequencies.clear()
        self._lengths.clear()
        self._idf.clear()
        self._avg_length = 0.0


def build() -> MemoryAdapter:
    return BM25()
