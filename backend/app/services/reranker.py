from __future__ import annotations

import logging

from app.config import Settings
from app.models.domain import SearchMatch
from app.utils.text import extract_keywords


logger = logging.getLogger(__name__)


class RerankerService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def rerank(self, query: str, matches: list[SearchMatch], top_n: int | None = None) -> list[SearchMatch]:
        if not matches:
            return []

        query_text = query.lower()
        query_tokens = set(extract_keywords(query))
        if not query_tokens:
            query_tokens = set(extract_keywords(query, keep_generic_terms=True))

        reranked: list[SearchMatch] = []
        for match in matches:
            text = match.chunk.text.lower()
            metadata = match.chunk.metadata
            keyword_bonus = self._keyword_bonus(query_tokens, text)
            phrase_bonus = self._phrase_bonus(query_text, text)
            structure_bonus = 0.08 if metadata.get("section") in {"schedule", "registration", "venue", "rules", "contact"} else 0.0
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
        hits = sum(1 for token in query_tokens if token in text)
        return min(0.18, hits * 0.04)

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
