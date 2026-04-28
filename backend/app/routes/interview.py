from typing import Annotated
import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.db.interview_crud import get_interview_for_user
from app.enums import InterviewStatus
from app.models import User
from app.services.ai_service import InterviewAIService
from app.services.auth import verify_token
from app.schemas.interview import (
    InterviewAnalysisStatusResponse,
    InterviewCreateRequest,
    InterviewCreateResponse,
    InterviewDetailsResponse,
    InterviewHistoryItemResponse,
    InterviewStatusResponse,
    WebSocketAnswerRequest,
    WebSocketAuthRequest,
    WebSocketEvent,
    WebSocketPingRequest,
    WebSocketSessionPayload,
    WebSocketStateRequest,
)
from app.services.interview import (
    create_interview_session,
    get_interview_details,
    get_interview_history,
    run_interview_resume_analysis,
)
from .dependencies import get_current_user
import logging


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/interview", tags=["interview"])
ws_router = APIRouter(tags=["interview_ws"])
interview_ai_service = InterviewAIService()


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


@router.post("/{interview_id}/analysis", response_model=InterviewAnalysisStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_interview_analysis(
    interview_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
) -> InterviewAnalysisStatusResponse:
    db = SessionLocal()
    try:
        interview = get_interview_for_user(db, interview_id, current_user.id)
    finally:
        db.close()

    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found.")

    background_tasks.add_task(run_interview_resume_analysis, interview_id)
    return InterviewAnalysisStatusResponse(
        status=interview.status,
        interview_id=interview_id,
        detail="Resume analysis queued."
    )


@router.get("/{interview_id}/status", response_model=InterviewStatusResponse)
async def get_interview_status(
    interview_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InterviewStatusResponse:
    interview = get_interview_for_user(db, interview_id, current_user.id)
    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found.")

    ready = interview.status in (InterviewStatus.ANALYSIS_COMPLETED, InterviewStatus.FAILED_ANALYSIS)
    return InterviewStatusResponse(
        status=interview.status,
        interview_id=interview_id,
        ready=ready
    )


@ws_router.websocket("/ws/interview/{interview_id}")
async def interview_websocket(
    websocket: WebSocket,
    interview_id: UUID,
    token: str | None = Query(default=None),
) -> None:
    await websocket.accept()

    if token is None:
        try:
            auth_payload = await websocket.receive_json()
            auth_message = WebSocketAuthRequest.model_validate(auth_payload)
            token = auth_message.token
        except Exception:
            token = None

    if not token:
        await websocket.send_json(WebSocketEvent(type="error", detail="Missing token.").model_dump())
        await websocket.close(code=1008)
        return

    def _authorize() -> bool:
        db = SessionLocal()
        try:
            user = verify_token(db=db, token=token)
            interview = get_interview_for_user(db, interview_id, user.id)
            return interview is not None
        finally:
            db.close()

    try:
        authorized = await asyncio.to_thread(_authorize)
    except Exception:
        await websocket.send_json(
            WebSocketEvent(type="error", detail="Invalid or expired token.").model_dump()
        )
        await websocket.close(code=1008)
        return

    if not authorized:
        await websocket.send_json(WebSocketEvent(type="error", detail="Interview not found.").model_dump())
        await websocket.close(code=1008)
        return

    try:
        logger.info("Starting interview %s", interview_id)
        start_payload = await interview_ai_service.start_interview(interview_id)
        await websocket.send_json(
            WebSocketEvent(
                type="session_started",
                data=WebSocketSessionPayload.model_validate(start_payload),
            ).model_dump()
        )

        while True:
            payload = await websocket.receive_json()
            if not isinstance(payload, dict):
                await websocket.send_json(WebSocketEvent(type="error", detail="Invalid payload.").model_dump())
                continue

            message_type = payload.get("type", "answer")
            if message_type == "ping":
                WebSocketPingRequest.model_validate(payload)
                await websocket.send_json(WebSocketEvent(type="pong").model_dump())
                continue

            if message_type == "state":
                WebSocketStateRequest.model_validate(payload)
                state_payload = await interview_ai_service.get_current_state(interview_id)
                await websocket.send_json(
                    WebSocketEvent(
                        type="state",
                        data=WebSocketSessionPayload.model_validate(state_payload),
                    ).model_dump()
                )
                continue

            answer_message = WebSocketAnswerRequest.model_validate(payload)
            answer = answer_message.answer

            result = await interview_ai_service.submit_answer(interview_id, answer)
            event_type = result.get("event_type") or ("session_completed" if result.get("is_complete") else "turn_result")
            if event_type == "error":
                await websocket.send_json(
                    WebSocketEvent(
                        type="error",
                        detail=result.get("detail", "Interview processing failed."),
                    ).model_dump()
                )
            else:
                await websocket.send_json(
                    WebSocketEvent(
                        type=event_type,
                        data=WebSocketSessionPayload.model_validate(result),
                    ).model_dump()
                )

            if result.get("is_complete"):
                await websocket.close(code=1000)
                return
    except WebSocketDisconnect:
        return
    except Exception as exc:
        logger.exception("WebSocket error for interview %s: %s", interview_id, exc)
        await websocket.send_json(WebSocketEvent(type="error", detail=str(exc)).model_dump())
        await websocket.close(code=1011)