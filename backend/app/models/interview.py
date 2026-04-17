from __future__ import annotations


import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

from app.enums import InterviewStatus


class Interview(Base):
	__tablename__ = "interviews"

	id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
	resume_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
	job_title: Mapped[str] = mapped_column(String(255), nullable=False)
	job_description: Mapped[str] = mapped_column(Text, nullable=False)
	status: Mapped[InterviewStatus] = mapped_column(
		SQLEnum(InterviewStatus, name="interview_status"),
		nullable=False,
		default=InterviewStatus.PENDING,
	)
	preferred_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

	user: Mapped["User"] = relationship(back_populates="interviews")
	resume: Mapped["Resume"] = relationship(back_populates="interviews")
	analysis: Mapped["InterviewAnalysis | None"] = relationship(back_populates="interview", uselist=False, cascade="all, delete-orphan")
	questions: Mapped[list["InterviewQuestion"]] = relationship(back_populates="interview", cascade="all, delete-orphan")
