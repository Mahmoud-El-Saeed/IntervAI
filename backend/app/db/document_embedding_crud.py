from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.document_embedding import DocumentEmbedding


def create_document_embeddings(
    db: Session,
    resume_id: uuid.UUID,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    if len(chunks) != len(embeddings):
        raise ValueError("Embedding count mismatch for resume chunks.")

    for chunk, embedding in zip(chunks, embeddings):
        db.add(
            DocumentEmbedding(
                resume_id=resume_id,
                text_chunk=chunk,
                embedding=embedding,
            )
        )
    db.commit()


def get_relevant_document_chunks(
    db: Session,
    resume_id: uuid.UUID,
    query_vector: list[float],
    top_k: int,
) -> list[str]:
    rows = (
        db.query(DocumentEmbedding.text_chunk)
        .filter(DocumentEmbedding.resume_id == resume_id)
        .order_by(DocumentEmbedding.embedding.cosine_distance(query_vector))
        .limit(top_k)
        .all()
    )
    return [row[0] for row in rows]
