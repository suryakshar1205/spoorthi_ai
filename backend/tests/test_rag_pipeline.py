from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.config import Settings
from app.models.schemas import UserQuery
from app.services.embeddings import EmbeddingService
from app.services.llm_service import LLMService
from app.services.memory import MemoryService
from app.services.rag_service import RAGService
from app.services.reranker import RerankerService
from app.services.retriever import RetrieverService
from app.services.search_service import SearchService
from app.services.vector_service import VectorService
from app.utils.text import build_chunk_records, token_count


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
    art_room_coord = await rag_service.answer_query("art room coord", session_id="test-session")
    tech_room_coord = await rag_service.answer_query("tech room cord", session_id="test-session")
    tech_room_details = await rag_service.answer_query("tech room", session_id="test-session")
    spaced_tech_room = await rag_service.answer_query("   tech   room   ", session_id="test-session")
    bare_events = await rag_service.answer_query("events", session_id="test-session")
    list_all_the_events = await rag_service.answer_query("List all the events", session_id="test-session")
    broad_events = await rag_service.answer_query("What events are happening?", session_id="test-session")
    broad_events_typo = await rag_service.answer_query("Waht evnts are heppening in fest?", session_id="test-session")
    workshops = await rag_service.answer_query("Tell me about the workshops", session_id="test-session")
    overview = await rag_service.answer_query("What is Spoorthi?", session_id="test-session")
    sponsors = await rag_service.answer_query("Who are the sponsors?", session_id="test-session")
    finance_team = await rag_service.answer_query("Who is in the finance team?", session_id="test-session")
    hod = await rag_service.answer_query("Who is the HOD?", session_id="test-session")
    unknown = await rag_service.answer_query("What is the hostel bus route for visitors?", session_id="test-session")

    assert "Dr. Anitha Sheela Kancharla" in faculty_coord.answer
    assert "Naveen" in student_coord.answer or "Nikitha" in student_coord.answer
    assert "Art Room Coordinator Details" in art_room_coord.answer
    assert "Veda" in art_room_coord.answer
    assert "Tech Room Coordinator Details" in tech_room_coord.answer
    assert "Surya" in tech_room_coord.answer
    assert "Tech Room Details" in tech_room_details.answer
    assert "technical games" in tech_room_details.answer.lower() or "project demonstrations" in tech_room_details.answer.lower()
    assert "Tech Room Details" in spaced_tech_room.answer
    assert "PCB Workshop" in bare_events.answer or "Hackathon" in bare_events.answer or "Tech Treasure Hunt" in bare_events.answer
    assert "PCB Workshop" in list_all_the_events.answer or "Hackathon" in list_all_the_events.answer or "Tech Treasure Hunt" in list_all_the_events.answer
    assert "PCB Workshop" in broad_events.answer or "Hackathon" in broad_events.answer
    assert "PCB Workshop" in broad_events_typo.answer or "Hackathon" in broad_events_typo.answer
    assert "PCB Workshop" in workshops.answer or "AI & IoT Workshop" in workshops.answer
    assert "Spoorthi" in overview.answer and "JNTUH" in overview.answer
    assert "Sponsors & Support Partners Details" in sponsors.answer
    assert "ICICI Bank" in sponsors.answer or "MathWorks" in sponsors.answer
    assert "Finance Team Details" in finance_team.answer
    assert "Adithya Varma" in finance_team.answer or "Eshwar" in finance_team.answer
    assert "Key Faculty Team Details" in hod.answer or "Here's what I found:" in hod.answer
    assert "Dr. T. Madhavi Kumari" in hod.answer
    assert "Please contact the organizers" in unknown.answer
    assert "Faculty Coordinator: Dr. Anitha Sheela Kancharla" in unknown.answer
    assert "Student Coordinator: Naveen, Nikitha, Aditya Singh, Yashashwini" in unknown.answer


@pytest.mark.asyncio
async def test_retriever_returns_relevant_documents(tmp_path: Path) -> None:
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

    retriever = RetrieverService(settings, vector_service)
    matches = await retriever.retrieve("tech room", top_k=3)

    assert matches
    assert len(matches) <= 3
    assert any("Tech Room" in match.chunk.text for match in matches)


