from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class KnowledgeSource(str, Enum):
    DOCUMENT = "document"
    INTERNET = "internet"
    MANUAL = "manual"
    FALLBACK = "fallback"


@dataclass(slots=True)
class ChunkRecord:
    id: str
    document_id: str
    file_name: str
    source_type: str
    text: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ChunkRecord":
        return cls(
            id=payload["id"],
            document_id=payload["document_id"],
            file_name=payload["file_name"],
            source_type=payload["source_type"],
            text=payload["text"],
            created_at=payload["created_at"],
            metadata=payload.get("metadata", {}),
        )


@dataclass(slots=True)
class SearchMatch:
    chunk: ChunkRecord
    score: float
    semantic_score: float = 0.0
    lexical_score: float = 0.0
    rerank_score: float = 0.0
    quality_score: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PipelineState:
    session_id: str
    raw_query: str
    prepared_query: str
    retrieval_query: str
    context: str
    source: str
    confidence: float
    matches: list[SearchMatch] = field(default_factory=list)
    direct_answer: str | None = None

    @property
    def should_fallback(self) -> bool:
        return self.context == "NO_CONTEXT_FOUND" and self.direct_answer is None
