from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

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