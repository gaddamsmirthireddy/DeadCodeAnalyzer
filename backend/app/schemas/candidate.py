from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CandidateCreate(BaseModel):
    investigation_id: int
    symbol: str
    reason: str
    confidence: float = 0.0


class CandidateResponse(BaseModel):
    id: int
    investigation_id: int
    symbol: str
    reason: str
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
