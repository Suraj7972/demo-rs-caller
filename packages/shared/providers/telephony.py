"""Telephony provider interface + Plivo implementation.

Plivo's Python SDK is synchronous (requests-based), so every SDK call runs in a worker
thread via `asyncio.to_thread` to keep the event loop (and live calls) unblocked.

Verified against plivo SDK 4.x source (`plivo/resources/calls.py`, `recordings.py`,
`utils/signature_v3.py`) and Plivo docs:
  - Stream XML: https://www.plivo.com/docs/voice-agents/audio-streaming/xml/stream
  - Stream events: https://www.plivo.com/docs/voice-agents/audio-streaming/concepts/audio-streaming-reference
  - Signatures: https://www.plivo.com/docs/voice/concepts/signature-validation
"""

import asyncio
import base64
import hashlib
import re
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode
from xml.sax.saxutils import escape, quoteattr

import plivo
from cryptography.fernet import Fernet, InvalidToken
from plivo.exceptions import PlivoRestError
from plivo.utils.signature_v3 import validate_v3_signature

E164_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")
# Plivo `extraHeaders` values must be alphanumeric; we use the same rule for answer-URL metadata.
_METADATA_RE = re.compile(r"^[A-Za-z0-9]{1,64}$")


def mask_phone(phone: str) -> str:
    """+919876543210 -> +9198****3210. Use for every log line (CLAUDE.md: never log full numbers)."""
    if len(phone) <= 8:
        return "****"
    return f"{phone[:5]}{'*' * (len(phone) - 9)}{phone[-4:]}"


@dataclass(frozen=True)
class PlacedCall:
    request_id: str  # Plivo `request_uuid`; echoed back as `RequestUUID` on the answer webhook
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecordingInfo:
    recording_id: str
    url: str
    duration_ms: int | None = None
    format: str | None = None


class TelephonyError(Exception):
    pass


class TelephonyProvider(ABC):
    """What the dialer, voice bot and webhooks need from any carrier (Plivo now, Exotel later)."""

    name: str

    @abstractmethod
    async def place_call(
        self,
        to: str,
        from_: str,
        answer_url: str,
        metadata: Mapping[str, str] | None = None,
        *,
        hangup_url: str | None = None,
        time_limit_s: int | None = None,
        machine_detection: bool = False,
    ) -> PlacedCall: ...

    @abstractmethod
    async def hangup(self, call_id: str) -> None: ...

    @abstractmethod
    async def transfer(self, call_id: str, to_number: str) -> None: ...

    @abstractmethod
    async def start_recording(self, call_id: str) -> RecordingInfo | None: ...

    @abstractmethod
    async def get_recording(self, call_id: str) -> list[RecordingInfo]: ...


