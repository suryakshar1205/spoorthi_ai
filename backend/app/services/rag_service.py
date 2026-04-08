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
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-]{8,}\d)")
CONTACT_KEYWORDS = ("coordinator", "organizer", "contact", "phone", "email", "help desk")
ROLE_CONTACT_RE = re.compile(
    r"\b(?P<role>(?:faculty|student|event|overall|test(?: edition)?)?\s*coordinator)\s*:\s*(?P<name>[A-Za-z][A-Za-z .'\-]{1,60})",
    re.IGNORECASE,
)
HELP_DESK_RE = re.compile(r"\bhelp\s*desk(?:\s*location)?\s*:\s*(?P<value>[^|\n.;]{3,100})", re.IGNORECASE)


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
        answer = await self._augment_fallback_with_contacts(answer, context)

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

            # If no relevant context is found, enrich the fallback with organizer contacts when available.
            if context == "NO_CONTEXT_FOUND":
                answer = await self._augment_fallback_with_contacts(FALLBACK_ANSWER, context)
                for token in re.findall(r"\S+\s*", answer):
                    yield {"type": "token", "content": token}
            else:
                answer_parts: list[str] = []
                async for token in self.llm_service.stream_response(context=context, query=query):
                    answer_parts.append(token)
                    yield {"type": "token", "content": token}

                answer = "".join(answer_parts).strip() or FALLBACK_ANSWER
                answer = await self._augment_fallback_with_contacts(answer, context)

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

    async def _augment_fallback_with_contacts(self, answer: str, context: str) -> str:
        if answer.strip() != FALLBACK_ANSWER:
            return answer

        contact_lines = self._extract_contact_lines(context)
        if not contact_lines:
            contact_lines = await self._lookup_contact_lines()

        if not contact_lines:
            return answer

        prioritized_lines = self._prioritize_contact_lines(contact_lines)

        return (
            f"{FALLBACK_ANSWER}\n\n"
            "You can reach the organizers using these details from the current knowledge base:\n"
            + "\n".join(f"- {line}" for line in prioritized_lines[:4])
        )

    async def _lookup_contact_lines(self) -> list[str]:
        contact_query = "organizer contact coordinator email phone help desk"
        retrieved = await self.retriever.retrieve(contact_query, top_k=max(5, self.settings.top_k))
        selected = self.reranker.rerank(contact_query, retrieved, top_n=self.settings.rerank_top_n)
        if not selected:
            return []

        lines: list[str] = []
        for match in selected:
            lines.extend(self._extract_contact_lines(match.chunk.text))

        deduped: list[str] = []
        seen: set[str] = set()
        for line in lines:
            normalized = line.lower().strip()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(line)
        return deduped

    def _extract_contact_lines(self, text: str) -> list[str]:
        if not text or text == "NO_CONTEXT_FOUND":
            return []

        cleaned_text = re.sub(r"[*_`#]+", "", text)
        cleaned_text = re.sub(r"[ \t]{2,}", " ", cleaned_text)
        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)

        prioritized: list[str] = []

        for match in ROLE_CONTACT_RE.finditer(cleaned_text):
            role = self._normalize_label(match.group("role"))
            name = self._normalize_contact_value(match.group("name"))
            if role and name:
                prioritized.append(f"{role}: {name}")

        for email in EMAIL_RE.findall(cleaned_text):
            normalized_email = email.strip().lower()
            if normalized_email:
                prioritized.append(f"Email: {normalized_email}")

        for phone in PHONE_RE.findall(cleaned_text):
            normalized_phone = self._normalize_phone(phone)
            if normalized_phone:
                prioritized.append(f"Phone: {normalized_phone}")

        for match in HELP_DESK_RE.finditer(cleaned_text):
            help_desk_value = self._normalize_contact_value(match.group("value"))
            if help_desk_value:
                prioritized.append(f"Help Desk: {help_desk_value}")

        # Fallback for simple line-based contact rows while filtering noisy, long narrative lines.
        for raw_line in cleaned_text.splitlines():
            line = raw_line.strip().strip("- ")
            if not line or len(line) > 140:
                continue

            lowered = line.lower()
            has_email = EMAIL_RE.search(line) is not None
            has_phone = PHONE_RE.search(line) is not None
            has_role = "coordinator:" in lowered or "organizer:" in lowered
            has_help_desk = "help desk" in lowered and ":" in lowered
            if not (has_email or has_phone or has_role or has_help_desk):
                continue

            candidate = self._normalize_contact_value(line)
            if candidate:
                prioritized.append(candidate)

        deduped: list[str] = []
        seen: set[str] = set()
        for line in prioritized:
            normalized = re.sub(r"\s+", " ", line.lower()).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(line)

        return deduped

    def _prioritize_contact_lines(self, lines: list[str]) -> list[str]:
        def priority(line: str) -> tuple[int, str]:
            lowered = line.lower().strip()
            if lowered.startswith("faculty coordinator:"):
                return (0, lowered)
            if lowered.startswith("student coordinator:"):
                return (1, lowered)
            if lowered.startswith("student coordinator contact number:"):
                return (2, lowered)
            if lowered.startswith("support phone:") or lowered.startswith("phone:"):
                return (3, lowered)
            if lowered.startswith("official email:") or lowered.startswith("support email:") or lowered.startswith("email:"):
                return (4, lowered)
            if lowered.startswith("official web platforms:"):
                return (5, lowered)
            if lowered.startswith("help desk:"):
                return (6, lowered)
            return (10, lowered)

        ordered = sorted(lines, key=priority)
        deduped: list[str] = []
        seen: set[str] = set()
        for line in ordered:
            normalized = re.sub(r"\s+", " ", line.lower()).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(line)
        return deduped

    def _normalize_label(self, label: str) -> str:
        normalized = self._normalize_contact_value(label)
        if not normalized:
            return ""
        return " ".join(word.capitalize() for word in normalized.split())

    def _normalize_contact_value(self, value: str) -> str:
        value = re.sub(r"\s{2,}", " ", value)
        value = value.strip(" -|:;,.")
        return value.strip()

    def _normalize_phone(self, phone: str) -> str:
        normalized = re.sub(r"\s+", " ", phone).strip()
        normalized = normalized.strip(" -|:;,.")
        return normalized
