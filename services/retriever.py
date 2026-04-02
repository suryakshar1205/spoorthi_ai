from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from services.embeddings import EmbeddingService


logger = logging.getLogger("spoorthi_retriever")


@dataclass
class Chunk:
    chunk_id: str
    source: str
    section: str
    text: str
    tokens: set[str]
    vector: dict[str, float]


class RetrieverService:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.embedding_service = EmbeddingService()
        self.chunks: list[Chunk] = []
        self._load()

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    def _load(self) -> None:
        documents = self._read_documents()
        chunk_payloads: list[tuple[str, str, str]] = []

        for source_name, text in documents:
            chunk_payloads.extend(self._chunk_document(source_name, text))

        self.embedding_service.fit(chunk_text for _, _, chunk_text in chunk_payloads)

        self.chunks = []
        for index, (source, section, chunk_text) in enumerate(chunk_payloads):
            vector = self.embedding_service.encode(chunk_text)
            tokens = set(self.embedding_service.tokenize(chunk_text))
            self.chunks.append(
                Chunk(
                    chunk_id=f"{source}-{index}",
                    source=source,
                    section=section,
                    text=chunk_text,
                    tokens=tokens,
                    vector=vector,
                )
            )

    def _read_documents(self) -> list[tuple[str, str]]:
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")

        documents: list[tuple[str, str]] = []
        for path in sorted(self.data_dir.iterdir()):
            if path.suffix.lower() not in {".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8")
            cleaned = self._normalize_text(text)
            if cleaned:
                documents.append((path.name, cleaned))

        if not documents:
            raise RuntimeError(f"No supported knowledge files found in {self.data_dir}")
        return documents

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
        text = re.sub(r"\[[0-9,\s]+\]", "", text)
        text = re.sub(r"[*_`]+", "", text)
        text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\|?[\s:-]+\|?$", "", text, flags=re.MULTILINE)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _chunk_document(self, source_name: str, text: str) -> list[tuple[str, str, str]]:
        lines = text.splitlines()
        sections: list[tuple[str, list[str]]] = []
        current_section = "General Information"
        buffer: list[str] = []

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            heading = re.match(r"^#{1,6}\s+(.+)$", line)
            if heading:
                if buffer:
                    sections.append((current_section, buffer))
                    buffer = []
                current_section = heading.group(1).strip()
                continue

            buffer.append(line)

        if buffer:
            sections.append((current_section, buffer))

        chunk_payloads: list[tuple[str, str, str]] = []
        for section_name, section_lines in sections:
            chunk_payloads.extend(self._build_section_chunks(source_name, section_name, section_lines))
        return chunk_payloads

    def _build_section_chunks(
        self,
        source_name: str,
        section_name: str,
        section_lines: list[str],
        min_tokens: int = 200,
        max_tokens: int = 400,
    ) -> list[tuple[str, str, str]]:
        chunks: list[tuple[str, str, str]] = []
        current_lines = [f"Section: {section_name}"]
        current_tokens = len(self.embedding_service.tokenize(current_lines[0]))

        for line in section_lines:
            line_tokens = len(self.embedding_service.tokenize(line))
            candidate_tokens = current_tokens + line_tokens

            should_flush = current_tokens >= min_tokens and candidate_tokens > max_tokens
            if should_flush:
                chunks.append((source_name, section_name, "\n".join(current_lines).strip()))
                current_lines = [f"Section: {section_name}", line]
                current_tokens = len(self.embedding_service.tokenize(current_lines[0])) + line_tokens
            else:
                current_lines.append(line)
                current_tokens = candidate_tokens

        if len(current_lines) > 1:
            chunks.append((source_name, section_name, "\n".join(current_lines).strip()))

        return chunks

    def retrieve(self, query: str, top_k: int = 3, final_k: int = 3) -> list[dict[str, object]]:
        query = query.strip()
        if not query:
            return []

        expanded_query = self._expand_query(query)
        query_vector = self.embedding_service.encode(expanded_query)
        query_tokens = set(self.embedding_service.tokenize(expanded_query))
        intent = self._detect_intent(query_tokens)

        scored: list[dict[str, object]] = []
        for chunk in self.chunks:
            semantic_score = self.embedding_service.cosine_similarity(query_vector, chunk.vector)
            lexical_overlap = len(query_tokens & chunk.tokens)
            lexical_score = lexical_overlap / max(len(query_tokens), 1)
            phrase_score = self._phrase_score(query, chunk.text)
            section_score = self._section_bonus(intent, chunk.section, chunk.text)
            total_score = (semantic_score * 0.55) + (lexical_score * 0.25) + phrase_score + section_score

            if total_score < 0.08:
                continue

            scored.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "source": chunk.source,
                    "section": chunk.section,
                    "text": chunk.text,
                    "semantic_score": round(semantic_score, 4),
                    "lexical_score": round(lexical_score, 4),
                    "score": round(total_score, 4),
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        top_candidates = scored[:top_k]
        reranked = self._rerank(query_tokens, intent, top_candidates)

        best_score = reranked[0]["score"] if reranked else 0.0
        if best_score < 0.12:
            return []
        return reranked[:final_k]

    @staticmethod
    def _expand_query(query: str) -> str:
        synonyms = {
            "where": "venue location hall room place",
            "timing": "time schedule slot",
            "when": "time schedule timing",
            "rules": "guidelines instructions policy",
            "register": "registration sign up desk",
            "registration": "register desk sign up",
            "workshop": "session hands on training",
            "hackathon": "hackathon briefing team event",
            "beginners": "beginner easy starter introductory",
            "beginner": "easy starter introductory",
            "contact": "coordinator email phone help",
        }

        tokens = query.split()
        expansions = [synonyms[token.lower()] for token in tokens if token.lower() in synonyms]
        return " ".join([query] + expansions)

    @staticmethod
    def _detect_intent(query_tokens: set[str]) -> str:
        intent_map = {
            "schedule": {"time", "timing", "schedule", "today", "when"},
            "venue": {"venue", "location", "where", "hall", "room"},
            "registration": {"register", "registration", "desk", "entry"},
            "rules": {"rule", "rules", "guideline", "guidelines", "allowed", "policy"},
            "contact": {"contact", "coordinator", "phone", "email", "help"},
            "events": {"event", "events", "available", "list", "suggest"},
            "beginner": {"beginner", "beginners", "easy", "starter"},
        }

        for intent, keywords in intent_map.items():
            if query_tokens & keywords:
                return intent
        return "general"

    @staticmethod
    def _phrase_score(query: str, chunk_text: str) -> float:
        lowered_query = query.lower().strip()
        lowered_chunk = chunk_text.lower()
        if lowered_query and lowered_query in lowered_chunk:
            return 0.15

        query_words = [word for word in re.findall(r"[a-z0-9]+", lowered_query) if len(word) > 3]
        matched = sum(1 for word in query_words if word in lowered_chunk)
        if not query_words:
            return 0.0
        return 0.1 * (matched / len(query_words))

    @staticmethod
    def _section_bonus(intent: str, section: str, text: str) -> float:
        lowered_section = section.lower()
        lowered_text = text.lower()

        if intent == "schedule" and ("schedule" in lowered_section or re.search(r"\b(am|pm)\b", lowered_text)):
            return 0.12
        if intent == "venue" and ("venue" in lowered_section or "location" in lowered_section):
            return 0.12
        if intent == "registration" and "registration" in lowered_section:
            return 0.12
        if intent == "rules" and "rules" in lowered_section:
            return 0.12
        if intent == "contact" and "contact" in lowered_section:
            return 0.12
        if intent == "beginner" and ("event" in lowered_section or "overview" in lowered_section):
            return 0.08
        if intent == "events" and ("event" in lowered_section or "overview" in lowered_section):
            return 0.12
        return 0.0

    @staticmethod
    def _rerank(
        query_tokens: set[str],
        intent: str,
        candidates: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        reranked: list[dict[str, object]] = []

        for candidate in candidates:
            lowered_text = str(candidate["text"]).lower()
            overlap = len(query_tokens & set(re.findall(r"[a-z0-9]+", lowered_text)))
            overlap_bonus = 0.03 * min(overlap, 5)
            intent_bonus = 0.03 if intent != "general" and intent in str(candidate["section"]).lower() else 0.0
            candidate["score"] = round(float(candidate["score"]) + overlap_bonus + intent_bonus, 4)
            reranked.append(candidate)

        reranked.sort(key=lambda item: item["score"], reverse=True)
        return reranked
