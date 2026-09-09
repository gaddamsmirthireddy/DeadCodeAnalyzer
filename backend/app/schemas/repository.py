from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator


class RepositoryCreate(BaseModel):
    name: str | None = None
    path: str | None = None
    url: str | None = None

    @model_validator(mode="after")
    def check_path_or_url(self) -> "RepositoryCreate":
        if not self.path and not self.url:
            raise ValueError("Either 'path' (local folder) or 'url' (git clone URL) must be provided.")
        return self


class RepositoryResponse(BaseModel):
    id: int
    name: str
    path: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)