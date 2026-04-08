from __future__ import annotations

import atexit
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from typing import TextIO
from uuid import NAMESPACE_URL, uuid5
import webbrowser

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin_routes import router as admin_router
from app.api.user_routes import router as user_router
from app.config import get_settings
from app.models.domain import KnowledgeSource
from app.services.auth_service import AuthService
from app.services.embeddings import EmbeddingService
from app.services.llm_service import LLMService, ProviderError
from app.services.memory import MemoryService
from app.services.rag_service import RAGService
from app.services.reranker import RerankerService
from app.services.retriever import RetrieverService
from app.services.search_service import SearchService
from app.services.vector_service import VectorService
from app.utils.document import extract_text_from_path
from app.utils.text import build_chunk_records


APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent if (BACKEND_DIR.parent / "frontend").exists() else BACKEND_DIR
FRONTEND_DIR = PROJECT_ROOT / "frontend"
LOG_DIR = PROJECT_ROOT / "logs"
FRONTEND_HOST = os.getenv("FRONTEND_HOST", "127.0.0.1")
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "3000"))
BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
DEV_MODE = os.getenv("SPOORTHI_DEV_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}
_frontend_process: subprocess.Popen[str] | None = None
_frontend_stdout: TextIO | None = None
_frontend_stderr: TextIO | None = None


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


def _is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def _npm_command(*args: str) -> list[str]:
    if os.name == "nt":
        return ["cmd", "/c", "npm", *args]
    return ["npm", *args]


def _frontend_install_command() -> list[str]:
    return _npm_command("install")


def _frontend_build_command() -> list[str]:
    return _npm_command("run", "build")


def _frontend_dev_command() -> list[str]:
    return _npm_command(
        "run",
        "dev",
        "--",
        "--hostname",
        FRONTEND_HOST,
        "--port",
        str(FRONTEND_PORT),
    )


def _frontend_start_command() -> list[str]:
    return _npm_command(
        "run",
        "start",
        "--",
        "--hostname",
        FRONTEND_HOST,
        "--port",
        str(FRONTEND_PORT),
    )


def _stop_frontend() -> None:
    global _frontend_process, _frontend_stdout, _frontend_stderr
    if _frontend_process is None:
        pass
    elif _frontend_process.poll() is None:
        _frontend_process.terminate()
        try:
            _frontend_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _frontend_process.kill()
    _frontend_process = None

    if _frontend_stdout is not None:
        _frontend_stdout.close()
        _frontend_stdout = None

    if _frontend_stderr is not None:
        _frontend_stderr.close()
        _frontend_stderr = None


def _start_frontend() -> None:
    global _frontend_process, _frontend_stdout, _frontend_stderr

    if _is_port_open(FRONTEND_PORT, FRONTEND_HOST):
        print(f"[Spoorthi Chatbot] Frontend already available at http://localhost:{FRONTEND_PORT}")
        return

    if not FRONTEND_DIR.exists():
        print(f"[Spoorthi Chatbot] Frontend directory not found: {FRONTEND_DIR}")
        return

    if not (FRONTEND_DIR / "node_modules").exists():
        print("[Spoorthi Chatbot] Frontend dependencies missing. Running npm install...")
        try:
            install_result = subprocess.run(
                _frontend_install_command(),
                cwd=str(FRONTEND_DIR),
                check=False,
            )
        except FileNotFoundError:
            print("[Spoorthi Chatbot] npm was not found. Install Node.js and npm, then try again.")
            return

        if install_result.returncode != 0:
            print("[Spoorthi Chatbot] npm install failed. Frontend was not started.")
            return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stdout_path = LOG_DIR / "frontend.out.log"
    stderr_path = LOG_DIR / "frontend.err.log"
    _frontend_stdout = stdout_path.open("w", encoding="utf-8")
    _frontend_stderr = stderr_path.open("w", encoding="utf-8")

    if DEV_MODE:
        command = _frontend_dev_command()
        startup_label = "development"
    else:
        print("[Spoorthi Chatbot] Building frontend for one-command startup...")
        build_result = subprocess.run(
            _frontend_build_command(),
            cwd=str(FRONTEND_DIR),
            check=False,
        )
        if build_result.returncode != 0:
            print("[Spoorthi Chatbot] Frontend build failed. Frontend was not started.")
            return
        command = _frontend_start_command()
        startup_label = "production"

    try:
        _frontend_process = subprocess.Popen(
            command,
            cwd=str(FRONTEND_DIR),
            stdout=_frontend_stdout,
            stderr=_frontend_stderr,
            text=True,
        )
    except FileNotFoundError:
        print("[Spoorthi Chatbot] npm was not found. Install Node.js and npm, then try again.")
        _frontend_process = None
        return

    time.sleep(4)

    if _frontend_process.poll() is not None:
        print(
            "[Spoorthi Chatbot] Frontend process exited early. "
            f"Check {stdout_path} and {stderr_path} for details."
        )
        _stop_frontend()
        return

    print(f"[Spoorthi Chatbot] Frontend started in {startup_label} mode on http://localhost:{FRONTEND_PORT}")
    print(f"[Spoorthi Chatbot] Frontend logs: {stdout_path}")


def _open_frontend_in_browser() -> None:
    url = f"http://localhost:{FRONTEND_PORT}"

    def _wait_and_open() -> None:
        for _ in range(60):
            if _is_port_open(FRONTEND_PORT, FRONTEND_HOST):
                webbrowser.open(url)
                return
            time.sleep(1)

    threading.Thread(target=_wait_and_open, daemon=True).start()


async def _load_bundled_knowledge(settings, vector_service: VectorService) -> tuple[int, int]:
    bundled_paths = settings.iter_bundled_knowledge_files()
    if not bundled_paths:
        return 0, 0

    existing_bundled_paths = {
        str(record.metadata.get("bundled_path", "")).strip()
        for record in vector_service.records
        if record.metadata.get("bundled") == "true"
    }

    loaded_count = 0
    loaded_chunks = 0
    for bundled_path in bundled_paths:
        relative_path = bundled_path.relative_to(settings.bundled_knowledge_dir).as_posix()
        if relative_path in existing_bundled_paths:
            continue

        try:
            text = extract_text_from_path(bundled_path).strip()
        except Exception:
            logging.getLogger(__name__).exception(
                "Failed to load bundled knowledge file %s", bundled_path
            )
            continue

        if not text:
            continue

        chunks = build_chunk_records(
            document_id=str(uuid5(NAMESPACE_URL, relative_path)),
            file_name=bundled_path.name,
            source_type=KnowledgeSource.DOCUMENT.value,
            text=text,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
            metadata={
                "bundled": "true",
                "bundled_path": relative_path,
                "file_path": str(bundled_path),
            },
        )
        if not chunks:
            continue

        await vector_service.add_chunks(chunks)
        loaded_count += 1
        loaded_chunks += len(chunks)

    if loaded_count:
        print(
            f"[Spoorthi Chatbot] Loaded {loaded_count} bundled knowledge file(s) from "
            f"{settings.bundled_knowledge_dir}"
        )
        print(f"[Spoorthi Chatbot] Active bundled knowledge chunks: {len(vector_service.records)}")

    return loaded_count, loaded_chunks


atexit.register(_stop_frontend)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    embedding_service = EmbeddingService(settings)
    vector_service = VectorService(settings, embedding_service=embedding_service)
    await vector_service.initialize()
    bundled_files_loaded, bundled_chunks_loaded = await _load_bundled_knowledge(settings, vector_service)

    auth_service = AuthService(settings)
    search_service = SearchService(settings)
    llm_service = LLMService(settings)
    memory_service = MemoryService(max_turns=max(6, settings.memory_turn_window * 2))
    retriever_service = RetrieverService(settings, vector_service)
    reranker_service = RerankerService(settings)
    rag_service = RAGService(
        settings=settings,
        retriever=retriever_service,
        reranker=reranker_service,
        search_service=search_service,
        llm_service=llm_service,
        memory_service=memory_service,
    )

    app.state.settings = settings
    app.state.embedding_service = embedding_service
    app.state.vector_service = vector_service
    app.state.bundled_files_loaded = bundled_files_loaded
    app.state.bundled_chunks_loaded = bundled_chunks_loaded
    app.state.auth_service = auth_service
    app.state.search_service = search_service
    app.state.llm_service = llm_service
    app.state.memory_service = memory_service
    app.state.retriever_service = retriever_service
    app.state.reranker_service = reranker_service
    app.state.rag_service = rag_service
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router)
app.include_router(admin_router)


