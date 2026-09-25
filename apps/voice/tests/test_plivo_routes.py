from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

import pytest
from starlette.websockets import WebSocketDisconnect

from voice import stream_token

PUBLIC = "https://voice.test.example"
SECRET = "test-app-secret"


def _answer(client, sign, query="mode=test&lang=mr", **overrides):
    form = {
        "CallUUID": "c0ffee00-0000-4000-8000-000000000001",
        "Direction": "outbound",
        "From": "+912212345678",
        "To": "+919876543210",
        "RequestUUID": "req-123",
        **overrides,
    }
    url = f"{PUBLIC}/plivo/answer?{query}"
    return client.post(f"/plivo/answer?{query}", data=form, headers=sign(url, form)), form


def test_answer_returns_stream_xml_with_bound_token(client, sign):
    response, form = _answer(client, sign)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")

    stream = ElementTree.fromstring(response.text).find("Stream")
    assert stream is not None
    assert stream.get("bidirectional") == "true"
    assert stream.get("statusCallbackUrl") == f"{PUBLIC}/plivo/status"
    ws = urlparse(stream.text.strip())
    assert (ws.scheme, ws.netloc, ws.path) == ("wss", "voice.test.example", "/ws/plivo")
    query = parse_qs(ws.query)
    assert query["lang"] == ["mr"] and query["mode"] == ["test"]
    assert stream_token.verify(query["token"][0], form["CallUUID"], SECRET)


def test_answer_rejects_bad_or_missing_signature(client, sign):
    form = {"CallUUID": "x", "To": "+919876543210"}
    forged = sign(f"{PUBLIC}/plivo/answer", {**form, "CallUUID": "other"})
    assert client.post("/plivo/answer", data=form, headers=forged).status_code == 403
    assert client.post("/plivo/answer", data=form).status_code == 403


def test_answer_unknown_language_falls_back_to_hindi(client, sign):
    response, _ = _answer(client, sign, query="mode=test&lang=xx")
    assert "lang=hi" in response.text


def test_status_callback_accepts_signed_request(client, sign):
    form = {"CallUUID": "abc", "CallStatus": "completed", "Duration": "42", "To": "+919876543210"}
    url = f"{PUBLIC}/plivo/status"
    assert client.post("/plivo/status", data=form, headers=sign(url, form)).status_code == 204


def test_transfer_dials_decrypted_number(client, sign, plivo):
    token = plivo._fernet.encrypt(b"+919800000000").decode()
    form = {"CallUUID": "abc"}
    path = f"/plivo/transfer?t={token}"
    response = client.post(path, data=form, headers=sign(f"{PUBLIC}{path}", form))
    dial = ElementTree.fromstring(response.text).find("Dial")
    assert dial is not None and dial.findtext("Number") == "+919800000000"
    assert dial.get("callerId") == "+912212345678"


def test_transfer_with_bad_token_hangs_up(client, sign):
    form = {"CallUUID": "abc"}
    path = "/plivo/transfer?t=bogus"
    response = client.post(path, data=form, headers=sign(f"{PUBLIC}{path}", form))
    assert ElementTree.fromstring(response.text).find("Hangup") is not None


def test_media_websocket_rejects_invalid_token(client):
    start = {
        "event": "start",
        "start": {"callId": "call-1", "streamId": "stream-1"},
    }
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/plivo?token=bad&lang=hi") as ws:
            ws.send_json(start)
            ws.send_json({"event": "media", "media": {"payload": ""}})
            ws.receive_text()
    assert exc.value.code == 1008
