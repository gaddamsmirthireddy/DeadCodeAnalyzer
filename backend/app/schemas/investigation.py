from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InvestigationCreate(BaseModel):
    repository_id: int
    summary: str | None = None
    trace_file: str | None = None


class InvestigationResponse(BaseModel):
    id: int
    repository_id: int
    status: str
    summary: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvestigationResultCandidate(BaseModel):
    id: int
    investigation_id: int
    symbol: str
    reason: str
    confidence: float
    evidence: list["EvidenceResponse"] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvestigationResultsResponse(BaseModel):
    investigation_id: int
    repository_id: int
    repository_name: str
    status: str
    summary: str | None
    created_at: datetime
    candidate_count: int
    candidates: list[InvestigationResultCandidate]

    model_config = ConfigDict(from_attributes=True)


from app.schemas.evidence import EvidenceResponse  # noqa: E402

InvestigationResultCandidate.model_rebuild()