@pytest.mark.asyncio
async def test_fallback_skips_llm_for_unknown_query(tmp_path: Path) -> None:
    class GuardLLMService:
        def __init__(self) -> None:
            self.called = False

        async def generate_response(self, context: str, query: str) -> str:
            self.called = True
            raise AssertionError("LLM should not be called for fallback queries")

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

    guard_llm = GuardLLMService()
    rag_service = RAGService(
        settings=settings,
        retriever=RetrieverService(settings, vector_service),
        reranker=RerankerService(settings),
        search_service=SearchService(settings),
        llm_service=guard_llm,  # type: ignore[arg-type]
        memory_service=MemoryService(max_turns=6),
    )

    unknown = await rag_service.answer_query("What is the hostel bus route for visitors?", session_id="test-session")

    assert guard_llm.called is False
    assert "Please contact the organizers" in unknown.answer
    assert "Faculty Coordinator: Dr. Anitha Sheela Kancharla" in unknown.answer


@pytest.mark.asyncio
async def test_rag_debug_mode_emits_request_trace(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(
        use_internet_fallback=False,
        rag_debug_mode=True,
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

    with caplog.at_level(logging.INFO):
        await rag_service.answer_query("tech room", session_id="debug-session")

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "RAG DEBUG request_start" in messages
    assert "RAG DEBUG input raw_query=" in messages
    assert "RAG DEBUG final_prompt" in messages
    assert "RAG DEBUG llm_output" in messages
    assert "RAG DEBUG request_complete" in messages


@pytest.mark.asyncio
async def test_pipeline_state_tracks_stage_outputs(tmp_path: Path) -> None:
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

    state = await rag_service._run_pipeline(query="tech room", session_key="pipeline-session", stream=False)

    assert state.raw_query == "tech room"
    assert state.prepared_query == "tech room"
    assert state.retrieval_query == "tech room"
    assert state.source == "document"
    assert state.context != "NO_CONTEXT_FOUND"
    assert state.matches
    assert state.direct_answer is None
    assert state.should_fallback is False


@pytest.mark.asyncio
async def test_step9_required_validation_queries(tmp_path: Path) -> None:
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

    fest_answer = await rag_service.answer_query("What is Spoorthi Fest?", session_id="validation-session")
    coordinator_answer = await rag_service.answer_query("Who is the coordinator?", session_id="validation-session")
    events_answer = await rag_service.answer_query("List events", session_id="validation-session")

    assert "Spoorthi" in fest_answer.answer
    assert "JNTUH" in fest_answer.answer
    assert "ECE" in fest_answer.answer
    assert "Faculty Coordinator" in coordinator_answer.answer
    assert "Dr. Anitha Sheela Kancharla" in coordinator_answer.answer
    assert "Student Coordinator" in coordinator_answer.answer
    assert "Naveen" in coordinator_answer.answer or "Nikitha" in coordinator_answer.answer
    assert events_answer.source == "document"
    assert (
        "PCB Workshop" in events_answer.answer
        or "Hackathon" in events_answer.answer
        or "Tech Treasure Hunt" in events_answer.answer
    )


def test_semantic_chunking_preserves_meaningful_sections() -> None:
    sample_path = Path(__file__).resolve().parents[1] / "sample_data" / "spoorthi_context.txt"
    sample_text = sample_path.read_text(encoding="utf-8")

    chunks = build_chunk_records(
        document_id="chunk-test",
        file_name=sample_path.name,
        source_type="document",
        text=sample_text,
        chunk_size=320,
        overlap=0,
        metadata={"seeded": "true"},
    )

    assert chunks
    assert all(token_count(chunk.text) <= 400 for chunk in chunks)
    assert any(180 <= token_count(chunk.text) <= 400 for chunk in chunks)
    assert any("Faculty Coordinator" in chunk.text for chunk in chunks)
    assert any("Tech Room" in chunk.text for chunk in chunks)
    assert not any("Faculty Coordinator" in chunk.text and "Tech Room" in chunk.text for chunk in chunks)


def test_strict_prompt_uses_context_and_question() -> None:
    settings = Settings()
    llm_service = LLMService(settings)

    prompt = llm_service.build_prompt(
        context="Tech Room\nPurpose: Technical games and project demonstrations",
        question="What is Tech Room?",
    )

    assert "You are Spoorthi Chatbot, an assistant for a technical fest." in prompt
    assert "Context:\nTech Room\nPurpose: Technical games and project demonstrations" in prompt
    assert "Question:\nWhat is Tech Room?" in prompt
    assert "I don’t have that information. Please contact the organizers." in prompt

def test_user_query_schema_normalizes_whitespace() -> None:
    payload = UserQuery(query="   tech   room   ", session_id="   session-1234   ")

    assert payload.query == "tech room"
    assert payload.session_id == "session-1234"
