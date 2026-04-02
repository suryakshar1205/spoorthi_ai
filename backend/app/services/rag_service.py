from __future__ import annotations

import logging
import re
from uuid import uuid4

from app.config import Settings
from app.models.domain import KnowledgeSource, SearchMatch
from app.models.schemas import AskResponse
from app.services.chatbot_logic import route_predefined_query
from app.services.llm_service import FALLBACK_ANSWER, LLMService
from app.services.memory import MemoryService
from app.services.reranker import RerankerService
from app.services.retriever import RetrieverService
from app.services.search_service import SearchService


logger = logging.getLogger(__name__)


class RAGService:
    def __init__(
        self,
        settings: Settings,
        retriever: RetrieverService,
        reranker: RerankerService,
        search_service: SearchService,
        llm_service: LLMService,
        memory_service: MemoryService,
    ) -> None:
        self.settings = settings
        self.retriever = retriever
        self.reranker = reranker
        self.search_service = search_service
        self.llm_service = llm_service
        self.memory_service = memory_service

    async def answer_query(self, query: str, session_id: str | None = None) -> AskResponse:
        session_key = session_id or str(uuid4())
        direct_answer = route_predefined_query(query)
        if direct_answer:
            self.memory_service.append_turn(session_key, "user", query)
            self.memory_service.append_turn(session_key, "assistant", direct_answer)
            self._log_answer(query, KnowledgeSource.DOCUMENT.value, [], direct_answer)
            return AskResponse(
                answer=direct_answer,
                source=KnowledgeSource.DOCUMENT.value,
                confidence=1.0,
                session_id=session_key,
            )

        retrieval_query = self._build_retrieval_query(session_key, query)
        context, source, confidence, selected = await self.retrieve_context(retrieval_query, session_key)
        answer = await self.llm_service.generate_response(context=context, query=query)

        self.memory_service.append_turn(session_key, "user", query)
        self.memory_service.append_turn(session_key, "assistant", answer)
        self._log_answer(query, source, selected, answer)

        return AskResponse(answer=answer, source=source, confidence=confidence, session_id=session_key)

    async def retrieve_context(
        self,
        query: str,
        session_id: str | None = None,
    ) -> tuple[str, str, float, list[SearchMatch]]:
        retrieved = await self.retriever.retrieve(query, top_k=max(5, self.settings.top_k))
        selected = self.reranker.rerank(query, retrieved, top_n=self.settings.rerank_top_n)
        best_score = selected[0].rerank_score if selected else 0.0

        if selected and best_score >= self.settings.similarity_threshold:
            memory_context = self.memory_service.format_context(session_id or "", limit=self.settings.memory_turn_window)
            context = self._build_document_context(selected, memory_context)
            return context, KnowledgeSource.DOCUMENT.value, min(1.0, best_score), selected

        if self.settings.use_internet_fallback:
            internet_context = await self.search_service.search_context(query)
            if internet_context != "NO_CONTEXT_FOUND":
                memory_context = self.memory_service.format_context(session_id or "", limit=self.settings.memory_turn_window)
                context = self._build_internet_context(internet_context, memory_context)
                return context, KnowledgeSource.INTERNET.value, 0.35, []

        return "NO_CONTEXT_FOUND", KnowledgeSource.FALLBACK.value, 0.0, []

    async def stream_answer(self, query: str, session_id: str | None = None):
        session_key = session_id or str(uuid4())
        direct_answer = route_predefined_query(query)
        if direct_answer:
            yield {"type": "status", "message": "Spoorthi Chatbot is typing..."}
            yield {"type": "meta", "session_id": session_key}
            for token in re.findall(r"\S+\s*", direct_answer):
                yield {"type": "token", "content": token}
            self.memory_service.append_turn(session_key, "user", query)
            self.memory_service.append_turn(session_key, "assistant", direct_answer)
            self._log_answer(query, KnowledgeSource.DOCUMENT.value, [], direct_answer)
            yield {"type": "done"}
            return

        retrieval_query = self._build_retrieval_query(session_key, query)

        try:
            yield {"type": "status", "message": "Spoorthi Chatbot is typing..."}
            context, source, confidence, selected = await self.retrieve_context(retrieval_query, session_key)
            yield {"type": "meta", "source": source, "confidence": confidence, "session_id": session_key}

            answer_parts: list[str] = []
            async for token in self.llm_service.stream_response(context=context, query=query):
                answer_parts.append(token)
                yield {"type": "token", "content": token}

            answer = "".join(answer_parts).strip() or FALLBACK_ANSWER
            self.memory_service.append_turn(session_key, "user", query)
            self.memory_service.append_turn(session_key, "assistant", answer)
            self._log_answer(query, source, selected, answer)
            yield {"type": "done"}
        except Exception as exc:
            logger.exception("Streaming answer failed for query=%r", query)
            yield {"type": "error", "message": str(exc)}
            yield {"type": "done"}

    def _build_retrieval_query(self, session_id: str, query: str) -> str:
        lowered = query.lower().strip()
        referential = {"it", "they", "them", "that", "those", "there", "then", "this", "these", "one", "ones"}
        if len(lowered.split()) > 6 and not any(token in referential for token in lowered.split()):
            return query

        recent_turns = [turn for turn in self.memory_service.recent_turns(session_id, limit=4) if turn.role == "user"]
        if not recent_turns:
            return query

        previous_query = recent_turns[-1].content
        return f"{previous_query}\nFollow-up question: {query}"

    def _build_document_context(self, matches: list[SearchMatch], memory_context: str) -> str:
        sections: list[str] = []
        if memory_context:
            sections.append(memory_context)

        lines = ["Retrieved context:"]
        for index, item in enumerate(matches, start=1):
            lines.append(f"[{index}] Source: {item.chunk.file_name}")
            lines.append(f"Section: {item.chunk.metadata.get('section', 'general')}")
            lines.append(f"Content: {item.chunk.text}")
            lines.append("")
        sections.append("\n".join(lines).strip())
        return "\n\n".join(section for section in sections if section.strip())

    def _build_internet_context(self, internet_context: str, memory_context: str) -> str:
        sections: list[str] = []
        if memory_context:
            sections.append(memory_context)
        sections.append(f"Retrieved context:\n[1] Source: internet\nSection: web\nContent: {internet_context}")
        return "\n\n".join(sections)

    def _log_answer(self, query: str, source: str, matches: list[SearchMatch], answer: str) -> None:
        logger.info(
            "RAG answer generated query=%r source=%s selected=%s answer_preview=%r",
            query,
            source,
            [f"{match.chunk.file_name}:{match.chunk.metadata.get('section', 'general')}:{match.rerank_score or match.score:.2f}" for match in matches],
            answer[:220],
        )
