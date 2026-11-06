from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # Уровень логов задаётся переменной окружения LOG_LEVEL (регистр не важен)
    log_level: LogLevel = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value


settings = Settings()
