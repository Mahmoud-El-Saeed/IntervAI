from pydantic import BaseModel
from uuid import UUID

class AnswerCreate(BaseModel):
    interview_id: UUID
    question_id: UUID
    user_response: str