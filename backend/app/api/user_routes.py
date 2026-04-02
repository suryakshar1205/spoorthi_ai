from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.models.schemas import AskResponse, UserQuery
from app.services.rag_service import RAGService


router = APIRouter(tags=["user"])


def get_rag_service(request: Request) -> RAGService:
    return request.app.state.rag_service


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    payload: UserQuery,
    rag_service: RAGService = Depends(get_rag_service),
) -> AskResponse:
    return await rag_service.answer_query(payload.query, session_id=payload.session_id)


@router.post("/ask/stream")
async def stream_question(
    payload: UserQuery,
    rag_service: RAGService = Depends(get_rag_service),
) -> StreamingResponse:
    async def event_stream():
        async for event in rag_service.stream_answer(payload.query, session_id=payload.session_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