class PlivoProvider(TelephonyProvider):
    name = "plivo"

    def __init__(
        self,
        auth_id: str,
        auth_token: str,
        public_base_url: str,
        secret_key: str,
        *,
        client: Any | None = None,
    ) -> None:
        self._auth_token = auth_token
        self._base = public_base_url.rstrip("/")
        self._client = client or plivo.RestClient(auth_id=auth_id, auth_token=auth_token)
        self._fernet = Fernet(_fernet_key(secret_key))

    async def _sdk(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a blocking SDK call off the event loop; normalise its errors."""
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except PlivoRestError as exc:
            raise TelephonyError(f"Plivo {type(exc).__name__}: {exc}") from exc

    # ------------------------------------------------------------ calls ----

    async def place_call(
        self,
        to: str,
        from_: str,
        answer_url: str,
        metadata: Mapping[str, str] | None = None,
        *,
        hangup_url: str | None = None,
        time_limit_s: int | None = None,
        machine_detection: bool = False,
    ) -> PlacedCall:
        for number in (to, from_):
            if not E164_RE.match(number):
                raise TelephonyError(f"not an E.164 number: {mask_phone(number)}")
        url = _with_query(answer_url, _validate_metadata(metadata or {}))
        kwargs: dict[str, Any] = {
            "from_": from_,
            "to_": to,
            "answer_url": url,
            "answer_method": "POST",
        }
        if hangup_url:
            kwargs.update(hangup_url=hangup_url, hangup_method="POST")
        if time_limit_s:
            kwargs["time_limit"] = time_limit_s
        if machine_detection:
            # "hangup": Plivo drops the call itself when it detects an answering machine.
            kwargs["machine_detection"] = "hangup"
        response = await self._sdk(self._client.calls.create, **kwargs)
        request_id = _get(response, "request_uuid")
        if not request_id:
            raise TelephonyError(f"Plivo did not return request_uuid: {response}")
        return PlacedCall(request_id=str(request_id), raw=_as_dict(response))

    async def hangup(self, call_id: str) -> None:
        await self._sdk(self._client.calls.delete, call_id)

    async def transfer(self, call_id: str, to_number: str) -> None:
        """Redirect the caller (A-leg) to XML that <Dial>s `to_number`.

        The number travels encrypted in the URL so it never shows in proxy/Plivo logs.
        """
        if not E164_RE.match(to_number):
            raise TelephonyError(f"not an E.164 number: {mask_phone(to_number)}")
        token = self._fernet.encrypt(to_number.encode()).decode()
        aleg_url = f"{self._base}/plivo/transfer?{urlencode({'t': token})}"
        await self._sdk(
            self._client.calls.update, call_id, legs="aleg", aleg_url=aleg_url, aleg_method="POST"
        )

    def decode_transfer_token(self, token: str, *, max_age_s: int = 300) -> str:
        try:
            number = self._fernet.decrypt(token.encode(), ttl=max_age_s).decode()
        except InvalidToken as exc:
            raise TelephonyError("invalid or expired transfer token") from exc
        if not E164_RE.match(number):
            raise TelephonyError("transfer token does not contain a phone number")
        return number

    # -------------------------------------------------------- recording ----

    async def start_recording(self, call_id: str) -> RecordingInfo | None:
        response = await self._sdk(
            self._client.calls.record, call_id, file_format="mp3", time_limit=3600
        )
        rec_id, url = _get(response, "recording_id"), _get(response, "url")
        return (
            RecordingInfo(recording_id=str(rec_id), url=str(url), format="mp3") if rec_id else None
        )

    async def get_recording(self, call_id: str) -> list[RecordingInfo]:
        response = await self._sdk(self._client.recordings.list, call_uuid=call_id)
        out: list[RecordingInfo] = []
        for rec in response:
            duration = _get(rec, "recording_duration_ms")
            out.append(
                RecordingInfo(
                    recording_id=str(_get(rec, "recording_id")),
                    url=str(_get(rec, "recording_url")),
                    duration_ms=int(float(duration)) if duration is not None else None,
                    format=_get(rec, "recording_format"),
                )
            )
        return out

    # ------------------------------------------------------- webhooks/XML ----

    def verify_signature(
        self, method: str, url: str, headers: Mapping[str, str], params: Mapping[str, str]
    ) -> bool:
        """Validate `X-Plivo-Signature-V3` for a webhook. `url` must be the PUBLIC url."""
        signature = headers.get("x-plivo-signature-v3")
        nonce = headers.get("x-plivo-signature-v3-nonce")
        if not signature or not nonce:
            return False
        return bool(
            validate_v3_signature(
                method.upper(), url, nonce, self._auth_token, signature, dict(params)
            )
        )


def stream_xml(
    ws_url: str,
    *,
    status_callback_url: str | None = None,
    extra_headers: Mapping[str, str] | None = None,
) -> str:
    """Answer XML that opens a bidirectional µ-law 8 kHz media stream to our websocket."""
    attrs = {
        "bidirectional": "true",
        "keepCallAlive": "true",
        "contentType": "audio/x-mulaw;rate=8000",
    }
    if status_callback_url:
        attrs["statusCallbackUrl"] = status_callback_url
        attrs["statusCallbackMethod"] = "POST"
    if extra_headers:
        attrs["extraHeaders"] = ";".join(
            f"{k}={v}" for k, v in _validate_metadata(extra_headers).items()
        )
    rendered = " ".join(f"{k}={quoteattr(v)}" for k, v in attrs.items())
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<Response>\n  <Stream {rendered}>{escape(ws_url)}</Stream>\n</Response>"
    )


def dial_xml(to_number: str, caller_id: str | None = None) -> str:
    caller = f" callerId={quoteattr(caller_id)}" if caller_id else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<Response>\n  <Dial{caller}>\n    <Number>{escape(to_number)}</Number>\n  </Dial>\n"
        "</Response>"
    )


def hangup_xml() -> str:
    return '<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n  <Hangup/>\n</Response>'


# ------------------------------------------------------------ helpers ----


def _fernet_key(secret: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())


def _validate_metadata(metadata: Mapping[str, str]) -> dict[str, str]:
    out = {}
    for key, value in metadata.items():
        if not (_METADATA_RE.match(key) and _METADATA_RE.match(str(value))):
            raise TelephonyError(f"metadata must be alphanumeric (got key {key!r})")
        out[key] = str(value)
    return out


def _with_query(url: str, params: Mapping[str, str]) -> str:
    if not params:
        return url
    return f"{url}{'&' if '?' in url else '?'}{urlencode(params)}"


def _get(obj: Any, key: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _as_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, Mapping):
        return dict(obj)
    return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
