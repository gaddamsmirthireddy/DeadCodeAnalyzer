from pydantic import BaseModel


class Candidate(BaseModel):
    id: str | None = None
    repository_id: str
    symbol: str
    reason: str
    confidence: float = 0.0
