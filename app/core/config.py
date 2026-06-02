from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    github_webhook_secret: str = Field(..., alias="GITHUB_WEBHOOK_SECRET")
    jira_webhook_token: str | None = Field(None, alias="JIRA_WEBHOOK_TOKEN")
    database_url: str = Field("sqlite:///./github_webhooks.db", alias="DATABASE_URL")
    store_raw_payload: bool = Field(False, alias="STORE_RAW_PAYLOAD")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings() # type: ignore
