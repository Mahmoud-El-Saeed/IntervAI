from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.core.config import get_settings

settings = get_settings()


class DocumentEmbedding(Base):
    __tablename__ = "document_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        index=True,
    )
    text_chunk: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.EMBEDDING_DIMENSION), nullable=False)
    resume: Mapped["Resume"] = relationship(back_populates="document_embeddings")