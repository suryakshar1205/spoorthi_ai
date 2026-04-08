from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import defaultdict

import faiss
import numpy as np

from app.config import Settings
from app.models.domain import ChunkRecord, SearchMatch
from app.services.embeddings import EmbeddingService
from app.utils.text import infer_chunk_metadata, normalize_source_text


logger = logging.getLogger(__name__)


class VectorService:
    def __init__(self, settings: Settings, embedding_service: EmbeddingService | None = None) -> None:
        self.settings = settings
        self.embedding_service = embedding_service or EmbeddingService(settings)
        self.dimension = settings.embedding_dimension
        self._lock = asyncio.Lock()
        self.index = faiss.IndexFlatIP(self.dimension)
        self.records: list[ChunkRecord] = []
        self._records_dirty = False

    async def initialize(self) -> None:
        self.settings.ensure_directories()
        self.records = []
        self.index = faiss.IndexFlatIP(self.dimension)
        self._records_dirty = False

        if not self.settings.persist_runtime_knowledge:
            return

        self.records = self._load_records()
        if self.settings.faiss_index_path.exists():
            self.index = faiss.read_index(str(self.settings.faiss_index_path))

        if self.index.ntotal != len(self.records) or self._records_dirty:
            await self.rebuild_index()

    async def add_chunks(self, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            return
        async with self._lock:
            vectors = np.vstack([self.embedding_service.embed_text(chunk.text) for chunk in chunks])
            self.index.add(vectors)
            self.records.extend(chunks)
            self._persist()

    async def semantic_search(self, query: str, top_k: int) -> list[SearchMatch]:
        async with self._lock:
            if not self.records or self.index.ntotal == 0:
                if self.settings.rag_debug_mode:
                    logger.info("RAG DEBUG semantic_search query=%r records=0", query)
                return []

            limit = min(max(top_k, 1), len(self.records))
            vector = self.embedding_service.embed_text(query).reshape(1, -1)
            scores, positions = self.index.search(vector, limit)
            records_snapshot = list(self.records)

        matches: list[SearchMatch] = []
        for raw_score, position in zip(scores[0], positions[0], strict=False):
            if position < 0 or position >= len(records_snapshot):
                continue
            semantic_score = max(0.0, min(1.0, (float(raw_score) + 1.0) / 2.0))
            matches.append(
                SearchMatch(
                    chunk=records_snapshot[position],
                    score=semantic_score,
                    semantic_score=semantic_score,
                    quality_score=1.0,
                )
            )

        if self.settings.rag_debug_mode:
            logger.info(
                "RAG DEBUG semantic_search query=%r top_k=%s total_records=%s candidates=%s",
                query,
                limit,
                len(records_snapshot),
                [
                    {
                        "file": match.chunk.file_name,
                        "section": match.chunk.metadata.get("section", "general"),
                        "semantic_score": round(match.semantic_score, 4),
                        "preview": self._preview_text(match.chunk.text),
                    }
                    for match in matches[: min(5, len(matches))]
                ],
            )

        return matches

    async def search(self, query: str, top_k: int | None = None) -> list[SearchMatch]:
        return await self.semantic_search(query, top_k or self.settings.top_k)

    async def delete_document(self, document_id: str) -> int:
        async with self._lock:
            remaining = [record for record in self.records if record.document_id != document_id]
            deleted = len(self.records) - len(remaining)
            self.records = remaining
            await self._rebuild_locked()
            return deleted

    async def rebuild_index(self) -> int:
        async with self._lock:
            return await self._rebuild_locked()

    async def _rebuild_locked(self) -> int:
        self.index = faiss.IndexFlatIP(self.dimension)
        if self.records:
            vectors = np.vstack([self.embedding_service.embed_text(record.text) for record in self.records])
            self.index.add(vectors)
        self._persist()
        self._records_dirty = False
        return self.index.ntotal

    def list_documents(self) -> list[dict[str, str | int]]:
        grouped: dict[str, dict[str, str | int]] = defaultdict(dict)
        for record in self.records:
            current = grouped.setdefault(
                record.document_id,
                {
                    "document_id": record.document_id,
                    "file_name": record.file_name,
                    "source_type": record.source_type,
                    "created_at": record.created_at,
                    "chunk_count": 0,
                },
            )
            current["chunk_count"] = int(current.get("chunk_count", 0)) + 1
        return sorted(grouped.values(), key=lambda item: str(item["created_at"]), reverse=True)

    def get_document_chunks(self, document_id: str) -> list[ChunkRecord]:
        return [record for record in self.records if record.document_id == document_id]

    def _persist(self) -> None:
        if not self.settings.persist_runtime_knowledge:
            return
        self.settings.ensure_directories()
        faiss.write_index(self.index, str(self.settings.faiss_index_path))
        payload = [record.to_dict() for record in self.records]
        self.settings.metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_records(self) -> list[ChunkRecord]:
        if not self.settings.persist_runtime_knowledge:
            return []
        if not self.settings.metadata_path.exists():
            return []

        payload = json.loads(self.settings.metadata_path.read_text(encoding="utf-8"))
        records = [ChunkRecord.from_dict(item) for item in payload]
        normalized_records: list[ChunkRecord] = []

        for record in records:
            cleaned_text = normalize_source_text(record.text)
            merged_metadata = {**infer_chunk_metadata(record.file_name, cleaned_text), **record.metadata}
            if cleaned_text != record.text or merged_metadata != record.metadata:
                self._records_dirty = True
            normalized_records.append(
                ChunkRecord(
                    id=record.id,
                    document_id=record.document_id,
                    file_name=record.file_name,
                    source_type=record.source_type,
                    text=cleaned_text,
                    created_at=record.created_at,
                    metadata=merged_metadata,
                )
            )

        if self._records_dirty:
            logger.info("Normalized persisted knowledge records before rebuilding the index.")
        return normalized_records

    def _preview_text(self, text: str, limit: int = 160) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= limit:
            return compact
        return compact[:limit].rstrip() + "..."
