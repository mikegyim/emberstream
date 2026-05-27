"""Natural-language query endpoint backed by the RAG service."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db import session_scope
from ..models import QueryIn, QueryOut
from ..services.rag import RAGService

router = APIRouter(prefix="/query", tags=["query"])


def get_rag() -> RAGService:
    return RAGService()


@router.post(
    "",
    response_model=QueryOut,
    summary="Ask a natural-language question over historical telemetry.",
)
async def post_query(body: QueryIn, rag: RAGService = Depends(get_rag)) -> QueryOut:
    async with session_scope() as session:
        return await rag.query(session, body.question, top_k=body.top_k)
