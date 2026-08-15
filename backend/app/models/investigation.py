from pydantic import BaseModel


class Investigation(BaseModel):
    id: str | None = None
    repository_id: str
    status: str = "queued"
    summary: str | None = None
