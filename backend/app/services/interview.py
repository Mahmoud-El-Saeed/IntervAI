from uuid import UUID

from sqlalchemy.orm import Session

from app.db.interview_crud import (
    create_interview,
    get_all_interviews_for_user,
    get_interview_details_for_user,
)
from app.db.resume_curd import get_resume_by_id
from app.schemas.interview import (
    InterviewCreateRequest,
    InterviewCreateResponse,
    InterviewDetailsResponse,
    InterviewHistoryItemResponse,
)


def create_interview_session(
    db: Session, current_user_id: UUID, payload: InterviewCreateRequest
) -> InterviewCreateResponse:
    """Create a new interview session for a user after validating resume ownership."""
    if not payload.job_title.strip():
        raise ValueError("Job title cannot be empty.")

    resume = get_resume_by_id(db, payload.resume_id)
    if not resume or resume.user_id != current_user_id:
        raise ValueError("Resume not found.")

    interview = create_interview(
        db=db,
        user_id=current_user_id,
        resume_id=payload.resume_id,
        job_title=payload.job_title.strip(),
        job_description=payload.job_description,
        preferred_language=payload.preferred_language,
    )
    return InterviewCreateResponse(interview_id=interview.id)


def get_interview_history(db: Session, current_user_id: UUID) -> list[InterviewHistoryItemResponse]:
    """Get all interviews for a user for sidebar history."""
    interviews = get_all_interviews_for_user(db, current_user_id)
    return [InterviewHistoryItemResponse.model_validate(interview) for interview in interviews]


def get_interview_details(
    db: Session, current_user_id: UUID, interview_id: UUID
) -> InterviewDetailsResponse:
    """Get interview details with nested analysis/questions/answers for the owner user."""
    interview = get_interview_details_for_user(db, interview_id, current_user_id)
    if not interview:
        raise ValueError("Interview not found.")

    return InterviewDetailsResponse.model_validate(interview)