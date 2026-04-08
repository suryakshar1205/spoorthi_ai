from __future__ import annotations

import logging
import re
from uuid import uuid4

from app.config import Settings
from app.models.domain import KnowledgeSource, PipelineState, SearchMatch
from app.models.schemas import AskResponse
from app.services.chatbot_logic import route_predefined_query
from app.services.llm_service import FALLBACK_ANSWER, LLMService
from app.services.memory import MemoryService
from app.services.reranker import RerankerService
from app.services.retriever import RetrieverService
from app.services.search_service import SearchService
from app.utils.text import extract_keywords, fuzzy_token_hits, normalize_query_text


logger = logging.getLogger(__name__)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-]{8,}\d)")
CONTACT_KEYWORDS = ("coordinator", "organizer", "contact", "phone", "email", "help desk")
ROLE_CONTACT_RE = re.compile(
    r"\b(?P<role>(?:faculty|student|event|overall|test(?: edition)?)?\s*coordinators?)\s*:\s*(?P<name>[A-Za-z][A-Za-z .,'&()\-]{1,100})",
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
        state = await self._run_pipeline(query=query, session_key=session_key, stream=False)
        answer = await self._resolve_answer(state)

        self.memory_service.append_turn(session_key, "user", state.prepared_query)
        self.memory_service.append_turn(session_key, "assistant", answer)
        self._log_answer(state.prepared_query, state.source, state.matches, answer)
        self._log_request_complete(
            session_key=session_key,
            query=state.prepared_query,
            source=state.source,
            confidence=state.confidence,
            answer=answer,
            stream=False,
        )

        return AskResponse(
            answer=answer,
            source=state.source,
            confidence=state.confidence,
            session_id=session_key,
        )

    async def retrieve_context(
        self,
        query: str,
        session_id: str | None = None,
        focus_query: str | None = None,
    ) -> tuple[str, str, float, list[SearchMatch]]:
        retrieved = await self.retriever.retrieve(query, top_k=max(5, self.settings.top_k))
        effective_query = focus_query or query
        selected = self.reranker.rerank(effective_query, retrieved, top_n=self.settings.rerank_top_n)
        best_score = selected[0].rerank_score if selected else 0.0

        relevance_ok, relevance_debug = self._evaluate_selected_relevance(effective_query, selected)

        if selected and best_score >= self.settings.similarity_threshold and relevance_ok:
            memory_context = self.memory_service.format_context(session_id or "", limit=self.settings.memory_turn_window)
            context = self._build_document_context(selected, memory_context)
            return context, KnowledgeSource.DOCUMENT.value, min(1.0, best_score), selected

        if self.settings.rag_debug_mode:
            logger.info(
                "RAG DEBUG fallback_detection retrieval_query=%r focus_query=%r reason=%s best_score=%.3f debug=%s",
                query,
                effective_query,
                "below-threshold" if selected and best_score < self.settings.similarity_threshold else "low-relevance",
                best_score,
                relevance_debug,
            )

        if self.settings.use_internet_fallback:
            internet_context = await self.search_service.search_context(effective_query)
            if internet_context != "NO_CONTEXT_FOUND":
                memory_context = self.memory_service.format_context(session_id or "", limit=self.settings.memory_turn_window)
                context = self._build_internet_context(internet_context, memory_context)
                return context, KnowledgeSource.INTERNET.value, 0.35, []

        return "NO_CONTEXT_FOUND", KnowledgeSource.FALLBACK.value, 0.0, []

    async def stream_answer(self, query: str, session_id: str | None = None):
        session_key = session_id or str(uuid4())
        state = await self._run_pipeline(query=query, session_key=session_key, stream=True)
        if state.direct_answer:
            yield {"type": "status", "message": "Spoorthi Chatbot is typing..."}
            yield {"type": "meta", "session_id": session_key}
            for token in re.findall(r"\S+\s*", state.direct_answer):
                yield {"type": "token", "content": token}
            self.memory_service.append_turn(session_key, "user", state.prepared_query)
            self.memory_service.append_turn(session_key, "assistant", state.direct_answer)
            self._log_answer(state.prepared_query, state.source, state.matches, state.direct_answer)
            self._log_request_complete(
                session_key=session_key,
                query=state.prepared_query,
                source=state.source,
                confidence=state.confidence,
                answer=state.direct_answer,
                stream=True,
            )
            yield {"type": "done"}
            return

        try:
            yield {"type": "status", "message": "Spoorthi Chatbot is typing..."}
            yield {
                "type": "meta",
                "source": state.source,
                "confidence": state.confidence,
                "session_id": session_key,
            }

            # If no relevant context is found, enrich the fallback with organizer contacts when available.
            if state.should_fallback:
                answer = await self._augment_fallback_with_contacts(FALLBACK_ANSWER, state.context)
                for token in re.findall(r"\S+\s*", answer):
                    yield {"type": "token", "content": token}
            else:
                answer_parts: list[str] = []
                async for token in self.llm_service.stream_response(context=state.context, query=state.prepared_query):
                    answer_parts.append(token)
                    yield {"type": "token", "content": token}

                answer = "".join(answer_parts).strip() or FALLBACK_ANSWER
                answer = await self._augment_fallback_with_contacts(answer, state.context)

            self.memory_service.append_turn(session_key, "user", state.prepared_query)
            self.memory_service.append_turn(session_key, "assistant", answer)
            self._log_answer(state.prepared_query, state.source, state.matches, answer)
            self._log_request_complete(
                session_key=session_key,
                query=state.prepared_query,
                source=state.source,
                confidence=state.confidence,
                answer=answer,
                stream=True,
            )
            yield {"type": "done"}
        except Exception as exc:
            logger.exception("Streaming answer failed for query=%r", state.prepared_query)
            yield {"type": "error", "message": str(exc)}
            yield {"type": "done"}

    def _prepare_query(self, query: str) -> str:
        prepared = re.sub(r"\s+", " ", query).strip()
        return prepared

    async def _run_pipeline(self, *, query: str, session_key: str, stream: bool) -> PipelineState:
        raw_query = query
        prepared_query = self._prepare_query(raw_query)
        self._log_request_start(
            session_key=session_key,
            raw_query=raw_query,
            prepared_query=prepared_query,
            stream=stream,
        )

        direct_answer = route_predefined_query(prepared_query)
        if direct_answer:
            return PipelineState(
                session_id=session_key,
                raw_query=raw_query,
                prepared_query=prepared_query,
                retrieval_query=prepared_query,
                context="DIRECT_ANSWER",
                source=KnowledgeSource.DOCUMENT.value,
                confidence=1.0,
                direct_answer=direct_answer,
            )

        retrieval_query = self._build_retrieval_query(session_key, prepared_query)
        context, source, confidence, selected = await self.retrieve_context(
            retrieval_query,
            session_key,
            focus_query=prepared_query,
        )
        self._log_context_flow(
            raw_query=raw_query,
            query=prepared_query,
            retrieval_query=retrieval_query,
            source=source,
            confidence=confidence,
            matches=selected,
            context=context,
        )
        return PipelineState(
            session_id=session_key,
            raw_query=raw_query,
            prepared_query=prepared_query,
            retrieval_query=retrieval_query,
            context=context,
            source=source,
            confidence=confidence,
            matches=selected,
        )

    async def _resolve_answer(self, state: PipelineState) -> str:
        if state.direct_answer:
            return state.direct_answer
        if state.should_fallback:
            return await self._augment_fallback_with_contacts(FALLBACK_ANSWER, state.context)

        answer = await self.llm_service.generate_response(context=state.context, query=state.prepared_query)
        return await self._augment_fallback_with_contacts(answer, state.context)

    def _log_request_start(self, *, session_key: str, raw_query: str, prepared_query: str, stream: bool) -> None:
        if not self.settings.rag_debug_mode:
            return
        logger.info(
            "RAG DEBUG request_start session_id=%s stream=%s raw_query=%r prepared_query=%r",
            session_key,
            stream,
            raw_query,
            prepared_query,
        )

    def _log_request_complete(
        self,
        *,
        session_key: str,
        query: str,
        source: str,
        confidence: float,
        answer: str,
        stream: bool,
    ) -> None:
        if not self.settings.rag_debug_mode:
            return
        logger.info(
            "RAG DEBUG request_complete session_id=%s stream=%s source=%s confidence=%.3f query=%r answer_preview=%r",
            session_key,
            stream,
            source,
            confidence,
            query,
            self._preview_text(answer, limit=260),
        )

    def _evaluate_selected_relevance(self, query: str, matches: list[SearchMatch]) -> tuple[bool, dict[str, object]]:
        if not matches:
            return False, {"reason": "no-matches"}

        query_text = normalize_query_text(query)
        query_tokens = set(extract_keywords(query_text))
        if not query_tokens:
            query_tokens = set(extract_keywords(query_text, keep_generic_terms=True))
        if not query_tokens:
            return False, {"reason": "no-query-tokens"}

        combined_text = "\n".join(match.chunk.text for match in matches)
        combined_tokens = set(extract_keywords(normalize_query_text(combined_text), keep_generic_terms=True))
        exact_hits, fuzzy_hits = fuzzy_token_hits(query_tokens, combined_tokens)
        total_hits = exact_hits + (fuzzy_hits * 0.65)
        coverage = total_hits / max(1.0, len(query_tokens))
        best_rerank = max(match.rerank_score or match.score for match in matches)
        best_lexical = max(match.lexical_score for match in matches)
        sections = {match.chunk.metadata.get("section", "general") for match in matches}
        broad_query = self._is_broad_query(query_text)

        section_hint = False
        if broad_query and any(term in query_text for term in ("event", "events", "activity", "activities", "schedule", "timing", "happening")):
            section_hint = bool(sections & {"events", "schedule", "venue"})
        elif any(term in query_text for term in ("overview", "about", "history", "what is")):
            section_hint = bool(sections & {"history", "general"})
        elif any(term in query_text for term in ("contact", "coordinator", "faculty", "student", "organizer", "phone", "email")):
            section_hint = bool(sections & {"contact", "faculty", "general"})
        elif any(term in query_text for term in ("sponsor", "sponsors", "partner", "partners", "support partner", "support partners")):
            section_hint = bool(sections & {"support", "general"})
        elif any(term in query_text for term in ("finance", "budget", "fund", "expenses")):
            section_hint = bool(sections & {"finance", "general"})
        elif any(term in query_text for term in ("faculty team", "professor", "professors", "head of department", "hod")):
            section_hint = bool(sections & {"faculty", "general"})

        is_relevant = (
            (coverage >= 0.22 and (best_lexical >= 0.08 or best_rerank >= self.settings.similarity_threshold))
            or (broad_query and section_hint and best_rerank >= max(self.settings.similarity_threshold, 0.5))
        )

        return is_relevant, {
            "coverage": round(coverage, 4),
            "exact_hits": exact_hits,
            "fuzzy_hits": fuzzy_hits,
            "best_rerank": round(best_rerank, 4),
            "best_lexical": round(best_lexical, 4),
            "sections": sorted(sections),
            "broad_query": broad_query,
            "section_hint": section_hint,
        }

    def _is_broad_query(self, query_text: str) -> bool:
        if query_text.strip() in {"event", "events", "activity", "activities"}:
            return True

        broad_terms = (
            "list events",
            "list all events",
            "list all the events",
            "show events",
            "show me all the events",
            "tell me all the events",
            "all events",
            "all the events",
            "event list",
            "what events are happening",
            "today",
            "schedule",
            "agenda",
            "timing of workshops",
            "suggest some events",
            "beginner",
            "overview",
            "tell me about",
        )
        return any(term in query_text for term in broad_terms)

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

    def _log_context_flow(
        self,
        *,
        raw_query: str,
        query: str,
        retrieval_query: str,
        source: str,
        confidence: float,
        matches: list[SearchMatch],
        context: str,
    ) -> None:
        if not self.settings.rag_debug_mode:
            return

        normalized_query = normalize_query_text(query)
        selected_chunks = [
            {
                "file": match.chunk.file_name,
                "section": match.chunk.metadata.get("section", "general"),
                "score": round(match.rerank_score or match.score, 4),
                "preview": self._preview_text(match.chunk.text, limit=180),
            }
            for match in matches
        ]

        logger.info(
            "RAG DEBUG input raw_query=%r prepared_query=%r normalized_query=%r",
            raw_query,
            query,
            normalized_query,
        )
        logger.info(
            "RAG DEBUG retrieval_query=%r normalized_retrieval_query=%r",
            retrieval_query,
            normalize_query_text(retrieval_query),
        )
        logger.info("RAG DEBUG source=%s confidence=%.3f matches=%s", source, confidence, selected_chunks)
        logger.info(
            "RAG DEBUG context_empty=%s context_preview=%r",
            context in {"", "NO_CONTEXT_FOUND"},
            self._preview_text(context, limit=700),
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
        contact_query = "faculty coordinator student coordinator organizer contact email phone help desk"
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

        for block in [part.strip() for part in re.split(r"\n{2,}", cleaned_text) if part.strip()]:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if len(lines) < 2:
                continue

            nested_title: str | None = None
            nested_values: dict[str, str] = {}

            def flush_nested() -> None:
                if nested_title == "faculty coordinator" and nested_values.get("name"):
                    prioritized.append(f"Faculty Coordinator: {self._normalize_contact_value(nested_values['name'])}")
                elif nested_title == "student coordinator team" and nested_values.get("names"):
                    prioritized.append(f"Student Coordinator: {self._normalize_contact_value(nested_values['names'])}")

            for line in lines:
                if ":" not in line:
                    flush_nested()
                    nested_title = self._normalize_contact_value(line).lower()
                    nested_values = {}
                    continue

                key, value = line.split(":", 1)
                normalized_key = self._normalize_contact_value(key).lower()
                normalized_value = self._normalize_contact_value(value)
                if nested_title:
                    nested_values[normalized_key] = normalized_value

            flush_nested()

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
            has_role = "coordinator:" in lowered or "coordinators:" in lowered or "organizer:" in lowered
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
            if lowered.startswith("faculty coordinators:"):
                return (0, lowered)
            if lowered.startswith("student coordinator:"):
                return (1, lowered)
            if lowered.startswith("student coordinators:"):
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

    def _preview_text(self, text: str, *, limit: int) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= limit:
            return compact
        return compact[:limit].rstrip() + "..."
