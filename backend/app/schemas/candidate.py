from pydantic import BaseModel


class CandidateCreate(BaseModel):
    repository_id: str
    symbol: str
    reason: str
    confidence: float = 0.0


class CandidateOut(CandidateCreate):
    id: str | None = None
