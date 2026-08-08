import uvicorn
from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.web.middleware import RequestContextMiddleware
from app.web.routes.health import router as health_router

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/api/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)
app.add_middleware(RequestContextMiddleware)
app.include_router(health_router)


def run() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
