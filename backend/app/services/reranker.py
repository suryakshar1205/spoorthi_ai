from __future__ import annotations

import logging

from app.config import Settings
from app.models.domain import SearchMatch
from app.utils.text import extract_keywords, fuzzy_token_hits, normalize_query_text


logger = logging.getLogger(__name__)


class RerankerService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def rerank(self, query: str, matches: list[SearchMatch], top_n: int | None = None) -> list[SearchMatch]:
        if not matches:
            return []

        query_text = normalize_query_text(query)
        query_tokens = set(extract_keywords(query_text))
        if not query_tokens:
            query_tokens = set(extract_keywords(query_text, keep_generic_terms=True))
        intents = self._detect_intents(query_text)
        broad_query = self._is_broad_query(query_text)
        query_tokens = self._expand_query_tokens(query_tokens, query_text, intents, broad_query)

        reranked: list[SearchMatch] = []
        for match in matches:
            text = normalize_query_text(match.chunk.text)
            metadata = match.chunk.metadata
            keyword_bonus = self._keyword_bonus(query_tokens, text)
            phrase_bonus = self._phrase_bonus(query_text, text)
            structure_bonus = self._section_adjustment(intents, broad_query, metadata.get("section", "general"))
            clean_bonus = 0.08 if metadata.get("quality", "clean") == "clean" else 0.0
            rerank_score = (
                (match.score * 0.5)
                + (match.semantic_score * 0.15)
                + (match.lexical_score * 0.2)
                + keyword_bonus
                + phrase_bonus
                + structure_bonus
                + clean_bonus
            )
            rerank_score = min(1.0, max(0.0, rerank_score))
            reranked.append(
                SearchMatch(
                    chunk=match.chunk,
                    score=rerank_score,
                    semantic_score=match.semantic_score,
                    lexical_score=match.lexical_score,
                    rerank_score=rerank_score,
                    quality_score=match.quality_score,
                    reasons=match.reasons + [f"rerank:{rerank_score:.2f}"],
                )
            )

        reranked.sort(key=lambda item: item.rerank_score or item.score, reverse=True)
        final_matches = reranked[: (top_n or 3)]
        logger.info(
            "Reranker selected %s chunks for query=%r: %s",
            len(final_matches),
            query,
            [f"{item.chunk.file_name}:{item.chunk.metadata.get('section', 'general')}:{item.rerank_score:.2f}" for item in final_matches],
        )
        return final_matches

    def _keyword_bonus(self, query_tokens: set[str], text: str) -> float:
        if not query_tokens:
            return 0.0
        text_tokens = set(extract_keywords(text, keep_generic_terms=True))
        exact_hits, fuzzy_hits = fuzzy_token_hits(query_tokens, text_tokens)
        return min(0.2, (exact_hits * 0.04) + (fuzzy_hits * 0.025))

    def _phrase_bonus(self, query_text: str, text: str) -> float:
        phrases = [
            phrase.strip()
            for phrase in query_text.replace("?", "").split(" and ")
            if len(phrase.strip()) >= 5
        ]
        for phrase in phrases:
            if phrase in text:
                return 0.16
        return 0.0

    def _detect_intents(self, query_text: str) -> set[str]:
        intents: set[str] = set()
        if any(term in query_text for term in ("today", "schedule", "agenda", "timeline", "happening", "timing")):
            intents.add("schedule")
        if any(term in query_text for term in ("where", "venue", "location", "hall", "room", "auditorium", "lab")):
            intents.add("venue")
        if any(term in query_text for term in ("register", "registration", "help desk", "spot registration", "id card")):
            intents.add("registration")
        if any(term in query_text for term in ("contact", "coordinator", "faculty", "student", "email", "phone", "organizer")):
            intents.add("contact")
        if any(term in query_text for term in ("rule", "rules", "allowed", "late entry", "team", "members")):
            intents.add("rules")
        if any(
            term in query_text
            for term in ("workshop", "presentation", "expo", "challenge", "quiz", "hackathon", "contest", "event", "events", "activities")
        ):
            intents.add("events")
        if any(term in query_text for term in ("history", "legacy", "about", "overview", "what is")):
            intents.add("overview")
        return intents

    def _expand_query_tokens(
        self,
        query_tokens: set[str],
        query_text: str,
        intents: set[str],
        broad_query: bool,
    ) -> set[str]:
        expanded = set(query_tokens)
        if "events" not in intents:
            return expanded

        if broad_query or query_text.strip() in {"event", "events", "activity", "activities"}:
            expanded.update(
                {
                    "workshop",
                    "hackathon",
                    "flashmob",
                    "ideathon",
                    "quiz",
                    "challenge",
                    "presentation",
                    "posteriza",
                    "circuit",
                    "clutch",
                    "combat",
                    "treasure",
                    "art",
                    "tech",
                    "room",
                }
            )
        return expanded

    def _section_adjustment(self, intents: set[str], broad_query: bool, section: str) -> float:
        if not intents:
            return 0.0

        section = section or "general"
        adjustment = 0.0
        if "contact" in intents and section == "contact":
            adjustment += 0.12
        if "registration" in intents and section == "registration":
            adjustment += 0.12
        if ("venue" in intents or "schedule" in intents or "events" in intents) and section in {"schedule", "venue", "events"}:
            adjustment += 0.1
        if "overview" in intents and section in {"history", "general"}:
            adjustment += 0.06
        if broad_query and "events" in intents and section in {"contact", "rules"}:
            adjustment -= 0.1
        if not broad_query and section == "history" and any(
            intent in intents for intent in ("contact", "registration", "rules", "schedule", "venue", "events")
        ):
            adjustment -= 0.18
        return adjustment

    def _is_broad_query(self, query_text: str) -> bool:
        if query_text.strip() in {"event", "events", "activity", "activities"}:
            return True

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
