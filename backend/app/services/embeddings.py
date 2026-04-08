from __future__ import annotations

import hashlib
import logging
import math

import numpy as np

from app.config import Settings
from app.utils.text import extract_keywords, normalize_query_text


logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.dimension = settings.embedding_dimension
        self._cache: dict[str, np.ndarray] = {}

    def embed_text(self, text: str) -> np.ndarray:
        normalized_text = normalize_query_text(text)
        cached = self._cache.get(normalized_text)
        if cached is not None:
            return cached.copy()

        vector = np.zeros(self.dimension, dtype="float32")
        tokens = extract_keywords(normalized_text, keep_generic_terms=True)
        if not tokens:
            if self.settings.rag_debug_mode:
                logger.info("RAG DEBUG embedding_empty text_preview=%r", self._preview_text(text))
            return vector

        if self.settings.rag_debug_mode and "\n" not in text and len(normalized_text) <= 200:
            logger.info(
                "RAG DEBUG embedding_input raw_text=%r normalized_text=%r token_count=%s",
                self._preview_text(text),
                normalized_text,
                len(tokens),
            )

        for feature, feature_weight in self._feature_stream(tokens):
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = feature_weight * (1.0 + (digest[5] / 255.0))
            vector[index] += sign * weight

        norm = float(np.linalg.norm(vector))
        if math.isfinite(norm) and norm > 0:
            vector /= norm

        if len(self._cache) > 4096:
            self._cache.clear()
        self._cache[normalized_text] = vector.copy()
        return vector

    def _feature_stream(self, tokens: list[str]):
        emitted = 0
        for token in tokens:
            yield token, 1.0
            emitted += 1
            if emitted >= 4096:
                return

        for left, right in zip(tokens, tokens[1:], strict=False):
            yield f"{left}__{right}", 1.35
            emitted += 1
            if emitted >= 4096:
                return

        for token in tokens[:256]:
            if len(token) < 5:
                continue
            for index in range(len(token) - 2):
                yield f"char3:{token[index:index + 3]}", 0.45
                emitted += 1
                if emitted >= 4096:
                    return

    def _preview_text(self, text: str, limit: int = 160) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return compact[:limit].rstrip() + "..."
