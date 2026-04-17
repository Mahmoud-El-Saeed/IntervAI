from pydantic import BaseModel, ConfigDict 
from uuid import UUID
from datetime import datetime
from app.enums import InterviewStatus

class InterviewCreate(BaseModel):
    resume_id: UUID
    job_title: str
    job_description: str = "" 
    preferred_language: str
    

class InterviewResponse(BaseModel):
    id: UUID
    status: InterviewStatus
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)