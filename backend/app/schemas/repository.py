from pydantic import BaseModel


class RepositoryCreate(BaseModel):
    name: str
    url: str
    branch: str = "main"


class RepositoryOut(RepositoryCreate):
    id: str | None = None
