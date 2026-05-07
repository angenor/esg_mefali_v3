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

    # F08 — Attestation Vérifiable Ed25519
    # Clé privée Ed25519 au format PEM PKCS8 (multi-lignes encodées avec \n).
    # En production, doit être renseignée via secret manager.
    # En développement/tests, si vide, ``SigningKeyStore`` génère une paire éphémère.
    attestation_private_key_pem: str = ""
    attestation_public_key_id: str = "v1"
    attestation_validity_days: int = 365
    attestation_verification_base_url: str = "https://esg-mefali.com"
    # Environnement applicatif (production exige la clé Ed25519).
    env: str = "development"

    # Application
    app_version: str = "0.1.0"
    debug: bool = False

    # F05 — RGPD Mes Données + Consentements
    # Clé secrète pour signer URLs temporaires (export download). En prod, doit
    # être renseignée via secret manager. En dev/tests, fallback sur secret_key.
    export_url_signing_key: str = ""

    # SMTP (optionnel — si non configuré, mailer logue dans audit_log).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "no-reply@esg-mefali.com"

    # Politique de confidentialité actuelle (mise à jour à chaque changement majeur).
    privacy_policy_version: str = "v1.0"

    # Délai de grâce avant purge effective d'un compte supprimé (jours).
    account_deletion_grace_period_days: int = 30

    # F19 — Cron Dispatcher Rappels (APScheduler MVP single-process).
    # Active l'enregistrement du scheduler dans le lifespan FastAPI.
    apscheduler_enabled: bool = False
    # Active les endpoints debug ``/api/admin/scheduler/*``.
    admin_debug_scheduler: bool = False
    # Délai (j) sans activité avant un reminder ``intermediary_followup``.
    silence_radio_delay_days: int = 14
    # Délai (j) avant l'expiration d'une évaluation ESG (renewal J-30).
    assessment_renewal_grace_days: int = 30
    # Délai (j) avant l'expiration d'une attestation (renewal J-30).
    attestation_expiration_grace_days: int = 30
    # Liste des jours J-N pour les deadlines (CSV : "30,7,1").
    deadline_reminder_days: str = "30,7,1"
    # Limite par batch pour le dispatcher (FOR UPDATE SKIP LOCKED).
    dispatch_batch_limit: int = 100
    # Délai (j) après quoi un reminder ``sent=true`` est archivé.
    purge_old_reminders_after_days: int = 90

    @property
    def deadline_reminder_days_list(self) -> list[int]:
        """Parse la chaîne CSV ``deadline_reminder_days`` en liste d'entiers."""
        if not self.deadline_reminder_days:
            return [30, 7, 1]
        try:
            return [
                int(x.strip())
                for x in self.deadline_reminder_days.split(",")
                if x.strip()
            ]
        except ValueError:
            return [30, 7, 1]


settings = Settings()
# F05 — fallback de la clé de signature export URL sur secret_key si non définie.
if not settings.export_url_signing_key:
    settings.export_url_signing_key = settings.secret_key
