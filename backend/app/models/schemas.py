from __future__ import annotations

from pydantic import BaseModel, Field


class UserQuery(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    session_id: str | None = Field(default=None, min_length=8, max_length=120)


class AskResponse(BaseModel):
    answer: str
    source: str
    confidence: float
    session_id: str | None = None


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AddContextRequest(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    content: str = Field(min_length=10, max_length=50000)


class KnowledgeDocument(BaseModel):
    document_id: str
    file_name: str
    source_type: str
    created_at: str
    chunk_count: int


class KnowledgeMutationResponse(BaseModel):
    detail: str
    count: int | None = None
