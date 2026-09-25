"""Process-wide singletons for the voice service."""

from functools import lru_cache

from shared.config import Settings, get_settings
from shared.providers.telephony import PlivoProvider


@lru_cache
def get_telephony() -> PlivoProvider:
    settings = get_settings()
    return build_plivo(settings)


def build_plivo(settings: Settings) -> PlivoProvider:
    if not settings.plivo_auth_id or not settings.plivo_auth_token:
        raise RuntimeError("PLIVO_AUTH_ID and PLIVO_AUTH_TOKEN must be set")
    return PlivoProvider(
        auth_id=settings.plivo_auth_id,
        auth_token=settings.plivo_auth_token.get_secret_value(),
        public_base_url=settings.public_base_url,
        secret_key=settings.app_secret_key.get_secret_value(),
    )
