from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.modules.identity.dependencies import require_scoped_permission
from app.modules.organizations.smart_import import (
    OrganizationImportCandidate,
    parse_organization_text,
)

router = APIRouter(prefix="/api/organizations", tags=["organization-import"])

_dep_create = Depends(require_scoped_permission("organizations.create"))  # noqa: B008
_MAX_IMPORT_BYTES = 5 * 1024 * 1024
_TEXT_SUFFIXES = {".txt"}


@router.post("/import-candidate", response_model=OrganizationImportCandidate)
async def import_candidate(
    file: UploadFile = File(...),
    _authorization=_dep_create,
) -> OrganizationImportCandidate:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _TEXT_SUFFIXES and file.content_type != "text/plain":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "Этот формат требует локального обработчика OCR/документов; "
                "отправка персональных данных во внешний сервис отключена."
            ),
        )

    raw = await file.read(_MAX_IMPORT_BYTES + 1)
    if len(raw) > _MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Файл реквизитов слишком большой.",
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Не удалось прочитать текстовый файл в UTF-8.",
        ) from exc

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Файл реквизитов пуст.",
        )
    return parse_organization_text(text)