@app.exception_handler(ProviderError)
async def provider_error_handler(_: Request, exc: ProviderError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "Spoorthi Chatbot backend is running.",
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/health")
async def healthcheck(request: Request) -> dict[str, str | int]:
    vector_service: VectorService = request.app.state.vector_service
    bundled_files = int(getattr(request.app.state, "bundled_files_loaded", 0))
    bundled_chunks = int(getattr(request.app.state, "bundled_chunks_loaded", 0))
    return {
        "status": "ok",
        "provider": settings.llm_provider,
        "model": settings.current_model,
        "knowledge_chunks": len(vector_service.records),
        "bundled_files_loaded_on_startup": bundled_files,
        "bundled_chunks_loaded_on_startup": bundled_chunks,
    }


if __name__ == "__main__":
    import uvicorn

    _start_frontend()
    _open_frontend_in_browser()
    print(f"[Spoorthi Chatbot] Backend starting on http://{BACKEND_HOST}:{BACKEND_PORT}")
    print(f"[Spoorthi Chatbot] API docs: http://{BACKEND_HOST}:{BACKEND_PORT}/docs")
    if DEV_MODE:
        print("[Spoorthi Chatbot] Dev mode is enabled. Frontend and backend will auto-reload on code changes.")
    uvicorn.run(
        "app.main:app",
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        reload=DEV_MODE,
        reload_dirs=[str(BACKEND_DIR)] if DEV_MODE else None,
    )
