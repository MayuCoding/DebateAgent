from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import logfire


class Settings(BaseSettings):
    mistral_api_key: str = Field(..., alias="MISTRAL_API_KEY")
    model: str = Field(default="mistral-small-latest", alias="MISTRAL_MODEL")
    logfire_token: Optional[str] = Field(default=None, alias="LOGFIRE_TOKEN")
    environment: str = Field(default="dev", alias="ENVIRONMENT")
    tavily_api_key: Optional[str] = Field(default=None, alias="TAVILY_API_KEY")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    def init_observability(self) -> None:
        if self.logfire_token:
            logfire.configure(token=self.logfire_token, service_name="ai_eng_ii_assign_01", environment=self.environment)
        else:
            logfire.configure(service_name="ai_eng_ii_assign_01", environment=self.environment)
