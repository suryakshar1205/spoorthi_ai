from __future__ import annotations

import hashlib
import math

import numpy as np

from app.config import Settings
from app.utils.text import extract_keywords


class EmbeddingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.dimension = settings.embedding_dimension
        self._cache: dict[str, np.ndarray] = {}

    def embed_text(self, text: str) -> np.ndarray:
        cached = self._cache.get(text)
        if cached is not None:
            return cached.copy()

        vector = np.zeros(self.dimension, dtype="float32")
        tokens = extract_keywords(text, keep_generic_terms=True)
        if not tokens:
            return vector

        for token in tokens[:4096]:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            vector[index] += sign * weight

        norm = float(np.linalg.norm(vector))
        if math.isfinite(norm) and norm > 0:
            vector /= norm

        if len(self._cache) > 4096:
            self._cache.clear()
        self._cache[text] = vector.copy()
        return vector
