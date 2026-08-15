from pydantic import BaseModel


class Repository(BaseModel):
    id: str | None = None
    name: str
    url: str
    branch: str = "main"
