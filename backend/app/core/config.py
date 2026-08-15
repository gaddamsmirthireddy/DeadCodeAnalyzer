from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "DeadCodeAnalyzer"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/deadcodeanalyzer"


settings = Settings()
