from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.models.domain import KnowledgeSource
from app.models.schemas import (
    AddContextRequest,
    AdminLoginRequest,
    KnowledgeDocument,
    KnowledgeMutationResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService, get_current_admin
from app.services.vector_service import VectorService
from app.utils.document import extract_text_from_upload
from app.utils.text import build_chunk_records, sanitize_filename, within_directory


router = APIRouter(prefix="/admin", tags=["admin"])


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def get_vector_service(request: Request) -> VectorService:
    return request.app.state.vector_service


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: AdminLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    if not auth_service.verify_credentials(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    token = auth_service.create_access_token(subject=payload.username)
    return TokenResponse(access_token=token)


@router.get("/docs", response_model=list[KnowledgeDocument])
async def list_docs(
    _: str = Depends(get_current_admin),
    vector_service: VectorService = Depends(get_vector_service),
) -> list[KnowledgeDocument]:
    return [KnowledgeDocument.model_validate(item) for item in vector_service.list_documents()]


@router.post("/upload", response_model=KnowledgeMutationResponse)
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    _: str = Depends(get_current_admin),
    vector_service: VectorService = Depends(get_vector_service),
) -> KnowledgeMutationResponse:
    settings = request.app.state.settings
    created_count = 0

    for upload in files:
        if not upload.filename:
            continue

        text = await extract_text_from_upload(upload)
        if not text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{upload.filename} did not contain extractable text.",
            )

        document_id = str(uuid4())
        original_name = upload.filename
        original_path = Path(original_name)
        safe_name = sanitize_filename(original_path.stem)
        extension = original_path.suffix.lower()
        stored_path = settings.upload_dir / f"{document_id}-{safe_name}{extension}"

        await upload.seek(0)
        stored_path.write_bytes(await upload.read())

        chunks = build_chunk_records(
            document_id=document_id,
            file_name=original_name,
            source_type=KnowledgeSource.DOCUMENT.value,
            text=text,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
            metadata={"file_path": str(stored_path)},
        )
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{upload.filename} could not be chunked into searchable text.",
            )
        await vector_service.add_chunks(chunks)
        created_count += 1

    return KnowledgeMutationResponse(detail="Documents indexed successfully.", count=created_count)


@router.post("/add-context", response_model=KnowledgeMutationResponse)
async def add_context(
    payload: AddContextRequest,
    request: Request,
    _: str = Depends(get_current_admin),
    vector_service: VectorService = Depends(get_vector_service),
) -> KnowledgeMutationResponse:
    settings = request.app.state.settings
    document_id = str(uuid4())
    chunks = build_chunk_records(
        document_id=document_id,
        file_name=payload.title,
        source_type=KnowledgeSource.MANUAL.value,
        text=payload.content,
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap,
        metadata={"manual": "true"},
    )
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manual context did not produce any searchable chunks.",
        )
    await vector_service.add_chunks(chunks)
    return KnowledgeMutationResponse(detail="Manual context added successfully.", count=len(chunks))


@router.delete("/delete/{document_id}", response_model=KnowledgeMutationResponse)
async def delete_document(
    document_id: str,
    request: Request,
    _: str = Depends(get_current_admin),
    vector_service: VectorService = Depends(get_vector_service),
) -> KnowledgeMutationResponse:
    settings = request.app.state.settings
    chunks = vector_service.get_document_chunks(document_id)
    deleted = await vector_service.delete_document(document_id)
    if deleted == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    paths = {chunk.metadata.get("file_path") for chunk in chunks if chunk.metadata.get("file_path")}
    for raw_path in paths:
        path = Path(raw_path)
        if path.exists() and within_directory(path, settings.upload_dir):
            os.remove(path)

    return KnowledgeMutationResponse(detail="Document deleted successfully.", count=deleted)


@router.post("/reindex", response_model=KnowledgeMutationResponse)
async def reindex(
    _: str = Depends(get_current_admin),
    vector_service: VectorService = Depends(get_vector_service),
) -> KnowledgeMutationResponse:
    total = await vector_service.rebuild_index()
    return KnowledgeMutationResponse(detail="Knowledge base rebuilt successfully.", count=total)
