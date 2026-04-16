from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InterviewAnalysis(Base):
    __tablename__ = "interview_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interview_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    
    matched_skills: Mapped[dict] = mapped_column(JSONB, nullable=False)
    missing_skills: Mapped[dict] = mapped_column(JSONB, nullable=False)
    market_trends: Mapped[dict] = mapped_column(JSONB, nullable=False)
    project_summaries: Mapped[dict] = mapped_column(JSONB, nullable=False)

    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    technical_evaluation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    soft_skills_evaluation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    final_verdict: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_roadmap: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    interview: Mapped["Interview"] = relationship(back_populates="analysis")