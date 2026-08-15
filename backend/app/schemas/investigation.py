from pydantic import BaseModel


class InvestigationCreate(BaseModel):
    repository_id: str
    summary: str | None = None


class InvestigationOut(InvestigationCreate):
    id: str | None = None
    status: str = "queued"
