from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class QuestionResponse(BaseModel):
    id: UUID
    question_text: str

    model_config = ConfigDict(from_attributes=True)