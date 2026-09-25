from collections.abc import Iterator
from typing import Any

import pytest
from plivo.utils.signature_v3 import construct_post_url, get_signature_v3
from pydantic import SecretStr

from shared.config import Settings, get_settings
from shared.providers.telephony import PlivoProvider
from voice.deps import get_telephony
from voice.main import app

AUTH_TOKEN = "test-plivo-auth-token"
PUBLIC = "https://voice.test.example"
SECRET = "test-app-secret"


class FakePlivoClient:
    """Records SDK calls instead of hitting Plivo."""

    def __init__(self) -> None:
        self.calls_made: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        outer = self

        class _Calls:
            def create(self, **kw: Any) -> dict[str, Any]:
                outer.calls_made.append(("create", (), kw))
                return {"api_id": "x", "message": "call fired", "request_uuid": "req-123"}

            def delete(self, *a: Any, **kw: Any) -> None:
                outer.calls_made.append(("delete", a, kw))

            def update(self, *a: Any, **kw: Any) -> dict[str, Any]:
                outer.calls_made.append(("update", a, kw))
                return {"message": "call transferred"}

            def record(self, *a: Any, **kw: Any) -> dict[str, Any]:
                outer.calls_made.append(("record", a, kw))
                return {"recording_id": "rec-1", "url": "https://media.plivo.com/rec-1.mp3"}

        class _Recordings:
            def list(self, **kw: Any) -> list[dict[str, Any]]:
                outer.calls_made.append(("recordings.list", (), kw))
                return [
                    {
                        "recording_id": "rec-1",
                        "recording_url": "https://media.plivo.com/rec-1.mp3",
                        "recording_duration_ms": "61000.00000",
                        "recording_format": "mp3",
                    }
                ]

        self.calls = _Calls()
        self.recordings = _Recordings()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        public_base_url=PUBLIC,
        plivo_auth_id="MAXXXXXXXXXXXXXXXXXX",
        plivo_auth_token=SecretStr(AUTH_TOKEN),
        plivo_caller_id="+912212345678",
        app_secret_key=SecretStr(SECRET),
        sarvam_api_key=SecretStr("sk-test"),
    )


@pytest.fixture
def fake_client() -> FakePlivoClient:
    return FakePlivoClient()


@pytest.fixture
def plivo(fake_client: FakePlivoClient) -> PlivoProvider:
    return PlivoProvider(
        auth_id="MAXXXXXXXXXXXXXXXXXX",
        auth_token=AUTH_TOKEN,
        public_base_url=PUBLIC,
        secret_key=SECRET,
        client=fake_client,
    )


@pytest.fixture
def client(settings: Settings, plivo: PlivoProvider) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_telephony] = lambda: plivo
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def sign() -> Any:
    """sign(url, params) -> the headers Plivo would send for a POST to `url` with `params`."""

    def _sign(
        url: str, params: dict[str, str], nonce: str = "12345678901234567890"
    ) -> dict[str, str]:
        signature = get_signature_v3(AUTH_TOKEN, construct_post_url(url, params), nonce).decode()
        return {"X-Plivo-Signature-V3": signature, "X-Plivo-Signature-V3-Nonce": nonce}

    return _sign
