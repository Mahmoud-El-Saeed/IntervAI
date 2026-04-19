from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.enums import InterviewStatus
from app.models import Interview, InterviewQuestion


def create_interview(
    db: Session,
    user_id: UUID,
    resume_id: UUID,
    job_title: str,
    job_description: str,
    preferred_language: str = "en",
) -> Interview:
    """Create a new interview in pending state."""
    new_interview = Interview(
        user_id=user_id,
        resume_id=resume_id,
        job_title=job_title,
        job_description=job_description,
        preferred_language=preferred_language,
        status=InterviewStatus.PENDING,
    )
    db.add(new_interview)
    db.commit()
    db.refresh(new_interview)
    return new_interview


def get_all_interviews_for_user(db: Session, user_id: UUID) -> list[Interview]:
    """Retrieve all interviews for a specific user ordered by newest first."""
    return (
        db.query(Interview)
        .filter(Interview.user_id == user_id)
        .order_by(Interview.created_at.desc())
        .all()
    )


def get_interview_for_user(db: Session, interview_id: UUID, user_id: UUID) -> Interview | None:
    """Retrieve one interview if it belongs to the user."""
    return (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.user_id == user_id)
        .first()
    )


def get_interview_details_for_user(db: Session, interview_id: UUID, user_id: UUID) -> Interview | None:
    """Retrieve one interview with analysis, questions, and answers if it belongs to the user."""
    return (
        db.query(Interview)
        .options(
            selectinload(Interview.analysis),
            selectinload(Interview.questions).selectinload(InterviewQuestion.answers),
        )
        .filter(Interview.id == interview_id, Interview.user_id == user_id)
        .first()
    )