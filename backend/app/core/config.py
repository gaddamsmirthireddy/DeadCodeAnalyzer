from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str
    environment: str
    api_v1_prefix: str = "/api/v1"
    database_url: str
    app_version: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
