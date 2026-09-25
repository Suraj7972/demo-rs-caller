"""arq entrypoint: `arq worker.main.WorkerSettings`."""

from typing import Any, ClassVar

from arq.connections import RedisSettings

from shared.config import get_settings

settings = get_settings()


async def ping(ctx: dict[str, Any]) -> str:
    """Liveness job; arq needs at least one registered function."""
    return "pong"


class WorkerSettings:
    functions: ClassVar[list[Any]] = [ping]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
