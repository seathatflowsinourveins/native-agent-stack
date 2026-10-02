from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Turn:
    role: str            # "user" or "assistant"
    content: str


@dataclass(frozen=True)
class Session:
    session_id: str
    date: str            # the dataset's session date string, unchanged
    turns: tuple[Turn, ...]


@dataclass(frozen=True)
class Retrieved:
    text: str
    session_ids: tuple[str, ...] = ()   # source sessions when the system reports them, else empty
    score: float | None = None


@dataclass(frozen=True)
class ModelRoute:
    base_url: str        # OpenAI-compatible, for example http://127.0.0.1:20128/v1
    model: str
    api_key_env: str = "H2H_API_KEY"   # name of the environment variable that holds the key; never the key itself


@dataclass
class IngestStats:
    sessions: int = 0
    seconds: float = 0.0
    llm_calls: int | None = None        # None when the system does not report it
    notes: list[str] = field(default_factory=list)


class MemoryAdapter(Protocol):
    name: str
    version: str                         # the pinned upstream release this adapter targets
    needs_llm: bool                      # True when ingestion or recall calls an LLM
    def start(self, workdir: Path, llm: ModelRoute | None, embed: ModelRoute | None) -> None: ...
    def reset(self, namespace: str) -> None: ...
    def ingest(self, namespace: str, sessions: list[Session]) -> IngestStats: ...
    def retrieve(self, namespace: str, query: str, k: int, question_date: str | None) -> list[Retrieved]: ...
    def stop(self) -> None: ...
