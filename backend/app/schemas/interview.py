from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import InterviewStatus


class InterviewCreateRequest(BaseModel):
    resume_id: UUID
    job_title: str
    job_description: str
    preferred_language: str = "en"


class InterviewCreateResponse(BaseModel):
    interview_id: UUID


class InterviewHistoryItemResponse(BaseModel):
    id: UUID
    job_title: str
    status: InterviewStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewAnswerResponse(BaseModel):
    id: UUID
    user_response: str
    ai_feedback: str
    score: int
    audio_url: str | None
    processing_time: float

    model_config = ConfigDict(from_attributes=True)


class InterviewQuestionDetailResponse(BaseModel):
    id: UUID
    question_text: str
    question_type: str
    expected_answer: str
    answers: list[InterviewAnswerResponse]

    model_config = ConfigDict(from_attributes=True)


class InterviewAnalysisResponse(BaseModel):
    id: UUID
    matched_skills: dict[str, Any]
    missing_skills: dict[str, Any]
    market_trends: dict[str, Any]
    project_summaries: dict[str, Any]
    overall_score: float | None
    technical_evaluation: dict[str, Any] | None
    soft_skills_evaluation: dict[str, Any] | None
    final_verdict: str | None
    learning_roadmap: dict[str, Any] | None

    model_config = ConfigDict(from_attributes=True)


class InterviewDetailsResponse(BaseModel):
    id: UUID
    resume_id: UUID
    job_title: str
    job_description: str
    preferred_language: str
    status: InterviewStatus
    created_at: datetime
    analysis: InterviewAnalysisResponse | None
    questions: list[InterviewQuestionDetailResponse]

    model_config = ConfigDict(from_attributes=True)


class InterviewAnalysisStatusResponse(BaseModel):
    status: InterviewStatus
    interview_id: UUID
    detail: str


class InterviewStatusResponse(BaseModel):
    status: InterviewStatus
    interview_id: UUID
    ready: bool


class WebSocketAuthRequest(BaseModel):
    type: Literal["auth"] = "auth"
    token: str


class WebSocketAnswerRequest(BaseModel):
    type: Literal["answer"] = "answer"
    answer: str

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Answer cannot be empty.")
        return cleaned


class WebSocketStateRequest(BaseModel):
    type: Literal["state"] = "state"


class WebSocketPingRequest(BaseModel):
    type: Literal["ping"] = "ping"


class WebSocketScorePayload(BaseModel):
    total: int = 0
    asked: int = 0


class WebSocketSessionPayload(BaseModel):
    is_initialized: bool = False
    is_complete: bool = False
    current_question: str = ""
    chat_history: list[dict[str, Any]] = Field(default_factory=list)
    hint: str = ""
    last_hint: str = ""
    last_feedback: str = ""
    final_report: dict[str, Any] | None = None
    final_summary: str = ""
    score: WebSocketScorePayload = Field(default_factory=WebSocketScorePayload)
    hint_count: int = 0
    difficulty_level: str = "Medium"
    current_topic: str = "General"
    force_move_next: bool = False
    forced_penalty: int = 0


class WebSocketEvent(BaseModel):
    type: Literal[
        "session_started",
        "turn_result",
        "hint_provided",
        "session_completed",
        "state",
        "pong",
        "error",
    ]
    data: WebSocketSessionPayload | None = None
    detail: str | None = None