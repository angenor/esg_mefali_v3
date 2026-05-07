"""Configuration de l'application via variables d'environnement."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Base de données
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/esg_mefali"

    # Sécurité JWT
    secret_key: str = "changez-cette-cle-en-production"
    jwt_algorithm: str = "HS256"
    # F02: durée passée à 24 h (1440 min) pour réduire la fréquence des refresh.
    access_token_expire_minutes: int = 1440
    refresh_token_expire_days: int = 30

    # F02: configuration des invitations d'équipe PME et de la rotation refresh.
    invite_token_ttl_days: int = 7
    refresh_token_grace_window_seconds: int = 5

    # OpenRouter / LLM
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-sonnet-4-20250514"

    # Aliases pour compatibilite avec le .env existant
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""

    def model_post_init(self, __context: object) -> None:
        """Mapper les variables LLM_* vers openrouter_* si non definies."""
        if not self.openrouter_api_key and self.llm_api_key:
            self.openrouter_api_key = self.llm_api_key
        if self.llm_base_url:
            self.openrouter_base_url = self.llm_base_url
        if self.llm_model:
            self.openrouter_model = self.llm_model

    # F04 — Currency / exchangerate-api.com
    exchangerate_api_key: str = ""
    exchangerate_api_base_url: str = "https://v6.exchangerate-api.com/v6"
    currency_fetch_daily_quota: int = 50

    # Application
    app_version: str = "0.1.0"
    debug: bool = False


settings = Settings()
