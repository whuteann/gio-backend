from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1"
    # Comma-separated origins allowed to call this API from a browser (the
    # Next.js dev server by default). gio-member-app is the only consumer
    # today, so this is intentionally narrow rather than "*".
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # `.env` also carries POSTGRES_* vars that only docker-compose needs (for
    # variable substitution into the db service) — ignore anything that
    # isn't one of this model's own fields rather than rejecting the file.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
