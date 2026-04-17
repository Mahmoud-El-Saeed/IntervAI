from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class ResumeResponse(BaseModel):
    id: UUID
    extracted_data: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
    
