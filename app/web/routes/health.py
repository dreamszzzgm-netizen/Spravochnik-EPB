from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import get_db

router = APIRouter(tags=["system"])


class HealthCheck(BaseModel):
    status: str
    database: str | None = None
    storage: str | None = None
    version: str | None = None


def check_storage(root: Path) -> bool:
    root.mkdir(parents=True, exist_ok=True)
    probe = root / ".health-probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        return probe.read_text(encoding="utf-8") == "ok"
    finally:
        probe.unlink(missing_ok=True)


@router.get("/health/live", response_model=HealthCheck)
def liveness(settings: Settings = Depends(get_settings)) -> HealthCheck:
    return HealthCheck(status="ok", version=settings.app_version)


@router.get("/health/ready", response_model=HealthCheck)
def readiness(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthCheck:
    db.execute(text("SELECT 1"))
    storage_ok = check_storage(settings.storage_root)
    return HealthCheck(
        status="ok" if storage_ok else "error",
        database="ok",
        storage="ok" if storage_ok else "error",
        version=settings.app_version,
    )


@router.get("/health", response_model=HealthCheck)
def health(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthCheck:
    return readiness(db=db, settings=settings)
