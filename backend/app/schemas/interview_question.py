from pydantic import BaseModel, ConfigDict
from uuid import UUID

from app.schemas.interview_answer import AnswerResponse

class QuestionResponse(BaseModel):
    id: UUID
    question_text: str

    model_config = ConfigDict(from_attributes=True)


class QuestionDetailResponse(BaseModel):
    id: UUID
    question_text: str
    question_type: str
    expected_answer: str
    answers: list[AnswerResponse]

    model_config = ConfigDict(from_attributes=True)