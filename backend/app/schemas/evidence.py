from pydantic import BaseModel


class EvidenceCreate(BaseModel):
    candidate_id: str
    file_path: str
    line_number: int | None = None
    snippet: str
    kind: str = "static"


class EvidenceOut(EvidenceCreate):
    id: str | None = None
