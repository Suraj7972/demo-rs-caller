"""Short-lived HMAC tokens that bind a media websocket to the call Plivo answered.

The answer webhook (signature-verified) mints a token for its CallUUID and puts it in the
<Stream> URL. The websocket only runs the (paid) STT/LLM/TTS pipeline if the token is
valid AND the Plivo `start` event carries the same CallUUID, so a random client can't
open /ws/plivo and burn provider credits.
"""

import hashlib
import hmac
import time

TOKEN_TTL_S = 120  # Plivo opens the stream right after fetching the answer XML


def mint(call_id: str, secret: str, *, now: float | None = None) -> str:
    expires = int((now or time.time()) + TOKEN_TTL_S)
    return f"{expires}.{_sig(call_id, expires, secret)}"


def verify(token: str, call_id: str, secret: str, *, now: float | None = None) -> bool:
    try:
        expires_s, sig = token.split(".", 1)
        expires = int(expires_s)
    except ValueError:
        return False
    if (now or time.time()) > expires:
        return False
    return hmac.compare_digest(sig, _sig(call_id, expires, secret))


def _sig(call_id: str, expires: int, secret: str) -> str:
    msg = f"{call_id}.{expires}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
