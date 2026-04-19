from pydantic import BaseModel, ConfigDict
from uuid import UUID

class AnswerCreate(BaseModel):
    interview_id: UUID
    question_id: UUID
    user_response: str


class AnswerResponse(BaseModel):
    id: UUID
    user_response: str
    ai_feedback: str
    score: int
    audio_url: str | None
    processing_time: float

    model_config = ConfigDict(from_attributes=True)