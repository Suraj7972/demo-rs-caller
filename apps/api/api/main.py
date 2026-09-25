from fastapi import FastAPI

from shared.config import get_settings

settings = get_settings()

app = FastAPI(title="PropCall API", version="0.1.0")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "api", "env": settings.app_env}
