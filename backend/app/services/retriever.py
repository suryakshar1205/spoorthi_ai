from __future__ import annotations

import logging
import re

from app.config import Settings
from app.models.domain import SearchMatch
from app.services.vector_service import VectorService
from app.utils.text import extract_keywords


logger = logging.getLogger(__name__)
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s*(?:AM|PM)\b", re.IGNORECASE)


class RetrieverService:
    def __init__(self, settings: Settings, vector_service: VectorService) -> None:
        self.settings = settings
        self.vector_service = vector_service

    async def retrieve(self, query: str, top_k: int | None = None) -> list[SearchMatch]:
        limit = top_k or max(5, self.settings.top_k)
        candidates = await self.vector_service.semantic_search(query, min(len(self.vector_service.records), limit * 4))
        query_text = query.lower()
        query_tokens = set(extract_keywords(query))
        if not query_tokens:
            query_tokens = set(extract_keywords(query, keep_generic_terms=True))
        intents = self._detect_intents(query_text)
        broad_query = self._is_broad_query(query_text)

        ranked: list[SearchMatch] = []
        for match in candidates:
            chunk_text = match.chunk.text
            lexical_score = self._lexical_score(query_tokens, chunk_text)
            intent_score, reasons = self._intent_score(intents, chunk_text, match.chunk.metadata.get("section", ""))
            quality_score = self._quality_score(chunk_text, match.chunk.metadata.get("quality", "clean"))
            total_score = (
                (match.semantic_score * 0.35)
                + (lexical_score * 0.35)
                + (intent_score * 0.2)
                + (quality_score * 0.1)
            )

            if lexical_score == 0 and intent_score == 0:
                continue
            if lexical_score == 0 and not broad_query:
                continue
            if total_score < 0.24:
                continue

            ranked.append(
                SearchMatch(
                    chunk=match.chunk,
                    score=total_score,
                    semantic_score=match.semantic_score,
                    lexical_score=lexical_score,
                    quality_score=quality_score,
                    reasons=reasons,
                )
            )

        ranked.sort(key=lambda item: item.score, reverse=True)
        final_matches = ranked[:limit]
        logger.info(
            "Retriever selected %s candidates for query=%r: %s",
            len(final_matches),
            query,
            [f"{item.chunk.file_name}:{item.chunk.metadata.get('section', 'general')}:{item.score:.2f}" for item in final_matches],
        )
        return final_matches

    def _lexical_score(self, query_tokens: set[str], text: str) -> float:
        if not query_tokens:
            return 0.0

        text_tokens = set(extract_keywords(text, keep_generic_terms=True))
        if not text_tokens:
            return 0.0

        overlap = len(query_tokens & text_tokens)
        if overlap == 0:
            return 0.0

        coverage = overlap / max(1.0, len(query_tokens))
        density = overlap / max(8.0, len(text_tokens))
        return min(1.0, (coverage * 0.8) + (density * 0.5))

    def _detect_intents(self, query_text: str) -> set[str]:
        intents: set[str] = set()

        if any(term in query_text for term in ("today", "schedule", "agenda", "timeline", "happening", "timing")):
            intents.add("schedule")
        if any(term in query_text for term in ("where", "venue", "location", "hall", "room", "auditorium", "lab")):
            intents.add("venue")
        if any(term in query_text for term in ("register", "registration", "help desk", "spot registration", "id card")):
            intents.add("registration")
        if any(
            term in query_text
            for term in (
                "contact",
                "coordinator",
                "coordinat",
                "coord",
                "faculty",
                "student coordinator",
                "email",
                "phone",
                "organizers",
                "organiz",
            )
        ):
            intents.add("contact")
        if any(term in query_text for term in ("rule", "rules", "allowed", "late entry", "team", "members")):
            intents.add("rules")
        if any(term in query_text for term in ("workshop", "presentation", "expo", "challenge", "quiz", "hackathon", "coding contest", "beginners")):
            intents.add("events")
        if any(term in query_text for term in ("history", "legacy", "about", "overview", "what is")):
            intents.add("overview")

        return intents

    def _intent_score(self, intents: set[str], text: str, section: str) -> tuple[float, list[str]]:
        if not intents:
            return 0.0, []

        lowered = text.lower()
        reasons: list[str] = []
        score = 0.0

        if "schedule" in intents and (TIME_RE.search(text) or section == "schedule"):
            score += 0.55
            reasons.append("schedule-match")
        if "venue" in intents and (section in {"venue", "schedule"} or any(term in lowered for term in ("hall", "room", "auditorium", "lab", "entrance"))):
            score += 0.45
            reasons.append("venue-match")
        if "registration" in intents and (section == "registration" or "registration" in lowered or "help desk" in lowered):
            score += 0.45
            reasons.append("registration-match")
        if "contact" in intents and (section == "contact" or any(term in lowered for term in ("coordinator", "email", "phone"))):
            score += 0.45
            reasons.append("contact-match")
        if "rules" in intents and (section == "rules" or any(term in lowered for term in ("participants", "judges", "late entry", "team"))):
            score += 0.45
            reasons.append("rules-match")
        if "events" in intents and (section in {"events", "schedule"} or any(term in lowered for term in ("workshop", "presentation", "expo", "challenge", "quiz", "cultural"))):
            score += 0.4
            reasons.append("event-match")
        if "overview" in intents and (section in {"history", "general"} or any(term in lowered for term in ("started", "legacy", "techno-cultural", "flagship"))):
            score += 0.35
            reasons.append("overview-match")

        return min(1.0, score), reasons

    def _quality_score(self, text: str, quality: str) -> float:
        lowered = text.lower()
        score = 1.0
        if quality == "noisy":
            score -= 0.25
        if "web sources" in lowered or "knowafest" in lowered or "youtube" in lowered or "instagram" in lowered:
            score -= 0.2
        if text.count("[") >= 2:
            score -= 0.2
        if "\x00" in text:
            score -= 0.25
        return max(0.1, min(1.0, score))

    def _is_broad_query(self, query_text: str) -> bool:
        broad_terms = (
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
