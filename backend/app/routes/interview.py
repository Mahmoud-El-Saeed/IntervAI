from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.db.interview_crud import get_interview_for_user
from app.models import User
from app.schemas.interview import (
    InterviewCreateRequest,
    InterviewCreateResponse,
    InterviewDetailsResponse,
    InterviewHistoryItemResponse,
)
from app.services.interview import (
    create_interview_session,
    get_interview_details,
    get_interview_history,
    run_interview_resume_analysis,
)
from .dependencies import get_current_user

router = APIRouter(prefix="/interview", tags=["interview"])


@router.post("", response_model=InterviewCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_interview(
    payload: InterviewCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InterviewCreateResponse:
    """Create a new interview session for the authenticated user."""
    try:
        return create_interview_session(db, current_user.id, payload)
    except ValueError as e:
        detail = str(e)
        error_status = (
            status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=error_status, detail=detail)


@router.get("", response_model=list[InterviewHistoryItemResponse])
async def list_interviews(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[InterviewHistoryItemResponse]:
    """Retrieve interview history for the authenticated user."""
    return get_interview_history(db, current_user.id)


@router.get("/{interview_id}", response_model=InterviewDetailsResponse)
async def get_interview_by_id(
    interview_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InterviewDetailsResponse:
    """Retrieve complete interview details for the authenticated user."""
    try:
        return get_interview_details(db, current_user.id, interview_id)
    except ValueError as e:
        detail = str(e)
        error_status = (
            status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=error_status, detail=detail)


@router.post("/{interview_id}/analysis", status_code=status.HTTP_202_ACCEPTED)
async def trigger_interview_analysis(
    interview_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    db = SessionLocal()
    try:
        interview = get_interview_for_user(db, interview_id, current_user.id)
    finally:
        db.close()

    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found.")

    background_tasks.add_task(run_interview_resume_analysis, interview_id)
    return {"detail": "Resume analysis queued.", "interview_id": str(interview_id)}