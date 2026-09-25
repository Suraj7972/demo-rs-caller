"""Place a real smoke-test call through Plivo.

    uv run python -m apps.voice.test_call +91XXXXXXXXXX [--lang hi|mr|en]

Prereqs: the voice server is running (`make dev-voice`) and PUBLIC_BASE_URL is a public
HTTPS tunnel to it (ngrok / cloudflared). The bot greets in the chosen language (Hindi by
default), says it is an AI assistant, then chats freely. Per-turn latency is printed in the
voice server's console, not here.
"""

import argparse
import asyncio
import sys
import urllib.request

from shared.config import get_settings
from shared.providers.telephony import E164_RE, TelephonyError, mask_phone
from voice.deps import build_plivo

TEST_CALL_MAX_S = 180


def _check_tunnel(base_url: str) -> None:
    url = f"{base_url.rstrip('/')}/healthz"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310 (our own URL)
            body = resp.read().decode()
    except Exception as exc:
        sys.exit(f"PUBLIC_BASE_URL is not reachable ({url}): {exc}\nIs the tunnel running?")
    if '"voice"' not in body:
        sys.exit(f"{url} answered but is not the voice service: {body[:200]}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("to", help="Destination in E.164, e.g. +919876543210")
    parser.add_argument("--lang", choices=["hi", "mr", "en"], default="hi")
    parser.add_argument("--from", dest="from_", help="Caller ID (default: PLIVO_CALLER_ID)")
    args = parser.parse_args()

    settings = get_settings()
    caller_id = args.from_ or settings.plivo_caller_id
    missing = [
        name
        for name, value in {
            "PLIVO_AUTH_ID": settings.plivo_auth_id,
            "PLIVO_AUTH_TOKEN": settings.plivo_auth_token,
            "PLIVO_CALLER_ID (or --from)": caller_id,
            "SARVAM_API_KEY": settings.sarvam_api_key,
        }.items()
        if not value
    ]
    if missing:
        sys.exit(f"Missing: {', '.join(missing)} (set them in .env)")
    if not E164_RE.match(args.to):
        sys.exit("Destination must be E.164, e.g. +919876543210")
    if not settings.public_base_url.startswith("https://"):
        sys.exit("PUBLIC_BASE_URL must be the https:// tunnel URL that reaches the voice server")
    _check_tunnel(settings.public_base_url)

    base = settings.public_base_url.rstrip("/")
    plivo = build_plivo(settings)
    try:
        placed = await plivo.place_call(
            to=args.to,
            from_=caller_id,
            answer_url=f"{base}/plivo/answer",
            metadata={"mode": "test", "lang": args.lang},
            hangup_url=f"{base}/plivo/status",
            time_limit_s=TEST_CALL_MAX_S,
        )
    except TelephonyError as exc:
        sys.exit(f"Could not place call: {exc}")
    print(
        f"Calling {mask_phone(args.to)} in {args.lang} (request {placed.request_id}). "
        "Watch the voice server console for transcripts and [latency] lines."
    )


if __name__ == "__main__":
    asyncio.run(main())
