import asyncio
import uuid

from sqlalchemy.orm import Session

from app.core.embedder import Embedder
from app.database import SessionLocal
from app.db.document_embedding_crud import get_relevant_document_chunks


def _embed_query_text(query_text: str) -> list[float]:
    embedder = Embedder()
    try:
        return embedder.embed_text(query_text)
    except Exception as exc:
        raise ValueError("Failed to generate query embedding.") from exc


def _retrieve_chunks_sync(
    resume_id: uuid.UUID,
    query_vector: list[float],
    top_k: int,
) -> list[str]:
    db = SessionLocal()
    try:
        return get_relevant_document_chunks(db, resume_id, query_vector, top_k)
    finally:
        db.close()


async def retrieve_relevant_cv_chunks(
    resume_id: uuid.UUID,
    query_text: str,
    top_k: int = 3,
) -> list[str]:
    query_vector = _embed_query_text(query_text)
    return await asyncio.to_thread(_retrieve_chunks_sync, resume_id, query_vector, top_k)
