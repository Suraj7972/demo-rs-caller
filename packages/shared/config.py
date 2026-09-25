"""Central settings, loaded from environment variables (and `.env` at the repo root in dev).

Every env var the platform uses is declared here and documented in `.env.example`.
Secrets are `SecretStr` so they never show up in reprs or logs.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# packages/shared/config.py -> repo root. Missing file is fine (Docker passes env directly).
_REPO_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT_ENV, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    public_base_url: str = "http://localhost:8000"
    timezone: str = "Asia/Kolkata"
    audio_cache_dir: Path = Path("audio_cache")
    # Encrypts short-lived tokens (e.g. call-transfer targets in callback URLs). Any long random string.
    app_secret_key: SecretStr = SecretStr("dev-insecure-change-me")

    # --- Telephony ---
    telephony_provider: Literal["plivo", "exotel"] = "plivo"
    plivo_auth_id: str | None = None
    plivo_auth_token: SecretStr | None = None
    plivo_caller_id: str | None = None
    # Reject Plivo webhooks without a valid X-Plivo-Signature-V3. Only disable for local curl tests.
    plivo_verify_signatures: bool = True
    exotel_sid: str | None = None
    exotel_api_key: str | None = None
    exotel_api_token: SecretStr | None = None
    exotel_subdomain: str = "api.exotel.com"
    exotel_caller_id: str | None = None

    # --- Sarvam AI (STT / TTS / live LLM) ---
    sarvam_api_key: SecretStr | None = None
    sarvam_stt_model: str = "saaras:v4"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_tts_speaker: str = "shubh"

    # --- LLM: live call (cheap, fast) ---
    llm_live_provider: Literal["sarvam", "openai", "anthropic"] = "sarvam"
    llm_live_model: str = "sarvam-105b-conversations"

    # --- LLM: post-call (stronger, async) ---
    llm_postcall_provider: Literal["anthropic", "openai", "sarvam"] = "anthropic"
    llm_postcall_model: str = "claude-sonnet-5"
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    # --- Supabase ---
    supabase_url: str | None = None
    supabase_publishable_key: SecretStr | None = None
    supabase_secret_key: SecretStr | None = None
    supabase_jwt_secret: SecretStr | None = None
    supabase_db_url: SecretStr | None = None
    supabase_bucket_recordings: str = "recordings"
    supabase_bucket_media: str = "project-media"

    # --- Meta WhatsApp Cloud API ---
    whatsapp_access_token: SecretStr | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_business_account_id: str | None = None
    whatsapp_webhook_verify_token: SecretStr | None = None
    meta_app_secret: SecretStr | None = None
    meta_graph_api_version: str = "v23.0"

    # --- Lead sources ---
    meta_leads_page_access_token: SecretStr | None = None
    google_ads_webhook_key: SecretStr | None = None
    website_lead_webhook_secret: SecretStr | None = None

    # --- Redis / jobs ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Call policy defaults (per-campaign settings may narrow these) ---
    calling_window_start: str = "09:00"
    calling_window_end: str = "21:00"
    max_call_duration_s: int = 360
    silence_timeout_s: int = 10
    default_max_concurrency: int = 2

    # --- Service ports ---
    api_port: int = 8000
    voice_port: int = 8765


@lru_cache
def get_settings() -> Settings:
    return Settings()
