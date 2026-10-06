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
    # Feature toggle: True (default) keeps the real Xendit checkout flow
    # exactly as-is. False bypasses it entirely — "Subscribe" grants
    # Premium immediately, no invoice, no payment collected. For
    # demos/dev/staging where you don't want a real gateway in the loop;
    # never flip this in a real production environment.
    payment_gateway_enabled: bool = True
    # Comma-separated origins allowed to call this API from a browser (the
    # Next.js dev server by default). Now also called directly by
    # bracelet-website (Gio<->Auren account linking) and bangle-bazi-admin
    # (Auren accounts listing) — see AUREN_GIO_ACCOUNT_LINKING_PLAN.md.
    cors_origins: str = "http://localhost:3000"

    # Shared secret with braceletBackend, used only to sign/verify the
    # short-lived Gio<->Auren account-linking tokens (see
    # app/core/link_token.py) and to gate the one true server-to-server
    # call left (the Auren-signup sync webhook) and the admin listing
    # endpoint. Never used for normal user sessions. Placeholder below
    # MUST be replaced with a real generated secret (kept identical on
    # braceletBackend) before any non-local deploy.
    internal_link_secret: str = "dev-only-insecure-placeholder-change-before-prod"

    # braceletBackend's base URL (including /api/v1 — call sites append only
    # the route-specific path beyond that, e.g. "/internal/auren/sync-user"),
    # for the outbound Auren-signup sync and link-from-signup calls. NOT
    # localhost — this process's own "localhost" is itself inside the
    # container. host.docker.internal is Docker Desktop's route to the
    # host machine; .env overrides this for other setups.
    bracelet_backend_url: str = "http://host.docker.internal:8000/api/v1"

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
