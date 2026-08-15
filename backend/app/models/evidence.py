from pydantic import BaseModel


class Evidence(BaseModel):
    id: str | None = None
    candidate_id: str
    file_path: str
    line_number: int | None = None
    snippet: str
    kind: str = "static"
