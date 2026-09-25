import time
from urllib.parse import parse_qs, urlparse

import pytest

from shared.providers.telephony import (
    PlivoProvider,
    TelephonyError,
    dial_xml,
    mask_phone,
    stream_xml,
)
from voice import stream_token

PUBLIC = "https://voice.test.example"
SECRET = "test-app-secret"


def test_mask_phone_hides_middle_digits():
    assert mask_phone("+919876543210") == "+9198****3210"
    assert "98765" not in mask_phone("+919876543210")
    assert mask_phone("+1") == "****"


def test_stream_xml_is_bidirectional_mulaw_and_escapes_url():
    xml = stream_xml(
        "wss://h/ws/plivo?token=a&lang=hi", status_callback_url=f"{PUBLIC}/plivo/status"
    )
    assert 'bidirectional="true"' in xml
    assert 'keepCallAlive="true"' in xml
    assert 'contentType="audio/x-mulaw;rate=8000"' in xml
    assert "token=a&amp;lang=hi" in xml
    assert "token=a&lang" not in xml


def test_stream_xml_rejects_non_alphanumeric_extra_headers():
    with pytest.raises(TelephonyError):
        stream_xml("wss://h/ws", extra_headers={"lead": "has-dash"})


def test_dial_xml():
    assert "<Number>+919800000000</Number>" in dial_xml("+919800000000", "+912212345678")


async def test_place_call_passes_metadata_limits_and_answer_url(plivo, fake_client):
    placed = await plivo.place_call(
        to="+919876543210",
        from_="+912212345678",
        answer_url=f"{PUBLIC}/plivo/answer",
        metadata={"mode": "test", "lang": "hi"},
        hangup_url=f"{PUBLIC}/plivo/status",
        time_limit_s=180,
        machine_detection=True,
    )
    assert placed.request_id == "req-123"
    name, _, kw = fake_client.calls_made[0]
    assert name == "create"
    assert kw["answer_url"] == f"{PUBLIC}/plivo/answer?mode=test&lang=hi"
    assert kw["to_"] == "+919876543210"
    assert kw["time_limit"] == 180
    assert kw["machine_detection"] == "hangup"


async def test_place_call_rejects_bad_numbers_and_metadata(plivo):
    with pytest.raises(TelephonyError):
        await plivo.place_call("98765", "+912212345678", f"{PUBLIC}/plivo/answer")
    with pytest.raises(TelephonyError):
        await plivo.place_call(
            "+919876543210", "+912212345678", f"{PUBLIC}/plivo/answer", {"x": "a b"}
        )


async def test_transfer_encrypts_number_in_url(plivo, fake_client):
    await plivo.transfer("call-1", "+919800000000")
    name, args, kw = fake_client.calls_made[0]
    assert (name, args, kw["legs"]) == ("update", ("call-1",), "aleg")
    assert "9800000000" not in kw["aleg_url"]
    token = parse_qs(urlparse(kw["aleg_url"]).query)["t"][0]
    assert plivo.decode_transfer_token(token) == "+919800000000"


def test_transfer_token_from_other_secret_is_rejected(plivo, fake_client):
    other = PlivoProvider("MA", "tok", PUBLIC, "different-secret", client=fake_client)
    token = other._fernet.encrypt(b"+919800000000").decode()
    with pytest.raises(TelephonyError):
        plivo.decode_transfer_token(token)


async def test_recordings(plivo):
    started = await plivo.start_recording("call-1")
    assert started and started.recording_id == "rec-1"
    recs = await plivo.get_recording("call-1")
    assert recs[0].duration_ms == 61000


# --------------------------------------------------------- signatures ----


def test_verify_signature_accepts_valid_and_rejects_tampered(plivo, sign):
    url = f"{PUBLIC}/plivo/status"
    params = {"CallUUID": "abc", "CallStatus": "completed"}
    headers = {k.lower(): v for k, v in sign(url, params).items()}
    assert plivo.verify_signature("POST", url, headers, params)
    assert not plivo.verify_signature("POST", url, headers, {**params, "CallStatus": "busy"})
    assert not plivo.verify_signature("POST", f"{PUBLIC}/plivo/answer", headers, params)
    assert not plivo.verify_signature("POST", url, {}, params)


# -------------------------------------------------------- stream token ----


def test_stream_token_roundtrip_expiry_and_binding():
    now = time.time()
    token = stream_token.mint("call-1", SECRET, now=now)
    assert stream_token.verify(token, "call-1", SECRET, now=now + 5)
    assert not stream_token.verify(token, "call-2", SECRET, now=now + 5)
    assert not stream_token.verify(token, "call-1", "other", now=now + 5)
    assert not stream_token.verify(token, "call-1", SECRET, now=now + stream_token.TOKEN_TTL_S + 1)
    assert not stream_token.verify("garbage", "call-1", SECRET)
