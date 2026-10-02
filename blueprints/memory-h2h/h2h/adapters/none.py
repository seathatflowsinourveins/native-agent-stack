"""No-context control. It holds no memory and requires no service or model."""

from pathlib import Path

from ..types import IngestStats, MemoryAdapter, ModelRoute, Retrieved, Session


class NoMemory:
    name = "none"
    version = "harness-control-v1"
    needs_llm = False
    reports_session_ids = False

    def start(self, workdir: Path, llm: ModelRoute | None, embed: ModelRoute | None) -> None:
        pass

    def reset(self, namespace: str) -> None:
        pass

    def ingest(self, namespace: str, sessions: list[Session]) -> IngestStats:
        return IngestStats(sessions=len(sessions), llm_calls=0)

    def retrieve(self, namespace: str, query: str, k: int, question_date: str | None) -> list[Retrieved]:
        if k < 0:
            raise ValueError("k must be nonnegative")
        return []

    def stop(self) -> None:
        pass


def build() -> MemoryAdapter:
    return NoMemory()
