from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.models.domain import KnowledgeSource
from app.services.embeddings import EmbeddingService
from app.services.llm_service import LLMService
from app.services.memory import MemoryService
from app.services.rag_service import RAGService
from app.services.reranker import RerankerService
from app.services.retriever import RetrieverService
from app.services.search_service import SearchService
from app.services.vector_service import VectorService
from app.utils.text import build_chunk_records


class DummyLLMService(LLMService):
    async def generate_response(self, context: str, query: str) -> str:
        return f"answer::{query}::{context[:50]}"


class DummySearchService(SearchService):
    async def search_context(self, query: str) -> str:
        return f"internet::{query}"


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        knowledge_dir=tmp_path,
        upload_dir=tmp_path / "uploads",
        faiss_index_path=tmp_path / "knowledge.index",
        metadata_path=tmp_path / "knowledge.json",
        similarity_threshold=0.45,
        use_internet_fallback=False,
    )


@pytest.mark.asyncio
async def test_document_match_wins_when_similarity_is_high(settings: Settings) -> None:
    vector_service = VectorService(settings, embedding_service=EmbeddingService(settings))
    await vector_service.initialize()

    chunks = build_chunk_records(
        document_id="doc-1",
        file_name="schedule.txt",
        source_type=KnowledgeSource.DOCUMENT.value,
        text="Spoorthi Tech Fest schedule: AI keynote at 10 AM in the main auditorium.",
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap,
    )
    await vector_service.add_chunks(chunks)

    rag_service = RAGService(
        settings=settings,
        retriever=RetrieverService(settings, vector_service),
        reranker=RerankerService(settings),
        search_service=DummySearchService(settings),
        llm_service=DummyLLMService(settings),
        memory_service=MemoryService(max_turns=6),
    )

    response = await rag_service.answer_query("When is the AI keynote?", session_id="core-test")

    assert response.source == KnowledgeSource.DOCUMENT.value
    assert response.confidence >= settings.similarity_threshold


@pytest.mark.asyncio
async def test_internet_fallback_is_used_without_matching_chunks(settings: Settings) -> None:
    settings.use_internet_fallback = True
    vector_service = VectorService(settings, embedding_service=EmbeddingService(settings))
    await vector_service.initialize()

    rag_service = RAGService(
        settings=settings,
        retriever=RetrieverService(settings, vector_service),
        reranker=RerankerService(settings),
        search_service=DummySearchService(settings),
        llm_service=DummyLLMService(settings),
        memory_service=MemoryService(max_turns=6),
    )

    response = await rag_service.answer_query("What is today's weather?", session_id="core-test")

    assert response.source == KnowledgeSource.INTERNET.value
    assert "Source: internet" in response.answer or "internet::" in response.answer
