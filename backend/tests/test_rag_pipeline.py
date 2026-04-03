from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.services.embeddings import EmbeddingService
from app.services.llm_service import LLMService
from app.services.memory import MemoryService
from app.services.rag_service import RAGService
from app.services.reranker import RerankerService
from app.services.retriever import RetrieverService
from app.services.search_service import SearchService
from app.services.vector_service import VectorService
from app.utils.text import build_chunk_records


@pytest.mark.asyncio
async def test_rag_pipeline_validation_queries(tmp_path: Path) -> None:
    settings = Settings(
        llm_provider="local",
        local_fallback_enabled=True,
        use_internet_fallback=False,
        knowledge_dir=tmp_path / "data",
        upload_dir=tmp_path / "data" / "uploads",
        faiss_index_path=tmp_path / "data" / "knowledge.index",
        metadata_path=tmp_path / "data" / "knowledge.json",
    )
    settings.ensure_directories()

    sample_path = Path(__file__).resolve().parents[1] / "sample_data" / "spoorthi_context.txt"
    sample_text = sample_path.read_text(encoding="utf-8")
    chunks = build_chunk_records(
        document_id="test-doc",
        file_name=sample_path.name,
        source_type="document",
        text=sample_text,
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap,
        metadata={"seeded": "true"},
    )

    embedding_service = EmbeddingService(settings)
    vector_service = VectorService(settings, embedding_service=embedding_service)
    await vector_service.initialize()
    await vector_service.add_chunks(chunks)

    rag_service = RAGService(
        settings=settings,
        retriever=RetrieverService(settings, vector_service),
        reranker=RerankerService(settings),
        search_service=SearchService(settings),
        llm_service=LLMService(settings),
        memory_service=MemoryService(max_turns=6),
    )

    hackathon = await rag_service.answer_query("Where is the hackathon?", session_id="test-session")
    rules = await rag_service.answer_query("What are the rules for coding contest?", session_id="test-session")
    beginners = await rag_service.answer_query("Suggest some events for beginners", session_id="test-session")
    workshops = await rag_service.answer_query("What is the timing of workshops?", session_id="test-session")

    assert "Block A Lab 3" in hackathon.answer
    assert rules.answer
    assert "beginner-friendly" in beginners.answer.lower() or "here are a few" in beginners.answer.lower()
    assert "11:00 AM" in workshops.answer or "AI Workshop" in workshops.answer
