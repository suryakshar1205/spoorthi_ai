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

    faculty_coord = await rag_service.answer_query("Who is facult co ord?", session_id="test-session")
    student_coord = await rag_service.answer_query("Who are the student co ords?", session_id="test-session")
    broad_events = await rag_service.answer_query("What events are happening?", session_id="test-session")
    workshops = await rag_service.answer_query("Tell me about the workshops", session_id="test-session")
    overview = await rag_service.answer_query("What is Spoorthi?", session_id="test-session")
    unknown = await rag_service.answer_query("What is the hostel bus route for visitors?", session_id="test-session")

    assert "Dr. Anitha Sheela Kancharla" in faculty_coord.answer
    assert "Naveen" in student_coord.answer or "Nikitha" in student_coord.answer
    assert "PCB Workshop" in broad_events.answer or "Hackathon" in broad_events.answer
    assert "PCB Workshop" in workshops.answer or "AI & IoT Workshop" in workshops.answer
    assert "Spoorthi" in overview.answer and "JNTUH" in overview.answer
    assert "Please contact the organizers" in unknown.answer
    assert "Faculty Coordinator" in unknown.answer
