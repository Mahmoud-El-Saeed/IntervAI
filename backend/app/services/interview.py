from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.db.interview_analysis_crud import upsert_interview_analysis
from app.db.interview_crud import (
    create_interview,
    get_all_interviews_for_user,
    get_interview_by_id_with_resume,
    get_interview_details_for_user,
    update_interview_status,
)
from app.db.resume_curd import get_resume_by_id
from app.enums import InterviewStatus
from app.schemas.interview import (
    InterviewCreateRequest,
    InterviewCreateResponse,
    InterviewDetailsResponse,
    InterviewHistoryItemResponse,
)
from app.services.ai_service import ResumeAnalysisInput, run_resume_analysis


logger = logging.getLogger(__name__)


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


async def run_interview_resume_analysis(interview_id: UUID) -> dict:
    """Integration orchestration for Phase 1 with full DB lifecycle handling."""
    db = SessionLocal()
    try:
        interview = get_interview_by_id_with_resume(db, interview_id)
        if interview is None:
            raise ValueError("Interview not found.")

        if interview.resume is None:
            raise ValueError("Resume not found for interview.")

        update_interview_status(db, interview_id, InterviewStatus.ANALYZING_RESUME)
        logger.info("Interview %s status set to ANALYZING_RESUME", interview_id)

        analysis_input = ResumeAnalysisInput(
            interview_id=str(interview.id),
            resume_id=str(interview.resume.id),
            resume_path=interview.resume.file_path,
            job_title=interview.job_title,
            job_description=interview.job_description,
            preferred_language=interview.preferred_language,
        )

        analysis_payload = await run_resume_analysis(analysis_input)

        upsert_interview_analysis(db, interview_id, analysis_payload)
        update_interview_status(db, interview_id, InterviewStatus.ANALYSIS_COMPLETED)
        logger.info("Interview %s status set to ANALYSIS_COMPLETED", interview_id)

        return analysis_payload
    finally:
        db.close()