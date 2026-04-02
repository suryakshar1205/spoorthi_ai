from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "please",
    "the",
    "to",
    "today",
    "what",
    "when",
    "where",
    "who",
    "with",
}


class EmbeddingService:
    def __init__(self) -> None:
        self._idf: dict[str, float] = {}

    @staticmethod
    def tokenize(text: str) -> list[str]:
        lowered = text.lower()
        tokens = re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", lowered)
        return [token for token in tokens if token not in STOP_WORDS and len(token) > 1]

    def fit(self, texts: Iterable[str]) -> None:
        documents = list(texts)
        total_docs = max(len(documents), 1)
        doc_frequency: Counter[str] = Counter()

        for text in documents:
            doc_frequency.update(set(self.tokenize(text)))

        self._idf = {
            token: math.log((1 + total_docs) / (1 + freq)) + 1.0
            for token, freq in doc_frequency.items()
        }

    def encode(self, text: str) -> dict[str, float]:
        tokens = self.tokenize(text)
        if not tokens:
            return {}

        counts = Counter(tokens)
        max_tf = max(counts.values()) or 1
        vector: dict[str, float] = {}

        for token, count in counts.items():
            idf = self._idf.get(token, 1.0)
            tf = 0.5 + 0.5 * (count / max_tf)
            vector[token] = tf * idf
        return vector

    @staticmethod
    def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
        if not left or not right:
            return 0.0

        shared = set(left) & set(right)
        dot_product = sum(left[token] * right[token] for token in shared)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))

        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return dot_product / (left_norm * right_norm)
