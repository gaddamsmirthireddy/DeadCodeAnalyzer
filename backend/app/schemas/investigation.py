from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InvestigationCreate(BaseModel):
    repository_id: int
    summary: str | None = None


class InvestigationResponse(BaseModel):
    id: int
    repository_id: int
    status: str
    summary: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)