from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.models.domain import ChunkRecord


WHITESPACE_RE = re.compile(r"[ \t]+")
BLANK_LINES_RE = re.compile(r"\n{3,}")
FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
CITATION_RE = re.compile(r"(?:\[\d+\])+")
SPACED_YEAR_RE = re.compile(r"\b(?:\d\s+){3}\d\b")
HEADING_RE = re.compile(r"^(#{1,6}\s+.+|[A-Z][A-Za-z0-9 /&()'_-]{2,}:)$")

STOPWORDS = {
    "a",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "do",
    "for",
    "from",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "please",
    "show",
    "tell",
    "that",
    "the",
    "their",
    "there",
    "these",
    "this",
    "those",
    "to",
    "us",
    "we",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "you",
    "your",
}

GENERIC_FEST_TOKENS = {
    "department",
    "ece",
    "event",
    "events",
    "fest",
    "festival",
    "jntuh",
    "spoorthi",
    "student",
    "students",
    "symposium",
    "tech",
    "technical",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def structured_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x00", "")
    text = text.replace("\u2011", "-").replace("\u2012", "-").replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("â€“", "-").replace("â€”", "-")
    lines = [WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]

    cleaned: list[str] = []
    previous_blank = True
    for line in lines:
        if not line:
            if cleaned and not previous_blank:
                cleaned.append("")
            previous_blank = True
            continue

        cleaned.append(line)
        previous_blank = False

    normalized = "\n".join(cleaned).strip()
    normalized = BLANK_LINES_RE.sub("\n\n", normalized)
    return normalized


def normalize_source_text(text: str) -> str:
    text = structured_text(text)
    text = CITATION_RE.sub("", text)
    text = SPACED_YEAR_RE.sub(lambda match: match.group(0).replace(" ", ""), text)
    text = re.sub(r"[*_`]+", "", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\|?[\s:-]+\|?$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\bo cial\b", "official", text)
    text = re.sub(r"\bagship\b", "flagship", text)
    text = re.sub(r"\bde nition\b", "definition", text)
    text = re.sub(r"\bveri able\b", "verifiable", text)
    text = re.sub(r"\bsta coordinator\b", "staff coordinator", text)
    text = re.sub(r"\btechno\s*-\s*cultural\b", "techno-cultural", text, flags=re.IGNORECASE)
    text = BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def token_count(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def extract_keywords(text: str, *, keep_generic_terms: bool = False) -> list[str]:
    tokens = [token.lower() for token in TOKEN_RE.findall(text)]
    keywords: list[str] = []

    for token in tokens:
        if len(token) <= 1 or token in STOPWORDS:
            continue
        if not keep_generic_terms and token in GENERIC_FEST_TOKENS:
            continue
        keywords.append(token)

    return keywords


def sanitize_filename(name: str) -> str:
    cleaned = FILENAME_RE.sub("-", name.strip())
    cleaned = cleaned.strip("-.")
    return cleaned or "upload"


def timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def semantic_chunk_text(
    text: str,
    *,
    target_tokens: int = 320,
    min_tokens: int = 180,
    max_tokens: int = 420,
) -> list[str]:
    normalized = normalize_source_text(text)
    if not normalized:
        return []

    blocks = _extract_blocks(normalized)
    if not blocks:
        return []

    chunks: list[str] = []
    current_blocks: list[str] = []
    current_tokens = 0

    for block in blocks:
        block_tokens = token_count(block)
        if block_tokens == 0:
            continue

        if block_tokens > max_tokens:
            large_parts = _split_large_block(block, max_tokens=max_tokens, min_tokens=min_tokens)
        else:
            large_parts = [block]

        for part in large_parts:
            part_tokens = token_count(part)
            if not current_blocks:
                current_blocks = [part]
                current_tokens = part_tokens
                continue

            candidate_tokens = current_tokens + part_tokens
            if candidate_tokens <= max_tokens and current_tokens < target_tokens:
                current_blocks.append(part)
                current_tokens = candidate_tokens
                continue

            chunks.append("\n\n".join(current_blocks).strip())
            current_blocks = [part]
            current_tokens = part_tokens

    if current_blocks:
        if chunks and current_tokens < min_tokens:
            trailing_text = "\n\n".join(current_blocks).strip()
            merged = f"{chunks[-1]}\n\n{trailing_text}".strip()
            if token_count(merged) <= max_tokens + min_tokens // 2:
                chunks[-1] = merged
            else:
                chunks.append("\n\n".join(current_blocks).strip())
        else:
            chunks.append("\n\n".join(current_blocks).strip())

    return [chunk for chunk in chunks if chunk.strip()]


def _extract_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]

    for paragraph in paragraphs:
        lines = [line.strip() for line in paragraph.split("\n") if line.strip()]
        if not lines:
            continue

        if len(lines) == 1:
            blocks.append(lines[0])
            continue

        current: list[str] = []
        for line in lines:
            if HEADING_RE.match(line) and current:
                blocks.append("\n".join(current).strip())
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append("\n".join(current).strip())

    return blocks


def _split_large_block(block: str, *, max_tokens: int, min_tokens: int) -> list[str]:
    sentences = [part.strip() for part in SENTENCE_SPLIT_RE.split(normalize_text(block)) if part.strip()]
    if not sentences:
        return [block]

    pieces: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = token_count(sentence)
        if current and current_tokens + sentence_tokens > max_tokens:
            pieces.append(" ".join(current).strip())
            current = [sentence]
            current_tokens = sentence_tokens
            continue

        current.append(sentence)
        current_tokens += sentence_tokens

    if current:
        if pieces and current_tokens < min_tokens:
            merged = f"{pieces[-1]} {' '.join(current)}".strip()
            if token_count(merged) <= max_tokens + min_tokens // 3:
                pieces[-1] = merged
            else:
                pieces.append(" ".join(current).strip())
        else:
            pieces.append(" ".join(current).strip())

    return pieces


def infer_chunk_metadata(file_name: str, text: str) -> dict[str, str]:
    lowered = text.lower()
    section = "general"

    if any(term in lowered for term in ("schedule", "timing", "09:00", "10:30", "am", "pm")):
        section = "schedule"
    elif any(term in lowered for term in ("venue", "location", "hall", "room", "auditorium", "lab")):
        section = "venue"
    elif any(term in lowered for term in ("register", "registration", "help desk", "id card")):
        section = "registration"
    elif any(term in lowered for term in ("rule", "participants", "judges", "late entry", "team")):
        section = "rules"
    elif any(term in lowered for term in ("coordinator", "email", "phone", "contact")):
        section = "contact"
    elif any(term in lowered for term in ("history", "legacy", "inception", "started", "expanded")):
        section = "history"
    elif any(term in lowered for term in ("workshop", "expo", "presentation", "quiz", "challenge", "cultural")):
        section = "events"

    quality = "clean"
    if CITATION_RE.search(text) or "\x00" in text or "web sources" in lowered:
        quality = "noisy"

    return {
        "section": section,
        "quality": quality,
        "keywords": ",".join(extract_keywords(f"{file_name} {text}")[:16]),
    }


def build_chunk_records(
    *,
    document_id: str,
    file_name: str,
    source_type: str,
    text: str,
    chunk_size: int,
    overlap: int,
    metadata: dict[str, str] | None = None,
) -> list[ChunkRecord]:
    del chunk_size
    del overlap

    created_at = timestamp_now()
    chunks = semantic_chunk_text(text)
    return [
        ChunkRecord(
            id=str(uuid4()),
            document_id=document_id,
            file_name=file_name,
            source_type=source_type,
            text=chunk,
            created_at=created_at,
            metadata={**infer_chunk_metadata(file_name, chunk), **(metadata or {})},
        )
        for chunk in chunks
    ]


def within_directory(candidate: Path, parent: Path) -> bool:
    try:
        candidate.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False
