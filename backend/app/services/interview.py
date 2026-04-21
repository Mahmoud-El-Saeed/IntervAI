from __future__ import annotations

import json
import logging
from typing import Any
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
from app.core.analysis_logging import get_analysis_logger, quiet_external_loggers
from app.enums import InterviewStatus
from app.schemas.interview import (
    InterviewCreateRequest,
    InterviewCreateResponse,
    InterviewDetailsResponse,
    InterviewHistoryItemResponse,
)
from app.services.ai_service import ResumeAnalysisInput, run_resume_analysis


logger = get_analysis_logger(__name__)


def _compact_analysis_summary(analysis_input: ResumeAnalysisInput) -> str:
    job_description_state = "present" if analysis_input.job_description.strip() else "empty"
    return (
        f"interview_id={analysis_input.interview_id}, "
        f"resume_id={analysis_input.resume_id}, "
        f"job_title={analysis_input.job_title}, "
        f"job_description={job_description_state}, "
        f"language={analysis_input.preferred_language}"
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


async def run_interview_resume_analysis(interview_id: UUID) -> dict:
    """Integration orchestration for Phase 1 with full DB lifecycle handling."""
    db: Session | None = None
    status_set_to_analyzing = False
    try:
        quiet_external_loggers()
        logger.info("analysis task started (interview_id=%s)", interview_id)

        # Phase A: read interview context and mark analysis started.
        db = SessionLocal()
        interview = get_interview_by_id_with_resume(db, interview_id)
        if interview is None:
            raise ValueError("Interview not found.")

        if interview.resume is None:
            raise ValueError("Resume not found for interview.")

        update_interview_status(db, interview_id, InterviewStatus.ANALYZING_RESUME)
        status_set_to_analyzing = True
        logger.info("Interview %s status set to ANALYZING_RESUME", interview_id)

        analysis_input = ResumeAnalysisInput(
            interview_id=str(interview.id),
            resume_id=str(interview.resume.id),
            resume_path=interview.resume.file_path,
            job_title=interview.job_title,
            job_description=interview.job_description,
            preferred_language=interview.preferred_language,
        )

        logger.info("analysis input ready (%s)", _compact_analysis_summary(analysis_input))

        db.close()
        db = None

        # Phase B: run async AI analysis with no open sync SQLAlchemy session.

        analysis_payload = await run_resume_analysis(analysis_input)

        # Phase C: persist outputs using a fresh sync SQLAlchemy session.
        db = SessionLocal()
        upsert_interview_analysis(db, interview_id, analysis_payload)
        update_interview_status(db, interview_id, InterviewStatus.ANALYSIS_COMPLETED)
        logger.info("Interview %s status set to ANALYSIS_COMPLETED", interview_id)

        return analysis_payload
    except Exception as e:
        if db is not None:
            db.close()
            db = None

        if status_set_to_analyzing:
            failure_db: Session | None = None
            try:
                failure_db = SessionLocal()
                update_interview_status(failure_db, interview_id, InterviewStatus.FAILED_ANALYSIS)
                logger.info("Interview %s status set to FAILED_ANALYSIS", interview_id)
            except Exception:
                logger.exception(
                    "Failed to set FAILED_ANALYSIS status for interview_id=%s",
                    interview_id,
                )
            finally:
                if failure_db is not None:
                    failure_db.close()

        logger.exception("analysis task failed (interview_id=%s, error=%s)", interview_id, e)
        raise
    finally:
        if db is not None:
            db.close()