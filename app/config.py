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
    # Xendit payment gateway (docs/behaviour_log_0009.md). Xendit has no
    # separate sandbox hostname — test vs live is purely which secret key
    # is configured here, both against the same api.xendit.co. `xendit_environment`
    # is informational only (a UI/log banner), never used to pick a URL.
    xendit_secret_key: str = ""
    xendit_webhook_token: str = ""
    xendit_success_redirect_url: str = "http://localhost:3000/membership/payment-success"
    xendit_failure_redirect_url: str = "http://localhost:3000/membership/payment-failed"
    xendit_environment: str = "sandbox"
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
