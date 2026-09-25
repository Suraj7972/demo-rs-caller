from fastapi import FastAPI

from shared.config import get_settings
from voice.plivo_routes import router as plivo_router

settings = get_settings()

app = FastAPI(title="PropCall Voice", version="0.1.0")
app.include_router(plivo_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "voice", "env": settings.app_env}
