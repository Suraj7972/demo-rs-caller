"""Plivo webhooks + media-stream websocket.

  POST /plivo/answer    Plivo fetches this when the callee answers -> <Stream> XML
  POST /plivo/status    call status / hangup callbacks and stream status callbacks
  POST /plivo/transfer  XML that <Dial>s a human (used by TelephonyProvider.transfer)
  WS   /ws/plivo        bidirectional audio -> Pipecat pipeline

Every POST is checked with X-Plivo-Signature-V3 against the PUBLIC url (PUBLIC_BASE_URL),
since behind Caddy/ngrok the app sees an internal host.
"""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket
from loguru import logger
from pipecat.runner.utils import parse_telephony_websocket
from starlette.websockets import WebSocketDisconnect

from shared.config import Settings, get_settings
from shared.db.enums import LanguageCode
from shared.providers.telephony import (
    PlivoProvider,
    TelephonyError,
    dial_xml,
    hangup_xml,
    mask_phone,
    stream_xml,
)
from voice import stream_token
from voice.bot import CallSession, run_bot
from voice.deps import get_telephony

router = APIRouter()

XML = "application/xml"


def _public_url(request: Request, settings: Settings) -> str:
    url = f"{settings.public_base_url.rstrip('/')}{request.url.path}"
    return f"{url}?{request.url.query}" if request.url.query else url


def _ws_base(settings: Settings) -> str:
    base = settings.public_base_url.rstrip("/")
    return (
        "wss://" + base.split("://", 1)[1]
        if base.startswith("https://")
        else base.replace("http://", "ws://", 1)
    )


async def verified_form(
    request: Request,
    settings: Settings = Depends(get_settings),
    plivo: PlivoProvider = Depends(get_telephony),
) -> dict[str, str]:
    form = {k: str(v) for k, v in (await request.form()).items()}
    if settings.plivo_verify_signatures and not plivo.verify_signature(
        request.method, _public_url(request, settings), request.headers, form
    ):
        logger.warning(f"rejected Plivo webhook with bad signature: {request.url.path}")
        raise HTTPException(status_code=403, detail="invalid signature")
    return form


def _language(value: str | None) -> LanguageCode:
    try:
        return LanguageCode(value or "hi")
    except ValueError:
        return LanguageCode.HI


@router.post("/plivo/answer")
async def plivo_answer(
    request: Request,
    form: dict[str, str] = Depends(verified_form),
    settings: Settings = Depends(get_settings),
) -> Response:
    call_id = form.get("CallUUID")
    if not call_id:
        raise HTTPException(status_code=400, detail="missing CallUUID")
    direction = form.get("Direction", "outbound")
    lang = _language(request.query_params.get("lang"))
    mode = request.query_params.get("mode", "test")
    logger.info(
        f"answer call={call_id} dir={direction} to={mask_phone(form.get('To', ''))} "
        f"lang={lang} mode={mode}"
    )
    token = stream_token.mint(call_id, settings.app_secret_key.get_secret_value())
    ws_url = f"{_ws_base(settings)}/ws/plivo?" + urlencode(
        {"token": token, "lang": lang.value, "mode": mode}
    )
    xml = stream_xml(
        ws_url, status_callback_url=f"{settings.public_base_url.rstrip('/')}/plivo/status"
    )
    return Response(content=xml, media_type=XML)


@router.post("/plivo/status")
async def plivo_status(form: dict[str, str] = Depends(verified_form)) -> Response:
    if "StreamID" in form or form.get("Event", "").startswith("Stream"):
        logger.info(
            f"stream status call={form.get('CallUUID')} stream={form.get('StreamID')} "
            f"event={form.get('Event')} error={form.get('Error', '')}"
        )
    else:
        logger.info(
            f"call status call={form.get('CallUUID')} status={form.get('CallStatus')} "
            f"duration={form.get('Duration')}s hangup={form.get('HangupCause')} "
            f"to={mask_phone(form.get('To', ''))}"
        )
    # Persisting to `calls` + enqueueing the post-call job is wired in with business logic.
    return Response(status_code=204)


@router.post("/plivo/transfer")
async def plivo_transfer(
    request: Request,
    _form: dict[str, str] = Depends(verified_form),
    settings: Settings = Depends(get_settings),
    plivo: PlivoProvider = Depends(get_telephony),
) -> Response:
    try:
        number = plivo.decode_transfer_token(request.query_params.get("t", ""))
    except TelephonyError:
        logger.warning("transfer with invalid/expired token -> hangup")
        return Response(content=hangup_xml(), media_type=XML)
    logger.info(f"transferring to {mask_phone(number)}")
    return Response(content=dial_xml(number, settings.plivo_caller_id), media_type=XML)


@router.websocket("/ws/plivo")
async def plivo_media(websocket: WebSocket) -> None:
    settings = get_settings()
    await websocket.accept()
    try:
        transport_type, call_data = await parse_telephony_websocket(websocket)
    except (ValueError, WebSocketDisconnect) as exc:
        logger.warning(f"media websocket closed before handshake: {exc}")
        return
    call_id, stream_id = call_data.get("call_id"), call_data.get("stream_id")
    token = websocket.query_params.get("token", "")
    if (
        transport_type != "plivo"
        or not call_id
        or not stream_id
        or not stream_token.verify(token, call_id, settings.app_secret_key.get_secret_value())
    ):
        logger.warning(f"rejected media websocket (type={transport_type}, call={call_id})")
        await websocket.close(code=1008)
        return

    session = CallSession(
        call_id=call_id,
        stream_id=stream_id,
        language=_language(websocket.query_params.get("lang")),
        mode=websocket.query_params.get("mode", "test"),
        label=f"call={call_id[:8]}",
    )
    logger.info(f"{session.label}: starting pipeline lang={session.language} mode={session.mode}")
    try:
        await run_bot(websocket, session, settings)
    except Exception:
        logger.exception(f"{session.label}: pipeline crashed")
        raise
