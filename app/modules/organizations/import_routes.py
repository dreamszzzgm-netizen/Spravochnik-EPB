from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.modules.identity.dependencies import require_scoped_permission
from app.modules.organizations import import_files
from app.modules.organizations.smart_import import (
    OrganizationImportCandidate,
    parse_organization_text,
)

router = APIRouter(prefix="/api/organizations", tags=["organization-import"])

_dep_create = Depends(require_scoped_permission("organizations.create"))  # noqa: B008
_MAX_IMPORT_BYTES = 5 * 1024 * 1024


@router.post("/import-candidate", response_model=OrganizationImportCandidate)
async def import_candidate(
    file: Annotated[UploadFile, File()],
    _authorization=_dep_create,
) -> OrganizationImportCandidate:
    raw = await file.read(_MAX_IMPORT_BYTES + 1)
    if len(raw) > _MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Файл реквизитов слишком большой.",
        )

    try:
        text = import_files.extract_local_import_text(
            file.filename or "",
            file.content_type,
            raw,
        )
    except import_files.UnsupportedImportFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "Этот формат требует локального обработчика OCR/документов; "
                "отправка персональных данных во внешний сервис отключена."
            ),
        ) from exc
    except import_files.InvalidImportFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось прочитать файл реквизитов: {exc}",
        ) from exc

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Файл реквизитов пуст.",
        )
    return parse_organization_text(text)
