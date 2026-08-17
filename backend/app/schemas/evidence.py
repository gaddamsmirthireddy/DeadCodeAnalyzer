from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvidenceCreate(BaseModel):
    candidate_id: int
    file_path: str
    line_number: int | None = None
    snippet: str
    kind: str = "static"


class EvidenceResponse(BaseModel):
    id: int
    candidate_id: int
    file_path: str
    line_number: int | None
    snippet: str
    kind: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)