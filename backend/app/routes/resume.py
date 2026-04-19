from typing import Annotated
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.resume import ResumeResponse
from app.db.resume_curd import get_all_resumes_for_user
from app.services.resume import handle_resume_upload
from .dependencies import get_current_user

router = APIRouter(prefix="/resume", tags=["resume"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[ResumeResponse])
async def get_resumes(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ResumeResponse]:
    """Retrieve all resumes that belong to the authenticated user."""
    resumes = get_all_resumes_for_user(db, current_user.id)
    return [ResumeResponse.model_validate(resume) for resume in resumes]

@router.post("/upload", response_model=ResumeResponse)
async def upload_resume(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    upload_file: UploadFile = File(...),
) -> ResumeResponse:
    """Endpoint to handle resume uploads."""
    try:
        user_id = current_user.id
        resume_response = await handle_resume_upload(db, user_id, upload_file)
        return resume_response
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception:
        logger.exception("Unexpected error while uploading resume")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while uploading resume.",
        )