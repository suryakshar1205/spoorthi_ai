from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"

for env_path in (
    APP_DIR / ".env.local",
    APP_DIR / ".env",
    BASE_DIR / ".env.local",
    BASE_DIR / ".env",
):
    if env_path.exists():
        # Real environment variables must win in deployment platforms like Render.
        load_dotenv(env_path, override=False)


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _get_int(name: str, default: int) -> int:
    value = _get_env(name)
    if value is None:
        return default
    return int(value)


def _get_float(name: str, default: float) -> float:
    value = _get_env(name)
    if value is None:
        return default
    return float(value)


def _get_list(name: str, default: list[str]) -> list[str]:
    value = _get_env(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _get_bool(name: str, default: bool) -> bool:
    value = _get_env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    app_name: str = _get_env("APP_NAME", "Spoorthi Chatbot API") or "Spoorthi Chatbot API"
    api_prefix: str = _get_env("API_PREFIX", "") or ""
    allowed_origins: list[str] = None  # type: ignore[assignment]

    llm_provider: str = "local"
    local_model_name: str = _get_env("LOCAL_MODEL_NAME", "local-context") or "local-context"
    temperature: float = _get_float("LLM_TEMPERATURE", 0.35)
    max_tokens: int = _get_int("LLM_MAX_TOKENS", 700)
    response_stream_delay_ms: int = _get_int("RESPONSE_STREAM_DELAY_MS", 10)
    rag_debug_mode: bool = _get_bool("RAG_DEBUG_MODE", False)
    similarity_threshold: float = _get_float("SIMILARITY_THRESHOLD", 0.52)
    embedding_dimension: int = _get_int("EMBEDDING_DIMENSION", 512)
    chunk_size: int = _get_int("CHUNK_SIZE", 320)
    chunk_overlap: int = _get_int("CHUNK_OVERLAP", 0)
    top_k: int = _get_int("TOP_K_RESULTS", 3)
    rerank_top_n: int = _get_int("RERANK_TOP_N", 3)
    memory_turn_window: int = _get_int("MEMORY_TURN_WINDOW", 4)
    web_result_limit: int = _get_int("WEB_RESULT_LIMIT", 5)
    web_context_char_limit: int = _get_int("WEB_CONTEXT_CHAR_LIMIT", 3500)
    internet_search_provider: str = _get_env("INTERNET_SEARCH_PROVIDER", "duckduckgo") or "duckduckgo"
    serpapi_api_key: str | None = _get_env("SERPAPI_API_KEY")
    use_internet_fallback: bool = _get_bool("USE_INTERNET_FALLBACK", False)
    load_repo_knowledge: bool = _get_bool("LOAD_REPO_KNOWLEDGE", True)
    persist_runtime_knowledge: bool = _get_bool("PERSIST_RUNTIME_KNOWLEDGE", False)

    jwt_secret: str = _get_env("JWT_SECRET", "change-me-in-production") or "change-me-in-production"
    jwt_algorithm: str = _get_env("JWT_ALGORITHM", "HS256") or "HS256"
    jwt_expire_minutes: int = _get_int("JWT_EXPIRE_MINUTES", 720)
    admin_username: str = _get_env("ADMIN_USERNAME", "admin") or "admin"
    admin_password: str = _get_env("ADMIN_PASSWORD", "admin123") or "admin123"
    admin_password_hash: str | None = _get_env("ADMIN_PASSWORD_HASH")

    knowledge_dir: Path = DATA_DIR
    upload_dir: Path = UPLOAD_DIR
    faiss_index_path: Path = DATA_DIR / "knowledge.index"
    metadata_path: Path = DATA_DIR / "knowledge.json"
    bundled_knowledge_dir: Path = BASE_DIR / "sample_data"

    def __post_init__(self) -> None:
        self.llm_provider = "local"
        if self.allowed_origins is None:
            self.allowed_origins = _get_list(
                "ALLOWED_ORIGINS",
                [
                    "http://localhost:3000",
                    "http://127.0.0.1:3000",
                    "http://localhost:5500",
                    "http://127.0.0.1:5500",
                ],
            )
        normalized_origins: list[str] = []
        seen: set[str] = set()
        for origin in self.allowed_origins:
            cleaned = origin.strip().rstrip("/")
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            normalized_origins.append(cleaned)
        self.allowed_origins = normalized_origins

    @property
    def current_model(self) -> str:
        return self.local_model_name

    def ensure_directories(self) -> None:
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def iter_bundled_knowledge_files(self) -> list[Path]:
        if not self.load_repo_knowledge or not self.bundled_knowledge_dir.exists():
            return []

        supported_suffixes = {".txt", ".md", ".pdf"}
        files = [
            path
            for path in self.bundled_knowledge_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in supported_suffixes
        ]
        return sorted(files, key=lambda path: path.name.lower())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
