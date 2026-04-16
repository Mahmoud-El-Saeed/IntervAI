from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base



class InterviewAnswer(Base):
	__tablename__ = "interview_answers"

	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	question_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("interview_questions.id", ondelete="CASCADE"),
		nullable=False,
	)
	user_response: Mapped[str] = mapped_column(Text, nullable=False)
	ai_feedback: Mapped[str] = mapped_column(Text, nullable=False)
	score: Mapped[int] = mapped_column(Integer, nullable=False)
	audio_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
	processing_time: Mapped[float] = mapped_column(Float, nullable=False)

	question: Mapped["InterviewQuestion"] = relationship(back_populates="answers")
