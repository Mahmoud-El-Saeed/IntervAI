from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InterviewQuestion(Base):
	__tablename__ = "interview_questions"

	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	interview_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False)
	question_text: Mapped[str] = mapped_column(Text, nullable=False)
	question_type: Mapped[str] = mapped_column(String(50), nullable=False)
	expected_answer: Mapped[str] = mapped_column(Text, nullable=False)

	interview: Mapped["Interview"] = relationship(back_populates="questions")
	answers: Mapped[list["InterviewAnswer"]] = relationship(back_populates="question", cascade="all, delete-orphan")
